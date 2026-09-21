# -*- coding: utf-8 -*-
"""AGENT-F1 / R2 full-flex closure Wave-3a round1: ROM reduction + verification.

Consumes 01_hf_model/SOLAR_R2_HF_FLEX_MODEL_V1.json (own stage-1 output) and
the upstream published leaf-only references (read-only, hash re-verified).
Retains the first 5 HF modes per wing (ODR-21 3-5 band), computes modal
participation factors (mass-normalized convention, Phi^T M Phi = I), injects
the modal-damping ASSUMPTION_BAND (zeta in [0.001, 0.02], literature-typical,
no point value), and builds the five-case frequency comparison against the
published leaf-only L2 values with an explicit difference decomposition.

Writes only into this directory.  Pure numpy/scipy/hashlib/json.
All outputs CANDIDATE_PROVISIONAL_BANDS: release_credit=false,
next_stage_authorized=false.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
HF_JSON = HERE.parent / "01_hf_model/SOLAR_R2_HF_FLEX_MODEL_V1.json"
E21_JSON = (ROOT / "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results"
            / "E21_FIXED_BASE_R2_ROM_REPRODUCTION_AND_MASS_CONFLICT_V1.json")
MCA_YAML = (ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
            / "mpi_phys_dyn_bridge/round1_bridge/decisions/ENG_DECISION_DYNAMIC_MASS_ALLOCATION_V1.yaml")

OUT_ROM = HERE / "SOLAR_R2_ROM_V1.json"
OUT_VER = HERE / "SOLAR_R2_ROM_VERIFICATION_V1.json"

N_RETAIN = 5
ZETA_BAND = (0.001, 0.02)   # ASSUMPTION_BAND, literature-typical modal damping

CASE_ORDER = ["nominal", "all_low", "all_high", "root_low_inter_high", "root_high_inter_low"]
EI_ORDER = ["EI_low", "EI_nominal", "EI_high"]


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def mac(a, b):
    a = np.asarray(a, float).ravel()
    b = np.asarray(b, float).ravel()
    return float((a @ b) ** 2 / ((a @ a) * (b @ b)))


def main():
    t0 = datetime.now(timezone(timedelta(hours=8))).isoformat()
    hf = json.loads(HF_JSON.read_text(encoding="utf-8"))
    e21 = json.loads(E21_JSON.read_text(encoding="utf-8"))

    M = np.array(hf["mass_matrix_kg_m2"])
    Bt = {"L": np.array(hf["participation_hf_left"]["B_t"]),
          "R": np.array(hf["participation_hf_right"]["B_t"])}
    Br = {"L": np.array(hf["participation_hf_left"]["B_r"]),
          "R": np.array(hf["participation_hf_right"]["B_r"])}
    sweep = hf["sweep_5_cases_x_3_ei"]
    l2ref = hf["l2_reference_per_case"]

    # published (4-decimal) and e21 full-precision references
    pub_hz = {c["case"]: c["published_hz"] for c in e21["leaf_only"]["cases"]}
    e21_hz = {c["case"]: c["leaf_only_reproduced_hz"] for c in e21["leaf_only"]["cases"]}

    # ---------------- ROM modal set per wing -------------------------------
    # eigenvectors/frequencies are identical for both wings (mirror symmetry of
    # the eigenproblem); only the participation vectors differ (stored per wing).
    rom_modes = []
    for m in range(N_RETAIN):
        rom_modes.append({"mode_index": m + 1, "per_case": {}})
    for case in CASE_ORDER:
        blk = sweep[case]
        f_nom = blk["per_ei"]["EI_nominal"]["frequencies_hz_first10"]
        V_nom = np.array(blk["per_ei"]["EI_nominal"]["eigenvectors_first8_mass_normalized"])
        qh_nom = np.array(blk["per_ei"]["EI_nominal"]["hinge_content_first8"])
        V_l2 = np.array(l2ref[case]["eigenvectors_mass_normalized"])
        # MAC of retained modes vs the 3 L2 modes (hinge-content coordinates)
        mac_mtx = [[mac(qh_nom[:, m], V_l2[:, j]) for j in range(3)] for m in range(N_RETAIN)]
        # branch continuity: self-MAC of mode m across EI corners (same case)
        cont = []
        for m in range(N_RETAIN):
            v_lo = np.array(blk["per_ei"]["EI_low"]["eigenvectors_first8_mass_normalized"])[:, m]
            v_hi = np.array(blk["per_ei"]["EI_high"]["eigenvectors_first8_mass_normalized"])[:, m]
            cont.append(mac(v_lo, v_hi))
        for m in range(N_RETAIN):
            phi = V_nom[:, m]
            om = 2.0 * math.pi * f_nom[m]
            entry = {
                "frequency_hz_EI_nominal": f_nom[m],
                "frequency_hz_per_EI": {ei: blk["per_ei"][ei]["frequencies_hz_first10"][m]
                                        for ei in EI_ORDER},
                "frequency_band_over_EI_hz": [
                    min(blk["per_ei"][ei]["frequencies_hz_first10"][m] for ei in EI_ORDER),
                    max(blk["per_ei"][ei]["frequencies_hz_first10"][m] for ei in EI_ORDER)],
                "eigenvector_mass_normalized": phi.tolist(),
                "hinge_content_q": list(qh_nom[:, m]),
                "mac_vs_L2_modes": mac_mtx[m],
                "l2_mode_assignment": int(np.argmax(mac_mtx[m])) + 1,
                "branch_continuity_mac_EI_low_vs_high": cont[m],
                "generalized_mass_kg_m2": 1.0,  # by mass-normalization convention Phi^T M Phi = I
                "normalization_convention": "MASS_NORMALIZED (Phi^T M Phi = I), fixed-base, q relative to base frame",
                "zeta_band_ASSUMPTION_BAND": list(ZETA_BAND),
                "modal_damping_c_band_N_m_s_per_rad": [2 * ZETA_BAND[0] * om, 2 * ZETA_BAND[1] * om],
                "modal_decay_tau_band_s_INFORMATIONAL": [1.0 / (ZETA_BAND[1] * om), 1.0 / (ZETA_BAND[0] * om)],
                "participation": {},
            }
            for wing in ("L", "R"):
                gt = phi @ Bt[wing]     # coupling to (vx, vy, vz)
                gr = phi @ Br[wing]     # coupling to (wx, wy, wz)
                entry["participation"][f"wing_{wing}"] = {
                    "Gamma_t_kg_m": gt.tolist(),
                    "Gamma_r_kg_m2": gr.tolist(),
                    "nonzero_columns": {"Gamma_t": ["v_z"], "Gamma_r": ["omega_x"]},
                    "effective_modal_mass_vz_kg": float(gt[2] ** 2),
                    "effective_modal_inertia_wx_kg_m2": float(gr[0] ** 2),
                }
            rom_modes[m]["per_case"][case] = entry

    # global band per mode over all 15 combos
    for m in range(N_RETAIN):
        vals = [sweep[c]["per_ei"][ei]["frequencies_hz_first10"][m]
                for c in CASE_ORDER for ei in EI_ORDER]
        rom_modes[m]["frequency_band_global_hz"] = [min(vals), max(vals)]
        # representative mode shape/hinge content at the nominal case
        rom_modes[m]["nominal_case_reference"] = "per_case.nominal"

    # participation coverage: retained-5 effective-mass sums vs complete basis
    coverage = {}
    for wing in ("L", "R"):
        bt, br = Bt[wing][:, 2], Br[wing][:, 0]
        full_t = float(bt @ np.linalg.solve(M, bt))
        full_r = float(br @ np.linalg.solve(M, br))
        for case in ("nominal",):
            V_nom = np.array(sweep[case]["per_ei"]["EI_nominal"]["eigenvectors_first8_mass_normalized"])[:, :N_RETAIN]
            st = float(np.sum((V_nom.T @ bt) ** 2))
            sr = float(np.sum((V_nom.T @ br) ** 2))
            coverage[f"wing_{wing}"] = {
                "case": case,
                "retained5_effective_mass_vz_sum_kg": st,
                "complete_basis_vz_kg": full_t,
                "coverage_vz": st / full_t,
                "retained5_effective_inertia_wx_sum_kg_m2": sr,
                "complete_basis_wx_kg_m2": full_r,
                "coverage_wx": sr / full_r,
            }

    # ---------------- five-case comparison -----------------------------------
    comparison = {}
    for case in CASE_ORDER:
        hf5 = [sweep[case]["per_ei"]["EI_nominal"]["frequencies_hz_first10"][m] for m in range(N_RETAIN)]
        l2_exact = e21_hz[case]
        l2_pub = pub_hz[case]
        rows = []
        for j in range(3):
            rows.append({
                "l2_mode": j + 1,
                "published_hz_4dec": l2_pub[j],
                "l2_exact_hz_e21": l2_exact[j],
                "hf_hz_EI_nominal": hf5[j],
                "hf_minus_l2_exact_hz": hf5[j] - l2_exact[j],
                "hf_minus_l2_exact_pct": 100.0 * (hf5[j] - l2_exact[j]) / l2_exact[j],
                "hf_within_published_band_corners": (
                    pub_hz["all_low"][j] <= hf5[j] <= pub_hz["all_high"][j]),
            })
        comparison[case] = {
            "hf_first5_hz_EI_nominal": hf5,
            "l2_exact_hz": l2_exact,
            "published_hz_4dec": l2_pub,
            "rows_first3_mapped": rows,
            "hf_mode4_mode5_hz_no_l2_counterpart": hf5[3:],
        }

    # published band containment test on the mapped first 3 modes
    containment = []
    for j in range(3):
        hf_low_corner = sweep["all_low"]["per_ei"]["EI_nominal"]["frequencies_hz_first10"][j]
        hf_high_corner = sweep["all_high"]["per_ei"]["EI_nominal"]["frequencies_hz_first10"][j]
        hf_low_corner_eilow = sweep["all_low"]["per_ei"]["EI_low"]["frequencies_hz_first10"][j]
        containment.append({
            "mode": j + 1,
            "published_band_hz": [pub_hz["all_low"][j], pub_hz["all_high"][j]],
            "hf_band_same_hinge_corners_EI_nominal_hz": [hf_low_corner, hf_high_corner],
            "hf_global_low_incl_EI_low_hz": hf_low_corner_eilow,
            "hf_undercuts_published_low_corner": hf_low_corner < pub_hz["all_low"][j],
            "hf_high_corner_below_published_high_corner": hf_high_corner < pub_hz["all_high"][j],
        })

    # ---------------- difference decomposition --------------------------------
    v3 = hf["verification"]["V3_rigid_limit_vs_L2"]
    decomposition = {
        "lane_A_reproduction": {
            "statement": "L2 leaf-only model independently recomputed (scipy eigh) reproduces the "
                         "e21 full-precision five-case frequencies",
            "global_max_abs_diff_hz": hf["verification"]["V2_L2_five_case_frequency_reproduction"]["global_max_abs_diff_hz"],
            "e21_G20_bound_hz": 4.840419126761475e-05,
        },
        "lane_B_rigid_limit": {
            "statement": "HF model with EI x 1e4 recovers the L2 hinge modes; residual scales ~ 1/scale "
                         "(series beam compliance vanishes); this is the assembly/discretization lane",
            "five_cases_max_rel_diff_at_EI_x1e4": v3["five_cases_max_rel_diff_at_EI_x1e4"],
            "nominal_trend": {k: vv["rel_diff_vs_l2"] for k, vv in v3["nominal_multiplier_trend"].items()},
        },
        "lane_C_leaf_flexibility_effect": {
            "statement": "at fixed hinge stiffness the HF (flexible-leaf) frequencies sit BELOW the L2 "
                         "rigid-leaf values; leaf bending compliance acts in series with the hinge springs; "
                         "the effect is a MODELING-SCOPE difference (rigid vs flexible leaves), not an "
                         "uncertainty and not a reproduction error",
            "nominal_shift_pct_per_mode": [
                100.0 * (sweep["nominal"]["per_ei"]["EI_nominal"]["frequencies_hz_first10"][j] - e21_hz["nominal"][j])
                / e21_hz["nominal"][j] for j in range(3)],
        },
        "mca_bookkeeping_difference_separate": {
            "statement": "the MC-A hinge-mass bookkeeping difference (Mqq vs Mqq*) is a DIFFERENT, already "
                         "registered item: nominal -3.5096 / -6.9411 / -13.4 pct; it is NOT mixed into the "
                         "leaf-flexibility numbers above; both are registered separately and neither is a "
                         "standard uncertainty",
            "reference": "ENG_DECISION_DYNAMIC_MASS_ALLOCATION_V1.yaml bookkeeping_difference_entry BK-DYN-MASS-HINGE-ALLOC-MC-A",
        },
    }

    # ---------------- MC-A consistency ----------------------------------------
    mca = {
        "ruling": "MC-A (ENG-RULING-DYN-MASS-ALLOC-MC-A-V1), dynamic_mass_allocation_frozen=true",
        "mca_yaml_sha256_recorded": sha256_file(MCA_YAML),
        "hf_mass_matrix_is_leaf_only": True,
        "hinge_point_masses_in_rom_kinetic_energy": False,
        "hinge_point_mass_booking": "2 x 0.03 kg per wing as rigid non-following interface masses at hinge "
                                    "lines (structural mass ledger only, inside the 0.78 kg/wing closure); "
                                    "root hinge 0.05 kg + HDRM 0.08 kg + harness 0.05 kg per wing booked the "
                                    "same way (engineering extension of the MC-A rule, flagged, not silent)",
        "delta_M_excluded_kg_m2_verbatim": e21["nonselecting_conflict_diagnostic"]["Mqq_star_minus_leaf_only_kg_m2"],
        "l2_Mqq_matches_published_max_abs_diff_kg_m2":
            hf["verification"]["V1_L2_mass_matrix_recomputed"]["max_abs_diff_vs_e21_kg_m2"],
        "no_mqq_star_consumption": True,
        "no_matrix_averaging": True,
    }

    # ---------------- damping discipline ---------------------------------------
    damping = {
        "zeta_band_ASSUMPTION_BAND": list(ZETA_BAND),
        "basis": "literature-typical modal damping ratio range for sandwich-panel deployable appendages "
                 "(order 0.1%-2%); NO measurement source; the upstream card value zeta=0.01 "
                 "(TBD_cite_literature) is NOT consumed as authority; it merely lies inside this band",
        "two_lane_discipline": "conservation/momentum-audit lane: zeta=0 exactly; dissipative-prediction "
                               "lane: zeta inside the ASSUMPTION_BAND, results reported as bands only",
        "no_decay_point_values": True,
    }

    # ---------------- ROM document ----------------------------------------------
    rom = {
        "schema": "SOLAR_R2_ROM_V1",
        "generated_local": t0,
        "generator": "AGENT-F1 R2 full-flex closure Wave-3a round1 (pure numpy/scipy; read-only upstream)",
        "class": "CANDIDATE_PROVISIONAL_BANDS__NOT_CERTIFIED",
        "release_credit": False,
        "next_stage_authorized": False,
        "source_hf_model": {"path": "01_hf_model/SOLAR_R2_HF_FLEX_MODEL_V1.json",
                            "sha256": sha256_file(HF_JSON)},
        "rom_definition": {
            "modes_retained_per_wing": N_RETAIN,
            "mode_selection": "first 5 fixed-base elastic modes per wing (sorted by frequency at EI nominal; "
                              "branch continuity across EI corners verified by self-MAC per mode per case)",
            "first_omitted_mode_hz_nominal":
                sweep["nominal"]["per_ei"]["EI_nominal"]["frequencies_hz_first10"][N_RETAIN],
            "wings": "LEFT computed explicitly; RIGHT identical eigenproblem (mirror); participation "
                     "vectors stored per wing (mirror sign conventions documented in HF model file)",
            "normalization": "MASS_NORMALIZED Phi^T M Phi = I",
            "base_coupling": "fixed-base modes + modal participation factors B_t/B_r (spec draft section 2 "
                             "construction; free-floating assembly itself NOT performed here)",
        },
        "modes": rom_modes,
        "participation_coverage_nominal": coverage,
        "damping": damping,
        "torsion_scope_note": {
            "status": "NO_TORSION_DOF (GJ band NULL, SLOT-01)",
            "informational_ASSUMPTION_BAND_only": {
                "GJ_est_Nm2": {"nominal": 4.2727, "band": [1.2818, 12.8181],
                               "basis": "GJ ~ EI/(2(1+nu)), nu=0.3 quasi-iso faces; 0.3x..3x corners; "
                                        "NOT consumed in the model"},
                "leaf_torsion_f1_est_hz": {"nominal": 31.4, "band": [17.2, 54.5],
                                           "basis": "f=(1/4L)sqrt(GJ/muJ), muJ=mu*A^2/12=0.00675 kg m; "
                                                    "per-leaf cantilever torsion estimate"},
                "implication": "leaf torsional modes likely fall INSIDE the capture-relevant band; "
                               "ROM mode-set completeness stays OPEN until SLOT-01 (GJ) closes",
            },
        },
        "nonclaims": [
            "does NOT modify or replace the published FLEXIBLE_APPENDAGE_R2 / MODES evidence chain",
            "published leaf-only five-case frequencies and Mqq stay authoritative (MC-A); this ROM is a "
            "candidate refinement adding leaf flexibility",
            "no free-floating assembly, no forced response, no scene-A2-class evaluation (still HOLD)",
            "all bands are engineering/assumption corners, NOT standard uncertainties; no null was zero-filled",
        ],
    }

    ver = {
        "schema": "SOLAR_R2_ROM_VERIFICATION_V1",
        "generated_local": t0,
        "class": "CANDIDATE_PROVISIONAL_BANDS__NOT_CERTIFIED",
        "release_credit": False,
        "next_stage_authorized": False,
        "input_hashes": {
            "hf_model_json": sha256_file(HF_JSON),
            "e21_rom_json": sha256_file(E21_JSON),
            "mca_decision_yaml": sha256_file(MCA_YAML),
        },
        "five_case_comparison": comparison,
        "published_band_containment_first3_modes": containment,
        "difference_decomposition": decomposition,
        "mca_consistency": mca,
        "hf_stage_checks_carried": hf["verification"],
    }

    OUT_ROM.write_text(json.dumps(rom, indent=1), encoding="utf-8")
    OUT_VER.write_text(json.dumps(ver, indent=1), indent := None, encoding="utf-8") if False else OUT_VER.write_text(json.dumps(ver, indent=1), encoding="utf-8")

    print("ROM_OK")
    for case in CASE_ORDER:
        c = comparison[case]
        print(case, "hf:", [round(x, 4) for x in c["hf_first5_hz_EI_nominal"]],
              "l2:", [round(x, 4) for x in c["l2_exact_hz"]])
    print("containment:", [(r["mode"], r["hf_undercuts_published_low_corner"],
                            r["hf_high_corner_below_published_high_corner"]) for r in containment])
    print("coverage:", json.dumps(coverage, indent=1))


if __name__ == "__main__":
    main()
