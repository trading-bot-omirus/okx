# AI Instructions — Trading Bot OKX

This file tells a new AI assistant everything it needs to know to continue working on this project. Read this FIRST before doing anything.
Να μιλάς πάντα ελληνικά
Να μην κάνεις καμία αλλαγή πριν ρωτήσεις πρώτα
Να επαληθεύει την αλλαγή πριν προχωρήσεις σε αλλαγή στον κώδικα
Να σκέφτεσαι σαν επαγγελματίας training ώστε να βρίσκεις την καλύτερη λύση

## Κανόνας ενημέρωσης Claude
1. Κάθε φορά που κάνουμε οποιαδήποτε αλλαγή, ΠΡΩΤΑ γράφω/ενημερώνω το README_AI.md
2. Μετά κάνω commit και push στο GitHub
3. Το raw URL https://raw.githubusercontent.com/trading-bot-omirus/okx/main/README_AI.md ενημερώνεται αυτόματα
4. Ο χρήστης δίνει αυτό το URL στο Claude.ai για να διαβάζει την τελευταία κατάσταση
5. Ποτέ δεν προχωράω σε αλλαγή χωρίς πρώτα να έχω κάνει update το README_AI.md 

---

## Project identity

- **Project**: Crypto Futures Trading Bot for OKX
- **Code location**: `/Users/macbook/Documents/Trading_bot_OKX/trading_bot/`
- **This file**: `/Users/macbook/Documents/Trading_bot_OKX/README_AI.md`
- **Language**: Python 3 + Flask
- **Deployment**: Railway.app (live at `https://web-production-44945.up.railway.app`)
- **GitHub**: `trading-bot-omirus/okx` (main branch, auto-deploy to Railway)
- **Status**: LIVE in Paper Trading mode on OKX Testnet

---

## Files in trading_bot/

| File | Purpose |
|---|---|
| `main.py` | Bot trading loop: `process_symbol()`, `cycle()`, risk checks |
| `api.py` | Flask server: all REST endpoints + dashboard HTML |
| `executor.py` | Opens/closes positions, calculates balance from DB trades |
| `database.py` | SQLite CRUD for `trades`, `signals`, `bot_config` tables |
| `data_feed.py` | CCXT client for OKX (testnet via sandbox, has `load_markets` fix) |
| `dashboard/index.html` | Full single-page dashboard UI |
| `AI_INSTRUCTIONS.md` | Full deployment guide (by the user, may be outdated) |
| `strategies/` | 4 strategy modules |
| `data/` | Runtime SQLite DB (persisted on Railway via volume mount) |
| `logs/` | Log files |
| `models/` | ML models (if any) |

---

## What has been done so far (chronological)

### Phase 1: Setup & Deployment
1. Git repo initialized, first commit pushed to GitHub
2. Railway web service created and deployed
3. Worker service DELETED (it caused duplicate bot loops)
4. Railway Volume mounted at `/app/data` for SQLite persistence
5. Environment variables set on Railway: `OKX_API_KEY`, `OKX_API_SECRET`, `OKX_PASSPHRASE`, `DASHBOARD_API_KEY`

