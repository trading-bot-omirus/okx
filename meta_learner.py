"""
Meta-Learner: συνδυάζει signals από 4 strategies + market context
Εκπαιδεύεται με walk-forward από ιστορικά trades
"""
import numpy as np, pandas as pd, joblib, logging, os, json
from datetime import datetime
import xgboost as xgb
from sklearn.preprocessing import LabelEncoder
from config import MODEL_PATH

log = logging.getLogger(__name__)

class MetaLearner:
    def __init__(self):
        self.model = xgb.XGBClassifier(
            n_estimators=300,
            max_depth=4,
            learning_rate=0.04,
            subsample=0.8,
            colsample_bytree=0.8,
            use_label_encoder=False,
            eval_metric='mlogloss',
            random_state=42
        )
        self.trained = False
        if os.path.exists(MODEL_PATH):
            self._load()

    def _load(self):
        try:
            self.model = joblib.load(MODEL_PATH)
            self.trained = True
            log.info("Meta-learner model loaded.")
        except Exception as e:
            log.warning(f"Could not load model: {e}")

    def _save(self):
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        joblib.dump(self.model, MODEL_PATH)

    def build_features(self, signals: dict, ctx: dict) -> pd.DataFrame:
        mom_s, mom_c   = signals.get('momentum',  (0,0))
        mr_s,  mr_c    = signals.get('mean_rev',  (0,0))
        ml_s,  ml_c    = signals.get('ml',        (0,0))
        arb_s, arb_c   = signals.get('arb',       (0,0))

        raw = [mom_s, mr_s, ml_s, arb_s]
        non_zero = [x for x in raw if x != 0]
        if non_zero:
            longs  = sum(1 for x in non_zero if x > 0)
            shorts = sum(1 for x in non_zero if x < 0)
            agreement = max(longs, shorts) / len(non_zero)
        else:
            agreement = 0.0
        votes_up  = sum(1 for x in raw if x > 0)
        votes_dn  = sum(1 for x in raw if x < 0)

        return pd.DataFrame([{
            'mom_signal':    mom_s, 'mom_conf':   mom_c,
            'mr_signal':     mr_s,  'mr_conf':    mr_c,
            'ml_signal':     ml_s,  'ml_conf':    ml_c,
            'arb_signal':    arb_s, 'arb_conf':   arb_c,
            'agreement':     agreement,
            'votes_up':      votes_up,
            'votes_dn':      votes_dn,
            'conf_avg':      np.mean([mom_c, mr_c, ml_c, arb_c]),
            'atr_pct':       ctx.get('atr_pct', 0),
            'vol_ratio':     ctx.get('vol_ratio', 1),
            'rsi':           ctx.get('rsi', 50),
            'adx':           ctx.get('adx', 20),
            'hour':          ctx.get('hour', 12),
            'dow':           ctx.get('dow', 2),
        }])

    def predict(self, signals: dict, ctx: dict) -> tuple[int, float]:
        feat = self.build_features(signals, ctx)
        if not self.trained:
            # Rule-based fallback
            return self._rule_based(signals, ctx)
        try:
            prob  = self.model.predict_proba(feat)[0]
            label = int(self.model.predict(feat)[0])
            conf  = float(max(prob))
            return label - 1, conf   # classes: 0=sell,1=hold,2=buy → -1,0,+1
        except Exception as e:
            log.error(f"Predict error: {e}")
            return 0, 0.0

    def _rule_based(self, signals, ctx) -> tuple[int, float]:
        """Fallback όταν δεν υπάρχει trained model"""
        from config import get_live_config
        _cfg = get_live_config()
        _min_agreement     = _cfg['MIN_AGREEMENT']
        _min_ml_confidence = _cfg['MIN_ML_CONFIDENCE']

        vals = [s[0] for s in signals.values() if s[0] != 0]
        if not vals: return 0, 0.0
        longs  = sum(1 for x in vals if x > 0)
        shorts = sum(1 for x in vals if x < 0)
        agree  = max(longs, shorts) / len(vals)
        if agree < _min_agreement: return 0, agree
        ml_s, ml_c = signals.get('ml', (0, 0))
        if ml_s != 0 and ml_c > 0 and ml_c < _min_ml_confidence: return 0, ml_c
        return (1 if longs > shorts else -1), agree

    def train_from_db(self):
        """Walk-forward training από ιστορικά trades στη DB"""
        try:
            from database import get_all_trades
            trades = get_all_trades(limit=5000)
            if len(trades) < 100:
                log.info(f"Not enough trades for training ({len(trades)}). Need 100+.")
                return False

            rows = []
            for t in trades:
                if t['signals_json'] and t['pnl_pct'] is not None:
                    import json
                    try:
                        sig = json.loads(t['signals_json'])
                        sig['outcome'] = 2 if t['pnl_pct'] > 0.005 else (0 if t['pnl_pct'] < -0.005 else 1)
                        rows.append(sig)
                    except: pass

            if len(rows) < 50:
                log.info("Not enough labeled rows for training.")
                return False

            df  = pd.DataFrame(rows)
            X   = df.drop('outcome', axis=1, errors='ignore')
            y   = df['outcome'].astype(int)

            n   = len(X)
            split = int(n * 0.8)
            self.model.fit(X.iloc[:split], y.iloc[:split],
                           eval_set=[(X.iloc[split:], y.iloc[split:])],
                           verbose=False)
            self.trained = True
            self._save()
            log.info(f"Meta-learner trained on {n} samples and saved.")
            return True
        except Exception as e:
            log.error(f"Training error: {e}")
            return False

    def train_from_backtest(self, path='data/backtest_trades.json'):
        """Εκπαιδεύει XGBoost από backtest trades"""
        try:
            if not os.path.exists(path):
                log.warning(f"Backtest file not found: {path}")
                return False
            with open(path) as f:
                trades = json.load(f)
            if len(trades) < 50:
                log.info(f"Not enough trades ({len(trades)}). Need 50+")
                return False
            rows = []
            for t in trades:
                ctx = t.get('ctx', {})
                rows.append({
                    'mom_signal': 0, 'mom_conf': 0,
                    'mr_signal': 0, 'mr_conf': 0,
                    'ml_signal': 0, 'ml_conf': 0.3,
                    'arb_signal': t['arb_signal'], 'arb_conf': t['conf'],
                    'agreement': t.get('agreement', 1.0),
                    'votes_up': 1 if t['arb_signal'] > 0 else 0,
                    'votes_dn': 1 if t['arb_signal'] < 0 else 0,
                    'conf_avg': t['conf'] / 4,
                    'atr_pct': ctx.get('atr_pct', 0),
                    'vol_ratio': ctx.get('vol_ratio', 1),
                    'rsi': ctx.get('rsi', 50),
                    'adx': ctx.get('adx', 0),
                    'hour': ctx.get('hour', 12),
                    'dow': ctx.get('dow', 2),
                    'outcome': t['outcome'],
                })
            df = pd.DataFrame(rows)
            X = df.drop('outcome', axis=1)
            y = df['outcome'].astype(int)
            n = len(X)
            split = int(n * 0.8)
            self.model = xgb.XGBClassifier(
                n_estimators=300, max_depth=4, learning_rate=0.04,
                subsample=0.8, colsample_bytree=0.8,
                use_label_encoder=False, eval_metric='mlogloss',
                random_state=42
            )
            self.model.fit(X.iloc[:split], y.iloc[:split],
                           eval_set=[(X.iloc[split:], y.iloc[split:])],
                           verbose=False)
            self.trained = True
            self._save()
            log.info(f"ML model trained from {n} backtest trades. Model saved.")
            return True
        except Exception as e:
            log.error(f"train_from_backtest error: {e}", exc_info=True)
            return False

META = MetaLearner()
