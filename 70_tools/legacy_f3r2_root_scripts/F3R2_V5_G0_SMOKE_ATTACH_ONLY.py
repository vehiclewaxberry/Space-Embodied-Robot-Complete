#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""G0 native-part smoke test for the F3R2 V5 mechanical release.

The program attaches to an already-running SOLIDWORKS 2024 session, creates
one temporary 20 x 20 x 10 mm native part in a new exclusive smoke-run
directory, saves it, closes only that document, and emits an auditable receipt.

Safety invariants:

* GetActiveObject only: this program cannot start or terminate SOLIDWORKS.
* It never changes Visible/UserControl and requires an initially empty session.
* It never creates a V5 release directory and never writes below V4/F3R1/F3R2.
* It refuses to write unless memory, manifest, templates, and protected hashes
  all pass immediately before the native document is created.
* API modelling dimensions are metres.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
ENGINEERING = ROOT / "20_engineering"
MANIFEST = (
    ENGINEERING
    / "F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809"
    / "99_tools"
    / "MFINAL_SOLIDWORKS_INPUT_MANIFEST.json"
)
MANIFEST_SHA256 = "A92AC96C9CD150374B566956E7383F8CCBE0625A41C5C833A3FAE5961913DE92"
PART_TEMPLATE = Path(r"F:\Windows_profile\solidworks\DocumentTemplates\零件.PRTDOT")
PART_TEMPLATE_SHA256 = "4353B758099AB8F6652F4764B47D923613EBEE042CBED26BB3314685DB0B2A5D"
SOLIDWORKS_PROG_ID = "SldWorks.Application"
EXPECTED_MAJOR = 32
MIN_AVAILABLE_GIB = 6.0
RUN_ID_RE = re.compile(r"^_MFINAL_G0_SMOKE_20260809T\d{6}_[A-Z0-9]{4,12}$")

PROTECTED = (
    {
        "name": "accepted_b601_urdf",
        "path": ENGINEERING / "cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
        "raw_sha256": "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164",
        "lf_sha256": "408147DDC9CC0BBA0FACBF864C559A54D1712262703BA41251514A4303B5A3A4",
    },
    {
        "name": "mass_inertia_budget",
        "path": ENGINEERING / "stage1_spacecraft_layout/04_mass_inertia_budget/mass_inertia_budget_v1.csv",
        "raw_sha256": "073C802527E35C9495188EEFD5D8BA51F524D326142CF2AB31E436BAD0899392",
    },
    {
        "name": "v2_2_native_donor_top",
        "path": ENGINEERING / "cad/Space_Embodied_Robot_CAD_V2_2_NATIVE/Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM",
        "raw_sha256": "30C09B50A0D2967EC1F48050CAAC34D12A43565C44978D54E3785595202DEF7A",
    },
    {
        "name": "b51_articulated_arm_donor",
        "path": ENGINEERING / "cad/B5_1_B601_interface_closure_candidate/03_CAD/native_articulated/B51_ARTICULATED_20260728T008/assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM",
        "raw_sha256": "603B87BBD4398FDDB3F732FFBFA7E1C080ED91ED6E0A026D56CBDCBA08DE2E22",
    },
    {
        "name": "f3r1_frozen_top",
        "path": ENGINEERING / "F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/03_native_cad/F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V3_CONFIGURED.SLDASM",
        "raw_sha256": "19D85E9C703BEC107396AE84DAB7B12DE5722434FC7D5474B3A5A144A1B590D0",
    },
    {
        "name": "f3r2_frozen_top",
        "path": ENGINEERING / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.SLDASM",
        "raw_sha256": "19D85E9C703BEC107396AE84DAB7B12DE5722434FC7D5474B3A5A144A1B590D0",
    },
)


class GateError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


class MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path, *, normalize_lf: bool = False) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        if normalize_lf:
            digest.update(stream.read().replace(b"\r\n", b"\n"))
        else:
            for block in iter(lambda: stream.read(1 << 20), b""):
                digest.update(block)
    return digest.hexdigest().upper()


def available_memory_gib() -> float:
    status = MemoryStatusEx()
    status.dwLength = ctypes.sizeof(MemoryStatusEx)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise GateError("MEMORY_QUERY_FAILED", "GlobalMemoryStatusEx returned false")
    return status.ullAvailPhys / (1024.0 ** 3)


