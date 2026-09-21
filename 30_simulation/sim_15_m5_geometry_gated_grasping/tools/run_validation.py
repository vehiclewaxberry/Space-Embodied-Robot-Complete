"""Recompute and validate the complete Sim15 diagnostic evidence chain."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


SIM15_ROOT = Path(__file__).resolve().parents[1]
if str(SIM15_ROOT) not in sys.path:
    sys.path.insert(0, str(SIM15_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate_baseline import (  # noqa: E402
    BINDING_RECEIPT_NAME,
    DEFAULT_INTERFACE,
    DEFAULT_OUTPUT,
    GATE_NAME,
    OUTPUT_MANIFEST_NAME,
    SOLVER_MANIFEST_NAME,
    SOURCE_MANIFEST_NAME,
    build_evidence_suite,
    canonical_sha256,
    rendered_sha256,
)
from src.authority import ACKNOWLEDGEMENT, load_authority, sha256_file  # noqa: E402
from src.env import (  # noqa: E402
    ExecutionMode,
    ProductionModeNotAuthorized,
    Sim15DiagnosticEnv,
)


def _load_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"expected JSON mapping in {path}")
    return value


def _hash_chain_findings(document: Mapping[str, Any]) -> list[str]:
    findings: list[str] = []
    solver_hash = document.get("hash_receipt", {}).get("solver_bundle_sha256")
    solver_receipt = document.get("solver_receipt", {})
    if solver_hash != solver_receipt.get("bundle_sha256"):
        findings.append("TOP_LEVEL_SOLVER_HASH_MISMATCH")
    files = solver_receipt.get("files")
    if not isinstance(files, Mapping):
        findings.append("SOLVER_FILE_RECEIPT_MISSING")
    else:
        if canonical_sha256(files) != solver_receipt.get("bundle_sha256"):
            findings.append("SOLVER_BUNDLE_CANONICAL_HASH_MISMATCH")
        for relative, expected in files.items():
            path = SIM15_ROOT / str(relative)
            actual = sha256_file(path) if path.is_file() else "MISSING"
            if actual != expected:
                findings.append(f"SOLVER_FILE_HASH_MISMATCH:{relative}")

    capture = document.get("capture_envelope", {})
    joint = document.get("joint_load_validation", {})
    capture_cases = capture.get("cases") if isinstance(capture, Mapping) else None
    joint_rows = joint.get("rows") if isinstance(joint, Mapping) else None
    if not isinstance(capture_cases, list) or len(capture_cases) != 8:
        findings.append("CAPTURE_CASE_COUNT_NOT_8")
        capture_cases = []
    if not isinstance(joint_rows, list) or len(joint_rows) != 6:
        findings.append("JOINT_ROW_COUNT_NOT_6")
        joint_rows = []

    for record in [*capture_cases, *joint_rows]:
        if not isinstance(record, Mapping):
            findings.append("CASE_OR_ROW_NOT_MAPPING")
            continue
        identifier = record.get("case_id", record.get("row_id", "UNKNOWN"))
        if canonical_sha256(record.get("inputs")) != record.get("input_sha256"):
            findings.append(f"INPUT_HASH_MISMATCH:{identifier}")
        if record.get("solver_sha256") != solver_hash:
            findings.append(f"SOLVER_HASH_MISMATCH:{identifier}")
        if canonical_sha256(record.get("output")) != record.get("output_sha256"):
            findings.append(f"OUTPUT_HASH_MISMATCH:{identifier}")

    hash_receipt = document.get("hash_receipt", {})
    all_inputs = [record["inputs"] for record in [*capture_cases, *joint_rows]]
    all_outputs = [record["output"] for record in [*capture_cases, *joint_rows]]
    if canonical_sha256(all_inputs) != hash_receipt.get("diagnostic_inputs_sha256"):
        findings.append("AGGREGATE_INPUT_HASH_MISMATCH")
    if canonical_sha256(all_outputs) != hash_receipt.get("diagnostic_outputs_sha256"):
        findings.append("AGGREGATE_OUTPUT_HASH_MISMATCH")
    return findings


def _production_abort_check(interface_path: Path) -> bool:
    authority = load_authority(interface_path)
    try:
        Sim15DiagnosticEnv(
            authority,
            acknowledgement=ACKNOWLEDGEMENT,
            mode=ExecutionMode.PRODUCTION,
        )
    except ProductionModeNotAuthorized:
        return True
    return False


def _suite_hash_findings(
    documents: Mapping[str, Mapping[str, Any]], baseline_name: str
) -> list[str]:
    findings: list[str] = []
    baseline = documents[baseline_name]
    output_manifest = documents[OUTPUT_MANIFEST_NAME]
    gate = documents[GATE_NAME]
    receipt = documents[BINDING_RECEIPT_NAME]
    if output_manifest.get("baseline", {}).get("sha256") != rendered_sha256(baseline):
        findings.append("OUTPUT_MANIFEST_BASELINE_HASH_MISMATCH")
    critical = gate.get("critical_evidence")
    if not isinstance(critical, Mapping):
        findings.append("GATE_CRITICAL_EVIDENCE_MISSING")
    else:
        for filename in (
            baseline_name,
            SOURCE_MANIFEST_NAME,
            SOLVER_MANIFEST_NAME,
            OUTPUT_MANIFEST_NAME,
        ):
            record = critical.get(filename)
            if not isinstance(record, Mapping):
                findings.append(f"GATE_EVIDENCE_RECORD_MISSING:{filename}")
            elif record.get("sha256") != rendered_sha256(documents[filename]):
                findings.append(f"GATE_EVIDENCE_HASH_MISMATCH:{filename}")
    receipt_records = receipt.get("evidence")
    if not isinstance(receipt_records, Mapping):
        findings.append("BINDING_RECEIPT_EVIDENCE_MISSING")
    else:
        for filename in (
            baseline_name,
            SOURCE_MANIFEST_NAME,
            SOLVER_MANIFEST_NAME,
            OUTPUT_MANIFEST_NAME,
            GATE_NAME,
        ):
            record = receipt_records.get(filename)
            if not isinstance(record, Mapping):
                findings.append(f"RECEIPT_EVIDENCE_RECORD_MISSING:{filename}")
            elif record.get("sha256") != rendered_sha256(documents[filename]):
                findings.append(f"RECEIPT_EVIDENCE_HASH_MISMATCH:{filename}")
    return findings


def validate(
    *,
    interface_path: Path,
    baseline_path: Path,
    allow_missing_baseline: bool,
) -> tuple[dict[str, Any], bool]:
    first_suite = build_evidence_suite(
        interface_path, baseline_name=baseline_path.name
    )
    second_suite = build_evidence_suite(
        interface_path, baseline_name=baseline_path.name
    )
    first = first_suite[baseline_path.name]
    deterministic_recompute = first_suite == second_suite
    hash_findings = _hash_chain_findings(first)
    hash_findings.extend(_suite_hash_findings(first_suite, baseline_path.name))
    production_aborts = _production_abort_check(interface_path)

    evidence_status: dict[str, dict[str, Any]] = {}
    published_matches = True
    for filename, expected_document in first_suite.items():
        path = baseline_path.parent / filename
        if path.is_file():
            matches = _load_json(path) == expected_document
            status = "MATCH" if matches else "MISMATCH"
            actual_sha256: str | None = sha256_file(path)
        else:
            matches = allow_missing_baseline
            status = (
                "MISSING_ALLOWED_FOR_SOURCE_SMOKE"
                if allow_missing_baseline
                else "MISSING"
            )
            actual_sha256 = None
        published_matches = published_matches and matches
        evidence_status[filename] = {
            "path": str(path.resolve()),
            "status": status,
            "sha256": actual_sha256,
        }

    test = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=SIM15_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    passed = (
        deterministic_recompute
        and not hash_findings
        and production_aborts
        and published_matches
        and test.returncode == 0
        and first.get("capture_envelope", {}).get("case_count") == 8
        and first.get("joint_load_validation", {}).get("row_count") == 6
        and first.get("lg_019_gate", {}).get("status")
        == "PASS_SIM15_DIAGNOSTIC_REPRODUCIBILITY_CLOSURE"
        and first.get("authority_binding", {}).get("m5_authority_modified_or_upgraded")
        is False
        and first.get("physical_contact_gate") == "HOLD"
        and first.get("production_gate") == "ABORT_NOT_AUTHORIZED"
    )
    report = {
        "schema": "SIM15_VALIDATION_REPORT_V1",
        "verdict": "PASS_DIAGNOSTIC_ONLY" if passed else "FAIL",
        "scope": "SIM15_DIAGNOSTIC_SOFTWARE_ONLY_NOT_PHYSICAL_OR_FLIGHT_AUTHORITY",
        "baseline_path": str(baseline_path.resolve()),
        "baseline_status": evidence_status[baseline_path.name]["status"],
        "baseline_file_sha256": evidence_status[baseline_path.name]["sha256"],
        "evidence_files": evidence_status,
        "deterministic_recompute": deterministic_recompute,
        "hash_chain_findings": hash_findings,
        "production_mode_aborts": production_aborts,
        "pytest_exit_code": test.returncode,
        "pytest_output": (test.stdout + test.stderr).strip(),
        "capture_case_count": first.get("capture_envelope", {}).get("case_count"),
        "joint_validation_row_count": first.get("joint_load_validation", {}).get("row_count"),
        "lg_019_status": first.get("lg_019_gate", {}).get("status"),
        "hash_receipt": first.get("hash_receipt"),
        "m5_authority_modified_or_upgraded": False,
        "physical_contact_gate": first.get("physical_contact_gate"),
        "structural_analysis_gate": first.get("structural_analysis_gate"),
        "production_gate": first.get("production_gate"),
    }
    return report, passed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interface", type=Path, default=DEFAULT_INTERFACE)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--allow-missing-baseline",
        action="store_true",
        help="permit source-only smoke before the final interface freeze",
    )
    args = parser.parse_args(argv)
    report, passed = validate(
        interface_path=args.interface,
        baseline_path=args.baseline,
        allow_missing_baseline=args.allow_missing_baseline,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
