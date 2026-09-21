"""Build and verify an isolated native SolidWorks B601 6R engineering assembly.

This script preserves the accepted URDF as kinematic and mass authority.  The
native CAD is an engineering geometry and articulation representation only.
The composite G08 gripper detail remains fixed to link6; its two prismatic
finger joints are explicitly held because no credible native partition exists.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import shutil
import sys
import traceback
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

sys.dont_write_bytecode = True

CANDIDATE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import b51_sw_rev_smoke as smoke  # noqa: E402

core = smoke.core
NATIVE_ROOT = CANDIDATE_ROOT / "03_CAD" / "native_articulated"
VERIFY_ROOT = CANDIDATE_ROOT / "07_VERIFICATION" / "articulation"
URDF_PATH = (
    CANDIDATE_ROOT.parent
    / "spacecraft_layout"
    / "arm_b601_v1"
    / "arm_b601_v1.urdf"
)
INPUT_ROOT = CANDIDATE_ROOT / "03_CAD" / "native_inputs"
LINK_PART_ROOT = INPUT_ROOT / "10_vendor_link_parts"
EXPECTED_URDF_SHA256 = (
    "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
)
ACCEPTED_URDF_MASS_KG = "4.6955559493429862"
STOW_V2_RAD = [
    2.523254,
    -2.967060,
    -1.117011,
    -0.403923,
    -0.418083,
    -0.174533,
]
TRACE_PATH: Path | None = None

SW_MATE_LOCK = 16
SW_MATE_COINCIDENT = 0
SW_MATE_CONCENTRIC = 1
SW_MATE_ALIGN_ALIGNED = 0
SW_MATE_ALIGN_ANTI_ALIGNED = 1
SW_ADD_MATE_NO_ERROR = 1
SW_COMPONENT_HIDDEN = 0

VISUAL_PARTS = {
    "base_link": LINK_PART_ROOT / "B51_REF_base_link_LINKLOCAL.SLDPRT",
    "link1": LINK_PART_ROOT / "B51_REF_link1_LINKLOCAL.SLDPRT",
    "link2": LINK_PART_ROOT / "B51_REF_link2_LINKLOCAL.SLDPRT",
    "link3": LINK_PART_ROOT / "B51_REF_link3_LINKLOCAL.SLDPRT",
    "link4": LINK_PART_ROOT / "B51_REF_link4_LINKLOCAL.SLDPRT",
    "link5": LINK_PART_ROOT / "B51_REF_link5_LINKLOCAL.SLDPRT",
    "link6": LINK_PART_ROOT / "B51_REF_link6_LINKLOCAL.SLDPRT",
    "gripper_link": LINK_PART_ROOT
    / "B51_REF_gripper_detail_LINKLOCAL.SLDPRT",
}


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest().upper()


def _file_record(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _stage_visual_inputs(run_root: Path) -> dict[str, Path]:
    target_root = run_root / "inputs" / "vendor_link_parts"
    target_root.mkdir(parents=True, exist_ok=True)
    staged: dict[str, Path] = {}
    for name, source in VISUAL_PARTS.items():
        if not source.is_file():
            raise core.Phase0Error(f"native visual input missing {name}: {source}")
        target = target_root / source.name
        if target.exists():
            raise core.Phase0Error(f"staged input overwrite forbidden: {target}")
        shutil.copy2(source, target)
        if _sha256(target) != _sha256(source):
            raise core.Phase0Error(f"staged input hash mismatch: {name}")
        staged[name] = target
    return staged


def _vector(text: str | None, length: int) -> np.ndarray:
    values = [float(value) for value in (text or "").split()]
    if len(values) != length:
        raise core.Phase0Error(f"vector length mismatch: {text!r}")
    return np.asarray(values, dtype=float)


def _rpy_matrix(rpy: np.ndarray) -> np.ndarray:
    roll, pitch, yaw = [float(value) for value in rpy]
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = np.asarray(
        [[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]], dtype=float
    )
    ry = np.asarray(
        [[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]], dtype=float
    )
    rz = np.asarray(
        [[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]], dtype=float
    )
    return rz @ ry @ rx


def _axis_angle_matrix(axis: np.ndarray, angle: float) -> np.ndarray:
    norm = float(np.linalg.norm(axis))
    if norm <= 1.0e-15:
        return np.eye(3, dtype=float)
    x, y, z = [float(value) for value in axis / norm]
    c = math.cos(angle)
    s = math.sin(angle)
    one = 1.0 - c
    return np.asarray(
        [
            [c + x * x * one, x * y * one - z * s, x * z * one + y * s],
            [y * x * one + z * s, c + y * y * one, y * z * one - x * s],
            [z * x * one - y * s, z * y * one + x * s, c + z * z * one],
        ],
        dtype=float,
    )


def _transform(
    translation: np.ndarray | None = None,
    rotation: np.ndarray | None = None,
) -> np.ndarray:
    matrix = np.eye(4, dtype=float)
    if rotation is not None:
        matrix[:3, :3] = rotation
    if translation is not None:
        matrix[:3, 3] = translation
    return matrix


def _parse_urdf() -> dict[str, Any]:
    if not URDF_PATH.is_file():
        raise core.Phase0Error(f"accepted URDF missing: {URDF_PATH}")
    digest = _sha256(URDF_PATH)
    if digest != EXPECTED_URDF_SHA256:
        raise core.Phase0Error(
            f"accepted URDF hash drift: {digest} != {EXPECTED_URDF_SHA256}"
        )
    root = ET.parse(URDF_PATH).getroot()
    joints: list[dict[str, Any]] = []
    fixed_gripper: dict[str, Any] | None = None
    for node in root.findall("joint"):
        name = str(node.attrib["name"])
        joint_type = str(node.attrib["type"])
        origin = node.find("origin")
        parent = node.find("parent")
        child = node.find("child")
        axis = node.find("axis")
        if origin is None or parent is None or child is None:
            raise core.Phase0Error(f"incomplete URDF joint: {name}")
        item = {
            "name": name,
            "type": joint_type,
            "parent": str(parent.attrib["link"]),
            "child": str(child.attrib["link"]),
            "xyz": _vector(origin.attrib.get("xyz"), 3),
            "rpy": _vector(origin.attrib.get("rpy"), 3),
            "axis": (
                np.zeros(3, dtype=float)
                if axis is None
                else _vector(axis.attrib.get("xyz"), 3)
            ),
        }
        limit = node.find("limit")
        if limit is not None:
            item["lower"] = float(limit.attrib["lower"])
            item["upper"] = float(limit.attrib["upper"])
        if name.startswith("joint") and name[5:].isdigit() and joint_type == "revolute":
            joints.append(item)
        elif name == "gripper_joint" and joint_type == "fixed":
            fixed_gripper = item
    joints.sort(key=lambda item: int(item["name"][5:]))
    if [item["name"] for item in joints] != [
        f"joint{index}" for index in range(1, 7)
    ]:
        raise core.Phase0Error("accepted 6R joint sequence is incomplete")
    if fixed_gripper is None:
        raise core.Phase0Error("accepted fixed gripper_joint is missing")
    return {
        "urdf": _file_record(URDF_PATH),
        "joints": joints,
        "fixed_gripper": fixed_gripper,
    }


def _origin_transform(joint: dict[str, Any]) -> np.ndarray:
    return _transform(joint["xyz"], _rpy_matrix(joint["rpy"]))


def _fk(chain: dict[str, Any], q: list[float]) -> dict[str, np.ndarray]:
    if len(q) != 6:
        raise core.Phase0Error(f"expected 6 joint values, got {len(q)}")
    result = {"base_link": np.eye(4, dtype=float)}
    for item, angle in zip(chain["joints"], q):
        if angle < item["lower"] - 1.0e-12 or angle > item["upper"] + 1.0e-12:
            raise core.Phase0Error(
                f"{item['name']} angle outside accepted limit: {angle}"
            )
        parent = result[item["parent"]]
        rotation = _transform(
            rotation=_axis_angle_matrix(item["axis"], float(angle))
        )
        result[item["child"]] = parent @ _origin_transform(item) @ rotation
    fixed = chain["fixed_gripper"]
    result["gripper_link"] = result[fixed["parent"]] @ _origin_transform(fixed)
    return result


def _matrix_array(matrix: np.ndarray) -> list[float]:
    return [
        float(matrix[0, 0]),
        float(matrix[1, 0]),
        float(matrix[2, 0]),
        float(matrix[0, 1]),
        float(matrix[1, 1]),
        float(matrix[2, 1]),
        float(matrix[0, 2]),
        float(matrix[1, 2]),
        float(matrix[2, 2]),
        float(matrix[0, 3]),
        float(matrix[1, 3]),
        float(matrix[2, 3]),
        1.0,
        0.0,
        0.0,
        0.0,
    ]


def _component_array(component: Any) -> list[float]:
    transform = core.get_com_member(component, "Transform2")
    return [
        float(value)
        for value in core.get_com_member(transform, "ArrayData")
    ]


def _max_error(actual: list[float], expected: list[float]) -> float:
    return max(abs(a - b) for a, b in zip(actual, expected))


def _math_transform(
    session: core.SolidWorksSession, matrix: np.ndarray
) -> Any:
    from win32com.client import VARIANT

    data = _matrix_array(matrix)
    typed = VARIANT(
        session.pythoncom.VT_ARRAY | session.pythoncom.VT_R8, data
    )
    utility = session.cast(
        core.get_com_member(session.sw, "GetMathUtility"), "IMathUtility"
    )
    transform = utility.CreateTransform(typed)
    if transform is None:
        raise core.Phase0Error("IMathUtility.CreateTransform failed")
    readback = [
        float(value)
        for value in core.get_com_member(transform, "ArrayData")
    ]
    if _max_error(readback, data) > 1.0e-12:
        raise core.Phase0Error(
            f"CreateTransform SAFEARRAY readback mismatch: {readback}"
        )
    return transform


def _set_component_transform(
    session: core.SolidWorksSession,
    model: Any,
    component: Any,
    matrix: np.ndarray,
    *,
    tolerance: float = 2.0e-7,
) -> dict[str, Any]:
    expected = _matrix_array(matrix)
    transform = _math_transform(session, matrix)
    api_ok = bool(component.SetTransformAndSolve3(transform, True))
    rebuild_ok = bool(model.EditRebuild3())
    actual = _component_array(component)
    error = _max_error(actual, expected)
    if error > tolerance:
        raise core.Phase0Error(
            f"component transform solve mismatch: error={error}, "
            f"component={core.get_com_member(component, 'Name2')}, "
            f"api_ok={api_ok}, expected={expected}, actual={actual}"
        )
    return {
        "api": "SetTransformAndSolve3",
        "api_ok": api_ok,
        "rebuild_ok": rebuild_ok,
        "max_abs_error": error,
    }


def _insert_component(
    session: core.SolidWorksSession,
    model: Any,
    part_path: Path,
    matrix: np.ndarray,
    *,
    fixed: bool,
    role: str,
) -> tuple[Any, dict[str, Any]]:
    part_model, open_record = session.open_document(part_path, "part")
    part_title = str(core.get_com_member(part_model, "GetTitle"))
    assembly_title = str(core.get_com_member(model, "GetTitle"))
    session.activate_document(assembly_title)
    assembly = session.cast(model, "IAssemblyDoc")
    component = assembly.AddComponent5(
        str(part_path), 0, "", False, "", 0.0, 0.0, 0.0
    )
    if component is None:
        raise core.Phase0Error(f"AddComponent5 failed: {part_path}")
    component = session.cast(component, "IComponent2")
    model.ClearSelection2(True)
    if not component.Select4(False, None, False):
        raise core.Phase0Error(f"component selection failed: {role}")
    if bool(core.get_com_member(component, "IsFixed")):
        assembly.UnfixComponent()
    model.ClearSelection2(True)
    transform_result = _set_component_transform(
        session, model, component, matrix, tolerance=1.0e-9
    )
    model.ClearSelection2(True)
    if not component.Select4(False, None, False):
        raise core.Phase0Error(f"component final selection failed: {role}")
    if fixed:
        assembly.FixComponent()
    else:
        assembly.UnfixComponent()
    model.ClearSelection2(True)
    fixed_readback = bool(core.get_com_member(component, "IsFixed"))
    if fixed_readback != fixed:
        raise core.Phase0Error(
            f"component fixed-state mismatch for {role}: {fixed_readback}"
        )
    resolved_path = Path(
        str(core.get_com_member(component, "GetPathName"))
    ).resolve()
    if resolved_path != part_path.resolve():
        raise core.Phase0Error(
            f"component reference mismatch: {resolved_path} != {part_path}"
        )
    name = str(core.get_com_member(component, "Name2"))
    session.sw.CloseDoc(part_title)
    return component, {
        "role": role,
        "component_name": name,
        "part": _file_record(part_path),
        "source_open": open_record,
        "fixed": fixed_readback,
        "transform": _component_array(component),
        "transform_set": transform_result,
    }


def _selection_manager(session: core.SolidWorksSession, model: Any) -> Any:
    import win32com.client

    raw = model._oleobj_.InvokeTypes(65537, 0, 2, (9, 0), ())
    return session.cast(win32com.client.Dispatch(raw), "ISelectionMgr")


def _mate_return(returned: Any) -> tuple[Any, int]:
    mate, outs = core._unpack_return(returned)
    error = int(outs[0]) if outs else -1
    return mate, error


def _add_lock_mate(
    session: core.SolidWorksSession,
    model: Any,
    assembly: Any,
    component_a: Any,
    component_b: Any,
    label: str,
) -> dict[str, Any]:
    model.ClearSelection2(True)
    manager = _selection_manager(session, model)
    data = session.cast(manager.CreateSelectData(), "ISelectData")
    data.Mark = 1
    selected_a = bool(component_a.Select4(False, data, False))
    selected_b = bool(component_b.Select4(True, data, False))
    mark_count = int(manager.GetSelectedObjectCount2(1))
    if not selected_a or not selected_b or mark_count != 2:
        raise core.Phase0Error(
            f"lock mate selection failed for {label}: "
            f"{selected_a},{selected_b},mark={mark_count}"
        )
    returned = assembly.AddMate3(
        SW_MATE_LOCK,
        SW_MATE_ALIGN_ALIGNED,
        False,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        False,
        0,
    )
    mate, error = _mate_return(returned)
    model.ClearSelection2(True)
    if mate is None or error != SW_ADD_MATE_NO_ERROR:
        raise core.Phase0Error(
            f"lock mate failed for {label}: {returned!r}"
        )
    return {
        "label": label,
        "type": "LOCK",
        "error_status": error,
        "mate_object_returned": True,
        "components": [
            str(core.get_com_member(component_a, "Name2")),
            str(core.get_com_member(component_b, "Name2")),
        ],
    }


def _add_entity_mate(
    session: core.SolidWorksSession,
    model: Any,
    assembly: Any,
    entity_a: Any,
    entity_b: Any,
    mate_type: int,
    alignment: int,
    label: str,
) -> dict[str, Any]:
    model.ClearSelection2(True)
    manager = _selection_manager(session, model)
    data = session.cast(manager.CreateSelectData(), "ISelectData")
    data.Mark = 1
    selected_a = bool(entity_a.Select4(False, data))
    selected_b = bool(entity_b.Select4(True, data))
    mark_count = int(manager.GetSelectedObjectCount2(1))
    selected: list[dict[str, Any]] = []
    for index in range(1, int(manager.GetSelectedObjectCount2(-1)) + 1):
        component = manager.GetSelectedObjectsComponent4(index, -1)
        selected.append(
            {
                "type": int(manager.GetSelectedObjectType3(index, -1)),
                "component": (
                    None
                    if component is None
                    else str(core.get_com_member(component, "Name2"))
                ),
            }
        )
    if not selected_a or not selected_b or mark_count != 2:
        raise core.Phase0Error(
            f"entity mate selection failed for {label}: "
            f"{selected_a},{selected_b},mark={mark_count}"
        )
    returned = assembly.AddMate3(
        mate_type,
        alignment,
        False,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        False,
        0,
    )
    mate, error = _mate_return(returned)
    model.ClearSelection2(True)
    if mate is None or error != SW_ADD_MATE_NO_ERROR:
        raise core.Phase0Error(
            f"entity mate failed for {label}: {returned!r}"
        )
    return {
        "label": label,
        "type": (
            "CONCENTRIC"
            if mate_type == SW_MATE_CONCENTRIC
            else "COINCIDENT"
        ),
        "alignment": alignment,
        "error_status": error,
        "mate_object_returned": True,
        "selected": selected,
        "selected_count_mark1": mark_count,
    }


def _visual_transform_readback(
    visuals: dict[str, Any], expected: dict[str, np.ndarray]
) -> dict[str, Any]:
    items: dict[str, Any] = {}
    maximum = 0.0
    for name, component in visuals.items():
        actual = _component_array(component)
        target = _matrix_array(expected[name])
        error = _max_error(actual, target)
        maximum = max(maximum, error)
        items[name] = {
            "max_abs_error": error,
            "translation_m": actual[9:12],
        }
    return {"max_abs_error": maximum, "links": items}


def _set_fixed_state(
    session: core.SolidWorksSession,
    model: Any,
    component: Any,
    fixed: bool,
) -> None:
    assembly = session.cast(model, "IAssemblyDoc")
    model.ClearSelection2(True)
    if not component.Select4(False, None, False):
        raise core.Phase0Error(
            "cannot select component for temporary fixed-state control"
        )
    if fixed:
        assembly.FixComponent()
    else:
        assembly.UnfixComponent()
    model.ClearSelection2(True)
    readback = bool(core.get_com_member(component, "IsFixed"))
    if readback != fixed:
        raise core.Phase0Error(
            f"temporary fixed-state mismatch: {readback} != {fixed}"
        )


def _apply_pose(
    session: core.SolidWorksSession,
    model: Any,
    visuals: dict[str, Any],
    chain: dict[str, Any],
    q: list[float],
    label: str,
    datums: dict[str, dict[int, Any]] | None = None,
) -> dict[str, Any]:
    if datums is None:
        raise core.Phase0Error("simultaneous pose application requires datums")
    expected = _fk(chain, q)
    z_back = _transform(np.asarray([0.0, 0.0, -0.002], dtype=float))
    targets: list[tuple[str, Any, np.ndarray]] = []
    for name in [f"link{index}" for index in range(1, 7)] + [
        "gripper_link"
    ]:
        targets.append((f"VISUAL_{name}", visuals[name], expected[name]))
    datum_expected: dict[str, np.ndarray] = {}
    for index, joint in enumerate(chain["joints"], start=1):
        female_target = (
            expected[joint["parent"]] @ _origin_transform(joint) @ z_back
        )
        male_target = expected[joint["child"]]
        datum_expected[f"FEMALE_{index}"] = female_target
        datum_expected[f"MALE_{index}"] = male_target
        targets.append(
            (
                f"J{index}_FEMALE",
                datums["female"][index],
                female_target,
            )
        )
        targets.append(
            (f"J{index}_MALE", datums["male"][index], male_target)
        )
    assembly = session.cast(model, "IAssemblyDoc")
    initial_rebuild_state = bool(assembly.EnableAssemblyRebuild)
    writes: list[dict[str, Any]] = []
    try:
        assembly.EnableAssemblyRebuild = False
        for role, component, matrix in targets:
            transform = _math_transform(session, matrix)
            component.Transform2 = transform
            immediate = _component_array(component)
            target_array = _matrix_array(matrix)
            writes.append(
                {
                    "role": role,
                    "api": "Transform2_PROPERTY_REBUILD_SUSPENDED",
                    "immediate_max_abs_error": _max_error(
                        immediate, target_array
                    ),
                }
            )
    finally:
        assembly.EnableAssemblyRebuild = initial_rebuild_state
    if not model.ForceRebuild3(True):
        raise core.Phase0Error(f"pose rebuild failed: {label}")
    _trace(
        "POSE_SIMULTANEOUS_WRITES_COMPLETE",
        label=label,
        initial_rebuild_state=initial_rebuild_state,
        writes=writes,
    )
    readback = _visual_transform_readback(visuals, expected)
    if readback["max_abs_error"] > 2.0e-7:
        raise core.Phase0Error(
            f"CAD FK mismatch for {label}: {readback}"
        )
    datum_readback: dict[str, Any] = {}
    datum_maximum = 0.0
    for index in range(1, 7):
        for kind in ("female", "male"):
            key = f"{kind.upper()}_{index}"
            actual = _component_array(datums[kind][index])
            target = _matrix_array(datum_expected[key])
            error = _max_error(actual, target)
            datum_maximum = max(datum_maximum, error)
            datum_readback[key] = {"max_abs_error": error}
    if datum_maximum > 2.0e-7:
        raise core.Phase0Error(
            f"datum FK mismatch for {label}: {datum_maximum}"
        )
    return {
        "label": label,
        "q_rad": [float(value) for value in q],
        "writes": writes,
        "readback": readback,
        "datum_readback": {
            "max_abs_error": datum_maximum,
            "items": datum_readback,
        },
    }


def _configuration_names(model: Any) -> list[str]:
    return sorted(
        str(value) for value in list(model.GetConfigurationNames() or [])
    )


def _create_pose_configurations(
    session: core.SolidWorksSession,
    model: Any,
    visuals: dict[str, Any],
    chain: dict[str, Any],
    datums: dict[str, dict[int, Any]],
) -> dict[str, Any]:
    q0 = [0.0] * 6
    _apply_pose(
        session,
        model,
        visuals,
        chain,
        q0,
        "CONFIG_Q0_PREP",
        datums,
    )
    manager = core.get_com_member(model, "ConfigurationManager")
    active = core.get_com_member(manager, "ActiveConfiguration")
    active.Name = "Q0_ACCEPTED"
    for name, comment in (
        (
            "FREE_6R_ENGINEERING",
            "Six native revolute DOFs; accepted URDF is kinematic authority.",
        ),
        (
            "STOW_V2_CANDIDATE_HOLD",
            "Vendor-derived stow candidate; packaging and continuous clearance HOLD.",
        ),
    ):
        if manager.AddConfiguration2(
            name, comment, "", 0, "", False, False
        ) is None:
            raise core.Phase0Error(f"AddConfiguration2 failed: {name}")
    if not model.ShowConfiguration2("STOW_V2_CANDIDATE_HOLD"):
        raise core.Phase0Error("cannot activate STOW_V2_CANDIDATE_HOLD")
    stow_set = _apply_pose(
        session,
        model,
        visuals,
        chain,
        STOW_V2_RAD,
        "CONFIG_STOW_V2",
        datums,
    )
    if not model.ShowConfiguration2("Q0_ACCEPTED"):
        raise core.Phase0Error("cannot reactivate Q0_ACCEPTED")
    if not model.ForceRebuild3(True):
        raise core.Phase0Error("Q0 configuration rebuild failed")
    q0_readback = _visual_transform_readback(visuals, _fk(chain, q0))
    if q0_readback["max_abs_error"] > 2.0e-7:
        raise core.Phase0Error(
            "Q0 configuration did not retain its component positions: "
            f"{q0_readback['max_abs_error']}"
        )
    if not model.ShowConfiguration2("STOW_V2_CANDIDATE_HOLD"):
        raise core.Phase0Error("cannot reactivate STOW_V2_CANDIDATE_HOLD")
    if not model.ForceRebuild3(True):
        raise core.Phase0Error("STOW configuration rebuild failed")
    stow_readback = _visual_transform_readback(
        visuals, _fk(chain, STOW_V2_RAD)
    )
    if stow_readback["max_abs_error"] > 2.0e-7:
        raise core.Phase0Error(
            "STOW configuration did not retain its component positions: "
            f"{stow_readback['max_abs_error']}"
        )
    return {
        "names": _configuration_names(model),
        "active": str(
            core.get_com_member(
                core.get_com_member(model, "ConfigurationManager"),
                "ActiveConfiguration",
            ).Name
        ),
        "control_method": (
            "ASSEMBLY_CONFIGURATION_SPECIFIC_COMPONENT_POSITIONS_WITH_NATIVE_MATES"
        ),
        "q0_readback": q0_readback,
        "stow_set": stow_set,
        "stow_readback": stow_readback,
        "status": "CONFIGURATION_POSE_PERSISTENCE_PASS_PRE_SAVE",
    }


def _map_reopened_visuals(
    session: core.SolidWorksSession, assembly: Any
) -> tuple[dict[str, Any], list[Any]]:
    components = [
        session.cast(item, "IComponent2")
        for item in list(assembly.GetComponents(False) or [])
    ]
    visuals: dict[str, Any] = {}
    expected_by_stem = {
        path.stem.upper(): name for name, path in VISUAL_PARTS.items()
    }
    for component in components:
        path = Path(str(core.get_com_member(component, "GetPathName")))
        name = expected_by_stem.get(path.stem.upper())
        if name is not None:
            visuals[name] = component
    if set(visuals) != set(VISUAL_PARTS):
        raise core.Phase0Error(
            f"reopened visual map mismatch: {sorted(visuals)}"
        )
    return visuals, components


def _map_reopened_datums(
    components: list[Any],
) -> dict[str, dict[int, Any]]:
    datums: dict[str, dict[int, Any]] = {"female": {}, "male": {}}
    for component in components:
        path = Path(str(core.get_com_member(component, "GetPathName")))
        stem = path.stem.upper()
        if stem not in {
            "B51_REV_DATUM_FEMALE",
            "B51_REV_DATUM_MALE",
        }:
            continue
        name = str(core.get_com_member(component, "Name2"))
        suffix = name.rsplit("-", 1)[-1]
        if suffix.isdigit() and 1 <= int(suffix) <= 6:
            kind = "female" if stem.endswith("FEMALE") else "male"
            datums[kind][int(suffix)] = component
    expected = set(range(1, 7))
    if set(datums["female"]) != expected or set(datums["male"]) != expected:
        raise core.Phase0Error(
            "reopened articulation datum map mismatch: "
            f"female={sorted(datums['female'])}, "
            f"male={sorted(datums['male'])}"
        )
    return datums


def _reopen_verify(
    session: core.SolidWorksSession,
    assembly_path: Path,
    chain: dict[str, Any],
) -> dict[str, Any]:
    _trace("REOPEN_BEGIN", path=str(assembly_path))
    model, open_record = session.open_document(assembly_path, "assembly")
    assembly = session.cast(model, "IAssemblyDoc")
    visuals, components = _map_reopened_visuals(session, assembly)
    datums = _map_reopened_datums(components)
    configurations = _configuration_names(model)
    expected_configs = {
        "Q0_ACCEPTED",
        "FREE_6R_ENGINEERING",
        "STOW_V2_CANDIDATE_HOLD",
    }
    if not expected_configs.issubset(set(configurations)):
        raise core.Phase0Error(
            f"reopened configuration set mismatch: {configurations}"
        )
    config_checks: dict[str, Any] = {}
    for name, q in (
        ("Q0_ACCEPTED", [0.0] * 6),
        ("STOW_V2_CANDIDATE_HOLD", STOW_V2_RAD),
    ):
        if not model.ShowConfiguration2(name):
            raise core.Phase0Error(f"reopen cannot activate config: {name}")
        if not model.ForceRebuild3(True):
            raise core.Phase0Error(f"reopened config rebuild failed: {name}")
        check = _visual_transform_readback(visuals, _fk(chain, q))
        if check["max_abs_error"] > 2.0e-7:
            raise core.Phase0Error(
                f"reopened configuration FK mismatch {name}: "
                f"{check['max_abs_error']}"
            )
        config_checks[name] = check
    model.ShowConfiguration2("Q0_ACCEPTED")
    reopen_drives = [
        _apply_pose(
            session,
            model,
            visuals,
            chain,
            [math.radians(0.5), 0.0, 0.0, 0.0, 0.0, 0.0],
            "REOPEN_J1_PLUS_0P5_DEG",
            datums,
        ),
        _apply_pose(
            session,
            model,
            visuals,
            chain,
            [0.0, math.radians(-0.5), 0.0, 0.0, 0.0, 0.0],
            "REOPEN_J2_MINUS_0P5_DEG_AXIS_SIGN",
            datums,
        ),
    ]
    datum_components = [
        component
        for component in components
        if "B51_REV_DATUM_" in Path(
            str(core.get_com_member(component, "GetPathName"))
        ).stem.upper()
    ]
    datum_mate_counts = [
        len(list(component.GetMates() or [])) for component in datum_components
    ]
    if len(components) != 20 or len(datum_components) != 12:
        raise core.Phase0Error(
            f"reopened component topology mismatch: "
            f"all={len(components)}, datums={len(datum_components)}"
        )
    if any(count != 3 for count in datum_mate_counts):
        raise core.Phase0Error(
            f"reopened datum mate endpoint counts mismatch: {datum_mate_counts}"
        )
    result = {
        "open": open_record,
        "configuration_names": configurations,
        "configuration_checks": config_checks,
        "component_count": len(components),
        "visual_component_count": len(visuals),
        "datum_component_count": len(datum_components),
        "datum_mate_counts": datum_mate_counts,
        "reopen_drives": reopen_drives,
        "status": "NATIVE_6R_REOPEN_REPRODUCIBILITY_PASS",
    }
    _trace("REOPEN_END", result=result)
    session.close_all_documents()
    return result


def _build(
    session: core.SolidWorksSession,
    run_root: Path,
    chain: dict[str, Any],
    visual_parts: dict[str, Path],
) -> tuple[Path, dict[str, Any]]:
    for name, path in visual_parts.items():
        if not path.is_file():
            raise core.Phase0Error(f"native visual input missing {name}: {path}")
    female_path, female_create = smoke._create_datum_part(
        session, run_root, "female"
    )
    male_path, male_create = smoke._create_datum_part(
        session, run_root, "male"
    )
    _trace(
        "DATUM_PARTS_CREATED",
        female=str(female_path),
        male=str(male_path),
    )
    assembly_path = (
        run_root
        / "assembly"
        / "B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM"
    )
    model = session.new_document("assembly")
    assembly = session.cast(model, "IAssemblyDoc")
    q0_fk = _fk(chain, [0.0] * 6)
    visuals: dict[str, Any] = {}
    insert_records: list[dict[str, Any]] = []
    for name in [
        "base_link",
        "link1",
        "link2",
        "link3",
        "link4",
        "link5",
        "link6",
        "gripper_link",
    ]:
        component, record = _insert_component(
            session,
            model,
            visual_parts[name],
            q0_fk[name],
            fixed=(name == "base_link"),
            role=f"VENDOR_VISUAL_{name}",
        )
        visuals[name] = component
        insert_records.append(record)
        _trace("VISUAL_INSERTED", role=name, component=record["component_name"])
    female_components: dict[int, Any] = {}
    male_components: dict[int, Any] = {}
    datum_records: list[dict[str, Any]] = []
    z_back = _transform(np.asarray([0.0, 0.0, -0.002], dtype=float))
    for index, joint in enumerate(chain["joints"], start=1):
        parent_fk = q0_fk[joint["parent"]]
        joint_fk = parent_fk @ _origin_transform(joint)
        female_component, female_record = _insert_component(
            session,
            model,
            female_path,
            joint_fk @ z_back,
            fixed=False,
            role=f"J{index}_FEMALE_PARENT_DATUM",
        )
        male_component, male_record = _insert_component(
            session,
            model,
            male_path,
            joint_fk,
            fixed=False,
            role=f"J{index}_MALE_CHILD_DATUM",
        )
        female_components[index] = female_component
        male_components[index] = male_component
        datum_records.extend([female_record, male_record])
    datums = {
        "female": female_components,
        "male": male_components,
    }
    lock_mates: list[dict[str, Any]] = []
    lock_mates.append(
        _add_lock_mate(
            session,
            model,
            assembly,
            visuals["base_link"],
            female_components[1],
            "BASE_TO_J1_FEMALE",
        )
    )
    for index in range(1, 7):
        link = visuals[f"link{index}"]
        lock_mates.append(
            _add_lock_mate(
                session,
                model,
                assembly,
                link,
                male_components[index],
                f"LINK{index}_TO_J{index}_MALE",
            )
        )
        if index < 6:
            lock_mates.append(
                _add_lock_mate(
                    session,
                    model,
                    assembly,
                    link,
                    female_components[index + 1],
                    f"LINK{index}_TO_J{index + 1}_FEMALE",
                )
            )
    lock_mates.append(
        _add_lock_mate(
            session,
            model,
            assembly,
            visuals["link6"],
            visuals["gripper_link"],
            "LINK6_TO_FIXED_COMPOSITE_GRIPPER_G08",
        )
    )
    _trace("LOCK_MATES_CREATED", count=len(lock_mates))
    hinge_mates: list[dict[str, Any]] = []
    hinge_topology: dict[str, Any] = {}
    for index in range(1, 7):
        female_cylinder, female_plane, female_topology = (
            smoke._datum_entities(session, female_components[index])
        )
        male_cylinder, male_plane, male_topology = smoke._datum_entities(
            session, male_components[index]
        )
        hinge_topology[f"joint{index}"] = {
            "female": female_topology,
            "male": male_topology,
        }
        hinge_mates.append(
            _add_entity_mate(
                session,
                model,
                assembly,
                female_cylinder,
                male_cylinder,
                SW_MATE_CONCENTRIC,
                SW_MATE_ALIGN_ALIGNED,
                f"J{index}_CONCENTRIC",
            )
        )
        hinge_mates.append(
            _add_entity_mate(
                session,
                model,
                assembly,
                female_plane,
                male_plane,
                SW_MATE_COINCIDENT,
                SW_MATE_ALIGN_ANTI_ALIGNED,
                f"J{index}_COINCIDENT",
            )
        )
        if not model.EditRebuild3():
            raise core.Phase0Error(f"joint{index} mate rebuild failed")
        _trace("HINGE_CREATED", joint=index, mates=hinge_mates[-2:])
    if not model.ForceRebuild3(True):
        raise core.Phase0Error("native 6R assembly rebuild failed")
    q0_readback = _visual_transform_readback(visuals, q0_fk)
    if q0_readback["max_abs_error"] > 2.0e-7:
        raise core.Phase0Error(
            f"initial Q0 FK mismatch: {q0_readback['max_abs_error']}"
        )
    for component in [
        *female_components.values(),
        *male_components.values(),
    ]:
        component.Visible = SW_COMPONENT_HIDDEN
    pretest_save = session.save_as(
        model, assembly_path, require_zero_warnings=False
    )
    _trace(
        "CORE_Q0_ASSEMBLY_PRETEST_SAVED",
        path=str(assembly_path),
        save=pretest_save,
    )
    sign_checks: list[dict[str, Any]] = []
    for index in range(6):
        plus = [0.0] * 6
        minus = [0.0] * 6
        plus[index] = math.radians(1.0)
        minus[index] = math.radians(-1.0)
        joint = chain["joints"][index]
        if plus[index] <= joint["upper"] and plus[index] >= joint["lower"]:
            sign_checks.append(
                _apply_pose(
                    session,
                    model,
                    visuals,
                    chain,
                    plus,
                    f"J{index + 1}_PLUS_1_DEG",
                    datums,
                )
            )
        if minus[index] <= joint["upper"] and minus[index] >= joint["lower"]:
            sign_checks.append(
                _apply_pose(
                    session,
                    model,
                    visuals,
                    chain,
                    minus,
                    f"J{index + 1}_MINUS_1_DEG",
                    datums,
                )
            )
    if len(sign_checks) != 12:
        raise core.Phase0Error(
            f"expected 12 joint sign checks, got {len(sign_checks)}"
        )
    rng = random.Random(60151)
    random_checks: list[dict[str, Any]] = []
    for sample_index in range(20):
        q = []
        for joint in chain["joints"]:
            lower = float(joint["lower"])
            upper = float(joint["upper"])
            margin = 0.05 * (upper - lower)
            q.append(rng.uniform(lower + margin, upper - margin))
        random_checks.append(
            _apply_pose(
                session,
                model,
                visuals,
                chain,
                q,
                f"RANDOM_LEGAL_{sample_index + 1:02d}",
                datums,
            )
        )
    _apply_pose(
        session,
        model,
        visuals,
        chain,
        [0.0] * 6,
        "RESET_Q0_AFTER_TESTS",
        datums,
    )
    configuration_result = _create_pose_configurations(
        session, model, visuals, chain, datums
    )
    session.set_text_properties(
        model,
        {
            "OBJECT_ID": "B51_B601_ARTICULATED_ENGINEERING_ARM",
            "ASSET_ROLE": "NATIVE_6R_ENGINEERING_GEOMETRY_AND_MATE_MODEL",
            "KINEMATIC_AUTHORITY": (
                f"ACCEPTED_URDF_SHA256_{EXPECTED_URDF_SHA256}"
            ),
            "MASS_AUTHORITY": (
                f"ACCEPTED_URDF_{ACCEPTED_URDF_MASS_KG}_KG_"
                "CAD_AUTO_MASS_NOT_AUTHORIZED"
            ),
            "TOPOLOGY": "6R_NATIVE_MATES_PLUS_FIXED_COMPOSITE_GRIPPER",
            "G08_2P_STATUS": (
                "B51_2P_GRIPPER_PARTITION_AND_ZERO_CALIBRATION_HOLD"
            ),
            "G05_G08_REGISTRATION": "CHAIN_DERIVED_HOLD",
            "STOW_STATUS": (
                "VENDOR_STOW_V2_CANDIDATE_HOLD_PACKAGING_AND_CLEARANCE_OPEN"
            ),
            "CLAIM_LIMIT": (
                "ENGINEERING_ARTICULATION_ONLY_NOT_FLIGHT_OR_MANUFACTURING_READY"
            ),
        },
    )
    save_result = session.save_as(
        model, assembly_path, require_zero_warnings=False
    )
    _trace("ASSEMBLY_SAVED", path=str(assembly_path), save=save_result)
    session.close_all_documents()
    return assembly_path, {
        "datum_parts": {
            "female": {"path": str(female_path), "create": female_create},
            "male": {"path": str(male_path), "create": male_create},
        },
        "visual_insertions": insert_records,
        "datum_insertions": datum_records,
        "lock_mates": lock_mates,
        "hinge_mates": hinge_mates,
        "hinge_topology": hinge_topology,
        "counts": {
            "visual_components": len(visuals),
            "datum_components": 12,
            "total_components": 20,
            "lock_mates": len(lock_mates),
            "hinge_mates": len(hinge_mates),
            "total_mates": len(lock_mates) + len(hinge_mates),
        },
        "q0_readback": q0_readback,
        "core_q0_pretest_save": pretest_save,
        "joint_sign_checks": sign_checks,
        "random_legal_pose_checks": random_checks,
        "configurations": configuration_result,
        "save": save_result,
    }


def _json_chain(chain: dict[str, Any]) -> dict[str, Any]:
    def clean(item: dict[str, Any]) -> dict[str, Any]:
        return {
            key: (
                [float(value) for value in value]
                if isinstance(value, np.ndarray)
                else value
            )
            for key, value in item.items()
        }

    return {
        "urdf": chain["urdf"],
        "joints": [clean(item) for item in chain["joints"]],
        "fixed_gripper": clean(chain["fixed_gripper"]),
    }


def main() -> int:
    global TRACE_PATH
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-id",
        default=datetime.now(timezone.utc).strftime(
            "B51_ARTICULATED_%Y%m%dT%H%M%SZ"
        ),
    )
    parser.add_argument("--attach-active", action="store_true")
    args = parser.parse_args()
    run_root = NATIVE_ROOT / args.run_id
    report_path = VERIFY_ROOT / f"{args.run_id}.json"
    report: dict[str, Any] = {
        "schema": "SER_B51_NATIVE_6R_ARTICULATION_V1",
        "generated_utc": _utc_now(),
        "run_id": args.run_id,
        "status": "B51_NATIVE_6R_ARTICULATION_HOLD",
        "scope": "NATIVE_SOLIDWORKS_6R_ENGINEERING_ARTICULATION",
        "mass_authority": {
            "source": "ACCEPTED_URDF",
            "kg": ACCEPTED_URDF_MASS_KG,
            "cad_auto_mass_authorized": False,
        },
        "g08_2p_status": (
            "B51_2P_GRIPPER_PARTITION_AND_ZERO_CALIBRATION_HOLD"
        ),
    }
    session: core.SolidWorksSession | None = None
    try:
        if run_root.exists() or report_path.exists():
            raise core.Phase0Error("immutable articulated run already exists")
        run_root.mkdir(parents=True, exist_ok=False)
        TRACE_PATH = run_root / "evidence" / "execution_trace.jsonl"
        smoke.TRACE_PATH = TRACE_PATH
        _trace("RUN_ROOT_CREATED", run_root=str(run_root))
        VERIFY_ROOT.mkdir(parents=True, exist_ok=True)
        chain = _parse_urdf()
        report["kinematic_chain"] = _json_chain(chain)
        report["input_visual_parts"] = {
            name: _file_record(path) for name, path in VISUAL_PARTS.items()
        }
        staged_visual_parts = _stage_visual_inputs(run_root)
        report["staged_visual_parts"] = {
            name: _file_record(path)
            for name, path in staged_visual_parts.items()
        }
        session_type = (
            smoke.AttachedSolidWorksSession
            if args.attach_active
            else core.SolidWorksSession
        )
        with session_type(run_root, visible=False) as session:
            _trace("SOLIDWORKS_SESSION_STARTED", session=session.info())
            report["session_start"] = session.info()
            assembly_path, report["build"] = _build(
                session, run_root, chain, staged_visual_parts
            )
            report["reopen_verification"] = _reopen_verify(
                session, assembly_path, chain
            )
        report["session_end"] = session.info()
        report["artifacts"] = {
            "assembly": core.artifact_record(assembly_path, run_root),
            "trace": core.artifact_record(TRACE_PATH, run_root),
        }
        report["status"] = (
            "B51_NATIVE_6R_ARTICULATION_PASS_WITH_G08_2P_AND_"
            "SYSTEM_CLEARANCE_HOLDS"
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
    return 0 if report["status"].startswith(
        "B51_NATIVE_6R_ARTICULATION_PASS"
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