def memory_gate(samples: int = 10, interval_seconds: float = 0.25) -> List[float]:
    values: List[float] = []
    for index in range(samples):
        values.append(round(available_memory_gib(), 6))
        if index + 1 < samples:
            time.sleep(interval_seconds)
    if not all(value >= MIN_AVAILABLE_GIB for value in values):
        raise GateError(
            "RESOURCE_GATE_HOLD",
            "every immediate pre-write sample must be at least 6 GiB",
            {"samples_gib": values, "minimum_gib": MIN_AVAILABLE_GIB},
        )
    return values


def validate_manifest() -> Dict[str, Any]:
    if not MANIFEST.is_file() or sha256(MANIFEST) != MANIFEST_SHA256:
        raise GateError("MANIFEST_IDENTITY_FAIL", "V4 input manifest identity changed")
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows: List[Dict[str, Any]] = []
    for section in ("inputs", "templates"):
        entries = raw.get(section)
        if not isinstance(entries, list):
            raise GateError("MANIFEST_FORMAT_FAIL", f"{section} is not a list")
        for entry in entries:
            path = Path(entry["path"])
            exists = path.is_file()
            actual_bytes = path.stat().st_size if exists else None
            actual_sha = sha256(path) if exists else None
            passed = (
                exists
                and actual_bytes == int(entry["bytes"])
                and actual_sha == str(entry["sha256"]).upper()
            )
            rows.append(
                {
                    "section": section,
                    "role": entry.get("role"),
                    "path": str(path).replace("\\", "/"),
                    "bytes": actual_bytes,
                    "sha256": actual_sha,
                    "pass": passed,
                }
            )
    if len(rows) != 26 or not all(row["pass"] for row in rows):
        raise GateError(
            "INPUT_OR_TEMPLATE_VALIDATION_FAIL",
            "all 22 inputs and 4 templates must match",
            {"count": len(rows), "failures": [row for row in rows if not row["pass"]]},
        )
    template_row = next(
        (row for row in rows if os.path.normcase(row["path"]) == os.path.normcase(str(PART_TEMPLATE).replace("\\", "/"))),
        None,
    )
    if template_row is None or template_row["sha256"] != PART_TEMPLATE_SHA256:
        raise GateError("PART_TEMPLATE_FAIL", "declared part template is not the frozen template")
    return {"manifest_sha256": MANIFEST_SHA256, "validated_items": len(rows)}


def validate_protected() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in PROTECTED:
        path: Path = item["path"]
        exists = path.is_file()
        raw = sha256(path) if exists else None
        lf = sha256(path, normalize_lf=True) if exists and item.get("lf_sha256") else None
        passed = exists and raw == item["raw_sha256"] and (
            item.get("lf_sha256") is None or lf == item["lf_sha256"]
        )
        rows.append(
            {
                "name": item["name"],
                "path": str(path).replace("\\", "/"),
                "bytes": path.stat().st_size if exists else None,
                "raw_sha256": raw,
                "lf_sha256": lf,
                "pass": passed,
            }
        )
    if not all(row["pass"] for row in rows):
        raise GateError(
            "PROTECTED_PRE_HASH_FAIL",
            "one or more protected PRE identities changed",
            {"failures": [row for row in rows if not row["pass"]]},
        )
    return rows


def as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (tuple, list)):
        return list(value)
    return [value]


def com_value(obj: Any, name: str, *args: Any) -> Any:
    """Read a COM member exposed either as a method or as a value property."""
    member = getattr(obj, name)
    return member(*args) if callable(member) else member


def wrap_interface(obj: Any, interface_name: str, sw_types: Any, pythoncom: Any) -> Any:
    """Wrap an existing SOLIDWORKS object with a cached makepy interface."""
    klass = getattr(sw_types, interface_name)
    ole = obj._oleobj_.QueryInterface(klass.CLSID, pythoncom.IID_IDispatch)
    return klass(ole)


