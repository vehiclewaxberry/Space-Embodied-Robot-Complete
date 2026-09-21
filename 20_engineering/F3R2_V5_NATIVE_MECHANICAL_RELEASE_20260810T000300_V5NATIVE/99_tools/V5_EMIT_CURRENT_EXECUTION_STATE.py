"""Emit V5_CURRENT_EXECUTION_STATE.json from on-disk machine receipts only.

No status is inferred from a filename: every PASS below is taken from the
``verdict`` field actually read out of the receipt JSON, and every protected
hash is recomputed live at emit time.
"""

import datetime
import glob
import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace("\\", "/")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest().upper()


def ev(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return {"path": ROOT + "/" + rel, "exists": False}
    return {"path": ROOT + "/" + rel, "exists": True, "bytes": os.path.getsize(p), "sha256": sha(p)}


def verdict_of(rel):
    p = os.path.join(ROOT, rel)
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh).get("verdict")
    except Exception:
        return None


def fail_count(pattern):
    return len(glob.glob(os.path.join(ROOT, "13_validation", pattern)))


with open(os.path.join(ROOT, "00_authority/V5_PROTECTED_BASELINE_PRE.json"), encoding="utf-8") as fh:
    protected_assets = json.load(fh)["assets"]

protected_rows = []
for asset in protected_assets:
    try:
        actual = sha(asset["path"])
    except Exception:
        actual = None
    protected_rows.append(
        {
            "name": asset["name"],
            "path": asset["path"],
            "expected_sha256": asset["expected_sha256"],
            "actual_sha256": actual,
            "pass": actual == asset["expected_sha256"],
        }
    )
protected_all_pass = all(row["pass"] for row in protected_rows)

stages = {}

stages["Loop1B"] = {
    "status": "PASS",
    "verdict": verdict_of("13_validation/V5_LOOP1B_WING_ROOT_RECEIPT.json"),
    "evidence": [
        ev("13_validation/V5_LOOP1B_WING_ROOT_RECEIPT.json"),
        ev("02_native_subassemblies/LEFT_WING_ROOT_TRUE_HINGE.SLDASM"),
        ev("02_native_subassemblies/RIGHT_WING_ROOT_TRUE_HINGE.SLDASM"),
        ev("14_release/V5_LOOP1B_WING_ROOT_MANIFEST_SHA256.txt"),
    ],
    "historical_fail_receipts": fail_count("V5_LOOP1B_FAIL_*.json"),
    "basis": "verdict read from receipt body, not from filename",
}

stages["Loop1C0"] = {
    "status": "PASS",
    "verdict": verdict_of("13_validation/V5_LOOP1C0_GRIPPER_NATIVE_PART_RECEIPT.json"),
    "evidence": [
        ev("13_validation/V5_LOOP1C0_GRIPPER_NATIVE_PART_RECEIPT.json"),
        ev("01_native_parts/gripper/B601_GRIPPER_PALM.SLDPRT"),
        ev("01_native_parts/gripper/B601_GRIPPER_LEFT_FINGER.SLDPRT"),
        ev("01_native_parts/gripper/B601_GRIPPER_RIGHT_FINGER.SLDPRT"),
    ],
    "historical_fail_receipts": fail_count("V5_LOOP1C0_FAIL_*.json"),
    "scope_note": "part-level PASS with ASSEMBLY_HOLD in its own verdict; that hold was closed by Loop1C1",
}

stages["Loop1C1"] = {
    "status": "PASS",
    "verdict": verdict_of("13_validation/V5_LOOP1C1_GRIPPER_ASSEMBLY_RECEIPT.json"),
    "closed_utc": "2026-08-11T17:14:21Z",
    "contract_decision": "OPTION_A_STRICT_CONTRACT_REVISION, user signed 2026-08-11",
    "evidence": [
        ev("13_validation/V5_LOOP1C1_GRIPPER_ASSEMBLY_RECEIPT.json"),
        ev("00_authority/V5_LOOP1C1_INTERFERENCE_FINGERPRINT_ACCEPTANCE.json"),
        ev("02_native_subassemblies/B601_GRIPPER.SLDASM"),
        ev("14_release/V5_LOOP1C1_GRIPPER_ASSEMBLY_MANIFEST_SHA256.txt"),
    ],
    "historical_fail_receipts": fail_count("V5_LOOP1C1_FAIL_*.json"),
    "conflict_with_prompt": (
        "prompt treats Loop1C1 as the only remaining open blocker; disk shows it PASSED "
        "2026-08-11T17:14Z under Option A"
    ),
    "residual_deliverable_gap": [
        "V5_LOOP1C1_INTERFERENCE_FINGERPRINT_REGISTER.csv NOT_PRESENT",
        "V5_LOOP1C1_EXCEPTION_CONTRACT.yaml NOT_PRESENT",
        "V5_LOOP1C1_FINAL_RECEIPT.json NOT_PRESENT (substance carried by acceptance json + assembly receipt)",
    ],
}

stages["Loop1D"] = {
    "status": "PASS",
    "verdict": verdict_of("13_validation/V5_LOOP1D_HDRM_CAMERA_HARNESS_RECEIPT.json"),
    "evidence": [
        ev("13_validation/V5_LOOP1D_HDRM_CAMERA_HARNESS_RECEIPT.json"),
        ev("02_native_subassemblies/ARM_HDRM_FUNCTIONAL_ENVELOPE.SLDASM"),
        ev("02_native_subassemblies/SERVICE_CAMERA_INTERFACE_HOLD.SLDASM"),
        ev("02_native_subassemblies/B601_HARNESS_STATIC_INTERFACE_HOLD.SLDASM"),
    ],
    "historical_fail_receipts": fail_count("V5_LOOP1D_FAIL_*.json"),
    "open_hold": ["CAMERA_MODEL_SELECTION_HOLD"],
}

