"""
Executor — τοποθετεί orders στο OKX Futures (ή paper trade simulation)
OKX perpetual swaps: tdMode=isolated, posSide=long/short
"""
import logging
from database import open_trade, close_trade, get_open_trades, get_all_trades, get_all_settings
from data_feed import get_exchange, get_mark_price, _to_okx_symbol

log = logging.getLogger(__name__)

INITIAL_BALANCE = 1000.0

def _lev():
    return int(get_all_settings().get('leverage', 2))

def _cfg(key, default=None):
    return get_all_settings().get(key, default)

def _margin_type():
    return _cfg('margin_type', 'isolated')

def _is_paper():
    return _cfg('paper_trading', '1') == '1'

class Executor:
    def __init__(self):
        self.paper_balance = self._calc_balance()

    def _calc_balance(self):
        total_pnl = sum(
            (t.get('pnl_usdt') or 0) for t in get_all_trades(9999)
            if t.get('status') != 'OPEN'
        )
        open_margin = sum(
            (t['qty'] * (t.get('entry_price') or 0)) / t.get('leverage', _lev())
            for t in get_open_trades()
        )
        return round(INITIAL_BALANCE + total_pnl - open_margin, 2)

    def open_position(self, symbol, side_int, qty, entry, sl, tp, strategy, signals, leverage=None):
        side_str = "LONG" if side_int == 1 else "SHORT"
        lev = leverage or _lev()
        try:
            if not _is_paper():
                ex     = get_exchange()
                sym    = _to_okx_symbol(symbol)
                ex.set_leverage(lev, sym, params={'mgnMode': _margin_type(), 'posSide': 'net'})
                order_side = "buy" if side_int == 1 else "sell"
                ex.create_market_order(sym, order_side, qty, params={
                    'tdMode': _margin_type(), 'posSide': 'long' if side_int == 1 else 'short',
                })
                log.info(f"[LIVE OKX] Opened {side_str} {symbol} qty={qty}")
            else:
                log.info(f"[PAPER] Opened {side_str} {symbol} qty={qty} @ {entry} lev={lev}x")
                self.paper_balance = self._calc_balance()

            trade_id = open_trade(
                symbol=symbol, side=side_str, entry=entry, qty=qty,
                leverage=lev, sl=sl, tp=tp,
                strategy=strategy, signals=signals, paper=_is_paper()
            )
            return trade_id
        except Exception as e:
            log.error(f"open_position error: {e}")
            return None

    def close_position(self, trade: dict, exit_price: float, reason: str, pnl_pct: float, pnl_usdt: float):
        trade_id = trade['id']
        symbol   = trade['symbol']
        qty      = trade['qty']
        side_str = trade['side']
        try:
            if not _is_paper():
                ex = get_exchange()
                ex.create_market_order(_to_okx_symbol(symbol),
                    "sell" if side_str == "LONG" else "buy", qty, params={
                    'tdMode': _margin_type(), 'posSide': "long" if side_str == "LONG" else "short",
                    'reduceOnly': True,
                })
                log.info(f"[LIVE OKX] Closed {trade_id} {symbol} reason={reason} PnL={pnl_usdt:.2f}")
            else:
                log.info(f"[PAPER] Closed {trade_id} {symbol} reason={reason} PnL={pnl_usdt:.2f}")
                self.paper_balance = self._calc_balance()

            close_trade(trade_id, exit_price, pnl_pct, pnl_usdt,
                        status=reason if reason in ("TAKE_PROFIT","STOP_LOSS") else "CLOSED")
        except Exception as e:
            log.error(f"close_position error: {e}")

try:
    EX = Executor()
except Exception as e:
    log.warning(f"Executor init failed: {e}")
    EX = Executor.__new__(Executor)
    EX.paper_balance = INITIAL_BALANCE
