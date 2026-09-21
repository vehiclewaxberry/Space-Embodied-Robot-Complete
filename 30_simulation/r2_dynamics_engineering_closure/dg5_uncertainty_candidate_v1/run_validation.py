from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping


PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
SRC = PACKAGE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dg5_uncertainty import build_evidence, canonical_sha256, file_sha256, jsonable, load_contract  # noqa: E402


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(value), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def build_gate(evidence: Mapping[str, Any], deterministic: bool) -> dict[str, Any]:
    mass = evidence["mass_uncertainty_audit"]
    solar = evidence["solar_r2_corner_audit"]
    holds = evidence["authority_hold_audit"]
    boundary = evidence["contract_boundary_audit"]
    checks = {
        "C01_all_16_source_hash_pins_exact": evidence["source_binding"]["all_match"] and evidence["source_binding"]["matched"] == 16,
        "C02_C01_design_mass_CG_inertia_and_standard_u_exact": mass["candidate_pass"] and mass["checks"]["all_10_estimates_u_units_distribution_dof_bound"],
        "C03_units_reference_frame_and_reference_point_explicit": mass["measurement_model"]["reference_frame"] == "S" and mass["measurement_model"]["inertia_reference_point"] == "system_center_of_mass",
        "C04_no_covariance_distribution_dof_or_coverage_invented": mass["candidate_pass"] and mass["checks"]["correlation_distribution_and_coverage_not_invented"] and mass["checks"]["deterministic_one_u_contract_exact"],
        "C05_exhaustive_1024_corner_replay_complete": mass["candidate_pass"] and mass["checks"]["all_1024_corners_evaluated_once"] and mass["checks"]["deterministic_one_u_contract_exact"],
        "C06_mass_positive_and_inertia_SPD_all_corners": mass["checks"]["all_corner_masses_positive"] and mass["checks"]["all_corner_inertia_matrices_spd"],
        "C07_triangle_invalid_corners_visible_and_quarantined": mass["checks"]["nonphysical_triangle_corners_detected_and_quarantined"] and mass["corner_audit"]["triangle_inequality_invalid"] == mass["corner_audit"]["quarantined"],
        "C08_unit_aware_OAT_sensitivity_budget_emitted": mass["checks"]["oat_sensitivity_coefficients_computed_with_units"] and mass["oat_sensitivity_budget"]["combined_u"] is None,
        "C09_bridged_nominal_crossbound_without_u_invention": mass["checks"]["bridged_nominal_crossbound_without_uncertainty_invention"],
        "C10_solar_LOW_NOMINAL_HIGH_corner_contract_exact": solar["candidate_pass"] and solar["checks"]["corner_order_parameter_units_interpretation_and_thresholds_exact"] and solar["checks"]["exact_LOW_NOMINAL_HIGH_parameter_corners_bound"],
        "C11_solar_ROM_matrix_and_frequency_replay_pass": solar["candidate_pass"] and solar["checks"]["Mrom_7x7_symmetric_positive_definite"] and solar["checks"]["all_three_K_C_7x7_symmetric_positive_definite"] and solar["checks"]["all_three_eigenfrequency_replays_bounded"],
        "C12_solar_ROM_provisional_scope_preserved": solar["candidate_pass"] and solar["checks"]["parent_ROM_gate_17_of_17_provisional_only"] and solar["checks"]["full_coupled_and_probability_credit_not_claimed"],
        "C13_current_DG1_DG2_15_of_15_bound_additively": holds["checks"]["current_DG1_DG2_candidate_gate_15_of_15_bound"] and holds["checks"]["DG1_DG2_evidence_explicitly_denies_DG5_and_release"],
        "C14_as_built_contact_actuator_nulls_preserved": all(holds["checks"][key] for key in ("as_built_mass_properties_remain_explicit_candidate_nulls", "contact_22_as_built_fields_all_null", "contact_candidate_vectors_and_uncertainty_budgets_remain_null", "actuator_8x19_measurements_all_null", "actuator_candidate_vectors_and_uncertainty_budgets_remain_null")),
        "C15_parent_DG5_remains_hold": holds["checks"]["parent_DG5_remains_HOLD_PARTIAL"] and holds["parent_DG5_satisfied"] is False,
        "C16_contract_boundary_determinism_and_no_authority_escalation": deterministic and evidence["candidate_pass"] and boundary["candidate_pass"] and holds["checks"]["no_hardware_production_next_stage_or_release_credit"],
    }
    passed = all(checks.values())
    return {
        "schema": "R2_DG5_DESIGN_UNCERTAINTY_CANDIDATE_GATE_V1",
        "technical_verdict": "DG5_BOUNDED_DESIGN_UNCERTAINTY_CANDIDATE_16_OF_16_PASS__PARENT_DG5_HOLD_AS_BUILT_CONTACT_ACTUATOR_NULL" if passed else "DG5_DESIGN_UNCERTAINTY_CANDIDATE_HOLD__SEE_FAILED_CHECKS",
        "scope": "CURRENT_R2_C01_DESIGN_STANDARD_UNCERTAINTY_AND_SOLAR_R2_THREE_CORNER_REPLAY",
        "checks": checks,
        "summary": {"passed": sum(bool(value) for value in checks.values()), "total": len(checks), "failed": [key for key, value in checks.items() if not value]},
        "design_uncertainty_candidate_satisfied": passed,
        "mass_corner_audit": {"evaluated": mass["corner_audit"]["evaluated"], "basic_rigid_body_constraints_not_falsified": mass["corner_audit"]["basic_rigid_body_constraints_not_falsified"], "quarantined": mass["corner_audit"]["quarantined"], "triangle_inequality_invalid": mass["corner_audit"]["triangle_inequality_invalid"], "corner_sequence_sha256": mass["corner_audit"]["corner_sequence_sha256"]},
        "solar_corner_replay_sha256": solar["corner_replay_sha256"],
        "parent_gate_update": "NOT_APPLIED__ADDITIVE_CANDIDATE_EVIDENCE_ONLY",
        "parent_DG5_satisfied": False,
        "as_built_mass_properties": None,
        "contact_uncertainty": None,
        "actuator_uncertainty": None,
        "dynamics_engineering_complete": False,
        "hardware_valid": False,
        "production_valid": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "review_status": "PENDING_OWNER_REVIEW",
    }


