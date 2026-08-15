"""ict_backtest/run_backtest.py — Runner PARTE 2: backtest ICT end-to-end.

Opcion A (default): HTF=D1, LTF=H4 (mas datos historicos).
Carga datos -> features ICT -> senales (mini-check dashboard) -> simulacion
vela a vela -> metricas (PF, winrate, expectancy, maxDD en R).

Uso:
  python ict_backtest/run_backtest.py --symbol XAUUSD --htf D1 --ltf H4
  python ict_backtest/run_backtest.py --symbol XAUUSD --htf H4 --ltf H4 --model intradia

NO ejecuta nada pesado en import; solo al correr como script.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.signal import ICTSignal  # noqa: E402
from ict_backtest.simulator import simulate_trade_with_context  # noqa: E402
# POI anclado: UNICA fuente = engine (Ley). El backtest no construye indice propio.
from engine.poi_anchor import build_htf_structure_index  # noqa: E402
from ict_backtest._util import (  # noqa: E402
    closed_row_at_time, tf_duration,
)


def _write_runner_progress(
    *,
    current: str,
    done: int | None = None,
    total: int | None = None,
    unit: str = "items",
    details: dict | None = None,
) -> None:
    """Real progress for Hermes Runner Monitor (HERMES_PROGRESS_FILE).

    No fake %: only write when we know done/total or at least a current stage.
    """
    path = (os.environ.get("HERMES_PROGRESS_FILE") or "").strip()
    if not path:
        return
    payload: dict = {"current": current, "unit": unit}
    if done is not None:
        payload["done"] = int(done)
    if total is not None:
        payload["total"] = int(total)
    if details:
        payload["details"] = details
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(payload), encoding="utf-8")
    except OSError:
        pass

from ict_backtest.data_feed import load_frames  # noqa: E402
from ict_backtest.costs import resolve_cost  # noqa: E402
from ict_backtest.simulator import simulate_trade  # noqa: E402
from engine.market_structure import detect_market_structure  # noqa: E402
from ict_backtest.canonical import (  # noqa: E402
    evaluate_signals,
    load_bos_table,
)
from engine.plan_attach import attach_alignment  # noqa: E402


def _metrics(pnls: list[float]) -> dict[str, float]:
    n = len(pnls)
    if n == 0:
        return {"trades": 0, "winrate": 0.0, "pf": 0.0, "expectancy": 0.0,
                "max_dd_r": 0.0, "total_r": 0.0}
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    pf = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
    # equity curve en R para maxDD
    equity, peak, max_dd = 0.0, 0.0, 0.0
    for p in pnls:
        equity += p
        peak = max(peak, equity)
        max_dd = min(max_dd, equity - peak)
    return {
        "trades": n,
        "winrate": len(wins) / n,
        "pf": pf,
        "expectancy": sum(pnls) / n,
        "max_dd_r": max_dd,
        "total_r": sum(pnls),
    }


def generate_sequence_signals(symbol: str, htf: str, ltf: str,
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
                               invalidate_on_opposite_swing: bool = False) -> list:
    """R7 thin wrapper — all decision logic lives in ``ict_backtest.canonical``.

    ``enable_pd_index`` enciende la Fase C (autoridad de zonas HTF). Por defecto
    False (backtest de rendimiento queda igual a lo historico; ver R4: backtests
    bloqueados hasta Fase G). La capa de AUTORIDAD se mide en backtest solo de
    forma explicita, nunca como filtro.
    """
    result = evaluate_signals(
        symbol,
        htf,
        ltf,
        counter_trend=counter_trend,
        tp_mode=tp_mode,
        require_displacement=require_displacement,
        displace_gap=displace_gap,
        bos_gap=bos_gap,
        bos_table=bos_table,
        frames=frames,
        fill_mode=fill_mode,
        enable_pd_index=enable_pd_index,
        exec_tf=exec_tf,
        return_phase_seen=return_phase_seen,
        invalidate_on_opposite_swing=invalidate_on_opposite_swing,
    )
    if return_phase_seen:
        res, phase_seen = result  # type: ignore[misc]
        return res, phase_seen  # type: ignore[misc]
    return result


def _build_objs_by_tf(frames: dict, symbol: str, tf_chain=("D1", "H4", "H1", "M15", "M5", "M1")) -> dict:
    """Fuente canonica de MarketObjects por TF para el medidor de alineacion.

    usa data_feed.build_objects (Fase A/B/C): produce MarketObjects con
    origin_tf + bar_index + bar_time sellados (translation.df_to_objects).
    Solo construye sobre TF_CHAIN (no todos los TF en disco) para no pagar
    el costo de M1/M5 masivos cuando el medidor solo necesita la cadena.
    Agrupa por origin_tf UNA vez por backtest (O(n)), fuera del loop de
    senales. Anti-look-ahead se aplica DESPUES en plan_attach por bar_time.
    Si falla, devuelve {} (missing, Regla #4 — sin inventar) y el medidor
    califica solo con el emit_* de la senal.
    """
    try:
        from ict_backtest.data_feed import build_objects
        sub = {tf: df for tf, df in frames.items() if tf in tf_chain}
        all_objs = build_objects(sub, symbol=symbol)
    except Exception:
        return {}
    by_tf: dict = {}
    for o in all_objs or []:
        tf = getattr(o, "origin_tf", None)
        if tf:
            by_tf.setdefault(tf, []).append(o)
    return by_tf


def _htf_swing_closed(ms: dict, t, htf_tf: str = "H4") -> tuple[float, float] | None:
    """Swing HTF ya CERRADO en t para dealing range (premium/discount).

    Usa el max high / min low de las velas HTF cerradas (time <= t).
    Anti look-ahead: solo barras cerradas. Devuelve (high, low) o None.
    """
    df = ms.get(htf_tf)
    if df is None or len(df) == 0:
        return None
    import pandas as pd
    try:
        times = pd.to_datetime(df["time"], utc=True, errors="coerce")
        tt = pd.to_datetime(t, utc=True, errors="coerce")
        mask = times <= tt
        win = df.loc[mask]
    except Exception:
        return None
    if len(win) < 3:
        return None
    return (float(win["high"].max()), float(win["low"].min()))


def run_sequence_backtest(symbol: str, htf: str, ltf: str, max_hold: int,
                           counter_trend: bool = False, tp_mode: str = "fixed2r",
                           require_displacement: bool = True,
                           displace_gap: int = 6, bos_gap: int | None = 10,
                           bos_table: dict | None = None,
                           cost: dict | None = None,
                           fill_mode: str = "next_open",
                           enable_pd_index: bool = False,
                           backtest_id: str | None = None,
                           window_months: int | None = None,
                           attach_plan: bool = False,
                           plan_gate: bool = False,
                           exec_tf: str | None = None,
                           invalidate_on_opposite_swing: bool = False) -> dict:
    """Capa 2: backtest con motor EVENT-SEQUENCE (espera los sucesos en orden).

    Fase D (Paso2): acumula RawDiagnosticData por trade en `contexts` (en
    memoria) para que el Diagnosis Engine (Paso3) los congele en TradeContext.
    NO altera el PnL ni la decision (R1 de Paso2). `backtest_id` permite
    reconstruir Backtest N -> Trade M.

    `window_months` (Fase D validacion): si se da, recorta la ventana LTF a
    los ultimos N meses (el HTF se recorta en consecuencia) ANTES de generar
    senales. No cambia la logica, solo el universo de velas.
    """
    backtest_id = backtest_id or f"BT-{uuid.uuid4().hex[:8]}"
    tag = f"SEQ-{'CT' if counter_trend else 'AT'}-{tp_mode}{'-disp' if require_displacement else ''}"
    # Fase D multi-TF (reglas #1/#4): cadena completa D1/H4/H1/M15/M5/M1.
    # Se cargan TODOS los TF que existan en disco; los ausentes quedan como
    # MISSING en el snapshot (nunca se inventan ni se copian de otro TF).
    TF_CHAIN = ("D1", "H4", "H1", "M15", "M5", "M1")
    print(f"[1/3] Cargando frames {symbol} + market_structure ...", flush=True)
    _write_runner_progress(
        current=f"[1/3] load+structure {symbol} {htf}->{ltf}",
        done=0,
        total=3,
        unit="stages",
        details={"stage": "load+structure", "symbol": symbol, "htf": htf, "ltf": ltf},
    )
    t0 = time.time()
    load_kwargs: dict = {}
    if window_months is not None:
        # Recorte de ventana ANTES de cargar (ahorra I/O + features)
        last = None
        for tf in TF_CHAIN:
            try:
                p = ROOT / "data" / "raw" / f"{symbol}_{tf}.parquet"
                if p.exists():
                    last = pd.read_parquet(p, columns=["time"])["time"].iloc[-1]
                    break
            except Exception:
                continue
        if last is not None:
            load_kwargs["start"] = last - pd.DateOffset(months=window_months)
    frames = load_frames(symbol, TF_CHAIN, **load_kwargs)
    ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
    ltf_df = ms[ltf]
    # Fase D: est_htf_fn para que el EMISOR propague htf_context REAL
    # (no placeholder). Solo si enable_pd_index (igual que evaluate_signals).
    est_htf_fn = None
    if enable_pd_index:
        htf_frames = {tf: df for tf, df in ms.items() if tf != ltf}
        _anchored_events = build_htf_structure_index(htf_frames) if htf_frames else []
        htf_df = ms.get(htf, ltf_df)

        def est_htf_fn(i: int) -> dict:  # type: ignore[no-redef]
            t = ltf_df.iloc[i]["time"]
            r = closed_row_at_time(htf_df, t, tf_duration(htf))
            ltf_t = pd.to_datetime(t, utc=True, errors="coerce")
            pd_zones = [
                e for e in _anchored_events
                if e.time is not None and e.time <= ltf_t
            ]
            return {
                "trend": str(r.get("trend", "RANGING")),
                "sweep_up": bool(r.get("liquidity_sweep_up", False)),
                "sweep_down": bool(r.get("liquidity_sweep_down", False)),
                "pd_zones": pd_zones,
            }
    _write_runner_progress(
        current=f"[2/3] sequence signals {symbol}",
        done=1,
        total=3,
        unit="stages",
        details={"stage": "sequence_signals", "frames": sorted(frames)},
    )
    generated = generate_sequence_signals(symbol, htf, ltf,
                                        counter_trend=counter_trend,
                                        tp_mode=tp_mode,
                                        require_displacement=require_displacement,
                                        displace_gap=displace_gap,
                                        bos_gap=bos_gap, frames=frames,
                                        bos_table=bos_table,
                                        fill_mode=fill_mode,
                                        enable_pd_index=enable_pd_index,
                                        exec_tf=exec_tf,
                                        return_phase_seen=True,
                                        invalidate_on_opposite_swing=invalidate_on_opposite_swing)
    # Compatibility with thin test/consumer doubles that return only signals;
    # the canonical wrapper returns (signals, phase_seen) when requested.
    if isinstance(generated, tuple) and len(generated) >= 2:
        signals, phase_seen = generated[0], generated[1]
    else:
        signals = generated
        phase_seen = {"SWEEP": 0, "DISPLACE": 0, "BOS": 0, "ENTRY": 0}
    print(f"      features en {time.time()-t0:.1f}s", flush=True)
    print(f"[2/3] Secuencia EVENT-DRIVEN (sweep->displace->BOS->retorno cuadro) ...", flush=True)
    print(f"      {len(signals)} senales", flush=True)
    _write_runner_progress(
        current=f"[2/3] sequence signals ready {symbol}",
        done=2,
        total=3,
        unit="stages",
        details={
            "stage": "sequence_signals_ready",
            "frames": sorted(frames),
            "signals": len(signals),
            "phase_seen": phase_seen,
        },
    )

    # A1 Opción B: compuerta de ejecución FSM (plan_gate). run_sequence intacto:
    # usa TODAS las señales; solo decide cuáles SE OPERAN. El dict objs por TF
    # se construye UNA vez (anti look-ahead real por bar_time en plan_step).
    # plan_step evalúa el estado del plan POR señal (contexto cerrado <= t),
    # no acumula entre señales (coherente con "contexto en t" de la tesis).
    plan_gate_fsm = None
    plan_gate_vetoes: list = []
    if plan_gate:
        from engine.plan_driver import plan_step, _state_rank
        from engine.plan_fsm import PlanFSM, PlanState
        plan_gate_fsm = PlanFSM()
        plan_gate_objs = _build_objs_by_tf(frames, symbol)
        plan_gate_threshold = PlanState.STRUCTURE_OK

    print(f"[3/3] Simulando trades vela a vela (max_hold={max_hold}) ...", flush=True)
    pnls: list[float] = []
    exits: dict[str, int] = {}
    contexts: list = []  # Fase D Paso 2: RawDiagnosticData emitido por trade
    alignments: list = []  # Fase 5: AlignmentReport adjunto por senal (modo OBSERVE)
    total = len(signals)
    _write_runner_progress(
        current=f"[3/3] simulate trades {symbol}",
        done=0,
        total=max(total, 1),
        unit="signals",
        details={"stage": "simulate_trades", "signals_total": total, "trades_found": 0},
    )
    # Fase 5 (Brecha A1, modo OBSERVE): medidor de alineacion multi-TF.
    # Fuente canonica de MarketObjects por TF: build_objects (Fase A/B/C),
    # agrupados por origin_tf UNA vez por backtest (no en el loop). El
    # anti-look-ahead real (bar_time <= t) se aplica en plan_attach.
    # Si no hay objetos, objs_by_tf={} y score_plan califica solo con el
    # emit_* de la senal (sin inventar, Regla #4).
    objs_by_tf = _build_objs_by_tf(frames, symbol) if attach_plan else {}
    # Update monitor ~20 times max (same cadence as console bar)
    step = max(1, total // 20) if total else 1
    for k, sig in enumerate(signals, 1):
        # A1 Opción B: si el gate está activo, la FSM decide si esta señal
        # opera. Las señales descartadas NO se simulan (se registra el veto).
        if plan_gate_fsm is not None:
            state = plan_step(plan_gate_fsm, sig, plan_gate_objs)
            if _state_rank(state) < _state_rank(plan_gate_threshold):
                plan_gate_vetoes.append({"signal_index": k - 1, "state": state.value})
                continue
        # Fase D multi-TF: snapshot closed-only de TODA la cadena en signal.time.
        from ict_backtest.v2.context_mtf import build_context_stack
        stack = None
        try:
            st = getattr(sig, "entry_at", None)
            t = ltf_df.iloc[int(st)]["time"] if st is not None else sig.time
            # zonas PD ancladas (Fase C) para poi real de H4/H1
            anchored: dict = {}
            if est_htf_fn is not None:
                htf_ctx = est_htf_fn(int(st) if st is not None else 0)
                for z in htf_ctx.get("pd_zones", []) or []:
                    tf = getattr(z, "tf", None)
                    if tf:
                        anchored.setdefault(tf, []).append(z)
            stack = build_context_stack(ms, t, tfs=TF_CHAIN, anchored_pd_zones=anchored)
        except (TypeError, ValueError, KeyError, IndexError):
            stack = None
        # Fase 5 (Brecha A1, modo OBSERVE): adjunta AlignmentReport multi-TF a la
        # senal. NO filtra ni cambia el PnL. Usa objs_by_tf REALES (MarketObjects
        # sellados por TF) + swing HTF cerrado en t (dealing range real).
        if attach_plan:
            try:
                st = getattr(sig, "entry_at", None)
                t = ltf_df.iloc[int(st)]["time"] if st is not None else sig.time
                swing = _htf_swing_closed(ms, t, htf_tf=htf if htf in ms else "H4")
                attached = attach_alignment(sig, objs_by_tf, swing=swing)
                alignments.append(attached["alignment"])
            except Exception:
                pass
        trade, meta, raw = simulate_trade_with_context(
            ltf_df, sig, max_hold, cost=cost, backtest_id=backtest_id,
            est_htf_fn=est_htf_fn, market_stack=stack,
        )
        if trade is not None:
            pnls.append(trade.pnl_r)
            exits[meta["exit_reason"]] = exits.get(meta["exit_reason"], 0) + 1
        if raw is not None:
            contexts.append(raw)
        if total and (k % step == 0 or k == total):
            pct = 100 * k // total
            bar = "#" * (pct // 5) + "-" * (20 - pct // 5)
            print(f"      [{bar}] {pct}% ({k}/{total})", flush=True)
            _write_runner_progress(
                current=f"[3/3] simulate {symbol} {k}/{total}",
                done=k,
                total=total,
                unit="signals",
                details={
                    "stage": "simulate_trades",
                    "signals_total": total,
                    "signals_processed": k,
                    "trades_found": len(pnls),
                },
            )

    m = _metrics(pnls)
    m["contexts"] = contexts  # Fase D Paso 2: datos emitidos (Paso 3 los congela)
    m["backtest_id"] = backtest_id
    m["funnel"] = phase_seen  # B2 (Ley 11): embudo de fases sweep→displace→BOS→entry
    if plan_gate:
        # A1 Opción B: reporte de vetos del gate (auditoría del plan FSM).
        # Cada entrada: {"signal_index", "state"} con el estado que vetó.
        m["plan_gate"] = True
        m["vetoes"] = plan_gate_vetoes
        m["trades_gated"] = m["trades"]
        m["signals_total"] = total
        print(f"  plan_gate    : {len(plan_gate_vetoes)} vetos / {total} señales "
              f"(umbral STRUCTURE_OK)", flush=True)
    if attach_plan:
        # Fase 5: AlignmentReport adjunto por senal (modo OBSERVE). Solo se
        # incluye si el flag esta activo; el backtest estandar queda intacto.
        m["alignments"] = alignments
    _write_runner_progress(
        current=f"done {symbol} PF={m['pf']:.3f} n={m['trades']}",
        done=total if total else 1,
        total=total if total else 1,
        unit="signals",
        details={
            "stage": "completed",
            "signals_total": total,
            "signals_processed": total,
            "trades": m["trades"],
            "winrate": m["winrate"],
            "pf": m["pf"],
            "total_r": m["total_r"],
        },
    )
    print(f"\n===== RESULTADO [{tag}] =====", flush=True)
    print(f"  simbolo      : {symbol}  |  Capa2 sequence  |  {htf}->{ltf}", flush=True)
    print(f"  trades       : {m['trades']}", flush=True)
    print(f"  winrate      : {m['winrate']*100:.1f}%", flush=True)
    print(f"  profit factor: {m['pf']:.3f}", flush=True)
    print(f"  expectancy   : {m['expectancy']:.3f} R/trade", flush=True)
    print(f"  total        : {m['total_r']:.1f} R", flush=True)
    print(f"  max drawdown : {m['max_dd_r']:.1f} R", flush=True)
    print(f"  salidas      : {exits}", flush=True)
    return m


def run(symbol: str, htf: str, ltf: str, model: str, max_hold: int,
        counter_trend: bool = False, tp_mode: str = "fixed2r",
        require_displacement: bool = False, cost: dict | None = None,
        exec_tf: str | None = None) -> dict:
    """Backtest POR DEFECTO (sin --engine) sobre el motor canonico sequence.

    R7 T3.1 (DoD #2 / H12): el camino por defecto delega en `run_sequence`
    (motor canonico), NO en `build_signals_from_frames` (isla engine
    divergente: entry en close, RR 1:2). El parametro `model` se portara a
    `SequenceConfig` en T3.3; aqui el motor canonico es event-sequence
    (tesis 18: entry en retorno al cuadro, RR 1:3, SL estructural).
    """
    return run_sequence_backtest(symbol, htf, ltf, max_hold,
                                 counter_trend=counter_trend,
                                 tp_mode=tp_mode,
                                 require_displacement=require_displacement,
                                 cost=cost,
                                 exec_tf=exec_tf)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--htf", default="D1")
    ap.add_argument("--ltf", default="H4")
    ap.add_argument("--model", default="intradia", choices=["intradia", "scalping", "po3"],
                    help="po3 = SOLO ciclo PO3 completo (R4 E2, medicion aislada)")
    ap.add_argument("--max-hold", type=int, default=16)
    ap.add_argument("--counter-trend", action="store_true")
    ap.add_argument("--tp-mode", default="fixed2r", choices=["fixed2r", "liquidity"])
    ap.add_argument("--require-displacement", action="store_true")
    ap.add_argument("--cost", default=None,
                    help="costos en pips 'spread,commission,slippage' "
                         "(ej 0.8,0.5,0.3). Override de la tabla por simbolo. "
                         "Por defecto usa COST_BY_SYMBOL del simbolo (costos ON).")
    ap.add_argument("--no-cost", action="store_true",
                    help="modo teoria: SIN costos (no usar en produccion).")
    ap.add_argument("--no-displacement", action="store_true",
                    help="no exigir vela de displacement (sequence engine)")
    ap.add_argument("--sweep", action="store_true",
                    help="corre las 4 variantes PARTE 2.1 y muestra tabla comparativa")
    ap.add_argument("--displace-gap", type=int, default=6,
                    help="ventana displacement tras sweep (sequence engine)")
    ap.add_argument("--bos-gap", type=int, default=10,
                    help="ventana BOS tras displacement (sequence engine)")
    ap.add_argument("--engine", default="sequence", choices=["sequence", "checklist"],
                    help="R7: only sequence is canonical. 'checklist' is an alias to sequence.")
    ap.add_argument("--attach-plan", action="store_true",
                    help="Fase 5: adjunta AlignmentReport multi-TF por senal (modo OBSERVE, "
                         "no filtra ni cambia el PnL). Mide calidad de alineacion.")
    ap.add_argument("--window-months", type=int, default=None,
                    help="Fase D validacion: recorta la ventana LTF a los ultimos N meses "
                         "ANTES de cargar (ahorra I/O + features).")
    ap.add_argument("--exec-tf", default=None, choices=[None, "M5", "M1"],
                    help="Fase B2 (libro 18): TF de EJECUCION fino (M5/M1) para anclar "
                         "entry/SL/TP. None = LTF (M15, regresion cero).")
    ap.add_argument("--invalidate-on-opposite-swing", action="store_true",
                    help="B3 aditivo: activa OPPOSITE_SWING_BREAK (invalida setups cuando "
                         "el precio rompe el swing opuesto). OFF = regresion cero "
                         "(identico al historico).")
    args = ap.parse_args()

    cost = resolve_cost(args.symbol, override=args.cost, no_cost=args.no_cost)

    # R7: checklist alias removed — always sequence.
    if args.sweep:
        variants = [
            ("V1 AT fixed2r",        dict(counter_trend=False, tp_mode="fixed2r", require_displacement=False)),
            ("V2 AT liquidity+disp", dict(counter_trend=False, tp_mode="liquidity", require_displacement=True)),
            ("V3 CT liquidity+disp", dict(counter_trend=True,  tp_mode="liquidity", require_displacement=True)),
            ("V4 CT fixed2r",        dict(counter_trend=True,  tp_mode="fixed2r",  require_displacement=False)),
        ]
        print("### SWEEP (R7 sequence only) ###")
        for name, kw in variants:
            print(f"\n----- {name} -----")
            m = run(args.symbol, args.htf, args.ltf, args.model, args.max_hold, cost=cost, exec_tf=args.exec_tf, **kw)
            print(f">>> {name}: PF={m['pf']:.3f} WR={m['winrate']*100:.1f}% trades={m['trades']} R={m['total_r']:.1f}")
        return

    run_sequence_backtest(
        args.symbol, args.htf, args.ltf, args.max_hold,
        counter_trend=args.counter_trend, tp_mode=args.tp_mode,
        require_displacement=not args.no_displacement,
        displace_gap=args.displace_gap, bos_gap=args.bos_gap,
        cost=cost,
        enable_pd_index=True,  # Fase C: autoridad de zonas HTF como METADATA (sin gate, R1 se preserva)
        backtest_id=f"BT-CLI-{uuid.uuid4().hex[:8]}",  # Fase D Paso 2: id estable de corrida
        attach_plan=args.attach_plan,  # Fase 5: calificador de alineacion (modo OBSERVE)
        window_months=args.window_months,  # Fase D validacion: recorte de ventana pre-carga
        exec_tf=args.exec_tf,  # Fase B2 (libro 18): entry/SL/TP en TF fino M5/M1
        invalidate_on_opposite_swing=args.invalidate_on_opposite_swing,  # B3 aditivo (regresion cero OFF)
    )


if __name__ == "__main__":
    main()
