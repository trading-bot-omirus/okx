"""
Telegram alerts για κρίσιμα events
"""
import requests, logging
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

log = logging.getLogger(__name__)

def send(msg: str):
    if not TELEGRAM_TOKEN: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": f"🤖 TradingBot\n{msg}"}, timeout=5)
    except Exception as e:
        log.warning(f"Telegram error: {e}")
