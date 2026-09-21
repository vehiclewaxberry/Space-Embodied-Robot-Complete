"""Generate deterministic evidence, bounded gate, manifest, and checksums."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
from typing import Any, Mapping


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
SRC = PACKAGE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dg1_dg2_candidate import (  # noqa: E402
    canonical_sha256,
    file_sha256,
    jsonable,
    load_contract,
    run_candidate,
)


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(jsonable(value), indent=2, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build_gate(evidence: Mapping[str, Any], deterministic: bool) -> dict[str, Any]:
    contract = load_contract()
    dg1_checks = {} if evidence.get("dg1") is None else evidence["dg1"]["checks"]
    dg2_checks = {} if evidence.get("dg2") is None else evidence["dg2"]["checks"]
    checks = {
        "C01_source_pins_exact": evidence["source_binding"]["all_match"] is True,
        "C02_DG1_reference_metric_declared": dg1_checks.get(
            "reference_scales_equal_finite_URDF_joint_spans", False
        )
        is True,
        "C03_DG1_energy_and_virtual_power_invariant": all(
            dg1_checks.get(name, False)
            for name in (
                "energy_invariant_under_reference_metric",
                "energy_invariant_under_alternate_metric",
                "virtual_power_invariant_under_reference_metric",
                "virtual_power_invariant_under_alternate_metric",
            )
        ),
        "C04_DG1_physical_acceleration_invariant": all(
            dg1_checks.get(name, False)
            for name in (
                "reference_revolute_acceleration_invariant",
                "reference_prismatic_acceleration_invariant",
                "alternate_revolute_acceleration_invariant",
                "alternate_prismatic_acceleration_invariant",
            )
        ),
        "C05_DG2_nonzero_momentum_case": dg2_checks.get(
            "nonzero_linear_momentum_case", False
        )
        and dg2_checks.get("nonzero_angular_momentum_case", False),
        "C06_DG2_base_pose_integrated": dg2_checks.get(
            "base_position_integrated", False
        )
        and dg2_checks.get("base_attitude_integrated", False),
        "C07_DG2_per_body_linear_momentum_conserved": dg2_checks.get(
            "RK4_linear_momentum_conserved_by_per_body_sum", False
        )
        and dg2_checks.get(
            "DOP853_linear_momentum_conserved_by_per_body_sum", False
        ),
        "C08_DG2_per_body_angular_momentum_conserved": dg2_checks.get(
            "RK4_angular_momentum_conserved_by_per_body_sum", False
        )
        and dg2_checks.get(
            "DOP853_angular_momentum_conserved_by_per_body_sum", False
        ),
        "C09_DG2_matrix_vs_body_cross": dg2_checks.get(
            "matrix_vs_body_linear_cross_bounded", False
        )
        and dg2_checks.get("matrix_vs_body_angular_cross_bounded", False),
        "C10_DG2_solver_cross": all(
            dg2_checks.get(name, False)
            for name in (
                "RK4_DOP853_position_cross_bounded",
                "RK4_DOP853_orientation_cross_bounded",
                "RK4_DOP853_revolute_joint_cross_bounded",
                "RK4_DOP853_prismatic_joint_cross_bounded",
            )
        ),
        "C11_DG2_quaternion_and_limits": dg2_checks.get(
            "quaternion_norm_bounded", False
        )
        and dg2_checks.get("joint_limits_respected", False),
        "C12_deterministic_replay": deterministic,
        "C13_no_execution_guard_triggered": all(
            value is False for value in contract["execution_guards"].values()
        ),
        "C14_parent_gate_not_mutated": evidence.get("parent_gate_mutated") is False,
        "C15_no_hardware_or_release_credit": evidence.get("hardware_valid") is False
        and evidence.get("release_credit") is False
        and evidence.get("next_stage_authorized") is False,
    }
    passed = all(checks.values())
    return {
        "schema": "R2_DG1_DG2_CANDIDATE_GATE_V2",
        "technical_verdict": (
            "DG1_DG2_CANDIDATE_15_OF_15_PASS__PARENT_DYNAMICS_GATE_REMAINS_HOLD_DG3_DG4_DG5"
            if passed
            else "DG1_DG2_CANDIDATE_HOLD__SEE_FAILED_CHECKS"
        ),
        "scope": "CURRENT_R2_DG1_REFERENCE_METRIC_AND_DG2_PRESCRIBED_MOTION_NONZERO_MOMENTUM",
        "checks": checks,
        "summary": {
            "passed": sum(bool(value) for value in checks.values()),
            "total": len(checks),
            "failed": [name for name, value in checks.items() if not value],
        },
        "candidate_DG1_satisfied": bool(evidence.get("dg1", {}).get("candidate_pass", False)),
        "candidate_DG2_satisfied": bool(evidence.get("dg2", {}).get("candidate_pass", False)),
        "candidate_package_complete": passed,
        "parent_gate_update": "NOT_APPLIED__ADDITIVE_CANDIDATE_EVIDENCE_ONLY",
        "remaining_parent_holds": [
            "DG3_ARM_TO_FLEX_TIME_DOMAIN_COUPLING_NOT_IMPLEMENTED",
            "DG4_CONTACT_HYBRID_AND_TARGET_ATTACHMENT_NOT_IMPLEMENTED",
            "DG5_AS_BUILT_MASS_CONTACT_ACTUATOR_UNCERTAINTY_OPEN"
        ],
        "dynamics_engineering_complete": False,
        "hardware_valid": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "review_status": "PENDING_OWNER_REVIEW"
    }


def artifact_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        rows.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    return rows


def main() -> int:
    first = run_candidate()
    second = run_candidate()
    deterministic = canonical_sha256(first) == canonical_sha256(second)
    first["determinism"] = {
        "exact_canonical_match": deterministic,
        "first_sha256": canonical_sha256(first),
        "second_sha256_before_determinism_field": canonical_sha256(second),
    }
    evidence_path = PACKAGE / "results" / "DG1_DG2_CANDIDATE_EVIDENCE_V2.json"
    gate_path = PACKAGE / "results" / "R2_DG1_DG2_CANDIDATE_GATE_V2.json"
    write_json(evidence_path, first)
    gate = build_gate(first, deterministic)
    write_json(gate_path, gate)

    required = [
        PACKAGE / "README.md",
        PACKAGE / "contracts" / "DG1_DG2_CANDIDATE_CONTRACT_V2.json",
        PACKAGE / "src" / "__init__.py",
        PACKAGE / "src" / "dg1_dg2_candidate.py",
        PACKAGE / "run_validation.py",
        PACKAGE / "tests" / "test_dg1_dg2_candidate.py",
        evidence_path,
        gate_path,
    ]
    if not all(path.is_file() for path in required):
        raise RuntimeError("REQUIRED_ARTIFACT_MISSING")
    rows = artifact_rows(required)
    manifest = {
        "schema": "DG1_DG2_CANDIDATE_PACKAGE_MANIFEST_V2",
        "artifacts": rows,
        "summary": {"count": len(rows), "all_exist": True},
        "candidate_package_complete": gate["candidate_package_complete"],
        "next_stage_authorized": False,
        "release_credit": False,
    }
    manifest_path = PACKAGE / "results" / "DG1_DG2_CANDIDATE_PACKAGE_MANIFEST_V2.json"
    write_json(manifest_path, manifest)
    checksum_rows = artifact_rows(required + [manifest_path])
    checksum_path = PACKAGE / "results" / "DG1_DG2_CANDIDATE_SHA256_V2.csv"
    with checksum_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("path", "bytes", "sha256"))
        writer.writeheader()
        writer.writerows(checksum_rows)
    print(gate["technical_verdict"])
    print(f"checks={gate['summary']['passed']}/{gate['summary']['total']}")
    print(f"evidence={evidence_path.relative_to(ROOT).as_posix()}")
    return 0 if gate["candidate_package_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
