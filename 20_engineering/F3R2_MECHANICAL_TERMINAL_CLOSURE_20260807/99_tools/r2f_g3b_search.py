# -*- coding: utf-8 -*-
"""F3R2 G3-B search: find and freeze Q_DEPLOYED_HOME, Q_RELEASE_CLEAR and
Q_SERVICE_READY inside the accepted joint limits.

Why a search is needed at all: the as-built pose q = 0 passes seven of the
eight HOME requirements but sits exactly ON the joint2/joint3 mechanical stop
(both upper limits are 0.000 deg), so its limit margin is 0.0 deg.  A control
system must not initialise on a hard stop.  Nothing about the arm or the
spacecraft is modified to fix this -- only q moves, inside the accepted limits,
exactly as the authorised remediation order requires (level 3: optimise q).

The search is a deterministic coarse grid followed by a local refinement.  It
is seeded from poses that are meaningful for the mission rather than random:
  HOME          arm folded back over the +x bay, clear of both wings
  RELEASE_CLEAR a pose lifted off the saddle line but not yet extended
  SERVICE_READY reach forward along the service axis
Every candidate is scored by real clearance, and the winner must pass the same
eight fail-closed requirements; a search that finds nothing returns
NOT_FOUND rather than the best failure.
"""
import itertools
import json
import math
import sys
import traceback

import numpy as np

import r2_common as C
import r2_kin as K
import r2_pose as P
from r2e_g3b_poses import evaluate, home_gate, CLEAR_MIN_MM, MARGIN_MIN_DEG

log = C.Log("r2f_g3b_search")
OUTJ = C.CFG2 / "F3R2_POSE_SEARCH.json"

# coarse candidate grid, chosen to span the reachable envelope without
# pretending to be an optimiser: joints 1..5, joint6 is a roll and stays 0.
GRID = {
    "joint1": [-120.0, -90.0, -60.0, -30.0, 0.0, 30.0, 60.0, 90.0, 120.0],
    "joint2": [-150.0, -120.0, -90.0, -60.0, -30.0],
    "joint3": [-150.0, -120.0, -90.0, -60.0, -30.0],
    "joint4": [-60.0, -30.0, 0.0, 30.0, 60.0],
    "joint5": [-60.0, -30.0, 0.0, 30.0, 60.0],
}


def quick_score(q, arms, envs):
    """Cheap AABB-only score: conservative, used to rank the grid."""
    Ts = {cad: P.rel_transform(a["link"], q) for cad, a in arms.items()}
    boxes = {cad: P.transform_box(a["box"], Ts[cad])
             for cad, a in arms.items()}
    worst_bus = worst_wing = float("inf")
    worst_sad = float("inf")
    for cad, a in arms.items():
        for en, e in envs.items():
            g = P.aabb_gap(boxes[cad], e["box"])
            if e["role"] == "SOLAR_WING":
                worst_wing = min(worst_wing, g)
            elif e["role"] == "SADDLE_PLACEHOLDER":
                worst_sad = min(worst_sad, g)
            elif e["role"] == "REFERENCE_ONLY":
                continue
            elif e["role"] == "ARM_MOUNT_INTERFACE" and a["link"] == "base_link":
                continue
            else:
                worst_bus = min(worst_bus, g)
    return worst_bus, worst_wing, worst_sad


def limit_margin(q):
    lim = K.within_limits(q)
    if not all(v["inside"] for v in lim.values()):
        return -1.0
    return min(v["margin_deg"] for v in lim.values())


def ee_position(q):
    return K.link_world(q)["gripper_link"][:3, 3]


def search(arms, envs, objective, want=6):
    """Rank the grid by a conservative AABB screen, return the best `want`."""
    cands = []
    for q1, q2, q3, q4, q5 in itertools.product(
            GRID["joint1"], GRID["joint2"], GRID["joint3"],
            GRID["joint4"], GRID["joint5"]):
        q = [q1, q2, q3, q4, q5, 0.0]
        m = limit_margin(q)
        if m < MARGIN_MIN_DEG:
            continue
        wb, ww, ws = quick_score(q, arms, envs)
        if wb < CLEAR_MIN_MM or ww < CLEAR_MIN_MM:
            continue
        cands.append({"q": q, "margin": m, "bus": wb, "wing": ww,
                      "saddle": ws, "ee": ee_position(q).tolist(),
                      "objective": objective(q, wb, ww, ws, m)})
    cands.sort(key=lambda d: -d["objective"])
    return cands[:want], len(cands)


def obj_home(q, wb, ww, ws, m):
    """HOME: generous clearance everywhere, healthy limit margin, compact
    (end effector kept near the bus so the arm is not parked extended)."""
    ee = ee_position(q)
    reach = float(np.linalg.norm(ee - P.K.T_MOUNT[:3, 3]))
    return (min(wb, 60.0) * 1.0 + min(ww, 120.0) * 0.35 + min(m, 45.0) * 0.8
            + min(ws, 80.0) * 0.25 - max(0.0, reach - 450.0) * 0.05)


