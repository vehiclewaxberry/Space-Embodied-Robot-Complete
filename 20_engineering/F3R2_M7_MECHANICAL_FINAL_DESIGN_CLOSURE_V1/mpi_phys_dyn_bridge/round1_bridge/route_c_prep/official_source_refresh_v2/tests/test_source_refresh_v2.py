from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import yaml


PACKAGE = Path(__file__).resolve().parents[1]
MODULE_PATH = PACKAGE / "src" / "validate_source_refresh_v2.py"
SPEC = importlib.util.spec_from_file_location("validate_source_refresh_v2", MODULE_PATH)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def load_input() -> dict:
    with (PACKAGE / "inputs" / "ROUTE_C_OFFICIAL_SOURCE_REFRESH_V2.yaml").open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def failed_ids(payload: dict) -> set[str]:
    return {row["id"] for row in VALIDATOR.evaluate(payload) if not row["pass"]}


def test_baseline_all_20_checks_pass() -> None:
    checks = VALIDATOR.evaluate(load_input())
    assert len(checks) == 20
    assert all(row["pass"] for row in checks)


def test_product_selection_mutation_is_killed() -> None:
    payload = load_input()
    payload["candidate_sets"]["RFI_E"]["selected_candidate_id"] = "RC-E-01"
    assert "RCS2-V08" in failed_ids(payload)


def test_registry_value_promotion_mutation_is_killed() -> None:
    payload = load_input()
    row = next(item for item in payload["field_effects"] if item["id"] == "P10")
    row["registry_value"] = 0.2
    row["registry_status"] = "AVAILABLE"
    row["promotion"] = "PROMOTED"
    assert "RCS2-V10" in failed_ids(payload)


def test_route_c_cad_authorization_mutation_is_killed() -> None:
    payload = load_input()
    payload["decision"]["ROUTE_C_CAD_AUTHORIZED"] = True
    assert "RCS2-V18" in failed_ids(payload)


def test_single_material_to_pair_coefficient_mutation_is_killed() -> None:
    payload = load_input()
    payload["non_equivalence_guards"]["single_material_coefficient_to_material_pair_coefficient_permitted"] = True
    assert "RCS2-V13" in failed_ids(payload)


def test_pair_coefficient_registration_mutation_is_killed() -> None:
    payload = load_input()
    record = next(item for item in payload["official_source_records"] if item["id"] == "SRC-F-TECASINT8591-GORE-PFA-20260825")
    record["pair_coefficient_registered"] = True
    assert "RCS2-V12" in failed_ids(payload)


def test_pair_coefficient_payload_injection_is_killed() -> None:
    payload = load_input()
    record = next(item for item in payload["official_source_records"] if item["id"] == "SRC-F-TECASINT8591-GORE-PFA-20260825")
    record["fact_snapshot"]["pair_coefficient"] = 0.2
    assert "RCS2-V12" in failed_ids(payload)


def test_rfi_f_candidate_coefficient_injection_is_killed() -> None:
    payload = load_input()
    payload["candidate_sets"]["RFI_F"]["candidates"][0]["pair_coefficient"] = 0.2
    assert "RCS2-V08" in failed_ids(payload)


def test_p10_field_effect_coefficient_injection_is_killed() -> None:
    payload = load_input()
    row = next(item for item in payload["field_effects"] if item["id"] == "P10")
    row["pair_coefficient"] = 0.2
    assert "RCS2-V10" in failed_ids(payload)


def test_material_identity_mutation_is_killed() -> None:
    payload = load_input()
    record = next(item for item in payload["official_source_records"] if item["id"] == "SRC-F-TECASINT2391-AXON-XLETFE-20260825")
    record["fact_snapshot"]["cable_outer_contact_material"] = "generic ETFE"
    assert "RCS2-V12" in failed_ids(payload)


def test_strict_outgassing_comparator_mutation_is_killed() -> None:
    payload = load_input()
    record = next(item for item in payload["official_source_records"] if item["id"] == "SRC-F-TECASINT8591-GORE-PFA-20260825")
    record["fact_snapshot"]["cable_TML_percent"]["comparator"] = "LE"
    assert "RCS2-V12" in failed_ids(payload)


def test_allowable_torsion_is_not_p08_compliance() -> None:
    payload = load_input()
    row = next(item for item in payload["field_effects"] if item["id"] == "P08")
    row["registry_value"] = {"Nm_per_rad": 1.0}
    assert {"RCS2-V10", "RCS2-V15"}.issubset(failed_ids(payload))


def test_nasa_tie_spacing_is_not_p13_schedule() -> None:
    payload = load_input()
    row = next(item for item in payload["field_effects"] if item["id"] == "P13")
    row["registry_value"] = [19.1, 38.1, 50.8, 76.2]
    assert {"RCS2-V10", "RCS2-V16"}.issubset(failed_ids(payload))


def test_step_parts_download_mutation_is_killed() -> None:
    payload = load_input()
    payload["catalog_search_record"]["step_files_downloaded"] = 1
    assert "RCS2-V07" in failed_ids(payload)


def test_unauthorized_p10_numeric_level_injection_is_killed() -> None:
    payload = load_input()
    payload["planned_physical_closure"]["P10_material_pair_test"]["vacuum_pressure_Pa"] = 0.001
    assert "RCS2-V14" in failed_ids(payload)


def test_unofficial_domain_mutation_is_killed() -> None:
    payload = load_input()
    payload["official_source_records"][0]["official_urls"][0] = "https://example.com/uncontrolled.pdf"
    assert "RCS2-V05" in failed_ids(payload)


def test_upstream_pin_mutation_is_killed() -> None:
    payload = load_input()
    payload["base_pins"][0]["sha256"] = "0" * 64
    assert "RCS2-V01" in failed_ids(payload)


def test_rfi_g08_promotion_mutation_is_killed() -> None:
    payload = copy.deepcopy(load_input())
    payload["decision"]["RFI_G08_closed"] = True
    payload["decision"]["rfi_g08_source_control_state"] = "PASS"
    assert {"RCS2-V17", "RCS2-V18"}.issubset(failed_ids(payload))


def test_source_field_bidirectional_mismatch_is_killed() -> None:
    payload = load_input()
    record = next(item for item in payload["official_source_records"] if item["id"] == "SRC-STD-NASA-8739-4A-C4-20260825")
    record["affected_fields"].remove("P06")
    assert "RCS2-V19" in failed_ids(payload)


def test_te_m5_interface_mutation_is_killed() -> None:
    payload = load_input()
    record = next(item for item in payload["official_source_records"] if item["id"] == "SRC-G-TE-PDKG-20260825")
    record["fact_snapshot"]["mounting_interface"] = "ANSI number 10 or MS screw"
    assert "RCS2-V20" in failed_ids(payload)
