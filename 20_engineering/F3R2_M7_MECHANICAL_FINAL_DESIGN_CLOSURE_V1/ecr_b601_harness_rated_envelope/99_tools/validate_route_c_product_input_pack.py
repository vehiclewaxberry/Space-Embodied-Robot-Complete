from __future__ import annotations

import copy
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

SOURCE = OUT / "ROUTE_C_PRODUCT_SOURCE_REGISTER_V1.json"
REGISTER = OUT / "ROUTE_C_MINIMUM_PRODUCT_INTERFACE_INPUT_REGISTER_V1.json"
TRADE = OUT / "ROUTE_C_CABLE_CONNECTOR_CANDIDATE_TRADE_V1.csv"
REQUEST = OUT / "ROUTE_C_ELECTRICAL_INTERFACE_DATA_REQUEST_V1.yaml"
GATE = OUT / "ROUTE_C_PRODUCT_INPUT_GATE_V1.json"
MANIFEST = OUT / "ROUTE_C_PRODUCT_INPUT_OUTPUT_MANIFEST_V1.json"
REPORT = OUT / "ROUTE_C_PRODUCT_INPUT_VALIDATION_V1.json"
BUILDER = SCRIPT.parent / "build_route_c_product_input_pack.py"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def rel(path: Path) -> str:
    return path.resolve().relative_to(WORKSPACE.resolve()).as_posix()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def quantities(value, path="root"):
    found = []
    if isinstance(value, dict):
        if isinstance(value.get("value"), (int, float)) and "unit" in value:
            found.append((path, value))
        for key, child in value.items():
            found.extend(quantities(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(quantities(child, f"{path}[{index}]"))
    return found


checks = []


def check(check_id, condition, evidence):
    checks.append({"id": check_id, "pass": bool(condition), "evidence": evidence})


for path in (SOURCE, REGISTER, TRADE, REQUEST, GATE, BUILDER):
    check(f"FILE_{path.stem}_EXISTS", path.is_file() and path.stat().st_size > 0, rel(path))

sources = load_json(SOURCE)
register = load_json(REGISTER)
gate = load_json(GATE)
request = yaml.safe_load(REQUEST.read_text(encoding="utf-8"))
with TRADE.open("r", encoding="utf-8", newline="") as stream:
    trade = list(csv.DictReader(stream))

source_by_id = {item["id"]: item for item in sources["sources"]}
check("SOURCE_SCHEMA", sources.get("schema") == "ROUTE_C_PRODUCT_SOURCE_REGISTER_V1", sources.get("schema"))
check("SOURCE_COUNT", len(source_by_id) == 8, sorted(source_by_id))
check("SOURCE_OFFICIAL_ONLY", all(item["source_class"].startswith("OFFICIAL_MANUFACTURER") for item in source_by_id.values()), sorted({item["source_class"] for item in source_by_id.values()}))
check("SOURCE_NO_PROJECT_SELECTION", sources["source_policy"].get("project_selection_authority") is False, sources["source_policy"])
check("DYNAMIC_FLEX_FAIL_CLOSED", "do not prove" in sources["source_policy"]["dynamic_flex_policy"], sources["source_policy"]["dynamic_flex_policy"])

expected = {
    "SRC-TE-SPEC55-22": {"outside_diameter": 1.1, "linear_mass": 4.27, "maximum_resistance_at_20C": 54.3},
    "SRC-TE-SPEC55-24": {"outside_diameter": 0.95, "linear_mass": 2.78, "maximum_resistance_at_20C": 106.2},
    "SRC-GLENAIR-963-080-24": {"outside_diameter_max": 7.24, "minimum_bend_radius": 31.75, "linear_mass": 62.335958},
    "SRC-GLENAIR-963-080-26": {"outside_diameter_max": 6.05, "minimum_bend_radius": 28.575, "linear_mass": 51.83727},
}
exact_ok = True
exact_evidence = {}
for source_id, fields in expected.items():
    facts = source_by_id[source_id]["facts"]
    exact_evidence[source_id] = {field: facts[field]["value"] for field in fields}
    exact_ok &= all(abs(float(facts[field]["value"]) - wanted) < 1e-9 for field, wanted in fields.items())
check("CABLE_NUMERIC_FACTS_EXACT", exact_ok, exact_evidence)
check("TE_AVAILABILITY_RISK_RETAINED", all(source_by_id[sid]["catalog_state_at_retrieval"] == "ACTIVE__NOT_CURRENTLY_AVAILABLE" for sid in ("SRC-TE-SPEC55-22", "SRC-TE-SPEC55-24")), [source_by_id[sid]["catalog_state_at_retrieval"] for sid in ("SRC-TE-SPEC55-22", "SRC-TE-SPEC55-24")])
check("SPACEWIRE_PROTOCOL_CONDITIONAL", all("only if" in source_by_id[sid]["intended_candidate_use"] for sid in ("SRC-GLENAIR-963-080-24", "SRC-GLENAIR-963-080-26", "SRC-GORE-SPACEWIRE")), [source_by_id[sid]["intended_candidate_use"] for sid in ("SRC-GLENAIR-963-080-24", "SRC-GLENAIR-963-080-26", "SRC-GORE-SPACEWIRE")])
check("GORE_SPACEWIRE_MISSING_MECHANICAL_DATA_EXPLICIT", set(("bundle OD", "linear mass", "bend radius", "dynamic torsion and flex life")).issubset(source_by_id["SRC-GORE-SPACEWIRE"]["missing_for_project_use"]), source_by_id["SRC-GORE-SPACEWIRE"]["missing_for_project_use"])
check("CONNECTOR_FAMILY_NOT_EXACT_PART", all("exact part number" in source_by_id[sid]["missing_for_project_use"] for sid in ("SRC-OMNETICS-POWER-MICROD", "SRC-OMNETICS-NANOD-FF")), "both connector families retain exact-PN gap")
check("MATING_CYCLES_NOT_FLEX_LIFE", all("NOT_HARNESS_FLEX_LIFE" in source_by_id[sid]["facts"]["mating_cycles_min"]["uncertainty"]["reason"] for sid in ("SRC-OMNETICS-POWER-MICROD", "SRC-OMNETICS-NANOD-FF")), "connector durability semantics retained")
check("INDUSTRIAL_ANALOG_EXCLUDED", "excluded from flight" in source_by_id["SRC-GORE-GFX617-EXCLUSION"]["intended_candidate_use"], source_by_id["SRC-GORE-GFX617-EXCLUSION"]["intended_candidate_use"])

numeric_quantities = quantities(sources)
uncertainty_ok = all(
    item.get("unit")
    and isinstance(item.get("uncertainty"), dict)
    and item["uncertainty"].get("standard_uncertainty") is None
    and item["uncertainty"].get("distribution") is None
    and item["uncertainty"].get("reason")
    and item.get("project_design_authority") is False
    for _, item in numeric_quantities
)
check("ALL_NUMERIC_PRODUCT_FACTS_HAVE_UNITS_UNCERTAINTY_PROVENANCE", uncertainty_ok and len(numeric_quantities) >= 40, {"quantity_count": len(numeric_quantities), "bad": [path for path, item in numeric_quantities if not (item.get("unit") and isinstance(item.get("uncertainty"), dict) and item["uncertainty"].get("reason") and item.get("project_design_authority") is False)]})
check("NO_SILENT_ZERO_UNCERTAINTY", all(item["uncertainty"].get("standard_uncertainty") != 0 for _, item in numeric_quantities), "no standard_uncertainty=0")
check("QUANTITY_SOURCE_IDS_VALID", all(item.get("provenance", {}).get("source_id") in source_by_id for _, item in numeric_quantities), sorted({item.get("provenance", {}).get("source_id") for _, item in numeric_quantities}))

check("REGISTER_SCHEMA", register.get("schema") == "ROUTE_C_MINIMUM_PRODUCT_INTERFACE_INPUT_REGISTER_V1", register.get("schema"))
criteria = register.get("c2_start_minimum_criteria", [])
check("EIGHT_MINIMUM_INPUTS", len(criteria) == 8 and [item["id"] for item in criteria] == [f"MPI-{i:02d}" for i in range(1, 9)], [item.get("id") for item in criteria])
check("ZERO_CONTROLLED_INPUTS", sum(item.get("state") == "CONTROLLED" for item in criteria) == 0, [item.get("state") for item in criteria])
check("REGISTER_FAIL_CLOSED", register.get("rc_ceg_03_state") == "HOLD" and register.get("next_stage_authorized") is False, {"rc_ceg_03": register.get("rc_ceg_03_state"), "next": register.get("next_stage_authorized")})
check("CATALOG_PROGRESS_NOT_SELECTION", register["catalog_candidate_progress"] == {"official_vendor_sources_reviewed": 8, "component_families_project_selected": 0, "exact_connector_part_numbers_selected": 0, "minimum_c2_inputs_controlled": 0, "minimum_c2_inputs_total": 8}, register["catalog_candidate_progress"])
check("FOUR_INTERFACE_NODES", [item["node"] for item in register["interface_station_audit"]] == ["HN-00", "HN-01", "HN-02", "HN-03"], [item["node"] for item in register["interface_station_audit"]])
check("INTERFACE_STATIONS_NOT_OVERCLAIMED", all("FORBIDDEN" in item["design_use"] or "REFERENCE_ONLY" in item["design_use"] for item in register["interface_station_audit"]), [item["design_use"] for item in register["interface_station_audit"]])
check("ROUTE_B_SEEDS_QUARANTINED", register.get("route_b_seed_policy") == "REJECTED_ROUTE_B_DIMENSIONS_AND_MASS_ARE_NOT_PRIORS_AND_ARE_NOT_INHERITED", register.get("route_b_seed_policy"))

bindings_ok = True
binding_evidence = []
for item in register["local_source_bindings"].values():
    path = WORKSPACE / item["path"]
    ok = path.is_file() and sha256(path) == item["sha256"]
    bindings_ok &= ok
    binding_evidence.append({"path": item["path"], "match": ok})
check("LOCAL_SOURCE_HASH_BINDINGS", bindings_ok, binding_evidence)
check("IMMUTABLE_HASHES_STILL_PINNED", register["local_source_bindings"]["accepted_urdf"]["sha256"] == "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164" and register["local_source_bindings"]["solar_r2"]["sha256"] == "21FF77B882DBFAB87B3E77DD56817EFC7F321C68E30AFEDCDDBB4D79B9915795", {"urdf": register["local_source_bindings"]["accepted_urdf"]["sha256"], "solar": register["local_source_bindings"]["solar_r2"]["sha256"]})
check("ODR42_STILL_PENDING", register["local_source_bindings"]["odr42_request"].get("owner_decision") == "PENDING", register["local_source_bindings"]["odr42_request"].get("owner_decision"))

check("TRADE_FOUR_ARCHITECTURES", len(trade) == 4, len(trade))
check("TRADE_NO_SELECTION", all("NOT_SELECTED" in row["status"] or "EXCLUDED" in row["status"] for row in trade), [row["status"] for row in trade])
check("SPLIT_PACK_PREFERRED_ONLY", next(row for row in trade if row["candidate_id"] == "RCA-02")["status"] == "PREFERRED_INVESTIGATION_NOT_SELECTED", next(row for row in trade if row["candidate_id"] == "RCA-02")["status"])
check("CUSTOM_PACK_PENDING_RFQ", next(row for row in trade if row["candidate_id"] == "RCA-03")["status"] == "PREFERRED_PROCUREMENT_PATH_PENDING_RFQ_NOT_SELECTED", next(row for row in trade if row["candidate_id"] == "RCA-03")["status"])
check("INDUSTRIAL_TRADE_EXCLUDED", next(row for row in trade if row["candidate_id"] == "RCA-04")["status"] == "EXCLUDED_FROM_FLIGHT_CANDIDATE__TEST_RIG_ONLY", next(row for row in trade if row["candidate_id"] == "RCA-04")["status"])

check("REQUEST_SCHEMA", request.get("schema") == "ROUTE_C_ELECTRICAL_INTERFACE_DATA_REQUEST_V1", request.get("schema"))
check("REQUEST_COUNT_AND_OWNERS", len(request.get("requests", [])) == 7 and all(item.get("owner_role") for item in request["requests"]), [(item.get("request_id"), item.get("owner_role")) for item in request.get("requests", [])])
check("REQUEST_UNITS_AND_UNCERTAINTY_REQUIRED", "units" in request["submission_rule"] and "uncertainty" in request["submission_rule"], request["submission_rule"])

check("GATE_SCHEMA", gate.get("schema") == "ROUTE_C_PRODUCT_INPUT_GATE_V1", gate.get("schema"))
check("GATE_HOLD", gate.get("gate") == "HOLD" and gate.get("rc_ceg_03") == "HOLD" and gate.get("next_stage_authorized") is False, {"gate": gate.get("gate"), "rc_ceg_03": gate.get("rc_ceg_03"), "next": gate.get("next_stage_authorized")})
check("GATE_COUNTS", gate.get("criteria_total") == 8 and gate.get("criteria_controlled") == 0, {"total": gate.get("criteria_total"), "controlled": gate.get("criteria_controlled")})
check("RESEARCH_PASS_SEMANTIC_LIMITED", gate["candidate_library"]["state"] == "PASS_RESEARCH_INTEGRITY_ONLY" and gate["candidate_library"]["flight_candidates_selected"] == 0, gate["candidate_library"])
check("CAD_PROHIBITED", "Route-C CAD/STEP generation" in gate["prohibited_now"], gate["prohibited_now"])
check("GATE_IMMUTABLE_HASHES_MATCH", gate["immutable_asset_hashes"]["accepted_urdf"] == sha256(WORKSPACE / register["local_source_bindings"]["accepted_urdf"]["path"]) and gate["immutable_asset_hashes"]["solar_r2"] == sha256(WORKSPACE / register["local_source_bindings"]["solar_r2"]["path"]), gate["immutable_asset_hashes"])

geometry_suffixes = {".step", ".stp", ".stl", ".glb", ".3mf", ".fcstd", ".sldprt", ".sldasm"}
geometry = [rel(path) for path in OUT.rglob("*") if path.is_file() and path.suffix.lower() in geometry_suffixes]
check("NO_GEOMETRY_CREATED", not geometry, geometry)

def fail_closed(candidate_gate):
    return bool(
        candidate_gate.get("gate") == "HOLD"
        and candidate_gate.get("rc_ceg_03") == "HOLD"
        and candidate_gate.get("next_stage_authorized") is False
        and candidate_gate.get("criteria_controlled") == 0
        and all(item.get("state") != "CONTROLLED" for item in candidate_gate.get("criteria", []))
    )


negative_controls = []
mutant = copy.deepcopy(gate)
mutant["next_stage_authorized"] = True
negative_controls.append({"id": "NC-01", "mutation": "force next_stage_authorized=true", "detected": not fail_closed(mutant)})
mutant = copy.deepcopy(gate)
mutant["criteria"][0]["state"] = "CONTROLLED"
negative_controls.append({"id": "NC-02", "mutation": "claim one controlled input while count remains zero", "detected": not fail_closed(mutant)})
mutant_sources = copy.deepcopy(sources)
first_quantity = quantities(mutant_sources)[0][1]
first_quantity["uncertainty"]["standard_uncertainty"] = 0
negative_controls.append({"id": "NC-03", "mutation": "replace missing uncertainty with silent zero", "detected": not all(item["uncertainty"].get("standard_uncertainty") != 0 for _, item in quantities(mutant_sources))})
mutant_trade = copy.deepcopy(trade)
mutant_trade[1]["status"] = "SELECTED"
negative_controls.append({"id": "NC-04", "mutation": "promote candidate architecture to selected", "detected": not all("NOT_SELECTED" in row["status"] or "EXCLUDED" in row["status"] for row in mutant_trade)})
check("NEGATIVE_CONTROLS_ALL_DETECTED", all(item["detected"] for item in negative_controls), negative_controls)

primary = [SOURCE, REGISTER, TRADE, REQUEST, GATE]
local_sources = [WORKSPACE / item["path"] for item in register["local_source_bindings"].values()]
manifest = {
    "schema": "ROUTE_C_PRODUCT_INPUT_OUTPUT_MANIFEST_V1",
    "generated_local": gate["generated_local"],
    "scope": "candidate product/interface research and fail-closed input maturity gate; no CAD or product selection",
    "outputs": [{"path": rel(path), "sha256": sha256(path), "bytes": path.stat().st_size} for path in primary],
    "local_source_bindings": [{"path": rel(path), "sha256": sha256(path), "bytes": path.stat().st_size} for path in local_sources],
    "generator": {"path": rel(BUILDER), "sha256": sha256(BUILDER), "bytes": BUILDER.stat().st_size},
    "validator": {"path": rel(SCRIPT), "sha256": sha256(SCRIPT), "bytes": SCRIPT.stat().st_size},
    "output_count": len(primary),
    "local_source_count": len(local_sources),
    "remote_official_source_count": len(sources["sources"]),
    "geometry_artifact_count": 0,
    "rc_ceg_03": "HOLD",
    "next_stage_authorized": False,
}
write_json(MANIFEST, manifest)
check("MANIFEST_COUNTS", manifest["output_count"] == 5 and manifest["local_source_count"] == 5 and manifest["remote_official_source_count"] == 8, {key: manifest[key] for key in ("output_count", "local_source_count", "remote_official_source_count")})
check("MANIFEST_HASH_CLOSURE", all(sha256(WORKSPACE / item["path"]) == item["sha256"] for item in manifest["outputs"] + manifest["local_source_bindings"]), "all output/source hashes match")
check("MANIFEST_GATE_HOLD", manifest["rc_ceg_03"] == "HOLD" and manifest["next_stage_authorized"] is False and manifest["geometry_artifact_count"] == 0, {"rc_ceg_03": manifest["rc_ceg_03"], "next": manifest["next_stage_authorized"], "geometry": manifest["geometry_artifact_count"]})

failed = [item["id"] for item in checks if not item["pass"]]
report = {
    "schema": "ROUTE_C_PRODUCT_INPUT_VALIDATION_V1",
    "generated_local": gate["generated_local"],
    "verdict": "PASS_CANDIDATE_DATA_PACK_INTEGRITY__RC_CEG_03_REMAINS_HOLD" if not failed else "FAIL_PRODUCT_INPUT_PACK_INTEGRITY",
    "package_integrity_pass": not failed,
    "rc_ceg_03": "HOLD",
    "next_stage_authorized": False,
    "checks_passed": len(checks) - len(failed),
    "checks_total": len(checks),
    "failed_checks": failed,
    "negative_controls_passed": sum(item["detected"] for item in negative_controls),
    "negative_controls_total": len(negative_controls),
    "negative_controls": negative_controls,
    "checks": checks,
    "manifest": {"path": rel(MANIFEST), "sha256": sha256(MANIFEST)},
    "claim_limit": "Integrity PASS validates source traceability, units, uncertainty gaps and fail-closed semantics only. It does not select a product, authorize CAD, or close RC-CEG-03.",
}
write_json(REPORT, report)
print(json.dumps({"verdict": report["verdict"], "checks": f"{report['checks_passed']}/{report['checks_total']}", "negative_controls": f"{report['negative_controls_passed']}/{report['negative_controls_total']}", "failed": failed, "manifest_sha256": sha256(MANIFEST), "validation_sha256": sha256(REPORT)}, indent=2, ensure_ascii=False))
raise SystemExit(0 if not failed else 1)
