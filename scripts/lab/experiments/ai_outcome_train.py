"""Runner local y fail-closed para el primer entrenamiento de outcomes ICT.

El runner no construye datasets ni lee fuentes de mercado. Solo acepta la ruta
de un ``DatasetSnapshot`` ya materializado y validado por INF-2, además de una
autorización científica JSON explícita con ``TRAINING_ELIGIBLE``. La ejecución
usa el plan temporal de ``TrainingPipeline`` (INF-4) y el baseline determinista
de ``outcome_classifier``. El artefacto resultante sigue siendo Shadow Mode.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.ai_learning.checkpoint_store import CheckpointStore
from runtime.ai_learning.dataset_snapshots import (
    DatasetSnapshot,
    DatasetSnapshotError,
    CertifiedDatasetReader,
    load_dataset_snapshot,
)
from runtime.ai_learning.model_registry import ModelRegistry, ModelRegistryError
from runtime.ai_learning.outcome_classifier import (
    OutcomeClassifierError,
    train_outcome_classifier,
)
from runtime.ai_learning.training_pipeline import TrainingPipeline, TrainingPipelineError


RUNNER_SCHEMA_VERSION = "1.0"
TARGET = "label_end_6"
MODEL_ID = "ICT_OUTCOME_CLASSIFIER_V1"
MODEL_VERSION = "1.0.0"
FEATURE_COLUMNS = ("features_at_t", "direction", "sequence_depth")
REQUIRED_GATES = ("causal_full_vs_prefix", "tna_behavioral_full_span")
DEFAULT_OUTPUT = ROOT / "runtime" / "ai_learning" / "artifacts" / "outcome_classifier_v1.json"
DEFAULT_REGISTRY = ROOT / "runtime" / "ai_learning" / "registry" / "outcome_classifier_v1"
DEFAULT_CHECKPOINTS = ROOT / "runtime" / "ai_learning" / "checkpoints" / "outcome_classifier_v1"


class TrainingRunnerError(ValueError):
    """Error de entrada o de ejecución del runner."""


class TrainingRunnerBlocked(TrainingRunnerError):
    """Una condición de contrato impide entrenar o publicar el artefacto."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _assert_local_path(path: str | Path, field: str) -> Path:
    text = str(path)
    if "://" in text:
        raise TrainingRunnerBlocked(f"{field} debe ser una ruta local, no un URI")
    return Path(path).resolve()


def _load_json_object(path: str | Path, field: str) -> dict[str, Any]:
    source = _assert_local_path(path, field)
    if source.suffix.lower() == ".parquet":
        raise TrainingRunnerBlocked(f"{field} parquet prohibido")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TrainingRunnerBlocked(f"{field} JSON ilegible: {source}") from exc
    if not isinstance(payload, Mapping):
        raise TrainingRunnerBlocked(f"{field} debe contener un objeto JSON")
    return dict(payload)


def _load_certified_snapshot(path: str | Path) -> tuple[DatasetSnapshot, tuple[dict[str, Any], ...]]:
    snapshot_path = _assert_local_path(path, "snapshot")
    if snapshot_path.suffix.lower() == ".parquet":
        raise TrainingRunnerBlocked("snapshot parquet prohibido")
    try:
        snapshot = load_dataset_snapshot(snapshot_path)
        rows = CertifiedDatasetReader(snapshot.snapshot_path.parent).read_snapshot(snapshot.snapshot_path)
    except (DatasetSnapshotError, OSError) as exc:
        raise TrainingRunnerBlocked(f"DatasetSnapshot no certificado o íntegro: {exc}") from exc
    if snapshot.certified_manifest.verdict != "PASS":
        raise TrainingRunnerBlocked("DatasetSnapshot requiere manifest verdict=PASS")
    return snapshot, rows


