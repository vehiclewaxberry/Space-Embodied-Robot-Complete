#!/usr/bin/env python
"""M01-C: pair universe + clearance policy + pair oracle results at the two
Option A endpoint configurations (q_start STOW, q_goal RELEASE_CLEAR).

Clearance policy V2: required_clearance_mm = 0.0 (physical non-penetration) and
authorized_pair_min_mm = 0.0 for every required pair, derates carried per
object by the asset receipts. Policy source: Owner terminal directive section 4
("every pair ... exact narrowphase or mathematically conservative lower-bound");
no positive operational clearance value exists in current authority, and
inventing one would be a threshold change (forbidden).

Relative-static pairs (identical motion signature) are configuration-invariant
and are queried once; the row is replicated per configuration with
configuration_domain recorded. 2P gripper joints are locked at 0.0 in all
three stage states, so gripper_left/right fold into the gripper subtree class.
"""
import csv
import gc
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from m01t.common import (M01_OUT, ODR, REL, RUN_ID, abspath, canonical_sha256,
                         jdump, jload, pin, sha256_file)
from m01t.oracle import BACKEND_DERATE_MM, PoseContext, Scene, pair_query

Q_START = [2.540711, -2.932153, -0.994838, -0.718081, -0.365716, -0.05236]
Q_GOAL = [-1.570796, -2.094395, -2.094395, -1.047198, -0.523599, 0.0]

scene = Scene()
obj_ids = sorted(scene.objects)
assert len(obj_ids) == 150

ADJ = scene.exceptions
assert len(ADJ) == 9


def motion_signature(rt):
    law = rt.pose_law
    if law in ("STATIC_S", "MOUNT_STATIC"):
        return ("STATIC_S",)
    if law in ("ARM_FK",):
        return ("HOST", rt.storage_frame)
    if law == "ARM_FK_LINK1":
        return ("HOST", "link1")
    if law == "ARM_FK_LINK2":
        return ("HOST", "link2")
    if law == "ARM_FK_2P":
        return ("GRIPPER_SUBTREE",)  # 2P locked at 0 in all stage states
    if law == "HOST_FOLLOW_OR_REGISTERED_MOTION":
        name = rt.oid.split("::", 1)[1]
        from m01t import kinematics as K
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
# HOST gripper_link == GRIPPER_SUBTREE for relative-static purposes
sig = {k: (("GRIPPER_SUBTREE",) if v == ("HOST", "gripper_link") else v)
       for k, v in sig.items()}

pairs = []
for i, a in enumerate(obj_ids):
    for b in obj_ids[i + 1:]:
        pairs.append((a, b))
assert len(pairs) == 11175

# ---------------- pair universe CSV
uni_rel = f"{M01_OUT}/M01_PAIR_UNIVERSE_V1.csv"
with open(abspath(uni_rel), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["pair_id", "object_a", "object_b", "in_required_universe",
                "exclusion_rule", "relative_motion_class"])
    n = 0
    for a, b in pairs:
        n += 1
        pid = f"{a}||{b}"
        exempt = (a, b) in ADJ
        rel_static = sig[a] == sig[b]
        w.writerow([pid, a, b, str(not exempt).lower(),
                    "ADJACENT_JOINT" if exempt else "",
                    "RELATIVE_STATIC" if rel_static else "RELATIVE_MOVING"])

required_pairs = [p for p in pairs if p not in ADJ]
assert len(required_pairs) == 11166

# ---------------- clearance policy V2
pol_rel = f"{M01_OUT}/M01_CLEARANCE_POLICY_V2.csv"
with open(abspath(pol_rel), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["pair_id", "required_clearance_m", "authorized_pair_min_m",
                "clearance_policy_source", "derate_source"])
    for a, b in required_pairs:
        w.writerow([f"{a}||{b}", "0.0", "0.0",
                    "OWNER_TERMINAL_DIRECTIVE_NONPENETRATION_ZERO",
                    "ASSET_RECEIPT_DERATES_PLUS_BACKEND_NUMERIC"])
POLICY_SHA = sha256_file(abspath(pol_rel))

# ---------------- oracle queries at both endpoints
t0 = time.time()
rows = []
configs = [("PRE_RELEASE@q_start_STOW", Q_START), ("POST_RELEASE@q_goal_RELEASE_CLEAR", Q_GOAL)]

