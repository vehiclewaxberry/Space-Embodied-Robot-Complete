"""VIZ-Gate 0 unified scene assembly (read-only consumption of truth sources).

Placement chain (never re-derived):
    30_simulation/sim_09_grasp_evaluator/src/target_propagation.propagate   (t_c = 0 here)
    30_simulation/sim_09_grasp_evaluator/src/adapters.scene_placement        (imported)
    evaluator.DEFAULT_CONFIG["scenario"]["capture_point_S"]    (E0 policy)

Two placements are produced per the scene manifest target-mapping declaration:
  * satellite_scene(): 22 kg target_satellite_v0, primary grasp point
    launch_adapter_ring, for the MAIN assembly figures v01..v04.
  * debris_scene():    target_debris_v0 with the E1.5 candidate P1, for the
    candidate figures v05/v06 (E1.5 truth: snapshot CSV target_id).

The B601 display configuration is the E1.5 selected q (case
P1_tc00_v10mm_pose_6d) read from the snapshot CSV -- iron rule 2.
"""
import _viz_bootstrap as vb
import csv
import json
import os

import numpy as np

import adapters                       # read-only import (sim_09)
import target_propagation             # read-only import (sim_09)
import evaluator                      # read-only import (sim_09; DEFAULT_CONFIG)
from contract import GraspCandidate   # read-only import (sim_09)
from e1_thin_slice import GRASP_POINTS, TARGET_ID as E1_TARGET_ID  # read-only
from rigid_body import load_object    # read-only import (30_simulation/common)

from b601_renderer import B601VisualChain, load_T_SM
from mesh_utils import load_mesh, decimate_vertex_cluster

SNAP = vb.SNAPSHOT_DIR
E15_CSV = os.path.join(SNAP, "results__sim_09_grasp_evaluator__e15_results_72cases.csv")
E15_MANIFEST = os.path.join(SNAP, "results__sim_09_grasp_evaluator__e15_geometry_manifest.json")
E15_ROLLS = os.path.join(SNAP, "results__sim_09_grasp_evaluator__e15_geometry_roll_details.csv")
E15_GATE = os.path.join(SNAP, "results__sim_09_grasp_evaluator__e15_gate_check.json")

CAPTURE_POINT_S = np.asarray(
    evaluator.DEFAULT_CONFIG["scenario"]["capture_point_S"], float)

DISPLAY_CASE_ID = "P1_tc00_v10mm_pose_6d"       # E1.5 G0 baseline grid cell