def _validate_snapshot_contract(
    snapshot: DatasetSnapshot,
    rows: tuple[dict[str, Any], ...],
    *,
    time_column: str,
) -> None:
    source = snapshot.source_path.replace("\\", "/").lower()
    if source.endswith(".parquet") or source.startswith("data/raw/") or "/mt5/" in source:
        raise TrainingRunnerBlocked("la fuente del snapshot es MT5/raw/parquet; solo se acepta el plano histórico certificado")

    if snapshot.config.get("can_trade") is not False:
        raise TrainingRunnerBlocked("snapshot.config.can_trade debe ser false")
    gate = snapshot.certified_manifest.gate
    if not isinstance(gate, Mapping):
        raise TrainingRunnerBlocked("el manifest debe exponer gates causales y temporales nominales")
    missing = [name for name in REQUIRED_GATES if gate.get(name) != "PASS"]
    if missing:
        raise TrainingRunnerBlocked("gates del snapshot no PASS: " + ", ".join(missing))

    columns = set(snapshot.schema.columns)
    required = set(FEATURE_COLUMNS) | {TARGET, time_column}
    absent = sorted(required - columns)
    if absent:
        raise TrainingRunnerBlocked("snapshot sin columnas requeridas: " + ", ".join(absent))
    if any(row.get("can_trade") is not False for row in rows):
        raise TrainingRunnerBlocked("todas las filas del snapshot deben conservar can_trade=false")


def _validate_training_authorization(
    research_gate: Mapping[str, Any],
    snapshot: DatasetSnapshot,
) -> None:
    if research_gate.get("status") != "PASS" or research_gate.get("verdict") != "TRAINING_ELIGIBLE":
        raise TrainingRunnerBlocked("la autorización científica debe ser status=PASS y verdict=TRAINING_ELIGIBLE")
    if research_gate.get("dataset_hash") != snapshot.dataset_hash:
        raise TrainingRunnerBlocked("research_gate.dataset_hash no coincide con el DatasetSnapshot")
    if "can_trade" in research_gate and research_gate["can_trade"] is not False:
        raise TrainingRunnerBlocked("la autorización no puede habilitar can_trade")
    if research_gate.get("snapshot_eligible") is False:
        raise TrainingRunnerBlocked("research_gate declara snapshot_eligible=false")


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.STDOUT
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise TrainingRunnerBlocked("no se pudo determinar el commit del runner") from exc


def _worktree_state() -> str:
    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True, stderr=subprocess.STDOUT
        )
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"
    return "CLEAN" if not status.strip() else "DIRTY"


def _register_or_validate_model(
    registry: ModelRegistry,
    snapshot: DatasetSnapshot,
    *,
    git_commit: str,
    config: Mapping[str, Any],
) -> None:
    try:
        registry.get_model(MODEL_ID, MODEL_VERSION)
        return
    except ModelRegistryError:
        pass
    try:
        registry.register_model(
            MODEL_ID,
            MODEL_VERSION,
            git_commit=git_commit,
            snapshot=snapshot,
            features=FEATURE_COLUMNS,
            labels=(TARGET,),
            seed=int(config["seed"]),
            config=config,
            created_at=snapshot.created_at,
        )
    except ModelRegistryError as exc:
        raise TrainingRunnerBlocked(f"no se pudo registrar el modelo con lineage: {exc}") from exc


