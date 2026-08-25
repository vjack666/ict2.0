#!/usr/bin/env python3
"""MICRO-AGENTE P2-ALT — HTF (H4) como FILTRO DE ESTRUCTURA sobre anchors LTF.

Comparador: EXP_B1 (baseline LTF, H1 depth>=4, sin HTF). SOLO cambia el FILTRO
de entrada; entry / SL / TP / horizonte / tie_policy / bootstrap / seed son
IDENTICOS a B1 (se reutiliza el codigo de exp_agentA_runner.py, que es el que
B1 llama).

FILTRO (congelado ANTES de ver resultados):
  Para cada anchor LTF (cierre de la barra STRUCTURE, depth>=4) se toma la
  ULTIMA barra H4 CERRADA en o antes del instante de entrada (close H1) y se
  exige que la direccion de la ULTIMA ruptura de estructura H4 coincida con la
  direccion del anchor:
      htf_break_dir = ffill(direccion del ultimo evento BOS/CHoCH)
        choch_signal CHOCH_BULLISH -> +1 ; CHOCH_BEARISH -> -1
        bos_direction BULLISH      -> +1 ; BEARISH      -> -1
        (CHoCH tiene precedencia sobre BOS en la misma barra: regla fijada)
  long  (dir=+1) requiere htf_break_dir == +1
  short (dir=-1) requiere htf_break_dir == -1

MAPEO H4->H1 (PIT, sin ambiguedad): la barra H4 etiquetada T cierra en T+4h y
solo es observable si T+4h <= close de la barra H1 de entrada (t+1h). Se usa
searchsorted sobre los close-times H4. Los gaps de fin de semana solo hacen el
mapeo MAS conservador (nunca adelanta informacion).

Delta vs B1: el tratamiento P2-ALT es un SUBCONJUNTO de los anchors de B1, asi
que el delta se estima con un bootstrap CLUSTERED EMPAREJADO sobre el conjunto
COMPLETO de anchors B1 (mismos clusters chain_id, 2000 remuestreos, seed 42):
en cada remuestreo se calcula mean_R(filtrado) - mean_R(todos) y se toma el
percentil 2.5/97.5 de la distribucion del delta.

Salida: reports/audits/EXP_P2ALT_raw.json + reports/audits/EXP_P2ALT_audit.json
NO promueve a senal. NO commit/push.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from engine.market_features import build_features  # noqa: E402
from engine.sequential_events import (  # noqa: E402
    SeqConfig,
    Stage,
    _causal_swings,
    run_sequential,
    summarize_chains,
)
from engine.sequential_outcome import (  # noqa: E402
    OutcomeConfig,
    bootstrap_clustered,
    resolve_outcome,
)

# Protocolo IDENTICO a B1 (se importa, no se redefine).
from exp_agentA_runner import (  # type: ignore  # noqa: E402
    BASELINE_SEED,
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    CODE_COMMIT,
    HORIZON_BARS,
    MIN_N_GATE,
    PAIRING_SEED,
    RANGE_END,
    RANGE_START,
    SL_BUFFER,
    SWING_LEFT,
    WARMUP_BARS,
    build_trade,
    compute_metrics,
    dataset_record,
    load_slice_csv,
)

REPORT_DIR = ROOT / "reports" / "audits"
RAW_PATH = REPORT_DIR / "EXP_P2ALT_raw.json"
AUDIT_PATH = REPORT_DIR / "EXP_P2ALT_audit.json"
PIT_JSON = REPORT_DIR / "data" / "p2alt_h4_pit.json"
B1_RAW = REPORT_DIR / "EXP_B1_raw.json"

DEPTH_MIN = 4
TF = "H1"
H1_REL = "datasets/eurusd_dukascopy_20y/EURUSD_H1.csv"
H4_REL = "datasets/eurusd_dukascopy_20y/EURUSD_H4.csv"
H1_PATH = ROOT / H1_REL
H4_PATH = ROOT / H4_REL
CANONICAL_H1_HASH = "2dbb5757895e52218f0e6be6fa761b0944b32005f72a3ad896899cd3e2bca022"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------
# HTF (H4) structure filter
# --------------------------------------------------------------------------
def break_dir_series(feat: pd.DataFrame) -> np.ndarray:
    bos = feat["bos_direction"].astype(str).to_numpy()
    ch = feat["choch_signal"].astype(str).to_numpy()
    out = np.zeros(len(feat), dtype=np.int8)
    cur = 0
    for i in range(len(feat)):
        ev = 0
        if ch[i] == "CHOCH_BULLISH":
            ev = 1
        elif ch[i] == "CHOCH_BEARISH":
            ev = -1
        elif bos[i] == "BULLISH":
            ev = 1
        elif bos[i] == "BEARISH":
            ev = -1
        if ev != 0:
            cur = ev
        out[i] = cur
    return out


def htf_context(h1_times: pd.Series) -> dict:
    """Return per-H1-bar HTF break direction, PIT-mapped from H4."""
    h4 = pd.read_csv(H4_PATH)
    h4_ts = pd.to_datetime(h4["time"])
    diffs = h4_ts.diff().dropna()
    median_delta_h = float(diffs.median().total_seconds() / 3600.0)
    feat = build_features(h4.copy())
    bd = break_dir_series(feat)

    # H4 bar labeled T is observable only from T + 4h (its close).
    h4_close = (h4_ts + pd.Timedelta(hours=4)).to_numpy()
    h1_close = (pd.to_datetime(h1_times) + pd.Timedelta(hours=1)).to_numpy()
    pos = np.searchsorted(h4_close, h1_close, side="right") - 1
    mapped = np.full(len(h1_close), 0, dtype=np.int8)
    unmapped = int((pos < 0).sum())
    ok = pos >= 0
    mapped[ok] = bd[pos[ok]]
    lag_h = np.full(len(h1_close), np.nan)
    lag_h[ok] = (h1_close[ok] - h4_close[pos[ok]]).astype("timedelta64[s]").astype(float) / 3600.0

    # H4 coverage defect detection (gaps in the HTF series make the mapped HTF
    # context STALE, never leaky). Reported, never silently absorbed.
    gaps = h4_ts.diff()
    gap_hours = gaps.dt.total_seconds().to_numpy() / 3600.0
    big_pos = np.flatnonzero(np.nan_to_num(gap_hours, nan=0.0) > 72.0)
    gap_list = [{"ends_at": str(h4_ts.iloc[int(i)]), "delta_hours": float(gap_hours[int(i)])}
                for i in big_pos]
    return {
        "dir_per_h1_bar": mapped,
        "h4_idx_per_h1_bar": pos,
        "lag_h_per_h1_bar": lag_h,
        "h4_gaps_gt_72h": gap_list,
        "h4_rows": len(h4),
        "h4_median_delta_hours": median_delta_h,
        "unmapped_h1_bars": unmapped,
        "max_lag_hours": float(np.nanmax(lag_h)) if ok.any() else None,
        "min_lag_hours": float(np.nanmin(lag_h)) if ok.any() else None,
        "h4_break_dir_counts": {
            "bull": int((bd == 1).sum()),
            "bear": int((bd == -1).sum()),
            "none": int((bd == 0).sum()),
        },
    }


# --------------------------------------------------------------------------
# Anchors B1-identical (treatment path of exp_agentA_runner.run_depth_experiment)
# --------------------------------------------------------------------------
def build_anchors(slice_df: pd.DataFrame) -> dict:
    cfg_seq = SeqConfig(structure_mode="lite", max_active_chains=4096, swing_left=SWING_LEFT)
    cfg_out = OutcomeConfig(horizon_bars=HORIZON_BARS, sl_buffer=SL_BUFFER, tie_policy="pessimistic")
    high = slice_df["high"].to_numpy(float)
    low = slice_df["low"].to_numpy(float)
    close = slice_df["close"].to_numpy(float)
    times = list(slice_df["time"])

    chains = run_sequential(slice_df, cfg_seq, timeframe=TF)
    summary = summarize_chains(chains)
    swing_highs, swing_lows = _causal_swings(high, low, SWING_LEFT)

    candidates = [c for c in chains if len(c.nodes) >= DEPTH_MIN]
    by_status: dict = {}
    for c in candidates:
        by_status[c.status] = by_status.get(c.status, 0) + 1

    seen: set = set()
    trades: list[dict] = []
    for ch in candidates:
        anchor_node = ch.nodes[DEPTH_MIN - 1]
        sweep_node = ch.nodes[1]
        assert sweep_node.stage is Stage.SWEEP
        assert anchor_node.stage is Stage.STRUCTURE
        bar_i = int(anchor_node.bar)
        sweep_bar = int(sweep_node.bar)
        key = (bar_i, int(ch.direction))
        if key in seen or bar_i < WARMUP_BARS:
            continue
        seen.add(key)
        sw_lo = float(low[sweep_bar]) if int(ch.direction) == 1 else None
        sw_hi = float(high[sweep_bar]) if int(ch.direction) == -1 else None
        a, b = sweep_bar, bar_i
        r_lo = float(np.min(low[a:b + 1]))
        r_hi = float(np.max(high[a:b + 1]))
        built = build_trade(int(ch.direction), bar_i, close, high, low, swing_lows, swing_highs,
                            sw_lo, sw_hi, r_lo, r_hi, cfg_out)
        if built is None:
            continue
        res = resolve_outcome(high, low, bar_i, built["levels"], cfg_out)
        trades.append({
            "group": "treatment", "chain_id": ch.chain_id,
            "direction": int(ch.direction), "structure_bar": bar_i,
            "sweep_bar": sweep_bar, "time": times[bar_i], "status": ch.status,
            "depth": len(ch.nodes),
            "entry": round(built["levels"].entry, 6), "sl": round(built["levels"].sl, 6),
            "tp": round(built["levels"].tp, 6),
            "range_low": round(r_lo, 6), "range_high": round(r_hi, 6),
            **res,
        })
    return {
        "trades": trades,
        "motor_summary": summary,
        "chains_depth_ge": {"depth_min": DEPTH_MIN, "n": len(candidates), "by_status": by_status},
    }


# --------------------------------------------------------------------------
# Paired clustered bootstrap for the delta (subset - full)
# --------------------------------------------------------------------------
def paired_delta_bootstrap(all_trades: list[dict], n_resamples: int, seed: int) -> dict:
    closed = [t for t in all_trades if t.get("exit_r") is not None]
    clusters: dict[str, list[tuple[float, bool]]] = {}
    for t in closed:
        clusters.setdefault(str(t["chain_id"]), []).append(
            (float(t["exit_r"]), bool(t["htf_pass"]))
        )
    keys = list(clusters.keys())
    if not keys:
        return {"delta_ci_95": None, "n_resamples": n_resamples, "seed": seed,
                "n_valid_resamples": 0, "delta_point": None}
    rng = np.random.default_rng(seed)
    n = len(keys)
    deltas = []
    means_f = []
    means_a = []
    for _ in range(n_resamples):
        pick = rng.integers(0, n, size=n)
        rs_all: list[float] = []
        rs_f: list[float] = []
        for j in pick:
            for r, ok in clusters[keys[j]]:
                rs_all.append(r)
                if ok:
                    rs_f.append(r)
        if not rs_all or not rs_f:
            continue
        ma = float(np.mean(rs_all))
        mf = float(np.mean(rs_f))
        means_a.append(ma)
        means_f.append(mf)
        deltas.append(mf - ma)
    if not deltas:
        return {"delta_ci_95": None, "n_resamples": n_resamples, "seed": seed,
                "n_valid_resamples": 0, "delta_point": None}
    arr = np.asarray(deltas, dtype=float)
    lo, hi = np.percentile(arr, [2.5, 97.5])
    return {
        "delta_ci_95": [round(float(lo), 6), round(float(hi), 6)],
        "delta_bootstrap_mean": round(float(arr.mean()), 6),
        "n_resamples": n_resamples,
        "n_valid_resamples": int(len(arr)),
        "seed": seed,
        "cluster": "chain_id",
        "method": "paired cluster bootstrap over the FULL B1 anchor set; per resample "
                  "delta = mean_R(HTF-filtered subset) - mean_R(all anchors)",
        "excludes_zero": bool(lo > 0 or hi < 0),
    }


def raw_block(m: dict) -> dict:
    ci = (m.get("bootstrap") or {}).get("mean_r_ci")
    return {
        "n_closed": m.get("n_closed"),
        "n_trades": m.get("n_trades"),
        "n_open": m.get("n_open"),
        "mean_R": m.get("mean_r"),
        "median_R": m.get("median_r"),
        "win_rate": m.get("win_rate"),
        "profit_factor": m.get("profit_factor"),
        "expectancy": m.get("expectancy"),
        "drawdown": m.get("drawdown"),
        "wilson_95": m.get("win_rate_wilson95"),
        "bootstrap_ci_95": ci,
    }


def main() -> None:
    t0 = time.time()
    h1_hash = sha256_file(H1_PATH)
    h4_hash = sha256_file(H4_PATH)
    hash_ok = h1_hash == CANONICAL_H1_HASH

    slice_df = load_slice_csv(H1_PATH)
    n_bars = len(slice_df)
    print(f"H1 slice bars={n_bars} hash_ok={hash_ok}", flush=True)

    ctx = htf_context(slice_df["time"])
    print(f"H4 rows={ctx['h4_rows']} median_delta={ctx['h4_median_delta_hours']}h "
          f"unmapped={ctx['unmapped_h1_bars']} lag=[{ctx['min_lag_hours']},{ctx['max_lag_hours']}]h",
          flush=True)

    res = build_anchors(slice_df)
    all_trades = res["trades"]
    hdir = ctx["dir_per_h1_bar"]
    h4idx = ctx["h4_idx_per_h1_bar"]
    lagv = ctx["lag_h_per_h1_bar"]
    for t in all_trades:
        b = int(t["structure_bar"])
        d = int(hdir[b])
        t["htf_break_dir"] = d
        t["h4_bar_idx"] = int(h4idx[b])
        t["htf_lag_hours"] = float(lagv[b])
        t["htf_stale"] = bool(float(lagv[b]) > 8.0)
        t["htf_pass"] = bool(d != 0 and d == int(t["direction"]))

    filtered = [t for t in all_trades if t["htf_pass"]]
    rejected = [t for t in all_trades if not t["htf_pass"]]
    print(f"anchors={len(all_trades)} htf_pass={len(filtered)} rejected={len(rejected)}", flush=True)

    m_p2 = compute_metrics(filtered, "chain_id")
    m_b1r = compute_metrics(all_trades, "chain_id")

    # Reproduction check against the stored B1 artefact (comparador oficial).
    b1_stored = json.loads(B1_RAW.read_text(encoding="utf-8"))
    b1_t = b1_stored["treatment"]
    repro = {
        "b1_stored": {k: b1_t.get(k) for k in ("n_trades", "n_closed", "mean_R", "win_rate")},
        "b1_recomputed": {"n_trades": m_b1r.get("n_trades"), "n_closed": m_b1r.get("n_closed"),
                          "mean_R": m_b1r.get("mean_r"), "win_rate": m_b1r.get("win_rate")},
    }
    repro["exact_match"] = bool(
        b1_t.get("n_trades") == m_b1r.get("n_trades")
        and b1_t.get("n_closed") == m_b1r.get("n_closed")
        and abs(float(b1_t.get("mean_R")) - float(m_b1r.get("mean_r") or 0)) < 1e-6
    )
    print(f"B1 reproduction exact_match={repro['exact_match']} {repro}", flush=True)

    delta_boot = paired_delta_bootstrap(all_trades, BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED)
    delta_point = None
    if m_p2.get("mean_r") is not None and m_b1r.get("mean_r") is not None:
        delta_point = round(float(m_p2["mean_r"]) - float(m_b1r["mean_r"]), 6)
    delta_vs_stored = None
    if m_p2.get("mean_r") is not None:
        delta_vs_stored = round(float(m_p2["mean_r"]) - float(b1_t["mean_R"]), 6)
    delta_boot["delta_point"] = delta_point

    # Unpaired sanity CI on the filtered subset alone (same helper as B1).
    boot_sub = bootstrap_clustered(filtered, "chain_id",
                                   n_resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED)

    # ---- PIT evidence ----
    pit = None
    if PIT_JSON.exists():
        try:
            pit = json.loads(PIT_JSON.read_text(encoding="utf-8"))
        except Exception:
            pit = None
    pit_stable = bool(pit and pit.get("pit_stable"))
    if pit:
        leak = (
            f"OK: (1) run_sequential una sola pasada sobre H1 2019-2024 (PIT-estable dentro "
            f"del rango, deuda FULL-vs-PREFIX del navigator HTF no aplica a este diseno). "
            f"(2) Columnas de estructura H4 (bos_direction/choch_signal) y la serie derivada "
            f"htf_break_dir verificadas FULL-vs-PREFIX en {pit.get('n_cuts')} cortes sobre TODO "
            f"el prefijo: violaciones totales={pit.get('totals')} -> pit_stable="
            f"{pit.get('pit_stable')}. (3) Mapeo H4->H1 usa solo barras H4 CERRADAS "
            f"(close H4 = label+4h <= close de la barra H1 de entrada); lag observado "
            f"[{ctx['min_lag_hours']}, {ctx['max_lag_hours']}] h >= 0, sin adelanto."
        )
    else:
        leak = ("PARCIAL: run_sequential PIT-estable en una pasada y mapeo H4->H1 solo con "
                "barras H4 cerradas (lag>=0), pero el probe FULL-vs-PREFIX de las columnas "
                "H4 no dejo artefacto legible en esta corrida.")

    # ---- Gates / verdict (mecanico) ----
    n_closed = m_p2.get("n_closed") or 0
    ci_sub = (m_p2.get("bootstrap") or {}).get("mean_r_ci")
    gate = {
        "n_ge_30": bool(n_closed >= MIN_N_GATE),
        "expectancy_gt_0": bool((m_p2.get("mean_r") or 0) > 0),
        "ci_lower_gt_0": bool(ci_sub and len(ci_sub) == 2 and ci_sub[0] > 0),
    }
    delta_ci = delta_boot.get("delta_ci_95")
    delta_excludes_zero = bool(delta_ci and (delta_ci[0] > 0 or delta_ci[1] < 0))
    htf_adds = bool(delta_excludes_zero and (delta_point or 0) > 0)

    executable_clean = bool(hash_ok and ctx["unmapped_h1_bars"] == 0 and repro["exact_match"])
    if not executable_clean or not pit_stable:
        verdict = "BLOCKED"
    elif n_closed < MIN_N_GATE:
        verdict = "BLOCKED"
    elif gate["expectancy_gt_0"] and gate["ci_lower_gt_0"] and htf_adds:
        verdict = "PASS"
    else:
        verdict = "FAIL"

    filter_spec = {
        "name": "HTF_H4_STRUCTURE_BREAK_ALIGNMENT",
        "rule": "keep anchor iff htf_break_dir(last CLOSED H4 bar at entry) == anchor.direction",
        "htf_break_dir": "forward-filled direction of the last H4 structural break; "
                         "choch_signal CHOCH_BULLISH/BEARISH -> +1/-1, else bos_direction "
                         "BULLISH/BEARISH -> +1/-1; CHoCH precedence on same bar",
        "source_columns": ["bos_direction", "choch_signal"],
        "htf_tf": "H4",
        "mapping": "PIT: H4 bar labeled T usable iff T+4h <= H1 entry close (t+1h); "
                   "searchsorted on H4 close-times; weekend gaps only add conservatism",
        "frozen_before_results": True,
    }

    raw = {
        "schema_version": "1.0",
        "experiment": "EXP_P2ALT",
        "role": "P2_INCREMENTAL — HTF (H4) como FILTRO DE ESTRUCTURA sobre anchors LTF de B1",
        "policy": "STUDY_OBJECT_EVIDENCE_NOT_APPROVED_SIGNAL",
        "hypothesis": (
            "H_P2ALT: filtrar los anchors LTF (H1 depth>=4, STRUCTURE close) exigiendo "
            "alineacion con la direccion de la ultima ruptura de estructura H4 (BOS/CHoCH) "
            "aporta INFORMACION INCREMENTAL sobre EXP_B1. Metrica primaria: expectancy "
            "(mean_R). Criterio de 'HTF aporta': IC95 del delta de expectancy vs B1 excluye 0. "
            "SL/TP/horizonte/tie_policy/bootstrap IDENTICOS a B1; SOLO cambia el filtro."
        ),
        "comparator": {
            "experiment": "EXP_B1",
            "artifact": "reports/audits/EXP_B1_raw.json",
            "stored_expectancy": b1_t.get("mean_R"),
            "stored_n_closed": b1_t.get("n_closed"),
            "reproduction_in_this_run": repro,
        },
        "dataset": dataset_record("csv", H1_REL, n_bars, h1_hash, True, TF,
                                  "Dataset canonico H1 2019-2024 (exec TF). Contexto HTF = H4 "
                                  "del mismo dataset Dukascopy; D1 NO usado."),
        "dataset_htf": {
            "exec_tf_context": "H4",
            "source": H4_REL,
            "rows": ctx["h4_rows"],
            "dataset_hash": h4_hash,
            "median_bar_delta_hours": ctx["h4_median_delta_hours"],
            "origin": "csv",
        },
        "dataset_hash": h1_hash,
        "dataset_hash_h4": h4_hash,
        "code_commit": CODE_COMMIT,
        "config": {
            "structure_mode": "lite",
            "max_active_chains": 4096,
            "swing_left": SWING_LEFT,
            "depth_min": DEPTH_MIN,
            "anchor": "STRUCTURE_bar_close (depth>=4)",
            "sl_rule": "min(sweep_wick, broken_swing)-buffer (IDENTICO a B1, nunca ATR)",
            "tp_rule": "measured_projection (fallback sancionado, IDENTICO a B1)",
            "sl_buffer": SL_BUFFER,
            "horizon_bars": HORIZON_BARS,
            "tie_policy": "pessimistic",
            "warmup_bars": WARMUP_BARS,
            "bootstrap": {"resamples": BOOTSTRAP_RESAMPLES, "seed": BOOTSTRAP_SEED,
                          "cluster": "chain_id"},
            "baseline_seed": BASELINE_SEED,
            "pairing_seed": PAIRING_SEED,
            "htf_context": True,
            "htf_filter": filter_spec,
            "fvg_random_baseline_run": False,
        },
        "fecha": datetime.now(timezone.utc).isoformat(),
        "treatment": raw_block(m_p2),
        "b1_recomputed_unfiltered": raw_block(m_b1r),
        "delta_vs_B1": {
            "metric": "expectancy (mean_R)",
            "p2alt_expectancy": m_p2.get("mean_r"),
            "b1_expectancy_recomputed": m_b1r.get("mean_r"),
            "b1_expectancy_stored": b1_t.get("mean_R"),
            "delta_expectancy": delta_point,
            "delta_expectancy_vs_stored_B1": delta_vs_stored,
            "delta_ci_95": delta_ci,
            "delta_ci_excludes_zero": delta_excludes_zero,
            "htf_aporta": htf_adds,
            "bootstrap": delta_boot,
            "delta_win_rate": (round(float(m_p2["win_rate"]) - float(m_b1r["win_rate"]), 4)
                               if m_p2.get("win_rate") is not None
                               and m_b1r.get("win_rate") is not None else None),
        },
        "filter_effect": {
            "n_anchors_total": len(all_trades),
            "n_anchors_kept": len(filtered),
            "n_anchors_rejected": len(rejected),
            "keep_rate": round(len(filtered) / len(all_trades), 4) if all_trades else None,
            "kept_by_direction": {
                "long": sum(1 for t in filtered if t["direction"] == 1),
                "short": sum(1 for t in filtered if t["direction"] == -1),
            },
            "rejected_reason_counts": {
                "htf_dir_opposite": sum(1 for t in rejected if t["htf_break_dir"] != 0),
                "htf_dir_undefined": sum(1 for t in rejected if t["htf_break_dir"] == 0),
            },
            "h4_break_dir_bar_counts": ctx["h4_break_dir_counts"],
            "htf_mapping_lag_hours": [ctx["min_lag_hours"], ctx["max_lag_hours"]],
            "unmapped_h1_bars": ctx["unmapped_h1_bars"],
            "htf_staleness": {
                "definition": "anchor whose mapped H4 context is older than one H4 bar (lag>8h)",
                "n_anchors_stale": sum(1 for t in all_trades if t["htf_stale"]),
                "n_kept_stale": sum(1 for t in filtered if t["htf_stale"]),
                "n_rejected_stale": sum(1 for t in rejected if t["htf_stale"]),
                "max_anchor_lag_hours": (round(max(float(t["htf_lag_hours"]) for t in all_trades), 2)
                                         if all_trades else None),
                "median_anchor_lag_hours": (round(float(np.median([t["htf_lag_hours"] for t in all_trades])), 2)
                                            if all_trades else None),
            },
        },
        "h4_coverage_defect": {
            "gaps_gt_72h": ctx["h4_gaps_gt_72h"],
            "impact": "A gap in the H4 series makes the PIT mapping return an OLDER closed H4 "
                      "bar (STALE context). It can never leak future information; it can only "
                      "degrade the filter's freshness. Reported, not corrected: correcting it "
                      "would be a post-result parameter/data change.",
        },
        "subset_bootstrap_check": boot_sub,
        "motor_summary": res["motor_summary"],
        "chains_depth_ge4": res["chains_depth_ge"],
        "pit_probe": pit,
        "losers_removed": False,
        "parameters_changed_after_seeing_results": False,
        "elapsed_s": round(time.time() - t0, 2),
    }

    audit = {
        "schema_version": "1.0",
        "experiment": "EXP_P2ALT",
        "role": "P2_INCREMENTAL — HTF (H4) como FILTRO DE ESTRUCTURA sobre anchors LTF de B1",
        "code_commit": CODE_COMMIT,
        "date": datetime.now(timezone.utc).isoformat(),
        "gate": {
            "n_ge_30": gate["n_ge_30"],
            "expectancy_gt_0": gate["expectancy_gt_0"],
            "ci_lower_gt_0": gate["ci_lower_gt_0"],
            "n_closed": n_closed,
            "expectancy": m_p2.get("mean_r"),
            "bootstrap_ci_95": ci_sub,
        },
        "incremental_gate": {
            "comparator": "EXP_B1 (mismos anchors sin filtro HTF, mismo SL/TP)",
            "delta_expectancy": delta_point,
            "delta_ci_95": delta_ci,
            "delta_ci_excludes_zero": delta_excludes_zero,
            "htf_aporta": htf_adds,
        },
        "protocol": {
            "leakage_check": leak,
            "parameter_change": False,
            "data_integrity": {
                **dataset_record("csv", H1_REL, n_bars, h1_hash, True, TF,
                                 "H1 canonico verificado por SHA256 (coincide con el hash del "
                                 "contrato). Contexto H4 del mismo dataset; D1 no usado."),
                "h1_hash_matches_contract": hash_ok,
                "h4_source": H4_REL,
                "h4_rows": ctx["h4_rows"],
                "h4_dataset_hash": h4_hash,
                "b1_reproduction_exact": repro["exact_match"],
                "htf_pit_probe": (None if not pit else
                                  {"pit_stable": pit.get("pit_stable"),
                                   "totals": pit.get("totals"),
                                   "n_cuts": pit.get("n_cuts")}),
                "unmapped_h1_bars": ctx["unmapped_h1_bars"],
                "h4_coverage_gaps_gt_72h": ctx["h4_gaps_gt_72h"],
                "h4_coverage_note": (
                    "DEFECTO DE COBERTURA H4 detectado y reportado: hueco(s) >72h en la serie H4. "
                    "Efecto = contexto HTF ENVEJECIDO (stale) en esos tramos; NO es leakage (el "
                    "mapeo sigue usando solo barras H4 ya cerradas). No se corrige en esta corrida "
                    "porque cambiar los datos tras ver el resultado violaria el contrato."
                ),
            },
        },
        "verdict": verdict,
        "rationale": (
            "mecanico. BLOCKED si el experimento no es ejecutable limpio (hash H1 != contrato, "
            "barras H1 sin mapeo H4, B1 no reproducido bit a bit, o columnas H4 no PIT-estables) "
            "o si n_closed<30. PASS iff n_closed>=30 AND expectancy>0 AND bootstrap CI95 lower>0 "
            "AND el IC95 del delta de expectancy vs B1 EXCLUYE 0 con delta>0 ('HTF aporta'). "
            "FAIL (incremental) en cualquier otro caso: el filtro HTF no demuestra informacion "
            "incremental sobre B1. NO se promueve a senal."
        ),
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_PATH.write_text(json.dumps(raw, indent=2, default=str), encoding="utf-8")
    AUDIT_PATH.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    print(f"WROTE {RAW_PATH}", flush=True)
    print(f"WROTE {AUDIT_PATH}", flush=True)
    print(json.dumps({
        "experiment": "EXP_P2ALT",
        "verdict": verdict,
        "n_closed": n_closed,
        "expectancy": m_p2.get("mean_r"),
        "ci95": ci_sub,
        "win_rate": m_p2.get("win_rate"),
        "profit_factor": m_p2.get("profit_factor"),
        "drawdown": m_p2.get("drawdown"),
        "delta_vs_B1": delta_point,
        "delta_ci_95": delta_ci,
        "delta_ci_excludes_zero": delta_excludes_zero,
        "keep_rate": raw["filter_effect"]["keep_rate"],
        "b1_repro_exact": repro["exact_match"],
    }, indent=2, default=str), flush=True)


if __name__ == "__main__":
    main()
