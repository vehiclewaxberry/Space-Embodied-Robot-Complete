"""Revalidate named B601 joint vectors against the current accepted URDF.

This is a kinematics and digital inertia recomputation only.  It intentionally
does not promote collision, physical-fit, or flight authority.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from datetime import datetime
from pathlib import Path

import numpy as np
import yaml


WORKSPACE = Path(__file__).resolve().parents[3]
M4 = Path(__file__).resolve().parents[1]
URDF = WORKSPACE / "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
POSES = WORKSPACE / "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/04_configurations/F3R2_ARM_INITIAL_POSE.yaml"
SCENE = WORKSPACE / "20_engineering/config/visualization/scene_manifest_v1.yaml"
MODEL = WORKSPACE / "30_simulation/sim_05_free_floating_arm/b601_model.py"
OUTPUT = M4 / "11_validation/B601_NAMED_POSE_REVALIDATION_V1.json"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def load_model():
    spec = importlib.util.spec_from_file_location("m4_b601_model", MODEL)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load model module: {MODEL}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tensor_record(matrix: np.ndarray) -> list[list[float]]:
    return [[float(value) for value in row] for row in matrix]


def load_scene_candidate() -> dict[str, object]:
    """Read only the frozen numeric fields from a legacy YAML-like manifest.

    The source contains an unquoted colon in a prose continuation and is not
    valid YAML 1.2.  Parsing the three named fields prevents any repair or
    mutation of that controlled source.
    """
    text = SCENE.read_text(encoding="utf-8")
    q_match = re.search(r"q_rad:\s*\[([^\]]+)\]", text, flags=re.DOTALL)
    case_match = re.search(r"case_id:\s*([^\s#]+)", text)
    capture_match = re.search(r"capture_point_S_m:\s*\[([^\]]+)\]", text)
    if not (q_match and case_match and capture_match):
        raise RuntimeError("cannot locate frozen scene candidate fields")
    parse_vector = lambda value: [float(item.strip()) for item in value.split(",")]
    return {
        "q_rad": parse_vector(q_match.group(1)),
        "case_id": case_match.group(1),
        "capture_point_S_m": parse_vector(capture_match.group(1)),
    }


def main() -> int:
    raw = URDF.read_bytes()
    pose_document = yaml.safe_load(POSES.read_text(encoding="utf-8"))
    scene_candidate_source = load_scene_candidate()
    model = load_model()
    arm = model.B601Arm(str(URDF))

    base_rows = np.asarray(pose_document["mount"]["transform_mm_rows"], dtype=float)
    base_transform = base_rows.copy()
    base_transform[:3, 3] /= 1000.0

    joint_limits = np.array(
        [[arm.joints_all[name]["lower"], arm.joints_all[name]["upper"]]
         for name in model.CHAIN_JOINTS],
        dtype=float,
    )
    position_tolerance_mm = 0.01
    pose_results: dict[str, object] = {}
    mandatory_pose_checks_pass = True
    held_pose_failures: list[str] = []
    for name, pose in pose_document["poses"].items():
        q = np.asarray(pose["q_rad"], dtype=float)
        limits_pass = bool(np.all(q >= joint_limits[:, 0]) and np.all(q <= joint_limits[:, 1]))
        fk = arm.fk(q, T_base=base_transform)
        computed_ee_mm = fk["T_E"][:3, 3] * 1000.0
        source_ee_mm = np.asarray(pose["end_effector_position_mm"], dtype=float)
        residual_mm = computed_ee_mm - source_ee_mm
        max_abs_residual_mm = float(np.max(np.abs(residual_mm)))
        fk_pass = max_abs_residual_mm <= position_tolerance_mm

        bodies = []
        base = arm.body["base_link"]
        bodies.append(model.transform_inertial(
            base_transform, base["mass"], base["cg"], base["I"]
        ))
        for state in arm.link_com_states(q, T_base=base_transform):
            bodies.append((state["mass"], state["c"], state["I"]))
        mass, com, inertia = model.combine_inertials(bodies)
        eigenvalues = np.linalg.eigvalsh(inertia)
        principal_triangle_pass = bool(
            eigenvalues[0] + eigenvalues[1] >= eigenvalues[2] - 1.0e-12
        )
        inertia_pass = bool(np.all(eigenvalues > 0.0) and principal_triangle_pass)
        pose_check_pass = limits_pass and fk_pass and inertia_pass
        if bool(pose["runtime"]) or name == "Q_AS_BUILT_REFERENCE":
            mandatory_pose_checks_pass &= pose_check_pass
        elif not pose_check_pass:
            held_pose_failures.append(name)
        pose_results[name] = {
            "source_runtime": bool(pose["runtime"]),
            "source_hold": pose.get("hold"),
            "q_rad": [float(value) for value in q],
            "joint_limits_pass": limits_pass,
            "computed_end_effector_position_S_mm": [float(value) for value in computed_ee_mm],
            "source_end_effector_position_S_mm": [float(value) for value in source_ee_mm],
            "position_residual_mm": [float(value) for value in residual_mm],
            "max_abs_position_residual_mm": max_abs_residual_mm,
            "position_tolerance_mm": position_tolerance_mm,
            "fk_regression_pass": fk_pass,
            "gate_role": (
                "MANDATORY_RUNTIME_POSE"
                if bool(pose["runtime"])
                else ("MANDATORY_REFERENCE_POSE" if name == "Q_AS_BUILT_REFERENCE" else "HELD_CANDIDATE")
            ),
            "digital_arm_mass_kg": float(mass),
            "digital_arm_center_of_mass_S_m": [float(value) for value in com],
            "digital_arm_inertia_about_arm_com_S_kg_m2": tensor_record(inertia),
            "principal_moments_kg_m2": [float(value) for value in eigenvalues],
            "inertia_positive_definite_and_triangle_pass": inertia_pass,
            "classification": "DIGITAL_MODEL_DERIVED",
            "uncertainty": None,
            "uncertainty_status": "HOLD_NOT_A_PHYSICAL_MEASUREMENT",
        }

    scene_q = np.asarray(scene_candidate_source["q_rad"], dtype=float)
    scene_limits_pass = bool(
        np.all(scene_q >= joint_limits[:, 0]) and np.all(scene_q <= joint_limits[:, 1])
    )
    scene_base = model.T_SM_4x4()
    scene_fk = arm.fk(scene_q, T_base=scene_base)
    scene_ee = scene_fk["T_E"][:3, 3]
    scene_capture = np.asarray(scene_candidate_source["capture_point_S_m"], dtype=float)
    scene_residual = scene_ee - scene_capture
    scene_bodies = []
    base = arm.body["base_link"]
    scene_bodies.append(model.transform_inertial(
        scene_base, base["mass"], base["cg"], base["I"]
    ))
    for state in arm.link_com_states(scene_q, T_base=scene_base):
        scene_bodies.append((state["mass"], state["c"], state["I"]))
    scene_mass, scene_com, scene_inertia = model.combine_inertials(scene_bodies)
    scene_eigenvalues = np.linalg.eigvalsh(scene_inertia)
    scene_candidate = {
        "source": SCENE.relative_to(WORKSPACE).as_posix(),
        "case_id": scene_candidate_source["case_id"],
        "q_rad": [float(value) for value in scene_q],
        "joint_limits_pass": scene_limits_pass,
        "computed_end_effector_position_S_m": [float(value) for value in scene_ee],
        "declared_capture_point_S_m": [float(value) for value in scene_capture],
        "position_residual_m": [float(value) for value in scene_residual],
        "max_abs_position_residual_m": float(np.max(np.abs(scene_residual))),
        "digital_arm_mass_kg": float(scene_mass),
        "digital_arm_center_of_mass_S_m": [float(value) for value in scene_com],
        "digital_arm_inertia_about_arm_com_S_kg_m2": tensor_record(scene_inertia),
        "principal_moments_kg_m2": [float(value) for value in scene_eigenvalues],
        "classification": "GEOMETRIC_PREGRASP_CANDIDATE_FOR_DEBRIS_E1P5",
        "target_22kg_dynamics_validated": False,
        "target_150kg_dynamics_validated": False,
        "status": "DIAGNOSTIC_CANDIDATE_HOLD_FOR_CAPTURE_DYNAMICS",
    }

    output = {
        "schema": "B601_NAMED_POSE_REVALIDATION_V1",
        "generated_local": datetime.now().astimezone().isoformat(),
        "accepted_urdf": {
            "path": URDF.relative_to(WORKSPACE).as_posix(),
            "raw_crlf_sha256": sha256_bytes(raw),
            "lf_normalized_sha256": sha256_bytes(raw.replace(b"\r\n", b"\n")),
            "source_pose_declared_sha256": pose_document["kinematics_authority"]["sha256"],
            "line_ending_equivalence_pass": (
                sha256_bytes(raw.replace(b"\r\n", b"\n"))
                == pose_document["kinematics_authority"]["sha256"]
            ),
        },
        "pose_source": POSES.relative_to(WORKSPACE).as_posix(),
        "mass_property_method": "URDF link inertials + current joint FK + rigid combination by parallel-axis theorem",
        "base_transform_source": "F3R2_ARM_INITIAL_POSE_V1.mount.transform_mm_rows",
        "pose_count": len(pose_results),
        "mandatory_runtime_and_reference_pose_checks_pass": mandatory_pose_checks_pass,
        "held_pose_failures": held_pose_failures,
        "pregrasp_scene_candidate": scene_candidate,
        "collision_revalidated": False,
        "physical_fitup_revalidated": False,
        "pose_results": pose_results,
        "release_boundary": (
            "Named runtime vectors may support bounded digital kinematics and inertia studies. "
            "Each source HOLD remains in force; no contact, physical-fit, or flight authority is created."
        ),
        "status": (
            "PASS_RUNTIME_DIGITAL_KINEMATICS_WITH_HELD_CANDIDATE_FAILURES"
            if mandatory_pose_checks_pass and held_pose_failures
            else ("PASS_DIGITAL_KINEMATICS_SCOPE" if mandatory_pose_checks_pass else "HOLD")
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "pose_count": output["pose_count"],
        "line_ending_equivalence_pass": output["accepted_urdf"]["line_ending_equivalence_pass"],
        "status": output["status"],
        "max_residual_mm": max(
            result["max_abs_position_residual_mm"] for result in pose_results.values()
        ),
    }, indent=2))
    return 0 if output["status"].startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
