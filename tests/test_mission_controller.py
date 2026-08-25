import json

from orchestration.mission_controller import (
    AgentRegistryResolver,
    OpenCodeCliAdapter,
    OpenCodeHttpAdapter,
    DelegationRef,
    SessionRef,
    MemorySaveResult,
    ProviderEvent,
    MissionController,
    MissionStore,
    route_request,
)


def test_route_request_selects_department_and_controls():
    decision = route_request("audita el drift y la calibración del modelo IA")
    assert decision.department_id == "D3"
    assert decision.assigned_role == "Model Evaluator"
    assert decision.agent_key == "auditor"
    assert "independent_verification" in decision.required_controls
    assert "CRO" in decision.required_reviews


def test_route_request_keeps_lab_and_daily_motor_separate():
    lab = route_request("diseña un experimento para validar una hipótesis ICT")
    daily = route_request("corrige un bug del motor diario")
    assert lab.department_id == "D6"
    assert daily.department_id == "D2"
    assert "lab_boundary" in lab.required_controls


def test_controller_persists_routed_mission_and_event(tmp_path):
    store = MissionStore(tmp_path / "missions")
    mission = MissionController(store=store, workspace=tmp_path).create_mission("ordena la bitácora y actualiza la documentación")
    loaded = store.load(mission["mission_id"])
    events = (tmp_path / "missions" / f"{mission['mission_id']}.events.jsonl").read_text(encoding="utf-8").splitlines()

    assert loaded["status"] == "PLAN"
    assert loaded["route"]["department_id"] == "D1"
    assert loaded["tasks"][0]["assigned_agent"] == "Knowledge Manager"
    assert loaded["tasks"][0]["agent_key"] == "documenter"
    assert json.loads(events[0])["type"] == "MISSION_CREATED"


def test_all_route_agent_keys_are_registered_in_opencode():
    resolver = AgentRegistryResolver("opencode.json")
    keys = {route_request(text).agent_key for text in (
        "haz un commit de la entrega",
        "audita el gate PIT",
        "revisa el dataset y su hash",
        "calibra el modelo IA",
        "diseña un experimento de laboratorio",
        "ordena la documentación",
        "corrige un bug del motor",
        "analiza esta solicitud",
    )}
    resolver.validate(sorted(keys))
    assert resolver.resolve("auditor").key == "auditor"


def test_controller_validates_provider_agent_before_persisting(tmp_path):
    controller = MissionController(workspace=".", store=MissionStore(tmp_path / "missions"))
    mission = controller.create_mission("audita el drift de la IA")
    assert mission["delegation"] == {
        "provider": "opencode",
        "agent_key": "auditor",
        "session_id": None,
        "status": "PLANNED",
    }


def test_opencode_adapter_builds_contractual_dry_run_without_launching_process(tmp_path):
    adapter = OpenCodeCliAdapter(
        workspace=".",
        registry=AgentRegistryResolver("opencode.json"),
        state_dir=tmp_path / "delegations",
        allow_process=False,
    )
    session = adapter.create_session("documenter", "Actualizar bitácora", "MC-TEST", "MC-TEST-T01")
    delegation = adapter.delegate(
        session,
        "mission_id=MC-TEST task_id=MC-TEST-T01 devuelve evidencia y siguiente acción",
    )
    assert delegation.status == "PLANNED"
    assert delegation.command[0] == "opencode"
    assert "--agent" in delegation.command
    assert not (tmp_path / "delegations").exists()


def test_opencode_adapter_rejects_prompt_without_mission_contract():
    adapter = OpenCodeCliAdapter(workspace=".", registry=AgentRegistryResolver("opencode.json"))
    session = adapter.create_session("auditor", "Auditar", "MC-TEST", "MC-TEST-T01")
    try:
        adapter.delegate(session, "haz el trabajo")
    except ValueError as error:
        assert "mission_id" in str(error)
    else:
        raise AssertionError("missing mission/task contract was accepted")


def test_opencode_event_normalization_extracts_provider_session_id():
    event = OpenCodeCliAdapter._normalize_event({
        "type": "session.status",
        "sessionID": "provider-123",
        "status": {"type": "idle"},
    })
    assert isinstance(event, ProviderEvent)
    assert event.provider_session_id == "provider-123"
    assert event.status == "idle"


def test_http_adapter_creates_delegates_and_polls_provider_status():
    calls = []

    def fake_request(method, path, body):
        calls.append((method, path, body))
        if method == "POST" and path == "/session":
            return {"id": "ses_provider_1"}
        if method == "GET" and path == "/session/status":
            return {"ses_provider_1": {"type": "idle"}}
        if method == "GET" and path == "/session/ses_provider_1/children":
            return []
        return {}

    from orchestration.mission_controller import OpenCodeHttpAdapter
    adapter = OpenCodeHttpAdapter(
        base_url="http://127.0.0.1:1",
        registry=AgentRegistryResolver("opencode.json"),
        request=fake_request,
    )
    session = adapter.create_session("auditor", "Auditar gate", "MC-HTTP", "MC-HTTP-T01")
    delegation = adapter.delegate(session, "mission_id=MC-HTTP task_id=MC-HTTP-T01 audita evidencia")
    status = adapter.get_session_status(session)
    events = adapter.poll_events()

    assert session.session_id == "ses_provider_1"
    assert delegation.status == "RUNNING"
    assert status["status"] == "IDLE"
    assert events[0].provider_session_id == "ses_provider_1"
    assert any(path == "/session/ses_provider_1/prompt_async" for _, path, _ in calls)


