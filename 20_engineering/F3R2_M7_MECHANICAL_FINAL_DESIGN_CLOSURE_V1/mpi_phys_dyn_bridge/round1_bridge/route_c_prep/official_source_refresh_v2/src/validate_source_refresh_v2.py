#!/usr/bin/env python3
"""Fail-closed validation for Route-C official-source refresh V2."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = next(parent for parent in HERE.parents if (parent / "AGENTS.md").exists())
INPUT = PACKAGE / "inputs" / "ROUTE_C_OFFICIAL_SOURCE_REFRESH_V2.yaml"
RESULTS = PACKAGE / "results"
VALIDATION = RESULTS / "ROUTE_C_OFFICIAL_SOURCE_REFRESH_VALIDATION_V2.json"
GATE = RESULTS / "ROUTE_C_OFFICIAL_SOURCE_REFRESH_GATE_V2.json"
MANIFEST = RESULTS / "ROUTE_C_OFFICIAL_SOURCE_REFRESH_OUTPUT_MANIFEST_V2.json"

EXPECTED_SOURCE_IDS = [
    "SRC-E-IGUS-E2M06-20260825",
    "SRC-E-TSUBAKI-TKP13H10-STD-20260825",
    "SRC-E-TSUBAKI-PVDF-20260825",
    "SRC-E-KABELSCHLEPP-MONO0130-NEG-20260825",
    "SRC-CABLE-IGUS-CFROBOT2-20260825",
    "SRC-CABLE-GORE-HFF-VAC-20260825",
    "SRC-CABLE-AXON-FLEXFORCE-20260825",
    "SRC-F-TECASINT8591-GORE-PFA-20260825",
    "SRC-F-TECASINT2391-AXON-XLETFE-20260825",
    "SRC-G-TE-PDKG-20260825",
    "SRC-G-AMPHENOL-75P-20260825",
    "SRC-G-AMPHENOL-OMEGA-20260825",
    "SRC-STD-NASA-8739-4A-C4-20260825",
    "SRC-STD-ECSS-Q-ST-20-30C-20260825",
    "SRC-STD-NASA-6016C-C1-20260825",
    "SRC-STD-ECSS-Q-ST-70-02C-20260825",
    "SRC-STD-MSFC-SPEC-494-20260825",
]

ALLOWED_DOMAINS = {
    "www.igus.com",
    "igus.widen.net",
    "en.tt-net.tsubakimoto.co.jp",
    "tsubaki-kabelschlepp.com",
    "www.gore.com",
    "www.axon-cable.com",
    "www.ensinger-online.com",
    "www.ensingerplastics.com",
    "www.te.com",
    "www.amphenolpcd.com",
    "standards.nasa.gov",
    "ecss.nl",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def evaluate(refresh: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def check(identifier: str, name: str, value: bool) -> None:
        checks.append({"id": identifier, "name": name, "pass": bool(value)})

    pins = refresh.get("base_pins", [])
    pin_ok = len(pins) == 5
    for pin in pins:
        path = ROOT / pin["path"]
        pin_ok = pin_ok and path.is_file() and path.stat().st_size == pin["bytes"] and digest(path) == pin["sha256"]
    check("RCS2-V01", "all five immutable upstream byte/hash pins are exact", pin_ok)

    registry = load_yaml(ROOT / pins[0]["path"]) if pins else {}
    check(
        "RCS2-V02",
        "base C2-01 independently remains 13 null HOLD and 0 AVAILABLE",
        registry.get("summary", {}).get("entries_total") == 13
        and registry.get("summary", {}).get("value_non_null") == 0
        and registry.get("summary", {}).get("status_AVAILABLE") == 0
        and registry.get("summary", {}).get("status_HOLD") == 13
        and len(registry.get("registry_entries", [])) == 13
        and all(row.get("value") is None and row.get("status") == "HOLD" for row in registry.get("registry_entries", [])),
    )

    admission = load_yaml(ROOT / pins[1]["path"]) if len(pins) > 1 else {}
    tally = admission.get("current_evaluation", {}).get("tally", {})
    check(
        "RCS2-V03",
        "base admission Gate independently remains 2/8 and Route-C CAD unauthorized",
        tally.get("conditions_total") == 8
        and tally.get("pass") == 2
        and tally.get("fail") == 6
        and admission.get("current_evaluation", {}).get("ROUTE_C_CAD_AUTHORIZED") is False,
    )

    records = refresh.get("official_source_records", [])
    check("RCS2-V04", "exact expected 17 primary-source records", [row.get("id") for row in records] == EXPECTED_SOURCE_IDS)

    urls = [url for row in records for url in row.get("official_urls", [])]
    check(
        "RCS2-V05",
        "all source links are HTTPS and restricted to official manufacturer or agency domains",
        bool(urls)
        and all(urlparse(url).scheme == "https" and urlparse(url).netloc.lower() in ALLOWED_DOMAINS for url in urls),
    )

    check(
        "RCS2-V06",
        "all source records retain screening-only semantics and retrieval date",
        all(
            row.get("retrieval_date_local") == "2026-08-25"
            and row.get("candidate_status")
            not in {"SELECTED", "AVAILABLE", "FLIGHT_QUALIFIED", "PROJECT_AUTHORITY"}
            for row in records
        ),
    )

    search = refresh.get("catalog_search_record", {})
    check(
        "RCS2-V07",
        "step.parts search is a zero-match no-download record",
        search.get("catalog_part_count") == 16847
        and search.get("relevant_exact_matches") == 0
        and search.get("step_files_downloaded") == 0
        and search.get("placeholder_geometry_generated") == 0
        and all(value == 0 for value in search.get("queries", {}).values()),
    )

    candidate_sets = refresh.get("candidate_sets", {})
    rfi_f_candidates = candidate_sets.get("RFI_F", {}).get("candidates", [])
    check(
        "RCS2-V08",
        "RFI-E/F/G sets are bounded 4/2/3; RFI-F has an exact no-coefficient schema; none is selected",
        len(candidate_sets.get("RFI_E", {}).get("candidates", [])) == 4
        and len(rfi_f_candidates) == 2
        and len(candidate_sets.get("RFI_G", {}).get("candidates", [])) == 3
        and all(set(row) == {"id", "source_ids", "material_pair", "status"} for row in rfi_f_candidates)
        and [row.get("id") for row in rfi_f_candidates] == ["RC-F-01", "RC-F-02"]
        and all(candidate_sets[name].get("selected_candidate_id") is None for name in ("RFI_E", "RFI_F", "RFI_G")),
    )

    effects = refresh.get("field_effects", [])
    effect_keys = {
        "id",
        "quantity",
        "registry_value",
        "registry_status",
        "screening_source_ids",
        "promotion",
        "remaining_closure",
    }
    check("RCS2-V09", "field effects enumerate P01 through P13 exactly once", [row.get("id") for row in effects] == [f"P{i:02d}" for i in range(1, 14)])
    check(
        "RCS2-V10",
        "all P-fields use an exact schema and remain null HOLD with no promotion",
        len(effects) == 13
        and all(
            set(row) == effect_keys
            and row.get("registry_value") is None
            and row.get("registry_status") == "HOLD"
            and row.get("promotion") == "NONE"
            for row in effects
        ),
    )
    check("RCS2-V11", "exactly eight P-fields gain screening links only", sum(bool(row.get("screening_source_ids")) for row in effects) == 8)

    pair_records = [row for row in records if row.get("id", "").startswith("SRC-F-")]
    pair_record_keys = {
        "id",
        "publisher",
        "source_class",
        "retrieval_date_local",
        "affected_fields",
        "official_urls",
        "document_locator",
        "fact_snapshot",
        "candidate_status",
        "pair_coefficient_registered",
        "exclusions",
    }
    expected_pair_facts = {
        "SRC-F-TECASINT8591-GORE-PFA-20260825": {
            "liner_material": "TECASINT 8591 grey modified PTFE",
            "liner_catalog_coefficient_of_friction_range": [0.14, 0.22],
            "liner_catalog_wear_rate_range_mm3_per_Nm": [1.0e-6, 1.0e-5],
            "liner_long_term_temperature_degC": 260.0,
            "liner_outgassing_statement": "passed ECSS-Q-70-02",
            "cable_outer_contact_material": "PFA jacket",
            "cable_temperature_range_degC": [-200.0, 180.0],
            "cable_TML_percent": {"comparator": "LT", "value": 1.0},
            "cable_VCM_percent": {"comparator": "LT", "value": 0.1},
        },
        "SRC-F-TECASINT2391-AXON-XLETFE-20260825": {
            "liner_material": "TECASINT 2391 black polyimide with 15 percent MoS2",
            "liner_outgassing_statement": "passed ECSS-Q-70-02",
            "available_tribology_counterface": "52100 bearing steel, not cable jacket",
            "cable_family": "ESCC 3901 012 shielded jacketed wire variants 41-50",
            "cable_outer_contact_material": "extruded cross-linked ETFE",
            "cable_temperature_range_degC": [-100.0, 200.0],
            "example_variant": "variant 45 AWG22",
            "example_variant_OD_max_mm": 2.03,
            "example_variant_mass_max_g_per_m": 10.95,
        },
    }
    check(
        "RCS2-V12",
        "both material-pair identities, units and strict comparators are exact with no coefficient injection",
        len(pair_records) == 2
        and all(
            set(row) == pair_record_keys
            and row.get("pair_coefficient_registered") is False
            and row.get("fact_snapshot") == expected_pair_facts.get(row.get("id"))
            for row in pair_records
        ),
    )

    guards = refresh.get("non_equivalence_guards", {})
    check(
        "RCS2-V13",
        "all ten non-equivalence promotions are prohibited",
        len(guards) == 10 and all(value is False for value in guards.values()),
    )

    closure = refresh.get("planned_physical_closure", {})
    p10_contract = closure.get("P10_material_pair_test", {})
    p10_contract_keys = {
        "state",
        "candidate_pairs",
        "required_axes",
        "required_outputs",
        "pair_coefficient_available",
        "numeric_test_levels_authorized",
    }
    check(
        "RCS2-V14",
        "P08/P10/RFI-G closures remain draft; P10 has an exact no-numeric-level schema",
        closure.get("P08_restoring_load_test", {}).get("state", "").startswith("DRAFT_UNEXECUTED")
        and closure.get("P08_restoring_load_test", {}).get("numeric_test_levels_authorized") is False
        and set(p10_contract) == p10_contract_keys
        and p10_contract.get("state") == "DRAFT_UNEXECUTED__EXACT_COMPOUNDS_AND_BATCHES_REQUIRED"
        and p10_contract.get("candidate_pairs") == ["RC-F-01", "RC-F-02"]
        and p10_contract.get("required_axes")
        == [
            "vacuum_pressure",
            "cold_nominal_hot_temperature",
            "sliding_speed",
            "normal_load_or_contact_pressure",
            "guide_curvature",
            "harness_tension",
            "travel",
            "torsion_amplitude",
            "cycles",
            "radiation_preconditioning",
        ]
        and p10_contract.get("required_outputs")
        == [
            "static_friction",
            "breakaway_force",
            "dynamic_friction",
            "stick_slip",
            "friction_hysteresis",
            "liner_wear",
            "jacket_wear",
            "transfer_film",
            "particle_mass",
            "particle_size_count",
            "post_test_electrical_acceptance",
            "uncertainty",
            "raw_data_hash",
        ]
        and p10_contract.get("pair_coefficient_available") is False
        and p10_contract.get("numeric_test_levels_authorized") is False
        and closure.get("RFI_G_installation_closure", {}).get("state", "").startswith("DRAFT_UNEXECUTED"),
    )

    cfrobot = next((row for row in records if row.get("id") == "SRC-CABLE-IGUS-CFROBOT2-20260825"), {})
    p08 = next((row for row in effects if row.get("id") == "P08"), {})
    check(
        "RCS2-V15",
        "CFROBOT allowable torsion is not consumed as P08 compliance or torque",
        cfrobot.get("fact_snapshot", {}).get("repeated_torsion_limit_deg_per_m_at_minus15_to_plus70_degC") == 180.0
        and p08.get("registry_value") is None
        and "measured force torque" in p08.get("remaining_closure", ""),
    )

    nasa = next((row for row in records if row.get("id") == "SRC-STD-NASA-8739-4A-C4-20260825"), {})
    p13 = next((row for row in effects if row.get("id") == "P13"), {})
    check(
        "RCS2-V16",
        "NASA tie spacing is not consumed as project structural clamp spacing",
        nasa.get("fact_snapshot", {}).get("lacing_and_tie_spacing_values_mm") == [19.1, 38.1, 50.8, 76.2]
        and p13.get("registry_value") is None
        and "project station schedule" in p13.get("remaining_closure", ""),
    )

    ceiling = refresh.get("authority_ceiling", {})
    decision = refresh.get("decision", {})
    check(
        "RCS2-V17",
        "source-control ceiling and RFI-G08 remain explicit HOLD",
        ceiling.get("source_control_level") == "URL_PLUS_DOCUMENT_IDENTIFIER_REVISION_PAGE_AND_FACT_SNAPSHOT__NO_LOCAL_BYTE_ARCHIVE"
        and decision.get("rfi_g08_source_control_state") == "HOLD_URL_PLUS_DOCUMENT_ID__NO_LOCAL_BYTE_ARCHIVE"
        and decision.get("RFI_G08_closed") is False,
    )

    check(
        "RCS2-V18",
        "terminal decision remains fail-closed with zero selection, promotion or release authority",
        decision.get("official_source_records_total") == 17
        and decision.get("fields_with_screening_sources") == 8
        and decision.get("fields_promoted_to_AVAILABLE") == 0
        and decision.get("registry_value_non_null_after") == 0
        and decision.get("registry_status_AVAILABLE_after") == 0
        and decision.get("registry_status_HOLD_after") == 13
        and decision.get("exact_products_selected") == 0
        and decision.get("owner_accepted") is False
        and decision.get("RFI_G08_closed") is False
        and decision.get("ROUTE_C_CAD_AUTHORIZED") is False
        and decision.get("geometry_execution_authorized") is False
        and decision.get("dynamics_capture_entry_authorized") is False
        and decision.get("next_stage_authorized") is False
        and decision.get("release_credit") is False,
    )

    record_links = {
        (field_id, row["id"])
        for row in records
        for field_id in row.get("affected_fields", [])
    }
    effect_links = {
        (row["id"], source_id)
        for row in effects
        for source_id in row.get("screening_source_ids", [])
    }
    check(
        "RCS2-V19",
        "source affected_fields and P-field screening links are an exact bidirectional set",
        record_links == effect_links
        and all(field_id in {f"P{i:02d}" for i in range(1, 14)} for field_id, _ in record_links)
        and all(source_id in set(EXPECTED_SOURCE_IDS) for _, source_id in effect_links),
    )

    te_clamp = next((row for row in records if row.get("id") == "SRC-G-TE-PDKG-20260825"), {})
    te_facts = te_clamp.get("fact_snapshot", {})
    check(
        "RCS2-V20",
        "TE P-clamp interface retains M5 wording and published torque ceiling without project selection",
        te_facts.get("compatible_bundle_diameter_range_mm") == [3.18, 34.93]
        and te_facts.get("mounting_hole_mm") == 5.1
        and te_facts.get("mounting_hole_plus_tolerance_mm") == 0.1
        and te_facts.get("mounting_hole_minus_tolerance_mm") == 0.0
        and te_facts.get("mounting_interface") == "ANSI number 10 or M5 screw; washer recommended; final fastener and torque customer-defined"
        and te_facts.get("installation_instruction_torque_upper_limit_Nm") == 5.99
        and candidate_sets.get("RFI_G", {}).get("selected_candidate_id") is None,
    )

    return checks


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def run() -> dict[str, Any]:
    refresh = load_yaml(INPUT)
    checks = evaluate(refresh)
    passed = sum(item["pass"] for item in checks)
    failed = [item["id"] for item in checks if not item["pass"]]

    validation_payload = {
        "schema": "ROUTE_C_OFFICIAL_SOURCE_REFRESH_VALIDATION_V2",
        "generated_date_local": "2026-08-25",
        "input_path": str(INPUT.relative_to(ROOT)).replace("\\", "/"),
        "input_sha256": digest(INPUT),
        "checks": checks,
        "summary": {"passed": passed, "total": len(checks), "failed": failed},
        "verdict": "PASS_FAIL_CLOSED_SOURCE_REFRESH_V2_VALIDATION" if not failed else "FAIL_SOURCE_REFRESH_V2_VALIDATION",
        "ROUTE_C_CAD_AUTHORIZED": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    write_json(VALIDATION, validation_payload)

    gate_payload = {
        "schema": "ROUTE_C_OFFICIAL_SOURCE_REFRESH_GATE_V2",
        "generated_date_local": "2026-08-25",
        "gate_status": "PASS_ROUTE_C_OFFICIAL_SOURCE_REFRESH_V2_ONLY" if not failed else "FAIL_ROUTE_C_OFFICIAL_SOURCE_REFRESH_V2",
        "validation_path": str(VALIDATION.relative_to(ROOT)).replace("\\", "/"),
        "validation_sha256": digest(VALIDATION),
        "criteria_total": len(checks),
        "criteria_passed": passed,
        "failed_ids": failed,
        "source_records": 17,
        "candidate_sets": {"RFI_E": 4, "RFI_F": 2, "RFI_G": 3},
        "fields_promoted_to_AVAILABLE": 0,
        "registry_value_non_null": 0,
        "registry_status_AVAILABLE": 0,
        "registry_status_HOLD": 13,
        "exact_products_selected": 0,
        "RFI_G08_closed": False,
        "ROUTE_C_CAD_AUTHORIZED": False,
        "geometry_execution_authorized": False,
        "dynamics_capture_entry_authorized": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "verdict": "SOURCE_AND_RFI_REFINEMENT_ONLY__NO_PRODUCT_SELECTION__ALL_P_FIELDS_NULL_HOLD__CAD_PROHIBITION_UNCHANGED",
    }
    write_json(GATE, gate_payload)

    inventory_paths = [
        PACKAGE / "README.md",
        INPUT,
        PACKAGE / "docs" / "ROUTE_C_RFI_EFG_ENGINEERING_SCREENING_V2.md",
        Path(__file__).resolve(),
        PACKAGE / "tests" / "test_source_refresh_v2.py",
        VALIDATION,
        GATE,
    ]
    manifest_payload = {
        "schema": "ROUTE_C_OFFICIAL_SOURCE_REFRESH_OUTPUT_MANIFEST_V2",
        "generated_date_local": "2026-08-25",
        "self_reference_policy": "MANIFEST_EXCLUDES_ITSELF",
        "files": [
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": digest(path),
            }
            for path in inventory_paths
        ],
        "file_count": len(inventory_paths),
        "ROUTE_C_CAD_AUTHORIZED": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    write_json(MANIFEST, manifest_payload)

    summary = validation_payload["summary"] | {"verdict": validation_payload["verdict"]}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if failed:
        raise SystemExit(1)
    return validation_payload


if __name__ == "__main__":
    run()
