#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SW2024 attach-only three-body/two-hinge native mate microfixture.

Purpose
-------
This diagnostic creates three native parts and one native assembly solely
under ``99_tools/probe_logs``.  Two serial, parallel-X hinges are built.  Each
hinge has exactly one concentric mate, one coincident mate and one native
advanced limit-angle mate.  The assembly is saved write-once, closed, then
cold-reopened read-only and verified from the live B-rep/mate definitions.

Safety contract
---------------
* ``audit`` is filesystem-only and never touches SOLIDWORKS.
* ``execute`` only calls the pinned Loop1B ``GetActiveObject`` attachment;
  it cannot start, terminate, hide or take ownership of an application.
* the attached SW2024 SP5 PID must be supplied explicitly and the session must
  start document-empty.
* every output path is containment-checked below ``PROBE_ROOT`` and every
  file/directory is write-once.  A failed run remains an immutable diagnostic
  run; retry with a new run id.
* no V5 production CAD, authority, configuration, release or receipt path is
  read-write opened by this script.

This is a feasibility probe, not solar-array release evidence and not a
flight/launch qualification artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


sys.dont_write_bytecode = True

ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
RUN_ROOT = ROOT / "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
TOOLS = RUN_ROOT / "99_tools"
PROBE_ROOT = TOOLS / "probe_logs"
LOOP1B_HELPER = TOOLS / "F3R2_V5_NATIVE_LOOP1B_WING_ROOTS_ATTACH_ONLY.py"
LOOP1E_REFERENCE = TOOLS / "F3R2_V5_NATIVE_LOOP1E_TOP_ASSEMBLY_ATTACH_ONLY.py"
PART_TEMPLATE = Path(r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_part.prtdot")
ASSEMBLY_TEMPLATE = Path(r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_assembly.asmdot")

LOOP1B_HELPER_SHA256 = "32BC06FC6A1EFCD6426FE4608D03EABCBD2902CBA228E95B2AD7A91B4E0F283F"
PART_TEMPLATE_SHA256 = "5DA21678EFE07EF465770630BEB4FFE540F23D47FCA07715F74D2AFDBEA87271"
ASSEMBLY_TEMPLATE_SHA256 = "37DED9268BABC616A97BF9DA29BDCC2FFD60E8E4353670748F74A18A3BB450CC"

sys.path.insert(0, str(TOOLS))
import F3R2_V5_NATIVE_LOOP1B_WING_ROOTS_ATTACH_ONLY as L1B  # noqa: E402


SW_MATE_COINCIDENT = 0
SW_MATE_CONCENTRIC = 1
SW_MATE_ANGLE = 6
SW_ALIGN_ALIGNED = 0
SW_ALIGN_CLOSEST = 2
SW_ADD_MATE_NO_ERROR = 1
SW_DOC_PART = 1
SW_DOC_ASSEMBLY = 2

HINGE_LIMITS = {
    "lower_rad": 0.0,
    "upper_rad": math.pi / 2.0,
    "creation_angle_rad": 0.0,
}
RIGHT_PLANE_NAMES = ("右视基准面", "Right Plane")
TOP_PLANE_NAMES = {"上视基准面", "Top Plane"}
RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


class ProbeError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Optional[Mapping[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.detail = dict(detail or {})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def norm(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def file_fact(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise ProbeError("FILE_FACT_MISSING", "expected output file is absent", {"path": norm(path)})
    return {"path": norm(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def assert_under_probe_root(path: Path, allow_root: bool = False) -> Path:
    root = PROBE_ROOT.resolve()
    candidate = path.resolve()
    if candidate != root and root not in candidate.parents:
        raise ProbeError(
            "WRITE_SCOPE_ESCAPE",
            "diagnostic target escapes the sole permitted probe root",
            {"probe_root": norm(PROBE_ROOT), "candidate": norm(path)},
        )
    if candidate == root and not allow_root:
        raise ProbeError("WRITE_SCOPE_TOO_BROAD", "the probe root itself cannot be a file target", {"candidate": norm(path)})
    return candidate


def run_directory(run_id: str) -> Path:
    if not RUN_ID_PATTERN.fullmatch(run_id) or run_id in {".", ".."}:
        raise ProbeError("RUN_ID_INVALID", "run id must be a single safe path token", {"run_id": run_id})
    return assert_under_probe_root(PROBE_ROOT / f"V5_SOLAR_HINGE_MICROFIXTURE_{run_id}")


def write_text_once(path: Path, text: str) -> None:
    assert_under_probe_root(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def write_json_once(path: Path, payload: Mapping[str, Any]) -> None:
    write_text_once(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def static_audit(run_id: Optional[str] = None) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []

    def check(name: str, passed: bool, **detail: Any) -> None:
        rows.append({"check": name, "pass": bool(passed), **detail})

    check(
        "loop1b_helper_hash_pinned",
        LOOP1B_HELPER.is_file() and sha256(LOOP1B_HELPER) == LOOP1B_HELPER_SHA256,
        path=norm(LOOP1B_HELPER),
        expected_sha256=LOOP1B_HELPER_SHA256,
        actual_sha256=sha256(LOOP1B_HELPER) if LOOP1B_HELPER.is_file() else None,
    )
    check(
        "part_template_hash_pinned",
        PART_TEMPLATE.is_file() and sha256(PART_TEMPLATE) == PART_TEMPLATE_SHA256,
        path=norm(PART_TEMPLATE),
        expected_sha256=PART_TEMPLATE_SHA256,
        actual_sha256=sha256(PART_TEMPLATE) if PART_TEMPLATE.is_file() else None,
    )
    check(
        "assembly_template_hash_pinned",
        ASSEMBLY_TEMPLATE.is_file() and sha256(ASSEMBLY_TEMPLATE) == ASSEMBLY_TEMPLATE_SHA256,
        path=norm(ASSEMBLY_TEMPLATE),
        expected_sha256=ASSEMBLY_TEMPLATE_SHA256,
        actual_sha256=sha256(ASSEMBLY_TEMPLATE) if ASSEMBLY_TEMPLATE.is_file() else None,
    )
    check(
        "probe_root_is_diagnostic",
        PROBE_ROOT.is_dir() and PROBE_ROOT.resolve() == (RUN_ROOT / "99_tools/probe_logs").resolve(),
        probe_root=norm(PROBE_ROOT),
    )
    check(
        "loop1e_reference_present",
        LOOP1E_REFERENCE.is_file(),
        path=norm(LOOP1E_REFERENCE),
        reference_sha256=sha256(LOOP1E_REFERENCE) if LOOP1E_REFERENCE.is_file() else None,
        gate_note="reference only; advanced-angle implementation is copied into this isolated probe",
    )
    target = None
    if run_id is not None:
        target = run_directory(run_id)
        check("run_directory_write_once", not target.exists(), target=norm(target), exists=target.exists())
        planned = (
            target / "parts/MF_BODY_A_FIXED.SLDPRT",
            target / "parts/MF_BODY_B_MIDDLE.SLDPRT",
            target / "parts/MF_BODY_C_FOLLOWER.SLDPRT",
            target / "assembly/MF_THREE_BODY_TWO_HINGE.SLDASM",
            target / "MANIFEST_SHA256.txt",
            target / "RESULT_PASS.json",
            target / "RESULT_FAIL.json",
        )
        for path in planned:
            assert_under_probe_root(path)
        check("planned_targets_contained", True, targets=[norm(path) for path in planned])
    return {
        "schema": "F3R2_V5_DIAG_SOLAR_HINGE_MICROFIXTURE_STATIC_AUDIT_V1",
        "timestamp_utc": utc_now(),
        "script": file_fact(Path(__file__)),
        "run_id": run_id,
        "target": norm(target) if target is not None else None,
        "checks": rows,
        "execution_authorized": all(row["pass"] for row in rows),
        "write_scope": norm(PROBE_ROOT),
        "solidworks_touched": False,
        "verdict": "V5_DIAG_MICROFIXTURE_STATIC_PASS" if all(row["pass"] for row in rows) else "V5_DIAG_MICROFIXTURE_STATIC_HOLD",
    }


def select_sketch_plane(model: Any, x_start_mm: float, name: str) -> str:
    if abs(x_start_mm) <= 1.0e-12:
        return L1B.select_base_plane(model, RIGHT_PLANE_NAMES)
    L1B.create_offset_plane(model, RIGHT_PLANE_NAMES, x_start_mm, name)
    model.ClearSelection2(True)
    if not bool(model.Extension.SelectByID2(name, "PLANE", 0.0, 0.0, 0.0, False, 0, None, 0)):
        raise ProbeError("OFFSET_PLANE_RESELECT_FAIL", "cannot select the diagnostic extrusion plane", {"plane": name})
    return name


def make_annulus_part(
    sw: Any,
    types: Any,
    pythoncom: Any,
    target: Path,
    role: str,
    x_start_mm: float,
    center_y_mm: float,
    run_id: str,
) -> Dict[str, Any]:
    assert_under_probe_root(target)
    if target.exists():
        raise ProbeError("WRITE_ONCE_PART_EXISTS", "diagnostic native part already exists", {"target": norm(target)})
    model = None
    try:
        model = L1B.new_part(sw, types, pythoncom)
        plane = select_sketch_plane(model, x_start_mm, f"MF_{role}_X_START")
        sketch = model.SketchManager
        sketch.InsertSketch(True)
        center_y_m = center_y_mm / 1000.0
        outer = sketch.CreateCircleByRadius(0.0, center_y_m, 0.0, 0.010)
        bore = sketch.CreateCircleByRadius(0.0, center_y_m, 0.0, 0.0042)
        if outer is None or bore is None:
            raise ProbeError("ANNULUS_SKETCH_FAIL", "annulus circle creation returned null", {"role": role})
        sketch.InsertSketch(True)
        extrusion = model.FeatureManager.FeatureExtrusion2(
            True, False, False, 0, 0, 0.006, 0.0,
            False, False, False, False, 0.0, 0.0,
            False, False, False, False, True, True, True, 0, 0.0, False,
        )
        if extrusion is None:
            raise ProbeError("ANNULUS_EXTRUSION_FAIL", "annulus native extrusion returned null", {"role": role})
        extrusion.Name = f"MF_{role}_ANNULUS_EXTRUSION"
        L1B.set_properties(
            model,
            {
                "PartNumber": f"V5-DIAG-MF-{role}",
                "Description": "diagnostic serial-hinge annulus body",
                "ARTIFACT_CLASS": "DIAGNOSTIC_MICROFIXTURE_NON_RELEASE",
                "PRODUCTION_USE": "PROHIBITED",
                "FLIGHT_QUALIFICATION": "NOT_APPLICABLE",
                "HINGE_AXIS": f"X@Y={center_y_mm:.3f}mm,Z=0",
                "BORE_DIAMETER_MM": "8.4",
                "RUN_ID": run_id,
            },
        )
        if not bool(model.ForceRebuild3(True)):
            raise ProbeError("PART_REBUILD_FAIL", "annulus part force rebuild failed", {"role": role})
        saved = L1B.save_as(model, target)
    finally:
        L1B.close_doc(sw, model)
    expected = [x_start_mm, center_y_mm - 10.0, -10.0, x_start_mm + 6.0, center_y_mm + 10.0, 10.0]
    cold = None
    try:
        cold, opened = L1B.open_doc(sw, target, SW_DOC_PART, True, types, pythoncom)
        facts = L1B.body_facts(cold, types, pythoncom)
        if facts["solid_body_count"] != 1 or not L1B.bbox_close(facts["bounding_box_mm"], expected):
            raise ProbeError("ANNULUS_COLD_BREP_FAIL", "cold annulus B-rep differs from the microfixture contract", {"role": role, "facts": facts, "expected_bbox_mm": expected})
        links = {
            "external": L1B.external_reference_count(cold),
            "auxiliary": L1B.auxiliary_reference_count(cold),
        }
        if links != {"external": 0, "auxiliary": 0}:
            raise ProbeError("ANNULUS_COLD_LINK_FAIL", "diagnostic annulus contains an external reference", {"role": role, "links": links})
    finally:
        L1B.close_doc(sw, cold)
    return {
        "role": role,
        "target": saved,
        "sketch_plane": plane,
        "axis": {"direction": [1.0, 0.0, 0.0], "point_mm": [0.0, center_y_mm, 0.0]},
        "expected_bbox_mm": expected,
        "cold_open": opened,
        "cold_facts": facts,
        "cold_links": links,
        "verdict": "V5_DIAG_ANNULUS_NATIVE_COLD_PASS",
    }


def make_middle_link_part(
    sw: Any,
    types: Any,
    pythoncom: Any,
    target: Path,
    run_id: str,
) -> Dict[str, Any]:
    assert_under_probe_root(target)
    if target.exists():
        raise ProbeError("WRITE_ONCE_PART_EXISTS", "diagnostic native part already exists", {"target": norm(target)})
    model = None
    try:
        model = L1B.new_part(sw, types, pythoncom)
        plane = select_sketch_plane(model, 0.0, "MF_BODY_B_X_START")
        sketch = model.SketchManager
        sketch.InsertSketch(True)
        # SketchManager coordinates are sketch-space coordinates even though
        # the active plane is the global Right Plane.  The earlier diagnostic
        # incorrectly supplied world-space (X,Y,Z) triples with a non-zero
        # third coordinate; SW projected consecutive vertices together and
        # CreateLine returned null.  On this plane sketch X maps to global Z
        # (up to sign) and sketch Y maps to global Y, so the required
        # Y=-10..50 mm / Z=-10..10 mm profile is authored below with z=0.
        points = (
            (-0.010, -0.010, 0.0),
            (-0.010, 0.050, 0.0),
            (0.010, 0.050, 0.0),
            (0.010, -0.010, 0.0),
            (-0.010, -0.010, 0.0),
        )
        for segment_index, (first, second) in enumerate(zip(points[:-1], points[1:]), start=1):
            if sketch.CreateLine(*first, *second) is None:
                raise ProbeError(
                    "MIDDLE_PROFILE_FAIL",
                    "middle-link outer profile line creation returned null",
                    {"segment_index": segment_index, "first_sketch_m": first, "second_sketch_m": second},
                )
        bore_1 = sketch.CreateCircleByRadius(0.0, 0.0, 0.0, 0.0042)
        bore_2 = sketch.CreateCircleByRadius(0.0, 0.040, 0.0, 0.0042)
        if bore_1 is None or bore_2 is None:
            raise ProbeError("MIDDLE_BORE_SKETCH_FAIL", "middle-link bore circle creation returned null")
        sketch.InsertSketch(True)
        extrusion = model.FeatureManager.FeatureExtrusion2(
            True, False, False, 0, 0, 0.006, 0.0,
            False, False, False, False, 0.0, 0.0,
            False, False, False, False, True, True, True, 0, 0.0, False,
        )
        if extrusion is None:
            raise ProbeError("MIDDLE_EXTRUSION_FAIL", "middle-link native extrusion returned null")
        extrusion.Name = "MF_BODY_B_TWO_BORE_LINK_EXTRUSION"
        L1B.set_properties(
            model,
            {
                "PartNumber": "V5-DIAG-MF-BODY-B",
                "Description": "diagnostic two-bore middle link",
                "ARTIFACT_CLASS": "DIAGNOSTIC_MICROFIXTURE_NON_RELEASE",
                "PRODUCTION_USE": "PROHIBITED",
                "FLIGHT_QUALIFICATION": "NOT_APPLICABLE",
                "HINGE_AXES": "X@Y=0mm,Z=0;X@Y=40mm,Z=0",
                "BORE_DIAMETER_MM": "8.4",
                "RUN_ID": run_id,
            },
        )
        if not bool(model.ForceRebuild3(True)):
            raise ProbeError("PART_REBUILD_FAIL", "middle-link force rebuild failed")
        saved = L1B.save_as(model, target)
    finally:
        L1B.close_doc(sw, model)
    expected = [0.0, -10.0, -10.0, 6.0, 50.0, 10.0]
    cold = None
    try:
        cold, opened = L1B.open_doc(sw, target, SW_DOC_PART, True, types, pythoncom)
        facts = L1B.body_facts(cold, types, pythoncom)
        if facts["solid_body_count"] != 1 or not L1B.bbox_close(facts["bounding_box_mm"], expected):
            raise ProbeError("MIDDLE_COLD_BREP_FAIL", "cold middle-link B-rep differs from the microfixture contract", {"facts": facts, "expected_bbox_mm": expected})
        links = {
            "external": L1B.external_reference_count(cold),
            "auxiliary": L1B.auxiliary_reference_count(cold),
        }
        if links != {"external": 0, "auxiliary": 0}:
            raise ProbeError("MIDDLE_COLD_LINK_FAIL", "diagnostic middle link contains an external reference", {"links": links})
    finally:
        L1B.close_doc(sw, cold)
    return {
        "role": "BODY_B_MIDDLE",
        "target": saved,
        "sketch_plane": plane,
        "axes": [
            {"direction": [1.0, 0.0, 0.0], "point_mm": [0.0, 0.0, 0.0]},
            {"direction": [1.0, 0.0, 0.0], "point_mm": [0.0, 40.0, 0.0]},
        ],
        "expected_bbox_mm": expected,
        "cold_open": opened,
        "cold_facts": facts,
        "cold_links": links,
        "verdict": "V5_DIAG_MIDDLE_LINK_NATIVE_COLD_PASS",
    }


def mate_feature_map(model: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    rows: Dict[str, Any] = {}
    raw = L1B.value(model, "FirstFeature")
    for _ in range(10000):
        if raw is None:
            return rows
        feature = L1B.wrap(raw, "IFeature", types, pythoncom)
        if str(L1B.value(feature, "GetTypeName2")) == "MateGroup":
            sub = L1B.value(feature, "GetFirstSubFeature")
            for _sub_index in range(10000):
                if sub is None:
                    break
                typed = L1B.wrap(sub, "IFeature", types, pythoncom)
                name = str(L1B.value(typed, "Name"))
                if name in rows:
                    raise ProbeError("MATE_NAME_COLLISION", "duplicate mate feature name", {"name": name})
                rows[name] = typed
                sub = L1B.value(typed, "GetNextSubFeature")
            else:
                raise ProbeError("MATE_SUBFEATURE_TRAVERSAL_LIMIT", "mate subfeature traversal exceeded guard")
        raw = L1B.value(feature, "GetNextFeature")
    raise ProbeError("MATE_FEATURE_TRAVERSAL_LIMIT", "mate feature traversal exceeded guard")


def rename_mate(model: Any, old_name: str, new_name: str, types: Any, pythoncom: Any) -> Any:
    before = mate_feature_map(model, types, pythoncom)
    if old_name not in before or new_name in before:
        raise ProbeError("MATE_RENAME_PRECONDITION_FAIL", "mate rename precondition is not unique", {"old_name": old_name, "new_name": new_name, "available": sorted(before)})
    before[old_name].Name = new_name
    after = mate_feature_map(model, types, pythoncom)
    if old_name in after or new_name not in after:
        raise ProbeError("MATE_RENAME_FAIL", "mate feature did not retain its deterministic diagnostic name", {"old_name": old_name, "new_name": new_name, "available": sorted(after)})
    return after[new_name]


def add_named_entity_mate(
    model: Any,
    assembly: Any,
    first_entity: Any,
    second_entity: Any,
    mate_type: int,
    expected_components: Sequence[Any],
    name: str,
    types: Any,
    pythoncom: Any,
) -> Dict[str, Any]:
    created = L1B.add_entity_mate(
        model,
        assembly,
        first_entity,
        second_entity,
        mate_type,
        SW_ALIGN_CLOSEST,
        expected_components,
        types,
        pythoncom,
    )
    rename_mate(model, created["feature_name"], name, types, pythoncom)
    return {**created, "feature_name": name}


def component_ref_plane(component: Any, types: Any, pythoncom: Any) -> Tuple[Any, Dict[str, Any]]:
    planes: List[Any] = []
    raw = L1B.value(component, "FirstFeature")
    for _ in range(10000):
        if raw is None:
            break
        feature = L1B.wrap(raw, "IFeature", types, pythoncom)
        if str(L1B.value(feature, "GetTypeName2")) == "RefPlane":
            planes.append(feature)
        raw = L1B.value(feature, "GetNextFeature")
    else:
        raise ProbeError("COMPONENT_FEATURE_TRAVERSAL_LIMIT", "component feature traversal exceeded guard")
    named = [feature for feature in planes if str(L1B.value(feature, "Name")) in TOP_PLANE_NAMES]
    candidates = named or (planes[1:2] if len(planes) >= 2 else [])
    if len(candidates) != 1:
        raise ProbeError(
            "ANGLE_PLANE_CARDINALITY_FAIL",
            "cannot resolve one axis-containing Top reference plane",
            {"component": str(L1B.value(component, "Name2")), "planes": [str(L1B.value(feature, "Name")) for feature in planes]},
        )
    return candidates[0], {
        "component": str(L1B.value(component, "Name2")),
        "selected": str(L1B.value(candidates[0], "Name")),
        "available": [str(L1B.value(feature, "Name")) for feature in planes],
        "selection_contract": "NAMED_TOP_PLANE_OR_SECOND_DEFAULT_REFPLANE",
    }


def angle_mate_fact(
    feature: Any,
    expected_lower: float,
    expected_upper: float,
    expected_angle: float,
    types: Any,
    pythoncom: Any,
) -> Dict[str, Any]:
    raw_mate = L1B.value(feature, "GetSpecificFeature2")
    raw_definition = L1B.value(feature, "GetDefinition")
    if raw_mate is None or raw_definition is None:
        raise ProbeError("ANGLE_MATE_OBJECT_NULL", "advanced angle feature has no IMate2/IAngleMateFeatureData", {"feature": str(L1B.value(feature, "Name"))})
    mate = L1B.wrap(raw_mate, "IMate2", types, pythoncom)
    definition = L1B.wrap(raw_definition, "IAngleMateFeatureData", types, pythoncom)
    raw_display = mate.DisplayDimension2(0)
    if raw_display is None:
        raise ProbeError("ANGLE_DISPLAY_DIMENSION_NULL", "angle mate has no DisplayDimension2(0)", {"feature": str(L1B.value(feature, "Name"))})
    display = L1B.wrap(raw_display, "IDisplayDimension", types, pythoncom)
    raw_dimension = display.GetDimension2(0)
    if raw_dimension is None:
        raise ProbeError("ANGLE_DIMENSION_NULL", "angle mate display has no IDimension", {"feature": str(L1B.value(feature, "Name"))})
    dimension = L1B.wrap(raw_dimension, "IDimension", types, pythoncom)
    fact = {
        "feature_name": str(L1B.value(feature, "Name")),
        "mate_type": int(L1B.value(mate, "Type")),
        "mate_alignment": int(L1B.value(mate, "Alignment")),
        "advanced": bool(L1B.value(definition, "IsAdvancedMate")),
        "minimum_angle_rad": float(L1B.value(definition, "MinimumAngle")),
        "maximum_angle_rad": float(L1B.value(definition, "MaximumAngle")),
        "angle_rad": float(L1B.value(definition, "Angle")),
        "dimension_full_name": str(L1B.value(dimension, "FullName")),
        "feature_health": L1B.feature_error_state(feature),
        "endpoints": L1B.mate_object_fact(mate, types, pythoncom),
    }
    if (
        fact["mate_type"] != SW_MATE_ANGLE
        or not fact["advanced"]
        or abs(fact["minimum_angle_rad"] - expected_lower) > 1.0e-9
        or abs(fact["maximum_angle_rad"] - expected_upper) > 1.0e-9
        or abs(fact["angle_rad"] - expected_angle) > 1.0e-9
        or fact["feature_health"]["feature_error_code"] != 0
        or fact["feature_health"]["feature_error_code2"] != 0
        or fact["feature_health"]["feature_is_warning"]
        or fact["feature_health"]["suppressed"]
    ):
        raise ProbeError("ADVANCED_LIMIT_ANGLE_READBACK_FAIL", "native advanced limit-angle readback differs from its creation contract", fact)
    return fact


def add_named_limit_angle(
    model: Any,
    assembly: Any,
    first_component: Any,
    second_component: Any,
    name: str,
    types: Any,
    pythoncom: Any,
) -> Dict[str, Any]:
    before = L1B.mate_ledger(model, types, pythoncom)
    first_plane, first_plane_fact = component_ref_plane(first_component, types, pythoncom)
    second_plane, second_plane_fact = component_ref_plane(second_component, types, pythoncom)
    model.ClearSelection2(True)
    if not bool(first_plane.Select2(False, 1)) or not bool(second_plane.Select2(True, 1)):
        raise ProbeError("ANGLE_PLANE_SELECTION_FAIL", "cannot select both component Top planes", {"name": name})
    manager = L1B.selection_manager(model, types, pythoncom)
    selected = int(manager.GetSelectedObjectCount2(1))
    returned = assembly.AddMate3(
        SW_MATE_ANGLE,
        SW_ALIGN_ALIGNED,
        False,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        HINGE_LIMITS["creation_angle_rad"],
        HINGE_LIMITS["upper_rad"],
        HINGE_LIMITS["lower_rad"],
        False,
        0,
    )
    model.ClearSelection2(True)
    created = L1B.resolve_created_mate(
        model,
        returned,
        before,
        SW_MATE_ANGLE,
        SW_ALIGN_ALIGNED,
        (first_component, second_component),
        selected,
        types,
        pythoncom,
    )
    feature = rename_mate(model, created["feature_name"], name, types, pythoncom)
    readback = angle_mate_fact(
        feature,
        HINGE_LIMITS["lower_rad"],
        HINGE_LIMITS["upper_rad"],
        HINGE_LIMITS["creation_angle_rad"],
        types,
        pythoncom,
    )
    return {
        **created,
        "feature_name": name,
        "first_plane": first_plane_fact,
        "second_plane": second_plane_fact,
        "readback": readback,
        "creation_api": "IAssemblyDoc.AddMate3",
        "creation_return_contract": "IMate2_PLUS_ErrorStatus_1",
        "modify_definition_called": False,
    }


def identity_transform_error(component: Any) -> Tuple[List[float], float]:
    actual = L1B.transform_array(component)
    expected = L1B.transform_data((0.0, 0.0, 0.0))
    if len(actual) != 16:
        return actual, float("inf")
    return actual, max(abs(first - second) for first, second in zip(actual, expected))


def reference_ledger(model: Any, expected_paths: Iterable[Path], run_dir: Path, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    expected = {path.resolve() for path in expected_paths}
    rows = []
    for component in L1B.get_components(model, types, pythoncom):
        path = L1B.component_path(component)
        if path not in expected or run_dir.resolve() not in path.parents or not path.is_file():
            raise ProbeError("ASSEMBLY_REFERENCE_SCOPE_FAIL", "assembly contains a missing/unexpected/out-of-run component", {"component": str(L1B.value(component, "Name2")), "path": norm(path), "expected": sorted(norm(item) for item in expected)})
        transform, transform_error = identity_transform_error(component)
        if transform_error > 2.0e-7:
            raise ProbeError("ZERO_POSE_TRANSFORM_DRIFT", "mate creation moved a component away from the authored zero-pose identity", {"component": str(L1B.value(component, "Name2")), "transform": transform, "identity_max_abs_error": transform_error})
        rows.append(
            {
                "name2": str(L1B.value(component, "Name2")),
                "path": norm(path),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
                "fixed": bool(L1B.value(component, "IsFixed")),
                "suppression": int(L1B.value(component, "GetSuppression")),
                "transform16": transform,
                "identity_max_abs_error": transform_error,
            }
        )
    if len(rows) != 3 or {Path(row["path"]).resolve() for row in rows} != expected:
        raise ProbeError("ASSEMBLY_REFERENCE_CARDINALITY_FAIL", "assembly does not contain exactly the three microfixture parts", {"rows": rows})
    return sorted(rows, key=lambda row: row["path"])


def geometry_signature(
    body_a: Any,
    body_b: Any,
    body_c: Any,
    types: Any,
    pythoncom: Any,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for hinge, first, second, y_mm, first_face_x, second_face_x in (
        ("H1", body_a, body_b, 0.0, 0.0, 0.0),
        ("H2", body_b, body_c, 40.0, 6.0, 6.0),
    ):
        first_cylinder, first_cylinder_fact = L1B.cylinder_entity(first, 4.2, y_mm, 1, types, pythoncom)
        second_cylinder, second_cylinder_fact = L1B.cylinder_entity(second, 4.2, y_mm, 1, types, pythoncom)
        first_face, first_face_fact = L1B.plane_entity_x(first, first_face_x, types, pythoncom)
        second_face, second_face_fact = L1B.plane_entity_x(second, second_face_x, types, pythoncom)
        rows.append(
            {
                "hinge": hinge,
                "axis": {"direction": [1.0, 0.0, 0.0], "point_mm": [0.0, y_mm, 0.0]},
                "first_cylinder": first_cylinder_fact,
                "second_cylinder": second_cylinder_fact,
                "first_axial_face": first_face_fact,
                "second_axial_face": second_face_fact,
                "selection_contract": "EXACT_BREP_CYLINDER_RADIUS_AXIS_PLUS_UNIQUE_X_PLANE",
                "_entities": (first_cylinder, second_cylinder, first_face, second_face),
            }
        )
    return rows


def public_geometry_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{key: value for key, value in row.items() if key != "_entities"} for row in rows]


def build_and_cold_verify_assembly(
    sw: Any,
    types: Any,
    pythoncom: Any,
    target: Path,
    parts: Mapping[str, Path],
    run_dir: Path,
    run_id: str,
) -> Dict[str, Any]:
    assert_under_probe_root(target)
    if target.exists():
        raise ProbeError("WRITE_ONCE_ASSEMBLY_EXISTS", "diagnostic native assembly already exists", {"target": norm(target)})
    model = None
    try:
        raw = sw.NewDocument(str(ASSEMBLY_TEMPLATE), 0, 0.0, 0.0)
        if raw is None:
            raw = L1B.value(sw, "ActiveDoc")
        if raw is None:
            raise ProbeError("NEW_ASSEMBLY_FAIL", "cannot create the native diagnostic assembly")
        model = L1B.wrap(raw, "IModelDoc2", types, pythoncom)
        assembly = L1B.wrap(model, "IAssemblyDoc", types, pythoncom)
        components = {
            "A": L1B.insert_component(sw, model, assembly, parts["A"], True, (0.0, 0.0, 0.0), types, pythoncom),
            "B": L1B.insert_component(sw, model, assembly, parts["B"], False, (0.0, 0.0, 0.0), types, pythoncom),
            "C": L1B.insert_component(sw, model, assembly, parts["C"], False, (0.0, 0.0, 0.0), types, pythoncom),
        }
        # Re-resolve B-rep entities immediately before each hinge is mated.
        # AddMate3/rebuild can invalidate previously held IFace2/IEntity
        # handles even when the zero-pose transform does not move, so H2 must
        # not reuse entities captured before H1 was created.
        geometry: List[Dict[str, Any]] = []
        mates: List[Dict[str, Any]] = []
        for geometry_index, first_key, second_key in ((0, "A", "B"), (1, "B", "C")):
            row = geometry_signature(components["A"], components["B"], components["C"], types, pythoncom)[geometry_index]
            geometry.append(row)
            hinge = row["hinge"]
            first_cylinder, second_cylinder, first_face, second_face = row["_entities"]
            mates.append(
                add_named_entity_mate(
                    model,
                    assembly,
                    first_cylinder,
                    second_cylinder,
                    SW_MATE_CONCENTRIC,
                    (components[first_key], components[second_key]),
                    f"MF_{hinge}_CONCENTRIC",
                    types,
                    pythoncom,
                )
            )
            mates.append(
                add_named_entity_mate(
                    model,
                    assembly,
                    first_face,
                    second_face,
                    SW_MATE_COINCIDENT,
                    (components[first_key], components[second_key]),
                    f"MF_{hinge}_COINCIDENT",
                    types,
                    pythoncom,
                )
            )
            mates.append(
                add_named_limit_angle(
                    model,
                    assembly,
                    components[first_key],
                    components[second_key],
                    f"MF_{hinge}_LIMIT_ANGLE",
                    types,
                    pythoncom,
                )
            )
        if not bool(model.ForceRebuild3(True)):
            raise ProbeError("ASSEMBLY_REBUILD_FAIL", "diagnostic assembly force rebuild failed before save")
        live_references = reference_ledger(model, parts.values(), run_dir, types, pythoncom)
        live_mates = L1B.mate_ledger(model, types, pythoncom)
        expected_names = {
            "MF_H1_CONCENTRIC",
            "MF_H1_COINCIDENT",
            "MF_H1_LIMIT_ANGLE",
            "MF_H2_CONCENTRIC",
            "MF_H2_COINCIDENT",
            "MF_H2_LIMIT_ANGLE",
        }
        type_counts = Counter(row["mate_type"] for row in live_mates)
        if len(live_mates) != 6 or {row["feature_name"] for row in live_mates} != expected_names or type_counts != Counter({SW_MATE_COINCIDENT: 2, SW_MATE_CONCENTRIC: 2, SW_MATE_ANGLE: 2}):
            raise ProbeError("LIVE_MATE_SET_FAIL", "live assembly does not contain the exact six-mate serial-hinge contract", {"mate_ledger": live_mates, "type_counts": dict(type_counts)})
        L1B.set_properties(
            model,
            {
                "PartNumber": "V5-DIAG-MF-3BODY-2HINGE",
                "Description": "diagnostic native three-body two-hinge mate microfixture",
                "ARTIFACT_CLASS": "DIAGNOSTIC_MICROFIXTURE_NON_RELEASE",
                "PRODUCTION_USE": "PROHIBITED",
                "FLIGHT_QUALIFICATION": "NOT_APPLICABLE",
                "MATE_CONTRACT": "2x(CONCENTRIC+COINCIDENT+ADVANCED_LIMIT_ANGLE)",
                "HINGE_LIMIT_DEG": "0..90",
                "RUN_ID": run_id,
            },
        )
        saved = L1B.save_as(model, target)
    finally:
        L1B.close_doc(sw, model)
    live_files = {path: file_fact(path) for path in (*parts.values(), target)}
    cold = None
    try:
        cold, cold_open = L1B.open_doc(sw, target, SW_DOC_ASSEMBLY, True, types, pythoncom)
        if not bool(cold.ForceRebuild3(True)):
            raise ProbeError("COLD_ASSEMBLY_REBUILD_FAIL", "cold read-only assembly force rebuild failed")
        cold_references = reference_ledger(cold, parts.values(), run_dir, types, pythoncom)
        cold_mates = L1B.mate_ledger(cold, types, pythoncom)
        cold_type_counts = Counter(row["mate_type"] for row in cold_mates)
        if len(cold_mates) != 6 or {row["feature_name"] for row in cold_mates} != expected_names or cold_type_counts != Counter({SW_MATE_COINCIDENT: 2, SW_MATE_CONCENTRIC: 2, SW_MATE_ANGLE: 2}):
            raise ProbeError("COLD_MATE_SET_FAIL", "cold assembly mate set drifted", {"mate_ledger": cold_mates, "type_counts": dict(cold_type_counts)})
        cold_feature_map = mate_feature_map(cold, types, pythoncom)
        cold_angles = [
            angle_mate_fact(cold_feature_map[name], HINGE_LIMITS["lower_rad"], HINGE_LIMITS["upper_rad"], HINGE_LIMITS["creation_angle_rad"], types, pythoncom)
            for name in ("MF_H1_LIMIT_ANGLE", "MF_H2_LIMIT_ANGLE")
        ]
        cold_components = {norm(L1B.component_path(component)): component for component in L1B.get_components(cold, types, pythoncom)}
        cold_geometry = geometry_signature(
            cold_components[norm(parts["A"])],
            cold_components[norm(parts["B"])],
            cold_components[norm(parts["C"])],
            types,
            pythoncom,
        )
    finally:
        L1B.close_doc(sw, cold)
        L1B.close_owned_documents(sw)
    cold_files = {path: file_fact(path) for path in (*parts.values(), target)}
    if live_files != cold_files:
        raise ProbeError(
            "COLD_OPEN_FILE_DRIFT",
            "read-only cold reopen changed one or more write-once native files",
            {"before": {norm(path): fact for path, fact in live_files.items()}, "after": {norm(path): fact for path, fact in cold_files.items()}},
        )
    if int(L1B.value(sw, "GetDocumentCount")) != 0 or L1B.value(sw, "ActiveDoc") is not None:
        raise ProbeError("POST_COLD_SESSION_NOT_EMPTY", "diagnostic documents remained open after cold verification")
    return {
        "target": saved,
        "live_references": live_references,
        "live_mates": live_mates,
        "live_mate_creation": mates,
        "live_geometry": public_geometry_rows(geometry),
        "cold_open": cold_open,
        "cold_references": cold_references,
        "cold_mates": cold_mates,
        "cold_advanced_limit_angles": cold_angles,
        "cold_geometry": public_geometry_rows(cold_geometry),
        "cold_file_identity": [cold_files[path] for path in (*parts.values(), target)],
        "verdict": "V5_DIAG_3BODY_2HINGE_NATIVE_MATE_COLD_PASS",
    }


def write_manifest(run_dir: Path, files: Sequence[Path]) -> Dict[str, Any]:
    path = run_dir / "MANIFEST_SHA256.txt"
    lines = []
    for file in sorted(files, key=lambda item: item.relative_to(run_dir).as_posix()):
        assert_under_probe_root(file)
        lines.append(f"{sha256(file)} *{file.relative_to(run_dir).as_posix()}")
    write_text_once(path, "\n".join(lines) + "\n")
    return {**file_fact(path), "entries": len(lines), "scope": "CAD_FILES_ONLY"}


def execute(run_id: str, expected_pid: int) -> Dict[str, Any]:
    audit = static_audit(run_id)
    if not audit["execution_authorized"]:
        raise ProbeError("STATIC_AUDIT_HOLD", "static audit did not authorize the diagnostic run", {"audit": audit})
    if expected_pid <= 0:
        raise ProbeError("EXPECTED_PID_INVALID", "expected SOLIDWORKS PID must be positive", {"expected_pid": expected_pid})
    target = run_directory(run_id)
    target.mkdir(parents=False, exist_ok=False)
    sw = None
    pythoncom = None
    try:
        sw, types, pythoncom, session = L1B.attach_empty_session(expected_pid)
        part_paths = {
            "A": target / "parts/MF_BODY_A_FIXED.SLDPRT",
            "B": target / "parts/MF_BODY_B_MIDDLE.SLDPRT",
            "C": target / "parts/MF_BODY_C_FOLLOWER.SLDPRT",
        }
        part_results = [
            make_annulus_part(sw, types, pythoncom, part_paths["A"], "BODY_A_FIXED", -6.0, 0.0, run_id),
            make_middle_link_part(sw, types, pythoncom, part_paths["B"], run_id),
            make_annulus_part(sw, types, pythoncom, part_paths["C"], "BODY_C_FOLLOWER", 6.0, 40.0, run_id),
        ]
        assembly_path = target / "assembly/MF_THREE_BODY_TWO_HINGE.SLDASM"
        assembly_result = build_and_cold_verify_assembly(sw, types, pythoncom, assembly_path, part_paths, target, run_id)
        manifest = write_manifest(target, (*part_paths.values(), assembly_path))
        result = {
            "schema": "F3R2_V5_DIAG_SOLAR_HINGE_MICROFIXTURE_RESULT_V1",
            "timestamp_utc": utc_now(),
            "run_id": run_id,
            "classification": "DIAGNOSTIC_MICROFIXTURE_NON_RELEASE",
            "release_claim": False,
            "production_use_permitted": False,
            "flight_ready": False,
            "launch_qualified": False,
            "script": file_fact(Path(__file__)),
            "static_audit": audit,
            "session": session,
            "output_root": norm(target),
            "write_scope": norm(PROBE_ROOT),
            "parts": part_results,
            "assembly": assembly_result,
            "manifest": manifest,
            "mate_contract": {
                "bodies": 3,
                "serial_hinges": 2,
                "hinge_axis_direction": [1.0, 0.0, 0.0],
                "hinge_axis_points_mm": [[0.0, 0.0, 0.0], [0.0, 40.0, 0.0]],
                "per_hinge": ["CONCENTRIC", "COINCIDENT", "ADVANCED_LIMIT_ANGLE"],
                "limit_angle_deg": [0.0, 90.0],
                "creation_angle_deg": 0.0,
            },
            "scope_note": "This proves SW2024 native mate creation/persistence only; it does not authorize solar geometry, clearances, masses or release.",
            "verdict": "V5_DIAG_SOLAR_3BODY_2HINGE_LIMIT_ANGLE_COLD_PASS",
        }
        write_json_once(target / "RESULT_PASS.json", result)
        return result
    except Exception as exc:
        if sw is not None:
            try:
                L1B.close_owned_documents(sw)
            except Exception:
                pass
        failure = {
            "schema": "F3R2_V5_DIAG_SOLAR_HINGE_MICROFIXTURE_FAILURE_V1",
            "timestamp_utc": utc_now(),
            "run_id": run_id,
            "classification": "DIAGNOSTIC_MICROFIXTURE_NON_RELEASE",
            "output_root": norm(target),
            "exception_type": type(exc).__name__,
            "error": str(exc),
            "error_code": getattr(exc, "code", "UNHANDLED_EXCEPTION"),
            "detail": getattr(exc, "detail", {}),
            "traceback": traceback.format_exc(),
            "verdict": "V5_DIAG_SOLAR_HINGE_MICROFIXTURE_FAIL",
        }
        failure_path = target / "RESULT_FAIL.json"
        if not failure_path.exists():
            write_json_once(failure_path, failure)
        raise
    finally:
        if pythoncom is not None:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit", help="filesystem-only safety/readiness audit")
    audit.add_argument("--run-id", default=None)
    run = commands.add_parser("execute", help="attach to an existing empty SW2024 SP5 session and run the diagnostic")
    run.add_argument("--run-id", required=True)
    run.add_argument("--expected-pid", required=True, type=int)
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "audit":
            result = static_audit(args.run_id)
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            return 0 if result["execution_authorized"] else 2
        result = execute(args.run_id, args.expected_pid)
        print(json.dumps({"run_id": result["run_id"], "output_root": result["output_root"], "verdict": result["verdict"]}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        payload = {
            "timestamp_utc": utc_now(),
            "exception_type": type(exc).__name__,
            "error": str(exc),
            "error_code": getattr(exc, "code", "UNHANDLED_EXCEPTION"),
            "detail": getattr(exc, "detail", {}),
            "verdict": "V5_DIAG_SOLAR_HINGE_MICROFIXTURE_HOLD",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
