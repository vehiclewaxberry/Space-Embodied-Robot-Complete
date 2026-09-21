"""Bounded R2 constrained-dynamics candidate.

This module consumes the hash-fixed Unified R2 zero-momentum backend without
modifying it.  It adds the missing prismatic lock semantics through a KKT
system and independently cross-checks the result by coordinate elimination.

The numerical efforts in this package are diagnostic excitations.  They are
not actuator limits or commands.  Contact, target attachment, collision, path
search, control, and flight qualification are intentionally outside scope.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Callable, Mapping, Sequence
import xml.etree.ElementTree as ET

for _name in (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "BLIS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_name, "1")

import numpy as np
import yaml
from scipy.integrate import solve_ivp
from scipy.linalg import block_diag, expm


PACKAGE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_DIR.parents[1]
AUTHORITY_PATH = PACKAGE_DIR / "contracts" / "R2_DYNAMICS_AUTHORITY_V1.yaml"
CONFIG_PATH = PACKAGE_DIR / "config" / "R2_DYNAMICS_ENGINEERING_CONFIG_V1.json"


class ContractError(RuntimeError):
    """Raised for malformed or hash-drifted authority inputs."""


def _reject_duplicate_key(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def load_json_strict(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_key)


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def load_contracts() -> tuple[dict[str, Any], dict[str, Any]]:
    authority = yaml.safe_load(AUTHORITY_PATH.read_text(encoding="utf-8"))
    config = load_json_strict(CONFIG_PATH)
    if authority.get("schema") != "R2_DYNAMICS_AUTHORITY_V1":
        raise ContractError("AUTHORITY_SCHEMA_MISMATCH")
    if config.get("schema") != "R2_DYNAMICS_ENGINEERING_CONFIG_V1":
        raise ContractError("CONFIG_SCHEMA_MISMATCH")
    return authority, config


def validate_source_pins(
    project_root: Path, authority: Mapping[str, Any]
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for pin_id, pin in authority["source_pins"].items():
        path = project_root / pin["path"]
        exists = path.is_file()
        actual_bytes = path.stat().st_size if exists else None
        actual_sha = file_sha256(path) if exists else None
        match = bool(
            exists
            and actual_bytes == int(pin["bytes"])
            and actual_sha == str(pin["sha256"]).upper()
        )
        rows.append(
            {
                "id": pin_id,
                "path": pin["path"],
                "expected_bytes": int(pin["bytes"]),
                "actual_bytes": actual_bytes,
                "expected_sha256": str(pin["sha256"]).upper(),
                "actual_sha256": actual_sha,
                "match": match,
            }
        )
    return {
        "schema": "R2_DYNAMICS_SOURCE_BINDING_V1",
        "pins": rows,
        "summary": {
            "matched": sum(row["match"] for row in rows),
            "total": len(rows),
        },
        "all_match": all(row["match"] for row in rows),
        "next_stage_authorized": False,
        "release_credit": False,
    }


def _install_backend_imports(project_root: Path) -> None:
    rebind = (
        project_root
        / "30_simulation"
        / "sim_13_physics_gated_embodied_grasping"
        / "v2_system_rebind"
    )
    for path in reversed((rebind / "runtime_fail_closed_backends_v2", rebind)):
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)


def load_backend(project_root: Path):
    _install_backend_imports(project_root)
    from sim13_v2_backends.dynamics_backend import UnifiedR2DynamicsBackend

    return UnifiedR2DynamicsBackend(project_root=project_root)


def parse_urdf_joint_contract(
    project_root: Path, authority: Mapping[str, Any]
) -> dict[str, Any]:
    pin = authority["source_pins"]["unified_r2_urdf"]
    root = ET.parse(project_root / pin["path"]).getroot()
    movable: list[dict[str, Any]] = []
    for joint in root.findall("joint"):
        joint_type = joint.attrib.get("type")
        if joint_type not in {"revolute", "continuous", "prismatic"}:
            continue
        limit = joint.find("limit")
        lower = None if limit is None else limit.attrib.get("lower")
        upper = None if limit is None else limit.attrib.get("upper")
        movable.append(
            {
                "name": joint.attrib["name"],
                "type": joint_type,
                "lower": None if lower is None else float(lower),
                "upper": None if upper is None else float(upper),
            }
        )
    expected_order = list(authority["coordinate_contract"]["joint_order"])
    by_name = {item["name"]: item for item in movable}
    if set(by_name) != set(expected_order):
        raise ContractError("UNIFIED_R2_MOVABLE_JOINT_SET_MISMATCH")
    ordered = [by_name[name] for name in expected_order]
    if [item["type"] for item in ordered] != ["revolute"] * 6 + ["prismatic"] * 2:
        raise ContractError("UNIFIED_R2_JOINT_TYPE_CONTRACT_MISMATCH")
    limits = np.asarray([[item["lower"], item["upper"]] for item in ordered], dtype=float)
    if limits.shape != (8, 2) or not np.all(np.isfinite(limits)):
        raise ContractError("UNIFIED_R2_FINITE_LIMITS_ABSENT")
    return {
        "joint_order": expected_order,
        "joint_types": [item["type"] for item in ordered],
        "limits_mixed_rad_m": limits.tolist(),
        "all_limits_finite": True,
    }


def finite_vector(values: Sequence[float], size: int, field: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.shape != (size,) or not np.all(np.isfinite(array)):
        raise ValueError(f"{field}_MUST_HAVE_{size}_FINITE_VALUES")
    return array


def solve_locked_kkt(
    mass: np.ndarray,
    bias: Sequence[float],
    effort: Sequence[float],
    constraint_jacobian: np.ndarray,
) -> dict[str, np.ndarray | float]:
    """Solve M*a + b = tau + J.T*r with J*a = 0."""

    mass = np.asarray(mass, dtype=float)
    n = mass.shape[0] if mass.ndim == 2 else 0
    if mass.shape != (n, n) or n < 1 or not np.all(np.isfinite(mass)):
        raise ValueError("KKT_MASS_MATRIX_MALFORMED")
    bias_v = finite_vector(bias, n, "KKT_BIAS")
    effort_v = finite_vector(effort, n, "KKT_EFFORT")
    jac = np.asarray(constraint_jacobian, dtype=float)
    if jac.ndim != 2 or jac.shape[1] != n or not np.all(np.isfinite(jac)):
        raise ValueError("KKT_CONSTRAINT_JACOBIAN_MALFORMED")
    m = jac.shape[0]
    kkt = np.block([[mass, -jac.T], [jac, np.zeros((m, m))]])
    rhs = np.concatenate((effort_v - bias_v, np.zeros(m)))
    solution = np.linalg.solve(kkt, rhs)
    acceleration = solution[:n]
    reaction = solution[n:]
    equilibrium = mass @ acceleration + bias_v - effort_v - jac.T @ reaction
    return {
        "acceleration": acceleration,
        "reaction": reaction,
        "equilibrium_residual": equilibrium,
        "constraint_acceleration": jac @ acceleration,
        "kkt_condition_number": float(np.linalg.cond(kkt)),
    }


@dataclass
class ReducedR2Model:
    backend: Any
    qP_star_m: np.ndarray

    def __post_init__(self) -> None:
        self.qP_star_m = finite_vector(self.qP_star_m, 2, "qP_STAR")
        self.J = np.column_stack((np.zeros((2, 6)), np.eye(2)))

    @staticmethod
    def coordinate_step(index: int) -> float:
        return 2.0e-5 if index < 6 else 2.0e-6

    def mass(self, q8: Sequence[float]) -> np.ndarray:
        return np.asarray(self.backend.reduced_mass_matrix(finite_vector(q8, 8, "q8")))

    def mass_derivatives(self, q8: Sequence[float]) -> np.ndarray:
        q = finite_vector(q8, 8, "q8")
        derivatives = np.empty((8, 8, 8))
        for index in range(8):
            step = self.coordinate_step(index)
            plus = q.copy()
            minus = q.copy()
            plus[index] += step
            minus[index] -= step
            coarse = (self.mass(plus) - self.mass(minus)) / (2.0 * step)
            half = 0.5 * step
            plus = q.copy()
            minus = q.copy()
            plus[index] += half
            minus[index] -= half
            fine = (self.mass(plus) - self.mass(minus)) / (2.0 * half)
            derivatives[index] = (4.0 * fine - coarse) / 3.0
        return derivatives

    def connection_derivatives(self, q8: Sequence[float]) -> np.ndarray:
        """Richardson derivatives of A(q), where base_twist = A(q) dq."""

        q = finite_vector(q8, 8, "q8")
        derivatives = np.empty((8, 6, 8))
        for index in range(8):
            step = self.coordinate_step(index)
            plus = q.copy()
            minus = q.copy()
            plus[index] += step
            minus[index] -= step
            coarse = (
                self.backend.mechanical_connection(plus)
                - self.backend.mechanical_connection(minus)
            ) / (2.0 * step)
            half = 0.5 * step
            plus = q.copy()
            minus = q.copy()
            plus[index] += half
            minus[index] -= half
            fine = (
                self.backend.mechanical_connection(plus)
                - self.backend.mechanical_connection(minus)
            ) / (2.0 * half)
            derivatives[index] = (4.0 * fine - coarse) / 3.0
        return derivatives

    def base_twist_kinematics(
        self,
        q8: Sequence[float],
        dq8: Sequence[float],
        ddq8: Sequence[float],
    ) -> dict[str, np.ndarray]:
        """Return body-frame base twist and its body-coordinate time derivative."""

        q = finite_vector(q8, 8, "q8")
        rate = finite_vector(dq8, 8, "dq8")
        acceleration = finite_vector(ddq8, 8, "ddq8")
        connection = np.asarray(self.backend.mechanical_connection(q), dtype=float)
        connection_rate = np.tensordot(
            rate, self.connection_derivatives(q), axes=(0, 0)
        )
        return {
            "base_twist_body": connection @ rate,
            "base_twist_rate_body_coordinates": connection @ acceleration
            + connection_rate @ rate,
            "mechanical_connection": connection,
            "mechanical_connection_rate": connection_rate,
        }

    def bias(self, q8: Sequence[float], dq8: Sequence[float]) -> np.ndarray:
        q = finite_vector(q8, 8, "q8")
        rate = finite_vector(dq8, 8, "dq8")
        derivatives = self.mass_derivatives(q)
        mass_rate = np.tensordot(rate, derivatives, axes=(0, 0))
        energy_gradient = np.asarray(
            [rate @ derivatives[index] @ rate for index in range(8)]
        )
        return mass_rate @ rate - 0.5 * energy_gradient

    def locked_state(self, q6: Sequence[float], dq6: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
        return (
            np.concatenate((finite_vector(q6, 6, "q6"), self.qP_star_m)),
            np.concatenate((finite_vector(dq6, 6, "dq6"), np.zeros(2))),
        )

    def locked_acceleration(
        self,
        q6: Sequence[float],
        dq6: Sequence[float],
        tau6: Sequence[float],
        tauP: Sequence[float],
    ) -> dict[str, Any]:
        q8, dq8 = self.locked_state(q6, dq6)
        tau = np.concatenate(
            (finite_vector(tau6, 6, "tau6"), finite_vector(tauP, 2, "tauP"))
        )
        mass = self.mass(q8)
        bias = self.bias(q8, dq8)
        kkt = solve_locked_kkt(mass, bias, tau, self.J)

        # Independent coordinate elimination: ddqP=0 is substituted before solve.
        acceleration6 = np.linalg.solve(mass[:6, :6], tau[:6] - bias[:6])
        acceleration_eliminated = np.concatenate((acceleration6, np.zeros(2)))
        reaction_eliminated = (
            mass[6:, :6] @ acceleration6 + bias[6:] - tau[6:]
        )
        return {
            "q8": q8,
            "dq8": dq8,
            "mass": mass,
            "bias": bias,
            "tau": tau,
            "kkt_acceleration": kkt["acceleration"],
            "kkt_reaction_N": kkt["reaction"],
            "kkt_equilibrium_residual": kkt["equilibrium_residual"],
            "constraint_acceleration": kkt["constraint_acceleration"],
            "raw_unscaled_kkt_condition_number_no_credit": kkt[
                "kkt_condition_number"
            ],
            "eliminated_acceleration": acceleration_eliminated,
            "eliminated_reaction_N": reaction_eliminated,
            "acceleration_cross_revolute_max_abs_rad_s2": float(
                np.max(
                    np.abs(
                        kkt["acceleration"][:6]
                        - acceleration_eliminated[:6]
                    )
                )
            ),
            "acceleration_cross_prismatic_max_abs_m_s2": float(
                np.max(
                    np.abs(
                        kkt["acceleration"][6:]
                        - acceleration_eliminated[6:]
                    )
                )
            ),
            "reaction_cross_max_abs_N": float(
                np.max(np.abs(kkt["reaction"] - reaction_eliminated))
            ),
        }

    def actuated_acceleration(
        self, q8: Sequence[float], dq8: Sequence[float], tau8: Sequence[float]
    ) -> dict[str, np.ndarray]:
        q = finite_vector(q8, 8, "q8")
        rate = finite_vector(dq8, 8, "dq8")
        effort = finite_vector(tau8, 8, "tau8")
        mass = self.mass(q)
        bias = self.bias(q, rate)
        acceleration = np.linalg.solve(mass, effort - bias)
        return {"mass": mass, "bias": bias, "acceleration": acceleration}

    def kinetic_energy(self, q6: Sequence[float], dq6: Sequence[float]) -> float:
        q8, dq8 = self.locked_state(q6, dq6)
        return float(0.5 * dq8 @ self.mass(q8) @ dq8)

    def locked_rhs(self, state12: Sequence[float]) -> np.ndarray:
        state = finite_vector(state12, 12, "locked_state12")
        q6 = state[:6]
        dq6 = state[6:]
        q8, dq8 = self.locked_state(q6, dq6)
        mass = self.mass(q8)
        bias = self.bias(q8, dq8)
        ddq6 = np.linalg.solve(mass[:6, :6], -bias[:6])
        return np.concatenate((dq6, ddq6))


def rk4_integrate(
    rhs: Callable[[np.ndarray], np.ndarray], initial: np.ndarray, step_s: float, steps: int
) -> tuple[np.ndarray, list[np.ndarray]]:
    state = np.asarray(initial, dtype=float).copy()
    history = [state.copy()]
    for _ in range(steps):
        k1 = rhs(state)
        k2 = rhs(state + 0.5 * step_s * k1)
        k3 = rhs(state + 0.5 * step_s * k2)
        k4 = rhs(state + step_s * k3)
        state += (step_s / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        history.append(state.copy())
    return state, history


def _relative_norm(left: np.ndarray, right: np.ndarray, floor: float = 1.0e-15) -> float:
    return float(
        np.linalg.norm(left - right)
        / max(np.linalg.norm(left), np.linalg.norm(right), floor)
    )


def audit_actuator_contract(project_root: Path, authority: Mapping[str, Any]) -> dict[str, Any]:
    pin = authority["source_pins"]["actuator_candidate"]
    contract = load_json_strict(project_root / pin["path"])
    records = contract.get("joint_records", [])
    expected = list(authority["coordinate_contract"]["joint_order"])
    null_fields = 0
    total_fields = 0
    per_joint: list[dict[str, Any]] = []
    for record in records:
        measurements = record.get("measurements", {})
        count = len(measurements)
        null_count = sum(value is None for value in measurements.values())
        null_fields += null_count
        total_fields += count
        per_joint.append(
            {
                "joint": record.get("joint"),
                "measurement_fields": count,
                "null_fields": null_count,
                "all_measurements_null": null_count == count,
                "status": record.get("measurement_status"),
            }
        )
    checks = {
        "schema_is_minimum_intake": contract.get("schema")
        == "CTRL_R2_ACTUATOR_DYNAMICS_INTAKE_V1",
        "joint_order_exact": [record.get("joint") for record in records] == expected,
        "zero_fill_forbidden": contract.get("zero_fill_forbidden") is True,
        "hardware_model_invalid": contract.get("hardware_model_valid") is False,
        "semantic_requirements_open": contract.get("semantic_requirements_complete") is False,
        "all_measurement_fields_null": total_fields > 0 and null_fields == total_fields,
    }
    return {
        "source_schema": contract.get("schema"),
        "joint_records": per_joint,
        "null_measurement_fields": null_fields,
        "total_measurement_fields": total_fields,
        "checks": checks,
        "minimum_intake_bound": all(checks.values()),
        "hardware_effort_model_valid": False,
        "actuated_8dof_execution_authorized": False,
        "hold": "MEASUREMENT_PENDING__NO_HARDWARE_EFFORT_OR_RATE_ENVELOPE",
    }


def run_flex_ringdown(
    project_root: Path,
    authority: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    pin_data = authority["source_pins"]["solar_r2_rom_data"]
    pin_envelope = authority["source_pins"]["solar_r2_validity_envelope"]
    envelope = load_json_strict(project_root / pin_envelope["path"])
    with np.load(project_root / pin_data["path"], allow_pickle=False) as source:
        arrays = {key: np.asarray(source[key]).copy() for key in source.files}

    cfg = config["flex_ringdown"]
    eta7 = finite_vector(cfg["initial_eta_per_wing"], 7, "initial_eta_per_wing")
    deta7 = finite_vector(cfg["initial_deta_per_wing_s"], 7, "initial_deta_per_wing_s")
    initial = np.concatenate((eta7, eta7, deta7, deta7))
    duration = float(cfg["duration_s"])
    samples = int(cfg["samples"])
    if duration <= 0.0 or samples < 2:
        raise ValueError("FLEX_RINGDOWN_TIME_CONTRACT_INVALID")

    M7 = np.asarray(arrays["Mrom"], dtype=float)
    M14 = block_diag(M7, M7)
    limits = envelope["quantitative_linearity_contract"]["limits"]
    operator_map = {
        "R_w_nodes": "max_abs_transverse_node_displacement_m",
        "R_theta_dofs": "max_abs_bending_slope_rad",
        "R_torsion_nodes": "max_abs_torsion_angle_rad",
        "R_hinge_relative": "max_abs_hinge_relative_rotation_rad",
        "R_tip_w": "max_abs_tip_transverse_deflection_m",
    }
    corners: list[dict[str, Any]] = []
    all_checks: list[bool] = []
    for corner in cfg["corners"]:
        K7 = np.asarray(arrays[f"Krom_{corner}"], dtype=float)
        C7 = np.asarray(arrays[f"Crom_{corner}"], dtype=float)
        K14 = block_diag(K7, K7)
        C14 = block_diag(C7, C7)
        A = np.block(
            [
                [np.zeros((14, 14)), np.eye(14)],
                [-np.linalg.solve(M14, K14), -np.linalg.solve(M14, C14)],
            ]
        )
        times = np.linspace(0.0, duration, samples)
        history = np.column_stack([expm(A * time_s) @ initial for time_s in times])
        final_expm = history[:, -1]

        def rhs(_: float, state: np.ndarray) -> np.ndarray:
            return A @ state

        cross = solve_ivp(
            rhs,
            (0.0, duration),
            initial,
            method="DOP853",
            rtol=float(cfg["cross_rtol"]),
            atol=float(cfg["cross_atol"]),
            max_step=duration / 10.0,
        )
        if not cross.success:
            raise RuntimeError(f"FLEX_CROSS_SOLVER_FAILED:{corner}:{cross.message}")
        solver_eta_cross_relative = _relative_norm(
            final_expm[:14], cross.y[:14, -1]
        )
        solver_deta_cross_relative = _relative_norm(
            final_expm[14:], cross.y[14:, -1]
        )
        eta_history = history[:14]
        deta_history = history[14:]
        energy = 0.5 * np.einsum("it,ij,jt->t", deta_history, M14, deta_history)
        energy += 0.5 * np.einsum("it,ij,jt->t", eta_history, K14, eta_history)
        domain_checks: list[dict[str, Any]] = []
        for wing_index, wing in enumerate(("LEFT", "RIGHT")):
            eta_wing = eta_history[7 * wing_index : 7 * (wing_index + 1), :]
            for operator_name, limit_name in operator_map.items():
                operator = np.asarray(arrays[operator_name], dtype=float)
                value = float(np.max(np.abs(operator @ eta_wing)))
                limit = float(limits[limit_name])
                domain_checks.append(
                    {
                        "wing": wing,
                        "operator": operator_name,
                        "max_abs_response": value,
                        "limit_name": limit_name,
                        "limit": limit,
                        "pass": value <= limit,
                    }
                )
        zero_final = expm(A * duration) @ np.zeros(28)
        K14_symmetry_abs = float(np.max(np.abs(K14 - K14.T)))
        K14_symmetry_relative = K14_symmetry_abs / max(
            float(np.max(np.abs(K14))), 1.0e-30
        )
        corner_checks = {
            "M14_symmetric": float(np.max(np.abs(M14 - M14.T))) <= 1.0e-12,
            "M14_positive_definite": float(np.min(np.linalg.eigvalsh(M14))) > 0.0,
            "K14_symmetric_within_source_relative_tolerance": K14_symmetry_relative
            <= float(config["thresholds"]["flex_matrix_symmetry_relative_max"]),
            "K14_positive_definite": float(np.min(np.linalg.eigvalsh(K14))) > 0.0,
            "C14_positive_semidefinite": float(np.min(np.linalg.eigvalsh(C14))) >= -1.0e-12,
            "free_ringdown_energy_nonincreasing": float(energy[-1])
            <= float(energy[0]) + float(config["thresholds"]["flex_energy_increase_tolerance_J"]),
            "expm_vs_DOP853_eta": solver_eta_cross_relative
            <= float(config["thresholds"]["flex_solver_eta_cross_relative_max"]),
            "expm_vs_DOP853_deta": solver_deta_cross_relative
            <= float(config["thresholds"]["flex_solver_deta_cross_relative_max"]),
            "linearity_domain_respected": all(item["pass"] for item in domain_checks),
            "flex_off_zero_state_exact": bool(np.array_equal(zero_final, np.zeros(28))),
        }
        all_checks.extend(corner_checks.values())
        corners.append(
            {
                "corner": corner,
                "M14_min_eigenvalue": float(np.min(np.linalg.eigvalsh(M14))),
                "K14_min_eigenvalue": float(np.min(np.linalg.eigvalsh(K14))),
                "K14_symmetry_max_abs": K14_symmetry_abs,
                "K14_symmetry_relative": K14_symmetry_relative,
                "C14_min_eigenvalue": float(np.min(np.linalg.eigvalsh(C14))),
                "initial_energy_J": float(energy[0]),
                "final_energy_J": float(energy[-1]),
                "relative_energy_change": float(
                    (energy[-1] - energy[0]) / max(abs(energy[0]), 1.0e-30)
                ),
                "expm_vs_DOP853_eta_relative": solver_eta_cross_relative,
                "expm_vs_DOP853_deta_relative": solver_deta_cross_relative,
                "DOP853_nfev": int(cross.nfev),
                "domain_checks": domain_checks,
                "checks": corner_checks,
                "pass": all(corner_checks.values()),
            }
        )
    return {
        "schema": "R2_DUAL_WING_14MODE_RINGDOWN_DIAGNOSTIC_V1",
        "scope": "DECOUPLED_FREE_RINGDOWN_AND_DOMAIN_DIAGNOSTIC_ONLY",
        "excitation_authority": cfg["excitation_authority"],
        "wing_order": ["LEFT", "RIGHT"],
        "modes_per_wing": 7,
        "combined_modes": 14,
        "corners": corners,
        "arm_to_flex_time_domain_coupling_evaluated": False,
        "full_coupled_rigid_limit_evaluated": False,
        "E23_pass_inherited": False,
        "pass_for_bounded_component_diagnostic": all(all_checks),
        "dynamics_engineering_credit": False,
    }


def run_constrained_dynamics_once(
    project_root: Path,
    authority: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    backend = load_backend(project_root)
    urdf = parse_urdf_joint_contract(project_root, authority)
    cfg = config["locked_diagnostic"]
    thresholds = config["thresholds"]
    q6 = finite_vector(cfg["q6_rad"], 6, "q6")
    qP = finite_vector(cfg["qP_star_m"], 2, "qP_star")
    dq6 = finite_vector(cfg["dq6_rad_s"], 6, "dq6")
    dqP = finite_vector(cfg["dqP_m_s"], 2, "dqP")
    if np.any(dqP != 0.0):
        raise ContractError("LOCKED_PRISMATIC_RATE_MUST_BE_EXACT_ZERO")
    limits = np.asarray(urdf["limits_mixed_rad_m"], dtype=float)
    q8 = np.concatenate((q6, qP))
    if np.any(q8 < limits[:, 0]) or np.any(q8 > limits[:, 1]):
        raise ContractError("DIAGNOSTIC_STATE_OUTSIDE_HASH_FIXED_URDF_LIMITS")

    model = ReducedR2Model(backend=backend, qP_star_m=qP)
    locked = model.locked_acceleration(
        q6, dq6, cfg["tau6_diagnostic_Nm"], cfg["tauP_diagnostic_N"]
    )
    mass = locked["mass"]
    mass_symmetry_delta = mass - mass.T
    mass_symmetry_RR_kg_m2 = float(
        np.max(np.abs(mass_symmetry_delta[:6, :6]))
    )
    mass_symmetry_RP_kg_m = float(
        max(
            np.max(np.abs(mass_symmetry_delta[:6, 6:])),
            np.max(np.abs(mass_symmetry_delta[6:, :6])),
        )
    )
    mass_symmetry_PP_kg = float(
        np.max(np.abs(mass_symmetry_delta[6:, 6:]))
    )
    raw_unscaled_mass_eigenvalues = np.linalg.eigvalsh(mass)

    # Counterexample: the same tauP=0 without a constraint generally accelerates 2P.
    actuated_cfg = config["actuated_8dof_diagnostic"]
    actuated_tau8 = finite_vector(
        actuated_cfg["tau8_mixed_Nm_N"], 8, "actuated_tau8"
    )
    if np.any(actuated_tau8[6:] != 0.0):
        raise ContractError("TAUP_ZERO_FALSIFIER_REQUIRES_EXACT_ZERO_TAUP")
    free_tauP_zero = model.actuated_acceleration(
        q8, locked["dq8"], actuated_tau8
    )

    locked_base = model.base_twist_kinematics(
        q8, locked["dq8"], locked["kkt_acceleration"]
    )
    eliminated_base = model.base_twist_kinematics(
        q8, locked["dq8"], locked["eliminated_acceleration"]
    )
    locked_base_cross_vector = (
        locked_base["base_twist_rate_body_coordinates"]
        - eliminated_base["base_twist_rate_body_coordinates"]
    )
    locked_base_linear_cross_m_s2 = float(
        np.max(np.abs(locked_base_cross_vector[:3]))
    )
    locked_base_angular_cross_rad_s2 = float(
        np.max(np.abs(locked_base_cross_vector[3:]))
    )
    free_base = model.base_twist_kinematics(
        q8, locked["dq8"], free_tauP_zero["acceleration"]
    )

    # Applying the solved lock reaction as actuator effort must recover KKT ddq.
    tau_equivalent = locked["tau"].copy()
    tau_equivalent[6:] += locked["kkt_reaction_N"]
    actuated_equivalent = model.actuated_acceleration(q8, locked["dq8"], tau_equivalent)
    mode_cross_vector = (
        actuated_equivalent["acceleration"] - locked["kkt_acceleration"]
    )
    mode_cross_R_rad_s2 = float(np.max(np.abs(mode_cross_vector[:6])))
    mode_cross_P_m_s2 = float(np.max(np.abs(mode_cross_vector[6:])))

    # Unforced short-time locked integration for energy and momentum diagnostics.
    time_cfg = config["locked_short_time"]
    duration = float(time_cfg["duration_s"])
    step = float(time_cfg["fixed_step_s"])
    steps_float = duration / step
    if abs(steps_float - round(steps_float)) > 1.0e-12:
        raise ContractError("LOCKED_INTEGRATION_DURATION_NOT_INTEGER_STEPS")
    steps = int(round(steps_float))
    initial12 = np.concatenate((q6, dq6))
    energy_initial = model.kinetic_energy(q6, dq6)
    final_rk4, primary_history = rk4_integrate(
        model.locked_rhs, initial12, step, steps
    )
    trajectory_energy = np.asarray(
        [model.kinetic_energy(state[:6], state[6:]) for state in primary_history]
    )
    energy_final = float(trajectory_energy[-1])
    energy_relative_drift = float(
        np.max(np.abs(trajectory_energy - energy_initial))
        / max(abs(energy_initial), 1.0e-30)
    )
    cross = solve_ivp(
        lambda _time, state: model.locked_rhs(state),
        (0.0, duration),
        initial12,
        method="DOP853",
        rtol=float(time_cfg["cross_rtol"]),
        atol=float(time_cfg["cross_atol"]),
        max_step=float(time_cfg["cross_max_step_s"]),
    )
    if not cross.success:
        raise RuntimeError(f"LOCKED_CROSS_SOLVER_FAILED:{cross.message}")
    cross_final = cross.y[:, -1]
    time_cross_qR_relative = _relative_norm(final_rk4[:6], cross_final[:6])
    time_cross_dqR_relative = _relative_norm(final_rk4[6:], cross_final[6:])
    trajectory_mass_symmetry_RR: list[float] = []
    trajectory_mass_symmetry_RP: list[float] = []
    trajectory_mass_symmetry_PP: list[float] = []
    trajectory_raw_unscaled_mass_min_eigenvalue: list[float] = []
    trajectory_constraint_residual: list[float] = []
    trajectory_equilibrium_residual_R_Nm: list[float] = []
    trajectory_equilibrium_residual_P_N: list[float] = []
    trajectory_reaction_norm: list[float] = []
    trajectory_linear_momentum: list[float] = []
    trajectory_angular_momentum: list[float] = []
    for state in primary_history:
        state_q8, state_dq8 = model.locked_state(state[:6], state[6:])
        state_mass = model.mass(state_q8)
        state_symmetry = state_mass - state_mass.T
        trajectory_mass_symmetry_RR.append(
            float(np.max(np.abs(state_symmetry[:6, :6])))
        )
        trajectory_mass_symmetry_RP.append(
            float(
                max(
                    np.max(np.abs(state_symmetry[:6, 6:])),
                    np.max(np.abs(state_symmetry[6:, :6])),
                )
            )
        )
        trajectory_mass_symmetry_PP.append(
            float(np.max(np.abs(state_symmetry[6:, 6:])))
        )
        trajectory_raw_unscaled_mass_min_eigenvalue.append(
            float(np.min(np.linalg.eigvalsh(state_mass)))
        )
        state_lock = model.locked_acceleration(
            state[:6], state[6:], np.zeros(6), np.zeros(2)
        )
        trajectory_constraint_residual.append(
            float(np.max(np.abs(state_lock["constraint_acceleration"])))
        )
        trajectory_equilibrium_residual_R_Nm.append(
            float(np.max(np.abs(state_lock["kkt_equilibrium_residual"][:6])))
        )
        trajectory_equilibrium_residual_P_N.append(
            float(np.max(np.abs(state_lock["kkt_equilibrium_residual"][6:])))
        )
        trajectory_reaction_norm.append(
            float(np.linalg.norm(state_lock["kkt_reaction_N"]))
        )
        state_base_twist = backend.mechanical_connection(state_q8) @ state_dq8
        state_momentum = backend.tree.momentum(
            state_q8, state_base_twist, state_dq8
        )
        trajectory_linear_momentum.append(
            float(np.linalg.norm(state_momentum.linear_root_kg_m_s))
        )
        trajectory_angular_momentum.append(
            float(np.linalg.norm(state_momentum.angular_about_root_kg_m2_s))
        )
    final_q8, final_dq8 = model.locked_state(final_rk4[:6], final_rk4[6:])
    final_connection = backend.mechanical_connection(final_q8)
    final_base_twist = final_connection @ final_dq8
    final_momentum = backend.tree.momentum(final_q8, final_base_twist, final_dq8)
    linear_residual = max(trajectory_linear_momentum)
    angular_residual = max(trajectory_angular_momentum)
    final_lock = model.locked_acceleration(
        final_rk4[:6], final_rk4[6:], np.zeros(6), np.zeros(2)
    )

    # Arm-stop degeneration: no velocity, effort, flex forcing, or base reaction.
    arm_stop = model.locked_acceleration(q6, np.zeros(6), np.zeros(6), np.zeros(2))
    stopped_q8, stopped_dq8 = model.locked_state(q6, np.zeros(6))
    stopped_base_twist = backend.mechanical_connection(stopped_q8) @ stopped_dq8

    actuator = audit_actuator_contract(project_root, authority)
    checks = {
        "backend_dof_8": backend.dof == 8,
        "backend_total_mass_current_r2": abs(
            float(backend.tree.total_mass_kg) - 31.022864807342987
        )
        <= 1.0e-12,
        "joint_order_exact": list(backend.tree.movable_joint_names)
        == urdf["joint_order"],
        "joint_types_6R2P": urdf["joint_types"]
        == ["revolute"] * 6 + ["prismatic"] * 2,
        "diagnostic_q_inside_urdf_limits": True,
        "heterogeneous_coordinate_metric_bound": False,
        "mass_symmetric_RR": mass_symmetry_RR_kg_m2
        <= float(thresholds["mass_symmetry_RR_max_abs_kg_m2"]),
        "mass_symmetric_RP": mass_symmetry_RP_kg_m
        <= float(thresholds["mass_symmetry_RP_max_abs_kg_m"]),
        "mass_symmetric_PP": mass_symmetry_PP_kg
        <= float(thresholds["mass_symmetry_PP_max_abs_kg"]),
        "mass_symmetric_RR_over_short_trajectory": max(
            trajectory_mass_symmetry_RR
        )
        <= float(thresholds["mass_symmetry_RR_max_abs_kg_m2"]),
        "mass_symmetric_RP_over_short_trajectory": max(
            trajectory_mass_symmetry_RP
        )
        <= float(thresholds["mass_symmetry_RP_max_abs_kg_m"]),
        "mass_symmetric_PP_over_short_trajectory": max(
            trajectory_mass_symmetry_PP
        )
        <= float(thresholds["mass_symmetry_PP_max_abs_kg"]),
        "kkt_equilibrium_revolute": float(
            np.max(np.abs(locked["kkt_equilibrium_residual"][:6]))
        )
        <= float(thresholds["kkt_equilibrium_R_max_abs_Nm"]),
        "kkt_equilibrium_prismatic": float(
            np.max(np.abs(locked["kkt_equilibrium_residual"][6:]))
        )
        <= float(thresholds["kkt_equilibrium_P_max_abs_N"]),
        "locked_ddqP_exact_within_tolerance": float(
            np.max(np.abs(locked["constraint_acceleration"]))
        )
        <= float(thresholds["constraint_acceleration_max_abs_m_s2"]),
        "KKT_vs_coordinate_elimination_revolute_acceleration": locked[
            "acceleration_cross_revolute_max_abs_rad_s2"
        ]
        <= float(thresholds["coordinate_cross_R_max_abs_rad_s2"]),
        "KKT_vs_coordinate_elimination_prismatic_acceleration": locked[
            "acceleration_cross_prismatic_max_abs_m_s2"
        ]
        <= float(thresholds["coordinate_cross_P_max_abs_m_s2"]),
        "KKT_vs_coordinate_elimination_reaction": locked[
            "reaction_cross_max_abs_N"
        ]
        <= float(thresholds["reaction_cross_max_abs_N"]),
        "constraint_reaction_explicit_and_nonzero": float(
            np.linalg.norm(locked["kkt_reaction_N"])
        )
        >= float(thresholds["reaction_nonzero_min_N"]),
        "tauP_zero_not_misclassified_as_lock": float(
            np.linalg.norm(free_tauP_zero["acceleration"][6:])
        )
        >= float(thresholds["tauP_zero_free_acceleration_min_m_s2"]),
        "reaction_as_effort_recovers_locked_revolute_mode": mode_cross_R_rad_s2
        <= float(thresholds["coordinate_cross_R_max_abs_rad_s2"]),
        "reaction_as_effort_recovers_locked_prismatic_mode": mode_cross_P_m_s2
        <= float(thresholds["coordinate_cross_P_max_abs_m_s2"]),
        "base_acceleration_finite_and_coordinate_crossed": bool(
            np.all(np.isfinite(locked_base["base_twist_rate_body_coordinates"]))
        )
        and locked_base_linear_cross_m_s2
        <= float(thresholds["base_linear_cross_max_abs_m_s2"])
        and locked_base_angular_cross_rad_s2
        <= float(thresholds["base_angular_cross_max_abs_rad_s2"]),
        "locked_short_time_energy": energy_relative_drift
        <= float(thresholds["energy_relative_drift_max"]),
        "RK4_vs_DOP853_qR": time_cross_qR_relative
        <= float(thresholds["time_solver_qR_cross_relative_max"]),
        "RK4_vs_DOP853_dqR": time_cross_dqR_relative
        <= float(thresholds["time_solver_dqR_cross_relative_max"]),
        "mechanical_connection_linear_zero_identity": linear_residual
        <= float(thresholds["linear_momentum_residual_max_Ns"]),
        "mechanical_connection_angular_zero_identity": angular_residual
        <= float(thresholds["angular_momentum_residual_max_Nms"]),
        "independent_full_state_momentum_conservation": False,
        "final_locked_ddqP_bounded": float(
            np.max(np.abs(final_lock["constraint_acceleration"]))
        )
        <= float(thresholds["constraint_acceleration_max_abs_m_s2"]),
        "locked_constraint_bounded_over_short_trajectory": max(
            trajectory_constraint_residual
        )
        <= float(thresholds["constraint_acceleration_max_abs_m_s2"]),
        "KKT_equilibrium_revolute_bounded_over_short_trajectory": max(
            trajectory_equilibrium_residual_R_Nm
        )
        <= float(thresholds["kkt_equilibrium_R_max_abs_Nm"]),
        "KKT_equilibrium_prismatic_bounded_over_short_trajectory": max(
            trajectory_equilibrium_residual_P_N
        )
        <= float(thresholds["kkt_equilibrium_P_max_abs_N"]),
        "arm_stop_revolute_acceleration_zero": float(
            np.max(np.abs(arm_stop["kkt_acceleration"][:6]))
        )
        <= float(thresholds["arm_stop_R_acceleration_max_abs_rad_s2"]),
        "arm_stop_prismatic_acceleration_zero": float(
            np.max(np.abs(arm_stop["kkt_acceleration"][6:]))
        )
        <= float(thresholds["arm_stop_P_acceleration_max_abs_m_s2"]),
        "arm_stop_constraint_reaction_zero": float(
            np.max(np.abs(arm_stop["kkt_reaction_N"]))
        )
        <= float(thresholds["arm_stop_reaction_max_abs_N"]),
        "arm_stop_base_linear_twist_zero": float(
            np.max(np.abs(stopped_base_twist[:3]))
        )
        <= float(thresholds["arm_stop_base_linear_max_abs_m_s"]),
        "arm_stop_base_angular_twist_zero": float(
            np.max(np.abs(stopped_base_twist[3:]))
        )
        <= float(thresholds["arm_stop_base_angular_max_abs_rad_s"]),
        "actuator_nulls_preserved": actuator["minimum_intake_bound"]
        and actuator["hardware_effort_model_valid"] is False,
    }
    return jsonable(
        {
            "schema": "R2_8DOF_CONSTRAINED_DYNAMICS_DIAGNOSTIC_INSTANCE_V1",
            "scope": "CURRENT_R2_ZERO_MOMENTUM_RIGID_8DOF_WITH_LOCKED_2P_CANDIDATE",
            "model": {
                "links": backend.tree.link_count,
                "joints": backend.tree.joint_count,
                "movable_dof": backend.dof,
                "total_mass_kg": backend.tree.total_mass_kg,
                "root_link": backend.tree.root_link,
                "joint_order": list(backend.tree.movable_joint_names),
                "joint_types": urdf["joint_types"],
                "coordinate_units": authority["coordinate_contract"]["coordinate_units"],
                "effort_units": authority["coordinate_contract"]["effort_units"],
                "urdf_joint_limits_mixed_rad_m": urdf[
                    "limits_mixed_rad_m"
                ],
            },
            "locked_2P": {
                "equation": "M*ddq+b=tau+J^T*reaction; J*ddq=0",
                "qP_star_m": qP,
                "dqP_m_s": dqP,
                "tauP_diagnostic_N": locked["tau"][6:],
                "reaction_N": locked["kkt_reaction_N"],
                "reaction_norm_N": float(np.linalg.norm(locked["kkt_reaction_N"])),
                "ddq8_mixed_rad_s2_m_s2": locked["kkt_acceleration"],
                "ddqP_m_s2": locked["kkt_acceleration"][6:],
                "equilibrium_residual_revolute_max_abs_Nm": float(
                    np.max(np.abs(locked["kkt_equilibrium_residual"][:6]))
                ),
                "equilibrium_residual_prismatic_max_abs_N": float(
                    np.max(np.abs(locked["kkt_equilibrium_residual"][6:]))
                ),
                "constraint_acceleration_max_abs_m_s2": float(
                    np.max(np.abs(locked["constraint_acceleration"]))
                ),
                "raw_unscaled_KKT_condition_number_no_credit": locked[
                    "raw_unscaled_kkt_condition_number_no_credit"
                ],
                "coordinate_elimination_cross": {
                    "revolute_acceleration_max_abs_rad_s2": locked[
                        "acceleration_cross_revolute_max_abs_rad_s2"
                    ],
                    "prismatic_acceleration_max_abs_m_s2": locked[
                        "acceleration_cross_prismatic_max_abs_m_s2"
                    ],
                    "reaction_max_abs_N": locked["reaction_cross_max_abs_N"],
                },
                "base_kinematics": {
                    "twist_order": authority["coordinate_contract"][
                        "base_twist_order"
                    ],
                    "base_twist_body_mixed_m_s_rad_s": locked_base[
                        "base_twist_body"
                    ],
                    "base_twist_rate_body_coordinates_mixed_m_s2_rad_s2": locked_base[
                        "base_twist_rate_body_coordinates"
                    ],
                    "linear_acceleration_body_coordinates_m_s2": locked_base[
                        "base_twist_rate_body_coordinates"
                    ][:3],
                    "angular_acceleration_body_coordinates_rad_s2": locked_base[
                        "base_twist_rate_body_coordinates"
                    ][3:],
                    "coordinate_elimination_linear_cross_max_abs_m_s2": locked_base_linear_cross_m_s2,
                    "coordinate_elimination_angular_cross_max_abs_rad_s2": locked_base_angular_cross_rad_s2,
                    "semantic_note": "BODY_COORDINATE_TIME_DERIVATIVE_OF_BASE_TWIST__NOT_AN_INERTIAL_POINT_ACCELERATION",
                },
                "tauP_zero_is_lock": False,
            },
            "actuated_8DOF_boundary": {
                "diagnostic_effort_authority": cfg["diagnostic_effort_authority"],
                "tau8_mixed_Nm_N": actuated_tau8,
                "qP_stroke_limits_m": np.asarray(
                    urdf["limits_mixed_rad_m"], dtype=float
                )[6:, :],
                "same_state_tauP_zero_free_ddqP_m_s2": free_tauP_zero[
                    "acceleration"
                ][6:],
                "same_state_tauP_zero_free_ddqP_norm_m_s2": float(
                    np.linalg.norm(free_tauP_zero["acceleration"][6:])
                ),
                "reaction_as_equivalent_effort_revolute_cross_max_abs_rad_s2": mode_cross_R_rad_s2,
                "reaction_as_equivalent_effort_prismatic_cross_max_abs_m_s2": mode_cross_P_m_s2,
                "base_twist_rate_body_coordinates_mixed_m_s2_rad_s2": free_base[
                    "base_twist_rate_body_coordinates"
                ],
                "actuator_contract": actuator,
                "hardware_effort_envelope_enforced": False,
                "execution_authorized": False,
            },
            "mass_matrix": {
                "shape": list(mass.shape),
                "coordinate_metric_status": "UNBOUND",
                "credited_spectrum_or_condition_available": False,
                "symmetry_RR_max_abs_kg_m2": mass_symmetry_RR_kg_m2,
                "symmetry_RP_max_abs_kg_m": mass_symmetry_RP_kg_m,
                "symmetry_PP_max_abs_kg": mass_symmetry_PP_kg,
                "short_trajectory_symmetry_RR_max_abs_kg_m2": max(
                    trajectory_mass_symmetry_RR
                ),
                "short_trajectory_symmetry_RP_max_abs_kg_m": max(
                    trajectory_mass_symmetry_RP
                ),
                "short_trajectory_symmetry_PP_max_abs_kg": max(
                    trajectory_mass_symmetry_PP
                ),
                "raw_unscaled_min_eigenvalue_no_credit": float(
                    np.min(raw_unscaled_mass_eigenvalues)
                ),
                "raw_unscaled_max_eigenvalue_no_credit": float(
                    np.max(raw_unscaled_mass_eigenvalues)
                ),
                "raw_unscaled_condition_number_no_credit": float(
                    np.linalg.cond(mass)
                ),
                "short_trajectory_raw_unscaled_min_eigenvalue_no_credit": min(
                    trajectory_raw_unscaled_mass_min_eigenvalue
                ),
                "unit_reparameterization_invariant": False,
            },
            "locked_short_time_integration": {
                "duration_s": duration,
                "fixed_step_s": step,
                "steps": steps,
                "primary_solver": time_cfg["primary_solver"],
                "cross_solver": time_cfg["cross_solver"],
                "initial_energy_J": energy_initial,
                "final_energy_J": energy_final,
                "energy_relative_drift": energy_relative_drift,
                "energy_relative_drift_definition": "MAX_ABS_OVER_ALL_PRIMARY_RK4_SAMPLES",
                "solver_cross_final_qR_relative": time_cross_qR_relative,
                "solver_cross_final_dqR_relative": time_cross_dqR_relative,
                "DOP853_nfev": int(cross.nfev),
                "final_q6_rad": final_rk4[:6],
                "final_dq6_rad_s": final_rk4[6:],
                "final_qP_m": final_q8[6:],
                "final_dqP_m_s": final_dq8[6:],
                "final_constraint_reaction_N": final_lock["kkt_reaction_N"],
                "trajectory_constraint_acceleration_max_abs_m_s2": max(
                    trajectory_constraint_residual
                ),
                "trajectory_KKT_equilibrium_revolute_max_abs_Nm": max(
                    trajectory_equilibrium_residual_R_Nm
                ),
                "trajectory_KKT_equilibrium_prismatic_max_abs_N": max(
                    trajectory_equilibrium_residual_P_N
                ),
                "trajectory_constraint_reaction_norm_max_N": max(
                    trajectory_reaction_norm
                ),
            },
            "zero_momentum_audit": {
                "base_twist_body_mixed_m_s_rad_s": final_base_twist,
                "linear_momentum_residual_root_Ns": final_momentum.linear_root_kg_m_s,
                "linear_momentum_residual_norm_Ns": linear_residual,
                "angular_momentum_residual_about_root_Nms": final_momentum.angular_about_root_kg_m2_s,
                "angular_momentum_residual_norm_Nms": angular_residual,
                "residual_norm_definition": "MAX_OVER_ALL_PRIMARY_RK4_SAMPLES",
                "linear_and_angular_not_mixed": True,
                "scope": "ZERO_TOTAL_MOMENTUM_MECHANICAL_CONNECTION_IDENTITY_DIAGNOSTIC",
                "base_pose_integrated": False,
                "nonzero_total_momentum_case_evaluated": False,
                "independent_full_state_conservation_proven": False,
                "credit": "ALGEBRAIC_IDENTITY_ONLY__NOT_TIME_DOMAIN_CONSERVATION",
            },
            "degeneration_checks": {
                "arm_stop": {
                    "revolute_acceleration_max_abs_rad_s2": float(
                        np.max(np.abs(arm_stop["kkt_acceleration"][:6]))
                    ),
                    "prismatic_acceleration_max_abs_m_s2": float(
                        np.max(np.abs(arm_stop["kkt_acceleration"][6:]))
                    ),
                    "reaction_max_abs_N": float(
                        np.max(np.abs(arm_stop["kkt_reaction_N"]))
                    ),
                    "base_linear_twist_max_abs_m_s": float(
                        np.max(np.abs(stopped_base_twist[:3]))
                    ),
                    "base_angular_twist_max_abs_rad_s": float(
                        np.max(np.abs(stopped_base_twist[3:]))
                    ),
                },
                "locked_to_actuated_reaction_equivalence_revolute_max_abs_rad_s2": mode_cross_R_rad_s2,
                "locked_to_actuated_reaction_equivalence_prismatic_max_abs_m_s2": mode_cross_P_m_s2,
                "rigid_flex_decoupled_zero_state": "EVALUATED_IN_14MODE_COMPONENT_DIAGNOSTIC",
                "full_arm_flex_coupled_rigid_limit": "NOT_EVALUATED_HOLD",
            },
            "execution_guards": config["execution_guards"],
            "checks": checks,
            "candidate_checks_pass": all(checks.values()),
            "technical_dynamics_complete": False,
            "next_stage_authorized": False,
            "release_credit": False,
        }
    )


def run_all_diagnostics(
    project_root: Path,
    authority: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    constrained_first = run_constrained_dynamics_once(project_root, authority, config)
    constrained_replay = run_constrained_dynamics_once(project_root, authority, config)
    flex_first = run_flex_ringdown(project_root, authority, config)
    flex_replay = run_flex_ringdown(project_root, authority, config)
    constrained_first_hash = canonical_sha256(constrained_first)
    constrained_replay_hash = canonical_sha256(constrained_replay)
    flex_first_hash = canonical_sha256(flex_first)
    flex_replay_hash = canonical_sha256(flex_replay)
    return {
        "schema": "R2_DYNAMICS_ENGINEERING_DIAGNOSTICS_V1",
        "constrained": constrained_first,
        "flex": flex_first,
        "determinism": {
            "constrained_first_sha256": constrained_first_hash,
            "constrained_replay_sha256": constrained_replay_hash,
            "constrained_exact_canonical_match": constrained_first_hash
            == constrained_replay_hash,
            "flex_first_sha256": flex_first_hash,
            "flex_replay_sha256": flex_replay_hash,
            "flex_exact_canonical_match": flex_first_hash == flex_replay_hash,
        },
        "execution_guards": config["execution_guards"],
        "candidate_diagnostics_pass": bool(
            constrained_first["candidate_checks_pass"]
            and flex_first["pass_for_bounded_component_diagnostic"]
            and constrained_first_hash == constrained_replay_hash
            and flex_first_hash == flex_replay_hash
        ),
        "technical_dynamics_complete": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }


__all__ = [
    "AUTHORITY_PATH",
    "CONFIG_PATH",
    "ContractError",
    "ReducedR2Model",
    "canonical_sha256",
    "file_sha256",
    "load_contracts",
    "load_json_strict",
    "run_all_diagnostics",
    "run_constrained_dynamics_once",
    "run_flex_ringdown",
    "solve_locked_kkt",
    "validate_source_pins",
]
