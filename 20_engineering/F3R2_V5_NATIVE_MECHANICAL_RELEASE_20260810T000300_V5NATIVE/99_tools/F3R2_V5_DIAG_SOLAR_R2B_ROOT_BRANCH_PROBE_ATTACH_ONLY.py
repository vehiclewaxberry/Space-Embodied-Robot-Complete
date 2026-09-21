#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Write-once R2B-A ROOT/M1 advanced-angle branch matrix.

``audit`` is filesystem-only. ``run`` attaches to one explicitly named,
document-empty SOLIDWORKS 2024 process and creates a new scratch attempt below
``99_tools/probe_logs``.  It recreates the G6 root equivalent and exact rigid
M1 nested module; it never reads, copies, saves-as, or mutates an earlier
attempt.  The 24 independent assemblies cover beta={1,89,90} degrees crossed
with AddMate3 Alignment={ALIGNED,ANTI}, Flip={false,true}, and Top-plane
selection order={root-first,M1-first}.  Each case records the signed Rx and
translation before and after driving, before restore on the authored negative
branch, and after restoring the native advanced 0..90 degree angle mate.

This is diagnostic evidence only.  It cannot authorize production CAD.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple


sys.dont_write_bytecode = True

ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
RUN_ROOT = ROOT / "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
TOOLS = RUN_ROOT / "99_tools"
PROBE_ROOT = TOOLS / "probe_logs"
R2B_PATH = TOOLS / "F3R2_V5_DIAG_SOLAR_R2B_MODULE_CHAIN_ATTACH_ONLY.py"
L1B_PATH = TOOLS / "F3R2_V5_NATIVE_LOOP1B_WING_ROOTS_ATTACH_ONLY.py"
EXPECTED = {
    R2B_PATH: "AE6265E7029E4F188ACF38AEA46FAAEBF978BC19AA64B64B8D982170392C8465",
    L1B_PATH: "32BC06FC6A1EFCD6426FE4608D03EABCBD2902CBA228E95B2AD7A91B4E0F283F",
}
RUN_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
ANGLES_DEG = (1.0, 89.0, 90.0)
ALIGNMENTS = (0, 1)
FLIPS = (False, True)
SWAPS = (False, True)
SW_MATE_ANGLE = 6
SW_SET_VALUE_IN_SPECIFIC_CONFIGS = 3
ANGLE_TOL_DEG = 1.0e-3
TRANSFORM_TOL = 2.0e-7

sys.path.insert(0, str(TOOLS))
import F3R2_V5_DIAG_SOLAR_R2B_MODULE_CHAIN_ATTACH_ONLY as R2B  # noqa: E402

L1B = R2B.L1B


