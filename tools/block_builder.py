"""Block builder: extrae VENTANAS DE VELAS CRUDAS alrededor de un evento.

Este módulo es el "ojo" del sistema de aprendizaje ICT: en vez de alimentar
al modelo con features ya procesadas (score_n, momentum, ...), entrega el
BLOQUE DE VELAS CRUDO (OHLC + volumen + spread) en una ventana CAUSAL
centrada en el break_bar del CHOCH. La IA aprende el comportamiento y la
naturaleza del patrón viendo las velas, no un reporte humano.

Ventana causal (SIN look-ahead en inferencia):
  [-W_pre, break_bar]  -> input (lo que ocurrio ANTES/debajo del evento)
  [break_bar+1, break_bar+W_post] -> contexto de etiquetado (SOLO para labels,
                                     nunca se pasa al encoder en inferencia)

Normalizacion anti-estacionariedad (la IA ve FORMA, no nivel de precio):
  - log-returns de close
  - (high-low)/mid, (close-open)/mid  (rango y cuerpo relativos al mid)
  - tick_volume / rolling_mean, spread / rolling_mean

Reusa el esquema de chunks+lead-in de scripts/gen_choch_dataset.py para no
cortar swings/BOS en el borde y procesar M5 (334k velas) sin explotar RAM.

Contrato de salida (por evento):
  {
    "tf", "symbol", "time", "signal", "bar", "cd",
    "X":    ndarray (W_pre, n_feat)   # input causal del encoder
    "y_win":ndarray (W_post, n_feat)  # ventana futura (target auto-sup)
    "meta": {...}                     # para labels de naturaleza (P3)
  }
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Features de cada vela normalizada (forma, no nivel)
NORM_FEATS = ["logret", "body", "wick_up", "wick_dn", "range", "vol", "spread"]

W_PRE_DEFAULT = 60      # velas antes del break (contexto del "ojo")
W_POST_DEFAULT = 30     # velas despues (para label de naturaleza / auto-sup)


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve DataFrame normalizado con columnas NORM_FEATS (sin look-ahead).

    OPCION A perf (2026-08-20): vectorizado con numpy (sin pandas .rolling),
    evita el cuello de botella sobre 334k velas M5.
    """
    close = df["close"].to_numpy(dtype=float)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    open_ = df["open"].to_numpy(dtype=float)
    vol = df["tick_volume"].to_numpy(dtype=float)
    spread = df["spread"].to_numpy(dtype=float)

    mid = (high + low) / 2.0
    mid = np.where(mid == 0, close, mid)
    logret = np.zeros_like(close)
    logret[1:] = np.diff(np.log(close + 1e-12))
    body = (close - open_) / mid
    wick_up = (high - np.maximum(close, open_)) / mid
    wick_dn = (np.minimum(close, open_) - low) / mid
    rng = (high - low) / mid
    # volumen y spread relativos a media movil (ventana 60, numpy stride-view)
    vol_ma = _rolling_mean(vol, 60)
    vol_rel = np.where(vol_ma > 0, vol / vol_ma, 0.0)
    spread_ma = _rolling_mean(spread, 60)
    spread_rel = np.where(np.isfinite(spread_ma) & (spread_ma > 0), spread / spread_ma, 0.0)

    out = pd.DataFrame({
        "logret": logret, "body": body, "wick_up": wick_up, "wick_dn": wick_dn,
        "range": rng, "vol": vol_rel, "spread": spread_rel,
    }, index=df.index)
    return out


def _rolling_mean(a: np.ndarray, w: int) -> np.ndarray:
    """Media movil vectorizada O(n) via cumsum (evita pandas y loops)."""
    a = np.nan_to_num(a, nan=0.0)
    n = len(a)
    if n == 0:
        return a
    cum = np.zeros(n + 1, dtype=float)
    np.cumsum(a, out=cum[1:])
    out = np.empty(n, dtype=float)
    for i in range(n):
        s = max(0, i - w + 1)
        out[i] = (cum[i + 1] - cum[s]) / (i - s + 1)
    return out


