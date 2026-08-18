"""Funnel real de FVG/OB sobre EURUSD H1/H4/D1.

Descarga CSV público de ejtraderLabs, normaliza escala y ejecuta los detectores
canónicos FVG/OB. No usa PnL ni IA. Los resultados se agregan por TF y dirección.
"""
from __future__ import annotations

import csv
import json
import statistics
import urllib.request
from pathlib import Path

from engine.detectors.fvg import detect_fvg
from engine.detectors.ob import detect_order_blocks
from .funnel import FunnelAudit

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "audits" / "fvg_ob_funnel.json"
BASE = "https://raw.githubusercontent.com/ejtraderLabs/historical-data/main/EURUSD/"
SOURCES = {
    "H1": BASE + "EURUSDh1.csv",
    "H4": BASE + "EURUSDh4.csv",
    "D1": BASE + "EURUSDd1.csv",
}


def load_csv(url: str) -> list[dict]:
    with urllib.request.urlopen(url, timeout=60) as response:
        text = response.read().decode("utf-8")
    rows = list(csv.DictReader(text.splitlines()))
    values = [float(r["open"]) for r in rows if r.get("open")]
    scale = 100000.0 if values and statistics.median(values) > 10 else 1.0
    out = []
    for r in rows:
        out.append({
            "time": r["Date"],
            "open": float(r["open"]) / scale,
            "high": float(r["high"]) / scale,
            "low": float(r["low"]) / scale,
            "close": float(r["close"]) / scale,
        })
    return out


def one_tf(tf: str, rows: list[dict]) -> dict:
    fvg = detect_fvg(rows, timeframe=tf, symbol="EURUSD")
    ob = detect_order_blocks(rows, timeframe=tf, symbol="EURUSD")
    records = []
    for i, item in enumerate(fvg):
        records.append({"stage": "FVG", "id": item.id, "accepted": True, "direction": item.direction, "timeframe": tf})
    for item in ob:
        records.append({"stage": "OB", "id": item.id, "accepted": True, "direction": item.direction, "timeframe": tf, "ob_type": "CANONICAL"})
    for item in fvg:
        records.append({"stage": "CONFLUENCE", "id": f"FVG_CONF_{item.id}", "accepted": False, "rejection_reason": "NO_OB_RELATION_AUDITED", "direction": item.direction, "timeframe": tf})
    for item in ob:
        records.append({"stage": "CONFLUENCE", "id": f"OB_CONF_{item.id}", "accepted": False, "rejection_reason": "NO_FVG_RELATION_AUDITED", "direction": item.direction, "timeframe": tf})
    result, summaries = FunnelAudit(f"A7_FVG_OB_{tf}").run(records)
    return {
        "timeframe": tf,
        "bars": len(rows),
        "fvg_count": len(fvg),
        "ob_count": len(ob),
        "fvg_bull": sum(x.direction == 1 for x in fvg),
        "fvg_bear": sum(x.direction == -1 for x in fvg),
        "ob_bull": sum(x.direction == 1 for x in ob),
        "ob_bear": sum(x.direction == -1 for x in ob),
        "audit_status": result.status.value,
        "findings": [f.__dict__ for f in result.findings],
        "stages": [s.__dict__ for s in summaries],
        "note": "Confluence is intentionally not inferred: current run measures detector populations only; FVG↔OB relation requires Fase D/E relation rules beyond this detector-only pass.",
    }


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    report = {"dataset": "ejtraderLabs/historical-data", "symbol": "EURUSD", "timeframes": {}}
    for tf, url in SOURCES.items():
        rows = load_csv(url)
        report["timeframes"][tf] = one_tf(tf, rows)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
