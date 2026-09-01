from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .base import AnalysisResult


@dataclass
class DecisionConfig:
    ict_weight: float = 0.35
    wyckoff_weight: float = 0.30
    structure_weight: float = 0.20
    ml_weight: float = 0.15
    min_combined_confidence: float = 0.55
    conflict_penalty: float = 0.15
    # Item F: "soft" = resta conflict_penalty a la confianza (actual);
    # "hard" = fuerza NEUTRAL/confianza 0.0 si ICT y Wyckoff contradicen
    conflict_mode: str = "soft"


@dataclass
class DecisionRecord:
    final_bias: str = "NEUTRAL"
    confidence: float = 0.0

    ict_bias: str | None = None
    ict_confidence: float = 0.0
    ict_weighted_contribution: float = 0.0

    wyckoff_bias: str | None = None
    wyckoff_confidence: float = 0.0
    wyckoff_weighted_contribution: float = 0.0

    structure_bias: str | None = None
    structure_confidence: float = 0.0
    structure_weighted_contribution: float = 0.0

    ml_probability: float | None = None
    ml_weighted_contribution: float = 0.0

    weighted_bias_sum: float = 0.0
    total_weight: float = 0.0
    conflict_penalty_applied: float = 0.0
    explanation_reasons: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_bias": self.final_bias,
            "confidence": self.confidence,
            "ict_bias": self.ict_bias,
            "ict_confidence": self.ict_confidence,
            "ict_weighted_contribution": self.ict_weighted_contribution,
            "wyckoff_bias": self.wyckoff_bias,
            "wyckoff_confidence": self.wyckoff_confidence,
            "wyckoff_weighted_contribution": self.wyckoff_weighted_contribution,
            "structure_bias": self.structure_bias,
            "structure_confidence": self.structure_confidence,
            "structure_weighted_contribution": self.structure_weighted_contribution,
            "ml_probability": self.ml_probability,
            "ml_weighted_contribution": self.ml_weighted_contribution,
            "weighted_bias_sum": self.weighted_bias_sum,
            "total_weight": self.total_weight,
            "conflict_penalty_applied": self.conflict_penalty_applied,
            "explanation_reasons": "; ".join(self.explanation_reasons),
            "conflicts": "; ".join(self.conflicts),
        }


