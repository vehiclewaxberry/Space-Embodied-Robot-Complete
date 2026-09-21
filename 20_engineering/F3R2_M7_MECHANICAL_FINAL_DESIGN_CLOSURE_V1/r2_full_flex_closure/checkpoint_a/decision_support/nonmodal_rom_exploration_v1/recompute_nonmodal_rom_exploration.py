#!/usr/bin/env python3
"""Recompute the bounded nonmodal ROM exploration for Solar R2.

This package is decision support only.  It consumes frozen Round3/Checkpoint-A
evidence, explores explicitly enumerated POD/Galerkin basis families, and never
modifies or upgrades Round3, E22, Checkpoint-A, e15, or any release artifact.

The exploration is deliberately candid about data reuse:

* basis snapshots: LEFT wing, Tc = 10/20/50 ms;
* internal holdout checks: Tc = 5/100 ms and RIGHT wing;
* method, rank, and the favourable 5D weighting were selected after inspecting
  the five-window scores, so these checks are not blind validation.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.linalg import eigh


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[5]
ROUND3 = HERE.parents[2] / "round3_hf_rom_v2"
REDTEAM = HERE.parents[1] / "red_team"
PARENT_DECISION_SUPPORT = HERE.parent

NPZ_PATH = ROUND3 / "R2_HF_ROM_NUMERICAL_DATA_V2.npz"
ROM5_CONTRACT_PATH = ROUND3 / "R2_FIVE_MODE_ROM_V2.json"
FALSIFIER_SCRIPT_PATH = REDTEAM / "recompute_rom5_dimension_falsifier.py"
FALSIFIER_RESULT_PATH = REDTEAM / "ROM5_DIMENSION_FALSIFIER_V1.json"
MULTICONTACT_SCRIPT_PATH = (
    PARENT_DECISION_SUPPORT / "recompute_multicontact_rom_dimension.py"
)
MULTICONTACT_RESULT_PATH = (
    PARENT_DECISION_SUPPORT / "MULTICONTACT_ROM_DIMENSION_DECISION_SUPPORT_V1.json"
)
OUT_PATH = HERE / "R2_NONMODAL_ROM_EXPLORATION_RESULTS_V1.json"

EXPECTED_SOURCE_SHA256 = {
    NPZ_PATH: "8D10E085385EDF2FACE92B9B48D1172939A31FD3B57E55242ED11C9EEEDF50DA",
    ROM5_CONTRACT_PATH: "9E4FE903AE7E34584F39F16275EF20FC31831AFB7F78B3B625418B86D0FBC817",
    FALSIFIER_SCRIPT_PATH: "2CEEA915A5A4B0D29891DA96FEA21816E855C4D380A2692BB526369E41E5C3EC",
    FALSIFIER_RESULT_PATH: "D219E69FE8D3555228BB007774F0B59F4F5BDFAD7711569EB7CD074130104E18",
    MULTICONTACT_SCRIPT_PATH: "C600C397114B408BDF3470C395208C930476A8CEAB1184C3DCF69AAE1C6BEF3D",
    MULTICONTACT_RESULT_PATH: "3237660693EC9790223559028264E115AEAB45AAA8A37250E0A58A5CAA81341D",
}

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
WINDOWS_MS = (5.0, 10.0, 20.0, 50.0, 100.0)
TRAINING_WINDOWS_MS = (10.0, 20.0, 50.0)
HOLDOUT_WINDOWS_MS = (5.0, 100.0)
CONTACT_SAMPLES = 401
POST_SAMPLES = 5001
POST_WINDOW_S = 5.0
SNAPSHOT_STRIDE = 5
RELATIVE_LIMIT = 0.01
DENOMINATOR_FLOOR = 1.0e-14
METRIC_NAMES = (
    "tip_peak_m",
    "node_peak_m",
    "slope_peak_rad",
    "hinge_peak_rad",
    "torsion_peak_rad",
    "modal_energy_peak_J",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(f"NONMODAL_EXPLORATION_FAIL_CLOSED:{message}")


def jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [jsonable(item) for item in value]
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(jsonable(payload), indent=2, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def unit_row(ndof: int, index: int) -> np.ndarray:
    out = np.zeros(ndof)
    out[int(index)] = 1.0
    return out


def reconstruct_hf_operators(contract: dict[str, Any]) -> dict[str, np.ndarray]:
    """Reconstruct the published full-field operators from DOF semantics."""
    semantics = contract["reduced_hf_dof_semantics"]
    ndof = len(semantics)
    w_items = sorted(
        (item for item in semantics if item["kind"] == "TRANSVERSE_W"),
        key=lambda item: int(item["node"]),
    )
    theta_items = sorted(
        (item for item in semantics if item["kind"] == "BENDING_SLOPE_THETA"),
        key=lambda item: (int(item["node"]), str(item["side"])),
    )
    torsion_items = sorted(
        (item for item in semantics if item["kind"] == "TORSION_PHI"),
        key=lambda item: int(item["node"]),
    )

    r_w = np.vstack(
        [np.zeros(ndof)]
        + [unit_row(ndof, item["reduced_index_0based"]) for item in w_items]
    )
    r_theta = np.vstack(
        [unit_row(ndof, item["reduced_index_0based"]) for item in theta_items]
    )
    r_torsion = np.vstack(
        [np.zeros(ndof)]
        + [unit_row(ndof, item["reduced_index_0based"]) for item in torsion_items]
    )

    by_node: dict[int, list[dict[str, Any]]] = {}
    for item in theta_items:
        by_node.setdefault(int(item["node"]), []).append(item)
    duplicated_hinge_nodes = sorted(
        node
        for node, items in by_node.items()
        if {str(item["side"]) for item in items} == {"L", "R"}
    )
    root_item = by_node[0][0]
    hinge_rows = [unit_row(ndof, root_item["reduced_index_0based"])]
    for node in duplicated_hinge_nodes:
        left = next(item for item in by_node[node] if item["side"] == "L")
        right = next(item for item in by_node[node] if item["side"] == "R")
        hinge_rows.append(
            unit_row(ndof, right["reduced_index_0based"])
            - unit_row(ndof, left["reduced_index_0based"])
        )

    return {
        "w_nodes": r_w,
        "theta_dofs": r_theta,
        "hinge_relative": np.vstack(hinge_rows),
        "torsion_nodes": r_torsion,
        "tip_w": r_w[-1:, :],
    }


def closed_form_response(
    eigenvalues: np.ndarray,
    modal_impulse: np.ndarray,
    tc_s: float,
) -> dict[str, np.ndarray]:
    """Undamped response to a unit-integral half-sine contact pulse."""
    omega = np.sqrt(eigenvalues)
    forcing_omega = math.pi / tc_s
    denominator = eigenvalues - forcing_omega**2
    separation = np.abs(denominator) / np.maximum(eigenvalues, forcing_omega**2)
    require(float(np.min(separation)) > 1.0e-10, "near resonant closed form")

    force_amplitude = math.pi / (2.0 * tc_s)
    particular = modal_impulse * force_amplitude / denominator
    homogeneous = -particular * forcing_omega / omega

    contact_t = np.linspace(0.0, tc_s, CONTACT_SAMPLES)[None, :]
    y_contact = particular[:, None] * np.sin(forcing_omega * contact_t) + (
        homogeneous[:, None] * np.sin(omega[:, None] * contact_t)
    )
    yd_contact = (
        particular[:, None] * forcing_omega * np.cos(forcing_omega * contact_t)
        + homogeneous[:, None] * omega[:, None] * np.cos(omega[:, None] * contact_t)
    )

    y_end = y_contact[:, -1]
    yd_end = yd_contact[:, -1]
    post_t = np.linspace(0.0, POST_WINDOW_S, POST_SAMPLES)[None, :]
    y_post = y_end[:, None] * np.cos(omega[:, None] * post_t) + (
        (yd_end / omega)[:, None] * np.sin(omega[:, None] * post_t)
    )
    yd_post = -y_end[:, None] * omega[:, None] * np.sin(
        omega[:, None] * post_t
    ) + yd_end[:, None] * np.cos(omega[:, None] * post_t)

    return {
        "y": np.hstack([y_contact, y_post[:, 1:]]),
        "yd": np.hstack([yd_contact, yd_post[:, 1:]]),
        "y_contact": y_contact,
        "yd_contact": yd_contact,
        "y_end": y_end,
        "yd_end": yd_end,
        "omega": omega,
    }


def response_metrics(
    solution: dict[str, np.ndarray],
    output_operators: dict[str, np.ndarray],
    eigenvalues: np.ndarray,
) -> dict[str, float]:
    values = {
        name: operator @ solution["y"]
        for name, operator in output_operators.items()
    }
    energy = 0.5 * np.sum(
        solution["yd"] ** 2 + eigenvalues[:, None] * solution["y"] ** 2,
        axis=0,
    )
    return {
        "tip_peak_m": float(np.max(np.abs(values["tip_w"]))),
        "node_peak_m": float(np.max(np.abs(values["w_nodes"]))),
        "slope_peak_rad": float(np.max(np.abs(values["theta_dofs"]))),
        "hinge_peak_rad": float(np.max(np.abs(values["hinge_relative"]))),
        "torsion_peak_rad": float(np.max(np.abs(values["torsion_nodes"]))),
        "modal_energy_peak_J": float(np.max(energy)),
    }


def metric_errors(
    candidate: dict[str, float], reference: dict[str, float]
) -> dict[str, float]:
    return {
        name: abs(candidate[name] - reference[name])
        / max(abs(reference[name]), DENOMINATOR_FLOOR)
        for name in METRIC_NAMES
    }


def evaluate_basis(
    basis_modal: np.ndarray,
    eigenvalues: np.ndarray,
    impulse_modal: dict[str, np.ndarray],
    operators_modal: dict[str, np.ndarray],
    references: dict[float, dict[str, dict[str, float]]],
) -> dict[str, Any]:
    dimension = basis_modal.shape[1]
    orthogonality = float(
        np.max(np.abs(basis_modal.T @ basis_modal - np.eye(dimension)))
    )
    require(orthogonality <= 1.0e-10, "candidate basis is not orthonormal")
    kr = basis_modal.T @ (eigenvalues[:, None] * basis_modal)
    ritz_values, ritz_vectors = np.linalg.eigh(kr)
    physical_modal_basis = basis_modal @ ritz_vectors
    reduced_operators = {
        name: operator @ physical_modal_basis
        for name, operator in operators_modal.items()
    }

    windows: dict[str, Any] = {}
    flat: dict[str, float] = {}
    for tc_ms in WINDOWS_MS:
        tc_s = tc_ms / 1000.0
        wings: dict[str, Any] = {}
        for wing in ("L", "R"):
            reduced_impulse = physical_modal_basis.T @ impulse_modal[wing]
            solution = closed_form_response(ritz_values, reduced_impulse, tc_s)
            candidate_metrics = response_metrics(
                solution, reduced_operators, ritz_values
            )
            errors = metric_errors(candidate_metrics, references[tc_ms][wing])
            wings[wing] = {
                "hf_metrics": references[tc_ms][wing],
                "candidate_metrics": candidate_metrics,
                "relative_errors": errors,
                "max_relative_error": max(errors.values()),
            }
            flat.update(
                {
                    f"TC_{tc_ms:g}MS_{wing}_{name}": value
                    for name, value in errors.items()
                }
            )
        window_max = max(
            error
            for key, error in flat.items()
            if key.startswith(f"TC_{tc_ms:g}MS_")
        )
        windows[f"TC_{tc_ms:g}MS"] = {
            "Tc_ms": tc_ms,
            "per_wing": wings,
            "max_relative_error": window_max,
            "passes_1pct": window_max <= RELATIVE_LIMIT,
        }

    maximum = max(flat.values())
    return {
        "dimension": dimension,
        "basis_orthogonality_max_abs": orthogonality,
        "ritz_frequencies_hz": np.sqrt(ritz_values) / (2.0 * math.pi),
        "per_window": windows,
        "per_window_max_relative_error": {
            name: item["max_relative_error"] for name, item in windows.items()
        },
        "global_max_relative_error": maximum,
        "governing_cases": sorted(
            key for key, value in flat.items() if abs(value - maximum) <= 1.0e-13
        ),
        "passes_1pct_all_windows_wings_metrics": maximum <= RELATIVE_LIMIT,
    }


def normalised_snapshot(solution: dict[str, np.ndarray], rows: Any = slice(None)) -> np.ndarray:
    snapshot = solution["y"][rows, ::SNAPSHOT_STRIDE].copy()
    scale = float(np.linalg.norm(snapshot, "fro"))
    require(scale > 0.0, "zero training snapshot")
    return snapshot / scale


def weighted_pod_basis_5d(
    snapshots: dict[tuple[str, float], dict[str, np.ndarray]],
    torsion_indices: np.ndarray,
    snapshot_wings: Iterable[str],
    alpha: float,
) -> np.ndarray:
    matrices = []
    for wing in snapshot_wings:
        for tc_ms in TRAINING_WINDOWS_MS:
            matrix = normalised_snapshot(snapshots[(wing, tc_ms)])
            weighted = matrix.copy()
            weighted[torsion_indices, :] *= alpha
            matrices.append(weighted)
    left_vectors = np.linalg.svd(
        np.hstack(matrices), full_matrices=False
    )[0][:, :5]
    raw = left_vectors.copy()
    raw[torsion_indices, :] /= alpha
    return np.linalg.qr(raw)[0][:, :5]


def hybrid_basis(
    bending_indices: np.ndarray,
    torsion_indices: np.ndarray,
    torsion_pod: np.ndarray,
    torsion_rank: int,
    ndof: int,
) -> np.ndarray:
    basis = np.zeros((ndof, 3 + torsion_rank))
    basis[bending_indices[:3], np.arange(3)] = 1.0
    basis[
        np.ix_(torsion_indices, np.arange(3, 3 + torsion_rank))
    ] = torsion_pod[:, :torsion_rank]
    return basis


def contact_end_state(
    eigenvalues: np.ndarray, modal_impulse: np.ndarray, tc_s: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    response = closed_form_response(eigenvalues, modal_impulse, tc_s)
    return (
        response["y_end"],
        response["yd_end"],
        response["y_contact"],
        response["yd_contact"],
    )


def dense_post_peak(
    eigenvalues: np.ndarray,
    y_end: np.ndarray,
    yd_end: np.ndarray,
    output_matrix: np.ndarray,
) -> dict[str, Any]:
    omega = np.sqrt(eigenvalues)
    best_value = -1.0
    best_row = -1
    best_tau = 0.0
    coarse_step_s = 1.0e-5
    chunk_duration_s = 0.1
    for start in np.arange(0.0, POST_WINDOW_S, chunk_duration_s):
        stop = min(POST_WINDOW_S, start + chunk_duration_s)
        times = np.arange(start, stop + 0.5 * coarse_step_s, coarse_step_s)
        y = y_end[:, None] * np.cos(omega[:, None] * times[None, :]) + (
            (yd_end / omega)[:, None]
            * np.sin(omega[:, None] * times[None, :])
        )
        values = output_matrix @ y
        index = np.unravel_index(np.argmax(np.abs(values)), values.shape)
        value = float(abs(values[index]))
        if value > best_value:
            best_value = value
            best_row = int(index[0])
            best_tau = float(times[index[1]])

    local_step_s = 1.0e-7
    local_times = np.arange(
        max(0.0, best_tau - 1.0e-4),
        min(POST_WINDOW_S, best_tau + 1.0e-4) + 0.5 * local_step_s,
        local_step_s,
    )
    local_y = y_end[:, None] * np.cos(
        omega[:, None] * local_times[None, :]
    ) + (yd_end / omega)[:, None] * np.sin(
        omega[:, None] * local_times[None, :]
    )
    local_values = output_matrix @ local_y
    local_index = np.unravel_index(
        np.argmax(np.abs(local_values)), local_values.shape
    )
    return {
        "peak_rad": float(abs(local_values[local_index])),
        "operator_row_0based": int(local_index[0]),
        "post_contact_tau_s": float(local_times[local_index[1]]),
        "coarse_step_s": coarse_step_s,
        "local_refinement_half_width_s": 1.0e-4,
        "local_refinement_step_s": local_step_s,
        "coarse_seed_peak_rad": best_value,
        "coarse_seed_operator_row_0based": best_row,
        "coarse_seed_tau_s": best_tau,
    }


def dense_5ms_torsion_audit(
    eigenvalues: np.ndarray,
    impulse_modal: dict[str, np.ndarray],
    operators_modal: dict[str, np.ndarray],
    torsion_indices: np.ndarray,
    torsion_pod: np.ndarray,
) -> dict[str, Any]:
    tc_s = 0.005
    lam_t = eigenvalues[torsion_indices]
    op_t = operators_modal["torsion_nodes"][:, torsion_indices]
    pod7 = torsion_pod[:, :7]
    kr = pod7.T @ (lam_t[:, None] * pod7)
    ritz_values, ritz_vectors = np.linalg.eigh(kr)
    rom_output = op_t @ pod7 @ ritz_vectors

    per_wing = {}
    for wing in ("L", "R"):
        b_t = impulse_modal[wing][torsion_indices]
        hf_end, hf_vel, hf_contact, _ = contact_end_state(lam_t, b_t, tc_s)
        b_rom = ritz_vectors.T @ pod7.T @ b_t
        rom_end, rom_vel, rom_contact, _ = contact_end_state(
            ritz_values, b_rom, tc_s
        )
        hf_dense = dense_post_peak(lam_t, hf_end, hf_vel, op_t)
        rom_dense = dense_post_peak(
            ritz_values, rom_end, rom_vel, rom_output
        )
        relative = abs(rom_dense["peak_rad"] - hf_dense["peak_rad"]) / max(
            abs(hf_dense["peak_rad"]), DENOMINATOR_FLOOR
        )
        hf_contact_peak = float(np.max(np.abs(op_t @ hf_contact)))
        rom_contact_peak = float(np.max(np.abs(rom_output @ rom_contact)))
        per_wing[wing] = {
            "hf_post_contact_dense_peak": hf_dense,
            "rom7_post_contact_dense_peak": rom_dense,
            "relative_peak_error": relative,
            "passes_1pct": relative <= RELATIVE_LIMIT,
            "contact_401_point_peak_rad": {
                "hf": hf_contact_peak,
                "rom7": rom_contact_peak,
            },
            "post_contact_controls_global_peak": (
                hf_dense["peak_rad"] >= hf_contact_peak
                and rom_dense["peak_rad"] >= rom_contact_peak
            ),
        }
    global_error = max(item["relative_peak_error"] for item in per_wing.values())
    return {
        "scope": "Tc=5 ms post-contact torsion peak only; official grid covers all six metrics",
        "per_wing": per_wing,
        "global_dense_relative_peak_error": global_error,
        "passes_1pct": global_error <= RELATIVE_LIMIT,
    }


def main() -> None:
    source_hashes: dict[str, Any] = {}
    for path, expected in EXPECTED_SOURCE_SHA256.items():
        actual = digest(path)
        source_hashes[rel(path)] = {
            "expected_sha256": expected,
            "actual_sha256": actual,
            "match": actual == expected,
        }
        require(actual == expected, f"source hash drift:{rel(path)}")

    contract = json.loads(ROM5_CONTRACT_PATH.read_text(encoding="utf-8"))
    existing_falsifier = json.loads(
        FALSIFIER_RESULT_PATH.read_text(encoding="utf-8")
    )
    existing_multicontact = json.loads(
        MULTICONTACT_RESULT_PATH.read_text(encoding="utf-8")
    )
    with np.load(NPZ_PATH) as archive:
        data = {name: archive[name] for name in archive.files}

    mass = data["M"]
    stiffness = data["K_nominal"]
    eigenvalues, physical_modes = eigh(stiffness, mass)
    require(float(np.min(eigenvalues)) > 0.0, "nonpositive eigenvalue")
    modal_mass_orthogonality = float(
        np.max(
            np.abs(
                physical_modes.T @ mass @ physical_modes
                - np.eye(mass.shape[0])
            )
        )
    )
    require(modal_mass_orthogonality <= 1.0e-10, "HF modes not mass orthonormal")

    physical_operators = reconstruct_hf_operators(contract)
    modal_operators = {
        name: operator @ physical_modes
        for name, operator in physical_operators.items()
    }
    semantics = contract["reduced_hf_dof_semantics"]
    torsion_dofs = np.asarray(
        [
            int(item["reduced_index_0based"])
            for item in semantics
            if item["kind"] == "TORSION_PHI"
        ],
        dtype=int,
    )
    m_tt = mass[np.ix_(torsion_dofs, torsion_dofs)]
    torsion_mass_fraction = np.asarray(
        [
            physical_modes[torsion_dofs, index]
            @ m_tt
            @ physical_modes[torsion_dofs, index]
            for index in range(physical_modes.shape[1])
        ]
    )
    torsion_indices = np.flatnonzero(torsion_mass_fraction > 0.5)
    bending_indices = np.flatnonzero(torsion_mass_fraction < 0.5)
    require(
        bending_indices[:3].tolist() == [0, 3, 7],
        "bending mode identity drift",
    )
    require(
        torsion_indices[:8].tolist() == [1, 2, 4, 5, 6, 8, 9, 10],
        "torsion mode identity drift",
    )

    impulse_physical = {
        wing: -(
            data[f"Bt_{wing}"] @ BASE_DELTA_TWIST_6[:3]
            + data[f"Br_{wing}"] @ BASE_DELTA_TWIST_6[3:]
        )
        for wing in ("L", "R")
    }
    impulse_modal = {
        wing: physical_modes.T @ impulse_physical[wing] for wing in ("L", "R")
    }

    snapshots: dict[tuple[str, float], dict[str, np.ndarray]] = {}
    references: dict[float, dict[str, dict[str, float]]] = {}
    for tc_ms in WINDOWS_MS:
        references[tc_ms] = {}
        for wing in ("L", "R"):
            solution = closed_form_response(
                eigenvalues, impulse_modal[wing], tc_ms / 1000.0
            )
            snapshots[(wing, tc_ms)] = solution
            references[tc_ms][wing] = response_metrics(
                solution, modal_operators, eigenvalues
            )

    # Current Round3 ROM5, mapped into the full mass-orthonormal modal basis.
    round3_modal_basis = physical_modes.T @ mass @ data["Phi_rom"]
    round3_result = evaluate_basis(
        round3_modal_basis,
        eigenvalues,
        impulse_modal,
        modal_operators,
        references,
    )

    # Favourable 5D weighted-POD exploration.  The entire 75-trial sweep is
    # recorded because alpha and snapshot-wing choice were selected by looking
    # at all five windows.  It is not an independent validation exercise.
    alpha_grid = np.geomspace(0.1, 10.0, 25)
    wing_sets = {"LEFT_ONLY": ("L",), "RIGHT_ONLY": ("R",), "BOTH_WINGS": ("L", "R")}
    weighted_trials: dict[str, list[dict[str, Any]]] = {}
    weighted_candidates: list[tuple[float, str, float, np.ndarray, dict[str, Any]]] = []
    for set_name, wings in wing_sets.items():
        weighted_trials[set_name] = []
        for alpha in alpha_grid:
            basis = weighted_pod_basis_5d(
                snapshots, torsion_indices, wings, float(alpha)
            )
            evaluated = evaluate_basis(
                basis,
                eigenvalues,
                impulse_modal,
                modal_operators,
                references,
            )
            score = float(evaluated["global_max_relative_error"])
            weighted_trials[set_name].append(
                {
                    "alpha": float(alpha),
                    "global_max_relative_error": score,
                    "passes_1pct": score <= RELATIVE_LIMIT,
                }
            )
            weighted_candidates.append((score, set_name, float(alpha), basis, evaluated))
    weighted_candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    best_5_score, best_5_set, best_5_alpha, _best_5_basis, best_5_result = weighted_candidates[0]

    # Hybrid family: retain all three bending eigenvectors and build a torsion
    # mass-POD from LEFT-wing, 10/20/50 ms normalized response snapshots.
    torsion_training = []
    for tc_ms in TRAINING_WINDOWS_MS:
        torsion_training.append(
            normalised_snapshot(
                snapshots[("L", tc_ms)], rows=torsion_indices
            )
        )
    torsion_pod, torsion_singular_values, _ = np.linalg.svd(
        np.hstack(torsion_training), full_matrices=False
    )
    hybrid_sweep: dict[str, Any] = {}
    detailed_hybrid: dict[int, dict[str, Any]] = {}
    for torsion_rank in range(2, 8):
        basis = hybrid_basis(
            bending_indices,
            torsion_indices,
            torsion_pod,
            torsion_rank,
            mass.shape[0],
        )
        evaluated = evaluate_basis(
            basis,
            eigenvalues,
            impulse_modal,
            modal_operators,
            references,
        )
        dimension = 3 + torsion_rank
        hybrid_sweep[str(dimension)] = {
            "dimension": dimension,
            "construction": f"3 bending eigenmodes + {torsion_rank} torsion mass-POD vectors",
            "global_max_relative_error": evaluated["global_max_relative_error"],
            "per_window_max_relative_error": evaluated[
                "per_window_max_relative_error"
            ],
            "governing_cases": evaluated["governing_cases"],
            "passes_1pct_all_windows_wings_metrics": evaluated[
                "passes_1pct_all_windows_wings_metrics"
            ],
        }
        if dimension in (9, 10):
            detailed_hybrid[dimension] = evaluated

    dense_audit = dense_5ms_torsion_audit(
        eigenvalues,
        impulse_modal,
        modal_operators,
        torsion_indices,
        torsion_pod,
    )

    # Fail-closed reproduction checks bind the published headline values to the
    # actual computation.  They are assertions, never replacements for results.
    require(abs(best_5_score - 0.04001049363625929) <= 2.0e-12, "5D result drift")
    require(
        abs(detailed_hybrid[9]["global_max_relative_error"] - 0.013757336666856242)
        <= 2.0e-12,
        "9D result drift",
    )
    require(
        abs(detailed_hybrid[10]["global_max_relative_error"] - 0.0096651825271157)
        <= 2.0e-12,
        "10D result drift",
    )
    require(
        abs(dense_audit["global_dense_relative_peak_error"] - 0.00948126119892961)
        <= 2.0e-12,
        "dense result drift",
    )

    existing_fixed_minimum = existing_multicontact[
        "single_fixed_basis_across_all_windows"
    ]["minimum_passing_dimension_within_first12"]
    require(existing_fixed_minimum == 11, "existing eigen-subset context drift")
    require(
        existing_falsifier["verdict"]
        == "ROM5_FULL_FIELD_TRUNCATION_FALSIFIED_AT_1PCT",
        "falsifier verdict drift",
    )

    result = {
        "schema": "R2_NONMODAL_ROM_EXPLORATION_RESULTS_V1",
        "evidence_id": "CHECKPOINT_A_NONMODAL_ROM_EXPLORATION_V1",
        "evidence_class": "EXPLORATORY_DECISION_SUPPORT_ONLY",
        "technical_verdict": (
            "TESTED_5D_AND_9D_FAMILIES_FAIL__HYBRID_10D_MEETS_INTERNAL_"
            "DISCRETE_AND_5MS_DENSE_CHECKS__NOT_BLIND_VALIDATION__NO_RELEASE_CREDIT"
        ),
        "scope": {
            "purpose": "bounded selection support for a possible future ROM contract revision",
            "mutates_round3_e22_checkpoint_a_terminal": False,
            "round4_generated": False,
            "component_pass_claimed": False,
            "new_rom_emitted": False,
        },
        "source_hashes": source_hashes,
        "method_contract": {
            "hf_dimension": int(mass.shape[0]),
            "stiffness_corner": "NOMINAL_ONLY",
            "damping_ratio": 0.0,
            "eigensolver": "scipy.linalg.eigh(K_nominal, M), ascending",
            "mass_orthogonality_max_abs": modal_mass_orthogonality,
            "base_delta_twist_6": BASE_DELTA_TWIST_6,
            "forcing": "unit-integral half sine, pi/(2*Tc)*sin(pi*t/Tc)",
            "contact_windows_ms": WINDOWS_MS,
            "training_snapshot_windows_ms": TRAINING_WINDOWS_MS,
            "internal_holdout_windows_ms": HOLDOUT_WINDOWS_MS,
            "training_snapshot_wing_for_hybrid": "LEFT_ONLY",
            "right_wing_in_training_for_hybrid": False,
            "contact_samples_inclusive": CONTACT_SAMPLES,
            "post_window_s": POST_WINDOW_S,
            "post_samples_inclusive": POST_SAMPLES,
            "contact_post_duplicate_endpoint_removed": True,
            "snapshot_stride": SNAPSHOT_STRIDE,
            "per_trajectory_snapshot_normalization": "Frobenius norm",
            "metrics": METRIC_NAMES,
            "score": (
                "max over contact windows, LEFT/RIGHT wings, and six metrics of "
                "abs(candidate-HF)/max(abs(HF),1e-14)"
            ),
            "relative_limit": RELATIVE_LIMIT,
        },
        "mode_partition": {
            "criterion": "torsion mass fraction >0.5; bending mass fraction <0.5",
            "bending_indices_0based": bending_indices,
            "torsion_indices_0based": torsion_indices,
            "first_three_bending_indices_0based": bending_indices[:3],
            "first_eight_torsion_indices_0based": torsion_indices[:8],
        },
        "candidate_families_tested": {
            "current_round3_rom5_baseline": {
                "construction": "published three lowest bending + two lowest torsion modes",
                "result": round3_result,
            },
            "weighted_full_state_pod_5d": {
                "construction": (
                    "normalized full modal-displacement snapshots; torsion rows weighted by alpha; "
                    "SVD; inverse weighting; Euclidean QR"
                ),
                "snapshot_wing_sets": wing_sets,
                "alpha_grid": alpha_grid,
                "trial_count": len(weighted_candidates),
                "all_trials": weighted_trials,
                "best_tested_candidate": {
                    "snapshot_wing_set": best_5_set,
                    "alpha": best_5_alpha,
                    "result": best_5_result,
                },
                "selection_disclosure": (
                    "alpha and snapshot-wing set were selected using the same five-window scores; "
                    "this is favourable exploratory selection with validation leakage"
                ),
                "global_optimality_claimed": False,
            },
            "three_bending_plus_torsion_mass_pod": {
                "construction": (
                    "B1/B2/B3 unit eigenvectors plus LEFT-wing Tc=10/20/50 ms torsion-response "
                    "POD vectors"
                ),
                "torsion_singular_values": torsion_singular_values,
                "dimension_sweep_5_to_10": hybrid_sweep,
                "detailed_9d": detailed_hybrid[9],
                "detailed_10d": detailed_hybrid[10],
                "rank_selection_disclosure": (
                    "rank 7 and the hybrid construction were retained after inspecting exploratory "
                    "scores; 5/100 ms are internal holdouts, not blind certification"
                ),
            },
            "existing_first12_eigenmode_subset_context": {
                "source": rel(MULTICONTACT_RESULT_PATH),
                "search_space": "all subsets of first 12 HF eigenmodes",
                "minimum_fixed_dimension_passing_all_five_windows": existing_fixed_minimum,
                "not_recomputed_or_reclassified_here": True,
            },
        },
        "headline_findings": {
            "best_tested_5d_weighted_pod": {
                "global_max_relative_error": best_5_score,
                "percent": 100.0 * best_5_score,
                "limit": RELATIVE_LIMIT,
                "status": "FAIL",
                "snapshot_wing_set": best_5_set,
                "alpha": best_5_alpha,
                "governing_cases": best_5_result["governing_cases"],
            },
            "hybrid_9d_3b_plus_6t_pod": {
                "global_max_relative_error": detailed_hybrid[9][
                    "global_max_relative_error"
                ],
                "percent": 100.0
                * detailed_hybrid[9]["global_max_relative_error"],
                "limit": RELATIVE_LIMIT,
                "status": "FAIL",
                "governing_cases": detailed_hybrid[9]["governing_cases"],
            },
            "hybrid_10d_3b_plus_7t_pod": {
                "global_max_relative_error": detailed_hybrid[10][
                    "global_max_relative_error"
                ],
                "percent": 100.0
                * detailed_hybrid[10]["global_max_relative_error"],
                "limit": RELATIVE_LIMIT,
                "status": "INTERNAL_EXPLORATORY_CHECK_BELOW_LIMIT",
                "governing_cases": detailed_hybrid[10]["governing_cases"],
                "relative_margin_to_limit": RELATIVE_LIMIT
                - detailed_hybrid[10]["global_max_relative_error"],
            },
            "hybrid_10d_5ms_dense_torsion_peak": {
                "global_dense_relative_peak_error": dense_audit[
                    "global_dense_relative_peak_error"
                ],
                "percent": 100.0
                * dense_audit["global_dense_relative_peak_error"],
                "limit": RELATIVE_LIMIT,
                "status": "INTERNAL_EXPLORATORY_CHECK_BELOW_LIMIT",
            },
        },
        "dense_5ms_torsion_audit": dense_audit,
        "negative_controls": {
            "NC01_reduce_torsion_pod_rank_from_7_to_6": {
                "purpose": "prove the scorer detects loss of the marginal torsion state",
                "dimension": 9,
                "global_max_relative_error": detailed_hybrid[9][
                    "global_max_relative_error"
                ],
                "expected": "> 0.01",
                "observed_fail": detailed_hybrid[9][
                    "global_max_relative_error"
                ]
                > RELATIVE_LIMIT,
                "negative_control_pass": detailed_hybrid[9][
                    "global_max_relative_error"
                ]
                > RELATIVE_LIMIT,
            },
            "NC02_synthetic_source_hash_mismatch": {
                "purpose": "confirm the source guard is fail-closed without mutating any file",
                "actual_npz_sha256": digest(NPZ_PATH),
                "synthetic_wrong_expected_sha256": "0"
                + digest(NPZ_PATH)[1:],
                "guard_would_accept": digest(NPZ_PATH)
                == ("0" + digest(NPZ_PATH)[1:]),
                "negative_control_pass": digest(NPZ_PATH)
                != ("0" + digest(NPZ_PATH)[1:]),
            },
        },
        "validation_status": {
            "training_windows": "10/20/50 ms",
            "internal_holdout_windows": "5/100 ms",
            "right_wing_snapshot_holdout": True,
            "rank_and_method_selected_after_exploration": True,
            "blind_validation": False,
            "independent_certification": False,
            "required_future_blind_cases": [
                "new base-delta-twist directions",
                "LOW and HIGH stiffness corners",
                "off-grid contact windows",
                "frozen basis/rank/hash before scoring",
            ],
        },
        "limitations_and_nonclaims": [
            "The examined candidate families do not prove a global minimum over arbitrary Grassmann subspaces.",
            "Failure to find a passing tested 5D basis is not a theorem that every possible 5D basis fails.",
            "The 10D result is an internal exploratory check with a thin margin, not blind validation.",
            "Only nominal stiffness, zero damping, one diagnostic base-delta-twist vector, and the frozen provisional physics are used.",
            "The RIGHT-wing torsion excitation is a sign mirror of LEFT in this model and is not strongly independent data.",
            "The dense audit covers only the governing 5 ms torsion peak; the official grid covers all six metrics.",
            "No component, coupled dynamics, contact, mission, e15, structural qualification, or flight conclusion is upgraded.",
            "No Round4 or replacement ROM artifact is generated.",
            "Round3, E22, Checkpoint-A, terminal packs, and their gates remain unchanged.",
        ],
        "governance": {
            "owner_accepted": False,
            "owner_acceptance": False,
            "release_credit": False,
            "component_gate_pass": False,
            "round4_generated": False,
            "e15_inherited": False,
            "e15_status_changed": False,
            "next_stage_authorized": False,
            "flight_qualified": False,
            "terminal_release": False,
            "review_status": "PENDING_OWNER_REVIEW",
        },
    }
    write_json(OUT_PATH, result)
    print(
        json.dumps(
            {
                "evidence_class": result["evidence_class"],
                "best_tested_5d_percent": 100.0 * best_5_score,
                "hybrid_9d_percent": 100.0
                * detailed_hybrid[9]["global_max_relative_error"],
                "hybrid_10d_percent": 100.0
                * detailed_hybrid[10]["global_max_relative_error"],
                "dense_5ms_percent": 100.0
                * dense_audit["global_dense_relative_peak_error"],
                "output_sha256": digest(OUT_PATH),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
