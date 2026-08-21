"""B5 — ABLATION LAB (A/B/C) — pipeline científico de aprendizaje.

Ejecuta las 7 combinaciones del plan BLOQUE 5:
    A=teacher (CHOCH RF sobre label_ep)
    B=nature  (nature_head.pt congelado -> P(bos_confirm), usado como senal auxiliar)
    C=context (logistic sobre SUBSET de features de contexto de mercado -> label_ep)
    combinaciones: A, B, C, A+B, A+C, B+C, A+B+C

Universo comun y label:
    - Eventos CHOCH EURUSD M5 de data/learning/choch/full/features.jsonl (4666 filas),
      target = label_ep (el "edge" accionable). A y C lo predicen directamente.
    - B predice bos_confirm (naturaleza) sobre un espacio de features distinto (bloque
      61x7=427). Para alinearlo al mismo universo se reconstruyen los bloques de cada
      evento M5 con build_tf_blocks y se puntua con el .pt YA ENTRENADO (congelado,
      sin re-entrenar en este dataset -> PIT correcto). Su salida P(bos_confirm) se
      usa como senal auxiliar.

Metodo de combinacion: STACKING LOGISTICO ajustado solo en TRAIN.
    Justificacion (citada en el informe): P_B es P(bos_confirm), un label DIFERENTE al
    de P_A/P_C (label_ep). Promediar probabilidades mezclaria dos labels/escalas y no
    es valido. El stacking con logistica ajustada en train mapea probabilidades
    heterogeneas de componentes al target comun label_ep, y permite medir la
    contribucion aislada y combinada de cada componente de forma honesta. Opcion
    explicitamente permitida por el plan ("stacking logístico ajustado en train").

PIT / sin look-ahead:
    - Split TEMPORAL (holdout 75/25 por tiempo) -> nunca el test ve el futuro.
    - A (RF), C (LR) y el meta (LR) se entrenan SOLO en TRAIN y se evaluan en TEST.
    - B es un modelo congelado pre-entrenado en OTRO dataset; no ve los labels de este.
    - Umbral de precision/recall = F1-optimo en TRAIN, aplicado a TEST.

OOS stability:
    - Ademas del holdout, se corre walk-forward temporal K=4 folds (train=segmentos
      previos, test=segmento k). Se reporta media +/- std de PR-AUC por combinacion.

NO hardcodea metricas: todo se mide con sklearn sobre el test set real.

Salida:
    data/learning/pipeline/experiments/EXP-006_ablation.json  (tabla + veredicto GATE 5)
"""
from __future__ import annotations
import sys, os, json, time, datetime
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ".")
sys.path.insert(0, REPO)
import numpy as np
import pandas as pd
import importlib.util as _u

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (roc_auc_score, average_precision_score,
                             brier_score_loss, precision_score, recall_score, f1_score)

# ---- paths ----
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
# NOTA: NO usar os.chdir(REPO) — rompe la resolucion del venv (sklearn) al cambiar cwd
# despues de que el interprete del venv ya cargo. El script se ejecuta desde REPO.
FEAT_JSONL = os.path.join(REPO, "data/learning/choch/full/features.jsonl")
NH_PT = os.path.join(REPO, "data/learning/encoder/nature_head.pt")
NH_NPZ = os.path.join(REPO, "data/learning/encoder/nature_head_data.npz")
OUT_JSON = os.path.join(REPO, "data/learning/pipeline/experiments/EXP-006_ablation.json")

# ---- features (AUTORIDAD = codigo b0/b3, NO la prosa de la tarea) ----
FEAT_ALL = ["score_n", "momentum", "after_bos", "displacement", "htf_ctx_code",
            "htf_trend_int", "cd", "break_body_ratio", "dist_to_level",
            "bos_age_bars", "tf_code"]
# C = contexto de mercado (features estructurales), excluye el "score" propio del CHOCH
FEAT_CONTEXT = ["after_bos", "displacement", "htf_ctx_code", "htf_trend_int",
                "break_body_ratio", "dist_to_level", "bos_age_bars", "tf_code"]
LABEL = "label_ep"
RS = 42

COMBOS = {
    "A":       ["A"],
    "B":       ["B"],
    "C":       ["C"],
    "A+B":     ["A", "B"],
    "A+C":     ["A", "C"],
    "B+C":     ["B", "C"],
    "A+B+C":   ["A", "B", "C"],
}


def _sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _load_nature_head():
    import torch
    spec = _u.spec_from_file_location("tnh_mod", os.path.join(REPO, "scripts/lab/learning/train_nature_head.py"))
    mod = _u.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ckpt = torch.load(NH_PT, weights_only=False)
    return mod, ckpt


