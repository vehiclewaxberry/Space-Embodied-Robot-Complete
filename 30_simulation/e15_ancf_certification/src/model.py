"""Numerical kernels for the isolated E1.5 ANCF certification campaign.

The frozen project model is imported read-only.  This module deliberately uses
displacement coordinates about the straight equilibrium, while the legacy
production code integrates absolute nodal coordinates.  That provides an
independent state representation without changing the underlying ANCF mass,
elastic-force, damping, or excitation definitions.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import time

# Importing the frozen tree must not create __pycache__ outside this dedicated
# directory.  The campaign launcher also sets PYTHONDONTWRITEBYTECODE.
sys.dont_write_bytecode = True
for _name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_name, "1")

import numpy as np
from scipy.integrate import BDF, Radau, solve_ivp
from scipy.linalg import eigh


CERT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = CERT_ROOT.parents[1]
for _path in (
    REPO_ROOT / "30_simulation" / "sim_09_grasp_evaluator" / "src",
    REPO_ROOT / "30_simulation" / "sim_07_ancf_flexible",
    REPO_ROOT / "30_simulation" / "common",
    REPO_ROOT / "30_simulation" / "sim_05_free_floating_arm",
    REPO_ROOT / "30_simulation" / "sim_06_capture_impulse",
):
    sys.path.insert(0, str(_path))

from ancf_beam import Beam, EA as EA_NOM, EI as EI_NOM, EI_CASES, L_TOT  # noqa: E402
import e1_thin_slice  # noqa: E402
import sim_07a_task_response as sim07  # noqa: E402


SOLVER_CLASSES = {"Radau": Radau, "BDF": BDF}
NUMERIC_METRICS = (
    "tip_peak_m", "root_moment_peak_Nm", "strain_energy_peak_J",
    "total_energy_peak_J",
)


class IntegrationFailure(RuntimeError):
    """Typed numerical/resource termination with auditable diagnostics."""

    def __init__(self, message: str, diagnostics: dict):
        super().__init__(message)
        self.diagnostics = dict(diagnostics)


class _AnchorWallTimeExceeded(RuntimeError):
    """Internal sentinel used by the child-process anchor guard."""


def canonicalize(value):
    if isinstance(value, np.ndarray):
        return [canonicalize(v) for v in value.tolist()]
    if isinstance(value, np.generic):
        return canonicalize(value.item())
    if isinstance(value, dict):
        return {str(k): canonicalize(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [canonicalize(v) for v in value]
    if isinstance(value, float):
        if not np.isfinite(value):
            raise ValueError("non-finite value cannot be hashed")
        return 0.0 if value == 0.0 else value
    return value


def canonical_hash(value) -> str:
    payload = json.dumps(
        canonicalize(value), ensure_ascii=True, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _build_beam(n_elements: int, ei_case: str = "nominal", zeta: float = 0.01):
    ei = float(EI_CASES[ei_case])
    beam = Beam(int(n_elements), ei=ei, ea=EA_NOM * ei / EI_NOM)
    tangent = beam.tangent_stiffness()
    free = beam.free
    mass = beam.M[np.ix_(free, free)]
    stiffness = tangent[np.ix_(free, free)]
    w2 = eigh(stiffness, mass, eigvals_only=True)
    positive = np.sort(w2[w2 > 1.0e-9])
    f1_hz = float(np.sqrt(positive[0]) / (2.0 * np.pi))
    beam.set_rayleigh_damping(zeta, f_lo=f1_hz, K_t=tangent)
    damping = beam.C[np.ix_(free, free)]
    return beam, mass, stiffness, damping, f1_hz


def _project_base_jump(dv, dw, rotation_IS, com_chaser_S):
    rotation = np.asarray(rotation_IS, dtype=float)
    com = np.asarray(com_chaser_S, dtype=float)
    dv = np.asarray(dv, dtype=float)
    dw = np.asarray(dw, dtype=float)
    r_rel_I = rotation @ (sim07.R_F_S - com)
    y_axis_I = rotation @ sim07.Y_F_S
    z_axis_I = rotation @ np.array([0.0, 0.0, 1.0])
    x_axis_I = rotation @ sim07.X_S
    dv_root = dv + np.cross(dw, r_rel_I)
    gradient = np.cross(dw, y_axis_I)
    return {
        "a_tr_mps": -float(dv_root @ z_axis_I),
        "b_tr_per_s": -float(gradient @ z_axis_I),
        "dropped_axial_mps": -float(dv_root @ y_axis_I),
        "dropped_inplane_root_mps": -float(dv_root @ x_axis_I),
        "dv_chaser": dv,
        "dw_chaser": dw,
        "rotation_IS": rotation,
        "com_chaser_S": com,
    }


def nominal_excitation():
    modes = sim07.capture_excitations()
    base = modes["6dof_rigid_lock"]
    projected = sim07.panel_excitation(base["dv"], base["dw"])
    return {
        "a_tr_mps": float(projected["a_tr"]),
        "b_tr_per_s": float(projected["b_tr"]),
        "source": "sim07.capture_excitations/6dof_rigid_lock",
    }


def reconstruct_historical_case(case_id: str):
    """Rebuild one frozen E1 physical input without writing to legacy paths."""
    csv_path = REPO_ROOT / "30_simulation" / "sim_09_grasp_evaluator" / "results" / "e1_results_72cases.csv"
    import csv

    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        rows = {row["case_id"]: row for row in csv.DictReader(stream)}
    if case_id not in rows:
        raise KeyError(f"historical case missing from frozen E1 CSV: {case_id}")
    source = rows[case_id]
    solutions = json.loads(source["ik_solution_set_json"])
    if not solutions:
        raise ValueError(f"historical case lacks selected IK solution: {case_id}")
    selected_q = np.asarray(solutions[0]["q"], dtype=float)
    specs = [s for s in e1_thin_slice.build_all_cases() if s["case_id"] == case_id]
    if len(specs) != 1:
        raise ValueError(f"case specification is not unique: {case_id}")
    spec = specs[0]
    candidate = e1_thin_slice.make_candidate(spec)
    capture, placement = e1_thin_slice._flex_capture_chain(candidate, selected_q)
    projected = _project_base_jump(
        capture["dv_chaser"], capture["dw_chaser"], placement["R_IS"],
        capture["meta"]["com_chaser_S"])
    physical = {
        "case_id": case_id,
        "legacy_scenario_hash": source["scenario_hash"],
        "historical_flex_status": source["flex_status"],
        "selected_q": selected_q,
        "candidate_hash_rebuilt": candidate.scenario_hash,
        "spec": spec,
        **projected,
    }
    physical["physical_input_hash"] = canonical_hash(physical)
    physical["legacy_row_hash"] = canonical_hash(source)
    physical["legacy_csv_sha256"] = sha256_file(csv_path)
    return physical


def prepare_system(n_elements: int, excitation: dict, scale: float = 1.0,
                   ei_case: str = "nominal", zeta: float = 0.01):
    beam, mass, stiffness, damping, f1_hz = _build_beam(
        n_elements, ei_case=ei_case, zeta=zeta)
    a_tr = float(excitation["a_tr_mps"]) * float(scale)
    b_tr = float(excitation["b_tr_per_s"]) * float(scale)
    ed_full = beam.initial_velocity_field(lambda x: a_tr + b_tr * x, None)
    free = beam.free
    velocity_jump = ed_full[free]
    equilibrium_force = beam.q_int(beam.e0)[free].copy()
    inv_mass = np.linalg.inv(mass)
    n = free.size
    jacobian = np.block([
        [np.zeros((n, n)), np.eye(n)],
        [-inv_mass @ stiffness, -inv_mass @ damping],
    ])
    tip_global = 4 * (beam.n_node - 1) + 1
    tip_local = int(np.where(free == tip_global)[0][0])
    return {
        "beam": beam,
        "free": free,
        "mass": mass,
        "stiffness": stiffness,
        "damping": damping,
        "inv_mass": inv_mass,
        "equilibrium_force": equilibrium_force,
        "velocity_jump": velocity_jump,
        "generalized_impulse": mass @ velocity_jump,
        "jacobian": jacobian,
        "tip_local": tip_local,
        "f1_hz": f1_hz,
        "a_tr_mps": a_tr,
        "b_tr_per_s": b_tr,
    }


def _rhs(system, external_force=None):
    beam = system["beam"]
    free = system["free"]
    inv_mass = system["inv_mass"]
    damping = system["damping"]
    equilibrium_force = system["equilibrium_force"]
    n = free.size
    force = np.zeros(n) if external_force is None else np.asarray(external_force, float)

    def fun(_time, state):
        displacement = state[:n]
        velocity = state[n:]
        coordinates = beam.e0.copy()
        coordinates[free] += displacement
        restoring = beam.q_int(coordinates)[free] - equilibrium_force
        acceleration = inv_mass @ (force - restoring - damping @ velocity)
        return np.concatenate((velocity, acceleration))

    return fun


def _initial_state(system, impulse_mode: str):
    n = system["free"].size
    velocity = system["velocity_jump"] if impulse_mode == "velocity_jump" else np.zeros(n)
    return np.concatenate((np.zeros(n), velocity))


def _sample_metrics(system, times, states):
    beam = system["beam"]
    free = system["free"]
    mass = system["mass"]
    n = free.size
    tip = states[system["tip_local"], :].copy()
    root_moment = np.empty(times.size)
    strain = np.empty(times.size)
    kinetic = np.empty(times.size)
    for index in range(times.size):
        coordinates = beam.e0.copy()
        coordinates[free] += states[:n, index]
        velocity = states[n:, index]
        root_moment[index] = beam.root_moment(coordinates)
        strain[index] = beam.strain_energy(coordinates)
        kinetic[index] = 0.5 * velocity @ (mass @ velocity)
    metrics = {
        "tip_peak_m": float(np.max(np.abs(tip))),
        "root_moment_peak_Nm": float(np.max(np.abs(root_moment))),
        "strain_energy_peak_J": float(np.max(strain)),
        "total_energy_peak_J": float(np.max(strain + kinetic)),
    }
    return metrics, tip


def integrate_adaptive(system, method: str, t_end_s: float, n_eval: int,
                       rtol: float, atol: float, max_step: float,
                       impulse_mode: str = "velocity_jump",
                       pulse_duration_s: float | None = None,
                       max_wall_s: float = 12.0):
    """Adaptive Radau/BDF integration for the inexpensive anchor matrix."""
    if method not in SOLVER_CLASSES:
        raise ValueError(f"unsupported method: {method}")
    times = np.linspace(0.0, float(t_end_s), int(n_eval))
    started = time.perf_counter()
    totals = {"nfev": 0, "njev": 0, "nlu": 0, "n_steps": 0}

    def guarded_solve(fun, *args, **kwargs):
        def guarded_fun(t, state):
            if time.perf_counter() - started >= float(max_wall_s):
                raise _AnchorWallTimeExceeded(
                    f"anchor wall-time limit {max_wall_s:g} s reached")
            return fun(t, state)
        try:
            return solve_ivp(guarded_fun, *args, **kwargs)
        except _AnchorWallTimeExceeded as exc:
            raise IntegrationFailure(str(exc), {
                "classification": "SOLVER_NONCONVERGENCE",
                "specific_classification": "RESOURCE_LIMIT_WALL",
                "termination_reason": "RESOURCE_LIMIT_WALL", "status": -1,
                "nfev": None, "njev": None, "nlu": None, "n_steps": None,
                "wall_s": float(time.perf_counter() - started),
            }) from exc

    if impulse_mode == "velocity_jump":
        solution = guarded_solve(
            _rhs(system), (0.0, float(t_end_s)), _initial_state(system, impulse_mode),
            method=method, rtol=float(rtol), atol=float(atol),
            max_step=float(max_step), jac=system["jacobian"],
            t_eval=times)
        if not solution.success:
            raise IntegrationFailure(solution.message, {
                "classification": "SOLVER_NONCONVERGENCE",
                "specific_classification": classify_message(solution.message),
                "termination_reason": "SOLVER_FAILURE", "status": solution.status,
                "nfev": solution.nfev, "njev": solution.njev, "nlu": solution.nlu,
                "n_steps": max(len(solution.t) - 1, 0),
            })
        states = solution.y
        totals.update({
            "nfev": int(solution.nfev), "njev": int(solution.njev),
            "nlu": int(solution.nlu), "n_steps": max(len(solution.t) - 1, 0),
        })
    elif impulse_mode == "rectangular_pulse":
        duration = float(pulse_duration_s or 0.0)
        if not 0.0 < duration < t_end_s:
            raise ValueError("pulse_duration_s must lie inside the integration interval")
        force = system["generalized_impulse"] / duration
        first = guarded_solve(
            _rhs(system, force), (0.0, duration), _initial_state(system, impulse_mode),
            method=method, rtol=float(rtol), atol=float(atol),
            max_step=min(float(max_step), duration / 10.0),
            jac=system["jacobian"], dense_output=True)
        if not first.success:
            raise IntegrationFailure(first.message, {
                "classification": "SOLVER_NONCONVERGENCE",
                "specific_classification": classify_message(first.message),
                "termination_reason": "SOLVER_FAILURE", "status": first.status,
                "nfev": first.nfev, "njev": first.njev, "nlu": first.nlu,
                "n_steps": max(len(first.t) - 1, 0),
            })
        second = guarded_solve(
            _rhs(system), (duration, float(t_end_s)), first.y[:, -1],
            method=method, rtol=float(rtol), atol=float(atol),
            max_step=float(max_step), jac=system["jacobian"], dense_output=True)
        if not second.success:
            raise IntegrationFailure(second.message, {
                "classification": "SOLVER_NONCONVERGENCE",
                "specific_classification": classify_message(second.message),
                "termination_reason": "SOLVER_FAILURE", "status": second.status,
                "nfev": first.nfev + second.nfev,
                "njev": first.njev + second.njev, "nlu": first.nlu + second.nlu,
                "n_steps": max(len(first.t) + len(second.t) - 2, 0),
            })
        mask = times <= duration
        states = np.empty((first.y.shape[0], times.size))
        states[:, mask] = first.sol(times[mask])
        states[:, ~mask] = second.sol(times[~mask])
        totals.update({
            "nfev": int(first.nfev + second.nfev),
            "njev": int(first.njev + second.njev),
            "nlu": int(first.nlu + second.nlu),
            "n_steps": max(len(first.t) + len(second.t) - 2, 0),
        })
    else:
        raise ValueError(f"unknown impulse mode: {impulse_mode}")

    metrics, tip = _sample_metrics(system, times, states)
    return {
        "times": times, "states": states, "tip": tip, "metrics": metrics,
        "diagnostics": {
            **totals, "success": True, "status": 0,
            "classification": "COMPLETED", "specific_classification": "COMPLETED",
            "termination_reason": "COMPLETED",
            "wall_s": float(time.perf_counter() - started),
        },
    }


def classify_message(message: str) -> str:
    text = str(message).upper()
    if "REQUIRED STEP SIZE IS LESS" in text or "SPACING BETWEEN NUMBERS" in text:
        return "NUMERICAL_STEP_UNDERFLOW"
    if "NAN" in text or "NON-FINITE" in text or "OVERFLOW" in text:
        return "NUMERIC_OVERFLOW"
    return "SOLVER_NONCONVERGENCE"


def integrate_streaming(system, method: str, t_end_s: float, n_eval: int,
                        rtol: float, atol: float, max_step: float,
                        max_accepted_steps: int, max_nfev: int,
                        max_wall_s: float):
    """Resource-bounded full-history run using SciPy's public OdeSolver API."""
    try:
        solver_class = SOLVER_CLASSES[method]
    except KeyError as exc:
        raise ValueError(f"unsupported method: {method}") from exc
    times = np.linspace(0.0, float(t_end_s), int(n_eval))
    state0 = _initial_state(system, "velocity_jump")
    solver = solver_class(
        _rhs(system), 0.0, state0, float(t_end_s), rtol=float(rtol),
        atol=float(atol), max_step=float(max_step), jac=system["jacobian"])
    states = np.empty((state0.size, times.size), dtype=float)
    next_sample = 0
    accepted = 0
    started = time.perf_counter()
    message = ""

    def diag(classification, specific, reason, success=False):
        return {
            "success": bool(success), "status": 0 if success else -1,
            "classification": classification,
            "specific_classification": specific,
            "termination_reason": reason, "solver_message": str(message),
            "n_steps": int(accepted), "nfev": int(solver.nfev),
            "njev": int(solver.njev), "nlu": int(solver.nlu),
            "wall_s": float(time.perf_counter() - started),
            "last_time_s": float(solver.t),
        }

    while solver.status == "running":
        elapsed = time.perf_counter() - started
        if elapsed >= float(max_wall_s):
            message = f"wall-time limit {max_wall_s:g} s reached before t_bound"
            raise IntegrationFailure(message, diag(
                "SOLVER_NONCONVERGENCE", "RESOURCE_LIMIT_WALL",
                "RESOURCE_LIMIT_WALL"))
        if accepted >= int(max_accepted_steps):
            message = f"accepted-step limit {max_accepted_steps} reached before t_bound"
            raise IntegrationFailure(message, diag(
                "SOLVER_NONCONVERGENCE", "RESOURCE_LIMIT_ACCEPTED_STEPS",
                "RESOURCE_LIMIT_ACCEPTED_STEPS"))
        if solver.nfev >= int(max_nfev):
            message = f"nfev limit {max_nfev} reached before t_bound"
            raise IntegrationFailure(message, diag(
                "SOLVER_NONCONVERGENCE", "RESOURCE_LIMIT_NFEV",
                "RESOURCE_LIMIT_NFEV"))
        previous = float(solver.t)
        message = solver.step() or ""
        if solver.status == "failed":
            specific = classify_message(message)
            raise IntegrationFailure(str(message), diag(
                "SOLVER_NONCONVERGENCE", specific, "SOLVER_FAILURE"))
        if not float(solver.t) > previous:
            message = "solver accepted a non-advancing step"
            raise IntegrationFailure(message, diag(
                "PROGRAM_EXCEPTION", "NON_ADVANCING_STEP", "PROGRAM_EXCEPTION"))
        accepted += 1
        local = solver.dense_output()
        side = "left" if method == "BDF" and solver.status != "finished" else "right"
        stop = int(np.searchsorted(times, solver.t, side=side))
        if stop > next_sample:
            states[:, next_sample:stop] = local(times[next_sample:stop])
            next_sample = stop

    if solver.status != "finished" or next_sample != times.size:
        message = "solver finished without covering all requested samples"
        raise IntegrationFailure(message, diag(
            "PROGRAM_EXCEPTION", "INCOMPLETE_SAMPLING", "PROGRAM_EXCEPTION"))
    metrics, tip = _sample_metrics(system, times, states)
    diagnostics = diag("COMPLETED", "COMPLETED", "COMPLETED", success=True)
    return {"times": times, "states": states, "tip": tip,
            "metrics": metrics, "diagnostics": diagnostics}


