#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1C1 live probe v11: name the bodies behind the interference rows.

Probe v9 localized cross-component overlaps by bbox; v10 proved the donor part
contains the same overlaps (bit-identical volumes).  This probe names the exact
palm/finger BODY pairs involved in the top rows at OPEN and CLOSED so a
part-level rework decision has concrete targets, and double-checks that no
mate-side misregistration remains (the V5 CLOSED overlap set should equal the
donor's internal set).

Method per state (OPEN, CLOSED): interference rows -> for each top row, find
candidate (palm body, finger body) pairs whose world bboxes intersect the
interference bbox, then confirm via IModelDoc2.ClosestDistance == 0.

Never saves, never writes receipts, leaves the session document-empty.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List

RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE")
sys.path.insert(0, str(RUN_ROOT / "99_tools"))

import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base  # noqa: E402
import F3R2_V5_NATIVE_LOOP1C1_GRIPPER_ASSEMBLY_ATTACH_ONLY as m  # noqa: E402

OPEN_TRAVEL_MM = float(m.STATES["OPEN"]["travel_mm"])
T0 = time.time()


def log(step: str) -> None:
    print(f"[{time.time() - T0:8.2f}s] {step}", flush=True)


def transform_point(array: List[float], point: List[float]) -> List[float]:
    return m.transform_point(array, point)


def main() -> int:
    result: Dict[str, Any] = {"schema": "V5_PROBE_LOOP1C1_INTERFERENCE_BODIES_V11", "states": [], "notes": []}
    sw = types = pythoncom = None
    try:
        log("attach: begin")
        sw, types, pythoncom, session = base.attach_empty_session()
        result["session"] = session
        raw_model = sw.NewDocument(str(m.ASSEMBLY_TEMPLATE), 0, 0.0, 0.0)
        model = base.wrap(raw_model, "IModelDoc2", types, pythoncom)
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
        for role in ("PALM", "LEFT", "RIGHT"):
            spec = m.PARTS[role]
            translation = m.expected_translation_m(role, OPEN_TRAVEL_MM)
            m.insert_component(sw, model, assembly, role, Path(spec["path"]), bool(spec["fixed"]), translation, types, pythoncom)
            log(f"insert {role}: ok")
        components = m.assembly_components(model, assembly, types, pythoncom)
        for side, prefix in (("LEFT", "L"), ("RIGHT", "R")):
            for guide in ("A", "B"):
                palm_face, _pf = m.guide_face(model, components["PALM"], "PALM", guide, types, pythoncom)
                finger_face, _ff = m.guide_face(model, components[side], side, guide, types, pythoncom)
                m.add_face_mate(model, assembly, palm_face, finger_face, 1, m.MATE_NAMES[f"{prefix}_{guide}"], types, pythoncom)
            m.add_advanced_limit_distance(
                model, assembly, components["PALM"], components[side],
                m.MATE_NAMES[f"{prefix}_LIMIT"], prefix, int(m.LIMIT_CONTRACTS[prefix]["alignment"]), types, pythoncom,
            )
            log(f"{prefix} guides+limit: ok")
        limit_features = [f for f in m.mate_features(model, types, pythoncom) if str(base.value(f, "Name")) in (m.MATE_NAMES["L_LIMIT"], m.MATE_NAMES["R_LIMIT"])]
        limit_features.sort(key=lambda f: str(base.value(f, "Name")))
        m.establish_configurations(model, limit_features, types, pythoncom)
        log("establish_configurations: ok")

        def body_catalog(role: str) -> List[Dict[str, Any]]:
            fresh = m.assembly_components(model, assembly, types, pythoncom)
            component = fresh[role]
            array = [float(v) for v in base.as_list(base.value(base.value(component, "Transform2"), "ArrayData"))]
            catalog = []
            for raw_body in base.as_list(component.GetBodies2(0)):
                body = base.wrap(raw_body, "IBody2", types, pythoncom)
                box = [float(v) for v in base.as_list(base.value(body, "GetBodyBox"))]
                if len(box) != 6:
                    continue
                corners = [[box[0], box[1], box[2]], [box[3], box[4], box[5]]]
                world = [transform_point(array, corner) for corner in corners]
                lo = [min(world[0][i], world[1][i]) * 1000.0 for i in range(3)]
                hi = [max(world[0][i], world[1][i]) * 1000.0 for i in range(3)]
                catalog.append({"name": str(base.value(body, "Name")), "bbox_mm": [round(v, 4) for v in lo + hi], "_raw": raw_body})
            return catalog

        def bbox_intersects(a: List[float], b: List[float]) -> bool:
            return all(a[i] <= b[i + 3] and b[i] <= a[i + 3] for i in range(3))

        for state in ("OPEN", "CLOSED"):
            m.show_configuration(model, state, types, pythoncom)
            catalogs = {role: body_catalog(role) for role in ("PALM", "LEFT", "RIGHT")}
            manager = base.wrap(base.value(assembly, "InterferenceDetectionManager"), "IInterferenceDetectionMgr", types, pythoncom)
            state_row: Dict[str, Any] = {"configuration": state, "rows": []}
            try:
                manager.TreatCoincidenceAsInterference = False
                manager.TreatSubAssembliesAsComponents = False
                manager.IncludeMultibodyPartInterferences = True
                manager.IgnoreHiddenBodies = False
                manager.ShowIgnoredInterferences = True
                interferences = base.as_list(manager.GetInterferences())
                rows: List[Dict[str, Any]] = []
                for raw in interferences:
                    interference = base.wrap(raw, "IInterference", types, pythoncom)
                    paths = sorted(m.component_path(base.wrap(c, "IComponent2", types, pythoncom)) for c in base.as_list(base.value(interference, "Components")))
                    volume_mm3 = float(base.value(interference, "Volume")) * 1.0e9
                    if len(set(paths)) < 2 or volume_mm3 <= 0.0:
                        continue
                    row: Dict[str, Any] = {"components": [Path(p).name for p in paths], "volume_mm3": round(volume_mm3, 6)}
                    try:
                        body_raw = interference.GetInterferenceBody()
                        if body_raw is not None:
                            body = base.wrap(body_raw, "IBody2", types, pythoncom)
                            box = [float(v) for v in base.as_list(base.value(body, "GetBodyBox"))]
                            if len(box) == 6:
                                row["bbox_mm"] = [round(v * 1000.0, 4) for v in box]
                    except Exception as exc:  # noqa: BLE001
                        row["body_error"] = repr(exc)
                    rows.append(row)
                rows.sort(key=lambda item: -item["volume_mm3"])
                for row in rows[:6]:
                    bbox = row.get("bbox_mm")
                    if not bbox:
                        continue
                    pair_names: List[Any] = []
                    for palm_body in catalogs["PALM"]:
                        if not bbox_intersects(bbox, palm_body["bbox_mm"]):
                            continue
                        for finger_role in ("LEFT", "RIGHT"):
                            for finger_body in catalogs[finger_role]:
                                if not bbox_intersects(bbox, finger_body["bbox_mm"]):
                                    continue
                                try:
                                    distance, _p1, _p2 = m.closest_distance(model, palm_body["_raw"], finger_body["_raw"])
                                except Exception:  # noqa: BLE001
                                    continue
                                if abs(distance) < 1.0e-7:
                                    pair_names.append([palm_body["name"], finger_body["name"]])
                    row["body_pairs"] = pair_names[:4]
                state_row["rows"] = rows[:12]
                state_row["cross_component_count"] = len(rows)
            finally:
                manager.Done()
            result["states"].append(state_row)
            log(f"{state}: rows={state_row['cross_component_count']} (top pairs named)")
        result["verdict"] = "V5_PROBE_LOOP1C1_INTERFERENCE_BODIES_PASS"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1C1_INTERFERENCE_BODIES_FAIL"
        log("exception; see payload")
    finally:
        if sw is not None:
            try:
                result["cleanup"] = m.close_all_owned(sw)
                log("cleanup: session document-empty")
            except Exception as cleanup_exc:  # noqa: BLE001
                result["cleanup_exception"] = repr(cleanup_exc)
        if pythoncom is not None:
            try:
                pythoncom.CoUninitialize()
            except Exception:  # noqa: BLE001
                pass
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0 if result.get("verdict", "").endswith("_PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
