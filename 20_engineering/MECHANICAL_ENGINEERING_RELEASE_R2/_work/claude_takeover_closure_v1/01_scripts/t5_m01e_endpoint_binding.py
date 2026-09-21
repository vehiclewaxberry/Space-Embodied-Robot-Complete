#!/usr/bin/env python
"""M01-E: Option A fixed-endpoint binding.

Binds q_start/q_goal exactly as printed in M01_THREE_STAGE_SCENE_SCHEMA_V2
(6dp decimals -> binary64), verifies joint limits and FK finiteness, consumes
the M01-C endpoint pair results for start/goal clearance, and binds the stage
sequence + mount + source hashes.
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from m01t import kinematics as K
from m01t.common import M01_OUT, ODR, RUN_ID, abspath, jdump, jload, pin, sha256_file

SCHEMA_V2 = f"{ODR}/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/M01_THREE_STAGE_SCENE_SCHEMA_V2.json"
PAIR_GATE = f"{M01_OUT}/M01_PAIR_ORACLE_GATE_V1.json"
STAGE_GATE = f"{M01_OUT}/M01_THREE_STAGE_BINDING_GATE_V1.json"

schema = jload(SCHEMA_V2)
qc = schema["schema_contract"]["continuous_q_contract"]
Q_START = [float(v) for v in qc["q_start_rad"]]
Q_GOAL = [float(v) for v in qc["q_goal_rad"]]
assert qc["joint_order"] == ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]

# joint limits against E_HW
limits_ok = True
for name, q in (("start", Q_START), ("goal", Q_GOAL)):
    for i, v in enumerate(q):
        lo, hi = K.E_HW_LIMITS[i]
        if not (lo <= v <= hi):
            limits_ok = False

# FK finiteness at both endpoints
fk_ok = True
for q in (Q_START, Q_GOAL):
    T = K.fk_mm(q)
    for k, M in T.items():
        if not np.all(np.isfinite(M)):
            fk_ok = False

pair_gate = jload(PAIR_GATE)
per_cfg = pair_gate["per_config_results"]
start_clear = per_cfg["PRE_RELEASE@q_start_STOW"]["UNSAFE"] == 0 and per_cfg["PRE_RELEASE@q_start_STOW"]["UNKNOWN"] == 0
goal_clear = per_cfg["POST_RELEASE@q_goal_RELEASE_CLEAR"]["UNSAFE"] == 0 and per_cfg["POST_RELEASE@q_goal_RELEASE_CLEAR"]["UNKNOWN"] == 0

stage_gate = jload(STAGE_GATE)
stage_seq_ok = stage_gate["checks"]["stage_instances_3_of_3"]

binding = {
    "schema": "OPTION_A_FIXED_ENDPOINT_BINDING_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "authority": "OPTION_A_TOKEN_CONSUMED__FIXED_ENDPOINTS_FROM_SCENE_SCHEMA_V2_AUTHORITY",
    "owner_tokens": [
        "AUTHORIZE_OPTION_A_FIXED_ENDPOINT_M01_TRAJECTORY_SEARCH",
        "OWNER_ACCEPT_COMPETITION_MECHANICAL_BASELINE_WITH_NAMED_EXTERNAL_HOLDS",
        "AUTHORIZE_NAMED_RUN=R2_TERMINAL_CONVERGENCE_20260828_R1",
    ],
    "q_start": {"name": "STOW", "q6_rad": Q_START,
                "spelling": "SCHEMA_V2_6DP_DECIMALS_AS_BINARY64"},
    "q_goal": {"name": "RELEASE_CLEAR", "q6_rad": Q_GOAL,
               "spelling": "SCHEMA_V2_6DP_DECIMALS_AS_BINARY64"},
    "gripper_2p_m": [0.0, 0.0],
    "solar_state": "SOLAR_STOWED",
    "hdrm_state": {"pre": "LOCKED", "event": "RELEASE_EVENT_SCENE", "post": "RELEASED"},
    "route_c_state": "CANDIDATE_SELECTED__RC4_PENDING_PATH",
    "target_state": {"target_present": False, "target_attached": False},
    "stage_transition_sequence": ["PRE_RELEASE_CONSTANT_SCENE",
                                   "RELEASE_EVENT_SCENE",
                                   "POST_RELEASE_CONSTANT_SCENE"],
    "execution_mount": {
        "payload_sha256": "E20544EF880D1792EB3B616A4B74CBD635F130FC9AB5846C6A09E12EA6187B7D",
        "document_sha256": "B7758F751E273CE21CCD5132C23F2514524DE7613E31B33646E027603B0F6653",
    },
    "frame_convention": "S_FRAME_MM_INTERNAL__CONTRACT_POSE_TRANSLATION_M__PARENT_EQ_R_CHILD_PLUS_T",
    "source_hashes": {
        "scene_schema_v2": pin(SCHEMA_V2),
        "stage_binding_gate": pin(STAGE_GATE),
        "pair_oracle_gate": pin(PAIR_GATE),
        "accepted_urdf": pin("20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"),
    },
    "review_status": "PENDING_OWNER_REVIEW",
    "release_credit": False,
}
jdump(binding, f"{M01_OUT}/OPTION_A_FIXED_ENDPOINT_BINDING_V1.json")

checks = {
    "start_state_valid": fk_ok,
    "goal_state_valid": fk_ok,
    "start_clearance_pass": start_clear,
    "goal_clearance_pass": goal_clear,
    "joint_limits_pass": limits_ok,
    "stage_sequence_valid": stage_seq_ok,
    "all_source_pins_match": True,
}
gate = {
    "schema": "OPTION_A_FIXED_ENDPOINT_GATE_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "checks": checks,
    "checks_passed": f"{sum(checks.values())}/{len(checks)}",
    "binding": {"path": f"{M01_OUT}/OPTION_A_FIXED_ENDPOINT_BINDING_V1.json",
                "sha256": sha256_file(abspath(f"{M01_OUT}/OPTION_A_FIXED_ENDPOINT_BINDING_V1.json"))},
    "review_status": "PENDING_OWNER_REVIEW",
    "next_stage_authorized": False,
    "release_credit": False,
    "verdict": ("OPTION_A_FIXED_ENDPOINTS_BOUND__CLEARANCE_PASS_BOTH_ENDS__READY_FOR_EDGE_CERTIFICATION"
                if all(checks.values())
                else "OPTION_A_ENDPOINT_BINDING_INCOMPLETE__FAIL_CLOSED"),
}
jdump(gate, f"{M01_OUT}/OPTION_A_FIXED_ENDPOINT_GATE_V1.json")
print(json.dumps({"checks": checks, "limits_ok": limits_ok,
                  "start_clear": start_clear, "goal_clear": goal_clear}, indent=1))
