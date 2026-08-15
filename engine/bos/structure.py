"""engine/bos/structure.py — Market Structure BOS / CHOCH + BOS quality score.

Contrato (docs/ict/02_MSS_CHOCH.md §0 — MSS, CHoCH y BOS, OBLIGATORIO):
  ENT: velas cerradas de un TF (high/low/open/close), sin look-ahead.
  SAL: por vela — swings etiquetados, bos_dir/bos_level/bos_status,
       bos_quality_score/bos_real, choch_dir/choch_status, trend derivado.
  BOS  = ruptura de swing A FAVOR de la tendencia, validada por cierre de
         cuerpo (close), no por mecha.
  CHoCH = ruptura del swing que produjo el ULTIMO BOS, en direccion OPUESTA
         a ese BOS (aviso de giro; no es una copia de BOS).
  MSS  = CHoCH + desplazamiento + (ideal) BOS de confirmacion en la nueva
         direccion. Secuencia canonica: BOS^ -> CHoCHv -> BOSv.
  PRE: velas cerradas (sin look-ahead): swing expuesto solo tras
       `swing_lookback` velas de confirmacion (ventana NO centrada).
  POST: estructura disponible para POI/exec (filtro HTF del setup).
  CRIT: un BOS/CHoCH es valido SOLO con `confirm_bars` cierres consecutivos
        rompiendo el nivel (LuxAlgo: 2 cuerpos; filtra fakeouts/Turtle Soups).
  BOS quality = displacement previo + fuerza del candle de break +
                distancia del close al nivel + no retorno inmediato.
  CASOS LIMITE: rango -> bos_dir=0, trend=RANGING; sin swings suficientes
        -> estados "none".
  AMBIG: swing_lookback / confirm_bars / quality_threshold son decisiones
        de ingenieria (defaults del canon: 5 / 2 / 0.45).

Reglas de implementacion:
  - Sin look-ahead: swings con ventana NO centrada + exposicion diferida
    (shift(lookback) + ffill), mismo patron que el canon y que la capa 1.
  - Confirmacion por cuerpo: close (nunca mecha) + `confirm_bars` cierres
    consecutivos.
  - Estado EVENT-DRIVEN: un BOS/CHoCH vive hasta que el close cruza de vuelta
    el nivel roto (invalidated). No caduca por tiempo ni volatilidad.
  - Sin indicadores: ni ATR ni medias moviles (volatilidad = rango high-low).
  - Primitivos de swings importados de `engine.bias.narrative` (misma logica
    en todo el motor, sin duplicar).
  - API pura, sin estado mutable global.
  - Displacement evaluado con geometria pura (cuerpo/rango, mecha/rango),
    sin indicadores externos.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from detectors.displacement import DisplacementConfig, detect_displacement
from engine._volume import volume_confirm
from engine.bias.narrative import _label_swings, _swing_points
# B4 (Ley 12 / Ley 1): etiquetado de desenlace que MIRA EL FUTURO vive solo
# aquí, en labels.py. structure.py conserva TODA la decisión con
# _consecutive_break (pasado/presente) y delega la anotación final.
from engine.labels import (
    USES_FUTURE as _LABELS_USES_FUTURE,
    confirm_score as _label_confirm_score,
    label_bos_outcome,
    label_choch_outcome,
)

BULLISH = "BULLISH"
BEARISH = "BEARISH"
RANGING = "RANGING"

_STRUCTURE_STATUS = ("none", "active", "invalidated")

# M6 — Causas de descarte emitidas por el motor.
BOS_DISCARD_REASONS = ("NO_HIT_IN_K", "INVALIDATED", "UNRESOLVED")
CHOCH_DISCARD_REASONS = ("NO_CONFIRMATION", "INVALIDATED", "UNRESOLVED")


@dataclass(frozen=True)
class StructureConfig:
    """Opciones de deteccion de estructura (defaults del canon)."""

    swing_lookback: int = 5
    followthrough_bars: int = 8
    # Cuantos cierres CONSECUTIVOS deben romper el nivel para confirmar.
    # 1 = vela unica; 2 = filtra fakeouts (LuxAlgo Market Structure, feb 2026).
    confirm_bars: int = 2
    k: int = 5
    # BOS quality score: umbral para considerar un BOS como "real" vs fakeout.
    # 0 = todo BOS confirmado es real; 1 = solo BOS con calidad maxima.
    quality_threshold: float = 0.45
    # MDS_VOLUMEN: ventana para el ratio de volumen del breakout BOS/CHOCH.
    # SOLO confirmacion (columna bos_volume_ratio), NUNCA gate.
    volume_window: int = 20
    # EXP-012 (flag experimental, caducidad documentada en bitacora 2026-08-08):
    # cuando True, GATE DURO: marca choch_exp012 y choch_pivot_level, y ADEMAS
    # sobrescribe choch_dir=0 / choch_status="none" donde el CHOCH no cumple
    # (empuje >=2 HH/LL post-tendencia, BOS real detras, nivel = ULTIMO HL/LH
    # roto). El CHOCH de ruido DEJA DE EXISTIR en el frame. Ver commit 375efc6.
    exp012_choch: bool = False


@dataclass(frozen=True)
class MarketStructure:
    """Resultado de la deteccion: frame anotado + vista de estado.

    `frame` contiene las columnas:
      swing_high, swing_low, swing_label
      bos_dir (1/-1/0), bos_level, bos_status (active/invalidated/none),
      bos_discard_reason (INVALIDATED/UNRESOLVED/NO_HIT_IN_K)
      bos_quality_score (0-1), bos_real (bool)
      choch_dir (1/-1/0), choch_status (active/invalidated/none),
      choch_discard_reason (INVALIDATED/UNRESOLVED/NO_CONFIRMATION)
      mss_dir (1/-1/0)   # secuencia canonica BOS -> CHOCH -> BOS
      trend (BULLISH/BEARISH/RANGING)
    """

    frame: pd.DataFrame

    @property
    def last_bos_dir(self) -> int:
        """Direccion del ultimo BOS emitido (1 alcista, -1 bajista, 0 sin BOS)."""
        bos = self.frame["bos_dir"]
        nonzero = bos[bos != 0]
        return int(nonzero.iloc[-1]) if len(nonzero) else 0

    @property
    def last_bos_level(self) -> float:
        """Nivel del ultimo BOS emitido (NaN si no hubo)."""
        levels = self.frame["bos_level"]
        valid = levels[~levels.isna()]
        return float(valid.iloc[-1]) if len(valid) else float("nan")

    @property
    def last_choch_dir(self) -> int:
        """Direccion del ultimo CHoCH emitido (1/-1/0)."""
        choch = self.frame["choch_dir"]
        nonzero = choch[choch != 0]
        return int(nonzero.iloc[-1]) if len(nonzero) else 0

    @property
    def counts(self) -> dict[str, int]:
        """Conteos de estado por vela (diagnostico rapido)."""
        return {
            "bos_active": int((self.frame["bos_status"] == "active").sum()),
            "bos_invalidated": int((self.frame["bos_status"] == "invalidated").sum()),
            "choch_active": int((self.frame["choch_status"] == "active").sum()),
            "trend": self.frame["trend"].value_counts().to_dict(),
        }


def _assert_no_upstream_label_consumption(frame: pd.DataFrame) -> None:
    """B4 — Guarda que ninguna columna `label_*` alimente decisión causal.

    Las columnas `label_*` son OBSERVABILIDAD (desenlace ya decidido). Este
    módulo documenta explícitamente que no deben leerse para invertir la
    dirección del BOS/CHOCH. Si algún día el llamador las usara para decidir,
    este assert (ejecutado en tests de aislamiento) lo haría visible.
    """
    # No hay consumo aguas arriba hoy: detect_market_structure escribe y no
    # relee label_* para ninguna decisión. La guarda es defensiva/documental.
    if frame is not None and "label_bos_reason" in getattr(frame, "columns", ()):
        # Se permite la EXISTENCIA (alias de transición); lo que se prohíbe
        # es que estas columnas determinen bos_dir/bos_status/choch_dir.
        pass


def _consecutive_break(break_mask: pd.Series, confirm_bars: int) -> pd.Series:
    """True donde hay `confirm_bars` rupturas CONSECUTIVAS del nivel.

    Una sola ruptura puede ser un wick/fakeout; exigir N cierres seguidos
    filtra los Turtle Soups (LuxAlgo: 2 cuerpos consecutivos).
    """
    if confirm_bars <= 1:
        return break_mask
    out = np.zeros(len(break_mask), dtype=bool)
    run = 0
    arr = break_mask.to_numpy()
    for i in range(len(arr)):
        run = run + 1 if arr[i] else 0
        if run >= confirm_bars:
            out[i] = True
    return pd.Series(out, index=break_mask.index)


def _track_structure(
    d: pd.DataFrame,
    config: StructureConfig,
    is_choch: bool = False,
    inval_level: pd.Series | None = None,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    n = len(d)
    status = pd.Series(["none"] * n, index=d.index, dtype=object)
    age = pd.Series([0] * n, index=d.index, dtype=int)
    discard_reason = pd.Series([pd.NA] * n, index=d.index, dtype=object)
    last_dir = 0
    last_level = float("nan")
    last_idx = -1
    active = False
    close = d["close"].to_numpy()
    dir_col = d["choch_dir"].to_numpy() if is_choch else d["bos_dir"].to_numpy()
    sh = d["swing_high"].to_numpy()
    slv = d["swing_low"].to_numpy()
    bos_level = d["bos_level"].to_numpy() if "bos_level" in d.columns else np.full(n, np.nan)
    last_dir_series = pd.Series(0, index=d.index, dtype=int)
    last_level_series = pd.Series(np.nan, index=d.index, dtype=float)

    for i in range(1, n):
        dr = int(dir_col[i])
        if dr != 0:
            # T9.6 (tesis: el humano no acumula BOS, mira el vigente):
            # si ya habia un evento ACTIVO en la MISMA direccion, el anterior
            # queda SUPERSEDED (reemplazado por este nuevo). Asi no se
            # acumulan miles de BOS active (ej: 21k en M15). Un BOS nuevo en
            # la misma direccion mato al viejo; solo queda 1 vigente/direccion.
            if active and last_idx >= 0 and dr == last_dir:
                status.iloc[last_idx] = "superseded"
                discard_reason.iloc[last_idx] = "SUPERSEDED"
            last_dir, last_idx, active = dr, i, True
            if is_choch:
                # T9.4 (tesis): el CHOCH se invalida cuando el precio cruza el
                # nivel del BOS contrario que ROMPIO (choch_proj_level), no el
                # swing de la vela del CHOCH. Eso evita CHOCH vivos de por
                # vida: un giro alcista muere si el precio cae y rompe el BOS
                # bajista previo. Si no se pasa inval_level, cae al swing.
                last_level = (
                    float(inval_level.iloc[i])
                    if inval_level is not None and pd.notna(inval_level.iloc[i])
                    else (float(sh[i]) if dr == 1 else float(slv[i]))
                )
            else:
                last_level = float(bos_level[i]) if pd.notna(bos_level[i]) else last_level
        if active:
            age.iloc[i] = i - last_idx
            crossed = (last_dir == 1 and close[i] < last_level) or (
                last_dir == -1 and close[i] > last_level
            )
            if crossed:
                status.iloc[i] = "invalidated"
                # T9.4: el evento original (vela last_idx) tambien queda
                # invalidado, no solo la vela del cruce. Asi _bias_from_frame
                # (que lee choch_status en la vela del evento) no lo cuenta
                # como CHOCH vivo de por vida.
                status.iloc[last_idx] = "invalidated"
                active = False
                discard_reason.iloc[last_idx] = "INVALIDATED"
            else:
                status.iloc[i] = "active"
        last_dir_series.iat[i] = last_dir
        last_level_series.iat[i] = last_level

    if not is_choch:
        d["_last_bos_dir"] = last_dir_series
        d["_last_bos_level"] = last_level_series
    else:
        d["_last_choch_dir"] = last_dir_series
        d["_last_choch_level"] = last_level_series
    return status, age, discard_reason


def _derive_trend(d: pd.DataFrame) -> pd.Series:
    """Tendencia por pendiente de swings: HH/HL -> BULLISH; LH/LL -> BEARISH; sino RANGING."""
    trend = pd.Series(RANGING, index=d.index, dtype=object)
    lab = d["swing_label"].fillna("NONE")
    trend[(lab == "HH") | (lab == "HL")] = BULLISH
    trend[(lab == "LH") | (lab == "LL")] = BEARISH
    return trend


def _label_bos_discard(
    d: pd.DataFrame,
    config: StructureConfig,
    bos_discard: pd.Series,
) -> pd.Series:
    """Etiqueta causa de descarte para BOS sin hit en `k` velas.

    B4 (Ley 12 / Ley 1): la lógica que mira `i+1:` (futuro) se delegó a
    `engine.labels.label_bos_outcome`. Esta función preserva EXACTAMENTE la
    columna `bos_discard_reason` de antes (regresión cero) y además deja el
    alias `label_bos_reason` para la fase de transición.
    """
    reasons = label_bos_outcome(d, config, bos_discard)
    # Alias de transición: columna `label_bos_reason` idéntica a la decisión.
    d["label_bos_reason"] = reasons
    return reasons


def _label_choch_discard(
    d: pd.DataFrame,
    config: StructureConfig,
    choch_discard: pd.Series,
) -> pd.Series:
    """Etiqueta causa de descarte para CHOCH.

    B4: la lógica que mira `i+1:` se delegó a `engine.labels`. Preserva la
    columna `choch_discard_reason` (regresión cero) y deja el alias
    `label_choch_reason`.
    """
    reasons = label_choch_outcome(d, config, choch_discard)
    d["label_choch_reason"] = reasons
    return reasons


def _compute_bos_quality(
    d: pd.DataFrame,
    config: StructureConfig,
) -> tuple[pd.Series, pd.Series]:
    """Calcula `bos_quality_score` y `bos_real` para cada BOS emitido.

    Score combina 4 componentes normalizados a [0,1]:
      1. displacement previo en la misma direccion (0/1)
      2. cuerpo de la vela de break / rango de esa vela (0-1)
      3. distancia del close al nivel roto / rango promedio (0-1, cap)
      4. confirmacion posterior: no retorno inmediato (0/1)

    `bos_real` = True si score >= quality_threshold.
    """
    n = len(d)
    quality = pd.Series(np.nan, index=d.index, dtype=float)
    real = pd.Series(False, index=d.index, dtype=bool)

    if n == 0:
        return quality, real

    # Displacement previo evaluado sobre TODO el frame (sin look-ahead por vela).
    disp = detect_displacement(d, DisplacementConfig())
    disp_bull = disp["displacement_bullish"].to_numpy()
    disp_bear = disp["displacement_bearish"].to_numpy()

    body = (d["close"] - d["open"]).abs().to_numpy()
    candle_range = (d["high"] - d["low"]).replace(0, np.nan).to_numpy()
    body_ratio = np.where(np.isfinite(candle_range), body / candle_range, 0.0)

    avg_range = pd.Series(candle_range).rolling(14, min_periods=1).mean().to_numpy()
    close = d["close"].to_numpy()
    bos_levels = d["bos_level"].to_numpy()
    bos_dir = d["bos_dir"].to_numpy()

    highs = d["high"].to_numpy()
    lows = d["low"].to_numpy()

    for i in np.where(bos_dir != 0)[0]:
        direction = int(bos_dir[i])
        level = float(bos_levels[i])
        cr = float(avg_range[i]) if avg_range[i] > 1e-9 else float(candle_range[i])
        if cr <= 0:
            cr = 1e-9

        # 1. displacement previo
        disp_flag = 0.0
        if direction == 1 and i > 0 and bool(disp_bull[i]):
            disp_flag = 1.0
        elif direction == -1 and i > 0 and bool(disp_bear[i]):
            disp_flag = 1.0

        # 2. cuerpo del break
        body_score = float(body_ratio[i])

        # 3. distancia del close al nivel roto
        if direction == 1:
            close_dist = (close[i] - level) / cr
        else:
            close_dist = (level - close[i]) / cr
        close_score = float(np.clip(close_dist / 0.5, 0.0, 1.0))

        # 4. no retorno inmediato (B4: delegado a engine.labels.confirm_score,
        # el único sitio autorizado a mirar i+1:).
        confirm_score = 0.0
        if config.confirm_bars > 0:
            confirm_score = _label_confirm_score(d, i, config.confirm_bars)

        score = (
            disp_flag * 0.25 +
            body_score * 0.25 +
            close_score * 0.25 +
            confirm_score * 0.25
        )
        quality.iloc[i] = float(np.clip(score, 0.0, 1.0))
        real.iloc[i] = score >= config.quality_threshold

    return quality, real


def _exp012_choch_marks(d: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    """EXP-012: marca CHOCH reales (bonus de autoridad, NO muta choch_dir).

    Recorre el frame YA anotado por detect_market_structure y, por cada vela
    con choch_dir != 0, decide si el CHOCH cumple la regla del trader humano:
      (a) MOMENTUM: racha >=2 HH (uptrend) para CHOCH bajista, o >=2 LL
          (downtrend) para CHOCH alcista. Sin empuje no hay "caracter" que
          cambiar -> es ruido (824/ano en M15).
      (b) AFTER_BOS REAL: hubo un BOS de mercado confirmado en la direccion de
          la tendencia opuesta al CHOCH (reusa _last_bos_dir del frame).
      (c) NIVEL = ULTIMO HL (para CHOCH bajista) / LH (alcista) ROTO, NO el
          nivel del BOS roto (choch_proj_level). Son pivotes distintos; usar el
          BOS dispara CHOCH prematuro y deja ruido.
      (d) RECLAIM: choch_status == "invalidated" invalida (T9.4 vigente).

    Devuelve (exp012 bool int8, pivot_level float, after_bos_dir int8).
    Sin copiar el frame; dtypes compactos.
    """
    n = len(d)
    choch_dir = d["choch_dir"].to_numpy() if "choch_dir" in d.columns else np.zeros(n, dtype=int)
    labels = d["swing_label"].to_numpy() if "swing_label" in d.columns else np.array(["NONE"] * n, dtype=object)
    last_bos_dir = d["_last_bos_dir"].to_numpy() if "_last_bos_dir" in d.columns else np.zeros(n, dtype=int)
    choch_status = d["choch_status"].to_numpy(dtype=object) if "choch_status" in d.columns else np.array(["none"] * n, dtype=object)

    exp012 = np.zeros(n, dtype=np.int8)
    pivot_level = np.full(n, np.nan, dtype=np.float64)
    after_bos = np.zeros(n, dtype=np.int8)

    hh_streak = 0
    ll_streak = 0
    # Ultimo HL / LH confirmado (precio del pivote), por indice temporal.
    last_hl_price = np.nan
    last_lh_price = np.nan

    for i in range(n):
        lab = labels[i]
        if lab == "HH":
            hh_streak += 1
            ll_streak = 0
            if "swing_high" in d.columns:
                last_hl_price = np.nan  # un HH nuevo desplaza el contexto de HL
        elif lab == "LL":
            ll_streak += 1
            hh_streak = 0
            if "swing_low" in d.columns:
                last_lh_price = np.nan
        elif lab == "HL":
            # Higher Low: confirma uptrend, NO resetea hh_streak (EXP-012: la
            # cadena HH/HL sostiene el impulso). Solo rompe ll_streak.
            if "swing_low" in d.columns:
                last_hl_price = float(d["swing_low"].to_numpy()[i])
            ll_streak = 0
        elif lab == "LH":
            # Lower High: rompe el uptrend, resetea hh_streak.
            if "swing_high" in d.columns:
                last_lh_price = float(d["swing_high"].to_numpy()[i])
            hh_streak = 0

        cd = int(choch_dir[i])
        if cd == 0:
            continue
        # (a) momentum
        if cd == -1:  # CHOCH bajista: exige uptrend con >=2 HH
            momentum_ok = hh_streak >= 2
            lvl = last_hl_price
        else:  # CHOCH alcista: exige downtrend con >=2 LL
            momentum_ok = ll_streak >= 2
            lvl = last_lh_price
        # (b) after_bos real: BOS de mercado en direccion opuesta al CHOCH
        bos_real = int(last_bos_dir[i]) == -cd
        # (d) reclaim invalida
        reclaimed = str(choch_status[i]) == "invalidated"
        if momentum_ok and bos_real and not reclaimed and pd.notna(lvl):
            exp012[i] = 1
            pivot_level[i] = lvl
            after_bos[i] = int(last_bos_dir[i])

    return (
        pd.Series(exp012, index=d.index, dtype="int8", name="choch_exp012"),
        pd.Series(pivot_level, index=d.index, dtype="float64", name="choch_pivot_level"),
        pd.Series(after_bos, index=d.index, dtype="int8", name="choch_exp012_after_bos"),
    )


def detect_market_structure(
    frame: pd.DataFrame,
    config: StructureConfig | None = None,
) -> MarketStructure:
    """Aplica las reglas canonicas BOS/CHoCH con memoria de estado (secuencial).

    Args:
        frame: DataFrame con columnas `high`/`low`/`open`/`close`, SOLO velas
               cerradas (sin look-ahead).
        config: opciones de deteccion (defaults del canon).

    Returns:
        MarketStructure con el frame anotado (swings, bos, choch, trend) y
        vista de estado.
    """
    if config is None:
        config = StructureConfig()
    d = frame.copy().reset_index(drop=True)
    sh, sl = _swing_points(d, config.swing_lookback)
    d["swing_high"], d["swing_low"] = sh, sl
    d["swing_label"] = _label_swings(sh, sl)

    # BOS: close (cuerpo) rompe el swing previo, CONFIRMADO por `confirm_bars`
    # cierres consecutivos (filtra fakeouts).
    bull_break = d["close"] > sh.shift(1)
    bear_break = d["close"] < sl.shift(1)
    bull_conf = _consecutive_break(bull_break, config.confirm_bars)
    bear_conf = _consecutive_break(bear_break, config.confirm_bars)
    d["bos_dir"] = np.select([bull_conf, bear_conf], [1, -1], default=0)
    d["bos_level"] = np.where(
        d["bos_dir"] == 1,
        sh.shift(1),
        np.where(d["bos_dir"] == -1, sl.shift(1), np.nan),
    )

    d["bos_status"], _, bos_discard = _track_structure(d, config, is_choch=False)
    # CHoCH real: rompe el swing que produjo el ULTIMO BOS, en direccion
    # OPUESTA a ese BOS. No es una copia de BOS.
    # CORRECCION (verificacion 2026-08-06): el CHOCH es un evento de GIRO
    # unico (flanco de ruptura del nivel del BOS contrario), NO un estado
    # sostenido. Marcar close>level en toda vela de continuacion genera CHOCH
    # espurios repetidos (30 en 400 velas H1). Se marca solo donde el cierre
    # ROMPE el nivel AHORA y la vela previa NO lo rompia.
    last_bos_dir = d["_last_bos_dir"].to_numpy()
    last_bos_level = d["_last_bos_level"].to_numpy()
    close_now = d["close"].to_numpy()
    close_prev = np.concatenate([[np.nan], close_now[:-1]])
    level_prev = np.concatenate([[np.nan], last_bos_level[:-1]])
    up_flank = (close_now > last_bos_level) & (close_prev <= level_prev)
    dn_flank = (close_now < last_bos_level) & (close_prev >= level_prev)
    up_choch = up_flank & (last_bos_dir == -1)
    dn_choch = dn_flank & (last_bos_dir == 1)
    choch_raw = np.select([up_choch, dn_choch], [1, -1], default=0)
    # CHoCH es evento de giro unico (1 vela de rupture); su confirmacion es el
    # BOS subsiguiente en la nueva direccion. Sin _consecutive_break (eso
    # mataria el flanco de 1 vela).
    d["choch_dir"] = choch_raw
    # T9.4: el nivel de invalidacion del CHOCH es el nivel del BOS contrario
    # que ROMPIO (choch_proj_level). Se pasa a _track_structure para que el
    # CHOCH muera cuando el precio cruza ese nivel (no vive de por vida).
    d["choch_proj_level"] = d["_last_bos_level"]
    d["choch_status"], _, choch_discard = _track_structure(
        d, config, is_choch=True, inval_level=d["choch_proj_level"]
    )
    # T9.2 — Niveles de PROYECCION e INVALIDACION (geometria pura, sin
    # indicadores), lo que el trader marca en pantalla:
    #   bos_proj_level   = pico opuesto que el precio debe romper para hacer BOS
    #                      (es el nivel del BOS: romperlo confirma, cruzar atras
    #                      lo invalida => bos_inval_level es el mismo nivel).
    #   choch_proj_level = nivel del ULTIMO BOS en direccion opuesta que el
    #                      precio debe romper para confirmar el giro (CHOCH).
    #   choch_inval_level= T9.4: el nivel que REALMENTE mata al CHOCH es el
    #                      choch_proj_level (el BOS contrario roto). Si el
    #                      precio lo cruza, el giro muere (no vive de por vida).
    d["bos_proj_level"] = d["bos_level"]
    d["bos_inval_level"] = d["bos_level"]
    d["choch_inval_level"] = d["choch_proj_level"]

    # EXP-012 (GATE DURO): cuando esta ON, el CHOCH sin empuje >=2 HH/LL (y BOS
    # real detras, nivel HL/LH, sin reclaim) DEJA DE EXISTIR para el motor: se
    # borra choch_dir y se marca choch_status="none". Asi sesgo, secuencia y
    # observador ven solo CHOCH reales, sin tocar sus consumidores. Las columnas
    # choch_exp012 / choch_pivot_level quedan como AUDITORIA de lo censurado.
    # Se corre ANTES de borrar las columnas internas (_last_bos_dir, etc.).
    if config.exp012_choch:
        exp012, pivot_level, after_bos = _exp012_choch_marks(d)
        d["choch_exp012"] = exp012
        d["choch_pivot_level"] = pivot_level
        d["choch_exp012_after_bos"] = after_bos
        mask_noise = exp012 == 0
        d.loc[mask_noise & (d["choch_dir"] != 0), "choch_dir"] = 0
        # status a "none" sobre la mascara de ruido (no sobre choch_dir, que ya
        # quedó 0 arriba): el CHOCH censurado queda totalmente invalidado.
        d.loc[mask_noise & (d["choch_status"] != "none"), "choch_status"] = "none"

    d = d.drop(
        columns=[
            "_last_bos_dir",
            "_last_bos_level",
            "_last_choch_dir",
            "_last_choch_level",
        ]
    )
    d["trend"] = _derive_trend(d)

    n = len(d)
    # MSS = secuencia canonica BOS -> CHOCH -> BOS.
    # Se marca solo cuando aparece un BOS en direccion opuesta al ultimo CHOCH,
    # sin depender del estado activo/invalidado del CHOCH (el CHOCH es un
    # evento puntual, no un estado persistente).
    last_choch_idx = -1
    last_choch_dir = 0
    mss_dir = np.zeros(n, dtype=int)
    for i in range(n):
        if d["choch_dir"].iat[i] != 0:
            last_choch_idx = i
            last_choch_dir = d["choch_dir"].iat[i]
        if (
            d["bos_dir"].iat[i] != 0
            and last_choch_idx != -1
            and d["bos_dir"].iat[i] == -last_choch_dir
        ):
            mss_dir[i] = d["bos_dir"].iat[i]
    d["mss_dir"] = mss_dir

    # M6 — Etiquetado de descarte desde el motor.
    d["bos_discard_reason"] = _label_bos_discard(d, config, bos_discard)
    d["choch_discard_reason"] = _label_choch_discard(d, config, choch_discard)

    # BOS quality score.
    quality, real = _compute_bos_quality(d, config)
    d["bos_quality_score"] = quality
    d["bos_real"] = real

    # MDS_VOLUMEN — Confirmacion OPCIONAL por volumen del breakout BOS/CHOCH.
    # Se ANOTA un ratio (float o NaN); NUNCA veta ni modifica bos_dir/choch_dir
    # ni ninguna columna geometrica. Sin columna 'volume' -> todo NaN.
    d["bos_volume_ratio"] = _bos_volume_ratio(d, config)

    return MarketStructure(frame=d)


def _bos_volume_ratio(d: pd.DataFrame, config: StructureConfig) -> pd.Series:
    """Ratio de volumen en las velas de breakout BOS/CHOCH (NO gate).

    Devuelve una Serie float: ratio en las velas con `bos_dir != 0` o
    `choch_dir != 0`, NaN en el resto. Todo NaN si no hay columna 'volume'
    (regresion cero).
    """
    ratios = pd.Series(np.nan, index=d.index, dtype="float64")
    if "volume" not in d.columns or len(d) == 0:
        return ratios
    bos_dir = d["bos_dir"].to_numpy()
    choch_dir = (
        d["choch_dir"].to_numpy() if "choch_dir" in d.columns else np.zeros(len(d), dtype=int)
    )
    window = int(getattr(config, "volume_window", 20) or 20)
    for i in np.where((bos_dir != 0) | (choch_dir != 0))[0]:
        r = volume_confirm(d, int(i), window)
        if r is not None:
            ratios.iat[int(i)] = float(r)
    return ratios
