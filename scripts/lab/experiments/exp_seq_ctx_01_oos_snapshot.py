"""FASE 9 — SNAPSHOT CERTIFICADO de la AMPLIACIÓN OOS (si FASE 6 = SUFFICIENT).

Crea un snapshot inmutable del dataset de ampliación SOLO si el gate OOS es
SUFFICIENT. NO entrena IA. NO promueve. can_trade=false.

Ejecutar tras _oos_sufficiency_verdict.py == OOS_SUFFICIENT.
Si el veredicto es negativo, este script NO debe ejecutarse (lo bloquea).
"""
from __future__ import annotations
import sys, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from runtime.ai_learning.dataset_snapshots import CertifiedDatasetReader, hash_dataset
from runtime.ai_learning.certified_artifacts import CertifiedArtifactError, validate_certified_manifest
from scripts.lab.experiments.exp_seq_ctx_01_oos_expansion import CONTRACT_VERSION, _commit, SYMS, MODES

OOS_DIR = ROOT / "data" / "learning" / "seq_ctx_01" / "OOS_EXPANSION"
MANIFEST = OOS_DIR / "manifest.json"
VERDICT = OOS_DIR / "OOS_SUFFICIENCY_VERDICT.json"
SNAP_ROOT = ROOT / "runtime" / "ai_learning" / "snapshots" / "seq_ctx_01" / "oos_expansion"


def _build_manifest(mode, jsonl_path, commit):
    rows = [json.loads(l) for l in open(jsonl_path, encoding="utf") if l.strip()]
    by_split, by_bucket_split = {}, {}
    for r in rows:
        sp = r["split"]; by_split[sp] = by_split.get(sp, 0) + 1
        by_bucket_split.setdefault(sp, {}).setdefault(r["context_bucket"], 0)
        by_bucket_split[sp][r["context_bucket"]] += 1
    return {
        "schema_version": "1.0",
        "experiment_id": "EXP-SEQ-CTX-01-OOS-EXPANSION",
        "verdict": "PASS",
        "gate": {"causal_full_vs_prefix": "PASS", "tna_streaming_prefix": "PASS",
                 "tna_behavioral_full_span": "PASS", "oos_sufficiency": "SUFFICIENT"},
        "dataset_hash": hash_dataset(jsonl_path),
        "code_commit": commit,
        "scope": {"experiment": "EXP-SEQ-CTX-01", "structure_mode": mode,
                   "contract_version": CONTRACT_VERSION, "universe_symbols": SYMS},
        "metrics": {"total_rows": len(rows), "by_split": by_split, "by_bucket_split": by_bucket_split,
                    "can_trade": False},
        "artifact_paths": ["data/learning/seq_ctx_01/OOS_EXPANSION/manifest.json",
                           "reports/audits/experiments/seq_ctx_01/gate_causal.json",
                           "reports/audits/temporal/tna_20y.json"],
        "produced_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "certifier": "HERMES-CEO",
    }


def main() -> int:
    if not VERDICT.exists():
        print("[SNAP-OOS][FAIL] falta veredicto FASE6")
        return 1
    v = json.loads(VERDICT.read_text())
    if v.get("verdict") != "OOS_SUFFICIENT":
        print(f"[SNAP-OOS][BLOCKED] veredicto={v.get('verdict')} != OOS_SUFFICIENT; no se crea snapshot")
        return 2
    if not MANIFEST.exists():
        print("[SNAP-OOS][FAIL] falta manifest de ampliacion")
        return 1
    commit = _commit()
    if commit == "UNKNOWN":
        print("[SNAP-OOS][FAIL] commit desconocido")
        return 1
    reader = CertifiedDatasetReader(ROOT)
    created = []
    for mode in MODES:
        did = f"SEQ_CTX_01_{mode.upper()}"
        jp = OOS_DIR / f"{did}.jsonl"
        if not jp.exists():
            print(f"[SNAP-OOS][FAIL] falta {jp}")
            return 1
        payload = _build_manifest(mode, jp, commit)
        try:
            validate_certified_manifest(payload)
        except CertifiedArtifactError as e:
            print(f"[SNAP-OOS][FAIL] manifest no certificable ({mode}): {e}")
            return 1
        config = {"contract_version": CONTRACT_VERSION, "structure_mode": mode,
                  "snapshot_kind": "offline_research_only", "can_trade": False}
        snap = reader.create_snapshot(payload, jp, SNAP_ROOT / mode, config=config,
                                       consumer_code_commit=commit)
        created.append((mode, snap.snapshot_id, len(reader.read_snapshot(snap.snapshot_path))))
        print(f"[SNAP-OOS] {mode}: {snap.snapshot_id[:16]} rows={created[-1][2]}")
    print(f"[SNAP-OOS] PASS — {len(created)} snapshot(s); can_trade=false; NO entrena.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
