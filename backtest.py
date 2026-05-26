"""
Backtest Engine — παράγει historical trades από OKX public OHLCV για ML training
Ξεχωριστά signals για momentum, mean_rev, arb — ανεξάρτητο backtest καθεμιάς
"""
import ccxt, pandas as pd, numpy as np
import json, os, logging, time, traceback
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

SYMBOLS = [
    'BTC/USDT','ETH/USDT','SOL/USDT',
    'BNB/USDT','ADA/USDT','ATOM/USDT',
]
TIMEFRAME  = '5m'
DAYS_BACK  = 180
LEVERAGE   = 2
MIN_CONF   = 0.68

# ── Data fetching ─────────────────────────────────────────────────────────────

def fetch_history(symbol, days=180):
    ex   = ccxt.okx({'enableRateLimit': True})
    sym  = symbol
    since = int((datetime.utcnow() - timedelta(days=days)).timestamp() * 1000)
    candles = []
    for _ in range(50):
        try:
            batch = ex.fetch_ohlcv(sym, TIMEFRAME, since=since, limit=300)
        except Exception as e:
            log.warning(f"fetch {symbol} batch error: {e}")
            time.sleep(2)
            continue
        if not batch:
            break
        candles.extend(batch)
        last_ts = batch[-1][0]
        if last_ts <= since:
            break
        since = last_ts + 1
        if len(batch) < 300:
            break
        time.sleep(0.3)
    if not candles:
        raise ValueError(f"No data for {symbol}")
    df = pd.DataFrame(candles, columns=['ts','open','high','low','close','volume'])
    df['ts'] = pd.to_datetime(df['ts'], unit='ms')
    df = df.drop_duplicates('ts').sort_values('ts')
    return df.set_index('ts')

# ── Feature extraction ────────────────────────────────────────────────────────

def compute_features(df, i):
    if i < 200:
        return {}
    close  = df['close']
    volume = df['volume']
    high   = df['high']
    low    = df['low']

    # RSI 14
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / (loss + 1e-10)
    rsi   = float(100 - 100 / (1 + rs.iloc[i]))

    # Bollinger Bands position (0..1: bottom..top)
    sma20  = close.iloc[i-20:i+1].mean()
    std20  = close.iloc[i-20:i+1].std()
    bb_pos = float((close.iloc[i] - (sma20 - 2*std20)) / (4 * std20 + 1e-9))
    bb_pos = max(0.0, min(1.0, bb_pos))

    # ATR %
    tr     = pd.concat([
        high.iloc[:i+1] - low.iloc[:i+1],
        (high.iloc[:i+1] - close.shift().iloc[:i+1]).abs(),
        (low.iloc[:i+1]  - close.shift().iloc[:i+1]).abs(),
    ], axis=1).max(axis=1)
    atr_val  = float(tr.rolling(14).mean().iloc[i])
    atr_pct  = atr_val / float(close.iloc[i])

    # Volume ratio
    vol_ratio = float(volume.iloc[i] / (volume.iloc[i-20:i].mean() + 1e-9))

    # Trend
    ema20  = close.ewm(span=20).mean().iloc[i]
    ema50  = close.ewm(span=50).mean().iloc[i]
    ema200 = close.ewm(span=200).mean().iloc[i]
    c = float(close.iloc[i])

    if c > ema50 > ema200:
        trend_bull, trend_bear = 1, 0
    elif c < ema50 < ema200:
        trend_bull, trend_bear = 0, 1
    else:
        trend_bull, trend_bear = 0, 0

    ts = df.index[i]
    return {
        'rsi':            round(rsi, 2),
        'bb_pos':         round(bb_pos, 4),
        'atr':            round(atr_pct, 6),
        'vol_ratio':      round(vol_ratio, 3),
        'hour':           ts.hour,
        'weekday':        ts.weekday(),
        'trend_bull':     trend_bull,
        'trend_bear':     trend_bear,
        'price_vs_ema20': round((c - ema20) / ema20, 6),
        'price_vs_ema50': round((c - ema50) / ema50, 6),
    }

# ── Trade simulation ──────────────────────────────────────────────────────────

