# -*- coding: utf-8 -*-
"""RED_TEAM_FLEX_PHASE_RECOMPUTE_V1 (AGENT-4 / Wave-3a red team, flexible phase).

Pure-python (stdlib + numpy + scipy + pyyaml) independent recomputation for:
  (1) MC-A ruling ENG_DECISION_DYNAMIC_MASS_ALLOCATION_V1.yaml attack surface
  (2) MPI-FB-08 gate MPI_BRIDGE_GATE_V1.json / FB08_INDEPENDENT_RECOMPUTATION_V1.json attack surface
Read-only on every upstream file. Writes NOTHING outside this directory; prints one JSON blob to stdout.
"""
import hashlib, json, math, os, sys
import numpy as np
from scipy.linalg import eigh
import yaml

ROOT = r"F:/China Graduate Future Flight Vehicle Innovation Competition"
P = {
    "bridge":   r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml",
    "contract": r"30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/00_authority/E21_AUTHORITY_CONTRACT_V1.yaml",
    "e21rom":   r"30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results/E21_FIXED_BASE_R2_ROM_REPRODUCTION_AND_MASS_CONFLICT_V1.json",
    "e21gate":  r"30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results/E21_DIAGNOSTIC_GATE_V1.json",
    "r2yaml":   r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/FLEXIBLE_APPENDAGE_R2.yaml",
    "r2modes":  r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/FLEXIBLE_APPENDAGE_R2_MODES.json",
    "r2mass":   r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json",
    "r2build":  r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_BUILD_REPORT_V1.json",
    "e15gate":  r"30_simulation/e15_ancf_certification/results/gate_summary.json",
    "decision": r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/decisions/ENG_DECISION_DYNAMIC_MASS_ALLOCATION_V1.yaml",
    "memo":     r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/r2_flex_prep/R2_FLEX_MASS_ALLOCATION_RULING_OPTIONS_V1.md",
    "inventory":r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round0_handover/03_r2_flex_inputs/R2_FLEX_INPUT_INVENTORY_V1.json",
    "spec":     r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/r2_flex_prep/R2_ROM_PARTICIPATION_DAMPING_SPEC_DRAFT_V1.md",
    "e15spec":  r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/r2_flex_prep/E15_RECERTIFICATION_TEST_SPEC_DRAFT_V1.md",
    "openitems":r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/00_authority/OPEN_ITEMS_AND_ECR_REGISTER_V1.csv",
    "v5gate":   r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/15_loop_continuation_v5/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V5.json",
    "fb03":     r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/03_validation/MPI03_BRIDGE_NUMERICAL_VALIDATION.json",
    "fb04":     r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/04_mass/MPI04_MASS_INERTIA_BRIDGE_VALIDATION.json",
    "fb05":     r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/05_e21_bridged/E21_BRIDGED_ARM_PLACEMENT_GATE_V2.json",
    "fb06":     r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/06_mass_propagation/SYSTEM_MASS_PROPERTIES_BRIDGED_V1.yaml",
    "v6":       r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/07_rebind/MECH_DYNAMICS_INTERFACE_V6_CANDIDATE.yaml",
    "r3":       r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/07_rebind/EMBODIED_MECHANICAL_CONTRACT_R3_CANDIDATE.yaml",
    "gate":     r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/08_gate/MPI_BRIDGE_GATE_V1.json",
    "fb08":     r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/08_gate/FB08_INDEPENDENT_RECOMPUTATION_V1.json",
}