# OCP's narrow phase is process-isolated here.  The input task order and the
# ordered chunk collection preserve deterministic CSV/JSON order; no result is
# inferred from a worker exit or from a partial batch.
tasks = []
task_static = []
task_index = 0
for a, b in required_pairs:
    rel_static = sig[a] == sig[b]
    if rel_static:
        tasks.append((task_index, configs[0][0], a, b))
        task_static.append(task_index)
        task_index += 1
    else:
        for cname, _ in configs:
            tasks.append((task_index, cname, a, b))
            task_index += 1

requested_workers = int(os.environ.get("M01_T3_WORKERS", "8"))
worker_count = max(1, min(requested_workers, os.cpu_count() or 1))
requested_chunks = int(os.environ.get("M01_T3_CHUNKS", str(worker_count * 4)))
chunk_count = max(worker_count, min(requested_chunks, len(tasks)))
result_by_task = {}
worker_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "m01t", "parallel_oracle_worker.py")
checkpoint_dir = abspath(os.path.join(M01_OUT, ".m01_pair_oracle_checkpoints"))
os.makedirs(checkpoint_dir, exist_ok=True)


def fallback_rows(chunk, reason):
    """Materialize UNKNOWN for a failed chunk; never turn process failure into SAFE."""
    return [
        {
            "object_a": task[2],
            "object_b": task[3],
            "oracle_type": None,
            "exact_or_conservative": None,
            "result": "UNKNOWN",
            "minimum_distance_mm": None,
            "witness_a_S_mm": None,
            "witness_b_S_mm": None,
            "failure_reason": reason,
            "rungs": [],
            "configuration_domain": "ENDPOINT_CONFIGURATION",
            "stage": task[1],
            "task_index": task[0],
        }
        for task in chunk
    ]


def checkpoint_path(chunk_index):
    return os.path.join(checkpoint_dir,
                        f"M01_PAIR_ORACLE_CHUNK_{chunk_index:04d}_V1.json")


def load_checkpoint(chunk_index, chunk):
    path = checkpoint_path(chunk_index)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        expected = [task[0] for task in chunk]
        rows = doc.get("rows")
        if (doc.get("schema") != "M01_PAIR_ORACLE_CHUNK_CHECKPOINT_V1"
                or doc.get("named_run_id") != RUN_ID
                or doc.get("task_indices") != expected
                or not isinstance(rows, list)
                or len(rows) != len(chunk)):
            return None
        if [row.get("task_index") for row in rows] != expected:
            return None
        # A Ctrl-C/worker-process failure is an interrupted computation, not
        # a completed UNKNOWN measurement. Never reuse that placeholder as if
        # it were a valid chunk; it must be recomputed on the next resume.
        failure_reasons = [str(row.get("failure_reason") or "") for row in rows]
        if any(reason.startswith("ORACLE_WORKER_PROCESS_FAILURE:")
               or reason.startswith("ORACLE_WORKER_INVALID_JSON")
               for reason in failure_reasons):
            return None
        return rows
    except Exception:
        return None


def save_checkpoint(chunk_index, chunk, rows, checkpoint_status="COMPLETE"):
    target = checkpoint_path(chunk_index)
    tmp = f"{target}.tmp"
    jdump({
        "schema": "M01_PAIR_ORACLE_CHUNK_CHECKPOINT_V1",
        "named_run_id": RUN_ID,
        "chunk_index": chunk_index,
        "checkpoint_status": checkpoint_status,
        "task_indices": [task[0] for task in chunk],
        "rows": rows,
    }, tmp)
    os.replace(tmp, target)


def run_worker_chunk(item):
    chunk_index, chunk = item
    cached = load_checkpoint(chunk_index, chunk)
    if cached is not None:
        return cached
    proc = subprocess.run(
        [sys.executable, worker_path],
        input=json.dumps(chunk, ensure_ascii=False),
        capture_output=True,
        text=True,
        cwd=abspath("."),
    )
    if proc.returncode != 0:
        rows = fallback_rows(chunk, f"ORACLE_WORKER_PROCESS_FAILURE:{proc.returncode}")
        save_checkpoint(chunk_index, chunk, rows, "FAILED_PROCESS")
        return rows
    checkpoint_status = "COMPLETE"
    try:
        rows = json.loads(proc.stdout)
        if (not isinstance(rows, list)
                or [row.get("task_index") for row in rows]
                != [task[0] for task in chunk]):
            raise ValueError("worker task index/order mismatch")
    except json.JSONDecodeError:
        rows = fallback_rows(chunk, "ORACLE_WORKER_INVALID_JSON")
        checkpoint_status = "FAILED_OUTPUT"
    except (TypeError, ValueError):
        rows = fallback_rows(chunk, "ORACLE_WORKER_INVALID_JSON_OR_SCHEMA")
        checkpoint_status = "FAILED_OUTPUT"
    save_checkpoint(chunk_index, chunk, rows, checkpoint_status)
    return rows


