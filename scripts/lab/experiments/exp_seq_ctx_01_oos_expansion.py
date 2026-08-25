"""EXP-SEQ-CTX-01 — AMPLIACIÓN OOS MULTI-SÍMBOLO (pre-registrada).

Ejecuta EXACTAMENTE OOS_EXPANSION_PREREGISTRATION.md:
  - Universo: 8 instrumentos (7 FX + XAUUSD) x {canonical_bos, lite} x HOLDOUT 2021-2025
    (+ EURUSD también DESIGN/VALIDATION, porque solo EURUSD tiene D1/H4 pre-2020).
  - Mismo detector (run_sequential + MTFNavigator PIT), mismos horizontes
    +6/12/24/48, misma purga +48, misma deduplicación intra-variante,
    mismo context_bucket normativo, can_trade=false.
  - NO cambia umbrales, NO mezcla modos, NO toca HOLDOUT.

Reusa la lógica de exp_seq_ctx_01_dataset.py (la fábrica vigente) y añade
solo el bucle de símbolos + el gating de splits por símbolo.

Fallos cerrados (exit != 0) si falta gate causal o gate TNA, o si hay leakage
o can_trade != false (mismas guardas que la fábrica base).
"""

from __future__ import annotations
import sys, json, hashlib, subprocess
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import engine.mtf_navigation as M
from engine.sequential_events import run_sequential, SeqConfig
from audits.codigo.mtf_seq_funnel import _load_tf

# Reusa helpers de la fábrica vigente (misma semántica de integridad)
from scripts.lab.experiments.exp_seq_ctx_01_dataset import (
    _check_gates, _commit, _source_hashes, _canonical_rows_hash,
    _worktree_dirty, _bias_name, _direction_sign, h1_alignment, context_bucket,
    CONTRACT_VERSION, GATE_CAUSAL, GATE_TNA,
)

# --- Universo pre-registrado (congelado) ---
SYMS = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF", "USDJPY", "XAUUSD"]
TIMEFRAMES = ["D1", "H4", "H1"]
TIMEFRAME = "H1"
MODES = ["canonical_bos", "lite"]
HORIZONS = [6, 12, 24, 48]
MIN_DEPTH = 4
MAX_ACTIVE = 10_000_000

BLOCKS = [
    ("DESIGN", "2006-01-01", "2015-12-31"),
    ("VALIDATION", "2016-01-01", "2020-12-31"),
    ("HOLDOUT", "2021-01-01", "2025-12-31"),
]
# Solo EURUSD tiene D1/H4 antes de 2020 → contexto PIT válido para DESIGN/VALIDATION.
SYMS_WITH_FULL_CONTEXT = {"EURUSD"}

OUT_DIR = ROOT / "data" / "learning" / "seq_ctx_01" / "OOS_EXPANSION"
MANIFEST = OUT_DIR / "manifest.json"
PROVENANCE_FILES = (
    "scripts/lab/experiments/exp_seq_ctx_01_oos_expansion.py",
    "engine/sequential_events.py",
    "engine/mtf_navigation.py",
    "docs/contratos/CONTRATO_DATASET_SEQ_CTX_01.md",
    "docs/planificacion/OOS_EXPANSION_PREREGISTRATION.md",
)


def _block_of(t: pd.Timestamp) -> str:
    for name, a, b in BLOCKS:
        if pd.Timestamp(a, tz="UTC") <= t <= pd.Timestamp(b, tz="UTC"):
            return name
    return "OUT"


def _block_end(name: str) -> pd.Timestamp:
    for n, a, b in BLOCKS:
        if n == name:
            return pd.Timestamp(b, tz="UTC")
    raise KeyError(name)


def _load_frames(symbol: str) -> dict[str, pd.DataFrame]:
    frames = {}
    for tf in TIMEFRAMES:
        p = ROOT / "data" / "raw" / symbol / f"{symbol}_{tf}.parquet"
        df = pd.read_parquet(p)
        df["time"] = pd.to_datetime(df["time"], utc=True)
        df = df.sort_values("time").reset_index(drop=True)
        # Optimización de rendimiento (no cambia observaciones conservadas):
        # los símbolos no-EURUSD solo aportan HOLDOUT 2021-2025 y su contexto
        # PIT necesita D1/H4 desde 2020-01-02. Recortar H1 a >=2020-01-01 es
        # seguro: barras anteriores a 2021 nunca son HOLDOUT y no se navegan.
        if symbol not in SYMS_WITH_FULL_CONTEXT and tf == "H1":
            df = df[df["time"] >= pd.Timestamp("2020-01-01", tz="UTC")].reset_index(drop=True)
        frames[tf] = df
    return frames


def _label(h1, bar_k, horizon, rng_lo, rng_hi) -> str:
    end = min(bar_k + horizon + 1, len(h1))
    fut = h1.iloc[bar_k + 1: end]
    if len(fut) < horizon:
        return "failure"
    hh = fut["high"].max()
    ll = fut["low"].min()
    if hh > rng_hi:
        return "continuation"
    if ll < rng_lo:
        return "reversal"
    return "failure"


