"""Filtro de BOS según la TESIS ICT (parte del sistema, no calificación humana).

Aplica las reglas canónicas de:
  - docs/ict/02_MSS_CHOCH.md §0 y §1
  - docs/ict/SPEC_TESIS_FORMAL.md §8

sobre los eventos BOS ya emitidos por tools/bos.py, anotando cada uno con:

  thesis_valid   : bool   → cumple la tesis como BOS real / accionable
  thesis_reason  : str    → por qué pasó o falló (cadena de razones)
  is_unique      : bool   → True si es el representante del nivel fusionado
  idle_bars      : int    → barras desde el break hasta el final del df
  htf_aligned    : bool | None

REGLAS DE TESIS IMPLEMENTADAS (citas):
- §8 CRIT: BOS = close rompe swing previo EN DIRECCIÓN; validado por CUERPO.
- §25 / AMBIG §8: confirm_bars = 2 (canónico actual).
- 02 §0 #1: BOS a favor de la tendencia vigente.
- 02 §0 #5 + SPEC §1: LTF se lee SIEMPRE contra sesgo HTF (a favor / contra).
- CASOS LÍMITE §8: CHOCH sin BOS posterior → solo aviso (no aplica aquí).

DECISIONES DE INGENIERÍA (etiquetadas, §25 permite):
- Fusión por (direction, price redondeado a 5 decimales). Un nivel = un setup.
- max_idle_bars: si el nivel no se ha testado en N barras se marca "dormido".
  Default 288 (~1 día M5). 0 = OFF.
- El filtro NO cambia la detección: solo anota. Es consumidor puro.

Uso típico:
    from tools.bos_filter import filter_bos_thesis
    events = bos_tool.run(...)
    annotated = filter_bos_thesis(df_m5, events, htf_frames={"H4": df_h4, "H1": df_h1})
"""
from __future__ import annotations

from collections import defaultdict
from typing import Sequence

import pandas as pd

from tools.event import ToolEvent


def _htf_bias_at(
    df_htf: pd.DataFrame | None,
    bar_time,
) -> int:
    """Sesgo del TF mayor en el momento de la vela (cerrado, sin look-ahead).

    Devuelve:
        1  → BULLISH
       -1  → BEARISH
        0  → RANGING / NEUTRAL / sin datos

    Prioridad de columnas:
        1. trend_int  (ya calculado por detectors.trend)
        2. trend      (string BULLISH/BEARISH/RANGING)
        3. 0 si no hay nada usable
    """
    if df_htf is None or df_htf is None:
        return 0
    if len(df_htf) == 0:
        return 0

    sub = df_htf
    if "time" in df_htf.columns and bar_time is not None:
        try:
            sub = df_htf[df_htf["time"] <= bar_time]
        except Exception:
            sub = df_htf

    if len(sub) == 0:
        return 0

    last = sub.iloc[-1]

    if "trend_int" in sub.columns:
        try:
            return int(last["trend_int"])
        except Exception:
            pass

    if "trend" in sub.columns:
        v = str(last["trend"]).upper()
        if "BULL" in v:
            return 1
        if "BEAR" in v:
            return -1
        return 0

    return 0


def _aggregate_htf_bias(
    htf_frames: dict[str, pd.DataFrame] | None,
    bar_time,
    priority: Sequence[str] = ("D1", "H4", "H1"),
) -> int:
    """Combina sesgos HTF por prioridad (el más alto que no sea neutral gana).

    Si todos son 0 → 0 (neutral).
    """
    if not htf_frames:
        return 0

    for tf in priority:
        if tf in htf_frames:
            b = _htf_bias_at(htf_frames[tf], bar_time)
            if b != 0:
                return b
    return 0


