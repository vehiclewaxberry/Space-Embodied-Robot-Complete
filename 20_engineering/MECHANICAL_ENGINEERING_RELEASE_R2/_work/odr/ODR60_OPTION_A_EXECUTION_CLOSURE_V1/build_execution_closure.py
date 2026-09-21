#!/usr/bin/env python3
"""Build the fail-closed ODR-60 Option-A execution-closure candidate.

This builder is deliberately static.  It hashes and parses authority artifacts, but it
does not load collision geometry, evaluate a pair, certify an edge, or start a path
planner.  Generated JSON is deterministic and duplicate-key free.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import yaml


OUT_REL = Path(
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
    "ODR60_OPTION_A_EXECUTION_CLOSURE_V1"
)

ATTACHMENT = Path(
    r"C:\Users\stude\.codex\attachments\0cd497c9-fcae-4714-997d-859171b88dc2\pasted-text.txt"
)

OPTION_A = "AUTHORIZE_OPTION_A_FIXED_ENDPOINT_M01_TRAJECTORY_SEARCH"
OPTION_B = "AUTHORIZE_OPTION_B_VENDOR_INTERNAL_ROUTING_OR_SLIP_RING_FEASIBILITY"
OPTION_HOLD = "KEEP_ROUTE_C_TMG4_AND_MECHANICAL_RELEASE_ON_HOLD"
LOW_MEMORY = "ACCEPT_SINGLE_RUN_LOW_MEMORY_RISK"
EXECUTION_PROMPT_HEADING = "# 十一、直接交给 Claude Code/Fable5 的执行提示词"


SOURCE_PINS = {
    "owner_attachment": (
        ATTACHMENT,
        "EB9138AF1C04E07F7470587871F26A364DCB754994A6C1131F077D0467E91AC3",
        "EXTERNAL_OWNER_DIRECTIVE",
    ),
    "odr60_decision_request": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR-60_DECISION_REQUEST.json"),
        "09686A33E1FD7984DB041A9E7D4609EF30785C93392B4CCA431701B68B52FA62",
        "OWNER_RESPONSE_CONTRACT",
    ),
    "option_a_scope": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR-60_OPTION_A_M01_TRAJECTORY_SCOPE_TEMPLATE.yaml"),
        "B10972A8FFB01CFA1A99DDEAA9A5A018038E87BE6E649749FDD31B490DF6C308",
        "AUTHORIZED_BRANCH_SCOPE_AFTER_SELECTION",
    ),
    "legacy_preflight_inputs": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_PREFLIGHT_V1/ODR60_OPTION_A_PREFLIGHT_INPUTS_V1.json"),
        "EF5E92A41AAEBF9EC6C3643B85B0ADC9B8E6567A0BEA5A692953FF148FF31EAE",
        "IMMUTABLE_LEGACY_INPUT",
    ),
    "legacy_preflight_gate": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_PREFLIGHT_V1/ODR60_OPTION_A_PREFLIGHT_GATE_V1.json"),
        "664E7E8FF98839858D4234730F6BB78496006DF3D33F54FF1425D804D7D8436A",
        "IMMUTABLE_LEGACY_DUPLICATE_KEY_EVIDENCE",
    ),
    "binding_intake_gate": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_BINDING_INTAKE_V1/BINDING_INTAKE_GATE_V1.json"),
        "509127D151BE7C60B74C54A12E629C0CC673126DEC5DF158177AED9E72009634",
        "BINDING_INTAKE",
    ),
    "provisional_mount_candidate": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_BINDING_INTAKE_V1/PROVISIONAL_MOUNT_REBIND_CANDIDATE_V1.json"),
        "664EA6181ECCCA81C05FAFF4D949E90ECF452CB9B8B1CAB89282CD26261DA59A",
        "MOUNT_LINEAGE_ONLY",
    ),
    "scene_intake": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_BINDING_INTAKE_V1/SYSTEM_SCENE_STATE_INTAKE_V1.json"),
        "725EA607DAE3C268945B457CAE68D90134FB4B13F94882BE70912B4A70D36352",
        "SCENE_GAP_AUTHORITY",
    ),
    "clearance_intake": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_BINDING_INTAKE_V1/CLEARANCE_POLICY_INTAKE_V1.json"),
        "51BF794D0DFFE8B877048EF367B7CCE54EAF3FF37BD1E5F79CB595DCC5AFFAB1",
        "CLEARANCE_GAP_AUTHORITY",
    ),
    "collision_authority_gate": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/ODR60_OPTION_A_COLLISION_AUTHORITY_GATE_V1.json"),
        "81D9201F2A7F62C450C45A067E586BAD722688F300F4D3AC816427BF30C0D763",
        "COLLISION_AUTHORITY",
    ),
    "system_collision_registry": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/M01_SYSTEM_COLLISION_REGISTRY_V1.json"),
        "AC975D11CC4715277E34FCFF7ABF049BC57334FD8F03AAB223BBED0877B1694F",
        "OBJECT_REGISTRY",
    ),
    "pair_coverage": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/M01_PAIR_COVERAGE_V1.csv"),
        "C1F64FB26D4E563EEF6BF798EE163645FE16766CC3C510552769DB7FDF97306C",
        "PAIR_UNIVERSE",
    ),
    "base_proxy_receipt": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/base_link_proxy_v2/BASE_LINK_OPERATIONAL_COLLISION_RECEIPT_V2.json"),
        "5871D0AF4F9E31BF19240E4C8E885CB4715DA8936FF74BBB34F2367655BBACDA",
        "BASE_OPERATIONAL_PROXY",
    ),
    "system_binding_gate": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_SYSTEM_BINDING_CONTRACT_V1/SYSTEM_BINDING_READINESS_GATE_V1.json"),
        "D93D9710EB1177417565B303138956CC70A41B0373A7148863CDEC6CF9877223",
        "SYSTEM_BINDING_READINESS",
    ),
    "motion_contract": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_SYSTEM_BINDING_CONTRACT_V1/OBJECT_MOTION_BOUND_CONTRACT_V1.json"),
        "CA1A741576A90301D77FD684DFA07882FB1AB88A00E927C1381D8709C715A5CD",
        "MOTION_CERTIFICATE_CONTRACT",
    ),
    "pair_oracle_contract": (
        Path("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_SYSTEM_BINDING_CONTRACT_V1/SYSTEM_PAIR_ORACLE_CONTRACT_V1.json"),
        "D8B9CEE66BBD1793732F08F8E52C070B91CC5A6FCAAE56820E09E3C13BC81417",
        "PAIR_ORACLE_CONTRACT",
    ),
    "unified_frame_tree": (
        Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/source_only_v2/UNIFIED_R2_SYSTEM_FRAME_TREE_V2.yaml"),
        "5F8B19DC5BF14EFBB3C6A781C6816D52FE80804DAB328821623E165239999756",
        "FULL_PRECISION_FRAME_LEDGER",
    ),
    "unified_source_inputs": (
        Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/source_only_v2/UNIFIED_R2_URDF_SOURCE_INPUTS_V2.yaml"),
        "8DC401FF86F6642DDD47585AD7ECE74F58831E7D3848F3B002BBF2B5952C56F3",
        "INDEPENDENT_FULL_PRECISION_FRAME_LEDGER",
    ),
    "m3r_physical_stack": (
        Path("20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/M3_interface_authority/M3R_TSM_PHYSICAL_STACK.yaml"),
        "172F3603E458F670323925E644BC68623EE9C85FCA7AF1200FAE2576EB43C68B",
        "PHYSICAL_INSTALLATION_AUTHORITY",
    ),
    "m5_linklocal_geometry": (
        Path("20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/01_geometry_authority/B601_CAD_MESH_FRAME_DECISION_V1.json"),
        "2A99484C6CE55B402CB06380F5DCB71D5A8B4BA622A371EEF72F4EC69EF124FF",
        "LINK_LOCAL_ASSET_FRAME_AUTHORITY",
    ),
    "wp11_cad_urdf_calibration": (
        Path("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp11_cad_urdf_registration/B601_CAD_URDF_GEOMETRY_CALIBRATION_V1.yaml"),
        "7463C1309C3530A42BB32CB4A661FFA56575691DFB7A4BE801AAE9094BEB51E1",
        "DESIGN_CALIBRATION",
    ),
    "accepted_b601_urdf": (
        Path("20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"),
        "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164",
        "KINEMATIC_HARDWARE_TRUTH",
    ),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def strict_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"DUPLICATE_JSON_KEY:{key}")
        out[key] = value
    return out


def strict_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_pairs)


def canonical_digest(value) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256_bytes(data)


def repo_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def verify_source_pins(repo_root: Path):
    rows = []
    for source_id, (rel, expected, role) in SOURCE_PINS.items():
        path = repo_path(repo_root, rel)
        if not path.is_file():
            raise FileNotFoundError(f"SOURCE_PIN_MISSING:{source_id}:{path}")
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(f"SOURCE_PIN_MISMATCH:{source_id}:{expected}:{actual}")
        rows.append(
            {
                "source_id": source_id,
                "path": str(rel).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": actual,
                "role": role,
                "match": True,
            }
        )
    return rows


def source_manifest_text(rows) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=["source_id", "path", "bytes", "sha256", "role", "match"],
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def parse_execution_prompt_selection(text: str, contract_tokens):
    """Return authority only from the specifically titled fenced execution prompt.

    Global token occurrence, recommendations, quotations, and unrelated fenced blocks
    are intentionally ignored.  The raw first non-empty block line must equal the
    selected token; whitespace-normalized equality is not sufficient.
    """
    lines = text.splitlines()
    heading_lines = [i for i, line in enumerate(lines) if line == EXECUTION_PROMPT_HEADING]
    evidence = {
        "authority_evidence_class": "EXPLICIT_EXECUTION_PROMPT_BLOCK_FIRST_LINE",
        "heading": EXECUTION_PROMPT_HEADING,
        "heading_line_numbers": [i + 1 for i in heading_lines],
        "heading_unique": len(heading_lines) == 1,
        "fence_open_line": None,
        "fence_close_line": None,
        "first_nonempty_line_number": None,
        "first_nonempty_line_raw": None,
        "execution_block_sha256": None,
        "selected_token": None,
        "authorized": False,
        "failure_reason": None,
    }
    if len(heading_lines) != 1:
        evidence["failure_reason"] = "EXECUTION_PROMPT_HEADING_NOT_UNIQUE"
        return evidence

    index = heading_lines[0] + 1
    while index < len(lines) and lines[index].strip() == "":
        index += 1
    if index >= len(lines) or lines[index] not in {"```", "```text"}:
        evidence["failure_reason"] = "IMMEDIATE_FENCED_EXECUTION_BLOCK_ABSENT"
        return evidence
    evidence["fence_open_line"] = index + 1
    close = index + 1
    while close < len(lines) and lines[close] != "```":
        close += 1
    if close >= len(lines):
        evidence["failure_reason"] = "EXECUTION_PROMPT_FENCE_UNCLOSED"
        return evidence
    evidence["fence_close_line"] = close + 1
    block_lines = lines[index + 1 : close]
    block_text = "\n".join(block_lines)
    evidence["execution_block_sha256"] = sha256_bytes(block_text.encode("utf-8"))
    nonempty = [(index + 2 + offset, line) for offset, line in enumerate(block_lines) if line.strip()]
    if not nonempty:
        evidence["failure_reason"] = "EXECUTION_PROMPT_BLOCK_EMPTY"
        return evidence
    first_line_number, first_raw = nonempty[0]
    evidence["first_nonempty_line_number"] = first_line_number
    evidence["first_nonempty_line_raw"] = first_raw
    if first_raw not in contract_tokens:
        evidence["failure_reason"] = "FIRST_NONEMPTY_LINE_IS_NOT_EXACT_CONTRACT_TOKEN"
        return evidence
    other_branch_tokens = [token for token in contract_tokens if token != first_raw]
    if any(token in block_text for token in other_branch_tokens):
        evidence["failure_reason"] = "MULTIPLE_BRANCH_TOKENS_IN_EXECUTION_PROMPT_BLOCK"
        return evidence
    evidence["selected_token"] = first_raw
    evidence["authorized"] = True
    return evidence


def owner_selection_record(repo_root: Path, decision_request: dict):
    text = ATTACHMENT.read_text(encoding="utf-8")
    lines = text.splitlines()
    contract_tokens = decision_request["owner_response_contract"]["select_exactly_one_token"]
    expected_contract = [OPTION_A, OPTION_B, OPTION_HOLD]
    if contract_tokens != expected_contract:
        raise RuntimeError("OWNER_RESPONSE_CONTRACT_CHANGED")

    selection_evidence = parse_execution_prompt_selection(text, contract_tokens)
    low_count = sum(line.strip() == LOW_MEMORY for line in lines)
    explicit_low_memory_non_authority = (
        "**现在不要提前发送**" in text
        and "停止并请求当前 run_id 专用" in text
        and decision_request["owner_response_contract"]["low_memory_confirmation_is_separate_and_run_specific"]
    )
    if not selection_evidence["authorized"] or selection_evidence["selected_token"] != OPTION_A:
        raise RuntimeError(f"OWNER_SELECTION_NOT_EXPLICIT_EXECUTION_BLOCK_OPTION_A:{selection_evidence}")
    if low_count == 0 or not explicit_low_memory_non_authority:
        raise RuntimeError("LOW_MEMORY_NON_AUTHORITY_NOT_EXPLICIT")

    occurrences = {}
    for token in expected_contract + [LOW_MEMORY]:
        occurrences[token] = [index + 1 for index, line in enumerate(lines) if line.strip() == token]

    return {
        "schema": "OWNER_SELECTION_RECORD_V1",
        "decision_id": "ODR-60",
        "generated_utc": "DETERMINISTIC_RECORD_NO_WALLCLOCK",
        "source": {
            "path": str(ATTACHMENT),
            "bytes": ATTACHMENT.stat().st_size,
            "sha256": sha256_file(ATTACHMENT),
            "line_count": len(lines),
        },
        "owner_response_contract": {
            "source_path": str(SOURCE_PINS["odr60_decision_request"][0]).replace("\\", "/"),
            "source_sha256": SOURCE_PINS["odr60_decision_request"][1],
            "select_exactly_one_token": contract_tokens,
        },
        "diagnostic_global_token_occurrences_not_authority": occurrences,
        "machine_authority_evidence": selection_evidence,
        "selection": {
            "selected_option": "A",
            "selected_token": OPTION_A,
            "option_a_selected": True,
            "option_b_selected": False,
            "hold_option_selected": False,
            "exactly_one_branch_selected": True,
            "machine_evidence": "EXPLICIT_EXECUTION_PROMPT_BLOCK_FIRST_LINE",
            "effect": "OWNER_BRANCH_SELECTION_RECORDED__ALL_PRESEARCH_AND_RUNTIME_GATES_REMAIN_REQUIRED",
        },
        "low_memory": {
            "token": LOW_MEMORY,
            "token_is_separate_from_branch_selection": True,
            "explicitly_not_authorized_now": True,
            "authorized_run_id": None,
            "authorization_window_start_utc": None,
            "authorization_window_end_utc": None,
            "risk_override_reusable": False,
            "memory_gate_passed": False,
            "runtime_memory_admission_pass": False,
            "disposition": "NOT_AUTHORIZED__REQUEST_FRESH_RUN_SPECIFIC_TOKEN_ONLY_IF_PRE_RUN_AVAILABLE_MEMORY_IS_BELOW_6_GIB",
        },
        "execution_effect": {
            "geometry_query_authorized_by_selection_alone": False,
            "pair_evaluation_authorized_by_selection_alone": False,
            "edge_evaluation_authorized_by_selection_alone": False,
            "path_search_authorized_by_selection_alone": False,
            "release_credit": False,
        },
        "review_status": "OWNER_SELECTION_RECORDED",
        "verdict": "ODR60_OPTION_A_SELECTED__LOW_MEMORY_OVERRIDE_EXPLICITLY_NOT_AUTHORIZED__PRESEARCH_GATES_STILL_FAIL_CLOSED",
    }


def build_mount_binding(repo_root: Path):
    frame_tree_path = repo_path(repo_root, SOURCE_PINS["unified_frame_tree"][0])
    source_inputs_path = repo_path(repo_root, SOURCE_PINS["unified_source_inputs"][0])
    stack_path = repo_path(repo_root, SOURCE_PINS["m3r_physical_stack"][0])
    frame_tree = yaml.safe_load(frame_tree_path.read_text(encoding="utf-8"))
    source_inputs = yaml.safe_load(source_inputs_path.read_text(encoding="utf-8"))
    stack = yaml.safe_load(stack_path.read_text(encoding="utf-8"))

    frame_matrix = frame_tree["canonical_absolute_frames_in_spacecraft_bus_S"]["B601_BASE_PHYSICAL"]["T_S_frame"]
    input_matrix = source_inputs["frames"]["T_S_B601_ARM_BASE_PHYSICAL"]
    expected_numeric = [
        [0.0, 0.0, 1.0, 0.208],
        [0.422618483193, 0.906307683772, 0.0, 0.0],
        [-0.906307683772, 0.422618483193, 0.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
    if frame_matrix != expected_numeric or input_matrix != expected_numeric:
        raise RuntimeError("FULL_PRECISION_MOUNT_SOURCE_DISAGREEMENT")
    station = float(stack["central_boss_physical_installation_face"]["station_x_mm"])
    clock_deg = float(stack["b601_as_built_fastener_end_plane"]["pattern_clocking_about_x_deg"])
    if station != 208.0 or clock_deg != 25.000014:
        raise RuntimeError("M3R_PHYSICAL_STACK_AUTHORITY_CHANGED")
    sine = math.sin(math.radians(clock_deg))
    cosine = math.cos(math.radians(clock_deg))
    if abs(sine - expected_numeric[1][0]) > 5e-13 or abs(cosine - expected_numeric[1][1]) > 5e-13:
        raise RuntimeError("MOUNT_CLOCK_TRIGONOMETRIC_CROSSCHECK_FAILED")

    canonical_strings = [
        ["0.000000000000", "0.000000000000", "1.000000000000", "0.208000000000"],
        ["0.422618483193", "0.906307683772", "0.000000000000", "0.000000000000"],
        ["-0.906307683772", "0.422618483193", "0.000000000000", "0.000000000000"],
        ["0.000000000000", "0.000000000000", "0.000000000000", "1.000000000000"],
    ]
    payload = {
        "frame_name": "T_S_B601_ARM_BASE_PHYSICAL",
        "parent_frame": "spacecraft_bus_S",
        "child_frame": "base_link",
        "matrix_semantics": "p_parent=R_parent_child*p_child+t_parent_child",
        "translation_unit": "m",
        "rotation_unit": "dimensionless",
        "canonical_decimal_places": 12,
        "canonical_matrix_decimal_strings": canonical_strings,
    }
    spelling_policy = {
        "runtime_must_consume_canonical_decimal_strings_above": True,
        "historical_D6_6dp_mount_forbidden": True,
        "rounded_25_deg_reconstruction_forbidden": True,
        "mixing_D6_and_full_precision_forbidden": True,
        "mpi_physical_to_dynamics_bridge_reapplication_in_collision_scene_forbidden": True,
    }
    binding_sha256 = canonical_digest(payload)
    return {
        "schema": "ODR60_OPTION_A_EXECUTION_MOUNT_BINDING_V1",
        "generated_utc": "DETERMINISTIC_BINDING_NO_WALLCLOCK",
        "authority": "OPTION_A_PRESEARCH_EXECUTION_BINDING_CANDIDATE__NOT_RELEASE",
        "source_pins": {
            key: {
                "path": str(SOURCE_PINS[key][0]).replace("\\", "/"),
                "sha256": SOURCE_PINS[key][1],
            }
            for key in ("unified_frame_tree", "unified_source_inputs", "m3r_physical_stack", "accepted_b601_urdf")
        },
        "binding": payload,
        "canonical_binding_payload_sha256": binding_sha256,
        "system_mount_binding_sha256": binding_sha256,
        "runtime_mount_numeric_spelling_policy_sha256": canonical_digest(spelling_policy),
        "cross_checks": {
            "two_independent_full_precision_ledgers_exactly_agree": True,
            "station_x_matches_physical_stack_208_mm": True,
            "clock_matches_physical_stack_25p000014_deg": True,
            "trigonometric_reconstruction_matches_12dp_matrix": True,
            "accepted_urdf_raw_sha256_match": True,
        },
        "spelling_policy": spelling_policy,
        "execution_mount_numeric_spelling_bound": True,
        "binding_scope": "ODR60_OPTION_A_PRESEARCH_STATIC_BINDING_ONLY",
        "pair_evaluation_authorized": False,
        "edge_evaluation_authorized": False,
        "path_search_authorized": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "verdict": "FULL_PRECISION_EXECUTION_MOUNT_SPELLING_BOUND_FOR_OPTION_A_PRESEARCH__NO_GEOMETRY_PAIR_EDGE_PATH_OR_RELEASE_AUTHORITY",
    }


def select_asset(registry_object: dict):
    geometry = registry_object["geometry"]
    if registry_object["object_id"] == "A::base_link":
        asset = geometry["operational_proxy"]["canonical_machine_authority"]
        return asset, True, "OPERATIONAL_PROXY_FRAME_BOUND__PAIR_EVALUATION_STILL_FORBIDDEN"
    asset = geometry["narrowphase_candidate"]
    return asset, False, "DESIGN_SCREENING_ASSET_FRAME_BOUND__OPERATIONAL_NARROWPHASE_PROMOTION_HOLD"


def parse_vector(text: str):
    return [float(value) for value in text.split()]


def urdf_joint_ledger(urdf_root):
    joints = {}
    for element in urdf_root.findall("joint"):
        origin = element.find("origin")
        axis = element.find("axis")
        limit = element.find("limit")
        joints[element.attrib["name"]] = {
            "name": element.attrib["name"],
            "type": element.attrib["type"],
            "parent": element.find("parent").attrib["link"],
            "child": element.find("child").attrib["link"],
            "origin_xyz": parse_vector(origin.attrib.get("xyz", "0 0 0")) if origin is not None else [0.0, 0.0, 0.0],
            "origin_rpy": parse_vector(origin.attrib.get("rpy", "0 0 0")) if origin is not None else [0.0, 0.0, 0.0],
            "axis": parse_vector(axis.attrib.get("xyz", "0 0 0")) if axis is not None else None,
            "lower": float(limit.attrib["lower"]) if limit is not None and "lower" in limit.attrib else None,
            "upper": float(limit.attrib["upper"]) if limit is not None and "upper" in limit.attrib else None,
        }
    return joints


def rotate_rpy(vector, rpy):
    roll, pitch, yaw = rpy
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rotation = [
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp, cp * sr, cp * cr],
    ]
    return [sum(rotation[row][col] * vector[col] for col in range(3)) for row in range(3)]


def close_vector(actual, expected, tolerance=1e-12):
    return len(actual) == len(expected) and all(abs(a - b) <= tolerance for a, b in zip(actual, expected))


def build_collision_registration(repo_root: Path, mount: dict):
    registry = strict_json(repo_path(repo_root, SOURCE_PINS["system_collision_registry"][0]))
    m5 = strict_json(repo_path(repo_root, SOURCE_PINS["m5_linklocal_geometry"][0]))
    calibration = yaml.safe_load(
        repo_path(repo_root, SOURCE_PINS["wp11_cad_urdf_calibration"][0]).read_text(encoding="utf-8")
    )
    receipt = strict_json(repo_path(repo_root, SOURCE_PINS["base_proxy_receipt"][0]))
    urdf_root = ET.parse(repo_path(repo_root, SOURCE_PINS["accepted_b601_urdf"][0])).getroot()
    urdf_links = {link.attrib["name"] for link in urdf_root.findall("link")}
    joints = urdf_joint_ledger(urdf_root)
    joint_by_child = {joint["child"]: joint for joint in joints.values()}
    expected_links = {
        "base_link", "link1", "link2", "link3", "link4", "link5", "link6",
        "gripper_link", "gripper_left", "gripper_right",
    }
    if urdf_links != expected_links:
        raise RuntimeError("ACCEPTED_URDF_LINK_SET_CHANGED")
    a_objects = sorted((obj for obj in registry["objects"] if obj["category"] == "A"), key=lambda x: x["object_id"])
    if len(a_objects) != 10:
        raise RuntimeError("A_CATEGORY_OBJECT_COUNT_NOT_10")

    rows = []
    for obj in a_objects:
        object_id = obj["object_id"]
        link_name = object_id.split("::", 1)[1]
        asset, operational_candidate, status = select_asset(obj)
        asset_path = repo_path(repo_root, Path(asset["path"]))
        actual_asset_sha256 = sha256_file(asset_path)
        if actual_asset_sha256 != asset["sha256"]:
            raise RuntimeError(f"COLLISION_ASSET_HASH_MISMATCH:{object_id}")

        if link_name in m5["components"]:
            m5_entry = m5["components"][link_name]
            m5_asset = m5_entry["local_surface"]
            m5_frame = m5_entry["carrier_frame"]
            m5_role = "M5_LINK_COMPONENT"
        else:
            gripper_key = {
                "gripper_link": "palm",
                "gripper_left": "left_finger",
                "gripper_right": "right_finger",
            }[link_name]
            m5_entry = m5["active_gripper_r1"][gripper_key]
            m5_asset = m5_entry["local_surface"]
            m5_frame = m5_entry["frame"]
            m5_role = f"M5_ACTIVE_GRIPPER_R1_{gripper_key.upper()}"

        child_joint = joint_by_child.get(link_name)
        urdf_tree_contract_matches = (
            link_name == "base_link" and child_joint is None
        ) or (
            child_joint is not None
            and child_joint["child"] == link_name
            and child_joint["parent"] in urdf_links
        )

        if object_id in {"A::gripper_left", "A::gripper_right"}:
            storage_frame = m5_frame
            joint_name = "gripper_joint1" if object_id.endswith("left") else "gripper_joint2"
            state_name = f"{joint_name}_m"
            joint = joints[joint_name]
            axis_parent = rotate_rpy(joint["axis"], joint["origin_rpy"])
            sign = -1.0 if axis_parent[1] < 0.0 else 1.0
            m5_range_key = "left_translation_m" if object_id.endswith("left") else "right_translation_m"
            m5_range = m5["active_gripper_r1"]["motion_contract"][m5_range_key]
            prismatic_contract_matches = (
                joint["type"] == "prismatic"
                and joint["parent"] == "gripper_link"
                and joint["child"] == link_name
                and joint["lower"] == 0.0
                and joint["upper"] == 0.0715
                and abs(axis_parent[0]) < 5e-6
                and abs(abs(axis_parent[1]) - 1.0) < 1e-9
                and abs(axis_parent[2]) < 1e-12
                and close_vector(m5_range, [0.0, sign * 0.0715])
            )
            motion = {
                "type": "PRISMATIC_TRANSLATION_FROM_CLOSED_TRAVEL_ZERO",
                "state_variable": state_name,
                "state_value_m": None,
                "translation_in_gripper_link_formula": ["0.0", f"{sign:+.1f}*{state_name}", "0.0"],
                "allowed_domain_m": [joint["lower"], joint["upper"]],
                "axis_in_parent_frame_from_accepted_urdf": axis_parent,
                "runtime_state_bound": False,
                "source": "M5_ACTIVE_GRIPPER_R1_MOTION_CONTRACT",
            }
        else:
            storage_frame = receipt["frame_contract"]["frame"] if object_id == "A::base_link" else m5_frame
            prismatic_contract_matches = True
            motion = {
                "type": "RIGID_LINK_LOCAL",
                "state_variable": None,
                "state_value_m": None,
                "asset_to_link_internal_transform_bound": True,
                "external_q6_scene_value_bound": False,
                "source": "M5_INVERSE_Q0_LINK_LOCALIZATION",
            }

        gripper_motion_contract = m5["active_gripper_r1"]["motion_contract"]
        if object_id == "A::base_link":
            registry_asset_field_matches = (
                obj["geometry"]["operational_proxy"]["canonical_machine_authority"]["path"] == asset["path"]
                and obj["geometry"]["operational_proxy"]["canonical_machine_authority"]["sha256"] == asset["sha256"]
            )
            m5_or_operational_asset_authority_matches = (
                m5_frame == "base_link"
                and receipt["artifacts"]["canonical_npz"]["sha256"] == asset["sha256"]
                and Path(receipt["artifacts"]["canonical_npz"]["path"]).name == Path(asset["path"]).name
                and receipt["frame_contract"]["frame"] == "base_link"
                and receipt["frame_contract"]["collision_unit"] == "meter"
                and receipt["frame_contract"]["spacecraft_mount_transform_baked"] is False
            )
        else:
            registry_asset_field_matches = (
                obj["geometry"]["narrowphase_candidate"]["path"] == asset["path"]
                and obj["geometry"]["narrowphase_candidate"]["sha256"] == asset["sha256"]
                and obj["geometry"]["narrowphase_candidate"]["units"] == asset["units"]
            )
            m5_or_operational_asset_authority_matches = (
                m5_asset["path"] == asset["path"]
                and m5_asset["sha256"] == asset["sha256"]
                and m5_asset["units"] == asset["units"]
            )

        if link_name.startswith("gripper"):
            m5_gripper_frame_contract_matches = (
                m5_frame == "gripper_link"
                and gripper_motion_contract["corrected_frame_binding"] == "gripper_link"
                and gripper_motion_contract["frame_registration"]["gripper_link_registration_pass"] is True
                and gripper_motion_contract["frame_registration"]["direct_link6_binding_rejected"] is True
            )
        else:
            m5_gripper_frame_contract_matches = True

        calibration_scope_matches = (
            link_name.startswith("gripper")
            or (
                link_name in calibration["links"]
                and calibration["links"][link_name]["D_i_rotation"] == "IDENTITY"
            )
        )
        cross_checks = {
            "registry_object_id_maps_to_accepted_urdf_link": link_name in urdf_links,
            "registry_parent_frame_exists_in_accepted_urdf": obj["parent_frame"] in urdf_links,
            "registry_selected_asset_path_hash_units_match": registry_asset_field_matches,
            "selected_asset_actual_sha256_matches_registry": actual_asset_sha256 == asset["sha256"],
            "selected_asset_units_are_metres": asset["units"] == "m",
            "m5_frame_matches_selected_storage_frame": m5_frame == storage_frame,
            "m5_asset_or_base_operational_receipt_matches_selected_asset": m5_or_operational_asset_authority_matches,
            "accepted_urdf_registration_frame_exists": storage_frame in urdf_links,
            "accepted_urdf_parent_child_tree_contract_matches": urdf_tree_contract_matches,
            "wp11_calibration_scope_matches_or_is_not_applicable_to_gripper": calibration_scope_matches,
            "m5_gripper_frame_contract_matches_or_is_not_applicable": m5_gripper_frame_contract_matches,
            "accepted_urdf_prismatic_motion_matches_m5_or_is_not_applicable": prismatic_contract_matches,
        }
        frame_relationship_proven = all(type(value) is bool and value for value in cross_checks.values())

        calibration_evidence = None
        if link_name in calibration["links"]:
            cal = calibration["links"][link_name]
            calibration_evidence = {
                "D_i_definition": calibration["definition"]["D_i"],
                "D_i_translation_mm": cal["D_i_translation_mm"],
                "D_i_rotation": cal["D_i_rotation"],
                "runtime_reapplication_to_link_local_asset_forbidden": True,
                "reason": "THE_SELECTED_M5_ASSET_IS_ALREADY_STORED_IN_THE_ACCEPTED_URDF_LINK_FRAME",
            }

        operational = operational_candidate and frame_relationship_proven
        if not frame_relationship_proven:
            status = "HOLD_UNPROVEN_STATIC_FRAME_RELATIONSHIP"
        rows.append(
            {
                "object_id": object_id,
                "m5_authority_role": m5_role,
                "registry_parent_frame": obj["parent_frame"],
                "asset_path": asset["path"],
                "asset_sha256": asset["sha256"],
                "asset_units": asset["units"],
                "asset_storage_frame": storage_frame,
                "accepted_urdf_registration_frame": storage_frame,
                "T_registration_frame_asset_storage": (
                    {"rotation": "IDENTITY", "translation": [0.0, 0.0, 0.0], "translation_unit": "m"}
                    if frame_relationship_proven else None
                ),
                "evidence_cross_checks": cross_checks,
                "all_verifiable_fields_crosschecked": frame_relationship_proven,
                "frame_relationship_bound": frame_relationship_proven,
                "runtime_object_pose_bound": False,
                "motion_registration": motion,
                "calibration_evidence": calibration_evidence,
                "operational_narrowphase_promoted": operational,
                "pair_evaluation_authorized": False,
                "status": status,
            }
        )

    base = next(row for row in rows if row["object_id"] == "A::base_link")
    if base["asset_sha256"] != receipt["artifacts"]["canonical_npz"]["sha256"]:
        raise RuntimeError("BASE_PROXY_RECEIPT_ASSET_MISMATCH")
    if receipt["frame_contract"]["frame"] != "base_link" or receipt["frame_contract"]["spacecraft_mount_transform_baked"]:
        raise RuntimeError("BASE_PROXY_FRAME_CONTRACT_UNEXPECTED")

    return {
        "schema": "ODR60_OPTION_A_COLLISION_FRAME_REGISTRATION_V1",
        "generated_utc": "DETERMINISTIC_REGISTRATION_NO_WALLCLOCK",
        "authority": "ACCEPTED_B601_URDF_SUBTREE_ASSET_FRAME_LEDGER__NOT_SYSTEM_COLLISION_PASS",
        "source_pins": {
            key: {
                "path": str(SOURCE_PINS[key][0]).replace("\\", "/"),
                "sha256": SOURCE_PINS[key][1],
            }
            for key in (
                "accepted_b601_urdf", "system_collision_registry", "m5_linklocal_geometry",
                "wp11_cad_urdf_calibration", "base_proxy_receipt",
            )
        },
        "execution_mount_binding": {
            "path": "EXECUTION_MOUNT_BINDING_V1.json",
            "document_sha256": sha256_bytes(json_text(mount).encode("utf-8")),
            "canonical_binding_payload_sha256": mount["canonical_binding_payload_sha256"],
            "spacecraft_mount_transform_baked_into_assets": False,
        },
        "frame_semantics": {
            "asset_origins_are_relative_to_asset_storage_frame": True,
            "accepted_urdf_joint_origins_are_parent_to_joint_child_frame": True,
            "joint_axes_are_expressed_in_joint_frame": True,
            "spacecraft_execution_mount_is_not_baked_into_link_local_assets": True,
            "mpi_bridge_must_not_be_applied_to_collision_assets": True,
        },
        "registrations": rows,
        "summary": {
            "accepted_urdf_link_count": 10,
            "registry_A_object_count": 10,
            "frame_relationships_bound": sum(row["frame_relationship_bound"] for row in rows),
            "rows_with_all_verifiable_fields_crosschecked": sum(row["all_verifiable_fields_crosschecked"] for row in rows),
            "operational_narrowphase_promoted": sum(row["operational_narrowphase_promoted"] for row in rows),
            "gripper_state_dependent_rows": 2,
            "gripper_state_values_bound": 0,
            "full_150_object_execution_pose_registration_bound": False,
            "complete_system_operational_collision_asset_set_bound": False,
        },
        "holds": [
            "NINE_OF_TEN_B601_ASSETS_NOT_PROMOTED_TO_OPERATIONAL_NARROWPHASE_AUTHORITY",
            "TWO_GRIPPER_PRISMATIC_STATE_VALUES_UNBOUND",
            "FULL_150_OBJECT_EXECUTION_POSE_AND_MOTION_REGISTRATION_NOT_BOUND",
            "PAIR_CLEARANCE_AND_ORACLE_AUTHORITY_ABSENT",
        ],
        "pair_evaluation_authorized": False,
        "edge_evaluation_authorized": False,
        "path_search_authorized": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "verdict": "ACCEPTED_URDF_SUBTREE_COLLISION_ASSET_FRAME_LEDGER_10_OF_10_BOUND__ONLY_BASE_PROXY_OPERATIONAL__FULL_SYSTEM_COLLISION_REGISTRATION_HOLD",
    }


def build_scene_schema(scene_intake: dict, scope: dict, mount: dict):
    required = scene_intake["required_bindings"]
    if scene_intake["bound_required_binding_count"] != 0 or scene_intake["required_binding_count"] != 9:
        raise RuntimeError("LEGACY_SCENE_INTAKE_COUNTS_CHANGED")
    endpoints = scope["fixed_endpoint_contract"]
    stages = [
        {
            "stage_id": "PRE_RELEASE_CONSTANT_SCENE",
            "kind": "CONSTANT_SCENE_EDGE",
            "instance": None,
            "required_constant_fields": [
                "gripper_joint1_m", "gripper_joint2_m", "solar_state", "solar_hdrm_state",
                "solar_latch_state", "arm_hdrm_state", "target_present", "target_attached",
                "active_object_universe_sha256", "active_pair_universe_sha256",
            ],
            "arm_hdrm_state_value": None,
            "status": "SCHEMA_BOUND__INSTANCE_VALUES_UNKNOWN",
        },
        {
            "stage_id": "RELEASE_EVENT_SCENE",
            "kind": "DISCRETE_EVENT_CONTRACT",
            "instance": None,
            "required_fields": [
                "event_id", "event_time_or_ordering", "pre_scene_sha256", "post_scene_sha256",
                "arm_hdrm_state_t0_minus", "arm_hdrm_state_t0_plus", "release_outcome",
                "released_constraint_ids", "retained_constraint_ids", "failure_disposition",
            ],
            "event_values": None,
            "status": "SCHEMA_BOUND__EVENT_CONTRACT_INSTANCE_UNKNOWN",
        },
        {
            "stage_id": "POST_RELEASE_CONSTANT_SCENE",
            "kind": "CONSTANT_SCENE_EDGE",
            "instance": None,
            "required_constant_fields": [
                "gripper_joint1_m", "gripper_joint2_m", "solar_state", "solar_hdrm_state",
                "solar_latch_state", "arm_hdrm_state", "target_present", "target_attached",
                "active_object_universe_sha256", "active_pair_universe_sha256",
            ],
            "arm_hdrm_state_value": None,
            "status": "SCHEMA_BOUND__INSTANCE_VALUES_UNKNOWN",
        },
    ]
    schema_core = {
        "stage_order": [stage["stage_id"] for stage in stages],
        "continuous_q_contract": {
            "q6_is_separate_from_discrete_scene_state": True,
            "joint_order": scope["joint_order"],
            "unit": "rad",
            "fixed_start_name": endpoints["from_state"],
            "fixed_goal_name": endpoints["to_state"],
            "q_start_rad": endpoints["q_start_rad"],
            "q_goal_rad": endpoints["q_goal_rad"],
            "candidate_path_sha256": None,
            "candidate_path_bound": False,
        },
        "stages": stages,
    }
    return {
        "schema": "M01_THREE_STAGE_SCENE_SCHEMA_V2",
        "generated_utc": "DETERMINISTIC_SCHEMA_NO_WALLCLOCK",
        "authority": "SCHEMA_AND_FIXED_ENDPOINT_BINDING_ONLY__NO_OBJECT_STATE_VALUES_INFERRED",
        "supersedes": {
            "path": str(SOURCE_PINS["scene_intake"][0]).replace("\\", "/"),
            "sha256": SOURCE_PINS["scene_intake"][1],
            "scope": "M01_EVENT_PARTITION_SCHEMA_ONLY",
        },
        "source_pins": {
            "scene_intake_sha256": SOURCE_PINS["scene_intake"][1],
            "option_a_scope_sha256": SOURCE_PINS["option_a_scope"][1],
            "system_registry_sha256": SOURCE_PINS["system_collision_registry"][1],
            "pair_universe_sha256": SOURCE_PINS["pair_coverage"][1],
        },
        "fixed_structure_binding": {
            "arm_execution_mount_path": "EXECUTION_MOUNT_BINDING_V1.json",
            "arm_execution_mount_document_sha256": sha256_bytes(json_text(mount).encode("utf-8")),
            "arm_execution_mount_canonical_payload_sha256": mount["canonical_binding_payload_sha256"],
            "bus_pose_S": "IDENTITY_PROXY_ONLY",
            "load_bridge_pose_S": None,
            "m3r_stage_a_pose_S": None,
            "m3r_stage_b_pose_S": None,
            "complete_fixed_structure_binding": False,
        },
        "canonicalization": {
            "scene_state_must_be_constant_on_each_certified_edge": True,
            "release_event_must_be_a_separate_contract_not_a_constant_edge": True,
            "q6_must_not_be_duplicated_inside_discrete_scene_state": True,
            "any_object_set_change_requires_new_object_and_pair_universe_hashes": True,
            "unknown_or_hash_mismatch": "UNKNOWN_ABORT",
        },
        "schema_contract": schema_core,
        "schema_contract_sha256": canonical_digest(schema_core),
        "field_types": {
            "gripper_joint1_m": {"type": "finite_number", "domain_m": required["gripper_joint1_m"]["allowed_domain_m"]},
            "gripper_joint2_m": {"type": "finite_number", "domain_m": required["gripper_joint2_m"]["allowed_domain_m"]},
            "solar_state": {"type": "enum", "domain": required["solar_state"]["allowed_domain"]},
            "solar_hdrm_state": {
                "type": "structured_per_wing_per_hardpoint_state",
                "value": None,
                "reason": scene_intake["required_schema_extension"]["solar_hdrm_state"]["reason"],
            },
            "solar_latch_state": {
                "type": "structured_two_wing_six_hardpoint_state",
                "value": None,
                "legacy_scalar_forbidden": True,
            },
            "arm_hdrm_state": {"type": "enum", "domain": required["arm_hdrm_state_t0_minus"]["reference_vocabulary"]},
            "target_present": {"type": "boolean"},
            "target_attached": {"type": "boolean", "constraint": "ATTACHED_IMPLIES_PRESENT"},
            "active_object_universe_sha256": {"type": "sha256"},
            "active_pair_universe_sha256": {"type": "sha256"},
        },
        "current_instances": {
            "stage_instances_bound": 0,
            "stage_instances_required": 3,
            "legacy_required_values_bound": 0,
            "legacy_required_values_total": 9,
            "scene_values_bound": False,
            "event_contract_bound": False,
            "active_object_universe_for_all_stages_bound": False,
            "active_pair_universe_for_all_stages_bound": False,
        },
        "known_universe_gaps": scene_intake["universe_gaps"],
        "scene_schema_complete": True,
        "scene_binding_complete": False,
        "pair_evaluation_authorized": False,
        "edge_evaluation_authorized": False,
        "path_search_authorized": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "verdict": "M01_THREE_STAGE_SCENE_SCHEMA_V2_BOUND__ZERO_STAGE_INSTANCES__NO_OBJECT_STATE_INFERRED__PAIR_EDGE_PATH_HOLD",
    }


def top_level_key_occurrence_evidence(path: Path, keys):
    """Preserve every top-level key occurrence and its native decoded value."""
    top_level_pairs = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=lambda pairs: pairs)
    if not isinstance(top_level_pairs, list):
        raise RuntimeError("LEGACY_GATE_TOP_LEVEL_NOT_OBJECT_PAIRS")
    evidence = {}
    for key in keys:
        values = [value for candidate, value in top_level_pairs if candidate == key]
        evidence[key] = {
            "occurrence_count": len(values),
            "native_values": values,
            "all_values_are_native_boolean_false": all(type(value) is bool and value is False for value in values),
        }
    return evidence


def duplicate_keys(path: Path):
    evidence = top_level_key_occurrence_evidence(path, ["next_stage_authorized", "release_credit"])
    return [key for key, item in evidence.items() if item["occurrence_count"] > 1]


def build_preflight_v2(owner, mount, collision, scene, clearance, motion, oracle, legacy_path: Path):
    duplicate_evidence = top_level_key_occurrence_evidence(
        legacy_path, ["next_stage_authorized", "release_credit"]
    )
    duplicate_contract_pass = all(
        item["occurrence_count"] == 2 and item["all_values_are_native_boolean_false"] is True
        for item in duplicate_evidence.values()
    )
    if not duplicate_contract_pass:
        raise RuntimeError(f"UNEXPECTED_LEGACY_PREFLIGHT_DUPLICATE_EVIDENCE:{duplicate_evidence}")
    return {
        "schema": "ODR60_OPTION_A_PREFLIGHT_GATE_V2",
        "generated_utc": "DETERMINISTIC_GATE_NO_WALLCLOCK",
        "authority": "SUPERSEDING_STRICT_JSON_STATIC_PREFLIGHT__NO_HISTORICAL_ARTIFACT_MUTATION",
        "supersession": {
            "superseded_path_for_machine_consumption": str(SOURCE_PINS["legacy_preflight_gate"][0]).replace("\\", "/"),
            "superseded_sha256": SOURCE_PINS["legacy_preflight_gate"][1],
            "legacy_duplicate_key_evidence": duplicate_evidence,
            "duplicate_preserving_parser_check_pass": duplicate_contract_pass,
            "historical_file_modified": False,
            "scientific_gate_upgrade_from_serialization_repair": False,
        },
        "static_closure": {
            "owner_option_a_selection_recorded": owner["selection"]["option_a_selected"],
            "low_memory_override_authorized": not owner["low_memory"]["explicitly_not_authorized_now"],
            "execution_mount_full_precision_spelling_bound": mount["execution_mount_numeric_spelling_bound"],
            "accepted_urdf_subtree_frame_relationships_bound": collision["summary"]["frame_relationships_bound"],
            "accepted_urdf_subtree_frame_relationships_required": 10,
            "complete_system_operational_collision_asset_set_bound": collision["summary"]["complete_system_operational_collision_asset_set_bound"],
            "three_stage_scene_schema_bound": scene["scene_schema_complete"],
            "three_stage_scene_instances_bound": scene["current_instances"]["stage_instances_bound"],
            "three_stage_scene_instances_required": scene["current_instances"]["stage_instances_required"],
            "scene_binding_complete": scene["scene_binding_complete"],
            "clearance_policy_rows_bound": clearance["policy_rows_emitted"],
            "clearance_policy_rows_required": clearance["universe"]["query_required_pair_count"],
            "motion_certificates_bound": motion["current_readiness"]["system_certified_object_motion_bound_count"],
            "motion_certificates_required": motion["current_readiness"]["classified_object_count"],
            "pair_oracle_rows_executed": oracle["current_readiness"]["pair_queries_executed"],
            "pair_oracle_rows_required": oracle["universe"]["query_required_pair_count"],
        },
        "execution_authority": {
            "all_static_preconditions_pass": False,
            "runtime_memory_admission_pass": False,
            "geometry_load_or_query_authorized": False,
            "pair_evaluation_authorized": False,
            "edge_evaluation_authorized": False,
            "path_search_authorized": False,
            "path_search_executed": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
        "blockers": [
            "LOW_MEMORY_OVERRIDE_NOT_AUTHORIZED_AND_RUNTIME_MEMORY_NOT_YET_MEASURED_FOR_A_NAMED_RUN",
            "COMPLETE_SYSTEM_OPERATIONAL_COLLISION_ASSET_SET_NOT_BOUND",
            "THREE_STAGE_SCENE_INSTANCE_VALUES_ZERO_OF_THREE",
            "ACTIVE_OBJECT_AND_PAIR_UNIVERSE_NOT_REISSUED_PER_STAGE",
            "CLEARANCE_POLICY_ZERO_OF_11166",
            "MOTION_CERTIFICATES_ZERO_OF_150",
            "PAIR_ORACLE_ZERO_OF_11166",
            "NO_CONTINUOUS_EDGE_CERTIFICATES",
        ],
        "review_status": "PENDING_INDEPENDENT_REVIEW",
        "verdict": "ODR60_OPTION_A_OWNER_SELECTION_AND_PARTIAL_STATIC_BINDINGS_RECORDED__SCENE_CLEARANCE_MOTION_ORACLE_HOLD__NO_GEOMETRY_PAIR_EDGE_PATH_EXECUTION",
    }


def build_gate(owner, mount, collision, scene, preflight, source_manifest_sha256, local_artifact_pins):
    return {
        "schema": "ODR60_OPTION_A_EXECUTION_CLOSURE_GATE_V1",
        "generated_utc": "DETERMINISTIC_GATE_NO_WALLCLOCK",
        "decision_rule": "Authority > Evidence > Independent reproduction > Agent opinion",
        "owner_selection_recorded": True,
        "static_preflight_pass": False,
        "pair_evaluation_authorized": False,
        "edge_evaluation_authorized": False,
        "path_search_authorized": False,
        "path_search_executed": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "source_hash_manifest_sha256": source_manifest_sha256,
        "local_artifact_pins": local_artifact_pins,
        "owner_authority": {
            "option_a_selected": owner["selection"]["option_a_selected"],
            "option_b_selected": owner["selection"]["option_b_selected"],
            "hold_option_selected": owner["selection"]["hold_option_selected"],
            "low_memory_override_authorized": False,
        },
        "actual_closures": {
            "owner_selection_record": True,
            "legacy_duplicate_key_repaired_by_new_strict_v2_gate": True,
            "historical_gate_rewritten": False,
            "execution_mount_full_precision_spelling_bound": mount["execution_mount_numeric_spelling_bound"],
            "accepted_urdf_subtree_collision_frame_ledger_bound": True,
            "accepted_urdf_subtree_collision_frame_rows": collision["summary"]["frame_relationships_bound"],
            "accepted_urdf_subtree_collision_frame_rows_required": 10,
            "operational_narrowphase_assets_promoted": collision["summary"]["operational_narrowphase_promoted"],
            "m01_three_stage_scene_schema_bound": scene["scene_schema_complete"],
            "m01_three_stage_scene_instances_bound": scene["current_instances"]["stage_instances_bound"],
        },
        "remaining_readiness": preflight["static_closure"],
        "execution_record": {
            "collision_geometry_loaded": False,
            "geometry_query_executed": False,
            "pair_queries_executed": 0,
            "edges_certified": 0,
            "path_search_process_started": False,
            "path_search_executed": False,
        },
        "authority": preflight["execution_authority"],
        "blockers": preflight["blockers"],
        "maximum_claim": "OPTION_A_EXECUTION_CLOSURE_CANDIDATE_WITH_MOUNT_AND_SCHEMA_BINDINGS__PRESEARCH_HOLD",
        "review_status": "PENDING_INDEPENDENT_REVIEW",
        "verdict": "ODR60_OPTION_A_EXECUTION_CLOSURE_CANDIDATE_BUILT__MOUNT_AND_ARM_FRAME_LEDGER_CLOSED__SCENE_VALUES_CLEARANCE_MOTION_ORACLE_HOLD__NO_QUERY_OR_SEARCH_AUTHORITY",
    }


def json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def package_manifest_text(out_dir: Path) -> str:
    rows = []
    excluded = "ODR60_OPTION_A_EXECUTION_CLOSURE_PACKAGE_SHA256_V1.csv"
    for path in sorted(p for p in out_dir.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        if path.name == excluded:
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


def build_outputs(repo_root: Path):
    repo_root = repo_root.resolve()
    source_rows = verify_source_pins(repo_root)
    source_manifest = source_manifest_text(source_rows)
    decision_request = strict_json(repo_path(repo_root, SOURCE_PINS["odr60_decision_request"][0]))
    scope = yaml.safe_load(repo_path(repo_root, SOURCE_PINS["option_a_scope"][0]).read_text(encoding="utf-8"))
    scene_intake = strict_json(repo_path(repo_root, SOURCE_PINS["scene_intake"][0]))
    clearance = strict_json(repo_path(repo_root, SOURCE_PINS["clearance_intake"][0]))
    motion = strict_json(repo_path(repo_root, SOURCE_PINS["motion_contract"][0]))
    oracle = strict_json(repo_path(repo_root, SOURCE_PINS["pair_oracle_contract"][0]))

    owner = owner_selection_record(repo_root, decision_request)
    mount = build_mount_binding(repo_root)
    collision = build_collision_registration(repo_root, mount)
    scene = build_scene_schema(scene_intake, scope, mount)
    preflight = build_preflight_v2(
        owner,
        mount,
        collision,
        scene,
        clearance,
        motion,
        oracle,
        repo_path(repo_root, SOURCE_PINS["legacy_preflight_gate"][0]),
    )
    rendered = {
        "ODR60_OPTION_A_SOURCE_HASH_MANIFEST_V1.csv": source_manifest,
        "OWNER_SELECTION_RECORD_V1.json": json_text(owner),
        "EXECUTION_MOUNT_BINDING_V1.json": json_text(mount),
        "COLLISION_FRAME_REGISTRATION_V1.json": json_text(collision),
        "M01_THREE_STAGE_SCENE_SCHEMA_V2.json": json_text(scene),
        "ODR60_OPTION_A_PREFLIGHT_GATE_V2.json": json_text(preflight),
    }
    local_artifact_pins = {
        name: {"path": name, "sha256": sha256_bytes(content.encode("utf-8"))}
        for name, content in rendered.items()
    }
    gate = build_gate(
        owner,
        mount,
        collision,
        scene,
        preflight,
        sha256_bytes(source_manifest.encode("utf-8")),
        local_artifact_pins,
    )
    rendered["results/ODR60_OPTION_A_EXECUTION_CLOSURE_GATE_V1.json"] = json_text(gate)
    return rendered


def write_outputs(repo_root: Path):
    out_dir = repo_root.resolve() / OUT_REL
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, content in build_outputs(repo_root).items():
        target = out_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
    package_manifest = package_manifest_text(out_dir)
    (out_dir / "ODR60_OPTION_A_EXECUTION_CLOSURE_PACKAGE_SHA256_V1.csv").write_text(
        package_manifest, encoding="utf-8", newline="\n"
    )
    return out_dir


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    out_dir = write_outputs(args.repo_root)
    print(out_dir)


if __name__ == "__main__":
    main()
