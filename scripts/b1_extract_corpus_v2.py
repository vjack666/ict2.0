#!/usr/bin/env python3
"""
B1-O1 — Extracción canónica del corpus CANDIDATE_SETUP para EURUSD.

REGLAS CRÍTICAS:
- Usa exclusivamente engine.mechanical_signal_assessment.assess_mechanical_signal()
- No usa "cada BOS = candidato"
- Si falta evidencia M15 → rechazo real (SWEEP_EVIDENCE_UNAVAILABLE, etc.)
- candidate_id determinista a partir de evidencia causal, NO uuid4()
- Solo datos con source_time <= decision_time
- No inventa entry_time, SL, TP, probability, confirmed, net_R
- DESIGN es [2006-01-01, 2016-01-01); HOLDOUT es [2021-01-01, +∞)
- HOLDOUT nunca se reclasifica como DESIGN para B1-O1

PRODUCTO:
- Corpus B1-O1: data/b1/corpus_design_canonical.jsonl
- Manifiesto: data/b1/corpus_design_canonical_manifest.json
- Resumen: reports/b1/corpus_design_summary.json
- Log: logs/b1/extract_design_canonical.log
"""

import sys
from pathlib import Path
from typing import Any
from datetime import datetime, timezone
from collections import Counter

import numpy as np
import pandas as pd
import hashlib
import json
import logging

# ─────────────────────────────────────────────────────────────────────────────
# PATH CONFIG
# ─────────────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "raw" / "EURUSD"
B1_DATA_DIR = ROOT / "data" / "b1"
REPORTS_DIR = ROOT / "reports" / "b1"
LOG_DIR = ROOT / "logs" / "b1"

DETECTORS = ROOT / "detectors"
if str(DETECTORS) not in sys.path:
    sys.path.insert(0, str(DETECTORS))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.market_features import build_features
from engine.mechanical_signal_assessment import assess_mechanical_signal

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "extract_design_canonical.log"),
    ],
)
logger = logging.getLogger("b1_extract_canonical")


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────────────────────

MANIFEST_PATH = ROOT / "B1_DATA_MANIFEST_V1.json"
M15_FRAME = DATA_DIR / "EURUSD_M15.parquet"
# Fuente B1-O1 inmutable y específica del tramo DESIGN. El parquet operativo
# M15 comienza en 2022 y no puede ser usado para este objetivo.
M15_DESIGN = DATA_DIR / "EURUSD_M15_2006_2015.parquet"
H1_FRAME = DATA_DIR / "EURUSD_H1.parquet"
H4_FRAME = DATA_DIR / "EURUSD_H4.parquet"
D1_FRAME = DATA_DIR / "EURUSD_D1.parquet"

# Contrato B1-O1: intervalos semiabiertos para que las fronteras no dependan
# de una hora final artificial. VALIDATION queda fuera de esta extracción y
# HOLDOUT jamás puede aparecer como input ni como decision_time.
DESIGN_START = pd.Timestamp("2006-01-01 00:00:00", tz="UTC")
DESIGN_END_EXCLUSIVE = pd.Timestamp("2016-01-01 00:00:00", tz="UTC")
HOLDOUT_START = pd.Timestamp("2021-01-01 00:00:00", tz="UTC")

# Alias explícitos para consumidores B1 existentes; B1_END es el último
# instante permitido, no el límite de inclusión del filtro.
B1_START = DESIGN_START
B1_END = DESIGN_END_EXCLUSIVE - pd.Timedelta(nanoseconds=1)


def _utc_timestamp(value: Any) -> pd.Timestamp:
    """Normaliza una frontera sin aceptar timestamps NaT."""
    result = pd.Timestamp(value)
    if pd.isna(result):
        raise ValueError(f"Timestamp inválido: {value!r}")
    return result.tz_localize("UTC") if result.tzinfo is None else result.tz_convert("UTC")


def is_design_time(value: Any) -> bool:
    """True solo dentro del periodo contractual DESIGN de B1-O1."""
    timestamp = _utc_timestamp(value)
    return DESIGN_START <= timestamp < DESIGN_END_EXCLUSIVE


