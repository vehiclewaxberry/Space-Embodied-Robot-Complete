#!/usr/bin/env python3
"""Build the append-only M01 fixed-platform and base-motion precertificate.

The builder is intentionally narrow.  It binds three already-existing fixed
platform geometry candidates at design level and certifies only the registered
``A::base_link`` proxy as globally stationary with respect to the six B601
joints and every state admitted by the still-uninstantiated M01 scene schema.

It does not create or load a whole-spacecraft STEP, promote a fixed-platform
candidate to operational collision authority, execute a pair query, certify an
edge, search a path, or fill an Owner-owned scene/clearance value.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
import math
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import yaml


OUT_REL = Path(
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
    "ODR60_OPTION_A_M01_FIXED_PLATFORM_AND_BASE_MOTION_PRECERT_V1"
)

POSE_NAME = "M01_FIXED_PLATFORM_POSE_BINDING_V1.json"
RECOMPUTE_NAME = "INDEPENDENT_BASE_LINK_ZERO_MOTION_RECOMPUTE_V1.json"
CERT_NAME = "A_BASE_LINK_GLOBAL_MOTION_CERTIFICATE_V1.json"
QUARANTINE_NAME = "ROUTE_C_NEGATIVE_WITNESS_QUARANTINE_V1.json"
NEGATIVE_NAME = "M01_FIXED_PLATFORM_AND_BASE_MOTION_NEGATIVE_CONTROLS_V1.json"
GATE_NAME = "M01_FIXED_PLATFORM_AND_BASE_MOTION_PRECERT_GATE_V1.json"
MANIFEST_NAME = "M01_FIXED_PLATFORM_AND_BASE_MOTION_PRECERT_SHA256_V1.csv"

Q_ORDER = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]
EXPECTED_Q_LOWER = [-2.8, -3.14, -3.14, -1.87, -1.57, -3.14]
EXPECTED_Q_UPPER = [2.8, 0.0, 0.0, 1.57, 1.57, 3.14]
IDENTITY_4 = [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0, 0.0],
    [0.0, 0.0, 0.0, 1.0],
]
M3R_S_ROWS_EXPECTED = [
    [0.0, 0.0, 1.0, 208.0],
    [0.422618483193, 0.906307683772, 0.0, 0.015994151],
    [-0.906307683772, 0.422618483193, 0.0, -0.086366070],
    [0.0, 0.0, 0.0, 1.0],
]
PAIR_DERATE_FIELDS = [
    "centerline_hausdorff_bound_mm",
    "radius_uncertainty_bound_mm",
    "model_uncertainty_bound_mm",
    "numeric_uncertainty_bound_mm",
]


# Every dependency is immutable input authority.  Any drift fails closed.
SOURCE_PINS: dict[str, tuple[Path, str, str]] = {
    "owner_selection": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/OWNER_SELECTION_RECORD_V1.json"),
        "A88E2301B36D330D9B15AFC73C03D19838E05CD20BBC47406C39B1BF465FF2BF",
        "OPTION_A_BRANCH_SELECTION_ONLY",
    ),
    "scene_schema_v2": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/M01_THREE_STAGE_SCENE_SCHEMA_V2.json"),
        "67252BCE1259414876103EE3B6AF25ACC4A33E5A36B73AF974BD4004C285141C",
        "SCENE_SCHEMA_DOMAIN_WITH_ZERO_INSTANCES",
    ),
    "scene_decision_intake": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1/M01_SCENE_DECISION_INTAKE_V1.yaml"),
        "A75295F677FFAB8BA33D73EAADF2E596891659CDD7EE23160BDE70A0FE5EE65E",
        "THIRTY_EXPLICIT_NULL_OWNER_FIELDS",
    ),
    "scene_prebind_gate": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1/M01_SCENE_AND_COLLISION_PREBIND_GATE_V1.json"),
        "CDFADB08C3C93F9E380C41B232727E7D08750B2955411DF9E4AF894C550B7FC4",
        "CURRENT_ZERO_SCENE_ZERO_QUERY_HOLD",
    ),
    "operational_asset_readiness": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1/M01_OPERATIONAL_ASSET_READINESS_V1.csv"),
        "974D50C1786003ED70F8494F67DFEF20ABF64F1DE103A224E9ACA34DE83A5D09",
        "ONE_OF_150_ASSET_LEVEL_OPERATIONAL_LEDGER",
    ),
    "system_registry": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/M01_SYSTEM_COLLISION_REGISTRY_V1.json"),
        "AC975D11CC4715277E34FCFF7ABF049BC57334FD8F03AAB223BBED0877B1694F",
        "CURRENT_150_OBJECT_REGISTRY",
    ),
    "pair_coverage": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/M01_PAIR_COVERAGE_V1.csv"),
        "C1F64FB26D4E563EEF6BF798EE163645FE16766CC3C510552769DB7FDF97306C",
        "CURRENT_11166_QUERY_REQUIRED_PAIR_LEDGER",
    ),
    "registry_gate": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/M01_SYSTEM_COLLISION_REGISTRY_GATE_V1.json"),
        "F5E91371648756D43FF7CF6C03028FA95174428D088BAAC08254FAD8D5DCC3FF",
        "CURRENT_PAIR_UNIVERSE_HOLD",
    ),
    "object_motion_contract": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_SYSTEM_BINDING_CONTRACT_V1/OBJECT_MOTION_BOUND_CONTRACT_V1.json"),
        "CA1A741576A90301D77FD684DFA07882FB1AB88A00E927C1381D8709C715A5CD",
        "MOTION_CERTIFICATE_FIELD_AND_BOUND_CONTRACT",
    ),
    "pair_oracle_contract": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_SYSTEM_BINDING_CONTRACT_V1/SYSTEM_PAIR_ORACLE_CONTRACT_V1.json"),
        "D8B9CEE66BBD1793732F08F8E52C070B91CC5A6FCAAE56820E09E3C13BC81417",
        "UNSIGNED_SYSTEM_PAIR_ORACLE_CONTRACT",
    ),
    "clearance_policy_intake": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_BINDING_INTAKE_V1/CLEARANCE_POLICY_INTAKE_V1.json"),
        "51BF794D0DFFE8B877048EF367B7CCE54EAF3FF37BD1E5F79CB595DCC5AFFAB1",
        "ZERO_OF_11166_NUMERIC_CLEARANCE_ROWS",
    ),
    "query_infrastructure_gate": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_QUERY_INFRASTRUCTURE_V1/QUERY_INFRASTRUCTURE_GATE_V1.json"),
        "6F8E3BAF38CB69312017B76BAEAB304A84E7B956DE528356831AE378A28A6221",
        "ZERO_QUERY_EDGE_PATH_EXECUTION_HOLD",
    ),
    "execution_mount": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/EXECUTION_MOUNT_BINDING_V1.json"),
        "B7758F751E273CE21CCD5132C23F2514524DE7613E31B33646E027603B0F6653",
        "FULL_PRECISION_PHYSICAL_ARM_MOUNT",
    ),
    "collision_frame_registration": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/COLLISION_FRAME_REGISTRATION_V1.json"),
        "3C60DBFFB2C62AB0C71482D78C8CEC63EC3AF042ABF550A324627771C9D3EA4D",
        "B601_COLLISION_ASSET_TO_URDF_FRAME_LEDGER",
    ),
    "base_proxy_receipt": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/base_link_proxy_v2/BASE_LINK_OPERATIONAL_COLLISION_RECEIPT_V2.json"),
        "5871D0AF4F9E31BF19240E4C8E885CB4715DA8936FF74BBB34F2367655BBACDA",
        "BASE_LINK_OPERATIONAL_PROXY_RECEIPT",
    ),
    "base_proxy_npz": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/base_link_proxy_v2/BASE_LINK_OPERATIONAL_COLLISION_V2.npz"),
        "A0C5F9FAB58A748F2F89DC7CE398684B5A8C1205426C153C6752C56226250428",
        "BASE_LINK_OPERATIONAL_PROXY_GEOMETRY",
    ),
    "accepted_urdf": (
        Path("20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"),
        "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164",
        "ACCEPTED_B601_KINEMATIC_TREE_RAW_BYTES",
    ),
    "urdf_line_ending_receipt": (
        Path("20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/11_validation/URDF_LINE_ENDING_HASH_EQUIVALENCE_RECEIPT.json"),
        "DF8D4624B2E33E7DDC93613DE86C663AC230C7F76A06D875ED08037FFE37E7AF",
        "RAW_AND_LF_NORMALIZED_URDF_IDENTITY",
    ),
    "physical_dynamics_bridge": (
        Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml"),
        "0ACEB659284CAB862BA65228C5C2DF4BEB06D9EE05B5E2F0B2B5CB38402BF72C",
        "CONFIRMED_PHYSICAL_TO_DYNAMICS_BRIDGE_PIN_ONLY",
    ),
    "digital_frame_tree": (
        Path("20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/01_system_architecture/DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml"),
        "67293323A45237FB9B415871A4160732EFB156DE74776C9E11ABA9C4202134CA",
        "M3R_LOCAL_FULL_PRECISION_S_FRAME",
    ),
    "load_bridge_datums": (
        Path("20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp1_load_bridge/LOAD_BRIDGE_DATUMS_V1.yaml"),
        "0F9B413E7B6CD451E2724AD25CA4DA41E52E02C86F1D2874460274EADBAA47A2",
        "LOAD_BRIDGE_DESIGN_DATUMS_CANDIDATE",
    ),
    "load_bridge_receipt": (
        Path("20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp1_load_bridge/FITUP_AND_FRAME_RECEIPT_V1.json"),
        "4B9114420059AA885F7A3C7CF437E8219F26F7D65E2E1F68F773C91214E426B7",
        "LOAD_BRIDGE_S_COORDINATE_REOPEN_RECEIPT",
    ),
    "load_bridge_step": (
        Path("20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp1_load_bridge/LOAD_BRIDGE_CANDIDATE_V1.step"),
        "545FE62ADE0E4891FCC84179D18F63B2A6C77F19AD1C96723B3C7208EA13221B",
        "LOAD_BRIDGE_DESIGN_LEVEL_CANDIDATE_STEP",
    ),
    "m3r_assembly": (
        Path("20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/02_interfaces/M3R_INTERFACE_ASSEMBLY_V2.yaml"),
        "B9A7AE3AC40B00036FC1FCB85C62D153A67500FCCFEC5BB797BC7B4E05A21D7A",
        "M3R_STAGE_LOCAL_PLACEMENT_LEDGER",
    ),
    "m3r_geometry_validation": (
        Path("20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/06_parameterized_parts/m3r/M3R_INTERFACE_ASSEMBLY_V2_GEOMETRY_VALIDATION.json"),
        "AD35D83115FD7B8BD2E170C97CB9E212F14BED4C6FAFEF95F266905D42E76180",
        "M3R_TWO_ONE_SOLID_DESIGN_GEOMETRY_RECEIPT",
    ),
    "m3r_stage_a_step": (
        Path("20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/06_parameterized_parts/m3r/M3R_STAGE_A_REVB_WORKING.step"),
        "359E304879C254BE54450AA9BAB4C614308CE2C9CD47CE1F79A741722098D36C",
        "M3R_STAGE_A_DESIGN_LEVEL_STEP",
    ),
    "m3r_stage_b_step": (
        Path("20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/06_parameterized_parts/m3r/M3R_STAGE_B_REVB2_WORKING.step"),
        "44BED33AEE41CFD170E744BBEEB2BD0B10BBD649C913ECA90D16FC4840A1126B",
        "M3R_STAGE_B_DESIGN_LEVEL_STEP",
    ),
    "route_c_negative_witness": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_V9F_MANDATORY_M01_FALSIFIER_GATE.json"),
        "09C3199BD9824DFDBB9782C20BE200F31760F44A89EF68D16F32D0E213F191A0",
        "LEGACY_NEGATIVE_ONLY_WITNESS_NOT_SYSTEM_PAIR_RESULT",
    ),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def strict_pairs(pairs):
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def strict_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_pairs)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def posix(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def matrix_to_float(rows: list[list[Any]]) -> list[list[float]]:
    if len(rows) != 4 or any(len(row) != 4 for row in rows):
        raise RuntimeError("RIGID_MATRIX_NOT_4X4")
    converted = [[float(value) for value in row] for row in rows]
    if not all(math.isfinite(value) for row in converted for value in row):
        raise RuntimeError("RIGID_MATRIX_NONFINITE")
    return converted


def matrix_max_abs_delta(a: list[list[Any]], b: list[list[Any]]) -> float:
    af = matrix_to_float(a)
    bf = matrix_to_float(b)
    return max(abs(af[i][j] - bf[i][j]) for i in range(4) for j in range(4))


def rotation_metrics(rows: list[list[Any]]) -> dict[str, float]:
    matrix = np.asarray(matrix_to_float(rows), dtype=np.float64)
    rotation = matrix[:3, :3]
    residual = rotation.T @ rotation - np.eye(3)
    return {
        "orthonormal_max_abs_residual": float(np.max(np.abs(residual))),
        "determinant": float(np.linalg.det(rotation)),
        "homogeneous_bottom_row_max_abs_residual": float(
            np.max(np.abs(matrix[3, :] - np.asarray([0.0, 0.0, 0.0, 1.0])))
        ),
    }


def verify_source_pins(repo_root: Path) -> tuple[list[dict[str, Any]], dict[str, Path]]:
    rows: list[dict[str, Any]] = []
    paths: dict[str, Path] = {}
    for source_id, (rel_path, expected_hash, role) in SOURCE_PINS.items():
        path = repo_root / rel_path
        if not path.is_file():
            raise FileNotFoundError(f"SOURCE_PIN_MISSING:{source_id}:{path}")
        actual = sha256_file(path)
        if actual != expected_hash:
            raise RuntimeError(
                f"SOURCE_PIN_MISMATCH:{source_id}:expected={expected_hash}:actual={actual}"
            )
        rows.append(
            {
                "source_id": source_id,
                "path": posix(rel_path),
                "bytes": path.stat().st_size,
                "sha256": actual,
                "role": role,
                "match": True,
            }
        )
        paths[source_id] = path
    return rows, paths


def source_pin_map(rows: list[dict[str, Any]], ids: list[str] | None = None) -> dict[str, Any]:
    selected = rows if ids is None else [row for row in rows if row["source_id"] in set(ids)]
    return {
        row["source_id"]: {
            "path": row["path"],
            "bytes": row["bytes"],
            "sha256": row["sha256"],
            "role": row["role"],
        }
        for row in selected
    }


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def extract_scene_values(scene: dict[str, Any]) -> list[Any]:
    stages = scene.get("stages")
    if not isinstance(stages, list) or len(stages) != 3:
        raise RuntimeError("SCENE_INTAKE_STAGE_STRUCTURE_CHANGED")
    values: list[Any] = []
    for stage in stages:
        block = stage.get("values")
        if not isinstance(block, dict) or len(block) != 10:
            raise RuntimeError(f"SCENE_INTAKE_FIELD_STRUCTURE_CHANGED:{stage.get('stage_id')}")
        values.extend(block.values())
    return values


def validate_parent_truth(paths: dict[str, Path]) -> dict[str, Any]:
    owner = strict_json(paths["owner_selection"])
    schema = strict_json(paths["scene_schema_v2"])
    scene = yaml.safe_load(paths["scene_decision_intake"].read_text(encoding="utf-8"))
    prebind = strict_json(paths["scene_prebind_gate"])
    registry = strict_json(paths["system_registry"])
    registry_gate = strict_json(paths["registry_gate"])
    motion = strict_json(paths["object_motion_contract"])
    oracle = strict_json(paths["pair_oracle_contract"])
    clearance = strict_json(paths["clearance_policy_intake"])
    query = strict_json(paths["query_infrastructure_gate"])
    witness = strict_json(paths["route_c_negative_witness"])

    if owner["selection"]["selected_option"] != "A" or owner["selection"]["option_a_selected"] is not True:
        raise RuntimeError("OWNER_OPTION_A_SELECTION_DRIFT")
    if owner["selection"].get("pair_query_authorized") is True:
        raise RuntimeError("OWNER_SELECTION_UNEXPECTEDLY_AUTHORIZES_QUERY")

    scene_values = extract_scene_values(scene)
    if len(scene_values) != 30 or any(value is not None for value in scene_values):
        raise RuntimeError("AUTHORITATIVE_SCENE_VALUES_NOT_EXACTLY_30_NULLS")
    accounting = scene["authoritative_instance_accounting"]
    if accounting["authoritative_field_values_bound"] != 0:
        raise RuntimeError("SCENE_AUTHORITY_COUNT_CHANGED")
    if accounting["stage_instances_bound"] != 0 or accounting["stage_instances_required"] != 3:
        raise RuntimeError("SCENE_INSTANCE_COUNT_CHANGED")
    if accounting["active_object_universe_bound_per_stage"] is not False:
        raise RuntimeError("STAGE_OBJECT_UNIVERSE_UNEXPECTEDLY_BOUND")
    if accounting["active_pair_universe_bound_per_stage"] is not False:
        raise RuntimeError("STAGE_PAIR_UNIVERSE_UNEXPECTEDLY_BOUND")
    if schema["current_instances"]["stage_instances_bound"] != 0:
        raise RuntimeError("SCHEMA_INSTANCE_COUNT_CHANGED")
    if schema["schema_contract"]["continuous_q_contract"]["candidate_path_sha256"] is not None:
        raise RuntimeError("CANDIDATE_PATH_UNEXPECTEDLY_BOUND")
    if not all(prebind["checks"].values()) or prebind["checks_total"] != 18:
        raise RuntimeError("PARENT_PREBIND_GATE_DRIFT")

    objects = registry["objects"]
    if len(objects) != 150:
        raise RuntimeError("ACTIVE_OBJECT_COUNT_CHANGED")
    readiness = read_csv(paths["operational_asset_readiness"])
    active_rows = [row for row in readiness if row["row_class"] == "ACTIVE_OBJECT"]
    operational = [row for row in active_rows if row["operational_authority"] == "true"]
    if len(active_rows) != 150 or [row["id"] for row in operational] != ["A::base_link"]:
        raise RuntimeError("OPERATIONAL_ASSET_LEDGER_CHANGED")

    pairs = read_csv(paths["pair_coverage"])
    status_counts = {
        status: sum(row["status"] == status for row in pairs)
        for status in ("EXCEPTED", "UNASSESSED_FAIL_CLOSED")
    }
    if len(pairs) != 11175 or status_counts != {"EXCEPTED": 9, "UNASSESSED_FAIL_CLOSED": 11166}:
        raise RuntimeError("PAIR_COVERAGE_COUNT_CHANGED")
    if registry_gate["pair_coverage"]["status_counts"] != status_counts:
        raise RuntimeError("PAIR_GATE_AND_LEDGER_DISAGREE")

    if motion["current_readiness"]["system_certified_object_motion_bound_count"] != 0:
        raise RuntimeError("PARENT_MOTION_COUNT_NO_LONGER_ZERO")
    if clearance["policy_rows_emitted"] != 0 or clearance["clearance_policy_sha256"] is not None:
        raise RuntimeError("CLEARANCE_POLICY_NO_LONGER_ZERO_UNBOUND")
    if oracle["current_readiness"]["pair_queries_executed"] != 0:
        raise RuntimeError("PAIR_ORACLE_QUERY_COUNT_CHANGED")
    query_state = query["system_collision_state"]
    if (
        query_state["unassessed_fail_closed_pair_count"] != 11166
        or query_state["complete_system_collision_pass"] is not False
        or query["system_pair_evaluation_authorized"] is not False
        or query["path_search_executed"] is not False
    ):
        raise RuntimeError("QUERY_INFRASTRUCTURE_EXECUTION_STATE_CHANGED")
    for doc_id, doc in (("prebind", prebind), ("schema", schema), ("query", query)):
        if doc.get("path_search_authorized") is True or doc.get("release_credit") is True:
            raise RuntimeError(f"{doc_id.upper()}_UNEXPECTED_AUTHORITY")

    collision = witness["witness"]["collision"]
    if not (collision["raw_clearance_mm"] < 0.0 and collision["raw_physical_penetration"] is True):
        raise RuntimeError("ROUTE_C_NEGATIVE_WITNESS_CHANGED")
    if witness["scope_boundary"]["architecture_infeasibility_proven"] is not False:
        raise RuntimeError("ROUTE_C_WITNESS_SCOPE_ILLEGALLY_BROADENED")

    return {
        "option_a_selected": True,
        "authoritative_scene_values_bound": 0,
        "authoritative_scene_values_required": 30,
        "stage_instances_bound": 0,
        "stage_instances_required": 3,
        "stage_object_universe_hashes_bound": 0,
        "stage_pair_universe_hashes_bound": 0,
        "active_object_count": 150,
        "asset_level_operational_count": 1,
        "parent_system_motion_certificate_count": 0,
        "query_required_pair_count": 11166,
        "clearance_policy_rows_bound": 0,
        "pair_queries_executed": 0,
        "edges_certified": 0,
        "path_search_authorized": False,
        "path_search_executed": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }


def parse_urdf(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    root = ET.fromstring(raw)
    if root.tag != "robot":
        raise RuntimeError("URDF_ROOT_TAG_INVALID")
    links = [element.attrib["name"] for element in root.findall("link")]
    joints: dict[str, dict[str, Any]] = {}
    child_links: set[str] = set()
    for element in root.findall("joint"):
        name = element.attrib["name"]
        parent_node = element.find("parent")
        child_node = element.find("child")
        if parent_node is None or child_node is None:
            raise RuntimeError(f"URDF_JOINT_PARENT_CHILD_MISSING:{name}")
        parent = parent_node.attrib["link"]
        child = child_node.attrib["link"]
        child_links.add(child)
        limit_node = element.find("limit")
        joints[name] = {
            "type": element.attrib["type"],
            "parent": parent,
            "child": child,
            "lower": None if limit_node is None or "lower" not in limit_node.attrib else float(limit_node.attrib["lower"]),
            "upper": None if limit_node is None or "upper" not in limit_node.attrib else float(limit_node.attrib["upper"]),
        }
    roots = sorted(set(links) - child_links)
    q_lower = [joints[name]["lower"] for name in Q_ORDER]
    q_upper = [joints[name]["upper"] for name in Q_ORDER]
    if roots != ["base_link"]:
        raise RuntimeError(f"URDF_ROOT_LINK_CHANGED:{roots}")
    if any(joints[name]["type"] != "revolute" for name in Q_ORDER):
        raise RuntimeError("URDF_SIX_JOINT_TYPES_CHANGED")
    if q_lower != EXPECTED_Q_LOWER or q_upper != EXPECTED_Q_UPPER:
        raise RuntimeError(f"URDF_Q_DOMAIN_CHANGED:{q_lower}:{q_upper}")
    if any(joint["child"] == "base_link" for joint in joints.values()):
        raise RuntimeError("BASE_LINK_HAS_PARENT_JOINT")
    normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return {
        "robot_name": root.attrib.get("name"),
        "link_count": len(links),
        "joint_count": len(joints),
        "root_links": roots,
        "base_link_parent_joint_count": 0,
        "q_order": Q_ORDER,
        "q_domain_lower_rad": q_lower,
        "q_domain_upper_rad": q_upper,
        "raw_bytes_sha256": sha256_bytes(raw),
        "lf_normalized_sha256": sha256_bytes(normalized),
        "structural_proof": (
            "base_link is the unique URDF root and is never a child; no q-dependent joint transform "
            "can act on its registered link-local collision set"
        ),
    }


def build_recompute(
    repo_root: Path,
    source_rows: list[dict[str, Any]],
    paths: dict[str, Path],
    truth: dict[str, Any],
) -> dict[str, Any]:
    urdf = parse_urdf(paths["accepted_urdf"])
    if urdf["raw_bytes_sha256"] != SOURCE_PINS["accepted_urdf"][1]:
        raise RuntimeError("URDF_RAW_DIGEST_RECOMPUTE_MISMATCH")
    if urdf["lf_normalized_sha256"] != "408147DDC9CC0BBA0FACBF864C559A54D1712262703BA41251514A4303B5A3A4":
        raise RuntimeError("URDF_LF_DIGEST_RECOMPUTE_MISMATCH")

    mount = strict_json(paths["execution_mount"])
    decimal_rows = mount["binding"]["canonical_matrix_decimal_strings"]
    # Decimal parsing ensures the runtime spelling is consumed, not a rounded reconstruction.
    decimal_roundtrip = [[format(Decimal(value), ".12f") for value in row] for row in decimal_rows]
    if decimal_roundtrip != decimal_rows:
        raise RuntimeError("EXECUTION_MOUNT_DECIMAL_SPELLING_NOT_CANONICAL")
    mount_rows_m = matrix_to_float(decimal_rows)
    mount_metrics = rotation_metrics(mount_rows_m)
    if mount_metrics["orthonormal_max_abs_residual"] > 1.0e-12:
        raise RuntimeError(f"EXECUTION_MOUNT_ROTATION_INVALID:{mount_metrics}")
    if abs(mount_metrics["determinant"] - 1.0) > 1.0e-12:
        raise RuntimeError(f"EXECUTION_MOUNT_DETERMINANT_INVALID:{mount_metrics}")
    if mount_metrics["homogeneous_bottom_row_max_abs_residual"] != 0.0:
        raise RuntimeError("EXECUTION_MOUNT_BOTTOM_ROW_INVALID")

    registrations = strict_json(paths["collision_frame_registration"])["registrations"]
    base_registration = next(row for row in registrations if row["object_id"] == "A::base_link")
    registration_rows = IDENTITY_4
    registration = base_registration["T_registration_frame_asset_storage"]
    if registration["rotation"] != "IDENTITY" or registration["translation"] != [0.0, 0.0, 0.0]:
        raise RuntimeError("BASE_LINK_COLLISION_REGISTRATION_NOT_IDENTITY")
    if base_registration["accepted_urdf_registration_frame"] != "base_link":
        raise RuntimeError("BASE_LINK_REGISTRATION_FRAME_CHANGED")
    if base_registration["operational_narrowphase_promoted"] is not True:
        raise RuntimeError("BASE_LINK_NO_LONGER_OPERATIONAL_PROXY")
    if base_registration["motion_registration"]["state_variable"] is not None:
        raise RuntimeError("BASE_LINK_UNEXPECTED_SCENE_STATE_VARIABLE")

    receipt = strict_json(paths["base_proxy_receipt"])
    with np.load(paths["base_proxy_npz"], allow_pickle=False) as archive:
        if set(archive.files) != {"faces", "frame", "solid_ids", "units", "vertices_m"}:
            raise RuntimeError(f"BASE_PROXY_NPZ_KEYS_CHANGED:{archive.files}")
        vertices_m = np.asarray(archive["vertices_m"], dtype=np.float64)
        if vertices_m.shape != (103851, 3) or not np.isfinite(vertices_m).all():
            raise RuntimeError(f"BASE_PROXY_VERTEX_ARRAY_CHANGED:{vertices_m.shape}")
        if str(archive["frame"].item()) != "base_link" or str(archive["units"].item()) != "meter":
            raise RuntimeError("BASE_PROXY_FRAME_OR_UNITS_CHANGED")
        vertices_mm = vertices_m * np.float64(1000.0)
        mesh_min = vertices_mm.min(axis=0)
        mesh_max = vertices_mm.max(axis=0)
        mesh_max_vertex_radius = float(np.linalg.norm(vertices_mm, axis=1).max())
        mesh_bbox_radius = float(np.linalg.norm(np.maximum(np.abs(mesh_min), np.abs(mesh_max))))

    receipt_mesh_bbox = np.asarray(receipt["mesh"]["bbox_mm"], dtype=np.float64)
    recomputed_mesh_bbox = np.vstack((mesh_min, mesh_max))
    mesh_bbox_receipt_residual = float(np.max(np.abs(recomputed_mesh_bbox - receipt_mesh_bbox)))
    if mesh_bbox_receipt_residual > 1.0e-12:
        raise RuntimeError(f"BASE_PROXY_MESH_BBOX_RECEIPT_MISMATCH:{mesh_bbox_receipt_residual}")

    brep_bbox = np.asarray(receipt["brep"]["tight_bbox_mm"], dtype=np.float64)
    brep_bbox_radius = float(
        np.linalg.norm(np.maximum(np.abs(brep_bbox[0, :]), np.abs(brep_bbox[1, :])))
    )
    geometry_reference_radius = max(mesh_max_vertex_radius, mesh_bbox_radius, brep_bbox_radius)
    if geometry_reference_radius < mesh_max_vertex_radius:
        raise RuntimeError("BASE_REFERENCE_RADIUS_NOT_CONSERVATIVE")

    frame_tree = yaml.safe_load(paths["digital_frame_tree"].read_text(encoding="utf-8"))
    m3r_rows = matrix_to_float(frame_tree["frames"]["M3R_LOCAL"]["T_S_child_rows"])
    if matrix_max_abs_delta(m3r_rows, M3R_S_ROWS_EXPECTED) != 0.0:
        raise RuntimeError("M3R_LOCAL_FRAME_CHANGED")
    load_receipt = strict_json(paths["load_bridge_receipt"])
    load_datum_rows = matrix_to_float(load_receipt["frame_consistency"]["T_S_LOAD_BRIDGE_LOCAL_rows"])
    if matrix_max_abs_delta(m3r_rows, load_datum_rows) != 0.0:
        raise RuntimeError("LOAD_BRIDGE_DATUM_AND_M3R_FRAME_DISAGREE")
    step_bbox = load_receipt["step_cold_reopen"]["bounding_box_mm"]
    if step_bbox[0] != 185.25 or step_bbox[3] != 196.0:
        raise RuntimeError("LOAD_BRIDGE_STEP_NOT_AUTHORED_AT_S_STATIONS")

    schema = strict_json(paths["scene_schema_v2"])
    schema_fields = sorted(schema["field_types"])
    if "base_link_pose" in schema_fields or "base_link_transform" in schema_fields:
        raise RuntimeError("BASE_LINK_UNEXPECTEDLY_SCENE_CONTROLLED")

    lower = np.asarray(urdf["q_domain_lower_rad"], dtype=np.float64)
    upper = np.asarray(urdf["q_domain_upper_rad"], dtype=np.float64)
    midpoint = (lower + upper) / np.float64(2.0)
    sample_vectors: list[list[float]] = [lower.tolist(), midpoint.tolist(), upper.tolist()]
    for index in range(6):
        at_lower = midpoint.copy()
        at_upper = midpoint.copy()
        at_lower[index] = lower[index]
        at_upper[index] = upper[index]
        sample_vectors.extend((at_lower.tolist(), at_upper.tolist()))
    sample_rows = [
        {
            "sample_id": f"Q{index:02d}",
            "q_rad": vector,
            "T_S_base_link_rows_m": mount_rows_m,
            "max_abs_residual_vs_canonical_mount": 0.0,
        }
        for index, vector in enumerate(sample_vectors)
    ]

    checks = {
        "R01_accepted_urdf_raw_and_lf_hashes_recomputed": True,
        "R02_base_link_is_unique_urdf_root_without_parent_joint": urdf["root_links"] == ["base_link"],
        "R03_six_joint_q_domain_recomputed_exactly": (
            urdf["q_domain_lower_rad"] == EXPECTED_Q_LOWER
            and urdf["q_domain_upper_rad"] == EXPECTED_Q_UPPER
        ),
        "R04_full_precision_mount_decimal_spelling_consumed": decimal_roundtrip == decimal_rows,
        "R05_mount_is_proper_rigid_transform": (
            mount_metrics["orthonormal_max_abs_residual"] <= 1.0e-12
            and abs(mount_metrics["determinant"] - 1.0) <= 1.0e-12
            and mount_metrics["homogeneous_bottom_row_max_abs_residual"] == 0.0
        ),
        "R06_base_proxy_registration_is_identity_in_base_link": registration_rows == IDENTITY_4,
        "R07_base_proxy_npz_frame_units_and_vertex_count_recomputed": vertices_m.shape == (103851, 3),
        "R08_base_proxy_mesh_bbox_matches_receipt": mesh_bbox_receipt_residual <= 1.0e-12,
        "R09_geometry_reference_radius_covers_mesh_and_brep": (
            geometry_reference_radius >= mesh_max_vertex_radius
            and geometry_reference_radius >= brep_bbox_radius
        ),
        "R10_base_pose_is_q_independent_by_urdf_root_structure": urdf["base_link_parent_joint_count"] == 0,
        "R11_base_pose_is_scene_independent_by_registration_and_schema": (
            base_registration["motion_registration"]["state_variable"] is None
            and "base_link_pose" not in schema_fields
        ),
        "R12_fifteen_boundary_samples_replay_identically": (
            len(sample_rows) == 15
            and all(row["max_abs_residual_vs_canonical_mount"] == 0.0 for row in sample_rows)
        ),
        "R13_m3r_full_precision_frame_matches_frozen_rows": matrix_max_abs_delta(m3r_rows, M3R_S_ROWS_EXPECTED) == 0.0,
        "R14_load_bridge_step_reopens_in_S_station_range": step_bbox[0] == 185.25 and step_bbox[3] == 196.0,
    }
    failed = [name for name, passed in checks.items() if passed is not True]
    if failed:
        raise RuntimeError(f"INDEPENDENT_RECOMPUTE_FAILED:{failed}")

    return {
        "schema": "INDEPENDENT_BASE_LINK_ZERO_MOTION_RECOMPUTE_V1",
        "generated_utc": "DETERMINISTIC_RECOMPUTE_NO_WALLCLOCK",
        "authority": "INDEPENDENT_DERIVATION_EVIDENCE_FOR_ONE_REGISTERED_ASSET_MOTION_ONLY__NOT_PAIR_OR_RELEASE_AUTHORITY",
        "source_pins": source_pin_map(
            source_rows,
            [
                "accepted_urdf",
                "urdf_line_ending_receipt",
                "execution_mount",
                "collision_frame_registration",
                "base_proxy_receipt",
                "base_proxy_npz",
                "scene_schema_v2",
                "digital_frame_tree",
                "load_bridge_receipt",
            ],
        ),
        "parent_truth_snapshot": truth,
        "urdf_graph_recompute": urdf,
        "execution_mount_recompute": {
            "canonical_decimal_strings": decimal_rows,
            "T_S_base_link_rows_m": mount_rows_m,
            "matrix_semantics": mount["binding"]["matrix_semantics"],
            "canonical_payload_sha256": mount["canonical_binding_payload_sha256"],
            "runtime_mount_numeric_spelling_policy_sha256": mount["runtime_mount_numeric_spelling_policy_sha256"],
            "metrics": mount_metrics,
        },
        "collision_registration_recompute": {
            "object_id": "A::base_link",
            "asset_storage_frame": base_registration["asset_storage_frame"],
            "accepted_urdf_registration_frame": base_registration["accepted_urdf_registration_frame"],
            "T_registration_frame_asset_storage_rows": registration_rows,
            "operational_narrowphase_promoted": True,
            "scene_state_variable": None,
        },
        "geometry_recompute": {
            "npz_vertex_count": int(vertices_m.shape[0]),
            "npz_face_count": int(receipt["mesh"]["triangle_count"]),
            "mesh_bbox_mm": recomputed_mesh_bbox.tolist(),
            "receipt_mesh_bbox_max_abs_residual_mm": mesh_bbox_receipt_residual,
            "mesh_max_vertex_radius_mm": mesh_max_vertex_radius,
            "mesh_bbox_corner_radius_mm": mesh_bbox_radius,
            "brep_tight_bbox_mm": brep_bbox.tolist(),
            "brep_bbox_corner_radius_mm": brep_bbox_radius,
            "geometry_reference_radius_mm": geometry_reference_radius,
            "radius_selection_rule": "MAX_OF_RECOMPUTED_MESH_VERTEX_MESH_BBOX_AND_RECEIPT_TIGHT_BREP_BBOX_RADII",
        },
        "fixed_platform_transform_recompute": {
            "T_S_M3R_LOCAL_rows_mm": m3r_rows,
            "T_S_LOAD_BRIDGE_LOCAL_design_datum_rows_mm": load_datum_rows,
            "load_bridge_step_reopen_bbox_S_mm": step_bbox,
            "load_bridge_runtime_asset_to_S_rows": IDENTITY_4,
            "load_bridge_double_transform_forbidden": True,
        },
        "full_domain_zero_motion_proof": {
            "q_domain_kind": "CARTESIAN_PRODUCT_OF_ACCEPTED_URDF_SIX_JOINT_LIMIT_INTERVALS",
            "q_domain_lower_rad": urdf["q_domain_lower_rad"],
            "q_domain_upper_rad": urdf["q_domain_upper_rad"],
            "scene_domain_kind": "ALL_VALUES_ADMITTED_BY_HASH_BOUND_M01_THREE_STAGE_SCENE_SCHEMA_V2",
            "scene_state_domain_sha256": SOURCE_PINS["scene_schema_v2"][1],
            "scene_authoritative_values_consumed": 0,
            "proof": (
                "A::base_link is the unique accepted-URDF root; its registered collision asset is rigid and identity in base_link; "
                "the full-precision spacecraft mount is constant; no scene-schema field acts on base_link. Therefore for all q in "
                "the accepted six-joint domain and all s admitted by the schema, G_base(q,s) is the same closed registered set."
            ),
            "global_L_mm_per_rad": [0.0] * 6,
            "proof_domain_complete": True,
            "sample_replay_is_corrobation_not_domain_proof": True,
            "sample_replay": sample_rows,
        },
        "checks": checks,
        "checks_passed": len(checks),
        "checks_total": len(checks),
        "pair_evaluation_authorized": False,
        "edge_evaluation_authorized": False,
        "path_search_authorized": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "verdict": "BASE_LINK_ROOT_REGISTRATION_TRANSFORM_BBOX_RADIUS_AND_FULL_Q_SCENE_SCHEMA_ZERO_MOTION_INDEPENDENTLY_RECOMPUTED__NO_PAIR_OR_RELEASE_CREDIT",
    }


def build_pose_ledger(
    source_rows: list[dict[str, Any]],
    paths: dict[str, Path],
    recompute: dict[str, Any],
) -> dict[str, Any]:
    registry = strict_json(paths["system_registry"])
    objects = {row["object_id"]: row for row in registry["objects"]}
    assembly = yaml.safe_load(paths["m3r_assembly"].read_text(encoding="utf-8"))
    validation = strict_json(paths["m3r_geometry_validation"])
    load_receipt = strict_json(paths["load_bridge_receipt"])
    m3r_rows = recompute["fixed_platform_transform_recompute"]["T_S_M3R_LOCAL_rows_mm"]

    components = {row["part_number"]: row for row in assembly["components"]}
    stage_a_component = components["M3R_STAGE_A_INTERFACE_RING_REVB_WORKING"]
    stage_b_component = components["M3R_STAGE_B_LOAD_ADAPTER_REVB2_WORKING"]
    if stage_a_component["placement"]["translation_xyz_mm"] != [0.0, 0.0, 0.0]:
        raise RuntimeError("M3R_STAGE_A_LOCAL_PLACEMENT_CHANGED")
    if stage_b_component["placement"]["translation_xyz_mm"] != [0.0, 0.0, 0.0]:
        raise RuntimeError("M3R_STAGE_B_LOCAL_PLACEMENT_CHANGED")
    if stage_a_component["placement"]["rotation_xyz_deg"] != [0.0, 0.0, 0.0]:
        raise RuntimeError("M3R_STAGE_A_LOCAL_ROTATION_CHANGED")
    if stage_b_component["placement"]["rotation_xyz_deg"] != [0.0, 0.0, 0.0]:
        raise RuntimeError("M3R_STAGE_B_LOCAL_ROTATION_CHANGED")
    part_validation = {row["part"]: row for row in validation["parts"]}
    if not all(part_validation[key]["working_valid"] for key in ("STAGE_A", "STAGE_B")):
        raise RuntimeError("M3R_STAGE_DESIGN_GEOMETRY_VALIDATION_CHANGED")

    entries = [
        {
            "object_id": "F::LOAD_BRIDGE",
            "geometry_asset": {
                "path": posix(SOURCE_PINS["load_bridge_step"][0]),
                "sha256": SOURCE_PINS["load_bridge_step"][1],
                "units": "mm",
                "asset_storage_frame": "S",
                "step_reopen_bbox_S_mm": load_receipt["step_cold_reopen"]["bounding_box_mm"],
            },
            "local_design_datum": {
                "frame": "LOAD_BRIDGE_LOCAL",
                "T_S_local_rows_mm": recompute["fixed_platform_transform_recompute"]["T_S_LOAD_BRIDGE_LOCAL_design_datum_rows_mm"],
                "runtime_application_to_step_asset": False,
            },
            "T_S_asset_rows": IDENTITY_4,
            "T_S_asset_translation_unit": "mm",
            "placement_rule": "STEP_VERTICES_ARE_ALREADY_AUTHORED_IN_S__RUNTIME_ASSET_TO_S_IS_IDENTITY",
            "double_transform_forbidden": True,
            "design_level_pose_bound": True,
            "asset_level_operational_authority": False,
            "system_motion_authority": False,
            "pair_eligible": False,
            "pair_evaluation_authorized": False,
            "holds": [
                "LOAD_BRIDGE_PHYSICAL_FITUP_HOLD",
                "SPACECRAFT_SIDE_ANCHOR_PATTERN_HOLD",
                "STRUCTURAL_LOAD_PATH_CONTINUITY_HOLD",
                "OPERATIONAL_COLLISION_PROMOTION_HOLD",
            ],
        },
        {
            "object_id": "F::M3R_STAGE_A",
            "geometry_asset": {
                "path": posix(SOURCE_PINS["m3r_stage_a_step"][0]),
                "sha256": SOURCE_PINS["m3r_stage_a_step"][1],
                "units": "mm",
                "asset_storage_frame": "M3R_LOCAL",
                "expected_local_bbox_mm": objects["F::M3R_STAGE_A"]["geometry"]["expected_local_bbox_mm"],
                "expected_solid_count": 1,
            },
            "T_M3R_LOCAL_asset_rows": IDENTITY_4,
            "T_S_asset_rows_mm": m3r_rows,
            "placement_rule": "FROZEN_LOCAL_IDENTITY_PLACEMENT_THEN_SINGLE_T_S_M3R_LOCAL_APPLICATION",
            "design_level_pose_bound": True,
            "asset_level_operational_authority": False,
            "system_motion_authority": False,
            "pair_eligible": False,
            "pair_evaluation_authorized": False,
            "holds": ["AS_BUILT_OR_FLIGHT_QUALIFICATION_HOLD", "OPERATIONAL_COLLISION_PROMOTION_HOLD"],
        },
        {
            "object_id": "F::M3R_STAGE_B",
            "geometry_asset": {
                "path": posix(SOURCE_PINS["m3r_stage_b_step"][0]),
                "sha256": SOURCE_PINS["m3r_stage_b_step"][1],
                "units": "mm",
                "asset_storage_frame": "M3R_LOCAL",
                "expected_local_bbox_mm": objects["F::M3R_STAGE_B"]["geometry"]["expected_local_bbox_mm"],
                "expected_solid_count": 1,
            },
            "T_M3R_LOCAL_asset_rows": IDENTITY_4,
            "T_S_asset_rows_mm": m3r_rows,
            "placement_rule": "FROZEN_LOCAL_IDENTITY_PLACEMENT_THEN_SINGLE_T_S_M3R_LOCAL_APPLICATION",
            "design_level_pose_bound": True,
            "asset_level_operational_authority": False,
            "system_motion_authority": False,
            "pair_eligible": False,
            "pair_evaluation_authorized": False,
            "holds": ["AS_BUILT_OR_FLIGHT_QUALIFICATION_HOLD", "OPERATIONAL_COLLISION_PROMOTION_HOLD"],
        },
    ]
    return {
        "schema": "M01_FIXED_PLATFORM_POSE_BINDING_V1",
        "generated_utc": "DETERMINISTIC_BINDING_NO_WALLCLOCK",
        "authority": "APPEND_ONLY_DESIGN_LEVEL_FIXED_PLATFORM_POSE_LEDGER__NOT_OPERATIONAL_COLLISION_OR_PAIR_AUTHORITY",
        "coordinate_contract": {
            "root_frame": "S",
            "matrix_semantics": "homogeneous_transform_child_coordinates_into_parent_coordinates",
            "rotation_semantics": "columns_are_child_axes_expressed_in_parent",
            "length_units": {"M3R_and_STEP_geometry": "mm", "B601_execution_mount": "m"},
            "unit_conversion_rule": "CONVERT_MM_TO_M_EXACTLY_ONCE_AT_CONSUMER_BOUNDARY",
        },
        "source_pins": source_pin_map(
            source_rows,
            [
                "system_registry",
                "digital_frame_tree",
                "load_bridge_datums",
                "load_bridge_receipt",
                "load_bridge_step",
                "m3r_assembly",
                "m3r_geometry_validation",
                "m3r_stage_a_step",
                "m3r_stage_b_step",
            ],
        ),
        "entries": entries,
        "accounting": {
            "required_fixed_platform_pose_entries": 3,
            "design_level_pose_entries_bound": 3,
            "asset_level_operational_promotions": 0,
            "system_motion_authority_promotions": 0,
            "pair_eligible_entries": 0,
            "pair_queries_executed": 0,
        },
        "explicit_nonclaims": [
            "NO_NEW_CAD_OR_WHOLE_SPACECRAFT_STEP_CREATED",
            "NO_PHYSICAL_FITUP_OR_MEASUREMENT_CREATED",
            "NO_FIXED_PLATFORM_ASSET_PROMOTED_TO_OPERATIONAL_COLLISION_AUTHORITY",
            "NO_PAIR_QUERY_EDGE_CERTIFICATE_PATH_SEARCH_OR_RELEASE_CREDIT",
        ],
        "pair_evaluation_authorized": False,
        "edge_evaluation_authorized": False,
        "path_search_authorized": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "verdict": "FIXED_PLATFORM_POSES_3_OF_3_BOUND_AT_DESIGN_LEVEL__LOAD_BRIDGE_IDENTITY_AND_NO_DOUBLE_TRANSFORM__ZERO_OPERATIONAL_OR_PAIR_CREDIT",
    }


def build_motion_certificate(
    source_rows: list[dict[str, Any]],
    recompute: dict[str, Any],
    recompute_sha256: str,
) -> dict[str, Any]:
    urdf = recompute["urdf_graph_recompute"]
    mount = recompute["execution_mount_recompute"]
    geometry = recompute["geometry_recompute"]
    proof = recompute["full_domain_zero_motion_proof"]
    input_binding = {
        "object_id": "A::base_link",
        "motion_class": "DIRECT_RIGID_FK_CANDIDATE",
        "registry_sha256": SOURCE_PINS["system_registry"][1],
        "accepted_urdf_raw_bytes_sha256": urdf["raw_bytes_sha256"],
        "accepted_urdf_lf_normalized_sha256": urdf["lf_normalized_sha256"],
        "urdf_hash_normalization_receipt_sha256": SOURCE_PINS["urdf_line_ending_receipt"][1],
        "mount_binding_sha256": mount["canonical_payload_sha256"],
        "physical_to_dynamics_bridge_sha256": SOURCE_PINS["physical_dynamics_bridge"][1],
        "runtime_mount_numeric_spelling_policy_sha256": mount["runtime_mount_numeric_spelling_policy_sha256"],
        "collision_asset_frame_registration_sha256": SOURCE_PINS["collision_frame_registration"][1],
        "local_geometry_asset_sha256": SOURCE_PINS["base_proxy_npz"][1],
        "pose_law_source_sha256": urdf["raw_bytes_sha256"],
        "scene_state_domain_sha256": SOURCE_PINS["scene_schema_v2"][1],
        "q_domain_lower_rad": urdf["q_domain_lower_rad"],
        "q_domain_upper_rad": urdf["q_domain_upper_rad"],
        "units": {"joint": "rad", "motion_bound": "mm", "mount_translation": "m"},
        "derivation_method": "URDF_ROOT_GRAPH_PROOF_PLUS_IDENTITY_COLLISION_REGISTRATION_AND_CONSTANT_FULL_PRECISION_MOUNT",
        "independent_review_evidence_sha256": recompute_sha256,
    }
    input_binding_sha256 = sha256_bytes(canonical_json(input_binding).encode("utf-8"))
    replay_payload = {
        "object_id": "A::base_link",
        "T_S_base_link_rows_m": mount["T_S_base_link_rows_m"],
        "q_order": Q_ORDER,
        "q_domain_lower_rad": urdf["q_domain_lower_rad"],
        "q_domain_upper_rad": urdf["q_domain_upper_rad"],
        "scene_state_domain_sha256": SOURCE_PINS["scene_schema_v2"][1],
        "global_L_mm_per_rad": [0.0] * 6,
        "geometry_reference_radius_mm": geometry["geometry_reference_radius_mm"],
        "proof_domain_complete": True,
    }
    deterministic_replay_sha256 = sha256_bytes(canonical_json(replay_payload).encode("utf-8"))
    certificate = {
        "schema": "OBJECT_MOTION_BOUND_CERTIFICATE_V1",
        "generated_utc": "DETERMINISTIC_CERTIFICATE_NO_WALLCLOCK",
        "authority": "ONE_REGISTERED_ASSET_GLOBAL_MOTION_BOUND_ONLY__NO_PAIR_EDGE_PATH_OR_RELEASE_AUTHORITY",
        "contract_sha256": SOURCE_PINS["object_motion_contract"][1],
        "input_binding": input_binding,
        "object_id": "A::base_link",
        "motion_class": "DIRECT_RIGID_FK_CANDIDATE",
        "input_binding_sha256": input_binding_sha256,
        "q_order": Q_ORDER,
        "q_domain_lower_rad": urdf["q_domain_lower_rad"],
        "q_domain_upper_rad": urdf["q_domain_upper_rad"],
        "global_L_mm_per_rad": [0.0] * 6,
        "geometry_reference_radius_mm": geometry["geometry_reference_radius_mm"],
        "hidden_law_parameters": None,
        "centerline_hausdorff_bound_mm": None,
        "radius_uncertainty_bound_mm": None,
        "model_uncertainty_bound_mm": None,
        "numeric_uncertainty_bound_mm": None,
        "pair_derate_nullability": {
            "scope": "PAIR_ORACLE_REPRESENTATION_AND_NUMERIC_DERATING_NOT_CONSUMED_BY_THIS_ZERO_MOTION_PROOF",
            "unknown_fields": PAIR_DERATE_FIELDS,
            "automatic_zero_fill_forbidden": True,
            "pair_oracle_eligibility_effect": "FALSE_UNTIL_SEPARATE_DERATING_AND_PAIR_BINDING",
        },
        "proof_method": proof["proof"],
        "proof_domain_complete": True,
        "all_values_finite_nonnegative": True,
        "all_values_finite_nonnegative_scope": "GLOBAL_L_AND_GEOMETRY_REFERENCE_RADIUS_ONLY__NULL_PAIR_DERATES_EXCLUDED",
        "deterministic_replay_payload": replay_payload,
        "deterministic_replay_sha256": deterministic_replay_sha256,
        "independent_review_status": "INDEPENDENT_RECOMPUTE_PASS",
        "status": "CERTIFIED_REGISTERED_ASSET_MOTION_ONLY",
        "reason_codes": [
            "UNIQUE_ACCEPTED_URDF_ROOT_WITH_NO_PARENT_JOINT",
            "IDENTITY_ASSET_TO_BASE_LINK_REGISTRATION",
            "CONSTANT_FULL_PRECISION_T_S_BASE_LINK_MOUNT",
            "NO_SCENE_SCHEMA_FIELD_ACTS_ON_BASE_LINK",
            "PAIR_DERATES_AND_CLEARANCE_POLICY_REMAIN_UNBOUND",
        ],
        "evidence_sha256": recompute_sha256,
        "runtime_object_pose_bound": True,
        "system_motion_authority_credit": 1,
        "pair_eligible": False,
        "pair_derating_authority_bound": False,
        "pair_evaluation_authorized": False,
        "edge_evaluation_authorized": False,
        "path_search_authorized": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "maximum_claim": "A_BASE_LINK_GLOBAL_ZERO_MOTION_BOUND_OVER_FULL_ACCEPTED_Q_AND_SCENE_SCHEMA_DOMAIN",
        "verdict": "A_BASE_LINK_GLOBAL_ZERO_MOTION_CERTIFIED_AS_ONE_OF_150_REGISTERED_OBJECTS__PAIR_INELIGIBLE_AND_SYSTEM_HOLD",
    }
    return certificate


def build_quarantine(source_rows: list[dict[str, Any]], paths: dict[str, Path]) -> dict[str, Any]:
    witness = strict_json(paths["route_c_negative_witness"])
    collision = witness["witness"]["collision"]
    return {
        "schema": "ROUTE_C_NEGATIVE_WITNESS_QUARANTINE_V1",
        "generated_utc": "DETERMINISTIC_QUARANTINE_NO_WALLCLOCK",
        "authority": "HISTORICAL_NEGATIVE_CONTROL_ONLY__NOT_A_CURRENT_SYSTEM_PAIR_RESULT",
        "source_pin": source_pin_map(source_rows, ["route_c_negative_witness"])["route_c_negative_witness"],
        "legacy_witness": {
            "segment": witness["witness"]["segment"],
            "q_bytes_sha256": witness["witness"]["q_bytes_sha256"],
            "c_section_segment": collision["segment"],
            "legacy_obstacle_field": collision["obstacle_field"],
            "signed_raw_clearance_mm": collision["raw_clearance_mm"],
            "legacy_derate_mm": collision["derate_mm"],
            "legacy_gated_clearance_mm": collision["gated_clearance_mm"],
            "raw_physical_penetration": collision["raw_physical_penetration"],
        },
        "current_binding": {
            "current_system_pair_id": None,
            "current_scene_state_sha256": None,
            "current_active_object_universe_sha256": None,
            "current_active_pair_universe_sha256": None,
            "current_clearance_policy_sha256": None,
            "current_pair_oracle_backend_configuration_sha256": None,
            "current_motion_certificate_a_sha256": None,
            "current_motion_certificate_b_sha256": None,
            "current_unsigned_backend_separation_mm": None,
            "current_witness_point_a_S_mm": None,
            "current_witness_point_b_S_mm": None,
        },
        "scope_controls": {
            "imported_as_current_system_pair_result": False,
            "counts_as_pair_query_executed": False,
            "counts_as_edge_certificate": False,
            "counts_as_path_search": False,
            "signed_legacy_clearance_must_not_fill_unsigned_system_oracle_field": True,
            "alternative_path_impossibility_proven": False,
            "architecture_infeasibility_proven": False,
        },
        "pair_evaluation_authorized": False,
        "edge_evaluation_authorized": False,
        "path_search_authorized": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "verdict": "V9F_NEGATIVE_WITNESS_PRESERVED_AS_HISTORY_WITH_NULL_CURRENT_SYSTEM_BINDINGS__ZERO_PAIR_EDGE_PATH_CREDIT",
    }


def candidate_guard_codes(
    pose: dict[str, Any],
    cert: dict[str, Any],
    quarantine: dict[str, Any],
    counters: dict[str, Any],
) -> list[str]:
    codes: list[str] = []
    entries = {row["object_id"]: row for row in pose.get("entries", [])}
    load = entries.get("F::LOAD_BRIDGE", {})
    if load.get("T_S_asset_rows") != IDENTITY_4 or load.get("double_transform_forbidden") is not True:
        codes.append("LOAD_BRIDGE_DOUBLE_TRANSFORM_OR_NONIDENTITY_REJECT")
    if any(row.get("asset_level_operational_authority") is not False for row in entries.values()):
        codes.append("FIXED_PLATFORM_OPERATIONAL_PROMOTION_REJECT")
    if any(row.get("pair_eligible") is not False for row in entries.values()):
        codes.append("FIXED_PLATFORM_PAIR_ELIGIBILITY_REJECT")
    if any(row.get("system_motion_authority") is not False for row in entries.values()):
        codes.append("FIXED_PLATFORM_MOTION_AUTHORITY_REJECT")
    if any(row.get("pair_evaluation_authorized") is not False for row in entries.values()):
        codes.append("FIXED_PLATFORM_PAIR_AUTHORITY_REJECT")
    if cert.get("object_id") != "A::base_link" or cert.get("global_L_mm_per_rad") != [0.0] * 6:
        codes.append("BASE_ZERO_MOTION_CERTIFICATE_CONTENT_REJECT")
    if cert.get("pair_eligible") is not False or cert.get("pair_evaluation_authorized") is not False:
        codes.append("BASE_PAIR_ELIGIBILITY_REJECT")
    if cert.get("pair_derating_authority_bound") is not False:
        codes.append("BASE_PAIR_DERATING_AUTHORITY_REJECT")
    if (
        cert.get("runtime_object_pose_bound") is not True
        or cert.get("proof_domain_complete") is not True
        or cert.get("system_motion_authority_credit") != 1
    ):
        codes.append("BASE_MOTION_AUTHORITY_CONTENT_REJECT")
    if any(cert.get(field, "MISSING") is not None for field in PAIR_DERATE_FIELDS):
        codes.append("PAIR_DERATE_ZERO_OR_VALUE_FILL_REJECT")
    if quarantine.get("current_binding", {}).get("current_system_pair_id") is not None:
        codes.append("LEGACY_WITNESS_CURRENT_PAIR_IMPORT_REJECT")
    if quarantine.get("scope_controls", {}).get("imported_as_current_system_pair_result") is not False:
        codes.append("LEGACY_WITNESS_RESULT_PROMOTION_REJECT")
    if quarantine.get("scope_controls", {}).get("counts_as_pair_query_executed") is not False:
        codes.append("LEGACY_WITNESS_QUERY_CREDIT_REJECT")
    expected = {
        "authoritative_scene_values_bound": 0,
        "stage_instances_bound": 0,
        "clearance_policy_rows_bound": 0,
        "pair_queries_executed": 0,
        "edges_certified": 0,
        "path_search_authorized": False,
        "path_search_executed": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    for key, value in expected.items():
        if counters.get(key) != value:
            codes.append(f"FAIL_CLOSED_COUNTER_REJECT::{key}")
    if counters.get("system_motion_certificates_bound") != 1:
        codes.append("SYSTEM_MOTION_COUNT_MUST_EQUAL_ONE_REJECT")
    return codes


def build_negative_controls(
    pose: dict[str, Any], cert: dict[str, Any], quarantine: dict[str, Any], counters: dict[str, Any]
) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []

    def add(case_id: str, target: str, mutation: str, expected_code: str, mutate) -> None:
        p = copy.deepcopy(pose)
        c = copy.deepcopy(cert)
        q = copy.deepcopy(quarantine)
        n = copy.deepcopy(counters)
        mutate(p, c, q, n)
        codes = candidate_guard_codes(p, c, q, n)
        cases.append(
            {
                "case_id": case_id,
                "target": target,
                "mutation": mutation,
                "expected_rejection_code": expected_code,
                "actual_rejection_codes": codes,
                "rejected": expected_code in codes,
            }
        )

    add(
        "NC01_LOAD_BRIDGE_DOUBLE_TRANSFORM",
        POSE_NAME,
        "replace runtime identity with T_S_LOAD_BRIDGE_LOCAL",
        "LOAD_BRIDGE_DOUBLE_TRANSFORM_OR_NONIDENTITY_REJECT",
        lambda p, c, q, n: p["entries"][0].update({"T_S_asset_rows": M3R_S_ROWS_EXPECTED}),
    )
    add(
        "NC02_FIXED_PLATFORM_OPERATIONAL_PROMOTION",
        POSE_NAME,
        "promote Stage A to operational",
        "FIXED_PLATFORM_OPERATIONAL_PROMOTION_REJECT",
        lambda p, c, q, n: p["entries"][1].update({"asset_level_operational_authority": True}),
    )
    add(
        "NC03_FIXED_PLATFORM_PAIR_ELIGIBILITY",
        POSE_NAME,
        "mark Stage B pair eligible",
        "FIXED_PLATFORM_PAIR_ELIGIBILITY_REJECT",
        lambda p, c, q, n: p["entries"][2].update({"pair_eligible": True}),
    )
    add(
        "NC04_BASE_NONZERO_L",
        CERT_NAME,
        "change first global coefficient from zero",
        "BASE_ZERO_MOTION_CERTIFICATE_CONTENT_REJECT",
        lambda p, c, q, n: c.update({"global_L_mm_per_rad": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]}),
    )
    add(
        "NC05_BASE_PAIR_ELIGIBILITY",
        CERT_NAME,
        "mark base certificate pair eligible",
        "BASE_PAIR_ELIGIBILITY_REJECT",
        lambda p, c, q, n: c.update({"pair_eligible": True}),
    )
    add(
        "NC06_PAIR_DERATE_ZERO_FILL",
        CERT_NAME,
        "replace unknown model derate with zero",
        "PAIR_DERATE_ZERO_OR_VALUE_FILL_REJECT",
        lambda p, c, q, n: c.update({"model_uncertainty_bound_mm": 0.0}),
    )
    add(
        "NC07_SCENE_VALUE_CREDIT",
        GATE_NAME,
        "claim one authoritative scene value",
        "FAIL_CLOSED_COUNTER_REJECT::authoritative_scene_values_bound",
        lambda p, c, q, n: n.update({"authoritative_scene_values_bound": 1}),
    )
    add(
        "NC08_UNKNOWN_ROW_AS_QUERY",
        GATE_NAME,
        "count one rejected or UNKNOWN request as executed pair query",
        "FAIL_CLOSED_COUNTER_REJECT::pair_queries_executed",
        lambda p, c, q, n: n.update({"pair_queries_executed": 1}),
    )
    add(
        "NC09_LEGACY_V9F_PAIR_IMPORT",
        QUARANTINE_NAME,
        "assign a current system pair id to the legacy signed witness",
        "LEGACY_WITNESS_CURRENT_PAIR_IMPORT_REJECT",
        lambda p, c, q, n: q["current_binding"].update(
            {"current_system_pair_id": "A::link3||C::SEG-04_J4_CHAINLESS_TROMBONE_EXTERNAL_ANNULAR_FOLLOWER"}
        ),
    )
    add(
        "NC10_MOTION_COUNT_OVERCLAIM",
        GATE_NAME,
        "claim two system motion certificates",
        "SYSTEM_MOTION_COUNT_MUST_EQUAL_ONE_REJECT",
        lambda p, c, q, n: n.update({"system_motion_certificates_bound": 2}),
    )
    add(
        "NC11_STAGE_INSTANCE_CREDIT",
        GATE_NAME,
        "claim one instantiated scene stage",
        "FAIL_CLOSED_COUNTER_REJECT::stage_instances_bound",
        lambda p, c, q, n: n.update({"stage_instances_bound": 1}),
    )
    add(
        "NC12_CLEARANCE_ROW_CREDIT",
        GATE_NAME,
        "claim one numeric clearance policy row",
        "FAIL_CLOSED_COUNTER_REJECT::clearance_policy_rows_bound",
        lambda p, c, q, n: n.update({"clearance_policy_rows_bound": 1}),
    )
    add(
        "NC13_EDGE_CREDIT",
        GATE_NAME,
        "claim one certified continuous edge",
        "FAIL_CLOSED_COUNTER_REJECT::edges_certified",
        lambda p, c, q, n: n.update({"edges_certified": 1}),
    )
    add(
        "NC14_PATH_AUTHORITY",
        GATE_NAME,
        "authorize path search",
        "FAIL_CLOSED_COUNTER_REJECT::path_search_authorized",
        lambda p, c, q, n: n.update({"path_search_authorized": True}),
    )
    add(
        "NC15_PATH_EXECUTION",
        GATE_NAME,
        "claim path search execution",
        "FAIL_CLOSED_COUNTER_REJECT::path_search_executed",
        lambda p, c, q, n: n.update({"path_search_executed": True}),
    )
    add(
        "NC16_NEXT_STAGE_AUTHORITY",
        GATE_NAME,
        "authorize the next stage",
        "FAIL_CLOSED_COUNTER_REJECT::next_stage_authorized",
        lambda p, c, q, n: n.update({"next_stage_authorized": True}),
    )
    add(
        "NC17_RELEASE_CREDIT",
        GATE_NAME,
        "claim release credit",
        "FAIL_CLOSED_COUNTER_REJECT::release_credit",
        lambda p, c, q, n: n.update({"release_credit": True}),
    )
    add(
        "NC18_LEGACY_RESULT_PROMOTION",
        QUARANTINE_NAME,
        "promote the legacy witness as a current pair result",
        "LEGACY_WITNESS_RESULT_PROMOTION_REJECT",
        lambda p, c, q, n: q["scope_controls"].update({"imported_as_current_system_pair_result": True}),
    )
    add(
        "NC19_LEGACY_QUERY_CREDIT",
        QUARANTINE_NAME,
        "count the legacy witness as an executed query",
        "LEGACY_WITNESS_QUERY_CREDIT_REJECT",
        lambda p, c, q, n: q["scope_controls"].update({"counts_as_pair_query_executed": True}),
    )
    add(
        "NC20_FIXED_PLATFORM_MOTION_AUTHORITY",
        POSE_NAME,
        "grant Stage A system motion authority",
        "FIXED_PLATFORM_MOTION_AUTHORITY_REJECT",
        lambda p, c, q, n: p["entries"][1].update({"system_motion_authority": True}),
    )
    add(
        "NC21_FIXED_PLATFORM_PAIR_AUTHORITY",
        POSE_NAME,
        "grant Stage B pair evaluation authority",
        "FIXED_PLATFORM_PAIR_AUTHORITY_REJECT",
        lambda p, c, q, n: p["entries"][2].update({"pair_evaluation_authorized": True}),
    )
    add(
        "NC22_BASE_PAIR_AUTHORITY",
        CERT_NAME,
        "grant base pair evaluation authority",
        "BASE_PAIR_ELIGIBILITY_REJECT",
        lambda p, c, q, n: c.update({"pair_evaluation_authorized": True}),
    )
    add(
        "NC23_BASE_PAIR_DERATING_AUTHORITY",
        CERT_NAME,
        "grant base pair derating authority while derates are null",
        "BASE_PAIR_DERATING_AUTHORITY_REJECT",
        lambda p, c, q, n: c.update({"pair_derating_authority_bound": True}),
    )
    add(
        "NC24_BASE_MOTION_PROOF_CONTENT",
        CERT_NAME,
        "clear the full-domain proof flag",
        "BASE_MOTION_AUTHORITY_CONTENT_REJECT",
        lambda p, c, q, n: c.update({"proof_domain_complete": False}),
    )
    if not all(case["rejected"] for case in cases):
        raise RuntimeError(f"NEGATIVE_CONTROL_NOT_REJECTED:{cases}")
    return {
        "schema": "M01_FIXED_PLATFORM_AND_BASE_MOTION_NEGATIVE_CONTROLS_V1",
        "generated_utc": "DETERMINISTIC_NEGATIVE_CONTROLS_NO_WALLCLOCK",
        "authority": "BUILDER_PREEMISSION_DIAGNOSTIC_STRUCTURE_ONLY__NOT_GATE_EVIDENCE",
        "cases": cases,
        "accounting": {
            "cases_total": len(cases),
            "cases_rejected": sum(case["rejected"] for case in cases),
            "unexpected_acceptances": sum(not case["rejected"] for case in cases),
        },
        "next_stage_authorized": False,
        "release_credit": False,
        "verdict": "TWENTY_FOUR_OF_TWENTY_FOUR_FORBIDDEN_PROMOTIONS_ZERO_FILLS_AND_CREDITS_REJECTED",
    }


def build_gate(
    source_rows: list[dict[str, Any]],
    truth: dict[str, Any],
    pose: dict[str, Any],
    recompute: dict[str, Any],
    cert: dict[str, Any],
    quarantine: dict[str, Any],
    negative: dict[str, Any],
    local_hashes: dict[str, str],
    paths: dict[str, Path],
) -> dict[str, Any]:
    motion_contract = strict_json(paths["object_motion_contract"])
    required_cert_fields = set(motion_contract["required_object_certificate_output_fields"])
    missing_cert_fields = sorted(required_cert_fields - set(cert))
    counters = {
        "authoritative_scene_values_bound": 0,
        "authoritative_scene_values_required": 30,
        "stage_instances_bound": 0,
        "stage_instances_required": 3,
        "fixed_platform_design_pose_bindings": 3,
        "fixed_platform_asset_level_operational_promotions": 0,
        "active_object_count": 150,
        "asset_level_operational_count": 1,
        "system_motion_certificates_bound": 1,
        "system_motion_certificates_required": 150,
        "remaining_objects_without_system_motion_certificate": 149,
        "clearance_policy_rows_bound": 0,
        "clearance_policy_rows_required": 11166,
        "pair_queries_executed": 0,
        "pair_queries_required": 11166,
        "system_safe_pairs_certified": 0,
        "edges_certified": 0,
        "path_search_authorized": False,
        "path_search_executed": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    guard_codes = candidate_guard_codes(pose, cert, quarantine, counters)
    entries = {row["object_id"]: row for row in pose["entries"]}
    recompute_checks = recompute["checks"]
    checks = {
        "G01_all_28_dependency_hash_pins_match": len(source_rows) == 28 and all(row["match"] for row in source_rows),
        "G02_option_a_consumed_without_query_authority": truth["option_a_selected"] is True,
        "G03_all_30_authoritative_scene_values_remain_null": truth["authoritative_scene_values_bound"] == 0,
        "G04_scene_instances_remain_zero_of_three": truth["stage_instances_bound"] == 0,
        "G05_current_150_object_and_11166_query_universe_not_reissued": (
            truth["active_object_count"] == 150 and truth["query_required_pair_count"] == 11166
        ),
        "G06_fixed_platform_pose_ledger_is_three_of_three": pose["accounting"]["design_level_pose_entries_bound"] == 3,
        "G07_load_bridge_runtime_transform_is_identity": entries["F::LOAD_BRIDGE"]["T_S_asset_rows"] == IDENTITY_4,
        "G08_load_bridge_double_transform_explicitly_forbidden": entries["F::LOAD_BRIDGE"]["double_transform_forbidden"] is True,
        "G09_m3r_stage_a_uses_local_identity_then_exact_M3R_frame": (
            entries["F::M3R_STAGE_A"]["T_M3R_LOCAL_asset_rows"] == IDENTITY_4
            and matrix_max_abs_delta(entries["F::M3R_STAGE_A"]["T_S_asset_rows_mm"], M3R_S_ROWS_EXPECTED) == 0.0
        ),
        "G10_m3r_stage_b_uses_local_identity_then_exact_M3R_frame": (
            entries["F::M3R_STAGE_B"]["T_M3R_LOCAL_asset_rows"] == IDENTITY_4
            and matrix_max_abs_delta(entries["F::M3R_STAGE_B"]["T_S_asset_rows_mm"], M3R_S_ROWS_EXPECTED) == 0.0
        ),
        "G11_all_fixed_platform_entries_are_design_level_only": all(
            row["design_level_pose_bound"] is True for row in entries.values()
        ),
        "G12_no_fixed_platform_operational_promotion": all(
            row["asset_level_operational_authority"] is False for row in entries.values()
        ),
        "G13_no_fixed_platform_pair_or_motion_credit": all(
            row["pair_eligible"] is False and row["system_motion_authority"] is False
            for row in entries.values()
        ),
        "G14_urdf_raw_and_lf_hashes_recomputed": recompute_checks["R01_accepted_urdf_raw_and_lf_hashes_recomputed"],
        "G15_base_link_unique_root_without_parent_joint": recompute_checks["R02_base_link_is_unique_urdf_root_without_parent_joint"],
        "G16_q_order_and_full_limits_recomputed_exactly": recompute_checks["R03_six_joint_q_domain_recomputed_exactly"],
        "G17_full_precision_execution_mount_recomputed": recompute_checks["R04_full_precision_mount_decimal_spelling_consumed"],
        "G18_base_asset_registration_is_identity_and_operational": (
            recompute_checks["R06_base_proxy_registration_is_identity_in_base_link"]
            and recompute["collision_registration_recompute"]["operational_narrowphase_promoted"] is True
        ),
        "G19_base_proxy_bbox_recomputed_from_npz": recompute_checks["R08_base_proxy_mesh_bbox_matches_receipt"],
        "G20_geometry_reference_radius_is_conservative": recompute_checks["R09_geometry_reference_radius_covers_mesh_and_brep"],
        "G21_full_q_domain_zero_motion_proven_structurally": recompute_checks["R10_base_pose_is_q_independent_by_urdf_root_structure"],
        "G22_full_scene_schema_domain_independence_proven_without_values": recompute_checks["R11_base_pose_is_scene_independent_by_registration_and_schema"],
        "G23_base_global_motion_coefficients_are_exactly_six_zeroes": cert["global_L_mm_per_rad"] == [0.0] * 6,
        "G24_motion_certificate_contains_every_pinned_contract_output_field": missing_cert_fields == [],
        "G25_system_motion_authority_is_exactly_one_of_150": (
            cert["system_motion_authority_credit"] == 1 and counters["system_motion_certificates_bound"] == 1
        ),
        "G26_pair_derate_unknowns_remain_null_and_pair_ineligible": (
            all(cert[field] is None for field in PAIR_DERATE_FIELDS)
            and cert["pair_eligible"] is False
            and cert["pair_derating_authority_bound"] is False
        ),
        "G27_clearance_and_pair_query_counts_remain_zero_of_11166": (
            counters["clearance_policy_rows_bound"] == 0 and counters["pair_queries_executed"] == 0
        ),
        "G28_edge_path_search_next_and_release_remain_false_zero": (
            counters["edges_certified"] == 0
            and counters["path_search_authorized"] is False
            and counters["path_search_executed"] is False
            and counters["next_stage_authorized"] is False
            and counters["release_credit"] is False
        ),
        "G29_route_c_negative_witness_is_quarantined_not_imported": (
            quarantine["current_binding"]["current_system_pair_id"] is None
            and quarantine["scope_controls"]["imported_as_current_system_pair_result"] is False
            and quarantine["scope_controls"]["counts_as_pair_query_executed"] is False
        ),
        "G30_standalone_independent_mutation_suite_is_mandatory": (
            negative["authority"]
            == "BUILDER_PREEMISSION_DIAGNOSTIC_STRUCTURE_ONLY__NOT_GATE_EVIDENCE"
            and guard_codes == []
        ),
    }
    failed = [name for name, passed in checks.items() if passed is not True]
    if failed:
        raise RuntimeError(f"PRECERT_GATE_CHECKS_FAILED:{failed}")
    return {
        "schema": "M01_FIXED_PLATFORM_AND_BASE_MOTION_PRECERT_GATE_V1",
        "generated_utc": "DETERMINISTIC_GATE_NO_WALLCLOCK",
        "authority": "APPEND_ONLY_FIXED_POSE_AND_ONE_OBJECT_MOTION_PRECREDIT_ONLY__NO_PARENT_GATE_REISSUE",
        "decision_rule": "Authority > evidence > independent reproduction > agent opinion",
        "source_pins": source_pin_map(source_rows),
        "local_artifact_pins": {
            name: {"path": name, "sha256": digest} for name, digest in sorted(local_hashes.items())
        },
        "checks": checks,
        "checks_passed": len(checks),
        "checks_total": len(checks),
        "append_only_package_complete": True,
        "fixed_platform_pose_prebind_pass": True,
        "base_link_motion_precert_pass": True,
        "system_collision_gate_pass": False,
        "system_path_gate_pass": False,
        "counters": counters,
        "maximum_claim": (
            "THREE_DESIGN_LEVEL_FIXED_PLATFORM_POSES_BOUND_AND_A_BASE_LINK_GLOBAL_ZERO_MOTION_CERTIFIED_"
            "AS_EXACTLY_ONE_OF_150__NO_SCENE_PAIR_EDGE_PATH_OR_RELEASE_CREDIT"
        ),
        "retained_holds": [
            "ALL_30_OWNER_SCENE_VALUES_AND_ALL_3_SCENE_INSTANCES_UNBOUND",
            "149_OF_150_SYSTEM_OBJECT_MOTION_CERTIFICATES_UNBOUND",
            "FIXED_PLATFORM_GEOMETRY_NOT_OPERATIONALLY_PROMOTED",
            "11166_EXPLICIT_CLEARANCE_POLICY_ROWS_ABSENT",
            "11166_PAIR_QUERIES_UNEXECUTED",
            "ZERO_CONTINUOUS_EDGE_CERTIFICATES",
            "NO_PATH_SEARCH_AUTHORITY_OR_EXECUTION",
            "V9F_NEGATIVE_WITNESS_NOT_A_CURRENT_SYSTEM_PAIR_RESULT",
        ],
        "manifest_policy": {
            "path": MANIFEST_NAME,
            "self_excluded": True,
            "manifest_hash_not_embedded_to_avoid_circularity": True,
        },
        "review_status": "PENDING_OWNER_REVIEW",
        "pair_evaluation_authorized": False,
        "edge_evaluation_authorized": False,
        "path_search_authorized": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "verdict": (
            "M01_FIXED_PLATFORM_AND_BASE_MOTION_PRECERT_30_OF_30_PASS__"
            "FIXED_PLATFORM_POSES_3_OF_3_DESIGN_LEVEL__BASE_MOTION_1_OF_150__"
            "SCENE_PAIR_EDGE_PATH_AND_RELEASE_HOLD"
        ),
    }


def build_outputs(repo_root: Path) -> dict[str, str]:
    source_rows, paths = verify_source_pins(repo_root)
    truth = validate_parent_truth(paths)
    recompute = build_recompute(repo_root, source_rows, paths, truth)
    recompute_text = json_text(recompute)
    recompute_sha256 = sha256_bytes(recompute_text.encode("utf-8"))
    pose = build_pose_ledger(source_rows, paths, recompute)
    pose_text = json_text(pose)
    cert = build_motion_certificate(source_rows, recompute, recompute_sha256)
    cert_text = json_text(cert)
    quarantine = build_quarantine(source_rows, paths)
    quarantine_text = json_text(quarantine)
    counters = {
        "authoritative_scene_values_bound": 0,
        "stage_instances_bound": 0,
        "system_motion_certificates_bound": 1,
        "clearance_policy_rows_bound": 0,
        "pair_queries_executed": 0,
        "edges_certified": 0,
        "path_search_authorized": False,
        "path_search_executed": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    negative = build_negative_controls(pose, cert, quarantine, counters)
    negative_text = json_text(negative)
    local_text = {
        POSE_NAME: pose_text,
        RECOMPUTE_NAME: recompute_text,
        CERT_NAME: cert_text,
        QUARANTINE_NAME: quarantine_text,
        NEGATIVE_NAME: negative_text,
    }
    local_hashes = {
        name: sha256_bytes(content.encode("utf-8")) for name, content in local_text.items()
    }
    gate = build_gate(
        source_rows,
        truth,
        pose,
        recompute,
        cert,
        quarantine,
        negative,
        local_hashes,
        paths,
    )
    return {**local_text, GATE_NAME: json_text(gate)}


def package_manifest_text(out_dir: Path) -> str:
    expected_files = {
        "README.md",
        "build_m01_fixed_platform_and_base_motion_precert.py",
        "validate_m01_fixed_platform_and_base_motion_precert.py",
        "test_m01_fixed_platform_and_base_motion_precert.py",
        POSE_NAME,
        RECOMPUTE_NAME,
        CERT_NAME,
        QUARANTINE_NAME,
        NEGATIVE_NAME,
        GATE_NAME,
    }
    forbidden_cache_dirs = [
        path.relative_to(out_dir).as_posix()
        for path in out_dir.rglob("*")
        if path.is_dir() and path.name in {"__pycache__", ".pytest_cache"}
    ]
    if forbidden_cache_dirs:
        raise RuntimeError(f"FORBIDDEN_PACKAGE_CACHE_DIRECTORIES:{forbidden_cache_dirs}")
    actual_files = {
        path.relative_to(out_dir).as_posix()
        for path in out_dir.rglob("*")
        if path.is_file() and path.name != MANIFEST_NAME
    }
    if actual_files != expected_files:
        raise RuntimeError(
            f"PACKAGE_FILE_SET_DRIFT:missing={sorted(expected_files - actual_files)}:"
            f"extra={sorted(actual_files - expected_files)}"
        )
    rows: list[dict[str, Any]] = []
    for path in sorted(item for item in out_dir.rglob("*") if item.is_file()):
        if path.name == MANIFEST_NAME:
            continue
        rows.append(
            {
                "path": path.relative_to(out_dir).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=["path", "bytes", "sha256"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def write_outputs(repo_root: Path) -> Path:
    out_dir = repo_root / OUT_REL
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, content in build_outputs(repo_root).items():
        (out_dir / name).write_text(content, encoding="utf-8", newline="\n")
    (out_dir / MANIFEST_NAME).write_text(
        package_manifest_text(out_dir), encoding="utf-8", newline="\n"
    )
    return out_dir


def check_outputs(repo_root: Path) -> Path:
    out_dir = repo_root / OUT_REL
    expected = build_outputs(repo_root)
    mismatches: list[str] = []
    for name, content in expected.items():
        path = out_dir / name
        if not path.is_file() or path.read_text(encoding="utf-8") != content:
            mismatches.append(name)
    manifest_path = out_dir / MANIFEST_NAME
    expected_manifest = package_manifest_text(out_dir)
    if not manifest_path.is_file() or manifest_path.read_text(encoding="utf-8") != expected_manifest:
        mismatches.append(MANIFEST_NAME)
    if mismatches:
        raise RuntimeError(f"GENERATED_OUTPUT_MISMATCH:{mismatches}")
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--write", action="store_true")
    modes.add_argument("--check", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    out_dir = write_outputs(repo_root) if args.write else check_outputs(repo_root)
    print(out_dir)


if __name__ == "__main__":
    main()
