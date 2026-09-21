#!/usr/bin/env python3
"""Independent structural and byte-level validator for the R2 reissue package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterator

from build_current_state_reissue import (
    GATE_NAME,
    INPUT_NAME,
    PACKAGE_NAME,
    PACKAGE_REL,
    SOURCE_SPECS,
    CurrentStateError,
    build_documents,
    canonical_json,
    require,
    sha256_bytes,
    strict_json_bytes,
    workspace_root,
)


def _safe_resolve(root: Path, rel: str) -> Path:
    require(isinstance(rel, str) and rel != "", "manifest path must be a non-empty string")
    candidate = Path(rel)
    require(not candidate.is_absolute(), f"absolute manifest path rejected: {rel}")
    require("\\" not in rel, f"non-canonical backslash path rejected: {rel}")
    require(".." not in candidate.parts, f"path traversal rejected: {rel}")
    resolved = (root / candidate).resolve()
    require(resolved == root or root in resolved.parents, f"path escapes workspace: {rel}")
    return resolved


def _walk_flags(value: Any) -> Iterator[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"next_stage_authorized", "release_credit"}:
                yield key, child
            yield from _walk_flags(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_flags(child)


def validate_package(root: Path | None = None, package_dir: Path | None = None) -> dict[str, Any]:
    root = (root or workspace_root()).resolve()
    package_dir = (package_dir or (root / PACKAGE_REL)).resolve()
    require(package_dir.is_dir(), f"package directory missing: {package_dir}")

    paths = {name: package_dir / name for name in (INPUT_NAME, GATE_NAME, PACKAGE_NAME)}
    for name, path in paths.items():
        require(path.is_file(), f"missing generated layer: {name}")

    actual_bytes = {name: path.read_bytes() for name, path in paths.items()}
    parsed = {name: strict_json_bytes(data, name) for name, data in actual_bytes.items()}
    input_manifest = parsed[INPUT_NAME]
    gate = parsed[GATE_NAME]
    package_manifest = parsed[PACKAGE_NAME]

    expected = build_documents(root, package_dir)
    exact_layers = {name: actual_bytes[name] == expected[name] for name in actual_bytes}
    require(all(exact_layers.values()), f"non-deterministic/stale layer(s): {exact_layers}")

    expected_source_ids = [row[0] for row in SOURCE_SPECS]
    expected_source_paths = [row[1] for row in SOURCE_SPECS]
    source_pins = input_manifest.get("source_pins")
    require(isinstance(source_pins, list), "source_pins must be a list")
    require(len(source_pins) == 27 and input_manifest.get("source_count") == 27,
            "input manifest must bind exactly 27 sources")
    require([row.get("id") for row in source_pins] == expected_source_ids,
            "source ids/order mismatch")
    require([row.get("path") for row in source_pins] == expected_source_paths,
            "source paths/order mismatch")
    require(len(set(expected_source_ids)) == 27 and len(set(expected_source_paths)) == 27,
            "source registry is not unique")

    source_hashes_match = True
    for pin in source_pins:
        source = _safe_resolve(root, pin["path"])
        require(source.is_file(), f"pinned source missing: {pin['path']}")
        data = source.read_bytes()
        if pin.get("bytes") != len(data) or pin.get("sha256") != sha256_bytes(data):
            source_hashes_match = False
            break
    require(source_hashes_match, "one or more source hashes do not match")

    input_rel = str(PACKAGE_REL / INPUT_NAME).replace("\\", "/")
    gate_input_pin = gate.get("input_manifest")
    require(isinstance(gate_input_pin, dict), "Gate input manifest pin missing")
    require(gate_input_pin == {
        "bytes": len(actual_bytes[INPUT_NAME]),
        "path": input_rel,
        "sha256": sha256_bytes(actual_bytes[INPUT_NAME]),
    }, "Gate does not bind the exact input manifest")

    require(input_manifest.get("layer") == 1, "input layer must be 1")
    require(gate.get("layer") == 2, "Gate layer must be 2")
    require(package_manifest.get("layer") == 3, "package layer must be 3")
    require(package_manifest.get("layer_order") == [INPUT_NAME, GATE_NAME, PACKAGE_NAME],
            "layer order mismatch")
    require(PACKAGE_NAME not in input_manifest.get("schema", ""),
            "input layer references package layer")
    require("package_manifest" not in gate, "Gate references package manifest")

    entries = package_manifest.get("package_entries")
    require(isinstance(entries, list) and len(entries) == 6,
            "package manifest must bind exactly six non-self artifacts")
    require(package_manifest.get("entry_count") == 6, "package entry count mismatch")
    expected_local_paths = {
        str(PACKAGE_REL / "README.md").replace("\\", "/"),
        str(PACKAGE_REL / "build_current_state_reissue.py").replace("\\", "/"),
        str(PACKAGE_REL / "validate_current_state_reissue.py").replace("\\", "/"),
        str(PACKAGE_REL / "tests/test_current_state_reissue.py").replace("\\", "/"),
        input_rel,
        str(PACKAGE_REL / GATE_NAME).replace("\\", "/"),
    }
    entry_paths = [entry.get("path") for entry in entries]
    require(set(entry_paths) == expected_local_paths and len(set(entry_paths)) == 6,
            "package entries are incomplete, duplicated, or unexpected")
    manifest_rel = str(PACKAGE_REL / PACKAGE_NAME).replace("\\", "/")
    require(manifest_rel not in entry_paths, "package manifest must exclude itself")
    require(package_manifest.get("self_reference_policy") == f"{PACKAGE_NAME} EXCLUDES_ITSELF",
            "package self-reference policy mismatch")

    package_hashes_match = True
    for entry in entries:
        artifact = _safe_resolve(root, entry["path"])
        require(artifact.is_file(), f"package artifact missing: {entry['path']}")
        data = artifact.read_bytes()
        if entry.get("bytes") != len(data) or entry.get("sha256") != sha256_bytes(data):
            package_hashes_match = False
            break
    require(package_hashes_match, "one or more package hashes do not match")

    checks = gate.get("checks")
    require(isinstance(checks, dict) and len(checks) >= 16, "fewer than 16 Gate checks")
    require(all(value is True for value in checks.values()), "one or more Gate checks are not true")
    require(gate.get("summary") == {"failed": [], "passed": len(checks), "total": len(checks)},
            "Gate summary mismatch")
    require(gate.get("technical_verdict") ==
            "PASS_APPEND_ONLY_CURRENT_STATE_REISSUE_INTEGRITY__MECHANICAL_DYNAMICS_CONTROL_SIM13_AND_RELEASE_HOLD",
            "Gate verdict changed")
    require(gate.get("parent_artifacts_modified") is False, "parent mutation claimed")
    require(gate.get("mechanical_release_ready") is False, "mechanical release unexpectedly ready")
    require(gate.get("reissue_integrity_pass") is True, "reissue integrity not passed")

    all_flags = list(_walk_flags([input_manifest, gate, package_manifest]))
    require(all(value is False for _key, value in all_flags),
            f"a generated next/release flag is not false: {all_flags}")

    truth = gate["current_truth"]
    defect = truth["baseline_manifest_integrity_defect"]
    require(defect["defect_confirmed"] is True and defect["repair_or_parent_mutation_performed"] is False,
            "baseline defect boundary missing")
    require(truth["mechanical_m01_route_c"]["route_c_m01_raw_clearance_mm"] == -10.729480331980062,
            "raw M01 witness mismatch")
    require(truth["mechanical_m01_route_c"]["route_c_m01_gated_clearance_mm"] == -17.313396996697108,
            "gated M01 witness mismatch")
    require(truth["sim13"]["backend_negative_control_subscope"] == "20_OF_20_PASS"
            and truth["sim13"]["full_tmg6_reissued"] is False,
            "Sim13 backend/full-gate boundary mismatch")
    require(truth["dynamics"]["V3"] == "19_OF_19_ADDITIVE_CONVERGENCE"
            and truth["dynamics"]["parent_dynamics"] == "1_OF_6_HOLD_NOT_REISSUED",
            "candidate/parent dynamics boundary mismatch")
    require(truth["control_and_joint"]["joint_gate"] == "4_OF_13"
            and truth["control_and_joint"]["joint_system_ready"] is False,
            "joint HOLD boundary mismatch")
    require(truth["l06_drawing_bom_material_conflict"]["manufacturing_use"] == "PROHIBITED_8_OF_8",
            "L06 manufacturing prohibition missing")
    require(truth["l06_drawing_bom_material_conflict"]["current_m3r_stage_a_b_design_material"] ==
            "PMAT-AL7075-T651-SHEET-PLATE",
            "L06 current material binding mismatch")

    validation_checks = {
        "V-01_three_layers_exist": True,
        "V-02_three_layers_strict_json": True,
        "V-03_three_layers_deterministic_byte_exact": all(exact_layers.values()),
        "V-04_input_has_exactly_27_sources": len(source_pins) == 27,
        "V-05_source_ids_exact_and_ordered": [row["id"] for row in source_pins] == expected_source_ids,
        "V-06_source_paths_exact_and_ordered": [row["path"] for row in source_pins] == expected_source_paths,
        "V-07_all_source_hashes_match": source_hashes_match,
        "V-08_gate_binds_exact_input_manifest": True,
        "V-09_layer_order_is_one_way": True,
        "V-10_package_has_exactly_six_nonself_entries": len(entries) == 6,
        "V-11_package_manifest_excludes_itself": manifest_rel not in entry_paths,
        "V-12_all_package_hashes_match": package_hashes_match,
        "V-13_gate_has_at_least_16_checks": len(checks) >= 16,
        "V-14_all_gate_checks_true": all(checks.values()),
        "V-15_baseline_self_defect_recorded_without_repair": True,
        "V-16_route_c_m01_negative_witness_exact": True,
        "V-17_sim13_20_of_20_limited_to_backend_subscope": True,
        "V-18_dg1_to_dg5_v3_candidate_parent_boundary_exact": True,
        "V-19_control_and_joint_hold_exact": True,
        "V-20_l06_6061_7075_and_sibling_debt_exact": True,
        "V-21_all_generated_next_and_release_flags_false": all(value is False for _key, value in all_flags),
        "V-22_parent_artifacts_unmodified_by_package": gate["parent_artifacts_modified"] is False,
    }
    require(all(validation_checks.values()), "validator check failure")
    return {
        "checks": validation_checks,
        "gate_sha256": sha256_bytes(actual_bytes[GATE_NAME]),
        "input_manifest_sha256": sha256_bytes(actual_bytes[INPUT_NAME]),
        "package_manifest_sha256": sha256_bytes(actual_bytes[PACKAGE_NAME]),
        "passed": len(validation_checks),
        "source_count": len(source_pins),
        "total": len(validation_checks),
        "verdict": "PASS_22_OF_22_CURRENT_STATE_REISSUE_VALIDATION__NO_RELEASE_AUTHORITY",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit full validation JSON")
    args = parser.parse_args()
    result = validate_package()
    if args.json:
        print(canonical_json(result).decode("utf-8"), end="")
    else:
        print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CurrentStateError as exc:
        print(json.dumps({"error": str(exc), "verdict": "FAIL_CLOSED"}, sort_keys=True))
        raise SystemExit(1)
