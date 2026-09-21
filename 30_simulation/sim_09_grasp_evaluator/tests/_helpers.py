"""Shared helpers for the sim_09 anchor-regression tests (t1..t7).

Adds 30_simulation/sim_09_grasp_evaluator/src to sys.path (its _bootstrap pins the BLAS env
vars BEFORE numpy is imported and exposes the validated solver directories) and
provides the NOMINAL candidate: target_debris_v0 tumbling at 3 deg/s about
[1,0.15,0.4]/norm, v_app = 0.01 m/s, t_c = 0, primary grasp point
[0.66,0,0.95]-cg with +X approach -- the exact sim_04/sim_06/sim_07a/sim_08
scenario the anchors were validated on.
"""
import os
import sys

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
SRC = os.path.join(REPO_ROOT, "30_simulation", "sim_09_grasp_evaluator", "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import _bootstrap  # noqa: E402,F401  (env pin + solver paths)
import numpy as np  # noqa: E402

from capture_impulse import GRASP  # noqa: E402  (single source of the anchor grasp point)
from rigid_body import load_object  # noqa: E402
from contract import GraspCandidate  # noqa: E402

RESULTS_DIR = _bootstrap.RESULTS_DIR

# grasp frame C for the +X_T approach: z_C = +X_T (outward normal),
# x_C = +Z_T, y_C = z x x = -Y_T (right-handed, det = +1)
R_C_NOMINAL = np.array([[0.0, 0.0, 1.0],
                        [0.0, -1.0, 0.0],
                        [1.0, 0.0, 0.0]])

Q0_NOMINAL = np.array([0.0, -0.9, -1.2, -0.8, 0.2, 0.0])   # inside URDF limits


def nominal_candidate(task_mode="approach_5d", capture_mode="rigid_6dof",
                      omega_dps=3.0, v_app=0.01, t_c=0.0, q0=None,
                      target_id="target_debris_v0"):
    tgt = load_object(target_id)
    r_gT = GRASP[target_id].copy()          # grasp point rel. CoM (CAD JSON - cg)
    T_C = np.eye(4)
    T_C[:3, :3] = R_C_NOMINAL
    T_C[:3, 3] = r_gT
    return GraspCandidate(
        target_id=target_id,
        grasp_point_id="nozzle_rim_primary" if "debris" in target_id else "adapter_ring",
        grasp_pose_target=T_C,
        approach_direction_target=np.array([1.0, 0.0, 0.0]),
        capture_time=float(t_c),
        approach_velocity=float(v_app),
        initial_joint_configuration=Q0_NOMINAL.copy() if q0 is None else np.asarray(q0, float),
        task_constraint_mode=task_mode,
        capture_mode=capture_mode,
        target_state={"omega_dps": float(omega_dps),
                      "tumble_axis": [1.0, 0.15, 0.4],
                      "attitude0_quat": [1.0, 0.0, 0.0, 0.0]},
        target_inertia={"mass": float(tgt["mass"]), "I": np.asarray(tgt["I"], float),
                        "inertia_scale": 1.0},
    )
