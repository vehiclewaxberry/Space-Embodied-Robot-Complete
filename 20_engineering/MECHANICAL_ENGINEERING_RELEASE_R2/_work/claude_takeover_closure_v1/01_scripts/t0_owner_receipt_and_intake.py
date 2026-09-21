#!/usr/bin/env python
"""Terminal convergence T0: Owner acceptance receipt + baseline intake verification.

Deterministic, append-only. Recomputes every pin from disk. Any mismatch is
recorded and fails the intake gate (fail-closed); nothing pre-existing is
modified.
"""
import hashlib
import json
import os
import subprocess

ROOT = r"F:/China Graduate Future Flight Vehicle Innovation Competition"
REL = "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2"
TK = f"{REL}/_work/claude_takeover_closure_v1"
OUT = os.path.join(ROOT, TK)

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()

def pin(rel):
    ap = os.path.join(ROOT, rel.replace("/", os.sep))
    ok = os.path.isfile(ap)
    return {"path": rel, "exists": ok,
            "sha256": sha256(ap) if ok else None,
            "bytes": os.path.getsize(ap) if ok else None}

def jload(rel):
    with open(os.path.join(ROOT, rel.replace("/", os.sep)), encoding="utf-8") as f:
        return json.load(f)

def jdump(obj, rel):
    ap = os.path.join(ROOT, rel.replace("/", os.sep))
    with open(ap, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False, sort_keys=True)

# ---------------------------------------------------------------- git state
branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT,
                        capture_output=True, text=True).stdout.strip()
head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                      capture_output=True, text=True).stdout.strip()

# ---------------------------------------------------------------- pins
PINS = {
    "release_gate": f"{REL}/00_RELEASE_GATE.json",
    "takeover_index": f"{TK}/CURRENT_TAKEOVER_AUTHORITY_INDEX_V1.json",
    "authority_delta_v8": "01_project/competition/CURRENT_R2_AUTHORITY_DELTA_V8.json",
    "takeover_convergence_gate": f"{TK}/CURRENT_SYSTEM_TAKEOVER_CONVERGENCE_GATE_V1.json",
    "link2_v8_append_receipt": f"{TK}/LINK2_B12_V8_APPEND_RECEIPT_V1.json",
    "link2_package_gate": f"{REL}/_work/odr/ODR60_OPTION_A_ROUTE_C_R95_LINK2_B12_OPERATIONAL_COLLISION_CANDIDATE_V1/05_results/LOCAL_CANDIDATE_GATE_V1.json",
    "link2_verification_evidence": f"{TK}/02_evidence/LINK2_B12_V8_VERIFICATION_EVIDENCE_V1.json",
    "m01_prebind_gate": f"{REL}/_work/odr/ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1/M01_SCENE_AND_COLLISION_PREBIND_GATE_V1.json",
    "system_collision_registry": f"{REL}/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/M01_SYSTEM_COLLISION_REGISTRY_V1.json",
    "system_collision_registry_gate": f"{REL}/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/M01_SYSTEM_COLLISION_REGISTRY_GATE_V1.json",
    "pair_oracle_contract": f"{REL}/_work/odr/ODR60_OPTION_A_SYSTEM_BINDING_CONTRACT_V1/SYSTEM_PAIR_ORACLE_CONTRACT_V1.json",
    "pair_oracle_backend_contract": f"{REL}/_work/odr/ODR60_OPTION_A_M01_SYSTEM_PAIR_ORACLE_BACKEND_V1/M01_SYSTEM_PAIR_ORACLE_BACKEND_CONTRACT_V1.json",
    "scene_schema_v2": f"{REL}/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/M01_THREE_STAGE_SCENE_SCHEMA_V2.json",
    "scene_decision_intake": f"{REL}/_work/odr/ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1/M01_SCENE_DECISION_INTAKE_V1.yaml",
    "execution_mount_binding": f"{REL}/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/EXECUTION_MOUNT_BINDING_V1.json",
    "collision_frame_registration": f"{REL}/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/COLLISION_FRAME_REGISTRATION_V1.json",
    "owner_selection_option_a": f"{REL}/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/OWNER_SELECTION_RECORD_V1.json",
    "accepted_b601_urdf_ref": f"{REL}/05_ACCEPTED_B601_URDF_REF.yaml",
    "accepted_b601_urdf": "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
    "harness_mission_envelope": f"{REL}/12_HARNESS_MISSION_ENVELOPE.yaml",
    "mech_to_embodied_handoff": f"{REL}/17_MECH_TO_EMBODIED_HANDOFF_GATE.json",
    "route_c_rc1_gate": f"{REL}/route_c/ROUTE_C_PHYSICAL_INPUT_GATE_V1.json",
    "route_c_v9f_falsifier": f"{REL}/route_c/ROUTE_C_V9F_MANDATORY_M01_FALSIFIER_GATE.json",
    "route_c_v9f_ruling": f"{REL}/route_c/ROUTE_C_V9F_TERMINAL_RULING.json",
    "route_c_negative_quarantine": f"{REL}/_work/odr/ODR60_OPTION_A_M01_FIXED_PLATFORM_AND_BASE_MOTION_PRECERT_V1/ROUTE_C_NEGATIVE_WITNESS_QUARANTINE_V1.json",
    "sim13_20_of_20_gate": "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_20_OF_20_GATE_V1.json",
    "sim13_full_registry_evidence": "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/evidence/SIM13_V2_FULL_REGISTRY_20_OF_20_V2.json",
    "mech_rl_interface_v2": "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/interfaces/MECH_RL_SYSTEM_INTERFACE_V2.yaml",
    "sim13_addendum_gate": f"{REL}/_work/loop_b/sim13_post_terminal_handoff_addendum_v1/SIM13_POST_TERMINAL_HANDOFF_ADDENDUM_GATE_V1.json",
    "mujoco_v1_manifest": "30_simulation/r2_mujoco_free_floating_precontact_v1/results/R2_MUJOCO_PACKAGE_MANIFEST_V1.json",
    "mujoco_v1_reuse_receipt": "01_project/competition/MUJOCO_V1_IMMUTABLE_REUSE_RECEIPT.json",
}
pins = {k: pin(v) for k, v in PINS.items()}
missing = [k for k, v in pins.items() if not v["exists"]]

