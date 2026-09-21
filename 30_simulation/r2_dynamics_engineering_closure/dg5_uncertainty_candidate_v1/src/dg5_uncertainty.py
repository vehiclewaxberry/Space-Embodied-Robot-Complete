from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import yaml


PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]
CONTRACT_PATH = PACKAGE / "contracts" / "DG5_DESIGN_UNCERTAINTY_CANDIDATE_CONTRACT_V1.json"

EXPECTED_AUTHORITY_SCOPE = "CURRENT_R2_C01_DESIGN_LEVEL_UNCERTAINTY_AND_DETERMINISTIC_REPLAY_ONLY"
EXPECTED_ALLOWED_CLAIMS = [
    "hash-bound CURRENT_R2 C01 design mass/CG/inertia standard-uncertainty intake",
    "exhaustive deterministic plus/minus one-standard-uncertainty hypercube screening",
    "Solar R2 LOW/NOMINAL/HIGH seven-mode ROM corner replay",
    "binding to the current additive DG1/DG2 candidate gate",
]
EXPECTED_FORBIDDEN_CLAIMS = [
    "GUM combined or expanded uncertainty without covariance, distributions and degrees of freedom",
    "probabilistic coverage claim for the plus/minus one-u hypercube",
    "as-built mass-property claim",
    "contact or actuator uncertainty propagation",
    "full parent DG5 closure",
    "hardware, production, next-stage or release credit",
]
EXPECTED_EXTERNAL_AUTHORITY_NULLS = {
    "as_built_mass_kg": None,
    "as_built_cg_xyz_m": None,
    "as_built_inertia_components_kg_m2": None,
    "as_built_mass_property_uncertainty_budget": None,
    "contact_as_built_parameter_vector": None,
    "contact_as_built_uncertainty_budget": None,
    "actuator_8dof_parameter_vector": None,
    "actuator_8dof_uncertainty_budget": None,
}
EXPECTED_EXECUTION_GUARDS = {
    "random_sampling_used": False,
    "contact_called": False,
    "actuator_model_instantiated": False,
    "as_built_value_filled": False,
    "parent_gate_mutated": False,
    "hardware_claimed": False,
    "production_claimed": False,
}
EXPECTED_SOLAR_PARAMETER_UNITS = {
    "EI": "N*m^2",
    "GJ": "N*m^2",
    "k_root": "N*m/rad",
    "k_inter": "N*m/rad",
    "zeta": "1",
    "frequency": "Hz",
}
EXPECTED_SOLAR_INTERPRETATION = (
    "THREE_DISCRETE_PROVISIONAL_DESIGN_CORNERS__NOT_A_PROBABILITY_DISTRIBUTION"
)
EXPECTED_CONTRACT_CANONICAL_SHA256 = (
    "B84C4047811B8CD0A5F11AFE3545DB8F7101B548F422A21AEAE1361FF14ED0DB"
)
EXPECTED_MEASUREMENT_MODEL_IDENTITY = {
    "measurand": "CURRENT_R2 C01 design mass properties in S at the system center of mass",
    "configuration_id": "C01",
    "configuration_name": "DEPLOYED_NOMINAL",
    "inertia_matrix_convention": "[[Ixx,Ixy,Ixz],[Ixy,Iyy,Iyz],[Ixz,Iyz,Izz]]",
    "derived_measurands": {
        "mass": "kg",
        "cg_offset_norm": "m",
        "principal_inertia_min_mid_max": "kg*m^2",
        "inertia_condition_number": "1",
        "principal_triangle_margin": "kg*m^2",
        "radius_of_gyration_sqrt_trace_over_2m": "m",
    },
}


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicates)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected YAML mapping: {path}")
    return value


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return load_json(path)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest().upper()


def source_binding(contract: Mapping[str, Any]) -> dict[str, Any]:
    records: dict[str, Any] = {}
    for key, pin in contract["source_pins"].items():
        path = ROOT / pin["path"]
        exists = path.is_file()
        actual_bytes = path.stat().st_size if exists else None
        actual_sha = file_sha256(path) if exists else None
        records[key] = {
            "path": pin["path"],
            "expected_bytes": pin["bytes"],
            "actual_bytes": actual_bytes,
            "expected_sha256": pin["sha256"],
            "actual_sha256": actual_sha,
            "match": exists and actual_bytes == pin["bytes"] and actual_sha == pin["sha256"],
        }
    return {
        "matched": sum(row["match"] for row in records.values()),
        "total": len(records),
        "all_match": all(row["match"] for row in records.values()),
        "records": records,
    }


