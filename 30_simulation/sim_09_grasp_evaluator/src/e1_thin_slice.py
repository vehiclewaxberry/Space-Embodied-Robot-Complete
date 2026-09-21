"""sim_09 Gate E1 -- deterministic G0/G1/G2 thin-slice sweep (72 cases).

Grid (fully deterministic, no sampling):
  grasp points  P1=[0.66,0,0.95]  P2=[0,0.66,0.95]  P3=[0.66,0,-0.95]
                (target CAD/D frame, nozzle-rim features; lever arm relative to
                the CoM = point - cg, cg from mass_inertia_budget_v1 via
                rigid_body.load_object -- same source as capture_impulse.GRASP)
  capture phase t_c in {0, 30, 60, 90} s  (tumble period T = 120 s @ 3 deg/s)
  approach vel  v_app in {0.005, 0.01, 0.02} m/s
  task mode     pose_6d | approach_5d
  fixed         q0 = zeros(6)  [NOTE: joints 2/3 upper limit is 0.0 -> q0 sits
                ON the limit; margins are evaluated at q_c, not q0],
                capture_mode = rigid_6dof, chaser_mode = b601,
                capture_point_S = evaluator default [0.95, 0, -0.10] (E0 policy),
                target = target_debris_v0 @ 3 deg/s about [1,0.15,0.4]/|.|.

G0 baseline = grid cell (P1, t_c=0, v_app=0.01, pose_6d) -- the E0 nominal
scenario evaluated by the SAME evaluator under the uniform E1 q0 policy.

Per-case pipeline (worker process; _bootstrap pins BLAS single-thread BEFORE
numpy in every process):
  1. evaluator.evaluate() with flexible DISABLED -> all fast metrics +
     admissibility flags (IK / limits / collision / conditioning / impulse /
     wheel momentum).
  2. ANCF gate: only cases passing IK + collision run the FULL flexible model
     (nominal f1, Radau rtol 1e-6, t_end 15 s -- identical to the E0 default).
     sim_07a.simulate asserts sol.success; on failure we RETRY with rtol 1e-5
     (ancf_cost_audit_verdict.md ruling). Still failing -> flex_status =
     FLEX_SOLVER_FAIL and the case is excluded from admissible set (never
     silently tabled).
  3. deterministic M_PCS = min of 5 normalized margins (thresholds from
     20_engineering/config/grasp_evaluator/hard_constraints_v1.yaml; theta_max has NO yaml
     entry -- see THETA_MAX_DEG comment; flagged UNVERIFIED in the E1 report).

Checkpoint / resume: each finished case is appended to the CSV immediately
(flushed); on restart complete rows are kept (file is compacted) and only the
missing cases are run. When all 72 rows exist the CSV is rewritten in canonical
grid order.

NO overall_score anywhere. Selection logic lives in e1_analysis.py:
hard-constraint screen -> per-metric values -> Pareto front.

Run:  python e1_thin_slice.py [--workers 4] [--fresh] [--limit N]
"""
import _bootstrap  # noqa: F401  (BLAS env pin BEFORE numpy; solver paths)
import argparse
import csv
import json
import os
import time

import numpy as np

import adapters
import evaluator
import target_propagation
from contract import GraspCandidate
from rigid_body import load_object

RESULTS_CSV = os.path.join(_bootstrap.RESULTS_DIR, "e1_results_72cases.csv")

TARGET_ID = "target_debris_v0"
OMEGA_DPS = 3.0
TUMBLE_AXIS = [1.0, 0.15, 0.4]          # normalized inside the propagation core
ATTITUDE0_QUAT = [1.0, 0.0, 0.0, 0.0]
Q0 = np.zeros(6)
CAPTURE_MODE = "rigid_6dof"
CHASER_MODE = "b601"

T_C_GRID = (0.0, 30.0, 60.0, 90.0)      # s (tumble period 120 s -> 0/90/180/270 deg)
V_APP_GRID = (0.005, 0.01, 0.02)        # m/s
MODE_GRID = ("pose_6d", "approach_5d")

