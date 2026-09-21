"""Independent integrity validation for the Route-C vendor-RFI package."""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import yaml


REPO = Path(__file__).resolve().parents[4]
BASE_REL = (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "ecr_b601_harness_rated_envelope"
)
OUT_REL = f"{BASE_REL}/08_route_c/01_minimum_product_inputs"
GENERATED_LOCAL = "2026-08-23T15:20:00+08:00"
EXPECTED_CANDIDATE_IDS = {"RFI-A", "RFI-B", "RFI-C", "RFI-D"}
EXPECTED_MANIFEST_OUTPUTS = {
    f"{OUT_REL}/ROUTE_C_VENDOR_RFI_SHORTLIST_V1.json",
    f"{OUT_REL}/ROUTE_C_VENDOR_RFI_REQUIREMENTS_V1.yaml",
    f"{OUT_REL}/ROUTE_C_VENDOR_RFI_DECISION_GATE_V1.json",
}
EXPECTED_MANIFEST_SOURCES = {
    f"{BASE_REL}/99_tools/build_route_c_vendor_rfi.py",
    f"{BASE_REL}/99_tools/validate_route_c_vendor_rfi.py",
}
EXPECTED_GATE_BINDINGS = {
    "product_input_register": f"{OUT_REL}/ROUTE_C_MINIMUM_PRODUCT_INTERFACE_INPUT_REGISTER_V1.json",
    "product_input_gate": f"{OUT_REL}/ROUTE_C_PRODUCT_INPUT_GATE_V1.json",
    "product_input_validation": f"{OUT_REL}/ROUTE_C_PRODUCT_INPUT_VALIDATION_V1.json",
    "odr42_request": f"{BASE_REL}/08_route_c/ROUTE_C_OWNER_DECISION_REQUEST_ODR42_V1.yaml",
    "accepted_urdf": "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
    "solar_r2": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.step"
    ),
}