def sha256(rel):
    h = hashlib.sha256()
    with open(os.path.join(ROOT, rel), "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()

def load_json(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)

def load_yaml(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return yaml.safe_load(f)

out = {"hash_pins": {}, "mca_attacks": {}, "fb08_attacks": {}}

# ---------------------------------------------------------------- hash pins
expect = {
    "bridge":   "0ACEB659284CAB862BA65228C5C2DF4BEB06D9EE05B5E2F0B2B5CB38402BF72C",
    "contract": "7D2E0792B3FF6BAB9BD9AE11A605341B20BAAB821961A7BA8E119996D1515D81",
    "e21rom":   "57958A9F3AC194893D689E9ECA4F12666474D97E0CFBB848ACBA794838B8396B",
    "e21gate":  "B03B7C7AF571AA00FE3612756FFBBD99CB834B84377BA8DC2C213355C252616B",
    "r2yaml":   "A04ACFE440C636BB095585C74F71E3563FD35F6678FCFAA39355383A9BF6B3FD",
    "r2modes":  "E068DE078A0DC680A44807516733FDF018DD720B5F65636BB2B8D21E557593B6",
    "r2mass":   "D5B7DD16532FE7117D27ECC09EFB29ECC570F51928BDBDF3B27BB96C3CF12C5E",
    "e15gate":  "AAB4D609E219279C2563C8A38743AC1784BBF16DE399D5B8798439B0AC2DCA80",
    "memo":     "F68EA9C0DE51BC5002CE9B8273734C18265BC814DA300AA4DEAF8E55D5B8A6AC",
    "inventory":"82DED34930694831AE9A03C1F6E1888C7B4577BA27F17098BBAFA8C16E4A00AD",
    "spec":     "E3453EFBFF644FA499AD2453E63621F710AC2B0BDB6F56798AA2B0D14B929E18",
    "e15spec":  "FBC90E00C5C2775635B0ECAFA53C3A9F54F82E61B756F9A00EAA8B64633DA369",
    "openitems":"5B31D0506CBBD198980A1015ACE2893FF397EB81B4B1FDB4120CBB8914E910AD",
    "fb03":     "CEBCF446F788555AFDF19D1F81A06BE64B2DC3D59B5350AED1C9EFCCD2F99D68",
    "fb04":     "41FCE5D7947D52A86A4A7953C360EA5A56D63E9F9635DCC4A87B4E2BB3766855",
    "fb05":     "7F670C69C6EDCF6CBF783DC22843C9EF53FD82FA88313E913C855FEB0A47E707",
    "fb06":     "E5D13A8D105B78C703EFA963BCF73714586E564F9951228AFBA9AF81ECB71528",
    "v6":       "4C52A68AA6E0749A2425D9E8CDB6C9F4477F5D4047C9D6C0BA6F0D95E97D184D",
    "r3":       "F3D6EC1D370FB26215A259391D5026CA4C261C7C4880AE6FD70AE2C0F0DDFC56",
    "gate":     None,  # self-hash excluded; record only
    "fb08":     "A5678600AE04EA329D627912C6ED0728943F1E2795160DDFB2CF9697B318F44D",
}
for k, rel in P.items():
    try:
        got = sha256(rel)
        exp = expect.get(k)
        out["hash_pins"][k] = {"sha256": got, "expected": exp,
                               "match": (None if exp is None else (got == exp))}
    except Exception as e:
        out["hash_pins"][k] = {"error": str(e)}

# OI-R1-01 drift sentinel
try:
    out["hash_pins"]["r2build_drift"] = {
        "sha256_recomputed": out["hash_pins"].get("r2build", {}).get("sha256") or sha256(P["r2build"]),
        "expected_registered_drift": "6160C1D0970B7EA19075B4A83C988C16CA2F1AFCA782BCAD90A89B14F17E6586",
        "self_recorded_never_matchable": "AFE4CA26A2CC7A1838DEF4FAD3E068DB1F364F4265A85903D9407D462711CEC9"}
except Exception as e:
    out["hash_pins"]["r2build_drift"] = {"error": str(e)}

# ---------------------------------------------------------------- load sources
rom   = load_json(P["e21rom"])
modes = load_json(P["r2modes"])
mass  = load_json(P["r2mass"])
dec   = load_yaml(P["decision"])
br    = load_yaml(P["bridge"])
ctr   = load_yaml(P["contract"])
fb06  = load_yaml(P["fb06"])

M   = np.array(rom["leaf_only"]["Mqq_kg_m2"], float)          # full precision e21
Mp  = np.array(rom["leaf_only"]["published_Mqq_kg_m2"], float)
Mst = np.array(rom["nonselecting_conflict_diagnostic"]["Mqq_star_kg_m2"], float)
dM  = np.array(rom["nonselecting_conflict_diagnostic"]["Mqq_star_minus_leaf_only_kg_m2"], float)

A = out["mca_attacks"]
# A1 deltaM internal consistency + vs decision verbatim
A["A1_deltaM_consistency"] = {
    "max_abs_(Mstar-M)-dM": float(np.max(np.abs((Mst - M) - dM))),
    "dM": dM.tolist(),
    "decision_delta_M": dec["ruling"]["delta_M_excluded_from_rom_kg_m2"],
    "decision_matches_max_abs": float(np.max(np.abs(dM - np.array(dec["ruling"]["delta_M_excluded_from_rom_kg_m2"], float)))),
}
# A2 authoritative Mqq vs published card
A["A2_authoritative_Mqq_vs_published"] = {
    "max_abs_e21full_vs_published": float(np.max(np.abs(M - Mp))),
    "e21_claimed_published_err": rom["leaf_only"]["published_mass_matrix_max_abs_error_kg_m2"],
    "decision_Mqq_vs_published_card_max_abs": float(np.max(np.abs(
        np.array(dec["ruling"]["authoritative_Mqq_kg_m2_published"], float) -
        np.array(load_yaml(P["r2yaml"])["wing_L2_reduced_model"]["mass_matrix_kgm2"], float)))),
}
# A3/A4/A5 five-case eigen, both lanes, shifts
cases = {}
for c in rom["leaf_only"]["cases"]:
    name = c["case"]
    K = np.array(c["K_Nm_per_rad"], float)
    w2_leaf, _ = eigh(K, Mp)
    f_leaf = np.sqrt(np.maximum(w2_leaf, 0.0)) / (2 * math.pi)
    w2_star, _ = eigh(K, Mst)
    f_star = np.sqrt(np.maximum(w2_star, 0.0)) / (2 * math.pi)
    pub = np.array(c["published_hz"], float)
    e21_leaf = np.array(c["leaf_only_reproduced_hz"], float)
    e21_star = np.array(c["moving_inter_hinge_mass_conflict_hz"], float)
    shift = (f_star - f_leaf) / f_leaf * 100.0
    rev = (f_leaf / f_star - 1.0) * 100.0
    cases[name] = {
        "rt_leaf_hz": f_leaf.tolist(),
        "rt_minus_published_max_abs_hz": float(np.max(np.abs(f_leaf - pub))),
        "rt_minus_e21leaf_max_abs_hz": float(np.max(np.abs(f_leaf - e21_leaf))),
        "rt_star_hz": f_star.tolist(),
        "rt_minus_e21star_max_abs_hz": float(np.max(np.abs(f_star - e21_star))),
        "rt_shift_pct": shift.tolist(),
        "rt_reverse_framing_pct": rev.tolist(),
    }
A["A3A4A5_five_case_eigen"] = cases
A["A5_shift_pct_vs_decision"] = {
    "decision": dec["nominal_frequency_basis_registration"]["bookkeeping_difference_entry"]["five_case_relative_shift_pct_recomputed"],
    "max_abs_diff_pct_point": float(max(
        abs(a - b) for name, d in cases.items()
        for a, b in zip(d["rt_shift_pct"], dec["nominal_frequency_basis_registration"]["bookkeeping_difference_entry"]["five_case_relative_shift_pct_recomputed"][name]))),
}
A["A6_reverse_framing_nominal_pct"] = {
    "rt": cases["nominal"]["rt_reverse_framing_pct"],
    "decision_note": "leaf-only vs conflict +3.64/+7.46/+15.47",
}
A["A8_e21_claims"] = {
    "G20_max_abs_error_hz_claimed": 4.840419126761475e-05,
    "rt_max_abs_error_hz": float(max(c["rt_minus_published_max_abs_hz"] for c in cases.values())),
    "G19_mass_err_claimed": 4.999999997368221e-10,
}
# A7 mass closure arithmetic
mm = mass["mass_model"]
wing = 3 * mm["leaf_kg"] + mm["hinge_root_kg"] + 2 * mm["hinge_inter_kg_each"] + mm["hdrm_per_wing_kg"] + mm["harness_per_wing_kg"]
sd = mass["system_delta"]
A["A7_mass_closure"] = {
    "wing_kg_recomputed": wing,
    "wing_kg_published": 0.78,
    "two_wings_kg": 2 * wing,
    "delta_vs_r1_kg": 1.56 - sd["legacy_r1_both_wings_kg"],
    "delta_published_kg": sd["delta_kg"],
    "whole_sat_recomputed": sd["whole_sat_legacy_kg"] + sd["delta_kg"],
    "whole_sat_published": sd["whole_sat_with_r2_kg"],
}
# A9 capture band first-mode shift range
first_shifts = [cases[n]["rt_shift_pct"][0] for n in cases]
A["A9_first_mode_band"] = {
    "leaf_first_mode_band_hz": [min(cases[n]["rt_leaf_hz"][0] for n in cases), max(cases[n]["rt_leaf_hz"][0] for n in cases)],
    "conflict_first_mode_band_hz": [min(cases[n]["rt_star_hz"][0] for n in cases), max(cases[n]["rt_star_hz"][0] for n in cases)],
    "first_mode_shift_pct_minmax": [min(first_shifts), max(first_shifts)],
}

# ---------------------------------------------------------------- FB-08 attacks
B = out["fb08_attacks"]
Tdyn  = np.array(ctr["placement_hypotheses"]["ODR01_DYNAMICS_T_SM"]["transform_S_A0_rows"], float)
Tphys = np.array(ctr["placement_hypotheses"]["WP11_PHYSICAL_GEOMETRY_CONTEXT"]["transform_S_A0_rows"], float)
B_stored = np.array(br["T_PHYSICAL_TO_DYNAMIC"]["homogeneous_4x4"], float)
# B2 rebuild via rigid inverse
R = Tdyn[:3, :3]; t = Tdyn[:3, 3]
Tdyn_inv = np.eye(4); Tdyn_inv[:3, :3] = R.T; Tdyn_inv[:3, 3] = -R.T @ t
B_rebuilt = Tdyn_inv @ Tphys
B["B2_bridge_rebuild_vs_stored_max_abs"] = float(np.max(np.abs(B_rebuilt - B_stored)))
# B3 closure
B["B3_closure_Tdyn_at_B_minus_Tphys_max_abs"] = float(np.max(np.abs(Tdyn @ B_stored - Tphys)))
# B4 det / orthogonality / roundtrip
RB = B_stored[:3, :3]
Binv = np.eye(4); Binv[:3, :3] = RB.T; Binv[:3, 3] = -RB.T @ B_stored[:3, 3]
B["B4_det_minus_1"] = float(np.linalg.det(RB) - 1.0)
B["B4_RtR_minus_I_max_abs"] = float(np.max(np.abs(RB.T @ RB - np.eye(3))))
B["B4_roundtrip_max_abs"] = float(max(np.max(np.abs(Binv @ B_stored - np.eye(4))),
                                      np.max(np.abs(B_stored @ Binv - np.eye(4)))))
# B5 derived angle/axis
ang = math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(RB) - 1.0) / 2.0))))
B["B5_derived_angle_deg"] = ang
B["B5_axis"] = (np.array([RB[2, 1] - RB[1, 2], RB[0, 2] - RB[2, 0], RB[1, 0] - RB[0, 1]]) / (2 * math.sin(math.radians(ang)))).tolist()
# closed form vs stored
th = math.radians(25.000014)
B_cf = np.array([[math.cos(th), -math.sin(th), 0, 0], [math.sin(th), math.cos(th), 0, 0], [0, 0, 1, 0.02275], [0, 0, 0, 1.0]])
B["B5_closedform_vs_stored_max_abs"] = float(np.max(np.abs(B_cf - B_stored)))
# B6 Steiner witness with arm mass from FB-06 member row
arm_member = None
for cfg in fb06["configurations"]:
    if cfg["configuration_id"] == "C01":
        for m_ in cfg["composition_candidate"]:
            if "arm" in m_["component_id"]:
                arm_member = m_
