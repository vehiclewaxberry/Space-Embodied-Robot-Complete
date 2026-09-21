#!/usr/bin/env python3
"""Independent key-result recompute for the nonmodal ROM exploration.

This file intentionally does not import the primary recompute module.  It
duplicates the minimum algebra needed to reconstruct the selected 5D, hybrid
9D/10D, and dense 5 ms results from the frozen NPZ and semantics contract.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.linalg import eigh


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[5]
ROUND3 = HERE.parents[2] / "round3_hf_rom_v2"
NPZ_PATH = ROUND3 / "R2_HF_ROM_NUMERICAL_DATA_V2.npz"
CONTRACT_PATH = ROUND3 / "R2_FIVE_MODE_ROM_V2.json"
RESULT_PATH = HERE / "R2_NONMODAL_ROM_EXPLORATION_RESULTS_V1.json"
OUT_PATH = HERE / "INDEPENDENT_RECOMPUTE_V1.json"

EXPECTED_NPZ = "8D10E085385EDF2FACE92B9B48D1172939A31FD3B57E55242ED11C9EEEDF50DA"
EXPECTED_CONTRACT = "9E4FE903AE7E34584F39F16275EF20FC31831AFB7F78B3B625418B86D0FBC817"
TWIST = np.asarray(
    [
        -0.009692455771418815,
        0.0038929116736479714,
        -0.0020413946008322834,
        -0.04501982207187775,
        -0.0015129575188143466,
        0.02812660573609509,
    ]
)
WINDOWS_MS = (5.0, 10.0, 20.0, 50.0, 100.0)
TRAIN_MS = (10.0, 20.0, 50.0)
N_CONTACT = 401
N_POST = 5001
POST_S = 5.0
LIMIT = 0.01
FLOOR = 1.0e-14
METRICS = (
    "tip_peak_m",
    "node_peak_m",
    "slope_peak_rad",
    "hinge_peak_rad",
    "torsion_peak_rad",
    "modal_energy_peak_J",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(f"INDEPENDENT_RECOMPUTE_FAIL_CLOSED:{message}")


def row(n: int, i: int) -> np.ndarray:
    answer = np.zeros(n)
    answer[int(i)] = 1.0
    return answer


def operators_from_semantics(contract: dict[str, Any]) -> dict[str, np.ndarray]:
    semantics = contract["reduced_hf_dof_semantics"]
    n = len(semantics)
    w = sorted(
        (x for x in semantics if x["kind"] == "TRANSVERSE_W"),
        key=lambda x: int(x["node"]),
    )
    theta = sorted(
        (x for x in semantics if x["kind"] == "BENDING_SLOPE_THETA"),
        key=lambda x: (int(x["node"]), str(x["side"])),
    )
    torsion = sorted(
        (x for x in semantics if x["kind"] == "TORSION_PHI"),
        key=lambda x: int(x["node"]),
    )
    rw = np.vstack([np.zeros(n)] + [row(n, x["reduced_index_0based"]) for x in w])
    rt = np.vstack(
        [np.zeros(n)] + [row(n, x["reduced_index_0based"]) for x in torsion]
    )
    rtheta = np.vstack([row(n, x["reduced_index_0based"]) for x in theta])
    grouped: dict[int, list[dict[str, Any]]] = {}
    for item in theta:
        grouped.setdefault(int(item["node"]), []).append(item)
    hinge = [row(n, grouped[0][0]["reduced_index_0based"])]
    for node in sorted(
        key
        for key, values in grouped.items()
        if {str(value["side"]) for value in values} == {"L", "R"}
    ):
        left = next(value for value in grouped[node] if value["side"] == "L")
        right = next(value for value in grouped[node] if value["side"] == "R")
        hinge.append(
            row(n, right["reduced_index_0based"])
            - row(n, left["reduced_index_0based"])
        )
    return {
        "tip_w": rw[-1:, :],
        "w_nodes": rw,
        "theta_dofs": rtheta,
        "hinge_relative": np.vstack(hinge),
        "torsion_nodes": rt,
    }


def response(lam: np.ndarray, b: np.ndarray, tc_s: float) -> dict[str, np.ndarray]:
    omega = np.sqrt(lam)
    pulse_omega = math.pi / tc_s
    p = b * math.pi / (2.0 * tc_s) / (lam - pulse_omega**2)
    h = -p * pulse_omega / omega
    tc = np.linspace(0.0, tc_s, N_CONTACT)[None, :]
    yc = p[:, None] * np.sin(pulse_omega * tc) + h[:, None] * np.sin(
        omega[:, None] * tc
    )
    vc = p[:, None] * pulse_omega * np.cos(pulse_omega * tc) + h[:, None] * omega[:, None] * np.cos(
        omega[:, None] * tc
    )
    tp = np.linspace(0.0, POST_S, N_POST)[None, :]
    ye = yc[:, -1]
    ve = vc[:, -1]
    yp = ye[:, None] * np.cos(omega[:, None] * tp) + ve[:, None] / omega[:, None] * np.sin(
        omega[:, None] * tp
    )
    vp = -ye[:, None] * omega[:, None] * np.sin(omega[:, None] * tp) + ve[:, None] * np.cos(
        omega[:, None] * tp
    )
    return {
        "y": np.hstack([yc, yp[:, 1:]]),
        "v": np.hstack([vc, vp[:, 1:]]),
        "yc": yc,
        "ye": ye,
        "ve": ve,
    }


def metric_values(
    state: dict[str, np.ndarray], ops: dict[str, np.ndarray], lam: np.ndarray
) -> dict[str, float]:
    out = {name: op @ state["y"] for name, op in ops.items()}
    energy = 0.5 * np.sum(
        state["v"] ** 2 + lam[:, None] * state["y"] ** 2, axis=0
    )
    return {
        "tip_peak_m": float(np.max(np.abs(out["tip_w"]))),
        "node_peak_m": float(np.max(np.abs(out["w_nodes"]))),
        "slope_peak_rad": float(np.max(np.abs(out["theta_dofs"]))),
        "hinge_peak_rad": float(np.max(np.abs(out["hinge_relative"]))),
        "torsion_peak_rad": float(np.max(np.abs(out["torsion_nodes"]))),
        "modal_energy_peak_J": float(np.max(energy)),
    }


def evaluate(
    w: np.ndarray,
    lam: np.ndarray,
    impulses: dict[str, np.ndarray],
    ops: dict[str, np.ndarray],
    refs: dict[tuple[float, str], dict[str, float]],
) -> dict[str, Any]:
    kr = w.T @ (lam[:, None] * w)
    lr, vr = np.linalg.eigh(kr)
    transform = w @ vr
    rops = {name: op @ transform for name, op in ops.items()}
    by_window = {}
    flat = {}
    for tc_ms in WINDOWS_MS:
        for wing in ("L", "R"):
            candidate = metric_values(
                response(lr, transform.T @ impulses[wing], tc_ms / 1000.0),
                rops,
                lr,
            )
            for metric in METRICS:
                error = abs(candidate[metric] - refs[(tc_ms, wing)][metric]) / max(
                    abs(refs[(tc_ms, wing)][metric]), FLOOR
                )
                flat[f"TC_{tc_ms:g}MS_{wing}_{metric}"] = error
        by_window[f"TC_{tc_ms:g}MS"] = max(
            value
            for key, value in flat.items()
            if key.startswith(f"TC_{tc_ms:g}MS_")
        )
    maximum = max(flat.values())
    return {
        "global_max_relative_error": maximum,
        "per_window_max_relative_error": by_window,
        "governing_cases": sorted(
            key for key, value in flat.items() if abs(value - maximum) <= 1.0e-13
        ),
    }


def dense_peak(
    lam: np.ndarray, ye: np.ndarray, ve: np.ndarray, op: np.ndarray
) -> dict[str, Any]:
    omega = np.sqrt(lam)
    best = (-1.0, -1, 0.0)
    for start in np.arange(0.0, POST_S, 0.1):
        stop = min(POST_S, start + 0.1)
        t = np.arange(start, stop + 0.5e-5, 1.0e-5)
        y = ye[:, None] * np.cos(omega[:, None] * t[None, :]) + ve[:, None] / omega[:, None] * np.sin(
            omega[:, None] * t[None, :]
        )
        values = op @ y
        index = np.unravel_index(np.argmax(np.abs(values)), values.shape)
        candidate = float(abs(values[index]))
        if candidate > best[0]:
            best = (candidate, int(index[0]), float(t[index[1]]))
    t = np.arange(max(0.0, best[2] - 1.0e-4), min(POST_S, best[2] + 1.0e-4) + 0.5e-7, 1.0e-7)
    y = ye[:, None] * np.cos(omega[:, None] * t[None, :]) + ve[:, None] / omega[:, None] * np.sin(
        omega[:, None] * t[None, :]
    )
    values = op @ y
    index = np.unravel_index(np.argmax(np.abs(values)), values.shape)
    return {
        "peak_rad": float(abs(values[index])),
        "row_0based": int(index[0]),
        "post_tau_s": float(t[index[1]]),
    }


def main() -> None:
    require(sha(NPZ_PATH) == EXPECTED_NPZ, "NPZ hash drift")
    require(sha(CONTRACT_PATH) == EXPECTED_CONTRACT, "contract hash drift")
    declared = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    require(
        declared["evidence_class"] == "EXPLORATORY_DECISION_SUPPORT_ONLY",
        "evidence class drift",
    )
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    with np.load(NPZ_PATH) as archive:
        data = {name: archive[name] for name in archive.files}

    m = data["M"]
    lam, u = eigh(data["K_nominal"], m)
    physical_ops = operators_from_semantics(contract)
    ops = {name: op @ u for name, op in physical_ops.items()}
    semantics = contract["reduced_hf_dof_semantics"]
    torsion_dofs = np.asarray(
        [
            int(item["reduced_index_0based"])
            for item in semantics
            if item["kind"] == "TORSION_PHI"
        ]
    )
    mtt = m[np.ix_(torsion_dofs, torsion_dofs)]
    fraction = np.asarray(
        [u[torsion_dofs, i] @ mtt @ u[torsion_dofs, i] for i in range(u.shape[1])]
    )
    ti = np.flatnonzero(fraction > 0.5)
    bi = np.flatnonzero(fraction < 0.5)
    require(bi[:3].tolist() == [0, 3, 7], "bending identity drift")

    b = {
        wing: u.T
        @ -(
            data[f"Bt_{wing}"] @ TWIST[:3]
            + data[f"Br_{wing}"] @ TWIST[3:]
        )
        for wing in ("L", "R")
    }
    states: dict[tuple[float, str], dict[str, np.ndarray]] = {}
    refs = {}
    for tc_ms in WINDOWS_MS:
        for wing in ("L", "R"):
            state = response(lam, b[wing], tc_ms / 1000.0)
            states[(tc_ms, wing)] = state
            refs[(tc_ms, wing)] = metric_values(state, ops, lam)

    alpha = float(
        declared["headline_findings"]["best_tested_5d_weighted_pod"]["alpha"]
    )
    require(
        declared["headline_findings"]["best_tested_5d_weighted_pod"][
            "snapshot_wing_set"
        ]
        == "LEFT_ONLY",
        "selected 5D snapshot set drift",
    )
    weighted = []
    torsion_train = []
    for tc_ms in TRAIN_MS:
        full = states[(tc_ms, "L")]["y"][:, ::5].copy()
        full /= np.linalg.norm(full, "fro")
        full[ti, :] *= alpha
        weighted.append(full)
        torsion = states[(tc_ms, "L")]["y"][ti, ::5].copy()
        torsion /= np.linalg.norm(torsion, "fro")
        torsion_train.append(torsion)
    uw = np.linalg.svd(np.hstack(weighted), full_matrices=False)[0][:, :5]
    uw[ti, :] /= alpha
    w5 = np.linalg.qr(uw)[0][:, :5]
    five = evaluate(w5, lam, b, ops, refs)

    pt = np.linalg.svd(np.hstack(torsion_train), full_matrices=False)[0]
    hybrid = {}
    for rank in (6, 7):
        w = np.zeros((len(lam), 3 + rank))
        w[bi[:3], np.arange(3)] = 1.0
        w[np.ix_(ti, np.arange(3, 3 + rank))] = pt[:, :rank]
        hybrid[3 + rank] = evaluate(w, lam, b, ops, refs)

    lam_t = lam[ti]
    op_t = ops["torsion_nodes"][:, ti]
    pt7 = pt[:, :7]
    kr = pt7.T @ (lam_t[:, None] * pt7)
    lr, vr = np.linalg.eigh(kr)
    dense_per_wing = {}
    for wing in ("L", "R"):
        hf_contact = response(lam_t, b[wing][ti], 0.005)
        rom_contact = response(lr, vr.T @ pt7.T @ b[wing][ti], 0.005)
        hf = dense_peak(lam_t, hf_contact["ye"], hf_contact["ve"], op_t)
        rom = dense_peak(
            lr,
            rom_contact["ye"],
            rom_contact["ve"],
            op_t @ pt7 @ vr,
        )
        dense_per_wing[wing] = {
            "hf": hf,
            "rom": rom,
            "relative_error": abs(rom["peak_rad"] - hf["peak_rad"])
            / max(abs(hf["peak_rad"]), FLOOR),
        }
    dense_error = max(item["relative_error"] for item in dense_per_wing.values())

    comparisons = {
        "best_tested_5d": {
            "declared": declared["headline_findings"][
                "best_tested_5d_weighted_pod"
            ]["global_max_relative_error"],
            "recomputed": five["global_max_relative_error"],
        },
        "hybrid_9d": {
            "declared": declared["headline_findings"][
                "hybrid_9d_3b_plus_6t_pod"
            ]["global_max_relative_error"],
            "recomputed": hybrid[9]["global_max_relative_error"],
        },
        "hybrid_10d": {
            "declared": declared["headline_findings"][
                "hybrid_10d_3b_plus_7t_pod"
            ]["global_max_relative_error"],
            "recomputed": hybrid[10]["global_max_relative_error"],
        },
        "dense_5ms": {
            "declared": declared["headline_findings"][
                "hybrid_10d_5ms_dense_torsion_peak"
            ]["global_dense_relative_peak_error"],
            "recomputed": dense_error,
        },
    }
    tolerance = 2.0e-12
    for comparison in comparisons.values():
        comparison["absolute_difference"] = abs(
            comparison["declared"] - comparison["recomputed"]
        )
        comparison["within_tolerance"] = (
            comparison["absolute_difference"] <= tolerance
        )
        require(comparison["within_tolerance"], "declared key result mismatch")

    require(hybrid[9]["global_max_relative_error"] > LIMIT, "rank-6 negative control did not fail")
    require(hybrid[10]["global_max_relative_error"] <= LIMIT, "rank-7 exploratory score drift")
    require(dense_error <= LIMIT, "dense exploratory score drift")

    output = {
        "schema": "R2_NONMODAL_ROM_EXPLORATION_INDEPENDENT_RECOMPUTE_V1",
        "evidence_class": "EXPLORATORY_DECISION_SUPPORT_ONLY",
        "verdict": "INDEPENDENT_KEY_RESULT_RECOMPUTE_PASS_WITH_EXPLORATORY_SCOPE",
        "independence_statement": (
            "No import from recompute_nonmodal_rom_exploration.py; algebra is independently duplicated."
        ),
        "source_hashes": {
            relative(NPZ_PATH): sha(NPZ_PATH),
            relative(CONTRACT_PATH): sha(CONTRACT_PATH),
            relative(RESULT_PATH): sha(RESULT_PATH),
        },
        "comparison_tolerance_absolute": tolerance,
        "comparisons": comparisons,
        "per_window_recompute": {
            "best_tested_5d": five["per_window_max_relative_error"],
            "hybrid_9d": hybrid[9]["per_window_max_relative_error"],
            "hybrid_10d": hybrid[10]["per_window_max_relative_error"],
        },
        "dense_5ms_per_wing": dense_per_wing,
        "negative_control": {
            "name": "remove seventh torsion POD vector",
            "rank6_9d_error": hybrid[9]["global_max_relative_error"],
            "expected_fail_above_1pct": True,
            "observed_fail": hybrid[9]["global_max_relative_error"] > LIMIT,
            "negative_control_pass": hybrid[9]["global_max_relative_error"] > LIMIT,
        },
        "all_comparisons_pass": all(
            item["within_tolerance"] for item in comparisons.values()
        ),
        "owner_accepted": False,
        "release_credit": False,
        "component_gate_pass": False,
        "round4_generated": False,
        "e15_inherited": False,
        "next_stage_authorized": False,
    }
    OUT_PATH.write_text(
        json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "verdict": output["verdict"],
                "all_comparisons_pass": output["all_comparisons_pass"],
                "output_sha256": sha(OUT_PATH),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
