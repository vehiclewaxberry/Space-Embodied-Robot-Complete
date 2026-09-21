from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import datetime
from pathlib import Path

import psutil


ROOT = Path(__file__).resolve().parents[1]
S01 = ROOT / "07_VERIFICATION/AUTONOMOUS/S01"
CLOSURE = ROOT / "09_DELIVERY/B51R1_AUTONOMOUS_G1A_CLOSURE_20260801"
STAGE_A = ROOT / "02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT"
FINAL = ROOT / "02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2.SLDPRT"
STAGE_A_SHA = "5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B"


def now() -> str:
    return datetime.now().astimezone().isoformat()


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def record(path: Path, role: str) -> dict:
    return {"path": rel(path), "bytes": path.stat().st_size, "sha256": sha(path), "role": role}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


receipts = [
    S01 / "B51R1_S01_SESSION_EXECUTION_RECEIPT.json",
    S01 / "B51R1_SR01_SESSION_EXECUTION_RECEIPT.json",
    S01 / "B51R1_SR02_SESSION_EXECUTION_RECEIPT.json",
]
for receipt in receipts:
    if not receipt.is_file() or read_json(receipt)["status"] != "S01_FAIL_CLOSED":
        raise RuntimeError(f"Missing or non-failed session receipt: {receipt}")
if sha(STAGE_A) != STAGE_A_SHA:
    raise RuntimeError("Protected Stage A hash mismatch")
if FINAL.exists():
    raise RuntimeError("Final skeleton unexpectedly exists")
if any(path.is_file() for folder in [S01 / "WORK", S01 / "WORK_SR01", S01 / "WORK_SR02"] for path in folder.rglob("*")):
    raise RuntimeError("A recovery work directory contains unexpected files")
sw = [p.info for p in psutil.process_iter(["pid", "name"]) if (p.info.get("name") or "").lower() == "sldworks.exe"]
if sw:
    raise RuntimeError("SolidWorks still running during automatic-stop finalization")

incident_path = S01 / "B51R1_S01_AUTOMATIC_STOP_INCIDENT.json"
incident = {
    "schema": "B51R1_S01_AUTOMATIC_STOP_INCIDENT_V1",
    "generated_at": now(),
    "status": "FAIL_CLOSED_AUTOMATIC_STOP_TWO_DISTINCT_RECOVERY_METHODS_EXHAUSTED",
    "primary_session": "S01",
    "recovery_sessions": ["SR01", "SR02"],
    "root_cause_class": "SOLIDWORKS_2024_COM_ROT_ACTIVATION_OR_STARTUP_RESPONSIVENESS",
    "observed_failures": [
        {"session": "S01", "route": "POWERSHELL_COM_ACTIVATION", "error": "0x8002802B_TYPE_E_ELEMENTNOTFOUND"},
        {"session": "SR01", "route": "DIRECT_EXECUTABLE_THEN_POWERSHELL_ROT_ATTACH", "error": "0x8002802B_TYPE_E_ELEMENTNOTFOUND"},
        {"session": "SR02", "route": "DIRECT_EXECUTABLE_THEN_CSHARP_INTERNAL_ATTACH", "error": "VISIBLE_WINDOW_NOT_RESPONSIVE_WITHIN_30_SECONDS_BUILDER_NOT_ENTERED"},
    ],
    "session_receipts": [record(path, "IMMUTABLE_FAILED_SESSION_RECEIPT") for path in receipts],
    "candidate_work_files_created": 0,
    "final_skeleton_exists": False,
    "s01_gate_pass_receipt_exists": False,
    "protected_stage_a": record(STAGE_A, "PROTECTED_STAGE_A_UNCHANGED"),
    "solidworks_process_count_after_graceful_close": 0,
    "force_termination_used": False,
    "graceful_close_main_window_used": True,
    "automatic_stop_rule": "REPEATED_TOOL_FAILURE_AFTER_TWO_DISTINCT_RECOVERY_METHODS",
    "required_external_state_change": "USER_CLEARS_SOLIDWORKS_RECOVERY_OR_REGISTRATION_DIALOG_AND_EXPLICITLY_REOPENS_RECOVERY_POOL",
    "claim_limit": "G1A_G1B_REMAIN_PASS_S01_HOLD_NATIVE_CAD_NOT_CREATED",
}
write_json(incident_path, incident)

