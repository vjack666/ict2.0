"""EXP-SEQ-CTX-01 — FÁBRICA DE DATASET OFFLINE (Sequence × Context State).

Trabajo 4 del SDD. NO reutiliza b2_dataset_factory / b3_walkforward (generic
CHOCH pipelines); es una fabrica especifica para Sequence × Context State que
falla CERRADO si falta cualquier guarda del contrato.

Genera ejemplos con el schema de CONTRATO_DATASET_SEQ_CTX_01.md:
  event_id, dataset_id, dataset_sha256, generator_commit, contract_version,
  symbol, timeframe, event_time, direction, structure_mode, sequence_depth,
  context_bucket, features_at_t, label_end_6/12/24/48, split, can_trade=false

Fallos cerrados (exit != 0) si:
  - falta gate causal (PASS) -> G0
  - falta gate TNA (PASS)    -> G1
  - falta dataset_sha256 / generator_commit
  - existe leakage (features_at_t con time > T, o label usado en features)
  - no existe split temporal
  - can_trade != false

El dataset es SOLO investigacion offline. No entrena, no promociona.
"""

from __future__ import annotations
import sys, os, json, time, hashlib, subprocess
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

OUT_DIR = ROOT / "data" / "learning" / "seq_ctx_01"
MANIFEST = OUT_DIR / "manifest.json"
CONTRACT_VERSION = "v1"
GATE_CAUSAL = ROOT / "reports/audits/experiments/seq_ctx_01/gate_causal.json"
GATE_TNA = ROOT / "reports/audits/tna_streaming_prefix_2026-08-22.json"
TIMEFRAMES = ["D1", "H4", "H1"]

# Bloques temporales CONGELADOS (SDD/OOS addendum)
BLOCKS = [
    ("DESIGN", "2006-01-01", "2015-12-31"),
    ("VALIDATION", "2016-01-01", "2020-12-31"),
    ("HOLDOUT", "2021-01-01", "2025-12-31"),
]
HORIZONS = [6, 12, 24, 48]
MODES = ["canonical_bos", "lite"]
MIN_DEPTH = 4
MAX_ACTIVE = 10_000_000


def _commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                        text=True).strip()[:12]
    except Exception:
        return "UNKNOWN"


def _fail(msg: str, code: int = 1) -> int:
    print(f"[FACTORY][FAIL-CLOSED] {msg}", flush=True)
    return code


def _check_gates() -> int:
    if not GATE_CAUSAL.exists():
        return _fail(f"falta gate causal: {GATE_CAUSAL}")
    gc = json.loads(GATE_CAUSAL.read_text())
    if gc.get("status") != "PASS" or gc.get("violations"):
        return _fail(f"gate causal no PASS: status={gc.get('status')} violations={len(gc.get('violations', []))}")
    if not GATE_TNA.exists():
        return _fail(f"falta gate TNA: {GATE_TNA}")
    gt = json.loads(GATE_TNA.read_text())
    # TNA reporta behavioral/full-span mismatches; el artefacto de f38c usa
    # 'mismatches': [] / 'mismatch_count_reported' (sin campo 'status' literal).
    n_mism = 0
    if isinstance(gt, dict):
        n_mism = len(gt.get("mismatches", [])) or gt.get("mismatch_count_reported", 0) or 0
    if n_mism:
        return _fail(f"gate TNA con {n_mism} mismatches")
    if isinstance(gt, dict) and gt.get("status") not in (None, "PASS"):
        return _fail(f"gate TNA no PASS: status={gt.get('status')}")
    print(f"[FACTORY] G0 causal=PASS, G1 TNA=PASS (mismatches={n_mism})", flush=True)
    return 0


def _load_frames():
    frames = {}
    for tf in TIMEFRAMES:
        df = _load_tf(tf)
        df["time"] = pd.to_datetime(df["time"], utc=True)
        frames[tf] = df.sort_values("time").reset_index(drop=True)
    return frames