def assert_design_time(value: Any) -> pd.Timestamp:
    """Fail closed: impide que VALIDATION o HOLDOUT entren al extractor B1."""
    timestamp = _utc_timestamp(value)
    if not is_design_time(timestamp):
        split = "HOLDOUT" if timestamp >= HOLDOUT_START else "OUTSIDE_DESIGN"
        raise ValueError(
            f"B1-O1 DESIGN_ONLY violation ({split}): {timestamp}; "
            f"allowed=[{DESIGN_START}, {DESIGN_END_EXCLUSIVE})"
        )
    return timestamp


def select_design_decision_times(times: pd.Series) -> pd.Series:
    """Selecciona únicamente decision_times del diseño y verifica el límite."""
    normalized = pd.to_datetime(times, utc=True, errors="coerce").dropna()
    selected = normalized[(normalized >= DESIGN_START) & (normalized < DESIGN_END_EXCLUSIVE)]
    if not selected.empty:
        assert all(is_design_time(value) for value in selected)
    return selected


def normalize_b1_time_column(values: pd.Series) -> pd.Series:
    """Normaliza timestamps B1 sin confundir epoch-ms con epoch-ns.

    El parquet inmutable M15 2006-2015 almacena epoch en milisegundos. Pandas
    asume nanosegundos para enteros si no se indica unidad, lo que lo desplaza
    falsamente a 1970 y puede vaciar o deformar el rango DESIGN.
    """
    numeric = pd.to_numeric(values, errors="coerce")
    if numeric.notna().any() and numeric.dropna().abs().median() >= 100_000_000_000:
        return pd.to_datetime(numeric, unit="ms", utc=True, errors="coerce")
    return pd.to_datetime(values, utc=True, errors="coerce")


def derive_h4_from_design_m15(m15: pd.DataFrame) -> pd.DataFrame:
    """Deriva H4 en memoria desde M15 DESIGN, sin escribir datos fuente."""
    source = m15.copy()
    time_col = "timestamp" if "timestamp" in source.columns else "time"
    source[time_col] = normalize_b1_time_column(source[time_col])
    source = source.dropna(subset=[time_col]).sort_values(time_col).set_index(time_col)
    volume_col = "volume" if "volume" in source.columns else "tick_volume"
    h4 = source.resample("4h", label="right", closed="right").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", volume_col: "sum",
    }).dropna(subset=["open", "high", "low", "close"]).reset_index()
    return h4.rename(columns={time_col: "time"})


# ─────────────────────────────────────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────────────────────────────────────

def load_parquet(path: Path) -> pd.DataFrame:
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    manifest_data = json.loads(MANIFEST_PATH.read_text())
    artifact = next((a for a in manifest_data if a["path"].endswith(path.name)), None)
    if artifact:
        assert sha == artifact["sha256"], f"Hash mismatch {path.name}"
        assert len(raw) == artifact["bytes"], f"Size mismatch {path.name}"
    df = pd.read_parquet(path)
    time_col = "timestamp" if "timestamp" in df.columns else "time" if "time" in df.columns else None
    if time_col is not None:
        df[time_col] = normalize_b1_time_column(df[time_col])
    logger.info(f"Cargado {path.name}: {len(df)} filas, hash verificado")
    return df


def snapshot_hash(snapshot: dict[str, Any]) -> str:
    content = json.dumps({
        "schema_version": snapshot.get("schema_version"),
        "status": snapshot.get("status"),
        "code": snapshot.get("code"),
        "symbol": snapshot.get("symbol"),
        "decision_time": snapshot.get("decision_time"),
        "m15_evidence": snapshot.get("m15_evidence"),
    }, sort_keys=True, default=str)
    return hashlib.sha256(content.encode()).hexdigest()


