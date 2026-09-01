from __future__ import annotations

import copy

import pytest

from runtime.engine_registry import (
    EngineRegistryError,
    assert_daily_engine_safe,
    load_engine_registry,
    validate_engine_registry,
)


def test_default_registry_freezes_active_engine_and_lab_boundary():
    registry = load_engine_registry()
    active = assert_daily_engine_safe(registry)

    assert active["id"] == "GEN-000"
    assert active["policy"] == "OBSERVE_ONLY_NO_ORDER"
    assert active["promotion_locked"] is True
    assert registry["research_engine"]["may_replace_active"] is False


@pytest.mark.parametrize(
    "change",
    [
        {"active_engine": {"policy": "EXECUTE_ORDERS"}},
        {"active_engine": {"promotion_locked": False}},
        {"research_engine": {"may_replace_active": True}},
    ],
)
def test_registry_rejects_unsafe_authority_changes(change):
    registry = load_engine_registry()
    for section, values in change.items():
        registry[section] = {**registry[section], **values}

    with pytest.raises(EngineRegistryError):
        validate_engine_registry(registry)