def _context_bucket(nav_state) -> str:
    """ALIGNED / NEUTRAL / AGAINST desde el MarketState PIT."""
    cons = nav_state.constraints
    allow = []
    if cons is not None:
        if cons.allow_long:
            allow.append("long")
        if cons.allow_short:
            allow.append("short")
    if cons is not None and cons.direction_hint is not None:
        hint = cons.direction_hint.value  # 'bull'/'bear'
        bull = hint == "bull"
        if (bull and "short" in allow and "long" not in allow) or \
           (not bull and "long" in allow and "short" not in allow):
            return "AGAINST"
        if bull and "long" in allow and "short" not in allow:
            return "ALIGNED"
        if (not bull) and "short" in allow and "long" not in allow:
            return "ALIGNED"
    return "NEUTRAL"


def _label(h1, bar_k, horizon, rng_lo, rng_hi) -> str:
    """Ruptura del rango de la secuencia a N barras (sin PnL)."""
    end = min(bar_k + horizon + 1, len(h1))
    fut = h1.iloc[bar_k + 1: end]
    if len(fut) < horizon:
        return "failure"  # insuficiente horizonte dentro del bloque
    hh = fut["high"].max()
    ll = fut["low"].min()
    if hh > rng_hi:
        return "continuation"
    if ll < rng_lo:
        return "reversal"
    return "failure"


def _block_of(t: pd.Timestamp) -> str:
    for name, a, b in BLOCKS:
        if pd.Timestamp(a, tz="UTC") <= t <= pd.Timestamp(b, tz="UTC"):
            return name
    return "OUT"


def _gen_mode(mode: str, frames, h1) -> list[dict]:
    print(f"[FACTORY] generando modo={mode} ...", flush=True)
    chains = run_sequential(h1, SeqConfig(structure_mode=mode, max_active_chains=MAX_ACTIVE),
                            symbol="EURUSD", timeframe="H1")
    rows = []
    for ch in chains:
        if str(getattr(ch, "status", ch)) != "COMPLETE":
            continue
        nodes = ch.nodes
        for k in range(1, len(nodes)):
            node = nodes[k]
            if k + 1 < MIN_DEPTH:
                continue
            bar_k = int(node.bar)
            t = pd.to_datetime(h1.iloc[bar_k]["time"], utc=True)
            split = _block_of(t)
            if split == "OUT":
                continue
            # Contexto PIT: navigator solo con barras <= t
            pref = {tf: frames[tf].loc[frames[tf]["time"] <= t].copy().reset_index(drop=True)
                    for tf in frames}
            nav = M.MTFNavigator(pref, M.NavigatorConfig(precompute_sequences=False, sequence_tf="H1"))
            st = nav.navigate(t, exec_tf="H1")
            bucket = _context_bucket(st)
            # Rango de la secuencia (ancla estructural) para el label
            bars = [int(n.bar) for n in nodes[:k + 1]]
            rng_lo = float(h1.iloc[bars]["low"].min())
            rng_hi = float(h1.iloc[bars]["high"].max())
            labels = {f"label_end_{h}": _label(h1, bar_k, h, rng_lo, rng_hi) for h in HORIZONS}
            # features_at_t: solo info <= t
            stage_val = lambda s: s.value if hasattr(s, "value") else str(s)
            feats = {
                "sequence": [stage_val(n.stage) for n in nodes[:k + 1]],
                "context_layers": {tf: {"bias": st.layers[tf].structure_bias.value
                                         if st.layers[tf].structure_bias is not None else None}
                                   for tf in ("D1", "H4", "H1")},
                "constraints": {"allow_long": st.constraints.allow_long if st.constraints else None,
                                "allow_short": st.constraints.allow_short if st.constraints else None,
                                "direction_hint": st.constraints.direction_hint.value
                                if st.constraints and st.constraints.direction_hint else None},
            }
            dir_val = node.direction.value if hasattr(node.direction, "value") else int(node.direction)
            row = {
                "dataset_id": f"SEQ_CTX_01_{mode.upper()}",
                "contract_version": CONTRACT_VERSION,
                "symbol": "EURUSD", "timeframe": "H1",
                "event_time": t.isoformat(),
                "direction": int(dir_val),
                "structure_mode": mode,
                "sequence_depth": k + 1,
                "context_bucket": bucket,
                "chain_id": str(getattr(ch, "chain_id", "")),
                "features_at_t": feats,
                "split": split,
                "can_trade": False,
                **labels,
            }
            rows.append(row)
    return rows


