"""Build the Route-C vendor-RFI shortlist without selecting a product.

The catalog facts in this package are research inputs only.  Every value keeps
its unit, source and uncertainty state.  Missing project loads, exact part
numbers, installed-bundle properties and dynamic-life evidence remain null or
explicitly UNKNOWN and therefore cannot close RC-CEG-03.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[4]
BASE_REL = (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "ecr_b601_harness_rated_envelope"
)
OUT_REL = f"{BASE_REL}/08_route_c/01_minimum_product_inputs"
GENERATED_LOCAL = "2026-08-23T15:20:00+08:00"
GENERATED_CLOCK_SOURCE = "LATEST_BOUND_PRODUCT_INPUT_VALIDATION_TIMESTAMP"

INPUTS = {
    "product_input_register": (
        f"{OUT_REL}/ROUTE_C_MINIMUM_PRODUCT_INTERFACE_INPUT_REGISTER_V1.json"
    ),
    "product_input_gate": f"{OUT_REL}/ROUTE_C_PRODUCT_INPUT_GATE_V1.json",
    "product_input_validation": f"{OUT_REL}/ROUTE_C_PRODUCT_INPUT_VALIDATION_V1.json",
    "odr42_request": f"{BASE_REL}/08_route_c/ROUTE_C_OWNER_DECISION_REQUEST_ODR42_V1.yaml",
    "accepted_urdf": "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
    "solar_r2": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.step"
    ),
}

EXPECTED_URDF_SHA256 = (
    "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
)
EXPECTED_SOLAR_SHA256 = (
    "21FF77B882DBFAB87B3E77DD56817EFC7F321C68E30AFEDCDDBB4D79B9915795"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_json(relative_path: str) -> dict[str, Any]:
    return json.loads((REPO / relative_path).read_text(encoding="utf-8"))


def write_json(relative_path: str, value: Any) -> None:
    path = REPO / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_text(relative_path: str, value: str) -> None:
    path = REPO / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8", newline="\n")


def binding(name: str, relative_path: str) -> dict[str, Any]:
    path = REPO / relative_path
    if not path.is_file() or path.stat().st_size <= 0:
        raise FileNotFoundError(f"missing or empty input: {relative_path}")
    return {
        "name": name,
        "path": relative_path,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def q(
    value: float | int | str | None,
    unit: str,
    source: str,
    uncertainty: str | None = None,
    qualifier: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "value": value,
        "unit": unit,
        "source": source,
        "uncertainty": uncertainty,
        "uncertainty_state": (
            "DECLARED_BOUND_OR_TOLERANCE"
            if uncertainty is not None
            else "NOT_PUBLISHED_IN_REVIEWED_SOURCE__UNKNOWN"
        ),
    }
    if qualifier is not None:
        result["qualifier"] = qualifier
    return result


def build_shortlist() -> dict[str, Any]:
    source_urls = {
        "GORE_SPACEWIRE": "https://www.gore.com/products/spacewire",
        "GORE_2025_CATALOG": (
            "https://www.gore.com/sites/default/files/resources/pdf/2025-09/"
            "gore-space-cables-traditional-brochure-us.pdf"
        ),
        "GLENAIR_GSWM": (
            "https://cdn.glenair.com/micro-d/pdf/b/"
            "spacewire-cable-assembly-in-back-to-back-or-single-ended-wire-configurations.pdf"
        ),
        "AXON_SPACE_LINKS": (
            "https://www.axon-cable.com/publications/axon-space-high-speed-links_cg.pdf"
        ),
        "AXON_SPACE_MICRO_NANO_D": (
            "https://www.axon-cable.com/PageSite/MediaFile?idPageLangue=946&"
            "path=%2FPDF%2Faxon-micro-D-connectors-space_cg.pdf&type=4"
        ),
        "TE_55_9960_26": "https://www.te.com/en/product-CD03823001.html",
        "GLENAIR_MICRO_D_SPEC": (
            "https://www.glenair.com/micro-d/pdf/micro-d-specifications.pdf"
        ),
        "GLENAIR_MICRO_D_WEIGHT": (
            "https://www.glenair.com/micro-d/pdf/a/micro-d-weights.pdf"
        ),
        "AXON_EQUIPMENT_WIRES": (
            "https://www.axon-cable.com/publications/equipment-wires-cables_cg.pdf"
        ),
    }
    source_titles = {
        "GORE_SPACEWIRE": "GORE SpaceWire Cables product page",
        "GORE_2025_CATALOG": "GORE Space Cables for Traditional Space Applications catalog",
        "GLENAIR_GSWM": "Glenair GSWM SpaceWire cable assemblies datasheet",
        "AXON_SPACE_LINKS": "Axon Space High-Speed Links catalog",
        "AXON_SPACE_MICRO_NANO_D": "Axon Micro-D and Nano-D Connectors for Space catalog",
        "TE_55_9960_26": "TE 55/9960-26 product page",
        "GLENAIR_MICRO_D_SPEC": "Glenair Micro-D specifications",
        "GLENAIR_MICRO_D_WEIGHT": "Glenair Micro-D weights",
        "AXON_EQUIPMENT_WIRES": "Axon Equipment Wires and Cables catalog",
    }
    source_controls = {
        source_id: {
            "document_title": source_titles[source_id],
            "url": url,
            "accessed_local_date": "2026-08-23",
            "local_snapshot_path": None,
            "local_snapshot_sha256": None,
            "supplier_controlled_revision": None,
            "controlled_supplier_document_received": False,
            "traceability_state": "OFFICIAL_URL_ONLY__CONTROLLED_COPY_REQUIRED_BEFORE_SELECTION",
        }
        for source_id, url in source_urls.items()
    }

    candidates = [
        {
            "candidate_id": "RFI-A",
            "name": "environment-mature SpaceWire route",
            "intended_function": "data bus candidate",
            "rfi_priority": 2,
            "selection_state": "RFI_SHORTLIST_NOT_SELECTED",
            "flight_shortlist": True,
            "products": [
                {
                    "vendor": "W. L. Gore & Associates",
                    "family_or_part": "SpaceWire variant 01 / ESCC390200301B",
                    "role": "28 AWG four-pair data cable",
                    "source_ids": ["GORE_SPACEWIRE", "GORE_2025_CATALOG"],
                    "catalog_metrics": {
                        "finished_outer_diameter_max": q(
                            7.5, "mm", "GORE_2025_CATALOG Table 21 p.30"
                        ),
                        "linear_mass_max": q(
                            85.0, "g/m", "GORE_2025_CATALOG Table 21 p.30"
                        ),
                        "minimum_bend_radius": q(
                            45.0,
                            "mm",
                            "GORE_2025_CATALOG Table 21 p.30",
                            qualifier="CATALOG_VALUE__DYNAMIC_CLASS_NOT_STATED",
                        ),
                        "data_rate": q(
                            400.0,
                            "Mbit/s",
                            "GORE_SPACEWIRE product page",
                            qualifier="PRODUCT_FAMILY_CAPABILITY",
                        ),
                        "temperature_min": q(-200.0, "degC", "GORE_SPACEWIRE product page"),
                        "temperature_max": q(180.0, "degC", "GORE_SPACEWIRE product page"),
                        "radiation_total_dose": q(
                            10.0,
                            "Mrad",
                            "GORE_SPACEWIRE product page",
                            qualifier="GREATER_THAN_OR_EQUAL_TO__PRODUCT_FAMILY_CAPABILITY",
                        ),
                    },
                },
                {
                    "vendor": "Glenair",
                    "family_or_part": "GSWM SpaceWire Micro-D assembly, exact dash number TBD",
                    "role": "9-contact SpaceWire connector assembly",
                    "source_ids": ["GLENAIR_GSWM"],
                    "catalog_metrics": {
                        "contact_count": q(9, "contact", "GLENAIR_GSWM datasheet"),
                        "wire_gauge_options": q(
                            "26_or_28", "AWG", "GLENAIR_GSWM datasheet"
                        ),
                        "default_temperature_min": q(-55.0, "degC", "GLENAIR_GSWM datasheet"),
                        "default_temperature_max": q(125.0, "degC", "GLENAIR_GSWM datasheet"),
                        "component_mass": q(None, "g", "NOT_PUBLISHED_FOR_SELECTED_DASH_NUMBER"),
                    },
                },
            ],
            "known_strength": "official space-qualified data-route evidence and screening options",
            "blocking_unknowns": [
                "exact connector/backshell/dash numbers and assembly mass",
                "project protocol, pair count, pin map and bonding",
                "installed-bundle OD/tolerance after branching and protection",
                "dynamic bend/torsion life and restoring-load curves",
            ],
        },
        {
            "candidate_id": "RFI-B",
            "name": "low-mass SpaceWire route",
            "intended_function": "data bus candidate",
            "rfi_priority": 1,
            "selection_state": "RFI_SHORTLIST_NOT_SELECTED",
            "flight_shortlist": True,
            "products": [
                {
                    "vendor": "Axon' Cable",
                    "family_or_part": "P551259",
                    "role": "28 AWG space high-speed cable",
                    "source_ids": ["AXON_SPACE_LINKS"],
                    "catalog_metrics": {
                        "conductor_area": q(0.093, "mm^2", "AXON_SPACE_LINKS P551259 table"),
                        "finished_outer_diameter_max": q(
                            6.5, "mm", "AXON_SPACE_LINKS P551259 table"
                        ),
                        "linear_mass_max": q(
                            42.0, "g/m", "AXON_SPACE_LINKS P551259 table"
                        ),
                        "minimum_fully_static_bend_radius": q(
                            25.0,
                            "mm",
                            "AXON_SPACE_LINKS P551259 table",
                            qualifier="FULLY_STATIC_ONLY",
                        ),
                        "temperature_min": q(-100.0, "degC", "AXON_SPACE_LINKS P551259 table"),
                        "temperature_max": q(150.0, "degC", "AXON_SPACE_LINKS P551259 table"),
                        "characteristic_impedance": q(
                            100.0,
                            "ohm",
                            "AXON_SPACE_LINKS P551259 table",
                            uncertainty="plus_or_minus_6_ohm_at_400_MHz",
                        ),
                    },
                },
                {
                    "vendor": "Axon' Cable",
                    "family_or_part": "Space Nano-D, exact part number TBD",
                    "role": "data connector family candidate",
                    "source_ids": ["AXON_SPACE_MICRO_NANO_D"],
                    "catalog_metrics": {
                        "contact_count_range": q("9_to_51", "contact", "AXON_SPACE_MICRO_NANO_D catalog"),
                        "current_per_contact": q(1.0, "A/contact", "AXON_SPACE_MICRO_NANO_D catalog"),
                        "mating_cycles_min": q(200, "cycle", "AXON_SPACE_MICRO_NANO_D catalog"),
                        "temperature_min": q(-55.0, "degC", "AXON_SPACE_MICRO_NANO_D catalog"),
                        "temperature_max": q(150.0, "degC", "AXON_SPACE_MICRO_NANO_D catalog"),
                        "approximate_mass_with_screwlock_backshell": q(
                            2.0,
                            "g",
                            "AXON_SPACE_MICRO_NANO_D catalog",
                            qualifier="APPROXIMATE_FAMILY_VALUE__NOT_RELEASE_MASS",
                        ),
                    },
                },
            ],
            "known_strength": "lowest reviewed catalog cable mass among data-route candidates",
            "blocking_unknowns": [
                "exact Nano-D part number, shell, keying, backshell and pinout",
                "allowable current/voltage and thermal derating for the complete assembly",
                "dynamic bend/torsion life and post-flex electrical performance",
                "installed-bundle geometry and restoring-load curves",
            ],
        },
        {
            "candidate_id": "RFI-C",
            "name": "discrete power and control baseline",
            "intended_function": "motor/brake/gripper power and discrete control candidate",
            "rfi_priority": 1,
            "selection_state": "RFI_SHORTLIST_NOT_SELECTED",
            "flight_shortlist": True,
            "products": [
                {
                    "vendor": "TE Connectivity",
                    "family_or_part": "55/9960-26 (CD03823001)",
                    "role": "26 AWG radiation-crosslinked ETFE equipment wire",
                    "source_ids": ["TE_55_9960_26"],
                    "catalog_metrics": {
                        "conductor_area": q(0.13, "mm^2", "TE_55_9960_26 product page"),
                        "finished_outer_diameter_nominal": q(0.72, "mm", "TE_55_9960_26 product page"),
                        "linear_mass_nominal": q(1.81, "g/m", "TE_55_9960_26 product page"),
                        "dc_resistance_max_at_20_degC": q(
                            149.0, "ohm/1000m", "TE_55_9960_26 product page"
                        ),
                        "voltage_rating": q(600.0, "V", "TE_55_9960_26 product page"),
                        "temperature_min": q(-65.0, "degC", "TE_55_9960_26 product page"),
                        "temperature_max": q(200.0, "degC", "TE_55_9960_26 product page"),
                    },
                },
                {
                    "vendor": "Glenair",
                    "family_or_part": "Space-grade Micro-D, exact dash number TBD",
                    "role": "power/control connector family candidate",
                    "source_ids": ["GLENAIR_MICRO_D_SPEC", "GLENAIR_MICRO_D_WEIGHT"],
                    "catalog_metrics": {
                        "continuous_current_per_contact": q(
                            3.0, "A/contact", "GLENAIR_MICRO_D_SPEC"
                        ),
                        "mating_cycles": q(500, "cycle", "GLENAIR_MICRO_D_SPEC"),
                        "temperature_min": q(-55.0, "degC", "GLENAIR_MICRO_D_SPEC"),
                        "temperature_max": q(150.0, "degC", "GLENAIR_MICRO_D_SPEC"),
                        "shield_effectiveness_with_ground_spring": q(
                            65.0,
                            "dB",
                            "GLENAIR_MICRO_D_SPEC",
                            qualifier="CONFIGURATION_DEPENDENT",
                        ),
                        "nine_contact_pigtail_connector_nominal_mass": q(
                            1.6,
                            "g",
                            "GLENAIR_MICRO_D_WEIGHT",
                            uncertainty="catalog_max_plus_10_percent",
                            qualifier="CONNECTOR_ONLY__EXACT_CONFIGURATION_TO_VERIFY",
                        ),
                    },
                },
            ],
            "known_strength": "traceable high-temperature discrete-wire and Micro-D baseline",
            "blocking_unknowns": [
                "B601 per-function load map, allowable voltage drop and simultaneity",
                "conductor/contact parallelization, derating and temperature rise",
                "exact connector, backshell, pin map and processed seal outgassing state",
                "dynamic wire/bundle flex life and installed restoring load",
            ],
            "special_caveat": (
                "Glenair reports as-received fluorosilicone seal CVCM above the assembled "
                "nonmetallic-material summary limit; exact processing and TVAC evidence must be controlled."
            ),
        },
        {
            "candidate_id": "RFI-D",
            "name": "extra-flex engineering-model route",
            "intended_function": "ground dynamic article and supplier test enquiry only",
            "rfi_priority": 1,
            "selection_state": "ENGINEERING_MODEL_RFI_ONLY",
            "flight_shortlist": False,
            "products": [
                {
                    "vendor": "Axon' Cable",
                    "family_or_part": "RE2633 and RET2633 Sh E2",
                    "role": "extra-flex discrete/shielded engineering-sample wires",
                    "source_ids": ["AXON_EQUIPMENT_WIRES"],
                    "catalog_metrics": {
                        "RE2633_conductor_area": q(0.13, "mm^2", "AXON_EQUIPMENT_WIRES"),
                        "RE2633_outer_diameter_nominal": q(0.96, "mm", "AXON_EQUIPMENT_WIRES"),
                        "RE2633_linear_mass_approximate": q(
                            2.30, "g/m", "AXON_EQUIPMENT_WIRES", qualifier="APPROXIMATE"
                        ),
                        "RE2633_voltage_rating": q(600.0, "V_ac", "AXON_EQUIPMENT_WIRES"),
                        "RET2633_outer_diameter_nominal": q(2.20, "mm", "AXON_EQUIPMENT_WIRES"),
                        "RET2633_linear_mass_approximate": q(
                            11.5, "g/m", "AXON_EQUIPMENT_WIRES", qualifier="APPROXIMATE"
                        ),
                        "temperature_min": q(-90.0, "degC", "AXON_EQUIPMENT_WIRES"),
                        "temperature_max": q(200.0, "degC", "AXON_EQUIPMENT_WIRES"),
                        "quantified_dynamic_life": q(
                            None,
                            "cycle",
                            "NOT_PUBLISHED_IN_REVIEWED_CATALOG",
                            qualifier="UNKNOWN",
                        ),
                    },
                },
                {
                    "vendor": "Axon' Cable",
                    "family_or_part": "Space Micro-D, exact part number TBD",
                    "role": "engineering-article connector family",
                    "source_ids": ["AXON_SPACE_MICRO_NANO_D"],
                    "catalog_metrics": {
                        "current_per_contact_max_for_AWG26": q(
                            2.5, "A/contact", "AXON_SPACE_MICRO_NANO_D catalog"
                        ),
                        "mating_cycles": q(500, "cycle", "AXON_SPACE_MICRO_NANO_D catalog"),
                        "nine_way_approximate_mass_with_screwlock_backshell": q(
                            8.0,
                            "g",
                            "AXON_SPACE_MICRO_NANO_D catalog",
                            qualifier="APPROXIMATE_FAMILY_VALUE",
                        ),
                    },
                },
            ],
            "known_strength": "catalog identifies extra-flex construction suitable for obtaining test articles",
            "blocking_unknowns": [
                "quantified bend radius, angle, torsion, speed, temperature and cycle life",
                "space environmental qualification of the complete cable construction",
                "outgassing, radiation, atomic oxygen, abrasion and particulate evidence",
                "post-flex electrical degradation and restoring-load curves",
            ],
            "flight_exclusion_rule": (
                "Exclude from flight shortlist until space-environment and quantified flex evidence "
                "for the exact construction are independently controlled."
            ),
        },
    ]

    return {
        "schema": "ROUTE_C_VENDOR_RFI_SHORTLIST_V1",
        "generated_local": GENERATED_LOCAL,
        "generated_clock_source": GENERATED_CLOCK_SOURCE,
        "record_type": "OFFICIAL_SOURCE_RFI_SHORTLIST__NOT_PRODUCT_SELECTION",
        "authority": "CANDIDATE_RESEARCH_ONLY__NO_CAD_OR_RELEASE_AUTHORITY",
        "decision_invariants": [
            "catalog family data never becomes project-selected hardware without an exact part number and owner approval",
            "catalog bend radius is not dynamic-life evidence unless the source explicitly states the applicable regime",
            "connector mating cycles are not harness flex cycles",
            "component cable OD and mass are not installed dress-pack OD and mass",
            "null uncertainty remains UNKNOWN and is never coerced to zero",
        ],
        "source_urls": source_urls,
        "source_controls": source_controls,
        "shortlist": candidates,
        "counts": {
            "candidate_routes": 4,
            "flight_rfi_routes": 3,
            "engineering_model_only_routes": 1,
            "selected_routes": 0,
            "exact_complete_assemblies_selected": 0,
        },
        "common_blocking_unknowns": [
            "B601 current/load/protocol/pin map authority",
            "finished installed bundle OD/tolerance and ovalization",
            "dynamic bend/torsion limits and life spectrum",
            "restoring force/torque versus angle/rate/temperature/cycles",
            "exact complete-assembly mass and tolerance",
            "selected-construction environmental and post-flex electrical evidence",
        ],
        "selection_state": "NO_PRODUCT_SELECTED",
        "rc_ceg_03": "HOLD",
        "next_stage_authorized": False,
    }


def build_requirements_yaml() -> str:
    return """