gate_path = S01 / "B51R1_S01_GATE_RECEIPT.json"
gate = {
    "schema": "B51R1_S01_GATE_RECEIPT_V1",
    "generated_at": now(),
    "status": "S01_HOLD_AUTOMATIC_STOP_COM_ROT_ACTIVATION_FAILURE",
    "gate": "S01",
    "pass": False,
    "next_session_authorized": False,
    "incident": record(incident_path, "AUTOMATIC_STOP_INCIDENT"),
    "g1b_sha256": "FF33C4FEC8B48C0B759C2BB9E6EA202E89B10DC4789B6385FC15841338276EE6",
    "input_lock_sha256": "AE4FF6021E837651CA019B7ABE8E84B4D0F92183CF158312DF7F826871A3F214",
    "native_target": {"path": rel(FINAL), "exists": False},
    "protected_stage_a_sha256": STAGE_A_SHA,
    "h10": "0_OF_28",
    "t005": "A_B_C_NOT_RUN",
    "claim_limit": "NO_S01_PASS_NO_S02_ADMISSION",
}
write_json(gate_path, gate)

ledger_path = CLOSURE / "B51R1_AUTONOMOUS_SESSION_POOL_LEDGER.json"
ledger = read_json(ledger_path)
ledger["status"] = "BLOCKED_AUTOMATIC_STOP_TWO_RECOVERY_METHODS_EXHAUSTED"
ledger["remaining"] = ledger["budget"] - ledger["consumed_since_activation"]
ledger["automatic_stop_incident"] = record(incident_path, "S01_AUTOMATIC_STOP")
ledger["next_session_authorized"] = False
ledger["updated_at"] = now()
write_json(ledger_path, ledger)

composition_path = CLOSURE / "B51R1_PHASE2_CURRENT_GATE_COMPOSITION.json"
composition = read_json(composition_path)
composition["generated_at"] = now()
composition["status"] = "G1A_G1B_PASS_S01_HOLD_AUTOMATIC_STOP"
composition["s01"] = {
    "status": gate["status"],
    "receipt": record(gate_path, "S01_HOLD_GATE_RECEIPT"),
    "native_target_exists": False,
    "next_session_authorized": False,
}
composition["solidworks_process_count"] = 0
composition["claim_limit"] = "G1A_G1B_PASS_ONLY_S01_HOLD_NATIVE_CAD_NOT_CREATED_H10_0_OF_28_T005_NOT_RUN"
write_json(composition_path, composition)

index_path = S01 / "B51R1_S01_AUTOMATIC_STOP_INDEX.json"
index_items = receipts + [incident_path, gate_path, ledger_path, composition_path, ROOT / "08_REVIEWS/B51R1_Run_Autonomous_S01.ps1", ROOT / "08_REVIEWS/B51R1_S01_MasterSkeletonFinalizer.cs", ROOT / "08_REVIEWS/B51R1_S01_MasterSkeletonFinalizer.dll"]
index = {
    "schema": "B51R1_S01_AUTOMATIC_STOP_INDEX_V1",
    "generated_at": now(),
    "status": "S01_HOLD_EVIDENCE_COMPLETE",
    "self_included": False,
    "items": [record(path, "S01_STOP_EVIDENCE") for path in index_items],
}
write_json(index_path, index)
(index_path.with_suffix(index_path.suffix + ".sha256")).write_text(sha(index_path) + "\n", encoding="utf-8", newline="\n")

zip_path = ROOT / "09_DELIVERY/B51R1_S01_AUTOMATIC_STOP_PACKAGE_20260802.zip"
if zip_path.exists():
    raise RuntimeError(f"Refusing to overwrite incident ZIP: {zip_path}")
with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in index_items + [index_path, index_path.with_suffix(index_path.suffix + ".sha256")]:
        archive.write(path, rel(path))
(zip_path.with_suffix(zip_path.suffix + ".sha256")).write_text(sha(zip_path) + "\n", encoding="utf-8", newline="\n")

print(json.dumps({
    "status": "S01_HOLD_AUTOMATIC_STOP_EVIDENCE_PACKAGED",
    "incident_sha256": sha(incident_path),
    "gate_receipt_sha256": sha(gate_path),
    "index_sha256": sha(index_path),
    "package": rel(zip_path),
    "package_sha256": sha(zip_path),
    "stage_a_unchanged": True,
    "final_skeleton_exists": False,
    "solidworks_process_count": 0,
}, ensure_ascii=False, indent=2))
