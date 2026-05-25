"""
Risk Manager — position sizing, daily loss limit, drawdown protection
"""
import logging
from config import (MAX_RISK_PER_TRADE, MAX_OPEN_POSITIONS, MAX_DAILY_LOSS,
                    MAX_DRAWDOWN, STOP_LOSS_PCT, TAKE_PROFIT_PCT, LEVERAGE)
from database import get_open_trades, get_stats

log = logging.getLogger(__name__)

class RiskManager:
    def __init__(self):
        self.peak_balance   = None
        self.daily_pnl      = 0.0
        self.daily_reset_date = None

    def reset_daily(self, today):
        if self.daily_reset_date != today:
            self.daily_pnl       = 0.0
            self.daily_reset_date = today

    def check_global_limits(self, balance: float, today: str) -> tuple[bool, str]:
        self.reset_daily(today)
        if self.peak_balance is None:
            self.peak_balance = balance

        # Update peak
        if balance > self.peak_balance:
            self.peak_balance = balance

        # Drawdown
        drawdown = (self.peak_balance - balance) / (self.peak_balance + 1e-10)
        if drawdown > MAX_DRAWDOWN:
            return False, f"MAX DRAWDOWN {drawdown*100:.1f}% — bot paused"

        # Daily loss
        if self.daily_pnl < -(balance * MAX_DAILY_LOSS):
            return False, f"DAILY LOSS LIMIT reached — bot paused"

        # Max open positions
        open_trades = get_open_trades()
        if len(open_trades) >= MAX_OPEN_POSITIONS:
            return False, f"Max open positions ({MAX_OPEN_POSITIONS}) reached"

        return True, "OK"

    def calc_position_size(self, balance: float, entry: float, signal_confidence: float) -> float:
        """
        Kelly-adjusted position sizing
        1% κεφαλαίου base × confidence × leverage
        """
        risk_amount  = balance * MAX_RISK_PER_TRADE * signal_confidence
        sl_distance  = entry * STOP_LOSS_PCT
        qty_base     = risk_amount / (sl_distance + 1e-10)
        qty_levered  = qty_base * LEVERAGE
        # Cap at 5% of balance in notional
        max_notional = balance * 0.05 * LEVERAGE
        qty_capped   = min(qty_levered, max_notional / (entry + 1e-10))
        return round(qty_capped, 6)

    def calc_sl_tp(self, entry: float, side: int):
        if side == 1:   # LONG
            sl = entry * (1 - STOP_LOSS_PCT)
            tp = entry * (1 + TAKE_PROFIT_PCT)
        else:            # SHORT
            sl = entry * (1 + STOP_LOSS_PCT)
            tp = entry * (1 - TAKE_PROFIT_PCT)
        return round(sl, 8), round(tp, 8)

    def should_close(self, trade: dict, current_price: float) -> tuple[bool, str]:
        side  = 1 if trade['side'] == 'LONG' else -1
        entry = trade['entry_price']
        sl    = trade['stop_loss']
        tp    = trade['take_profit']

        if side == 1:
            if current_price <= sl: return True, "STOP_LOSS"
            if current_price >= tp: return True, "TAKE_PROFIT"
        else:
            if current_price >= sl: return True, "STOP_LOSS"
            if current_price <= tp: return True, "TAKE_PROFIT"
        return False, ""

    def calc_pnl(self, trade: dict, exit_price: float):
        entry = trade['entry_price']
        side  = 1 if trade['side'] == 'LONG' else -1
        qty   = trade['qty']
        lev   = trade['leverage']
        pnl_pct  = side * (exit_price - entry) / entry * lev
        pnl_usdt = qty * entry * pnl_pct
        return round(pnl_pct, 6), round(pnl_usdt, 4)

RISK = RiskManager()
