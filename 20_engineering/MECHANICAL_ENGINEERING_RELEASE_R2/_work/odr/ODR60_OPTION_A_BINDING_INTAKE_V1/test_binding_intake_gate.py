from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("binding_intake_builder", HERE / "build_binding_intake_gate.py")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _inputs():
    return list(copy.deepcopy(MODULE.load_inputs(MODULE.ROOT)))


def _errors(items=None):
    return MODULE.audit_documents(*(items or _inputs()))


def test_positive_intake_audit_is_clean_and_strictly_fail_closed():
    assert _errors() == []
    gate = MODULE.build_gate(MODULE.ROOT)
    assert all(gate["checks"].values())
    ready = gate["current_readiness"]
    assert ready["urdf_content_identity_bound"] is True
    assert ready["physical_dynamics_bridge_bound"] is True
    assert ready["scene_bound_required_binding_count"] == 0
    assert ready["clearance_numeric_policy_row_count"] == 0
    for key in ("execution_mount_numeric_spelling_bound", "collision_asset_frame_registration_bound", "scene_binding_complete", "clearance_policy_bound", "pair_evaluation_authorized", "edge_evaluation_authorized", "path_search_authorized", "next_stage_authorized", "release_credit"):
        assert ready[key] is False


def test_urdf_dual_digest_is_exactly_reproduced():
    audit = _inputs()[1]
    raw = _inputs()[6]
    assert len(raw) == 11321
    assert raw.count(b"\r\n") == 292
    assert raw.count(b"\n") - raw.count(b"\r\n") == 0
    assert MODULE.sha256_bytes(raw) == audit["normalization"]["raw_crlf_sha256"]
    assert MODULE.sha256_bytes(raw.replace(b"\r\n", b"\n")) == audit["normalization"]["lf_normalized_sha256"]


@pytest.mark.parametrize("mutation,expected", [
    ("urdf_bytes", "URDF_RAW_DIGEST_MISMATCH"),
    ("legacy_conflict", "FALSE_URDF_LEGACY_CONFLICT_CLAIM"),
    ("bridge_hash", "CONFIRMED_BRIDGE_NOT_CROSS_BOUND"),
    ("mount_spelling", "UNAUTHORIZED_MOUNT_EXECUTION_VALUE::runtime_mount_numeric_spelling"),
    ("motion_credit", "FALSE_SYSTEM_MOTION_CERTIFICATE_CREDIT"),
    ("drop_scene_field", "INTAKE_SCENE_REQUIRED_FIELD_SET_MISMATCH"),
    ("fill_q", "UNAUTHORIZED_SCENE_VALUE::q6"),
    ("fill_target", "UNAUTHORIZED_SCENE_VALUE::target_present"),
    ("fill_solar_hdrm", "UNAUTHORIZED_SOLAR_HDRM_VALUE"),
    ("scene_credit", "FALSE_SCENE_BINDING_CREDIT"),
    ("bad_partition", "M01_EVENT_PARTITION_NOT_FAIL_CLOSED"),
    ("policy_row", "UNAUTHORIZED_OR_NONEMPTY_CLEARANCE_POLICY_ROWS"),
    ("policy_credit", "FALSE_CLEARANCE_POLICY_CREDIT"),
    ("wildcard", "CLEARANCE_FALLBACK_NOT_FORBIDDEN::wildcard"),
    ("action_credit", "ACTION_FIELD_NOT_FALSE::scene::path_search_authorized"),
])
def test_adversarial_mutations_fail_closed(mutation, expected):
    items = _inputs()
    urdf_audit, mount, clearance, scene, raw = items[1], items[2], items[3], items[4], items[6]
    if mutation == "urdf_bytes":
        items[6] = raw.replace(b"robot", b"ROB0T", 1)
    elif mutation == "legacy_conflict":
        urdf_audit["legacy_or_new_model_conflict"] = True
    elif mutation == "bridge_hash":
        mount["physical_to_dynamics_bridge"]["sha256"] = "0" * 64
    elif mutation == "mount_spelling":
        mount["execution_binding"]["runtime_mount_numeric_spelling"] = "D6_6DP"
    elif mutation == "motion_credit":
        mount["system_object_motion_certificates_emitted"] = 1
    elif mutation == "drop_scene_field":
        scene["required_bindings"].pop("target_attached")
    elif mutation == "fill_q":
        scene["required_bindings"]["q6"]["value"] = [0.0] * 6
    elif mutation == "fill_target":
        scene["required_bindings"]["target_present"]["value"] = True
    elif mutation == "fill_solar_hdrm":
        scene["required_schema_extension"]["solar_hdrm_state"]["value"] = "HDRM_ENGAGED"
    elif mutation == "scene_credit":
        scene["bound_required_binding_count"] = 9
    elif mutation == "bad_partition":
        scene["event_partition_required"] = ["M01_SINGLE_EDGE"]
    elif mutation == "policy_row":
        clearance["policy_rows"] = [{"pair_id": "Q000001", "authorized_pair_min_mm": 0.0}]
    elif mutation == "policy_credit":
        clearance["clearance_policy_bound"] = True
    elif mutation == "wildcard":
        clearance["coverage_contract"]["wildcard"] = "ALLOW"
    elif mutation == "action_credit":
        scene["path_search_authorized"] = True
    assert expected in _errors(items)


def test_strict_json_duplicate_keys_are_rejected():
    with pytest.raises(ValueError, match="duplicate JSON key"):
        MODULE.strict_json_bytes(b'{"x": 1, "x": 2}')


def test_builder_is_deterministic_and_manifest_not_self_referential():
    gate1, manifest1 = MODULE.expected_outputs(MODULE.ROOT)
    gate2, manifest2 = MODULE.expected_outputs(MODULE.ROOT)
    assert gate1 == gate2
    assert manifest1 == manifest2
    assert MODULE.GATE_REL.as_posix().encode() in manifest1
    assert MODULE.MANIFEST_REL.as_posix().encode() not in manifest1
    parsed = json.loads(gate1)
    assert parsed["read_scope"]["geometry_loaded"] is False
    assert parsed["read_scope"]["pair_query_executed"] is False
    assert parsed["read_scope"]["edge_query_executed"] is False
    assert parsed["read_scope"]["path_search_executed"] is False


def test_builder_has_no_geometry_or_planning_backend_imports():
    source = (HERE / "build_binding_intake_gate.py").read_text(encoding="utf-8")
    forbidden = ("import numpy", "import trimesh", "import FreeCAD", "import fcl", "import pybullet", "import ompl")
    assert not any(token in source for token in forbidden)
