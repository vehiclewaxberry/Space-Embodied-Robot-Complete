# -*- coding: utf-8 -*-
"""MPI-FB-08 gate independent verification (pure python/numpy; read-only on all upstream files).

Recomputes every load-bearing number of the MPI-FB-02..07 main chain from hash-pinned
authority sources and emits FB08_INDEPENDENT_RECOMPUTATION_V1.json.
Discipline: no CAD/FEA process; writes ONLY inside round1_bridge/08_gate/.
"""
import hashlib
import json
import math
import os
from datetime import datetime, timezone, timedelta

import numpy as np
import yaml

ROOT = r"F:/China Graduate Future Flight Vehicle Innovation Competition"
PKG = r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge"
OUT_DIR = os.path.join(ROOT, PKG, "round1_bridge", "08_gate")

P = {
    "contract": "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/00_authority/E21_AUTHORITY_CONTRACT_V1.yaml",
    "bridge": PKG + "/round1_bridge/02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml",
    "fb03": PKG + "/round1_bridge/03_validation/MPI03_BRIDGE_NUMERICAL_VALIDATION.json",
    "fb04": PKG + "/round1_bridge/04_mass/MPI04_MASS_INERTIA_BRIDGE_VALIDATION.json",
    "fb05": PKG + "/round1_bridge/05_e21_bridged/E21_BRIDGED_ARM_PLACEMENT_GATE_V2.json",
    "fb06": PKG + "/round1_bridge/06_mass_propagation/SYSTEM_MASS_PROPERTIES_BRIDGED_V1.yaml",
    "v6": PKG + "/round1_bridge/07_rebind/MECH_DYNAMICS_INTERFACE_V6_CANDIDATE.yaml",
    "r3": PKG + "/round1_bridge/07_rebind/EMBODIED_MECHANICAL_CONTRACT_R3_CANDIDATE.yaml",
    "v3r2": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml",
    "v5r2": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp10_mech_rl_v4/MECH_DYNAMICS_INTERFACE_V5_R2.yaml",
    "r2base": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp13_embodied_contract/EMBODIED_MECHANICAL_CONTRACT_R2.yaml",
    "v5gate": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/15_loop_continuation_v5/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V5.json",
    "e15gate": "30_simulation/e15_ancf_certification/results/gate_summary.json",
    "rt2": PKG + "/round1_bridge/redteam_round2/RED_TEAM_ROUND2_EXECUTION_V1.json",
    "rt2rerun": PKG + "/round1_bridge/redteam_round2/rt2_e21_rerun_output.json",
    "receipt": PKG + "/round0_handover/00_receipt/KIMI_M7_TERMINAL_HANDOVER_RECEIPT.json",
    "open_items": PKG + "/round1_bridge/00_authority/OPEN_ITEMS_UPDATE_V1.csv",
    "decision": PKG + "/round1_bridge/decisions/ENG_DECISION_DYNAMIC_MASS_ALLOCATION_V1.yaml",
    "c201": PKG + "/round1_bridge/route_c_prep/ROUTE_C_C2_01_REGISTRY_SKELETON_V1.yaml",
    "solar_build_report": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_BUILD_REPORT_V1.json",
}

UPSTREAM_PINS = {  # path -> expected sha256 (case-insensitive), from round1 pins
    P["contract"]: "7D2E0792B3FF6BAB9BD9AE11A605341B20BAAB821961A7BA8E119996D1515D81",
    P["v3r2"]: "3FD2557318E98748A37927977FA2925C18803668FE16391D824C184F646486BB",
    P["v5r2"]: "9B6D8025D3318A66AB7DD9BD15F7EEE2CDE31DD7A0A9A4FDB5CE4AEB60DE8203",
    P["r2base"]: "5DDA627794A4B29D087D7489BECC7A98ED632BC6EAC0413CD9F7226C03AE1E7C",
    P["v5gate"]: "EB7F9AA14E5F455831711089D3ED3A2C5014783E5D103E144E164AFE9CC8379B",
    P["e15gate"]: "AAB4D609E219279C2563C8A38743AC1784BBF16DE399D5B8798439B0AC2DCA80",
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/M3_interface_authority/M3R_TSM_PHYSICAL_STACK.yaml": "172F3603E458F670323925E644BC68623EE9C85FCA7AF1200FAE2576EB43C68B",
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/M3_interface_authority/M3R_TSM_FRAME_TO_FLANGE_TRANSFORM.json": "29303BA65DFD7473F2E0DBB7BFD16CF269C87EF1A336575AE054594B57BBD6CA",
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/04_configurations/F3R2_ARM_INITIAL_POSE.yaml": "D6E33CB5993BA056E1368F72487B4972E4316E83655FB5AF33035FCC1761AAE2",
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/01_system_architecture/DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml": "67293323A45237FB9B415871A4160732EFB156DE74776C9E11ABA9C4202134CA",
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp11_cad_urdf_registration/B601_CAD_URDF_GEOMETRY_CALIBRATION_V1.yaml": "7463C1309C3530A42BB32CB4A661FFA56575691DFB7A4BE801AAE9094BEB51E1",
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_OWNER_DECISION_REGISTER_V1.yaml": "F5B1572C0CFCEC35C40F262A3D7386AFA91DEC09DA94FE31FD03F5C04956F8B6",
    "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf": "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164",
    "30_simulation/sim_05_free_floating_arm/b601_model.py": "3E2B451476F437E482661E275073249AD101705251B78C042851C32AE741052F",
    "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/src/build_e21_diagnostics.py": "7EC0B2ADA7EDCD5E7F34F7E7857A9F0147A1FF633D3EC2227E939C2C62903792",
    "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results/E21_C07_R2_DEPLOYED_LOCKED_FIXED_RESIDUAL_V1.json": "2E24233D2B14D31B25876AE0943AA0FD2C7EF4418DCCE4397C3730398F571AA2",
    "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results/E21_ODR01_DYNAMICS_T_SM__M07_ARM_ONLY_RADAU_SUMMARY_V1.json": "C575F1D4F4CDDBAE9890D44379A575E28817A2586D8741FA9FEDC044AD8C038C",
    "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results/E21_WP11_PHYSICAL_GEOMETRY_CONTEXT__M07_ARM_ONLY_RADAU_SUMMARY_V1.json": "55DC3E9E36FCECA7101B5707C07E9363F73DBF1E159D07FAA3E60D049D11D6B3",
    "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results/E21_NINE_CONFIGURATION_ARM_PLACEMENT_AUDIT_V1.json": "FCCE9EFBD4010201EFC08A3A01B95DA0676F6862C071BB40E4AC1AB6ADFC2129",
    "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/config/E21_CURRENT_R2_RIGID_DIAGNOSTIC_CAMPAIGN_V1.yaml": "A344E6677AE51AD30A3CF9DE1C01F22DD0DBCEDFCFF009912852F359108A640E",
    "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results/E21_DIAGNOSTIC_GATE_V1.json": "B03B7C7AF571AA00FE3612756FFBBD99CB834B84377BA8DC2C213355C252616B",
    "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results/E21_FIXED_BASE_R2_ROM_REPRODUCTION_AND_MASS_CONFLICT_V1.json": "57958A9F3AC194893D689E9ECA4F12666474D97E0CFBB848ACBA794838B8396B",
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/FLEXIBLE_APPENDAGE_R2.yaml": "A04ACFE440C636BB095585C74F71E3563FD35F6678FCFAA39355383A9BF6B3FD",
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/FLEXIBLE_APPENDAGE_R2_MODES.json": "E068DE078A0DC680A44807516733FDF018DD720B5F65636BB2B8D21E557593B6",
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json": "D5B7DD16532FE7117D27ECC09EFB29ECC570F51928BDBDF3B27BB96C3CF12C5E",
    "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp2_mass_properties/CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml": "F43D871FAA6831652441C75916B1E890D760EAE3D5781DDF3650CFB65159DE51",
}

