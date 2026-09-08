from datetime import datetime, timezone
import json
from threading import Event, Thread

from mechanical_bot.core import BotAction, BotConfig, Cycle, Position, Snapshot
from mechanical_bot.mt5_adapter import AccountStatus
from mechanical_bot.service import MechanicalBotService


class FakeAdapter:
    execution_enabled = False

    def __init__(self):
        self._positions = []

    def account_status(self):
        return AccountStatus(123, "Demo", 1_000.0, 1_000.0, True)

    def closed_m15_candles(self, _symbol):
        return []

    def tick_price(self, _symbol, _side):
        return 1.1

    def positions(self):
        return list(self._positions)

    def execute(self, action, **_kwargs):
        if action.kind == "CLOSE_ALL":
            self._positions = []
        return [{"kind": action.kind}]


class RealAccountAdapter(FakeAdapter):
    def account_status(self):
        return AccountStatus(456, "Broker-Live", 1_000.0, 990.0, False)


def test_service_is_off_by_default_and_reports_demo_account(tmp_path):
    service = MechanicalBotService(adapter=FakeAdapter(), snapshot_path=tmp_path / "missing.json", state_path=tmp_path / "state.json", log_path=tmp_path / "events.jsonl")
    status = service.status()
    assert status["state"] == "OFF"
    assert status["account"]["environment"] == "DEMO"
    assert status["m5_m1"] == "DIAGNOSTIC_ONLY_NO_VETO"
    assert service.analyze()["snapshot"] is None


def test_manual_close_executes_only_bot_cycle_and_records_event(tmp_path):
    log = tmp_path / "events.jsonl"
    adapter = FakeAdapter()
    adapter._positions = [Position("EURUSD", 26090615, "BUY", .1, 1.1, 0)]
    service = MechanicalBotService(BotConfig(enabled=True), adapter=adapter, snapshot_path=tmp_path / "snap.json", state_path=tmp_path / "state.json", log_path=log)
    service.bot.cycle = Cycle("BUY", 1.1, 1_000, datetime.now(timezone.utc))
    state = service.close_cycle()
    assert state["state"] == "CLOSED"
    assert json.loads(log.read_text(encoding="utf-8").splitlines()[-1])["event"] == "CLOSE_ALL"


def test_close_with_no_owned_positions_stays_error_and_preserves_cycle(tmp_path):
    service = MechanicalBotService(BotConfig(enabled=True), adapter=FakeAdapter(), snapshot_path=tmp_path / "snap.json", state_path=tmp_path / "state.json", log_path=tmp_path / "events.jsonl")
    service.bot.cycle = Cycle("BUY", 1.1, 1_000, datetime.now(timezone.utc))
    try:
        service.close_cycle()
    except RuntimeError as exc:
        assert "no matching" in str(exc)
    else:
        raise AssertionError("unreconciled close must fail")
    assert service.bot.state.value == "ERROR" and service.bot.cycle is not None


def test_snapshot_reader_requires_all_fields(tmp_path):
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps({"direction": "BUY"}), encoding="utf-8")
    service = MechanicalBotService(adapter=FakeAdapter(), snapshot_path=path, state_path=tmp_path / "state.json", log_path=tmp_path / "events.jsonl")
    assert service._load_snapshot() is None
    path.write_text(json.dumps({"direction": "BUY", "probability": .7, "confirmed": True, "asof_time": datetime.now(timezone.utc).isoformat(), "symbol": "EURUSD"}), encoding="utf-8")
    assert service._load_snapshot().normalized_direction() == "BUY"


def test_snapshot_reader_rejects_string_boolean_and_missing_symbol(tmp_path):
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps({"direction": "BUY", "probability": .7, "confirmed": "false", "asof_time": datetime.now(timezone.utc).isoformat(), "symbol": "EURUSD"}), encoding="utf-8")
    service = MechanicalBotService(adapter=FakeAdapter(), snapshot_path=path, state_path=tmp_path / "state.json", log_path=tmp_path / "events.jsonl")
    assert service._load_snapshot() is None
    path.write_text(json.dumps({"direction": "BUY", "probability": .7, "confirmed": True, "asof_time": datetime.now(timezone.utc).isoformat()}), encoding="utf-8")
    assert service._load_snapshot() is None


