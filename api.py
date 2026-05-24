"""
Flask REST API — τροφοδοτεί το Dashboard
"""
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from functools import wraps
import os, json
from database import (get_all_trades, get_open_trades, get_stats,
                      get_symbols, set_symbols, get_config, set_config,
                      get_all_settings, save_settings as db_save_settings,
                      init_db)
from config import API_HOST, API_PORT, API_KEY

app = Flask(__name__, static_folder='dashboard')
CORS(app)

def auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if key != API_KEY:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

# ── Dashboard static ──────────────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('dashboard', 'index.html')

# ── Stats ─────────────────────────────────────────────────────────────────────
@app.route('/api/stats')
@auth
def stats():
    return jsonify(get_stats())

@app.route('/api/trades')
@auth
def trades():
    limit = int(request.args.get('limit', 100))
    return jsonify(get_all_trades(limit))

@app.route('/api/positions')
@auth
def positions():
    return jsonify(get_open_trades())

# ── Symbols ───────────────────────────────────────────────────────────────────
@app.route('/api/symbols', methods=['GET'])
@auth
def get_syms():
    return jsonify({'symbols': get_symbols()})

@app.route('/api/symbols', methods=['POST'])
@auth
def update_syms():
    data    = request.get_json()
    symbols = data.get('symbols', [])
    if not isinstance(symbols, list) or len(symbols) == 0:
        return jsonify({'error': 'Invalid symbols'}), 400
    set_symbols(symbols)
    return jsonify({'symbols': get_symbols(), 'message': 'Updated!'})

# ── Bot Control ───────────────────────────────────────────────────────────────
@app.route('/api/bot/status')
@auth
def bot_status():
    running = get_config('running', '0') == '1'
    return jsonify({'running': running})

@app.route('/api/bot/stop', methods=['POST'])
@auth
def bot_stop():
    set_config('running', '0')
    return jsonify({'message': 'Bot stopping...'})

@app.route('/api/bot/start', methods=['POST'])
@auth
def bot_start():
    import subprocess, sys
    set_config('running', '1')
    subprocess.Popen([sys.executable, 'main.py'],
                     stdout=open('logs/bot.log','a'),
                     stderr=subprocess.STDOUT)
    return jsonify({'message': 'Bot started!'})

# ── Logs ──────────────────────────────────────────────────────────────────────
@app.route('/api/logs')
@auth
def get_logs():
    try:
        with open('logs/bot.log') as f:
            lines = f.readlines()[-100:]
        return jsonify({'logs': lines})
    except:
        return jsonify({'logs': []})

# ── Settings ──────────────────────────────────────────────────────────────────
@app.route('/api/settings', methods=['GET'])
@auth
def get_settings():
    return jsonify(get_all_settings())

@app.route('/api/settings', methods=['POST'])
@auth
def update_settings():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400
    allowed = {
        'leverage','margin_type','timeframe','paper_trading','testnet',
        'max_risk_per_trade','stop_loss_pct','take_profit_pct',
        'max_daily_loss','max_drawdown','max_open_positions',
        'min_agreement','min_ml_confidence',
        'telegram_token','telegram_chat_id','telegram_enabled'
    }
    filtered = {k: v for k, v in data.items() if k in allowed}
    db_save_settings(filtered)
    return jsonify({'message': 'Settings saved!', 'settings': get_all_settings()})

