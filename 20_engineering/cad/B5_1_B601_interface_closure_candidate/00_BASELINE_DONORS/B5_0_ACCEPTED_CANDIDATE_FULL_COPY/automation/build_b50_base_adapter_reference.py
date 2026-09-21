"""Build the evidence-bounded B5.0 B601 base-adapter reference envelope.

The only admitted geometry is the approved dual-track datum and three
Gate-0/PDR-bound envelopes.  Bolt holes, pins, materials, loads, connector
penetrations, tolerances, and physical qualification remain UNKNOWN/HOLD.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from build_b50_native import _add_component, _part_facts  # noqa: E402
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
WORKSPACE_ROOT = CANDIDATE_ROOT.parents[2]
EXPECTED_URDF_SHA256 = (
    "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
)
GATE0_RULING_SHA256 = (
    "EDD794B21221EB7EFA9F01E67BF52732A993B83C74D8CE040C88A316C0528B71"
)
INTERFACE_REGISTER_SHA256 = (
    "3BF778FB23843976889EFA0909941EBE8EBCDE90BA142492CA37AD757082225E"
)
PDR_MOUNT_SHA256 = (
    "BBD4F7C0C61652879F8C1DBF1F906A91526265105BF1ED5F145C1FA01F1F0959"
)
PDR_LOAD_INTERFACE_SHA256 = (
    "262B4D898CA8DA49AB78EEE28E5AF254F6774DCE8416A947BBF79E5F1A76805F"
)
SOURCE_FILES = {
    "accepted_urdf": (
        WORKSPACE_ROOT
        / "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
        EXPECTED_URDF_SHA256,
    ),
    "gate0_ruling": (
        WORKSPACE_ROOT
        / "20_engineering/design_inputs/v2_2_physical_architecture/gate_0_ruling_record.yaml",
        GATE0_RULING_SHA256,
    ),
    "interface_register": (
        WORKSPACE_ROOT
        / "20_engineering/design_inputs/v2_system_mechanical/03_mechanical_interfaces/V2_interface_register.yaml",
        INTERFACE_REGISTER_SHA256,
    ),
    "pdr_mount": (
        WORKSPACE_ROOT
        / "20_engineering/design_review/V2_PDR_package/05_robot_mount/robot_mount_preliminary_design.md",
        PDR_MOUNT_SHA256,
    ),
    "pdr_load_interface": (
        WORKSPACE_ROOT
        / "20_engineering/design_review/V2_PDR_package/05_robot_mount/robot_mount_load_interface.yaml",
        PDR_LOAD_INTERFACE_SHA256,
    ),
}

ASSEMBLY_NAME = "B601_BASE_ADAPTER"
DRAWING_NAME = "B601_BASE_ADAPTER_REFERENCE"

PARTS: tuple[dict[str, Any], ...] = (
    {
        "key": "FLANGE",
        "name": "B50_BASE_ADAPTER_UPPER_FLANGE_ENVELOPE",
        "shape": "rectangle",
        "target_x_mm": [183.0, 198.0],
        "y_mm": 160.0,
        "z_mm": 160.0,
        "role": "B601_UPPER_INSTALL_FLANGE_REFERENCE_ENVELOPE",
    },
    {
        "key": "PLATE",
        "name": "B50_BASE_ADAPTER_SPREADER_PLATE_ENVELOPE",
        "shape": "rectangle",
        "target_x_mm": [171.0, 183.0],
        "y_mm": 160.0,
        "z_mm": 160.0,
        "role": "SPACECRAFT_LOAD_SPREADING_PLATE_REFERENCE_ENVELOPE",
    },
    {
        "key": "BOSS",
        "name": "B50_BASE_ADAPTER_PRIMARY_BOSS_ENVELOPE",
        "shape": "circle",
        "target_x_mm": [156.0, 171.0],
        "diameter_mm": 100.0,
        "role": "PRIMARY_STRUCTURE_BOSS_REFERENCE_ENVELOPE",
    },
)


def _m(mm: float) -> float:
    return float(mm) / 1000.0


def _run_root(run_id: str) -> Path:
    if not run_id or any(
        char
        not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-"
        for char in run_id
    ):
        raise Phase0Error(f"invalid run id: {run_id!r}")
    return require_within(RUNS_ROOT / run_id, RUNS_ROOT, "native_run_root")


def _verify_sources() -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for name, (path, expected_hash) in SOURCE_FILES.items():
        if not path.is_file():
            raise Phase0Error(f"required source is missing: {path}")
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            raise Phase0Error(
                f"required source hash drift for {name}: "
                f"{actual_hash} != {expected_hash}"
            )
        records[name] = {
            "path": path.relative_to(WORKSPACE_ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": actual_hash,
            "editable": False,
        }
    return records


def _select_right_plane(model: Any) -> str:
    model.ClearSelection2(True)
    for name in ("右视基准面", "Right Plane"):
        if model.Extension.SelectByID2(
            name, "PLANE", 0.0, 0.0, 0.0, False, 0, None, 0
        ):
            return name
    raise Phase0Error("cannot select Right Plane in the pinned part template")


def _extrude_on_right_plane(
    session: SolidWorksSession,
    model: Any,
    definition: dict[str, Any],
) -> dict[str, Any]:
    plane = _select_right_plane(model)
    sketch = model.SketchManager
    sketch.InsertSketch(True)
    if definition["shape"] == "rectangle":
        created = sketch.CreateCenterRectangle(
            0.0,
            0.0,
            0.0,
            _m(0.5 * definition["y_mm"]),
            _m(0.5 * definition["z_mm"]),
            0.0,
        )
        if not created:
            raise Phase0Error(f"rectangle creation failed: {definition['key']}")
    elif definition["shape"] == "circle":
        created = sketch.CreateCircleByRadius(
            0.0,
            0.0,
            0.0,
            _m(0.5 * definition["diameter_mm"]),
        )
        if created is None:
            raise Phase0Error(f"circle creation failed: {definition['key']}")
    else:  # pragma: no cover - static table contract
        raise Phase0Error(f"unsupported shape: {definition['shape']}")
    sketch.InsertSketch(True)
    thickness = definition["target_x_mm"][1] - definition["target_x_mm"][0]
    feature = model.FeatureManager.FeatureExtrusion2(
        True,
        False,
        False,
        0,
        0,
        _m(thickness),
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
        raise Phase0Error(f"extrusion failed: {definition['key']}")
    try:
        session.cast(feature, "IFeature").Name = (
            f"{definition['key']}_REFERENCE_ENVELOPE_EXTRUDE"
        )
    except Exception:
        pass
    if not model.ForceRebuild3(False):
        raise Phase0Error(f"part rebuild failed: {definition['key']}")
    return {"selected_plane": plane, "thickness_mm": thickness}


def _validate_part_box(
    definition: dict[str, Any], facts: dict[str, Any]
) -> None:
    box = facts.get("bounding_box_mm")
    if facts.get("solid_body_count") != 1 or not isinstance(box, list) or len(box) != 6:
        raise Phase0Error(f"invalid part facts for {definition['key']}: {facts}")
    dimensions = [
        float(box[3] - box[0]),
        float(box[4] - box[1]),
        float(box[5] - box[2]),
    ]
    thickness = definition["target_x_mm"][1] - definition["target_x_mm"][0]
    if definition["shape"] == "rectangle":
        expected = [thickness, definition["y_mm"], definition["z_mm"]]
    else:
        expected = [thickness, definition["diameter_mm"], definition["diameter_mm"]]
    for actual, wanted in zip(dimensions, expected):
        if abs(actual - wanted) > 0.02:
            raise Phase0Error(
                f"{definition['key']} bbox dimension {actual} != {wanted} mm; "
                f"facts={facts}"
            )


def _common_properties(run_id: str) -> dict[str, Any]:
    return {
        "RUN_ID": run_id,
        "CANDIDATE_ID": "COMP-PROT-03-A4-B5.0-B601-SPACE-MANIPULATOR-ENGINEERING-CAD",
        "DESIGN_STATUS": "DESIGN_PROPOSAL_REFERENCE_ENVELOPE",
        "PHYSICAL_QUALIFICATION": "FALSE",
        "MANUFACTURING_AUTHORITY": "NONE",
        "MASS_AUTHORITY": "EXCLUDED_ACCEPTED_URDF_ONLY",
        "MATERIAL": "UNKNOWN",
        "INSTALL_LOADS_6D": "UNKNOWN_BLOCKED",
        "BOLT_PATTERN": "TBD",
        "LOCATING_PINS": "TBD",
        "FASTENER_SPEC_PRELOAD_LOCKING": "TBD",
        "TOLERANCE_AND_SURFACE": "TBD",
        "CONNECTOR_AND_HARNESS_PENETRATION": "TBD",
        "THERMAL_ISOLATION_AND_GROUND_BOND": "TBD",
        "ACCEPTED_URDF_SHA256": EXPECTED_URDF_SHA256,
        "GATE0_RULING_SHA256": GATE0_RULING_SHA256,
        "INTERFACE_REGISTER_SHA256": INTERFACE_REGISTER_SHA256,
        "PDR_MOUNT_SHA256": PDR_MOUNT_SHA256,
        "PDR_LOAD_INTERFACE_SHA256": PDR_LOAD_INTERFACE_SHA256,
        "TRACK_POLICY": "DUAL_TRACK_EXPLICIT_NO_SILENT_MERGE",
        "DISPLAY_MOUNT_X_MM": "198.0",
        "DYNAMICS_T_SM_X_MM": "185.25",
        "TRACK_DELTA_MM": "12.75",
    }


def _build_part(
    session: SolidWorksSession,
    run_root: Path,
    run_id: str,
    definition: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    target = run_root / "10_reference_parts" / f"{definition['name']}.SLDPRT"
    model = session.new_document("part")
    geometry = _extrude_on_right_plane(session, model, definition)
    properties = {
        **_common_properties(run_id),
        "ASSET_ROLE": definition["role"],
        "SHAPE": definition["shape"].upper(),
        "TARGET_X_RANGE_MM": (
            f"{definition['target_x_mm'][0]},{definition['target_x_mm'][1]}"
        ),
        "NO_HOLES_OR_FASTENERS": "TRUE",
    }
    if definition["shape"] == "rectangle":
        properties["REFERENCE_ENVELOPE_YZ_MM"] = (
            f"{definition['y_mm']}x{definition['z_mm']}"
        )
    else:
        properties["REFERENCE_ENVELOPE_DIAMETER_MM"] = str(
            definition["diameter_mm"]
        )
    session.set_text_properties(model, properties)
    facts = _part_facts(session, model)
    _validate_part_box(definition, facts)
    save = session.save_as(model, target)
    session.close_all_documents()
    return target, {
        "definition": definition,
        "geometry": geometry,
        "facts": facts,
        "save": save,
    }


def _identity_translation(tx: float, ty: float, tz: float) -> list[list[float]]:
    return [
        [1.0, 0.0, 0.0, float(tx)],
        [0.0, 1.0, 0.0, float(ty)],
        [0.0, 0.0, 1.0, float(tz)],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _build_assembly(
    session: SolidWorksSession,
    run_root: Path,
    run_id: str,
    part_results: dict[str, tuple[Path, dict[str, Any]]],
) -> tuple[Path, dict[str, Any]]:
    target = run_root / "20_assembly" / f"{ASSEMBLY_NAME}.SLDASM"
    model = session.new_document("assembly")
    components: list[dict[str, Any]] = []
    for definition in PARTS:
        part_path, record = part_results[definition["key"]]
        box = record["facts"]["bounding_box_mm"]
        target_min = float(definition["target_x_mm"][0])
        target_center_y = 0.0
        target_center_z = 0.0
        local_center_y = 0.5 * (float(box[1]) + float(box[4]))
        local_center_z = 0.5 * (float(box[2]) + float(box[5]))
        matrix = _identity_translation(
            _m(target_min - float(box[0])),
            _m(target_center_y - local_center_y),
            _m(target_center_z - local_center_z),
        )
        component = _add_component(
            session,
            model,
            part_path,
            matrix,
            f"{definition['key']}_REFERENCE_ENVELOPE",
        )
        component["expected_global_x_range_mm"] = definition["target_x_mm"]
        components.append(component)
    session.set_text_properties(
        model,
        {
            **_common_properties(run_id),
            "ASSET_ROLE": "B601_BASE_ADAPTER_REFERENCE_ASSEMBLY",
            "ASSEMBLY_DOF_AUTHORITY": "NONE_FIXED_REFERENCE_ENVELOPES",
            "LOAD_PATH": (
                "B601_A0_TO_UPPER_FLANGE_TO_SPREADER_PLATE_TO_PRIMARY_BOSS_"
                "TO_TASK_FACE_FRONT_FRAME_LONGERONS_PRIMARY_STRUCTURE"
            ),
            "COMPONENT_COUNT": "3",
            "REFERENCE_STACK_X_MM": "BOSS[156,171];PLATE[171,183];FLANGE[183,198]",
            "NO_PHYSICAL_HOLE_PATTERN": "TRUE",
        },
    )
    if not model.ForceRebuild3(False):
        raise Phase0Error("base-adapter assembly rebuild failed")
    save = session.save_as(model, target)
    session.close_all_documents()
    return target, {"components": components, "save": save}


def _build_drawing(
    session: SolidWorksSession,
    run_root: Path,
    run_id: str,
    assembly_path: Path,
) -> tuple[Path, dict[str, Any]]:
    target = run_root / "40_drawings" / f"{DRAWING_NAME}.SLDDRW"
    _, assembly_open = session.open_document(assembly_path, "assembly")
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
        raise Phase0Error("cannot create model-backed base-adapter drawing view")
    session.set_text_properties(
        drawing_model,
        {
            **_common_properties(run_id),
            "ASSET_ROLE": "B601_BASE_ADAPTER_REFERENCE_DRAWING",
            "DRAWING_STATUS": "REFERENCE_ENVELOPE_ONLY_NOT_FOR_MANUFACTURE",
        },
    )
    if not drawing_model.ForceRebuild3(False):
        raise Phase0Error("base-adapter drawing rebuild failed")
    sheet = session.cast(drawing_doc.GetCurrentSheet(), "ISheet")
    views = list(sheet.GetViews() or [])
    if not views:
        raise Phase0Error("base-adapter drawing contains no views")
    save = session.save_as(drawing_model, target)
    session.close_all_documents()
    return target, {
        "assembly_open": assembly_open,
        "placed_model_view": placed_name,
        "sheet_view_count": len(views),
        "save": save,
    }


def _export_step(
    session: SolidWorksSession,
    run_root: Path,
    assembly_path: Path,
) -> tuple[Path, dict[str, Any]]:
    target = run_root / "30_exports" / f"{DRAWING_NAME}.step"
    model, open_record = session.open_document(assembly_path, "assembly")
    if not model.ForceRebuild3(False):
        raise Phase0Error("base-adapter assembly rebuild failed before STEP export")
    save = session.save_as(model, target)
    session.close_all_documents()
    return target, {"assembly_open": open_record, "save": save}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_contract = _verify_sources()
    run_root = _run_root(args.run_id)
    if run_root.exists():
        raise SystemExit(f"run root already exists; overwrite forbidden: {run_root}")
    run_root.mkdir(parents=True, exist_ok=False)
    report_path = run_root / "evidence/base_adapter_reference_build.json"
    report: dict[str, Any] = {
        "schema": "SER_B50_BASE_ADAPTER_REFERENCE_BUILD_V1",
        "generated_utc": utc_now(),
        "run_id": args.run_id,
        "run_root": str(run_root),
        "status": "B5_0_BASE_ADAPTER_REFERENCE_BUILD_HOLD",
        "design_status": "DESIGN_PROPOSAL_REFERENCE_ENVELOPE",
        "physical_qualification": False,
        "manufacturing_authority": "NONE",
        "mass_authority": "EXCLUDED_ACCEPTED_URDF_ONLY",
        "source_contract": source_contract,
        "parts": {},
        "artifacts": {},
    }
    session: SolidWorksSession | None = None
    try:
        part_results: dict[str, tuple[Path, dict[str, Any]]] = {}
        with SolidWorksSession(run_root, visible=False) as session:
            report["session_start"] = session.info()
            for definition in PARTS:
                part_path, part_record = _build_part(
                    session, run_root, args.run_id, definition
                )
                part_results[definition["key"]] = (part_path, part_record)
                report["parts"][definition["key"]] = part_record
            assembly_path, report["assembly"] = _build_assembly(
                session, run_root, args.run_id, part_results
            )
            drawing_path, report["drawing"] = _build_drawing(
                session, run_root, args.run_id, assembly_path
            )
            step_path, report["step_export"] = _export_step(
                session, run_root, assembly_path
            )
        report["session_end"] = session.info()
        for key, path in {
            **{
                f"part_{key.lower()}": value[0]
                for key, value in part_results.items()
            },
            "assembly": assembly_path,
            "drawing": drawing_path,
            "step": step_path,
        }.items():
            report["artifacts"][key] = artifact_record(path, run_root)
        report["status"] = "B5_0_BASE_ADAPTER_REFERENCE_BUILD_PASS_WITH_PHYSICAL_HOLD"
    except Exception as exc:
        report["exception"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        if session is not None:
            report["session_end"] = session.info()
    finally:
        report["completed_utc"] = utc_now()
        write_json_once(report_path, report, run_root)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return (
        0
        if report["status"]
        == "B5_0_BASE_ADAPTER_REFERENCE_BUILD_PASS_WITH_PHYSICAL_HOLD"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
