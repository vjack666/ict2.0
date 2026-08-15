"""R7 — Single source of truth for ICT decision.

Only public decision API for the in-scope R7 surface:

    evaluate_signals(...)  -> list[ICTSignal]
    latest_plan(...)       -> dict | None   (for observador / live)

Canonical engine: ``sequence.run_sequence`` (+ structural SL / RR 1:3 / killzone).

Out of R7 implementation scope (documented debt — not invisible):
  - legacy/backtest/engine.py  — accepted as DEBT; not rewired here
  - ml/dataset_builder.py      — accepted as DEBT; still uses legacy

Those must not be treated as a second "official" ICT motor for new work.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from ict_backtest._util import (
    avg_candle_range,
    closed_row_at_time,
    tf_duration,
)
from engine.signal import ICTSignal
from engine.trade_levels import (
    STRUCT_SL_MAX_RANGE,
    calc_structural_sl,
    _tp_liquidity,
)
from ict_backtest.simulator import fill_entry_price
from engine.market_structure import detect_market_structure
from engine.multitf_context import MultiTFContext, build_multitf_context, extract_htf_layer
from engine.dealing_range_eq import compute_zone_class
from engine.po3 import compute_po3_complete, Po3MotorConfig
from engine.killzone import killzone_en
from ict_backtest.sequence import SequenceConfig, run_sequence
from engine.rr_by_setup import rr_for
# POI anclado: UNICA fuente = engine (Ley). El backtest NO tiene logica propia.
from engine.poi_anchor import build_htf_structure_index, make_htf_poi_fn, poi_present
# Fase B2 (libro 18): el calculo FIN de entry/SL/TP en el TF de ejecucion
# (M5/M1) es UNICA responsabilidad de engine (Ley: engine/ fuente unica de
# decision). El backtest SOLO lo consume, no lo reimplemenba.
from engine.execution import fine_execution


def _rr_for_raw_signal(s: dict, ltf_df: pd.DataFrame, direction: int, ltf: str = "M15") -> float:
    """Resuelve el RR objetivo del setup de la senal cruda ``s`` (call-site real).

    Usa los detectores reales (is_silver_bullet / is_turtle_soup / is_ote_entry)
    sobre los indices sweep/entry de ``s`` contra ``ltf_df``. Precedencia
    SB > Turtle > OTE > default (mismo contrato que rr_map._setup_of). Si ningun
    setup se confirma, rr_for(None)=3.0 (default de tesis).

    Call-site real del pipeline: evaluate_signals llama esto DENTRO del loop
    (no una funcion aislada) para aplicar rr_target al TP. Los flags post-loop
    (flag_rr) anotan lo mismo en el ICTSignal para el consumidor (scoring/UI).
    """
    sweep_at = s.get("sweep_at")
    entry_at = s.get("entry_at")
    sb_confirmed = False
    turtle_confirmed = False
    ote_confirmed = False
    sweep_ts = None
    entry_ts = None
    if sweep_at is not None and entry_at is not None and ltf_df is not None:
        # Importar por modulo (no por la ref del top) para que los tests
        # puedan mockear a nivel de modulo del detector y para respetar
        # overrides en runtime.
        from engine.silver_bullet import is_silver_bullet as _is_sb
        from engine.turtle_soup import is_turtle_soup as _is_ts
        from engine.ote import is_ote_entry as _is_ote
        try:
            sweep_ts = ltf_df.iloc[int(sweep_at)]["time"]
            entry_ts = ltf_df.iloc[int(entry_at)]["time"]
            sb_confirmed, _ = _is_sb(sweep_ts, entry_ts, direction, killzone_en)
        except Exception:
            sb_confirmed = False
        try:
            _frames = {ltf: ltf_df}
            turtle_confirmed, _ = _is_ts(sweep_ts, direction, _frames, ltf)
        except Exception:
            turtle_confirmed = False
        try:
            # OTE requiere swing en el row de entry; lo lee del ltf_df.
            if "swing_high" in ltf_df.columns and "swing_low" in ltf_df.columns:
                sh = ltf_df.iloc[int(entry_at)].get("swing_high")
                sl = ltf_df.iloc[int(entry_at)].get("swing_low")
                if not (pd.isna(sh) or pd.isna(sl)):
                    ote_confirmed, _ = _is_ote(float(s.get("entry", 0.0)), float(sh), float(sl), direction)
        except Exception:
            ote_confirmed = False
    if sb_confirmed:
        return rr_for("silver_bullet")
    if turtle_confirmed:
        return rr_for("turtle_soup")
    if ote_confirmed:
        return rr_for("ote")
    return rr_for(None)

CANONICAL_ENGINE = "sequence"

# Explicit R7 debt (DoD H2/H3) — not migrated in this change.
R7_DOCUMENTED_DEBT = (
    "legacy/backtest/engine.py",
    "ml/dataset_builder.py",
)


def load_bos_table() -> dict | None:
    """Load empirical bos_table if present (R10); else None -> sequence fallback."""
    from pathlib import Path
    import json

    path = Path(__file__).resolve().parent / "bos_table.json"
    if not path.exists():
        return None
    try:
        return {int(k): int(v) for k, v in json.loads(path.read_text(encoding="utf-8")).items()}
    except (ValueError, OSError):
        return None


def _exec_idx_at_time(exec_df: pd.DataFrame, t: Any) -> int:
    """Indice en ``exec_df`` de la vela cuyo ``time`` <= ``t`` (cerrado).

    Mapeo anti look-ahead del instante de toque del LTF al TF de ejecucion:
    el toque de zona ocurre en el LTF en un timestamp dado; buscamos en el
    exec_df la ULTIMA vela ya cerrada cuyo time sea <= ese timestamp. La vela
    del exec TF que contiene el toque ya cerro (no miramos el futuro del exec
    TF), y NO restamos ``duration`` (a diferencia de closed_row_at_time) para
    no desplazar el ancla una vela mas alla del toque real.
    """
    tt = pd.to_datetime(t, utc=True, errors="coerce")
    times = pd.to_datetime(exec_df["time"], utc=True, errors="coerce")
    prior = exec_df.index[times <= tt]
    if len(prior):
        return int(prior[-1])  # type: ignore[arg-type]
    return 0


def evaluate_signals(
    symbol: str,
    htf: str,
    ltf: str,
    *,
    counter_trend: bool = False,
    tp_mode: str = "fixed2r",
    require_displacement: bool = True,
    displace_gap: int = 6,
    bos_gap: int | None = None,
    bos_table: dict | None = None,
    frames: dict | None = None,
    fill_mode: str = "next_open",
    enable_pd_index: bool = False,
    exec_tf: str | None = None,
    return_phase_seen: bool = False,
    invalidate_on_opposite_swing: bool = False,
) -> list[ICTSignal]:
    """Canonical ICT signal generator (R7).

    Event-sequence sweep→displace→BOS→return, structural SL, RR≥1:3, killzone.

    ``enable_pd_index`` activa la Fase C (capa de autoridad de zonas HTF):
    construye HtfPdIndex y anota ``zone_authority`` en cada señal. Si esta
    False (modo historico), NO se paga el costo de detectar FVG/OB del HTF y
    el comportamiento es identico al de antes de Fase C (C desactivado).

    Fase B2 (libro 18 ICT): ``exec_tf`` ancla entry/SL/TP al TF de EJECUCION
    mas fino (M5/M1), NO al LTF (M15). Por defecto (None) o si == ltf, el
    comportamiento es IDENTICO al historico (regresion cero). El SETUP sigue
    detectandose en el LTF via run_sequence; solo se reanclan entry/SL/TP.
    """
    if bos_table is None:
        bos_table = load_bos_table()
    if frames is None:
        from ict_backtest.data_feed import load_frames

        # Fase 1 (lectura multitemporal): cargar TODA la cadena D1/H4/H1/M15/M5/M1.
        # Los datos de 6 TF ya están en disco (EURUSD/XAUUSD/GBPUSD/...); el
        # cuello de botella era que el motor solo leía [htf, ltf, "D1"].
        tfs = ("D1", "H4", "H1", "M15", "M5", "M1")
        frames = load_frames(symbol, tfs)

    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    ltf_df = ms[ltf]
    htf_df = ms.get(htf, ltf_df)

    # --- Fase C (C1): POI anclado = UNICA fuente engine.poi_anchor (Ley). ---
    # El backtest NO construye su propio indice HTF; consume el motor.
    htf_frames = {tf: df for tf, df in frames.items() if tf != ltf}
    # Mapa de zonas ancladas (BOS/CHOCH padre en misma dir) para el contexto.
    _anchored_events = build_htf_structure_index(htf_frames) if htf_frames else []
    def est_htf_ctx_fn(i: int) -> "MultiTFContext":
        t = ltf_df.iloc[i]["time"]
        anchored = None
        if _anchored_events:
            ltf_t = pd.to_datetime(ltf_df.iloc[i]["time"], utc=True, errors="coerce")
            prior = [e for e in _anchored_events if e.time is not None and e.time <= ltf_t]
            anchored = {}
            for e in prior:
                anchored.setdefault(e.tf, []).append(e)
        return build_multitf_context(
            ms, t, tfs=("D1", "H4", "H1", "M15", "M5", "M1"),
            anchored_pd_zones=anchored,
        )

    # Fallback legacy: si run_sequence se llamara sin est_htf_ctx_fn, este
    # est_htf_fn devuelve el dict plano idéntico al de antes (extract_htf_layer
    # sobre el contexto). Mantiene compatibilidad con el 2º arg posicional.
    def est_htf_fn_legacy(i: int) -> dict:
        return extract_htf_layer(est_htf_ctx_fn(i), htf)

    raw_sigs, phase_seen = run_sequence(
        ltf_df,
        est_htf_fn_legacy,  # 2º arg (est_htf_fn legacy): dict plano válido.
        SequenceConfig(
            counter_trend=counter_trend,
            tp_mode=tp_mode,
            require_displacement=require_displacement,
            displace_gap=displace_gap,
            # R10 running: sin default hardcodeado; sequence trae None por defecto.
            bos_gap=bos_gap,
            # B3 aditivo: flag OFF => build_rules NO anade OPPOSITE_SWING_BREAK
            # => comportamiento bit a bit identico al historico (regresion cero).
            invalidate_on_opposite_swing=invalidate_on_opposite_swing,
        ),
        ltf_tf=ltf,
        bos_table=bos_table,
        # POI anclado = motor (engine.poi_anchor). Sin indice propio del
        # backtest. as_gate=False: NO veta (el veto destruye edge), solo anota.
        htf_poi_fn=make_htf_poi_fn(ltf_df, htf_frames) if htf_frames else None,
        htf=htf,
        est_htf_ctx_fn=est_htf_ctx_fn,
    )

    signals: list[ICTSignal] = []
    # FUENTE ÚNICA de volatilidad/riesgo: rango promedio (high-low) del LTF.
    # Migrado de la columna `atr` (inexistente en el ms, lo que mataba el
    # filtro). Mismo contrato: serie alineada al índice de ltf_df.
    rng_series = avg_candle_range(ltf_df, window=50)

    # --- Fase B2 (libro 18 ICT): TF de EJECUCION para anclar entry/SL/TP. ---
    # None o == ltf  => comportamiento historico (regresion cero). Si es otro
    # TF (M5/M1) ya cargado en `ms`, entry/SL/TP/liq/killzone se recalculan
    # sobre esa vela mas fina (el SL SIEMPRE en el exec TF, nunca en mayor).
    use_exec = exec_tf is not None and exec_tf != ltf and exec_tf in ms
    exec_df = ms[exec_tf] if use_exec else ltf_df

    for s in raw_sigs:
        direction = s["direction"]
        entry_at = s["entry_at"]
        entry_row = ltf_df.iloc[entry_at]
        try:
            entry = fill_entry_price(ltf_df, entry_at, fill_mode)
        except ValueError:
            continue
        # Volatilidad de contexto = rango promedio en la barra de entrada.
        rng = float(rng_series.iloc[entry_at]) if entry_at < len(rng_series) else 0.0
        if not (rng > 0):
            continue
        kz = killzone_en(pd.to_datetime(entry_row["time"], utc=True))
        if kz not in ("London Open", "New York AM", "New York PM"):
            continue
        sweep_row = ltf_df.iloc[s["sweep_at"]]
        sl = calc_structural_sl(sweep_row, direction, rng)
        if sl is None:
            continue
        risk = abs(entry - sl)
        if risk <= 0 or risk > STRUCT_SL_MAX_RANGE * rng:
            continue
        liq = _tp_liquidity(entry_row, direction, ltf_df)
        tp_ext = liq.get("external")
        _rr = _rr_for_raw_signal(s, ltf_df, direction, ltf)
        if liq.get("internal") is not None:
            tp = liq["internal"]
            # Guarda minima: liquidez internal no puede quedar < 2R del risk.
            if direction == 1 and tp <= entry + 2.0 * risk:
                tp = entry + _rr * risk
            if direction == -1 and tp >= entry - 2.0 * risk:
                tp = entry - _rr * risk
        else:
            tp = entry + _rr * risk if direction == 1 else entry - _rr * risk
        # --- Fase B2: reanclar entry/SL/TP al EXEC TF (M5/M1) via engine ---
        # El SETUP se detecto en el LTF (entry_at/sweep_at son indices LTF).
        # La ENTRADA FINA baja al TF de ejecucion segun el motor (libro 18:
        # "la entrada SIEMPRE va en M5/M1"). fine_execution es la UNICA fuente
        # de la decision fina (Ley: engine/ fuente unica PERMANENTE); el
        # backtest SOLO lo consume, no lo reimplementa. Anti look-ahead:
        # t = entry_at closed time del LTF (vela ya cerrada); el motor recorta
        # el exec_df a time<=t. Regla de oro: si exec_tf es None o == ltf, no
        # entramos (regresion cero).
        if use_exec:
            entry_ts = ltf_df.iloc[entry_at]["time"]
            _rr_exec = _rr_for_raw_signal(s, ltf_df, direction, ltf)
            sweep_ts = ltf_df.iloc[s["sweep_at"]]["time"]
            fine = fine_execution(
                ms, entry_ts, direction,
                exec_tf=exec_tf, rr=_rr_exec, sweep_ts=sweep_ts,
            )
            if not fine.get("ok"):
                # Sin estructura fina suficiente en el exec TF: NO vetar la
                # senal (regla Ruben), NO operar en este punto.
                continue
            entry = fine["entry"]
            sl = fine["sl"]
            tp = fine["tp"]
            # Liquidez externa del exec TF (metadata; si el motor la trajo).
            if fine.get("tp_ext") is not None:
                tp_ext = fine["tp_ext"]
            # Killzone sobre el timestamp del exec TF (mismo instante, mas fino).
            entry_row_exec_idx = _exec_idx_at_time(exec_df, entry_ts)
            entry_row_exec = exec_df.iloc[entry_row_exec_idx] if entry_row_exec_idx >= 0 else None
            if entry_row_exec is not None:
                kz = killzone_en(pd.to_datetime(entry_row_exec["time"], utc=True))
            # Recalcular risk con el SL del exec TF antes de los cortes RR.
            risk = abs(entry - sl)
            rng_exec = fine.get("rng_exec") or rng
            if rng_exec and risk > STRUCT_SL_MAX_RANGE * rng_exec:
                continue
        # --- Fin Fase B2 ---
        # --- Brecha C (Opción 2): clase de zona según dealing range HTF ---
        htf_ms = ms.get(htf, ltf_df)
        htf_row = closed_row_at_time(htf_ms, ltf_df.iloc[s["entry_at"]]["time"],
                                     tf_duration(htf))
        zone_class = compute_zone_class(
            sig_dir=direction,
            entry=entry,
            swing_high_htf=float(htf_row["swing_high"]) if htf_row is not None else None,
            swing_low_htf=float(htf_row["swing_low"]) if htf_row is not None else None,
        )
        # --- Brecha E (Opción 2): ciclo PO3/AMD completo al momento de entry ---
        # Estructura con velas CERRADAS <= entry_at (anti look-ahead).
        po3_structure: dict = {}
        for tf_key, tf_df in ms.items():
            sub = tf_df.iloc[: s["entry_at"] + 1]
            if len(sub) == 0:
                continue
            last = sub.iloc[-1]
            po3_structure[tf_key] = {
                "trend": str(last.get("trend", "")),
                "sweep_up": bool(last.get("sweep_up", False)),
                "sweep_down": bool(last.get("sweep_down", False)),
                "bos_dir": int(last.get("bos_dir", 0) or 0),
                "bos_status": str(last.get("bos_status", "")),
                "choch_status": str(last.get("choch_status", "")),
                "fvg_state": str(last.get("fvg_state", "")),
                "ob_dir": str(last.get("ob_dir", "")),
                "session_range": str(last.get("session_range", "")),
                "session_open": float(last.get("open", "nan")) if tf_key == "D1" else None,
            }
        htf_bias = str(htf_ms.iloc[s["entry_at"]]["trend"]) if len(htf_ms) > s["entry_at"] else ""
        po3_complete = compute_po3_complete(
            po3_structure if po3_structure else None,
            config=Po3MotorConfig(bias=htf_bias, exec_tf=exec_tf or ltf, htf=htf),
        )

        signals.append(
            ICTSignal(
            symbol=symbol,
            time=s["time"],
            direction=direction,
            entry=entry,
            stop_loss=sl,
            take_profit=tp,
            model="sequence",
            sweep_at=s["sweep_at"],
            bos_at=s["bos_at"],
            entry_at=s["entry_at"],
            zone_authority=s.get("zone_authority"),
            poi_present=s.get("poi_present"),
            external_tp=tp_ext,
            htf_anchored=poi_present(ltf_df, htf_frames, int(s["entry_at"]), direction),
            zone_class=zone_class,
            po3_complete=po3_complete,
            )
        )

    # --- Cableado de setups ICT (Fase C2/C3/D1/RR) como PASO POST ---
    # Principio Brecha D / leccion A'': los flags SOLO ANOTAN metadato
    # (sb_confirmed, turtle_confirmed, ote_confirmed, rr_target) en cada
    # ICTSignal. NO filtran ni alteran entry/SL/TP. El filtro duro queda
    # como knob apagado (hard_filter=False). Asi el pipeline produce la
    # senal completa y quien consuma (scoring/E1) decide. Call-site real:
    # evaluate_signals AHORA llama estos flags sobre su propia salida.
    from engine.silver_bullet import flag_silver_bullet
    from engine.turtle_soup import flag_turtle_soup
    from engine.ote import flag_ote
    from engine.rr_by_setup import flag_rr
    from engine.liquidity_internal_external import flag_liquidity_irl_erl

    ltf_df_for_flags = frames.get(ltf) if isinstance(frames, dict) else (frames if isinstance(frames, pd.DataFrame) else None)
    for _fn in (
        lambda s: flag_silver_bullet(s, ltf_df_for_flags),
        lambda s: flag_turtle_soup(s, frames, ltf) if isinstance(frames, dict) else None,
        lambda s: flag_ote(s, frames, ltf) if isinstance(frames, dict) else None,
        lambda s: flag_rr(s),
        lambda s: flag_liquidity_irl_erl(s, frames, ltf) if isinstance(frames, dict) else None,
    ):
        try:
            _fn(signals)
        except Exception:
            pass  # knob apagado: si un flag falla, no rompe el pipeline base

    if return_phase_seen:
        return signals, phase_seen
    return signals


def latest_plan(
    symbol: str,
    htf: str = "H4",
    ltf: str = "M15",
    *,
    frames: dict | None = None,
    max_age_bars: int = 48,
) -> dict[str, Any] | None:
    """Last canonical signal as a live plan dict, or None.

    Used by the observador so Lab/LIMIT share the same brain as sequence.
    ``max_age_bars``: ignore signals whose entry_at is older than this many
    bars from the end of the LTF series (stale setups).
    """
    signals = evaluate_signals(symbol, htf, ltf, frames=frames, enable_pd_index=True)
    if not signals:
        return None
    sig = signals[-1]
    # Optional freshness when frames available
    if frames is not None and ltf in frames and sig.entry_at is not None:
        n = len(frames[ltf])
        if n - 1 - int(sig.entry_at) > max_age_bars:
            return None
    side = "LONG" if sig.direction == 1 else "SHORT"
    risk = abs(sig.entry - sig.stop_loss)
    reward = abs(sig.take_profit - sig.entry)
    rr = (reward / risk) if risk > 0 else 0.0
    plan = {
        "engine": CANONICAL_ENGINE,
        "symbol": sig.symbol,
        "side": side,
        "direction": sig.direction,
        "entry": float(sig.entry),
        "sl": float(sig.stop_loss),
        "tp": float(sig.take_profit),
        "rr": float(rr),
        "time": str(sig.time),
        "model": sig.model,
        "sweep_at": sig.sweep_at,
        "bos_at": sig.bos_at,
        "entry_at": sig.entry_at,
    }
    # Fase C (C3): la autoridad de la zona es INFORMACION para el operador
    # (humor del mercado / "donde mirar"), no un filtro.
    za = sig.zone_authority
    if za is not None:
        plan["zone_authority"] = {
            "has_htf_anchor": za.has_htf_anchor,
            "tier": za.tier,
            "stacking_level": za.stacking_level,
            "confidence_weight": za.confidence_weight,
            "level": za.level,
        }
    return plan
