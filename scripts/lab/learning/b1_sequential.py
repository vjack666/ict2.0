"""B1 — SEQUENTIAL ICT ablation lab (version aislada, sin imports inexistentes).

El plan BLOQUE B1 lista LIQUIDITY/SWEEP/DISPLACEMENT/STRUCTURE/OB/FVG/RETEST.
HALLAZGO A3: en tools/ SOLO existen swing, bos, choch, displacement como detectores
(segun ls tools/*.py). liquidity/sweep/fvg/retest NO son modulos Tool independientes.
Por tanto la cadena medible es: SWING -> DISPLACEMENT -> BOS(STRUCTURE) -> CHOCH.

Para cada profundidad k (presencia acumulada de eventos 0..k ANTES del break CHOCH, PIT):
  - feature binaria seq_depth_k = 1 si los k eventos previos ocurrieron antes del break
  - modelo: RandomForest sobre [features_base + seq_depth_k]
  - metrica: PR-AUC / ROC / Brier de label_ep en holdout temporal 75/25

GATE B1: PASS si profundidades mayores aportan ΔPR-AUC incremental significativo
vs profundidad minima; FAIL si no hay ganancia o n insuficiente (<30 por celda).

NO hardcodea: todo medido con sklearn. PIT obligatorio. Sin promocion automatica.
"""
from __future__ import annotations
import sys, os, json, time, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, REPO)
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (roc_auc_score, average_precision_score, brier_score_loss)

from tools.swing import SwingTool
from tools.bos import BOSTool
from tools.choch import CHOCHTool
from tools.displacement import detect_displacement

SYM = "EURUSD"
TF = "M5"
PARQUET = os.path.join(REPO, f"data/raw/{SYM}/{SYM}_{TF}.parquet")
OUT_JSON = os.path.join(REPO, "data/learning/pipeline/experiments/EXP-007_sequential_ict.json")
RS = 42

# Etapas medibles (HALLAZGO: solo estas existen como detectores en tools/)
STAGES = ["SWING", "DISPLACEMENT", "BOS", "CHOCH"]