def modal_reference(system, times, impulse_mode="velocity_jump",
                    pulse_duration_s=None):
    """Exact per-mode linear reference from the tangent M/C/K system."""
    mass = system["mass"]
    stiffness = system["stiffness"]
    damping = system["damping"]
    w2, modes = eigh(stiffness, mass)
    keep = w2 > 1.0e-9
    w = np.sqrt(w2[keep])
    modes = modes[:, keep]
    modal_damping = np.diag(modes.T @ damping @ modes)
    modal_velocity = modes.T @ mass @ system["velocity_jump"]
    modal_force = modes.T @ system["generalized_impulse"]
    q = np.empty((w.size, len(times)), dtype=float)
    duration = None if pulse_duration_s is None else float(pulse_duration_s)

    times = np.asarray(times, dtype=float)

    def homogeneous(q0, v0, local_times, omega, damping_coefficient):
        """Closed-form free response, including under/critical/over damping."""
        local_times = np.asarray(local_times, dtype=float)
        alpha = 0.5 * damping_coefficient
        if alpha < omega * (1.0 - 1.0e-12):
            wd = np.sqrt(omega * omega - alpha * alpha)
            cosine = np.cos(wd * local_times)
            sine = np.sin(wd * local_times)
            decay = np.exp(-alpha * local_times)
            a = q0
            b = (v0 + alpha * q0) / wd
            position = decay * (a * cosine + b * sine)
            velocity = decay * (
                (-alpha * a + wd * b) * cosine
                + (-alpha * b - wd * a) * sine)
            return position, velocity
        if alpha > omega * (1.0 + 1.0e-12):
            root = np.sqrt(alpha * alpha - omega * omega)
            r1, r2 = -alpha + root, -alpha - root
            a = (v0 - r2 * q0) / (r1 - r2)
            b = (r1 * q0 - v0) / (r1 - r2)
            e1, e2 = np.exp(r1 * local_times), np.exp(r2 * local_times)
            return a * e1 + b * e2, r1 * a * e1 + r2 * b * e2
        decay = np.exp(-alpha * local_times)
        b = v0 + alpha * q0
        position = (q0 + b * local_times) * decay
        velocity = (b - alpha * (q0 + b * local_times)) * decay
        return position, velocity

    for index, (omega, c_i, v_i, impulse_i) in enumerate(
            zip(w, modal_damping, modal_velocity, modal_force)):
        if impulse_mode == "velocity_jump":
            q[index] = homogeneous(0.0, v_i, times, omega, c_i)[0]
        elif impulse_mode == "rectangular_pulse":
            if duration is None or duration <= 0.0:
                raise ValueError("pulse duration required")
            constant_force = impulse_i / duration
            static = constant_force / (omega * omega)
            forced_mask = times <= duration
            forced_q, forced_v = homogeneous(
                -static, 0.0, times[forced_mask], omega, c_i)
            q[index, forced_mask] = static + forced_q
            end_q_h, end_v = homogeneous(
                -static, 0.0, np.array([duration]), omega, c_i)
            end_q = static + end_q_h[0]
            if np.any(~forced_mask):
                q[index, ~forced_mask] = homogeneous(
                    end_q, end_v[0], times[~forced_mask] - duration,
                    omega, c_i)[0]
        else:
            raise ValueError(f"unknown impulse mode: {impulse_mode}")
    displacement = modes @ q
    return displacement[system["tip_local"], :]


