"""EXP-SEQ-CTX-01 — CREACIÓN DE SNAPSHOT CERTIFICADO (Paso 4 de la ruta IA).

Toma los JSONL generados por exp_seq_ctx_01_dataset.py y materializa un
DatasetSnapshot certificado vía runtime/ai_learning/dataset_snapshots.py
(límite INF-2). El snapshot es SOLO una fotografía congelada y verificable
del dataset; NO entrena, NO promueve, NO autoriza edge.

Por cada modo (canonical_bos / lite):
  1. calcula hash_dataset(jsonl)  -> dataset_hash del manifest certificado;
  2. arma CertifiedExperimentManifest (verdict=PASS, code_commit, artifact_paths,
     scope, metrics, produced_at, certifier);
  3. CertifiedDatasetReader.create_snapshot(...) -> copia inmutable + metadata;
  4. read_snapshot(...) -> verifica integridad (schema_hash, row_count, hash).

El snapshot_id es estable (mismo origen + commit + config => mismo id), por lo
que re-ejecutar es idempotente y no sobrescribe uno existente.

Reglas:
  - can_trade=false en todas las filas (heredado del dataset).
  - El manifest certificado exige verdict=PASS; si los gates no pasan, falla.
  - output_dir dentro de runtime/ai_learning/snapshots/ (fuera de rutas protegidas).
"""

from __future__ import annotations
import sys, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.ai_learning.dataset_snapshots import (
    CertifiedDatasetReader,
    hash_dataset,
    load_dataset_snapshot,
)
from runtime.ai_learning.certified_artifacts import (
    CertifiedArtifactError,
    validate_certified_manifest,
)

from scripts.lab.experiments.exp_seq_ctx_01_dataset import (
    _check_gates, OUT_DIR, MANIFEST, MODES, SYMBOL, TIMEFRAME,
    CONTRACT_VERSION, _commit,
)

SNAPSHOT_ROOT = ROOT / "runtime" / "ai_learning" / "snapshots" / "seq_ctx_01"
GATE_CAUSAL = ROOT / "reports/audits/experiments/seq_ctx_01/gate_causal.json"
GATE_TNA = ROOT / "reports/audits/tna_streaming_prefix_2026-08-22.json"
CONTRACT = ROOT / "docs/contratos/CONTRATO_DATASET_SEQ_CTX_01.md"
FACTORY = ROOT / "scripts/lab/experiments/exp_seq_ctx_01_dataset.py"
SEQ_EVENTS = ROOT / "engine/sequential_events.py"
MTF_NAV = ROOT / "engine/mtf_navigation.py"
EXPERIMENT_ID = "EXP-SEQ-CTX-01"


def _rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def _source_hashes_for_manifest() -> list[str]:
    """Hashes de las fuentes relevantes para el manifest certificado."""
    return [_rel(p) for p in (FACTORY, SEQ_EVENTS, MTF_NAV, CONTRACT)]


def _check_oos_sufficiency() -> int:
    """Bloquea la frontera IA mientras el Gate OOS siga subpotenciado."""
    if not MANIFEST.exists():
        print(f"[SNAPSHOT][FAIL-CLOSED] falta manifest OOS: {MANIFEST}")
        return 1
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[SNAPSHOT][FAIL-CLOSED] manifest OOS ilegible: {exc}")
        return 1
    status = manifest.get("status")
    oos_status = manifest.get("oos_sufficiency", {}).get("status")
    if status != "OOS_SUFFICIENT" or oos_status != "SUFFICIENT":
        print(
            "[SNAPSHOT][FAIL-CLOSED] Gate OOS no suficiente: "
            f"status={status!r}, oos_sufficiency={oos_status!r}; "
            "no se crea snapshot de entrenamiento."
        )
        return 1
    return 0


