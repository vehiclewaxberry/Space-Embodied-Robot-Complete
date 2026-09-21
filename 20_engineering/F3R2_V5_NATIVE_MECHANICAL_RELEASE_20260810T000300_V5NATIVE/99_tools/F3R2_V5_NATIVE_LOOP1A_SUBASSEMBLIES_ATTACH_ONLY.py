#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the Rev-B2 adapter and G07/G08/Mid native subassemblies.

The application connection is strictly GetActiveObject-only through the
already-audited Loop-1 helper.  No application start/exit or visibility/user
control mutation is present.  The script writes only inside the claimed V5
root, preserves all protected parents, uses actual planar/cylindrical faces for
the load-path mates, and cold-reopens every saved assembly read-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base


sys.dont_write_bytecode = True

ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
RUN_ROOT = ROOT / "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
RUN_ID = "20260810T000300_V5NATIVE"
# The F:-profile templates are preserved and still audited by the fixed G0/
# import receipts, but this live Session-B process rejects NewDocument on that
# profile path.  The installed GB templates below were runtime-probed in the
# same empty attach-only session, then pinned by exact hash.
ASSEMBLY_TEMPLATE = Path(r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_assembly.asmdot")
PART_TEMPLATE = Path(r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_part.prtdot")
ASSEMBLY_TEMPLATE_SHA256 = "37DED9268BABC616A97BF9DA29BDCC2FFD60E8E4353670748F74A18A3BB450CC"
PART_TEMPLATE_SHA256 = "5DA21678EFE07EF465770630BEB4FFE540F23D47FCA07715F74D2AFDBEA87271"
IMPORT_RECEIPT = RUN_ROOT / "13_validation/V5_LOOP1_NEUTRAL_IMPORT_RECEIPT.json"
IMPORT_RECEIPT_SHA256 = "9FC8D1DBBBDD7D1FE37F5FCCA4359838827282A0D7A961D8EEB511E75BE7160D"
AUTHORITY_RECEIPT = RUN_ROOT / "13_validation/V5_AUTHORITY_SEED_RECEIPT.json"
AUTHORITY_RECEIPT_SHA256 = "7251758420639907CAB4F4C134A278B0F860535BCC62A8E264E6862B7ECBED0F"
BASE_HELPER = ROOT / "F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py"
BASE_HELPER_COPY = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py"
BASE_HELPER_SHA256 = "1F589D3FAE23D64F2364B1CE98FA232A1AA19648398521E55CB5C7F85D0B6062"
# This exact predecessor created and cold-reopened the diamond locator before
# a later assembly-document-count guard (not the part build) failed.  It is
# accepted only for that one checkpoint and is re-cold-opened on resume.
DIAMOND_CHECKPOINT_PREDECESSOR_SHA256 = "8DB7E5AEEDF968A06CB54E8124D87C63FC9BF56837F3B6B94CC4522B3B27EE2C"

SW_MATE_COINCIDENT = 0
SW_MATE_CONCENTRIC = 1
SW_MATE_DISTANCE = 5
SW_MATE_LOCK = 16
SW_ALIGN_ALIGNED = 0
SW_ALIGN_ANTI = 1
SW_ALIGN_CLOSEST = 2
SW_ADD_MATE_NO_ERROR = 1

PIN_PATH = RUN_ROOT / "01_native_parts/adapter/B601_DIAMOND_DOWEL_4MM.SLDPRT"

ASSEMBLIES: Dict[str, Dict[str, Any]] = {
    "B601_BASE_ADAPTER_REV_B2": {
        "target": RUN_ROOT / "02_native_subassemblies/B601_BASE_ADAPTER_REV_B2.SLDASM",
        "kind": "adapter",
        "components": [
            ("STAGE_B", RUN_ROOT / "01_native_parts/adapter/B601_LOAD_ADAPTER_STAGE_B_REV_B2.SLDPRT", True, (0.0, 0.0, 0.0)),
            ("STAGE_A", RUN_ROOT / "01_native_parts/adapter/B601_INTERFACE_STAGE_A_REV_B2.SLDPRT", False, (0.0, 0.0, 0.0)),
            # The one-direction extrusion spans local Z=[0,12] mm.  Place it
            # at global Z=[-10,+2] mm so it stays inside the measured Stage-B
            # and Stage-A locator bores instead of protruding above Stage A.
            ("DIAMOND_DOWEL", PIN_PATH, False, (0.055, 0.0, -0.010)),
        ],
    },
    "G07_PRIMARY_SUPPORT_V2": {
        "target": RUN_ROOT / "02_native_subassemblies/G07_PRIMARY_SUPPORT_V2.SLDASM",
        "kind": "support",
        "body_top_mm": 252.5016,
        "carrier_bottom_mm": 254.5016,
        "carrier_top_mm": 258.5016,
        "pad_bottom_mm": 258.5016,
        "body_carrier_distance_mm": 2.0,
        "components": [
            ("BODY", RUN_ROOT / "01_native_parts/supports/G07_PRIMARY_SUPPORT_V2.SLDPRT", True, (0.0, 0.0, 0.0)),
            ("CARRIER", RUN_ROOT / "01_native_parts/supports/G07_PAD_CARRIER_V2.SLDPRT", False, (0.0, 0.0, 0.0)),
            ("PAD", RUN_ROOT / "01_native_parts/supports/G07_PTFE_CONTACT_PAD_V2.SLDPRT", False, (0.0, 0.0, 0.0)),
        ],
    },
    "G08_PRIMARY_SUPPORT_V2": {
        "target": RUN_ROOT / "02_native_subassemblies/G08_PRIMARY_SUPPORT_V2.SLDASM",
        "kind": "support",
        "body_top_mm": 202.4929,
        "carrier_bottom_mm": 202.4929,
        "carrier_top_mm": 206.4929,
        "pad_bottom_mm": 206.4929,
        "body_carrier_distance_mm": 0.0,
        "components": [
            ("BODY", RUN_ROOT / "01_native_parts/supports/G08_PRIMARY_SUPPORT_V2.SLDPRT", True, (0.0, 0.0, 0.0)),
            ("CARRIER", RUN_ROOT / "01_native_parts/supports/G08_PAD_CARRIER_V2.SLDPRT", False, (0.0, 0.0, 0.0)),
            ("PAD", RUN_ROOT / "01_native_parts/supports/G08_VMQ_CONTACT_PAD_V2.SLDPRT", False, (0.0, 0.0, 0.0)),
        ],
    },
    "MID_BACKUP_SUPPORT_V2": {
        "target": RUN_ROOT / "02_native_subassemblies/MID_BACKUP_SUPPORT_V2.SLDASM",
        "kind": "support",
        "body_top_mm": 205.9189,
        "carrier_bottom_mm": 205.9189,
        "carrier_top_mm": 209.9189,
        "pad_bottom_mm": 209.9189,
        "body_carrier_distance_mm": 0.0,
        "components": [
            ("BODY", RUN_ROOT / "01_native_parts/supports/MID_BACKUP_SUPPORT_V2.SLDPRT", True, (0.0, 0.0, 0.0)),
            ("CARRIER", RUN_ROOT / "01_native_parts/supports/MID_PAD_CARRIER_V2.SLDPRT", False, (0.0, 0.0, 0.0)),
            ("PAD", RUN_ROOT / "01_native_parts/supports/MID_CONTACT_PAD_V2.SLDPRT", False, (0.0, 0.0, 0.0)),
        ],
    },
}

PIN_CHECKPOINT = RUN_ROOT / "13_validation/V5_LOOP1A_CHECKPOINT_DIAMOND_LOCATOR.json"
ASSEMBLY_CHECKPOINTS = {
    name: RUN_ROOT / f"13_validation/V5_LOOP1A_CHECKPOINT_{name}.json"
    for name in ASSEMBLIES
}
FINAL_RECEIPT = RUN_ROOT / "13_validation/V5_LOOP1A_SUBASSEMBLY_RECEIPT.json"
SCRIPT_COPY = RUN_ROOT / "99_tools" / Path(__file__).name
FINAL_MANIFEST = RUN_ROOT / "14_release/V5_LOOP1A_SUBASSEMBLY_MANIFEST_SHA256.txt"


class GateError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    return base.sha256(path)


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        result = json.load(stream)
    if not isinstance(result, dict):
        raise GateError("JSON_ROOT_FAIL", f"JSON root must be an object: {path}")
    return result


def write_json_once(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def validate_inputs() -> Dict[str, Any]:
    if not RUN_ROOT.is_dir():
        raise GateError("V5_ROOT_MISSING", "claimed V5 root is absent")
    fixed = (
        (ASSEMBLY_TEMPLATE, ASSEMBLY_TEMPLATE_SHA256),
        (PART_TEMPLATE, PART_TEMPLATE_SHA256),
        (IMPORT_RECEIPT, IMPORT_RECEIPT_SHA256),
        (AUTHORITY_RECEIPT, AUTHORITY_RECEIPT_SHA256),
        (BASE_HELPER, BASE_HELPER_SHA256),
        (BASE_HELPER_COPY, BASE_HELPER_SHA256),
    )
    audits = []
    for path, expected in fixed:
        actual = sha256(path) if path.is_file() else None
        row = {"path": str(path).replace("\\", "/"), "exists": path.is_file(), "expected_sha256": expected, "actual_sha256": actual, "pass": actual == expected}
        audits.append(row)
    if not all(row["pass"] for row in audits):
        raise GateError("FIXED_INPUT_HASH_FAIL", "template or receipt hash drift", {"audits": audits})
    receipt = load_json(IMPORT_RECEIPT)
    if receipt.get("verdict") != "V5_LOOP1_NEUTRAL_NATIVE_PART_IMPORT_PASS" or receipt.get("native_part_count") != 20:
        raise GateError("IMPORT_RECEIPT_FAIL", "20-part import PASS is not proven")
    registered: Dict[str, Dict[str, Any]] = {}
    for item in receipt.get("native_parts", []):
        target = item.get("target", {})
        path = Path(str(target.get("path", ""))).resolve()
        if not path.is_file() or RUN_ROOT.resolve() not in path.parents:
            raise GateError("NATIVE_PART_PATH_FAIL", "registered part is absent or outside V5", {"path": str(path)})
        if target.get("sha256") != sha256(path) or target.get("bytes") != path.stat().st_size:
            raise GateError("NATIVE_PART_DRIFT", "registered native part changed", {"path": str(path)})
        registered[str(path)] = {
            "path": str(path).replace("\\", "/"),
            "bytes": target.get("bytes"),
            "sha256": target.get("sha256"),
        }
    if len(registered) != 20:
        raise GateError("REGISTERED_PART_COUNT_FAIL", "Loop-1 receipt does not register exactly 20 unique parts", {"count": len(registered)})
    for spec in ASSEMBLIES.values():
        for role, path, _fixed, _translation in spec["components"]:
            if role == "DIAMOND_DOWEL":
                continue
            if str(path.resolve()) not in registered:
                raise GateError("ASSEMBLY_COMPONENT_NOT_REGISTERED", "component is outside Loop-1 manifest", {"role": role, "path": str(path)})
    return {"fixed": audits, "registered_part_count": len(registered), "registered_parts": sorted(registered.values(), key=lambda row: row["path"])}


def audit_registered_parts(expected_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for expected in expected_rows:
        path = Path(str(expected["path"]))
        actual_hash = sha256(path) if path.is_file() else None
        actual_bytes = path.stat().st_size if path.is_file() else None
        row = {
            "path": str(path).replace("\\", "/"),
            "expected_bytes": expected["bytes"],
            "actual_bytes": actual_bytes,
            "expected_sha256": expected["sha256"],
            "actual_sha256": actual_hash,
            "pass": actual_bytes == expected["bytes"] and actual_hash == expected["sha256"],
        }
        rows.append(row)
    if len(rows) != 20 or not all(row["pass"] for row in rows):
        raise GateError("V5_NATIVE_PART_HASH_DRIFT", "one or more of the 20 imported native parts drifted", {"rows": rows})
    return rows


def select_front_plane(model: Any) -> str:
    model.ClearSelection2(True)
    for name in ("前视基准面", "Front Plane"):
        if bool(model.Extension.SelectByID2(name, "PLANE", 0.0, 0.0, 0.0, False, 0, None, 0)):
            return name
    raise GateError("FRONT_PLANE_SELECTION_FAIL", "cannot select native Front Plane")


def make_diamond_pin(sw: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    if PIN_PATH.exists():
        raise GateError("DIAMOND_PIN_ALREADY_EXISTS", "write-once diamond pin target already exists")
    raw = sw.NewDocument(str(PART_TEMPLATE), 0, 0.0, 0.0)
    if raw is None:
        raw = base.value(sw, "ActiveDoc")
    if raw is None:
        raise GateError("PIN_NEW_DOCUMENT_FAIL", "cannot create diamond locator part")
    model = base.wrap(raw, "IModelDoc2", types, pythoncom)
    title = str(base.value(model, "GetTitle"))
    try:
        plane = select_front_plane(model)
        sketch = model.SketchManager
        sketch.InsertSketch(True)
        # The full 4 mm width is tangential (global Y at the [55,0] station)
        # and the relieved 3 mm width is radial.  This is the physical
        # round-plus-diamond scheme: Stage B Ø4.0 provides nominal tangential
        # line contact, while Stage A Ø4.1 and the 3 mm radial width avoid a
        # second fully radial round-pin constraint.
        points = ((0.0015, 0.0), (0.0, 0.002), (-0.0015, 0.0), (0.0, -0.002), (0.0015, 0.0))
        segments = []
        for (x1, y1), (x2, y2) in zip(points[:-1], points[1:]):
            segment = sketch.CreateLine(x1, y1, 0.0, x2, y2, 0.0)
            if segment is None:
                raise GateError("PIN_SKETCH_FAIL", "diamond locator line creation failed")
            segments.append(segment)
        sketch.InsertSketch(True)
        feature = model.FeatureManager.FeatureExtrusion2(
            True, False, False, 0, 0, 0.012, 0.0,
            False, False, False, False, 0.0, 0.0,
            False, False, False, False, True, True, True,
            0, 0.0, False,
        )
        if feature is None:
            raise GateError("PIN_EXTRUSION_FAIL", "diamond locator extrusion returned null")
        manager = model.Extension.CustomPropertyManager("")
        properties = {
            "PartNumber": "SEI-MECH-B601-DIAMOND-004",
            "Description": "4 x 3 x 12 mm relieved diamond clocking locator",
            "Revision": "V5-A",
            "MaterialSpecification": "17-4PH_H900_CANDIDATE",
            "RELEASE_SCOPE": "COMPETITION_PROTOTYPE_MANUFACTURING_DEFINITION",
            "LOCATING_ROLE": "ONE_RELIEVED_DIAMOND_LOCATOR_DO_NOT_USE_SECOND_ROUND_PIN",
            "RUN_ID": RUN_ID,
            "FLIGHT_QUALIFICATION": "HOLD",
        }
        for name, value in properties.items():
            if int(manager.Add3(name, 30, value, 2)) < 0:
                raise GateError("PIN_PROPERTY_FAIL", f"cannot set {name}")
        save = base.save_native_part(model, PIN_PATH)
    finally:
        try:
            sw.CloseDoc(str(base.value(model, "GetTitle")))
        except Exception:
            sw.CloseDoc(title)
    if int(base.value(sw, "GetDocumentCount")) != 0:
        raise GateError("PIN_CLOSE_FAIL", "diamond pin remained open")
    cold, cold_open = base.open_read_only(sw, PIN_PATH, types, pythoncom)
    cold_title = str(base.value(cold, "GetTitle"))
    try:
        facts = base.body_facts(cold, types, pythoncom)
        if facts["solid_body_count"] != 1:
            raise GateError("PIN_BODY_FAIL", "diamond pin is not one solid body", facts)
        box = facts["bounding_box_mm"]
        dimensions = sorted((box[3] - box[0], box[4] - box[1], box[5] - box[2]))
        expected = [3.0, 4.0, 12.0]
        if any(abs(a - b) > 0.02 for a, b in zip(dimensions, expected)):
            raise GateError("PIN_DIMENSION_FAIL", "diamond pin dimensions drifted", {"dimensions_mm": dimensions})
    finally:
        sw.CloseDoc(cold_title)
    return {"path": str(PIN_PATH).replace("\\", "/"), "save": save, "cold_open": cold_open, "cold_facts": facts, "front_plane": plane, "verdict": "V5_DIAMOND_LOCATOR_NATIVE_PASS"}


def unpack_document(result: Any, label: str) -> Tuple[Any, int, int]:
    if not isinstance(result, tuple) or len(result) < 3:
        raise GateError(f"{label}_RETURN_SHAPE_FAIL", f"{label} did not return model/errors/warnings", {"returned": repr(result)})
    model, outs = base.unpack(result)
    return model, int(outs[0]), int(outs[1])


def activate(sw: Any, title: str) -> Any:
    returned = sw.ActivateDoc3(title, True, 0, 0)
    if isinstance(returned, tuple):
        model, outs = base.unpack(returned)
        error = int(outs[0]) if outs else 0
    else:
        model, error = returned, 0
    if model is None or error != 0:
        raise GateError("ACTIVATE_ASSEMBLY_FAIL", "cannot activate owned assembly", {"title": title, "error": error})
    return model


def transform_data(translation: Tuple[float, float, float]) -> List[float]:
    return [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, translation[0], translation[1], translation[2], 1.0, 0.0, 0.0, 0.0]


def insert_component(sw: Any, model: Any, assembly: Any, path: Path, fixed: bool, translation: Tuple[float, float, float], types: Any, pythoncom: Any) -> Any:
    raw_part = part = None
    part_title: Optional[str] = None
    assembly_title = str(base.value(model, "GetTitle"))
    baseline_count = int(base.value(sw, "GetDocumentCount"))
    try:
        # SILENT | READONLY.  Imported native source parts are immutable inputs
        # to this assembly pass and are independently hash-audited PRE/POST.
        raw_part, errors, warnings = unpack_document(sw.OpenDoc6(str(path), 1, 3, "", 0, 0), "OPEN_COMPONENT")
        if raw_part is not None:
            part = base.wrap(raw_part, "IModelDoc2", types, pythoncom)
            part_title = str(base.value(part, "GetTitle"))
        if raw_part is None or errors != 0 or warnings != 0 or not bool(base.value(part, "IsOpenedReadOnly")):
            raise GateError("OPEN_COMPONENT_FAIL", "component read-only preload failed", {"path": str(path), "errors": errors, "warnings": warnings})
        activate(sw, assembly_title)
        raw_component = assembly.AddComponent5(str(path), 0, "", False, "", 0.0, 0.0, 0.0)
        if raw_component is None:
            raise GateError("ADD_COMPONENT_FAIL", "AddComponent5 returned null", {"path": str(path)})
        component = base.wrap(raw_component, "IComponent2", types, pythoncom)
        math_utility = base.wrap(base.value(sw, "GetMathUtility"), "IMathUtility", types, pythoncom)
        from win32com.client import VARIANT

        typed = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, transform_data(translation))
        transform = math_utility.CreateTransform(typed)
        if transform is None:
            raise GateError("CREATE_TRANSFORM_FAIL", "CreateTransform returned null")
        if not bool(component.SetTransformAndSolve3(transform, True)):
            raise GateError("COMPONENT_TRANSFORM_SOLVE_FAIL", "SetTransformAndSolve3 returned false", {"path": str(path)})
        model.EditRebuild3()
        readback = [float(v) for v in base.as_list(base.value(base.value(component, "Transform2"), "ArrayData"))]
        if len(readback) != 16 or any(abs(readback[9 + index] - translation[index]) > 1.0e-8 for index in range(3)):
            raise GateError("COMPONENT_TRANSFORM_FAIL", "component transform readback mismatch", {"path": str(path), "readback": readback, "expected_translation": translation})
        model.ClearSelection2(True)
        if not bool(component.Select4(False, None, False)):
            raise GateError("COMPONENT_SELECTION_FAIL", "cannot select component for fixed-state change")
        if fixed:
            assembly.FixComponent()
        else:
            assembly.UnfixComponent()
        model.ClearSelection2(True)
        if bool(base.value(component, "IsFixed")) != fixed:
            raise GateError("COMPONENT_FIXED_STATE_FAIL", "fixed state did not read back", {"path": str(path), "expected": fixed})
        return component
    finally:
        if part_title:
            try:
                sw.CloseDoc(part_title)
            except Exception:
                pass
        # Once inserted, SolidWorks intentionally keeps the part document
        # resident as an assembly dependency.  It is not a stray top-level
        # user document: the active document must be the owned assembly and
        # the document graph must grow by exactly this one unique dependency.
        actual_count = int(base.value(sw, "GetDocumentCount"))
        # ISldWorks.ActiveDoc is exposed as a default dispatch member in this
        # Session-B makepy wrapper and can raise DISP_E_MEMBERNOTFOUND when it
        # is read through the generic helper.  ActivateDoc3 is the already
        # proven, typed path: it both restores the owned assembly as the active
        # document and fails closed if that exact title is unavailable.
        activate(sw, assembly_title)
        if actual_count != baseline_count + 1:
            raise GateError("COMPONENT_DEPENDENCY_GRAPH_FAIL", "component preload cleanup did not leave the expected assembly/dependency graph", {"path": str(path), "baseline_count": baseline_count, "actual_count": actual_count, "assembly_title": assembly_title})


def component_bodies(component: Any, types: Any, pythoncom: Any) -> List[Any]:
    for call in (("GetBodies2", (0,)), ("GetBodies2", (1,)), ("GetBody", ())):
        try:
            raw = base.value(component, call[0], *call[1])
        except Exception:
            continue
        bodies = base.as_list(raw)
        if bodies:
            return [base.wrap(body, "IBody2", types, pythoncom) for body in bodies]
    raise GateError("COMPONENT_BODY_FAIL", "component exposes no body")


def planar_face(component: Any, target_z_mm: float, types: Any, pythoncom: Any) -> Tuple[Any, Dict[str, Any]]:
    candidates = []
    for body in component_bodies(component, types, pythoncom):
        for raw_face in base.as_list(base.value(body, "GetFaces")):
            face = base.wrap(raw_face, "IFace2", types, pythoncom)
            surface = base.wrap(base.value(face, "GetSurface"), "ISurface", types, pythoncom)
            if not bool(surface.IsPlane()):
                continue
            params = [float(v) for v in base.as_list(base.value(surface, "PlaneParams"))]
            if len(params) < 6 or abs(abs(params[2]) - 1.0) > 1.0e-5:
                continue
            z_mm = params[5] * 1000.0
            if abs(z_mm - target_z_mm) > 0.03:
                continue
            area = float(base.value(face, "GetArea")) * 1.0e6
            candidates.append((area, face, params))
    if len(candidates) != 1:
        raise GateError("PLANAR_FACE_SIGNATURE_NOT_UNIQUE", "expected exactly one Z-plane face signature", {"component": str(base.value(component, "Name2")), "target_z_mm": target_z_mm, "candidate_count": len(candidates), "areas_mm2": [item[0] for item in candidates]})
    candidates.sort(key=lambda item: -item[0])
    area, face, params = candidates[0]
    return base.wrap(face, "IEntity", types, pythoncom), {"target_z_mm": target_z_mm, "plane_params": params, "area_mm2": area, "candidate_count": len(candidates)}


def cylindrical_face(component: Any, radius_mm: float, center_xy_mm: Tuple[float, float], types: Any, pythoncom: Any) -> Tuple[Any, Dict[str, Any]]:
    candidates = []
    for body in component_bodies(component, types, pythoncom):
        for raw_face in base.as_list(base.value(body, "GetFaces")):
            face = base.wrap(raw_face, "IFace2", types, pythoncom)
            surface = base.wrap(base.value(face, "GetSurface"), "ISurface", types, pythoncom)
            if not bool(surface.IsCylinder()):
                continue
            params = [float(v) for v in base.as_list(base.value(surface, "CylinderParams"))]
            if len(params) < 7:
                continue
            origin = (params[0] * 1000.0, params[1] * 1000.0)
            axis = params[3:6]
            radius = params[6] * 1000.0
            if abs(abs(axis[2]) - 1.0) > 1.0e-5 or math.dist(origin, center_xy_mm) > 0.05 or abs(radius - radius_mm) > 0.05:
                continue
            area = float(base.value(face, "GetArea")) * 1.0e6
            candidates.append((area, face, params))
    if len(candidates) != 1:
        raise GateError("CYLINDER_FACE_SIGNATURE_NOT_UNIQUE", "expected exactly one cylindrical face signature", {"component": str(base.value(component, "Name2")), "radius_mm": radius_mm, "center_xy_mm": center_xy_mm, "candidate_count": len(candidates), "areas_mm2": [item[0] for item in candidates]})
    candidates.sort(key=lambda item: -item[0])
    area, face, params = candidates[0]
    return base.wrap(face, "IEntity", types, pythoncom), {"radius_mm": radius_mm, "center_xy_mm": center_xy_mm, "cylinder_params": params, "area_mm2": area, "candidate_count": len(candidates)}


def selection_manager(model: Any, types: Any, pythoncom: Any) -> Any:
    for name in ("ISelectionManager", "SelectionManager"):
        try:
            raw = getattr(model, name)
            if raw is not None:
                return base.wrap(raw, "ISelectionMgr", types, pythoncom)
        except Exception:
            continue
    raise GateError("SELECTION_MANAGER_FAIL", "cannot obtain ISelectionMgr")


def add_entity_mate(model: Any, assembly: Any, first: Any, second: Any, mate_type: int, align: int, distance_m: float, types: Any, pythoncom: Any) -> Dict[str, Any]:
    model.ClearSelection2(True)
    manager = selection_manager(model, types, pythoncom)
    data = base.wrap(manager.CreateSelectData(), "ISelectData", types, pythoncom)
    data.Mark = 1
    if not bool(first.Select4(False, data)) or not bool(second.Select4(True, data)):
        raise GateError("ENTITY_SELECTION_FAIL", "IEntity.Select4 failed")
    selected = int(manager.GetSelectedObjectCount2(1))
    returned = assembly.AddMate3(mate_type, align, False, distance_m, distance_m, distance_m, 0.0, 0.0, 0.0, 0.0, 0.0, False, 0)
    feature, outs = base.unpack(returned)
    error = int(outs[0]) if outs else -1
    model.ClearSelection2(True)
    if feature is None or error != SW_ADD_MATE_NO_ERROR or selected != 2:
        raise GateError("ADD_ENTITY_MATE_FAIL", "AddMate3 failed", {"mate_type": mate_type, "align": align, "distance_m": distance_m, "error": error, "selected": selected})
    return {"mate_type": mate_type, "align": align, "distance_m": distance_m, "error_status": error, "selected_count": selected}


def select_component_plane(model: Any, component: Any, plane: str, append: bool) -> str:
    candidates = {
        "RIGHT": ("右视基准面", "Right Plane"),
        "TOP": ("上视基准面", "Top Plane"),
        "FRONT": ("前视基准面", "Front Plane"),
    }[plane]
    names = []
    comp_name = str(base.value(component, "Name2"))
    names.extend((comp_name, comp_name.split("/")[-1]))
    for datum in candidates:
        try:
            raw_feature = component.FeatureByName(datum)
            if raw_feature is not None:
                feature = raw_feature
                if bool(feature.Select2(append, 1)):
                    return f"{datum}@{comp_name}::IComponent2.FeatureByName"
        except Exception:
            pass
        assembly_stem = Path(str(base.value(model, "GetTitle"))).stem
        for name in names:
            for full in (f"{datum}@{name}@{assembly_stem}", f"{datum}@{name}"):
                if bool(model.Extension.SelectByID2(full, "PLANE", 0.0, 0.0, 0.0, append, 1, None, 0)):
                    return full
    raise GateError("COMPONENT_PLANE_SELECTION_FAIL", "cannot select component datum plane", {"component": comp_name, "plane": plane})


def add_plane_mate(model: Any, assembly: Any, first: Any, second: Any, plane: str) -> Dict[str, Any]:
    model.ClearSelection2(True)
    a = select_component_plane(model, first, plane, False)
    b = select_component_plane(model, second, plane, True)
    returned = assembly.AddMate3(SW_MATE_COINCIDENT, SW_ALIGN_ALIGNED, False, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False, 0)
    feature, outs = base.unpack(returned)
    error = int(outs[0]) if outs else -1
    model.ClearSelection2(True)
    if feature is None or error != SW_ADD_MATE_NO_ERROR:
        raise GateError("ADD_PLANE_MATE_FAIL", "datum plane mate failed", {"first": a, "second": b, "plane": plane, "error": error})
    return {"mate_type": SW_MATE_COINCIDENT, "align": SW_ALIGN_ALIGNED, "datum_plane": plane, "first": a, "second": b, "error_status": error}


def add_component_lock_mate(model: Any, assembly: Any, first: Any, second: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    model.ClearSelection2(True)
    manager = selection_manager(model, types, pythoncom)
    data = base.wrap(manager.CreateSelectData(), "ISelectData", types, pythoncom)
    data.Mark = 1
    if not bool(first.Select4(False, data, False)) or not bool(second.Select4(True, data, False)):
        raise GateError("LOCK_COMPONENT_SELECTION_FAIL", "cannot select the two components for a lock mate")
    selected = int(manager.GetSelectedObjectCount2(1))
    # SW2024 normalizes component LOCK mates to swMateAlignCLOSEST (2)
    # regardless of an ALIGNED request.  Pass and audit that native value
    # explicitly so the saved/cold-open ledger remains deterministic.
    returned = assembly.AddMate3(SW_MATE_LOCK, SW_ALIGN_CLOSEST, False, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False, 0)
    feature, outs = base.unpack(returned)
    error = int(outs[0]) if outs else -1
    model.ClearSelection2(True)
    if feature is None or error != SW_ADD_MATE_NO_ERROR or selected != 2:
        raise GateError("ADD_LOCK_MATE_FAIL", "native component lock mate failed", {"error": error, "selected": selected})
    return {"mate_type": SW_MATE_LOCK, "align": SW_ALIGN_CLOSEST, "error_status": error, "selected_count": selected}


def mate_ledger(model: Any, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    feature = base.value(model, "FirstFeature")
    while feature is not None:
        typed = base.wrap(feature, "IFeature", types, pythoncom)
        if str(base.value(typed, "GetTypeName2")) == "MateGroup":
            sub = base.value(typed, "GetFirstSubFeature")
            while sub is not None:
                sf = base.wrap(sub, "IFeature", types, pythoncom)
                mate = base.wrap(base.value(sf, "GetSpecificFeature2"), "IMate2", types, pythoncom)
                count = int(base.value(mate, "GetMateEntityCount"))
                component_paths: List[str] = []
                reference_types: List[int] = []
                for index in range(count):
                    entity = base.wrap(mate.MateEntity(index), "IMateEntity2", types, pythoncom)
                    reference_types.append(int(base.value(entity, "ReferenceType2")))
                    raw_component = base.value(entity, "ReferenceComponent")
                    if raw_component is None:
                        raise GateError("MATE_ENTITY_COMPONENT_MISSING", "mate entity has no reference component", {"index": index})
                    component = base.wrap(raw_component, "IComponent2", types, pythoncom)
                    component_paths.append(str(Path(str(base.value(component, "GetPathName"))).resolve()).replace("\\", "/"))
                row = {
                    "feature_name": str(base.value(sf, "Name")),
                    "feature_error_code": int(base.value(sf, "GetErrorCode")),
                    "suppressed": bool(base.value(sf, "IsSuppressed")),
                    "mate_type": int(base.value(mate, "Type")),
                    "alignment": int(base.value(mate, "Alignment")),
                    "flipped": bool(base.value(mate, "Flipped")),
                    "entity_count": count,
                    "component_paths": sorted(component_paths),
                    "reference_types": sorted(reference_types),
                }
                if row["feature_error_code"] != 0 or row["suppressed"] or count != 2:
                    raise GateError("MATE_SEMANTIC_STATUS_FAIL", "mate is errored, suppressed, or does not have two entities", row)
                rows.append(row)
                sub = base.value(sf, "GetNextSubFeature")
        feature = base.value(typed, "GetNextFeature")
    return rows


def expected_mate_contract(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    paths = {role: str(path.resolve()).replace("\\", "/") for role, path, _fixed, _translation in spec["components"]}
    if spec["kind"] == "adapter":
        contract = [
            (SW_MATE_CONCENTRIC, SW_ALIGN_ALIGNED, paths["STAGE_A"], paths["STAGE_B"]),
            (SW_MATE_COINCIDENT, SW_ALIGN_ANTI, paths["STAGE_A"], paths["STAGE_B"]),
            # Clocking is explicitly derived from the physical relieved pin,
            # not from a direct Stage-A/Stage-B datum-plane shortcut.
            (SW_MATE_COINCIDENT, SW_ALIGN_ALIGNED, paths["DIAMOND_DOWEL"], paths["STAGE_A"]),
            (SW_MATE_LOCK, SW_ALIGN_CLOSEST, paths["DIAMOND_DOWEL"], paths["STAGE_B"]),
        ]
    else:
        primary = SW_MATE_DISTANCE if float(spec["body_carrier_distance_mm"]) > 0.0 else SW_MATE_COINCIDENT
        contract = [
            (primary, SW_ALIGN_ANTI, paths["BODY"], paths["CARRIER"]),
            (SW_MATE_COINCIDENT, SW_ALIGN_ALIGNED, paths["BODY"], paths["CARRIER"]),
            (SW_MATE_COINCIDENT, SW_ALIGN_ALIGNED, paths["BODY"], paths["CARRIER"]),
            (SW_MATE_COINCIDENT, SW_ALIGN_ANTI, paths["CARRIER"], paths["PAD"]),
            (SW_MATE_COINCIDENT, SW_ALIGN_ALIGNED, paths["CARRIER"], paths["PAD"]),
            (SW_MATE_COINCIDENT, SW_ALIGN_ALIGNED, paths["CARRIER"], paths["PAD"]),
        ]
    return sorted(
        ({"mate_type": mate_type, "alignment": alignment, "flipped": False, "component_paths": sorted((first, second))} for mate_type, alignment, first, second in contract),
        key=lambda row: (row["mate_type"], row["component_paths"], row["alignment"], row["flipped"]),
    )


def normalized_mate_contract(ledger: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        ({"mate_type": int(row["mate_type"]), "alignment": int(row["alignment"]), "flipped": bool(row["flipped"]), "component_paths": sorted(row["component_paths"])} for row in ledger),
        key=lambda row: (row["mate_type"], row["component_paths"], row["alignment"], row["flipped"]),
    )


def mate_semantic_signature(ledger: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        (
            {
                "mate_type": int(row["mate_type"]),
                "alignment": int(row["alignment"]),
                "flipped": bool(row["flipped"]),
                "entity_count": int(row["entity_count"]),
                "component_paths": sorted(row["component_paths"]),
                "reference_types": sorted(int(value) for value in row["reference_types"]),
            }
            for row in ledger
        ),
        key=lambda row: (row["mate_type"], row["component_paths"], row["alignment"], row["flipped"], row["reference_types"]),
    )


def component_state(component: Any) -> Dict[str, Any]:
    path = Path(str(base.value(component, "GetPathName"))).resolve()
    transform = [float(value) for value in base.as_list(base.value(base.value(component, "Transform2"), "ArrayData"))]
    if len(transform) != 16:
        raise GateError("COMPONENT_TRANSFORM_SHAPE_FAIL", "component Transform2 is not a 16-value matrix", {"path": str(path), "transform": transform})
    return {
        "path": str(path).replace("\\", "/"),
        "name2": str(base.value(component, "Name2")),
        "fixed": bool(base.value(component, "IsFixed")),
        "suppression": int(base.value(component, "GetSuppression2")),
        "transform": [round(value, 12) for value in transform],
    }


def component_states(components: Iterable[Any]) -> List[Dict[str, Any]]:
    return sorted((component_state(component) for component in components), key=lambda row: row["path"])


def validate_component_states(states: Sequence[Dict[str, Any]], spec: Dict[str, Any]) -> None:
    expected_by_path = {
        str(path.resolve()).replace("\\", "/"): {
            "fixed": bool(fixed),
            "transform": transform_data(translation),
        }
        for _role, path, fixed, translation in spec["components"]
    }
    if {row["path"] for row in states} != set(expected_by_path):
        raise GateError("COMPONENT_STATE_PATH_FAIL", "component-state paths do not match the exact assembly contract", {"states": list(states), "expected_paths": sorted(expected_by_path)})
    for row in states:
        expected = expected_by_path[row["path"]]
        if row["fixed"] != expected["fixed"] or row["suppression"] != 2:
            raise GateError("COMPONENT_STATE_FAIL", "component fixed/suppression state drifted", {"state": row, "expected": expected})
        if any(abs(float(actual) - float(wanted)) > 2.0e-6 for actual, wanted in zip(row["transform"], expected["transform"])):
            raise GateError("COMPONENT_FINAL_TRANSFORM_FAIL", "mate solve moved or flipped a component away from the controlled global geometry", {"state": row, "expected_transform": expected["transform"]})


def save_assembly(model: Any, target: Path) -> Dict[str, Any]:
    if target.exists():
        raise GateError("ASSEMBLY_TARGET_EXISTS", "write-once assembly target exists", {"path": str(target)})
    if not bool(model.ForceRebuild3(True)):
        raise GateError("ASSEMBLY_REBUILD_FAIL", "assembly full rebuild failed")
    returned = model.Extension.SaveAs(str(target), 0, 1, None, 0, 0)
    if not isinstance(returned, tuple) or len(returned) < 3:
        raise GateError("ASSEMBLY_SAVE_SHAPE_FAIL", "assembly SaveAs return shape is invalid", {"returned": repr(returned)})
    ok, outs = base.unpack(returned)
    errors, warnings = int(outs[0]), int(outs[1])
    if not bool(ok) or errors != 0 or warnings != 0 or not target.is_file():
        raise GateError("ASSEMBLY_SAVE_FAIL", "assembly SaveAs failed", {"ok": bool(ok), "errors": errors, "warnings": warnings})
    final = model.Save3(1, 0, 0)
    if not isinstance(final, tuple) or len(final) < 3:
        raise GateError("ASSEMBLY_SAVE3_SHAPE_FAIL", "assembly Save3 return shape is invalid")
    final_ok, final_outs = base.unpack(final)
    if not bool(final_ok) or int(final_outs[0]) != 0 or int(final_outs[1]) != 0:
        raise GateError("ASSEMBLY_SAVE3_FAIL", "assembly Save3 failed", {"ok": bool(final_ok), "errors": int(final_outs[0]), "warnings": int(final_outs[1])})
    return {"path": str(target).replace("\\", "/"), "bytes": target.stat().st_size, "sha256": sha256(target), "errors": errors, "warnings": warnings}


def build_one(sw: Any, types: Any, pythoncom: Any, name: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    raw = sw.NewDocument(str(ASSEMBLY_TEMPLATE), 0, 0.0, 0.0)
    if raw is None:
        raw = base.value(sw, "ActiveDoc")
    if raw is None:
        raise GateError("NEW_ASSEMBLY_FAIL", "cannot create native assembly", {"name": name})
    model = base.wrap(raw, "IModelDoc2", types, pythoncom)
    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    components: Dict[str, Any] = {}
    component_rows = []
    try:
        for role, path, fixed, translation in spec["components"]:
            component = insert_component(sw, model, assembly, path, fixed, translation, types, pythoncom)
            components[role] = component
            component_rows.append({"role": role, "path": str(path).replace("\\", "/"), "fixed": fixed, "translation_m": list(translation), "name2": str(base.value(component, "Name2"))})
        mates = []
        geometry = []
        if spec["kind"] == "adapter":
            stage_b = components["STAGE_B"]
            stage_a = components["STAGE_A"]
            diamond = components["DIAMOND_DOWEL"]
            b_plane, b_plane_fact = planar_face(stage_b, 0.0, types, pythoncom)
            a_plane, a_plane_fact = planar_face(stage_a, 0.0, types, pythoncom)
            b_cyl, b_cyl_fact = cylindrical_face(stage_b, 50.0, (0.0, 0.0), types, pythoncom)
            a_cyl, a_cyl_fact = cylindrical_face(stage_a, 49.8, (0.0, 0.0), types, pythoncom)
            # These unique measured bore faces are evidence that the physical
            # locator participates in both stages.  The Stage-B bore is Ø4.0
            # and the Stage-A bore is Ø4.1 at the same asymmetric [55,0] axis.
            _b_pin_hole, b_pin_hole_fact = cylindrical_face(stage_b, 2.0, (55.0, 0.0), types, pythoncom)
            _a_pin_hole, a_pin_hole_fact = cylindrical_face(stage_a, 2.05, (55.0, 0.0), types, pythoncom)
            mates.append(add_entity_mate(model, assembly, b_cyl, a_cyl, SW_MATE_CONCENTRIC, SW_ALIGN_ALIGNED, 0.0, types, pythoncom))
            mates.append(add_entity_mate(model, assembly, b_plane, a_plane, SW_MATE_COINCIDENT, SW_ALIGN_ANTI, 0.0, types, pythoncom))
            mates.append(add_component_lock_mate(model, assembly, stage_b, diamond, types, pythoncom))
            # Clocking is tied to the physical diamond locator's tangential
            # datum and the Stage-A datum.  There is deliberately no second
            # round-hole concentric mate and no direct A/B TOP-plane shortcut.
            mates.append(add_plane_mate(model, assembly, diamond, stage_a, "TOP"))
            geometry.extend((b_plane_fact, a_plane_fact, b_cyl_fact, a_cyl_fact, b_pin_hole_fact, a_pin_hole_fact))
            geometry.append({
                "locator_global_bbox_mm": [53.5, -2.0, -10.0, 56.5, 2.0, 2.0],
                "stage_b_bore_radius_mm": 2.0,
                "stage_a_bore_radius_mm": 2.05,
                "tangential_half_width_mm": 2.0,
                "radial_half_width_mm": 1.5,
                "stage_b_tangential_clearance_mm": 0.0,
                "stage_b_radial_relief_mm": 0.5,
                "stage_a_tangential_clearance_mm": 0.05,
                "stage_a_radial_relief_mm": 0.55,
                "verdict": "ROUND_PLUS_RELIEVED_DIAMOND_LOCATOR_GEOMETRY_DEFINED",
            })
        else:
            body, carrier, pad = components["BODY"], components["CARRIER"], components["PAD"]
            body_face, body_fact = planar_face(body, float(spec["body_top_mm"]), types, pythoncom)
            carrier_bottom, carrier_bottom_fact = planar_face(carrier, float(spec["carrier_bottom_mm"]), types, pythoncom)
            distance = float(spec["body_carrier_distance_mm"]) / 1000.0
            mate_type = SW_MATE_DISTANCE if distance > 0.0 else SW_MATE_COINCIDENT
            mates.append(add_entity_mate(model, assembly, body_face, carrier_bottom, mate_type, SW_ALIGN_ANTI, distance, types, pythoncom))
            mates.append(add_plane_mate(model, assembly, body, carrier, "RIGHT"))
            mates.append(add_plane_mate(model, assembly, body, carrier, "TOP"))
            carrier_top, carrier_top_fact = planar_face(carrier, float(spec["carrier_top_mm"]), types, pythoncom)
            pad_bottom, pad_bottom_fact = planar_face(pad, float(spec["pad_bottom_mm"]), types, pythoncom)
            mates.append(add_entity_mate(model, assembly, carrier_top, pad_bottom, SW_MATE_COINCIDENT, SW_ALIGN_ANTI, 0.0, types, pythoncom))
            mates.append(add_plane_mate(model, assembly, carrier, pad, "RIGHT"))
            mates.append(add_plane_mate(model, assembly, carrier, pad, "TOP"))
            geometry.extend((body_fact, carrier_bottom_fact, carrier_top_fact, pad_bottom_fact))
        if not bool(model.ForceRebuild3(True)):
            raise GateError("ASSEMBLY_POST_MATE_REBUILD_FAIL", "post-mate rebuild failed", {"name": name})
        ledger = mate_ledger(model, types, pythoncom)
        contract = expected_mate_contract(spec)
        if len(ledger) != len(mates) or normalized_mate_contract(ledger) != contract:
            raise GateError("ASSEMBLY_MATE_CONTRACT_FAIL", "native mate types/endpoints do not match the controlled contract", {"expected": contract, "actual": normalized_mate_contract(ledger), "ledger": ledger})
        states = component_states(components.values())
        validate_component_states(states, spec)
        manager = model.Extension.CustomPropertyManager("")
        for key, value in {
            "AssemblyNumber": f"SEI-MECH-{name}",
            "Revision": "V5-A",
            "RELEASE_SCOPE": "COMPETITION_PROTOTYPE_MANUFACTURING_DEFINITION",
            "MATE_ARCHITECTURE": "ACTUAL_LOAD_FACE_PLUS_DATUM_LOCATION_AND_PHYSICAL_DIAMOND_CLOCKING",
            "RUN_ID": RUN_ID,
            "FLIGHT_QUALIFICATION": "HOLD",
        }.items():
            if int(manager.Add3(key, 30, value, 2)) < 0:
                raise GateError("ASSEMBLY_PROPERTY_FAIL", f"cannot set {key}")
        save = save_assembly(model, Path(spec["target"]))
        own_title = str(base.value(model, "GetTitle"))
        sw.CloseDoc(own_title)
        model = None
        if int(base.value(sw, "GetDocumentCount")) != 0:
            raise GateError("ASSEMBLY_CLOSE_FAIL", "assembly remained open before cold reopen", {"name": name})
        raw_cold = cold = None
        cold_title: Optional[str] = None
        try:
            raw_cold, errors, warnings = unpack_document(sw.OpenDoc6(str(spec["target"]), 2, 3, "", 0, 0), "COLD_OPEN_ASSEMBLY")
            if raw_cold is not None:
                cold = base.wrap(raw_cold, "IModelDoc2", types, pythoncom)
                cold_title = str(base.value(cold, "GetTitle"))
            if raw_cold is None or errors != 0 or warnings != 0:
                raise GateError("COLD_OPEN_ASSEMBLY_FAIL", "assembly did not cold-open cleanly", {"name": name, "errors": errors, "warnings": warnings})
            if not bool(base.value(cold, "IsOpenedReadOnly")) or not bool(cold.ForceRebuild3(True)):
                raise GateError("COLD_ASSEMBLY_REBUILD_FAIL", "cold assembly is not read-only or rebuildable", {"name": name})
            cold_asm = base.wrap(cold, "IAssemblyDoc", types, pythoncom)
            cold_components = [base.wrap(item, "IComponent2", types, pythoncom) for item in base.as_list(cold_asm.GetComponents(True))]
            paths = [Path(str(base.value(item, "GetPathName"))).resolve() for item in cold_components]
            expected_paths = sorted(Path(path).resolve() for _role, path, _fixed, _translation in spec["components"])
            if sorted(paths) != expected_paths:
                raise GateError("COLD_ASSEMBLY_REFERENCE_FAIL", "cold component paths do not match the exact expected multiset", {"name": name, "expected": [str(p) for p in expected_paths], "actual": [str(p) for p in sorted(paths)]})
            reference_hashes = []
            for path in paths:
                if RUN_ROOT.resolve() not in path.parents or not path.is_file():
                    raise GateError("COLD_ASSEMBLY_REFERENCE_OUTSIDE_V5", "cold component is absent or outside the unique V5 root", {"path": str(path)})
                reference_hashes.append({"path": str(path).replace("\\", "/"), "bytes": path.stat().st_size, "sha256": sha256(path)})
            cold_ledger = mate_ledger(cold, types, pythoncom)
            if mate_semantic_signature(cold_ledger) != mate_semantic_signature(ledger):
                raise GateError("COLD_MATE_SEMANTIC_DRIFT", "mate type/alignment/endpoints changed on cold reopen", {"before": ledger, "cold": cold_ledger})
            cold_states = component_states(cold_components)
            validate_component_states(cold_states, spec)
            state_signature = lambda rows: [{key: row[key] for key in ("path", "fixed", "suppression", "transform")} for row in rows]
            if state_signature(cold_states) != state_signature(states):
                raise GateError("COLD_COMPONENT_STATE_DRIFT", "component state/transform changed on cold reopen", {"before": states, "cold": cold_states})
        finally:
            if cold_title:
                try:
                    sw.CloseDoc(cold_title)
                except Exception:
                    pass
            if int(base.value(sw, "GetDocumentCount")) != 0:
                raise GateError("COLD_ASSEMBLY_CLEANUP_FAIL", "cold assembly remained open after owned close", {"name": name, "document_count": int(base.value(sw, "GetDocumentCount"))})
        return {
            "name": name,
            "target": save,
            "components": component_rows,
            "mates_created": mates,
            "mate_ledger": ledger,
            "mate_contract": contract,
            "component_states": states,
            "geometry_selection": geometry,
            "cold_open": {
                "errors": errors,
                "warnings": warnings,
                "component_count": len(paths),
                "component_references": sorted(reference_hashes, key=lambda row: row["path"]),
                "mate_ledger": cold_ledger,
                "component_states": cold_states,
            },
            "interference_closure_claimed": False,
            "interference_next_gate": "LOOP2_NATIVE_INTERFERENCE_AND_EXPECTED_CONTACT_WHITELIST",
            "verdict": "V5_NATIVE_SUBASSEMBLY_MATES_AND_COLD_REOPEN_PASS",
        }
    finally:
        if model is not None:
            try:
                sw.CloseDoc(str(base.value(model, "GetTitle")))
            except Exception:
                pass


def file_fact(path: Path) -> Dict[str, Any]:
    return {
        "path": str(path).replace("\\", "/"),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def checkpoint_binding() -> Dict[str, Any]:
    receipt = load_json(IMPORT_RECEIPT)
    registered = sorted(
        (
            {
                "path": item["target"]["path"],
                "bytes": item["target"]["bytes"],
                "sha256": item["target"]["sha256"],
            }
            for item in receipt.get("native_parts", [])
        ),
        key=lambda row: row["path"],
    )
    digest = hashlib.sha256(json.dumps(registered, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest().upper()
    return {
        "script_sha256": sha256(Path(__file__)),
        "base_helper_sha256": BASE_HELPER_SHA256,
        "import_receipt_sha256": IMPORT_RECEIPT_SHA256,
        "authority_receipt_sha256": AUTHORITY_RECEIPT_SHA256,
        "registered_native_part_count": len(registered),
        "registered_native_part_contract_sha256": digest,
    }


def write_checkpoint(checkpoint: Path, target: Path, item_result: Dict[str, Any], kind: str) -> Dict[str, Any]:
    payload = {
        "schema": "F3R2_V5_LOOP1A_ARTIFACT_CHECKPOINT_V1",
        "timestamp_utc": utc_now(),
        "kind": kind,
        "binding": checkpoint_binding(),
        "target": file_fact(target),
        "result": item_result,
        "verdict": "V5_LOOP1A_ARTIFACT_CHECKPOINT_PASS",
    }
    write_json_once(checkpoint, payload)
    return {"path": str(checkpoint).replace("\\", "/"), "bytes": checkpoint.stat().st_size, "sha256": sha256(checkpoint)}


def load_checkpoint(checkpoint: Path, target: Path, kind: str, accepted_predecessor_scripts: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    if not checkpoint.is_file() or not target.is_file():
        raise GateError("ARTIFACT_CHECKPOINT_PAIR_FAIL", "target/checkpoint pair is incomplete", {"target": str(target), "checkpoint": str(checkpoint)})
    payload = load_json(checkpoint)
    actual_binding = payload.get("binding", {})
    expected_binding = checkpoint_binding()
    binding_without_script = {key: value for key, value in actual_binding.items() if key != "script_sha256"}
    expected_without_script = {key: value for key, value in expected_binding.items() if key != "script_sha256"}
    accepted_scripts = {expected_binding["script_sha256"], *(accepted_predecessor_scripts or ())}
    if (
        payload.get("schema") != "F3R2_V5_LOOP1A_ARTIFACT_CHECKPOINT_V1"
        or payload.get("kind") != kind
        or binding_without_script != expected_without_script
        or actual_binding.get("script_sha256") not in accepted_scripts
        or payload.get("verdict") != "V5_LOOP1A_ARTIFACT_CHECKPOINT_PASS"
        or payload.get("target") != file_fact(target)
        or not isinstance(payload.get("result"), dict)
    ):
        raise GateError("ARTIFACT_CHECKPOINT_VALIDATION_FAIL", "artifact checkpoint is incomplete or does not bind the current target", {"target": str(target), "checkpoint": str(checkpoint)})
    return payload


def target_checkpoint_state(target: Path, checkpoint: Path, kind: str) -> Dict[str, Any]:
    target_exists = target.is_file()
    checkpoint_exists = checkpoint.is_file()
    state = {
        "target": str(target).replace("\\", "/"),
        "checkpoint": str(checkpoint).replace("\\", "/"),
        "target_exists": target_exists,
        "checkpoint_exists": checkpoint_exists,
    }
    if not target_exists and not checkpoint_exists:
        state.update({"status": "PENDING", "pass": True})
        return state
    if target_exists and checkpoint_exists:
        try:
            predecessors = [DIAMOND_CHECKPOINT_PREDECESSOR_SHA256] if kind == "DIAMOND_LOCATOR" else []
            payload = load_checkpoint(checkpoint, target, kind, predecessors)
        except GateError as exc:
            state.update({"status": exc.code, "pass": False, "reason": str(exc)})
        else:
            state.update({"status": "CHECKPOINT_VERIFIED_RESUMABLE", "pass": True, "target_fact": payload["target"], "checkpoint_sha256": sha256(checkpoint)})
        return state
    state.update({"status": "UNPAIRED_PARTIAL_ARTIFACT_HOLD", "pass": False})
    return state


def reverify_existing_diamond(sw: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    payload = load_checkpoint(
        PIN_CHECKPOINT,
        PIN_PATH,
        "DIAMOND_LOCATOR",
        [DIAMOND_CHECKPOINT_PREDECESSOR_SHA256],
    )
    prior = payload["result"]
    if prior.get("verdict") != "V5_DIAMOND_LOCATOR_NATIVE_PASS" or prior.get("path") != str(PIN_PATH).replace("\\", "/"):
        raise GateError("DIAMOND_CHECKPOINT_RESULT_FAIL", "diamond checkpoint result schema/verdict/path is incomplete")
    cold = None
    title: Optional[str] = None
    try:
        cold, opened = base.open_read_only(sw, PIN_PATH, types, pythoncom)
        title = str(base.value(cold, "GetTitle"))
        facts = base.body_facts(cold, types, pythoncom)
        dimensions = sorted((facts["bounding_box_mm"][3] - facts["bounding_box_mm"][0], facts["bounding_box_mm"][4] - facts["bounding_box_mm"][1], facts["bounding_box_mm"][5] - facts["bounding_box_mm"][2]))
        if facts["solid_body_count"] != 1 or any(abs(actual - expected) > 0.02 for actual, expected in zip(dimensions, (3.0, 4.0, 12.0))):
            raise GateError("DIAMOND_RESUME_GEOMETRY_FAIL", "existing diamond locator failed independent cold geometry verification", {"facts": facts, "dimensions_mm": dimensions})
    finally:
        if title:
            sw.CloseDoc(title)
    if int(base.value(sw, "GetDocumentCount")) != 0:
        raise GateError("DIAMOND_RESUME_CLEANUP_FAIL", "diamond resume verification left a document open")
    result = dict(prior)
    result["resumed_from_checkpoint"] = True
    result["resume_reverification"] = {
        "timestamp_utc": utc_now(),
        "checkpoint_sha256": sha256(PIN_CHECKPOINT),
        "target": file_fact(PIN_PATH),
        "cold_open": opened,
        "cold_facts": facts,
        "verdict": "V5_DIAMOND_LOCATOR_RESUME_REVERIFIED_PASS",
    }
    return result


def static_audit() -> Dict[str, Any]:
    inputs = validate_inputs()
    targets = [target_checkpoint_state(PIN_PATH, PIN_CHECKPOINT, "DIAMOND_LOCATOR")]
    targets.extend(target_checkpoint_state(Path(spec["target"]), ASSEMBLY_CHECKPOINTS[name], name) for name, spec in ASSEMBLIES.items())
    script_copy_ok = not SCRIPT_COPY.exists() or (SCRIPT_COPY.is_file() and sha256(SCRIPT_COPY) == sha256(Path(__file__)))
    packaging = {
        "final_receipt_exists": FINAL_RECEIPT.exists(),
        "script_copy_exists": SCRIPT_COPY.exists(),
        "script_copy_matches_current": script_copy_ok,
        "final_manifest_exists": FINAL_MANIFEST.exists(),
    }
    authorized = all(row["pass"] for row in targets) and not FINAL_RECEIPT.exists() and script_copy_ok and not FINAL_MANIFEST.exists()
    return {
        "schema": "F3R2_V5_LOOP1A_STATIC_AUDIT_V2",
        "timestamp_utc": utc_now(),
        "run_root": str(RUN_ROOT).replace("\\", "/"),
        "inputs": inputs,
        "targets": targets,
        "packaging": packaging,
        "execution_authorized": authorized,
        "verdict": "V5_LOOP1A_STATIC_PASS_OR_VERIFIED_RESUME" if authorized else "V5_LOOP1A_STATIC_HOLD_OR_COMPLETE",
    }


def execute() -> int:
    result: Dict[str, Any] = {
        "schema": "F3R2_V5_LOOP1A_SUBASSEMBLY_RECEIPT_V2",
        "timestamp_start_utc": utc_now(),
        "run_root": str(RUN_ROOT).replace("\\", "/"),
        "subassemblies": [],
        "artifact_checkpoints": [],
    }
    sw = types = pythoncom = None
    try:
        audit = static_audit()
        if not audit["execution_authorized"]:
            raise GateError("LOOP1A_STATIC_EXECUTION_HOLD", "static target/checkpoint or packaging state is not executable", {"audit": audit})
        result["input_audit"] = audit
        result["protected_pre"] = base.audit_protected()
        result["native_parts_pre"] = audit_registered_parts(audit["inputs"]["registered_parts"])
        import_receipt = load_json(IMPORT_RECEIPT)
        qualified_memory = [float(value) for value in import_receipt.get("memory_samples_gib", [])]
        if len(qualified_memory) != 10 or not all(value >= 6.0 for value in qualified_memory):
            raise GateError("QUALIFIED_G0_MEMORY_EVIDENCE_FAIL", "fixed Loop-1 receipt does not preserve the ten-sample >=6 GiB Session-B resource gate", {"samples_gib": qualified_memory})
        result["g0_resource_qualification"] = {
            "scope": "SESSION_B_G0_AND_NEUTRAL_IMPORT_QUALIFICATION_ALREADY_PASSED_DO_NOT_RERUN_G0",
            "memory_samples_gib": qualified_memory,
            "minimum_gib": min(qualified_memory),
            "current_available_gib_observation": round(base.available_gib(), 6),
        }
        sw, types, pythoncom, session = base.attach_empty_session()
        result["solidworks"] = session
        import_session = import_receipt.get("solidworks", {})
        if import_session and int(import_session.get("pid", -1)) != int(session["pid"]):
            raise GateError("SOLIDWORKS_SESSION_PID_DRIFT", "Loop1A is not attached to the same qualified Session-B process used for neutral import", {"import_session": import_session, "current_session": session})
        if PIN_PATH.exists():
            pin_result = reverify_existing_diamond(sw, types, pythoncom)
        else:
            pin_result = make_diamond_pin(sw, types, pythoncom)
            result["artifact_checkpoints"].append(write_checkpoint(PIN_CHECKPOINT, PIN_PATH, pin_result, "DIAMOND_LOCATOR"))
        result["diamond_locator"] = pin_result
        for name, spec in ASSEMBLIES.items():
            target = Path(spec["target"])
            checkpoint = ASSEMBLY_CHECKPOINTS[name]
            if target.exists():
                payload = load_checkpoint(checkpoint, target, name)
                item = dict(payload["result"])
                item["resumed_from_checkpoint"] = True
            else:
                item = build_one(sw, types, pythoncom, name, spec)
                result["artifact_checkpoints"].append(write_checkpoint(checkpoint, target, item, name))
            result["subassemblies"].append(item)
        result["native_parts_post"] = audit_registered_parts(audit["inputs"]["registered_parts"])
        if result["native_parts_pre"] != result["native_parts_post"]:
            raise GateError("V5_NATIVE_PART_POST_DRIFT", "one or more imported V5 native parts changed during assembly build")
        result["protected_post"] = base.audit_protected()
        if result["protected_pre"] != result["protected_post"]:
            raise GateError("PROTECTED_POST_DRIFT", "protected asset hashes changed")
        if int(base.value(sw, "GetDocumentCount")) != 0 or base.value(sw, "ActiveDoc") is not None:
            raise GateError("POST_BUILD_SESSION_NOT_EMPTY", "documents remain open after Loop1A")
        # Package first.  The formal PASS receipt is the last write so a copy
        # or manifest failure can never coexist with a stale PASS marker.
        if SCRIPT_COPY.exists():
            if sha256(SCRIPT_COPY) != sha256(Path(__file__)):
                raise GateError("SCRIPT_COPY_DRIFT", "existing Loop1A script copy does not match the executing script")
        else:
            shutil.copy2(Path(__file__).resolve(), SCRIPT_COPY)
        lines = []
        manifest_inputs = [
            PIN_PATH,
            PIN_CHECKPOINT,
            *(Path(spec["target"]) for spec in ASSEMBLIES.values()),
            *(ASSEMBLY_CHECKPOINTS[name] for name in ASSEMBLIES),
            SCRIPT_COPY,
            IMPORT_RECEIPT,
            AUTHORITY_RECEIPT,
        ]
        for path in manifest_inputs:
            lines.append(f"{sha256(path)}  {path.stat().st_size}  {path.relative_to(RUN_ROOT).as_posix()}")
        with FINAL_MANIFEST.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write("\n".join(sorted(lines)) + "\n")
        result.update({
            "timestamp_end_utc": utc_now(),
            "verdict": "V5_LOOP1A_ADAPTER_SUPPORT_SUBASSEMBLIES_PASS",
            "native_part_created": 1,
            "native_subassemblies_created": 4,
            "manifest": file_fact(FINAL_MANIFEST),
            "interference_closure_claimed": False,
            "remaining_loop1": ["WING_ROOT_TRUE_HINGE_SUBASSEMBLIES", "ARM_HDRM_FUNCTIONAL_SUBASSEMBLY", "CAMERA_HARNESS_NATIVE_INTERFACE", "GRIPPER_SAVE_BODIES_AND_PRISMATIC_MATES", "TOP_ASSEMBLY"],
        })
        write_json_once(FINAL_RECEIPT, result)
        print(json.dumps({"verdict": result["verdict"], "receipt": str(FINAL_RECEIPT).replace("\\", "/"), "receipt_sha256": sha256(FINAL_RECEIPT), "manifest_sha256": sha256(FINAL_MANIFEST), "native_subassemblies": 4, "solidworks_document_count": int(base.value(sw, "GetDocumentCount"))}, ensure_ascii=False, indent=2))
        return 0
    except (GateError, base.GateError) as exc:
        code = getattr(exc, "code", "LOOP1A_GATE_FAIL")
        detail = getattr(exc, "detail", {})
        result.update({"verdict": code, "reason": str(exc), "detail": detail, "traceback": traceback.format_exc(), "timestamp_end_utc": utc_now()})
        failure = RUN_ROOT / f"13_validation/V5_LOOP1A_FAIL_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')}.json"
        try:
            write_json_once(failure, result)
        except Exception:
            pass
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 3
    except Exception as exc:
        result.update({
            "verdict": "V5_LOOP1A_UNEXPECTED_EXCEPTION",
            "reason": repr(exc),
            "traceback": traceback.format_exc(),
            "timestamp_end_utc": utc_now(),
            "partial_artifacts": [
                file_fact(path)
                for path in [PIN_PATH, *(Path(spec["target"]) for spec in ASSEMBLIES.values())]
                if path.is_file()
            ],
        })
        if sw is not None:
            try:
                result["solidworks_document_count_on_failure"] = int(base.value(sw, "GetDocumentCount"))
            except Exception:
                pass
        failure = RUN_ROOT / f"13_validation/V5_LOOP1A_FAIL_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')}.json"
        try:
            write_json_once(failure, result)
        except Exception:
            pass
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 4
    finally:
        sw = None
        if pythoncom is not None:
            pythoncom.CoUninitialize()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("audit", "execute"))
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.command == "audit":
        print(json.dumps(static_audit(), ensure_ascii=False, indent=2))
        return 0
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())
