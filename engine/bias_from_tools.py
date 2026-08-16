"""engine/bias_from_tools.py — Adaptador: sesgo del motor USANDO tools/ (Fase 1 + Task 6).

PROPOSITO:
  El motor de lectura (engine/plan.py) calcula el sesgo desde un df anotado
  con columnas bos_dir/bos_status/choch_dir/choch_status (via motor viejo).
  Este adaptador produce ESE MISMO formato pero usando las herramientas
  corregidas y PROFESIONALIZADAS de tools/:
    - SwingTool (objeto persistente)
    - BOSTool + apply_validation (ACTIVE/INVALIDATED)
    - tools.displacement (geometria pura, SIN ATR)
    - tools.quality_score (score 0-1 + is_real)
    - CHOCHTool (fallback swings) + tools.choch_quality (EXP-012: CHOCH real)
    - tools.swing_state (estado temporal fresh/tested/mitigated/invalidated)
  Asi la mejora de Fase 1/Task6 SIRVE para uso real del motor (uso diario).

RESPESTA AISLAMIENTO (Ley Task 2):
  engine/ importa tools/ (permitido). tools/ NO importa engine/.

METODOLOGIA (geometria de mercado, sin ATR):
  displacement usa rango promedio high-low (no ATR). quality_score usa
  body_ratio / distancia al nivel / rango promedio. Todo matematica pura.
"""
from __future__ import annotations

from typing import Any

import os
import numpy as np
import pandas as pd

from tools.swing import SwingTool
from tools.bos import BOSTool
from tools.bos_validate import apply_validation
from tools.choch import CHOCHTool
from tools.bos_filter import filter_bos_thesis
from tools.displacement import detect_displacement
from tools.quality_score import compute_quality, QualityConfig
from tools.choch_quality import mark_choch_quality
from tools.swing_state import ObjectState, next_state_on_test