def _c01_mass_record(mass_ledger: Mapping[str, Any]) -> dict[str, Any]:
    matches = [row for row in mass_ledger["configurations"] if row.get("configuration_id") == "C01"]
    if len(matches) != 1:
        raise ValueError("expected exactly one C01 mass record")
    return matches[0]


def _input_vector(contract: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    model = contract["measurement_model"]
    inputs = model["inputs"]
    order = model["input_order"]
    estimates = np.asarray([inputs[name]["estimate"] for name in order], dtype=np.float64)
    standard_uncertainties = np.asarray([inputs[name]["standard_uncertainty"] for name in order], dtype=np.float64)
    return estimates, standard_uncertainties


def _inertia_from_vector(values: np.ndarray) -> np.ndarray:
    ixx, iyy, izz, ixy, ixz, iyz = values[4:10]
    return np.asarray([[ixx, ixy, ixz], [ixy, iyy, iyz], [ixz, iyz, izz]], dtype=np.float64)


def derived_metrics(values: np.ndarray) -> dict[str, float | bool]:
    mass = float(values[0])
    cg = values[1:4]
    inertia = _inertia_from_vector(values)
    eigenvalues = np.linalg.eigvalsh(inertia)
    min_eig, mid_eig, max_eig = (float(x) for x in eigenvalues)
    triangle_margin = min_eig + mid_eig - max_eig
    spd = min_eig > 0.0
    triangle_valid = triangle_margin >= -1e-14
    radius = math.sqrt(float(np.trace(inertia)) / (2.0 * mass)) if mass > 0.0 and float(np.trace(inertia)) > 0.0 else float("nan")
    return {
        "mass_kg": mass,
        "cg_offset_norm_m": float(np.linalg.norm(cg)),
        "principal_inertia_min_kg_m2": min_eig,
        "principal_inertia_mid_kg_m2": mid_eig,
        "principal_inertia_max_kg_m2": max_eig,
        "inertia_condition_number": max_eig / min_eig if spd else float("inf"),
        "principal_triangle_margin_kg_m2": triangle_margin,
        "radius_of_gyration_m": radius,
        "mass_positive": mass > 0.0,
        "inertia_spd": spd,
        "rigid_body_triangle_inequalities": triangle_valid,
    }


def audit_mass_uncertainty(contract: Mapping[str, Any], mass_ledger: Mapping[str, Any], bridged_ledger: Mapping[str, Any]) -> dict[str, Any]:
    c01 = _c01_mass_record(mass_ledger)
    model = contract["measurement_model"]
    inputs = model["inputs"]
    order = model["input_order"]
    expected_order = [
        "mass", "cg_x", "cg_y", "cg_z", "Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz"
    ]
    expected_units = {
        "mass": "kg",
        "cg_x": "m",
        "cg_y": "m",
        "cg_z": "m",
        "Ixx": "kg*m^2",
        "Iyy": "kg*m^2",
        "Izz": "kg*m^2",
        "Ixy": "kg*m^2",
        "Ixz": "kg*m^2",
        "Iyz": "kg*m^2",
    }
    source_estimates = {
        "mass": c01["mass"]["value_kg"],
        "cg_x": c01["center_of_mass"]["xyz_m"][0],
        "cg_y": c01["center_of_mass"]["xyz_m"][1],
        "cg_z": c01["center_of_mass"]["xyz_m"][2],
        **{name: c01["inertia"]["components_kg_m2"][name] for name in ("Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz")},
    }
    source_u = {
        "mass": c01["mass"]["standard_uncertainty_kg"],
        "cg_x": c01["center_of_mass"]["standard_uncertainty_xyz_m"][0],
        "cg_y": c01["center_of_mass"]["standard_uncertainty_xyz_m"][1],
        "cg_z": c01["center_of_mass"]["standard_uncertainty_xyz_m"][2],
        **{name: c01["inertia"]["standard_uncertainty_components_kg_m2"][name] for name in ("Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz")},
    }
    input_checks = {
        name: {
            "estimate_exact": source_estimates[name] == inputs[name]["estimate"],
            "standard_uncertainty_exact": source_u[name] == inputs[name]["standard_uncertainty"],
            "unit_exact_for_named_measurand": inputs[name]["unit"] == expected_units[name],
            "source_distribution_explicit": inputs[name]["source_distribution"] == "UNSPECIFIED",
            "degrees_of_freedom_explicit_null": inputs[name]["degrees_of_freedom"] is None,
        }
        for name in order
    }
    metadata_complete = order == expected_order and set(inputs) == set(expected_order) and all(
        all(row.values()) for row in input_checks.values()
    )

    propagation = model["propagation"]
    deterministic_one_u_contract_exact = (
        model.get("uncertainty_semantics")
        == "SOURCE_FIELDS_ARE_STANDARD_UNCERTAINTIES__NOT_TOLERANCE_BOUNDS"
        and model.get("correlation_model") is None
        and model.get("correlation_disposition")
        == "TOP_LEVEL_COVARIANCE_NOT_PROVIDED__NO_CORRELATION_INVENTED__NO_COMBINED_U"
        and propagation.get("method") == "EXHAUSTIVE_LEXICOGRAPHIC_SIGN_HYPERCUBE"
        and propagation.get("u_scale") == 1.0
        and propagation.get("corner_count") == 1024
        and propagation.get("random_seed") is None
        and propagation.get("statistical_coverage_probability") is None
        and propagation.get("coverage_factor") is None
        and propagation.get("combined_standard_uncertainty") is None
        and propagation.get("interpretation")
        == "DESIGN_SCREENING_ONLY__PLUS_MINUS_ONE_U_IS_NOT_A_COVERAGE_REGION"
    )

    estimates, standard_uncertainties = _input_vector(contract)
    corner_records: list[dict[str, Any]] = []
    extrema_keys = [
        "mass_kg", "cg_offset_norm_m", "principal_inertia_min_kg_m2",
        "principal_inertia_mid_kg_m2", "principal_inertia_max_kg_m2",
        "inertia_condition_number", "principal_triangle_margin_kg_m2",
        "radius_of_gyration_m",
    ]
    for index, signs in enumerate(itertools.product((-1.0, 1.0), repeat=len(order))):
        sign_vector = np.asarray(signs, dtype=np.float64)
        values = estimates + standard_uncertainties * sign_vector
        metrics = derived_metrics(values)
        corner_records.append({
            "index": index,
            "sign_bits": "".join("1" if sign > 0 else "0" for sign in signs),
            "metrics": metrics,
            "admission": "BASIC_RIGID_BODY_CONSTRAINTS_NOT_FALSIFIED" if metrics["mass_positive"] and metrics["inertia_spd"] and metrics["rigid_body_triangle_inequalities"] else "QUARANTINED_BASIC_RIGID_BODY_CONSTRAINT_FAILURE",
        })
    not_falsified = [
        row
        for row in corner_records
        if row["admission"] == "BASIC_RIGID_BODY_CONSTRAINTS_NOT_FALSIFIED"
    ]
    quarantined = [
        row
        for row in corner_records
        if row["admission"] != "BASIC_RIGID_BODY_CONSTRAINTS_NOT_FALSIFIED"
    ]
    extrema = {
        key: {
            "minimum": min(float(row["metrics"][key]) for row in corner_records),
            "maximum": max(float(row["metrics"][key]) for row in corner_records),
            "unit": model["derived_measurands"][{
                "mass_kg": "mass",
                "cg_offset_norm_m": "cg_offset_norm",
                "principal_inertia_min_kg_m2": "principal_inertia_min_mid_max",
                "principal_inertia_mid_kg_m2": "principal_inertia_min_mid_max",
                "principal_inertia_max_kg_m2": "principal_inertia_min_mid_max",
                "inertia_condition_number": "inertia_condition_number",
                "principal_triangle_margin_kg_m2": "principal_triangle_margin",
                "radius_of_gyration_m": "radius_of_gyration_sqrt_trace_over_2m",
            }[key]],
        }
        for key in extrema_keys
    }

    nominal_metrics = derived_metrics(estimates)
    sensitivities: dict[str, Any] = {}
    for i, name in enumerate(order):
        plus = estimates.copy(); plus[i] += standard_uncertainties[i]
        minus = estimates.copy(); minus[i] -= standard_uncertainties[i]
        plus_metrics = derived_metrics(plus)
        minus_metrics = derived_metrics(minus)
        sensitivities[name] = {
            key: {
                "central_sensitivity_per_input_unit": (float(plus_metrics[key]) - float(minus_metrics[key])) / (2.0 * standard_uncertainties[i]),
                "half_difference_contribution_at_one_u": (float(plus_metrics[key]) - float(minus_metrics[key])) / 2.0,
                "output_unit": extrema[key]["unit"],
                "input_unit": inputs[name]["unit"],
            }
            for key in extrema_keys
        }

    bridge_rows = [row for row in bridged_ledger["configurations"] if row.get("configuration_id") == "C01"]
    if len(bridge_rows) != 1:
        raise ValueError("expected exactly one bridged C01")
    bridge = bridge_rows[0]
    stated_matrix = np.asarray(bridge["v3_r2_stated"]["inertia_about_system_cg_S_kg_m2"], dtype=np.float64)
    contract_matrix = _inertia_from_vector(estimates)
    bridge_uncertainty_null_count = sum(
        row.get("bridge_provenance", {}).get("bridge_uncertainty") is None
        for row in bridge.get("composition_candidate", [])
        if "bridge_provenance" in row
    )
    bridge_audit = {
        "stated_mass_matches_design": bridge["v3_r2_stated"]["mass_kg"] == estimates[0],
        "stated_cg_matches_design": np.array_equal(np.asarray(bridge["v3_r2_stated"]["cg_S_m"]), estimates[1:4]),
        "stated_inertia_matches_design": np.array_equal(stated_matrix, contract_matrix),
        "bridged_mass_invariant": bridge["bridged_candidate"]["mass_kg"] == estimates[0],
        "bridged_nominal_diff_disclosed": bridge["candidate_minus_stated"]["cg_norm_m"] > 0.0 and bridge["candidate_minus_stated"]["inertia_max_abs"] > 0.0,
        "bridge_uncertainty_policy_explicit_null": "bridge uncertainty = null" in bridged_ledger["uncertainty_policy"] and bridge_uncertainty_null_count >= 1,
        "bridged_top_level_uncertainty_propagated": False,
    }
    checks = {
        "C01_unique_and_named_deployed_nominal": c01.get("name") == "DEPLOYED_NOMINAL",
        "all_10_estimates_u_units_distribution_dof_bound": metadata_complete,
        "all_standard_uncertainties_positive": bool(np.all(standard_uncertainties > 0.0)),
        "correlation_distribution_and_coverage_not_invented": model["correlation_model"] is None and propagation["statistical_coverage_probability"] is None and propagation["coverage_factor"] is None and propagation["combined_standard_uncertainty"] is None,
        "deterministic_one_u_contract_exact": deterministic_one_u_contract_exact,
        "all_1024_corners_evaluated_once": len(corner_records) == 2 ** len(order) and len({row["sign_bits"] for row in corner_records}) == len(corner_records),
        "all_corner_masses_positive": all(row["metrics"]["mass_positive"] for row in corner_records),
        "all_corner_inertia_matrices_spd": all(row["metrics"]["inertia_spd"] for row in corner_records),
        "nonphysical_triangle_corners_detected_and_quarantined": len(quarantined) > 0 and all(not row["metrics"]["rigid_body_triangle_inequalities"] for row in quarantined),
        "oat_sensitivity_coefficients_computed_with_units": len(sensitivities) == 10 and all(len(rows) == len(extrema_keys) for rows in sensitivities.values()),
        "bridged_nominal_crossbound_without_uncertainty_invention": all(
            bool(value)
            for key, value in bridge_audit.items()
            if key != "bridged_top_level_uncertainty_propagated"
        )
        and bridge_audit["bridged_top_level_uncertainty_propagated"] is False,
    }
    return {
        "schema": "DG5_C01_DESIGN_UNCERTAINTY_AUDIT_V1",
        "measurement_model": {
            "configuration_id": "C01",
            "reference_frame": c01["center_of_mass"]["reference_frame"],
            "inertia_reference_point": c01["inertia"]["reference_point"],
            "input_order": order,
            "input_checks": input_checks,
            "source_uncertainty_policy": c01["uncertainty_policy"],
            "correlation_model": None,
            "combined_standard_uncertainty": None,
            "coverage_probability": None,
            "interpretation": model["propagation"]["interpretation"],
        },
        "nominal_metrics": nominal_metrics,
        "corner_audit": {
            "algorithm": "itertools.product((-1,+1), repeat=10), lexicographic",
            "u_scale": 1.0,
            "evaluated": len(corner_records),
            "basic_rigid_body_constraints_not_falsified": len(not_falsified),
            "quarantined": len(quarantined),
            "mass_nonpositive": sum(not row["metrics"]["mass_positive"] for row in corner_records),
            "inertia_non_spd": sum(not row["metrics"]["inertia_spd"] for row in corner_records),
            "triangle_inequality_invalid": sum(not row["metrics"]["rigid_body_triangle_inequalities"] for row in corner_records),
            "corner_sequence_sha256": canonical_sha256(corner_records),
            "extrema_all_corners": extrema,
        },
        "oat_sensitivity_budget": {
            "method": "CENTRAL_ONE_AT_A_TIME_PLUS_MINUS_ONE_STANDARD_UNCERTAINTY",
            "combined_u": None,
            "reason_combined_u_null": "TOP_LEVEL_COVARIANCE_DISTRIBUTIONS_AND_DOF_NOT_PROVIDED",
            "coefficients": sensitivities,
        },
        "bridge_crossbind": bridge_audit,
        "checks": checks,
        "candidate_pass": all(checks.values()),
    }


def audit_solar_rom(contract: Mapping[str, Any], rom: Mapping[str, Any], envelope: Mapping[str, Any], rom_gate: Mapping[str, Any]) -> dict[str, Any]:
    corner_contract = contract["solar_r2_corner_contract"]
    order = corner_contract["corner_order"]
    m = np.asarray(rom["Mrom"], dtype=np.float64)
    m_sym = (m + m.T) / 2.0
    m_eig = np.linalg.eigvalsh(m_sym)
    rows: dict[str, Any] = {}
    for corner in order:
        k = np.asarray(rom["Krom_by_corner"][corner], dtype=np.float64)
        c = np.asarray(rom["Crom_by_corner"][corner], dtype=np.float64)
        k_sym = (k + k.T) / 2.0
        c_sym = (c + c.T) / 2.0
        l = np.linalg.cholesky(m_sym)
        transformed = np.linalg.solve(l, k_sym)
        transformed = np.linalg.solve(l, transformed.T).T
        frequency = np.sqrt(np.maximum(np.linalg.eigvalsh((transformed + transformed.T) / 2.0), 0.0)) / (2.0 * np.pi)
        stored = np.asarray(rom["rom_eigenfrequencies_by_corner_hz"][corner], dtype=np.float64)
        k_scale = max(float(np.max(np.abs(k))), 1.0)
        c_scale = max(float(np.max(np.abs(c))), 1.0)
        relative = np.abs(frequency - stored) / np.maximum(np.abs(stored), 1e-30)
        rows[corner] = {
            "parameter_values": envelope["parameter_corners"][corner],
            "M_min_eigenvalue": float(np.min(m_eig)),
            "K_min_eigenvalue": float(np.min(np.linalg.eigvalsh(k_sym))),
            "C_min_eigenvalue": float(np.min(np.linalg.eigvalsh(c_sym))),
            "M_symmetry_max_abs": float(np.max(np.abs(m - m.T))),
            "K_symmetry_relative": float(np.max(np.abs(k - k.T)) / k_scale),
            "C_symmetry_relative": float(np.max(np.abs(c - c.T)) / c_scale),
            "recomputed_frequencies_hz": frequency.tolist(),
            "stored_frequencies_hz": stored.tolist(),
            "frequency_replay_max_relative": float(np.max(relative)),
        }
    monotonic_parameters = all(
        envelope["parameter_corners"]["LOW"][key] < envelope["parameter_corners"]["NOMINAL"][key] < envelope["parameter_corners"]["HIGH"][key]
        for key in ("EI", "GJ", "k_root", "k_inter", "zeta")
    )
    stored_matrix = np.asarray([rows[corner]["stored_frequencies_hz"] for corner in order])
    checks = {
        "corner_order_parameter_units_interpretation_and_thresholds_exact": (
            order == ["LOW", "NOMINAL", "HIGH"]
            and corner_contract.get("parameter_units") == EXPECTED_SOLAR_PARAMETER_UNITS
            and corner_contract.get("interpretation") == EXPECTED_SOLAR_INTERPRETATION
            and corner_contract.get("matrix_symmetry_relative_max") == 2.0e-11
            and corner_contract.get("eigenfrequency_replay_relative_max") == 1.0e-10
        ),
        "exact_LOW_NOMINAL_HIGH_parameter_corners_bound": envelope["parameter_corners"] == corner_contract["parameter_corners"],
        "Mrom_7x7_symmetric_positive_definite": m.shape == (7, 7) and float(np.max(np.abs(m - m.T))) <= corner_contract["matrix_symmetry_relative_max"] and float(np.min(m_eig)) > 0.0,
        "all_three_K_C_7x7_symmetric_positive_definite": all(rows[corner]["K_min_eigenvalue"] > 0.0 and rows[corner]["C_min_eigenvalue"] > 0.0 and rows[corner]["K_symmetry_relative"] <= corner_contract["matrix_symmetry_relative_max"] and rows[corner]["C_symmetry_relative"] <= corner_contract["matrix_symmetry_relative_max"] for corner in order),
        "all_three_eigenfrequency_replays_bounded": all(rows[corner]["frequency_replay_max_relative"] <= corner_contract["eigenfrequency_replay_relative_max"] for corner in order),
        "corner_parameters_and_sorted_frequencies_monotonic": monotonic_parameters and bool(np.all(stored_matrix[0] < stored_matrix[1])) and bool(np.all(stored_matrix[1] < stored_matrix[2])),
        "parent_ROM_gate_17_of_17_provisional_only": rom_gate.get("technical_verdict") == "PASS_WITH_DECLARED_PROVISIONAL_PHYSICS" and rom_gate.get("summary") == {"passed": 17, "total": 17} and rom_gate.get("next_stage_authorized") is False and rom_gate.get("release_credit") is False,
        "full_coupled_and_probability_credit_not_claimed": envelope.get("r2_coupled_diagnostics") == "NOT_EVALUATED" and envelope.get("e15_inheritance") == "NOT_INHERITED" and corner_contract.get("interpretation") == EXPECTED_SOLAR_INTERPRETATION,
    }
    return {
        "schema": "DG5_SOLAR_R2_CORNER_REPLAY_V1",
        "corner_order": order,
        "corner_results": rows,
        "corner_replay_sha256": canonical_sha256(rows),
        "checks": checks,
        "candidate_pass": all(checks.values()),
    }


def audit_contract_boundary(contract: Mapping[str, Any]) -> dict[str, Any]:
    model = contract.get("measurement_model", {})
    checks = {
        "entire_contract_canonical_sha256_exact": (
            canonical_sha256(contract) == EXPECTED_CONTRACT_CANONICAL_SHA256
        ),
        "schema_and_decision_rule_exact": (
            contract.get("schema") == "DG5_DESIGN_UNCERTAINTY_CANDIDATE_CONTRACT_V1"
            and contract.get("decision_rule")
            == "Authority > Evidence > Independent reproduction > Agent opinion"
        ),
        "authority_scope_exact": contract.get("authority_scope") == EXPECTED_AUTHORITY_SCOPE,
        "measurement_model_identity_and_derived_units_exact": (
            isinstance(model, Mapping)
            and all(model.get(key) == value for key, value in EXPECTED_MEASUREMENT_MODEL_IDENTITY.items())
        ),
        "claim_boundary_exact": contract.get("claim_boundary")
        == {
            "allowed": EXPECTED_ALLOWED_CLAIMS,
            "forbidden": EXPECTED_FORBIDDEN_CLAIMS,
        },
        "external_authority_nulls_exact": contract.get("external_authority_nulls")
        == EXPECTED_EXTERNAL_AUTHORITY_NULLS,
        "execution_guards_exact": contract.get("execution_guards") == EXPECTED_EXECUTION_GUARDS,
        "review_and_release_boundary_exact": (
            contract.get("review_status") == "PENDING_OWNER_REVIEW"
            and contract.get("next_stage_authorized") is False
            and contract.get("release_credit") is False
        ),
    }
    return {
        "schema": "DG5_CONTRACT_AUTHORITY_BOUNDARY_AUDIT_V1",
        "checks": checks,
        "candidate_pass": all(checks.values()),
        "authority_scope": contract.get("authority_scope"),
        "next_stage_authorized": False,
        "release_credit": False,
    }


def _collect_named_values(value: Any, key_name: str) -> list[Any]:
    found: list[Any] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == key_name:
                found.append(item)
            found.extend(_collect_named_values(item, key_name))
    elif isinstance(value, list):
        for item in value:
            found.extend(_collect_named_values(item, key_name))
    return found


def audit_authority_holds(
    contract: Mapping[str, Any],
    dg_gate: Mapping[str, Any],
    dg_evidence: Mapping[str, Any],
    parent_gate: Mapping[str, Any],
    parent_authority: Mapping[str, Any],
    mass_ref: Mapping[str, Any],
    contact: Mapping[str, Any],
    actuator: Mapping[str, Any],
) -> dict[str, Any]:
    parent_dg5 = [row for row in parent_gate["gate_rows"] if row.get("id") == "DG5"]
    contact_as_built = _collect_named_values(contact, "as_built")
    required_fields = actuator["required_measurement_fields"]
    actuator_measurements = [value for joint in actuator["joint_records"] for value in joint["measurements"].values()]
    nulls = contract["external_authority_nulls"]
    checks = {
        "current_DG1_DG2_candidate_gate_15_of_15_bound": dg_gate.get("summary") == {"passed": 15, "total": 15, "failed": []} and dg_gate.get("candidate_DG1_satisfied") is True and dg_gate.get("candidate_DG2_satisfied") is True and dg_gate.get("parent_gate_update") == "NOT_APPLIED__ADDITIVE_CANDIDATE_EVIDENCE_ONLY",
        "DG1_DG2_evidence_explicitly_denies_DG5_and_release": dg_evidence.get("candidate_pass") is True and "NO_DG3_DG4_DG5_OR_RELEASE_CREDIT" in dg_evidence.get("technical_verdict", "") and dg_evidence.get("next_stage_authorized") is False and dg_evidence.get("release_credit") is False,
        "parent_DG5_remains_HOLD_PARTIAL": len(parent_dg5) == 1 and parent_dg5[0].get("status") == "HOLD_PARTIAL" and parent_dg5[0].get("satisfied") is False and parent_gate.get("dynamics_engineering_complete") is False,
        "as_built_mass_properties_remain_explicit_candidate_nulls": all(value is None for key, value in nulls.items() if key.startswith("as_built_")) and parent_authority["configuration_classes"]["CURRENT_R2"]["as_built_status"] == "MEASUREMENT_PENDING" and mass_ref.get("as_built_metrology") == "HOLD_EXTERNAL_MEASUREMENT_PENDING",
        "contact_22_as_built_fields_all_null": len(contact_as_built) == 22 and all(value is None for value in contact_as_built) and contact.get("zero_fill_forbidden") is True and contact.get("next_stage_authorized") is False,
        "contact_candidate_vectors_and_uncertainty_budgets_remain_null": nulls["contact_as_built_parameter_vector"] is None and nulls["contact_as_built_uncertainty_budget"] is None,
        "actuator_8x19_measurements_all_null": len(actuator["joint_records"]) == 8 and len(required_fields) == 19 and len(actuator_measurements) == 152 and all(value is None for value in actuator_measurements) and all(set(joint["measurements"]) == set(required_fields) for joint in actuator["joint_records"]),
        "actuator_candidate_vectors_and_uncertainty_budgets_remain_null": nulls["actuator_8dof_parameter_vector"] is None and nulls["actuator_8dof_uncertainty_budget"] is None and actuator.get("hardware_model_valid") is False and actuator.get("zero_fill_forbidden") is True,
        "no_hardware_production_next_stage_or_release_credit": contract["execution_guards"] == {"random_sampling_used": False, "contact_called": False, "actuator_model_instantiated": False, "as_built_value_filled": False, "parent_gate_mutated": False, "hardware_claimed": False, "production_claimed": False} and parent_gate.get("hardware_valid") is False and parent_gate.get("next_stage_authorized") is False and parent_gate.get("release_credit") is False,
    }
    return {
        "schema": "DG5_AUTHORITY_HOLD_AUDIT_V1",
        "contact_as_built_field_count": len(contact_as_built),
        "contact_as_built_null_count": sum(value is None for value in contact_as_built),
        "actuator_joint_count": len(actuator["joint_records"]),
        "actuator_required_fields_per_joint": len(required_fields),
        "actuator_measurement_null_count": sum(value is None for value in actuator_measurements),
        "as_built_mass_properties": None,
        "contact_uncertainty": None,
        "actuator_uncertainty": None,
        "checks": checks,
        "all_holds_preserved": all(checks.values()),
        "parent_DG5_satisfied": False,
        "hardware_valid": False,
        "production_valid": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }


def build_evidence() -> dict[str, Any]:
    contract = load_contract()
    pins = contract["source_pins"]
    binding = source_binding(contract)
    mass_ledger = load_yaml(ROOT / pins["r2_design_mass_ledger"]["path"])
    bridged = load_yaml(ROOT / pins["r2_bridged_mass_ledger"]["path"])
    mass_ref = load_yaml(ROOT / pins["r2_mass_ref"]["path"])
    rom = load_json(ROOT / pins["solar_r2_rom"]["path"])
    rom_gate = load_json(ROOT / pins["solar_r2_rom_gate"]["path"])
    envelope = load_json(ROOT / pins["solar_r2_validity_envelope"]["path"])
    dg_gate = load_json(ROOT / pins["current_dg1_dg2_gate"]["path"])
    dg_evidence = load_json(ROOT / pins["current_dg1_dg2_evidence"]["path"])
    parent_gate = load_json(ROOT / pins["parent_dynamics_gate"]["path"])
    parent_authority = load_yaml(ROOT / pins["parent_dynamics_authority"]["path"])
    contact = load_yaml(ROOT / pins["design_contact_model"]["path"])
    actuator = load_json(ROOT / pins["actuator_intake"]["path"])
    mass_audit = audit_mass_uncertainty(contract, mass_ledger, bridged)
    solar_audit = audit_solar_rom(contract, rom, envelope, rom_gate)
    hold_audit = audit_authority_holds(contract, dg_gate, dg_evidence, parent_gate, parent_authority, mass_ref, contact, actuator)
    boundary_audit = audit_contract_boundary(contract)
    candidate_pass = (
        binding["all_match"]
        and boundary_audit["candidate_pass"]
        and mass_audit["candidate_pass"]
        and solar_audit["candidate_pass"]
        and hold_audit["all_holds_preserved"]
    )
    return {
        "schema": "DG5_DESIGN_UNCERTAINTY_CANDIDATE_EVIDENCE_V1",
        "technical_verdict": "DG5_BOUNDED_DESIGN_UNCERTAINTY_CANDIDATE_PASS__PARENT_DG5_HOLD" if candidate_pass else "DG5_DESIGN_UNCERTAINTY_CANDIDATE_HOLD__SEE_FAILED_CHECKS",
        "authority_scope": contract["authority_scope"],
        "source_binding": binding,
        "contract_boundary_audit": boundary_audit,
        "mass_uncertainty_audit": mass_audit,
        "solar_r2_corner_audit": solar_audit,
        "authority_hold_audit": hold_audit,
        "candidate_pass": candidate_pass,
        "parent_DG5_satisfied": False,
        "dynamics_engineering_complete": False,
        "hardware_valid": False,
        "production_valid": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "review_status": "PENDING_OWNER_REVIEW",
    }
