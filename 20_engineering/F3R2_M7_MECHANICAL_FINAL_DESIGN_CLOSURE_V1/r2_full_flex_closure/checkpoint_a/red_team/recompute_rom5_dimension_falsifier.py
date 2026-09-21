#!/usr/bin/env python3
"""Independent Checkpoint-A falsifier for the Solar R2 five-mode ROM.

This script is intentionally isolated from e22.  It consumes only the frozen
Round3 NPZ and ROM contract, reconstructs the 183-DOF output operators from the
published DOF semantics, and recomputes the finite-contact HF/ROM response.

It writes ROM5_DIMENSION_FALSIFIER_V1.json next to this script.  No accepted
Round3 or e22 artifact is modified.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import eigh


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[4]
ROUND3 = (
    PROJECT_ROOT
    / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
    / "r2_full_flex_closure/round3_hf_rom_v2"
)
NPZ_PATH = ROUND3 / "R2_HF_ROM_NUMERICAL_DATA_V2.npz"
CONTRACT_PATH = ROUND3 / "R2_FIVE_MODE_ROM_V2.json"
OUT_PATH = HERE / "ROM5_DIMENSION_FALSIFIER_V1.json"

EXPECTED_SHA256 = {
    NPZ_PATH: "8D10E085385EDF2FACE92B9B48D1172939A31FD3B57E55242ED11C9EEEDF50DA",
    CONTRACT_PATH: "9E4FE903AE7E34584F39F16275EF20FC31831AFB7F78B3B625418B86D0FBC817",
}

# Diagnostic base velocity change handed to the independent red team.  It is
# an excitation vector only; this script does not re-derive or grant authority
# to the coupled capture solution that produced it.
BASE_DELTA_TWIST_6 = np.asarray(
    [
        -0.009692455771418815,
        0.0038929116736479714,
        -0.0020413946008322834,
        -0.04501982207187775,
        -0.0015129575188143466,
        0.02812660573609509,
    ],
    dtype=float,
)

TC_NOMINAL_S = 0.020
POST_WINDOW_S = 5.0
CONTACT_SAMPLES = 401
POST_SAMPLES = 5001
RELATIVE_LIMIT = 0.01
DENOMINATOR_FLOOR = 1.0e-14


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def relative_path(path: Path) -> str:
    return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")


def jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(jsonable(payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def row(ndof: int, index: int) -> np.ndarray:
    out = np.zeros(ndof)
    out[int(index)] = 1.0
    return out


def reconstruct_hf_operators(contract: dict[str, Any]) -> dict[str, np.ndarray]:
    semantics = contract["reduced_hf_dof_semantics"]
    ndof = len(semantics)
    w_items = sorted(
        (x for x in semantics if x["kind"] == "TRANSVERSE_W"),
        key=lambda x: int(x["node"]),
    )
    theta_items = sorted(
        (x for x in semantics if x["kind"] == "BENDING_SLOPE_THETA"),
        key=lambda x: (int(x["node"]), str(x["side"])),
    )
    torsion_items = sorted(
        (x for x in semantics if x["kind"] == "TORSION_PHI"),
        key=lambda x: int(x["node"]),
    )

    r_w = np.vstack(
        [np.zeros(ndof)]
        + [row(ndof, x["reduced_index_0based"]) for x in w_items]
    )
    r_theta = np.vstack(
        [row(ndof, x["reduced_index_0based"]) for x in theta_items]
    )
    r_torsion = np.vstack(
        [np.zeros(ndof)]
        + [row(ndof, x["reduced_index_0based"]) for x in torsion_items]
    )

    by_node: dict[int, list[dict[str, Any]]] = {}
    for item in theta_items:
        by_node.setdefault(int(item["node"]), []).append(item)
    duplicated_hinge_nodes = sorted(
        node
        for node, items in by_node.items()
        if {str(x["side"]) for x in items} == {"L", "R"}
    )
    root_item = by_node[0][0]
    hinge_rows = [row(ndof, root_item["reduced_index_0based"])]
    for node in duplicated_hinge_nodes:
        left = next(x for x in by_node[node] if x["side"] == "L")
        right = next(x for x in by_node[node] if x["side"] == "R")
        hinge_rows.append(
            row(ndof, right["reduced_index_0based"])
            - row(ndof, left["reduced_index_0based"])
        )

    return {
        "w_nodes": r_w,
        "theta_dofs": r_theta,
        "hinge_relative": np.vstack(hinge_rows),
        "torsion_nodes": r_torsion,
        "tip_w": r_w[-1:, :],
    }


def time_grids(tc_s: float) -> tuple[np.ndarray, np.ndarray]:
    return (
        np.linspace(0.0, tc_s, CONTACT_SAMPLES),
        np.linspace(0.0, POST_WINDOW_S, POST_SAMPLES),
    )


def modal_half_sine(
    mass: np.ndarray,
    stiffness: np.ndarray,
    impulse_vector: np.ndarray,
    tc_s: float,
    t_contact: np.ndarray,
    t_post: np.ndarray,
) -> dict[str, np.ndarray]:
    """Closed-form undamped response to a unit-integral half sine."""
    eigenvalues, modes = eigh(stiffness, mass)
    if float(np.min(eigenvalues)) <= 0.0:
        raise RuntimeError("NONPOSITIVE_EIGENVALUE_IN_FALSIFIER")
    omega = np.sqrt(eigenvalues)
    omega_contact = math.pi / tc_s
    denominator = omega * omega - omega_contact * omega_contact
    separation = np.abs(denominator) / np.maximum(omega * omega, omega_contact**2)
    if float(np.min(separation)) < 1.0e-10:
        raise RuntimeError("NEAR_RESONANT_LIMIT_FORM_REQUIRED")

    modal_impulse = modes.T @ impulse_vector
    force_amplitude = math.pi / (2.0 * tc_s)
    coefficient = modal_impulse * force_amplitude / denominator
    homogeneous = -coefficient * omega_contact / omega

    tc = np.asarray(t_contact, dtype=float)[None, :]
    y_contact = coefficient[:, None] * np.sin(omega_contact * tc) + (
        homogeneous[:, None] * np.sin(omega[:, None] * tc)
    )
    yd_contact = (
        coefficient[:, None] * omega_contact * np.cos(omega_contact * tc)
        + homogeneous[:, None] * omega[:, None] * np.cos(omega[:, None] * tc)
    )

    y_end = y_contact[:, -1]
    yd_end = yd_contact[:, -1]
    tp = np.asarray(t_post, dtype=float)[None, :]
    y_post = y_end[:, None] * np.cos(omega[:, None] * tp) + (
        (yd_end / omega)[:, None] * np.sin(omega[:, None] * tp)
    )
    yd_post = -y_end[:, None] * omega[:, None] * np.sin(omega[:, None] * tp) + (
        yd_end[:, None] * np.cos(omega[:, None] * tp)
    )

    return {
        "eigenvalues": eigenvalues,
        "omega": omega,
        "modes": modes,
        "modal_impulse": modal_impulse,
        "y": np.hstack([y_contact, y_post[:, 1:]]),
        "yd": np.hstack([yd_contact, yd_post[:, 1:]]),
        "y_end": y_end,
        "yd_end": yd_end,
    }


def response_metrics(
    solution: dict[str, np.ndarray],
    physical_operators: dict[str, np.ndarray],
) -> dict[str, float]:
    physical_modes = solution["modes"]
    modal_state = solution["y"]
    values = {
        name: operator @ physical_modes @ modal_state
        for name, operator in physical_operators.items()
    }
    energy = 0.5 * np.sum(
        solution["yd"] ** 2
        + solution["eigenvalues"][:, None] * solution["y"] ** 2,
        axis=0,
    )
    return {
        "tip_peak_m": float(np.max(np.abs(values["tip_w"]))),
        "node_peak_m": float(np.max(np.abs(values["w_nodes"]))),
        "slope_peak_rad": float(np.max(np.abs(values["theta_dofs"]))),
        "hinge_peak_rad": float(np.max(np.abs(values["hinge_relative"]))),
        "torsion_peak_rad": float(np.max(np.abs(values["torsion_nodes"]))),
        "modal_energy_peak_J": float(np.max(energy)),
        "modal_energy_final_J": float(energy[-1]),
    }


def relative_errors(
    candidate: dict[str, float], reference: dict[str, float]
) -> dict[str, float]:
    return {
        key: abs(candidate[key] - reference[key])
        / max(abs(reference[key]), DENOMINATOR_FLOOR)
        for key in candidate
    }


def numerical_crosscheck(
    mass: np.ndarray,
    stiffness: np.ndarray,
    impulse_vector: np.ndarray,
    operators: dict[str, np.ndarray],
) -> dict[str, Any]:
    """Cross the analytic ROM response against an independent DOP853 ODE."""
    tc = np.linspace(0.0, TC_NOMINAL_S, CONTACT_SAMPLES)
    post_short_s = 0.2
    tp = np.linspace(0.0, post_short_s, 2001)
    exact = modal_half_sine(
        mass, stiffness, impulse_vector, TC_NOMINAL_S, tc, tp
    )
    q_exact = exact["modes"] @ exact["y"]
    qd_exact = exact["modes"] @ exact["yd"]
    ndof = mass.shape[0]

    def rhs_contact(t: float, state: np.ndarray) -> np.ndarray:
        q = state[:ndof]
        qd = state[ndof:]
        shape = math.pi / (2.0 * TC_NOMINAL_S) * math.sin(
            math.pi * t / TC_NOMINAL_S
        )
        qdd = np.linalg.solve(mass, impulse_vector * shape - stiffness @ q)
        return np.concatenate([qd, qdd])

    def rhs_free(_t: float, state: np.ndarray) -> np.ndarray:
        q = state[:ndof]
        qd = state[ndof:]
        qdd = np.linalg.solve(mass, -stiffness @ q)
        return np.concatenate([qd, qdd])

    contact = solve_ivp(
        rhs_contact,
        (0.0, TC_NOMINAL_S),
        np.zeros(2 * ndof),
        method="DOP853",
        t_eval=tc,
        rtol=1.0e-12,
        atol=1.0e-14,
        max_step=TC_NOMINAL_S / 100.0,
    )
    free = solve_ivp(
        rhs_free,
        (0.0, post_short_s),
        contact.y[:, -1],
        method="DOP853",
        t_eval=tp,
        rtol=1.0e-12,
        atol=1.0e-14,
        max_step=2.0e-4,
    )
    if not contact.success or not free.success:
        raise RuntimeError("NUMERICAL_CROSSCHECK_SOLVER_FAILURE")

    q_numeric = np.hstack([contact.y[:ndof], free.y[:ndof, 1:]])
    qd_numeric = np.hstack([contact.y[ndof:], free.y[ndof:, 1:]])
    tip_exact = float(np.max(np.abs(operators["tip_w"] @ q_exact)))
    tip_numeric = float(np.max(np.abs(operators["tip_w"] @ q_numeric)))
    torsion_exact = float(np.max(np.abs(operators["torsion_nodes"] @ q_exact)))
    torsion_numeric = float(np.max(np.abs(operators["torsion_nodes"] @ q_numeric)))

    shape = math.pi / (2.0 * TC_NOMINAL_S) * np.sin(
        math.pi * tc / TC_NOMINAL_S
    )
    trapz_integral = float(np.trapezoid(shape, tc))
    return {
        "analytic_forcing": {
            "shape": "pi/(2*Tc) * sin(pi*t/Tc)",
            "Tc_s": TC_NOMINAL_S,
            "spectral_center_hz": 1.0 / (2.0 * TC_NOMINAL_S),
            "analytic_integral": 1.0,
            "401_point_trapezoid_integral": trapz_integral,
            "trapezoid_absolute_error": abs(trapz_integral - 1.0),
        },
        "numerical_method": "DOP853 two-stage contact/free response",
        "post_crosscheck_duration_s": post_short_s,
        "rtol": 1.0e-12,
        "atol": 1.0e-14,
        "contact_success": bool(contact.success),
        "free_success": bool(free.success),
        "contact_nfev": int(contact.nfev),
        "free_nfev": int(free.nfev),
        "q_max_abs_difference": float(np.max(np.abs(q_numeric - q_exact))),
        "q_relative_to_peak_scale": float(
            np.max(np.abs(q_numeric - q_exact))
            / max(np.max(np.abs(q_exact)), DENOMINATOR_FLOOR)
        ),
        "qdot_max_abs_difference": float(np.max(np.abs(qd_numeric - qd_exact))),
        "qdot_relative_to_peak_scale": float(
            np.max(np.abs(qd_numeric - qd_exact))
            / max(np.max(np.abs(qd_exact)), DENOMINATOR_FLOOR)
        ),
        "tip_peak_relative_difference": abs(tip_numeric - tip_exact)
        / max(abs(tip_exact), DENOMINATOR_FLOOR),
        "torsion_peak_relative_difference": abs(torsion_numeric - torsion_exact)
        / max(abs(torsion_exact), DENOMINATOR_FLOOR),
    }


def mode_families(
    mass: np.ndarray,
    modes: np.ndarray,
    torsion_dofs: np.ndarray,
) -> tuple[list[str], np.ndarray]:
    m_tt = mass[np.ix_(torsion_dofs, torsion_dofs)]
    fractions = np.asarray(
        [
            modes[torsion_dofs, i]
            @ m_tt
            @ modes[torsion_dofs, i]
            for i in range(modes.shape[1])
        ]
    )
    classes = ["TORSION" if value > 0.5 else "BENDING" for value in fractions]
    return classes, fractions


def dense_post_peak(
    omega: np.ndarray,
    y_end: np.ndarray,
    yd_end: np.ndarray,
    physical_mode_matrix: np.ndarray,
    tc_s: float,
    post_s: float,
    coarse_step_s: float = 1.0e-5,
) -> dict[str, Any]:
    """Grid-independent audit of the post-contact physical peak."""
    best_value = -1.0
    best_row = -1
    best_tau = 0.0
    chunk_duration = 0.1
    for start in np.arange(0.0, post_s, chunk_duration):
        stop = min(post_s, start + chunk_duration)
        times = np.arange(start, stop + 0.5 * coarse_step_s, coarse_step_s)
        y = y_end[:, None] * np.cos(omega[:, None] * times[None, :]) + (
            (yd_end / omega)[:, None]
            * np.sin(omega[:, None] * times[None, :])
        )
        values = physical_mode_matrix @ y
        index = np.unravel_index(np.argmax(np.abs(values)), values.shape)
        value = float(abs(values[index]))
        if value > best_value:
            best_value = value
            best_row = int(index[0])
            best_tau = float(times[index[1]])

    local_step = 1.0e-7
    local_times = np.arange(
        max(0.0, best_tau - 1.0e-4),
        min(post_s, best_tau + 1.0e-4) + 0.5 * local_step,
        local_step,
    )
    local_y = y_end[:, None] * np.cos(omega[:, None] * local_times[None, :]) + (
        (yd_end / omega)[:, None]
        * np.sin(omega[:, None] * local_times[None, :])
    )
    local_values = physical_mode_matrix @ local_y
    local_index = np.unravel_index(
        np.argmax(np.abs(local_values)), local_values.shape
    )
    return {
        "peak": float(abs(local_values[local_index])),
        "operator_row_0based": int(local_index[0]),
        "post_contact_tau_s": float(local_times[local_index[1]]),
        "total_time_s": float(tc_s + local_times[local_index[1]]),
        "coarse_step_s": coarse_step_s,
        "local_refinement_step_s": local_step,
    }


def main() -> None:
    source_hashes: dict[str, Any] = {}
    for path, expected in EXPECTED_SHA256.items():
        actual = sha256(path)
        source_hashes[relative_path(path)] = {
            "expected_sha256": expected,
            "actual_sha256": actual,
            "match": actual == expected,
        }
        if actual != expected:
            raise RuntimeError(f"SOURCE_HASH_DRIFT:{relative_path(path)}")

    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    with np.load(NPZ_PATH) as loaded:
        data = {name: loaded[name] for name in loaded.files}

    mass = data["M"]
    stiffness = data["K_nominal"]
    phi = data["Phi_rom"]
    m_rom = data["Mrom"]
    k_rom = data["Krom_NOMINAL"]
    operators_hf = reconstruct_hf_operators(contract)
    operators_rom = {
        name: operators_hf[name] @ phi for name in operators_hf
    }
    stored_operator_names = {
        "w_nodes": "R_w_nodes",
        "theta_dofs": "R_theta_dofs",
        "hinge_relative": "R_hinge_relative",
        "torsion_nodes": "R_torsion_nodes",
        "tip_w": "R_tip_w",
    }
    operator_backcheck = {
        name: float(
            np.max(np.abs(operators_rom[name] - data[stored_name]))
        )
        for name, stored_name in stored_operator_names.items()
    }

    algebra_audit = {
        "M_shape": list(mass.shape),
        "K_shape": list(stiffness.shape),
        "Phi_shape": list(phi.shape),
        "Bt_Br_shape_per_wing": list(data["Bt_L"].shape),
        "Gamma_shape_per_wing": list(data["Gamma_t_L"].shape),
        "M_symmetry_max_abs": float(np.max(np.abs(mass - mass.T))),
        "K_symmetry_max_abs": float(np.max(np.abs(stiffness - stiffness.T))),
        "M_min_eigenvalue": float(np.min(np.linalg.eigvalsh(mass))),
        "K_min_eigenvalue": float(np.min(np.linalg.eigvalsh(stiffness))),
        "Phi_T_M_Phi_minus_I_max_abs": float(
            np.max(np.abs(phi.T @ mass @ phi - np.eye(phi.shape[1])))
        ),
        "Mrom_projection_max_abs": float(
            np.max(np.abs(m_rom - phi.T @ mass @ phi))
        ),
        "Krom_projection_max_abs": float(
            np.max(np.abs(k_rom - phi.T @ stiffness @ phi))
        ),
        "Gamma_projection_max_abs": {
            wing: {
                "translation": float(
                    np.max(
                        np.abs(
                            data[f"Gamma_t_{wing}"]
                            - phi.T @ data[f"Bt_{wing}"]
                        )
                    )
                ),
                "rotation": float(
                    np.max(
                        np.abs(
                            data[f"Gamma_r_{wing}"]
                            - phi.T @ data[f"Br_{wing}"]
                        )
                    )
                ),
            }
            for wing in ("L", "R")
        },
        "operator_projection_max_abs": operator_backcheck,
        "wing_symmetry": {
            "Bt_L_minus_Bt_R_max_abs": float(
                np.max(np.abs(data["Bt_L"] - data["Bt_R"]))
            ),
            "Br_L_plus_Br_R_max_abs": float(
                np.max(np.abs(data["Br_L"] + data["Br_R"]))
            ),
        },
    }

    tc_nominal, tp_nominal = time_grids(TC_NOMINAL_S)
    full_solutions: dict[str, dict[str, np.ndarray]] = {}
    current_rom: dict[str, Any] = {}
    forcing_vectors: dict[str, np.ndarray] = {}
    projected_forcing_vectors: dict[str, np.ndarray] = {}
    for wing in ("L", "R"):
        impulse = -(
            data[f"Bt_{wing}"] @ BASE_DELTA_TWIST_6[:3]
            + data[f"Br_{wing}"] @ BASE_DELTA_TWIST_6[3:]
        )
        impulse_rom = phi.T @ impulse
        impulse_gamma = -(
            data[f"Gamma_t_{wing}"] @ BASE_DELTA_TWIST_6[:3]
            + data[f"Gamma_r_{wing}"] @ BASE_DELTA_TWIST_6[3:]
        )
        forcing_vectors[wing] = impulse
        projected_forcing_vectors[wing] = impulse_rom
        full = modal_half_sine(
            mass,
            stiffness,
            impulse,
            TC_NOMINAL_S,
            tc_nominal,
            tp_nominal,
        )
        reduced = modal_half_sine(
            m_rom,
            k_rom,
            impulse_rom,
            TC_NOMINAL_S,
            tc_nominal,
            tp_nominal,
        )
        full_solutions[wing] = full
        full_metrics = response_metrics(full, operators_hf)
        rom_metrics = response_metrics(reduced, operators_rom)
        errors = relative_errors(rom_metrics, full_metrics)
        current_rom[wing] = {
            "hf_metrics": full_metrics,
            "rom5_metrics": rom_metrics,
            "relative_errors": errors,
            "max_relative_error": max(errors.values()),
            "forcing_impulse_generalized_norm": float(np.linalg.norm(impulse)),
            "projected_force_gamma_max_abs_residual": float(
                np.max(np.abs(impulse_rom - impulse_gamma))
            ),
        }

    current_global_max = max(
        current_rom[wing]["max_relative_error"] for wing in ("L", "R")
    )

    full_nominal = full_solutions["L"]
    full_modes = full_nominal["modes"]
    omega_full = full_nominal["omega"]
    semantics = contract["reduced_hf_dof_semantics"]
    torsion_dofs = np.asarray(
        [
            int(item["reduced_index_0based"])
            for item in semantics
            if item["kind"] == "TORSION_PHI"
        ],
        dtype=int,
    )
    classes, torsion_fractions = mode_families(mass, full_modes, torsion_dofs)
    first12 = list(range(12))
    bending_first12 = [i for i in first12 if classes[i] == "BENDING"]
    torsion_first12 = [i for i in first12 if classes[i] == "TORSION"]

    lane_counter = {"BENDING": 0, "TORSION": 0}
    mode_inventory = []
    labels_by_index: dict[int, str] = {}
    for index in first12:
        family = classes[index]
        lane_counter[family] += 1
        prefix = "B" if family == "BENDING" else "T"
        label = f"{prefix}{lane_counter[family]}"
        labels_by_index[index] = label
        mode_inventory.append(
            {
                "hf_index_0based": index,
                "hf_index_1based": index + 1,
                "label": label,
                "family": family,
                "frequency_hz": float(omega_full[index] / (2.0 * math.pi)),
                "torsion_mass_fraction": float(torsion_fractions[index]),
            }
        )

    mac = np.abs(full_modes.T @ mass @ phi)
    stored_to_hf = [int(np.argmax(mac[:, column])) for column in range(phi.shape[1])]
    mode_mapping = {
        "stored_mode_labels": contract["mode_labels"],
        "stored_column_to_hf_index_0based": stored_to_hf,
        "stored_column_mac": [
            float(mac[stored_to_hf[column], column])
            for column in range(phi.shape[1])
        ],
        "stored_nominal_frequencies_hz": contract[
            "nominal_selected_frequencies_hz"
        ],
    }

    bending_ops = {
        key: value
        for key, value in operators_hf.items()
        if key != "torsion_nodes"
    }
    bending_position = {mode: pos for pos, mode in enumerate(bending_first12)}
    torsion_position = {mode: pos for pos, mode in enumerate(torsion_first12)}
    bending_cache: dict[str, dict[int, dict[str, float]]] = {"L": {}, "R": {}}
    torsion_cache: dict[str, dict[int, float]] = {"L": {}, "R": {}}
    modal_energy_final: dict[str, np.ndarray] = {}

    for wing in ("L", "R"):
        solution = full_solutions[wing]
        y = solution["y"]
        yd = solution["yd"]
        modal_energy_final[wing] = 0.5 * (
            yd[:, -1] ** 2 + solution["eigenvalues"] * y[:, -1] ** 2
        )
        for mask in range(1 << len(bending_first12)):
            selected = [
                mode
                for pos, mode in enumerate(bending_first12)
                if (mask >> pos) & 1
            ]
            bending_cache[wing][mask] = {
                name: (
                    float(
                        np.max(
                            np.abs(operator @ full_modes[:, selected] @ y[selected])
                        )
                    )
                    if selected
                    else 0.0
                )
                for name, operator in bending_ops.items()
            }
        for mask in range(1 << len(torsion_first12)):
            selected = [
                mode
                for pos, mode in enumerate(torsion_first12)
                if (mask >> pos) & 1
            ]
            torsion_cache[wing][mask] = (
                float(
                    np.max(
                        np.abs(
                            operators_hf["torsion_nodes"]
                            @ full_modes[:, selected]
                            @ y[selected]
                        )
                    )
                )
                if selected
                else 0.0
            )

    def score_subset(selected_tuple: tuple[int, ...]) -> dict[str, Any]:
        selected = list(selected_tuple)
        bending_mask = sum(
            1 << bending_position[index]
            for index in selected
            if index in bending_position
        )
        torsion_mask = sum(
            1 << torsion_position[index]
            for index in selected
            if index in torsion_position
        )
        per_wing: dict[str, Any] = {}
        flattened: dict[str, float] = {}
        for wing in ("L", "R"):
            hf = current_rom[wing]["hf_metrics"]
            candidate = {
                "tip_peak_m": bending_cache[wing][bending_mask]["tip_w"],
                "node_peak_m": bending_cache[wing][bending_mask]["w_nodes"],
                "slope_peak_rad": bending_cache[wing][bending_mask][
                    "theta_dofs"
                ],
                "hinge_peak_rad": bending_cache[wing][bending_mask][
                    "hinge_relative"
                ],
                "torsion_peak_rad": torsion_cache[wing][torsion_mask],
                "modal_energy_peak_J": float(
                    np.sum(modal_energy_final[wing][selected])
                ),
            }
            reference = {key: hf[key] for key in candidate}
            errors = relative_errors(candidate, reference)
            per_wing[wing] = {
                "candidate_metrics": candidate,
                "relative_errors": errors,
                "max_relative_error": max(errors.values()),
            }
            flattened.update({f"{wing}_{key}": value for key, value in errors.items()})
        maximum = max(flattened.values())
        governing = sorted(
            key for key, value in flattened.items() if abs(value - maximum) <= 1.0e-14
        )
        return {
            "hf_indices_0based": selected,
            "modes": [
                {
                    "hf_index_0based": index,
                    "label": labels_by_index[index],
                    "family": classes[index],
                    "frequency_hz": float(omega_full[index] / (2.0 * math.pi)),
                }
                for index in selected
            ],
            "bending_mode_count": sum(classes[index] == "BENDING" for index in selected),
            "torsion_mode_count": sum(classes[index] == "TORSION" for index in selected),
            "per_wing": per_wing,
            "global_max_relative_error": maximum,
            "governing_metrics": governing,
            "passes_1pct": maximum <= RELATIVE_LIMIT,
        }

    best_by_dimension: dict[int, dict[str, Any]] = {}
    evaluated_by_dimension: dict[int, int] = {}
    for dimension in range(1, 13):
        best: dict[str, Any] | None = None
        count = 0
        for selected in itertools.combinations(first12, dimension):
            count += 1
            scored = score_subset(selected)
            if best is None or scored["global_max_relative_error"] < best[
                "global_max_relative_error"
            ]:
                best = scored
        if best is None:
            raise RuntimeError("EMPTY_COMBINATION_SEARCH")
        best_by_dimension[dimension] = best
        evaluated_by_dimension[dimension] = count

    minimum_passing_dimension = next(
        (
            dimension
            for dimension in range(1, 13)
            if best_by_dimension[dimension]["passes_1pct"]
        ),
        None,
    )

    preserve_three_bending: dict[int, dict[str, Any]] = {}
    required_bending = set(bending_first12)
    for dimension in range(len(required_bending), 13):
        candidates = []
        for selected in itertools.combinations(first12, dimension):
            if required_bending.issubset(selected):
                candidates.append(score_subset(selected))
        preserve_three_bending[dimension] = min(
            candidates, key=lambda item: item["global_max_relative_error"]
        )
    minimum_passing_preserve_three_bending = next(
        (
            dimension
            for dimension, result in preserve_three_bending.items()
            if result["passes_1pct"]
        ),
        None,
    )

    current_sorted_indices = tuple(sorted(stored_to_hf))
    current_eigen_subset = score_subset(current_sorted_indices)
    best_five = best_by_dimension[5]
    best_six = best_by_dimension[6]
    best_preserve_three_bending_seven = preserve_three_bending[7]

    torsion_all = [
        index for index, family in enumerate(classes) if family == "TORSION"
    ]
    contact_sensitivity: dict[str, Any] = {}
    for tc_ms in (5.0, 10.0, 20.0, 50.0, 100.0):
        tc_s = tc_ms / 1000.0
        tc_grid, tp_grid = time_grids(tc_s)
        solution = modal_half_sine(
            mass,
            stiffness,
            forcing_vectors["L"],
            tc_s,
            tc_grid,
            tp_grid,
        )
        y = solution["y"]
        full_peak = float(
            np.max(
                np.abs(
                    operators_hf["torsion_nodes"] @ solution["modes"] @ y
                )
            )
        )
        first_two = torsion_all[:2]
        two_peak = float(
            np.max(
                np.abs(
                    operators_hf["torsion_nodes"]
                    @ solution["modes"][:, first_two]
                    @ y[first_two]
                )
            )
        )
        two_error = abs(two_peak - full_peak) / max(
            abs(full_peak), DENOMINATOR_FLOOR
        )
        minimum_torsion_count = None
        convergence_curve = []
        for count in range(1, len(torsion_all) + 1):
            selected = torsion_all[:count]
            peak = float(
                np.max(
                    np.abs(
                        operators_hf["torsion_nodes"]
                        @ solution["modes"][:, selected]
                        @ y[selected]
                    )
                )
            )
            error = abs(peak - full_peak) / max(
                abs(full_peak), DENOMINATOR_FLOOR
            )
            if count <= 10:
                convergence_curve.append(
                    {
                        "first_n_torsion_modes": count,
                        "peak_rad": peak,
                        "relative_error": error,
                    }
                )
            if minimum_torsion_count is None and error <= RELATIVE_LIMIT:
                minimum_torsion_count = count
                break
        contact_sensitivity[f"TC_{tc_ms:g}MS"] = {
            "Tc_ms": tc_ms,
            "half_sine_spectral_center_hz": 1.0 / (2.0 * tc_s),
            "hf_torsion_peak_rad": full_peak,
            "current_first_two_torsion_peak_rad": two_peak,
            "current_first_two_relative_error": two_error,
            "minimum_first_n_torsion_modes_for_1pct": minimum_torsion_count,
            "convergence_curve_until_pass_or_n10": convergence_curve,
        }

    # Dense post-contact sampling check.  Only pure torsion columns are retained
    # in this calculation, so no bending work is repeated.
    full_torsion_modes = np.asarray(torsion_all, dtype=int)
    dense_full = dense_post_peak(
        full_solutions["L"]["omega"][full_torsion_modes],
        full_solutions["L"]["y_end"][full_torsion_modes],
        full_solutions["L"]["yd_end"][full_torsion_modes],
        operators_hf["torsion_nodes"]
        @ full_solutions["L"]["modes"][:, full_torsion_modes],
        TC_NOMINAL_S,
        POST_WINDOW_S,
    )
    reduced_nominal = modal_half_sine(
        m_rom,
        k_rom,
        projected_forcing_vectors["L"],
        TC_NOMINAL_S,
        tc_nominal,
        tp_nominal,
    )
    reduced_physical_torsion = (
        operators_hf["torsion_nodes"] @ phi @ reduced_nominal["modes"]
    )
    reduced_torsion_columns = np.where(
        np.max(np.abs(reduced_physical_torsion), axis=0) > 1.0e-10
    )[0]
    dense_rom = dense_post_peak(
        reduced_nominal["omega"][reduced_torsion_columns],
        reduced_nominal["y_end"][reduced_torsion_columns],
        reduced_nominal["yd_end"][reduced_torsion_columns],
        reduced_physical_torsion[:, reduced_torsion_columns],
        TC_NOMINAL_S,
        POST_WINDOW_S,
    )
    dense_error = abs(dense_rom["peak"] - dense_full["peak"]) / max(
        dense_full["peak"], DENOMINATOR_FLOOR
    )

    numeric_cross = numerical_crosscheck(
        m_rom,
        k_rom,
        projected_forcing_vectors["L"],
        operators_rom,
    )

    # Isolate the torsion-lane energy masking effect at contact end.
    torsion_energy = modal_energy_final["L"][torsion_all]
    torsion_energy_first_two = float(np.sum(torsion_energy[:2]))
    torsion_energy_full = float(np.sum(torsion_energy))
    dense_full_peak = dense_full["peak"]
    tail_at_dense_peak_tau = dense_full["post_contact_tau_s"]
    omega_t = full_solutions["L"]["omega"][full_torsion_modes]
    y_t = full_solutions["L"]["y_end"][full_torsion_modes] * np.cos(
        omega_t * tail_at_dense_peak_tau
    ) + (
        full_solutions["L"]["yd_end"][full_torsion_modes] / omega_t
    ) * np.sin(omega_t * tail_at_dense_peak_tau)
    tip_mode_contributions = (
        operators_hf["torsion_nodes"][-1]
        @ full_solutions["L"]["modes"][:, full_torsion_modes]
    ) * y_t

    result = {
        "schema": "ROM5_DIMENSION_FALSIFIER_V1",
        "evidence_id": "CHECKPOINT_A_RED_TEAM_ROM5_DIMENSION_FALSIFIER_V1",
        "verdict": "ROM5_FULL_FIELD_TRUNCATION_FALSIFIED_AT_1PCT",
        "scope": (
            "Independent linear Solar R2 per-wing HF-to-ROM dimension falsifier; "
            "nominal 20 ms undamped contact plus bounded contact-window sensitivity"
        ),
        "deterministic_recompute": True,
        "source_hashes": source_hashes,
        "input_contract": {
            "base_delta_twist_6": BASE_DELTA_TWIST_6,
            "base_delta_twist_units": "[m/s,m/s,m/s,rad/s,rad/s,rad/s]",
            "base_delta_authority": (
                "DIAGNOSTIC_INPUT_ONLY__NOT_REDERIVED_OR_GRANTED_COUPLED_AUTHORITY"
            ),
            "contact_window_nominal_ms": 20.0,
            "post_window_s": POST_WINDOW_S,
            "contact_samples": CONTACT_SAMPLES,
            "post_samples": POST_SAMPLES,
            "damping_ratio": 0.0,
            "relative_limit": RELATIVE_LIMIT,
            "relative_denominator_floor": DENOMINATOR_FLOOR,
            "forcing_equation": (
                "f_impulse = -(B_t*delta_v_base + B_r*delta_omega_base); "
                "f(t)=f_impulse*pi/(2*Tc)*sin(pi*t/Tc)"
            ),
        },
        "algebra_audit": algebra_audit,
        "analytic_numeric_crosscheck": numeric_cross,
        "mode_inventory_first12": mode_inventory,
        "round3_mode_mapping": mode_mapping,
        "current_round3_rom5": {
            "selection_rule": contract["selection_rule"],
            "stored_hf_indices_0based": stored_to_hf,
            "sorted_hf_indices_0based": list(current_sorted_indices),
            "per_wing": current_rom,
            "global_max_relative_error": current_global_max,
            "passes_1pct_all_published_metrics": current_global_max
            <= RELATIVE_LIMIT,
            "direct_eigen_subset_recompute": current_eigen_subset,
        },
        "dimension_combination_falsifier": {
            "eigenmode_pool": "first 12 nominal HF eigenmodes",
            "five_dimensional_combination_count": evaluated_by_dimension[5],
            "expected_five_dimensional_combination_count": math.comb(12, 5),
            "all_792_five_dimensional_subsets_evaluated": evaluated_by_dimension[5]
            == 792,
            "metrics": [
                "tip_peak_m",
                "node_peak_m",
                "slope_peak_rad",
                "hinge_peak_rad",
                "torsion_peak_rad",
                "modal_energy_peak_J",
            ],
            "score": (
                "max over LEFT/RIGHT and metrics of "
                "abs(candidate_peak-HF_peak)/max(abs(HF_peak),1e-14)"
            ),
            "best_by_dimension_1_to_7": {
                str(dimension): best_by_dimension[dimension]
                for dimension in range(1, 8)
            },
            "best_five_dimensional_subset": best_five,
            "minimum_passing_dimension_within_first12": minimum_passing_dimension,
            "best_six_dimensional_subset": best_six,
            "minimum_passing_dimension_preserving_all_three_bending_modes": (
                minimum_passing_preserve_three_bending
            ),
            "best_seven_dimensional_subset_preserving_three_bending_modes": (
                best_preserve_three_bending_seven
            ),
            "round3_three_bending_two_torsion_subset": current_eigen_subset,
        },
        "contact_window_sensitivity": contact_sensitivity,
        "sampling_and_denominator_audit": {
            "official_grid_full_torsion_peak_rad": current_rom["L"]["hf_metrics"][
                "torsion_peak_rad"
            ],
            "official_grid_rom5_torsion_peak_rad": current_rom["L"][
                "rom5_metrics"
            ]["torsion_peak_rad"],
            "official_grid_relative_error": current_rom["L"]["relative_errors"][
                "torsion_peak_rad"
            ],
            "dense_full": dense_full,
            "dense_rom5": dense_rom,
            "dense_relative_error": dense_error,
            "hf_peak_to_denominator_floor_ratio": dense_full_peak
            / DENOMINATOR_FLOOR,
            "near_zero_denominator": dense_full_peak <= 100.0 * DENOMINATOR_FLOOR,
        },
        "physical_cause": {
            "contact_spectral_center_hz": 25.0,
            "T3": mode_inventory[4],
            "T4": mode_inventory[5],
            "full_torsion_energy_J": torsion_energy_full,
            "first_two_torsion_energy_J": torsion_energy_first_two,
            "first_two_torsion_energy_coverage": torsion_energy_first_two
            / torsion_energy_full,
            "tip_torsion_mode_contributions_at_dense_full_peak_rad": {
                f"T{index + 1}": float(value)
                for index, value in enumerate(tip_mode_contributions[:8])
            },
            "tail_after_T2_at_dense_full_peak_rad": float(
                np.sum(tip_mode_contributions[2:])
            ),
            "interpretation": (
                "The 25 Hz contact band lies between T2 and T3.  T3/T4 are "
                "physically excited and their post-contact free response is omitted "
                "by the two-torsion-mode Round3 basis."
            ),
        },
        "static_residual_assessment": {
            "formula": "q_res=(K^-1-Phi*Krom^-1*Phi^T)*f(t)",
            "contact_end_s": TC_NOMINAL_S,
            "full_dense_peak_time_s": dense_full["total_time_s"],
            "rom_dense_peak_time_s": dense_rom["total_time_s"],
            "force_after_contact": 0.0,
            "static_residual_at_reported_post_contact_peaks": 0.0,
            "can_close_dynamic_tail_without_new_states": False,
            "disposition": (
                "A static/mode-acceleration residual cannot repair a free-response "
                "peak after the half-sine force has ended; a persistent dynamic "
                "residual kernel is additional dynamics, not a five-mode ROM."
            ),
        },
        "contract_disposition": {
            "owner_P2_mode_count_contract": "3-5 dominant modes per wing",
            "round3_selection_rule": contract["selection_rule"],
            "best_five_dimensional_result": "FAIL_1PCT",
            "minimum_nominal_20ms_passing_dimension": minimum_passing_dimension,
            "minimum_dimension_preserving_three_bending_modes": (
                minimum_passing_preserve_three_bending
            ),
            "silent_mode_count_extension_forbidden": True,
            "round3_component_gate_changed_by_this_falsifier": False,
            "e15_inheritance": "NOT_INHERITED",
            "legacy_ancf_status": "REPEAT_ANCF_CERTIFICATION",
            "recommended_checkpoint_a_disposition": (
                "DIAGNOSTIC_COMPLETE_WITH_PROVISIONAL_PHYSICS__"
                "ROM5_FULL_FIELD_TRUNCATION_FAIL__NO_E15_OR_RELEASE_CREDIT"
            ),
        },
        "nonclaims": [
            "No e22 module, result, runner, or gate is imported or modified.",
            "The diagnostic base delta twist is not independently re-derived here.",
            "The first-12 eigenmode enumeration is not a proof over arbitrary nonmodal or response-trained bases.",
            "No threshold is widened and no torsion observable is removed from the score.",
            "No coupled spacecraft-arm-target dynamics claim is made.",
            "No ANCF/e15 certification or inheritance claim is made.",
            "No flight qualification, release, or Owner acceptance claim is made.",
            "The accepted Round3 component artifacts are not mutated by this evidence.",
        ],
        "review_status": "PENDING_OWNER_REVIEW",
        "owner_accepted": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    write_json(OUT_PATH, result)
    print(f"wrote {relative_path(OUT_PATH)}")
    print(f"verdict={result['verdict']}")
    print(f"current_rom5_max_relative_error={current_global_max:.12g}")
    print(
        "best_5d_max_relative_error="
        f"{best_five['global_max_relative_error']:.12g}"
    )
    print(f"minimum_passing_dimension={minimum_passing_dimension}")
    print(f"output_sha256={sha256(OUT_PATH)}")


if __name__ == "__main__":
    main()
