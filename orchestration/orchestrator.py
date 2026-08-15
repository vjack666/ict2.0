from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from analysis.base import AnalysisResult
from analysis.decision_agent import DecisionAgent, DecisionConfig
from analysis.ict_agent import ICTAgent
from analysis.structure_agent import StructureAgent
from analysis.wyckoff_agent import WyckoffAgent

AGENT_COLUMNS = [
    "agent_ict_bias",
    "agent_ict_confidence",
    "agent_ict_events",
    "agent_wyckoff_bias",
    "agent_wyckoff_confidence",
    "agent_wyckoff_phase",
    "agent_wyckoff_events",
    "agent_wyckoff_spring",
    "agent_wyckoff_upthrust",
    "agent_wyckoff_sos",
    "agent_wyckoff_sow",
    "agent_wyckoff_effort_divergence",
    "agent_wyckoff_stoch_exhaustion",
    "agent_wyckoff_stoch_divergence",
    "agent_structure_bias",
    "agent_structure_confidence",
    "agent_structure_events",
    "agent_decision_bias",
    "agent_decision_confidence",
    "agent_decision_reasons",
    "agent_decision_conflicts",
    "agent_decision_conflict_penalty",
    "agent_decision_ml_probability",
    "agent_decision_weighted_bias_sum",
    "agent_decision_total_weight",
]


class AgentOrchestrator:
    def __init__(
        self,
        ict_agent: ICTAgent | None = None,
        wyckoff_agent: WyckoffAgent | None = None,
        structure_agent: StructureAgent | None = None,
        decision_agent: DecisionAgent | None = None,
    ) -> None:
        self.ict = ict_agent or ICTAgent()
        self.wyckoff = wyckoff_agent or WyckoffAgent()
        self.structure = structure_agent or StructureAgent()
        self.decision = decision_agent or DecisionAgent()

    def analyze_bar(
        self,
        context: pd.DataFrame,
        index: int,
        ml_probability: float | None = None,
    ) -> dict[str, Any]:
        ict_result = self.ict.analyze(context, index)
        wyckoff_result = self.wyckoff.analyze(context, index)
        structure_result = self.structure.analyze(context, index)
        decision_result, decision_record = self.decision.decide(
            ict=ict_result,
            wyckoff=wyckoff_result,
            structure=structure_result,
            ml_probability=ml_probability,
        )

        return {
            "agent_ict_bias": ict_result.bias,
            "agent_ict_confidence": ict_result.confidence,
            "agent_ict_events": _serialise_events(ict_result.detected_events),
            "agent_wyckoff_bias": wyckoff_result.bias,
            "agent_wyckoff_confidence": wyckoff_result.confidence,
            "agent_wyckoff_phase": str(wyckoff_result.evidence.get("phase", "UNKNOWN")),
            "agent_wyckoff_events": _serialise_events(wyckoff_result.detected_events),
            "agent_wyckoff_spring": int(any(e["type"] == "SPRING" for e in wyckoff_result.detected_events)),
            "agent_wyckoff_upthrust": int(any(e["type"] == "UPTHRUST" for e in wyckoff_result.detected_events)),
            "agent_wyckoff_sos": int(any(e["type"] == "SOS" for e in wyckoff_result.detected_events)),
            "agent_wyckoff_sow": int(any(e["type"] == "SOW" for e in wyckoff_result.detected_events)),
            "agent_wyckoff_effort_divergence": int(
                bool(
                    (wyckoff_result.evidence.get("effort_vs_result") or {}).get("divergence", False)
                )
            ),
            "agent_wyckoff_stoch_exhaustion": str(
                (wyckoff_result.evidence.get("stoch_exhaustion") or {}).get("type", "")
            ),
            "agent_wyckoff_stoch_divergence": int(
                bool(
                    (wyckoff_result.evidence.get("stoch_exhaustion") or {}).get("divergence", False)
                )
            ),
            "agent_structure_bias": structure_result.bias,
            "agent_structure_confidence": structure_result.confidence,
            "agent_structure_events": _serialise_events(structure_result.detected_events),
            "agent_decision_bias": decision_result.bias,
            "agent_decision_confidence": decision_result.confidence,
            "agent_decision_reasons": "; ".join(decision_result.evidence.get("reasons", [])),
            "agent_decision_conflicts": "; ".join(decision_result.evidence.get("conflicts", [])),
            "agent_decision_conflict_penalty": decision_record.conflict_penalty_applied,
            "agent_decision_ml_probability": decision_record.ml_probability if decision_record.ml_probability is not None else float("nan"),
            "agent_decision_weighted_bias_sum": decision_record.weighted_bias_sum,
            "agent_decision_total_weight": decision_record.total_weight,
        }

    def analyze_context(
        self,
        context: pd.DataFrame,
        ml_probabilities: np.ndarray | None = None,
        progress_cb: callable = None,
    ) -> pd.DataFrame:
        result = context.copy()
        n = len(result)
        agent_data: list[dict[str, Any]] = [{} for _ in range(n)]

        for i in range(n):
            ml_p = float(ml_probabilities[i]) if ml_probabilities is not None and i < len(ml_probabilities) else None
            agent_data[i] = self.analyze_bar(result, i, ml_probability=ml_p)
            if progress_cb:
                progress_cb(i + 1, n)

        for col in AGENT_COLUMNS:
            result[col] = pd.Series([d.get(col, None) for d in agent_data], index=result.index)

        return result

    def get_agent_confidence(self, context: pd.DataFrame, index: int) -> float:
        row = context.iloc[index] if index < len(context) else None
        if row is None:
            return 0.0
        return float(row.get("agent_decision_confidence", 0.0))

    def get_agent_bias(self, context: pd.DataFrame, index: int) -> str:
        row = context.iloc[index] if index < len(context) else None
        if row is None:
            return "NEUTRAL"
        return str(row.get("agent_decision_bias", "NEUTRAL"))

    def get_agent_reasons(self, context: pd.DataFrame, index: int) -> list[str]:
        row = context.iloc[index] if index < len(context) else None
        if row is None:
            return []
        raw = str(row.get("agent_decision_reasons", ""))
        return [r.strip() for r in raw.split(";") if r.strip()]


def _serialise_events(events: list[dict[str, Any]]) -> str:
    if not events:
        return ""
    parts = [f"{e.get('type', '?')}" for e in events[:5]]
    return ", ".join(parts)
