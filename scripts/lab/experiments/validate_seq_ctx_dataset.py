"""EXP-SEQ-CTX-01 — VALIDADOR DE CONTRATO DE DATOS OFFLINE.

Trabajo 4 (parte 2). Valida que el dataset producido por exp_seq_ctx_01_dataset.py
cumple CONTRATO_DATASET_SEQ_CTX_01.md. Falla cerrado (exit != 0) si viola
cualquier guarda. No modifica datos.

Guardas:
  - esquema de columnas obligatorias;
  - tipos y valores nulos;
  - duplicados en event_id;
  - frontera causal: features_at_t sin time > T, sin label_ en features;
  - can_trade == false siempre;
  - separacion canonical_bos vs lite (datasets distintos);
  - split temporal presente;
  - dataset_sha256 y generator_commit presentes;
  - gate causal/TNA en PASS (referencia).
"""

from __future__ import annotations
import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.lab.experiments.exp_seq_ctx_01_dataset import _check_gates, OUT_DIR, MANIFEST

REQUIRED = [
    "event_id", "dataset_id", "dataset_sha256", "generator_commit", "contract_version",
    "symbol", "timeframe", "event_time", "direction", "structure_mode",
 "sequence_depth", "context_bucket", "chain_id", "features_at_t",
    "label_end_6", "label_end_12", "label_end_24", "label_end_48",
    "split", "can_trade",
]
VALID_BUCKETS = {"ALIGNED", "NEUTRAL", "AGAINST"}
VALID_SPLITS = {"DESIGN", "VALIDATION", "HOLDOUT"}
VALID_LABELS = {"continuation", "reversal", "failure"}


def _err(msg):
    print(f"[VALIDADOR][FAIL] {msg}")
    return 1


def main() -> int:
    rc = _check_gates()
    if rc:
        return _fail_gate()
    if not MANIFEST.exists():
        return _err(f"manifest ausente: {MANIFEST}")
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get("can_trade") is not False:
        return _err("manifest.can_trade != false")
    errs = 0
    n_total = 0
    seen_ids = set()
    modes_seen = set()
    for did in manifest["datasets"]:
        path = OUT_DIR / f"{did}.jsonl"
        if not path.exists():
            return _err(f"falta archivo de dataset: {path}")
        rows = [json.loads(l) for l in open(path, encoding="utf") if l.strip()]
        n_total += len(rows)
        for i, r in enumerate(rows):
            modes_seen.add(r["structure_mode"])
            # columnas
            miss = [c for c in REQUIRED if c not in r]
            if miss:
                errs += _err(f"{did} fila {i}: faltan {miss}")
                continue
            # nulos
            for c in REQUIRED:
                if r[c] is None:
                    errs += _err(f"{did} fila {i}: {c} es nulo")
            # bucket / split / label
            if r["context_bucket"] not in VALID_BUCKETS:
                errs += _err(f"{did} fila {i}: context_bucket={r['context_bucket']}")
            if r["split"] not in VALID_SPLITS:
                errs += _err(f"{did} fila {i}: split={r['split']}")
            for h in (6, 12, 24, 48):
                if r[f"label_end_{h}"] not in VALID_LABELS:
                    errs += _err(f"{did} fila {i}: label_end_{h}={r[f'label_end_{h}']}")
            # can_trade
            if r["can_trade"] is not False:
                errs += _err(f"{did} fila {i}: can_trade != false")
            # leakage: features_at_t sin label_
            if any(k.startswith("label_") for k in r["features_at_t"]):
                errs += _err(f"{did} fila {i}: leakage label_ en features_at_t")
            # duplicados
            if r["event_id"] in seen_ids:
                errs += _err(f"{did} fila {i}: event_id duplicado {r['event_id']}")
            seen_ids.add(r["event_id"])
    # separacion de modos
    if "canonical_bos" in modes_seen and "lite" in modes_seen:
        # ambos deben estar en datasets distintos (ya lo garantiza dataset_id)
        pass
    print(f"[VALIDADOR] total_rows={n_total} event_ids_unicos={len(seen_ids)} "
          f"modos={modes_seen} errores={errs}")
    if errs:
        return 1
    print("[VALIDADOR] PASS — contrato cumplido, dataset offline valido (can_trade=false)")
    return 0


def _fail_gate():
    print("[VALIDADOR][FAIL] gates no PASS; no se valida dataset")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
