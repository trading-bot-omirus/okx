import pandas as pd, numpy as np

def compute(df: pd.DataFrame):
    c = df['close']
    mid   = c.rolling(20).mean()
    std   = c.rolling(20).std()
    upper = mid + 2*std
    lower = mid - 2*std
    z     = (c.iloc[-1] - mid.iloc[-1]) / (std.iloc[-1]+1e-10)
    rsi14 = 100 - 100/(1+(c.diff().clip(lower=0).rolling(14).mean()/
                          (-c.diff().clip(upper=0).rolling(14).mean()+1e-10)))

    if z < -2.0 and rsi14.iloc[-1] < 35:
        conf = min(0.95, abs(z)/4)
        return 1.0, conf
    elif z > 2.0 and rsi14.iloc[-1] > 65:
        conf = min(0.95, abs(z)/4)
        return -1.0, conf
    return 0.0, 0.0
