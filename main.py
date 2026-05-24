"""
Main loop — τρέχει το trading bot
"""
import time, logging, os, sys
from datetime import datetime

from config import (RETRAIN_EVERY_HOURS, LOG_FILE, get_live_config)
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
os.makedirs("data", exist_ok=True)
os.makedirs("models", exist_ok=True)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("main")

def current_interval():
    from config import get_live_config
    tf = get_live_config().get('TIMEFRAME', '15m')
    return {"1m":60,"3m":180,"5m":300,"15m":900,"1h":3600}.get(tf, 900)
last_train = 0.0

def get_market_context(df):
    import pandas as pd
    import numpy as np
    c = df['close']; h = df['high']; l = df['low']; v = df['volume']
    delta = c.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rsi   = float((100 - 100/(1+(gain/(loss+1e-10)))).iloc[-1])
    tr    = pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    atr   = float(tr.rolling(14).mean().iloc[-1])
    atr_pct   = atr / float(c.iloc[-1])
    vol_ratio = float(v.iloc[-1] / (v.rolling(20).mean().iloc[-1] + 1e-10))
    dm_p  = h.diff().clip(lower=0)
    dm_n  = (-l.diff().clip(upper=0))
    atr14 = tr.rolling(14).mean()
    di_p  = float((dm_p.rolling(14).mean()/(atr14+1e-10)*100).iloc[-1])
    di_n  = float((dm_n.rolling(14).mean()/(atr14+1e-10)*100).iloc[-1])
    adx   = abs(di_p-di_n)/(di_p+di_n+1e-10)*100
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
        # Live config κάθε φορά (όχι frozen imports)
        _cfg = get_live_config()
        _min_agreement     = _cfg['MIN_AGREEMENT']
        _min_ml_confidence = _cfg['MIN_ML_CONFIDENCE']

        log.info(f"Fetching data for {symbol}...")
        df = fetch_ohlcv(symbol)
        if df is None or len(df) < 60:
            log.warning(f"{symbol}: not enough data ({len(df) if df is not None else 0} bars)")
            return

        # Signals από 4 strategies
        mom_s, mom_c  = momentum.compute(df)
        mr_s,  mr_c   = mean_reversion.compute(df)
        ml_s,  ml_c   = ml_strategy.compute(df)
        arb_s, arb_c  = arbitrage.compute(df, df_btc)

        log.info(f"{symbol} signals → mom:{mom_s:.0f}({mom_c:.2f}) mr:{mr_s:.0f}({mr_c:.2f}) ml:{ml_s:.0f}({ml_c:.2f}) arb:{arb_s:.0f}({arb_c:.2f})")

        signals = {
            'momentum': (mom_s, mom_c),
            'mean_rev': (mr_s,  mr_c),
            'ml':       (ml_s,  ml_c),
            'arb':      (arb_s, arb_c),
        }
        ctx = get_market_context(df)

        import numpy as np
        final_signal, confidence = META.predict(signals, ctx)

        raw_vals  = [mom_s, mr_s, ml_s, arb_s]
        non_zero  = [x for x in raw_vals if x != 0]
        if non_zero:
            longs  = sum(1 for x in non_zero if x > 0)
            shorts = sum(1 for x in non_zero if x < 0)
            agreement = max(longs, shorts) / len(non_zero)
        else:
            agreement = 0.0

        if agreement < _min_agreement:
            log.info(f"{symbol}: low agreement {agreement:.2f} — skip")
            return
        if ml_c > 0 and ml_c < _min_ml_confidence:
            log.info(f"{symbol}: low ml_conf {ml_c:.2f} — skip")
            return
        if ctx['vol_ratio'] < 0.3:
            log.info(f"{symbol}: low volume ratio {ctx['vol_ratio']:.2f} — skip")
            return

        save_signal(symbol, mom_s, mr_s, ml_s, arb_s, agreement, final_signal,
                    "trending" if ctx['adx'] > 25 else "ranging")

        if final_signal == 0:
            log.info(f"{symbol}: no signal — hold")
            return

        # Risk check
        try:
            balance_info = fetch_balance()
            usdt = balance_info.get('USDT', {})
            balance = float(usdt.get('free', EX.paper_balance))
        except Exception as e:
            log.warning(f"Balance fetch failed: {e} — using paper balance")
            balance = EX.paper_balance

        ok, reason = RISK.check_global_limits(balance, datetime.utcnow().strftime("%Y-%m-%d"))
        if not ok:
            log.warning(f"Risk limit: {reason}")
            return

        entry    = get_mark_price(symbol)
        qty      = RISK.calc_position_size(balance, entry, confidence)
        sl, tp   = RISK.calc_sl_tp(entry, final_signal)

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
            side_str = "LONG 📈" if final_signal == 1 else "SHORT 📉"
            send(f"{side_str} {symbol}\nEntry: {entry}\nSL: {sl} | TP: {tp}\nQty: {qty}\nConf: {confidence:.0%}")

    except Exception as e:
        log.error(f"process_symbol {symbol}: {e}", exc_info=True)

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
                send(f"{emoji} {trade['side']} {symbol} [{reason}]\nPnL: {pnl_usdt:+.2f} USDT ({pnl_pct*100:+.2f}%)")
        except Exception as e:
            log.error(f"manage_open_trades {trade.get('id','?')}: {e}", exc_info=True)

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
    log.info("  Trading Bot starting — OKX Futures")
    log.info("=" * 50)
    init_db()
    set_config('running', '1')
    send("🚀 Bot started! Paper Trading mode.")

    df_btc      = None
    btc_refresh = 0

    while True:
        try:
            if get_config('running') == '0':
                log.info("Bot stopped via dashboard.")
                break

            symbols = get_symbols()
            log.info(f"Scanning {len(symbols)} symbols: {symbols}")

            _interval = current_interval()
            # Refresh BTC data για arbitrage
            if time.time() - btc_refresh > _interval:
                try:
                    df_btc      = fetch_ohlcv("BTC/USDT")
                    btc_refresh = time.time()
                    log.info("BTC/USDT data refreshed for arbitrage")
                except Exception as e:
                    log.warning(f"BTC data refresh failed: {e}")

            manage_open_trades()

            for symbol in symbols:
                process_symbol(symbol, df_btc if symbol != "BTC/USDT" else None)
                time.sleep(2)

            maybe_retrain()

            log.info(f"Cycle done. Sleeping {_interval}s...")
            time.sleep(_interval)

        except Exception as e:
            log.error(f"Main loop error: {e}", exc_info=True)
            time.sleep(30)

if __name__ == "__main__":
    main()