def build_blocks(
    df: pd.DataFrame,
    events: list,                 # lista de dicts/stub con break_bar, signal, time, tf
    w_pre: int = W_PRE_DEFAULT,
    w_post: int = W_POST_DEFAULT,
) -> list[dict]:
    """Extrae bloques causales para cada evento cuyo break_bar caiga en zona limpia.

    df: DataFrame de velas del TF (time indexado). NO se modifica.
    Devuelve lista de dicts (ver docstring del modulo).
    """
    norm = _normalize(df)
    n = len(df)
    close = df["close"].to_numpy(dtype=float)
    out = []
    for ev in events:
        i = ev.get("break_bar")
        if i is None:
            i = ev.get("bar_index")
        if i is None or i < 0:
            continue
        # zona limpia: no cortar en bordes
        if i - w_pre < 1 or i + w_post >= n:
            continue
        X = norm.iloc[i - w_pre: i + 1].to_numpy(dtype=float)      # [i-w_pre .. i]
        y_win = norm.iloc[i + 1: i + 1 + w_post].to_numpy(dtype=float)
        cd = 1 if ev.get("signal") == "CHOCH_UP" else -1
        out.append({
            "tf": ev.get("tf"),
            "symbol": ev.get("symbol"),
            "time": str(df["time"].iloc[i]),
            "signal": ev.get("signal"),
            "bar": int(i),
            "cd": cd,
            "X": X.astype(np.float32),
            "y_win": y_win.astype(np.float32),
            "price_level": float(close[i]),
        })
    return out


def build_tf_blocks(
    parquet_path: str,
    events: list,
    w_pre: int = W_PRE_DEFAULT,
    w_post: int = W_POST_DEFAULT,
    chunk: int = 20000,
    overlap: int = 200,
) -> list[dict]:
    """Igual que build_blocks pero lee parquet por CHUNKS (reusa patron de gen_choch_dataset).

    events: lista global; se filtran los que caen en cada chunk via break_bar global.
    """
    d = pd.read_parquet(parquet_path)
    d = d.assign(time=pd.to_datetime(d["time"])).reset_index(drop=True)
    n = len(d)
    blocks: list[dict] = []
    # indice por break_bar (global)
    ev_by_bar = {e.get("break_bar") or e.get("bar_index"): e for e in events
                 if (e.get("break_bar") or e.get("bar_index")) is not None}
    # OPCION A perf (2026-08-20): indexar eventos por chunk UNA vez, no loop global
    # por cada chunk. Evita O(eventos x chunks) -> O(eventos + chunks).
    from collections import defaultdict
    ev_by_chunk: dict[int, list] = defaultdict(list)
    for gb, e in ev_by_bar.items():
        ev_by_chunk[gb // chunk].append((gb, e))
    start = 0
    while start < n:
        end = min(start + chunk, n)
        seg = d.iloc[max(0, start - overlap): end].reset_index(drop=True)
        g0 = max(0, start - overlap)
        cid = start // chunk
        seg_events = []
        for gb, e in ev_by_chunk.get(cid, []):
            if g0 <= gb < end:
                ec = dict(e)
                ec["break_bar"] = gb - g0   # indice local
                seg_events.append(ec)
        seg_blocks = build_blocks(seg, seg_events, w_pre, w_post)
        blocks.extend(seg_blocks)
        start = end
    # dedupe por (tf,time,signal)
    seen = set()
    uniq = []
    for b in blocks:
        key = (b["tf"], b["time"], b["signal"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(b)
    return uniq


if __name__ == "__main__":
    # Smoke: construye bloques del mes 2026-08 de CHOCH crudos
    import json, glob, os, sys
    sys.path.insert(0, ".")
    from tools.choch import CHOCHTool
    from tools.swing import SwingTool
    from tools.bos import BOSTool
    from tools.bos_validate import apply_validation
    from tools.bos_filter import filter_bos_thesis
    from tools.displacement import detect_displacement

    SYM = "EURUSD"
    d = pd.read_parquet(f"data/raw/{SYM}/{SYM}_M5.parquet")
    d = d.assign(time=pd.to_datetime(d["time"])).reset_index(drop=True)
    out = detect_displacement(d)
    sw = SwingTool(lookback=5).run(out, symbol=SYM)
    sids = {e.origin_bar: e.id for e in sw}
    bo = BOSTool(lookback=5).run(out, symbol=SYM, context={"swing_ids": sids})
    bo = apply_validation(out, bo)
    bo = filter_bos_thesis(out, bo, confirm_bars=2, max_idle_bars=0)
    che = CHOCHTool().run(out, symbol=SYM, context={"swings": sw, "boses": bo})
    evs = [{"break_bar": (e.break_bar if e.break_bar is not None else e.bar_index),
            "signal": e.signal, "tf": "M5", "symbol": SYM,
            "time": str(d["time"].iloc[e.break_bar]) if e.break_bar is not None else None}
           for e in che if (e.break_bar if e.break_bar is not None else e.bar_index) is not None]
    blocks = build_blocks(d, evs, w_pre=60, w_post=30)
    print(f"bloques CHOCH M5 (sample mes): {len(blocks)}")
    if blocks:
        b0 = blocks[0]
        print("X shape:", b0["X"].shape, "y_win shape:", b0["y_win"].shape)
        print("features:", NORM_FEATS)
