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
from typing import Any, Mapping

from backtest.schema import validate_visual_backtest


CONTRACT_VERSION = "EPISODES_FUNNEL_V1"
_HEX_COMMIT = re.compile(r"^[0-9a-fA-F]{7,64}$")


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
) -> dict[str, Any]:
    """Link replay signals to trades without inventing Funnel acceptance."""

    payload = _load(backtest_artifact)
    try:
        validate_visual_backtest(payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise FunnelBridgeError(f"BACKTEST_SCHEMA_INVALID: {exc}") from exc
    if not _HEX_COMMIT.fullmatch(generator_commit):
        raise FunnelBridgeError("generator_commit inválido")

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
        episode_id = str(signal.get("episode_id") or f"EP_SIGNAL_{index + 1:06d}")
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


__all__ = ["CONTRACT_VERSION", "FunnelBridgeError", "build_funnel_artifact"]
