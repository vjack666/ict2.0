import sys, json, glob, os
sys.path.insert(0, ".")
import pandas as pd, numpy as np
import joblib
from sklearn.metrics import roc_auc_score

models = glob.glob("data/learning/choch/**/model.joblib", recursive=True)
print("modelos:", models)
m = joblib.load(models[-1])
files = glob.glob("data/learning/choch/EURUSD_M5_*.jsonl") + glob.glob("data/learning/choch/2026-08/features.jsonl")
rows = []
for f in files:
    for l in open(f):
        if l.strip():
            rows.append(json.loads(l))
df = pd.DataFrame(rows)
print("total CHOCH REAL:", len(df), "labels=1:", int(df["label"].sum()))
FEAT = ["score", "momentum", "after_bos", "displacement", "htf_ctx_code",
        "htf_trend_int", "cd", "break_body_ratio", "dist_to_level", "bos_age_bars", "tf_code"]
for c in FEAT:
    if c not in df.columns:
        df[c] = 0
X = df[FEAT].astype(float).to_numpy()
y = df["label"].to_numpy()
if df["label"].nunique() < 2:
    print("SIN VARIEDAD DE LABELS")
else:
    p = m.predict_proba(X)[:, 1]
    print("ROC-AUC (todo):", round(roc_auc_score(y, p), 3))
    for tf in sorted(df["tf"].unique()):
        sub = df[df["tf"] == tf]
        if sub["label"].nunique() >= 2:
            pp = m.predict_proba(sub[FEAT].astype(float).to_numpy())[:, 1]
            print(f"  {tf}: ROC={round(roc_auc_score(sub['label'], pp), 3)} n={len(sub)}")
    print("TOP features:")
    for f, imp in sorted(zip(FEAT, m.feature_importances_), key=lambda x: -x[1])[:5]:
        print("  ", f, round(imp, 3))
