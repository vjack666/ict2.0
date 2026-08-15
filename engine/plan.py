"""engine/plan.py — Lectura TOP-DOWN del trader humano (PERMANENTE).

Esto es la lectura del grafico del humano hecha codigo:
  D1 (sesgo) -> H4 (zona) -> H1 (contexto) -> M15 (entrada)
  -> M5 (ejecucion fina / momentum) -> M1 (microestructura)
con premium/discount y POI anclado. M5/M1 solo CONFIRMAN a favor: nunca
redefinen ni vetan el sesgo mayor (tesis §5).

Es la FUENTE de verdad de la estrategia. Vive en el motor (permanente) y el
backtest (ict_backtest/v2) la CONSUME para demostrar la tesis. El observador
en vivo la importa directo de aqui. NUNCA importa ict_backtest/ (Ley).

Anti look-ahead: cada TF superior se consulta CLOSED-ONLY al tiempo t de la
vela LTF (no se mezclan relojes). El trend por TF sale de
engine.bos.detect_market_structure (mismo motor de estructura del resto).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from engine.bos import detect_market_structure, StructureConfig


# --------------------------------------------------------------------------- #
# helpers de tiempo (anti look-ahead por timestamp)
# --------------------------------------------------------------------------- #
def _closed_row_at_time(df: pd.DataFrame, t: Any):
    """Fila de df ya CERRADA al tiempo t (time <= t). None si no hay."""
    if df is None or len(df) == 0 or "time" not in df.columns:
        return None
    times = pd.to_datetime(df["time"], utc=True, errors="coerce")
    tt = pd.to_datetime(t, utc=True, errors="coerce")
    if pd.isna(tt):
        return None
    mask = times <= tt
    if not mask.any():
        return None
    return df.loc[mask].iloc[-1]


def _trend_of(row: pd.Series | None) -> str:
    if row is None or (isinstance(row, float) and np.isnan(row)):
        return "RANGING"
    try:
        t = str(row.get("trend", row.get("macro_direction", "RANGING")))
    except Exception:
        return "RANGING"
    if t in ("BULLISH", "BEARISH"):
        return t
    return "RANGING"


def _bos_real_behind(sub, i, choch_dir, choch_proj_level, tol: float = 0.0005) -> bool:
    """T9.7 (tesis S7.0, extension de T9.5): un CHOCH solo cuenta si el BOS
    contrario que rompio era REAL (bos_real). Busca en velas anteriores un BOS
    de direccion opuesta, bos_real=True, con bos_level ~ choch_proj_level.
    Sin bos_real en el frame -> True (regresion cero)."""
    if "bos_real" not in sub.columns:
        return True
    opp = -int(choch_dir)
    cand = sub[(sub.index < i) & (sub["bos_dir"] == opp) & (sub["bos_real"] == True)]
    hit = cand[np.abs(cand["bos_level"] - choch_proj_level) <= tol]
    return len(hit) > 0


def _bias_from_frame(df: pd.DataFrame, t: Any) -> str:
    """Sesgo por estructura del TF completo cerrado hasta t (T9.1/T9.3).

    Escanea el frame anotado (bos_dir/bos_status/choch_dir/choch_status) y
    devuelve la direccion del ULTIMO evento activo: CHOCH activo manda sobre
    BOS activo; sin ninguno => RANGING. No lee la ultima fila (que puede no
    ser evento), sino el maximo indice con evento active. Unica fuente de
    sesgo por estructura, reusada por snapshot_tf y ltf_structure_at.
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
    # Feed sin anotar (sin bos_dir/bos_status): cae a la etiqueta de swing
    # para no romper frames sinteticos/feeds externos (regresion cero).
    if "bos_dir" not in sub.columns or "bos_status" not in sub.columns:
        return _trend_of(sub.iloc[-1])
    # T9.5 (tesis §3/§7.0): el sesgo HTF solo cuenta BOS REALES (bos_real),
    # o sea BOS con displacement (empujon decidido) sobre swing confirmado.
    # Un BOS sin displacement es ruido de rotura tibia que el humano no cuenta.
    # Si el frame no trae bos_real (feed externo), se acepta cualquier BOS
    # (regresion cero).
    has_real = "bos_real" in sub.columns
    last_bos_idx = last_bos_dir = 0
    last_choch_idx = last_choch_dir = 0
    for i in range(len(sub)):
        bd = sub["bos_dir"].iloc[i]
        if (
            bd not in (0, "0", None)
            and str(sub["bos_status"].iloc[i]) == "active"
            and (not has_real or bool(sub["bos_real"].iloc[i]))
        ):
            last_bos_idx, last_bos_dir = i, int(bd)
        cd = sub["choch_dir"].iloc[i]
        if cd not in (0, "0", None) and str(sub["choch_status"].iloc[i]) == "active":
            # T9.7 (tesis S7.0, extension T9.5): el CHOCH solo cuenta si el BOS
            # contrario que rompio era REAL (bos_real). Un CHOCH sobre BOS de
            # ruido es un giro falso que el humano ignora -> no manda sesgo.
            if has_real and not _bos_real_behind(
                sub, i, int(cd), float(sub["choch_proj_level"].iloc[i])
            ):
                continue
            last_choch_idx, last_choch_dir = i, int(cd)
    if last_choch_dir != 0:
        return "BULLISH" if last_choch_dir > 0 else "BEARISH"
    if last_bos_dir != 0:
        return "BULLISH" if last_bos_dir > 0 else "BEARISH"
    return "RANGING"


