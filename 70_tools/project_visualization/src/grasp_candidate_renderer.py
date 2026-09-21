"""VIZ-Gate 0 Stage 3 -- geometry payload for the grasp-candidate explorer.

Computes (READ-ONLY consumption, iron rules 1-3) everything the interactive
HTML needs, and returns it as one JSON-serializable dict:

  * debris simplified body: cylinder O 1.32 m x 2.5 m (task SSOT; grasp rim
    rings at z = +/-0.95 m from target_debris_v0.json grasp_points_mm), built
    in the D frame once; per-(P, t_c) pose T_S_D comes from the SAME read-only
    placement chain the evaluator used (e1_thin_slice.make_candidate ->
    target_propagation.propagate -> adapters.scene_placement).  The target
    attitude therefore rotates with capture phase under the constant-angular-
    velocity model; the tumble axis ([1, 0.15, 0.4] @ 3 deg/s) is the E1
    CONTEXT value (e1_thin_slice.py) -- it is NOT restated in the E1.5
    snapshot and must be labelled as such.
  * candidate grasp frames: nominal R_C from e1_thin_slice.GRASP_POINTS,
    rolled about the outward normal +z_G per the frozen E1.5 convention
    (grasp_frames.py: ``T_T_G(c) @ R_z_G(roll)``, roll grid -90..+90 step 30).
  * B601 end-effector positions: FK of the snapshot's selected_q_json rows
    via 30_simulation/sim_05_free_floating_arm/b601_model.B601Arm.fk (read-only import,
    the numerical truth chain) -- only rows that passed the hard screen carry
    a q; IK_FAIL rows carry none and the explorer must say so.
  * E1.5 evidence tables re-keyed for the UI: 96 roll rows, 24 group
    selections, 72 top-level cases with the recount class from
    evidence_recount (semantic red line: four scientific classes, never a
    SAFE/UNSAFE red-green binary).

Self-checks (assertions, run on build):
  placement puts the commanded grasp point at capture_point_S (< 1e-9 m) and
  FK of every feasible selected q lands on capture_point_S within 2 mm.
"""
import _viz_bootstrap as vb  # noqa: F401  (env pins BEFORE numpy)
import csv
import json
import os

import numpy as np

import adapters                                 # read-only import (sim_09)
import target_propagation                       # read-only import (sim_09)
import evaluator                                # read-only import (sim_09)
from e1_thin_slice import (GRASP_POINTS, TARGET_ID, OMEGA_DPS, TUMBLE_AXIS,
                           make_candidate)      # read-only import (sim_09)
from rigid_body import load_object              # read-only import (30_simulation/common)
from b601_model import B601Arm                  # read-only import (sim_05 FK truth)

import evidence_recount as er

SNAP = vb.SNAPSHOT_DIR
E15_CSV = os.path.join(SNAP, "results__sim_09_grasp_evaluator__e15_results_72cases.csv")
E15_ROLLS = os.path.join(SNAP, "results__sim_09_grasp_evaluator__e15_geometry_roll_details.csv")
E15_MANIFEST = os.path.join(SNAP, "results__sim_09_grasp_evaluator__e15_geometry_manifest.json")
E15_GATE = os.path.join(SNAP, "results__sim_09_grasp_evaluator__e15_gate_check.json")
PROTECTION_MANIFEST = os.path.join(vb.VIZ_TABLES_DIR,
                                   "gate_artifact_protection_manifest.csv")

CAPTURE_POINT_S = np.asarray(
    evaluator.DEFAULT_CONFIG["scenario"]["capture_point_S"], float)

# task SSOT for the simplified debris body (rim rings from the CAD JSON)
DEBRIS_RADIUS_M = 0.66          # O 1.32 m
DEBRIS_HALF_LEN_M = 1.25        # length 2.5 m
RIM_Z_M = (0.95, -0.95)         # forward / aft end-ring rims (grasp z)

T_C_GRID = (0, 30, 60, 90)
PIDS = ("P1", "P2", "P3")
MODES = ("pose_6d", "approach_5d")
VELS = (5, 10, 20)              # mm/s


