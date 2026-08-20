"""P4 — Etiqueta HUMANO SINTETICO (teacher labeling) sobre los 226k eventos.

Objetivo del usuario: NO clasificar a mano los eventos cuyo human_score esta
en null. En su lugar, el "humano" (tools/teacher_rubric.py = rúbrica ICT de
sus .md) califica cada CHOCH y escribe human_score en la data.

Flujo eficiente (no re-corre detectores):
  - Lee data/learning/choch/<mes>/features.jsonl  (YA trae momentum, after_bos,
    displacement, htf_ctx_code, htf_trend_int, break_body_ratio, tf_code, cd,
    real, signal). Esas columnas son los inputs de la rúbrica.
  - Aplica tools/teacher_rubric.score_rubric -> human_score 0-100 + clase.
  - Vuelca data/learning/choch/<mes>/labels_human.jsonl
    {event_id, tf, time, signal, human_score, human_class, reason, ...} y
    actualiza el resumen con la distribucion de human_score.

Esto cumple el contrato de tools/base.py (human_score lleno) SIN que el
usuario edite ningun .md a mano.

Sobre el "modelo que aprende como humano" (F5): este script produce las
ETIQUETAS de entrenamiento. Luego scripts/train_human_model.py entrena un
modelo que imita estas etiquetas usando el embedding del encoder (P2) +
features de rúbrica. Ese modelo es el que finalmente califica "como humano"
en inferencia, sin necesitar la rúbrica en produccion.

NO requiere torch. Requiere pandas/numpy (venv repo).
"""
from __future__ import annotations

import sys
import os
import json
import glob

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from tools.teacher_rubric import RubricInput, score_rubric

CHOCH_DIR = "data/learning/choch"


def _ctx_from_code(code: int) -> str:
    return {0: "contra", 1: "neutral", 2: "a_favor"}.get(int(code), "neutral")


def label_file(features_path: str, htf_ctx: str = "neutral") -> tuple[str, dict]:
    """Procesa un features.jsonl -> labels_human.jsonl. Devuelve ruta out.
    htf_ctx: sesgo HTF jerarquico del mes (Fase 5: build_daily_bias)."""
    rows = [json.loads(l) for l in open(features_path, encoding="utf-8") if l.strip()]
    out_rows = []
    for r in rows:
        signal = r.get("signal")
        cd = int(r.get("cd", 0))
        # F5: el sesgo jerarquico compuesto (D1 raiz) manda sobre htf_ctx_code
        # por evento, para alineacion real con la estructura mayor (SPEC §47).
        inp = RubricInput(
            signal=signal,
            choch_real=bool(int(r.get("real", 0))),
            momentum=bool(int(r.get("momentum", 0))),
            after_bos=bool(int(r.get("after_bos", 0))),
            displacement=bool(int(r.get("displacement", 0))),
            body_ratio=float(r.get("break_body_ratio", 0.0) or 0.0),
            htf_ctx=htf_ctx,
            reclaimed=False,  # el features no trae reclaim; extensible
            conf_fill={
                "mtf_align": htf_ctx == "a_favor",
                "displacement": bool(int(r.get("displacement", 0))),
                "bos_afavor": bool(int(r.get("after_bos", 0))),
                "choch_afavor": True,
            },
            killzone=False,
        )
        out = score_rubric(inp)
        out_rows.append({
            "tf": r.get("tf"),
            "time": r.get("time"),
            "signal": signal,
            "cd": cd,
            "real": int(r.get("real", 0)),
            "human_score": out.human_score,
            "human_class": out.klass,
            "breakdown": out.breakdown,
        })

    out_path = os.path.join(os.path.dirname(features_path), "labels_human.jsonl")
    with open(out_path, "w", encoding="utf-8") as f:
        for o in out_rows:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")

    # resumen de distribucion
    scores = [o["human_score"] for o in out_rows]
    classes = [o["human_class"] for o in out_rows]
    summ = {
        "source": features_path,
        "n": len(out_rows),
        "mean_human_score": round(float(np.mean(scores)), 2),
        "class_counts": {c: int(classes.count(c)) for c in ("premium", "useful", "noise")},
        "pct_premium": round(100.0 * classes.count("premium") / max(1, len(classes)), 1),
        "pct_useful": round(100.0 * classes.count("useful") / max(1, len(classes)), 1),
        "pct_noise": round(100.0 * classes.count("noise") / max(1, len(classes)), 1),
    }
    summ_path = os.path.join(os.path.dirname(features_path), "labels_human_summary.json")
    with open(summ_path, "w", encoding="utf-8") as f:
        json.dump(summ, f, indent=2)
    return out_path, summ


