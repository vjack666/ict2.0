"""Read-only multimodel audit for ABSTAIN and REJECT setup-grammar rows.

This is a parallel diagnostic classification. It never writes back to the
dataset, never changes original grammar labels, and never grants trade or
entry authority.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from detectors.fvg import detect_fvg
from detectors.liquidity_context import canonical_sweep
from detectors.ob import detect_order_blocks
from engine.killzone import killzone_en
from engine.silver_bullet import is_silver_bullet
from engine.turtle_soup import is_turtle_soup
from scripts.lab.experiments.execution_calibration_preflight_v2 import (
    SPLIT_FILES,
    as_utc,
    normalize_source,
    source_path,
)


DATASET_DIR = ROOT / "data" / "ml" / "tensorflow" / "setup_grammar_v1"
REPORT_DIR = ROOT / "reports" / "audits" / "experiments" / "ai"
ROWS_PATH = REPORT_DIR / "setup_grammar_multimodel_audit_v1.jsonl"
REPORT_PATH = REPORT_DIR / "setup_grammar_multimodel_audit_v1.md"
SWEEP_TO_DECISION_BARS = 20
# 200 M15 bars cover more than two trading days: enough for prior-day
# Turtle levels, the 20-bar canonical sweep, and post-sweep structure.
CONTEXT_BARS = 200


def load_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for split, filename in SPLIT_FILES.items():
        with (DATASET_DIR / filename).open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                row["_split_name"] = split
                if (row.get("grammar_labels") or {}).get("setup_decision") in {"ABSTAIN", "REJECT"}:
                    rows.append(row)
    return rows


def latest_sweep(swept):
    flags = swept["liquidity_sweep_down"] | swept["liquidity_sweep_up"]
    candidates = swept.index[flags].tolist()
    if not candidates:
        return None
    index = candidates[-1]
    if len(swept) - 1 - index > SWEEP_TO_DECISION_BARS:
        return None
    return index


def zone_after_sweep(fvg, ob, sweep_index: int | None) -> tuple[bool, bool]:
    if sweep_index is None:
        return False, False
    after = slice(sweep_index + 1, None)
    return bool((fvg.loc[after, "fvg_bullish"] | fvg.loc[after, "fvg_bearish"]).any()), bool((ob.loc[after, "ob_bullish"] | ob.loc[after, "ob_bearish"]).any())


def classify_row(row: dict[str, Any], source_cache: dict[Path, dict[str, Any]]) -> dict[str, Any]:
    labels = row.get("grammar_labels") or {}
    context = (row.get("features_at_t") or {}).get("context_inputs") or {}
    decision = as_utc(row.get("decision_time"))
    direction = int(context.get("sequence_direction", 0) or 0)
    path = source_path(row)
    base = {
        "event_id": row.get("event_id"),
        "split": row.get("_split_name"),
        "original_label": labels.get("setup_decision"),
        "original_weak_link": labels.get("weak_link"),
        "decision_time": decision.isoformat() if decision is not None else None,
        "symbol": row.get("symbol"),
        "direction": direction,
        "can_trade": False,
        "entry_authorized": False,
        "families": {},
    }
    if path is None or path not in source_cache or decision is None or direction not in (-1, 1):
        base["audit_status"] = "EVIDENCE_MISSING"
        return base
    source = source_cache[path]
    closed = source.loc[source["time"] <= decision].tail(CONTEXT_BARS).reset_index(drop=True)
    if len(closed) < 21:
        base["audit_status"] = "EVIDENCE_MISSING"
        return base
    swept = canonical_sweep(closed)
    fvg = detect_fvg(closed)
    ob = detect_order_blocks(closed)
    sweep_index = latest_sweep(swept)
    sweep_time = None if sweep_index is None else swept.iloc[sweep_index]["time"]
    sweep_direction = None
    if sweep_index is not None:
        sweep_direction = "down" if bool(swept.iloc[sweep_index]["liquidity_sweep_down"]) else "up"
    has_fvg, has_ob = zone_after_sweep(fvg, ob, sweep_index)
    d1_bias = str(context.get("d1_bias", "UNKNOWN"))
    aligned = (d1_bias == "BULLISH" and direction == 1) or (d1_bias == "BEARISH" and direction == -1)
    countertrend = (d1_bias == "BULLISH" and direction == -1) or (d1_bias == "BEARISH" and direction == 1)
    structure = labels.get("structure_confirmation") == "CONFIRMED"
    sweep_opposes_direction = (direction == 1 and sweep_direction == "down") or (direction == -1 and sweep_direction == "up")

    po3_structural = bool(d1_bias in {"BULLISH", "BEARISH"} and aligned and sweep_opposes_direction and structure and (has_fvg or has_ob))
    turtle_core, turtle_meta = (False, {}) if sweep_time is None else is_turtle_soup(sweep_time, direction, {"M15": closed}, "M15")
    turtle_structural = bool(countertrend and turtle_core and structure and (has_fvg or has_ob))
    silver_core, silver_meta = (False, {}) if sweep_time is None else is_silver_bullet(sweep_time, decision, direction, killzone_en)
    silver_structural = bool(silver_core and aligned and has_fvg)

    base["audit_status"] = "OK"
    base["evidence"] = {
        "closed_m15_bars": len(closed),
        "context_bars_cap": CONTEXT_BARS,
        "sweep_time": None if sweep_time is None else sweep_time.isoformat(),
        "sweep_direction": sweep_direction,
        "fvg_after_sweep": has_fvg,
        "ob_after_sweep": has_ob,
        "d1_bias": d1_bias,
        "aligned": aligned,
        "countertrend": countertrend,
    }
    base["families"] = {
        "PO3": {
            "structural_match": po3_structural,
            "status": "EVIDENCE_MISSING_EXECUTION_GEOMETRY" if po3_structural else "NOT_MATCHED",
            "reason": "RR_and_sweep_anchored_execution_not_materialized",
        },
        "TURTLE_SOUP": {
            "structural_match": turtle_structural,
            "status": "EVIDENCE_MISSING_EXECUTION_GEOMETRY" if turtle_structural else "NOT_MATCHED",
            "reason": "RR_and_sweep_anchored_execution_not_materialized",
            "turtle_meta": turtle_meta,
        },
        "SILVER_BULLET": {
            "structural_match": silver_structural,
            "status": "EVIDENCE_MISSING_SCHEDULE_CONTRACT" if silver_structural else "NOT_MATCHED",
            "reason": "Local documents disagree on exact SB session hours; no certified count is emitted.",
            "silver_meta": silver_meta,
        },
    }
    return base


def render_report(results: list[dict[str, Any]]) -> str:
    rows_by_label = Counter(result["original_label"] for result in results)
    lines = [
        "# Auditoria Semantica Multimodelo v1", "", "## Dictamen", "",
        "Estado: **MORE_DETERMINISTIC_WORK_REQUIRED**. La clasificacion es paralela y diagnostica; no altera `grammar_labels`, no crea candidatos operables y mantiene `can_trade=false`.",
        "", "## Cobertura", "", f"- Filas auditadas: `{len(results)}`.",
        f"- ABSTAIN: `{rows_by_label['ABSTAIN']}`; REJECT: `{rows_by_label['REJECT']}`.",
        "", "## Coincidencias estructurales", "", "| Familia | ABSTAIN | REJECT | Total | Estado |", "| --- | ---: | ---: | ---: | --- |",
    ]
    for family in ("PO3", "TURTLE_SOUP", "SILVER_BULLET"):
        counts = Counter(result["original_label"] for result in results if result.get("families", {}).get(family, {}).get("structural_match"))
        status = "NO_CERTIFIED_COUNT" if family == "SILVER_BULLET" else "PENDING_EXECUTION_GEOMETRY"
        lines.append(f"| {family} | {counts['ABSTAIN']} | {counts['REJECT']} | {sum(counts.values())} | {status} |")
    lines.extend([
        "", "## Limites", "",
        "- La evidencia M15 se corta en `time <= decision_time`; no se consulta futuro.",
        "- La ventana de sweep usa la definicion canonica local con lookback 20 y exige que el ultimo sweep este a no mas de 20 velas de la decision.",
        "- Ninguna coincidencia pasa a `PASS`: faltan RR, coste, fill y ancla materializada de `sweep_ts`.",
        "- Silver Bullet no recibe conteo certificado hasta reconciliar las horas exactas que difieren entre los documentos locales.", "",
    ])
    return "\n".join(lines)


def run() -> list[dict[str, Any]]:
    rows = load_rows()
    source_cache: dict[Path, Any] = {}
    for row in rows:
        path = source_path(row)
        if path is not None and path not in source_cache:
            source_cache[path] = normalize_source(path)[0]
    results = [classify_row(row, source_cache) for row in rows]
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ROWS_PATH.write_text("".join(json.dumps(result, ensure_ascii=True, default=str) + "\n" for result in results), encoding="utf-8")
    REPORT_PATH.write_text(render_report(results), encoding="utf-8")
    return results


if __name__ == "__main__":
    output = run()
    print(f"audited_rows={len(output)}")
    for family in ("PO3", "TURTLE_SOUP", "SILVER_BULLET"):
        print(f"{family}=" + str(sum(bool(row.get("families", {}).get(family, {}).get("structural_match")) for row in output)))
