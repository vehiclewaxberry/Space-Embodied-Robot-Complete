#!/usr/bin/env python
"""Independent numerical recomputation for the isolated Solar R2 HF/ROM V2.

This script deliberately does not import the builder.  It consumes the emitted
NPZ plus e21 and recomputes the central invariants with separate equations.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from scipy.linalg import eigh

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
ROOT = PKG.parents[3]
NPZ = PKG / "R2_HF_ROM_NUMERICAL_DATA_V2.npz"
ROM_JSON = PKG / "R2_FIVE_MODE_ROM_V2.json"
EVID_JSON = PKG / "R2_HF_NUMERICAL_EVIDENCE_V2.json"
MODEL_YAML = PKG / "R2_HF_MODEL_V2.yaml"
OUT = HERE / "INDEPENDENT_RECOMPUTE_V2.json"
E21 = (ROOT / "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics"
       / "results/E21_FIXED_BASE_R2_ROM_REPRODUCTION_AND_MASS_CONFLICT_V1.json")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def maxabs(a) -> float:
    return float(np.max(np.abs(np.asarray(a, dtype=float))))


def main() -> None:
    z = np.load(NPZ)
    e21 = json.loads(E21.read_text(encoding="utf-8"))
    rom = json.loads(ROM_JSON.read_text(encoding="utf-8"))
    evid = json.loads(EVID_JSON.read_text(encoding="utf-8"))

    Mfull = z["M_full"]
    M = z["M"]
    K = z["K_nominal"]
    Kun = z["K_unlatched"]
    Q = z["Q_rigid"]
    S = z["coordinate_scale"]
    Phi = z["Phi_rom"]
    u_trans = z["rigid_translation_full"]
    Mqq_e21 = np.asarray(e21["leaf_only"]["Mqq_kg_m2"], float)

    checks = {}
    m_leaf = float(u_trans @ Mfull @ u_trans)
    checks["I01_unconstrained_rigid_translation_mass"] = {
        "recomputed_kg": m_leaf,
        "target_kg": 0.54,
        "abs_error_kg": abs(m_leaf - 0.54),
        "pass": abs(m_leaf - 0.54) < 1e-12,
    }

    Mqq = Q.T @ M @ Q
    checks["I02_piecewise_rigid_projection_Mqq"] = {
        "max_abs_diff_vs_e21_kg_m2": maxabs(Mqq - Mqq_e21),
        "recomputed": Mqq.tolist(),
        "pass": maxabs(Mqq - Mqq_e21) < 1e-12,
    }

    five = {}
    cases = {
        "nominal": (200.0, 100.0),
        "all_low": (50.0, 20.0),
        "all_high": (800.0, 400.0),
        "root_low_inter_high": (50.0, 400.0),
        "root_high_inter_low": (800.0, 20.0),
    }
    refs = {c["case"]: c["leaf_only_reproduced_hz"]
            for c in e21["leaf_only"]["cases"]}
    max_df = 0.0
    for name, (kr, ki) in cases.items():
        f = np.sqrt(eigh(np.diag([kr, ki, ki]), Mqq,
                         eigvals_only=True)) / (2.0 * math.pi)
        df = maxabs(f - np.asarray(refs[name]))
        max_df = max(max_df, df)
        five[name] = {"recomputed_hz": f.tolist(), "max_abs_diff_hz": df}
    checks["I03_e21_five_case_reproduction"] = {
        "per_case": five, "global_max_abs_diff_hz": max_df,
        "pass": max_df < 1e-9,
    }

    Mr = Phi.T @ M @ Phi
    Kr = Phi.T @ K @ Phi
    checks["I04_rom_projection"] = {
        "Mrom_identity_max_abs": maxabs(Mr - np.eye(5)),
        "Mrom_vs_published_max_abs": maxabs(Mr - z["Mrom"]),
        "Krom_vs_published_max_abs": maxabs(Kr - z["Krom_NOMINAL"]),
        "pass": (maxabs(Mr - np.eye(5)) < 1e-10 and
                 maxabs(Kr - z["Krom_NOMINAL"]) < 1e-8),
    }

    participation_checks = {}
    for wing in ("L", "R"):
        Bt, Br = z[f"Bt_{wing}"], z[f"Br_{wing}"]
        gt, gr = Phi.T @ Bt, Phi.T @ Br
        participation_checks[wing] = {
            "Gamma_t_max_abs_diff": maxabs(gt - z[f"Gamma_t_{wing}"]),
            "Gamma_r_max_abs_diff": maxabs(gr - z[f"Gamma_r_{wing}"]),
            "pass": (maxabs(gt - z[f"Gamma_t_{wing}"]) < 1e-12 and
                     maxabs(gr - z[f"Gamma_r_{wing}"]) < 1e-12),
        }
    checks["I05_base_participation_projection"] = {
        "per_wing": participation_checks,
        "pass": all(v["pass"] for v in participation_checks.values()),
    }

    # Dimensionally homogeneous stiffness: physical q = diag(S) q_hat.
    Ks = (S[:, None] * Kun) * S[None, :]
    _, sv, vh = np.linalg.svd(Ks)
    tol = max(sv) * 1e-10
    nnull = int(np.sum(sv < tol))
    Qs = Q / S[:, None]
    q_exp, _ = np.linalg.qr(Qs)
    n_svd = vh.T[:, -3:]
    principal = np.linalg.svd(q_exp.T @ n_svd, compute_uv=False)
    residuals = [float(np.linalg.norm(Ks @ Qs[:, i]) /
                       (np.linalg.norm(Ks) * np.linalg.norm(Qs[:, i])))
                 for i in range(3)]
    checks["I06_scaled_nullspace"] = {
        "nullity": nnull,
        "threshold": tol,
        "principal_cosines_explicit_vs_svd": principal.tolist(),
        "explicit_mechanism_relative_residuals": residuals,
        "pass": (nnull == 3 and min(principal) > 1.0 - 1e-8 and
                 max(residuals) < 1e-11),
    }

    # LEFT/RIGHT symmetry: translation participation equal; rotations x/y
    # change sign under mirror; structurally zero columns stay exactly zero.
    checks["I07_left_right_participation_symmetry"] = {
        "Bt_max_abs_L_minus_R": maxabs(z["Bt_L"] - z["Bt_R"]),
        "Br_max_abs_L_plus_R": maxabs(z["Br_L"] + z["Br_R"]),
        "pass": (maxabs(z["Bt_L"] - z["Bt_R"]) < 1e-14 and
                 maxabs(z["Br_L"] + z["Br_R"]) < 1e-14),
    }

    checks["I08_scope_guards"] = {
        "r2_coupled_diagnostics": evid["scope_guards"]["r2_coupled_diagnostics"],
        "e15_inheritance": evid["scope_guards"]["e15_inheritance"],
        "next_stage_authorized": evid["next_stage_authorized"],
        "release_credit": evid["release_credit"],
        "pass": (evid["scope_guards"]["r2_coupled_diagnostics"] == "NOT_EVALUATED" and
                 evid["scope_guards"]["e15_inheritance"] == "NOT_INHERITED" and
                 evid["next_stage_authorized"] is False and
                 evid["release_credit"] is False),
    }

    checks["I09_root_authority_no_average"] = {
        "root_y_m": evid["geometry_authority"]["root_hinge_S_m"]["y_abs"],
        "root_z_m": evid["geometry_authority"]["root_hinge_S_m"]["z"],
        "historical_0p1149_disposition": evid["geometry_authority"]["historical_conflict"]["disposition"],
        "pass": (evid["geometry_authority"]["root_hinge_S_m"]["y_abs"] == 0.1154 and
                 evid["geometry_authority"]["root_hinge_S_m"]["z"] == -0.10815 and
                 "AVERAGE" not in evid["geometry_authority"]["historical_conflict"]["disposition"]),
    }

    semantics = rom["reduced_hf_dof_semantics"]
    op_keys = {
        "w_nodes": "R_w_nodes",
        "theta_dofs": "R_theta_dofs",
        "torsion_nodes": "R_torsion_nodes",
        "hinge_relative": "R_hinge_relative",
        "tip_w": "R_tip_w",
    }
    operator_diffs = {
        name: maxabs(np.asarray(rom["reconstruction_operators_rom"][name], float)
                     - z[npz_key])
        for name, npz_key in op_keys.items()
    }
    contract = rom["quantitative_linearity_contract"]
    limits = contract["limits"]
    checks["I10_reconstruction_and_linearity_contract"] = {
        "semantic_count": len(semantics),
        "unique_reduced_indices": len({x["reduced_index_0based"] for x in semantics}),
        "unique_full_indices": len({x["full_index_0based"] for x in semantics}),
        "operator_json_vs_npz_max_abs": operator_diffs,
        "root_w_modal_row_max_abs": maxabs(z["R_w_nodes"][0]),
        "root_torsion_modal_row_max_abs": maxabs(z["R_torsion_nodes"][0]),
        "tip_row_identity_residual": maxabs(z["R_tip_w"] - z["R_w_nodes"][-1:, :]),
        "linearity_limits": limits,
        "out_of_domain_policy": contract["out_of_domain_policy"],
        "pass": (
            len(semantics) == M.shape[0]
            and len({x["reduced_index_0based"] for x in semantics}) == M.shape[0]
            and len({x["full_index_0based"] for x in semantics}) == M.shape[0]
            and max(operator_diffs.values()) < 1e-14
            and maxabs(z["R_w_nodes"][0]) == 0.0
            and maxabs(z["R_torsion_nodes"][0]) == 0.0
            and maxabs(z["R_tip_w"] - z["R_w_nodes"][-1:, :]) == 0.0
            and all(float(v) > 0.0 for v in limits.values())
            and contract["out_of_domain_policy"] == "FAIL_CLOSED__NO_LINEAR_ROM_EXTRAPOLATION"
        ),
    }

    all_pass = all(v["pass"] for v in checks.values())
    report = {
        "schema": "R2_HF_ROM_INDEPENDENT_RECOMPUTE_V2",
        "generated_local": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "method_independence": "does not import builder; recomputes from NPZ and e21",
        "input_hashes": {
            str(NPZ.name): sha256(NPZ),
            str(ROM_JSON.name): sha256(ROM_JSON),
            str(EVID_JSON.name): sha256(EVID_JSON),
            str(MODEL_YAML.name): sha256(MODEL_YAML),
            str(E21.relative_to(ROOT)).replace("\\", "/"): sha256(E21),
        },
        "checks": checks,
        "summary": {"passed": sum(int(v["pass"]) for v in checks.values()),
                    "total": len(checks)},
        "verdict": "PASS" if all_pass else "FAIL",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"INDEPENDENT_RECOMPUTE {report['verdict']} "
          f"{report['summary']['passed']}/{report['summary']['total']}")
    if not all_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