# --------------------------------------------------------------- helpers
def _f(x):
    """CSV cell -> float or None."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _Rz(deg):
    a = np.deg2rad(float(deg))
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def cylinder_mesh(radius, half_len, nseg=48):
    """(verts Nx3, faces Mx3) closed cylinder along +z in the D frame."""
    th = np.linspace(0.0, 2.0 * np.pi, nseg, endpoint=False)
    ring = np.stack([radius * np.cos(th), radius * np.sin(th)], axis=1)
    top = np.hstack([ring, np.full((nseg, 1), half_len)])
    bot = np.hstack([ring, np.full((nseg, 1), -half_len)])
    verts = np.vstack([top, bot, [[0, 0, half_len]], [[0, 0, -half_len]]])
    ctop, cbot = 2 * nseg, 2 * nseg + 1
    faces = []
    for i in range(nseg):
        j = (i + 1) % nseg
        faces += [(i, j, nseg + i), (j, nseg + j, nseg + i),   # wall
                  (ctop, i, j), (cbot, nseg + j, nseg + i)]    # caps
    return verts, np.asarray(faces, int)


def rim_ring(radius, z, nseg=72):
    th = np.linspace(0.0, 2.0 * np.pi, nseg + 1)
    return np.stack([radius * np.cos(th), radius * np.sin(th),
                     np.full(nseg + 1, z)], axis=1)


# --------------------------------------------------------------- placement
def placement_for(pid, t_c):
    """T_S_D (debris GEOMETRIC frame -> S) + tumble axis in S at t_c, via the
    read-only evaluator chain (never re-derived here)."""
    cand = make_candidate({"grasp_point_id": pid, "t_c": float(t_c),
                           "v_app": 0.01, "mode": "pose_6d"})
    tgt = load_object(TARGET_ID)
    r_gT = cand.grasp_pose_target[:3, 3]
    prop = target_propagation.propagate(cand.target_state, r_gT, float(t_c))
    pl = adapters.scene_placement(cand, prop, CAPTURE_POINT_S)
    R_TS, r_com_S = pl["R_TS"], pl["r_T_S"]
    T = np.eye(4)
    T[:3, :3] = R_TS
    T[:3, 3] = r_com_S - R_TS @ np.asarray(tgt["cg"], float)
    # self-check: commanded grasp point must sit at the capture point
    p_D = np.asarray(GRASP_POINTS[pid]["p_D"], float)
    p_S = T[:3, :3] @ p_D + T[:3, 3]
    assert np.linalg.norm(p_S - CAPTURE_POINT_S) < 1e-9, (pid, t_c, p_S)
    axis_S = pl["R_SI"] @ (prop["omega_I"] / np.linalg.norm(prop["omega_I"]))
    return {"T_S_D": T, "axis_S": axis_S, "com_S": r_com_S,
            "R_TS": R_TS}


# --------------------------------------------------------------- payload
def build_payload():
    arm = B601Arm()
    gate = json.load(open(E15_GATE, encoding="utf-8"))
    manifest = json.load(open(E15_MANIFEST, encoding="utf-8"))
    rec = er.recount(write=False)
    by_case_rec = {r["case_id"]: r for r in rec["rows"]}

    with open(E15_CSV, newline="", encoding="utf-8") as f:
        results = list(csv.DictReader(f))
    with open(E15_ROLLS, newline="", encoding="utf-8") as f:
        rolls = list(csv.DictReader(f))

    # ---- debris base geometry (D frame) ----
    verts, faces = cylinder_mesh(DEBRIS_RADIUS_M, DEBRIS_HALF_LEN_M)
    rings = [rim_ring(DEBRIS_RADIUS_M, z).round(5).tolist() for z in RIM_Z_M]

    # ---- placements per (pid, t_c) ----
    placements = {}
    for pid in PIDS:
        for tc in T_C_GRID:
            pl = placement_for(pid, tc)
            placements[f"{pid}|{tc}"] = {
                "T_S_D": np.round(pl["T_S_D"], 9).tolist(),
                "axis_S": np.round(pl["axis_S"], 6).tolist(),
                "com_S": np.round(pl["com_S"], 6).tolist(),
            }

    # ---- group selections (manifest) ----
    selections = {s["geometry_group_key"]: s for s in manifest["selections"]}

    # ---- roll rows -> groups dict with triads / FK EE ----
    groups = {}
    fk_checked = 0
    for r in rolls:
        gk = r["geometry_group_key"]            # e.g. "P1|tc=0|pose_6d"
        pid, tck, mode = gk.split("|")
        tc = int(tck.split("=")[1])
        sel = selections[gk]
        g = groups.setdefault(gk, {
            "pid": pid, "tc": tc, "mode": mode,
            "selection_status": sel["status"],
            "selected_roll": sel["selected_roll_angle_deg"],
            "selected_hash": sel["selected_scenario_hash"],
            "rolls": [],
        })
        feas = r["hard_screen_feasible"] == "True"
        pl = placement_for(pid, tc)
        R_SD = pl["T_S_D"][:3, :3]
        R_C = np.asarray(GRASP_POINTS[pid]["R_C"], float)
        roll = float(r["roll_angle_deg"])
        # frozen E1.5 convention: roll about local +z_G (outward normal)
        R_S_C = R_SD @ R_C @ _Rz(roll)
        p_S = CAPTURE_POINT_S                   # by placement construction
        ee_S = None
        if feas and r["selected_q_json"] not in ("", "null"):
            q = np.asarray(json.loads(r["selected_q_json"]), float)
            p_E = arm.fk(q)["T_E"][:3, 3]
            assert np.linalg.norm(p_E - CAPTURE_POINT_S) < 2e-3, (gk, roll, p_E)
            fk_checked += 1
            ee_S = np.round(p_E, 6).tolist()
        g["rolls"].append({
            "roll": roll,
            "roll_status": r["roll_status"],
            "feasible": feas,
            "ik_feasible": r["ik_feasible"] == "True",
            "cond": _f(r["condition_number"]),
            "coll_margin_m": _f(r["collision_margin_m"]),
            "joint_margin_rad": _f(r["joint_limit_margin_rad"]),
            "realized_roll": _f(r["realized_roll_angle_deg"]),
            "hash": r["candidate_scenario_hash"],
            "triad": {ax: np.round(R_S_C[:, i], 6).tolist()
                      for i, ax in enumerate(("x", "y", "z"))},
            "p_S": np.round(p_S, 6).tolist(),
            "ee_S": ee_S,
        })

    # ---- 72 top-level cases (results CSV + recount classes) ----
    cases = {}
    for r in results:
        cid = r["case_id"]
        rr = by_case_rec[cid]
        cases[cid] = {
            "pid": r["grasp_point_id"],
            "tc": int(float(r["t_c_s"])),
            "v_mm": int(round(float(r["v_app_mps"]) * 1000)),
            "mode": r["task_constraint_mode"],
            "e15_state_raw": rr["e15_state_raw"],
            "recount_class": rr["recount_class"],
            "ik_feasible": r["ik_feasible"] == "1",
            "roll_selection_status": r["roll_selection_status"],
            "cond": _f(r["condition_number"]),
            "coll_margin_m": _f(r["collision_margin_min_m"]),
            "mpcs": _f(rr["M_PCS_e15"]),
            "rate_dps": _f(r["post_capture_rate_dps"]),
            "rate_margin": _f(rr["margin__post_capture_rate_dps"]),
            "flex_status": r["flex_status"],
            "hash": r["scenario_hash"],
        }

    # ---- provenance / snapshot hash list ----
    files = []
    if os.path.exists(PROTECTION_MANIFEST):
        with open(PROTECTION_MANIFEST, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                files.append({"source": row["source_rel_path"],
                              "sha256": row["expected_sha256"].lower()})

    payload = {
        "meta": {
            "git_commit": vb.repo_commit_short(),
            "e15_source_commit": rec["provenance"]["e15_source_commit"],
            "gate": gate["gate"],
            "state_counts_raw": gate["state_counts"],
            "recount_tally": rec["tally"],
            "admissible": "0/72",
            "capture_point_S": CAPTURE_POINT_S.tolist(),
            "tumble_context": {
                "axis": list(TUMBLE_AXIS), "omega_dps": OMEGA_DPS,
                "label": ("E1 context（e1_thin_slice.py 网格值；E1.5 快照未"
                          "重申该值——对 E1.5 属证据缺失）"),
            },
            "debris_ssot": "simplified cylinder O 1.32 m x 2.5 m; rim rings z=±0.95 m",
            "snapshot_dir": os.path.relpath(SNAP, vb.REPO_ROOT).replace("\\", "/"),
            "snapshot_files": files,
            "fk_checked_rows": fk_checked,
        },
        "debris": {
            "verts": np.round(verts, 5).tolist(),
            "faces": faces.tolist(),
            "rings": rings,
            "grasp_points_D": {k: v["p_D"] for k, v in GRASP_POINTS.items()},
        },
        "placements": placements,
        "groups": groups,
        "cases": cases,
    }
    return payload


if __name__ == "__main__":
    p = build_payload()
    print("groups:", len(p["groups"]), "| roll rows:",
          sum(len(g["rolls"]) for g in p["groups"].values()),
          "| cases:", len(p["cases"]),
          "| FK-checked feasible rows:", p["meta"]["fk_checked_rows"])
    print("recount tally:", p["meta"]["recount_tally"])
    s = json.dumps(p)
    print(f"payload JSON size: {len(s)/1024:.0f} KB")