def deterministic_candidate_id(
    symbol: str,
    decision_time: str,
    context_direction: str | None,
    m15_evidence: dict[str, Any],
) -> str:
    sweep_ref = m15_evidence.get("sweep_time") or ""
    displacement_ref = m15_evidence.get("displacement_time") or ""
    structure_ref = m15_evidence.get("structure_time") or ""
    poi_ref = m15_evidence.get("poi_time") or ""
    retest_ref = m15_evidence.get("retest_time") or ""
    
    content = (
        f"{symbol}|{decision_time}|{context_direction or ''}|"
        f"{sweep_ref}|{displacement_ref}|{structure_ref}|{poi_ref}|{retest_ref}"
    )
    return hashlib.sha256(content.encode()).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# ENSAMBLADOR DE SNAPSHOT HISTÓRICO
# ─────────────────────────────────────────────────────────────────────────────

def build_historical_snapshot(
    m15_features: pd.DataFrame,
    h1_features: pd.DataFrame,
    h4_features: pd.DataFrame,
    decision_time: pd.Timestamp,
    symbol: str = "EURUSD",
) -> dict[str, Any]:
    def get_time_col(df):
        return "timestamp" if "timestamp" in df.columns else "time"
    
    m15_tc = get_time_col(m15_features)
    h1_tc = "timestamp" if "timestamp" in h1_features.columns else "time"
    h4_tc = "timestamp" if "timestamp" in h4_features.columns else "time"
    
    m15_times = pd.to_datetime(m15_features[m15_tc], utc=True, errors="coerce")
    if decision_time < m15_times.min() or decision_time > m15_times.max():
        return {
            "schema_version": "MT5_OPERATIONAL_SNAPSHOT_V1",
            "status": "BLOCKED",
            "code": "M15_DATA_UNAVAILABLE",
            "detail": f"decision_time fuera del rango M15: {decision_time}",
            "symbol": symbol,
            "decision_time": str(decision_time),
            "can_trade": False,
            "entry_authorized": False,
        }
    
    m15_mask = m15_features[m15_tc] <= decision_time
    h1_mask = h1_features[h1_tc] <= decision_time
    h4_mask = h4_features[h4_tc] <= decision_time
    
    m15_ctx = m15_features[m15_mask]
    h1_ctx = h1_features[h1_mask]
    h4_ctx = h4_features[h4_mask]
    
    if m15_ctx.empty:
        return {
            "schema_version": "MT5_OPERATIONAL_SNAPSHOT_V1",
            "status": "BLOCKED",
            "code": "M15_DATA_UNAVAILABLE",
            "detail": f"No hay velas M15 cerradas hasta {decision_time}",
            "symbol": symbol,
            "decision_time": str(decision_time),
            "can_trade": False,
            "entry_authorized": False,
        }
    
    m15_last = m15_ctx.iloc[-1]
    h1_last = h1_ctx.iloc[-1] if not h1_ctx.empty else None
    h4_last = h4_ctx.iloc[-1] if not h4_ctx.empty else None
    
    h4_bias = str(h4_last["bos_direction"]) if h4_last is not None and "bos_direction" in h4_ctx.columns else None
    h1_bias = str(h1_last["bos_direction"]) if h1_last is not None and "bos_direction" in h1_ctx.columns else None
    
    if h4_bias is None or h1_bias is None or h4_bias != h1_bias:
        context_direction = None
        h4_aligned = False
        h1_aligned = False
    else:
        context_direction = h4_bias
        h4_aligned = True
        h1_aligned = True
    
    m15_evidence = {}
    
    sweep_up = bool(m15_last.get("liquidity_sweep_up", False))
    sweep_down = bool(m15_last.get("liquidity_sweep_down", False))
    m15_evidence["sweep"] = True if (sweep_up or sweep_down) else False
    m15_evidence["sweep_time"] = str(m15_last.name)
    m15_evidence["sweep_direction"] = "up" if sweep_up else ("down" if sweep_down else None)
    m15_evidence["source"] = "detector_liquidity"
    
    if m15_evidence["sweep"]:
        disp_bull = bool(m15_last.get("displacement_bullish", False))
        disp_bear = bool(m15_last.get("displacement_bearish", False))
        m15_evidence["displacement"] = True if (disp_bull or disp_bear) else False
        m15_evidence["displacement_time"] = str(m15_last.name)
        m15_evidence["source"] = "detector_displacement"
    else:
        m15_evidence["displacement"] = False
        m15_evidence["displacement_time"] = None
        m15_evidence["source"] = "no_sweep"
    
    if m15_evidence.get("displacement"):
        bos = bool(m15_last.get("bos_dir", 0) != 0)
        choch = bool(m15_last.get("choch_dir", 0) != 0)
        m15_evidence["bos_or_choch"] = True if (bos or choch) else False
        m15_evidence["structure_time"] = str(m15_last.name)
        m15_evidence["source"] = "detector_structure"
    else:
        m15_evidence["bos_or_choch"] = False
        m15_evidence["structure_time"] = None
        m15_evidence["source"] = "no_displacement"
    
    if m15_evidence.get("bos_or_choch"):
        fvg = bool(m15_last.get("fvg_bullish", False) or m15_last.get("fvg_bearish", False))
        ob = bool(m15_last.get("ob_bullish", False) or m15_last.get("ob_bearish", False))
        m15_evidence["fvg_or_ob"] = True if (fvg or ob) else False
        m15_evidence["poi_time"] = str(m15_last.name)
        m15_evidence["source"] = "detector_fvg_ob"
    else:
        m15_evidence["fvg_or_ob"] = False
        m15_evidence["poi_time"] = None
        m15_evidence["source"] = "no_structure"
    
    if m15_evidence.get("fvg_or_ob"):
        fill_status = str(m15_last.get("fvg_fill_status", "unknown"))
        m15_evidence["retest"] = fill_status not in ("none", "unknown")
        m15_evidence["retest_time"] = str(m15_last.name)
        m15_evidence["source"] = "detector_retest"
    else:
        m15_evidence["retest"] = False
        m15_evidence["retest_time"] = None
        m15_evidence["source"] = "no_poi"
    
    snapshot = {
        "schema_version": "MT5_OPERATIONAL_SNAPSHOT_V1",
        "status": "READY",
        "policy": "OBSERVE_ONLY_NO_ORDER",
        "symbol": symbol,
        "decision_time": str(decision_time),
        "can_trade": False,
        "entry_authorized": False,
        "missing_timeframes": [],
        "context_state": {
            "layers": {
                "H4": {"timeframe": "H4", "last_time": str(h4_last.name) if h4_last is not None else None, "structure_bias": h4_bias},
                "H1": {"timeframe": "H1", "last_time": str(h1_last.name) if h1_last is not None else None, "structure_bias": h1_bias},
                "M15": {"timeframe": "M15", "last_time": str(m15_last.name), "structure_bias": str(m15_last.get("bos_direction", None))},
            }
        },
        "daily_motor": {
            "direction": context_direction,
            "context": {"constraints": {"allow_long": True, "allow_short": True}},
        },
        "m15_evidence": m15_evidence,
        "micro_confirmation": None,
    }
    
    return snapshot


