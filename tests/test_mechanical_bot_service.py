from datetime import datetime, timedelta, timezone
import json
from threading import Event, Thread

import pytest

from mechanical_bot.core import BotAction, BotConfig, BotState, Cycle, Position, Snapshot, StochasticReading
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
    assert status["adapter_configured"] is True
    assert status["account"]["environment"] == "DEMO"
    assert status["m5_m1"] == "DIAGNOSTIC_ONLY_NO_VETO"
    analysis = service.analyze()
    assert analysis["snapshot"] is None
    assessment = analysis["signal_assessment"]
    assert assessment["status"] == "NO_SIGNAL"
    assert assessment["code"] == "MECHANICAL_PRODUCER_UNAVAILABLE"
    assert assessment["entry_authorized"] is False
    assert assessment["required_fields"] == ["symbol", "direction", "probability", "confirmed", "asof_time"]


def test_invalid_mechanical_snapshot_explains_contract_failure_without_authorizing_entry(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps({"symbol": "EURUSD", "direction": "BUY"}), encoding="utf-8")
    service = MechanicalBotService(adapter=FakeAdapter(), snapshot_path=path,
                                   state_path=tmp_path / "state.json", log_path=tmp_path / "events.jsonl")
    assessment = service.analyze()["signal_assessment"]
    assert assessment["status"] == "NO_SIGNAL"
    assert assessment["code"] == "MECHANICAL_SNAPSHOT_INVALID"
    assert assessment["missing_fields"] == ["probability", "confirmed", "asof_time"]
    assert assessment["entry_authorized"] is False


def test_valid_mechanical_snapshot_is_only_a_candidate_until_readiness_passes(tmp_path):
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps({"symbol": "EURUSD", "direction": "BUY", "probability": .70,
                                "confirmed": True, "asof_time": datetime.now(timezone.utc).isoformat()}), encoding="utf-8")
    service = MechanicalBotService(adapter=FakeAdapter(), snapshot_path=path,
                                   state_path=tmp_path / "state.json", log_path=tmp_path / "events.jsonl")
    assessment = service.analyze()["signal_assessment"]
    assert assessment["status"] == "CANDIDATE_SIGNAL"
    assert assessment["entry_authorized"] is False


def test_missing_snapshot_arms_into_wait_signal_and_records_black_box_decision(tmp_path):
    blackbox = tmp_path / "blackbox.jsonl"
    service = MechanicalBotService(
        BotConfig(enabled=True), adapter=FakeAdapter(), snapshot_path=tmp_path / "missing.json",
        state_path=tmp_path / "state.json", log_path=tmp_path / "events.jsonl", blackbox_path=blackbox,
    )
    service.arm()
    status = service.tick()
    assert status["state"] == "WAIT_SIGNAL"
    decision = json.loads(blackbox.read_text(encoding="utf-8").splitlines()[-1])
    assert decision["event"] == "DECISION"
    assert decision["reason"] == "WAIT_DIRECTION"
    assert decision["raw_snapshot_hash"] is None
    assert status["black_box"]["path"] == str(blackbox)


def test_poi_observation_contract_with_can_trade_false_cannot_reach_adapter(tmp_path):
    class EnabledAdapter(FakeAdapter):
        execution_enabled = True
        executions = 0

        def execute(self, action, **kwargs):
            self.executions += 1
            return super().execute(action, **kwargs)

    path = tmp_path / "poi-observation.json"
    path.write_text(json.dumps({
        "schema_version": "POI_STOCH_M15_OBSERVATION_SNAPSHOT_V1",
        "symbol": "EURUSD",
        "asof_time": datetime.now(timezone.utc).isoformat(),
        "object_projection": [],
        "can_trade": False,
        "entry_authorized": False,
    }), encoding="utf-8")
    blackbox = tmp_path / "blackbox.jsonl"
    adapter = EnabledAdapter()
    service = MechanicalBotService(BotConfig(enabled=True), adapter=adapter, snapshot_path=path,
                                   state_path=tmp_path / "state.json", log_path=tmp_path / "events.jsonl",
                                   blackbox_path=blackbox)
    service.arm()
    status = service.tick()
    assert status["state"] == "WAIT_SIGNAL"
    assert adapter.executions == 0
    decision = json.loads(blackbox.read_text(encoding="utf-8").splitlines()[-1])
    assert decision["reason"] == "CAN_TRADE_FALSE"


