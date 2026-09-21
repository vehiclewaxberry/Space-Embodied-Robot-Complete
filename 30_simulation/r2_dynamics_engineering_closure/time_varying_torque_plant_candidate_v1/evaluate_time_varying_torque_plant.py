#!/usr/bin/env python3
"""Build, write, or deterministically replay-check the candidate evidence."""

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

from time_varying_torque_plant import (  # noqa: E402
    canonical_bytes,
    canonical_sha256,
    build_candidate,
    file_record,
    load_contract,
    load_json_strict,
    to_builtin,
)


RESULTS = PACKAGE_ROOT / "results"
EVIDENCE_PATH = RESULTS / "R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_EVIDENCE_V1.json"
GATE_PATH = RESULTS / "R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_GATE_V1.json"
MANIFEST_PATH = RESULTS / "R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_MANIFEST_V1.json"
INDEPENDENT_RECEIPT_PATH = RESULTS / "R2_TIME_VARYING_TORQUE_PLANT_INDEPENDENT_VALIDATION_V1.json"
FROZEN_PACKAGE_PATHS = (
    "README.md",
    "contracts/R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_CONTRACT_V1.json",
    "evaluate_time_varying_torque_plant.py",
    "independent_validate_time_varying_torque_plant.py",
    "results/R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_EVIDENCE_V1.json",
    "results/R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_GATE_V1.json",
    "run_validation.py",
    "src/__init__.py",
    "src/time_varying_torque_plant.py",
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
        "manifest_self_present_or_pending": MANIFEST_PATH.is_file(),
        "independent_receipt_dynamic_present": INDEPENDENT_RECEIPT_PATH.is_file(),
        "exact": not missing and not unexpected,
    }


def build_manifest(contract: Mapping[str, Any]) -> dict[str, Any]:
    payload = directory_payload_audit()
    if not payload["exact"]:
        raise RuntimeError(
            "DIRECTORY_PAYLOAD_NOT_EXACT:"
            + json.dumps(payload, sort_keys=True, separators=(",", ":"))
        )
    entries: list[dict[str, Any]] = []
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
        "schema": "R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_MANIFEST_V1",
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


def check_manifest(manifest: Mapping[str, Any], contract: Mapping[str, Any]) -> dict[str, Any]:
    expected = build_manifest(contract)
    return {
        "schema_exact": manifest.get("schema") == expected["schema"],
        "self_excluded": manifest.get("self_excluded") is True
        and manifest.get("self_excluded_path") == expected["self_excluded_path"],
        "frozen_allowlist_exact": manifest.get("frozen_package_path_allowlist")
        == expected["frozen_package_path_allowlist"],
        "directory_payload_exact": directory_payload_audit()["exact"]
        and manifest.get("directory_payload_exact_at_generation") is True
        and manifest.get("cache_bytecode_or_unlisted_payload_allowed") is False,
        "exclusions_exact": manifest.get("exclusions") == expected["exclusions"],
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
        "manifest_entries_canonical_sha256": manifest["package_entries_canonical_sha256"],
        "manifest_entry_count": manifest["package_entry_count"],
    }


def check_outputs(evidence: Mapping[str, Any], gate: Mapping[str, Any]) -> dict[str, Any]:
    if not EVIDENCE_PATH.is_file() or not GATE_PATH.is_file() or not MANIFEST_PATH.is_file():
        raise RuntimeError("CANDIDATE_OUTPUTS_MISSING")
    stored_evidence = load_json_strict(EVIDENCE_PATH)
    stored_gate = load_json_strict(GATE_PATH)
    stored_manifest = load_json_strict(MANIFEST_PATH)
    manifest_checks = check_manifest(stored_manifest, load_contract())
    checks = {
        "evidence_canonical_exact": canonical_bytes(stored_evidence) == canonical_bytes(evidence),
        "gate_canonical_exact": canonical_bytes(stored_gate) == canonical_bytes(gate),
        "manifest_all_checks_pass": all(manifest_checks.values()),
        "gate_24_of_24": stored_gate.get("passed") == 24
        and stored_gate.get("total") == 24
        and stored_gate.get("all_checks_pass") is True,
        "authority_false": stored_gate.get("next_stage_authorized") is False
        and stored_gate.get("release_credit") is False,
    }
    return {"checks": checks, "manifest_checks": manifest_checks, "all_pass": all(checks.values())}


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="recompute and write deterministic artifacts")
    mode.add_argument("--check", action="store_true", help="recompute and compare against stored artifacts")
    mode.add_argument("--stdout", action="store_true", help="recompute and print the gate only")
    mode.add_argument(
        "--refresh-manifest",
        action="store_true",
        help="refresh only the fixed-allowlist manifest from already stored evidence and gate",
    )
    args = parser.parse_args()
    if args.refresh_manifest:
        stored_gate = load_json_strict(GATE_PATH)
        load_json_strict(EVIDENCE_PATH)
        if (
            stored_gate.get("passed") != 24
            or stored_gate.get("total") != 24
            or stored_gate.get("all_checks_pass") is not True
            or stored_gate.get("review_status") != "PENDING_OWNER_REVIEW"
        ):
            raise RuntimeError("STORED_GATE_NOT_ELIGIBLE_FOR_MANIFEST_REFRESH")
        manifest = build_manifest(load_contract())
        write_exact(MANIFEST_PATH, manifest)
        print(
            json.dumps(
                {
                    "manifest": file_record(MANIFEST_PATH),
                    "manifest_entries_canonical_sha256": manifest[
                        "package_entries_canonical_sha256"
                    ],
                    "manifest_entry_count": manifest["package_entry_count"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    evidence, gate = build_candidate(PROJECT_ROOT)
    if args.write:
        receipt = write_outputs(evidence, gate)
        print(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False))
        return 0 if gate["all_checks_pass"] else 2
    if args.check:
        result = check_outputs(evidence, gate)
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False))
        return 0 if result["all_pass"] else 3
    print(json.dumps(gate, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False))
    return 0 if gate["all_checks_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
