from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import yaml


SCRIPT = Path(__file__).resolve()
PACKAGE = SCRIPT.parent.parent
ROUTE = PACKAGE / "08_route_c"
OUT = ROUTE / "01_minimum_product_inputs"
WORKSPACE = PACKAGE.parents[2]
GENERATED_LOCAL = "2026-08-23T15:20:00+08:00"

CONTRACT = ROUTE / "ROUTE_C_PRELIMINARY_DESIGN_CONTRACT_V1.json"
ODR42 = ROUTE / "ROUTE_C_OWNER_DECISION_REQUEST_ODR42_V1.yaml"
HARNESS_ROUTING = PACKAGE.parent / "wp1_structure_cad" / "HARNESS_ROUTING_V1.yaml"
URDF = WORKSPACE / "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
SOLAR_R2 = (
    WORKSPACE
    / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.step"
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def rel(path: Path) -> str:
    return path.resolve().relative_to(WORKSPACE.resolve()).as_posix()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def quantity(
    value,
    unit: str,
    semantic: str,
    source_id: str,
    *,
    uncertainty_reason: str,
    derivation: str | None = None,
):
    record = {
        "value": value,
        "unit": unit,
        "semantic": semantic,
        "uncertainty": {
            "standard_uncertainty": None,
            "distribution": None,
            "coverage_factor": None,
            "reason": uncertainty_reason,
        },
        "provenance": {"source_id": source_id},
        "project_design_authority": False,
    }
    if derivation:
        record["derivation"] = derivation
    return record


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    odr = yaml.safe_load(ODR42.read_text(encoding="utf-8"))
    routing = yaml.safe_load(HARNESS_ROUTING.read_text(encoding="utf-8"))

    sources = {
        "schema": "ROUTE_C_PRODUCT_SOURCE_REGISTER_V1",
        "generated_local": GENERATED_LOCAL,
        "authority": "OFFICIAL_SOURCE_RESEARCH__CANDIDATE_LIBRARY_ONLY__NO_PROJECT_SELECTION",
        "retrieval_date": "2026-08-23",
        "source_policy": {
            "accepted_sources": "official manufacturer product pages/datasheets and official agency standards only",
            "catalog_fact_authority": "source-controlled at retrieval; supplier confirmation still required at procurement",
            "project_selection_authority": False,
            "uncertainty_policy": "No missing tolerance, distribution, or uncertainty is encoded as zero.",
            "dynamic_flex_policy": "Mating-cycle ratings and static/unspecified bend radii do not prove six-joint dynamic flex life.",
        },
        "sources": [
            {
                "id": "SRC-TE-SPEC55-22",
                "publisher": "TE Connectivity",
                "source_class": "OFFICIAL_MANUFACTURER_PRODUCT_PAGE",
                "url": "https://www.te.com/en/product-7534143001.html",
                "product": "55/9952-22-1(LAT3)",
                "catalog_state_at_retrieval": "ACTIVE__NOT_CURRENTLY_AVAILABLE",
                "intended_candidate_use": "individual motor-power or powered-discrete conductor pending load analysis",
                "facts": {
                    "wire_size_awg": "22",
                    "conductor_area": quantity(0.33, "mm^2", "PUBLISHED_VALUE", "SRC-TE-SPEC55-22", uncertainty_reason="VENDOR_TOLERANCE_NOT_DISCLOSED"),
                    "outside_diameter": quantity(1.1, "mm", "PUBLISHED_VALUE", "SRC-TE-SPEC55-22", uncertainty_reason="VENDOR_TOLERANCE_NOT_DISCLOSED"),
                    "linear_mass": quantity(4.27, "g/m", "PUBLISHED_NOMINAL", "SRC-TE-SPEC55-22", uncertainty_reason="VENDOR_NOMINAL_TOLERANCE_NOT_DISCLOSED", derivation="4.27 kg/km is numerically 4.27 g/m"),
                    "maximum_resistance_at_20C": quantity(54.3, "ohm/1000m", "PUBLISHED_MAXIMUM", "SRC-TE-SPEC55-22", uncertainty_reason="PUBLISHED_LIMIT__TEST_AND_LOT_VARIATION_NOT_DISCLOSED"),
                    "operating_voltage": quantity(600, "V", "PUBLISHED_RATING", "SRC-TE-SPEC55-22", uncertainty_reason="RATING_NOT_RANDOM_ESTIMATE"),
                    "temperature_min": quantity(-65, "degC", "PUBLISHED_OPERATING_BOUND", "SRC-TE-SPEC55-22", uncertainty_reason="BOUND_NOT_RANDOM_ESTIMATE"),
                    "temperature_max": quantity(200, "degC", "PUBLISHED_OPERATING_BOUND", "SRC-TE-SPEC55-22", uncertainty_reason="BOUND_NOT_RANDOM_ESTIMATE"),
                    "strand_count": "19",
                    "conductor_material": "silver-plated high-strength copper alloy",
                    "insulation": "radiation-crosslinked modified fluoropolymer",
                },
                "missing_for_project_use": ["allowable RMS/peak current for project installation", "finished-bundle OD and tolerance", "dynamic bend radius", "torsional flex life", "lot and agency-approval confirmation"],
            },
            {
                "id": "SRC-TE-SPEC55-24",
                "publisher": "TE Connectivity",
                "source_class": "OFFICIAL_MANUFACTURER_PRODUCT_PAGE",
                "url": "https://www.te.com/en/product-2770853005.html",
                "product": "55/9952-24-9(LAT3)",
                "catalog_state_at_retrieval": "ACTIVE__NOT_CURRENTLY_AVAILABLE",
                "intended_candidate_use": "low-current discrete or signal conductor pending protocol and load analysis",
                "facts": {
                    "wire_size_awg": "24",
                    "conductor_area": quantity(0.2, "mm^2", "PUBLISHED_VALUE", "SRC-TE-SPEC55-24", uncertainty_reason="VENDOR_TOLERANCE_NOT_DISCLOSED"),
                    "outside_diameter": quantity(0.95, "mm", "PUBLISHED_VALUE", "SRC-TE-SPEC55-24", uncertainty_reason="VENDOR_TOLERANCE_NOT_DISCLOSED"),
                    "linear_mass": quantity(2.78, "g/m", "PUBLISHED_NOMINAL", "SRC-TE-SPEC55-24", uncertainty_reason="VENDOR_NOMINAL_TOLERANCE_NOT_DISCLOSED", derivation="2.78 kg/km is numerically 2.78 g/m"),
                    "maximum_resistance_at_20C": quantity(106.2, "ohm/1000m", "PUBLISHED_MAXIMUM", "SRC-TE-SPEC55-24", uncertainty_reason="PUBLISHED_LIMIT__TEST_AND_LOT_VARIATION_NOT_DISCLOSED"),
                    "operating_voltage": quantity(600, "V", "PUBLISHED_RATING", "SRC-TE-SPEC55-24", uncertainty_reason="RATING_NOT_RANDOM_ESTIMATE"),
                    "temperature_min": quantity(-65, "degC", "PUBLISHED_OPERATING_BOUND", "SRC-TE-SPEC55-24", uncertainty_reason="BOUND_NOT_RANDOM_ESTIMATE"),
                    "temperature_max": quantity(200, "degC", "PUBLISHED_OPERATING_BOUND", "SRC-TE-SPEC55-24", uncertainty_reason="BOUND_NOT_RANDOM_ESTIMATE"),
                    "strand_count": "19",
                    "conductor_material": "silver-plated high-strength copper alloy",
                    "insulation": "radiation-crosslinked modified fluoropolymer",
                },
                "missing_for_project_use": ["protocol suitability", "finished-bundle OD and tolerance", "dynamic bend radius", "torsional flex life", "lot and agency-approval confirmation"],
            },
            {
                "id": "SRC-GLENAIR-963-080-24",
                "publisher": "Glenair",
                "source_class": "OFFICIAL_MANUFACTURER_DATASHEET",
                "url": "https://www.glenair.com/speedline/pdf/963-080-24.pdf",
                "product": "963-080-24 100-ohm SpaceWire-type cable",
                "intended_candidate_use": "data cable only if the B601 bus protocol is confirmed compatible",
                "facts": {
                    "data_pairs": "4 shielded twisted pairs",
                    "wire_size_awg": "24",
                    "outside_diameter_max": quantity(7.24, "mm", "PUBLISHED_MAXIMUM", "SRC-GLENAIR-963-080-24", uncertainty_reason="PUBLISHED_LIMIT__DIMENSIONS_SUBJECT_TO_CHANGE"),
                    "minimum_bend_radius": quantity(31.75, "mm", "PUBLISHED_MINIMUM__STATIC_OR_DYNAMIC_CLASS_NOT_STATED", "SRC-GLENAIR-963-080-24", uncertainty_reason="BEND_CLASS_AND_TEST_CONDITION_NOT_DISCLOSED", derivation="1.25 in x 25.4 mm/in"),
                    "linear_mass": quantity(62.335958, "g/m", "DERIVED_FROM_PUBLISHED_VALUE", "SRC-GLENAIR-963-080-24", uncertainty_reason="VENDOR_MASS_TOLERANCE_NOT_DISCLOSED", derivation="19.0 g/ft divided by 0.3048 m/ft"),
                    "dielectric_withstand": quantity(600, "Vrms", "PUBLISHED_RATING", "SRC-GLENAIR-963-080-24", uncertainty_reason="RATING_NOT_RANDOM_ESTIMATE"),
                    "differential_impedance_nominal": quantity(100, "ohm", "PUBLISHED_NOMINAL", "SRC-GLENAIR-963-080-24", uncertainty_reason="PUBLISHED_TOLERANCE_IS_SEPARATE_PLUS_MINUS_6_OHM"),
                    "temperature_min": quantity(-65, "degC", "PUBLISHED_OPERATING_BOUND", "SRC-GLENAIR-963-080-24", uncertainty_reason="BOUND_NOT_RANDOM_ESTIMATE"),
                    "temperature_max": quantity(200, "degC", "PUBLISHED_OPERATING_BOUND", "SRC-GLENAIR-963-080-24", uncertainty_reason="BOUND_NOT_RANDOM_ESTIMATE"),
                    "insulation_and_jacket": "FEP",
                    "shielding": "pair aluminum/polyimide tape plus silver-plated-copper outer shield, 90% minimum coverage",
                },
                "missing_for_project_use": ["actual bus protocol", "dynamic/static bend classification", "dynamic torsion and flex life", "restoring-load curves", "termination and connector definition"],
            },
            {
                "id": "SRC-GLENAIR-963-080-26",
                "publisher": "Glenair",
                "source_class": "OFFICIAL_MANUFACTURER_DATASHEET",
                "url": "https://www.glenair.com/speedline/pdf/963-080-26.pdf",
                "product": "963-080-26 100-ohm SpaceWire-type cable",
                "intended_candidate_use": "lower-mass data cable only if the B601 bus protocol is confirmed compatible",
                "facts": {
                    "data_pairs": "4 shielded twisted pairs",
                    "wire_size_awg": "26",
                    "outside_diameter_max": quantity(6.05, "mm", "PUBLISHED_MAXIMUM", "SRC-GLENAIR-963-080-26", uncertainty_reason="PUBLISHED_LIMIT__DIMENSIONS_SUBJECT_TO_CHANGE"),
                    "minimum_bend_radius": quantity(28.575, "mm", "PUBLISHED_MINIMUM__STATIC_OR_DYNAMIC_CLASS_NOT_STATED", "SRC-GLENAIR-963-080-26", uncertainty_reason="BEND_CLASS_AND_TEST_CONDITION_NOT_DISCLOSED", derivation="1.125 in x 25.4 mm/in"),
                    "linear_mass": quantity(51.83727, "g/m", "DERIVED_FROM_PUBLISHED_VALUE", "SRC-GLENAIR-963-080-26", uncertainty_reason="VENDOR_MASS_TOLERANCE_NOT_DISCLOSED", derivation="15.8 g/ft divided by 0.3048 m/ft"),
                    "dielectric_withstand": quantity(600, "Vrms", "PUBLISHED_RATING", "SRC-GLENAIR-963-080-26", uncertainty_reason="RATING_NOT_RANDOM_ESTIMATE"),
                    "differential_impedance_nominal": quantity(100, "ohm", "PUBLISHED_NOMINAL", "SRC-GLENAIR-963-080-26", uncertainty_reason="PUBLISHED_TOLERANCE_IS_SEPARATE_PLUS_MINUS_6_OHM"),
                    "temperature_min": quantity(-65, "degC", "PUBLISHED_OPERATING_BOUND", "SRC-GLENAIR-963-080-26", uncertainty_reason="BOUND_NOT_RANDOM_ESTIMATE"),
                    "temperature_max": quantity(200, "degC", "PUBLISHED_OPERATING_BOUND", "SRC-GLENAIR-963-080-26", uncertainty_reason="BOUND_NOT_RANDOM_ESTIMATE"),
                    "insulation_and_jacket": "FEP",
                    "shielding": "pair aluminum/polyimide tape plus silver-plated-copper outer shield, 90% minimum coverage",
                },
                "missing_for_project_use": ["actual bus protocol", "dynamic/static bend classification", "dynamic torsion and flex life", "restoring-load curves", "termination and connector definition"],
            },
            {
                "id": "SRC-GORE-SPACEWIRE",
                "publisher": "W. L. Gore & Associates",
                "source_class": "OFFICIAL_MANUFACTURER_PRODUCT_PAGE",
                "url": "https://www.gore.com/products/spacewire",
                "product": "GORE Space Cables, Type SpaceWire",
                "intended_candidate_use": "space-qualified data candidate only if SpaceWire/LVDS is the selected B601 protocol",
                "facts": {
                    "ordering_numbers": {"28_awg": "ESCC390200301B", "26_awg": "ESCC390200302B"},
                    "signal_speed_max": quantity(400, "Mbit/s", "PUBLISHED_MAXIMUM", "SRC-GORE-SPACEWIRE", uncertainty_reason="PUBLISHED_LIMIT__SYSTEM_MARGIN_NOT_EVALUATED"),
                    "operating_voltage_max": quantity(200, "Vrms", "PUBLISHED_MAXIMUM", "SRC-GORE-SPACEWIRE", uncertainty_reason="RATING_NOT_RANDOM_ESTIMATE"),
                    "temperature_min": quantity(-200, "degC", "PUBLISHED_OPERATING_BOUND", "SRC-GORE-SPACEWIRE", uncertainty_reason="BOUND_NOT_RANDOM_ESTIMATE"),
                    "temperature_max": quantity(180, "degC", "PUBLISHED_OPERATING_BOUND", "SRC-GORE-SPACEWIRE", uncertainty_reason="BOUND_NOT_RANDOM_ESTIMATE"),
                    "radiation_resistance_min": quantity(10, "Mrad", "PUBLISHED_MINIMUM", "SRC-GORE-SPACEWIRE", uncertainty_reason="PUBLISHED_LIMIT__TEST_DETAIL_REQUIRES_DATASHEET_CONFIRMATION"),
                    "vcm_max": quantity(0.1, "%", "PUBLISHED_STRICT_UPPER_LIMIT", "SRC-GORE-SPACEWIRE", uncertainty_reason="PUBLISHED_LIMIT_NOT_RANDOM_ESTIMATE"),
                    "tml_max": quantity(1.0, "%", "PUBLISHED_STRICT_UPPER_LIMIT", "SRC-GORE-SPACEWIRE", uncertainty_reason="PUBLISHED_LIMIT_NOT_RANDOM_ESTIMATE"),
                    "jacket": "PFA",
                    "insulation": "expanded PTFE",
                    "vendor_listed_qualifications": ["ESA ESCC 3902/003", "ECSS-Q-ST-60-13C Annex G Class 1", "NASA EEE-INST-002 Level 1"],
                },
                "missing_for_project_use": ["bundle OD", "linear mass", "bend radius", "dynamic torsion and flex life", "exact connector/termination", "protocol confirmation"],
            },
            {
                "id": "SRC-OMNETICS-POWER-MICROD",
                "publisher": "Omnetics Connector Corp.",
                "source_class": "OFFICIAL_MANUFACTURER_PRODUCT_PAGE",
                "url": "https://www.omnetics.com/product/power-micro-d/",
                "product": "Power Micro-D family, LMDP/LMDS",
                "intended_candidate_use": "power/discrete connector family pending exact current, pin and shell definition",
                "facts": {
                    "available_contact_counts": ["9", "15", "21", "25", "31", "37", "51"],
                    "current_rating_per_contact": quantity(3, "A", "PUBLISHED_RATING", "SRC-OMNETICS-POWER-MICROD", uncertainty_reason="RATING_NOT_RANDOM_ESTIMATE__DERATING_NOT_APPLIED"),
                    "contact_resistance_max_at_2p5A": quantity(26, "mohm", "PUBLISHED_MAXIMUM", "SRC-OMNETICS-POWER-MICROD", uncertainty_reason="PUBLISHED_LIMIT__INSTALLATION_VARIATION_NOT_DISCLOSED"),
                    "mating_cycles_min": quantity(2000, "cycles", "PUBLISHED_MINIMUM", "SRC-OMNETICS-POWER-MICROD", uncertainty_reason="PUBLISHED_LIMIT__NOT_HARNESS_FLEX_LIFE"),
                    "temperature_min": quantity(-55, "degC", "PUBLISHED_OPERATING_BOUND", "SRC-OMNETICS-POWER-MICROD", uncertainty_reason="BOUND_NOT_RANDOM_ESTIMATE"),
                    "temperature_max_standard": quantity(125, "degC", "PUBLISHED_OPERATING_BOUND", "SRC-OMNETICS-POWER-MICROD", uncertainty_reason="BOUND_NOT_RANDOM_ESTIMATE"),
                    "tml_max": quantity(1.0, "%", "PUBLISHED_MAXIMUM", "SRC-OMNETICS-POWER-MICROD", uncertainty_reason="PUBLISHED_LIMIT_NOT_RANDOM_ESTIMATE"),
                    "cvcm_max": quantity(0.03, "%", "PUBLISHED_MAXIMUM", "SRC-OMNETICS-POWER-MICROD", uncertainty_reason="PUBLISHED_LIMIT_NOT_RANDOM_ESTIMATE"),
                },
                "missing_for_project_use": ["exact part number", "pin map", "project derating", "backshell and strain relief", "mass and envelope", "mating interface coordinates"],
            },
            {
                "id": "SRC-OMNETICS-NANOD-FF",
                "publisher": "Omnetics Connector Corp.",
                "source_class": "OFFICIAL_MANUFACTURER_PRODUCT_PAGE",
                "url": "https://www.omnetics.com/product/nano-d-bi-lobe-connectors-dual-row-flex-mount-ff/",
                "product": "Nano-D/Bi-Lobe dual-row flex-mount family, MNPO/MNSO",
                "intended_candidate_use": "low-current signal connector family pending exact protocol, pin and shell definition",
                "facts": {
                    "available_contact_count_range": "9 through 65 positions",
                    "current_rating_per_contact": quantity(1, "A", "PUBLISHED_RATING", "SRC-OMNETICS-NANOD-FF", uncertainty_reason="RATING_NOT_RANDOM_ESTIMATE__DERATING_NOT_APPLIED"),
                    "mating_cycles_min": quantity(200, "cycles", "PUBLISHED_MINIMUM_FOR_THIS_PAGE_VARIANT", "SRC-OMNETICS-NANOD-FF", uncertainty_reason="PUBLISHED_LIMIT__NOT_HARNESS_FLEX_LIFE"),
                    "temperature_min": quantity(-55, "degC", "PUBLISHED_OPERATING_BOUND", "SRC-OMNETICS-NANOD-FF", uncertainty_reason="BOUND_NOT_RANDOM_ESTIMATE"),
                    "temperature_max_standard": quantity(125, "degC", "PUBLISHED_OPERATING_BOUND", "SRC-OMNETICS-NANOD-FF", uncertainty_reason="BOUND_NOT_RANDOM_ESTIMATE"),
                    "tml_max": quantity(1.0, "%", "PUBLISHED_MAXIMUM", "SRC-OMNETICS-NANOD-FF", uncertainty_reason="PUBLISHED_LIMIT_NOT_RANDOM_ESTIMATE"),
                    "vcm_max": quantity(0.1, "%", "PUBLISHED_MAXIMUM", "SRC-OMNETICS-NANOD-FF", uncertainty_reason="PUBLISHED_LIMIT_NOT_RANDOM_ESTIMATE"),
                },
                "missing_for_project_use": ["exact part number", "pin map", "project derating", "backshell and strain relief", "mass and envelope", "mating interface coordinates"],
            },
            {
                "id": "SRC-GORE-GFX617-EXCLUSION",
                "publisher": "W. L. Gore & Associates",
                "source_class": "OFFICIAL_MANUFACTURER_PRODUCT_PAGE",
                "url": "https://kr.gore.com/node/6851",
                "product": "GORE IDC GFX617 high-flex ribbon cable",
                "intended_candidate_use": "ground test-rig flex analog only; excluded from flight candidate set",
                "facts": {
                    "application_scope": "industrial linear motion, inspection and pick-and-place",
                    "minimum_flex_life_28awg": quantity(100000000, "cycles", "PUBLISHED_MINIMUM_AT_0P75_IN_RADIUS", "SRC-GORE-GFX617-EXCLUSION", uncertainty_reason="PUBLISHED_LIMIT__INDUSTRIAL_TEST_CONDITION_ONLY"),
                    "minimum_flex_life_26awg": quantity(50000000, "cycles", "PUBLISHED_MINIMUM_AT_0P75_IN_RADIUS", "SRC-GORE-GFX617-EXCLUSION", uncertainty_reason="PUBLISHED_LIMIT__INDUSTRIAL_TEST_CONDITION_ONLY"),
                },
                "exclusion_reason": "Industrial product/application evidence is not flight selection or six-axis space-dress-pack qualification authority.",
            },
        ],
        "explicit_non_findings": [
            "No reviewed public source establishes B601 six-joint combined bending/torsion flex life.",
            "No reviewed public source establishes the installed Route-C finished-bundle OD, mass, stiffness, or restoring torque.",
            "No connector family page establishes the B601 exact pinout, shell, backshell, mass, or mating datum.",
        ],
    }

    run = next(item for item in routing["runs"] if item["run_id"] == "H-RUN-01_ARM_POWER_AND_DATA")
    nodes = {item["node"]: item for item in run["topology_nodes"]}
    input_register = {
        "schema": "ROUTE_C_MINIMUM_PRODUCT_INTERFACE_INPUT_REGISTER_V1",
        "generated_local": GENERATED_LOCAL,
        "authority": "CURRENT_INPUT_MATURITY_AUDIT__NO_SELECTION_OR_RELEASE",
        "route_c_stage": "C1_INPUT_FREEZE_PREPARATION",
        "rc_ceg_03_state": "HOLD",
        "next_stage_authorized": False,
        "known_system_function": run["function"],
        "local_source_bindings": {
            "route_c_contract": {"path": rel(CONTRACT), "sha256": sha256(CONTRACT)},
            "odr42_request": {"path": rel(ODR42), "sha256": sha256(ODR42), "owner_decision": odr["owner_decision"]},
            "harness_routing": {"path": rel(HARNESS_ROUTING), "sha256": sha256(HARNESS_ROUTING)},
            "accepted_urdf": {"path": rel(URDF), "sha256": sha256(URDF)},
            "solar_r2": {"path": rel(SOLAR_R2), "sha256": sha256(SOLAR_R2)},
        },
        "c2_start_minimum_criteria": [
            {"id": "MPI-01", "input": "motor, brake and gripper voltage/current/load map", "state": "HOLD_UNKNOWN", "candidate_evidence": "none", "controlled_exit": "approved per-function nominal, RMS, peak, duration, simultaneity and derating values with units and owners"},
            {"id": "MPI-02", "input": "data protocol, rate, impedance and EMC/separation needs", "state": "HOLD_UNKNOWN", "candidate_evidence": "SpaceWire products reviewed conditionally; B601 protocol is not identified", "controlled_exit": "approved protocol and signal-integrity/EMC requirements"},
            {"id": "MPI-03", "input": "conductor count, gauge, redundancy, shield and bond map", "state": "HOLD_CANDIDATE_COMPONENTS_ONLY", "candidate_evidence": "TE Spec 55 22/24 AWG individual-wire candidates; no project conductor map", "controlled_exit": "frozen circuit/pin/conductor/shield/bond map with current and voltage-drop analysis"},
            {"id": "MPI-04", "input": "exact connector, backshell, strain relief and pinout", "state": "HOLD_FAMILY_CANDIDATES_ONLY", "candidate_evidence": "Omnetics Power Micro-D and Nano-D family pages; exact part numbers absent", "controlled_exit": "exact mating pair, shell, keying, contacts, backshell, pinout, mass, envelope and derating"},
            {"id": "MPI-05", "input": "installed finished-bundle OD and tolerance", "state": "HOLD_UNKNOWN", "candidate_evidence": "single-wire and protocol-cable diameters are not an assembled dress-pack OD", "controlled_exit": "supplier-controlled or measured installed OD/tolerance for each routed sub-bundle"},
            {"id": "MPI-06", "input": "applicable static and dynamic bend/torsion limit versus temperature", "state": "HOLD_UNKNOWN_DYNAMIC_CLASS", "candidate_evidence": "Glenair publishes minimum bend radii but does not state static/dynamic class in the reviewed sheet", "controlled_exit": "selected-construction static/dynamic bend and torsion limits with temperature and installation conditions"},
            {"id": "MPI-07", "input": "controlled installation interfaces and datums", "state": "HOLD_PARTIAL_TOPOLOGY_ONLY", "candidate_evidence": "HN-01 declared; HN-02 y/z absent; HN-03 connector face unsupported; bus origin absent; passage not a physical void", "controlled_exit": "controlled HN-00..HN-03 locations/orientations, connector face, passage/guide/clamp datums and fastener interfaces"},
            {"id": "MPI-08", "input": "mission life target and acceptance factor", "state": "HOLD_UNKNOWN", "candidate_evidence": "connector mating-cycle data is not harness flex life", "controlled_exit": "mission cycles by segment/joint plus qualification/acceptance factors and combined bend-torsion test spectrum"},
        ],
        "interface_station_audit": [
            {"node": "HN-00", "location": nodes["HN-00"].get("at"), "coordinates_S_mm": nodes["HN-00"].get("coordinates_S_mm"), "state": nodes["HN-00"].get("status"), "design_use": "FORBIDDEN_UNTIL_CONTROLLED"},
            {"node": "HN-01", "location": nodes["HN-01"].get("at"), "coordinates_S_mm": nodes["HN-01"].get("coordinates_S_mm"), "state": nodes["HN-01"].get("status"), "design_use": "TOPOLOGY_REFERENCE_ONLY__PASSAGE_IS_NOT_A_PHYSICAL_VOID"},
            {"node": "HN-02", "location": nodes["HN-02"].get("at"), "coordinates_S_mm": nodes["HN-02"].get("coordinates_S_mm"), "state": nodes["HN-02"].get("status"), "design_use": "FORBIDDEN_UNTIL_Y_Z_AND_CLAMP_INTERFACE_CONTROLLED"},
            {"node": "HN-03", "location": nodes["HN-03"].get("at"), "coordinates_S_mm": nodes["HN-03"].get("coordinates_S_mm"), "state": nodes["HN-03"].get("status"), "design_use": "FORBIDDEN_AS_CONNECTOR_DATUM_UNTIL_GEOMETRICALLY_RECONCILED"},
        ],
        "downstream_inputs_not_required_for_initial_C2_but_required_before_release": [
            "installed linear and component mass with uncertainty and provenance",
            "bending/torsional restoring-load curves versus angle, rate and temperature",
            "guide/clamp/liner/fastener materials and processes",
            "abrasion, particulate, outgassing and thermal-vacuum evidence",
            "installation inspection and post-install electrical test procedure",
            "eight released mission trajectories and coupled SAFE results",
        ],
        "catalog_candidate_progress": {
            "official_vendor_sources_reviewed": len(sources["sources"]),
            "component_families_project_selected": 0,
            "exact_connector_part_numbers_selected": 0,
            "minimum_c2_inputs_controlled": 0,
            "minimum_c2_inputs_total": 8,
        },
        "route_b_seed_policy": "REJECTED_ROUTE_B_DIMENSIONS_AND_MASS_ARE_NOT_PRIORS_AND_ARE_NOT_INHERITED",
        "release_rule": "RC-CEG-03 remains HOLD until all MPI-01..MPI-08 are CONTROLLED by named owners; catalog candidates never close the gate by themselves.",
    }

    trade_rows = [
        {
            "candidate_id": "RCA-01",
            "architecture": "MONOLITHIC_SPEC55_LOOM",
            "power_path": "TE Spec 55 individual wires pending load map",
            "data_path": "same loom pending protocol and EMC review",
            "connector_path": "exact connector unknown",
            "dynamic_flex_evidence": "NONE",
            "project_mass_od_authority": "NONE",
            "status": "REFERENCE_BASELINE_NOT_SELECTED",
            "disposition": "retain only as wiring baseline; packaging, EMC and flex uncertainties remain coupled",
        },
        {
            "candidate_id": "RCA-02",
            "architecture": "SPLIT_POWER_AND_PROTOCOL_DATA_GUIDED_PACK",
            "power_path": "TE Spec 55 22/24 AWG candidates pending load/voltage-drop map",
            "data_path": "Gore/Glenair SpaceWire candidates only if protocol is SpaceWire/LVDS",
            "connector_path": "Power Micro-D plus low-current signal family candidates pending exact part/pinout",
            "dynamic_flex_evidence": "NONE_FOR_B601_SIX_JOINT_DUTY",
            "project_mass_od_authority": "NONE",
            "status": "PREFERRED_INVESTIGATION_NOT_SELECTED",
            "disposition": "preferred engineering trade because power/data mechanics and EMC can be controlled separately; cannot enter CAD until MPI-01..08 close",
        },
        {
            "candidate_id": "RCA-03",
            "architecture": "CUSTOM_VENDOR_TERMINATED_HIGH_FLEX_SPACE_DRESS_PACK",
            "power_path": "custom selected after current/load map",
            "data_path": "custom protocol-specific construction",
            "connector_path": "vendor-terminated exact mating set",
            "dynamic_flex_evidence": "PROJECT_SPECIFIC_TEST_REQUIRED",
            "project_mass_od_authority": "SUPPLIER_DRAWING_AND_FIRST_ARTICLE_REQUIRED",
            "status": "PREFERRED_PROCUREMENT_PATH_PENDING_RFQ_NOT_SELECTED",
            "disposition": "request combined bend/torsion/restoring-load/life characterization on the installed construction",
        },
        {
            "candidate_id": "RCA-04",
            "architecture": "INDUSTRIAL_HIGH_FLEX_ANALOG",
            "power_path": "not flight candidate",
            "data_path": "Gore GFX617 or equivalent only for ground-rig method development",
            "connector_path": "test fixture only",
            "dynamic_flex_evidence": "INDUSTRIAL_LINEAR_FLEX_ONLY",
            "project_mass_od_authority": "NONE",
            "status": "EXCLUDED_FROM_FLIGHT_CANDIDATE__TEST_RIG_ONLY",
            "disposition": "may de-risk the test fixture and instrumentation; cannot support flight selection or qualification",
        },
    ]

    data_request = {
        "schema": "ROUTE_C_ELECTRICAL_INTERFACE_DATA_REQUEST_V1",
        "generated_local": GENERATED_LOCAL,
        "record_type": "ENGINEERING_DATA_REQUEST__NOT_OWNER_AUTHORIZATION",
        "objective": "Close MPI-01..MPI-08 without turning catalog candidates or Route-B seeds into project authority.",
        "requests": [
            {"request_id": "RID-01", "owner_role": "B601_ELECTRICAL_OWNER", "required_for": "C2_ENTRY", "deliverable": "per-joint motor plus brake and gripper circuit load table", "required_fields": ["function", "bus_voltage_V", "nominal_current_A", "rms_current_A", "peak_current_A", "peak_duration_s", "simultaneity_case", "allowable_voltage_drop_V", "derating_rule", "source_and_revision"]},
            {"request_id": "RID-02", "owner_role": "B601_AVIONICS_OR_SUPPLIER_INTERFACE_OWNER", "required_for": "C2_ENTRY", "deliverable": "data and discrete interface control table", "required_fields": ["protocol", "data_rate_bit_per_s", "topology", "impedance_ohm_if_applicable", "pair_count", "shield_and_bond", "redundancy", "EMC_separation", "source_and_revision"]},
            {"request_id": "RID-03", "owner_role": "HARNESS_ELECTRICAL_OWNER", "required_for": "C2_ENTRY", "deliverable": "controlled circuit-to-conductor-and-pin map", "required_fields": ["circuit_id", "from_pin", "to_pin", "wire_or_cable_part_number", "gauge_or_construction", "contact_part_number", "shield_termination", "spare_policy", "current_and_voltage_drop_check"]},
            {"request_id": "RID-04", "owner_role": "HARNESS_MECHANICAL_OWNER", "required_for": "C2_ENTRY", "deliverable": "installed-construction mechanical input sheet", "required_fields": ["subbundle_id", "finished_OD_mm", "OD_tolerance_mm", "minimum_static_bend_radius_mm", "minimum_dynamic_bend_radius_mm", "torsion_limit_deg_per_m", "temperature_range_degC", "linear_mass_g_per_m", "uncertainty_or_bounded_distribution", "supplier_drawing_or_measurement"]},
            {"request_id": "RID-05", "owner_role": "MECHANICAL_INTERFACE_OWNER", "required_for": "C2_ENTRY", "deliverable": "HN-00 through HN-03 and J1-J6 installation ICD", "required_fields": ["frame", "xyz_mm", "orientation", "datum_scheme", "connector_face", "passage_or_guide_geometry", "clamp_fastener_interface", "installation_access", "tolerance"]},
            {"request_id": "RID-06", "owner_role": "SYSTEMS_AND_QUALIFICATION_OWNER", "required_for": "C2_ENTRY", "deliverable": "mission-life and qualification-factor allocation", "required_fields": ["segment_id", "joint_motion_cycles", "angle_range_rad", "rate_rad_per_s", "temperature_case", "vacuum_case", "qualification_factor", "acceptance_factor", "combined_bend_torsion_spectrum"]},
            {"request_id": "RID-07", "owner_role": "HARNESS_SUPPLIER_OR_TEST_OWNER", "required_for": "C5_C6_RELEASE", "deliverable": "installed-bundle restoring-load and flex-life evidence", "required_fields": ["article_configuration", "bend_radius_mm", "torsion_deg_per_m", "angle_rad", "rate_rad_per_s", "temperature_degC", "torque_Nm", "force_N", "cycles", "failure_criterion", "uncertainty", "raw_data_hash"]},
        ],
        "submission_rule": "Null, TBD, typical-without-source, or unqualified family-level values remain UNKNOWN. SI-compatible units, source revision, owner and uncertainty/bounds are mandatory.",
    }

    criteria = input_register["c2_start_minimum_criteria"]
    gate = {
        "schema": "ROUTE_C_PRODUCT_INPUT_GATE_V1",
        "generated_local": GENERATED_LOCAL,
        "gate": "HOLD",
        "verdict": "ROUTE_C_MINIMUM_PRODUCT_AND_INTERFACE_INPUTS_NOT_CONTROLLED",
        "rc_ceg_03": "HOLD",
        "next_stage_authorized": False,
        "criteria_total": len(criteria),
        "criteria_controlled": sum(item["state"] == "CONTROLLED" for item in criteria),
        "criteria": criteria,
        "candidate_library": {
            "state": "PASS_RESEARCH_INTEGRITY_ONLY",
            "official_sources_reviewed": len(sources["sources"]),
            "flight_candidates_selected": 0,
            "note": "This PASS means the candidate library is traceable; it is not a product, CAD, or release PASS.",
        },
        "detailed_design_start_effect": "RC-CEG-03_REMAINS_BLOCKING",
        "owner_authorization_effect": "ODR-42_REMAINS_SEPARATE_AND_PENDING",
        "allowed_now": ["supplier data request", "electrical/interface definition", "candidate trade refinement", "test-method planning"],
        "prohibited_now": ["Route-C CAD/STEP generation", "product selection claim", "harness mass or OD release", "dynamic flex-life claim", "restoring-torque claim", "production/contact/RL/hardware authority"],
        "immutable_asset_hashes": {
            "accepted_urdf": sha256(URDF),
            "solar_r2": sha256(SOLAR_R2),
        },
    }

    source_path = OUT / "ROUTE_C_PRODUCT_SOURCE_REGISTER_V1.json"
    register_path = OUT / "ROUTE_C_MINIMUM_PRODUCT_INTERFACE_INPUT_REGISTER_V1.json"
    trade_path = OUT / "ROUTE_C_CABLE_CONNECTOR_CANDIDATE_TRADE_V1.csv"
    request_path = OUT / "ROUTE_C_ELECTRICAL_INTERFACE_DATA_REQUEST_V1.yaml"
    gate_path = OUT / "ROUTE_C_PRODUCT_INPUT_GATE_V1.json"
    write_json(source_path, sources)
    write_json(register_path, input_register)
    with trade_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(trade_rows[0]))
        writer.writeheader()
        writer.writerows(trade_rows)
    request_path.write_text(yaml.safe_dump(data_request, sort_keys=False, allow_unicode=True), encoding="utf-8")
    write_json(gate_path, gate)

    result = {
        "verdict": gate["verdict"],
        "criteria_controlled": f"{gate['criteria_controlled']}/{gate['criteria_total']}",
        "official_sources_reviewed": len(sources["sources"]),
        "artifacts": [rel(path) for path in (source_path, register_path, trade_path, request_path, gate_path)],
        "accepted_urdf_sha256": sha256(URDF),
        "solar_r2_sha256": sha256(SOLAR_R2),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
