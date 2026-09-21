#!/usr/bin/env python3
"""Independent V4 audit without importing the V4 guard or backend modules."""

from __future__ import annotations

import ast
import csv
import hashlib
import hmac
import io
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import numpy as np
import yaml


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
V3_ROOT = HERE.parent / "v3_in_memory_dynamics_diagnostic"
if str(V3_ROOT) not in sys.path:
    sys.path.insert(0, str(V3_ROOT))

from sim13_v3.reduced_dynamics import ZeroMomentumReducedDynamics
from sim13_v3.source_model import build_synthetic_8dof_model


LEDGER_PATH = HERE / "evidence/SIM13_V4_RUNTIME_GUARD_LEDGER_V1.json"
SOURCE_MANIFEST_PATH = HERE / "evidence/SIM13_V4_SOURCE_MANIFEST_V1.csv"
AUDIT_PATH = HERE / "evidence/SIM13_V4_INDEPENDENT_AUDIT_RECEIPT_V1.json"
SIM10_GATE_PATH = (
    PROJECT_ROOT
    / "30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json"
)
SIM10_SUMMARY_PATH = (
    PROJECT_ROOT
    / "30_simulation/sim_10_mission_feasibility/results/sim_10_scan_summary.json"
)
SIM10_PARAMETER_CARD_PATH = (
    PROJECT_ROOT / "20_engineering/config/mission_feasibility/scan_v0.yaml"
)
SIM10_ANCHOR_SOURCE_PATH = (
    PROJECT_ROOT / "30_simulation/sim_10_mission_feasibility/src/scan_grid.py"
)
V2_GATE_PATH = (
    HERE.parent
    / "v2_system_rebind/results/SIM13_V2_PREBIND_SOURCE_GATE_V1.json"
)
EXPECTED_SIM10_GATE_SHA256 = (
    "4DBD8C91FF3455D5E5997A995AC385F02BBC1D2E379BBFE5C0563D41834DFC67"
)
EXPECTED_SIM10_SUMMARY_SHA256 = (
    "63D84CE5CA84E9B9DE8C2833577C9645FF2060874B8AB5E081EE7672D0046FC5"
)
EXPECTED_SIM10_PARAMETER_CARD_SHA256 = (
    "856F1E30DE47CA5B3F505F9FE5BD5CD22A75E448EC916B42D9C330F7A62E28EA"
)
EXPECTED_SIM10_ANCHOR_SOURCE_SHA256 = (
    "FBEA1EB8AC459ABA364683AF9C6BE668154FF036ADEDCCC441B5D32CFFF4D5C4"
)
DIAGNOSTIC_HMAC_KEY = b"SIM13_V4_PUBLIC_DIAGNOSTIC_KEY_NOT_SECRET_NOT_PRODUCTION_V1"
SYNTHETIC_POLICY_FIXTURE = {
    "schema": "SIM13_V4_SYNTHETIC_TARGET_POLICY_FIXTURE_V1",
    "policy_id": "ALLOW_SYNTHETIC_NON_DEBRIS_DYNAMICS_DIAGNOSTIC",
    "target": {
        "target_id": "synthetic_non_debris_fixture",
        "target_mass_kg": 1.0,
        "tumble_rate_dps": 0.0,
    },
    "mission_veto_required": False,
    "current_system_policy": False,
    "contact_policy": False,
    "production_credit": False,
}
DEBRIS_TARGET = {
    "target_id": "target_debris_v0",
    "target_mass_kg": 150.0,
    "tumble_rate_dps": 3.0,
}
DEBRIS_POLICY_FIXTURE = {
    "schema": "SIM13_V4_DEBRIS_VETO_POLICY_FIXTURE_V1",
    "policy_id": "REQUIRE_HASH_BOUND_SIM10_VETO_BEFORE_BACKEND",
    "target": DEBRIS_TARGET,
    "mission_veto_required": True,
    "current_system_policy": False,
    "contact_policy": False,
    "production_credit": False,
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest().upper()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _record(path: Path) -> dict[str, object]:
    payload = path.read_bytes()
    return {
        "path": path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest().upper(),
    }


def _signature(payload: Mapping[str, object]) -> str:
    return hmac.new(
        DIAGNOSTIC_HMAC_KEY,
        _canonical_bytes(payload),
        hashlib.sha256,
    ).hexdigest().upper()


def _rotation(wxyz: Sequence[float]) -> np.ndarray:
    q = np.asarray(wxyz, dtype=float)
    q /= np.linalg.norm(q)
    w, x, y, z = q
    return np.array(
        (
            (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
            (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
            (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)),
        )
    )


def _ee_centroid(
    model: object,
    q: Sequence[float],
    position: Sequence[float],
    quaternion: Sequence[float],
) -> np.ndarray:
    transforms, _ = model.forward_kinematics(q)  # type: ignore[attr-defined]
    local = np.mean(
        np.stack(
            [
                transforms[name][:3, 3]
                for name in (
                    "synthetic_link_6",
                    "synthetic_finger_1",
                    "synthetic_finger_2",
                )
            ]
        ),
        axis=0,
    )
    return np.asarray(position, dtype=float) + _rotation(quaternion) @ local


def _manifest_rows() -> list[dict[str, str]]:
    return list(
        csv.DictReader(
            io.StringIO(SOURCE_MANIFEST_PATH.read_text(encoding="utf-8"))
        )
    )


def _manifest_valid() -> tuple[bool, dict[str, object]]:
    rows = _manifest_rows()
    paths = [row["path"] for row in rows]
    unique = len(paths) == len(set(paths))
    generated_excluded = all(
        "/evidence/" not in f"/{path}/" and "/results/" not in f"/{path}/"
        for path in paths
    )
    current = True
    for row in rows:
        path = PROJECT_ROOT / row["path"]
        if (
            not path.is_file()
            or int(row["bytes"]) != path.stat().st_size
            or row["sha256"] != _sha256_file(path)
        ):
            current = False
            break
    return unique and generated_excluded and current, {
        "rows": len(rows),
        "unique": unique,
        "generated_artifacts_excluded": generated_excluded,
        "all_hashes_current": current,
    }


def _source_boundary_valid() -> tuple[bool, dict[str, object]]:
    forbidden_calls = {"_build_robot", "gen_urdf"}
    observed_calls: list[str] = []
    primary_imports: list[str] = []
    for path in HERE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                else:
                    name = ""
                if name in forbidden_calls:
                    observed_calls.append(f"{path.name}:{name}")
            if path == Path(__file__).resolve() and isinstance(
                node, (ast.Import, ast.ImportFrom)
            ):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                else:
                    names = [node.module or ""]
                if any(name.startswith("sim13_v4") for name in names):
                    primary_imports.extend(names)
    urdf_files = [path.relative_to(HERE).as_posix() for path in HERE.rglob("*.urdf")]
    forbidden_names = {
        "MECH_RL_SYSTEM_INTERFACE_V2.yaml",
        "OWNER_AUTHORIZATION.json",
        "RUN_AUTHORIZATION.json",
        "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json",
    }
    interface_or_authorization_files = [
        path.relative_to(HERE).as_posix()
        for path in HERE.rglob("*")
        if path.name in forbidden_names
    ]
    valid = not (
        observed_calls
        or primary_imports
        or urdf_files
        or interface_or_authorization_files
    )
    return valid, {
        "private_generator_calls": observed_calls,
        "auditor_primary_v4_imports": primary_imports,
        "urdf_files": urdf_files,
        "interface_or_authorization_files": interface_or_authorization_files,
    }


def _audit_capability(nc18: Mapping[str, object]) -> tuple[bool, dict[str, object]]:
    capability = nc18["capability"]
    payload = capability["payload"]
    action = nc18["action"]
    context = nc18["context"]
    snapshot = nc18["gate_snapshot"]
    signature_ok = hmac.compare_digest(
        capability["signature_hmac_sha256"], _signature(payload)
    )
    bindings_ok = (
        payload["action_sha256"] == _digest(action)
        and payload["context_sha256"] == _digest(context)
        and payload["gate_snapshot_sha256"] == _digest(snapshot)
        and payload["backend_id"] == context["backend_id"]
    )
    finite_window = (
        math.isfinite(float(payload["validity_window_s"]))
        and 0.0 < float(payload["validity_window_s"]) <= 5.0
        and float(payload["not_before_s"]) == float(payload["issued_at_s"])
        and float(payload["expires_at_s"])
        == float(payload["issued_at_s"]) + float(payload["validity_window_s"])
    )
    authority_false = all(
        payload[name] is False
        for name in (
            "current_system_binding_passed",
            "runtime_production_gate_passed",
            "release_credit",
        )
    )
    return signature_ok and bindings_ok and finite_window and authority_false, {
        "signature_ok": signature_ok,
        "bindings_ok": bindings_ok,
        "finite_window": finite_window,
        "authority_flags_false": authority_false,
        "key_class": payload["key_class"],
        "clock_class": payload["clock_class"],
    }


def _audit_nc15(control: Mapping[str, object]) -> tuple[bool, dict[str, object]]:
    cases = control["cases"]
    expected = {
        "stale": "CAPABILITY_STALE",
        "action_mismatch": "CAPABILITY_ACTION_MISMATCH",
        "context_mismatch": "CAPABILITY_CONTEXT_MISMATCH",
        "snapshot_mismatch": "CAPABILITY_GATE_SNAPSHOT_MISMATCH",
        "signature_tamper": "CAPABILITY_SIGNATURE_INVALID",
    }
    ordinary = all(
        cases[name]["allowed"] is False
        and cases[name]["executed_action"]["strategy_id"] == "ABORT"
        and cases[name]["reason_code"] == reason
        and cases[name]["consumed_nonce_returned"] is None
        and cases[name]["canonical_module_nonce_consumed"] is False
        for name, reason in expected.items()
    )
    replay = cases["replay"]
    replay_ok = (
        replay["qualified_single_use_baseline"]["allowed"] is True
        and replay["qualified_single_use_baseline"]["consumed_nonce_returned"]
        == "NC15-REPLAY"
        and replay["same_shield_replay"]["allowed"] is False
        and replay["same_shield_replay"]["reason_code"]
        == "CAPABILITY_NONCE_REPLAY"
        and replay["same_shield_replay"]["executed_action"]["strategy_id"]
        == "ABORT"
        and replay["same_shield_replay"]["canonical_module_nonce_consumed"] is True
    )
    cross = cases["cross_shield_new_ledger_replay"]
    cross_instance_ok = (
        cross["decision"]["allowed"] is False
        and cross["decision"]["reason_code"] == "CAPABILITY_NONCE_REPLAY"
        and cross["decision"]["executed_action"]["strategy_id"] == "ABORT"
        and cross["new_ledger_view_reports_consumed"] is True
        and cross["new_ledger_view_reconsume_allowed"] is False
        and cross["isolated_ledger_injection_api_available"] is False
    )
    race = cases["thread_safe_cross_shield_race"]
    race_ok = (
        race["attempts"] == 16
        and race["allowed"] == 1
        and race["replay_rejections"] == 15
        and race["canonical_module_nonce_consumed"] is True
    )
    lifetime_boundary_ok = control["persistence_boundary"] == (
        "SINGLE_CANONICAL_MODULE_INSTANCE_LIFETIME_SHARED_THREAD_SAFE_ONLY__"
        "NO_IMPORTLIB_RELOAD_DUPLICATE_MODULE_INSTANCE_CROSS_PROCESS_OR_RESTART_"
        "PERSISTENCE_CLAIM"
    )
    return ordinary and replay_ok and cross_instance_ok and race_ok and lifetime_boundary_ok, {
        "ordinary_fail_closed_cases": len(expected),
        "ordinary_exact": ordinary,
        "single_use_then_replay_rejected": replay_ok,
        "cross_shield_and_new_ledger_replay_rejected": cross_instance_ok,
        "thread_safe_exactly_one_of_sixteen": race_ok,
        "single_canonical_module_instance_only_reload_not_persistent": (
            lifetime_boundary_ok
        ),
    }


def _audit_dynamics(nc18: Mapping[str, object]) -> tuple[bool, dict[str, object]]:
    initial = nc18["input"]["initial_state"]
    effort = nc18["input"]["generalized_effort"]
    output = nc18["output"]["final_state"]
    model = build_synthetic_8dof_model()
    solver = ZeroMomentumReducedDynamics(model)
    history = solver.propagate(
        initial["q_mixed_rad_m"],
        initial["qdot_mixed_rad_s_m_s"],
        step_s=float(nc18["input"]["step_s"]),
        steps=int(nc18["input"]["steps"]),
        generalized_effort=effort["values_mixed"],
        base_position_inertial_initial_m=initial["base_position_inertial_m"],
        base_quaternion_body_to_inertial_initial_wxyz=initial[
            "base_quaternion_body_to_inertial_wxyz"
        ],
    )
    q = history.q[-1]
    qdot = history.qdot[-1]
    position = history.base_position_inertial_m[-1]
    quaternion = history.base_quaternion_body_to_inertial_wxyz[-1]
    twist = history.base_twist_body_mixed_units[-1]
    ee = _ee_centroid(model, q, position, quaternion)
    comparisons = {
        "q": bool(np.allclose(q, output["q_mixed_rad_m"], atol=2e-13, rtol=2e-13)),
        "qdot": bool(
            np.allclose(qdot, output["qdot_mixed_rad_s_m_s"], atol=2e-13, rtol=2e-13)
        ),
        "base_position": bool(
            np.allclose(position, output["base_position_inertial_m"], atol=2e-13, rtol=2e-13)
        ),
        "base_quaternion": bool(
            np.allclose(
                quaternion,
                output["base_quaternion_body_to_inertial_wxyz"],
                atol=2e-13,
                rtol=2e-13,
            )
        ),
        "base_twist": bool(
            np.allclose(
                twist,
                output["base_twist_body_mixed_m_s_rad_s"],
                atol=2e-13,
                rtol=2e-13,
            )
        ),
        "ee_centroid": bool(
            np.allclose(ee, output["ee_centroid_inertial_m"], atol=2e-13, rtol=2e-13)
        ),
    }
    nonzero_effort_by_unit = (
        np.linalg.norm(np.asarray(effort["revolute"]["values_Nm"])) > 0.0
        and np.linalg.norm(np.asarray(effort["prismatic"]["values_N"])) > 0.0
        and effort["heterogeneous_global_norm_used"] is False
    )
    initial_q = np.asarray(initial["q_mixed_rad_m"], dtype=float)
    initial_qdot = np.asarray(initial["qdot_mixed_rad_s_m_s"], dtype=float)
    initial_position = np.asarray(initial["base_position_inertial_m"], dtype=float)
    initial_quaternion = np.asarray(
        initial["base_quaternion_body_to_inertial_wxyz"], dtype=float
    )
    initial_twist = np.asarray(
        initial["base_twist_body_mixed_m_s_rad_s"], dtype=float
    )
    quaternion_alignment = abs(
        float(
            initial_quaternion
            @ (np.asarray(quaternion, dtype=float) / np.linalg.norm(quaternion))
        )
    )
    quaternion_alignment = min(1.0, max(-1.0, quaternion_alignment))
    change_by_unit = {
        "revolute_q_max_abs_rad": float(np.max(np.abs(q[:6] - initial_q[:6]))),
        "prismatic_q_max_abs_m": float(np.max(np.abs(q[6:] - initial_q[6:]))),
        "revolute_qdot_max_abs_rad_s": float(
            np.max(np.abs(qdot[:6] - initial_qdot[:6]))
        ),
        "prismatic_qdot_max_abs_m_s": float(
            np.max(np.abs(qdot[6:] - initial_qdot[6:]))
        ),
        "base_position_norm_m": float(np.linalg.norm(position - initial_position)),
        "base_orientation_angle_rad": float(
            2.0 * math.acos(quaternion_alignment)
        ),
        "base_linear_twist_norm_m_s": float(
            np.linalg.norm(twist[:3] - initial_twist[:3])
        ),
        "base_angular_twist_norm_rad_s": float(
            np.linalg.norm(twist[3:] - initial_twist[3:])
        ),
        "ee_centroid_position_norm_m": float(
            np.linalg.norm(ee - np.asarray(initial["ee_centroid_inertial_m"]))
        ),
    }
    joint_state_changed = all(
        change_by_unit[name] > 1.0e-12
        for name in (
            "revolute_q_max_abs_rad",
            "prismatic_q_max_abs_m",
            "revolute_qdot_max_abs_rad_s",
            "prismatic_qdot_max_abs_m_s",
        )
    )
    base_or_ee_changed = any(
        change_by_unit[name] > 1.0e-12
        for name in (
            "base_position_norm_m",
            "base_orientation_angle_rad",
            "base_linear_twist_norm_m_s",
            "base_angular_twist_norm_rad_s",
            "ee_centroid_position_norm_m",
        )
    )
    real_change = (
        joint_state_changed
        and base_or_ee_changed
        and nc18["output"]["state_evolution"][
            "base_linear_and_angular_twist_audited_separately"
        ]
        is True
    )
    phase = nc18["phase_only_negative_control"]
    before = phase["before"]
    after = phase["after"]
    physical_fields = set(before) - {"phase"}
    phase_only_independent = (
        all(before[name] == after[name] for name in physical_fields)
        and before["phase"] != after["phase"]
        and phase["assessment"]["accepted"] is False
        and phase["assessment"]["reason_code"]
        == "DYNAMICS_STATE_UPDATE_FAILURE_PHASE_ONLY"
    )
    units_ok = (
        nc18["unit_contract"]["effort_units"] == ["N*m"] * 6 + ["N"] * 2
        and nc18["unit_contract"]["coordinate_units"] == ["rad"] * 6 + ["m"] * 2
        and nc18["unit_contract"]["rate_units"] == ["rad/s"] * 6 + ["m/s"] * 2
        and nc18["unit_contract"]["heterogeneous_global_norm_used"] is False
        and nc18["unit_contract"][
            "base_linear_and_angular_twist_audited_separately"
        ]
        is True
    )
    policy_binding_ok = (
        nc18["target_policy_fixture"] == SYNTHETIC_POLICY_FIXTURE
        and nc18["context"]["target_policy_sha256"]
        == _digest(SYNTHETIC_POLICY_FIXTURE)
        and nc18["context"]["coordinator_id"]
        == "SIM13_V4_UNIQUE_DIAGNOSTIC_EXECUTION_COORDINATOR_V1"
        and nc18["output"]["backend_invocation_delta"] == 1
        and nc18["output"]["capability_consumed"] is True
    )
    passed = (
        all(comparisons.values())
        and nonzero_effort_by_unit
        and real_change
        and phase_only_independent
        and units_ok
        and policy_binding_ok
    )
    return passed, {
        "public_v3_recompute_matches": comparisons,
        "nonzero_effort_separated_by_unit": nonzero_effort_by_unit,
        "real_physical_state_change": bool(real_change),
        "change_by_unit_without_heterogeneous_norm": change_by_unit,
        "base_linear_and_angular_twist_checked_separately": True,
        "combined_base_twist_norm_computed": False,
        "phase_only_negative_independently_detected": phase_only_independent,
        "unit_contract_exact": units_ok,
        "explicit_synthetic_target_policy_and_coordinator_binding": policy_binding_ok,
        "primary_v4_dynamics_imported": False,
    }


def _anchor_source_literals_independent() -> dict[str, float]:
    tree = ast.parse(
        SIM10_ANCHOR_SOURCE_PATH.read_text(encoding="utf-8"),
        filename=str(SIM10_ANCHOR_SOURCE_PATH),
    )
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        entries: dict[str, ast.AST] = {}
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                entries[key.value] = value
        anchor = entries.get("anchor")
        if not (
            isinstance(anchor, ast.Constant)
            and anchor.value == "debris_sim06"
        ):
            continue
        mass = entries.get("m_t")
        speed = entries.get("omega_dps")
        if not (
            isinstance(mass, ast.Constant)
            and isinstance(mass.value, (int, float))
            and not isinstance(mass.value, bool)
            and isinstance(speed, ast.Constant)
            and isinstance(speed.value, (int, float))
            and not isinstance(speed.value, bool)
        ):
            raise ValueError("independent sim10 anchor source types unknown")
        return {
            "target_mass_kg": float(mass.value),
            "tumble_rate_dps": float(speed.value),
        }
    raise ValueError("independent debris_sim06 source row absent")


def _audit_nc20(control: Mapping[str, object]) -> tuple[bool, dict[str, object]]:
    receipt = control["receipt"]
    payload = receipt["payload"]
    signature_ok = hmac.compare_digest(
        receipt["signature_hmac_sha256"], _signature(payload)
    )
    bindings_ok = (
        payload["action_sha256"] == _digest(control["action"])
        and payload["gate_snapshot_sha256"] == _digest(control["gate_snapshot"])
        and payload["target_sha256"] == _digest(control["target"])
        and control["target"] == DEBRIS_TARGET
        and control["target_policy_fixture"] == DEBRIS_POLICY_FIXTURE
        and control["coordinator_context"]["target_policy_sha256"]
        == _digest(DEBRIS_POLICY_FIXTURE)
        and control["coordinator_capability"]["payload"]["action_sha256"]
        == _digest(control["action"])
        and control["coordinator_capability"]["payload"]["context_sha256"]
        == _digest(control["coordinator_context"])
        and control["coordinator_capability"]["payload"]["gate_snapshot_sha256"]
        == _digest(control["gate_snapshot"])
    )
    expected_hashes = {
        "gate": EXPECTED_SIM10_GATE_SHA256,
        "summary": EXPECTED_SIM10_SUMMARY_SHA256,
        "parameter_card": EXPECTED_SIM10_PARAMETER_CARD_SHA256,
        "anchor_source": EXPECTED_SIM10_ANCHOR_SOURCE_SHA256,
    }
    paths = {
        "gate": SIM10_GATE_PATH,
        "summary": SIM10_SUMMARY_PATH,
        "parameter_card": SIM10_PARAMETER_CARD_PATH,
        "anchor_source": SIM10_ANCHOR_SOURCE_PATH,
    }
    artifacts = control["sim10_artifacts"]
    hashes_ok = all(
        _sha256_file(paths[name]) == expected
        and artifacts[name]["sha256"] == expected
        for name, expected in expected_hashes.items()
    ) and (
        payload["sim10_gate_sha256"] == EXPECTED_SIM10_GATE_SHA256
        and payload["sim10_summary_sha256"] == EXPECTED_SIM10_SUMMARY_SHA256
        and payload["sim10_parameter_card_sha256"]
        == EXPECTED_SIM10_PARAMETER_CARD_SHA256
        and payload["sim10_anchor_source_sha256"]
        == EXPECTED_SIM10_ANCHOR_SOURCE_SHA256
    )
    gate = json.loads(SIM10_GATE_PATH.read_text(encoding="utf-8"))
    summary = json.loads(SIM10_SUMMARY_PATH.read_text(encoding="utf-8"))
    parameter_card = yaml.safe_load(
        SIM10_PARAMETER_CARD_PATH.read_text(encoding="utf-8")
    )
    source_literals = _anchor_source_literals_independent()
    anchors = [
        item
        for item in gate["gates"]["X1_anchors_vs_sim06"]["checks"]
        if item["anchor"] == "debris_sim06"
    ]
    g1 = parameter_card["scan"]["geometry_classes"]["G1_slender"]
    mass_speed_source_proof = {
        "parameter_card_calibration_mass_kg": float(g1["calibration_mass_kg"]),
        "anchor_source_target_mass_kg": source_literals["target_mass_kg"],
        "anchor_source_tumble_rate_dps": source_literals["tumble_rate_dps"],
    }
    gate_summary_region_w_plus_ok = (
        len(anchors) == 1
        and anchors[0]["ok"] is True
        and anchors[0]["region"] == "INFEASIBLE_RATE"
        and anchors[0]["region_expected"] == "INFEASIBLE_RATE"
        and anchors[0]["w_plus_dps"] == 3.0633304945807067
        and summary["anchors"]["debris_sim06"]["region_default_tier"]
        == "INFEASIBLE_RATE"
        and summary["anchors"]["debris_sim06"]["w_plus_dps"]
        == 3.0633304945807067
        and payload["anchor_region"] == "INFEASIBLE_RATE"
        and payload["anchor_w_plus_dps"] == 3.0633304945807067
    )
    parameter_card_mass_ok = (
        g1["calibration_target"] == "target_debris_v0"
        and mass_speed_source_proof["parameter_card_calibration_mass_kg"] == 150.0
    )
    anchor_source_mass_tumble_ok = (
        mass_speed_source_proof["anchor_source_target_mass_kg"] == 150.0
        and mass_speed_source_proof["anchor_source_tumble_rate_dps"] == 3.0
    )
    receipt_distributed_field_proof_ok = (
        payload["mass_speed_source_proof"] == mass_speed_source_proof
    )
    anchor_ok = all(
        (
            gate_summary_region_w_plus_ok,
            parameter_card_mass_ok,
            anchor_source_mass_tumble_ok,
            receipt_distributed_field_proof_ok,
        )
    )
    expected = {
        "valid_infeasible_rate_veto": "MISSION_VETO_INFEASIBLE_RATE",
        "action_mismatch": "SIM10_VETO_RECEIPT_ACTION_MISMATCH",
        "snapshot_mismatch": "SIM10_VETO_RECEIPT_SNAPSHOT_MISMATCH",
        "target_mismatch": "SIM10_VETO_RECEIPT_TARGET_MISMATCH",
        "anchor_drift": "SIM10_VETO_RECEIPT_ANCHOR_DRIFT",
        "hash_drift": "SIM10_VETO_RECEIPT_HASH_DRIFT",
        "unknown_receipt": "SIM10_VETO_RECEIPT_UNKNOWN",
        "resigned_malformed_numeric": "SIM10_VETO_RECEIPT_MALFORMED_TYPE",
    }
    cases = control["cases"]
    cases_ok = all(
        cases[name]["allowed"] is False
        and cases[name]["executed_action"]["strategy_id"] == "ABORT"
        and cases[name]["reason_code"] == reason
        and cases[name]["historical_sim10_pass_inherited_to_current_system"]
        is False
        for name, reason in expected.items()
    ) and cases["valid_infeasible_rate_veto"]["receipt_verified"] is True
    coordinator_expected = {
        "missing_receipt": "SIM10_VETO_RECEIPT_UNKNOWN",
        "valid_infeasible_veto": "MISSION_VETO_INFEASIBLE_RATE",
        "action_drift": "SIM10_VETO_RECEIPT_ACTION_MISMATCH",
        "snapshot_drift": "SIM10_VETO_RECEIPT_SNAPSHOT_MISMATCH",
        "target_drift": "SIM10_VETO_RECEIPT_TARGET_MISMATCH",
        "anchor_drift": "SIM10_VETO_RECEIPT_ANCHOR_DRIFT",
        "hash_drift": "SIM10_VETO_RECEIPT_HASH_DRIFT",
        "malformed_numeric": "SIM10_VETO_RECEIPT_MALFORMED_TYPE",
    }
    coordinator_cases = control["coordinator_prebackend_veto_cases"]
    coordinator_ok = set(coordinator_cases) == set(coordinator_expected) and all(
        coordinator_cases[name]["expected_reason"] == reason
        and coordinator_cases[name]["observed_reason"] == reason
        and coordinator_cases[name]["executed_action"]["strategy_id"] == "ABORT"
        and coordinator_cases[name]["capability_consumed"] is False
        and coordinator_cases[name]["backend_invocation_count_before"] == 0
        and coordinator_cases[name]["backend_invocation_count_after"] == 0
        and coordinator_cases[name]["backend_invocation_delta"] == 0
        and coordinator_cases[name]["state_byte_semantic_unchanged"] is True
        and coordinator_cases[name]["before_state_sha256"]
        == coordinator_cases[name]["after_state_sha256"]
        for name, reason in coordinator_expected.items()
    )
    coordinator_ok = coordinator_ok and (
        control["coordinator_backend_invocation_count_final"] == 0
        and control["coordinator_capability_nonce_consumed"] is False
        and control["direct_capability_backend_bypass_reason"]
        == "BACKEND_DIRECT_CALL_FORBIDDEN_USE_COORDINATOR"
        and control["veto_precedes_capability_consumption_and_backend"] is True
    )
    semantics_false = (
        payload["historical_sim10_gate_pass_inherited_to_current_system"] is False
        and payload["current_r2_feasibility_passed"] is False
        and payload["contact_grasp_gate_passed"] is False
        and payload["release_credit"] is False
    )
    passed = all(
        (
            signature_ok,
            bindings_ok,
            hashes_ok,
            anchor_ok,
            cases_ok,
            coordinator_ok,
            semantics_false,
        )
    )
    return passed, {
        "signature_ok": signature_ok,
        "target_action_context_snapshot_capability_bindings_ok": bindings_ok,
        "four_artifact_sha_bindings_ok": hashes_ok,
        "gate_summary_region_and_w_plus_ok": gate_summary_region_w_plus_ok,
        "parameter_card_calibration_mass_ok": parameter_card_mass_ok,
        "anchor_source_mass_and_tumble_ok": anchor_source_mass_tumble_ok,
        "receipt_distributed_anchor_field_proof_ok": (
            receipt_distributed_field_proof_ok
        ),
        "eight_fail_closed_receipt_cases_exact": cases_ok,
        "eight_coordinator_prebackend_abort_cases_exact": coordinator_ok,
        "backend_invocations_after_all_debris_cases": control[
            "coordinator_backend_invocation_count_final"
        ],
        "historical_sim10_pass_inherited_to_current_system": not semantics_false,
    }


def build_audit() -> dict[str, Any]:
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    controls = ledger["diagnostic_controls"]
    manifest_ok, manifest_details = _manifest_valid()
    boundary_ok, boundary_details = _source_boundary_valid()
    capability_ok, capability_details = _audit_capability(controls["NC18"])
    nc15_ok, nc15_details = _audit_nc15(controls["NC15"])
    opaque_probe = controls["NC16"]["opaque_invocation_negative_controls"]
    opaque_probe_ok = (
        opaque_probe["passed"] is True
        and opaque_probe["direct_construction_reason"]
        == "OPAQUE_INVOCATION_DIRECT_CONSTRUCTION_REJECTED"
        and opaque_probe["object_new_accepted"] is False
        and opaque_probe["object_new_reason"] == "OPAQUE_INVOCATION_UNREGISTERED"
        and opaque_probe["copy_constructor_rejected"] is True
        and opaque_probe["manual_clone_accepted"] is False
        and opaque_probe["manual_clone_reason"]
        == "OPAQUE_INVOCATION_OBJECT_IDENTITY_MISMATCH"
        and opaque_probe["registered_original_accepted_once"] is True
        and opaque_probe["replay_accepted"] is False
        and opaque_probe["replay_reason"] == "OPAQUE_INVOCATION_REPLAY_REJECTED"
        and opaque_probe["module_private_forge_primitives"] == []
    )
    nc16_ok = (
        controls["NC16"]["direct_bypass_reason"]
        == "BACKEND_DIRECT_CALL_FORBIDDEN_USE_COORDINATOR"
        and controls["NC16"]["shielded_baseline_executed"] is True
        and controls["NC16"]["shielded_capability_consumed"] is True
        and controls["NC16"]["coordinator_backend_invocation_delta"] == 1
        and controls["NC16"]["capability_alone_is_backend_invocation"] is False
        and opaque_probe_ok
        and "MALICIOUS_MONKEYPATCH_OR_CLOSURE_INTROSPECTION_OUT_OF_SCOPE"
        in controls["NC16"]["security_boundary"]
    )
    nc18_ok, nc18_details = _audit_dynamics(controls["NC18"])
    nc20_ok, nc20_details = _audit_nc20(controls["NC20"])
    v2_gate = json.loads(V2_GATE_PATH.read_text(encoding="utf-8"))
    v2_unchanged = (
        v2_gate["formal_negative_controls_passed"] == 15
        and v2_gate["formal_negative_controls_declared"] == 20
        and v2_gate["formal_negative_controls_hold_ids"]
        == ["NC15", "NC16", "NC18", "NC19", "NC20"]
        and ledger["formal_v2_negative_control_state"]["unchanged_by_v4"] is True
    )
    nc19_hold = (
        ledger["nc19"]["executed"] is False
        and ledger["nc19"]["passed"] is False
        and ledger["nc19"]["status"].startswith("HOLD_")
    )
    flags_false = all(value is False for value in ledger["authority_flags"].values())
    diagnostic_accounting = ledger["diagnostic_summary"] == {
        "declared": 4,
        "executed": 4,
        "passed": 4,
        "failed": 0,
        "control_ids": ["NC15", "NC16", "NC18", "NC20"],
        "all_passed_diagnostic": True,
        "formal_production_nc_credit": False,
    }
    checks = {
        "A01_LEDGER_SCHEMA_SCOPE": ledger["schema"]
        == "SIM13_V4_RUNTIME_GUARD_DIAGNOSTIC_LEDGER_V1"
        and ledger["scope"] == "SYNTHETIC_PREBIND_DIAGNOSTIC_ONLY",
        "A02_SOURCE_MANIFEST_CURRENT_NO_CYCLE": manifest_ok,
        "A03_NO_PRIVATE_GENERATOR_CALL_OR_URDF": boundary_ok,
        "A04_CAPABILITY_SIGNATURE_AND_BINDINGS": capability_ok,
        "A05_NC15_STALE_REPLAY_MISMATCH_FAIL_CLOSED": nc15_ok,
        "A06_NC16_DIRECT_BACKEND_BYPASS_REJECTED": nc16_ok,
        "A07_NC18_PUBLIC_V3_RECOMPUTE_MATCH": nc18_ok,
        "A08_NC20_HASH_BOUND_VETO": nc20_ok,
        "A09_V2_FORMAL_STATE_UNCHANGED_15_OF_20": v2_unchanged,
        "A10_NC19_REMAINS_HOLD": nc19_hold,
        "A11_AUTHORITY_RELEASE_FLAGS_FALSE": flags_false,
        "A12_DIAGNOSTIC_ACCOUNTING_ONLY": diagnostic_accounting,
        "A13_AUDITOR_DOES_NOT_IMPORT_PRIMARY_V4": boundary_details[
            "auditor_primary_v4_imports"
        ]
        == [],
        "A14_PRODUCTION_CREDIT_FALSE": controls["NC18"]["output"][
            "production_credit"
        ]
        is False,
        "A15_HETEROGENEOUS_NORMS_NOT_USED": controls["NC18"]["unit_contract"][
            "heterogeneous_global_norm_used"
        ]
        is False,
        "A16_BASE_LINEAR_AND_ANGULAR_TWIST_AUDITED_SEPARATELY": nc18_details[
            "base_linear_and_angular_twist_checked_separately"
        ]
        is True
        and nc18_details["combined_base_twist_norm_computed"] is False,
        "A17_NC15_SINGLE_CANONICAL_MODULE_INSTANCE_ONLY": nc15_details[
            "single_canonical_module_instance_only_reload_not_persistent"
        ]
        is True,
        "A18_NC16_OPAQUE_ONE_USE_NEGATIVE_CONTROLS": opaque_probe_ok,
        "A19_NC20_PREBACKEND_COORDINATOR_ZERO_INVOCATIONS": nc20_details[
            "eight_coordinator_prebackend_abort_cases_exact"
        ]
        is True
        and nc20_details["backend_invocations_after_all_debris_cases"] == 0,
        "A20_SIM10_FOUR_SHA_PLUS_DISTRIBUTED_ANCHOR_FIELDS": nc20_details[
            "four_artifact_sha_bindings_ok"
        ]
        is True
        and nc20_details["gate_summary_region_and_w_plus_ok"] is True
        and nc20_details["parameter_card_calibration_mass_ok"] is True
        and nc20_details["anchor_source_mass_and_tumble_ok"] is True
        and nc20_details["receipt_distributed_anchor_field_proof_ok"] is True,
    }
    passed_count = sum(int(value) for value in checks.values())
    passed = passed_count == len(checks)
    return {
        "schema": "SIM13_V4_INDEPENDENT_AUDIT_RECEIPT_V1",
        "generated_date_local": "2026-08-24",
        "scope": "INDEPENDENT_RECOMPUTATION_WITHOUT_IMPORTING_PRIMARY_V4_GUARD_OR_BACKEND",
        "verdict": (
            "PASS_INDEPENDENT_SYNTHETIC_DIAGNOSTIC_AUDIT"
            if passed
            else "FAIL_INDEPENDENT_SYNTHETIC_DIAGNOSTIC_AUDIT"
        ),
        "score": {
            "pass": passed_count,
            "total": len(checks),
            "failed": [name for name, value in checks.items() if not value],
        },
        "checks": checks,
        "details": {
            "manifest": manifest_details,
            "source_boundary": boundary_details,
            "capability": capability_details,
            "nc15": nc15_details,
            "nc16": {
                "direct_bypass_reason": controls["NC16"]["direct_bypass_reason"],
                "opaque_invocation_negative_controls_exact": opaque_probe_ok,
                "security_boundary": controls["NC16"]["security_boundary"],
            },
            "nc18": nc18_details,
            "nc20": nc20_details,
        },
        "inputs": {
            "ledger": _record(LEDGER_PATH),
            "source_manifest": _record(SOURCE_MANIFEST_PATH),
            "sim10_gate": _record(SIM10_GATE_PATH),
            "sim10_summary": _record(SIM10_SUMMARY_PATH),
            "sim10_parameter_card": _record(SIM10_PARAMETER_CARD_PATH),
            "sim10_anchor_source": _record(SIM10_ANCHOR_SOURCE_PATH),
            "v2_formal_gate": _record(V2_GATE_PATH),
        },
        "auditor_imports_primary_guard_or_backend": False,
        "owner_accepted": False,
        "current_system_passed": False,
        "current_system_binding_passed": False,
        "system_binding_passed": False,
        "runtime_fail_closed_gate_passed": False,
        "runtime_production_gate_passed": False,
        "production_dynamics_gate_passed": False,
        "contact_grasp_gate_passed": False,
        "system_urdf_available": False,
        "system_interface_instantiated": False,
        "release_credit": False,
        "next_stage_authorized": False,
    }


def write_audit() -> dict[str, Any]:
    document = build_audit()
    payload = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_bytes(payload.encode("utf-8"))
    return document


def main(argv: list[str] | None = None) -> int:
    check_only = bool(argv and "--check-only" in argv)
    document = build_audit() if check_only else write_audit()
    print(json.dumps({"score": document["score"], "verdict": document["verdict"]}, sort_keys=True))
    return 0 if not document["score"]["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
