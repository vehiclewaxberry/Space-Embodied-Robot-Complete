"""Fail-closed ASM-00 preflight, RF classifier, and success evaluator.

This module intentionally does not run interface physics or write an SSOT v1.
It classifies the current draft and freezes/validates the downstream evaluator
contract without treating that freeze as HAG-A approval.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml


EXPECTED_CRITERION_IDS = [
    "C01_FINAL_POSITION",
    "C02_FINAL_ORIENTATION",
    "C03_INSERTION_DEPTH",
    "C04_LATCH_GEOMETRY",
    "C05_CONTACT_LOAD",
    "C06_BASE_WHEEL_RESOURCES",
    "C07_FLEXIBLE_RESPONSE",
    "C08_PROVENANCE_AND_PHASE_LEDGER",
    "C09_CONTACT_HISTORY",
]

RAW_VERDICT_BLOCKED = "ASM00_AG0_BLOCKED_BY_INTERFACE"
RAW_VERDICT_REPEAT = "ASM00_AG0_REPEAT"
RAW_VERDICT_PASS_PROVISIONAL = "ASM00_AG0_PASS_WITH_PROVISIONAL_PARAMS"

EXTERNAL_STATUS_BLOCKED = "ASM00_BLOCKED_BY_MISSING_PARAMETERS"
EXTERNAL_STATUS_REPEAT = "ASM00_REPEAT_GEOMETRY"
EXTERNAL_STATUS_PASS_PROVISIONAL = (
    "ASM00_INTERFACE_QUALIFIED_WITH_PROVISIONAL_PARAMS"
)


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML mapping and reject any other root type."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write stable, human-readable JSON with no wall-clock fields."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_lf_normalized(path: Path) -> str:
    raw = path.read_bytes()
    normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return sha256_bytes(normalized)


def nested_get(data: Mapping[str, Any], dotted_path: str) -> Any:
    current: Any = data
    for token in dotted_path.split("."):
        if not isinstance(current, Mapping) or token not in current:
            return None
        current = current[token]
    return current


def unwrap_value(value: Any) -> Any:
    if isinstance(value, Mapping) and "value" in value:
        return value["value"]
    return value


def finite_float(value: Any, field: str) -> float:
    raw = unwrap_value(value)
    try:
        result = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a finite number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{field} must be a finite number")
    return result


def missing_fields(data: Mapping[str, Any], paths: list[str]) -> list[str]:
    return sorted(path for path in paths if nested_get(data, path) is None)


def _round(value: float) -> float:
    return round(value, 12)


def classify_rf1(
    ssot: Mapping[str, Any], required_fields: list[str]
) -> dict[str, Any]:
    """Classify the guide-cone capture-chain red flag from the draft."""
    missing = missing_fields(ssot, required_fields)
    angle_deg = finite_float(
        nested_get(ssot, "interface.guide_cone.half_angle_deg"),
        "guide_cone.half_angle_deg",
    )
    depth_mm = finite_float(
        nested_get(ssot, "interface.guide_cone.depth_mm"),
        "guide_cone.depth_mm",
    )
    coarse_mm = finite_float(
        nested_get(ssot, "interface.translational_tolerance_mm.coarse"),
        "translational_tolerance_mm.coarse",
    )
    fine_mm = finite_float(
        nested_get(ssot, "interface.translational_tolerance_mm.fine"),
        "translational_tolerance_mm.fine",
    )
    funnel_reduction_mm = depth_mm * math.tan(math.radians(angle_deg))
    required_reduction_mm = coarse_mm - fine_mm

    result: dict[str, Any] = {
        "rf_id": "RF-1",
        "status": "BLOCKED" if missing else "REPEAT",
        "reason_code": (
            "RF1_BLOCKED_MISSING_GUIDE_RADII"
            if missing
            else "RF1_REPEAT_CAPTURE_CHAIN_NOT_CLOSED"
        ),
        "missing_fields": missing,
        "inputs": {
            "coarse_tolerance_mm": coarse_mm,
            "fine_tolerance_mm": fine_mm,
            "guide_cone_depth_mm": depth_mm,
            "guide_cone_half_angle_deg": angle_deg,
        },
        "derived": {
            "nominal_funnel_reduction_mm": _round(funnel_reduction_mm),
            "required_coarse_to_fine_reduction_mm": _round(
                required_reduction_mm
            ),
            "nominal_funnel_alone_closes_chain": (
                funnel_reduction_mm >= required_reduction_mm
            ),
        },
        "negative_result_preserved": True,
    }
    if missing:
        return result

    throat_mm = finite_float(
        nested_get(ssot, "interface.guide_cone.throat_r_mm"),
        "guide_cone.throat_r_mm",
    )
    mouth_mm = finite_float(
        nested_get(ssot, "interface.guide_cone.mouth_r_mm"),
        "guide_cone.mouth_r_mm",
    )
    radial_span_mm = mouth_mm - throat_mm
    consistency_error_mm = abs(radial_span_mm - funnel_reduction_mm)
    geometry_consistent = consistency_error_mm <= 1.0e-9
    chain_closed = radial_span_mm >= required_reduction_mm
    result["inputs"].update(
        {"mouth_r_mm": mouth_mm, "throat_r_mm": throat_mm}
    )
    result["derived"].update(
        {
            "mouth_to_throat_radial_span_mm": _round(radial_span_mm),
            "cone_geometry_consistency_error_mm": _round(
                consistency_error_mm
            ),
            "cone_geometry_consistent": geometry_consistent,
            "capture_chain_closed": chain_closed,
        }
    )
    if geometry_consistent and chain_closed:
        result["status"] = "RESOLVED"
        result["reason_code"] = "RF1_RESOLVED_CAPTURE_CHAIN_CLOSED"
    return result


def classify_rf2(
    ssot: Mapping[str, Any], required_fields: list[str]
) -> dict[str, Any]:
    """Classify the wedge/friction red flag without treating depth as a fix."""
    missing = missing_fields(ssot, required_fields)
    angle_deg = finite_float(
        nested_get(ssot, "interface.guide_cone.half_angle_deg"),
        "guide_cone.half_angle_deg",
    )
    mu = finite_float(
        nested_get(ssot, "interface.friction_coulomb.value"),
        "friction_coulomb.value",
    )
    tan_alpha = math.tan(math.radians(angle_deg))
    nominal_margin = tan_alpha - mu

    citation_verified = nested_get(
        ssot, "interface.friction_coulomb.citation_verified"
    )
    invalid_provenance = (
        citation_verified is not None and citation_verified is not True
    )
    status = "BLOCKED" if missing or invalid_provenance else "REPEAT"
    reason = (
        "RF2_BLOCKED_MISSING_FRICTION_PROVENANCE_OR_MARGIN"
        if missing
        else (
            "RF2_BLOCKED_UNVERIFIED_FRICTION_CITATION"
            if invalid_provenance
            else "RF2_REPEAT_WEDGE_MARGIN_NOT_MET"
        )
    )
    result: dict[str, Any] = {
        "rf_id": "RF-2",
        "status": status,
        "reason_code": reason,
        "missing_fields": missing,
        "inputs": {
            "friction_coefficient": mu,
            "guide_cone_half_angle_deg": angle_deg,
        },
        "derived": {
            "tan_alpha": _round(tan_alpha),
            "nominal_tan_alpha_minus_mu": _round(nominal_margin),
            "nominal_sliding_condition_tan_alpha_ge_mu": tan_alpha >= mu,
            "guide_depth_can_resolve_wedge_condition": False,
        },
        "negative_result_preserved": True,
    }
    if missing or invalid_provenance:
        return result

    margin_factor = finite_float(
        nested_get(ssot, "interface.guide_cone.wedge_margin_factor"),
        "guide_cone.wedge_margin_factor",
    )
    required_tan_alpha = margin_factor * mu
    margin = tan_alpha - required_tan_alpha
    result["inputs"].update(
        {
            "citation_key": nested_get(
                ssot, "interface.friction_coulomb.citation_key"
            ),
            "citation_verified": citation_verified,
            "material_pair": nested_get(
                ssot, "interface.friction_coulomb.material_pair"
            ),
            "surface_finish": nested_get(
                ssot, "interface.friction_coulomb.surface_finish"
            ),
            "wedge_margin_factor": margin_factor,
        }
    )
    result["derived"].update(
        {
            "required_tan_alpha": _round(required_tan_alpha),
            "wedge_margin": _round(margin),
            "wedge_margin_met": margin >= 0.0,
        }
    )
    if margin >= 0.0:
        result["status"] = "RESOLVED"
        result["reason_code"] = "RF2_RESOLVED_WEDGE_MARGIN_MET"
    return result


def classify_rf3(
    ssot: Mapping[str, Any], required_fields: list[str]
) -> dict[str, Any]:
    """Classify pin/hole clearance semantics and angular self-consistency."""
    missing = missing_fields(ssot, required_fields)
    clearance_mm = finite_float(
        nested_get(ssot, "interface.pin_hole.clearance_mm"),
        "pin_hole.clearance_mm",
    )
    insertion_depth_mm = finite_float(
        nested_get(ssot, "interface.insertion_depth_mm"),
        "insertion_depth_mm",
    )
    fine_deg = finite_float(
        nested_get(ssot, "interface.angular_tolerance_deg.fine"),
        "angular_tolerance_deg.fine",
    )
    diameter_theta_deg = math.degrees(
        (clearance_mm / 2.0) / insertion_depth_mm
    )
    radial_theta_deg = math.degrees(clearance_mm / insertion_depth_mm)

    result: dict[str, Any] = {
        "rf_id": "RF-3",
        "status": "BLOCKED" if missing else "REPEAT",
        "reason_code": (
            "RF3_BLOCKED_CLEARANCE_SEMANTICS_UNDEFINED"
            if missing
            else "RF3_REPEAT_FINE_ANGLE_NOT_SELF_CONSISTENT"
        ),
        "missing_fields": missing,
        "inputs": {
            "clearance_mm": clearance_mm,
            "fine_angular_tolerance_deg": fine_deg,
            "insertion_depth_mm": insertion_depth_mm,
        },
        "derived": {
            "diametral_interpretation_theta_max_deg": _round(
                diameter_theta_deg
            ),
            "diametral_interpretation_pass": diameter_theta_deg >= fine_deg,
            "radial_interpretation_theta_max_deg": _round(radial_theta_deg),
            "radial_interpretation_pass": radial_theta_deg >= fine_deg,
        },
        "negative_result_preserved": True,
    }
    if missing:
        return result

    semantics = str(
        nested_get(ssot, "interface.pin_hole.clearance_semantics")
    ).upper()
    if semantics not in {"DIAMETRAL", "RADIAL"}:
        result["status"] = "BLOCKED"
        result["reason_code"] = "RF3_BLOCKED_INVALID_CLEARANCE_SEMANTICS"
        result["invalid_clearance_semantics"] = semantics
        return result

    theta_deg = (
        diameter_theta_deg if semantics == "DIAMETRAL" else radial_theta_deg
    )
    result["inputs"]["clearance_semantics"] = semantics
    result["derived"]["selected_theta_max_deg"] = _round(theta_deg)
    result["derived"]["selected_semantics_pass"] = theta_deg >= fine_deg
    if theta_deg >= fine_deg:
        result["status"] = "RESOLVED"
        result["reason_code"] = "RF3_RESOLVED_ANGULAR_CHAIN_SELF_CONSISTENT"
    return result


def classify_red_flags(
    ssot: Mapping[str, Any], rf_contract: Mapping[str, Any]
) -> dict[str, Any]:
    rf1 = classify_rf1(
        ssot, list(rf_contract["RF-1"]["required_fields"])
    )
    rf2 = classify_rf2(
        ssot, list(rf_contract["RF-2"]["required_fields"])
    )
    rf3 = classify_rf3(
        ssot, list(rf_contract["RF-3"]["required_fields"])
    )
    shared_missing = missing_fields(
        ssot, list(rf_contract["shared_critical_fields"])
    )
    results = [rf1, rf2, rf3]
    counts = Counter(item["status"] for item in results)
    return {
        "results": results,
        "status_counts": {
            key: counts.get(key, 0)
            for key in ("RESOLVED", "REPEAT", "BLOCKED")
        },
        "shared_critical_fields": {
            "status": "BLOCKED" if shared_missing else "PASS",
            "missing_fields": shared_missing,
            "reason_code": (
                "ASM00_BLOCKED_MISSING_PIN_SPACING_OR_CHAMFER"
                if shared_missing
                else "ASM00_SHARED_CRITICAL_FIELDS_PRESENT"
            ),
        },
    }


def validate_success_contract(
    contract: Mapping[str, Any], required: Mapping[str, Any]
) -> dict[str, Any]:
    failures: list[str] = []
    criteria = contract.get("criteria")
    if not isinstance(criteria, list):
        criteria = []
        failures.append("criteria_not_a_list")
    criterion_ids = [
        item.get("id") for item in criteria if isinstance(item, Mapping)
    ]
    if len(criteria) != required["required_criterion_count"]:
        failures.append("criterion_count_mismatch")
    if criterion_ids != EXPECTED_CRITERION_IDS:
        failures.append("criterion_ids_or_order_mismatch")
    if len(set(criterion_ids)) != len(criterion_ids):
        failures.append("duplicate_criterion_id")
    if contract.get("schema_id") != required["required_schema_id"]:
        failures.append("schema_id_mismatch")
    if contract.get("authorization_effect") != required[
        "authorization_effect_required"
    ]:
        failures.append("authorization_effect_not_none")

    semantics = contract.get("evaluation_semantics", {})
    if semantics.get("criterion_count") != 9:
        failures.append("declared_criterion_count_not_nine")
    if semantics.get("success_rule") != "ALL_NINE_CRITERIA_PASS":
        failures.append("success_rule_not_all_nine")
    if semantics.get("unknown_can_be_success") is not False:
        failures.append("unknown_can_be_success")
    if semantics.get("state_enum") != ["PASS", "FAIL", "UNKNOWN"]:
        failures.append("invalid_state_enum")

    by_id = {
        item.get("id"): item
        for item in criteria
        if isinstance(item, Mapping) and item.get("id")
    }
    if by_id.get("C01_FINAL_POSITION", {}).get("threshold_ref") != (
        "/interface/translational_tolerance_mm/fine"
    ):
        failures.append("position_threshold_not_ssot_ref")
    if by_id.get("C02_FINAL_ORIENTATION", {}).get("threshold_ref") != (
        "/interface/angular_tolerance_deg/fine"
    ):
        failures.append("orientation_threshold_not_ssot_ref")

    c04_predicates = by_id.get("C04_LATCH_GEOMETRY", {}).get(
        "predicates", []
    )
    c08_predicates = by_id.get(
        "C08_PROVENANCE_AND_PHASE_LEDGER", {}
    ).get("predicates", [])
    c09_predicates = by_id.get("C09_CONTACT_HISTORY", {}).get(
        "predicates", []
    )
    if {item.get("evidence_field") for item in c04_predicates} != {
        "latch_state",
        "geometry_consistent",
    }:
        failures.append("criterion_04_missing_geometry_crosscheck")
    if {item.get("evidence_field") for item in c08_predicates} != {
        "provenance_complete",
        "phase_transition_adjudication_ledger_complete",
    }:
        failures.append("criterion_08_missing_run_ledger")
    if {item.get("evidence_field") for item in c09_predicates} != {
        "all_contact_history_peaks_within_limits",
        "all_contact_segments_converged",
        "contact_log_complete",
    }:
        failures.append("criterion_09_incomplete_contact_history")

    return {
        "status": "PASS" if not failures else "FAIL",
        "criterion_count": len(criteria),
        "criterion_ids": criterion_ids,
        "failures": failures,
        "contract_freeze_is_HAG_A_approval": False,
    }


def _pointer_get(data: Mapping[str, Any], pointer: str) -> Any:
    current: Any = data
    for token in pointer.strip("/").split("/"):
        if not isinstance(current, Mapping) or token not in current:
            return None
        current = current[token]
    return unwrap_value(current)


def _evaluate_predicate(
    predicate: Mapping[str, Any],
    evidence: Mapping[str, Any],
    ssot: Mapping[str, Any],
) -> str:
    value = evidence.get(predicate.get("evidence_field"))
    if value is None:
        return "UNKNOWN"
    operator = predicate.get("operator")
    if operator == "EQUAL":
        return "PASS" if value == predicate.get("expected") else "FAIL"
    if operator == "LESS_THAN_OR_EQUAL":
        threshold = _pointer_get(ssot, str(predicate.get("threshold_ref", "")))
        if threshold is None:
            return "UNKNOWN"
        try:
            return (
                "PASS"
                if finite_float(value, "evidence") <= finite_float(
                    threshold, "threshold"
                )
                else "FAIL"
            )
        except ValueError:
            return "UNKNOWN"
    return "UNKNOWN"


def evaluate_success(
    contract: Mapping[str, Any],
    evidence: Mapping[str, Any],
    ssot: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate the frozen nine-criterion contract with tri-state semantics."""
    criterion_states: list[dict[str, str]] = []
    for criterion in contract["criteria"]:
        if criterion.get("operator") == "ALL":
            states = [
                _evaluate_predicate(predicate, evidence, ssot)
                for predicate in criterion.get("predicates", [])
            ]
            if not states:
                state = "UNKNOWN"
            elif "FAIL" in states:
                state = "FAIL"
            elif "UNKNOWN" in states:
                state = "UNKNOWN"
            else:
                state = "PASS"
        else:
            state = _evaluate_predicate(criterion, evidence, ssot)
        criterion_states.append({"id": criterion["id"], "state": state})

    states = [item["state"] for item in criterion_states]
    if "FAIL" in states:
        overall = "FAIL"
    elif "UNKNOWN" in states:
        overall = "UNKNOWN"
    elif len(states) == 9 and all(state == "PASS" for state in states):
        overall = "ASSEMBLY_SUCCESS"
    else:
        overall = "UNKNOWN"
    return {
        "overall": overall,
        "success": overall == "ASSEMBLY_SUCCESS",
        "criteria": criterion_states,
    }


