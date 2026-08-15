"""Breaker Block / MMXM detector (libro 22 / SPEC A4).

Breaker Block = OB previo que FALLO (cierran por el lado opuesto) y tras el
cambio de estructura (CHoCH/MSS) cambia de rol:

  - bearish OB rota desde arriba  -> Bullish Breaker (soporte).
  - bullish OB rota desde abajo   -> Bearish Breaker (resistencia).

MMXM = mitiga la zona del breaker solo una vez; tras la primera mitigación,
el breaker queda invalidado y no se reutiliza.

CONTRATO (no toca canonical.py/engine.py, sin ATR ni indicadores):
  - is_breaker_block(df, current_idx, fvgs, obs) -> dict con:
        breaker_active : bool
        breaker_type   : 'bullish' | 'bearish' | None
        mitigation_level : float | None
        strength       : float  (0..1)
  - flag_breaker_block(signals, frames, ltf='M15') anota ICTSignal sin tocar engine.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Helpers puros sobre Series/arrays
# ---------------------------------------------------------------------------
def _last_valid(series: pd.Series) -> float | None:
    non_null = series.dropna()
    return float(non_null.iloc[-1]) if len(non_null) else None


def _range_size(top: float, bottom: float) -> float:
    r = float(top) - float(bottom)
    return r if r > 0 else 1e-9


def _normalize_strength(
    bars_since: int,
    zone_range: float,
    avg_range: float,
    *,
    max_bars: int = 80,
) -> float:
    recency = 1.0 - min(float(bars_since) / float(max_bars), 1.0)
    size_ratio = min(float(zone_range) / float(avg_range), 1.0) if avg_range > 0 else 0.5
    strength = np.sqrt(recency * size_ratio)
    return float(np.clip(strength, 0.0, 1.0))


# ---------------------------------------------------------------------------
# Detección principal
# ---------------------------------------------------------------------------
def is_breaker_block(
    df: pd.DataFrame,
    current_idx: int,
    fvgs: list,
    obs: list,
) -> dict:
    """Detecta si en ``current_idx`` hay un Breaker Block activo.

    Estrategia (sin ATR ni indicadores):
      1. Revisa los ``obs`` entregados (trozos candidatos a breaker).
         Cada elemento de ``obs`` debe ser un dict con al menos:
         - ``type`` : 'bullish' | 'bearish'
         - ``top``  : float | None
         - ``bottom``: float | None
         - ``start_idx`` : int | None
         - ``end_idx``   : int | None
      2. Clasifica cada OB como candidato:
         - bearish OB + close[actual] > top  -> bullish breaker candidato.
         - bullish OB + close[actual] < bottom -> bearish breaker candidato.
      3. Confirma post-BOS: la barra actual cae al menos una barra después del
         OB (end_idx < current_idx). Esto evita falsos positivos en formación.
      4. MMXM: solo permite UNA mitigación por breaker. Después de la primera
         mitigación invalida el breaker para siempre.
      5. Calcula ``strength`` normalizada y ``mitigation_level``.

    Args:
        df: Frame LTF con columnas OHLC + ``ob_*`` y ``fvg_*`` (reset_index).
        current_idx: Índice de barra actual.
        fvgs: lista de dicts FVG detectados.
        obs: lista de dicts OB candidatos.

    Returns:
        dict con:
            breaker_active   : bool
            breaker_type     : 'bullish' | 'bearish' | None
            mitigation_level : float | None
            strength         : float
    """
    if df is None or len(df) == 0:
        return _empty_result()

    if current_idx < 0 or current_idx >= len(df):
        return _empty_result()

    row = df.iloc[current_idx]
    close = float(row["close"])

    # Rango promedio de la ventana para normalizar strength.
    recent = df.iloc[max(0, current_idx - 50): current_idx + 1]
    avg_range = float((recent["high"] - recent["low"]).mean()) if len(recent) else 0.0

    # ------------------------------------------------------------------
    # Buscar OB rotos -> breaker candidatos
    # ------------------------------------------------------------------
    bullish_breaker = None
    bearish_breaker = None

    for ob in obs or []:
        ob_type = str(ob.get("type") or "").lower()
        top = ob.get("top")
        bottom = ob.get("bottom")
        if top is None or bottom is None:
            continue
        try:
            top = float(top)
            bottom = float(bottom)
            end_idx = int(ob.get("end_idx") or -1)
        except (TypeError, ValueError):
            continue

        if ob_type == "bearish" and close > top:
            bullish_breaker = {
                "type": "bullish",
                "mitigation_level": top,
                "ob_top": top,
                "ob_bottom": bottom,
                "end_idx": end_idx,
                "zone_range": _range_size(top, bottom),
                "bars_since": max(0, current_idx - end_idx) if end_idx >= 0 else 0,
            }
            break

        if ob_type == "bullish" and close < bottom:
            bearish_breaker = {
                "type": "bearish",
                "mitigation_level": bottom,
                "ob_top": top,
                "ob_bottom": bottom,
                "end_idx": end_idx,
                "zone_range": _range_size(top, bottom),
                "bars_since": max(0, current_idx - end_idx) if end_idx >= 0 else 0,
            }
            break

    # Elegimos el primer breaker activo válido.
    active = bullish_breaker or bearish_breaker
    if active is None:
        return _empty_result()

    # El OB debe existir y estar al menos una barra antes de current_idx.
    start_idx = int(active.get("start_idx") or -1)
    if start_idx < 0 or start_idx >= current_idx:
        return _empty_result()

    # MMXM: si el breaker ya fue marcado como mitigado/manejado, no queda activo.
    if active.get("start_idx") == -2:
        return _empty_result()

    # Mitigación real: desde la barra siguiente a current_idx, si el precio
    # vuelve a entrar en la zona del breaker queda invalidado (MMXM = 1 toque).
    if _was_mitigated(df, current_idx, active):
        return _empty_result()

    strength = _normalize_strength(
        current_idx - start_idx,
        active["zone_range"],
        avg_range,
    )

    return {
        "breaker_active": True,
        "breaker_type": active["type"],
        "mitigation_level": active["mitigation_level"],
        "strength": strength,
    }


def _was_mitigated(df: pd.DataFrame, current_idx: int, breaker: dict) -> bool:
    """Comprueba si TRAS la barra ``current_idx`` el precio volvió a entrar en
    la zona del breaker (primer toque = mitigación MMXM).
    """
    start = current_idx + 1
    if start >= len(df):
        return False
    sub = df.iloc[start:]
    if len(sub) == 0:
        return False

    top = float(breaker["ob_top"])
    bottom = float(breaker["ob_bottom"])
    low = sub["low"].to_numpy(dtype=float)
    high = sub["high"].to_numpy(dtype=float)

    # Mitigación: el precio entra dentro del rango del breaker.
    # Para bullish breaker: price retests from above (high drops into zone)
    # Para bearish breaker: price retests from below (low rises into zone)
    if breaker["type"] == "bullish":
        return bool(np.any(low <= top))
    return bool(np.any(high >= bottom))


def _empty_result() -> dict:
    return {
        "breaker_active": False,
        "breaker_type": None,
        "mitigation_level": None,
        "strength": 0.0,
    }


# ---------------------------------------------------------------------------
# Helpers para armar ``obs`` desde el frame si el caller no lo provee.
# ---------------------------------------------------------------------------
def _ob_dicts_from_frame(df: pd.DataFrame) -> list:
    """Extrae dicts de OB desde columnas ``ob_bullish`` / ``ob_bearish``."""
    records = []
    bull = df["ob_bullish"].to_numpy(bool) if "ob_bullish" in df.columns else np.zeros(len(df), dtype=bool)
    bear = df["ob_bearish"].to_numpy(bool) if "ob_bearish" in df.columns else np.zeros(len(df), dtype=bool)
    ob_top = df["ob_top"].to_numpy() if "ob_top" in df.columns else np.full(len(df), np.nan)
    ob_bottom = df["ob_bottom"].to_numpy() if "ob_bottom" in df.columns else np.full(len(df), np.nan)

    for i in range(len(df)):
        if bull[i] or bear[i]:
            records.append({
                "type": "bullish" if bull[i] else "bearish",
                "top": float(ob_top[i]) if not np.isnan(ob_top[i]) else None,
                "bottom": float(ob_bottom[i]) if not np.isnan(ob_bottom[i]) else None,
                "start_idx": i,
                "end_idx": i,
            })
    return records


# ---------------------------------------------------------------------------
# Flag helper (anota ICTSignal sin tocar engine.py)
# ---------------------------------------------------------------------------
def flag_breaker_block(signals, frames, ltf: str = "M15") -> list:
    """Anota ``breaker_active`` / ``breaker_type`` / ``mitigation_level`` /
    ``breaker_strength`` en cada seña sin editar ``engine.py``.

    Call-site: se usa DESPUÉS de ``evaluate_signals``, igual que los flags
    de setups C2/C3.  Principio Brecha D: solo anota; no veta.

    Args:
        signals: lista de señales (ICTSignal u objetos planos).
        frames: dict de DataFrames por TF (debe contener ``ltf``).
        ltf: timeframe de ejecución.

    Returns:
        La misma lista recibida (anotada in-place).
    """
    if not signals:
        return list(signals)
    ltf_df = frames.get(ltf) if isinstance(frames, dict) else None
    if ltf_df is None:
        return list(signals)

    ltf_df = ltf_df.reset_index(drop=True)
    obs = _ob_dicts_from_frame(ltf_df)
    fvgs = _fvgs_from_frame(ltf_df) if "fvg_bullish" in ltf_df.columns else []

    for sig in signals:
        idx = getattr(sig, "entry_at", None) or getattr(sig, "current_idx", None)
        if idx is None:
            setattr(sig, "breaker_active", False)
            setattr(sig, "breaker_type", None)
            setattr(sig, "mitigation_level", None)
            setattr(sig, "breaker_strength", 0.0)
            continue
        try:
            idx = int(idx)
        except (TypeError, ValueError):
            idx = 0
        res = is_breaker_block(ltf_df, idx, fvgs, obs)
        setattr(sig, "breaker_active", bool(res["breaker_active"]))  # type: ignore[attr-defined]
        setattr(sig, "breaker_type", res.get("breaker_type"))  # type: ignore[attr-defined]
        setattr(sig, "mitigation_level", res.get("mitigation_level"))  # type: ignore[attr-defined]
        setattr(sig, "breaker_strength", float(res.get("strength") or 0.0))  # type: ignore[attr-defined]
    return signals


# ---------------------------------------------------------------------------
# Helpers de FVG (versión ligera, sin dependencias)
# ---------------------------------------------------------------------------
def _fvgs_from_frame(df: pd.DataFrame) -> list:
    """Extrae dicts de FVG válidos desde el frame."""
    records = []
    if "fvg_bullish" not in df.columns or "fvg_bearish" not in df.columns:
        return records
    fb = df["fvg_bullish"].to_numpy(bool)
    fg = df["fvg_bearish"].to_numpy(bool)
    prev2_high = df["high"].shift(2).to_numpy()
    prev2_low = df["low"].shift(2).to_numpy()
    low = df["low"].to_numpy()
    high = df["high"].to_numpy()
    for i in range(2, len(df)):
        if fb[i]:
            records.append({
                "type": "bullish",
                "top": float(prev2_high[i]),
                "bottom": float(low[i]),
                "idx": i,
            })
        elif fg[i]:
            records.append({
                "type": "bearish",
                "top": float(high[i]),
                "bottom": float(prev2_low[i]),
                "idx": i,
            })
    return records