def filter_bos_thesis(
    df: pd.DataFrame,
    events: list[ToolEvent],
    htf_frames: dict[str, pd.DataFrame] | None = None,
    confirm_bars: int = 2,
    max_idle_bars: int = 288,
    price_decimals: int = 5,
    require_htf_alignment: bool = True,
) -> list[ToolEvent]:
    """Anota cada BOS con thesis_valid / thesis_reason / is_unique / idle_bars.

    Parámetros
    ----------
    df : DataFrame M5 (o el TF del evento) con columnas close, time (opcional).
    events : lista de ToolEvent emitidos por BOSTool.
    htf_frames : dict opcional {'D1': df, 'H4': df, 'H1': df}.
                 Cada df debería tener 'trend_int' o 'trend' (ver detectors.trend).
    confirm_bars : velas consecutivas de cierre más allá del nivel (default 2).
    max_idle_bars : si > 0, marca dormido cuando (len(df)-1 - break_bar) > N.
                    0 = desactivado.
    price_decimals : redondeo para fusión de niveles.
    require_htf_alignment : si True, exige que la dirección del BOS coincida
                            con el sesgo HTF (o que HTF sea neutral).

    Returns
    -------
    La misma lista de eventos, mutada in-place con campos en .extra y
    (opcionalmente) status actualizado.
    """
    if not events:
        return events

    n = len(df)
    end_bar = n - 1

    # ------------------------------------------------------------------
    # 1. Anotar cada evento individualmente (geométrico + confirm + HTF + idle)
    # ------------------------------------------------------------------
    for ev in events:
        if not (ev.signal or "").startswith(("BOS_", "CHOCH_")):
            continue

        direction = 1 if ev.signal == "BOS_UP" else -1
        level = float(ev.price) if ev.price is not None else None
        b = ev.break_bar if ev.break_bar is not None else ev.bar_index

        reasons_ok: list[str] = []
        reasons_fail: list[str] = []

        # (0) Precondición geométrica: debe seguir vivo
        #     (el llamador puede haber puesto status="invalidated" ya)
        if getattr(ev, "status", "") == "invalidated":
            ev.extra["thesis_valid"] = False
            ev.extra["thesis_reason"] = "FALLO: invalidado geométricamente (precio cruzó el nivel en contra)"
            ev.extra["is_unique"] = False
            ev.extra["idle_bars"] = end_bar - b if b is not None else None
            ev.extra["htf_aligned"] = None
            continue

        # (1) confirm_bars: N cierres consecutivos más allá del nivel
        if level is not None and b is not None and confirm_bars > 0:
            ok_confirm = True
            if b + confirm_bars - 1 >= n:
                ok_confirm = False
                reasons_fail.append(f"FALLO: no hay {confirm_bars} velas posteriores para confirmar")
            else:
                for k in range(confirm_bars):
                    c = float(df["close"].iloc[b + k])
                    if direction == 1 and c <= level:
                        ok_confirm = False
                        break
                    if direction == -1 and c >= level:
                        ok_confirm = False
                        break
                if ok_confirm:
                    reasons_ok.append(f"OK: confirm_bars={confirm_bars}")
                else:
                    reasons_fail.append(f"FALLO: no hay {confirm_bars} cierres consecutivos más allá del nivel")
        else:
            reasons_ok.append("OK: confirm_bars no aplicable / desactivado")

        # (2) Alineación con sesgo HTF
        htf_bias = _aggregate_htf_bias(htf_frames, ev.time)
        htf_aligned: bool | None
        if htf_frames is None or not htf_frames:
            htf_aligned = None
            reasons_ok.append("OK: sin HTF frames (alineación no evaluada)")
        else:
            if htf_bias == 0:
                htf_aligned = True  # neutral no bloquea
                reasons_ok.append("OK: HTF neutral → no bloquea")
            elif htf_bias == direction:
                htf_aligned = True
                reasons_ok.append(f"OK: alineado con HTF bias={htf_bias}")
            else:
                htf_aligned = False
                if require_htf_alignment:
                    reasons_fail.append(f"FALLO: BOS dir={direction} contra HTF bias={htf_bias}")
                else:
                    reasons_ok.append(f"INFO: contra HTF bias={htf_bias} (require_htf_alignment=False)")

        # (3) Dormido (decisión de ingeniería)
        idle = (end_bar - b) if b is not None else None
        if max_idle_bars > 0 and idle is not None and idle > max_idle_bars:
            reasons_fail.append(f"FALLO: dormido ({idle} barras > max_idle_bars={max_idle_bars})")
        elif idle is not None:
            reasons_ok.append(f"OK: idle_bars={idle} <= {max_idle_bars}")

        # Decisión final individual (antes de fusión)
        thesis_valid = len(reasons_fail) == 0
        reason = " | ".join(reasons_ok + reasons_fail) if (reasons_ok or reasons_fail) else "sin evaluación"

        ev.extra["thesis_valid"] = thesis_valid
        ev.extra["thesis_reason"] = reason
        ev.extra["idle_bars"] = idle
        ev.extra["htf_aligned"] = htf_aligned
        ev.extra["htf_bias"] = htf_bias
        ev.extra["is_unique"] = False  # se resuelve en el paso de fusión

    # ------------------------------------------------------------------
    # 2. Fusión de niveles: (direction, price redondeado) → un solo representante
    #    Solo entre los que pasaron thesis_valid=True.
    #    Criterio de representante: el de menor break_bar (el primero).
    # ------------------------------------------------------------------
    groups: dict[tuple[int, float], list[ToolEvent]] = defaultdict(list)

    for ev in events:
        if not (ev.signal or "").startswith(("BOS_", "CHOCH_")):
            continue
        if not ev.extra.get("thesis_valid", False):
            continue
        direction = 1 if ev.signal == "BOS_UP" else -1
        if ev.price is None:
            continue
        key = (direction, round(float(ev.price), price_decimals))
        groups[key].append(ev)

    for key, group in groups.items():
        # Ordenar por break_bar ascendente
        group_sorted = sorted(
            group,
            key=lambda e: (e.break_bar if e.break_bar is not None else e.bar_index),
        )
        winner = group_sorted[0]
        winner.extra["is_unique"] = True
        winner.extra["fusion_count"] = len(group_sorted)
        winner.extra["thesis_reason"] += f" | OK: representante de nivel (fusionados={len(group_sorted)})"

        for loser in group_sorted[1:]:
            loser.extra["is_unique"] = False
            loser.extra["thesis_valid"] = False
            loser.extra["thesis_reason"] += (
                f" | FALLO: fusionado (mismo nivel que {winner.id}, "
                f"se conserva solo el primero)"
            )

    return events


def summarize_bos_filter(events: list[ToolEvent]) -> dict:
    """Resumen rápido para logs y bitácoras (BOS y CHOCH)."""
    bos = [e for e in events if (e.signal or "").startswith(("BOS_", "CHOCH_"))]
    total = len(bos)
    active_geo = sum(1 for e in bos if getattr(e, "status", "") != "invalidated")
    thesis_valid = sum(1 for e in bos if e.extra.get("thesis_valid") is True)
    unique = sum(1 for e in bos if e.extra.get("is_unique") is True)
    up_unique = sum(1 for e in bos if e.extra.get("is_unique") and e.signal.endswith("UP"))
    dn_unique = sum(1 for e in bos if e.extra.get("is_unique") and e.signal.endswith("DOWN"))

    return {
        "total": total,
        "geometric_active": active_geo,
        "thesis_valid": thesis_valid,
        "unique_setups": unique,
        "unique_up": up_unique,
        "unique_down": dn_unique,
    }