schema: ROUTE_C_VENDOR_RFI_REQUIREMENTS_V1
generated_local: '2026-08-23T15:20:00+08:00'
generated_clock_source: LATEST_BOUND_PRODUCT_INPUT_VALIDATION_TIMESTAMP
record_type: SUPPLIER_AND_PROJECT_DATA_REQUEST__NOT_PURCHASE_OR_SELECTION
authority: C1_INPUT_FREEZE_PREPARATION_ONLY
applies_to_candidates: [RFI-A, RFI-B, RFI-C, RFI-D]
submission_contract:
  units_required: true
  exact_part_number_and_revision_required: true
  source_or_test_record_required: true
  uncertainty_or_bounded_tolerance_required: true
  null_policy: NULL_OR_TBD_REMAINS_UNKNOWN_AND_CANNOT_CLOSE_A_GATE
  typical_value_policy: TYPICAL_WITHOUT_CONTROLLED_SOURCE_IS_INFORMATIONAL_ONLY
project_owner_inputs:
  - request_id: PRJ-01
    owner_role: B601_ELECTRICAL_OWNER
    subject: per-function power and load map
    required_fields: [function, bus_voltage_V, nominal_current_A, rms_current_A, peak_current_A, peak_duration_s, simultaneity_case, allowable_voltage_drop_V, derating_rule, source_revision]
  - request_id: PRJ-02
    owner_role: B601_AVIONICS_OWNER
    subject: protocol and EMC definition
    required_fields: [protocol, data_rate_bit_per_s, topology, impedance_ohm, pair_count, shield_bond, redundancy, EMC_separation, source_revision]
  - request_id: PRJ-03
    owner_role: HARNESS_ELECTRICAL_OWNER
    subject: circuit, pin and conductor map
    required_fields: [circuit_id, from_pin, to_pin, conductor_part_number, contact_part_number, gauge, shield_termination, spare_policy, voltage_drop_check]
  - request_id: PRJ-04
    owner_role: MECHANICAL_INTERFACE_OWNER
    subject: HN-00 through HN-03 and J1 through J6 installation ICD
    required_fields: [frame, xyz_mm, orientation, datum_scheme, connector_face, passage_or_guide_geometry, clamp_fastener_interface, installation_access, tolerance_mm, source_revision]
  - request_id: PRJ-05
    owner_role: SYSTEMS_AND_QUALIFICATION_OWNER
    subject: mission-life and qualification allocation
    required_fields: [segment_id, joint_motion_cycles, angle_range_rad, rate_rad_per_s, temperature_degC, vacuum_condition, qualification_factor, acceptance_factor, combined_bend_torsion_spectrum, source_revision]
  - request_id: PRJ-06
    owner_role: MECHANICAL_DYNAMICS_AND_CONTROL_OWNERS
    subject: allowable harness restoring-load allocation by joint and mission segment
    required_fields: [joint_id, segment_id, angle_rad, rate_rad_per_s, temperature_degC, allowable_force_N, allowable_torque_Nm, margin_rule, actuator_or_control_budget_source, uncertainty]