def artifact_record(path: Path, role: str) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": file_sha256(path), "role": role}


def main() -> int:
    first = build_evidence()
    second = build_evidence()
    deterministic = canonical_sha256(first) == canonical_sha256(second)
    first["determinism"] = {"exact_canonical_match": deterministic, "first_sha256_before_determinism_field": canonical_sha256(first), "second_sha256_before_determinism_field": canonical_sha256(second)}
    evidence_path = PACKAGE / "results" / "DG5_DESIGN_UNCERTAINTY_CANDIDATE_EVIDENCE_V1.json"
    gate_path = PACKAGE / "results" / "R2_DG5_DESIGN_UNCERTAINTY_CANDIDATE_GATE_V1.json"
    write_json(evidence_path, first)
    gate = build_gate(first, deterministic)
    write_json(gate_path, gate)
    local = {
        PACKAGE / "README.md": "scope and reproduction",
        PACKAGE / "contracts" / "DG5_DESIGN_UNCERTAINTY_CANDIDATE_CONTRACT_V1.json": "measurement and authority contract",
        PACKAGE / "src" / "__init__.py": "package export",
        PACKAGE / "src" / "dg5_uncertainty.py": "deterministic evaluator",
        PACKAGE / "run_validation.py": "evidence, gate and manifest builder",
        PACKAGE / "tests" / "test_dg5_uncertainty.py": "positive and fail-closed negative controls",
        PACKAGE / "pytest.ini": "test configuration",
        evidence_path: "generated evidence",
        gate_path: "generated additive candidate gate",
    }
    if not all(path.is_file() for path in local):
        raise RuntimeError("required artifact missing")
    contract = load_contract()
    external = {key: {"path": pin["path"], "bytes": pin["bytes"], "sha256": pin["sha256"], "role": "hash-pinned external input"} for key, pin in contract["source_pins"].items()}
    manifest = {
        "schema": "DG5_DESIGN_UNCERTAINTY_CANDIDATE_MANIFEST_V1",
        "local_artifacts": [artifact_record(path, role) for path, role in local.items()],
        "external_input_pins": external,
        "summary": {"local_count": len(local), "external_pin_count": len(external), "all_exist": True},
        "design_uncertainty_candidate_satisfied": gate["design_uncertainty_candidate_satisfied"],
        "parent_DG5_satisfied": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    manifest_path = PACKAGE / "results" / "DG5_DESIGN_UNCERTAINTY_CANDIDATE_MANIFEST_V1.json"
    write_json(manifest_path, manifest)
    print(gate["technical_verdict"])
    print(f"checks={gate['summary']['passed']}/{gate['summary']['total']}")
    print(f"mass_corners={gate['mass_corner_audit']['evaluated']} quarantined={gate['mass_corner_audit']['quarantined']}")
    return 0 if gate["design_uncertainty_candidate_satisfied"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
