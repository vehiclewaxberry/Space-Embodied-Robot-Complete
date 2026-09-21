"""Generate the deterministic Sim15 LG-019 diagnostic baseline.

The baseline contains eight rigid-capture envelope cases and a separate
six-row joint-load software-verification table.  It binds every result to the
M5 interface, source inputs, and Sim15 solver hashes without promoting M5
physical-load, contact, structural, production, or flight authority.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml


SIM15_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SIM15_ROOT.parents[1]
M5_ROOT = (
    PROJECT_ROOT
    / "20_engineering"
    / "F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1"
)
DEFAULT_INTERFACE = (
    M5_ROOT / "07_simulation_handoff" / "MECH_DYNAMICS_INTERFACE_V3.yaml"
)
DEFAULT_OUTPUT = SIM15_ROOT / "evidence" / "SIM15_DIAGNOSTIC_BASELINE_V1.json"
SOURCE_MANIFEST_NAME = "SIM15_SOURCE_MANIFEST_V1.json"
SOLVER_MANIFEST_NAME = "SIM15_SOLVER_MANIFEST_V1.json"
OUTPUT_MANIFEST_NAME = "SIM15_OUTPUT_MANIFEST_V1.json"
GATE_NAME = "SIM15_DIAGNOSTIC_GATE_V1.json"
BINDING_RECEIPT_NAME = "SIM15_BINDING_RECEIPT_V1.json"
if str(SIM15_ROOT) not in sys.path:
    sys.path.insert(0, str(SIM15_ROOT))

from src.authority import AuthorityBundle, load_authority, sha256_file  # noqa: E402
from src.contact_gate import PhysicalContactGate  # noqa: E402
from src.joint_loads import JointLoadDistributor  # noqa: E402
from src.rigid_capture import (  # noqa: E402
    RigidPlasticCaptureSolver,
    body_from_mapping,
    junction_couple_impulse_at_point,
)


CAPTURE_SPEEDS_MPS = (0.005, 0.01, 0.02, 0.03)
CAPTURE_ANCHORS: Mapping[str, Mapping[str, str]] = {
    "ANCHOR_22KG_0P5DPS": {
        "target_model_id": "target_satellite_v0",
        "mass_property_record_id": "target_22kg_scenario",
        "grasp_coordinate_key": "point_mm_T",
    },
    "ANCHOR_150KG_3DPS": {
        "target_model_id": "target_debris_v0",
        "mass_property_record_id": "target_150kg_scenario",
        "grasp_coordinate_key": "point_mm_D",
    },
}
JOINT_WRENCH_STIMULI: Mapping[str, tuple[float, ...]] = {
    "SIX_DOF_MIX_A": (125.0, -23.0, 47.0, 3.2, -4.1, 5.7),
    "SIX_DOF_MIX_B": (-80.0, 31.0, -19.0, -2.4, 6.3, -1.7),
}
CAPTURE_RESIDUAL_LIMIT = 1.0e-10
JOINT_EQUILIBRIUM_LIMIT = 1.0e-10


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest().upper()


def _load_mapping(path: Path) -> Mapping[str, Any]:
    text = path.read_text(encoding="utf-8")
    value = json.loads(text) if path.suffix.casefold() == ".json" else yaml.safe_load(text)
    if not isinstance(value, Mapping):
        raise ValueError(f"expected mapping in {path}")
    return value


def _quantity(
    estimate: Any,
    *,
    unit: str,
    source: str,
    status: str,
    u: Any = None,
    distribution: str | None = None,
    dof: int | float | None = None,
    correlation: str | None = None,
) -> dict[str, Any]:
    """Create complete input metadata; unknowns stay null, never numeric zero."""

    return {
        "estimate": estimate,
        "unit": unit,
        "u": u,
        "standard_uncertainty": u,
        "distribution": distribution,
        "dof": dof,
        "degrees_of_freedom": dof,
        "source": source,
        "correlation": correlation,
        "correlation_group": correlation,
        "status": status,
    }


def _vector_add(left: Sequence[float], right: Sequence[float]) -> list[float]:
    if len(left) != 3 or len(right) != 3:
        raise ValueError("three-component vector required")
    return [float(left[index]) + float(right[index]) for index in range(3)]


def _vector_subtract(left: Sequence[float], right: Sequence[float]) -> list[float]:
    if len(left) != 3 or len(right) != 3:
        raise ValueError("three-component vector required")
    return [float(left[index]) - float(right[index]) for index in range(3)]


def _norm(value: Sequence[float]) -> float:
    return math.sqrt(math.fsum(float(component) ** 2 for component in value))


def _target_grasp_geometry(
    authority: AuthorityBundle,
    anchor_id: str,
) -> dict[str, Any]:
    binding = CAPTURE_ANCHORS[anchor_id]
    target_models_path = authority.artifacts["target_models"].path
    mass_properties_path = authority.artifacts["m4_mass_properties"].path
    target_models = _load_mapping(target_models_path)
    mass_properties = _load_mapping(mass_properties_path)
    target_model_id = binding["target_model_id"]
    mass_record_id = binding["mass_property_record_id"]
    target_model = target_models.get(target_model_id)
    component_records = mass_properties.get("component_records")
    if not isinstance(target_model, Mapping) or not isinstance(component_records, Mapping):
        raise ValueError("bound target geometry or mass-property records are malformed")
    mass_record = component_records.get(mass_record_id)
    if not isinstance(mass_record, Mapping):
        raise ValueError(f"missing bound mass-property record {mass_record_id}")
    grasp_primary = target_model.get("grasp_primary")
    center_of_mass = mass_record.get("center_of_mass")
    if not isinstance(grasp_primary, Mapping) or not isinstance(center_of_mass, Mapping):
        raise ValueError("target grasp or center-of-mass record is malformed")
    raw_grasp_mm = grasp_primary.get(binding["grasp_coordinate_key"])
    raw_center_m = center_of_mass.get("estimate_xyz_m")
    if not isinstance(raw_grasp_mm, Sequence) or len(raw_grasp_mm) != 3:
        raise ValueError("target grasp coordinate must have three mm components")
    if not isinstance(raw_center_m, Sequence) or len(raw_center_m) != 3:
        raise ValueError("target center of mass must have three metre components")
    grasp_target_m = [float(value) / 1000.0 for value in raw_grasp_mm]
    center_target_m = [float(value) for value in raw_center_m]
    lever_target_m = _vector_subtract(grasp_target_m, center_target_m)
    return {
        "target_model_id": target_model_id,
        "mass_property_record_id": mass_record_id,
        "grasp_point_target_frame_m": grasp_target_m,
        "target_center_of_mass_target_frame_m": center_target_m,
        "lever_from_target_com_m": lever_target_m,
        "target_models_source": str(target_models_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "mass_properties_source": str(mass_properties_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "source_hashes": {
            "target_models_sha256": authority.artifacts["target_models"].actual_sha256,
            "m4_mass_properties_sha256": authority.artifacts["m4_mass_properties"].actual_sha256,
        },
        "status": "DIAGNOSTIC_LOW_CONFIDENCE_UNCERTAINTY_HOLD_NOT_CONTACT_GEOMETRY_AUTHORITY",
    }


def _capture_inputs(
    authority: AuthorityBundle,
    anchor_id: str,
    approach_speed_mps: float,
    grasp: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    fixture = authority.diagnostic_fixture
    service_raw = fixture.get("service_spacecraft_fixture")
    anchors = fixture.get("anchors")
    if not isinstance(service_raw, Mapping) or not isinstance(anchors, Mapping):
        raise ValueError("diagnostic fixture bodies are malformed")
    target_raw = anchors.get(anchor_id)
    if not isinstance(target_raw, Mapping):
        raise KeyError(f"unknown diagnostic anchor {anchor_id}")
    service = copy.deepcopy(dict(service_raw))
    target = copy.deepcopy(dict(target_raw))
    service["initial_linear_velocity_mps"] = [0.0, 0.0, 0.0]
    target["initial_linear_velocity_mps"] = [0.0, approach_speed_mps, 0.0]
    service["initial_quaternion_xyzw"] = [0.0, 0.0, 0.0, 1.0]
    target["initial_quaternion_xyzw"] = [0.0, 0.0, 0.0, 1.0]
    fixture_source = str(authority.artifacts["sim14_fixture"].path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    envelope_source = (
        "SIM15_LG019_CAPTURE_ENVELOPE_V1: target v=[0,v_app,0] m/s, "
        "service v=[0,0,0] m/s; diagnostic software stimulus"
    )
    identity_source = (
        "SIM14 fixture has no attitude field; Sim15 diagnostic identity-attitude "
        "interpretation, not a released capture pose"
    )
    hold = "DIAGNOSTIC_INPUT_UNCERTAINTY_HOLD_NOT_A_PHYSICAL_MEASUREMENT"
    inputs = {
        "anchor_id": _quantity(
            anchor_id, unit="1", source=fixture_source, status=hold
        ),
        "approach_speed_mps": _quantity(
            approach_speed_mps,
            unit="m/s",
            source=envelope_source,
            status=hold,
        ),
        "target_model_id": _quantity(
            grasp["target_model_id"],
            unit="1",
            source=grasp["target_models_source"],
            status=grasp["status"],
        ),
        "mass_property_record_id": _quantity(
            grasp["mass_property_record_id"],
            unit="1",
            source=grasp["mass_properties_source"],
            status=grasp["status"],
        ),
        "service.mass_kg": _quantity(service["mass_kg"], unit="kg", source=fixture_source, status=hold),
        "service.inertia_about_com_kg_m2": _quantity(
            service["inertia_about_com_kg_m2"], unit="kg*m^2", source=fixture_source, status=hold
        ),
        "service.position_m": _quantity(service["initial_position_m"], unit="m", source=fixture_source, status=hold),
        "service.linear_velocity_mps": _quantity(
            service["initial_linear_velocity_mps"], unit="m/s", source=envelope_source, status=hold
        ),
        "service.angular_velocity_radps": _quantity(
            service["initial_angular_velocity_radps"], unit="rad/s", source=fixture_source, status=hold
        ),
        "service.quaternion_xyzw": _quantity(
            service["initial_quaternion_xyzw"], unit="1", source=identity_source, status=hold
        ),
        "target.mass_kg": _quantity(target["mass_kg"], unit="kg", source=fixture_source, status=hold),
        "target.inertia_about_com_kg_m2": _quantity(
            target["inertia_about_com_kg_m2"], unit="kg*m^2", source=fixture_source, status=hold
        ),
        "target.position_m": _quantity(target["initial_position_m"], unit="m", source=fixture_source, status=hold),
        "target.linear_velocity_mps": _quantity(
            target["initial_linear_velocity_mps"], unit="m/s", source=envelope_source, status=hold
        ),
        "target.angular_velocity_radps": _quantity(
            target["initial_angular_velocity_radps"], unit="rad/s", source=fixture_source, status=hold
        ),
        "target.quaternion_xyzw": _quantity(
            target["initial_quaternion_xyzw"], unit="1", source=identity_source, status=hold
        ),
        "target.grasp_point_target_frame_m": _quantity(
            grasp["grasp_point_target_frame_m"], unit="m", source=grasp["target_models_source"], status=grasp["status"]
        ),
        "target.center_of_mass_target_frame_m": _quantity(
            grasp["target_center_of_mass_target_frame_m"], unit="m", source=grasp["mass_properties_source"], status=grasp["status"]
        ),
        "target.grasp_lever_from_com_m": _quantity(
            grasp["lever_from_target_com_m"],
            unit="m",
            source=(
                f"{grasp['target_models_source']} grasp point minus "
                f"{grasp['mass_properties_source']} target COM"
            ),
            status=grasp["status"],
        ),
    }
    return service, target, inputs


def _capture_case(
    authority: AuthorityBundle,
    anchor_id: str,
    approach_speed_mps: float,
    solver_hash: str,
) -> dict[str, Any]:
    grasp = _target_grasp_geometry(authority, anchor_id)
    service_mapping, target_mapping, inputs = _capture_inputs(
        authority, anchor_id, approach_speed_mps, grasp
    )
    service = body_from_mapping(service_mapping)
    target = body_from_mapping(target_mapping)
    result = RigidPlasticCaptureSolver().capture(service, target)
    grasp_point_inertial_m = _vector_add(
        target.position_m, grasp["lever_from_target_com_m"]
    )
    couple = junction_couple_impulse_at_point(
        com_angular_impulse_N_m_s=result.target_com_angular_impulse_N_m_s,
        com_linear_impulse_N_s=result.target_com_linear_impulse_N_s,
        body_com_position_m=target.position_m,
        junction_point_m=grasp_point_inertial_m,
    )
    impulse_pair_residual = _vector_add(
        result.service_com_linear_impulse_N_s,
        result.target_com_linear_impulse_N_s,
    )
    impulse_pair_norm = _norm(impulse_pair_residual)
    equal_opposite = {
        "residual_N_s": impulse_pair_residual,
        "residual_norm_N_s": impulse_pair_norm,
        "absolute_limit_N_s": CAPTURE_RESIDUAL_LIMIT,
        "pass": impulse_pair_norm <= CAPTURE_RESIDUAL_LIMIT,
    }
    output = asdict(result)
    output.update(
        {
            "target_grasp_lever_from_com_m": grasp["lever_from_target_com_m"],
            "target_grasp_point_inertial_m": grasp_point_inertial_m,
            "grasp_point_and_lever_source": {
                "target_model_id": grasp["target_model_id"],
                "mass_property_record_id": grasp["mass_property_record_id"],
                "target_models_source": grasp["target_models_source"],
                "mass_properties_source": grasp["mass_properties_source"],
                "source_hashes": grasp["source_hashes"],
                "units": "m",
                "status": grasp["status"],
            },
            "junction_couple_impulse_at_grasp_N_m_s": couple,
            "junction_couple_measurement_model": (
                "dL_com_target - (p_grasp-r_target_com) cross J_target"
            ),
            "equal_opposite_linear_impulse_check": equal_opposite,
        }
    )
    case_id = f"CAPTURE_{anchor_id}_VAPP_{str(approach_speed_mps).replace('.', 'P')}_MPS"
    return {
        "case_id": case_id,
        "case_type": "RIGID_PLASTIC_CAPTURE_DIAGNOSTIC",
        "anchor_id": anchor_id,
        "approach_speed_mps": approach_speed_mps,
        "inputs": inputs,
        "input_sha256": canonical_sha256(inputs),
        "solver_sha256": solver_hash,
        "output": output,
        "output_sha256": canonical_sha256(output),
        "status": (
            "PASS_DIAGNOSTIC_NUMERICAL_CLOSURE"
            if result.linear_residual_norm_kg_mps <= CAPTURE_RESIDUAL_LIMIT
            and result.angular_residual_norm_kg_m2ps <= CAPTURE_RESIDUAL_LIMIT
            and result.plastic_energy_loss_J >= 0.0
            and equal_opposite["pass"]
            else "FAIL_DIAGNOSTIC_NUMERICAL_CLOSURE"
        ),
    }


def _joint_validation_rows(
    authority: AuthorityBundle, solver_hash: str
) -> list[dict[str, Any]]:
    distributor = JointLoadDistributor(authority)
    model_source = str(authority.artifacts["joint_load_model"].path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    rows: list[dict[str, Any]] = []
    for pattern_id in distributor.pattern_ids:
        pattern = authority.joint_load_model["patterns"][pattern_id]
        for stimulus_id, wrench in JOINT_WRENCH_STIMULI.items():
            inputs = {
                "stimulus_id": _quantity(
                    stimulus_id,
                    unit="1",
                    source="SIM15_JOINT_SOFTWARE_VERIFICATION_STIMULUS_V1",
                    status="NOT_A_MEASUREMENT_NO_UNCERTAINTY_CLAIM",
                ),
                "pattern_id": _quantity(
                    pattern_id,
                    unit="1",
                    source=model_source,
                    status="FROZEN_GEOMETRIC_MODEL_WITH_METROLOGY_UNCERTAINTY_HOLD",
                ),
                "coordinates_yz_m": _quantity(
                    pattern["coordinates_yz_m"],
                    unit="m",
                    source=model_source,
                    status="HOLD_NO_METROLOGY_INPUT",
                ),
                "influence_matrices": _quantity(
                    pattern["influence_matrices"],
                    unit="N_PER_[N,N,N,N*m,N*m,N*m]",
                    source=model_source,
                    status="ANALYTIC_GEOMETRIC_COEFFICIENTS_NOT_STRENGTH_AUTHORITY",
                ),
                "wrench_N_Nm": _quantity(
                    wrench,
                    unit="[N,N,N,N*m,N*m,N*m]",
                    source=f"SIM15_JOINT_SOFTWARE_VERIFICATION_STIMULUS_V1:{stimulus_id}",
                    status="NOT_A_MEASUREMENT_NO_UNCERTAINTY_CLAIM",
                ),
            }
            result = distributor.distribute(pattern_id, wrench)
            output = asdict(result)
            rows.append(
                {
                    "row_id": f"{pattern_id}__{stimulus_id}",
                    "pattern_id": pattern_id,
                    "stimulus_id": stimulus_id,
                    "inputs": inputs,
                    "input_sha256": canonical_sha256(inputs),
                    "solver_sha256": solver_hash,
                    "output": output,
                    "output_sha256": canonical_sha256(output),
                    "status": (
                        "PASS_GEOMETRIC_EQUILIBRIUM"
                        if result.equilibrium_residual_norm <= JOINT_EQUILIBRIUM_LIMIT
                        else "FAIL_GEOMETRIC_EQUILIBRIUM"
                    ),
                }
            )
    return rows


def _solver_receipt() -> dict[str, Any]:
    relative_paths = (
        "src/authority.py",
        "src/rigid_capture.py",
        "src/joint_loads.py",
        "src/contact_gate.py",
        "src/env.py",
    )
    files = {
        relative: sha256_file(SIM15_ROOT / relative) for relative in relative_paths
    }
    return {"files": files, "bundle_sha256": canonical_sha256(files)}


def _metadata_complete(cases: Sequence[Mapping[str, Any]]) -> bool:
    required = {
        "estimate",
        "unit",
        "u",
        "standard_uncertainty",
        "distribution",
        "dof",
        "degrees_of_freedom",
        "source",
        "correlation",
        "correlation_group",
        "status",
    }
    for case in cases:
        inputs = case.get("inputs")
        if not isinstance(inputs, Mapping) or not inputs:
            return False
        for record in inputs.values():
            if not isinstance(record, Mapping) or set(record) != required:
                return False
            if record["u"] != record["standard_uncertainty"]:
                return False
            if record["dof"] != record["degrees_of_freedom"]:
                return False
            if record["correlation"] != record["correlation_group"]:
                return False
            if record["source"] in (None, "") or record["status"] in (None, ""):
                return False
    return True


def build_baseline(interface_path: Path = DEFAULT_INTERFACE) -> dict[str, Any]:
    authority = load_authority(interface_path)
    solver_receipt = _solver_receipt()
    solver_hash = solver_receipt["bundle_sha256"]
    capture_cases = [
        _capture_case(authority, anchor_id, speed, solver_hash)
        for anchor_id in CAPTURE_ANCHORS
        for speed in CAPTURE_SPEEDS_MPS
    ]
    joint_rows = _joint_validation_rows(authority, solver_hash)
    contact_gate = asdict(PhysicalContactGate.evaluate(authority))
    all_inputs = [case["inputs"] for case in capture_cases] + [
        row["inputs"] for row in joint_rows
    ]
    all_outputs = [case["output"] for case in capture_cases] + [
        row["output"] for row in joint_rows
    ]
    capture_pass = len(capture_cases) == 8 and all(
        case["status"] == "PASS_DIAGNOSTIC_NUMERICAL_CLOSURE"
        for case in capture_cases
    )
    joint_pass = len(joint_rows) == 6 and all(
        row["status"] == "PASS_GEOMETRIC_EQUILIBRIUM" for row in joint_rows
    )
    metadata_pass = _metadata_complete([*capture_cases, *joint_rows])
    lg019_pass = capture_pass and joint_pass and metadata_pass
    artifact_hashes = {
        artifact_id: binding.actual_sha256
        for artifact_id, binding in authority.artifacts.items()
    }
    hash_receipt = {
        "m5_interface_sha256": authority.interface_sha256,
        "m5_artifact_set_sha256": canonical_sha256(artifact_hashes),
        "diagnostic_inputs_sha256": canonical_sha256(all_inputs),
        "solver_bundle_sha256": solver_hash,
        "diagnostic_outputs_sha256": canonical_sha256(all_outputs),
    }
    document = {
        "schema": "SIM15_DIAGNOSTIC_BASELINE_V1",
        "scope": (
            "HASH_BOUND_DIAGNOSTIC_CAPTURE_IMPULSE_AND_GEOMETRIC_JOINT_LOAD_"
            "SOFTWARE_ONLY_NOT_PHYSICAL_CONTACT_OR_FLIGHT_AUTHORITY"
        ),
        "units_policy": "STRICT_SI_AT_ALL_API_BOUNDARIES",
        "zero_fill_forbidden": True,
        "authority_binding": {
            "interface_path": str(authority.interface_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "interface_sha256": authority.interface_sha256,
            "artifact_hashes": artifact_hashes,
            "required_acknowledgement": authority.document["required_acknowledgement"],
            "m5_physical_load_authority": False,
            "m5_authority_modified_or_upgraded": False,
        },
        "hash_receipt": hash_receipt,
        "solver_receipt": solver_receipt,
        "capture_envelope": {
            "case_count": len(capture_cases),
            "target_count": 2,
            "approach_speeds_mps": CAPTURE_SPEEDS_MPS,
            "velocity_assumption": (
                "target=[0,v_app,0] m/s; service=[0,0,0] m/s; target angular "
                "velocity and inertia retained from each hash-bound anchor"
            ),
            "cases": capture_cases,
            "status": "PASS_8_OF_8_DIAGNOSTIC" if capture_pass else "FAIL",
        },
        "joint_load_validation": {
            "row_count": len(joint_rows),
            "pattern_count": 3,
            "stimulus_count_per_pattern": 2,
            "rows": joint_rows,
            "status": "PASS_6_OF_6_GEOMETRIC_EQUILIBRIUM" if joint_pass else "FAIL",
            "strength_or_flight_authority": False,
        },
        "contact_gate": contact_gate,
        "lg_019_gate": {
            "requirement_id": "LG-019",
            "status": (
                "PASS_SIM15_DIAGNOSTIC_REPRODUCIBILITY_CLOSURE"
                if lg019_pass
                else "FAIL_SIM15_DIAGNOSTIC_REPRODUCIBILITY"
            ),
            "applies_to": "SIM15_DIAGNOSTIC_SOFTWARE_ONLY",
            "input_metadata_complete": metadata_pass,
            "input_solver_output_hash_chain_complete": True,
            "m5_gap_count_or_authority_modified": False,
            "physical_load_authority_created": False,
        },
        "physical_contact_gate": "HOLD",
        "structural_analysis_gate": "HOLD",
        "production_gate": "ABORT_NOT_AUTHORIZED",
        "rl_training_gate": "HOLD_NOT_AUTHORIZED",
        "overall_status": (
            "PASS_SIM15_DIAGNOSTIC_BASELINE_HOLD_ALL_PHYSICAL_AND_PRODUCTION_GATES"
            if lg019_pass and not contact_gate["allowed"] and not authority.production_ready
            else "FAIL"
        ),
    }
    # Normalize tuples to JSON arrays so an on-disk round trip compares exactly.
    return json.loads(canonical_json_bytes(document).decode("utf-8"))


def rendered_json_bytes(document: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")


def rendered_sha256(document: Mapping[str, Any]) -> str:
    return hashlib.sha256(rendered_json_bytes(document)).hexdigest().upper()


def _evidence_record(filename: str, document: Mapping[str, Any]) -> dict[str, Any]:
    relative = Path("30_simulation") / SIM15_ROOT.name / "evidence" / filename
    return {
        "path": relative.as_posix(),
        "sha256": rendered_sha256(document),
        "bytes": len(rendered_json_bytes(document)),
    }


def build_evidence_suite(
    interface_path: Path = DEFAULT_INTERFACE,
    *,
    baseline_name: str = DEFAULT_OUTPUT.name,
) -> dict[str, dict[str, Any]]:
    """Build all non-circular evidence documents without writing them."""

    authority = load_authority(interface_path)
    baseline = build_baseline(interface_path)
    source_records = [
        {
            "source_id": "m5_interface",
            "path": str(authority.interface_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "sha256": authority.interface_sha256,
            "required": True,
        }
    ]
    source_records.extend(
        {
            "source_id": artifact_id,
            "path": str(binding.path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "sha256": binding.actual_sha256,
            "required": binding.required,
        }
        for artifact_id, binding in authority.artifacts.items()
    )
    source_manifest = {
        "schema": "SIM15_SOURCE_MANIFEST_V1",
        "scope": "M5_HASH_BOUND_DIAGNOSTIC_INPUTS_ONLY",
        "record_count": len(source_records),
        "records": source_records,
        "source_set_sha256": canonical_sha256(source_records),
        "frozen_input_verification_count": authority.frozen_input_verification_count,
        "nested_geometry_hash_verification_count": authority.nested_hash_verification_count,
        "all_required_sources_resolved": True,
        "physical_load_authority_created": False,
    }
    solver_files = baseline["solver_receipt"]["files"]
    solver_manifest = {
        "schema": "SIM15_SOLVER_MANIFEST_V1",
        "scope": "SIM15_DIAGNOSTIC_SOFTWARE_IMPLEMENTATION",
        "file_count": len(solver_files),
        "files": [
            {"path": path, "sha256": sha256}
            for path, sha256 in solver_files.items()
        ],
        "solver_bundle_sha256": baseline["solver_receipt"]["bundle_sha256"],
        "impulse_to_force_conversion_permitted": False,
        "production_execution_permitted": False,
    }
    capture_records = [
        {
            "case_id": case["case_id"],
            "input_sha256": case["input_sha256"],
            "solver_sha256": case["solver_sha256"],
            "output_sha256": case["output_sha256"],
            "status": case["status"],
        }
        for case in baseline["capture_envelope"]["cases"]
    ]
    joint_records = [
        {
            "row_id": row["row_id"],
            "input_sha256": row["input_sha256"],
            "solver_sha256": row["solver_sha256"],
            "output_sha256": row["output_sha256"],
            "status": row["status"],
        }
        for row in baseline["joint_load_validation"]["rows"]
    ]
    output_manifest = {
        "schema": "SIM15_OUTPUT_MANIFEST_V1",
        "scope": "DIAGNOSTIC_NUMERICAL_OUTPUTS_NOT_ENGINEERING_PREDICTIONS",
        "baseline": {
            "path": (Path("30_simulation") / SIM15_ROOT.name / "evidence" / baseline_name).as_posix(),
            "sha256": rendered_sha256(baseline),
            "bytes": len(rendered_json_bytes(baseline)),
        },
        "capture_case_count": len(capture_records),
        "capture_cases": capture_records,
        "joint_validation_row_count": len(joint_records),
        "joint_validation_rows": joint_records,
        "aggregate_input_sha256": baseline["hash_receipt"]["diagnostic_inputs_sha256"],
        "solver_bundle_sha256": baseline["hash_receipt"]["solver_bundle_sha256"],
        "aggregate_output_sha256": baseline["hash_receipt"]["diagnostic_outputs_sha256"],
        "contact_force_outputs": None,
        "contact_pressure_outputs": None,
        "flight_or_strength_outputs": None,
    }
    upstream_documents = {
        baseline_name: baseline,
        SOURCE_MANIFEST_NAME: source_manifest,
        SOLVER_MANIFEST_NAME: solver_manifest,
        OUTPUT_MANIFEST_NAME: output_manifest,
    }
    critical_evidence = {
        filename: _evidence_record(filename, document)
        for filename, document in upstream_documents.items()
    }
    gate = {
        "schema": "SIM15_DIAGNOSTIC_GATE_V1",
        "scope": "SIM15_ONLY_NO_M5_AUTHORITY_WRITEBACK",
        "critical_evidence": critical_evidence,
        "capture_envelope_gate": baseline["capture_envelope"]["status"],
        "joint_equilibrium_gate": baseline["joint_load_validation"]["status"],
        "input_metadata_gate": (
            "PASS_COMPLETE_WITH_NULL_HOLD_UNKNOWNS"
            if baseline["lg_019_gate"]["input_metadata_complete"]
            else "FAIL"
        ),
        "hash_chain_gate": "PASS_INPUT_SOLVER_OUTPUT_BOUND",
        "lg_019_status": baseline["lg_019_gate"]["status"],
        "m5_gap_count_modified": False,
        "m5_physical_load_authority_upgraded": False,
        "physical_contact_gate": "HOLD",
        "structural_analysis_gate": "HOLD",
        "production_gate": "ABORT_NOT_AUTHORIZED",
        "overall_status": (
            "PASS_SIM15_DIAGNOSTIC_REPRODUCIBILITY_ONLY"
            if baseline["overall_status"].startswith("PASS_")
            else "FAIL"
        ),
    }
    receipt_evidence = dict(critical_evidence)
    receipt_evidence[GATE_NAME] = _evidence_record(GATE_NAME, gate)
    receipt = {
        "schema": "SIM15_BINDING_RECEIPT_V1",
        "scope": "INPUT_SOLVER_OUTPUT_AND_GATE_BINDING_DIAGNOSTIC_ONLY",
        "m5_interface_sha256": authority.interface_sha256,
        "evidence": receipt_evidence,
        "evidence_record_count": len(receipt_evidence),
        "all_hashes_resolved": True,
        "capture_case_count": 8,
        "joint_validation_row_count": 6,
        "lg_019_closed_in_sim15_only": True,
        "m5_authority_modified_or_upgraded": False,
        "physical_or_production_authority_created": False,
        "status": "PASS_DIAGNOSTIC_BINDING_RECEIPT",
    }
    return {
        baseline_name: baseline,
        SOURCE_MANIFEST_NAME: source_manifest,
        SOLVER_MANIFEST_NAME: solver_manifest,
        OUTPUT_MANIFEST_NAME: output_manifest,
        GATE_NAME: gate,
        BINDING_RECEIPT_NAME: receipt,
    }


def _write_document(document: Mapping[str, Any], output_path: Path) -> None:
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f"{output_path.name}.tmp")
    temporary_path.write_bytes(rendered_json_bytes(document))
    temporary_path.replace(output_path)


def write_baseline(document: Mapping[str, Any], output_path: Path) -> None:
    _write_document(document, output_path)


def write_evidence_suite(
    documents: Mapping[str, Mapping[str, Any]], output_directory: Path
) -> None:
    for filename, document in documents.items():
        _write_document(document, output_directory / filename)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interface", type=Path, default=DEFAULT_INTERFACE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--stdout-only",
        action="store_true",
        help="print the baseline without writing an evidence file",
    )
    args = parser.parse_args(argv)
    documents = build_evidence_suite(
        args.interface, baseline_name=args.output.name
    )
    baseline = documents[args.output.name]
    if not args.stdout_only:
        write_evidence_suite(documents, args.output.parent)
    print(
        json.dumps(
            {
                "overall_status": baseline["overall_status"],
                "interface_sha256": baseline["authority_binding"]["interface_sha256"],
                "generated_files": list(documents),
                "hash_receipt": baseline["hash_receipt"],
            },
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
    )
    return 0 if baseline["overall_status"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
