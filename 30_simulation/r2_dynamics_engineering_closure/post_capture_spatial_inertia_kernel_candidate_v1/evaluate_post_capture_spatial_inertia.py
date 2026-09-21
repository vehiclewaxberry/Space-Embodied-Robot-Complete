#!/usr/bin/env python3
"""Build and replay-check the post-capture spatial-inertia kernel evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[2]
SRC = PACKAGE_ROOT / "src"
sys.dont_write_bytecode = True
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from post_capture_spatial_inertia import (  # noqa: E402
    build_candidate,
    canonical_bytes,
    canonical_sha256,
    file_record,
    load_contract,
    load_json_strict,
    to_builtin,
)


RESULTS = PACKAGE_ROOT / "results"
EVIDENCE_PATH = RESULTS / "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_EVIDENCE_V1.json"
GATE_PATH = RESULTS / "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_GATE_V1.json"
MANIFEST_PATH = RESULTS / "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_MANIFEST_V1.json"
INDEPENDENT_RECEIPT_PATH = RESULTS / "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_INDEPENDENT_VALIDATION_V1.json"
FROZEN_PACKAGE_PATHS = (
    "README.md",
    "contracts/POST_CAPTURE_SPATIAL_INERTIA_KERNEL_CONTRACT_V1.json",
    "evaluate_post_capture_spatial_inertia.py",
    "independent_validate_post_capture_spatial_inertia.py",
    "results/POST_CAPTURE_SPATIAL_INERTIA_KERNEL_EVIDENCE_V1.json",
    "results/POST_CAPTURE_SPATIAL_INERTIA_KERNEL_GATE_V1.json",
    "run_validation.py",
    "src/__init__.py",
    "src/post_capture_spatial_inertia.py",
    "tests/conftest.py",
    "tests/test_candidate.py",
)


def pretty_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            to_builtin(value),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def write_exact(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pretty_bytes(value))


def package_file_paths() -> list[Path]:
    paths = [PACKAGE_ROOT / relative for relative in FROZEN_PACKAGE_PATHS]
    missing = [
        path.relative_to(PACKAGE_ROOT).as_posix()
        for path in paths
        if not path.is_file()
    ]
    if missing:
        raise RuntimeError(f"FROZEN_PACKAGE_PAYLOAD_MISSING:{','.join(missing)}")
    return paths


def directory_payload_audit() -> dict[str, Any]:
    actual = sorted(
        path.relative_to(PACKAGE_ROOT).as_posix()
        for path in PACKAGE_ROOT.rglob("*")
        if path.is_file()
    )
    required = set(FROZEN_PACKAGE_PATHS)
    allowed_dynamic = {
        MANIFEST_PATH.relative_to(PACKAGE_ROOT).as_posix(),
        INDEPENDENT_RECEIPT_PATH.relative_to(PACKAGE_ROOT).as_posix(),
    }
    actual_set = set(actual)
    missing = sorted(required - actual_set)
    unexpected = sorted(actual_set - required - allowed_dynamic)
    return {
        "frozen_package_paths": list(FROZEN_PACKAGE_PATHS),
        "actual_file_paths": actual,
        "missing_frozen_paths": missing,
        "unexpected_paths": unexpected,
        "exact": not missing and not unexpected,
    }


def build_manifest(contract: Mapping[str, Any]) -> dict[str, Any]:
    payload = directory_payload_audit()
    if not payload["exact"]:
        raise RuntimeError(
            "DIRECTORY_PAYLOAD_NOT_EXACT:"
            + json.dumps(payload, sort_keys=True, separators=(",", ":"))
        )
    entries = []
    for path in package_file_paths():
        raw = path.read_bytes()
        entries.append(
            {
                "path": path.relative_to(PACKAGE_ROOT).as_posix(),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest().upper(),
            }
        )
    return {
        "schema": "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_MANIFEST_V1",
        "deterministic": True,
        "self_excluded": True,
        "self_excluded_path": MANIFEST_PATH.relative_to(PACKAGE_ROOT).as_posix(),
        "exclusions": [
            INDEPENDENT_RECEIPT_PATH.relative_to(PACKAGE_ROOT).as_posix()
        ],
        "independent_validation_receipt_excluded": True,
        "cache_bytecode_or_unlisted_payload_allowed": False,
        "frozen_package_path_allowlist": list(FROZEN_PACKAGE_PATHS),
        "directory_payload_exact_at_generation": True,
        "package_entries": entries,
        "package_entry_count": len(entries),
        "package_entries_canonical_sha256": canonical_sha256(entries),
        "external_source_pins": contract["source_pins"],
        "external_source_pin_count": len(contract["source_pins"]),
        "next_stage_authorized": False,
        "release_credit": False,
    }


def check_manifest(manifest: Mapping[str, Any], contract: Mapping[str, Any]) -> dict[str, bool]:
    expected = build_manifest(contract)
    return {
        "schema_exact": manifest.get("schema") == expected["schema"],
        "self_excluded": manifest.get("self_excluded") is True
        and manifest.get("self_excluded_path") == expected["self_excluded_path"],
        "exclusions_exact": manifest.get("exclusions") == expected["exclusions"],
        "frozen_allowlist_exact": manifest.get("frozen_package_path_allowlist")
        == expected["frozen_package_path_allowlist"],
        "directory_payload_exact": directory_payload_audit()["exact"]
        and manifest.get("directory_payload_exact_at_generation") is True
        and manifest.get("cache_bytecode_or_unlisted_payload_allowed") is False,
        "package_entries_exact": manifest.get("package_entries") == expected["package_entries"],
        "package_entries_hash_exact": manifest.get("package_entries_canonical_sha256")
        == expected["package_entries_canonical_sha256"],
        "external_source_pins_exact": manifest.get("external_source_pins")
        == expected["external_source_pins"],
        "authority_false": manifest.get("next_stage_authorized") is False
        and manifest.get("release_credit") is False,
    }


def write_outputs(evidence: Mapping[str, Any], gate: Mapping[str, Any]) -> dict[str, Any]:
    write_exact(EVIDENCE_PATH, evidence)
    write_exact(GATE_PATH, gate)
    contract = load_contract()
    manifest = build_manifest(contract)
    write_exact(MANIFEST_PATH, manifest)
    return {
        "evidence": file_record(EVIDENCE_PATH),
        "gate": file_record(GATE_PATH),
        "manifest": file_record(MANIFEST_PATH),
        "manifest_entry_count": manifest["package_entry_count"],
        "manifest_entries_canonical_sha256": manifest[
            "package_entries_canonical_sha256"
        ],
    }


def check_outputs(evidence: Mapping[str, Any], gate: Mapping[str, Any]) -> dict[str, Any]:
    stored_evidence = load_json_strict(EVIDENCE_PATH)
    stored_gate = load_json_strict(GATE_PATH)
    stored_manifest = load_json_strict(MANIFEST_PATH)
    contract = load_contract()
    manifest_checks = check_manifest(stored_manifest, contract)
    checks = {
        "evidence_canonical_exact": canonical_bytes(stored_evidence)
        == canonical_bytes(evidence),
        "gate_canonical_exact": canonical_bytes(stored_gate) == canonical_bytes(gate),
        "gate_22_of_22": gate["passed"] == 22
        and gate["total"] == 22
        and gate["all_checks_pass"] is True,
        "review_status_exact": gate["review_status"] == "PENDING_OWNER_REVIEW",
        "current_instances_not_evaluated": gate["current_C08_status"]
        == "NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3"
        and gate["current_C09_status"]
        == "NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3",
        "authority_false": all(
            gate[key] is False
            for key in (
                "current_system_instance_evaluated",
                "contact_valid",
                "attachment_valid",
                "target_attachment_plant_valid",
                "hardware_valid",
                "non_abort_authorized",
                "parent_dynamics_engineering_complete",
                "next_stage_authorized",
                "release_credit",
            )
        ),
        "manifest_all_checks_pass": all(manifest_checks.values()),
    }
    return {
        "checks": checks,
        "manifest_checks": manifest_checks,
        "all_pass": all(checks.values()),
    }


def refresh_manifest() -> dict[str, Any]:
    gate = load_json_strict(GATE_PATH)
    if (
        gate.get("passed") != 22
        or gate.get("total") != 22
        or gate.get("all_checks_pass") is not True
        or gate.get("review_status") != "PENDING_OWNER_REVIEW"
    ):
        raise RuntimeError("STORED_GATE_NOT_ELIGIBLE_FOR_MANIFEST_REFRESH")
    contract = load_contract()
    manifest = build_manifest(contract)
    write_exact(MANIFEST_PATH, manifest)
    return {
        "manifest": file_record(MANIFEST_PATH),
        "manifest_entry_count": manifest["package_entry_count"],
        "manifest_entries_canonical_sha256": manifest[
            "package_entries_canonical_sha256"
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--stdout", action="store_true")
    mode.add_argument("--refresh-manifest", action="store_true")
    args = parser.parse_args()
    if args.refresh_manifest:
        print(json.dumps(refresh_manifest(), indent=2, sort_keys=True))
        return 0
    evidence, gate = build_candidate()
    if args.write:
        result = write_outputs(evidence, gate)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if gate["all_checks_pass"] else 2
    if args.check:
        result = check_outputs(evidence, gate)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["all_pass"] else 3
    print(json.dumps({"evidence": evidence, "gate": gate}, indent=2, sort_keys=True))
    return 0 if gate["all_checks_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