def _gen_symbol_mode(symbol: str, mode: str, frames: dict, allowed_splits: set) -> tuple[list[dict], dict, dict]:
    """Igual que _gen_mode de la fábrica base, pero por símbolo y con gating de splits."""
    h1 = frames["H1"]
    print(f"[OOS] {symbol}/{mode} H1={len(h1)} splits={sorted(allowed_splits)}", flush=True)
    chains = run_sequential(h1, SeqConfig(structure_mode=mode, max_active_chains=MAX_ACTIVE),
                            symbol=symbol, timeframe=TIMEFRAME)
    rows = []
    excluded = {"out_of_block": 0, "purge_48_crosses_boundary": 0,
                "dedup_structure_bar_direction": 0, "split_not_allowed": 0}
    seen: set = set()
    h1_time = h1["time"].reset_index(drop=True)
    for ch in chains:
        if str(getattr(ch, "status", ch)) != "COMPLETE":
            continue
        nodes = ch.nodes
        chain_id = str(getattr(ch, "chain_id", ""))
        for k in range(1, len(nodes)):
            if k + 1 < MIN_DEPTH:
                continue
            bar_k = int(nodes[k].bar)
            dir_val = nodes[k].direction.value if hasattr(nodes[k].direction, "value") else int(nodes[k].direction)
            dedup_key = (symbol, mode, bar_k, int(dir_val))
            if dedup_key in seen:
                excluded["dedup_structure_bar_direction"] += 1
                continue
            seen.add(dedup_key)
            t = pd.to_datetime(h1.iloc[bar_k]["time"], utc=True)
            split = _block_of(t)
            if split not in allowed_splits:
                if split == "OUT":
                    excluded["out_of_block"] += 1
                else:
                    excluded["split_not_allowed"] += 1
                continue
            end48_idx = min(bar_k + 48, len(h1_time) - 1)
            t48 = pd.to_datetime(h1_time.iloc[end48_idx], utc=True)
            if t48 > _block_end(split):
                excluded["purge_48_crosses_boundary"] += 1
                continue
            pref = {tf: frames[tf].loc[frames[tf]["time"] <= t].copy().reset_index(drop=True)
                    for tf in frames}
            nav = M.MTFNavigator(pref, M.NavigatorConfig(precompute_sequences=False, sequence_tf="H1"))
            st = nav.navigate(t, exec_tf="H1")
            d1 = st.layers.get("D1")
            h4 = st.layers.get("H4")
            h1_layer = st.layers.get("H1")
            d1_bias = _bias_name(d1.structure_bias) if d1 else "UNKNOWN"
            h4_answer = (h4.answers.get(M.NavQuestion.WHERE_IN_CONTEXT.value) or {}) if h4 else {}
            h4_loc = h4_answer.get("location", "UNKNOWN") if isinstance(h4_answer, dict) else "UNKNOWN"
            h1_bias = _bias_name(h1_layer.structure_bias) if h1_layer else "UNKNOWN"
            h1_align = h1_alignment(dir_val, h1_bias)
            bucket = context_bucket(dir_val, d1_bias, h4_loc, h1_align)
            bars = [int(n.bar) for n in nodes[:k + 1]]
            rng_lo = float(h1.iloc[bars]["low"].min())
            rng_hi = float(h1.iloc[bars]["high"].max())
            labels = {f"label_end_{h}": _label(h1, bar_k, h, rng_lo, rng_hi) for h in HORIZONS}
            stage_val = lambda s: s.value if hasattr(s, "value") else str(s)
            feats = {
                "sequence": [stage_val(n.stage) for n in nodes[:k + 1]],
                "context_layers": {
                    "D1": {"bias": d1_bias},
                    "H4": {"bias": _bias_name(h4.structure_bias) if h4 else "UNKNOWN", "location": h4_loc},
                    "H1": {"bias": h1_bias, "alignment": h1_align},
                },
                "context_inputs": {
                    "sequence_direction": int(dir_val),
                    "d1_bias": d1_bias,
                    "h4_location": h4_loc,
                    "h1_alignment": h1_align,
                },
                "constraints": {"allow_long": st.constraints.allow_long if st.constraints else None,
                                "allow_short": st.constraints.allow_short if st.constraints else None,
                                "direction_hint": _bias_name(st.constraints.direction_hint)
                                if st.constraints and st.constraints.direction_hint else None},
            }
            row = {
                "dataset_id": f"SEQ_CTX_01_{mode.upper()}",
                "contract_version": CONTRACT_VERSION,
                "symbol": symbol, "timeframe": TIMEFRAME,
                "event_time": t.isoformat(),
                "direction": int(dir_val),
                "structure_mode": mode,
                "sequence_depth": k + 1,
                "context_bucket": bucket,
                "chain_id": chain_id,
                "features_at_t": feats,
                "split": split,
                "can_trade": False,
                **labels,
            }
            rows.append(row)
    return rows, excluded, {}


