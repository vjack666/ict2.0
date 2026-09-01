"""EXP-SEQ-CTX-01 — VALIDADOR DE CONTRATO DE DATOS OFFLINE (V2, fortalecido).

Trabajo 4 (parte 2). Valida que el dataset producido por exp_seq_ctx_01_dataset.py
cumple CONTRATO_DATASET_SEQ_CTX_01.md. Falla cerrado (exit != 0) si viola
cualquier guarda. No modifica datos.

Verificaciones (correcciones V2):
  - esquema de columnas obligatorias;
  - tipos y valores nulos;
  - duplicados en event_id (unicidad real);
  - frontera causal: features_at_t sin time > T, sin label_ en features;
  - can_trade == false siempre;
  - separacion canonical_bos vs lite (datasets distintos);
  - split temporal presente;
  - dataset_sha256 y generator_commit presentes;
  - hash canónico del payload recalculado y comparado contra manifest.datasets[did].sha256;
  - n de filas del manifest == n real del archivo;
  - by_split del manifest == conteo real por split;
  - event_id alineado con el contrato (symbol/timeframe incluidos);
  - gate causal/TNA en PASS (referencia).
"""

from __future__ import annotations
import sys, json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.lab.experiments.exp_seq_ctx_01_dataset import (
    _check_gates, OUT_DIR, MANIFEST, _event_id, _canonical_rows_hash,
    _source_hashes, CONTRACT_VERSION, context_bucket, h1_alignment,
)

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
EXPECTED_DATASETS = {"SEQ_CTX_01_CANONICAL_BOS", "SEQ_CTX_01_LITE"}


def _err(msg) -> int:
    print(f"[VALIDADOR][FAIL] {msg}")
    return 1


def _contains_forbidden_key(value) -> bool:
    if isinstance(value, dict):
        return any(str(k).startswith("label_") or _contains_forbidden_key(v)
                   for k, v in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden_key(v) for v in value)
    return False


def _as_utc_timestamp(value):
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def _feature_times_after_t(value, event_time) -> list[str]:
    """Busca timestamps explícitos anidados dentro de features_at_t."""
    violations = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key).lower()
            if key_text in {"time", "timestamp", "event_time"} or key_text.endswith("_time"):
                if isinstance(item, str):
                    try:
                        if _as_utc_timestamp(item) > event_time:
                            violations.append(f"{key}={item}")
                    except Exception:
                        violations.append(f"{key} no parseable={item}")
            violations.extend(_feature_times_after_t(item, event_time))
    elif isinstance(value, list):
        for item in value:
            violations.extend(_feature_times_after_t(item, event_time))
    return violations