def test_canonical_signal_assessment_is_recorded_with_its_source_hash(tmp_path):
    blackbox = tmp_path / "blackbox.jsonl"
    service = MechanicalBotService(
        adapter=FakeAdapter(), snapshot_path=tmp_path / "missing.json", state_path=tmp_path / "state.json",
        log_path=tmp_path / "events.jsonl", blackbox_path=blackbox,
    )
    canonical = {"source": "MT5_LOCAL", "decision_time": "2026-09-11T15:00:00+00:00", "can_trade": False}
    assessment = {"status": "NO_SIGNAL", "code": "NO_SWEEP", "entry_authorized": False}
    service.record_signal_assessment(assessment, canonical)
    record = json.loads(blackbox.read_text(encoding="utf-8").splitlines()[-1])
    assert record["event"] == "SIGNAL_ASSESSMENT"
    assert record["assessment"] == assessment
    assert record["snapshot_source"] == "MT5_LOCAL"
    assert len(record["canonical_snapshot_hash"]) == 64


def test_rejected_snapshot_abstains_without_killing_runner_state(tmp_path):
    path = tmp_path / "snap.json"
    path.write_text(json.dumps({
        "symbol": "EURUSD", "direction": "BUY", "probability": 2.0, "confirmed": True,
        "asof_time": datetime.now(timezone.utc).isoformat(),
    }), encoding="utf-8")
    blackbox = tmp_path / "blackbox.jsonl"
    service = MechanicalBotService(BotConfig(enabled=True), adapter=FakeAdapter(), snapshot_path=path,
                                  state_path=tmp_path / "state.json", log_path=tmp_path / "events.jsonl", blackbox_path=blackbox)
    service.arm()
    status = service.tick()
    assert status["state"] == "WAIT_SIGNAL"
    decision = json.loads(blackbox.read_text(encoding="utf-8").splitlines()[-1])
    assert decision["reason"].startswith("SNAPSHOT_REJECTED:")
    assert decision["stochastic"] is None


