#!/usr/bin/env python3
"""Independent read-only recomputation and terminal receipt for Phase-A.

This process intentionally does not import ``sim13_v3.reduced_dynamics``.  It
rebuilds the Schur complement directly from the reused V2 mass-matrix model,
uses an explicit five-point derivative, evaluates the full triple Christoffel
sum, and resolves qdd and the two zero-momentum residuals at three states.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys

import numpy as np


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
SOURCE_MANIFEST_PATH = HERE / "evidence" / "SIM13_V3_PHASE_A_SOURCE_MANIFEST_V2.csv"
LEDGER_PATH = HERE / "evidence" / "SIM13_V3_PHASE_A_DYNAMICS_LEDGER_V2.json"
VALIDATION_PATH = HERE / "evidence" / "SIM13_V3_PHASE_A_VALIDATION_V2.json"
EVIDENCE_MANIFEST_PATH = HERE / "evidence" / "SIM13_V3_PHASE_A_EVIDENCE_MANIFEST_V2.json"
GATE_PATH = HERE / "results" / "SIM13_V3_PHASE_A_DYNAMICS_GATE_V2.json"
RECEIPT_PATH = HERE / "evidence" / "SIM13_V3_PHASE_A_INDEPENDENT_AUDIT_RECEIPT_V2.json"
OUTER_MANIFEST_PATH = HERE / "results" / "SIM13_V3_PHASE_A_OUTER_SELF_EXCLUDED_MANIFEST_V2.json"

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from sim13_v3.source_model import (
    PROJECT_ROOT as MODEL_PROJECT_ROOT,
    build_synthetic_8dof_model,
    file_record,
    sha256_bytes,
    synthetic_8dof_xml_bytes,
)


EXPECTED_SOURCE_RECORD_COUNT = 17
BIAS_ABSOLUTE_TOLERANCE_BY_TYPE = {"REVOLUTE_NM": 2.0e-9, "PRISMATIC_N": 2.0e-9}
ACCELERATION_ABSOLUTE_TOLERANCE_BY_TYPE = {
    "REVOLUTE_RAD_S2": 2.0e-8,
    "PRISMATIC_M_S2": 2.0e-8,
}
MOMENTUM_TOLERANCES = {"linear_ns": 2.0e-13, "angular_about_root_nms": 2.0e-13}


def _canonical_json_bytes(document: object) -> bytes:
    return (
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _write_json(path: Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_json_bytes(document))


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _record(path: Path, role: str) -> dict[str, object]:
    return {"role": role, **file_record(path)}


def _matches_record(path: Path, record: dict[str, object]) -> bool:
    actual = file_record(path)
    return (
        actual["path"] == record.get("path")
        and actual["bytes"] == record.get("bytes")
        and actual["sha256"] == record.get("sha256")
    )


def _explicit_reduced_mass(model, q: np.ndarray) -> np.ndarray:
    blocks = model.mass_matrix_blocks(q)
    reduced = blocks.Hmm - blocks.Hmb @ np.linalg.solve(blocks.Hbb, blocks.Hbm)
    return 0.5 * (reduced + reduced.T)


def _five_point_derivatives(
    model, q: np.ndarray, fine_steps: np.ndarray
) -> np.ndarray:
    dof = q.size
    derivatives = np.empty((dof, dof, dof))
    for index, step in enumerate(fine_steps):
        minus_two = q.copy()
        minus_one = q.copy()
        plus_one = q.copy()
        plus_two = q.copy()
        minus_two[index] -= 2.0 * step
        minus_one[index] -= step
        plus_one[index] += step
        plus_two[index] += 2.0 * step
        derivatives[index] = (
            _explicit_reduced_mass(model, minus_two)
            - 8.0 * _explicit_reduced_mass(model, minus_one)
            + 8.0 * _explicit_reduced_mass(model, plus_one)
            - _explicit_reduced_mass(model, plus_two)
        ) / (12.0 * step)
    return derivatives


def _triple_christoffel_bias(
    derivatives: np.ndarray, rates: np.ndarray
) -> np.ndarray:
    dof = rates.size
    bias = np.zeros(dof)
    for i in range(dof):
        for j in range(dof):
            for k in range(dof):
                gamma_ijk = 0.5 * (
                    derivatives[k, i, j]
                    + derivatives[j, i, k]
                    - derivatives[i, j, k]
                )
                bias[i] += gamma_ijk * rates[j] * rates[k]
    return bias


def _audit_source_manifest(failures: list[str]) -> dict[str, object]:
    with SOURCE_MANIFEST_PATH.open("r", encoding="utf-8", newline="") as stream:
        records = list(csv.DictReader(stream))
    if len(records) != EXPECTED_SOURCE_RECORD_COUNT:
        failures.append("source_manifest_record_count")
    if any(
        "__pycache__" in record["path"]
        or ".pytest_cache" in record["path"]
        or record["path"].endswith(".pyc")
        for record in records
    ):
        failures.append("source_manifest_cache_entry")
    schemas = {record["schema"] for record in records}
    if schemas != {"SIM13_V3_PHASE_A_SOURCE_MANIFEST_V2"}:
        failures.append("source_manifest_schema")
    mismatches = []
    for record in records:
        path = PROJECT_ROOT / record["path"]
        payload = path.read_bytes()
        if len(payload) != int(record["bytes"]):
            mismatches.append(f"bytes:{record['path']}")
        if hashlib.sha256(payload).hexdigest().upper() != record["sha256"]:
            mismatches.append(f"hash:{record['path']}")
    failures.extend(f"source_manifest:{item}" for item in mismatches)
    return {
        "records_verified": len(records),
        "mismatches": mismatches,
        "cache_entries": 0,
        "explicit_whitelist_required": True,
    }


def main() -> int:
    if PROJECT_ROOT != MODEL_PROJECT_ROOT:
        raise RuntimeError("project-root resolution drift")
    if "sim13_v3.reduced_dynamics" in sys.modules:
        raise RuntimeError("independent audit must start without reduced_dynamics imported")
    failures: list[str] = []
    source_audit = _audit_source_manifest(failures)
    ledger = _load_json(LEDGER_PATH)
    validation = _load_json(VALIDATION_PATH)
    evidence_manifest = _load_json(EVIDENCE_MANIFEST_PATH)
    gate = _load_json(GATE_PATH)

    source_reference = _record(SOURCE_MANIFEST_PATH, "UPSTREAM_SOURCE_MANIFEST")
    if ledger.get("hash_chain", {}).get("upstream_source_manifest") != source_reference:
        failures.append("ledger_source_chain")
    if validation.get("hash_chain", {}).get("upstream_source_manifest") != source_reference:
        failures.append("validation_source_chain")
    if evidence_manifest.get("upstream_source_manifest") != source_reference:
        failures.append("evidence_source_chain")
    evidence_records = evidence_manifest.get("records", [])
    expected_evidence_records = [
        _record(LEDGER_PATH, "DIAGNOSTIC_LEDGER"),
        _record(VALIDATION_PATH, "VALIDATION_EVIDENCE"),
    ]
    if evidence_records != expected_evidence_records:
        failures.append("evidence_manifest_records")
    if evidence_manifest.get("self_excluded_path") != EVIDENCE_MANIFEST_PATH.relative_to(
        PROJECT_ROOT
    ).as_posix():
        failures.append("evidence_manifest_self_exclusion")
    evidence_reference = _record(
        EVIDENCE_MANIFEST_PATH, "UPSTREAM_EVIDENCE_MANIFEST"
    )
    if gate.get("hash_chain", {}).get("upstream_source_manifest") != source_reference:
        failures.append("gate_source_chain")
    if gate.get("hash_chain", {}).get("upstream_evidence_manifest") != evidence_reference:
        failures.append("gate_evidence_chain")
    if gate.get("overall_status") != "PASS_DIAGNOSTIC_WITH_UNIFIED_R2_EXECUTION_BINDING_HOLD":
        failures.append("overall_status")
    gates = {item["id"]: item for item in gate.get("gates", [])}
    if gates.get("DYN-A01", {}).get("status") != "PASS_DIAGNOSTIC":
        failures.append("generic_diagnostic")
    if gates.get("DYN-G01", {}).get("pass") is not False or not str(
        gates.get("DYN-G01", {}).get("status", "")
    ).startswith("HOLD_"):
        failures.append("unified_r2_hold")
    if validation.get("summary") != {"fail": 0, "pass": 18, "total": 18}:
        failures.append("validation_summary")
    boundary = ledger.get("current_system_boundary", {})
    forbidden_true = (
        "unified_r2_source_imported",
        "unified_r2_private_builder_called",
        "unified_r2_generator_called",
        "unified_r2_solver_input",
        "current_system_binding_passed",
    )
    if any(boundary.get(field) is not False for field in forbidden_true):
        failures.append("current_system_boundary")
    if list(HERE.rglob("*.urdf")):
        failures.append("urdf_artifact_present")
    if ledger.get("fixture", {}).get("in_memory_xml_sha256") != sha256_bytes(
        synthetic_8dof_xml_bytes()
    ):
        failures.append("fixture_hash")

    model = build_synthetic_8dof_model()
    recompute_contract = ledger.get("independent_recompute_contract", {})
    if recompute_contract.get("required_method") != (
        "EXPLICIT_SCHUR_PLUS_FIVE_POINT_TRIPLE_CHRISTOFFEL_WITHOUT_IMPORTING_REDUCED_DYNAMICS"
    ):
        failures.append("recompute_method_contract")
    cases = recompute_contract.get("cases", [])
    if len(cases) < 3:
        failures.append("recompute_case_count")
    case_receipts: list[dict[str, object]] = []
    for case in cases:
        case_id = case["case_id"]
        q = np.asarray(case["generalized_coordinates"]["values"], dtype=float)
        rates = np.asarray(case["generalized_rates"]["values"], dtype=float)
        effort = np.asarray(case["generalized_effort"]["values"], dtype=float)
        fine_steps = np.asarray(case["finite_difference"]["fine_steps"], dtype=float)
        reduced = _explicit_reduced_mass(model, q)
        derivatives = _five_point_derivatives(model, q, fine_steps)
        bias = _triple_christoffel_bias(derivatives, rates)
        acceleration = np.linalg.solve(reduced, effort - bias)
        blocks = model.mass_matrix_blocks(q)
        base_twist = -np.linalg.solve(blocks.Hbb, blocks.Hbm @ rates)
        generalized_momentum = model.mass_matrix(q) @ np.concatenate(
            (base_twist, rates)
        )
        linear_residual_ns = float(np.linalg.norm(generalized_momentum[:3]))
        angular_residual_nms = float(np.linalg.norm(generalized_momentum[3:6]))
        expected = case["main_backend_results"]
        expected_bias = np.asarray(
            expected["generalized_bias_effort_values"], dtype=float
        )
        expected_acceleration = np.asarray(
            expected["generalized_acceleration_values"], dtype=float
        )
        bias_error_revolute_nm = float(
            np.max(np.abs(bias[:6] - expected_bias[:6]))
        )
        bias_error_prismatic_n = float(
            np.max(np.abs(bias[6:] - expected_bias[6:]))
        )
        acceleration_error_revolute_rad_s2 = float(
            np.max(np.abs(acceleration[:6] - expected_acceleration[:6]))
        )
        acceleration_error_prismatic_m_s2 = float(
            np.max(np.abs(acceleration[6:] - expected_acceleration[6:]))
        )
        reduced_hash = sha256_bytes(
            np.asarray(reduced, dtype="<f8").tobytes(order="C")
        )
        case_pass = (
            bias_error_revolute_nm
            <= BIAS_ABSOLUTE_TOLERANCE_BY_TYPE["REVOLUTE_NM"]
            and bias_error_prismatic_n
            <= BIAS_ABSOLUTE_TOLERANCE_BY_TYPE["PRISMATIC_N"]
            and acceleration_error_revolute_rad_s2
            <= ACCELERATION_ABSOLUTE_TOLERANCE_BY_TYPE["REVOLUTE_RAD_S2"]
            and acceleration_error_prismatic_m_s2
            <= ACCELERATION_ABSOLUTE_TOLERANCE_BY_TYPE["PRISMATIC_M_S2"]
            and linear_residual_ns <= MOMENTUM_TOLERANCES["linear_ns"]
            and angular_residual_nms
            <= MOMENTUM_TOLERANCES["angular_about_root_nms"]
            and reduced_hash == expected["numeric_reduced_mass_sha256"]
        )
        if not case_pass:
            failures.append(f"independent_case:{case_id}")
        case_receipts.append(
            {
                "case_id": case_id,
                "pass": case_pass,
                "bias_error_revolute_nm": bias_error_revolute_nm,
                "bias_error_prismatic_n": bias_error_prismatic_n,
                "acceleration_error_revolute_rad_s2": acceleration_error_revolute_rad_s2,
                "acceleration_error_prismatic_m_s2": acceleration_error_prismatic_m_s2,
                "linear_momentum_residual_ns": linear_residual_ns,
                "angular_momentum_about_root_residual_nms": angular_residual_nms,
                "numeric_reduced_mass_sha256": reduced_hash,
                "five_point_steps": fine_steps.tolist(),
                "five_point_step_units": case["finite_difference"]["step_units"],
            }
        )

    reduced_module_imported = "sim13_v3.reduced_dynamics" in sys.modules
    if reduced_module_imported:
        failures.append("reduced_dynamics_imported")
    receipt = {
        "schema": "SIM13_V3_PHASE_A_INDEPENDENT_AUDIT_RECEIPT_V2",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "hash_chain": {
            "upstream_source_manifest": source_reference,
            "upstream_evidence_manifest": evidence_reference,
            "upstream_gate": _record(GATE_PATH, "UPSTREAM_MACHINE_GATE"),
        },
        "method": {
            "reduced_dynamics_module_imported": reduced_module_imported,
            "schur_complement": "EXPLICIT_Hmm_MINUS_Hmb_SOLVE_Hbb_Hbm",
            "mass_derivative": "EXPLICIT_FIVE_POINT_PER_COORDINATE",
            "bias": "EXPLICIT_TRIPLE_CHRISTOFFEL_SUM",
            "states_recomputed": len(case_receipts),
            "heterogeneous_momentum_norm_used": False,
            "heterogeneous_step_error_sum_used": False,
        },
        "thresholds": {
            "bias_absolute_by_coordinate_type": BIAS_ABSOLUTE_TOLERANCE_BY_TYPE,
            "acceleration_absolute_by_coordinate_type": ACCELERATION_ABSOLUTE_TOLERANCE_BY_TYPE,
            "momentum": MOMENTUM_TOLERANCES,
        },
        "source_manifest_audit": source_audit,
        "case_receipts": case_receipts,
        "urdf_files_under_v3": 0,
        "unified_r2_execution_binding": "HOLD",
        "production_dynamics": "HOLD",
        "continuous_contact_capture": "HOLD",
        "release": "HOLD",
    }
    _write_json(RECEIPT_PATH, receipt)
    outer_manifest = {
        "schema": "SIM13_V3_PHASE_A_OUTER_SELF_EXCLUDED_MANIFEST_V2",
        "self_excluded_path": OUTER_MANIFEST_PATH.relative_to(
            PROJECT_ROOT
        ).as_posix(),
        "self_hash_present": False,
        "records": [
            _record(GATE_PATH, "MACHINE_GATE"),
            _record(RECEIPT_PATH, "INDEPENDENT_AUDIT_RECEIPT"),
        ],
    }
    _write_json(OUTER_MANIFEST_PATH, outer_manifest)
    print(
        json.dumps(
            {
                "schema": receipt["schema"],
                "status": receipt["status"],
                "failures": failures,
                "source_manifest_records_verified": source_audit[
                    "records_verified"
                ],
                "independent_states_recomputed": len(case_receipts),
                "reduced_dynamics_module_imported": reduced_module_imported,
                "unified_r2_execution_binding": "HOLD",
                "urdf_files_under_v3": 0,
                "outer_manifest": OUTER_MANIFEST_PATH.relative_to(
                    PROJECT_ROOT
                ).as_posix(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

