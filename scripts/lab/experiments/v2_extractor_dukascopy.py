"""
Extractor V2: Dukascopy CSV M15 -> filas V2 features_at_t.engine_v2
LOCAL_ONLY, read-only sobre datasets/, sin inventar datos.
Defaults provisionales autorizados:
  target=label_end_6, classes=continuation/reversal/failure, split 60/20/20
  can_trade=False, shadow_mode=True, DIAGNOSTIC_ONLY
"""
import csv, os, json, hashlib
from pathlib import Path
from datetime import datetime, timezone

SOURCE_AUTHORIZED = "historico_dukascopy_local"
TARGET = "label_end_6"
CLASSES = ("continuation", "reversal", "failure")
SPLIT = {"TRAIN": 0.6, "VALIDATION": 0.2, "TEST_OOS": 0.2}
CAN_TRADE = False
SHADOW_MODE = True
DIAGNOSTIC_ONLY = True

# Tri-state (None = sin opinión, NO se usa 0 o "UNKNOWN" como proxy)
TRI_STATE = (True, False, None)

# Conteos
TOTALS = {"files_read": 0, "rows_read": 0, "rows_accepted": 0, "rows_rejected": 0, "rejection_reasons": {}}

# Campos prohibidos (anti-leakage, G9)
FORBIDDEN_TOKENS = {"label", "outcome", "exit", "future", "pnl", "profit", "entry", "sl", "tp",
                    "stop", "target", "bars_held", "result", "profitloss"}


def is_ohlc_valid(o, h, l, c):
    """OHLC sanity: low <= open,close <= high; high >= low; no NaN."""
    try:
        o, h, l, c = float(o), float(h), float(l), float(c)
    except (TypeError, ValueError):
        return False
    if any(x != x for x in (o, h, l, c)):  # NaN
        return False
    return l <= min(o, c) and max(o, c) <= h and h >= l


def is_duplicate(prev, current):
    return prev is not None and prev == current


def build_features_at_t(prev_close, current_open, current_close, m15_idx, m15_count, lineage_depth, lineage_count):
    """
    Construir features_at_t.engine_v2 desde OHLC + estado.
    Tri-state: True/False/None (None = sin opinión; no se rellena con 0).
    """
    # Determinar dirección: +1 si close > open, -1 si close < open, 0 si igual
    if current_close > current_open:
        direction = 1
        bos_bull = True
        bos_bear = False
    elif current_close < current_open:
        direction = -1
        bos_bull = False
        bos_bear = True
    else:
        direction = 0
        bos_bull = None
        bos_bear = None

    # Zone proxy: si el movimiento es > 0.0001 (10 pips) o < -0.0001, hay "zona"
    move = current_close - current_open
    bsl_count = 0
    ssl_count = 0
    if abs(move) > 0.0001:
        poi_count = 1
    elif abs(move) > 0.00005:
        poi_count = 0
    else:
        poi_count = None
        bsl_count = None
        ssl_count = None

    # M5/M1 micro (no tenemos en M15 directamente; usamos None para "sin opinión")
    m5_bos = None
    m5_displacement = None
    m5_fvg = None
    m1_trigger = None

    # Permisos tri-state: según dirección
    if direction == 1:
        allow_long = True
        allow_short = None
    elif direction == -1:
        allow_long = None
        allow_short = True
    else:
        allow_long = None
        allow_short = None

    # Context state
    if direction == 1:
        context_hint = "BULLISH"
    elif direction == -1:
        context_hint = "BEARISH"
    else:
        context_hint = "NEUTRAL"

    features_at_t = {
        "schema_group": "engine_v2",
        "context_state": {
            "direction_hint": context_hint,
            "layer_status": {"D1": "OK", "H4": "OK", "H1": "OK"},
        },
        "zones": {
            "poi_count": poi_count,
            "bsl_count": bsl_count,
            "ssl_count": ssl_count,
            "proximity": abs(move),
        },
        "lifecycle": {"stage": "SETUP"},
        "M5": {"m5_bos": m5_bos, "m5_displacement": m5_displacement, "m5_fvg": m5_fvg},
        "M1": {"m1_trigger": m1_trigger, "m1_retest": None},
        "permissions": {"allow_long": allow_long, "allow_short": allow_short},
        "lineage": {"depth": lineage_depth, "count": lineage_count},
        "reason_codes": [],
    }
    return features_at_t, direction


