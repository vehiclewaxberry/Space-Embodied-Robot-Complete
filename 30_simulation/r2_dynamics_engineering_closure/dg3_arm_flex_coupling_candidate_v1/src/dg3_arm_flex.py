"""Frozen-configuration arm-to-Solar-R2-flex tangent-space diagnostic."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence
import xml.etree.ElementTree as ET

for _name in (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "BLIS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_name, "1")

import numpy as np
import yaml
from scipy.integrate import solve_ivp
from scipy.linalg import block_diag


PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]
CONTRACT_PATH = PACKAGE / "contracts" / "DG3_ARM_FLEX_COUPLING_CONTRACT_V1.json"
PARENT_SRC = PACKAGE.parent / "src"
if str(PARENT_SRC) not in sys.path:
    sys.path.insert(0, str(PARENT_SRC))

from r2_dynamics import load_backend  # noqa: E402


class DG3Error(RuntimeError):
    """Raised for malformed or drifted candidate inputs."""


EXPECTED_CONTRACT_SCHEMA = "DG3_ARM_FLEX_COUPLING_CONTRACT_V1"
EXPECTED_AUTHORITY_SCOPE = (
    "BOUNDED_FROZEN_LINEAR_TANGENT_CANDIDATE_WITH_CANONICAL_CONSERVATION_GATES"
)
EXPECTED_REVIEW_STATUS = "PENDING_OWNER_REVIEW"
EXPECTED_CORNERS = ["LOW", "NOMINAL", "HIGH"]
EXPECTED_EXCITATION_AUTHORITY = (
    "ARBITRARY_SMALL_AMPLITUDE_DIAGNOSTIC_NOT_COMMAND_OR_HARDWARE_ENVELOPE"
)
EXPECTED_SOLVERS = {
    "primary": "RADAU",
    "cross": "BDF",
    "rtol": 1.0e-11,
    "atol": 1.0e-13,
    "max_step_s": 5.0e-4,
    "cross_C0_HIGH_max_step_s": 5.0e-5,
    "cross_C0_HIGH_refinement_reason": "HIGH_corner_undamped_eta_rate_cross_requires_temporal_refinement_without_changing_the_preregistered_1e-6_threshold",
}
EXPECTED_EXECUTION_GUARDS = {
    "contact_called": False,
    "target_attached": False,
    "collision_query_called": False,
    "path_search_called": False,
    "control_command_issued": False,
    "hardware_authority_claimed": False,
}
EXPECTED_FROZEN_Q0_MIXED_RAD_M = [
    -0.000014722592995215019,
    -1.0482002296028674,
    -1.3989828152470147,
    -1.2200100679438755,
    0.000003673218594813444,
    0.000018395811591279014,
    0.03575,
    0.03575,
]
EXPECTED_CONTRACT_SECTION_SHA256 = {
    "full_contract": "66DC37DB5E8B3FCFFBABCC279DD5CD5FBE2634FBEC49C8B2B8C0928738AAACEA",
    "top_level_keys": "FBFBA536328FC6D21C2DEA70275A546679511725D992FF195984F455881D158E",
    "claim_boundary": "6DF57E52615F896DEA1F4C2422B9A83E44BEABB925A0E9662642DB94D3374262",
    "thresholds": "BC067DE57B4D86E2CEC2C50AE386B52E3E16DAFB60ED37368D76C71E57D8634B",
    "threshold_units": "E2B6AA57CFCE31ED77DCFC2FFE2086696204454E9891BC63163B54FED67103AA",
    "units": "5EAF30B1E2CA2BDA06DDB80014ADAEE3839C83C811AAC27FD4B7753014910FC2",
    "corner_semantics": "485CA3E343FE09341393A193982B9EF0171599202C084E70367A457FD0BFEB86",
}
EXPECTED_BASE_COORDINATE_UNITS = ["m", "m", "m", "rad", "rad", "rad"]
EXPECTED_JOINT_UNITS = ["rad", "rad", "rad", "rad", "rad", "rad", "m", "m"]
EXPECTED_MODAL_COORDINATE_UNITS = "MIXED_MASS_NORMALIZED_MODAL_COORDINATES"


def _reject_duplicate_key(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DG3Error(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_key
    )


def _plain_canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest().upper()


def validate_contract_semantics(document: Mapping[str, Any]) -> dict[str, Any]:
    """Fail-closed exact policy validation independent of contract-owned values."""
    frozen = document.get("frozen_linearization", {})
    actual_section_sha256 = {
        "full_contract": _plain_canonical_sha256(document),
        "top_level_keys": _plain_canonical_sha256(sorted(document.keys())),
        **{
            name: _plain_canonical_sha256(document.get(name))
            for name in (
                "claim_boundary",
                "thresholds",
                "threshold_units",
                "units",
                "corner_semantics",
            )
        },
    }
    checks = {
        "full_parsed_contract_canonical_sha256_exact": actual_section_sha256[
            "full_contract"
        ]
        == EXPECTED_CONTRACT_SECTION_SHA256["full_contract"],
        "top_level_schema_fields_exact": actual_section_sha256["top_level_keys"]
        == EXPECTED_CONTRACT_SECTION_SHA256["top_level_keys"],
        "schema_exact": document.get("schema") == EXPECTED_CONTRACT_SCHEMA,
        "authority_scope_exact": document.get("authority_scope")
        == EXPECTED_AUTHORITY_SCOPE,
        "claim_boundary_allowed_and_forbidden_exact": actual_section_sha256[
            "claim_boundary"
        ]
        == EXPECTED_CONTRACT_SECTION_SHA256["claim_boundary"],
        "review_status_exact": document.get("review_status")
        == EXPECTED_REVIEW_STATUS,
        "next_stage_authorized_exact_false": document.get(
            "next_stage_authorized"
        )
        is False,
        "release_credit_exact_false": document.get("release_credit") is False,
        "all_gate_sensitive_thresholds_exact": actual_section_sha256["thresholds"]
        == EXPECTED_CONTRACT_SECTION_SHA256["thresholds"],
        "all_threshold_units_exact": actual_section_sha256["threshold_units"]
        == EXPECTED_CONTRACT_SECTION_SHA256["threshold_units"],
        "physical_units_exact": actual_section_sha256["units"]
        == EXPECTED_CONTRACT_SECTION_SHA256["units"],
        "base_joint_modal_coordinate_units_exact": frozen.get(
            "base_coordinate_units"
        )
        == EXPECTED_BASE_COORDINATE_UNITS
        and frozen.get("joint_units") == EXPECTED_JOINT_UNITS
        and frozen.get("modal_coordinate_units")
        == EXPECTED_MODAL_COORDINATE_UNITS,
        "corner_order_exact_LOW_NOMINAL_HIGH": document.get("corners")
        == EXPECTED_CORNERS,
        "corner_semantics_exact": actual_section_sha256["corner_semantics"]
        == EXPECTED_CONTRACT_SECTION_SHA256["corner_semantics"],
        "prescribed_excitation_authority_exact": document.get(
            "prescribed_excitation", {}
        ).get("authority")
        == EXPECTED_EXCITATION_AUTHORITY,
        "solver_tolerances_and_steps_exact": document.get("solvers")
        == EXPECTED_SOLVERS,
        "execution_guard_keys_and_false_values_exact": document.get(
            "execution_guards"
        )
        == EXPECTED_EXECUTION_GUARDS,
        "frozen_q0_exact": frozen.get("q0_mixed_rad_m")
        == EXPECTED_FROZEN_Q0_MIXED_RAD_M,
    }
    return {
        "schema": "DG3_CONTRACT_SEMANTICS_AUDIT_V1",
        "checks": checks,
        "expected_section_sha256": EXPECTED_CONTRACT_SECTION_SHA256,
        "actual_section_sha256": actual_section_sha256,
        "pass": all(checks.values()),
        "failed": [name for name, passed in checks.items() if not passed],
    }


def contract_tamper_negative_controls(
    document: Mapping[str, Any],
) -> dict[str, Any]:
    """Prove five policy-mutation classes are rejected by the exact validator."""
    mutations: dict[str, tuple[dict[str, Any], tuple[str, ...]]] = {}

    promoted = copy.deepcopy(document)
    promoted["authority_scope"] = "FLIGHT_RELEASE_AUTHORITY"
    promoted["next_stage_authorized"] = True
    promoted["release_credit"] = True
    mutations["authority_promotion"] = (
        promoted,
        (
            "authority_scope_exact",
            "next_stage_authorized_exact_false",
            "release_credit_exact_false",
        ),
    )

    forbidden_deleted = copy.deepcopy(document)
    forbidden_deleted["claim_boundary"]["forbidden"].pop()
    mutations["forbidden_claim_deletion"] = (
        forbidden_deleted,
        ("claim_boundary_allowed_and_forbidden_exact",),
    )

    threshold_widened = copy.deepcopy(document)
    threshold_widened["thresholds"][
        "modes_removed_solver_position_cross_max_m"
    ] *= 10.0
    mutations["threshold_widening"] = (
        threshold_widened,
        ("all_gate_sensitive_thresholds_exact",),
    )

    unit_tampered = copy.deepcopy(document)
    unit_tampered["units"]["base_position"] = "mm"
    mutations["unit_tamper"] = (
        unit_tampered,
        ("physical_units_exact",),
    )

    corner_tampered = copy.deepcopy(document)
    corner_tampered["corners"] = ["NOMINAL", "LOW", "HIGH"]
    corner_tampered["corner_semantics"]["bindings"]["LOW"]["Krom_key"] = (
        "Krom_HIGH"
    )
    mutations["corner_semantics_tamper"] = (
        corner_tampered,
        ("corner_order_exact_LOW_NOMINAL_HIGH", "corner_semantics_exact"),
    )

    excitation_promoted = copy.deepcopy(document)
    excitation_promoted["prescribed_excitation"]["authority"] = (
        "COMMAND_AND_HARDWARE_ENVELOPE"
    )
    mutations["excitation_authority_promotion"] = (
        excitation_promoted,
        (
            "full_parsed_contract_canonical_sha256_exact",
            "prescribed_excitation_authority_exact",
        ),
    )

    solver_relaxed = copy.deepcopy(document)
    solver_relaxed["solvers"]["rtol"] = 1.0e-6
    solver_relaxed["solvers"]["max_step_s"] = 5.0e-3
    mutations["solver_tolerance_and_step_relaxation"] = (
        solver_relaxed,
        (
            "full_parsed_contract_canonical_sha256_exact",
            "solver_tolerances_and_steps_exact",
        ),
    )

    guard_key_removed = copy.deepcopy(document)
    del guard_key_removed["execution_guards"]["hardware_authority_claimed"]
    mutations["execution_guard_key_removal"] = (
        guard_key_removed,
        (
            "full_parsed_contract_canonical_sha256_exact",
            "execution_guard_keys_and_false_values_exact",
        ),
    )

    frozen_q0_tampered = copy.deepcopy(document)
    frozen_q0_tampered["frozen_linearization"]["q0_mixed_rad_m"][0] += 1.0e-4
    mutations["frozen_q0_tamper"] = (
        frozen_q0_tampered,
        (
            "full_parsed_contract_canonical_sha256_exact",
            "frozen_q0_exact",
        ),
    )

    controls: dict[str, Any] = {}
    for name, (mutated, expected_failed_checks) in mutations.items():
        audit = validate_contract_semantics(mutated)
        controls[name] = {
            "rejected": not audit["pass"],
            "expected_checks_failed": all(
                audit["checks"][check] is False for check in expected_failed_checks
            ),
            "validator_failed_checks": audit["failed"],
        }
    return {
        "schema": "DG3_CONTRACT_TAMPER_NEGATIVE_CONTROLS_V1",
        "controls": controls,
        "all_rejected": all(
            row["rejected"] and row["expected_checks_failed"]
            for row in controls.values()
        ),
    }


def load_contract() -> dict[str, Any]:
    document = load_json(CONTRACT_PATH)
    audit = validate_contract_semantics(document)
    if not audit["pass"]:
        raise DG3Error("CONTRACT_SEMANTICS_MISMATCH:" + ",".join(audit["failed"]))
    return document


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            jsonable(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest().upper()


def jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _vector(values: Sequence[float], size: int, field: str) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.shape != (size,) or not np.all(np.isfinite(result)):
        raise DG3Error(f"{field}_MUST_HAVE_{size}_FINITE_VALUES")
    return result


def validate_source_pins(contract: Mapping[str, Any]) -> dict[str, Any]:
    rows = []
    for source_id, pin in contract["source_pins"].items():
        path = ROOT / pin["path"]
        exists = path.is_file()
        actual_bytes = path.stat().st_size if exists else None
        actual_sha = sha256(path) if exists else None
        match = bool(
            exists
            and actual_bytes == int(pin["bytes"])
            and actual_sha == str(pin["sha256"]).upper()
        )
        rows.append(
            {
                "id": source_id,
                "path": pin["path"],
                "expected_bytes": int(pin["bytes"]),
                "actual_bytes": actual_bytes,
                "expected_sha256": str(pin["sha256"]).upper(),
                "actual_sha256": actual_sha,
                "match": match,
            }
        )
    return {
        "pins": rows,
        "matched": sum(bool(row["match"]) for row in rows),
        "total": len(rows),
        "all_match": all(bool(row["match"]) for row in rows),
    }


def _pin_path(contract: Mapping[str, Any], source_id: str) -> Path:
    return ROOT / contract["source_pins"][source_id]["path"]


def _skew(vector: Sequence[float]) -> np.ndarray:
    x, y, z = _vector(vector, 3, "SKEW_VECTOR")
    return np.array(((0.0, -z, y), (z, 0.0, -x), (-y, x, 0.0)))


def _inertia_from_components(values: Mapping[str, float]) -> np.ndarray:
    return np.array(
        (
            (values["Ixx"], values["Ixy"], values["Ixz"]),
            (values["Ixy"], values["Iyy"], values["Iyz"]),
            (values["Ixz"], values["Iyz"], values["Izz"]),
        ),
        dtype=float,
    )


def _spatial_inertia(mass: float, cg: np.ndarray, inertia_cg: np.ndarray) -> np.ndarray:
    cross = _skew(cg)
    return np.block(
        [
            [mass * np.eye(3), -mass * cross],
            [
                mass * cross,
                inertia_cg
                + mass * ((cg @ cg) * np.eye(3) - np.outer(cg, cg)),
            ],
        ]
    )


def _c07_spatial_inertia(contract: Mapping[str, Any]) -> np.ndarray:
    ledger = yaml.safe_load(_pin_path(contract, "r2_mass_ledger").read_text(encoding="utf-8"))
    row = next(
        item
        for item in ledger["configurations"]
        if item["configuration_id"] == "C07"
    )
    mass = float(row["mass"]["value_kg"])
    cg = np.asarray(row["center_of_mass"]["xyz_m"], dtype=float)
    inertia = _inertia_from_components(row["inertia"]["components_kg_m2"])
    return _spatial_inertia(mass, cg, inertia)


def _joint_limits(backend: Any) -> np.ndarray:
    root = ET.fromstring(backend.urdf_bytes)
    rows = []
    for joint in root.findall("joint"):
        if joint.attrib.get("type") not in {"revolute", "prismatic"}:
            continue
        limit = joint.find("limit")
        if limit is None:
            raise DG3Error("MOVABLE_JOINT_LIMIT_MISSING")
        rows.append((float(limit.attrib["lower"]), float(limit.attrib["upper"])))
    limits = np.asarray(rows, dtype=float)
    if limits.shape != (8, 2):
        raise DG3Error("MOVABLE_JOINT_LIMIT_SHAPE_MISMATCH")
    return limits


def _numbers(text: str | None, size: int, field: str) -> np.ndarray:
    if text is None:
        return np.zeros(size)
    return _vector([float(value) for value in text.split()], size, field)


def _rpy_rotation(rpy: Sequence[float]) -> np.ndarray:
    roll, pitch, yaw = _vector(rpy, 3, "RPY")
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = np.array(((1.0, 0.0, 0.0), (0.0, cr, -sr), (0.0, sr, cr)))
    ry = np.array(((cp, 0.0, sp), (0.0, 1.0, 0.0), (-sp, 0.0, cp)))
    rz = np.array(((cy, -sy, 0.0), (sy, cy, 0.0), (0.0, 0.0, 1.0)))
    return rz @ ry @ rx


def _origin_transform(origin: ET.Element | None) -> np.ndarray:
    transform = np.eye(4)
    if origin is None:
        return transform
    transform[:3, :3] = _rpy_rotation(_numbers(origin.attrib.get("rpy"), 3, "ORIGIN_RPY"))
    transform[:3, 3] = _numbers(origin.attrib.get("xyz"), 3, "ORIGIN_XYZ")
    return transform


def _urdf_absolute_transforms(root: ET.Element) -> tuple[str, dict[str, np.ndarray]]:
    links = {node.attrib["name"] for node in root.findall("link")}
    children: dict[str, list[tuple[str, np.ndarray]]] = {name: [] for name in links}
    child_links: set[str] = set()
    for joint in root.findall("joint"):
        parent_node = joint.find("parent")
        child_node = joint.find("child")
        if parent_node is None or child_node is None:
            raise DG3Error("URDF_JOINT_PARENT_CHILD_MISSING")
        parent = parent_node.attrib["link"]
        child = child_node.attrib["link"]
        if parent not in links or child not in links or child in child_links:
            raise DG3Error("URDF_TREE_INVALID")
        child_links.add(child)
        children[parent].append((child, _origin_transform(joint.find("origin"))))
    roots = sorted(links - child_links)
    if len(roots) != 1:
        raise DG3Error("URDF_ROOT_COUNT_NOT_ONE")
    root_name = roots[0]
    transforms = {root_name: np.eye(4)}
    stack = [root_name]
    while stack:
        parent = stack.pop()
        for child, relative in children[parent]:
            transforms[child] = transforms[parent] @ relative
            stack.append(child)
    if set(transforms) != links:
        raise DG3Error("URDF_TREE_DISCONNECTED")
    return root_name, transforms


def _matrix_max_abs(left: np.ndarray, right: np.ndarray) -> float:
    if left.shape != right.shape:
        return float("inf")
    return float(np.max(np.abs(left - right)))


def audit_rom_structure(
    contract: Mapping[str, Any],
    rom: Mapping[str, np.ndarray],
    rom_document: Mapping[str, Any],
) -> dict[str, Any]:
    threshold = contract["thresholds"]
    structure = contract["rom_structure_contract"]
    phi = np.asarray(rom["Phi_rom"], dtype=float)
    mrom = np.asarray(rom["Mrom"], dtype=float)
    identity_residual = _matrix_max_abs(mrom, np.eye(7))
    phi_json_residual = _matrix_max_abs(
        phi, np.asarray(rom_document["Phi_mass_normalized"], dtype=float)
    )
    per_side: dict[str, Any] = {}
    translation_active = np.zeros((7, 3), dtype=bool)
    rotation_active = np.zeros((7, 3), dtype=bool)
    for row, column in structure["translation_structural_nonzero"]:
        translation_active[int(row), int(column)] = True
    for row, column in structure["rotation_structural_nonzero"]:
        rotation_active[int(row), int(column)] = True
    for long_side, short_side in (("LEFT", "L"), ("RIGHT", "R")):
        gamma_t = np.asarray(rom[f"Gamma_t_{short_side}"], dtype=float)
        gamma_r = np.asarray(rom[f"Gamma_r_{short_side}"], dtype=float)
        bt = np.asarray(rom[f"Bt_{short_side}"], dtype=float)
        br = np.asarray(rom[f"Br_{short_side}"], dtype=float)
        json_side = rom_document["base_participation"][long_side]
        json_hf = rom_document["HF_base_participation_matrices"][long_side]
        per_side[long_side] = {
            "Gamma_t_minus_PhiT_Bt_max_abs": _matrix_max_abs(gamma_t, phi.T @ bt),
            "Gamma_r_minus_PhiT_Br_max_abs": _matrix_max_abs(gamma_r, phi.T @ br),
            "Gamma_t_npz_vs_json_max_abs": _matrix_max_abs(
                gamma_t, np.asarray(json_side["Gamma_t"], dtype=float)
            ),
            "Gamma_r_npz_vs_json_max_abs": _matrix_max_abs(
                gamma_r, np.asarray(json_side["Gamma_r"], dtype=float)
            ),
            "Bt_npz_vs_json_max_abs": _matrix_max_abs(
                bt, np.asarray(json_hf["B_t"], dtype=float)
            ),
            "Br_npz_vs_json_max_abs": _matrix_max_abs(
                br, np.asarray(json_hf["B_r"], dtype=float)
            ),
            "translation_structural_zero_max_abs": float(
                np.max(np.abs(gamma_t[~translation_active]))
            ),
            "rotation_structural_zero_max_abs": float(
                np.max(np.abs(gamma_r[~rotation_active]))
            ),
            "translation_active_min_abs": float(
                np.min(np.abs(gamma_t[translation_active]))
            ),
            "rotation_active_min_abs": float(
                np.min(np.abs(gamma_r[rotation_active]))
            ),
        }
    gamma_mirror = {
        "Gamma_t_LEFT_minus_RIGHT_max_abs": _matrix_max_abs(
            np.asarray(rom["Gamma_t_L"]), np.asarray(rom["Gamma_t_R"])
        ),
        "Gamma_r_LEFT_plus_RIGHT_max_abs": float(
            np.max(np.abs(np.asarray(rom["Gamma_r_L"]) + np.asarray(rom["Gamma_r_R"])))
        ),
        "Bt_LEFT_minus_RIGHT_max_abs": _matrix_max_abs(
            np.asarray(rom["Bt_L"]), np.asarray(rom["Bt_R"])
        ),
        "Br_LEFT_plus_RIGHT_max_abs": float(
            np.max(np.abs(np.asarray(rom["Br_L"]) + np.asarray(rom["Br_R"])))
        ),
    }
    checks = {
        "mode_order_exact": rom_document["mode_labels"] == structure["mode_labels"]
        and rom_document["hf_mode_indices_1based"] == structure["hf_mode_indices_1based"],
        "Phi_and_Mrom_npz_json_exact": phi_json_residual == 0.0
        and _matrix_max_abs(mrom, np.asarray(rom_document["Mrom"], dtype=float)) == 0.0,
        "Mrom_mass_normalized_identity": identity_residual
        <= threshold["mrom_identity_max_abs"],
        "Gamma_equals_PhiT_B_all_sides": all(
            max(
                row["Gamma_t_minus_PhiT_Bt_max_abs"],
                row["Gamma_r_minus_PhiT_Br_max_abs"],
                row["Gamma_t_npz_vs_json_max_abs"],
                row["Gamma_r_npz_vs_json_max_abs"],
                row["Bt_npz_vs_json_max_abs"],
                row["Br_npz_vs_json_max_abs"],
            )
            <= threshold["gamma_phi_t_B_max_abs"]
            for row in per_side.values()
        ),
        "left_right_mirror_exact": max(gamma_mirror.values())
        <= threshold["gamma_mirror_max_abs"],
        "structural_zeros_and_active_entries_exact": all(
            max(
                row["translation_structural_zero_max_abs"],
                row["rotation_structural_zero_max_abs"],
            )
            <= threshold["gamma_structural_zero_max_abs"]
            and min(row["translation_active_min_abs"], row["rotation_active_min_abs"])
            > 0.0
            for row in per_side.values()
        ),
        "reconstruction_contract_exact": rom_document["reconstruction_contract"][
            "base_coupling"
        ]
        == structure["gamma_identity"]
        == "Gamma_t=Phi^T B_t; Gamma_r=Phi^T B_r",
    }
    return {
        "schema": "DG3_ROM_STRUCTURE_AUDIT_V1",
        "mode_labels": rom_document["mode_labels"],
        "hf_mode_indices_1based": rom_document["hf_mode_indices_1based"],
        "Mrom_minus_identity_max_abs": identity_residual,
        "Phi_npz_vs_json_max_abs": phi_json_residual,
        "per_side": per_side,
        "mirror": gamma_mirror,
        "checks": checks,
        "pass": all(checks.values()),
    }


def _ledger_configuration(ledger: Mapping[str, Any], configuration_id: str) -> Mapping[str, Any]:
    rows = [
        row
        for row in ledger["configurations"]
        if row.get("configuration_id") == configuration_id
    ]
    if len(rows) != 1:
        raise DG3Error(f"MASS_LEDGER_{configuration_id}_COUNT_NOT_ONE")
    return rows[0]


def audit_unified_urdf_and_frames(
    contract: Mapping[str, Any],
    backend: Any,
    q0: np.ndarray,
    nominal_model: Mapping[str, Any],
    mass_ledger: Mapping[str, Any],
    envelope: Mapping[str, Any],
    frame_tree: Mapping[str, Any],
    frame_bridge: Mapping[str, Any],
    e23_source_text: str,
) -> dict[str, Any]:
    threshold = contract["thresholds"]
    handshake = contract["frame_handshake"]
    root = ET.fromstring(_pin_path(contract, "unified_r2_urdf").read_bytes())
    root_link, transforms = _urdf_absolute_transforms(root)
    masses: dict[str, float] = {}
    for link in root.findall("link"):
        inertial = link.find("inertial")
        if inertial is None:
            continue
        mass_node = inertial.find("mass")
        if mass_node is None:
            raise DG3Error("URDF_INERTIAL_MASS_MISSING")
        masses[link.attrib["name"]] = float(mass_node.attrib["value"])
    left_name = handshake["left_wing_link"]
    right_name = handshake["right_wing_link"]
    left_mass = masses[left_name]
    right_mass = masses[right_name]
    solar_total = left_mass + right_mass
    urdf_total = math.fsum(masses.values())
    c01 = _ledger_configuration(mass_ledger, "C01")
    ledger_total = float(c01["mass"]["value_kg"])
    ledger_solar_rows = [
        row
        for row in c01["composition"]
        if row["component_id"] in {"solar_array_r2_left", "solar_array_r2_right"}
    ]
    ledger_solar_total = math.fsum(float(row["mass_kg"]) for row in ledger_solar_rows)
    backend_rigid = np.asarray(backend.tree.mass_matrix(q0), dtype=float)
    left_transform = transforms[left_name]
    right_transform = transforms[right_name]
    base_transform = transforms["base_link"]
    canonical = frame_tree["canonical_absolute_frames_in_spacecraft_bus_S"]
    frame_left = np.asarray(canonical["SOLAR_R2_ROOT_L"]["T_S_frame"], dtype=float)
    frame_right = np.asarray(canonical["SOLAR_R2_ROOT_R"]["T_S_frame"], dtype=float)
    frame_base = np.asarray(canonical["B601_BASE_PHYSICAL"]["T_S_frame"], dtype=float)
    bridge_dynamic = np.asarray(
        frame_bridge["frame_semantics"]["T_S_A0_dynamics"]["transform_S_A0_rows_m"],
        dtype=float,
    )
    bridge_physical = np.asarray(
        frame_bridge["frame_semantics"]["T_S_A0_physical"]["transform_S_A0_rows_m"],
        dtype=float,
    )
    physical_to_dynamic = np.linalg.solve(bridge_dynamic, base_transform)
    clocking_deg = math.degrees(
        math.atan2(physical_to_dynamic[1, 0], physical_to_dynamic[0, 0])
    )
    c07 = _c07_spatial_inertia(contract)
    urdf_hbb = backend_rigid[:6, :6]
    hbb_relative = float(np.linalg.norm(urdf_hbb - c07) / np.linalg.norm(c07))
    wrong_total = urdf_total + solar_total
    full_rigid_block_residual = _matrix_max_abs(
        np.asarray(nominal_model["mass"][:14, :14]), backend_rigid
    )
    solar_mass_audit = {
        "left_link": left_name,
        "left_mass_kg": left_mass,
        "right_link": right_name,
        "right_mass_kg": right_mass,
        "solar_total_mass_kg": solar_total,
        "urdf_all_physical_link_mass_kg": urdf_total,
        "mass_ledger_C01_total_kg": ledger_total,
        "mass_ledger_solar_total_kg": ledger_solar_total,
        "backend_translational_diagonal_kg": np.diag(backend_rigid[:3, :3]).tolist(),
        "full_28x28_rigid_block_vs_backend_max_abs": full_rigid_block_residual,
        "modal_mass_semantics": "RELATIVE_MASS_NORMALIZED_COORDINATE_BLOCK__NO_RIGID_MASS_ADDITION",
        "negative_control": {
            "injected_operation": "ADD_ALREADY_INCLUDED_LEFT_AND_RIGHT_0P78KG_WINGS_AGAIN",
            "wrong_total_mass_kg": wrong_total,
            "detected_excess_kg": wrong_total - ledger_total,
            "detected": wrong_total - ledger_total
            >= threshold["double_count_excess_min_kg"],
        },
    }
    frame_audit = {
        "S_root_link": root_link,
        "frame_tree_S_root_link": canonical["S_SPACECRAFT_BUS"]["link"],
        "left_root_parsed_T_S": left_transform,
        "right_root_parsed_T_S": right_transform,
        "B601_base_parsed_T_S": base_transform,
        "left_root_vs_frame_tree_max_abs": _matrix_max_abs(left_transform, frame_left),
        "right_root_vs_frame_tree_max_abs": _matrix_max_abs(right_transform, frame_right),
        "B601_base_vs_frame_tree_max_abs": _matrix_max_abs(base_transform, frame_base),
        "B601_base_vs_bridge_physical_max_abs": _matrix_max_abs(
            base_transform, bridge_physical
        ),
        "ROM_root_y_abs_m": float(envelope["geometry"]["root_y_abs_m"]),
        "ROM_root_z_m": float(envelope["geometry"]["root_z_m"]),
    }
    representation = {
        "Unified_current_B601_base_x_S_m": float(base_transform[0, 3]),
        "Unified_current_clocking_deg": clocking_deg,
        "E23_legacy_B601_base_x_S_m": float(bridge_dynamic[0, 3]),
        "E23_legacy_clocking_deg": 0.0,
        "bridge_translation_in_A0_dynamics_m": physical_to_dynamic[:3, 3],
        "Hbb_max_abs_difference": float(np.max(np.abs(urdf_hbb - c07))),
        "Hbb_relative_frobenius_difference": hbb_relative,
        "root_cause": "E23_C07_USES_LEGACY_X_0P18525_NO_CLOCKING__UNIFIED_USES_PHYSICAL_X_0P208_PLUS_25P000014_DEG",
        "E23_numerical_inheritance": False,
        "disposition": "REPRESENTATION_MISMATCH_ROOT_CAUSE_BOUND__E23_NUMERICAL_VALUES_NOT_INHERITED",
    }
    e23_lookup = (
        'bridge["frame_semantics"]["T_S_A0_dynamics"]['
        '"transform_S_A0_rows_m"]'
    )
    checks = {
        "URDF_tree_is_19_link_18_joint_rooted_in_S": len(root.findall("link")) == 19
        and len(root.findall("joint")) == 18
        and root_link == handshake["S_root_link"]
        and canonical["S_SPACECRAFT_BUS"]["link"] == handshake["S_root_link"],
        "wing_roots_match_ROM_and_frame_tree": max(
            frame_audit["left_root_vs_frame_tree_max_abs"],
            frame_audit["right_root_vs_frame_tree_max_abs"],
            abs(abs(float(left_transform[1, 3])) - float(envelope["geometry"]["root_y_abs_m"])),
            abs(abs(float(right_transform[1, 3])) - float(envelope["geometry"]["root_y_abs_m"])),
            abs(float(left_transform[2, 3]) - float(envelope["geometry"]["root_z_m"])),
            abs(float(right_transform[2, 3]) - float(envelope["geometry"]["root_z_m"])),
        )
        <= threshold["frame_transform_max_abs"],
        "B601_current_physical_frame_handshake": max(
            frame_audit["B601_base_vs_frame_tree_max_abs"],
            frame_audit["B601_base_vs_bridge_physical_max_abs"],
            abs(float(base_transform[0, 3]) - handshake["current_B601_base_x_S_m"]),
            abs(clocking_deg - handshake["current_B601_clocking_deg"]),
        )
        <= max(threshold["frame_transform_max_abs"], 1.0e-9),
        "URDF_wings_each_0p78_and_total_mass_reclosed": len(ledger_solar_rows) == 2
        and left_mass == 0.78
        and right_mass == 0.78
        and abs(solar_total - 1.56) <= threshold["mass_reclosure_max_kg"]
        and abs(ledger_solar_total - 1.56) <= threshold["mass_reclosure_max_kg"]
        and abs(urdf_total - ledger_total) <= threshold["mass_reclosure_max_kg"]
        and max(abs(float(value) - ledger_total) for value in np.diag(backend_rigid[:3, :3]))
        <= threshold["mass_reclosure_max_kg"],
        "no_rigid_wing_mass_added_with_modal_coordinates": full_rigid_block_residual
        <= threshold["mass_reclosure_max_kg"],
        "double_count_negative_control_detected": solar_mass_audit["negative_control"]["detected"]
        and abs(solar_mass_audit["negative_control"]["detected_excess_kg"] - 1.56)
        <= threshold["mass_reclosure_max_kg"],
        "E23_legacy_transform_use_machine_bound": e23_lookup in e23_source_text
        and abs(float(bridge_dynamic[0, 3]) - handshake["legacy_E23_B601_base_x_S_m"])
        <= threshold["frame_transform_max_abs"]
        and handshake["legacy_E23_clocking_deg"] == 0.0,
        "E23_Hbb_mismatch_replayed_and_inheritance_denied": abs(
            hbb_relative - threshold["E23_Hbb_relative_difference_expected"]
        )
        <= threshold["E23_Hbb_relative_difference_replay_abs_max"]
        and handshake["E23_numerical_inheritance"] is False
        and representation["E23_numerical_inheritance"] is False,
    }
    return {
        "schema": "DG3_UNIFIED_URDF_MASS_AND_FRAME_AUDIT_V1",
        "solar_mass_audit": solar_mass_audit,
        "frame_handshake_audit": frame_audit,
        "representation_compatibility_audit": representation,
        "checks": checks,
        "pass": all(checks.values()),
    }


def cholesky_positive_definite_structure(
    matrix: np.ndarray, label: str
) -> dict[str, Any]:
    """Return structural booleans only; never emit mixed-unit spectral scalars."""
    array = np.asarray(matrix, dtype=float)
    square = array.ndim == 2 and array.shape[0] == array.shape[1]
    finite = bool(square and np.all(np.isfinite(array)))
    symmetric = bool(
        finite
        and np.max(np.abs(array - array.T))
        <= 1.0e-12
    )
    cholesky_succeeded = False
    if symmetric:
        try:
            np.linalg.cholesky(array)
            cholesky_succeeded = True
        except np.linalg.LinAlgError:
            cholesky_succeeded = False
    return {
        "label": label,
        "shape": list(array.shape),
        "square": square,
        "finite": finite,
        "symmetric_within_frozen_numeric_tolerance": symmetric,
        "cholesky_factorization_succeeded": cholesky_succeeded,
        "positive_definite": bool(
            square and finite and symmetric and cholesky_succeeded
        ),
        "method": "CHOLESKY_BOOLEAN_STRUCTURE_ONLY",
        "eigenvalue_or_condition_number_emitted": False,
        "spectral_numeric_credit": False,
    }


def _require_positive_definite_structures(
    structures: Mapping[str, Mapping[str, Any]], lane: str
) -> None:
    failed = [
        name
        for name, audit in structures.items()
        if audit.get("positive_definite") is not True
    ]
    if failed:
        raise DG3Error(
            f"MASS_MATRIX_NOT_CHOLESKY_POSITIVE_DEFINITE:{lane}:"
            + ",".join(failed)
        )


def assemble_model(
    backend: Any,
    rom: Mapping[str, np.ndarray],
    q0: np.ndarray,
    corner: str,
    coupling_scale: float = 1.0,
    damping_scale: float = 1.0,
) -> dict[str, Any]:
    rigid = np.asarray(backend.tree.mass_matrix(q0), dtype=float)
    base_modal = np.block(
        [
            [rom["Gamma_t_L"].T, rom["Gamma_t_R"].T],
            [rom["Gamma_r_L"].T, rom["Gamma_r_R"].T],
        ]
    )
    full_coupling = np.vstack((base_modal, np.zeros((8, 14)))) * float(coupling_scale)
    modal_mass = block_diag(rom["Mrom"], rom["Mrom"])
    stiffness = block_diag(rom[f"Krom_{corner}"], rom[f"Krom_{corner}"])
    damping = (
        block_diag(rom[f"Crom_{corner}"], rom[f"Crom_{corner}"])
        * float(damping_scale)
    )
    mass = np.block([[rigid, full_coupling], [full_coupling.T, modal_mass]])
    unknown = np.r_[np.arange(6), np.arange(14, 28)]
    prescribed = np.arange(6, 14)
    muu = mass[np.ix_(unknown, unknown)]
    mass_matrix_structure = {
        "rigid_14x14": cholesky_positive_definite_structure(
            rigid, "RIGID_BASE_PLUS_JOINT_14X14"
        ),
        "base_Hbb_6x6": cholesky_positive_definite_structure(
            rigid[:6, :6], "BASE_HBB_6X6"
        ),
        "modal_14x14": cholesky_positive_definite_structure(
            modal_mass, "DUAL_WING_MODAL_MASS_14X14"
        ),
        "full_28x28": cholesky_positive_definite_structure(
            mass, "FULL_RIGID_MODAL_MASS_28X28"
        ),
        "unknown_Muu_20x20": cholesky_positive_definite_structure(
            muu, "SOLVED_UNKNOWN_MASS_MUU_20X20"
        ),
    }
    return {
        "mass": mass,
        "rigid_mass": rigid,
        "base_modal": base_modal * float(coupling_scale),
        "joint_modal": np.zeros((8, 14)),
        "modal_mass": modal_mass,
        "stiffness": stiffness,
        "damping": damping,
        "unknown_indices": unknown,
        "prescribed_indices": prescribed,
        "Muu": muu,
        "Mup": mass[np.ix_(unknown, prescribed)],
        "mass_matrix_structure": mass_matrix_structure,
        "all_mass_matrices_cholesky_positive_definite": all(
            audit["positive_definite"]
            for audit in mass_matrix_structure.values()
        ),
        "corner": corner,
        "coupling_scale": float(coupling_scale),
        "damping_scale": float(damping_scale),
    }


def joint_motion(
    time_s: float, q0: np.ndarray, amplitude: np.ndarray, frequency_hz: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    omega = 2.0 * math.pi * frequency_hz
    phase = omega * time_s
    return (
        q0 + amplitude * (1.0 - math.cos(phase)),
        amplitude * omega * math.sin(phase),
        amplitude * omega * omega * math.cos(phase),
    )


def _rhs(
    model: Mapping[str, Any],
    q0: np.ndarray,
    amplitude: np.ndarray,
    frequency_hz: float,
):
    mass = model["mass"]
    stiffness = model["stiffness"]
    damping = model["damping"]
    Muu = model["Muu"]
    Mup = model["Mup"]

    def rhs(time_s: float, state: np.ndarray) -> np.ndarray:
        base_displacement = state[:6]
        del base_displacement
        base_rate = state[6:12]
        eta = state[12:26]
        eta_rate = state[26:40]
        _q, qdot, qddot = joint_motion(time_s, q0, amplitude, frequency_hz)
        restoring = np.r_[np.zeros(6), stiffness @ eta + damping @ eta_rate]
        unknown_acceleration = np.linalg.solve(
            Muu, -Mup @ qddot - restoring
        )
        base_acceleration = unknown_acceleration[:6]
        eta_acceleration = unknown_acceleration[6:]
        full_acceleration = np.r_[base_acceleration, qddot, eta_acceleration]
        joint_effort = (mass @ full_acceleration)[6:14]
        actuator_power = float(joint_effort @ qdot)
        damping_power = float(eta_rate @ (damping @ eta_rate))
        return np.r_[
            base_rate,
            base_acceleration,
            eta_rate,
            eta_acceleration,
            actuator_power,
            damping_power,
        ]

    return rhs


def _relative_norm(left: np.ndarray, right: np.ndarray, floor: float = 1.0e-30) -> float:
    return float(
        np.linalg.norm(left - right)
        / max(np.linalg.norm(left), np.linalg.norm(right), floor)
    )


def solve_case(
    model: Mapping[str, Any],
    q0: np.ndarray,
    amplitude: np.ndarray,
    excitation: Mapping[str, Any],
    solver: Mapping[str, Any],
    method: str,
    initial_state: np.ndarray | None = None,
) -> dict[str, Any]:
    _require_positive_definite_structures(
        model["mass_matrix_structure"], f"SOLVE_CASE_{method}"
    )
    duration = float(excitation["duration_s"])
    samples = int(excitation["samples"])
    times = np.linspace(0.0, duration, samples)
    initial = np.zeros(42) if initial_state is None else np.asarray(initial_state, dtype=float)
    if initial.shape != (42,) or not np.all(np.isfinite(initial)):
        raise DG3Error("INITIAL_STATE_MUST_HAVE_42_FINITE_VALUES")
    solution = solve_ivp(
        _rhs(model, q0, amplitude, float(excitation["frequency_hz"])),
        (0.0, duration),
        initial,
        method=method,
        t_eval=times,
        rtol=float(solver["rtol"]),
        atol=float(solver["atol"]),
        max_step=float(solver["max_step_s"]),
    )
    if not solution.success or solution.y.shape != (42, samples):
        raise DG3Error(f"SOLVER_FAILED:{method}:{solution.message}")
    history = solution.y.T
    energies = []
    modal_energies = []
    canonical_base_momenta = []
    for index, time_s in enumerate(times):
        _q, qdot, _qddot = joint_motion(
            float(time_s), q0, amplitude, float(excitation["frequency_hz"])
        )
        base_rate = history[index, 6:12]
        eta = history[index, 12:26]
        eta_rate = history[index, 26:40]
        velocity = np.r_[base_rate, qdot, eta_rate]
        canonical_base_momenta.append((model["mass"] @ velocity)[:6])
        kinetic = 0.5 * velocity @ (model["mass"] @ velocity)
        potential = 0.5 * eta @ (model["stiffness"] @ eta)
        modal_kinetic = 0.5 * eta_rate @ (model["modal_mass"] @ eta_rate)
        energies.append(float(kinetic + potential))
        modal_energies.append(float(modal_kinetic + potential))
    energy = np.asarray(energies)
    modal_energy = np.asarray(modal_energies)
    canonical_base_momentum = np.asarray(canonical_base_momenta)
    momentum_residual = canonical_base_momentum - canonical_base_momentum[0]
    work = history[:, 40]
    dissipation = history[:, 41]
    balance = energy - energy[0] - work + dissipation
    scale = max(
        float(np.max(np.abs(energy))),
        float(np.max(np.abs(work))),
        float(np.max(np.abs(dissipation))),
        1.0e-30,
    )
    conservative_scale = max(float(np.max(np.abs(energy))), abs(float(energy[0])), 1.0e-30)
    return {
        "method": method,
        "nfev": int(solution.nfev),
        "time_s": times,
        "history": history,
        "energy_J": energy,
        "modal_energy_J": modal_energy,
        "metrics": {
            "base_translation_tangent_peak_m": float(
                np.max(np.abs(history[:, :3]))
            ),
            "base_rotation_tangent_peak_rad": float(
                np.max(np.abs(history[:, 3:6]))
            ),
            "base_linear_rate_peak_m_s": float(
                np.max(np.abs(history[:, 6:9]))
            ),
            "base_angular_rate_peak_rad_s": float(
                np.max(np.abs(history[:, 9:12]))
            ),
            "eta_peak_modal_coordinate": float(
                np.max(np.abs(history[:, 12:26]))
            ),
            "eta_rate_peak_modal_coordinate_s": float(
                np.max(np.abs(history[:, 26:40]))
            ),
            "modal_energy_peak_J": float(np.max(modal_energy)),
            "modal_energy_final_J": float(modal_energy[-1]),
            "actuator_work_final_J": float(work[-1]),
            "damping_dissipation_final_J": float(dissipation[-1]),
            "energy_final_J": float(energy[-1]),
            "energy_work_dissipation_balance_absolute_peak_J": float(
                np.max(np.abs(balance))
            ),
            "energy_work_dissipation_balance_relative_peak": float(
                np.max(np.abs(balance)) / scale
            ),
            "total_energy_conservation_absolute_peak_J": float(
                np.max(np.abs(energy - energy[0]))
            ),
            "total_energy_conservation_relative_peak": float(
                np.max(np.abs(energy - energy[0])) / conservative_scale
            ),
            "canonical_base_linear_momentum_residual_max_kg_m_s": float(
                np.max(np.abs(momentum_residual[:, :3]))
            ),
            "canonical_base_angular_momentum_residual_max_kg_m2_s": float(
                np.max(np.abs(momentum_residual[:, 3:]))
            ),
            "canonical_base_momentum_initial": canonical_base_momentum[0],
            "canonical_base_momentum_final": canonical_base_momentum[-1],
        },
    }


def conservative_initial_state(
    model: Mapping[str, Any], eta: np.ndarray, eta_rate: np.ndarray
) -> np.ndarray:
    _require_positive_definite_structures(
        {
            "base_Hbb_6x6": model["mass_matrix_structure"]["base_Hbb_6x6"],
            "full_28x28": model["mass_matrix_structure"]["full_28x28"],
        },
        "CONSERVATIVE_INITIAL_STATE",
    )
    eta = _vector(eta, 14, "CONSERVATIVE_ETA")
    eta_rate = _vector(eta_rate, 14, "CONSERVATIVE_ETA_RATE")
    initial = np.zeros(42)
    initial[12:26] = eta
    initial[26:40] = eta_rate
    initial[6:12] = -np.linalg.solve(
        np.asarray(model["mass"][:6, :6]),
        np.asarray(model["mass"][:6, 14:]) @ eta_rate,
    )
    return initial


def solve_modes_removed_rigid_case(
    rigid_mass: np.ndarray,
    q0: np.ndarray,
    amplitude: np.ndarray,
    excitation: Mapping[str, Any],
    solver: Mapping[str, Any],
    method: str,
) -> dict[str, Any]:
    rigid_mass = np.asarray(rigid_mass, dtype=float)
    if rigid_mass.shape != (14, 14):
        raise DG3Error("MODES_REMOVED_RIGID_MASS_MUST_BE_14X14")
    hbb = rigid_mass[:6, :6]
    hbj = rigid_mass[:6, 6:]
    mass_matrix_structure = {
        "rigid_14x14": cholesky_positive_definite_structure(
            rigid_mass, "MODES_REMOVED_RIGID_BASE_PLUS_JOINT_14X14"
        ),
        "base_Hbb_6x6": cholesky_positive_definite_structure(
            hbb, "MODES_REMOVED_BASE_HBB_6X6"
        ),
    }
    _require_positive_definite_structures(
        mass_matrix_structure, f"MODES_REMOVED_{method}"
    )
    duration = float(excitation["duration_s"])
    samples = int(excitation["samples"])
    frequency_hz = float(excitation["frequency_hz"])
    times = np.linspace(0.0, duration, samples)

    def rhs(time_s: float, state: np.ndarray) -> np.ndarray:
        _q, _qdot, qddot = joint_motion(time_s, q0, amplitude, frequency_hz)
        return np.r_[state[6:12], -np.linalg.solve(hbb, hbj @ qddot)]

    solution = solve_ivp(
        rhs,
        (0.0, duration),
        np.zeros(12),
        method=method,
        t_eval=times,
        rtol=float(solver["rtol"]),
        atol=float(solver["atol"]),
        max_step=float(solver["max_step_s"]),
    )
    if not solution.success or solution.y.shape != (12, samples):
        raise DG3Error(f"MODES_REMOVED_SOLVER_FAILED:{method}:{solution.message}")
    history = solution.y.T
    rigid_map = -np.linalg.solve(hbb, hbj)
    q_rows = []
    qdot_rows = []
    for time_s in times:
        q, qdot, _qddot = joint_motion(float(time_s), q0, amplitude, frequency_hz)
        q_rows.append(q)
        qdot_rows.append(qdot)
    q_history = np.asarray(q_rows)
    qdot_history = np.asarray(qdot_rows)
    expected_displacement = (rigid_map @ (q_history - q0).T).T
    expected_rate = (rigid_map @ qdot_history.T).T
    canonical = (hbb @ history[:, 6:12].T + hbj @ qdot_history.T).T
    canonical_residual = canonical - canonical[0]
    return {
        "method": method,
        "state_dimension": 12,
        "mass_matrix_shape": [14, 14],
        "modal_dof": 0,
        "lane_definition": "MODES_REMOVED_CONSTRAINED_RIGID__NO_MODAL_STATE_NO_K_NO_C_NO_GAMMA",
        "mass_matrix_structure": mass_matrix_structure,
        "all_mass_matrices_cholesky_positive_definite": all(
            audit["positive_definite"]
            for audit in mass_matrix_structure.values()
        ),
        "history": history,
        "metrics": {
            "analytic_base_position_max_abs_m": float(
                np.max(np.abs(history[:, :3] - expected_displacement[:, :3]))
            ),
            "analytic_base_attitude_max_abs_rad": float(
                np.max(np.abs(history[:, 3:6] - expected_displacement[:, 3:6]))
            ),
            "analytic_base_linear_rate_max_abs_m_s": float(
                np.max(np.abs(history[:, 6:9] - expected_rate[:, :3]))
            ),
            "analytic_base_angular_rate_max_abs_rad_s": float(
                np.max(np.abs(history[:, 9:12] - expected_rate[:, 3:6]))
            ),
            "canonical_base_linear_momentum_residual_max_kg_m_s": float(
                np.max(np.abs(canonical_residual[:, :3]))
            ),
            "canonical_base_angular_momentum_residual_max_kg_m2_s": float(
                np.max(np.abs(canonical_residual[:, 3:]))
            ),
        },
    }


def response_envelope(
    rom: Mapping[str, np.ndarray],
    envelope: Mapping[str, Any],
    eta_history: np.ndarray,
) -> dict[str, Any]:
    limits = envelope["quantitative_linearity_contract"]["limits"]
    definitions = {
        "transverse_node_displacement": (
            "R_w_nodes",
            "max_abs_transverse_node_displacement_m",
            "m",
        ),
        "bending_slope": (
            "R_theta_dofs",
            "max_abs_bending_slope_rad",
            "rad",
        ),
        "hinge_relative_rotation": (
            "R_hinge_relative",
            "max_abs_hinge_relative_rotation_rad",
            "rad",
        ),
        "torsion_angle": (
            "R_torsion_nodes",
            "max_abs_torsion_angle_rad",
            "rad",
        ),
        "tip_transverse_deflection": (
            "R_tip_w",
            "max_abs_tip_transverse_deflection_m",
            "m",
        ),
    }
    wings = {}
    for wing_index, wing_name in enumerate(("LEFT", "RIGHT")):
        eta = eta_history[:, wing_index * 7 : (wing_index + 1) * 7].T
        checks = {}
        for name, (operator_key, limit_key, unit) in definitions.items():
            peak = float(np.max(np.abs(rom[operator_key] @ eta)))
            limit = float(limits[limit_key])
            checks[name] = {
                "peak": peak,
                "limit": limit,
                "unit": unit,
                "margin": limit - peak,
                "pass": peak <= limit,
            }
        wings[wing_name] = {
            "checks": checks,
            "pass": all(row["pass"] for row in checks.values()),
        }
    return {
        "authority": envelope["quantitative_linearity_contract"]["authority"],
        "out_of_domain_policy": envelope["quantitative_linearity_contract"][
            "out_of_domain_policy"
        ],
        "wings": wings,
        "pass": all(row["pass"] for row in wings.values()),
    }
