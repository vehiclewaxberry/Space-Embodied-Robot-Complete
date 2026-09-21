#!/usr/bin/env python3
"""Fail-closed contract/adapter negative controls; imports no builder code."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable


PACKAGE = Path(__file__).resolve().parents[1]
ROOT = next(candidate for candidate in (PACKAGE, *PACKAGE.parents) if (candidate / "PROJECT_MAP.md").is_file())
CONTRACT = PACKAGE / "00_contract/LINK1_B6_OPERATIONAL_COLLISION_CONTRACT_V1.json"
LEDGER = PACKAGE / "00_contract/FRAME_UNIT_AND_UNCERTAINTY_LEDGER_V1.json"
LOCK = PACKAGE / "00_contract/SOURCE_AUTHORITY_LOCK_V1.json"
OUTPUT = PACKAGE / "05_results/NEGATIVE_CONTROLS_V1.json"


EXPECTED_IDS = {
    "R::RC-BRK-L1-01", "R::RC-CLP-J1-MOV", "R::RC-CLP-J2-FIX", "R::RC-CLP-L1-01",
    "R::RC-GDE-J2-MANDREL", "R::RC-GDE-J2-MANDREL-LINER",
}
EXPECTED_SAMPLES = [("accepted_lower", "-2.8"), ("q0", "0"), ("accepted_upper", "2.8")]


def reject(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate(contract: dict[str, Any], ledger: dict[str, Any], lock: dict[str, Any]) -> None:
    reject(contract.get("schema") == "ROUTE_C_LINK1_B6_OPERATIONAL_COLLISION_CONTRACT_V1", "schema")
    objects = contract.get("objects", [])
    reject(len(objects) == 6 and {row.get("object_id") for row in objects} == EXPECTED_IDS, "exact object set")
    reject(len({row.get("source_label") for row in objects}) == 6 and len({row.get("output") for row in objects}) == 6, "unique mapping")
    reject(all(row.get("parent_frame") == "link1" for row in objects), "parent")
    reject(all(row.get("output", "").endswith("_LINK1_V1.step") for row in objects), "output naming")
    req = contract.get("requirements", {})
    reject(req.get("object_placement_reapplied") is False, "placement")
    reject(req.get("source_frame") == "A0_q0" and req.get("source_unit") == "mm", "source frame/unit")
    reject(req.get("output_frame") == "link1" and req.get("output_unit") == "mm", "output frame/unit")
    reject(req.get("runtime_frame") == "link1" and req.get("runtime_unit") == "m", "runtime frame/unit")
    reject(req.get("runtime_derived_from_reopened_step_only") is True, "runtime lineage")
    reject(req.get("cad_root_count_each") == 1 and req.get("output_closed_positive_single_solid_each") is True, "STEP topology")
    status = contract.get("system_status_invariant", {})
    expected_status = {"operational_geometry_count": "1/150", "pair_queries": "0/11166", "safe_count": 0, "edge_count": 0, "stage_clearance": "0/3", "path_exists": False, "TMG4": "HOLD", "G12": "FAIL", "next_stage_authorized": False, "release_credit": False}
    reject(status == expected_status and ledger.get("system_status_invariant") == expected_status, "system invariant")
    reject(ledger.get("source_geometry", {}).get("placement_semantics") == "FreeCAD_obj.Shape_already_contains_Object.Placement", "source placement semantics")
    reject(ledger.get("step_primary", {}).get("frame") == "link1" and ledger["step_primary"].get("length_unit") == "mm", "primary frame")
    reject(ledger.get("runtime_sidecars", {}).get("scale") == 0.001 and ledger["runtime_sidecars"].get("scale_application_count") == 1, "runtime scaling")
    reject(ledger.get("as_built_uncertainty", {}).get("derate_mm") is None and ledger["as_built_uncertainty"].get("zero_fill_forbidden") is True, "as-built unknown")
    reject([(row.get("sample"), row.get("q1_rad")) for row in ledger.get("pose_samples", [])] == EXPECTED_SAMPLES, "pose samples")
    raw = ledger.get("accepted_urdf_joint1_raw", {})
    reject(raw.get("origin_xyz_raw_m") == ["-8.416E-05", "0", "0.08465"] and raw.get("axis_raw") == ["0", "0", "1"], "raw URDF")
    reject(raw.get("limit_raw_rad") == {"lower": "-2.8", "upper": "2.8"}, "joint limits")
    reject(ledger.get("mount_consumption", {}).get("canonical_decimal_places") == 12 and ledger["mount_consumption"].get("source_field") == "binding.canonical_matrix_decimal_strings", "mount spelling")
    forbidden = set(ledger.get("forbidden", []))
    reject("RECONSTRUCT_EXECUTION_MOUNT_FROM_25_DEG" in forbidden and "USE_HISTORICAL_D6_SIX_DECIMAL_MOUNT" in forbidden and "REAPPLY_FREECAD_OBJECT_PLACEMENT_AFTER_CONSUMING_OBJ_SHAPE" in forbidden, "forbidden set")
    reject(lock.get("source_pin_count") == 10 and len(lock.get("source_pins", [])) == 10, "pin count")
    reject(len({row.get("id") for row in lock["source_pins"]}) == 10, "pin ids")
    reject(all(row.get("bytes", 0) > 0 and len(row.get("sha256", "")) == 64 for row in lock["source_pins"]), "pin records")


def set_value(target: dict[str, Any], path: list[Any], value: Any) -> None:
    node: Any = target
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--write", action="store_true"); args = parser.parse_args()
    baseline = {
        "contract": json.loads(CONTRACT.read_text(encoding="utf-8")),
        "ledger": json.loads(LEDGER.read_text(encoding="utf-8")),
        "lock": json.loads(LOCK.read_text(encoding="utf-8")),
    }
    validate(**baseline)
    cases: list[tuple[str, str, Callable[[dict[str, Any]], None]]] = [
        ("NC01_CONTRACT_SCHEMA", "contract schema altered", lambda d: set_value(d, ["contract", "schema"], "BAD")),
        ("NC02_OBJECT_MISSING", "one selected object removed", lambda d: d["contract"]["objects"].pop()),
        ("NC03_OBJECT_SUBSTITUTED", "object outside exact link1 set substituted", lambda d: set_value(d, ["contract", "objects", 0, "object_id"], "R::RC-CLP-J2-MOV")),
        ("NC04_DUPLICATE_ID", "duplicate object id", lambda d: set_value(d, ["contract", "objects", 1, "object_id"], d["contract"]["objects"][0]["object_id"])),
        ("NC05_DUPLICATE_LABEL", "duplicate source label", lambda d: set_value(d, ["contract", "objects", 1, "source_label"], d["contract"]["objects"][0]["source_label"])),
        ("NC06_DUPLICATE_OUTPUT", "duplicate STEP output", lambda d: set_value(d, ["contract", "objects", 1, "output"], d["contract"]["objects"][0]["output"])),
        ("NC07_PARENT_NOT_LINK1", "parent frame altered", lambda d: set_value(d, ["contract", "objects", 0, "parent_frame"], "base_link")),
        ("NC08_OUTPUT_NOT_LINK1_NAMED", "host-local output naming removed", lambda d: set_value(d, ["contract", "objects", 0, "output"], "bad.step")),
        ("NC09_OBJECT_PLACEMENT_REAPPLIED", "FreeCAD Object.Placement reapplied", lambda d: set_value(d, ["contract", "requirements", "object_placement_reapplied"], True)),
        ("NC10_SOURCE_FRAME", "source frame altered", lambda d: set_value(d, ["contract", "requirements", "source_frame"], "S")),
        ("NC11_SOURCE_UNIT", "source unit altered", lambda d: set_value(d, ["contract", "requirements", "source_unit"], "m")),
        ("NC12_OUTPUT_FRAME", "primary STEP frame altered", lambda d: set_value(d, ["contract", "requirements", "output_frame"], "S")),
        ("NC13_OUTPUT_UNIT", "primary STEP unit altered", lambda d: set_value(d, ["contract", "requirements", "output_unit"], "m")),
        ("NC14_RUNTIME_FRAME", "runtime frame altered", lambda d: set_value(d, ["contract", "requirements", "runtime_frame"], "A0")),
        ("NC15_RUNTIME_UNIT", "runtime unit altered", lambda d: set_value(d, ["contract", "requirements", "runtime_unit"], "mm")),
        ("NC16_RUNTIME_NOT_FROM_STEP", "runtime derived from source BREP", lambda d: set_value(d, ["contract", "requirements", "runtime_derived_from_reopened_step_only"], False)),
        ("NC17_MULTIPLE_STEP_ROOTS", "STEP root count contract relaxed", lambda d: set_value(d, ["contract", "requirements", "cad_root_count_each"], 2)),
        ("NC18_OPEN_STEP_ALLOWED", "closed-positive-solid requirement relaxed", lambda d: set_value(d, ["contract", "requirements", "output_closed_positive_single_solid_each"], False)),
        ("NC19_DOUBLE_MM_TO_M", "runtime scale applied twice", lambda d: set_value(d, ["ledger", "runtime_sidecars", "scale_application_count"], 2)),
        ("NC20_BAD_RUNTIME_SCALE", "runtime scale changed", lambda d: set_value(d, ["ledger", "runtime_sidecars", "scale"], 1.0)),
        ("NC21_AS_BUILT_ZERO_FILL", "unknown as-built uncertainty zero-filled", lambda d: set_value(d, ["ledger", "as_built_uncertainty", "derate_mm"], 0.0)),
        ("NC22_LOWER_SAMPLE_CHANGED", "accepted lower sample changed", lambda d: set_value(d, ["ledger", "pose_samples", 0, "q1_rad"], "-2.79")),
        ("NC23_UPPER_SAMPLE_CHANGED", "accepted upper sample changed", lambda d: set_value(d, ["ledger", "pose_samples", 2, "q1_rad"], "2.79")),
        ("NC24_JOINT_ORIGIN_REBUILT", "raw joint1 origin spelling altered", lambda d: set_value(d, ["ledger", "accepted_urdf_joint1_raw", "origin_xyz_raw_m", 0], "-0.00008416")),
        ("NC25_JOINT_AXIS", "joint1 axis altered", lambda d: set_value(d, ["ledger", "accepted_urdf_joint1_raw", "axis_raw"], ["0", "0", "-1"])),
        ("NC26_JOINT_LIMIT", "joint1 accepted limit altered", lambda d: set_value(d, ["ledger", "accepted_urdf_joint1_raw", "limit_raw_rad", "upper"], "3.14")),
        ("NC27_MOUNT_DECIMALS", "12dp mount contract relaxed", lambda d: set_value(d, ["ledger", "mount_consumption", "canonical_decimal_places"], 6)),
        ("NC28_MOUNT_FIELD", "canonical string field bypassed", lambda d: set_value(d, ["ledger", "mount_consumption", "source_field"], "reconstructed_25deg")),
        ("NC29_MOUNT_RECONSTRUCTION_ALLOWED", "rounded 25 degree reconstruction unbanned", lambda d: d["ledger"]["forbidden"].remove("RECONSTRUCT_EXECUTION_MOUNT_FROM_25_DEG")),
        ("NC30_HISTORICAL_D6_ALLOWED", "historical D6 mount unbanned", lambda d: d["ledger"]["forbidden"].remove("USE_HISTORICAL_D6_SIX_DECIMAL_MOUNT")),
        ("NC31_PLACEMENT_REAPPLY_ALLOWED", "Object.Placement reapplication unbanned", lambda d: d["ledger"]["forbidden"].remove("REAPPLY_FREECAD_OBJECT_PLACEMENT_AFTER_CONSUMING_OBJ_SHAPE")),
        ("NC32_OPERATIONAL_COUNT_UPGRADE", "system operational count upgraded", lambda d: set_value(d, ["contract", "system_status_invariant", "operational_geometry_count"], "7/150")),
        ("NC33_PAIR_QUERY_CREDIT", "pair query credit claimed", lambda d: set_value(d, ["contract", "system_status_invariant", "pair_queries"], "6/11166")),
        ("NC34_SAFE_CREDIT", "SAFE credit claimed", lambda d: set_value(d, ["contract", "system_status_invariant", "safe_count"], 1)),
        ("NC35_EDGE_CREDIT", "edge credit claimed", lambda d: set_value(d, ["contract", "system_status_invariant", "edge_count"], 1)),
        ("NC36_STAGE_CREDIT", "stage credit claimed", lambda d: set_value(d, ["contract", "system_status_invariant", "stage_clearance"], "1/3")),
        ("NC37_PATH_CREDIT", "path claimed", lambda d: set_value(d, ["contract", "system_status_invariant", "path_exists"], True)),
        ("NC38_TMG4_UPGRADE", "TMG4 upgraded", lambda d: set_value(d, ["contract", "system_status_invariant", "TMG4"], "PASS")),
        ("NC39_G12_UPGRADE", "G12 upgraded", lambda d: set_value(d, ["contract", "system_status_invariant", "G12"], "PASS")),
        ("NC40_NEXT_STAGE", "next stage authorized", lambda d: set_value(d, ["contract", "system_status_invariant", "next_stage_authorized"], True)),
        ("NC41_RELEASE_CREDIT", "release credit claimed", lambda d: set_value(d, ["contract", "system_status_invariant", "release_credit"], True)),
        ("NC42_SOURCE_PIN_REMOVED", "source pin removed", lambda d: d["lock"]["source_pins"].pop()),
        ("NC43_SOURCE_PIN_DUPLICATE", "source pin id duplicated", lambda d: set_value(d, ["lock", "source_pins", 1, "id"], d["lock"]["source_pins"][0]["id"])),
        ("NC44_SOURCE_PIN_HASH", "source pin hash malformed", lambda d: set_value(d, ["lock", "source_pins", 0, "sha256"], "0"*63)),
    ]
    rows = []
    for case_id, reason, mutate in cases:
        documents = copy.deepcopy(baseline); mutate(documents)
        rejected, error = False, None
        try:
            validate(**documents)
        except Exception as exc:
            rejected, error = True, str(exc)
        if not rejected:
            raise RuntimeError(f"negative control escaped: {case_id}")
        rows.append({"case_id": case_id, "mutation": reason, "expected": "REJECT", "actual": "REJECT", "pass": True, "rejection": error})
    document = {
        "schema": "ROUTE_C_LINK1_B6_NEGATIVE_CONTROLS_V1", "generated_utc": "DETERMINISTIC_VALIDATION_NO_WALLCLOCK",
        "case_count": len(rows), "pass_count": sum(row["pass"] for row in rows), "fail_count": sum(not row["pass"] for row in rows),
        "cases": rows, "verdict": "44_OF_44_NEGATIVE_CONTROLS_REJECTED_FAIL_CLOSED",
    }
    data = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
    if args.write:
        temporary = OUTPUT.with_suffix(".json.tmp"); temporary.write_bytes(data); temporary.replace(OUTPUT)
    print(json.dumps({"cases": len(rows), "passed": len(rows), "mode": "write" if args.write else "check", "verdict": document["verdict"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
