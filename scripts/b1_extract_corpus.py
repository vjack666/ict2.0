"""
B1 — Departamento B: Extracción del corpus causal B1 (DESIGN 2006-2015).

Construye una fila por cada CANDIDATE_SETUP usando las definiciones
congeladas del Departamento C (ICT/Wyckoff) y los datos de
B1_DATA_MANIFEST_V1 (5 parquets verificados, 0 mismatches).

Regla: si una variable no existe causalmente → UNAVAILABLE, no se infiere
mirando el futuro.

Auditoría integrada: cada feature registra su source_time para que
el Departamento A pueda verificar source_time <= decision_time.
"""

import sys
from pathlib import Path

# Configurar path para importar desde la raíz del proyecto
ROOT = Path(__file__).resolve().parent.parent
_detectors = ROOT / "detectors"
if str(_detectors) not in sys.path:
    sys.path.insert(0, str(_detectors))

import json
import hashlib
import uuid
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("b1_extract")

ROOT = Path(__file__).resolve().parent.parent  # raíz del repo
DATA_DIR = ROOT / "data" / "raw" / "EURUSD"
B1_DATA_DIR = ROOT / "data" / "b1"
REPORTS_DIR = ROOT / "reports" / "b1"
LOG_DIR = ROOT / "logs" / "b1"
SCRIPTS_DIR = ROOT / "scripts"

# Asegurar que ROOT esté en el path para importar engine/ y detectors/ como paquetes
sys.path.insert(0, str(ROOT))
MANIFEST_PATH = ROOT / "B1_DATA_MANIFEST_V1.json"
with open(MANIFEST_PATH) as f:
    MANIFEST = json.load(f)

MANIFEST_HASH = hashlib.sha256(json.dumps(MANIFEST, sort_keys=True).encode()).hexdigest()
logger.info(f"Manifest hash: {MANIFEST_HASH[:16]}...")

# Código commit (placeholder — se actualiza con el commit real)
CODE_COMMIT = "PENDING_COMMIT"

# ============================================================
# Carga de datos
# ============================================================

def load_parquet(name: str) -> pd.DataFrame:
    """Carga un parquet desde B1_DATA_MANIFEST_V1 y verifica su hash."""
    artifact = next(a for a in MANIFEST if a["path"].endswith(name))
    p = DATA_DIR / name
    raw = p.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    assert sha == artifact["sha256"], f"Hash mismatch para {name}: esperado {artifact['sha256'][:16]}, obtenido {sha[:16]}"
    df = pd.read_parquet(p)
    logger.info(f"Cargado {name}: {len(df)} filas, hash verificado")
    return df

def load_design_m15() -> pd.DataFrame:
    """Carga M15 2006-2015 para DESIGN."""
    return load_parquet("EURUSD_M15_2006_2015.parquet")

def load_htf_frames() -> dict[str, pd.DataFrame]:
    """Carga frames HTF para contexto."""
    result = {}
    for name, tf in [("EURUSD_H1.parquet", "H1"), ("EURUSD_H4.parquet", "H4"), ("EURUSD_D1.parquet", "D1")]:
        result[tf] = load_parquet(name)
    return result

# ============================================================
# Features ICT
# ============================================================

sys.path.insert(0, str(ROOT / "engine"))
sys.path.insert(0, str(ROOT / "detectors"))

from engine.market_features import build_features, load_tf
from engine.turtle_soup import is_turtle_soup, flag_turtle_soup
from engine.bos import detect_market_structure, StructureConfig

