# 🚀 Deploy στο Railway — Βήμα-Βήμα

## Βήμα 1 — Φτιάξε GitHub repo
1. Πήγαινε στο github.com → σύνδεση
2. Πάτα **New repository** → όνομα: `trading-bot`
3. Private ✅ → Create repository
4. Ανέβασε τα αρχεία:
   - Πάτα **uploading an existing file**
   - Σύρε ΟΛΟΝ τον φάκελο `trading_bot`
   - Commit changes

⚠️ ΜΗΝ ανεβάσεις το `.env` αρχείο!

---

## Βήμα 2 — Deploy στο Railway
1. Πήγαινε railway.app → **Login with GitHub**
2. **New Project** → Deploy from GitHub repo
3. Επέλεξε το `trading-bot` repo
4. Railway το ανιχνεύει αυτόματα ως Python ✅

---

## Βήμα 3 — Variables (API Keys)
Railway Dashboard → το project σου → **Variables** → Add:

```
OKX_API_KEY          = το_api_key_σου
OKX_API_SECRET       = το_api_secret_σου
OKX_PASSPHRASE       = το_passphrase_σου
DASHBOARD_API_KEY    = διάλεξε_ένα_password
TELEGRAM_TOKEN       = (προαιρετικό)
TELEGRAM_CHAT_ID     = (προαιρετικό)
```

---

## Βήμα 4 — Deploy!
- Railway κάνει build αυτόματα
- Μετά από 2-3 λεπτά → **View Logs** για να δεις αν τρέχει

---

## Βήμα 5 — Άνοιξε το Dashboard
Railway → Settings → **Generate Domain**
→ Παίρνεις URL τύπου: `https://trading-bot-xxx.railway.app`
→ Άνοιξε στον browser → βάλε το DASHBOARD_API_KEY

---

## ✅ Checklist
- [ ] PAPER_TRADING = True στο Dashboard Settings
- [ ] Testnet/Demo = True στο Dashboard Settings  
- [ ] OKX API Keys με ΜΟΝΟ Read + Trade
- [ ] .env ΔΕΝ ανέβηκε στο GitHub
- [ ] Δοκίμασε 2-3 μήνες paper πριν live!
