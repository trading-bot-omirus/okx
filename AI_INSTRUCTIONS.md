# AI Assistant Instructions — Trading Bot Deployment

## RULES (follow strictly)
1. Execute ONE step at a time
2. After each step → STOP and ask: "Βήμα X ολοκληρώθηκε. Να συνεχίσω στο Βήμα X+1;"
3. Wait for explicit "ναι" / "yes" / "continue" before proceeding
4. If any step fails → STOP, show the exact error, ask how to proceed
5. NEVER skip steps or combine multiple steps

---

## PROJECT OVERVIEW

This is a crypto trading bot with:
- **Exchange:** OKX Futures (Perpetual Swaps)
- **Language:** Python 3.11
- **Framework:** Flask (web API) + SQLite (database)
- **Hosting:** Railway.app
- **Dashboard:** Web UI at dashboard/index.html

### File responsibilities:
- `api.py` → Web server, starts on Railway, serves dashboard
- `main.py` → Bot trading loop, runs as background worker
- `config.py` → Reads settings from DB or environment variables
- `database.py` → SQLite CRUD for trades, signals, settings
- `data_feed.py` → OKX API connection via CCXT
- `executor.py` → Places/closes orders on OKX
- `risk_manager.py` → Position sizing, SL/TP, drawdown limits
- `meta_learner.py` → XGBoost ensemble of 4 strategies
- `notifier.py` → Telegram alerts
- `strategies/momentum.py` → EMA + RSI + MACD signals
- `strategies/mean_reversion.py` → Bollinger Bands signals
- `strategies/ml_strategy.py` → XGBoost ML signals
- `strategies/arbitrage.py` → BTC correlation signals
- `dashboard/index.html` → Full web dashboard UI
- `Procfile` → Railway start command
- `railway.toml` → Railway build config
- `requirements.txt` → Python dependencies
- `.gitignore` → Excludes .env, logs, DB from git
- `.env.example` → Template for environment variables

---

## DEPLOYMENT TASK

Deploy this trading bot to Railway.app via GitHub.

---

## STEP 1 — Verify project structure

Run this command and show me the output:
```bash
ls -la ~/Downloads/trading_bot/
```

Expected files: api.py, main.py, config.py, database.py, data_feed.py,
executor.py, risk_manager.py, meta_learner.py, notifier.py, requirements.txt,
Procfile, railway.toml, runtime.txt, .gitignore, README.md
and folders: strategies/, dashboard/, logs/, models/, data/

If any file is missing → STOP and tell me which ones.

**→ STOP. Ask before Step 2.**

---

## STEP 2 — Check Git installation

```bash
git --version
```

If git is not installed:
- macOS: run `xcode-select --install`
- Wait for installation to complete
- Verify again with `git --version`

**→ STOP. Ask before Step 3.**

---

## STEP 3 — Initialize Git repository

```bash
cd ~/Downloads/trading_bot
git init
git add .
git status
```

Show me the output of `git status`.
Verify that `.env` is NOT in the list (it should be gitignored).
If `.env` appears → STOP, do not commit, tell me immediately.

**→ STOP. Ask before Step 4.**

---

## STEP 4 — First commit

```bash
cd ~/Downloads/trading_bot
git commit -m "Trading bot initial commit - OKX Futures"
```

Show me the commit output.

**→ STOP. Ask before Step 5.**

---

## STEP 5 — Connect to GitHub

Ask me: "Ποιο είναι το GitHub username και το όνομα του repo;"

Wait for my answer, then run:
```bash
git remote add origin https://github.com/MYGITHUBUSER/MYREPONAME.git
git branch -M main
git push -u origin main
```

Replace MYGITHUBUSER and MYREPONAME with what I tell you.
If push fails with authentication error → tell me to create a GitHub Personal Access Token.

**→ STOP. Ask before Step 6.**

---

## STEP 6 — Verify Railway files exist