def main() -> int:
    rc = _check_gates()
    if rc:
        print("[VALIDADOR][FAIL] gates no PASS; no se valida dataset")
        return 1
    if not MANIFEST.exists():
        return _err(f"manifest ausente: {MANIFEST}")
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get("can_trade") is not False:
        return _err("manifest.can_trade != false")
    if manifest.get("contract_version") != CONTRACT_VERSION:
        return _err(f"manifest.contract_version={manifest.get('contract_version')} != {CONTRACT_VERSION}")
    if set(manifest.get("datasets", {})) != EXPECTED_DATASETS:
        return _err(f"datasets esperados={EXPECTED_DATASETS}, reales={set(manifest.get('datasets', {}))}")
    if not manifest.get("generator_commit") or manifest.get("generator_commit") == "UNKNOWN":
        return _err("manifest.generator_commit ausente/desconocido")
    if not isinstance(manifest.get("generator_source_hashes"), dict):
        return _err("manifest.generator_source_hashes ausente")
    try:
        current_source_hashes = _source_hashes()
    except Exception as exc:
        return _err(f"no se pueden calcular hashes de procedencia: {exc}")
    if manifest["generator_source_hashes"] != current_source_hashes:
        return _err("generator_source_hashes no coincide con el codigo/documentacion actual")

    errs = 0
    n_total = 0
    seen_ids: set[str] = set()
    modes_seen: set[str] = set()

    for did, meta in manifest["datasets"].items():
        path = OUT_DIR / f"{did}.jsonl"
        if not path.exists():
            errs += _err(f"falta archivo de dataset: {path}")
            continue
        rows = [json.loads(l) for l in open(path, encoding="utf") if l.strip()]
        # El hash canónico excluye solo dataset_sha256 para evitar circularidad.
        real_hash = _canonical_rows_hash(rows)
        if real_hash != meta.get("sha256"):
            errs += _err(f"{did}: hash canónico {real_hash[:12]}.. != manifest {str(meta.get('sha256'))[:12]}..")
        else:
            print(f"[VALIDADOR] HASH_CANONICO {did}: MATCH ({real_hash[:12]}..)")

        # --- Punto 2: n filas manifest vs real ---
        if meta.get("rows") != len(rows):
            errs += _err(f"{did}: manifest rows={meta.get('rows')} != real={len(rows)}")
        n_total += len(rows)

        # --- Punto 2: by_split manifest vs real ---
        real_by_split: dict[str, int] = {}
        for r in rows:
            real_by_split[r["split"]] = real_by_split.get(r["split"], 0) + 1
        if meta.get("by_split") != real_by_split:
            errs += _err(f"{did}: manifest by_split={meta.get('by_split')} != real={real_by_split}")
        real_by_bucket_split = {
            split: {
                bucket: sum(1 for r in rows
                            if r.get("split") == split and r.get("context_bucket") == bucket)
                for bucket in ("ALIGNED", "NEUTRAL", "AGAINST")
            }
            for split in ("DESIGN", "VALIDATION", "HOLDOUT")
        }
        if meta.get("by_bucket_split") != real_by_bucket_split:
            errs += _err(f"{did}: manifest by_bucket_split no coincide con conteo real")

        for i, r in enumerate(rows):
            modes_seen.add(r["structure_mode"])
            miss = [c for c in REQUIRED if c not in r]
            if miss:
                errs += _err(f"{did} fila {i}: faltan {miss}")
                continue
            for c in REQUIRED:
                if r[c] is None:
                    errs += _err(f"{did} fila {i}: {c} es nulo")
            if r.get("dataset_sha256") != meta.get("sha256"):
                errs += _err(f"{did} fila {i}: dataset_sha256 no coincide con manifest")
            if r.get("generator_commit") != manifest.get("generator_commit"):
                errs += _err(f"{did} fila {i}: generator_commit no coincide con manifest")
            if r.get("dataset_id") != did:
                errs += _err(f"{did} fila {i}: dataset_id inconsistente={r.get('dataset_id')}")
            if r.get("structure_mode") not in {"canonical_bos", "lite"}:
                errs += _err(f"{did} fila {i}: structure_mode invalido={r.get('structure_mode')}")
            if did.endswith("_CANONICAL_BOS") and r.get("structure_mode") != "canonical_bos":
                errs += _err(f"{did} fila {i}: mezcla de modos")
            if did.endswith("_LITE") and r.get("structure_mode") != "lite":
                errs += _err(f"{did} fila {i}: mezcla de modos")
            if r.get("direction") not in (-1, 1):
                errs += _err(f"{did} fila {i}: direction invalida={r.get('direction')}")
            try:
                event_time = _as_utc_timestamp(r["event_time"])
            except Exception:
                errs += _err(f"{did} fila {i}: event_time no parseable={r.get('event_time')}")
                event_time = None
            if r["context_bucket"] not in VALID_BUCKETS:
                errs += _err(f"{did} fila {i}: context_bucket={r['context_bucket']}")
            if r["split"] not in VALID_SPLITS:
                errs += _err(f"{did} fila {i}: split={r['split']}")
            for h in (6, 12, 24, 48):
                if r[f"label_end_{h}"] not in VALID_LABELS:
                    errs += _err(f"{did} fila {i}: label_end_{h}={r[f'label_end_{h}']}")
            if r["can_trade"] is not False:
                errs += _err(f"{did} fila {i}: can_trade != false")
            if _contains_forbidden_key(r["features_at_t"]):
                errs += _err(f"{did} fila {i}: leakage label_ en features_at_t")
            if event_time is not None:
                for violation in _feature_times_after_t(r["features_at_t"], event_time):
                    errs += _err(f"{did} fila {i}: feature posterior a T: {violation}")
            # El bucket debe ser reconstruible desde los inputs normativos
            # guardados en la propia fila; no se acepta una etiqueta opaca.
            features = r["features_at_t"]
            inputs = features.get("context_inputs") if isinstance(features, dict) else None
            layers = features.get("context_layers") if isinstance(features, dict) else None
            if not isinstance(inputs, dict):
                errs += _err(f"{did} fila {i}: falta features_at_t.context_inputs")
                inputs = {}
            for key in ("sequence_direction", "d1_bias", "h4_location", "h1_alignment"):
                if key not in inputs or inputs[key] is None:
                    errs += _err(f"{did} fila {i}: falta context_inputs.{key}")
            if inputs.get("sequence_direction") != r.get("direction"):
                errs += _err(f"{did} fila {i}: sequence_direction != direction")
            expected_bucket = context_bucket(
                r.get("direction"), inputs.get("d1_bias"),
                inputs.get("h4_location"), inputs.get("h1_alignment"),
            )
            if r.get("context_bucket") != expected_bucket:
                errs += _err(f"{did} fila {i}: context_bucket no reconstruible ({r.get('context_bucket')} != {expected_bucket})")
            if isinstance(layers, dict):
                h1_layer = layers.get("H1") if isinstance(layers.get("H1"), dict) else {}
                expected_h1 = h1_alignment(r.get("direction"), h1_layer.get("bias"))
                if inputs.get("h1_alignment") != expected_h1:
                    errs += _err(f"{did} fila {i}: h1_alignment inconsistente con H1.bias")
            # --- Punto 4: event_id alineado con contrato (symbol/timeframe) ---
            exp = _event_id(did, r["symbol"], r["timeframe"], r["event_time"],
                            r["structure_mode"], r.get("chain_id", ""), r["sequence_depth"])
            if r["event_id"] != exp:
                errs += _err(f"{did} fila {i}: event_id={r['event_id']} != esperado {exp}")
            if r["event_id"] in seen_ids:
                errs += _err(f"{did} fila {i}: event_id duplicado {r['event_id']}")
            seen_ids.add(r["event_id"])

    if manifest.get("total_rows") != n_total:
        errs += _err(f"manifest total_rows={manifest.get('total_rows')} != real={n_total}")
    if modes_seen != {"canonical_bos", "lite"}:
        errs += _err(f"modos observados inesperados={modes_seen}")
    print(f"[VALIDADOR] total_rows={n_total} event_ids_unicos={len(seen_ids)} "
          f"modos={modes_seen}")
    if errs:
        print(f"[VALIDADOR] FAIL — {errs} error(es)")
        return 1
    print("[VALIDADOR] PASS — integridad certificada (hash/filas/splits/event_id/"
          "modos separados/can_trade=false). Dataset offline, no operativo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