# ─────────────────────────────────────────────────────────────────────────────
# EVALUACIÓN CANÓNICA
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_decision_time(
    m15_features: pd.DataFrame,
    h1_features: pd.DataFrame,
    h4_features: pd.DataFrame,
    decision_time: pd.Timestamp,
    symbol: str = "EURUSD",
) -> dict[str, Any]:
    decision_time = assert_design_time(decision_time)
    snap = build_historical_snapshot(m15_features, h1_features, h4_features, decision_time, symbol)
    assessment = assess_mechanical_signal(snap)
    
    result = {
        "decision_time": str(decision_time),
        "symbol": symbol,
        "snapshot_hash": snapshot_hash(snap),
        "phase2a_status": assessment.get("status"),
        "phase2a_code": assessment.get("code"),
        "phase2a_detail": assessment.get("detail"),
        "context_direction": assessment.get("context_direction"),
        "m15_evidence": snap.get("m15_evidence", {}),
        "source_refs": {
            "m15_file": str(M15_DESIGN),
            "h1_file": str(H1_FRAME),
            "h4_file": f"derived_in_memory_from:{M15_DESIGN}",
        },
        "candidate_id": None,
    }
    
    if assessment.get("status") == "CANDIDATE_SETUP":
        result["candidate_id"] = deterministic_candidate_id(
            symbol=symbol,
            decision_time=str(decision_time),
            context_direction=assessment.get("context_direction"),
            m15_evidence=snap.get("m15_evidence", {}),
        )
    
    return result


