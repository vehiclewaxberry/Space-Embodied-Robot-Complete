# -*- coding: utf-8 -*-
# RED_TEAM_ROUND1_EXECUTION_V1 master recomputation script (AGENT-4, read-only on all upstream assets).
# Pure Python 3.13 + numpy. No CAD/FEA process. Writes nothing outside this directory.
import hashlib, json, math, os, re, sys
import numpy as np

ROOT = r"F:/China Graduate Future Flight Vehicle Innovation Competition"
BRIDGE_DIR = r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge"
R0 = os.path.join(ROOT, BRIDGE_DIR, "round0_handover")
OUT = os.path.join(ROOT, BRIDGE_DIR, "round1_bridge", "redteam_round1")

def sha256_of(relpath):
    p = os.path.join(ROOT, relpath)
    with open(p, "rb") as f:
        b = f.read()
    return hashlib.sha256(b).hexdigest().upper(), len(b)

def read_text(relpath):
    with open(os.path.join(ROOT, relpath), "r", encoding="utf-8") as f:
        return f.read()

results = {}

# ---------------------------------------------------------------- S1: task (a) six round-1 hash pins
six_pins = [
    ("accepted_urdf_b601", r"20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf", "1BC2B7483CD8025D", 11321),
    ("solar_r2_step", r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_CANDIDATE_V1.step", "21FF77B882DBFAB8", 131834),
    ("e21_gate", r"30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results/E21_DIAGNOSTIC_GATE_V1.json", "B03B7C7AF571AA00", 22675),
    ("harness_fk_sweep_v2", r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/HARNESS_B601_FULL_FK_SWEEP_V2.json", "DB86348B8276FB2D", 20197),
    ("route_c_precad_gate", r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/02_pre_cad_parametric_guided_route_search/03_gate/ROUTE_C_PRECAD_PARAMETRIC_SEARCH_GATE_V1.json", "B43745081B4D0F22", 17306),
    ("route_c_precad_validation", r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/02_pre_cad_parametric_guided_route_search/03_gate/ROUTE_C_PRECAD_PARAMETRIC_SEARCH_VALIDATION_V1.json", "84D89F631F7904DA", 32996),
]
s1 = []
for name, rel, prefix16, exp_bytes in six_pins:
    h, n = sha256_of(rel)
    s1.append({"name": name, "sha256_16": h[:16], "pinned_16": prefix16, "hash_match": h[:16] == prefix16.upper(),
               "bytes": n, "bytes_match": n == exp_bytes, "full_sha256": h})
results["task_a_six_round1_pins"] = s1

# ---------------------------------------------------------------- S2: receipt 29 baseline entries (ATK-14 full recompute)
receipt_rel = BRIDGE_DIR.replace("/", "\\") + r"\round0_handover\00_receipt\KIMI_M7_TERMINAL_HANDOVER_RECEIPT.json"
receipt = json.loads(read_text(receipt_rel))
s2 = []
for e in receipt["baseline_verification"]:
    h, n = sha256_of(e["path"])
    rec = {"name": e["name"], "declared_status": e["status"],
           "sha256_match": (h == e["sha256"].upper()), "bytes_match": (n == e["bytes"]),
           "recomputed_sha256": h, "recomputed_bytes": n}
    if e.get("expected_sha256"):
        rec["expected_match"] = (h == e["expected_sha256"].upper())
    if "expected_bytes" in e:
        rec["expected_bytes_match"] = (n == e["expected_bytes"])
    if e["name"] == "accepted_urdf_b601":
        raw = open(os.path.join(ROOT, e["path"]), "rb").read()
        lf = raw.replace(b"\r\n", b"\n")
        rec["lf_normalized_sha256"] = hashlib.sha256(lf).hexdigest().upper()
        rec["lf_match"] = rec["lf_normalized_sha256"] == e["sha256_lf_normalized"].upper()
    s2.append(rec)
results["receipt_29_entries_recompute"] = s2
summary = receipt["verification_summary"]
results["receipt_count_audit"] = {
    "entries_independent_count": len(receipt["baseline_verification"]),
    "declared_files_checked": summary["files_checked"],
    "declared_pass": summary["pass"], "independent_pass_count": sum(1 for e in receipt["baseline_verification"] if e["status"] == "PASS"),
    "declared_no_recorded_hash": summary["no_recorded_hash"],
    "independent_no_recorded_hash": sum(1 for e in receipt["baseline_verification"] if e["status"] == "NO_RECORDED_HASH"),
    "declared_drift": summary["drift_or_missing"],
    "independent_drift": sum(1 for e in receipt["baseline_verification"] if e["status"] != "PASS" and e["status"] != "NO_RECORDED_HASH"),
    "receipt_self_listed": any("KIMI_M7_TERMINAL_HANDOVER_RECEIPT" in e["path"] for e in receipt["baseline_verification"]),
    "next_stage_authorized": receipt["next_stage_authorized"], "release_credit": receipt["release_credit"],
}

# ---------------------------------------------------------------- S3: Route-C inventory 21 pins (full 64-hex)
rc_inv = json.loads(read_text(BRIDGE_DIR.replace("/", "\\") + r"\round0_handover\02_route_c_inputs\ROUTE_C_PHYSICAL_INPUT_INVENTORY_V1.json"))
s3 = []
for rel, h_expected in rc_inv["source_files_sha256"].items():
    h, n = sha256_of(rel)
    s3.append({"path": rel, "match": h == h_expected.upper(), "bytes": n})
results["route_c_inventory_21_pins"] = s3

# ---------------------------------------------------------------- S4: R2 flex inventory 16 pins (16-hex truncated + '...')
r2_inv = json.loads(read_text(BRIDGE_DIR.replace("/", "\\") + r"\round0_handover\03_r2_flex_inputs\R2_FLEX_INPUT_INVENTORY_V1.json"))
s4 = []
for rel, h_expected in r2_inv["source_files_sha256"].items():
    h, n = sha256_of(rel)
    m = re.fullmatch(r"([0-9a-f]{16})\.\.\.", h_expected)
    prefix = m.group(1) if m else None
    s4.append({"path": rel, "format": "16hex_truncated" if m else "other",
               "prefix_match": (h.lower().startswith(prefix) if prefix else None), "bytes": n})
results["r2_flex_inventory_16_pins"] = s4

# ---------------------------------------------------------------- S5: authority matrix CSV pins (12-hex) + row/CONFLICT_CANDIDATE counts
csv_text = read_text(BRIDGE_DIR.replace("/", "\\") + r"\round0_handover\01_frame_authority\MPI01_FRAME_AUTHORITY_MATRIX.csv")
rows = [r for r in csv_text.splitlines() if r.strip()][1:]
import csv, io
parsed = list(csv.DictReader(io.StringIO(csv_text)))
pin_rows, bad_pin_rows = [], []
seen = {}
for r in parsed:
    rel = r["path"]; short = r["sha256_short"].upper()
    if rel not in seen:
        try:
            h, n = sha256_of(rel)
            seen[rel] = (h, n)
        except FileNotFoundError:
            seen[rel] = (None, 0)
    h, n = seen[rel]
    ok = (h is not None and h.startswith(short))
    (pin_rows if ok else bad_pin_rows).append({"item": r["item"], "path": rel, "short": short, "prefix_match": ok, "bytes": n})
results["authority_matrix_pin_audit"] = {
    "data_rows": len(parsed), "unique_paths": len(seen),
    "pin_rows": len(pin_rows), "bad_pin_rows": bad_pin_rows,
    "conflict_candidate_rows": sum(1 for r in parsed if "CONFLICT_CANDIDATE" in (r["notes"] or "")),
    "pin_hex_width": 12, "full_width_required_by_plan": 64,
}

# ---------------------------------------------------------------- S6: bridge independent rebuild (ATK-11 core)
contract = read_text(r"30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/00_authority/E21_AUTHORITY_CONTRACT_V1.yaml")
def extract_rows(text, block):
    i = text.index(block)
    j = text.index("transform_S_A0_rows", i)
    seg = text[j:j + 400]
    rows = re.findall(r"\[([^\[\]]+)\]", seg)[:4]
    M = [[float(x) for x in r.split(",")] for r in rows]
    assert len(M) == 4 and all(len(r) == 4 for r in M), M
    return np.array(M, dtype=float)
T_dyn = extract_rows(contract, "ODR01_DYNAMICS_T_SM")
T_phys = extract_rows(contract, "WP11_PHYSICAL_GEOMETRY_CONTEXT")
B = np.linalg.inv(T_dyn) @ T_phys
R_B = B[:3, :3]; t_B = B[:3, 3]
s_c, c_c = 0.422618483193, 0.906307683772  # contract 12-dp spelling
theta_contract = math.degrees(math.atan2(s_c, c_c))
th_full = math.radians(25.000014)
B_full = np.array([[math.cos(th_full), -math.sin(th_full), 0, 0],
                   [math.sin(th_full), math.cos(th_full), 0, 0],
                   [0, 0, 1.0, 0.02275], [0, 0, 0, 1.0]])
th_25 = math.radians(25.0)
quat_w = math.sqrt(1.0 + R_B[0,0] + R_B[1,1] + R_B[2,2]) / 2.0
quat_z = (R_B[1,0] - R_B[0,1]) / (4.0 * quat_w)
plan_B = np.array([[0.906307683772, -0.422618483193, 0.0, 0.0],
                   [0.422618483193, 0.906307683772, 0.0, 0.0],
                   [0.0, 0.0, 1.0, 0.02275],
                   [0.0, 0.0, 0.0, 1.0]])
# chirality discriminator: candidate with -theta
B_neg = np.array([[math.cos(th_full), math.sin(th_full), 0, 0],
                  [-math.sin(th_full), math.cos(th_full), 0, 0],
                  [0, 0, 1.0, 0.02275], [0, 0, 0, 1.0]])
v_test = np.array([1.0, 0.0, 0.0, 1.0])
ang_between = math.degrees(math.acos(np.clip(np.dot((B @ v_test)[:3], (B_neg @ v_test)[:3]) /
    (np.linalg.norm((B @ v_test)[:3]) * np.linalg.norm((B_neg @ v_test)[:3])), -1, 1)))
results["bridge_rebuild"] = {
    "T_dyn_from_contract": T_dyn.tolist(), "T_phys_from_contract": T_phys.tolist(),
    "B": B.tolist(),
    "det_R_B": float(np.linalg.det(R_B)),
    "orth_max_abs": float(np.max(np.abs(R_B.T @ R_B - np.eye(3)))),
    "angle_deg_from_matrix": float(math.degrees(math.acos(np.clip((np.trace(R_B) - 1) / 2, -1, 1)))),
    "theta_contract_spelling_deg": theta_contract,
    "theta_full_precision_deg": 25.000014,
    "theta_exact_25_deg_delta": float(theta_contract - 25.0),
    "translation": t_B.tolist(),
    "translation_expected": [0.0, 0.0, 0.02275],
    "inv_B": np.linalg.inv(B).tolist(),
    "roundtrip_max_abs": float(np.max(np.abs(np.linalg.inv(B) @ B - np.eye(4)))),
    "Tdyn_B_vs_Tphys_max_abs": float(np.max(np.abs(T_dyn @ B - T_phys))),
    "elementwise_vs_plan_B_max_abs": float(np.max(np.abs(B - plan_B))),
    "full_precision_witness_max_abs_delta": float(np.max(np.abs(B - B_full))),
    "sin_cos_25deg_exact": [math.sin(th_25), math.cos(th_25)],
    "contract_spelling_vs_sin_cos_25deg_delta": [s_c - math.sin(th_25), c_c - math.cos(th_25)],
    "quaternion_wxyz": [quat_w, 0.0, 0.0, quat_z],
    "plan_quaternion_wxyz": [0.976295980677, 0, 0, 0.216439733215],
    "quaternion_delta": [quat_w - 0.976295980677, quat_z - 0.216439733215],
    "chirality_discriminator_deg_between_plus_minus_candidates": ang_between,
    "det_R_odr01": float(np.linalg.det(T_dyn[:3, :3])),
    "det_R_wp11": float(np.linalg.det(T_phys[:3, :3])),
    "orth_wp11_max_abs": float(np.max(np.abs(T_phys[:3, :3].T @ T_phys[:3, :3] - np.eye(3)))),
    "origin_delta_m": abs(0.208 - 0.18525),
}

# ---------------------------------------------------------------- S7: ATK-04 positive controls + ATK-05 mass identity + ATK-12 Steiner
CG_odr = np.array([0.09123549790183574, 4.37633035602944e-05, -0.006282656311277057])
CG_wp11 = np.array([0.0946788903322559, 0.0007727570136472924, -0.006101972690591536])
I_odr = np.array([[0.4890598697082972, -0.0005788023248723302, 0.04318674475009798],
                  [-0.0005788023248723302, 1.823007876628233, -2.7303305627283267e-05],
                  [0.04318674475009798, -2.7303305627283267e-05, 2.0283280319657617]])
I_wp11 = np.array([[0.48911082356730723, -0.0249693662376088, 0.03807122743844715],
                   [-0.0249693662376088, 1.918049314817376, 0.008628492015865859],
                   [0.03807122743844715, 0.008628492015865859, 2.1314475671941233]])
m_arm, M_sys = 4.695555949342986, 31.022864807342987
C_S = T_dyn @ np.linalg.inv(T_phys)
r_ledger_C01 = np.array([0.376934164889081, -0.17567666955456437, -0.08674287405126006, 1.0])
r_odr01_computed_C01 = np.array([0.3541841648890811, -0.1958762386983999, -0.004371637241445176])
mapped = (C_S @ r_ledger_C01)[:3]
delta_CG_sys = float(np.linalg.norm(CG_wp11 - CG_odr))
implied_arm_disp = delta_CG_sys * M_sys / m_arm
# bridge displacement field at C01 arm CG (full-precision bridge, pure):
disp_C01 = (C_S @ r_ledger_C01)[:3] - r_ledger_C01[:3]
steiner_witness = m_arm * 0.02275 ** 2
results["frame_cross_checks"] = {
    "cg_delta_norm_recomputed": delta_CG_sys, "cg_delta_norm_published": 0.003524348142565558,
    "cg_delta_match": abs(delta_CG_sys - 0.003524348142565558) < 1e-15,
    "inertia_channel_delta_max_abs_recomputed": float(np.max(np.abs(I_wp11 - I_odr))),
    "inertia_channel_delta_published": 0.10311953522836159,
    "inertia_delta_match": abs(float(np.max(np.abs(I_wp11 - I_odr))) - 0.10311953522836159) < 1e-15,
    "C01_arm_CG_mapped_by_C_S": mapped.tolist(),
    "C01_arm_CG_e21_odr01_computed": r_odr01_computed_C01.tolist(),
    "C01_residual_norm_m": float(np.linalg.norm(mapped - r_odr01_computed_C01)),
    "C01_residual_norm_mm": float(np.linalg.norm(mapped - r_odr01_computed_C01) * 1000.0),
    "plan_claimed_residual_mm": 1.1314e-4,
    "e21_published_ledger_residual_mm": 0.00011314150166020904,
    "implied_arm_level_displacement_m_from_system_delta": implied_arm_disp,
    "C01_bridge_displacement_norm_m": float(np.linalg.norm(disp_C01)),
    "mass_residual_plus_arm": 26.327308858000002 + m_arm,
    "mass_system_published": M_sys,
    "mass_identity_abs_error": abs(26.327308858000002 + m_arm - M_sys),
    "wing_mass_closure": 3 * 0.18 + 0.05 + 2 * 0.03 + 0.08 + 0.05,
    "two_wings": 2 * (3 * 0.18 + 0.05 + 2 * 0.03 + 0.08 + 0.05),
    "r2_minus_r1_delta": 1.56 - 2 * 0.3483933,
    "whole_sat_with_r2": 24.0 + (1.56 - 2 * 0.3483933),
    "steiner_witness_m_arm_d2": steiner_witness,
    "silent_average_witness_deg": (29.041965867604112 + 29.41085537835705) / 2.0,
    "cg_midpoint_blacklist": ((CG_odr + CG_wp11) / 2.0).tolist(),
    "inertia_midpoint_max_element": float(np.max((I_odr + I_wp11) / 2.0)),
    "theta_rounded_spelling_deg": float(math.degrees(math.atan2(0.422618, 0.906308))),
    "theta_rounded_claim_deg": 24.999981252,
    "theta_full_vs_rounded_delta_deg": float(theta_contract - math.degrees(math.atan2(0.422618, 0.906308))),
}

# ---------------------------------------------------------------- S8: M3R flange composition caution recomputation
t_flange = np.array([25.155, 0.015994151, -0.08636607])
t_dyn_mm = np.array([185.25, 0.0, 0.0])
R_dyn = T_dyn[:3, :3]
naive_pos = R_dyn @ t_flange + t_dyn_mm            # naive: treat JSON translation as M-frame coords
stackaxis_pos = t_dyn_mm + t_flange                # intended: translation along S-axes at M origin
M3R_LOCAL_origin = np.array([208.0, 0.015994151, -0.086366070])
FASTENER_END_origin = np.array([210.405, 0.015994151, -0.086366070])
results["m3r_flange_composition_caution"] = {
    "naive_Tdyn_times_TMflange_position_mm": naive_pos.tolist(),
    "error_vs_M3R_LOCAL_norm_mm": float(np.linalg.norm(naive_pos - M3R_LOCAL_origin)),
    "error_vs_FASTENER_END_PLANE_norm_mm": float(np.linalg.norm(naive_pos - FASTENER_END_origin)),
    "error_z_component_mm": float(abs(naive_pos[2] - M3R_LOCAL_origin[2])),
    "claimed_misplacement_mm_in_artifacts": 25.07,
    "stackaxis_reading_position_mm": stackaxis_pos.tolist(),
    "stackaxis_reading_equals_M4_fastener_end_plane": bool(np.allclose(stackaxis_pos, FASTENER_END_origin, atol=1e-9)),
}

# ---------------------------------------------------------------- S9: URDF mass sum + base_link CG (authority matrix row claims)
urdf = read_text(r"20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf")
masses = [float(x) for x in re.findall(r'<mass\s+value="([0-9.eE+-]+)"', urdf)]
results["urdf_audit"] = {
    "mass_tag_count": len(masses), "mass_sum": sum(masses), "mass_sum_claim": 4.695555949342986,
    "mass_sum_abs_error": abs(sum(masses) - 4.695555949342986),
}

# ---------------------------------------------------------------- S10: blacklist + keyword scan over the 8 artifacts (ATK-06/08/09/03)
art = {
    "receipt_json": receipt_rel,
    "authority_csv": BRIDGE_DIR.replace("/", "\\") + r"\round0_handover\01_frame_authority\MPI01_FRAME_AUTHORITY_MATRIX.csv",
    "frame_defs_md": BRIDGE_DIR.replace("/", "\\") + r"\round0_handover\01_frame_authority\FRAME_DEFINITIONS_DISCOVERED_V1.md",
    "bridge_plan_md": BRIDGE_DIR.replace("/", "\\") + r"\round0_handover\01_frame_authority\MPI01_BRIDGE_DERIVATION_PLAN_V1.md",
    "route_c_json": BRIDGE_DIR.replace("/", "\\") + r"\round0_handover\02_route_c_inputs\ROUTE_C_PHYSICAL_INPUT_INVENTORY_V1.json",
    "route_c_md": BRIDGE_DIR.replace("/", "\\") + r"\round0_handover\02_route_c_inputs\ROUTE_C_PHYSICAL_INPUT_INVENTORY_V1.md",
    "r2flex_json": BRIDGE_DIR.replace("/", "\\") + r"\round0_handover\03_r2_flex_inputs\R2_FLEX_INPUT_INVENTORY_V1.json",
    "r2flex_md": BRIDGE_DIR.replace("/", "\\") + r"\round0_handover\03_r2_flex_inputs\R2_FLEX_INPUT_INVENTORY_V1.md",
}
blacklist_literals = ["29.226410622980581", "29.22641062298", "23.3032134", "0.3483933", "1.7419665",
                      "4.3630e-3", "0.0043630", "8.9042e-3", "0.0089042", "1.5047e-2", "0.015047"]
kw = re.compile(r"averag|midpoint|blend|\bmean\b", re.IGNORECASE)
scan = {}
for tag, rel in art.items():
    txt = read_text(rel)
    hits = {}
    for lit in blacklist_literals:
        for m in re.finditer(re.escape(lit), txt):
            line_no = txt[:m.start()].count("\n") + 1
            line = txt.splitlines()[line_no - 1].strip()
            hits.setdefault(lit, []).append({"line": line_no, "context": line[:220]})
    kw_hits = []
    for i, line in enumerate(txt.splitlines(), 1):
        if kw.search(line):
            kw_hits.append({"line": i, "context": line.strip()[:220]})
    # numeric 24.0 needs word-boundary-ish handling
    h24 = []
    for m in re.finditer(r"24\.0(?!\d)", txt):
        line_no = txt[:m.start()].count("\n") + 1
        h24.append({"line": line_no, "context": txt.splitlines()[line_no - 1].strip()[:220]})
    if h24:
        hits["24.0"] = h24
    scan[tag] = {"blacklist_hits": hits, "avg_keyword_hits": kw_hits,
                 "bytes": len(txt.encode("utf-8"))}
results["blacklist_keyword_scan"] = scan

# ---------------------------------------------------------------- S11: null^PASS structural scan on 3 JSON artifacts (ATK-02)
def walk(obj, path, hits, nulls):
    if isinstance(obj, dict):
        keys = {k.lower(): k for k in obj}
        passlike = [obj[k] for k in obj if k.lower() in ("pass", "closed", "controlled", "verified") and obj[k] is True]
        status_pass = obj.get("status") == "PASS" or obj.get("state") == "PASS"
        if (passlike or status_pass):
            nullvals = [k for k, v in obj.items() if v is None]
            if nullvals:
                hits.append({"path": path, "null_fields_with_pass": nullvals})
        for k, v in obj.items():
            walk(v, f"{path}.{k}", hits, nulls)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk(v, f"{path}[{i}]", hits, nulls)
    elif obj is None:
        nulls.append(path)
for tag in ("receipt_json", "route_c_json", "r2flex_json"):
    obj = json.loads(read_text(art[tag]))
    hits, nulls = [], []
    walk(obj, "$", hits, nulls)
    results.setdefault("null_pass_scan", {})[tag] = {"null_and_pass_coexist": hits, "null_count": len(nulls)}

# ---------------------------------------------------------------- S12: five-case frequency cross-check (ATK-09) + ATK-07 inventory counts
e21_rom = json.loads(read_text(r"30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results/E21_FIXED_BASE_R2_ROM_REPRODUCTION_AND_MASS_CONFLICT_V1.json"))
modes = json.loads(read_text(r"20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/FLEXIBLE_APPENDAGE_R2_MODES.json"))
inv_freq = r2_inv["five_case_frequency_evidence"]
cmp_cases = {}
for case in ["nominal", "all_low", "all_high", "root_low_inter_high", "root_high_inter_low"]:
    e21_case = next(c for c in e21_rom["leaf_only"]["cases"] if c["case"] == case)
    cmp_cases[case] = {
        "inv_leaf_only_eq_e21_reproduced": inv_freq["leaf_only_reproduced_hz"][case] == e21_case["leaf_only_reproduced_hz"],
        "inv_conflict_eq_e21": inv_freq["moving_inter_hinge_mass_conflict_hz"][case] == e21_case["moving_inter_hinge_mass_conflict_hz"],
        "inv_delta_eq_e21": inv_freq["conflict_minus_leaf_only_hz"][case] == e21_case["conflict_minus_leaf_only_hz"],
        "inv_delta_all_negative": all(x < 0 for x in inv_freq["conflict_minus_leaf_only_hz"][case]),
        "published_modes_match_modes_json": r2_inv["parameter_status_table"][5]["value"][case] == modes["modes_hz_per_case"][case],
        "published_vs_reproduced_max_abs_hz": max(abs(a - b) for a, b in zip(modes["modes_hz_per_case"][case], e21_case["leaf_only_reproduced_hz"])),
        "e21_published_max_abs_error_hz": e21_case["published_max_abs_error_hz"],
    }
rel_shift = [100.0 * (c - l) / l for c, l in zip(inv_freq["moving_inter_hinge_mass_conflict_hz"]["nominal"],
                                                 inv_freq["leaf_only_reproduced_hz"]["nominal"])]
results["five_case_frequency_audit"] = {
    "cases": cmp_cases,
    "nominal_relative_shift_pct_recomputed": rel_shift,
    "nominal_relative_shift_pct_inventory": inv_freq["nominal_relative_shift_pct_recomputed_by_this_agent"],
    "max_e21_published_abs_error_hz": max(c["e21_published_max_abs_error_hz"] for c in cmp_cases.values()),
    "mqq_star_minus_mqq_inventory": [[0.006, 0.0024, 0], [0.0024, 0.0012, 0], [0, 0, 0]],
    "mqq_star_minus_mqq_e21": e21_rom["nonselecting_conflict_diagnostic"]["Mqq_star_minus_leaf_only_kg_m2"],
    "conflict_flags_e21": {k: e21_rom["nonselecting_conflict_diagnostic"][k] for k in
                           ("selected", "propagated_to_free_floating_dynamics", "dynamic_mass_allocation_frozen")},
    "e21_rom_nulls": {k: e21_rom[k] for k in ("damping_matrix", "participation_factors", "forced_response", "standard_uncertainty")},
    "inventory_counts": {"parameter_rows": len(r2_inv["parameter_status_table"]),
                         "gap_rows": len(r2_inv["hf_model_and_rom_input_gap_list"]["gaps"]),
                         "mc_options": len(r2_inv["mass_conflict_resolution_options"]["options"]),
                         "source_pins": len(r2_inv["source_files_sha256"])},
    "route_c_inventory_counts": {"p_rows": len(rc_inv["physical_capability_inventory"]),
                                 "nrb_anchors": len(rc_inv["route_b_negative_result_anchors"]),
                                 "topology_candidates": len(rc_inv["topology_input_readiness_matrix"]["candidates"]),
                                 "source_pins": len(rc_inv["source_files_sha256"]),
                                 "summary_block": rc_inv["summary"]},
}

# ---------------------------------------------------------------- S13: in-memory 1-byte mutation negative control (ATK-14 falsifier)
probe = os.path.join(ROOT, six_pins[2][1])
raw = open(probe, "rb").read()
h0 = hashlib.sha256(raw).hexdigest().upper()
mut = bytearray(raw); mut[0] ^= 0x01
h1 = hashlib.sha256(bytes(mut)).hexdigest().upper()
results["mutation_negative_control"] = {"file": six_pins[2][1], "original_match": h0 == "B03B7C7AF571AA00FE3612756FFBBD99CB834B84377BA8DC2C213355C252616B",
                                        "mutated_detected": h1 != h0, "in_memory_only": True}

# ---------------------------------------------------------------- S14: round1 bridge file presence (task b)
bridge_candidate = os.path.join(ROOT, BRIDGE_DIR, "round1_bridge", "02_bridge", "B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml")
results["task_b_round1_bridge_file"] = {"path": bridge_candidate, "exists": os.path.exists(bridge_candidate)}

print(json.dumps(results, indent=1, ensure_ascii=False))
