"""Strict parser for a future MECH_RL_SYSTEM_INTERFACE_V2 candidate.

JSON is used as the source-freeze serialization because JSON is a YAML subset
and the Python standard library can reject duplicate keys deterministically.
No file is written to the future interface-instance path by this module.
"""

from __future__ import annotations

import re
from types import MappingProxyType
from typing import Any, Mapping

from .strict_json import StrictJSONError, deep_freeze, loads_strict, require_exact_keys


SCHEMA = "MECH_RL_SYSTEM_INTERFACE_V2"
CONFIGURATION_ID = "C01_DEPLOYED_NOMINAL_FIXED_SOLAR_SNAPSHOT"
BUS_MODE = "EXPLICIT_STRUCTURE_PLUS_RESIDUAL"
ACTUATED_JOINTS = (
    "joint1",
    "joint2",
    "joint3",
    "joint4",
    "joint5",
    "joint6",
    "gripper_joint1",
    "gripper_joint2",
)
RUNTIME_GATES = (
    "ik_reachable",
    "external_collision_clear",
    "keep_out_clear",
    "sim10_gate",
    "safe00_state",
    "post_grasp_stability_gate",
    "gripper_configuration_accepted",
    "target_surface_normal_valid",
    "mechanical_system_binding",
    "harness_rated_envelope",
    "contact_physics_ready",
    "route_c_scope_disposition",
)
CORE_ARTIFACTS = (
    "system_urdf",
    "system_frame_tree",
    "accepted_b601_urdf",
    "urdf_generation_receipt",
    "unified_r2_source_gate",
    "sim_candidate_contract",
)
GATE_ARTIFACTS = (
    "v2_loader_source",
    "v2_loader_validation_receipt",
    "runtime_gate_adapter_source",
    "runtime_evaluator_source",
    "runtime_evaluator_receipt",
    "dynamics_backend_source",
    "dynamics_backend_validation_receipt",
    "contact_backend_source",
    "contact_backend_validation_receipt",
)
ARTIFACTS = CORE_ARTIFACTS + GATE_ARTIFACTS
_SHA256 = re.compile(r"^[0-9A-F]{64}$")
SYSTEM_URDF_TARGET_PATH = (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "unified_r2_digital_prototype_prebind/generated_v2/"
    "unified_r2_c01_no_route_c_sim_candidate_v2.urdf"
)


