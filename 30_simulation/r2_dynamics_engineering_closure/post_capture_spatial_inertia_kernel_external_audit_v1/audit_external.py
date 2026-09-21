#!/usr/bin/env python3
"""Package-external, frozen-pin audit for the post-capture inertia candidate."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Mapping, Sequence

import numpy as np


AUDIT_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = AUDIT_ROOT.parents[2]
LOCK_PATH = AUDIT_ROOT / "SOURCE_LOCK_V1.json"
RESULT_PATH = AUDIT_ROOT / "results" / "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_EXTERNAL_AUDIT_GATE_V1.json"
EXPECTED_LOCK_CANONICAL_SHA256 = "182EC07190EB34FCECF5C77817802186C4DCCAFC889378234BA558E7B508EC47"
FALSE_KEYS = (
    "current_system_instance_evaluated", "contact_valid", "attachment_valid",
    "target_attachment_plant_valid", "hardware_valid", "non_abort_authorized",
    "parent_dynamics_engineering_complete", "next_stage_authorized", "release_credit",
)


class AuditError(RuntimeError):
    pass


def reject_constant(token: str) -> None:
    raise ValueError(f"NONFINITE_JSON:{token}")


def unique_pairs(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def strict_read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs, parse_constant=reject_constant)


def builtin(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [builtin(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): builtin(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [builtin(item) for item in value]
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(builtin(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest().upper()


def file_record(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest().upper()}


def vec(value: Any, size: int, token: str) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != (size,) or not np.all(np.isfinite(result)):
        raise AuditError(token)
    return result


def mat(value: Any, shape: tuple[int, int], token: str) -> np.ndarray:
    result = np.asarray(value, dtype=float)
    if result.shape != shape or not np.all(np.isfinite(result)):
        raise AuditError(token)
    return result


def validate_transform(value: Any, token: str) -> np.ndarray:
    transform = mat(value, (4, 4), token)
    if np.max(np.abs(transform[3] - np.array([0.0, 0.0, 0.0, 1.0]))) > 1.0e-14:
        raise AuditError(token + "_ROW")
    rotation = transform[:3, :3]
    if np.max(np.abs(rotation.T @ rotation - np.eye(3))) > 2.0e-12:
        raise AuditError(token + "_ORTHONORMAL")
    if abs(np.linalg.det(rotation) - 1.0) > 2.0e-12:
        raise AuditError(token + "_PROPER")
    return transform


def validate_inertia(value: Any, token: str) -> np.ndarray:
    inertia = mat(value, (3, 3), token)
    if np.max(np.abs(inertia - inertia.T)) > 2.0e-12:
        raise AuditError(token + "_SYMMETRY")
    eigenvalues = np.linalg.eigvalsh(inertia)
    if eigenvalues[0] < 1.0e-10 or eigenvalues[-1] > eigenvalues[0] + eigenvalues[1] + 1.0e-10:
        raise AuditError(token + "_PHYSICAL")
    if not math.isfinite(float(np.linalg.cond(inertia))):
        raise AuditError(token + "_SINGULAR")
    return inertia


def paa(mass: float, displacement: Any) -> np.ndarray:
    if not math.isfinite(mass) or mass < 0.0:
        raise AuditError("PAA_MASS")
    d = vec(displacement, 3, "PAA_D")
    return mass * ((d @ d) * np.eye(3) - np.outer(d, d))


def cross_matrix(value: Any) -> np.ndarray:
    x, y, z = vec(value, 3, "CROSS")
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def audit_pins(lock: Mapping[str, Any]) -> dict[str, Any]:
    records = []
    for pin in lock["pins"]:
        path = PROJECT_ROOT / pin["path"]
        actual = file_record(path) if path.is_file() else {"bytes": None, "sha256": None}
        records.append({"id": pin["id"], "path": pin["path"], **actual, "match": actual == {"bytes": pin["bytes"], "sha256": pin["sha256"]}})
    return {"records": records, "count": len(records), "all_match": all(item["match"] for item in records)}


def documents(lock: Mapping[str, Any]) -> dict[str, Any]:
    by_id = {item["id"]: PROJECT_ROOT / item["path"] for item in lock["pins"]}
    return {key: strict_read(by_id[key]) for key in ("contract", "evidence", "gate", "manifest", "standalone_internal_receipt")}


def contract_semantics(contract: Mapping[str, Any]) -> dict[str, bool]:
    authority = contract.get("current_system_authority_contract", {})
    admission = authority.get("successful_admission_receipt_contract", {})
    event = contract.get("model_contract", {}).get("event_momentum", {})
    pc05 = contract.get("minimum_true_inputs_to_bind_existing_23d_plant", [None] * 5)[4]
    return {
        "schema": contract.get("schema") == "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_CONTRACT_V1",
        "receipt_pin_required": admission.get("required_contract_source_pin_id") == "attachment_authority_receipt",
        "receipt_pin_currently_absent": admission.get("current_contract_contains_attachment_authority_receipt_pin") is False and not any(item.get("id") == "attachment_authority_receipt" for item in contract.get("source_pins", [])),
        "frame_ids": admission.get("required_frame_ids") == {"parent_frame": "E", "child_frame": "T", "transform_field": "T_E_T_rows"},
        "bare_inputs_forbidden": admission.get("caller_supplied_status_or_boolean_without_pinned_receipt_forbidden") is True,
        "numeric_origin": "origin_O_in_I_m" in pc05.get("required", []) and event.get("angular_momentum_translation_law") == "H_O_prime=H_O-(r_O_prime-r_O)xP",
        "current_attachment_null": authority.get("required_value") is None,
        "current_authority_false": authority.get("operational_attachment_authority") is False and authority.get("kernel_call_for_current_instance_allowed") is False,
        "release_false": contract.get("next_stage_authorized") is False and contract.get("release_credit") is False,
    }


def static_api_audit(lock: Mapping[str, Any]) -> dict[str, bool]:
    core_pin = next(item for item in lock["pins"] if item["id"] == "core_source")
    source = (PROJECT_ROOT / core_pin["path"]).read_text(encoding="utf-8")
    return {
        "receipt_api_signature": "authority_receipt: Mapping[str, Any] | None" in source and "configuration_id: str" in source,
        "contract_loaded_internally": "contract = load_contract()" in source,
        "no_legacy_bare_boolean_signature": "status: str,\n    operational_authority: bool,\n    plant_allowed: bool" not in source,
        "receipt_file_rehashed": "ATTACHMENT_AUTHORITY_RECEIPT_SOURCE_HASH_MISMATCH" in source,
        "state_record_hash_linked": "ATTACHMENT_CONFIGURATION_RECORD_HASH_LINKAGE_MISMATCH" in source,
        "state_source_rehashed": "CONFIGURATION_STATE_SOURCE_HASH_MISMATCH" in source,
        "numeric_origin_formula": "lever_O_to_C_I = cg_position_I - origin_O" in source and "np.cross(lever_O_to_C_I, linear)" in source,
        "public_mass_guards": "SPATIAL_MASS" in source and "COMPOSITE_MASS" in source,
        "public_inertia_guards": "validate_inertia(inertia, \"SPATIAL_INERTIA_CG\")" in source and "validate_inertia(inertia_B, \"COMPOSITE_INERTIA_B\")" in source,
    }


def runtime_authority_controls(lock: Mapping[str, Any]) -> dict[str, Any]:
    """Execute the fixed-pin core in an isolated child process against forgeries."""
    by_id = {item["id"]: PROJECT_ROOT / item["path"] for item in lock["pins"]}
    contract = strict_read(by_id["contract"])
    forged_contract = copy.deepcopy(contract)
    forged_contract["release_credit"] = True
    forged_receipt = {
        "schema": "AUTHORITY_BOUND_ATTACHMENT_SE3_RECEIPT_V1",
        "status": "AUTHORITY_BOUND_OPERATIONAL_ATTACHMENT_SE3",
        "operational_attachment_authority": True,
        "target_attachment_plant_allowed": True,
        "attachment_frame_ids": {"parent_frame": "E", "child_frame": "T", "transform_field": "T_E_T_rows"},
        "T_E_T_rows": np.eye(4).tolist(),
        "system_configuration_linkage": {"configuration_id": "C08"},
    }
    child = r'''
import importlib.util, json, pathlib, sys
core_path, real_contract_path, forged_contract_path, forged_receipt_path = map(pathlib.Path, sys.argv[1:5])
spec = importlib.util.spec_from_file_location("runtime_forgery_target", core_path)
module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
receipt = json.loads(forged_receipt_path.read_text(encoding="utf-8"))
def observe(operation):
    try:
        operation(); return "NO_EXCEPTION"
    except Exception as exc:
        return type(exc).__name__ + ":" + str(exc)
supplied_contract = observe(lambda: module.admit_current_system_attachment(receipt, "C08", {}))
module.CONTRACT_PATH = forged_contract_path
forged_contract = observe(lambda: module.admit_current_system_attachment(receipt, "C08"))
module.CONTRACT_PATH = real_contract_path
forged_receipt = observe(lambda: module.admit_current_system_attachment(receipt, "C08"))
print(json.dumps({"caller_supplied_contract": supplied_contract, "forged_contract_file": forged_contract, "forged_receipt_file": forged_receipt}, sort_keys=True))
'''
    with tempfile.TemporaryDirectory(prefix="post_capture_runtime_authority_") as temporary:
        temporary_root = Path(temporary)
        forged_contract_path = temporary_root / "forged_contract.json"
        forged_receipt_path = temporary_root / "forged_receipt.json"
        forged_contract_path.write_text(json.dumps(forged_contract, sort_keys=True), encoding="utf-8")
        forged_receipt_path.write_text(json.dumps(forged_receipt, sort_keys=True), encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, "-B", "-c", child, str(by_id["core_source"]), str(by_id["contract"]), str(forged_contract_path), str(forged_receipt_path)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    parsed = json.loads(completed.stdout.strip()) if completed.returncode == 0 and completed.stdout.strip() else {}
    checks = {
        "child_exit_zero": completed.returncode == 0,
        "caller_contract_argument_rejected": "TypeError" in parsed.get("caller_supplied_contract", ""),
        "forged_contract_file_rejected_by_canonical_hash": "CONTRACT_CANONICAL_SHA256_DRIFT" in parsed.get("forged_contract_file", ""),
        "forged_receipt_file_rejected_without_contract_pin": "ATTACHMENT_AUTHORITY_SOURCE_PIN_MISSING" in parsed.get("forged_receipt_file", ""),
    }
    return {"checks": checks, "observed": parsed, "stderr": completed.stderr.strip(), "all_pass": all(checks.values())}


def recompute_case(run: Mapping[str, Any]) -> dict[str, Any]:
    fixture = run["fixture"]
    if fixture["service"].get("frame") != "B" or fixture["target"].get("frame") != "T":
        raise AuditError("BODY_FRAME")
    if fixture.get("frames") != {"service_mass_properties": "B", "target_mass_properties": "T", "T_B_E": "B_FROM_E", "T_E_T": "E_FROM_T", "T_I_B": "I_FROM_B", "momentum": "I_ABOUT_O"}:
        raise AuditError("FRAME_LEDGER")
    T_B_E = validate_transform(fixture["T_B_E_rows"], "T_B_E")
    T_E_T = validate_transform(fixture["T_E_T_rows"], "T_E_T")
    T_B_T = validate_transform(T_B_E @ T_E_T, "T_B_T")
    service = fixture["service"]; target = fixture["target"]
    ms = float(service["mass_kg"]); mt = float(target["mass_kg"])
    if not (math.isfinite(ms) and ms > 0.0 and math.isfinite(mt) and mt > 0.0):
        raise AuditError("MASS")
    cs = vec(service["cg_m"], 3, "CS"); ct = T_B_T[:3, :3] @ vec(target["cg_m"], 3, "CT") + T_B_T[:3, 3]
    Is = validate_inertia(service["inertia_cg_kg_m2"], "IS")
    It = T_B_T[:3, :3] @ validate_inertia(target["inertia_cg_kg_m2"], "IT") @ T_B_T[:3, :3].T
    mass = ms + mt; cg = (ms * cs + mt * ct) / mass
    inertia = Is + paa(ms, cs - cg) + It + paa(mt, ct - cg)
    validate_inertia(inertia, "COMPOSITE")
    stored = run["composite_direct"]
    direct_error = max(abs(mass - stored["mass_kg"]), float(np.max(np.abs(cg - np.asarray(stored["cg_B_m"])))), float(np.max(np.abs(inertia - np.asarray(stored["inertia_cg_B_kg_m2"])))))
    s_cs = cross_matrix(cs); s_ct = cross_matrix(ct)
    spatial = np.block([[ms*np.eye(3), -ms*s_cs], [ms*s_cs, Is+paa(ms,cs)]]) + np.block([[mt*np.eye(3), -mt*s_ct], [mt*s_ct, It+paa(mt,ct)]])
    spatial_error = float(np.max(np.abs(spatial - np.asarray(run["independent_spatial_formula_cross"]["spatial_inertia_B_v_omega_order"]))))
    T_I_B = validate_transform(fixture["T_I_B_rows"], "T_I_B"); R = T_I_B[:3, :3]
    cg_I = T_I_B[:3, 3] + R @ cg; inertia_I = R @ inertia @ R.T
    P = vec(fixture["linear_momentum_I_kg_m_s"], 3, "P"); H = vec(fixture["angular_momentum_about_O_I_kg_m2_s"], 3, "H"); origin = vec(fixture["origin_O_in_I_m"], 3, "ORIGIN")
    omega = np.linalg.solve(inertia_I, H - np.cross(cg_I - origin, P))
    vbase = P / mass - np.cross(omega, R @ cg)
    stored_state = run["post_capture_state_initialization"]
    twist_error = float(np.max(np.abs(np.concatenate((vbase, omega)) - np.asarray(stored_state["derived_base_twist_I_m_s_rad_s"]))))
    delta = np.array([0.37, -0.21, 0.16]); shifted_H = H - np.cross(delta, P)
    shifted_omega = np.linalg.solve(inertia_I, shifted_H - np.cross(cg_I - origin - delta, P))
    wrong_omega = np.linalg.solve(inertia_I, H + np.cross(delta, P) - np.cross(cg_I - origin - delta, P))
    return {
        "direct_max_abs": direct_error,
        "spatial_max_abs": spatial_error,
        "twist_max_abs": twist_error,
        "reference_translation_twist_max_abs": float(np.max(np.abs(shifted_omega - omega))),
        "wrong_cross_sign_omega_delta": float(np.max(np.abs(wrong_omega - omega))),
    }


def build_gate() -> dict[str, Any]:
    lock = strict_read(LOCK_PATH)
    if canonical_hash(lock) != EXPECTED_LOCK_CANONICAL_SHA256:
        raise AuditError("SOURCE_LOCK_CANONICAL_SHA256_DRIFT")
    pins = audit_pins(lock); docs = documents(lock)
    contract_checks = contract_semantics(docs["contract"]); static_checks = static_api_audit(lock); runtime_controls = runtime_authority_controls(lock)
    physics = {key: recompute_case(docs["evidence"]["synthetic_fixture_runs"][key]) for key in ("C08", "C09")}
    gate = docs["gate"]; receipt = docs["standalone_internal_receipt"]
    gate_false = all(gate.get(key) is False for key in FALSE_KEYS)
    receipt_false = all(receipt.get(key) is False for key in FALSE_KEYS)
    candidate_summary = gate.get("passed") == gate.get("total") == 22 and gate.get("all_checks_pass") is True
    current_held = gate.get("current_C08_status") == lock["required_current_status"] and gate.get("current_C09_status") == lock["required_current_status"]
    internal_honest = receipt.get("independence_classification") == lock["expected_internal_validation"]["classification"] and receipt.get("passed") == receipt.get("total") == 34 and receipt.get("negative_controls", {}).get("passed") == receipt.get("negative_controls", {}).get("count") == 29
    physics_pass = all(item["direct_max_abs"] <= 2.0e-11 and item["spatial_max_abs"] <= 2.0e-11 and item["twist_max_abs"] <= 2.0e-12 and item["reference_translation_twist_max_abs"] <= 2.0e-12 and item["wrong_cross_sign_omega_delta"] > 1.0e-8 for item in physics.values())
    mutated_lock = copy.deepcopy(lock); mutated_lock["pins"][0]["sha256"] = "0" * 64
    mutation_rejected = not audit_pins(mutated_lock)["all_match"]
    checks = [
        ("EA01", "EXTERNAL_SOURCE_LOCK_CANONICAL_FIXED", True),
        ("EA02", "TEN_CANDIDATE_FILES_MATCH_FIXED_BYTES_AND_SHA256", pins["count"] == 10 and pins["all_match"]),
        ("EA03", "SOURCE_LOCK_MUTATION_REHASH_REJECTED", mutation_rejected),
        ("EA04", "CONTRACT_RECEIPT_AUTHORITY_FAIL_CLOSED_SEMANTICS", all(contract_checks.values())),
        ("EA05", "CORE_API_STATIC_GUARDS_AND_RUNTIME_FORGED_CONTRACT_RECEIPT_REJECTION", all(static_checks.values()) and runtime_controls["all_pass"]),
        ("EA06", "CANDIDATE_GATE_22_OF_22", candidate_summary),
        ("EA07", "C08_C09_REMAIN_NOT_EVALUATED", current_held),
        ("EA08", "CANDIDATE_GATE_ALL_DOWNSTREAM_AUTHORITY_FALSE", gate_false),
        ("EA09", "INTERNAL_VALIDATOR_HONESTLY_CLASSIFIED_STANDALONE_INTERNAL", internal_honest),
        ("EA10", "INTERNAL_RECEIPT_ALL_DOWNSTREAM_AUTHORITY_FALSE", receipt_false),
        ("EA11", "SERVICE_AND_TARGET_BODY_FRAMES_REPARSED", physics_pass),
        ("EA12", "COMPOSED_T_B_T_REVALIDATED", physics_pass),
        ("EA13", "DIRECT_MASS_CG_INERTIA_RECOMPUTED", all(item["direct_max_abs"] <= 2.0e-11 for item in physics.values())),
        ("EA14", "SPATIAL_INERTIA_RECOMPUTED", all(item["spatial_max_abs"] <= 2.0e-11 for item in physics.values())),
        ("EA15", "POST_CAPTURE_TWIST_WITH_NUMERIC_ORIGIN_RECOMPUTED", all(item["twist_max_abs"] <= 2.0e-12 for item in physics.values())),
        ("EA16", "REFERENCE_POINT_TRANSLATION_COVARIANCE_RECOMPUTED", all(item["reference_translation_twist_max_abs"] <= 2.0e-12 for item in physics.values())),
        ("EA17", "REFERENCE_POINT_CROSS_SIGN_FALSIFIER_ACTIVE", all(item["wrong_cross_sign_omega_delta"] > 1.0e-8 for item in physics.values())),
        ("EA18", "NO_PARENT_RELEASE_SAFE_CAD_M01_OR_HARDWARE_CREDIT", gate_false and receipt_false),
    ]
    rows = [{"id": identifier, "name": name, "pass": bool(passed)} for identifier, name, passed in checks]
    return builtin({
        "schema": "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_EXTERNAL_AUDIT_GATE_V1",
        "audit_architecture": "PACKAGE_EXTERNAL_FIXED_SOURCE_LOCK__NO_CANDIDATE_IMPORT__NO_RUNTIME_EXPECTATION_GENERATION_FROM_TARGET_PACKAGE",
        "source_lock_canonical_sha256": EXPECTED_LOCK_CANONICAL_SHA256,
        "checks": rows, "passed": sum(item["pass"] for item in rows), "total": len(rows), "all_checks_pass": all(item["pass"] for item in rows),
        "verdict": "EXTERNAL_AUDIT_PASS_FOR_SYNTHETIC_KERNEL_ONLY__CURRENT_C08_C09_NOT_EVALUATED__NO_DOWNSTREAM_CREDIT" if all(item["pass"] for item in rows) else "EXTERNAL_AUDIT_HOLD",
        "fixed_pin_audit": pins, "contract_semantics": contract_checks, "static_api_audit": static_checks, "runtime_authority_controls": runtime_controls, "physics_recomputation": physics,
        "current_C08_status": lock["required_current_status"], "current_C09_status": lock["required_current_status"],
        **{key: False for key in FALSE_KEYS},
        "safe_gate_credit": False, "cad_credit": False, "m01_credit": False,
    })


def pretty(value: Any) -> bytes:
    return (json.dumps(builtin(value), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(); group = parser.add_mutually_exclusive_group(required=True); group.add_argument("--write", action="store_true"); group.add_argument("--check", action="store_true"); group.add_argument("--stdout", action="store_true"); args = parser.parse_args()
    gate = build_gate()
    if args.write:
        RESULT_PATH.parent.mkdir(parents=True, exist_ok=True); RESULT_PATH.write_bytes(pretty(gate)); print(json.dumps({"gate": file_record(RESULT_PATH), "checks": f"{gate['passed']}/{gate['total']}"}, indent=2, sort_keys=True)); return 0 if gate["all_checks_pass"] else 2
    if args.check:
        stored = strict_read(RESULT_PATH); exact = canonical_bytes(stored) == canonical_bytes(gate); result = {"recompute_pass": gate["all_checks_pass"], "stored_canonical_exact": exact, "checks": f"{gate['passed']}/{gate['total']}", "all_pass": gate["all_checks_pass"] and exact}; print(json.dumps(result, indent=2, sort_keys=True)); return 0 if result["all_pass"] else 3
    print(json.dumps(gate, indent=2, sort_keys=True, ensure_ascii=False)); return 0 if gate["all_checks_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