def simulate_trade(df, i, side_str, lev=2, sl_pct=0.015, tp_pct=0.025, max_candles=144):
    entry = float(df['close'].iloc[i])
    if side_str == 'LONG':
        sl = entry * (1 - sl_pct)
        tp = entry * (1 + tp_pct)
    else:
        sl = entry * (1 + sl_pct)
        tp = entry * (1 - tp_pct)
    for j in range(1, max_candles):
        idx = i + j
        if idx >= len(df):
            break
        low  = float(df['low'].iloc[idx])
        high = float(df['high'].iloc[idx])
        if side_str == 'LONG':
            if low <= sl:
                return 'STOP_LOSS', (sl - entry) / entry * lev
            if high >= tp:
                return 'TAKE_PROFIT', (tp - entry) / entry * lev
        else:
            if high >= sl:
                return 'STOP_LOSS', (entry - sl) / entry * lev
            if low <= tp:
                return 'TAKE_PROFIT', (entry - tp) / entry * lev
    last = float(df['close'].iloc[min(i+max_candles, len(df)-1)])
    raw  = (last - entry) / entry if side_str == 'LONG' else (entry - last) / entry
    return 'TIMEOUT', raw * lev

# ── Strategy signals ──────────────────────────────────────────────────────────

def momentum_signal(df, i):
    """
    EMA crossover + volume confirmation
    LONG:  ema10 > ema30 > ema50 + vol spike
    SHORT: ema10 < ema30 < ema50 + vol spike
    """
    if i < 50:
        return 0, 0.0
    close  = df['close']
    volume = df['volume']

    ema10 = close.ewm(span=10).mean().iloc[i]
    ema30 = close.ewm(span=30).mean().iloc[i]
    ema50 = close.ewm(span=50).mean().iloc[i]

    vol_ratio = volume.iloc[i] / (volume.iloc[i-20:i].mean() + 1e-9)

    if ema10 > ema30 > ema50 and vol_ratio > 1.3:
        conf = min(0.92, 0.65 + (ema10 - ema30) / ema30 * 10)
        return 1, round(conf, 3)

    if ema10 < ema30 < ema50 and vol_ratio > 1.3:
        conf = min(0.92, 0.65 + (ema30 - ema10) / ema30 * 10)
        return -1, round(conf, 3)

    return 0, 0.0

def mean_reversion_signal(df, i):
    """
    Z-score + RSI confirmation
    LONG:  z < -2.0 AND RSI < 35 (oversold bounce)
    SHORT: z >  2.0 AND RSI > 65 (overbought rejection)
    """
    if i < 50:
        return 0, 0.0
    close = df['close']
    window = close.iloc[i-30:i+1]
    mean  = window.mean()
    std   = window.std()
    price = close.iloc[i]
    if std == 0:
        return 0, 0.0
    zscore = (price - mean) / std

    delta  = close.diff()
    gain   = delta.clip(lower=0).rolling(14).mean()
    loss   = (-delta.clip(upper=0)).rolling(14).mean()
    loss_val = loss.iloc[i]
    if loss_val == 0:
        return 0, 0.0
    rsi = 100 - 100 / (1 + gain.iloc[i] / loss_val)

    if zscore < -2.0 and rsi < 35:
        conf = min(0.92, 0.65 + abs(zscore) * 0.08)
        return 1, round(conf, 3)

    if zscore > 2.0 and rsi > 65:
        conf = min(0.92, 0.65 + abs(zscore) * 0.08)
        return -1, round(conf, 3)

    return 0, 0.0

def arbitrage_signal(df, i):
    """
    Proxy arb: VWAP spread + volume imbalance
    LONG:  price below VWAP + buying pressure
    SHORT: price above VWAP + selling pressure
    """
    if i < 30:
        return 0, 0.0
    close  = df['close']
    high   = df['high']
    low    = df['low']
    volume = df['volume']

    typical = (high + low + close) / 3
    vwap = (typical.iloc[i-20:i+1] * volume.iloc[i-20:i+1]).sum() / (volume.iloc[i-20:i+1].sum() + 1e-9)

    price = close.iloc[i]
    spread_pct = (price - vwap) / vwap

    recent   = df.iloc[i-10:i+1]
    up_vol   = recent[recent['close'] >= recent['open']]['volume'].sum()
    down_vol = recent[recent['close'] <  recent['open']]['volume'].sum()
    total_vol = up_vol + down_vol + 1e-9
    imbalance = (up_vol - down_vol) / total_vol

    if spread_pct < -0.003 and imbalance > 0.3:
        conf = min(0.92, 0.65 + abs(spread_pct) * 20)
        return 1, round(conf, 3)

    if spread_pct > 0.003 and imbalance < -0.3:
        conf = min(0.92, 0.65 + abs(spread_pct) * 20)
        return -1, round(conf, 3)

    return 0, 0.0

