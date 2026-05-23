# 🚀 Οδηγός Deployment στο Cloudways

## Βήμα 1 — SSH στον Cloudways Server
```bash
# Cloudways Dashboard → Servers → SSH Keys → Copy SSH command
ssh your-user@your-server-ip
```

## Βήμα 2 — Εγκατάσταση Python & venv
```bash
sudo apt update && sudo apt install python3-pip python3-venv -y
mkdir -p /var/www/tradingbot && cd /var/www/tradingbot
```

## Βήμα 3 — Upload κώδικα (από τον υπολογιστή σου)
```bash
# Στον local υπολογιστή:
scp -r ./trading_bot/* your-user@your-server-ip:/var/www/tradingbot/
```

## Βήμα 4 — Python venv + packages
```bash
cd /var/www/tradingbot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Βήμα 5 — Ρύθμιση .env
```bash
cp .env.example .env
nano .env
# Βάλε τα Binance API keys & dashboard password
```

## Βήμα 6 — Supervisor (ώστε να τρέχει πάντα)
```bash
sudo apt install supervisor -y
sudo cp tradingbot-api.conf /etc/supervisor/conf.d/
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start tradingbot-api
# Το bot ξεκινάει μέσω Dashboard ή:
sudo supervisorctl start tradingbot-bot
```

## Βήμα 7 — Nginx Reverse Proxy (Cloudways)
Cloudways Dashboard → Application → Vhost:
```nginx
location /api/ {
    proxy_pass http://127.0.0.1:5000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
location / {
    proxy_pass http://127.0.0.1:5000;
}
```

## Βήμα 8 — Άνοιγμα Dashboard
Πήγαινε στο: https://your-cloudways-domain.cloudwaysapps.com
Βάλε το DASHBOARD_API_KEY που όρισες στο .env

## ✅ Checklist
- [ ] PAPER_TRADING = True (δοκιμή πρώτα!)
- [ ] TESTNET = True (Binance testnet)
- [ ] API keys με ΜΟΝΟ Futures permission (όχι withdraw!)
- [ ] .env ΔΕΝ ανεβαίνει στο GitHub (βάλτο στο .gitignore)
- [ ] Δοκίμασε 2-3 μήνες paper πριν live
