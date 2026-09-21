"""sim_09 Gate E0 -- data contract for the grasp-candidate evaluator.

GraspCandidate        input record (all geometry in the TARGET body frame unless
                      stated otherwise; SI units).
GraspEvaluationResult output record (hard-constraint screening -> per-metric
                      values -> Pareto downstream; NO aggregated score, see note
                      at the bottom of the result class).

Frames / conventions
--------------------
T   target body frame, origin at the target CoM. grasp_pose_target is the 4x4
    pose of the grasp frame C in T: origin = grasp point (relative to the target
    CoM), +z_C = outward approach normal at the grasp feature.
I   scene inertial frame: target CoM at origin and translationally at rest at
    the capture instant; target attitude R_T(t_c) from target_state propagation.
S   servicer body frame. The evaluator's scene-placement rule (adapters.py)
    aligns +X_S with the negative inertial approach direction, mirroring the
    validated sim_04/sim_06 convention (R_IS = diag(-1,-1,1) for the nominal
    +X approach).

scenario_hash: sha256 (first 16 hex chars) of the canonical, key-sorted JSON of
all candidate inputs with every float rounded to 1e-9 -- two candidates that
differ by more than 1e-9 in ANY input hash differently (test t7).

Scope guards (Gate E0 iron rules)
---------------------------------
* No overall_score (kept as a comment placeholder only).
* No contact force / grasp probability / impedance optimization. Contact
  severity is the PROXY field `impact_severity_proxy` (combination of |J_t| and
  |L_grasp|); it is NOT a peak contact force and NOT a success probability.
"""
import _bootstrap  # noqa: F401  (pins BLAS env before numpy import)
import hashlib
import json
from dataclasses import dataclass, field, asdict

import numpy as np

TASK_CONSTRAINT_MODES = ("pose_6d", "approach_5d", "position_3d")
CAPTURE_MODES = ("rigid_6dof", "point_3dof")

# failure_reason_codes enumeration (closed set)
FAILURE_CODES = (
    "IK_FAIL",            # no IK solution converged
    "LIMIT_VIOLATION",    # joint_limit_margin below hard threshold
    "COLLISION",          # collision_margin below hard threshold
    "SINGULAR",           # task-Jacobian condition number above hard threshold
    "IMPULSE_EXCEED",     # post-capture |omega+| above budget
    "ACTUATOR_EXCEED",    # |H_c| above the thruster-scheme momentum bound
    "FLEX_EXCEED",        # flexible energy proxy above placeholder bound
    "PROPAGATION_FAIL",   # target-state propagation failed
)