def newmark_linear(system, time_step_s: float, t_end_s: float):
    """Average-acceleration Newmark solution of the independent tangent FE model."""
    dt = float(time_step_s)
    count = int(round(float(t_end_s) / dt))
    times = np.linspace(0.0, count * dt, count + 1)
    mass, damping, stiffness = (
        system["mass"], system["damping"], system["stiffness"])
    n = mass.shape[0]
    displacement = np.zeros(n)
    velocity = system["velocity_jump"].copy()
    acceleration = np.linalg.solve(
        mass, -damping @ velocity - stiffness @ displacement)
    history = np.empty((n, count + 1))
    history[:, 0] = displacement
    beta, gamma = 0.25, 0.5
    a0 = 1.0 / (beta * dt * dt)
    a1 = gamma / (beta * dt)
    a2 = 1.0 / (beta * dt)
    a3 = 1.0 / (2.0 * beta) - 1.0
    a4 = gamma / beta - 1.0
    a5 = dt * (gamma / (2.0 * beta) - 1.0)
    effective = stiffness + a0 * mass + a1 * damping
    for step in range(1, count + 1):
        rhs = (mass @ (a0 * displacement + a2 * velocity + a3 * acceleration)
               + damping @ (a1 * displacement + a4 * velocity + a5 * acceleration))
        new_displacement = np.linalg.solve(effective, rhs)
        new_acceleration = (
            a0 * (new_displacement - displacement) - a2 * velocity - a3 * acceleration)
        new_velocity = velocity + dt * (
            (1.0 - gamma) * acceleration + gamma * new_acceleration)
        displacement, velocity, acceleration = (
            new_displacement, new_velocity, new_acceleration)
        history[:, step] = displacement
    tip = history[system["tip_local"], :]
    return times, tip


def relative_difference(left: float, right: float, floor=1.0e-30) -> float:
    return float(abs(float(left) - float(right)) /
                 max(abs(float(left)), abs(float(right)), float(floor)))


def metric_differences(left: dict, right: dict):
    return {key: relative_difference(left[key], right[key]) for key in NUMERIC_METRICS}
