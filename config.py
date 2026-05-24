"""
⚠️  ΠΡΟΕΙΔΟΠΟΙΗΣΗ: Futures trading με leverage ενέχει ΥΨΗΛΟ κίνδυνο.
    Ξεκίνα ΠΑΝΤΑ με PAPER_TRADING = True και TESTNET = True.
"""
import os

# ── OKX API ───────────────────────────────────────────────────────────────────
OKX_API_KEY        = os.getenv("OKX_API_KEY", "")
OKX_API_SECRET     = os.getenv("OKX_API_SECRET", "")
OKX_PASSPHRASE     = os.getenv("OKX_PASSPHRASE", "")   # ← OKX χρειάζεται passphrase!

# ── Dashboard ─────────────────────────────────────────────────────────────────
API_HOST  = "0.0.0.0"
API_PORT  = 5000
API_KEY   = os.getenv("DASHBOARD_API_KEY", "change_this_secret")

# ── Database / Logs ───────────────────────────────────────────────────────────
DB_PATH   = "data/trades.db"
LOG_FILE  = "logs/bot.log"
LOG_LEVEL = "INFO"

# ── Defaults (override από Dashboard Settings) ────────────────────────────────
DEFAULT_SYMBOLS     = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "OKB/USDT"]
LOOKBACK_BARS       = 500
MODEL_PATH          = "models/meta_learner.pkl"
RETRAIN_EVERY_HOURS = 24

def get_live_config():
    try:
        from database import get_all_settings
        s = get_all_settings()
        return {
            'PAPER_TRADING':      s.get('paper_trading','1') == '1',
            'TESTNET':            s.get('testnet','1') == '1',
            'LEVERAGE':           int(s.get('leverage', 2)),
            'MARGIN_TYPE':        s.get('margin_type', 'isolated'),
            'TIMEFRAME':          s.get('timeframe', '15m'),
            'MAX_RISK_PER_TRADE': float(s.get('max_risk_per_trade', 1.0)) / 100,
            'STOP_LOSS_PCT':      float(s.get('stop_loss_pct', 1.5)) / 100,
            'TAKE_PROFIT_PCT':    float(s.get('take_profit_pct', 3.0)) / 100,
            'MAX_DAILY_LOSS':     float(s.get('max_daily_loss', 3.0)) / 100,
            'MAX_DRAWDOWN':       float(s.get('max_drawdown', 12.0)) / 100,
            'MAX_OPEN_POSITIONS': int(s.get('max_open_positions', 3)),
            'MIN_AGREEMENT':      float(s.get('min_agreement', 50)) / 100,
            'MIN_ML_CONFIDENCE':  float(s.get('min_ml_confidence', 50)) / 100,
            'TELEGRAM_TOKEN':     s.get('telegram_token', os.getenv('TELEGRAM_TOKEN','')),
            'TELEGRAM_CHAT_ID':   s.get('telegram_chat_id', os.getenv('TELEGRAM_CHAT_ID','')),
        }
    except Exception:
        return {
            'PAPER_TRADING': True, 'TESTNET': True,
            'LEVERAGE': 2, 'MARGIN_TYPE': 'isolated', 'TIMEFRAME': '15m',
            'MAX_RISK_PER_TRADE': 0.01, 'STOP_LOSS_PCT': 0.015,
            'TAKE_PROFIT_PCT': 0.030, 'MAX_DAILY_LOSS': 0.03,
            'MAX_DRAWDOWN': 0.12, 'MAX_OPEN_POSITIONS': 3,
            'MIN_AGREEMENT': 0.50, 'MIN_ML_CONFIDENCE': 0.50,
            'TELEGRAM_TOKEN': os.getenv('TELEGRAM_TOKEN',''),
            'TELEGRAM_CHAT_ID': os.getenv('TELEGRAM_CHAT_ID',''),
        }

_cfg = get_live_config()
PAPER_TRADING      = _cfg['PAPER_TRADING']
TESTNET            = _cfg['TESTNET']
LEVERAGE           = _cfg['LEVERAGE']
MARGIN_TYPE        = _cfg['MARGIN_TYPE']
TIMEFRAME          = _cfg['TIMEFRAME']
MAX_RISK_PER_TRADE = _cfg['MAX_RISK_PER_TRADE']
STOP_LOSS_PCT      = _cfg['STOP_LOSS_PCT']
TAKE_PROFIT_PCT    = _cfg['TAKE_PROFIT_PCT']
MAX_DAILY_LOSS     = _cfg['MAX_DAILY_LOSS']
MAX_DRAWDOWN       = _cfg['MAX_DRAWDOWN']
MAX_OPEN_POSITIONS = _cfg['MAX_OPEN_POSITIONS']
MIN_AGREEMENT      = _cfg['MIN_AGREEMENT']
MIN_ML_CONFIDENCE  = _cfg['MIN_ML_CONFIDENCE']
TELEGRAM_TOKEN     = _cfg['TELEGRAM_TOKEN']
TELEGRAM_CHAT_ID   = _cfg['TELEGRAM_CHAT_ID']
