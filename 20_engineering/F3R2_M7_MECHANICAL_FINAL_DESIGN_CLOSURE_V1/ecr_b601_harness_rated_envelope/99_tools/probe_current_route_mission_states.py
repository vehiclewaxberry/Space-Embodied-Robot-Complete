# -*- coding: utf-8 -*-
"""Exact, read-only key-state probe for the frozen B601 harness candidate.

This wrapper imports the existing R2-HRN-05 geometry kernel without editing it.
It deliberately uses the same collision fields, tube-radius class value,
bend-radius class value, FK and signed-distance semantics as the 308-state V2
negative result.  Its purpose is to determine whether Route B is worth mapping
before a larger adaptive sweep is launched.

Run with FreeCADCmd.exe, not ordinary Python.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import yaml


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
M7 = PACKAGE.parent
PROJECT = M7.parents[1]
KERNEL_PATH = M7 / "ecr_solar_array_r2" / "sweep_b601_harness_full_fk.py"
POSE_PATH = (
    PROJECT
    / "20_engineering"
    / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
    / "04_configurations"
    / "F3R2_ARM_INITIAL_POSE.yaml"
)
CONTROL_PATH = PROJECT / "20_engineering" / "config" / "control_scene" / "control_01_v0.yaml"
V2_PATH = M7 / "ecr_solar_array_r2" / "HARNESS_B601_FULL_FK_SWEEP_V2.json"
OUT = PACKAGE / "02_exact_predicate" / "CURRENT_ROUTE_KEY_STATE_PROBE_V1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def now_local() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def load_kernel():
    spec = importlib.util.spec_from_file_location("b601_harness_v2_kernel", KERNEL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen harness kernel")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_context(k):
    arm = k.ArmModel(k.URDF, k.load_mount())
    fields_local = {}
    verts_local = {}
    for link in k.ARM_LINKS:
        tris = k.mesh_tris(k.STL_DIR / (link + ".STL"))
        fields_local[link] = k.TriField(link, tris)
        verts_local[link] = np.unique(np.round(tris.reshape(-1, 3), 3), axis=0)

    bus = k.BoxField("BUS_PROXY", (-170.25, -113.15, -113.15), (170.25, 113.15, 113.15))
    solar = k.TriField(
        "SOLAR_R2_DEPLOYED",
        k.shape_tris(k.Part.read(str(k.SOLAR_STEP)), 0.3),
    )

    gripper_field = fields_local["gripper_link"]
    palm_tris = k.shape_tris(k.Part.read(str(k.PALM_SLOT_STEP)), 0.25)
    palm_vertices = palm_tris.reshape(-1, 3)
    palm_vertices = palm_vertices[:: max(1, len(palm_vertices) // 2000)]
    palm_median_mm = float(
        np.median(np.asarray([gripper_field.min_dist(p)[0] for p in palm_vertices]))
    )
    rail_fields = []
    if palm_median_mm < 3.0:
        for rail_path in k.RAIL_STEPS:
            rail_fields.append(
                k.TriField(
                    rail_path.stem,
                    k.shape_tris(k.Part.read(str(rail_path)), 0.25),
                )
            )
    rail_vertices = np.vstack([f.v0 for f in rail_fields]) if rail_fields else None
    design = k.HarnessDesign(
        arm,
        verts_local,
        rail_vertices,
        fields_local=fields_local,
        rail_fields=rail_fields,
        bus_field=bus,
    )
    return {
        "arm": arm,
        "fields": fields_local,
        "bus": bus,
        "solar": solar,
        "rails": rail_fields,
        "design": design,
        "palm_frame_validation_median_mm": palm_median_mm,
    }


def field_minimum(k, field, points_local):
    lower = field.aabb_lb(points_local)
    candidates = np.where(lower < field.D + 5.0)[0]
    if len(candidates) == 0:
        return float(lower.min()) - k.TUBE_R, 0, 1
    best = math.inf
    exact = 0
    bounded = 0
    for index in candidates:
        value = k.signed_clearance_point(field, points_local[index])
        if value is None:
            bounded += 1
            continue
        exact += 1
        best = min(best, float(value))
    if not math.isfinite(best):
        return None, exact, bounded
    return best, exact, bounded


def evaluate_state(k, ctx, state_id: str, q_rad):
    q = np.asarray(q_rad, dtype=float)
    arm = ctx["arm"]
    design = ctx["design"]
    transforms = arm.fk_S(q)
    points, required_length, min_radius, min_radius_where, sections = design.build(q)

    per_field = {}
    exact_queries = 0
    bounded_queries = 0
    comparisons = 0
    for field, points_local in ((ctx["bus"], points), (ctx["solar"], points)):
        value, exact, bounded = field_minimum(k, field, points_local)
        per_field[field.name] = value
        exact_queries += exact
        bounded_queries += bounded
        comparisons += 1
    for link in k.ARM_LINKS:
        transform = transforms[link]
        points_local = (points - transform[:3, 3]) @ transform[:3, :3]
        value, exact, bounded = field_minimum(k, ctx["fields"][link], points_local)
        per_field[link] = value
        exact_queries += exact
        bounded_queries += bounded
        comparisons += 1
    gripper_transform = transforms["gripper_link"]
    for field in ctx["rails"]:
        points_local = (points - gripper_transform[:3, 3]) @ gripper_transform[:3, :3]
        value, exact, bounded = field_minimum(k, field, points_local)
        per_field[field.name] = value
        exact_queries += exact
        bounded_queries += bounded
        comparisons += 1

    finite_clearances = [v for v in per_field.values() if v is not None and math.isfinite(v)]
    clearance = min(finite_clearances) if finite_clearances else None

    pinch_per_joint = {}
    empty_sets = 0
    for joint in arm.rev:
        joint_name = joint["name"]
        crossing = design.crossings[joint_name]
        joint_frame = transforms[joint["parent"]] @ arm.origin_T(joint)
        points_joint = (points - joint_frame[:3, 3]) @ joint_frame[:3, :3]
        axial = points_joint @ crossing["a"]
        mask = np.abs(axial - crossing["station"]) <= 40.0
        if not mask.any():
            pinch_per_joint[joint_name] = None
            empty_sets += 1
            continue
        band = points_joint[mask]
        best = math.inf
        for link in (joint["parent"], joint["child"]):
            mapping = np.linalg.inv(transforms[link]) @ joint_frame
            local_band = band @ mapping[:3, :3].T + mapping[:3, 3]
            field = ctx["fields"][link]
            for point in local_band:
                value = k.signed_clearance_point(field, point)
                if value is not None:
                    best = min(best, float(value))
        pinch_per_joint[joint_name] = best if math.isfinite(best) else None

    finite_pinch = [v for v in pinch_per_joint.values() if v is not None and math.isfinite(v)]
    pinch = min(finite_pinch) if finite_pinch else None
    provisioned_length = float(
        json.loads(V2_PATH.read_text(encoding="utf-8"))["results"]["length_provisioned_derived_mm"]
    )
    length_margin = provisioned_length - float(required_length)
    bend_margin = float(min_radius) - float(k.BEND_CLASS)
    joint_margin = min(
        min(q[i] - joint["lo"], joint["hi"] - q[i])
        for i, joint in enumerate(arm.rev)
    )
    margins = {
        "clearance_mm": clearance,
        "bend_radius_mm": float(min_radius),
        "bend_margin_mm": bend_margin,
        "pinch_mm": pinch,
        "length_required_mm": float(required_length),
        "length_available_mm": provisioned_length,
        "length_margin_mm": length_margin,
        "joint_limit_margin_rad": float(joint_margin),
    }
    known = all(
        margins[key] is not None and math.isfinite(float(margins[key]))
        for key in ("clearance_mm", "bend_margin_mm", "pinch_mm", "length_margin_mm", "joint_limit_margin_rad")
    )
    safe = bool(
        known
        and clearance >= 0.0
        and bend_margin >= 0.0
        and pinch >= 0.0
        and length_margin >= 0.0
        and joint_margin >= 0.0
        and empty_sets == 0
    )
    status = "SAFE" if safe else ("UNSAFE" if known else "UNKNOWN")
    return {
        "state_id": state_id,
        "q_rad": [float(v) for v in q],
        "status": status,
        "margins": margins,
        "minimum_bend_location": min_radius_where,
        "per_field_clearance_mm": per_field,
        "per_joint_pinch_mm": pinch_per_joint,
        "empty_comparison_sets": empty_sets,
        "comparison_fields": comparisons,
        "exact_distance_queries": exact_queries,
        "lower_bound_only_queries": bounded_queries,
        "sections": sections,
    }


def main():
    k = load_kernel()
    ctx = build_context(k)
    poses = yaml.safe_load(POSE_PATH.read_text(encoding="utf-8"))["poses"]
    control = yaml.safe_load(CONTROL_PATH.read_text(encoding="utf-8"))
    pregrasp = control["trajectories"]["T2"]["q_initial_rad"]
    states = {
        "Q_AS_BUILT_REFERENCE": poses["Q_AS_BUILT_REFERENCE"]["q_rad"],
        "ARM_STOWED_ONORBIT_C05": poses["Q_STOW_ENGINEERING_CANDIDATE"]["q_rad"],
        "ARM_RELEASE_CLEAR": poses["Q_RELEASE_CLEAR"]["q_rad"],
        "Q_DEPLOYED_HOME": poses["Q_DEPLOYED_HOME"]["q_rad"],
        "ARM_TASK_READY_C06": poses["Q_SERVICE_READY"]["q_rad"],
        "PREGRASP": pregrasp,
        "CONTACT": pregrasp,
        "CAPTURE_22KG": pregrasp,
        "POST_CAPTURE_22KG": pregrasp,
        "PHYSICS_VETO_150KG": pregrasp,
        "SAFE_RECOVERY_TARGET": poses["Q_DEPLOYED_HOME"]["q_rad"],
    }
    results = [evaluate_state(k, ctx, name, q) for name, q in states.items()]
    route_b_key_states_pass = all(item["status"] == "SAFE" for item in results)
    design = ctx["design"]
    design_debug = {
        "spans_link_local": {
            link: {
                "start_mm": [float(v) for v in value[0][0]],
                "end_mm": [float(v) for v in value[0][-1]],
                "sample_count": int(len(value[0])),
                "length_mm": float(value[1]),
                "min_radius_mm": float(value[2]),
                "design_margin_mm": float(value[3]),
                "straight": bool(value[4]),
                "construction_debug": getattr(design, "_span_debug", {}).get(link),
            }
            for link, value in design.spans.items()
        },
        "spines_link_local_mm": {
            link: [[float(v) for v in point] for point in spine]
            for link, spine in design.spines.items()
        },
        "link_mesh_bounds_local_mm": {
            link: {
                "min": [float(v) for v in values.min(axis=0)],
                "max": [float(v) for v in values.max(axis=0)],
            }
            for link, values in design.verts_local.items()
        },
    }
    report = {
        "schema": "CURRENT_ROUTE_KEY_STATE_PROBE_V1",
        "generated_local": now_local(),
        "role": "PRE_ENVELOPE_EXACT_FALSIFICATION_PROBE",
        "authority": "ODR-35..41; geometry semantics inherited unchanged from R2-HRN-05",
        "inputs_sha256": {
            str(KERNEL_PATH.relative_to(PROJECT)): sha256(KERNEL_PATH),
            str(k.URDF.relative_to(PROJECT)): sha256(k.URDF),
            str(k.SOLAR_STEP.relative_to(PROJECT)): sha256(k.SOLAR_STEP),
            str(POSE_PATH.relative_to(PROJECT)): sha256(POSE_PATH),
            str(CONTROL_PATH.relative_to(PROJECT)): sha256(CONTROL_PATH),
            str(V2_PATH.relative_to(PROJECT)): sha256(V2_PATH),
        },
        "accepted_urdf_limits_unchanged": True,
        "candidate_class_values": {
            "tube_radius_mm": k.TUBE_R,
            "bend_radius_required_mm": k.BEND_CLASS,
            "note": "candidate class values, not vendor qualification data",
        },
        "palm_frame_validation_median_mm": ctx["palm_frame_validation_median_mm"],
        "states_total": len(results),
        "states_safe": sum(r["status"] == "SAFE" for r in results),
        "states_unsafe": sum(r["status"] == "UNSAFE" for r in results),
        "states_unknown": sum(r["status"] == "UNKNOWN" for r in results),
        "route_b_key_state_screen": "PASS_CONTINUE_TO_TRAJECTORY_MAPPING" if route_b_key_states_pass else "FAIL_ROUTE_B_KEY_STATE_CONTAINMENT",
        "decision_rule": "all mandatory key states must be SAFE before a trajectory envelope can pass",
        "design_debug": design_debug,
        "results": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(OUT),
        "states_safe": report["states_safe"],
        "states_unsafe": report["states_unsafe"],
        "states_unknown": report["states_unknown"],
        "route_b_key_state_screen": report["route_b_key_state_screen"],
    }, indent=2))


if __name__ == "__main__" or (
    len(__import__("sys").argv) > 1
    and Path(__import__("sys").argv[1]).stem == __name__
):
    main()
