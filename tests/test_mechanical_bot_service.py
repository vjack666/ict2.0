from datetime import datetime, timezone
import json

from mechanical_bot.core import BotConfig, Cycle
from mechanical_bot.mt5_adapter import AccountStatus
from mechanical_bot.service import MechanicalBotService


class FakeAdapter:
    execution_enabled = False

    def account_status(self):
        return AccountStatus(123, "Demo", 1_000.0, 1_000.0, True)

    def closed_m15_candles(self, _symbol):
        return []

    def tick_price(self, _symbol, _side):
        return 1.1

    def positions(self):
        return []

    def execute(self, action, **_kwargs):
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
    service = MechanicalBotService(BotConfig(enabled=True), adapter=FakeAdapter(), snapshot_path=tmp_path / "snap.json", state_path=tmp_path / "state.json", log_path=log)
    service.bot.cycle = Cycle("BUY", 1.1, 1_000, datetime.now(timezone.utc))
    state = service.close_cycle()
    assert state["state"] == "CLOSED"
    assert json.loads(log.read_text(encoding="utf-8").splitlines()[-1])["event"] == "CLOSE_ALL"


def test_snapshot_reader_requires_all_fields(tmp_path):
    path = tmp_path / "snapshot.json"
    path.write_text(json.dumps({"direction": "BUY"}), encoding="utf-8")
    service = MechanicalBotService(adapter=FakeAdapter(), snapshot_path=path, state_path=tmp_path / "state.json", log_path=tmp_path / "events.jsonl")
    assert service._load_snapshot() is None
    path.write_text(json.dumps({"direction": "BUY", "probability": .7, "confirmed": True, "asof_time": datetime.now(timezone.utc).isoformat(), "symbol": "EURUSD"}), encoding="utf-8")
    assert service._load_snapshot().normalized_direction() == "BUY"


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
