"""
Stat-arb / regime signal — βασισμένο στη σχέση BTC ↔ symbol
"""
import pandas as pd, numpy as np

def compute(df_sym: pd.DataFrame, df_btc: pd.DataFrame):
    if df_btc is None or len(df_btc) < 60:
        return 0.0, 0.0
    n  = min(len(df_sym), len(df_btc), 200)
    sy = df_sym['close'].iloc[-n:].values
    bt = df_btc['close'].iloc[-n:].values
    spread = sy/sy[0] - bt/bt[0]
    z = (spread[-1] - spread.mean()) / (spread.std()+1e-10)
    if z < -1.5:
        return 1.0, min(0.85, abs(z)/3)
    elif z > 1.5:
        return -1.0, min(0.85, abs(z)/3)
    return 0.0, 0.0
