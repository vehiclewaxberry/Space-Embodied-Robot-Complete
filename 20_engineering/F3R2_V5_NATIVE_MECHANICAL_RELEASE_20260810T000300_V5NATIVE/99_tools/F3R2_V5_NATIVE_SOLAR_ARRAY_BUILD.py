#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 multi-panel solar array candidate native build (attach-only).

Builds six simplified panel SLDPRTs (L1..L3, R1..R3) and two side
subassemblies with per-configuration panel positions for the seven solar
states.  No solar cells, no flight mechanism detail, no L0 mass override.
Assembly uses configuration transforms only; kinematic hinge mates are a
separate later step to avoid the Loop1D suppression/rebuild hang.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence


sys.dont_write_bytecode = True
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import F3R2_V5_SESSION_BINDING as sbin
import F3R2_V5_MEMORY_OVERRIDE as mo
import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base
import F3R2_V5_NATIVE_LOOP1D_HDRM_CAMERA_HARNESS_ATTACH_ONLY as loop1d


RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
RUN_ROOT = RUN_ROOT / "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
SOLAR_DIR = RUN_ROOT / "01_native_parts/solar_array"
SUBASM_DIR = RUN_ROOT / "02_native_subassemblies"
VALIDATION = RUN_ROOT / "13_validation"

