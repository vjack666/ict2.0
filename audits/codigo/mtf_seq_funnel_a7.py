"""Funnel de auditoría A7 (Gate A7) — versión con provenance y validación real.

NO sobrescribe el artefacto histórico mtf_seq_funnel.json; escribe un reporte
nuevo con timestamp y provenance completa: commit, estado git, hashes del
dataset, configuración, versión contractual y checksum del reporte.

Carga el snapshot CANÓNICO (datasets/eurusd_dukascopy_20y/*.csv, verificado por
SHA256SUMS) y enriquece cada record con observation_time / parent_id /
lineage_valid / direction para que FunnelAudit valide realmente los invariantes
A7 (causalidad, prefijo, unicidad, lineage, dirección, determinismo).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from engine.detectors.fvg import detect_fvg
from engine.detectors.ob import detect_order_blocks
from engine.relations import relate_fvg_ob, relation_links
from engine.sequential_events import SeqConfig, run_sequential, summarize_chains
from engine.mtf_navigation import MTFNavigator, NavigatorConfig
from .funnel import FunnelAudit, STAGES

ROOT = Path(__file__).resolve().parents[2]
CANON = ROOT / "datasets" / "eurusd_dukascopy_20y"
OUT_DIR = ROOT / "reports" / "audits" / "experiments" / "fvg_ob"
CONTRACT_VERSION = "CONTRATO_FUNNEL_AUDIT.md#A7"
SAMPLE_EVERY = 2500
PRECOMPUTE = True


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                        stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "UNKNOWN"


def _git_status() -> str:
    try:
        out = subprocess.check_output(["git", "status", "--porcelain", "-b"], cwd=ROOT,
                                       stderr=subprocess.DEVNULL).decode().strip().splitlines()
        return "DIRTY" if any(not l.startswith("##") for l in out) else "CLEAN"
    except Exception:
        return "UNKNOWN"


def _dataset_hashes() -> dict:
    sums = (CANON / "SHA256SUMS").read_text(errors="ignore").splitlines()
    out = {}
    for line in sums:
        line = line.strip().replace("\r", "")
        if not line:
            continue
        h, _, name = line.partition("  ")
        out[name] = h
    return out


def _load_tf(tf: str) -> pd.DataFrame:
    p = CANON / f"EURUSD_{tf}.csv"
    if not p.exists():
        raise FileNotFoundError(f"CSV canónico no encontrado: {p}")
    df = pd.read_csv(p)
    df["time"] = pd.to_datetime(df["time"])
    return df


def _obs_time(mo, time_by_index: dict | None = None) -> str | None:
    """Tiempo de observación real del objeto (mapeado desde el CSV canónico).

    El detector expone confirmation_time/candidate_time como bar_index (int).
    Si hay un mapa bar_index->timestamp, devolvemos el ISO real; si no, el
    entero como string (fallback, aún comparable dentro de la misma TF).
    """
    t = getattr(mo, "confirmation_time", None) or getattr(mo, "candidate_time", None)
    if t is None:
        return None
    if isinstance(t, datetime):
        return t.isoformat()
    # t es bar_index (int)
    if time_by_index is not None:
        ts = time_by_index.get(int(t))
        if ts is not None:
            return ts.isoformat() if isinstance(ts, datetime) else str(ts)
    return str(int(t))


def _run_funnel(records: list[dict]) -> dict:
    result, summaries = FunnelAudit(audit_id="A7_FUNNEL_A7").run(records)
    return {
        "audit_status": result.status.value,
        "input_count": result.input_count,
        "accepted_count": result.accepted_count,
        "rejected_count": result.rejected_count,
        "audit_score": result.metrics.get("audit_score"),
        "n_findings": len(result.findings),
        "findings": [
            {"code": f.code, "severity": f.severity, "message": f.message,
             "stage": f.stage, "record_id": f.record_id}
            for f in result.findings
        ],
        "stages": [
            {"stage": s.stage, "input_count": s.input_count,
             "accepted_count": s.accepted_count, "rejected_count": s.rejected_count}
            for s in summaries
        ],
    }


def funnel_fvg_ob(df: pd.DataFrame, tf: str) -> dict:
    rows = df[["open", "high", "low", "close"]].copy()
    rows["time"] = list(range(len(df)))
    rows = rows.to_dict("records")
    fvg = detect_fvg(rows, timeframe=tf, symbol="EURUSD")
    ob = detect_order_blocks(rows, timeframe=tf, symbol="EURUSD")
    relations = relate_fvg_ob(fvg, ob, max_bars_apart=20, same_direction=True, causal_mode="strict")
    known_ids = {x.id for x in fvg} | {x.id for x in ob}
    # Mapa bar_index -> timestamp real del CSV canónico (para observation_time A7).
    time_by_index = {i: df["time"].iloc[i] for i in range(len(df))}

    records = []
    for item in fvg:
        records.append({"stage": "FVG", "id": item.id, "accepted": True,
                         "direction": item.direction, "timeframe": tf,
                         "observation_time": _obs_time(item, time_by_index), "requires_parent": False})
    for item in ob:
        records.append({"stage": "OB", "id": item.id, "accepted": True,
                         "direction": item.direction, "timeframe": tf,
                         "observation_time": _obs_time(item, time_by_index), "requires_parent": False})
    related_fvg = {r.fvg_id for r in relations}
    for item in fvg:
        if item.id not in related_fvg:
            records.append({"stage": "CONFLUENCE", "id": f"FVG_NO_REL_{item.id}",
                             "accepted": False, "direction": item.direction, "timeframe": tf,
                             "rejection_reason": "NO_OB_CAUSAL",
                             "observation_time": _obs_time(item, time_by_index), "requires_parent": False})
    for rel in relations:
        rec_ob = ob_dict(ob, rel.ob_id)
        records.append({"stage": "CONFLUENCE", "id": f"{rel.fvg_id}__{rel.ob_id}",
                         "accepted": True, "direction": rel.direction, "timeframe": tf,
                         "observation_time": _obs_time(rec_ob, time_by_index),
                         "requires_parent": True, "parent_id": rel.ob_id,
                         "lineage_valid": rel.ob_id in known_ids})

    audit = _run_funnel(records)
    accepted_ids = [r["id"] for r in records if r.get("accepted")]
    accepted_obs = {r["id"]: r.get("observation_time") for r in records if r.get("accepted")}
    return {"timeframe": tf, "bars": len(df), "fvg_count": len(fvg),
            "ob_count": len(ob), "relation_count": len(relations),
            "relation_rule": "STRICT FVG_OB_CAUSAL", "accepted_ids": accepted_ids,
            "accepted_obs": accepted_obs, **audit}


def ob_dict(ob_list, oid):
    for o in ob_list:
        if o.id == oid:
            return o
    return ob_list[0]


def funnel_sequence(df: pd.DataFrame, tf: str) -> dict:
    cfg = SeqConfig(structure_mode="canonical_bos", max_active_chains=128)
    raw = run_sequential(df, cfg, symbol="EURUSD", timeframe=tf)
    chains: list = list(raw)  # run_sequential devuelve lista de SequentialChain
    summary = summarize_chains(chains)
    time_by_index = {i: df["time"].iloc[i] for i in range(len(df))}

    records = []
    for ch in chains:
        chain_obs = time_by_index.get(ch.last_bar)  # barra de confirmación de la cadena
        records.append({"stage": "SEQ_CHAIN", "id": ch.chain_id,
                         "accepted": ch.status == "COMPLETE",
                         "rejection_reason": None if ch.status == "COMPLETE" else "INVALID_DATA",
                         "direction": ch.direction, "timeframe": tf,
                         "observation_time": chain_obs.isoformat() if chain_obs is not None else None,
                         "requires_parent": False})
        for nd in ch.nodes:
            obs = time_by_index.get(nd.bar)
            records.append({"stage": f"SEQ_{nd.stage.value}", "id": f"{ch.chain_id}_{nd.stage.value}",
                             "accepted": True, "direction": ch.direction, "timeframe": tf,
                             "observation_time": obs.isoformat() if obs is not None else None,
                             "requires_parent": False})
    audit = _run_funnel(records)
    accepted_ids = [r["id"] for r in records if r.get("accepted")]
    return {"timeframe": tf, "summary": summary,
            "n_complete": summary.get("by_status", {}).get("COMPLETE", 0),
            "n_chains": summary.get("n_chains", 0), "accepted_ids": accepted_ids, **audit}


def funnel_mtf_navigation(frames: dict[str, pd.DataFrame]) -> dict:
    h1 = frames["H1"]
    nav = MTFNavigator(frames, NavigatorConfig(precompute_sequences=PRECOMPUTE, sequence_tf="H1"))
    records = []
    samples = []
    for i in range(500, len(h1), SAMPLE_EVERY):
        t = h1["time"].iloc[i]
        st = nav.navigate(decision_time=t, exec_tf="H1")
        samples.append({"decision_time": str(t), "status": st.status,
                         "path_len": len(st.path.steps) if st.path else 0})
        records.append({"stage": "MTF_NAV", "id": f"nav_{i}", "accepted": st.status == "OK",
                         "rejection_reason": None if st.status == "OK" else "CONTRACT_VIOLATION",
                         "timeframe": "H1", "observation_time": str(t), "requires_parent": False})
    audit = _run_funnel(records)
    return {"n_samples": len(samples), "sample_every": SAMPLE_EVERY,
            "precompute_sequences": PRECOMPUTE, "samples_preview": samples[:5],
            "policy": "CONTEXT_STATE_NOT_ENTRY_SIGNAL", **audit}


def funnel_prefix_invariance(frames: dict[str, pd.DataFrame]) -> dict:
    """Contrato A7 §Invariancia PREFIX: bars[:t] debe producir los mismos eventos
    aceptados (con observation_time <= t) que el dataset completo.

    Los detectores FVG/OB son PIT-stable por barra (átomos en t iguales, según
    deuda documentada en .hermes-index.md). run_sequential TIENE deuda conocida
    de PIT-stability (NO FULL-vs-PREFIX); por eso el sub-check de secuencia se
    reporta como hallazgo informativo y no como FAIL ciego.
    """
    cut = 0.60
    result = {"prefix_ratio": cut, "by_timeframe": {}, "sequence": {}}
    for tf in ("H1", "H4", "D1"):
        full = funnel_fvg_ob(frames[tf], tf)
        n = len(frames[tf])
        k = int(n * cut)
        prefix = funnel_fvg_ob(frames[tf].iloc[:k], tf)
        t_max = str(frames[tf]["time"].iloc[k - 1])
        full_in_window = {i for i, ot in full["accepted_obs"].items()
                          if ot is not None and ot <= t_max}
        missing = full_in_window - set(prefix["accepted_ids"])
        result["by_timeframe"][tf] = {
            "full_accepted": len(full["accepted_ids"]),
            "prefix_accepted": len(prefix["accepted_ids"]),
            "full_in_prefix_window": len(full_in_window),
            "missing_in_prefix": len(missing),
            "prefix_invariant": len(missing) == 0,
        }
    # Sequence (deuda conocida): reportar diferencia, no fallar ciego.
    full_seq = funnel_sequence(frames["H1"], "H1")
    n = len(frames["H1"]); k = int(n * cut)
    pref_seq = funnel_sequence(frames["H1"].iloc[:k], "H1")
    seq_missing = set(full_seq["accepted_ids"]) - set(pref_seq["accepted_ids"])
    result["sequence"] = {
        "full_chains": full_seq.get("n_chains"),
        "prefix_chains": pref_seq.get("n_chains"),
        "missing_in_prefix": len(seq_missing),
        "note": "run_sequential NO PIT-stable FULL-vs-PREFIX (deuda motor documentada); "
                "diferencias reportadas como hallazgo, no como FAIL automatico",
    }
    return result


def main() -> dict:
    frames = {tf: _load_tf(tf) for tf in ("H1", "H4", "D1")}
    hashes = _dataset_hashes()
    report = {
        "contract_version": CONTRACT_VERSION,
        "gate": "A7",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commit": _git_commit(),
        "git_status": _git_status(),
        "dataset": "dukascopy EURUSD 20Y (canonico)",
        "dataset_hashes": hashes,
        "config": {"sample_every": SAMPLE_EVERY, "precompute_sequences": PRECOMPUTE,
                    "relation_rule": "STRICT FVG_OB_CAUSAL", "causal_mode": "strict"},
        "symbol": "EURUSD",
        "policy": "AUDIT_FUNNEL_NO_PNL_NO_ENTRY",
        "fvg_ob": {}, "sequence": {}, "mtf_navigation": {},
    }
    for tf in ("H1", "H4", "D1"):
        report["fvg_ob"][tf] = funnel_fvg_ob(frames[tf], tf)
    report["sequence"]["H1"] = funnel_sequence(frames["H1"], "H1")
    report["mtf_navigation"] = funnel_mtf_navigation(frames)
    report["prefix_invariance"] = funnel_prefix_invariance(frames)

    # Checksum del reporte (sin el propio checksum).
    report_str = json.dumps(report, default=str, sort_keys=True)
    report["report_checksum_sha256"] = hashlib.sha256(report_str.encode()).hexdigest()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUT_DIR / f"mtf_seq_funnel_a7_{stamp}.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps({
        "out": str(out_path),
        "commit": report["commit"], "git_status": report["git_status"],
        "fvg_ob_H1_rel": report["fvg_ob"]["H1"]["relation_count"],
        "seq_complete": report["sequence"]["H1"]["n_complete"],
        "mtf_status": report["mtf_navigation"]["audit_status"],
        "report_checksum": report["report_checksum_sha256"],
    }, indent=2))
    return report


if __name__ == "__main__":
    main()
