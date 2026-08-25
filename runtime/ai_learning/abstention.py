"""Contrato determinista y advisory para confianza y abstención de INF-7.

Este módulo clasifica la calidad de una evaluación en ``ACCEPT``, ``REVIEW``
o ``ABSTAIN``. No interpreta esos estados como compra, venta, orden, sesgo ni
permiso operativo. La ausencia de información válida siempre cierra el flujo
en ``ABSTAIN``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any


ABSTENTION_SCHEMA_VERSION = "1.0"
DEFAULT_POLICY_VERSION = "INF-7.1"


class DecisionState(str, Enum):
    """Resultado de la política, sin semántica de mercado u operación."""

    ACCEPT = "ACCEPT"
    REVIEW = "REVIEW"
    ABSTAIN = "ABSTAIN"


# Constantes de conveniencia para consumidores que no necesitan importar el enum.
ACCEPT = DecisionState.ACCEPT
REVIEW = DecisionState.REVIEW
ABSTAIN = DecisionState.ABSTAIN


class ReasonCode(str, Enum):
    """Motivos estables y auditables de la clasificación."""

    ACCEPTED_WITHIN_POLICY = "ACCEPTED_WITHIN_POLICY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    MISSING_FEATURES = "MISSING_FEATURES"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    OUT_OF_DOMAIN = "OUT_OF_DOMAIN"
    DOMAIN_UNCERTAIN = "DOMAIN_UNCERTAIN"
    INVALID_INPUT = "INVALID_INPUT"


@dataclass(frozen=True)
class AbstentionResult:
    """Resultado inmutable, serializable y sin autoridad operativa."""

    state: DecisionState
    reasons: tuple[ReasonCode, ...]
    confidence: float | None
    in_domain: bool | None
    missing_features: tuple[str, ...]
    review_threshold: float
    accept_threshold: float
    policy_version: str
    audit_id: str

    @property
    def abstained(self) -> bool:
        return self.state is DecisionState.ABSTAIN

    def to_dict(self) -> dict[str, Any]:
        """Devuelve el registro de auditoría sin añadir decisiones operativas."""

        return {
            "schema_version": ABSTENTION_SCHEMA_VERSION,
            "policy_version": self.policy_version,
            "state": self.state.value,
            "reasons": [reason.value for reason in self.reasons],
            "confidence": self.confidence,
            "in_domain": self.in_domain,
            "missing_features": list(self.missing_features),
            "thresholds": {
                "review": self.review_threshold,
                "accept": self.accept_threshold,
            },
            "audit_id": self.audit_id,
        }


class AbstentionPolicy:
    """Política fail-closed para clasificar una evaluación de modelo.

    ``review_threshold`` separa una confianza insuficiente de una evaluación
    que requiere revisión. ``accept_threshold`` separa revisión de aceptación.
    El dominio debe declararse explícitamente como ``True`` para poder aceptar.
    """

    def __init__(
        self,
        *,
        review_threshold: float = 0.50,
        accept_threshold: float = 0.80,
        policy_version: str = DEFAULT_POLICY_VERSION,
    ) -> None:
        self.review_threshold = _threshold(review_threshold, "review_threshold")
        self.accept_threshold = _threshold(accept_threshold, "accept_threshold")
        if self.review_threshold > self.accept_threshold:
            raise ValueError("review_threshold no puede superar accept_threshold")
        if not isinstance(policy_version, str) or not policy_version.strip():
            raise ValueError("policy_version debe ser texto no vacío")
        self.policy_version = policy_version.strip()

    def evaluate(
        self,
        features: Mapping[str, Any] | None,
        confidence: float | int | None,
        in_domain: bool | None,
        *,
        required_features: Sequence[str] = (),
    ) -> AbstentionResult:
        """Clasifica una evaluación; entradas inválidas producen ``ABSTAIN``.

        Solo se inspeccionan presencia y validez de features, confianza y
        dominio. La función no recibe ni devuelve una dirección de mercado.
        """

        normalized_required, required_error = _required_features(required_features)
        normalized_confidence, confidence_error = _confidence(confidence)
        normalized_features, feature_error = _features(features)
        if isinstance(in_domain, bool):
            domain_error = None
        elif in_domain is None:
            domain_error = ReasonCode.DOMAIN_UNCERTAIN
        else:
            domain_error = ReasonCode.INVALID_INPUT

        invalid = required_error or confidence_error or feature_error
        if domain_error is ReasonCode.INVALID_INPUT:
            invalid = ReasonCode.INVALID_INPUT
        if invalid is not None:
            return self._result(
                DecisionState.ABSTAIN,
                (ReasonCode.INVALID_INPUT,),
                normalized_confidence,
                in_domain if isinstance(in_domain, bool) else None,
                (),
            )

        missing = tuple(
            name for name in normalized_required
            if name not in normalized_features or normalized_features[name] is None
        )
        reasons: list[ReasonCode] = []
        if missing:
            reasons.append(ReasonCode.MISSING_FEATURES)
        if in_domain is False:
            reasons.append(ReasonCode.OUT_OF_DOMAIN)
        elif domain_error is not None:
            reasons.append(domain_error)
        if normalized_confidence is None or normalized_confidence < self.review_threshold:
            reasons.append(ReasonCode.LOW_CONFIDENCE)

        if reasons:
            state = DecisionState.ABSTAIN
        elif normalized_confidence < self.accept_threshold:
            state = DecisionState.REVIEW
            reasons.append(ReasonCode.REVIEW_REQUIRED)
        else:
            state = DecisionState.ACCEPT
            reasons.append(ReasonCode.ACCEPTED_WITHIN_POLICY)

        return self._result(
            state,
            tuple(reasons),
            normalized_confidence,
            in_domain if isinstance(in_domain, bool) else None,
            missing,
        )

    def _result(
        self,
        state: DecisionState,
        reasons: tuple[ReasonCode, ...],
        confidence: float | None,
        in_domain: bool | None,
        missing_features: tuple[str, ...],
    ) -> AbstentionResult:
        payload = {
            "schema_version": ABSTENTION_SCHEMA_VERSION,
            "policy_version": self.policy_version,
            "state": state.value,
            "reasons": [reason.value for reason in reasons],
            "confidence": confidence,
            "in_domain": in_domain,
            "missing_features": list(missing_features),
            "thresholds": {
                "review": self.review_threshold,
                "accept": self.accept_threshold,
            },
        }
        audit_id = hashlib.sha256(_canonical_json(payload)).hexdigest()
        return AbstentionResult(
            state=state,
            reasons=reasons,
            confidence=confidence,
            in_domain=in_domain,
            missing_features=missing_features,
            review_threshold=self.review_threshold,
            accept_threshold=self.accept_threshold,
            policy_version=self.policy_version,
            audit_id=audit_id,
        )


def evaluate_abstention(
    features: Mapping[str, Any] | None,
    confidence: float | int | None,
    in_domain: bool | None,
    *,
    required_features: Sequence[str] = (),
    review_threshold: float = 0.50,
    accept_threshold: float = 0.80,
    policy_version: str = DEFAULT_POLICY_VERSION,
) -> AbstentionResult:
    """Atajo determinista para evaluar una entrada con una política explícita."""

    try:
        policy = AbstentionPolicy(
            review_threshold=review_threshold,
            accept_threshold=accept_threshold,
            policy_version=policy_version,
        )
    except (TypeError, ValueError):
        # Una configuración no válida nunca puede abrir el flujo.
        return _fail_closed_result(
            confidence=confidence,
            policy_version=policy_version,
            reason=ReasonCode.INVALID_INPUT,
        )
    return policy.evaluate(
        features,
        confidence,
        in_domain,
        required_features=required_features,
    )


# Nombre alternativo explícito para consumidores que prefieren "assess".
assess_abstention = evaluate_abstention
AbstentionState = DecisionState
AbstentionReason = ReasonCode


def _threshold(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} debe ser numérico")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} debe ser numérico") from None
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"{name} fuera de [0, 1]")
    return number


def _confidence(value: Any) -> tuple[float | None, ReasonCode | None]:
    if isinstance(value, bool) or value is None:
        return None, ReasonCode.INVALID_INPUT
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, ReasonCode.INVALID_INPUT
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        return None, ReasonCode.INVALID_INPUT
    return number, None


def _required_features(value: Any) -> tuple[tuple[str, ...], ReasonCode | None]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return (), ReasonCode.INVALID_INPUT
    names: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip() or item.strip() in names:
            return (), ReasonCode.INVALID_INPUT
        names.append(item.strip())
    return tuple(names), None


def _features(value: Any) -> tuple[Mapping[str, Any], ReasonCode | None]:
    if not isinstance(value, Mapping):
        return {}, ReasonCode.INVALID_INPUT
    for name, item in value.items():
        if not isinstance(name, str) or not name.strip():
            return {}, ReasonCode.INVALID_INPUT
        if item is not None and isinstance(item, (bool, str, bytes)):
            continue
        if item is not None:
            try:
                if not math.isfinite(float(item)):
                    return {}, ReasonCode.INVALID_INPUT
            except (TypeError, ValueError):
                return {}, ReasonCode.INVALID_INPUT
    return value, None


def _fail_closed_result(
    *, confidence: Any, policy_version: Any, reason: ReasonCode
) -> AbstentionResult:
    normalized_confidence, _ = _confidence(confidence)
    version = policy_version.strip() if isinstance(policy_version, str) and policy_version.strip() else "INVALID"
    payload = {
        "schema_version": ABSTENTION_SCHEMA_VERSION,
        "policy_version": version,
        "state": DecisionState.ABSTAIN.value,
        "reasons": [reason.value],
        "confidence": normalized_confidence,
        "in_domain": None,
        "missing_features": [],
        "thresholds": {"review": None, "accept": None},
    }
    return AbstentionResult(
        state=DecisionState.ABSTAIN,
        reasons=(reason,),
        confidence=normalized_confidence,
        in_domain=None,
        missing_features=(),
        review_threshold=0.0,
        accept_threshold=0.0,
        policy_version=version,
        audit_id=hashlib.sha256(_canonical_json(payload)).hexdigest(),
    )


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
