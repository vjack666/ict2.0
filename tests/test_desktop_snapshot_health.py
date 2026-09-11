from concurrent.futures import Future
from datetime import datetime, timezone
from copy import deepcopy

import pytest

from runtime.desktop_terminal.backend import TerminalRuntime
from runtime.desktop_terminal.snapshot_health import canonical_health, TF_SECONDS

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


def snapshot():
    return {"schema_version": "MT5_OPERATIONAL_SNAPSHOT_V1", "symbol": "EURUSD",
            "status": "READY", "missing_timeframes": [], "policy": "OBSERVE_ONLY_NO_ORDER",
            "can_trade": False, "entry_authorized": False, "decision_time": NOW.isoformat(),
            "asof_times_by_tf": {tf: datetime.fromtimestamp(NOW.timestamp() - seconds, timezone.utc).isoformat()
                                 for tf, seconds in TF_SECONDS.items()}}


def health(s, status="READY", feed="READY", now=NOW):
    return canonical_health({"snapshot": s, "status": status}, {"status": feed}, "EURUSD", now)


def test_diagnostic_is_valid_without_manufactured_signal():
    s = snapshot()
    original = deepcopy(s)
    assert health(s)["valid"] is True
    assert not health(s)["can_trade"]
    assert s == original
    assert "probability" not in s and "confirmed" not in s
    assert health(s, status="RUNNING")["valid"] is True


@pytest.mark.parametrize("field,value,code", [
    ("schema_version", "unknown", "CANONICAL_SCHEMA_INVALID"),
    ("symbol", "GBPUSD", "CANONICAL_SYMBOL_MISMATCH"),
    ("can_trade", True, "CANONICAL_POLICY_INVALID"),
    ("status", "BLOCKED", "CANONICAL_BLOCKED"),
    ("missing_timeframes", ["M1"], "CANONICAL_BLOCKED"),
    ("decision_time", "2026-09-10T12:00:00", "CANONICAL_TIME_INVALID"),
    ("decision_time", "2026-09-10T12:01:00+00:00", "CANONICAL_FUTURE"),
    ("decision_time", "2026-09-10T11:00:00+00:00", "CANONICAL_STALE"),
    ("asof_times_by_tf", {}, "CANONICAL_TIME_INVALID"),
])
def test_invalid_contract_fails_closed(field, value, code):
    s = snapshot()
    s[field] = value
    assert health(s)["code"] == code
    assert health(s)["valid"] is False


def test_closed_bars_must_precede_decision_and_be_fresh():
    s = snapshot()
    s["asof_times_by_tf"]["M15"] = NOW.isoformat()
    assert health(s)["code"] == "CANONICAL_UNCLOSED_BAR"
    s = snapshot()
    s["asof_times_by_tf"]["M1"] = "2026-09-10T11:00:00+00:00"
    assert health(s)["code"] == "CANONICAL_TF_STALE"


def test_failure_and_recovery_are_recomputed_on_every_http_read():
    runtime = TerminalRuntime()
    runtime.state["engine"] = {"status": "READY", "snapshot": snapshot()}
    assert health(None)["valid"] is False
    assert health(snapshot(), feed="STALE")["code"] == "CANONICAL_FEED_UNAVAILABLE"
    assert health(snapshot(), status="ERROR")["code"] == "CANONICAL_ENGINE_UNAVAILABLE"
    assert health(snapshot())["valid"] is True
    assert "canonical_snapshot_health" in runtime.snapshot(engine_version=0)


def test_diagnostic_never_publishes_mechanical_signal(tmp_path, monkeypatch):
    import runtime.desktop_terminal.backend as backend
    monkeypatch.setattr(backend, "ROOT", tmp_path)
    runtime = TerminalRuntime()
    assert runtime._publish_bot_snapshot(snapshot()) is False
    assert not (tmp_path / "runtime/mechanical_bot/latest_snapshot.json").exists()


def test_failed_engine_retries_same_bars_after_backoff(monkeypatch):
    import runtime.desktop_terminal.backend as backend
    clock = [100.0]
    monkeypatch.setattr(backend.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(backend.time, "time", lambda: NOW.timestamp())
    class Executor:
        calls = 0
        def submit(self, *args):
            self.calls += 1
            return Future()
    executor = Executor()
    runtime = TerminalRuntime(executor=executor)
    runtime.state["connection"] = {"status": "READY"}
    runtime.closed_bars = {tf: [{"time": NOW.timestamp() - seconds}] for tf, seconds in TF_SECONDS.items()}
    runtime.bars_signature = runtime.engine_signature = "unchanged"
    runtime.future = Future()
    runtime.future.set_exception(RuntimeError("transient failure"))
    runtime.poll_engine()
    assert runtime.state["engine"]["status"] == "ERROR"
    assert runtime.engine_signature is None and executor.calls == 0
    clock[0] += 4
    runtime.poll_engine()
    assert executor.calls == 0
    clock[0] += 1
    runtime.poll_engine()
    assert executor.calls == 1 and runtime.state["engine"]["status"] == "RUNNING"
    runtime.poll_engine()
    assert executor.calls == 1


def test_submit_error_is_engine_error_and_does_not_spin(monkeypatch):
    import runtime.desktop_terminal.backend as backend
    monkeypatch.setattr(backend.time, "time", lambda: NOW.timestamp())
    class Executor:
        def submit(self, *args):
            raise RuntimeError("unavailable worker")
    runtime = TerminalRuntime(executor=Executor())
    runtime.state["connection"] = {"status": "READY"}
    runtime.closed_bars = {"M1": [{"time": NOW.timestamp() - 60}]}
    runtime.bars_signature = "new"
    runtime.poll_engine()
    assert runtime.state["engine"]["status"] == "ERROR"
    assert runtime.state["engine"]["retry_after_seconds"] == 5


def test_broken_pool_is_replaced_with_backoff(monkeypatch):
    import runtime.desktop_terminal.backend as backend
    class Executor:
        closed = False
        def shutdown(self, **kwargs):
            self.closed = True
    old, replacement = Executor(), Executor()
    monkeypatch.setattr(backend, "ProcessPoolExecutor", lambda **kwargs: replacement)
    runtime = TerminalRuntime(executor=old)
    runtime._engine_failed(backend.BrokenProcessPool("worker died"))
    assert old.closed and runtime.executor is replacement
    assert runtime.engine_signature is None
    assert runtime.state["engine"]["retry_after_seconds"] == 5


def test_incremental_http_health_expires_without_new_engine_version(monkeypatch):
    import runtime.desktop_terminal.backend as backend
    clock = [NOW]
    monkeypatch.setattr(backend, "canonical_health", lambda e, c, s: canonical_health(e, c, s, clock[0]))
    runtime = TerminalRuntime()
    runtime.state["engine"] = {"snapshot": snapshot(), "status": "READY"}
    runtime.state["connection"] = {"status": "READY"}
    assert runtime.snapshot(engine_version=0)["canonical_snapshot_health"]["valid"] is True
    clock[0] = datetime.fromtimestamp(NOW.timestamp() + 181, timezone.utc)
    result = runtime.snapshot(engine_version=0)
    assert "snapshot" not in result["engine"]
    assert result["canonical_snapshot_health"]["code"] == "CANONICAL_STALE"
