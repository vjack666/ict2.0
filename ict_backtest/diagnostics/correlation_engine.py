"""Fase E — correlation_engine.py (MIDE asociaciones, NO interpreta).

Consume ``list[TradeContext]`` v2 y produce ``CorrelationReport``. Para cada
faceta de ``market_context`` (vía cohorts) calcula la asociación con el OUTCOME
(win binario => phi; pnl_r continuo => punto-biserial). Solo MIDE.

NO genera hipótesis (eso es HypothesisEngine), NO mira pnl para crear la
faceta (usa cohorts, que solo leen contexto congelado). Cada asociación trae
feature, outcome, coef, n, strength y can_conclude; si n < MIN_N o falta
variación => can_conclude=False con warn explícito.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Sequence

from ict_backtest.diagnostics.trade_context import TradeContext
from ict_backtest.diagnostics import cohorts as _cohorts

MIN_N = 30


@dataclass(frozen=True)
class Association:
    feature: str
    category: str
    outcome: str          # 'win' | 'pnl_r'
    coef: float           # phi o punto-biserial, rango [-1, 1]
    n: int
    strength: str         # negligible | small | moderate | strong
    can_conclude: bool
    warn: str


@dataclass(frozen=True)
class CorrelationReport:
    outcome: str
    associations: list[Association]


def _strength(c: float) -> str:
    a = abs(c)
    if a < 0.1:
        return "negligible"
    if a < 0.3:
        return "small"
    if a < 0.5:
        return "moderate"
    return "strong"


def _phi(a: int, b: int, c: int, d: int) -> float:
    """Coeficiente phi para tabla 2x2 [[a,b],[c,d]] (win vs faceta)."""
    denom = math.sqrt((a + b) * (c + d) * (a + c) * (b + d))
    if denom == 0:
        return 0.0
    return (a * d - b * c) / denom


def _point_biserial(xs: list[int], ys: list[float]) -> float:
    """Correlación punto-biserial entre dummy x y continuo y."""
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    dx = math.sqrt(sum((xs[i] - mx) ** 2 for i in range(n)))
    dy = math.sqrt(sum((ys[i] - my) ** 2 for i in range(n)))
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


DEFAULT_COHORTS: list[tuple[str, Callable[[TradeContext], str]]] = [
    ("htf_alignment", _cohorts.htf_alignment),
    ("has_htf_poi", _cohorts.has_htf_poi),
    ("m5_confirms", _cohorts.m5_confirms),
    ("m1_clean", _cohorts.m1_clean),
    ("d1_pd_state", _cohorts.d1_pd_state),
]


def compute(
    contexts: Sequence[TradeContext],
    outcome: str = "win",
    cohort_specs: list[tuple[str, Callable[[TradeContext], str]]] | None = None,
) -> CorrelationReport:
    if outcome not in ("win", "pnl_r"):
        raise ValueError("outcome debe ser 'win' o 'pnl_r'")
    cohort_specs = cohort_specs or DEFAULT_COHORTS
    assoc: list[Association] = []
    for name, fn in cohort_specs:
        groups: dict[str, list[TradeContext]] = {}
        for c in contexts:
            groups.setdefault(fn(c), []).append(c)
        real = [cat for cat in groups if cat != "unknown"]
        for cat in real:
            grp = groups[cat]
            rest = [c for k, g in groups.items() if k != cat and k != "unknown" for c in g]
            n = len(grp) + len(rest)
            if outcome == "win":
                a = sum(1 for c in grp if c.pnl_r > 0)
                b = len(grp) - a
                cwin = sum(1 for c in rest if c.pnl_r > 0)
                d = len(rest) - cwin
                coef = _phi(a, b, cwin, d)
            else:
                xs = [1] * len(grp) + [0] * len(rest)
                ys = [c.pnl_r for c in grp] + [c.pnl_r for c in rest]
                coef = _point_biserial(xs, ys)
            can = n >= MIN_N and (len(grp) > 0 and len(rest) > 0)
            warn = "" if can else f"n={n} < {MIN_N} o sin contraste: no concluyente"
            assoc.append(Association(
                feature=name, category=cat, outcome=outcome,
                coef=coef, n=n, strength=_strength(coef),
                can_conclude=can, warn=warn,
            ))
    assoc.sort(key=lambda x: abs(x.coef), reverse=True)
    return CorrelationReport(outcome=outcome, associations=assoc)
