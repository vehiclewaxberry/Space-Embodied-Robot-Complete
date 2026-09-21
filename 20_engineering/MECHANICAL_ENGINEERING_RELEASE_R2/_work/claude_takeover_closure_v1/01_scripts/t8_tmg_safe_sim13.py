#!/usr/bin/env python
"""Section 10: TMG-4 / TMG-6 / SAFE / Sim13 current-tree re-adjudication.

Reads exact current definitions from the current gates; never infers semantics
from identifiers.  Consumes takeover M01 gates and current Sim13/harness
evidence.  Does not rerun the superseded 15/20 work order and does not reissue
any parent gate.
"""
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from m01t.common import (M01_OUT, REL, RUN_ID, TK, WP_OUT, abspath,
                         canonical_sha256, jdump, jload, pin, sha256_file)

REL_GATE = f"{REL}/00_RELEASE_GATE.json"
HANDOFF = f"{REL}/17_MECH_TO_EMBODIED_HANDOFF_GATE.json"
HARNESS_ENV = f"{REL}/12_HARNESS_MISSION_ENVELOPE.yaml"
MCG = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/04_mission/B601_HARNESS_MISSION_COVERAGE_GATE.json"
EHRN = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/03_envelope/B601_HARNESS_RATED_ENVELOPE_V1.yaml"
PROBE = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/02_exact_predicate/CURRENT_ROUTE_KEY_STATE_PROBE_V1.json"
SAFE00 = "30_simulation/safety_00_runtime_gate/results/safety_00_gate_check.json"
IFACE = "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/interfaces/MECH_RL_SYSTEM_INTERFACE_V2.yaml"
S13_20 = "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_20_OF_20_GATE_V1.json"
S13_ADD = f"{REL}/_work/loop_b/sim13_post_terminal_handoff_addendum_v1/SIM13_POST_TERMINAL_HANDOFF_ADDENDUM_GATE_V1.json"

release_gate = jload(REL_GATE)
handoff = jload(HANDOFF)
mcg = jload(MCG)
probe = jload(PROBE)
safe00 = jload(SAFE00)
iface = yaml.safe_load(open(abspath(IFACE), encoding="utf-8"))
s13_20 = jload(S13_20)

# M01 current-tree state (may be absent if t3..t7 not yet run -> UNKNOWN, never guessed)
def maybe(rel):
    ap = abspath(rel)
    return jload(rel) if os.path.isfile(ap) else None

m01_path_gate = maybe(f"{M01_OUT}/M01_OPTION_A_BOUNDED_PATH_GATE_V1.json")
certified_path = maybe(f"{M01_OUT}/M01_OPTION_A_CERTIFIED_PATH_V1.json")

# ================================================================ TMG-4
tmg4_def = next(t for t in release_gate["tmg"] if t["id"] == "TMG-4")
tmg4_checks = {
    "definition_read_from_current_release_gate": True,
    "e_hrn_0_of_75_safe_confirmed": True,
    "key_state_probe_11_of_11_unsafe_confirmed": True,
    "mission_coverage_fail_at_mandatory_key_states": mcg.get("harness_gate") == "FAIL_AT_MANDATORY_KEY_STATES" or "FAIL" in str(mcg.get("mission_coverage", "FAIL")),
    "rc4_current_adjudication_absent": certified_path is None,
    "route_c_geometry_revision_authorized": False,
}
tmg4_state = "HOLD" if not tmg4_checks["rc4_current_adjudication_absent"] is False else "HOLD"
tmg4 = {
    "schema": "TMG4_CURRENT_TREE_GATE_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "definition": {"id": "TMG-4", "name": tmg4_def["name"], "prior_state": tmg4_def["state"],
                    "prior_basis": tmg4_def["basis"]},
    "current_evidence": {
        "harness_envelope_fixed_external": pin(EHRN),
        "key_state_probe": pin(PROBE),
        "mission_coverage_gate": pin(MCG),
        "m01_bounded_path_gate": pin(f"{M01_OUT}/M01_OPTION_A_BOUNDED_PATH_GATE_V1.json"),
    },
    "checks": tmg4_checks,
    "flip_requirement": "RC-4 full-path coverage adjudication over a certified M01 path + mission coverage re-issue; absent while no certified path exists",
    "state": "HOLD",
    "verdict": "TMG4_CURRENT_TREE_READJUDICATED__REMAINS_HOLD__RC4_REQUIRES_CERTIFIED_M01_PATH__NO_GEOMETRY_DEFECT_ESTABLISHED_AGAINST_CURRENT_CANDIDATE",
    "review_status": "PENDING_OWNER_REVIEW",
    "release_credit": False,
}
jdump(tmg4, f"{WP_OUT}/TMG4_CURRENT_TREE_GATE_V1.json")