Check these files are correct:

**Procfile** should contain:
```
web: python api.py
worker: python main.py
```

**railway.toml** should contain:
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "python api.py"
restartPolicyType = "always"
```

**runtime.txt** should contain:
```
python-3.11.0
```

If any of these are wrong → fix them, commit, and push before continuing.

**→ STOP. Ask before Step 7.**

---

## STEP 7 — Railway deployment

Tell me to do the following manually (you cannot do this for me):

```
1. Go to railway.app
2. Click: New Project
3. Click: Deploy from GitHub repo
4. Select: MYREPONAME
5. Click: Deploy Now
6. Wait for build to complete (2-3 minutes)
7. Tell me when done or show me any errors
```

**→ STOP. Wait for me to confirm Railway deployment is complete.**

---

## STEP 8 — Environment Variables

Tell me to add these variables in Railway:
```
Railway Dashboard → my project → Variables tab → Add Variable
```

Variables needed:
```
OKX_API_KEY          = (ask me for the value)
OKX_API_SECRET       = (ask me for the value)
OKX_PASSPHRASE       = (ask me for the value)
DASHBOARD_API_KEY    = (ask me to choose a password)
```

Ask me for each value ONE AT A TIME.
NEVER suggest default values for API keys.
After I provide each value → confirm it was added.

**→ STOP. Ask before Step 9.**

---

## STEP 9 — Generate Railway domain

Tell me to do manually:
```
Railway Dashboard → my project → Settings → Networking → Generate Domain
```

Ask me: "Ποιο URL έδωσε το Railway;"
Save this URL, it will be the dashboard address.

**→ STOP. Ask before Step 10.**

---

## STEP 10 — Verify deployment

Ask me to open the Railway URL in browser.
The page should show the Trading Bot Dashboard and ask for API Key.

If it shows an error → ask me to share the error message and the Railway logs.

**→ STOP. Ask before Step 11.**

---

## STEP 11 — Dashboard initial setup

Tell me to do in the Dashboard:
```
1. Enter DASHBOARD_API_KEY when prompted
2. Go to Settings tab
3. Verify: Paper Trading toggle = ON
4. Verify: Testnet/Demo toggle = ON
5. Go to Overview tab
6. Click: Start Bot
7. Go to Logs tab → verify bot is running
```

Ask me to confirm each of these 7 items.

**→ STOP. Deployment complete. Show summary.**

---

## FINAL SUMMARY (show after Step 11)

Show this summary:
```
✅ Deployment Complete!

Dashboard URL: [the Railway URL]
Bot status: Paper Trading (simulation mode)
Exchange: OKX Futures
Leverage: x2 (default)

Next steps:
1. Monitor the Dashboard for 2-3 months in Paper Trading
2. Check Trades tab to see bot performance
3. Only switch to Live Trading if results are consistently profitable
4. To change settings: Dashboard → Settings tab → Save

⚠️ DO NOT switch Paper Trading OFF until you have 
   verified the bot is profitable in simulation!
```

---

## ERROR HANDLING

### If Railway build fails:
1. Show me the full build log
2. Check if requirements.txt has all packages
3. Check if Procfile syntax is correct
4. Check Python version in runtime.txt

### If OKX connection fails:
1. Verify API keys are correct in Railway Variables
2. Verify OKX API has Read + Trade permissions
3. Verify Testnet mode is ON in Dashboard Settings
4. Check Logs tab for specific error

### If Dashboard shows blank/error:
1. Check Railway deployment logs
2. Verify PORT environment variable is set (Railway sets it automatically)
3. Check that api.py is running (not main.py as web)

---

## IMPORTANT WARNINGS (remind me if I forget)

- NEVER disable Paper Trading without my explicit request
- NEVER add Withdraw permission to OKX API keys
- NEVER commit .env file to GitHub
- NEVER run main.py as the web service (only api.py)
- ALWAYS ask before each step