class DecisionAgent:
    name: str = "DECISION"

    def __init__(self, config: DecisionConfig | None = None) -> None:
        self.config = config or DecisionConfig()

    def analyze(self, context: pd.DataFrame, index: int) -> AnalysisResult:
        row = context.iloc[index] if index < len(context) else None
        if row is None:
            return AnalysisResult(
                agent_name="DECISION",
                bias="NEUTRAL",
                confidence=0.0,
                detected_events=[],
                evidence={},
                invalidation_conditions=[],
            )

        ict_bias = str(row.get("agent_ict_bias", "NEUTRAL"))
        ict_conf = float(row.get("agent_ict_confidence", 0.0))
        ict_events_str = str(row.get("agent_ict_events", ""))
        ict_events = [{"type": e.strip()} for e in ict_events_str.split(",") if e.strip()] if ict_events_str else []
        ict_result = AnalysisResult(
            agent_name="ICT",
            bias=ict_bias,
            confidence=ict_conf,
            detected_events=ict_events,
        )

        wyckoff_bias = str(row.get("agent_wyckoff_bias", "NEUTRAL"))
        wyckoff_conf = float(row.get("agent_wyckoff_confidence", 0.0))
        wyckoff_events_str = str(row.get("agent_wyckoff_events", ""))
        wyckoff_events = [{"type": e.strip()} for e in wyckoff_events_str.split(",") if e.strip()] if wyckoff_events_str else []
        wyckoff_result = AnalysisResult(
            agent_name="WYCKOFF",
            bias=wyckoff_bias,
            confidence=wyckoff_conf,
            detected_events=wyckoff_events,
        )

        structure_bias = str(row.get("agent_structure_bias", "NEUTRAL"))
        structure_conf = float(row.get("agent_structure_confidence", 0.0))
        structure_events_str = str(row.get("agent_structure_events", ""))
        structure_events = [{"type": e.strip()} for e in structure_events_str.split(",") if e.strip()] if structure_events_str else []
        structure_result = AnalysisResult(
            agent_name="STRUCTURE",
            bias=structure_bias,
            confidence=structure_conf,
            detected_events=structure_events,
        )

        result, _ = self.decide(
            ict=ict_result,
            wyckoff=wyckoff_result,
            structure=structure_result,
            ml_probability=None,
        )
        return result

    def decide(
        self,
        ict: AnalysisResult | None = None,
        wyckoff: AnalysisResult | None = None,
        structure: AnalysisResult | None = None,
        ml_probability: float | None = None,
    ) -> tuple[AnalysisResult, DecisionRecord]:
        record = DecisionRecord()
        inputs: dict[str, Any] = {}
        total_weight = 0.0
        weighted_bias_sum = 0.0
        weighted_conf_sum = 0.0
        all_events: list[dict[str, Any]] = []
        reasons: list[str] = []
        conflicts: list[str] = []

        agents_info = [
            ("ICT", ict, self.config.ict_weight),
            ("WYCKOFF", wyckoff, self.config.wyckoff_weight),
            ("STRUCTURE", structure, self.config.structure_weight),
        ]

        bias_map = {"BULLISH": 1.0, "NEUTRAL": 0.0, "BEARISH": -1.0}

        for name, result, weight in agents_info:
            if result is None or result.confidence <= 0.0:
                continue

            inputs[name] = {"bias": result.bias, "confidence": result.confidence}
            total_weight += weight
            bias_val = bias_map.get(result.bias, 0.0)
            contribution = bias_val * weight * result.confidence
            weighted_bias_sum += contribution
            weighted_conf_sum += result.confidence * weight
            all_events.extend(result.detected_events)

            if name == "ICT":
                record.ict_bias = result.bias
                record.ict_confidence = result.confidence
                record.ict_weighted_contribution = round(contribution, 4)
            elif name == "WYCKOFF":
                record.wyckoff_bias = result.bias
                record.wyckoff_confidence = result.confidence
                record.wyckoff_weighted_contribution = round(contribution, 4)
            elif name == "STRUCTURE":
                record.structure_bias = result.bias
                record.structure_confidence = result.confidence
                record.structure_weighted_contribution = round(contribution, 4)

            if result.detected_events:
                reasons.append(f"{name}: {', '.join(e['type'] for e in result.detected_events[:3])}")

        if ml_probability is not None and 0.0 <= ml_probability <= 1.0:
            inputs["ML"] = {"probability": ml_probability}
            total_weight += self.config.ml_weight
            ml_bias = 1.0 if ml_probability >= 0.5 else -1.0
            ml_contribution = ml_bias * ml_probability * self.config.ml_weight
            weighted_bias_sum += ml_contribution
            weighted_conf_sum += ml_probability * self.config.ml_weight
            record.ml_probability = ml_probability
            record.ml_weighted_contribution = round(ml_contribution, 4)
            reasons.append(f"ML: probability {ml_probability:.2f}")

        record.weighted_bias_sum = round(weighted_bias_sum, 4)
        record.total_weight = round(total_weight, 4)

        if total_weight <= 0.0:
            return AnalysisResult(
                agent_name="DECISION",
                bias="NEUTRAL",
                confidence=0.0,
                detected_events=[],
                evidence={"inputs": inputs, "reason": "no agent data"},
                invalidation_conditions=[],
            ), record

        combined_bias_val = weighted_bias_sum / total_weight
        combined_confidence = weighted_conf_sum / total_weight

        biases = [r.bias for r in [ict, wyckoff, structure] if r is not None and r.confidence > 0.0]
        if len(set(b for b in biases if b != "NEUTRAL")) > 1:
            conflicts.append(f"conflict: {', '.join(biases)}")
            if self.config.conflict_mode == "hard":
                # Veto duro: senal NEUTRAL, confianza 0.0
                record.conflict_penalty_applied = 1.0
                reasons.append("conflict HARD veto -> NEUTRAL")
            else:
                # Penalizacion suave (comportamiento actual)
                conflict_penalty = self.config.conflict_penalty
                combined_confidence = max(combined_confidence - conflict_penalty, 0.0)
                record.conflict_penalty_applied = conflict_penalty
                reasons.append(f"conflict penalty -{conflict_penalty:.2f}")

        # Aplicar veto duro ANTES de mapear bias final
        hard_veto = self.config.conflict_mode == "hard" and any("HARD veto" in r for r in reasons)
        if hard_veto:
            final_bias = "NEUTRAL"
            combined_confidence = 0.0
        elif combined_bias_val >= 0.15:
            final_bias = "BULLISH"
        elif combined_bias_val <= -0.15:
            final_bias = "BEARISH"
        else:
            final_bias = "NEUTRAL"

        combined_confidence = min(combined_confidence, 0.95)

        record.final_bias = final_bias
        record.confidence = round(combined_confidence, 4)
        record.explanation_reasons = reasons
        record.conflicts = conflicts

        invalidation: list[str] = []
        if combined_confidence < self.config.min_combined_confidence:
            invalidation.append(f"combined confidence {combined_confidence:.2f} below {self.config.min_combined_confidence}")

        decision_events = all_events.copy()
        decision_events.append({
            "type": "DECISION_SUMMARY",
            "combined_confidence": round(combined_confidence, 4),
            "final_bias": final_bias,
        })

        return AnalysisResult(
            agent_name="DECISION",
            bias=final_bias,
            confidence=round(combined_confidence, 4),
            detected_events=decision_events,
            evidence={
                "inputs": inputs,
                "weighted_bias": round(combined_bias_val, 4),
                "reasons": reasons,
                "conflicts": conflicts,
                "ml_probability": ml_probability,
            },
            invalidation_conditions=invalidation,
        ), record