@app.route('/api/settings/test-telegram', methods=['POST'])
@auth
def test_telegram():
    token   = get_config('telegram_token', '')
    chat_id = get_config('telegram_chat_id', '')
    if not token or not chat_id:
        return jsonify({'error': 'Token ή Chat ID δεν έχουν οριστεί'}), 400
    import requests as req
    try:
        r = req.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": "🤖 TradingBot test alert!"},
            timeout=5
        )
        if r.status_code == 200:
            return jsonify({'message': 'Test alert στάλθηκε!'})
        return jsonify({'error': f'Error: {r.text}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── Available Pairs from OKX ──────────────────────────────────────────────────
@app.route('/api/available-pairs')
@auth
def available_pairs():
    try:
        from data_feed import get_exchange
        ex      = get_exchange()
        markets = ex.load_markets()
        pairs   = []
        seen    = set()
        for s, m in markets.items():
            if m.get('swap') and m.get('quote') == 'USDT' and m.get('active'):
                display = f"{m['base']}/USDT"
                if display not in seen:
                    seen.add(display)
                    pairs.append({'symbol': display, 'base': m['base'], 'quote': 'USDT'})
        pairs = sorted(pairs, key=lambda x: x['symbol'])
        return jsonify({'pairs': pairs, 'count': len(pairs)})
    except Exception as e:
        fallback = [
            'BTC/USDT','ETH/USDT','SOL/USDT','OKB/USDT','XRP/USDT',
            'DOGE/USDT','ADA/USDT','AVAX/USDT','LINK/USDT','DOT/USDT',
            'LTC/USDT','UNI/USDT','ATOM/USDT','NEAR/USDT','APT/USDT',
            'ARB/USDT','OP/USDT','INJ/USDT','SUI/USDT','TIA/USDT',
            'WLD/USDT','SEI/USDT','TON/USDT','PEPE/USDT','BONK/USDT',
        ]
        return jsonify({
            'pairs': [{'symbol':s,'base':s.split('/')[0],'quote':'USDT'} for s in fallback],
            'count': len(fallback),
            'note': f'Offline — {str(e)[:60]}'
        })

# ── Manual Close Trade ─────────────────────────────────────────────────────────
@app.route('/api/trade/close', methods=['POST'])
@auth
def manual_close():
    from executor import EX
    from risk_manager import RISK
    from data_feed import get_mark_price
    from database import get_open_trades
    data  = request.get_json() or {}
    trade_id = data.get('trade_id')
    if not trade_id:
        return jsonify({'error': 'trade_id required'}), 400
    trades = get_open_trades()
    trade = next((t for t in trades if t['id'] == trade_id), None)
    if not trade:
        return jsonify({'error': 'Trade not found or already closed'}), 404
    try:
        price = get_mark_price(trade['symbol'])
        should_close, reason = RISK.should_close(trade, price)
        if not should_close:
            reason = "MANUAL_CLOSE"
        pnl_pct, pnl_usdt = RISK.calc_pnl(trade, price)
        RISK.daily_pnl += pnl_usdt
        EX.close_position(trade, price, reason, pnl_pct, pnl_usdt)
        return jsonify({'message': f"Closed {trade['symbol']}", 'pnl_usdt': pnl_usdt})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── Manual Test Trade ──────────────────────────────────────────────────────────
@app.route('/api/trade/manual', methods=['POST'])
@auth
def manual_trade():
    from executor import EX
    from risk_manager import RISK
    from data_feed import get_mark_price, fetch_balance
    from database import get_config
    data = request.get_json() or {}
    symbol = data.get('symbol', 'BTC/USDT')
    side   = int(data.get('side', 1))  # 1=LONG, -1=SHORT
    try:
        entry = get_mark_price(symbol)
        qty   = data.get('qty', 0.001)
        sl    = data.get('sl', round(entry * 0.98, 2))
        tp    = data.get('tp', round(entry * 1.03, 2))
        trade_id = EX.open_position(symbol, side, float(qty), entry, sl, tp,
                                    'manual', {'manual': True})
        if trade_id:
            return jsonify({'message': f"{'LONG' if side==1 else 'SHORT'} {symbol} opened!", 'trade_id': trade_id, 'entry': entry})
        return jsonify({'error': 'Failed to open trade'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── Balance ───────────────────────────────────────────────────────────────────
@app.route('/api/balance')
@auth
def get_balance():
    from config import PAPER_TRADING
    from executor import EX
    result = {
        'paper_trading':  PAPER_TRADING,
        'paper_balance':  round(EX.paper_balance, 2),
        'real_balance':   None,
        'currency':       'USDT',
    }
    if not PAPER_TRADING:
        try:
            from data_feed import fetch_balance
            bal = fetch_balance()
            usdt = bal.get('USDT', {})
            result['real_balance'] = round(float(usdt.get('free', 0)), 2)
        except Exception as e:
            result['real_balance_error'] = str(e)
    else:
        try:
            from data_feed import fetch_balance
            bal = fetch_balance()
            usdt = bal.get('USDT', {})
            result['real_balance'] = round(float(usdt.get('free', 0)), 2)
        except:
            result['real_balance'] = None
    return jsonify(result)

# ── Reset Balance ──────────────────────────────────────────────────────────────
@app.route('/api/balance/reset', methods=['POST'])
@auth
def reset_balance():
    from database import set_config
    set_config('paper_balance', '1000.0')
    from executor import EX
    EX._load_balance()
    return jsonify({'message': 'Balance reset to $1,000', 'paper_balance': 1000.0})

if __name__ == '__main__':
    import os
    os.makedirs('logs', exist_ok=True)
    os.makedirs('data', exist_ok=True)
    os.makedirs('models', exist_ok=True)
    init_db()
    port = int(os.getenv('PORT', API_PORT))
    app.run(host=API_HOST, port=port, debug=False)
