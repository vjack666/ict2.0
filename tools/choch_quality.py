"""CHOCH de calidad (EXP-012) — rescate aislado de SMC-SYSTEMS.

Fuente: SMC-SYSTEMS/engine/bos/structure.py::_exp012_choch_marks.
Adaptado a tools/ (aislado, usa SwingTool + BOSTool).

Marca CHOCH REALES (bonus de autoridad) aplicando las 4 reglas de la tesis:
  (a) MOMENTUM: racha >=2 HH (uptrend) para CHOCH bajista, o >=2 LL
      (downtrend) para CHOCH alcista. Sin empuje no hay "caracter" que
      cambiar -> es ruido.
  (b) AFTER_BOS REAL: hubo un BOS de mercado confirmado en la direccion
      OPUESTA al CHOCH (el BOS que el CHOCH viene a revertir).
  (c) NIVEL = ULTIMO HL (CHOCH bajista) / LH (alcista) ROTO, NO el nivel
      del BOS roto. Son pivotes distintos; usar el BOS dispara CHOCH
      prematuro y deja ruido.
  (d) RECLAIM: status == invalidated invalida el CHOCH.

Esto es exactamente el salto de "sistema normal" a "profesional" de la tabla
del Director: romper el swing del ultimo BOS + momentum + nivel correcto.

Salida: choch_quality_score (0/1 real) + choch_pivot_level (nivel HL/LH roto).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from tools.event import ToolEvent


def mark_choch_quality(
    df: pd.DataFrame,
    choch_events: list[ToolEvent],
    swing_events: list[ToolEvent],
    bos_events: list[ToolEvent],
    htf_frames: dict | None = None,
) -> list[ToolEvent]:
    """Anota cada CHOCH con extra['choch_real'] y extra['choch_score'] (0-100).

    Usa swings (HH/HL/LH/LL) y BOS (dir, real) de las herramientas de tools/.
    Score hibrido (plan v1.1 F2):
      Estructura 30 + Contexto HTF 20 + Geometria 20 + Confirmacion 15 + IA 15.
    """
    n = len(df)
    if n == 0:
        return choch_events

    # mapeos por barra
    hh_streak = 0
    ll_streak = 0
    last_hl_price = np.nan
    last_lh_price = np.nan

    # BOS dir por barra (1 UP / -1 DN) de TODOS los BOS (incluso invalidados):
    # el CHOCH viene a revertir el ultimo BOS de mercado, aunque ya estuviera
    # invalidado. Filtrar solo los no-invalidados mataba el after_bos en meses
    # con BOS invalidados (bug: interseccion momentum^after_bos ~0).
    bos_dir_by_bar = {}
    for b in bos_events:
        bb = b.break_bar if b.break_bar is not None else b.bar_index
        if bb is None:
            continue
        d = 1 if b.signal == "BOS_UP" else -1
        bos_dir_by_bar[bb] = d

    # swings ordenados por barra para saber HH/HL/LH/LL
    swings_sorted = sorted(
        [s for s in swing_events if s.origin_bar is not None],
        key=lambda e: e.origin_bar,
    )

    # precompute swing labels por barra
    lab_by_bar = {}
    for s in swings_sorted:
        sig = s.signal  # SWING_HH / SWING_HL / SWING_LH / SWING_LL
        lab = {"SWING_HH": "HH", "SWING_HL": "HL", "SWING_LH": "LH", "SWING_LL": "LL"}.get(sig, "NONE")
        lab_by_bar[s.origin_bar] = (lab, s.price)

    # recorrer en orden de barras para mantener rachas (igual que EXP-012)
    last_bos_dir_at = {i: 0 for i in range(n)}
    cur_dir = 0
    for i in range(n):
        if i in bos_dir_by_bar:
            cur_dir = bos_dir_by_bar[i]
        last_bos_dir_at[i] = cur_dir

    # procesar CHOCH en orden de barra
    choch_sorted = sorted(
        [c for c in choch_events if c.break_bar is not None],
        key=lambda e: e.break_bar,
    )
    # necesitamos rachas actualizadas hasta la barra del CHOCH
    # recomputamos rachas recorriendo todas las barras y evaluando CHOCH al vuelo
    hh_streak = ll_streak = 0
    last_hl = last_lh = np.nan
    # indice de CHOCH por barra
    choch_by_bar = {c.break_bar: c for c in choch_sorted}

    # precalculer lab por barra ordenado
    bars = sorted(lab_by_bar.keys())
    bi = 0
    for i in range(n):
        while bi < len(bars) and bars[bi] <= i:
            lab, price = lab_by_bar[bars[bi]]
            if lab == "HH":
                hh_streak += 1
                ll_streak = 0
                last_hl = np.nan
            elif lab == "LL":
                ll_streak += 1
                hh_streak = 0
                last_lh = np.nan
            elif lab == "HL":
                last_hl = price
                ll_streak = 0
            elif lab == "LH":
                last_lh = price
                hh_streak = 0
            bi += 1

        if i not in choch_by_bar:
            continue
        c = choch_by_bar[i]
        cd = 1 if c.signal == "CHOCH_UP" else -1
        # (a) momentum (racha >=2 HH/LL) — campo de score, NO veto único
        if cd == -1:
            momentum_ok = hh_streak >= 2
            lvl = last_hl
        else:
            momentum_ok = ll_streak >= 2
            lvl = last_lh
        # (b) after_bos: hubo BOS de mercado en direccion OPUESTA al CHOCH
        #     (el BOS que el CHOCH viene a revertir). Cualquier BOS previo
        #     cuenta (no exigimos que fuera 'real' para no matar el 99%).
        bos_prev_dir = last_bos_dir_at[i]
        after_bos = (bos_prev_dir == -cd)
        # (c) desplazamiento: en la vela de ruptura O en las 2 siguientes
        #     (confirmacion de intencion, geometria pura SIN ATR). El break
        #     suele ser por mecha; el desplazamiento confirma despues.
        #     IMPORTANTE (decision Director 2026-08-15): el desplazamiento NO
        #     bloquea el CHOCH (un dia de trading necesita CHOCH accionables).
        #     Es bonus de score, no veto.
        disp_now = bool(df["displacement_bullish"].iloc[i]) if cd == 1 else bool(df["displacement_bearish"].iloc[i])
        disp_conf = False
        for j in range(i + 1, min(i + 3, len(df))):
            if cd == 1 and bool(df["displacement_bullish"].iloc[j]):
                disp_conf = True
                break
            if cd == -1 and bool(df["displacement_bearish"].iloc[j]):
                disp_conf = True
                break
        disp = disp_now or disp_conf
        # (d) nivel HL/LH presente (el swing contrario roto)
        lvl_present = pd.notna(lvl)
        # CHOCH REAL = nivel correcto + after_bos (definicion tesis).
        # Desplazamiento es bonus (extra), NO veto.
        is_real = bool(after_bos and lvl_present)

        # --- SCORE HIBRIDO 0-100 (plan v1.1 F2) ---
        # Estructura 30 + Contexto HTF 20 + Geometria 20 + Confirmacion 15 + IA 15
        # Calibracion: is_real solo ya es 'useful' (>=70); disp/momentum/htf
        # empujan a 'premium' (>=85).
        score = 0.0
        # Estructura: nivel correcto + after-BOS es la base del CHOCH real.
        # is_real solo ya es 'useful' (>=70); momentum/htf/disp empujan a premium.
        if is_real:
            score += 70.0
            if momentum_ok:
                score += 10.0
        # Contexto HTF: a favor=20, neutral=10, contra=5
        htf_ctx = "neutral"
        if htf_frames:
            _htf = next(iter(htf_frames.values()))
            htf_trend = str(_htf.get("trend", "RANGING") if isinstance(_htf, dict) else "RANGING")
            if htf_trend == "BULLISH" and cd == 1:
                htf_ctx = "a_favor"; score += 20.0
            elif htf_trend == "BEARISH" and cd == -1:
                htf_ctx = "a_favor"; score += 20.0
            elif htf_trend in ("BULLISH", "BEARISH"):
                htf_ctx = "contra"; score += 5.0
            else:
                score += 10.0
        else:
            score += 10.0
        # Geometria: desplazamiento (intencion de ruptura)
        if disp:
            score += 20.0
        # Confirmacion: el CHOCH no fue invalidado (sobrevive)
        if c.status != "invalidated":
            score += 15.0
        # IA 15%: pendiente fase modelo -> 0 por ahora (extensible)
        # score += 15.0 * modelo_prob
        score = float(np.clip(score, 0.0, 100.0))

        c.extra["choch_real"] = is_real
        c.extra["choch_pivot_level"] = float(lvl) if lvl_present else None
        c.extra["choch_momentum"] = bool(momentum_ok)
        c.extra["choch_after_bos"] = bool(after_bos)
        c.extra["choch_displacement"] = disp
        c.extra["choch_htf_ctx"] = htf_ctx
        c.extra["choch_score"] = score
        # clasificacion operativa
        if score >= 85:
            c.extra["choch_class"] = "premium"
        elif score >= 70:
            c.extra["choch_class"] = "useful"
        else:
            c.extra["choch_class"] = "noise"

    return choch_events