# --------------------------------------------------------------------------- #
# snapshots cerrados por TF (closed-only al tiempo t)
# --------------------------------------------------------------------------- #
def snapshot_tf(ms: dict[str, pd.DataFrame], tf: str, t: Any,
                closed_idx: int | None = None) -> dict[str, Any]:
    """Snapshot closed-only de un TF al tiempo t de la vela LTF.

    Opción 3 (2026-08-14, Change Gate autorizado por Director): si se pasa
    `closed_idx` (índice precomputado de la última vela HTF cerrada <= t),
    se usa `df.iloc[closed_idx]` en vez de `_closed_row_at_time(df, t)`. El
    procesamiento de la fila (_bias_from_frame, extracción de campos) es
    IDÉNTICO al camino original. La optimización SOLO evita el re-cálculo del
    índice (O(n) ciego por vela -> O(1) lookup); NO sustituye el contexto
    procesado por un dict de fila cruda (invariante 5 del Change Gate).
    """
    df = ms.get(tf)
    if df is None or len(df) == 0:
        return {"tf": tf, "available": False, "trend": "RANGING"}
    if tf in ("M1", "M5", "M15"):
        # LTF/exec: ultima barra con time <= t (esa barra ya cerro en el loop)
        times = pd.to_datetime(df["time"], utc=True, errors="coerce")
        tt = pd.to_datetime(t, utc=True, errors="coerce")
        prior = df.index[times <= tt]
        if len(prior) == 0:
            return {"tf": tf, "available": False, "trend": "RANGING"}
        row = df.iloc[int(prior[-1])]
    else:
        if closed_idx is not None and 0 <= closed_idx < len(df):
            row = df.iloc[int(closed_idx)]
        else:
            row = _closed_row_at_time(df, t)
    if row is None:
        return {"tf": tf, "available": False, "trend": "RANGING"}
    fvg_state = str(row.get("fvg_state", "NONE") or "NONE")
    ob_dir = str(row.get("ob_direction", row.get("ob_dir", "-")) or "-")
    return {
        "tf": tf,
        "available": True,
        "trend": _bias_from_frame(df, t),
        "close": float(row.get("close", np.nan) or np.nan),
        "high": float(row.get("high", np.nan) or np.nan),
        "low": float(row.get("low", np.nan) or np.nan),
        "sweep_up": bool(row.get("liquidity_sweep_up", False)),
        "sweep_down": bool(row.get("liquidity_sweep_down", False)),
        "bos_dir": int(row.get("bos_dir", row.get("bos_direction", 0)) or 0)
        if not isinstance(row.get("bos_direction", 0), str)
        else (1 if str(row.get("bos_direction")) == "BULLISH" else -1 if str(row.get("bos_direction")) == "BEARISH" else 0),
        "choch": str(row.get("choch_signal", row.get("choch_status", ""))),
        "fvg_state": fvg_state,
        "ob_dir": ob_dir,
        "time": str(row.get("time", t)),
    }