def _canon(value):
    """Canonicalise a value for hashing: floats rounded to 1e-9, numpy arrays
    -> nested lists, dicts key-sorted (json dump does the sorting)."""
    if isinstance(value, (np.floating, float)):
        v = round(float(value), 9)
        return 0.0 if v == 0.0 else v          # avoid -0.0 vs 0.0 hash split
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, np.ndarray):
        return [_canon(x) for x in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [_canon(x) for x in value]
    if isinstance(value, dict):
        return {str(k): _canon(v) for k, v in value.items()}
    if value is None or isinstance(value, (str, bool)):
        return value
    raise TypeError(f"unhashable candidate field type: {type(value)}")


def scenario_hash_of(payload):
    """sha256[:16] of the canonical sorted-key JSON of `payload`."""
    canon = _canon(payload)
    blob = json.dumps(canon, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("ascii")).hexdigest()[:16]


@dataclass
class GraspCandidate:
    """One grasp candidate. Field order is contractual (Gate E0)."""
    target_id: str                       # e.g. "target_debris_v0"
    grasp_point_id: str                  # CAD-JSON grasp feature id (D-6 source)
    grasp_pose_target: np.ndarray        # 4x4, frame C in T (origin=grasp point, z=approach normal)
    approach_direction_target: np.ndarray  # unit 3-vector in T (outward)
    capture_time: float                  # s, t_c since target_state epoch
    approach_velocity: float             # m/s residual closing speed at contact
    initial_joint_configuration: np.ndarray  # (6,) rad, q0
    task_constraint_mode: str            # "pose_6d" | "approach_5d" | "position_3d"
    capture_mode: str = "rigid_6dof"     # "rigid_6dof" | "point_3dof"
    target_state: dict = None            # {omega_dps: float, tumble_axis: (3,) inertial,
    #                                       attitude0_quat: (4,) scalar-first}
    target_inertia: dict = None          # {mass: kg, I: 3x3 about CoM (T axes), inertia_scale: float}
    scenario_hash: str = field(default=None)  # auto-computed; do not set manually

    def __post_init__(self):
        if self.target_state is None or self.target_inertia is None:
            raise ValueError("target_state and target_inertia are required")
        if self.task_constraint_mode not in TASK_CONSTRAINT_MODES:
            raise ValueError(f"task_constraint_mode must be one of {TASK_CONSTRAINT_MODES}")
        if self.capture_mode not in CAPTURE_MODES:
            raise ValueError(f"capture_mode must be one of {CAPTURE_MODES}")
        self.grasp_pose_target = np.asarray(self.grasp_pose_target, float).reshape(4, 4)
        a = np.asarray(self.approach_direction_target, float).reshape(3)
        n = np.linalg.norm(a)
        if n < 1e-12:
            raise ValueError("approach_direction_target must be a nonzero vector")
        self.approach_direction_target = a / n
        self.initial_joint_configuration = np.asarray(
            self.initial_joint_configuration, float).reshape(6)
        self.scenario_hash = scenario_hash_of(self.hash_payload())

    def hash_payload(self):
        """All scenario-defining inputs (everything except the hash itself)."""
        return {
            "target_id": self.target_id,
            "grasp_point_id": self.grasp_point_id,
            "grasp_pose_target": self.grasp_pose_target,
            "approach_direction_target": self.approach_direction_target,
            "capture_time": self.capture_time,
            "approach_velocity": self.approach_velocity,
            "initial_joint_configuration": self.initial_joint_configuration,
            "task_constraint_mode": self.task_constraint_mode,
            "capture_mode": self.capture_mode,
            "target_state": self.target_state,
            "target_inertia": self.target_inertia,
        }


@dataclass
class GraspEvaluationResult:
    """Evaluation output. Numeric payloads are stored as plain python types
    (float / list / dict) so that two evaluations of the same candidate compare
    bit-identically (test t7; provenance wall_time_ms excluded, see canonical()).
    A candidate that fails early (e.g. IK) still returns the FULL structure with
    None for the metrics that were never reached."""
    ik_feasible: bool
    ik_solution_set: list        # [{q, residual_position, residual_orientation,
    #                               joint_limit_margin, jacobian_singular_values,
    #                               condition_number, task_rank, task_nullity}, ...]
    pose_residual: dict          # selected solution: {position_m, orientation_rad}
    joint_limit_margin: float    # rad, selected solution
    task_jacobian_rank: int
    task_nullity: int
    manipulability: dict         # {sqrt_det_JJT, sigma_min} @ selected solution
    collision_margin: dict       # {min_margin_m, t_at_min_s}
    base_attitude_change: float  # deg, peak attitude deviation over approach
    base_angular_velocity_metric: float  # deg/s, peak |w_base|
    capture_impulse_6d: dict     # {J_t_Ns: [3], L_grasp_Nms: [3]} impulse ON target,
    #                              couple at the grasp point (junction_couple)
    impulse_moment_at_grasp: dict  # {L_grasp_Nms: [3], norm_Nms: float}
    post_capture_angular_velocity: float  # deg/s |omega+| (combined body for
    #                              rigid_6dof; target body for point_3dof)
    wheel_momentum_required: float  # N*m*s = |H_c| about combined CoM
    thruster_impulse_required: float  # N*s = |H_c| / lever  (sim_08 couple)
    propellant_required: float   # g, configured Isp class (sim_08 formula)
    flexible_energy_proxy: float  # J, max(strain+kinetic) of ANCF panel response
    impact_severity_proxy: float  # PROXY ONLY: |J_t| + |L_grasp|/lever_ref combination;
    #                              NOT a contact force, NOT a grasp probability
    admissibility_flags: dict    # {constraint_name: bool} per hard constraint
    failure_reason_codes: list   # subset of FAILURE_CODES
    solver_provenance: dict      # {component: {module, commit, units, wall_time_ms}}
    scenario_hash: str
    # overall_score: <INTENTIONALLY NOT IMPLEMENTED - Gate E0 ruling: hard-constraint
    #                 screening -> per-metric values -> Pareto front. An aggregated
    #                 weighted score is deferred; this comment reserves the slot.>

    def to_dict(self):
        return asdict(self)

    def canonical(self, exclude_timing=True):
        """Dict for bitwise determinism comparison. Provenance wall_time_ms is
        the only intentionally non-deterministic field and is excluded."""
        d = self.to_dict()
        if exclude_timing:
            prov = d.get("solver_provenance") or {}
            d["solver_provenance"] = {
                k: {kk: vv for kk, vv in (v or {}).items() if kk != "wall_time_ms"}
                for k, v in prov.items()}
        return d