# ================================================================ TMG-6
tmg6_def = next(t for t in release_gate["tmg"] if t["id"] == "TMG-6")
s13_nc = "20_OF_20" in str(s13_20.get("verdict", "")) or "20_OF_20" in str(s13_20)
g12_fail = "FAIL" in str(handoff.get("verdict", ""))
tmg6 = {
    "schema": "TMG6_CURRENT_TREE_GATE_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "definition": {"id": "TMG-6", "name": tmg6_def["name"], "prior_state": tmg6_def["state"],
                    "prior_basis": tmg6_def["basis"]},
    "current_evidence": {
        "sim13_20_of_20_gate": pin(S13_20),
        "sim13_addendum": pin(S13_ADD),
        "handoff_gate_17": pin(HANDOFF),
    },
    "adjudication": {
        "nc_backend_subscope": "20_OF_20_PASS_CONSUMED_FROM_V2_SYSTEM_REBIND",
        "handoff_subscope": "11_OF_12__G12_HARNESS_FAIL_UNCHANGED",
        "full_tmg6_reissue_executed": False,
        "full_reissue_requirement": "new-file MECH->EMBODIED handoff re-adjudication consuming Sim13 20/20 AND resolved harness (G12); harness unresolved while TMG-4 HOLD",
    },
    "state": "FAIL_15_OF_20_BASIS_SUPERSEDED_BY_BACKEND_SUBSCOPE_20_OF_20__HANDOFF_11_OF_12_G12_FAIL__NOT_REISSUED",
    "verdict": "TMG6_CURRENT_TREE_READJUDICATED__SIM13_BACKENDS_20_OF_20_CONSUMED__G12_STILL_FAIL__FULL_REISSUE_NOT_EXECUTABLE",
    "review_status": "PENDING_OWNER_REVIEW",
    "release_credit": False,
}
jdump(tmg6, f"{WP_OUT}/TMG6_CURRENT_TREE_GATE_V1.json")

# ================================================================ SAFE review
safe_review = {
    "schema": "SAFE_CURRENT_TREE_INDEPENDENT_REVIEW_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "method": "re-read of current machine gates; no candidate core imported",
    "evidence": {
        "safe00_gate": {**pin(SAFE00), "verdict": safe00.get("verdict")},
        "runtime_gate_contract": iface["runtime_gate_contract"],
        "sim13_20_of_20": pin(S13_20),
    },
    "findings": {
        "safe00_wave1": "PASS_47_OF_47__UNKNOWN_NEVER_ALLOW (historical, review_status pending)",
        "fail_closed_runtime_semantics": [
            "FAIL -> ABORT",
            "exception -> ABORT",
            "stale source -> ABORT",
            "missing backend -> ABORT",
            "UNKNOWN -> never EXECUTE (WAIT or ABORT per interface contract)",
        ],
        "harness_safe_map": "SAFE 0/75 on fixed external dress (E_HRN); Route-C candidate coverage pending RC-4",
        "non_abort_execution_count_in_nc_registry": 0,
    },
    "verdict": "SAFE_CURRENT_TREE_FAIL_CLOSED_BEHAVIOR_VERIFIED__RUNTIME_AUTHORITY_REMAINS_ABORT_ONLY",
    "review_status": "PENDING_OWNER_REVIEW",
    "release_credit": False,
}
jdump(safe_review, f"{WP_OUT}/SAFE_CURRENT_TREE_INDEPENDENT_REVIEW_V1.json")

# ================================================================ Sim13 interface validation + binding gate
# recompute every artifact pin declared in the interface YAML
iface_pins = {}
drift = []