def test_entry_session_blocks_only_new_entries_and_keeps_wait_signal(tmp_path):
    service = MechanicalBotService(BotConfig(enabled=True), adapter=FakeAdapter(), snapshot_path=tmp_path / "missing.json",
                                  state_path=tmp_path / "state.json", log_path=tmp_path / "events.jsonl",
                                  blackbox_path=tmp_path / "blackbox.jsonl", entry_sessions_enabled=True)
    service._session_schedule = lambda: {"enabled": True, "sessions": [{"name": "LONDON", "active": False}, {"name": "NEW_YORK", "active": False}]}  # type: ignore[method-assign]
    service.arm()
    assert service.tick()["state"] == "WAIT_SIGNAL"
    decision = json.loads((tmp_path / "blackbox.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert decision["reason"] == "OUTSIDE_ENTRY_WINDOW"


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


def _readiness_service(tmp_path, payload, *, sessions=False):
    path = tmp_path / "snapshot.json"
    if payload is not None:
        path.write_text(json.dumps(payload), encoding="utf-8")

    class ReadinessAdapter(FakeAdapter):
        execution_enabled = True

    return MechanicalBotService(BotConfig(enabled=True), adapter=ReadinessAdapter(), snapshot_path=path,
                                state_path=tmp_path / "state.json", log_path=tmp_path / "events.jsonl",
                                entry_sessions_enabled=sessions)


def _ready_payload(**overrides):
    payload = {"symbol": "EURUSD", "direction": "bullish", "probability": .70, "confirmed": True,
               "asof_time": datetime.now(timezone.utc).isoformat()}
    payload.update(overrides)
    return payload


def _gate(analysis, identifier):
    return next(item for item in analysis["readiness"]["gates"] if item["id"] == identifier)


def test_readiness_allows_scan_with_execution_disabled_but_keeps_execution_gate_closed(tmp_path):
    service = _readiness_service(tmp_path, _ready_payload())
    service.adapter.execution_enabled = False
    analysis = service.analyze()
    gate = _gate(analysis, "execution_enabled")
    assert gate["passed"] is False and gate["code"] == "EXECUTION_DISABLED"
    assert analysis["readiness"]["scan_can_start"] is True


def test_disabled_execution_runner_records_observation_without_creating_an_order(tmp_path):
    blackbox = tmp_path / "blackbox.jsonl"
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(json.dumps(_ready_payload()), encoding="utf-8")
    service = MechanicalBotService(BotConfig(enabled=True), adapter=FakeAdapter(),
                                  snapshot_path=snapshot, state_path=tmp_path / "state.json",
                                  log_path=tmp_path / "events.jsonl", blackbox_path=blackbox)
    service.arm()
    status = service.tick()
    decision = json.loads(blackbox.read_text(encoding="utf-8").splitlines()[-1])
    assert status["state"] == "WAIT_SIGNAL"
    assert status["cycle"] is None
    assert decision["event"] == "DECISION"
    assert decision["reason"] == "EXECUTION_DISABLED_SCAN_ONLY"


@pytest.mark.parametrize(("payload", "code"), [
    (None, "SNAPSHOT_MISSING"),
    (_ready_payload(asof_time="not-a-timestamp"), "SNAPSHOT_INVALID"),
    (_ready_payload(symbol="GBPUSD"), "SNAPSHOT_SYMBOL_MISMATCH"),
    (_ready_payload(asof_time=(datetime.now(timezone.utc) + timedelta(minutes=21)).isoformat()), "SNAPSHOT_FUTURE"),
    (_ready_payload(asof_time=(datetime.now(timezone.utc) - timedelta(minutes=21)).isoformat()), "SNAPSHOT_STALE"),
])
def test_readiness_reports_snapshot_gate_failures(tmp_path, payload, code):
    service = _readiness_service(tmp_path, payload)
    gate = _gate(service.analyze(), "snapshot")
    assert gate["passed"] is False and gate["code"] == code
    assert "age_seconds" in gate["observed"]
    assert gate["required"]["max_age_seconds"] == service.bot.config.stale_after.total_seconds()


@pytest.mark.parametrize(("payload", "identifier", "code"), [
    (_ready_payload(direction="SIDEWAYS"), "direction", "DIRECTION_INVALID"),
    (_ready_payload(probability=.69), "probability", "PROBABILITY_BELOW_MINIMUM"),
    (_ready_payload(probability=float("nan")), "probability", "PROBABILITY_INVALID"),
    (_ready_payload(probability=".70"), "probability", "PROBABILITY_INVALID"),
])
def test_readiness_reports_direction_and_probability_failures(tmp_path, payload, identifier, code):
    service = _readiness_service(tmp_path, payload)
    gate = _gate(service.analyze(), identifier)
    assert gate["passed"] is False and gate["code"] == code


def test_readiness_reports_missing_confirmation_reading_and_cross(tmp_path, monkeypatch):
    service = _readiness_service(tmp_path, _ready_payload(confirmed=False))
    assert _gate(service.analyze(), "m15_confirmation")["code"] == "M15_CONFIRMATION_MISSING"

    service = _readiness_service(tmp_path, _ready_payload())
    assert _gate(service.analyze(), "m15_confirmation")["code"] == "M15_READING_MISSING"

    incompatible = StochasticReading(k=50, d=40, previous_k=35, previous_d=30)
    monkeypatch.setattr("mechanical_bot.service.stochastic_14_3_3", lambda *_args: incompatible)
    assert _gate(service.analyze(), "m15_confirmation")["code"] == "M15_CROSS_INCOMPATIBLE"


def test_readiness_reports_session_gate_and_all_ready(tmp_path, monkeypatch):
    service = _readiness_service(tmp_path, _ready_payload(), sessions=True)
    service._session_schedule = lambda: {"enabled": True, "sessions": [{"name": "LONDON", "active": False}]}  # type: ignore[method-assign]
    assert _gate(service.analyze(), "session")["code"] == "OUTSIDE_ENTRY_WINDOW"

    service._session_schedule = lambda: {"enabled": True, "sessions": [{"name": "LONDON", "active": True}]}  # type: ignore[method-assign]
    bullish_cross = StochasticReading(k=25, d=20, previous_k=15, previous_d=15)
    monkeypatch.setattr("mechanical_bot.service.stochastic_14_3_3", lambda *_args: bullish_cross)
    analysis = service.analyze()
    readiness = analysis["readiness"]
    assert readiness["ready"] is True
    assert [item["id"] for item in readiness["gates"]] == ["execution_enabled", "snapshot", "direction", "probability", "m15_confirmation", "session"]
    assert readiness["evaluated_at"].endswith("+00:00")


def test_readiness_marks_disabled_session_gate_as_not_required(tmp_path):
    service = _readiness_service(tmp_path, _ready_payload())
    gate = _gate(service.analyze(), "session")
    assert gate["passed"] is True and gate["required"] == "no requerido"


def test_non_finite_probability_stays_fail_closed_and_json_safe(tmp_path):
    service = _readiness_service(tmp_path, _ready_payload(probability=float("nan")))
    analysis = service.analyze()
    assert analysis["snapshot"] is None
    assert _gate(analysis, "probability")["code"] == "PROBABILITY_INVALID"
    json.dumps(analysis, allow_nan=False)


def test_malformed_snapshot_and_m15_read_failure_are_visible(tmp_path):
    service = _readiness_service(tmp_path, _ready_payload())
    service.snapshot_path.write_text("{not-json", encoding="utf-8")
    assert _gate(service.analyze(), "snapshot")["code"] == "SNAPSHOT_INVALID"

    service.snapshot_path.write_text(json.dumps(_ready_payload()), encoding="utf-8")
    service.adapter.closed_m15_candles = lambda _symbol: (_ for _ in ()).throw(RuntimeError("M15_STALE"))
    gate = _gate(service.analyze(), "m15_confirmation")
    assert gate["passed"] is False and gate["code"] == "M15_DATA_UNAVAILABLE"
    assert "M15_STALE" in gate["detail"]


def test_snapshot_age_boundary_is_inclusive_at_twenty_minutes(tmp_path):
    service = _readiness_service(tmp_path, _ready_payload())
    evaluated_at = datetime(2026, 9, 10, 15, 0, tzinfo=timezone.utc)
    stochastic = StochasticReading(k=25, d=20, previous_k=15, previous_d=15)
    for age, expected in ((timedelta(minutes=20), "PASS"), (timedelta(minutes=20, microseconds=1), "SNAPSHOT_STALE")):
        snapshot = Snapshot("BUY", .70, True, evaluated_at - age, "EURUSD")
        raw = {"symbol": snapshot.symbol, "direction": snapshot.direction, "probability": snapshot.probability,
               "confirmed": snapshot.confirmed, "asof_time": snapshot.asof_time.isoformat()}
        gate = _gate({"readiness": service._readiness(raw, snapshot, stochastic, evaluated_at)}, "snapshot")
        assert gate["code"] == expected


def test_session_schedule_uses_local_weekday_and_exact_half_open_window(tmp_path):
    service = _readiness_service(tmp_path, _ready_payload(), sessions=True)

    def london(at):
        return next(item for item in service._session_schedule(at)["sessions"] if item["name"] == "LONDON")

    assert london(datetime(2026, 1, 5, 8, 0, tzinfo=timezone.utc))["active"] is True
    assert london(datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc))["active"] is False
    assert london(datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc))["active"] is False
    # Europe/London is UTC+1 in July; 07:00 UTC is the inclusive 08:00 local boundary.
    assert london(datetime(2026, 7, 6, 7, 0, tzinfo=timezone.utc))["active"] is True


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


