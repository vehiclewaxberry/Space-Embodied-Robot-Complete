"""Build the isolated B5.0 native SolidWorks B601 engineering-reference arm.

The accepted URDF remains the sole kinematic and mass authority.  This writer
imports the registered vendor groups as link-local multibody reference parts,
creates an accepted-q0 master skeleton, and assembles the parts with explicit
source-derived transforms.  The q0 assembly is intentionally fixed and is not
evidence of retained mechanism degrees of freedom.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from win32com.client import VARIANT

sys.dont_write_bytecode = True

from sw_b50_core import (  # noqa: E402
    CANDIDATE_ROOT,
    Phase0Error,
    SolidWorksSession,
    artifact_record,
    get_com_member,
    require_within,
    sha256_file,
    utc_now,
    write_json_once,
)


RUNS_ROOT = CANDIDATE_ROOT / "03_CAD" / "native_runs"
CHAIN_PATH = CANDIDATE_ROOT / "01_KINEMATICS" / "accepted_chain.json"
VENDOR_LEDGER_PATH = (
    CANDIDATE_ROOT / "02_DESIGN" / "vendor_registration_ledger.json"
)
EXPECTED_URDF_SHA256 = (
    "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
)
EXPECTED_MASS_SOURCE = "4.6955559493429862"

GROUP_LINK = {
    "G01": "link1",
    "G02": "link2",
    "G03": "link3",
    "G04": "link4",
    "G05": "link6",
    "G06": "base_link",
    "G07": "link5",
    "G08": "gripper_link",
}
GROUP_ORDER = ["G06", "G01", "G02", "G03", "G04", "G07", "G05", "G08"]
PART_STEM = {
    "G01": "B50_REF_link1_LINKLOCAL",
    "G02": "B50_REF_link2_LINKLOCAL",
    "G03": "B50_REF_link3_LINKLOCAL",
    "G04": "B50_REF_link4_LINKLOCAL",
    "G05": "B50_REF_link6_LINKLOCAL",
    "G06": "B50_REF_base_link_LINKLOCAL",
    "G07": "B50_REF_link5_LINKLOCAL",
    "G08": "B50_REF_gripper_detail_LINKLOCAL",
}

PREF_INTEGER = {201: 1}
PREF_TOGGLES = {615: True, 710: False, 712: False, 713: False, 716: False}
IMPORT_PREF_INTEGER = {
    577: 0,  # swImportNeutral_KnitOption = FormSolids
    578: 1,  # swImportNeutral_CurvesAndPointsOption = As3DCurves (disabled below)
    579: 2,  # swImportNeutralAssemblyStructureMapping = MultibodyPart
    580: 0,  # swImportNeutralUnits = ImportFileUnits
}
IMPORT_PREF_TOGGLE = {
    291: False,  # swImportAutoRunImportDiagnostics (avoid modal diagnostics)
    686: True,   # swImportNeutral_SolidandSurface
    687: False,  # swImportNeutral_FreeCurvesAndPoints
    688: False,  # swImportNeutralReferencePlane
    689: False,  # swImportNeutral_AttributesAndProperties
    690: False,  # swImportNeutralRunDiagnostics (geometry is gated separately)
    691: False,  # swMultiCAD_Enable3DInterconnect
    696: False,  # swImportReferencePlane
    697: False,  # swImportReferenceAxis
    698: False,  # swImportUnconsumedSketchesAndCurves
    699: False,  # swImportCustomProperties
    700: False,  # swImportMaterialProperties
    701: False,  # swImportDissolveTopLevelAssemblyOnOpen
}


def _run_root(run_id: str) -> Path:
    if not run_id or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-" for ch in run_id):
        raise Phase0Error(f"invalid run id: {run_id!r}")
    return require_within(RUNS_ROOT / run_id, RUNS_ROOT, "native_run_root")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _source_contract() -> tuple[dict[str, Any], dict[str, Any]]:
    if not CHAIN_PATH.is_file() or not VENDOR_LEDGER_PATH.is_file():
        raise Phase0Error("accepted-chain or vendor-registration evidence is missing")
    chain = _load_json(CHAIN_PATH)
    vendor = _load_json(VENDOR_LEDGER_PATH)
    if str(chain["source"]["sha256"]).upper() != EXPECTED_URDF_SHA256:
        raise Phase0Error("accepted URDF hash drift in accepted_chain.json")
    if str(chain["mass"]["total_kg_source_decimal"]) != EXPECTED_MASS_SOURCE:
        raise Phase0Error("accepted mass source string drift")
    if vendor.get("verdict") != (
        "B5_0_VENDOR_LINKLOCAL_REGISTRATION_PASS_WITH_G05_G08_HOLD"
    ):
        raise Phase0Error("vendor link-local registration is not admitted")
    if vendor.get("hold_groups") != ["G05", "G08"]:
        raise Phase0Error("vendor hold-group contract drift")
    return chain, vendor


def _vendor_item(vendor: dict[str, Any], group: str) -> dict[str, Any]:
    for item in vendor["groups"]:
        if item["group"] == group:
            if item["accepted_link_frame"] != GROUP_LINK[group]:
                raise Phase0Error(f"{group} accepted-link mapping drift")
            return item
    raise Phase0Error(f"vendor group absent from ledger: {group}")


def _part_path(run_root: Path, group: str) -> Path:
    return run_root / "10_vendor_reference_parts" / f"{PART_STEM[group]}.SLDPRT"


def _receipt_path(run_root: Path, name: str) -> Path:
    return run_root / "evidence" / f"{name}.json"


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _document_type(model: Any) -> int:
    return int(get_com_member(model, "GetType"))


def _part_facts(session: SolidWorksSession, model: Any) -> dict[str, Any]:
    part = session.cast(model, "IPartDoc")
    bodies = _as_list(part.GetBodies2(0, False))
    boxes: list[list[float]] = []
    for body in bodies:
        cast_body = session.cast(body, "IBody2")
        values = _as_list(get_com_member(cast_body, "GetBodyBox"))
        if len(values) == 6:
            boxes.append([float(value) * 1000.0 for value in values])
    if not boxes:
        bbox = None
    else:
        bbox = [
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            min(box[2] for box in boxes),
            max(box[3] for box in boxes),
            max(box[4] for box in boxes),
            max(box[5] for box in boxes),
        ]
    return {"solid_body_count": len(bodies), "bounding_box_mm": bbox}


def _external_reference_count(model: Any) -> int | None:
    try:
        return int(model.ListExternalFileReferencesCount2())
    except Exception:
        try:
            return int(model.ListExternalFileReferencesCount(False))
        except Exception:
            return None


def _auxiliary_external_reference_count(model: Any) -> int | None:
    try:
        return int(model.ListAuxiliaryExternalFileReferencesCount())
    except Exception:
        return None


def _three_d_interconnect_features(
    session: SolidWorksSession, model: Any
) -> list[str]:
    names: list[str] = []
    feature = get_com_member(model, "FirstFeature")
    visited = 0
    while feature is not None and visited < 10000:
        cast_feature = session.cast(feature, "IFeature")
        try:
            if bool(get_com_member(cast_feature, "Is3DInterconnectFeature")):
                names.append(str(get_com_member(cast_feature, "Name")))
        except Exception:
            pass
        feature = get_com_member(cast_feature, "GetNextFeature")
        visited += 1
    if visited >= 10000:
        raise Phase0Error("feature traversal exceeded safety limit")
    return names


def _load_step(
    session: SolidWorksSession, path: Path, preference_tag: str
) -> tuple[Any, dict[str, Any]]:
    path = require_within(path, CANDIDATE_ROOT, "registered_step")
    before_path = (
        session.run_root
        / "evidence"
        / f"{preference_tag}_import_preferences_before.json"
    )
    after_path = (
        session.run_root
        / "evidence"
        / f"{preference_tag}_import_preferences_after.json"
    )
    if before_path.exists() or after_path.exists():
        raise Phase0Error(
            f"import-preference evidence already exists for {preference_tag}"
        )
    before = {
        "integer": {
            str(key): int(session.sw.GetUserPreferenceIntegerValue(key))
            for key in IMPORT_PREF_INTEGER
        },
        "toggle": {
            str(key): bool(session.sw.GetUserPreferenceToggle(key))
            for key in IMPORT_PREF_TOGGLE
        },
    }
    target = {
        "integer": {
            str(key): int(value)
            for key, value in IMPORT_PREF_INTEGER.items()
        },
        "toggle": {
            str(key): bool(value)
            for key, value in IMPORT_PREF_TOGGLE.items()
        },
    }
    write_json_once(
        before_path,
        {
            "schema": "SER_B50_IMPORT_PREFERENCES_BEFORE_V1",
            "generated_utc": utc_now(),
            "preference_tag": preference_tag,
            "source_step": str(path),
            "before": before,
            "target": target,
            "restoration_required_if_after_receipt_missing": True,
        },
        session.run_root,
    )
    map_configuration_data: bool | None = None
    returned: Any = None
    started = time.perf_counter()
    try:
        _set_save_preferences(session.sw, target)
        applied = {
            "integer": {
                str(key): int(session.sw.GetUserPreferenceIntegerValue(key))
                for key in IMPORT_PREF_INTEGER
            },
            "toggle": {
                str(key): bool(session.sw.GetUserPreferenceToggle(key))
                for key in IMPORT_PREF_TOGGLE
            },
        }
        if applied != target:
            raise Phase0Error(
                f"classic STEP import preference readback mismatch: {applied}"
            )
        import_data = session.sw.GetImportFileData(str(path))
        if import_data is None:
            raise Phase0Error(f"GetImportFileData returned no object: {path}")
        try:
            import_data = session.cast(import_data, "IImportStepData")
            import_data.MapConfigurationData = False
            map_configuration_data = bool(import_data.MapConfigurationData)
        except Exception:
            map_configuration_data = None
        # "r" follows the SolidWorks classic STEP-import API example and
        # prevents a linked 3D Interconnect representation.
        returned = session.sw.LoadFile4(str(path), "r", import_data, 0)
    finally:
        _set_save_preferences(session.sw, before)
        restored = {
            "integer": {
                str(key): int(session.sw.GetUserPreferenceIntegerValue(key))
                for key in IMPORT_PREF_INTEGER
            },
            "toggle": {
                str(key): bool(session.sw.GetUserPreferenceToggle(key))
                for key in IMPORT_PREF_TOGGLE
            },
        }
        write_json_once(
            after_path,
            {
                "schema": "SER_B50_IMPORT_PREFERENCES_AFTER_V1",
                "generated_utc": utc_now(),
                "preference_tag": preference_tag,
                "before": before,
                "target": target,
                "restored": restored,
                "restoration_pass": restored == before,
            },
            session.run_root,
        )
        if restored != before:
            raise Phase0Error(
                f"classic STEP import preferences were not restored: {restored}"
            )
    elapsed = round(time.perf_counter() - started, 3)
    if isinstance(returned, tuple):
        model = returned[0]
        errors = int(returned[1]) if len(returned) > 1 else 0
    else:
        model = returned
        errors = 0
    if model is None:
        raise Phase0Error(f"LoadFile4 returned no model: errors={errors}")
    if errors != 0:
        raise Phase0Error(f"LoadFile4 returned error {errors}: {path}")
    model = session.cast(model, "IModelDoc2")
    return model, {
        "api": "GetImportFileData+LoadFile4",
        "arg_string": "r",
        "import_mode": "CLASSIC_STEP_3D_INTERCONNECT_DISABLED",
        "elapsed_sec": elapsed,
        "errors": errors,
        "map_configuration_data": map_configuration_data,
        "document_type": _document_type(model),
    }


def _snapshot_save_preferences(sw: Any) -> dict[str, dict[str, Any]]:
    return {
        "integer": {
            str(key): int(sw.GetUserPreferenceIntegerValue(key))
            for key in PREF_INTEGER
        },
        "toggle": {
            str(key): bool(sw.GetUserPreferenceToggle(key))
            for key in PREF_TOGGLES
        },
    }


def _target_save_preferences() -> dict[str, dict[str, Any]]:
    return {
        "integer": {str(key): int(value) for key, value in PREF_INTEGER.items()},
        "toggle": {str(key): bool(value) for key, value in PREF_TOGGLES.items()},
    }


def _set_save_preferences(sw: Any, values: dict[str, dict[str, Any]]) -> None:
    for key, value in values["integer"].items():
        sw.SetUserPreferenceIntegerValue(int(key), int(value))
    for key, value in values["toggle"].items():
        sw.SetUserPreferenceToggle(int(key), bool(value))


def _assembly_to_part(
    session: SolidWorksSession, model: Any, target: Path
) -> dict[str, Any]:
    target = require_within(target, session.run_root, "assembly_to_part")
    if target.exists():
        raise Phase0Error(f"save target already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    before = _snapshot_save_preferences(session.sw)
    applied = _target_save_preferences()
    errors = warnings = 0
    try:
        _set_save_preferences(session.sw, applied)
        readback = _snapshot_save_preferences(session.sw)
        if readback != applied:
            raise Phase0Error(
                f"assembly-to-part preference readback mismatch: {readback}"
            )
        returned = model.Extension.SaveAs3(
            str(target), 0, 1, None, None, 0, 0
        )
        if isinstance(returned, tuple):
            ok = bool(returned[0])
            errors = int(returned[1]) if len(returned) > 1 else 0
            warnings = int(returned[2]) if len(returned) > 2 else 0
        else:
            ok = bool(returned)
        if not ok or errors != 0 or not target.is_file():
            raise Phase0Error(
                "assembly SaveAs3 multibody part failed: "
                f"ok={ok}, errors={errors}, warnings={warnings}"
            )
    finally:
        _set_save_preferences(session.sw, before)
        restored = _snapshot_save_preferences(session.sw)
        if restored != before:
            raise Phase0Error(
                f"SolidWorks save preferences were not restored: {restored}"
            )
    return {
        "path": target.relative_to(session.run_root).as_posix(),
        "api": "IModelDocExtension.SaveAs3",
        "errors": errors,
        "warnings": warnings,
        "preference_before": before,
        "preference_applied": applied,
        "preference_restored": restored,
        "bytes": target.stat().st_size,
        "sha256": sha256_file(target),
    }


def _import_group(
    session: SolidWorksSession,
    run_root: Path,
    group: str,
    chain: dict[str, Any],
    vendor: dict[str, Any],
) -> dict[str, Any]:
    item = _vendor_item(vendor, group)
    # The ledger path is workspace-relative, while CANDIDATE_ROOT starts below it.
    source = (
        CANDIDATE_ROOT
        / "02_DESIGN"
        / "vendor_reference_linklocal"
        / f"{PART_STEM[group]}.step"
    )
    if not source.is_file():
        raise Phase0Error(f"registered link-local STEP missing: {source}")
    if sha256_file(source) != item["output"]["sha256"]:
        raise Phase0Error(f"registered link-local STEP hash drift: {group}")
    target = _part_path(run_root, group)
    model, import_record = _load_step(session, source, f"native_{group}")
    doc_type = _document_type(model)
    interconnect_features = _three_d_interconnect_features(session, model)
    if interconnect_features:
        raise Phase0Error(
            f"{group} imported as 3D Interconnect features: "
            f"{interconnect_features}"
        )
    external_before = _external_reference_count(model)
    auxiliary_external_before = _auxiliary_external_reference_count(model)
    try:
        model.Extension.BreakAllExternalFileReferences2(True)
        break_called = True
    except Exception as exc:
        break_called = False
        break_error = repr(exc)
    external_after = _external_reference_count(model)
    auxiliary_external_after = _auxiliary_external_reference_count(model)
    properties = {
        "OBJECT_ID": f"B50_VENDOR_REF_{GROUP_LINK[group]}",
        "REPRESENTATION_LAYER": "L1_VENDOR_REFERENCE_LINKLOCAL",
        "GEOMETRY_AUTHORITY": source.name,
        "SOURCE_STEP_SHA256": item["output"]["sha256"],
        "SOURCE_REGISTRATION_METHOD": item["method"],
        "SOURCE_REGISTRATION_STATUS": item["status"],
        "ACCEPTED_LINK_FRAME": GROUP_LINK[group],
        "KINEMATICS_AUTHORITY": "EXCLUDED_ACCEPTED_URDF_ONLY",
        "MASS_AUTHORITY": "EXCLUDED_ACCEPTED_URDF_ONLY",
        "ACCEPTED_URDF_SHA256": EXPECTED_URDF_SHA256,
        "GEOMETRY_LICENSE": "CERN-OHL-W-2.0",
        "INTERNAL_RESEARCH_NO_REDISTRIBUTION": "TRUE",
        "MANUFACTURING_AUTHORITY": "NONE",
        "RUN_ID": run_root.name,
        "CLAIM_LIMIT": (
            "reference geometry only; no material, strength, fit, tolerance, "
            "environmental or flight authority"
        ),
    }
    session.set_text_properties(model, properties)
    pre_facts = _part_facts(session, model) if doc_type == 1 else None
    if doc_type == 1:
        save = session.save_as(model, target, require_zero_warnings=False)
    elif doc_type == 2:
        save = _assembly_to_part(session, model, target)
    else:
        raise Phase0Error(f"{group} imported unsupported document type {doc_type}")
    session.close_all_documents()
    cold_model, cold_open = session.open_document(target, "part")
    cold_facts = _part_facts(session, cold_model)
    cold_properties = {
        name: session.read_text_property(cold_model, name)
        for name in (
            "OBJECT_ID",
            "MASS_AUTHORITY",
            "ACCEPTED_URDF_SHA256",
            "SOURCE_REGISTRATION_STATUS",
        )
    }
    session.close_all_documents()
    expected_bodies = int(item["output_stats"]["solid_count"])
    if cold_facts["solid_body_count"] != expected_bodies:
        raise Phase0Error(
            f"{group} cold body count {cold_facts['solid_body_count']} "
            f"!= registered {expected_bodies}"
        )
    if cold_properties["MASS_AUTHORITY"] != "EXCLUDED_ACCEPTED_URDF_ONLY":
        raise Phase0Error(f"{group} mass-exclusion property did not persist")
    if cold_properties["ACCEPTED_URDF_SHA256"] != EXPECTED_URDF_SHA256:
        raise Phase0Error(f"{group} accepted-URDF property did not persist")
    if external_after not in (None, 0):
        raise Phase0Error(f"{group} retained {external_after} external references")
    if auxiliary_external_after not in (None, 0):
        raise Phase0Error(
            f"{group} retained {auxiliary_external_after} auxiliary references"
        )
    return {
        "group": group,
        "accepted_link": GROUP_LINK[group],
        "registration_method": item["method"],
        "registration_status": item["status"],
        "source": artifact_record(source, CANDIDATE_ROOT),
        "import": import_record,
        "imported_document_type": doc_type,
        "three_d_interconnect_features": interconnect_features,
        "pre_save_part_facts": pre_facts,
        "external_references_before": external_before,
        "auxiliary_external_references_before": auxiliary_external_before,
        "break_external_references_called": break_called,
        "break_external_references_error": (
            None if break_called else break_error
        ),
        "external_references_after": external_after,
        "auxiliary_external_references_after": auxiliary_external_after,
        "save": save,
        "cold_open": cold_open,
        "cold_facts": cold_facts,
        "cold_properties": cold_properties,
        "expected_solid_body_count": expected_bodies,
        "verdict": f"B5_0_NATIVE_{group}_PASS",
    }


def _sketch_feature(active_sketch: Any) -> Any:
    if active_sketch is None:
        return None
    try:
        return active_sketch.GetFeature()
    except Exception:
        return None


def _create_master_skeleton(
    session: SolidWorksSession,
    run_root: Path,
    chain: dict[str, Any],
) -> dict[str, Any]:
    target = run_root / "00_skeleton" / "B50_B601_MASTER_SKELETON.SLDPRT"
    if target.exists():
        raise Phase0Error(f"skeleton target already exists: {target}")
    model = session.new_document("part")
    sketch_manager = model.SketchManager
    link_frames = chain["q0_frames_A0"]
    joint_frames = chain["q0_joint_frames_A0"]
    link_points: dict[str, tuple[float, float, float]] = {
        name: (
            float(matrix[0][3]),
            float(matrix[1][3]),
            float(matrix[2][3]),
        )
        for name, matrix in link_frames.items()
    }

    sketch_manager.Insert3DSketch(True)
    active = get_com_member(sketch_manager, "ActiveSketch")
    point_count = 0
    line_count = 0
    for name in [item["name"] for item in chain["links"]]:
        if sketch_manager.CreatePoint(*link_points[name]) is None:
            raise Phase0Error(f"cannot create q0 skeleton point: {name}")
        point_count += 1
    for joint in chain["joints"]:
        parent = link_points[joint["parent"]]
        child = link_points[joint["child"]]
        length = math.dist(parent, child)
        if length > 1.0e-12:
            if sketch_manager.CreateLine(*parent, *child) is None:
                raise Phase0Error(f"cannot create q0 chain line: {joint['name']}")
            line_count += 1
    chain_feature = _sketch_feature(active)
    sketch_manager.Insert3DSketch(True)
    if chain_feature is not None:
        session.cast(chain_feature, "IFeature").Name = "SK3D_ACCEPTED_Q0_LINK_CHAIN"

    sketch_manager.Insert3DSketch(True)
    active_axes = get_com_member(sketch_manager, "ActiveSketch")
    axis_count = 0
    axis_length_m = 0.04
    for joint in chain["joints"]:
        frame = joint_frames[joint["name"]]
        origin = [float(frame[row][3]) for row in range(3)]
        local_axis = [float(value) for value in joint["axis_source"].split()]
        world_axis = [
            sum(float(frame[row][col]) * local_axis[col] for col in range(3))
            for row in range(3)
        ]
        norm = math.sqrt(sum(value * value for value in world_axis))
        if norm <= 1.0e-12:
            # The accepted fixed joint has a zero axis; retain its origin point.
            if sketch_manager.CreatePoint(*origin) is None:
                raise Phase0Error(
                    f"cannot create fixed-joint origin: {joint['name']}"
                )
            continue
        end = [
            origin[index] + axis_length_m * world_axis[index] / norm
            for index in range(3)
        ]
        if sketch_manager.CreateLine(*origin, *end) is None:
            raise Phase0Error(f"cannot create joint axis: {joint['name']}")
        axis_count += 1
    axes_feature = _sketch_feature(active_axes)
    sketch_manager.Insert3DSketch(True)
    if axes_feature is not None:
        session.cast(axes_feature, "IFeature").Name = "SK3D_ACCEPTED_Q0_JOINT_AXES"

    session.set_text_properties(
        model,
        {
            "OBJECT_ID": "B50_B601_MASTER_SKELETON",
            "REPRESENTATION_LAYER": "L1_NATIVE_DATUM_SKELETON",
            "KINEMATICS_AUTHORITY": "ACCEPTED_URDF_READ_ONLY_MIRROR",
            "ACCEPTED_URDF_SHA256": EXPECTED_URDF_SHA256,
            "ACCEPTED_TOPOLOGY": "10_LINKS_9_JOINTS_6R_FIXED_2P",
            "ACCEPTED_MASS_REFERENCE_KG": EXPECTED_MASS_SOURCE,
            "MASS_AUTHORITY": "EXCLUDED_REFERENCE_ONLY",
            "FRAME_ID": "A0_ACCEPTED_URDF_BASE_LINK",
            "SPACECRAFT_CAD_MAPPING": (
                "p_S_mm=[198,0,0]+[[0,0,1],[0,1,0],[-1,0,0]]*p_A0_mm"
            ),
            "DISPLAY_TRACK_X_MM": "198.0_CANDIDATE_CAD_ONLY",
            "DYNAMICS_TRACK_X_MM": "185.25_EXISTING_CONTRACT",
            "TRACK_DIFFERENCE_MM": "12.75_MUST_NOT_ENTER_JOINT_ORIGINS",
            "RUN_ID": run_root.name,
            "CLAIM_LIMIT": (
                "datum mirror only; no manufacturing, mass, mechanism, "
                "strength, clearance or flight release"
            ),
        },
    )
    if not model.ForceRebuild3(False):
        raise Phase0Error("master skeleton rebuild failed")
    save = session.save_as(model, target)
    session.close_all_documents()
    cold_model, cold_open = session.open_document(target, "part")
    cold_property = session.read_text_property(
        cold_model, "ACCEPTED_URDF_SHA256"
    )
    session.close_all_documents()
    if cold_property != EXPECTED_URDF_SHA256:
        raise Phase0Error("master skeleton URDF property did not persist")
    return {
        "artifact": artifact_record(target, run_root),
        "point_count": point_count,
        "chain_segment_count": line_count,
        "nonzero_joint_axis_count": axis_count,
        "joint2_axis_source": chain["joints"][1]["axis_source"],
        "save": save,
        "cold_open": cold_open,
        "verdict": "B5_0_MASTER_SKELETON_PASS",
    }


def _math_transform_data(matrix: list[list[float]]) -> list[float]:
    # accepted_chain uses the conventional column-vector contract p_A0=R*p_link+t.
    # SolidWorks MathTransform applies row vectors, so ArrayData stores R^T.
    return [
        float(matrix[0][0]),
        float(matrix[1][0]),
        float(matrix[2][0]),
        float(matrix[0][1]),
        float(matrix[1][1]),
        float(matrix[2][1]),
        float(matrix[0][2]),
        float(matrix[1][2]),
        float(matrix[2][2]),
        float(matrix[0][3]),
        float(matrix[1][3]),
        float(matrix[2][3]),
        1.0,
        0.0,
        0.0,
        0.0,
    ]


def _close_enough(actual: list[float], expected: list[float], tol: float) -> bool:
    return len(actual) == len(expected) and all(
        abs(float(a) - float(b)) <= tol for a, b in zip(actual, expected)
    )


def _component_transform_array(component: Any) -> list[float]:
    transform = get_com_member(component, "Transform2")
    return [
        float(value)
        for value in _as_list(get_com_member(transform, "ArrayData"))
    ]


def _add_component(
    session: SolidWorksSession,
    assembly_model: Any,
    part_path: Path,
    matrix: list[list[float]],
    label: str,
) -> dict[str, Any]:
    part_model, open_record = session.open_document(part_path, "part")
    part_title = str(get_com_member(part_model, "GetTitle"))
    assembly_title = str(get_com_member(assembly_model, "GetTitle"))
    session.activate_document(assembly_title)
    assembly = session.cast(assembly_model, "IAssemblyDoc")
    component = assembly.AddComponent5(
        str(part_path), 0, "", False, "", 0.0, 0.0, 0.0
    )
    if component is None:
        raise Phase0Error(f"AddComponent5 failed: {part_path}")
    component = session.cast(component, "IComponent2")
    assembly_model.ClearSelection2(True)
    if not component.Select4(False, None, False):
        raise Phase0Error(f"cannot select component for floating: {label}")
    initially_fixed = bool(get_com_member(component, "IsFixed"))
    if initially_fixed:
        assembly.UnfixComponent()
    floating_before_transform = not bool(get_com_member(component, "IsFixed"))
    assembly_model.ClearSelection2(True)
    if not floating_before_transform:
        raise Phase0Error(f"component remained fixed before transform: {label}")
    data = _math_transform_data(matrix)
    math_utility = session.cast(
        get_com_member(session.sw, "GetMathUtility"), "IMathUtility"
    )
    typed_data = VARIANT(
        session.pythoncom.VT_ARRAY | session.pythoncom.VT_R8, data
    )
    transform = math_utility.CreateTransform(typed_data)
    if transform is None:
        raise Phase0Error(f"CreateTransform failed: {label}")
    transform_input_readback = [
        float(value)
        for value in _as_list(get_com_member(transform, "ArrayData"))
    ]
    if not _close_enough(transform_input_readback, data, 1.0e-12):
        raise Phase0Error(
            f"CreateTransform SAFEARRAY readback mismatch for {label}: "
            f"{transform_input_readback}"
        )
    transform_attempts: list[dict[str, Any]] = []
    try:
        set_transform = getattr(component, "SetTransformAndSolve3")
    except AttributeError:
        set_transform = None
    if set_transform is not None:
        api_ok = bool(set_transform(transform, True))
        rebuild_ok = bool(assembly_model.EditRebuild3())
        readback = _component_transform_array(component)
        transform_attempts.append(
            {
                "api": "SetTransformAndSolve3",
                "api_ok": api_ok,
                "edit_rebuild_ok": rebuild_ok,
                "readback": readback,
                "matches_expected": _close_enough(readback, data, 1.0e-10),
            }
        )
    else:
        readback = _component_transform_array(component)
    if set_transform is None or not _close_enough(readback, data, 1.0e-10):
        property_error = None
        try:
            component.Transform2 = transform
        except Exception as exc:
            property_error = repr(exc)
        rebuild_ok = bool(assembly_model.EditRebuild3())
        readback = _component_transform_array(component)
        transform_attempts.append(
            {
                "api": "Transform2_PROPERTY",
                "api_ok": property_error is None,
                "exception": property_error,
                "edit_rebuild_ok": rebuild_ok,
                "readback": readback,
                "matches_expected": _close_enough(readback, data, 1.0e-10),
            }
        )
    if not _close_enough(readback, data, 1.0e-10):
        api_ok = bool(component.SetTransformAndSolve2(transform))
        rebuild_ok = bool(assembly_model.EditRebuild3())
        readback = _component_transform_array(component)
        transform_attempts.append(
            {
                "api": "SetTransformAndSolve2_COMPATIBILITY_FALLBACK",
                "api_ok": api_ok,
                "edit_rebuild_ok": rebuild_ok,
                "readback": readback,
                "matches_expected": _close_enough(readback, data, 1.0e-10),
            }
        )
    if not _close_enough(readback, data, 1.0e-10):
        raise Phase0Error(
            f"component transform readback mismatch for {label}: "
            f"{transform_attempts}"
        )
    transform_api = next(
        attempt["api"]
        for attempt in transform_attempts
        if attempt["matches_expected"]
    )
    try:
        assembly.UpdateBox()
    except Exception:
        pass
    assembly_model.ClearSelection2(True)
    if not component.Select4(False, None, False):
        raise Phase0Error(f"cannot select component for fixing: {label}")
    assembly.FixComponent()
    fixed_readback = bool(get_com_member(component, "IsFixed"))
    post_fix_readback = _component_transform_array(component)
    assembly_model.ClearSelection2(True)
    if not fixed_readback:
        raise Phase0Error(f"component did not remain fixed after transform: {label}")
    if not _close_enough(post_fix_readback, data, 1.0e-10):
        raise Phase0Error(
            f"component transform changed when fixed for {label}: "
            f"{post_fix_readback}"
        )
    component_path = Path(str(get_com_member(component, "GetPathName"))).resolve()
    if component_path != part_path.resolve():
        raise Phase0Error(
            f"component reference mismatch: {component_path} != {part_path}"
        )
    session.sw.CloseDoc(part_title)
    return {
        "label": label,
        "part_path": component_path.relative_to(session.run_root).as_posix(),
        "source_open": open_record,
        "math_transform_array": data,
        "math_transform_input_readback": transform_input_readback,
        "transform_readback": readback,
        "initially_fixed": initially_fixed,
        "floating_before_transform": floating_before_transform,
        "transform_api": transform_api,
        "transform_attempts": transform_attempts,
        "post_fix_transform_readback": post_fix_readback,
        "fixed_q0_reference": fixed_readback,
    }


def _build_assembly(
    session: SolidWorksSession,
    run_root: Path,
    chain: dict[str, Any],
    vendor: dict[str, Any],
) -> dict[str, Any]:
    skeleton = run_root / "00_skeleton" / "B50_B601_MASTER_SKELETON.SLDPRT"
    required = [skeleton] + [_part_path(run_root, group) for group in GROUP_ORDER]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise Phase0Error(f"native assembly inputs missing: {missing}")
    target = run_root / "20_assembly" / "B50_B601_ENGINEERING_ARM_Q0.SLDASM"
    step_target = run_root / "30_exports" / "B50_B601_ENGINEERING_ARM_Q0.step"
    drawing_target = (
        run_root / "40_drawings" / "B50_B601_ENGINEERING_ARM_Q0.SLDDRW"
    )
    for path in (target, step_target, drawing_target):
        if path.exists():
            raise Phase0Error(f"assembly-stage target already exists: {path}")
    model = session.new_document("assembly")
    identity = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
    components = [
        _add_component(session, model, skeleton, identity, "MASTER_SKELETON")
    ]
    for group in GROUP_ORDER:
        item = _vendor_item(vendor, group)
        components.append(
            _add_component(
                session,
                model,
                _part_path(run_root, group),
                chain["q0_frames_A0"][GROUP_LINK[group]],
                f"{group}_{GROUP_LINK[group]}_{item['status']}",
            )
        )
    session.set_text_properties(
        model,
        {
            "OBJECT_ID": "B50_B601_ENGINEERING_ARM_Q0",
            "REPRESENTATION_LAYER": "L1_NATIVE_VENDOR_REFERENCE_ASSEMBLY",
            "CONFIGURATION_STATE": "Q0_ACCEPTED_URDF",
            "KINEMATICS_AUTHORITY": "ACCEPTED_URDF_TRANSFORMS_ONLY",
            "MECHANISM_DOF_AUTHORITY": "NONE_FIXED_Q0_REFERENCE",
            "MASS_AUTHORITY": "EXCLUDED_ACCEPTED_URDF_ONLY",
            "ACCEPTED_URDF_SHA256": EXPECTED_URDF_SHA256,
            "ACCEPTED_TOTAL_MASS_REFERENCE_KG": EXPECTED_MASS_SOURCE,
            "VENDOR_DIRECT_GROUPS": "G01;G02;G03;G04;G06;G07",
            "VENDOR_HOLD_GROUPS": "G05;G08",
            "G05_STATUS": "CHAIN_DERIVED_HOLD",
            "G08_STATUS": "CHAIN_DERIVED_HOLD",
            "B106_STATUS": "NOT_FOUND_IN_PHASE0_BOUNDED_SEARCH",
            "RUN_ID": run_root.name,
            "CLAIM_LIMIT": (
                "fixed q0 geometry reference; no retained 6R mates, continuous "
                "clearance, material, mass, strength, tolerance or flight release"
            ),
        },
    )
    if not model.ForceRebuild3(True):
        raise Phase0Error("q0 assembly full rebuild failed")
    assembly_save = session.save_as(model, target, require_zero_warnings=False)
    session.close_all_documents()

    assembly_model, assembly_open = session.open_document(target, "assembly")
    if not assembly_model.ForceRebuild3(True):
        raise Phase0Error("q0 assembly rebuild failed before STEP export")
    step_save = session.save_as(
        assembly_model, step_target, require_zero_warnings=False
    )
    session.close_all_documents()

    assembly_model, drawing_source_open = session.open_document(
        target, "assembly"
    )
    drawing_model = session.new_document("drawing")
    drawing_doc = session.cast(drawing_model, "IDrawingDoc")
    placed = None
    placed_name = None
    for view_name in ("*等轴测", "*Isometric", "*前视", "*Front"):
        try:
            placed = drawing_doc.CreateDrawViewFromModelView3(
                str(target), view_name, 0.18, 0.14, 0.0
            )
        except Exception:
            placed = None
        if placed is not None:
            placed_name = view_name
            break
    if placed is None:
        raise Phase0Error("cannot create q0 assembly drawing view")
    session.set_text_properties(
        drawing_model,
        {
            "OBJECT_ID": "B50_B601_ENGINEERING_ARM_Q0_DRAWING",
            "DRAWING_STATUS": "ENGINEERING_REFERENCE_NOT_FOR_MANUFACTURE",
            "MASS_AUTHORITY": "EXCLUDED",
            "ACCEPTED_URDF_SHA256": EXPECTED_URDF_SHA256,
            "RUN_ID": run_root.name,
            "CLAIM_LIMIT": "reference view only; dimensions and tolerances not released",
        },
    )
    if not drawing_model.ForceRebuild3(True):
        raise Phase0Error("q0 drawing rebuild failed")
    drawing_save = session.save_as(
        drawing_model, drawing_target, require_zero_warnings=False
    )
    session.close_all_documents()
    return {
        "components": components,
        "component_count": len(components),
        "fixed_geometry_component_count": len(components),
        "retained_mechanism_dof_claimed": False,
        "assembly": artifact_record(target, run_root),
        "assembly_save": assembly_save,
        "assembly_open_for_export": assembly_open,
        "step": artifact_record(step_target, run_root),
        "step_save": step_save,
        "drawing_source_open": drawing_source_open,
        "drawing_view": placed_name,
        "drawing": artifact_record(drawing_target, run_root),
        "drawing_save": drawing_save,
        "verdict": "B5_0_NATIVE_Q0_ASSEMBLY_BUILD_PASS",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build one fail-closed B5.0 native SolidWorks stage."
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--stage", choices=("skeleton", "link", "assembly"), required=True
    )
    parser.add_argument("--group", choices=sorted(GROUP_LINK))
    parser.add_argument(
        "--attempt-id",
        help="append-only evidence suffix for an assembly recovery attempt",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if (args.stage == "link") != bool(args.group):
        raise SystemExit("--group is required only for --stage link")
    if args.attempt_id and args.stage != "assembly":
        raise SystemExit("--attempt-id is only valid for --stage assembly")
    if args.attempt_id and not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}", args.attempt_id
    ):
        raise SystemExit("--attempt-id must be a safe 1-32 character label")
    run_root = _run_root(args.run_id)
    run_root.mkdir(parents=True, exist_ok=True)
    name = (
        "master_skeleton_build"
        if args.stage == "skeleton"
        else (
            f"native_{args.group}_build"
            if args.stage == "link"
            else "q0_assembly_build"
        )
    )
    if args.attempt_id:
        name = f"{name}_{args.attempt_id}"
    report_path = _receipt_path(run_root, name)
    report: dict[str, Any] = {
        "schema": "SER_B50_NATIVE_BUILD_V1",
        "generated_utc": utc_now(),
        "run_id": args.run_id,
        "stage": args.stage,
        "group": args.group,
        "attempt_id": args.attempt_id,
        "candidate_root": str(CANDIDATE_ROOT),
        "run_root": str(run_root),
        "status": "B5_0_NATIVE_BUILD_HOLD",
        "mass_authority": "EXCLUDED_ACCEPTED_URDF_ONLY",
    }
    session: SolidWorksSession | None = None
    try:
        if report_path.exists():
            raise Phase0Error(f"evidence already exists: {report_path}")
        chain, vendor = _source_contract()
        import_visible = args.stage == "link"
        report["solidworks_visible"] = import_visible
        with SolidWorksSession(run_root, visible=import_visible) as session:
            report["session_start"] = session.info()
            if args.stage == "skeleton":
                report["result"] = _create_master_skeleton(
                    session, run_root, chain
                )
            elif args.stage == "link":
                report["result"] = _import_group(
                    session, run_root, args.group, chain, vendor
                )
            else:
                report["result"] = _build_assembly(
                    session, run_root, chain, vendor
                )
        report["session_end"] = session.info()
        report["status"] = "B5_0_NATIVE_BUILD_PASS"
    except Exception as exc:
        report["status"] = "B5_0_NATIVE_BUILD_HOLD"
        report["exception"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        if session is not None:
            report["session_end"] = session.info()
    finally:
        report["completed_utc"] = utc_now()
        try:
            write_json_once(report_path, report, run_root)
        except Exception as evidence_exc:
            report["evidence_write_error"] = repr(evidence_exc)
            report["status"] = "B5_0_NATIVE_BUILD_HOLD"
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "B5_0_NATIVE_BUILD_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