# frozen candidate package gates
CANDIDATE_GATES = {
    "R20_R121": f"{REL}/_work/odr/ODR60_OPTION_A_ROUTE_C_R121_OPERATIONAL_COLLISION_CANDIDATE_V1/05_results/LOCAL_CANDIDATE_GATE_V1.json",
    "LINK1_B6": f"{REL}/_work/odr/ODR60_OPTION_A_ROUTE_C_R101_LINK1_B6_OPERATIONAL_COLLISION_CANDIDATE_V1/05_results/LOCAL_CANDIDATE_GATE_V1.json",
    "LINK2_B12": f"{REL}/_work/odr/ODR60_OPTION_A_ROUTE_C_R95_LINK2_B12_OPERATIONAL_COLLISION_CANDIDATE_V1/05_results/LOCAL_CANDIDATE_GATE_V1.json",
    "C9": f"{REL}/_work/odr/ODR60_OPTION_A_ROUTE_C_C9_ANALYTIC_CAPSULE_CANDIDATE_V1/05_results/LOCAL_CANDIDATE_GATE_V1.json",
    "GRIPPER_2P": f"{REL}/_work/odr/ODR60_OPTION_A_B601_GRIPPER_2P_OPERATIONAL_PROXY_V1/05_results/LOCAL_CANDIDATE_GATE_V1.json",
    "FIXED_PLATFORM": f"{REL}/_work/odr/ODR60_OPTION_A_FIXED_PLATFORM_OPERATIONAL_COLLISION_CANDIDATE_V1/05_results/LOCAL_CANDIDATE_GATE_V1.json",
    "RIGID_LINKS": f"{REL}/_work/odr/ODR60_OPTION_A_B601_RIGID_LINK_OPERATIONAL_PROXY_V1/05_results/B601_RIGID_LINK_OPERATIONAL_PROXY_LOCAL_GATE_V1.json",
}
cand_pins = {}
for k, rel in CANDIDATE_GATES.items():
    ap = os.path.join(ROOT, rel.replace("/", os.sep))
    if not os.path.isfile(ap):
        # fallback: first *GATE_V1.json in 05_results
        resdir = os.path.join(os.path.dirname(os.path.dirname(ap)), )
        cand_pins[k] = {"path": rel, "exists": False}
        continue
    g = jload(rel)
    cand_pins[k] = {"path": rel, "exists": True, "sha256": sha256(ap),
                    "bytes": os.path.getsize(ap),
                    "verdict": g.get("verdict", "")[:120]}

# V8 contains exactly the Link2 addition
v8 = jload("01_project/competition/CURRENT_R2_AUTHORITY_DELTA_V8.json")
v8_adds = v8.get("authority_additions", [])
v8_link2_ok = (len(v8_adds) == 1
               and v8_adds[0].get("delta_id") == "D09_ROUTE_C_R95_LINK2_B12_LOCAL_OPERATIONAL_COLLISION_CANDIDATES"
               and v8_adds[0].get("sha256") == pins["link2_package_gate"]["sha256"])

# MuJoCo V1 byte-identity against its own manifest
mj_manifest = jload(PINS["mujoco_v1_manifest"])
mj_files = mj_manifest.get("files") or mj_manifest.get("entries") or []
mj_total, mj_match = 0, 0
mj_mismatch = []
for e in mj_files:
    rel = e.get("path") or e.get("file")
    want = (e.get("sha256") or "").upper()
    if not rel or not want:
        continue
    mj_total += 1
    ap = os.path.join(ROOT, rel.replace("/", os.sep))
    if os.path.isfile(ap) and sha256(ap) == want:
        mj_match += 1
    else:
        mj_mismatch.append(rel)

