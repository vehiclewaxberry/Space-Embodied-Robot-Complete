"""Build the isolated B5.0 native SolidWorks Phase0 smoke artifacts.

The geometry is a tool-health coupon only.  It has no spacecraft, B601,
manufacturing, mass, strength, or flight authority.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from sw_b50_core import (  # noqa: E402
    CANDIDATE_ROOT,
    Phase0Error,
    SolidWorksSession,
    add_component_identity,
    artifact_record,
    default_run_id,
    get_com_member,
    require_new_run_root,
    utc_now,
    write_json_once,
)


PART_NAME = "PHASE0_COM_SMOKE_PART"
ASSEMBLY_NAME = "PHASE0_COM_SMOKE_ASSEMBLY"
DRAWING_NAME = "PHASE0_COM_SMOKE_DRAWING"


def _m(mm: float) -> float:
    return float(mm) / 1000.0


def _select_front_plane(model: Any) -> str:
    model.ClearSelection2(True)
    for name in ("前视基准面", "Front Plane"):
        if model.Extension.SelectByID2(
            name, "PLANE", 0.0, 0.0, 0.0, False, 0, None, 0
        ):
            return name
    raise Phase0Error("cannot select Front Plane in Phase0 part template")


def _build_part(
    session: SolidWorksSession, run_root: Path, run_id: str
) -> tuple[Path, dict[str, Any]]:
    path = run_root / "native" / "parts" / f"{PART_NAME}.SLDPRT"
    model = session.new_document("part")
    selected_plane = _select_front_plane(model)
    sketch = model.SketchManager
    sketch.InsertSketch(True)
    rectangle = sketch.CreateCenterRectangle(
        0.0, 0.0, 0.0, _m(10.0), _m(5.0), 0.0
    )
    if not rectangle:
        raise Phase0Error("CreateCenterRectangle returned no sketch entities")
    sketch.InsertSketch(True)
    feature = model.FeatureManager.FeatureExtrusion2(
        True,
        False,
        False,
        0,
        0,
        _m(5.0),
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
        raise Phase0Error("FeatureExtrusion2 returned no feature")
    try:
        session.cast(feature, "IFeature").Name = "PHASE0_SMOKE_EXTRUDE"
    except Exception:
        pass
    session.set_text_properties(
        model,
        {
            "ASSET_ROLE": "SOLIDWORKS_AUTOMATION_SMOKE_TEST_ONLY",
            "DESIGN_AUTHORITY": "NONE",
            "MASS_AUTHORITY": "EXCLUDED",
            "GEOMETRY_AUTHORITY": "TEST_COUPON_ONLY",
            "RUN_ID": run_id,
            "DIMENSION_NOTE": "20x10x5 mm tool coupon; not spacecraft geometry",
        },
    )
    if not model.ForceRebuild3(False):
        raise Phase0Error("Phase0 part rebuild failed")
    part_doc = session.cast(model, "IPartDoc")
    box = [float(value) * 1000.0 for value in part_doc.GetPartBox(True)]
    bodies = list(part_doc.GetBodies2(0, False) or [])
    if not bodies:
        raise Phase0Error("Phase0 part contains no solid body")
    if min(box[3] - box[0], box[4] - box[1], box[5] - box[2]) <= 0.0:
        raise Phase0Error(f"Phase0 part has a degenerate box: {box}")
    save = session.save_as(model, path)
    session.close_document(model)
    return path, {
        "selected_plane": selected_plane,
        "solid_body_count": len(bodies),
        "bounding_box_mm": box,
        "save": save,
    }


def _build_assembly(
    session: SolidWorksSession, run_root: Path, part_path: Path, run_id: str
) -> tuple[Path, dict[str, Any]]:
    path = run_root / "native" / "assembly" / f"{ASSEMBLY_NAME}.SLDASM"
    model = session.new_document("assembly")
    component = add_component_identity(session, model, part_path)
    session.set_text_properties(
        model,
        {
            "ASSET_ROLE": "SOLIDWORKS_AUTOMATION_SMOKE_TEST_ONLY",
            "DESIGN_AUTHORITY": "NONE",
            "MASS_AUTHORITY": "EXCLUDED",
            "RUN_ID": run_id,
            "REFERENCE_POLICY": "CANDIDATE_RUN_ROOT_ONLY",
        },
    )
    save = session.save_as(model, path)
    session.close_all_documents()
    return path, {"component": component, "save": save}


def _build_drawing(
    session: SolidWorksSession, run_root: Path, assembly_path: Path, run_id: str
) -> tuple[Path, dict[str, Any]]:
    path = run_root / "native" / "drawings" / f"{DRAWING_NAME}.SLDDRW"
    assembly_model, assembly_open = session.open_document(assembly_path, "assembly")
    drawing_model = session.new_document("drawing")
    drawing_doc = session.cast(drawing_model, "IDrawingDoc")
    placed = None
    placed_name = None
    for view_name in ("*等轴测", "*Isometric", "*前视", "*Front"):
        try:
            placed = drawing_doc.CreateDrawViewFromModelView3(
                str(assembly_path), view_name, 0.18, 0.14, 0.0
            )
        except Exception:
            placed = None
        if placed is not None:
            placed_name = view_name
            break
    if placed is None:
        raise Phase0Error("cannot create a drawing view from the smoke assembly")
    session.set_text_properties(
        drawing_model,
        {
            "ASSET_ROLE": "SOLIDWORKS_AUTOMATION_SMOKE_TEST_ONLY",
            "DESIGN_AUTHORITY": "NONE",
            "MASS_AUTHORITY": "EXCLUDED",
            "RUN_ID": run_id,
            "DRAWING_PURPOSE": "API health check; not an engineering drawing",
        },
    )
    if not drawing_model.ForceRebuild3(False):
        raise Phase0Error("Phase0 drawing rebuild failed")
    sheet = session.cast(drawing_doc.GetCurrentSheet(), "ISheet")
    views = list(sheet.GetViews() or [])
    if not views:
        raise Phase0Error("Phase0 drawing has no views after rebuild")
    save = session.save_as(drawing_model, path)
    session.close_all_documents()
    return path, {
        "assembly_open": assembly_open,
        "placed_model_view": placed_name,
        "sheet_view_count": len(views),
        "save": save,
    }


def _export_step(
    session: SolidWorksSession, run_root: Path, assembly_path: Path
) -> tuple[Path, dict[str, Any]]:
    path = run_root / "exports" / f"{ASSEMBLY_NAME}.step"
    model, open_record = session.open_document(assembly_path, "assembly")
    if not model.ForceRebuild3(False):
        raise Phase0Error("Phase0 assembly rebuild failed before STEP export")
    save = session.save_as(model, path)
    session.close_all_documents()
    return path, {"assembly_open": open_record, "save": save}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a new, isolated SolidWorks Phase0 smoke run."
    )
    parser.add_argument(
        "--run-id",
        default=default_run_id(),
        help="New immutable run identifier; existing run roots are rejected.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report: dict[str, Any] = {
        "schema": "SER_B50_PHASE0_BUILD_V1",
        "generated_utc": utc_now(),
        "run_id": args.run_id,
        "candidate_root": str(CANDIDATE_ROOT),
        "scope": "SOLIDWORKS_AUTOMATION_SMOKE_TEST_ONLY",
        "design_authority": "NONE",
        "mass_authority": "EXCLUDED",
        "status": "PHASE0_TOOL_GATE_BUILD_HOLD",
        "steps": {},
        "artifacts": {},
    }
    run_root: Path | None = None
    report_path: Path | None = None
    session: SolidWorksSession | None = None
    try:
        run_root = require_new_run_root(args.run_id)
        report_path = run_root / "evidence" / "phase0_build_report.json"
        report["run_root"] = str(run_root)
        with SolidWorksSession(run_root, visible=False) as session:
            report["session_start"] = session.info()
            part_path, report["steps"]["part"] = _build_part(
                session, run_root, args.run_id
            )
            assembly_path, report["steps"]["assembly"] = _build_assembly(
                session, run_root, part_path, args.run_id
            )
            drawing_path, report["steps"]["drawing"] = _build_drawing(
                session, run_root, assembly_path, args.run_id
            )
            step_path, report["steps"]["step_export"] = _export_step(
                session, run_root, assembly_path
            )
        report["session_end"] = session.info()
        for name, path in {
            "part": part_path,
            "assembly": assembly_path,
            "drawing": drawing_path,
            "step": step_path,
        }.items():
            report["artifacts"][name] = artifact_record(path, run_root)
        report["status"] = "PHASE0_TOOL_GATE_BUILD_PASS"
    except Exception as exc:
        report["status"] = "PHASE0_TOOL_GATE_BUILD_HOLD"
        report["exception"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        if session is not None:
            report["session_end"] = session.info()
    finally:
        report["completed_utc"] = utc_now()
        if run_root is not None and report_path is not None:
            try:
                write_json_once(report_path, report, run_root)
            except Exception as evidence_exc:
                report["evidence_write_error"] = repr(evidence_exc)
                report["status"] = "PHASE0_TOOL_GATE_BUILD_HOLD"
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PHASE0_TOOL_GATE_BUILD_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

