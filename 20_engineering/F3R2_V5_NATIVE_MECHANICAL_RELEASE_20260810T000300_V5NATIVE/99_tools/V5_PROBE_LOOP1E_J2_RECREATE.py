#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1E live probe: joint2 recreation failure discriminator.

20260812T0734/0739 runs: joint1 passed the full recreate-drive architecture
(create 0 -> delete -> recreate +0.5 deg -> delete -> recreate 0), but
joint2's first recreation (delete the just-created mate, recreate at
-0.5 deg — joint2's upper bound is 0 so the probe goes inward/negative)
fails with AddMate3 error=0 and zero additions, even with a rebuild after
the delete.

Discriminate (in-memory, NO SAVE, production state):
  E1  create joint2 mate at 0.0 (baseline — worked in the driver loop);
  E2  delete it, recreate at 0.0 (delete-then-same-angle);
  E3  delete, recreate at -0.0087 rad (the production failing case);
  E4  delete, recreate at +0.0087 rad (sign isolation);
Record AddMate3 error status and additions count for each, plus joint2
relative rotation (link1<-link2) where created.

Never writes inside the release tree, never mutates the protected donor,
never saves; session left document-empty.
"""

from __future__ import annotations

import json
import math
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE")
sys.path.insert(0, str(RUN_ROOT / "99_tools"))

import pythoncom  # noqa: E402
import win32com.client  # noqa: E402
from win32com.client import gencache  # noqa: E402

import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base  # noqa: E402
import F3R2_V5_NATIVE_LOOP1E_TOP_ASSEMBLY_ATTACH_ONLY as m  # noqa: E402
import F3R2_V5_SESSION_BINDING as sbin  # noqa: E402

T0 = time.time()
SW_COMPONENT_FULLY_RESOLVED = 1
PROTECTED_WATCH = [m.B51_DONOR] + sorted(m.B51_DONOR_ROOT.rglob("*.SLDPRT"))
MATE_NAME = "V5_PROBE_J2_ANGLE"


def log(step: str) -> None:
    print(f"[{time.time() - T0:8.2f}s] {step}", flush=True)


def close_everything(sw: Any) -> int:
    for _pass in range(4):
        documents = base.as_list(base.value(sw, "GetDocuments"))
        if not documents:
            break
        titles: List[str] = []
        for raw in documents:
            try:
                titles.append(str(base.value(raw, "GetTitle")))
            except Exception:  # noqa: BLE001
                continue
        for title in reversed(list(dict.fromkeys(titles))):
            try:
                sw.CloseDoc(title)
            except Exception:  # noqa: BLE001
                pass
    if int(base.value(sw, "GetDocumentCount")):
        try:
            sw.CloseAllDocuments(True)
        except Exception:  # noqa: BLE001
            pass
    return int(base.value(sw, "GetDocumentCount"))


def find_leaf(assembly: Any, leaf: str, types: Any, pythoncom_module: Any) -> Optional[Any]:
    for raw in base.as_list(assembly.GetComponents(True)):
        component = base.wrap(raw, "IComponent2", types, pythoncom_module)
        if str(base.value(component, "Name2")).split("/")[-1] == leaf:
            return component
    return None


def delete_feature(model: Any, feature: Any) -> bool:
    model.ClearSelection2(True)
    if not bool(feature.Select2(False, 0)):
        return False
    try:
        model.EditDelete()
        return True
    except Exception:  # noqa: BLE001
        return False
    finally:
        model.ClearSelection2(True)


def attempt(model: Any, assembly: Any, joint: Dict[str, Any], angle: float, types: Any, pythoncom_module: Any) -> Dict[str, Any]:
    female = find_leaf(assembly, "B51_REV_DATUM_FEMALE-2", types, pythoncom_module)
    male = find_leaf(assembly, "B51_REV_DATUM_MALE-2", types, pythoncom_module)
    first_plane = m.component_side_plane(female, base, types, pythoncom_module)
    second_plane = m.component_side_plane(male, base, types, pythoncom_module)
    before_names = set(m.mate_features(model, base, types, pythoncom_module))
    model.ClearSelection2(True)
    sel = bool(first_plane.Select2(False, 1)) and bool(second_plane.Select2(True, 1))
    if not sel:
        return {"angle": angle, "error": "SELECT_FAIL"}
    returned = assembly.AddMate3(6, 0, False, 0.0, 0.0, 0.0, 0.0, 0.0, float(angle), float(joint["upper_rad"]), float(joint["lower_rad"]), False, 0)
    mate_raw, outs = base.unpack(returned)
    error = int(outs[0]) if outs else -1
    model.ClearSelection2(True)
    after = m.mate_features(model, base, types, pythoncom_module)
    additions = [item for name, item in after.items() if name not in before_names]
    out: Dict[str, Any] = {"angle": angle, "error_status": error, "mate_raw_null": mate_raw is None, "additions": len(additions)}
    if mate_raw is not None and additions:
        feature = additions[0]
        feature.Name = MATE_NAME
        definition = m.angle_mate_data(feature, base, types, pythoncom_module)
        out["angle_after"] = float(base.value(definition, "Angle"))
        out["error_code"] = m.feature_error_code(feature, base)
    return out


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "V5_PROBE_LOOP1E_J2_RECREATE_V1",
        "timestamp_start_utc": datetime.now(timezone.utc).isoformat(),
        "phases": {},
    }
    sw = types = pythoncom_module = None
    try:
        pythoncom_module = pythoncom
        pythoncom_module.CoInitialize()
        types = gencache.GetModuleForTypelib(*base.SW_TLB)
        raw = win32com.client.GetActiveObject(base.SW_PROG_ID)
        sw = base.wrap(raw, "ISldWorks", types, pythoncom_module)
        session = {"pid": int(base.value(sw, "GetProcessID")), "revision": str(base.value(sw, "RevisionNumber"))}
        expected_pid = int(sbin.resolve_pid(json.loads(m.LOOP1_RECEIPT.read_text(encoding="utf-8-sig")).get("solidworks", {}).get("pid", -1)))
        if session["pid"] != expected_pid:
            raise RuntimeError(f"session PID drifted: {session['pid']} != {expected_pid}")
        if int(base.value(sw, "GetDocumentCount")) != 0:
            raise RuntimeError("session not document-empty at probe start")
        result["session"] = session
        result["protected_pre"] = {m.sha256(path): str(path) for path in PROTECTED_WATCH if path.is_file()}
        log(f"attach ok pid={session['pid']}")

        for part in sorted(p for p in m.LOCAL_ARM_ROOT.rglob("*.SLDPRT") if not p.name.startswith("~$")):
            open_form = m.sw_openable_path(part)
            options = 1 | (2 if open_form != str(part.resolve()) else 0)
            raw2 = sw.OpenDoc6(open_form, m.SW_DOC_PART, options, "", 0, 0)
            model_raw, outs = base.unpack(raw2)
            if model_raw is None or (outs and int(outs[0]) != 0):
                raise RuntimeError(f"prebind failed {part.name}")
        raw_asm = sw.OpenDoc6(m.sw_openable_path(m.LOCAL_ARM), m.SW_DOC_ASSEMBLY, 1, "", 0, 0)
        model_raw, outs = base.unpack(raw_asm)
        if model_raw is None or (outs and int(outs[0]) != 0):
            raise RuntimeError("assembly open failed")
        model = base.wrap(model_raw, "IModelDoc2", types, pythoncom_module)
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom_module)
        for cfg in m.ARM_CONFIGS:
            if not m.show_config_ok(model, cfg, base, types, pythoncom_module):
                raise RuntimeError(f"census config failed {cfg}")
        for raw2 in base.as_list(assembly.GetComponents(True)):
            component = base.wrap(raw2, "IComponent2", types, pythoncom_module)
            name2 = str(base.value(component, "Name2"))
            leaf = name2.split("/")[-1]
            if leaf == m.ARM_LEGACY_GRIPPER_LEAF or int(base.value(component, "GetSuppression2")) == SW_COMPONENT_FULLY_RESOLVED:
                continue
            part_title = Path(str(base.value(component, "GetPathName"))).name
            try:
                sw.CloseDoc(part_title)
            except Exception:  # noqa: BLE001
                pass
            component.SetSuppression2(SW_COMPONENT_FULLY_RESOLVED)
            if not bool(model.ForceRebuild3(True)):
                raise RuntimeError(f"reload rebuild failed {name2}")
        if not m.show_config_ok(model, m.ARM_CONFIGS[0], base, types, pythoncom_module) or not bool(model.ForceRebuild3(True)):
            raise RuntimeError("默认 activation failed")
        log("state ready")

        joint2 = m.accepted_urdf_joints()[1]
        experiments: Dict[str, Any] = {}
        current = None
        for label, angle in (("E1_create_zero", 0.0), ("E2_recreate_zero", 0.0), ("E3_recreate_neg", math.radians(-0.5)), ("E4_recreate_pos", math.radians(0.5))):
            if current is not None:
                feature = m.mate_features(model, base, types, pythoncom_module).get(MATE_NAME)
                deleted = delete_feature(model, feature) if feature is not None else False
                model.ForceRebuild3(True)
                experiments[label + "_deleted_prior"] = deleted
            out = attempt(model, assembly, joint2, angle, types, pythoncom_module)
            experiments[label] = out
            current = out if out.get("additions") else None
            log(f"{label}: error_status={out.get('error_status')} additions={out.get('additions')} angle_after={out.get('angle_after')}")
        result["phases"]["experiments"] = experiments

        remaining = close_everything(sw)
        result["cleanup_remaining"] = remaining
        log(f"cleanup remaining={remaining}")
        result["verdict"] = "V5_PROBE_LOOP1E_J2_RECREATE_PASS"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1E_J2_RECREATE_FAIL"
        log("exception; see payload")
    finally:
        if sw is not None:
            try:
                result["cleanup_document_count"] = close_everything(sw)
            except Exception as cleanup_exc:  # noqa: BLE001
                result["cleanup_exception"] = repr(cleanup_exc)
        try:
            post = {m.sha256(path): str(path) for path in PROTECTED_WATCH if path.is_file()}
            result["protected_post_unchanged"] = post == result.get("protected_pre")
        except Exception as exc:  # noqa: BLE001
            result["protected_post_exception"] = repr(exc)
        result["timestamp_end_utc"] = datetime.now(timezone.utc).isoformat()
        if pythoncom_module is not None:
            try:
                pythoncom_module.CoUninitialize()
            except Exception:  # noqa: BLE001
                pass
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
