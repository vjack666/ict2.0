"""CLI reproducible para ejecutar A0-A9 en secuencia y luego A7 Funnel.

Uso:
    python -m audits.codigo.run_full_stack

El runner usa un smoke dataset para probar el contrato de todos los gates y,
si se encuentra el reporte histórico del Funnel, lo registra como evidencia
preexistente. No inventa un Funnel de FVG/OB si no existe una extracción de
objetos disponible.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .audit_stack import run_stack

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "audits"


def smoke_rows():
    return [
        {"id": "bar-1", "time": 1, "open": 1.10, "high": 1.20, "low": 1.00, "close": 1.15},
        {"id": "bar-2", "time": 2, "open": 1.15, "high": 1.25, "low": 1.05, "close": 1.20},
        {"id": "bar-3", "time": 3, "open": 1.20, "high": 1.30, "low": 1.10, "close": 1.25},
    ]


def smoke_events():
    return [
        {"id": "evt-1", "candidate_time": 1, "confirmation_time": 2, "tradable_time": 2, "observation_time": 2},
    ]


def smoke_funnel():
    return [
        {"stage": "VALID_BARS", "id": "b1", "accepted": True, "direction": 1},
        {"stage": "STRUCTURE", "id": "s1", "accepted": True, "direction": 1},
        {"stage": "BOS_CHOCH", "id": "c1", "accepted": True, "direction": 1},
        {"stage": "DISPLACEMENT", "id": "d1", "accepted": True, "direction": 1},
        {"stage": "FVG", "id": "f1", "accepted": True, "direction": 1},
        {"stage": "OB", "id": "o1", "accepted": True, "direction": 1, "ob_type": "CANONICAL"},
        {"stage": "CONFLUENCE", "id": "x1", "accepted": True, "direction": 1},
        {"stage": "LINEAGE", "id": "l1", "accepted": True, "direction": 1},
        {"stage": "SETUP", "id": "u1", "accepted": True, "direction": 1},
    ]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    stack = run_stack(smoke_rows(), smoke_events(), smoke_funnel())
    stack["timestamp"] = datetime.now(timezone.utc).isoformat()
    stack["scope"] = "contract-smoke + existing historical Funnel evidence"
    historical = ROOT / "docs" / "AUDITORIA_FUNNEL_EURUSD_H1_H4_D1.md"
    stack["historical_funnel_report"] = str(historical) if historical.exists() else None
    path = OUT / "A0_A9_audit_stack.json"
    path.write_text(json.dumps(stack, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(stack, ensure_ascii=False, indent=2))
    return 0 if stack["status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