def label_bos_file(features_path: str, htf_ctx: str = "neutral") -> tuple[str, dict]:
    """Procesa features.jsonl de BOS -> labels_human.jsonl usando score_bos_rubric.
    htf_ctx: sesgo HTF jerarquico del mes (Fase 5: build_daily_bias)."""
    from tools.teacher_rubric import BosRubricInput, score_bos_rubric
    rows = [json.loads(l) for l in open(features_path, encoding="utf-8") if l.strip()]
    out_rows = []
    for r in rows:
        inp = BosRubricInput(
            signal=r.get("signal"),
            displacement_prev=bool(r.get("displacement_prev", False)),
            body_ratio=float(r.get("body_ratio", 0.0) or 0.0),
            dist_to_level=float(r.get("dist_to_level", 0.0) or 0.0),
            confirmed=bool(r.get("confirmed", False)),
            status=r.get("status", "active"),
            htf_ctx=htf_ctx,  # F5: sesgo jerarquico real, no neutral
        )
        out = score_bos_rubric(inp)
        out_rows.append({
            "tf": r.get("tf"), "time": r.get("time"), "signal": r.get("signal"),
            "cd": int(r.get("cd", 0)), "status": inp.status,
            "human_score": out.human_score, "human_class": out.klass,
            "breakdown": out.breakdown,
        })
    out_path = os.path.join(os.path.dirname(features_path), "labels_human.jsonl")
    with open(out_path, "w", encoding="utf-8") as f:
        for o in out_rows:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
    scores = [o["human_score"] for o in out_rows]
    classes = [o["human_class"] for o in out_rows]
    summ = {
        "source": features_path, "n": len(out_rows),
        "mean_human_score": round(float(np.mean(scores)), 2),
        "class_counts": {c: int(classes.count(c)) for c in ("premium", "useful", "noise")},
    }
    summ_path = os.path.join(os.path.dirname(features_path), "labels_human_summary.json")
    with open(summ_path, "w", encoding="utf-8") as f:
        json.dump(summ, f, indent=2)
    return out_path, summ


def main():
    # --- Fase 5: sesgo HTF jerarquico del mes (D1 raiz, SPEC §43/§47) ---
    htf_ctx = "neutral"
    try:
        from engine.bias_from_tools import build_daily_bias
        bias = build_daily_bias(symbol="EURUSD", month="2026-08")
        d = bias.get("direction", "RANGING")
        htf_ctx = {"BULLISH": "a_favor", "BEARISH": "contra"}.get(d, "neutral")
        print(f"FASE 5: sesgo HTF jerarquico 2026-08 = {d} (htf_ctx={htf_ctx})")
    except Exception as e:
        print(f"FASE 5: no se pudo calcular bias HTF ({e}); usando neutral")

    # --- CHOCH (ya generado por gen_choch_dataset) ---
    choch_feats = [f for f in glob.glob(os.path.join(CHOCH_DIR, "**", "features.jsonl"), recursive=True)
                   if "labels_human" not in f]
    if choch_feats:
        print(f"CHOCH: {len(choch_feats)} features.jsonl")
        for fp in choch_feats:
            out_path, summ = label_file(fp, htf_ctx=htf_ctx)
            print(f"  {fp}\n    -> {out_path}\n    {json.dumps(summ)}")

    # --- BOS (features generados por scripts/gen_bos_dataset.py) ---
    bos_dir = "data/learning/bos"
    bos_feats = [f for f in glob.glob(os.path.join(bos_dir, "**", "features.jsonl"), recursive=True)
                 if "labels_human" not in f]
    if bos_feats:
        print(f"\nBOS: {len(bos_feats)} features.jsonl")
        for fp in bos_feats:
            out_path, summ = label_bos_file(fp, htf_ctx=htf_ctx)
            print(f"  {fp}\n    -> {out_path}\n    {json.dumps(summ)}")
    else:
        print("\nBOS: no hay features.jsonl. Corre scripts/gen_bos_dataset.py primero.")

    # --- SWING: primitivo, NO se califica como humano ---
    # (ICT_RULEBOOK §1 / SPEC §8: HH/HL/LH/LL son la pieza primaria, no un setup.
    #  Se les da metadatos via tools/swing_state.py, no human_score de juicio.)
    #  Marcamos explicitamente N/A para cerrar la "solicitud de verificacion".
    swing_dir = "data/learning/swing"
    sw_files = sorted(glob.glob(os.path.join(swing_dir, "*.jsonl")))
    if sw_files:
        n_sw = 0
        na_path = os.path.join(swing_dir, "labels_human_NA.jsonl")
        with open(na_path, "w", encoding="utf-8") as f:
            for fp in sw_files:
                for l in open(fp, encoding="utf-8"):
                    l = l.strip()
                    if not l:
                        continue
                    r = json.loads(l)
                    n_sw += 1
                    f.write(json.dumps({
                        "id": r.get("id"), "tf": r.get("tf"), "signal": r.get("signal"),
                        "time": r.get("time"),
                        "human_score": None,
                        "human_class": "N/A_PRIMITIVO",
                        "reason": "swing es pieza primaria (HH/HL/LH/LL); no es setup. Metadatos via swing_state.",
                    }, ensure_ascii=False) + "\n")
        print(f"\nSWING: {n_sw} eventos marcados N/A_PRIMITIVO -> {na_path}")
        print("  (no se califica; se usa tools/swing_state.py para fresh/tested/mitigated)")


if __name__ == "__main__":
    main()