# Grasp frames C in T: z_C = outward approach normal (radial at the rim),
# x_C = axial direction pointing AWAY from the target body (+Z_T on the top rim,
# -Z_T on the bottom rim), y_C = z_C x x_C (right-handed, det = +1).
# P1 frame == the validated E0 nominal (tests/_helpers.R_C_NOMINAL).
GRASP_POINTS = {
    "P1": {"p_D": [0.66, 0.0, 0.95], "approach_T": [1.0, 0.0, 0.0],
           "R_C": [[0.0, 0.0, 1.0], [0.0, -1.0, 0.0], [1.0, 0.0, 0.0]]},
    "P2": {"p_D": [0.0, 0.66, 0.95], "approach_T": [0.0, 1.0, 0.0],
           "R_C": [[0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [1.0, 0.0, 0.0]]},
    "P3": {"p_D": [0.66, 0.0, -0.95], "approach_T": [1.0, 0.0, 0.0],
           "R_C": [[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]]},
}

# ---- flexible (ANCF) settings: E0 evaluator defaults + audit-ruled retry ----
FLEX_T_END_S = 15.0
FLEX_N_EVAL = 1500
FLEX_RTOL = 1e-6
FLEX_RTOL_RETRY = 1e-5                  # ancf_cost_audit_verdict.md ruling
FLEX_EI_CASE = "nominal"

# ---- M_PCS thresholds (source: hard_constraints_v1.yaml unless stated) ----
_HC = evaluator.load_hard_constraints()
H_MAX_NMS = float(_HC["wheel_momentum_max_Nms"])          # yaml (PLACEHOLDER 1.5x sim_08)
OMEGA_MAX_DPS = float(_HC["post_capture_rate_max_dps"])   # yaml (sim_04 POST_CAP_BUDGET)
E_FLEX_MAX_J = float(_HC["flexible_energy_max_J"])        # yaml (PLACEHOLDER ~40x sim_07a)
LEVER_M = float(evaluator.DEFAULT_CONFIG["actuator"]["lever_m"])   # sim_08 couple lever
J_THR_MAX_NS = H_MAX_NMS / LEVER_M      # DERIVED: yaml H_max / sim_08 lever (0.17 m)
THETA_MAX_DEG = 20.0                    # NOT in hard_constraints_v1.yaml -- derived
#   placeholder: ceiling of the sim_05 mainline full-reach base excursion
#   (19.20 deg headline). Declared UNVERIFIED in the E1 report; replace once a
#   GNC pointing budget exists.

# E1-level failure code (NOT part of the E0 contract FAILURE_CODES enum; the
# contract result object is never rebuilt with it -- CSV bookkeeping only).
FLEX_SOLVER_FAIL = "FLEX_SOLVER_FAIL"

CSV_COLUMNS = [
    # ---- candidate inputs (everything hashing into scenario_hash) ----
    "grid_index", "case_id", "target_id", "grasp_point_id",
    "grasp_point_D_json", "r_gT_json", "approach_dir_T_json",
    "grasp_pose_target_json", "t_c_s", "v_app_mps", "task_constraint_mode",
    "capture_mode", "chaser_mode", "q0_json", "omega_dps", "tumble_axis_json",
    "attitude0_quat_json", "target_mass_kg", "inertia_scale",
    "capture_point_S_json", "scenario_hash",
    # ---- the 21 contract result fields (complex fields as JSON) ----
    "ik_feasible", "ik_solution_set_json", "pose_residual_json",
    "joint_limit_margin_rad", "task_jacobian_rank", "task_nullity",
    "manipulability_json", "collision_margin_json", "base_attitude_change_deg",
    "base_rate_peak_dps", "capture_impulse_6d_json",
    "impulse_moment_at_grasp_json", "post_capture_rate_dps", "H_RW_Nms",
    "J_thr_Ns", "m_prop_g", "E_flex_J", "severity_proxy",
    "admissibility_flags_json", "failure_codes", "solver_provenance_json",
    # ---- flattened conveniences (duplicated from the JSON fields) ----
    "n_ik_solutions", "pose_residual_pos_m", "pose_residual_ori_rad",
    "cond_number", "manip_sqrt_det_JJT", "manip_sigma_min",
    "collision_margin_min_m", "collision_t_at_min_s", "Jt_norm_Ns",
    "Lgrasp_norm_Nms", "dv_chaser_norm_mps", "dw_chaser_norm_radps",
    # ---- E1 flexible bookkeeping ----
    "flex_status", "flex_rtol_used", "flex_tip_peak_mm", "flex_f1_hz",
    # ---- admissibility + deterministic M_PCS ----
    "admissible", "mpcs_margin_H", "mpcs_margin_Jthr", "mpcs_margin_Eflex",
    "mpcs_margin_omega", "mpcs_margin_theta", "M_PCS",
    # ---- provenance / timing / integrity ----
    "wall_s_fast", "wall_s_flex", "row_complete",
]


# --------------------------------------------------------------------------
# case grid
# --------------------------------------------------------------------------

def build_all_cases():
    """Canonical 72-case grid, deterministic order (grid_index 0..71)."""
    cases = []
    idx = 0
    for pid in ("P1", "P2", "P3"):
        for t_c in T_C_GRID:
            for v_app in V_APP_GRID:
                for mode in MODE_GRID:
                    cases.append({
                        "grid_index": idx,
                        "case_id": f"{pid}_tc{int(t_c):02d}_v{int(round(v_app * 1000))}mm_{mode}",
                        "grasp_point_id": pid, "t_c": float(t_c),
                        "v_app": float(v_app), "mode": mode,
                    })
                    idx += 1
    return cases


def make_candidate(spec):
    gp = GRASP_POINTS[spec["grasp_point_id"]]
    tgt = load_object(TARGET_ID)
    r_gT = np.asarray(gp["p_D"], float) - np.asarray(tgt["cg"], float)
    T_C = np.eye(4)
    T_C[:3, :3] = np.asarray(gp["R_C"], float)
    T_C[:3, 3] = r_gT
    return GraspCandidate(
        target_id=TARGET_ID,
        grasp_point_id=spec["grasp_point_id"],
        grasp_pose_target=T_C,
        approach_direction_target=np.asarray(gp["approach_T"], float),
        capture_time=spec["t_c"],
        approach_velocity=spec["v_app"],
        initial_joint_configuration=Q0.copy(),
        task_constraint_mode=spec["mode"],
        capture_mode=CAPTURE_MODE,
        target_state={"omega_dps": OMEGA_DPS, "tumble_axis": list(TUMBLE_AXIS),
                      "attitude0_quat": list(ATTITUDE0_QUAT)},
        target_inertia={"mass": float(tgt["mass"]),
                        "I": np.asarray(tgt["I"], float), "inertia_scale": 1.0},
    )


# --------------------------------------------------------------------------
# M_PCS (deterministic, per project definition; NOT an overall_score -- it is
# reported alongside the Pareto metrics, never used to pre-filter them)
# --------------------------------------------------------------------------

def mpcs_terms(H_Nms, J_thr_Ns, E_flex_J, omega_dps, dtheta_deg):
    """5 normalized stability margins; M_PCS = min(terms). None if E_flex is
    unavailable (skipped / solver-failed case)."""
    if None in (H_Nms, J_thr_Ns, omega_dps, dtheta_deg) or E_flex_J is None:
        return None
    return {
        "mpcs_margin_H": 1.0 - H_Nms / H_MAX_NMS,
        "mpcs_margin_Jthr": 1.0 - J_thr_Ns / J_THR_MAX_NS,
        "mpcs_margin_Eflex": 1.0 - E_flex_J / E_FLEX_MAX_J,
        "mpcs_margin_omega": 1.0 - omega_dps / OMEGA_MAX_DPS,
        "mpcs_margin_theta": 1.0 - dtheta_deg / THETA_MAX_DEG,
    }


# --------------------------------------------------------------------------
# worker
# --------------------------------------------------------------------------

def _flex_capture_chain(candidate, q_c):
    """Re-run the (cheap, deterministic) propagation -> placement -> capture
    chain to recover (dv, dw, R_IS, com_chaser_S) for the flexible adapter.
    Bit-identical to the pass inside evaluate() (verified by the caller)."""
    cfg = evaluator.DEFAULT_CONFIG
    r_g_T = candidate.grasp_pose_target[:3, 3]
    I_scaled = (np.asarray(candidate.target_inertia["I"], float)
                * float(candidate.target_inertia.get("inertia_scale", 1.0)))
    prop = target_propagation.propagate(
        candidate.target_state, r_g_T, candidate.capture_time,
        mode=cfg["scenario"]["propagation_mode"], target_I=I_scaled)
    placement = adapters.scene_placement(candidate, prop,
                                         cfg["scenario"]["capture_point_S"])
    cap = adapters.capture_adapter(candidate, prop, placement, CHASER_MODE, q_c)
    return cap, placement


def evaluate_case(spec):
    """Full E1 pipeline for one grid case. Returns a flat CSV row dict."""
    cand = make_candidate(spec)
    cfg_fast = evaluator.make_config({"flexible": {"enabled": False}})

    t0 = time.time()
    res = evaluator.evaluate(cand, cfg_fast)
    wall_fast = time.time() - t0

    flags = dict(res.admissibility_flags)
    codes = list(res.failure_reason_codes)
    e_flex = None
    flex_status, flex_rtol_used = "SKIPPED_INADMISSIBLE", ""
    flex_tip_mm, flex_f1 = None, None
    dv_norm, dw_norm = None, None
    wall_flex = 0.0

    flex_eligible = bool(res.ik_feasible) and bool(flags.get("collision_margin_min_m"))
    if flex_eligible:
        q_c = np.asarray(res.ik_solution_set[0]["q"], float)
        cap, _ = _flex_capture_chain(cand, q_c)
        # determinism cross-check vs the capture pass inside evaluate()
        d = np.max(np.abs(np.asarray(cap["J_t_Ns"])
                          - np.asarray(res.capture_impulse_6d["J_t_Ns"])))
        if d > 1e-12:
            raise RuntimeError(f"capture re-run mismatch {d:.3e} for {spec['case_id']}")
        dv_norm = float(np.linalg.norm(cap["dv_chaser"]))
        dw_norm = float(np.linalg.norm(cap["dw_chaser"]))

        t0 = time.time()
        flx = None
        for rtol, status in ((FLEX_RTOL, "OK"),
                             (FLEX_RTOL_RETRY, "RETRY_OK_rtol1e-5")):
            try:
                flx = adapters.flexible_adapter(
                    cap["dv_chaser"], cap["dw_chaser"],
                    cap["meta"]["R_IS"], cap["meta"]["com_chaser_S"],
                    t_end_s=FLEX_T_END_S, n_eval=FLEX_N_EVAL, rtol=rtol,
                    ei_case=FLEX_EI_CASE)
                flex_status, flex_rtol_used = status, f"{rtol:.0e}"
                break
            except Exception:  # noqa: BLE001 (AssertionError <=> sol.success=False)
                flx = None
        wall_flex = time.time() - t0
        if flx is None:
            flex_status, flex_rtol_used = FLEX_SOLVER_FAIL, ""
            codes.append(FLEX_SOLVER_FAIL)
            flags["flexible_energy_max_J"] = False       # unproven -> inadmissible
        else:
            e_flex = float(flx["E_flex_J"])
            flex_tip_mm = float(flx["tip_peak_mm"])
            flex_f1 = float(flx["f1_hz"])
            flags["flexible_energy_max_J"] = e_flex < E_FLEX_MAX_J
            if not flags["flexible_energy_max_J"]:
                codes.append("FLEX_EXCEED")

    admissible = bool(res.ik_feasible) and all(flags.values()) \
        and flex_status in ("OK", "RETRY_OK_rtol1e-5")

    terms = mpcs_terms(res.wheel_momentum_required, res.thruster_impulse_required,
                       e_flex, res.post_capture_angular_velocity,
                       res.base_attitude_change)
    m_pcs = min(terms.values()) if terms else None

    sel = res.ik_solution_set[0] if res.ik_solution_set else None
    gp = GRASP_POINTS[spec["grasp_point_id"]]
    r_gT = cand.grasp_pose_target[:3, 3]

    def jdump(x):
        return json.dumps(x, separators=(",", ":"))

    row = {
        "grid_index": spec["grid_index"], "case_id": spec["case_id"],
        "target_id": TARGET_ID, "grasp_point_id": spec["grasp_point_id"],
        "grasp_point_D_json": jdump(gp["p_D"]),
        "r_gT_json": jdump([float(v) for v in r_gT]),
        "approach_dir_T_json": jdump(gp["approach_T"]),
        "grasp_pose_target_json": jdump(cand.grasp_pose_target.tolist()),
        "t_c_s": spec["t_c"], "v_app_mps": spec["v_app"],
        "task_constraint_mode": spec["mode"], "capture_mode": CAPTURE_MODE,
        "chaser_mode": CHASER_MODE, "q0_json": jdump(Q0.tolist()),
        "omega_dps": OMEGA_DPS, "tumble_axis_json": jdump(TUMBLE_AXIS),
        "attitude0_quat_json": jdump(ATTITUDE0_QUAT),
        "target_mass_kg": float(cand.target_inertia["mass"]),
        "inertia_scale": 1.0,
        "capture_point_S_json": jdump(
            evaluator.DEFAULT_CONFIG["scenario"]["capture_point_S"]),
        "scenario_hash": cand.scenario_hash,

        "ik_feasible": int(res.ik_feasible),
        "ik_solution_set_json": jdump(res.ik_solution_set),
        "pose_residual_json": jdump(res.pose_residual),
        "joint_limit_margin_rad": res.joint_limit_margin,
        "task_jacobian_rank": res.task_jacobian_rank,
        "task_nullity": res.task_nullity,
        "manipulability_json": jdump(res.manipulability),
        "collision_margin_json": jdump(res.collision_margin),
        "base_attitude_change_deg": res.base_attitude_change,
        "base_rate_peak_dps": res.base_angular_velocity_metric,
        "capture_impulse_6d_json": jdump(res.capture_impulse_6d),
        "impulse_moment_at_grasp_json": jdump(res.impulse_moment_at_grasp),
        "post_capture_rate_dps": res.post_capture_angular_velocity,
        "H_RW_Nms": res.wheel_momentum_required,
        "J_thr_Ns": res.thruster_impulse_required,
        "m_prop_g": res.propellant_required,
        "E_flex_J": e_flex,
        "severity_proxy": res.impact_severity_proxy,
        "admissibility_flags_json": jdump(flags),
        "failure_codes": ";".join(codes),
        # canonical() strips wall_time_ms -> the column is deterministic
        "solver_provenance_json": jdump(res.canonical()["solver_provenance"]),

        "n_ik_solutions": len(res.ik_solution_set),
        "pose_residual_pos_m": None if res.pose_residual is None
        else res.pose_residual["position_m"],
        "pose_residual_ori_rad": None if res.pose_residual is None
        else res.pose_residual["orientation_rad"],
        "cond_number": None if sel is None else sel["condition_number"],
        "manip_sqrt_det_JJT": None if res.manipulability is None
        else res.manipulability["sqrt_det_JJT"],
        "manip_sigma_min": None if res.manipulability is None
        else res.manipulability["sigma_min"],
        "collision_margin_min_m": None if res.collision_margin is None
        else res.collision_margin["min_margin_m"],
        "collision_t_at_min_s": None if res.collision_margin is None
        else res.collision_margin["t_at_min_s"],
        "Jt_norm_Ns": None if res.capture_impulse_6d is None
        else float(np.linalg.norm(res.capture_impulse_6d["J_t_Ns"])),
        "Lgrasp_norm_Nms": None if res.impulse_moment_at_grasp is None
        else res.impulse_moment_at_grasp["norm_Nms"],
        "dv_chaser_norm_mps": dv_norm, "dw_chaser_norm_radps": dw_norm,

        "flex_status": flex_status, "flex_rtol_used": flex_rtol_used,
        "flex_tip_peak_mm": flex_tip_mm, "flex_f1_hz": flex_f1,

        "admissible": int(admissible),
    }
    if terms:
        row.update({k: v for k, v in terms.items()})
    else:
        row.update({k: None for k in ("mpcs_margin_H", "mpcs_margin_Jthr",
                                      "mpcs_margin_Eflex", "mpcs_margin_omega",
                                      "mpcs_margin_theta")})
    row["M_PCS"] = m_pcs
    row["wall_s_fast"] = round(wall_fast, 2)
    row["wall_s_flex"] = round(wall_flex, 2)
    row["row_complete"] = 1
    return row


# --------------------------------------------------------------------------
# checkpointed CSV
# --------------------------------------------------------------------------

def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return repr(v)                     # full double precision round-trip
    return v


def load_existing_rows(path=RESULTS_CSV):
    """Complete rows keyed by scenario_hash (torn/incomplete rows dropped)."""
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            try:
                if r.get("row_complete") == "1" and r.get("scenario_hash"):
                    rows[r["scenario_hash"]] = r
            except Exception:              # noqa: BLE001 torn line -> re-run case
                continue
    return rows


def write_rows(rows, path=RESULTS_CSV):
    """Rewrite the CSV from scratch in canonical grid order."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ordered = sorted(rows.values(), key=lambda r: int(r["grid_index"]))
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in ordered:
            w.writerow({k: _fmt(r.get(k)) for k in CSV_COLUMNS})


def append_row(row, path=RESULTS_CSV):
    new_file = not os.path.exists(path)
    with open(path, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        if new_file:
            w.writeheader()
        w.writerow({k: _fmt(row.get(k)) for k in CSV_COLUMNS})
        f.flush()
        os.fsync(f.fileno())


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workers", type=int, default=4,
                    help="parallel worker processes (audit ruling: 3-4)")
    ap.add_argument("--fresh", action="store_true",
                    help="ignore any existing checkpoint CSV and restart")
    ap.add_argument("--limit", type=int, default=0,
                    help="run at most N pending cases (0 = all; smoke testing)")
    args = ap.parse_args(argv)

    cases = build_all_cases()
    hashes = {}
    for spec in cases:
        hashes[spec["case_id"]] = make_candidate(spec).scenario_hash

    existing = {} if args.fresh else load_existing_rows()
    valid_hashes = set(hashes.values())
    existing = {h: r for h, r in existing.items() if h in valid_hashes}
    if existing:
        write_rows(existing)               # compact: drop torn/stale lines
    pending = [s for s in cases if hashes[s["case_id"]] not in existing]
    if args.limit:
        pending = pending[: args.limit]

    print(f"[e1] grid {len(cases)} cases | done {len(existing)} | "
          f"pending {len(pending)} | workers {args.workers}", flush=True)
    if not pending:
        print("[e1] nothing to do")
    else:
        t0 = time.time()
        done = len(existing)
        if args.workers <= 1:
            it = map(evaluate_case, pending)
            for row in it:
                append_row(row)
                done += 1
                print(f"[e1] {done:2d}/{len(cases)} {row['case_id']:32s} "
                      f"adm={row['admissible']} codes={row['failure_codes'] or '-'} "
                      f"flex={row['flex_status']} "
                      f"wall={row['wall_s_fast']}+{row['wall_s_flex']}s", flush=True)
        else:
            import multiprocessing as mp
            ctx = mp.get_context("spawn")
            with ctx.Pool(processes=args.workers) as pool:
                for row in pool.imap_unordered(evaluate_case, pending):
                    append_row(row)
                    done += 1
                    print(f"[e1] {done:2d}/{len(cases)} {row['case_id']:32s} "
                          f"adm={row['admissible']} codes={row['failure_codes'] or '-'} "
                          f"flex={row['flex_status']} "
                          f"wall={row['wall_s_fast']}+{row['wall_s_flex']}s",
                          flush=True)
        print(f"[e1] sweep wall {time.time() - t0:.0f} s", flush=True)

    final = load_existing_rows()
    final = {h: r for h, r in final.items() if h in valid_hashes}
    if len(final) == len(cases):
        write_rows(final)                   # canonical grid order
        n_adm = sum(int(r["admissible"]) for r in final.values())
        print(f"[e1] COMPLETE: {len(final)} rows -> {RESULTS_CSV} "
              f"({n_adm} admissible)", flush=True)
    else:
        print(f"[e1] checkpoint holds {len(final)}/{len(cases)} rows -- rerun to "
              "resume", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