def _event_id(did, symbol, tf, event_time, mode, chain_id, depth) -> str:
    basis = f"{did}|{symbol}|{tf}|{event_time}|{mode}|{chain_id}|{depth}"
    return hashlib.sha256(basis.encode()).hexdigest()


def main() -> int:
    print("[OOS] inicio ampliación OOS multi-símbolo (pre-registrada)", flush=True)
    rc = _check_gates()
    if rc:
        return rc
    commit = _commit()
    if commit == "UNKNOWN":
        return 1

    all_rows: list[dict] = []
    exclusions = {}
    per_symbol_mode: dict = {}
    for symbol in SYMS:
        frames = _load_frames(symbol)
        allowed = {"HOLDOUT"} if symbol not in SYMS_WITH_FULL_CONTEXT else {"DESIGN", "VALIDATION", "HOLDOUT"}
        for mode in MODES:
            rs, exc, _ = _gen_symbol_mode(symbol, mode, frames, allowed)
            exclusions[f"{symbol}/{mode}"] = exc
            per_symbol_mode.setdefault(symbol, {})[mode] = len(rs)
            all_rows.extend(rs)
            print(f"[OOS]   {symbol}/{mode}: aceptadas={len(rs)} exc={exc}", flush=True)

    if not all_rows:
        print("[OOS][FAIL-CLOSED] 0 observaciones generadas")
        return 1

    # Guardas anti-leakage / can_trade
    for r in all_rows:
        if any(k.startswith("label_") for k in r["features_at_t"]):
            print("[OOS][FAIL-CLOSED] leakage: label_ en features_at_t")
            return 1
        if r["can_trade"] is not False:
            print("[OOS][FAIL-CLOSED] can_trade != false")
            return 1

    # Escribir por variante (dataset_id separado por modo, nunca mezclar)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    by_dataset: dict[str, list[dict]] = {}
    for r in all_rows:
        by_dataset.setdefault(r["dataset_id"], []).append(r)

    source_hashes = _source_hashes()
    per_year: dict = {}
    for did, rs in by_dataset.items():
        for r in rs:
            r["dataset_sha256"] = ""
            r["generator_commit"] = commit
            r["event_id"] = _event_id(did, r["symbol"], r["timeframe"], r["event_time"],
                                      r["structure_mode"], r.get("chain_id", ""), r["sequence_depth"])
        ds_hash = _canonical_rows_hash(rs)
        for r in rs:
            r["dataset_sha256"] = ds_hash
        out = OUT_DIR / f"{did}.jsonl"
        lines = [json.dumps(r, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
                 for r in rs]
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        # conteos por año/símbolo/bucket/split
        for r in rs:
            yr = pd.Timestamp(r["event_time"]).year
            key = (r["symbol"], r["structure_mode"], r["context_bucket"], r["split"], yr)
            per_year[key] = per_year.get(key, 0) + 1

    # Celdas HOLDOUT agregadas por variante (universo pre-registrado completo)
    holdout_cells = {}
    for did in by_dataset:
        for bucket in ("ALIGNED", "NEUTRAL", "AGAINST"):
            n = sum(1 for r in by_dataset[did] if r["split"] == "HOLDOUT" and r["context_bucket"] == bucket)
            holdout_cells[f"{did}:{bucket}"] = n
    sufficient = all(n >= 30 for n in holdout_cells.values())

    manifest = {
        "experiment": "EXP-SEQ-CTX-01",
        "artifact": "OOS_EXPANSION",
        "preregistration": "docs/planificacion/OOS_EXPANSION_PREREGISTRATION.md",
        "contract_version": CONTRACT_VERSION,
        "generator_commit": commit,
        "generator_worktree": "DIRTY" if _worktree_dirty() else "CLEAN",
        "generator_source_hashes": source_hashes,
        "universe": {"symbols": SYMS, "timeframes": TIMEFRAMES, "modes": MODES,
                     "blocks": {n: {"start": a, "end": b} for n, a, b in BLOCKS},
                     "note": "DESIGN/VALIDATION solo EURUSD (D1/H4 pre-2020 ausentes en otros simbolos)"},
        "can_trade": False,
        "criterion": "n >= 30 per (structure_mode, context_bucket, HOLDOUT)",
        "holdout_cells": holdout_cells,
        "oos_status": "SUFFICIENT" if sufficient else "SUBPOWERED",
        "gate_causal": "PASS", "gate_tna": "PASS",
        "per_symbol_mode_rows": per_symbol_mode,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "policy": "OFFLINE_RESEARCH_ONLY; can_trade=false",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, default=str))
    (OUT_DIR / "OOS_EXPANSION_COUNTS.json").write_text(
        json.dumps({"holdout_cells": holdout_cells,
                    "per_year": {f"{s}|{m}|{b}|{sp}|{y}": c for (s, m, b, sp, y), c in sorted(per_year.items())},
                    "per_symbol_mode": per_symbol_mode}, indent=2, default=str))
    (OUT_DIR / "exclusions_report.json").write_text(json.dumps(exclusions, indent=2))
    print(f"[OOS] total={len(all_rows)} holdout_cells={holdout_cells} oos_status={manifest['oos_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
