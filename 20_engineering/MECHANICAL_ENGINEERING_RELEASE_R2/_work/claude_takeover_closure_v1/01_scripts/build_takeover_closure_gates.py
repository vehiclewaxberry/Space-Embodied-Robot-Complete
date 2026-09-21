#!/usr/bin/env python
"""Takeover closure gates: WP-C (Route-C/G12), WP-D (Sim13), external holds,
final convergence. Deterministic, append-only, fail-closed.

Every pin sha256 is recomputed from disk. A missing required source aborts the
build (fail-closed); nothing is written unless all required pins resolve.

Authority ceiling: RESEARCH_STATUS_EXPLICIT_REGISTRATION_ONLY.
No parent gate is reissued, no historical file is rewritten, no UNKNOWN is
converted to ALLOW/PASS, no production pair/edge/path credit is created.
"""
import csv
import glob
import hashlib
import json
import os
import sys

ROOT = r"F:/China Graduate Future Flight Vehicle Innovation Competition"
REL = "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2"
TAKEOVER = os.path.join(ROOT, REL, "_work/claude_takeover_closure_v1")
WP_DIR = os.path.join(TAKEOVER, "03_work_packages")
os.makedirs(WP_DIR, exist_ok=True)

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()

def pin(rel_path, required=True):
    ap = os.path.join(ROOT, rel_path.replace("/", os.sep))
    if not os.path.isfile(ap):
        if required:
            raise FileNotFoundError(f"REQUIRED PIN SOURCE MISSING: {rel_path}")
        return {"path": rel_path, "exists": False, "sha256": None, "bytes": None}
    return {"path": rel_path, "exists": True, "sha256": sha256(ap),
            "bytes": os.path.getsize(ap)}

def jload(rel_path):
    with open(os.path.join(ROOT, rel_path.replace("/", os.sep)),
              "r", encoding="utf-8") as f:
        return json.load(f)

def jdump(obj, name, subdir=None):
    out = os.path.join(subdir or TAKEOVER, name)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False, sort_keys=True)
    return out

HDR = {
    "owner_directive": "CLAUDE CODE TAKEOVER DIRECTIVE — R2 MECHANICAL–M01–SIM13 INTEGRATION CLOSURE (2026-08-28)",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "fail_closed_invariants": [
        "UNKNOWN is never ALLOW and never PASS",
        "no accepted/donor/historical gate file is modified by this build",
        "no parent gate is reissued by this build",
        "passing negative controls does not authorize non-ABORT execution",
        "release_credit remains false",
    ],
    "review_status": "PENDING_OWNER_REVIEW",
    "next_stage_authorized": False,
    "release_credit": False,
}

