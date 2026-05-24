"""
Αντλεί OHLCV δεδομένα από OKX Futures μέσω CCXT
OKX perpetual swaps: BTC/USDT → BTC/USDT:USDT (ccxt format)
"""
import ccxt, pandas as pd, logging
from config import OKX_API_KEY, OKX_API_SECRET, OKX_PASSPHRASE, TESTNET, TIMEFRAME, LOOKBACK_BARS

log = logging.getLogger(__name__)
_exchange = None

def _to_okx_symbol(symbol: str) -> str:
    """BTC/USDT → BTC/USDT:USDT  (OKX perpetual swap format)"""
    if ':' not in symbol:
        base, quote = symbol.split('/')
        return f"{base}/{quote}:{quote}"
    return symbol

def get_exchange():
    global _exchange
    if _exchange is not None:
        return _exchange
    ex = ccxt.okx({
        'apiKey':     OKX_API_KEY,
        'secret':     OKX_API_SECRET,
        'password':   OKX_PASSPHRASE,
        'options': {
            'defaultType': 'swap',
        },
        'enableRateLimit': True,
    })
    if TESTNET:
        ex.set_sandbox_mode(True)
    try:
        markets = ex.load_markets()
        ex.markets = {k: v for k, v in markets.items() if v.get('base')}
    except Exception as e:
        log.warning(f"load_markets failed: {e} — continuing without validation")
    _exchange = ex
    return _exchange

def fetch_ohlcv(symbol: str, timeframe=TIMEFRAME, limit=LOOKBACK_BARS):
    try:
        ex  = get_exchange()
        sym = _to_okx_symbol(symbol)
        raw = ex.fetch_ohlcv(sym, timeframe, limit=limit)
        if not raw:
            return None
        df  = pd.DataFrame(raw, columns=['timestamp','open','high','low','close','volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df
    except Exception as e:
        log.warning(f"fetch_ohlcv {symbol}: {e}")
        return None

def fetch_ticker(symbol: str) -> dict:
    return get_exchange().fetch_ticker(_to_okx_symbol(symbol))

def fetch_balance() -> dict:
    ex      = get_exchange()
    balance = ex.fetch_balance({'type': 'swap'})
    return balance

def get_mark_price(symbol: str) -> float:
    ticker = fetch_ticker(symbol)
    return float(ticker['last'])

def load_markets():
    return get_exchange().load_markets()