def test_restart_cancels_persisted_manual_direction_without_resuming_it(tmp_path):
    state = tmp_path / "state.json"
    log = tmp_path / "events.jsonl"
    blackbox = tmp_path / "blackbox.jsonl"
    service = MechanicalBotService(BotConfig(enabled=True), adapter=FakeAdapter(), snapshot_path=tmp_path / "snap.json",
                                  state_path=state, log_path=log, blackbox_path=blackbox)
    service.bot.state = BotState.WAIT_STOCHASTIC
    service.manual_direction = "SELL"
    service._persist_state()

    recovered = MechanicalBotService(BotConfig(enabled=True), adapter=FakeAdapter(), snapshot_path=tmp_path / "snap.json",
                                     state_path=state, log_path=log, blackbox_path=blackbox)
    assert recovered.status()["state"] == "OFF"
    assert recovered.status()["manual_direction"] is None
    persisted = json.loads(state.read_text(encoding="utf-8"))
    assert persisted["state"] == "OFF" and persisted["manual_direction"] is None
    event = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert event["event"] == "CANCELLED_BY_RESTART"
    decision = json.loads(blackbox.read_text(encoding="utf-8").splitlines()[-1])
    assert decision["event"] == "CANCELLED_BY_RESTART"


def test_manual_entry_rejects_invalid_direction(tmp_path):
    service = MechanicalBotService(BotConfig(enabled=True), adapter=FakeAdapter(), snapshot_path=tmp_path / "snap.json",
                                    state_path=tmp_path / "state.json", log_path=tmp_path / "events.jsonl",
                                    blackbox_path=tmp_path / "blackbox.jsonl")
    service._session_schedule = lambda: {"enabled": True, "sessions": [{"name": "NEW_YORK", "active": True}]}  # type: ignore[method-assign]
    service.bot.state = BotState.ARMED
    with pytest.raises(ValueError, match="direction must be BUY or SELL"):
        service.manual_entry("HOLD")


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
    monkeypatch.setattr(service, "_read_snapshot", lambda: {"symbol": "EURUSD", "direction": "BUY", "probability": .7, "confirmed": True, "asof_time": datetime.now(timezone.utc).isoformat()})
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