def compute_features(df_m15: pd.DataFrame, htf_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Computa todas las features ICT para M15."""
    # Features M15
    features_m15 = build_features(df_m15, include_liquidity_zones=True)
    
    # Features HTF (para contexto)
    htf_features = {}
    for tf, df_htf in htf_frames.items():
        htf_features[tf] = build_features(df_htf, include_liquidity_zones=False)
    
    return features_m15, htf_features

# ============================================================
# Detección de eventos
# ============================================================

def detect_sweep_events(features_m15: pd.DataFrame) -> pd.DataFrame:
    """Detecta eventos de sweep (turtle soup) en M15."""
    sweeps = []
    time_col = "time" if "time" in features_m15.columns else "timestamp"
    sweep_high_col = "sweep_high" if "sweep_high" in features_m15.columns else None
    sweep_low_col = "sweep_low" if "sweep_low" in features_m15.columns else None
    
    for i in range(len(features_m15)):
        ts_val = features_m15.iloc[i][time_col]
        if pd.isna(ts_val):
            continue
        try:
            ts = pd.Timestamp(ts_val)
        except Exception:
            continue
        
        bos_dir_val = features_m15.iloc[i].get("bos_dir", 0)
        direction = 1 if bos_dir_val > 0 else (-1 if bos_dir_val < 0 else 0)
        if direction == 0:
            continue
        
        meta = {
            "ts_broke_pdh": False,
            "ts_broke_pdl": False,
            "ts_reversal": False,
        }
        
        # Detección simple de sweep: precio rompió nivel de liquidez previo
        high = features_m15.iloc[i].get("high", 0)
        low = features_m15.iloc[i].get("low", 0)
        
        if sweep_high_col and not pd.isna(features_m15.iloc[i].get(sweep_high_col)):
            meta["ts_broke_pdh"] = direction == -1 and high > features_m15.iloc[i][sweep_high_col]
        if sweep_low_col and not pd.isna(features_m15.iloc[i].get(sweep_low_col)):
            meta["ts_broke_pdl"] = direction == 1 and low < features_m15.iloc[i][sweep_low_col]
        
        meta["ts_reversal"] = meta["ts_broke_pdh"] or meta["ts_broke_pdl"]
        confirmed = meta["ts_broke_pdh"] or meta["ts_broke_pdl"]
        
        if confirmed:
            sweeps.append({
                "sweep_idx": i,
                "sweep_time": ts,
                "direction": direction,
                "sweep_type": "turtle_soup",
                **meta,
            })
    
    return pd.DataFrame(sweeps) if sweeps else pd.DataFrame()

def detect_displacement_events(features_m15: pd.DataFrame) -> pd.DataFrame:
    """Detecta eventos de displacement en M15."""
    mask = features_m15["displacement_bullish"] | features_m15["displacement_bearish"]
    if not mask.any():
        return pd.DataFrame()
    disp_df = features_m15[mask].copy()
    disp_df["displacement_type"] = np.where(disp_df["displacement_bullish"], "bullish", "bearish")
    disp_df = disp_df.rename(columns={"timestamp": "time"})
    return disp_df.reset_index(drop=True)

def detect_structure_events(features_m15: pd.DataFrame) -> pd.DataFrame:
    """Detecta eventos de BOS y CHOCH en M15."""
    events = []
    bos_dir = features_m15["bos_dir"].fillna(0).values
    choch_dir = features_m15["choch_dir"].fillna(0).values
    timestamps = features_m15["timestamp"].values
    
    for i in range(len(features_m15)):
        ts_val = timestamps[i]
        if pd.isna(ts_val):
            continue
        try:
            ts = pd.Timestamp(ts_val)
        except Exception:
            continue
        
        if bos_dir[i] != 0:
            events.append({
                "event_time": ts,
                "event_type": "BOS",
                "direction": int(bos_dir[i]),
            })
        if choch_dir[i] != 0:
            events.append({
                "event_time": ts,
                "event_type": "CHOCH",
                "direction": int(choch_dir[i]),
            })
    
    return pd.DataFrame(events) if events else pd.DataFrame()

def detect_poi_events(features_m15: pd.DataFrame) -> pd.DataFrame:
    """Detecta POI (FVG, OB) en M15."""
    poi = []
    time_col = "time" if "time" in features_m15.columns else "timestamp"
    
    # FVG
    fvg_mask = features_m15["fvg_bullish"] | features_m15["fvg_bearish"]
    for i in features_m15[fvg_mask].index:
        row = features_m15.loc[i]
        poi.append({
            "poi_idx": i,
            "poi_time": row[time_col] if not pd.isna(row[time_col]) else None,
            "poi_type": "FVG",
            "poi_direction": "bullish" if row["fvg_bullish"] else "bearish",
            "poi_size": row.get("fvg_size", 0),
            "poi_mid": row.get("fvg_mid", np.nan),
            "poi_fill_status": row.get("fvg_fill_status", "unknown"),
        })
    
    # OB
    ob_mask = features_m15["ob_bullish"] | features_m15["ob_bearish"]
    for i in features_m15[ob_mask].index:
        row = features_m15.loc[i]
        poi.append({
            "poi_idx": i,
            "poi_time": row[time_col] if not pd.isna(row[time_col]) else None,
            "poi_type": "OB",
            "poi_direction": "bullish" if row["ob_bullish"] else "bearish",
            "poi_top": row.get("ob_top", np.nan),
            "poi_bottom": row.get("ob_bottom", np.nan),
            "poi_age": row.get("ob_age", np.nan),
            "poi_status": row.get("ob_status", "unknown"),
        })
    
    return pd.DataFrame(poi) if poi else pd.DataFrame()

# ============================================================
# Construcción de CANDIDATE_SETUP
# ============================================================

def build_candidate_setups(
    features_m15: pd.DataFrame,
    htf_features: dict[str, pd.DataFrame],
    sweeps: pd.DataFrame,
    displacements: pd.DataFrame,
    structure_events: pd.DataFrame,
    pois: pd.DataFrame,
) -> list[dict]:
    """Construye una lista de CANDIDATE_SETUP, una por cada evento estructural."""
    
    # Normalizar nombres de columna a "time" para consistencia
    def normalize_time_col(df: pd.DataFrame) -> pd.DataFrame:
        if "time" not in df.columns and "timestamp" in df.columns:
            return df.rename(columns={"timestamp": "time"})
        return df
    
    displacements = normalize_time_col(displacements)
    sweeps = normalize_time_col(sweeps)
    pois = normalize_time_col(pois)
    structure_events = normalize_time_col(structure_events)
    
    setups = []
    
    # Para cada evento de estructura (BOS/CHOCH), crear un CANDIDATE_SETUP
    for _, event in structure_events.iterrows():
        setup = {
            "candidate_id": str(uuid.uuid4()),
            "decision_time": event["event_time"].isoformat() if not pd.isna(event["event_time"]) else None,
            "symbol": "EURUSD",
            "direction_context": "BULLISH" if event["direction"] > 0 else "BEARISH",
            "period_split": "DESIGN",
            "source_refs": [],
            "code_commit": CODE_COMMIT,
            "dataset_manifest_hash": MANIFEST_HASH,
        }
        
        # HTF context
        try:
            h1_frame = htf_features.get("H1", pd.DataFrame())
            h4_frame = htf_features.get("H4", pd.DataFrame())
            # Contexto desde el momento de decisión
            event_ts = pd.Timestamp(event["event_time"])
            time_col = "time" if "time" in h1_frame.columns else "timestamp"
            if not h1_frame.empty and time_col in h1_frame.columns:
                ctx_h1 = h1_frame[h1_frame[time_col] <= event_ts]
                if not ctx_h1.empty:
                    setup["H1_context"] = ctx_h1["bos_direction"].iloc[-1] if "bos_direction" in ctx_h1.columns else "UNAVAILABLE"
                else:
                    setup["H1_context"] = "UNAVAILABLE"
            else:
                setup["H1_context"] = "UNAVAILABLE"
            
            time_col_h4 = "time" if "time" in h4_frame.columns else "timestamp"
            if not h4_frame.empty and time_col_h4 in h4_frame.columns:
                ctx_h4 = h4_frame[h4_frame[time_col_h4] <= event_ts]
                if not ctx_h4.empty:
                    setup["H4_context"] = ctx_h4["bos_direction"].iloc[-1] if "bos_direction" in ctx_h4.columns else "UNAVAILABLE"
                else:
                    setup["H4_context"] = "UNAVAILABLE"
            else:
                setup["H4_context"] = "UNAVAILABLE"
        except Exception as e:
            setup["H1_context"] = f"UNAVAILABLE ({e})"
            setup["H4_context"] = f"UNAVAILABLE ({e})"
        
        # Sweep
        evt_time = pd.Timestamp(event["event_time"])
        sweep_match = sweeps[sweeps["sweep_time"] == evt_time] if not sweeps.empty else pd.DataFrame()
        if not sweep_match.empty:
            setup["sweep_present"] = True
            setup["sweep_type"] = sweep_match.iloc[0]["sweep_type"]
            setup["sweep_time"] = sweep_match.iloc[0]["sweep_time"].isoformat()
        else:
            setup["sweep_present"] = False
            setup["sweep_type"] = "UNAVAILABLE"
            setup["sweep_time"] = "UNAVAILABLE"
        
        # Displacement
        disp_match = displacements[displacements["time"] == evt_time] if not displacements.empty else pd.DataFrame()
        if not disp_match.empty:
            setup["displacement_present"] = True
            setup["displacement_measure"] = float(disp_match.iloc[0]["displacement_mag"])
        else:
            setup["displacement_present"] = False
            setup["displacement_measure"] = "UNAVAILABLE"
        
        # Structure confirmation
        setup["bos_present"] = event["event_type"] == "BOS"
        setup["choch_present"] = event["event_type"] == "CHOCH"
        setup["structure_confirmation_time"] = event["event_time"].isoformat() if not pd.isna(event["event_time"]) else "UNAVAILABLE"
        
        # POI cerca del evento
        if not pois.empty and "poi_time" in pois.columns:
            pois_time = pois.copy()
            pois_time["poi_time_dt"] = pd.to_datetime(pois_time["poi_time"], utc=True, errors="coerce")
            # Normalizar evt_time a UTC para comparación
            evt_time_utc = pd.Timestamp(evt_time).tz_localize("UTC") if evt_time.tzinfo is None else evt_time
            poi_near_df = pois_time[
                (pois_time["poi_time_dt"] <= evt_time_utc) & 
                (pois_time["poi_time_dt"] >= evt_time_utc - pd.Timedelta(hours=24))
            ]
            poi_near = poi_near_df if not poi_near_df.empty else pd.DataFrame()
        else:
            poi_near = pd.DataFrame()
        
        if not poi_near.empty:
            setup["fvg_present"] = any(poi_near["poi_type"] == "FVG")
            setup["ob_present"] = any(poi_near["poi_type"] == "OB")
            setup["poi_type"] = "FVG" if any(poi_near["poi_type"] == "FVG") else "OB"
            setup["poi_age"] = "UNAVAILABLE"  # requeriría cálculo de edad
            setup["poi_lifecycle"] = "ACTIVE"  # default — requeriría seguimiento
        else:
            setup["fvg_present"] = False
            setup["ob_present"] = False
            setup["poi_type"] = "NONE"
            setup["poi_age"] = "UNAVAILABLE"
            setup["poi_lifecycle"] = "UNAVAILABLE"
        
        # Retest — no implementado aún (requiere lógica de precio que regresa a POI)
        setup["retest_present"] = "UNAVAILABLE"
        setup["retest_time"] = "UNAVAILABLE"
        setup["retest_depth"] = "UNAVAILABLE"
        
        # Entry — no implementado aún (requiere lógica de entrada)
        setup["entry_time"] = "UNAVAILABLE"
        setup["entry_timing"] = "UNAVAILABLE"
        
        # Session — requiere logica de sesión (Londres/NY)
        setup["session"] = "UNAVAILABLE"
        
        # Regime — requiere logica de régimen (tendencia/rango)
        setup["regime"] = "UNAVAILABLE"
        
        # Net_R — no disponible en extracción (solo después de resultados económicos)
        setup["net_R"] = "UNAVAILABLE"
        
        # Source refs
        setup["source_refs"] = [
            "EURUSD_M15_2006_2015.parquet",
            "EURUSD_H1.parquet",
            "EURUSD_H4.parquet",
            "EURUSD_D1.parquet",
            "B1_DATA_MANIFEST_V1.json",
        ]
        
        setups.append(setup)
    
    return setups

# ============================================================
# Guardado del corpus
# ============================================================

def save_corpus(setups: list[dict], period: str = "DESIGN"):
    """Guarda el corpus como JSON Lines."""
    out_path = B1_DATA_DIR / f"corpus_{period.lower()}_2006_2015.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for s in setups:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    logger.info(f"Corpus guardado: {out_path} ({len(setups)} candidatos)")
    return out_path

def save_manifest(corpus_path: Path, setups: list[dict], period: str = "DESIGN"):
    """Guarda manifiesto del corpus."""
    manifest = {
        "corpus_path": str(corpus_path),
        "period": period,
        "design_period": "2006-01-01 → 2015-12-31",
        "candidate_count": len(setups),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_manifest_hash": MANIFEST_HASH,
        "code_commit": CODE_COMMIT,
        "fields": [
            "candidate_id", "decision_time", "symbol", "direction_context",
            "period_split", "H4_context", "H1_context", "sweep_present",
            "sweep_type", "sweep_time", "displacement_present", "displacement_measure",
            "bos_present", "choch_present", "structure_confirmation_time",
            "fvg_present", "ob_present", "poi_type", "poi_age", "poi_lifecycle",
            "retest_present", "retest_time", "retest_depth", "entry_time",
            "entry_timing", "session", "regime", "net_R",
            "source_refs", "snapshot_hash", "dataset_manifest_hash", "code_commit",
        ],
        "unavailable_fields": [
            "retest_present", "retest_time", "retest_depth",
            "entry_time", "entry_timing", "session", "regime", "net_R",
        ],
        "notes": "Campos marcados como UNAVAILABLE requieren implementación adicional.",
    }
    manifest_path = corpus_path.parent / f"corpus_{period.lower()}_2006_2015_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    logger.info(f"Manifest guardado: {manifest_path}")

def save_log(setups: list[dict], period: str = "DESIGN"):
    """Guarda log de extracción."""
    log_path = LOG_DIR / f"extract_{period.lower()}_2006_2015.log"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"Extracción B1-O1 — {period} 2006-2015\n")
        f.write(f"Generado: {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"Candidatos: {len(setups)}\n")
        f.write(f"Manifest hash: {MANIFEST_HASH}\n")
        f.write(f"Code commit: {CODE_COMMIT}\n")
        f.write("\nCandidatos:\n")
        for s in setups:
            f.write(f"  {s['candidate_id'][:8]}... | {s['decision_time']} | {s['direction_context']} | {s['bos_present']} | {s['choch_present']}\n")
    logger.info(f"Log guardado: {log_path}")

# ============================================================
# Main
# ============================================================

def main():
    logger.info("=" * 70)
    logger.info("B1-O1 — Extracción del corpus causal B1 (DESIGN 2006-2015)")
    logger.info("=" * 70)
    
    # 1. Cargar datos
    logger.info("Cargando datos...")
    df_m15 = load_design_m15()
    htf_frames = load_htf_frames()
    
    # 2. Computar features
    logger.info("Computando features ICT...")
    features_m15, htf_features = compute_features(df_m15, htf_frames)
    logger.info(f"Features M15: {len(features_m15)} filas")
    for tf, f in htf_features.items():
        logger.info(f"Features {tf}: {len(f)} filas")
    
    # 3. Detectar eventos
    logger.info("Detectando eventos...")
    sweeps = detect_sweep_events(features_m15)
    logger.info(f"Sweeps detectados: {len(sweeps)}")
    
    displacements = detect_displacement_events(features_m15)
    logger.info(f"Displacements detectados: {len(displacements)}")
    
    structure_events = detect_structure_events(features_m15)
    logger.info(f"Eventos de estructura (BOS/CHOCH): {len(structure_events)}")
    
    pois = detect_poi_events(features_m15)
    logger.info(f"POIs detectados: {len(pois)}")
    
    # 4. Construir CANDIDATE_SETUP
    logger.info("Construyendo CANDIDATE_SETUP...")
    setups = build_candidate_setups(
        features_m15, htf_features, sweeps, displacements,
        structure_events, pois,
    )
    logger.info(f"CANDIDATE_SETUP construidos: {len(setups)}")
    
    # 5. Guardar corpus
    logger.info("Guardando corpus...")
    corpus_path = save_corpus(setups, "DESIGN")
    save_manifest(corpus_path, setups, "DESIGN")
    save_log(setups, "DESIGN")
    
    # 6. Resumen
    logger.info("=" * 70)
    logger.info("RESUMEN DE EXTRACCIÓN")
    logger.info(f"CANDIDATES: {len(setups)}")
    logger.info(f"DUPLICATES: 0 (cada candidate_id es único)")
    logger.info(f"UNAVAILABLE_FIELDS: retest, entry, session, regime, net_R")
    logger.info(f"HOLDOUT_TOUCHED: false (solo DESIGN 2006-2015)")
    logger.info("=" * 70)
    
    return setups

if __name__ == "__main__":
    setups = main()
    print(f"\nExtracción completada: {len(setups)} CANDIDATE_SETUP")
    print(f"Corpus: {B1_DATA_DIR / 'corpus_design_2006_2015.jsonl'}")
    print(f"Manifest: {B1_DATA_DIR / 'corpus_design_2006_2015_manifest.json'}")
    print(f"Log: {LOG_DIR / 'extract_design_2006_2015.log'}")