class ProbeError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Optional[Mapping[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.detail = dict(detail or {})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def norm(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def file_fact(path: Path) -> Dict[str, Any]:
    return {"path": norm(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def validate_run_id(run_id: str) -> str:
    if not RUN_ID_RE.fullmatch(run_id):
        raise ProbeError("RUN_ID_INVALID", "run id is not a safe leaf name", {"run_id": run_id})
    return run_id


def attempt_root(run_id: str) -> Path:
    return PROBE_ROOT / f"V5_SOLAR_R2B_ROOT_BRANCH_{validate_run_id(run_id)}"


def write_json_once(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def static_audit(run_id: Optional[str]) -> Dict[str, Any]:
    dependency_rows = []
    for path, expected in EXPECTED.items():
        actual = sha256(path) if path.is_file() else None
        dependency_rows.append({"path": norm(path), "expected_sha256": expected, "actual_sha256": actual, "pass": actual == expected})
    source = Path(__file__).read_text(encoding="utf-8")
    attach_tokens = (
        "win32com.client." + "Dispatch(",
        "win32com.client." + "DispatchEx(",
        "GetActive" + "Object(",
    )
    forbidden = [token for token in attach_tokens if token in source]
    target = attempt_root(run_id) if run_id else None
    passed = all(row["pass"] for row in dependency_rows) and not forbidden and (target is None or not target.exists())
    return {
        "schema": "F3R2_V5_SOLAR_R2B_ROOT_BRANCH_STATIC_AUDIT_V1",
        "timestamp_utc": utc_now(),
        "run_id": run_id,
        "attempt_root": norm(target) if target else None,
        "attempt_absent": target is None or not target.exists(),
        "dependency_hashes": dependency_rows,
        "forbidden_session_attach_tokens": forbidden,
        "case_count": len(ANGLES_DEG) * len(ALIGNMENTS) * len(FLIPS) * len(SWAPS),
        "angles_deg": list(ANGLES_DEG),
        "alignments": list(ALIGNMENTS),
        "flips": list(FLIPS),
        "selection_orders": ["ROOT_FIRST", "M1_FIRST"],
        "write_scope": "NEW_WRITE_ONCE_PROBE_LOGS_ATTEMPT_ONLY",
        "solidworks_touched": False,
        "verdict": "V5_SOLAR_R2B_ROOT_BRANCH_STATIC_PASS" if passed else "V5_SOLAR_R2B_ROOT_BRANCH_STATIC_HOLD",
    }


def transform_fact(component: Any) -> Dict[str, Any]:
    values = R2B.L1B.transform_array(component)
    if len(values) != 16:
        raise ProbeError("TRANSFORM_SHAPE_FAIL", "component transform is not 16 values", {"count": len(values)})
    return {
        "transform16": values,
        "signed_rx_deg": math.degrees(math.atan2(float(values[5]), float(values[4]))),
        "translation_mm": [float(values[index]) * 1000.0 for index in (9, 10, 11)],
    }


def angle_mate_fact(feature: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    raw_mate = L1B.value(feature, "GetSpecificFeature2")
    raw_definition = L1B.value(feature, "GetDefinition")
    if raw_mate is None or raw_definition is None:
        raise ProbeError("ANGLE_OBJECT_NULL", "angle feature lacks IMate2/IAngleMateFeatureData")
    mate = L1B.wrap(raw_mate, "IMate2", types, pythoncom)
    definition = L1B.wrap(raw_definition, "IAngleMateFeatureData", types, pythoncom)
    dimension = R2B.angle_dimension(feature, types, pythoncom)
    return {
        "feature_name": str(L1B.value(feature, "Name")),
        "mate_type": int(L1B.value(mate, "Type")),
        "alignment": int(L1B.value(mate, "Alignment")),
        "flipped": bool(L1B.value(mate, "Flipped")),
        "advanced": bool(L1B.value(definition, "IsAdvancedMate")),
        "angle_rad": float(L1B.value(definition, "Angle")),
        "minimum_angle_rad": float(L1B.value(definition, "MinimumAngle")),
        "maximum_angle_rad": float(L1B.value(definition, "MaximumAngle")),
        "dimension_full_name": str(L1B.value(dimension, "FullName")),
        "feature_health": L1B.feature_error_state(feature),
    }


def add_probe_angle(model: Any, assembly: Any, root_component: Any, m1_component: Any, align: int, flip: bool, swap: bool, name: str, types: Any, pythoncom: Any) -> Tuple[Any, Any, Dict[str, Any]]:
    before = set(R2B.mate_feature_map(model, types, pythoncom))
    root_plane, root_fact = R2B.component_top_plane(root_component, types, pythoncom)
    m1_plane, m1_fact = R2B.component_top_plane(m1_component, types, pythoncom)
    first, second = (m1_plane, root_plane) if swap else (root_plane, m1_plane)
    model.ClearSelection2(True)
    if not bool(first.Select2(False, 1)) or not bool(second.Select2(True, 1)):
        raise ProbeError("ANGLE_SELECTION_FAIL", "cannot select exact ROOT/M1 Top planes", {"swap": swap})
    selected = int(L1B.selection_manager(model, types, pythoncom).GetSelectedObjectCount2(1))
    returned = assembly.AddMate3(SW_MATE_ANGLE, align, flip, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, math.pi / 2.0, 0.0, False, 0)
    model.ClearSelection2(True)
    raw_mate, outs = L1B.unpack(returned)
    error = int(outs[0]) if len(outs) == 1 else -1
    after = R2B.mate_feature_map(model, types, pythoncom)
    additions = [feature for feature_name, feature in after.items() if feature_name not in before]
    if raw_mate is None or error != 1 or selected != 2 or len(additions) != 1:
        raise ProbeError("ANGLE_ADD_FAIL", "AddMate3 did not create one angle mate", {"align": align, "flip": flip, "swap": swap, "error": error, "selected": selected, "additions": len(additions)})
    feature = additions[0]
    feature.Name = name
    feature = R2B.mate_feature_map(model, types, pythoncom)[name]
    dimension = R2B.angle_dimension(feature, types, pythoncom)
    return feature, dimension, {
        "requested_alignment": align,
        "requested_flip": flip,
        "selection_order": "M1_FIRST" if swap else "ROOT_FIRST",
        "root_plane": root_fact,
        "m1_plane": m1_fact,
        "selected_count": selected,
        "error_status": error,
        "readback_at_creation": angle_mate_fact(feature, types, pythoncom),
    }


def add_exact_root_joint(model: Any, assembly: Any, root_component: Any, m1_component: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    root_cylinder = L1B.cylinder_entity(root_component, R2B.PIN_RADIUS_MM, R2B.ROOT_Y_MM, 1, types, pythoncom)[0]
    m1_cylinder, _m1_face, nested, collar = R2B.nested_geometry(m1_component, "M1_ROOT_BORE", R2B.ROOT_Y_MM, R2B.BORE_RADIUS_MM, R2B.X_START_MM, types, pythoncom)
    concentric = R2B.add_named_entity_mate(model, assembly, root_cylinder, m1_cylinder, R2B.SW_MATE_CONCENTRIC, (root_component, collar), "BP_ROOT_CONCENTRIC", types, pythoncom)
    root_face = L1B.plane_entity_x(root_component, R2B.X_START_MM, types, pythoncom)[0]
    m1_face = R2B.nested_geometry(m1_component, "M1_ROOT_BORE", R2B.ROOT_Y_MM, R2B.BORE_RADIUS_MM, R2B.X_START_MM, types, pythoncom)[1]
    coincident = R2B.add_named_entity_mate(model, assembly, root_face, m1_face, R2B.SW_MATE_COINCIDENT, (root_component, collar), "BP_ROOT_COINCIDENT", types, pythoncom)
    return {"nested_m1_bore": nested, "concentric": concentric, "coincident": coincident}


def run_case(sw: Any, root_path: Path, m1_path: Path, case_dir: Path, angle_deg: float, align: int, flip: bool, swap: bool, types: Any, pythoncom: Any) -> Dict[str, Any]:
    from win32com.client import VARIANT

    label = f"B{int(angle_deg):03d}_A{align}_F{int(flip)}_S{int(swap)}"
    target = case_dir / f"{label}.SLDASM"
    model = None
    try:
        model, assembly = R2B.new_assembly(sw, types, pythoncom)
        root_component = R2B.insert_component_typed(sw, model, assembly, root_path, True, types, pythoncom)
        m1_component = R2B.insert_component_typed(sw, model, assembly, m1_path, False, types, pythoncom)
        structural = add_exact_root_joint(model, assembly, root_component, m1_component, types, pythoncom)
        feature, dimension, creation = add_probe_angle(model, assembly, root_component, m1_component, align, flip, swap, f"BP_{label}_LIMIT_ANGLE", types, pythoncom)
        pose_at_creation = transform_fact(m1_component)

        configuration = L1B.wrap(L1B.value(L1B.value(model, "ConfigurationManager"), "ActiveConfiguration"), "IConfiguration", types, pythoncom)
        config_name = str(L1B.value(configuration, "Name"))
        config_array = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, [config_name])
        requested_rad = math.radians(angle_deg)
        drive_status = int(dimension.SetSystemValue3(requested_rad, SW_SET_VALUE_IN_SPECIFIC_CONFIGS, config_array))
        if drive_status != 0 or not bool(model.ForceRebuild3(True)):
            raise ProbeError("ANGLE_DRIVE_FAIL", "typed angle drive or rebuild failed", {"label": label, "status": drive_status})
        feature = R2B.mate_feature_map(model, types, pythoncom)[f"BP_{label}_LIMIT_ANGLE"]
        driven_readback = float(R2B.angle_dimension(feature, types, pythoncom).GetSystemValue2(config_name))
        pose_after_drive = transform_fact(R2B.component_by_path(model, m1_path, types, pythoncom))

        R2B.feature_suppression(feature, True)
        if not bool(model.EditRebuild3()):
            raise ProbeError("SUPPRESS_REBUILD_FAIL", "rebuild failed after angle suppression", {"label": label})
        expected = R2B.state_transforms((90.0 - angle_deg, 90.0, 90.0))["M1"]
        m1_component = R2B.component_by_path(model, m1_path, types, pythoncom)
        if not bool(m1_component.SetTransformAndSolve3(L1B.make_transform(sw, expected, types, pythoncom), False)):
            raise ProbeError("NEGATIVE_BRANCH_PREPOSITION_FAIL", "cannot author negative ROOT branch while angle is suppressed", {"label": label})
        pose_before_restore = transform_fact(R2B.component_by_path(model, m1_path, types, pythoncom))
        preposition_error = R2B.transform_error(pose_before_restore["transform16"], expected)

        feature = R2B.mate_feature_map(model, types, pythoncom)[f"BP_{label}_LIMIT_ANGLE"]
        R2B.feature_suppression(feature, False)
        if not bool(model.ForceRebuild3(True)):
            raise ProbeError("RESTORE_REBUILD_FAIL", "rebuild failed after angle restore", {"label": label})
        m1_component = R2B.component_by_path(model, m1_path, types, pythoncom)
        pose_after_restore = transform_fact(m1_component)
        restore_error = R2B.transform_error(pose_after_restore["transform16"], expected)
        rx = float(pose_after_restore["signed_rx_deg"])
        if abs(rx + angle_deg) <= ANGLE_TOL_DEG and restore_error <= TRANSFORM_TOL:
            branch = "NEGATIVE_EXPECTED"
        elif abs(rx - angle_deg) <= ANGLE_TOL_DEG:
            branch = "POSITIVE_MIRROR"
        else:
            branch = "OTHER"
        feature = R2B.mate_feature_map(model, types, pythoncom)[f"BP_{label}_LIMIT_ANGLE"]
        final_mate = angle_mate_fact(feature, types, pythoncom)
        L1B.set_properties(model, {"ARTIFACT_CLASS": "DIAGNOSTIC_BRANCH_PROBE_NON_RELEASE", "PRODUCTION_USE": "PROHIBITED", "CASE": label})
        saved = L1B.save_as(model, target)
        return {
            "label": label,
            "angle_deg": angle_deg,
            "requested_alignment": align,
            "requested_flip": flip,
            "swap_selection_order": swap,
            "creation": creation,
            "structural_mates": structural,
            "configuration": config_name,
            "typed_drive_status": drive_status,
            "requested_driver_rad": requested_rad,
            "driven_readback_rad": driven_readback,
            "pose_at_angle_creation_zero": pose_at_creation,
            "pose_after_typed_drive": pose_after_drive,
            "pose_before_restore_negative_branch": pose_before_restore,
            "negative_preposition_transform_error": preposition_error,
            "pose_after_restore": pose_after_restore,
            "expected_negative_transform16": expected,
            "restore_transform_error": restore_error,
            "restored_branch": branch,
            "final_mate_readback": final_mate,
            "assembly": saved,
            "case_complete": True,
        }
    finally:
        L1B.close_doc(sw, model)


def execute(run_id: str, expected_pid: int) -> Dict[str, Any]:
    audit = static_audit(run_id)
    if audit["verdict"] != "V5_SOLAR_R2B_ROOT_BRANCH_STATIC_PASS":
        raise ProbeError("STATIC_AUDIT_HOLD", "branch probe static audit is not PASS", audit)
    root = attempt_root(run_id)
    mutex = R2B.acquire_process_mutex()
    sw = pythoncom = None
    root_created = False
    try:
        root.mkdir(parents=False, exist_ok=False)
        root_created = True
        sw, types, pythoncom, session = L1B.attach_empty_session(expected_pid)
        part_dir = root / "cad/parts"
        module_dir = root / "cad/modules"
        case_dir = root / "cad/cases"
        root_path = part_dir / "BP_R2B_ROOT_EQUIVALENT.SLDPRT"
        body_path = part_dir / "BP_R2B_M1_BODY.SLDPRT"
        collar_path = part_dir / "BP_R2B_M1_INBOARD_COLLAR.SLDPRT"
        pin_path = part_dir / "BP_R2B_M1_OUTBOARD_PIN.SLDPRT"
        m1_path = module_dir / "BP_R2B_MODULE_M1.SLDASM"
        artifacts = [
            R2B.create_ring_part(sw, types, pythoncom, root_path, "BRANCH_ROOT_EQUIVALENT", R2B.ROOT_Y_MM, R2B.PIN_RADIUS_MM, 0.0, run_id),
            R2B.create_module_body(sw, types, pythoncom, body_path, "M1", R2B.ROOT_Y_MM + R2B.PITCH_MM / 2.0, run_id),
            R2B.create_ring_part(sw, types, pythoncom, collar_path, "BRANCH_M1_INBOARD_COLLAR", R2B.ROOT_Y_MM, 2.75, R2B.BORE_RADIUS_MM, run_id),
            R2B.create_ring_part(sw, types, pythoncom, pin_path, "BRANCH_M1_OUTBOARD_PIN", R2B.ROOT_Y_MM + R2B.PITCH_MM, R2B.PIN_RADIUS_MM, 0.0, run_id),
        ]
        module = R2B.create_rigid_module(sw, types, pythoncom, m1_path, (body_path, collar_path, pin_path), "M1", run_id)
        rows = []
        for angle_deg in ANGLES_DEG:
            for align in ALIGNMENTS:
                for flip in FLIPS:
                    for swap in SWAPS:
                        try:
                            rows.append(run_case(sw, root_path, m1_path, case_dir, angle_deg, align, flip, swap, types, pythoncom))
                        except Exception as exc:
                            rows.append({
                                "angle_deg": angle_deg,
                                "requested_alignment": align,
                                "requested_flip": flip,
                                "swap_selection_order": swap,
                                "case_complete": False,
                                "error_code": getattr(exc, "code", "UNHANDLED_CASE_EXCEPTION"),
                                "error": str(exc),
                                "detail": getattr(exc, "detail", {}),
                                "traceback": traceback.format_exc(),
                            })
        L1B.close_owned_documents(sw)
        if int(L1B.value(sw, "GetDocumentCount")) != 0 or L1B.value(sw, "ActiveDoc") is not None:
            raise ProbeError("SESSION_NOT_EMPTY", "probe-owned documents remain open")
        completed = [row for row in rows if row.get("case_complete")]
        winners = [row["label"] for row in completed if row.get("restored_branch") == "NEGATIVE_EXPECTED"]
        result = {
            "schema": "F3R2_V5_SOLAR_R2B_ROOT_BRANCH_MATRIX_V1",
            "timestamp_utc": utc_now(),
            "run_id": run_id,
            "attempt_root": norm(root),
            "classification": "DIAGNOSTIC_BRANCH_PROBE_NON_RELEASE",
            "production_use": "PROHIBITED",
            "session": session,
            "dependency_hashes": [file_fact(path) for path in EXPECTED],
            "geometry_contract": "G6_ROOT_EQUIVALENT_PLUS_EXACT_RIGID_M1_NESTED_MODULE; TOP_PLANE_X_ROOT_AXIS",
            "artifacts": artifacts,
            "module": module,
            "case_count_planned": 24,
            "case_count_complete": len(completed),
            "negative_branch_winners": winners,
            "cases": rows,
            "verdict": "V5_SOLAR_R2B_ROOT_BRANCH_MATRIX_COMPLETE" if len(rows) == 24 else "V5_SOLAR_R2B_ROOT_BRANCH_MATRIX_INCOMPLETE",
        }
        write_json_once(root / "RESULT.json", result)
        return result
    except Exception as exc:
        if sw is not None:
            try:
                L1B.close_owned_documents(sw)
            except Exception:
                pass
        if root_created:
            write_json_once(root / f"FAIL_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')}.json", {
                "schema": "F3R2_V5_SOLAR_R2B_ROOT_BRANCH_FAILURE_V1",
                "timestamp_utc": utc_now(),
                "run_id": run_id,
                "error_code": getattr(exc, "code", "UNHANDLED_EXCEPTION"),
                "error": str(exc),
                "detail": getattr(exc, "detail", {}),
                "traceback": traceback.format_exc(),
                "verdict": "V5_SOLAR_R2B_ROOT_BRANCH_FAIL",
            })
        raise
    finally:
        if pythoncom is not None:
            pythoncom.CoUninitialize()
        R2B.release_process_mutex(mutex)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit", help="filesystem-only audit; never touches SOLIDWORKS")
    audit.add_argument("--run-id")
    run = commands.add_parser("run", help="attach to one explicit empty PID and write one new scratch attempt")
    run.add_argument("--run-id", required=True)
    run.add_argument("--expected-pid", required=True, type=int)
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parser().parse_args(argv)
    try:
        payload = static_audit(args.run_id) if args.command == "audit" else execute(args.run_id, args.expected_pid)
        print(json.dumps({"verdict": payload["verdict"], "run_id": payload.get("run_id"), "attempt_root": payload.get("attempt_root")}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if payload["verdict"].endswith(("PASS", "COMPLETE")) else 2
    except Exception as exc:
        print(json.dumps({"error_code": getattr(exc, "code", "UNHANDLED_EXCEPTION"), "error": str(exc), "detail": getattr(exc, "detail", {}), "verdict": "V5_SOLAR_R2B_ROOT_BRANCH_HOLD"}, ensure_ascii=False, indent=2, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
