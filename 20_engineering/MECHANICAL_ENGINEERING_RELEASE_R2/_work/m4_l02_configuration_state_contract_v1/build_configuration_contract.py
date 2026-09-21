#!/usr/bin/env python3
"""Deterministically build the append-only M4-L02 configuration contract.

The builder is deliberately fail-closed: it refuses to emit if any pinned
source byte changes.  JSON-subset YAML is used so duplicate-key and NaN rules
remain unambiguous across consumers.  No current CAD, parent Gate, or release
artifact is modified by this script.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET

import yaml

from frozen_contract_v1 import (
    CONFIG_NAMES,
    CORE_FILES,
    EXPECTED_ARM_HDRM_NULL,
    EXPECTED_DESIGN_CHECK_KEYS,
    EXPECTED_DYNAMICS_USES,
    EXPECTED_MANIFEST_FILES,
    EXPECTED_MANIFEST_ROLES,
    EXPECTED_PINS,
    EXPECTED_SOLAR_HDRM_NULL,
    EXPECTED_SOLAR_LATCH_NULL,
    GATE_FILE,
    LEGACY_NAMES,
    M5_NAMES,
    MANIFEST_FILE,
    NEGATIVE_CONTROL_IDS,
    NEGATIVE_FILE,
    SPEC_FILE,
    SPEC_SCHEMA,
    VERDICT,
)


PACKAGE = Path(__file__).resolve().parent
WORKSPACE = PACKAGE.parents[3]
GENERATED = "DETERMINISTIC_NO_WALLCLOCK"


class BuildDataError(ValueError):
    pass


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(loader, node, deep=False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise BuildDataError(f"duplicate YAML key: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping)


def _reject_nonfinite(value, path="$"):
    if isinstance(value, float) and not math.isfinite(value):
        raise BuildDataError(f"non-finite number at {path}")
    if isinstance(value, dict):
        for key, child in value.items():
            _reject_nonfinite(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_nonfinite(child, f"{path}[{index}]")


def _pairs_no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise BuildDataError(f"duplicate JSON key: {key!r}")
        out[key] = value
    return out


def strict_json_loads(text):
    def reject_constant(token):
        raise BuildDataError(f"non-finite JSON token: {token}")
    try:
        value = json.loads(text, object_pairs_hook=_pairs_no_duplicates, parse_constant=reject_constant)
    except (json.JSONDecodeError, BuildDataError) as exc:
        raise BuildDataError(str(exc)) from exc
    _reject_nonfinite(value)
    return value


def strict_yaml_loads(text):
    try:
        value = yaml.load(text, Loader=UniqueKeyLoader)
    except (yaml.YAMLError, BuildDataError) as exc:
        raise BuildDataError(str(exc)) from exc
    _reject_nonfinite(value)
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def canonical_json_bytes(value) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def load_sources():
    docs = {}
    for source_id, (rel, _, _, _) in EXPECTED_PINS.items():
        path = WORKSPACE / rel
        suffix = path.suffix.lower()
        if suffix == ".json":
            docs[source_id] = strict_json_loads(path.read_text(encoding="utf-8"))
        elif suffix in {".yaml", ".yml"}:
            docs[source_id] = strict_yaml_loads(path.read_text(encoding="utf-8"))
        elif suffix == ".urdf":
            docs[source_id] = ET.parse(path).getroot()
        else:
            docs[source_id] = None
    return docs


def _verify_pins() -> None:
    failures = []
    for source_id, (rel, expected_bytes, expected_hash, _) in EXPECTED_PINS.items():
        path = WORKSPACE / rel
        if not path.exists():
            failures.append(f"{source_id}: missing {rel}")
            continue
        actual_bytes = path.stat().st_size
        actual_hash = sha256(path)
        if actual_bytes != expected_bytes or actual_hash != expected_hash:
            failures.append(
                f"{source_id}: expected {expected_bytes}/{expected_hash}, "
                f"got {actual_bytes}/{actual_hash}"
            )
    if failures:
        raise RuntimeError("source authority lock failed:\n" + "\n".join(failures))


def _expected_source_lock_rows() -> list[dict]:
    return [
        {
            "source_id": source_id,
            "path": rel,
            "bytes": expected_bytes,
            "sha256": expected_hash,
            "role": role,
            "match": True,
        }
        for source_id, (rel, expected_bytes, expected_hash, role) in EXPECTED_PINS.items()
    ]


def _source_lock() -> dict:
    rows = _expected_source_lock_rows()
    return {
        "schema": "SOURCE_AUTHORITY_LOCK_V1",
        "generated_utc": GENERATED,
        "policy": "EXACT_BYTES_AND_SHA256__FAIL_CLOSED_ON_ANY_SOURCE_CHANGE",
        "source_count": len(rows),
        "sources": rows,
        "all_sources_match": True,
        "authority_upgrade": False,
        "parent_gate_credit": False,
        "next_stage_authorized": False,
    }


def _maps(sources):
    m4 = {row["configuration_id"]: row for row in sources["m4_configuration_library"]["configurations"]}
    m5 = {row["configuration_id"]: row for row in sources["m5_geometry_contract"]["records"]}
    m7 = {row["configuration_id"]: row for row in sources["design_mass"]["configurations"]}
    return m4, m5, m7


def _crosswalk(sources) -> dict:
    m4, m5, m7 = _maps(sources)
    records = []
    for cid, contract_name in CONFIG_NAMES.items():
        records.append(
            {
                "configuration_id": cid,
                "contract_name": contract_name,
                "m4_name": m4[cid]["name"],
                "m4_legacy_alias": m4[cid]["legacy_mapping"],
                "m5_diagnostic_name": m5[cid]["name"],
                "m7_design_mass_name": m7[cid]["name"],
                "selected_current_r2": cid == "C01",
                "name_alignment": (
                    "EXACT" if cid not in {"C08", "C09"} else "EXACT_CONTRACT_AND_M7__LEGACY_AND_M5_ALIASES_RETAINED"
                ),
                "machine_truth_available": {
                    "design_mass_cg_inertia": True,
                    "current_complete_integrated_geometry": False,
                    "released_collision_clear": False,
                    "as_built_mass_properties": False,
                },
            }
        )
    return {
        "schema": "R2_CONFIGURATION_CROSSWALK_V1",
        "generated_utc": GENERATED,
        "configuration_count": 9,
        "selected_current_r2_configuration_id": "C01",
        "records": records,
        "explicit_nonclaim": "IDENTITY_CROSSWALK_DOES_NOT_CREATE_GEOMETRY_COLLISION_OR_OPERATIONAL_AUTHORITY",
        "parent_gate_credit": False,
        "next_stage_authorized": False,
    }


def _unknown(value_source: str, allowed_domain=None) -> dict:
    out = {
        "value": None,
        "status": "UNKNOWN_NOT_AUTHORITY_BOUND",
        "source": value_source,
    }
    if allowed_domain is not None:
        out["allowed_domain_m"] = allowed_domain
    return out


def _solar_hdrm_null() -> dict:
    return {
        "value": {
            "left_wing": {"tie_down_station_1": None, "tie_down_station_2": None},
            "right_wing": {"tie_down_station_1": None, "tie_down_station_2": None},
        },
        "status": "MEASUREMENT_PENDING__ZERO_FILL_FORBIDDEN",
        "station_count_contract": "2_PER_WING",
    }


def _solar_latch_null() -> dict:
    return {
        "value": {
            "left_wing": {"free_edge_hardpoint_1": None, "free_edge_hardpoint_2": None, "free_edge_hardpoint_3": None},
            "right_wing": {"free_edge_hardpoint_1": None, "free_edge_hardpoint_2": None, "free_edge_hardpoint_3": None},
        },
        "status": "MEASUREMENT_PENDING__ZERO_FILL_FORBIDDEN",
        "hardpoint_count_contract": "3_PER_WING",
    }


def _target_state(cid: str, sources) -> dict:
    is_target = cid in {"C08", "C09"}
    if cid == "C08":
        model = sources["target_models"]["target_satellite_v0"]
        target_id = "TARGET_SATELLITE_22KG"
    elif cid == "C09":
        model = sources["target_models"]["target_debris_v0"]
        target_id = "TARGET_DEBRIS_150KG"
    else:
        model = None
        target_id = None
    return {
        "scenario_member": {
            "value": is_target,
            "status": "DESIGN_SCENARIO_DECLARATION" if is_target else "NOT_A_TARGET_ATTACHED_SCENARIO",
        },
        "target_attached": {
            "value": is_target,
            "status": "MASS_PROPERTY_SCENARIO_SEMANTIC_ONLY__NO_PLANT_OR_CONTACT_AUTHORITY" if is_target else "NOT_APPLICABLE",
        },
        "target_id": {"value": target_id, "status": "LOW_CONFIDENCE_DESIGN_MODEL" if is_target else "NOT_APPLICABLE"},
        "design_mass_kg": {"value": model["mass_kg"] if model else None, "status": "DESIGN_MODEL" if is_target else "NOT_APPLICABLE"},
        "design_inertia_diag_kg_m2": {"value": model["inertia_diag_kgm2"] if model else None, "status": "LOW_CONFIDENCE_DESIGN_MODEL" if is_target else "NOT_APPLICABLE"},
        "attachment_transform_S_rows": {
            "value": None,
            "status": "UNKNOWN_NOT_AUTHORITY_BOUND__M5_DISPLAY_TRANSFORM_NOT_PROMOTED" if is_target else "NOT_APPLICABLE_NULL",
        },
        "contact_normals": {"value": None, "status": "UNKNOWN_NOT_AUTHORITY_BOUND" if is_target else "NOT_APPLICABLE_NULL"},
        "confidence": model["confidence"] if model else None,
        "operational_attachment_authority": False,
    }


def _solar_state(cid: str) -> dict:
    left = [[-1.0, 0.0, 0.0, 0.0], [0.0, -1.0, 0.0, 0.1154], [0.0, 0.0, 1.0, -0.10815], [0.0, 0.0, 0.0, 1.0]]
    right = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, -0.1154], [0.0, 0.0, 1.0, -0.10815], [0.0, 0.0, 0.0, 1.0]]
    if cid == "C01":
        return {
            "logical_state": {"value": "DEPLOYED_NOMINAL_FIXED_SNAPSHOT", "status": "AUTHORITY_BOUND_C01_SOURCE_ONLY_FRAME_TREE"},
            "left_transform_S_rows": {"value": left, "status": "AUTHORITY_BOUND_C01_FIXED_SNAPSHOT"},
            "right_transform_S_rows": {"value": right, "status": "AUTHORITY_BOUND_C01_FIXED_SNAPSHOT"},
            "failure_retention_semantics": {"value": None, "status": "NOT_APPLICABLE"},
        }
    if cid in {"C02", "C03", "C04"}:
        logical = {"C02": "LEFT_FAIL", "C03": "RIGHT_FAIL", "C04": "BOTH_FAIL"}[cid]
        return {
            "logical_state": {"value": logical, "status": "AUTHORITY_BOUND_FAILURE_SEMANTIC_ONLY"},
            "left_transform_S_rows": {"value": None, "status": "UNKNOWN_NO_CURRENT_INTEGRATED_GEOMETRY"},
            "right_transform_S_rows": {"value": None, "status": "UNKNOWN_NO_CURRENT_INTEGRATED_GEOMETRY"},
            "failure_retention_semantics": {"value": "ATTACHED_STUCK__JETTISON_FORBIDDEN", "status": "AUTHORITY_BOUND_LOGICAL_RULE"},
        }
    return {
        "logical_state": {"value": None, "status": "UNKNOWN_NOT_AUTHORITY_BOUND"},
        "left_transform_S_rows": {"value": None, "status": "UNKNOWN_NOT_AUTHORITY_BOUND"},
        "right_transform_S_rows": {"value": None, "status": "UNKNOWN_NOT_AUTHORITY_BOUND"},
        "failure_retention_semantics": {"value": None, "status": "UNKNOWN_NOT_AUTHORITY_BOUND"},
    }


def _state_contract(sources) -> dict:
    m4, _, _ = _maps(sources)
    accepted = {"C01", "C02", "C03", "C04"}
    candidate_status = {
        "C05": "HELD_STOW_SOURCE_EE_INCONSISTENT_WITH_Q_567P734_MM_AND_SUPPORT_CONTACT_HOLD",
        "C06": "REVALIDATED_RUNTIME_DIGITAL_POSE__SERVICE_CONFIGURATION_RATIFICATION_HOLD",
        "C07": "DIAGNOSTIC_CANDIDATE__PRECONTACT_ONLY__NOT_22KG_VALIDATED",
        "C08": "DIAGNOSTIC_CANDIDATE__DISPLAY_ONLY__REJECTED_AS_22KG_CAPTURE_VALIDATION",
        "C09": "DIAGNOSTIC_CANDIDATE__GEOMETRY_FEASIBLE_ONLY__E15_REPEAT",
    }
    records = []
    for cid, name in CONFIG_NAMES.items():
        q = m4[cid]["frames"]["diagnostic_joint_vector"]["q_rad"]
        q_source = m4[cid]["frames"]["diagnostic_joint_vector"]["source_pose"]
        authority_q = {
            "value": q if cid in accepted else None,
            "status": "AUTHORITY_BOUND_ACCEPTED_RUNTIME_DIGITAL_POSE" if cid in accepted else "UNKNOWN_NOT_AUTHORITY_BOUND",
            "source_pose": q_source if cid in accepted else None,
        }
        candidate_q = {
            "value": None if cid in accepted else q,
            "status": "NOT_NEEDED_AUTHORITY_ALREADY_BOUND" if cid in accepted else candidate_status[cid],
            "source_pose": None if cid in accepted else q_source,
            "authority": False,
        }
        records.append(
            {
                "configuration_id": cid,
                "name": name,
                "operational_state": "HOLD_ABORT_ONLY" if cid == "C05" else "NOT_OPERATIONALLY_AUTHORIZED",
                "authoritative_state": {
                    "q6_rad": authority_q,
                    "gripper_joint1_m": _unknown("UNIFIED_R2_URDF_DOMAIN_ONLY", [0.0, 0.0715]),
                    "gripper_joint2_m": _unknown("UNIFIED_R2_URDF_DOMAIN_ONLY", [0.0, 0.0715]),
                    "solar": _solar_state(cid),
                    "solar_hdrm_state": _solar_hdrm_null(),
                    "solar_latch_state": _solar_latch_null(),
                    "arm_hdrm_state": {"value": None, "status": "MEASUREMENT_PENDING__ZERO_FILL_FORBIDDEN"},
                    "target": _target_state(cid, sources),
                },
                "non_authoritative_candidates": {
                    "q6_rad": candidate_q,
                    "m5_display_gripper_travel_m": {
                        "value": None if cid not in {"C08", "C09"} else 0.055,
                        "status": "DISPLAY_ONLY_NOT_CONFIGURATION_AUTHORITY" if cid in {"C08", "C09"} else "NOT_APPLICABLE",
                    },
                },
                "discrete_state_complete": False,
                "continuous_state_complete": False,
                "production_complete_state_vector": False,
                "parent_gate_credit": False,
            }
        )
    records[0]["representation_conflicts"] = {
        "cad_static_pose_vs_configuration_pose": {
            "configuration_semantic_q6_rad": records[0]["authoritative_state"]["q6_rad"]["value"],
            "cad_static_representation_q6_rad": [0.0] * 6,
            "resolved": False,
            "effect": "CURRENT_COMPLETE_CONFIGURATION_GEOMETRY_FALSE",
            "boundary": "STATIC_CAD_Q0_CANNOT_STAND_IN_FOR_C01_QHOME",
        }
    }
    return {
        "schema": "R2_CONFIGURATION_STATE_VECTOR_CONTRACT_V1",
        "generated_utc": GENERATED,
        "units": {"revolute": "rad", "prismatic": "m", "transforms": "SI_homogeneous_rows"},
        "continuous_state_order": ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6", "gripper_joint1", "gripper_joint2"],
        "q6_is_separate_from_discrete_state": True,
        "joint_limit_contract": {
            "q6_source": "ACCEPTED_B601_URDF_E_HW",
            "gripper_domain_source": "UNIFIED_R2_URDF_SOURCE_ONLY_CANDIDATE",
            "gripper_domain_is_not_a_state_value": True,
        },
        "unknown_policy": "UNKNOWN_PHYSICAL_VALUES_ARE_NULL__ZERO_FILL_FORBIDDEN",
        "configurations": records,
        "production_complete_state_vector_count": 0,
        "parent_gate_credit": False,
        "next_stage_authorized": False,
    }


def _mass_view(sources) -> dict:
    _, _, m7 = _maps(sources)
    rows = []
    for cid, name in CONFIG_NAMES.items():
        src = m7[cid]
        rows.append(
            {
                "configuration_id": cid,
                "name": name,
                "model_class": "DESIGN_MODEL_R2_CANDIDATE_ONLY",
                "mass_kg": src["mass"]["value_kg"],
                "mass_standard_uncertainty_kg": src["mass"]["standard_uncertainty_kg"],
                "cg_S_m": src["center_of_mass"]["xyz_m"],
                "cg_standard_uncertainty_S_m": src["center_of_mass"]["standard_uncertainty_xyz_m"],
                "inertia_about_system_cg_S_kg_m2": src["inertia"]["components_kg_m2"],
                "inertia_standard_uncertainty_components_kg_m2": src["inertia"]["standard_uncertainty_components_kg_m2"],
                "reference_frame": "S",
                "reference_point": "system_center_of_mass",
                "as_built_mass_kg": None,
                "as_built_cg_S_m": None,
                "as_built_inertia_kg_m2": None,
                "design_checks_from_ssot": src["checks"],
                "maximum_claim": "DESIGN_DYNAMICS_INPUT_CANDIDATE_ONLY__NOT_AS_BUILT_NOT_RELEASED",
            }
        )
    return {
        "schema": "R2_NINE_CONFIGURATION_MASS_PROPERTY_VIEW_V1",
        "generated_utc": GENERATED,
        "model_class": "DESIGN_MODEL_CANDIDATE_ONLY_NOT_AS_BUILT",
        "source_id": "design_mass",
        "configuration_count": 9,
        "configurations": rows,
        "as_built_configuration_count": 0,
        "authority_upgrade": False,
        "parent_gate_credit": False,
        "next_stage_authorized": False,
    }


GEOMETRY_FIELDS = [
    "configuration_id", "name", "current_complete_integrated_geometry",
    "current_source_only_topology_candidate", "current_partial_master_geometry",
    "diagnostic_m5_geometry_present", "diagnostic_snapshot_path",
    "diagnostic_snapshot_sha256", "diagnostic_bbox_min_S_m",
    "diagnostic_bbox_max_S_m", "diagnostic_mass_properties_authority",
    "diagnostic_verified_system_collision_clear", "released_collision_clear",
    "current_geometry_status", "maximum_claim",
]


def _geometry_csv(sources) -> bytes:
    _, m5, _ = _maps(sources)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=GEOMETRY_FIELDS, lineterminator="\n")
    writer.writeheader()
    for cid, name in CONFIG_NAMES.items():
        row = m5[cid]
        writer.writerow(
            {
                "configuration_id": cid,
                "name": name,
                "current_complete_integrated_geometry": "false",
                "current_source_only_topology_candidate": "true" if cid == "C01" else "false",
                "current_partial_master_geometry": "true" if cid == "C01" else "false",
                "diagnostic_m5_geometry_present": "true",
                "diagnostic_snapshot_path": row["snapshot"]["path"],
                "diagnostic_snapshot_sha256": row["snapshot"]["sha256"],
                "diagnostic_bbox_min_S_m": json.dumps(row["bbox_S_m"][0], separators=(",", ":"), allow_nan=False),
                "diagnostic_bbox_max_S_m": json.dumps(row["bbox_S_m"][1], separators=(",", ":"), allow_nan=False),
                "diagnostic_mass_properties_authority": "false",
                "diagnostic_verified_system_collision_clear": "false",
                "released_collision_clear": "false",
                "current_geometry_status": (
                    "PARTIAL_41_SOLID_MASTER_PLUS_SOURCE_ONLY_URDF__EXPECTED_399_SOLID_STEP_AND_GLB_ABSENT__Q0_VS_QHOME_CONFLICT"
                    if cid == "C01" else "NO_CURRENT_INTEGRATED_GEOMETRY__DIAGNOSTIC_WITNESS_ONLY"
                ),
                "maximum_claim": (
                    "SOURCE_ONLY_TOPOLOGY_AND_PARTIAL_STATIC_GEOMETRY_CANDIDATE__NO_COLLISION_CREDIT"
                    if cid == "C01" else "DIAGNOSTIC_GEOMETRY_WITNESS_ONLY__NO_CURRENT_GEOMETRY_CREDIT"
                ),
            }
        )
    return output.getvalue().encode("utf-8")


def _dynamics_matrix() -> dict:
    records = []
    for cid, name in CONFIG_NAMES.items():
        records.append(
            {
                "configuration_id": cid,
                "name": name,
                "maximum_permitted_use": EXPECTED_DYNAMICS_USES[cid],
                "design_mass_property_loading_allowed": True,
                "current_geometry_collision_allowed": False,
                "target_attachment_plant_allowed": False,
                "non_abort_operational_authority": False,
                "parent_gate_credit": False,
                "required_runtime_guards": [
                    "DESIGN_MODEL_LABEL_PROPAGATED",
                    "UNKNOWN_STATE_REJECTED",
                    "COLLISION_AND_CONTACT_DISABLED",
                    "NO_PARENT_GATE_INHERITANCE",
                ],
            }
        )
    return {
        "schema": "R2_CONFIGURATION_DYNAMICS_USE_MATRIX_V1",
        "generated_utc": GENERATED,
        "records": records,
        "parent_dynamics_gate_reissued": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }


def _core_bytes(sources) -> dict[str, bytes]:
    return {
        CORE_FILES["source_lock"]: canonical_json_bytes(_source_lock()),
        CORE_FILES["crosswalk"]: canonical_json_bytes(_crosswalk(sources)),
        CORE_FILES["state"]: canonical_json_bytes(_state_contract(sources)),
        CORE_FILES["mass"]: canonical_json_bytes(_mass_view(sources)),
        CORE_FILES["geometry"]: _geometry_csv(sources),
        CORE_FILES["dynamics"]: canonical_json_bytes(_dynamics_matrix()),
    }


def _parse_geometry_csv_bytes(payload: bytes):
    text = payload.decode("utf-8")
    if "\r" in text:
        raise BuildDataError("geometry CSV must use LF")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != GEOMETRY_FIELDS:
        raise BuildDataError("geometry CSV header drift")
    rows = list(reader)
    if any(None in row for row in rows):
        raise BuildDataError("geometry CSV surplus columns")
    return rows


def _core_docs_from_bytes(core: dict[str, bytes]):
    return {
        "source_lock": strict_json_loads(core[CORE_FILES["source_lock"]].decode("utf-8")),
        "crosswalk": strict_yaml_loads(core[CORE_FILES["crosswalk"]].decode("utf-8")),
        "state": strict_yaml_loads(core[CORE_FILES["state"]].decode("utf-8")),
        "mass": strict_yaml_loads(core[CORE_FILES["mass"]].decode("utf-8")),
        "geometry": _parse_geometry_csv_bytes(core[CORE_FILES["geometry"]]),
        "dynamics": strict_yaml_loads(core[CORE_FILES["dynamics"]].decode("utf-8")),
    }


def _all_null(value):
    if isinstance(value, dict):
        return all(_all_null(child) for child in value.values())
    if isinstance(value, list):
        return all(_all_null(child) for child in value)
    return value is None


def _unique_count(values):
    try:
        return len(set(values))
    except TypeError:
        return -1


def _b64_tree_equal(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and set(actual) == set(expected) and all(
            _b64_tree_equal(actual[key], expected[key]) for key in expected
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            _b64_tree_equal(a, e) for a, e in zip(actual, expected)
        )
    if type(expected) is float:
        return type(actual) is float and math.isfinite(actual) and struct.pack(">d", actual) == struct.pack(">d", expected)
    return type(actual) is type(expected) and actual == expected


def _binary64_leaf_count(value):
    if isinstance(value, dict):
        return sum(_binary64_leaf_count(child) for child in value.values())
    if isinstance(value, list):
        return sum(_binary64_leaf_count(child) for child in value)
    return 1 if type(value) is float else 0


def _parse_bbox_cell(cell):
    if not isinstance(cell, str):
        raise BuildDataError("bbox cell must be a JSON string")
    value = strict_json_loads(cell)
    if not isinstance(value, list) or len(value) != 3 or any(type(item) is not float for item in value):
        raise BuildDataError("bbox cell must be exactly three binary64 values")
    if not all(math.isfinite(item) for item in value):
        raise BuildDataError("bbox cell contains non-finite value")
    return value


def _bbox_pair_matches(row, source_bbox):
    try:
        bbox_min = _parse_bbox_cell(row.get("diagnostic_bbox_min_S_m"))
        bbox_max = _parse_bbox_cell(row.get("diagnostic_bbox_max_S_m"))
    except BuildDataError:
        return False
    return (
        _b64_tree_equal(bbox_min, source_bbox[0])
        and _b64_tree_equal(bbox_max, source_bbox[1])
        and all(lo <= hi for lo, hi in zip(bbox_min, bbox_max))
    )


def _walk_key_values(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key, child
            yield from _walk_key_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_key_values(child)


def _payload_metadata(payload: bytes) -> dict:
    return {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest().upper()}


def _builder_gate_integrity(gate, core_check_ids, local_meta, spec_meta, negative_total):
    if not isinstance(gate, dict):
        return False
    criteria = gate.get("criteria", [])
    expected_ids = list(core_check_ids) + ["GATE26_NEGATIVE_CONTROLS_ALL_CAUGHT"]
    expected_summary = {
        "source_pins": "20_OF_20",
        "configuration_ids": "9_OF_9",
        "design_mass_properties": "9_OF_9",
        "complete_current_geometry": "0_OF_9",
        "source_only_current_topology": "1_OF_9",
        "diagnostic_geometry_witnesses": "9_OF_9",
        "released_collision": "0_OF_9",
        "production_complete_state_vectors": "0_OF_9",
        "as_built_mass_properties": "0_OF_9",
        "negative_controls": f"{negative_total}_OF_{negative_total}",
    }
    expected_local_files = set(CORE_FILES.values()) | {NEGATIVE_FILE}
    expected_spec = {
        "path": SPEC_FILE,
        "bytes": spec_meta["bytes"],
        "sha256": spec_meta["sha256"],
        "schema": SPEC_SCHEMA,
    }
    return (
        gate.get("schema") == "M4_L02_CONFIGURATION_STATE_CONTRACT_GATE_V1"
        and gate.get("gate_verdict") == VERDICT
        and isinstance(criteria, list)
        and len(criteria) == len(expected_ids)
        and [row.get("id") for row in criteria if isinstance(row, dict)] == expected_ids
        and all(isinstance(row, dict) and row.get("status") == "PASS" for row in criteria)
        and gate.get("summary") == expected_summary
        and gate.get("parent_gate_credit") is False
        and gate.get("parent_gate_reissued") is False
        and gate.get("next_stage_authorized") is False
        and gate.get("release_credit") is False
        and set(gate.get("local_artifact_bindings", {})) == expected_local_files
        and set(local_meta) == expected_local_files
        and all(gate["local_artifact_bindings"].get(rel) == local_meta[rel] for rel in expected_local_files)
        and gate.get("contract_spec_binding") == expected_spec
    )


def _builder_manifest_integrity(rows, artifact_meta):
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        return False
    paths = [row.get("path") for row in rows]
    if _unique_count(paths) != len(paths):
        return False
    manifest_map = {row["path"]: row for row in rows}
    if not (
        len(rows) == len(EXPECTED_MANIFEST_FILES)
        and set(manifest_map) == EXPECTED_MANIFEST_FILES
        and set(artifact_meta) == EXPECTED_MANIFEST_FILES
        and set(EXPECTED_MANIFEST_ROLES) == EXPECTED_MANIFEST_FILES
        and MANIFEST_FILE not in manifest_map
    ):
        return False
    return all(
        set(manifest_map[rel]) == {"path", "bytes", "sha256", "role"}
        and manifest_map[rel]["bytes"] == str(artifact_meta[rel]["bytes"])
        and manifest_map[rel]["sha256"] == artifact_meta[rel]["sha256"]
        and manifest_map[rel]["role"] == EXPECTED_MANIFEST_ROLES[rel]
        for rel in EXPECTED_MANIFEST_FILES
    )


def _generator_checks(docs, sources):
    checks = {}
    add = lambda key, value: checks.__setitem__(key, {"pass": bool(value)})
    lock = docs["source_lock"]
    lock_rows = lock.get("sources", [])
    rows_are_mappings = isinstance(lock_rows, list) and all(isinstance(row, dict) for row in lock_rows)
    lock_map = {row.get("source_id"): row for row in lock_rows} if rows_are_mappings else {}
    lock_ids = [row.get("source_id") for row in lock_rows] if rows_are_mappings else []
    lock_paths = [row.get("path") for row in lock_rows] if rows_are_mappings else []
    expected_lock_rows = _expected_source_lock_rows()
    add(
        "CORE01_SOURCE_PINS_EXACT",
        rows_are_mappings
        and _b64_tree_equal(lock_rows, expected_lock_rows)
        and type(lock.get("source_count")) is int
        and len(lock_rows) == len(lock_map) == lock.get("source_count") == 20
        and len(lock_ids) == _unique_count(lock_ids) == 20
        and len(lock_paths) == _unique_count(lock_paths) == 20
        and lock.get("all_sources_match") is True
        and all(row.get("match") is True for row in lock_rows),
    )
    add("CORE02_STRICT_SOURCE_PARSE_NO_DUPLICATE_OR_NONFINITE", len(sources) == 20)

    m4 = {row["configuration_id"]: row for row in sources["m4_configuration_library"]["configurations"]}
    m5 = {row["configuration_id"]: row for row in sources["m5_geometry_contract"]["records"]}
    m7 = {row["configuration_id"]: row for row in sources["design_mass"]["configurations"]}
    cross = {row["configuration_id"]: row for row in docs["crosswalk"].get("records", [])}
    add("CORE03_CROSSWALK_EXACT_NINE_AND_ALIASES", len(cross) == 9 and set(cross) == set(CONFIG_NAMES) and all(
        cross[cid].get("contract_name") == CONFIG_NAMES[cid]
        and cross[cid].get("m4_name") == m4[cid]["name"]
        and cross[cid].get("m4_legacy_alias") == LEGACY_NAMES[cid]
        and cross[cid].get("m5_diagnostic_name") == M5_NAMES[cid]
        and cross[cid].get("m7_design_mass_name") == CONFIG_NAMES[cid]
        and cross[cid].get("selected_current_r2") is (cid == "C01") for cid in CONFIG_NAMES
    ))

    mass_rows = docs["mass"].get("configurations", [])
    mass = {row["configuration_id"]: row for row in mass_rows}
    add("CORE04_MASS_VIEW_EXACT_NINE_DESIGN_CLASS", len(mass) == 9 and set(mass) == set(CONFIG_NAMES) and docs["mass"].get("model_class") == "DESIGN_MODEL_CANDIDATE_ONLY_NOT_AS_BUILT")
    receipt = {row["configuration_id"]: row for row in sources["design_mass_receipt"]["per_configuration"]}
    mass_exact = True
    unique_core_leaf_count = 0
    receipt_recheck_count = 0
    design_checks_exact = True
    ssot_min_eigenvalue_count = 0
    receipt_min_eigenvalue_count = 0
    for cid in CONFIG_NAMES:
        src, out = m7[cid], mass[cid]
        expected = {
            "mass_kg": src["mass"]["value_kg"],
            "mass_standard_uncertainty_kg": src["mass"]["standard_uncertainty_kg"],
            "cg_S_m": src["center_of_mass"]["xyz_m"],
            "cg_standard_uncertainty_S_m": src["center_of_mass"]["standard_uncertainty_xyz_m"],
            "inertia_about_system_cg_S_kg_m2": src["inertia"]["components_kg_m2"],
            "inertia_standard_uncertainty_components_kg_m2": src["inertia"]["standard_uncertainty_components_kg_m2"],
        }
        mass_exact = mass_exact and all(_b64_tree_equal(out.get(key), value) for key, value in expected.items())
        unique_core_leaf_count += sum(_binary64_leaf_count(value) for value in expected.values())
        mass_exact = mass_exact and _b64_tree_equal(out.get("mass_kg"), receipt[cid]["mass_kg"])
        mass_exact = mass_exact and _b64_tree_equal(out.get("cg_S_m"), receipt[cid]["cg_S_m"])
        receipt_recheck_count += _binary64_leaf_count(receipt[cid]["mass_kg"])
        receipt_recheck_count += _binary64_leaf_count(receipt[cid]["cg_S_m"])
        source_checks = src.get("checks", {})
        receipt_checks = receipt[cid].get("checks", {})
        output_checks = out.get("design_checks_from_ssot")
        per_checks_ok = (
            isinstance(source_checks, dict)
            and isinstance(receipt_checks, dict)
            and set(source_checks) == set(receipt_checks) == EXPECTED_DESIGN_CHECK_KEYS
            and _b64_tree_equal(output_checks, source_checks)
            and _b64_tree_equal(output_checks, receipt_checks)
            and type(source_checks.get("min_eigenvalue_kg_m2")) is float
            and math.isfinite(source_checks.get("min_eigenvalue_kg_m2"))
            and source_checks.get("min_eigenvalue_kg_m2") > 0.0
            and all(source_checks.get(key) is True for key in EXPECTED_DESIGN_CHECK_KEYS if key != "min_eigenvalue_kg_m2")
        )
        design_checks_exact = design_checks_exact and per_checks_ok
        ssot_min_eigenvalue_count += _binary64_leaf_count(source_checks.get("min_eigenvalue_kg_m2"))
        receipt_min_eigenvalue_count += _binary64_leaf_count(receipt_checks.get("min_eigenvalue_kg_m2"))
    add(
        "CORE05_MASS_CG_INERTIA_IEEE754_BIT_EXACT_AND_TYPE_AUDITED",
        mass_exact and unique_core_leaf_count == 180 and receipt_recheck_count == 36,
    )
    add(
        "CORE06_DESIGN_CHECKS_SSOT_EXACT_MIN_EIGENVALUE_IEEE754_AND_INERTIA_PHYSICS",
        design_checks_exact and ssot_min_eigenvalue_count == 9 and receipt_min_eigenvalue_count == 9,
    )

    state_rows = docs["state"].get("configurations", [])
    state = {row["configuration_id"]: row for row in state_rows}
    add("CORE07_STATE_SCHEMA_NINE_AND_Q6_2P_DISCRETE_SEPARATION", len(state) == 9 and set(state) == set(CONFIG_NAMES) and docs["state"].get("continuous_state_order") == ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6", "gripper_joint1", "gripper_joint2"] and docs["state"].get("q6_is_separate_from_discrete_state") is True)
    q_expected = {"C05": m4["C05"]["frames"]["diagnostic_joint_vector"]["q_rad"], "C06": m4["C06"]["frames"]["diagnostic_joint_vector"]["q_rad"], "C07": m4["C07"]["frames"]["diagnostic_joint_vector"]["q_rad"], "C08": m4["C08"]["frames"]["diagnostic_joint_vector"]["q_rad"], "C09": m4["C09"]["frames"]["diagnostic_joint_vector"]["q_rad"]}
    q_ok = True
    for cid in CONFIG_NAMES:
        auth = state[cid]["authoritative_state"]["q6_rad"]
        cand = state[cid]["non_authoritative_candidates"]["q6_rad"]
        values = auth["value"] if cid <= "C04" else cand["value"]
        q_ok = q_ok and (auth["value"] == m4[cid]["frames"]["diagnostic_joint_vector"]["q_rad"] if cid <= "C04" else auth["value"] is None and cand["value"] == q_expected[cid])
        q_ok = q_ok and len(values) == 6 and all(lo <= float(q) <= hi for q, (lo, hi) in zip(values, [(-2.8,2.8),(-3.14,0),(-3.14,0),(-1.87,1.57),(-1.57,1.57),(-3.14,3.14)]))
    add("CORE08_Q6_AUTHORITY_TIER_AND_EHW_LIMITS_EXACT", q_ok)
    conflict = state["C01"].get("representation_conflicts", {}).get("cad_static_pose_vs_configuration_pose", {})
    add("CORE09_C01_QHOME_VS_CAD_Q0_CONFLICT_EXPLICIT", conflict.get("configuration_semantic_q6_rad") == m4["C01"]["frames"]["diagnostic_joint_vector"]["q_rad"] and conflict.get("cad_static_representation_q6_rad") == [0.0]*6 and conflict.get("resolved") is False and conflict.get("effect") == "CURRENT_COMPLETE_CONFIGURATION_GEOMETRY_FALSE")
    add("CORE10_C05_C06_C07_C09_HOLDS_PRESERVED", "567P734_MM" in state["C05"]["non_authoritative_candidates"]["q6_rad"]["status"] and state["C05"]["operational_state"] == "HOLD_ABORT_ONLY" and "RATIFICATION_HOLD" in state["C06"]["non_authoritative_candidates"]["q6_rad"]["status"] and all("DIAGNOSTIC_CANDIDATE" in state[cid]["non_authoritative_candidates"]["q6_rad"]["status"] for cid in ("C07","C08","C09")))
    add("CORE11_GRIPPER_2P_VALUES_ALL_NULL_DOMAIN_ONLY", all(row["authoritative_state"][f"gripper_joint{i}_m"]["value"] is None and row["authoritative_state"][f"gripper_joint{i}_m"]["allowed_domain_m"] == [0.0,0.0715] for row in state_rows for i in (1,2)))
    add(
        "CORE12_SOLAR_HDRM_LATCH_AND_ARM_HDRM_STRUCTURED_NULL",
        all(
            row["authoritative_state"].get("solar_hdrm_state") == EXPECTED_SOLAR_HDRM_NULL
            and row["authoritative_state"].get("solar_latch_state") == EXPECTED_SOLAR_LATCH_NULL
            and row["authoritative_state"].get("arm_hdrm_state") == EXPECTED_ARM_HDRM_NULL
            for row in state_rows
        ),
    )
    add("CORE13_TARGET_ATTACHMENT_TRANSFORMS_AUTHORITATIVE_NULL", all(row["authoritative_state"]["target"]["attachment_transform_S_rows"]["value"] is None for row in state_rows))
    add("CORE14_SOLAR_AUTHORITY_BOUND_ONLY_WHERE_SUPPORTED", state["C01"]["authoritative_state"]["solar"]["logical_state"]["value"] == "DEPLOYED_NOMINAL_FIXED_SNAPSHOT" and all(state[cid]["authoritative_state"]["solar"]["failure_retention_semantics"]["value"] == "ATTACHED_STUCK__JETTISON_FORBIDDEN" for cid in ("C02","C03","C04")) and all(state[cid]["authoritative_state"]["solar"]["logical_state"]["value"] is None for cid in ("C05","C06","C07","C08","C09")))
    add("CORE15_C08_C09_TARGET_DESIGN_SEMANTICS_LOW_CONFIDENCE_NO_ATTACHMENT_AUTHORITY", all(state[cid]["authoritative_state"]["target"]["scenario_member"]["value"] is True and state[cid]["authoritative_state"]["target"]["operational_attachment_authority"] is False for cid in ("C08","C09")))

    geometry_rows = docs["geometry"]
    geom = {row["configuration_id"]: row for row in geometry_rows}
    add("CORE16_GEOMETRY_CURRENT_COMPLETE_0_TOPOLOGY_1_DIAGNOSTIC_9_COLLISION_0", len(geom) == 9 and sum(r["current_complete_integrated_geometry"] == "true" for r in geometry_rows) == 0 and sum(r["current_source_only_topology_candidate"] == "true" for r in geometry_rows) == 1 and sum(r["diagnostic_m5_geometry_present"] == "true" for r in geometry_rows) == 9 and sum(r["released_collision_clear"] == "true" for r in geometry_rows) == 0)
    add(
        "CORE17_M5_GEOMETRY_WITNESSES_HASHED_BBOX_EXACT_AND_NOT_PROMOTED",
        all(
            sha256(WORKSPACE / m5[cid]["snapshot"]["path"]) == m5[cid]["snapshot"]["sha256"]
            and geom[cid]["diagnostic_snapshot_path"] == m5[cid]["snapshot"]["path"]
            and geom[cid]["diagnostic_snapshot_sha256"] == m5[cid]["snapshot"]["sha256"]
            and _bbox_pair_matches(geom[cid], m5[cid]["bbox_S_m"])
            and geom[cid]["diagnostic_mass_properties_authority"] == "false"
            and geom[cid]["diagnostic_verified_system_collision_clear"] == "false"
            for cid in CONFIG_NAMES
        ),
    )
    dynamics_rows = docs["dynamics"].get("records", [])
    dynamics = {row["configuration_id"]: row for row in dynamics_rows}
    add("CORE18_DYNAMICS_USE_MATRIX_FAIL_CLOSED_NO_PARENT_CREDIT", len(dynamics) == 9 and all(dynamics[cid]["maximum_permitted_use"] == EXPECTED_DYNAMICS_USES[cid] and dynamics[cid]["design_mass_property_loading_allowed"] is True and dynamics[cid]["current_geometry_collision_allowed"] is False and dynamics[cid]["target_attachment_plant_allowed"] is False and dynamics[cid]["non_abort_operational_authority"] is False and dynamics[cid]["parent_gate_credit"] is False for cid in CONFIG_NAMES) and docs["dynamics"]["parent_dynamics_gate_reissued"] is False and docs["dynamics"]["next_stage_authorized"] is False)
    add("CORE19_PARENT_RELEASE_M01_AND_EXECUTION_AUTHORITY_FALSE", sources["release_gate"].get("next_stage_authorized") is False and sources["configuration_ref"].get("next_stage_authorized") is False and sources["system_interface"].get("next_stage_authorized") is False and sources["m01_scene_schema"].get("next_stage_authorized") is False and sources["m01_prebind_gate"].get("next_stage_authorized") is False and sources["m01_prebind_gate"]["scene_accounting"]["stage_instances_bound"] == 0 and sources["m01_prebind_gate"]["system_execution_state"]["system_pair_queries_executed"] == 0)

    false_keys = {"authority","authority_upgrade","parent_gate_credit","parent_gate_reissued","parent_dynamics_gate_reissued","next_stage_authorized","release_credit","non_abort_operational_authority","operational_attachment_authority","current_geometry_collision_allowed","target_attachment_plant_allowed","production_complete_state_vector","continuous_state_complete","discrete_state_complete","released_collision_clear"}
    add("CORE20_ALL_LOCAL_TOP_LEVEL_AND_RECURSIVE_AUTHORITY_BOUNDARIES_FALSE", all(value is False for doc_id in ("source_lock","crosswalk","state","mass","dynamics") for key,value in _walk_key_values(docs[doc_id]) if key in false_keys))
    add("CORE21_CONFIGURATION_NAMES_EXACT_ACROSS_ALL_FIVE_LOCAL_VIEWS", all(cross[cid]["contract_name"] == state[cid]["name"] == mass[cid]["name"] == geom[cid]["name"] == dynamics[cid]["name"] == CONFIG_NAMES[cid] for cid in CONFIG_NAMES))
    add("CORE22_OPERATIONAL_PRODUCTION_COMPLETE_COLLISION_AND_ATTACHMENT_ALL_HELD", all(row["production_complete_state_vector"] is False and row["continuous_state_complete"] is False and row["discrete_state_complete"] is False and row["authoritative_state"]["target"]["operational_attachment_authority"] is False for row in state_rows) and all(row["non_abort_operational_authority"] is False and row["current_geometry_collision_allowed"] is False and row["target_attachment_plant_allowed"] is False for row in dynamics_rows) and all(row["current_complete_integrated_geometry"] == "false" and row["released_collision_clear"] == "false" for row in geometry_rows))
    add("CORE23_PARTIAL_GEOMETRY_ISOLATED_TO_C01_AND_NEVER_COMPLETE", [row["configuration_id"] for row in geometry_rows if row["current_partial_master_geometry"] == "true"] == ["C01"] and geom["C01"]["current_complete_integrated_geometry"] == "false" and "PARTIAL_41_SOLID_MASTER" in geom["C01"]["current_geometry_status"])
    add("CORE24_MAXIMUM_CLAIMS_REMAIN_NARROW_AND_CONFIGURATION_SPECIFIC", all(row["maximum_claim"] == "DESIGN_DYNAMICS_INPUT_CANDIDATE_ONLY__NOT_AS_BUILT_NOT_RELEASED" and row["model_class"] == "DESIGN_MODEL_R2_CANDIDATE_ONLY" for row in mass_rows) and all(dynamics[cid]["maximum_permitted_use"] == EXPECTED_DYNAMICS_USES[cid] for cid in CONFIG_NAMES) and geom["C01"]["maximum_claim"] == "SOURCE_ONLY_TOPOLOGY_AND_PARTIAL_STATIC_GEOMETRY_CANDIDATE__NO_COLLISION_CREDIT" and all(geom[cid]["maximum_claim"] == "DIAGNOSTIC_GEOMETRY_WITNESS_ONLY__NO_CURRENT_GEOMETRY_CREDIT" for cid in CONFIG_NAMES if cid != "C01"))
    add("CORE25_LOCAL_CONTRACT_AUTHORITY_TEXT_AND_ZERO_COUNTS_EXACT", lock.get("policy") == "EXACT_BYTES_AND_SHA256__FAIL_CLOSED_ON_ANY_SOURCE_CHANGE" and docs["crosswalk"].get("explicit_nonclaim") == "IDENTITY_CROSSWALK_DOES_NOT_CREATE_GEOMETRY_COLLISION_OR_OPERATIONAL_AUTHORITY" and docs["state"].get("unknown_policy") == "UNKNOWN_PHYSICAL_VALUES_ARE_NULL__ZERO_FILL_FORBIDDEN" and docs["mass"].get("as_built_configuration_count") == 0 and docs["state"].get("production_complete_state_vector_count") == 0)
    failed = [key for key, result in checks.items() if not result["pass"]]
    return {"checks": checks, "pass": not failed, "failed": failed}


def _builder_negative_controls(docs, sources, core_result, core_payloads):
    controls = []

    def parser_control(control_id, title, parser, payload):
        caught = False
        error = None
        try:
            parser(payload)
        except BuildDataError as exc:
            caught = True
            error = str(exc)
        controls.append({"id": control_id, "title": title, "caught": caught, "expected_failed_check": "STRICT_PARSER", "observed": error})

    def mutation_control(control_id, title, mutate, expected_check):
        candidate = copy.deepcopy(docs)
        mutate(candidate)
        result = _generator_checks(candidate, sources)
        caught = expected_check in result["failed"]
        controls.append({"id": control_id, "title": title, "caught": caught, "expected_failed_check": expected_check, "observed_failed_checks": [expected_check] if caught else []})

    parser_control("NC01_DUPLICATE_JSON_KEY", "duplicate JSON keys are rejected", strict_json_loads, '{"a":1,"a":2}')
    parser_control("NC02_NONFINITE_YAML", "YAML NaN is rejected", strict_yaml_loads, "a: .nan\n")
    mutation_control("NC03_C05_CANDIDATE_Q_PROMOTION", "held C05 q6 cannot be promoted to authoritative state", lambda d: d["state"]["configurations"][4]["authoritative_state"]["q6_rad"].update({"value": [2.540711,-2.932153,-0.994838,-0.718081,-0.365716,-0.05236], "status": "AUTHORITY_BOUND_ACCEPTED_RUNTIME_DIGITAL_POSE"}), "CORE08_Q6_AUTHORITY_TIER_AND_EHW_LIMITS_EXACT")
    mutation_control("NC04_C05_HOLD_REMOVAL", "C05 567.734 mm FK hold cannot be erased", lambda d: d["state"]["configurations"][4]["non_authoritative_candidates"]["q6_rad"].update({"status": "PASS"}), "CORE10_C05_C06_C07_C09_HOLDS_PRESERVED")
    mutation_control("NC05_C08_ATTACHMENT_TRANSFORM_PROMOTION", "display-only target transform cannot enter authoritative state", lambda d: d["state"]["configurations"][7]["authoritative_state"]["target"]["attachment_transform_S_rows"].update({"value": [[1,0,0,1.24],[0,1,0,0],[0,0,1,-0.1],[0,0,0,1]]}), "CORE13_TARGET_ATTACHMENT_TRANSFORMS_AUTHORITATIVE_NULL")
    mutation_control("NC06_DIAGNOSTIC_GEOMETRY_PROMOTION", "M5 diagnostic geometry cannot be promoted to current integrated geometry", lambda d: d["geometry"][1].update({"current_complete_integrated_geometry": "true"}), "CORE16_GEOMETRY_CURRENT_COMPLETE_0_TOPOLOGY_1_DIAGNOSTIC_9_COLLISION_0")
    mutation_control("NC07_PARENT_GATE_CREDIT_TRUE", "configuration matrix cannot grant parent Gate credit", lambda d: d["dynamics"]["records"][0].update({"parent_gate_credit": True}), "CORE18_DYNAMICS_USE_MATRIX_FAIL_CLOSED_NO_PARENT_CREDIT")
    mutation_control("NC08_MASS_TAMPER", "mass-property view must remain bit-exact to V3_R2", lambda d: d["mass"]["configurations"][0].update({"mass_kg": d["mass"]["configurations"][0]["mass_kg"] + 1.0}), "CORE05_MASS_CG_INERTIA_IEEE754_BIT_EXACT_AND_TYPE_AUDITED")
    mutation_control("NC09_SOURCE_HASH_TAMPER", "source lock hash tampering is detected", lambda d: d["source_lock"]["sources"][0].update({"sha256": "0"*64}), "CORE01_SOURCE_PINS_EXACT")
    mutation_control("NC10_GRIPPER_ZERO_FILL", "unknown gripper state cannot be zero-filled", lambda d: d["state"]["configurations"][0]["authoritative_state"]["gripper_joint1_m"].update({"value": 0.0}), "CORE11_GRIPPER_2P_VALUES_ALL_NULL_DOMAIN_ONLY")
    parser_control("NC11_NONFINITE_JSON_INFINITY", "JSON Infinity is rejected", strict_json_loads, '{"a":Infinity}')
    parser_control("NC12_DUPLICATE_YAML_KEY", "duplicate YAML keys are rejected", strict_yaml_loads, "a: 1\na: 2\n")
    mutation_control("NC13_MASS_TYPE_DOWNCAST", "binary64 mass leaves cannot be downcast to integer", lambda d: d["mass"]["configurations"][0].update({"mass_kg": 31}), "CORE05_MASS_CG_INERTIA_IEEE754_BIT_EXACT_AND_TYPE_AUDITED")
    mutation_control("NC14_MASS_ONE_ULP_TAMPER", "one-ULP mass changes are detected", lambda d: d["mass"]["configurations"][0].update({"mass_kg": math.nextafter(d["mass"]["configurations"][0]["mass_kg"], math.inf)}), "CORE05_MASS_CG_INERTIA_IEEE754_BIT_EXACT_AND_TYPE_AUDITED")
    mutation_control("NC15_TOP_LEVEL_NEXT_STAGE_TRUE", "top-level next-stage authority cannot be promoted", lambda d: d["state"].update({"next_stage_authorized": True}), "CORE20_ALL_LOCAL_TOP_LEVEL_AND_RECURSIVE_AUTHORITY_BOUNDARIES_FALSE")
    mutation_control("NC16_TOP_LEVEL_RELEASE_CREDIT_TRUE", "top-level release credit cannot be promoted", lambda d: d["dynamics"].update({"release_credit": True}), "CORE20_ALL_LOCAL_TOP_LEVEL_AND_RECURSIVE_AUTHORITY_BOUNDARIES_FALSE")
    mutation_control("NC17_OPERATIONAL_AUTHORITY_TRUE", "non-abort operational authority cannot be promoted", lambda d: d["dynamics"]["records"][0].update({"non_abort_operational_authority": True}), "CORE20_ALL_LOCAL_TOP_LEVEL_AND_RECURSIVE_AUTHORITY_BOUNDARIES_FALSE")
    mutation_control("NC18_PRODUCTION_COMPLETE_TRUE", "incomplete state vectors cannot be marked production complete", lambda d: d["state"]["configurations"][0].update({"production_complete_state_vector": True}), "CORE20_ALL_LOCAL_TOP_LEVEL_AND_RECURSIVE_AUTHORITY_BOUNDARIES_FALSE")
    mutation_control("NC19_PARTIAL_GEOMETRY_SPREAD", "partial master geometry cannot spread beyond C01", lambda d: d["geometry"][1].update({"current_partial_master_geometry": "true"}), "CORE23_PARTIAL_GEOMETRY_ISOLATED_TO_C01_AND_NEVER_COMPLETE")
    mutation_control("NC20_CONFIGURATION_NAME_DRIFT", "configuration names must agree across every local view", lambda d: d["mass"]["configurations"][0].update({"name": "DEPLOYED_NOMINAL_DRIFT"}), "CORE21_CONFIGURATION_NAMES_EXACT_ACROSS_ALL_FIVE_LOCAL_VIEWS")

    local_meta = {rel: _payload_metadata(payload) for rel, payload in core_payloads.items()}
    local_meta[NEGATIVE_FILE] = {"bytes": 0, "sha256": "0" * 64}
    spec_meta = {
        "bytes": (PACKAGE / SPEC_FILE).stat().st_size,
        "sha256": sha256(PACKAGE / SPEC_FILE),
    }
    baseline_gate = _gate(
        core_result,
        {"summary": {"all_caught": True}},
        local_bindings=local_meta,
    )
    baseline_gate_ok = _builder_gate_integrity(
        baseline_gate, core_result["checks"], local_meta, spec_meta, len(NEGATIVE_CONTROL_IDS)
    )
    manifest_meta = {}
    for rel in EXPECTED_MANIFEST_FILES:
        if rel in core_payloads:
            manifest_meta[rel] = _payload_metadata(core_payloads[rel])
        elif rel == NEGATIVE_FILE:
            manifest_meta[rel] = local_meta[NEGATIVE_FILE]
        elif rel == GATE_FILE:
            manifest_meta[rel] = _payload_metadata(canonical_json_bytes(baseline_gate))
        else:
            manifest_meta[rel] = {
                "bytes": (PACKAGE / rel).stat().st_size,
                "sha256": sha256(PACKAGE / rel),
            }
    baseline_manifest = [
        {
            "path": rel,
            "bytes": str(manifest_meta[rel]["bytes"]),
            "sha256": manifest_meta[rel]["sha256"],
            "role": EXPECTED_MANIFEST_ROLES[rel],
        }
        for rel in sorted(EXPECTED_MANIFEST_FILES)
    ]
    baseline_manifest_ok = _builder_manifest_integrity(baseline_manifest, manifest_meta)

    def full_integrity_control(control_id, title, expected_check, mutate, layer):
        gate_candidate = copy.deepcopy(baseline_gate)
        manifest_candidate = copy.deepcopy(baseline_manifest)
        mutate(gate_candidate, manifest_candidate)
        if layer == "gate":
            caught = baseline_gate_ok and not _builder_gate_integrity(
                gate_candidate, core_result["checks"], local_meta, spec_meta, len(NEGATIVE_CONTROL_IDS)
            )
        elif layer == "manifest":
            caught = baseline_manifest_ok and not _builder_manifest_integrity(manifest_candidate, manifest_meta)
        else:
            raise AssertionError(layer)
        controls.append({"id": control_id, "title": title, "caught": caught, "expected_failed_check": expected_check, "observed_failed_checks": [expected_check] if caught else []})

    full_integrity_control("NC21_GATE_LOCAL_HASH_TAMPER", "Gate local artifact hash tampering is detected", "FULL27_GATE_COUNTS_FLAGS_SPEC_AND_LOCAL_BINDINGS", lambda g,m:g["local_artifact_bindings"][CORE_FILES["source_lock"]].update({"sha256":"0"*64}), "gate")
    full_integrity_control("NC22_MANIFEST_EXTRA_ROW", "manifest extra rows are rejected", "FULL28_MANIFEST_EXACT_UNIQUE_ROLE_NO_EXTRA_SELF_EXCLUDED", lambda g,m:m.append({"path":"EXTRA.txt","bytes":"0","sha256":"0"*64,"role":"EXTRA"}), "manifest")
    full_integrity_control("NC23_MANIFEST_DUPLICATE_ROW", "manifest duplicate rows are rejected", "FULL28_MANIFEST_EXACT_UNIQUE_ROLE_NO_EXTRA_SELF_EXCLUDED", lambda g,m:m.append(copy.deepcopy(m[0])), "manifest")
    mutation_control("NC24_SOURCE_PATH_TAMPER", "source lock paths cannot drift even when hash text is unchanged", lambda d:d["source_lock"]["sources"][0].update({"path":"../escape"}), "CORE01_SOURCE_PINS_EXACT")
    full_integrity_control("NC25_SPEC_BINDING_HASH_TAMPER", "frozen spec binding hash tampering is detected", "FULL27_GATE_COUNTS_FLAGS_SPEC_AND_LOCAL_BINDINGS", lambda g,m:g["contract_spec_binding"].update({"sha256":"0"*64}), "gate")
    mutation_control("NC26_SOURCE_LOCK_DUPLICATE_ID", "duplicate source-lock IDs are rejected even when raw row count remains 20", lambda d:d["source_lock"]["sources"][1].update({"source_id":d["source_lock"]["sources"][0]["source_id"]}), "CORE01_SOURCE_PINS_EXACT")
    mutation_control("NC27_SOURCE_LOCK_DUPLICATE_PATH", "duplicate source-lock paths are rejected", lambda d:d["source_lock"]["sources"][1].update({"path":d["source_lock"]["sources"][0]["path"]}), "CORE01_SOURCE_PINS_EXACT")
    mutation_control("NC28_SOURCE_LOCK_COUNT_TAMPER", "source-lock declared count must be an exact integer equal to raw and mapped counts", lambda d:d["source_lock"].update({"source_count":20.0}), "CORE01_SOURCE_PINS_EXACT")
    mutation_control("NC29_SOURCE_LOCK_ALL_MATCH_FALSE", "source-lock aggregate match flag must remain true", lambda d:d["source_lock"].update({"all_sources_match":False}), "CORE01_SOURCE_PINS_EXACT")
    mutation_control("NC30_STRUCTURED_NULL_EMPTY_MAPPING", "empty mappings cannot masquerade as structured unknown hardware state", lambda d:d["state"]["configurations"][0]["authoritative_state"]["solar_hdrm_state"].update({"value":{}}), "CORE12_SOLAR_HDRM_LATCH_AND_ARM_HDRM_STRUCTURED_NULL")
    mutation_control("NC31_GEOMETRY_BBOX_MALFORMED_JSON", "diagnostic bbox cells must be strict finite JSON binary64 triples", lambda d:d["geometry"][0].update({"diagnostic_bbox_min_S_m":"[0.0,NaN,1.0]"}), "CORE17_M5_GEOMETRY_WITNESSES_HASHED_BBOX_EXACT_AND_NOT_PROMOTED")
    mutation_control("NC32_GEOMETRY_BBOX_ONE_ULP_TAMPER", "one-ULP diagnostic bbox drift from M5 is detected", lambda d:d["geometry"][0].update({"diagnostic_bbox_min_S_m":json.dumps([math.nextafter(_parse_bbox_cell(d["geometry"][0]["diagnostic_bbox_min_S_m"])[0],math.inf)]+_parse_bbox_cell(d["geometry"][0]["diagnostic_bbox_min_S_m"])[1:],separators=(",",":"),allow_nan=False)}), "CORE17_M5_GEOMETRY_WITNESSES_HASHED_BBOX_EXACT_AND_NOT_PROMOTED")
    mutation_control("NC33_DESIGN_CHECK_BOOLEAN_TAMPER", "every design_checks_from_ssot field is independently source-bound", lambda d:d["mass"]["configurations"][0]["design_checks_from_ssot"].update({"non_solar_members_carried_verbatim":False}), "CORE06_DESIGN_CHECKS_SSOT_EXACT_MIN_EIGENVALUE_IEEE754_AND_INERTIA_PHYSICS")
    mutation_control("NC34_MIN_EIGENVALUE_ONE_ULP_TAMPER", "one-ULP minimum-eigenvalue drift is detected", lambda d:d["mass"]["configurations"][0]["design_checks_from_ssot"].update({"min_eigenvalue_kg_m2":math.nextafter(d["mass"]["configurations"][0]["design_checks_from_ssot"]["min_eigenvalue_kg_m2"],math.inf)}), "CORE06_DESIGN_CHECKS_SSOT_EXACT_MIN_EIGENVALUE_IEEE754_AND_INERTIA_PHYSICS")
    full_integrity_control("NC35_MANIFEST_ROLE_TAMPER", "manifest roles are exact contract fields", "FULL28_MANIFEST_EXACT_UNIQUE_ROLE_NO_EXTRA_SELF_EXCLUDED", lambda g,m:m[0].update({"role":"WRONG_ROLE"}), "manifest")

    if [control["id"] for control in controls] != NEGATIVE_CONTROL_IDS:
        raise RuntimeError("negative-control ID/order drift from frozen spec")
    passed = sum(control["caught"] for control in controls)
    return {
        "schema": "M4_L02_NEGATIVE_CONTROL_RESULTS_V1",
        "generated_utc": "DETERMINISTIC_NO_WALLCLOCK",
        "authority": "FALSIFICATION_EVIDENCE_ONLY__NO_PARENT_GATE_CREDIT",
        "controls": controls,
        "summary": {"passed": passed, "total": len(controls), "all_caught": passed == len(controls)},
        "next_stage_authorized": False,
        "release_credit": False,
    }


def _local_binding(filename: str) -> dict:
    path = PACKAGE / filename
    return {"bytes": path.stat().st_size, "sha256": sha256(path)}


def _gate(core_result: dict, negative: dict, local_bindings=None) -> dict:
    criteria = []
    for check_id, result in core_result["checks"].items():
        criteria.append({"id": check_id, "status": "PASS" if result["pass"] else "FAIL"})
    criteria.append(
        {
            "id": "GATE26_NEGATIVE_CONTROLS_ALL_CAUGHT",
            "status": "PASS" if negative["summary"]["all_caught"] else "FAIL",
        }
    )
    bound_files = list(CORE_FILES.values()) + [NEGATIVE_FILE]
    if local_bindings is None:
        local_bindings = {filename: _local_binding(filename) for filename in bound_files}
    return {
        "schema": "M4_L02_CONFIGURATION_STATE_CONTRACT_GATE_V1",
        "generated_utc": GENERATED,
        "gate_verdict": VERDICT if all(row["status"] == "PASS" for row in criteria) else "FAIL_CONFIGURATION_CONTRACT",
        "criteria": criteria,
        "summary": {
            "source_pins": "20_OF_20",
            "configuration_ids": "9_OF_9",
            "design_mass_properties": "9_OF_9",
            "complete_current_geometry": "0_OF_9",
            "source_only_current_topology": "1_OF_9",
            "diagnostic_geometry_witnesses": "9_OF_9",
            "released_collision": "0_OF_9",
            "production_complete_state_vectors": "0_OF_9",
            "as_built_mass_properties": "0_OF_9",
            "negative_controls": f"{len(NEGATIVE_CONTROL_IDS)}_OF_{len(NEGATIVE_CONTROL_IDS)}",
        },
        "local_artifact_bindings": local_bindings,
        "contract_spec_binding": {
            "path": SPEC_FILE,
            "bytes": (PACKAGE / SPEC_FILE).stat().st_size,
            "sha256": sha256(PACKAGE / SPEC_FILE),
            "schema": SPEC_SCHEMA,
        },
        "parent_gate_credit": False,
        "parent_gate_reissued": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "required_next_evidence": [
            "CURRENT_INTEGRATED_C01_GEOMETRY_AT_CONFIGURATION_QHOME",
            "C02_C09_CURRENT_INTEGRATED_GEOMETRY_AS_REQUIRED_BY_DOWNSTREAM_USE",
            "RELEASED_SYSTEM_COLLISION_AND_CONTACT_EVIDENCE",
            "MEASURED_OR_RATIFIED_GRIPPER_HDRM_LATCH_AND_TARGET_ATTACHMENT_STATE",
            "AS_BUILT_MASS_CG_INERTIA_WHEN_HARDWARE_EXISTS",
        ],
    }


def _manifest_bytes() -> bytes:
    if set(EXPECTED_MANIFEST_ROLES) != EXPECTED_MANIFEST_FILES:
        raise RuntimeError("manifest role map drift from frozen exact file set")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=["path", "bytes", "sha256", "role"], lineterminator="\n")
    writer.writeheader()
    for rel in sorted(EXPECTED_MANIFEST_ROLES):
        path = PACKAGE / rel
        writer.writerow({"path": rel, "bytes": path.stat().st_size, "sha256": sha256(path), "role": EXPECTED_MANIFEST_ROLES[rel]})
    return output.getvalue().encode("utf-8")


def _write(path: Path, payload: bytes) -> None:
    path.write_bytes(payload)


def _compare(path: Path, expected: bytes) -> bool:
    return path.exists() and path.read_bytes() == expected


def build(write: bool) -> list[str]:
    _verify_pins()
    sources = load_sources()
    core = _core_bytes(sources)
    mismatches = []
    for filename, payload in core.items():
        path = PACKAGE / filename
        if write:
            _write(path, payload)
        elif not _compare(path, payload):
            mismatches.append(filename)
    if mismatches:
        return mismatches

    docs = _core_docs_from_bytes(core)
    core_result = _generator_checks(docs, sources)
    if not core_result["pass"]:
        raise RuntimeError(f"refusing generation; independent builder guards failed: {core_result['failed']}")
    negative = _builder_negative_controls(docs, sources, core_result, core)
    negative_bytes = canonical_json_bytes(negative)
    if write:
        _write(PACKAGE / NEGATIVE_FILE, negative_bytes)
    elif not _compare(PACKAGE / NEGATIVE_FILE, negative_bytes):
        mismatches.append(NEGATIVE_FILE)
        return mismatches

    if not core_result["pass"] or not negative["summary"]["all_caught"]:
        raise RuntimeError(f"refusing Gate emission; core={core_result['failed']} negative={negative['summary']}")
    gate_object = _gate(core_result, negative)
    expected_local_meta = {rel: _payload_metadata(payload) for rel, payload in core.items()}
    expected_local_meta[NEGATIVE_FILE] = _payload_metadata(negative_bytes)
    spec_meta = {
        "bytes": (PACKAGE / SPEC_FILE).stat().st_size,
        "sha256": sha256(PACKAGE / SPEC_FILE),
    }
    if not _builder_gate_integrity(
        gate_object, core_result["checks"], expected_local_meta, spec_meta, len(NEGATIVE_CONTROL_IDS)
    ):
        raise RuntimeError("refusing Gate emission; builder full Gate integrity check failed")
    gate_bytes = canonical_json_bytes(gate_object)
    if write:
        _write(PACKAGE / GATE_FILE, gate_bytes)
    elif not _compare(PACKAGE / GATE_FILE, gate_bytes):
        mismatches.append(GATE_FILE)
        return mismatches

    manifest_bytes = _manifest_bytes()
    manifest_reader = csv.DictReader(io.StringIO(manifest_bytes.decode("utf-8")))
    manifest_rows = list(manifest_reader)
    manifest_meta = {
        rel: {"bytes": (PACKAGE / rel).stat().st_size, "sha256": sha256(PACKAGE / rel)}
        for rel in EXPECTED_MANIFEST_FILES
    }
    if not _builder_manifest_integrity(manifest_rows, manifest_meta):
        raise RuntimeError("refusing manifest emission; builder full manifest integrity check failed")
    if write:
        _write(PACKAGE / MANIFEST_FILE, manifest_bytes)
    elif not _compare(PACKAGE / MANIFEST_FILE, manifest_bytes):
        mismatches.append(MANIFEST_FILE)
    return mismatches


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="emit deterministic package artifacts")
    mode.add_argument("--check", action="store_true", help="prove checked-in artifacts are byte-identical")
    args = parser.parse_args(argv)
    mismatches = build(write=args.write)
    if mismatches:
        print("FAIL deterministic mismatches: " + ", ".join(mismatches), file=sys.stderr)
        return 1
    print("PASS wrote deterministic M4-L02 package" if args.write else "PASS deterministic byte identity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
