"""REDTEAM-2 (Wave-2b) round2 static attacks - read-only independent recomputation.

Attacks (a) ATK-11 bridge body, (b) ATK-06 silent average, (c) ATK-04 frame mixing,
(d) ATK-12 Steiner/uncertainty, (f) FB-06 recompute, (g) V6/R3 candidates,
(h) hash sentinels, plus ATK-01/02 hygiene sweeps.

Discipline: pure python + numpy + yaml + hashlib; no CAD/FEA process; git unused.
NEVER executes Wave-2a generator scripts (they would rewrite frozen round1 products).
e21 module is NOT imported here (see rt2_e21_rerun.py for the dynamic lane).
Writes ONLY inside redteam_round2/.
"""
import hashlib
import json
import math
import os
import re
import sys
from pathlib import Path

import numpy as np
import yaml

sys.dont_write_bytecode = True

ROOT = Path("F:/China Graduate Future Flight Vehicle Innovation Competition")
BASE = ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge"
OUT_DIR = BASE / "redteam_round2"
OUT_FILE = OUT_DIR / "rt2_static_output.json"

BRIDGE_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml"
FB03_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/03_validation/MPI03_BRIDGE_NUMERICAL_VALIDATION.json"
FB04_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/04_mass/MPI04_MASS_INERTIA_BRIDGE_VALIDATION.json"
FB05_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/05_e21_bridged/E21_BRIDGED_ARM_PLACEMENT_GATE_V2.json"
FB06_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/06_mass_propagation/SYSTEM_MASS_PROPERTIES_BRIDGED_V1.yaml"
V6_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/07_rebind/MECH_DYNAMICS_INTERFACE_V6_CANDIDATE.yaml"
R3_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/07_rebind/EMBODIED_MECHANICAL_CONTRACT_R3_CANDIDATE.yaml"
E21_PREFIX = "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics"
E21_AUTHORITY_REL = f"{E21_PREFIX}/00_authority/E21_AUTHORITY_CONTRACT_V1.yaml"
E21_ODR01_LANE_REL = f"{E21_PREFIX}/results/E21_ODR01_DYNAMICS_T_SM__M07_ARM_ONLY_RADAU_SUMMARY_V1.json"
E21_WP11_LANE_REL = f"{E21_PREFIX}/results/E21_WP11_PHYSICAL_GEOMETRY_CONTEXT__M07_ARM_ONLY_RADAU_SUMMARY_V1.json"
E21_RESIDUAL_REL = f"{E21_PREFIX}/results/E21_C07_R2_DEPLOYED_LOCKED_FIXED_RESIDUAL_V1.json"
V3_R2_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml"
V5_GATE_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/15_loop_continuation_v5/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V5.json"
WP10_BASE_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp10_mech_rl_v4/MECH_DYNAMICS_INTERFACE_V5_R2.yaml"
WP13_BASE_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp13_embodied_contract/EMBODIED_MECHANICAL_CONTRACT_R2.yaml"
R0_RECEIPT_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round0_handover/00_receipt/KIMI_M7_TERMINAL_HANDOVER_RECEIPT.json"
RT1_OUT_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/redteam_round1/round1_verify_output.json"

ARM_ID = "b601_complete_arm_including_gripper_urdf_links"
PHYSICAL_CONSUMED = {"C01", "C02", "C03", "C04", "C05", "C06"}
DYNAMICS_CONSUMED = {"C07", "C08", "C09"}

R = {"schema": "RED_TEAM_ROUND2_STATIC_OUTPUT_V1",
     "generator": "KIMI M7 Wave-2b REDTEAM-2 (pure python/numpy/hashlib; read-only)",
     "sections": {}}


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest().upper()


def sha256_file(rel) -> str:
    return sha256_bytes((ROOT / rel).read_bytes())


def maxabs(A) -> float:
    return float(np.max(np.abs(np.asarray(A, dtype=float))))


def load_yaml_rel(rel):
    return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))