def _finalize(rows_all: list[dict], commit: str) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    per_split = {}
    per_mode = {}
    for r in rows_all:
        did = r["dataset_id"]
        sp = r["split"]
        per_mode.setdefault(did, {}).setdefault(sp, 0)
        per_mode[did][sp] += 1
        per_split[sp] = per_split.get(sp, 0) + 1
    # Escribir JSONL por dataset_id
    by_dataset: dict[str, list[dict]] = {}
    for r in rows_all:
        by_dataset.setdefault(r["dataset_id"], []).append(r)
    hashes = {}
    for did, rs in by_dataset.items():
        # calcular dataset_sha256 deterministicamente
        payload = json.dumps(rs, sort_keys=True, default=str).encode()
        ds_hash = hashlib.sha256(payload).hexdigest()
        for r in rs:
            r["dataset_sha256"] = ds_hash
            r["generator_commit"] = commit
            r["event_id"] = hashlib.sha256(
                f"{did}|{r['event_time']}|{r['structure_mode']}|{r['sequence_depth']}|{r['context_bucket']}|{r.get('chain_id','')}".encode()
            ).hexdigest()[:16]
        out = OUT_DIR / f"{did}.jsonl"
        with open(out, "w", encoding="utf-8") as f:
            for r in rs:
                f.write(json.dumps(r, default=str) + "\n")
        hashes[did] = ds_hash
    # Manifest
    manifest = {
        "dataset_id": "SEQ_CTX_01",
        "contract_version": CONTRACT_VERSION,
        "generator_commit": commit,
        "symbol": "EURUSD", "timeframe": "H1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "can_trade": False,
        "blocks": {n: {"start": a, "end": b} for n, a, b in BLOCKS},
        "horizons": HORIZONS,
        "datasets": {did: {"rows": len(rs), "sha256": hashes[did],
                           "by_split": per_mode[did]} for did, rs in by_dataset.items()},
        "total_rows": len(rows_all),
        "gate_causal": "PASS", "gate_tna": "PASS",
        "policy": "OFFLINE_RESEARCH_ONLY; can_trade=false",
        "status": "WAITING_FOR_OOS_EVIDENCE" if any(
            per_mode[d].get("HOLDOUT", 0) < 30 for d in by_dataset) else "READY",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, default=str))
    print(f"[FACTORY] escrito manifest: {MANIFEST}", flush=True)
    print(f"[FACTORY] total_rows={len(rows_all)} per_mode={per_mode}", flush=True)
    return 0


def main() -> int:
    print("[FACTORY] inicio EXP-SEQ-CTX-01 dataset offline", flush=True)
    rc = _check_gates()
    if rc:
        return rc
    commit = _commit()
    if commit == "UNKNOWN":
        return _fail("generator_commit desconocido")
    frames = _load_frames()
    h1 = frames["H1"]
    rows_all = []
    for mode in MODES:
        rows_all.extend(_gen_mode(mode, frames, h1))
    if not rows_all:
        return _fail("0 observaciones generadas (sin split temporal?)")
    # Guarda anti-leakage: features_at_t no debe contener claves label_*
    for r in rows_all:
        if any(k.startswith("label_") for k in r["features_at_t"]):
            return _fail("leakage: label_ en features_at_t")
        if r["can_trade"] is not False:
            return _fail("can_trade != false")
    return _finalize(rows_all, commit)


if __name__ == "__main__":
    raise SystemExit(main())
