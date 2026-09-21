"""Cold-reopen and verify one immutable B5.0 SolidWorks Phase0 smoke run."""
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
    artifact_record,
    get_com_member,
    is_within,
    phase0_run_root,
    sha256_file,
    utc_now,
    validate_run_id,
    write_json_once,
)


PART_NAME = "PHASE0_COM_SMOKE_PART"
ASSEMBLY_NAME = "PHASE0_COM_SMOKE_ASSEMBLY"
DRAWING_NAME = "PHASE0_COM_SMOKE_DRAWING"


def _required_paths(run_root: Path) -> dict[str, Path]:
    return {
        "part": run_root / "native" / "parts" / f"{PART_NAME}.SLDPRT",
        "assembly": (
            run_root / "native" / "assembly" / f"{ASSEMBLY_NAME}.SLDASM"
        ),
        "drawing": (
            run_root / "native" / "drawings" / f"{DRAWING_NAME}.SLDDRW"
        ),
        "step": run_root / "exports" / f"{ASSEMBLY_NAME}.step",
        "build_report": run_root / "evidence" / "phase0_build_report.json",
    }


def _load_and_check_build_report(
    run_root: Path, paths: dict[str, Path]
) -> dict[str, Any]:
    with paths["build_report"].open("r", encoding="utf-8") as stream:
        report = json.load(stream)
    if report.get("status") != "PHASE0_TOOL_GATE_BUILD_PASS":
        raise Phase0Error(
            f"build report is not PASS: {report.get('status')!r}"
        )
    if Path(report.get("run_root", "")).resolve() != run_root.resolve():
        raise Phase0Error("build report run_root does not match requested run")
    for name in ("part", "assembly", "drawing", "step"):
        expected = report.get("artifacts", {}).get(name)
        if not isinstance(expected, dict):
            raise Phase0Error(f"build report lacks artifact record: {name}")
        actual = artifact_record(paths[name], run_root)
        if actual["path"] != expected.get("path"):
            raise Phase0Error(f"{name} relative path changed after build")
        if actual["bytes"] != expected.get("bytes"):
            raise Phase0Error(f"{name} byte count changed after build")
        if actual["sha256"] != expected.get("sha256"):
            raise Phase0Error(f"{name} hash changed after build")
    return report


def _verify_part(
    session: SolidWorksSession, run_root: Path, path: Path
) -> dict[str, Any]:
    before_hash = sha256_file(path)
    model, open_record = session.open_document(path, "part")
    part = session.cast(model, "IPartDoc")
    bodies = list(part.GetBodies2(0, False) or [])
    box = [float(value) * 1000.0 for value in part.GetPartBox(True)]
    role = session.read_text_property(model, "ASSET_ROLE")
    mass_authority = session.read_text_property(model, "MASS_AUTHORITY")
    if not bodies:
        raise Phase0Error("cold-reopened part contains no solid body")
    if min(box[3] - box[0], box[4] - box[1], box[5] - box[2]) <= 0.0:
        raise Phase0Error(f"cold-reopened part has degenerate box: {box}")
    if role != "SOLIDWORKS_AUTOMATION_SMOKE_TEST_ONLY":
        raise Phase0Error(f"part role property mismatch: {role!r}")
    if mass_authority != "EXCLUDED":
        raise Phase0Error(
            f"part mass authority is not excluded: {mass_authority!r}"
        )
    session.close_document(model)
    after_hash = sha256_file(path)
    if after_hash != before_hash:
        raise Phase0Error("read-only part verification changed the file hash")
    return {
        "open": open_record,
        "solid_body_count": len(bodies),
        "bounding_box_mm": box,
        "asset_role": role,
        "mass_authority": mass_authority,
        "hash_unchanged": True,
    }


def _verify_assembly(
    session: SolidWorksSession,
    run_root: Path,
    path: Path,
    expected_part: Path,
) -> dict[str, Any]:
    before_hash = sha256_file(path)
    model, open_record = session.open_document(path, "assembly")
    assembly = session.cast(model, "IAssemblyDoc")
    components = list(assembly.GetComponents(True) or [])
    if len(components) != 1:
        raise Phase0Error(
            f"smoke assembly must contain exactly one component, got {len(components)}"
        )
    references: list[dict[str, Any]] = []
    for component in components:
        component = session.cast(component, "IComponent2")
        raw_path = str(get_com_member(component, "GetPathName") or "")
        component_path = Path(raw_path).resolve()
        if component_path != expected_part.resolve():
            raise Phase0Error(
                f"assembly references unexpected component: {component_path}"
            )
        if not is_within(component_path, run_root):
            raise Phase0Error(
                f"assembly component escapes run root: {component_path}"
            )
        references.append(
            {
                "path": component_path.relative_to(run_root).as_posix(),
                "exists": component_path.is_file(),
            }
        )
    role = session.read_text_property(model, "ASSET_ROLE")
    if role != "SOLIDWORKS_AUTOMATION_SMOKE_TEST_ONLY":
        raise Phase0Error(f"assembly role property mismatch: {role!r}")
    session.close_document(model)
    after_hash = sha256_file(path)
    if after_hash != before_hash:
        raise Phase0Error("read-only assembly verification changed the file hash")
    return {
        "open": open_record,
        "component_count": len(components),
        "references": references,
        "all_references_inside_run_root": True,
        "asset_role": role,
        "hash_unchanged": True,
    }