supplier_rfi_packages:
  - request_id: RFI-01
    subject: exact configuration and drawing
    required_fields: [exact_part_number, revision, controlled_drawing, conductor_construction, shield_construction, jacket_material, connector, contact, backshell, strain_relief, keying]
  - request_id: RFI-02
    subject: finished geometry and installation envelope
    required_fields: [finished_OD_mm, OD_tolerance_mm, ovalization_limit_mm, connector_envelope_mm, backshell_envelope_mm, minimum_static_bend_radius_mm, applicable_temperature_degC]
  - request_id: RFI-03
    subject: dynamic bend and torsion capability
    required_fields: [minimum_dynamic_bend_radius_mm, bend_angle_deg, torsion_deg_per_m, motion_speed_rad_per_s, temperature_degC, vacuum_condition, cycles, failure_criterion]
  - request_id: RFI-04
    subject: mass properties
    required_fields: [cable_linear_mass_g_per_m, cable_mass_tolerance, connector_mass_g, backshell_mass_g, clamp_mass_g, protection_mass_g_per_m, slack_allowance_definition]
  - request_id: RFI-05
    subject: restoring-load characterization
    required_fields: [article_configuration, angle_rad, rate_rad_per_s, temperature_degC, accumulated_cycles, force_N, torque_Nm, hysteresis_definition, uncertainty, raw_data_hash]
  - request_id: RFI-06
    subject: electrical derating and EMC
    required_fields: [voltage_rating_V, current_derating_A_vs_temperature, temperature_rise_degC, dc_resistance_ohm_per_m, allowable_parallel_contacts, impedance_ohm, insertion_loss_dB, crosstalk_dB, shield_transfer_impedance, bond_scheme]
  - request_id: RFI-07
    subject: environment and materials
    required_fields: [temperature_range_degC, TML_percent, CVCM_percent, TVAC_condition, radiation_dose_krad, atomic_oxygen_evidence, abrasion_evidence, particulate_evidence, material_and_process_list]
  - request_id: RFI-08
    subject: post-flex acceptance performance
    required_fields: [continuity_limit_ohm, insulation_resistance_ohm, dielectric_test_V, shield_check, pull_test_N, impedance_change_percent, resistance_change_percent, visual_failure_criteria]
  - request_id: RFI-09
    subject: procurement and authority
    required_fields: [exact_part_number, current_availability, lead_time_week, MOQ, lot_traceability, certificate_of_conformance, agency_or_owner_approval_path, export_or_handling_constraints]