def select_front_plane(
    model: Any,
    pythoncom: Any,
    variant_type: Any,
    sw_types: Any,
) -> str:
    # Some localized templates expose mojibake display names through COM.  The
    # first RefPlane in a normal part template is the front plane; selecting the
    # feature object avoids any dependency on the UI language or code page.
    raw_feature = com_value(model, "FirstFeature")
    feature = (
        wrap_interface(raw_feature, "IFeature", sw_types, pythoncom)
        if raw_feature is not None
        else None
    )
    visited = 0
    while feature is not None and visited < 512:
        visited += 1
        try:
            type_name = str(com_value(feature, "GetTypeName2"))
            feature_name = str(com_value(feature, "Name"))
        except Exception:
            type_name = ""
            feature_name = ""
        if type_name == "RefPlane":
            model.ClearSelection2(True)
            if bool(com_value(feature, "Select2", False, 0)):
                return f"feature_tree:{feature_name}:RefPlane"
        try:
            raw_feature = com_value(feature, "GetNextFeature")
            feature = (
                wrap_interface(raw_feature, "IFeature", sw_types, pythoncom)
                if raw_feature is not None
                else None
            )
        except Exception:
            feature = None
    raise GateError(
        "FRONT_PLANE_SELECTION_FAIL",
        "localized names failed and no selectable RefPlane was found",
        {"feature_nodes_visited": visited},
    )


def select_sketch(model: Any, names: Iterable[str], pythoncom: Any, variant_type: Any) -> str:
    for name in names:
        model.ClearSelection2(True)
        if bool(
            model.Extension.SelectByID2(
                name, "SKETCH", 0.0, 0.0, 0.0, False, 0, None, 0
            )
        ):
            return name
    raise GateError("SKETCH_SELECTION_FAIL", "created sketch could not be selected")