def _verify_drawing(
    session: SolidWorksSession,
    run_root: Path,
    path: Path,
    expected_assembly: Path,
) -> dict[str, Any]:
    before_hash = sha256_file(path)
    model, open_record = session.open_document(path, "drawing")
    drawing = session.cast(model, "IDrawingDoc")
    sheet = session.cast(drawing.GetCurrentSheet(), "ISheet")
    views = list(sheet.GetViews() or [])
    role = session.read_text_property(model, "ASSET_ROLE")
    if not views:
        raise Phase0Error("cold-reopened drawing contains no views")
    if role != "SOLIDWORKS_AUTOMATION_SMOKE_TEST_ONLY":
        raise Phase0Error(f"drawing role property mismatch: {role!r}")
    view_records: list[dict[str, Any]] = []
    model_references: list[str] = []
    for raw_view in views:
        view = session.cast(raw_view, "IView")
        referenced = str(get_com_member(view, "GetReferencedModelName") or "")
        if referenced:
            referenced_path = Path(referenced).resolve()
            if referenced_path != expected_assembly.resolve():
                raise Phase0Error(
                    f"drawing references unexpected model: {referenced_path}"
                )
            if not is_within(referenced_path, run_root):
                raise Phase0Error(
                    f"drawing model reference escapes run root: {referenced_path}"
                )
            model_references.append(
                referenced_path.relative_to(run_root).as_posix()
            )
        view_records.append(
            {
                "name": str(get_com_member(view, "GetName2")),
                "type": int(view.Type),
                "referenced_model": (
                    Path(referenced).resolve().relative_to(run_root).as_posix()
                    if referenced
                    else None
                ),
            }
        )
    if not model_references:
        raise Phase0Error("drawing has no model-backed view")
    session.close_document(model)
    after_hash = sha256_file(path)
    if after_hash != before_hash:
        raise Phase0Error("read-only drawing verification changed the file hash")
    return {
        "open": open_record,
        "view_count": len(view_records),
        "views": view_records,
        "model_references": sorted(set(model_references)),
        "asset_role": role,
        "hash_unchanged": True,
    }


def _verify_step(path: Path, run_root: Path) -> dict[str, Any]:
    try:
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.STEPControl import STEPControl_Reader
    except Exception as exc:
        raise Phase0Error(f"OCP STEP reader is unavailable: {exc!r}") from exc
    reader = STEPControl_Reader()
    status = reader.ReadFile(str(path))
    if status != IFSelect_RetDone:
        raise Phase0Error(f"OCP STEP ReadFile failed with status {status!r}")
    transferred = int(reader.TransferRoots())
    shape = reader.OneShape()
    if transferred <= 0 or shape.IsNull():
        raise Phase0Error(
            f"OCP STEP transfer produced no valid shape: roots={transferred}"
        )
    return {
        **artifact_record(path, run_root),
        "ocp_read": "PASS",
        "transferred_roots": transferred,
        "shape_is_null": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cold-reopen and verify an immutable Phase0 smoke run."
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--attempt-id",
        help=(
            "Optional additive verification-attempt suffix. This never "
            "overwrites an earlier report."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report: dict[str, Any] = {
        "schema": "SER_B50_PHASE0_VERIFY_V1",
        "generated_utc": utc_now(),
        "run_id": args.run_id,
        "attempt_id": args.attempt_id or "initial",
        "candidate_root": str(CANDIDATE_ROOT),
        "status": "PHASE0_TOOL_GATE_HOLD",
        "checks": {},
    }
    run_root: Path | None = None
    report_path: Path | None = None
    session: SolidWorksSession | None = None
    initial_hashes: dict[str, str] = {}
    try:
        validate_run_id(args.run_id)
        run_root = phase0_run_root(args.run_id)
        if not run_root.is_dir():
            raise Phase0Error(f"run_root does not exist: {run_root}")
        if args.attempt_id:
            validate_run_id(args.attempt_id)
            report_path = (
                run_root
                / "evidence"
                / f"phase0_verify_report_{args.attempt_id}.json"
            )
        else:
            report_path = run_root / "evidence" / "phase0_verify_report.json"
        if report_path.exists():
            raise Phase0Error(
                f"verification evidence exists; rerun overwrite forbidden: {report_path}"
            )
        paths = _required_paths(run_root)
        for name, path in paths.items():
            if not path.is_file():
                raise Phase0Error(f"required Phase0 file is missing: {name}={path}")
        build_report = _load_and_check_build_report(run_root, paths)
        report["checks"]["build_report"] = {
            "status": build_report["status"],
            "hash_reconciliation": "PASS",
        }
        initial_hashes = {
            name: sha256_file(paths[name])
            for name in ("part", "assembly", "drawing", "step")
        }

        with SolidWorksSession(run_root, visible=False) as session:
            report["session_start"] = session.info()
            report["checks"]["part"] = _verify_part(
                session, run_root, paths["part"]
            )
            report["checks"]["assembly"] = _verify_assembly(
                session, run_root, paths["assembly"], paths["part"]
            )
            report["checks"]["drawing"] = _verify_drawing(
                session,
                run_root,
                paths["drawing"],
                paths["assembly"],
            )
        report["session_end"] = session.info()
        report["checks"]["step"] = _verify_step(paths["step"], run_root)

        final_hashes = {
            name: sha256_file(paths[name])
            for name in ("part", "assembly", "drawing", "step")
        }
        if final_hashes != initial_hashes:
            raise Phase0Error("verification changed one or more CAD/export hashes")
        report["checks"]["all_artifact_hashes_unchanged"] = True
        report["status"] = "PHASE0_TOOL_GATE_PASS"
    except Exception as exc:
        report["status"] = "PHASE0_TOOL_GATE_HOLD"
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
                report["status"] = "PHASE0_TOOL_GATE_HOLD"
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PHASE0_TOOL_GATE_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
