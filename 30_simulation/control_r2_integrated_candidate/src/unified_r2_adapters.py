"""Safe static adapters for Unified R2 control predevelopment.

The adapters in this module are deliberately diagnostic-only.  They never call
the Unified R2 backend ``advance`` method, never infer prismatic constraint
reactions, and never inherit E23 or Round4 release credit.
"""
from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Mapping, Sequence
import xml.etree.ElementTree as ET

import numpy as np

from predevelopment import canonical_sha256, load_json_strict


def _pin_path(repo_root: Path, config: Mapping[str, Any], pin_id: str) -> Path:
    pin = next(item for item in config["source_pins"] if item["id"] == pin_id)
    return repo_root / pin["path"]


def _install_unified_r2_imports(repo_root: Path) -> None:
    rebind = (
        repo_root
        / "30_simulation"
        / "sim_13_physics_gated_embodied_grasping"
        / "v2_system_rebind"
    )
    paths = (rebind / "runtime_fail_closed_backends_v2", rebind)
    for path in reversed(paths):
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)


def validate_locked_prismatic_state(
    qP_m: Sequence[float], qP_limits_m: Sequence[Sequence[float]]
) -> np.ndarray:
    qP = np.asarray(qP_m, dtype=float)
    limits = np.asarray(qP_limits_m, dtype=float)
    if qP.shape != (2,) or limits.shape != (2, 2) or not np.all(np.isfinite(qP)):
        raise ValueError("LOCKED_PRISMATIC_STATE_MALFORMED")
    if not np.all(np.isfinite(limits)) or np.any(limits[:, 0] > limits[:, 1]):
        raise ValueError("LOCKED_PRISMATIC_LIMITS_MALFORMED")
    if np.any(qP < limits[:, 0]) or np.any(qP > limits[:, 1]):
        raise ValueError("LOCKED_PRISMATIC_STATE_OUTSIDE_URDF_LIMITS_FAIL_CLOSED")
    return qP


def validate_joint_state_limits(
    q: Sequence[float],
    limits: Sequence[Sequence[float]],
    joint_names: Sequence[str],
) -> tuple[np.ndarray, np.ndarray]:
    """Validate a complete joint state against inclusive hash-bound URDF limits."""
    state = np.asarray(q, dtype=float)
    bounds = np.asarray(limits, dtype=float)
    names = list(joint_names)
    if (
        state.ndim != 1
        or state.size == 0
        or bounds.shape != (state.size, 2)
        or len(names) != state.size
    ):
        raise ValueError("JOINT_STATE_LIMIT_VECTOR_SHAPE_MISMATCH")
    if not np.all(np.isfinite(state)) or not np.all(np.isfinite(bounds)):
        raise ValueError("JOINT_STATE_OR_URDF_LIMIT_NONFINITE")
    if np.any(bounds[:, 0] > bounds[:, 1]):
        raise ValueError("URDF_JOINT_LIMIT_ORDER_INVALID")
    if np.any(state < bounds[:, 0]) or np.any(state > bounds[:, 1]):
        raise ValueError("JOINT_STATE_OUTSIDE_URDF_LIMITS_FAIL_CLOSED")
    margins = np.column_stack((state - bounds[:, 0], bounds[:, 1] - state))
    return state, margins


