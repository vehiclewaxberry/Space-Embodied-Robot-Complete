"""MPI-FB-02: freeze the unique B601 physical<->dynamics bridge.

Derives B = inv(T_S_A0_dyn) @ T_S_A0_phys and inv(B) independently from the
e21 authority contract (hash-pinned), cross-checks against the closed form
Trans(z,+0.02275 m) . Rot(z,+25.000014 deg), pins the M3R flange-JSON
composition convention, and writes B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml.

Pure python/numpy. Read-only on every upstream file. Writes ONLY inside
round1_bridge/02_bridge/.
"""
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import yaml

sys.dont_write_bytecode = True

ROOT = Path("F:/China Graduate Future Flight Vehicle Innovation Competition")
OUT_DIR = ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/02_bridge"
OUT_FILE = OUT_DIR / "B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml"

E21_AUTHORITY_REL = "30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/00_authority/E21_AUTHORITY_CONTRACT_V1.yaml"
E21_AUTHORITY_SHA = "7D2E0792B3FF6BAB9BD9AE11A605341B20BAAB821961A7BA8E119996D1515D81"
M4_TREE_REL = "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/01_system_architecture/DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml"
M4_TREE_SHA = "67293323A45237FB9B415871A4160732EFB156DE74776C9E11ABA9C4202134CA"
WP11_CAL_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp11_cad_urdf_registration/B601_CAD_URDF_GEOMETRY_CALIBRATION_V1.yaml"
WP11_CAL_SHA = "7463C1309C35"
M3R_STACK_REL = "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/M3_interface_authority/M3R_TSM_PHYSICAL_STACK.yaml"
M3R_STACK_SHA = "172F3603E458"
M3R_FLANGE_REL = "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/M3_interface_authority/M3R_TSM_FRAME_TO_FLANGE_TRANSFORM.json"
M3R_FLANGE_SHA = "29303BA65DFD"
ODR_REGISTER_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_OWNER_DECISION_REGISTER_V1.yaml"
ODR_REGISTER_SHA = "F5B1572C0CFCEC35C40F262A3D7386AFA91DEC09DA94FE31FD03F5C04956F8B6"
F3R2_POSE_REL = "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/04_configurations/F3R2_ARM_INITIAL_POSE.yaml"
F3R2_POSE_SHA = "D6E33CB5993B"
V3_R2_REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml"
V3_R2_SHA = "3FD2557318E98748A37927977FA2925C18803668FE16391D824C184F646486BB"


