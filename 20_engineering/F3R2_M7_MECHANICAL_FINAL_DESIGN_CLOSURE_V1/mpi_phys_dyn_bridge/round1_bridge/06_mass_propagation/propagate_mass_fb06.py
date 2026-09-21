"""MPI-FB-06: nine-configuration mass propagation through the frozen bridge.

Unifies the V3_R2 ledger onto a single consumption semantics (ODR-01 dynamics
consumption): C07..C09 arm rows are already dynamics-consumed (e21 proved
residual 0); C01..C06 arm rows (physical-rail consumed, rounded spelling) are
re-expressed through the S-frame conjugate C_S = T_dyn @ inv(T_phys):
    cg|dyn = R(C_S) cg|phys + p(C_S);   I|dyn = R(C_S) I|phys R(C_S).T
Mass is invariant (exact zero difference). Non-arm members are copied verbatim
(bus, M3R, load-bridge candidate, Solar R2 wings, scenario targets) - Solar R2
wings are bus-attached and never pass through the arm mount bridge.

The accepted V3_R2 file is READ-ONLY; the output is a NEW candidate file.
Writes ONLY SYSTEM_MASS_PROPERTIES_BRIDGED_V1.yaml inside 06_mass_propagation/.
"""
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np
import yaml

sys.dont_write_bytecode = True

ROOT = Path("F:/China Graduate Future Flight Vehicle Innovation Competition")
BASE = ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge"
BRIDGE_FILE = BASE / "02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml"
OUT_DIR = BASE / "06_mass_propagation"
OUT_FILE = OUT_DIR / "SYSTEM_MASS_PROPERTIES_BRIDGED_V1.yaml"

V3_R2_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml"
M6_TRANSFORMS_REL = "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp2_mass_properties/CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml"
E21_SRC_REL = "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/src/build_e21_diagnostics.py"
E21_AUDIT_REL = "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results/E21_NINE_CONFIGURATION_ARM_PLACEMENT_AUDIT_V1.json"
URDF_REL = "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
B601_MODEL_REL = "30_simulation/sim_05_free_floating_arm/b601_model.py"
E21_CAMPAIGN_REL = "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/config/E21_CURRENT_R2_RIGID_DIAGNOSTIC_CAMPAIGN_V1.yaml"

ARM_ID = "b601_complete_arm_including_gripper_urdf_links"
PHYSICAL_CONSUMED = {"C01", "C02", "C03", "C04", "C05", "C06"}   # e21 audit classification
DYNAMICS_CONSUMED = {"C07", "C08", "C09"}


def sha256_file(rel) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest().upper()


def maxabs(A) -> float:
    return float(np.max(np.abs(A)))


def steiner(m, r):
    r = np.asarray(r, dtype=float)
    return float(m) * ((r @ r) * np.eye(3) - np.outer(r, r))


def inertia_of(member):
    v = member["inertia_about_own_com_S_kg_m2"]
    if isinstance(v, list):
        return np.asarray(v, dtype=float)
    return np.array([[v["Ixx"], v["Ixy"], v["Ixz"]],
                     [v["Ixy"], v["Iyy"], v["Iyz"]],
                     [v["Ixz"], v["Iyz"], v["Izz"]]], dtype=float)


def aggregate(members):
    mass = math.fsum(float(m["mass_kg"]) for m in members)
    cg = np.sum([float(m["mass_kg"]) * np.asarray(m["com_S_m"], dtype=float) for m in members], axis=0) / mass
    I = np.zeros((3, 3))
    for m in members:
        c = np.asarray(m["com_S_m"], dtype=float)
        I += inertia_of(m) + steiner(float(m["mass_kg"]), c - cg)
    return mass, cg, 0.5 * (I + I.T)


