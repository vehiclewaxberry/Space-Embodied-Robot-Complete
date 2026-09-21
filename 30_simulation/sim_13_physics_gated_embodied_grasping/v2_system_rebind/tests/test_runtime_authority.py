from __future__ import annotations

import hashlib
import inspect
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pytest


V2_ROOT = Path(__file__).resolve().parents[1]
if str(V2_ROOT) not in sys.path:
    sys.path.insert(0, str(V2_ROOT))

from sim13_v2 import authority_resolver as resolver_module
from sim13_v2.authority_resolver import AuthorityResolver
from sim13_v2.contracts import GateSnapshot, REQUIRED_GATES
from sim13_v2.env import Sim13V2Environment
from sim13_v2.system_model import SystemModel


def _inertial(link: ET.Element, mass: float = 1.0) -> None:
    inertial = ET.SubElement(link, "inertial")
    ET.SubElement(inertial, "mass", {"value": str(mass)})
    ET.SubElement(inertial, "origin", {"xyz": "0 0 0", "rpy": "0 0 0"})
    ET.SubElement(
        inertial,
        "inertia",
        {"ixx": "1", "ixy": "0", "ixz": "0", "iyy": "1", "iyz": "0", "izz": "1"},
    )


def _joint(
    robot: ET.Element,
    name: str,
    kind: str,
    parent: str,
    child: str,
) -> None:
    joint = ET.SubElement(robot, "joint", {"name": name, "type": kind})
    ET.SubElement(joint, "parent", {"link": parent})
    ET.SubElement(joint, "child", {"link": child})
    ET.SubElement(joint, "origin", {"xyz": "0 0 0", "rpy": "0 0 0"})
    if kind != "fixed":
        ET.SubElement(joint, "axis", {"xyz": "0 0 1"})
        ET.SubElement(
            joint,
            "limit",
            {"lower": "-1", "upper": "1", "effort": "1", "velocity": "1"},
        )


def _synthetic_system_urdf() -> bytes:
    """Topology-only parser fixture; it carries no gate or release PASS."""

    robot = ET.Element("robot", {"name": "synthetic_unified_r2_parser_fixture"})
    physical = [
        "spacecraft_bus",
        "bus_primary_structure_candidate_v1",
        "load_bridge_candidate",
        "m3r_lumped_link",
        "base_link",
        "link1",
        "link2",
        "link3",
        "link4",
        "link5",
        "link6",
        "gripper_link",
        "gripper_left",
        "gripper_right",
        "solar_r2_left_c01_snapshot",
        "solar_r2_right_c01_snapshot",
    ]
    frames = ["D_BUS_MATE_PHYSICAL", "D_BUS_M6_PATTERN", "M_DYNAMICS_NONPHYSICAL"]
    for name in physical:
        mass = 16.022864807342987 if name == "spacecraft_bus" else 1.0
        _inertial(ET.SubElement(robot, "link", {"name": name}), mass)
    for name in frames:
        ET.SubElement(robot, "link", {"name": name})
    _joint(robot, "bus_to_bus_primary_structure_candidate_v1", "fixed", "spacecraft_bus", "bus_primary_structure_candidate_v1")
    _joint(robot, "bus_to_D_BUS_MATE_PHYSICAL", "fixed", "spacecraft_bus", "D_BUS_MATE_PHYSICAL")
    _joint(robot, "D_BUS_MATE_PHYSICAL_to_D_BUS_M6_PATTERN", "fixed", "D_BUS_MATE_PHYSICAL", "D_BUS_M6_PATTERN")
    _joint(robot, "D_BUS_M6_PATTERN_to_load_bridge_candidate", "fixed", "D_BUS_M6_PATTERN", "load_bridge_candidate")
    _joint(robot, "load_bridge_candidate_to_m3r_lumped_link", "fixed", "load_bridge_candidate", "m3r_lumped_link")
    _joint(robot, "m3r_lumped_link_to_base_link", "fixed", "m3r_lumped_link", "base_link")
    parent = "base_link"
    for index in range(1, 7):
        child = f"link{index}"
        _joint(robot, f"joint{index}", "revolute", parent, child)
        parent = child
    _joint(robot, "gripper_joint", "fixed", "link6", "gripper_link")
    _joint(robot, "gripper_joint1", "prismatic", "gripper_link", "gripper_left")
    _joint(robot, "gripper_joint2", "prismatic", "gripper_link", "gripper_right")
    _joint(robot, "bus_to_M_DYNAMICS_NONPHYSICAL", "fixed", "spacecraft_bus", "M_DYNAMICS_NONPHYSICAL")
    _joint(robot, "bus_to_solar_r2_left_c01_snapshot", "fixed", "spacecraft_bus", "solar_r2_left_c01_snapshot")
    _joint(robot, "bus_to_solar_r2_right_c01_snapshot", "fixed", "spacecraft_bus", "solar_r2_right_c01_snapshot")
    return ET.tostring(robot, encoding="utf-8", xml_declaration=True)