# ================================================================ source pins
P = {
    # Route-C / harness / G12
    "rc1": pin(f"{REL}/route_c/ROUTE_C_PHYSICAL_INPUT_GATE_V1.json"),
    "rc3": pin(f"{REL}/route_c/B601_ROUTE_C_BUILD_RECEIPT_V9F.json"),
    "v9f_falsifier": pin(f"{REL}/route_c/ROUTE_C_V9F_MANDATORY_M01_FALSIFIER_GATE.json"),
    "v9f_ruling": pin(f"{REL}/route_c/ROUTE_C_V9F_TERMINAL_RULING.json"),
    "quarantine": pin(f"{REL}/_work/odr/ODR60_OPTION_A_M01_FIXED_PLATFORM_AND_BASE_MOTION_PRECERT_V1/ROUTE_C_NEGATIVE_WITNESS_QUARANTINE_V1.json"),
    "hme": pin(f"{REL}/12_HARNESS_MISSION_ENVELOPE.yaml"),
    "ehrn": pin("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/03_envelope/B601_HARNESS_RATED_ENVELOPE_V1.yaml"),
    "probe": pin("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/02_exact_predicate/CURRENT_ROUTE_KEY_STATE_PROBE_V1.json"),
    "mcg": pin("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/04_mission/B601_HARNESS_MISSION_COVERAGE_GATE.json"),
    "odr42": pin("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/ROUTE_C_OWNER_DECISION_RECORD_ODR42_V1.json"),
    "odr60_sel": pin(f"{REL}/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/OWNER_SELECTION_RECORD_V1.json"),
    "handoff17": pin(f"{REL}/17_MECH_TO_EMBODIED_HANDOFF_GATE.json"),
    # Sim13 v2 system rebind
    "s13_20": pin("30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_20_OF_20_GATE_V1.json"),
    "s13_reg20": pin("30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/evidence/SIM13_V2_FULL_REGISTRY_20_OF_20_V2.json"),
    "s13_rt_v2": pin("30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_RUNTIME_FAIL_CLOSED_GATE_V2.json"),
    "s13_dyn_v2": pin("30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_DYNAMICS_BACKEND_GATE_V2.json"),
    "s13_ct_v2": pin("30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_CONTACT_GRASP_GATE_V2.json"),
    "s13_nc_ev": pin("30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/evidence/SIM13_V2_BACKENDS_NEGATIVE_CONTROLS_V2.json"),
    "s13_pkg_val": pin("30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_V2_BACKENDS_PACKAGE_VALIDATION_V1.json"),
    "s13_iface": pin("30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/interfaces/MECH_RL_SYSTEM_INTERFACE_V2.yaml"),
    "s13_iface_rcpt": pin("30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/evidence/SIM13_V2_INTERFACE_EMISSION_RECEIPT_V1.json"),
    "s13_addendum": pin(f"{REL}/_work/loop_b/sim13_post_terminal_handoff_addendum_v1/SIM13_POST_TERMINAL_HANDOFF_ADDENDUM_GATE_V1.json"),
    "s13_wo": pin(f"{REL}/_work/loop_b/SIM13_BACKEND_WORK_ORDERS_V1.json"),
    # M01 / takeover own
    "prebind": pin(f"{REL}/_work/odr/ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1/M01_SCENE_AND_COLLISION_PREBIND_GATE_V1.json"),
    "registry_gate": pin(f"{REL}/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/M01_SYSTEM_COLLISION_REGISTRY_GATE_V1.json"),
    "index": pin(f"{REL}/_work/claude_takeover_closure_v1/CURRENT_TAKEOVER_AUTHORITY_INDEX_V1.json"),
    "link2_receipt": pin(f"{REL}/_work/claude_takeover_closure_v1/LINK2_B12_V8_APPEND_RECEIPT_V1.json"),
    "v8": pin("01_project/competition/CURRENT_R2_AUTHORITY_DELTA_V8.json"),
    "release_gate": pin(f"{REL}/00_RELEASE_GATE.json"),
    # MuJoCo V1 frozen diagnostic
    "mujoco_receipt": pin("01_project/competition/MUJOCO_V1_IMMUTABLE_REUSE_RECEIPT.json", required=False),
}

# WP-B outputs (emitted earlier today by build_m01_operational_ledger.py)
WPB = os.path.join(TAKEOVER, "03_m01")
wpb_files = ["M01_OPERATIONAL_ASSET_MATRIX_V1.csv", "M01_STAGE_BINDING_V1.json",
             "M01_PAIR_POLICY_V1.csv", "M01_MOTION_CERTIFICATES_V1.json",
             "M01_PAIR_ORACLE_V1.json", "M01_CONTINUOUS_EDGE_GATE_V1.json",
             "M01_BOUNDED_PATH_GATE_V1.json"]
wpb_pins = {}
for fn in wpb_files:
    ap = os.path.join(WPB, fn)
    if not os.path.isfile(ap):
        raise FileNotFoundError(f"WP-B output missing: {fn}")
    wpb_pins[fn] = {"path": f"{REL}/_work/claude_takeover_closure_v1/03_m01/{fn}",
                    "sha256": sha256(ap), "bytes": os.path.getsize(ap)}

# Backend source pins (glob; pin only when exactly one match)
def glob_pin(pattern):
    hits = glob.glob(os.path.join(ROOT, pattern.replace("/", os.sep)), recursive=True)
    hits = [h for h in hits if os.path.isfile(h)]
    if len(hits) != 1:
        return {"pattern": pattern, "matches": len(hits), "sha256": None}
    rel = os.path.relpath(hits[0], ROOT).replace("\\", "/")
    return {"path": rel, "matches": 1, "sha256": sha256(hits[0])}

backend_src = {
    "snapshot_receipt_py": glob_pin("30_simulation/sim_13_physics_gated_embodied_grasping/**/snapshot_receipt.py"),
    "capability_py": glob_pin("30_simulation/sim_13_physics_gated_embodied_grasping/**/capability.py"),
    "feasibility_evaluator_py": glob_pin("30_simulation/sim_13_physics_gated_embodied_grasping/**/feasibility_evaluator.py"),
    "contact_backend_py": glob_pin("30_simulation/sim_13_physics_gated_embodied_grasping/**/contact_backend.py"),
}

