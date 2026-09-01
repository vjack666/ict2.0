import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_department_registry_is_complete_and_points_to_existing_paths():
    registry = json.loads((ROOT / "governance/DEPARTMENT_REGISTRY.json").read_text(encoding="utf-8"))
    departments = registry["departments"]
    assert len(departments) == 8
    assert {department["id"] for department in departments} == {f"D{i}" for i in range(8)}
    for department in departments:
        assert department["roles"]
        for relative in department["paths"]:
            assert (ROOT / relative).exists(), f"missing registered path: {relative}"


def test_routing_targets_registered_departments_and_preserves_controls():
    registry = json.loads((ROOT / "governance/DEPARTMENT_REGISTRY.json").read_text(encoding="utf-8"))
    ids = {department["id"] for department in registry["departments"]}
    assert set(registry["routing"].values()) <= ids
    assert "independent_verification" in registry["mandatory_controls"]
    assert "no_unapproved_promotion" in registry["mandatory_controls"]
    assert "daily_motor_is_separate_from_lab" in registry["protected_invariants"]


def test_department_graph_covers_every_registered_department():
    graph = (ROOT / "governance/ORGANIGRAMA_ICT_2_0.mmd").read_text(encoding="utf-8")
    for department_id in (f"D{i}" for i in range(8)):
        assert f"{department_id}[" in graph