def dealing_range_pd(d1: pd.DataFrame, t: Any, lookback: int = 20,
                     closed_idx: int | None = None) -> dict[str, Any]:
    """Premium/Discount del TF (D1/H4) usando las ultimas N velas cerradas.

    Opción 3 (2026-08-14, Change Gate): si se pasa ``closed_idx`` (índice
    precomputado de la última vela D1 cerrada <= t), usa ``d1.iloc[closed_idx]``
    en vez de ``_closed_row_at_time(d1, t)``. El resto del cálculo (ventana
    lookback, eq, range) es IDÉNTICO. Solo evita el re-cálculo O(n) del índice.
    """
    if closed_idx is not None and 0 <= closed_idx < len(d1):
        row = d1.iloc[int(closed_idx)]
    else:
        row = _closed_row_at_time(d1, t)
    if row is None or len(d1) < 5:
        return {"pd_side": "UNKNOWN", "eq": np.nan, "range_high": np.nan, "range_low": np.nan}
    tt = pd.to_datetime(row["time"], utc=True, errors="coerce")
    times = pd.to_datetime(d1["time"], utc=True, errors="coerce")
    mask = times <= tt
    win = d1.loc[mask].tail(lookback)
    if len(win) < 3:
        return {"pd_side": "UNKNOWN", "eq": np.nan, "range_high": np.nan, "range_low": np.nan}
    rh = float(win["high"].max())
    rl = float(win["low"].min())
    eq = 0.5 * (rh + rl)
    px = float(row["close"])
    if px < eq:
        side = "DISCOUNT"
    elif px > eq:
        side = "PREMIUM"
    else:
        side = "EQ"
    return {"pd_side": side, "eq": eq, "range_high": rh, "range_low": rl, "close": px}


# --------------------------------------------------------------------------- #
# capas LTF (M5 / M1): ejecucion fina y microestructura
#
# Tesis (docs/tesis/HALLAZGOS_ESTRUCTURA_BOS_CHOCH.md, §5): la lectura humana es
# D1 -> H4 -> H1 -> M15 -> M5 -> M1. M5 refina la entrada dentro de la zona M15
# (confirmacion de momentum) y M1 es microestructura. NINGUNO redefine el sesgo
# mayor: solo pueden CONFIRMAR a favor, jamas vetar contra D1/H4/H1.
# --------------------------------------------------------------------------- #
LTF_TFS: tuple[str, ...] = ("M5", "M1")


def ltf_structure_at(
    ms: dict[str, pd.DataFrame],
    tf: str,
    t: Any,
    *,
    lookback: int = 120,
    exp012: bool = False,
) -> dict[str, Any]:
    """Estructura fina closed-only de un TF de ejecucion (M5/M1) al tiempo t.

    Reusa engine.bos.detect_market_structure (que a su vez usa los swings
    canonicos de engine.bias.narrative._swing_points). NO duplica deteccion.

    Anti look-ahead: se recorta el frame a las velas con ``time <= t`` ANTES de
    correr la deteccion, por lo que ninguna vela futura entra al calculo.
    """
    out: dict[str, Any] = {
        "tf": tf,
        "available": False,
        "trend": "RANGING",
        "bos_dir": 0,
        "momentum": 0,
        "bars": 0,
    }
    df = ms.get(tf)
    if df is None or len(df) == 0 or "time" not in df.columns:
        return out
    times = pd.to_datetime(df["time"], utc=True, errors="coerce")
    tt = pd.to_datetime(t, utc=True, errors="coerce")
    if pd.isna(tt):
        return out
    win = df.loc[times <= tt]
    if len(win) == 0:
        return out
    win = win.tail(int(max(lookback, 5))).reset_index(drop=True)
    out["bars"] = int(len(win))
    out["available"] = True
    out["time"] = str(win["time"].iloc[-1])

    trend = "RANGING"
    bos_dir = 0
    if {"high", "low", "open", "close"}.issubset(win.columns) and len(win) >= 5:
        try:
            ms_res = detect_market_structure(
                win, StructureConfig(exp012_choch=exp012)
            )
            fr = ms_res.frame
            last = fr.iloc[-1]
            trend = _bias_from_frame(win, win["time"].iloc[-1])
            bos_dir = int(last.get("bos_dir", 0) or 0)
            # EXP-012 (bonus de autoridad, NO veta el sesgo canonico): cuantos
            # CHOCH en la ventana cumplen la regla del humano (empuje >=2 HH/LL).
            if exp012 and "choch_exp012" in fr.columns:
                out["choch_exp012_count"] = int(fr["choch_exp012"].sum())
                out["choch_exp012_last_level"] = (
                    float(fr.loc[fr["choch_exp012"] == 1, "choch_pivot_level"].iloc[-1])
                    if (fr["choch_exp012"] == 1).any() else None
                )
        except Exception:
            trend = _trend_of(win.iloc[-1])
    else:
        trend = _trend_of(win.iloc[-1])

    # Fallback: si el frame ya trae 'trend' precomputado y la deteccion no
    # resolvio nada, respeta la columna (frames sinteticos / feeds anotados).
    if trend == "RANGING":
        col_trend = _trend_of(win.iloc[-1])
        if col_trend != "RANGING":
            trend = col_trend

    out["trend"] = trend
    out["bos_dir"] = bos_dir

    # Momentum fino: desplazamiento neto de cierres en la ventana corta.
    try:
        tail = win["close"].astype(float).tail(min(6, len(win)))
        delta = float(tail.iloc[-1]) - float(tail.iloc[0])
        out["momentum"] = 1 if delta > 0 else (-1 if delta < 0 else 0)
        out["momentum_delta"] = delta
    except Exception:
        out["momentum"] = 0
    return out


