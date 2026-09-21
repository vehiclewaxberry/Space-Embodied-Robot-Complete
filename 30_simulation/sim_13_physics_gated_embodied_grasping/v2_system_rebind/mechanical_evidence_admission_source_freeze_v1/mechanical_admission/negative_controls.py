"""Adversarial controls for the mechanical evidence admission boundary."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable
from unittest.mock import patch

from .evaluator import evaluate_snapshot, validate_publication_candidate
from .strict_io import (
    AdmissionError,
    EvidenceSnapshot,
    deep_freeze,
    load_default_snapshot,
    resolve_bound_path,
    strict_json_bytes,
    strict_yaml_bytes,
    thaw,
    validate_project_relative_path,
    verify_payload,
)


def _rejected(action: Callable[[], Any]) -> bool:
    try:
        result = action()
    except (AdmissionError, KeyError, TypeError, ValueError, AttributeError):
        return True
    return isinstance(result, dict) and result.get("source_only_validation_pass") is False


def _mutated(snapshot: EvidenceSnapshot, artifact_id: str, mutation: Callable[[dict[str, Any]], None]) -> EvidenceSnapshot:
    artifacts = dict(snapshot.artifacts)
    artifact = artifacts[artifact_id]
    document = thaw(artifact.parsed)
    mutation(document)
    artifacts[artifact_id] = replace(artifact, parsed=deep_freeze(document))
    return replace(snapshot, artifacts=MappingProxyType(artifacts))


def run_negative_controls(snapshot: EvidenceSnapshot | None = None) -> dict[str, Any]:
    snapshot = load_default_snapshot() if snapshot is None else snapshot
    baseline = evaluate_snapshot(snapshot)
    controls: list[dict[str, Any]] = []

    def add(control_id: str, stimulus: str, passed: bool) -> None:
        controls.append({"id": control_id, "stimulus": stimulus, "passed": passed})

    payload = b"bound"
    add("NC01", "SOURCE_BYTES_DRIFT", _rejected(lambda: verify_payload(payload, len(payload) + 1, "0" * 64)))
    add("NC02", "SOURCE_SHA256_DRIFT", _rejected(lambda: verify_payload(payload, len(payload), "0" * 64)))
    add(
        "NC03",
        "ABSOLUTE_OR_TRAVERSAL_PATH",
        _rejected(lambda: validate_project_relative_path("C:/escape.yaml"))
        and _rejected(lambda: validate_project_relative_path("../escape.yaml")),
    )
    with patch("mechanical_admission.strict_io._is_reparse_or_symlink", return_value=True):
        reparse_rejected = _rejected(
            lambda: resolve_bound_path(snapshot.project_root, snapshot.artifacts["frame_tree"].relative_path)
        )
    add("NC04", "SYMLINK_OR_REPARSE_PATH", reparse_rejected)
    duplicate_json = _rejected(lambda: strict_json_bytes(b'{"schema":"A","schema":"B"}'))
    duplicate_yaml = _rejected(lambda: strict_yaml_bytes(b"schema: A\nschema: B\n"))
    add("NC05", "DUPLICATE_KEY_OR_SCHEMA_DRIFT", duplicate_json and duplicate_yaml)

    add(
        "NC06",
        "18_LINK_MODE_MASQUERADES_AS_SELECTED_19_LINK_MODE",
        _rejected(
            lambda: evaluate_snapshot(
                _mutated(snapshot, "frame_tree", lambda doc: doc["mode_topology"]["EXPLICIT_STRUCTURE_PLUS_RESIDUAL"].__setitem__("total_links", 18))
            )
        ),
    )
    add(
        "NC07",
        "D_M_ALIAS_OR_PHYSICAL_PATH_THROUGH_M",
        _rejected(
            lambda: evaluate_snapshot(
                _mutated(snapshot, "frame_tree", lambda doc: doc["frame_only_contract"].__setitem__("D_and_M_semantic_relation", "ALIASED"))
            )
        ),
    )
    add(
        "NC08",
        "PROHIBITED_37P05784541499227_KG_DOUBLE_COUNT",
        _rejected(
            lambda: evaluate_snapshot(
                _mutated(snapshot, "rebind_boundary", lambda doc: doc["selected_system_contract"].__setitem__("total_mass_kg", 37.05784541499227))
            )
        ),
    )

    def swap_joint_order(doc: dict[str, Any]) -> None:
        joints = doc["joint_tree_selected_mode"]
        i1 = next(i for i, item in enumerate(joints) if item["name"] == "joint1")
        i2 = next(i for i, item in enumerate(joints) if item["name"] == "joint2")
        joints[i1], joints[i2] = joints[i2], joints[i1]

    add("NC09", "B601_SUBTREE_OR_JOINT_ORDER_UNIT_DRIFT", _rejected(lambda: evaluate_snapshot(_mutated(snapshot, "frame_tree", swap_joint_order))))
    add(
        "NC10",
        "LOADABLE_MESH_PROMOTED_TO_COLLISION_AUTHORITY",
        _rejected(lambda: evaluate_snapshot(_mutated(snapshot, "collision_audit", lambda doc: doc.__setitem__("narrow_phase_available", True)))),
    )
    add(
        "NC11",
        "URDF_15_MPS_PROMOTED_TO_PHYSICAL_SPEED",
        _rejected(lambda: evaluate_snapshot(_mutated(snapshot, "gripper_interface", lambda doc: doc["physical_actuator_layer"].__setitem__("rated_speed_m_s", 15.0)))),
    )
    add(
        "NC12",
        "NULL_CONTACT_PARAMETER_ZERO_FILLED",
        _rejected(lambda: evaluate_snapshot(_mutated(snapshot, "contact_contract", lambda doc: doc["normal_contact"]["normal_stiffness_N_per_m"].__setitem__("estimate", 0.0)))),
    )

    def promote_trajectory(doc: dict[str, Any]) -> None:
        doc["segments"][1]["released_for_mission_gate"] = True
        doc["segments"][1]["status"] = "RELEASED"

    add("NC13", "CANDIDATE_TRAJECTORY_PROMOTED_TO_RELEASED", _rejected(lambda: evaluate_snapshot(_mutated(snapshot, "trajectory_contract", promote_trajectory))))
    add(
        "NC14",
        "ABSENT_SYSTEM_URDF_OR_INTERFACE_REPORTED_AVAILABLE",
        _rejected(lambda: evaluate_snapshot(replace(snapshot, required_absent_paths=tuple()))),
    )
    forged = dict(baseline)
    forged["current_system_bound"] = True
    add("NC15", "MANDATORY_FALSE_AUTHORIZATION_FLIPPED_TRUE", _rejected(lambda: validate_publication_candidate(forged)))

    parsed = snapshot.artifacts["frame_tree"].parsed
    nested_mutation_rejected = False
    try:
        parsed["frame_only_contract"]["links"][0] = "FORGED"
    except (TypeError, AttributeError):
        nested_mutation_rejected = True
    add("NC16", "POST_LOAD_NESTED_MUTATION", nested_mutation_rejected)

    return {
        "schema": "MECHANICAL_EVIDENCE_ADMISSION_NEGATIVE_CONTROLS_V1",
        "baseline_source_only_validation_pass": baseline["source_only_validation_pass"],
        "controls": controls,
        "controls_passed": sum(item["passed"] for item in controls),
        "controls_total": len(controls),
        "all_passed": bool(controls) and all(item["passed"] for item in controls),
        "generated_physics_or_mechanical_assets": False,
    }