def _run_git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def check_file_binding(
    root: Path, binding: Mapping[str, Any]
) -> dict[str, Any]:
    relative_path = str(binding["path"])
    path = root / relative_path
    expected = str(binding["expected_sha256"]).lower()
    if not path.is_file():
        return {
            "path": relative_path,
            "status": "MISSING",
            "expected_raw_sha256": expected,
            "actual_raw_sha256": None,
            "actual_lf_normalized_sha256": None,
            "raw_hash_match": False,
            "lf_normalized_hash_match": False,
        }
    raw_hash = sha256_file(path)
    lf_hash = sha256_lf_normalized(path)
    return {
        "path": relative_path,
        "status": "PASS" if raw_hash == expected else "FAIL_RAW_HASH",
        "expected_raw_sha256": expected,
        "actual_raw_sha256": raw_hash,
        "actual_lf_normalized_sha256": lf_hash,
        "raw_hash_match": raw_hash == expected,
        "lf_normalized_hash_match": lf_hash == expected,
    }


def check_authorizations(
    repo_root: Path,
    planning_root: Path,
    records: Mapping[str, str],
) -> dict[str, Any]:
    roots: list[tuple[str, Path]] = [("execution_root", repo_root)]
    if planning_root.resolve() != repo_root.resolve():
        roots.append(("planning_root", planning_root))

    checks: dict[str, Any] = {}
    for name, relative_path in records.items():
        locations = [
            {
                "root": root_name,
                "path": relative_path,
                "exists": (root / relative_path).is_file(),
            }
            for root_name, root in roots
        ]
        present = any(item["exists"] for item in locations)
        checks[name] = {
            "canonical_path": relative_path,
            "locations_checked": locations,
            "status": "PRESENT_UNVERIFIED" if present else "ABSENT",
            "authorization_granted": False,
            "reason_code": (
                "BLOCKED_BY_UNVERIFIED_AUTHORIZATION"
                if present
                else "BLOCKED_BY_MISSING_AUTHORIZATION"
            ),
        }
    return checks