def ltf_confirms(stack: dict[str, Any], direction: int) -> dict[str, Any]:
    """¿M5/M1 estan A FAVOR de ``direction``? Solo confirma; nunca veta.

    Devuelve dict con ``confirmed`` (bool), ``score`` y detalle por TF. Un TF
    ausente/no disponible es NEUTRO (regresion cero: si M5/M1 no estan en ms,
    el resultado es 'no confirmado' pero jamas un bloqueo).
    """
    if direction == 0:
        return {"confirmed": False, "score": 0, "detail": {}, "available": False}
    detail: dict[str, Any] = {}
    score = 0
    any_available = False
    for tf in LTF_TFS:
        snap = stack.get(tf) or {}
        if not snap.get("available"):
            detail[tf] = "unavailable"
            continue
        any_available = True
        trend = snap.get("trend", "RANGING")
        want = "BULLISH" if direction > 0 else "BEARISH"
        opp = "BEARISH" if direction > 0 else "BULLISH"
        bos = int(snap.get("bos_dir", 0) or 0)
        mom = int(snap.get("momentum", 0) or 0)
        if trend == want or bos == direction or (trend != opp and mom == direction):
            detail[tf] = "with"
            score += 1
        elif trend == opp or bos == -direction:
            detail[tf] = "against"
            score -= 1
        else:
            detail[tf] = "neutral"
    return {
        "confirmed": score > 0,
        "score": score,
        "detail": detail,
        "available": any_available,
    }


