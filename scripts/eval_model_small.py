import sys, json
sys.path.insert(0, ".")
import pandas as pd, numpy as np, joblib
from sklearn.metrics import roc_auc_score, classification_report

m = joblib.load("data/learning/choch/2026-08/model.joblib")
df = pd.DataFrame([json.loads(l) for l in open("data/learning/choch/2026-08/features.jsonl") if l.strip()])
FEAT = ["score", "momentum", "after_bos", "displacement", "htf_ctx_code",
        "htf_trend_int", "cd", "break_body_ratio", "dist_to_level", "bos_age_bars", "tf_code"]
for c in FEAT:
    if c not in df.columns:
        df[c] = 0
X = df[FEAT].astype(float).to_numpy()
print("n=", len(df))
for lab in ["label_ep", "label_peak", "label_dir", "peak_fav", "real"]:
    if lab not in df.columns:
        continue
    y = df[lab].astype(float).to_numpy()
    if df[lab].nunique() < 2:
        print(f"{lab}: SIN VARIEDAD ({int(y.sum())}/{len(y)})")
        continue
    try:
        p = m.predict_proba(X)[:, 1]
        print(f"{lab}: ROC-AUC={round(roc_auc_score(y, p), 3)}  pos={int(y.sum())}/{len(y)}")
    except Exception as e:
        print(f"{lab}: ERROR {repr(e)[:150]}")
