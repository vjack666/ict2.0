"""Detección determinista de drift para el dominio conocido de IA.

Este módulo es deliberadamente puro: no lee ni escribe archivos, no modifica el
dominio conocido y no recalibra umbrales con datos OOS. El dominio se construye
con una referencia certificada por el llamador y queda congelado en una
representación inmutable. El análisis posterior solo compara filas contra esa
referencia y devuelve un informe reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from typing import Any, Mapping, Sequence


DRIFT_SCHEMA_VERSION = "1.0"
DEFAULT_DIMENSIONS = ("symbol", "tf", "regime", "period")
DEFAULT_BIN_COUNT = 10
_MISSING = "__MISSING__"
_OTHER = "__OTHER__"


class DriftError(ValueError):
    """Entrada inválida o contrato de drift inconsistente."""


class DriftStatus:
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    ABSTAIN = "ABSTAIN"


@dataclass(frozen=True, slots=True)
class DriftThresholds:
    """Umbrales inmutables usados por un dominio y sus informes."""

    warning: float = 0.10
    abstain: float = 0.25
    min_group_rows: int = 1
    epsilon: float = 1e-9

    def __post_init__(self) -> None:
        if not (math.isfinite(self.warning) and math.isfinite(self.abstain)):
            raise DriftError("los umbrales deben ser finitos")
        if self.warning < 0 or self.abstain <= self.warning:
            raise DriftError("se requiere 0 <= warning < abstain")
        if not isinstance(self.min_group_rows, int) or self.min_group_rows < 1:
            raise DriftError("min_group_rows debe ser entero positivo")
        if not math.isfinite(self.epsilon) or self.epsilon <= 0:
            raise DriftError("epsilon debe ser positivo y finito")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "DriftThresholds":
        if not isinstance(payload, Mapping):
            raise DriftError("thresholds debe ser un objeto")
        return cls(
            warning=float(payload.get("warning", 0.10)),
            abstain=float(payload.get("abstain", 0.25)),
            min_group_rows=int(payload.get("min_group_rows", 1)),
            epsilon=float(payload.get("epsilon", 1e-9)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "warning": self.warning,
            "abstain": self.abstain,
            "min_group_rows": self.min_group_rows,
            "epsilon": self.epsilon,
        }


@dataclass(frozen=True, slots=True)
class VariableDomain:
    """Distribución de referencia congelada para una feature o label."""

    name: str
    kind: str
    count: int
    missing_rate: float
    distribution: tuple[float, ...]
    bins: tuple[float, ...] = ()
    categories: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name or self.kind not in {"numeric", "categorical"}:
            raise DriftError("VariableDomain inválido")
        if self.count < 1 or not 0 <= self.missing_rate <= 1:
            raise DriftError("conteo o missing_rate inválido")
        if not self.distribution or abs(sum(self.distribution) - 1.0) > 1e-8:
            raise DriftError("distribution debe sumar 1")
        if self.kind == "numeric" and len(self.bins) < 2:
            raise DriftError("una variable numérica requiere bins")
        if self.kind == "categorical" and not self.categories:
            raise DriftError("una variable categórica requiere categorías")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "kind": self.kind,
            "count": self.count,
            "missing_rate": self.missing_rate,
            "distribution": list(self.distribution),
        }
        if self.kind == "numeric":
            payload["bins"] = list(self.bins)
        else:
            payload["categories"] = list(self.categories)
        return payload


@dataclass(frozen=True, slots=True)
class DomainSlice:
    """Referencia congelada para un único valor de segmentación."""

    scope: tuple[tuple[str, str], ...]
    features: tuple[VariableDomain, ...]
    labels: tuple[VariableDomain, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": dict(self.scope),
            "features": [v.to_dict() for v in self.features],
            "labels": [v.to_dict() for v in self.labels],
        }


@dataclass(frozen=True, slots=True)
class KnownDomain:
    """Representación serializable e inmutable del dominio conocido."""

    features: tuple[VariableDomain, ...]
    labels: tuple[VariableDomain, ...]
    slices: tuple[DomainSlice, ...] = ()
    dimensions: tuple[str, ...] = DEFAULT_DIMENSIONS
    thresholds: DriftThresholds = DriftThresholds()
    source_id: str = "reference"
    schema_version: str = DRIFT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != DRIFT_SCHEMA_VERSION:
            raise DriftError("schema_version de drift no soportada")
        if not self.features:
            raise DriftError("el dominio requiere al menos una feature")
        names = [v.name for v in self.features + self.labels]
        if len(names) != len(set(names)):
            raise DriftError("features y labels no pueden repetir nombres")
        if len(set(self.dimensions)) != len(self.dimensions):
            raise DriftError("dimensions contiene duplicados")
        if any(not isinstance(d, str) or not d.strip() for d in self.dimensions):
            raise DriftError("dimensions debe contener textos no vacíos")
        scopes = [slice_.scope for slice_ in self.slices]
        if len(scopes) != len(set(scopes)):
            raise DriftError("slices contiene scopes duplicados")

    @property
    def domain_id(self) -> str:
        return _digest(self.to_dict(include_id=False))

    @property
    def feature_names(self) -> tuple[str, ...]:
        return tuple(v.name for v in self.features)

    @property
    def label_names(self) -> tuple[str, ...]:
        return tuple(v.name for v in self.labels)

    def to_dict(self, *, include_id: bool = True) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "source_id": self.source_id,
            "dimensions": list(self.dimensions),
            "thresholds": self.thresholds.to_dict(),
            "features": [v.to_dict() for v in self.features],
            "labels": [v.to_dict() for v in self.labels],
            "slices": [slice_.to_dict() for slice_ in self.slices],
        }
        if include_id:
            payload["domain_id"] = self.domain_id
        return payload

    @classmethod
    def from_reference(
        cls,
        rows: Sequence[Mapping[str, Any]],
        feature_names: Sequence[str],
        *,
        label_names: Sequence[str] = (),
        dimensions: Sequence[str] = DEFAULT_DIMENSIONS,
        thresholds: DriftThresholds | Mapping[str, Any] | None = None,
        source_id: str = "reference",
        bin_count: int = DEFAULT_BIN_COUNT,
    ) -> "KnownDomain":
        return build_known_domain(
            rows,
            feature_names,
            label_names=label_names,
            dimensions=dimensions,
            thresholds=thresholds,
            source_id=source_id,
            bin_count=bin_count,
        )


@dataclass(frozen=True, slots=True)
class DriftMetric:
    name: str
    variable_type: str
    count: int
    missing_rate: float
    drift_score: float
    status: str
    reference_distribution: tuple[float, ...]
    observed_distribution: tuple[float, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "variable_type": self.variable_type,
            "count": self.count,
            "missing_rate": self.missing_rate,
            "drift_score": self.drift_score,
            "status": self.status,
            "reference_distribution": list(self.reference_distribution),
            "observed_distribution": list(self.observed_distribution),
        }


@dataclass(frozen=True, slots=True)
class DriftGroup:
    scope: tuple[tuple[str, str], ...]
    row_count: int
    feature_metrics: tuple[DriftMetric, ...]
    label_metrics: tuple[DriftMetric, ...]
    status: str

    @property
    def scope_dict(self) -> dict[str, str]:
        return dict(self.scope)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope_dict,
            "row_count": self.row_count,
            "status": self.status,
            "features": [m.to_dict() for m in self.feature_metrics],
            "labels": [m.to_dict() for m in self.label_metrics],
        }


@dataclass(frozen=True, slots=True)
class DriftReport:
    domain_id: str
    row_count: int
    status: str
    thresholds: DriftThresholds
    groups: tuple[DriftGroup, ...]
    schema_version: str = DRIFT_SCHEMA_VERSION

    @property
    def report_id(self) -> str:
        return _digest(self.to_dict(include_id=False))

    def to_dict(self, *, include_id: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "domain_id": self.domain_id,
            "row_count": self.row_count,
            "status": self.status,
            "thresholds": self.thresholds.to_dict(),
            "groups": [g.to_dict() for g in self.groups],
        }
        if include_id:
            payload["report_id"] = self.report_id
        return payload

    def to_json(self) -> str:
        return _canonical_json(self.to_dict())


def build_known_domain(
    rows: Sequence[Mapping[str, Any]],
    feature_names: Sequence[str],
    *,
    label_names: Sequence[str] = (),
    dimensions: Sequence[str] = DEFAULT_DIMENSIONS,
    thresholds: DriftThresholds | Mapping[str, Any] | None = None,
    source_id: str = "reference",
    bin_count: int = DEFAULT_BIN_COUNT,
) -> KnownDomain:
    """Construye una referencia congelada sin conservar filas ni usar OOS."""

    normalized = _rows(rows)
    if not normalized:
        raise DriftError("el dominio requiere filas de referencia")
    features = _variable_domains(normalized, feature_names, bin_count)
    labels = _variable_domains(normalized, label_names, bin_count, allow_empty=True)
    threshold_obj = _coerce_thresholds(thresholds)
    dims = tuple(dict.fromkeys(str(d).strip() for d in dimensions))
    if not source_id or not isinstance(source_id, str):
        raise DriftError("source_id debe ser texto no vacío")
    slices: list[DomainSlice] = []
    for dimension in dims:
        values = sorted({_dimension_value(row.get(dimension, _MISSING)) for row in normalized})
        for value in values:
            scoped_rows = tuple(
                row for row in normalized if _dimension_value(row.get(dimension, _MISSING)) == value
            )
            try:
                scoped_features = _variable_domains(scoped_rows, feature_names, bin_count)
            except DriftError:
                # Si una feature no existe en un segmento, el análisis usa la
                # referencia global para ese segmento en lugar de inventarla.
                continue
            scoped_labels = _variable_domains(scoped_rows, label_names, bin_count, allow_empty=True)
            slices.append(DomainSlice(((dimension, value),), scoped_features, scoped_labels))
    return KnownDomain(
        features=features,
        labels=labels,
        slices=tuple(slices),
        dimensions=dims,
        thresholds=threshold_obj,
        source_id=source_id.strip(),
    )


def analyze_drift(
    domain: KnownDomain,
    observed_rows: Sequence[Mapping[str, Any]],
    *,
    thresholds: DriftThresholds | Mapping[str, Any] | None = None,
) -> DriftReport:
    """Compara observaciones contra ``domain`` y devuelve un informe estable.

    ``thresholds`` solo se acepta si coincide exactamente con los umbrales
    congelados en el dominio; nunca se aprende o recalibra desde observaciones.
    """

    if not isinstance(domain, KnownDomain):
        raise DriftError("domain debe ser KnownDomain")
    selected = domain.thresholds if thresholds is None else _coerce_thresholds(thresholds)
    if selected != domain.thresholds:
        raise DriftError("los umbrales del dominio están congelados")
    rows = _rows(observed_rows)
    groups = _make_groups(rows, domain.dimensions)
    if not rows:
        groups = [([], [])]
    built: list[DriftGroup] = []
    for scope, scoped_rows in groups:
        reference = next((slice_ for slice_ in domain.slices if slice_.scope == tuple(scope)), None)
        reference_features = reference.features if reference is not None else domain.features
        reference_labels = reference.labels if reference is not None else domain.labels
        feature_metrics = tuple(_measure(v, scoped_rows, selected) for v in reference_features)
        label_metrics = tuple(
            _measure(v, scoped_rows, selected, is_label=True)
            for v in reference_labels
            if any(_present(row, v.name) for row in scoped_rows)
        )
        statuses = [m.status for m in feature_metrics + label_metrics]
        if len(scoped_rows) < selected.min_group_rows:
            group_status = DriftStatus.ABSTAIN
        else:
            group_status = _worst_status(statuses) if statuses else DriftStatus.NORMAL
        built.append(
            DriftGroup(
                scope=tuple(scope),
                row_count=len(scoped_rows),
                feature_metrics=feature_metrics,
                label_metrics=label_metrics,
                status=group_status,
            )
        )
    built.sort(key=lambda group: (0 if not group.scope else 1, _canonical_json(group.scope_dict)))
    overall = DriftStatus.ABSTAIN if not rows else _worst_status([g.status for g in built])
    return DriftReport(
        domain_id=domain.domain_id,
        row_count=len(rows),
        status=overall,
        thresholds=selected,
        groups=tuple(built),
    )


# Aliases make the intent discoverable without introducing another mutable API.
create_known_domain = build_known_domain
compute_drift = analyze_drift


def _variable_domains(
    rows: tuple[Mapping[str, Any], ...],
    names: Sequence[str],
    bin_count: int,
    *,
    allow_empty: bool = False,
) -> tuple[VariableDomain, ...]:
    if not isinstance(names, Sequence) or isinstance(names, (str, bytes)):
        raise DriftError("los nombres deben ser una secuencia")
    if not isinstance(bin_count, int) or bin_count < 2:
        raise DriftError("bin_count debe ser entero >= 2")
    result: list[VariableDomain] = []
    for raw_name in names:
        name = _name(raw_name)
        values = [row[name] for row in rows if _present(row, name)]
        if not values:
            if allow_empty:
                continue
            raise DriftError(f"la variable de referencia no tiene valores: {name}")
        kind = "numeric" if all(_number(value) for value in values) else "categorical"
        missing_rate = (len(rows) - len(values)) / len(rows)
        if kind == "numeric":
            numeric = [float(value) for value in values]
            bins = _numeric_bins(numeric, bin_count)
            counts = _numeric_counts(numeric, bins)
            result.append(VariableDomain(name, kind, len(rows), missing_rate, _proportions(counts), bins=bins))
        else:
            categories = tuple(sorted({_category(value) for value in values}))
            counts = [_category_count(values, category) for category in categories]
            result.append(
                VariableDomain(
                    name,
                    kind,
                    len(rows),
                    missing_rate,
                    _proportions(counts),
                    categories=categories,
                )
            )
    return tuple(result)


def _measure(variable: VariableDomain, rows: Sequence[Mapping[str, Any]], thresholds: DriftThresholds, *, is_label: bool = False) -> DriftMetric:
    values = [row[variable.name] for row in rows if _present(row, variable.name)]
    if variable.kind == "numeric":
        valid_values = [float(v) for v in values if _number(v)]
        missing_rate = (len(rows) - len(valid_values)) / len(rows) if rows else 1.0
        observed = _proportions(_numeric_counts(valid_values, variable.bins))
    else:
        missing_rate = (len(rows) - len(values)) / len(rows) if rows else 1.0
        observed = _proportions(
            [_category_count(values, category) for category in variable.categories]
            + [_category_count(values, _OTHER, known=variable.categories)]
        )
    reference = list(variable.distribution)
    if variable.kind == "categorical":
        # The reference has an implicit zero-mass OTHER bucket.
        reference.append(0.0)
    observed = _with_missing(observed, variable.missing_rate, missing_rate)
    reference = _with_missing(reference, variable.missing_rate, variable.missing_rate)
    score = _psi(reference, observed, thresholds.epsilon)
    status = _status(score, thresholds)
    return DriftMetric(variable.name, "label" if is_label else "feature", len(rows), missing_rate, score, status, tuple(reference), tuple(observed))


def _with_missing(distribution: Sequence[float], reference_missing: float, observed_missing: float) -> list[float]:
    base_ref = max(1.0 - reference_missing, 0.0)
    base_obs = max(1.0 - observed_missing, 0.0)
    return [float(value) * base_ref for value in distribution] + [observed_missing if observed_missing >= 0 else 0.0]


def _psi(reference: Sequence[float], observed: Sequence[float], epsilon: float) -> float:
    score = 0.0
    for ref, obs in zip(reference, observed):
        safe_ref = max(float(ref), epsilon)
        safe_obs = max(float(obs), epsilon)
        score += (safe_obs - safe_ref) * math.log(safe_obs / safe_ref)
    return float(score)


def _status(score: float, thresholds: DriftThresholds) -> str:
    if score >= thresholds.abstain:
        return DriftStatus.ABSTAIN
    if score >= thresholds.warning:
        return DriftStatus.WARNING
    return DriftStatus.NORMAL


def _worst_status(statuses: Sequence[str]) -> str:
    order = {DriftStatus.NORMAL: 0, DriftStatus.WARNING: 1, DriftStatus.ABSTAIN: 2}
    return max(statuses, key=lambda value: order[value]) if statuses else DriftStatus.NORMAL


def _make_groups(rows: tuple[Mapping[str, Any], ...], dimensions: Sequence[str]) -> list[tuple[list[tuple[str, str]], list[Mapping[str, Any]]]]:
    groups: list[tuple[list[tuple[str, str]], list[Mapping[str, Any]]]] = [([], list(rows))]
    for dimension in dimensions:
        values: dict[str, list[Mapping[str, Any]]] = {}
        for row in rows:
            value = _dimension_value(row.get(dimension, _MISSING))
            values.setdefault(value, []).append(row)
        for value in sorted(values):
            groups.append(([(dimension, value)], values[value]))
    return groups


def _rows(rows: Sequence[Mapping[str, Any]]) -> tuple[Mapping[str, Any], ...]:
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        raise DriftError("rows debe ser una secuencia de objetos")
    normalized = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise DriftError("cada fila debe ser un objeto")
        normalized.append(dict(row))
    return tuple(normalized)


def _present(row: Mapping[str, Any], name: str) -> bool:
    value = row.get(name, None)
    return value is not None


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _numeric_bins(values: Sequence[float], bin_count: int) -> tuple[float, ...]:
    low, high = min(values), max(values)
    if low == high:
        return (low - 0.5, high + 0.5)
    return tuple(low + (high - low) * i / bin_count for i in range(bin_count + 1))


def _numeric_counts(values: Sequence[float], bins: Sequence[float]) -> list[int]:
    counts = [0] * (len(bins) - 1)
    for value in values:
        index = next((i for i in range(len(bins) - 1) if value < bins[i + 1]), len(counts) - 1)
        counts[index] += 1
    return counts


def _category(value: Any) -> str:
    if isinstance(value, str):
        return value
    return _canonical_json(value)


def _category_count(values: Sequence[Any], category: str, *, known: Sequence[str] = ()) -> int:
    if category == _OTHER:
        return sum(_category(value) not in known for value in values)
    return sum(_category(value) == category for value in values)


def _proportions(counts: Sequence[int]) -> list[float]:
    total = sum(counts)
    return [count / total if total else 0.0 for count in counts]


def _dimension_value(value: Any) -> str:
    if value is None:
        return _MISSING
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return _canonical_json(value)


def _name(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DriftError("los nombres deben ser textos no vacíos")
    return value.strip()


def _coerce_thresholds(value: DriftThresholds | Mapping[str, Any] | None) -> DriftThresholds:
    if value is None:
        return DriftThresholds()
    if isinstance(value, DriftThresholds):
        return value
    return DriftThresholds.from_mapping(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return sha256(_canonical_json(value).encode("utf-8")).hexdigest()


__all__ = [
    "DRIFT_SCHEMA_VERSION",
    "DriftError",
    "DriftStatus",
    "DriftThresholds",
    "VariableDomain",
    "DomainSlice",
    "KnownDomain",
    "DriftMetric",
    "DriftGroup",
    "DriftReport",
    "build_known_domain",
    "create_known_domain",
    "analyze_drift",
    "compute_drift",
]
