"""Fase E — hypothesis_engine.py (INTERPRETA evidencia, NO crea reglas).

Consume ``StatisticsReport`` + ``CorrelationReport`` (ya construidos) y produce
``HypothesisReport``. Transforma observaciones en hipótesis EXPLÍCITAS.

NO consume TradeContext crudo (separación limpia: recibe reportes).
NO genera reglas de trading ni modifica lógica de entrada.
NO elige "la mejor" hipótesis: reporta TODAS, rankeadas por confianza.
Toda hipótesis trae: statement, evidence_for, evidence_against, n, metrics,
confidence, can_conclude. Lo no concluyente va a ``inconclusive``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ict_backtest.diagnostics.statistics_engine import StatisticsReport, CohortStat
from ict_backtest.diagnostics.correlation_engine import CorrelationReport, Association


@dataclass(frozen=True)
class Hypothesis:
    statement: str
    evidence_for: str
    evidence_against: str
    n: int
    metrics: str
    confidence: str       # low | medium | high
    can_conclude: bool


@dataclass(frozen=True)
class HypothesisReport:
    hypotheses: list[Hypothesis]
    inconclusive: list[str]


def _conf_from(strong: bool, n_ok: bool) -> str:
    if not n_ok:
        return "low"
    return "high" if strong else "medium"


def _find_cohort(reps: StatisticsReport, name: str, cat: str) -> CohortStat | None:
    for cs in reps.cohorts:
        if cs.name == name and cs.category == cat:
            return cs
    return None


def _find_assoc(reps: CorrelationReport, name: str, cat: str) -> Association | None:
    for a in reps.associations:
        if a.feature == name and a.category == cat:
            return a
    return None


# Umbral de fuerza de asociación para considerar "fuerte" (|coef| >= 0.3)
STRONG_COEF = 0.3


def compute(stats: StatisticsReport, corr: CorrelationReport) -> HypothesisReport:
    hypotheses: list[Hypothesis] = []
    inconclusive: list[str] = []

    # 1) Hipótesis por cohorte: compara categorías de una misma faceta.
    seen: set[str] = set()
    for cs in stats.cohorts:
        if cs.name in seen:
            continue
        seen.add(cs.name)
        group = [c for c in stats.cohorts if c.name == cs.name]
        real = [c for c in group if c.category != "unknown" and c.can_conclude]
        if len(real) < 2:
            inconclusive.append(
                f"{cs.name}: sin contraste concluyente entre categorías "
                f"(n por categoría insuficiente o falta variación)")
            continue
        # toma las dos categorías con mayor n como ejemplo de comparación
        real_sorted = sorted(real, key=lambda x: x.n, reverse=True)
        a, b = real_sorted[0], real_sorted[1]
        delta_wr = a.win_rate - b.win_rate
        delta_pf = a.pf - b.pf
        strong = abs(delta_wr) >= 0.15 or (a.pf != float("inf") and b.pf != float("inf")
                                           and abs(delta_pf) >= 0.5)
        conf = _conf_from(strong, a.can_conclude and b.can_conclude)
        stmt = (f"La cohorte '{cs.name}={a.category}' se comporta distinto a "
                f"'{cs.name}={b.category}' en resultado.")
        ev_for = (f"{a.category}: WR={a.win_rate:.2f} PF={a.pf:.2f} "
                  f"(n={a.n}, IC95 [{a.ci95_low:.2f},{a.ci95_high:.2f}]); "
                  f"{b.category}: WR={b.win_rate:.2f} PF={b.pf:.2f} (n={b.n})")
        ev_against = "Sin evidencia en contra dentro del backtest; muestra fija."
        hypotheses.append(Hypothesis(
            statement=stmt, evidence_for=ev_for, evidence_against=ev_against,
            n=a.n + b.n,
            metrics=f"delta_wr={delta_wr:+.2f}, delta_pf={delta_pf:+.2f}",
            confidence=conf, can_conclude=a.can_conclude and b.can_conclude,
        ))

    # 2) Hipótesis por asociación: cada Association concluyente => hipótesis.
    for a in corr.associations:
        if not a.can_conclude:
            inconclusive.append(
                f"{a.feature}={a.category}: asociación no concluyente "
                f"({a.warn or 'n insuficiente'}); no se formula hipótesis")
            continue
        strong = abs(a.coef) >= STRONG_COEF
        direction = "positiva" if a.coef > 0 else "negativa"
        stmt = (f"{a.feature}={a.category} muestra asociación {direction} con "
                f"{a.outcome} (coef={a.coef:+.2f}).")
        ev_for = (f"coef={a.coef:+.2f} ({a.strength}), n={a.n}, "
                  f"outcome={a.outcome}")
        # busca contraste en stats para evidencia en contra
        coh = _find_cohort(stats, a.feature, a.category)
        ev_against = (f"IC de WR amplio (n={coh.n})" if coh else
                      "Sin contraste estadístico directo en statistics")
        hypotheses.append(Hypothesis(
            statement=stmt, evidence_for=ev_for, evidence_against=ev_against,
            n=a.n, metrics=f"coef={a.coef:+.2f} ({a.strength})",
            confidence=_conf_from(strong, a.can_conclude),
            can_conclude=a.can_conclude,
        ))

    # rank por confianza (high > medium > low), luego n
    rank = {"high": 2, "medium": 1, "low": 0}
    hypotheses.sort(key=lambda h: (rank[h.confidence], h.n), reverse=True)
    return HypothesisReport(hypotheses=hypotheses, inconclusive=inconclusive)
