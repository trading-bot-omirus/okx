"""
Αντλεί OHLCV δεδομένα από OKX Futures μέσω CCXT
OKX perpetual swaps: BTC/USDT → BTC/USDT:USDT (ccxt format)
"""
import ccxt, pandas as pd, logging
from config import OKX_API_KEY, OKX_API_SECRET, OKX_PASSPHRASE, TESTNET, TIMEFRAME, LOOKBACK_BARS

log = logging.getLogger(__name__)

def _to_okx_symbol(symbol: str) -> str:
    """BTC/USDT → BTC/USDT:USDT  (OKX perpetual swap format)"""
    if ':' not in symbol:
        base, quote = symbol.split('/')
        return f"{base}/{quote}:{quote}"
    return symbol

def get_exchange():
    ex = ccxt.okx({
        'apiKey':     OKX_API_KEY,
        'secret':     OKX_API_SECRET,
        'password':   OKX_PASSPHRASE,   # OKX passphrase
        'options': {
            'defaultType': 'swap',       # perpetual futures
        },
        'enableRateLimit': True,
    })
    if TESTNET:
        ex.set_sandbox_mode(True)
    return ex

def fetch_ohlcv(symbol: str, timeframe=TIMEFRAME, limit=LOOKBACK_BARS) -> pd.DataFrame:
    ex  = get_exchange()
    sym = _to_okx_symbol(symbol)
    try:
        ex.load_markets()
    except TypeError:
        log.warning("load_markets() failed — some OKX testnet markets have null base")
        ex.markets = {}
    raw = ex.fetch_ohlcv(sym, timeframe, limit=limit)
    df  = pd.DataFrame(raw, columns=['timestamp','open','high','low','close','volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df

def fetch_ticker(symbol: str) -> dict:
    return get_exchange().fetch_ticker(_to_okx_symbol(symbol))

def fetch_balance() -> dict:
    """Επιστρέφει USDT balance από OKX"""
    ex      = get_exchange()
    balance = ex.fetch_balance({'type': 'swap'})
    return balance

def get_mark_price(symbol: str) -> float:
    ticker = fetch_ticker(symbol)
    return float(ticker['last'])

def load_markets():
    return get_exchange().load_markets()