def _artifact_record(path: str, payload: bytes | None, **metadata: object) -> dict[str, object]:
    return {
        "path": path,
        "bytes": None if payload is None else len(payload),
        "sha256": None if payload is None else hashlib.sha256(payload).hexdigest().upper(),
        "schema": metadata.get("schema"),
        "verdict": metadata.get("verdict"),
        "next_stage_authorized": metadata.get("next_stage_authorized"),
    }


def _install_isolated_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    audit_payload: bytes,
    audit_record_overrides: dict[str, object] | None = None,
    config_overrides: dict[str, object] | None = None,
) -> Path:
    project = tmp_path / "project"
    config_dir = project / "30_simulation" / "sim13" / "v2_system_rebind" / "config"
    audit_path = project / "evidence" / "audit.json"
    config_dir.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_bytes(audit_payload)
    record = _artifact_record(
        "evidence/audit.json",
        audit_payload,
        schema="CURRENT_AUDIT",
        verdict="HOLD",
        next_stage_authorized=False,
    )
    record.update(audit_record_overrides or {})
    absent = _artifact_record("future/not_instantiated", None)
    gate_sources = {
        name: {
            "artifact": "current_mechanical_audit" if name == "mechanical_system_binding" else "system_interface",
            "field": "/next_stage_authorized",
            "pass_value": True,
        }
        for name in REQUIRED_GATES
    }
    document: dict[str, object] = {
        "schema": "SIM13_V2_AUTHORITY_BINDINGS_V1",
        "scope": "SOURCE_ONLY_PREBIND_NOT_BOUND_NOT_LOADED",
        "project_root": os.path.relpath(project, config_dir).replace(os.sep, "/"),
        "artifacts": {
            "current_mechanical_audit": record,
            "system_interface": absent,
            "system_urdf": absent,
        },
        "gate_sources": gate_sources,
    }
    document.update(config_overrides or {})
    config_path = config_dir / "authority_bindings_v2.json"
    config_path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(resolver_module, "_AUTHORITY_BINDINGS_PATH", config_path)
    monkeypatch.setattr(resolver_module, "_EXPECTED_PROJECT_ROOT", project)
    return config_path


def _audit_payload(*, schema: str = "CURRENT_AUDIT") -> bytes:
    return json.dumps(
        {
            "schema": schema,
            "technical_verdict": "HOLD",
            "next_stage_authorized": False,
        }
    ).encode("utf-8")


def test_public_api_has_no_gate_injection_and_snapshot_has_no_pass_factory() -> None:
    assert len(REQUIRED_GATES) == 12
    assert REQUIRED_GATES[-4:] == (
        "mechanical_system_binding",
        "harness_rated_envelope",
        "contact_physics_ready",
        "route_c_scope_disposition",
    )
    assert "gates" not in inspect.signature(Sim13V2Environment.reset).parameters
    assert "gates" not in inspect.signature(Sim13V2Environment.action_mask).parameters
    assert "gates" not in inspect.signature(Sim13V2Environment.step).parameters
    assert not hasattr(GateSnapshot, "all_pass")
    assert not hasattr(GateSnapshot, "from_mapping")
    with pytest.raises(TypeError, match="authority-resolver"):
        GateSnapshot({})


def test_current_package_state_exposes_abort_only() -> None:
    env = Sim13V2Environment()
    observation, info = env.reset()
    mask = env.action_mask()
    assert mask["ABORT"]["allowed"] is True
    assert mask["S1"]["allowed"] is False
    assert mask["S3a"]["allowed"] is False
    assert observation["collision"] == {
        "status": "UNKNOWN_NOT_EVALUATED",
        "detected": None,
        "clear": None,
        "operational_collision_authority": False,
    }
    assert observation["production_ready"] is False
    assert observation["command_emitted"] is False
    assert len(observation["authority_snapshot_sha256"]) == 64
    assert observation["system"]["expected_topology"] == {
        "links": 19,
        "joints": 18,
        "physical_links": 16,
        "frame_only_links": 3,
        "movable_dof": 8,
    }
    assert info["execution_scope"].endswith("NO_DYNAMICS_OR_CONTACT_CLAIM")
    assert len(info["authority_config_sha256"]) == 64
    assert info["gate_snapshot"]["mechanical_system_binding"] == "FAIL"
    assert info["command_emitted"] is False


def test_non_abort_is_shielded_and_forged_pass_field_is_rejected() -> None:
    env = Sim13V2Environment()
    env.reset()
    _, _, terminated, _, info = env.step(
        {
            "grasp_candidate_id": "GC_PRIMARY",
            "capture_timing_id": "T_NOMINAL",
            "strategy_id": "S1",
        }
    )
    assert terminated is True
    assert info["executed_action"]["strategy_id"] == "ABORT"
    with pytest.raises(ValueError, match="exactly"):
        env.step(
            {
                "grasp_candidate_id": "GC_PRIMARY",
                "capture_timing_id": "T_NOMINAL",
                "strategy_id": "S1",
                "mechanical_system_binding": "PASS",
            }
        )
    with pytest.raises(ValueError, match="low-level"):
        env.step(
            {
                "grasp_candidate_id": "GC_PRIMARY",
                "capture_timing_id": "T_NOMINAL",
                "strategy_id": "S1",
                "joint_torque": [1.0],
            }
        )