def _write_immutable_json(path: str | Path, payload: Mapping[str, Any]) -> Path:
    destination = _assert_local_path(path, "output")
    if destination.suffix.lower() != ".json":
        raise TrainingRunnerBlocked("output debe ser un artefacto JSON")
    if destination.exists():
        raise TrainingRunnerBlocked(f"output ya existe y no se sobrescribe: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    body = dict(payload)
    body["artifact_hash"] = hashlib.sha256(_canonical_json(body)).hexdigest()
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
    except OSError as exc:
        raise TrainingRunnerBlocked(f"no se pudo publicar el artefacto: {destination}") from exc
    return destination


def run_training(
    *,
    snapshot_path: str | Path,
    research_gate_path: str | Path,
    output_path: str | Path = DEFAULT_OUTPUT,
    registry_root: str | Path = DEFAULT_REGISTRY,
    checkpoint_root: str | Path = DEFAULT_CHECKPOINTS,
    time_column: str = "event_time",
    seed: int = 20260831,
    iterations: int = 500,
    learning_rate: float = 0.05,
    l2: float = 1e-4,
    min_class_rows: int = 5,
) -> dict[str, Any]:
    """Ejecuta el entrenamiento únicamente detrás de todos los gates."""
    if time_column not in {"event_time", "timestamp"}:
        raise TrainingRunnerBlocked("time_column no permitido; use event_time o timestamp")
    snapshot, rows = _load_certified_snapshot(snapshot_path)
    _validate_snapshot_contract(snapshot, rows, time_column=time_column)
    research_gate = _load_json_object(research_gate_path, "research_gate")
    _validate_training_authorization(research_gate, snapshot)

    git_commit = _git_commit()
    config = {
        "algorithm": "deterministic_multinomial_softmax",
        "can_trade": False,
        "shadow_mode": True,
        "target": TARGET,
        "time_column": time_column,
        "train_fraction": 0.6,
        "validation_fraction": 0.2,
        "seed": seed,
        "iterations": iterations,
        "learning_rate": learning_rate,
        "l2": l2,
        "min_class_rows": min_class_rows,
    }
    registry = ModelRegistry(_assert_local_path(registry_root, "registry_root"))
    _register_or_validate_model(registry, snapshot, git_commit=git_commit, config=config)
    pipeline = TrainingPipeline(
        snapshot=snapshot.snapshot_path,
        registry=registry,
        checkpoint_store=CheckpointStore(
            _assert_local_path(checkpoint_root, "checkpoint_root"), workspace_root=ROOT
        ),
        model_id=MODEL_ID,
        model_version=MODEL_VERSION,
        features=FEATURE_COLUMNS,
        labels=(TARGET,),
        seed=seed,
        config=config,
        time_column=time_column,
        train_fraction=0.6,
        validation_fraction=0.2,
    )
    try:
        plan = pipeline.plan()
        model = train_outcome_classifier(
            pipeline,
            research_gate=research_gate,
            target=TARGET,
            min_class_rows=min_class_rows,
            iterations=iterations,
            learning_rate=learning_rate,
            l2=l2,
        )
    except (OutcomeClassifierError, TrainingPipelineError) as exc:
        raise TrainingRunnerBlocked(f"entrenamiento bloqueado por contrato: {exc}") from exc

    model_payload = model.to_dict()
    model_payload["model_artifact_hash"] = model_payload.pop("artifact_hash")
    payload: dict[str, Any] = {
        **model_payload,
        "runner_schema_version": RUNNER_SCHEMA_VERSION,
        "artifact_kind": "ai_outcome_classifier_training",
        "runner": {
            "path": _relative(Path(__file__)),
            "code_commit": git_commit,
            "worktree_state": _worktree_state(),
            "local_only": True,
        },
        "dataset_snapshot": {
            "snapshot_path": _relative(snapshot.snapshot_path),
            "snapshot_id": snapshot.snapshot_id,
            "data_path": snapshot.data_path.name,
            "dataset_hash": snapshot.dataset_hash,
            "schema_hash": snapshot.schema_hash,
            "experiment_id": snapshot.experiment_id,
            "source_path": snapshot.source_path,
        },
        "research_gate": research_gate,
        "training_pipeline": {
            "schema_version": plan.pipeline_schema_version,
            "run_id": plan.run_id,
            "split": plan.split.to_dict(),
            "plan_metrics": plan.metrics,
            "fit_scope": "TRAIN only",
            "validation_scope": "VALIDATION reporting only",
            "oos_scope": "TEST_OOS reporting only; never fitted",
        },
        "shadow_mode": True,
        "can_trade": False,
    }
    destination = _write_immutable_json(output_path, payload)
    payload["artifact_hash"] = hashlib.sha256(_canonical_json(payload)).hexdigest()
    payload["output_path"] = _relative(destination)
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, help="Directorio de DatasetSnapshot certificado")
    parser.add_argument("--research-gate", required=True, help="JSON de autorización TRAINING_ELIGIBLE")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Artefacto JSON inmutable de salida")
    parser.add_argument("--registry-root", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--checkpoint-root", default=str(DEFAULT_CHECKPOINTS))
    parser.add_argument("--time-column", default="event_time", choices=("event_time", "timestamp"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        payload = run_training(
            snapshot_path=args.snapshot,
            research_gate_path=args.research_gate,
            output_path=args.output,
            registry_root=args.registry_root,
            checkpoint_root=args.checkpoint_root,
            time_column=args.time_column,
        )
    except TrainingRunnerBlocked as exc:
        print(json.dumps({"runner_schema_version": RUNNER_SCHEMA_VERSION, "status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"status": "COMPLETED", "output_path": payload["output_path"], "metrics": payload["metrics"]}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["TrainingRunnerBlocked", "TrainingRunnerError", "run_training"]