# ── Strategy registry ─────────────────────────────────────────────────────────

STRATEGIES_BACKTEST = {
    'momentum': momentum_signal,
    'mean_rev': mean_reversion_signal,
    'arb':      arbitrage_signal,
}

# ── Main backtest ─────────────────────────────────────────────────────────────

def run_backtest():
    all_trades = []

    for strategy_name, signal_fn in STRATEGIES_BACKTEST.items():
        strategy_trades = []
        log.info(f"\n=== Backtesting strategy: {strategy_name} ===")

        for symbol in SYMBOLS:
            log.info(f"  {symbol}...")
            try:
                df = fetch_history(symbol, DAYS_BACK)
            except Exception as e:
                log.warning(f"  SKIP {symbol}: {e}")
                continue

            i = 50
            while i < len(df) - 50:
                try:
                    signal, conf = signal_fn(df, i)
                except Exception:
                    i += 1
                    continue

                if signal == 0 or conf < MIN_CONF:
                    i += 1
                    continue

                trade_side = 'LONG' if signal == 1 else 'SHORT'
                try:
                    status, pnl = simulate_trade(df, i, trade_side,
                                                  lev=LEVERAGE,
                                                  sl_pct=0.015,
                                                  tp_pct=0.025,
                                                  max_candles=144)
                except Exception:
                    i += 1
                    continue

                features = compute_features(df, i)

                trade = {
                    'strategy':    strategy_name,
                    'symbol':      symbol,
                    'side':        trade_side,
                    'entry_price': float(df['close'].iloc[i]),
                    'entry_time':  str(df.index[i]),
                    'status':      status,
                    'pnl_pct':     round(pnl, 6),
                    'conf':        round(conf, 4),
                    'features':    features,
                    'label':       1 if status == 'TAKE_PROFIT' else 0,
                }
                strategy_trades.append(trade)
                all_trades.append(trade)
                i += 24

        wins  = sum(1 for t in strategy_trades if t['label'] == 1)
        total = len(strategy_trades)
        if total > 0:
            log.info(f"  → {total} trades, win rate: {wins/total*100:.1f}%")
        else:
            log.info(f"  → 0 trades generated")

    os.makedirs('data', exist_ok=True)
    with open('data/backtest_trades.json', 'w') as f:
        json.dump(all_trades, f, indent=2)

    total = len(all_trades)
    wins  = sum(1 for t in all_trades if t['label'] == 1)
    log.info(f"\n=== Backtest complete ===")
    log.info(f"Total trades: {total}")
    if total > 0:
        log.info(f"Win rate: {wins/total*100:.1f}%  ({wins}W/{total-wins}L)")
        by_strat = {}
        for t in all_trades:
            s = t['strategy']
            by_strat.setdefault(s, {'total':0,'wins':0})
            by_strat[s]['total'] += 1
            by_strat[s]['wins']  += t['label']
        for s, v in by_strat.items():
            wr = v['wins']/v['total']*100 if v['total'] else 0
            log.info(f"  {s}: {v['total']} trades ({v['wins']}W, {wr:.1f}%)")
        by_symbol = {}
        for t in all_trades:
            by_symbol[t['symbol']] = by_symbol.get(t['symbol'], 0) + 1
        for sym, cnt in sorted(by_symbol.items()):
            sym_wins = sum(1 for t in all_trades if t['symbol']==sym and t['label']==1)
            log.info(f"  {sym}: {cnt} trades ({sym_wins}W)")

    if total >= 50:
        log.info("Training per-strategy ML models from backtest...")
        try:
            from meta_learner import train_from_backtest as train_fn
            results = train_fn('data/backtest_trades.json')
            log.info(f"Training results: {results}")
            from notifier import send
            summary = " | ".join(
                f"{s}:{v['trades']}t {v['win_rate']}%"
                for s,v in (results or {}).items()
            )
            send(f"🧠 Per-strategy ML models trained!\n{summary}")
        except Exception as e:
            log.error(f"ML training failed: {e}", exc_info=True)

    return all_trades

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
    run_backtest()
