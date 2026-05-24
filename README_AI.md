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

---

## Current state

- **Mode**: Paper Trading (simulation). Virtual balance: starts at $1,000.
- **Exchange**: OKX Testnet (sandbox mode in CCXT)
- **Bot loop**: Runs as a subprocess from the Flask web service. Started/stopped via `/api/bot/start` and `/api/bot/stop`.
- **Balance logic**: Sum of all trades' PnL + margin of open positions. NOT a hardcoded number. Each trade records its own leverage.
- **Leverage**: Configurable per trade (2-10x). Saved in DB, read in real time by `executor.py`.
- **Timeframe**: 5 minutes (configurable in Settings)

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
