"""
Meta-Learner: συνδυάζει signals από 4 strategies + market context
Εκπαιδεύεται με walk-forward από ιστορικά trades
"""
import numpy as np, pandas as pd, joblib, logging, os, json
from datetime import datetime
import xgboost as xgb
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from sklearn.utils.class_weight import compute_class_weight
from sklearn.preprocessing import LabelEncoder
from config import MODEL_PATH

log = logging.getLogger(__name__)

# ── Per-strategy ML (Phase 13) ────────────────────────────────────────────────

FEATURE_KEYS = [
    'rsi','bb_pos','atr','vol_ratio',
    'hour','weekday','trend_bull','trend_bear',
    'price_vs_ema20','price_vs_ema50'
]

def train_from_backtest(trades_path='data/backtest_trades.json'):
    """
    Εκπαιδεύει ξεχωριστό GradientBoostingClassifier για κάθε strategy.
    Αποθηκεύει models/ml_{strategy}.pkl.
    """
    if not os.path.exists(trades_path):
        log.warning(f"Backtest file not found: {trades_path}")
        return None

    with open(trades_path) as f:
        all_trades = json.load(f)

    if len(all_trades) < 30:
        log.info(f"Not enough trades ({len(all_trades)}). Need 30+")
        return None

    os.makedirs('models', exist_ok=True)
    results = {}

    for strat in ['momentum','mean_rev','arb']:
        trades = [t for t in all_trades if t.get('strategy') == strat]
        if len(trades) < 30:
            log.info(f"  {strat}: insufficient data ({len(trades)}) — skip")
            results[strat] = {'trades': len(trades), 'win_rate': 0.0, 'error': 'insufficient'}
            continue

        X = np.array([
            [t.get('features', {}).get(k, 0) for k in FEATURE_KEYS]
            for t in trades
        ], dtype=np.float64)
        y = np.array([t.get('label', 0) for t in trades])

        if len(np.unique(y)) < 2:
            log.info(f"  {strat}: only 1 class ({np.unique(y)[0]}) — skip")
            results[strat] = {'trades': len(trades), 'win_rate': round(float(y.sum()/len(y))*100, 1), 'error': 'single_class'}
            continue

        classes = np.unique(y)
        weights = compute_class_weight('balanced', classes=classes, y=y)
        cw = dict(zip(classes, weights))

        X_tr, X_te, y_tr, y_te = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y)

        model = GradientBoostingClassifier(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            random_state=42
        )
        model.fit(X_tr, y_tr)

        report = classification_report(y_te, model.predict(X_te), output_dict=True, zero_division=0)
        log.info(f"\n{strat.upper()} model:")
        log.info(f"  Accuracy: {report.get('accuracy', 0):.3f}")
        log.info(f"  Precision: {report.get('macro avg', {}).get('precision', 0):.3f}")
        log.info(f"  Recall: {report.get('macro avg', {}).get('recall', 0):.3f}")

        path = f'models/ml_{strat}.pkl'
        joblib.dump({
            'model': model,
            'feature_keys': FEATURE_KEYS,
            'strategy': strat,
            'n_samples': len(trades),
        }, path)
        log.info(f"  Saved: {path}")

        wins = int(y.sum())
        results[strat] = {
            'trades':   len(trades),
            'win_rate': round(wins / len(trades) * 100, 1),
        }

    summary_path = 'models/training_summary.json'
    with open(summary_path, 'w') as f:
        json.dump(results, f, indent=2)
    log.info(f"Training summary saved: {summary_path}")

    return results


def predict_for_strategy(strategy_name: str, features_dict: dict) -> tuple[float, float]:
    """
    Επιστρέφει (signal, confidence) για τη συγκεκριμένη strategy.
    signal: 1.0 = LONG, -1.0 = SHORT, 0.0 = HOLD
    confidence: 0..1
    Fallback: (0.0, 0.3) όταν δεν υπάρχει μοντέλο.
    """
    path = f'models/ml_{strategy_name}.pkl'
    if not os.path.exists(path):
        return 0.0, 0.3

    try:
        data = joblib.load(path)
        model = data['model']
        keys = data['feature_keys']
        X = np.array([[features_dict.get(k, 0) for k in keys]], dtype=np.float64)
        prob = float(model.predict_proba(X)[0][1])

        if prob > 0.65:
            return 1.0, prob
        elif prob < 0.35:
            return -1.0, 1 - prob
        else:
            return 0.0, 0.5
    except Exception as e:
        log.warning(f"predict_for_strategy({strategy_name}) error: {e}")
        return 0.0, 0.3

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
