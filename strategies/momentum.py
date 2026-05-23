import pandas as pd, numpy as np

def ema(series, n): return series.ewm(span=n, adjust=False).mean()

def compute(df: pd.DataFrame):
    c = df['close']
    e9, e21, e55 = ema(c,9), ema(c,21), ema(c,55)
    bull_cross = (e9.iloc[-1] > e21.iloc[-1] > e55.iloc[-1])
    bear_cross = (e9.iloc[-1] < e21.iloc[-1] < e55.iloc[-1])

    delta = c.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rsi   = (100 - 100/(1+(gain/(loss+1e-10)))).iloc[-1]

    macd_line   = ema(c,12) - ema(c,26)
    signal_line = ema(macd_line, 9)
    macd_bull   = macd_line.iloc[-1] > signal_line.iloc[-1]
    macd_bear   = macd_line.iloc[-1] < signal_line.iloc[-1]

    high, low = df['high'], df['low']
    tr  = pd.concat([high-low, (high-c.shift()).abs(), (low-c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    dm_p = high.diff().clip(lower=0)
    dm_n = (-low.diff().clip(upper=0))
    di_p = (dm_p.rolling(14).mean()/(atr+1e-10)*100).iloc[-1]
    di_n = (dm_n.rolling(14).mean()/(atr+1e-10)*100).iloc[-1]
    adx  = abs(di_p-di_n)/(di_p+di_n+1e-10)*100

    if bull_cross and 50 < rsi < 70 and macd_bull:
        return 1.0, min(0.95, 0.5 + adx/100 + (rsi-50)/100)
    elif bear_cross and 30 < rsi < 50 and macd_bear:
        return -1.0, min(0.95, 0.5 + adx/100 + (50-rsi)/100)
    return 0.0, 0.0
