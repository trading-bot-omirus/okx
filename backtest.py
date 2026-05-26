"""
Backtest Engine — παράγει historical trades από OKX για ML training
"""
import ccxt, pandas as pd, numpy as np
import json, os, logging, time
from datetime import datetime, timedelta
from meta_learner import META

log = logging.getLogger(__name__)

SYMBOLS = [
    'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT',
    'DOGE/USDT', 'ADA/USDT', 'ATOM/USDT', 'XRP/USDT',
]
TIMEFRAME = '15m'
DAYS_BACK = 365
LEVERAGE = 2

def _live_exchange():
    ex = ccxt.okx({
        'enableRateLimit': True,
        'options': {'defaultType': 'swap'},
    })
    ex.load_markets()
    return ex

def _okx_sym(symbol):
    b, q = symbol.split('/')
    return f"{b}/{q}:{q}"

def fetch_history(symbol, days=365):
    ex = _live_exchange()
    sym = _okx_sym(symbol)
    since = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    candles = []
    while True:
        try:
            batch = ex.fetch_ohlcv(sym, TIMEFRAME, since=since, limit=1000)
        except Exception:
            batch = ex.fetch_ohlcv(sym, TIMEFRAME, since=since, limit=100)
        if not batch:
            break
        candles.extend(batch)
        since = batch[-1][0] + 1
        if len(batch) < 1000:
            break
    df = pd.DataFrame(candles, columns=['ts','open','high','low','close','volume'])
    df['ts'] = pd.to_datetime(df['ts'], unit='ms')
    df.set_index('ts', inplace=True)
    return df

def market_context(df, i):
    c = df['close'].iloc[:i+1]
    h = df['high'].iloc[:i+1]
    l = df['low'].iloc[:i+1]
    v = df['volume'].iloc[:i+1]
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = float((100 - 100/(1+gain/(loss+1e-10))).iloc[-1])
    tr = pd.concat([h-l, (h-c.shift()).abs(), (l-c.shift()).abs()], axis=1).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1]) / float(c.iloc[-1])
    vr = float(v.iloc[-1] / (v.rolling(20).mean().iloc[-1] + 1e-10))
    return {'atr_pct': atr, 'vol_ratio': vr, 'rsi': rsi,
            'hour': df.index[i].hour, 'dow': df.index[i].weekday()}

def simulate_trade(df, i, side, lev=2, sl_pct=0.015, tp_pct=0.03, max_candles=72):
    entry = float(df['close'].iloc[i])
    if side == 1:
        sl = entry * (1 - sl_pct)
        tp = entry * (1 + tp_pct)
    else:
        sl = entry * (1 + sl_pct)
        tp = entry * (1 - tp_pct)
    for j in range(1, max_candles):
        idx = i + j
        if idx >= len(df):
            break
        low = float(df['low'].iloc[idx])
        high = float(df['high'].iloc[idx])
        if side == 1:
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
    raw = (last - entry) / entry if side == 1 else (entry - last) / entry
    return 1, raw * lev

def run_backtest():
    from strategies.arbitrage import compute as arb_compute
    log.info(f"Fetching {DAYS_BACK}d BTC/USDT history...")
    btc_df = fetch_history('BTC/USDT', DAYS_BACK)
    log.info(f"BTC: {len(btc_df)} candles")
    btc_ref = pd.Series(btc_df['close'].values, index=btc_df.index,
                         name='btc_close').to_frame()
    all_trades = []
    targets = [s for s in SYMBOLS if s != 'BTC/USDT']
    for symbol in targets:
        log.info(f"Fetching {symbol}...")
        sym_df = fetch_history(symbol, DAYS_BACK)
        log.info(f"  {len(sym_df)} candles")
        aligned = sym_df.join(btc_ref, how='inner')
        if len(aligned) < 200:
            log.warning(f"  {symbol}: not enough aligned data")
            continue
        sym_close = aligned[['open','high','low','close','volume']].copy()
        btc_close = aligned[['btc_close']].rename(columns={'btc_close': 'close'})
        i = 200
        while i < len(sym_close) - 100:
            sym_slice = sym_close.iloc[:i+1]
            btc_slice = btc_close.iloc[:i+1]
            signal, conf = arb_compute(sym_slice, btc_slice)
            if signal == 0 or conf < 0.65:
                i += 3
                continue
            outcome, pnl = simulate_trade(sym_close, i, signal, LEVERAGE)
            ctx = market_context(sym_close, i)
            raw_vals = [signal if signal != 0 else 0, 0, 0, 0]
            non_zero = [x for x in raw_vals if x != 0]
            trade = {
                'symbol': symbol, 'side': 'LONG' if signal == 1 else 'SHORT',
                'entry_price': float(sym_close['close'].iloc[i]),
                'entry_time': str(sym_close.index[i]),
                'outcome': outcome,
                'pnl_pct': round(pnl, 6),
                'conf': round(conf, 4),
                'arb_signal': signal, 'arb_conf': conf,
                'agreement': 1.0 if non_zero else 0.0,
                'ctx': ctx,
                'mom_signal': 0, 'mom_conf': 0,
                'mr_signal': 0, 'mr_conf': 0,
                'ml_signal': 0, 'ml_conf': 0.3,
            }
            all_trades.append(trade)
            i += 12
        log.info(f"  {symbol}: {sum(1 for t in all_trades if t['symbol']==symbol)} trades")
    os.makedirs('data', exist_ok=True)
    with open('data/backtest_trades.json', 'w') as f:
        json.dump(all_trades, f)
    wins = sum(1 for t in all_trades if t['outcome'] == 2)
    losses = sum(1 for t in all_trades if t['outcome'] == 0)
    neutrals = sum(1 for t in all_trades if t['outcome'] == 1)
    total = len(all_trades)
    log.info(f"\nBacktest complete: {total} trades, {wins}W/{losses}L/{neutrals}N ({wins/total*100:.1f}% WR)")
    if total >= 50:
        log.info("Training ML model from backtest...")
        ok = META.train_from_backtest('data/backtest_trades.json')
        if ok:
            from notifier import send
            send(f"🧠 ML model trained from {total} backtest trades! WR: {wins/total*100:.1f}%")
    return all_trades

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_backtest()
