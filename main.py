"""
Main loop — τρέχει το trading bot
"""
import time, logging, os, sys
from datetime import datetime

from config import (TIMEFRAME, MIN_AGREEMENT, MIN_ML_CONFIDENCE,
                    RETRAIN_EVERY_HOURS, LOG_FILE, LOG_LEVEL)
from database import (init_db, get_symbols, get_open_trades,
                      save_signal, get_config, set_config)
from data_feed import fetch_ohlcv, get_mark_price, fetch_balance
from strategies import momentum, mean_reversion, ml_strategy, arbitrage
from meta_learner import META
from risk_manager import RISK
from executor import EX
from notifier import send

# ── Logging ───────────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("main")

INTERVAL   = {"1m":60,"3m":180,"5m":300,"15m":900,"1h":3600}.get(TIMEFRAME, 900)
last_train = 0.0

def get_market_context(df):
    c  = df['close']
    h  = df['high']
    l  = df['low']
    v  = df['volume']
    delta = c.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rsi   = float((100 - 100/(1+(gain/(loss+1e-10)))).iloc[-1])
    import pandas as pd
    tr = pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1])
    atr_pct = atr / float(c.iloc[-1])
    vol_ratio = float(v.iloc[-1] / v.rolling(20).mean().iloc[-1])
    dm_p = h.diff().clip(lower=0)
    dm_n = (-l.diff().clip(upper=0))
    atr14= tr.rolling(14).mean()
    di_p = float((dm_p.rolling(14).mean()/(atr14+1e-10)*100).iloc[-1])
    di_n = float((dm_n.rolling(14).mean()/(atr14+1e-10)*100).iloc[-1])
    adx  = abs(di_p-di_n)/(di_p+di_n+1e-10)*100
    return {
        'atr_pct':   atr_pct,
        'vol_ratio': vol_ratio,
        'rsi':       rsi,
        'adx':       adx,
        'hour':      datetime.utcnow().hour,
        'dow':       datetime.utcnow().weekday(),
    }

def process_symbol(symbol: str, df_btc=None):
    try:
        df = fetch_ohlcv(symbol)
        if len(df) < 60:
            return

        # Signals από 4 strategies
        mom_s, mom_c  = momentum.compute(df)
        mr_s,  mr_c   = mean_reversion.compute(df)
        ml_s,  ml_c   = ml_strategy.compute(df)
        arb_s, arb_c  = arbitrage.compute(df, df_btc)

        signals = {
            'momentum':  (mom_s, mom_c),
            'mean_rev':  (mr_s,  mr_c),
            'ml':        (ml_s,  ml_c),
            'arb':       (arb_s, arb_c),
        }
        ctx = get_market_context(df)

        # Meta-learner decision
        final_signal, confidence = META.predict(signals, ctx)

        # Filters
        import numpy as np
        raw_vals  = [mom_s, mr_s, ml_s, arb_s]
        agreement = abs(np.mean([x for x in raw_vals if x != 0]) if any(x!=0 for x in raw_vals) else 0)

        if agreement < MIN_AGREEMENT:
            log.debug(f"{symbol}: low agreement {agreement:.2f} — skip")
            return
        if ml_c > 0 and ml_c < MIN_ML_CONFIDENCE:
            log.debug(f"{symbol}: low ml_conf {ml_c:.2f} — skip")
            return
        if ctx['vol_ratio'] < 0.3:
            log.debug(f"{symbol}: low volume — skip")
            return

        save_signal(symbol, mom_s, mr_s, ml_s, arb_s, agreement, final_signal,
                    "trending" if ctx['adx'] > 25 else "ranging")

        if final_signal == 0:
            return

        # Risk check
        try:
            balance_info = fetch_balance()
            balance = float(balance_info.get('USDT',{}).get('free', EX.paper_balance))
        except:
            balance = EX.paper_balance

        ok, reason = RISK.check_global_limits(balance, datetime.utcnow().strftime("%Y-%m-%d"))
        if not ok:
            log.warning(f"Risk limit: {reason}")
            return

        entry = get_mark_price(symbol)
        qty   = RISK.calc_position_size(balance, entry, confidence)
        sl, tp = RISK.calc_sl_tp(entry, final_signal)

        sig_dict = {
            'mom_signal': mom_s, 'mom_conf': mom_c,
            'mr_signal':  mr_s,  'mr_conf':  mr_c,
            'ml_signal':  ml_s,  'ml_conf':  ml_c,
            'arb_signal': arb_s, 'arb_conf': arb_c,
            'agreement':  agreement,
        }

        strategy_name = max(
            [('momentum',mom_c),('mean_rev',mr_c),('ml',ml_c),('arb',arb_c)],
            key=lambda x: x[1]
        )[0]

        trade_id = EX.open_position(symbol, final_signal, qty, entry, sl, tp,
                                    strategy_name, sig_dict)
        if trade_id:
            side_str = "LONG 📈" if final_signal==1 else "SHORT 📉"
            send(f"{side_str} {symbol}\nEntry: {entry}\nSL: {sl} | TP: {tp}\nQty: {qty}\nConf: {confidence:.0%}")

    except Exception as e:
        log.error(f"process_symbol {symbol}: {e}")

def manage_open_trades():
    for trade in get_open_trades():
        try:
            symbol = trade['symbol']
            price  = get_mark_price(symbol)
            should_close, reason = RISK.should_close(trade, price)
            if should_close:
                pnl_pct, pnl_usdt = RISK.calc_pnl(trade, price)
                RISK.daily_pnl   += pnl_usdt
                EX.close_position(trade, price, reason, pnl_pct, pnl_usdt)
                emoji = "✅" if pnl_usdt > 0 else "❌"
                send(f"{emoji} {trade['side']} {symbol} closed [{reason}]\nPnL: {pnl_usdt:+.2f} USDT ({pnl_pct*100:+.2f}%)")
        except Exception as e:
            log.error(f"manage_open_trades {trade}: {e}")

def maybe_retrain():
    global last_train
    now = time.time()
    if now - last_train > RETRAIN_EVERY_HOURS * 3600:
        log.info("Starting meta-learner retraining...")
        result = META.train_from_db()
        if result:
            send("🧠 Meta-learner retrained successfully!")
        last_train = now

def main():
    log.info("=" * 50)
    log.info("  Trading Bot starting...")
    log.info("=" * 50)
    init_db()
    set_config('running', '1')
    send("🚀 Bot started!")

    df_btc = None
    btc_refresh = 0

    while True:
        if get_config('running') == '0':
            log.info("Bot stopped via dashboard.")
            break

        symbols = get_symbols()
        log.info(f"Scanning {len(symbols)} symbols: {symbols}")

        # Refresh BTC data για arbitrage
        if time.time() - btc_refresh > INTERVAL:
            try:
                df_btc = fetch_ohlcv("BTC/USDT")
                btc_refresh = time.time()
            except: pass

        manage_open_trades()

        for symbol in symbols:
            process_symbol(symbol, df_btc if symbol != "BTC/USDT" else None)
            time.sleep(1)

        maybe_retrain()

        log.info(f"Cycle done. Sleeping {INTERVAL}s...")
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