def main():
    t0 = time.time()
    d = pd.read_parquet(PARQUET)
    d = d.assign(time=pd.to_datetime(d["time"])).reset_index(drop=True)
    print(f"[B1] {SYM} {TF}: {len(d)} barras")
    out = detect_displacement(d)
    sw = SwingTool(lookback=5).run(out, symbol=SYM)
    sids = {e.origin_bar: e.id for e in sw}
    bo = BOSTool(lookback=5).run(out, symbol=SYM, context={"swing_ids": sids})
    che = CHOCHTool().run(out, symbol=SYM, context={"swings": sw, "boses": bo})

    # Universo CHOCH del dataset ya generado (label_ep)
    feat_path = os.path.join(REPO, "data/learning/choch/full/features.jsonl")
    rows = [json.loads(l) for l in open(feat_path, encoding="utf-8") if l.strip()]
    fdf = pd.DataFrame(rows)
    fdf = fdf[fdf["tf"] == TF].copy().reset_index(drop=True)
    fdf["dt"] = pd.to_datetime(fdf["time"])
    fdf = fdf.dropna(subset=["label_ep", "score_n", "momentum", "after_bos",
                             "displacement", "htf_ctx_code", "htf_trend_int",
                             "cd", "break_body_ratio", "dist_to_level", "bos_age_bars", "tf_code"])
    fdf["label_ep"] = fdf["label_ep"].astype(int)
    print(f"[B1] universo CHOCH: {len(fdf)} eventos, label_ep rate={fdf['label_ep'].mean():.4f}")

    # barras de cada tipo de evento (origin_bar)
    swing_bars = {e.origin_bar for e in sw}
    disp_bars = {e.origin_bar for e in out.get("displacements", [])}
    bos_bars = {e.origin_bar for e in bo}
    choch_bars = {e.break_bar if e.break_bar is not None else e.bar_index for e in che}

    def stage_flags(break_bar):
        # presencia de evento ANTES del break (bar < break_bar) => PIT
        return [
            any(b < break_bar for b in swing_bars),
            any(b < break_bar for b in disp_bars),
            any(b < break_bar for b in bos_bars),
            any(b < break_bar for b in choch_bars),
        ]

    seq_mat = np.array([stage_flags(int(r["bar"])) for _, r in fdf.iterrows()])
    depth_flags = {k: seq_mat[:, :k].all(axis=1).astype(int) for k in range(1, len(STAGES) + 1)}

    FEAT_BASE = ["score_n", "momentum", "after_bos", "displacement", "htf_ctx_code",
                 "htf_trend_int", "cd", "break_body_ratio", "dist_to_level", "bos_age_bars", "tf_code"]
    Xb = fdf[FEAT_BASE].to_numpy(float)
    y = fdf["label_ep"].to_numpy(int)
    dt = fdf["dt"]
    order = np.argsort(dt.values)
    n = len(order)
    cut = int(n * 0.75)
    tr, te = order[:cut], order[cut:]

    results = {}
    for k in range(1, len(STAGES) + 1):
        cols = np.column_stack([Xb, depth_flags[k].reshape(-1, 1)])
        rf = RandomForestClassifier(n_estimators=300, max_depth=5, random_state=RS)
        rf.fit(cols[tr], y[tr])
        p = rf.predict_proba(cols[te])[:, 1]
        prauc = float(average_precision_score(y[te], p)) if y[te].sum() > 0 else float("nan")
        roc = float(roc_auc_score(y[te], p)) if len(set(y[te])) > 1 else float("nan")
        brier = float(brier_score_loss(y[te], p))
        results[f"depth_{k}_{STAGES[k-1]}"] = {
            "pr_auc": round(prauc, 4), "roc_auc": round(roc, 4), "brier": round(brier, 4),
            "n_test": int(len(te)), "n_test_pos": int(y[te].sum()),
            "seq_present_rate": round(float(depth_flags[k][te].mean()), 4)}
        print(f"  depth {k:2d} {STAGES[k-1]:12s} PR-AUC={prauc:.4f} ROC={roc:.4f} Brier={brier:.4f} "
              f"n_pos={int(y[te].sum())} seq_rate={depth_flags[k][te].mean():.3f}")

    base_prauc = results["depth_1_SWING"]["pr_auc"]
    for k in range(2, len(STAGES) + 1):
        name = f"depth_{k}_{STAGES[k-1]}"
        results[name]["delta_pr_auc_vs_depth1"] = round(results[name]["pr_auc"] - base_prauc, 4)

    best_k = max(results, key=lambda x: results[x]["pr_auc"])
    best_prauc = results[best_k]["pr_auc"]
    dpr = best_prauc - base_prauc
    significant = any(results[f"depth_{k}_{STAGES[k-1]}"]["delta_pr_auc_vs_depth1"] > 0.01
                      and results[f"depth_{k}_{STAGES[k-1]}"]["n_test_pos"] >= 30
                      for k in range(2, len(STAGES) + 1))
    gate = "PASS" if (dpr > 0 and significant) else "FAIL"
    gate_detail = (f"Mejor profundidad={best_k} PR-AUC={best_prauc:.4f} vs depth1={base_prauc:.4f} "
                   f"(Δ={dpr:+.4f}); ganancia incremental significativa={significant}.")

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    report = {
        "experiment_id": "EXP-007_sequential_ict",
        "block": "B1_SEQUENTIAL_ICT",
        "generated_at": datetime.datetime.utcnow().isoformat(),
        "git_commit": os.popen("git rev-parse HEAD").read().strip(),
        "universe": {"source": feat_path, "filter": "tf==M5 AND dropna", "n_events": int(len(fdf)),
                     "label": "label_ep", "label_rate": round(float(fdf["label_ep"].mean()), 4)},
        "stages_measured": STAGES,
        "stages_plan_missing": ["LIQUIDITY", "SWEEP", "FVG", "RETEST"],
        "method": "depth k = presencia acumulada de eventos 0..k ANTES del break (PIT); RF sobre [base + depth_flag]",
        "split": "temporal holdout 75/25",
        "results": results,
        "GATE_B1": {"result": gate, "detail": gate_detail, "best_depth": best_k,
                     "delta_pr_auc_vs_depth1": round(dpr, 4),
                     "criteria": "PASS iff ΔPR-AUC>0 AND ganancia incremental significativa (Δ>0.01, n_pos>=30)"},
        "limitations": [
            "HALLAZGO: tools/ no tiene liquidity/sweep/fvg/retest como Tool independientes; cadena reducida a SWING->DISPLACEMENT->BOS->CHOCH.",
            "Secuencia simplificada: presencia de evento antes del break (no cadena estricta ordenada).",
            "Universo EURUSD M5 unicamente.",
        ],
    }
    json.dump(report, open(OUT_JSON, "w"), indent=2, default=str)
    print(f"\nGATE B1: {gate}")
    print(f"  {gate_detail}")
    print(f"-> {OUT_JSON}  [{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
