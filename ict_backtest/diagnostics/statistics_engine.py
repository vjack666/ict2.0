"""Fase E — statistics_engine.py (MIDE, no optimiza).

Consume ``list[TradeContext]`` v2 y produce ``StatisticsReport``. Toda métrica
lleva ``n``. Si ``n < MIN_N`` => ``can_conclude=False`` y ``warn`` explícito
(condición #3 de Ruben). NO elige el mejor cohort (condición #4): reporta
todos con evidencia honesta.

Separación: no se conoce con correlation/hypothesis. Solo lectura de contextos.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

import math

from ict_backtest.diagnostics.trade_context import TradeContext
from ict_backtest.diagnostics import cohorts as _cohorts

MIN_N = 30
_Z = 1.96  # normal 95%


@dataclass(frozen=True)
class OverallStat:
    n: int
    win_rate: float
    pf: float
    avg_r: float
    expectancy_r: float


@dataclass(frozen=True)
class CohortStat:
    name: str
    category: str
    n: int
    win_rate: float
    pf: float
    avg_r: float
    ci95_low: float
    ci95_high: float
    can_conclude: bool
    warn: str


@dataclass(frozen=True)
class Comparison:
    cohort: str
    a: str
    b: str
    delta_wr: float
    delta_pf: float
    can_conclude: bool
    verdict: str


@dataclass(frozen=True)
class StatisticsReport:
    overall: OverallStat
    cohorts: list[CohortStat]
    comparisons: list[Comparison]


def _win_rate(contexts: Sequence[TradeContext]) -> float:
    if not contexts:
        return 0.0
    return sum(1 for c in contexts if c.pnl_r > 0) / len(contexts)


def _pf(contexts: Sequence[TradeContext]) -> float:
    if not contexts:
        return 0.0
    gross_w = sum(c.pnl_r for c in contexts if c.pnl_r > 0)
    gross_l = sum(abs(c.pnl_r) for c in contexts if c.pnl_r <= 0)
    return (gross_w / gross_l) if gross_l > 0 else float("inf")


def _wilson(p: float, n: int) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    denom = 1 + _Z**2 / n
    center = (p + _Z**2 / (2 * n)) / denom
    margin = _Z * math.sqrt(p * (1 - p) / n + _Z**2 / (4 * n**2)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def _cohort_stat(name: str, category: str, group: Sequence[TradeContext]) -> CohortStat:
    n = len(group)
    wr = _win_rate(group)
    pf = _pf(group)
    avg_r = sum(c.pnl_r for c in group) / n if n else 0.0
    lo, hi = _wilson(wr, n)
    can = n >= MIN_N
    warn = "" if can else f"n={n} < {MIN_N}: muestra insuficiente, no concluyente"
    return CohortStat(
        name=name, category=category, n=n, win_rate=wr, pf=pf, avg_r=avg_r,
        ci95_low=lo, ci95_high=hi, can_conclude=can, warn=warn,
    )


DEFAULT_COHORTS: list[tuple[str, Callable[[TradeContext], str]]] = [
    ("htf_alignment", _cohorts.htf_alignment),
    ("has_htf_poi", _cohorts.has_htf_poi),
    ("m5_confirms", _cohorts.m5_confirms),
    ("m1_clean", _cohorts.m1_clean),
    ("d1_pd_state", _cohorts.d1_pd_state),
]


def compute(
    contexts: Sequence[TradeContext],
    cohort_specs: list[tuple[str, Callable[[TradeContext], str]]] | None = None,
) -> StatisticsReport:
    cohort_specs = cohort_specs or DEFAULT_COHORTS
    n = len(contexts)
    overall = OverallStat(
        n=n,
        win_rate=_win_rate(contexts),
        pf=_pf(contexts),
        avg_r=sum(c.pnl_r for c in contexts) / n if n else 0.0,
        expectancy_r=sum(c.pnl_r for c in contexts) / n if n else 0.0,
    )
    cohort_stats: list[CohortStat] = []
    comparisons: list[Comparison] = []
    for name, fn in cohort_specs:
        groups: dict[str, list[TradeContext]] = {}
        for c in contexts:
            cat = fn(c)
            groups.setdefault(cat, []).append(c)
        for cat, grp in groups.items():
            cohort_stats.append(_cohort_stat(name, cat, grp))
        real = [cat for cat in groups if cat != "unknown"]
        if len(real) == 2:
            a, b = real
            ga, gb = groups[a], groups[b]
            wa, wb = _win_rate(ga), _win_rate(gb)
            pa, pb = _pf(ga), _pf(gb)
            can = len(ga) >= MIN_N and len(gb) >= MIN_N
            verdict = "sin conclusion (n bajo)" if not can else (
                f"a favor de {a}" if wa > wb else f"a favor de {b}")
            comparisons.append(Comparison(
                cohort=name, a=a, b=b, delta_wr=wa - wb, delta_pf=pa - pb,
                can_conclude=can, verdict=verdict,
            ))
    return StatisticsReport(overall=overall, cohorts=cohort_stats, comparisons=comparisons)