### Phase 2: Bug Fixes
6. **data_feed.py**: `load_markets()` would crash because OKX testnet returns `base: null` for some markets. Fixed by wrapping in try/except; on failure, clears `ex.markets` dict.
7. **main.py**: Removed broken `LOG_LEVEL` import (module didn't exist). Added `exc_info=True` to logging. Added `mkdirs()` for logs/data/models at startup.
8. **executor.py**: Completely rewritten. Previously read leverage/margin/paper from a config constant. Now reads these from the `bot_config` table in SQLite in real time, so manual buy respects user-chosen leverage.

### Phase 3: Dashboard
9. Redesigned Open Positions table: Symbol, Side, Entry Price, Position Value in $, PnL%, Strategy, Leverage, Close button
10. Flash animation on cells when values change (CSS class toggling)
11. Live refresh every 5 seconds (positions) / 15 seconds (full data)
12. Manual buy form: user enters Symbol, USDT amount, Leverage (2-10x), qty auto-calculated as `usd * lev / entry_price`
13. Manual close: ✕ button triggers API call to close position
14. `/api/balance/reset` endpoint: deletes all trades, resets paper balance

### Phase 4: Telegram
15. Bot `@Omirus_bot` created on Telegram
16. Token + Chat ID saved in dashboard Settings
17. Test alert sent and confirmed received

### Phase 5: Cleanup
18. Deleted `trading_bot_BALANCE` folder (old copy of code)
19. Created this `README_AI.md`

### Phase 6: Bug Fixes — Automated Trading (Claude analysis)
20. **agreement logic fix** (`main.py`): Πριν χρησιμοποιούσε `abs(mean(signals))` — λάθος. Π.χ. 3 LONG + 1 SHORT = mean 0.5 → agreement 50% → SKIP. Τώρα μετράει longs vs shorts: 3 LONG + 1 SHORT = 75% agreement. Διορθώθηκε.
21. **Live config reads** (`main.py`, `config.py`): Πριν τα `MIN_AGREEMENT`, `MIN_ML_CONFIDENCE`, `TIMEFRAME` ήταν frozen imports που διαβάζονταν ΜΙΑ φορά στο startup. Τώρα κάθε `process_symbol()` διαβάζει live το config από τη DB.
22. **Thresholds lowered** (`config.py`): `MIN_AGREEMENT` από 60% → 50%, `MIN_ML_CONFIDENCE` από 62% → 50%.

### Phase 7: Executor Fixes (Claude analysis)
23. **Bug fix — balance calc leverage** (`executor.py:35`): `_calc_balance()` χρησιμοποιούσε `_lev()` (τρέχον leverage από settings) αντί για το leverage του κάθε trade. Αν άλλαζες leverage στο dashboard, το balance υπολογιζόταν λάθος. Διορθώθηκε σε `t.get('leverage', _lev())`.
24. **Bug fix — safe init** (`executor.py:90`): `EX = Executor()` έτρεχε `_calc_balance()` στο import. Αν η DB δεν ήταν έτοιμη, κρασάρε. Τώρα wrapped σε try/except με fallback balance $1,000.

### Phase 8: Meta-Learner Fix (Claude analysis)
25. **Bug fix — meta_learner agreement** (`meta_learner.py`): Το `_rule_based()` fallback είχε ακόμα την παλιά `abs(mean())` λογική. Επίσης το `build_features()` είχε το ίδιο. Και τα δύο διορθώθηκαν σε longs/shorts count. Επίσης τα thresholds διαβάζονται live από DB (όχι frozen imports).

### Phase 9: Data Feed Fix — The Real Culprit (Claude analysis)
26. **Singleton exchange** (`data_feed.py`): `get_exchange()` δημιουργούσε νέο CCXT object σε κάθε κλήση → `load_markets()` δεκάδες φορές ανά cycle. Τώρα cached (global `_exchange`), `load_markets()` τρέχει μόνο μία φορά.
27. **Filter null-base markets** (`data_feed.py`): Το OKX testnet επιστρέφει markets με `base: null`. Πριν ο κώδικας έκανε `ex.markets = {}` (κενό) → `fetch_ohlcv` αποτύγχανε με BadSymbol. Τώρα φιλτράρει: `{k:v for k,v in markets.items() if v.get('base')}`.
28. **Safe fetch_ohlcv** (`data_feed.py`): `fetch_ohlcv()` δεν είχε try/except — αν απέτυχε, το exception σιωπούσε στο process_symbol. Τώρα έχει try/except και επιστρέφει `None`.

### Phase 10: Duplicate Symbol Fix
29. **Skip duplicate open position** (`main.py`): Πριν το bot άνοιγε πολλαπλές θέσεις στο ίδιο symbol (π.χ. 2 φορές ATOM/LONG). Τώρα ελέγχει αν υπάρχει ήδη ανοιχτή θέση στο ίδιο symbol πριν ανοίξει νέα.

### Phase 10: Dashboard Redesign
30. **Dashboard cleanup** (`index.html`, `api.py`): Αφαιρέθηκαν Open Positions, Total PnL, Best Trade, Worst Trade. Προστέθηκαν Balance in Trades (margin σε θέσεις) και Total Balance (ελεύθερο + δεσμευμένο). Νέα grid-3 διάταξη.

### Phase 11: Risk Management Overhaul (2026-05-25)

**Αιτία**: 12 κλειστά trades → win rate 16.7%, net -$142.40. Το momentum (0W/4L, -$47) δεν κέρδισε ποτέ. Το mean_rev (0W/2L, -$187) κατέστρεψε λόγω gapping SL (HBAR -62%, BNB -43%). Μόνο arb ήταν profitable (2W/2L, +$102).

**Αλλαγές**:

| # | Αρχείο | Τι άλλαξε |
|---|--------|-----------|
| 31 | `config.py` | Πρόσθεσε: HARD_STOP_LOSS_PCT (8%), MIN_SIGNAL_CONFIDENCE (70%), TRAILING_STOP (2.5%), STRATEGY_*_ENABLED flags, DEFAULT_LEVERAGE (2x), STOP_LOSS_CHECK_INTERVAL (60s), FULL_CYCLE_INTERVAL (300s) |
| 32 | `database.py` | Πρόσθεσε `peak_price REAL` column στο trades table (για trailing stop). Νέα function `update_trade_peak()`. Νέα statuses: HARD_STOP, TRAILING_STOP. |
| 33 | `risk_manager.py` | Πρόσθεσε `check_hard_stop()` (κλείνει αν leveraged loss > 8%), `check_trailing_stop()` (2.5% από peak), `can_open_position()`. Η `should_close()` ελέγχει hard stop και trailing stop ΠΡΙΝ το fixed SL/TP. |
| 34 | `main.py` | Bottleneck split: **(α)** `check_all_stop_losses()` κάθε 60 δευτ. — ελέγχει hard/trailing/fixed stops + ενημερώνει peak_price **(β)** `process_symbol()` κάθε 300 δευτ. — full signal scan. Strategy enable/disable filters & min confidence check. |
| 35 | `api.py` | Πρόσθεσε όλα τα νέα settings στο `allowed` list του `/api/settings`. |
| 36 | `dashboard/index.html` | Νέα UI: Hard Stop Loss slider, Min Signal Confidence slider, Trailing Stop toggle + %, Strategy toggles (momentum, mr, arb), SL check interval slider, Full cycle interval slider. |
| 37 | `notifier.py` | Χρησιμοποιείται με τα νέα statuses HARD_STOP 🚨, TRAILING_STOP 🔔 στα Telegram alerts. |

**Περιγραφή νέου loop**:
```
κάθε 60 δευτ. → check_all_stop_losses()
  ├─ check_hard_stop(trade, price) → HARD_STOP 🚨
  ├─ check_trailing_stop(trade, price) → TRAILING_STOP 🔔
  ├─ fixed SL check → STOP_LOSS 🛑
  ├─ fixed TP check → TAKE_PROFIT ✅
  └─ update peak_price στη DB (για trailing)
κάθε 300 δευτ. → full cycle
  ├─ BTC data refresh
  ├─ scan όλων των symbols (μόνο enabled strategies)
  └─ maybe_retrain()
```

**Απενεργοποιημένες στρατηγικές**: Momentum (0W/4L), Mean Reversion (0W/2L, gapping).
**Ενεργή**: Arbitrage (2W/2L, +$102 net).
**Default Leverage**: 2x (πριν: 4x).

### Phase 12: ML Backtest Bootstrap (2026-05-25)

**Αιτία**: Το `train_from_db()` χρειάζεται 100+ trades από live data. Με ~12 trades/μήνα θα περιμέναμε 8 μήνες. Λύση: φτιάξαμε backtest engine που τρέχει σε 5-10 λεπτά και παράγει 500+ εικονικά trades από historical data OKX.

**Αλλαγές**:

| # | Αρχείο | Τι άλλαξε |
|---|--------|-----------|
| 37 | `backtest.py` | **Νέο αρχείο**. Signal generation με RSI + Bollinger Bands (backtestable από OHLCV). `fetch_history()` με `ccxt.okx()` χωρίς sandbox, 180 ημέρες 5m data. `simulate_trade()` με SL 1.5% / TP 2.5%. Αποθηκεύει σε `data/backtest_trades.json`. |
| 38 | `meta_learner.py` | Πρόσθεσε `train_from_backtest()`. Φορτώνει backtest trades, χτίζει features (όπως `build_features()`), εκπαιδεύει XGBoost, αποθηκεύει στο `models/meta_learner.pkl`. |
| 39 | `api.py` | Πρόσθεσε `POST /api/backtest/run` (background thread) και `GET /api/backtest/status` (με diagnostics ανά symbol). |

**Backtest flow**:
```
POST /api/backtest/run
  → background thread
    → fetch_history() for 6 symbols (180 days 5m data)
    → for each candle (skip every 24 = ~2h):
        → generate_signal() = RSI(<32 oversold / >68 overbought) + BB(lower/upper band)
        → if conf >= 0.68: simulate_trade() with SL 1.5% / TP 2.5% / max 144 candles
        → save market context + outcome (0=loss, 1=neutral, 2=win)
    → if ≥50 trades: train XGBoost → save to models/meta_learner.pkl
```

**Σύνολο**: Αντί να περιμένουμε 6-8 μήνες live trades, έχουμε εκπαιδευμένο ML σε 5-10 λεπτά.

**Σημαντικό**: Το backtest χρησιμοποιεί live OKX exchange (όχι testnet) για public OHLCV data — δεν χρειάζονται API keys για fetch ιστορικών δεδομένων.

---

## Current state

- **Mode**: Paper Trading (simulation). Virtual balance: starts at $1,000.
- **Exchange**: OKX Testnet (sandbox mode in CCXT)
- **Bot loop**: Two-level split: stop loss check every 60s, full signal scan every 300s. Runs as subprocess from Flask.
- **Balance logic**: Sum of all trades' PnL + margin of open positions. NOT a hardcoded number. Each trade records its own leverage.
- **Leverage**: Default 2x (configurable 1-10x). Saved per trade in DB.
- **Timeframe**: 15 minutes (configurable in Settings)
- **Stop loss**: Fixed (1.5% from entry) + Hard stop (8% leveraged max) + Trailing stop (2.5% from peak)
- **Active strategy**: Arbitrage only. Momentum and Mean Reversion disabled (poor performance)

---

## How to continue working

1. Read this file first.
2. Read `AI_INSTRUCTIONS.md` inside `trading_bot/` for any deployment-specific steps the user documented.
3. Ask the user: "Do you want to continue from where we left off?"
4. Wait for their answer. Do NOT take any action without confirmation.
5. If the user says yes, ask what they want to do next, or check the Dashboard for what's broken/missing.

---

## Key secrets (do NOT commit)

- `DASHBOARD_API_KEY`: `6970018123`
- Telegram bot token: `8606852155:AAH6Tulj7cTfjYdexi_91j25s7iFsV1Kwrg`
- Telegram chat ID: `1866635586`
- OKX API credentials are in Railway env vars, not in local files

---

## Common pitfalls

- The SQLite DB is at `/app/data/trading_bot.db` on Railway. Local development uses `data/trading_bot.db`.
- After changing Settings (leverage, strategy, etc.), user must click **Save** then **Restart Bot** for changes to take effect.
- Paper balance is NOT a fixed number in code. It is calculated from trades. To reset, use `/api/balance/reset`.
- `load_markets()` bug: OKX testnet returns `base: null` for SWAP markets. The fix clears `ex.markets` and retries. If adding new exchange features, be aware of this.
- **Stop loss split**: Το bot τώρα έχει 3 επίπεδα stop loss: (1) Hard stop στο 8% leveraged max loss (προστασία από gap), (2) Trailing stop στο 2.5% από peak, (3) Fixed SL στο 1.5% από entry.
- **Loop timing**: Το bot ελέγχει stop losses κάθε 60 δευτ. αλλά κάνει full scan κάθε 300 δευτ. Αν θες συχνότερο scan, μείωσε το full_cycle_interval.
- **Disabled strategies**: Momentum και Mean Reversion είναι απενεργοποιημένες από default. Μόνο το Arbitrage είναι ενεργό. Μπορείς να τις ενεργοποιήσεις από Settings → Strategies.
- **Trailing stop**: Αποθηκεύει peak_price στη DB κάθε 60 δευτ. Αν η τιμή γυρίσει 2.5% από το υψηλότερο σημείο, κλείνει η θέση με status TRAILING_STOP.

---

## Phase 13 — Per‑strategy ML models

Each strategy now has its own ML model trained from historical backtest:

| Model | Backtest source | Purpose |
|---|---|---|
| `models/ml_momentum.pkl` | EMA crossover + volume | Filters momentum trades |
| `models/ml_mean_rev.pkl` | Z-score + RSI | Filters mean reversion trades |
| `models/ml_arb.pkl` | VWAP spread + imbalance | Filters arbitrage trades |

**How it works:**
1. `backtest.py` runs 3 independent backtests (one per strategy), generating trades with `strategy` + `features` + `label` fields
2. `meta_learner.train_from_backtest()` trains a separate `GradientBoostingClassifier` per strategy
3. `meta_learner.predict_for_strategy(name, features)` returns `(signal, confidence)` per strategy
4. Integration into live loop: each strategy's raw signal is filtered by its ML model before combining

**Key differences from old (Phase 12) single-model approach:**
- Old: single XGBoost model `meta_learner.pkl` tried to learn all 4 strategies at once
- New: each strategy has its own `GradientBoostingClassifier` specializing in that strategy's win/loss patterns
- Old: ML signal was always 0.30 neutral (no real predictions)
- New: each strategy can be independently approved/rejected by its ML model

**Backtest signals:**
- **Momentum**: EMA10/30/50 crossover + volume spike >1.3x
- **Mean reversion**: Z-score ±2.0 + RSI <35/>65
- **Arbitrage**: Price vs VWAP spread >0.3% + volume imbalance >0.3

**API changes:**
- `/api/backtest/status` now returns `by_strategy` breakdown and `models_trained` count
- `models/training_summary.json` stores per-strategy results

**Usage:**
- `POST /api/backtest/run?api_key=...` triggers backtest + per-strategy training
- `GET /api/backtest/status?api_key=...` shows strategy breakdown
- `ml_strategy.compute()` still loads combined model; per-strategy models used live via `predict_for_strategy()`

**File changes:**
- `backtest.py`: Complete rewrite — 3 signal functions, strategy loop, `compute_features()`
- `meta_learner.py`: Added `train_from_backtest()`, `predict_for_strategy()`, `FEATURE_KEYS`
- `api.py`: `by_strategy` in status endpoint, `models_trained` count