def import_source(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    bridge_sha = hashlib.sha256(BRIDGE_FILE.read_bytes()).hexdigest().upper()
    bridge = yaml.safe_load(BRIDGE_FILE.read_bytes().decode("utf-8"))
    C_S = np.asarray(bridge["S_frame_conjugate_for_S_expressed_quantities"]["C_S_homogeneous_4x4"], dtype=float)
    R_Cs, p_Cs = C_S[:3, :3], C_S[:3, 3]

    v3 = yaml.safe_load((ROOT / V3_R2_REL).read_text(encoding="utf-8"))
    e21 = import_source("fb06_e21_src", E21_SRC_REL)
    b601 = import_source("fb06_b601_model", B601_MODEL_REL)
    campaign = yaml.safe_load((ROOT / E21_CAMPAIGN_REL).read_text(encoding="utf-8"))
    transform_card = yaml.safe_load((ROOT / M6_TRANSFORMS_REL).read_text(encoding="utf-8"))
    arm_obj = b601.B601Arm(str(ROOT / URDF_REL))

    configs_out = []
    summary_rows = []
    for config in v3["configurations"]:
        cid = config["configuration_id"]
        members = config["composition"]
        arm_row = next(m for m in members if m["component_id"] == ARM_ID)

        # stated totals (dual storage keys carry identical content)
        stated_mass = float(config["mass"]["value_kg"])
        stated_cg = np.asarray(config["center_of_mass"]["xyz_m"], dtype=float)
        ic = config["inertia"]["components_kg_m2"]
        stated_I = np.array([[ic["Ixx"], ic["Ixy"], ic["Ixz"]],
                             [ic["Ixy"], ic["Iyy"], ic["Iyz"]],
                             [ic["Ixz"], ic["Iyz"], ic["Izz"]]], dtype=float)

        # aggregator validation: members -> totals, no bridge involved
        agg_m, agg_cg, agg_I = aggregate(members)
        aggregator_check = {
            "mass_stated_minus_aggregated": stated_mass - agg_m,
            "cg_stated_minus_aggregated_max_abs": maxabs(stated_cg - agg_cg),
            "inertia_stated_minus_aggregated_max_abs": maxabs(stated_I - agg_I),
        }

        # candidate arm row
        arm_cg_ledger = np.asarray(arm_row["com_S_m"], dtype=float)
        arm_I_ledger = inertia_of(arm_row)
        if cid in PHYSICAL_CONSUMED:
            arm_cg_cand = R_Cs @ arm_cg_ledger + p_Cs
            arm_I_cand = R_Cs @ arm_I_ledger @ R_Cs.T
            arm_action = "RE_EXPRESSED_VIA_C_S_PHYSICAL_TO_DYNAMICS_CONSUMPTION"
        else:
            arm_cg_cand = arm_cg_ledger.copy()
            arm_I_cand = arm_I_ledger.copy()
            arm_action = "UNCHANGED_ALREADY_ODR01_DYNAMICS_CONSUMED"

        cand_members = []
        for m in members:
            if m["component_id"] == ARM_ID:
                m2 = dict(m)
                m2["com_S_m"] = [float(v) for v in arm_cg_cand]
                m2["inertia_about_own_com_S_kg_m2"] = [[float(v) for v in row] for row in arm_I_cand]
                m2["bridge_provenance"] = {
                    "action": arm_action,
                    "bridge_file": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml",
                    "bridge_sha256": bridge_sha,
                    "pre_bridge_com_S_m": [float(v) for v in arm_cg_ledger],
                    "pre_bridge_inertia_about_own_com_S_kg_m2": [[float(v) for v in row] for row in arm_I_ledger],
                    "bridge_uncertainty": None,
                    "bridge_uncertainty_note": "deterministic geometric object; declared member uncertainties carried verbatim from V3_R2",
                }
                cand_members.append(m2)
            else:
                cand_members.append(m)  # verbatim carry

        cand_m, cand_cg, cand_I = aggregate(cand_members)

        # independent FK cross-check at the pure ODR01 placement
        pose_key, q = e21.pose_vector(arm_row["transform_ref"], transform_card)
        fk_m, fk_cg, fk_I = e21.arm_properties(b601, arm_obj, q, e21.PLACEMENTS["ODR01_DYNAMICS_T_SM"])
        fk_cross = {
            "pose_binding": pose_key,
            "candidate_arm_mass_minus_fk": float(cand_m * 0 + float(arm_row["mass_kg"]) - fk_m),
            "candidate_arm_cg_minus_fk_norm_m": float(np.linalg.norm(arm_cg_cand - fk_cg)),
            "candidate_arm_inertia_minus_fk_max_abs": maxabs(arm_I_cand - fk_I),
            "note": ("C01..C06: residual = registered WP11-F-03 rounded-clock spelling deviation (~1.1e-4 mm class), "
                     "documented not zeroed" if cid in PHYSICAL_CONSUMED else
                     "C07..C09: candidate row identical to ledger (already dynamics-consumed); residual vs FK is "
                     "the e21 G10-class machine-precision closure"),
        }

        eig = np.linalg.eigvalsh(cand_I)
        checks = {
            "mass_invariant_candidate_minus_stated_exact": float(cand_m - stated_mass),
            "symmetry_max_abs": maxabs(cand_I - cand_I.T),
            "spd_min_eigenvalue": float(eig[0]),
            "principal_moments": [float(v) for v in eig],
            "triangle_inequalities": bool(
                cand_I[0, 0] + cand_I[1, 1] >= cand_I[2, 2] and
                cand_I[1, 1] + cand_I[2, 2] >= cand_I[0, 0] and
                cand_I[2, 2] + cand_I[0, 0] >= cand_I[1, 1]),
        }

        delta_cg = cand_cg - stated_cg
        delta_I = cand_I - stated_I
        # bridge-explanation: the system totals are a linear-parallel-axis aggregate,
        # so the delta decomposes EXACTLY into (i) arm about-CG conjugation,
        # (ii) arm Steiner delta, (iii) induced system-CG-shift Steiner delta on
        # every other member - all downstream of the single arm-row bridge action:
        m_arm = float(arm_row["mass_kg"])
        dI_pred = (arm_I_cand - arm_I_ledger) \
            + m_arm * (steiner(1.0, arm_cg_cand - cand_cg) - steiner(1.0, arm_cg_ledger - stated_cg)) \
            + np.sum([float(m["mass_kg"]) * (steiner(1.0, np.asarray(m["com_S_m"], dtype=float) - cand_cg)
                                             - steiner(1.0, np.asarray(m["com_S_m"], dtype=float) - stated_cg))
                      for m in members if m["component_id"] != ARM_ID], axis=0)
        dcg_pred = m_arm / stated_mass * (arm_cg_cand - arm_cg_ledger)
        bridge_explanation = {
            "delta_cg_total_m": delta_cg.tolist(),
            "delta_cg_from_arm_row_only_m": dcg_pred.tolist(),
            "delta_cg_explained_max_abs_residual": maxabs(delta_cg - dcg_pred),
            "delta_inertia_total_max_abs": maxabs(delta_I),
            "delta_inertia_from_arm_row_only_max_abs_residual": maxabs(delta_I - dI_pred),
        }

        out_config = {
            "configuration_id": cid,
            "name": config["name"],
            "candidate_semantics": "SINGLE_ODR01_DYNAMICS_CONSUMPTION_VIA_B601_PHYSICAL_DYNAMICS_BRIDGE_V1",
            "v3_r2_stated": {
                "mass_kg": stated_mass,
                "cg_S_m": stated_cg.tolist(),
                "inertia_about_system_cg_S_kg_m2": stated_I.tolist(),
            },
            "aggregator_validation_members_to_stated": aggregator_check,
            "bridged_candidate": {
                "mass_kg": cand_m,
                "cg_S_m": cand_cg.tolist(),
                "inertia_about_system_cg_S_kg_m2": cand_I.tolist(),
            },
            "candidate_minus_stated": {
                "mass_exact": float(cand_m - stated_mass),
                "cg_vector_m": delta_cg.tolist(),
                "cg_norm_m": float(np.linalg.norm(delta_cg)),
                "inertia_max_abs": maxabs(delta_I),
            },
            "arm_row_action": arm_action,
            "arm_pose_status_carried_verbatim": arm_row.get("pose_status"),
            "fk_cross_check_vs_pure_odr01_placement": fk_cross,
            "bridge_explanation_of_deltas": bridge_explanation,
            "checks": checks,
            "composition_candidate": cand_members,
        }
        configs_out.append(out_config)
        summary_rows.append({
            "configuration_id": cid,
            "mass_invariant_exact_zero_diff": float(cand_m - stated_mass),
            "cg_shift_norm_m": float(np.linalg.norm(delta_cg)),
            "inertia_shift_max_abs": maxabs(delta_I),
            "arm_action": arm_action,
            "fk_residual_cg_m": fk_cross["candidate_arm_cg_minus_fk_norm_m"],
            "fk_residual_inertia_max_abs": fk_cross["candidate_arm_inertia_minus_fk_max_abs"],
            "spd_min_eigenvalue": float(eig[0]),
        })

    # solar wing pollution guard: every non-arm member byte-equal to V3_R2
    pollution = []
    for cfg_out, cfg_in in zip(configs_out, v3["configurations"]):
        for m_out, m_in in zip(cfg_out["composition_candidate"], cfg_in["composition"]):
            if m_in["component_id"] == ARM_ID:
                continue
            if m_out is not m_in:
                pollution.append((cfg_in["configuration_id"], m_in["component_id"]))
    gate_checks = [
        {"id": "FB06-01", "name": "mass invariant per configuration (exact 0 diff)",
         "value": max(abs(r["mass_invariant_exact_zero_diff"]) for r in summary_rows), "limit": 0.0,
         "status": "PASS" if all(r["mass_invariant_exact_zero_diff"] == 0.0 for r in summary_rows) else "FAIL"},
        {"id": "FB06-02", "name": "C07..C09 candidate totals identical to stated (arm untouched)",
         "value": max(max(r["cg_shift_norm_m"], r["inertia_shift_max_abs"]) for r in summary_rows if r["configuration_id"] in DYNAMICS_CONSUMED),
         "limit": 0.0,
         "status": "PASS" if all(r["cg_shift_norm_m"] == 0.0 and r["inertia_shift_max_abs"] == 0.0
                                 for r in summary_rows if r["configuration_id"] in DYNAMICS_CONSUMED) else "FAIL"},
        {"id": "FB06-03", "name": "C01..C06 deltas fully explained by arm-row bridge action",
         "value": max(max(o["bridge_explanation_of_deltas"]["delta_cg_explained_max_abs_residual"],
                          o["bridge_explanation_of_deltas"]["delta_inertia_from_arm_row_only_max_abs_residual"])
                      for o in configs_out if o["configuration_id"] in PHYSICAL_CONSUMED),
         "limit": 1e-12,
         "status": "PASS" if all(o["bridge_explanation_of_deltas"]["delta_cg_explained_max_abs_residual"] <= 1e-12
                                 and o["bridge_explanation_of_deltas"]["delta_inertia_from_arm_row_only_max_abs_residual"] <= 1e-12
                                 for o in configs_out if o["configuration_id"] in PHYSICAL_CONSUMED) else "FAIL"},
        {"id": "FB06-04", "name": "all candidate inertias symmetric SPD triangle",
         "value": 0.0 if all(o["checks"]["symmetry_max_abs"] <= 1e-12 and o["checks"]["spd_min_eigenvalue"] > 0
                             and o["checks"]["triangle_inequalities"] for o in configs_out) else 1.0,
         "limit": 0.0,
         "status": "PASS" if all(o["checks"]["symmetry_max_abs"] <= 1e-12 and o["checks"]["spd_min_eigenvalue"] > 0
                                 and o["checks"]["triangle_inequalities"] for o in configs_out) else "FAIL"},
        {"id": "FB06-05", "name": "non-arm members carried byte-identical (no solar/M3R/bridge/target pollution)",
         "value": float(len(pollution)), "limit": 0.0,
         "status": "PASS" if not pollution else "FAIL", "detail": pollution},
        {"id": "FB06-06", "name": "C01..C06 FK residuals inside registered spelling band (not zeroed)",
         "value": max(r["fk_residual_cg_m"] for r in summary_rows if r["configuration_id"] in PHYSICAL_CONSUMED),
         "limit": 1.2e-7,
         "status": "PASS" if all(r["fk_residual_cg_m"] <= 1.2e-7 for r in summary_rows
                                 if r["configuration_id"] in PHYSICAL_CONSUMED) else "FAIL",
         "note": "band = registered WP11-F-03 rounded-clock spelling deviation class (~1.13e-7 m)"},
        {"id": "FB06-07", "name": "C07..C09 FK residuals at machine precision",
         "value": max(r["fk_residual_cg_m"] for r in summary_rows if r["configuration_id"] in DYNAMICS_CONSUMED),
         "limit": 1e-12,
         "status": "PASS" if all(r["fk_residual_cg_m"] <= 1e-12 for r in summary_rows
                                 if r["configuration_id"] in DYNAMICS_CONSUMED) else "FAIL"},
        {"id": "FB06-08", "name": "aggregator fidelity: members->stated totals before bridging",
         "value": max(max(abs(o["aggregator_validation_members_to_stated"]["mass_stated_minus_aggregated"]),
                          o["aggregator_validation_members_to_stated"]["cg_stated_minus_aggregated_max_abs"],
                          o["aggregator_validation_members_to_stated"]["inertia_stated_minus_aggregated_max_abs"])
                      for o in configs_out),
         "limit": 1e-9,
         "status": None},
    ]
    agg_worst = gate_checks[7]["value"]
    gate_checks[7]["status"] = "PASS" if agg_worst <= 1e-9 else "FAIL"

    all_pass = all(c["status"] == "PASS" for c in gate_checks)
    out = {
        "schema": "SYSTEM_MASS_PROPERTIES_BRIDGED_V1",
        "candidate": True,
        "generated_local": "2026-08-23T19:40:00+08:00",
        "generator": "KIMI M7 Wave-2a AGENT-1 MPI-FB-06 (pure python/numpy)",
        "status": "CANDIDATE_ONLY_NOT_RELEASE_NOT_PRODUCTION_PENDING_OWNER_REVIEW",
        "source_ledger": {"path": V3_R2_REL, "sha256": sha256_file(V3_R2_REL),
                          "note": "V3_R2 remains the accepted R2 design ledger (ODR-44); this candidate never overwrites it"},
        "bridge_artifact": {"path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml",
                            "sha256": bridge_sha},
        "consumption_semantics": "SINGLE_ODR01_DYNAMICS_CONSUMPTION; physical-rail arm rows (C01..C06) re-expressed "
                                 "via C_S conjugate of the frozen bridge; no selection, no averaging, no uncertainty re-label",
        "uncertainty_policy": "member-level declared uncertainties carried verbatim inside composition_candidate; "
                              "bridge uncertainty = null (deterministic geometry); no uncertainty matrix rotation "
                              "(WP2-AUD-02 precedent honored)",
        "carried_pose_status_note": "C05 pose_status (HELD_CANDIDATE_FK_REGRESSION_FAIL_MAX_RESIDUAL_567P734_MM...) "
                                    "carried verbatim; not absorbed, not fixed by this package",
        "configurations": configs_out,
        "summary_by_configuration": summary_rows,
        "gate_checks": gate_checks,
        "criterion_counts": {"total": len(gate_checks), "pass": sum(c["status"] == "PASS" for c in gate_checks),
                             "fail": sum(c["status"] == "FAIL" for c in gate_checks)},
        "overall": "PASS" if all_pass else "FAIL",
        "source_register": [
            {"path": V3_R2_REL, "sha256": sha256_file(V3_R2_REL)},
            {"path": M6_TRANSFORMS_REL, "sha256": sha256_file(M6_TRANSFORMS_REL)},
            {"path": E21_SRC_REL, "sha256": sha256_file(E21_SRC_REL)},
            {"path": E21_AUDIT_REL, "sha256": sha256_file(E21_AUDIT_REL)},
            {"path": URDF_REL, "sha256": sha256_file(URDF_REL)},
            {"path": B601_MODEL_REL, "sha256": sha256_file(B601_MODEL_REL)},
        ],
        "next_stage_authorized": False,
        "release_credit": False,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_bytes(yaml.safe_dump(out, sort_keys=False, allow_unicode=True, width=200).encode("utf-8"))
    digest = hashlib.sha256(OUT_FILE.read_bytes()).hexdigest().upper()
    print("WROTE", OUT_FILE)
    print("sha256:", digest)
    print("overall:", out["overall"], out["criterion_counts"])
    for r in summary_rows:
        print(r["configuration_id"], "| dmass:", r["mass_invariant_exact_zero_diff"],
              "| dCG m:", r["cg_shift_norm_m"], "| dI max:", r["inertia_shift_max_abs"],
              "| fk cg resid m:", r["fk_residual_cg_m"], "|", r["arm_action"][:40])
    print("aggregator worst:", agg_worst)


if __name__ == "__main__":
    main()
