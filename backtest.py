"""
Backtest Engine — παράγει historical trades από OKX public OHLCV για ML training
"""
import ccxt, pandas as pd, numpy as np
import json, os, logging, time, traceback
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

SYMBOLS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT',
    'BNB/USDT', 'ADA/USDT', 'ATOM/USDT',
]
TIMEFRAME  = '5m'
DAYS_BACK  = 180
LEVERAGE   = 2

# ── Signal generation (RSI + Bollinger Bands, backtestable from OHLCV) ─────────

def generate_signal(df, i):
    """RSI + Bollinger Bands — δουλεύει αποκλειστικά από OHLCV history."""
    if i < 50:
        return 0, 0.0

    close = df['close']

    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rsi_val = loss.iloc[i]
    if rsi_val == 0:
        return 0, 0.0
    rsi = 100 - 100 / (1 + gain.iloc[i] / rsi_val)

    window = close.iloc[i-20:i+1]
    sma = window.mean()
    std = window.std()
    lower_band = sma - 2 * std
    upper_band = sma + 2 * std
    price = close.iloc[i]

    ema20 = close.iloc[i-20:i+1].ewm(span=20).mean().iloc[-1]
    ema50 = close.iloc[i-50:i+1].ewm(span=50).mean().iloc[-1]

    if rsi < 32 and price <= lower_band * 1.005:
        conf = min(0.92, 0.65 + (32 - rsi) / 100)
        return 1, round(conf, 3)

    if rsi > 68 and price >= upper_band * 0.995:
        conf = min(0.92, 0.65 + (rsi - 68) / 100)
        return -1, round(conf, 3)

    return 0, 0.0

# ── Data fetching ─────────────────────────────────────────────────────────────

def fetch_history(symbol, days=180):
    """Κατεβάζει OHLCV από real OKX (public, χωρίς API key)."""
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

# ── Market context ────────────────────────────────────────────────────────────

def market_context(df, i):
    c = df['close'].iloc[:i+1]
    h = df['high'].iloc[:i+1]
    l = df['low'].iloc[:i+1]
    v = df['volume'].iloc[:i+1]
    delta = c.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = float((100 - 100/(1+gain/(loss+1e-10))).iloc[-1])
    hi = df['high'].iloc[:i+1]
    lo = df['low'].iloc[:i+1]
    tr = pd.concat([hi-lo, (hi-c.shift()).abs(), (lo-c.shift()).abs()], axis=1).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1]) / float(c.iloc[-1])
    vr  = float(v.iloc[-1] / (v.rolling(20).mean().iloc[-1] + 1e-10))
    dm_p  = hi.diff().clip(lower=0)
    dm_n  = (-lo.diff().clip(upper=0))
    atr14 = tr.rolling(14).mean()
    di_p  = float((dm_p.rolling(14).mean()/(atr14+1e-10)*100).iloc[-1])
    di_n  = float((dm_n.rolling(14).mean()/(atr14+1e-10)*100).iloc[-1])
    adx   = abs(di_p-di_n)/(di_p+di_n+1e-10)*100
    return {
        'atr_pct':   atr,
        'vol_ratio': vr,
        'rsi':       rsi,
        'adx':       adx,
        'hour':      df.index[i].hour,
        'dow':       df.index[i].weekday(),
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
                return 0, (sl - entry) / entry * lev
            if high >= tp:
                return 2, (tp - entry) / entry * lev
        else:
            if high >= sl:
                return 0, (entry - sl) / entry * lev
            if low <= tp:
                return 2, (entry - tp) / entry * lev
    last = float(df['close'].iloc[min(i+max_candles, len(df)-1)])
    raw  = (last - entry) / entry if side_str == 'LONG' else (entry - last) / entry
    return 1, raw * lev

# ── Main backtest ─────────────────────────────────────────────────────────────

def run_backtest():
    all_trades = []

    for symbol in SYMBOLS:
        log.info(f"Fetching {symbol} ({DAYS_BACK}d {TIMEFRAME})...")
        try:
            df = fetch_history(symbol, DAYS_BACK)
            log.info(f"  {len(df)} candles")
        except Exception as e:
            log.warning(f"  SKIP {symbol}: {e}")
            continue

        i = 50
        symbol_trades = 0

        while i < len(df) - 50:
            try:
                signal, conf = generate_signal(df, i)
            except Exception as e:
                log.warning(f"  signal error at {i}: {e}")
                i += 1
                continue

            if signal == 0 or conf < 0.68:
                i += 1
                continue

            trade_side = 'LONG' if signal == 1 else 'SHORT'
            try:
                outcome, pnl = simulate_trade(df, i, trade_side, LEVERAGE,
                                               sl_pct=0.015, tp_pct=0.025,
                                               max_candles=144)
            except Exception as e:
                log.warning(f"  simulate error at {i}: {e}")
                i += 1
                continue

            ctx = market_context(df, i)
            all_trades.append({
                'symbol':     symbol,
                'side':       trade_side,
                'entry_price': float(df['close'].iloc[i]),
                'entry_time': str(df.index[i]),
                'outcome':    outcome,
                'pnl_pct':    round(pnl, 6),
                'conf':       round(conf, 4),
                'arb_signal': signal,
                'arb_conf':   round(conf, 4),
                'agreement':  1.0,
                'ctx':        ctx,
                'mom_signal': 0, 'mom_conf': 0,
                'mr_signal':  0, 'mr_conf': 0,
                'ml_signal':  0, 'ml_conf': 0.3,
            })
            symbol_trades += 1
            i += 24

        log.info(f"  {symbol}: {symbol_trades} trades")

    os.makedirs('data', exist_ok=True)
    with open('data/backtest_trades.json', 'w') as f:
        json.dump(all_trades, f, indent=2)

    total = len(all_trades)
    wins  = sum(1 for t in all_trades if t['outcome'] == 2)
    losses = sum(1 for t in all_trades if t['outcome'] == 0)

    log.info(f"\n=== Backtest complete ===")
    log.info(f"Total trades: {total}")
    if total > 0:
        log.info(f"Win rate: {wins/total*100:.1f}%  ({wins}W/{losses}L)")
        by_symbol = {}
        for t in all_trades:
            by_symbol[t['symbol']] = by_symbol.get(t['symbol'], 0) + 1
        for sym, cnt in sorted(by_symbol.items()):
            sym_wins = sum(1 for t in all_trades if t['symbol']==sym and t['outcome']==2)
            log.info(f"  {sym}: {cnt} trades ({sym_wins}W)")

    if total >= 50:
        log.info("Training ML model from backtest...")
        try:
            from meta_learner import META
            ok = META.train_from_backtest('data/backtest_trades.json')
            if ok:
                from notifier import send
                send(f"🧠 ML model trained from {total} backtest trades! WR: {wins/total*100:.1f}%")
        except Exception as e:
            log.error(f"ML training failed: {e}", exc_info=True)

    return all_trades

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
    run_backtest()