def build_native_part(
    sw: Any,
    run_dir: Path,
    pythoncom: Any,
    variant_type: Any,
    sw_types: Any,
) -> Dict[str, Any]:
    output = run_dir / "G0_SMOKE_20X20X10.SLDPRT"
    if output.exists():
        raise GateError("SMOKE_OUTPUT_ALREADY_EXISTS", str(output))

    model = None
    own_title: Optional[str] = None
    closed = False
    try:
        model = sw.NewDocument(str(PART_TEMPLATE), 0, 0.0, 0.0)
        if model is None:
            for _ in range(20):
                model = sw.ActiveDoc
                if model is not None:
                    break
                time.sleep(0.25)
        if model is None:
            raise GateError("NEW_DOCUMENT_FAIL", "NewDocument returned null")
        own_title = str(com_value(model, "GetTitle"))
        model = wrap_interface(model, "IModelDoc2", sw_types, pythoncom)
        if int(com_value(model, "GetType")) != 1:
            raise GateError("NEW_DOCUMENT_TYPE_FAIL", "new document is not a native part")

        plane = select_front_plane(model, pythoncom, variant_type, sw_types)
        model.SketchManager.InsertSketch(True)
        rectangle = as_list(
            model.SketchManager.CreateCenterRectangle(
                0.0, 0.0, 0.0, 0.010, 0.010, 0.0
            )
        )
        # SOLIDWORKS returns four perimeter lines plus two diagonal construction
        # lines for a center rectangle.
        if len(rectangle) != 6 or any(segment is None for segment in rectangle):
            raise GateError(
                "RECTANGLE_CREATION_FAIL",
                "CreateCenterRectangle did not return six expected sketch segments",
                {"segment_count": len(rectangle)},
            )

        sketch_name: Optional[str] = None
        sketch_feature = None
        try:
            sketch = com_value(model, "GetActiveSketch2")
            raw_sketch_feature = (
                com_value(sketch, "GetFeature") if sketch is not None else None
            )
            sketch_feature = (
                wrap_interface(
                    raw_sketch_feature, "IFeature", sw_types, pythoncom
                )
                if raw_sketch_feature is not None
                else None
            )
            sketch_name = (
                str(com_value(sketch_feature, "Name"))
                if sketch_feature is not None
                else None
            )
        except Exception:
            sketch_name = None
            sketch_feature = None
        model.SketchManager.InsertSketch(True)
        model.ClearSelection2(True)
        if sketch_feature is not None and bool(
            com_value(sketch_feature, "Select2", False, 0)
        ):
            selected_sketch = f"feature_object:{sketch_name}"
        else:
            selected_sketch = select_sketch(
                model,
                [name for name in (sketch_name, "草图1", "Sketch1") if name],
                pythoncom,
                variant_type,
            )
        boss = model.FeatureManager.FeatureExtrusion3(
            True, False, True, 0, 0, 0.010, 0.0,
            False, False, False, False, 0.0, 0.0,
            False, False, False, False, True, False, True,
            0, 0.0, False,
        )
        if boss is None:
            raise GateError("EXTRUSION_FAIL", "FeatureExtrusion3 returned null")

        rebuild_ok = bool(com_value(model, "EditRebuild3"))
        if not rebuild_ok:
            raise GateError("REBUILD_FAIL", "EditRebuild3 returned false")
        part = wrap_interface(model, "IPartDoc", sw_types, pythoncom)
        bodies = as_list(part.GetBodies2(0, False))
        if len(bodies) != 1:
            raise GateError("SOLID_BODY_COUNT_FAIL", "expected exactly one solid body", {"count": len(bodies)})
        body = bodies[0]
        if hasattr(body, "IsSolidBody") and not bool(com_value(body, "IsSolidBody")):
            raise GateError("BODY_NOT_SOLID_FAIL", "created body is not solid")
        box = [float(value) for value in as_list(com_value(body, "GetBodyBox"))]
        if len(box) != 6:
            raise GateError("BODY_BOX_FAIL", "GetBodyBox did not return six values")
        dimensions = sorted(
            [abs(box[3] - box[0]), abs(box[4] - box[1]), abs(box[5] - box[2])]
        )
        expected = [0.010, 0.020, 0.020]
        if any(abs(actual - target) > 0.00005 for actual, target in zip(dimensions, expected)):
            raise GateError(
                "BODY_DIMENSION_FAIL",
                "native body bounding box does not match 20 x 20 x 10 mm",
                {"dimensions_m_sorted": dimensions},
            )

        save_return = model.Extension.SaveAs(
            str(output), 0, 1, None, 0, 0
        )
        if not isinstance(save_return, tuple) or len(save_return) < 3:
            raise GateError(
                "NATIVE_SAVE_OUTPUT_SHAPE_FAIL",
                "typed SaveAs did not return retval/errors/warnings",
                {"return_repr": repr(save_return)},
            )
        saved = bool(save_return[0])
        save_errors = int(save_return[1])
        save_warnings = int(save_return[2])
        if not saved or save_errors != 0 or save_warnings != 0:
            raise GateError(
                "NATIVE_SAVE_FAIL",
                "SaveAs did not return a clean success",
                {
                    "success": saved,
                    "errors": save_errors,
                    "warnings": save_warnings,
                },
            )
        own_title = str(com_value(model, "GetTitle"))
        if not output.is_file() or output.stat().st_size <= 0:
            raise GateError("NATIVE_OUTPUT_MISSING", "saved native part is absent or empty")

        rectangle_segment_count = len(rectangle)
        solid_body_count = len(bodies)
        feature_count = int(com_value(model, "GetFeatureCount"))
        rectangle = []
        body = None
        bodies = []
        part = None
        boss = None
        sw.CloseDoc(own_title)
        closed = True
        model = None
        time.sleep(0.5)
        if int(com_value(sw, "GetDocumentCount")) != 0 or sw.ActiveDoc is not None:
            raise GateError("SESSION_NOT_EMPTY_AFTER_CLOSE", "smoke document did not close cleanly")

        return {
            "plane_selected": plane,
            "sketch_selected": selected_sketch,
            "rectangle_segments": rectangle_segment_count,
            "feature_count": feature_count,
            "solid_body_count": solid_body_count,
            "dimensions_m_sorted": dimensions,
            "output": str(output).replace("\\", "/"),
            "output_bytes": output.stat().st_size,
            "output_sha256": sha256(output),
            "save_errors": save_errors,
            "save_warnings": save_warnings,
            "document_closed": closed,
        }
    finally:
        if model is not None and not closed and own_title:
            try:
                sw.CloseDoc(str(com_value(model, "GetTitle") or own_title))
            except Exception:
                pass


