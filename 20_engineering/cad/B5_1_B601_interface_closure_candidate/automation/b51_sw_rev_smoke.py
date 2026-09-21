"""Build and verify a two-component native SolidWorks revolute-mate smoke.

The coupon proves only the SolidWorks COM mate chain used by B5.1.  It has no
spacecraft geometry, mass, strength, manufacturing, or flight authority.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

CANDIDATE_ROOT = Path(__file__).resolve().parent.parent
B50_AUTOMATION = (
    CANDIDATE_ROOT.parent
    / "B5_0_B601_space_manipulator_candidate"
    / "automation"
)
sys.path.insert(0, str(B50_AUTOMATION))

import sw_b50_core as core  # noqa: E402

core.CANDIDATE_ROOT = CANDIDATE_ROOT
core.WRITER_MUTEX_NAME = r"Local\SER_B51_SOLIDWORKS_WRITER"

NATIVE_ROOT = CANDIDATE_ROOT / "03_CAD" / "native_articulated"
VERIFY_ROOT = CANDIDATE_ROOT / "07_VERIFICATION" / "articulation"
TRACE_PATH: Path | None = None

SW_MATE_COINCIDENT = 0
SW_MATE_CONCENTRIC = 1
SW_MATE_ALIGN_ALIGNED = 0
SW_MATE_ALIGN_ANTI_ALIGNED = 1
SW_ADD_MATE_NO_ERROR = 1
SW_UNDER_CONSTRAINED = 2
SW_REMAINING_DOFS_RESTRICTED = 0


class AttachedSolidWorksSession(core.SolidWorksSession):
    """Attach to one explicitly pre-launched, document-free SW 2024 instance."""

    def __enter__(self) -> "AttachedSolidWorksSession":
        try:
            import pythoncom
            import win32api
            import win32event
            import winerror
            import win32com.client
            from win32com.client import gencache

            self.pythoncom = pythoncom
            self.win32api = win32api
            self.win32event = win32event
            self.mutex = win32event.CreateMutex(
                None, True, core.WRITER_MUTEX_NAME
            )
            if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
                win32api.CloseHandle(self.mutex)
                self.mutex = None
                raise core.Phase0Error("another B5.1 SolidWorks writer owns the mutex")
            self.pre_process_ids = core.sldworks_process_ids()
            if len(self.pre_process_ids) != 1:
                raise core.Phase0Error(
                    "attach mode requires exactly one pre-launched SLDWORKS "
                    f"process, found {self.pre_process_ids}"
                )
            pythoncom.CoInitialize()
            self.com_initialized = True
            self.tlb_module = gencache.EnsureModule(*core.SW_TLB)
            self.raw = win32com.client.GetActiveObject(
                "SldWorks.Application"
            )
            klass = getattr(self.tlb_module, "ISldWorks")
            ole = self.raw._oleobj_.QueryInterface(
                klass.CLSID, pythoncom.IID_IDispatch
            )
            self.sw = klass(ole)
            self.revision = str(core.get_com_member(self.sw, "RevisionNumber"))
            if int(self.revision.split(".", 1)[0]) != core.EXPECTED_SW_MAJOR:
                raise core.Phase0Error(
                    f"SolidWorks revision mismatch: {self.revision}"
                )
            self.owner_pid = int(core.get_com_member(self.sw, "GetProcessID"))
            if self.owner_pid != self.pre_process_ids[0]:
                raise core.Phase0Error(
                    f"attached PID mismatch: {self.owner_pid} != "
                    f"{self.pre_process_ids[0]}"
                )
            if core.get_com_member(self.sw, "ActiveDoc") is not None:
                raise core.Phase0Error(
                    "attach mode requires a document-free SolidWorks instance"
                )
            self.sw.Visible = self.visible
            self.sw.CommandInProgress = True
            for kind, enum_value in core.TEMPLATE_PREFERENCE.items():
                template = core.PINNED_TEMPLATE_PATH[kind]
                digest = core.sha256_file(template)
                if digest != core.EXPECTED_TEMPLATE_SHA256[kind]:
                    raise core.Phase0Error(
                        f"{kind} template hash drift: {digest}"
                    )
                self.templates[kind] = {
                    "preference_enum": enum_value,
                    "user_preference_path": str(
                        core.get_com_member(
                            self.sw,
                            "GetUserPreferenceStringValue",
                            enum_value,
                        )
                        or ""
                    ),
                    "user_preference_is_file": True,
                    "user_preference_sha256": None,
                    "path": str(template.resolve()),
                    "bytes": template.stat().st_size,
                    "sha256": digest,
                    "selection_policy": (
                        "EXPLICIT_PINNED_TEMPLATE_NO_PREFERENCE_MUTATION"
                    ),
                }
            return self
        except Exception:
            self._cleanup()
            raise

    def _cleanup(self) -> None:
        """Release automation state but keep the pre-launched app alive."""
        import gc

        if self.sw is not None:
            try:
                self.sw.CloseAllDocuments(True)
            except Exception as exc:
                self.cleanup_errors.append(f"CloseAllDocuments:{exc!r}")
            try:
                self.sw.CommandInProgress = False
            except Exception as exc:
                self.cleanup_errors.append(
                    f"CommandInProgressFalse:{exc!r}"
                )
        self.sw = None
        self.raw = None
        gc.collect()
        if self.pythoncom is not None and self.com_initialized:
            try:
                self.pythoncom.CoUninitialize()
            except Exception as exc:
                self.cleanup_errors.append(f"CoUninitialize:{exc!r}")
            self.com_initialized = False
        self.pythoncom = None
        try:
            self.post_process_ids = core.sldworks_process_ids()
        except Exception as exc:
            self.cleanup_errors.append(f"post_process_check:{exc!r}")
        if self.mutex is not None and self.win32event is not None:
            try:
                self.win32event.ReleaseMutex(self.mutex)
            except Exception as exc:
                self.cleanup_errors.append(f"ReleaseMutex:{exc!r}")
            try:
                self.win32api.CloseHandle(self.mutex)
            except Exception as exc:
                self.cleanup_errors.append(f"CloseMutex:{exc!r}")
            self.mutex = None


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


def _m(mm: float) -> float:
    return float(mm) / 1000.0


def _select_front_plane(model: Any) -> str:
    model.ClearSelection2(True)
    for name in ("前视基准面", "Front Plane"):
        if model.Extension.SelectByID2(
            name, "PLANE", 0.0, 0.0, 0.0, False, 0, None, 0
        ):
            return name
    raise core.Phase0Error("cannot select Front Plane")


def _create_datum_part(
    session: core.SolidWorksSession, run_root: Path, kind: str
) -> tuple[Path, dict[str, Any]]:
    if kind not in {"female", "male"}:
        raise core.Phase0Error(f"unsupported datum kind: {kind}")
    object_id = f"B51_REV_DATUM_{kind.upper()}"
    target = run_root / "parts" / f"{object_id}.SLDPRT"
    model = session.new_document("part")
    plane = _select_front_plane(model)
    sketch = model.SketchManager
    sketch.InsertSketch(True)
    if kind == "female":
        outer = sketch.CreateCircleByRadius(0.0, 0.0, 0.0, _m(6.0))
        inner = sketch.CreateCircleByRadius(0.0, 0.0, 0.0, _m(4.1))
        if outer is None or inner is None:
            raise core.Phase0Error("female annulus sketch creation failed")
        dimensions = "OD_12_ID_8.2_DEPTH_2"
        feature_name = "REV_DATUM_FEMALE_ANNULUS"
    else:
        circle = sketch.CreateCircleByRadius(0.0, 0.0, 0.0, _m(4.0))
        if circle is None:
            raise core.Phase0Error("male cylinder sketch creation failed")
        dimensions = "DIAMETER_8_DEPTH_2"
        feature_name = "REV_DATUM_MALE_CYLINDER"
    sketch.InsertSketch(True)
    feature = model.FeatureManager.FeatureExtrusion2(
        True,
        False,
        False,
        0,
        0,
        _m(2.0),
        0.0,
        False,
        False,
        False,
        False,
        0.0,
        0.0,
        False,
        False,
        False,
        False,
        True,
        True,
        True,
        0,
        0.0,
        False,
    )
    if feature is None:
        raise core.Phase0Error("FeatureExtrusion2 failed")
    try:
        session.cast(feature, "IFeature").Name = feature_name
    except Exception:
        pass
    session.set_text_properties(
        model,
        {
            "OBJECT_ID": object_id,
            "ASSET_ROLE": "SOLIDWORKS_REVOLUTE_MATE_SMOKE_ONLY",
            "MASS_AUTHORITY": "EXCLUDED",
            "GEOMETRY_AUTHORITY": "TEST_COUPON_ONLY",
            "DATUM_KIND": kind.upper(),
            "DIMENSIONS_MM": dimensions,
        },
    )
    if not model.ForceRebuild3(True):
        raise core.Phase0Error("datum part rebuild failed")
    save = session.save_as(model, target, require_zero_warnings=False)
    part = session.cast(model, "IPartDoc")
    bodies = list(part.GetBodies2(0, False) or [])
    if len(bodies) != 1:
        raise core.Phase0Error(f"expected one datum body, got {len(bodies)}")
    session.close_all_documents()
    return target, {"selected_plane": plane, "save": save}


def _transform_data(
    angle_rad: float = 0.0,
    translation_m: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> list[float]:
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    return [
        c,
        s,
        0.0,
        -s,
        c,
        0.0,
        0.0,
        0.0,
        1.0,
        float(translation_m[0]),
        float(translation_m[1]),
        float(translation_m[2]),
        1.0,
        0.0,
        0.0,
        0.0,
    ]


def _insert_component(
    session: core.SolidWorksSession,
    assembly_model: Any,
    part_path: Path,
    *,
    fixed: bool,
    translation_m: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> Any:
    part_model, _ = session.open_document(part_path, "part")
    part_title = str(core.get_com_member(part_model, "GetTitle"))
    assembly_title = str(core.get_com_member(assembly_model, "GetTitle"))
    session.activate_document(assembly_title)
    assembly = session.cast(assembly_model, "IAssemblyDoc")
    component = assembly.AddComponent5(
        str(part_path), 0, "", False, "", 0.0, 0.0, 0.0
    )
    if component is None:
        raise core.Phase0Error("AddComponent5 failed")
    component = session.cast(component, "IComponent2")
    assembly_model.ClearSelection2(True)
    if not component.Select4(False, None, False):
        raise core.Phase0Error("component selection failed before transform")
    if bool(core.get_com_member(component, "IsFixed")):
        assembly.UnfixComponent()
    assembly_model.ClearSelection2(True)
    math_utility = session.cast(
        core.get_com_member(session.sw, "GetMathUtility"), "IMathUtility"
    )
    from win32com.client import VARIANT

    transform_input = _transform_data(translation_m=translation_m)
    typed_input = VARIANT(
        session.pythoncom.VT_ARRAY | session.pythoncom.VT_R8,
        transform_input,
    )
    transform = math_utility.CreateTransform(typed_input)
    if transform is None:
        raise core.Phase0Error("CreateTransform failed")
    transform_readback = [
        float(value)
        for value in core.get_com_member(transform, "ArrayData")
    ]
    if any(
        abs(transform_readback[index] - transform_input[index]) > 1.0e-12
        for index in range(16)
    ):
        raise core.Phase0Error(
            f"CreateTransform input readback mismatch: {transform_readback}"
        )
    expected_translation = list(translation_m)
    readback = _array_data(component)
    try:
        component.SetTransformAndSolve3(transform, True)
        assembly_model.EditRebuild3()
        readback = _array_data(component)
    except Exception:
        pass
    if any(
        abs(readback[9 + index] - expected_translation[index]) > 1.0e-10
        for index in range(3)
    ):
        try:
            component.Transform2 = transform
            assembly_model.EditRebuild3()
            readback = _array_data(component)
        except Exception:
            pass
    if any(
        abs(readback[9 + index] - expected_translation[index]) > 1.0e-10
        for index in range(3)
    ):
        component.SetTransformAndSolve2(transform)
        assembly_model.EditRebuild3()
        readback = _array_data(component)
    if any(
        abs(readback[9 + index] - expected_translation[index]) > 1.0e-10
        for index in range(3)
    ):
        raise core.Phase0Error(
            f"component translation readback mismatch: {readback[9:12]} "
            f"!= {expected_translation}"
        )
    assembly_model.ClearSelection2(True)
    if not component.Select4(False, None, False):
        raise core.Phase0Error("component selection failed")
    if fixed:
        assembly.FixComponent()
    else:
        assembly.UnfixComponent()
    assembly_model.ClearSelection2(True)
    fixed_readback = bool(core.get_com_member(component, "IsFixed"))
    if fixed_readback != fixed:
        raise core.Phase0Error(
            f"component fixed-state mismatch: {fixed_readback} != {fixed}"
        )
    session.sw.CloseDoc(part_title)
    return component


def _datum_entities(
    session: core.SolidWorksSession, component: Any
) -> tuple[Any, Any, dict[str, Any]]:
    part_model_raw = component.GetModelDoc2()
    if part_model_raw is None:
        raise core.Phase0Error("component source model is unavailable")
    part_model = session.cast(part_model_raw, "IModelDoc2")
    part_doc = session.cast(part_model, "IPartDoc")
    bodies = [
        session.cast(body, "IBody2")
        for body in list(part_doc.GetBodies2(0, False) or [])
    ]
    if len(bodies) != 1:
        raise core.Phase0Error(f"expected one component body, got {len(bodies)}")
    faces = [
        session.cast(face, "IFace2")
        for face in list(bodies[0].GetFaces() or [])
    ]
    cylinders: list[Any] = []
    planes: list[Any] = []
    for face in faces:
        surface = session.cast(face.GetSurface(), "ISurface")
        if bool(surface.IsCylinder()):
            cylinders.append(face)
        elif bool(surface.IsPlane()):
            planes.append(face)
    expected_cylinders = (
        2
        if "FEMALE" in str(core.get_com_member(component, "Name2")).upper()
        else 1
    )
    if len(cylinders) != expected_cylinders or len(planes) != 2:
        raise core.Phase0Error(
            f"unexpected datum topology: cylinders={len(cylinders)}, "
            f"planes={len(planes)}, faces={len(faces)}"
        )
    cylinder_boxes = [
        [float(value) for value in face.GetBox()] for face in cylinders
    ]
    plane_boxes = [
        [float(value) for value in face.GetBox()] for face in planes
    ]
    cylinders_with_size = sorted(
        zip(cylinders, cylinder_boxes),
        key=lambda item: max(
            abs(item[1][0]),
            abs(item[1][1]),
            abs(item[1][3]),
            abs(item[1][4]),
        ),
    )
    planes_with_height = sorted(
        zip(planes, plane_boxes),
        key=lambda item: 0.5 * (item[1][2] + item[1][5]),
    )
    cylinder_source = cylinders_with_size[0][0]
    if expected_cylinders == 2:
        plane_source = planes_with_height[-1][0]
        selected_plane_role = "FEMALE_TOP"
    else:
        plane_source = planes_with_height[0][0]
        selected_plane_role = "MALE_BOTTOM"
    cylinder_entity = component.GetCorrespondingEntity(
        session.cast(cylinder_source, "IEntity")
    )
    plane_entity = component.GetCorrespondingEntity(
        session.cast(plane_source, "IEntity")
    )
    if cylinder_entity is None or plane_entity is None:
        raise core.Phase0Error("GetCorrespondingEntity failed for datum face")
    topology = {
        "face_count": len(faces),
        "cylindrical_face_count": len(cylinders),
        "planar_face_count": len(planes),
        "cylinder_boxes_local_m": cylinder_boxes,
        "plane_boxes_local_m": plane_boxes,
        "selected_cylinder_box_local_m": cylinders_with_size[0][1],
        "selected_plane_box_local_m": (
            planes_with_height[-1][1]
            if expected_cylinders == 2
            else planes_with_height[0][1]
        ),
        "selected_plane_role": selected_plane_role,
    }
    return (
        session.cast(cylinder_entity, "IEntity"),
        session.cast(plane_entity, "IEntity"),
        topology,
    )


def _add_mate_by_points(
    session: core.SolidWorksSession,
    model: Any,
    assembly: Any,
    point_a_m: tuple[float, float, float],
    point_b_m: tuple[float, float, float],
    mate_type: int,
    mate_align: int = SW_MATE_ALIGN_ALIGNED,
) -> dict[str, Any]:
    model.ClearSelection2(True)
    selected_a = bool(
        model.Extension.SelectByID2(
            "",
            "FACE",
            *point_a_m,
            False,
            1,
            None,
            0,
        )
    )
    selected_b = bool(
        model.Extension.SelectByID2(
            "",
            "FACE",
            *point_b_m,
            True,
            1,
            None,
            0,
        )
    )
    if not selected_a or not selected_b:
        raise core.Phase0Error(
            f"coordinate face selection failed: a={selected_a}, "
            f"b={selected_b}, points={point_a_m},{point_b_m}"
        )
    selection_raw = model._oleobj_.InvokeTypes(
        65537, 0, 2, (9, 0), ()
    )
    import win32com.client

    selection_manager = win32com.client.Dispatch(selection_raw)
    selected_count = int(selection_manager.GetSelectedObjectCount2(-1))
    selected_count_mark1 = int(selection_manager.GetSelectedObjectCount2(1))
    selected: list[dict[str, Any]] = []
    for index in range(1, selected_count + 1):
        component = selection_manager.GetSelectedObjectsComponent4(index, -1)
        selected.append(
            {
                "type": int(
                    selection_manager.GetSelectedObjectType3(index, -1)
                ),
                "component": (
                    None
                    if component is None
                    else str(core.get_com_member(component, "Name2"))
                ),
            }
        )
    returned = assembly.AddMate3(
        mate_type,
        mate_align,
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
    mate, outs = core._unpack_return(returned)
    error = int(outs[0]) if outs else 0
    model.ClearSelection2(True)
    if error != SW_ADD_MATE_NO_ERROR or mate is None:
        raise core.Phase0Error(
            f"AddMate3 failed after SelectByID2: type={mate_type}, "
            f"error={error}, selected={selected}, "
            f"mark1_count={selected_count_mark1}, returned={returned!r}"
        )
    return {
        "api": "IModelDocExtension.SelectByID2+IAssemblyDoc.AddMate3",
        "mate_type": mate_type,
        "mate_align": mate_align,
        "selection_points_m": [list(point_a_m), list(point_b_m)],
        "selected": selected,
        "selected_count_mark1": selected_count_mark1,
        "error_status": error,
        "mate_object_returned": mate is not None,
    }


def _add_mate_by_entities(
    session: core.SolidWorksSession,
    model: Any,
    assembly: Any,
    entity_a: Any,
    entity_b: Any,
    mate_type: int,
    mate_align: int = SW_MATE_ALIGN_ALIGNED,
) -> dict[str, Any]:
    model.ClearSelection2(True)
    selection_raw = model._oleobj_.InvokeTypes(
        65537, 0, 2, (9, 0), ()
    )
    import win32com.client

    selection_manager = session.cast(
        win32com.client.Dispatch(selection_raw), "ISelectionMgr"
    )
    select_data = selection_manager.CreateSelectData()
    select_data = session.cast(select_data, "ISelectData")
    select_data.Mark = 1
    selected_a = bool(entity_a.Select4(False, select_data))
    selected_b = bool(entity_b.Select4(True, select_data))
    if not selected_a or not selected_b:
        raise core.Phase0Error(
            f"IEntity.Select4 failed: a={selected_a}, b={selected_b}"
        )
    selected_count = int(selection_manager.GetSelectedObjectCount2(-1))
    selected_count_mark1 = int(selection_manager.GetSelectedObjectCount2(1))
    selected: list[dict[str, Any]] = []
    for index in range(1, selected_count + 1):
        component = selection_manager.GetSelectedObjectsComponent4(index, -1)
        selected.append(
            {
                "type": int(
                    selection_manager.GetSelectedObjectType3(index, -1)
                ),
                "component": (
                    None
                    if component is None
                    else str(core.get_com_member(component, "Name2"))
                ),
            }
        )
    returned = assembly.AddMate3(
        mate_type,
        mate_align,
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
    mate, outs = core._unpack_return(returned)
    error = int(outs[0]) if outs else 0
    model.ClearSelection2(True)
    if error != SW_ADD_MATE_NO_ERROR or mate is None:
        raise core.Phase0Error(
            f"AddMate3 failed after IEntity.Select4: type={mate_type}, "
            f"error={error}, selected={selected}, "
            f"mark1_count={selected_count_mark1}, returned={returned!r}"
        )
    return {
        "api": "IEntity.Select4+IAssemblyDoc.AddMate3",
        "mate_type": mate_type,
        "mate_align": mate_align,
        "selected": selected,
        "selected_count_mark1": selected_count_mark1,
        "error_status": error,
        "mate_object_returned": True,
    }


def _array_data(component: Any) -> list[float]:
    transform = core.get_com_member(component, "Transform2")
    return [float(v) for v in core.get_com_member(transform, "ArrayData")]


def _transform_point(
    component: Any, local_m: tuple[float, float, float]
) -> tuple[float, float, float]:
    data = _array_data(component)
    x, y, z = local_m
    return (
        x * data[0] + y * data[3] + z * data[6] + data[9],
        x * data[1] + y * data[4] + z * data[7] + data[10],
        x * data[2] + y * data[5] + z * data[8] + data[11],
    )


def _rotate_and_solve(
    session: core.SolidWorksSession,
    model: Any,
    component: Any,
    angle_rad: float,
    translation_m: tuple[float, float, float],
    axis: str = "z",
) -> dict[str, Any]:
    math_utility = session.cast(
        core.get_com_member(session.sw, "GetMathUtility"), "IMathUtility"
    )
    from win32com.client import VARIANT

    if axis == "z":
        transform_data = _transform_data(angle_rad, translation_m)
        angle_indices = (1, 0)
        angle_sign = 1.0
    elif axis == "x":
        c = math.cos(angle_rad)
        s = math.sin(angle_rad)
        transform_data = [
            1.0,
            0.0,
            0.0,
            0.0,
            c,
            s,
            0.0,
            -s,
            c,
            *translation_m,
            1.0,
            0.0,
            0.0,
            0.0,
        ]
        angle_indices = (5, 4)
        angle_sign = 1.0
    elif axis == "y":
        c = math.cos(angle_rad)
        s = math.sin(angle_rad)
        transform_data = [
            c,
            0.0,
            -s,
            0.0,
            1.0,
            0.0,
            s,
            0.0,
            c,
            *translation_m,
            1.0,
            0.0,
            0.0,
            0.0,
        ]
        angle_indices = (2, 0)
        angle_sign = -1.0
    else:
        raise core.Phase0Error(f"unsupported rotation axis: {axis}")
    typed_input = VARIANT(
        session.pythoncom.VT_ARRAY | session.pythoncom.VT_R8,
        transform_data,
    )
    transform = math_utility.CreateTransform(typed_input)
    if transform is None:
        raise core.Phase0Error("CreateTransform for rotation failed")
    try:
        api_ok = bool(component.SetTransformAndSolve3(transform, True))
        api = "SetTransformAndSolve3"
    except Exception:
        api_ok = bool(component.SetTransformAndSolve2(transform))
        api = "SetTransformAndSolve2"
    rebuild_ok = bool(model.EditRebuild3())
    data = _array_data(component)
    recovered = angle_sign * math.atan2(
        data[angle_indices[0]], data[angle_indices[1]]
    )
    return {
        "api": api,
        "api_ok": api_ok,
        "rebuild_ok": rebuild_ok,
        "axis": axis,
        "commanded_rad": angle_rad,
        "readback_rad": recovered,
        "readback_error_rad": recovered - angle_rad,
        "translation_m": data[9:12],
        "rotation_matrix": data[0:9],
        "off_axis_tilt_metric": math.sqrt(
            data[2] ** 2 + data[5] ** 2 + data[6] ** 2 + data[7] ** 2
        ),
    }


def _build_smoke(
    session: core.SolidWorksSession,
    run_root: Path,
    female_part_path: Path,
    male_part_path: Path,
) -> tuple[Path, dict[str, Any]]:
    target = run_root / "assembly" / "B51_REV_MATE_SMOKE.SLDASM"
    model = session.new_document("assembly")
    _trace("ASSEMBLY_DOCUMENT_CREATED")
    fixed = _insert_component(session, model, female_part_path, fixed=True)
    _trace(
        "FIXED_COMPONENT_INSERTED",
        transform=_array_data(fixed),
        box=list(fixed.GetBox(False, False) or []),
    )
    moving = _insert_component(
        session,
        model,
        male_part_path,
        fixed=False,
        translation_m=(0.020, 0.0, 0.010),
    )
    _trace(
        "MOVING_COMPONENT_INSERTED",
        transform=_array_data(moving),
        box=list(moving.GetBox(False, False) or []),
    )
    fixed_cylinder, fixed_plane, topology_a = _datum_entities(session, fixed)
    _trace("FIXED_COMPONENT_FACES_CLASSIFIED", topology=topology_a)
    moving_cylinder, moving_plane, topology_b = _datum_entities(
        session, moving
    )
    _trace("MOVING_COMPONENT_FACES_CLASSIFIED", topology=topology_b)
    assembly = session.cast(model, "IAssemblyDoc")
    _trace("CONCENTRIC_MATE_BEGIN")
    mates = [
        _add_mate_by_entities(
            session,
            model,
            assembly,
            fixed_cylinder,
            moving_cylinder,
            SW_MATE_CONCENTRIC,
        )
    ]
    _trace("CONCENTRIC_MATE_END", result=mates[-1])
    concentric_rebuild = bool(model.EditRebuild3())
    moving_after_concentric = _array_data(moving)
    _trace(
        "CONCENTRIC_MATE_SOLVED",
        rebuild_ok=concentric_rebuild,
        moving_transform=moving_after_concentric,
    )
    _trace("COINCIDENT_MATE_BEGIN")
    mates.append(
        _add_mate_by_entities(
            session,
            model,
            assembly,
            fixed_plane,
            moving_plane,
            SW_MATE_COINCIDENT,
            SW_MATE_ALIGN_ANTI_ALIGNED,
        )
    )
    _trace("COINCIDENT_MATE_END", result=mates[-1])
    _trace("FULL_REBUILD_BEGIN")
    if not model.ForceRebuild3(True):
        raise core.Phase0Error("smoke assembly rebuild failed")
    _trace("FULL_REBUILD_END")
    _trace("CONSTRAINT_READBACK_BEGIN")
    remaining_dofs = moving.GetRemainingDOFs()
    before = {
        "fixed_status": int(fixed.GetConstrainedStatus()),
        "moving_status": int(moving.GetConstrainedStatus()),
        "remaining_dofs_raw": repr(remaining_dofs),
        "transform": _array_data(moving),
    }
    _trace("CONSTRAINT_READBACK_RAW", result=before)
    expected_translation = (0.0, 0.0, 0.002)
    if max(
        abs(before["transform"][9 + index] - expected_translation[index])
        for index in range(3)
    ) > 1.0e-9:
        raise core.Phase0Error(
            "mates did not close translation: "
            f"{before['transform'][9:12]} != {expected_translation}"
        )
    remaining_dofs_result = (
        int(remaining_dofs[0])
        if isinstance(remaining_dofs, tuple)
        else int(remaining_dofs)
    )
    if before["moving_status"] != SW_UNDER_CONSTRAINED:
        raise core.Phase0Error(
            "expected an under-constrained moving component, got "
            f"{before['moving_status']}"
        )
    if remaining_dofs_result != SW_REMAINING_DOFS_RESTRICTED:
        raise core.Phase0Error(
            "expected restricted remaining-DOF result, got "
            f"{remaining_dofs_result}"
        )
    _trace("CONSTRAINT_READBACK_END", result=before)
    _trace("ROTATION_TEST_BEGIN")
    rotation_tests = [
        _rotate_and_solve(
            session,
            model,
            moving,
            math.radians(17.0),
            expected_translation,
            "z",
        ),
        _rotate_and_solve(
            session,
            model,
            moving,
            math.radians(-11.0),
            expected_translation,
            "z",
        ),
        _rotate_and_solve(
            session,
            model,
            moving,
            math.radians(13.0),
            expected_translation,
            "x",
        ),
        _rotate_and_solve(
            session,
            model,
            moving,
            math.radians(-9.0),
            expected_translation,
            "y",
        ),
    ]
    _trace("ROTATION_TEST_END", results=rotation_tests)
    for rotation in rotation_tests[:2]:
        if abs(rotation["readback_error_rad"]) > 1.0e-7:
            raise core.Phase0Error(
                f"allowed revolute rotation readback mismatch: {rotation}"
            )
    for rotation in rotation_tests[2:]:
        if abs(rotation["readback_rad"]) > 1.0e-7:
            raise core.Phase0Error(
                f"off-axis rotation was not rejected: {rotation}"
            )
        if rotation["off_axis_tilt_metric"] > 1.0e-7:
            raise core.Phase0Error(
                f"off-axis tilt remained after solve: {rotation}"
            )
    for rotation in rotation_tests:
        if max(
            abs(rotation["translation_m"][index] - expected_translation[index])
            for index in range(3)
        ) > 1.0e-9:
            raise core.Phase0Error(f"revolute translation drift: {rotation}")
    session.set_text_properties(
        model,
        {
            "OBJECT_ID": "B51_REV_MATE_SMOKE",
            "ASSET_ROLE": "SOLIDWORKS_REVOLUTE_MATE_SMOKE_ONLY",
            "MASS_AUTHORITY": "EXCLUDED",
            "MATE_TOPOLOGY": "MALE_SHAFT_FEMALE_BORE_CONCENTRIC_PLUS_COINCIDENT",
            "RETAINED_DOF": "ONE_ROTATION_ABOUT_DATUM_Z",
            "CLAIM_LIMIT": "tool-chain coupon only; no spacecraft authority",
        },
    )
    save = session.save_as(model, target, require_zero_warnings=False)
    _trace("ASSEMBLY_SAVED", target=str(target))
    session.close_all_documents()
    return target, {
        "component_count": 2,
        "topology_fixed": topology_a,
        "topology_moving": topology_b,
        "mates": mates,
        "constraint_readback_before_rotation": before,
        "rotation_tests": rotation_tests,
        "save": save,
    }


def _reopen_verify(
    session: core.SolidWorksSession, assembly_path: Path
) -> dict[str, Any]:
    _trace("REOPEN_VERIFICATION_BEGIN", path=str(assembly_path))
    model, open_result = session.open_document(assembly_path, "assembly")
    assembly = session.cast(model, "IAssemblyDoc")
    if not model.ForceRebuild3(True):
        raise core.Phase0Error("reopened smoke assembly rebuild failed")
    components = [
        session.cast(component, "IComponent2")
        for component in list(assembly.GetComponents(False) or [])
    ]
    if len(components) != 2:
        raise core.Phase0Error(
            f"reopened component count mismatch: {len(components)}"
        )
    by_name = {
        str(core.get_com_member(component, "Name2")).upper(): component
        for component in components
    }
    fixed = next(
        (
            component
            for name, component in by_name.items()
            if "FEMALE" in name
        ),
        None,
    )
    moving = next(
        (
            component
            for name, component in by_name.items()
            if "MALE" in name
        ),
        None,
    )
    if fixed is None or moving is None:
        raise core.Phase0Error(
            f"reopened component role lookup failed: {list(by_name)}"
        )
    mates = list(moving.GetMates() or [])
    remaining_dofs = moving.GetRemainingDOFs()
    fixed_status = int(fixed.GetConstrainedStatus())
    moving_status = int(moving.GetConstrainedStatus())
    before_transform = _array_data(moving)
    if len(mates) != 2:
        raise core.Phase0Error(f"reopened mate count mismatch: {len(mates)}")
    if fixed_status != 3 or moving_status != SW_UNDER_CONSTRAINED:
        raise core.Phase0Error(
            "reopened constrained status mismatch: "
            f"fixed={fixed_status}, moving={moving_status}"
        )
    remaining_result = (
        int(remaining_dofs[0])
        if isinstance(remaining_dofs, tuple)
        else int(remaining_dofs)
    )
    if remaining_result != SW_REMAINING_DOFS_RESTRICTED:
        raise core.Phase0Error(
            f"reopened remaining-DOF result mismatch: {remaining_result}"
        )
    expected_translation = (0.0, 0.0, 0.002)
    if max(
        abs(before_transform[9 + index] - expected_translation[index])
        for index in range(3)
    ) > 1.0e-9:
        raise core.Phase0Error(
            f"reopened transform translation mismatch: {before_transform}"
        )
    drive_tests = [
        _rotate_and_solve(
            session,
            model,
            moving,
            math.radians(7.0),
            expected_translation,
            "z",
        ),
        _rotate_and_solve(
            session,
            model,
            moving,
            math.radians(-5.0),
            expected_translation,
            "z",
        ),
        _rotate_and_solve(
            session,
            model,
            moving,
            math.radians(4.0),
            expected_translation,
            "x",
        ),
    ]
    for result in drive_tests[:2]:
        if abs(result["readback_error_rad"]) > 1.0e-7:
            raise core.Phase0Error(
                f"reopened allowed rotation mismatch: {result}"
            )
    if (
        abs(drive_tests[2]["readback_rad"]) > 1.0e-7
        or drive_tests[2]["off_axis_tilt_metric"] > 1.0e-7
    ):
        raise core.Phase0Error(
            f"reopened off-axis rotation was not rejected: {drive_tests[2]}"
        )
    for result in drive_tests:
        if max(
            abs(result["translation_m"][index] - expected_translation[index])
            for index in range(3)
        ) > 1.0e-9:
            raise core.Phase0Error(
                f"reopened rotation translation drift: {result}"
            )
    result = {
        "open": open_result,
        "component_names": sorted(by_name),
        "component_count": len(components),
        "mate_count_on_moving_component": len(mates),
        "fixed_status": fixed_status,
        "moving_status": moving_status,
        "remaining_dofs_raw": repr(remaining_dofs),
        "before_transform": before_transform,
        "drive_tests": drive_tests,
        "status": "REOPEN_REPRODUCIBILITY_PASS",
    }
    _trace("REOPEN_VERIFICATION_END", result=result)
    session.close_all_documents()
    return result


def main() -> int:
    global TRACE_PATH
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-id",
        default=datetime.now(timezone.utc).strftime("B51_REV_SMOKE_%Y%m%dT%H%M%SZ"),
    )
    parser.add_argument(
        "--attach-active",
        action="store_true",
        help="attach to exactly one pre-launched, document-free SW instance",
    )
    args = parser.parse_args()
    run_root = NATIVE_ROOT / args.run_id
    report_path = VERIFY_ROOT / f"{args.run_id}.json"
    report: dict[str, Any] = {
        "schema": "SER_B51_REV_MATE_SMOKE_V1",
        "generated_utc": _utc_now(),
        "run_id": args.run_id,
        "status": "B51_REV_MATE_SMOKE_HOLD",
        "scope": "SOLIDWORKS_NATIVE_REVOLUTE_MATE_TOOL_CHAIN_ONLY",
        "mass_authority": "EXCLUDED",
    }
    session: core.SolidWorksSession | None = None
    try:
        if run_root.exists() or report_path.exists():
            raise core.Phase0Error("immutable smoke run already exists")
        run_root.mkdir(parents=True, exist_ok=False)
        TRACE_PATH = run_root / "evidence" / "execution_trace.jsonl"
        _trace("RUN_ROOT_CREATED", run_root=str(run_root))
        VERIFY_ROOT.mkdir(parents=True, exist_ok=True)
        session_type = (
            AttachedSolidWorksSession
            if args.attach_active
            else core.SolidWorksSession
        )
        with session_type(run_root, visible=False) as session:
            _trace("SOLIDWORKS_SESSION_STARTED", session=session.info())
            report["session_start"] = session.info()
            female_path, report["female_part"] = _create_datum_part(
                session, run_root, "female"
            )
            _trace("DATUM_PART_COMPLETE", kind="female", path=str(female_path))
            male_path, report["male_part"] = _create_datum_part(
                session, run_root, "male"
            )
            _trace("DATUM_PART_COMPLETE", kind="male", path=str(male_path))
            assembly_path, report["assembly"] = _build_smoke(
                session, run_root, female_path, male_path
            )
            report["reopen_verification"] = _reopen_verify(
                session, assembly_path
            )
        report["session_end"] = session.info()
        report["artifacts"] = {
            "female_part": core.artifact_record(female_path, run_root),
            "male_part": core.artifact_record(male_path, run_root),
            "assembly": core.artifact_record(assembly_path, run_root),
        }
        report["status"] = "B51_REV_MATE_SMOKE_PASS"
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
    return 0 if report["status"] == "B51_REV_MATE_SMOKE_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
