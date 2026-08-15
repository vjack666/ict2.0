"""grid_stats.py — utilidades de la grilla de edge diagnosis (21 variantes x 8 simbolos = 168 celdas).

Dos responsabilidades, ambas nacidas de deuda tecnica de la auditoria R6:

DEUDA A — cap roto.
    El motor original (scripts/edge_diagnosis/run.py, hoy purgado) capaba las
    senales de cada variante a ``MAX_SIGNALS_PER_VARIANT=3000`` ordenando por
    *confianza descendente* y quedandose con el top-N:

        order = rows[np.argsort(-conf[rows])]
        rows = order[:MAX_SIGNALS_PER_VARIANT]

    Eso es un cap ROTO: introduce sesgo de seleccion. Se queda solo con las
    senales de mayor confianza, lo que (1) infla artificialmente win-rate/PF/Sharpe
    de la celda y (2) destruye la representatividad temporal — las senales de alta
    confianza no estan repartidas uniformemente en el tiempo, con lo cual el split
    IS/OOS 70/30 (que es cronologico) queda contaminado. ``cap_signals_unbiased``
    reemplaza ese cap por un submuestreo cronologico uniforme (stride), que respeta
    la distribucion temporal y no privilegia por confianza.

DEUDA B — DSR/PBO en la grilla 168.
    El pipeline F13 (ml/stats_validator.py) implementa Deflated Sharpe Ratio y
    Probability of Backtest Overfitting, pero SOLO se invocaban en el walk-forward
    de una sola celda (scripts/run_walkforward_validation.py) — nunca sobre la grilla
    completa de 168 celdas, que es justamente donde el multiple-testing es severo
    (21 variantes probadas => alto riesgo de que la "ganadora" sea ruido).
    ``compute_grid_overfitting`` cablea DSR/PBO de F13 sobre la grilla entera,
    reusando la implementacion existente (no reimplementa nada).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np

# Reuso directo de F13 (ml/stats_validator.py) — NO reimplementar.
from ml.stats_validator import compute_deflated_sharpe_ratio, compute_pbo

MAX_SIGNALS_PER_VARIANT = 3000


def cap_signals_unbiased(
    signals: Sequence[Any],
    max_signals: int = MAX_SIGNALS_PER_VARIANT,
    *,
    time_key: str = "time",
) -> list[Any]:
    """Capa una lista de senales SIN sesgo de confianza.

    Si ``len(signals) <= max_signals`` devuelve la lista tal cual (ordenada por
    tiempo). Si excede, ordena cronologicamente y toma un submuestreo UNIFORME
    (stride constante) que conserva el primer y ultimo evento y reparte el resto
    de forma pareja en el tiempo. Esto sustituye el ``argsort(-conf)[:N]`` roto.

    ``signals`` puede ser lista de dicts (usa ``s[time_key]``) o de objetos
    (usa ``getattr(s, time_key)``).
    """
    n = len(signals)
    if max_signals <= 0:
        raise ValueError("max_signals debe ser > 0")

    def _t(s: Any) -> Any:
        if isinstance(s, dict):
            return s.get(time_key)
        return getattr(s, time_key)

    ordered = sorted(signals, key=_t)
    if n <= max_signals:
        return ordered

    # Submuestreo uniforme: indices equiespaciados sobre [0, n-1], incluyendo
    # extremos. np.linspace redondeado da un stride que preserva el span temporal.
    idx = np.unique(np.round(np.linspace(0, n - 1, num=max_signals)).astype(int))
    return [ordered[i] for i in idx]


@dataclass(frozen=True)
class GridOverfittingReport:
    """Resultado de DSR/PBO sobre la grilla de edge diagnosis."""

    dsr: float
    pbo: float
    n_cells: int
    n_variants: int
    n_symbols: int
    num_trials: int


def _oos_sharpe(cell: dict) -> float:
    oos = cell.get("oos") or {}
    val = oos.get("sharpe", 0.0)
    try:
        f = float(val)
    except (TypeError, ValueError):
        return 0.0
    return f if np.isfinite(f) else 0.0


def compute_grid_overfitting(
    grid_results: Sequence[dict],
    *,
    n_pbo_simulations: int = 500,
    random_state: int = 42,
) -> GridOverfittingReport:
    """Cablea DSR/PBO (F13) sobre la grilla 168.

    ``grid_results`` es la lista de celdas tal como la produce el edge diagnosis
    (cada celda: ``{"symbol", "variant", "oos": {"sharpe", ...}, ...}``), p.ej.
    ``results/edge_diagnosis/full_results.json``.

    - DSR: se computa sobre el vector de Sharpe OOS por variante (promediado sobre
      simbolos), con ``num_trials = n_variants`` — el numero de hipotesis probadas
      en la grilla (correccion por multiple testing).
    - PBO: se arma la matriz ``(n_symbols folds x n_variants strategies)`` de Sharpe
      OOS y se pasa a ``compute_pbo`` de F13. Los simbolos actuan como folds y las
      variantes como estrategias en competencia.
    """
    symbols = sorted({c["symbol"] for c in grid_results})
    variants = sorted({c["variant"] for c in grid_results})
    n_sym, n_var = len(symbols), len(variants)

    sym_idx = {s: i for i, s in enumerate(symbols)}
    var_idx = {v: i for i, v in enumerate(variants)}

    # Matriz simbolos x variantes de Sharpe OOS (folds x strategies para PBO).
    matrix = np.zeros((n_sym, n_var), dtype=float)
    for c in grid_results:
        matrix[sym_idx[c["symbol"]], var_idx[c["variant"]]] = _oos_sharpe(c)

    # DSR sobre el Sharpe medio por variante; num_trials = variantes probadas.
    per_variant_sharpe = matrix.mean(axis=0)
    dsr = compute_deflated_sharpe_ratio(per_variant_sharpe, num_trials=max(n_var, 1))

    # PBO reusando F13: matriz folds(symbols) x strategies(variants).
    if n_sym >= 2 and n_var >= 2:
        pbo = compute_pbo(
            matrix,
            n_simulations=n_pbo_simulations,
            random_state=random_state,
        )
    else:
        pbo = 0.0

    return GridOverfittingReport(
        dsr=float(dsr),
        pbo=float(pbo),
        n_cells=len(grid_results),
        n_variants=n_var,
        n_symbols=n_sym,
        num_trials=n_var,
    )
