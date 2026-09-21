#!/usr/bin/env python3
"""Search a single HF-eigenmode ROM basis across the full 5--100 ms window.

This is decision support only.  It does not modify Round3/E22, change the
ODR-21/ODR-32 3--5 mode contract, or authorize a new ROM.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[4]
REDTEAM = HERE.parent / "red_team"
ROUND3 = HERE.parents[1] / "round3_hf_rom_v2"
NPZ_PATH = ROUND3 / "R2_HF_ROM_NUMERICAL_DATA_V2.npz"
CONTRACT_PATH = ROUND3 / "R2_FIVE_MODE_ROM_V2.json"
FALSIFIER_PATH = REDTEAM / "recompute_rom5_dimension_falsifier.py"
OUT_PATH = HERE / "MULTICONTACT_ROM_DIMENSION_DECISION_SUPPORT_V1.json"

EXPECTED = {
    NPZ_PATH: "8D10E085385EDF2FACE92B9B48D1172939A31FD3B57E55242ED11C9EEEDF50DA",
    CONTRACT_PATH: "9E4FE903AE7E34584F39F16275EF20FC31831AFB7F78B3B625418B86D0FBC817",
    FALSIFIER_PATH: "2CEEA915A5A4B0D29891DA96FEA21816E855C4D380A2692BB526369E41E5C3EC",
}

sys.path.insert(0, str(REDTEAM))
import recompute_rom5_dimension_falsifier as base  # noqa: E402


WINDOWS_MS = (5.0, 10.0, 20.0, 50.0, 100.0)
FIRST_N_POOL = 12
LIMIT = 0.01


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(f"MULTICONTACT_ROM_SEARCH_FAIL_CLOSED:{message}")


def jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def main() -> None:
    source_hashes = {}
    for path, expected in EXPECTED.items():
        actual = digest(path)
        require(actual == expected, f"source hash drift:{rel(path)}")
        source_hashes[rel(path)] = actual

    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    with np.load(NPZ_PATH) as archive:
        data = {name: archive[name] for name in archive.files}

    mass = data["M"]
    stiffness = data["K_nominal"]
    operators = base.reconstruct_hf_operators(contract)
    eigvals, eigvecs = base.eigh(stiffness, mass)
    omega = np.sqrt(eigvals)
    semantics = contract["reduced_hf_dof_semantics"]
    torsion_dofs = np.asarray([
        int(item["reduced_index_0based"])
        for item in semantics
        if item["kind"] == "TORSION_PHI"
    ])
    families, torsion_fractions = base.mode_families(mass, eigvecs, torsion_dofs)
    pool = tuple(range(FIRST_N_POOL))
    bending = tuple(index for index in pool if families[index] == "BENDING")
    torsion = tuple(index for index in pool if families[index] == "TORSION")
    require(len(bending) == 3, f"expected three bending modes in first12, got {len(bending)}")

    family_counter = {"BENDING": 0, "TORSION": 0}
    labels: dict[int, str] = {}
    inventory = []
    for index in pool:
        family_counter[families[index]] += 1
        labels[index] = ("B" if families[index] == "BENDING" else "T") + str(
            family_counter[families[index]])
        inventory.append({
            "hf_index_0based": index,
            "label": labels[index],
            "family": families[index],
            "frequency_hz": float(omega[index] / (2.0 * math.pi)),
            "torsion_mass_fraction": float(torsion_fractions[index]),
        })

    phi = data["Phi_rom"]
    mac = np.abs(eigvecs.T @ mass @ phi)
    round3_indices = tuple(sorted(int(np.argmax(mac[:, col])) for col in range(phi.shape[1])))
    require(len(set(round3_indices)) == 5, "Round3 mode mapping is not one-to-one")

    impulse = {
        wing: -(
            data[f"Bt_{wing}"] @ base.BASE_DELTA_TWIST_6[:3]
            + data[f"Br_{wing}"] @ base.BASE_DELTA_TWIST_6[3:]
        )
        for wing in ("L", "R")
    }
    bending_position = {mode: pos for pos, mode in enumerate(bending)}
    torsion_position = {mode: pos for pos, mode in enumerate(torsion)}
    bending_ops = {key: value for key, value in operators.items() if key != "torsion_nodes"}

    # Keep the complete score for every subset/window so the final fixed-basis
    # search is the max over all five contact windows, not a union of local optima.
    all_scores: dict[float, dict[tuple[int, ...], dict[str, Any]]] = {}
    per_window = {}

    for tc_ms in WINDOWS_MS:
        tc_s = tc_ms / 1000.0
        t_contact, t_post = base.time_grids(tc_s)
        solutions = {}
        references = {}
        bending_cache: dict[str, dict[int, dict[str, float]]] = {"L": {}, "R": {}}
        torsion_cache: dict[str, dict[int, float]] = {"L": {}, "R": {}}
        energy_final = {}

        for wing in ("L", "R"):
            solution = base.modal_half_sine(
                mass, stiffness, impulse[wing], tc_s, t_contact, t_post
            )
            solutions[wing] = solution
            references[wing] = base.response_metrics(solution, operators)
            energy_final[wing] = 0.5 * (
                solution["yd"][:, -1] ** 2
                + solution["eigenvalues"] * solution["y"][:, -1] ** 2
            )
            for mask in range(1 << len(bending)):
                selected = [mode for pos, mode in enumerate(bending) if (mask >> pos) & 1]
                bending_cache[wing][mask] = {
                    name: (
                        float(np.max(np.abs(op @ eigvecs[:, selected] @ solution["y"][selected])))
                        if selected else 0.0
                    )
                    for name, op in bending_ops.items()
                }
            for mask in range(1 << len(torsion)):
                selected = [mode for pos, mode in enumerate(torsion) if (mask >> pos) & 1]
                torsion_cache[wing][mask] = (
                    float(np.max(np.abs(
                        operators["torsion_nodes"] @ eigvecs[:, selected] @ solution["y"][selected]
                    ))) if selected else 0.0
                )

        def score(selected: tuple[int, ...]) -> dict[str, Any]:
            bmask = sum(1 << bending_position[index] for index in selected if index in bending_position)
            tmask = sum(1 << torsion_position[index] for index in selected if index in torsion_position)
            errors_flat = {}
            per_wing = {}
            for wing in ("L", "R"):
                candidate = {
                    "tip_peak_m": bending_cache[wing][bmask]["tip_w"],
                    "node_peak_m": bending_cache[wing][bmask]["w_nodes"],
                    "slope_peak_rad": bending_cache[wing][bmask]["theta_dofs"],
                    "hinge_peak_rad": bending_cache[wing][bmask]["hinge_relative"],
                    "torsion_peak_rad": torsion_cache[wing][tmask],
                    "modal_energy_peak_J": float(np.sum(energy_final[wing][list(selected)])),
                }
                reference = {key: references[wing][key] for key in candidate}
                errors = base.relative_errors(candidate, reference)
                per_wing[wing] = errors
                errors_flat.update({f"{wing}_{key}": value for key, value in errors.items()})
            maximum = max(errors_flat.values())
            return {
                "hf_indices_0based": list(selected),
                "labels": [labels[index] for index in selected],
                "bending_mode_count": sum(families[index] == "BENDING" for index in selected),
                "torsion_mode_count": sum(families[index] == "TORSION" for index in selected),
                "global_max_relative_error": maximum,
                "governing_metrics": sorted(
                    key for key, value in errors_flat.items()
                    if abs(value - maximum) <= 1.0e-14
                ),
                "passes_1pct": maximum <= LIMIT,
                "per_wing_relative_errors": per_wing,
            }

        scores = {}
        best_by_dimension = {}
        for dimension in range(1, FIRST_N_POOL + 1):
            candidates = []
            for selected in itertools.combinations(pool, dimension):
                result = score(selected)
                scores[selected] = result
                candidates.append(result)
            best_by_dimension[dimension] = min(
                candidates, key=lambda item: item["global_max_relative_error"]
            )
        all_scores[tc_ms] = scores
        minimum = next((d for d in range(1, 13) if best_by_dimension[d]["passes_1pct"]), None)
        preserve = {
            d: min(
                (result for selected, result in scores.items()
                 if len(selected) == d and set(bending).issubset(selected)),
                key=lambda item: item["global_max_relative_error"],
            )
            for d in range(len(bending), 13)
        }
        minimum_preserve = next((d for d in range(len(bending), 13) if preserve[d]["passes_1pct"]), None)
        per_window[f"TC_{tc_ms:g}MS"] = {
            "Tc_ms": tc_ms,
            "half_sine_spectral_center_hz": 1.0 / (2.0 * tc_s),
            "round3_rom5": scores[round3_indices],
            "best_5D": best_by_dimension[5],
            "minimum_passing_dimension_within_first12": minimum,
            "minimum_passing_subset": None if minimum is None else best_by_dimension[minimum],
            "minimum_passing_dimension_preserving_three_bending": minimum_preserve,
            "minimum_passing_subset_preserving_three_bending": (
                None if minimum_preserve is None else preserve[minimum_preserve]
            ),
        }

    fixed_best_by_dimension = {}
    for dimension in range(1, 13):
        candidates = []
        for selected in itertools.combinations(pool, dimension):
            window_errors = {
                f"TC_{tc_ms:g}MS": all_scores[tc_ms][selected]["global_max_relative_error"]
                for tc_ms in WINDOWS_MS
            }
            maximum = max(window_errors.values())
            candidates.append({
                "hf_indices_0based": list(selected),
                "labels": [labels[index] for index in selected],
                "bending_mode_count": sum(families[index] == "BENDING" for index in selected),
                "torsion_mode_count": sum(families[index] == "TORSION" for index in selected),
                "per_window_max_relative_error": window_errors,
                "global_max_relative_error_across_windows": maximum,
                "governing_windows": sorted(
                    name for name, value in window_errors.items()
                    if abs(value - maximum) <= 1.0e-14
                ),
                "passes_1pct_all_windows": maximum <= LIMIT,
            })
        fixed_best_by_dimension[dimension] = min(
            candidates, key=lambda item: item["global_max_relative_error_across_windows"]
        )

    fixed_minimum = next(
        (d for d in range(1, 13) if fixed_best_by_dimension[d]["passes_1pct_all_windows"]),
        None,
    )
    fixed_preserve = {
        d: min(
            (item for item in (
                {
                    "selected": selected,
                    "result": {
                        "hf_indices_0based": list(selected),
                        "labels": [labels[index] for index in selected],
                        "per_window_max_relative_error": {
                            f"TC_{tc_ms:g}MS": all_scores[tc_ms][selected]["global_max_relative_error"]
                            for tc_ms in WINDOWS_MS
                        },
                    },
                }
                for selected in itertools.combinations(pool, d)
                if set(bending).issubset(selected)
            )),
             key=lambda entry: max(entry["result"]["per_window_max_relative_error"].values()))
        for d in range(3, 13)
    }
    fixed_preserve_summary = {}
    for dimension, entry in fixed_preserve.items():
        result = entry["result"]
        maximum = max(result["per_window_max_relative_error"].values())
        result["global_max_relative_error_across_windows"] = maximum
        result["passes_1pct_all_windows"] = maximum <= LIMIT
        fixed_preserve_summary[dimension] = result
    fixed_minimum_preserve = next(
        (d for d in range(3, 13) if fixed_preserve_summary[d]["passes_1pct_all_windows"]),
        None,
    )

    payload = {
        "schema": "MULTICONTACT_ROM_DIMENSION_DECISION_SUPPORT_V1",
        "evidence_class": "DIAGNOSTIC_DECISION_SUPPORT_ONLY",
        "technical_verdict": (
            "FIXED_BASIS_DIMENSION_IDENTIFIED_WITHIN_FIRST12"
            if fixed_minimum is not None
            else "NO_FIXED_BASIS_WITHIN_FIRST12_PASSES_ALL_WINDOWS"
        ),
        "source_hashes": source_hashes,
        "input_contract": {
            "contact_windows_ms": list(WINDOWS_MS),
            "post_window_s": base.POST_WINDOW_S,
            "relative_limit": LIMIT,
            "metrics": [
                "tip_peak_m", "node_peak_m", "slope_peak_rad", "hinge_peak_rad",
                "torsion_peak_rad", "modal_energy_peak_J",
            ],
            "score": "max over LEFT/RIGHT, metrics, and claimed contact windows",
            "candidate_pool": "all subsets of first 12 nominal HF eigenmodes",
            "base_delta_twist_6": base.BASE_DELTA_TWIST_6,
            "damping_ratio": 0.0,
        },
        "mode_inventory_first12": inventory,
        "round3_mapping": {
            "hf_indices_0based": list(round3_indices),
            "labels": [labels[index] for index in round3_indices],
        },
        "per_window": per_window,
        "single_fixed_basis_across_all_windows": {
            "best_by_dimension_1_to_12": {
                str(d): fixed_best_by_dimension[d] for d in range(1, 13)
            },
            "minimum_passing_dimension_within_first12": fixed_minimum,
            "minimum_passing_subset": (
                None if fixed_minimum is None else fixed_best_by_dimension[fixed_minimum]
            ),
            "minimum_passing_dimension_preserving_three_bending": fixed_minimum_preserve,
            "minimum_passing_subset_preserving_three_bending": (
                None if fixed_minimum_preserve is None
                else fixed_preserve_summary[fixed_minimum_preserve]
            ),
        },
        "contract_effect": {
            "current_owner_contract": "ODR-21 and ODR-32: 3-5 dominant modes per wing",
            "current_contract_changed": False,
            "new_rom_authorized": False,
            "recommended_decision_form": (
                "replace a fixed 3-5 ceiling with a validation-selected dimension and bind "
                "the released ROM to an explicit contact-window validity envelope"
            ),
        },
        "nonclaims": [
            "This diagnostic does not authorize or emit a replacement ROM.",
            "The search is over HF eigenmode subsets only, not arbitrary nonmodal or balanced bases.",
            "The diagnostic base delta twist is not granted coupled-scenario authority here.",
            "No e15 inheritance, mission release, flight qualification, or Owner acceptance is claimed.",
        ],
        "owner_accepted": False,
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    OUT_PATH.write_text(
        json.dumps(jsonable(payload), indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "technical_verdict": payload["technical_verdict"],
        "minimum_fixed_dimension_all_windows": fixed_minimum,
        "minimum_fixed_dimension_all_windows_preserving_three_bending": fixed_minimum_preserve,
        "output_sha256": digest(OUT_PATH),
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
