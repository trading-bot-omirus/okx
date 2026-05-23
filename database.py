"""
SQLite database — αποθηκεύει trades, signals, stats
"""
import sqlite3, json
from datetime import datetime
from config import DB_PATH

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS trades (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol      TEXT    NOT NULL,
        side        TEXT    NOT NULL,       -- LONG / SHORT
        entry_price REAL    NOT NULL,
        exit_price  REAL,
        qty         REAL    NOT NULL,
        leverage    INTEGER DEFAULT 2,
        pnl_pct     REAL,
        pnl_usdt    REAL,
        status      TEXT    DEFAULT 'OPEN', -- OPEN / CLOSED / STOPPED
        stop_loss   REAL,
        take_profit REAL,
        strategy    TEXT,                  -- ποια στρατηγική το πήρε
        signals_json TEXT,                 -- raw signals από bots
        opened_at   TEXT    NOT NULL,
        closed_at   TEXT,
        paper       INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS signals (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol      TEXT,
        momentum    REAL,
        mean_rev    REAL,
        ml_score    REAL,
        arb_score   REAL,
        agreement   REAL,
        final_signal INTEGER,
        market_regime TEXT,
        created_at  TEXT
    );

    CREATE TABLE IF NOT EXISTS bot_config (
        key   TEXT PRIMARY KEY,
        value TEXT
    );

    CREATE TABLE IF NOT EXISTS daily_stats (
        date         TEXT PRIMARY KEY,
        total_trades INTEGER DEFAULT 0,
        wins         INTEGER DEFAULT 0,
        losses       INTEGER DEFAULT 0,
        pnl_usdt     REAL    DEFAULT 0,
        max_drawdown REAL    DEFAULT 0
    );
    """)
    conn.commit()
    # Default symbols
    symbols = json.dumps(["BTC/USDT","ETH/USDT","BNB/USDT","SOL/USDT"])
    c.execute("INSERT OR IGNORE INTO bot_config VALUES ('symbols', ?)", (symbols,))
    c.execute("INSERT OR IGNORE INTO bot_config VALUES ('running', '0')")
    conn.commit()
    conn.close()

# ── CRUD ──────────────────────────────────────────────────────────────────────
def open_trade(symbol, side, entry, qty, leverage, sl, tp, strategy, signals, paper=True):
    conn = get_conn()
    conn.execute("""
        INSERT INTO trades (symbol,side,entry_price,qty,leverage,stop_loss,take_profit,
                            strategy,signals_json,opened_at,paper)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (symbol, side, entry, qty, leverage, sl, tp,
          strategy, json.dumps(signals), datetime.utcnow().isoformat(), int(paper)))
    conn.commit()
    trade_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return trade_id

def close_trade(trade_id, exit_price, pnl_pct, pnl_usdt, status="CLOSED"):
    conn = get_conn()
    conn.execute("""
        UPDATE trades SET exit_price=?, pnl_pct=?, pnl_usdt=?, status=?, closed_at=?
        WHERE id=?
    """, (exit_price, pnl_pct, pnl_usdt, status, datetime.utcnow().isoformat(), trade_id))
    conn.commit()
    conn.close()

def get_open_trades():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM trades WHERE status='OPEN'").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_trades(limit=200):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stats():
    conn = get_conn()
    r = conn.execute("""
        SELECT
            COUNT(*)                            AS total_trades,
            SUM(CASE WHEN pnl_usdt>0 THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN pnl_usdt<=0 THEN 1 ELSE 0 END) AS losses,
            ROUND(SUM(pnl_usdt),2)              AS total_pnl,
            ROUND(AVG(pnl_pct),4)               AS avg_pnl_pct,
            ROUND(MAX(pnl_usdt),2)              AS best_trade,
            ROUND(MIN(pnl_usdt),2)              AS worst_trade
        FROM trades WHERE status='CLOSED'
    """).fetchone()
    conn.close()
    d = dict(r)
    w = d['wins'] or 0
    t = d['total_trades'] or 1
    d['win_rate'] = round(w / t * 100, 1)
    return d

def save_signal(sym, mom, mr, ml, arb, agr, final, regime):
    conn = get_conn()
    conn.execute("""
        INSERT INTO signals (symbol,momentum,mean_rev,ml_score,arb_score,
                             agreement,final_signal,market_regime,created_at)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (sym, mom, mr, ml, arb, agr, final, regime, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def get_config(key, default=None):
    conn = get_conn()
    row = conn.execute("SELECT value FROM bot_config WHERE key=?", (key,)).fetchone()
    conn.close()
    return row[0] if row else default

def set_config(key, value):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO bot_config VALUES (?,?)", (key, str(value)))
    conn.commit()
    conn.close()

def get_symbols():
    return json.loads(get_config('symbols', '["BTC/USDT","ETH/USDT"]'))

def set_symbols(symbols: list):
    set_config('symbols', json.dumps(symbols))

# ── Settings (Risk / Bot config) ──────────────────────────────────────────────
def get_all_settings() -> dict:
    """Επιστρέφει όλες τις ρυθμίσεις με default τιμές"""
    defaults = {
        'leverage':           '2',
        'margin_type':        'isolated',
        'timeframe':          '15m',
        'paper_trading':      '1',
        'testnet':            '1',
        'max_risk_per_trade': '1.0',
        'stop_loss_pct':      '1.5',
        'take_profit_pct':    '3.0',
        'max_daily_loss':     '3.0',
        'max_drawdown':       '12.0',
        'max_open_positions': '3',
        'min_agreement':      '60',
        'min_ml_confidence':  '62',
        'telegram_token':     '',
        'telegram_chat_id':   '',
        'telegram_enabled':   '0',
    }
    conn = get_conn()
    rows = conn.execute("SELECT key, value FROM bot_config").fetchall()
    conn.close()
    result = dict(defaults)
    for r in rows:
        result[r[0]] = r[1]
    return result

def save_settings(settings: dict):
    """Αποθηκεύει ρυθμίσεις στη DB"""
    conn = get_conn()
    for key, value in settings.items():
        conn.execute("INSERT OR REPLACE INTO bot_config VALUES (?,?)", (key, str(value)))
    conn.commit()
    conn.close()
