"""
Executor — τοποθετεί orders στο OKX Futures (ή paper trade simulation)
OKX perpetual swaps: tdMode=isolated, posSide=long/short
"""
import logging
from config import PAPER_TRADING, LEVERAGE, MARGIN_TYPE
from database import open_trade, close_trade, get_open_trades, get_all_trades
from data_feed import get_exchange, get_mark_price, _to_okx_symbol

log = logging.getLogger(__name__)

INITIAL_BALANCE = 1000.0

class Executor:
    def __init__(self):
        self.paper_balance = self._calc_balance()

    def _calc_balance(self):
        total_pnl = sum(
            (t.get('pnl_usdt') or 0) for t in get_all_trades(9999)
            if t.get('status') != 'OPEN'
        )
        open_margin = sum(
            (t['qty'] * (t.get('entry_price') or 0)) / LEVERAGE
            for t in get_open_trades()
        )
        return round(INITIAL_BALANCE + total_pnl - open_margin, 2)

    def _set_leverage(self, ex, symbol: str):
        """Ορίζει leverage & margin mode στο OKX"""
        try:
            sym = _to_okx_symbol(symbol)
            # OKX: tdMode = 'isolated' ή 'cross'
            ex.set_leverage(LEVERAGE, sym, params={
                'mgnMode': MARGIN_TYPE,   # 'isolated' ή 'cross'
                'posSide': 'net',
            })
        except Exception as e:
            log.warning(f"set_leverage warning (συχνά ΟΚ): {e}")

    def open_position(self, symbol, side_int, qty, entry, sl, tp, strategy, signals):
        side_str = "LONG" if side_int == 1 else "SHORT"
        try:
            if not PAPER_TRADING:
                ex     = get_exchange()
                sym    = _to_okx_symbol(symbol)
                self._set_leverage(ex, symbol)

                # OKX params για swap
                order_side = "buy" if side_int == 1 else "sell"
                params = {
                    'tdMode':  MARGIN_TYPE,        # isolated / cross
                    'posSide': 'long' if side_int == 1 else 'short',
                }
                ex.create_market_order(sym, order_side, qty, params=params)
                log.info(f"[LIVE OKX] Opened {side_str} {symbol} qty={qty}")
            else:
                log.info(f"[PAPER] Opened {side_str} {symbol} qty={qty} @ {entry}")
                self.paper_balance = self._calc_balance()

            trade_id = open_trade(
                symbol=symbol, side=side_str, entry=entry, qty=qty,
                leverage=LEVERAGE, sl=sl, tp=tp,
                strategy=strategy, signals=signals, paper=PAPER_TRADING
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
            if not PAPER_TRADING:
                ex          = get_exchange()
                sym         = _to_okx_symbol(symbol)
                close_side  = "sell" if side_str == "LONG" else "buy"
                pos_side    = "long" if side_str == "LONG" else "short"
                params = {
                    'tdMode':    MARGIN_TYPE,
                    'posSide':   pos_side,
                    'reduceOnly': True,
                }
                ex.create_market_order(sym, close_side, qty, params=params)
                log.info(f"[LIVE OKX] Closed {trade_id} {symbol} reason={reason} PnL={pnl_usdt:.2f}")
            else:
                entry_price = trade.get('entry_price', 0)
                log.info(f"[PAPER] Closed {trade_id} {symbol} reason={reason} PnL={pnl_usdt:.2f}")
                self.paper_balance = self._calc_balance()

            close_trade(trade_id, exit_price, pnl_pct, pnl_usdt,
                        status=reason if reason in ("TAKE_PROFIT","STOP_LOSS") else "CLOSED")
        except Exception as e:
            log.error(f"close_position error: {e}")

EX = Executor()