def _unified_r2_static_once(repo_root: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    _install_unified_r2_imports(repo_root)
    from sim13_v2_backends.dynamics_backend import UnifiedR2DynamicsBackend

    cfg = config["unified_r2_static_probe"]
    backend = UnifiedR2DynamicsBackend(project_root=repo_root)
    urdf_root = ET.parse(
        _pin_path(repo_root, config, "unified_r2_urdf_candidate")
    ).getroot()
    urdf_movable: dict[str, dict[str, Any]] = {}
    for joint in urdf_root.findall("joint"):
        joint_type = joint.attrib.get("type")
        if joint_type not in {"revolute", "continuous", "prismatic"}:
            continue
        limit = joint.find("limit")
        urdf_movable[joint.attrib["name"]] = {
            "type": joint_type,
            "lower": None if limit is None or "lower" not in limit.attrib else float(limit.attrib["lower"]),
            "upper": None if limit is None or "upper" not in limit.attrib else float(limit.attrib["upper"]),
        }
    frame_tree_text = _pin_path(
        repo_root, config, "unified_r2_system_frame_tree"
    ).read_text(encoding="utf-8")
    frame_tree_contract_ok = all(
        marker in frame_tree_text
        for marker in (
            "schema: UNIFIED_R2_SYSTEM_FRAME_TREE_V2",
            "root_link: spacecraft_bus",
            "S_SPACECRAFT_BUS:",
            "link: spacecraft_bus",
            "SOLAR_R2_ROOT_L:",
            "SOLAR_R2_ROOT_R:",
        )
    )
    q6 = np.asarray(cfg["q6_rad"], dtype=float)
    expected_joint_order = list(cfg["joint_order"])
    if set(urdf_movable) != set(expected_joint_order):
        raise ValueError("UNIFIED_R2_URDF_MOVABLE_JOINT_SET_MISMATCH")
    urdf_joint_types = [urdf_movable[name]["type"] for name in expected_joint_order]
    urdf_q8_limits = np.asarray(
        [
            [urdf_movable[name]["lower"], urdf_movable[name]["upper"]]
            for name in expected_joint_order
        ],
        dtype=float,
    )
    urdf_qP_limits = urdf_q8_limits[-2:, :]
    declared_qP_limits = np.asarray(cfg["qP_limits_m"], dtype=float)
    qP_limits_match_urdf = bool(np.array_equal(declared_qP_limits, urdf_qP_limits))
    qP = validate_locked_prismatic_state(cfg["qP_m"], urdf_qP_limits)
    qdot6 = np.asarray(cfg["qdot6_rad_s"], dtype=float)
    qdotP = np.asarray(cfg["qdotP_m_s"], dtype=float)
    if q6.shape != (6,) or qdot6.shape != (6,) or qdotP.shape != (2,):
        raise ValueError("UNIFIED_R2_STATIC_VECTOR_SHAPE_MISMATCH")
    if not np.all(np.isfinite(np.concatenate((q6, qdot6, qdotP)))):
        raise ValueError("UNIFIED_R2_STATIC_VECTOR_NONFINITE")
    if np.any(qdotP != 0.0):
        raise ValueError("LOCKED_PRISMATIC_RATE_MUST_BE_EXACT_ZERO")

    q8 = np.concatenate((q6, qP))
    q8, q8_limit_margins = validate_joint_state_limits(
        q8, urdf_q8_limits, expected_joint_order
    )
    qdot8 = np.concatenate((qdot6, qdotP))
    coordinate_units = ["rad"] * 6 + ["m"] * 2
    joint_limit_audit = [
        {
            "joint": name,
            "unit": coordinate_units[index],
            "q": float(q8[index]),
            "lower": float(urdf_q8_limits[index, 0]),
            "upper": float(urdf_q8_limits[index, 1]),
            "lower_margin": float(q8_limit_margins[index, 0]),
            "upper_margin": float(q8_limit_margins[index, 1]),
            "minimum_margin": float(np.min(q8_limit_margins[index, :])),
            "inside_inclusive_limits": True,
        }
        for index, name in enumerate(expected_joint_order)
    ]
    blocks = backend.tree.mass_matrix_blocks(q8)
    Hbb = np.asarray(blocks.Hbb, dtype=float)
    Hbm = np.asarray(blocks.Hbm, dtype=float)
    reduced8 = np.asarray(backend.reduced_mass_matrix(q8), dtype=float)
    reduced6 = reduced8[:6, :6]
    connection6 = -np.linalg.solve(Hbb, Hbm[:, :6])
    base_twist = connection6 @ qdot6
    momentum = backend.tree.momentum(q8, base_twist, qdot8)
    linear = np.asarray(momentum.linear_root_kg_m_s, dtype=float)
    angular = np.asarray(momentum.angular_about_root_kg_m2_s, dtype=float)

    Hbb_symmetry = float(np.max(np.abs(Hbb - Hbb.T)))
    reduced8_symmetry = float(np.max(np.abs(reduced8 - reduced8.T)))
    reduced6_symmetry = float(np.max(np.abs(reduced6 - reduced6.T)))
    Hbb_min_eigenvalue = float(np.min(np.linalg.eigvalsh(Hbb)))
    reduced8_min_eigenvalue = float(np.min(np.linalg.eigvalsh(reduced8)))
    reduced6_min_eigenvalue = float(np.min(np.linalg.eigvalsh(reduced6)))
    linear_norm = float(np.linalg.norm(linear))
    angular_norm = float(np.linalg.norm(angular))
    checks = {
        "backend_dof_is_8": backend.dof == 8,
        "backend_root_is_spacecraft_bus_S": backend.tree.root_link
        == "spacecraft_bus",
        "system_frame_tree_contract_bound": frame_tree_contract_ok,
        "joint_order_exact": list(backend.tree.movable_joint_names)
        == expected_joint_order,
        "joint_types_exact_6R2P": urdf_joint_types
        == ["revolute"] * 6 + ["prismatic"] * 2,
        "all_8_joint_limits_finite": bool(np.all(np.isfinite(urdf_q8_limits))),
        "q8_inside_URDF_limits": True,
        "qP_limits_match_URDF": qP_limits_match_urdf,
        "qP_inside_URDF_limits": True,
        "qdotP_exact_zero": bool(np.all(qdotP == 0.0)),
        "Hbb_shape_6x6": Hbb.shape == (6, 6),
        "Hbm_shape_6x8": Hbm.shape == (6, 8),
        "mechanical_connection_locked6_shape_6x6": connection6.shape == (6, 6),
        "reduced_mass_full8_shape_8x8": reduced8.shape == (8, 8),
        "reduced_mass_locked6_shape_6x6": reduced6.shape == (6, 6),
        "Hbb_symmetric": Hbb_symmetry <= float(cfg["symmetry_abs_max"]),
        "reduced8_symmetric": reduced8_symmetry <= float(cfg["symmetry_abs_max"]),
        "reduced6_symmetric": reduced6_symmetry <= float(cfg["symmetry_abs_max"]),
        "Hbb_positive_definite": Hbb_min_eigenvalue
        > float(cfg["positive_eigenvalue_min"]),
        "reduced8_positive_definite": reduced8_min_eigenvalue
        > float(cfg["positive_eigenvalue_min"]),
        "reduced6_positive_definite": reduced6_min_eigenvalue
        > float(cfg["positive_eigenvalue_min"]),
        "linear_momentum_residual_bounded_separately": linear_norm
        <= float(cfg["linear_momentum_residual_max_kg_m_s"]),
        "angular_momentum_residual_bounded_separately": angular_norm
        <= float(cfg["angular_momentum_residual_max_kg_m2_s"]),
    }
    return {
        "schema": "CTRL_R2_UNIFIED_8DOF_STATIC_PROBE_INSTANCE_V1",
        "scope": cfg["scope"],
        "model": "HASH_PINNED_UNIFIED_R2_8DOF_RUNTIME_BACKEND",
        "root_frame": {
            "backend_root_link": backend.tree.root_link,
            "semantic_frame": "S_SPACECRAFT_BUS",
            "frame_tree_contract": "UNIFIED_R2_SYSTEM_FRAME_TREE_V2",
        },
        "joint_order": list(backend.tree.movable_joint_names),
        "coordinate_units": coordinate_units,
        "q8_mixed_rad_m": q8.tolist(),
        "qdot8_mixed_rad_s_m_s": qdot8.tolist(),
        "urdf_joint_limit_audit": {
            "source": "HASH_PINNED_UNIFIED_R2_URDF",
            "policy": "INCLUSIVE_LOWER_UPPER__FAIL_CLOSED",
            "all_8_inside": True,
            "minimum_margin_any_joint_mixed_rad_m": float(
                np.min(q8_limit_margins)
            ),
            "joints": joint_limit_audit,
        },
        "locked_prismatic_contract": {
            "qP_m": qP.tolist(),
            "qP_limits_m": urdf_qP_limits.tolist(),
            "qP_limits_source": "HASH_PINNED_UNIFIED_R2_URDF",
            "declared_config_limits_match_URDF": qP_limits_match_urdf,
            "qdotP_m_s": qdotP.tolist(),
            "constraint_reaction_solver": "NOT_IMPLEMENTED__TORQUE_LEVEL_PROPAGATION_HOLD",
        },
        "mass_blocks": {
            "full_shape": list(blocks.full.shape),
            "Hbb_shape": list(Hbb.shape),
            "Hbm_shape": list(Hbm.shape),
            "Hmm_shape": list(blocks.Hmm.shape),
            "Hbb_symmetry_max_abs": Hbb_symmetry,
            "Hbb_min_eigenvalue": Hbb_min_eigenvalue,
        },
        "locked_6R_adapter": {
            "mechanical_connection_shape": list(connection6.shape),
            "mechanical_connection": connection6.tolist(),
            "reduced_mass_full8_shape": list(reduced8.shape),
            "reduced_mass_locked6_shape": list(reduced6.shape),
            "reduced_mass_full8_symmetry_max_abs": reduced8_symmetry,
            "reduced_mass_locked6_symmetry_max_abs": reduced6_symmetry,
            "reduced_mass_full8_min_eigenvalue": reduced8_min_eigenvalue,
            "reduced_mass_locked6_min_eigenvalue": reduced6_min_eigenvalue,
        },
        "zero_momentum_diagnostic": {
            "base_twist_S_mixed_m_s_rad_s": base_twist.tolist(),
            "linear_momentum_residual_S_kg_m_s": linear.tolist(),
            "linear_momentum_residual_norm_kg_m_s": linear_norm,
            "angular_momentum_residual_about_S_N_m_s": angular.tolist(),
            "angular_momentum_residual_norm_N_m_s": angular_norm,
            "linear_and_angular_residuals_not_mixed": True,
        },
        "execution_guards": {
            "backend_advance_called": False,
            "contact_called": False,
            "collision_query_called": False,
            "path_search_called": False,
        },
        "checks": checks,
        "pass": all(checks.values()),
    }


def run_unified_r2_static_probe(
    repo_root: Path, config: Mapping[str, Any]
) -> dict[str, Any]:
    first = _unified_r2_static_once(repo_root, config)
    replay = _unified_r2_static_once(repo_root, config)
    first_hash = canonical_sha256(first)
    replay_hash = canonical_sha256(replay)
    return {
        "schema": "CTRL_R2_UNIFIED_8DOF_STATIC_PROBE_V1",
        "scope": "STATIC_DIAGNOSTIC_ONLY__NO_ADVANCE_NO_CONTACT_NO_CONTROL_PERFORMANCE_CREDIT",
        "first": first,
        "determinism": {
            "first_canonical_sha256": first_hash,
            "replay_canonical_sha256": replay_hash,
            "bitwise_canonical_equal": first_hash == replay_hash,
        },
        "pass": first["pass"] and first_hash == replay_hash,
        "next_stage_authorized": False,
        "release_credit": False,
    }


def _operator_screen(
    eta: np.ndarray,
    arrays: Mapping[str, np.ndarray],
    limits: Mapping[str, float],
    operator_limit_map: Mapping[str, str],
) -> tuple[list[dict[str, Any]], bool]:
    checks: list[dict[str, Any]] = []
    for operator_name, limit_name in operator_limit_map.items():
        operator = np.asarray(arrays[operator_name], dtype=float)
        value = float(np.max(np.abs(operator @ eta)))
        limit = float(limits[limit_name])
        checks.append(
            {
                "operator": operator_name,
                "operator_shape": list(operator.shape),
                "limit_name": limit_name,
                "max_abs_response": value,
                "limit": limit,
                "pass": value <= limit,
            }
        )
    return checks, all(item["pass"] for item in checks)


def flexibility_static_screen_once(
    repo_root: Path,
    config: Mapping[str, Any],
    *,
    eta_override_by_wing: Mapping[str, Sequence[float]] | None = None,
) -> dict[str, Any]:
    cfg = config["flex_static_screen"]
    rom_contract = load_json_strict(
        _pin_path(repo_root, config, "round4_seven_mode_rom")
    )
    envelope = load_json_strict(
        _pin_path(repo_root, config, "round4_flex_validity_envelope")
    )
    round4_gate = load_json_strict(
        _pin_path(repo_root, config, "round4_hf_rom_gate")
    )
    wing_order = tuple(cfg["wing_order"])
    corner_order = tuple(cfg["corner_order"])
    if wing_order != ("LEFT", "RIGHT"):
        raise ValueError("FLEX_WING_ORDER_MUST_BE_LEFT_THEN_RIGHT")
    if corner_order != ("LOW", "NOMINAL", "HIGH"):
        raise ValueError("FLEX_CORNER_ORDER_MUST_BE_LOW_NOMINAL_HIGH")

    acceleration = np.asarray(cfg["base_linear_acceleration_S_m_s2"], dtype=float)
    angular_acceleration = np.asarray(
        cfg["base_angular_acceleration_S_rad_s2"], dtype=float
    )
    if acceleration.shape != (3,) or angular_acceleration.shape != (3,):
        raise ValueError("FLEX_DIAGNOSTIC_ACCELERATION_SHAPE_MISMATCH")
    if float(np.linalg.norm(acceleration)) <= 0.0 or float(
        np.linalg.norm(angular_acceleration)
    ) <= 0.0:
        raise ValueError("FLEX_DIAGNOSTIC_ACCELERATIONS_MUST_BE_NONZERO")

    with np.load(
        _pin_path(repo_root, config, "round4_hf_rom_numerical_data"),
        allow_pickle=False,
    ) as source:
        arrays = {key: np.asarray(source[key]).copy() for key in source.files}

    mode_order = list(cfg["mode_order_per_wing"])
    limits = envelope["quantitative_linearity_contract"]["limits"]
    operator_limit_map = cfg["operator_limit_map"]
    M7 = np.asarray(arrays["Mrom"], dtype=float)
    M14 = np.zeros((14, 14), dtype=float)
    M14[:7, :7] = M7
    M14[7:, 7:] = M7
    gamma_by_wing: dict[str, dict[str, np.ndarray]] = {}
    for wing, suffix in (("LEFT", "L"), ("RIGHT", "R")):
        gamma_by_wing[wing] = {
            "translation": np.asarray(arrays[f"Gamma_t_{suffix}"], dtype=float),
            "rotation": np.asarray(arrays[f"Gamma_r_{suffix}"], dtype=float),
        }
    gamma6_left = np.concatenate(
        (gamma_by_wing["LEFT"]["translation"], gamma_by_wing["LEFT"]["rotation"]),
        axis=1,
    )
    gamma6_right = np.concatenate(
        (gamma_by_wing["RIGHT"]["translation"], gamma_by_wing["RIGHT"]["rotation"]),
        axis=1,
    )
    gamma_contract_match = all(
        np.array_equal(
            gamma_by_wing[wing][kind],
            np.asarray(
                rom_contract["base_participation"][wing][
                    "Gamma_t" if kind == "translation" else "Gamma_r"
                ],
                dtype=float,
            ),
        )
        for wing in wing_order
        for kind in ("translation", "rotation")
    )

    corners: list[dict[str, Any]] = []
    all_wing_checks: list[bool] = []
    for corner in corner_order:
        K7 = np.asarray(arrays[f"Krom_{corner}"], dtype=float)
        C7 = np.asarray(arrays[f"Crom_{corner}"], dtype=float)
        K14 = np.zeros((14, 14), dtype=float)
        K14[:7, :7] = K7
        K14[7:, 7:] = K7
        wings: list[dict[str, Any]] = []
        combined_eta: list[float] = []
        for wing in wing_order:
            gamma_t = gamma_by_wing[wing]["translation"]
            gamma_r = gamma_by_wing[wing]["rotation"]
            forcing = -(gamma_t @ acceleration + gamma_r @ angular_acceleration)
            if eta_override_by_wing is None:
                eta = np.linalg.solve(K7, forcing)
                response_source = "STATIC_K_INVERSE_BASE_ACCELERATION_FORCING"
            else:
                if wing not in eta_override_by_wing:
                    raise ValueError("ETA_OVERRIDE_MUST_COVER_LEFT_AND_RIGHT")
                eta = np.asarray(eta_override_by_wing[wing], dtype=float)
                if eta.shape != (7,) or not np.all(np.isfinite(eta)):
                    raise ValueError("ETA_OVERRIDE_MALFORMED")
                response_source = "EXPLICIT_FAIL_CLOSED_DOMAIN_TEST_OVERRIDE"
            operator_checks, in_domain = _operator_screen(
                eta, arrays, limits, operator_limit_map
            )
            all_wing_checks.append(in_domain)
            combined_eta.extend(eta.tolist())
            wings.append(
                {
                    "wing": wing,
                    "mode_order": mode_order,
                    "Gamma_t_shape": list(gamma_t.shape),
                    "Gamma_r_shape": list(gamma_r.shape),
                    "Gamma_t": gamma_t.tolist(),
                    "Gamma_r": gamma_r.tolist(),
                    "diagnostic_modal_force": forcing.tolist(),
                    "diagnostic_modal_force_norm": float(np.linalg.norm(forcing)),
                    "eta_static": eta.tolist(),
                    "response_source": response_source,
                    "operator_checks": operator_checks,
                    "state": (
                        "IN_DOMAIN"
                        if in_domain
                        else "FAIL_CLOSED_OUT_OF_LINEAR_ROM_DOMAIN"
                    ),
                    "pass": in_domain,
                }
            )
        corners.append(
            {
                "corner": corner,
                "M7_shape": list(M7.shape),
                "K7_shape": list(K7.shape),
                "C7_shape": list(C7.shape),
                "M7_min_eigenvalue": float(np.min(np.linalg.eigvalsh(M7))),
                "K7_min_eigenvalue": float(np.min(np.linalg.eigvalsh(K7))),
                "M14_shape": list(M14.shape),
                "K14_shape": list(K14.shape),
                "M14_min_eigenvalue": float(np.min(np.linalg.eigvalsh(M14))),
                "K14_min_eigenvalue": float(np.min(np.linalg.eigvalsh(K14))),
                "combined_eta_LEFT_then_RIGHT": combined_eta,
                "wings": wings,
                "pass": all(wing["pass"] for wing in wings),
            }
        )

    checks = {
        "rom_contract_schema": rom_contract.get("schema") == "R2_SEVEN_MODE_ROM_V3",
        "validity_envelope_schema": envelope.get("schema")
        == "R2_FLEXIBILITY_VALIDITY_ENVELOPE_V3",
        "mode_order_exact": rom_contract.get("mode_labels") == mode_order,
        "hf_shape_183": arrays["M"].shape == (183, 183),
        "rom_basis_shape_183x7": arrays["Phi_rom"].shape == (183, 7),
        "dual_wing_mode_total_14": M14.shape == (14, 14),
        "wing_order_LEFT_then_RIGHT": list(wing_order) == ["LEFT", "RIGHT"],
        "nonzero_linear_acceleration_S": float(np.linalg.norm(acceleration)) > 0.0,
        "nonzero_angular_acceleration_S": float(np.linalg.norm(angular_acceleration))
        > 0.0,
        "per_wing_gamma_contract_match": gamma_contract_match,
        "left_right_combined_gamma_distinct": not np.array_equal(
            gamma6_left, gamma6_right
        ),
        "all_M_and_K_positive_definite": all(
            corner["M7_min_eigenvalue"] > float(cfg["positive_eigenvalue_min"])
            and corner["K7_min_eigenvalue"]
            > float(cfg["positive_eigenvalue_min"])
            for corner in corners
        ),
        "all_per_wing_operator_limits_satisfied": all(all_wing_checks),
        "out_of_domain_policy_exact": envelope["quantitative_linearity_contract"][
            "out_of_domain_policy"
        ]
        == cfg["out_of_domain_policy"],
    }
    return {
        "schema": "CTRL_R2_DUAL_WING_14MODE_STATIC_FLEX_INSTANCE_V1",
        "scope": cfg["scope"],
        "configuration": "DEPLOYED_FLAT_LATCHED_ONLY",
        "excitation_authority": cfg["excitation_authority"],
        "mission_flex_robustness_evaluated": False,
        "frame_semantics": {
            "base_linear_acceleration_S_m_s2": acceleration.tolist(),
            "base_angular_acceleration_S_rad_s2": angular_acceleration.tolist(),
            "expressed_in": "SPACECRAFT_S_FRAME",
        },
        "wing_order": list(wing_order),
        "mode_order_per_wing": mode_order,
        "combined_mode_order": [
            f"{wing}:{mode}" for wing in wing_order for mode in mode_order
        ],
        "gamma_semantics": {
            "per_wing_source_keys": {
                "LEFT": ["Gamma_t_L", "Gamma_r_L"],
                "RIGHT": ["Gamma_t_R", "Gamma_r_R"],
            },
            "left_right_translation_gamma_equal_by_model_symmetry": bool(
                np.array_equal(
                    gamma_by_wing["LEFT"]["translation"],
                    gamma_by_wing["RIGHT"]["translation"],
                )
            ),
            "left_right_rotation_gamma_equal": bool(
                np.array_equal(
                    gamma_by_wing["LEFT"]["rotation"],
                    gamma_by_wing["RIGHT"]["rotation"],
                )
            ),
            "left_right_combined_gamma_distinct": not np.array_equal(
                gamma6_left, gamma6_right
            ),
        },
        "corners": corners,
        "checks": checks,
        "out_of_domain_policy": cfg["out_of_domain_policy"],
        "e23_pass_inheritance": "NOT_INHERITED",
        "round4_gate_pass_inheritance": "NOT_INHERITED",
        "round4_source_gate_technical_verdict": round4_gate.get("technical_verdict"),
        "round4_source_gate_review_status": round4_gate.get("review_status"),
        "pass": all(checks.values()),
    }


def run_flexibility_static_screen(
    repo_root: Path, config: Mapping[str, Any]
) -> dict[str, Any]:
    first = flexibility_static_screen_once(repo_root, config)
    replay = flexibility_static_screen_once(repo_root, config)
    first_hash = canonical_sha256(first)
    replay_hash = canonical_sha256(replay)
    return {
        "schema": "CTRL_R2_DUAL_WING_14MODE_STATIC_FLEX_SCREEN_V1",
        "scope": "STATIC_PROVISIONAL_FLEXIBILITY_SCREEN_ONLY__NO_E23_OR_RELEASE_INHERITANCE",
        "first": first,
        "determinism": {
            "first_canonical_sha256": first_hash,
            "replay_canonical_sha256": replay_hash,
            "bitwise_canonical_equal": first_hash == replay_hash,
        },
        "pass": first["pass"] and first_hash == replay_hash,
        "next_stage_authorized": False,
        "release_credit": False,
    }


def audit_actuator_dynamics_intake(
    document: Mapping[str, Any], config: Mapping[str, Any]
) -> dict[str, Any]:
    expected_order = list(config["unified_r2_static_probe"]["joint_order"])
    required = list(document.get("required_measurement_fields", []))
    records = list(document.get("joint_records", []))
    record_order = [record.get("joint") for record in records]
    field_checks: list[dict[str, Any]] = []
    for record in records:
        measurements = record.get("measurements", {})
        source_only = record.get("source_only_urdf_declarations", {})
        keys_exact = list(measurements) == required
        all_null = keys_exact and all(measurements[field] is None for field in required)
        pending = record.get("measurement_status") == "MEASUREMENT_PENDING_ALL_FIELDS"
        velocity_literal_guarded = (
            source_only.get("velocity_limit_unit") == "UNDECLARED"
            and source_only.get("velocity_limit_interpretation")
            == "MODEL_ONLY_NONPHYSICAL_NUMERIC_LITERAL"
            and source_only.get("hardware_validity") == "NOT_ESTABLISHED"
        )
        field_checks.append(
            {
                "joint": record.get("joint"),
                "required_field_count": len(required),
                "fields_exact_and_ordered": keys_exact,
                "all_measurement_values_null": all_null,
                "measurement_pending": pending,
                "urdf_velocity_literal_unit_undeclared_and_nonphysical": velocity_literal_guarded,
                "pass": keys_exact and all_null and pending and velocity_literal_guarded,
            }
        )
    checks = {
        "schema_exact": document.get("schema")
        == "CTRL_R2_ACTUATOR_DYNAMICS_INTAKE_V1",
        "joint_order_exact_8DOF": record_order == expected_order
        and document.get("joint_order") == expected_order,
        "required_fields_nonempty": len(required) >= 19,
        "all_joint_records_complete_null_pending": len(records) == 8
        and all(item["pass"] for item in field_checks),
        "zero_fill_forbidden": document.get("zero_fill_forbidden") is True,
        "hardware_model_not_claimed": document.get("hardware_model_valid") is False,
        "next_stage_false": document.get("next_stage_authorized") is False,
        "release_credit_false": document.get("release_credit") is False,
        "minimum_schema_label_exact": document.get("schema_completeness")
        == "MINIMUM_SYNTAX_ONLY__SEMANTIC_REQUIREMENTS_OPEN",
        "semantic_requirements_explicitly_incomplete": document.get(
            "semantic_requirements_complete"
        )
        is False,
        "known_requirement_gaps_registered": len(
            document.get("known_missing_requirement_groups", [])
        )
        >= 6,
    }
    return {
        "schema": "CTRL_R2_ACTUATOR_DYNAMICS_INTAKE_AUDIT_V1",
        "joint_record_checks": field_checks,
        "checks": checks,
        "minimum_intake_schema_complete": all(checks.values()),
        "semantic_requirements_complete": False,
        "known_missing_requirement_groups": list(
            document.get("known_missing_requirement_groups", [])
        ),
        "hardware_measurements_complete": False,
        "hardware_model_valid": False,
        "hold": "MEASUREMENT_PENDING__NO_TORQUE_LEVEL_OR_THERMAL_CONTROL_CREDIT",
        "pass_for_candidate_packaging_minimum_schema_only": all(checks.values()),
        "next_stage_authorized": False,
        "release_credit": False,
    }