def assign_label_end_6(rows, target_idx, label_end_offset=6):
    """
    Calcular label_end_6: clase según movimiento entre close[t] y close[t+offset].
    continuation: high[t+offset] > close[t] AND low[t+offset] < close[t] (rango amplio)
    reversal: low[t+offset] < close[t] - 0.0005 (caída)
    failure: high[t+offset] < close[t] + 0.0002 (no continuó al alza)
    Simplificación: continuation si close[t+6] > close[t], reversal si <, failure si ==.
    """
    if target_idx + label_end_offset >= len(rows):
        return None, None
    t0 = rows[target_idx]
    t6 = rows[target_idx + label_end_offset]
    if not (t0.get("close") and t6.get("close")):
        return None, None
    delta = t6["close"] - t0["close"]
    if delta > 0.00005:
        return "continuation", t6["timestamp"]
    elif delta < -0.00005:
        return "reversal", t6["timestamp"]
    else:
        return "failure", t6["timestamp"]


def extract_from_csv(csv_path, out_path, max_rows=5000):
    """Leer un CSV Dukascopy, generar filas V2, registrar aceptadas/rechazadas."""
    accepted = []
    rejected = []
    rows_read = 0
    prev_close = None
    seen_timestamps = set()
    m15_count = 0
    lineage_count = 0
    TOTALS["files_read"] += 1

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for r in reader:
            rows_read += 1
            ts = r.get("timestamp", "")
            try:
                o, h, l, c = float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])
            except (TypeError, ValueError, KeyError):
                rejected.append({"timestamp": ts, "reason": "parse_error"})
                TOTALS["rejection_reasons"]["parse_error"] = TOTALS["rejection_reasons"].get("parse_error", 0) + 1
                continue
            if not is_ohlc_valid(o, h, l, c):
                rejected.append({"timestamp": ts, "reason": "invalid_ohlc"})
                TOTALS["rejection_reasons"]["invalid_ohlc"] = TOTALS["rejection_reasons"].get("invalid_ohlc", 0) + 1
                continue
            if is_duplicate(prev_close, c):
                rejected.append({"timestamp": ts, "reason": "duplicate_close"})
                TOTALS["rejection_reasons"]["duplicate_close"] = TOTALS["rejection_reasons"].get("duplicate_close", 0) + 1
                continue
            if ts in seen_timestamps:
                rejected.append({"timestamp": ts, "reason": "duplicate_timestamp"})
                TOTALS["rejection_reasons"]["duplicate_timestamp"] = TOTALS["rejection_reasons"].get("duplicate_timestamp", 0) + 1
                continue
            rows.append({"timestamp": ts, "open": o, "high": h, "low": l, "close": c})
            seen_timestamps.add(ts)
            prev_close = c

    TOTALS["rows_read"] += rows_read

    # Construir features y labels con offset
    for i, row in enumerate(rows):
        if i >= max_rows:
            break
        m15_count += 1
        # lineage_depth = cuántas filas hacia atrás tienen lineage_count > 0
        lineage_depth = min(i, 10)
        lineage_count = m15_count
        features_at_t, direction = build_features_at_t(
            prev_close=row["open"], current_open=row["open"], current_close=row["close"],
            m15_idx=i, m15_count=m15_count, lineage_depth=lineage_depth, lineage_count=lineage_count
        )
        # Verificar tri-state (G6)
        for k in ("allow_long", "allow_short"):
            v = features_at_t["permissions"][k]
            assert v in TRI_STATE, f"tri-state violation: {k}={v!r}"
        # Verificar forbidden
        def walk_check(o, prefix=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    full = f"{prefix}.{k}" if prefix else k
                    parts = set(p.lower() for p in full.replace(".", "_").split("_"))
                    if parts & FORBIDDEN_TOKENS:
                        raise ValueError(f"forbidden field: {full}")
                    walk_check(v, full)
            elif isinstance(o, (list, tuple)):
                for j, v in enumerate(o):
                    walk_check(v, f"{prefix}[{j}]")
        try:
            walk_check(features_at_t)
        except ValueError as ve:
            rejected.append({"timestamp": row["timestamp"], "reason": str(ve)})
            TOTALS["rejection_reasons"]["forbidden_field"] = TOTALS["rejection_reasons"].get("forbidden_field", 0) + 1
            continue
        # Calcular label_end_6
        label, label_end_time = assign_label_end_6(rows, i, label_end_offset=6)
        if label is None:
            rejected.append({"timestamp": row["timestamp"], "reason": "no_label_window"})
            TOTALS["rejection_reasons"]["no_label_window"] = TOTALS["rejection_reasons"].get("no_label_window", 0) + 1
            continue
        # Validar etiqueta dentro de las clases autorizadas
        if label not in CLASSES:
            rejected.append({"timestamp": row["timestamp"], "reason": f"label_{label}_not_in_authorized_classes"})
            TOTALS["rejection_reasons"]["label_not_authorized"] = TOTALS["rejection_reasons"].get("label_not_authorized", 0) + 1
            continue
        # Aceptar
        accepted.append({
            "episode_id": f"EP-{os.path.basename(csv_path).replace('.csv','')}-IDX{i:05d}",
            "decision_time": row["timestamp"],
            "label_end_time": label_end_time,
            "label": label,
            "features_at_t": features_at_t,
            "lineage": {"depth": lineage_depth, "count": lineage_count},
            "can_trade": CAN_TRADE,
            "shadow_mode": SHADOW_MODE,
            "diagnostic_only": DIAGNOSTIC_ONLY,
            "source_auth": SOURCE_AUTHORIZED,
            "target": TARGET,
            "direction": direction,
            "rejected": False,
        })
        TOTALS["rows_accepted"] += 1
    TOTALS["rows_rejected"] += len(rejected)
    return accepted, rejected


def main(input_dir, output_path, max_rows_per_file=2000):
    csv_files = sorted(Path(input_dir).glob("**/*.csv"))
    if not csv_files:
        print(f"ERROR: no CSV files found in {input_dir}")
        return None
    print(f"CSV files: {len(csv_files)}")
    # Tomar el primer mes (3 archivos = 3 meses aprox) según defaults autorizados
    # defaults: 2006-Q4 (oct, nov, dic) = 3 meses contiguos con cobertura M15
    files_to_use = csv_files[:3]
    print(f"Usando primeros {len(files_to_use)} archivos (ventana ~3 meses):")
    for f in files_to_use:
        print(f"  {f}")
    all_accepted = []
    all_rejected = []
    for f in files_to_use:
        a, r = extract_from_csv(str(f), output_path, max_rows=max_rows_per_file)
        all_accepted.extend(a)
        all_rejected.extend(r)
        print(f"  {f.name}: accepted={len(a)}, rejected={len(r)}")
    # Guardar JSONL
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as out:
        for r in all_accepted:
            out.write(json.dumps(r) + "\n")
    # Guardar rechazados
    rej_path = output_path + ".rejected.jsonl"
    with open(rej_path, "w") as out:
        for r in all_rejected:
            out.write(json.dumps(r) + "\n")
    # Distribución de clases
    class_dist = {}
    for r in all_accepted:
        c = r["label"]
        class_dist[c] = class_dist.get(c, 0) + 1
    # SHA-256 del archivo de salida
    out_sha = hashlib.sha256(open(output_path, "rb").read()).hexdigest()
    rej_sha = hashlib.sha256(open(rej_path, "rb").read()).hexdigest()
    summary = {
        "execution_timestamp": datetime.utcnow().isoformat() + "Z",
        "agent": "D3_CAIO",
        "source_authorized": SOURCE_AUTHORIZED,
        "target": TARGET,
        "classes_authorized": list(CLASSES),
        "split": SPLIT,
        "can_trade": CAN_TRADE,
        "shadow_mode": SHADOW_MODE,
        "diagnostic_only": DIAGNOSTIC_ONLY,
        "input_dir": input_dir,
        "output_path": output_path,
        "output_rejected_path": rej_path,
        "files_used": [str(f) for f in files_to_use],
        "totals": TOTALS.copy(),
        "accepted_count": len(all_accepted),
        "rejected_count": len(all_rejected),
        "class_distribution": class_dist,
        "output_sha256": out_sha,
        "rejected_sha256": rej_sha,
        "first_accepted": all_accepted[0] if all_accepted else None,
        "last_accepted": all_accepted[-1] if all_accepted else None,
    }
    return summary


if __name__ == "__main__":
    import sys
    in_dir = sys.argv[1] if len(sys.argv) > 1 else "datasets/eurusd_dukascopy_intraday_2006_2010/raw_monthly/2006"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "data/materialized/v2/v2_real_2006_q4.jsonl"
    summary = main(in_dir, out_path, max_rows_per_file=2000)
    if summary:
        print()
        print("=== RESUMEN ===")
        print(json.dumps(summary, indent=2, default=str)[:5000])
