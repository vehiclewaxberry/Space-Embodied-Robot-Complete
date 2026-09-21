"""Cold-verify the B5.0 base-adapter reference-envelope SolidWorks run."""
from __future__ import annotations

import argparse
import json
import math
import sys
import traceback
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from build_b50_base_adapter_reference import (  # noqa: E402
    ASSEMBLY_NAME,
    DRAWING_NAME,
    PARTS,
    RUNS_ROOT,
    _common_properties,
    _verify_sources,
)
from sw_b50_core import (  # noqa: E402
    Phase0Error,
    SolidWorksSession,
    artifact_record,
    get_com_member,
    is_within,
    require_within,
    sha256_file,
    utc_now,
    validate_run_id,
    write_json_once,
)
from verify_b50_native_q0 import (  # noqa: E402
    _as_list,
    _auxiliary_external_reference_count,
    _body_facts,
    _component_path,
    _external_reference_count,
    _max_abs_error,
    _read_and_match_properties,
    _three_d_interconnect_features,
)


def _run_root(run_id: str) -> Path:
    validate_run_id(run_id)
    return require_within(RUNS_ROOT / run_id, RUNS_ROOT, "native_run_root")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise Phase0Error(f"missing JSON receipt: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _part_path(run_root: Path, definition: dict[str, Any]) -> Path:
    return run_root / "10_reference_parts" / f"{definition['name']}.SLDPRT"


def _required_paths(run_root: Path) -> dict[str, Path]:
    paths = {
        "build_receipt": run_root / "evidence/base_adapter_reference_build.json",
        "assembly": run_root / "20_assembly" / f"{ASSEMBLY_NAME}.SLDASM",
        "drawing": run_root / "40_drawings" / f"{DRAWING_NAME}.SLDDRW",
        "step": run_root / "30_exports" / f"{DRAWING_NAME}.step",
    }
    paths.update(
        {
            f"part_{definition['key']}": _part_path(run_root, definition)
            for definition in PARTS
        }
    )
    return paths


def _artifact_paths(paths: dict[str, Path]) -> dict[str, Path]:
    return {
        name: path
        for name, path in paths.items()
        if name != "build_receipt"
    }


def _critical_properties(
    run_id: str, definition: dict[str, Any]
) -> dict[str, str]:
    common = _common_properties(run_id)
    return {
        "RUN_ID": run_id,
        "DESIGN_STATUS": str(common["DESIGN_STATUS"]),
        "PHYSICAL_QUALIFICATION": str(common["PHYSICAL_QUALIFICATION"]),
        "MANUFACTURING_AUTHORITY": str(common["MANUFACTURING_AUTHORITY"]),
        "MASS_AUTHORITY": str(common["MASS_AUTHORITY"]),
        "MATERIAL": "UNKNOWN",
        "INSTALL_LOADS_6D": "UNKNOWN_BLOCKED",
        "BOLT_PATTERN": "TBD",
        "LOCATING_PINS": "TBD",
        "FASTENER_SPEC_PRELOAD_LOCKING": "TBD",
        "TOLERANCE_AND_SURFACE": "TBD",
        "ACCEPTED_URDF_SHA256": str(common["ACCEPTED_URDF_SHA256"]),
        "TRACK_POLICY": "DUAL_TRACK_EXPLICIT_NO_SILENT_MERGE",
        "DISPLAY_MOUNT_X_MM": "198.0",
        "DYNAMICS_T_SM_X_MM": "185.25",
        "TRACK_DELTA_MM": "12.75",
        "ASSET_ROLE": str(definition["role"]),
        "TARGET_X_RANGE_MM": (
            f"{definition['target_x_mm'][0]},{definition['target_x_mm'][1]}"
        ),
        "NO_HOLES_OR_FASTENERS": "TRUE",
    }


def _verify_part(
    session: SolidWorksSession,
    run_root: Path,
    path: Path,
    run_id: str,
    definition: dict[str, Any],
) -> dict[str, Any]:
    before_hash = sha256_file(path)
    model, open_record = session.open_document(path, "part")
    try:
        facts = _body_facts(session, model)
        if facts["solid_body_count"] != 1:
            raise Phase0Error(
                f"{definition['key']} body count is not 1: {facts}"
            )
        bbox = facts["bounding_box_mm"]
        dimensions = [
            bbox["max"][index] - bbox["min"][index] for index in range(3)
        ]
        thickness = (
            definition["target_x_mm"][1] - definition["target_x_mm"][0]
        )
        expected = (
            [thickness, definition["y_mm"], definition["z_mm"]]
            if definition["shape"] == "rectangle"
            else [
                thickness,
                definition["diameter_mm"],
                definition["diameter_mm"],
            ]
        )
        max_dimension_error = max(
            abs(actual - wanted)
            for actual, wanted in zip(dimensions, expected)
        )
        if max_dimension_error > 0.02:
            raise Phase0Error(
                f"{definition['key']} dimension error {max_dimension_error} mm"
            )
        external_count = _external_reference_count(model)
        auxiliary_count = _auxiliary_external_reference_count(model)
        interconnect = _three_d_interconnect_features(session, model)
        if external_count != 0 or auxiliary_count != 0 or interconnect:
            raise Phase0Error(
                f"{definition['key']} external reference contamination: "
                f"external={external_count}, auxiliary={auxiliary_count}, "
                f"interconnect={interconnect}"
            )
        properties = _read_and_match_properties(
            session,
            model,
            _critical_properties(run_id, definition),
            definition["key"],
        )
    finally:
        session.close_document(model)
    after_hash = sha256_file(path)
    if after_hash != before_hash:
        raise Phase0Error(
            f"read-only verification changed {definition['key']} hash"
        )
    return {
        "open": open_record,
        "artifact": artifact_record(path, run_root),
        "facts": facts,
        "expected_dimensions_mm": expected,
        "max_dimension_error_mm": max_dimension_error,
        "external_reference_count": external_count,
        "auxiliary_external_reference_count": auxiliary_count,
        "three_d_interconnect_features": interconnect,
        "custom_properties": properties,
        "hash_unchanged": True,
    }


def _verify_assembly(
    session: SolidWorksSession,
    run_root: Path,
    path: Path,
    run_id: str,
    build: dict[str, Any],
) -> dict[str, Any]:
    before_hash = sha256_file(path)
    model, open_record = session.open_document(path, "assembly")
    try:
        assembly = session.cast(model, "IAssemblyDoc")
        components = _as_list(assembly.GetComponents(True))
        if len(components) != 3:
            raise Phase0Error(
                f"base-adapter assembly component count {len(components)} != 3"
            )
        expected_by_path: dict[Path, dict[str, Any]] = {}
        for record in build["assembly"]["components"]:
            component_path = (run_root / record["part_path"]).resolve()
            expected_by_path[component_path] = record
        observed: list[Path] = []
        component_records: list[dict[str, Any]] = []
        for raw_component in components:
            component = session.cast(raw_component, "IComponent2")
            component_path = _component_path(
                str(get_com_member(component, "GetPathName") or ""), path
            )
            observed.append(component_path)
            if component_path not in expected_by_path:
                raise Phase0Error(
                    f"unexpected base-adapter component: {component_path}"
                )
            if not is_within(component_path, run_root):
                raise Phase0Error(
                    f"base-adapter component escapes run root: {component_path}"
                )
            if component_path.suffix.lower() != ".sldprt":
                raise Phase0Error(
                    f"component is not native SLDPRT: {component_path}"
                )
            fixed = bool(get_com_member(component, "IsFixed"))
            if not fixed:
                raise Phase0Error(
                    f"reference-envelope component is not fixed: {component_path}"
                )
            transform = get_com_member(component, "Transform2")
            actual = [
                float(value)
                for value in _as_list(get_com_member(transform, "ArrayData"))
            ]
            expected = [
                float(value)
                for value in expected_by_path[component_path][
                    "math_transform_array"
                ]
            ]
            error = _max_abs_error(actual, expected)
            if error > 1.0e-9:
                raise Phase0Error(
                    f"component transform error {error}: {component_path}"
                )
            component_records.append(
                {
                    "path": component_path.relative_to(run_root).as_posix(),
                    "fixed": fixed,
                    "math_transform_array": actual,
                    "expected_math_transform_array": expected,
                    "max_abs_error": error,
                }
            )
        if len(set(observed)) != 3 or set(observed) != set(expected_by_path):
            raise Phase0Error("base-adapter component path set mismatch")
        assembly_properties = {
            "RUN_ID": run_id,
            "ASSET_ROLE": "B601_BASE_ADAPTER_REFERENCE_ASSEMBLY",
            "DESIGN_STATUS": "DESIGN_PROPOSAL_REFERENCE_ENVELOPE",
            "PHYSICAL_QUALIFICATION": "FALSE",
            "MANUFACTURING_AUTHORITY": "NONE",
            "MASS_AUTHORITY": "EXCLUDED_ACCEPTED_URDF_ONLY",
            "ASSEMBLY_DOF_AUTHORITY": "NONE_FIXED_REFERENCE_ENVELOPES",
            "COMPONENT_COUNT": "3",
            "REFERENCE_STACK_X_MM": (
                "BOSS[156,171];PLATE[171,183];FLANGE[183,198]"
            ),
            "NO_PHYSICAL_HOLE_PATTERN": "TRUE",
        }
        properties = _read_and_match_properties(
            session,
            model,
            assembly_properties,
            "base-adapter assembly",
        )
    finally:
        session.close_document(model)
    after_hash = sha256_file(path)
    if after_hash != before_hash:
        raise Phase0Error("read-only assembly verification changed file hash")
    return {
        "open": open_record,
        "artifact": artifact_record(path, run_root),
        "component_count": len(component_records),
        "all_components_native_sldprt": True,
        "all_components_inside_run_root": True,
        "all_components_fixed": True,
        "components": component_records,
        "max_transform_abs_error": max(
            item["max_abs_error"] for item in component_records
        ),
        "custom_properties": properties,
        "hash_unchanged": True,
    }


def _verify_drawing(
    session: SolidWorksSession,
    run_root: Path,
    path: Path,
    assembly_path: Path,
    run_id: str,
) -> dict[str, Any]:
    before_hash = sha256_file(path)
    model, open_record = session.open_document(path, "drawing")
    try:
        drawing = session.cast(model, "IDrawingDoc")
        sheet = session.cast(drawing.GetCurrentSheet(), "ISheet")
        views = _as_list(sheet.GetViews())
        if not views:
            raise Phase0Error("base-adapter drawing contains no views")
        records: list[dict[str, Any]] = []
        model_backed = 0
        for raw_view in views:
            view = session.cast(raw_view, "IView")
            referenced = str(
                get_com_member(view, "GetReferencedModelName") or ""
            ).strip()
            referenced_relative = None
            if referenced:
                referenced_path = _component_path(referenced, path)
                if referenced_path != assembly_path.resolve():
                    raise Phase0Error(
                        f"drawing references unexpected model: {referenced_path}"
                    )
                if not is_within(referenced_path, run_root):
                    raise Phase0Error(
                        f"drawing reference escapes run root: {referenced_path}"
                    )
                referenced_relative = referenced_path.relative_to(
                    run_root
                ).as_posix()
                model_backed += 1
            records.append(
                {
                    "name": str(get_com_member(view, "GetName2") or ""),
                    "type": int(view.Type),
                    "referenced_model": referenced_relative,
                }
            )
        if model_backed < 1:
            raise Phase0Error("drawing has no model-backed view")
        properties = _read_and_match_properties(
            session,
            model,
            {
                "RUN_ID": run_id,
                "ASSET_ROLE": "B601_BASE_ADAPTER_REFERENCE_DRAWING",
                "DRAWING_STATUS": "REFERENCE_ENVELOPE_ONLY_NOT_FOR_MANUFACTURE",
                "MANUFACTURING_AUTHORITY": "NONE",
                "MASS_AUTHORITY": "EXCLUDED_ACCEPTED_URDF_ONLY",
            },
            "base-adapter drawing",
        )
    finally:
        session.close_document(model)
    after_hash = sha256_file(path)
    if after_hash != before_hash:
        raise Phase0Error("read-only drawing verification changed file hash")
    return {
        "open": open_record,
        "artifact": artifact_record(path, run_root),
        "view_count": len(records),
        "model_backed_view_count": model_backed,
        "views": records,
        "custom_properties": properties,
        "hash_unchanged": True,
    }


def _verify_step(path: Path, run_root: Path) -> dict[str, Any]:
    try:
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.STEPControl import STEPControl_Reader
        from OCP.TopAbs import TopAbs_SOLID
        from OCP.TopExp import TopExp_Explorer
    except Exception as exc:
        raise Phase0Error(f"OCP STEP reader unavailable: {exc!r}") from exc
    before_hash = sha256_file(path)
    reader = STEPControl_Reader()
    status = reader.ReadFile(str(path))
    if status != IFSelect_RetDone:
        raise Phase0Error(f"STEP ReadFile failed: {status!r}")
    transferred = int(reader.TransferRoots())
    shape = reader.OneShape()
    if transferred <= 0 or shape.IsNull():
        raise Phase0Error("STEP transfer produced no valid shape")
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    values = [float(value) for value in box.Get()]
    if len(values) != 6 or not all(math.isfinite(value) for value in values):
        raise Phase0Error(f"invalid STEP bbox: {values}")
    bbox = {"min": values[:3], "max": values[3:]}
    solid_count = 0
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    while explorer.More():
        solid_count += 1
        explorer.Next()
    if solid_count != 3:
        raise Phase0Error(f"STEP solid count {solid_count} != 3")
    expected = {
        "min": [156.0, -80.0, -80.0],
        "max": [198.0, 80.0, 80.0],
    }
    errors = {
        "min": [
            abs(bbox["min"][index] - expected["min"][index])
            for index in range(3)
        ],
        "max": [
            abs(bbox["max"][index] - expected["max"][index])
            for index in range(3)
        ],
    }
    max_error = max(errors["min"] + errors["max"])
    if max_error > 0.02:
        raise Phase0Error(f"STEP bbox error {max_error} mm > 0.02 mm")
    after_hash = sha256_file(path)
    if after_hash != before_hash:
        raise Phase0Error("OCP STEP verification changed file hash")
    return {
        **artifact_record(path, run_root),
        "ocp_read": "PASS",
        "transferred_roots": transferred,
        "solid_count": solid_count,
        "bbox_mm": bbox,
        "expected_bbox_mm": expected,
        "bbox_abs_errors_mm": errors,
        "max_bbox_abs_error_mm": max_error,
        "hash_unchanged": True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_root = _run_root(args.run_id)
    paths = _required_paths(run_root)
    output = run_root / "evidence/base_adapter_reference_cold_verify.json"
    report: dict[str, Any] = {
        "schema": "SER_B50_BASE_ADAPTER_REFERENCE_COLD_VERIFY_V1",
        "generated_utc": utc_now(),
        "run_id": args.run_id,
        "status": "B5_0_BASE_ADAPTER_REFERENCE_COLD_VERIFY_HOLD",
        "design_status": "DESIGN_PROPOSAL_REFERENCE_ENVELOPE",
        "physical_qualification": False,
        "manufacturing_authority": "NONE",
        "mass_authority": "EXCLUDED_ACCEPTED_URDF_ONLY",
    }
    session: SolidWorksSession | None = None
    try:
        for path in paths.values():
            if not path.is_file():
                raise Phase0Error(f"required artifact missing: {path}")
        source_contract = _verify_sources()
        build = _load_json(paths["build_receipt"])
        if build.get("status") != (
            "B5_0_BASE_ADAPTER_REFERENCE_BUILD_PASS_WITH_PHYSICAL_HOLD"
        ):
            raise Phase0Error("build receipt is not PASS_WITH_PHYSICAL_HOLD")
        if build.get("source_contract") != source_contract:
            raise Phase0Error("build source contract does not match live sources")
        for name, expected in build["artifacts"].items():
            path_key = (
                name.replace("part_", "part_").upper()
                if name.startswith("part_")
                else name
            )
            if name.startswith("part_"):
                path_key = f"part_{name.removeprefix('part_').upper()}"
            actual = artifact_record(paths[path_key], run_root)
            if actual != expected:
                raise Phase0Error(
                    f"build artifact reconciliation failed for {name}: "
                    f"{actual} != {expected}"
                )
        artifacts = _artifact_paths(paths)
        initial_hashes = {
            name: sha256_file(path) for name, path in artifacts.items()
        }
        report["source_contract"] = source_contract
        report["build_receipt"] = artifact_record(
            paths["build_receipt"], run_root
        )
        report["initial_hashes"] = initial_hashes
        with SolidWorksSession(run_root, visible=False) as session:
            report["session_start"] = session.info()
            report["parts"] = {
                definition["key"]: _verify_part(
                    session,
                    run_root,
                    paths[f"part_{definition['key']}"],
                    args.run_id,
                    definition,
                )
                for definition in PARTS
            }
            report["assembly"] = _verify_assembly(
                session,
                run_root,
                paths["assembly"],
                args.run_id,
                build,
            )
            report["drawing"] = _verify_drawing(
                session,
                run_root,
                paths["drawing"],
                paths["assembly"],
                args.run_id,
            )
        report["session_end"] = session.info()
        report["step"] = _verify_step(paths["step"], run_root)
        final_hashes = {
            name: sha256_file(path) for name, path in artifacts.items()
        }
        if final_hashes != initial_hashes:
            raise Phase0Error("cold verification changed one or more artifacts")
        report["final_hashes"] = final_hashes
        report["artifact_hashes_unchanged_at_exit"] = True
        report["remaining_holds"] = [
            "Published B601 bolt pattern, hole count, hole diameter, and bolt circle are TBD.",
            "Locating pins, mating stack-up, tolerances, surface requirements, fastener preload, and locking are UNKNOWN.",
            "Materials, thermal isolation, ground bond, connectors, harness penetration, and bend radius are UNKNOWN.",
            "All six-dimensional install/load cases remain UNKNOWN_BLOCKED.",
            "The three solids are reference envelopes with no physical holes or fasteners.",
            "No mass, strength, stiffness, modal, launch, manufacturing, or flight claim is authorized.",
        ]
        report["status"] = (
            "B5_0_BASE_ADAPTER_REFERENCE_COLD_VERIFY_PASS_WITH_PHYSICAL_HOLD"
        )
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
        write_json_once(output, report, run_root)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return (
        0
        if report["status"]
        == "B5_0_BASE_ADAPTER_REFERENCE_COLD_VERIFY_PASS_WITH_PHYSICAL_HOLD"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