# ----------------------------------------------------------------------------
def main():
    t0 = time.time()
    import torch  # local import so module-level load defs above are simple
    mod, ckpt = _load_nature_head()
    NatureHead = mod.NatureHead

    # ---------------- 1. cargar universo comun (EURUSD M5 CHOCH) ----------------
    rows = [json.loads(l) for l in open(FEAT_JSONL, encoding="utf-8") if l.strip()]
    df = pd.DataFrame(rows)
    df = df[df["tf"] == "M5"].copy().reset_index(drop=True)
    df["dt"] = pd.to_datetime(df["time"])
    df = df.dropna(subset=FEAT_ALL + [LABEL])
    # tipos
    for c in FEAT_ALL:
        df[c] = df[c].astype(float)
    df[LABEL] = df[LABEL].astype(int)
    print(f"[universo] EURUSD M5 CHOCH events tras dropna: {len(df)} | "
          f"label_ep rate={df[LABEL].mean():.4f} pos={int(df[LABEL].sum())}")
    print(f"[rango] {df['dt'].min()} .. {df['dt'].max()}")

    # ---------------- 2. reconstruir bloques B y puntuar nature head ----------
    from tools.block_builder import build_tf_blocks, W_PRE_DEFAULT
    evs = [{"break_bar": int(r["bar"]), "signal": r["signal"], "tf": r["tf"],
            "symbol": r["symbol"], "time": str(r["time"])}
           for _, r in df.iterrows()]
    blocks = build_tf_blocks(os.path.join(REPO, "data/raw/EURUSD/EURUSD_M5.parquet"), evs,
                             w_pre=W_PRE_DEFAULT, w_post=30)
    # mapear bloque -> fila por (bar, signal)
    key2idx = {(int(r["bar"]), r["signal"]): i for i, r in df.iterrows()}
    keep_idx, Xb = [], []
    for b in blocks:
        k = (int(b["bar"]), b["signal"])
        if k in key2idx:
            keep_idx.append(key2idx[k])
            Xb.append(np.array(b["X"], dtype=np.float32).flatten())
    Xb = np.array(Xb)  # (n, 427)
    df = df.iloc[keep_idx].reset_index(drop=True)
    print(f"[B] bloques reconstruidos y alineados: {len(df)} (de {len(evs)} eventos)")

    model = NatureHead(int(ckpt["dim"]))
    model.load_state_dict(ckpt["state"])
    model.eval()
    with torch.no_grad():
        pB_all = torch.sigmoid(model(torch.from_numpy(Xb))).numpy().astype(float)
    # pB = P(bos_confirm) para cada evento del universo alineado (frozen)

    # ---------------- 3. matrices de componentes por evento -------------------
    X_all = df[FEAT_ALL].to_numpy(float)
    Xc_all = df[FEAT_CONTEXT].to_numpy(float)
    y_all = df[LABEL].to_numpy(int)
    dt = df["dt"]

    # ---------------- 4. splits PIT -------------------------------------------
    order = np.argsort(dt.values)
    n = len(order)
    cut = int(n * 0.75)
    ho_train = order[:cut]
    ho_test = order[cut:]
    # walk-forward K folds temporales
    K = 4
    fold_bounds = np.linspace(0, n, K + 1).astype(int)
    folds = []
    for k in range(1, K + 1):
        tr = order[:fold_bounds[k - 1]]
        te = order[fold_bounds[k]:fold_bounds[k + 1]] if k < K else order[fold_bounds[k]:]
        if len(tr) >= 100 and len(te) >= 20:
            folds.append((tr, te))

    def fit_components(tr_idx):
        """Entrena A(RF) y C(LR) en tr_idx; devuelve probs TRAIN y (lazy) prediccion TEST."""
        ytr = y_all[tr_idx]
        # A
        rf = RandomForestClassifier(n_estimators=300, max_depth=5, random_state=RS)
        rf.fit(X_all[tr_idx], ytr)
        # C
        lr = LogisticRegression(max_iter=1000, class_weight="balanced")
        lr.fit(Xc_all[tr_idx], ytr)
        return rf, lr

    def comp_probs(rf, lr, idx):
        pA = rf.predict_proba(X_all[idx])[:, 1]
        pC = lr.predict_proba(Xc_all[idx])[:, 1]
        pB = pB_all[idx]
        return pA, pB, pC

    def eval_combo(pcols_train, pcols_test, ytr, yte, cols):
        """Meta logistic sobre las columnas de componentes; threshold F1-opt en train."""
        meta = LogisticRegression(max_iter=1000)  # sin class_weight -> calibracion limpia
        meta.fit(pcols_train, ytr)
        pte = meta.predict_proba(pcols_test)[:, 1]
        # umbral F1-optimo en TRAIN (PIT)
        ptr = meta.predict_proba(pcols_train)[:, 1]
        best_t, best_f1 = 0.5, -1
        for t in np.linspace(0.01, 0.99, 99):
            f1 = f1_score(ytr, (ptr >= t).astype(int)) if len(set(ytr)) > 1 else 0.0
            if f1 > best_f1:
                best_f1, best_t = f1, t
        pred = (pte >= best_t).astype(int)
        prauc = float(average_precision_score(yte, pte)) if yte.sum() > 0 else float("nan")
        roc = float(roc_auc_score(yte, pte)) if len(set(yte)) > 1 else float("nan")
        brier = float(brier_score_loss(yte, pte))
        prec = float(precision_score(yte, pred, zero_division=0))
        rec = float(recall_score(yte, pred, zero_division=0))
        return {"pr_auc": prauc, "pr_auc_vs_base": None, "roc_auc": roc,
                "brier": brier, "precision": prec, "recall": rec,
                "threshold": round(float(best_t), 3), "n_test": int(len(yte)),
                "n_test_pos": int(yte.sum())}, pte

    # ---------------- 5. HOLDOUT principal: 7 combinaciones -------------------
    rf, lr = fit_components(ho_train)
    pA_tr, pB_tr, pC_tr = comp_probs(rf, lr, ho_train)
    pA_te, pB_te, pC_te = comp_probs(rf, lr, ho_test)
    ytr, yte = y_all[ho_train], y_all[ho_test]
    comp_train = {"A": pA_tr, "B": pB_tr, "C": pC_tr}
    comp_test = {"A": pA_te, "B": pB_te, "C": pC_te}

    ho_results = {}
    for name, members in COMBOS.items():
        tr_cols = np.column_stack([comp_train[m] for m in members])
        te_cols = np.column_stack([comp_test[m] for m in members])
        res, _ = eval_combo(tr_cols, te_cols, ytr, yte, members)
        ho_results[name] = res
        print(f"  {name:6s} PR-AUC={res['pr_auc']:.4f} Brier={res['brier']:.4f} "
              f"P={res['precision']:.3f} R={res['recall']:.3f} thr={res['threshold']}")

    # ---------------- 6. WALK-FORWARD: estabilidad OOS ------------------------
    wf_pr = {name: [] for name in COMBOS}
    for fi, (tr_idx, te_idx) in enumerate(folds):
        rf, lr = fit_components(tr_idx)
        pA_tr, pB_tr, pC_tr = comp_probs(rf, lr, tr_idx)
        pA_te, pB_te, pC_te = comp_probs(rf, lr, te_idx)
        ytr, yte = y_all[tr_idx], y_all[te_idx]
        ct = {"A": pA_tr, "B": pB_tr, "C": pC_tr}
        cte = {"A": pA_te, "B": pB_te, "C": pC_te}
        for name, members in COMBOS.items():
            tr_cols = np.column_stack([ct[m] for m in members])
            te_cols = np.column_stack([cte[m] for m in members])
            res, _ = eval_combo(tr_cols, te_cols, ytr, yte, members)
            wf_pr[name].append(res["pr_auc"])
    wf_summary = {}
    for name in COMBOS:
        arr = np.array([x for x in wf_pr[name] if x == x])
        wf_summary[name] = {"mean_pr_auc": round(float(arr.mean()), 4),
                            "std_pr_auc": round(float(arr.std()), 4),
                            "n_folds": int(len(arr))}

    # ---------------- 7. deltas vs baseline aislado ---------------------------
    iso = {k: ho_results[k] for k in ["A", "B", "C"]}
    best_iso_prauc = max(iso[k]["pr_auc"] for k in iso)
    best_iso_name = max(iso, key=lambda k: iso[k]["pr_auc"])
    min_iso_brier = min(iso[k]["brier"] for k in iso)
    min_iso_name = min(iso, key=lambda k: iso[k]["brier"])

    for name, res in ho_results.items():
        res["delta_pr_auc_vs_best_isolated"] = round(res["pr_auc"] - best_iso_prauc, 4)
        res["delta_brier_vs_best_calibrated_isolated"] = round(res["brier"] - min_iso_brier, 4)
        res["delta_precision_vs_best_isolated"] = round(res["precision"] - iso[best_iso_name]["precision"], 4)
        res["delta_recall_vs_best_isolated"] = round(res["recall"] - iso[best_iso_name]["recall"], 4)

    # ---------------- 8. GATE 5 ----------------------------------------------
    best_combo = max(ho_results, key=lambda k: ho_results[k]["pr_auc"])
    best_combo_prauc = ho_results[best_combo]["pr_auc"]
    best_combo_brier = ho_results[best_combo]["brier"]
    dpr = best_combo_prauc - best_iso_prauc
    dbrier = best_combo_brier - min_iso_brier
    pass_pr = dpr > 0
    pass_cal = dbrier <= 0  # calibration no degrada
    gate = "PASS" if (pass_pr and pass_cal) else "FAIL"
    gate_detail = (f"Mejor combinacion={best_combo} PR-AUC={best_combo_prauc:.4f} vs "
                   f"mejor aislado {best_iso_name}={best_iso_prauc:.4f} (ΔPR-AUC={dpr:+.4f}); "
                   f"Brier={best_combo_brier:.4f} vs mejor calibrado {min_iso_name}={min_iso_brier:.4f} "
                   f"(ΔBrier={dbrier:+.4f}). PR-supera={pass_pr}, calib-no-degrada={pass_cal}.")

    # ---------------- 9. guardar EXP-006 --------------------------------------
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    report = {
        "experiment_id": "EXP-006_ablation",
        "block": "B5_ABLATION_LAB",
        "generated_at": datetime.datetime.utcnow().isoformat(),
        "git_commit": os.popen("git rev-parse HEAD").read().strip(),
        "branch": os.popen("git rev-parse --abbrev-ref HEAD").read().strip(),
        "universe": {
            "source": FEAT_JSONL,
            "filter": "tf=='M5' AND dropna(FEAT_ALL+label_ep) AND block rebuilt & aligned",
            "n_events": int(len(df)),
            "label": LABEL,
            "label_rate": round(float(df[LABEL].mean()), 4),
            "label_pos": int(df[LABEL].sum()),
            "time_range": [str(df["dt"].min()), str(df["dt"].max())],
        },
        "components": {
            "A": {"name": "teacher CHOCH", "model": "RandomForest(300,max_depth=5,rs=42)",
                  "features": FEAT_ALL, "target": LABEL,
                  "trained_on": "TRAIN split (PIT)"},
            "B": {"name": "nature head", "model": "nature_head.pt (frozen, loaded)",
                  "input": "block 61x7=427 rebuilt via build_tf_blocks",
                  "target_original": "bos_confirm", "used_as": "auxiliary signal P(bos_confirm)",
                  "trained_on": "external dataset (frozen; not retrained here)"},
            "C": {"name": "context", "model": "LogisticRegression(balanced,max_iter=1000)",
                  "features": FEAT_CONTEXT, "target": LABEL,
                  "trained_on": "TRAIN split (PIT)"},
        },
        "combination_method": "stacking logistic (LogisticRegression, no class_weight) "
                              "fitted ONLY on TRAIN; evaluated on TEST. Chosen over probability "
                              "averaging because P_B is P(bos_confirm) (different label/scale than "
                              "P_A/P_C=label_ep); averaging would mix labels. Threshold= F1-optimal "
                              "on TRAIN applied to TEST.",
        "split": {
            "method": "temporal holdout 75/25 by event time (PIT, no look-ahead)",
            "n_train": int(len(ho_train)), "n_test": int(len(ho_test)),
            "walk_forward": f"K={K} temporal folds for OOS stability",
        },
        "holdout_metrics": ho_results,
        "walk_forward_stability": wf_summary,
        "baseline_isolated": {"best_pr_auc": {best_iso_name: round(best_iso_prauc, 4)},
                              "best_calibrated_brier": {min_iso_name: round(min_iso_brier, 4)}},
        "GATE_5": {
            "result": gate,
            "detail": gate_detail,
            "best_combo": best_combo,
            "delta_pr_auc_vs_best_isolated": round(dpr, 4),
            "delta_brier_vs_best_calibrated_isolated": round(dbrier, 4),
            "criteria": "PASS iff ΔPR-AUC>0 AND calibration no degrada (ΔBrier<=0)",
        },
        "artifacts": {"script": "scripts/lab/learning/b5_ablation.py",
                      "nature_head_pt": NH_PT, "nature_head_npz": NH_NPZ},
        "limitations": [
            "B (nature head) predice bos_confirm en un espacio de features distinto; se usa como senal "
            "auxiliar sobre el universo M5, no como predictor directo de label_ep.",
            "Universo restringido a EURUSD M5 (B entrenado solo en M5; H4/D1 estarian fuera de distribucion).",
            "Stability medida con K=4 walk-forward temporal, no el esquema completo de B3 (costo).",
            "No se modifico audit_state.json ni archivos fuera del perimetro B5.",
        ],
    }
    json.dump(report, open(OUT_JSON, "w"), indent=2, default=str)

    print(f"\n[WF stability] PR-AUC media +/- std por combinacion:")
    for name in COMBOS:
        s = wf_summary[name]
        print(f"  {name:6s} {s['mean_pr_auc']:.4f} +/- {s['std_pr_auc']:.4f} (n={s['n_folds']})")
    print(f"\nGATE 5: {gate}")
    print(f"  {gate_detail}")
    print(f"-> {OUT_JSON}  [{time.time()-t0:.0f}s]")


if __name__ == "__main__":
    main()