m_arm = arm_member["mass_kg"]
B["B6_steiner_witness"] = {"m_arm_kg": m_arm, "t_m": 0.02275,
                           "m_t2": m_arm * 0.02275 ** 2,
                           "fb04_published": 0.0024302436760318276,
                           "diff": m_arm * 0.02275 ** 2 - 0.0024302436760318276}
# B7 FB-06 supplementary spot re-aggregation C02/C06 (FB-08 did C01/C05/C07)
def reaggregate(cfg):
    Mtot = sum(m_["mass_kg"] for m_ in cfg["composition_candidate"])
    cg = sum(m_["mass_kg"] * np.array(m_["com_S_m"], float) for m_ in cfg["composition_candidate"]) / Mtot
    I = np.zeros((3, 3))
    for m_ in cfg["composition_candidate"]:
        mi = m_["mass_kg"]; ri = np.array(m_["com_S_m"], float) - cg
        Ii = np.array(m_["inertia_about_own_com_S_kg_m2"], float)
        I += Ii + mi * ((ri @ ri) * np.eye(3) - np.outer(ri, ri))
    return Mtot, cg, I
B7 = {}
for cid in ("C02", "C06"):
    cfg = next(c for c in fb06["configurations"] if c["configuration_id"] == cid)
    Mtot, cg, I = reaggregate(cfg)
    cand = cfg["bridged_candidate"]
    stated = cfg["v3_r2_stated"]
    B7[cid] = {
        "reagg_mass_minus_candidate": float(Mtot - cand["mass_kg"]),
        "reagg_cg_minus_candidate_max_abs": float(np.max(np.abs(cg - np.array(cand["cg_S_m"], float)))),
        "reagg_inertia_minus_candidate_max_abs": float(np.max(np.abs(I - np.array(cand["inertia_about_system_cg_S_kg_m2"], float)))),
        "candidate_mass_minus_stated": float(cand["mass_kg"] - stated["mass_kg"]),
        "delta_cg_explained_residual_max_abs": float(np.max(np.abs(
            np.array(cfg["bridge_explanation_of_deltas"]["delta_cg_total_m"], float)
            - np.array(cfg["bridge_explanation_of_deltas"]["delta_cg_from_arm_row_only_m"], float)))),
        "delta_inertia_total_vs_arm_only_max_abs": float(abs(
            cfg["bridge_explanation_of_deltas"]["delta_inertia_total_max_abs"]
            - cfg["bridge_explanation_of_deltas"]["delta_inertia_from_arm_row_only_max_abs_residual"])),
        "fk_cg_residual_m": cfg["fk_cross_check_vs_pure_odr01_placement"]["candidate_arm_cg_minus_fk_norm_m"],
        "fk_inertia_residual": cfg["fk_cross_check_vs_pure_odr01_placement"]["candidate_arm_inertia_minus_fk_max_abs"],
        "spd_min_eig_stated": float(np.linalg.eigvalsh(np.array(stated["inertia_about_system_cg_S_kg_m2"], float))[0]),
        "spd_min_eig_candidate": float(np.linalg.eigvalsh(np.array(cand["inertia_about_system_cg_S_kg_m2"], float))[0]),
    }