PKG_PRODUCT_PINS = {  # cross-referenced inside V6/R3 source registers and FB-03/04/05 reports
    P["bridge"]: "0ACEB659284CAB862BA65228C5C2DF4BEB06D9EE05B5E2F0B2B5CB38402BF72C",
    P["fb03"]: "CEBCF446F788555AFDF19D1F81A06BE64B2DC3D59B5350AED1C9EFCCD2F99D68",
    P["fb04"]: "41FCE5D7947D52A86A4A7953C360EA5A56D63E9F9635DCC4A87B4E2BB3766855",
    P["fb05"]: "7F670C69C6EDCF6CBF783DC22843C9EF53FD82FA88313E913C855FEB0A47E707",
    P["fb06"]: "E5D13A8D105B78C703EFA963BCF73714586E564F9951228AFBA9AF81ECB71528",
}

results = []
def rec(cid, name, value, limit, status, detail=None):
    results.append({"id": cid, "name": name, "value": value, "limit": limit,
                    "status": status, "detail": detail})

def sha256_of(relpath):
    h = hashlib.sha256()
    with open(os.path.join(ROOT, relpath), "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def load_yaml(relpath):
    with open(os.path.join(ROOT, relpath), encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_json(relpath):
    with open(os.path.join(ROOT, relpath), encoding="utf-8") as f:
        return json.load(f)

def rigid_inv(T):
    R = T[:3, :3]; t = T[:3, 3]
    Ti = np.eye(4); Ti[:3, :3] = R.T; Ti[:3, 3] = -R.T @ t
    return Ti

def maxabs(A):
    return float(np.max(np.abs(A)))

# ---------------------------------------------------------------- V-01 bridge rebuild
contract = load_yaml(P["contract"])
bridge = load_yaml(P["bridge"])
T_dyn = np.array(contract["placement_hypotheses"]["ODR01_DYNAMICS_T_SM"]["transform_S_A0_rows"], float)
T_phys = np.array(contract["placement_hypotheses"]["WP11_PHYSICAL_GEOMETRY_CONTEXT"]["transform_S_A0_rows"], float)
T_dyn_file = np.array(bridge["frame_semantics"]["T_S_A0_dynamics"]["transform_S_A0_rows_m"], float)
T_phys_file = np.array(bridge["frame_semantics"]["T_S_A0_physical"]["transform_S_A0_rows_m"], float)
rec("V01-01", "bridge file T_S_A0_dynamics == authority contract (max-abs)",
    maxabs(T_dyn_file - T_dyn), 0.0, "PASS" if maxabs(T_dyn_file - T_dyn) == 0.0 else "FAIL")
rec("V01-02", "bridge file T_S_A0_physical == authority contract (max-abs)",
    maxabs(T_phys_file - T_phys), 0.0, "PASS" if maxabs(T_phys_file - T_phys) == 0.0 else "FAIL")

B_rebuilt = rigid_inv(T_dyn) @ T_phys            # path A: analytic rigid inverse
B_dense = np.linalg.inv(T_dyn) @ T_phys          # path B: dense inverse
B_stored = np.array(bridge["T_PHYSICAL_TO_DYNAMIC"]["homogeneous_4x4"], float)
invB_stored = np.array(bridge["T_DYNAMIC_TO_PHYSICAL_inverse_bridge"]["homogeneous_4x4"], float)
CS_stored = np.array(bridge["S_frame_conjugate_for_S_expressed_quantities"]["C_S_homogeneous_4x4"], float)
CS_rebuilt = T_dyn @ rigid_inv(T_phys)

d1 = maxabs(B_rebuilt - B_stored)
d2 = maxabs(B_dense - B_rebuilt)
closure = maxabs(T_dyn @ B_stored - T_phys)
R_B = B_stored[:3, :3]
det_R = float(np.linalg.det(R_B))
orth = maxabs(R_B.T @ R_B - np.eye(3))
rt1 = maxabs(invB_stored @ B_stored - np.eye(4))
rt2_ = maxabs(B_stored @ invB_stored - np.eye(4))
dCS = maxabs(CS_rebuilt - CS_stored)
rec("V01-03", "B rebuilt from hash-pinned contract vs stored bridge (max-abs)", d1, 1e-15,
    "PASS" if d1 <= 1e-15 else "FAIL", {"dense_vs_rigid_path_max_abs": d2})
rec("V01-04", "closure T_dyn @ B == T_phys (max-abs)", closure, 1e-12,
    "PASS" if closure <= 1e-12 else "FAIL")
rec("V01-05", "det(R_B) - 1 (chirality +1)", det_R - 1.0, 1e-9,
    "PASS" if abs(det_R - 1.0) <= 1e-9 and det_R > 0 else "FAIL", {"det_R_B": det_R})
rec("V01-06", "max|R^T R - I|", orth, 1e-9, "PASS" if orth <= 1e-9 else "FAIL")
rec("V01-07", "roundtrip max(inv(B)@B, B@inv(B)) - I", max(rt1, rt2_), 1e-12,
    "PASS" if max(rt1, rt2_) <= 1e-12 else "FAIL", {"invB_at_B": rt1, "B_at_invB": rt2_})
rec("V01-08", "C_S conjugate rebuilt vs stored (max-abs)", dCS, 1e-12,
    "PASS" if dCS <= 1e-12 else "FAIL")

# rotation angle/axis from stored R_B
ang = math.degrees(math.acos(max(-1.0, min(1.0, (float(np.trace(R_B)) - 1.0) / 2.0))))
axis = np.array([R_B[2, 1] - R_B[1, 2], R_B[0, 2] - R_B[2, 0], R_B[1, 0] - R_B[0, 1]])
axis = axis / np.linalg.norm(axis)
q_stored = np.array(bridge["T_PHYSICAL_TO_DYNAMIC"]["quaternion_wxyz"], float)
half = math.radians(ang) / 2.0
q_rebuilt = np.array([math.cos(half), *(axis * math.sin(half))])
dq = min(maxabs(q_rebuilt - q_stored), maxabs(q_rebuilt + q_stored))
rec("V01-09", "rotation angle/axis/quaternion vs stored", dq, 1e-9,
    "PASS" if dq <= 1e-9 and maxabs(axis - np.array([0, 0, 1.0])) < 1e-9 else "FAIL",
    {"angle_deg": ang, "axis": axis.tolist(), "quat_rebuilt": q_rebuilt.tolist()})

# negative controls (mutation tests must fire)
B_neg_theta = rigid_inv(T_dyn) @ T_dyn  # identity baseline sanity replaced below
th = math.radians(25.000014)
Rz = np.array([[math.cos(th), -math.sin(th), 0], [math.sin(th), math.cos(th), 0], [0, 0, 1.0]])
B_mut_theta = np.eye(4); B_mut_theta[:3, :3] = Rz.T; B_mut_theta[:3, 3] = B_stored[:3, 3]
mut_theta = maxabs(T_dyn @ B_mut_theta - T_phys)
B_mut_t = B_stored.copy(); B_mut_t[:3, 3] = -B_stored[:3, 3]
mut_t = maxabs(T_dyn @ B_mut_t - T_phys)
R_avg = (T_dyn[:3, :3] + T_phys[:3, :3]) / 2.0
det_avg = float(np.linalg.det(R_avg))
fired = mut_theta > 1e-6 and mut_t > 1e-6 and abs(det_avg - 1.0) > 1e-6
rec("V01-10", "negative controls fire (theta flip / t flip / frame averaging det)",
    0 if fired else 1, 0, "PASS" if fired else "FAIL",
    {"theta_flipped_closure": mut_theta, "t_flipped_closure": mut_t,
     "averaged_frame_det": det_avg})

# ---------------------------------------------------------------- V-02 FB-03 recheck
fb03 = load_json(P["fb03"])
n_pass = sum(1 for c in fb03["checks"] if c["status"] == "PASS")
hm = fb03["headline_metrics"]
mism = []
if hm["det_R_B"] != det_R: mism.append("det_R_B")
if hm["max_abs_RtR_minus_I"] != orth: mism.append("max_abs_RtR_minus_I")
if hm["closure_T_dyn_at_B_minus_T_phys_max_abs"] != closure: mism.append("closure")
rec("V02-01", "FB-03 report 21/21 PASS fields", n_pass, 21,
    "PASS" if n_pass == 21 and fb03["overall"] == "PASS" else "FAIL")
rec("V02-02", "FB-03 headline metrics == FB-08 recomputation", len(mism), 0,
    "PASS" if not mism else "FAIL", {"mismatched_fields": mism})
nc = fb03["checks"][19]["detail"]  # FB03-20 negative controls
nc_fired = all(v.get("fired") for v in nc.values())
rec("V02-03", "FB-03 six mutation negative controls all fired", 0 if nc_fired else 1, 0,
    "PASS" if nc_fired else "FAIL", {"mutations": list(nc.keys())})

# ---------------------------------------------------------------- V-03 FB-04 recompute
fb04 = load_json(P["fb04"])
v3r2 = load_yaml(P["v3r2"])
cfgs_v3 = {c["configuration_id"]: c for c in v3r2["configurations"]}
C07 = cfgs_v3["C07"]
comp07 = {m["component_id"]: m for m in C07["composition"]}
arm07 = comp07["b601_complete_arm_including_gripper_urdf_links"]
m_arm = arm07["mass_kg"]
tz = float(B_stored[2, 3])
steiner = m_arm * tz * tz
rec("V03-01", "Steiner witness m*t_bridge^2 (kg m^2)", steiner, "== 0.0024302436760318276",
    "PASS" if abs(steiner - 0.0024302436760318276) < 1e-15 else "FAIL",
    {"fb04_published": 0.0024302436760318276, "diff": steiner - 0.0024302436760318276})

o2 = fb04["objects"][0]
r_A0dyn_pub = np.array(o2["r_A0dyn_m"]); r_A0phys_pub = np.array(o2["r_A0phys_m"])
r_map = (B_stored @ np.append(r_A0phys_pub, 1.0))[:3]
cg_res = maxabs(r_map - r_A0dyn_pub)
rec("V03-02", "arm CG map r_A0dyn == B @ r_A0phys (max-abs m)", cg_res, 1e-12,
    "PASS" if cg_res <= 1e-12 else "FAIL")
pm = o2["about_cg_inertia_invariants"]
rec("V03-03", "about-CG pure-rotation principal invariance (arm)",
    pm["principal_moments_max_abs_diff"], 1e-12,
    "PASS" if pm["principal_moments_max_abs_diff"] <= 1e-12 else "FAIL")
lit = o2["literal_unconjugated_formula_deviation_max_abs_FORBIDDEN_READING"]
rec("V03-04", "literal un-conjugated reading clearly nonzero (forbidden guard)",
    lit, ">1e-4", "PASS" if lit > 1e-4 else "FAIL")

# system lane re-aggregation: physical consumption = residual + C_S_inv-mapped arm
CS_inv = rigid_inv(CS_stored)
def aggregate(members):
    M = sum(mm["mass_kg"] for mm in members)
    cg = sum(mm["mass_kg"] * np.array(mm["com_S_m"]) for mm in members) / M
    I = np.zeros((3, 3))
    for mm in members:
        r = np.array(mm["com_S_m"]); d = r - cg
        I += np.array(mm["inertia_about_own_com_S_kg_m2"]) + mm["mass_kg"] * ((d @ d) * np.eye(3) - np.outer(d, d))
    return M, cg, I
residual_members = [m for cid, m in comp07.items() if cid != "b601_complete_arm_including_gripper_urdf_links"]
arm07_phys = dict(arm07)
arm07_phys["com_S_m"] = (CS_inv @ np.append(np.array(arm07["com_S_m"]), 1.0))[:3].tolist()
RCS_inv = CS_inv[:3, :3]
arm07_phys["inertia_about_own_com_S_kg_m2"] = (RCS_inv @ np.array(arm07["inertia_about_own_com_S_kg_m2"]) @ RCS_inv.T).tolist()
M_p, cg_p, I_p = aggregate(residual_members + [arm07_phys])
ld = fb04["lane_delta_explanation"]
d_mass = abs(M_p - ld["bridged_system_mass_kg"])
d_cg = maxabs(cg_p - np.array(ld["bridged_system_cg_S_m"]))
d_I = maxabs(I_p - np.array(ld["bridged_system_inertia_about_system_cg_S_kg_m2"]))
d_cg_pub = maxabs(cg_p - np.array(ld["wp11_lane_published_cg_S_m"]))
d_lane_cg = float(np.linalg.norm(cg_p - np.array(C07["cg_S_m"])))
stated_I07 = C07["inertia_about_system_cg_S_kg_m2"]
I07 = np.array([[stated_I07["Ixx"], stated_I07["Ixy"], stated_I07["Ixz"]],
                [stated_I07["Ixy"], stated_I07["Iyy"], stated_I07["Iyz"]],
                [stated_I07["Ixz"], stated_I07["Iyz"], stated_I07["Izz"]]])
d_lane_I = maxabs(I_p - I07)
ok = (d_mass == 0.0 and d_cg <= 1e-12 and d_I <= 1e-12 and d_cg_pub <= 1e-12
      and abs(d_lane_cg - 0.003524348142565558) < 1e-12
      and abs(d_lane_I - 0.10311953522836159) < 1e-10)
rec("V03-05", "WP11 physical lane re-aggregated via C_S_inv == FB-04 published", 0 if ok else 1, 0,
    "PASS" if ok else "FAIL",
    {"mass_diff": d_mass, "cg_max_abs": d_cg, "inertia_max_abs": d_I,
     "cg_vs_wp11_published_max_abs": d_cg_pub,
     "lane_delta_cg_norm_recomputed": d_lane_cg, "lane_delta_inertia_recomputed": d_lane_I})
rec("V03-06", "mass invariant exact zero (FB-04 objects)", fb04["checks"][0]["value"], 0.0,
    "PASS" if fb04["checks"][0]["value"] == 0.0 and fb04["criterion_counts"]["pass"] == 12 else "FAIL")

# ---------------------------------------------------------------- V-04 FB-05 semantics
fb05 = load_json(P["fb05"])
cs = fb05["consumption_semantics"]
rec("V04-01", "FB-05 consumer_ambiguity_count == 0", cs["consumer_ambiguity_count"], 0,
    "PASS" if cs["consumer_ambiguity_count"] == 0 else "FAIL",
    {"single_rule": cs["single_rule"], "mount_used": cs["mount_used"],
     "mount_equals_T_phys_max_abs": cs["mount_equals_T_phys_max_abs"],
     "audit_mount_sites": fb05["checks"][0]["audit"]["mount_construction_sites_in_runner"]})
rec("V04-02", "FB-05 single authoritative peak (deg) == physical lane value",
    fb05["single_authoritative_result"]["peak_base_attitude_deviation_deg"],
    "== 29.41085537835705 (NOT an acceptance anchor)",
    "PASS" if fb05["single_authoritative_result"]["peak_base_attitude_deviation_deg"] == 29.41085537835705
    and fb05["single_authoritative_result"]["standard_uncertainty"] is None else "FAIL",
    {"bridged_minus_odr01_deg": fb05["relationship_to_legacy_two_lane_values"]["bridged_minus_reference_odr01_deg"],
     "acceptance_rule": fb05["acceptance_rule_declaration"]})
inv = fb05["invariants"]
inv_ok = (inv["momentum_max_norm_dP"] <= 1e-11 and inv["momentum_max_norm_dL"] <= 1e-11
          and inv["energy_audit_relative"] <= 1e-8
          and inv["quaternion_norm_max_error_after_normalization"] <= 1e-12
          and inv["mass_matrix_min_eigenvalue"] > 0)
rec("V04-03", "FB-05 numerical invariants within limits", 0 if inv_ok else 1, 0,
    "PASS" if inv_ok else "FAIL", inv)
holds_e21 = contract["mandatory_holds"]
holds_fb05 = fb05["mandatory_holds_carried"]
rec("V04-04", "FB-05 mandatory_holds == e21 authority contract (verbatim)",
    0 if holds_fb05 == holds_e21 else 1, 0, "PASS" if holds_fb05 == holds_e21 else "FAIL",
    {"holds": holds_fb05})
rt2r = load_json(P["rt2rerun"])
rec("V04-05", "RT2 independent e21 bridged rerun 23/23 PASS", rt2r["criterion_counts"]["pass"], 23,
    "PASS" if rt2r["criterion_counts"]["pass"] == 23 and rt2r["overall"] == "ALL_PASS" else "FAIL",
    {"watch_files_count": rt2r["watch_files_count"],
     "peak": [c for c in rt2r["checks"] if c["id"] == "RT2-E-04"][0]["value"]})

# ---------------------------------------------------------------- V-05 FB-06 spot checks
fb06 = load_yaml(P["fb06"])
cfgs_b = {c["configuration_id"]: c for c in fb06["configurations"]}
mass_diffs = {cid: abs(cfgs_b[cid]["bridged_candidate"]["mass_kg"] - cfgs_v3[cid]["mass"]["value_kg"])
              for cid in sorted(cfgs_b)}
worst_mass = max(mass_diffs.values())
rec("V05-01", "FB-06 mass invariant all 9 configs (candidate - V3_R2 stated)",
    worst_mass, 0.0, "PASS" if worst_mass == 0.0 else "FAIL", mass_diffs)

def member_map(fb06cfg):
    return {m["component_id"]: m for m in fb06cfg["composition_candidate"]}

spot_details = {}
spot_ok = True
RCS = CS_stored[:3, :3]
for cid in ["C01", "C05", "C07"]:
    bc = cfgs_b[cid]; vc = cfgs_v3[cid]
    vm = {m["component_id"]: m for m in vc["composition"]}
    bm = member_map(bc)
    det = {}
    # (1) arm row transform check
    r_arm = np.array(vm["b601_complete_arm_including_gripper_urdf_links"]["com_S_m"])
    I_arm = np.array(vm["b601_complete_arm_including_gripper_urdf_links"]["inertia_about_own_com_S_kg_m2"])
    if cid in ("C01", "C05"):
        r_exp = (CS_stored @ np.append(r_arm, 1.0))[:3]
        I_exp = RCS @ I_arm @ RCS.T
    else:
        r_exp, I_exp = r_arm, I_arm
    b_arm = bm["b601_complete_arm_including_gripper_urdf_links"]
    d_r = maxabs(r_exp - np.array(b_arm["com_S_m"]))
    d_I = maxabs(I_exp - np.array(b_arm["inertia_about_own_com_S_kg_m2"]))
    det["arm_row_reexpression_cg_max_abs"] = d_r
    det["arm_row_reexpression_inertia_max_abs"] = d_I
    spot_ok &= (d_r <= 1e-12 and d_I <= 1e-12)
    # (2) arm non-bridged fields verbatim
    nv = []
    for k in vm["b601_complete_arm_including_gripper_urdf_links"]:
        if k in ("com_S_m", "inertia_about_own_com_S_kg_m2"):
            continue
        if k not in b_arm or b_arm[k] != vm["b601_complete_arm_including_gripper_urdf_links"][k]:
            nv.append(k)
    det["arm_nonbridged_fields_mismatch"] = nv
    spot_ok &= (len(nv) == 0)
    # (3) non-arm members verbatim (subset deep equality)
    na = []
    for mcid, mm in vm.items():
        if mcid == "b601_complete_arm_including_gripper_urdf_links":
            continue
        for k, v in mm.items():
            if mcid not in bm or k not in bm[mcid] or bm[mcid][k] != v:
                na.append((mcid, k))
    det["non_arm_member_mismatch"] = na
    spot_ok &= (len(na) == 0)
    # (4) re-aggregate candidate and compare with stated bridged totals
    M_b, cg_b, I_b = aggregate(list(bm.values()))
    det["reagg_mass_diff"] = abs(M_b - bc["bridged_candidate"]["mass_kg"])
    det["reagg_cg_max_abs"] = maxabs(cg_b - np.array(bc["bridged_candidate"]["cg_S_m"]))
    det["reagg_inertia_max_abs"] = maxabs(I_b - np.array(bc["bridged_candidate"]["inertia_about_system_cg_S_kg_m2"]))
    spot_ok &= (det["reagg_mass_diff"] == 0.0 and det["reagg_cg_max_abs"] <= 1e-12
                and det["reagg_inertia_max_abs"] <= 1e-9)
    # (5) delta explanation: candidate - stated == arm-row-only action
    M_l, cg_l, I_l = aggregate(list(vm.values()))
    dcg = cg_b - cg_l
    dI = I_b - I_l
    expl = bc["bridge_explanation_of_deltas"]
    det["delta_cg_explained_residual"] = maxabs(dcg - np.array(expl["delta_cg_total_m"]))
    det["delta_inertia_explained_residual"] = abs(maxabs(dI) - expl["delta_inertia_total_max_abs"])
    spot_ok &= (det["delta_cg_explained_residual"] <= 1e-12
                and det["delta_inertia_explained_residual"] <= 1e-9)
    # (6) pose status carried verbatim
    det["pose_status_carried"] = bc["arm_pose_status_carried_verbatim"]
    det["pose_status_matches_v3r2"] = (
        bc["arm_pose_status_carried_verbatim"] == vm["b601_complete_arm_including_gripper_urdf_links"].get("pose_status"))
    spot_ok &= det["pose_status_matches_v3r2"]
    # (7) SPD of recomputed candidate inertia
    det["reagg_candidate_min_eigenvalue"] = float(np.min(np.linalg.eigvalsh(I_b)))
    spot_ok &= det["reagg_candidate_min_eigenvalue"] > 0
    spot_details[cid] = det
rec("V05-02", "FB-06 spot re-aggregation + bridge action C01/C05/C07", 0 if spot_ok else 1, 0,
    "PASS" if spot_ok else "FAIL", spot_details)

c0709_zero = all(cfgs_b[c]["candidate_minus_stated"]["mass_exact"] == 0.0
                 and cfgs_b[c]["candidate_minus_stated"]["cg_norm_m"] == 0.0
                 and cfgs_b[c]["candidate_minus_stated"]["inertia_max_abs"] == 0.0
                 for c in ["C07", "C08", "C09"])
rec("V05-03", "C07..C09 candidate totals identical to stated (exact 0)", 0 if c0709_zero else 1, 0,
    "PASS" if c0709_zero else "FAIL")
fk = {c["configuration_id"]: (c["fk_residual_cg_m"], c["fk_residual_inertia_max_abs"])
      for c in fb06["summary_by_configuration"]}
fk_ok = (1.0e-7 <= fk["C01"][0] <= 1.3e-7 and 1.0e-7 <= fk["C05"][0] <= 1.3e-7
         and fk["C07"][0] <= 1e-12)
rec("V05-04", "FK residuals: C01/C05 in registered spelling band; C07 machine-zero",
    0 if fk_ok else 1, 0, "PASS" if fk_ok else "FAIL", fk)
rec("V05-05", "FB-06 gate_checks 8/8 PASS fields",
    sum(1 for c in fb06["gate_checks"] if c["status"] == "PASS"), 8,
    "PASS" if all(c["status"] == "PASS" for c in fb06["gate_checks"]) and fb06["overall"] == "PASS" else "FAIL")

# ---------------------------------------------------------------- V-06 FB-07 candidates
v6 = load_yaml(P["v6"]); r3 = load_yaml(P["r3"])
v5gate = load_json(P["v5gate"]); r2base = load_yaml(P["r2base"])
ok_v6 = (v6.get("candidate") is True and v6["next_stage_authorized"] is False
         and v6["release_credit"] is False
         and v6["replaced_sections"]["frame_authority"]["new_in_this_candidate"]["installation_bridge"]["sha256"]
         == "0ACEB659284CAB862BA65228C5C2DF4BEB06D9EE05B5E2F0B2B5CB38402BF72C")
ok_r3 = (r3.get("candidate") is True and r3["next_stage_authorized"] is False
         and r3["release_credit"] is False
         and r3["replaced_sections"]["authority_hierarchy"]["new_in_this_candidate"]["mount_level_installation_bridge"]["sha256"]
         == "0ACEB659284CAB862BA65228C5C2DF4BEB06D9EE05B5E2F0B2B5CB38402BF72C")
rec("V06-01", "V6/R3 candidates: flags + bridge sha pin", 0 if (ok_v6 and ok_r3) else 1, 0,
    "PASS" if ok_v6 and ok_r3 else "FAIL")
carries = {
    "v6_e21_holds": v6["carried_verbatim_from_e21_authority"]["mandatory_holds"] == holds_e21,
    "r3_e21_holds": r3["carried_verbatim_from_e21_authority"]["mandatory_holds"] == holds_e21,
    "v6_v5_invariants": v6["carried_verbatim_from_v5_gate"]["fail_closed_invariants"] == v5gate["fail_closed_invariants"],
    "r3_v5_invariants": r3["carried_verbatim_from_v5_gate"]["fail_closed_invariants"] == v5gate["fail_closed_invariants"],
    "r3_r2_holds": r3["carried_verbatim_from_r2_base"]["retained_holds"] == r2base["retained_holds"],
    "r3_r2_prohibitions": r3["carried_verbatim_from_r2_base"]["prohibitions_honored"] == r2base["prohibitions_honored"],
}
rec("V06-02", "V6/R3 verbatim carries (e21 holds 11, V5 invariants 11, R2 holds 11, R2 prohibitions 8)",
    sum(carries.values()), 6, "PASS" if all(carries.values()) else "FAIL", carries)
receipt = load_json(P["receipt"])
rec_text = json.dumps(receipt)
base_hash_ok = ("9B6D8025D3318A66AB7DD9BD15F7EEE2CDE31DD7A0A9A4FDB5CE4AEB60DE8203" in rec_text
                and "5DDA627794A4B29D087D7489BECC7A98ED632BC6EAC0413CD9F7226C03AE1E7C" in rec_text
                and sha256_of(P["v5r2"]).upper() == "9B6D8025D3318A66AB7DD9BD15F7EEE2CDE31DD7A0A9A4FDB5CE4AEB60DE8203"
                and sha256_of(P["r2base"]).upper() == "5DDA627794A4B29D087D7489BECC7A98ED632BC6EAC0413CD9F7226C03AE1E7C")
rec("V06-03", "R2 base files (V5_R2 / R2) byte-unchanged vs round0 receipt pins",
    0 if base_hash_ok else 1, 0, "PASS" if base_hash_ok else "FAIL")

# ---------------------------------------------------------------- V-07 discipline scan
def walk_numbers(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from walk_numbers(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk_numbers(v)
    elif isinstance(o, (int, float)) and not isinstance(o, bool):
        yield float(o)

odr01_cg = np.array(C07["cg_S_m"])
wp11_cg = np.array(ld["wp11_lane_published_cg_S_m"])
mid_cg = (odr01_cg + wp11_cg) / 2.0
odr01_I = I07
wp11_I = np.array(ld["bridged_system_inertia_about_system_cg_S_kg_m2"])
mid_I = (odr01_I + wp11_I) / 2.0
blacklist = {"averaged_peak_deg": 29.226410622980581, "legacy_24kg": 24.0,
             "r1_panel_mass": 0.3483933, "r1_panel_inertia": 1.7419665}
blacklist.update({f"cg_midpoint_{i}": float(v) for i, v in enumerate(mid_cg)})
blacklist.update({f"inertia_midpoint_{i}": float(v) for i, v in enumerate(mid_I.flatten())})
scan_files = [P["bridge"], P["fb03"], P["fb04"], P["fb05"], P["fb06"], P["v6"], P["r3"]]
hits = []
for rel in scan_files:
    obj = load_yaml(rel) if rel.endswith(".yaml") else load_json(rel)
    for val in walk_numbers(obj):
        for name, target in blacklist.items():
            if target != 0.0 and abs(val - target) <= 1e-9 * abs(target):
                hits.append({"file": rel, "blacklist": name, "value": val})
            elif target == 0.0 and val == 0.0:
                pass
# 24.0 exact hits: only flag in mass-ish context is impossible to auto-classify; report all
rec("V07-01", "numeric blacklist scan on 7 main-chain products (avg/midpoint/legacy values)",
    len(hits), 0, "PASS" if len(hits) == 0 else "FAIL", hits)
kw_hits = []
for rel in scan_files:
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            low = line.lower()
            if any(k in low for k in ("averag", "midpoint", "blend")):
                kw_hits.append({"file": os.path.basename(rel), "line": ln, "text": line.strip()})
# every hit must be a prohibition / negation / declaration-false / detector-name context
markers = ("no ", "not ", "never", "forbidden", "prohibition", "nonclaim", "禁止",
           ": false", "detector", "_det", "scan", "blacklist", "mutation", "without")
bad_hits = [h for h in kw_hits if not any(m in h["text"].lower() for m in markers)]
rec("V07-02", "keyword scan (averag*/midpoint/blend) all in prohibition/negation context",
    len(bad_hits), 0,
    "PASS" if not bad_hits else "FAIL",
    {"total_hits": len(kw_hits), "unclassified_hits": bad_hits,
     "hits": [{k: (v[:160] + "..." if k == "text" and len(v) > 160 else v) for k, v in h.items()} for h in kw_hits]})
null_ok = (fb05["single_authoritative_result"]["standard_uncertainty"] is None
           and v6["replaced_sections"]["frame_authority"]["new_in_this_candidate"]
           ["single_consumption_semantics_block"]["legacy_dual_lane_values_retained_as_evidence_not_anchors"]["delta_nature"].endswith("standard_uncertainty=null"))
rec("V07-03", "branch delta never re-labeled as uncertainty (standard_uncertainty stays null)",
    0 if null_ok else 1, 0, "PASS" if null_ok else "FAIL")
mm_hits = []
for rel in [P["v6"], P["r3"]]:
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            if "measured_mass" in line:
                mm_hits.append({"file": os.path.basename(rel), "line": ln, "text": line.strip()[:120]})
mm_allowed = all("no measured_mass" in h["text"] for h in mm_hits)
rec("V07-04", "no measured_mass field introduced in V6/R3 (hits only in prohibition text)",
    len(mm_hits), "prohibition-only", "PASS" if mm_allowed else "FAIL", mm_hits)

# ---------------------------------------------------------------- V-08 hash chain
hash_results = {}
n_mismatch = 0
for rel, expect in {**UPSTREAM_PINS, **PKG_PRODUCT_PINS}.items():
    actual = sha256_of(rel).upper()
    ok = actual == expect.upper()
    hash_results[rel] = {"expected": expect.upper(), "actual": actual, "match": ok}
    n_mismatch += 0 if ok else 1
rec("V08-01", "hash chain: 26 upstream pins + 5 package product pins recomputed",
    n_mismatch, 0, "PASS" if n_mismatch == 0 else "FAIL",
    {"checked": len(hash_results),
     "mismatches": [k for k, v in hash_results.items() if not v["match"]]})
solar_actual = sha256_of(P["solar_build_report"]).upper()
oi01 = (solar_actual == "6160C1D0970B7EA19075B4A83C988C16CA2F1AFCA782BCAD90A89B14F17E6586"
        and solar_actual != "AFE4CA26A2CC7A1838DEF4FAD3E068DB1F364F4265A85903D9407D462711CEC9")
rec("V08-02", "OI-R1-01: solar build report self-hash DRIFT reproduced as registered (no new drift)",
    0 if oi01 else 1, 0, "PASS" if oi01 else "FAIL",
    {"recomputed": solar_actual,
     "self_recorded_never_matchable": "AFE4CA26A2CC7A1838DEF4FAD3E068DB1F364F4265A85903D9407D462711CEC9",
     "disposition": "AWAITING_UPSTREAM_ERRATUM (registered open item; both real artifacts recompute PASS per receipt)"})

# ---------------------------------------------------------------- V-09 ambiguity synthesis
bridge_definers = []
bridge_citers = []
for dirpath, _, files in os.walk(os.path.join(ROOT, PKG)):
    for fn in files:
        rel = os.path.relpath(os.path.join(dirpath, fn), ROOT)
        if "08_gate" in rel:
            continue
        with open(os.path.join(dirpath, fn), encoding="utf-8", errors="ignore") as f:
            txt = f.read()
        if "T_PHYSICAL_TO_DYNAMIC" in txt:
            if "schema: B601_PHYSICAL_DYNAMICS_BRIDGE_V1" in txt:
                bridge_definers.append(rel)
            else:
                bridge_citers.append(rel)
frame_amb_ok = (len(bridge_definers) == 1)
rec("V09-01", "frame_ambiguity: exactly one bridge definition file; all others cite it",
    len(bridge_definers), 1, "PASS" if frame_amb_ok else "FAIL",
    {"definition_file": bridge_definers, "citing_files_count": len(bridge_citers)})
cac_values = []
for rel in [P["fb05"], P["v6"], P["r3"]]:
    obj = load_yaml(rel) if rel.endswith(".yaml") else load_json(rel)
    def find_cac(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "consumer_ambiguity_count":
                    cac_values.append((os.path.basename(rel), v))
                else:
                    find_cac(v)
        elif isinstance(o, list):
            for v in o:
                find_cac(v)
    find_cac(obj)
cac_ok = all(v == 0 for _, v in cac_values) and len(cac_values) >= 3
rec("V09-02", "consumer_ambiguity_count field == 0 in FB-05/V6/R3 (semantic audit: single mount site, single rule)",
    0 if cac_ok else 1, 0, "PASS" if cac_ok else "FAIL", {"occurrences": cac_values})
sem_ok = all(cfgs_b[c]["candidate_semantics"].startswith("SINGLE_ODR01_DYNAMICS_CONSUMPTION") for c in cfgs_b)
rec("V09-03", "FB-06 9/9 configs single consumption semantics via unique bridge",
    sum(1 for c in cfgs_b if cfgs_b[c]["candidate_semantics"].startswith("SINGLE_ODR01")), 9,
    "PASS" if sem_ok else "FAIL")

# ---------------------------------------------------------------- V-10 gate-level states
v5_state = {"gate": v5gate.get("gate"), "next_stage_authorized": v5gate.get("next_stage_authorized"),
            "single_consumption_rule_resolved": v5gate.get("m7_r2_arm_placement_consumption", {}).get("single_consumption_rule_resolved")}
e15 = load_json(P["e15gate"])
e15_state = e15.get("overall")
decision = load_yaml(P["decision"])
c201 = load_yaml(P["c201"])
c201_entries = c201.get("entries", c201.get("registry", []))
c201_all_hold = True
c201_detail = "entries key not found; text-level check"
txt = open(os.path.join(ROOT, P["c201"]), encoding="utf-8").read()
c201_all_hold = ("status: HOLD" in txt) and ("value: null" in txt) and ("status: AVAILABLE" not in txt)
c201_detail = {"contains_HOLD": "status: HOLD" in txt, "contains_null": "value: null" in txt,
               "contains_AVAILABLE": "status: AVAILABLE" in txt}
state_ok = (v5_state["gate"] == "HOLD" and v5_state["next_stage_authorized"] is False
            and v5_state["single_consumption_rule_resolved"] is False
            and e15_state == "REPEAT_ANCF_CERTIFICATION"
            and decision["status"].startswith("ISSUED_AND_EFFECTIVE_AT_ENGINEERING_LEVEL")
            and decision["review_status"] == "PENDING_OWNER_REVIEW"
            and c201_all_hold)
rec("V10-01", "gate-level states: V5 HOLD / e15 REPEAT / MC-A engineering-effective / C2-01 all null+HOLD",
    0 if state_ok else 1, 0, "PASS" if state_ok else "FAIL",
    {"v5_gate": v5_state, "e15_overall": e15_state,
     "decision_status": decision["status"], "c2_01": c201_detail})

# ---------------------------------------------------------------- summary
n_pass = sum(1 for r in results if r["status"] == "PASS")
n_fail = sum(1 for r in results if r["status"] == "FAIL")
out = {
    "schema": "FB08_INDEPENDENT_RECOMPUTATION_V1",
    "generated_local": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
    "generator": "KIMI M7 MPI-FB-08 gate assembly agent (pure python 3.13.9 + numpy 2.3.5 + pyyaml 6.0.3; read-only upstream; no CAD/FEA)",
    "checks": results,
    "criterion_counts": {"total": len(results), "pass": n_pass, "fail": n_fail},
    "overall": "PASS" if n_fail == 0 else "FAIL",
    "bottom_line_metrics": {
        "frame_ambiguity": 0 if frame_amb_ok else 1,
        "mass_inconsistency": worst_mass,
        "inertia_inconsistency_unexplained_residual": max(
            spot_details[c]["delta_inertia_explained_residual"] for c in spot_details),
        "consumer_ambiguity": 0 if (cac_ok and cs["consumer_ambiguity_count"] == 0) else 1,
        "hash_mismatch": n_mismatch,
    },
    "next_stage_authorized": False,
    "release_credit": False,
}
with open(os.path.join(OUT_DIR, "FB08_INDEPENDENT_RECOMPUTATION_V1.json"), "w", encoding="utf-8", newline="\n") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
print(json.dumps({"overall": out["overall"], "pass": n_pass, "fail": n_fail,
                  "bottom_line": out["bottom_line_metrics"]}, indent=2))
for r in results:
    if r["status"] != "PASS":
        print("FAIL:", r["id"], r["name"], r.get("detail"))