def annotate_with_tools(df: pd.DataFrame, symbol: str = "EURUSD",
                        max_idle_bars: int = 0, require_htf_alignment: bool = False,
                        htf_frames: dict | None = None, tf: str = "M5") -> pd.DataFrame:
    """Devuelve df anotado compatible con engine.plan (_bias_from_frame) pero
    usando herramientas corregidas + profesionales de tools/.

    Columnas: bos_dir, bos_status, bos_real, bos_level, choch_dir,
    choch_status, choch_proj_level, displacement_*, quality_score.

    Fase 4: tf parametriza el lookback adaptativo del SwingTool (M5=5, H4=20,
    D1=30) para que cada TF use su ventana de estructura MAYOR (SPEC §47, §49).
    """
    out = df.copy().reset_index(drop=True)
    out["bos_dir"] = 0
    out["bos_status"] = "none"
    out["bos_real"] = False
    out["bos_level"] = np.nan
    out["bos_quality"] = np.nan
    out["choch_dir"] = 0
    out["choch_status"] = "none"
    out["choch_proj_level"] = np.nan
    out["choch_real"] = False

    # 1. displacement (geometria pura, SIN ATR) sobre el frame
    out = detect_displacement(out)

    # F4: SwingTool con lookback adaptativo por TF (Fase 1), no 5 ciego.
    sw = SwingTool(tf=tf)
    swe = sw.run(out, symbol=symbol)
    sids = {e.origin_bar: e.id for e in swe}

    # 2. BOS (hijo de swing) + validacion geometrica + filtro tesis
    bo = BOSTool(lookback=5)
    boe_raw = bo.run(out, symbol=symbol, context={"swing_ids": sids})
    boe_raw = apply_validation(out, boe_raw)
    boe = filter_bos_thesis(out, boe_raw, htf_frames=htf_frames, confirm_bars=2,
                            max_idle_bars=max_idle_bars,
                            require_htf_alignment=require_htf_alignment)

    # escribir BOS en out ANTES de quality_score (lo necesita)
    for e in boe:
        i = e.break_bar if e.break_bar is not None else e.bar_index
        if i is None or i < 0 or i >= len(out):
            continue
        out.loc[i, "bos_dir"] = 1 if e.signal == "BOS_UP" else -1
        out.loc[i, "bos_level"] = float(e.price) if e.price is not None else np.nan
        out.loc[i, "bos_status"] = "active" if getattr(e, "status", "") != "invalidated" else "invalidated"

    # 3. quality_score sobre BOS (usa displacement ya en out + bos_dir/bos_level)
    q, real = compute_quality(
        out,
        bos_dir_col="bos_dir",
        bos_level_col="bos_level",
        config=QualityConfig(quality_threshold=0.5, confirm_bars=2),
    )
    for e in boe:
        i = e.break_bar if e.break_bar is not None else e.bar_index
        if i is None or i < 0 or i >= len(out):
            continue
        out.loc[i, "bos_real"] = bool(real.iloc[i]) if not np.isnan(real.iloc[i]) else bool(e.extra.get("thesis_valid", False))
        out.loc[i, "bos_quality"] = float(q.iloc[i]) if not np.isnan(q.iloc[i]) else np.nan

    # 4. CHOCH (fallback swings) + filtro tesis
    ch = CHOCHTool()
    che = ch.run(out, symbol=symbol, context={"swings": swe, "boses": boe})
    che = filter_bos_thesis(out, che, htf_frames=htf_frames, confirm_bars=2,
                            max_idle_bars=max_idle_bars,
                            require_htf_alignment=require_htf_alignment)

    # 5. CHOCH calidad (EXP-012): momentum + after_bos + nivel HL/LH + score 0-100
    #    pasamos boe_raw (todos los BOS del mercado) y htf_frames para el score
    che = mark_choch_quality(out, che, swe, boe_raw, htf_frames=htf_frames)

    for e in che:
        i = e.break_bar if e.break_bar is not None else e.bar_index
        if i is None or i < 0 or i >= len(out):
            continue
        out.loc[i, "choch_dir"] = 1 if e.signal == "CHOCH_UP" else -1
        out.loc[i, "choch_status"] = "active" if getattr(e, "status", "") != "invalidated" else "invalidated"
        if e.price is not None:
            out.loc[i, "choch_proj_level"] = float(e.price)
        out.loc[i, "choch_real"] = bool(e.extra.get("choch_real", False))
        # superficie del score hibrido calibrado (incluye componente IA 15%)
        out.loc[i, "choch_score"] = float(e.extra.get("choch_score", 0.0))
        out.loc[i, "choch_class"] = str(e.extra.get("choch_class", "noise"))
        out.loc[i, "choch_ia_prob"] = float(e.extra.get("choch_ia_prob", 0.0))

    return out


def bias_from_tools(df: pd.DataFrame, t: Any) -> str:
    """Sesgo por estructura (igual firma que engine.plan._bias_from_frame)
    sobre df anotado por tools/ profesionales. CHOCH real manda sobre BOS real.
    """
    if df is None or len(df) == 0 or "time" not in df.columns:
        return "RANGING"
    times = pd.to_datetime(df["time"], utc=True, errors="coerce")
    tt = pd.to_datetime(t, utc=True, errors="coerce")
    if pd.isna(tt):
        return "RANGING"
    sub = df.loc[times <= tt]
    if len(sub) == 0:
        return "RANGING"
    has_real = "bos_real" in sub.columns
    has_choch_class = "choch_class" in sub.columns
    last_bos_idx = last_bos_dir = 0
    last_choch_idx = last_choch_dir = 0
    last_choch_class = ""
    for i in range(len(sub)):
        bd = sub["bos_dir"].iloc[i]
        if bd not in (0, "0", None) and str(sub["bos_status"].iloc[i]) == "active" \
           and (not has_real or bool(sub["bos_real"].iloc[i])):
            last_bos_idx, last_bos_dir = i, int(bd)
        cd = sub["choch_dir"].iloc[i]
        if cd not in (0, "0", None) and str(sub["choch_status"].iloc[i]) == "active":
            # T9.7: CHOCH solo cuenta si el BOS contrario era REAL (bos_real)
            if has_real:
                opp = -int(cd)
                cand = sub.iloc[:i]
                hit = cand[
                    (cand["bos_dir"] == opp)
                    & (cand["bos_status"] == "active")
                    & (cand["bos_real"].fillna(False).astype(bool))
                ]
                if len(hit) == 0:
                    continue
            last_choch_idx, last_choch_dir = i, int(cd)
            if has_choch_class:
                last_choch_class = str(sub["choch_class"].iloc[i])
    if last_choch_dir != 0:
        base = "BULLISH" if last_choch_dir > 0 else "BEARISH"
        if last_choch_class in ("premium", "useful", "noise"):
            return f"{base} ({last_choch_class})"
        return base
    if last_bos_dir != 0:
        return "BULLISH" if last_bos_dir > 0 else "BEARISH"
    return "RANGING"