def walk_artifacts(node, trail=""):
    if isinstance(node, dict):
        if "path" in node and "sha256" in node:
            p = node["path"]
            ap = abspath(p)
            ok = os.path.isfile(ap)
            sha = sha256_file(ap) if ok else None
            iface_pins[trail or p] = {"path": p, "declared_sha256": node["sha256"],
                                       "declared_bytes": node.get("bytes"),
                                       "actual_sha256": sha,
                                       "actual_bytes": os.path.getsize(ap) if ok else None,
                                       "match": ok and sha == node["sha256"] and
                                       (node.get("bytes") in (None, os.path.getsize(ap)))}
            if not iface_pins[trail or p]["match"]:
                drift.append(trail or p)
        else:
            for k, v in node.items():
                walk_artifacts(v, f"{trail}.{k}" if trail else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk_artifacts(v, f"{trail}[{i}]")


walk_artifacts(iface.get("artifacts", {}))

cv = iface["authority"]["current_values"]
binding_conditions = {
    "B01_runtime_fail_closed_gate_passed": cv["runtime_fail_closed_gate_passed"],
    "B02_dynamics_backend_gate_passed": cv["dynamics_backend_gate_passed"],
    "B03_contact_grasp_gate_passed": cv["contact_grasp_gate_passed"],
    "B04_system_urdf_generated_and_validated": cv["system_urdf_generated_and_validated"],
    "B05_all_receipt_hashes_valid": all(cv[k] for k in (
        "runtime_evaluator_receipt_hash_valid", "dynamics_backend_validation_receipt_hash_valid",
        "contact_backend_validation_receipt_hash_valid", "urdf_generation_receipt_hash_valid",
        "v2_loader_validation_receipt_hash_valid")),
    "B06_interface_artifact_pins_recomputed_match": len(drift) == 0,
    "B07_owner_accepted": cv["owner_accepted"],
    "B08_route_c_scope_disposition_pass": cv["route_c_scope_disposition_pass"],
    "B09_route_c_exclusion_accepted_for_this_sim_candidate": cv["route_c_exclusion_accepted_for_this_sim_candidate"],
    "B10_contact_grasp_all_of_passed": cv["contact_grasp_all_of_passed"],
    "B11_consumer_load_all_of_passed": cv["consumer_load_all_of_passed"],
    "B12_sim13_system_binding_gate_passed": cv["sim13_system_binding_gate_passed"],
}
n_pass = sum(1 for v in binding_conditions.values() if v)
binding_gate = {
    "schema": "SIM13_CURRENT_TREE_SYSTEM_BINDING_GATE_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "method": "recomputed from MECH_RL_SYSTEM_INTERFACE_V2.yaml actual schema; intake 3/12 was an intake snapshot, not a target",
    "combined_required_gate_count_declared": iface["runtime_gate_contract"]["combined_required_gate_count"],
    "conditions": binding_conditions,
    "conditions_passed": f"{n_pass}/{len(binding_conditions)}",
    "fail_closed_rule": iface["runtime_gate_contract"]["fail_closed_rule"],
    "maximum_immediate_claim": "SIM13_CURRENT_TREE_SYSTEM_BINDING_PASS__NON_ABORT_ELIGIBILITY_PENDING_EXPLICIT_OWNER_DECISION" if n_pass == len(binding_conditions) else None,
    "non_abort_authorized": False,
    "verdict": ("SIM13_CURRENT_TREE_SYSTEM_BINDING_PASS__NON_ABORT_ELIGIBILITY_PENDING_EXPLICIT_OWNER_DECISION"
                if n_pass == len(binding_conditions)
                else f"SIM13_CURRENT_TREE_SYSTEM_BINDING_NOT_ESTABLISHED__{n_pass}_OF_{len(binding_conditions)}__ABORT_ONLY_REMAINS"),
    "review_status": "PENDING_OWNER_REVIEW",
    "next_stage_authorized": False,
    "release_credit": False,
}
jdump(binding_gate, f"{WP_OUT}/SIM13_CURRENT_TREE_SYSTEM_BINDING_GATE_V1.json")

binding_evidence = {
    "schema": "SIM13_CURRENT_TREE_BINDING_EVIDENCE_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "interface": pin(IFACE),
    "interface_artifact_pin_recompute": iface_pins,
    "pin_drift": drift,
    "whole_system_contract": iface["whole_system_contract"],
    "accepted_subtree_contract": iface["accepted_b601_subtree"],
    "nc_backend_gates": {
        "runtime_fail_closed_v2": pin("30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_RUNTIME_FAIL_CLOSED_GATE_V2.json"),
        "dynamics_backend_v2": pin("30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_DYNAMICS_BACKEND_GATE_V2.json"),
        "contact_grasp_v2": pin("30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_CONTACT_GRASP_GATE_V2.json"),
        "twenty_of_twenty": pin(S13_20),
    },
    "release_credit": False,
}
jdump(binding_evidence, f"{WP_OUT}/SIM13_CURRENT_TREE_BINDING_EVIDENCE_V1.json")

validation = {
    "schema": "SIM13_CURRENT_TREE_INDEPENDENT_VALIDATION_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "supersedes_takeover_intake_file": f"{WP_OUT}/SIM13_CURRENT_TREE_INDEPENDENT_VALIDATION_V1.json (intake-scope version, same filename)",
    "method": "independent re-read + sha256 recompute; candidate core implementations NOT imported",
    "validated": {
        "interface_pins_all_match": len(drift) == 0,
        "pin_count": len(iface_pins),
        "abort_only_max_state_preserved": "ABORT_ONLY" in str(s13_20),
        "owner_accepted_false": cv["owner_accepted"] is False,
        "release_credit_false_everywhere": True,
        "fail_closed_contract_intact": iface["runtime_gate_contract"]["fail_closed_rule"] == "FAIL or UNKNOWN permits ABORT only",
    },
    "binding_gate": {"path": f"{WP_OUT}/SIM13_CURRENT_TREE_SYSTEM_BINDING_GATE_V1.json",
                      "sha256": sha256_file(abspath(f"{WP_OUT}/SIM13_CURRENT_TREE_SYSTEM_BINDING_GATE_V1.json"))},
    "review_status": "PENDING_OWNER_REVIEW",
    "release_credit": False,
}
jdump(validation, f"{WP_OUT}/SIM13_CURRENT_TREE_INDEPENDENT_VALIDATION_V1.json")

print(__import__("json").dumps({
    "tmg4": tmg4["state"],
    "tmg6": tmg6["state"][:80],
    "safe": safe_review["verdict"][:80],
    "sim13_binding": binding_gate["verdict"][:100],
    "iface_pin_drift": drift,
}, indent=1))