def _build_manifest(mode: str, jsonl_path: Path, commit: str) -> dict:
    rows = [json.loads(l) for l in open(jsonl_path, encoding="utf") if l.strip()]
    by_split = {}
    by_bucket_split = {}
    for r in rows:
        sp = r["split"]
        by_split[sp] = by_split.get(sp, 0) + 1
        by_bucket_split.setdefault(sp, {}).setdefault(r["context_bucket"], 0)
        by_bucket_split[sp][r["context_bucket"]] = by_bucket_split[sp].get(r["context_bucket"], 0) + 1
    dataset_hash = hash_dataset(jsonl_path)
    artifact_paths = [
        _rel(jsonl_path),
        _rel(GATE_CAUSAL),
        _rel(GATE_TNA),
        _rel(CONTRACT),
        _rel(FACTORY),
        _rel(SEQ_EVENTS),
        _rel(MTF_NAV),
    ]
    # El dataset_hash del manifest certificado es el hash de BYTES del archivo
    # (lo que hash_dataset calcula); coincide con lo que create_snapshot verifica.
    payload = {
        "schema_version": "1.0",
        "experiment_id": EXPERIMENT_ID,
        "verdict": "PASS",
        "gate": {
            "causal_full_vs_prefix": "PASS",
            "tna_streaming_prefix": "PASS",
            "tna_behavioral_full_span": "UNVERIFIED",
        },
        "dataset_hash": dataset_hash,
        "code_commit": commit,
        "scope": {
            "experiment": EXPERIMENT_ID,
            "symbol": SYMBOL,
            "timeframe": TIMEFRAME,
            "structure_mode": mode,
            "contract_version": CONTRACT_VERSION,
        },
        "metrics": {
            "total_rows": len(rows),
            "by_split": by_split,
            "by_bucket_split": by_bucket_split,
            "can_trade": False,
        },
        "artifact_paths": artifact_paths,
        "produced_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "certifier": "HERMES-CEO",
    }
    return payload


def main() -> int:
    print("[SNAPSHOT] inicio EXP-SEQ-CTX-01 (Paso 4: snapshot certificado)", flush=True)
    rc = _check_gates()
    if rc:
        print("[SNAPSHOT][FAIL] gates no PASS; no se crea snapshot")
        return 1
    rc = _check_oos_sufficiency()
    if rc:
        return 1
    commit = _commit()
    if commit == "UNKNOWN":
        print("[SNAPSHOT][FAIL] commit desconocido")
        return 1

    reader = CertifiedDatasetReader(ROOT)
    created = []
    for mode in MODES:
        did = f"SEQ_CTX_01_{mode.upper()}"
        jsonl_path = OUT_DIR / f"{did}.jsonl"
        if not jsonl_path.exists():
            print(f"[SNAPSHOT][FAIL] falta {jsonl_path}")
            return 1
        manifest_payload = _build_manifest(mode, jsonl_path, commit)
        # Valida localmente antes de cruzar la frontera
        try:
            validate_certified_manifest(manifest_payload)
        except CertifiedArtifactError as exc:
            print(f"[SNAPSHOT][FAIL] manifest no certificable ({mode}): {exc}")
            return 1
        output_dir = SNAPSHOT_ROOT / mode
        config = {
            "contract_version": CONTRACT_VERSION,
            "structure_mode": mode,
            "snapshot_kind": "offline_research_only",
            "can_trade": False,
        }
        try:
            snap = reader.create_snapshot(
                manifest_payload, jsonl_path, output_dir,
                config=config, consumer_code_commit=commit,
            )
        except Exception as exc:
            print(f"[SNAPSHOT][FAIL] create_snapshot ({mode}): {exc}")
            return 1
        # Verificación de integridad del snapshot recién creado
        try:
            loaded = load_dataset_snapshot(snap.snapshot_path)
            rows = reader.read_snapshot(snap.snapshot_path)
            assert loaded.row_count == len(rows)
        except Exception as exc:
            print(f"[SNAPSHOT][FAIL] verificacion de snapshot ({mode}): {exc}")
            return 1
        created.append((mode, snap.snapshot_id, len(rows)))
        print(f"[SNAPSHOT] {mode}: snapshot={snap.snapshot_id[:16]}.. rows={len(rows)} "
              f"path={snap.snapshot_path}")

    print(f"[SNAPSHOT] PASS — {len(created)} snapshot(s) certificado(s) creados.")
    print("[SNAPSHOT] Estado: DATASET OFFLINE (can_trade=false); NO entrena, NO promueve.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