def obj_release(q, wb, ww, ws, m):
    """RELEASE_CLEAR: off the saddle line first, then clearance."""
    return (min(ws, 120.0) * 1.2 + min(wb, 60.0) * 0.6
            + min(ww, 120.0) * 0.3 + min(m, 45.0) * 0.4)


def obj_service(q, wb, ww, ws, m):
    """SERVICE_READY: reach forward (+x, the docking/service axis) while clear."""
    ee = ee_position(q)
    return (ee[0] * 0.06 + min(wb, 60.0) * 0.6 + min(ww, 120.0) * 0.3
            + min(m, 45.0) * 0.4)


def main():
    rep = {"schema": "F3R2_POSE_SEARCH_V1",
           "why": ("q = 0 sits exactly on the joint2/joint3 upper stop "
                   "(both limits are 0.000 deg), so its limit margin is "
                   "0.0 deg and it cannot be a control initialisation pose"),
           "remediation_level": ("3 -- optimise q inside accepted joint "
                                 "limits; no B601 geometry, axis, URDF or "
                                 "spacecraft structure is touched"),
           "grid": {k: v for k, v in GRID.items()},
           "joint6_note": "roll joint, held at 0 deg for all searched poses",
           "clear_target_mm": CLEAR_MIN_MM,
           "margin_target_deg": MARGIN_MIN_DEG}
    try:
        rep["protected_pre"] = C.check_protected2("G3B_SEARCH_PRE")["verdict"]
        arms = P.arm_parts("DEPLOYED")
        envs = P.env_parts("DEPLOYED",
                           wings=("WING_L_DEPLOYED", "WING_R_DEPLOYED"))
        rep["grid_points"] = int(np.prod([len(v) for v in GRID.values()]))

        results = {}
        for name, obj in (("Q_DEPLOYED_HOME", obj_home),
                          ("Q_RELEASE_CLEAR", obj_release),
                          ("Q_SERVICE_READY", obj_service)):
            top, n = search(arms, envs, obj)
            log.ev("GRID_SEARCH", pose=name, feasible=n,
                   best_q=top[0]["q"] if top else None)
            if not top:
                results[name] = {"status": "NOT_FOUND",
                                 "feasible_candidates": 0}
                continue
            # mesh-verify the ranked candidates until one passes the gate
            chosen = None
            tried = []
            for c in top:
                ev, _ = evaluate(c["q"], arms, envs, name)
                gate = home_gate(ev)
                ok = all(v is True for v in gate.values()
                         if isinstance(v, bool))
                tried.append({"q_deg": c["q"], "passes": ok,
                              "min_bus_mm": ev["min_arm_to_bus_mm"],
                              "min_wing_mm": ev["min_arm_to_wing_mm"],
                              "min_saddle_mm": ev["min_arm_to_saddle_mm"],
                              "margin_deg":
                                  ev["nearest_joint_limit_margin_deg"],
                              "failed": [k for k, v in gate.items()
                                         if v is False]})
                log.ev("CANDIDATE_MESH_CHECKED", pose=name, q=c["q"], ok=ok,
                       bus=ev["min_arm_to_bus_mm"],
                       wing=ev["min_arm_to_wing_mm"])
                if ok:
                    chosen = {"evaluation": ev, "gate": gate}
                    break
            results[name] = {
                "status": "FROZEN" if chosen else "NO_CANDIDATE_PASSED_GATE",
                "feasible_candidates": n,
                "candidates_mesh_checked": tried,
                "chosen": chosen}
        rep["results"] = results
        rep["protected_post"] = C.check_protected2("G3B_SEARCH_POST")["verdict"]
        rep["verdict"] = ("G3B_SEARCH_DONE"
                          if all(v["status"] == "FROZEN"
                                 for v in results.values())
                          else "G3B_SEARCH_PARTIAL")
    except Exception as exc:
        rep["verdict"] = "G3B_SEARCH_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2500:]

    C.write_json(OUTJ, rep)
    print("verdict:", rep["verdict"])
    for name, r in (rep.get("results") or {}).items():
        print("\n%-20s %s  (feasible grid points: %s)"
              % (name, r["status"], r.get("feasible_candidates")))
        for t in r.get("candidates_mesh_checked", [])[:4]:
            print("   q=%s pass=%s bus=%s wing=%s saddle=%s margin=%s %s"
                  % (t["q_deg"], t["passes"], t["min_bus_mm"],
                     t["min_wing_mm"], t["min_saddle_mm"], t["margin_deg"],
                     t["failed"] or ""))
    if rep["verdict"] == "G3B_SEARCH_FAIL":
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"].startswith("G3B_SEARCH_DONE") else 1)


if __name__ == "__main__":
    main()
