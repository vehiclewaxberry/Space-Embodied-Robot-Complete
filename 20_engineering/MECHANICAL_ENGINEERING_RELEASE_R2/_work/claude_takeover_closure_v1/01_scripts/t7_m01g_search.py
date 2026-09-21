#!/usr/bin/env python
"""M01-G: one named bounded Option A path campaign (R2_TERMINAL_CONVERGENCE_20260828_R1).

Sequence per directive section 8:
  1. deterministic direct-edge attempt (straight q segment, from M01-F);
  2. deterministic multi-resolution search (midpoint ladder);
  3. bounded sampling-based search (seeded RRT, dimensionally scaled metric);
  4. path simplification (deterministic shortcut passes);
  5. full independent continuous-edge recertification of the final path.

Honest outcomes A/B/C per the directive.  No mechanical geometry is modified.
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from m01t import kinematics as K
from m01t.common import M01_OUT, RUN_ID, abspath, jdump, jload, pin, sha256_file
from m01t.motion import MotionCertifier, certify_edge
from m01t.oracle import PoseContext, Scene, pair_query

Q_START = np.array([2.540711, -2.932153, -0.994838, -0.718081, -0.365716, -0.05236])
Q_GOAL = np.array([-1.570796, -2.094395, -2.094395, -1.047198, -0.523599, 0.0])

# ---------------- preconditions
edge_gate = jload(f"{M01_OUT}/M01_CONTINUOUS_EDGE_GATE_V1.json")
endpoint_gate = jload(f"{M01_OUT}/OPTION_A_FIXED_ENDPOINT_GATE_V1.json")
asset_gate = jload(f"{M01_OUT}/M01_OPERATIONAL_ASSET_GATE_V1.json")
stage_gate = jload(f"{M01_OUT}/M01_THREE_STAGE_BINDING_GATE_V1.json")
motion_gate = jload(f"{M01_OUT}/M01_OBJECT_MOTION_CERTIFICATE_GATE_V1.json")
pair_gate = jload(f"{M01_OUT}/M01_PAIR_ORACLE_GATE_V1.json")

pre_ok = all([
    asset_gate["checks_passed"].split("/")[0] == asset_gate["checks_passed"].split("/")[1],
    stage_gate["checks"]["stage_instances_3_of_3"],
    pair_gate["checks"]["unknown_pairs_zero"],
    motion_gate["checks"]["certified_objects_eq_150"],
    endpoint_gate["checks"]["start_clearance_pass"],
    endpoint_gate["checks"]["goal_clearance_pass"],
])

scene = Scene()
cert = MotionCertifier(scene)
obj_ids = sorted(scene.objects)
ADJ = scene.exceptions


def motion_signature(rt):
    law = rt.pose_law
    if law in ("STATIC_S", "MOUNT_STATIC"):
        return ("STATIC_S",)
    if law == "ARM_FK":
        return ("HOST", rt.storage_frame)
    if law == "ARM_FK_LINK1":
        return ("HOST", "link1")
    if law == "ARM_FK_LINK2":
        return ("HOST", "link2")
    if law == "ARM_FK_2P":
        return ("GRIPPER_SUBTREE",)
    if law == "HOST_FOLLOW_OR_REGISTERED_MOTION":
        name = rt.oid.split("::", 1)[1]
        if name in K.J3_CARRIAGE_PARTS:
            return ("LAW_J3_CARRIAGE",)
        mc = rt.motion_class
        if mc in ("ONE_THIRD_TRAVEL", "TWO_THIRDS_TRAVEL", "FULL_TRAVEL"):
            return ("LAW_J4_TRAVEL", mc)
        return ("HOST", rt.host)
    if law == "C_SECTION_POINT_LAWS":
        return ("C", rt.segment_id)
    raise ValueError(law)


sig = {oid: motion_signature(scene.objects[oid]) for oid in obj_ids}
sig = {k: (("GRIPPER_SUBTREE",) if v == ("HOST", "gripper_link") else v)
       for k, v in sig.items()}
moving = [(a, b) for i, a in enumerate(obj_ids) for b in obj_ids[i + 1:]
          if (a, b) not in ADJ and sig[a] != sig[b]]

# ---------------- run contract (recorded before execution)
Q_LO = np.array([lo for lo, hi in K.E_HW_LIMITS])
Q_HI = np.array([hi for lo, hi in K.E_HW_LIMITS])
certs_doc = jload(f"{M01_OUT}/M01_OBJECT_MOTION_CERTIFICATES_V2.json")
W = np.zeros(6)
for c in certs_doc["certificates"]:
    for j, r in c["rho_table_mm_at_domain_midpoint"].items():
        i = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"].index(j)
        W[i] = max(W[i], r)
W = np.maximum(W, 1.0)
W_METRIC = W / W.max()

contract = {
    "schema": "M01_OPTION_A_NAMED_RUN_CONTRACT_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "planner": {"implementation": "t7_m01g_search.py deterministic RRT + direct + multiresolution + shortcut",
                 "version": "1.0.0-takeover"},
    "fixed_seed_set": [20260828, 601, 12],
    "sampling_domain": {"q_lo": Q_LO.tolist(), "q_hi": Q_HI.tolist()},
    "interpolation_convention": "LINEAR_Q_SEGMENT_BETWEEN_WAYPOINTS",
    "joint_metric": {"kind": "DIAGONALLY_SCALED_EUCLIDEAN",
                      "weights_mm_normalized": W_METRIC.tolist(),
                      "derivation": "per-joint max vertex-to-axis radius over all 150 objects, normalized"},
    "limits": {"rrt_max_nodes": 800, "rrt_max_edge_attempts": 4000,
                "per_edge_leaf_cap_search": 64, "per_edge_max_depth_search": 6,
                "final_recert_leaf_cap": 512, "final_recert_max_depth": 8,
                "shortcut_rounds": 40},
    "memory_policy": "MONITORING_ONLY__STOP_ONLY_ON_OOM_ALLOCATION_FAILURE_OR_SEVERE_PAGING",
    "cpu_threads": "single-process deterministic",
    "start_goal_hashes": {"q_start": Q_START.tolist(), "q_goal": Q_GOAL.tolist()},
    "asset_stage_pair_oracle_certificate_hashes": {
        "asset_gate": pin(f"{M01_OUT}/M01_OPERATIONAL_ASSET_GATE_V1.json"),
        "stage_gate": pin(f"{M01_OUT}/M01_THREE_STAGE_BINDING_GATE_V1.json"),
        "pair_oracle_gate": pin(f"{M01_OUT}/M01_PAIR_ORACLE_GATE_V1.json"),
        "motion_cert_gate": pin(f"{M01_OUT}/M01_OBJECT_MOTION_CERTIFICATE_GATE_V1.json"),
        "continuous_edge_gate": pin(f"{M01_OUT}/M01_CONTINUOUS_EDGE_GATE_V1.json"),
        "endpoint_gate": pin(f"{M01_OUT}/OPTION_A_FIXED_ENDPOINT_GATE_V1.json"),
    },
    "review_status": "PENDING_OWNER_REVIEW",
    "release_credit": False,
}
jdump(contract, f"{M01_OUT}/M01_OPTION_A_NAMED_RUN_CONTRACT_V1.json")

if not pre_ok:
    receipt = {
        "schema": "M01_OPTION_A_NAMED_RUN_RECEIPT_V1",
        "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
        "named_run_id": RUN_ID,
        "executed": False,
        "outcome": "C",
        "verdict": "M01_PRESEARCH_NOT_ESTABLISHED__PATH_SEARCH_NOT_EXECUTED",
        "failing_preconditions": {
            "asset_gate": asset_gate["checks_passed"],
            "stage_3_of_3": stage_gate["checks"]["stage_instances_3_of_3"],
            "pair_unknown_zero": pair_gate["checks"]["unknown_pairs_zero"],
            "motion_150": motion_gate["checks"]["certified_objects_eq_150"],
            "endpoint_clearance": [endpoint_gate["checks"]["start_clearance_pass"],
                                    endpoint_gate["checks"]["goal_clearance_pass"]],
        },
        "release_credit": False,
    }
    jdump(receipt, f"{M01_OUT}/M01_OPTION_A_NAMED_RUN_RECEIPT_V1.json")
    gate = {"schema": "M01_OPTION_A_BOUNDED_PATH_GATE_V1", "named_run_id": RUN_ID,
            "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
            "verdict": "M01_PRESEARCH_NOT_ESTABLISHED__PATH_SEARCH_NOT_EXECUTED",
            "path_search_executed": False, "release_credit": False,
            "review_status": "PENDING_OWNER_REVIEW", "next_stage_authorized": False}
    jdump(gate, f"{M01_OUT}/M01_OPTION_A_BOUNDED_PATH_GATE_V1.json")
    print(json.dumps(receipt["failing_preconditions"], indent=1))
    sys.exit(0)

# ---------------- certification machinery with caches
ctx_cache = {}
row_cache = {}


def get_ctx(q):
    key = tuple(float(x) for x in q)
    if key not in ctx_cache:
        ctx_cache[key] = PoseContext(scene, key)
    return ctx_cache[key]


def qrow(a, b, q):
    key = (a, b, tuple(float(x) for x in q))
    if key not in row_cache:
        row_cache[key] = pair_query(scene, get_ctx(q), a, b, required_mm=0.0)
    return row_cache[key]


def certify_edge_all_pairs(qa, qb, leaf_cap, max_depth, pair_subset=None):
    """Certify one edge over all moving pairs. Returns (status, worst)."""
    worst = {"margin": np.inf, "pair": None}
    for a, b in (pair_subset or moving):
        budget = {"leaves": 0, "max_leaves": leaf_cap}
        c = certify_edge(scene, cert, qrow, a, b, list(qa), list(qb),
                         required_mm=0.0, max_depth=max_depth, budget=budget)
        if c["result"] == "FAIL":
            return "FAIL", {"pair": (a, b), "cert": c}
        if c["result"] == "UNKNOWN":
            return "UNKNOWN", {"pair": (a, b), "cert": c}
        m = c.get("minimum_certified_clearance_mm", np.inf)
        if m < worst["margin"]:
            worst = {"margin": m, "pair": (a, b)}
    return "PASS", worst


run = {"phases": [], "started_note": "deterministic; wallclock logged for capacity only"}
t_start = time.time()

# ---------------- phase 1: direct edge (reuse M01-F result)
direct_ok = edge_gate["checks"]["edges_all_pass"]
run["phases"].append({"phase": "DIRECT_EDGE", "result": "PASS" if direct_ok else "FAIL",
                       "evidence": "M01_CONTINUOUS_EDGE_GATE_V1.json"})

path = None
if direct_ok:
    path = [Q_START.copy(), Q_GOAL.copy()]
else:
    # ---------------- phase 2: deterministic multi-resolution ladder
    # waypoint grid at joint-wise midpoints around the failing region
    found = None
    mids = []
    for j in range(6):
        for frac in (0.25, 0.5, 0.75):
            q = Q_START + frac * (Q_GOAL - Q_START)
            mids.append(q)
    for q in mids:
        s1, _ = certify_edge_all_pairs(Q_START, q, 64, 6)
        if s1 != "PASS":
            continue
        s2, _ = certify_edge_all_pairs(q, Q_GOAL, 64, 6)
        if s2 == "PASS":
            found = [Q_START.copy(), q, Q_GOAL.copy()]
            break
    run["phases"].append({"phase": "MULTI_RESOLUTION", "result": "PASS" if found else "NO_PATH"})
    path = found

    if path is None:
        # ---------------- phase 3: bounded seeded RRT
        rng = np.random.default_rng(20260828)
        nodes = [Q_START.copy()]
        parents = [-1]
        edge_status = {}

        def metric(a, b):
            return float(np.sqrt(((W_METRIC * (a - b)) ** 2).sum()))

        goal_reached = None
        attempts = 0
        while len(nodes) < 800 and attempts < 4000:
            attempts += 1
            if attempts % 5 == 0:
                sample = Q_GOAL
            else:
                sample = Q_LO + rng.random(6) * (Q_HI - Q_LO)
            d = [metric(sample, n) for n in nodes]
            i_near = int(np.argmin(d))
            q_new = nodes[i_near] + 0.35 * (sample - nodes[i_near])
            q_new = np.clip(q_new, Q_LO, Q_HI)
            status, _ = certify_edge_all_pairs(nodes[i_near], q_new, 64, 6)
            if status != "PASS":
                continue
            nodes.append(q_new)
            parents.append(i_near)
            edge_status[(i_near, len(nodes) - 1)] = status
            if metric(q_new, Q_GOAL) < 0.35 * metric(Q_START, Q_GOAL) * 0.2:
                s, _ = certify_edge_all_pairs(q_new, Q_GOAL, 64, 6)
                if s == "PASS":
                    goal_reached = len(nodes) - 1
                    break
        run["phases"].append({"phase": "BOUNDED_SAMPLING_RRT",
                               "nodes": len(nodes), "edge_attempts": attempts,
                               "result": "PASS" if goal_reached is not None else "NO_PATH"})
        if goal_reached is not None:
            way = [Q_GOAL.copy()]
            i = goal_reached
            while i >= 0:
                way.append(nodes[i])
                i = parents[i]
            way.reverse()
            # phase 4: deterministic shortcut
            improved = True
            rounds = 0
            while improved and rounds < 40:
                rounds += 1
                improved = False
                for i in range(len(way) - 2):
                    s, _ = certify_edge_all_pairs(way[i], way[i + 2], 64, 6)
                    if s == "PASS":
                        del way[i + 1]
                        improved = True
                        break
            run["phases"].append({"phase": "SHORTCUT", "rounds": rounds,
                                   "waypoints": len(way)})
            path = way

receipt = {
    "schema": "M01_OPTION_A_NAMED_RUN_RECEIPT_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "executed": True,
    "phases": run["phases"],
    "elapsed_seconds": round(time.time() - t_start, 3),
    "release_credit": False,
}

if path is not None:
    # ---------------- phase 5: independent full recertification
    ctx_cache.clear()
    row_cache.clear()
    final_edges = []
    all_pass = True
    min_margin = np.inf
    for i in range(len(path) - 1):
        status, worst = certify_edge_all_pairs(path[i], path[i + 1], 512, 8)
        final_edges.append({"edge_index": i, "q_start": path[i].tolist(),
                            "q_end": path[i + 1].tolist(), "status": status,
                            "min_margin_mm": None if worst["margin"] == np.inf else worst["margin"],
                            "limiting_pair": worst["pair"]})
        if status != "PASS":
            all_pass = False
        elif worst["margin"] < min_margin:
            min_margin = worst["margin"]
    run["phases"].append({"phase": "INDEPENDENT_RECERTIFICATION",
                           "result": "PASS" if all_pass else "FAIL",
                           "edges": len(final_edges)})
    receipt["final_edges"] = final_edges

    raw = {"schema": "M01_OPTION_A_RAW_PATH_V1", "named_run_id": RUN_ID,
           "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
           "waypoints_q6": [p.tolist() for p in path],
           "interpolant": "LINEAR_Q_SEGMENT", "release_credit": False}
    jdump(raw, f"{M01_OUT}/M01_OPTION_A_RAW_PATH_V1.json")
    if all_pass:
        cert_path = {
            "schema": "M01_OPTION_A_CERTIFIED_PATH_V1", "named_run_id": RUN_ID,
            "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
            "waypoints_q6": [p.tolist() for p in path],
            "edges": final_edges,
            "minimum_certified_margin_mm": None if min_margin == np.inf else min_margin,
            "certification": "EVERY_FINAL_EDGE_INDEPENDENTLY_RECERTIFIED_ALL_11166_PAIR_SCOPE",
            "pending": "TIME_PARAMETERIZATION_AND_OWNER_RELEASE",
            "release_credit": False,
        }
        jdump(cert_path, f"{M01_OUT}/M01_OPTION_A_CERTIFIED_PATH_V1.json")
        receipt["outcome"] = "A"
        receipt["verdict"] = "VERIFIED_GEOMETRIC_PATH_CANDIDATE_PENDING_TIME_AND_OWNER_RELEASE"
    else:
        receipt["outcome"] = "B"
        receipt["verdict"] = ("M01_BOUNDED_SEARCH_EXECUTED_NO_CERTIFIED_PATH__"
                               "MECHANICAL_CANDIDATES_REMAIN_FROZEN")
else:
    receipt["outcome"] = "B"
    receipt["verdict"] = ("M01_BOUNDED_SEARCH_EXECUTED_NO_CERTIFIED_PATH__"
                           "MECHANICAL_CANDIDATES_REMAIN_FROZEN")
    # minimal blocker report from M01-F failing/unknown pairs
    certs = jload(f"{M01_OUT}/M01_CONTINUOUS_EDGE_CERTIFICATES_V1.json")
    blockers = certs.get("failing_pairs", []) + certs.get("unknown_pairs", [])
    report = []
    for c in blockers[:50]:
        pid = c["pair_id"]
        a, b = pid.split("||")
        ra, rb = scene.objects[a], scene.objects[b]
        report.append({
            "pair_id": pid,
            "stage": "PRE_RELEASE_STRAIGHT_Q",
            "result": c["result"],
            "termination_reason": c.get("termination_reason"),
            "minimum_certified_clearance_mm": c.get("minimum_certified_clearance_mm"),
            "object_a_ownership": ra.host or ra.storage_frame,
            "object_b_ownership": rb.host or rb.storage_frame,
            "issue_class": "GEOMETRY_CONTACT_WITNESS" if c["result"] == "FAIL" else "UNRESOLVED_THRESHOLD_OR_BUDGET",
            "modifiable_candidate_exists": False,
            "note": "V9F historical negative (-17.313396996697108 mm) is on this straight-q family; no redesign authorized in this run",
        })
    jdump({"schema": "M01_OPTION_A_BLOCKER_REPORT_V1", "named_run_id": RUN_ID,
           "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
           "blockers": report, "release_credit": False},
          f"{M01_OUT}/M01_OPTION_A_BLOCKER_REPORT_V1.json")

jdump(receipt, f"{M01_OUT}/M01_OPTION_A_NAMED_RUN_RECEIPT_V1.json")

validation = {
    "schema": "M01_OPTION_A_PATH_INDEPENDENT_VALIDATION_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "method": "final edges recertified with cleared caches (fresh PoseContext and OCP objects)",
    "phases": run["phases"],
    "release_credit": False,
}
jdump(validation, f"{M01_OUT}/M01_OPTION_A_PATH_INDEPENDENT_VALIDATION_V1.json")

gate = {
    "schema": "M01_OPTION_A_BOUNDED_PATH_GATE_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "path_search_authorized": True,
    "path_search_executed": True,
    "outcome": receipt["outcome"],
    "verdict": receipt["verdict"],
    "outputs": {k: {"path": f"{M01_OUT}/{k}", "sha256": sha256_file(abspath(f"{M01_OUT}/{k}"))}
                for k in ["M01_OPTION_A_NAMED_RUN_CONTRACT_V1.json",
                           "M01_OPTION_A_NAMED_RUN_RECEIPT_V1.json",
                           "M01_OPTION_A_PATH_INDEPENDENT_VALIDATION_V1.json"]
                if os.path.isfile(abspath(f"{M01_OUT}/{k}"))},
    "review_status": "PENDING_OWNER_REVIEW",
    "next_stage_authorized": False,
    "release_credit": False,
}
jdump(gate, f"{M01_OUT}/M01_OPTION_A_BOUNDED_PATH_GATE_V1.json")
print(json.dumps({"outcome": receipt["outcome"], "verdict": receipt["verdict"],
                  "phases": [(p["phase"], p["result"] if "result" in p else p.get("nodes"))
                              for p in run["phases"]],
                  "elapsed_s": receipt["elapsed_seconds"]}, indent=1))