def check_scope_guard(
    repo_root: Path, owned_path: str
) -> dict[str, Any]:
    status = _run_git(
        repo_root, "status", "--porcelain=v1", "--untracked-files=all"
    )
    outside_owned: list[str] = []
    owned_prefix = owned_path.replace("\\", "/")
    for line in status.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip('"').replace("\\", "/")
        if not path.startswith(owned_prefix):
            outside_owned.append(path)
    return {
        "status": "PASS" if not outside_owned else "FAIL",
        "owned_path": owned_prefix,
        "outside_owned_paths": sorted(outside_owned),
    }


def _collect_source_levels(node: Any, counts: Counter[str]) -> None:
    if isinstance(node, Mapping):
        source = node.get("source")
        if isinstance(source, str):
            counts[source] += 1
        for value in node.values():
            _collect_source_levels(value, counts)
    elif isinstance(node, list):
        for value in node:
            _collect_source_levels(value, counts)


def build_gate(
    repo_root: Path,
    planning_root: Path,
    preflight_contract_path: Path,
    ssot_path: Path,
    success_contract_path: Path,
) -> dict[str, Any]:
    preflight = load_yaml(preflight_contract_path)
    ssot = load_yaml(ssot_path)
    success_contract = load_yaml(success_contract_path)

    head = _run_git(repo_root, "rev-parse", "HEAD")
    branch = _run_git(repo_root, "branch", "--show-current")
    base_check = {
        "expected_commit": preflight["approved_base"]["commit"],
        "actual_commit": head,
        "commit_match": head == preflight["approved_base"]["commit"],
        "expected_branch": preflight["approved_base"]["branch"],
        "actual_branch": branch,
        "branch_match": branch == preflight["approved_base"]["branch"],
    }

    input_bindings = {
        name: check_file_binding(repo_root, binding)
        for name, binding in preflight["input_bindings"].items()
    }
    planning_bindings = {
        name: check_file_binding(planning_root, binding)
        for name, binding in preflight["planning_bindings"].items()
    }
    authorizations = check_authorizations(
        repo_root,
        planning_root,
        preflight["authorization_records"],
    )

    success_binding_spec = preflight["success_evaluator"]
    success_binding = check_file_binding(repo_root, success_binding_spec)
    success_validation = validate_success_contract(
        success_contract, success_binding_spec
    )
    contract_freeze_complete = (
        success_binding["raw_hash_match"]
        and success_validation["status"] == "PASS"
    )

    rf_classification = classify_red_flags(
        ssot, preflight["rf_contract"]
    )
    scope_guard = check_scope_guard(repo_root, preflight["owned_path"])
    source_levels: Counter[str] = Counter()
    _collect_source_levels(ssot, source_levels)
    draft_criteria = ssot.get("assembly_success_criteria", {})
    draft_criteria_count = (
        len(draft_criteria) if isinstance(draft_criteria, Mapping) else 0
    )

    blockers: list[str] = []
    repeats: list[str] = []
    if not base_check["commit_match"]:
        blockers.append("BLOCKED_BY_HEAD_MISMATCH")
    if not base_check["branch_match"]:
        blockers.append("BLOCKED_BY_BRANCH_MISMATCH")
    if authorizations["HAG-A"]["status"] == "ABSENT":
        blockers.append("BLOCKED_BY_MISSING_HAG_A")
    else:
        blockers.append("BLOCKED_BY_UNVERIFIED_HAG_A")
    for name, check in input_bindings.items():
        if not check["raw_hash_match"]:
            blockers.append(f"BLOCKED_BY_{name.upper()}_RAW_HASH_MISMATCH")
    for name, check in planning_bindings.items():
        if not check["raw_hash_match"]:
            blockers.append(
                f"BLOCKED_BY_{name.upper()}_RAW_HASH_MISMATCH"
            )
    if not contract_freeze_complete:
        blockers.append("BLOCKED_BY_SUCCESS_CONTRACT_FREEZE_FAILURE")
    if scope_guard["status"] != "PASS":
        blockers.append("BLOCKED_BY_SCOPE_VIOLATION")
    for result in rf_classification["results"]:
        if result["status"] == "BLOCKED":
            blockers.append(result["reason_code"])
        elif result["status"] == "REPEAT":
            repeats.append(result["reason_code"])
    if rf_classification["shared_critical_fields"]["status"] == "BLOCKED":
        blockers.append(
            rf_classification["shared_critical_fields"]["reason_code"]
        )

    if blockers:
        raw_verdict = RAW_VERDICT_BLOCKED
    elif repeats:
        raw_verdict = RAW_VERDICT_REPEAT
    else:
        raw_verdict = RAW_VERDICT_PASS_PROVISIONAL
    external_status = preflight["verdict_mapping"][raw_verdict]

    gates = {
        "AG0_AUTHORIZATION_PREFLIGHT": {
            "status": "BLOCKED",
            "reason_code": authorizations["HAG-A"]["reason_code"],
        },
        "AG0_BASE_AND_HASH_BINDING": {
            "status": (
                "PASS"
                if base_check["commit_match"]
                and base_check["branch_match"]
                and all(
                    item["raw_hash_match"]
                    for item in input_bindings.values()
                )
                and all(
                    item["raw_hash_match"]
                    for item in planning_bindings.values()
                )
                else "BLOCKED"
            ),
            "raw_hash_equivalence_required": True,
            "lf_normalized_equivalence_is_not_raw_equivalence": True,
        },
        "AG0_SUCCESS_CONTRACT_FREEZE": {
            "status": "PASS" if contract_freeze_complete else "BLOCKED",
            "contract_freeze_is_HAG_A_approval": False,
        },
        "AG0_RF_CLASSIFICATION": {
            "status": (
                "PASS"
                if rf_classification["status_counts"]["RESOLVED"] == 3
                and not rf_classification["shared_critical_fields"][
                    "missing_fields"
                ]
                else "BLOCKED"
            )
        },
        "AG0_SCIENTIFIC_INTERFACE_QUALIFICATION": {
            "status": "NOT_RUN_UNAUTHORIZED",
            "physics_solver_run": False,
            "monte_carlo_run": False,
            "ssot_v1_written": False,
        },
    }

    return {
        "schema_version": "asm00-gate-check-v1",
        "task_id": "ASM-00",
        "execution_mode": "PREFLIGHT_AND_DRAFT_CLASSIFICATION_ONLY",
        "raw_verdict": raw_verdict,
        "external_status": external_status,
        "interface_qualification_granted": False,
        "scientific_execution_authorized": False,
        "next_stage_authorized": False,
        "contract_freeze_completed": contract_freeze_complete,
        "contract_freeze_is_HAG_A_approval": False,
        "thresholds_widened": bool(preflight["thresholds_widened"]),
        "negative_results_preserved": True,
        "source_files_modified": False,
        "base_check": base_check,
        "scope_guard": scope_guard,
        "input_bindings": input_bindings,
        "planning_bindings": planning_bindings,
        "authorization_checks": authorizations,
        "success_evaluator": {
            "binding": success_binding,
            "validation": success_validation,
            "HAG_A_binding_present": False,
        },
        "draft_state": {
            "version": ssot.get("version"),
            "status": ssot.get("status"),
            "success_criteria_count": draft_criteria_count,
            "source_level_counts": {
                key: source_levels[key] for key in sorted(source_levels)
            },
            "has_measured_source": source_levels.get("MEASURED", 0) > 0,
        },
        "rf_classification": rf_classification,
        "gates": gates,
        "blockers": sorted(set(blockers)),
        "repeat_reasons": sorted(set(repeats)),
        "stop_reason": (
            "ASM00_PREFLIGHT_BLOCKED_STOP_NO_ASM01_ASM02"
            if raw_verdict == RAW_VERDICT_BLOCKED
            else (
                "ASM00_REPEAT_STOP_NO_ASM01_ASM02"
                if raw_verdict == RAW_VERDICT_REPEAT
                else "ASM00_INTERFACE_QUALIFIED_STOP_AWAIT_HAG_B"
            )
        ),
        "claim_boundaries": {
            "allowed": [
                "Nine-criterion evaluator contract frozen pending HAG-A binding.",
                "RF-1/RF-2/RF-3 machine-classified from the unchanged draft.",
            ],
            "forbidden": [
                "HAG-A approved.",
                "Interface parameters validated or measured.",
                "Assembly success demonstrated.",
                "Autonomous on-orbit assembly completed.",
                "ASM-01 or ASM-02 authorized.",
            ],
        },
    }


