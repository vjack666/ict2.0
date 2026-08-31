"""Materializador causal de outcomes para el primer dataset IA de ICT.

Este módulo consume únicamente dos artefactos ya serializados:

* el Funnel/Episodes causal, cuya autoridad de features es ``features_at_t``;
* el artefacto ``backtest/visual_backtest.json`` producido por el replay canónico.

No carga ``data/raw`` ni ejecuta el backtest.  El futuro solo entra por el
resultado que el replay ya resolvió: TP, SL u OPEN.  Por tanto, este módulo no
puede corregir un feed, recalcular una señal ni convertir un reporte técnico
en autorización científica.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backtest.schema import SCHEMA_VERSION as VISUAL_BACKTEST_SCHEMA_VERSION
from backtest.schema import validate_visual_backtest
from runtime.ai_learning.dataset_snapshots import (
    DatasetSnapshot,
    CertifiedDatasetReader,
    hash_dataset,
    load_dataset_snapshot,
)
from runtime.ai_learning.training_pipeline import TrainingPipeline


CONTRACT_VERSION = "AI_OUTCOME_DATASET_V1"
EPISODES_CONTRACT_VERSION = "EPISODES_FUNNEL_V1"
OUTCOME_CLASSES = ("continuation", "reversal", "failure")
_DIRECTION_ALIASES = {
    "BULLISH": 1,
    "BULL": 1,
    "LONG": 1,
    "BEARISH": -1,
    "BEAR": -1,
    "SHORT": -1,
}
_FORBIDDEN_FEATURE_PARTS = (
    "label",
    "outcome",
    "exit",
    "future",
    "pnl",
    "profit",
    "return",
    "entry",
    "stop",
    "target",
    "sl",
    "tp",
    "bars_held",
    "result",
)
_TIME_PARTS = ("time", "timestamp", "asof", "available", "observed", "created")
_HEX_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_HEX_COMMIT = re.compile(r"^[0-9a-fA-F]{7,64}$")


class OutcomeDatasetError(ValueError):
    """Entrada incompleta, no causal o incompatible con el contrato."""


class TrainingEligibilityError(OutcomeDatasetError):
    """El material técnico no puede cruzar la frontera de entrenamiento."""


@dataclass(frozen=True)
class MaterializationResult:
    """Filas reproducibles más el dictamen de elegibilidad, sin autoridad de trading."""

    rows: tuple[dict[str, Any], ...]
    status: str
    training_eligible: bool
    diagnostics: tuple[str, ...] = field(default_factory=tuple)
    horizon_bars: int | None = None
    dataset_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": CONTRACT_VERSION,
            "status": self.status,
            "training_eligible": self.training_eligible,
            "horizon_bars": self.horizon_bars,
            "dataset_hash": self.dataset_hash,
            "rows": [deepcopy(row) for row in self.rows],
            "diagnostics": list(self.diagnostics),
            "can_trade": False,
        }


def _load_json(value: Mapping[str, Any] | str | Path, name: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return deepcopy(dict(value))
    path = Path(value)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OutcomeDatasetError(f"{name} ilegible: {path}") from exc
    if not isinstance(payload, Mapping):
        raise OutcomeDatasetError(f"{name} debe ser un objeto JSON")
    return dict(payload)


def _utc(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise OutcomeDatasetError(f"{field_name} debe ser timestamp ISO-8601")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise OutcomeDatasetError(f"{field_name} debe ser timestamp ISO-8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: Any, field_name: str) -> str:
    return _utc(value, field_name).isoformat()


def _direction(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise OutcomeDatasetError(f"{field_name} direction inválida")
    if isinstance(value, (int, float)):
        result = int(value)
        if result in (-1, 1) and float(value) == result:
            return result
    if isinstance(value, str):
        raw = value.strip().upper()
        if raw in _DIRECTION_ALIASES:
            return _DIRECTION_ALIASES[raw]
        try:
            result = int(raw)
            if result in (-1, 1):
                return result
        except ValueError:
            pass
    raise OutcomeDatasetError(f"{field_name} direction inválida")


def _int(value: Any, field_name: str, *, positive: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise OutcomeDatasetError(f"{field_name} debe ser entero")
    if positive and value < 1:
        raise OutcomeDatasetError(f"{field_name} debe ser positivo")
    return value


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _jsonl_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    lines = [json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str) for row in rows]
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def _features_source(
    episode: Mapping[str, Any],
    features_by_episode: Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    episode_id = episode.get("episode_id")
    candidates = [
        episode.get("features_at_t"),
        (episode.get("meta") or {}).get("features_at_t") if isinstance(episode.get("meta"), Mapping) else None,
        features_by_episode.get(str(episode_id)) if features_by_episode and episode_id is not None else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, Mapping):
            return candidate
    raise OutcomeDatasetError("MISSING_FEATURES_AT_T")


def _validate_feature_value(value: Any, decision_time: datetime, path: str) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).lower()
            if any(part in key_text for part in _FORBIDDEN_FEATURE_PARTS):
                raise OutcomeDatasetError(f"features_at_t contiene campo futuro/prohibido: {path}.{key}")
            if key_text in {"time", "timestamp", "event_time", "observed_time", "available_time", "created_at", "as_of", "asof"}:
                observed = _utc(child, f"features_at_t.{path}.{key}")
                if observed > decision_time:
                    raise OutcomeDatasetError(f"features_at_t contiene tiempo futuro: {path}.{key}")
            elif any(part in key_text for part in _TIME_PARTS):
                # ``timeframe``/``timestamp_mode`` are categorical fields, not
                # timestamps. Parse only opportunistically for other names.
                try:
                    observed = _utc(child, f"features_at_t.{path}.{key}")
                except OutcomeDatasetError:
                    observed = None
                if observed is not None and observed > decision_time:
                    raise OutcomeDatasetError(f"features_at_t contiene tiempo futuro: {path}.{key}")
            _validate_feature_value(child, decision_time, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate_feature_value(child, decision_time, f"{path}[{index}]")


def _causal_features(episode: Mapping[str, Any], source: Mapping[str, Any], decision_time: datetime) -> tuple[dict[str, Any], int]:
    _validate_feature_value(source, decision_time, "features_at_t")
    features = deepcopy(dict(source))
    sequence = features.get("sequence")
    context = features.get("context_inputs")
    if not isinstance(sequence, (list, tuple)) or not sequence:
        raise OutcomeDatasetError(f"{episode.get('episode_id')}: features_at_t.sequence requerido")
    if not isinstance(context, Mapping):
        raise OutcomeDatasetError(f"{episode.get('episode_id')}: features_at_t.context_inputs requerido")
    required_context = {"sequence_direction", "d1_bias", "h4_location", "h1_alignment"}
    missing = sorted(required_context.difference(context))
    if missing:
        raise OutcomeDatasetError(
            f"{episode.get('episode_id')}: features_at_t.context_inputs incompleto: {','.join(missing)}"
        )
    depth = features.get("sequence_depth", episode.get("sequence_depth"))
    if depth is None and isinstance(episode.get("meta"), Mapping):
        depth = episode["meta"].get("sequence_depth")
    depth = _int(depth, f"{episode.get('episode_id')}.sequence_depth", positive=True)
    direction = _direction(episode.get("direction"), f"{episode.get('episode_id')}.direction")
    if _direction(context.get("sequence_direction"), f"{episode.get('episode_id')}.features.direction") != direction:
        raise OutcomeDatasetError(f"{episode.get('episode_id')}: dirección de feature no coincide con Episode")
    features["sequence"] = [str(stage) for stage in sequence]
    features["context_inputs"] = dict(context)
    features["sequence_depth"] = depth
    return features, depth


def _validate_funnel(funnel: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    diagnostics: list[str] = []
    if funnel.get("contract_version") != EPISODES_CONTRACT_VERSION:
        diagnostics.append("FUNNEL_CONTRACT_MISMATCH")
    if funnel.get("aggregated_status") != "PASS":
        diagnostics.append(f"FUNNEL_STATUS_{funnel.get('aggregated_status', 'MISSING')}")
    gates = funnel.get("gates")
    if not isinstance(gates, Mapping) or not gates or any(value != "PASS" for value in gates.values()):
        diagnostics.append("FUNNEL_CAUSAL_GATES_NOT_PASS")
    full_prefix = funnel.get("full_prefix")
    if not isinstance(full_prefix, Mapping) or full_prefix.get("prefix_matches_full") is not True:
        diagnostics.append("FUNNEL_FULL_PREFIX_NOT_PROVEN")
    if not isinstance(funnel.get("generator_commit"), str) or not _HEX_COMMIT.fullmatch(funnel["generator_commit"]):
        diagnostics.append("FUNNEL_GENERATOR_COMMIT_MISSING_OR_INVALID")
    if not isinstance(funnel.get("provenance"), Mapping) or not funnel.get("provenance"):
        diagnostics.append("FUNNEL_PROVENANCE_MISSING")
    episodes = funnel.get("episodes")
    if not isinstance(episodes, list):
        diagnostics.append("FUNNEL_EPISODES_MISSING")
        return [], diagnostics
    accepted: list[dict[str, Any]] = []
    seen: set[str] = set()
    for episode in episodes:
        if not isinstance(episode, Mapping):
            diagnostics.append("FUNNEL_EPISODE_NOT_OBJECT")
            continue
        if episode.get("status") != "ACCEPTED":
            diagnostics.append(f"EPISODE_NOT_ACCEPTED:{episode.get('episode_id', '')}")
            continue
        episode_id = str(episode.get("episode_id", ""))
        if not episode_id or episode_id in seen:
            diagnostics.append(f"EPISODE_ID_INVALID_OR_DUPLICATE:{episode_id}")
            continue
        seen.add(episode_id)
        accepted.append(dict(episode))
    return accepted, diagnostics


def _validate_backtest(backtest: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int], list[str]]:
    diagnostics: list[str] = []
    try:
        validate_visual_backtest(backtest)
    except (KeyError, TypeError, ValueError) as exc:
        raise OutcomeDatasetError(f"BACKTEST_SCHEMA_INVALID: {exc}") from exc
    if backtest.get("schema_version") != VISUAL_BACKTEST_SCHEMA_VERSION:
        diagnostics.append("BACKTEST_SCHEMA_MISMATCH")
    metadata = backtest.get("metadata")
    if not isinstance(metadata, Mapping) or metadata.get("causal") is not True:
        diagnostics.append("BACKTEST_CAUSAL_METADATA_MISSING")
    if not isinstance(metadata, Mapping) or metadata.get("legacy_backtest") is not False:
        diagnostics.append("BACKTEST_LEGACY_BOUNDARY_UNPROVEN")
    if not isinstance(metadata, Mapping) or metadata.get("promotion_authorized") is not False:
        diagnostics.append("BACKTEST_PROMOTION_BOUNDARY_UNPROVEN")
    candles = backtest.get("candles", [])
    times: list[str] = []
    prior: datetime | None = None
    for index, candle in enumerate(candles):
        if not isinstance(candle, Mapping):
            raise OutcomeDatasetError(f"BACKTEST_CANDLE_NOT_OBJECT:{index}")
        current = _utc(candle.get("time"), f"candles[{index}].time")
        if prior is not None and current <= prior:
            raise OutcomeDatasetError("BACKTEST_CANDLE_TIMES_NOT_STRICTLY_INCREASING")
        times.append(current.isoformat())
        prior = current
    by_key: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for trade in backtest.get("trades", []):
        if not isinstance(trade, Mapping):
            diagnostics.append("BACKTEST_TRADE_NOT_OBJECT")
            continue
        if trade.get("entry_time") is None or trade.get("entry_index") is None:
            diagnostics.append(f"TRADE_IDENTITY_MISSING:{trade.get('id', '')}")
            continue
        entry_time = _iso(trade["entry_time"], f"trade[{trade.get('id', '')}].entry_time")
        direction = _direction(trade.get("direction"), f"trade[{trade.get('id', '')}].direction")
        by_key.setdefault((entry_time, direction), []).append(dict(trade))
    return times, {key: len(value) for key, value in by_key.items()}, diagnostics


def _resolve_horizon(backtest: Mapping[str, Any], explicit: int | None) -> int:
    metadata = backtest.get("metadata")
    nested = metadata.get("outcome") if isinstance(metadata, Mapping) else None
    candidates = [
        explicit,
        nested.get("horizon_bars") if isinstance(nested, Mapping) else None,
        metadata.get("outcome_horizon_bars") if isinstance(metadata, Mapping) else None,
    ]
    for candidate in candidates:
        if candidate is not None:
            return _int(candidate, "horizon_bars", positive=True)
    raise OutcomeDatasetError("BACKTEST_HORIZON_MISSING: no se puede determinar el futuro permitido")


def _trade_for_episode(
    episode: Mapping[str, Any],
    times: Sequence[str],
    trades: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    decision_time = _iso(episode.get("decision_time"), f"episode[{episode.get('episode_id', '')}].decision_time")
    direction = _direction(episode.get("direction"), f"episode[{episode.get('episode_id', '')}].direction")
    matches = []
    for trade in trades:
        if trade.get("entry_time") is None:
            continue
        if _iso(trade["entry_time"], "trade.entry_time") != decision_time:
            continue
        if _direction(trade.get("direction"), "trade.direction") == direction:
            matches.append(dict(trade))
    if len(matches) != 1:
        reason = "MISSING" if not matches else "AMBIGUOUS"
        raise OutcomeDatasetError(f"{episode.get('episode_id')}: BACKTEST_TRADE_{reason}")
    trade = matches[0]
    entry_index = _int(trade.get("entry_index"), "trade.entry_index")
    if not 0 <= entry_index < len(times) or times[entry_index] != decision_time:
        raise OutcomeDatasetError(f"{episode.get('episode_id')}: TRADE_ENTRY_NOT_AT_DECISION_TIME")
    return trade


def _label_from_trade(trade: Mapping[str, Any], entry_index: int, times: Sequence[str], horizon: int) -> tuple[str, str, int | None]:
    raw = str(trade.get("outcome", "")).upper()
    mapping = {"TP": "continuation", "SL": "reversal", "OPEN": "failure"}
    if raw not in mapping:
        raise OutcomeDatasetError(f"{trade.get('id', '')}: BACKTEST_OUTCOME_INVALID:{raw or 'MISSING'}")
    last_allowed = entry_index + horizon
    if last_allowed >= len(times):
        raise OutcomeDatasetError(f"{trade.get('id', '')}: INSUFFICIENT_FUTURE_HORIZON")
    exit_index = trade.get("exit_index")
    if raw in {"TP", "SL"}:
        exit_index = _int(exit_index, f"trade[{trade.get('id', '')}].exit_index")
        if not entry_index < exit_index <= last_allowed:
            raise OutcomeDatasetError(f"{trade.get('id', '')}: EXIT_OUTSIDE_ALLOWED_HORIZON")
        available = _iso(trade.get("exit_time"), f"trade[{trade.get('id', '')}].exit_time") if trade.get("exit_time") else times[exit_index]
        if available != times[exit_index]:
            raise OutcomeDatasetError(f"{trade.get('id', '')}: EXIT_TIME_INDEX_MISMATCH")
        return mapping[raw], available, exit_index
    if exit_index is not None:
        raise OutcomeDatasetError(f"{trade.get('id', '')}: OPEN_HAS_EXIT")
    # OPEN is only a valid failure after the complete configured horizon was
    # observed.  A truncated file is excluded, never relabeled as failure.
    return mapping[raw], times[last_allowed], None


def _a7_diagnostics(a7: Mapping[str, Any] | None) -> list[str]:
    if a7 is None:
        return ["A7_EVIDENCE_MISSING"]
    diagnostics: list[str] = []
    if a7.get("gate") != "A7":
        diagnostics.append("A7_GATE_ID_MISMATCH")
    if a7.get("aggregated_status") != "PASS":
        diagnostics.append(f"A7_TECHNICAL_STATUS_{a7.get('aggregated_status', 'MISSING')}")
    if a7.get("aggregated_findings", 0) != 0:
        diagnostics.append("A7_TECHNICAL_FINDINGS_PRESENT")
    matrix = a7.get("matrix")
    if isinstance(matrix, list) and any(isinstance(item, Mapping) and item.get("status") != "PASS" for item in matrix):
        diagnostics.append("A7_COMPLETION_MATRIX_NOT_PASS")
    source = a7.get("provenance_source") or a7.get("source_provenance")
    if not isinstance(source, Mapping):
        diagnostics.append("A7_SOURCE_PROVENANCE_MISSING")
    else:
        if source.get("declared_status") != "PASS":
            diagnostics.append(f"A7_SOURCE_PROVENANCE_{source.get('declared_status', 'MISSING')}")
        if source.get("license_and_permitted_use") in (None, "UNKNOWN"):
            diagnostics.append("A7_LICENSE_OR_PERMITTED_USE_UNKNOWN")
        if source.get("execution_verified") is not True:
            diagnostics.append("A7_ACQUISITION_EXECUTION_UNVERIFIED")
        if source.get("source_provenance_complete") is not True:
            diagnostics.append("A7_SOURCE_PROVENANCE_INCOMPLETE")
    return diagnostics


def _research_gate_diagnostics(research_gate: Mapping[str, Any] | None, dataset_hash: str | None = None) -> list[str]:
    if research_gate is None:
        return ["RESEARCH_GATE_MISSING"]
    diagnostics: list[str] = []
    if research_gate.get("status") != "PASS":
        diagnostics.append(f"RESEARCH_GATE_STATUS_{research_gate.get('status', 'MISSING')}")
    if research_gate.get("verdict") != "TRAINING_ELIGIBLE":
        diagnostics.append(f"RESEARCH_GATE_VERDICT_{research_gate.get('verdict', 'MISSING')}")
    if dataset_hash is not None and research_gate.get("dataset_hash") != dataset_hash:
        diagnostics.append("RESEARCH_GATE_DATASET_HASH_MISMATCH")
    return diagnostics


def materialize_outcome_rows(
    funnel_artifact: Mapping[str, Any] | str | Path,
    backtest_artifact: Mapping[str, Any] | str | Path,
    *,
    a7_report: Mapping[str, Any] | str | Path | None = None,
    research_gate: Mapping[str, Any] | None = None,
    features_by_episode: Mapping[str, Any] | None = None,
    horizon_bars: int | None = None,
) -> MaterializationResult:
    """Materializa filas; el resultado permanece BLOCKED si los gates no pasan.

    La ausencia de features o una inconsistencia temporal impide formar esa
    fila. Los bloqueos de provenance/ciencia se conservan en ``diagnostics`` y
    no se degradan a una etiqueta o a un snapshot certificable.
    """

    funnel = _load_json(funnel_artifact, "funnel_artifact")
    backtest = _load_json(backtest_artifact, "backtest_artifact")
    a7 = _load_json(a7_report, "a7_report") if a7_report is not None else None
    episodes, diagnostics = _validate_funnel(funnel)
    times, _, backtest_diagnostics = _validate_backtest(backtest)
    diagnostics.extend(backtest_diagnostics)
    diagnostics.extend(_a7_diagnostics(a7))
    horizon = _resolve_horizon(backtest, horizon_bars)
    trades = backtest.get("trades", [])
    if not isinstance(trades, list):
        raise OutcomeDatasetError("BACKTEST_TRADES_INVALID")
    rows: list[dict[str, Any]] = []
    row_errors: list[str] = []
    for episode in episodes:
        episode_id = str(episode.get("episode_id", ""))
        try:
            decision_time = _iso(episode.get("decision_time"), f"episode[{episode_id}].decision_time")
            feature_source = _features_source(episode, features_by_episode)
            features, depth = _causal_features(episode, feature_source, _utc(decision_time, "decision_time"))
            trade = _trade_for_episode(episode, times, trades)
            entry_index = _int(trade.get("entry_index"), f"trade[{trade.get('id', '')}].entry_index")
            label, available_time, exit_index = _label_from_trade(trade, entry_index, times, horizon)
            rows.append({
                "dataset_id": "AI_OUTCOME_DATASET_V1",
                "contract_version": CONTRACT_VERSION,
                "symbol": str(backtest.get("symbol") or episode.get("symbol") or ""),
                "timeframe": str(backtest.get("timeframe") or ""),
                "episode_id": episode_id,
                "event_time": decision_time,
                "label_available_time": available_time,
                "direction": _direction(episode.get("direction"), f"episode[{episode_id}].direction"),
                "sequence_depth": depth,
                "features_at_t": features,
                "label": label,
                f"label_end_{horizon}": label,
                "backtest_trade_id": str(trade.get("id", "")),
                "backtest_entry_index": entry_index,
                "backtest_exit_index": exit_index,
                "label_source": "canonical_backtest_trade_outcome",
                "can_trade": False,
            })
        except OutcomeDatasetError as exc:
            row_errors.append(f"{episode_id}: {exc}")
    diagnostics.extend(f"ROW_REJECTED:{error}" for error in row_errors)
    if not rows:
        diagnostics.append("NO_VERIFIABLE_ROWS")
    scientific_hash = hashlib.sha256(_jsonl_bytes(rows)).hexdigest() if rows else None
    diagnostics.extend(_research_gate_diagnostics(research_gate, scientific_hash))
    # A technical row set may be useful for review, but it is not a training
    # dataset until every gate and hash is explicitly authorized.
    training_eligible = bool(rows) and not diagnostics
    return MaterializationResult(
        rows=tuple(rows),
        status="PASS" if training_eligible else "BLOCKED",
        training_eligible=training_eligible,
        diagnostics=tuple(diagnostics),
        horizon_bars=horizon,
        dataset_hash=scientific_hash,
    )


def write_jsonl(result: MaterializationResult, output_path: str | Path) -> Path:
    """Escribe solo el material técnico solicitado; nunca escribe snapshots/gates."""
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(_jsonl_bytes(result.rows))
    return destination


def build_snapshot_manifest(
    result: MaterializationResult,
    dataset_path: str | Path,
    *,
    experiment_id: str,
    code_commit: str,
    artifact_paths: Sequence[str],
) -> dict[str, Any]:
    """Construye un manifest INF-2 únicamente después de elegibilidad explícita."""
    if not result.training_eligible:
        raise TrainingEligibilityError(
            "no se puede crear manifest de entrenamiento: " + "; ".join(result.diagnostics)
        )
    if not _HEX_COMMIT.fullmatch(code_commit):
        raise TrainingEligibilityError("code_commit inválido")
    data_hash = hash_dataset(dataset_path)
    return {
        "schema_version": "1.0",
        "experiment_id": experiment_id,
        "verdict": "PASS",
        "gate": {"causal": "PASS", "a7": "PASS", "scientific": "TRAINING_ELIGIBLE"},
        "dataset_hash": data_hash,
        "code_commit": code_commit,
        "scope": {"contract_version": CONTRACT_VERSION, "can_trade": False},
        "metrics": {"rows": len(result.rows), "horizon_bars": result.horizon_bars},
        "artifact_paths": list(artifact_paths),
        "produced_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "certifier": "D4-DATA-RESEARCH",
    }


def build_training_pipeline(
    snapshot: DatasetSnapshot | str | Path,
    *,
    registry: Any,
    checkpoint_store: Any,
    model_id: str,
    model_version: str,
    features: Sequence[str],
    labels: Sequence[str],
    seed: int,
    config: Mapping[str, Any],
    time_column: str = "event_time",
    train_fraction: float = 0.6,
    validation_fraction: float = 0.2,
) -> TrainingPipeline:
    """Reutiliza INF-2/INF-4; no ejecuta ``run`` ni entrena pesos."""
    loaded = load_dataset_snapshot(snapshot.snapshot_path if isinstance(snapshot, DatasetSnapshot) else snapshot)
    reader = CertifiedDatasetReader(loaded.snapshot_path.parent)
    reader.read_snapshot(loaded.snapshot_path)
    return TrainingPipeline(
        snapshot=loaded,
        registry=registry,
        checkpoint_store=checkpoint_store,
        model_id=model_id,
        model_version=model_version,
        features=features,
        labels=labels,
        seed=seed,
        config=config,
        time_column=time_column,
        train_fraction=train_fraction,
        validation_fraction=validation_fraction,
    )


def main() -> int:
    """Diagnóstico LOCAL_ONLY: no ejecuta feed, backtest ni entrenamiento."""
    root = ROOT
    backtest_path = root / "backtest" / "visual_backtest.json"
    funnel_path = root / "reports" / "audits" / "episodes" / "episodes_audit_20260830.json"
    a7_path = root / "reports" / "audits" / "experiments" / "fvg_ob" / "mtf_seq_funnel_a7_20260829_200059.json"
    print("[AI_OUTCOME][LOCAL_ONLY] materializador causal; no se escriben datasets ni snapshots")
    if not backtest_path.exists():
        print(f"[AI_OUTCOME][BLOCKED] BACKTEST_ARTIFACT_MISSING: {backtest_path}")
        print("[AI_OUTCOME][NEXT] exportar localmente el artefacto canónico congelado y volver a auditarlo")
        return 2
    try:
        result = materialize_outcome_rows(funnel_path, backtest_path, a7_report=a7_path)
    except OutcomeDatasetError as exc:
        print(f"[AI_OUTCOME][BLOCKED] {exc}")
        return 2
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.training_eligible else 2


__all__ = [
    "CONTRACT_VERSION",
    "MaterializationResult",
    "OutcomeDatasetError",
    "TrainingEligibilityError",
    "build_snapshot_manifest",
    "build_training_pipeline",
    "materialize_outcome_rows",
    "write_jsonl",
]


if __name__ == "__main__":
    raise SystemExit(main())
