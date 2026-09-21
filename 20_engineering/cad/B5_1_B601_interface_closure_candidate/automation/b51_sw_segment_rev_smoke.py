"""Prove a revolute mate between two rigid SolidWorks segment subassemblies.

The coupon uses the accepted B601 base_link and link1 vendor geometry.  Each
visual is fixed inside a segment subassembly together with a hidden interface
datum.  The top-level assembly mates the nested datum faces and must retain
exactly the intended J1 rotation after save/reopen.

This is an architecture smoke test only.  It does not establish the complete
6R chain, G08 two-prismatic articulation, spacecraft clearance, or flight
acceptance.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

sys.dont_write_bytecode = True

CANDIDATE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import b51_build_articulated_b601 as articulated  # noqa: E402
import b51_sw_rev_smoke as smoke  # noqa: E402

core = smoke.core
NATIVE_ROOT = CANDIDATE_ROOT / "03_CAD" / "native_articulated"
VERIFY_ROOT = CANDIDATE_ROOT / "07_VERIFICATION" / "articulation"
TRACE_PATH: Path | None = None


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


def _stage_inputs(run_root: Path) -> dict[str, Path]:
    target_root = run_root / "inputs" / "vendor_link_parts"
    target_root.mkdir(parents=True, exist_ok=True)
    staged: dict[str, Path] = {}
    for role in ("base_link", "link1"):
        source = articulated.VISUAL_PARTS[role]
        if not source.is_file():
            raise core.Phase0Error(f"vendor visual missing: {source}")
        target = target_root / source.name
        if target.exists():
            raise core.Phase0Error(f"immutable staged input exists: {target}")
        shutil.copy2(source, target)
        if articulated._sha256(source) != articulated._sha256(target):
            raise core.Phase0Error(f"staged vendor hash mismatch: {role}")
        staged[role] = target
    return staged


def _create_segment(
    session: core.SolidWorksSession,
    run_root: Path,
    *,
    segment_name: str,
    visual_path: Path,
    visual_role: str,
    datum_path: Path,
    datum_role: str,
    datum_transform: np.ndarray,
) -> tuple[Path, dict[str, Any]]:
    target = run_root / "segments" / f"{segment_name}.SLDASM"
    model = session.new_document("assembly")
    visual, visual_record = articulated._insert_component(
        session,
        model,
        visual_path,
        np.eye(4, dtype=float),
        fixed=True,
        role=visual_role,
    )
    datum, datum_record = articulated._insert_component(
        session,
        model,
        datum_path,
        datum_transform,
        fixed=True,
        role=datum_role,
    )
    if not model.ForceRebuild3(True):
        raise core.Phase0Error(f"segment rebuild failed: {segment_name}")
    session.set_text_properties(
        model,
        {
            "OBJECT_ID": segment_name,
            "ASSET_ROLE": "B51_RIGID_SEGMENT_ARCHITECTURE_SMOKE",
            "VISUAL_ROLE": visual_role,
            "DATUM_ROLE": datum_role,
            "KINEMATIC_AUTHORITY": (
                f"ACCEPTED_URDF_SHA256_{articulated.EXPECTED_URDF_SHA256}"
            ),
            "MASS_AUTHORITY": (
                f"ACCEPTED_URDF_{articulated.ACCEPTED_URDF_MASS_KG}_KG_"
                "CAD_AUTO_MASS_NOT_AUTHORIZED"
            ),
            "CLAIM_LIMIT": "J1_SEGMENT_ARCHITECTURE_SMOKE_ONLY",
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
        "visual": visual_record,
        "datum": datum_record,
        "component_names": component_names,
        "component_count": 2,
        "save": save,
    }


def _insert_subassembly(
    session: core.SolidWorksSession,
    model: Any,
    path: Path,
    transform: np.ndarray,
    *,
    fixed: bool,
    role: str,
) -> tuple[Any, dict[str, Any]]:
    source, open_record = session.open_document(path, "assembly")
    source_title = str(core.get_com_member(source, "GetTitle"))
    target_title = str(core.get_com_member(model, "GetTitle"))
    session.activate_document(target_title)
    assembly = session.cast(model, "IAssemblyDoc")
    component = assembly.AddComponent5(
        str(path), 0, "", False, "", 0.0, 0.0, 0.0
    )
    if component is None:
        raise core.Phase0Error(f"subassembly insertion failed: {path}")
    component = session.cast(component, "IComponent2")
    model.ClearSelection2(True)
    if not component.Select4(False, None, False):
        raise core.Phase0Error(f"subassembly selection failed: {role}")
    if bool(core.get_com_member(component, "IsFixed")):
        assembly.UnfixComponent()
    model.ClearSelection2(True)
    transform_result = articulated._set_component_transform(
        session, model, component, transform, tolerance=1.0e-9
    )
    model.ClearSelection2(True)
    if not component.Select4(False, None, False):
        raise core.Phase0Error(f"subassembly final selection failed: {role}")
    if fixed:
        assembly.FixComponent()
    else:
        assembly.UnfixComponent()
    model.ClearSelection2(True)
    fixed_readback = bool(core.get_com_member(component, "IsFixed"))
    if fixed_readback != fixed:
        raise core.Phase0Error(
            f"subassembly fixed-state mismatch: {fixed_readback} != {fixed}"
        )
    session.sw.CloseDoc(source_title)
    return component, {
        "role": role,
        "component_name": str(core.get_com_member(component, "Name2")),
        "source": articulated._file_record(path),
        "source_open": open_record,
        "fixed": fixed_readback,
        "transform": articulated._component_array(component),
        "transform_set": transform_result,
    }


def _children(session: core.SolidWorksSession, component: Any) -> list[Any]:
    children = [
        session.cast(child, "IComponent2")
        for child in list(component.GetChildren() or [])
    ]
    if len(children) != 2:
        raise core.Phase0Error(
            "segment nested child count mismatch: "
            f"{core.get_com_member(component, 'Name2')} -> {len(children)}"
        )
    return children


def _find_nested(
    session: core.SolidWorksSession, component: Any, token: str
) -> Any:
    matches = [
        child
        for child in _children(session, component)
        if token.upper()
        in str(core.get_com_member(child, "Name2")).upper()
    ]
    if len(matches) != 1:
        names = [
            str(core.get_com_member(child, "Name2"))
            for child in _children(session, component)
        ]
        raise core.Phase0Error(
            f"nested role lookup failed token={token!r}, names={names}"
        )
    return matches[0]


def _total_array(component: Any) -> list[float]:
    transform = component.GetTotalTransform(True)
    if transform is None:
        transform = core.get_com_member(component, "Transform2")
    return [
        float(value)
        for value in core.get_com_member(transform, "ArrayData")
    ]


def _remaining_dofs(component: Any) -> dict[str, Any]:
    raw = component.GetRemainingDOFs()
    result = int(raw[0]) if isinstance(raw, tuple) else int(raw)
    return {"raw": repr(raw), "result": result}


def _verify_nested_visual_follows(
    moving_segment: Any,
    link1_visual: Any,
    expected_segment_transform: list[float],
    *,
    tolerance: float = 2.0e-7,
) -> dict[str, Any]:
    segment = articulated._component_array(moving_segment)
    nested_total = _total_array(link1_visual)
    segment_error = articulated._max_error(
        segment, expected_segment_transform
    )
    nested_error = articulated._max_error(
        nested_total, expected_segment_transform
    )
    if segment_error > tolerance or nested_error > tolerance:
        raise core.Phase0Error(
            "rigid segment/vendor visual propagation mismatch: "
            f"segment={segment_error}, nested={nested_error}"
        )
    return {
        "segment_max_abs_error": segment_error,
        "nested_vendor_total_max_abs_error": nested_error,
        "segment_transform": segment,
        "nested_vendor_total_transform": nested_total,
    }


def _drive(
    session: core.SolidWorksSession,
    model: Any,
    moving_segment: Any,
    link1_visual: Any,
    angle_rad: float,
    translation: tuple[float, float, float],
    axis: str,
) -> dict[str, Any]:
    result = smoke._rotate_and_solve(
        session,
        model,
        moving_segment,
        angle_rad,
        translation,
        axis,
    )
    expected_angle = angle_rad if axis == "z" else 0.0
    expected = smoke._transform_data(expected_angle, translation)
    follow = _verify_nested_visual_follows(
        moving_segment, link1_visual, expected
    )
    result["nested_vendor_follow"] = follow
    if axis == "z":
        if abs(result["readback_error_rad"]) > 1.0e-7:
            raise core.Phase0Error(
                f"segment allowed J1 rotation mismatch: {result}"
            )
    elif (
        abs(result["readback_rad"]) > 1.0e-7
        or result["off_axis_tilt_metric"] > 1.0e-7
    ):
        raise core.Phase0Error(
            f"segment off-axis rotation was not rejected: {result}"
        )
    if max(
        abs(result["translation_m"][index] - translation[index])
        for index in range(3)
    ) > 1.0e-9:
        raise core.Phase0Error(
            f"segment revolute translation drift: {result}"
        )
    return result


def _build(
    session: core.SolidWorksSession,
    run_root: Path,
    chain: dict[str, Any],
    staged: dict[str, Path],
) -> tuple[Path, dict[str, Any]]:
    female_path, female_create = smoke._create_datum_part(
        session, run_root, "female"
    )
    male_path, male_create = smoke._create_datum_part(
        session, run_root, "male"
    )
    joint1 = chain["joints"][0]
    joint1_origin = articulated._origin_transform(joint1)
    z_back = articulated._transform(
        np.asarray([0.0, 0.0, -0.002], dtype=float)
    )
    base_segment, base_record = _create_segment(
        session,
        run_root,
        segment_name="B51_SEGMENT_0_BASE",
        visual_path=staged["base_link"],
        visual_role="VENDOR_VISUAL_base_link",
        datum_path=female_path,
        datum_role="J1_FEMALE_PARENT_DATUM",
        datum_transform=joint1_origin @ z_back,
    )
    link1_segment, link1_record = _create_segment(
        session,
        run_root,
        segment_name="B51_SEGMENT_1_LINK1",
        visual_path=staged["link1"],
        visual_role="VENDOR_VISUAL_link1",
        datum_path=male_path,
        datum_role="J1_MALE_CHILD_DATUM",
        datum_transform=np.eye(4, dtype=float),
    )
    target = run_root / "assembly" / "B51_SEGMENT_J1_REV_SMOKE.SLDASM"
    model = session.new_document("assembly")
    assembly = session.cast(model, "IAssemblyDoc")
    base, base_insert = _insert_subassembly(
        session,
        model,
        base_segment,
        np.eye(4, dtype=float),
        fixed=True,
        role="BASE_RIGID_SEGMENT",
    )
    moving, moving_insert = _insert_subassembly(
        session,
        model,
        link1_segment,
        joint1_origin,
        fixed=False,
        role="LINK1_RIGID_SEGMENT",
    )
    base_female = _find_nested(session, base, "FEMALE")
    link1_male = _find_nested(session, moving, "MALE")
    link1_visual = _find_nested(session, moving, "LINKLOCAL")
    female_cyl, female_plane, female_topology = smoke._datum_entities(
        session, base_female
    )
    male_cyl, male_plane, male_topology = smoke._datum_entities(
        session, link1_male
    )
    mates = [
        articulated._add_entity_mate(
            session,
            model,
            assembly,
            female_cyl,
            male_cyl,
            articulated.SW_MATE_CONCENTRIC,
            articulated.SW_MATE_ALIGN_ALIGNED,
            "J1_SEGMENT_CONCENTRIC",
        ),
        articulated._add_entity_mate(
            session,
            model,
            assembly,
            female_plane,
            male_plane,
            articulated.SW_MATE_COINCIDENT,
            articulated.SW_MATE_ALIGN_ANTI_ALIGNED,
            "J1_SEGMENT_COINCIDENT",
        ),
    ]
    if not model.ForceRebuild3(True):
        raise core.Phase0Error("segment J1 assembly rebuild failed")
    before = {
        "base_status": int(base.GetConstrainedStatus()),
        "moving_status": int(moving.GetConstrainedStatus()),
        "remaining_dofs": _remaining_dofs(moving),
        "moving_transform": articulated._component_array(moving),
        "nested_link1_total_transform": _total_array(link1_visual),
    }
    if before["moving_status"] != smoke.SW_UNDER_CONSTRAINED:
        raise core.Phase0Error(
            f"segment moving status is not under-constrained: {before}"
        )
    if (
        before["remaining_dofs"]["result"]
        != smoke.SW_REMAINING_DOFS_RESTRICTED
    ):
        raise core.Phase0Error(
            f"segment remaining DOFs are not restricted: {before}"
        )
    expected_q0 = articulated._matrix_array(joint1_origin)
    q0_follow = _verify_nested_visual_follows(
        moving, link1_visual, expected_q0
    )
    pretest_target = (
        run_root
        / "assembly"
        / "B51_SEGMENT_J1_REV_SMOKE_PRETEST.SLDASM"
    )
    pretest_save = session.save_as(
        model, pretest_target, require_zero_warnings=False
    )
    translation = tuple(float(value) for value in joint1["xyz"])
    drive_tests = [
        _drive(
            session,
            model,
            moving,
            link1_visual,
            math.radians(17.0),
            translation,
            "z",
        ),
        _drive(
            session,
            model,
            moving,
            link1_visual,
            math.radians(-11.0),
            translation,
            "z",
        ),
        _drive(
            session,
            model,
            moving,
            link1_visual,
            math.radians(13.0),
            translation,
            "x",
        ),
        _drive(
            session,
            model,
            moving,
            link1_visual,
            math.radians(-9.0),
            translation,
            "y",
        ),
        _drive(
            session,
            model,
            moving,
            link1_visual,
            0.0,
            translation,
            "z",
        ),
    ]
    session.set_text_properties(
        model,
        {
            "OBJECT_ID": "B51_SEGMENT_J1_REV_SMOKE",
            "ASSET_ROLE": "NATIVE_RIGID_SEGMENT_REVOLUTE_ARCHITECTURE_SMOKE",
            "TOPOLOGY": (
                "TWO_RIGID_SUBASSEMBLIES_NESTED_DATUM_CONCENTRIC_"
                "PLUS_COINCIDENT"
            ),
            "KINEMATIC_AUTHORITY": (
                f"ACCEPTED_URDF_SHA256_{articulated.EXPECTED_URDF_SHA256}"
            ),
            "MASS_AUTHORITY": (
                f"ACCEPTED_URDF_{articulated.ACCEPTED_URDF_MASS_KG}_KG_"
                "CAD_AUTO_MASS_NOT_AUTHORIZED"
            ),
            "G08_2P_STATUS": (
                "B51_2P_GRIPPER_PARTITION_AND_ZERO_CALIBRATION_HOLD"
            ),
            "CLAIM_LIMIT": (
                "J1_ARCHITECTURE_SMOKE_ONLY_NOT_COMPLETE_6R_OR_FLIGHT_READY"
            ),
        },
    )
    save = session.save_as(model, target, require_zero_warnings=False)
    nested_component_names = {
        "base": [
            str(core.get_com_member(child, "Name2"))
            for child in _children(session, base)
        ],
        "moving": [
            str(core.get_com_member(child, "Name2"))
            for child in _children(session, moving)
        ],
    }
    session.close_all_documents()
    return target, {
        "datum_parts": {
            "female": {"path": str(female_path), "create": female_create},
            "male": {"path": str(male_path), "create": male_create},
        },
        "segments": {
            "base": {
                "path": str(base_segment),
                "record": base_record,
            },
            "link1": {
                "path": str(link1_segment),
                "record": link1_record,
            },
        },
        "insertions": [base_insert, moving_insert],
        "nested_component_names": nested_component_names,
        "topology": {
            "female": female_topology,
            "male": male_topology,
        },
        "mates": mates,
        "constraint_readback": before,
        "q0_nested_vendor_follow": q0_follow,
        "pretest_save": pretest_save,
        "drive_tests": drive_tests,
        "save": save,
    }


def _reopen_verify(
    session: core.SolidWorksSession,
    assembly_path: Path,
    chain: dict[str, Any],
) -> dict[str, Any]:
    model, open_record = session.open_document(assembly_path, "assembly")
    assembly = session.cast(model, "IAssemblyDoc")
    if not model.ForceRebuild3(True):
        raise core.Phase0Error("reopened segment smoke rebuild failed")
    top = [
        session.cast(component, "IComponent2")
        for component in list(assembly.GetComponents(True) or [])
    ]
    if len(top) != 2:
        raise core.Phase0Error(
            f"reopened top-level segment count mismatch: {len(top)}"
        )
    fixed = next(
        (
            component
            for component in top
            if "SEGMENT_0_BASE"
            in str(core.get_com_member(component, "Name2")).upper()
        ),
        None,
    )
    moving = next(
        (
            component
            for component in top
            if "SEGMENT_1_LINK1"
            in str(core.get_com_member(component, "Name2")).upper()
        ),
        None,
    )
    if fixed is None or moving is None:
        raise core.Phase0Error(
            "reopened top-level segment role lookup failed: "
            f"{[core.get_com_member(c, 'Name2') for c in top]}"
        )
    link1_visual = _find_nested(session, moving, "LINKLOCAL")
    mates = list(moving.GetMates() or [])
    if len(mates) != 2:
        raise core.Phase0Error(
            f"reopened segment mate count mismatch: {len(mates)}"
        )
    remaining = _remaining_dofs(moving)
    if remaining["result"] != smoke.SW_REMAINING_DOFS_RESTRICTED:
        raise core.Phase0Error(
            f"reopened segment remaining DOFs mismatch: {remaining}"
        )
    joint1 = chain["joints"][0]
    translation = tuple(float(value) for value in joint1["xyz"])
    drives = [
        _drive(
            session,
            model,
            moving,
            link1_visual,
            math.radians(7.0),
            translation,
            "z",
        ),
        _drive(
            session,
            model,
            moving,
            link1_visual,
            math.radians(-5.0),
            translation,
            "z",
        ),
        _drive(
            session,
            model,
            moving,
            link1_visual,
            math.radians(4.0),
            translation,
            "x",
        ),
        _drive(
            session,
            model,
            moving,
            link1_visual,
            0.0,
            translation,
            "z",
        ),
    ]
    result = {
        "open": open_record,
        "top_level_component_names": sorted(
            str(core.get_com_member(component, "Name2"))
            for component in top
        ),
        "mate_count_on_moving_segment": len(mates),
        "fixed_status": int(fixed.GetConstrainedStatus()),
        "moving_status": int(moving.GetConstrainedStatus()),
        "remaining_dofs": remaining,
        "drive_tests": drives,
        "status": "SEGMENT_J1_REOPEN_REPRODUCIBILITY_PASS",
    }
    session.close_all_documents()
    return result


def main() -> int:
    global TRACE_PATH
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--run-id",
        default=datetime.now(timezone.utc).strftime(
            "B51_SEGMENT_REV_SMOKE_%Y%m%dT%H%M%SZ"
        ),
    )
    parser.add_argument("--attach-active", action="store_true")
    args = parser.parse_args()
    run_root = NATIVE_ROOT / args.run_id
    report_path = VERIFY_ROOT / f"{args.run_id}.json"
    report: dict[str, Any] = {
        "schema": "SER_B51_RIGID_SEGMENT_REV_SMOKE_V1",
        "generated_utc": _utc_now(),
        "run_id": args.run_id,
        "status": "B51_RIGID_SEGMENT_REV_SMOKE_HOLD",
        "scope": (
            "SOLIDWORKS_NATIVE_J1_RIGID_SEGMENT_ARCHITECTURE_SMOKE_ONLY"
        ),
        "mass_authority": {
            "source": "ACCEPTED_URDF",
            "kg": articulated.ACCEPTED_URDF_MASS_KG,
            "cad_auto_mass_authorized": False,
        },
        "g08_2p_status": (
            "B51_2P_GRIPPER_PARTITION_AND_ZERO_CALIBRATION_HOLD"
        ),
    }
    session: core.SolidWorksSession | None = None
    try:
        if run_root.exists() or report_path.exists():
            raise core.Phase0Error("immutable segment smoke run exists")
        run_root.mkdir(parents=True, exist_ok=False)
        TRACE_PATH = run_root / "evidence" / "execution_trace.jsonl"
        smoke.TRACE_PATH = TRACE_PATH
        articulated.TRACE_PATH = TRACE_PATH
        _trace("RUN_ROOT_CREATED", run_root=str(run_root))
        VERIFY_ROOT.mkdir(parents=True, exist_ok=True)
        chain = articulated._parse_urdf()
        report["kinematic_chain"] = articulated._json_chain(chain)
        staged = _stage_inputs(run_root)
        report["staged_inputs"] = {
            role: articulated._file_record(path)
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
            assembly_path, report["build"] = _build(
                session, run_root, chain, staged
            )
            report["reopen_verification"] = _reopen_verify(
                session, assembly_path, chain
            )
        report["session_end"] = session.info()
        report["artifacts"] = {
            "assembly": core.artifact_record(assembly_path, run_root),
            "trace": core.artifact_record(TRACE_PATH, run_root),
        }
        report["status"] = "B51_RIGID_SEGMENT_REV_SMOKE_PASS"
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
    return 0 if report["status"] == "B51_RIGID_SEGMENT_REV_SMOKE_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
