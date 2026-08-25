"""Funnel de auditoría: FVG/OB + secuencia + navegación MTF (Context State).

Extiende el funnel FVG/OB con etapas de profundidad secuencial y del grafo
multi-TF. No calcula PnL ni emite entradas.

Salida: reports/audits/experiments/fvg_ob/mtf_seq_funnel.json
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from engine.detectors.fvg import detect_fvg
from engine.detectors.ob import detect_order_blocks
from engine.relations import relate_fvg_ob, relation_links
from engine.sequential_events import SeqConfig, run_sequential, summarize_chains
from engine.mtf_navigation import MTFNavigator, NavigatorConfig
from .funnel import FunnelAudit

def _count_extra_stages(records: list[dict]) -> dict[str, dict[str, int]]:
    """Count stages beyond the classic A7 STAGES list."""
    from collections import defaultdict
    g: dict[str, list] = defaultdict(list)
    for r in records:
        g[str(r.get("stage", ""))].append(r)
    out = {}
    for stage, items in sorted(g.items()):
        acc = sum(1 for x in items if x.get("accepted", True))
        out[stage] = {"n": len(items), "accepted": acc, "rejected": len(items) - acc}
    return out


def _run_funnel(audit_id: str, records: list[dict]) -> dict:
    result, summaries = FunnelAudit(audit_id=audit_id).run(records)
    status = getattr(result.status, "value", str(result.status))
    return {
        "audit_status": status,
        "stages": [
            {
                "stage": s.stage,
                "input_count": s.input_count,
                "accepted_count": s.accepted_count,
                "rejected_count": s.rejected_count,
            }
            for s in summaries
        ],
        "extra_stage_counts": _count_extra_stages(records),
        "findings": [getattr(f, "code", str(f)) for f in result.findings] if result.findings else [],
    }

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "audits" / "experiments" / "fvg_ob" / "mtf_seq_funnel.json"
DATA = ROOT / "data" / "raw" / "EURUSD"
# fallback datasets path
DATA_ALT = ROOT / "datasets" / "eurusd_dukascopy_20y"


def _load_tf(tf: str) -> pd.DataFrame:
    for base in (DATA, DATA_ALT):
        p = base / f"EURUSD_{tf}.csv"
        if p.exists():
            df = pd.read_csv(p)
            df["time"] = pd.to_datetime(df["time"])
            return df
    raise FileNotFoundError(f"EURUSD_{tf}.csv not found in {DATA} or {DATA_ALT}")


def _rows_for_detectors(df: pd.DataFrame) -> list[dict]:
    rec = df[["open", "high", "low", "close"]].copy()
    rec["time"] = list(range(len(df)))
    return rec.to_dict("records")


def funnel_fvg_ob(df: pd.DataFrame, tf: str) -> dict:
    rows = _rows_for_detectors(df)
    fvg = detect_fvg(rows, timeframe=tf, symbol="EURUSD")
    ob = detect_order_blocks(rows, timeframe=tf, symbol="EURUSD")
    relations = relate_fvg_ob(fvg, ob, max_bars_apart=20, same_direction=True, causal_mode="strict")
    links = relation_links(relations, {x.id: x for x in fvg}, {x.id: x for x in ob})

    records = []
    for item in fvg:
        records.append({"stage": "FVG", "id": item.id, "accepted": True, "direction": item.direction, "timeframe": tf})
    for item in ob:
        records.append({"stage": "OB", "id": item.id, "accepted": True, "direction": item.direction, "timeframe": tf})
    for rel in relations:
        records.append({
            "stage": "CONFLUENCE",
            "id": f"{rel.fvg_id}__{rel.ob_id}",
            "accepted": True,
            "direction": rel.direction,
            "timeframe": tf,
            "relation": rel.relation,
            "bars_apart": rel.bars_apart,
        })
    related_fvg = {r.fvg_id for r in relations}
    for item in fvg:
        if item.id not in related_fvg:
            records.append({
                "stage": "CONFLUENCE",
                "id": f"FVG_NO_REL_{item.id}",
                "accepted": False,
                "rejection_reason": "NO_OB_CAUSAL",
                "timeframe": tf,
            })

    result, summaries = FunnelAudit(audit_id=f"A7_FVG_OB_{tf}").run(records)
    return {
        "timeframe": tf,
        "bars": len(df),
        "fvg_count": len(fvg),
        "ob_count": len(ob),
        "relation_count": len(relations),
        "causal_links": len(links),
        "relation_rate_vs_fvg": (len(relations) / len(fvg)) if fvg else 0.0,
        "relation_rule": "STRICT FVG_OB_CAUSAL",
        "audit_status": str(result.status),
        "audit_score": result.metrics.get("audit_score") if hasattr(result, "metrics") else None,
        "stages": [
            {"stage": s.stage, "input_count": s.input_count, "accepted_count": s.accepted_count, "rejected_count": s.rejected_count}
            for s in summaries
        ],
        "extra_stage_counts": _count_extra_stages(records),
    }


def funnel_sequence(df: pd.DataFrame, tf: str) -> dict:
    cfg = SeqConfig(structure_mode="canonical_bos", max_active_chains=128)
    chains = run_sequential(df, cfg, symbol="EURUSD", timeframe=tf)
    summary = summarize_chains(chains)
    records = []
    for ch in chains:
        depth = len(ch.nodes)
        records.append({
            "stage": "SEQ_CHAIN",
            "id": ch.chain_id,
            "accepted": ch.status == "COMPLETE",
            "rejection_reason": None if ch.status == "COMPLETE" else ch.status,
            "direction": ch.direction,
            "timeframe": tf,
            "depth": depth,
            "stages_path": ch.stages_present,
        })
        # stage-level funnel markers
        for nd in ch.nodes:
            records.append({
                "stage": f"SEQ_{nd.stage.value}",
                "id": f"{ch.chain_id}_{nd.stage.value}",
                "accepted": True,
                "direction": ch.direction,
                "timeframe": tf,
                "bar": nd.bar,
            })

    audit = _run_funnel(f"A7_SEQ_{tf}", records)
    return {
        "timeframe": tf,
        "summary": summary,
        "n_complete": summary.get("by_status", {}).get("COMPLETE", 0),
        "n_chains": summary.get("n_chains", 0),
        **audit,
    }


def funnel_mtf_navigation(frames: dict[str, pd.DataFrame], sample_every: int = 2000) -> dict:
    """Sample decision times on H1 and audit navigation path completeness."""
    h1 = frames["H1"]
    nav = MTFNavigator(
        frames,
        NavigatorConfig(precompute_sequences=True, sequence_tf="H1"),
    )
    records = []
    samples = []
    for i in range(500, len(h1), sample_every):
        t = h1["time"].iloc[i]
        st = nav.navigate(decision_time=t, exec_tf="H1")
        depth_ans = None
        if "H1" in st.layers:
            depth_ans = st.layers["H1"].answers.get("HAS_SEQUENCE_DEPTH")
        samples.append({
            "decision_time": str(t),
            "status": st.status,
            "direction_hint": st.constraints.direction_hint.value if st.constraints else None,
            "path_len": len(st.path.steps),
            "seq_depth": depth_ans,
            "regime_stack": st.constraints.regime_stack if st.constraints else {},
        })
        records.append({
            "stage": "MTF_NAV",
            "id": f"nav_{i}",
            "accepted": st.status == "OK",
            "rejection_reason": None if st.status == "OK" else st.status,
            "timeframe": "H1",
        })
        records.append({
            "stage": "MTF_CONSTRAINTS",
            "id": f"ctx_{i}",
            "accepted": st.constraints is not None,
            "timeframe": "H1",
        })
        if depth_ans is not None:
            d = depth_ans.get("depth", 0) if isinstance(depth_ans, dict) else int(depth_ans)
            records.append({
                "stage": "MTF_SEQ_DEPTH",
                "id": f"depth_{i}",
                "accepted": d >= 1,
                "rejection_reason": None if d >= 1 else "SEQ_DEPTH_ZERO",
                "timeframe": "H1",
                "depth": d,
                "source": depth_ans.get("source") if isinstance(depth_ans, dict) else None,
            })

    audit = _run_funnel("A7_MTF_NAV", records)
    return {
        "n_samples": len(samples),
        "sample_every": sample_every,
        "samples_preview": samples[:5],
        "anti_lookahead": "docs/ANTI_LOOKAHEAD_MTF_SEQUENCE.md",
        "policy": "CONTEXT_STATE_NOT_ENTRY_SIGNAL",
        **audit,
    }


def main() -> dict:
    frames = {tf: _load_tf(tf) for tf in ("H1", "H4", "D1")}
    report = {
        "dataset": "dukascopy EURUSD 20Y",
        "symbol": "EURUSD",
        "policy": "AUDIT_FUNNEL_NO_PNL_NO_ENTRY",
        "fvg_ob": {},
        "sequence": {},
        "mtf_navigation": {},
    }
    for tf in ("H1", "H4", "D1"):
        report["fvg_ob"][tf] = funnel_fvg_ob(frames[tf], tf)
    report["sequence"]["H1"] = funnel_sequence(frames["H1"], "H1")
    report["mtf_navigation"] = funnel_mtf_navigation(frames, sample_every=2500)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps({
        "out": str(OUT),
        "fvg_ob_H1_rel": report["fvg_ob"]["H1"]["relation_count"],
        "seq_complete": report["sequence"]["H1"]["n_complete"],
        "seq_chains": report["sequence"]["H1"]["n_chains"],
        "mtf_samples": report["mtf_navigation"]["n_samples"],
        "mtf_status": report["mtf_navigation"]["audit_status"],
    }, indent=2))
    return report


if __name__ == "__main__":
    main()
