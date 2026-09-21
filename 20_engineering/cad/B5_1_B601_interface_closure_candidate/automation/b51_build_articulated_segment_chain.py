"""Build a native SolidWorks B601 serial chain from rigid segment subassemblies.

Each segment SLDASM contains the accepted vendor link geometry plus fixed,
hidden interface datum components.  The top-level SLDASM contains only rigid
segment subassemblies and six (or a requested prefix of six) native revolute
mate pairs.  This avoids the solver ambiguity observed when visuals and datum
parts were connected by top-level lock mates.

The accepted URDF remains the kinematic and mass authority.  CAD automatic mass
is explicitly excluded.  The composite G08 visual remains fixed to link6 and
its two prismatic finger joints stay on HOLD.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

sys.dont_write_bytecode = True

CANDIDATE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import b51_build_articulated_b601 as legacy  # noqa: E402
import b51_sw_rev_smoke as smoke  # noqa: E402
import b51_sw_segment_rev_smoke as segment_smoke  # noqa: E402

core = smoke.core
NATIVE_ROOT = CANDIDATE_ROOT / "03_CAD" / "native_articulated"
VERIFY_ROOT = CANDIDATE_ROOT / "07_VERIFICATION" / "articulation"
TRACE_PATH: Path | None = None
LIMIT_TOL_RAD = 1.0e-12
BUILD_SIGN_DELTA_RAD = math.radians(1.0)
REOPEN_SIGN_DELTA_RAD = math.radians(0.5)
RANDOM_SEED_BASE = 6015100
CAD_FK_TOLERANCE = 2.0e-7


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trace(event: str, **data: Any) -> None:
    if TRACE_PATH is None:
        return
    payload = {"utc": _utc_now(), "event": event, **data}
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TRACE_PATH.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
        stream.flush()


def _stage_inputs(
    run_root: Path, max_joints: int
) -> dict[str, Path]:
    roles = ["base_link"] + [
        f"link{index}" for index in range(1, max_joints + 1)
    ]
    if max_joints == 6:
        roles.append("gripper_link")
    target_root = run_root / "inputs" / "vendor_link_parts"
    target_root.mkdir(parents=True, exist_ok=True)
    staged: dict[str, Path] = {}
    for role in roles:
        source = legacy.VISUAL_PARTS[role]
        if not source.is_file():
            raise core.Phase0Error(f"vendor visual missing: {source}")
        target = target_root / source.name
        if target.exists():
            raise core.Phase0Error(f"immutable staged input exists: {target}")
        shutil.copy2(source, target)
        if legacy._sha256(source) != legacy._sha256(target):
            raise core.Phase0Error(f"staged vendor hash mismatch: {role}")
        staged[role] = target
    return staged


def _create_segment(
    session: core.SolidWorksSession,
    run_root: Path,
    *,
    index: int,
    link_role: str,
    child_specs: list[dict[str, Any]],
) -> tuple[Path, dict[str, Any]]:
    target = (
        run_root
        / "segments"
        / f"B51_SEGMENT_{index}_{link_role.upper()}.SLDASM"
    )
    model = session.new_document("assembly")
    insertions: list[dict[str, Any]] = []
    for child in child_specs:
        _, record = legacy._insert_component(
            session,
            model,
            child["path"],
            child["transform"],
            fixed=True,
            role=child["role"],
        )
        insertions.append(record)
    if not model.ForceRebuild3(True):
        raise core.Phase0Error(f"segment rebuild failed: {target.name}")
    session.set_text_properties(
        model,
        {
            "OBJECT_ID": f"B51_SEGMENT_{index}_{link_role.upper()}",
            "ASSET_ROLE": "B51_RIGID_ARTICULATED_LINK_SEGMENT",
            "LINK_ROLE": link_role,
            "SEGMENT_INDEX": str(index),
            "KINEMATIC_AUTHORITY": (
                f"ACCEPTED_URDF_SHA256_{legacy.EXPECTED_URDF_SHA256}"
            ),
            "MASS_AUTHORITY": (
                f"ACCEPTED_URDF_{legacy.ACCEPTED_URDF_MASS_KG}_KG_"
                "CAD_AUTO_MASS_NOT_AUTHORIZED"
            ),
            "G08_2P_STATUS": (
                "B51_2P_GRIPPER_PARTITION_AND_ZERO_CALIBRATION_HOLD"
            ),
            "CLAIM_LIMIT": (
                "ENGINEERING_ARTICULATION_SEGMENT_NOT_FLIGHT_OR_"
                "MANUFACTURING_READY"
            ),
        },
    )
    save = session.save_as(model, target, require_zero_warnings=False)
    component_names = sorted(
        str(core.get_com_member(component, "Name2"))
        for component in list(
            session.cast(model, "IAssemblyDoc").GetComponents(False) or []
        )
    )
    session.close_all_documents()
    return target, {
        "index": index,
        "link_role": link_role,
        "child_component_names": component_names,
        "child_count": len(component_names),
        "insertions": insertions,
        "save": save,
    }


def _build_segment_files(
    session: core.SolidWorksSession,
    run_root: Path,
    chain: dict[str, Any],
    staged: dict[str, Path],
    female_path: Path,
    male_path: Path,
    max_joints: int,
) -> tuple[dict[str, Path], dict[str, Any]]:
    paths: dict[str, Path] = {}
    records: dict[str, Any] = {}
    z_back = legacy._transform(
        np.asarray([0.0, 0.0, -0.002], dtype=float)
    )
    for index in range(0, max_joints + 1):
        link_role = "base_link" if index == 0 else f"link{index}"
        specs: list[dict[str, Any]] = [
            {
                "path": staged[link_role],
                "transform": np.eye(4, dtype=float),
                "role": f"VENDOR_VISUAL_{link_role}",
            }
        ]
        if index > 0:
            specs.append(
                {
                    "path": male_path,
                    "transform": np.eye(4, dtype=float),
                    "role": f"J{index}_MALE_CHILD_DATUM",
                }
            )
        if index < max_joints:
            outgoing_joint = chain["joints"][index]
            specs.append(
                {
                    "path": female_path,
                    "transform": (
                        legacy._origin_transform(outgoing_joint) @ z_back
                    ),
                    "role": f"J{index + 1}_FEMALE_PARENT_DATUM",
                }
            )
        if index == 6:
            specs.append(
                {
                    "path": staged["gripper_link"],
                    "transform": legacy._origin_transform(
                        chain["fixed_gripper"]
                    ),
                    "role": "VENDOR_VISUAL_gripper_link_FIXED_G08",
                }
            )
        path, record = _create_segment(
            session,
            run_root,
            index=index,
            link_role=link_role,
            child_specs=specs,
        )
        paths[link_role] = path
        records[link_role] = record
        _trace(
            "RIGID_SEGMENT_SAVED",
            index=index,
            link_role=link_role,
            path=str(path),
            child_count=record["child_count"],
        )
    return paths, records


def _fk_unbounded(
    chain: dict[str, Any],
    q: list[float],
    max_joints: int,
) -> dict[str, np.ndarray]:
    if len(q) != max_joints:
        raise core.Phase0Error(
            f"expected {max_joints} q values, got {len(q)}"
        )
    result = {"base_link": np.eye(4, dtype=float)}
    for item, angle in zip(chain["joints"][:max_joints], q):
        parent = result[item["parent"]]
        rotation = legacy._transform(
            rotation=legacy._axis_angle_matrix(
                item["axis"], float(angle)
            )
        )
        result[item["child"]] = (
            parent @ legacy._origin_transform(item) @ rotation
        )
    if max_joints == 6:
        fixed = chain["fixed_gripper"]
        result["gripper_link"] = (
            result[fixed["parent"]] @ legacy._origin_transform(fixed)
        )
    return result


def _top_role(index: int) -> str:
    return "base_link" if index == 0 else f"link{index}"


def _find_nested(
    session: core.SolidWorksSession,
    segment_component: Any,
    token: str,
) -> Any:
    children = [
        session.cast(child, "IComponent2")
        for child in list(segment_component.GetChildren() or [])
    ]
    matches = [
        child
        for child in children
        if token.upper()
        in str(core.get_com_member(child, "Name2")).upper()
    ]
    if len(matches) != 1:
        names = [
            str(core.get_com_member(child, "Name2"))
            for child in children
        ]
        raise core.Phase0Error(
            f"nested lookup failed token={token!r}, names={names}"
        )
    return matches[0]


def _nested_map(
    session: core.SolidWorksSession,
    segments: dict[str, Any],
    max_joints: int,
) -> tuple[dict[str, Any], dict[int, Any], dict[int, Any]]:
    visuals: dict[str, Any] = {}
    female: dict[int, Any] = {}
    male: dict[int, Any] = {}
    for index in range(0, max_joints + 1):
        role = _top_role(index)
        token = (
            "BASE_LINK_LINKLOCAL"
            if index == 0
            else f"LINK{index}_LINKLOCAL"
        )
        visuals[role] = _find_nested(
            session, segments[role], token
        )
        if index > 0:
            male[index] = _find_nested(
                session, segments[role], "DATUM_MALE"
            )
        if index < max_joints:
            female[index + 1] = _find_nested(
                session, segments[role], "DATUM_FEMALE"
            )
    if max_joints == 6:
        visuals["gripper_link"] = _find_nested(
            session, segments["link6"], "GRIPPER_DETAIL_LINKLOCAL"
        )
    return visuals, female, male


def _remaining_dofs(component: Any) -> dict[str, Any]:
    raw = component.GetRemainingDOFs()
    if isinstance(raw, tuple):
        result = int(raw[0])
        slots = []
        for index in range(1, len(raw), 2):
            count = int(raw[index])
            entity = raw[index + 1] if index + 1 < len(raw) else None
            slots.append(
                {
                    "count": count,
                    "entity_present": entity is not None,
                    "entity_repr": None if entity is None else repr(entity),
                }
            )
    else:
        result = int(raw)
        slots = []
    return {
        "raw": repr(raw),
        "result": result,
        "parsed_slots": slots,
    }


def _total_array(component: Any) -> list[float]:
    transform = component.GetTotalTransform(True)
    if transform is None:
        transform = core.get_com_member(component, "Transform2")
    return [
        float(value)
        for value in core.get_com_member(transform, "ArrayData")
    ]


def _verify_pose(
    segments: dict[str, Any],
    visuals: dict[str, Any],
    expected: dict[str, np.ndarray],
    max_joints: int,
    *,
    tolerance: float = CAD_FK_TOLERANCE,
) -> dict[str, Any]:
    segment_items: dict[str, Any] = {}
    visual_items: dict[str, Any] = {}
    maximum = 0.0
    for index in range(0, max_joints + 1):
        role = _top_role(index)
        target = legacy._matrix_array(expected[role])
        actual_segment = legacy._component_array(segments[role])
        actual_visual = _total_array(visuals[role])
        segment_error = legacy._max_error(actual_segment, target)
        visual_error = legacy._max_error(actual_visual, target)
        maximum = max(maximum, segment_error, visual_error)
        segment_items[role] = {
            "max_abs_error": segment_error,
            "translation_m": actual_segment[9:12],
        }
        visual_items[role] = {
            "max_abs_error": visual_error,
            "translation_m": actual_visual[9:12],
        }
    if max_joints == 6:
        target = legacy._matrix_array(expected["gripper_link"])
        actual = _total_array(visuals["gripper_link"])
        error = legacy._max_error(actual, target)
        maximum = max(maximum, error)
        visual_items["gripper_link"] = {
            "max_abs_error": error,
            "translation_m": actual[9:12],
        }
    result = {
        "max_abs_error": maximum,
        "segments": segment_items,
        "vendor_visuals": visual_items,
    }
    if maximum > tolerance:
        raise core.Phase0Error(f"segment-chain CAD FK mismatch: {result}")
    return result


def _apply_exact_pose(
    session: core.SolidWorksSession,
    model: Any,
    segments: dict[str, Any],
    visuals: dict[str, Any],
    chain: dict[str, Any],
    q: list[float],
    max_joints: int,
    label: str,
) -> dict[str, Any]:
    expected = _fk_unbounded(chain, q, max_joints)
    assembly = session.cast(model, "IAssemblyDoc")
    initial_rebuild = bool(assembly.EnableAssemblyRebuild)
    if initial_rebuild:
        assembly.EnableAssemblyRebuild = False
        raise core.Phase0Error(
            "unexpected suspended assembly rebuild state on exact-pose entry"
        )
    writes: list[dict[str, Any]] = []
    pre_rebuild_segments: dict[str, Any] = {}
    pre_rebuild_maximum = 0.0
    try:
        # SOLIDWORKS API: True suspends rebuild; False resumes it.
        assembly.EnableAssemblyRebuild = True
        if not bool(assembly.EnableAssemblyRebuild):
            raise core.Phase0Error(
                f"cannot suspend assembly rebuild for exact pose: {label}"
            )
        for index in range(1, max_joints + 1):
            role = f"link{index}"
            transform = legacy._math_transform(
                session, expected[role]
            )
            segments[role].Transform2 = transform
            actual = legacy._component_array(segments[role])
            target = legacy._matrix_array(expected[role])
            writes.append(
                {
                    "role": role,
                    "immediate_max_abs_error": legacy._max_error(
                        actual, target
                    ),
                }
            )
        for index in range(1, max_joints + 1):
            role = f"link{index}"
            actual = legacy._component_array(segments[role])
            target = legacy._matrix_array(expected[role])
            error = legacy._max_error(actual, target)
            pre_rebuild_maximum = max(pre_rebuild_maximum, error)
            pre_rebuild_segments[role] = {
                "max_abs_error": error,
                "translation_m": actual[9:12],
            }
        if pre_rebuild_maximum > CAD_FK_TOLERANCE:
            raise core.Phase0Error(
                "pre-rebuild exact-pose write mismatch: "
                f"{label}: {pre_rebuild_segments}"
            )
    finally:
        assembly.EnableAssemblyRebuild = False
        if bool(assembly.EnableAssemblyRebuild):
            raise core.Phase0Error(
                f"cannot resume assembly rebuild after exact pose: {label}"
            )
    if not model.ForceRebuild3(True):
        raise core.Phase0Error(f"exact pose rebuild failed: {label}")
    readback = _verify_pose(
        segments, visuals, expected, max_joints
    )
    return {
        "label": label,
        "q_rad": [float(value) for value in q],
        "writes": writes,
        "write_order": [f"link{index}" for index in range(1, max_joints + 1)],
        "assembly_rebuild_control": {
            "rebuild_suspension_before": initial_rebuild,
            "rebuild_suspension_during": True,
            "rebuild_suspension_after": bool(
                assembly.EnableAssemblyRebuild
            ),
            "semantics": (
                "TRUE_SUSPENDS_REBUILD_FALSE_RESUMES_REBUILD"
            ),
        },
        "pre_rebuild_readback": {
            "max_abs_error": pre_rebuild_maximum,
            "segments": pre_rebuild_segments,
        },
        "rebuild_api": "ForceRebuild3(True)",
        "readback": readback,
    }


def _set_and_solve(
    session: core.SolidWorksSession,
    model: Any,
    component: Any,
    target: np.ndarray,
) -> dict[str, Any]:
    transform = legacy._math_transform(session, target)
    try:
        api_ok = bool(component.SetTransformAndSolve3(transform, True))
        api = "SetTransformAndSolve3"
    except Exception:
        api_ok = bool(component.SetTransformAndSolve2(transform))
        api = "SetTransformAndSolve2"
    rebuild_ok = bool(model.EditRebuild3())
    return {
        "api": api,
        "api_ok": api_ok,
        "rebuild_ok": rebuild_ok,
        "target_transform": legacy._matrix_array(target),
        "component_readback": legacy._component_array(component),
    }


def _sign_drive(
    session: core.SolidWorksSession,
    model: Any,
    segments: dict[str, Any],
    visuals: dict[str, Any],
    chain: dict[str, Any],
    max_joints: int,
    joint_index: int,
    angle_rad: float,
) -> dict[str, Any]:
    q0 = [0.0] * max_joints
    _apply_exact_pose(
        session,
        model,
        segments,
        visuals,
        chain,
        q0,
        max_joints,
        f"RESET_Q0_BEFORE_J{joint_index}_SIGN",
    )
    q = [0.0] * max_joints
    q[joint_index - 1] = angle_rad
    coordinated = _apply_exact_pose(
        session,
        model,
        segments,
        visuals,
        chain,
        q,
        max_joints,
        f"COORDINATED_J{joint_index}_SIGN_POSE",
    )
    joint = chain["joints"][joint_index - 1]
    return {
        "joint_index": joint_index,
        "joint_name": joint["name"],
        "angle_rad": angle_rad,
        "angle_deg": math.degrees(angle_rad),
        "within_accepted_limit_from_q0": (
            angle_rad >= float(joint["lower"])
            and angle_rad <= float(joint["upper"])
        ),
        "drive_method": (
            "COORDINATED_CHAIN_TRANSFORM_WITH_NATIVE_MATE_REBUILD"
        ),
        "single_component_solver_propagation_authority": False,
        "coordinated_pose": coordinated,
        "readback": coordinated["readback"],
    }


def _classify_q0_direction(
    chain: dict[str, Any],
    joint_index: int,
    angle_rad: float,
) -> dict[str, Any]:
    joint = chain["joints"][joint_index - 1]
    lower = float(joint["lower"])
    upper = float(joint["upper"])
    candidate = float(angle_rad)
    legal = (
        candidate >= lower - LIMIT_TOL_RAD
        and candidate <= upper + LIMIT_TOL_RAD
    )
    return {
        "joint_index": joint_index,
        "joint_name": joint["name"],
        "direction": "POSITIVE" if angle_rad > 0.0 else "NEGATIVE",
        "q0_rad": 0.0,
        "commanded_delta_rad": float(angle_rad),
        "commanded_delta_deg": math.degrees(angle_rad),
        "candidate_q_rad": candidate,
        "accepted_limit_rad": {"lower": lower, "upper": upper},
        "limit_tolerance_rad": LIMIT_TOL_RAD,
        "legal_from_q0": legal,
    }


def _exercise_q0_directions(
    session: core.SolidWorksSession,
    model: Any,
    segments: dict[str, Any],
    visuals: dict[str, Any],
    chain: dict[str, Any],
    max_joints: int,
    *,
    delta_rad: float,
    phase: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for index in range(1, max_joints + 1):
        for angle in (abs(delta_rad), -abs(delta_rad)):
            classification = _classify_q0_direction(
                chain, index, angle
            )
            if classification["legal_from_q0"]:
                drive = _sign_drive(
                    session,
                    model,
                    segments,
                    visuals,
                    chain,
                    max_joints,
                    index,
                    angle,
                )
                item = {
                    **classification,
                    "solver_write_attempted": True,
                    "rejection_layer": None,
                    "status": "LEGAL_DIRECTION_DRIVE_PASS",
                    "drive_result": drive,
                }
                _trace(
                    f"{phase}_LEGAL_DIRECTION_DRIVE_PASS",
                    joint_index=index,
                    direction=classification["direction"],
                    angle_deg=classification["commanded_delta_deg"],
                    max_abs_error=drive["readback"]["max_abs_error"],
                )
            else:
                item = {
                    **classification,
                    "solver_write_attempted": False,
                    "rejection_layer": "ACCEPTED_URDF_LIMIT_PRECHECK",
                    "status": (
                        "ILLEGAL_DIRECTION_REJECTED_BY_ACCEPTED_"
                        "URDF_LIMIT_PRECHECK"
                    ),
                }
                _trace(
                    f"{phase}_ILLEGAL_DIRECTION_PRECHECK_REJECTION_PASS",
                    joint_index=index,
                    direction=classification["direction"],
                    candidate_q_rad=classification["candidate_q_rad"],
                    accepted_limit_rad=classification[
                        "accepted_limit_rad"
                    ],
                )
            checks.append(item)
    legal_expected = sum(
        bool(
            _classify_q0_direction(chain, index, angle)[
                "legal_from_q0"
            ]
        )
        for index in range(1, max_joints + 1)
        for angle in (abs(delta_rad), -abs(delta_rad))
    )
    summary = {
        "phase": phase,
        "delta_rad": float(abs(delta_rad)),
        "delta_deg": math.degrees(abs(delta_rad)),
        "total_expected": 2 * max_joints,
        "total_observed": len(checks),
        "legal_expected": legal_expected,
        "legal_passed": sum(
            item["status"] == "LEGAL_DIRECTION_DRIVE_PASS"
            for item in checks
        ),
        "illegal_expected": 2 * max_joints - legal_expected,
        "illegal_rejected": sum(
            item["status"].startswith(
                "ILLEGAL_DIRECTION_REJECTED"
            )
            and not item["solver_write_attempted"]
            for item in checks
        ),
    }
    summary["coverage_pass"] = (
        summary["total_observed"] == summary["total_expected"]
        and summary["legal_passed"] == summary["legal_expected"]
        and summary["illegal_rejected"] == summary["illegal_expected"]
    )
    if not summary["coverage_pass"]:
        raise core.Phase0Error(
            f"{phase} q0 direction coverage failed: {summary}"
        )
    return checks, summary


def _validate_q_vector_limits(
    chain: dict[str, Any],
    q: list[float],
    max_joints: int,
) -> dict[str, Any]:
    if len(q) != max_joints:
        raise core.Phase0Error(
            f"q vector length {len(q)} != {max_joints}"
        )
    records: list[dict[str, Any]] = []
    for index, (joint, value) in enumerate(
        zip(chain["joints"][:max_joints], q), start=1
    ):
        lower = float(joint["lower"])
        upper = float(joint["upper"])
        legal = (
            float(value) >= lower - LIMIT_TOL_RAD
            and float(value) <= upper + LIMIT_TOL_RAD
        )
        records.append(
            {
                "joint_index": index,
                "joint_name": joint["name"],
                "q_rad": float(value),
                "lower_rad": lower,
                "upper_rad": upper,
                "legal": legal,
            }
        )
    result = {
        "authority": "ACCEPTED_URDF",
        "method": "PRE_SOLVER_Q_VECTOR_GATE",
        "all_legal": all(item["legal"] for item in records),
        "records": records,
    }
    if not result["all_legal"]:
        raise core.Phase0Error(f"q vector violates accepted limits: {result}")
    return result


def _perpendicular_axis(axis: np.ndarray) -> np.ndarray:
    normalized = np.asarray(axis, dtype=float)
    normalized = normalized / np.linalg.norm(normalized)
    trial = np.asarray([1.0, 0.0, 0.0], dtype=float)
    if abs(float(np.dot(normalized, trial))) > 0.9:
        trial = np.asarray([0.0, 1.0, 0.0], dtype=float)
    perpendicular = np.cross(normalized, trial)
    return perpendicular / np.linalg.norm(perpendicular)


def _off_axis_drive(
    session: core.SolidWorksSession,
    model: Any,
    segments: dict[str, Any],
    visuals: dict[str, Any],
    chain: dict[str, Any],
    max_joints: int,
    joint_index: int,
) -> dict[str, Any]:
    q0 = [0.0] * max_joints
    reset = _apply_exact_pose(
        session,
        model,
        segments,
        visuals,
        chain,
        q0,
        max_joints,
        f"RESET_Q0_BEFORE_J{joint_index}_OFF_AXIS",
    )
    expected = _fk_unbounded(chain, q0, max_joints)
    joint = chain["joints"][joint_index - 1]
    perpendicular = _perpendicular_axis(joint["axis"])
    perturbation = legacy._transform(
        rotation=legacy._axis_angle_matrix(
            perpendicular, math.radians(0.75)
        )
    )
    target = expected[f"link{joint_index}"] @ perturbation
    drive = _set_and_solve(
        session,
        model,
        segments[f"link{joint_index}"],
        target,
    )
    readback = _verify_pose(
        segments, visuals, expected, max_joints
    )
    return {
        "joint_index": joint_index,
        "joint_name": joint["name"],
        "commanded_off_axis_deg": 0.75,
        "joint_axis_local": [
            float(value) for value in joint["axis"]
        ],
        "off_axis_local": [
            float(value) for value in perpendicular
        ],
        "reset": reset,
        "drive": drive,
        "readback_after_rejection": readback,
    }


def _constraint_readback(
    segments: dict[str, Any], max_joints: int
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for index in range(0, max_joints + 1):
        role = _top_role(index)
        component = segments[role]
        item = {
            "constrained_status": int(component.GetConstrainedStatus()),
            "fixed": bool(core.get_com_member(component, "IsFixed")),
            "remaining_dofs": (
                None if index == 0 else _remaining_dofs(component)
            ),
        }
        if index == 0:
            if (
                item["constrained_status"] != 3
                or not item["fixed"]
            ):
                raise core.Phase0Error(
                    f"base segment constraint mismatch: {item}"
                )
        else:
            if (
                item["constrained_status"]
                != smoke.SW_UNDER_CONSTRAINED
            ):
                raise core.Phase0Error(
                    f"{role} is not under-constrained: {item}"
                )
            if (
                item["remaining_dofs"]["result"]
                != smoke.SW_REMAINING_DOFS_RESTRICTED
            ):
                raise core.Phase0Error(
                    f"{role} remaining DOFs not restricted: {item}"
                )
        result[role] = item
    return result


def _create_pose_configurations(
    session: core.SolidWorksSession,
    model: Any,
    segments: dict[str, Any],
    visuals: dict[str, Any],
    chain: dict[str, Any],
    max_joints: int,
) -> dict[str, Any] | None:
    if max_joints != 6:
        return None
    q0 = [0.0] * max_joints
    q0_set = _apply_exact_pose(
        session,
        model,
        segments,
        visuals,
        chain,
        q0,
        max_joints,
        "CONFIG_Q0_PREP",
    )
    manager = core.get_com_member(model, "ConfigurationManager")
    active = core.get_com_member(manager, "ActiveConfiguration")
    active.Name = "Q0_ACCEPTED"
    for name, comment in (
        (
            "FREE_6R_ENGINEERING",
            "Six native revolute DOFs; coordinated pose control uses the "
            "accepted URDF while native mates retain the revolute topology.",
        ),
        (
            "STOW_V2_CANDIDATE_HOLD",
            "Vendor-derived STOW v2 candidate; packaging and continuous "
            "clearance remain HOLD.",
        ),
    ):
        if manager.AddConfiguration2(
            name, comment, "", 0, "", False, False
        ) is None:
            raise core.Phase0Error(f"AddConfiguration2 failed: {name}")
    if not model.ShowConfiguration2("STOW_V2_CANDIDATE_HOLD"):
        raise core.Phase0Error(
            "cannot activate STOW_V2_CANDIDATE_HOLD"
        )
    stow_q = [float(value) for value in legacy.STOW_V2_RAD]
    stow_set = _apply_exact_pose(
        session,
        model,
        segments,
        visuals,
        chain,
        stow_q,
        max_joints,
        "CONFIG_STOW_V2",
    )
    if not model.ShowConfiguration2("Q0_ACCEPTED"):
        raise core.Phase0Error("cannot reactivate Q0_ACCEPTED")
    if not model.ForceRebuild3(True):
        raise core.Phase0Error("Q0 configuration rebuild failed")
    q0_readback = _verify_pose(
        segments,
        visuals,
        _fk_unbounded(chain, q0, max_joints),
        max_joints,
    )
    if not model.ShowConfiguration2("STOW_V2_CANDIDATE_HOLD"):
        raise core.Phase0Error(
            "cannot reactivate STOW_V2_CANDIDATE_HOLD"
        )
    if not model.ForceRebuild3(True):
        raise core.Phase0Error("STOW configuration rebuild failed")
    stow_readback = _verify_pose(
        segments,
        visuals,
        _fk_unbounded(chain, stow_q, max_joints),
        max_joints,
    )
    names = sorted(
        str(value) for value in list(model.GetConfigurationNames() or [])
    )
    expected = sorted(
        [
            "FREE_6R_ENGINEERING",
            "Q0_ACCEPTED",
            "STOW_V2_CANDIDATE_HOLD",
        ]
    )
    if names != expected:
        raise core.Phase0Error(
            f"configuration set mismatch: {names} != {expected}"
        )
    return {
        "names": names,
        "active": str(
            core.get_com_member(
                manager, "ActiveConfiguration"
            ).Name
        ),
        "control_method": (
            "ASSEMBLY_CONFIGURATION_SPECIFIC_COORDINATED_SEGMENT_"
            "POSITIONS_WITH_NATIVE_REVOLUTE_MATES"
        ),
        "q0_set": q0_set,
        "q0_readback": q0_readback,
        "stow_set": stow_set,
        "stow_readback": stow_readback,
        "status": "CONFIGURATION_POSE_PERSISTENCE_PASS_PRE_SAVE",
    }


def _build_top_level(
    session: core.SolidWorksSession,
    run_root: Path,
    chain: dict[str, Any],
    segment_paths: dict[str, Path],
    max_joints: int,
    random_samples: int,
) -> tuple[Path, dict[str, Any]]:
    target = (
        run_root
        / "assembly"
        / (
            "B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM"
            if max_joints == 6
            else f"B51_B601_ARTICULATED_PREFIX_{max_joints}R.SLDASM"
        )
    )
    pretest_target = (
        run_root
        / "assembly"
        / (
            "B51_B601_ARTICULATED_ENGINEERING_ARM_PRETEST.SLDASM"
            if max_joints == 6
            else f"B51_B601_ARTICULATED_PREFIX_{max_joints}R_PRETEST.SLDASM"
        )
    )
    model = session.new_document("assembly")
    assembly = session.cast(model, "IAssemblyDoc")
    q0 = [0.0] * max_joints
    q0_fk = _fk_unbounded(chain, q0, max_joints)
    segments: dict[str, Any] = {}
    insertions: dict[str, Any] = {}
    for index in range(0, max_joints + 1):
        role = _top_role(index)
        component, record = segment_smoke._insert_subassembly(
            session,
            model,
            segment_paths[role],
            q0_fk[role],
            fixed=(index == 0),
            role=f"RIGID_SEGMENT_{index}_{role}",
        )
        segments[role] = component
        insertions[role] = record
        _trace(
            "TOP_SEGMENT_INSERTED",
            index=index,
            role=role,
            component_name=record["component_name"],
        )
    visuals, female, male = _nested_map(
        session, segments, max_joints
    )
    mates: list[dict[str, Any]] = []
    topology: dict[str, Any] = {}
    for index in range(1, max_joints + 1):
        female_cyl, female_plane, female_topology = (
            smoke._datum_entities(session, female[index])
        )
        male_cyl, male_plane, male_topology = smoke._datum_entities(
            session, male[index]
        )
        topology[f"joint{index}"] = {
            "female": female_topology,
            "male": male_topology,
        }
        joint_mates = [
            legacy._add_entity_mate(
                session,
                model,
                assembly,
                female_cyl,
                male_cyl,
                legacy.SW_MATE_CONCENTRIC,
                legacy.SW_MATE_ALIGN_ALIGNED,
                f"J{index}_SEGMENT_CONCENTRIC",
            ),
            legacy._add_entity_mate(
                session,
                model,
                assembly,
                female_plane,
                male_plane,
                legacy.SW_MATE_COINCIDENT,
                legacy.SW_MATE_ALIGN_ANTI_ALIGNED,
                f"J{index}_SEGMENT_COINCIDENT",
            ),
        ]
        mates.extend(joint_mates)
        if not model.EditRebuild3():
            raise core.Phase0Error(
                f"joint{index} segment mate rebuild failed"
            )
        _trace(
            "TOP_JOINT_MATES_CREATED",
            joint_index=index,
            mates=joint_mates,
        )
    if not model.ForceRebuild3(True):
        raise core.Phase0Error("top segment chain rebuild failed")
    for component in [*female.values(), *male.values()]:
        component.Visible = legacy.SW_COMPONENT_HIDDEN
    q0_readback = _verify_pose(
        segments, visuals, q0_fk, max_joints
    )
    constraint_readback = _constraint_readback(
        segments, max_joints
    )
    pretest_save = session.save_as(
        model, pretest_target, require_zero_warnings=True
    )
    _trace(
        "TOP_CHAIN_PRETEST_SAVED",
        path=str(pretest_target),
        save=pretest_save,
    )
    direction_checks, direction_summary = _exercise_q0_directions(
        session,
        model,
        segments,
        visuals,
        chain,
        max_joints,
        delta_rad=BUILD_SIGN_DELTA_RAD,
        phase="BUILD",
    )
    off_axis_checks: list[dict[str, Any]] = []
    for index in range(1, max_joints + 1):
        off_axis = _off_axis_drive(
            session,
            model,
            segments,
            visuals,
            chain,
            max_joints,
            index,
        )
        off_axis_checks.append(off_axis)
        _trace(
            "JOINT_OFF_AXIS_REJECTION_PASS",
            joint_index=index,
            max_abs_error=off_axis[
                "readback_after_rejection"
            ]["max_abs_error"],
        )
    random_seed = RANDOM_SEED_BASE + max_joints
    rng = random.Random(random_seed)
    random_checks: list[dict[str, Any]] = []
    for sample_index in range(random_samples):
        q: list[float] = []
        for joint in chain["joints"][:max_joints]:
            lower = float(joint["lower"])
            upper = float(joint["upper"])
            margin = 0.05 * (upper - lower)
            q.append(rng.uniform(lower + margin, upper - margin))
        limit_validation = _validate_q_vector_limits(
            chain, q, max_joints
        )
        result = _apply_exact_pose(
            session,
            model,
            segments,
            visuals,
            chain,
            q,
            max_joints,
            f"RANDOM_LEGAL_{sample_index + 1:02d}",
        )
        result["sample_index"] = sample_index + 1
        result["sampling_seed"] = random_seed
        result["sampling_margin_fraction"] = 0.05
        result["limit_validation"] = limit_validation
        random_checks.append(result)
        _trace(
            "RANDOM_LEGAL_POSE_PASS",
            sample=sample_index + 1,
            max_abs_error=result["readback"]["max_abs_error"],
        )
    stow_v2_check: dict[str, Any] | None = None
    if max_joints == 6:
        stow_q = [float(value) for value in legacy.STOW_V2_RAD]
        stow_limit_validation = _validate_q_vector_limits(
            chain, stow_q, max_joints
        )
        stow_v2_check = _apply_exact_pose(
            session,
            model,
            segments,
            visuals,
            chain,
            stow_q,
            max_joints,
            "STOW_V2_CANDIDATE_HOLD",
        )
        stow_v2_check["limit_validation"] = stow_limit_validation
        stow_v2_check["status"] = (
            "STOW_V2_POSE_DRIVE_PASS_PACKAGING_AND_CLEARANCE_HOLD"
        )
        _trace(
            "STOW_V2_POSE_DRIVE_PASS_WITH_HOLDS",
            max_abs_error=stow_v2_check["readback"]["max_abs_error"],
        )
    reset = _apply_exact_pose(
        session,
        model,
        segments,
        visuals,
        chain,
        q0,
        max_joints,
        "FINAL_RESET_Q0",
    )
    configuration_result = _create_pose_configurations(
        session,
        model,
        segments,
        visuals,
        chain,
        max_joints,
    )
    session.set_text_properties(
        model,
        {
            "OBJECT_ID": (
                "B51_B601_ARTICULATED_ENGINEERING_ARM"
                if max_joints == 6
                else f"B51_B601_ARTICULATED_PREFIX_{max_joints}R"
            ),
            "ASSET_ROLE": (
                f"NATIVE_{max_joints}R_RIGID_SEGMENT_ENGINEERING_"
                "ARTICULATION"
            ),
            "TOPOLOGY": (
                f"{max_joints + 1}_RIGID_SEGMENT_SUBASSEMBLIES_"
                f"{max_joints}R_NESTED_DATUM_MATES"
            ),
            "KINEMATIC_AUTHORITY": (
                f"ACCEPTED_URDF_SHA256_{legacy.EXPECTED_URDF_SHA256}"
            ),
            "MASS_AUTHORITY": (
                f"ACCEPTED_URDF_{legacy.ACCEPTED_URDF_MASS_KG}_KG_"
                "CAD_AUTO_MASS_NOT_AUTHORIZED"
            ),
            "G08_2P_STATUS": (
                "B51_2P_GRIPPER_PARTITION_AND_ZERO_CALIBRATION_HOLD"
            ),
            "G05_G08_REGISTRATION": "CHAIN_DERIVED_HOLD",
            "STOW_STATUS": (
                "STOW_V2_POSE_TESTED_PACKAGING_AND_CLEARANCE_HOLD"
            ),
            "MOTION_CONTROL_METHOD": (
                "COORDINATED_SEGMENT_POSE_CONTROL_WITH_NATIVE_"
                "REVOLUTE_MATES"
            ),
            "SINGLE_COMPONENT_CASCADE_DRIVE_STATUS": (
                "HOLD_T001_STOPPED_PROPAGATING_AFTER_LINK4"
            ),
            "CLAIM_LIMIT": (
                "ENGINEERING_ARTICULATION_ONLY_NOT_FLIGHT_OR_"
                "MANUFACTURING_READY"
            ),
        },
    )
    save = session.save_as(
        model, target, require_zero_warnings=True
    )
    nested_names = {
        role: sorted(
            str(core.get_com_member(child, "Name2"))
            for child in list(component.GetChildren() or [])
        )
        for role, component in segments.items()
    }
    session.close_all_documents()
    return target, {
        "insertions": insertions,
        "nested_component_names": nested_names,
        "mates": mates,
        "mate_count": len(mates),
        "topology": topology,
        "q0_readback": q0_readback,
        "constraint_readback": constraint_readback,
        "pretest_save": pretest_save,
        "joint_direction_checks": direction_checks,
        "joint_direction_summary": direction_summary,
        "joint_sign_checks_deprecated_legal_only": [
            item
            for item in direction_checks
            if item["status"] == "LEGAL_DIRECTION_DRIVE_PASS"
        ],
        "off_axis_rejection_checks": off_axis_checks,
        "random_legal_pose_checks": random_checks,
        "random_pose_summary": {
            "seed": random_seed,
            "margin_fraction": 0.05,
            "requested": random_samples,
            "executed": len(random_checks),
            "all_limit_valid": all(
                item["limit_validation"]["all_legal"]
                for item in random_checks
            ),
        },
        "stow_v2_pose_check": stow_v2_check,
        "configurations": configuration_result,
        "final_q0_reset": reset,
        "save": save,
    }


def _map_reopened_segments(
    session: core.SolidWorksSession,
    assembly: Any,
    max_joints: int,
) -> dict[str, Any]:
    top = [
        session.cast(component, "IComponent2")
        for component in list(assembly.GetComponents(True) or [])
    ]
    if len(top) != max_joints + 1:
        raise core.Phase0Error(
            f"reopened top segment count mismatch: {len(top)}"
        )
    result: dict[str, Any] = {}
    for index in range(0, max_joints + 1):
        role = _top_role(index)
        token = (
            "SEGMENT_0_BASE_LINK"
            if index == 0
            else f"SEGMENT_{index}_LINK{index}"
        )
        matches = [
            component
            for component in top
            if token
            in str(core.get_com_member(component, "Name2")).upper()
        ]
        if len(matches) != 1:
            raise core.Phase0Error(
                f"reopened segment lookup failed {role}: "
                f"{[core.get_com_member(c, 'Name2') for c in top]}"
            )
        result[role] = matches[0]
    return result


def _reference_containment(
    session: core.SolidWorksSession,
    assembly: Any,
    run_root: Path,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for component in list(assembly.GetComponents(False) or []):
        typed = session.cast(component, "IComponent2")
        raw = str(core.get_com_member(typed, "GetPathName") or "")
        resolved = Path(raw).resolve() if raw else None
        try:
            inside = (
                resolved is not None
                and resolved.is_relative_to(run_root.resolve())
            )
        except AttributeError:
            try:
                resolved.relative_to(run_root.resolve())  # type: ignore[union-attr]
                inside = True
            except (ValueError, AttributeError):
                inside = False
        records.append(
            {
                "name": str(core.get_com_member(typed, "Name2")),
                "path": str(resolved) if resolved is not None else "",
                "path_exists": (
                    resolved.is_file() if resolved is not None else False
                ),
                "inside_run_root": inside,
            }
        )
    external = [
        item["path"]
        for item in records
        if item["path"] and not item["inside_run_root"]
    ]
    missing = [
        item["path"] or f"EMPTY:{item['name']}"
        for item in records
        if not item["path_exists"]
    ]
    result = {
        "resolved_reference_records": records,
        "external_reference_paths": external,
        "missing_reference_paths": missing,
        "reference_containment_status": (
            "PASS" if not external and not missing else "HOLD"
        ),
    }
    if result["reference_containment_status"] != "PASS":
        raise core.Phase0Error(
            f"segment-chain reference containment failed: {result}"
        )
    return result


def _reopen_verify(
    session: core.SolidWorksSession,
    assembly_path: Path,
    chain: dict[str, Any],
    max_joints: int,
) -> dict[str, Any]:
    model, open_record = session.open_document(
        assembly_path, "assembly"
    )
    if open_record["warnings"] not in (None, 0):
        raise core.Phase0Error(
            f"reopened segment chain warnings: {open_record}"
        )
    assembly = session.cast(model, "IAssemblyDoc")
    containment = _reference_containment(
        session, assembly, assembly_path.parents[1]
    )
    if not model.ForceRebuild3(True):
        raise core.Phase0Error("reopened segment chain rebuild failed")
    segments = _map_reopened_segments(
        session, assembly, max_joints
    )
    visuals, _, _ = _nested_map(
        session, segments, max_joints
    )
    q0 = [0.0] * max_joints
    q0_fk = _fk_unbounded(chain, q0, max_joints)
    configuration_persistence: dict[str, Any] | None = None
    if max_joints == 6:
        names = sorted(
            str(value)
            for value in list(model.GetConfigurationNames() or [])
        )
        expected_names = sorted(
            [
                "FREE_6R_ENGINEERING",
                "Q0_ACCEPTED",
                "STOW_V2_CANDIDATE_HOLD",
            ]
        )
        if names != expected_names:
            raise core.Phase0Error(
                f"reopened configuration mismatch: {names}"
            )
        if not model.ShowConfiguration2("Q0_ACCEPTED"):
            raise core.Phase0Error(
                "reopen cannot activate Q0_ACCEPTED"
            )
        if not model.ForceRebuild3(True):
            raise core.Phase0Error(
                "reopened Q0 configuration rebuild failed"
            )
        q0_configuration_readback = _verify_pose(
            segments, visuals, q0_fk, max_joints
        )
        if not model.ShowConfiguration2(
            "STOW_V2_CANDIDATE_HOLD"
        ):
            raise core.Phase0Error(
                "reopen cannot activate STOW_V2_CANDIDATE_HOLD"
            )
        if not model.ForceRebuild3(True):
            raise core.Phase0Error(
                "reopened STOW configuration rebuild failed"
            )
        stow_configuration_readback = _verify_pose(
            segments,
            visuals,
            _fk_unbounded(
                chain,
                [float(value) for value in legacy.STOW_V2_RAD],
                max_joints,
            ),
            max_joints,
        )
        if not model.ShowConfiguration2("Q0_ACCEPTED"):
            raise core.Phase0Error(
                "reopen cannot restore Q0_ACCEPTED"
            )
        if not model.ForceRebuild3(True):
            raise core.Phase0Error(
                "reopened Q0 restore rebuild failed"
            )
        configuration_persistence = {
            "names": names,
            "q0_readback": q0_configuration_readback,
            "stow_v2_readback": stow_configuration_readback,
            "status": "CONFIGURATION_POSE_PERSISTENCE_REOPEN_PASS",
        }
    q0_readback = _verify_pose(
        segments, visuals, q0_fk, max_joints
    )
    constraint_readback = _constraint_readback(
        segments, max_joints
    )
    mate_references = {
        role: len(list(component.GetMates() or []))
        for role, component in segments.items()
    }
    expected_mate_references = {
        _top_role(index): (
            2 if index in (0, max_joints) else 4
        )
        for index in range(0, max_joints + 1)
    }
    if mate_references != expected_mate_references:
        raise core.Phase0Error(
            "reopened mate-reference count mismatch: "
            f"{mate_references} != {expected_mate_references}"
        )
    direction_checks, direction_summary = _exercise_q0_directions(
        session,
        model,
        segments,
        visuals,
        chain,
        max_joints,
        delta_rad=REOPEN_SIGN_DELTA_RAD,
        phase="REOPEN",
    )
    reopen_off_axis: list[dict[str, Any]] = []
    for index in range(1, max_joints + 1):
        off_axis = _off_axis_drive(
            session,
            model,
            segments,
            visuals,
            chain,
            max_joints,
            index,
        )
        reopen_off_axis.append(off_axis)
        _trace(
            "REOPEN_JOINT_OFF_AXIS_REJECTION_PASS",
            joint_index=index,
            max_abs_error=off_axis[
                "readback_after_rejection"
            ]["max_abs_error"],
        )
    stow_v2_check: dict[str, Any] | None = None
    if max_joints == 6:
        stow_q = [float(value) for value in legacy.STOW_V2_RAD]
        stow_v2_check = _apply_exact_pose(
            session,
            model,
            segments,
            visuals,
            chain,
            stow_q,
            max_joints,
            "REOPEN_STOW_V2_CANDIDATE_HOLD",
        )
        stow_v2_check["limit_validation"] = _validate_q_vector_limits(
            chain, stow_q, max_joints
        )
        stow_v2_check["status"] = (
            "STOW_V2_REOPEN_DRIVE_PASS_PACKAGING_AND_CLEARANCE_HOLD"
        )
    reset = _apply_exact_pose(
        session,
        model,
        segments,
        visuals,
        chain,
        q0,
        max_joints,
        "REOPEN_FINAL_RESET_Q0",
    )
    result = {
        "open": open_record,
        "top_level_component_names": sorted(
            str(core.get_com_member(component, "Name2"))
            for component in segments.values()
        ),
        "q0_readback": q0_readback,
        "constraint_readback": constraint_readback,
        "configuration_persistence": configuration_persistence,
        "mate_references_by_segment": mate_references,
        "expected_mate_references_by_segment": expected_mate_references,
        "joint_direction_checks": direction_checks,
        "joint_direction_summary": direction_summary,
        "off_axis_rejection_checks": reopen_off_axis,
        "stow_v2_pose_check": stow_v2_check,
        **containment,
        "final_q0_reset": reset,
        "reopen_mode": "READ_ONLY_DOCUMENT_REOPEN",
        "status": (
            f"NATIVE_{max_joints}R_SEGMENT_CHAIN_REOPEN_"
            "REPRODUCIBILITY_PASS"
        ),
    }
    session.close_all_documents()
    return result


def _cold_process_reopen_with_retry(
    run_root: Path,
    assembly_path: Path,
    chain: dict[str, Any],
    max_joints: int,
) -> dict[str, Any]:
    errors: list[str] = []
    for attempt in range(1, 4):
        try:
            with core.SolidWorksSession(
                run_root, visible=False
            ) as cold_session:
                session_start = cold_session.info()
                verification = _reopen_verify(
                    cold_session,
                    assembly_path,
                    chain,
                    max_joints,
                )
            return {
                "attempt": attempt,
                "session_start": session_start,
                "session_end": cold_session.info(),
                "cold_process_reopen": True,
                "verification": verification,
            }
        except Exception as exc:
            transient = (
                "-2146959355" in repr(exc)
                or "服务器运行失败" in str(exc)
            )
            errors.append(f"{type(exc).__name__}: {exc}")
            if not transient or attempt == 3:
                raise
            if core.sldworks_process_ids():
                raise core.Phase0Error(
                    "transient cold-reopen launch failure left a "
                    f"SolidWorks process: {core.sldworks_process_ids()}"
                ) from exc
            time.sleep(20.0 * attempt)
    raise core.Phase0Error(
        f"cold process reopen exhausted retries: {errors}"
    )


def main() -> int:
    global TRACE_PATH
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-id",
        default=datetime.now(timezone.utc).strftime(
            "B51_SEGMENT_CHAIN_%Y%m%dT%H%M%SZ"
        ),
    )
    parser.add_argument(
        "--max-joints", type=int, choices=range(1, 7), default=6
    )
    parser.add_argument("--random-samples", type=int, default=20)
    parser.add_argument("--attach-active", action="store_true")
    args = parser.parse_args()
    if args.random_samples < 0 or args.random_samples > 20:
        raise SystemExit("--random-samples must be within 0..20")
    if args.max_joints == 6 and args.random_samples != 20:
        raise SystemExit(
            "full 6R acceptance requires --random-samples 20"
        )
    run_root = NATIVE_ROOT / args.run_id
    report_path = VERIFY_ROOT / f"{args.run_id}.json"
    report: dict[str, Any] = {
        "schema": "SER_B51_NATIVE_RIGID_SEGMENT_CHAIN_V2",
        "generated_utc": _utc_now(),
        "run_id": args.run_id,
        "status": f"B51_NATIVE_{args.max_joints}R_SEGMENT_CHAIN_HOLD",
        "scope": (
            f"SOLIDWORKS_NATIVE_{args.max_joints}R_RIGID_SEGMENT_"
            "ENGINEERING_ARTICULATION"
        ),
        "mass_authority": {
            "source": "ACCEPTED_URDF",
            "kg": legacy.ACCEPTED_URDF_MASS_KG,
            "cad_auto_mass_authorized": False,
        },
        "g08_2p_status": (
            "B51_2P_GRIPPER_PARTITION_AND_ZERO_CALIBRATION_HOLD"
        ),
        "max_joints": args.max_joints,
        "random_samples_requested": args.random_samples,
        "joint_limit_enforcement": {
            "authority": "ACCEPTED_URDF",
            "method": "PRE_SOLVER_Q_VECTOR_GATE",
            "native_limit_mates_present": False,
            "claim_limit": (
                "Illegal q0 directions are rejected at the command gate; "
                "this does not prove a native SolidWorks limit mate."
            ),
        },
        "motion_control_scope": {
            "accepted_method": (
                "COORDINATED_CHAIN_CONFIGURATION_POSE_CONTROL_WITH_"
                "NATIVE_REVOLUTE_MATES"
            ),
            "single_component_cascade_drive": (
                "HOLD_T001_PROPAGATION_STOPPED_AFTER_LINK4"
            ),
            "t001_evidence": (
                "07_VERIFICATION/articulation/"
                "B51_SEGMENT_CHAIN_6R_20260728T001.json"
            ),
            "claim_limit": (
                "A passing coordinated-pose run does not upgrade the "
                "failed single-component cascade drive."
            ),
        },
    }
    session: core.SolidWorksSession | None = None
    try:
        if run_root.exists() or report_path.exists():
            raise core.Phase0Error("immutable segment-chain run exists")
        run_root.mkdir(parents=True, exist_ok=False)
        TRACE_PATH = run_root / "evidence" / "execution_trace.jsonl"
        smoke.TRACE_PATH = TRACE_PATH
        legacy.TRACE_PATH = TRACE_PATH
        segment_smoke.TRACE_PATH = TRACE_PATH
        _trace("RUN_ROOT_CREATED", run_root=str(run_root))
        VERIFY_ROOT.mkdir(parents=True, exist_ok=True)
        chain = legacy._parse_urdf()
        report["kinematic_chain"] = legacy._json_chain(chain)
        staged = _stage_inputs(run_root, args.max_joints)
        report["staged_inputs"] = {
            role: legacy._file_record(path)
            for role, path in staged.items()
        }
        session_type = (
            smoke.AttachedSolidWorksSession
            if args.attach_active
            else core.SolidWorksSession
        )
        with session_type(run_root, visible=False) as session:
            report["session_start"] = session.info()
            _trace("SOLIDWORKS_SESSION_STARTED", session=session.info())
            female_path, female_record = smoke._create_datum_part(
                session, run_root, "female"
            )
            male_path, male_record = smoke._create_datum_part(
                session, run_root, "male"
            )
            report["datum_parts"] = {
                "female": {
                    "path": str(female_path),
                    "create": female_record,
                },
                "male": {
                    "path": str(male_path),
                    "create": male_record,
                },
            }
            segment_paths, report["segments"] = _build_segment_files(
                session,
                run_root,
                chain,
                staged,
                female_path,
                male_path,
                args.max_joints,
            )
            assembly_path, report["build"] = _build_top_level(
                session,
                run_root,
                chain,
                segment_paths,
                args.max_joints,
                args.random_samples,
            )
            report["same_process_document_reopen"] = _reopen_verify(
                session,
                assembly_path,
                chain,
                args.max_joints,
            )
            report["same_process_document_reopen"][
                "cold_process_reopen"
            ] = False
        report["session_end"] = session.info()
        if args.attach_active:
            report["cold_process_reopen_verification"] = {
                "status": "HOLD_ATTACH_MODE_CANNOT_PROVE_COLD_PROCESS_REOPEN",
                "cold_process_reopen": False,
            }
        else:
            time.sleep(15.0)
            report["cold_process_reopen_verification"] = (
                _cold_process_reopen_with_retry(
                    run_root,
                    assembly_path,
                    chain,
                    args.max_joints,
                )
            )
        report["artifacts"] = {
            "assembly": core.artifact_record(
                assembly_path, run_root
            ),
            "segments": {
                role: core.artifact_record(path, run_root)
                for role, path in segment_paths.items()
            },
            "trace": core.artifact_record(TRACE_PATH, run_root),
        }
        cold_pass = bool(
            report["cold_process_reopen_verification"].get(
                "cold_process_reopen"
            )
        )
        report["status"] = (
            (
                f"B51_NATIVE_{args.max_joints}R_SEGMENT_CHAIN_PASS_"
                "WITH_G08_2P_AND_SYSTEM_CLEARANCE_HOLDS"
            )
            if cold_pass
            else (
                f"B51_NATIVE_{args.max_joints}R_SEGMENT_CHAIN_HOLD_"
                "COLD_PROCESS_REOPEN_NOT_PROVEN"
            )
        )
    except Exception as exc:
        report["exception"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        if session is not None:
            report["session_end"] = session.info()
    report["completed_utc"] = _utc_now()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return (
        0
        if report["status"].startswith(
            f"B51_NATIVE_{args.max_joints}R_SEGMENT_CHAIN_PASS"
        )
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