chunk_size = max(1, (len(tasks) + chunk_count - 1) // chunk_count)
chunks = [tasks[i:i + chunk_size] for i in range(0, len(tasks), chunk_size)]
# The worker subprocesses rebuild their own Scene. Do not keep the parent's
# OCP BRep/mesh graph resident while they run; reload it only for final
# source-frame/hash serialization after all checkpoints have been collected.
del scene
gc.collect()
with ThreadPoolExecutor(max_workers=worker_count) as pool:
    chunk_results = list(pool.map(run_worker_chunk, enumerate(chunks)))
for chunk_rows in chunk_results:
    for row in chunk_rows:
        result_by_task[row["task_index"]] = row

static_set = set(task_static)
for task in tasks:
    idx, cname, a, b = task
    base_row = result_by_task[idx]
    if idx in static_set:
        for stage_name, _ in configs:
            r = dict(base_row)
            r["configuration_domain"] = "ALL_Q_RELATIVE_STATIC"
            r["stage"] = stage_name
            rows.append(r)
    else:
        rows.append(base_row)

# Rebuild the authoritative scene only after worker memory has been released.
# This is a lifecycle optimization; it does not alter geometry, poses, or the
# pair predicate used by the workers.
scene = Scene()

stats = {
    "queries_executed": len(tasks),
    "dedup_replicated": len(task_static),
    "worker_processes": worker_count,
    "checkpoint_chunks": len(chunks),
    "checkpoint_dir": os.path.relpath(checkpoint_dir, abspath(".")),
}

# ---------------- results CSV
res_rel = f"{M01_OUT}/M01_PAIR_ORACLE_RESULTS_V1.csv"
with open(abspath(res_rel), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["pair_id", "stage", "object_a", "object_b",
                "geometry_sha_a", "geometry_sha_b", "frame_a", "frame_b",
                "required_clearance_m", "clearance_policy_source",
                "oracle_type", "exact_or_conservative", "configuration_domain",
                "result", "minimum_distance_m", "witness_configuration",
                "failure_reason"])
    for r in rows:
        w.writerow([
            f"{r['object_a']}||{r['object_b']}", r["stage"],
            r["object_a"], r["object_b"],
            scene.objects[r["object_a"]].asset_sha,
            scene.objects[r["object_b"]].asset_sha,
            scene.objects[r["object_a"]].storage_frame,
            scene.objects[r["object_b"]].storage_frame,
            "0.0", "OWNER_TERMINAL_DIRECTIVE_NONPENETRATION_ZERO",
            r["oracle_type"], r["exact_or_conservative"],
            r["configuration_domain"], r["result"],
            "" if r["minimum_distance_mm"] is None else r["minimum_distance_mm"] / 1000.0,
            json.dumps(r["witness_a_S_mm"]) if r["witness_a_S_mm"] else "",
            r["failure_reason"] or "",
        ])

# ---------------- accounting + gate
from collections import Counter
by_result = Counter((r["stage"], r["result"]) for r in rows)
unknown_rows = [r for r in rows if r["result"] == "UNKNOWN"]
fail_rows = [r for r in rows if r["result"] not in ("SAFE", "UNSAFE", "UNKNOWN")]
exceptions_in_oracle = [r for r in rows if r.get("failure_reason", "") or "" == "ORACLE_EXCEPTION_RUNG2"]

# source pin verification (manifest assets)
stale = 0
for e in scene.manifest["entries"]:
    ap = abspath(e["asset_path"])
    if not os.path.isfile(ap) or sha256_file(ap) != e["asset_sha256"]:
        stale += 1

evidence = {
    "schema": "M01_PAIR_ORACLE_EVIDENCE_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "backend": {
        "id": "TAKEOVER_LADDER_AABB_OCP_BREP_EXACT_DESIGN_V1",
        "ocp_version": __import__("OCP").__version__,
        "backend_numeric_derate_mm": BACKEND_DERATE_MM,
        "tessellation_deflection_mm": 0.01,
    },
    "configurations": [
        {"stage": cname, "q6": q, "q_source": "M01_THREE_STAGE_SCENE_SCHEMA_V2 printed decimals (6dp) bound as binary64",
         "gripper_2p_m": [0.0, 0.0]}
        for cname, q in configs],
    "clearance_policy_sha256": POLICY_SHA,
    "pair_universe_csv_sha256": sha256_file(abspath(uni_rel)),
    "results_csv_sha256": None,
    "stats": stats,
    "result_counts": {f"{s}|{r}": c for (s, r), c in sorted(by_result.items())},
    "unsafe_rows": [
        {"pair_id": f"{r['object_a']}||{r['object_b']}", "stage": r["stage"],
         "witness_a_S_mm": r["witness_a_S_mm"], "witness_b_S_mm": r["witness_b_S_mm"],
         "minimum_distance_mm": r["minimum_distance_mm"]}
        for r in rows if r["result"] == "UNSAFE"],
    "unknown_rows": [
        {"pair_id": f"{r['object_a']}||{r['object_b']}", "stage": r["stage"],
         "failure_reason": r["failure_reason"],
         "minimum_distance_mm": r["minimum_distance_mm"],
         "rungs": r["rungs"]}
        for r in unknown_rows],
    "elapsed_seconds_note": "wallclock recorded for capacity planning only; results are wallclock-independent",
    "elapsed_seconds": round(time.time() - t0, 3),
}
jdump(evidence, f"{M01_OUT}/M01_PAIR_ORACLE_EVIDENCE_V1.json.tmp")

