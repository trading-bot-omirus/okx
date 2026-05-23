#!/bin/bash
# Εκκίνηση API + Bot
cd /var/www/tradingbot
source venv/bin/activate
nohup python api.py  > logs/api.log  2>&1 &
nohup python main.py > logs/bot.log  2>&1 &
echo "Bot + API started! PID: $!"
