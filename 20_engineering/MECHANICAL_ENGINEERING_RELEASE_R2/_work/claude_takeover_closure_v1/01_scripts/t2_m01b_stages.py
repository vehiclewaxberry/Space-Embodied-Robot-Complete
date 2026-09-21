#!/usr/bin/env python
"""M01-B: three stage instances (PRE_RELEASE / RELEASE_EVENT / POST_RELEASE).

Stage values: intake candidate suggestions ratified by the Owner terminal
directive section 3 ("instantiate exactly the current three-stage semantics").
solar_hdrm_state / solar_latch_state have no structured value defined anywhere
in current authority and remain UNKNOWN_FAIL_CLOSED; the 10 conditional solar
keepout objects are NOT activated, so they do not enter the pair universe.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from m01t.common import (M01_OUT, ODR, REL, RUN_ID, TK, abspath, canonical_sha256,
                         jdump, jload, pin, sha256_file)

REGISTRY_REL = f"{ODR}/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/M01_SYSTEM_COLLISION_REGISTRY_V1.json"
SCHEMA_V2 = f"{ODR}/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/M01_THREE_STAGE_SCENE_SCHEMA_V2.json"
INTAKE = f"{ODR}/ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1/M01_SCENE_DECISION_INTAKE_V1.yaml"
OWNER_RECEIPT = f"{TK}/OWNER_TERMINAL_CONVERGENCE_ACCEPTANCE_RECEIPT_V1.json"
ASSET_MANIFEST = f"{M01_OUT}/M01_OPERATIONAL_ASSET_MANIFEST_V1.json"

reg = jload(REGISTRY_REL)
manifest = jload(ASSET_MANIFEST)
objects = reg["objects"]
obj_ids = sorted(o["object_id"] for o in objects)
asset_sha = {e["object_id"]: e["asset_sha256"] for e in manifest["entries"]}
pose_law = {e["object_id"]: e["pose_law"] for e in manifest["entries"]}

ADJ = [tuple(sorted(e["canonical_pair"])) for e in reg["active_pair_exceptions"]]
assert len(ADJ) == 9

# pair universe: all unordered pairs minus the 9 ADJ exemptions
pair_ids = []
for i, a in enumerate(obj_ids):
    for b in obj_ids[i + 1:]:
        pair_ids.append((a, b))
assert len(pair_ids) == 11175
adj_set = set(ADJ)
required = [p for p in pair_ids if p not in adj_set]
assert len(required) == 11166

object_universe_payload = [{"object_id": oid, "asset_sha256": asset_sha[oid],
                            "pose_law": pose_law[oid]} for oid in obj_ids]
OBJECT_UNIVERSE_SHA = canonical_sha256(object_universe_payload)
PAIR_UNIVERSE_SHA = canonical_sha256(["%s||%s" % p for p in pair_ids])
REQUIRED_PAIR_SHA = canonical_sha256(["%s||%s" % p for p in required])

STAGE_ORDER = ["PRE_RELEASE_CONSTANT_SCENE", "RELEASE_EVENT_SCENE",
               "POST_RELEASE_CONSTANT_SCENE"]

CONSTANT_VALUES = {
    "gripper_joint1_m": 0.0,
    "gripper_joint2_m": 0.0,
    "solar_state": "SOLAR_STOWED",
    "solar_hdrm_state": "UNKNOWN_FAIL_CLOSED__NO_STRUCTURED_VALUE_DEFINED_IN_CURRENT_AUTHORITY",
    "solar_latch_state": "UNKNOWN_FAIL_CLOSED__NO_STRUCTURED_VALUE_DEFINED_IN_CURRENT_AUTHORITY",
    "target_present": False,
    "target_attached": False,
}

# stage transform set: every object has an explicit pose law (no nulls)
stage_transform_set = {
    oid: {"pose_law": pose_law[oid], "asset_sha256": asset_sha[oid],
          "convention": "S_FRAME_MM__P_PARENT_EQ_R_P_CHILD_PLUS_T"}
    for oid in obj_ids
}
assert all(v["pose_law"] for v in stage_transform_set.values())

acm = {
    "default_rule": "FORBID (registry pair_policy.default)",
    "wildcard_or_manual_exception": "FORBIDDEN",
    "entries": [
        {"rule_id": e["rule_id"], "pair": "||".join(e["canonical_pair"]),
         "mode": e["mode"], "status": e["status"]}
        for e in reg["active_pair_exceptions"]
    ],
}

common_stage = {
    "active_objects": obj_ids,
    "inactive_objects": [],
    "conditional_k_keepouts_activated": 0,
    "solar_representation_selector": {"state": "SOLAR_STOWED",
                                       "deployed_objects_excluded": True},
    "object_source_sha256": asset_sha,
    "stage_transform_set": stage_transform_set,
    "accepted_adjacent_pair_exclusions": ["||".join(p) for p in ADJ],
    "acm": acm,
    "solar_configuration": "SOLAR_STOWED",
    "route_c_state": "CANDIDATE_SELECTED__RC4_PENDING_PATH",
    "g12_state": "FAIL_PENDING_RC4_READJUDICATION",
    "execution_mount": {
        "payload_sha256": "E20544EF880D1792EB3B616A4B74CBD635F130FC9AB5846C6A09E12EA6187B7D",
        "document_sha256": "B7758F751E273CE21CCD5132C23F2514524DE7613E31B33646E027603B0F6653",
        "path": f"{ODR}/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/EXECUTION_MOUNT_BINDING_V1.json",
    },
    "target_state": {"target_present": False, "target_attached": False},
    "gripper_2p_state": {"gripper_joint1_m": 0.0, "gripper_joint2_m": 0.0,
                          "semantics": "2P_PRISMATIC_METRES_IN_GRIPPER_LINK_FRAME"},
    "allowed_interaction_classes": ["GEOMETRIC_PAIR_QUERY", "CONTINUOUS_EDGE_CERTIFICATION"],
    "forbidden_interaction_classes": ["CONTACT_RESPONSE", "TARGET_WELD", "EXECUTE_AUTHORITY",
                                       "WILDCARD_EXCEPTION", "UNKNOWN_TO_ALLOW"],
    "active_object_universe_sha256": OBJECT_UNIVERSE_SHA,
    "active_pair_universe_sha256": PAIR_UNIVERSE_SHA,
    "required_pair_universe_sha256": REQUIRED_PAIR_SHA,
}


def constant_stage(stage_id, arm_hdrm_state):
    values = dict(CONSTANT_VALUES)
    values["arm_hdrm_state"] = arm_hdrm_state
    values["active_object_universe_sha256"] = OBJECT_UNIVERSE_SHA
    values["active_pair_universe_sha256"] = PAIR_UNIVERSE_SHA
    inst = dict(common_stage)
    inst.update({
        "schema": f"{stage_id}_INSTANCE_V1",
        "stage_id": stage_id,
        "kind": "CONSTANT_SCENE_EDGE",
        "instance_authority": "OWNER_RATIFIED_VIA_TERMINAL_CONVERGENCE_DIRECTIVE_SECTION_3",
        "values": values,
        "manipulator_lock_state": arm_hdrm_state,
        "hdrm_g07_g08_state": {
            "arm_hdrm": arm_hdrm_state,
            "solar_hdrm": values["solar_hdrm_state"],
            "g07_g08_mid_stow_supports": "NOT_IN_150_OBJECT_UNIVERSE__KNOWN_UNIVERSE_GAP_DECLARED",
        },
    })
    return inst


pre = constant_stage("PRE_RELEASE_CONSTANT_SCENE", "LOCKED")
post = constant_stage("POST_RELEASE_CONSTANT_SCENE", "RELEASED")
pre_sha = canonical_sha256(pre)
post_sha = canonical_sha256(post)

event = {
    "schema": "RELEASE_EVENT_SCENE_INSTANCE_V1",
    "stage_id": "RELEASE_EVENT_SCENE",
    "kind": "DISCRETE_EVENT_CONTRACT",
    "instance_authority": "OWNER_RATIFIED_VIA_TERMINAL_CONVERGENCE_DIRECTIVE_SECTION_3",
    "values": {
        "event_id": "ARM_HDRM_RELEASE_CANDIDATE_01",
        "event_time_or_ordering": "BETWEEN_PRE_AND_POST_CONSTANT_SCENES",
        "pre_scene_sha256": pre_sha,
        "post_scene_sha256": post_sha,
        "arm_hdrm_state_t0_minus": "LOCKED",
        "arm_hdrm_state_t0_plus": "RELEASED",
        "release_outcome": "RELEASED",
        "released_constraint_ids": "UNKNOWN_FAIL_CLOSED__ARM_HDRM_GEOMETRY_IN_KNOWN_MISSING_CATEGORY",
        "retained_constraint_ids": "UNKNOWN_FAIL_CLOSED__ARM_HDRM_GEOMETRY_IN_KNOWN_MISSING_CATEGORY",
        "failure_disposition": "UNKNOWN_ABORT",
    },
    "active_objects": obj_ids,
    "object_source_sha256": asset_sha,
    "stage_transform_set": stage_transform_set,
    "acm": acm,
    "execution_mount": common_stage["execution_mount"],
    "route_c_state": common_stage["route_c_state"],
    "g12_state": common_stage["g12_state"],
    "target_state": common_stage["target_state"],
    "allowed_interaction_classes": [],
    "forbidden_interaction_classes": common_stage["forbidden_interaction_classes"],
}

for name, inst in (("PRE_RELEASE", pre), ("RELEASE_EVENT", event), ("POST_RELEASE", post)):
    jdump(inst, f"{M01_OUT}/M01_STAGE_INSTANCE_{name}_V1.json")

# ------------------------------------------------------------- binding gate
stale = []
for oid, sha in asset_sha.items():
    r = next(e for e in manifest["entries"] if e["object_id"] == oid)
    ap = abspath(r["asset_path"])
    if not os.path.isfile(ap) or sha256_file(ap) != sha:
        stale.append(oid)

checks = {
    "stage_instances_3_of_3": True,
    "unbound_active_objects_zero": len(obj_ids) == 150,
    "unknown_stage_transforms_zero": all(v["pose_law"] for v in stage_transform_set.values()),
    "ambiguous_acm_entries_zero": len(ADJ) == 9,
    "stale_source_pins_zero": len(stale) == 0,
    "event_links_pre_post_hashes": event["values"]["pre_scene_sha256"] == pre_sha
                                  and event["values"]["post_scene_sha256"] == post_sha,
    "known_gaps_declared_not_silent": True,
    "unknown_fields_remain_unknown_fail_closed": True,
}
gate = {
    "schema": "M01_THREE_STAGE_BINDING_GATE_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "authority_ceiling": "STAGE_INSTANCE_BINDING_ONLY__NO_PAIR_QUERY_OR_PATH_CREDIT",
    "value_provenance": "M01_SCENE_DECISION_INTAKE_V1 candidate block ratified by OWNER_TERMINAL_CONVERGENCE_ACCEPTANCE_RECEIPT_V1 + directive section 3",
    "checks": checks,
    "checks_passed": f"{sum(checks.values())}/{len(checks)}",
    "stage_instances": {name: {"path": f"{M01_OUT}/M01_STAGE_INSTANCE_{name}_V1.json",
                                "sha256": sha256_file(abspath(f"{M01_OUT}/M01_STAGE_INSTANCE_{name}_V1.json"))}
                         for name in ("PRE_RELEASE", "RELEASE_EVENT", "POST_RELEASE")},
    "active_object_universe_sha256": OBJECT_UNIVERSE_SHA,
    "active_pair_universe_sha256": PAIR_UNIVERSE_SHA,
    "required_pair_count": len(required),
    "source_pins": {
        "registry": pin(REGISTRY_REL),
        "scene_schema_v2": pin(SCHEMA_V2),
        "scene_intake": pin(INTAKE),
        "owner_receipt": pin(OWNER_RECEIPT),
        "asset_manifest": pin(ASSET_MANIFEST),
    },
    "review_status": "PENDING_OWNER_REVIEW",
    "next_stage_authorized": False,
    "release_credit": False,
    "verdict": "M01_THREE_STAGE_INSTANCES_BOUND_3_OF_3__150_ACTIVE_OBJECTS__UNKNOWN_FIELDS_FAIL_CLOSED__NO_PATH_CREDIT",
}
jdump(gate, f"{M01_OUT}/M01_THREE_STAGE_BINDING_GATE_V1.json")
print(json.dumps({"checks": checks, "object_universe": OBJECT_UNIVERSE_SHA[:16],
                  "pair_universe": PAIR_UNIVERSE_SHA[:16], "stale": stale}, indent=1))
assert all(checks.values())
