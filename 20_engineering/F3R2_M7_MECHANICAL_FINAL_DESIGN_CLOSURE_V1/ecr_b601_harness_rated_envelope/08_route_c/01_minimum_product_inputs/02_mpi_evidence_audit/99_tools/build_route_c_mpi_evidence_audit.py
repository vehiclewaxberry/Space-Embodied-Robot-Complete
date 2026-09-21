from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import yaml


GENERATED_LOCAL = "2026-08-23T17:35:00+08:00"
PACKAGE_REL = Path(
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "ecr_b601_harness_rated_envelope/08_route_c/01_minimum_product_inputs/"
    "02_mpi_evidence_audit"
)


def find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / "PROJECT_MAP.md").is_file() and (candidate / "AGENTS.md").is_file():
            return candidate
    raise RuntimeError("Repository root with PROJECT_MAP.md and AGENTS.md was not found")


ROOT = find_repo_root()
OUT = ROOT / PACKAGE_REL

SOURCES = {
    "minimum_input_register": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/01_minimum_product_inputs/ROUTE_C_MINIMUM_PRODUCT_INTERFACE_INPUT_REGISTER_V1.json",
    "product_source_register": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/01_minimum_product_inputs/ROUTE_C_PRODUCT_SOURCE_REGISTER_V1.json",
    "product_input_gate": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/01_minimum_product_inputs/ROUTE_C_PRODUCT_INPUT_GATE_V1.json",
    "rfi_requirements": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/01_minimum_product_inputs/ROUTE_C_VENDOR_RFI_REQUIREMENTS_V1.yaml",
    "rfi_gate": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/01_minimum_product_inputs/ROUTE_C_VENDOR_RFI_DECISION_GATE_V1.json",
    "vendor_rebot_b601_dm_bom_readme": "80_third_party/vendor/reBot-DevArm/hardware/reBot_B601_DM/readme.md",
    "hardware_component_plan": "10_research/competition_convergence/hardware_component_plan.md",
    "harness_routing": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp1_structure_cad/HARNESS_ROUTING_V1.yaml",
    "joint_interface_control_documents": "20_engineering/cad/freecad_authoritative/JOINT_INTERFACE_CONTROL_DOCUMENTS.yaml",
    "accepted_urdf": "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
    "e17_gate": "30_simulation/e17_b601_mission_trajectory_candidates/results/B601_MISSION_TRAJECTORY_CANDIDATE_GATE_V1.json",
    "route_b_rejected_product_definition": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/01_product_definition/B601_HARNESS_ROUTING_PRODUCT_DEFINITION_V1.yaml",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def binding(path_text: str) -> dict:
    path = ROOT / path_text
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"path": path_text, "sha256": sha256(path), "bytes": path.stat().st_size}


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=110),
        encoding="utf-8",
    )


def unknown_quantity(unit: str, requirement: str) -> dict:
    return {
        "value": None,
        "unit": unit,
        "source_revision": None,
        "owner": None,
        "uncertainty": {
            "standard_uncertainty": None,
            "distribution": None,
            "coverage_factor": None,
            "degrees_of_freedom": None,
            "reason": "OWNER_CONTROLLED_SOURCE_NOT_PROVIDED",
        },
        "controlled": False,
        "requirement": requirement,
    }


def unknown_category(requirement: str) -> dict:
    return {
        "value": None,
        "unit": "not_applicable",
        "source_revision": None,
        "owner": None,
        "uncertainty": {
            "standard_uncertainty": None,
            "distribution": "not_applicable_to_categorical_value",
            "coverage_factor": None,
            "degrees_of_freedom": None,
            "reason": "CATEGORICAL_OWNER_INPUT_NOT_PROVIDED",
        },
        "controlled": False,
        "requirement": requirement,
    }


def unknown_bounds(unit: str, requirement: str) -> dict:
    return {
        "minimum": None,
        "maximum": None,
        "unit": unit,
        "source_revision": None,
        "owner": None,
        "bounded_tolerance": {
            "lower": None,
            "upper": None,
            "unit": unit,
            "distribution": None,
            "basis": None,
        },
        "controlled": False,
        "requirement": requirement,
    }


