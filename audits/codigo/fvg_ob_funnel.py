"""Funnel real FVG/OB + relación explícita sobre EURUSD H1/H4/D1.

Descarga CSV público de ejtraderLabs, normaliza escala y ejecuta los detectores
canónicos FVG/OB y la relación FVG↔OB. No usa PnL ni IA.
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
    "H1": str(ROOT / "data/raw/EURUSD/EURUSD_H1.csv"),
    "H4": str(ROOT / "data/raw/EURUSD/EURUSD_H4.csv"),
    "D1": str(ROOT / "data/raw/EURUSD/EURUSD_D1.csv"),
}


def load_csv(url: str) -> list[dict]:
    if str(url).startswith("http"):
        with urllib.request.urlopen(url, timeout=60) as response:
            text = response.read().decode("utf-8")
    else:
        text = Path(url).read_text(encoding="utf-8")
    rows = list(csv.DictReader(text.splitlines()))
    values = [float(r["open"]) for r in rows if r.get("open")]
    scale = 100000.0 if values and statistics.median(values) > 10 else 1.0
    out = []
    for r in rows:
        out.append({
            "time": r.get("Date") or r.get("time") or r.get("timestamp"),
            "open": float(r["open"]) / scale,
            "high": float(r["high"]) / scale,
            "low": float(r["low"]) / scale,
            "close": float(r["close"]) / scale,
        })
    return out


def one_tf(tf: str, rows: list[dict]) -> dict:
    fvg = detect_fvg(rows, timeframe=tf, symbol="EURUSD")
    ob = detect_order_blocks(rows, timeframe=tf, symbol="EURUSD")
    relations = relate_fvg_ob(fvg, ob, max_bars_apart=20, same_direction=True, causal_mode="strict")
    links = relation_links(
        relations,
        {item.id: item for item in fvg},
        {item.id: item for item in ob},
    )

    records = []
    for item in fvg:
        records.append({"stage": "FVG", "id": item.id, "accepted": True, "direction": item.direction, "timeframe": tf})
    for item in ob:
        records.append({"stage": "OB", "id": item.id, "accepted": True, "direction": item.direction, "timeframe": tf, "ob_type": "CANONICAL"})
    for rel in relations:
        records.append({
            "stage": "CONFLUENCE",
            "id": f"{rel.fvg_id}__{rel.ob_id}",
            "accepted": True,
            "direction": rel.direction,
            "timeframe": tf,
            "bars_apart": rel.bars_apart,
            "overlap_low": rel.overlap_low,
            "overlap_high": rel.overlap_high,
        })
    related_fvg = {rel.fvg_id for rel in relations}
    related_ob = {rel.ob_id for rel in relations}
    for item in fvg:
        if item.id not in related_fvg:
            records.append({"stage": "CONFLUENCE", "id": f"FVG_NO_REL_{item.id}", "accepted": False, "rejection_reason": "NO_OB_RELATION", "direction": item.direction, "timeframe": tf})
    for item in ob:
        if item.id not in related_ob:
            records.append({"stage": "CONFLUENCE", "id": f"OB_NO_REL_{item.id}", "accepted": False, "rejection_reason": "NO_FVG_RELATION", "direction": item.direction, "timeframe": tf})

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
        "relation_count": len(relations),
        "relation_bull": sum(x.direction == 1 for x in relations),
        "relation_bear": sum(x.direction == -1 for x in relations),
        "relation_rate_vs_fvg": len(relations) / len(fvg) if fvg else 0.0,
        "relation_rate_vs_ob": len(relations) / len(ob) if ob else 0.0,
        "causal_links": len(links),
        "audit_status": result.status.value,
        "findings": [f.__dict__ for f in result.findings],
        "stages": [s.__dict__ for s in summaries],
        "relation_rule": "STRICT: same_direction + price_overlap + OB_before_FVG + lag<=20 + CausalLink parent=OB",
    }


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    report = {"dataset": "dukascopy-node EURUSD 2006-01-01..2026-01-01 (20Y) + FVG_OB relation", "symbol": "EURUSD", "timeframes": {}}
    for tf, url in SOURCES.items():
        rows = load_csv(url)
        report["timeframes"][tf] = one_tf(tf, rows)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
