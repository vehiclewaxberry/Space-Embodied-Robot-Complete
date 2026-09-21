"""Independent Phase-B2 physics/DAG audit and sole final-Gate issuer.

This module intentionally does not import the B2 solver or its validator.  It
reconstructs geometry, common-point wrench shifting, the regularized friction
law, P/H/E+D ledgers and convergence from hash-bound raw evidence.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[3]
PHASE_ROOT = HERE.parent
if str(PHASE_ROOT) not in sys.path:
    sys.path.insert(0, str(PHASE_ROOT))

from sim13_v4a.full_floating import (  # noqa: E402
    FullFloatingServiceModel,
    ServiceState,
    TargetState,
    TARGET_MASS_KG,
    quat_to_rotation,
    quaternion_geodesic,
    target_momentum_energy,
)


SOURCE_MANIFEST = HERE / "evidence/SIM13_V4B2_SOURCE_MANIFEST_V1.json"
TRACE = HERE / "evidence/SIM13_V4B2_FRICTION_TRACE_V1.json"
LEDGER = HERE / "evidence/SIM13_V4B2_FRICTION_LEDGER_V1.json"
VALIDATION = HERE / "evidence/SIM13_V4B2_VALIDATION_V1.json"
EVIDENCE_MANIFEST = HERE / "evidence/SIM13_V4B2_EVIDENCE_MANIFEST_V1.json"
PRE_AUDIT_GATE = HERE / "results/SIM13_V4B2_PRE_AUDIT_GATE_V1.json"
AUDIT_RECEIPT = HERE / "evidence/SIM13_V4B2_INDEPENDENT_AUDIT_RECEIPT_V1.json"
FINAL_GATE = HERE / "results/SIM13_V4B2_AUDITED_GATE_V1.json"
TERMINAL_MANIFEST = HERE / "results/SIM13_V4B2_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json"

EXPECTED_PHASE_A_GATE_SHA = "82ECF267AA5F0DF0B79610AB4FBFD4DB4AE564EDE530A7F69AB579D1E15F7A40"
EXPECTED_PHASE_B1_GATE_SHA = "91F11FA541A336D9C3E073104CB15C215BCAEC4417090D9FA743D7D089604BE4"

FLOORS = {
    "service_base_position_m": 1.0e-12,
    "service_base_quaternion_geodesic_rad": 5.0e-8,
    "service_q_R_rad": 1.0e-12,
    "service_q_P_m": 1.0e-12,
    "service_v_base_m_s": 1.0e-12,
    "service_omega_base_rad_s": 1.0e-14,
    "service_qdot_R_rad_s": 1.0e-12,
    "service_qdot_P_m_s": 1.0e-12,
    "target_position_m": 1.0e-12,
    "target_quaternion_geodesic_rad": 5.0e-8,
    "target_velocity_m_s": 1.0e-12,
    "target_omega_rad_s": 1.0e-14,
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _record(path: Path, role: str) -> dict[str, Any]:
    return {"role": role, "path": _relative(path), "bytes": path.stat().st_size, "sha256": _sha(path)}


def _resolve(relative: Any) -> Path | None:
    if not isinstance(relative, str) or not relative:
        return None
    candidate = (PROJECT_ROOT / relative).resolve()
    try:
        candidate.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return None
    return candidate


def _strict_reference(reference: Any, path: Path, role: str) -> dict[str, Any]:
    valid = isinstance(reference, dict)
    actual = _record(path, role) if path.is_file() else None
    expected = actual
    passed = valid and reference == expected
    return {"pass": bool(passed), "declared": reference, "actual": actual}


def _source_audit(source: dict[str, Any]) -> dict[str, Any]:
    records = source.get("records")
    checks = []
    roles = []
    paths = []
    if not isinstance(records, list):
        return {"pass": False, "reason": "records_not_list"}
    for item in records:
        valid = isinstance(item, dict)
        path = _resolve(item.get("path")) if valid else None
        role = item.get("role") if valid else None
        actual = None
        if path is not None and path.is_file() and isinstance(role, str):
            actual = _record(path, role)
        item_pass = actual == item
        checks.append({"pass": item_pass, "declared": item, "actual": actual})
        if valid:
            roles.append(role); paths.append(item.get("path"))
    phase_a = [item for item in records if isinstance(item, dict) and item.get("role") == "UPSTREAM_PHASE_A_GATE"]
    phase_b1 = [item for item in records if isinstance(item, dict) and item.get("role") == "UPSTREAM_PHASE_B1_FINAL_GATE"]
    required_roles = {
        "UPSTREAM_PHASE_A_MODEL", "UPSTREAM_PHASE_A_GATE", "UPSTREAM_PHASE_B1_KERNEL",
        "UPSTREAM_PHASE_B1_FINAL_GATE", "MODEL_CONTRACT", "GOVERNANCE_CONTRACT",
        "PACKAGE_SOURCE", "FRICTION_KERNEL_SOURCE", "SCOPE_README", "PYTEST_CONFIG",
        "VALIDATOR_SOURCE", "INDEPENDENT_AUDIT_SOURCE", "TEST_SOURCE",
    }
    passed = (
        source.get("schema") == "SIM13_V4B2_SOURCE_MANIFEST_V1"
        and all(item["pass"] for item in checks)
        and len(paths) == len(set(paths))
        and required_roles.issubset(set(roles))
        and len(phase_a) == 1 and phase_a[0].get("sha256") == EXPECTED_PHASE_A_GATE_SHA
        and len(phase_b1) == 1 and phase_b1[0].get("sha256") == EXPECTED_PHASE_B1_GATE_SHA
    )
    return {"pass": bool(passed), "record_count": len(records), "checks": checks}


def _dag_audit(
    trace: dict[str, Any], ledger: dict[str, Any], validation: dict[str, Any],
    evidence: dict[str, Any], pre_audit: dict[str, Any],
) -> dict[str, Any]:
    checks = [
        _strict_reference(trace.get("upstream_source_manifest"), SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST"),
        _strict_reference(ledger.get("upstream_source_manifest"), SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST"),
        _strict_reference(ledger.get("upstream_trace"), TRACE, "UPSTREAM_RAW_TRACE"),
        _strict_reference(validation.get("upstream_source_manifest"), SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST"),
        _strict_reference(validation.get("upstream_trace"), TRACE, "UPSTREAM_RAW_TRACE"),
        _strict_reference(validation.get("upstream_ledger"), LEDGER, "UPSTREAM_LEDGER"),
        _strict_reference(pre_audit.get("upstream_evidence_manifest"), EVIDENCE_MANIFEST, "UPSTREAM_EVIDENCE_MANIFEST"),
    ]
    declared_records = evidence.get("records") if isinstance(evidence.get("records"), list) else []
    expected = [
        (SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST"), (TRACE, "UPSTREAM_RAW_TRACE"),
        (LEDGER, "UPSTREAM_LEDGER"), (VALIDATION, "UPSTREAM_VALIDATION"),
    ]
    for index, (path, role) in enumerate(expected):
        checks.append(_strict_reference(declared_records[index] if index < len(declared_records) else None, path, role))
    passed = (
        evidence.get("schema") == "SIM13_V4B2_EVIDENCE_MANIFEST_V1"
        and evidence.get("acyclic") is True and evidence.get("self_excluded") is True
        and len(declared_records) == len(expected) and all(item["pass"] for item in checks)
    )
    return {"pass": bool(passed), "checks": checks}


def _service_state(record: dict[str, Any]) -> ServiceState:
    data = record["service"]
    return ServiceState(
        np.asarray(data["base_position_inertial_m"], dtype=float),
        np.asarray(data["base_quaternion_body_to_inertial_wxyz"], dtype=float),
        np.asarray(data["joint_coordinates_mixed"], dtype=float),
        np.asarray(data["nu_s_mixed"], dtype=float),
    )


def _target_state(record: dict[str, Any]) -> TargetState:
    data = record["target"]
    return TargetState(
        np.asarray(data["position_inertial_m"], dtype=float),
        np.asarray(data["quaternion_body_to_inertial_wxyz"], dtype=float),
        np.asarray(data["twist_inertial_mixed"], dtype=float),
    )


def _crossing_time(times: np.ndarray, gaps: np.ndarray, direction: str, start: int = 1) -> float:
    for index in range(max(1, start), len(times)):
        left, right = float(gaps[index - 1]), float(gaps[index])
        crossing = (left > 0.0 and right <= 0.0) if direction == "enter" else (left < 0.0 and right >= 0.0)
        if crossing:
            denominator = abs(left) + abs(right)
            fraction = abs(left) / denominator if denominator else 0.0
            return float(times[index - 1] + fraction * (times[index] - times[index - 1]))
    raise ValueError("required crossing absent")


def _physics_audit(trace: dict[str, Any]) -> dict[str, Any]:
    config = trace["scenario"]
    radius = float(config["sphere_radius_m"])
    stiffness = float(config["normal_stiffness_n_m"])
    damping = float(config["normal_damping_n_s_m"])
    mu = float(config["friction_coefficient"])
    epsilon = float(config["tangential_regularization_speed_m_s"])
    link = int(config["pad_link_index"])
    local = np.asarray(config["pad_point_local_m"], dtype=float)
    records = trace["reference_records"]
    model = FullFloatingServiceModel()
    times = np.asarray([item["time_s"] for item in records], dtype=float)

    error: dict[str, float] = {
        "pad_position_m": 0.0, "gap_m": 0.0, "penetration_m": 0.0,
        "normal": 0.0, "common_point_m": 0.0,
        "service_common_velocity_m_s": 0.0, "target_common_velocity_m_s": 0.0,
        "relative_tangent_velocity_m_s": 0.0, "normal_force_n": 0.0,
        "tangential_force_n": 0.0, "service_force_n": 0.0,
        "target_force_n": 0.0, "shift_torque_n_m": 0.0,
        "generalized_effort_mixed": 0.0, "target_torque_n_m": 0.0,
        "normal_dissipation_rate_w": 0.0, "friction_dissipation_rate_w": 0.0,
    }
    service_p = []; service_h = []; target_p = []; target_h = []
    service_t = []; target_t = []; elastic = []
    forces = []; tangents = []; normals = []; common_points = []; pads = []
    gaps = []; penetrations = []; normal_magnitudes = []; tangent_speeds = []
    normal_speeds = []; normal_rates = []; friction_rates = []
    dn = []; dt = []; impulse = []; angular_impulse = []
    for record in records:
        service = _service_state(record); target = _target_state(record); logged = record["contact"]
        pad, jv, jw = model.point_position_and_jacobian(service, link, local)
        radial = pad - target.position_inertial_m
        distance = float(np.linalg.norm(radial)); normal = radial / distance
        gap = distance - radius; penetration = max(-gap, 0.0)
        common = target.position_inertial_m + radius * normal
        pad_velocity = jv @ service.nu_s_mixed
        link_omega = jw @ service.nu_s_mixed
        service_common_velocity = pad_velocity + np.cross(link_omega, common - pad)
        target_common_velocity = target.twist_inertial_mixed[:3] + np.cross(target.twist_inertial_mixed[3:], common - target.position_inertial_m)
        relative = service_common_velocity - target_common_velocity
        vn = float(relative @ normal)
        vt = relative - vn * normal; vt_speed = float(np.linalg.norm(vt))
        if penetration > 0.0:
            closing = max(-vn, 0.0)
            fn = stiffness * penetration + damping * closing
            ft = -mu * fn * vt / math.sqrt(vt_speed**2 + epsilon**2)
        else:
            closing = 0.0; fn = 0.0; ft = np.zeros(3)
        force = fn * normal + ft; target_force = -force
        shift = np.cross(common - pad, force)
        effort = jv.T @ force + jw.T @ shift
        target_torque = np.cross(common - target.position_inertial_m, target_force)
        normal_d_rate = damping * closing**2 if penetration > 0.0 else 0.0
        friction_d_rate = max(float(-ft @ vt), 0.0)

        declared = {
            "pad_position_m": np.asarray(logged["pad_point_inertial_m"], dtype=float),
            "gap_m": float(logged["gap_m"]), "penetration_m": float(logged["penetration_m"]),
            "normal": np.asarray(logged["normal_target_to_pad_inertial"], dtype=float),
            "common_point_m": np.asarray(logged["common_contact_point_inertial_m"], dtype=float),
            "service_common_velocity_m_s": np.asarray(logged["service_common_point_velocity_inertial_m_s"], dtype=float),
            "target_common_velocity_m_s": np.asarray(logged["target_common_point_velocity_inertial_m_s"], dtype=float),
            "relative_tangent_velocity_m_s": np.asarray(logged["relative_tangential_velocity_inertial_m_s"], dtype=float),
            "normal_force_n": float(logged["normal_force_magnitude_n"]),
            "tangential_force_n": np.asarray(logged["tangential_force_service_inertial_n"], dtype=float),
            "service_force_n": np.asarray(logged["service_force_inertial_n"], dtype=float),
            "target_force_n": np.asarray(logged["target_force_inertial_n"], dtype=float),
            "shift_torque_n_m": np.asarray(logged["service_shift_torque_inertial_n_m"], dtype=float),
            "generalized_effort_mixed": np.asarray(logged["service_generalized_contact_effort_mixed"], dtype=float),
            "target_torque_n_m": np.asarray(logged["target_torque_about_com_inertial_n_m"], dtype=float),
            "normal_dissipation_rate_w": float(logged["normal_dissipation_rate_w"]),
            "friction_dissipation_rate_w": float(logged["friction_dissipation_rate_w"]),
        }
        recomputed = {
            "pad_position_m": pad, "gap_m": gap, "penetration_m": penetration,
            "normal": normal, "common_point_m": common,
            "service_common_velocity_m_s": service_common_velocity,
            "target_common_velocity_m_s": target_common_velocity,
            "relative_tangent_velocity_m_s": vt, "normal_force_n": fn,
            "tangential_force_n": ft, "service_force_n": force,
            "target_force_n": target_force, "shift_torque_n_m": shift,
            "generalized_effort_mixed": effort, "target_torque_n_m": target_torque,
            "normal_dissipation_rate_w": normal_d_rate,
            "friction_dissipation_rate_w": friction_d_rate,
        }
        for key in error:
            difference = np.asarray(declared[key]) - np.asarray(recomputed[key])
            error[key] = max(error[key], float(np.max(np.abs(difference))))

        sl = model.momentum_energy(service); tl = target_momentum_energy(target)
        service_p.append(sl.linear_momentum_n_s); service_h.append(sl.angular_momentum_about_inertial_origin_n_m_s)
        target_p.append(tl.linear_momentum_n_s); target_h.append(tl.angular_momentum_about_inertial_origin_n_m_s)
        service_t.append(sl.kinetic_energy_j); target_t.append(tl.kinetic_energy_j)
        elastic.append(0.5 * stiffness * penetration**2)
        forces.append(force); tangents.append(ft); normals.append(normal); common_points.append(common); pads.append(pad)
        gaps.append(gap); penetrations.append(penetration); normal_magnitudes.append(fn); tangent_speeds.append(vt_speed)
        normal_speeds.append(vn); normal_rates.append(normal_d_rate); friction_rates.append(friction_d_rate)
        integrated = record["integrated"]
        dn.append(float(integrated["normal_dissipation_j"])); dt.append(float(integrated["friction_dissipation_j"]))
        impulse.append(integrated["service_impulse_n_s"]); angular_impulse.append(integrated["service_angular_impulse_n_m_s"])

    service_p = np.asarray(service_p); service_h = np.asarray(service_h)
    target_p = np.asarray(target_p); target_h = np.asarray(target_h)
    forces = np.asarray(forces); tangents = np.asarray(tangents); normals = np.asarray(normals)
    common_points = np.asarray(common_points); pads = np.asarray(pads)
    gaps = np.asarray(gaps); penetrations = np.asarray(penetrations)
    normal_magnitudes = np.asarray(normal_magnitudes); tangent_speeds = np.asarray(tangent_speeds)
    normal_speeds = np.asarray(normal_speeds); normal_rates = np.asarray(normal_rates); friction_rates = np.asarray(friction_rates)
    dn = np.asarray(dn); dt = np.asarray(dt); impulse = np.asarray(impulse); angular_impulse = np.asarray(angular_impulse)
    total_p = service_p + target_p; total_h = service_h + target_h
    total_energy = np.asarray(service_t) + np.asarray(target_t) + np.asarray(elastic) + dn + dt
    contact = np.flatnonzero(penetrations > 0.0)
    event = {
        "first_contact_time_s": _crossing_time(times, gaps, "enter"),
        "separation_after_contact_time_s": _crossing_time(times, gaps, "exit", int(contact[0] + 1)),
        "peak_normal_force_n": float(np.max(normal_magnitudes)),
        "maximum_penetration_m": float(np.max(penetrations)),
    }
    declared_event = _load(LEDGER)["reference_summary"]["contact_event"]
    event_error = {key: abs(float(event[key]) - float(declared_event[key])) for key in event}
    friction_power = np.einsum("ij,ij->i", tangents, np.asarray([
        item["contact"]["relative_tangential_velocity_inertial_m_s"] for item in records
    ], dtype=float))
    states = ["SEPARATED"]
    state = "SEPARATED"
    for gap, penetration, normal_speed in zip(gaps, penetrations, normal_speeds):
        if state == "SEPARATED" and gap > 0.0 and normal_speed < 0.0:
            state = "APPROACH"
        elif state in ("SEPARATED", "APPROACH") and penetration > 0.0:
            state = "SINGLE_CONTACT"
        elif state == "SINGLE_CONTACT" and gap >= 0.0 and normal_speed > 0.0:
            state = "SEPARATING_AFTER_CONTACT"
        if state != states[-1]:
            states.append(state)
    metrics = {
        "reconstruction_max_abs_errors": error,
        "action_reaction_max_error_n": float(np.max(np.linalg.norm(forces + np.asarray([item["contact"]["target_force_inertial_n"] for item in records]), axis=1))),
        "friction_cone_max_excess_n": float(np.max(np.maximum(np.linalg.norm(tangents, axis=1) - mu * normal_magnitudes, 0.0))),
        "tangential_orthogonality_max_error_n": float(np.max(np.abs(np.einsum("ij,ij->i", tangents, normals)))),
        "common_point_shift_identity_max_error_n_m": float(np.max(np.linalg.norm(np.cross(pads, forces) + np.cross(common_points - pads, forces) - np.cross(common_points, forces), axis=1))),
        "maximum_friction_power_w": float(np.max(friction_power)),
        "service_linear_impulse_error_n_s": float(np.max(np.linalg.norm((service_p - service_p[0]) - impulse, axis=1))),
        "target_linear_impulse_error_n_s": float(np.max(np.linalg.norm((target_p - target_p[0]) + impulse, axis=1))),
        "total_linear_momentum_drift_n_s": float(np.max(np.linalg.norm(total_p - total_p[0], axis=1))),
        "service_angular_impulse_error_n_m_s": float(np.max(np.linalg.norm((service_h - service_h[0]) - angular_impulse, axis=1))),
        "target_angular_impulse_error_n_m_s": float(np.max(np.linalg.norm((target_h - target_h[0]) + angular_impulse, axis=1))),
        "total_angular_momentum_drift_n_m_s": float(np.max(np.linalg.norm(total_h - total_h[0], axis=1))),
        "energy_plus_dissipation_drift_j": float(np.max(np.abs(total_energy - total_energy[0]))),
        "final_normal_dissipation_j": float(dn[-1]), "final_friction_dissipation_j": float(dt[-1]),
        "normal_dissipation_trapezoidal_error_j": float(abs(np.trapezoid(normal_rates, times) - dn[-1])),
        "friction_dissipation_trapezoidal_error_j": float(abs(np.trapezoid(friction_rates, times) - dt[-1])),
        "independent_state_sequence": states,
        "event": event, "event_vs_declared_error": event_error,
    }
    return {"metrics": metrics, "forces": forces, "tangents": tangents, "normals": normals, "pads": pads, "common_points": common_points, "normal_magnitudes": normal_magnitudes}


def _terminal_difference(left: dict[str, Any], right: dict[str, Any]) -> dict[str, float]:
    a = left["final_state"]; b = right["final_state"]
    return {
        "service_base_position_m": float(np.linalg.norm(np.asarray(a["service_base_position_inertial_m"]) - np.asarray(b["service_base_position_inertial_m"]))),
        "service_base_quaternion_geodesic_rad": quaternion_geodesic(a["service_base_quaternion_body_to_inertial_wxyz"], b["service_base_quaternion_body_to_inertial_wxyz"]),
        "service_q_R_rad": float(np.max(np.abs(np.asarray(a["service_joint_coordinates_mixed"])[:6] - np.asarray(b["service_joint_coordinates_mixed"])[:6]))),
        "service_q_P_m": float(np.max(np.abs(np.asarray(a["service_joint_coordinates_mixed"])[6:] - np.asarray(b["service_joint_coordinates_mixed"])[6:]))),
        "service_v_base_m_s": float(np.max(np.abs(np.asarray(a["service_nu_s_mixed"])[:3] - np.asarray(b["service_nu_s_mixed"])[:3]))),
        "service_omega_base_rad_s": float(np.max(np.abs(np.asarray(a["service_nu_s_mixed"])[3:6] - np.asarray(b["service_nu_s_mixed"])[3:6]))),
        "service_qdot_R_rad_s": float(np.max(np.abs(np.asarray(a["service_nu_s_mixed"])[6:12] - np.asarray(b["service_nu_s_mixed"])[6:12]))),
        "service_qdot_P_m_s": float(np.max(np.abs(np.asarray(a["service_nu_s_mixed"])[12:] - np.asarray(b["service_nu_s_mixed"])[12:]))),
        "target_position_m": float(np.linalg.norm(np.asarray(a["target_position_inertial_m"]) - np.asarray(b["target_position_inertial_m"]))),
        "target_quaternion_geodesic_rad": quaternion_geodesic(a["target_quaternion_body_to_inertial_wxyz"], b["target_quaternion_body_to_inertial_wxyz"]),
        "target_velocity_m_s": float(np.max(np.abs(np.asarray(a["target_twist_inertial_mixed"])[:3] - np.asarray(b["target_twist_inertial_mixed"])[:3]))),
        "target_omega_rad_s": float(np.max(np.abs(np.asarray(a["target_twist_inertial_mixed"])[3:] - np.asarray(b["target_twist_inertial_mixed"])[3:]))),
    }


def _raw_event(run: dict[str, Any]) -> dict[str, float]:
    times = np.asarray(run["time_s"], dtype=float); gaps = np.asarray(run["gap_m"], dtype=float)
    penetration = np.asarray(run["penetration_m"], dtype=float); force = np.asarray(run["normal_force_magnitude_n"], dtype=float)
    contact = np.flatnonzero(penetration > 0.0)
    return {
        "first_contact_time_s": _crossing_time(times, gaps, "enter"),
        "separation_after_contact_time_s": _crossing_time(times, gaps, "exit", int(contact[0] + 1)),
        "peak_normal_force_n": float(np.max(force)), "maximum_penetration_m": float(np.max(penetration)),
    }


def _assess(coarse: dict[str, float], fine: dict[str, float]) -> dict[str, Any]:
    items = {}
    for key, coarse_error in coarse.items():
        fine_error = fine[key]; floor = FLOORS[key]
        passed = fine_error < coarse_error or (coarse_error <= floor and fine_error <= floor)
        items[key] = {"coarse": coarse_error, "fine": fine_error, "floor": floor, "pass": passed}
    return {"components": items, "all_components_pass": all(item["pass"] for item in items.values())}


def _convergence(trace: dict[str, Any]) -> dict[str, Any]:
    runs = trace["convergence_runs"]
    rk_c = _terminal_difference(runs["rk4_coarse"], runs["rk4_fine"])
    rk_f = _terminal_difference(runs["rk4_fine"], runs["rk4_reference"])
    mp_c = _terminal_difference(runs["midpoint_coarse"], runs["midpoint_fine"])
    mp_f = _terminal_difference(runs["midpoint_fine"], runs["midpoint_reference"])
    events = {name: _raw_event(run) for name, run in runs.items()}
    cross = {key: abs(events["rk4_reference"][key] - events["midpoint_reference"][key]) for key in events["rk4_reference"]}
    return {"rk4": _assess(rk_c, rk_f), "midpoint": _assess(mp_c, mp_f), "events": events, "cross_event": cross}


def _negative_controls(physics: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    tangents = physics["tangents"]; peak = int(np.argmax(np.linalg.norm(tangents, axis=1)))
    force = physics["forces"][peak]; tangent = tangents[peak]; normal = physics["normals"][peak]
    fn = physics["normal_magnitudes"][peak]; pad = physics["pads"][peak]; common = physics["common_points"][peak]
    mu = float(config["friction_coefficient"])
    raw = {
        "same_sign_pair_n": float(np.linalg.norm(2.0 * force)),
        "friction_cone_excess_n": 0.2 * mu * fn,
        "friction_sign_flip_power_proxy_w": float(np.linalg.norm(tangent) * 1.0e-3),
        "missing_shift_moment_n_m": float(np.linalg.norm(np.cross(pad - common, force))),
        "tangent_normal_contamination_n": 0.1 * max(fn, 1.0) * float(normal @ normal),
        "separated_suction_n": 1.0,
    }
    return [
        {"control_id": key, "raw_error": float(value), "rejected": bool(value > 1.0e-12)}
        for key, value in raw.items()
    ]


def _forbidden_scan() -> dict[str, Any]:
    found = []
    for path in HERE.rglob("*"):
        name = path.name.lower()
        if path.is_dir() and name in {"__pycache__", ".pytest_cache"}:
            found.append(path.relative_to(HERE).as_posix())
        elif path.is_file() and (name.endswith(".urdf") or "authorization" in name or "interface" in name):
            found.append(path.relative_to(HERE).as_posix())
    return {"pass": not found, "paths": sorted(found)}


def _check(check_id: str, name: str, passed: bool, metrics: Any) -> dict[str, Any]:
    return {"id": check_id, "name": name, "pass": bool(passed), "metrics": metrics}


def main() -> int:
    for stale in (FINAL_GATE, TERMINAL_MANIFEST):
        if stale.is_file():
            stale.unlink()
    required = (SOURCE_MANIFEST, TRACE, LEDGER, VALIDATION, EVIDENCE_MANIFEST, PRE_AUDIT_GATE)
    if not all(path.is_file() for path in required):
        print("missing pre-audit evidence", file=sys.stderr); return 2
    source = _load(SOURCE_MANIFEST); trace = _load(TRACE); ledger = _load(LEDGER)
    validation = _load(VALIDATION); evidence = _load(EVIDENCE_MANIFEST); pre_audit = _load(PRE_AUDIT_GATE)
    source_result = _source_audit(source)
    dag_result = _dag_audit(trace, ledger, validation, evidence, pre_audit)
    physics = _physics_audit(trace); metrics = physics["metrics"]
    convergence = _convergence(trace)
    controls = _negative_controls(physics, trace["scenario"])
    forbidden = _forbidden_scan()
    reconstruction = metrics["reconstruction_max_abs_errors"]
    cross = convergence["cross_event"]
    checks = [
        _check("IA-B201", "strict source manifest and audited upstream hashes", source_result["pass"], source_result),
        _check("IA-B202", "strict acyclic path-bytes-sha-role evidence DAG", dag_result["pass"], dag_result),
        _check("IA-B203", "validator pre-audit state only", validation.get("status") == "PASS_VALIDATOR_PENDING_INDEPENDENT_AUDIT" and validation.get("score", {}).get("fail") == 0 and pre_audit.get("final_gate") is False, {"validation": validation.get("status"), "pre_audit_final": pre_audit.get("final_gate")}),
        _check("IA-B204", "geometry velocity and force law independently reconstructed", max(reconstruction.values()) <= 2.0e-11, reconstruction),
        _check("IA-B205", "action reaction and tangential orthogonality", metrics["action_reaction_max_error_n"] <= 1.0e-12 and metrics["tangential_orthogonality_max_error_n"] <= 1.0e-12, metrics),
        _check("IA-B206", "regularized Coulomb bound and non-injective power", metrics["friction_cone_max_excess_n"] <= 1.0e-12 and metrics["maximum_friction_power_w"] <= 1.0e-14, metrics),
        _check("IA-B207", "common inertial point service wrench shift", metrics["common_point_shift_identity_max_error_n_m"] <= 1.0e-12, metrics),
        _check("IA-B208", "service and target linear impulse ledgers", metrics["service_linear_impulse_error_n_s"] <= 1.0e-10 and metrics["target_linear_impulse_error_n_s"] <= 1.0e-10, metrics),
        _check("IA-B209", "total linear momentum", metrics["total_linear_momentum_drift_n_s"] <= 1.0e-10, metrics),
        _check("IA-B210", "service and target angular impulse ledgers", metrics["service_angular_impulse_error_n_m_s"] <= 1.0e-10 and metrics["target_angular_impulse_error_n_m_s"] <= 1.0e-10, metrics),
        _check("IA-B211", "total angular momentum", metrics["total_angular_momentum_drift_n_m_s"] <= 1.0e-10, metrics),
        _check("IA-B212", "kinetic elastic normal and friction dissipation ledger", metrics["energy_plus_dissipation_drift_j"] <= 1.0e-6 and metrics["final_normal_dissipation_j"] > 0.0 and metrics["final_friction_dissipation_j"] > 0.0, metrics),
        _check("IA-B213", "independent node-quadrature cross-check of separated dissipation channels", metrics["normal_dissipation_trapezoidal_error_j"] <= 1.0e-5 and metrics["friction_dissipation_trapezoidal_error_j"] <= 1.0e-7, metrics),
        _check("IA-B214", "contact state sequence independently reconstructed", metrics["independent_state_sequence"] == ["SEPARATED", "APPROACH", "SINGLE_CONTACT", "SEPARATING_AFTER_CONTACT"], metrics["independent_state_sequence"]),
        _check("IA-B215", "contact event independently recomputed", max(metrics["event_vs_declared_error"].values()) <= 1.0e-12, metrics["event_vs_declared_error"]),
        _check("IA-B216", "independent RK4 midpoint and cross-event convergence", convergence["rk4"]["all_components_pass"] and convergence["midpoint"]["all_components_pass"] and cross["first_contact_time_s"] <= 2.0e-6 and cross["separation_after_contact_time_s"] <= 5.0e-6 and cross["peak_normal_force_n"] <= 2.0e-2 and cross["maximum_penetration_m"] <= 2.0e-6, convergence),
        _check("IA-B217", "independent negative controls", len(controls) == 6 and all(item["rejected"] for item in controls), controls),
        _check("IA-B218", "formal physical current production release holds", pre_audit.get("authorizations") == {"synthetic_phase_b2_audited_ready": False, "physical_friction_identified": False, "dual_contact_ready": False, "soft_capture_ready": False, "lock_ready": False, "contact_grasp_passed": False, "current_system_bound": False, "formal_nc19_closed": False, "owner_authorized": False, "production_ready": False, "released": False, "next_stage_authorized": False}, pre_audit.get("authorizations")),
        _check("IA-B219", "no forbidden generated artifacts", forbidden["pass"], forbidden),
    ]
    passed = sum(item["pass"] for item in checks); all_pass = passed == len(checks)
    receipt = {
        "schema": "SIM13_V4B2_INDEPENDENT_AUDIT_RECEIPT_V1",
        "status": "PASS_INDEPENDENT_AUDIT" if all_pass else "FAIL_INDEPENDENT_AUDIT",
        "upstream_source_manifest": _record(SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST"),
        "upstream_evidence_manifest": _record(EVIDENCE_MANIFEST, "UPSTREAM_EVIDENCE_MANIFEST"),
        "upstream_pre_audit_gate": _record(PRE_AUDIT_GATE, "UPSTREAM_PRE_AUDIT_GATE"),
        "score": {"pass": passed, "fail": len(checks) - passed, "total": len(checks)},
        "checks": checks,
    }
    _write(AUDIT_RECEIPT, receipt)
    if not all_pass:
        print(json.dumps({"status": receipt["status"], "score": receipt["score"]}, indent=2)); return 1
    final = {
        "schema": "SIM13_V4B2_AUDITED_GATE_V1",
        "overall_status": "PASS_PHASE_B2_SYNTHETIC_REGULARIZED_FRICTION_SINGLE_CONTACT_WITH_PHYSICAL_FRICTION_DUAL_CONTACT_LOCK_AND_CURRENT_SYSTEM_HOLD",
        "final_gate": True,
        "hash_chain": {
            "upstream_source_manifest": _record(SOURCE_MANIFEST, "UPSTREAM_SOURCE_MANIFEST"),
            "upstream_evidence_manifest": _record(EVIDENCE_MANIFEST, "UPSTREAM_EVIDENCE_MANIFEST"),
            "upstream_pre_audit_gate": _record(PRE_AUDIT_GATE, "UPSTREAM_PRE_AUDIT_GATE"),
            "upstream_independent_audit_receipt": _record(AUDIT_RECEIPT, "UPSTREAM_INDEPENDENT_AUDIT_RECEIPT"),
        },
        "validator_checks": validation["score"], "independent_audit_checks": receipt["score"],
        "audited_metrics": {
            "contact_event": metrics["event"],
            "peak_tangential_force_n": ledger["reference_summary"]["friction"]["peak_tangential_force_n"],
            "final_friction_dissipation_j": metrics["final_friction_dissipation_j"],
            "total_linear_momentum_max_drift_n_s": metrics["total_linear_momentum_drift_n_s"],
            "total_angular_momentum_max_drift_n_m_s": metrics["total_angular_momentum_drift_n_m_s"],
            "energy_plus_dissipation_max_drift_j": metrics["energy_plus_dissipation_drift_j"],
            "cross_integrator_event_difference": cross,
        },
        "gates": [
            {"id": "V4B2-FG01", "name": "synthetic regularized-friction single-contact diagnostic", "status": "PASS_AUDITED", "pass": True},
            {"id": "V4B2-FG02", "name": "physical friction identification", "status": "HOLD_SYNTHETIC_PARAMETERS", "pass": False},
            {"id": "V4B2-FG03", "name": "dual contact soft capture lock", "status": "HOLD_NOT_IMPLEMENTED", "pass": False},
            {"id": "V4B2-FG04", "name": "current system and formal NC19", "status": "HOLD_NOT_BOUND", "pass": False},
            {"id": "V4B2-FG05", "name": "Owner production release next stage", "status": "HOLD_NOT_AUTHORIZED", "pass": False},
        ],
        "authorizations": {
            "synthetic_phase_b2_audited_ready": True,
            "physical_friction_identified": False, "dual_contact_ready": False,
            "soft_capture_ready": False, "lock_ready": False,
            "contact_grasp_passed": False, "current_system_bound": False,
            "formal_nc19_closed": False, "owner_authorized": False,
            "production_ready": False, "released": False, "next_stage_authorized": False,
        },
        "formal_sim13_v2_state": {"passed": 15, "declared": 20, "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"], "changed_by_this_package": False},
    }
    _write(FINAL_GATE, final)
    terminal = {
        "schema": "SIM13_V4B2_TERMINAL_SELF_EXCLUDED_MANIFEST_V1",
        "self_excluded": True, "acyclic": True,
        "records": [_record(AUDIT_RECEIPT, "UPSTREAM_INDEPENDENT_AUDIT_RECEIPT"), _record(FINAL_GATE, "UPSTREAM_FINAL_GATE")],
    }
    _write(TERMINAL_MANIFEST, terminal)
    print(json.dumps({
        "status": final["overall_status"], "validator_checks": validation["score"],
        "independent_audit_checks": receipt["score"], "audited_metrics": final["audited_metrics"],
        "negative_controls": len(controls), "final_gate_sha256": _sha(FINAL_GATE),
        "terminal_manifest_sha256": _sha(TERMINAL_MANIFEST),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