# ─────────────────────────────────────────────────────────────────────────────
# EXTRACCIÓN DEL CORPUS
# ─────────────────────────────────────────────────────────────────────────────

def extract_corpus_design():
    logger.info("=" * 70)
    logger.info("B1-O1 — Extracción canónica del corpus CANDIDATE_SETUP")
    logger.info("=" * 70)
    
    logger.info("Cargando frames...")
    m15 = load_parquet(M15_DESIGN)
    h1 = load_parquet(H1_FRAME)
    # H4_FRAME comienza en 2020. Para B1-O1 se deriva H4 reproduciblemente de
    # M15 DESIGN en memoria; el archivo fuente no se modifica.
    h4 = derive_h4_from_design_m15(m15)
    
    m15_tc = "timestamp" if "timestamp" in m15.columns else "time"
    h1_tc = "timestamp" if "timestamp" in h1.columns else "time"
    h4_tc = "timestamp" if "timestamp" in h4.columns else "time"
    
    m15_start = pd.to_datetime(m15[m15_tc], utc=True).min()
    m15_end = pd.to_datetime(m15[m15_tc], utc=True).max()
    h1_start = pd.to_datetime(h1[h1_tc], utc=True).min()
    h1_end = pd.to_datetime(h1[h1_tc], utc=True).max()
    h4_start = pd.to_datetime(h4[h4_tc], utc=True).min()
    h4_end = pd.to_datetime(h4[h4_tc], utc=True).max()
    
    valid_start = max(m15_start, h1_start, h4_start)
    valid_end = min(m15_end, h1_end, h4_end)
    
    logger.info(f"Rango M15:   {m15_start} -> {m15_end}  ({len(m15)} filas)")
    logger.info(f"Rango H1:    {h1_start} -> {h1_end}  ({len(h1)} filas)")
    logger.info(f"Rango H4:    {h4_start} -> {h4_end}  ({len(h4)} filas)")
    logger.info(f"Rango común: {valid_start} -> {valid_end}")
    logger.info(f"Duración común: {valid_end - valid_start}")
    logger.info(f"Años: {valid_start.year} -> {valid_end.year}")
    
    m15_times = pd.to_datetime(m15[m15_tc], utc=True, errors="coerce").dropna()
    # El rango común es una condición de disponibilidad; el contrato temporal
    # es una condición independiente y obligatoria.
    decision_times = select_design_decision_times(
        m15_times[(m15_times >= valid_start) & (m15_times <= valid_end)]
    )
    if decision_times.empty:
        raise RuntimeError(
            "B1-O1 no tiene cobertura común dentro de DESIGN 2006-2015; "
            "no se permite sustituirla por datos de HOLDOUT."
        )
    
    logger.info(f"Decision times en rango válido: {len(decision_times)}")
    
    logger.info("Evaluando decision times con evaluador canónico...")
    results = []
    for i, dt in enumerate(decision_times):
        if i % 10000 == 0 and i > 0:
            logger.info(f"  Progreso: {i}/{len(decision_times)} ({100*i/len(decision_times):.1f}%)")
        result = evaluate_decision_time(m15, h1, h4, dt, "EURUSD")
        results.append(result)
    
    logger.info(f"Evaluación completada: {len(results)} resultados")
    
    candidates = [r for r in results if r["phase2a_status"] == "CANDIDATE_SETUP"]
    rejections = [r for r in results if r["phase2a_status"] != "CANDIDATE_SETUP"]
    
    logger.info(f"CANDIDATE_SETUP: {len(candidates)}")
    logger.info(f"Rechazos: {len(rejections)}")
    
    rejection_counts = Counter(r["phase2a_code"] for r in rejections)
    logger.info("Resumen de rechazos:")
    for code, count in sorted(rejection_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {code}: {count}")
    
    for r in results:
        assert_design_time(r["decision_time"])
    
    candidate_ids = [r["candidate_id"] for r in candidates]
    duplicates = [cid for cid, count in Counter(candidate_ids).items() if count > 1]
    if duplicates:
        raise ValueError(f"Duplicate candidate_ids encontrados: {duplicates}")
    
    logger.info("Guardando resultados...")
    
    corpus_path = B1_DATA_DIR / "corpus_design_canonical.jsonl"
    with open(corpus_path, "w", encoding="utf-8") as f:
        for c in candidates:
            record = {
                "candidate_id": c["candidate_id"],
                "decision_time": c["decision_time"],
                "symbol": c["symbol"],
                "context_direction": c["context_direction"],
                "phase2a_status": c["phase2a_status"],
                "phase2a_code": c["phase2a_code"],
                "snapshot_hash": c["snapshot_hash"],
                "m15_evidence": c["m15_evidence"],
                "source_refs": c["source_refs"],
                "dataset_manifest_hash": hashlib.sha256(
                    ROOT.joinpath("B1_DATA_MANIFEST_V1.json").read_bytes()
                ).hexdigest(),
                "code_commit": "bbee8963115ff32399b08db22930852a5c1e8b4b",
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    
    logger.info(f"Corpus guardado: {corpus_path} ({len(candidates)} candidatos)")
    
    manifest = {
        "corpus_path": str(corpus_path),
        "period": "DESIGN",
        "valid_range": {
            "start": str(valid_start),
            "end": str(valid_end),
            "years": f"{valid_start.year}-{valid_end.year}",
        },
        "candidate_count": len(candidates),
        "rejection_count": len(rejections),
        "rejection_codes": dict(rejection_counts),
        "dataset_manifest_hash": hashlib.sha256(
            ROOT.joinpath("B1_DATA_MANIFEST_V1.json").read_bytes()
        ).hexdigest(),
        "code_commit": "bbee8963115ff32399b08db22930852a5c1e8b4b",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    manifest_path = B1_DATA_DIR / "corpus_design_canonical_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Manifiesto guardado: {manifest_path}")
    
    summary = {
        "valid_range": {"start": str(valid_start), "end": str(valid_end)},
        "total_decision_times": len(decision_times),
        "candidates": len(candidates),
        "rejections": len(rejections),
        "rejection_codes": dict(rejection_counts),
        "duplicates": len(duplicates),
        "holdout_touched": False,
        "generator": "engine.mechanical_signal_assessment.assess_mechanical_signal",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    summary_path = REPORTS_DIR / "corpus_design_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Resumen guardado: {summary_path}")
    logger.info("=" * 70)
    logger.info("RESUMEN")
    logger.info(f"CANDIDATES: {len(candidates)}")
    logger.info(f"REJECTIONS: {len(rejections)}")
    logger.info(f"DUPLICATES: 0")
    logger.info(f"HOLDOUT_TOUCHED: false")
    logger.info("=" * 70)
    
    return candidates, rejections, results


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        candidates, rejections, all_results = extract_corpus_design()
        print(f"\n{'='*70}")
        print("EXTRACCIÓN COMPLETADA")
        print(f"{'='*70}")
        print(f"CANDIDATE_SETUP: {len(candidates)}")
        print(f"Rechazos: {len(rejections)}")
        print(f"Corpus: {B1_DATA_DIR / 'corpus_design_canonical.jsonl'}")
        print(f"Manifiesto: {B1_DATA_DIR / 'corpus_design_canonical_manifest.json'}")
        print(f"Resumen: {REPORTS_DIR / 'corpus_design_summary.json'}")
        print(f"Log: {LOG_DIR / 'extract_design_canonical.log'}")
    except Exception as e:
        logger.error(f"FALLA CRÍTICA: {e}")
        print(f"\nFALLA CRÍTICA: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