ASSEMBLY_TEMPLATE = Path(r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_assembly.asmdot")

PANEL_LEN_MM = 56.67
PANEL_W_MM = 227.0
PANEL_T_MM = 6.0
ROOT_Y_L = 143.15
ROOT_Y_R = -143.15
INNER_Y_L = 116.15
INNER_Y_R = -116.15

CONFIGS = [
    "SOLAR_STOWED",
    "SOLAR_DEPLOY_STAGE1",
    "SOLAR_DEPLOY_STAGE2",
    "SOLAR_DEPLOYED_NOMINAL",
    "SOLAR_LEFT_FAIL",
    "SOLAR_RIGHT_FAIL",
    "SOLAR_BOTH_FAIL",
]


def posix(path: Path) -> str:
    return str(path).replace("\\", "/")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def file_fact(path: Path) -> Dict[str, Any]:
    return {"path": posix(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def write_json_once(path: Path, payload: Dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return posix(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return value


def panel_specs() -> Dict[str, Dict[str, Any]]:
    specs: Dict[str, Dict[str, Any]] = {}
    for side in ("L", "R"):
        for index in (1, 2, 3):
            name = f"SOLAR_PANEL_{side}{index}"
            specs[name] = {
                "target": SOLAR_DIR / f"{name}.SLDPRT",
                "geometry": {
                    "kind": "box",
                    "width_mm": PANEL_W_MM,
                    "height_mm": PANEL_LEN_MM,
                    "depth_mm": PANEL_T_MM,
                },
                "expected_sorted_mm": [PANEL_T_MM, PANEL_LEN_MM, PANEL_W_MM],
                "local_center_mm": [0.0, 0.0, PANEL_T_MM / 2.0],
                "properties": {
                    "FUNCTION": "SIMPLIFIED_SOLAR_PANEL_CANDIDATE",
                    "SIDE": side,
                    "PANEL_INDEX": str(index),
                    "SOLAR_CELL_DETAIL": "PROHIBITED",
                    "MASS_SOURCE": "EXTERNAL_MECHANICAL_ONLY",
                    "HINGE_AXIS": f"X@ROOT_Y={ROOT_Y_L if side == 'L' else ROOT_Y_R}mm",
                },
            }
    return specs


def rotation_x_data(deg: float, tx: float = 0.0, ty: float = 0.0, tz: float = 0.0) -> List[float]:
    a = __import__("math").radians(deg)
    c, s = __import__("math").cos(a), __import__("math").sin(a)
    return [1.0, 0.0, 0.0, 0.0, c, s, 0.0, -s, c, tx, ty, tz, 1.0, 0.0, 0.0, 0.0]


def translation_data(tx: float, ty: float, tz: float) -> List[float]:
    return [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, tx, ty, tz, 1.0, 0.0, 0.0, 0.0]


def panel_pose(side: str, index: int, deployed: bool) -> List[float]:
    sign = 1.0 if side == "L" else -1.0
    root_y = ROOT_Y_L if side == "L" else ROOT_Y_R
    inner_y = INNER_Y_L if side == "L" else INNER_Y_R
    offset = (index - 1) * PANEL_LEN_MM
    if deployed:
        cy = root_y + offset + PANEL_LEN_MM / 2.0
        return translation_data(0.0, sign * cy, 0.0)
    cz = -((index - 1) * PANEL_LEN_MM + PANEL_LEN_MM / 2.0)
    return rotation_x_data(-90.0, 0.0, sign * inner_y, cz)


def build_panels(sw: Any, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    rows = []
    for name, spec in panel_specs().items():
        target = Path(spec["target"])
        if target.exists():
            rows.append({"name": name, "resumed_from_existing": True, "cold": loop1d.verify_part_cold(sw, types, pythoncom, name, spec)})
        else:
            rows.append(loop1d.build_part(sw, types, pythoncom, name, spec))
    return rows


def make_transform(sw: Any, data: Sequence[float], types: Any, pythoncom: Any) -> Any:
    from win32com.client import VARIANT
    utility = base.wrap(base.value(sw, "GetMathUtility"), "IMathUtility", types, pythoncom)
    transform = utility.CreateTransform(VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, list(data)))
    if transform is None:
        raise RuntimeError("CreateTransform returned null")
    return transform


def insert_panel(sw: Any, model: Any, assembly: Any, panel_path: Path, transform: List[float], types: Any, pythoncom: Any) -> Any:
    title = str(base.value(model, "GetTitle"))
    part = None
    try:
        raw_part, errors, warnings = loop1d.unpack_document(sw.OpenDoc6(str(panel_path), 1, 3, "", 0, 0), "OPEN_SOLAR_PANEL")
        if raw_part is None or errors != 0 or warnings not in (0, 128):
            raise RuntimeError(f"open panel failed {panel_path} e={errors} w={warnings}")
        part = base.wrap(raw_part, "IModelDoc2", types, pythoncom)
        loop1d.activate(sw, title)
        raw_component = assembly.AddComponent5(str(panel_path), 0, "", False, "", 0.0, 0.0, 0.0)
        if raw_component is None:
            raise RuntimeError("AddComponent5 returned null")
        component = base.wrap(raw_component, "IComponent2", types, pythoncom)
        if not bool(component.SetTransformAndSolve3(make_transform(sw, transform, types, pythoncom), True)):
            raise RuntimeError("panel transform failed")
        if not bool(model.EditRebuild3()):
            raise RuntimeError("rebuild failed after panel insert")
        model.ClearSelection2(True)
        if not bool(component.Select4(False, None, False)):
            raise RuntimeError("panel select failed")
        assembly.UnfixComponent()
        model.ClearSelection2(True)
        if bool(base.value(component, "IsFixed")):
            raise RuntimeError("panel remained fixed after unfix")
        return component
    finally:
        if part is not None:
            try:
                sw.CloseDoc(str(base.value(part, "GetTitle")))
            except Exception:
                pass
        loop1d.activate(sw, title)


def config_pose_map(side: str) -> Dict[str, Dict[int, bool]]:
    return {
        "SOLAR_STOWED": {1: False, 2: False, 3: False},
        "SOLAR_DEPLOY_STAGE1": {1: True, 2: False, 3: False},
        "SOLAR_DEPLOY_STAGE2": {1: True, 2: True, 3: False},
        "SOLAR_DEPLOYED_NOMINAL": {1: True, 2: True, 3: True},
        "SOLAR_LEFT_FAIL": {1: True, 2: False, 3: False},
        "SOLAR_RIGHT_FAIL": {1: True, 2: True, 3: True},
        "SOLAR_BOTH_FAIL": {1: False, 2: False, 3: False},
    }


def fresh_panels(model: Any, assembly: Any, side: str, types: Any, pythoncom: Any) -> Dict[int, Any]:
    fresh: Dict[int, Any] = {}
    for raw in base.as_list(assembly.GetComponents(False)):
        component = base.wrap(raw, "IComponent2", types, pythoncom)
        path = Path(str(base.value(component, "GetPathName"))).resolve()
        for index in (1, 2, 3):
            if path.name == f"SOLAR_PANEL_{side}{index}.SLDPRT":
                fresh[index] = component
    if set(fresh) != {1, 2, 3}:
        raise RuntimeError(f"fresh panel set incomplete {side}: {sorted(fresh)}")
    return fresh


def build_side_assembly(sw: Any, types: Any, pythoncom: Any, side: str) -> Dict[str, Any]:
    target = SUBASM_DIR / f"{side}_SOLAR_ARRAY.SLDASM"
    if target.exists():
        return {"side": side, "target": posix(target), "resumed_from_existing": True, "save": file_fact(target)}
    raw = sw.NewDocument(str(ASSEMBLY_TEMPLATE), 0, 0.0, 0.0)
    if raw is None:
        raw = base.value(sw, "ActiveDoc")
    if raw is None:
        raise RuntimeError("new assembly failed")
    model = base.wrap(raw, "IModelDoc2", types, pythoncom)
    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    manager = base.wrap(base.value(model, "ConfigurationManager"), "IConfigurationManager", types, pythoncom)
    active = base.wrap(base.value(manager, "ActiveConfiguration"), "IConfiguration", types, pythoncom)
    active.Name = CONFIGS[0]
    components: Dict[str, Any] = {}
    for index in (1, 2, 3):
        panel_path = SOLAR_DIR / f"SOLAR_PANEL_{side}{index}.SLDPRT"
        components[str(index)] = insert_panel(sw, model, assembly, panel_path, panel_pose(side, index, False), types, pythoncom)
    for config in CONFIGS[1:]:
        if manager.AddConfiguration2(config, "solar state", "", 0, "", "", True) is None:
            raise RuntimeError(f"add configuration failed {config}")
    pose_map = config_pose_map(side)
    rows = []
    for config in CONFIGS:
        model.ShowConfiguration2(config)
        active_name = str(base.value(base.wrap(base.value(manager, "ActiveConfiguration"), "IConfiguration", types, pythoncom), "Name"))
        if active_name != config:
            raise RuntimeError(f"show configuration failed {config}: active={active_name}")
        if not bool(model.EditRebuild3()):
            raise RuntimeError(f"rebuild after show configuration failed {config}")
        fresh = fresh_panels(model, assembly, side, types, pythoncom)
        for index, component in fresh.items():
            if bool(base.value(component, "IsFixed")):
                model.ClearSelection2(True)
                if not bool(component.Select4(False, None, False)):
                    raise RuntimeError(f"panel select failed in config {config}")
                assembly.UnfixComponent()
                model.ClearSelection2(True)
            pose = panel_pose(side, int(index), pose_map[config][int(index)])
            if not bool(component.SetTransformAndSolve3(make_transform(sw, pose, types, pythoncom), False)):
                raise RuntimeError(f"config transform failed {config} panel {index}")
        if not bool(model.ForceRebuild3(True)):
            raise RuntimeError(f"config rebuild failed {config}")
        rows.append({"configuration": config, "panel_deployed": pose_map[config]})
    if not bool(model.ShowConfiguration2("SOLAR_DEPLOYED_NOMINAL")):
        raise RuntimeError("cannot restore nominal config")
    save = base.save_native_part(model, target)
    try:
        sw.CloseDoc(str(base.value(model, "GetTitle")))
    except Exception:
        pass
    return {"side": side, "target": posix(target), "save": save, "configurations": rows, "components": {k: posix(Path(str(base.value(v, "GetPathName")))) for k, v in components.items()}}


def cold_verify_side(sw: Any, types: Any, pythoncom: Any, side: str) -> Dict[str, Any]:
    target = SUBASM_DIR / f"{side}_SOLAR_ARRAY.SLDASM"
    raw = sw.OpenDoc6(str(target), 2, 3, "", 0, 0)
    model_raw, outs = base.unpack(raw)
    errors, warnings = int(outs[0]), int(outs[1])
    if model_raw is None or errors != 0 or warnings not in (0, 128):
        raise RuntimeError(f"cold open failed {target} e={errors} w={warnings}")
    model = base.wrap(model_raw, "IModelDoc2", types, pythoncom)
    names = [str(n) for n in base.as_list(base.value(model, "GetConfigurationNames"))]
    if set(names) != set(CONFIGS):
        raise RuntimeError(f"cold config set mismatch {side}: {names}")
    facts = {"path": posix(target), "bytes": target.stat().st_size, "sha256": sha256(target), "configurations": names}
    sw.CloseDoc(str(base.value(model, "GetTitle")))
    return facts


def execute() -> int:
    result: Dict[str, Any] = {
        "schema": "F3R2_V5_SOLAR_ARRAY_NATIVE_RECEIPT_V1",
        "timestamp_start_utc": datetime.now(timezone.utc).isoformat(),
        "run_root": posix(RUN_ROOT),
        "panels": [],
        "assemblies": [],
        "non_claims": [
            "NOT_FINAL_NATIVE_BASELINE",
            "NOT_FLIGHT_READY",
            "NO_SOLAR_CELL_DETAIL",
            "NO_L0_MASS_OVERRIDE",
        ],
    }
    sw = types = pythoncom = None
    try:
        sw, types, pythoncom, session = base.attach_empty_session()
        if int(session["pid"]) != int(sbin.resolve_pid(42276)):
            raise RuntimeError(f"session pid mismatch {session['pid']}")
        result["solidworks"] = session
        result["memory_samples_gib"] = base.memory_gate()
        result["memory_override_allowed"] = mo.override_allowed()
        result["panels"] = build_panels(sw, types, pythoncom)
        for side in ("L", "R"):
            result["assemblies"].append(build_side_assembly(sw, types, pythoncom, side))
        for side in ("L", "R"):
            result["assemblies"].append({"cold": cold_verify_side(sw, types, pythoncom, side)})
        if int(base.value(sw, "GetDocumentCount")) != 0:
            raise RuntimeError("documents remain open after solar build")
        result["timestamp_end_utc"] = datetime.now(timezone.utc).isoformat()
        result["verdict"] = "V5_SOLAR_ARRAY_CANDIDATE_NATIVE_PANELS_AND_SIDE_ASMS_PASS"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        receipt = VALIDATION / f"V5_SOLAR_ARRAY_NATIVE_RECEIPT_{stamp}.json"
        write_json_once(receipt, json_safe(result))
        print(json.dumps({"verdict": result["verdict"], "receipt": posix(receipt), "panels": len(result["panels"]), "assemblies": len(result["assemblies"])}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        result.update({"verdict": "V5_SOLAR_ARRAY_BUILD_FAIL", "reason": str(exc), "traceback": __import__("traceback").format_exc()})
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        failure = VALIDATION / f"V5_SOLAR_ARRAY_FAIL_{stamp}.json"
        write_json_once(failure, json_safe(result))
        print(json.dumps({"verdict": result["verdict"], "failure": posix(failure), "reason": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    finally:
        if sw is not None:
            try:
                docs = [d for d in (base.as_list(base.value(sw, "GetDocuments")) or [])]
                for d in docs:
                    try:
                        sw.CloseDoc(str(base.value(d, "GetTitle")))
                    except Exception:
                        pass
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(execute())