# Sim13 current state verification
s13 = jload(PINS["sim13_20_of_20_gate"])
s13_txt = json.dumps(s13)
sim13_20 = "20_OF_20" in s13_txt and "ABORT_ONLY" in s13_txt and s13.get("release_credit") is False

# historical negative preserved
v9f = jload(PINS["route_c_v9f_falsifier"])
v9f_txt = json.dumps(v9f)
hist_neg_ok = "-17.313396996697108" in v9f_txt

intake_checks = {
    "branch_is_publication_stage3": branch == "publication/stage3-integrity-closure",
    "head_matches_intake_5c5adde": head.startswith("5c5adde"),
    "all_core_pins_exist": len(missing) == 0,
    "v8_contains_exactly_valid_link2_addition": v8_link2_ok,
    "frozen_candidate_gates_present_7_of_7": sum(1 for v in cand_pins.values() if v.get("exists")) == 7,
    "mujoco_v1_manifest_files_byte_identical": mj_total > 0 and mj_match == mj_total,
    "sim13_backend_20_of_20_abort_only": sim13_20,
    "historical_v9f_negative_preserved": hist_neg_ok,
    "abort_only_max_runtime_authority": "ABORT_ONLY" in json.dumps(jload(PINS["release_gate"]).get("sim13_state", {})),
}
intake_pass = all(intake_checks.values())

# ---------------------------------------------------------------- owner receipt
receipt = {
    "schema": "OWNER_TERMINAL_CONVERGENCE_ACCEPTANCE_RECEIPT_V1",
    "generated_utc": "DETERMINISTIC_RECORD_NO_WALLCLOCK",
    "owner_tokens_recorded_verbatim": [
        "AUTHORIZE_OPTION_A_FIXED_ENDPOINT_M01_TRAJECTORY_SEARCH",
        "OWNER_ACCEPT_COMPETITION_MECHANICAL_BASELINE_WITH_NAMED_EXTERNAL_HOLDS",
        "AUTHORIZE_NAMED_RUN=R2_TERMINAL_CONVERGENCE_20260828_R1",
    ],
    "competition_mechanical_baseline_owner_accepted": True,
    "link2_v8_append_owner_accepted": True,
    "frozen_local_candidate_evidence_owner_accepted": True,
    "named_m01_run_authorized": True,
    "named_run_id": "R2_TERMINAL_CONVERGENCE_20260828_R1",
    "research_system_release": False,
    "hardware_release": False,
    "flight_release": False,
    "contact_valid": False,
    "capture_success": False,
    "non_abort_authorized": False,
    "release_credit": False,
    "acceptance_scope": [
        "accept competition digital mechanical baseline with named external engineering holds",
        "accept R20, Link1-B6, C9, Link2-B12, gripper 2P, fixed platform and rigid link proxy packages as frozen local evidence",
        "authorize production of L2 operational collision assets from frozen candidates",
        "authorize deterministic M01 pre-search construction",
        "authorize exactly one named bounded Option A path campaign after all pre-search machine conditions pass",
        "authorize Route-C RC-4 and G12 evaluation against the certified path",
        "authorize current-tree SAFE/Sim13 rebind and independent validation",
        "authorize a new MuJoCo V2 research package only after a certified M01 path candidate exists",
        "authorize offline candidate-generation benchmarking only",
    ],
    "not_permitted": [
        "editing accepted B601 or Unified R2",
        "editing donor CAD",
        "rewriting historical Gates",
        "changing existing thresholds",
        "forcing UNKNOWN to ALLOW",
        "claiming contact, capture, hardware, flight or release validity",
        "direct VLA torque/current/execution authority",
    ],
    "intake_pin_set_sha256": None,
    "review_status": "OWNER_ACCEPTANCE_RECORDED__EXECUTION_RESULTS_PENDING",
    "next_stage_authorized": False,
}
jdump(receipt, f"{TK}/OWNER_TERMINAL_CONVERGENCE_ACCEPTANCE_RECEIPT_V1.json")

intake = {
    "schema": "BASELINE_INTAKE_VERIFICATION_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "git": {"branch": branch, "head": head},
    "checks": intake_checks,
    "pins": pins,
    "candidate_gate_pins": cand_pins,
    "missing_pins": missing,
    "mujoco_v1_manifest": {"files_checked": mj_total, "files_match": mj_match,
                           "mismatches": mj_mismatch},
    "broad_audit_superseded": "existing takeover index reused; no new broad authority index created",
    "intake_pass": intake_pass,
    "verdict": ("BASELINE_INTAKE_VERIFIED__PROCEED_TO_EXECUTION" if intake_pass
                else "BASELINE_INTAKE_FAILED__FAIL_CLOSED_STOP"),
    "release_credit": False,
}
jdump(intake, f"{TK}/BASELINE_INTAKE_VERIFICATION_V1.json")
print(json.dumps({"intake_pass": intake_pass, "checks": intake_checks,
                  "missing": missing, "mujoco": f"{mj_match}/{mj_total}"}, indent=1))
assert intake_pass, "intake verification failed - fail-closed stop"