def build_context_stack(
    ms: dict[str, pd.DataFrame],
    t: Any,
    *,
    tfs: tuple[str, ...] = ("D1", "H4", "H1", "M15"),
    anchored_pd_zones: dict[str, Any] | None = None,
    closed_index: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Stack top-down de snapshots closed-only al tiempo t.

    Inyecta premium/discount (pd_side) en D1/H4 y POI anclado (H4/H1) si se
    pasa ``anchored_pd_zones``. No mezcla relojes: una t, muchos lookups cerrados.

    Opción 3 (2026-08-14, Change Gate): ``closed_index`` es un dict
    ``{tf: int}`` con el índice precomputado de la última vela HTF cerrada <= t
    (calculado UNA vez por el llamador, O(n) total). Si se pasa, ``snapshot_tf``
    usa ``df.iloc[idx]`` en vez de ``_closed_row_at_time`` (O(1) lookup). El
    procesamiento de la fila es IDÉNTICO. Si no se pasa, comportamiento original
    (retrocompatible, O(n) ciego por vela dentro de ``_closed_row_at_time``).
    """
    _ci = closed_index or {}
    stack = {tf: snapshot_tf(ms, tf, t, closed_idx=_ci.get(tf)) for tf in tfs if tf in ms or tf in tfs}
    for tf in tfs:
        stack.setdefault(tf, {"tf": tf, "available": False, "trend": "RANGING"})
    # Capas de ejecucion fina: si el caller pide M5/M1, se enriquecen con la
    # estructura closed-only del motor (no redefinen el sesgo mayor).
    for tf in LTF_TFS:
        if tf in tfs:
            fine = ltf_structure_at(ms, tf, t)
            base = dict(stack.get(tf) or {})
            if fine.get("available"):
                base.update(
                    {
                        "available": True,
                        "trend": fine["trend"],
                        "bos_dir": fine.get("bos_dir", 0),
                        "momentum": fine.get("momentum", 0),
                        "momentum_delta": fine.get("momentum_delta"),
                        "bars": fine.get("bars", 0),
                    }
                )
            stack[tf] = base
    for tf in ("D1", "H4"):
        df = ms.get(tf)
        if df is not None:
            _ci_tf = _ci.get(tf)
            dr = dealing_range_pd(df, t, closed_idx=_ci_tf)
            stack[tf]["pd_side"] = dr.get("pd_side", "UNKNOWN")
    # Clave 'dealing' consolidada para el gate/logs/explanations
    # (lee pd_side de H4 primero, luego D1). Sin esto, top_down_allows_trade
    # veia dealing={} -> pd_unknown sistematico.
    _pd = stack.get("H4", {}).get("pd_side") or stack.get("D1", {}).get("pd_side")
    stack["dealing"] = {"pd_side": _pd if _pd else "UNKNOWN"}
    if anchored_pd_zones:
        for tf, zones in anchored_pd_zones.items():
            if tf in stack and zones:
                stack[tf]["pd_side"] = "PD"
                stack[tf]["poi_count"] = len(zones)
    return stack


def top_down_allows_trade(
    stack: dict[str, Any],
    direction: int,
    *,
    require_d1: bool = True,
    require_h4: bool = True,
    require_h1: bool = True,
    require_pd: bool = True,
    counter_trend: bool = False,
    require_ltf: bool = False,
) -> tuple[bool, str]:
    """Gate del humano: D1 -> H4 -> H1 -> PD (-> M5/M1 opcional).

    ``require_ltf`` activa la CONFIRMACION de las capas finas M5/M1. Segun la
    tesis, M5/M1 NO redefinen el sesgo mayor: por eso solo pueden pedir
    confirmacion a favor y NUNCA vetan una direccion validada por D1/H4/H1
    cuando estan ausentes/neutros. Con ``require_ltf=False`` (default) el
    comportamiento es identico al previo -> regresion cero.
    """
    d1 = stack.get("D1", {})
    h4 = stack.get("H4", {})
    h1 = stack.get("H1", {})
    dealing = stack.get("dealing", {})

    if require_d1:
        if not d1.get("available"):
            return False, "d1_unavailable"
        if d1.get("trend") == "RANGING":
            return False, "d1_ranging"
        if not counter_trend:
            if direction > 0 and d1.get("trend") != "BULLISH":
                return False, "d1_against_long"
            if direction < 0 and d1.get("trend") != "BEARISH":
                return False, "d1_against_short"
        else:
            if direction > 0 and d1.get("trend") != "BEARISH":
                return False, "d1_ct_needs_bearish"
            if direction < 0 and d1.get("trend") != "BULLISH":
                return False, "d1_ct_needs_bullish"

    if require_h4:
        if not h4.get("available"):
            return False, "h4_unavailable"
        if h4.get("trend") == "RANGING":
            return False, "h4_ranging"
        if not counter_trend:
            if direction > 0 and h4.get("trend") != "BULLISH":
                return False, "h4_against_long"
            if direction < 0 and h4.get("trend") != "BEARISH":
                return False, "h4_against_short"

    if require_h1 and "H1" in stack:
        if not h1.get("available"):
            return False, "h1_unavailable"
        if not counter_trend:
            if direction > 0 and h1.get("trend") == "BEARISH":
                return False, "h1_opposes_long"
            if direction < 0 and h1.get("trend") == "BULLISH":
                return False, "h1_opposes_short"

    if require_pd:
        side = dealing.get("pd_side", "UNKNOWN")
        if side == "UNKNOWN":
            return False, "pd_unknown"
        if direction > 0 and side == "PREMIUM":
            return False, "long_in_premium"
        if direction < 0 and side == "DISCOUNT":
            return False, "short_in_discount"

    if require_ltf:
        conf = ltf_confirms(stack, direction)
        # Solo se exige confirmacion si HAY datos LTF. Sin M5/M1 en ms, la
        # decision del sesgo mayor manda (M5/M1 no redefinen sesgo).
        if conf.get("available") and not conf.get("confirmed"):
            return False, "ltf_not_confirming"

    return True, "ok"