class _FakeAdapter:
    def __init__(self, status="RUNNING"):
        self.status = status

    def create_session(self, agent, title, mission_id, task_id):
        return SessionRef(f"ses_fake_{mission_id}", agent, title, mission_id, task_id)

    def delegate(self, session, prompt):
        return DelegationRef("deleg_fake", session.session_id, "RUNNING", ("fake",))

    def get_session_status(self, session):
        return {"session_id": session.session_id, "status": self.status}


class _FakeMemorySink:
    def __init__(self):
        self.calls = []

    def save(self, mission):
        self.calls.append(mission["mission_id"])
        return MemorySaveResult("fake-engram", "RECORDED", "ict2.0")


def test_controller_delegates_and_reconciles_without_faking_completion(tmp_path):
    store = MissionStore(tmp_path / "missions")
    controller = MissionController(store=store, workspace=".")
    mission = controller.create_mission("corrige un bug del motor diario")
    task_id = mission["tasks"][0]["task_id"]
    delegated = controller.delegate_task(
        mission["mission_id"], task_id, _FakeAdapter(),
        f"mission_id={mission['mission_id']} task_id={task_id} corrige con evidencia",
    )
    assert delegated["status"] == "EXECUTE"
    assert delegated["tasks"][0]["status"] == "RUNNING"

    observed = controller.reconcile_task(mission["mission_id"], task_id, _FakeAdapter("IDLE"))
    assert observed["status"] == "OBSERVE"
    assert observed["tasks"][0]["status"] == "OBSERVE"
    assert observed["completion_state"]["mission_complete"] is False


def test_controller_reconciliation_routes_failed_provider_to_recovery(tmp_path):
    store = MissionStore(tmp_path / "missions")
    controller = MissionController(store=store, workspace=".")
    mission = controller.create_mission("corrige un bug del motor diario")
    task_id = mission["tasks"][0]["task_id"]
    controller.delegate_task(
        mission["mission_id"], task_id, _FakeAdapter(),
        f"mission_id={mission['mission_id']} task_id={task_id} corrige con evidencia",
    )
    recovered = controller.reconcile_task(mission["mission_id"], task_id, _FakeAdapter("FAILED"))
    assert recovered["status"] == "RECOVER"
    assert recovered["tasks"][0]["status"] == "RECOVER"


def test_controller_requires_all_gates_and_evidence_before_completion(tmp_path):
    store = MissionStore(tmp_path / "missions")
    memory = _FakeMemorySink()
    controller = MissionController(store=store, workspace=tmp_path, memory_sink=memory)
    mission = controller.create_mission("corrige un bug del motor diario")
    task_id = mission["tasks"][0]["task_id"]
    controller.delegate_task(
        mission["mission_id"], task_id, _FakeAdapter(),
        f"mission_id={mission['mission_id']} task_id={task_id} corrige con evidencia",
    )
    controller.reconcile_task(mission["mission_id"], task_id, _FakeAdapter("IDLE"))
    observed = controller.store.load(mission["mission_id"])
    try:
        controller.complete_mission(mission["mission_id"], "final.json")
    except ValueError as error:
        assert "incomplete tasks" in str(error)
    else:
        raise AssertionError("incomplete task was accepted")
    controller.verify_task(mission["mission_id"], task_id, outputs=["patch.diff"], evidence_refs=["test-report.json"])
    for gate in ("objective_satisfied", "required_tests_pass", "evidence_recorded", "no_unresolved_blockers", "artifacts_consistent"):
        controller.set_gate(mission["mission_id"], gate, True, f"gate-{gate}.json")
    completed = controller.complete_mission(mission["mission_id"], "final-verdict.json")
    assert completed["status"] == "COMPLETE"
    assert completed["completion_state"]["mission_complete"] is True
    assert completed["memory"]["status"] == "RECORDED"
    assert memory.calls == [mission["mission_id"]]
    worklog = tmp_path / ".hermes-worklog" / f"HERMES_MISSION_{mission['mission_id']}.md"
    assert worklog.is_file()
    assert "\nnone\n" in worklog.read_text(encoding="utf-8")
    assert controller.audit_mission(mission["mission_id"]) == []


def test_store_lists_and_controller_recovers_active_mission(tmp_path):
    store = MissionStore(tmp_path / "missions")
    controller = MissionController(store=store, workspace=".")
    mission = controller.create_mission("corrige un bug del motor diario")
    task_id = mission["tasks"][0]["task_id"]
    controller.delegate_task(
        mission["mission_id"], task_id, _FakeAdapter(),
        f"mission_id={mission['mission_id']} task_id={task_id} corrige con evidencia",
    )
    restarted = MissionController(store=MissionStore(tmp_path / "missions"), workspace=".")
    recovered = restarted.recover_mission(mission["mission_id"], _FakeAdapter("RUNNING"))
    assert mission["mission_id"] in restarted.store.list_missions()
    assert recovered["status"] == "WAITING_FOR_AGENT"
