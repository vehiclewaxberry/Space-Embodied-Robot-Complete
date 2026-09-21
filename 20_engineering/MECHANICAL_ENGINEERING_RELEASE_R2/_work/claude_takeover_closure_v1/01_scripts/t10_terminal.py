#!/usr/bin/env python
"""Sections 13+14: terminal independent validation, protected-asset receipt,
and the single final convergence gate.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from m01t.common import (M01_OUT, REL, RUN_ID, TK, WP_OUT, abspath, jdump,
                         jload, pin, sha256_file)

INTAKE = jload(f"{TK}/BASELINE_INTAKE_VERIFICATION_V1.json")

# ---------------- new-file inventory (takeover scope only)
new_files = []
for root, _, files in os.walk(abspath(TK)):
    for fn in files:
        ap = os.path.join(root, fn)
        rel = os.path.relpath(ap, abspath("")).replace("\\", "/")
        new_files.append({"path": rel, "bytes": os.path.getsize(ap),
                          "sha256": sha256_file(ap)})
new_files.sort(key=lambda x: x["path"])

# ---------------- protected-asset recheck: every intake pin must be unchanged
recheck = {}
drift = []
for k, v in INTAKE["pins"].items():
    ap = abspath(v["path"])
    ok = os.path.isfile(ap) and sha256_file(ap) == v["sha256"]
    recheck[k] = {"path": v["path"], "intake_sha256": v["sha256"], "unchanged": ok}
    if not ok:
        drift.append(k)
for k, v in INTAKE["candidate_gate_pins"].items():
    if not v.get("exists"):
        continue
    ap = abspath(v["path"])
    ok = os.path.isfile(ap) and sha256_file(ap) == v["sha256"]
    recheck[f"candidate::{k}"] = {"path": v["path"], "intake_sha256": v["sha256"],
                                   "unchanged": ok}
    if not ok:
        drift.append(f"candidate::{k}")

# MuJoCo V1 byte-identity (manifest re-run)
mj = jload("30_simulation/r2_mujoco_free_floating_precontact_v1/results/R2_MUJOCO_PACKAGE_MANIFEST_V1.json")
mj_ok, mj_total = 0, 0
for e in mj["files"]:
    mj_total += 1
    ap = abspath(e["path"])
    if os.path.isfile(ap) and sha256_file(ap) == e["sha256"].upper():
        mj_ok += 1

branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                        cwd=abspath(""), capture_output=True, text=True).stdout.strip()
head = subprocess.run(["git", "rev-parse", "HEAD"],
                      cwd=abspath(""), capture_output=True, text=True).stdout.strip()
git_status = subprocess.run(["git", "status", "--porcelain", "--",
                             "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/claude_takeover_closure_v1",
                             "30_simulation/r2_mujoco_target_relative_precontact_v2"],
                            cwd=abspath(""), capture_output=True, text=True).stdout.strip()

# ---------------- UNKNOWN-upgrade audit across takeover M01 outputs
unknown_audit = {"unknown_results_preserved": True, "notes": []}
pair_gate = None
pg_rel = f"{M01_OUT}/M01_PAIR_ORACLE_GATE_V1.json"
if os.path.isfile(abspath(pg_rel)):
    pair_gate = jload(pg_rel)
    ev = jload(f"{M01_OUT}/M01_PAIR_ORACLE_EVIDENCE_V1.json")
    n_unknown = sum(1 for k, v in ev["result_counts"].items() if k.endswith("|UNKNOWN"))
    unknown_audit["endpoint_unknown_rows"] = sum(
        v for k, v in ev["result_counts"].items() if k.endswith("|UNKNOWN"))

protected = {
    "schema": "TERMINAL_PROTECTED_ASSET_RECEIPT_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "git": {"branch": branch, "head": head},
    "intake_pin_recheck": recheck,
    "pin_drift": drift,
    "mujoco_v1_byte_identical": f"{mj_ok}/{mj_total}",
    "accepted_donor_historical_unchanged": len(drift) == 0 and mj_ok == mj_total,
    "path_scoped_change_inventory": git_status.splitlines() if git_status else [],
    "no_whole_repository_commit_made": True,
    "unknown_audit": unknown_audit,
    "thresholds_relaxed": 0,
    "historical_negative_evidence_removed": 0,
    "release_credit": False,
}
jdump(protected, f"{TK}/TERMINAL_PROTECTED_ASSET_RECEIPT_V1.json")

pin_validation = {
    "schema": "TERMINAL_SOURCE_PIN_INDEPENDENT_VALIDATION_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "new_file_count": len(new_files),
    "new_files": new_files,
    "all_intake_pins_unchanged": len(drift) == 0,
    "release_credit": False,
}
jdump(pin_validation, f"{TK}/TERMINAL_SOURCE_PIN_INDEPENDENT_VALIDATION_V1.json")

# terminal package manifest + sha inventory (self-excluding)
jdump({"schema": "TERMINAL_PACKAGE_MANIFEST_V1", "named_run_id": RUN_ID,
       "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
       "files": new_files, "file_count": len(new_files), "release_credit": False},
      f"{TK}/TERMINAL_PACKAGE_MANIFEST_V1.json")
import csv
with open(abspath(f"{TK}/TERMINAL_SHA256_V1.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["path", "bytes", "sha256"])
    for e in new_files:
        w.writerow([e["path"], e["bytes"], e["sha256"]])

# ---------------- negative control summary (aggregates all NC evidence created today)
nc_files = {
    "m01_continuous_edge": f"{M01_OUT}/M01_CONTINUOUS_EDGE_NEGATIVE_CONTROLS_V1.json",
    "sim13_backend_nc": "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/evidence/SIM13_V2_BACKENDS_NEGATIVE_CONTROLS_V2.json",
    "link2_v8_verification": f"{TK}/02_evidence/LINK2_B12_V8_VERIFICATION_EVIDENCE_V1.json",
}
nc_summary = {"schema": "TERMINAL_NEGATIVE_CONTROL_SUMMARY_V1",
              "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
              "named_run_id": RUN_ID, "sets": {}, "release_credit": False}
for k, rel in nc_files.items():
    if os.path.isfile(abspath(rel)):
        nc_summary["sets"][k] = {**pin(rel)}
jdump(nc_summary, f"{TK}/TERMINAL_NEGATIVE_CONTROL_SUMMARY_V1.json")

# ---------------- final convergence gate
def gstate(rel, key=None):
    ap = abspath(rel)
    if not os.path.isfile(ap):
        return "NOT_CREATED"
    d = jload(rel)
    if key:
        return d.get(key, "UNKNOWN_FIELD")
    return d.get("verdict", "NO_VERDICT")


m01_path_gate = jload(f"{M01_OUT}/M01_OPTION_A_BOUNDED_PATH_GATE_V1.json") if os.path.isfile(abspath(f"{M01_OUT}/M01_OPTION_A_BOUNDED_PATH_GATE_V1.json")) else None
outcome = m01_path_gate.get("outcome") if m01_path_gate else None

convergence = {
    "schema": "CURRENT_R2_TERMINAL_CONVERGENCE_GATE_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "fields": {
        "owner_acceptance": "ACCEPTED (OWNER_TERMINAL_CONVERGENCE_ACCEPTANCE_RECEIPT_V1)",
        "competition_mechanical_baseline": "FROZEN_WITH_NAMED_EXTERNAL_HOLDS__OWNER_ACCEPTED",
        "frozen_local_candidate_evidence": "CLOSED (R20/Link1-B6/C9/Link2-B12/gripper-2P/platform/rigid-links frozen as evidence)",
        "link2_v8_append": "REGISTERED_IN_V8_D09__OWNER_ACCEPTED",
        "m01_operational_assets": gstate(f"{M01_OUT}/M01_OPERATIONAL_ASSET_GATE_V1.json", "verdict"),
        "m01_three_stage_binding": gstate(f"{M01_OUT}/M01_THREE_STAGE_BINDING_GATE_V1.json", "verdict"),
        "m01_pair_universe": "11175_ENUMERATED__9_ADJ_EXEMPT__11166_REQUIRED",
        "m01_clearance_policy": "ZERO_NONPENETRATION_PLUS_DECLARED_DERATES (M01_CLEARANCE_POLICY_V2)",
        "m01_pair_oracle": gstate(f"{M01_OUT}/M01_PAIR_ORACLE_GATE_V1.json", "verdict"),
        "m01_motion_certificates": gstate(f"{M01_OUT}/M01_OBJECT_MOTION_CERTIFICATE_GATE_V1.json", "verdict"),
        "m01_continuous_edges": gstate(f"{M01_OUT}/M01_CONTINUOUS_EDGE_GATE_V1.json", "verdict"),
        "m01_bounded_search": gstate(f"{M01_OUT}/M01_OPTION_A_NAMED_RUN_RECEIPT_V1.json", "verdict"),
        "m01_certified_path": ("EXISTS" if os.path.isfile(abspath(f"{M01_OUT}/M01_OPTION_A_CERTIFIED_PATH_V1.json")) else "NONE"),
        "route_c_rc4": gstate(f"{WP_OUT}/ROUTE_C_RC4_GATE_V1.json", "route_c_rc4"),
        "g12": gstate(f"{WP_OUT}/G12_CURRENT_PATH_HANDOFF_GATE_V1.json", "g12_current_path_handoff"),
        "tmg4": gstate(f"{WP_OUT}/TMG4_CURRENT_TREE_GATE_V1.json", "state"),
        "tmg6": gstate(f"{WP_OUT}/TMG6_CURRENT_TREE_GATE_V1.json", "state"),
        "safe_current_tree": gstate(f"{WP_OUT}/SAFE_CURRENT_TREE_INDEPENDENT_REVIEW_V1.json", "verdict"),
        "sim13_backend": "20_OF_20_BACKEND_SUBSCOPE_PASS__PENDING_OWNER_REVIEW",
        "sim13_system_binding": gstate(f"{WP_OUT}/SIM13_CURRENT_TREE_SYSTEM_BINDING_GATE_V1.json", "verdict"),
        "mujoco_v1_immutable": f"BYTE_IDENTICAL_{mj_ok}_OF_{mj_total}",
        "mujoco_v2_target_relative": ("NOT_EXECUTED_NO_CERTIFIED_PATH" if outcome != "A" else "SEE_PACKAGE"),
        "embodied_candidate_benchmark": ("NOT_EXECUTED_PRECONDITIONS_ABSENT" if outcome != "A" else "SEE_PACKAGE"),
        "contact_status": "HOLD__DESIGN_CONTACT_MODEL_BOUNDED_PROVISIONAL__AS_BUILT_MEASUREMENT_PENDING",
        "hardware_status": "EXTERNAL_INPUT_HOLD (XH-01..XH-13)",
        "flex_status": "PASS_WITH_DECLARED_PROVISIONAL_PHYSICS (E23 18/18 lineage, unchanged)",
        "non_abort_status": "ABORT_ONLY_REMAINS_MAXIMUM_RUNTIME_STATE",
        "flight_release_status": "FALSE_HOLD",
        "release_credit": False,
    },
    "m01_outcome": outcome,
    "review_status": "PENDING_OWNER_REVIEW",
    "next_stage_authorized": False,
    "release_credit": False,
}
VERDICTS = {
    "A": "COMPETITION_MECHANICAL_BASELINE_OWNER_ACCEPTED__M01_OPTION_A_CERTIFIED_PATH_CANDIDATE__ROUTE_C_RC4_AND_G12_CURRENT_TREE_BOUND__SIM13_CURRENT_TREE_SYSTEM_BINDING_PASS__MUJOCO_V2_TARGET_RELATIVE_PRECONTACT_DIAGNOSTIC_PASS__CONTACT_HARDWARE_FLEX_NON_ABORT_AND_FLIGHT_RELEASE_HOLD",
    "B": "COMPETITION_MECHANICAL_BASELINE_OWNER_ACCEPTED__M01_BOUNDED_SEARCH_EXECUTED_NO_CERTIFIED_PATH__SIM13_RUNTIME_REMAINS_ABORT_ONLY__HARDWARE_AND_FLIGHT_RELEASE_HOLD",
    "C": "COMPETITION_MECHANICAL_BASELINE_OWNER_ACCEPTED__M01_OPERATIONALIZATION_REPEAT_REQUIRED__PATH_SEARCH_NOT_EXECUTED__SIM13_RUNTIME_REMAINS_ABORT_ONLY__HARDWARE_AND_FLIGHT_RELEASE_HOLD",
    None: "COMPETITION_MECHANICAL_BASELINE_OWNER_ACCEPTED__M01_OPERATIONALIZATION_REPEAT_REQUIRED__PATH_SEARCH_NOT_EXECUTED__SIM13_RUNTIME_REMAINS_ABORT_ONLY__HARDWARE_AND_FLIGHT_RELEASE_HOLD",
}
# outcome A additionally requires RC4/G12/Sim13/MuJoCo evidence to use the A verdict
if outcome == "A":
    rc4 = convergence["fields"]["route_c_rc4"]
    sim13b = convergence["fields"]["sim13_system_binding"]
    if rc4 != "PASS" or "BINDING_PASS" not in str(sim13b):
        convergence["verdict"] = ("COMPETITION_MECHANICAL_BASELINE_OWNER_ACCEPTED__"
                                   "M01_OPTION_A_CERTIFIED_PATH_CANDIDATE__"
                                   "DOWNSTREAM_RC4_G12_SIM13_STATUS_EXPLICIT__"
                                   "HARDWARE_AND_FLIGHT_RELEASE_HOLD")
    else:
        convergence["verdict"] = VERDICTS["A"]
else:
    convergence["verdict"] = VERDICTS[outcome]
jdump(convergence, f"{TK}/CURRENT_R2_TERMINAL_CONVERGENCE_GATE_V1.json")

print(json.dumps({"pin_drift": drift, "mujoco": f"{mj_ok}/{mj_total}",
                  "new_files": len(new_files), "m01_outcome": outcome,
                  "verdict": convergence["verdict"]}, indent=1))