def load_json_rel(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def rot_to_angle_deg(Rm):
    return math.degrees(math.atan2(Rm[1, 0], Rm[0,0]))


# ============================================================================
# S0: hash sentinel - round1 products inventory + upstream cross-pin consistency
# ============================================================================
def s0_hash_sentinel():
    sec = {"round1_products": [], "upstream_recompute": [], "cross_pin_conflicts": [],
           "negative_control_mutation_detector_fired": None}
    # (h.1) every file under round1_bridge except our own output dir
    for dirpath, _dirnames, filenames in os.walk(BASE):
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            rel = p.relative_to(ROOT).as_posix()
            if rel.startswith((BASE / "redteam_round2").relative_to(ROOT).as_posix()):
                continue
            b = p.read_bytes()
            sec["round1_products"].append({"path": rel, "bytes": len(b), "sha256": sha256_bytes(b)})
    # (h.2) collect every pinned (path, sha256) pair across all products
    pin_sources = {}
    def add_pins(obj, origin):
        if isinstance(obj, dict):
            if "path" in obj and "sha256" in obj and isinstance(obj["path"], str) and isinstance(obj["sha256"], str):
                if obj["path"].count("/") >= 2 and len(obj["sha256"]) == 64:
                    pin_sources.setdefault(obj["path"], set()).add(obj["sha256"].upper())
            for v in obj.values():
                add_pins(v, origin)
        elif isinstance(obj, list):
            for v in obj:
                add_pins(v, origin)
    for rel, loader in [(BRIDGE_REL, load_yaml_rel), (FB03_REL, load_json_rel), (FB04_REL, load_json_rel),
                        (FB05_REL, load_json_rel), (FB06_REL, load_yaml_rel), (V6_REL, load_yaml_rel),
                        (R3_REL, load_yaml_rel), (R0_RECEIPT_REL, load_json_rel)]:
        add_pins(loader(rel), rel)
    # round0 receipt baseline entries carry expected_sha256 too
    r0 = load_json_rel(R0_RECEIPT_REL)
    for e in r0.get("baseline_verification", []):
        if e.get("path") and e.get("expected_sha256"):
            pin_sources.setdefault(e["path"], set()).add(e["expected_sha256"].upper())
    for path in sorted(pin_sources):
        fp = ROOT / path
        if not fp.exists():
            sec["upstream_recompute"].append({"path": path, "pins": sorted(pin_sources[path]),
                                              "recomputed": None, "status": "MISSING_FILE"})
            sec["cross_pin_conflicts"].append({"path": path, "issue": "pinned file missing"})
            continue
        b = fp.read_bytes()
        rec = sha256_bytes(b)
        pins = pin_sources[path]
        ok = all(rec == p for p in pins)
        sec["upstream_recompute"].append({"path": path, "bytes": len(b), "recomputed": rec,
                                          "n_distinct_pins": len(pins), "status": "MATCH" if ok else "DRIFT"})
        if not ok or len(pins) > 1:
            sec["cross_pin_conflicts"].append({"path": path, "pins": sorted(pins), "recomputed": rec,
                                               "issue": "DRIFT" if not ok else "PIN_DISAGREEMENT"})
    # self-test: 1-byte in-memory mutation of the bridge must be detected
    raw = bytearray((ROOT / BRIDGE_REL).read_bytes())
    raw[100] ^= 0x01
    sec["negative_control_mutation_detector_fired"] = bool(sha256_bytes(bytes(raw)) != sha256_file(BRIDGE_REL))
    n_match = sum(1 for u in sec["upstream_recompute"] if u["status"] == "MATCH")
    sec["summary"] = {"round1_product_files": len(sec["round1_products"]),
                      "upstream_unique_paths": len(sec["upstream_recompute"]),
                      "upstream_match": n_match, "conflicts": len(sec["cross_pin_conflicts"])}
    return sec


# ============================================================================
# S1: ATK-11 bridge body - independent rebuild from the e21 authority contract
# ============================================================================
def s1_atk11_bridge():
    sec = {}
    contract = load_yaml_rel(E21_AUTHORITY_REL)
    hyp = contract["placement_hypotheses"]
    T_dyn = np.asarray(hyp["ODR01_DYNAMICS_T_SM"]["transform_S_A0_rows"], dtype=float)
    T_phys = np.asarray(hyp["WP11_PHYSICAL_GEOMETRY_CONTEXT"]["transform_S_A0_rows"], dtype=float)
    bridge = load_yaml_rel(BRIDGE_REL)
    B_stored = np.asarray(bridge["T_PHYSICAL_TO_DYNAMIC"]["homogeneous_4x4"], dtype=float)
    Binv_stored = np.asarray(bridge["T_DYNAMIC_TO_PHYSICAL_inverse_bridge"]["homogeneous_4x4"], dtype=float)
    CS_stored = np.asarray(bridge["S_frame_conjugate_for_S_expressed_quantities"]["C_S_homogeneous_4x4"], dtype=float)
    CSinv_stored = np.asarray(bridge["S_frame_conjugate_for_S_expressed_quantities"]["C_S_inverse_homogeneous_4x4"], dtype=float)

    # independent rebuild, two paths (dense inv vs analytic rigid inverse)
    B_dense = np.linalg.inv(T_dyn) @ T_phys
    Rd, td = T_dyn[:3, :3], T_dyn[:3, 3]
    T_dyn_inv_rigid = np.eye(4); T_dyn_inv_rigid[:3, :3] = Rd.T; T_dyn_inv_rigid[:3, 3] = -Rd.T @ td
    B_rigid = T_dyn_inv_rigid @ T_phys
    Rb, tb = B_dense[:3, :3], B_dense[:3, 3]
    Binv_dense = np.linalg.inv(B_dense)
    Binv_rigid = np.eye(4); Binv_rigid[:3, :3] = Rb.T; Binv_rigid[:3, 3] = -Rb.T @ tb
    CS_ind = T_dyn @ np.linalg.inv(T_phys)

    sec["stored_B_vs_rebuilt_dense_max_abs"] = maxabs(B_stored - B_dense)
    sec["stored_B_vs_rebuilt_rigid_max_abs"] = maxabs(B_stored - B_rigid)
    sec["dense_vs_rigid_rebuild_max_abs"] = maxabs(B_dense - B_rigid)
    sec["stored_invB_vs_rebuilt_max_abs"] = maxabs(Binv_stored - Binv_dense)
    sec["stored_invB_vs_rigid_inverse_max_abs"] = maxabs(Binv_stored - Binv_rigid)
    sec["independent_dense_inverse_vs_rigid_inverse_max_abs"] = maxabs(Binv_dense - Binv_rigid)
    sec["stored_CS_vs_rebuilt_max_abs"] = maxabs(CS_stored - CS_ind)
    sec["stored_CSinv_vs_rebuilt_max_abs"] = maxabs(CSinv_stored - np.linalg.inv(CS_ind))
    sec["det_R_B"] = float(np.linalg.det(Rb))
    sec["max_abs_RtR_minus_I"] = maxabs(Rb.T @ Rb - np.eye(3))
    sec["roundtrip_B_at_invB_max_abs"] = maxabs(B_dense @ Binv_dense - np.eye(4))
    sec["roundtrip_invB_at_B_max_abs"] = maxabs(Binv_dense @ B_dense - np.eye(4))
    sec["T_dyn_at_B_minus_T_phys_max_abs"] = maxabs(T_dyn @ B_dense - T_phys)
    sec["T_phys_at_invB_minus_T_dyn_max_abs"] = maxabs(T_phys @ Binv_dense - T_dyn)
    sec["bridge_translation_m"] = tb.tolist()
    sec["bridge_translation_z_minus_0p02275"] = float(tb[2] - 0.02275)

    # direction semantics on test points: p_S via T_dyn@(B@x_phys) must equal T_phys@x_phys
    rng_pts = [np.array([0.0, 0.0, 0.0, 1.0]), np.array([1.0, 0.0, 0.0, 1.0]),
               np.array([0.0, 1.0, 0.0, 1.0]), np.array([0.0, 0.0, 1.0, 1.0]),
               np.array([-7.849e-06, -1.1531e-06, 0.029841, 1.0]),
               np.array([0.31, -0.17, 0.42, 1.0])]
    sec["direction_semantics_point_closure_worst"] = max(
        maxabs(T_dyn @ (B_dense @ p) - T_phys @ p) for p in rng_pts)

    # chirality / sign discrimination: +theta vs -theta candidates on a test vector
    v = np.array([1.0, 0.0, 0.0])
    theta = math.radians(25.000014)
    Rz_pos = np.array([[math.cos(theta), -math.sin(theta), 0.0],
                       [math.sin(theta), math.cos(theta), 0.0], [0.0, 0.0, 1.0]])
    Rz_neg = Rz_pos.T
    mapped = Rb @ v
    ang_pos = math.degrees(math.acos(float(np.clip(mapped @ (Rz_pos @ v), -1, 1))))
    ang_neg = math.degrees(math.acos(float(np.clip(mapped @ (Rz_neg @ v), -1, 1))))
    sec["chirality"] = {"det_positive": bool(np.linalg.det(Rb) > 0),
                        "angle_vs_plus_theta_candidate_deg": ang_pos,
                        "angle_vs_minus_theta_candidate_deg": ang_neg,
                        "separation_deg": ang_neg - ang_pos}

    # truncation dual-version witnesses
    sec["contract_derived_angle_deg"] = rot_to_angle_deg(Rb)
    th_full = 25.000014
    B_exact_theta = np.eye(4)
    B_exact_theta[:3, :3] = np.array([[math.cos(math.radians(th_full)), -math.sin(math.radians(th_full)), 0.0],
                                      [math.sin(math.radians(th_full)), math.cos(math.radians(th_full)), 0.0],
                                      [0.0, 0.0, 1.0]])
    B_exact_theta[2, 3] = 0.02275
    sec["exact_theta_25p000014_vs_bridge_matrix_max_abs"] = maxabs(B_exact_theta - B_dense)
    sec["angle_gap_25p000014_minus_contract_derived_deg"] = th_full - sec["contract_derived_angle_deg"]
    th_25 = math.radians(25.0)
    B_25 = np.eye(4)
    B_25[:3, :3] = np.array([[math.cos(th_25), -math.sin(th_25), 0.0],
                             [math.sin(th_25), math.cos(th_25), 0.0], [0.0, 0.0, 1.0]])
    B_25[2, 3] = 0.02275
    sec["exact_25deg_reference_vs_bridge_matrix_max_abs"] = maxabs(B_25 - B_dense)
    s_r, c_r = 0.422618, 0.906308
    sec["rounded_spelling_angle_deg"] = math.degrees(math.atan2(s_r, c_r))
    B_round = np.eye(4)
    B_round[:3, :3] = np.array([[c_r, -s_r, 0.0], [s_r, c_r, 0.0], [0.0, 0.0, 1.0]])
    B_round[2, 3] = 0.02275
    sec["rounded_spelling_vs_bridge_matrix_max_abs"] = maxabs(B_round - B_dense)
    # positional effect of rounded spelling at the C01 arm-CG lever (bridge register path)
    v3 = load_yaml_rel(V3_R2_REL)
    c01 = next(c for c in v3["configurations"] if c["configuration_id"] == "C01")
    arm_c01 = next(x for x in c01["composition"] if x["component_id"] == ARM_ID)
    cg_ledger = np.asarray(arm_c01["com_S_m"], dtype=float)
    T_phys_rounded = T_phys.copy()
    T_phys_rounded[1, 0], T_phys_rounded[1, 1] = s_r, c_r
    T_phys_rounded[2, 0], T_phys_rounded[2, 1] = -c_r, s_r
    r_A0 = np.linalg.inv(T_phys_rounded) @ np.append(cg_ledger, 1.0)
    sec["c01_spelling_witness_recomputed_m"] = float(np.linalg.norm((T_phys @ r_A0 - T_phys_rounded @ r_A0)[:3]))
    # quaternion: stored vs rebuilt (up to sign), pre/post normalization
    q_stored = np.asarray(bridge["T_PHYSICAL_TO_DYNAMIC"]["quaternion_wxyz"], dtype=float)
    tr = float(np.trace(Rb))
    qw = math.sqrt(max(0.0, 1.0 + tr)) / 2.0
    qz = (Rb[1, 0] - Rb[0, 1]) / (4.0 * qw)
    q_rebuilt = np.array([qw, 0.0, 0.0, qz])
    q_rebuilt /= np.linalg.norm(q_rebuilt)
    sec["quaternion"] = {
        "stored": q_stored.tolist(), "rebuilt": q_rebuilt.tolist(),
        "stored_norm_error_pre": abs(float(np.linalg.norm(q_stored)) - 1.0),
        "stored_vs_rebuilt_up_to_sign_max_abs": min(maxabs(q_stored - q_rebuilt), maxabs(q_stored + q_rebuilt)),
        "stored_vs_axis_flipped_max_abs": maxabs(q_stored - np.array([qw, 0.0, 0.0, -qz])),
    }
    # register cross-checks (values the bridge file itself publishes)
    reg = {e["id"]: e for e in bridge["known_deviation_register"]}
    sec["register_crosscheck"] = {
        "CONTRACT_12DP_matrix_max_abs_exact_theta_vs_bridge_published": reg["CONTRACT_12DP_TRIG_TRUNCATION"]["matrix_max_abs_exact_theta_vs_bridge"],
        "CONTRACT_12DP_recomputed": sec["exact_theta_25p000014_vs_bridge_matrix_max_abs"],
        "EXACT_25DEG_published": reg["EXACT_25DEG_REFERENCE_ONLY"]["matrix_max_abs_vs_bridge"],
        "EXACT_25DEG_recomputed": sec["exact_25deg_reference_vs_bridge_matrix_max_abs"],
        "WP11_F03_matrix_max_abs_published": reg["WP11-F-03_ROUNDED_CLOCK_SPELLING"]["matrix_max_abs_vs_bridge"],
        "WP11_F03_recomputed": sec["rounded_spelling_vs_bridge_matrix_max_abs"],
        "WP11_F03_witness_published_m": reg["WP11-F-03_ROUNDED_CLOCK_SPELLING"]["witness_recomputed_this_round_m_on_c01_arm_cg"],
        "WP11_F03_witness_recomputed_m": sec["c01_spelling_witness_recomputed_m"],
        "numerical_health_det_R_B_published": bridge["numerical_health"]["det_R_B"],
        "numerical_health_det_R_B_recomputed": sec["det_R_B"],
        "closure_published": bridge["numerical_health"]["T_dyn_at_B_minus_T_phys_max_abs"],
        "closure_recomputed": sec["T_dyn_at_B_minus_T_phys_max_abs"],
    }
    sec["bridge_file_sha256"] = sha256_file(BRIDGE_REL)
    return sec


# ============================================================================
# S2: ATK-06 silent average - blacklist numeric/string scan over all round1 files
# ============================================================================
def _walk_numbers(obj, path=""):
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        yield path, float(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_numbers(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_numbers(v, f"{path}[{i}]")


def s2_atk06_silent_average():
    sec = {"blacklist_targets": [], "numeric_hits": [], "string_hits": [], "keyword_hits": [],
           "rotation_block_det_scan": []}
    odr = load_json_rel(E21_ODR01_LANE_REL)
    wp = load_json_rel(E21_WP11_LANE_REL)
    odr_cg = np.asarray(odr["initial_mass_properties_vs_V3_R2_C07"]["computed_cg_S_m"], dtype=float)
    wp_cg = np.asarray(wp["initial_mass_properties_vs_V3_R2_C07"]["computed_cg_S_m"], dtype=float)
    odr_I = np.asarray(odr["initial_mass_properties_vs_V3_R2_C07"]["computed_inertia_about_system_cg_S_kg_m2"], dtype=float)
    wp_I = np.asarray(wp["initial_mass_properties_vs_V3_R2_C07"]["computed_inertia_about_system_cg_S_kg_m2"], dtype=float)
    mid_cg = 0.5 * (odr_cg + wp_cg)
    mid_I = 0.5 * (odr_I + wp_I)
    targets = {
        "avg_peak_deg_HARD": 29.226410622980581,
        "avg_peak_deg_rounded": 29.22641062298058,
        "legacy_total_24kg": 24.0,
        "legacy_bus_23p3032134_context_classify": 23.3032134,
        "legacy_R1_panel_mass": 0.3483933,
        "legacy_R1_mu": 1.7419665,
        "legacy_R1_EI_1": 4.3630e-3,
        "legacy_R1_EI_2": 8.9042e-3,
        "legacy_R1_EI_3": 1.5047e-2,
    }
    for i, ax in enumerate("xyz"):
        targets[f"midpoint_cg_{ax}"] = float(mid_cg[i])
    for i in range(3):
        for j in range(3):
            targets[f"midpoint_inertia_{i}{j}"] = float(mid_I[i, j])
    sec["blacklist_targets"] = [{"name": k, "value": v} for k, v in targets.items()]
    hard = {"avg_peak_deg_HARD", "avg_peak_deg_rounded", "legacy_R1_panel_mass", "legacy_R1_mu",
            "legacy_R1_EI_1", "legacy_R1_EI_2", "legacy_R1_EI_3"} | {k for k in targets if k.startswith("midpoint_")}

    files_scanned = 0
    for dirpath, _dn, filenames in os.walk(BASE):
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            rel = p.relative_to(ROOT).as_posix()
            if rel.startswith((BASE / "redteam_round2").relative_to(ROOT).as_posix()):
                continue
            files_scanned += 1
            text = p.read_text(encoding="utf-8", errors="replace")
            # string-level blacklist
            for s in ["29.226410622980581", "29.22641062298058", "0.3483933", "1.7419665"]:
                if s in text:
                    for ln, line in enumerate(text.splitlines(), 1):
                        if s in line:
                            sec["string_hits"].append({"file": rel, "line": ln, "needle": s,
                                                       "context": line.strip()[:200]})
            # keyword scan (averaging / selection vocabulary)
            for ln, line in enumerate(text.splitlines(), 1):
                if re.search(r"(?i)averag|midpoint|blend| either |or_use|alternativ|select|choose|chosen", line):
                    sec["keyword_hits"].append({"file": rel, "line": ln, "context": line.strip()[:220]})
            # numeric leaf scan on parseable json/yaml
            if fn.endswith(".json") or fn.endswith(".yaml"):
                try:
                    obj = json.loads(text) if fn.endswith(".json") else yaml.safe_load(text)
                except Exception:
                    obj = None
                if obj is not None:
                    for kpath, val in _walk_numbers(obj):
                        for name, tv in targets.items():
                            if abs(val - tv) <= 1e-9 * max(1.0, abs(tv)):
                                sec["numeric_hits"].append({"file": rel, "key": kpath, "value": val,
                                                            "target": name,
                                                            "class": "HARD" if name in hard else "CONTEXT_CLASSIFY"})
            # rotation-like 3x3/4x4 block det scan on yaml/json
                if obj is not None:
                    def scan_blocks(o, kp=""):
                        if isinstance(o, dict):
                            for k, v in o.items():
                                kk = f"{kp}.{k}"
                                if isinstance(v, list) and re.search(r"(?i)rotation|homogeneous|transform|C_S|4x4", k):
                                    arr = np.asarray(v, dtype=float) if all(isinstance(r, list) for r in v) else None
                                    if arr is not None and arr.shape == (4, 4):
                                        d = float(np.linalg.det(arr[:3, :3]))
                                        if abs(d - 1.0) > 1e-6:
                                            sec["rotation_block_det_scan"].append({"file": rel, "key": kk, "det": d})
                                    elif arr is not None and arr.shape == (3, 3) and re.search(r"(?i)rotation", k):
                                        d = float(np.linalg.det(arr))
                                        if abs(d - 1.0) > 1e-6:
                                            sec["rotation_block_det_scan"].append({"file": rel, "key": kk, "det": d})
                                scan_blocks(v, kk)
                        elif isinstance(o, list):
                            for i, v in enumerate(o):
                                scan_blocks(v, f"{kp}[{i}]")
                    scan_blocks(obj)
    sec["files_scanned"] = files_scanned
    sec["n_hard_numeric_hits"] = sum(1 for h in sec["numeric_hits"] if h["class"] == "HARD")
    return sec


# ============================================================================
# S3: ATK-04 frame mixing - unique bridge id + hash on every cross-frame quantity
# ============================================================================
def s3_atk04_frame_mixing():
    sec = {"bridge_sha256": sha256_file(BRIDGE_REL)}
    fb06 = load_yaml_rel(FB06_REL)
    per_config = []
    for cfg in fb06["configurations"]:
        cid = cfg["configuration_id"]
        arm = next(m for m in cfg["composition_candidate"] if m["component_id"] == ARM_ID)
        prov = arm.get("bridge_provenance", {})
        non_arm_with_prov = [m["component_id"] for m in cfg["composition_candidate"]
                             if m["component_id"] != ARM_ID and "bridge_provenance" in m]
        per_config.append({
            "configuration_id": cid,
            "candidate_semantics": cfg.get("candidate_semantics"),
            "arm_row_action": cfg.get("arm_row_action"),
            "bridge_file_ref_ok": prov.get("bridge_file", "").endswith("02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml"),
            "bridge_sha_matches_recomputed": prov.get("bridge_sha256", "").upper() == sec["bridge_sha256"],
            "bridge_uncertainty_null": prov.get("bridge_uncertainty", "MISSING") is None,
            "non_arm_members_with_bridge_provenance": non_arm_with_prov,
            "arm_pre_bridge_values_present": ("pre_bridge_com_S_m" in prov and "pre_bridge_inertia_about_own_com_S_kg_m2" in prov),
        })
    sec["fb06_per_config"] = per_config
    sec["fb06_top_consumption_semantics"] = fb06.get("consumption_semantics")
    sec["fb06_bridge_artifact_sha_ok"] = fb06["bridge_artifact"]["sha256"].upper() == sec["bridge_sha256"]
    v6 = load_yaml_rel(V6_REL)
    r3 = load_yaml_rel(R3_REL)
    def rebind_audit(doc, label):
        fa = doc["replaced_sections"]["frame_authority"] if label == "V6" else None
        ah = doc["replaced_sections"]["authority_hierarchy"] if label == "R3" else None
        new = (fa or ah)["new_in_this_candidate"]
        br = new.get("installation_bridge") or new.get("mount_level_installation_bridge")
        sc = new["single_consumption_semantics_block"]
        overlay_key = "system_design_mass_properties_candidate_overlay" if label == "V6" \
            else "system_mass_configurations_candidate_overlay"
        ov = new.get(overlay_key)
        if ov is None and label == "V6":
            ov = doc["replaced_sections"]["design_mass_model_binding"].get(overlay_key)
        return {
            "bridge_id": br["bridge_id"],
            "bridge_sha_ok": br["sha256"].upper() == sec["bridge_sha256"],
            "classification": br["classification"],
            "validation_shas_ok": all(v["sha256"].upper() == sha256_file(v["path"]) for v in br["validation"]),
            "single_consumption_semantics": sc["single_consumption_semantics"],
            "consumer_ambiguity_count": sc["consumer_ambiguity_count"],
            "evidence_sha_ok": sc["evidence"]["sha256"].upper() == sha256_file(sc["evidence"]["path"]),
            "mass_overlay_sha_ok": (ov["sha256"].upper() == sha256_file(ov["path"])) if ov else "MISSING",
        }
    sec["v6_audit"] = rebind_audit(v6, "V6")
    sec["r3_audit"] = rebind_audit(r3, "R3")
    # V6 mass overlay sha (its own block)
    ov = v6["replaced_sections"]["design_mass_model_binding"]["system_design_mass_properties_candidate_overlay"]
    sec["v6_mass_overlay_sha_ok"] = ov["sha256"].upper() == sha256_file(ov["path"])
    return sec


# ============================================================================
# S4: ATK-12 Steiner / uncertainty-rotation audit
# ============================================================================
def _steiner(m, r):
    r = np.asarray(r, dtype=float)
    return float(m) * ((r @ r) * np.eye(3) - np.outer(r, r))


def s4_atk12_steiner():
    sec = {}
    contract = load_yaml_rel(E21_AUTHORITY_REL)
    hyp = contract["placement_hypotheses"]
    T_dyn = np.asarray(hyp["ODR01_DYNAMICS_T_SM"]["transform_S_A0_rows"], dtype=float)
    T_phys = np.asarray(hyp["WP11_PHYSICAL_GEOMETRY_CONTEXT"]["transform_S_A0_rows"], dtype=float)
    B = np.linalg.inv(T_dyn) @ T_phys
    Rb, tb = B[:3, :3], B[:3, 3]
    residual = load_json_rel(E21_RESIDUAL_REL)
    arm_m = float(residual["subtracted_complete_arm_at_ODR01"]["mass_kg"])
    arm_cg_dyn = np.asarray(residual["subtracted_complete_arm_at_ODR01"]["cg_S_m"], dtype=float)
    arm_I_dyn = np.asarray(residual["subtracted_complete_arm_at_ODR01"]["inertia_about_arm_cg_S_kg_m2"], dtype=float)

    # (d.1) Steiner witness scale
    sec["arm_mass_kg"] = arm_m
    sec["steiner_witness_m_times_d2_recomputed"] = arm_m * float(tb @ tb)
    sec["steiner_witness_published"] = 0.0024302436760318276
    sec["steiner_witness_abs_diff"] = abs(sec["steiner_witness_m_times_d2_recomputed"] - 0.0024302436760318276)

    # (d.2) about-origin transform: conjugated vs literal (forbidden) reading
    r_dyn = (np.linalg.inv(T_dyn) @ np.append(arm_cg_dyn, 1.0))[:3]
    r_phys = (np.linalg.inv(B) @ np.append(r_dyn, 1.0))[:3]
    I_C_phys = Rb.T @ arm_I_dyn @ Rb
    I_O_phys = I_C_phys + _steiner(arm_m, r_phys)
    r_dyn_mapped = Rb @ r_phys + tb
    I_O_dyn_conjugated = Rb @ I_O_phys @ Rb.T + arm_m * (_steiner(1.0, r_dyn_mapped) - _steiner(1.0, Rb @ r_phys))
    I_O_dyn_literal = Rb @ I_O_phys @ Rb.T + arm_m * (_steiner(1.0, r_dyn_mapped) - _steiner(1.0, r_phys))
    I_O_dyn_direct = arm_I_dyn + _steiner(arm_m, r_dyn)
    sec["conjugated_transform_vs_first_principles_max_abs"] = maxabs(I_O_dyn_conjugated - I_O_dyn_direct)
    sec["literal_unconjugated_deviation_max_abs"] = maxabs(I_O_dyn_literal - I_O_dyn_direct)
    sec["literal_deviation_published"] = 0.007710680881610109

    # (d.3) lane-delta explanation re-derived independently (residual fixed, arm mapped via C_S_inv)
    C_S = T_dyn @ np.linalg.inv(T_phys)
    C_S_inv = np.linalg.inv(C_S)
    Rci, pci = C_S_inv[:3, :3], C_S_inv[:3, 3]
    res_m = float(residual["fixed_residual"]["mass_kg"])
    res_cg = np.asarray(residual["fixed_residual"]["cg_S_m"], dtype=float)
    res_I = np.asarray(residual["fixed_residual"]["inertia_about_residual_cg_S_kg_m2"], dtype=float)
    sys_m = float(residual["source_total"]["mass_kg"])
    sys_cg = np.asarray(residual["source_total"]["cg_S_m"], dtype=float)
    sys_I = np.asarray(residual["source_total"]["inertia_about_system_cg_S_kg_m2"], dtype=float)
    arm_cg_phys = Rci @ arm_cg_dyn + pci
    arm_I_phys = Rci @ arm_I_dyn @ Rci.T
    def combine(bodies):
        m = math.fsum(b[0] for b in bodies)
        cg = np.sum([b[0] * b[1] for b in bodies], axis=0) / m
        I = np.zeros((3, 3))
        for mm, cc, ii in bodies:
            I += ii + _steiner(mm, cc - cg)
        return m, cg, 0.5 * (I + I.T)
    sm, scg, sI = combine([(res_m, res_cg, res_I), (arm_m, arm_cg_phys, arm_I_phys)])
    sec["lane_delta"] = {
        "mass_invariant": float(sm - sys_m),
        "delta_cg_norm_recomputed": float(np.linalg.norm(scg - sys_cg)),
        "delta_cg_norm_published_G11": 0.003524348142565558,
        "delta_inertia_max_abs_recomputed": maxabs(sI - sys_I),
        "delta_inertia_max_abs_published_G11": 0.10311953522836159,
        "bridged_vs_published_wp11_cg_max_abs": None,
        "bridged_vs_published_wp11_I_max_abs": None,
    }
    wp = load_json_rel(E21_WP11_LANE_REL)
    wp_cg = np.asarray(wp["initial_mass_properties_vs_V3_R2_C07"]["computed_cg_S_m"], dtype=float)
    wp_I = np.asarray(wp["initial_mass_properties_vs_V3_R2_C07"]["computed_inertia_about_system_cg_S_kg_m2"], dtype=float)
    sec["lane_delta"]["bridged_vs_published_wp11_cg_max_abs"] = maxabs(scg - wp_cg)
    sec["lane_delta"]["bridged_vs_published_wp11_I_max_abs"] = maxabs(sI - wp_I)

    # (d.4) uncertainty-rotation audit on FB-06 arm rows (C01..C06 bridged)
    fb06 = load_yaml_rel(FB06_REL)
    v3 = load_yaml_rel(V3_R2_REL)
    audit = []
    for cid in sorted(PHYSICAL_CONSUMED | DYNAMICS_CONSUMED):
        cfg_new = next(c for c in fb06["configurations"] if c["configuration_id"] == cid)
        cfg_old = next(c for c in v3["configurations"] if c["configuration_id"] == cid)
        arm_new = next(m for m in cfg_new["composition_candidate"] if m["component_id"] == ARM_ID)
        arm_old = next(m for m in cfg_old["composition"] if m["component_id"] == ARM_ID)
        unc_keys = [k for k in arm_old if "uncertainty" in k]
        verbatim = all(arm_new.get(k) == arm_old.get(k) for k in unc_keys)
        moved = not (np.allclose(np.asarray(arm_new["com_S_m"], float), np.asarray(arm_old["com_S_m"], float), atol=0, rtol=0)
                     and np.allclose(np.asarray(arm_new["inertia_about_own_com_S_kg_m2"], float),
                                     np.asarray(arm_old["inertia_about_own_com_S_kg_m2"], float), atol=0, rtol=0))
        # negative control: what R U R^T element-wise rotation WOULD have produced (must NOT appear)
        audit.append({"configuration_id": cid,
                      "uncertainty_keys_checked": unc_keys,
                      "uncertainty_verbatim_vs_V3R2": bool(verbatim),
                      "arm_values_actually_moved": bool(moved) if cid in PHYSICAL_CONSUMED else "UNCHANGED_BY_DESIGN",
                      "mass_uncertainty_verbatim": arm_new.get("mass_standard_uncertainty_kg") == arm_old.get("mass_standard_uncertainty_kg"),
                      "pose_status_verbatim": arm_new.get("pose_status") == arm_old.get("pose_status")})
    sec["fb06_uncertainty_audit"] = audit
    sec["fb04_method_declaration_forbids_uncertainty_rotation"] = (
        "never rotated" in load_json_rel(FB04_REL)["method_declaration"]["uncertainty_policy"])
    return sec


# ============================================================================
# S5: (f) FB-06 nine-configuration independent recompute (C01/C05/C07 spotlight)
# ============================================================================
def _inertia_of(member):
    v = member["inertia_about_own_com_S_kg_m2"]
    if isinstance(v, (list, np.ndarray)):
        return np.asarray(v, dtype=float)
    return np.array([[v["Ixx"], v["Ixy"], v["Ixz"]],
                     [v["Ixy"], v["Iyy"], v["Iyz"]],
                     [v["Ixz"], v["Iyz"], v["Izz"]]], dtype=float)


def _aggregate(members):
    mass = math.fsum(float(m["mass_kg"]) for m in members)
    cg = np.sum([float(m["mass_kg"]) * np.asarray(m["com_S_m"], dtype=float) for m in members], axis=0) / mass
    I = np.zeros((3, 3))
    for m in members:
        c = np.asarray(m["com_S_m"], dtype=float)
        I += _inertia_of(m) + _steiner(float(m["mass_kg"]), c - cg)
    return mass, cg, 0.5 * (I + I.T)


def s5_fb06_recompute():
    sec = {}
    contract = load_yaml_rel(E21_AUTHORITY_REL)
    hyp = contract["placement_hypotheses"]
    T_dyn = np.asarray(hyp["ODR01_DYNAMICS_T_SM"]["transform_S_A0_rows"], dtype=float)
    T_phys = np.asarray(hyp["WP11_PHYSICAL_GEOMETRY_CONTEXT"]["transform_S_A0_rows"], dtype=float)
    C_S = T_dyn @ np.linalg.inv(T_phys)          # my own conjugate, not the bridge file's
    Rcs, pcs = C_S[:3, :3], C_S[:3, 3]

    v3 = load_yaml_rel(V3_R2_REL)
    fb06 = load_yaml_rel(FB06_REL)
    rows = []
    for cfg in v3["configurations"]:
        cid = cfg["configuration_id"]
        members = cfg["composition"]
        arm = next(m for m in members if m["component_id"] == ARM_ID)
        stated_m = float(cfg["mass"]["value_kg"])
        stated_cg = np.asarray(cfg["center_of_mass"]["xyz_m"], dtype=float)
        ic = cfg["inertia"]["components_kg_m2"]
        stated_I = np.array([[ic["Ixx"], ic["Ixy"], ic["Ixz"]],
                             [ic["Ixy"], ic["Iyy"], ic["Iyz"]],
                             [ic["Ixz"], ic["Iyz"], ic["Izz"]]], dtype=float)
        agg_m, agg_cg, agg_I = _aggregate(members)
        arm_cg_old = np.asarray(arm["com_S_m"], dtype=float)
        arm_I_old = _inertia_of(arm)
        if cid in PHYSICAL_CONSUMED:
            arm_cg_new = Rcs @ arm_cg_old + pcs
            arm_I_new = Rcs @ arm_I_old @ Rcs.T
        else:
            arm_cg_new, arm_I_new = arm_cg_old.copy(), arm_I_old.copy()
        cand_members = []
        for m in members:
            if m["component_id"] == ARM_ID:
                m2 = dict(m)
                m2["com_S_m"] = arm_cg_new
                m2["inertia_about_own_com_S_kg_m2"] = arm_I_new
                cand_members.append(m2)
            else:
                cand_members.append(m)
        cm, ccg, cI = _aggregate(cand_members)
        pub = next(c for c in fb06["configurations"] if c["configuration_id"] == cid)
        pub_cg = np.asarray(pub["bridged_candidate"]["cg_S_m"], dtype=float)
        pub_I = np.asarray(pub["bridged_candidate"]["inertia_about_system_cg_S_kg_m2"], dtype=float)
        # delta explanation via arm-row-only action (my own derivation)
        m_arm = float(arm["mass_kg"])
        dcg_pred = m_arm / stated_m * (arm_cg_new - arm_cg_old)
        dI_pred = (arm_I_new - arm_I_old) \
            + m_arm * (_steiner(1.0, arm_cg_new - ccg) - _steiner(1.0, arm_cg_old - stated_cg)) \
            + np.sum([float(m["mass_kg"]) * (_steiner(1.0, np.asarray(m["com_S_m"], float) - ccg)
                                             - _steiner(1.0, np.asarray(m["com_S_m"], float) - stated_cg))
                      for m in members if m["component_id"] != ARM_ID], axis=0)
        # non-arm members deep verbatim check
        non_arm_verbatim = True
        for m_new, m_old in zip(pub["composition_candidate"], members):
            if m_old["component_id"] == ARM_ID:
                continue
            if m_new != m_old:
                non_arm_verbatim = False
        # arm row: everything except com/inertia/bridge_provenance must be verbatim
        arm_new_pub = next(m for m in pub["composition_candidate"] if m["component_id"] == ARM_ID)
        strip = {"com_S_m", "inertia_about_own_com_S_kg_m2", "bridge_provenance"}
        arm_rest_verbatim = all(arm_new_pub.get(k) == arm.get(k) for k in arm if k not in strip)
        rows.append({
            "configuration_id": cid,
            "aggregator_stated_minus_members_max_abs": max(maxabs(stated_m - agg_m), maxabs(stated_cg - agg_cg), maxabs(stated_I - agg_I)),
            "mass_invariant_candidate_minus_stated": float(cm - stated_m),
            "my_candidate_vs_fb06_cg_max_abs": maxabs(ccg - pub_cg),
            "my_candidate_vs_fb06_inertia_max_abs": maxabs(cI - pub_I),
            "delta_cg_explained_residual_max_abs": maxabs((ccg - stated_cg) - dcg_pred),
            "delta_inertia_explained_residual_max_abs": maxabs((cI - stated_I) - dI_pred),
            "non_arm_members_deep_verbatim": bool(non_arm_verbatim),
            "arm_row_nonbridged_fields_verbatim": bool(arm_rest_verbatim),
            "pose_status": arm.get("pose_status"),
            "candidate_spd_min_eigenvalue": float(np.linalg.eigvalsh(cI)[0]),
        })
    sec["per_configuration"] = rows
    c05 = next(r for r in rows if r["configuration_id"] == "C05")
    sec["c05_pose_status_verbatim_string"] = c05["pose_status"]
    sec["c05_pose_status_expected"] = "HELD_CANDIDATE_FK_REGRESSION_FAIL_MAX_RESIDUAL_567P734_MM_RETAINED_FACT_NOT_ABSORBED_BY_UNCERTAINTY"
    sec["c05_pose_status_carried_exact"] = (c05["pose_status"] == sec["c05_pose_status_expected"])
    sec["c05_carried_note_in_fb06"] = fb06.get("carried_pose_status_note")
    sec["worst"] = {
        "mass_invariant_abs_max": max(abs(r["mass_invariant_candidate_minus_stated"]) for r in rows),
        "my_vs_fb06_cg_max": max(r["my_candidate_vs_fb06_cg_max_abs"] for r in rows),
        "my_vs_fb06_inertia_max": max(r["my_candidate_vs_fb06_inertia_max_abs"] for r in rows),
        "delta_cg_explained_worst": max(r["delta_cg_explained_residual_max_abs"] for r in rows),
        "delta_inertia_explained_worst": max(r["delta_inertia_explained_residual_max_abs"] for r in rows),
        "c07_c09_exact_zero": all(rows[i]["mass_invariant_candidate_minus_stated"] == 0.0
                                  and rows[i]["my_candidate_vs_fb06_cg_max_abs"] == 0.0
                                  for i in range(6, 9)),
    }
    return sec


# ============================================================================
# S6: (g) V6/R3 candidate audit
# ============================================================================
def s6_v6_r3_candidates():
    sec = {}
    r0 = load_json_rel(R0_RECEIPT_REL)
    r0_pins = {e["path"]: (e["sha256"], e["bytes"]) for e in r0.get("baseline_verification", [])}
    for label, rel in [("wp10_V5_R2", WP10_BASE_REL), ("wp13_R2", WP13_BASE_REL)]:
        cur = sha256_file(rel)
        n_bytes = len((ROOT / rel).read_bytes())
        sec[f"{label}_base_untouched"] = {
            "current_sha256": cur, "current_bytes": n_bytes,
            "round0_receipt_pin": r0_pins.get(rel, [None, None])[0],
            "round0_receipt_bytes": r0_pins.get(rel, [None, None])[1],
            "matches_round0_receipt": bool(r0_pins.get(rel) and cur == r0_pins[rel][0] and n_bytes == r0_pins[rel][1]),
        }
    v6 = load_yaml_rel(V6_REL)
    r3 = load_yaml_rel(R3_REL)
    v5 = load_json_rel(V5_GATE_REL)
    r2 = load_yaml_rel(WP13_BASE_REL)
    contract = load_yaml_rel(E21_AUTHORITY_REL)
    # V5 11 fail-closed invariants verbatim
    v6_inv = v6["carried_verbatim_from_v5_gate"]["fail_closed_invariants"]
    sec["v6_carries_v5_invariants"] = {
        "count_v6": len(v6_inv), "count_v5_source": len(v5["fail_closed_invariants"]),
        "verbatim_equal": v6_inv == v5["fail_closed_invariants"]}
    r3_inv = r3["carried_verbatim_from_v5_gate"]["fail_closed_invariants"]
    sec["r3_carries_v5_invariants"] = {"count_r3": len(r3_inv), "verbatim_equal": r3_inv == v5["fail_closed_invariants"]}
    # R2 11 retained_holds + prohibitions verbatim
    r3_holds = r3["carried_verbatim_from_r2_base"]["retained_holds"]
    sec["r3_carries_r2_retained_holds"] = {
        "count_r3": len(r3_holds), "count_r2_source": len(r2["retained_holds"]),
        "verbatim_equal": r3_holds == r2["retained_holds"]}
    r3_prop = r3["carried_verbatim_from_r2_base"]["prohibitions_honored"]
    sec["r3_carries_r2_prohibitions"] = {
        "count_r3": len(r3_prop), "count_r2_source": len(r2["prohibitions_honored"]),
        "verbatim_equal": r3_prop == r2["prohibitions_honored"]}
    # e21 11 mandatory holds verbatim in both candidates
    for label, doc in [("v6", v6), ("r3", r3)]:
        mh = doc["carried_verbatim_from_e21_authority"]["mandatory_holds"]
        sec[f"{label}_carries_e21_mandatory_holds"] = {
            "count": len(mh), "count_source": len(contract["mandatory_holds"]),
            "verbatim_equal": mh == contract["mandatory_holds"]}
    # status / authorization fields
    for label, doc, rel in [("v6", v6, V6_REL), ("r3", r3, R3_REL)]:
        sec[f"{label}_status_fields"] = {
            "filename_contains_CANDIDATE": "CANDIDATE" in Path(rel).name,
            "candidate_flag": doc.get("candidate"),
            "status": doc.get("status"),
            "next_stage_authorized": doc.get("next_stage_authorized"),
            "release_credit": doc.get("release_credit"),
            "review_status": doc.get("review_status"),
            "required_acknowledgement": doc.get("required_acknowledgement"),
            "base_document_sha_ok": doc["base_document"]["sha256"].upper() == sha256_file(doc["base_document"]["path"]),
            "sections_untouched_list": doc.get("sections_explicitly_untouched_by_reference"),
        }
    # V5 gate still HOLD / unresolved today
    sec["v5_gate_today"] = {"gate": v5.get("gate"), "next_stage_authorized": v5.get("next_stage_authorized"),
                            "single_consumption_rule_resolved":
                            v5.get("m7_r2_arm_placement_consumption", {}).get("single_consumption_rule_resolved")}
    return sec


# ============================================================================
# S7: hygiene sweeps (ATK-01 empty / ATK-02 null+PASS) on round1 products
# ============================================================================
def s7_hygiene():
    sec = {"empty_or_unparseable": [], "null_pass_coexistence": [], "products_next_stage_flags": {}}
    targets = {"FB03": (FB03_REL, "json"), "FB04": (FB04_REL, "json"), "FB05": (FB05_REL, "json"),
               "FB06": (FB06_REL, "yaml"), "V6": (V6_REL, "yaml"), "R3": (R3_REL, "yaml"),
               "BRIDGE": (BRIDGE_REL, "yaml")}
    def walk_null_pass(o, kp=""):
        hits = []
        if isinstance(o, dict):
            status_pass = o.get("status") == "PASS" or o.get("pass") is True
            if status_pass and o.get("value", "NONE") is None:
                hits.append(kp)
            for k, v in o.items():
                hits += walk_null_pass(v, f"{kp}.{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                hits += walk_null_pass(v, f"{kp}[{i}]")
        return hits
    for label, (rel, kind) in targets.items():
        raw = (ROOT / rel).read_bytes()
        if len(raw) == 0:
            sec["empty_or_unparseable"].append(rel)
            continue
        try:
            obj = json.loads(raw) if kind == "json" else yaml.safe_load(raw)
        except Exception as e:
            sec["empty_or_unparseable"].append(f"{rel}: {e}")
            continue
        sec["null_pass_coexistence"] += [{"product": label, "key": h} for h in walk_null_pass(obj)]
        sec["products_next_stage_flags"][label] = {
            "next_stage_authorized": obj.get("next_stage_authorized"),
            "release_credit": obj.get("release_credit"),
            "overall_or_status": obj.get("overall", obj.get("status"))}
    return sec


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    R["sections"]["S0_hash_sentinel"] = s0_hash_sentinel()
    R["sections"]["S1_ATK11_bridge"] = s1_atk11_bridge()
    R["sections"]["S2_ATK06_silent_average"] = s2_atk06_silent_average()
    R["sections"]["S3_ATK04_frame_mixing"] = s3_atk04_frame_mixing()
    R["sections"]["S4_ATK12_steiner"] = s4_atk12_steiner()
    R["sections"]["S5_FB06_recompute"] = s5_fb06_recompute()
    R["sections"]["S6_V6_R3_candidates"] = s6_v6_r3_candidates()
    R["sections"]["S7_hygiene"] = s7_hygiene()
    OUT_FILE.write_bytes((json.dumps(R, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"))
    print("WROTE", OUT_FILE)
    s0 = R["sections"]["S0_hash_sentinel"]["summary"]
    print("S0:", json.dumps(s0))
    s1 = R["sections"]["S1_ATK11_bridge"]
    print("S1 closure:", s1["T_dyn_at_B_minus_T_phys_max_abs"], "| det:", s1["det_R_B"],
          "| stored-vs-rebuilt:", s1["stored_B_vs_rebuilt_dense_max_abs"])
    print("S1 witnesses:", json.dumps(s1["register_crosscheck"], indent=1))
    s2 = R["sections"]["S2_ATK06_silent_average"]
    print("S2: files", s2["files_scanned"], "hard numeric hits", s2["n_hard_numeric_hits"],
          "string hits", len(s2["string_hits"]), "keyword hits", len(s2["keyword_hits"]),
          "det anomalies", len(s2["rotation_block_det_scan"]))
    s4 = R["sections"]["S4_ATK12_steiner"]
    print("S4: steiner witness", s4["steiner_witness_m_times_d2_recomputed"],
          "conjugated residual", s4["conjugated_transform_vs_first_principles_max_abs"],
          "literal deviation", s4["literal_unconjugated_deviation_max_abs"])
    s5w = R["sections"]["S5_FB06_recompute"]["worst"]
    print("S5 worst:", json.dumps(s5w))
    print("S5 C05 pose carried:", R["sections"]["S5_FB06_recompute"]["c05_pose_status_carried_exact"])
    s6 = R["sections"]["S6_V6_R3_candidates"]
    print("S6:", json.dumps({k: v for k, v in s6.items() if "verbatim_equal" in json.dumps(v) or "untouched" in k}, default=str)[:600])
    print("S7 null-pass hits:", len(R["sections"]["S7_hygiene"]["null_pass_coexistence"]))


if __name__ == "__main__":
    main()
