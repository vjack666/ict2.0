"""Ruta DIAGNOSTIC_ONLY para el primer entrenamiento sobre JSONL causal.

Esta ruta existe para probar el cableado ``JSONL materializado -> split temporal
-> OutcomeClassifier`` sin cruzar la frontera de INF-2. No crea ni acepta un
DatasetSnapshot, no escribe en ModelRegistry/CheckpointStore y nunca concede
autoridad de trading.

Cuando el JSONL alcanza los mínimos mecánicos, se invoca la función real
``train_outcome_classifier`` mediante un adaptador de plan en memoria. La
autorización que se le entrega es un token de compatibilidad *local* marcado
DIAGNOSTIC_ONLY: no es un gate científico, no se publica como
TRAINING_ELIGIBLE y no convierte una fuente bloqueada en certificada.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

from .outcome_classifier import (
    OUTCOME_CLASSES,
    OutcomeClassifierError,
    TrainingAuthorizationError,
    train_outcome_classifier,
)
from .training_pipeline import (
    TRAINING_PIPELINE_SCHEMA_VERSION,
    TemporalSplit,
    TrainingPlan,
)


DIAGNOSTIC_SCHEMA_VERSION = "1.0"
DIAGNOSTIC_ARTIFACT_KIND = "ai_outcome_classifier_diagnostic_only"
DIAGNOSTIC_MODEL_ID = "ICT_OUTCOME_CLASSIFIER_V1_DIAGNOSTIC"
DIAGNOSTIC_MODEL_VERSION = "diagnostic-1.0.0"
DIAGNOSTIC_EXPERIMENT_ID = "EXP-AI-OUTCOME-DIAGNOSTIC-ONLY"
MIN_PARTITION_ROWS = {"train": 30, "validation": 10, "test": 10}
MIN_TOTAL_ROWS = sum(MIN_PARTITION_ROWS.values())
DEFAULT_MIN_CLASS_ROWS = 5
_TARGET_RE = re.compile(r"^label_end_[1-9][0-9]*$")
_FORBIDDEN_FEATURE_PARTS = (
    "label", "outcome", "exit", "future", "pnl", "profit", "return",
    "entry", "stop", "target", "sl", "tp", "bars_held", "result",
)
_TIME_PARTS = ("time", "timestamp", "asof", "available", "observed", "created")


class DiagnosticTrainingError(ValueError):
    """Entrada inválida para la ruta de diagnóstico."""


@dataclass(frozen=True)
class DiagnosticRows:
    rows: tuple[dict[str, Any], ...]
    raw_sha256: str
    schema_hash: str
    source_name: str


class _DiagnosticRegistry:
    """Sólo satisface la lectura de lineage que requiere el clasificador real."""

    def __init__(self, *, code_commit: str):
        self._record = SimpleNamespace(
            git_commit=code_commit,
            experiment_id=DIAGNOSTIC_EXPERIMENT_ID,
        )

    def get_model(self, model_id: str, version: str) -> SimpleNamespace:
        return self._record


class _DiagnosticPipeline:
    """Adaptador sin persistencia para ``train_outcome_classifier``.

    El pipeline INF-4 normal exige DatasetSnapshot certificado. Esta clase no
    lo suplanta: su nombre y el artefacto resultante dejan explícito que es una
    prueba DIAGNOSTIC_ONLY fuera de la frontera científica.
    """

    def __init__(self, plan: TrainingPlan, *, code_commit: str):
        self._plan = plan
        self.registry = _DiagnosticRegistry(code_commit=code_commit)

    def plan(self) -> TrainingPlan:
        return self._plan


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _parse_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise DiagnosticTrainingError(f"{field} debe ser timestamp ISO-8601")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise DiagnosticTrainingError(f"{field} debe ser timestamp ISO-8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _validate_feature_value(value: Any, decision_time: datetime, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).lower()
            if any(part in key_text for part in _FORBIDDEN_FEATURE_PARTS):
                raise DiagnosticTrainingError(
                    f"features_at_t contiene campo futuro/prohibido: {path}.{key}"
                )
            if key_text in {
                "time", "timestamp", "event_time", "observed_time",
                "available_time", "created_at", "as_of", "asof",
            } or any(part in key_text for part in _TIME_PARTS):
                if isinstance(child, str):
                    try:
                        observed = _parse_time(child, f"features_at_t.{path}.{key}")
                    except DiagnosticTrainingError:
                        observed = None
                    if observed is not None and observed > decision_time:
                        raise DiagnosticTrainingError(
                            f"features_at_t contiene tiempo futuro: {path}.{key}"
                        )
            _validate_feature_value(child, decision_time, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate_feature_value(child, decision_time, f"{path}[{index}]")


def _schema_hash(rows: Sequence[Mapping[str, Any]]) -> str:
    columns = sorted({str(key) for row in rows for key in row})
    schema = {"format": "jsonl", "columns": columns}
    return hashlib.sha256(_canonical_json(schema)).hexdigest()


def load_causal_jsonl(path: str | Path, *, target: str) -> DiagnosticRows:
    """Lee y valida el JSONL materializado sin corregir ni completar filas."""

    if not _TARGET_RE.fullmatch(target):
        raise DiagnosticTrainingError("target debe tener formato label_end_N")
    source = Path(path).resolve()
    if source.suffix.lower() not in {".jsonl", ".ndjson"}:
        raise DiagnosticTrainingError("la entrada debe ser JSONL/NDJSON; parquet prohibido")
    try:
        raw = source.read_bytes()
    except OSError as exc:
        raise DiagnosticTrainingError(f"JSONL ilegible: {source}") from exc
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for number, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DiagnosticTrainingError(f"línea JSONL inválida: {number}") from exc
        if not isinstance(value, Mapping):
            raise DiagnosticTrainingError(f"fila {number} no es un objeto")
        row = dict(value)
        if row.get("can_trade") is not False:
            raise DiagnosticTrainingError(f"fila {number}: can_trade debe ser false")
        label = str(row.get(target, "")).lower()
        if label not in OUTCOME_CLASSES:
            raise DiagnosticTrainingError(f"fila {number}: etiqueta {target} inválida")
        event_time = _parse_time(row.get("event_time"), f"fila {number}.event_time")
        if "label_available_time" in row:
            available = _parse_time(
                row["label_available_time"], f"fila {number}.label_available_time"
            )
            if available <= event_time:
                raise DiagnosticTrainingError(
                    f"fila {number}: label_available_time no es posterior a event_time"
                )
        features = row.get("features_at_t")
        if not isinstance(features, Mapping):
            raise DiagnosticTrainingError(f"fila {number}: features_at_t requerido")
        context = features.get("context_inputs")
        sequence = features.get("sequence")
        if not isinstance(context, Mapping) or not isinstance(sequence, (list, tuple)):
            raise DiagnosticTrainingError(
                f"fila {number}: features_at_t causal incompleto"
            )
        required_context = {"sequence_direction", "d1_bias", "h4_location", "h1_alignment"}
        missing = sorted(required_context.difference(context))
        if missing:
            raise DiagnosticTrainingError(
                f"fila {number}: faltan context_inputs: {','.join(missing)}"
            )
        _validate_feature_value(features, event_time, f"fila {number}.features_at_t")
        identity = str(row.get("episode_id") or row.get("event_id") or "")
        if not identity or identity in seen_ids:
            raise DiagnosticTrainingError(f"fila {number}: identidad ausente o duplicada")
        seen_ids.add(identity)
        rows.append(row)
    if not rows:
        raise DiagnosticTrainingError("JSONL vacío: no hay filas causales")
    rows.sort(
        key=lambda item: (
            _parse_time(item["event_time"], "event_time"),
            _canonical_json(item),
        )
    )
    for prior, current in zip(rows, rows[1:]):
        prior_time = _parse_time(prior["event_time"], "event_time")
        current_time = _parse_time(current["event_time"], "event_time")
        if current_time <= prior_time:
            raise DiagnosticTrainingError(
                "event_time debe ser estrictamente creciente; no se inventan desempates"
            )
    return DiagnosticRows(
        rows=tuple(rows),
        raw_sha256=hashlib.sha256(raw).hexdigest(),
        schema_hash=_schema_hash(rows),
        source_name=source.name,
    )


def _split_counts(total: int, train_fraction: float, validation_fraction: float) -> tuple[int, int, int]:
    train = int(math.floor(total * train_fraction))
    validation = int(math.floor(total * validation_fraction))
    return train, validation, total - train - validation


def _minimum_window(
    rows: Sequence[Mapping[str, Any]],
    *,
    target: str,
    train_fraction: float,
    validation_fraction: float,
    min_class_rows: int,
) -> dict[str, Any]:
    labels = [str(row.get(target, "")).lower() for row in rows]
    current_counts = {name: labels.count(name) for name in OUTCOME_CLASSES}
    candidate: dict[str, Any] | None = None
    for total in range(1, len(rows) + 1):
        train, validation, test = _split_counts(total, train_fraction, validation_fraction)
        if (train < MIN_PARTITION_ROWS["train"] or
                validation < MIN_PARTITION_ROWS["validation"] or
                test < MIN_PARTITION_ROWS["test"]):
            continue
        train_counts = {
            name: labels[:train].count(name) for name in OUTCOME_CLASSES
        }
        if min(train_counts.values()) < min_class_rows:
            continue
        candidate = {
            "rows_required": total,
            "train_rows": train,
            "validation_rows": validation,
            "test_rows": test,
            "start_event_time": rows[0].get("event_time"),
            "end_event_time": rows[total - 1].get("event_time"),
            "train_class_counts": train_counts,
        }
        break
    return {
        "minimum_total_rows": MIN_TOTAL_ROWS,
        "minimum_partition_rows": dict(MIN_PARTITION_ROWS),
        "minimum_train_class_rows": min_class_rows,
        "available_rows": len(rows),
        "additional_rows_at_least": max(0, MIN_TOTAL_ROWS - len(rows)),
        "available_class_counts": current_counts,
        "earliest_qualifying_window": candidate,
        "window_policy": "chronological prefix; 60% train, 20% validation, remainder test",
    }


def _build_split(
    rows: Sequence[Mapping[str, Any]],
    *,
    train_fraction: float,
    validation_fraction: float,
) -> TemporalSplit:
    train_count, validation_count, test_count = _split_counts(
        len(rows), train_fraction, validation_fraction
    )
    if min(train_count, validation_count, test_count) < 1:
        raise DiagnosticTrainingError("no se puede construir split temporal con estas filas")
    train = tuple(rows[:train_count])
    validation = tuple(rows[train_count:train_count + validation_count])
    test = tuple(rows[train_count + validation_count:])
    if _parse_time(train[-1]["event_time"], "train_end") >= _parse_time(
        validation[0]["event_time"], "validation_start"
    ) or _parse_time(validation[-1]["event_time"], "validation_end") >= _parse_time(
        test[0]["event_time"], "test_start"
    ):
        raise DiagnosticTrainingError("frontera temporal ambigua por timestamps iguales")
    return TemporalSplit(
        train=train,
        validation=validation,
        test=test,
        time_column="event_time",
        train_end=train[-1]["event_time"],
        validation_end=validation[-1]["event_time"],
        split_source="diagnostic_configured_temporal",
    )


def _git_commit() -> str:
    try:
        value = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.STDOUT
        ).strip()
        return value if re.fullmatch(r"[0-9a-fA-F]{7,64}", value) else "DIAGNOSTIC_LOCAL"
    except (OSError, subprocess.CalledProcessError):
        return "DIAGNOSTIC_LOCAL"


def _plan(
    rows: DiagnosticRows,
    split: TemporalSplit,
    *,
    target: str,
    seed: int,
    config: Mapping[str, Any],
) -> TrainingPlan:
    data_digest = hashlib.sha256(
        b"\n".join(_canonical_json(row) for row in rows.rows)
    ).hexdigest()
    identity = {
        "schema": TRAINING_PIPELINE_SCHEMA_VERSION,
        "dataset_hash": rows.raw_sha256,
        "schema_hash": rows.schema_hash,
        "target": target,
        "seed": seed,
        "config": dict(config),
        "split": split.to_dict(),
        "data_digest": data_digest,
    }
    run_id = hashlib.sha256(_canonical_json(identity)).hexdigest()
    metrics = {
        "pipeline_schema_version": TRAINING_PIPELINE_SCHEMA_VERSION,
        "train_rows": len(split.train),
        "validation_rows": len(split.validation),
        "test_rows": len(split.test),
        "selection_rows": len(split.selection),
        "oos_test_rows": len(split.oos_test),
        "selection_scope": "train+validation",
        "oos_scope": "test",
        "split_source": split.split_source,
        "data_digest": data_digest,
        "model_training_executed": False,
    }
    return TrainingPlan(
        pipeline_schema_version=TRAINING_PIPELINE_SCHEMA_VERSION,
        run_id=run_id,
        snapshot_id=f"DIAGNOSTIC_JSONL_{rows.raw_sha256[:16]}",
        dataset_hash=rows.raw_sha256,
        schema_hash=rows.schema_hash,
        model_id=DIAGNOSTIC_MODEL_ID,
        model_version=DIAGNOSTIC_MODEL_VERSION,
        features=("features_at_t", "direction", "sequence_depth"),
        labels=(target,),
        seed=seed,
        config=dict(config),
        split=split,
        metrics=metrics,
    )


def _base_payload(rows: DiagnosticRows, *, target: str, config: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": DIAGNOSTIC_SCHEMA_VERSION,
        "artifact_kind": DIAGNOSTIC_ARTIFACT_KIND,
        "status": "BLOCKED",
        "reason_code": None,
        "fit_executed": False,
        "target": target,
        "input": {
            "format": "causal_materialized_jsonl",
            "source_name": rows.source_name,
            "sha256": rows.raw_sha256,
            "schema_hash": rows.schema_hash,
            "rows": len(rows.rows),
        },
        "config": dict(config),
        "certified_snapshot": False,
        "scientific_training_eligible": False,
        "promotion_authorized": False,
        "shadow_mode": True,
        "can_trade": False,
    }


def run_diagnostic_training(
    jsonl_path: str | Path,
    *,
    target: str = "label_end_6",
    seed: int = 7,
    iterations: int = 500,
    learning_rate: float = 0.05,
    l2: float = 1e-4,
    min_class_rows: int = DEFAULT_MIN_CLASS_ROWS,
    train_fraction: float = 0.6,
    validation_fraction: float = 0.2,
    code_commit: str | None = None,
) -> dict[str, Any]:
    """Ejecuta o bloquea el primer ajuste diagnóstico, sin certificación."""

    if not isinstance(min_class_rows, int) or isinstance(min_class_rows, bool) or min_class_rows < 1:
        raise DiagnosticTrainingError("min_class_rows debe ser entero positivo")
    rows = load_causal_jsonl(jsonl_path, target=target)
    config = {
        "algorithm": "deterministic_multinomial_softmax",
        "target": target,
        "seed": seed,
        "iterations": iterations,
        "learning_rate": learning_rate,
        "l2": l2,
        "min_class_rows": min_class_rows,
        "train_fraction": train_fraction,
        "validation_fraction": validation_fraction,
        "mode": "DIAGNOSTIC_ONLY",
        "can_trade": False,
    }
    payload = _base_payload(rows, target=target, config=config)
    payload["minimum_window"] = _minimum_window(
        rows.rows,
        target=target,
        train_fraction=train_fraction,
        validation_fraction=validation_fraction,
        min_class_rows=min_class_rows,
    )
    total = len(rows.rows)
    train_count, validation_count, test_count = _split_counts(
        total, train_fraction, validation_fraction
    )
    if (
        train_count < MIN_PARTITION_ROWS["train"]
        or validation_count < MIN_PARTITION_ROWS["validation"]
        or test_count < MIN_PARTITION_ROWS["test"]
    ):
        payload["reason_code"] = "INSUFFICIENT_DATA"
        payload["diagnostics"] = [
            "no se ejecutó ajuste: faltan filas para 30 TRAIN + 10 VALIDATION + 10 TEST/OOS",
        ]
        payload["temporal_split"] = {
            "train_rows": train_count,
            "validation_rows": validation_count,
            "test_rows": test_count,
            "split_source": "diagnostic_configured_temporal",
        }
        return _with_hash(payload)

    split = _build_split(
        rows.rows,
        train_fraction=train_fraction,
        validation_fraction=validation_fraction,
    )
    train_counts = {
        name: sum(str(row.get(target, "")).lower() == name for row in split.train)
        for name in OUTCOME_CLASSES
    }
    payload["temporal_split"] = split.to_dict()
    payload["train_class_counts"] = train_counts
    if min(train_counts.values()) < min_class_rows:
        payload["reason_code"] = "INSUFFICIENT_CLASS_SUPPORT"
        payload["diagnostics"] = [
            f"no se ejecutó ajuste: TRAIN requiere al menos {min_class_rows} filas por clase",
        ]
        return _with_hash(payload)

    plan = _plan(rows, split, target=target, seed=seed, config=config)
    pipeline = _DiagnosticPipeline(plan, code_commit=code_commit or _git_commit())
    # La API existente del clasificador exige estas dos claves. Este mapping
    # es deliberadamente local y de diagnóstico; nunca se trata como el gate
    # científico del dataset ni se pasa al runner productivo.
    diagnostic_authorization = {
        "status": "PASS",
        "verdict": "TRAINING_ELIGIBLE",
        "dataset_hash": rows.raw_sha256,
        "scope": "DIAGNOSTIC_ONLY",
        "certified_snapshot": False,
        "promotion_authorized": False,
    }
    try:
        model = train_outcome_classifier(
            pipeline,
            research_gate=diagnostic_authorization,
            target=target,
            min_class_rows=min_class_rows,
            iterations=iterations,
            learning_rate=learning_rate,
            l2=l2,
        )
    except (OutcomeClassifierError, TrainingAuthorizationError) as exc:
        payload["reason_code"] = "CLASSIFIER_CONTRACT_BLOCKED"
        payload["diagnostics"] = [str(exc)]
        return _with_hash(payload)

    payload.update({
        "status": "DIAGNOSTIC_ONLY_COMPLETED",
        "fit_executed": True,
        "reason_code": None,
        "diagnostics": [
            "ajuste ejecutado sólo para diagnóstico local; no es certificación ni promoción",
        ],
        "metrics": json.loads(json.dumps(model.metrics, sort_keys=True)),
        "model": model.to_dict(),
        "training_plan": plan.state(),
        "diagnostic_authorization": diagnostic_authorization,
    })
    return _with_hash(payload)


def _with_hash(payload: Mapping[str, Any]) -> dict[str, Any]:
    body = json.loads(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    body.pop("artifact_hash", None)
    body["artifact_hash"] = hashlib.sha256(_canonical_json(body)).hexdigest()
    return body


def write_diagnostic_artifact(payload: Mapping[str, Any], output: str | Path) -> Path:
    destination = Path(output).resolve()
    if destination.suffix.lower() != ".json":
        raise DiagnosticTrainingError("output debe ser JSON")
    if destination.exists():
        raise DiagnosticTrainingError(f"output ya existe y no se sobrescribe: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    body = _with_hash(payload)
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.write_text(
        json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


__all__ = [
    "DIAGNOSTIC_ARTIFACT_KIND",
    "DIAGNOSTIC_SCHEMA_VERSION",
    "DiagnosticRows",
    "DiagnosticTrainingError",
    "MIN_PARTITION_ROWS",
    "MIN_TOTAL_ROWS",
    "load_causal_jsonl",
    "run_diagnostic_training",
    "write_diagnostic_artifact",
]