def _safe_project_path(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise StrictJSONError(f"INVALID_PATH:{path}")
    if "\x00" in value or "\\" in value or ":" in value or value.startswith("/"):
        raise StrictJSONError(f"NON_PROJECT_RELATIVE_PATH:{path}")
    raw_parts = value.split("/")
    if "//" in value or any(part in ("", ".", "..") for part in raw_parts):
        raise StrictJSONError(f"PATH_TRAVERSAL:{path}")
    return value


def _artifact_record(value: Any, name: str) -> Mapping[str, Any]:
    require_exact_keys(value, ("path", "bytes", "sha256"), path=f"/artifacts/{name}")
    _safe_project_path(value["path"], f"/artifacts/{name}/path")
    if type(value["bytes"]) is not int or value["bytes"] <= 0:
        raise StrictJSONError(f"INVALID_BYTE_COUNT:/artifacts/{name}")
    if not isinstance(value["sha256"], str) or not _SHA256.fullmatch(value["sha256"]):
        raise StrictJSONError(f"INVALID_SHA256:/artifacts/{name}")
    return deep_freeze(dict(value))


def _exact_mapping(value: Any, expected: Mapping[str, Any], path: str) -> None:
    require_exact_keys(value, expected, path=path)
    for key, exact in expected.items():
        if value[key] != exact:
            raise StrictJSONError(f"EXACT_VALUE_MISMATCH:{path}/{key}")


def parse_interface_candidate(payload: bytes | str) -> Mapping[str, Any]:
    """Parse and validate one synthetic candidate, returning an immutable view."""

    data = loads_strict(payload)
    require_exact_keys(
        data,
        (
            "schema",
            "configuration_id",
            "selected_bus_mass_mode",
            "artifacts",
            "whole_system_contract",
            "accepted_b601_subtree",
            "actuation_contract",
            "runtime_gate_contract",
            "authority",
        ),
        path="/",
    )
    if data["schema"] != SCHEMA:
        raise StrictJSONError("SCHEMA_MISMATCH")
    if data["configuration_id"] != CONFIGURATION_ID:
        raise StrictJSONError("CONFIGURATION_ID_MISMATCH")
    if data["selected_bus_mass_mode"] != BUS_MODE:
        raise StrictJSONError("BUS_MODE_MISMATCH")

    artifacts = data["artifacts"]
    require_exact_keys(artifacts, ARTIFACTS, path="/artifacts")
    immutable_artifacts = {
        name: _artifact_record(artifacts[name], name) for name in ARTIFACTS
    }
    paths = [artifacts[name]["path"] for name in ARTIFACTS]
    hashes = [artifacts[name]["sha256"] for name in ARTIFACTS]
    if len(paths) != len(set(paths)):
        raise StrictJSONError("DUPLICATE_ARTIFACT_PATH")
    if len(hashes) != len(set(hashes)):
        raise StrictJSONError("DUPLICATE_ARTIFACT_SHA256")
    if artifacts["system_urdf"]["path"] != SYSTEM_URDF_TARGET_PATH:
        raise StrictJSONError("SYSTEM_URDF_FIXED_PATH_MISMATCH")

    _exact_mapping(
        data["whole_system_contract"],
        {
            "root_link": "spacecraft_bus",
            "links": 19,
            "physical_links": 16,
            "frame_only_links": 3,
            "joints": 18,
            "fixed": 10,
            "revolute": 6,
            "prismatic": 2,
            "actuated_dof": 8,
            "total_mass_kg": 31.022864807342987,
        },
        "/whole_system_contract",
    )
    _exact_mapping(
        data["accepted_b601_subtree"],
        {
            "root_link": "base_link",
            "links": 10,
            "joints": 9,
            "fixed": 1,
            "revolute": 6,
            "prismatic": 2,
            "mass_kg": 4.695555949342986,
            "exact_semantic_fields": [
                "link_names",
                "joint_names",
                "parent_child",
                "joint_origin",
                "joint_axis",
                "joint_limits",
                "per_link_mass_com_inertia",
            ],
        },
        "/accepted_b601_subtree",
    )
    _exact_mapping(
        data["actuation_contract"],
        {
            "actuated_joint_names": list(ACTUATED_JOINTS),
            "fixed_joint_excluded_from_state": ["gripper_joint"],
        },
        "/actuation_contract",
    )
    _exact_mapping(
        data["runtime_gate_contract"],
        {
            "required_gate_names": list(RUNTIME_GATES),
            "required_gate_count": 12,
            "allowed_states": ["PASS", "FAIL", "UNKNOWN"],
            "fail_closed_rule": "ANY_FAIL_OR_UNKNOWN_MASKS_TO_ABORT_ONLY",
        },
        "/runtime_gate_contract",
    )
    _exact_mapping(
        data["authority"],
        {
            "evaluation": "ALL_OF_HASH_BOUND_RECEIPTS",
            "caller_supplied_gate_state_is_authority": False,
            "current_scope": "SOURCE_FREEZE_ONLY",
            "consumer_load_authorized": False,
            "contact_grasp_authorized": False,
        },
        "/authority",
    )

    frozen = dict(data)
    frozen["artifacts"] = immutable_artifacts
    return deep_freeze(frozen)


def synthetic_interface_candidate() -> dict[str, Any]:
    """Return a deterministic in-memory parser fixture, never an instance file."""

    artifacts = {
        name: {
            "path": f"synthetic_fixture/{name}.bin",
            "bytes": index + 1,
            "sha256": f"{index + 1:064X}",
        }
        for index, name in enumerate(ARTIFACTS)
    }
    artifacts["system_urdf"]["path"] = SYSTEM_URDF_TARGET_PATH
    return {
        "schema": SCHEMA,
        "configuration_id": CONFIGURATION_ID,
        "selected_bus_mass_mode": BUS_MODE,
        "artifacts": artifacts,
        "whole_system_contract": {
            "root_link": "spacecraft_bus",
            "links": 19,
            "physical_links": 16,
            "frame_only_links": 3,
            "joints": 18,
            "fixed": 10,
            "revolute": 6,
            "prismatic": 2,
            "actuated_dof": 8,
            "total_mass_kg": 31.022864807342987,
        },
        "accepted_b601_subtree": {
            "root_link": "base_link",
            "links": 10,
            "joints": 9,
            "fixed": 1,
            "revolute": 6,
            "prismatic": 2,
            "mass_kg": 4.695555949342986,
            "exact_semantic_fields": [
                "link_names",
                "joint_names",
                "parent_child",
                "joint_origin",
                "joint_axis",
                "joint_limits",
                "per_link_mass_com_inertia",
            ],
        },
        "actuation_contract": {
            "actuated_joint_names": list(ACTUATED_JOINTS),
            "fixed_joint_excluded_from_state": ["gripper_joint"],
        },
        "runtime_gate_contract": {
            "required_gate_names": list(RUNTIME_GATES),
            "required_gate_count": 12,
            "allowed_states": ["PASS", "FAIL", "UNKNOWN"],
            "fail_closed_rule": "ANY_FAIL_OR_UNKNOWN_MASKS_TO_ABORT_ONLY",
        },
        "authority": {
            "evaluation": "ALL_OF_HASH_BOUND_RECEIPTS",
            "caller_supplied_gate_state_is_authority": False,
            "current_scope": "SOURCE_FREEZE_ONLY",
            "consumer_load_authorized": False,
            "contact_grasp_authorized": False,
        },
    }


__all__ = [
    "ACTUATED_JOINTS",
    "ARTIFACTS",
    "CONFIGURATION_ID",
    "RUNTIME_GATES",
    "SCHEMA",
    "SYSTEM_URDF_TARGET_PATH",
    "parse_interface_candidate",
    "synthetic_interface_candidate",
]
