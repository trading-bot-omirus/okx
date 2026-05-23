# 🤖 Trading Bot — OKX Futures

## Τι είναι αυτό το project

Είναι ένα **αυτόματο trading bot** για το **OKX exchange** (Futures/Perpetual Swaps).
Τρέχει 24/7 στο **Railway.app** και έχει **web dashboard** για έλεγχο από τον browser.

---

## Τι κάνει το bot

- Παρακολουθεί crypto pairs (BTC, ETH, SOL κτλ) σε real-time
- Χρησιμοποιεί **4 στρατηγικές** ταυτόχρονα:
  - Momentum (EMA + RSI + MACD)
  - Mean Reversion (Bollinger Bands)
  - ML Prediction (XGBoost)
  - Statistical Arbitrage
- Ένα **Meta-Learner** (AI) αποφασίζει πότε να μπει/βγει από trade
- Έχει πλήρες **Risk Management** (Stop Loss, Take Profit, Max Drawdown)
- Στέλνει **Telegram alerts** για κάθε trade
- Ξεκινά σε **Paper Trading** (simulation) — δεν χρησιμοποιεί real χρήματα μέχρι να το ενεργοποιήσεις

---

## Δομή αρχείων

```
trading_bot/
│
├── api.py              ← Web server (Flask) + REST API για το Dashboard
├── main.py             ← Κεντρικός loop του bot (τρέχει κάθε 15 λεπτά)
├── config.py           ← Ρυθμίσεις (διαβάζει από DB ή .env)
├── database.py         ← SQLite: αποθηκεύει trades, signals, ρυθμίσεις
├── data_feed.py        ← Σύνδεση με OKX API - παίρνει τιμές
├── executor.py         ← Εκτελεί orders στο OKX (ή paper simulation)
├── risk_manager.py     ← Position sizing, Stop Loss, Take Profit
├── meta_learner.py     ← AI που συνδυάζει τις 4 στρατηγικές
├── notifier.py         ← Telegram alerts
│
├── strategies/
│   ├── momentum.py     ← Στρατηγική 1: EMA + RSI + MACD
│   ├── mean_reversion.py ← Στρατηγική 2: Bollinger Bands
│   ├── ml_strategy.py  ← Στρατηγική 3: XGBoost ML
│   └── arbitrage.py    ← Στρατηγική 4: Statistical Arbitrage
│
├── dashboard/
│   └── index.html      ← Web Dashboard (UI)
│
├── Procfile            ← Λέει στο Railway πώς να ξεκινήσει το app
├── railway.toml        ← Ρυθμίσεις Railway deployment
├── runtime.txt         ← Python version (3.11)
├── requirements.txt    ← Python packages που χρειάζονται
├── .env.example        ← Template για τα API keys
├── .gitignore          ← Αρχεία που ΔΕΝ ανεβαίνουν στο GitHub
│
├── README.md           ← Αυτό το αρχείο
├── RAILWAY_DEPLOY.md   ← Οδηγίες deployment στο Railway
└── DEPLOY_CLOUDWAYS.md ← Οδηγίες deployment στο Cloudways (εναλλακτικό)
```

---

## Τι χρειάζεται για να τρέξει

### 1. OKX API Keys
- Λογαριασμός στο **okx.com**
- API Key + Secret + Passphrase με permissions: **Read + Trade** (ΟΧΙ Withdraw)

### 2. Railway Account
- Λογαριασμός στο **railway.app**
- Συνδεδεμένο με GitHub

### 3. GitHub repo
- Private repository με τον κώδικα

### 4. (Προαιρετικό) Telegram Bot
- Για alerts σε κάθε trade

---

## Βήματα Deployment στο Railway

> ⚠️ **Σημαντικό:** Κάνε κάθε βήμα με τη σειρά και ρώτα πριν προχωρήσεις στο επόμενο.

### Βήμα 1 — Προετοιμασία GitHub repo
```bash
# Άνοιξε Terminal στον φάκελο trading_bot
cd ~/Downloads/trading_bot

# Αρχικοποίηση git
git init
git add .
git commit -m "Trading bot initial commit"

# Σύνδεση με GitHub repo σου
git remote add origin https://github.com/USERNAME/trading-bot.git
git push -u origin main
```
**→ Ρώτα πριν συνεχίσεις στο Βήμα 2**

---

### Βήμα 2 — Δημιουργία Railway Project
```
1. railway.app → Login
2. New Project → Deploy from GitHub repo
3. Επέλεξε: trading-bot
4. Πάτα: Deploy Now
```
**→ Ρώτα πριν συνεχίσεις στο Βήμα 3**

---

### Βήμα 3 — Environment Variables (API Keys)
```
Railway Dashboard → το project → Variables → Add Variable:

OKX_API_KEY       = (το api key από OKX)
OKX_API_SECRET    = (το api secret από OKX)
OKX_PASSPHRASE    = (το passphrase από OKX)
DASHBOARD_API_KEY = (διάλεξε ένα password για το dashboard)
```
**→ Ρώτα πριν συνεχίσεις στο Βήμα 4**

---

### Βήμα 4 — Domain (URL για το Dashboard)
```
Railway → Settings → Networking → Generate Domain
→ Παίρνεις: https://trading-bot-xxx.railway.app
```
**→ Ρώτα πριν συνεχίσεις στο Βήμα 5**

---

### Βήμα 5 — Πρώτο άνοιγμα Dashboard
```
1. Άνοιξε: https://trading-bot-xxx.railway.app
2. Βάλε το DASHBOARD_API_KEY που όρισες
3. Πήγαινε Settings tab
4. Βεβαιώσου ότι:
   - Paper Trading = ON ✅
   - Testnet/Demo = ON ✅
5. Πάτα Start Bot
```
**→ Ρώτα πριν συνεχίσεις στο Βήμα 6**

---

### Βήμα 6 — Paper Trading (δοκιμαστική περίοδος)
```
Άφησε το bot να τρέχει σε Paper Trading για 2-3 μήνες.
Παρακολούθησε τα αποτελέσματα στο Dashboard.
ΜΟΝΟ αν τα αποτελέσματα είναι καλά → ενεργοποίησε Live Trading.
```

---

## Dashboard — Τι κάνει κάθε tab

| Tab | Περιγραφή |
|---|---|
| **Overview** | KPIs, PnL chart, open positions, Start/Stop bot |
| **Trades** | Πλήρες ιστορικό όλων των trades |
| **Pairs** | Επιλογή ποια crypto να trade-άρει |
| **Settings** | OKX API keys, Leverage, Risk Management |
| **Logs** | Live logs του bot |

---

## ⚠️ Σημαντικές Προειδοποιήσεις

1. **Ξεκίνα ΠΑΝΤΑ με Paper Trading** — δεν χάνεις real χρήματα
2. **Futures με leverage = υψηλός κίνδυνος** — μπορείς να χάσεις όλο το κεφάλαιο
3. **ΜΗΝ βάλεις Withdraw permission** στα OKX API keys
4. **ΜΗΝ ανεβάσεις το .env** στο GitHub (το .gitignore το αποτρέπει)
5. **Δοκίμασε 2-3 μήνες paper** πριν βάλεις real χρήματα

---

## Αν κάτι πάει στραβά

- **Railway logs:** Railway Dashboard → Deployments → View Logs
- **Bot logs:** Dashboard → Logs tab
- **Επανεκκίνηση:** Railway → Deployments → Redeploy