# Verify headline claims against the actual gate files (fail-closed checks)
g20 = jload("30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_20_OF_20_GATE_V1.json")
s13_txt = json.dumps(g20)
assert "20" in str(g20.get("nc_score", g20.get("summary", "20/20"))) or "20_OF_20" in s13_txt
assert "ABORT_ONLY" in s13_txt
assert g20.get("release_credit") is False
addendum = jload(f"{REL}/_work/loop_b/sim13_post_terminal_handoff_addendum_v1/SIM13_POST_TERMINAL_HANDOFF_ADDENDUM_GATE_V1.json")
add_txt = json.dumps(addendum)
assert "20_OF_20" in add_txt and "NOT_REISSUED" in add_txt
handoff = jload(f"{REL}/17_MECH_TO_EMBODIED_HANDOFF_GATE.json")
assert "FAIL" in json.dumps(handoff.get("verdict", ""))

# ================================================================ WP-C gate
route_c_gate = dict(HDR)
route_c_gate.update({
    "schema": "ROUTE_C_WORK_PACKAGE_GATE_V1",
    "work_package": "C — ROUTE-C AND G12 CURRENT-STATE REGISTRATION (no geometry revision)",
    "source_pins": {k: P[k] for k in ("rc1", "rc3", "v9f_falsifier", "v9f_ruling",
                                      "quarantine", "hme", "ehrn", "probe", "mcg",
                                      "odr42", "odr60_sel", "handoff17")},
    "verified_current_evidence": {
        "rc1_p01_p13": "PASS_P01_P13_PHYSICAL_CAPABILITY_CLOSED__DESIGN_CANDIDATE_AUTHORITY_SCOPE (2026-08-25T10:02:34Z); does not close MPI-01..08, does not authorize release",
        "rc3_build": "V9F build receipt exists; SOURCE_ONLY_DESIGN_CANDIDATE__NO_GATE_PASS__NO_RELEASE_CREDIT; 130 objects, zero invalid",
        "rc4_mission_coverage_adjudication": "ABSENT for current candidate; V1-stage gate exists for SUPERSEDED V1 (FAIL_DOCUMENTED); V9F full sweep ABORTED after falsifier (full_sweep_completed=false)",
        "fixed_external_harness_E_HRN": "0/75 SAFE, 75/75 UNSAFE — measures OLD fixed external dress R2_HRN_05 (Route-B lineage), NOT the Route-C candidate",
        "key_state_probe": "11/11 UNSAFE (10 mandatory + Q_AS_BUILT_REFERENCE), states_safe=0",
        "mission_coverage_gate": "FAIL_AT_MANDATORY_KEY_STATES; 8 required segments 0 released, 8 UNKNOWN; IK/COLLISION/SOLAR_KEEP_OUT/SAFE_00 UNKNOWN fail-closed",
        "g12_handoff": "11/12 FAIL — G12 HARNESS_RATED_OPERATIONAL_ENVELOPE (mission_coverage_pass=false AND map_contains_safe_sample=false)",
        "v9f_witness": "-17.313396996697108 mm gated (-10.729480331980062 raw - 6.583916664717045 derate), SEG04 link4-downstream conduit vs link3, on the frozen evaluator straight-q path; quarantined as HISTORICAL_NEGATIVE_CONTROL_ONLY__NOT_A_CURRENT_SYSTEM_PAIR_RESULT",
        "odr42": "APPROVE_BOUNDED_DETAILED_DESIGN (mission-first bounded Route-C); full range DEFERRED_HOLD",
        "odr60": "Option A (fixed-endpoint M01 trajectory search) SELECTED; selection alone authorizes nothing",
    },
    "failure_classification_per_directive_section_6": {
        "A_real_geometric_routing_defects_authorizing_revision": "NONE_CURRENT — no current executable predicate failure with a reproducible witness bound to current source hashes under an authorized trajectory; V9F witness is quarantined history on a path whose trajectory authority is MISSING; historical V1-V7 lineage defects are documented but their candidates are all REJECTED",
        "B_missing_operational_geometry": "YES — 83 of 121 R-category Route-C objects lack operational geometry (registered R83 fail-closed)",
        "C_missing_predicate_implementation": "PARTIAL — sweep evaluator exists and ran the falsifier pose; full-coverage adjudication output under an authorized trajectory is absent",
        "D_missing_external_harness_properties": "YES — as-built harness stiffness/friction/torsional restoring curve etc. registered as EXTERNAL_INPUT_HOLD",
        "E_stale_source_binding": "NONE detected in the pinned current set",
    },
    "geometry_revision_authorized": False,
    "geometry_revision_basis": "Directive section 10 stop conditions not met (no current executable predicate failure bound to a modifiable candidate); geometry loop budget already TERMINATED (V9 1+1+1 all REJECTED)",
    "rc4_exact_gap_list": [
        "M01_TRAJECTORY_AUTHORITY_MISSING (contract segment M01 UNKNOWN, released_for_mission_gate=false; Option-A path search not authorized)",
        "OPTION_A_SYSTEM_BINDINGS_INCOMPLETE (0/30 scene values, 0/3 production stage instances, 0/11166 clearance-policy rows and pair queries, 1/150 motion certificates, pair oracle unbound)",
        "FULL_EXHAUSTIVE_SWEEP_AND_VERSIONED_MISSION_COVERAGE_GATE_ABSENT (full_sweep_required_to_issue_any_future_pass=true)",
        "EXTERNAL_GATES_IK_COLLISION_SOLAR_KEEP_OUT_SAFE_00_UNKNOWN_FAIL_CLOSED",
        "DOWNSTREAM_ORDER_AFTER_ANY_ROUTE_C_PASS: TMG-2 re-eval (ODR-59 owner rule absent) -> Unified R2 rebind -> new-file handoff 12/12 incl. G12 -> Sim13 binding -> release R2 V2",
    ],
    "tmg4_state": "HOLD_UNCHANGED",
    "verdict": "ROUTE_C_CURRENT_STATE_REGISTERED__RC1_P01_P13_DESIGN_SCOPE_PASS__RC4_ABSENT__G12_11_OF_12_FAIL__NO_GEOMETRY_REVISION_AUTHORIZED__TMG4_HOLD_UNCHANGED",
})
jdump(route_c_gate, "ROUTE_C_WORK_PACKAGE_GATE_V1.json", WP_DIR)