def test_system_model_excludes_all_fixed_joints_from_eight_dof_state(tmp_path: Path) -> None:
    model = SystemModel.from_xml_bytes(_synthetic_system_urdf(), artifact_root=tmp_path)
    state = model.zero_state()
    assert len(model.link_names) == 19
    assert len(model.joint_names) == 18
    assert len(model.fixed_joint_names) == 10
    assert len(model.revolute_joint_names) == 6
    assert len(model.prismatic_joint_names) == 2
    assert len(state.q) == len(state.dq) == len(state.joint_names) == 8
    assert "gripper_joint" in model.fixed_joint_names
    assert "gripper_joint" not in state.joint_names


def _mutated_system_urdf(mutation: str) -> bytes:
    root = ET.fromstring(_synthetic_system_urdf())
    if mutation == "18_LINK_AGGREGATE":
        structure = root.find("./link[@name='bus_primary_structure_candidate_v1']")
        joint = root.find("./joint[@name='bus_to_bus_primary_structure_candidate_v1']")
        assert structure is not None and joint is not None
        root.remove(structure)
        root.remove(joint)
    elif mutation == "MASS_DOUBLE_COUNT":
        mass = root.find("./link[@name='spacecraft_bus']/inertial/mass")
        assert mass is not None
        mass.set("value", "22.05784541499227")
    elif mutation == "FRAME_ONLY_CONTAMINATION":
        frame = root.find("./link[@name='M_DYNAMICS_NONPHYSICAL']")
        assert frame is not None
        ET.SubElement(frame, "visual")
    elif mutation == "B601_PARENT_CHILD_DRIFT":
        parent = root.find("./joint[@name='joint3']/parent")
        assert parent is not None
        parent.set("link", "base_link")
    elif mutation == "D_M_NUMERIC_ALIAS_DRIFT":
        origin = root.find("./joint[@name='bus_to_M_DYNAMICS_NONPHYSICAL']/origin")
        assert origin is not None
        origin.set("xyz", "0.001 0 0")
    else:
        raise AssertionError(mutation)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


@pytest.mark.parametrize(
    "mutation",
    [
        "18_LINK_AGGREGATE",
        "MASS_DOUBLE_COUNT",
        "FRAME_ONLY_CONTAMINATION",
        "B601_PARENT_CHILD_DRIFT",
        "D_M_NUMERIC_ALIAS_DRIFT",
    ],
)
def test_selected_system_contract_negative_controls_fail_closed(
    mutation: str, tmp_path: Path
) -> None:
    with pytest.raises(ValueError):
        SystemModel.from_xml_bytes(
            _mutated_system_urdf(mutation), artifact_root=tmp_path
        )


def test_hash_drift_makes_source_unknown_not_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = _audit_payload()
    _install_isolated_config(
        monkeypatch,
        tmp_path,
        audit_payload=payload,
        audit_record_overrides={"sha256": "0" * 64},
    )
    resolution = AuthorityResolver().resolve()
    assert resolution.config_valid is True
    assert resolution.snapshot.state("mechanical_system_binding").value == "FAIL"
    assert (
        resolution.artifacts["current_mechanical_audit"].reason_code
        == "BYTES_OR_SHA256_MISMATCH"
    )
    assert resolution.snapshot.permits_non_abort is False


def test_canonical_authority_config_is_source_pinned_and_prebind_locked() -> None:
    resolution = AuthorityResolver().resolve()
    assert resolution.config_valid is True
    assert resolution.config_sha256 == resolver_module._EXPECTED_BINDINGS_SHA256
    assert resolution.snapshot.state("mechanical_system_binding").value == "FAIL"
    assert (
        resolution.snapshot.evidence("mechanical_system_binding").reason_code
        == "MECHANICAL_SYSTEM_BINDING_PREBIND_SCOPE_LOCK"
    )


def test_schema_mismatch_and_path_escape_fail_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    payload = _audit_payload(schema="WRONG")
    _install_isolated_config(monkeypatch, tmp_path, audit_payload=payload)
    schema_resolution = AuthorityResolver().resolve()
    assert schema_resolution.snapshot.state("mechanical_system_binding").value == "FAIL"
    assert schema_resolution.artifacts["current_mechanical_audit"].verified is False

    _install_isolated_config(
        monkeypatch,
        tmp_path,
        audit_payload=_audit_payload(),
        audit_record_overrides={"path": "../outside.json"},
    )
    path_resolution = AuthorityResolver().resolve()
    assert path_resolution.snapshot.state("mechanical_system_binding").value == "FAIL"
    assert path_resolution.artifacts["current_mechanical_audit"].reason_code == "PATH_CONTAINMENT_FAIL"


def test_verified_false_authority_is_fail_and_absence_stays_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _install_isolated_config(monkeypatch, tmp_path, audit_payload=_audit_payload())
    resolution = AuthorityResolver().resolve()
    assert resolution.config_valid is True
    assert resolution.snapshot.state("mechanical_system_binding").value == "FAIL"
    assert resolution.snapshot.state("contact_physics_ready").value == "UNKNOWN"
    assert resolution.snapshot.permits_non_abort is False
