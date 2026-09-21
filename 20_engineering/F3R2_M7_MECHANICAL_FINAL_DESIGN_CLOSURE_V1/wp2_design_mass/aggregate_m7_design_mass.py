"""M7 WP2 — nine-configuration DESIGN mass/CoM/inertia aggregation with declared uncertainties.

Builds the single M7 DESIGN composition (ODR-01/ODR-02/ODR-05 scope):

    BUS_PRIMARY_STRUCTURE (bus core BUDGETED + legacy flange MATERIAL_DERIVED,
        merged per the ODR-01 scope-note mass-allocation design ruling)
    + solar_array_left + solar_array_right (panel fail = attached-stuck, ODR-02)
    + b601_complete_arm_including_gripper_urdf_links (ACCEPTED_URDF, never overridden)
    + m3r_stage_a_plus_stage_b_budget_envelope (0.7619 kg, ODR-05; ring+plate
        analytic idealization for CoM/inertia, FreeCAD not run in WP2)
    + spacecraft_load_bridge_candidate (M6 candidate, MATERIAL_DERIVED,
        candidate member pending WP1 structure confirmation)
    + target scenario member in C08 (22 kg) / C09 (150 kg) bound to the M5
        display transforms T@[1.24,0,-0.1] / D@[1.61,0,-1.05]

Branch A / Branch B diagnostic semantics converge here into the single DESIGN
composition; the old branch ledgers are kept as references and the mass deltas
are explained exactly (DESIGN - A = M3R + bridge; DESIGN - B = flange + bridge).

Uncertainty model: DESIGN_MASS_UNCERTAINTY_POLICY_V1.yaml (declared Type-B
standard uncertainties by source class, PENDING_CALIBRATION; never measured).
First-order GUM propagation with a numerical central-difference Jacobian
through the full aggregation chain (mass, CoM, rotated tensors + parallel-axis
shift about the configuration system CoM, eigenvalues, eigenvectors).
Principal-axis angular standard uncertainties use first-order eigenvector
perturbation with degeneracy flagging.

Fail-closed rules enforced here:
  * strict SI units (kg, m, kg*m^2, rad);
  * no zero-filled uncertainties; no measured/as-built claims;
  * the accepted URDF arm mass is used as-is and verified by assertion;
  * Q_STOW FK regression failure (567.734 mm) is carried as a retained fact,
    not absorbed by any uncertainty class;
  * target scenarios stay PROVISIONAL scenario anchors;
  * re-runnable: same inputs -> same values (except generated_local).

This script performs no FEA and creates no flight, manufacturing, launch, or
qualification authority. DESIGN level only, pending calibration.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml

WORKSPACE = Path(__file__).resolve().parents[3]
M4 = WORKSPACE / "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1"
M5 = WORKSPACE / "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1"
M6 = WORKSPACE / "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1"
M3 = WORKSPACE / "20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1"
CDR = WORKSPACE / "20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821"
M3TC = WORKSPACE / "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
M7 = WORKSPACE / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
WP2 = M7 / "wp2_design_mass"

V3_PATH = M4 / "03_mass_properties/SYSTEM_MASS_PROPERTIES_V3.yaml"
CONFIG_LIB_PATH = M4 / "03_mass_properties/CONFIGURATION_LIBRARY_V1.yaml"
FRAME_TREE_PATH = M4 / "01_system_architecture/DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml"
REVALIDATION_PATH = M4 / "11_validation/B601_NAMED_POSE_REVALIDATION_V1.json"
M5_CONTRACT_PATH = M5 / "02_configurations/M5_CONFIGURATION_GEOMETRY_CONTRACT_V1.yaml"
TRANSFORM_CANDIDATES_PATH = M6 / "wp2_mass_properties/CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml"
M6_V4_PATH = M6 / "wp2_mass_properties/SYSTEM_MASS_PROPERTIES_V4_DIAGNOSTIC.yaml"
BRIDGE_DATUMS_PATH = M6 / "wp1_load_bridge/LOAD_BRIDGE_DATUMS_V1.yaml"
STAGE_A_TABLE_PATH = M3 / "06_parameterized_parts/m3r/M3R_STAGE_A_PARAMETER_TABLE.yaml"
STAGE_B_TABLE_PATH = M3 / "06_parameterized_parts/m3r/M3R_STAGE_B_PARAMETER_TABLE.yaml"
TSM_STACK_PATH = M3TC / "03_native_cad/M3_interface_authority/M3R_TSM_PHYSICAL_STACK.yaml"
M3R_RULING_PATH = CDR / "03_wp2_mass_interface/M3R_MASS_RULING.json"
CDR_AUTHORITY_PATH = CDR / "03_wp2_mass_interface/SYSTEM_MASS_PROPERTIES_AUTHORITY_V2.yaml"
STAGE1_BUDGET_PATH = WORKSPACE / "20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/mass_inertia_budget_v1.csv"
TARGET_MODELS_PATH = WORKSPACE / "20_engineering/config/geometry/target_models_v1.yaml"
URDF_PATH = WORKSPACE / "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
ODR_PATH = M7 / "00_authority/M7_OWNER_DECISION_REGISTER_V1.yaml"
PLAN_PATH = M7 / "00_authority/M7_EXECUTION_PLAN_V1.md"
POLICY_PATH = WP2 / "DESIGN_MASS_UNCERTAINTY_POLICY_V1.yaml"
OUTPUT_PATH = WP2 / "SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml"

URDF_WITNESS_MASS_KG = 4.695555949342986
M3R_BUDGET_KG = 0.7619
BRIDGE_MASS_KG = 0.702195458
BUS_CORE_KG = 22.927194215348
LEGACY_FLANGE_KG = 0.376019184652

# M3R ring+plate analytic idealization, S frame, metres (geometry basis:
# M3R_STAGE_A/B_PARAMETER_TABLE RevB/RevB2 + M3R_TSM_PHYSICAL_STACK stations).
M3R_STAGE_A_X = (0.202405, 0.210405)       # 208.0-5.595 .. 208.0+2.405 mm
M3R_STAGE_A_R = (0.020, 0.075)             # central passage dia 40 / outer dia 150
M3R_STAGE_B_X = (0.196, 0.208)             # base thickness 12 mm below installation face
M3R_STAGE_B_HALF_W = 0.08                  # 160 mm square
M3R_STAGE_B_BORE_R = 0.050                 # central bore dia 100
M3R_STAGE_B_POCKET_X = (0.202405, 0.208)   # pocket depth 5.595 mm
M3R_STAGE_B_POCKET_R = (0.050, 0.0752)     # pocket dia 100 .. 150.4
M3R_PATTERN_CENTER_YZ_M = np.array([0.000015994, -0.000086366])  # as-built pattern centre, sub-uncertainty

# Load bridge box+hole idealization (LOAD_BRIDGE_DATUMS_V1: x 185.25..196.0 mm,
# 160x160 rounded square clocked 25.000014 deg about +X_S; the 4-fold hole
# pattern and square outline keep the S-frame tensor diagonal under clocking).
BRIDGE_X = (0.18525, 0.196)
BRIDGE_HALF_W = 0.08
BRIDGE_HOLE_R = 0.0033                     # dia 6.6 clearance
BRIDGE_HOLE_OFFSET = 0.07                  # centres (+/-70, +/-70) local
BRIDGE_CENTER_HOLE_R = 0.020               # dia 40 central passage
BRIDGE_CENTER_YZ_M = M3R_PATTERN_CENTER_YZ_M.copy()

NOTIONAL_DENSITY = 2700.0                  # shape-only; masses are normalized to authorities

TENSOR_KEYS = ["Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def now_local() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def load_yaml(path: Path) -> Any:
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def rows_to_transform(rows: list[list[float]]) -> tuple[np.ndarray, np.ndarray]:
    matrix = np.asarray(rows, dtype=float)
    assert matrix.shape == (4, 4), f"expected 4x4 transform rows, got {matrix.shape}"
    rotation = matrix[:3, :3]
    translation = matrix[:3, 3]
    assert np.allclose(matrix[3], [0.0, 0.0, 0.0, 1.0]), "last row must be [0 0 0 1]"
    det = float(np.linalg.det(rotation))
    assert abs(det - 1.0) < 1e-9, f"rotation determinant {det} != 1"
    assert np.allclose(rotation @ rotation.T, np.eye(3), atol=1e-9), "rotation not orthonormal"
    return rotation, translation


def steiner(mass: float, offset: np.ndarray) -> np.ndarray:
    return mass * (float(offset @ offset) * np.eye(3) - np.outer(offset, offset))


# ---------------------------------------------------------------------------
# Analytic primitive library (uniform notional density; shape only).
# Each primitive: (sign, kind, params). kind 'box': (x0,x1,y0,y1,z0,z1);
# kind 'cyl_x': (x0,x1,cy,cz,r0,r1) cylindrical shell about an x-parallel axis.
# ---------------------------------------------------------------------------
def primitive_moments(kind: str, params: tuple) -> tuple[float, np.ndarray, np.ndarray]:
    """Return (volume, first moment vector, inertia about origin) per unit density."""
    if kind == "box":
        x0, x1, y0, y1, z0, z1 = params
        lx, ly, lz = x1 - x0, y1 - y0, z1 - z0
        volume = lx * ly * lz
        centroid = np.array([(x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2])
        first = volume * centroid
        inertia_centroid = volume / 12.0 * np.diag([ly**2 + lz**2, lx**2 + lz**2, lx**2 + ly**2])
        inertia_origin = inertia_centroid + steiner(volume, centroid)
        return volume, first, inertia_origin
    if kind == "cyl_x":
        x0, x1, cy, cz, r0, r1 = params
        length = x1 - x0
        area = np.pi * (r1**2 - r0**2)
        volume = area * length
        centroid = np.array([(x0 + x1) / 2, cy, cz])
        first = volume * centroid
        ixx_c = 0.5 * volume * (r1**2 + r0**2)
        iyy_c = volume * (3.0 * (r1**2 + r0**2) + length**2) / 12.0
        izz_c = iyy_c
        inertia_centroid = np.diag([ixx_c, iyy_c, izz_c])
        inertia_origin = inertia_centroid + steiner(volume, centroid)
        return volume, first, inertia_origin
    raise ValueError(kind)


def composite_properties(primitives: list[tuple[float, str, tuple]]) -> tuple[float, np.ndarray, np.ndarray]:
    """(volume, centroid, inertia about centroid) for a signed primitive set, per unit density."""
    volume = 0.0
    first = np.zeros(3)
    inertia_origin = np.zeros((3, 3))
    for sign, kind, params in primitives:
        v, f, i = primitive_moments(kind, params)
        volume += sign * v
        first += sign * f
        inertia_origin += sign * i
    centroid = first / volume
    inertia_centroid = inertia_origin - steiner(volume, centroid)
    return volume, centroid, 0.5 * (inertia_centroid + inertia_centroid.T)


def m3r_idealization() -> dict[str, Any]:
    stage_a = [(1.0, "cyl_x", (M3R_STAGE_A_X[0], M3R_STAGE_A_X[1], 0.0, 0.0, M3R_STAGE_A_R[0], M3R_STAGE_A_R[1]))]
    stage_b = [
        (1.0, "box", (M3R_STAGE_B_X[0], M3R_STAGE_B_X[1], -M3R_STAGE_B_HALF_W, M3R_STAGE_B_HALF_W, -M3R_STAGE_B_HALF_W, M3R_STAGE_B_HALF_W)),
        (-1.0, "cyl_x", (M3R_STAGE_B_X[0], M3R_STAGE_B_X[1], 0.0, 0.0, 0.0, M3R_STAGE_B_BORE_R)),
        (-1.0, "cyl_x", (M3R_STAGE_B_POCKET_X[0], M3R_STAGE_B_POCKET_X[1], 0.0, 0.0, M3R_STAGE_B_POCKET_R[0], M3R_STAGE_B_POCKET_R[1])),
    ]
    vol_a, _, _ = composite_properties(stage_a)
    vol_b, _, _ = composite_properties(stage_b)
    volume, centroid, inertia = composite_properties(stage_a + stage_b)
    total_mass_shape = volume * NOTIONAL_DENSITY
    scale = M3R_BUDGET_KG / total_mass_shape
    com = centroid.copy()
    com[1:] += M3R_PATTERN_CENTER_YZ_M  # as-built pattern centre offset (sub-uncertainty, documented)
    return {
        "mass_kg": M3R_BUDGET_KG,
        "com_S_m": com,
        "inertia_own_com": inertia * NOTIONAL_DENSITY * scale,
        "idealized_volume_mm3": volume * 1e9,
        "stage_a_idealized_volume_mm3": vol_a * 1e9,
        "stage_b_idealized_volume_mm3": vol_b * 1e9,
        "stage_a_allocated_mass_kg": M3R_BUDGET_KG * vol_a / volume,
        "stage_b_allocated_mass_kg": M3R_BUDGET_KG * vol_b / volume,
        "shape_mass_at_notional_density_kg": total_mass_shape,
        "normalization_scale": scale,
    }


def bridge_idealization() -> dict[str, Any]:
    cy, cz = float(BRIDGE_CENTER_YZ_M[0]), float(BRIDGE_CENTER_YZ_M[1])
    primitives: list[tuple[float, str, tuple]] = [
        (1.0, "box", (BRIDGE_X[0], BRIDGE_X[1], cy - BRIDGE_HALF_W, cy + BRIDGE_HALF_W, cz - BRIDGE_HALF_W, cz + BRIDGE_HALF_W)),
        (-1.0, "cyl_x", (BRIDGE_X[0], BRIDGE_X[1], cy, cz, 0.0, BRIDGE_CENTER_HOLE_R)),
    ]
    for sy in (-1.0, 1.0):
        for sz in (-1.0, 1.0):
            # holes are clocked 25.000014 deg about +X_S with the M3R pattern; the
            # 4-fold symmetric set contributes zero product of inertia either way,
            # so the un-clocked placement is exact for the tensor and centroid.
            primitives.append((-1.0, "cyl_x", (BRIDGE_X[0], BRIDGE_X[1], cy + sy * BRIDGE_HOLE_OFFSET, cz + sz * BRIDGE_HOLE_OFFSET, 0.0, BRIDGE_HOLE_R)))
    volume, centroid, inertia = composite_properties(primitives)
    shape_mass = volume * NOTIONAL_DENSITY
    scale = BRIDGE_MASS_KG / shape_mass
    return {
        "mass_kg": BRIDGE_MASS_KG,
        "com_S_m": centroid,
        "inertia_own_com": inertia * NOTIONAL_DENSITY * scale,
        "idealized_volume_mm3": volume * 1e9,
        "shape_mass_at_notional_density_kg": shape_mass,
        "normalization_scale": scale,
    }


# ---------------------------------------------------------------------------
# Aggregation with numerical uncertainty propagation.
# Member dict: mass_kg, com_S_m, rotation_S, inertia_own_com (local frame),
# plus per-quantity standard uncertainties (u_mass, u_com per axis,
# u_inertia_diag relative, u_inertia_offdiag absolute).
# ---------------------------------------------------------------------------
def rotate_tensor(rotation: np.ndarray, inertia: np.ndarray) -> np.ndarray:
    return rotation @ inertia @ rotation.T


def aggregate_from_theta(members: list[dict[str, Any]], theta: np.ndarray) -> np.ndarray:
    """Outputs: [M, cx, cy, cz, Ixx, Iyy, Izz, Ixy, Ixz, Iyz, lam1, lam2, lam3]."""
    per = 10
    total_mass = 0.0
    weighted = np.zeros(3)
    rotated_tensors = []
    coms = []
    masses = []
    for index, member in enumerate(members):
        block = theta[index * per:(index + 1) * per]
        mass = block[0]
        com = block[1:4]
        inertia_local = np.array([
            [block[4], block[7], block[8]],
            [block[7], block[5], block[9]],
            [block[8], block[9], block[6]],
        ])
        masses.append(mass)
        coms.append(com)
        rotated_tensors.append(rotate_tensor(member["rotation_S"], inertia_local))
        total_mass += mass
        weighted += mass * com
    system_cg = weighted / total_mass
    inertia = np.zeros((3, 3))
    for mass, com, rotated in zip(masses, coms, rotated_tensors):
        inertia += rotated + steiner(mass, com - system_cg)
    inertia = 0.5 * (inertia + inertia.T)
    eigenvalues = np.linalg.eigvalsh(inertia)
    return np.concatenate([
        [total_mass], system_cg,
        [inertia[0, 0], inertia[1, 1], inertia[2, 2], inertia[0, 1], inertia[0, 2], inertia[1, 2]],
        eigenvalues,
    ])


def tensor_from_theta(members: list[dict[str, Any]], theta: np.ndarray) -> np.ndarray:
    out = aggregate_from_theta(members, theta)
    return np.array([
        [out[4], out[7], out[8]],
        [out[7], out[5], out[9]],
        [out[8], out[9], out[6]],
    ])


def propagate(members: list[dict[str, Any]]) -> dict[str, Any]:
    """First-order GUM propagation; returns nominal outputs and standard uncertainties."""
    per = 10
    theta0 = []
    sigma = []
    typical = []
    for member in members:
        inertia_local = member["inertia_own_com"]
        i_scale = float((inertia_local[0, 0] + inertia_local[1, 1] + inertia_local[2, 2]) / 3.0)
        u_diag = member["u_inertia_rel"] * np.array([abs(inertia_local[0, 0]), abs(inertia_local[1, 1]), abs(inertia_local[2, 2])])
        u_off = member["u_inertia_rel"] * i_scale
        theta0.extend([
            member["mass_kg"], *member["com_S_m"],
            inertia_local[0, 0], inertia_local[1, 1], inertia_local[2, 2],
            inertia_local[0, 1], inertia_local[0, 2], inertia_local[1, 2],
        ])
        sigma.extend([member["u_mass"], member["u_com"], member["u_com"], member["u_com"], *u_diag, u_off, u_off, u_off])
        typical.extend([1.0, 0.1, 0.1, 0.1, max(i_scale, 1e-6), max(i_scale, 1e-6), max(i_scale, 1e-6), max(i_scale, 1e-6), max(i_scale, 1e-6), max(i_scale, 1e-6)])
    theta0 = np.asarray(theta0, dtype=float)
    sigma = np.asarray(sigma, dtype=float)
    typical = np.asarray(typical, dtype=float)
    assert np.all(sigma > 0.0), "zero-filled uncertainty is forbidden"

    nominal = aggregate_from_theta(members, theta0)
    n_out = nominal.size
    jacobian = np.zeros((n_out, theta0.size))
    tensor_jacobian = np.zeros((9, theta0.size))
    for j in range(theta0.size):
        step = 1e-6 * max(abs(theta0[j]), typical[j])
        plus = theta0.copy(); plus[j] += step
        minus = theta0.copy(); minus[j] -= step
        jacobian[:, j] = (aggregate_from_theta(members, plus) - aggregate_from_theta(members, minus)) / (2.0 * step)
        tensor_jacobian[:, j] = (
            (tensor_from_theta(members, plus) - tensor_from_theta(members, minus)) / (2.0 * step)
        ).reshape(9)

    variance = (jacobian ** 2) @ (sigma ** 2)
    std = np.sqrt(variance)

    inertia_nominal = tensor_from_theta(members, theta0)
    eigenvalues, eigenvectors = np.linalg.eigh(inertia_nominal)
    # principal-axis angular standard uncertainty via first-order eigenvector perturbation;
    # near-degenerate moment pairs (relative gap < 5%) make the first-order angular
    # uncertainty formally huge and physically meaningless -> flag those axes.
    axis_angular_std = np.zeros(3)
    degeneracy_flags = []
    for k in range(3):
        gaps = [abs(eigenvalues[k] - eigenvalues[i]) for i in range(3) if i != k]
        min_gap = min(gaps)
        scale_ref = max(abs(eigenvalues[k]), 1e-12)
        if min_gap < 5e-2 * scale_ref:
            degeneracy_flags.append(
                f"AXIS_{k}_NEAR_DEGENERATE_RELATIVE_GAP_{min_gap / scale_ref:.4f}_FIRST_ORDER_ANGULAR_UNCERTAINTY_ILL_CONDITIONED"
            )
        acc = 0.0
        for j in range(theta0.size):
            d_a = tensor_jacobian[:, j].reshape(3, 3)
            dv = np.zeros(3)
            for i in range(3):
                if i == k:
                    continue
                gap = eigenvalues[k] - eigenvalues[i]
                if abs(gap) < 1e-12:
                    continue
                dv += (float(eigenvectors[:, i] @ d_a @ eigenvectors[:, k]) / gap) * eigenvectors[:, i]
            acc += float(dv @ dv) * sigma[j] ** 2
        axis_angular_std[k] = np.sqrt(acc)

    return {
        "nominal": nominal,
        "std": std,
        "inertia_matrix": inertia_nominal,
        "inertia_std_matrix": np.array([
            [std[4], std[7], std[8]],
            [std[7], std[5], std[9]],
            [std[8], std[9], std[6]],
        ]),
        "eigenvalues": eigenvalues,
        "eigenvectors": eigenvectors,
        "eigenvalue_std": std[10:13],
        "axis_angular_std_rad": axis_angular_std,
        "degeneracy_flags": degeneracy_flags,
    }


def main() -> None:
    v3 = load_yaml(V3_PATH)
    config_lib = load_yaml(CONFIG_LIB_PATH)
    revalidation = json.loads(REVALIDATION_PATH.read_text(encoding="utf-8"))
    m5_contract = load_yaml(M5_CONTRACT_PATH)
    candidates = load_yaml(TRANSFORM_CANDIDATES_PATH)
    m6_v4 = load_yaml(M6_V4_PATH)
    bridge_datums = load_yaml(BRIDGE_DATUMS_PATH)
    m3r_ruling = json.loads(M3R_RULING_PATH.read_text(encoding="utf-8"))
    policy = load_yaml(POLICY_PATH)

    with open(STAGE1_BUDGET_PATH, encoding="utf-8") as handle:
        header = handle.readline().strip().split(",")
        stage1_rows = {}
        for line in handle:
            values = line.strip().split(",")
            stage1_rows[values[0]] = dict(zip(header, values))

    classes = {entry["class_id"]: entry for entry in policy["source_classes"]}

    def class_mass_u(class_id: str, mass: float) -> float:
        return float(classes[class_id]["mass_relative_standard_uncertainty"]) * mass

    def class_com_u(class_id: str) -> float:
        return float(classes[class_id]["com_absolute_standard_uncertainty_m_per_axis"])

    def class_inertia_u(class_id: str) -> float:
        return float(classes[class_id]["inertia_relative_standard_uncertainty"])

    # --- authority assertions (fail-closed) ---
    records = v3["component_records"]
    arm_record = records["b601_complete_arm_including_gripper_urdf_links"]
    arm_mass = float(arm_record["mass"]["estimate_kg"])
    assert abs(arm_mass - URDF_WITNESS_MASS_KG) < 1e-12, "L0 URDF arm mass mismatch"
    assert abs(float(m3r_ruling["active_digital_authority"]["value_kg"]) - M3R_BUDGET_KG) < 1e-15
    bridge_candidate = bridge_datums["material_derived_mass_candidate"]
    assert abs(float(bridge_candidate["mass_kg"]) - BRIDGE_MASS_KG) < 1e-12, "bridge contract mass mismatch"

    bus = records["spacecraft_bus_no_panels"]
    panel_left = records["solar_array_left"]
    panel_right = records["solar_array_right"]
    target_22 = records["target_22kg_scenario"]
    target_150 = records["target_150kg_scenario"]
    assert abs(float(bus["mass"]["estimate_kg"]) - (BUS_CORE_KG + LEGACY_FLANGE_KG)) < 1e-12

    m3r = m3r_idealization()
    bridge = bridge_idealization()
    assert M3R_STAGE_B_X[0] - 1e-12 <= m3r["com_S_m"][0] <= M3R_STAGE_A_X[1] + 1e-12
    # idealization cross-check vs independent STEP B-rep volumes (parameter tables)
    brep_a = 127784.800333
    brep_b = 161966.032228
    idealization_check = {
        "stage_a_idealized_vs_brep_volume_ratio": m3r["stage_a_idealized_volume_mm3"] / brep_a,
        "stage_b_idealized_vs_brep_volume_ratio": m3r["stage_b_idealized_volume_mm3"] / brep_b,
        "bridge_idealized_vs_freecad_volume_ratio": bridge["idealized_volume_mm3"] / float(bridge_candidate["volume_mm3"]),
    }

    # --- component builders ---
    def bus_member() -> dict[str, Any]:
        u_mass = float(np.hypot(
            class_mass_u("BUDGETED", BUS_CORE_KG),
            class_mass_u("MATERIAL_DERIVED", LEGACY_FLANGE_KG),
        ))
        return {
            "component_id": "bus_primary_structure",
            "mass_kg": float(bus["mass"]["estimate_kg"]),
            "mass_class": "MERGED_RSS(bus_core: BUDGETED, legacy_flange: MATERIAL_DERIVED)",
            "u_mass": u_mass,
            "com_S_m": np.asarray(bus["center_of_mass"]["estimate_xyz_m"], dtype=float),
            "com_class": "BUDGETED",
            "u_com": class_com_u("BUDGETED"),
            "rotation_S": np.eye(3),
            "inertia_own_com": np.asarray(bus["inertia_about_own_com"]["matrix_kg_m2"], dtype=float),
            "inertia_class": "BUDGETED",
            "u_inertia_rel": class_inertia_u("BUDGETED"),
            "inertia_reference_frame": "S",
            "transform_classification": "NOT_REQUIRED_ALREADY_IN_S",
            "source_ref": "m4_system_mass_properties_v3",
            "pedigree_note": "M4 bus record = bus core 22.927194215348 kg (BUDGETED block-model recomposition) + legacy flange 0.376019184652 kg (MATERIAL_DERIVED), merged into BUS_PRIMARY_STRUCTURE per ODR-01 scope-note design ruling",
        }

    panel_transforms = candidates["transform_library"]["panel_transforms"]

    def panel_member(side: str, transform_key: str) -> dict[str, Any]:
        record = panel_left if side == "left" else panel_right
        rotation, translation = rows_to_transform(panel_transforms[transform_key]["T_S_child_rows"])
        return {
            "component_id": f"solar_array_{side}",
            "mass_kg": float(record["mass"]["estimate_kg"]),
            "mass_class": "BUDGETED",
            "u_mass": class_mass_u("BUDGETED", float(record["mass"]["estimate_kg"])),
            "com_S_m": translation,
            "com_class": "ANALYTIC_IDEALIZATION",
            "u_com": class_com_u("ANALYTIC_IDEALIZATION"),
            "rotation_S": rotation,
            "inertia_own_com": np.asarray(record["inertia_about_own_com"]["matrix_kg_m2"], dtype=float),
            "inertia_class": "ANALYTIC_IDEALIZATION",
            "u_inertia_rel": class_inertia_u("ANALYTIC_IDEALIZATION"),
            "inertia_reference_frame": f"F_{side.upper()}_LOCAL_COM",
            "transform_classification": "DESIGN_BINDING_FROM_M6_CANDIDATE",
            "transform_ref": f"CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml#transform_library.panel_transforms.{transform_key}",
            "source_ref": "stage1_mass_budget",
            "pedigree_note": "thin-plate spec (0.227x0.200x0.006 m) under the bound M6 candidate transform; physical hinge kinematics ratification remains open",
        }

    pose_props = {
        "Q_DEPLOYED_HOME": revalidation["pose_results"]["Q_DEPLOYED_HOME"],
        "Q_DEPLOYED_HOME_DISPLAY_ONLY_FOR_FAILURE_BRANCH": revalidation["pose_results"]["Q_DEPLOYED_HOME"],
        "Q_STOW_ENGINEERING_CANDIDATE": revalidation["pose_results"]["Q_STOW_ENGINEERING_CANDIDATE"],
        "Q_SERVICE_READY": revalidation["pose_results"]["Q_SERVICE_READY"],
        "PREGRASP_SCENE_CANDIDATE": revalidation["pregrasp_scene_candidate"],
    }
    pose_status_map = {
        "Q_DEPLOYED_HOME": "PASS_RUNTIME_FK_AND_INERTIA_NO_SOURCE_HOLD",
        "Q_DEPLOYED_HOME_DISPLAY_ONLY_FOR_FAILURE_BRANCH": "PASS_RUNTIME_FK_AND_INERTIA_NO_SOURCE_HOLD_DISPLAY_ONLY_BINDING",
        "Q_STOW_ENGINEERING_CANDIDATE": "HELD_CANDIDATE_FK_REGRESSION_FAIL_MAX_RESIDUAL_567P734_MM_RETAINED_FACT_NOT_ABSORBED_BY_UNCERTAINTY",
        "Q_SERVICE_READY": "PASS_RUNTIME_FK_AND_INERTIA_WITH_SOURCE_CONFIGURATION_RATIFICATION_HOLD",
        "PREGRASP_SCENE_CANDIDATE": "DIAGNOSTIC_CANDIDATE_HOLD_FOR_CAPTURE_DYNAMICS",
    }

    def arm_member(pose_ref: str) -> dict[str, Any]:
        props = pose_props[pose_ref]
        return {
            "component_id": "b601_complete_arm_including_gripper_urdf_links",
            "mass_kg": arm_mass,
            "mass_class": "ACCEPTED_URDF",
            "u_mass": class_mass_u("ACCEPTED_URDF", arm_mass),
            "com_S_m": np.asarray(props["digital_arm_center_of_mass_S_m"], dtype=float),
            "com_class": "ACCEPTED_URDF",
            "u_com": class_com_u("ACCEPTED_URDF"),
            "rotation_S": np.eye(3),  # revalidation values are already expressed in S
            "inertia_own_com": np.asarray(props["digital_arm_inertia_about_arm_com_S_kg_m2"], dtype=float),
            "inertia_class": "ACCEPTED_URDF",
            "u_inertia_rel": class_inertia_u("ACCEPTED_URDF"),
            "inertia_reference_frame": "S",
            "transform_classification": "DESIGN_BINDING_OF_NAMED_POSE_DIGITAL_PROPERTIES",
            "transform_ref": f"CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml#transform_library.arm_named_pose_bindings.{pose_ref}",
            "pose_status": pose_status_map[pose_ref],
            "source_ref": "b601_named_pose_revalidation",
            "pedigree_note": "URDF link inertials + joint FK, rigid combination by parallel-axis theorem (M4 revalidation); L0 mass never overridden",
        }

    def m3r_member() -> dict[str, Any]:
        return {
            "component_id": "m3r_stage_a_plus_stage_b_budget_envelope",
            "mass_kg": M3R_BUDGET_KG,
            "mass_class": "BUDGETED",
            "u_mass": class_mass_u("BUDGETED", M3R_BUDGET_KG),
            "com_S_m": m3r["com_S_m"],
            "com_class": "ANALYTIC_IDEALIZATION",
            "u_com": class_com_u("ANALYTIC_IDEALIZATION"),
            "rotation_S": np.eye(3),
            "inertia_own_com": m3r["inertia_own_com"],
            "inertia_class": "ANALYTIC_IDEALIZATION",
            "u_inertia_rel": class_inertia_u("ANALYTIC_IDEALIZATION"),
            "inertia_reference_frame": "S",
            "transform_classification": "NOT_REQUIRED_PLACED_BY_STATION_STACK",
            "source_ref": "m3r_mass_ruling",
            "pedigree_note": (
                "ODR-05 budget 0.7619 kg (DESIGN_BUDGET, confidence B); CoM/inertia from ring+plate analytic "
                "idealization (Stage A shell dia 150/40 x 8 mm at x 202.405..210.405 mm; Stage B 160x160x12 mm plate, "
                "dia 100 bore, dia 150.4/100 x 5.595 mm pocket at x 196..208 mm), normalized to the budget; stage split "
                f"proportional to idealized volumes (A {m3r['stage_a_allocated_mass_kg']:.6f} kg / B {m3r['stage_b_allocated_mass_kg']:.6f} kg), "
                "stage allocation itself PENDING owner allocation; excludes fasteners/locator/harness/mating structure"
            ),
        }

    def bridge_member() -> dict[str, Any]:
        return {
            "component_id": "spacecraft_load_bridge_candidate",
            "mass_kg": BRIDGE_MASS_KG,
            "mass_class": "MATERIAL_DERIVED",
            "u_mass": class_mass_u("MATERIAL_DERIVED", BRIDGE_MASS_KG),
            "com_S_m": bridge["com_S_m"],
            "com_class": "ANALYTIC_IDEALIZATION",
            "u_com": class_com_u("ANALYTIC_IDEALIZATION"),
            "rotation_S": np.eye(3),
            "inertia_own_com": bridge["inertia_own_com"],
            "inertia_class": "ANALYTIC_IDEALIZATION",
            "u_inertia_rel": class_inertia_u("ANALYTIC_IDEALIZATION"),
            "inertia_reference_frame": "S",
            "transform_classification": "NOT_REQUIRED_PLACED_BY_STATION_STACK",
            "source_ref": "m6_load_bridge_datums",
            "membership_status": "CANDIDATE_MEMBER_AWAITING_WP1_STRUCTURE_CONFIRMATION",
            "pedigree_note": (
                "M6 candidate plate 160x160x10.75 mm at x 185.25..196.0 mm, 4x dia 6.6 at (+/-70,+/-70), dia 40 centre, "
                "candidate mass 702.195458 g (MATERIAL_DERIVED, 6061-T6 2700 kg/m3); clocked 25.000014 deg about +X_S "
                "(tensor invariant under the 4-fold pattern); excluded from the M3R budget (mating spacecraft structure)"
            ),
        }

    target_poses = candidates["transform_library"]["target_capture_pose_candidates"]
    bindings = {item["configuration_id"]: item for item in candidates["configuration_bindings"]}
    m5_records = {item["configuration_id"]: item for item in m5_contract["records"]}
    lib_records = {item["configuration_id"]: item for item in config_lib["configurations"]}
    m6_v4_records = {item["configuration_id"]: item for item in m6_v4["configurations"]}

    def target_member(config_id: str) -> dict[str, Any] | None:
        binding = bindings[config_id]["target"]
        if binding is None or not binding["system_mass_member"]:
            return None
        pose = target_poses[binding["pose_ref"]]
        rotation, translation = rows_to_transform(pose["T_S_target_rows"])
        record = target_22 if config_id == "C08" else target_150
        com_local = np.asarray(record["center_of_mass"]["estimate_xyz_m"], dtype=float)
        mass = float(record["mass"]["estimate_kg"])
        return {
            "component_id": "target_22kg_scenario" if config_id == "C08" else "target_150kg_scenario",
            "mass_kg": mass,
            "mass_class": "PROVISIONAL",
            "u_mass": class_mass_u("PROVISIONAL", mass),
            "com_S_m": rotation @ com_local + translation,
            "com_class": "PROVISIONAL",
            "u_com": class_com_u("PROVISIONAL"),
            "rotation_S": rotation,
            "inertia_own_com": np.asarray(record["inertia_about_own_com"]["matrix_kg_m2"], dtype=float),
            "inertia_class": "PROVISIONAL",
            "u_inertia_rel": class_inertia_u("PROVISIONAL"),
            "inertia_reference_frame": "T" if config_id == "C08" else "D",
            "transform_classification": "DESIGN_BINDING_FROM_M5_DISPLAY_TRANSFORM_UNRATIFIED",
            "transform_ref": f"CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml#transform_library.target_capture_pose_candidates.{binding['pose_ref']}",
            "source_ref": "stage1_mass_budget",
            "pedigree_note": "scenario anchor, never measured (RA-003); rigidly retained after capture is a scenario assumption",
        }

    # --- per-configuration aggregation ---
    configurations_out = []
    checks = {
        "branch_mass_delta_constant": [],
        "stripped_composition_rebuilds_m6_v4_branch_A": [],
        "target_transform_matches_m5_contract": [],
        "inertia_symmetric_positive_definite": [],
        "uncertainty_positive_no_zero_fill": [],
    }

    for config_id in [f"C{index:02d}" for index in range(1, 10)]:
        binding = bindings[config_id]
        lib = lib_records[config_id]
        m5_record = m5_records[config_id]

        members = [
            bus_member(),
            panel_member("left", binding["solar_panel_transforms"]["left"]["transform_ref"]),
            panel_member("right", binding["solar_panel_transforms"]["right"]["transform_ref"]),
            arm_member(binding["arm_named_pose_binding"]["pose_ref"]),
            m3r_member(),
            bridge_member(),
        ]
        target = target_member(config_id)
        if target is not None:
            members.append(target)

        result = propagate(members)
        nominal, std = result["nominal"], result["std"]
        design_mass = float(nominal[0])

        # --- regression: M4 branch references and M6 V4 Branch A rebuild ---
        expected_a = float(lib["mass"]["diagnostic_branches"]["legacy_A_value_kg"])
        expected_b = float(lib["mass"]["diagnostic_branches"]["m3r_B_value_kg"])
        delta_a = design_mass - expected_a
        delta_b = design_mass - expected_b
        checks["branch_mass_delta_constant"].append({
            "configuration_id": config_id,
            "design_mass_kg": design_mass,
            "legacy_A_reference_kg": expected_a,
            "m3r_B_reference_kg": expected_b,
            "design_minus_legacy_A_kg": delta_a,
            "design_minus_m3r_B_kg": delta_b,
            "expected_delta_A_kg": M3R_BUDGET_KG + BRIDGE_MASS_KG,
            "expected_delta_B_kg": LEGACY_FLANGE_KG + BRIDGE_MASS_KG,
            "pass": abs(delta_a - (M3R_BUDGET_KG + BRIDGE_MASS_KG)) < 1e-12
                    and abs(delta_b - (LEGACY_FLANGE_KG + BRIDGE_MASS_KG)) < 1e-12,
        })

        # stripped composition (drop M3R + bridge) must rebuild the M6 V4 Branch A diagnostic exactly
        stripped = [m for m in members if m["component_id"] not in
                    ("m3r_stage_a_plus_stage_b_budget_envelope", "spacecraft_load_bridge_candidate")]
        stripped_theta = []
        for member in stripped:
            il = member["inertia_own_com"]
            stripped_theta.extend([member["mass_kg"], *member["com_S_m"], il[0, 0], il[1, 1], il[2, 2], il[0, 1], il[0, 2], il[1, 2]])
        stripped_out = aggregate_from_theta(stripped, np.asarray(stripped_theta))
        v4_record = m6_v4_records[config_id]
        v4_cg = np.asarray(v4_record["cg"]["diagnostic_branch_A_xyz_m"], dtype=float)
        v4_inertia = np.asarray(v4_record["inertia"]["diagnostic_branch_A_matrix_kg_m2"], dtype=float)
        stripped_inertia = np.array([
            [stripped_out[4], stripped_out[7], stripped_out[8]],
            [stripped_out[7], stripped_out[5], stripped_out[9]],
            [stripped_out[8], stripped_out[9], stripped_out[6]],
        ])
        checks["stripped_composition_rebuilds_m6_v4_branch_A"].append({
            "configuration_id": config_id,
            "mass_abs_err_kg": abs(float(stripped_out[0]) - expected_a),
            "cg_max_abs_err_m": float(np.max(np.abs(stripped_out[1:4] - v4_cg))),
            "inertia_max_abs_err_kg_m2": float(np.max(np.abs(stripped_inertia - v4_inertia))),
            "pass": abs(float(stripped_out[0]) - expected_a) < 1e-12
                    and float(np.max(np.abs(stripped_out[1:4] - v4_cg))) < 1e-9
                    and float(np.max(np.abs(stripped_inertia - v4_inertia))) < 1e-9,
        })

        if binding["target"] is not None:
            m5_rows = np.asarray(m5_record["target_transform_S_rows"], dtype=float)
            cand_rows = np.asarray(target_poses[binding["target"]["pose_ref"]]["T_S_target_rows"], dtype=float)
            checks["target_transform_matches_m5_contract"].append({
                "configuration_id": config_id,
                "max_abs_err_m": float(np.max(np.abs(m5_rows - cand_rows))),
                "pass": bool(np.allclose(m5_rows, cand_rows, atol=1e-12)),
            })

        inertia_matrix = result["inertia_matrix"]
        checks["inertia_symmetric_positive_definite"].append({
            "configuration_id": config_id,
            "min_eigenvalue_kg_m2": float(result["eigenvalues"].min()),
            "symmetric": bool(np.allclose(inertia_matrix, inertia_matrix.T, atol=1e-15)),
            "pass": bool(np.allclose(inertia_matrix, inertia_matrix.T, atol=1e-15) and result["eigenvalues"].min() > 0.0),
        })
        checks["uncertainty_positive_no_zero_fill"].append({
            "configuration_id": config_id,
            "min_standard_uncertainty": float(std.min()),
            "pass": bool(np.all(std > 0.0)),
        })

        components_out = []
        for member in members:
            il = member["inertia_own_com"]
            i_scale = float((il[0, 0] + il[1, 1] + il[2, 2]) / 3.0)
            u_off = member["u_inertia_rel"] * i_scale
            inertia_std_local = np.array([
                [member["u_inertia_rel"] * abs(il[0, 0]), u_off, u_off],
                [u_off, member["u_inertia_rel"] * abs(il[1, 1]), u_off],
                [u_off, u_off, member["u_inertia_rel"] * abs(il[2, 2])],
            ])
            component_out = {
                "component_id": member["component_id"],
                "mass_kg": member["mass_kg"],
                "mass_class": member["mass_class"],
                "mass_standard_uncertainty_kg": member["u_mass"],
                "com_S_m": [float(v) for v in member["com_S_m"]],
                "com_class": member["com_class"],
                "com_standard_uncertainty_m_per_axis": member["u_com"],
                "inertia_about_own_com_S_kg_m2": [[float(v) for v in row] for row in rotate_tensor(member["rotation_S"], il)],
                "inertia_class": member["inertia_class"],
                "inertia_standard_uncertainty_S_kg_m2": [[float(v) for v in row] for row in rotate_tensor(member["rotation_S"], inertia_std_local)],
                "inertia_reference_frame_declared": member["inertia_reference_frame"],
                "transform_classification": member["transform_classification"],
                "membership_status": member.get("membership_status", "DESIGN_MEMBER"),
                "source_ref": member["source_ref"],
                "pedigree_note": member["pedigree_note"],
            }
            # optional metadata keys are omitted when absent (no null padding)
            if member.get("transform_ref") is not None:
                component_out["transform_ref"] = member["transform_ref"]
            if member.get("pose_status") is not None:
                component_out["pose_status"] = member["pose_status"]
            components_out.append(component_out)

        eigenvectors = result["eigenvectors"]
        principal_axes = [[float(eigenvectors[row, col]) for row in range(3)] for col in range(3)]
        configurations_out.append({
            "configuration_id": config_id,
            "name": lib["name"],
            "legacy_mapping": lib["legacy_mapping"],
            "configuration_semantics": {
                "panel_failure_rule": "ODR-02_ATTACHED_STUCK_NEVER_JETTISON",
                "arm_pose_ref": binding["arm_named_pose_binding"]["pose_ref"],
                "target_membership": None if target is None else {
                    "pose_ref": binding["target"]["pose_ref"],
                    "system_mass_member": binding["target"]["system_mass_member"],
                    "scenario_mass_kg": binding["target"].get("scenario_mass_kg"),
                },
            },
            "composition": components_out,
            "mass": {
                "value_kg": design_mass,
                "standard_uncertainty_kg": float(std[0]),
                "relative_standard_uncertainty": float(std[0] / design_mass),
                "status": "DESIGN_DECLARED_UNCERTAINTY_PENDING_CALIBRATION_NOT_MEASURED",
            },
            "center_of_mass": {
                "reference_frame": "spacecraft_assembly_frame",
                "reference_frame_resolution": "frozen identity alias of S (M4 frame tree)",
                "xyz_m": [float(v) for v in nominal[1:4]],
                "standard_uncertainty_xyz_m": [float(v) for v in std[1:4]],
                "status": "DESIGN_DECLARED_UNCERTAINTY_PENDING_CALIBRATION_NOT_MEASURED",
            },
            "inertia": {
                "reference_frame": "spacecraft_assembly_frame",
                "reference_point": "configuration_system_CG",
                "matrix_kg_m2": [[float(v) for v in row] for row in inertia_matrix],
                "components_kg_m2": {key: float(value) for key, value in zip(TENSOR_KEYS, nominal[4:10])},
                "standard_uncertainty_matrix_kg_m2": [[float(v) for v in row] for row in result["inertia_std_matrix"]],
                "standard_uncertainty_components_kg_m2": {key: float(value) for key, value in zip(TENSOR_KEYS, std[4:10])},
                "status": "DESIGN_DECLARED_UNCERTAINTY_PENDING_CALIBRATION_NOT_MEASURED",
            },
            "principal_inertia": {
                "moments_kg_m2": [float(v) for v in result["eigenvalues"]],
                "moment_standard_uncertainties_kg_m2": [float(v) for v in result["eigenvalue_std"]],
                "axes_S_unit_vectors": principal_axes,
                "axes_order": "ascending moments; each axis listed as [x,y,z] in S",
                "axis_angular_standard_uncertainty_rad": [float(v) for v in result["axis_angular_std_rad"]],
                "degeneracy_flags": result["degeneracy_flags"],
                "status": "DESIGN_DECLARED_UNCERTAINTY_PENDING_CALIBRATION_NOT_MEASURED",
            },
            "branch_reconciliation": {
                "legacy_A_reference_kg": expected_a,
                "m3r_B_reference_kg": expected_b,
                "design_minus_legacy_A_kg": float(delta_a),
                "design_minus_m3r_B_kg": float(delta_b),
                "explanation": "DESIGN = legacy_A + M3R 0.7619 kg + load bridge 0.702195458 kg = m3r_B + legacy flange 0.376019184652 kg + load bridge 0.702195458 kg (exact constant per configuration)",
                "old_branch_references_retained": ["M4-DIAG-LEGACY-A", "M4-DIAG-M3R-B"],
            },
            "status": "DESIGN_MODEL_VALUES_WITH_DECLARED_UNCERTAINTY_NOT_MEASURED_NOT_FLIGHT_QUALIFIED",
        })

    # --- whole-sat closure check (bus + 2 deployed panels rebuild servicer_12U_v0) ---
    whole = stage1_rows["servicer_12U_v0"]
    closure_members = [bus_member(), panel_member("left", "panel_left_deployed"), panel_member("right", "panel_right_deployed")]
    closure_theta = []
    for member in closure_members:
        il = member["inertia_own_com"]
        closure_theta.extend([member["mass_kg"], *member["com_S_m"], il[0, 0], il[1, 1], il[2, 2], il[0, 1], il[0, 2], il[1, 2]])
    closure_out = aggregate_from_theta(closure_members, np.asarray(closure_theta))
    closure_inertia = np.array([
        [closure_out[4], closure_out[7], closure_out[8]],
        [closure_out[7], closure_out[5], closure_out[9]],
        [closure_out[8], closure_out[9], closure_out[6]],
    ])
    whole_cg = np.array([float(whole["cg_x_m"]), float(whole["cg_y_m"]), float(whole["cg_z_m"])])
    whole_inertia = np.array([
        [float(whole["Ixx_kgm2"]), float(whole["Ixy_kgm2"]), float(whole["Ixz_kgm2"])],
        [float(whole["Ixy_kgm2"]), float(whole["Iyy_kgm2"]), float(whole["Iyz_kgm2"])],
        [float(whole["Ixz_kgm2"]), float(whole["Iyz_kgm2"]), float(whole["Izz_kgm2"])],
    ])
    closure_check = {
        "reference_row": "servicer_12U_v0 (stage1 mass_inertia_budget_v1.csv, CSV 7-decimal rounding)",
        "mass_abs_err_kg": abs(float(closure_out[0]) - float(whole["mass_kg"])),
        "cg_max_abs_err_m": float(np.max(np.abs(closure_out[1:4] - whole_cg))),
        "inertia_max_abs_err_kg_m2": float(np.max(np.abs(closure_inertia - whole_inertia))),
        "tolerances": {"mass_kg": 1e-9, "cg_m": 5e-6, "inertia_kg_m2": 5e-6},
    }
    closure_check["pass"] = (
        closure_check["mass_abs_err_kg"] < 1e-9
        and closure_check["cg_max_abs_err_m"] < 5e-6
        and closure_check["inertia_max_abs_err_kg_m2"] < 5e-6
    )

    def flatten_pass(items: list[dict[str, Any]]) -> bool:
        return all(item["pass"] for item in items)

    design_checks = {
        "urdf_arm_mass_pinned_exactly": abs(arm_mass - URDF_WITNESS_MASS_KG) < 1e-12,
        "m3r_budget_normalized_exactly_kg": M3R_BUDGET_KG,
        "bridge_candidate_mass_kg": BRIDGE_MASS_KG,
        "idealization_volume_crosscheck_vs_brep": idealization_check,
        "branch_mass_delta_constant_9_of_9": {
            "pass": flatten_pass(checks["branch_mass_delta_constant"]),
            "detail": checks["branch_mass_delta_constant"],
        },
        "stripped_composition_rebuilds_m6_v4_branch_A_9_of_9": {
            "pass": flatten_pass(checks["stripped_composition_rebuilds_m6_v4_branch_A"]),
            "detail": checks["stripped_composition_rebuilds_m6_v4_branch_A"],
        },
        "target_capture_transforms_match_m5_display_rows": {
            "pass": flatten_pass(checks["target_transform_matches_m5_contract"]),
            "detail": checks["target_transform_matches_m5_contract"],
        },
        "inertia_symmetric_positive_definite_9_of_9": {
            "pass": flatten_pass(checks["inertia_symmetric_positive_definite"]),
            "detail": checks["inertia_symmetric_positive_definite"],
        },
        "uncertainty_positive_no_zero_fill_9_of_9": {
            "pass": flatten_pass(checks["uncertainty_positive_no_zero_fill"]),
            "detail": checks["uncertainty_positive_no_zero_fill"],
        },
        "deployed_panels_whole_sat_closure_vs_stage1_row": closure_check,
    }
    all_pass = all([
        design_checks["urdf_arm_mass_pinned_exactly"],
        design_checks["branch_mass_delta_constant_9_of_9"]["pass"],
        design_checks["stripped_composition_rebuilds_m6_v4_branch_A_9_of_9"]["pass"],
        design_checks["target_capture_transforms_match_m5_display_rows"]["pass"],
        design_checks["inertia_symmetric_positive_definite_9_of_9"]["pass"],
        design_checks["uncertainty_positive_no_zero_fill_9_of_9"]["pass"],
        closure_check["pass"],
    ])

    def rel(path: Path) -> str:
        return path.relative_to(WORKSPACE).as_posix()

    source_register = {
        "m7_owner_decision_register": {"path": rel(ODR_PATH), "sha256": sha256(ODR_PATH)},
        "m7_execution_plan": {"path": rel(PLAN_PATH), "sha256": sha256(PLAN_PATH)},
        "m7_design_mass_uncertainty_policy": {"path": rel(POLICY_PATH), "sha256": sha256(POLICY_PATH)},
        "m4_system_mass_properties_v3": {"path": rel(V3_PATH), "sha256": sha256(V3_PATH)},
        "m4_configuration_library_v1": {"path": rel(CONFIG_LIB_PATH), "sha256": sha256(CONFIG_LIB_PATH)},
        "m4_frame_tree": {"path": rel(FRAME_TREE_PATH), "sha256": sha256(FRAME_TREE_PATH)},
        "b601_named_pose_revalidation": {"path": rel(REVALIDATION_PATH), "sha256": sha256(REVALIDATION_PATH)},
        "m5_configuration_geometry_contract": {"path": rel(M5_CONTRACT_PATH), "sha256": sha256(M5_CONTRACT_PATH)},
        "m6_configuration_transform_candidates": {"path": rel(TRANSFORM_CANDIDATES_PATH), "sha256": sha256(TRANSFORM_CANDIDATES_PATH)},
        "m6_system_mass_properties_v4_diagnostic": {"path": rel(M6_V4_PATH), "sha256": sha256(M6_V4_PATH)},
        "m6_load_bridge_datums": {"path": rel(BRIDGE_DATUMS_PATH), "sha256": sha256(BRIDGE_DATUMS_PATH)},
        "m3r_stage_a_parameter_table": {"path": rel(STAGE_A_TABLE_PATH), "sha256": sha256(STAGE_A_TABLE_PATH)},
        "m3r_stage_b_parameter_table": {"path": rel(STAGE_B_TABLE_PATH), "sha256": sha256(STAGE_B_TABLE_PATH)},
        "m3r_tsm_physical_stack": {"path": rel(TSM_STACK_PATH), "sha256": sha256(TSM_STACK_PATH)},
        "m3r_mass_ruling": {"path": rel(M3R_RULING_PATH), "sha256": sha256(M3R_RULING_PATH)},
        "cdr_system_mass_properties_authority_v2": {"path": rel(CDR_AUTHORITY_PATH), "sha256": sha256(CDR_AUTHORITY_PATH)},
        "stage1_mass_budget": {"path": rel(STAGE1_BUDGET_PATH), "sha256": sha256(STAGE1_BUDGET_PATH)},
        "target_models_ssot": {"path": rel(TARGET_MODELS_PATH), "sha256": sha256(TARGET_MODELS_PATH)},
        "accepted_b601_urdf_L0_witness": {"path": rel(URDF_PATH), "sha256": sha256(URDF_PATH)},
    }

    output = {
        "schema": "M7_SYSTEM_DESIGN_MASS_PROPERTIES_V1",
        "generated_local": now_local(),
        "phase": "M7_MECHANICAL_FINAL_DESIGN_CLOSURE",
        "work_package": "WP2_DESIGN_MASS",
        "scope": "NINE_CONFIGURATION_DESIGN_MASS_COM_INERTIA_MODEL_WITH_DECLARED_UNCERTAINTIES",
        "status": "DESIGN_MASS_MODEL_ACTIVE_DECLARED_UNCERTAINTY_PENDING_CALIBRATION",
        "design_not_flight_qualified": True,
        "units": {"mass": "kg", "center_of_mass": "m", "inertia": "kg*m^2", "angle": "rad"},
        "authority_basis": {
            "ODR-01": "M frame authority T_SM=[185.25,0,0] mm + Ry(90 deg); legacy flange allocated to BUS_PRIMARY_STRUCTURE by design ruling",
            "ODR-02": "panel failure = attached-stuck, never jettison (C02/C03/C04 keep panel mass at the stowed endpoint)",
            "ODR-05": "M3R 0.7619 kg design-budget authority (DESIGN_BUDGET, confidence B); as-built measurement open",
            "contract": "M7_EXECUTION_PLAN_V1.md pinned contract values",
        },
        "composition_ruling": {
            "single_design_composition": [
                "bus_primary_structure (= M4 bus_no_panels record: bus core 22.927194215348 kg + legacy flange 0.376019184652 kg merged with declared uncertainty)",
                "solar_array_left (0.3483933 kg, state transform per configuration)",
                "solar_array_right (0.3483933 kg, state transform per configuration)",
                "b601_complete_arm_including_gripper_urdf_links (4.695555949342986 kg, ACCEPTED_URDF, named-pose digital properties)",
                "m3r_stage_a_plus_stage_b_budget_envelope (0.7619 kg, ODR-05, ring+plate analytic idealization)",
                "spacecraft_load_bridge_candidate (0.702195458 kg, MATERIAL_DERIVED, candidate member pending WP1 structure confirmation)",
                "target scenario member in C08/C09 only (PROVISIONAL, M5 display transform binding)",
            ],
            "branch_convergence": "M4 Branch A / Branch B dual diagnostic semantics converge into this single DESIGN composition; old branch ledgers retained as references under branch_reconciliation per configuration",
            "design_mass_uncaptured_without_bridge_kg": 29.457455949342986,
            "design_mass_uncaptured_with_bridge_kg": 30.159651407342986,
        },
        "aggregation_contract": {
            "target_frame": "spacecraft_assembly_frame (frozen identity alias of S, M4 frame tree)",
            "mass_model": "m_system = sum(m_i) over the declared non-overlapping member set",
            "center_of_mass_model": "r_system = sum(m_i*r_i)/sum(m_i)",
            "inertia_model": "rotate each own-COM tensor into S, then parallel-axis shift to the configuration system CG",
            "tensor_matrix_order": [["Ixx", "Ixy", "Ixz"], ["Ixy", "Iyy", "Iyz"], ["Ixz", "Iyz", "Izz"]],
            "uncertainty_model_ref": "wp2_design_mass/DESIGN_MASS_UNCERTAINTY_POLICY_V1.yaml (declared, PENDING_CALIBRATION, never measured)",
            "zero_fill_forbidden": True,
            "measured_or_as_built_claims_forbidden": True,
        },
        "uncertainty_policy": {
            "path": "wp2_design_mass/DESIGN_MASS_UNCERTAINTY_POLICY_V1.yaml",
            "sha256": sha256(POLICY_PATH),
            "status": "ACTIVE_DECLARED_ENGINEERING_POLICY_PENDING_CALIBRATION",
        },
        "aggregator": {
            "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/aggregate_m7_design_mass.py",
            "rerun_command": "python 20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/aggregate_m7_design_mass.py",
        },
        "m3r_analytic_idealization": {
            "method": "ring+plate composite of exact primitives (cylindrical shell, box, bore, pocket), uniform notional density, normalized to the ODR-05 budget",
            "idealized_volume_mm3": m3r["idealized_volume_mm3"],
            "stage_a_idealized_volume_mm3": m3r["stage_a_idealized_volume_mm3"],
            "stage_b_idealized_volume_mm3": m3r["stage_b_idealized_volume_mm3"],
            "stage_a_allocated_mass_kg": m3r["stage_a_allocated_mass_kg"],
            "stage_b_allocated_mass_kg": m3r["stage_b_allocated_mass_kg"],
            "stage_allocation_status": "PENDING_OWNER_ALLOCATION_VOLUME_PROPORTIONAL_ENGINEERING_RULE",
            "brep_volume_crosscheck": idealization_check,
            "freecad_run": False,
        },
        "source_register": source_register,
        "design_checks": design_checks,
        "configurations": configurations_out,
        "summary": {
            "configuration_count": 9,
            "design_mass_count": 9,
            "design_cg_count": 9,
            "design_inertia_count": 9,
            "design_principal_inertia_count": 9,
            "all_checks_pass": all_pass,
            "use_authorization": "ENGINEERING_DESIGN_ANALYSIS_ONLY_NOT_FLIGHT_NOT_QUALIFICATION_NOT_MEASURED",
        },
        "retained_holds": [
            "PENDING_CALIBRATION: all uncertainties are declared Type-B policy values; as-built weighing and a controlled uncertainty budget do not exist (M3R as-built measurement open per ODR-05)",
            "Q_STOW_ENGINEERING_CANDIDATE FK regression failure 567.734 mm and support-contact hold retained as facts; not absorbed by any uncertainty class (C05)",
            "Q_SERVICE_READY service-configuration ratification hold retained (C06)",
            "PREGRASP scene candidate not dynamics-validated for 22 kg / 150 kg capture (C07..C09)",
            "target identity, physical mass properties and capture transforms unratified (PROVISIONAL scenario anchors, M5 display-derived binding)",
            "panel physical full hinge kinematics and stowed-configuration collision/standoff relief remain open; bound transforms are DESIGN bindings, not ratified kinematics",
            "spacecraft load bridge remains a candidate member (MATERIAL_DERIVED) pending WP1 structure confirmation; M3R excludes fasteners/locator/harness/mating structure",
            "bus coverage of camera/HDRM/sensor/harness placeholders is not configuration-controlled (carried as limitation, not numeric allowance)",
            "launch-qualification FEA and launcher ICD remain HOLD (ODR-06); nothing here is a flight margin input",
            "correlation review required before any calibration upgrade (panel L/R shared budget source declared)",
        ],
        "release_prohibitions": [
            "DO_NOT_REPORT_ANY_VALUE_HERE_AS_MEASURED_OR_AS_INSTALLED",
            "DO_NOT_USE_FOR_FLIGHT_MARGIN_QUALIFICATION_OR_LAUNCHER_ICD",
            "DO_NOT_ZERO_FILL_OR_DROP_ANY_UNCERTAINTY_FIELD",
            "DO_NOT_OVERRIDE_ACCEPTED_URDF_MASSES_WITH_CAD_OR_CANDIDATE_VALUES",
            "DO_NOT_WRITE_ANY_VALUE_OF_THIS_FILE_BACK_INTO_M4_M5_M6_CDR_OR_SIM_BASELINES",
        ],
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="\n") as handle:
        yaml.safe_dump(output, handle, sort_keys=False, allow_unicode=True, width=140)

    print(json.dumps({
        "output": rel(OUTPUT_PATH),
        "all_checks_pass": all_pass,
        "design_masses_kg": {c["configuration_id"]: c["mass"]["value_kg"] for c in configurations_out},
        "design_mass_standard_uncertainties_kg": {c["configuration_id"]: c["mass"]["standard_uncertainty_kg"] for c in configurations_out},
        "closure_check": closure_check,
    }, indent=2))
    if not all_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
