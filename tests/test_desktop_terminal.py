from concurrent.futures import Future
import json
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from runtime.desktop_terminal.backend import TerminalRuntime, normalize_rates
from runtime.desktop_terminal.server import create_server


def bar(stamp, **extra):
    return {"time": stamp, "open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15, "tick_volume": 17, **extra}


def test_closed_boundary_never_passes_open_bar_to_engine():
    closed, opened = normalize_rates([bar(60), bar(120)], "M1", 160)
    assert [b["time"] for b in closed] == [60]
    assert opened["time"] == 120
    closed, opened = normalize_rates([bar(60), bar(120)], "M1", 180)
    assert len(closed) == 2 and opened is None


@pytest.mark.parametrize("rows", [[bar(120), bar(60)], [bar(60), bar(60)], [bar(60, high=float("nan"))], [bar(60, low=1.16)]])
def test_invalid_bars_rejected(rows):
    with pytest.raises(ValueError):
        normalize_rates(rows, "M1", 200)


def test_candle_cache_is_bounded():
    closed, _ = normalize_rates([bar(i * 60) for i in range(1, 900)], "M1", 60000)
    assert len(closed) == 400


def test_explicit_broker_offset_preserves_closed_bar_boundary():
    closed, opened = normalize_rates([bar(10860), bar(10920)], "M1", 160, 10800)
    assert closed[0]["time"] == 60
    assert opened["time"] == 120


def test_engine_does_not_queue_multiple_jobs_or_block_cache():
    runtime = TerminalRuntime()
    runtime.future = Future()  # deliberately unfinished calculation
    runtime.state["tick"] = {"bid": 1.1}
    runtime.poll_engine()
    assert runtime.snapshot()["tick"]["bid"] == 1.1
    assert not runtime.future.done()


def test_state_is_detached():
    runtime = TerminalRuntime()
    body = runtime.snapshot()
    body["bot"]["state"] = "ARMED"
    assert runtime.snapshot()["bot"]["state"] == "OFF"


def test_incremental_response_omits_only_unchanged_heavy_payloads():
    runtime = TerminalRuntime()
    result = runtime.snapshot(bars_version=0, engine_version=0)
    assert "candles_by_tf" not in result
    assert "snapshot" not in result["engine"]
    assert "tick" in result and "open_candles_by_tf" in result
    full = runtime.snapshot(bars_version=-1, engine_version=-1)
    assert "candles_by_tf" in full and "snapshot" in full["engine"]


def test_disabled_actions_and_missing_producer_fail_closed():
    class Service:
        enabled = False
        def status(self):
            return {"execution_enabled": self.enabled}
        def _load_snapshot(self):
            return None
        def arm(self):
            pytest.fail("Must never arm")
    service = Service()
    runtime = TerminalRuntime(service=service)
    with pytest.raises(RuntimeError, match="EXECUTION_DISABLED"):
        runtime.action("arm")
    service.enabled = True
    with pytest.raises(RuntimeError, match="WAIT_SNAPSHOT"):
        runtime.action("arm")


def test_demo_wait_arms_without_fabricating_snapshot():
    class Service:
        demo_wait_enabled = True
        def status(self):
            return {"execution_enabled": True}
        def arm(self):
            return {"state": "ARMED", "snapshot": None}
    runtime = TerminalRuntime(service=Service())
    result = runtime.action("arm")
    assert result["state"] == "ARMED"
    assert result["snapshot"] is None


def test_http_origin_token_and_path_boundary(tmp_path):
    (tmp_path / "index.html").write_text("<h1>ICT</h1>")
    runtime = TerminalRuntime()
    server = create_server(runtime, port=0, ui_dist=tmp_path)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(base + "/api/state") as response:
            assert json.load(response)["bot"]["execution_enabled"] is False
        for headers in ({}, {"X-ICT-Token": runtime.token, "Origin": "https://evil.example"}):
            with pytest.raises(HTTPError) as exc:
                urlopen(Request(base + "/api/actions/analyze", method="POST", headers=headers))
            assert exc.value.code == 403
        with urlopen(Request(base + "/api/actions/analyze", method="POST", headers={"X-ICT-Token": runtime.token, "Origin": base})) as response:
            assert json.load(response)["ok"] is True
        assert runtime.refresh_event.is_set()
        with urlopen(base + "/api/documents") as response:
            assert "docs/tesis/SDD_DESKTOP_TERMINAL.md" in json.load(response)["documents"]
        with pytest.raises(HTTPError) as exc:
            urlopen(base + "/api/document?path=../../secrets.txt")
        assert exc.value.code == 404
        with pytest.raises(HTTPError) as exc:
            urlopen(base + "/%2e%2e/backend.py")
        assert exc.value.code == 404
        with pytest.raises(HTTPError) as exc:
            urlopen(Request(base + "/api/state", headers={"Host": "evil.example"}))
        assert exc.value.code == 403
    finally:
        server.shutdown()
        server.server_close()
        worker.join(2)