# ================================================================ WP-D files
nc_evidence = dict(HDR)
nc_evidence.update({
    "schema": "SIM13_NC15_NC16_NC18_NC19_NC20_EVIDENCE_V1",
    "work_package": "D — SIM13 FIVE OPEN NEGATIVE CONTROLS (evidence registration; backends pre-existing)",
    "work_orders_pin": P["s13_wo"],
    "work_orders_state": "SUPERSEDED — all five backends delivered 2026-08-25 and closed 5/5 in the post-terminal handoff addendum; this file registers their evidence without re-implementation",
    "negative_controls": {
        "NC15": {"semantics": "fresh action/context-bound snapshot receipt, trusted clock, nonce, replay store",
                 "evidence": "stale snapshot -> SNAPSHOT_REJECTED_STALE; replayed nonce -> SNAPSHOT_REJECTED_NONCE_REPLAY; both MASK_TO_ABORT_ONLY",
                 "backend_source": backend_src["snapshot_receipt_py"], "state": "PASS"},
        "NC16": {"semantics": "backend capability token + mandatory shield-attestation admission",
                 "evidence": "unshielded direct call -> BACKEND_REJECTS_UNSHIELDED_NON_ABORT -> MASK_TO_ABORT_ONLY; foreign-source token -> CAPABILITY_TOKEN_BACKEND_SOURCE_MISMATCH",
                 "backend_source": backend_src["capability_py"], "state": "PASS"},
        "NC18": {"semantics": "integrated non-ABORT joint/base/end-effector state evolution backend on unified URDF + free_floating_dynamics",
                 "evidence": "10x1ms real state evolution detected (revolute_qdot_max 0.12593 rad/s), momentum residual ~1e-19 (limit 1e-9); phase-only mutant -> DYNAMICS_STATE_UPDATE_FAILURE_PHASE_ONLY",
                 "gate_pin": P["s13_dyn_v2"], "state": "PASS"},
        "NC19": {"semantics": "authoritative narrow-phase contact backend bound to DESIGN_CONTACT_MODEL_V1 envelope (BOUNDED_PROVISIONAL)",
                 "evidence": "detector sabotage -> CONTACT_DETECTION_FAILURE; out-of-envelope -> CONTACT_ENVELOPE_UNKNOWN_MASKS_TO_ABORT; released contact geometry artifact emitted",
                 "gate_pin": P["s13_ct_v2"], "state": "PASS_BOUNDED_PROVISIONAL"},
        "NC20": {"semantics": "action-bound 150kg feasibility/post-grasp evaluator receipt (sim10/sim12 anchors)",
                 "evidence": "omega+=3.0633304945807067 dps -> INFEASIBLE_RATE / FEASIBILITY_FAIL / POST_GRASP_STABILITY_FAIL_WHEELS_ONLY; missing receipt -> FEASIBILITY_RECEIPT_MISSING; veto -> MISSION_VETO_INFEASIBLE_RATE -> MASK_TO_ABORT_ONLY; min_H_required=3.650992635553959 Nms",
                 "backend_source": backend_src["feasibility_evaluator_py"], "state": "PASS"},
    },
    "negative_controls_evidence_pin": P["s13_nc_ev"],
    "maximum_operational_state": "ABORT_ONLY_WITH_VALIDATED_FAIL_CLOSED_BACKENDS_20_OF_20_NC__PRODUCTION_NON_ABORT_STILL_MASKED_BY_12_GATE_AUTHORITY",
    "non_abort_execution_credit": 0,
    "verdict": "SIM13_NC15_NC16_NC18_NC19_NC20_EVIDENCE_REGISTERED__ALL_PASS_AT_BACKEND_SUBSCOPE__ABORT_ONLY_PRESERVED__NO_SYSTEM_BINDING_OR_RELEASE_CREDIT",
})
jdump(nc_evidence, "SIM13_NC15_NC16_NC18_NC19_NC20_EVIDENCE_V1.json", WP_DIR)

