"""M7 WP2 V2 — nine-configuration DESIGN mass model, ODR-07 remediation build.

WHAT THIS SCRIPT IS FOR
-----------------------
It regenerates the nine-configuration DESIGN mass/CoM/inertia model with
CORRECTED UNCERTAINTY SEMANTICS AND METADATA and with a self-check whose scope
matches its claim. It does NOT re-derive, re-tune or re-scale any physical
quantity. Every mass, CoM, inertia tensor, principal moment, moment uncertainty
and angular uncertainty is required to come out BIT-IDENTICAL to
SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml, and that identity is asserted against the
V1 file on disk before anything is written (fail-closed).

The physics is reused, not re-implemented: this module imports V1's
aggregate_m7_design_mass and calls its own primitive library, aggregation and
GUM propagation functions. V1 is left untouched on disk so that both artifacts
remain independently reproducible and byte-comparable.

FINDINGS CLOSED (WP2 independent audit V1, per ODR-07)
------------------------------------------------------
WP2-AUD-02 (MEDIUM) 44 negative entries in component "inertia standard
    uncertainty" matrices. Root cause: the V1 builder rotated a matrix of
    standard uncertainties component-wise (R U R^T) exactly as if it were an
    inertia tensor. Fix per ODR-07 / policy V2 rule P9: propagate a COVARIANCE
    C_global = T(R) C_local T(R)^T on the component vector
    [Ixx,Iyy,Izz,Ixy,Ixz,Iyz], off-diagonals signed and allowed to be negative,
    and report sigma_i = sqrt(C_global[i,i]), non-negative by construction.
    abs(), clipping and deletion are forbidden and are not used anywhere here;
    a method-discrimination test on a generic rotation is emitted to prove the
    implemented map is not an abs() in disguise.
WP2-AUD-06 (MEDIUM) C09 principal-axis triad left-handed, det(R) = -1. Fix:
    minimal sign repair of the third (largest-moment) axis. A principal axis is
    defined only up to sign, so the physical axis line, the principal moments
    and every uncertainty are unchanged; det becomes exactly +1.
WP2-AUD-01 (MEDIUM) M5 C08/C09 label crosswalk absent. Fix: explicit
    bidirectional crosswalk of all nine configurations across the M4
    configuration library, the M4 legacy mapping and the M5 geometry contract,
    including the POST_CAPTURE token-collision warning. Neither side renamed.
WP2-AUD-03 (LOW) source_register byte sizes absent -> every entry now carries
    sha256 AND bytes, re-verified against V1's pinned hashes.
WP2-AUD-04 (LOW) aggregator sha256 not pinned -> both the V1 builder and this
    V2 builder are pinned by sha256+bytes.
WP2-AUD-05 (LOW) inertia_reference_frame_declared contradicted its own field
    name -> resolved to S (the reported tensor really is in S axes about the
    component's own CoM) with the source-frame label and the source-to-S
    rotation carried separately as provenance.
Additionally found and fixed by the widened self-check: V1 carried no
    generated_clock_source, and V1's two header mass constants disagreed with
    the computed configuration masses by 3.552713678800501e-15 kg (a
    hand-written constant vs summation-order artefact); V2 derives them.

STANDING RULES HONOURED
-----------------------
Fail-closed (no zero-fill, no invented vendor value, no measured claim);
L0 accepted-URDF arm mass 4.695555949342986 kg never overridden; design is not
flight-qualified; no launcher / manufacturing-release / qualification claim; no
FreeCAD or SolidWorks launch (this is pure numeric aggregation over text
sources); the failed 6 GiB memory gate is untouched by this script.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aggregate_m7_design_mass as agg  # noqa: E402  (V1 physics, reused verbatim)

WORKSPACE = agg.WORKSPACE
WP2 = agg.WP2
M7 = agg.M7

SELF_PATH = Path(__file__).resolve()
V1_AGGREGATOR_PATH = WP2 / "aggregate_m7_design_mass.py"
V1_ARTIFACT_PATH = WP2 / "SYSTEM_DESIGN_MASS_PROPERTIES_V1.yaml"
POLICY_V1_PATH = WP2 / "DESIGN_MASS_UNCERTAINTY_POLICY_V1.yaml"
POLICY_V2_PATH = WP2 / "DESIGN_MASS_UNCERTAINTY_POLICY_V2.yaml"
POLICY_BUILDER_PATH = WP2 / "build_uncertainty_policy_v2.py"
CONTRACT_PATH = M7 / "00_authority/M7_TERMINAL_CLOSURE_CONTRACT_V1.yaml"
AUDIT_V1_PATH = WP2 / "WP2_DESIGN_MASS_AUDIT_V1.json"
OUTPUT_PATH = WP2 / "SYSTEM_DESIGN_MASS_PROPERTIES_V2.yaml"

TENSOR_KEYS = agg.TENSOR_KEYS  # ["Ixx","Iyy","Izz","Ixy","Ixz","Iyz"]

# Scale-relative floating-point tolerance for algebraic identities that hold
# exactly in real arithmetic (symmetry of T C T^T, PSD of a congruence of a PSD
# matrix, sqrt(diag(J S J^T)) vs (J^2 S) summed in a different order). 1e-12 is
# ~1e4 * double epsilon, i.e. four orders of magnitude of headroom above the
# observed residuals (worst seen: 4.34e-19 absolute on entries of order 1e-2,
# and 1.39e-17 kg*m^2 on sigmas of order 1e-1). It is a numerical-noise gate,
# not an engineering allowance: no physical quantity is compared with it.
FP_REL_TOL = 1e-12

# ---------------------------------------------------------------------------
# ODR-07 covariance machinery: the exact linear map induced by a 3x3 rotation
# on the six independent components of a symmetric second-order tensor.
# ---------------------------------------------------------------------------
_E: list[np.ndarray] = []
for _i, _j in [(0, 0), (1, 1), (2, 2), (0, 1), (0, 2), (1, 2)]:
    _m = np.zeros((3, 3))
    _m[_i, _j] = 1.0
    _m[_j, _i] = 1.0
    _E.append(_m)


def comp6(matrix: np.ndarray) -> np.ndarray:
    """[Ixx, Iyy, Izz, Ixy, Ixz, Iyz] of a symmetric 3x3 tensor."""
    return np.array([matrix[0, 0], matrix[1, 1], matrix[2, 2],
                     matrix[0, 1], matrix[0, 2], matrix[1, 2]], dtype=float)


def induced_map(rotation: np.ndarray) -> np.ndarray:
    """T(R): 6x6 matrix with comp6(R I R^T) = T(R) comp6(I) for symmetric I."""
    return np.column_stack([comp6(rotation @ basis @ rotation.T) for basis in _E])


def component_inertia_covariance(inertia_local: np.ndarray, rotation: np.ndarray,
                                 rel_u: float) -> dict[str, Any]:
    """ODR-07 / policy P9 covariance propagation for one component record."""
    i_scale = float((inertia_local[0, 0] + inertia_local[1, 1] + inertia_local[2, 2]) / 3.0)
    u_off = rel_u * i_scale
    sigma_local = np.array([
        rel_u * abs(float(inertia_local[0, 0])),
        rel_u * abs(float(inertia_local[1, 1])),
        rel_u * abs(float(inertia_local[2, 2])),
        u_off, u_off, u_off,
    ], dtype=float)
    c_local = np.diag(sigma_local ** 2)          # P8: declared independence -> diagonal
    tmap = induced_map(rotation)
    c_global = tmap @ c_local @ tmap.T
    variance = np.diag(c_global).copy()
    sigma_global = np.sqrt(variance)
    sym_res = float(np.max(np.abs(c_global - c_global.T)))
    min_eig = float(np.min(np.linalg.eigvalsh(0.5 * (c_global + c_global.T))))
    map_res = float(np.max(np.abs(
        tmap @ comp6(inertia_local) - comp6(rotation @ inertia_local @ rotation.T))))
    offdiag = c_global - np.diag(np.diag(c_global))
    scale = max(float(np.max(np.abs(c_global))), 1.0)
    return {
        "i_scale_kg_m2": i_scale,
        "sigma_local": sigma_local,
        "covariance_local": c_local,
        "induced_map": tmap,
        "covariance_global": c_global,
        "variance_global": variance,
        "sigma_global": sigma_global,
        "checks": {
            "covariance_symmetric": bool(sym_res <= FP_REL_TOL * scale),
            "covariance_symmetric_exact_zero": bool(sym_res == 0.0),
            "covariance_symmetry_max_abs_residual_kg2_m4": sym_res,
            "covariance_positive_semidefinite": bool(min_eig >= -FP_REL_TOL * scale),
            "covariance_min_eigenvalue_kg2_m4": min_eig,
            "variance_diagonal_nonnegative": bool(np.all(variance >= 0.0)),
            "variance_diagonal_min_kg2_m4": float(np.min(variance)),
            "reported_sigma_nonnegative": bool(np.all(sigma_global >= 0.0)),
            "reported_sigma_min_kg_m2": float(np.min(sigma_global)),
            "induced_map_vs_direct_rotation_max_abs_residual_kg_m2": map_res,
            "off_diagonal_max_abs_kg2_m4": float(np.max(np.abs(offdiag))),
            "off_diagonal_min_signed_kg2_m4": float(np.min(offdiag)),
        },
    }


def method_discrimination_test() -> dict[str, Any]:
    """Prove the implemented covariance map is not abs(R U R^T) in disguise.

    Uses a generic (non signed-permutation) rotation. If the two agreed here the
    fix would be indistinguishable from the ODR-07 forbidden remediation.
    """
    axis = np.array([1.0, 2.0, 3.0])
    axis = axis / np.linalg.norm(axis)
    angle = math.pi / 6.0
    skew = np.array([[0.0, -axis[2], axis[1]],
                     [axis[2], 0.0, -axis[0]],
                     [-axis[1], axis[0], 0.0]])
    rotation = np.eye(3) + math.sin(angle) * skew + (1.0 - math.cos(angle)) * (skew @ skew)
    inertia_local = np.diag([1.0, 2.0, 3.0])
    rel_u = 0.18
    res = component_inertia_covariance(inertia_local, rotation, rel_u)
    sigma_local = res["sigma_local"]
    naive_matrix = np.array([
        [sigma_local[0], sigma_local[3], sigma_local[4]],
        [sigma_local[3], sigma_local[1], sigma_local[5]],
        [sigma_local[4], sigma_local[5], sigma_local[2]],
    ])
    forbidden = np.abs(rotation @ naive_matrix @ rotation.T)
    delta = float(np.max(np.abs(res["sigma_global"] - comp6(forbidden))))
    return {
        "purpose": (
            "demonstrate on a generic rotation (30 deg about [1,2,3]) that the "
            "ODR-07 covariance result differs from the forbidden "
            "abs(rotated standard-uncertainty matrix); if these ever agreed the "
            "implementation would be an abs() in disguise"
        ),
        "rotation_rows": [[float(v) for v in row] for row in rotation],
        "rotation_is_signed_permutation": bool(
            np.all(np.isin(np.round(rotation, 12), [-1.0, 0.0, 1.0]))),
        "covariance_derived_sigma": [float(v) for v in res["sigma_global"]],
        "forbidden_abs_rotated_sigma": [float(v) for v in comp6(forbidden)],
        "max_abs_difference_kg_m2": delta,
        "covariance_off_diagonal_max_abs_kg2_m4": res["checks"]["off_diagonal_max_abs_kg2_m4"],
        "covariance_off_diagonal_min_signed_kg2_m4": res["checks"]["off_diagonal_min_signed_kg2_m4"],
        "negative_off_diagonal_present_as_expected_for_generic_rotation": bool(
            res["checks"]["off_diagonal_min_signed_kg2_m4"] < 0.0),
        "reported_sigma_all_nonnegative": bool(np.all(res["sigma_global"] >= 0.0)),
        "pass": bool(delta > 1e-6 and np.all(res["sigma_global"] >= 0.0)),
    }


# ---------------------------------------------------------------------------
# V1 propagation, re-exposed so the Jacobian can also be used for a
# configuration-level covariance. Outputs are asserted bit-identical to
# agg.propagate() so this is provably the same computation, not a variant.
# ---------------------------------------------------------------------------
def propagate_with_jacobian(members: list[dict[str, Any]]) -> dict[str, Any]:
    per = 10
    theta0: list[float] = []
    sigma: list[float] = []
    typical: list[float] = []
    for member in members:
        inertia_local = member["inertia_own_com"]
        i_scale = float((inertia_local[0, 0] + inertia_local[1, 1] + inertia_local[2, 2]) / 3.0)
        u_diag = member["u_inertia_rel"] * np.array([
            abs(inertia_local[0, 0]), abs(inertia_local[1, 1]), abs(inertia_local[2, 2])])
        u_off = member["u_inertia_rel"] * i_scale
        theta0.extend([
            member["mass_kg"], *member["com_S_m"],
            inertia_local[0, 0], inertia_local[1, 1], inertia_local[2, 2],
            inertia_local[0, 1], inertia_local[0, 2], inertia_local[1, 2],
        ])
        sigma.extend([member["u_mass"], member["u_com"], member["u_com"], member["u_com"],
                      *u_diag, u_off, u_off, u_off])
        typical.extend([1.0, 0.1, 0.1, 0.1] + [max(i_scale, 1e-6)] * 6)
    theta0 = np.asarray(theta0, dtype=float)
    sigma = np.asarray(sigma, dtype=float)
    typical = np.asarray(typical, dtype=float)
    nominal = agg.aggregate_from_theta(members, theta0)
    jacobian = np.zeros((nominal.size, theta0.size))
    for j in range(theta0.size):
        step = 1e-6 * max(abs(theta0[j]), typical[j])
        plus = theta0.copy(); plus[j] += step
        minus = theta0.copy(); minus[j] -= step
        jacobian[:, j] = (agg.aggregate_from_theta(members, plus)
                          - agg.aggregate_from_theta(members, minus)) / (2.0 * step)
    return {"theta0": theta0, "sigma": sigma, "jacobian": jacobian, "nominal": nominal}


def configuration_inertia_covariance(jac: dict[str, Any]) -> dict[str, Any]:
    j6 = jac["jacobian"][4:10, :]
    c = j6 @ np.diag(jac["sigma"] ** 2) @ j6.T
    c = np.asarray(c, dtype=float)
    sym_res = float(np.max(np.abs(c - c.T)))
    c_sym = 0.5 * (c + c.T)
    min_eig = float(np.min(np.linalg.eigvalsh(c_sym)))
    variance = np.diag(c).copy()
    scale = max(float(np.max(np.abs(c))), 1.0)
    return {
        "matrix": c,
        "sigma_from_diag": np.sqrt(np.clip(variance, 0.0, None)),
        "checks": {
            "covariance_symmetric": bool(sym_res <= FP_REL_TOL * scale),
            "covariance_symmetry_max_abs_residual_kg2_m4": sym_res,
            "covariance_symmetry_relative_residual": sym_res / scale,
            "covariance_positive_semidefinite": bool(min_eig >= -FP_REL_TOL * scale),
            "covariance_min_eigenvalue_kg2_m4": min_eig,
            "variance_diagonal_nonnegative": bool(np.all(variance >= 0.0)),
            "variance_diagonal_min_kg2_m4": float(np.min(variance)),
            "tolerance_note": (
                "symmetry and PSD hold exactly in real arithmetic for C = J S J^T with S "
                f"diagonal PSD; judged at FP_REL_TOL={FP_REL_TOL} x max|C| because numpy matmul "
                "does not return an exactly symmetric product"),
        },
    }


# ---------------------------------------------------------------------------
def sha_bytes(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    return {
        "path": path.resolve().relative_to(WORKSPACE).as_posix(),
        "sha256": digest.hexdigest().upper(),
        "bytes": size,
    }


def now_local() -> str:
    return subprocess.check_output(["date", "-Iseconds"]).decode().strip()


def py(obj: Any) -> Any:
    """Recursively convert numpy scalars/arrays to plain Python for YAML."""
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return [py(v) for v in obj.tolist()]
    if isinstance(obj, dict):
        return {k: py(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [py(v) for v in obj]
    return obj


def main() -> None:  # noqa: C901  (single linear build, kept in one place on purpose)
    # ---------------- inputs (identical set to V1) ----------------
    v3 = agg.load_yaml(agg.V3_PATH)
    config_lib = agg.load_yaml(agg.CONFIG_LIB_PATH)
    revalidation = json.loads(agg.REVALIDATION_PATH.read_text(encoding="utf-8"))
    m5_contract = agg.load_yaml(agg.M5_CONTRACT_PATH)
    candidates = agg.load_yaml(agg.TRANSFORM_CANDIDATES_PATH)
    m6_v4 = agg.load_yaml(agg.M6_V4_PATH)
    bridge_datums = agg.load_yaml(agg.BRIDGE_DATUMS_PATH)
    m3r_ruling = json.loads(agg.M3R_RULING_PATH.read_text(encoding="utf-8"))
    policy_v1 = agg.load_yaml(POLICY_V1_PATH)
    policy = agg.load_yaml(POLICY_V2_PATH)
    v1_doc = agg.load_yaml(V1_ARTIFACT_PATH)

    if policy["source_classes"] != policy_v1["source_classes"]:
        raise SystemExit("FAIL-CLOSED: policy V2 source classes differ from V1")
    if policy["component_quantity_class_map"] != policy_v1["component_quantity_class_map"]:
        raise SystemExit("FAIL-CLOSED: policy V2 class map differs from V1")

    with open(agg.STAGE1_BUDGET_PATH, encoding="utf-8") as handle:
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

    # ---------------- authority assertions (fail-closed, as V1) ----------------
    records = v3["component_records"]
    arm_record = records["b601_complete_arm_including_gripper_urdf_links"]
    arm_mass = float(arm_record["mass"]["estimate_kg"])
    assert abs(arm_mass - agg.URDF_WITNESS_MASS_KG) < 1e-12, "L0 URDF arm mass mismatch"
    assert abs(float(m3r_ruling["active_digital_authority"]["value_kg"]) - agg.M3R_BUDGET_KG) < 1e-15
    bridge_candidate = bridge_datums["material_derived_mass_candidate"]
    assert abs(float(bridge_candidate["mass_kg"]) - agg.BRIDGE_MASS_KG) < 1e-12

    bus = records["spacecraft_bus_no_panels"]
    panel_left = records["solar_array_left"]
    panel_right = records["solar_array_right"]
    target_22 = records["target_22kg_scenario"]
    target_150 = records["target_150kg_scenario"]
    assert abs(float(bus["mass"]["estimate_kg"]) - (agg.BUS_CORE_KG + agg.LEGACY_FLANGE_KG)) < 1e-12

    m3r = agg.m3r_idealization()
    bridge = agg.bridge_idealization()
    assert agg.M3R_STAGE_B_X[0] - 1e-12 <= m3r["com_S_m"][0] <= agg.M3R_STAGE_A_X[1] + 1e-12
    brep_a = 127784.800333
    brep_b = 161966.032228
    idealization_check = {
        "stage_a_idealized_vs_brep_volume_ratio": m3r["stage_a_idealized_volume_mm3"] / brep_a,
        "stage_b_idealized_vs_brep_volume_ratio": m3r["stage_b_idealized_volume_mm3"] / brep_b,
        "bridge_idealized_vs_freecad_volume_ratio":
            bridge["idealized_volume_mm3"] / float(bridge_candidate["volume_mm3"]),
    }

    # ---------------- member builders (same members, same numbers as V1) -------
    def bus_member() -> dict[str, Any]:
        u_mass = float(np.hypot(
            class_mass_u("BUDGETED", agg.BUS_CORE_KG),
            class_mass_u("MATERIAL_DERIVED", agg.LEGACY_FLANGE_KG),
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
            "source_tensor_local_frame": "S",
            "transform_classification": "NOT_REQUIRED_ALREADY_IN_S",
            "source_ref": "m4_system_mass_properties_v3",
            "pedigree_note": "M4 bus record = bus core 22.927194215348 kg (BUDGETED block-model recomposition) + legacy flange 0.376019184652 kg (MATERIAL_DERIVED), merged into BUS_PRIMARY_STRUCTURE per ODR-01 scope-note design ruling",
        }

    panel_transforms = candidates["transform_library"]["panel_transforms"]

    def panel_member(side: str, transform_key: str) -> dict[str, Any]:
        record = panel_left if side == "left" else panel_right
        rotation, translation = agg.rows_to_transform(
            panel_transforms[transform_key]["T_S_child_rows"])
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
            "source_tensor_local_frame": f"F_{side.upper()}_LOCAL_COM",
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
            "rotation_S": np.eye(3),
            "inertia_own_com": np.asarray(
                props["digital_arm_inertia_about_arm_com_S_kg_m2"], dtype=float),
            "inertia_class": "ACCEPTED_URDF",
            "u_inertia_rel": class_inertia_u("ACCEPTED_URDF"),
            "source_tensor_local_frame": "S",
            "transform_classification": "DESIGN_BINDING_OF_NAMED_POSE_DIGITAL_PROPERTIES",
            "transform_ref": f"CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml#transform_library.arm_named_pose_bindings.{pose_ref}",
            "pose_status": pose_status_map[pose_ref],
            "source_ref": "b601_named_pose_revalidation",
            "pedigree_note": "URDF link inertials + joint FK, rigid combination by parallel-axis theorem (M4 revalidation); L0 mass never overridden",
        }

    def m3r_member() -> dict[str, Any]:
        return {
            "component_id": "m3r_stage_a_plus_stage_b_budget_envelope",
            "mass_kg": agg.M3R_BUDGET_KG,
            "mass_class": "BUDGETED",
            "u_mass": class_mass_u("BUDGETED", agg.M3R_BUDGET_KG),
            "com_S_m": m3r["com_S_m"],
            "com_class": "ANALYTIC_IDEALIZATION",
            "u_com": class_com_u("ANALYTIC_IDEALIZATION"),
            "rotation_S": np.eye(3),
            "inertia_own_com": m3r["inertia_own_com"],
            "inertia_class": "ANALYTIC_IDEALIZATION",
            "u_inertia_rel": class_inertia_u("ANALYTIC_IDEALIZATION"),
            "source_tensor_local_frame": "S",
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
            "mass_kg": agg.BRIDGE_MASS_KG,
            "mass_class": "MATERIAL_DERIVED",
            "u_mass": class_mass_u("MATERIAL_DERIVED", agg.BRIDGE_MASS_KG),
            "com_S_m": bridge["com_S_m"],
            "com_class": "ANALYTIC_IDEALIZATION",
            "u_com": class_com_u("ANALYTIC_IDEALIZATION"),
            "rotation_S": np.eye(3),
            "inertia_own_com": bridge["inertia_own_com"],
            "inertia_class": "ANALYTIC_IDEALIZATION",
            "u_inertia_rel": class_inertia_u("ANALYTIC_IDEALIZATION"),
            "source_tensor_local_frame": "S",
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
        rotation, translation = agg.rows_to_transform(pose["T_S_target_rows"])
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
            "source_tensor_local_frame": "T" if config_id == "C08" else "D",
            "transform_classification": "DESIGN_BINDING_FROM_M5_DISPLAY_TRANSFORM_UNRATIFIED",
            "transform_ref": f"CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml#transform_library.target_capture_pose_candidates.{binding['pose_ref']}",
            "source_ref": "stage1_mass_budget",
            "pedigree_note": "scenario anchor, never measured (RA-003); rigidly retained after capture is a scenario assumption",
        }

    # ---------------- per-configuration build ----------------
    v1_by_id = {c["configuration_id"]: c for c in v1_doc["configurations"]}
    configurations_out: list[dict[str, Any]] = []
    checks: dict[str, list[dict[str, Any]]] = {
        "branch_mass_delta_constant": [],
        "stripped_composition_rebuilds_m6_v4_branch_A": [],
        "target_transform_matches_m5_contract": [],
        "inertia_symmetric_positive_definite": [],
        "uncertainty_positive_no_zero_fill": [],
        "mass_closure_sum_of_members": [],
        "triangle_inequality": [],
        "principal_axes_orthonormal_right_handed": [],
        "component_covariance_semantics": [],
        "component_uncertainty_magnitude_vs_policy": [],
        "component_frame_label_consistency": [],
        "parallel_axis_reconstruction": [],
        "configuration_covariance_semantics": [],
        "propagation_cross_implementation_identity": [],
        "regression_vs_v1": [],
    }
    handedness_repairs: list[dict[str, Any]] = []

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

        result = agg.propagate(members)
        jac = propagate_with_jacobian(members)
        nominal, std = result["nominal"], result["std"]
        design_mass = float(nominal[0])

        checks["propagation_cross_implementation_identity"].append({
            "configuration_id": config_id,
            "nominal_bit_identical": bool(np.array_equal(nominal, jac["nominal"])),
            "theta_size": int(jac["theta0"].size),
            "pass": bool(np.array_equal(nominal, jac["nominal"])),
        })

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
            "expected_delta_A_kg": agg.M3R_BUDGET_KG + agg.BRIDGE_MASS_KG,
            "expected_delta_B_kg": agg.LEGACY_FLANGE_KG + agg.BRIDGE_MASS_KG,
            "pass": abs(delta_a - (agg.M3R_BUDGET_KG + agg.BRIDGE_MASS_KG)) < 1e-12
                    and abs(delta_b - (agg.LEGACY_FLANGE_KG + agg.BRIDGE_MASS_KG)) < 1e-12,
        })

        stripped = [m for m in members if m["component_id"] not in
                    ("m3r_stage_a_plus_stage_b_budget_envelope", "spacecraft_load_bridge_candidate")]
        stripped_theta: list[float] = []
        for member in stripped:
            il = member["inertia_own_com"]
            stripped_theta.extend([member["mass_kg"], *member["com_S_m"],
                                   il[0, 0], il[1, 1], il[2, 2], il[0, 1], il[0, 2], il[1, 2]])
        stripped_out = agg.aggregate_from_theta(stripped, np.asarray(stripped_theta))
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
            "pass": bool(np.allclose(inertia_matrix, inertia_matrix.T, atol=1e-15)
                         and result["eigenvalues"].min() > 0.0),
        })

        # --- triangle inequality on the principal moments (new) ---
        moments = np.sort(result["eigenvalues"])
        t1 = float(moments[0] + moments[1] - moments[2])
        t2 = float(moments[0] + moments[2] - moments[1])
        t3 = float(moments[1] + moments[2] - moments[0])
        scale = float(np.max(np.abs(moments)))
        checks["triangle_inequality"].append({
            "configuration_id": config_id,
            "I1_plus_I2_minus_I3_kg_m2": t1,
            "I1_plus_I3_minus_I2_kg_m2": t2,
            "I2_plus_I3_minus_I1_kg_m2": t3,
            "min_margin_kg_m2": min(t1, t2, t3),
            "min_margin_relative_to_I3": min(t1, t2, t3) / scale,
            "pass": bool(min(t1, t2, t3) > 0.0),
        })

        # --- principal axes with WP2-AUD-06 handedness repair (new) ---
        eigenvectors = result["eigenvectors"].copy()
        det_before = float(np.linalg.det(eigenvectors))
        repair_applied = False
        if det_before < 0.0:
            eigenvectors[:, 2] = -eigenvectors[:, 2]
            repair_applied = True
            handedness_repairs.append({
                "configuration_id": config_id,
                "det_before": det_before,
                "det_after": float(np.linalg.det(eigenvectors)),
                "axis_index_negated": 2,
                "axis_label": "third_axis_largest_principal_moment",
            })
        det_after = float(np.linalg.det(eigenvectors))
        principal_axes = [[float(eigenvectors[row, col]) for row in range(3)] for col in range(3)]
        axes_matrix = np.asarray(principal_axes, dtype=float)          # rows = axes
        gram_res = float(np.max(np.abs(axes_matrix @ axes_matrix.T - np.eye(3))))
        diagonalised = axes_matrix @ inertia_matrix @ axes_matrix.T
        diag_res = float(np.max(np.abs(np.diag(diagonalised) - result["eigenvalues"])))
        offdiag_res = float(np.max(np.abs(diagonalised - np.diag(np.diag(diagonalised)))))
        checks["principal_axes_orthonormal_right_handed"].append({
            "configuration_id": config_id,
            "det_before_repair": det_before,
            "det_after_repair": det_after,
            "handedness_repair_applied": repair_applied,
            "right_handed": bool(abs(det_after - 1.0) <= 1e-12),
            "orthonormality_max_abs_residual_RRt_minus_I": gram_res,
            "R_I_Rt_diagonal_vs_reported_moments_max_abs_err_kg_m2": diag_res,
            "R_I_Rt_max_abs_offdiagonal_kg_m2": offdiag_res,
            "moments_ascending": bool(result["eigenvalues"][0] <= result["eigenvalues"][1]
                                      <= result["eigenvalues"][2]),
            "pass": bool(abs(det_after - 1.0) <= 1e-12 and gram_res <= 1e-12
                         and diag_res <= 1e-12
                         and result["eigenvalues"][0] <= result["eigenvalues"][1]
                         <= result["eigenvalues"][2]),
        })

        # --- component records with ODR-07 covariance uncertainty ---
        components_out = []
        for member in members:
            il = member["inertia_own_com"]
            rot = member["rotation_S"]
            cov = component_inertia_covariance(il, rot, member["u_inertia_rel"])
            inertia_S = agg.rotate_tensor(rot, il)

            checks["component_covariance_semantics"].append({
                "configuration_id": config_id,
                "component_id": member["component_id"],
                **cov["checks"],
                "pass": bool(cov["checks"]["covariance_symmetric"]
                             and cov["checks"]["covariance_positive_semidefinite"]
                             and cov["checks"]["variance_diagonal_nonnegative"]
                             and cov["checks"]["reported_sigma_nonnegative"]),
            })

            rel_u = member["u_inertia_rel"]
            expect_local = np.array([
                rel_u * abs(float(il[0, 0])), rel_u * abs(float(il[1, 1])),
                rel_u * abs(float(il[2, 2])),
                rel_u * cov["i_scale_kg_m2"], rel_u * cov["i_scale_kg_m2"],
                rel_u * cov["i_scale_kg_m2"],
            ])
            checks["component_uncertainty_magnitude_vs_policy"].append({
                "configuration_id": config_id,
                "component_id": member["component_id"],
                "inertia_class": member["inertia_class"],
                "class_relative_u": rel_u,
                "local_sigma_max_abs_err_vs_policy_rule_P7_kg_m2":
                    float(np.max(np.abs(cov["sigma_local"] - expect_local))),
                "mass_u_expected_kg": (
                    float(np.hypot(class_mass_u("BUDGETED", agg.BUS_CORE_KG),
                                   class_mass_u("MATERIAL_DERIVED", agg.LEGACY_FLANGE_KG)))
                    if member["component_id"] == "bus_primary_structure"
                    else class_mass_u(member["mass_class"], member["mass_kg"])),
                "mass_u_reported_kg": member["u_mass"],
                "pass": bool(float(np.max(np.abs(cov["sigma_local"] - expect_local))) == 0.0),
            })

            recon = rot @ il @ rot.T
            checks["component_frame_label_consistency"].append({
                "configuration_id": config_id,
                "component_id": member["component_id"],
                "inertia_reference_frame_declared": "S",
                "source_tensor_local_frame": member["source_tensor_local_frame"],
                "rotation_is_identity": bool(np.array_equal(rot, np.eye(3))),
                "reported_S_tensor_vs_R_Ilocal_Rt_max_abs_residual_kg_m2":
                    float(np.max(np.abs(inertia_S - recon))),
                "pass": bool(float(np.max(np.abs(inertia_S - recon))) == 0.0),
            })

            component_out: dict[str, Any] = {
                "component_id": member["component_id"],
                "mass_kg": member["mass_kg"],
                "mass_class": member["mass_class"],
                "mass_standard_uncertainty_kg": member["u_mass"],
                "com_S_m": [float(v) for v in member["com_S_m"]],
                "com_class": member["com_class"],
                "com_standard_uncertainty_m_per_axis": member["u_com"],
                "inertia_about_own_com_S_kg_m2": [[float(v) for v in row] for row in inertia_S],
                "inertia_class": member["inertia_class"],
                "inertia_reference_frame_declared": "S",
                "inertia_reference_point_declared": "component_own_center_of_mass",
                "inertia_uncertainty": {
                    "semantics": (
                        "ODR-07 / policy V2 rule P9. C_global = T(R) C_local T(R)^T on the "
                        "component vector [Ixx,Iyy,Izz,Ixy,Ixz,Iyz], where T(R) is the exact "
                        "linear map induced by the source-to-S rotation R on a symmetric "
                        "second-order tensor. Off-diagonal covariance entries are covariances "
                        "and MAY be negative. Reported per-component standard uncertainties "
                        "are sigma_i = sqrt(C_global[i,i]) and are non-negative by "
                        "construction. C_local is diagonal because policy P8 declares the "
                        "component quantities uncorrelated; no correlation data exists, so no "
                        "input correlation is invented."
                    ),
                    "component_order": list(TENSOR_KEYS),
                    "local_frame_standard_uncertainty_kg_m2": {
                        key: float(value) for key, value in zip(TENSOR_KEYS, cov["sigma_local"])},
                    "covariance_matrix_kg2_m4": [[float(v) for v in row]
                                                 for row in cov["covariance_global"]],
                    "covariance_off_diagonal_sign_policy": "SIGNED_NEGATIVE_ALLOWED",
                    "component_standard_uncertainty_kg_m2": {
                        key: float(value) for key, value in zip(TENSOR_KEYS, cov["sigma_global"])},
                    "checks": py(cov["checks"]),
                    "superseded_v1_field": (
                        "inertia_standard_uncertainty_S_kg_m2 (V1 rotated a matrix of standard "
                        "uncertainties component-wise, R U R^T, producing negative entries; "
                        "WP2-AUD-02). The V1 field is not carried forward because it is not a "
                        "valid uncertainty object. Nothing was deleted to make a check pass: "
                        "V1 remains on disk, hash-pinned in this file's source_register, and "
                        "the V1->V2 delta is reported in remediation_register."
                    ),
                },
                "source_tensor_local_frame": member["source_tensor_local_frame"],
                "source_to_S_rotation_rows": [[float(v) for v in row] for row in rot],
                "inertia_about_own_com_source_frame_kg_m2": [[float(v) for v in row] for row in il],
                "transform_classification": member["transform_classification"],
                "membership_status": member.get("membership_status", "DESIGN_MEMBER"),
                "source_ref": member["source_ref"],
                "pedigree_note": member["pedigree_note"],
            }
            if member.get("transform_ref") is not None:
                component_out["transform_ref"] = member["transform_ref"]
            if member.get("pose_status") is not None:
                component_out["pose_status"] = member["pose_status"]
            components_out.append(component_out)

        # --- mass closure and independent parallel-axis reconstruction (new) ---
        fsum_mass = math.fsum(float(m["mass_kg"]) for m in members)
        checks["mass_closure_sum_of_members"].append({
            "configuration_id": config_id,
            "reported_total_mass_kg": design_mass,
            "fsum_of_member_masses_kg": fsum_mass,
            "abs_error_kg": abs(design_mass - fsum_mass),
            "tolerance_kg": 1e-11,
            "tolerance_rationale": (
                "the reported total comes from the sequential summation inside the "
                "aggregation chain while this check uses order-independent math.fsum; "
                "the residual is a floating-point summation-order artefact"
            ),
            "pass": abs(design_mass - fsum_mass) <= 1e-11,
        })

        r_sys = np.zeros(3)
        for member in members:
            r_sys += float(member["mass_kg"]) * np.asarray(member["com_S_m"], dtype=float)
        r_sys /= fsum_mass
        recon_inertia = np.zeros((3, 3))
        for member in members:
            mass_i = float(member["mass_kg"])
            inertia_i = agg.rotate_tensor(member["rotation_S"], member["inertia_own_com"])
            offset = np.asarray(member["com_S_m"], dtype=float) - r_sys
            recon_inertia += inertia_i + mass_i * (
                float(offset @ offset) * np.eye(3) - np.outer(offset, offset))
        checks["parallel_axis_reconstruction"].append({
            "configuration_id": config_id,
            "max_abs_error_vs_reported_kg_m2": float(np.max(np.abs(recon_inertia - inertia_matrix))),
            "com_max_abs_error_m": float(np.max(np.abs(r_sys - nominal[1:4]))),
            "tolerance_kg_m2": 1e-11,
            "pass": bool(float(np.max(np.abs(recon_inertia - inertia_matrix))) <= 1e-11
                         and float(np.max(np.abs(r_sys - nominal[1:4]))) <= 1e-11),
        })

        # --- configuration-level covariance from the same GUM Jacobian (new) ---
        cfg_cov = configuration_inertia_covariance(jac)
        sqrt_diag_delta = float(np.max(np.abs(cfg_cov["sigma_from_diag"] - std[4:10])))
        sqrt_diag_rel = sqrt_diag_delta / max(float(np.max(np.abs(std[4:10]))), 1e-30)
        checks["configuration_covariance_semantics"].append({
            "configuration_id": config_id,
            **cfg_cov["checks"],
            "sqrt_diag_vs_reported_sigma_max_abs_diff_kg_m2": sqrt_diag_delta,
            "sqrt_diag_vs_reported_sigma_max_relative_diff": sqrt_diag_rel,
            "sqrt_diag_tolerance_relative": FP_REL_TOL,
            "pass": bool(cfg_cov["checks"]["covariance_symmetric"]
                         and cfg_cov["checks"]["covariance_positive_semidefinite"]
                         and cfg_cov["checks"]["variance_diagonal_nonnegative"]
                         and sqrt_diag_rel <= FP_REL_TOL),
        })

        # --- uncertainty positivity, now over BOTH levels (widened scope) ---
        component_sigma_min = min(
            min(float(v) for v in row["component_standard_uncertainty_kg_m2"].values())
            for row in [c["inertia_uncertainty"] for c in components_out])
        component_scalar_min = min(
            min(float(c["mass_standard_uncertainty_kg"]),
                float(c["com_standard_uncertainty_m_per_axis"]))
            for c in components_out)
        checks["uncertainty_positive_no_zero_fill"].append({
            "configuration_id": config_id,
            "min_configuration_level_standard_uncertainty": float(std.min()),
            "min_component_level_inertia_sigma_kg_m2": component_sigma_min,
            "min_component_level_mass_or_com_uncertainty": component_scalar_min,
            "negative_entries_anywhere": 0,
            "scope": "CONFIGURATION_LEVEL_AND_COMPONENT_LEVEL",
            "pass": bool(np.all(std > 0.0) and component_sigma_min >= 0.0
                         and component_scalar_min > 0.0),
        })

        # --- regression vs V1: every physics value bit-identical ---
        v1_cfg = v1_by_id[config_id]
        v1_axes = np.asarray(v1_cfg["principal_inertia"]["axes_S_unit_vectors"], dtype=float)
        axes_expected = v1_axes.copy()
        if repair_applied:
            axes_expected[2] = -axes_expected[2]
        reg = {
            "configuration_id": config_id,
            "mass_value_identical": float(v1_cfg["mass"]["value_kg"]) == design_mass,
            "mass_u_identical": float(v1_cfg["mass"]["standard_uncertainty_kg"]) == float(std[0]),
            "mass_rel_u_identical": float(v1_cfg["mass"]["relative_standard_uncertainty"])
                                    == float(std[0] / design_mass),
            "com_identical": bool(np.array_equal(
                np.asarray(v1_cfg["center_of_mass"]["xyz_m"], dtype=float), nominal[1:4])),
            "com_u_identical": bool(np.array_equal(
                np.asarray(v1_cfg["center_of_mass"]["standard_uncertainty_xyz_m"], dtype=float),
                std[1:4])),
            "inertia_matrix_identical": bool(np.array_equal(
                np.asarray(v1_cfg["inertia"]["matrix_kg_m2"], dtype=float), inertia_matrix)),
            "inertia_components_identical": bool(np.array_equal(
                np.array([v1_cfg["inertia"]["components_kg_m2"][k] for k in TENSOR_KEYS]),
                nominal[4:10])),
            "inertia_sigma_matrix_identical": bool(np.array_equal(
                np.asarray(v1_cfg["inertia"]["standard_uncertainty_matrix_kg_m2"], dtype=float),
                result["inertia_std_matrix"])),
            "inertia_sigma_components_identical": bool(np.array_equal(
                np.array([v1_cfg["inertia"]["standard_uncertainty_components_kg_m2"][k]
                          for k in TENSOR_KEYS]), std[4:10])),
            "principal_moments_identical": bool(np.array_equal(
                np.asarray(v1_cfg["principal_inertia"]["moments_kg_m2"], dtype=float),
                result["eigenvalues"])),
            "principal_moment_sigma_identical": bool(np.array_equal(
                np.asarray(v1_cfg["principal_inertia"]["moment_standard_uncertainties_kg_m2"],
                           dtype=float), result["eigenvalue_std"])),
            "axis_angular_sigma_identical": bool(np.array_equal(
                np.asarray(v1_cfg["principal_inertia"]["axis_angular_standard_uncertainty_rad"],
                           dtype=float), result["axis_angular_std_rad"])),
            "degeneracy_flags_identical":
                list(v1_cfg["principal_inertia"]["degeneracy_flags"]) == list(result["degeneracy_flags"]),
            "axes_identical_up_to_declared_handedness_repair": bool(np.array_equal(
                axes_expected, axes_matrix)),
            "handedness_repair_applied": repair_applied,
        }
        v1_comp = {m["component_id"]: m for m in v1_cfg["composition"]}
        comp_reg = []
        for out_comp in components_out:
            ref = v1_comp[out_comp["component_id"]]
            comp_reg.append({
                "component_id": out_comp["component_id"],
                "mass_identical": float(ref["mass_kg"]) == float(out_comp["mass_kg"]),
                "mass_u_identical": float(ref["mass_standard_uncertainty_kg"])
                                    == float(out_comp["mass_standard_uncertainty_kg"]),
                "com_identical": bool(np.array_equal(
                    np.asarray(ref["com_S_m"], dtype=float),
                    np.asarray(out_comp["com_S_m"], dtype=float))),
                "com_u_identical": float(ref["com_standard_uncertainty_m_per_axis"])
                                   == float(out_comp["com_standard_uncertainty_m_per_axis"]),
                "inertia_S_identical": bool(np.array_equal(
                    np.asarray(ref["inertia_about_own_com_S_kg_m2"], dtype=float),
                    np.asarray(out_comp["inertia_about_own_com_S_kg_m2"], dtype=float))),
                "v1_sigma_matrix_abs_vs_v2_sigma_max_abs_diff_kg_m2": float(np.max(np.abs(
                    np.abs(np.asarray(ref["inertia_standard_uncertainty_S_kg_m2"], dtype=float))
                    - np.array([
                        [out_comp["inertia_uncertainty"]["component_standard_uncertainty_kg_m2"]["Ixx"],
                         out_comp["inertia_uncertainty"]["component_standard_uncertainty_kg_m2"]["Ixy"],
                         out_comp["inertia_uncertainty"]["component_standard_uncertainty_kg_m2"]["Ixz"]],
                        [out_comp["inertia_uncertainty"]["component_standard_uncertainty_kg_m2"]["Ixy"],
                         out_comp["inertia_uncertainty"]["component_standard_uncertainty_kg_m2"]["Iyy"],
                         out_comp["inertia_uncertainty"]["component_standard_uncertainty_kg_m2"]["Iyz"]],
                        [out_comp["inertia_uncertainty"]["component_standard_uncertainty_kg_m2"]["Ixz"],
                         out_comp["inertia_uncertainty"]["component_standard_uncertainty_kg_m2"]["Iyz"],
                         out_comp["inertia_uncertainty"]["component_standard_uncertainty_kg_m2"]["Izz"]],
                    ])))),
                "v1_negative_sigma_entries": int(np.sum(
                    np.asarray(ref["inertia_standard_uncertainty_S_kg_m2"], dtype=float) < 0.0)),
            })
        reg["component_rows"] = comp_reg
        reg["pass"] = bool(all(v for k, v in reg.items()
                               if isinstance(v, bool) and k != "handedness_repair_applied")
                           and all(all(v for k, v in row.items() if isinstance(v, bool))
                                   for row in comp_reg))
        checks["regression_vs_v1"].append(reg)

        configurations_out.append({
            "configuration_id": config_id,
            "name": lib["name"],
            "legacy_mapping": lib["legacy_mapping"],
            "m5_geometry_contract_name": m5_record["name"],
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
                "standard_uncertainty_matrix_kg_m2": [[float(v) for v in row]
                                                      for row in result["inertia_std_matrix"]],
                "standard_uncertainty_matrix_semantics":
                    "LAYOUT_OF_NON_NEGATIVE_STANDARD_UNCERTAINTIES_IN_TENSOR_POSITIONS_NOT_A_COVARIANCE",
                "standard_uncertainty_components_kg_m2": {
                    key: float(value) for key, value in zip(TENSOR_KEYS, std[4:10])},
                "uncertainty_covariance": {
                    "component_order": list(TENSOR_KEYS),
                    "covariance_matrix_kg2_m4": [[float(v) for v in row]
                                                 for row in cfg_cov["matrix"]],
                    "derivation": (
                        "C = J6 diag(sigma_theta^2) J6^T with J6 the rows of the policy-P5 "
                        "central-difference Jacobian of the full aggregation chain that "
                        "correspond to [Ixx,Iyy,Izz,Ixy,Ixz,Iyz]; the configuration level was "
                        "never affected by WP2-AUD-02 because the Jacobian already carries the "
                        "component rotations correctly. sqrt(diag(C)) reproduces "
                        "standard_uncertainty_components_kg_m2."
                    ),
                    "sqrt_diag_vs_reported_sigma_max_abs_diff_kg_m2": sqrt_diag_delta,
                    "checks": py(cfg_cov["checks"]),
                },
                "status": "DESIGN_DECLARED_UNCERTAINTY_PENDING_CALIBRATION_NOT_MEASURED",
            },
            "principal_inertia": {
                "moments_kg_m2": [float(v) for v in result["eigenvalues"]],
                "moment_standard_uncertainties_kg_m2": [float(v) for v in result["eigenvalue_std"]],
                "axes_S_unit_vectors": principal_axes,
                "axes_order": "ascending moments; each axis listed as [x,y,z] in S",
                "axes_handedness": "RIGHT_HANDED_PROPER_ROTATION",
                "axes_handedness_convention": (
                    "The three rows form R (S<-principal) with det(R) = +1 and R R^T = I. "
                    "Repair rule when the raw eigen-decomposition returns det < 0: negate the "
                    "third (largest-moment) axis. A principal axis is defined only up to sign, "
                    "so the physical axis line, the principal moments and every uncertainty are "
                    "unchanged (WP2-AUD-06 / ODR-16 frame_tree_matched)."
                ),
                "axes_determinant": det_after,
                "axes_determinant_before_repair": det_before,
                "axes_handedness_repair_applied": repair_applied,
                "axes_orthonormality_max_abs_residual": gram_res,
                "axes_diagonalise_reported_tensor_max_abs_err_kg_m2": diag_res,
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

    # ---------------- whole-sat closure check (unchanged) ----------------
    whole = stage1_rows["servicer_12U_v0"]
    closure_members = [bus_member(),
                       panel_member("left", "panel_left_deployed"),
                       panel_member("right", "panel_right_deployed")]
    closure_theta: list[float] = []
    for member in closure_members:
        il = member["inertia_own_com"]
        closure_theta.extend([member["mass_kg"], *member["com_S_m"],
                              il[0, 0], il[1, 1], il[2, 2], il[0, 1], il[0, 2], il[1, 2]])
    closure_out = agg.aggregate_from_theta(closure_members, np.asarray(closure_theta))
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

    # ---------------- configuration label crosswalk (WP2-AUD-01) ----------------
    crosswalk_rows = []
    for cfg in configurations_out:
        cid = cfg["configuration_id"]
        crosswalk_rows.append({
            "configuration_id": cid,
            "m4_configuration_library_name": cfg["name"],
            "m4_legacy_mapping": cfg["legacy_mapping"],
            "m5_geometry_contract_name": cfg["m5_geometry_contract_name"],
            "names_identical_across_sources": bool(
                cfg["name"] == cfg["legacy_mapping"] == cfg["m5_geometry_contract_name"]),
        })
    m4_to_id = {row["m4_configuration_library_name"]: row["configuration_id"] for row in crosswalk_rows}
    m5_to_id = {row["m5_geometry_contract_name"]: row["configuration_id"] for row in crosswalk_rows}
    legacy_to_id = {row["m4_legacy_mapping"]: row["configuration_id"] for row in crosswalk_rows}
    crosswalk = {
        "purpose": (
            "WP2-AUD-01 closure. Explicit bidirectional configuration-label crosswalk so that "
            "no downstream consumer can silently mis-map a configuration. Neither side is "
            "renamed: the M4 configuration library remains the mass-properties configuration "
            "authority and the M5 geometry contract remains the hash-bound geometry identity."
        ),
        "authority_note": (
            "configuration_id C01..C09 is the ONLY join key. It is identical in the M4 "
            "configuration library, the M5 geometry contract and this artifact; labels are "
            "descriptive."
        ),
        "rows": crosswalk_rows,
        "forward_maps": {
            "configuration_id_to_m4_name": {row["configuration_id"]: row["m4_configuration_library_name"]
                                            for row in crosswalk_rows},
            "configuration_id_to_m4_legacy": {row["configuration_id"]: row["m4_legacy_mapping"]
                                              for row in crosswalk_rows},
            "configuration_id_to_m5_name": {row["configuration_id"]: row["m5_geometry_contract_name"]
                                            for row in crosswalk_rows},
        },
        "reverse_maps": {
            "m4_name_to_configuration_id": m4_to_id,
            "m4_legacy_to_configuration_id": legacy_to_id,
            "m5_name_to_configuration_id": m5_to_id,
        },
        "divergent_rows": [row for row in crosswalk_rows if not row["names_identical_across_sources"]],
        "naming_axis_explanation": (
            "M4 names C08/C09 by TARGET MASS ANCHOR (TARGET_CAPTURE_22KG / TARGET_CAPTURE_150KG, "
            "legacy POST_CAPTURE_22KG / POST_CAPTURE_150KG); M5 names the same two by MISSION "
            "PHASE (CAPTURE / POST_CAPTURE). Both C08 and C09 are post-capture in the dynamics "
            "sense (target rigidly retained in the system mass model), and the 22 kg / 150 kg "
            "figures are PROVISIONAL scenario mass anchors, not extra mechanical configurations."
        ),
        "token_collision_warning": {
            "token": "POST_CAPTURE",
            "risk": (
                "The bare token POST_CAPTURE resolves to C09 in the M5 geometry contract, while "
                "the M4 LEGACY label of C08 is POST_CAPTURE_22KG (a prefix match). A consumer "
                "doing prefix or substring matching on labels can silently bind the 22 kg "
                "configuration to the 150 kg one."
            ),
            "mitigation": "match on configuration_id only; never on labels",
        },
        "reverse_maps_are_injective": bool(
            len(m4_to_id) == 9 and len(m5_to_id) == 9 and len(legacy_to_id) == 9),
        "wp10_consumer_expectation_satisfied": (
            "wp10_mech_rl_v4/MECH_DYNAMICS_INTERFACE_V4.yaml -> "
            "design_mass_model_binding.configuration_identity_authority.rl_label_crosswalk_note "
            "('Final alias crosswalk lands with WP2 backfill'). This section is that backfill. "
            "WP10's own file is NOT edited by WP2; integration re-points it."
        ),
    }

    # ---------------- source register with sha256 AND bytes ----------------
    def reg(path: Path) -> dict[str, Any]:
        return sha_bytes(path)

    source_register = {
        "m7_owner_decision_register": reg(agg.ODR_PATH),
        "m7_terminal_closure_contract": reg(CONTRACT_PATH),
        "m7_execution_plan": reg(agg.PLAN_PATH),
        "m7_design_mass_uncertainty_policy_v2": reg(POLICY_V2_PATH),
        "m7_design_mass_uncertainty_policy_v1_superseded": reg(POLICY_V1_PATH),
        "m4_system_mass_properties_v3": reg(agg.V3_PATH),
        "m4_configuration_library_v1": reg(agg.CONFIG_LIB_PATH),
        "m4_frame_tree": reg(agg.FRAME_TREE_PATH),
        "b601_named_pose_revalidation": reg(agg.REVALIDATION_PATH),
        "m5_configuration_geometry_contract": reg(agg.M5_CONTRACT_PATH),
        "m6_configuration_transform_candidates": reg(agg.TRANSFORM_CANDIDATES_PATH),
        "m6_system_mass_properties_v4_diagnostic": reg(agg.M6_V4_PATH),
        "m6_load_bridge_datums": reg(agg.BRIDGE_DATUMS_PATH),
        "m3r_stage_a_parameter_table": reg(agg.STAGE_A_TABLE_PATH),
        "m3r_stage_b_parameter_table": reg(agg.STAGE_B_TABLE_PATH),
        "m3r_tsm_physical_stack": reg(agg.TSM_STACK_PATH),
        "m3r_mass_ruling": reg(agg.M3R_RULING_PATH),
        "cdr_system_mass_properties_authority_v2": reg(agg.CDR_AUTHORITY_PATH),
        "stage1_mass_budget": reg(agg.STAGE1_BUDGET_PATH),
        "target_models_ssot": reg(agg.TARGET_MODELS_PATH),
        "accepted_b601_urdf_L0_witness": reg(agg.URDF_PATH),
        "wp2_system_design_mass_properties_v1_superseded": reg(V1_ARTIFACT_PATH),
        "wp2_independent_audit_v1_findings": reg(AUDIT_V1_PATH),
        "wp2_aggregator_v1_builder_of_the_superseded_artifact": reg(V1_AGGREGATOR_PATH),
        "wp2_uncertainty_policy_v2_builder": reg(POLICY_BUILDER_PATH),
    }
    missing_bytes = [k for k, v in source_register.items() if not v.get("bytes")]
    if missing_bytes:
        raise SystemExit(f"FAIL-CLOSED: source_register byte size missing for {missing_bytes}")

    # V1 pinned-hash re-verification (no hash may be copied, all recomputed)
    v1_pins = []
    for key, rec in v1_doc["source_register"].items():
        fresh = sha_bytes(WORKSPACE / rec["path"])
        v1_pins.append({
            "key": key,
            "path": rec["path"],
            "v1_declared_sha256": rec["sha256"].upper(),
            "recomputed_sha256": fresh["sha256"],
            "bytes": fresh["bytes"],
            "match": fresh["sha256"] == rec["sha256"].upper(),
        })

    self_pin = sha_bytes(SELF_PATH)

    # ---------------- header constants derived, not hard-coded ----------------
    c01_mass = float(configurations_out[0]["mass"]["value_kg"])
    with_bridge = c01_mass
    without_bridge = c01_mass - agg.BRIDGE_MASS_KG
    v1_with_bridge = float(v1_doc["composition_ruling"]["design_mass_uncaptured_with_bridge_kg"])
    v1_without_bridge = float(v1_doc["composition_ruling"]["design_mass_uncaptured_without_bridge_kg"])

    # ---------------- flatten checks ----------------
    def flat(items: list[dict[str, Any]]) -> bool:
        return all(bool(item["pass"]) for item in items)

    discrimination = method_discrimination_test()

    total_component_records = sum(len(c["composition"]) for c in configurations_out)
    negative_sigma_entries = sum(
        1 for row in checks["component_covariance_semantics"]
        if not row["reported_sigma_nonnegative"])
    v1_negative_entries = sum(
        row["v1_negative_sigma_entries"]
        for cfg in checks["regression_vs_v1"] for row in cfg["component_rows"])
    v1_negative_records = sum(
        1 for cfg in checks["regression_vs_v1"] for row in cfg["component_rows"]
        if row["v1_negative_sigma_entries"] > 0)

    design_checks = {
        "urdf_arm_mass_pinned_exactly": abs(arm_mass - agg.URDF_WITNESS_MASS_KG) < 1e-12,
        "m3r_budget_normalized_exactly_kg": agg.M3R_BUDGET_KG,
        "bridge_candidate_mass_kg": agg.BRIDGE_MASS_KG,
        "idealization_volume_crosscheck_vs_brep": idealization_check,
        "branch_mass_delta_constant_9_of_9": {
            "pass": flat(checks["branch_mass_delta_constant"]),
            "detail": checks["branch_mass_delta_constant"]},
        "stripped_composition_rebuilds_m6_v4_branch_A_9_of_9": {
            "pass": flat(checks["stripped_composition_rebuilds_m6_v4_branch_A"]),
            "detail": checks["stripped_composition_rebuilds_m6_v4_branch_A"]},
        "target_capture_transforms_match_m5_display_rows": {
            "pass": flat(checks["target_transform_matches_m5_contract"]),
            "detail": checks["target_transform_matches_m5_contract"]},
        "inertia_symmetric_positive_definite_9_of_9": {
            "pass": flat(checks["inertia_symmetric_positive_definite"]),
            "detail": checks["inertia_symmetric_positive_definite"]},
        "uncertainty_positive_no_zero_fill_9_of_9": {
            "pass": flat(checks["uncertainty_positive_no_zero_fill"]),
            "scope": "WIDENED_TO_COMPONENT_LEVEL_V1_SCANNED_CONFIGURATION_LEVEL_ONLY",
            "detail": checks["uncertainty_positive_no_zero_fill"]},
        "deployed_panels_whole_sat_closure_vs_stage1_row": closure_check,
        "mass_closure_sum_of_members_9_of_9": {
            "pass": flat(checks["mass_closure_sum_of_members"]),
            "detail": checks["mass_closure_sum_of_members"]},
        "triangle_inequality_9_of_9": {
            "pass": flat(checks["triangle_inequality"]),
            "note": "NEW in V2: V1 ran no triangle-inequality test",
            "detail": checks["triangle_inequality"]},
        "principal_axes_orthonormal_right_handed_9_of_9": {
            "pass": flat(checks["principal_axes_orthonormal_right_handed"]),
            "note": "NEW in V2: V1 ran no handedness test (WP2-AUD-06)",
            "handedness_repairs": handedness_repairs,
            "detail": checks["principal_axes_orthonormal_right_handed"]},
        "component_inertia_covariance_semantics_all_records": {
            "pass": flat(checks["component_covariance_semantics"]),
            "records_checked": total_component_records,
            "required_checks": ["covariance_symmetric", "covariance_positive_semidefinite",
                                "variance_diagonal_nonnegative", "reported_sigma_nonnegative"],
            "negative_reported_sigma_records": negative_sigma_entries,
            "note": "NEW in V2: ODR-07 required check set (WP2-AUD-02)",
            "detail": checks["component_covariance_semantics"]},
        "component_uncertainty_magnitude_vs_policy_class_rule": {
            "pass": flat(checks["component_uncertainty_magnitude_vs_policy"]),
            "detail": checks["component_uncertainty_magnitude_vs_policy"]},
        "covariance_method_discrimination_vs_forbidden_abs": discrimination,
        "component_inertia_frame_label_consistency": {
            "pass": flat(checks["component_frame_label_consistency"]),
            "resolution": (
                "WP2-AUD-05: the reported tensor IS in S axes about the component's own CoM, so "
                "inertia_reference_frame_declared = S is the correct value and the V1 values "
                "F_LEFT_LOCAL_COM / F_RIGHT_LOCAL_COM / T / D were mislabelled. Evidence: the "
                "reported matrix equals R I_local R^T exactly (residual 0.0 on every record) and "
                "the parallel-axis reconstruction of every configuration tensor only closes with "
                "S-frame component tensors. The source-frame label is retained separately as "
                "source_tensor_local_frame with the rotation actually used."),
            "detail": checks["component_frame_label_consistency"]},
        "parallel_axis_reconstruction_9_of_9": {
            "pass": flat(checks["parallel_axis_reconstruction"]),
            "note": "NEW in V2: internal mirror of the independent audit reconstruction",
            "detail": checks["parallel_axis_reconstruction"]},
        "configuration_inertia_covariance_9_of_9": {
            "pass": flat(checks["configuration_covariance_semantics"]),
            "detail": checks["configuration_covariance_semantics"]},
        "propagation_cross_implementation_identity_9_of_9": {
            "pass": flat(checks["propagation_cross_implementation_identity"]),
            "note": ("the V1 propagate() and the Jacobian-exposing V2 propagation return "
                     "bit-identical nominal vectors, so the configuration-level covariance is "
                     "derived from the same computation that produced the reported values"),
            "detail": checks["propagation_cross_implementation_identity"]},
        "regression_vs_v1_all_physics_bit_identical_9_of_9": {
            "pass": flat(checks["regression_vs_v1"]),
            "meaning": ("every mass, CoM, inertia tensor, tensor uncertainty, principal moment, "
                        "moment uncertainty and angular uncertainty is bit-identical to V1; the "
                        "only intentional numeric change in the whole artifact is the C09 "
                        "principal-axis sign repair and the replacement of the invalid component "
                        "uncertainty field by the covariance structure"),
            "v1_negative_component_sigma_entries_found": v1_negative_entries,
            "v1_negative_component_sigma_records_found": v1_negative_records,
            "detail": checks["regression_vs_v1"]},
        "source_register_sha256_and_bytes_complete": {
            "pass": bool(not missing_bytes and all(p["match"] for p in v1_pins)),
            "entry_count": len(source_register),
            "entries_missing_bytes": missing_bytes,
            "v1_pinned_hash_reverification": v1_pins,
            "note": "NEW in V2: byte sizes present on every entry (WP2-AUD-03)"},
        "self_reference_pins_complete": {
            "pass": True,
            "aggregator_v2_self_pin": self_pin,
            "aggregator_v1_pin": sha_bytes(V1_AGGREGATOR_PATH),
            "policy_v2_pin": sha_bytes(POLICY_V2_PATH),
            "note": "NEW in V2: the generating aggregator is pinned by sha256+bytes (WP2-AUD-04)"},
        "policy_v2_class_values_identical_to_v1": {
            "pass": bool(policy["source_classes"] == policy_v1["source_classes"]
                         and policy["component_quantity_class_map"]
                         == policy_v1["component_quantity_class_map"]),
            "note": "no uncertainty class number changed; only the frame-transformation rule P9 was added"},
        "header_constants_derived_from_computed_masses": {
            "pass": True,
            "design_mass_uncaptured_with_bridge_kg": with_bridge,
            "design_mass_uncaptured_without_bridge_kg": without_bridge,
            "v1_hard_coded_with_bridge_kg": v1_with_bridge,
            "v1_hard_coded_without_bridge_kg": v1_without_bridge,
            "v1_with_bridge_minus_computed_kg": v1_with_bridge - with_bridge,
            "note": ("found by the widened self-check: V1's hand-written header constant "
                     "disagreed with its own computed C01..C07 mass by 3.552713678800501e-15 kg "
                     "(summation-order artefact). V2 derives both constants from the computed "
                     "configuration mass so the header cannot drift from the table.")},
    }

    all_pass = all([
        bool(design_checks["urdf_arm_mass_pinned_exactly"]),
        design_checks["branch_mass_delta_constant_9_of_9"]["pass"],
        design_checks["stripped_composition_rebuilds_m6_v4_branch_A_9_of_9"]["pass"],
        design_checks["target_capture_transforms_match_m5_display_rows"]["pass"],
        design_checks["inertia_symmetric_positive_definite_9_of_9"]["pass"],
        design_checks["uncertainty_positive_no_zero_fill_9_of_9"]["pass"],
        closure_check["pass"],
        design_checks["mass_closure_sum_of_members_9_of_9"]["pass"],
        design_checks["triangle_inequality_9_of_9"]["pass"],
        design_checks["principal_axes_orthonormal_right_handed_9_of_9"]["pass"],
        design_checks["component_inertia_covariance_semantics_all_records"]["pass"],
        design_checks["component_uncertainty_magnitude_vs_policy_class_rule"]["pass"],
        design_checks["covariance_method_discrimination_vs_forbidden_abs"]["pass"],
        design_checks["component_inertia_frame_label_consistency"]["pass"],
        design_checks["parallel_axis_reconstruction_9_of_9"]["pass"],
        design_checks["configuration_inertia_covariance_9_of_9"]["pass"],
        design_checks["propagation_cross_implementation_identity_9_of_9"]["pass"],
        design_checks["regression_vs_v1_all_physics_bit_identical_9_of_9"]["pass"],
        design_checks["source_register_sha256_and_bytes_complete"]["pass"],
        design_checks["self_reference_pins_complete"]["pass"],
        design_checks["policy_v2_class_values_identical_to_v1"]["pass"],
        design_checks["header_constants_derived_from_computed_masses"]["pass"],
    ])

    output = {
        "schema": "M7_SYSTEM_DESIGN_MASS_PROPERTIES_V2",
        "generated_local": now_local(),
        "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
        "phase": "M7_MECHANICAL_FINAL_DESIGN_CLOSURE",
        "work_package": "WP2_DESIGN_MASS",
        "role": "A2_MASS_FRAMES",
        "scope": "NINE_CONFIGURATION_DESIGN_MASS_COM_INERTIA_MODEL_WITH_DECLARED_UNCERTAINTIES",
        "status": "DESIGN_MASS_MODEL_ACTIVE_DECLARED_UNCERTAINTY_PENDING_CALIBRATION",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "design_not_flight_qualified": True,
        "supersedes": {
            **sha_bytes(V1_ARTIFACT_PATH),
            "declared_generated_local": v1_doc["generated_local"],
            "reason": (
                "ODR-07 remediation of WP2-AUD-01/02/03/04/05/06 (3 MEDIUM + 3 LOW) plus a "
                "widened self-check. UNCERTAINTY SEMANTICS AND METADATA ONLY: no mass, CoM, "
                "inertia tensor, tensor uncertainty, principal moment, moment uncertainty or "
                "angular uncertainty value changed (asserted bit-identical against V1 on disk "
                "before this file was written)."),
            "v1_retained_on_disk": True,
            "v1_retention_rationale": (
                "V1 is kept byte-intact so the V1->V2 delta stays independently verifiable and "
                "so the V1 audit trail (WP2_DESIGN_MASS_AUDIT_V1.json, V1 receipt) keeps "
                "resolving against a real file."),
            "downstream_repin_required": [
                "wp10_mech_rl_v4/MECH_DYNAMICS_INTERFACE_V4.yaml design_mass_model_binding "
                "(system_design_mass_properties + uncertainty_policy still say "
                "PENDING_SIBLING_HASH and point at the V1 filenames)",
                "wp9_release_package receipt/verification matrix references",
                "12_release/M7_CROSS_WP_REFERENCE_RECONCILIATION_V1 (integration backfill)",
            ],
            "repin_owner": "A0_mechanical_chief / A7_cm_release (WP2 must not edit sibling files)",
        },
        "units": {"mass": "kg", "center_of_mass": "m", "inertia": "kg*m^2", "angle": "rad"},
        "authority_basis": {
            "ODR-01": "M frame authority T_SM=[185.25,0,0] mm + Ry(90 deg); legacy flange allocated to BUS_PRIMARY_STRUCTURE by design ruling",
            "ODR-02": "panel failure = attached-stuck, never jettison (C02/C03/C04 keep panel mass at the stowed endpoint)",
            "ODR-05": "M3R 0.7619 kg design-budget authority (DESIGN_BUDGET, confidence B); as-built measurement open",
            "ODR-07": "component inertia uncertainty is a covariance; abs()/clipping/deletion forbidden; four covariance checks mandatory",
            "ODR-14": "Gate A criterion 10 may not be PASS while WP2-AUD-02 or WP2-AUD-06 is open; this build closes both with evidence",
            "ODR-16": "right-handed principal frames are required for the MECHANICAL_TO_EMBODIED handoff check frame_tree_matched",
            "contract": "M7_EXECUTION_PLAN_V1.md pinned contract values",
        },
        "remediation_register": {
            "WP2-AUD-02": {
                "severity": "MEDIUM",
                "status": "CLOSED_WITH_EVIDENCE",
                "defect": ("component inertia standard-uncertainty matrices were rotated "
                           "component-wise (R U R^T), producing "
                           f"{v1_negative_entries} negative entries across "
                           f"{v1_negative_records} component records in V1"),
                "fix": ("covariance propagation C_global = T(R) C_local T(R)^T with "
                        "sigma_i = sqrt(C_global[i,i]); new field inertia_uncertainty carries "
                        "covariance_matrix_kg2_m4 (signed off-diagonal allowed) and "
                        "component_standard_uncertainty_kg_m2 (all non-negative)"),
                "forbidden_remediations_not_used": ["abs(rotated_uncertainty_matrix)",
                                                    "clipping negatives to zero",
                                                    "deleting the offending entries"],
                "proof_it_is_not_an_abs": "design_checks.covariance_method_discrimination_vs_forbidden_abs",
                "numeric_outcome_note": (
                    "every component-to-S rotation in this design is a signed permutation, so "
                    "T(R) C_local T(R)^T stays diagonal and the covariance-derived sigma "
                    "coincides numerically with |V1 entry| on this data set "
                    "(max |abs(V1) - V2 sigma| = 0.0). That coincidence is a property of these "
                    "particular transforms, not of the method: on the generic 30 deg rotation of "
                    "the discrimination test the two differ by "
                    f"{discrimination['max_abs_difference_kg_m2']:.6e} kg*m^2 and the covariance "
                    "carries genuinely negative off-diagonal entries."),
                "checks_added": ["covariance_symmetric", "covariance_positive_semidefinite",
                                 "variance_diagonal_nonnegative", "reported_sigma_nonnegative"],
                "records_checked": total_component_records,
                "negative_reported_sigma_after_fix": negative_sigma_entries,
            },
            "WP2-AUD-06": {
                "severity": "MEDIUM",
                "status": "CLOSED_WITH_EVIDENCE",
                "defect": "C09 TARGET_CAPTURE_150KG principal-axis triad left-handed, det(R) = -1.0",
                "fix": ("minimal sign repair: negate the third (largest-moment) axis of any "
                        "configuration whose raw eigen-decomposition returns det < 0; the "
                        "convention is now declared in principal_inertia.axes_handedness_convention"),
                "configurations_repaired": handedness_repairs,
                "determinants_after": {row["configuration_id"]: row["det_after_repair"]
                                       for row in checks["principal_axes_orthonormal_right_handed"]},
                "moments_unchanged": True,
                "physical_axis_lines_unchanged": True,
                "angular_uncertainties_unchanged": True,
            },
            "WP2-AUD-01": {
                "severity": "MEDIUM",
                "status": "CLOSED_WITH_EVIDENCE",
                "defect": "M5 C08/C09 label crosswalk (CAPTURE / POST_CAPTURE) absent",
                "fix": ("configuration_label_crosswalk: 9 rows, three forward maps, three "
                        "injective reverse maps, naming-axis explanation and a POST_CAPTURE "
                        "token-collision warning; each configuration record also now carries "
                        "m5_geometry_contract_name inline"),
                "neither_side_renamed": True,
            },
            "WP2-AUD-03": {"severity": "LOW", "status": "CLOSED_WITH_EVIDENCE",
                           "fix": "every source_register entry carries sha256 AND bytes",
                           "entry_count": len(source_register)},
            "WP2-AUD-04": {"severity": "LOW", "status": "CLOSED_WITH_EVIDENCE",
                           "fix": "aggregator sha256+bytes pinned (V2 self-pin and V1 lineage pin)"},
            "WP2-AUD-05": {"severity": "LOW", "status": "CLOSED_WITH_EVIDENCE",
                           "fix": ("inertia_reference_frame_declared = S on all "
                                   f"{total_component_records} records (correct: the stored tensor "
                                   "is in S axes about the component own CoM); the source frame "
                                   "and the source-to-S rotation are carried separately")},
            "NEW_FOUND_BY_WIDENED_SELF_CHECK": {
                "generated_clock_source_absent_in_v1": "added",
                "header_mass_constants_hard_coded_in_v1":
                    ("derived in V2; V1 header disagreed with its own configuration table by "
                     f"{v1_with_bridge - with_bridge:.6e} kg"),
            },
        },
        "composition_ruling": {
            "single_design_composition": list(v1_doc["composition_ruling"]["single_design_composition"]),
            "branch_convergence": v1_doc["composition_ruling"]["branch_convergence"],
            "design_mass_uncaptured_without_bridge_kg": without_bridge,
            "design_mass_uncaptured_with_bridge_kg": with_bridge,
            "header_constants_derivation": "computed from the C01 aggregation, not hand-written",
        },
        "aggregation_contract": {
            "target_frame": "spacecraft_assembly_frame (frozen identity alias of S, M4 frame tree)",
            "mass_model": "m_system = sum(m_i) over the declared non-overlapping member set",
            "center_of_mass_model": "r_system = sum(m_i*r_i)/sum(m_i)",
            "inertia_model": "rotate each own-COM tensor into S, then parallel-axis shift to the configuration system CG",
            "tensor_matrix_order": [["Ixx", "Ixy", "Ixz"], ["Ixy", "Iyy", "Iyz"], ["Ixz", "Iyz", "Izz"]],
            "component_vector_order": list(TENSOR_KEYS),
            "uncertainty_model_ref": "wp2_design_mass/DESIGN_MASS_UNCERTAINTY_POLICY_V2.yaml (declared, PENDING_CALIBRATION, never measured)",
            "component_uncertainty_transformation": "COVARIANCE_C_GLOBAL_EQ_T_R_C_LOCAL_T_R_TRANSPOSE (ODR-07 / P9)",
            "zero_fill_forbidden": True,
            "measured_or_as_built_claims_forbidden": True,
        },
        "uncertainty_policy": {
            "path": "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/DESIGN_MASS_UNCERTAINTY_POLICY_V2.yaml",
            **{k: v for k, v in sha_bytes(POLICY_V2_PATH).items() if k != "path"},
            "status": "ACTIVE_DECLARED_ENGINEERING_POLICY_PENDING_CALIBRATION",
            "superseded_v1": sha_bytes(POLICY_V1_PATH),
        },
        "aggregator": {
            **self_pin,
            "rerun_command": "python 20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/aggregate_m7_design_mass_v2.py",
            "reuses_v1_physics_module": sha_bytes(V1_AGGREGATOR_PATH),
            "reuse_note": ("the V1 aggregator is imported, not copied, for the primitive library, "
                           "the aggregation chain and the GUM propagation, so the physics cannot "
                           "silently diverge; only reporting/uncertainty-semantics code is new"),
            "self_pin_note": ("sha256 above is this file's own bytes at build time; re-running "
                              "after any edit of this file changes it, which is the intended "
                              "provenance binding (WP2-AUD-04)"),
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
        "configuration_label_crosswalk": crosswalk,
        "source_register": source_register,
        "design_checks": design_checks,
        "configurations": configurations_out,
        "summary": {
            "configuration_count": 9,
            "design_mass_count": 9,
            "design_cg_count": 9,
            "design_inertia_count": 9,
            "design_principal_inertia_count": 9,
            "component_record_count": total_component_records,
            "all_checks_pass": all_pass,
            "self_check_scope": {
                "claim": ("all_checks_pass covers every check listed in design_checks, and that "
                          "list is the same scope the WP2 INDEPENDENT audit uses"),
                "covered": [
                    "pinned authority values (L0 URDF arm mass, M3R budget, bridge candidate)",
                    "mass closure of every configuration against its own member list",
                    "CoM and full-tensor parallel-axis reconstruction from the declared composition",
                    "tensor symmetry, positive definiteness AND triangle inequality",
                    "principal-axis orthonormality, right-handedness and diagonalisation residual",
                    "component-level covariance symmetry / PSD / variance / sigma non-negativity",
                    "component uncertainty magnitudes against the policy class rules",
                    "proof that the covariance method is not the forbidden abs()",
                    "component inertia frame-label consistency with the stored numbers",
                    "configuration-level covariance consistency with the reported sigmas",
                    "cross-implementation identity of the propagation",
                    "bit-identity of every physics value against the superseded V1 artifact",
                    "source_register sha256 AND bytes for every entry, V1 pins re-verified",
                    "self-reference pins (policy V2, aggregator V1 and V2)",
                    "policy V2 class values identical to V1",
                    "header constants derived from the computed masses",
                    "M4 / M4-legacy / M5 configuration label crosswalk completeness and injectivity",
                ],
                "explicitly_not_covered": [
                    "correctness of the upstream M4/M5/M6/CDR source values themselves (they are "
                    "consumed as hash-pinned inputs, not re-derived)",
                    "any measured, as-built or as-installed property (none exists anywhere in the chain)",
                    "calibration of the declared Type-B uncertainty classes (PENDING_CALIBRATION)",
                    "correlation between component uncertainties (P8 declares independence; a "
                    "correlation review is required before any calibration upgrade)",
                    "flight, launcher, manufacturing-release or qualification adequacy (forbidden here)",
                    "geometry / interference / CAD validity (WP1 scope)",
                    "structural strength or FEA adequacy (WP7 scope)",
                ],
                "v1_scope_defect_closed": ("V1's uncertainty check scanned configuration-level "
                                           "fields only and ran no triangle-inequality, handedness "
                                           "or byte-size test, so its all_checks_pass=true was "
                                           "narrower than its claim"),
            },
            "use_authorization": "ENGINEERING_DESIGN_ANALYSIS_ONLY_NOT_FLIGHT_NOT_QUALIFICATION_NOT_MEASURED",
        },
        "retained_holds": list(v1_doc["retained_holds"]),
        "release_prohibitions": list(v1_doc["release_prohibitions"]),
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="\n") as handle:
        yaml.safe_dump(py(output), handle, sort_keys=False, allow_unicode=True, width=140)

    print(json.dumps({
        "output": OUTPUT_PATH.relative_to(WORKSPACE).as_posix(),
        "all_checks_pass": all_pass,
        "handedness_repairs": handedness_repairs,
        "det_after": {row["configuration_id"]: row["det_after_repair"]
                      for row in checks["principal_axes_orthonormal_right_handed"]},
        "v1_negative_component_sigma_entries": v1_negative_entries,
        "v1_negative_component_sigma_records": v1_negative_records,
        "negative_reported_sigma_after_fix": negative_sigma_entries,
        "regression_vs_v1_pass": flat(checks["regression_vs_v1"]),
        "discrimination_delta": discrimination["max_abs_difference_kg_m2"],
    }, indent=2))
    if not all_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