def write_receipt_exclusive(path: Path, payload: Dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Attach-only SOLIDWORKS G0 native smoke test")
    parser.add_argument("run_id", help="exclusive _MFINAL_G0_SMOKE_... directory name")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not RUN_ID_RE.fullmatch(args.run_id):
        raise SystemExit("run_id does not match the controlled G0 smoke naming rule")
    run_dir = (ENGINEERING / args.run_id).resolve(strict=False)
    if run_dir.parent != ENGINEERING.resolve() or run_dir.exists():
        raise SystemExit("run directory must be absent and directly under 20_engineering")

    base: Dict[str, Any] = {
        "schema": "F3R2_V5_G0_SMOKE_SESSION_A_V1",
        "timestamp_utc": utc_now(),
        "run_id": args.run_id,
        "run_dir": str(run_dir).replace("\\", "/"),
        "safety": {
            "attach_only": True,
            "script_start_solidworks": False,
            "script_exit_solidworks": False,
            "changes_visible_or_user_control": False,
            "v5_release_created": False,
        },
    }
    run_created = False
    pythoncom = None
    sw = None
    try:
        base["manifest"] = validate_manifest()
        base["protected_pre"] = validate_protected()
        base["memory_samples_gib"] = memory_gate()

        import pythoncom as _pythoncom  # type: ignore
        import win32com.client  # type: ignore
        from win32com.client import VARIANT, gencache  # type: ignore

        pythoncom = _pythoncom
        pythoncom.CoInitialize()
        try:
            sw = win32com.client.GetActiveObject(SOLIDWORKS_PROG_ID)
        except Exception as exc:
            raise GateError("ATTACH_REQUIRED", "no manually started SOLIDWORKS session", {"exception": repr(exc)}) from exc
        revision = str(com_value(sw, "RevisionNumber"))
        major = int(revision.split(".", 1)[0])
        doc_count = int(com_value(sw, "GetDocumentCount"))
        active_is_null = sw.ActiveDoc is None
        base["solidworks_pre"] = {
            "revision": revision,
            "major": major,
            "expected_major": EXPECTED_MAJOR,
            "doc_count": doc_count,
            "active_doc_is_null": active_is_null,
        }
        if major != EXPECTED_MAJOR or doc_count != 0 or not active_is_null:
            raise GateError("SOLIDWORKS_SESSION_GATE_FAIL", "version 32 and an empty session are required")
        sw_types = gencache.GetModuleForTypelib(
            "{83A33D31-27C5-11CE-BFD4-00400513BB57}", 0, 32, 0
        )

        # Final memory measurement occurs immediately before the first write.
        base["memory_final_snapshot_gib"] = round(available_memory_gib(), 6)
        if base["memory_final_snapshot_gib"] < MIN_AVAILABLE_GIB:
            raise GateError("RESOURCE_GATE_HOLD", "memory fell below 6 GiB immediately before write")

        run_dir.mkdir(exist_ok=False)
        run_created = True
        base["native_part"] = build_native_part(
            sw, run_dir, pythoncom, VARIANT, sw_types
        )
        base["protected_post"] = validate_protected()
        base["solidworks_post"] = {
            "doc_count": int(com_value(sw, "GetDocumentCount")),
            "active_doc_is_null": sw.ActiveDoc is None,
        }
        base["verdict"] = "G0_SMOKE_SESSION_A_PASS_AWAITING_SESSION_B"
        base["next_required_action"] = "USER_CLOSE_AND_RESTART_SOLIDWORKS_FOR_COLD_REOPEN_SESSION_B"
        receipt = run_dir / "G0_SMOKE_SESSION_A_RECEIPT.json"
        write_receipt_exclusive(receipt, base)
        print(json.dumps({**base, "receipt": str(receipt).replace("\\", "/")}, ensure_ascii=False, indent=2))
        return 0
    except GateError as exc:
        base.update({"verdict": exc.code, "reason": str(exc), "detail": exc.detail})
        if run_created:
            try:
                write_receipt_exclusive(run_dir / "G0_SMOKE_SESSION_A_FAIL.json", base)
            except Exception as receipt_exc:
                base["receipt_error"] = repr(receipt_exc)
        print(json.dumps(base, ensure_ascii=False, indent=2), file=sys.stderr)
        return 3
    except Exception as exc:
        base.update(
            {
                "verdict": "UNEXPECTED_SMOKE_EXCEPTION",
                "exception_type": type(exc).__name__,
                "reason": repr(exc),
                "traceback": traceback.format_exc(),
            }
        )
        if run_created:
            try:
                write_receipt_exclusive(run_dir / "G0_SMOKE_SESSION_A_FAIL.json", base)
            except Exception as receipt_exc:
                base["receipt_error"] = repr(receipt_exc)
        print(json.dumps(base, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    finally:
        sw = None
        if pythoncom is not None:
            pythoncom.CoUninitialize()


if __name__ == "__main__":
    raise SystemExit(main())