def sha256_file(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest().upper()


def rot_z(theta: float) -> np.ndarray:
    c, s = math.cos(theta), math.sin(theta)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def rot_x(theta: float) -> np.ndarray:
    c, s = math.cos(theta), math.sin(theta)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def rot_y(theta: float) -> np.ndarray:
    c, s = math.cos(theta), math.sin(theta)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


def make_T(R: np.ndarray, t: np.ndarray) -> np.ndarray:
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = t
    return T


def rigid_inv(T: np.ndarray) -> np.ndarray:
    R, t = T[:3, :3], T[:3, 3]
    Ti = np.eye(4)
    Ti[:3, :3] = R.T
    Ti[:3, 3] = -R.T @ t
    return Ti


def R_to_quat_wxyz(R: np.ndarray) -> np.ndarray:
    tr = float(np.trace(R))
    if tr > 0.0:
        s = math.sqrt(tr + 1.0) * 2.0
        w = 0.25 * s
        x = (R[2, 1] - R[1, 2]) / s
        y = (R[0, 2] - R[2, 0]) / s
        z = (R[1, 0] - R[0, 1]) / s
    else:  # pragma: no cover - not expected for this bridge
        raise RuntimeError("unexpected rotation branch")
    q = np.array([w, x, y, z])
    return q / np.linalg.norm(q)


def maxabs(A: np.ndarray) -> float:
    return float(np.max(np.abs(A)))


def main() -> None:
    # ---- 0. hash-pin every consumed upstream file --------------------------
    pins = {}
    for rel, expected in [
        (E21_AUTHORITY_REL, E21_AUTHORITY_SHA),
        (M4_TREE_REL, M4_TREE_SHA),
        (M3R_STACK_REL, M3R_STACK_SHA),
        (M3R_FLANGE_REL, M3R_FLANGE_SHA),
        (ODR_REGISTER_REL, ODR_REGISTER_SHA),
        (F3R2_POSE_REL, F3R2_POSE_SHA),
        (WP11_CAL_REL, WP11_CAL_SHA),
        (V3_R2_REL, V3_R2_SHA),
    ]:
        actual = sha256_file(rel)
        if len(expected) == 64:
            ok = actual == expected
        else:
            ok = actual.startswith(expected)  # 12-hex short pin from round0 matrix
        if not ok:
            raise RuntimeError(f"hash drift on {rel}: {actual} != {expected}")
        pins[rel] = actual  # full 64-hex recorded in the bridge source_register

    # ---- 1. read the two authoritative transform_S_A0 ----------------------
    contract = yaml.safe_load((ROOT / E21_AUTHORITY_REL).read_text(encoding="utf-8"))
    hyp = contract["placement_hypotheses"]
    T_dyn = np.asarray(hyp["ODR01_DYNAMICS_T_SM"]["transform_S_A0_rows"], dtype=float)
    T_phys = np.asarray(hyp["WP11_PHYSICAL_GEOMETRY_CONTEXT"]["transform_S_A0_rows"], dtype=float)
    if hyp["averaging_forbidden"] is not True or hyp["branch_delta_is_uncertainty"] is not False:
        raise RuntimeError("e21 authority contract guard drift")

    # ---- 2. bridge derivation (two independent paths) ----------------------
    B_direct = rigid_inv(T_dyn) @ T_phys                      # path A: rigid inverse
    B_full_inv = np.linalg.inv(T_dyn) @ T_phys                # path B: dense inverse
    R_B, t_B = B_direct[:3, :3], B_direct[:3, 3]
    theta_from_matrix = math.atan2(R_B[1, 0], R_B[0, 0])      # derived angle
    # closed form: Trans(z, +0.02275) . Rot(z, +theta)
    B_closed = make_T(rot_z(theta_from_matrix), np.array([0.0, 0.0, 0.02275]))
    path_ab_max = maxabs(B_direct - B_full_inv)
    closed_max = maxabs(B_direct - B_closed)

    Bi_direct = rigid_inv(B_direct)
    Bi_dense = np.linalg.inv(B_direct)
    inv_paths_max = maxabs(Bi_direct - Bi_dense)

    # S-frame conjugates for already-S-expressed quantities
    C_S = T_dyn @ rigid_inv(T_phys)          # physical-consumption -> dynamics-consumption
    C_S_inv = rigid_inv(C_S)                 # dynamics-consumption -> physical-consumption

    # decomposition witness: R_phys = Rx_S(theta) @ R_dyn
    decomp_residual = maxabs(T_phys[:3, :3] - rot_x(theta_from_matrix) @ T_dyn[:3, :3])

    # ---- 3. witness family (never silently pick one) -----------------------
    theta_m3r_deg = 25.000014                                   # M3R measured clocking
    theta_contract_deg = math.degrees(theta_from_matrix)        # from contract 12-dp sin/cos
    B_m3r_exact = make_T(rot_z(math.radians(theta_m3r_deg)), np.array([0.0, 0.0, 0.02275]))
    B_25deg = make_T(rot_z(math.radians(25.0)), np.array([0.0, 0.0, 0.02275]))
    theta_rounded_deg = math.degrees(math.atan2(0.422618, 0.906308))  # F3R2 pose / V5R 6-dp spelling
    B_rounded = make_T(rot_z(math.radians(theta_rounded_deg)), np.array([0.0, 0.0, 0.02275]))
    # positional witness of the rounded spelling, computed on the real C01 arm-CG
    # lever: recover the A0-frame arm CG from the V3_R2 ledger C01 row (that row was
    # computed with the ROUNDED mount), then apply full-vs-rounded physical mounts.
    v3 = yaml.safe_load((ROOT / V3_R2_REL).read_text(encoding="utf-8"))
    c01 = next(c for c in v3["configurations"] if c["configuration_id"] == "C01")
    arm_c01 = next(x for x in c01["composition"]
                   if x["component_id"] == "b601_complete_arm_including_gripper_urdf_links")
    cg_S_c01_ledger = np.asarray(arm_c01["com_S_m"], dtype=float)
    s_r, c_r = 0.422618, 0.906308  # rounded spelling
    T_phys_rounded = np.array(
        [[0.0, 0.0, 1.0, 0.208],
         [s_r, c_r, 0.0, 0.0],
         [-c_r, s_r, 0.0, 0.0],
         [0.0, 0.0, 0.0, 1.0]])
    r_A0_c01 = rigid_inv(T_phys_rounded) @ np.append(cg_S_c01_ledger, 1.0)
    cg_full = T_phys @ r_A0_c01
    cg_rounded = T_phys_rounded @ r_A0_c01
    rounded_positional_witness_m = float(np.linalg.norm(cg_full - cg_rounded))
    witnesses = {
        "contract_matrix_derived_angle_deg": theta_contract_deg,
        "m3r_measured_clocking_deg": theta_m3r_deg,
        "m3r_minus_contract_angle_deg": theta_m3r_deg - theta_contract_deg,
        "m3r_exact_vs_contract_matrix_max_abs": maxabs(B_m3r_exact - B_direct),
        "exact_25deg_vs_contract_matrix_max_abs": maxabs(B_25deg - B_direct),
        "rounded_spelling_angle_deg": theta_rounded_deg,
        "rounded_spelling_vs_contract_matrix_max_abs": maxabs(B_rounded - B_direct),
        # positional witness of the rounded spelling on the C01 arm CG (real lever):
        "rounded_spelling_positional_witness_m_on_c01_arm_cg": rounded_positional_witness_m,
        "e21_audit_ledger_residual_mm_c01": 0.00011314150166020904,
        "round0_angle_report_deg": 25.000013999932,
        "round0_minus_this_derivation_deg": 25.000013999932 - theta_contract_deg,
    }

    # ---- 4. M3R flange JSON composition convention pin ---------------------
    flange = json.loads((ROOT / M3R_FLANGE_REL).read_text(encoding="utf-8"))
    t_json_mm = np.asarray(flange["translation_xyz_mm"], dtype=float)
    R_json = np.asarray(flange["rotation_matrix"], dtype=float)
    T_json = make_T(R_json, t_json_mm)
    T_dyn_mm = make_T(T_dyn[:3, :3], T_dyn[:3, 3] * 1000.0)
    naive = T_dyn_mm @ T_json                     # WRONG standard T_M_child composition
    naive_origin = naive[:3, 3]
    m4 = yaml.safe_load((ROOT / M4_TREE_REL).read_text(encoding="utf-8"))
    m3r_local_rows = np.asarray(m4["frames"]["M3R_LOCAL"]["T_S_child_rows"], dtype=float) \
        if "frames" in m4 else None
    if m3r_local_rows is None:
        # fall back: the M4 tree nests frames under a top-level key; find it
        for key, value in m4.items():
            if isinstance(value, dict) and "M3R_LOCAL" in value:
                m3r_local_rows = np.asarray(value["M3R_LOCAL"]["T_S_child_rows"], dtype=float)
                break
    if m3r_local_rows is None:
        raise RuntimeError("M3R_LOCAL not found in M4 frame tree")
    m3r_local_origin = m3r_local_rows[:3, 3]
    misplace_vec = naive_origin - m3r_local_origin
    flange_pin = {
        "naive_T_dyn_mm_at_T_json_origin_mm": naive_origin.tolist(),
        "m4_M3R_LOCAL_origin_mm": m3r_local_origin.tolist(),
        "misplacement_vector_mm": misplace_vec.tolist(),
        "misplacement_z_component_mm": float(abs(misplace_vec[2])),
        "misplacement_norm_mm": float(np.linalg.norm(misplace_vec)),
        "correct_composition": (
            "translation_xyz_mm is expressed along the stack axis in S axes at the M origin: "
            "datum_origin_S_mm = [185.25,0,0] + translation_xyz_mm = [210.405, 0.015994151, -0.08636607]; "
            "datum_orientation_S = Rx_S(25.000014deg) . Ry(90deg) (= M4 M3R_LOCAL rows). "
            "The JSON rotation_matrix (pure Rx) and its translation are NOT a standard T_M_child block."
        ),
        "as_built_datum_210p405_in_bridge": False,
        "flange_json_in_bridge": False,
    }
    datum_origin_s = np.array([185.25, 0.0, 0.0]) + t_json_mm
    flange_pin["datum_origin_S_mm_reconstructed"] = datum_origin_s.tolist()
    flange_pin["datum_origin_matches_m4_fastener_end_plane"] = bool(
        np.allclose(datum_origin_s, np.array([210.405, 0.015994151, -0.086366070]), atol=1e-12))

    # ---- 5. quaternion + numerics ------------------------------------------
    quat = R_to_quat_wxyz(R_B)
    det_R = float(np.linalg.det(R_B))
    orth = maxabs(R_B.T @ R_B - np.eye(3))
    roundtrip = maxabs(Bi_direct @ B_direct - np.eye(4))
    closure_T = maxabs(T_dyn @ B_direct - T_phys)

    # ---- 6. emit bridge YAML ------------------------------------------------
    def rows(M: np.ndarray):
        return [[float(v) for v in row] for row in np.asarray(M, dtype=float)]

    bridge = {
        "schema": "B601_PHYSICAL_DYNAMICS_BRIDGE_V1",
        "generated_local": "2026-08-23T18:30:00+08:00",
        "generator": "KIMI M7 Wave-2a AGENT-1 MPI-FB-02 (pure python/numpy; no CAD/FEA process)",
        "status": "FROZEN_CANDIDATE_PENDING_OWNER_CONFIRMATION_AND_MPI_FB08_GATE",
        "authority_basis": {
            "ODR-43": "B601_ARM_PLACEMENT_RULE: DUAL_FRAME_EXPLICIT_BRIDGE - unique explicit T_PHYSICAL_TO_DYNAMIC; "
                      "no selection, no per-module mixing, no averaging, delta is not uncertainty, no silent substitution",
            "ODR-44": "APPROVE_BOUNDED_DETAILED_DESIGN - accepted URDF / Solar R2 / M3R / Gripper R1 / M7 FEA frozen; "
                      "no Route-C CAD before MPI-FB-01..08 all closed",
        },
        "frame_semantics": {
            "convention": "row-major 4x4 homogeneous T_parent_child: p_parent = T_parent_child @ p_child; "
                          "rotation columns = child axes expressed in parent",
            "T_S_A0_dynamics": {
                "meaning": "ODR-01 T_SM dynamics mounting reference (M frame); A0 = URDF base_link",
                "transform_S_A0_rows_m": rows(T_dyn),
                "source": E21_AUTHORITY_REL + " placement_hypotheses.ODR01_DYNAMICS_T_SM",
            },
            "T_S_A0_physical": {
                "meaning": "WP11 physical installation context (PHYSICAL_INSTALLATION_AUTHORITY per ODR-43)",
                "transform_S_A0_rows_m": rows(T_phys),
                "source": E21_AUTHORITY_REL + " placement_hypotheses.WP11_PHYSICAL_GEOMETRY_CONTEXT",
            },
        },
        "bridge_constant_ruling": {
            "unique_bridge_clocking_deg": 25.000014,
            "clocking_source": "M3R measured clocking_about_spacecraft_x_deg / pattern_clocking_about_x_deg "
                               "(M3R_TSM_PHYSICAL_STACK.yaml, sha " + M3R_STACK_SHA + "); identical full-precision "
                               "spelling in M4 frame tree, WP11 calibration, e21 authority contract",
            "contract_matrix_derived_angle_deg": theta_contract_deg,
            "contract_spelling_note": "the e21 authority contract carries sin/cos to 12 decimal places; the derived "
                                      "matrix angle differs from the 25.000014 deg constant only at the 12-decimal "
                                      "input-rounding noise level (see known_deviation_register entry "
                                      "CONTRACT_12DP_TRIG_TRUNCATION for the exact figures). The stored bridge "
                                      "matrix below is derived from the hash-pinned contract matrices, NOT "
                                      "re-synthesized from theta, so the bridge stays bit-consistent with the "
                                      "authority sources. round0's derivation reported 25.000013999932 deg vs this "
                                      "derivation's %.12f deg; the 3.2e-11 deg gap is one input-ulp of the 12-dp "
                                      "contract spelling (computation-path noise), not a content difference."
                                      % theta_contract_deg,
            "bridge_translation_m": 0.02275,
            "bridge_translation_note": "208.0 - 185.25 = 22.75 mm along +X_S, expressed in A0-dyn as +z (+0.02275 m); "
                                       "NOT 12.75 mm (adapter face) and NOT 2.405 mm (fastener plane) - stack-internal "
                                       "station distances are forbidden as bridge translation",
        },
        "T_PHYSICAL_TO_DYNAMIC": {
            "definition": "B = inv(T_S_A0_dyn) @ T_S_A0_phys; maps A0 coordinates expressed under the physical "
                          "installation convention into A0 coordinates under the dynamics convention: "
                          "p_A0dyn = B @ p_A0phys. Equivalently T_S_A0_dyn @ B = T_S_A0_phys (closure "
                          "max_abs = %.3e)." % closure_T,
            "closed_form": "B = Trans(z_A0, +0.02275 m) . Rot(z_A0, +25.000014 deg) - pure z screw, no x/y component",
            "translation_m": [float(v) for v in t_B],
            "quaternion_wxyz": [float(v) for v in quat],
            "rotation_matrix": rows(R_B),
            "homogeneous_4x4": rows(B_direct),
            "rotation_angle_deg_derived": theta_contract_deg,
            "rotation_axis_in_A0_dynamics": [0.0, 0.0, 1.0],
        },
        "T_DYNAMIC_TO_PHYSICAL_inverse_bridge": {
            "definition": "inv(B) = Trans(z_A0, -0.02275 m) . Rot(z_A0, -25.000014 deg); p_A0phys = inv(B) @ p_A0dyn",
            "translation_m": [float(v) for v in Bi_direct[:3, 3]],
            "rotation_matrix": rows(Bi_direct[:3, :3]),
            "homogeneous_4x4": rows(Bi_direct),
            "independent_dense_inverse_max_abs_vs_rigid_inverse": inv_paths_max,
        },
        "S_frame_conjugate_for_S_expressed_quantities": {
            "definition": "for quantities already expressed in S (e.g. WP2 ledger arm CG/inertia consumed under the "
                          "physical rail), re-expression between consumption semantics uses the S-frame conjugate "
                          "C_S = T_S_A0_dyn @ inv(T_S_A0_phys) = Trans_S([-0.02275,0,0] m) . Rot_S(x, -25.000014 deg); "
                          "p_S|dyn_consumption = C_S @ p_S|phys_consumption; I|dyn = R(C_S) @ I|phys @ R(C_S).T",
            "C_S_homogeneous_4x4": rows(C_S),
            "C_S_inverse_homogeneous_4x4": rows(C_S_inv),
        },
        "numerical_health": {
            "det_R_B": det_R,
            "max_abs_RtR_minus_I": orth,
            "roundtrip_invB_at_B_minus_I_max_abs": roundtrip,
            "T_dyn_at_B_minus_T_phys_max_abs": closure_T,
            "derivation_pathA_rigid_inv_vs_pathB_dense_inv_max_abs": path_ab_max,
            "closed_form_vs_derived_max_abs": closed_max,
            "physical_rotation_equals_RxS_theta_at_R_dyn_residual": decomp_residual,
        },
        "known_deviation_register": [
            {
                "id": "WP11-F-03_ROUNDED_CLOCK_SPELLING",
                "spelling": "sin/cos written 0.422618/0.906308 (= 24.999981252 deg) in F3R2_ARM_INITIAL_POSE.yaml, "
                            "V5R SYSTEM_FRAME_TREE.yaml and the M5 mesh-localization chain",
                "authoritative_spelling_deg": 25.000014,
                "witness": "arm CG displacement ~1.1e-4 mm at C01 (e21 audit ledger residual "
                           "0.00011314150166020904 mm; round0 end-to-end witness 1.1314e-4 mm)",
                "witness_recomputed_this_round_m_on_c01_arm_cg": rounded_positional_witness_m,
                "recomputation_method": "r_A0 = inv(T_phys_rounded) @ ledger_C01_arm_CG_S; "
                                        "||T_phys_full @ r_A0 - T_phys_rounded @ r_A0|| (V3_R2 C01 arm row, hash-pinned)",
                "disposition": "REGISTERED KNOWN DEVIATION - forbidden to silently mix spellings; ledger C01..C06 "
                               "arm rows carry the rounded spelling and are re-expressed in MPI-FB-06 through this "
                               "bridge with the residual documented, never zeroed",
                "matrix_max_abs_vs_bridge": witnesses["rounded_spelling_vs_contract_matrix_max_abs"],
            },
            {
                "id": "CONTRACT_12DP_TRIG_TRUNCATION",
                "spelling": "e21 authority contract sin/cos at 12 decimal places",
                "derived_angle_deg": theta_contract_deg,
                "angle_gap_vs_25_000014_deg": theta_m3r_deg - theta_contract_deg,
                "matrix_max_abs_exact_theta_vs_bridge": witnesses["m3r_exact_vs_contract_matrix_max_abs"],
                "positional_effect_m_at_0p76m_lever": float(
                    (theta_m3r_deg - theta_contract_deg) * math.pi / 180.0 * 0.76),
                "disposition": "stored bridge uses the hash-pinned contract matrices; exact-theta synthesis kept "
                               "as witness only (red-team ATK-11 dual-version control)",
            },
            {
                "id": "EXACT_25DEG_REFERENCE_ONLY",
                "spelling": "sin/cos(25.000000 deg) full precision",
                "disposition": "reference witness only, NOT the bridge (red-team ATK-11 dual-version control)",
                "matrix_max_abs_vs_bridge": witnesses["exact_25deg_vs_contract_matrix_max_abs"],
            },
        ],
        "m3r_flange_json_composition_pin": flange_pin,
        "explicitly_not_in_bridge": [
            "M3R as-built datum 210.405 mm (B601_FASTENER_END_PLANE) and its yz pattern offsets "
            "[0.015994151, -0.086366070] mm - GEOMETRY rail only; dynamics entry requires a separate ruling",
            "M3R_TSM_FRAME_TO_FLANGE_TRANSFORM.json - composition convention pinned above; not consumed by this bridge",
            "ADAPTER_PLATE_EXTERNAL_FACE 198.0 mm - stack station, not a mount plane",
            "link-level D_i calibration (B601_CAD_URDF_GEOMETRY_CALIBRATION_V1) - composes with this mount-level "
            "bridge, never substitutes it",
        ],
        "forbidden": [
            "selecting one of the two frames and discarding the other",
            "per-module mixing of the two frames",
            "averaging the frames or their outputs (the 0.36889 deg branch delta is NOT an uncertainty)",
            "treating the branch delta as standard uncertainty (standard_uncertainty remains null)",
            "silent coordinate substitution; any consumer must cite this file and its sha256",
            "using stack-internal station distances (12.75 / 10.0 / 2.405 / 25.155 mm) as bridge translation",
        ],
        "source_register": [
            {"path": E21_AUTHORITY_REL, "sha256": pins[E21_AUTHORITY_REL], "role": "BRIDGE_DERIVATION_AUTHORITY_BOTH_TRANSFORMS"},
            {"path": ODR_REGISTER_REL, "sha256": pins[ODR_REGISTER_REL], "role": "ODR-01_DYNAMICS_FRAME_AUTHORITY"},
            {"path": M4_TREE_REL, "sha256": pins[M4_TREE_REL], "role": "FROZEN_FRAME_TREE_CROSSCHECK"},
            {"path": WP11_CAL_REL, "sha256": pins[WP11_CAL_REL], "role": "WP11_PHYSICAL_MOUNT_CONTEXT_CROSSCHECK"},
            {"path": M3R_STACK_REL, "sha256": pins[M3R_STACK_REL], "role": "CLOCKING_25_000014_MEASURED_SOURCE"},
            {"path": M3R_FLANGE_REL, "sha256": pins[M3R_FLANGE_REL], "role": "COMPOSITION_CONVENTION_PINNED_NOT_IN_BRIDGE"},
            {"path": F3R2_POSE_REL, "sha256": pins[F3R2_POSE_REL], "role": "ROUNDED_SPELLING_PROVENANCE_WP11_F03"},
            {"path": V3_R2_REL, "sha256": pins[V3_R2_REL], "role": "C01_ARM_CG_LEVER_FOR_SPELLING_WITNESS"},
        ],
        "self_hash_policy": "SELF_REFERENCE_EXCLUDED - this file carries no hash of itself; downstream consumers "
                            "pin its sha256 after emission (same policy as e21/V5 manifests)",
        "next_stage_authorized": False,
        "release_credit": False,
        "nonclaims": [
            "this bridge does not select or average the two placement hypotheses; it connects them",
            "this bridge grants no production, manufacturing, qualification, launcher or flight authority",
            "M3R as-built datum usage in dynamics is a separate ruling, not implied here",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(bridge, sort_keys=False, allow_unicode=True, width=200)
    OUT_FILE.write_bytes(text.encode("utf-8"))  # byte-exact: no CRLF translation
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest().upper()
    print("WROTE", OUT_FILE)
    print("sha256:", digest)
    print("theta_contract_deg:", theta_contract_deg)
    print("det_R:", det_R, "orth:", orth, "roundtrip:", roundtrip, "closure:", closure_T)
    print("witnesses:", json.dumps(witnesses, indent=1))
    print("flange z-misplacement mm:", flange_pin["misplacement_z_component_mm"],
          "norm mm:", flange_pin["misplacement_norm_mm"])


if __name__ == "__main__":
    main()