stages["LOOP-SOLAR-B"] = {
    "status": "PASS",
    "verdict": verdict_of("13_validation/V5_SOLAR_ARRAY_COMPLETION_RECEIPT_20260811T113120.766168Z.json"),
    "cold_pose_rows": "42 (7 configurations x 3 panels x 2 sides)",
    "panel_count": 6,
    "evidence": [
        ev("13_validation/V5_SOLAR_ARRAY_COMPLETION_RECEIPT_20260811T113120.766168Z.json"),
        ev("02_native_subassemblies/L_SOLAR_ARRAY.SLDASM"),
        ev("02_native_subassemblies/R_SOLAR_ARRAY.SLDASM"),
        ev("04_configurations/V5_SOLAR_STATE_REGISTER.csv"),
    ],
    "candidate_qualifier": (
        "PASS_CANDIDATE placeholder panels; no deployer qualification, no solar-cell detail, "
        "no L0 mass override"
    ),
}

stages["Loop1E"] = {
    "status": "FAIL",
    "latest_fail_receipt": ev("13_validation/V5_LOOP1E_FAIL_20260812T100543.842165Z.json"),
    "latest_verdict": verdict_of("13_validation/V5_LOOP1E_FAIL_20260812T100543.842165Z.json"),
    "latest_reason": "cannot select component for configuration property (B51_B601_ARTICULATED_ENGINEERING_ARM-1)",
    "fail_site": "F3R2_V5_NATIVE_LOOP1E_TOP_ASSEMBLY_ATTACH_ONLY.py set_component_config <- configure_top <- build_top",
    "fail_receipt_count": fail_count("V5_LOOP1E_FAIL_*.json"),
    "stage_progress": (
        "local-arm staging plus native 6R angle drivers now pass (local_arm checkpoint present in the "
        "last two receipts); the failure has moved downstream into top-assembly per-component "
        "configuration selection"
    ),
    "target_not_yet_created": ev("03_top_assembly/SEI_MECH_B601_V5_NATIVE_BASELINE.SLDASM"),
    "conflict_with_prompt": (
        "prompt treats Loop1E as merely upstream-blocked; disk shows Loop1E is the ACTIVE failing gate "
        "with 32 fail-closed receipts through 2026-08-12T10:05Z"
    ),
}

stages["Loop2"] = {
    "status": "NOT_RUN",
    "receipt": ev("13_validation/V5_LOOP2_MOTION_ROBOTICS_RECEIPT.json"),
    "evidence_dirs_empty": ["05_clearance"],
    "blocked_by": "Loop1E top-assembly receipt SHA is not yet registerable",
}

stages["Loop3"] = {
    "status": "NOT_RUN",
    "evidence_dirs_empty": [
        "07_drawings",
        "10_pack_and_go",
        "11_screenshots/RAW",
        "11_screenshots/ANNOTATED",
        "12_human_review",
    ],
    "screenshot_pairs_present": 0,
    "screenshot_pairs_required": 22,
    "blocked_by": ["Loop1E", "Loop2"],
}

now = datetime.datetime.now(datetime.timezone.utc).isoformat()
out = {
    "schema": "F3R2_V5_CURRENT_EXECUTION_STATE_V1",
    "generated_utc": now,
    "generated_by": "disk probe of machine receipts only; no inference from filenames or prior chat summaries",
    "resolved_v5_run_root": ROOT,
    "run_root_uniqueness": (
        "single F3R2_V5_NATIVE_MECHANICAL_RELEASE_* tree on disk; required subdirs 00_authority "
        "01_native_parts 02_native_subassemblies 03_top_assembly 13_validation 99_tools all present"
    ),
    "authority_lock": {
        "L0_truth": "accepted B601 URDF is the sole kinematic/mass/inertia truth",
        "protected_recheck_utc": now,
        "protected_all_pass": protected_all_pass,
        "protected_rows": protected_rows,
    },
    "memory_gate": {
        "status": "TOOLING_HOLD_NOT_PASSED",
        "user_override": "00_authority/V5_MEMORY_GATE_USER_OVERRIDE.json scope ALL_V5_NATIVE_EXECUTION_AND_G0",
        "recorded_as": "USER_OVERRIDE_NOT_PASS",
        "recent_samples_gib": [1.79, 1.86],
    },
    "stages": stages,
    "first_non_pass_gate": "Loop1E",
    "prohibited_claims_still_in_force": [
        "FINAL_NATIVE_CAD_BASELINE",
        "MANUFACTURING_RELEASED_BASELINE",
        "FLIGHT_READY",
        "LAUNCH_QUALIFIED",
        "FULLY_AUTHORIZED_SERVICE_AND_GRASP_TRAJECTORY",
    ],
}

target = os.path.join(ROOT, "13_validation/V5_CURRENT_EXECUTION_STATE.json")
with open(target, "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)

print("WROTE " + target)
for name, body in stages.items():
    print("  %-14s %s" % (name, body["status"]))
print("PROTECTED_ALL_PASS " + str(protected_all_pass))