acceptance_rule:
  C2_entry: PRJ-01..PRJ-05 plus RFI-01..RFI-04 must be configuration-controlled and MPI-01..MPI-08 must all be CONTROLLED by named owners.
  later_release: PRJ-06 plus RFI-05..RFI-08 must close allowable and measured restoring-load, life, environment and post-install verification evidence.
  no_automatic_selection: A complete RFI response permits a trade review only; it does not select or release hardware.
"""


def candidate_by_id(shortlist: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    matches = [item for item in shortlist["shortlist"] if item["candidate_id"] == candidate_id]
    if len(matches) != 1:
        raise ValueError(f"expected one candidate {candidate_id}, got {len(matches)}")
    return matches[0]


def build_gate(shortlist: dict[str, Any]) -> dict[str, Any]:
    product_gate = read_json(INPUTS["product_input_gate"])
    product_validation = read_json(INPUTS["product_input_validation"])
    product_register = read_json(INPUTS["product_input_register"])
    immutable_ok = (
        sha256_file(REPO / INPUTS["accepted_urdf"]) == EXPECTED_URDF_SHA256
        and sha256_file(REPO / INPUTS["solar_r2"]) == EXPECTED_SOLAR_SHA256
    )
    criteria = [
        {
            "id": "RFI-G01",
            "name": "official-source candidate routes are traceable",
            "state": "PASS_RESEARCH_INTEGRITY_ONLY",
            "release_credit": False,
            "observed": len(shortlist["source_urls"]) == 9,
        },
        {
            "id": "RFI-G02",
            "name": "no catalog candidate silently selected",
            "state": "PASS_FAIL_CLOSED",
            "release_credit": False,
            "observed": shortlist["counts"]["selected_routes"] == 0,
        },
        {
            "id": "RFI-G03",
            "name": "engineering-model route excluded from flight shortlist",
            "state": "PASS_FAIL_CLOSED",
            "release_credit": False,
            "observed": (
                candidate_by_id(shortlist, "RFI-D")["flight_shortlist"] is False
                and candidate_by_id(shortlist, "RFI-D")["selection_state"]
                == "ENGINEERING_MODEL_RFI_ONLY"
            ),
        },
        {
            "id": "RFI-G04",
            "name": "minimum product/interface inputs controlled",
            "state": "HOLD_0_OF_8",
            "release_credit": False,
            "observed": product_gate["criteria_controlled"] == 0,
        },
        {
            "id": "RFI-G05",
            "name": "ODR-42 owner authority",
            "state": "HOLD_PENDING",
            "release_credit": False,
            "observed": product_register["local_source_bindings"]["odr42_request"]["owner_decision"]
            == "PENDING",
        },
        {
            "id": "RFI-G06",
            "name": "immutable URDF and Solar assets unchanged",
            "state": "PASS_INTEGRITY_ONLY" if immutable_ok else "HOLD_HASH_MISMATCH",
            "release_credit": False,
            "observed": immutable_ok,
        },
        {
            "id": "RFI-G07",
            "name": "upstream candidate pack independently validated",
            "state": "PASS_INTEGRITY_ONLY",
            "release_credit": False,
            "observed": (
                product_validation["package_integrity_pass"] is True
                and product_validation["checks_passed"]
                == product_validation["checks_total"]
                and product_validation["negative_controls_passed"]
                == product_validation["negative_controls_total"]
            ),
        },
        {
            "id": "RFI-G08",
            "name": "official-source revision/content control",
            "state": "HOLD_URL_ONLY_SOURCE_CONTROL",
            "release_credit": False,
            "observed": all(
                item["controlled_supplier_document_received"] is False
                and item["local_snapshot_sha256"] is None
                and item["supplier_controlled_revision"] is None
                for item in shortlist["source_controls"].values()
            ),
        },
    ]
    confirmed = sum(bool(item["observed"]) for item in criteria)
    return {
        "schema": "ROUTE_C_VENDOR_RFI_DECISION_GATE_V1",
        "generated_local": GENERATED_LOCAL,
        "generated_clock_source": GENERATED_CLOCK_SOURCE,
        "gate": "HOLD",
        "verdict": "ROUTE_C_RFI_SHORTLIST_READY__NO_PRODUCT_SELECTED__RC_CEG_03_HOLD",
        "authority": "RFI_PREPARATION_ONLY__NO_PURCHASE_CAD_OR_RELEASE_AUTHORITY",
        "input_bindings": [binding(name, path) for name, path in INPUTS.items()],
        "criteria": criteria,
        "criteria_total": len(criteria),
        "criteria_confirmed": confirmed,
        "candidate_routes": shortlist["counts"],
        "minimum_inputs": {
            "controlled": product_gate["criteria_controlled"],
            "total": product_gate["criteria_total"],
            "rc_ceg_03": product_gate["rc_ceg_03"],
        },
        "allowed_now": [
            "issue non-binding supplier RFIs for exact data and samples",
            "complete B601 electrical/protocol/pin-map inputs",
            "plan dynamic bend-torsion and restoring-load tests",
            "refine the candidate trade with controlled responses",
        ],
        "prohibited_now": [
            "product selection or procurement-release claim",
            "Route-C CAD/STEP generation",
            "installed bundle OD, mass, flex-life or torque release",
            "production dynamics, physical contact RL or hardware motion",
        ],
        "rc_ceg_03": "HOLD",
        "odr42": "PENDING",
        "next_stage_authorized": False,
        "immutable_asset_hashes": {
            "accepted_urdf": EXPECTED_URDF_SHA256,
            "solar_r2": EXPECTED_SOLAR_SHA256,
        },
    }


def main() -> None:
    shortlist_rel = f"{OUT_REL}/ROUTE_C_VENDOR_RFI_SHORTLIST_V1.json"
    requirements_rel = f"{OUT_REL}/ROUTE_C_VENDOR_RFI_REQUIREMENTS_V1.yaml"
    gate_rel = f"{OUT_REL}/ROUTE_C_VENDOR_RFI_DECISION_GATE_V1.json"
    manifest_rel = f"{OUT_REL}/ROUTE_C_VENDOR_RFI_OUTPUT_MANIFEST_V1.json"

    shortlist = build_shortlist()
    write_json(shortlist_rel, shortlist)
    write_text(requirements_rel, build_requirements_yaml())
    write_json(gate_rel, build_gate(shortlist))

    output_paths = [shortlist_rel, requirements_rel, gate_rel]
    source_paths = [
        f"{BASE_REL}/99_tools/build_route_c_vendor_rfi.py",
        f"{BASE_REL}/99_tools/validate_route_c_vendor_rfi.py",
    ]
    manifest = {
        "schema": "ROUTE_C_VENDOR_RFI_OUTPUT_MANIFEST_V1",
        "generated_local": GENERATED_LOCAL,
        "generated_clock_source": GENERATED_CLOCK_SOURCE,
        "hash_algorithm": "SHA-256",
        "outputs": [binding(Path(path).name, path) for path in output_paths],
        "sources": [binding(Path(path).name, path) for path in source_paths],
        "output_count": len(output_paths),
        "source_count": len(source_paths),
        "validation_report_excluded_to_avoid_recursive_hash": True,
    }
    write_json(manifest_rel, manifest)
    gate = read_json(gate_rel)
    print(
        json.dumps(
            {
                "verdict": gate["verdict"],
                "criteria": f'{gate["criteria_confirmed"]}/{gate["criteria_total"]}',
                "candidate_routes": gate["candidate_routes"]["candidate_routes"],
                "selected_routes": gate["candidate_routes"]["selected_routes"],
                "manifest_sha256": sha256_file(REPO / manifest_rel),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
