from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

from scripts.mechanical_bot_dashboard import create_server
from scripts import start_mechanical_bot
from scripts.start_mechanical_bot import DEFAULT_TERMINAL_PATH, acquire_pid, release_pid


class FakeService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def status(self):
        return {"state": "OFF", "can_trade": False, "account": {"mode": "DEMO"}}

    def analyze_options(self):
        self.calls.append("analyze")
        return {"state": "WAIT_SIGNAL", "message": "analysis complete"}

    def arm(self):
        self.calls.append("arm")
        return {"state": "ARMED"}

    def disarm(self):
        self.calls.append("disarm")
        return {"state": "OFF"}

    def close_cycle(self):
        self.calls.append("close-cycle")
        return {"state": "CLOSING"}


def _request(url: str, data: bytes | None = None):
    return urllib.request.urlopen(url, data=data, timeout=2)


def test_dashboard_status_and_actions_are_local_and_mocked():
    service = FakeService()
    server = create_server(service, port=0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with _request(base + "/api/status") as response:
            assert response.status == 200
            assert json.loads(response.read())["state"] == "OFF"
        with _request(base + "/api/actions/arm", b"") as response:
            assert response.status == 200
            assert json.loads(response.read())["state"] == "ARMED"
        assert service.calls == ["arm"]
        try:
            _request(base + "/api/actions/not-real", b"")
        except urllib.error.HTTPError as exc:
            assert exc.code == 409
            assert json.loads(exc.read())["can_trade"] is False
        else:
            raise AssertionError("unknown action must be rejected")
    finally:
        server.shutdown()
        worker.join(timeout=2)
        server.server_close()


def test_dashboard_root_and_missing_chart_are_safe():
    server = create_server(FakeService(), port=0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with _request(base + "/") as response:
            html = response.read().decode("utf-8")
            assert "Encender bot" in html
            assert "M5/M1 se muestran solo como diagnóstico" in html
        try:
            _request(base + "/charts/INVALID")
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
        else:
            raise AssertionError("unlisted chart must not be served")
    finally:
        server.shutdown()
        worker.join(timeout=2)
        server.server_close()


def test_pid_lock_recovers_stale_file_and_does_not_remove_foreign_pid(tmp_path: Path, monkeypatch):
    pid_file = tmp_path / "dashboard.pid"
    pid_file.write_text("999999", encoding="utf-8")
    monkeypatch.setattr("scripts.start_mechanical_bot.pid_is_running", lambda _pid: False)
    assert acquire_pid(pid_file) is True
    assert pid_file.read_text(encoding="utf-8")
    pid_file.write_text("123456", encoding="utf-8")
    release_pid(pid_file)
    assert pid_file.exists()


def test_launcher_does_not_start_a_second_dashboard(tmp_path: Path, monkeypatch):
    pid_file = tmp_path / "dashboard.pid"
    monkeypatch.setattr(start_mechanical_bot, "acquire_pid", lambda _path: False)
    assert start_mechanical_bot.main(["--pid-file", str(pid_file)]) == 0


def test_launcher_selects_an_explicit_mt5_terminal_by_default():
    assert DEFAULT_TERMINAL_PATH.name.lower() == "terminal64.exe"