def template_header(schema: str, covered_mpis: list[str], owner_role: str) -> dict:
    return {
        "schema": schema,
        "generated_local": GENERATED_LOCAL,
        "authority": "OWNER_INPUT_TEMPLATE_ONLY__NO_RELEASE_CREDIT_WHILE_ANY_REQUIRED_VALUE_IS_NULL",
        "covered_mpis": covered_mpis,
        "owner_role_required": owner_role,
        "template_state": "UNFILLED_HOLD",
        "release_credit": False,
        "next_stage_authorized": False,
        "completion_rule": (
            "Every required record must carry a non-null value, explicit unit, controlled source revision, "
            "named owner, and uncertainty or bounded tolerance; independent review is still required."
        ),
        "unknown_policy": "Unknown is null with a reason; zero is never substituted for missing data.",
    }


def parse_urdf_joints() -> list[dict]:
    tree = ET.parse(ROOT / SOURCES["accepted_urdf"])
    robot = tree.getroot()
    joints = []
    for name in [f"joint{i}" for i in range(1, 7)]:
        node = robot.find(f"./joint[@name='{name}']")
        if node is None:
            raise RuntimeError(f"Accepted URDF missing {name}")
        origin = node.find("origin")
        axis = node.find("axis")
        limit = node.find("limit")
        joints.append(
            {
                "joint": name,
                "type": node.attrib["type"],
                "parent": node.find("parent").attrib["link"],
                "child": node.find("child").attrib["link"],
                "origin_xyz_m": [float(x) for x in origin.attrib["xyz"].split()],
                "origin_rpy_rad": [float(x) for x in origin.attrib["rpy"].split()],
                "axis_in_joint_frame": [float(x) for x in axis.attrib["xyz"].split()],
                "lower_rad": float(limit.attrib["lower"]),
                "upper_rad": float(limit.attrib["upper"]),
                "local_authority": "ACCEPTED_URDF_KINEMATICS_ONLY",
                "installation_icd_credit": False,
            }
        )
    return joints