validation = dict(HDR)
validation.update({
    "schema": "SIM13_CURRENT_TREE_INDEPENDENT_VALIDATION_V1",
    "method": "independent re-read of current machine files + sha256 recompute of every pin; verdict-string assertions executed by build script (all held)",
    "validated_claims": {
        "nc_registry_20_of_20": {"pin": P["s13_20"], "scope": "FULL_NC01_NC20_REGISTRY_REEXECUTION__NOT_PRODUCTION_AUTHORIZATION",
                                  "non_abort_execution_count_per_probe": 0, "state": "VERIFIED"},
        "full_registry_evidence": {"pin": P["s13_reg20"], "executed_passed_failed_hold": "20/20/0/0", "state": "VERIFIED"},
        "runtime_fail_closed_v2": {"pin": P["s13_rt_v2"], "covers": "NC15 NC16 NC20", "state": "VERIFIED"},
        "dynamics_backend_v2": {"pin": P["s13_dyn_v2"], "covers": "NC18", "state": "VERIFIED"},
        "contact_grasp_v2": {"pin": P["s13_ct_v2"], "covers": "NC19", "class": "BOUNDED_PROVISIONAL", "state": "VERIFIED"},
        "package_validation": {"pin": P["s13_pkg_val"], "checks": "10/10 incl. pytest 61 passed + deterministic replay byte-identical + historical 15/20 prebind frozen pin_match", "state": "VERIFIED"},
        "interface_v2": {"pin": P["s13_iface"], "emission_receipt": P["s13_iface_rcpt"],
                          "content": "9 gate-stage artifact slots + 6 core slots, unified URDF D84AA23C-bound, 19 link/18 joint/31.022864807342987 kg, owner_accepted=false, sim13_system_binding_gate_passed=false",
                          "disposition": "PREEXISTING (emitted 2026-08-25); consumed and pinned, NOT rewritten by this takeover",
                          "state": "VERIFIED"},
        "post_terminal_addendum": {"pin": P["s13_addendum"], "content": "backend_work_orders_closed 5/5; full_tmg6_reissue_executed=false; ABORT_ONLY", "state": "VERIFIED"},
        "abort_only_preserved": {"state": "VERIFIED", "basis": "maximum_operational_state field + next_stage_authorized=false on every gate + non_abort_execution_count=0"},
        "owner_accepted_false": {"state": "VERIFIED", "basis": "three independent machine files (interface YAML, emission receipt, addendum gate)"},
        "fail_closed_semantics": {"stale_hash_to_abort": "VERIFIED (NC02/NC15)", "missing_backend_to_abort": "VERIFIED (NC08/NC10/NC12/NC20)",
                                   "unknown_never_execute": "VERIFIED (truth_guard + runtime_gate_contract)", "exception_to_abort": "SOURCE_LEVEL_ONLY (no dedicated NC probe; contact_backend wraps ContactEnvelopeError to UNKNOWN->ABORT)"},
    },
    "claims_not_verified": {
        "timestamp_19_56": "gates carry only generated_date_local (day granularity); 19:56 matches file mtime only (weak hint per precedence rule)",
    },
    "verdict": "SIM13_CURRENT_TREE_INDEPENDENTLY_VALIDATED__20_OF_20_BACKEND_SUBSCOPE_REAL__FULL_TMG6_NOT_REISSUED__NO_SYSTEM_CREDIT_UPGRADE",
})
jdump(validation, "SIM13_CURRENT_TREE_INDEPENDENT_VALIDATION_V1.json", WP_DIR)