def build_evidence_manifest(
    repo_root: Path,
    planning_root: Path,
    gate: Mapping[str, Any],
    gate_path: Path,
    evidence_manifest_path: Path,
) -> dict[str, Any]:
    owned_root = repo_root / "30_simulation/asm_00_interface_preflight"
    artifacts: list[dict[str, Any]] = []
    for path in sorted(
        item
        for item in owned_root.rglob("*")
        if item.is_file() and item.resolve() != evidence_manifest_path.resolve()
    ):
        artifacts.append(
            {
                "path": path.relative_to(repo_root).as_posix(),
                "raw_sha256": sha256_file(path),
                "role": (
                    "MACHINE_GATE"
                    if path.resolve() == gate_path.resolve()
                    else "OWNED_EVIDENCE"
                ),
            }
        )

    source_inputs: list[dict[str, Any]] = []
    for scope, root, bindings in (
        ("execution", repo_root, gate["input_bindings"]),
        ("planning", planning_root, gate["planning_bindings"]),
    ):
        for name, binding in sorted(bindings.items()):
            path = root / binding["path"]
            source_inputs.append(
                {
                    "artifact_id": name,
                    "scope": scope,
                    "path": binding["path"],
                    "status": "PRESENT" if path.is_file() else "MISSING",
                    "raw_sha256": sha256_file(path) if path.is_file() else None,
                    "expected_raw_sha256": binding[
                        "expected_raw_sha256"
                    ],
                    "raw_hash_match": binding["raw_hash_match"],
                }
            )

    authorization_evidence = [
        {
            "authorization_id": name,
            "canonical_path": value["canonical_path"],
            "status": value["status"],
            "authorization_granted": False,
        }
        for name, value in sorted(gate["authorization_checks"].items())
    ]
    return {
        "schema_version": "asm00-evidence-manifest-v1",
        "task_id": "ASM-00",
        "generation_policy": "DETERMINISTIC_NO_WALL_CLOCK",
        "base_commit": gate["base_check"]["actual_commit"],
        "raw_verdict": gate["raw_verdict"],
        "external_status": gate["external_status"],
        "interface_qualification_granted": False,
        "scientific_execution_authorized": False,
        "negative_results_preserved": True,
        "source_inputs": source_inputs,
        "authorization_evidence": authorization_evidence,
        "owned_artifacts": artifacts,
        "owned_artifact_count": len(artifacts),
        "manifest_self_hash_included": False,
        "evidence_freeze_complete": True,
    }