def build_templates(source_bindings: dict) -> dict[str, dict]:
    common_binding = {
        "minimum_input_register": source_bindings["minimum_input_register"],
        "accepted_urdf": source_bindings["accepted_urdf"],
    }

    electrical = template_header(
        "B601_ELECTRICAL_AND_DATA_ICD_OWNER_INPUT_TEMPLATE_V1",
        ["MPI-01", "MPI-02"],
        "B601 electrical/data interface Owner",
    )
    electrical["source_bindings"] = common_binding
    electrical["electrical_loads"] = {
        "bus_supply_voltage": unknown_bounds("V", "Approved B601 input-voltage operating and transient bounds"),
        "arm_idle_current": unknown_quantity("A", "Measured or controlled idle current at declared voltage/temperature"),
        "arm_rms_current": unknown_quantity("A", "Mission-profile RMS current with duty and simultaneity basis"),
        "arm_peak_current": unknown_quantity("A", "Peak current with duration and simultaneous-joint assumption"),
        "arm_peak_duration": unknown_quantity("s", "Duration associated with peak current"),
        "gripper_rms_current": unknown_quantity("A", "Gripper RMS current by load case"),
        "gripper_peak_current": unknown_quantity("A", "Gripper peak or stall current with duration"),
        "brake_count_and_type": unknown_category("Brake presence/count/type; state none only with controlled source"),
        "brake_release_current_per_channel": unknown_quantity("A", "Brake release current per channel"),
        "simultaneity_factor": unknown_quantity("dimensionless", "Maximum concurrent motor/brake/gripper load factor"),
        "temperature_derating_factor": unknown_quantity("dimensionless", "Current derating over controlled temperature range"),
    }
    electrical["data_interface"] = {
        "protocol": unknown_category("Flight/engineering protocol identity; CAN-USB BOM mention is not selection"),
        "physical_layer": unknown_category("Transceiver/physical-layer standard and voltage levels"),
        "topology": unknown_category("Daisy-chain, star, redundant bus, or other controlled topology"),
        "nominal_data_rate": unknown_quantity("bit/s", "Approved nominal data rate"),
        "differential_impedance": unknown_bounds("ohm", "Required cable/termination impedance bounds, if applicable"),
        "termination_map": unknown_category("Termination values and locations"),
        "redundancy_class": unknown_category("Single/dual/redundant-channel allocation"),
        "emc_separation_minimum": unknown_quantity("mm", "Minimum separation from power/noisy circuits"),
        "shield_termination_rule": unknown_category("Shield grounding/bonding and pigtail prohibition/allowance"),
        "chassis_signal_return_rule": unknown_category("Chassis, power return, signal return and isolation policy"),
    }

    wire = template_header(
        "WIRE_LIST_PINOUT_OWNER_INPUT_TEMPLATE_V1",
        ["MPI-03", "MPI-04"],
        "B601 harness electrical design Owner",
    )
    wire["source_bindings"] = common_binding
    wire["owner_rows"] = []
    wire["required_row_template_not_data"] = {
        "circuit_id": unknown_category("Unique controlled circuit identifier"),
        "function": unknown_category("Motor phase/power, brake, encoder, data, gripper, return, spare or shield"),
        "source_pin": unknown_category("Source connector reference and pin/cavity"),
        "destination_pin": unknown_category("Destination connector reference and pin/cavity"),
        "nominal_voltage": unknown_quantity("V", "Circuit nominal voltage"),
        "rms_current": unknown_quantity("A", "Circuit RMS current"),
        "peak_current": unknown_quantity("A", "Circuit peak current"),
        "peak_duration": unknown_quantity("s", "Peak duration"),
        "conductor_part_number": unknown_category("Exact conductor/cable part number and revision"),
        "wire_gauge": unknown_quantity("AWG", "Selected conductor gauge"),
        "conductor_count": unknown_quantity("count", "Number of conductors allocated to circuit"),
        "redundancy_allocation": unknown_category("Channel/redundancy allocation"),
        "shield_id": unknown_category("Shield group and drain allocation"),
        "bond_end_a": unknown_category("Shield/bond disposition at end A"),
        "bond_end_b": unknown_category("Shield/bond disposition at end B"),
        "connector_end_a_part_number": unknown_category("Exact connector mating part, shell, keying and contact"),
        "connector_end_b_part_number": unknown_category("Exact connector mating part, shell, keying and contact"),
        "backshell_part_number": unknown_category("Exact backshell/strain-relief part number"),
        "contact_derating_factor": unknown_quantity("dimensionless", "Approved contact current derating"),
    }
    wire["required_global_inputs"] = {
        "connector_mating_pair_definition": unknown_category("Complete mating pair, polarization and keying definition"),
        "pinout_revision": unknown_category("Controlled pinout document revision"),
        "spare_policy": unknown_category("Spare contacts/conductors and termination policy"),
        "voltage_drop_limit": unknown_quantity("V", "Maximum allowable end-to-end drop by power circuit"),
    }

    construction = template_header(
        "INSTALLED_CONSTRUCTION_OWNER_INPUT_TEMPLATE_V1",
        ["MPI-05", "MPI-06"],
        "Harness product and materials/process Owner",
    )
    construction["source_bindings"] = common_binding
    construction["selected_construction"] = {
        "construction_id": unknown_category("Controlled installed dress-pack construction identifier"),
        "sub_bundle_definition": unknown_category("Power/data split and lay-up definition"),
        "finished_bundle_outer_diameter": unknown_quantity("mm", "Installed finished OD after sleeving/shielding/ties"),
        "finished_bundle_od_tolerance": unknown_bounds("mm", "Two-sided or explicitly one-sided installed OD tolerance"),
        "linear_mass": unknown_quantity("g/m", "Installed linear mass including shield, sleeve and ties"),
        "component_mass": unknown_quantity("g", "Connector, backshell, clamp, guide and service-loop component mass"),
        "static_minimum_bend_radius": unknown_quantity("mm", "Selected construction static minimum bend radius"),
        "dynamic_minimum_bend_radius": unknown_quantity("mm", "Selected construction dynamic minimum bend radius"),
        "torsion_limit_per_length": unknown_quantity("deg/m", "Allowable cyclic torsion per unit length"),
        "temperature_operating_bounds": unknown_bounds("degC", "Controlled operating temperature bounds"),
        "bend_temperature_derating": unknown_category("Bend-radius derating law/table versus temperature"),
        "torsion_temperature_derating": unknown_category("Torsion derating law/table versus temperature"),
        "jacket_sleeve_material": unknown_category("Exact jacket/sleeve/braid material and process specification"),
        "clamp_liner_material": unknown_category("Exact clamp/liner material and process specification"),
        "outgassing_evidence": unknown_category("Controlled TML/CVCM or approved equivalent evidence"),
        "abrasion_and_particulate_evidence": unknown_category("Selected-construction abrasion/particulate control evidence"),
        "bending_restoring_moment_curve": unknown_category("Raw curve/table versus bend angle, rate and temperature"),
        "torsional_restoring_moment_curve": unknown_category("Raw curve/table versus twist, rate and temperature"),
    }

    installation = template_header(
        "INSTALLATION_ICD_OWNER_INPUT_TEMPLATE_V1",
        ["MPI-07"],
        "Mechanical installation-interface Owner",
    )
    installation["source_bindings"] = {
        **common_binding,
        "harness_routing": source_bindings["harness_routing"],
        "joint_interface_control_documents": source_bindings["joint_interface_control_documents"],
    }
    installation["accepted_urdf_local_kinematic_reference"] = {
        "status": "J1_TO_J6_LOCAL_KINEMATICS_AVAILABLE__NO_INSTALLATION_ICD_CREDIT",
        "joints": parse_urdf_joints(),
        "explicit_limit": "URDF origins/axes/limits do not define connector faces, clamp seats, feedthroughs, voids, fasteners, or installation tolerances.",
    }
    node_template = {
        "controlled_frame_id": unknown_category("Controlled parent frame and datum reference"),
        "position_x": unknown_quantity("mm", "Datum position x in controlled parent frame"),
        "position_y": unknown_quantity("mm", "Datum position y in controlled parent frame"),
        "position_z": unknown_quantity("mm", "Datum position z in controlled parent frame"),
        "orientation_rpy": unknown_quantity("rad", "Controlled orientation; provide vector/order convention"),
        "position_tolerance": unknown_bounds("mm", "Manufacturing and installation positional tolerance"),
        "orientation_tolerance": unknown_bounds("rad", "Manufacturing and installation angular tolerance"),
        "interface_feature": unknown_category("Connector face, feedthrough, clamp, guide, or termination feature"),
        "fastener_or_retention": unknown_category("Exact retention hardware and installation torque/process"),
    }
    installation["installation_nodes"] = {
        node: {key: dict(value) for key, value in node_template.items()}
        for node in ["HN-00", "HN-01", "HN-02", "HN-03"]
    }
    installation["additional_required_interfaces"] = {
        "physical_passage_void_geometry": unknown_category("Controlled passage/void geometry; reference box is insufficient"),
        "connector_face_geometry": unknown_category("Arm-side connector face model/drawing and mating direction"),
        "clamp_and_guide_station_schedule": unknown_category("All clamp/guide datums, host links and fastener interfaces"),
        "installation_sequence": unknown_category("Assembly/reeving sequence and access constraints"),
        "inspection_and_post_install_test": unknown_category("Inspection plus continuity/insulation/bond test procedure"),
    }

    life = template_header(
        "MISSION_LIFE_ALLOCATION_OWNER_INPUT_TEMPLATE_V1",
        ["MPI-08"],
        "Mission and mechanism-life Owner",
    )
    life["source_bindings"] = {
        **common_binding,
        "e17_gate": source_bindings["e17_gate"],
    }
    life["mission_segment_rows"] = []
    life["required_segment_template_not_data"] = {
        "segment_id": unknown_category("One of M01, M02, M03, M04, M05_150, M05_22, M06_22, M07_22"),
        "planned_executions_per_mission": unknown_quantity("cycles/mission", "Planned segment repetitions per mission"),
        "mission_count": unknown_quantity("missions", "Required mission count"),
        "joint_cycle_equivalents": unknown_quantity("cycles", "Equivalent bend/torsion cycles by joint and construction"),
        "bend_amplitude": unknown_quantity("rad", "Segment bend amplitude or controlled time history reference"),
        "torsion_amplitude": unknown_quantity("rad", "Segment torsion amplitude or controlled time history reference"),
        "temperature_case": unknown_category("Controlled thermal state/range for this segment"),
        "trajectory_revision": unknown_category("Released trajectory file/revision/hash"),
    }
    life["global_factors"] = {
        "qualification_life_factor": unknown_quantity("dimensionless", "Qualification life multiplier"),
        "acceptance_life_factor": unknown_quantity("dimensionless", "Acceptance life multiplier or rationale if not applicable"),
        "protoflight_life_factor": unknown_quantity("dimensionless", "Protoflight multiplier if selected"),
        "storage_and_ground_cycles": unknown_quantity("cycles", "Ground handling, integration and storage cycling allocation"),
        "contingency_cycles": unknown_quantity("cycles", "Abort/retry/anomaly contingency allocation"),
        "combined_bend_torsion_spectrum": unknown_category("Controlled combined spectrum or raw time-history set"),
        "acceptance_criterion": unknown_category("Electrical/mechanical degradation and inspection acceptance limits"),
    }
    life["e17_boundary"] = {
        "segments_total": 8,
        "segments_released": 0,
        "state": "E17_SEEDS_AND_SYMBOLIC_SCAFFOLDS_DO_NOT_SUPPLY_MISSION_LIFE_COUNTS",
        "release_credit": False,
    }

    return {
        "B601_ELECTRICAL_AND_DATA_ICD_OWNER_INPUT_TEMPLATE_V1.yaml": electrical,
        "WIRE_LIST_PINOUT_OWNER_INPUT_TEMPLATE_V1.yaml": wire,
        "INSTALLED_CONSTRUCTION_OWNER_INPUT_TEMPLATE_V1.yaml": construction,
        "INSTALLATION_ICD_OWNER_INPUT_TEMPLATE_V1.yaml": installation,
        "MISSION_LIFE_ALLOCATION_OWNER_INPUT_TEMPLATE_V1.yaml": life,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_bindings = {name: binding(path) for name, path in SOURCES.items()}

    contract = {
        "schema": "ROUTE_C_MPI_EVIDENCE_AUDIT_AUTHORITY_CONTRACT_V1",
        "generated_local": GENERATED_LOCAL,
        "authority": "READ_ONLY_EVIDENCE_AUDIT_AND_OWNER_INPUT_PREPARATION",
        "scope": "MPI-01..MPI-08 closure evidence for Route-C C1/C2 entry",
        "mutation_authority": False,
        "cad_generation_authorized": False,
        "accepted_urdf_mutation_authorized": False,
        "owner_decision_authority": False,
        "release_authority": False,
        "source_bindings": source_bindings,
        "closure_logic": {
            "controlled_definition": (
                "Owner-approved, configuration-controlled, revisioned input with units and uncertainty or bounded "
                "tolerance, plus independent review and exact source hash."
            ),
            "all_required": True,
            "unknown_is_allow": False,
            "catalog_candidate_is_controlled": False,
            "rfi_issue_or_response_is_controlled": False,
            "upstream_bom_is_controlled": False,
            "local_urdf_kinematics_is_installation_icd": False,
            "mission_segment_name_or_seed_is_life_allocation": False,
        },
        "unit_and_uncertainty_policy": {
            "unknown_value": None,
            "zero_substitution_for_unknown": "PROHIBITED",
            "required_for_physical_values": ["value", "unit", "source_revision", "owner", "uncertainty_or_bounded_tolerance"],
        },
        "route_b_quarantine": {
            "overall_diameter_mm_10": "FORBIDDEN_TO_INHERIT",
            "legacy_radius_mm_25": "FORBIDDEN_TO_INHERIT",
            "terminal_requirement_mm_30": "FORBIDDEN_TO_INHERIT_AS_SELECTED_PRODUCT_LIMIT",
            "cut_length_mm_4001_158": "FORBIDDEN_TO_INHERIT",
            "reason": "Route-B product definition is FROZEN_TESTED_CANDIDATE__ROUTE_B_REJECTED.",
        },
        "fail_closed": "Any missing input, null Owner/source, absent uncertainty/tolerance, hash mismatch, or unsupported inheritance keeps the gate HOLD.",
    }
    write_json(OUT / "ROUTE_C_MPI_EVIDENCE_AUDIT_AUTHORITY_CONTRACT_V1.json", contract)

    audits = [
        {
            "id": "MPI-01",
            "input": "motor, brake and gripper voltage/current/load map",
            "state": "HOLD_NOT_CONTROLLED",
            "controlled": False,
            "local_evidence": [
                "Vendor BOM/readme names DM43-series motors and a ground-use 24 V, 14.6 A power-supply option.",
                "Hardware component plan prohibits B601 motion before physical identity/driver/safety/encoder qualification.",
            ],
            "why_not_closed": "No per-function nominal/RMS/peak current, duration, simultaneity, brake allocation, flight derating, or controlled spacecraft supply interface.",
            "owner_template": "B601_ELECTRICAL_AND_DATA_ICD_OWNER_INPUT_TEMPLATE_V1.yaml",
        },
        {
            "id": "MPI-02",
            "input": "data protocol, rate, impedance and EMC/separation needs",
            "state": "HOLD_NOT_CONTROLLED",
            "controlled": False,
            "local_evidence": [
                "Vendor BOM/readme names a CAN-USB driver board as an upstream ground component.",
                "RFI package contains conditional protocol cable families only.",
            ],
            "why_not_closed": "No controlled B601 physical layer, bit rate, topology, termination, impedance, redundancy, EMC, shield, or return-current rule.",
            "owner_template": "B601_ELECTRICAL_AND_DATA_ICD_OWNER_INPUT_TEMPLATE_V1.yaml",
        },
        {
            "id": "MPI-03",
            "input": "conductor count, gauge, redundancy, shield and bond map",
            "state": "HOLD_NOT_CONTROLLED",
            "controlled": False,
            "local_evidence": [
                "Vendor BOM/readme says motor/gripper kits include wiring harnesses but gives no controlled wire list.",
                "Product-source register contains 22/24 AWG catalog candidates only.",
            ],
            "why_not_closed": "No project circuit list, conductor count, selected gauge, load/drop proof, redundancy, shield grouping, or bond map.",
            "owner_template": "WIRE_LIST_PINOUT_OWNER_INPUT_TEMPLATE_V1.yaml",
        },
        {
            "id": "MPI-04",
            "input": "exact connector, backshell, strain relief and pinout",
            "state": "HOLD_NOT_CONTROLLED",
            "controlled": False,
            "local_evidence": [
                "Vendor BOM/readme contains ground power connectors and cable hardware references.",
                "RFI package lists connector families, not selected exact spacecraft mating pairs.",
            ],
            "why_not_closed": "Exact mating pair, shell/keying, contacts, backshell, strain relief, pinout, mass/envelope and derating are absent.",
            "owner_template": "WIRE_LIST_PINOUT_OWNER_INPUT_TEMPLATE_V1.yaml",
        },
        {
            "id": "MPI-05",
            "input": "installed finished-bundle OD and tolerance",
            "state": "HOLD_NOT_CONTROLLED",
            "controlled": False,
            "local_evidence": [
                "Catalog register has individual-wire/cable diameters without an installed construction.",
                "Route-B used OD 10 mm only in a rejected candidate.",
            ],
            "why_not_closed": "No supplier-controlled or measured installed bundle OD/tolerance for each selected sub-bundle.",
            "owner_template": "INSTALLED_CONSTRUCTION_OWNER_INPUT_TEMPLATE_V1.yaml",
        },
        {
            "id": "MPI-06",
            "input": "applicable static and dynamic bend/torsion limit versus temperature",
            "state": "HOLD_NOT_CONTROLLED",
            "controlled": False,
            "local_evidence": [
                "RFI sources contain conditional/static-or-unspecified bend data for unselected products.",
                "Route-B contains R25 legacy and R30 terminal requirement values in a rejected architecture.",
            ],
            "why_not_closed": "Selected-construction static/dynamic class, torsion, temperature derating and restoring-load data are absent.",
            "owner_template": "INSTALLED_CONSTRUCTION_OWNER_INPUT_TEMPLATE_V1.yaml",
        },
        {
            "id": "MPI-07",
            "input": "controlled installation interfaces and datums",
            "state": "HOLD_PARTIAL_LOCAL_KINEMATICS_ONLY",
            "controlled": False,
            "local_evidence": [
                "Accepted URDF controls J1..J6 local parent/child origins, joint-frame axes and limits.",
                "Joint ICD retains PCD/bolt counts as TBD; harness-routing record retains HN-00/HN-02/HN-03 and passage defects.",
            ],
            "why_not_closed": "Local kinematics do not define connector faces, feedthrough voids, clamp/guide seats, fastener interfaces, orientations or installation tolerances.",
            "owner_template": "INSTALLATION_ICD_OWNER_INPUT_TEMPLATE_V1.yaml",
        },
        {
            "id": "MPI-08",
            "input": "mission life target and acceptance factor",
            "state": "HOLD_NOT_CONTROLLED",
            "controlled": False,
            "local_evidence": [
                "E17 names eight mission segments but releases 0/8; five are numeric arm-only seeds, one symbolic, two uninstantiated.",
                "Catalog connector mating-cycle data, where present, is not moving-harness flex life.",
            ],
            "why_not_closed": "No mission/ground/contingency cycle allocation, joint-equivalent bend/torsion spectrum, qualification factor, acceptance factor or degradation limit.",
            "owner_template": "MISSION_LIFE_ALLOCATION_OWNER_INPUT_TEMPLATE_V1.yaml",
        },
    ]

    joint_ledger = parse_urdf_joints()
    audit = {
        "schema": "ROUTE_C_MPI_EVIDENCE_AUDIT_V1",
        "generated_local": GENERATED_LOCAL,
        "authority": "MACHINE_EVIDENCE_AUDIT__NO_SELECTION_NO_RELEASE",
        "source_bindings": source_bindings,
        "summary": {
            "criteria_total": 8,
            "criteria_controlled": 0,
            "criteria_hold": 8,
            "gate": "HOLD",
            "next_stage_authorized": False,
            "cad_assets_created": 0,
        },
        "audits": audits,
        "mpi07_urdf_local_kinematics": {
            "accepted_urdf_sha256": source_bindings["accepted_urdf"]["sha256"],
            "joint_count": 6,
            "joints": joint_ledger,
            "credit": "LOCAL_KINEMATIC_REFERENCE_ONLY",
            "installation_icd_closed": False,
        },
        "evidence_class_non_equivalence": [
            {"evidence": "directory_or_file_presence", "mpi_closure_credit": False},
            {"evidence": "RFI_issued_or_candidate_response", "mpi_closure_credit": False},
            {"evidence": "upstream_vendor_BOM_or_readme", "mpi_closure_credit": False},
            {"evidence": "accepted_URDF_J1_to_J6_local_kinematics", "mpi_closure_credit": False},
            {"evidence": "eight_mission_segment_names_or_numeric_seeds", "mpi_closure_credit": False},
        ],
        "route_b_values_not_inherited": [
            {"name": "bundle_outer_diameter", "value": 10.0, "unit": "mm", "inherited": False},
            {"name": "legacy_bend_radius", "value": 25.0, "unit": "mm", "inherited": False},
            {"name": "terminal_requirement_radius", "value": 30.0, "unit": "mm", "inherited": False},
            {"name": "cut_length", "value": 4001.158, "unit": "mm", "inherited": False},
        ],
        "owner_templates_required": [
            "B601_ELECTRICAL_AND_DATA_ICD_OWNER_INPUT_TEMPLATE_V1.yaml",
            "WIRE_LIST_PINOUT_OWNER_INPUT_TEMPLATE_V1.yaml",
            "INSTALLED_CONSTRUCTION_OWNER_INPUT_TEMPLATE_V1.yaml",
            "INSTALLATION_ICD_OWNER_INPUT_TEMPLATE_V1.yaml",
            "MISSION_LIFE_ALLOCATION_OWNER_INPUT_TEMPLATE_V1.yaml",
        ],
        "claim_limit": "This audit converts dispersed evidence into an executable HOLD and Owner input path; it does not close any MPI.",
    }
    write_json(OUT / "ROUTE_C_MPI_EVIDENCE_AUDIT_V1.json", audit)

    templates = build_templates(source_bindings)
    for name, document in templates.items():
        write_yaml(OUT / name, document)

    gate = {
        "schema": "ROUTE_C_MPI_EVIDENCE_GATE_V1",
        "generated_local": GENERATED_LOCAL,
        "gate": "HOLD",
        "verdict": "ROUTE_C_MPI_EVIDENCE_AUDITED__OWNER_INPUTS_UNFILLED__0_OF_8_CONTROLLED",
        "authority_class": "NON_RELEASE_EVIDENCE_AUDIT",
        "criteria_total": 8,
        "criteria_controlled": 0,
        "criteria_hold": 8,
        "criteria": [
            {
                "id": item["id"],
                "state": item["state"],
                "controlled": False,
                "owner_template": item["owner_template"],
            }
            for item in audits
        ],
        "mpi07_local_kinematics_available": True,
        "mpi07_installation_icd_closed": False,
        "e17_mission_segments_total": 8,
        "e17_mission_segments_released": 0,
        "route_b_seed_inheritance_allowed": False,
        "cad_generation_authorized": False,
        "cad_assets_created": 0,
        "next_stage_authorized": False,
        "allowed_next": [
            "Owner completes five input templates with controlled sources, units and uncertainties/tolerances",
            "independent review and supplier/bench evidence acquisition",
            "repeat this machine audit after controlled inputs are issued",
        ],
        "prohibited_next": [
            "Route-C CAD generation",
            "inherit Route-B OD/radius/length values",
            "claim MPI closure from RFI, BOM, URDF kinematics or trajectory names",
            "production dynamics, physical-contact RL or hardware motion",
        ],
        "audit_binding": {
            "path": (PACKAGE_REL / "ROUTE_C_MPI_EVIDENCE_AUDIT_V1.json").as_posix(),
            "sha256": sha256(OUT / "ROUTE_C_MPI_EVIDENCE_AUDIT_V1.json"),
        },
    }
    write_json(OUT / "ROUTE_C_MPI_EVIDENCE_GATE_V1.json", gate)

    readme = """# Route-C MPI evidence audit and Owner input pack

## Machine result

- Gate: `HOLD`
- MPI controlled: `0/8`
- Next stage authorized: `false`
- CAD created/authorized: `0 / false`

This package audits the evidence already present in the repository and provides five blank, unit-bearing Owner input templates. It does not edit the accepted URDF or any prior Route-C/Route-B artifact.

## Decisive boundary

The accepted URDF supplies local J1..J6 kinematics only. RFI files, candidate catalog data, the upstream reBot BOM/readme, directories, and the eight E17 segment names/seeds do not close product, installation, or life authority. Route-B `OD=10 mm`, `R25`, `R30`, and `4001.158 mm` are quarantined and are not inherited.

## Owner completion sequence

1. Complete `B601_ELECTRICAL_AND_DATA_ICD_OWNER_INPUT_TEMPLATE_V1.yaml` for MPI-01/02.
2. Complete `WIRE_LIST_PINOUT_OWNER_INPUT_TEMPLATE_V1.yaml` for MPI-03/04.
3. Complete `INSTALLED_CONSTRUCTION_OWNER_INPUT_TEMPLATE_V1.yaml` for MPI-05/06.
4. Complete `INSTALLATION_ICD_OWNER_INPUT_TEMPLATE_V1.yaml` for MPI-07.
5. Complete `MISSION_LIFE_ALLOCATION_OWNER_INPUT_TEMPLATE_V1.yaml` for MPI-08.
6. Bind controlled source revisions, named owners, units, and uncertainty or bounded tolerance; then repeat independent validation.

Unknown values remain `null`. A zero may be entered only when a controlled source proves that the physical value is zero.

## Rebuild and validate

From the repository root:

```powershell
python 20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/01_minimum_product_inputs/02_mpi_evidence_audit/99_tools/build_route_c_mpi_evidence_audit.py
python 20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/01_minimum_product_inputs/02_mpi_evidence_audit/99_tools/validate_route_c_mpi_evidence_audit.py
```
"""
    (OUT / "README.md").write_text(readme, encoding="utf-8")

    manifest_names = [
        "ROUTE_C_MPI_EVIDENCE_AUDIT_AUTHORITY_CONTRACT_V1.json",
        "ROUTE_C_MPI_EVIDENCE_AUDIT_V1.json",
        *templates.keys(),
        "ROUTE_C_MPI_EVIDENCE_GATE_V1.json",
        "README.md",
        "99_tools/build_route_c_mpi_evidence_audit.py",
        "99_tools/validate_route_c_mpi_evidence_audit.py",
    ]
    manifest = {
        "schema": "ROUTE_C_MPI_EVIDENCE_AUDIT_OUTPUT_MANIFEST_V1",
        "generated_local": GENERATED_LOCAL,
        "package_root": PACKAGE_REL.as_posix(),
        "validation_report_excluded_to_avoid_recursive_hash": "ROUTE_C_MPI_EVIDENCE_AUDIT_VALIDATION_V1.json",
        "files": [binding((PACKAGE_REL / name).as_posix()) for name in manifest_names],
    }
    write_json(OUT / "ROUTE_C_MPI_EVIDENCE_AUDIT_OUTPUT_MANIFEST_V1.json", manifest)

    print(json.dumps({
        "package": PACKAGE_REL.as_posix(),
        "gate": gate["gate"],
        "criteria_controlled": gate["criteria_controlled"],
        "criteria_total": gate["criteria_total"],
        "manifest_sha256": sha256(OUT / "ROUTE_C_MPI_EVIDENCE_AUDIT_OUTPUT_MANIFEST_V1.json"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
