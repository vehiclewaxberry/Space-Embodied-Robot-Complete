"""Read-only validator for the frozen M7-to-Sim13 admission package."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from independent_audit_mechanical_evidence_admission import build_audit
from mechanical_admission.evaluator import GATE_CEILING, evaluate_default_snapshot, validate_publication_candidate
from mechanical_admission.freeze_support import canonical_json_bytes, file_receipt, source_inventory
from mechanical_admission.negative_controls import run_negative_controls
from mechanical_admission.strict_io import AdmissionError, strict_json_bytes


EVIDENCE_DIR = PACKAGE_ROOT / "evidence"
RESULTS_DIR = PACKAGE_ROOT / "results"
VALIDATION_PATH = EVIDENCE_DIR / "M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_VALIDATION_V1.json"
NC_PATH = EVIDENCE_DIR / "M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_NEGATIVE_CONTROLS_V1.json"
MANIFEST_PATH = EVIDENCE_DIR / "M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_SOURCE_MANIFEST_V1.json"
AUDIT_PATH = EVIDENCE_DIR / "M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_INDEPENDENT_AUDIT_V1.json"
GATE_PATH = RESULTS_DIR / "M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_SOURCE_FREEZE_GATE_V1.json"
TERMINAL_PATH = RESULTS_DIR / "M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_SOURCE_FREEZE_TERMINAL_V1.json"
MANDATORY_FALSE = (
    "system_urdf_available",
    "current_system_bound",
    "physical_contact_ready",
    "dynamics_capture_entry_authorized",
    "next_stage_authorized",
)


def _read_json(path: Path):
    return strict_json_bytes(path.read_bytes())


def _exact(path: Path, expected) -> bool:
    return path.read_bytes() == canonical_json_bytes(expected)


def validate() -> dict:
    evaluation = evaluate_default_snapshot()
    validate_publication_candidate(evaluation)
    negative = run_negative_controls()
    audit = build_audit()
    manifest = {
        "schema": "M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_SOURCE_MANIFEST_V1",
        "artifact_id": "SIM13_M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_V1",
        "inventory_scope": "PACKAGE_SOURCES_ONLY__EVIDENCE_RESULTS_AND_CACHES_EXCLUDED",
        "files": source_inventory(),
        "file_count": len(source_inventory()),
        "generated_mechanical_or_physics_artifacts": False,
    }
    checks = {
        "validation_exact_replay": VALIDATION_PATH.is_file() and _exact(VALIDATION_PATH, evaluation),
        "negative_controls_exact_replay": NC_PATH.is_file() and _exact(NC_PATH, negative),
        "source_manifest_exact_replay": MANIFEST_PATH.is_file() and _exact(MANIFEST_PATH, manifest),
        "independent_audit_exact_replay": AUDIT_PATH.is_file() and _exact(AUDIT_PATH, audit),
    }
    admission_contract = _read_json(PACKAGE_ROOT / "contracts" / "MECHANICAL_EVIDENCE_ADMISSION_CONTRACT_V1.json")
    nc_contract = _read_json(PACKAGE_ROOT / "contracts" / "MECHANICAL_EVIDENCE_NEGATIVE_CONTROL_CONTRACT_V1.json")
    checks["admission_contract_semantics_exact"] = (
        admission_contract.get("gate_ceiling") == GATE_CEILING
        and admission_contract.get("allowed_evidence_statuses") == ["BOUND_DIGITAL", "DESIGN_CANDIDATE", "DIAGNOSTIC_ONLY", "OWNER_REQUIRED", "TEST_REQUIRED", "ABSENT"]
        and admission_contract.get("mandatory_false_outputs") == list(MANDATORY_FALSE)
        and admission_contract.get("topology_contract", {}).get("total_links") == 19
        and admission_contract.get("topology_contract", {}).get("joints") == 18
        and admission_contract.get("topology_contract", {}).get("physical_links") == 16
        and admission_contract.get("topology_contract", {}).get("frame_only_links") == 3
        and admission_contract.get("topology_contract", {}).get("actuated_dof") == 8
    )
    checks["negative_control_contract_exact"] = [item.get("id") for item in nc_contract.get("controls", ())] == [f"NC{i:02d}" for i in range(1, 17)]
    if not GATE_PATH.is_file() or not TERMINAL_PATH.is_file():
        checks["gate_and_terminal_exist"] = False
        return {"pass": False, "checks": checks}
    gate = _read_json(GATE_PATH)
    terminal = _read_json(TERMINAL_PATH)
    checks["gate_schema_and_ceiling"] = gate.get("schema") == "M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_SOURCE_FREEZE_GATE_V1" and gate.get("overall_status") == GATE_CEILING
    checks["gate_evidence_receipts_exact"] = gate.get("evidence") == [file_receipt(path) for path in (VALIDATION_PATH, NC_PATH, MANIFEST_PATH, AUDIT_PATH)]
    checks["gate_contract_receipts_exact"] = gate.get("contracts") == [
        file_receipt(PACKAGE_ROOT / "contracts" / name)
        for name in (
            "MECHANICAL_EVIDENCE_ADMISSION_CONTRACT_V1.json",
            "MECHANICAL_EVIDENCE_SOURCE_BINDINGS_V1.json",
            "MECHANICAL_EVIDENCE_NEGATIVE_CONTROL_CONTRACT_V1.json",
        )
    ]
    checks["terminal_binds_gate_exact"] = terminal.get("gate") == file_receipt(GATE_PATH) and terminal.get("terminal_status") == GATE_CEILING
    checks["mandatory_false_everywhere"] = all(gate.get(field) is False and terminal.get(field) is False and evaluation.get(field) is False and audit.get(field) is False for field in MANDATORY_FALSE)
    checks["source_counts_exact"] = gate.get("source_artifact_count") == 27 and gate.get("negative_controls_passed") == gate.get("negative_controls_total") == 16
    checks["no_generated_mechanical_or_physics_assets"] = gate.get("generated_cad_step_mesh_urdf_fea_or_trajectory") is False and manifest["generated_mechanical_or_physics_artifacts"] is False
    return {
        "schema": "M7_TO_SIM13_MECHANICAL_EVIDENCE_ADMISSION_SOURCE_FREEZE_VALIDATOR_V1",
        "pass": all(checks.values()),
        "status": "PASS_READ_ONLY_VALIDATION" if all(checks.values()) else "FAIL_READ_ONLY_VALIDATION",
        "checks": checks,
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
    }


def main() -> int:
    try:
        result = validate()
    except (AdmissionError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"validator=FAIL error={exc}")
        return 1
    print(f"validator={result['status']} checks={result['checks_passed']}/{result['checks_total']}")
    if not result["pass"]:
        print("failed_checks=" + ",".join(name for name, passed in result["checks"].items() if not passed))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
