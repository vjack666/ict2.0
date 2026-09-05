"""
EXTRACTOR V2 — LOCAL_ONLY, DIAGNOSTIC_ONLY, read-only sobre datos locales.
No usa MT5 operativo. No modifica engine/ ni archivos raw.
Basado en contrato V1 (Dukascopy histórico) + snapshot V2 del motor (read-only).
Defaults provisionales autorizados:
  - Fuente: Dukascopy histórico local (datos guardados en datasets/)
  - Target: label_end_6
  - Clases: continuation, reversal, failure
  - Split temporal: 60/20/20 (TRAIN/VALIDATION/TEST_OOS) cronológico
  - Modelo seleccionado con VALIDATION, evaluado 1 vez con TEST_OOS
  - can_trade=false, shadow_mode=true, no edge, no promoción
  - Si no hay soporte suficiente por clase: BLOCKED_INSUFFICIENT_CLASS_SUPPORT
"""
from __future__ import annotations
import json, hashlib, os
from pathlib import Path
from typing import Any, Mapping, Optional
from datetime import datetime

# Confirmar defaults autorizados
SOURCE_AUTHORIZED = "historico_dukascopy_local"
TARGET_AUTHORIZED = "label_end_6"
CLASSES_AUTHORIZED = ("continuation", "reversal", "failure")
SPLIT = {"TRAIN": 0.6, "VALIDATION": 0.2, "TEST_OOS": 0.2}
CAN_TRADE = False  # DIAGNOSTIC_ONLY; nunca true
SHADOW_MODE = True
DIAGNOSTIC_ONLY = True


def audit_source_manifest(data_dir: Path) -> dict:
    """Inventario de datos locales (read-only, no modifica archivos)."""
    manifest = {
        "source": SOURCE_AUTHORIZED,
        "audit_time": datetime.utcnow().isoformat(),
        "files": {},
        "note": ("Datos Dukascopy locales guardados; MT5 operativo "
                 "reservado para evaluación futura Shadow Mode (no se usa para entrenar)."),
    }
    # Confirmar presencia de los datasets conocidos
    for sub in ("eurusd_dukascopy_intraday_2006_2010",
                "eurusd_dukascopy_intraday_2011_2020",
                "eurusd_dukascopy_intraday_2021_2025"):
        p = data_dir / sub
        manifest["files"][sub] = {"exists": p.is_dir(), "read_only": True}
    return manifest


def build_v2_row(record: Mapping[str, Any], snapshot_path: Optional[str]) -> dict:
    """
    Construir fila V2 con features_at_t real del snapshot.
    Fallo cerrado si no es engine_v2.
    """
    from scripts.lab.experiments.ai_outcome_v2_adapter import AdapterError
    features = record.get("features_at_t", {})
    if not isinstance(features, Mapping) or not features:
        raise AdapterError("v2 extractor: record lacks features_at_t (causal failure, R3)")
    if features.get("schema_group") != "engine_v2":
        # Si es V1 (schema_group=MISSING o diferente), no inventamos V2
        raise AdapterError(
            f"v2 extractor: schema_group must be 'engine_v2', got {features.get('schema_group')!r}; "
            f"no synthetic conversion from V1 is permitted (R3, RECOVERY.md)"
        )
    # Verificar tri-state (G6 MANDATORY PASS)
    perms = features.get("permissions", {})
    for k in ("allow_long", "allow_short"):
        val = perms.get(k)
        if val not in (True, False, None):
            raise AdapterError(f"tri-state violation: permissions.{k}={val!r}")
    # Verificar campos prohibidos (G9 ANTI-LEAKAGE)
    forbidden_tokens = {
        "label", "outcome", "exit", "future", "pnl", "profit", "entry", "sl", "tp",
        "stop", "target", "bars_held", "result", "profitloss",
    }
    def check(name: str):
        parts = set(p.lower() for p in name.replace("=", "_").split("_"))
        if parts & forbidden_tokens:
            raise AdapterError(f"forbidden field detected: {name}")

    def walk(obj, prefix=""):
        if isinstance(obj, Mapping):
            for k, v in obj.items():
                full = f"{prefix}.{k}" if prefix else k
                check(full)
                walk(v, full)
        elif isinstance(obj, (list, tuple)):
            for i, v in enumerate(obj):
                walk(v, f"{prefix}[{i}]")

    walk(features.get("context_state", {}), "context_state")
    walk(features.get("zones", {}), "zones")
    # No crear datos sintéticos; conservar los valores reales del record
    result = {
        "episode_id": record.get("episode_id") or record.get("canonical_setup_key", "UNKNOWN"),
        "decision_time": record.get("decision_time") or record.get("time"),
        "label": record.get("label"),  # El label se registra, no se usa como feature
        "label_end_time": record.get("label_end_time"),
        "features_at_t": dict(features),
        "lineage": {
            "depth": record.get("lineage_depth", 0),
            "count": record.get("lineage_count", 0),
        },
        "can_trade": CAN_TRADE,
        "shadow_mode": SHADOW_MODE,
        "diagnostic_only": DIAGNOSTIC_ONLY,
        "source_auth": SOURCE_AUTHORIZED,
        "target": TARGET_AUTHORIZED,
        "rejected": False,
    }
    # Rechazar si falta label
    if result["label"] is None:
        result["rejected"] = True
    return result, result["rejected"]