FILES = {
    "shortlist": f"{OUT_REL}/ROUTE_C_VENDOR_RFI_SHORTLIST_V1.json",
    "requirements": f"{OUT_REL}/ROUTE_C_VENDOR_RFI_REQUIREMENTS_V1.yaml",
    "gate": f"{OUT_REL}/ROUTE_C_VENDOR_RFI_DECISION_GATE_V1.json",
    "manifest": f"{OUT_REL}/ROUTE_C_VENDOR_RFI_OUTPUT_MANIFEST_V1.json",
    "upstream_gate": f"{OUT_REL}/ROUTE_C_PRODUCT_INPUT_GATE_V1.json",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_json(relative_path: str) -> dict[str, Any]:
    return json.loads((REPO / relative_path).read_text(encoding="utf-8"))


def check_record(checks: list[dict[str, Any]], check_id: str, passed: bool, detail: str) -> None:
    checks.append({"id": check_id, "pass": bool(passed), "detail": detail})


def metric_records(shortlist: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for route in shortlist["shortlist"]:
        for product in route["products"]:
            records.extend(product["catalog_metrics"].values())
    return records


def candidate_by_id(shortlist: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    matches = [item for item in shortlist["shortlist"] if item["candidate_id"] == candidate_id]
    if len(matches) != 1:
        raise ValueError(f"expected one candidate {candidate_id}, got {len(matches)}")
    return matches[0]


def product_by_part_token(route: dict[str, Any], token: str) -> dict[str, Any]:
    matches = [item for item in route["products"] if token in item["family_or_part"]]
    if len(matches) != 1:
        raise ValueError(
            f"expected one product containing {token!r} in {route['candidate_id']}, got {len(matches)}"
        )
    return matches[0]


def gate_fail_closed(value: dict[str, Any]) -> bool:
    binding_map = {item["name"]: item["path"] for item in value["input_bindings"]}
    return (
        value["gate"] == "HOLD"
        and value["rc_ceg_03"] == "HOLD"
        and value["odr42"] == "PENDING"
        and value["next_stage_authorized"] is False
        and value["minimum_inputs"] == {"controlled": 0, "total": 8, "rc_ceg_03": "HOLD"}
        and value["candidate_routes"]["selected_routes"] == 0
        and value["criteria_confirmed"] == value["criteria_total"] == len(value["criteria"])
        and value["criteria_confirmed"] == sum(bool(item["observed"]) for item in value["criteria"])
        and all(item["release_credit"] is False for item in value["criteria"])
        and len(binding_map) == len(value["input_bindings"])
        and binding_map == EXPECTED_GATE_BINDINGS
    )


def manifest_safe(value: dict[str, Any]) -> bool:
    output_paths = [item["path"] for item in value["outputs"]]
    source_paths = [item["path"] for item in value["sources"]]
    return (
        len(output_paths) == len(set(output_paths)) == value["output_count"] == 3
        and len(source_paths) == len(set(source_paths)) == value["source_count"] == 2
        and set(output_paths) == EXPECTED_MANIFEST_OUTPUTS
        and set(source_paths) == EXPECTED_MANIFEST_SOURCES
        and value["validation_report_excluded_to_avoid_recursive_hash"] is True
    )


def fail_closed(candidate: dict[str, Any]) -> bool:
    routes = candidate["shortlist"]
    route_a = candidate_by_id(candidate, "RFI-A")
    route_b = candidate_by_id(candidate, "RFI-B")
    route_d = candidate_by_id(candidate, "RFI-D")
    gswm = product_by_part_token(route_a, "GSWM")
    extra_flex = product_by_part_token(route_d, "RE2633")
    metrics = metric_records(candidate)
    required_unknowns = [
        gswm["catalog_metrics"]["component_mass"],
        extra_flex["catalog_metrics"]["quantified_dynamic_life"],
    ]
    source_controls = candidate["source_controls"]
    return (
        candidate["selection_state"] == "NO_PRODUCT_SELECTED"
        and {item["candidate_id"] for item in routes} == EXPECTED_CANDIDATE_IDS
        and len(routes) == len(EXPECTED_CANDIDATE_IDS)
        and candidate["counts"]["selected_routes"] == 0
        and all(route["selection_state"] != "SELECTED" for route in routes)
        and route_d["flight_shortlist"] is False
        and all(isinstance(item.get("unit"), str) and item["unit"] for item in metrics)
        and all(isinstance(item.get("source"), str) and item["source"] for item in metrics)
        and all("uncertainty" in item and "uncertainty_state" in item for item in metrics)
        and all(
            item["uncertainty_state"]
            in {"DECLARED_BOUND_OR_TOLERANCE", "NOT_PUBLISHED_IN_REVIEWED_SOURCE__UNKNOWN"}
            for item in metrics
        )
        and all(
            item["value"] is None
            and item["uncertainty"] is None
            and item["uncertainty_state"] == "NOT_PUBLISHED_IN_REVIEWED_SOURCE__UNKNOWN"
            and item["source"].startswith("NOT_PUBLISHED")
            for item in required_unknowns
        )
        and "DYNAMIC_CLASS_NOT_STATED"
        in route_a["products"][0]["catalog_metrics"]["minimum_bend_radius"]["qualifier"]
        and route_b["products"][0]["catalog_metrics"]["minimum_fully_static_bend_radius"]["qualifier"]
        == "FULLY_STATIC_ONLY"
        and len(source_controls) == len(candidate["source_urls"]) == 9
        and set(source_controls) == set(candidate["source_urls"])
        and all(
            item["url"] == candidate["source_urls"][source_id]
            and item["controlled_supplier_document_received"] is False
            and item["local_snapshot_path"] is None
            and item["local_snapshot_sha256"] is None
            and item["supplier_controlled_revision"] is None
            and item["traceability_state"]
            == "OFFICIAL_URL_ONLY__CONTROLLED_COPY_REQUIRED_BEFORE_SELECTION"
            for source_id, item in source_controls.items()
        )
        and candidate["rc_ceg_03"] == "HOLD"
        and candidate["next_stage_authorized"] is False
    )


def main() -> None:
    shortlist = read_json(FILES["shortlist"])
    gate = read_json(FILES["gate"])
    manifest = read_json(FILES["manifest"])
    upstream = read_json(FILES["upstream_gate"])
    requirements = (REPO / FILES["requirements"]).read_text(encoding="utf-8")
    requirements_data = yaml.safe_load(requirements)
    gate_binding_map = {item["name"]: item for item in gate["input_bindings"]}
    product_validation = read_json(gate_binding_map["product_input_validation"]["path"])
    checks: list[dict[str, Any]] = []

    for name, relative_path in FILES.items():
        path = REPO / relative_path
        check_record(checks, f"FILE-{name}", path.is_file() and path.stat().st_size > 0, relative_path)

    check_record(checks, "SCHEMA-01", shortlist["schema"] == "ROUTE_C_VENDOR_RFI_SHORTLIST_V1", shortlist["schema"])
    check_record(checks, "SCHEMA-02", gate["schema"] == "ROUTE_C_VENDOR_RFI_DECISION_GATE_V1", gate["schema"])
    check_record(checks, "SCHEMA-03", manifest["schema"] == "ROUTE_C_VENDOR_RFI_OUTPUT_MANIFEST_V1", manifest["schema"])
    check_record(checks, "COUNT-01", len(shortlist["shortlist"]) == 4, str(len(shortlist["shortlist"])))
    check_record(checks, "COUNT-ID", {item["candidate_id"] for item in shortlist["shortlist"]} == EXPECTED_CANDIDATE_IDS, sorted(item["candidate_id"] for item in shortlist["shortlist"]))
    check_record(checks, "COUNT-02", shortlist["counts"]["flight_rfi_routes"] == 3, str(shortlist["counts"]))
    check_record(checks, "COUNT-03", shortlist["counts"]["engineering_model_only_routes"] == 1, str(shortlist["counts"]))
    check_record(checks, "COUNT-04", shortlist["counts"]["selected_routes"] == 0, str(shortlist["counts"]))
    check_record(checks, "SOURCE-01", len(shortlist["source_urls"]) == 9, str(len(shortlist["source_urls"])))
    check_record(checks, "SOURCE-02", set(shortlist["source_controls"]) == set(shortlist["source_urls"]), "source control IDs match official URL IDs")
    check_record(checks, "SOURCE-03", all(item["local_snapshot_sha256"] is None and item["controlled_supplier_document_received"] is False for item in shortlist["source_controls"].values()), "all official sources explicitly URL-only and non-release")
    referenced_source_ids = {
        source_id
        for route in shortlist["shortlist"]
        for product in route["products"]
        for source_id in product["source_ids"]
    }
    check_record(checks, "SOURCE-04", referenced_source_ids <= set(shortlist["source_controls"]), sorted(referenced_source_ids))
    check_record(checks, "SOURCE-05", all(item["url"] == shortlist["source_urls"][source_id] for source_id, item in shortlist["source_controls"].items()), "controlled source URLs match official URL registry")
    check_record(checks, "TIME-01", datetime.fromisoformat(shortlist["generated_local"]) >= datetime.fromisoformat(product_validation["generated_local"]) and shortlist["generated_clock_source"] == "LATEST_BOUND_PRODUCT_INPUT_VALIDATION_TIMESTAMP", {"derived": shortlist["generated_local"], "latest_input": product_validation["generated_local"]})
    priority_map = {item["candidate_id"]: item["rfi_priority"] for item in shortlist["shortlist"]}
    check_record(checks, "RANK-01", priority_map == {"RFI-A": 2, "RFI-B": 1, "RFI-C": 1, "RFI-D": 1}, str(priority_map))
    route_d = candidate_by_id(shortlist, "RFI-D")
    check_record(checks, "USE-01", route_d["selection_state"] == "ENGINEERING_MODEL_RFI_ONLY", route_d["selection_state"])
    check_record(checks, "USE-02", route_d["flight_shortlist"] is False, "RFI-D flight_shortlist=false")
    check_record(checks, "HOLD-01", fail_closed(shortlist), "shortlist fail-closed invariants")
    check_record(checks, "HOLD-02", gate_fail_closed(gate), gate["verdict"])
    check_record(checks, "HOLD-03", gate["minimum_inputs"] == {"controlled": 0, "total": 8, "rc_ceg_03": "HOLD"}, str(gate["minimum_inputs"]))
    check_record(checks, "HOLD-04", upstream["criteria_controlled"] == 0 and upstream["criteria_total"] == 8, "upstream 0/8")
    check_record(checks, "GATE-01", gate["criteria_confirmed"] == gate["criteria_total"] == 8 and gate["criteria_confirmed"] == sum(bool(item["observed"]) for item in gate["criteria"]), f'{gate["criteria_confirmed"]}/{gate["criteria_total"]}')
    check_record(checks, "GATE-02", all(item["release_credit"] is False for item in gate["criteria"]), "all release_credit=false")
    check_record(checks, "AUTH-01", gate["odr42"] == "PENDING", gate["odr42"])
    check_record(checks, "AUTH-02", "NO_CAD_OR_RELEASE_AUTHORITY" in shortlist["authority"], shortlist["authority"])
    check_record(checks, "UNIT-01", all(item.get("unit") for item in metric_records(shortlist)), f'{len(metric_records(shortlist))} metric records')
    check_record(checks, "PROV-01", all(item.get("source") for item in metric_records(shortlist)), "all metrics have source")
    null_metrics = [item for item in metric_records(shortlist) if item["value"] is None]
    route_a = candidate_by_id(shortlist, "RFI-A")
    route_d = candidate_by_id(shortlist, "RFI-D")
    required_unknowns = [
        product_by_part_token(route_a, "GSWM")["catalog_metrics"]["component_mass"],
        product_by_part_token(route_d, "RE2633")["catalog_metrics"]["quantified_dynamic_life"],
    ]
    check_record(checks, "NULL-01", all(item["value"] is None and item["source"].startswith("NOT_PUBLISHED") for item in required_unknowns), f'{len(null_metrics)} total null metrics; two required unknowns retained')
    check_record(checks, "UNC-01", all("uncertainty" in item and "uncertainty_state" in item for item in metric_records(shortlist)), "all metrics carry uncertainty value and state")
    check_record(checks, "NULL-02", all(item["value"] is None and item["uncertainty"] is None and item["uncertainty_state"] == "NOT_PUBLISHED_IN_REVIEWED_SOURCE__UNKNOWN" for item in required_unknowns), "required unknown values and uncertainty retained as null with reason")
    check_record(checks, "REQ-01", [item["request_id"] for item in requirements_data["supplier_rfi_packages"]] == [f"RFI-{index:02d}" for index in range(1, 10)], "parsed RFI-01..RFI-09")
    check_record(checks, "REQ-02", [item["request_id"] for item in requirements_data["project_owner_inputs"]] == [f"PRJ-{index:02d}" for index in range(1, 7)], "parsed PRJ-01..PRJ-06")
    check_record(checks, "REQ-03", requirements_data["submission_contract"]["units_required"] is True and requirements_data["submission_contract"]["uncertainty_or_bounded_tolerance_required"] is True, requirements_data["submission_contract"])
    check_record(checks, "REQ-04", "PRJ-01..PRJ-05" in requirements_data["acceptance_rule"]["C2_entry"] and "MPI-01..MPI-08 must all be CONTROLLED" in requirements_data["acceptance_rule"]["C2_entry"], requirements_data["acceptance_rule"]["C2_entry"])
    check_record(checks, "REQ-05", "PRJ-06" in requirements_data["acceptance_rule"]["later_release"] and "allowable and measured restoring-load" in requirements_data["acceptance_rule"]["later_release"], requirements_data["acceptance_rule"]["later_release"])
    for token in [
        "uncertainty_or_bounded_tolerance_required: true",
        "minimum_dynamic_bend_radius_mm",
        "torque_Nm",
        "TML_percent",
        "raw_data_hash",
        "no_automatic_selection",
    ]:
        check_record(checks, f"REQ-{token[:12]}", token in requirements, token)

    check_record(checks, "MANIFEST-SET", manifest_safe(manifest), {"outputs": [item["path"] for item in manifest["outputs"]], "sources": [item["path"] for item in manifest["sources"]]})
    manifest_entries = manifest["outputs"] + manifest["sources"]
    for index, item in enumerate(manifest_entries, start=1):
        path = REPO / item["path"]
        passed = (
            path.is_file()
            and path.stat().st_size == item["bytes"]
            and sha256_file(path) == item["sha256"]
        )
        check_record(checks, f"HASH-{index:02d}", passed, item["path"])

    bound_matches = 0
    for item in gate["input_bindings"]:
        path = REPO / item["path"]
        if path.is_file() and path.stat().st_size == item["bytes"] and sha256_file(path) == item["sha256"]:
            bound_matches += 1
    check_record(checks, "BIND-01", bound_matches == len(gate["input_bindings"]) == 6 and {item["name"]: item["path"] for item in gate["input_bindings"]} == EXPECTED_GATE_BINDINGS, f'{bound_matches}/{len(gate["input_bindings"])}')

    negative_controls: list[dict[str, Any]] = []
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("NC-01_SELECT_WITHOUT_INPUTS", lambda value: value["counts"].__setitem__("selected_routes", 1)),
        ("NC-02_PROMOTE_ENGINEERING_ROUTE", lambda value: candidate_by_id(value, "RFI-D").__setitem__("flight_shortlist", True)),
        ("NC-03_DROP_HOLD", lambda value: value.__setitem__("rc_ceg_03", "PASS")),
        ("NC-04_AUTHORIZE_NEXT_STAGE", lambda value: value.__setitem__("next_stage_authorized", True)),
        ("NC-05_DROP_METRIC_UNIT", lambda value: candidate_by_id(value, "RFI-A")["products"][0]["catalog_metrics"]["linear_mass_max"].__setitem__("unit", "")),
        ("NC-06_PROMOTE_STATIC_BEND", lambda value: candidate_by_id(value, "RFI-B")["products"][0]["catalog_metrics"]["minimum_fully_static_bend_radius"].__setitem__("qualifier", "DYNAMIC")),
        ("NC-07_ZERO_FILL_UNKNOWN", lambda value: candidate_by_id(value, "RFI-A")["products"][1]["catalog_metrics"]["component_mass"].__setitem__("value", 0.0)),
        ("NC-08_FAKE_SOURCE_CONTROL", lambda value: value["source_controls"]["GORE_SPACEWIRE"].__setitem__("controlled_supplier_document_received", True)),
        ("NC-09_RENAME_RFI_C", lambda value: candidate_by_id(value, "RFI-C").__setitem__("candidate_id", "RFI-X")),
        ("NC-10_SOURCE_URL_MISMATCH", lambda value: value["source_controls"]["GORE_SPACEWIRE"].__setitem__("url", "https://example.invalid/not-controlled")),
    ]
    for control_id, mutate in mutations:
        try:
            candidate = copy.deepcopy(shortlist)
            mutate(candidate)
            detected = not fail_closed(candidate)
        except (KeyError, TypeError, ValueError):
            detected = True
        negative_controls.append({"id": control_id, "pass": detected, "detail": "unsafe mutation rejected" if detected else "unsafe mutation escaped"})

    gate_mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("NC-11_GATE_RC_CEG_PASS", lambda value: value.__setitem__("rc_ceg_03", "PASS")),
        ("NC-12_GATE_CRITERIA_COUNT_TAMPER", lambda value: value.__setitem__("criteria_confirmed", 7)),
        ("NC-13_GATE_PRODUCT_SELECTED", lambda value: value["candidate_routes"].__setitem__("selected_routes", 1)),
        ("NC-14_GATE_BINDING_DUPLICATE", lambda value: value["input_bindings"].__setitem__(5, copy.deepcopy(value["input_bindings"][0]))),
    ]
    for control_id, mutate in gate_mutations:
        candidate_gate = copy.deepcopy(gate)
        mutate(candidate_gate)
        detected = not gate_fail_closed(candidate_gate)
        negative_controls.append({"id": control_id, "pass": detected, "detail": "unsafe gate mutation rejected" if detected else "unsafe gate mutation escaped"})

    candidate_manifest = copy.deepcopy(manifest)
    candidate_manifest["outputs"][0] = copy.deepcopy(candidate_manifest["outputs"][1])
    manifest_detected = not manifest_safe(candidate_manifest)
    negative_controls.append({"id": "NC-15_MANIFEST_DUPLICATE", "pass": manifest_detected, "detail": "duplicate manifest entry rejected" if manifest_detected else "duplicate manifest entry escaped"})

    checks_passed = sum(item["pass"] for item in checks)
    negative_passed = sum(item["pass"] for item in negative_controls)
    integrity_pass = checks_passed == len(checks) and negative_passed == len(negative_controls)
    report = {
        "schema": "ROUTE_C_VENDOR_RFI_VALIDATION_V1",
        "generated_local": GENERATED_LOCAL,
        "validation_scope": "PACKAGE_INTEGRITY_AND_FAIL_CLOSED_SEMANTICS_ONLY",
        "verdict": (
            "PASS_RFI_PACKAGE_INTEGRITY__NO_PRODUCT_SELECTED__RC_CEG_03_HOLD"
            if integrity_pass
            else "FAIL_RFI_PACKAGE_INTEGRITY"
        ),
        "package_integrity_pass": integrity_pass,
        "checks": checks,
        "checks_passed": checks_passed,
        "checks_total": len(checks),
        "negative_controls": negative_controls,
        "negative_controls_passed": negative_passed,
        "negative_controls_total": len(negative_controls),
        "release_credit": False,
        "rc_ceg_03": "HOLD",
        "odr42": "PENDING",
        "next_stage_authorized": False,
        "prohibition": "Validation PASS cannot select hardware, authorize Route-C CAD or release mission dynamics.",
    }
    report_rel = f"{OUT_REL}/ROUTE_C_VENDOR_RFI_VALIDATION_V1.json"
    path = REPO / report_rel
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "checks": f"{checks_passed}/{len(checks)}",
                "negative_controls": f"{negative_passed}/{len(negative_controls)}",
                "validation_sha256": sha256_file(path),
            },
            ensure_ascii=False,
        )
    )
    if not integrity_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