def test_manual_sell_selection_waits_for_stochastic_without_sending_order(tmp_path, monkeypatch):
    class ExecutionAdapter(FakeAdapter):
        execution_enabled = True
        def __init__(self):
            super().__init__()
            self.executions = []
        def execute(self, action, **kwargs):
            self.executions.append((action, kwargs))
            return super().execute(action, **kwargs)

    adapter = ExecutionAdapter()
    service = MechanicalBotService(BotConfig(enabled=True), adapter=adapter,
                                  snapshot_path=tmp_path / "missing.json", state_path=tmp_path / "state.json",
                                  log_path=tmp_path / "events.jsonl", blackbox_path=tmp_path / "blackbox.jsonl")
    service._session_schedule = lambda: {"enabled": True, "sessions": [{"name": "LONDON", "active": True}]}  # type: ignore[method-assign]
    monkeypatch.setattr(service, "start_runner", lambda: None)
    service.arm()

    selected = service.manual_entry("SELL")
    assert selected["state"] == "WAIT_STOCHASTIC"
    assert selected["manual_direction"] == "SELL"
    assert selected["cycle"] is None
    assert adapter.executions == []

    monkeypatch.setattr("mechanical_bot.service.stochastic_14_3_3", lambda *_args: None)
    waiting = service.tick()
    assert waiting["state"] == "WAIT_STOCHASTIC"
    assert waiting["manual_direction"] == "SELL"
    assert waiting["cycle"] is None
    assert adapter.executions == []
    decision = json.loads((tmp_path / "blackbox.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert decision["reason"] == "WAIT_MANUAL_DIRECTION_STOCHASTIC"


def test_manual_london_rejects_buy_and_allows_one_pending_sell_cycle(tmp_path, monkeypatch):
    class ExecutionAdapter(FakeAdapter):
        execution_enabled = True
        def __init__(self):
            super().__init__()
            self.executions = []
        def execute(self, action, **kwargs):
            self.executions.append(action)
            return super().execute(action, **kwargs)

    adapter = ExecutionAdapter()
    service = MechanicalBotService(BotConfig(enabled=True), adapter=adapter,
                                  snapshot_path=tmp_path / "missing.json", state_path=tmp_path / "state.json",
                                  log_path=tmp_path / "events.jsonl", blackbox_path=tmp_path / "blackbox.jsonl")
    service._session_schedule = lambda: {"enabled": True, "sessions": [{"name": "LONDON", "active": True}]}  # type: ignore[method-assign]
    monkeypatch.setattr(service, "start_runner", lambda: None)
    service.arm()

    with pytest.raises(RuntimeError, match="LONDON_SELL_ONLY"):
        service.manual_entry("BUY")
    assert adapter.executions == []

    service.manual_entry("SELL")
    bearish_cross = StochasticReading(k=75, d=82, previous_k=85, previous_d=82)
    monkeypatch.setattr("mechanical_bot.service.stochastic_14_3_3", lambda *_args: bearish_cross)
    entered = service.tick()
    assert entered["state"] == "INITIAL_ENTRY"
    assert entered["manual_direction"] is None
    assert entered["cycle"]["direction"] == "SELL"
    assert len(adapter.executions) == 1
    assert adapter.executions[0].kind == "OPEN"

    with pytest.raises(RuntimeError, match="cycle already active"):
        service.manual_entry("SELL")
    assert len(adapter.executions) == 1