# ------------------------------------------------------------- E1.5 snapshot
def e15_selected_case(case_id=DISPLAY_CASE_ID):
    with open(E15_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["case_id"] == case_id:
                assert r["target_id"] == E1_TARGET_ID == "target_debris_v0"
                return {
                    "case_id": case_id,
                    "target_id": r["target_id"],
                    "q": np.asarray(json.loads(r["selected_q_json"]), float),
                    "scenario_hash": r["scenario_hash"],
                    "roll_selection_status": r["roll_selection_status"],
                    "selected_roll_angle_deg": r["selected_roll_angle_deg"],
                    "admissible": r["admissible"],
                    "condition_number": float(r["condition_number"]),
                    "source_commit": r["source_commit"][:7],
                }
    raise KeyError(case_id)


def e15_states():
    gate = json.load(open(E15_GATE, encoding="utf-8"))
    man = json.load(open(E15_MANIFEST, encoding="utf-8"))
    rolls = {}
    with open(E15_ROLLS, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            g = r["geometry_group_key"]
            rolls.setdefault(g, []).append(
                (float(r["roll_angle_deg"]), r["hard_screen_feasible"] == "True"))
    feas = {g: sorted(a for a, ok in v if ok) for g, v in rolls.items()}
    return {"state_counts": gate["state_counts"], "gate": gate["gate"],
            "selections": man["selections"], "feasible_rolls": feas,
            "source_commit": man["source_commit"][:7]}


# ------------------------------------------------------------- placements
def _place(candidate, com_T):
    """Run the read-only placement chain at t_c and return poses in S."""
    r_gT = candidate.grasp_pose_target[:3, 3]
    prop = target_propagation.propagate(candidate.target_state, r_gT,
                                        candidate.capture_time)
    pl = adapters.scene_placement(candidate, prop, CAPTURE_POINT_S)
    # pose of the target GEOMETRIC frame (T/D origin) in S:
    R_TS, r_com_S = pl["R_TS"], pl["r_T_S"]
    T_S_T = np.eye(4)
    T_S_T[:3, :3] = R_TS
    T_S_T[:3, 3] = r_com_S - R_TS @ np.asarray(com_T, float)
    return {"placement": pl, "prop": prop, "T_S_T": T_S_T,
            "com_S": r_com_S, "capture_point_S": CAPTURE_POINT_S.copy()}


def satellite_scene():
    """22 kg satellite placed so launch_adapter_ring sits at the capture point."""
    spec = json.load(open(os.path.join(vb.CAD_DIR, "target_satellite_v0",
                                       "target_satellite_v0.json"),
                          encoding="utf-8"))
    tgt = load_object("target_satellite_v0")          # budget mass/cg/I
    gps = spec["features"]["grasp_points_mm"]
    ring = next(g for g in gps if g["name"] == "launch_adapter_ring")
    p_T = np.asarray(ring["point_mm"], float) / 1000.0
    r_gT = p_T - tgt["cg"]
    # grasp frame C: z_C = +X_T outward approach normal, x_C = +Z_T (same
    # column convention as the E1 P1 nominal frame)
    R_C = np.array([[0.0, 0.0, 1.0], [0.0, -1.0, 0.0], [1.0, 0.0, 0.0]])
    T_C = np.eye(4)
    T_C[:3, :3] = R_C
    T_C[:3, 3] = r_gT
    cand = GraspCandidate(
        target_id="target_satellite_v0", grasp_point_id="launch_adapter_ring",
        grasp_pose_target=T_C, approach_direction_target=[1.0, 0.0, 0.0],
        capture_time=0.0, approach_velocity=0.0,
        initial_joint_configuration=np.zeros(6), task_constraint_mode="pose_6d",
        capture_mode="rigid_6dof",
        # static placement: t_c = 0 -> attitude identity; omega set to 0 so no
        # tumble dynamics is implied (JSON nominal 2-5 deg/s about +Z_T is
        # annotation-only, never used here)
        target_state={"omega_dps": 0.0, "tumble_axis": [0.0, 0.0, 1.0],
                      "attitude0_quat": [1.0, 0.0, 0.0, 0.0]},
        target_inertia={"mass": tgt["mass"], "I": tgt["I"], "inertia_scale": 1.0},
    )
    out = _place(cand, tgt["cg"])
    T_S_T = out["T_S_T"]
    pts = []
    for g in gps:
        p = np.asarray(g["point_mm"], float) / 1000.0
        pts.append({"id": g["name"], "priority": g["priority"],
                    "approach_axis": g["approach_axis"],
                    "p_T": p, "p_S": T_S_T[:3, :3] @ p + T_S_T[:3, 3]})
    out.update({"spec": spec, "grasp_points": pts, "cg_T": tgt["cg"],
                "mass": tgt["mass"]})
    return out


def debris_scene():
    """E1.5 target (debris), candidate P1, placed at t_c = 0."""
    from e1_thin_slice import make_candidate
    cand = make_candidate({"grasp_point_id": "P1", "t_c": 0.0,
                           "v_app": 0.01, "mode": "pose_6d"})
    tgt = load_object("target_debris_v0")
    out = _place(cand, tgt["cg"])
    spec = json.load(open(os.path.join(vb.CAD_DIR, "target_debris_v0",
                                       "target_debris_v0.json"),
                          encoding="utf-8"))
    out.update({"spec": spec, "cg_D": tgt["cg"], "mass": tgt["mass"],
                "grasp_points_D": {k: np.asarray(v["p_D"], float)
                                   for k, v in GRASP_POINTS.items()},
                "grasp_frames_D": {k: np.asarray(v["R_C"], float)
                                   for k, v in GRASP_POINTS.items()},
                "approach_D": {k: np.asarray(v["approach_T"], float)
                               for k, v in GRASP_POINTS.items()},
                "e1_candidate_hash": cand.scenario_hash})
    return out


# ------------------------------------------------------------- display meshes
_DISPLAY_CACHE = {}


def display_mesh(path, target_faces=20000):
    key = (path, target_faces)
    if key not in _DISPLAY_CACHE:
        m = load_mesh(path)
        _DISPLAY_CACHE[key] = decimate_vertex_cluster(m, target_faces)
    return _DISPLAY_CACHE[key]


def model_vf(model_id, target_faces=20000):
    p = os.path.join(vb.CAD_DIR, model_id, f"{model_id}.stl")
    return display_mesh(p, target_faces)


def arm_visuals(q, target_faces=6000):
    """[(link, V, F)] arm display meshes posed in S at configuration q."""
    chain = B601VisualChain()
    out = []
    for name, mesh_path, T in chain.visual_poses(q):
        V, F = display_mesh(mesh_path, target_faces)
        out.append((name, V @ T[:3, :3].T + T[:3, 3], F))
    return out


def arm_frames(q):
    """Key frames (S, M, E) + link poses from the aligned render chain."""
    chain = B601VisualChain()
    lp = chain.link_poses(q)
    return {"T_SM": load_T_SM(), "T_E": lp["T_E"], "links": lp["T"]}
