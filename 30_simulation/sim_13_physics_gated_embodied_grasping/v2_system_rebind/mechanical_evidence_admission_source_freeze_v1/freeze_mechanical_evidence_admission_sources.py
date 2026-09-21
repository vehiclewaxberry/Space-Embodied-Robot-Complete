"""Freeze deterministic source-only validation evidence and the capped Gate."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from mechanical_admission.evaluator import GATE_CEILING, evaluate_default_snapshot, validate_publication_candidate
from mechanical_admission.freeze_support import file_receipt, source_inventory, write_canonical_json
from mechanical_admission.negative_controls import run_negative_controls
from mechanical_admission.strict_io import PROJECT_ROOT


EVIDENCE_DIR = PACKAGE_ROOT / "evidence"
RESULTS_DIR = PACKAGE_ROOT / "results"
VALIDATION_PATH = EVIDENCE_DIR / "M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_VALIDATION_V1.json"
NC_PATH = EVIDENCE_DIR / "M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_NEGATIVE_CONTROLS_V1.json"
MANIFEST_PATH = EVIDENCE_DIR / "M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_SOURCE_MANIFEST_V1.json"
AUDIT_PATH = EVIDENCE_DIR / "M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_INDEPENDENT_AUDIT_V1.json"
GATE_PATH = RESULTS_DIR / "M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_SOURCE_FREEZE_GATE_V1.json"
TERMINAL_PATH = RESULTS_DIR / "M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_SOURCE_FREEZE_TERMINAL_V1.json"
CONTRACT_NAMES = (
    "MECHANICAL_EVIDENCE_ADMISSION_CONTRACT_V1.json",
    "MECHANICAL_EVIDENCE_SOURCE_BINDINGS_V1.json",
    "MECHANICAL_EVIDENCE_NEGATIVE_CONTROL_CONTRACT_V1.json",
)


def build_manifest() -> dict:
    records = source_inventory()
    return {
        "schema": "M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_SOURCE_MANIFEST_V1",
        "artifact_id": "SIM13_M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_V1",
        "inventory_scope": "PACKAGE_SOURCES_ONLY__EVIDENCE_RESULTS_AND_CACHES_EXCLUDED",
        "files": records,
        "file_count": len(records),
        "generated_mechanical_or_physics_artifacts": False,
    }


def write_source_evidence() -> None:
    validation = evaluate_default_snapshot()
    validate_publication_candidate(validation)
    negative_controls = run_negative_controls()
    if not negative_controls["all_passed"]:
        raise SystemExit("negative controls failed")
    write_canonical_json(VALIDATION_PATH, validation)
    write_canonical_json(NC_PATH, negative_controls)
    write_canonical_json(MANIFEST_PATH, build_manifest())


def _contract_receipts() -> list[dict]:
    return [file_receipt(PACKAGE_ROOT / "contracts" / name) for name in CONTRACT_NAMES]


def write_gate() -> None:
    required = (VALIDATION_PATH, NC_PATH, MANIFEST_PATH, AUDIT_PATH)
    if any(not path.is_file() for path in required):
        raise SystemExit("source evidence and independent audit must exist before Gate freeze")
    validation = __import__("json").loads(VALIDATION_PATH.read_text(encoding="utf-8"))
    negative = __import__("json").loads(NC_PATH.read_text(encoding="utf-8"))
    audit = __import__("json").loads(AUDIT_PATH.read_text(encoding="utf-8"))
    if validation.get("source_only_validation_pass") is not True or negative.get("all_passed") is not True or audit.get("independent_audit_pass") is not True:
        raise SystemExit("Gate prerequisites are not exact true")
    gate = {
        "schema": "M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_SOURCE_FREEZE_GATE_V1",
        "artifact_id": "SIM13_M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_V1",
        "overall_status": GATE_CEILING,
        "source_freeze_tooling_pass": True,
        "source_artifact_count": len(validation["source_receipts"]),
        "source_validation_checks_passed": validation["checks_passed"],
        "source_validation_checks_total": validation["checks_total"],
        "negative_controls_passed": negative["controls_passed"],
        "negative_controls_total": negative["controls_total"],
        "independent_audit_pass": True,
        "contracts": _contract_receipts(),
        "evidence": [file_receipt(path) for path in required],
        "machine_policy_results": validation["machine_policy_results"],
        "status_enum": ["BOUND_DIGITAL", "DESIGN_CANDIDATE", "DIAGNOSTIC_ONLY", "OWNER_REQUIRED", "TEST_REQUIRED", "ABSENT"],
        "system_urdf_available": False,
        "current_system_bound": False,
        "physical_contact_ready": False,
        "dynamics_capture_entry_authorized": False,
        "next_stage_authorized": False,
        "generated_cad_step_mesh_urdf_fea_or_trajectory": False,
        "release_credit": False,
        "ceiling_note": "PASS covers only the source, contract, validator, audit and replay toolchain. It grants no dynamics/contact/current-system/release authority.",
    }
    write_canonical_json(GATE_PATH, gate)
    terminal = {
        "schema": "M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_SOURCE_FREEZE_TERMINAL_V1",
        "terminal_status": GATE_CEILING,
        "gate": file_receipt(GATE_PATH),
        "system_urdf_available": False,
        "current_system_bound": False,
        "physical_contact_ready": False,
        "dynamics_capture_entry_authorized": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    write_canonical_json(TERMINAL_PATH, terminal)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-source-evidence", action="store_true")
    parser.add_argument("--write-gate", action="store_true")
    args = parser.parse_args()
    if args.write_source_evidence == args.write_gate:
        parser.error("select exactly one write mode")
    if args.write_source_evidence:
        write_source_evidence()
    else:
        write_gate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
