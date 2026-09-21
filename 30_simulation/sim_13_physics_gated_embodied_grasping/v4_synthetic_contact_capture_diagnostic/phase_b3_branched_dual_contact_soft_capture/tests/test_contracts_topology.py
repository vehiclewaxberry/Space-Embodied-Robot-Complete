from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from b3_contact.dual_contact_kernel import (
    ATTACHED_TARGET_RELEASED,
    CURRENT_SYSTEM_BOUND,
    FORMAL_NC19_CREDIT,
    GRASP_SUCCESS_CLAIMED,
    LOCK_IMPLEMENTED,
    NEXT_STAGE_AUTHORIZED,
    PHYSICAL_ACTUATOR_TIMING_IDENTIFIED,
    PHYSICAL_DUAL_CONTACT_IDENTIFIED,
    PHYSICAL_FRICTION_IDENTIFIED,
    PRODUCTION_READY,
    RELEASE_AUTHORIZED,
    SOFT_CAPTURE_CURRENT_SYSTEM_PASSED,
    DualContactConfig,
)


PHASE_B3 = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PHASE_B3.parents[3]
TOPOLOGY_LEDGER = PHASE_B3 / "contracts/PHASE_B3_URDF_TOPOLOGY_LEDGER_V1.json"
MODEL_CONTRACT = PHASE_B3 / "contracts/PHASE_B3_MODEL_CONTRACT_V1.json"
GOVERNANCE_CONTRACT = PHASE_B3 / "contracts/PHASE_B3_GOVERNANCE_CONTRACT_V1.json"
EXPECTED_URDF_SHA256 = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _vector(text: str) -> np.ndarray:
    return np.asarray([float(value) for value in text.split()], dtype=float)


def _rpy_rotation(rpy: np.ndarray) -> np.ndarray:
    roll, pitch, yaw = rpy
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = np.array(((1.0, 0.0, 0.0), (0.0, cr, -sr), (0.0, sr, cr)))
    ry = np.array(((cp, 0.0, sp), (0.0, 1.0, 0.0), (-sp, 0.0, cp)))
    rz = np.array(((cy, -sy, 0.0), (sy, cy, 0.0), (0.0, 0.0, 1.0)))
    return rz @ ry @ rx


def test_source_urdf_hash_and_topology_ledger_are_exact():
    ledger = _load(TOPOLOGY_LEDGER)
    source = PROJECT_ROOT / ledger["source_urdf"]["path"]
    actual_sha = hashlib.sha256(source.read_bytes()).hexdigest().upper()
    assert actual_sha == ledger["source_urdf"]["sha256"] == EXPECTED_URDF_SHA256
    assert ledger["source_urdf"]["modified_by_phase_b3"] is False
    assert ledger["role"] == "READ_ONLY_TOPOLOGY_AND_FRAME_SEMANTICS__NOT_CONTACT_OR_TIMING_AUTHORITY"


def test_two_prismatic_fingers_are_siblings_with_opposed_palm_axes():
    ledger = _load(TOPOLOGY_LEDGER)
    source = PROJECT_ROOT / ledger["source_urdf"]["path"]
    root = ET.parse(source).getroot()
    joints = {item.attrib["name"]: item for item in root.findall("joint")}
    measured_axes = []
    for declared in ledger["joints"]:
        joint = joints[declared["name"]]
        assert joint.attrib["type"] == declared["type"] == "prismatic"
        assert joint.find("parent").attrib["link"] == declared["parent"] == "gripper_link"
        assert joint.find("child").attrib["link"] == declared["child"]
        origin = joint.find("origin")
        axis_joint = _vector(joint.find("axis").attrib["xyz"])
        axis_palm = _rpy_rotation(_vector(origin.attrib["rpy"])) @ axis_joint
        limit = joint.find("limit")
        assert np.allclose(_vector(origin.attrib["xyz"]), declared["origin_xyz_parent_m"], atol=5.0e-10)
        assert np.allclose(axis_joint, declared["axis_joint_frame"], atol=1.0e-12)
        assert np.allclose(axis_palm, declared["axis_palm_frame_analytic"], atol=5.0e-6)
        assert np.allclose(
            [float(limit.attrib["lower"]), float(limit.attrib["upper"])],
            declared["limit_m"],
            atol=1.0e-12,
        )
        measured_axes.append(axis_palm / np.linalg.norm(axis_palm))
    assert float(measured_axes[0] @ measured_axes[1]) <= -1.0 + 1.0e-10


def test_contact_frames_and_physical_timing_remain_explicitly_unbound():
    ledger = _load(TOPOLOGY_LEDGER)
    source = PROJECT_ROOT / ledger["source_urdf"]["path"]
    root = ET.parse(source).getroot()
    joints = {item.attrib["name"]: item for item in root.findall("joint")}
    velocities = [float(joints[item["name"]].find("limit").attrib["velocity"]) for item in ledger["joints"]]
    assert velocities == [ledger["model_limit_exclusions"]["urdf_velocity_literal_m_s"]] * 2
    assert not any(
        ledger["model_limit_exclusions"][key]
        for key in ("physical_speed_authority", "physical_timing_authority", "physical_force_authority")
    )
    assert ledger["missing_spatial_authorities"] == {
        "left_contact_frame_T_gripper_link": None,
        "right_contact_frame_T_gripper_link": None,
        "target_contact_geometry": None,
        "rule": "B3 contact pads must be named synthetic assumptions and may not be attributed to this URDF",
    }


def test_governance_and_solver_boundaries_stay_fail_closed():
    governance = _load(GOVERNANCE_CONTRACT)
    required_false = governance["required_false"]
    assert required_false and not any(required_false.values())
    assert governance["formal_sim13_v2_state_unchanged"] == {
        "passed": 15,
        "declared": 20,
        "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"],
    }
    assert not any(
        (
            PHYSICAL_DUAL_CONTACT_IDENTIFIED,
            PHYSICAL_FRICTION_IDENTIFIED,
            PHYSICAL_ACTUATOR_TIMING_IDENTIFIED,
            SOFT_CAPTURE_CURRENT_SYSTEM_PASSED,
            LOCK_IMPLEMENTED,
            GRASP_SUCCESS_CLAIMED,
            ATTACHED_TARGET_RELEASED,
            CURRENT_SYSTEM_BOUND,
            FORMAL_NC19_CREDIT,
            PRODUCTION_READY,
            RELEASE_AUTHORIZED,
            NEXT_STAGE_AUTHORIZED,
        )
    )
    model_contract = _load(MODEL_CONTRACT)
    assert "average_contact_point" in model_contract["forbidden_aggregation"]
    assert "single_combined_contact_impulse" in model_contract["forbidden_aggregation"]


def test_configuration_validation_and_generated_artifact_boundary():
    with pytest.raises(ValueError):
        DualContactConfig(friction_coefficient=0.0).validated()
    with pytest.raises(ValueError):
        DualContactConfig(initial_finger_coordinate_m=0.08).validated()
    with pytest.raises(ValueError):
        DualContactConfig(dual_contact_dwell_s=0.0).validated()
    forbidden = []
    for path in PHASE_B3.rglob("*"):
        name = path.name.lower()
        if path.is_dir() and name in {"__pycache__", ".pytest_cache"}:
            forbidden.append(path.relative_to(PHASE_B3).as_posix())
        elif path.is_file() and (
            name.endswith(".urdf") or "authorization" in name or "interface" in name
        ):
            forbidden.append(path.relative_to(PHASE_B3).as_posix())
    assert forbidden == []