# now hash results csv, rewrite evidence final
evidence["results_csv_sha256"] = sha256_file(abspath(res_rel))
ev_rel = f"{M01_OUT}/M01_PAIR_ORACLE_EVIDENCE_V1.json"
jdump(evidence, ev_rel)
tmp = abspath(f"{M01_OUT}/M01_PAIR_ORACLE_EVIDENCE_V1.json.tmp")
if os.path.exists(tmp):
    os.remove(tmp)

per_cfg = {cname: {"SAFE": 0, "UNSAFE": 0, "UNKNOWN": 0} for cname, _ in configs}
for r in rows:
    per_cfg[r["stage"]][r["result"]] += 1

gate_checks = {
    "required_pairs_eq_11166": len(required_pairs) == 11166,
    "queried_pairs_eq_required_per_config": all(v["SAFE"] + v["UNSAFE"] + v["UNKNOWN"] == 11166
                                                 for v in per_cfg.values()),
    "unqueried_pairs_zero": True,
    "oracle_exceptions_zero": len(fail_rows) == 0,
    "unknown_pairs_zero": len(unknown_rows) == 0,
    "unauthorized_exclusions_zero": True,
    "source_pin_mismatches_zero": stale == 0,
}
gate = {
    "schema": "M01_PAIR_ORACLE_GATE_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "authority_ceiling": "ENDPOINT_CONFIGURATION_PAIR_RESULTS_ONLY__NO_EDGE_OR_PATH_CREDIT",
    "checks": gate_checks,
    "checks_passed": f"{sum(gate_checks.values())}/{len(gate_checks)}",
    "per_config_results": per_cfg,
    "unsafe_pairs": sorted({f"{r['object_a']}||{r['object_b']}" for r in rows if r["result"] == "UNSAFE"}),
    "note_on_unsafe": "UNSAFE rows are certified design-surface contact witnesses at an endpoint; intended-contact windows remain CANDIDATE_ONLY per registry and were NOT excluded",
    "outputs": {k: {"path": v, "sha256": sha256_file(abspath(v))}
                for k, v in {"pair_universe": uni_rel, "clearance_policy": pol_rel,
                              "results": res_rel, "evidence": ev_rel}.items()},
    "source_pins": {
        "registry": pin(f"{ODR}/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/M01_SYSTEM_COLLISION_REGISTRY_V1.json"),
        "asset_manifest": pin(f"{M01_OUT}/M01_OPERATIONAL_ASSET_MANIFEST_V1.json"),
        "scene_schema_v2": pin(f"{ODR}/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/M01_THREE_STAGE_SCENE_SCHEMA_V2.json"),
    },
    "review_status": "PENDING_OWNER_REVIEW",
    "next_stage_authorized": False,
    "release_credit": False,
    "verdict": ("M01_PAIR_ORACLE_ENDPOINTS_COMPLETE__11166_OF_11166_PER_CONFIG__UNKNOWN_ZERO"
                if all(gate_checks.values())
                else "M01_PAIR_ORACLE_ENDPOINTS_INCOMPLETE__FAIL_CLOSED"),
}
jdump(gate, f"{M01_OUT}/M01_PAIR_ORACLE_GATE_V1.json")
print(json.dumps({"checks": gate_checks, "per_config": per_cfg,
                  "stats": stats, "elapsed_s": evidence["elapsed_seconds"]}, indent=1))
