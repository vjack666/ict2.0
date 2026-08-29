"""Funnel de auditoría A7 (Gate A7) — runner con provenance y validación real.

NO sobrescribe el artefacto histórico mtf_seq_funnel.json; escribe un reporte
nuevo con timestamp y provenance completa: commit, estado git, hashes del
dataset (validados contra SHA256SUMS), configuración, versión contractual y
checksum del reporte.

Materializa las etapas del contrato A7 con poblaciones REALES del motor:
  RAW_BARS -> VALID_BARS -> FVG -> OB -> CONFLUENCE -> LINEAGE ->
  SEQUENCE (BOS_CHOCH / DISPLACEMENT / LIQUIDITY_POOL / SWEEP) -> MTF_NAVIGATION

Enriquece cada record con observation_time / candidate_time / confirmation_time /
tradable_time / parent_id / lineage_valid / direction para que FunnelAudit valide
realmente los invariantes A7 (causalidad, prefijo, lineage, duplicados, dirección).
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
from engine.relations import relate_fvg_ob
from engine.sequential_events import SeqConfig, run_sequential, summarize_chains
from engine.mtf_navigation import MTFNavigator, NavigatorConfig
from .funnel import FunnelAudit, STAGES

ROOT = Path(__file__).resolve().parents[2]
CANON = ROOT / "datasets" / "eurusd_dukascopy_20y"
OUT_DIR = ROOT / "reports" / "audits" / "experiments" / "fvg_ob"
CONTRACT_VERSION = "CONTRATO_FUNNEL_AUDIT.md#A7"
SAMPLE_EVERY = 2500
PRECOMPUTE = True
PREFIX_RATIO = 0.60


# --------------------------------------------------------------------------
# Git / dataset
# --------------------------------------------------------------------------
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


def _load_tf(tf: str) -> pd.DataFrame:
    p = CANON / f"EURUSD_{tf}.csv"
    if not p.exists():
        raise FileNotFoundError(f"CSV canónico no encontrado: {p}")
    df = pd.read_csv(p)
    df["time"] = pd.to_datetime(df["time"])
    df["bar"] = range(len(df))
    return df


def _dataset_manifest() -> dict:
    """Lee SHA256SUMS (LF) y valida que los bytes del CSV cargado coincidan."""
    manifest = {}
    raw = (CANON / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    for line in raw:
        line = line.strip()
        if not line:
            continue
        h, _, name = line.partition("  ")
        manifest[name] = h
    return manifest


def _verify_provenance() -> dict:
    """Valida hashes reales de los CSV contra el manifiesto (gate de provenance)."""
    manifest = _dataset_manifest()
    result = {}
    for name, expected in manifest.items():
        p = CANON / name
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        result[name] = {"expected": expected, "actual": actual, "match": expected == actual}
    return result


def _obs_time(mo, time_by_index: dict | None = None) -> tuple[str | None, str | None, str | None, str | None]:
    """Mapea tiempos del detector (bar_index) a timestamps reales del CSV.

    Devuelve (observation_time, candidate_time, confirmation_time, tradable_time).
    """
    def _map(v):
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.isoformat()
        if isinstance(v, int) and time_by_index is not None:
            ts = time_by_index.get(v)
            if ts is not None:
                return ts.isoformat() if isinstance(ts, datetime) else str(ts)
        return str(int(v)) if isinstance(v, int) else str(v)

    return _map(getattr(mo, "confirmation_time", None) or getattr(mo, "candidate_time", None)), \
           _map(getattr(mo, "candidate_time", None)), \
           _map(getattr(mo, "confirmation_time", None)), \
           _map(getattr(mo, "tradable_time", None))


def _time_string(value) -> str:
    """Serializa tiempos datetime y tiempos numéricos de fixtures sin perderlos."""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _latest_time(*values) -> str | None:
    """Devuelve el último tiempo causal disponible, normalizado a UTC."""
    parsed = []
    for value in values:
        timestamp = _as_utc_timestamp(value)
        if timestamp is not None:
            parsed.append(timestamp)
    if parsed:
        return max(parsed).isoformat()
    for value in values:
        if value is not None:
            return str(value)
    return None


# --------------------------------------------------------------------------
# Etapas del funnel
# --------------------------------------------------------------------------
def funnel_raw_valid(df: pd.DataFrame) -> dict:
    """Conteos RAW/VALID_BARS por TF (meta-conteos, no eventos temporales auditados)."""
    n = len(df)
    valid = int(((df["high"] >= df["low"]) & df[["open", "high", "low", "close"]].notna().all(axis=1)).sum())
    return {"raw_bars": n, "valid_bars": valid}


def funnel_fvg_ob(df: pd.DataFrame, tf: str) -> list[dict]:
    rows = df[["open", "high", "low", "close"]].copy()
    rows["time"] = df["bar"].tolist()
    rows = rows.to_dict("records")
    fvg = detect_fvg(rows, timeframe=tf, symbol="EURUSD")
    ob = detect_order_blocks(rows, timeframe=tf, symbol="EURUSD")
    relations = relate_fvg_ob(fvg, ob, max_bars_apart=20, same_direction=True, causal_mode="strict")
    known_ids = {x.id for x in fvg} | {x.id for x in ob}
    time_by_index = {int(i): df["time"].iloc[i] for i in range(len(df))}

    records = []
    for item in fvg:
        obs, cand, conf, trad = _obs_time(item, time_by_index)
        records.append({"stage": "FVG", "id": item.id, "accepted": True,
                         "direction": item.direction, "timeframe": tf,
                         "observation_time": obs, "candidate_time": cand,
                         "confirmation_time": conf, "tradable_time": trad,
                         "requires_parent": False})
    for item in ob:
        obs, cand, conf, trad = _obs_time(item, time_by_index)
        records.append({"stage": "OB", "id": item.id, "accepted": True,
                         "direction": item.direction, "timeframe": tf,
                         "observation_time": obs, "candidate_time": cand,
                         "confirmation_time": conf, "tradable_time": trad,
                         "requires_parent": False})
    related_fvg = {r.fvg_id for r in relations}
    for item in fvg:
        if item.id not in related_fvg:
            obs, _, _, _ = _obs_time(item, time_by_index)
            records.append({"stage": "CONFLUENCE", "id": f"FVG_NO_REL_{item.id}",
                             "accepted": False, "direction": item.direction, "timeframe": tf,
                             "rejection_reason": "NO_OB_CAUSAL",
                             "observation_time": obs, "requires_parent": False})
    fvg_by_id = {item.id: item for item in fvg}
    for rel in relations:
        rec_ob = ob_dict(ob, rel.ob_id)
        rec_fvg = fvg_by_id.get(rel.fvg_id)
        if rec_fvg is None:
            continue
        fvg_obs, fvg_cand, fvg_conf, fvg_trad = _obs_time(rec_fvg, time_by_index)
        ob_obs, ob_cand, ob_conf, ob_trad = _obs_time(rec_ob, time_by_index)
        parent_time = ob_obs or ob_conf or ob_cand
        # La relación existe cuando ambos objetos ya son observables. Su
        # candidate_time no puede preceder a la confirmación del padre OB.
        cand = _latest_time(fvg_cand, ob_cand, parent_time)
        conf = _latest_time(fvg_conf, ob_conf, cand)
        trad = _latest_time(fvg_trad, ob_trad, conf)
        obs = _latest_time(fvg_obs, ob_obs, trad, conf)
        records.append({"stage": "CONFLUENCE", "id": f"{rel.fvg_id}__{rel.ob_id}",
                         "accepted": True, "direction": rel.direction, "timeframe": tf,
                         "observation_time": obs, "candidate_time": cand,
                         "confirmation_time": conf, "tradable_time": trad,
                         "requires_parent": True, "parent_id": rel.ob_id,
                         "parent_time": parent_time,
                         "lineage_valid": rel.ob_id in known_ids})
        records.append({"stage": "LINEAGE", "id": f"LINEAGE_{rel.fvg_id}__{rel.ob_id}",
                        "accepted": True, "direction": rel.direction, "timeframe": tf,
                        "observation_time": obs, "candidate_time": cand,
                        "confirmation_time": conf, "tradable_time": trad,
                        "parent_id": rel.ob_id, "parent_time": parent_time,
                        "lineage_valid": rel.ob_id in known_ids, "requires_parent": True})
    return records


def ob_dict(ob_list, oid):
    for o in ob_list:
        if o.id == oid:
            return o
    return ob_list[0]


def funnel_sequence(df: pd.DataFrame, tf: str) -> list[dict]:
    cfg = SeqConfig(structure_mode="canonical_bos", max_active_chains=128)
    raw = run_sequential(df, cfg, symbol="EURUSD", timeframe=tf)
    chains: list = list(raw)
    time_by_index = {int(i): df["time"].iloc[i] for i in range(len(df))}
    records = []
    # Estructura semilla (liquidity pools) como etapa STRUCTURE
    for ch in chains:
        for nd in ch.nodes:
            obs = time_by_index.get(int(nd.bar))
            obs_s = _time_string(obs) if obs is not None else str(int(nd.bar))
            raw_stage_name = nd.stage.value
            # RETEST es una subetapa secuencial, pero no una etapa pública de
            # FunnelAudit. Se proyecta a SEQUENCE sin perder su identidad.
            stage_name = "SEQUENCE" if raw_stage_name == "RETEST" else raw_stage_name
            # ID atómico estable: la raíz del pool identifica la cadena causal;
            # chain_id conserva compatibilidad, pero no es la identidad lógica.
            root_id = str(ch.nodes[0].object_id) if ch.nodes else str(ch.chain_id)
            rec = {"stage": stage_name, "id": f"{tf}:SEQ:{root_id}:{stage_name}",
                   "accepted": True, "direction": ch.direction, "timeframe": tf,
                   "observation_time": obs_s,
                   "candidate_time": obs_s, "confirmation_time": obs_s, "tradable_time": obs_s,
                   "requires_parent": False, "atomic": True,
                   "sequence_stage": raw_stage_name}
            records.append(rec)
        # Una cadena abierta/expirada no es un evento atómico: su estado final
        # cambia si el dataset recibe barras posteriores. Solo la terminación
        # completa tiene identidad y observation_time estables para FULL/PREFIX.
        chain_obs = time_by_index.get(ch.last_bar)
        chain_obs_s = _time_string(chain_obs) if chain_obs is not None else str(ch.last_bar)
        aggregate = {"stage": "SEQUENCE", "id": f"{tf}:SEQ:{root_id}:COMPLETE",
                     "accepted": ch.status == "COMPLETE",
                     "rejection_reason": None if ch.status == "COMPLETE" else "INVALID_DATA",
                     "direction": ch.direction, "timeframe": tf,
                     "observation_time": chain_obs_s, "requires_parent": False,
                     "atomic": ch.status == "COMPLETE"}
        if ch.status == "COMPLETE":
            # El evento terminal se observa en last_bar y debe satisfacer el
            # contrato temporal completo del stage SEQUENCE.
            aggregate.update(candidate_time=chain_obs_s,
                             confirmation_time=chain_obs_s,
                             tradable_time=chain_obs_s)
        records.append(aggregate)
    return records


def funnel_mtf_navigation(frames: dict[str, pd.DataFrame]) -> list[dict]:
    h1 = frames["H1"]
    nav = MTFNavigator(frames, NavigatorConfig(precompute_sequences=PRECOMPUTE, sequence_tf="H1"))
    records = []
    for i in range(500, len(h1), SAMPLE_EVERY):
        t = h1["time"].iloc[i]
        st = nav.navigate(decision_time=t, exec_tf="H1")
        records.append({"stage": "MTF_NAVIGATION", "id": f"nav_{i}",
                         "accepted": st.status == "OK",
                         "rejection_reason": None if st.status == "OK" else "CONTRACT_VIOLATION",
                         "timeframe": "H1", "observation_time": str(t),
                         "candidate_time": str(t), "confirmation_time": str(t),
                         "tradable_time": str(t), "direction": 0, "requires_parent": False})
    return records


# --------------------------------------------------------------------------
# PREFIX check (evento atómico, filtrado por tiempo)
# --------------------------------------------------------------------------
def _as_utc_timestamp(value) -> pd.Timestamp | None:
    """Normaliza timestamps antes de comparar el corte FULL/PREFIX."""
    if value is None:
        return None
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed)


def _atomic_events(
    records: list[dict], cutoff=None
) -> set[tuple[str, str, str]]:
    """Devuelve átomos namespaced por ``timeframe``, etapa e ID estable.

    ``atomic=False`` se reserva para agregados parciales (por ejemplo una cadena
    que aún puede crecer); incluirlos haría que el mismo ID representara estados
    distintos entre FULL y PREFIX. El corte usa tiempo normalizado, no texto.
    """
    cutoff_ts = _as_utc_timestamp(cutoff)
    events = set()
    for record in records:
        if record.get("atomic", True) is False:
            continue
        if cutoff_ts is not None:
            observation_ts = _as_utc_timestamp(record.get("observation_time"))
            if observation_ts is None or observation_ts > cutoff_ts:
                continue
        events.add((str(record.get("timeframe", "")),
                    str(record["stage"]), str(record["id"])))
    return events


def _prefix_event_delta(
    full: list[dict], prefix: list[dict], cutoff
) -> tuple[set[tuple[str, str, str]], set[tuple[str, str, str]]]:
    """Compara exactamente los átomos observables: (missing, extra)."""
    full_events = _atomic_events(full, cutoff)
    prefix_events = _atomic_events(prefix, cutoff)
    return full_events - prefix_events, prefix_events - full_events


def funnel_prefix_invariance(frames: dict[str, pd.DataFrame]) -> dict:
    """Contrato A7 §Prefijo: bars[:t] debe producir los mismos eventos atómicos
    (con observation_time <= t) que el dataset completo.

    Unidad lógica = evento atómico (stage, id), no cadena entera. Truncar el
    dataset no debe alterar eventos confirmados antes de t. run_sequential es
    PIT-stable por evento (probe: missing=0 filtrando por bar<=k).
    """
    result = {"prefix_ratio": PREFIX_RATIO, "by_timeframe": {}, "sequence": {}}
    for tf in ("H1", "H4", "D1"):
        full = funnel_fvg_ob(frames[tf], tf)
        full += funnel_sequence(frames[tf], tf)
        n = len(frames[tf]); k = int(n * PREFIX_RATIO)
        cutoff = frames[tf]["time"].iloc[k - 1]
        prefix = funnel_fvg_ob(frames[tf].iloc[:k], tf)
        prefix += funnel_sequence(frames[tf].iloc[:k], tf)
        missing, extra = _prefix_event_delta(full, prefix, cutoff)
        # Clasificar missing por etapa para diagnóstico
        by_stage = {}
        for _, s, _ in missing:
            by_stage[s] = by_stage.get(s, 0) + 1
        extra_by_stage = {}
        for _, s, _ in extra:
            extra_by_stage[s] = extra_by_stage.get(s, 0) + 1
        result["by_timeframe"][tf] = {
            "full_events": len(_atomic_events(full)),
            "full_in_window": len(_atomic_events(full, cutoff)),
            "prefix_events": len(_atomic_events(prefix)),
            "missing_in_prefix": len(missing),
            "missing_by_stage": by_stage,
            "extra_in_prefix": len(extra),
            "extra_by_stage": extra_by_stage,
            "prefix_invariant": not missing and not extra,
        }
    # Sequence (mismo método, por evento atómico)
    full_seq = funnel_sequence(frames["H1"], "H1")
    n = len(frames["H1"]); k = int(n * PREFIX_RATIO)
    cutoff = frames["H1"]["time"].iloc[k - 1]
    pref_seq = funnel_sequence(frames["H1"].iloc[:k], "H1")
    missing, extra = _prefix_event_delta(full_seq, pref_seq, cutoff)
    result["sequence"] = {
        "full_events": len(_atomic_events(full_seq)),
        "full_in_window": len(_atomic_events(full_seq, cutoff)),
        "prefix_events": len(_atomic_events(pref_seq)),
        "missing_in_prefix": len(missing),
        "extra_in_prefix": len(extra),
        "prefix_invariant": not missing and not extra,
    }
    return result


# --------------------------------------------------------------------------
# Runner principal
# --------------------------------------------------------------------------
def _run_funnel(records: list[dict]) -> dict:
    result, summaries = FunnelAudit(audit_id="A7_FUNNEL").run(records)
    metrics = result.metrics
    return {
        "audit_status": result.status.value,
        "input_count": result.input_count,
        "accepted_count": result.accepted_count,
        "rejected_count": result.rejected_count,
        "audit_score": metrics.get("audit_score"),
        # OE-A7.6/A7.7: conservar en cada sección las distribuciones que
        # calcula FunnelAudit, sin recalcularlas ni ocultar findings.
        "rejection_reason_counts": dict(metrics.get("rejection_reason_counts") or {}),
        "timeframe_counts": dict(metrics.get("timeframe_counts") or {}),
        "extra_stage_counts": dict(metrics.get("extra_stage_counts") or {}),
        "n_findings": len(result.findings),
        "findings": [{"code": f.code, "severity": f.severity, "message": f.message,
                     "stage": f.stage, "record_id": f.record_id} for f in result.findings],
        "stages": [{"stage": s.stage, "input_count": s.input_count,
                    "accepted_count": s.accepted_count, "rejected_count": s.rejected_count,
                    "duplicate_count": s.duplicate_count, "orphan_count": s.orphan_count,
                    "temporal_violation_count": s.temporal_violation_count} for s in summaries],
    }


def main() -> dict:
    frames = {tf: _load_tf(tf) for tf in ("H1", "H4", "D1")}
    provenance = _verify_provenance()
    all_records: list[dict] = []
    funnel_sections: dict = {}
    bars_by_tf: dict = {}

    for tf in ("H1", "H4", "D1"):
        bars_by_tf[tf] = funnel_raw_valid(frames[tf])
        recs = funnel_fvg_ob(frames[tf], tf) + funnel_sequence(frames[tf], tf)
        funnel_sections.setdefault("by_tf", {})[tf] = _run_funnel(recs)
        all_records.extend(recs)
    mtf_recs = funnel_mtf_navigation(frames)
    funnel_sections["mtf_navigation"] = _run_funnel(mtf_recs)
    all_records.extend(mtf_recs)

    overall = _run_funnel(all_records)
    prefix = funnel_prefix_invariance(frames)

    report = {
        "contract_version": CONTRACT_VERSION,
        "gate": "A7",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commit": _git_commit(),
        "git_status": _git_status(),
        "dataset": "dukascopy EURUSD 20Y (canonico)",
        "provenance": provenance,
        "provenance_ok": all(v["match"] for v in provenance.values()),
        "config": {"sample_every": SAMPLE_EVERY, "precompute_sequences": PRECOMPUTE,
                    "relation_rule": "STRICT FVG_OB_CAUSAL", "causal_mode": "strict",
                    "prefix_ratio": PREFIX_RATIO},
        "symbol": "EURUSD",
        "policy": "AUDIT_FUNNEL_NO_PNL_NO_ENTRY",
        "bars_by_tf": bars_by_tf,
        "funnel_by_tf": funnel_sections.get("by_tf", {}),
        "mtf_navigation": funnel_sections["mtf_navigation"],
        "aggregated_status": overall["audit_status"],
        "aggregated_findings": overall["n_findings"],
        "prefix_invariance": prefix,
    }
    # Checksum determinista: excluye generated_at (campo no determinista por contrato A7 §5.1).
    report_for_checksum = {k: v for k, v in report.items() if k != "generated_at"}
    report_str = json.dumps(report_for_checksum, default=str, sort_keys=True)
    report["report_checksum_sha256"] = hashlib.sha256(report_str.encode()).hexdigest()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUT_DIR / f"mtf_seq_funnel_a7_{stamp}.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps({
        "out": str(out_path),
        "commit": report["commit"], "git_status": report["git_status"],
        "provenance_ok": report["provenance_ok"],
        "aggregated_status": report["aggregated_status"],
        "prefix_sequence_invariant": prefix["sequence"]["prefix_invariant"],
        "report_checksum": report["report_checksum_sha256"],
    }, indent=2))
    return report


if __name__ == "__main__":
    main()
