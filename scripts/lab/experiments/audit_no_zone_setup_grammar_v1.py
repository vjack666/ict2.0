#!/usr/bin/env python3
"""Audit NO_ZONE rows in SETUP_GRAMMAR_DATASET_V1.

This is a read-only audit. It does not relabel rows, invent zones, train a
model, run MT5, or authorize trading.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent.parent.parent  # raíz del repo (3 niveles desde scripts/lab/experiments/).parent  # raíz del repo (scripts/lab/experiments/ → 3 niveles arriba)  # raíz del repo (3 niveles desde scripts/lab/experiments/).parent  # raíz del repo (scripts/lab/experiments/ → 3 niveles arriba)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.market_features import build_features
from scripts.lab.experiments.materialize_setup_grammar_dataset_v1 import (  # noqa: E402
    _exec_source_for_time,
    load_exec_tf_sources,
)


DATASET_DIR = ROOT / "data/ml/tensorflow/setup_grammar_v1"
SOURCE_FILES = [
    ROOT / "data/learning/seq_ctx_01/SEQ_CTX_01_CANONICAL_BOS.jsonl",
    ROOT / "data/learning/seq_ctx_01/SEQ_CTX_01_LITE.jsonl",
]
REPORT_DIR = ROOT / "reports/audits/experiments/ai"
REPORT_MD = REPORT_DIR / "setup_grammar_no_zone_audit_v1.md"
REPORT_JSON = REPORT_DIR / "setup_grammar_no_zone_audit_v1.json"

ZONE_STAGES = {"FVG", "OB", "BPR", "BREAKER", "MITIGATION", "MITIGATION_BLOCK", "REJECTION", "LIQUIDITY_VOID"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_dataset_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for filename in ["dataset_train.jsonl", "dataset_validation.jsonl", "dataset_test_oos.jsonl"]:
        rows.extend(load_jsonl(DATASET_DIR / filename))
    return rows


def load_source_rows() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in SOURCE_FILES:
        for row in load_jsonl(path):
            row["_source_file"] = str(path.relative_to(ROOT))
            rows[str(row["event_id"])] = row
    return rows


def sequence(row: dict[str, Any]) -> list[str]:
    return [str(item).upper() for item in ((row.get("features_at_t") or {}).get("sequence") or [])]


def has_zone_stage(row: dict[str, Any]) -> bool:
    return bool(set(sequence(row)) & ZONE_STAGES)


def m15_geometry_probe(row: dict[str, Any], sources: list[dict[str, Any]]) -> dict[str, Any]:
    decision_time = pd.to_datetime(row.get("decision_time"), utc=True, errors="coerce")
    if pd.isna(decision_time):
        return {"status": "NO_DECISION_TIME"}
    source = _exec_source_for_time(sources, decision_time)
    if source is None:
        return {"status": "NO_LOCAL_M15_SOURCE"}
    frame = source["frame"]
    past = frame.loc[frame["time"] <= decision_time].tail(120).reset_index(drop=True)
    if len(past) < 20:
        return {"status": "INSUFFICIENT_M15_CONTEXT", "source": source["path"], "bars": int(len(past))}
    features = build_features(past, include_liquidity_zones=False)
    recent = features.tail(20)
    direction = int(((row.get("features_at_t") or {}).get("context_inputs") or {}).get("sequence_direction", 0) or 0)
    fvg_bull = bool(recent["fvg_bullish"].fillna(False).any())
    fvg_bear = bool(recent["fvg_bearish"].fillna(False).any())
    ob_bull = bool(recent["ob_bullish"].fillna(False).any())
    ob_bear = bool(recent["ob_bearish"].fillna(False).any())
    directional = (
        (direction > 0 and (fvg_bull or ob_bull))
        or (direction < 0 and (fvg_bear or ob_bear))
    )
    return {
        "status": "M15_GEOMETRY_PROBED",
        "source": source["path"],
        "bars": int(len(past)),
        "recent_window_bars": 20,
        "any_fvg_or_ob": bool(fvg_bull or fvg_bear or ob_bull or ob_bear),
        "directional_fvg_or_ob": bool(directional),
        "fvg_bullish": fvg_bull,
        "fvg_bearish": fvg_bear,
        "ob_bullish": ob_bull,
        "ob_bearish": ob_bear,
    }


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    dataset_rows = load_dataset_rows()
    source_by_id = load_source_rows()
    sources = load_exec_tf_sources()

    chains: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source_row in source_by_id.values():
        chains[str(source_row.get("chain_id", ""))].append(source_row)
    for rows in chains.values():
        rows.sort(key=lambda item: str(item.get("event_time", "")))

    no_zone_rows = [row for row in dataset_rows if row["grammar_labels"]["pd_array_zone"] == "NO_ZONE"]
    audits: list[dict[str, Any]] = []
    for row in no_zone_rows:
        source_row = source_by_id.get(str(row["event_id"]), {})
        chain_id = str(source_row.get("chain_id", ""))
        chain_rows = chains.get(chain_id, [])
        decision_time = str(row.get("decision_time", ""))
        future_zone_rows = [
            item for item in chain_rows
            if str(item.get("event_time", "")) > decision_time and has_zone_stage(item)
        ]
        source_seq_has_zone = has_zone_stage(source_row)
        m15_probe = m15_geometry_probe(row, sources)
        if source_seq_has_zone:
            verdict = "POSSIBLE_LABELING_ERROR_SOURCE_SEQUENCE_HAS_ZONE"
        elif m15_probe.get("directional_fvg_or_ob"):
            verdict = "REVIEW_M15_DIRECTIONAL_GEOMETRY_PRESENT"
        elif m15_probe.get("any_fvg_or_ob"):
            verdict = "REVIEW_M15_OPPOSITE_OR_NEUTRAL_GEOMETRY_PRESENT"
        elif future_zone_rows:
            verdict = "VALID_PRE_ZONE_WAIT_STATE_FUTURE_ZONE_NOT_CAUSAL"
        else:
            verdict = "VALID_NO_ZONE_NO_PD_ARRAY_EVIDENCE"
        audits.append({
            "event_id": row["event_id"],
            "split": row["split"],
            "decision_time": row["decision_time"],
            "chain_id": chain_id,
            "source_file": source_row.get("_source_file"),
            "source_sequence": sequence(source_row),
            "source_sequence_has_zone": source_seq_has_zone,
            "future_same_chain_zone_count": len(future_zone_rows),
            "first_future_zone_time": future_zone_rows[0].get("event_time") if future_zone_rows else None,
            "m15_geometry_probe": m15_probe,
            "verdict": verdict,
            "can_trade": False,
        })

    summary = {
        "schema_version": "SETUP_GRAMMAR_NO_ZONE_AUDIT_V1",
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "can_trade": False,
        "total_rows": len(dataset_rows),
        "no_zone_rows": len(no_zone_rows),
        "no_zone_rate": len(no_zone_rows) / len(dataset_rows) if dataset_rows else 0.0,
        "no_zone_by_split": dict(Counter(row["split"] for row in no_zone_rows)),
        "verdict_counts": dict(Counter(item["verdict"] for item in audits)),
        "source_sequence_zone_present_count": sum(1 for item in audits if item["source_sequence_has_zone"]),
        "future_same_chain_zone_count": sum(1 for item in audits if item["future_same_chain_zone_count"] > 0),
        "m15_directional_geometry_present_count": sum(1 for item in audits if item["m15_geometry_probe"].get("directional_fvg_or_ob")),
        "m15_any_geometry_present_count": sum(1 for item in audits if item["m15_geometry_probe"].get("any_fvg_or_ob")),
        "thesis_comparison": {
            "poi_requires_pd_array": "21_POI.md §0: POI is a PD Array such as OB/FVG/BPR in the correct context.",
            "zone_layer_rule": "18_EJECUCION_OPTIMA_TF_SL_ENTRY.md §0-2: HTF gives bias, ITF marks zone, exec TF triggers.",
            "no_invention_rule": "If source sequence has no PD Array, NO_ZONE is valid unless a causal local detector proves a PD Array requiring semantic review.",
        },
        "audits": audits,
    }
    REPORT_JSON.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Setup Grammar NO_ZONE Audit v1",
        "",
        "**Estado:** `REVIEW`",
        "**Trading:** `can_trade=false`",
        "",
        "## Pregunta",
        "",
        "Verificar si las filas `NO_ZONE` son errores de lectura de mercado o si realmente no habia PD Array causal disponible en la tesis/materializacion.",
        "",
        "## Reglas de tesis usadas",
        "",
        "- `21_POI.md`: un POI valido debe ser un PD Array, como OB/FVG/BPR, en contexto correcto; no cualquier geometria suelta.",
        "- `18_EJECUCION_OPTIMA_TF_SL_ENTRY.md`: lectura top-down; HTF da sesgo, ITF marca zona, exec TF dispara.",
        "- No se inventa zona: si la secuencia causal no trae PD Array, se mantiene `NO_ZONE` salvo que otra evidencia local cerrada lo marque para revision.",
        "",
        "## Conteos",
        "",
        f"- Total filas: `{summary['total_rows']}`",
        f"- NO_ZONE: `{summary['no_zone_rows']}` (`{summary['no_zone_rate']:.2%}`)",
    ]
    for split, count in sorted(summary["no_zone_by_split"].items()):
        lines.append(f"- {split}: `{count}`")
    lines.extend([
        "",
        "## Dictamen por categoria",
        "",
    ])
    for verdict, count in sorted(summary["verdict_counts"].items()):
        lines.append(f"- `{verdict}`: `{count}`")
    lines.extend([
        "",
        "## Lectura",
        "",
        f"- Filas `NO_ZONE` cuya secuencia fuente ya tenia FVG/OB/BPR/etc.: `{summary['source_sequence_zone_present_count']}`.",
        f"- Filas `NO_ZONE` donde la misma cadena tuvo zona despues: `{summary['future_same_chain_zone_count']}`. Eso no puede usarse para cambiar la etiqueta en el tiempo de decision porque seria futuro.",
        f"- Filas con geometria M15 direccional reciente que requieren revision semantica: `{summary['m15_directional_geometry_present_count']}`.",
        f"- Filas con cualquier geometria M15 reciente: `{summary['m15_any_geometry_present_count']}`.",
        "",
        "## Conclusión",
        "",
        "El auditor no promueve ninguna fila `NO_ZONE` a zona valida. Cuando detecta geometria M15, la marca como `REVIEW`, porque la tesis exige contexto, sesgo, zona correcta y respaldo institucional. La siguiente correccion segura es materializar PD Arrays semanticos M15/ITF y compararlos contra estas filas.",
        "",
    ])
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "audits"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