def test_analysis_exposes_context_but_keeps_m5_m1_diagnostic_only(tmp_path):
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps({"direction": "BUY", "probability": .70, "confirmed": True,
        "asof_time": datetime.now(timezone.utc).isoformat(), "symbol": "EURUSD",
        "context_state": {"D1": "BULLISH", "H4": "BULLISH"}, "zones": [{"kind": "OB"}],
        "bos": [{"direction": "BUY"}], "m5_m1": {"M5": "NOT_CONFIRMED", "M1": "NOT_CONFIRMED"}}), encoding="utf-8")
    service = MechanicalBotService(adapter=FakeAdapter(), snapshot_path=path, state_path=tmp_path / "state.json", log_path=tmp_path / "events.jsonl")
    analysis = service.analyze()
    assert analysis["context"]["context_state"]["H4"] == "BULLISH"
    assert analysis["context"]["m5_m1"]["M5"] == "NOT_CONFIRMED"


def test_real_account_is_visible_as_a_persistent_warning(tmp_path):
    service = MechanicalBotService(adapter=RealAccountAdapter(), snapshot_path=tmp_path / "missing.json", state_path=tmp_path / "state.json", log_path=tmp_path / "events.jsonl")
    account = service.status()["account"]
    assert account["environment"] == "REAL"
    assert account["real_account_warning"] is True


def test_restart_restores_cycle_but_fails_closed_until_rearmed(tmp_path):
    state = tmp_path / "state.json"
    service = MechanicalBotService(BotConfig(enabled=True), adapter=FakeAdapter(), snapshot_path=tmp_path / "snap.json", state_path=state, log_path=tmp_path / "events.jsonl")
    service.bot.cycle = Cycle("BUY", 1.1, 1_000, datetime.now(timezone.utc), entries=2)
    service._persist_state()
    recovered = MechanicalBotService(BotConfig(enabled=True), adapter=FakeAdapter(), snapshot_path=tmp_path / "snap.json", state_path=state, log_path=tmp_path / "events.jsonl")
    assert recovered.bot.state.value == "OFF"
    assert recovered.bot.cycle is not None and recovered.bot.cycle.entries == 2


def test_disarm_waits_for_running_tick_and_blocks_later_execution(tmp_path, monkeypatch):
    class BlockingAdapter(FakeAdapter):
        execution_enabled = True
        def __init__(self):
            super().__init__()
            self.started, self.release = Event(), Event()
            self.executions = 0
        def execute(self, action, **kwargs):
            self.executions += 1
            self.started.set()
            self.release.wait(timeout=2)
            return super().execute(action, **kwargs)

    adapter = BlockingAdapter()
    service = MechanicalBotService(BotConfig(enabled=True), adapter=adapter, snapshot_path=tmp_path / "snap.json", state_path=tmp_path / "state.json", log_path=tmp_path / "events.jsonl")
    service.bot.arm()
    monkeypatch.setattr(service, "_load_snapshot", lambda: Snapshot("BUY", .7, True, datetime.now(timezone.utc), "EURUSD"))
    monkeypatch.setattr(service.bot, "decide_entry", lambda *_args: BotAction("OPEN", "test", "BUY", .1))
    tick_thread = Thread(target=service.tick)
    tick_thread.start(); assert adapter.started.wait(timeout=1)
    disarm_thread = Thread(target=service.disarm)
    disarm_thread.start(); assert disarm_thread.is_alive()
    adapter.release.set()
    tick_thread.join(timeout=2); disarm_thread.join(timeout=2)
    assert service.status()["state"] == "OFF"
    service.tick()
    assert adapter.executions == 1
