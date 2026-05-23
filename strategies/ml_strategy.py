import pandas as pd, numpy as np, joblib, os
from config import MODEL_PATH

def make_features(df: pd.DataFrame) -> pd.DataFrame:
    c = df['close']; h = df['high']; l = df['low']; v = df['volume']
    feat = pd.DataFrame(index=df.index)
    for n in [9,21,55]:
        feat[f'ema{n}_dist'] = (c - c.ewm(span=n).mean()) / c
    delta = c.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    feat['rsi14'] = 100 - 100/(1+gain/(loss+1e-10))
    feat['macd']  = c.ewm(12).mean() - c.ewm(26).mean()
    tr   = pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    feat['atr14']    = tr.rolling(14).mean() / c
    feat['vol_ratio']= v / v.rolling(20).mean()
    feat['ret_1']    = c.pct_change(1)
    feat['ret_5']    = c.pct_change(5)
    feat['ret_15']   = c.pct_change(15)
    feat['hour']     = df.index.hour
    feat['dow']      = df.index.dayofweek
    return feat.dropna()

def compute(df: pd.DataFrame):
    if not os.path.exists(MODEL_PATH):
        return 0.0, 0.3   # no model yet → neutral
    try:
        model = joblib.load(MODEL_PATH)
        feat  = make_features(df)
        if len(feat) == 0:
            return 0.0, 0.0
        row   = feat.iloc[[-1]]
        prob  = model.predict_proba(row)[0]   # [p_down, p_neutral, p_up]
        p_up, p_dn = prob[2], prob[0]
        if p_up > p_dn and p_up > 0.55:
            return 1.0, float(p_up)
        elif p_dn > p_up and p_dn > 0.55:
            return -1.0, float(p_dn)
        return 0.0, float(max(prob))
    except Exception as e:
        return 0.0, 0.0
