# -*- coding: utf-8 -*-
"""Create and cold-verify native SolidWorks M3R adapter documents.

Only small, newly generated F3R2 STEP files are opened. The protected baseline,
donors, F3R1 and accepted URDF are never opened for write.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import pythoncom
import win32com.client
from win32com.client import VARIANT


F3R2 = Path(
    "F:/China Graduate Future Flight Vehicle Innovation Competition/"
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
)
ROOT = F3R2 / "03_native_cad/M3_interface_authority"
CAD = ROOT / "cad"
RECEIPT = ROOT / "M3R_SOLIDWORKS_NATIVE_RECEIPT.json"
TEMPLATE_ASM = Path("F:/Windows_profile/solidworks/DocumentTemplates/装配体.asmdot")

RING = "B601_BASE_INTERFACE_RING_F3R2"
BODY = "B601_LOAD_SPREADING_ADAPTER_F3R2"
ASM = "B601_BASE_ADAPTER_F3R2"

SW_DOC_PART = 1
SW_DOC_ASSEMBLY = 2
SW_OPEN_SILENT = 1
SW_OPEN_READONLY = 2
SW_SAVE_SILENT = 1


def out_i4():
    return VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest().upper()


def save_as(model, path: Path):
    errors, warnings = out_i4(), out_i4()
    ok = bool(model.Extension.SaveAs(
        str(path), 0, SW_SAVE_SILENT, None, errors, warnings))
    return {"ok": ok, "errors": int(errors.value),
            "warnings": int(warnings.value), "exists": path.is_file()}


def open_doc(sw, path: Path, doc_type: int, options=SW_OPEN_SILENT):
    errors, warnings = out_i4(), out_i4()
    model = sw.OpenDoc6(str(path), doc_type, options, "", errors, warnings)
    if model is None:
        raise RuntimeError(
            f"OpenDoc6 failed {path}; errors={errors.value} warnings={warnings.value}"
        )
    return model, int(errors.value), int(warnings.value)


def set_props(model, part_number, description):
    props = model.Extension.CustomPropertyManager("")
    values = {
        "PartNumber": part_number,
        "Description": description,
        "MaterialSpecification": "AL6061-T6",
        "ReleaseScope": "COMPETITION_PROTOTYPE_MANUFACTURING_CANDIDATE",
        "Qualification": "NOT_FLIGHT_RELEASED; FORMAL_FASTENER_MOS_HOLD",
        "Revision": "A",
    }
    for key, value in values.items():
        props.Add3(key, 30, value, 1)


def close_doc(sw, model):
    title = model.GetTitle()
    sw.CloseDoc(title)


def fix_component(model, asm_doc, comp):
    try:
        model.ClearSelection2(True)
        comp.Select4(False, None, False)
        asm_doc.FixComponent()
        model.ClearSelection2(True)
        return True
    except Exception:
        return False


def add_component(asm_doc, path: Path):
    try:
        return asm_doc.AddComponent5(str(path), 0, "", False, "", 0.0, 0.0, 0.0)
    except Exception:
        return asm_doc.AddComponent4(str(path), "", 0.0, 0.0, 0.0)


def native_interference(asm_doc):
    mgr = getattr(asm_doc, "InterferenceDetectionManager", None)
    if mgr is None:
        mgr = getattr(asm_doc, "InterferenceDetection", None)
    if mgr is None:
        return {"available": False, "error": "manager unavailable"}
    for key, value in {
        "TreatCoincidenceAsInterference": False,
        "TreatSubAssembliesAsComponents": False,
        "IncludeMultibodyPartInterferences": True,
        "MakeInterferingPartsTransparent": False,
        "ShowIgnoredInterferences": False,
        "UseSelectedComponents": False,
    }.items():
        try:
            setattr(mgr, key, value)
        except Exception:
            pass
    try:
        items = list(mgr.GetInterferences() or [])
        volumes = []
        for item in items:
            try:
                volumes.append(float(item.Volume) * 1.0e9)
            except Exception:
                volumes.append(None)
        result = {
            "available": True,
            "treat_coincidence_as_interference": False,
            "count": len(items),
            "volumes_mm3": volumes,
            "total_volume_mm3": sum(v for v in volumes if v is not None),
        }
        try:
            mgr.Done()
        except Exception:
            pass
        return result
    except Exception as exc:
        return {"available": True, "error": str(exc)}


def main():
    pythoncom.CoInitialize()
    report = {
        "schema": "M3R_SOLIDWORKS_NATIVE_RECEIPT_V1",
        "solidworks_version_expected": "2024 SP05",
        "active_root": str(F3R2).replace("\\", "/"),
        "writes_confined_to": str(ROOT).replace("\\", "/"),
    }
    launched = False
    sw = None
    try:
        try:
            sw = win32com.client.GetActiveObject("SldWorks.Application")
        except Exception:
            sw = win32com.client.Dispatch("SldWorks.Application.32")
            launched = True
        sw.Visible = False
        sw.UserControl = False
        report["solidworks_revision"] = str(sw.RevisionNumber())
        report["solidworks_started_by_script"] = launched

        native_parts = {}
        for name, description in (
            (RING, "Corrected four-M4 B601 competition interface ring"),
            (BODY, "M6 140x140 competition load-spreading adapter"),
        ):
            step = CAD / f"{name}.step"
            sldprt = CAD / f"{name}.SLDPRT"
            if sldprt.exists():
                raise RuntimeError(f"refusing to overwrite existing native part: {sldprt}")
            model, open_err, open_warn = open_doc(sw, step, SW_DOC_PART)
            set_props(model, name, description)
            rebuild = bool(model.ForceRebuild3(False))
            save = save_as(model, sldprt)
            native_parts[name] = {
                "source_step_sha256": sha256(step),
                "open_errors": open_err,
                "open_warnings": open_warn,
                "rebuild_success": rebuild,
                "save": save,
                "path": str(sldprt).replace("\\", "/"),
                "bytes": sldprt.stat().st_size if sldprt.exists() else 0,
                "sha256": sha256(sldprt) if sldprt.exists() else None,
            }
            close_doc(sw, model)
        report["native_parts"] = native_parts

        asm_path = CAD / f"{ASM}.SLDASM"
        if asm_path.exists():
            raise RuntimeError(f"refusing to overwrite existing native assembly: {asm_path}")
        if not TEMPLATE_ASM.is_file():
            raise RuntimeError(f"assembly template missing: {TEMPLATE_ASM}")
        model = sw.NewDocument(str(TEMPLATE_ASM), 0, 0.0, 0.0)
        if model is None:
            raise RuntimeError("NewDocument returned None")
        asm_doc = model
        components = []
        for name in (BODY, RING):
            comp = add_component(asm_doc, CAD / f"{name}.SLDPRT")
            if comp is None:
                raise RuntimeError(f"AddComponent failed: {name}")
            components.append(comp)
            fix_component(model, asm_doc, comp)
        set_props(model, ASM, "Corrected two-stage B601 competition adapter")

        config_created = False
        try:
            config = model.ConfigurationManager.AddConfiguration2(
                "AS_BUILT_M4_TO_M6", "4xM4 as-built to 4xM6 140x140", "",
                0, "", "", True)
            config_created = config is not None
        except Exception:
            config_created = False
        rebuild = bool(model.ForceRebuild3(True))
        native_id = native_interference(asm_doc)
        save = save_as(model, asm_path)
        component_rows = []
        for comp in components:
            path = Path(str(comp.GetPathName()))
            try:
                fixed = bool(comp.IsFixed())
            except Exception:
                fixed = None
            component_rows.append({
                "name": str(comp.Name2),
                "path": str(path).replace("\\", "/"),
                "exists": path.is_file(),
                "fixed": fixed,
            })
        report["assembly_write"] = {
            "path": str(asm_path).replace("\\", "/"),
            "configuration_created": config_created,
            "rebuild_success": rebuild,
            "native_interference": native_id,
            "components": component_rows,
            "save": save,
            "bytes": asm_path.stat().st_size if asm_path.exists() else 0,
            "sha256": sha256(asm_path) if asm_path.exists() else None,
        }
        close_doc(sw, model)

        # Cold reopen with no writable document state retained.
        time.sleep(1.0)
        cold, open_err, open_warn = open_doc(
            sw, asm_path, SW_DOC_ASSEMBLY, SW_OPEN_SILENT | SW_OPEN_READONLY)
        cold_rebuild = bool(cold.ForceRebuild3(True))
        cold_components = list(cold.GetComponents(True) or [])
        missing = []
        refs = []
        for comp in cold_components:
            path = Path(str(comp.GetPathName()))
            refs.append(str(path).replace("\\", "/"))
            if not path.is_file():
                missing.append(str(path))
        cold_interference = native_interference(cold)
        configs = list(cold.GetConfigurationNames() or [])
        report["cold_reopen"] = {
            "open_errors": open_err,
            "open_warnings": open_warn,
            "rebuild_success": cold_rebuild,
            "configuration_names": configs,
            "top_component_count": len(cold_components),
            "references": refs,
            "missing_references": missing,
            "native_interference": cold_interference,
        }
        close_doc(sw, cold)

        report["verdict"] = (
            "M3R_SOLIDWORKS_NATIVE_PASS"
            if all(v["save"]["ok"] and v["rebuild_success"]
                   for v in native_parts.values())
            and report["assembly_write"]["save"]["ok"]
            and report["assembly_write"]["rebuild_success"]
            and cold_rebuild and not missing
            and cold_interference.get("count") == 0
            else "M3R_SOLIDWORKS_NATIVE_FAIL"
        )
    except Exception as exc:
        report["verdict"] = "M3R_SOLIDWORKS_NATIVE_FAIL"
        report["error"] = repr(exc)
    finally:
        RECEIPT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
        if sw is not None and launched:
            try:
                sw.ExitApp()
            except Exception:
                pass
        pythoncom.CoUninitialize()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("verdict") == "M3R_SOLIDWORKS_NATIVE_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
