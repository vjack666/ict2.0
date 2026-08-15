"""Fase E — diagnosis_report.py (ORQUESTADOR PURO, sin lógica de trading).

Único módulo que encadena los 3 motores de análisis. No decide nada: solo
pasa los TradeContext v2 a cada motor en orden y devuelve los reportes.

Cadena: TradeContext* -> Statistics -> Correlation -> Hypothesis -> Report

Separación (Ruben):
- NO importa engine/sequence/canonical (el motor de ejecución no cambia).
- NO filtra, NO scored, NO selecciona "mejor" hipótesis.
- Los motores ya aplican sus propias reglas (n<MIN_N => can_conclude=False).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ict_backtest.diagnostics.trade_context import TradeContext
from ict_backtest.diagnostics.statistics_engine import compute as stats_compute, StatisticsReport
from ict_backtest.diagnostics.correlation_engine import compute as corr_compute, CorrelationReport
from ict_backtest.diagnostics.hypothesis_engine import compute as hypo_compute, HypothesisReport


@dataclass(frozen=True)
class DiagnosisReport:
    statistics: StatisticsReport
    correlation: CorrelationReport
    hypothesis: HypothesisReport


def run(contexts: Sequence[TradeContext]) -> DiagnosisReport:
    """Orquesta statistics -> correlation -> hypothesis.

    Solo lectura de contexts. Sin lógica de trading. Devuelve los 3 reportes.
    """
    stats = stats_compute(contexts)
    corr = corr_compute(contexts, outcome="win")
    hypo = hypo_compute(stats, corr)
    return DiagnosisReport(statistics=stats, correlation=corr, hypothesis=hypo)