def bias_from_tools_htf(
    d1: pd.DataFrame,
    h4: pd.DataFrame,
    h1: pd.DataFrame,
    htf_frames: dict | None = None,
    symbol: str = "EURUSD",
    max_idle_bars: int = 0,
    require_htf_alignment: bool = False,
) -> dict:
    """Sesgo HTF unificado usando las herramientas corregidas de tools/.

    Equivalente a compute_htf_bias de narrative.py PERO con el motor de
    deteccion profesional (Swing/BOS/CHOCH + displacement + quality + score).
    Compone D1->H4->H1 via _compose_htf_bias (misma regla de autoridad).

    Devuelve dict con 'd1','h4','h1','direction','aligned' (igual interfaz
    que HtfBias de narrative.py) para que htf_narrative lo consuma sin cambios.
    """
    from engine.bias.narrative import _compose_htf_bias  # lazy: evita ciclo

    def _one(tf_name, tf_df):
        if tf_df is None or len(tf_df) < 3:
            return "RANGING"
        ann = annotate_with_tools(
            tf_df, symbol=symbol, max_idle_bars=max_idle_bars,
            require_htf_alignment=require_htf_alignment, htf_frames=htf_frames,
            tf=tf_name,   # F4: lookback adaptativo por TF
        )
        return bias_from_tools(ann, str(tf_df["time"].iloc[-1]))

    d1b = _one("D1", d1)
    h4b = _one("H4", h4)
    h1b = _one("H1", h1)
    direction = _compose_htf_bias(d1b, h4b, h1b)
    non_neutral = [v for v in (d1b, h4b, h1b) if v != "RANGING"]
    aligned = len(non_neutral) >= 2 and len(set(non_neutral)) == 1
    return {
        "d1": d1b, "h4": h4b, "h1": h1b,
        "direction": direction, "aligned": aligned,
    }


def build_daily_bias(symbol: str = "EURUSD",
                     month: str = "2026-08",
                     max_idle_bars: int = 0,
                     require_htf_alignment: bool = False) -> dict:
    """Cableado PARA USO DIARIO: sesgo HTF jerarquico listo para el motor.

    Carga las velas CERRADAS de cada TF (sin look-ahead: solo cierres
    completos, SPEC §44) desde data/raw, y compone D1->H4->H1 via
    bias_from_tools_htf. No inventa nada: reusa el detector profesional de
    tools/ y la autoridad D1 raiz de narrative._compose_htf_bias.

    Devuelve dict con 'd1','h4','h1','direction','aligned' + 'source'.
    """
    from engine.bias.narrative import _compose_htf_bias  # lazy

    frames = {}
    for tf in ("D1", "H4", "H1"):
        p = f"data/raw/{symbol}/{symbol}_{tf}.parquet"
        if not os.path.exists(p):
            frames[tf] = None
            continue
        d = pd.read_parquet(p)
        d = d.assign(time=pd.to_datetime(d["time"])).reset_index(drop=True)
        m = d["time"].dt.strftime("%Y-%m") == month
        d = d[m].reset_index(drop=True)
        frames[tf] = d if len(d) >= 3 else None

    htf = bias_from_tools_htf(
        d1=frames["D1"], h4=frames["H4"], h1=frames["H1"],
        symbol=symbol, max_idle_bars=max_idle_bars,
        require_htf_alignment=require_htf_alignment,
    )
    htf["source"] = f"tools/ profesionales + _compose_htf_bias (D1 raiz), month={month}"
    return htf
