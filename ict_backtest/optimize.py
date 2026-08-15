"""ict_backtest/optimize.py — Capa 3: optimizador bayesiano (Optuna) + walk-forward.

Objetivo: afinar los hiperparametros de la Capa 2 (sequence.py) SIN overfit.
Segun docs/ict/09_OPTIMIZADOR_BAYESIANO.md:

  - Optuna (TPE sampler) busca la combinacion que MAXIMIZA el Profit Factor.
  - Walk-forward: dividimos el LTF en ventanas rolling; optimizamos en la
    ventana IN-SAMPLE y validamos en la OUT-OF-SAMPLE (datos nunca vistos).
    El PF promedio out-of-sample es la prueba de fuego contra el overfit.

Diseno:
  - objective(trial): sugere parametros -> corre sequence sobre la ventana
    in-sample -> devuelve PF (o penaliza si pocos trades / PF<=0).
  - Tras la optimizacion, evaluamos los mejores parametros en CADA ventana
    out-of-sample y reportamos PF medio (la metrica honesta).

Uso (rapido, pocos trials, para validar):
  python ict_backtest/optimize.py --symbol EURUSD --ltf M15 --trials 8 \
      --n-windows 3 --window-bars 8000

Uso completo (lento, 50k velas):
  python ict_backtest/optimize.py --symbol EURUSD --ltf M15 --trials 60
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ict_backtest.data_feed import load_frames  # noqa: E402
from engine.market_structure import detect_market_structure  # noqa: E402
from ict_backtest.sequence import run_sequence, SequenceConfig  # noqa: E402
from ict_backtest._util import closed_row_at_time, infer_tf_duration, avg_candle_range  # noqa: E402
from ict_backtest.costs import resolve_cost  # noqa: E402
from engine.signal import ICTSignal  # noqa: E402
from ict_backtest.simulator import simulate_trade, fill_entry_price  # noqa: E402

# Helper global: mapea indice del LTF -> timestamp, usado por el estimator HTF
# (busqueda por tiempo, robusta a recortes de walk-forward).
ltf_time_fn = lambda i: i


@dataclass
class _OptParams:
    displace_gap: int
    bos_gap: int
    require_displacement: bool
    tp_mode: str


def _metrics(pnls: list[float]) -> dict[str, float]:
    n = len(pnls)
    if n == 0:
        return {"trades": 0, "winrate": 0.0, "pf": 0.0, "expectancy": 0.0,
                "max_dd_r": 0.0, "total_r": 0.0}
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    # Tope para evitar inf cuando no hay perdidas (poco realista en vivo).
    pf = (gross_win / gross_loss) if gross_loss > 0 else 10.0
    pf = min(pf, 10.0)
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


def _build_htf_estimator(htf_df: pd.DataFrame):
    htf_dur = infer_tf_duration(htf_df)

    def est_htf_fn(i: int) -> dict:
        # Busca por TIEMPO, no por indice de posicion: asi funciona aunque el
        # LTF y el HTF esten recortados a distinto rango (walk-forward slices).
        # CLOSED-ONLY (R6.1): la barra HTF debe haber cerrado antes de leerse;
        # sino se usa precio futuro (look-ahead cross-timeframe).
        t = ltf_time_fn(i)
        r = closed_row_at_time(htf_df, t, htf_dur)
        return {"trend": str(r.get("trend", "RANGING")),
                "sweep_up": bool(r.get("liquidity_sweep_up", False)),
                "sweep_down": bool(r.get("liquidity_sweep_down", False))}
    return est_htf_fn


def sequence_pf_on_slice(ltf_df: pd.DataFrame, htf_df: pd.DataFrame,
                         params: _OptParams, max_hold: int,
                         cost: dict | None = None) -> dict:
    """Corre la Capa 2 sobre un subconjunto del LTF y devuelve metricas."""
    global ltf_time_fn
    ltf_time_fn = lambda i: ltf_df.iloc[i]["time"]
    est = _build_htf_estimator(htf_df)
    raw_sigs, _phases = run_sequence(
        ltf_df, est,
        SequenceConfig(counter_trend=False, tp_mode=params.tp_mode,
                       require_displacement=params.require_displacement,
                       displace_gap=params.displace_gap, bos_gap=params.bos_gap))

    signals = []
    rng_series = avg_candle_range(ltf_df, window=50)
    for s in raw_sigs:
        direction = s["direction"]
        # Fill default produccion = next_open (open vela siguiente). R6.2 G2.
        entry = fill_entry_price(ltf_df, s["entry_at"], "next_open")
        # FUENTE ÚNICA de volatilidad/riesgo: rango promedio (high-low). Migrado
        # de ATR a rango puro (Fase 1), múltiplo equivalente para medir impacto.
        rng = float(rng_series.iloc[s["entry_at"]]) if s["entry_at"] < len(rng_series) else 0.0
        if not (rng > 0):
            continue
        bos_lvl = s.get("bos_level", float("nan"))
        if direction == 1:
            sl = bos_lvl - 0.5 * rng if np.isfinite(bos_lvl) else entry - rng
        else:
            sl = bos_lvl + 0.5 * rng if np.isfinite(bos_lvl) else entry + rng
        risk = abs(entry - sl)
        if risk <= 0:
            continue
        tp = entry + 2.0 * risk if direction == 1 else entry - 2.0 * risk
        signals.append(ICTSignal(symbol="", time=s["time"], direction=direction,
                                 entry=entry, stop_loss=sl, take_profit=tp,
                                 model="sequence"))

    pnls: list[float] = []
    for sig in signals:
        # FIX #4 (auditoria): pasar costos de mercado reales a simulate_trade.
        trade, _meta = simulate_trade(ltf_df, sig, max_hold, cost=cost)
        if trade is not None:
            pnls.append(trade.pnl_r)
    return _metrics(pnls)


def _split_windows(n: int, n_windows: int, min_train: int) -> list[tuple[int, int, int, int]]:
    """Walk-forward ROLLING multi-fold (hallazgo #5, auditoría 2026-07-11).

    Cada fold: train = [0, te_s), test = [te_s, te_e). Los folds avanzan en el
    tiempo (test contiguo, no solapado). La dirección temporal es CORRECTA:
    se optimiza sobre el pasado y se valida hacia el futuro (no invertida).
    Devuelve lista de (train_start, train_end, test_start, test_end).
    """
    if n_windows < 2:
        n_windows = 2
    # El primer tramo de entrenamiento arranca en 0 y crece; cada fold de test
    # es una porción contigua hacia el final de la serie.
    out = []
    step = (n - min_train) // n_windows
    if step < 1:
        step = 1
    for i in range(n_windows):
        te_s = min_train + step * i
        te_e = min_train + step * (i + 1) if i < n_windows - 1 else n
        if te_e - te_s < 5:
            continue
        out.append((0, te_s, te_s, te_e))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="EURUSD")
    ap.add_argument("--htf", default="H4")
    ap.add_argument("--ltf", default="M15")
    ap.add_argument("--trials", type=int, default=8)
    ap.add_argument("--n-windows", type=int, default=3)
    ap.add_argument("--window-bars", type=int, default=0,
                    help="si >0, usa solo las ultimas N velas del LTF (rapidez). 0=completo.")
    ap.add_argument("--max-hold", type=int, default=96)
    ap.add_argument("--study-name", default="capa3_sequence")
    ap.add_argument("--symbols", default=None,
                    help="lista separada por coma (EURUSD,AUDUSD,...) para correr "
                         "varios pares y agregar metricas OOS. Si se omite usa --symbol.")
    ap.add_argument("--cost", default=None,
                    help="costos en pips 'spread,commission,slippage' "
                         "(ej 0.8,0.5,0.3). Override de la tabla por simbolo. "
                         "Por defecto usa COST_BY_SYMBOL (costos ON).")
    ap.add_argument("--no-cost", action="store_true",
                    help="modo teoria: SIN costos (no usar en produccion).")
    ap.add_argument("--n-jobs", type=int, default=-1,
                    help="nucleos para Optuna (trials en paralelo). "
                         "-1 = todos los nucleos logicos (default). "
                         "1 = secuencial. Reduce RAM si bajas el numero.")
    args = ap.parse_args()

    # Costos de mercado reales (fix #4 auditoria). Default ON (produccion);
    # --no-cost = modo teoria. Referencia por simbolo principal.
    cost = resolve_cost(args.symbol, override=args.cost, no_cost=args.no_cost)
    symbols = [s.strip() for s in (args.symbols or args.symbol).split(",") if s.strip()]
    print(f"[C3] Costos: {cost if cost else 'SIN COSTOS (teoria, --no-cost)'}", flush=True)
    print(f"[C3] Simbolos: {symbols}", flush=True)

    import optuna

    # Agregados OOS de TODOS los simbolos (para veredicto de fondeo).
    all_oos_pfs, all_oos_wrs, all_oos_trades = [], [], []

    for sym in symbols:
        print(f"\n########## SIMBOLO: {sym} ##########", flush=True)
        t0 = time.time()
        frames = load_frames(sym, (args.htf, args.ltf, "D1"))
        # CRITICO: aplicar detect_market_structure IGUAL que run_backtest.py.
        ms = {tf: detect_market_structure(df) for tf, df in frames.items()}
        ltf_df = ms[args.ltf]
        htf_df = ms.get(args.htf, ltf_df)
        print(f"      LTF: {len(ltf_df)} velas | HTF: {len(htf_df)} velas "
              f"({time.time()-t0:.1f}s)", flush=True)

        # Recorte opcional para rapidez (validacion). Siempre usamos el FINAL.
        if args.window_bars and args.window_bars < len(ltf_df):
            ltf_df = ltf_df.iloc[-args.window_bars:].reset_index(drop=True)
            t_min = ltf_df["time"].min()
            htf_df = htf_df[htf_df["time"] >= t_min].reset_index(drop=True)
            print(f"      recorte LTF -> {len(ltf_df)} velas (rapidez)", flush=True)

        n = len(ltf_df)
        min_train = max(2000, n // (args.n_windows + 1))
        windows = _split_windows(n, args.n_windows, min_train)
        print(f"      ventanas walk-forward: {len(windows)} (rolling, {min_train} velas train base)", flush=True)

        def objective(trial: "optuna.trial.Trial") -> float:
            params = _OptParams(
                displace_gap=trial.suggest_int("displace_gap", 1, 12),
                bos_gap=trial.suggest_int("bos_gap", 1, 16),
                require_displacement=trial.suggest_categorical("require_displacement", [True, False]),
                tp_mode=trial.suggest_categorical("tp_mode", ["fixed2r", "liquidity"]),
            )
            tr0, te0 = windows[0][0], windows[0][1]
            m = sequence_pf_on_slice(ltf_df.iloc[tr0:te0].reset_index(drop=True),
                                     htf_df, params, args.max_hold, cost=cost)
            if m["trades"] < 5 or not np.isfinite(m["pf"]) or m["pf"] <= 0:
                return 0.01 * (1.0 + m["trades"] / 100.0)
            return float(m["pf"])

        print(f"[C3] Optuna: {args.trials} trials (TPE) sobre ventana in-sample "
              f"| n_jobs={args.n_jobs} (nucleos)", flush=True)
        import optuna as _opt

        class _CuentaRegresiva:
            def __init__(self, n: int, sym: str):
                self.n = n
                self.sym = sym
                self.t0 = time.time()
            def __call__(self, study, trial):
                done = trial.number + 1
                if done < 1:
                    return
                elapsed = time.time() - self.t0
                avg = elapsed / done
                restan = self.n - done
                falta_min = (avg * restan) / 60.0
                mejor = study.best_value
                barra = "#" * done + "-" * (self.n - done)
                print(f"  [{self.sym}] [{barra}] Trial {done}/{self.n} | falta ~{falta_min:.1f} min "
                      f"| mejor_PF={mejor:.3f}", flush=True)

        study = _opt.create_study(direction="maximize",
                                  sampler=_opt.samplers.TPESampler(seed=42),
                                  study_name=f"{args.study_name}_{sym}")
        t0 = time.time()
        study.optimize(objective, n_trials=args.trials, n_jobs=args.n_jobs,
                       callbacks=[_CuentaRegresiva(args.trials, sym)])
        print(f"      optimizado en {time.time()-t0:.1f}s", flush=True)
        print(f"      MEJOR PF in-sample: {study.best_value:.3f}", flush=True)
        print(f"      MEJORES PARAMS: {study.best_params}", flush=True)

        best = _OptParams(
            displace_gap=study.best_params["displace_gap"],
            bos_gap=study.best_params["bos_gap"],
            require_displacement=study.best_params["require_displacement"],
            tp_mode=study.best_params["tp_mode"],
        )

        print(f"\n===== WALK-FORWARD {sym} (params optimizados) =====", flush=True)
        for wi, (tr_s, tr_e, te_s, te_e) in enumerate(windows):
            if te_e - te_s < 5:
                continue
            m = sequence_pf_on_slice(ltf_df.iloc[te_s:te_e].reset_index(drop=True),
                                     htf_df, best, args.max_hold, cost=cost)
            tag = "IN-SAMPLE" if wi == 0 else "OUT-OF-SAMPLE"
            print(f"  ventana {wi+1} [{tag}]: trades={m['trades']} WR={m['winrate']*100:.1f}% "
                  f"PF={m['pf']:.3f} R={m['total_r']:.1f} DD={m['max_dd_r']:.1f}", flush=True)
            if wi > 0:
                all_oos_pfs.append(m["pf"]); all_oos_wrs.append(m["winrate"])
                all_oos_trades.append(m["trades"])

        # (los pnls individuales no se re-acumulan; el agregado usa PF/WR/trades
        #  por fold, que es suficiente para el veredicto de fondeo)

    # ===== AGREGADO GLOBAL OOS (veredicto de fondeo) =====
    if all_oos_pfs:
        mean_pf = float(np.mean(all_oos_pfs))
        std_pf = float(np.std(all_oos_pfs)) if len(all_oos_pfs) > 1 else 0.0
        total_trades = sum(all_oos_trades)
        mean_wr = float(np.mean(all_oos_wrs)) * 100
        print(f"\n===== AGREGADO OOS GLOBAL ({len(symbols)} simbolos) =====", flush=True)
        print(f">>> PF OUT-OF-SAMPLE MEDIO: {mean_pf:.3f} +/- {std_pf:.3f} "
              f"(folds={len(all_oos_pfs)}, trades={total_trades})", flush=True)
        print(f">>> WR OUT-OF-SAMPLE MEDIO: {mean_wr:.1f}%", flush=True)
        if mean_pf > 1.0 and all(p > 1.0 for p in all_oos_pfs):
            print(">>> VERDICTO: edge mantiene PF>1 en TODOS los folds OOS => ROBUSTO.", flush=True)
        elif mean_pf > 1.0:
            print(">>> VERDICTO: PF>1 promedio OOS pero algun fold <1 => FRAGIL, revisar.", flush=True)
        else:
            print(">>> VERDICTO: PF<=1 en out-of-sample => posible overfit o edge debil.", flush=True)


if __name__ == "__main__":
    main()
