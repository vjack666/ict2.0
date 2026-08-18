"""Funnel real de FVG/OB sobre EURUSD H1/H4/D1.

Descarga datos, ejecuta detectores canónicos y conecta FVG↔OB mediante la
relación auditada. No usa PnL ni IA.
"""
from __future__ import annotations

import csv
import json
import statistics
import urllib.request
from pathlib import Path

from engine.detectors.fvg import detect_fvg
from engine.detectors.ob import detect_order_blocks
from engine.relations import relate_fvg_ob, relation_links
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
    return [
        {
            "time": r["Date"],
            "open": float(r["open"]) / scale,
            "high": float(r["high"]) / scale,
            "low": float(r["low"]) / scale,
            "close": float(r["close"]) / scale,
        }
        for r in rows
    ]


def one_tf(tf: str, rows: list[dict]) -> dict:
    fvgs = detect_fvg(rows, timeframe=tf, symbol="EURUSD")
    obs = detect_order_blocks(rows, timeframe=tf, symbol="EURUSD")
    fvg_by_id = {item.id: item for item in fvgs}
    ob_by_id = {item.id: item for item in obs}
    relations = relate_fvg_ob(fvgs, obs, max_bars_apart=20, same_direction=True)
    links = relation_links(relations, fvg_by_id, ob_by_id)

    records = [
        {"stage": "FVG", "id": item.id, "accepted": True, "direction": item.direction, "timeframe": tf}
        for item in fvgs
    ]
    records += [
        {"stage": "OB", "id": item.id, "accepted": True, "direction": item.direction, "timeframe": tf, "ob_type": "CANONICAL"}
        for item in obs
    ]
    records += [
        {
            "stage": "CONFLUENCE",
            "id": f"REL_{relation.fvg_id}_{relation.ob_id}",
            "accepted": True,
            "direction": relation.direction,
            "timeframe": tf,
            "relation": relation.relation,
            "bars_apart": relation.bars_apart,
            "overlap_low": relation.overlap_low,
            "overlap_high": relation.overlap_high,
        }
        for relation in relations
    ]
    records += [
        {"stage": "LINEAGE", "id": f"LINK_{link.parent_id}_{link.child_id}", "accepted": True, "direction": 0, "timeframe": tf, "relation": link.relation}
        for link in links
    ]

    result, summaries = FunnelAudit(f"A7_FVG_OB_{tf}").run(records)
    return {
        "timeframe": tf,
        "bars": len(rows),
        "fvg_count": len(fvgs),
        "ob_count": len(obs),
        "relation_count": len(relations),
        "lineage_link_count": len(links),
        "fvg_bull": sum(x.direction == 1 for x in fvgs),
        "fvg_bear": sum(x.direction == -1 for x in fvgs),
        "ob_bull": sum(x.direction == 1 for x in obs),
        "ob_bear": sum(x.direction == -1 for x in obs),
        "audit_status": result.status.value,
        "findings": [f.__dict__ for f in result.findings],
        "stages": [s.__dict__ for s in summaries],
        "note": "Confluence uses the canonical FVG↔OB overlap contract: same direction, positive price overlap and <=20 bars apart; lineage is represented as CausalLink.",
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
