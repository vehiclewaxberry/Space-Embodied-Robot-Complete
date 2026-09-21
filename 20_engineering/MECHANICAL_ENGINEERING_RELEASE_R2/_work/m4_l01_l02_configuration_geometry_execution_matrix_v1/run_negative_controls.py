"""Run mutation-based negative controls through the independent validator."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from frozen_execution_spec_v1 import LOCAL_MANIFEST_ROLES, NEGATIVE_CONTROL_COUNT
from validate_execution_matrix import (
    GATE_NAME,
    MANIFEST_NAME,
    evaluate_all,
    workspace_root,
)


PACKAGE = Path(__file__).resolve().parent
RECEIPT = PACKAGE / "NEGATIVE_CONTROL_RESULTS_V1.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_valid_negative_placeholder(package: Path) -> None:
    rows = [
        {"id": f"PLACEHOLDER_{index:02d}", "passed": True, "stimulus": "TEMP_VALIDATION_FIXTURE", "observed_failed_checks": ["TEMP"]}
        for index in range(1, NEGATIVE_CONTROL_COUNT + 1)
    ]
    write_json(
        package / "NEGATIVE_CONTROL_RESULTS_V1.json",
        {
            "schema": "M4_L01_L02_GEOMETRY_NEGATIVE_CONTROL_RESULTS_V1",
            "expected_count": NEGATIVE_CONTROL_COUNT,
            "executed_count": NEGATIVE_CONTROL_COUNT,
            "passed_count": NEGATIVE_CONTROL_COUNT,
            "all_passed": True,
            "results": rows,
            "cad_kernel_loaded": False,
            "step_generation_executed": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
    )


def force_valid_gate(package: Path) -> None:
    gate = read_json(package / GATE_NAME)
    gate["gate_passed"] = True
    gate["passed_count"] = gate["expected_count"]
    gate["verdict"] = "PASS_SOURCE_ONLY_MATRIX__0_OF_9_CONFIGURATION_CURRENT_STEP_BUILDABLE__D01_Q0_DIAGNOSTIC_RECIPE_READY__NO_CAD_RUN_OR_RELEASE_CREDIT"
    for row in gate["checks"]:
        row["pass"] = True
    gate["negative_control_receipt"] = {
        "present": True,
        "expected_count": NEGATIVE_CONTROL_COUNT,
        "all_passed": True,
    }
    for name in list(gate["artifact_hashes"]):
        path = package / name
        if path.is_file():
            gate["artifact_hashes"][name] = sha256(path)
    gate["artifact_hashes"]["NEGATIVE_CONTROL_RESULTS_V1.json"] = sha256(package / "NEGATIVE_CONTROL_RESULTS_V1.json")
    write_json(package / GATE_NAME, gate)


def write_valid_manifest(package: Path) -> None:
    path = package / MANIFEST_NAME
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["path", "bytes", "sha256", "role", "exists"], lineterminator="\n")
        writer.writeheader()
        for relative, role in sorted(LOCAL_MANIFEST_ROLES.items()):
            local = package / relative
            writer.writerow(
                {
                    "path": relative,
                    "bytes": local.stat().st_size,
                    "sha256": sha256(local),
                    "role": role,
                    "exists": "true",
                }
            )


def prepare_valid_fixture(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc"),
    )
    write_valid_negative_placeholder(destination)
    force_valid_gate(destination)
    write_valid_manifest(destination)
    baseline = evaluate_all(destination, workspace_root(PACKAGE), verify_external_sources=False)
    failures = [row for row in baseline if not row["pass"]]
    if failures:
        raise RuntimeError(f"NEGATIVE_FIXTURE_BASELINE_INVALID:{failures}")


def mutate_json(package: Path, filename: str, callback) -> None:
    path = package / filename
    value = read_json(path)
    callback(value)
    write_json(path, value)


def refresh_manifest_unless_target(package: Path, manifest_is_stimulus: bool) -> None:
    if not manifest_is_stimulus:
        write_valid_manifest(package)


def run_case(case: dict, root: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="m4_geom_nc_") as temp:
        fixture = Path(temp) / "package"
        prepare_valid_fixture(PACKAGE, fixture)
        case["mutate"](fixture)
        refresh_manifest_unless_target(fixture, case.get("manifest_stimulus", False))
        checks = evaluate_all(fixture, root, verify_external_sources=False)
        failed_ids = [row["id"] for row in checks if not row["pass"]]
        passed = any(expected in failed_ids for expected in case["expected"])
        return {
            "id": case["id"],
            "stimulus": case["stimulus"],
            "expected_failed_checks": case["expected"],
            "observed_failed_checks": failed_ids,
            "passed": passed,
        }


def cases() -> list[dict]:
    def json_case(case_id, stimulus, filename, callback, expected):
        return {
            "id": case_id,
            "stimulus": stimulus,
            "expected": expected,
            "mutate": lambda package, f=filename, cb=callback: mutate_json(package, f, cb),
        }

    rows = [
        json_case("NC01", "PROMOTE_C01_CURRENT_STEP_BUILDABLE", "CONFIGURATION_GEOMETRY_EXECUTION_MATRIX_V1.yaml", lambda v: v["configurations"][0].__setitem__("configuration_current_step_buildable_now", True), ["V12_CONFIG_ROWS_EXACT", "V13_ZERO_CURRENT_STEP_BUILDABLE"]),
        json_case("NC02", "DROP_C09", "CONFIGURATION_GEOMETRY_EXECUTION_MATRIX_V1.yaml", lambda v: v["configurations"].pop(), ["V10_NINE_CONFIGS", "V11_CONFIG_IDS_EXACT"]),
        json_case("NC03", "DUPLICATE_CONFIGURATION_ID", "CONFIGURATION_GEOMETRY_EXECUTION_MATRIX_V1.yaml", lambda v: v["configurations"][8].__setitem__("configuration_id", "C08"), ["V11_CONFIG_IDS_EXACT"]),
        json_case("NC04", "REPLACE_C01_QHOME_WITH_Q0", "CONFIGURATION_GEOMETRY_EXECUTION_MATRIX_V1.yaml", lambda v: v["configurations"][0].__setitem__("authoritative_q6_rad", [0.0] * 6), ["V12_CONFIG_ROWS_EXACT", "V18_C01_QHOME_EXACT"]),
        json_case("NC05", "PROMOTE_D01_TO_CONFIGURATION_CURRENT", "SOURCE_ONLY_GEOMETRY_GENERATION_CONTRACT_V1.yaml", lambda v: v.__setitem__("configuration_current", True), ["V17_D01_CONTRACT_EXACT"]),
        json_case("NC06", "GRANT_D01_CONFIGURATION_CREDIT", "SOURCE_ONLY_GEOMETRY_GENERATION_CONTRACT_V1.yaml", lambda v: v.__setitem__("configuration_credit", True), ["V17_D01_CONTRACT_EXACT", "V40_ALL_BOUNDARIES_FALSE"]),
        json_case("NC07", "PROMOTE_C05_CANDIDATE_Q", "CONFIGURATION_GEOMETRY_EXECUTION_MATRIX_V1.yaml", lambda v: v["configurations"][4].__setitem__("authoritative_q6_rad", v["configurations"][4]["non_authoritative_q6_rad"]), ["V12_CONFIG_ROWS_EXACT", "V20_C05_C09_AUTH_Q_NULL"]),
        json_case("NC08", "FILL_C08_TARGET_ATTACHMENT_WITH_IDENTITY", "CONFIGURATION_GEOMETRY_EXECUTION_MATRIX_V1.yaml", lambda v: v["configurations"][7].__setitem__("target_attachment_transform_S_rows", [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]), ["V12_CONFIG_ROWS_EXACT", "V21_TARGET_ATTACHMENTS_NULL"]),
        json_case("NC09", "FILL_C09_TARGET_ATTACHMENT_WITH_IDENTITY", "CONFIGURATION_GEOMETRY_EXECUTION_MATRIX_V1.yaml", lambda v: v["configurations"][8].__setitem__("target_attachment_transform_S_rows", [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]), ["V12_CONFIG_ROWS_EXACT", "V21_TARGET_ATTACHMENTS_NULL"]),
        json_case("NC10", "FILL_ARM_HDRM_WITH_EMPTY_OBJECT", "SOURCE_ONLY_GEOMETRY_GENERATION_CONTRACT_V1.yaml", lambda v: v["placements"].__setitem__("ARM_HDRM", {}), ["V17_D01_CONTRACT_EXACT", "V27_NULL_PLACEMENTS_STRUCTURED"]),
        json_case("NC11", "FILL_SOLAR_HDRM_WITH_EMPTY_OBJECT", "SOURCE_ONLY_GEOMETRY_GENERATION_CONTRACT_V1.yaml", lambda v: v["placements"].__setitem__("SOLAR_HDRM_HARDWARE", {}), ["V17_D01_CONTRACT_EXACT", "V27_NULL_PLACEMENTS_STRUCTURED"]),
        json_case("NC12", "GRANT_COLLISION_AUTHORITY", "SOURCE_ONLY_GEOMETRY_GENERATION_CONTRACT_V1.yaml", lambda v: v.__setitem__("collision_authority", True), ["V17_D01_CONTRACT_EXACT", "V40_ALL_BOUNDARIES_FALSE"]),
        json_case("NC13", "GRANT_CONTACT_AUTHORITY", "SOURCE_ONLY_GEOMETRY_GENERATION_CONTRACT_V1.yaml", lambda v: v.__setitem__("contact_authority", True), ["V17_D01_CONTRACT_EXACT", "V40_ALL_BOUNDARIES_FALSE"]),
        json_case("NC14", "GRANT_MASS_AUTHORITY", "SOURCE_ONLY_GEOMETRY_GENERATION_CONTRACT_V1.yaml", lambda v: v.__setitem__("mass_authority", True), ["V17_D01_CONTRACT_EXACT", "V40_ALL_BOUNDARIES_FALSE"]),
        json_case("NC15", "GRANT_PRODUCTION_AUTHORITY", "SOURCE_ONLY_GEOMETRY_GENERATION_CONTRACT_V1.yaml", lambda v: v.__setitem__("production_authority", True), ["V17_D01_CONTRACT_EXACT", "V40_ALL_BOUNDARIES_FALSE"]),
        json_case("NC16", "GRANT_RELEASE_CREDIT", "SOURCE_ONLY_GEOMETRY_GENERATION_CONTRACT_V1.yaml", lambda v: v.__setitem__("release_credit", True), ["V17_D01_CONTRACT_EXACT", "V40_ALL_BOUNDARIES_FALSE"]),
        json_case("NC17", "CLAIM_FRESH_RUN_AUTHORITY", "SOURCE_ONLY_PREFLIGHT_V1.json", lambda v: v.__setitem__("fresh_run_authority_observed", True), ["V38_NO_RUN_OR_MEMORY_AUTHORITY"]),
        json_case("NC18", "CLAIM_MEMORY_GATE_PASS", "SOURCE_ONLY_PREFLIGHT_V1.json", lambda v: v.__setitem__("memory_gate_passed", True), ["V38_NO_RUN_OR_MEMORY_AUTHORITY"]),
        json_case("NC19", "CLAIM_CAD_KERNEL_LOADED", "SOURCE_ONLY_PREFLIGHT_V1.json", lambda v: v.__setitem__("cad_kernel_loaded", True), ["V37_NO_CAD_OR_STEP_EXECUTION"]),
        json_case("NC20", "CLAIM_STEP_EXECUTED", "SOURCE_ONLY_PREFLIGHT_V1.json", lambda v: v.__setitem__("step_generation_executed", True), ["V37_NO_CAD_OR_STEP_EXECUTION"]),
        json_case("NC21", "CHANGE_D01_SOLID_COUNT", "SOURCE_ONLY_GEOMETRY_GENERATION_CONTRACT_V1.yaml", lambda v: v["expected"].__setitem__("leaf_solid_count", 402), ["V17_D01_CONTRACT_EXACT", "V30_COUNTS_EXACT_403_3"]),
        json_case("NC22", "CHANGE_D01_GROUP_COUNT", "SOURCE_ONLY_GEOMETRY_GENERATION_CONTRACT_V1.yaml", lambda v: v["expected"].__setitem__("intermediate_group_count", 2), ["V17_D01_CONTRACT_EXACT", "V30_COUNTS_EXACT_403_3"]),
        json_case("NC23", "DRIFT_D01_BBOX", "SOURCE_ONLY_GEOMETRY_GENERATION_CONTRACT_V1.yaml", lambda v: v["expected"]["bbox_S_mm"]["max"].__setitem__(1, 715.5), ["V17_D01_CONTRACT_EXACT", "V31_BBOX_EXACT"]),
        json_case("NC24", "DRIFT_B601_PLACEMENT", "SOURCE_ONLY_GEOMETRY_GENERATION_CONTRACT_V1.yaml", lambda v: v["placements"]["B601_FIXED_Q0_LOCAL_TO_S_ROWS_MM"][0].__setitem__(3, 208.1), ["V17_D01_CONTRACT_EXACT", "V26_B601_MATRIX_EXACT"]),
        json_case("NC25", "INCLUDE_LEGACY_SOLAR_IN_MASTER_SELECTION", "SOURCE_ONLY_GEOMETRY_GENERATION_CONTRACT_V1.yaml", lambda v: v["master_retained"][8].__setitem__("index", 7), ["V17_D01_CONTRACT_EXACT", "V28_SELECTIONS_EXACT"]),
        json_case("NC26", "PROMOTE_SOLAR_HDRM_KEEPOUT_AS_SELECTED", "SOURCE_ONLY_GEOMETRY_GENERATION_CONTRACT_V1.yaml", lambda v: v["solar_selected"][5].__setitem__("index", 19), ["V17_D01_CONTRACT_EXACT", "V28_SELECTIONS_EXACT"]),
        json_case("NC27", "TAMPER_SOURCE_SHA", "SOURCE_AUTHORITY_LOCK_V1.json", lambda v: v["sources"][0].__setitem__("sha256", "0" * 64), ["V05_SOURCE_ROWS_EXACT"]),
        json_case("NC28", "DUPLICATE_SOURCE_ID", "SOURCE_AUTHORITY_LOCK_V1.json", lambda v: v["sources"][1].__setitem__("id", v["sources"][0]["id"]), ["V03_SOURCE_IDS_UNIQUE", "V05_SOURCE_ROWS_EXACT"]),
        json_case("NC29", "DUPLICATE_SOURCE_PATH", "SOURCE_AUTHORITY_LOCK_V1.json", lambda v: v["sources"][1].__setitem__("path", v["sources"][0]["path"]), ["V04_SOURCE_PATHS_UNIQUE", "V05_SOURCE_ROWS_EXACT"]),
    ]

    def top_level_cad_import(package: Path) -> None:
        path = package / "source_only_step_generator_v1.py"
        path.write_text("import OCP\n" + path.read_text(encoding="utf-8"), encoding="utf-8")

    rows.append({"id": "NC30", "stimulus": "ADD_TOP_LEVEL_CAD_IMPORT", "expected": ["V42_GENERATOR_NO_TOP_LEVEL_CAD_IMPORT"], "mutate": top_level_cad_import})
    rows.append(json_case("NC31", "CLAIM_SNAPSHOT_EXECUTED", "SNAPSHOT_TASK_PLAN_V1.json", lambda v: (v["tasks"][0].__setitem__("executed", True), v["tasks"][0].__setitem__("artifact", "fake.png")), ["V34_SNAPSHOT_PLAN_EXACT", "V35_SNAPSHOTS_UNEXECUTED"]))

    def duplicate_key(package: Path) -> None:
        path = package / "SOURCE_ONLY_PREFLIGHT_V1.json"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace('{\n', '{\n  "schema": "DUPLICATE",\n', 1), encoding="utf-8")

    rows.append({"id": "NC32", "stimulus": "INJECT_DUPLICATE_JSON_KEY", "expected": ["V00_CORE_PARSE"], "mutate": duplicate_key})

    def inject_nan(package: Path) -> None:
        path = package / "SOURCE_ONLY_PREFLIGHT_V1.json"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace('"memory_gate_gib": 6.0', '"memory_gate_gib": NaN'), encoding="utf-8")

    rows.append({"id": "NC33", "stimulus": "INJECT_NAN", "expected": ["V00_CORE_PARSE"], "mutate": inject_nan})

    def manifest_role(package: Path) -> None:
        path = package / MANIFEST_NAME
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace(",human_readme,true", ",wrong_role,true", 1), encoding="utf-8")

    rows.append({"id": "NC34", "stimulus": "MUTATE_MANIFEST_ROLE", "expected": ["M04_MANIFEST_ROLES_EXACT"], "mutate": manifest_role, "manifest_stimulus": True})

    def manifest_extra(package: Path) -> None:
        (package / "UNDECLARED_EXTRA.txt").write_text("extra\n", encoding="utf-8")

    rows.append({"id": "NC35", "stimulus": "ADD_UNDECLARED_FILE", "expected": ["M06_NO_EXTRA_OR_MISSING_CONTROLLED_FILES"], "mutate": manifest_extra, "manifest_stimulus": True})

    def fake_step(package: Path) -> None:
        (package / "D01_R2_SOLAR_B601_FIXED_Q0_DIAGNOSTIC_V1.step").write_text("FAKE_STEP\n", encoding="utf-8")

    rows.append({"id": "NC36", "stimulus": "ADD_FAKE_STEP_OUTPUT", "expected": ["V39_NO_GEOMETRY_OUTPUTS", "M06_NO_EXTRA_OR_MISSING_CONTROLLED_FILES"], "mutate": fake_step, "manifest_stimulus": True})
    return rows


def main() -> int:
    rows = cases()
    if len(rows) != NEGATIVE_CONTROL_COUNT:
        raise RuntimeError(f"NEGATIVE_CONTROL_COUNT_DRIFT:{len(rows)}")
    root = workspace_root(PACKAGE)
    results = [run_case(case, root) for case in rows]
    passed_count = sum(row["passed"] for row in results)
    receipt = {
        "schema": "M4_L01_L02_GEOMETRY_NEGATIVE_CONTROL_RESULTS_V1",
        "expected_count": NEGATIVE_CONTROL_COUNT,
        "executed_count": len(results),
        "passed_count": passed_count,
        "all_passed": passed_count == NEGATIVE_CONTROL_COUNT,
        "results": results,
        "method": "TEMPORARY_PACKAGE_MUTATION_THROUGH_INDEPENDENT_FULL_VALIDATION_CHAIN",
        "cad_kernel_loaded": False,
        "step_generation_executed": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    write_json(RECEIPT, receipt)
    print(json.dumps({key: receipt[key] for key in ("expected_count", "executed_count", "passed_count", "all_passed")}, sort_keys=True))
    return 0 if receipt["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

