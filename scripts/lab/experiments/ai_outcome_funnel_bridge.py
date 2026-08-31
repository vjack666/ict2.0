"""Construye el artefacto Episodes/Funnel desde señales del replay canónico.

Este adaptador no crea señales ni recalcula outcomes. Solo enlaza los records
``signals`` y ``trades`` que el backtest ya produjo mediante ``signal_index`` y
expone las features PIT serializadas por el replay. La salida permanece
``BLOCKED`` si el backtest no aporta una prueba FULL/PREFIX explícita.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping

from backtest.schema import validate_visual_backtest


CONTRACT_VERSION = "EPISODES_FUNNEL_V1"
ROOT = Path(__file__).resolve().parents[3]
_HEX_COMMIT = re.compile(r"^[0-9a-fA-F]{7,64}$")
_NAMESPACE = re.compile(r"^[A-Za-z0-9_-]{1,48}$")


class FunnelBridgeError(ValueError):
    """Entrada del replay o lineage insuficiente para formar el Funnel."""


def _load(value: Mapping[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return deepcopy(dict(value))
    try:
        payload = json.loads(Path(value).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FunnelBridgeError(f"backtest ilegible: {value}") from exc
    if not isinstance(payload, Mapping):
        raise FunnelBridgeError("backtest debe ser un objeto JSON")
    return dict(payload)


def _canonical_hash(value: Any) -> str:
    body = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(body).hexdigest()


def build_funnel_artifact(
    backtest_artifact: Mapping[str, Any] | str | Path,
    *,
    generator_commit: str,
    episode_namespace: str | None = None,
) -> dict[str, Any]:
    """Link replay signals to trades without inventing Funnel acceptance."""

    payload = _load(backtest_artifact)
    try:
        validate_visual_backtest(payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise FunnelBridgeError(f"BACKTEST_SCHEMA_INVALID: {exc}") from exc
    if not _HEX_COMMIT.fullmatch(generator_commit):
        raise FunnelBridgeError("generator_commit inválido")
    if episode_namespace is not None and not _NAMESPACE.fullmatch(episode_namespace):
        raise FunnelBridgeError("episode_namespace inválido")

    metadata = payload.get("metadata")
    signals = payload.get("signals")
    trades = payload.get("trades")
    if not isinstance(metadata, Mapping) or metadata.get("causal") is not True:
        raise FunnelBridgeError("BACKTEST_CAUSAL_METADATA_MISSING")
    if not isinstance(signals, list) or not signals:
        raise FunnelBridgeError("BACKTEST_SIGNALS_MISSING")
    if not isinstance(trades, list):
        raise FunnelBridgeError("BACKTEST_TRADES_INVALID")

    by_signal: dict[int, list[Mapping[str, Any]]] = {}
    for trade in trades:
        if not isinstance(trade, Mapping) or not isinstance(trade.get("signal_index"), int):
            continue
        by_signal.setdefault(int(trade["signal_index"]), []).append(trade)

    episodes: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[int] = set()
    for signal in signals:
        if not isinstance(signal, Mapping):
            rejected.append({"reason": "SIGNAL_NOT_OBJECT"})
            continue
        index = signal.get("signal_index")
        if isinstance(index, bool) or not isinstance(index, int) or index in seen:
            rejected.append({"signal_index": index, "reason": "SIGNAL_ID_INVALID_OR_DUPLICATE"})
            continue
        seen.add(index)
        candidates = by_signal.get(index, [])
        if len(candidates) != 1:
            rejected.append({"signal_index": index, "reason": "BACKTEST_TRADE_MISSING_OR_AMBIGUOUS"})
            continue
        features = signal.get("features_at_t")
        if not isinstance(features, Mapping):
            rejected.append({"signal_index": index, "reason": "MISSING_FEATURES_AT_T"})
            continue
        base_episode_id = str(signal.get("episode_id") or f"EP_SIGNAL_{index + 1:06d}")
        episode_id = (
            f"{episode_namespace}__{base_episode_id}"
            if episode_namespace else base_episode_id
        )
        event_time = signal.get("decision_time")
        if not isinstance(event_time, str) or not event_time:
            rejected.append({"signal_index": index, "reason": "MISSING_DECISION_TIME"})
            continue
        direction = signal.get("direction")
        if direction not in (-1, 1):
            rejected.append({"signal_index": index, "reason": "INVALID_DIRECTION"})
            continue
        episodes.append({
            "episode_id": episode_id,
            "contract_version": CONTRACT_VERSION,
            "stage": "EPISODE",
            "status": "ACCEPTED",
            "reason": "",
            "symbol": payload.get("symbol", ""),
            "decision_time": event_time,
            "direction": int(direction),
            "features_at_t": deepcopy(dict(features)),
            "lineage": deepcopy(dict(signal.get("lineage") or {})),
            "object_refs": sorted((signal.get("event_objects") or {}).keys()),
            "meta": {"backtest_signal_index": index},
        })

    prefix = metadata.get("full_prefix")
    prefix_pass = isinstance(prefix, Mapping) and prefix.get("prefix_matches_full") is True
    gates = {
        "E0": "PASS" if episodes else "BLOCKED",
        "E1": "PASS" if not rejected else "BLOCKED",
        "causal_full_vs_prefix": "PASS" if prefix_pass else "BLOCKED",
    }
    status = "PASS" if episodes and not rejected and prefix_pass else "BLOCKED"
    artifact = {
        "contract_version": CONTRACT_VERSION,
        "aggregated_status": status,
        "gates": gates,
        "full_prefix": {"prefix_matches_full": prefix_pass},
        "generator_commit": generator_commit,
        "provenance": deepcopy(dict(metadata.get("provenance") or {})),
        "episodes": episodes,
        "records": episodes + rejected,
        "rejections": rejected,
        "backtest_linkage": {
            "artifact_kind": "canonical_replay_signal_trade_link",
            "trade_key": "signal_index",
            "outcome_not_copied_into_features": True,
        },
    }
    artifact["checksum"] = _canonical_hash(artifact)
    return artifact


def write_funnel_artifact(
    backtest_artifact: Mapping[str, Any] | str | Path,
    output: str | Path,
    *,
    generator_commit: str,
    episode_namespace: str | None = None,
) -> dict[str, Any]:
    """Build and write one immutable Episodes/Funnel bridge artifact."""

    destination = Path(output).resolve()
    if destination.suffix.lower() != ".json":
        raise FunnelBridgeError("output debe ser JSON")
    if destination.exists():
        raise FunnelBridgeError(f"output ya existe y no se sobrescribe: {destination}")
    artifact = build_funnel_artifact(
        backtest_artifact,
        generator_commit=generator_commit,
        episode_namespace=episode_namespace,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return artifact


def _git_commit() -> str:
    try:
        value = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.STDOUT
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise FunnelBridgeError("no se pudo determinar el commit del bridge") from exc
    if not _HEX_COMMIT.fullmatch(value):
        raise FunnelBridgeError("commit del bridge inválido")
    return value


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backtest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--generator-commit", help="Commit que contiene el bridge")
    parser.add_argument(
        "--episode-namespace",
        help="Prefijo determinista para evitar colisiones al unir particiones",
    )
    args = parser.parse_args(argv)
    try:
        artifact = write_funnel_artifact(
            args.backtest,
            args.output,
            generator_commit=args.generator_commit or _git_commit(),
            episode_namespace=args.episode_namespace,
        )
    except (FunnelBridgeError, OSError) as exc:
        print(f"[AI_OUTCOME_FUNNEL][BLOCKED] {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "status": artifact["aggregated_status"],
        "output": str(args.output),
        "episodes": len(artifact["episodes"]),
        "rejections": len(artifact["rejections"]),
        "gates": artifact["gates"],
    }, ensure_ascii=False, sort_keys=True))
    return 0 if artifact["aggregated_status"] == "PASS" else 2


__all__ = [
    "CONTRACT_VERSION",
    "FunnelBridgeError",
    "build_funnel_artifact",
    "write_funnel_artifact",
]


if __name__ == "__main__":
    raise SystemExit(main())
