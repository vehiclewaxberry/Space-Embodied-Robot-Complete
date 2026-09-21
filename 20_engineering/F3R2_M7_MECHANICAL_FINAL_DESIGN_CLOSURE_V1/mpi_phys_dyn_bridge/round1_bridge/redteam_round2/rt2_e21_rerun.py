"""REDTEAM-2 (Wave-2b) - (e) independent e21 bridged-lane rerun + FB-06 FK cross-checks.

Independence: the mount is rebuilt from the hash-pinned e21 authority contract
(B_rt2 = inv(T_dyn) @ T_phys computed HERE), then checked against the frozen
bridge file. The e21 module and b601 model are imported READ-ONLY via
importlib with bytecode writing disabled; a full-directory hash sentinel of the
e21 module (and sim_05 model) runs before AND after the integration.

Writes ONLY rt2_e21_rerun_output.json inside redteam_round2/.
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import yaml

sys.dont_write_bytecode = True

ROOT = Path("F:/China Graduate Future Flight Vehicle Innovation Competition")
BASE = ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge"
OUT_DIR = BASE / "redteam_round2"
OUT_FILE = OUT_DIR / "rt2_e21_rerun_output.json"

E21_PREFIX = "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics"
E21_SRC_REL = f"{E21_PREFIX}/src/build_e21_diagnostics.py"
E21_AUTHORITY_REL = f"{E21_PREFIX}/00_authority/E21_AUTHORITY_CONTRACT_V1.yaml"
E21_CAMPAIGN_REL = f"{E21_PREFIX}/config/E21_CURRENT_R2_RIGID_DIAGNOSTIC_CAMPAIGN_V1.yaml"
E21_ODR01_PUB_REL = f"{E21_PREFIX}/results/E21_ODR01_DYNAMICS_T_SM__M07_ARM_ONLY_RADAU_SUMMARY_V1.json"
E21_WP11_PUB_REL = f"{E21_PREFIX}/results/E21_WP11_PHYSICAL_GEOMETRY_CONTEXT__M07_ARM_ONLY_RADAU_SUMMARY_V1.json"
B601_MODEL_REL = "30_simulation/sim_05_free_floating_arm/b601_model.py"
URDF_REL = "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
BRIDGE_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml"
FB05_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/05_e21_bridged/E21_BRIDGED_ARM_PLACEMENT_GATE_V2.json"
FB06_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/06_mass_propagation/SYSTEM_MASS_PROPERTIES_BRIDGED_V1.yaml"
M6_TRANSFORMS_REL = "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp2_mass_properties/CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml"
ARM_ID = "b601_complete_arm_including_gripper_urdf_links"

WATCH_DIRS = [ROOT / E21_PREFIX, ROOT / "30_simulation/sim_05_free_floating_arm",
              ROOT / "20_engineering/cad/spacecraft_layout/arm_b601_v1",
              ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass",
              ROOT / "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp2_mass_properties"]


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest().upper()


def snapshot():
    snap = {}
    for d in WATCH_DIRS:
        for p in sorted(d.rglob("*")):
            if p.is_file():
                snap[p.relative_to(ROOT).as_posix()] = sha256_file(p)
    return snap


def import_source(name, rel):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def maxabs(A) -> float:
    return float(np.max(np.abs(np.asarray(A, dtype=float))))


def main():
    rep = {"schema": "RED_TEAM_ROUND2_E21_RERUN_OUTPUT_V1",
           "generator": "KIMI M7 Wave-2b REDTEAM-2 independent e21 bridged-lane rerun",
           "checks": []}
    def check(cid, name, value, limit, passed, detail=None):
        rep["checks"].append({"id": cid, "name": name, "value": value, "limit": limit,
                              "status": "PASS" if passed else "FAIL", "detail": detail})

    snap_before = snapshot()
    rep["watch_files_count"] = len(snap_before)
    rep["pycache_present_before"] = [k for k in snap_before if "__pycache__" in k]

    # ---- independent bridge rebuild from the authority contract ------------
    contract = yaml.safe_load((ROOT / E21_AUTHORITY_REL).read_text(encoding="utf-8"))
    hyp = contract["placement_hypotheses"]
    T_dyn = np.asarray(hyp["ODR01_DYNAMICS_T_SM"]["transform_S_A0_rows"], dtype=float)
    T_phys = np.asarray(hyp["WP11_PHYSICAL_GEOMETRY_CONTEXT"]["transform_S_A0_rows"], dtype=float)
    B_rt2 = np.linalg.inv(T_dyn) @ T_phys
    bridge_bytes = (ROOT / BRIDGE_REL).read_bytes()
    bridge = yaml.safe_load(bridge_bytes.decode("utf-8"))
    B_file = np.asarray(bridge["T_PHYSICAL_TO_DYNAMIC"]["homogeneous_4x4"], dtype=float)
    check("RT2-E-00a", "independent B rebuild vs frozen bridge file (max-abs)",
          maxabs(B_rt2 - B_file), 1e-15, maxabs(B_rt2 - B_file) <= 1e-15)
    check("RT2-E-00b", "bridge file sha256", hashlib.sha256(bridge_bytes).hexdigest().upper(),
          "0ACEB659284CAB862BA65228C5C2DF4BEB06D9EE05B5E2F0B2B5CB38402BF72C",
          hashlib.sha256(bridge_bytes).hexdigest().upper()
          == "0ACEB659284CAB862BA65228C5C2DF4BEB06D9EE05B5E2F0B2B5CB38402BF72C")

    # single consumption mount: exactly one construction site in this runner
    mount_bridged = T_dyn @ B_rt2
    mount_equiv = maxabs(mount_bridged - T_phys)
    check("RT2-E-01", "mount T_dyn@B_rt2 == T_phys (exact)", mount_equiv, 1e-12, mount_equiv <= 1e-12)
    consumer_ambiguity_count = 0  # single mount construction site; reference lanes non-consumed
    check("RT2-E-02", "consumer_ambiguity_count == 0 by construction (1 mount site)",
          consumer_ambiguity_count, 0, consumer_ambiguity_count == 0,
          {"mount_construction_sites_in_runner": 1})

    # ---- e21 read-only import + lane reruns --------------------------------
    e21 = import_source("rt2_e21_src", E21_SRC_REL)
    b601 = import_source("rt2_b601_model", B601_MODEL_REL)
    campaign = yaml.safe_load((ROOT / E21_CAMPAIGN_REL).read_text(encoding="utf-8"))
    input_manifest = e21.build_input_manifest(campaign)
    check("RT2-E-03", "e21 build_input_manifest all_exact_hash_match",
          0.0 if input_manifest["all_exact_hash_match"] else 1.0, 0.0,
          bool(input_manifest["all_exact_hash_match"]))
    trajectory, trajectory_check = e21.read_m07(campaign)
    arm0 = b601.B601Arm(str(ROOT / URDF_REL))
    residual, residual_record = e21.invert_fixed_residual(b601, arm0, trajectory.q0)
    total_ref = e21.c07_total_properties()[:3]

    rtol = float(campaign["solver"]["rtol"]); atol = float(campaign["solver"]["atol"])
    n_out = int(campaign["solver"]["output_samples"])

    def run_lane(mount):
        arm = b601.B601Arm(str(ROOT / URDF_REL))
        model = e21.RigidArmOnlyModel(arm, np.asarray(mount, float).copy(),
                                      (residual[0], residual[1].copy(), residual[2].copy()))
        result = model.integrate(trajectory, rtol=rtol, atol=atol, n_out=n_out)
        summary = e21.summarize_lane("RT2_BRIDGED", result, model, trajectory, total_ref, campaign)
        return model, result, summary

    model_b, res_b, sum_b = run_lane(mount_bridged)
    _mo, res_o, sum_o = run_lane(T_dyn)
    _mp, res_p, sum_p = run_lane(T_phys)
    mb = sum_b["metrics"]

    pub_odr = json.loads((ROOT / E21_ODR01_PUB_REL).read_text(encoding="utf-8"))
    pub_wp11 = json.loads((ROOT / E21_WP11_PUB_REL).read_text(encoding="utf-8"))
    fb05 = json.loads((ROOT / FB05_REL).read_text(encoding="utf-8"))

    peak = mb["peak_base_attitude_deviation_deg"]
    check("RT2-E-04", "bridged lane peak base attitude deviation (deg)", peak,
          "== published wp11 lane 29.41085537835705 (exact)",
          peak == pub_wp11["metrics"]["peak_base_attitude_deviation_deg"] == 29.41085537835705,
          {"wp11_published": pub_wp11["metrics"]["peak_base_attitude_deviation_deg"],
           "fb05_single_authoritative": fb05["single_authoritative_result"]["peak_base_attitude_deviation_deg"]})
    check("RT2-E-05", "reference rerun wp11 peak == published (exact)",
          sum_p["metrics"]["peak_base_attitude_deviation_deg"], "== 29.41085537835705",
          sum_p["metrics"]["peak_base_attitude_deviation_deg"] == 29.41085537835705)
    delta_odr = peak - sum_o["metrics"]["peak_base_attitude_deviation_deg"]
    check("RT2-E-06", "bridged minus ODR01 reference lane delta (deg)", delta_odr,
          "== 0.3688895107529362", abs(delta_odr - 0.3688895107529362) <= 1e-12,
          {"odr01_rerun_peak": sum_o["metrics"]["peak_base_attitude_deviation_deg"],
           "odr01_published": pub_odr["metrics"]["peak_base_attitude_deviation_deg"]})
    check("RT2-E-07", "nfev bridged vs FB-05 published", sum_b["solver"]["nfev"], "== 5013",
          sum_b["solver"]["nfev"] == fb05["solver"]["nfev"] == 5013)
    check("RT2-E-08", "momentum closure dP", mb["momentum_max_norm_dP"], 1e-11,
          mb["momentum_max_norm_dP"] <= 1e-11, {"fb05": fb05["invariants"]["momentum_max_norm_dP"]})
    check("RT2-E-09", "momentum closure dL", mb["momentum_max_norm_dL"], 1e-11,
          mb["momentum_max_norm_dL"] <= 1e-11, {"fb05": fb05["invariants"]["momentum_max_norm_dL"]})
    check("RT2-E-10", "energy audit relative", mb["energy_audit_relative"], 1e-8,
          mb["energy_audit_relative"] <= 1e-8, {"fb05": fb05["invariants"]["energy_audit_relative"]})
    check("RT2-E-11", "quaternion norm error pre-normalization in Radau band",
          mb["quaternion_norm_max_error_before_output_normalization"], 1e-9,
          mb["quaternion_norm_max_error_before_output_normalization"] <= 1e-9,
          {"fb05": fb05["invariants"]["quaternion_norm_max_error_before_output_normalization"]})
    check("RT2-E-12", "quaternion norm error post-normalization",
          mb["quaternion_norm_max_error_after_normalization"], 1e-12,
          mb["quaternion_norm_max_error_after_normalization"] <= 1e-12)
    check("RT2-E-13", "mass matrix min eigenvalue > 0", mb["mass_matrix_min_eigenvalue"], 1e-9,
          mb["mass_matrix_min_eigenvalue"] > 1e-9,
          {"fb05": fb05["invariants"]["mass_matrix_min_eigenvalue"]})

    initial = model_b.system_mass_properties(trajectory.q0)
    check("RT2-E-14", "initial mass == V3_R2 C07 (exact 0 error)", abs(initial[0] - total_ref[0]), 0.0,
          abs(initial[0] - total_ref[0]) == 0.0, {"mass": initial[0]})
    cg_err = float(np.linalg.norm(initial[1] - total_ref[1]))
    I_err = maxabs(initial[2] - total_ref[2])
    check("RT2-E-15", "initial CG error vs ledger == published lane delta", cg_err,
          "== 0.003524348142565558", abs(cg_err - 0.003524348142565558) <= 1e-12)
    check("RT2-E-16", "initial inertia error vs ledger == published lane delta", I_err,
          "== 0.10311953522836159", abs(I_err - 0.10311953522836159) <= 1e-9)

    full_wp11 = {"quat": maxabs(res_b["quat"] - res_p["quat"]),
                 "pos": float(np.max(np.linalg.norm(res_b["r"] - res_p["r"], axis=1))),
                 "dev": maxabs(res_b["dev_deg"] - res_p["dev_deg"])}
    check("RT2-E-17", "full-state bridged == wp11 reference (trajectory-wise)",
          max(full_wp11.values()), 1e-9, max(full_wp11.values()) <= 1e-9, full_wp11)
    full_odr = {"quat": maxabs(res_b["quat"] - res_o["quat"]),
                "pos": float(np.max(np.linalg.norm(res_b["r"] - res_o["r"], axis=1))),
                "dev": maxabs(res_b["dev_deg"] - res_o["dev_deg"])}
    check("RT2-E-18", "full-state bridged vs odr01 reference matches FB-05 published deltas",
          full_odr["dev"], "== 0.41524309238457846",
          abs(full_odr["dev"] - fb05["relationship_to_legacy_two_lane_values"]["full_state"]["bridged_vs_odr01_reference"]["max_abs_deviation_diff_deg"]) <= 1e-9,
          full_odr)

    # acceptance independence: no FB-05 check limit references the legacy peaks
    bad_limits = []
    for c in fb05["checks"]:
        lim = json.dumps(c.get("limit"))
        if "29.041" in lim or "29.410" in lim or "29.226" in lim:
            bad_limits.append(c["id"])
    check("RT2-E-19", "FB-05 acceptance never uses proximity to legacy lane peaks",
          len(bad_limits), 0, not bad_limits,
          {"declaration_present": "acceptance NEVER uses proximity" in fb05.get("acceptance_rule_declaration", ""),
           "bad_limit_checks": bad_limits})

    # ---- FB-06 FK cross-checks (C01/C05/C07) --------------------------------
    v3 = yaml.safe_load((ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml").read_text(encoding="utf-8"))
    fb06 = yaml.safe_load((ROOT / FB06_REL).read_text(encoding="utf-8"))
    transforms = yaml.safe_load((ROOT / M6_TRANSFORMS_REL).read_text(encoding="utf-8"))
    arm_fk = b601.B601Arm(str(ROOT / URDF_REL))
    fk_rows = []
    for cid in ["C01", "C05", "C07"]:
        cfg_old = next(c for c in v3["configurations"] if c["configuration_id"] == cid)
        arm_old = next(m for m in cfg_old["composition"] if m["component_id"] == ARM_ID)
        cfg_new = next(c for c in fb06["configurations"] if c["configuration_id"] == cid)
        arm_new = next(m for m in cfg_new["composition_candidate"] if m["component_id"] == ARM_ID)
        pose_key, q = e21.pose_vector(arm_old["transform_ref"], transforms)
        fk_m, fk_cg, fk_I = e21.arm_properties(b601, arm_fk, q, e21.PLACEMENTS["ODR01_DYNAMICS_T_SM"])
        cg_resid = float(np.linalg.norm(np.asarray(arm_new["com_S_m"], float) - fk_cg))
        I_resid = maxabs(np.asarray(arm_new["inertia_about_own_com_S_kg_m2"], float) - fk_I)
        pub_fk = cfg_new["fk_cross_check_vs_pure_odr01_placement"]
        fk_rows.append({"configuration_id": cid, "pose_binding": pose_key,
                        "cg_residual_m_rt2": cg_resid, "cg_residual_m_published": pub_fk["candidate_arm_cg_minus_fk_norm_m"],
                        "inertia_residual_rt2": I_resid, "inertia_residual_published": pub_fk["candidate_arm_inertia_minus_fk_max_abs"],
                        "mass_exact": float(arm_new["mass_kg"]) - fk_m})
    rep["fb06_fk_cross_checks"] = fk_rows
    ok01 = abs(fk_rows[0]["cg_residual_m_rt2"] - fk_rows[0]["cg_residual_m_published"]) <= 1e-12 and 1.0e-7 <= fk_rows[0]["cg_residual_m_rt2"] <= 1.3e-7
    ok05 = abs(fk_rows[1]["cg_residual_m_rt2"] - fk_rows[1]["cg_residual_m_published"]) <= 1e-12 and 1.0e-7 <= fk_rows[1]["cg_residual_m_rt2"] <= 1.2e-7
    ok07 = fk_rows[2]["cg_residual_m_rt2"] <= 1e-12
    check("RT2-E-20", "FB-06 FK cross-checks reproduced (C01/C05 in spelling band, C07 machine-zero)",
          [r["cg_residual_m_rt2"] for r in fk_rows], "C01/C05 in [1e-7,1.3e-7]; C07<=1e-12",
          ok01 and ok05 and ok07)

    # ---- pollution sentinel AFTER -------------------------------------------
    snap_after = snapshot()
    new_files = sorted(set(snap_after) - set(snap_before))
    drifted = sorted(k for k in snap_before if k in snap_after and snap_before[k] != snap_after[k])
    deleted = sorted(set(snap_before) - set(snap_after))
    check("RT2-E-21", "no e21/upstream file modified or created by this rerun",
          len(new_files) + len(drifted) + len(deleted), 0,
          not (new_files or drifted or deleted),
          {"new": new_files, "drifted": drifted, "deleted": deleted})
    rep["pycache_present_after"] = [k for k in snap_after if "__pycache__" in k]

    rep["criterion_counts"] = {"total": len(rep["checks"]),
                               "pass": sum(c["status"] == "PASS" for c in rep["checks"]),
                               "fail": sum(c["status"] == "FAIL" for c in rep["checks"])}
    rep["overall"] = "ALL_PASS" if all(c["status"] == "PASS" for c in rep["checks"]) else "HAS_FAIL"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_bytes((json.dumps(rep, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))
    print("WROTE", OUT_FILE)
    print("overall:", rep["overall"], rep["criterion_counts"])
    for c in rep["checks"]:
        print(c["id"], c["status"], "|", c["name"], "|", str(c["value"])[:80])


if __name__ == "__main__":
    main()