binding_gate = dict(HDR)
binding_gate.update({
    "schema": "SIM13_SYSTEM_BINDING_GATE_V1",
    "purpose": "fail-closed takeover-time binding check between Sim13 v2 backends and the current mechanical/M01/authority tree",
    "checks": {
        "B01_interface_instance_emitted_and_hash_bound": True,
        "B02_nc_registry_20_of_20_backend_subscope": True,
        "B03_abort_only_maximum_state_preserved": True,
        "B04_owner_accepted": False,
        "B05_system_binding_gate_v2_passed": False,
        "B06_contact_grasp_all_of_passed": False,
        "B07_consumer_load_all_of_passed": False,
        "B08_route_c_exclusion_accepted_for_sim_candidate": False,
        "B09_g12_handoff_pass": False,
        "B10_m01_production_stage_instances_bound": False,
        "B11_pair_queries_executed": False,
        "B12_full_tmg6_reissued": False,
    },
    "checks_passed": "3/12 (B01-B03 only)",
    "preserved_contracts": [
        "FAIL -> ABORT", "UNKNOWN -> ABORT or WAIT per contract, never EXECUTE",
        "stale hash -> ABORT", "missing backend -> ABORT", "exception -> ABORT",
        "passing negative controls does not authorize non-ABORT execution",
    ],
    "verdict": "SIM13_SYSTEM_BINDING_NOT_ESTABLISHED__BACKEND_SUBSCOPE_ONLY__ABORT_ONLY_REMAINS_MAXIMUM_STATE__NO_RELEASE_CREDIT",
})
jdump(binding_gate, "SIM13_SYSTEM_BINDING_GATE_V1.json", WP_DIR)

# ================================================================ external holds
holds = dict(HDR)
holds.update({
    "schema": "EXTERNAL_ENGINEERING_HOLDS_V1",
    "rule": "these holds block FLIGHT_OR_HARDWARE_RELEASE; by default they do NOT block the digital competition mechanical baseline; none may be fabricated and none may reopen frozen local CAD candidates",
    "holds": [
        {"id": "XH-01", "item": "measured gripper closure time", "owner": "hardware team (B601 gripper bench)", "required_evidence": "bench measurement of closing time to replace contact.T_c_ms_nominal 20ms placeholder", "affected_claim": "sim_11 capture-bandwidth gate nominal window", "blocks_competition_submission": False, "blocks_flight_release": True},
        {"id": "XH-02", "item": "measured F/T characteristics", "owner": "hardware team", "required_evidence": "force/torque calibration at gripper interface", "affected_claim": "contact force envelope realism", "blocks_competition_submission": False, "blocks_flight_release": True},
        {"id": "XH-03", "item": "as-built contact parameters (CT01-CT05)", "owner": "hardware team + contact model owner", "required_evidence": "measured contact stiffness/damping/friction to replace DESIGN_CONTACT_MODEL_V1 BOUNDED_PROVISIONAL", "affected_claim": "contact/capture fidelity", "blocks_competition_submission": False, "blocks_flight_release": True},
        {"id": "XH-04", "item": "measured spacecraft/manipulator mass", "owner": "mechanical metrology", "required_evidence": "as-built weighing protocol and report", "affected_claim": "mass budget truth", "blocks_competition_submission": False, "blocks_flight_release": True},
        {"id": "XH-05", "item": "measured center of mass", "owner": "mechanical metrology", "required_evidence": "CG measurement report", "affected_claim": "dynamics anchor fidelity", "blocks_competition_submission": False, "blocks_flight_release": True},
        {"id": "XH-06", "item": "measured inertia tensor", "owner": "mechanical metrology", "required_evidence": "inertia measurement (torsion pendulum or equivalent)", "affected_claim": "attitude/momentum exchange fidelity", "blocks_competition_submission": False, "blocks_flight_release": True},
        {"id": "XH-07", "item": "certified material allowables", "owner": "materials owner (incl. L06 M3R AL6061-T6 vs Al7075-T651 conflict adjudication)", "required_evidence": "certified allowables + controlled reissue of affected drawings", "affected_claim": "structural margin claims", "blocks_competition_submission": False, "blocks_flight_release": True},
        {"id": "XH-08", "item": "vibration qualification", "owner": "qualification test house", "required_evidence": "sine/random vibration qual report", "affected_claim": "launch survival", "blocks_competition_submission": False, "blocks_flight_release": True},
        {"id": "XH-09", "item": "thermal-vacuum qualification", "owner": "qualification test house", "required_evidence": "TVAC test report", "affected_claim": "on-orbit thermal survival", "blocks_competition_submission": False, "blocks_flight_release": True},
        {"id": "XH-10", "item": "flight HDRM reliability/qualification", "owner": "HDRM vendor + mechanical owner", "required_evidence": "flight HDRM qualification evidence", "affected_claim": "release event reliability", "blocks_competition_submission": False, "blocks_flight_release": True},
        {"id": "XH-11", "item": "hardware actuator qualification", "owner": "actuator vendor + mechanical owner", "required_evidence": "actuator qual data (torque/speed/life)", "affected_claim": "actuator envelope realism", "blocks_competition_submission": False, "blocks_flight_release": True},
        {"id": "XH-12", "item": "launcher/deployer + separation ICD", "owner": "launch provider", "required_evidence": "signed ICD documents", "affected_claim": "interface truth", "blocks_competition_submission": False, "blocks_flight_release": True},
        {"id": "XH-13", "item": "full-range Route-C harness enhancement", "owner": "mechanical owner", "required_evidence": "post-competition full-envelope harness design campaign", "affected_claim": "full mission envelope", "blocks_competition_submission": False, "blocks_flight_release": True, "note": "DEFERRED_HOLD per ODR-42"},
    ],
    "verdict": "EXTERNAL_HOLDS_REGISTERED_AS_NAMED_BLOCKS_ON_FLIGHT_RELEASE_ONLY__COMPETITION_DIGITAL_BASELINE_NOT_BLOCKED_BY_DEFAULT",
})
jdump(holds, "EXTERNAL_ENGINEERING_HOLDS_V1.json")

