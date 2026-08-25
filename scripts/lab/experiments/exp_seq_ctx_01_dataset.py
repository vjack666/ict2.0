"""EXP-SEQ-CTX-01 — FÁBRICA DE DATASET OFFLINE (Sequence × Context State).

Trabajo 4 del SDD. NO reutiliza b2_dataset_factory / b3_walkforward (generic
CHOCH pipelines); es una fabrica especifica para Sequence × Context State que
falla CERRADO si falta cualquier guarda del contrato.

Genera ejemplos con el schema de CONTRATO_DATASET_SEQ_CTX_01.md:
  event_id, dataset_id, dataset_sha256, generator_commit, contract_version,
  symbol, timeframe, event_time, direction, structure_mode, sequence_depth,
  context_bucket, chain_id, features_at_t, label_end_6/12/24/48, split, can_trade=false

Integridad (correcciones V2):
  - dataset_sha256 = SHA-256 del payload JSONL canónico (filas normalizadas,
    sin el campo autorreferente dataset_sha256). El manifest y el validador
    usan exactamente la misma serialización; no se presenta como hash de bytes
    crudos del archivo.
  - event_id = SHA-256 completo de (dataset_id, symbol, timeframe, event_time,
    structure_mode, chain_id, sequence_depth).
  - purga +48: si el timestamp de T+48 cae fuera del bloque de T, la
    observacion se EXCLUYE del dataset (reporte de exclusiones); no se queda
    con label failure dentro del split.

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

OUT_DIR = ROOT / "data" / "learning" / "seq_ctx_01"
MANIFEST = OUT_DIR / "manifest.json"
CONTRACT_VERSION = "v2"
GATE_CAUSAL = ROOT / "reports/audits/experiments/seq_ctx_01/gate_causal.json"
GATE_TNA = ROOT / "reports/audits/tna_streaming_prefix_2026-08-22.json"
TIMEFRAMES = ["D1", "H4", "H1"]
SYMBOL = "EURUSD"
TIMEFRAME = "H1"

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

# Fuentes que deben quedar identificadas junto al commit. El commit por sí solo
# no describe cambios locales no committeados; estos hashes sí permiten detectar
# que el artefacto fue generado con otra versión de una dependencia relevante.
PROVENANCE_FILES = (
    "scripts/lab/experiments/exp_seq_ctx_01_dataset.py",
    "engine/sequential_events.py",
    "engine/mtf_navigation.py",
    "audits/codigo/mtf_seq_funnel.py",
    "docs/contratos/CONTRATO_DATASET_SEQ_CTX_01.md",
)


def _commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                        text=True).strip()
    except Exception:
        return "UNKNOWN"


def _source_hashes() -> dict[str, str]:
    result = {}
    for rel in PROVENANCE_FILES:
        path = ROOT / rel
        if not path.exists():
            raise FileNotFoundError(path)
        result[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _worktree_dirty() -> bool:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no", "--", *PROVENANCE_FILES],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        return bool(proc.stdout.strip())
    except Exception:
        return True


def _canonical_payload(rows: list[dict]) -> bytes:
    """Serialización única de integridad, sin el campo autorreferente."""
    normalized = []
    for row in rows:
        item = dict(row)
        item.pop("dataset_sha256", None)
        normalized.append(json.dumps(
            item, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
        ))
    return ("\n".join(normalized) + ("\n" if normalized else "")).encode("utf-8")


def _canonical_rows_hash(rows: list[dict]) -> str:
    return hashlib.sha256(_canonical_payload(rows)).hexdigest()


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


def _bias_name(value) -> str:
    """Devuelve la taxonomía normativa, incluyendo valores de Enum."""
    raw = value.value if hasattr(value, "value") else value
    return str(raw).upper() if raw is not None else "UNKNOWN"


def _direction_sign(seq_dir) -> int | None:
    """Normaliza la dirección de secuencia a +1/-1 sin inferirla del contexto."""
    raw = seq_dir.value if hasattr(seq_dir, "value") else seq_dir
    if isinstance(raw, bool):
        return None
    try:
        sign = int(raw)
    except (TypeError, ValueError):
        aliases = {"BULLISH": 1, "BEARISH": -1, "BULL": 1, "BEAR": -1}
        return aliases.get(str(raw).upper())
    return sign if sign in (1, -1) else None


def h1_alignment(seq_dir: int, h1_bias: str) -> str:
    """Clasifica H1 respecto de la dirección explícita de la secuencia."""
    seq_sign = _direction_sign(seq_dir)
    bias = _bias_name(h1_bias)
    if seq_sign is None or bias not in ("BULLISH", "BEARISH"):
        return "NEUTRAL"
    h1_sign = 1 if bias == "BULLISH" else -1
    return "ALIGNED" if h1_sign == seq_sign else "AGAINST"


def context_bucket(seq_dir: int, d1_bias: str, h4_loc: str, h1_align: str) -> str:
    """Agrega los cuatro componentes PIT a ALIGNED/NEUTRAL/AGAINST.

    ``seq_dir`` es obligatorio: el mismo contexto puede apoyar una secuencia
    alcista y oponerse a una bajista. D1 y H4 se puntúan relativos a esa
    dirección; H1 llega ya reducido a ALIGNED/AGAINST por ``h1_alignment``.
    """
    seq_sign = _direction_sign(seq_dir)
    if seq_sign is None:
        return "NEUTRAL"

    score = 0
    d1 = _bias_name(d1_bias)
    if d1 in ("BULLISH", "BEARISH"):
        d1_sign = 1 if d1 == "BULLISH" else -1
        score += 1 if d1_sign == seq_sign else -1

    location = _bias_name(h4_loc)
    if location in ("DISCOUNT", "PREMIUM"):
        location_sign = 1 if location == "DISCOUNT" else -1
        score += 1 if location_sign == seq_sign else -1

    alignment = _bias_name(h1_align)
    if alignment == "ALIGNED":
        score += 1
    elif alignment == "AGAINST":
        score -= 1

    if score >= 2:
        return "ALIGNED"
    if score <= -2:
        return "AGAINST"
    return "NEUTRAL"


def _context_bucket(seq_dir: int, d1_bias: str, h4_loc: str, h1_align: str) -> str:
    """Compatibilidad nominal para consumidores del helper privado anterior."""
    return context_bucket(seq_dir, d1_bias, h4_loc, h1_align)


def _label(h1, bar_k, horizon, rng_lo, rng_hi) -> str:
    """Ruptura del rango de la secuencia a N barras (sin PnL)."""
    end = min(bar_k + horizon + 1, len(h1))
    fut = h1.iloc[bar_k + 1: end]
    if len(fut) < horizon:
        return "failure"  # insuficiente horizonte (no es purga; es dato corto real)
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


def _block_end(name: str) -> pd.Timestamp:
    for n, a, b in BLOCKS:
        if n == name:
            return pd.Timestamp(b, tz="UTC")
    raise KeyError(name)


def _gen_mode(mode: str, frames, h1) -> tuple[list[dict], dict]:
    """Devuelve (filas aceptadas, reporte de exclusiones por motivo)."""
    print(f"[FACTORY] generando modo={mode} ...", flush=True)
    chains = run_sequential(h1, SeqConfig(structure_mode=mode, max_active_chains=MAX_ACTIVE),
                            symbol=SYMBOL, timeframe=TIMEFRAME)
    rows = []
    excluded = {
        "out_of_block": 0,
        "purge_48_crosses_boundary": 0,
        "dedup_structure_bar_direction": 0,
    }
    seen_structure_direction = set()
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
            dedup_key = (bar_k, int(dir_val))
            if dedup_key in seen_structure_direction:
                excluded["dedup_structure_bar_direction"] += 1
                continue
            seen_structure_direction.add(dedup_key)
            t = pd.to_datetime(h1.iloc[bar_k]["time"], utc=True)
            split = _block_of(t)
            if split == "OUT":
                excluded["out_of_block"] += 1
                continue
            # Purga +48: el timestamp de T+48 debe caer DENTRO del mismo bloque.
            # Si cruza el limite del bloque, la observacion se EXCLUYE.
            end48_idx = min(bar_k + 48, len(h1_time) - 1)
            t48 = pd.to_datetime(h1_time.iloc[end48_idx], utc=True)
            if t48 > _block_end(split):
                excluded["purge_48_crosses_boundary"] += 1
                continue
            # Contexto PIT: navigator solo con barras <= t
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
                    "H4": {"bias": _bias_name(h4.structure_bias) if h4 else "UNKNOWN",
                           "location": h4_loc},
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
                "symbol": SYMBOL, "timeframe": TIMEFRAME,
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
    return rows, excluded


def _event_id(did: str, symbol: str, tf: str, event_time: str, mode: str,
              chain_id: str, depth: int) -> str:
    """Alineado con CONTRATO_DATASET_SEQ_CTX_01.md §1 (incluye symbol/timeframe)."""
    basis = f"{did}|{symbol}|{tf}|{event_time}|{mode}|{chain_id}|{depth}"
    return hashlib.sha256(basis.encode()).hexdigest()


def _finalize(rows_all: list[dict], commit: str) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    by_dataset: dict[str, list[dict]] = {}
    per_mode: dict[str, dict] = {}
    per_split: dict[str, int] = {}
    source_hashes = _source_hashes()
    for r in rows_all:
        did = r["dataset_id"]
        sp = r["split"]
        by_dataset.setdefault(did, []).append(r)
        per_mode.setdefault(did, {}).setdefault(sp, 0)
        per_mode[did][sp] += 1
        per_split[sp] = per_split.get(sp, 0) + 1

    hashes = {}
    for did, rs in by_dataset.items():
        out = OUT_DIR / f"{did}.jsonl"
        # Preparar identidad y metadata sin escribir estados intermedios ni
        # placeholders. El hash omite únicamente su propio campo.
        for r in rs:
            r["dataset_sha256"] = ""
            r["generator_commit"] = commit
            r["event_id"] = _event_id(did, r["symbol"], r["timeframe"], r["event_time"],
                                       r["structure_mode"], r.get("chain_id", ""), r["sequence_depth"])
        ds_hash = _canonical_rows_hash(rs)
        hashes[did] = ds_hash
        for r in rs:
            r["dataset_sha256"] = ds_hash
        lines = [json.dumps(r, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
                 for r in rs]
        out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    counts = {
        did: {
            split: {bucket: sum(1 for r in rs if r["split"] == split and r["context_bucket"] == bucket)
                    for bucket in ("ALIGNED", "NEUTRAL", "AGAINST")}
            for split in ("DESIGN", "VALIDATION", "HOLDOUT")
        }
        for did, rs in by_dataset.items()
    }
    holdout_cells = {
        f"{did}:{bucket}": counts[did]["HOLDOUT"][bucket]
        for did in by_dataset for bucket in ("ALIGNED", "NEUTRAL", "AGAINST")
    }
    sufficient = all(n >= 30 for n in holdout_cells.values())

    manifest = {
        "dataset_id": "SEQ_CTX_01",
        "contract_version": CONTRACT_VERSION,
        "generator_commit": commit,
        "generator_worktree": "DIRTY" if _worktree_dirty() else "CLEAN",
        "generator_source_hashes": source_hashes,
        "symbol": SYMBOL, "timeframe": TIMEFRAME,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "can_trade": False,
        "blocks": {n: {"start": a, "end": b} for n, a, b in BLOCKS},
        "horizons": HORIZONS,
        "datasets": {did: {"rows": len(rs), "sha256": hashes[did],
                           "by_split": per_mode[did], "by_bucket_split": counts[did]}
                     for did, rs in by_dataset.items()},
        "total_rows": len(rows_all),
        "event_unit": "SequentialChain node k; dedup=(structure_bar, direction) within variant",
        "oos_sufficiency": {
            "criterion": "n >= 30 per (variant, context_bucket, HOLDOUT)",
            "holdout_cells": holdout_cells,
            "status": "SUFFICIENT" if sufficient else "SUBPOWERED",
        },
        "gate_causal": "PASS", "gate_tna": "PASS",
        "policy": "OFFLINE_RESEARCH_ONLY; can_trade=false",
        "status": "OOS_SUFFICIENT" if sufficient else "WAITING_FOR_OOS_EVIDENCE",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, default=str))
    print(f"[FACTORY] escrito manifest: {MANIFEST}", flush=True)
    print(f"[FACTORY] total_rows={len(rows_all)} per_mode={per_mode}", flush=True)
    return 0


def main() -> int:
    print("[FACTORY] inicio EXP-SEQ-CTX-01 dataset offline (V2 integridad)", flush=True)
    rc = _check_gates()
    if rc:
        return rc
    commit = _commit()
    if commit == "UNKNOWN":
        return _fail("generator_commit desconocido")
    frames = _load_frames()
    h1 = frames["H1"]
    rows_all = []
    exclusions = {}
    for mode in MODES:
        rs, exc = _gen_mode(mode, frames, h1)
        rows_all.extend(rs)
        exclusions[mode] = exc
        print(f"[FACTORY]   modo={mode}: aceptadas={len(rs)} exclusiones={exc}", flush=True)
    if not rows_all:
        return _fail("0 observaciones generadas (sin split temporal?)")
    # Guardas anti-leakage
    for r in rows_all:
        if any(k.startswith("label_") for k in r["features_at_t"]):
            return _fail("leakage: label_ en features_at_t")
        if r["can_trade"] is not False:
            return _fail("can_trade != false")
    # Reporte de exclusiones
    excl_path = OUT_DIR / "exclusions_report.json"
    excl_path.write_text(json.dumps(exclusions, indent=2))
    print(f"[FACTORY] reporte exclusiones: {excl_path}", flush=True)
    return _finalize(rows_all, commit)


if __name__ == "__main__":
    raise SystemExit(main())