B["B7_fb06_C02_C06_spot"] = B7
# B8 consumer ambiguity: count files citing the bridge sha inside round1_bridge
bridge_sha = "0ACEB659284CAB86"
cite_files = []
pkg = os.path.join(ROOT, r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge")
for dp, dn, fn in os.walk(pkg):
    dn[:] = [d for d in dn if d != "__pycache__"]
    for f in fn:
        if f.endswith((".json", ".yaml", ".md", ".csv")):
            fp = os.path.join(dp, f)
            try:
                with open(fp, encoding="utf-8", errors="ignore") as fh:
                    if bridge_sha in fh.read():
                        cite_files.append(os.path.relpath(fp, pkg))
            except Exception:
                pass
B["B8_bridge_sha_citing_files_in_mpi_package"] = {"count": len(cite_files), "files": sorted(cite_files)}
# e21 peak sentinel present in FB-05
with open(os.path.join(ROOT, P["fb05"]), encoding="utf-8") as f:
    fb05_txt = f.read()
B["B8_fb05_peak_sentinel"] = {"29.41085537835705_present": "29.41085537835705" in fb05_txt,
                              "consumer_ambiguity_count_0_present": "\"consumer_ambiguity_count\": 0" in fb05_txt}
# B9 V5 gate state re-read
v5 = load_json(P["v5gate"])
B["B9_v5_gate_state"] = {"gate": v5["gate"], "next_stage_authorized": v5["next_stage_authorized"],
                         "single_consumption_rule_resolved": v5["m7_r2_arm_placement_consumption"]["single_consumption_rule_resolved"]}
# B10 e15 state re-read
e15 = load_json(P["e15gate"])
B["B10_e15_state"] = {"overall": e15["overall"],
                      "cross_solver_max_rel_diff": e15["cross_solver_diagnostic"]["max_relative_difference"],
                      "gate_limit": e15["final_candidate_cross_solver"]["gate_limit"],
                      "final_candidate_available": e15["final_candidate_cross_solver"]["available"]}
# B11 blacklist scan on NEW files (decision + gate + fb08)
def scan_blacklist(rel, needles):
    with open(os.path.join(ROOT, rel), encoding="utf-8", errors="ignore") as f:
        txt = f.read()
    return {n: txt.count(n) for n in needles}
needles = ["29.226410622980581", "0.3483933", "1.7419665", "measured_mass"]
B["B11_blacklist_new_files"] = {k: scan_blacklist(P[k], needles) for k in ("decision", "gate", "fb08")}
B["B11_legacy_24kg_literal_decision"] = scan_blacklist(P["decision"], ["24.0"])
# B12 C02..C06 rounded-spelling provenance: recompute arm-CG witness? witness needs V3_R2 rows; instead verify C02..C06 FK residual class consistency
B["B12_fk_residuals_all_configs_m"] = {
    c["configuration_id"]: [c["fk_cross_check_vs_pure_odr01_placement"]["candidate_arm_cg_minus_fk_norm_m"],
                            c["fk_cross_check_vs_pure_odr01_placement"]["candidate_arm_inertia_minus_fk_max_abs"]]
    for c in fb06["configurations"]}

print(json.dumps(out, indent=1, ensure_ascii=False))