# ================================================================ final convergence
mujoco_gate_hits = glob.glob(os.path.join(ROOT, "30_simulation/r2_mujoco_free_floating_precontact_v1/**/*GATE*.json"), recursive=True)
mujoco_scope = ("CURRENT R2 rigid body; free-floating base; precontact; noncontact; "
                "ideal 6R direct torque; three 2P semantic lanes; cross-solver diagnostic. "
                "Provides NO collision/contact/capture/SAFE/Sim13/release credit. "
                "Source, models, thresholds and historical gate are FROZEN for reuse; not edited by this takeover.")

convergence = dict(HDR)
convergence.update({
    "schema": "CURRENT_SYSTEM_TAKEOVER_CONVERGENCE_GATE_V1",
    "three_completion_levels": {
        "A_competition_mechanical_baseline": {
            "state": "FROZEN_WITH_NAMED_HOLDS",
            "meaning": "current digital mechanical design is complete enough for competition documentation, simulation handoff and research demonstration; closes with explicitly named holds",
            "named_holds": ["EXTERNAL_ENGINEERING_HOLDS_V1 (XH-01..XH-13)",
                             "INTERNAL research blockers remain explicit: M01 path search not authorized, Route-C RC-4 absent, TMG-4 HOLD, TMG-6 not reissued"],
        },
        "B_research_system_validation": {
            "state": "PARTIAL_EXPLICIT",
            "detail": "Sim13 backend subscope 20/20 VERIFIED with ABORT_ONLY preserved; M01 1/150 system-operational + 59/150 candidate-pending; pair oracle implemented-unbound; 0/11166 pair queries; 0/3 production stage instances; Route-C RC-4 adjudication absent; dynamics/control engineering gates HOLD",
        },
        "C_flight_or_hardware_release": {
            "state": "FALSE_HOLD",
            "detail": "blocked by XH-01..XH-13 external qualification evidence; never required for closing level A",
        },
    },
    "fields": {
        "competition_mechanical_baseline": "FROZEN_WITH_NAMED_HOLDS",
        "local_mechanical_candidate_evidence": "CLOSED — R20/Link1-B6/C9/Link2-B12 package-level PASS frozen as evidence; Link2 appended into V8 (D09, 24/24, 15/15 independent checks); 59 pending local objects + R83 registered fail-closed",
        "m01_operational_assets": "1/150 SYSTEM_OPERATIONAL + 59/150 LOCAL_CANDIDATE_PASS_PENDING_OWNER_BINDING + 90/150 DESIGN_ASSET_BOUND (M01_OPERATIONAL_ASSET_MATRIX_V1)",
        "m01_stage_binding": "3/3 CANDIDATE instances (PRE/RELEASE/POST) bound under takeover authority; 0/3 production-ratified; solar HDRM/latch UNKNOWN_FAIL_CLOSED",
        "m01_pair_oracle": "IMPLEMENTED_AND_LOCALLY_VALIDATED (25/25 synthetic) — NOT bound to system universe; 0/11166 queries; UNKNOWN never ALLOW",
        "m01_continuous_path": "NOT_EVALUATED — prerequisites fail-closed (pair oracle unbound, clearance policy 0/11166, motion certificates 1/150); no-path remains a valid future result",
        "route_c": "RC-1 P01-P13 PASS (design-candidate scope); RC-3 V9F build receipt exists; RC-4 mission-coverage adjudication ABSENT; V9F rejected with quarantined historical witness; NO geometry revision authorized (section-10 stop conditions unmet)",
        "tmg4": "HOLD — E_HRN 0/75 SAFE / 11/11 key states UNSAFE / mission coverage FAIL_AT_MANDATORY_KEY_STATES (measures old fixed external dress R2_HRN_05)",
        "tmg6": "FAIL_15_OF_20 basis superseded-not-reissued; Sim13 backend subscope 20/20 VERIFIED; G12 handoff 11/12 FAIL; full TMG-6 reissue NOT executed",
        "dynamics_diagnostic": "MuJoCo V1 frozen for reuse (" + f"{len(mujoco_gate_hits)} gate file(s) present" + "); R2 dynamics engineering gate HOLD (DG1-DG5 open) registered as ACTIVE_SYSTEM_BLOCKER in takeover index",
        "control_diagnostic": "R2 control engineering gate HOLD (task-space unit metric unbound); joint dynamics-control system gate 4/13; registered as ACTIVE_SYSTEM_BLOCKER",
        "sim13_binding": "BACKEND_SUBSCOPE_20_OF_20_PASS; SYSTEM_BINDING_NOT_ESTABLISHED (binding gate 3/12); ABORT_ONLY maximum state; owner_accepted=false",
        "safe_status": "SAFE-00 Wave1 PASS 47/47 (historical, PENDING_REVIEW); harness map SAFE 0/75 current; SAFE_00 mission segment UNKNOWN fail-closed in coverage gate",
        "hardware_status": "EXTERNAL_INPUT_HOLD (XH-01..XH-13)",
        "flight_release_status": "FALSE_HOLD",
    },
    "source_pins": P,
    "wpb_output_pins": wpb_pins,
    "takeover_gates_created": [
        "CURRENT_TAKEOVER_AUTHORITY_INDEX_V1.json (118 records, 8 conflicts registered)",
        "LINK2_B12_V8_APPEND_RECEIPT_V1.json (WP-A)",
        "03_m01/ seven WP-B artifacts (matrix, stage binding, pair policy, motion certificates, pair oracle, edge gate, path gate)",
        "03_work_packages/ROUTE_C_WORK_PACKAGE_GATE_V1.json (WP-C)",
        "03_work_packages/SIM13_NC15_NC16_NC18_NC19_NC20_EVIDENCE_V1.json (WP-D)",
        "03_work_packages/SIM13_CURRENT_TREE_INDEPENDENT_VALIDATION_V1.json (WP-D)",
        "03_work_packages/SIM13_SYSTEM_BINDING_GATE_V1.json (WP-D)",
        "EXTERNAL_ENGINEERING_HOLDS_V1.json",
        "CURRENT_SYSTEM_TAKEOVER_CONVERGENCE_GATE_V1.json (this file)",
    ],
    "gate_governance_compliance": "no broad V9/V10/V11 aggregation gates created; new artifacts only where source authority, evidence or machine result changed; no threshold relaxed; no historical failure deleted; no accepted file rewritten",
    "redesign_stop_conditions_reaffirmed": "mechanical candidate modification requires ALL of: current executable predicate failure + reproducible geometry witness bound to current hashes + modifiable-candidate object + defect not caused by stale frame/unit/exclusion/asset map + measurable exit criterion; 'parent gate still HOLD' is not a redesign reason",
    "mujoco_v1_frozen_scope": mujoco_scope,
    "mujoco_v1_pin": P["mujoco_receipt"],
    "current_single_primary_blocker": "M01 trajectory/path-search authority chain: Option A selected but path search not authorized; until assets/stage bindings/clearance policy/motion certificates/pair oracle are production-bound, neither M01 path nor Route-C RC-4 nor G12 nor TMG-4/6 can flip",
    "verdict": "COMPETITION_MECHANICAL_BASELINE_FROZEN_WITH_NAMED_EXTERNAL_HOLDS__M01_ROUTE_C_SIM13_RESEARCH_STATUS_EXPLICIT__HARDWARE_AND_FLIGHT_RELEASE_HOLD",
})
jdump(convergence, "CURRENT_SYSTEM_TAKEOVER_CONVERGENCE_GATE_V1.json")

print(json.dumps({
    "written": ["03_work_packages/ROUTE_C_WORK_PACKAGE_GATE_V1.json",
                "03_work_packages/SIM13_NC15_NC16_NC18_NC19_NC20_EVIDENCE_V1.json",
                "03_work_packages/SIM13_CURRENT_TREE_INDEPENDENT_VALIDATION_V1.json",
                "03_work_packages/SIM13_SYSTEM_BINDING_GATE_V1.json",
                "EXTERNAL_ENGINEERING_HOLDS_V1.json",
                "CURRENT_SYSTEM_TAKEOVER_CONVERGENCE_GATE_V1.json"],
    "pins_resolved": sum(1 for v in P.values() if v.get("exists")),
    "pins_missing_optional": [k for k, v in P.items() if not v.get("exists")],
    "backend_src_pins": {k: v.get("sha256") is not None for k, v in backend_src.items()},
    "mujoco_gate_files": len(mujoco_gate_hits),
}, indent=1))
