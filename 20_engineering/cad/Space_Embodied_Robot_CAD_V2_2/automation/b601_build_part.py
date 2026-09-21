"""Build the B601 high-fidelity static multibody part by the approved P-C route.

The canonical V2.2 top assembly is not touched here.  The exact registered STEP
is loaded in memory because the preserved ASSET-00 SLDASM references vanished
spiop temporaries.  The original STEP and scratch SLDASM remain read-only.
"""
from __future__ import annotations

import json
import math
import os
import sys
import shutil
from pathlib import Path
import traceback

sys.path.insert(0, str(Path(__file__).parent))

import b601_reimport_probe as recovery
import b601_swap_01 as base
from b3_lib import sw_core as core
from b3_lib.sw_core import B3FailClosed, BuildLog, cast, connect, get_com_member

HIFI_DIR = base.V22 / "35_B601_HiFi_Visual"
RAW_PART = HIFI_DIR / "recovery_scratch" / "B601_VENDOR_STOWED_RAW.SLDPRT"
WORK_PART = HIFI_DIR / "B601_STOWED_HIFI_WORK.SLDPRT"
FINAL_PART = HIFI_DIR / "B601_STOWED_HIFI.SLDPRT"
RESULT = base.EVIDENCE / "part_build_result.json"
BODY_MAPPING = base.EVIDENCE / "body_mapping.yaml"

PREF_INTEGER = {201: 1}
PREF_TOGGLES = {615: True, 710: False, 712: False, 713: False, 716: False}

SOURCE_GROUP_ROLES = {
    "01-BASE-1_ASM-1": {
        "semantic_role": "base_and_joint1_stator",
        "urdf_correspondence": ["base_link"],
        "confidence": "HIGH_BY_VENDOR_NAME",
    },
    "2026-04-01-16-48-42-413-1": {
        "semantic_role": "joint1_rotor_interface",
        "urdf_correspondence": ["base_link", "link1"],
        "confidence": "MEDIUM_BY_CONTENT_M1_ROTOR",
    },
    "02-LINK-1_ASM-1": {
        "semantic_role": "vendor_link1_group",
        "urdf_correspondence": ["link1"],
        "confidence": "HIGH_BY_VENDOR_NAME",
    },
    "03-LINK-2_ASM-1": {
        "semantic_role": "vendor_link2_group",
        "urdf_correspondence": ["link2"],
        "confidence": "HIGH_BY_VENDOR_NAME",
    },
    "04-LINK-3_ASM-1": {
        "semantic_role": "vendor_link3_and_wrist_base_group",
        "urdf_correspondence": ["link3", "link4"],
        "confidence": "MEDIUM_BY_NAME_AND_CONTENT_M5_BASE",
    },
    "2026-04-01-17-02-36-958-1": {
        "semantic_role": "wrist_rotor_group",
        "urdf_correspondence": ["link4", "link5"],
        "confidence": "MEDIUM_BY_CONTENT_M5_ROTOR",
    },
    "05-GRIPPER_ASM-1": {
        "semantic_role": "wrist_and_gripper_drive_group",
        "urdf_correspondence": ["link5", "link6", "gripper_link"],
        "confidence": "MEDIUM_BY_VENDOR_NAME_AND_CONTENT_M6_M7",
    },
    "2026-04-01-17-05-40-350-1": {
        "semantic_role": "gripper_rail_and_fingers_group",
        "urdf_correspondence": ["gripper_link", "gripper_left", "gripper_right"],
        "confidence": "HIGH_BY_CONTENT_RAIL_RACK_SLIDER",
    },
}


def body_records(model):
    part = cast(model, "IPartDoc")
    bodies = base.as_list(part.GetBodies2(0, False))
    records = []
    for index, body in enumerate(bodies):
        b = cast(body, "IBody2")
        try:
            box = [round(float(v) * 1000.0, 6) for v in base.as_list(b.GetBodyBox())]
        except Exception:
            box = None
        records.append({
            "index": index,
            "name": str(base.call_or_value(b, "Name", f"BODY_{index:04d}")),
            "bbox_mm": box,
        })
    return bodies, records


def union_bbox(records):
    boxes = [r["bbox_mm"] for r in records if r.get("bbox_mm") and len(r["bbox_mm"]) == 6]
    if not boxes:
        return None
    return [
        min(b[0] for b in boxes), min(b[1] for b in boxes), min(b[2] for b in boxes),
        max(b[3] for b in boxes), max(b[4] for b in boxes), max(b[5] for b in boxes),
    ]


def snapshot_save_preferences(sw):
    return {
        "integer": {str(k): int(sw.GetUserPreferenceIntegerValue(k)) for k in PREF_INTEGER},
        "toggle": {str(k): bool(sw.GetUserPreferenceToggle(k)) for k in PREF_TOGGLES},
    }


def target_save_preferences():
    return {
        "integer": {str(k): int(v) for k, v in PREF_INTEGER.items()},
        "toggle": {str(k): bool(v) for k, v in PREF_TOGGLES.items()},
    }


def apply_save_preferences(sw, before, log):
    setter_returns = {"integer": {}, "toggle": {}}
    try:
        for key, value in PREF_INTEGER.items():
            setter_returns["integer"][str(key)] = sw.SetUserPreferenceIntegerValue(key, value)
        for key, value in PREF_TOGGLES.items():
            setter_returns["toggle"][str(key)] = sw.SetUserPreferenceToggle(key, value)
    except Exception as exc:
        log.fail(
            "SolidWorks save preference setter raised",
            error=repr(exc),
            before=before,
            setter_returns=setter_returns,
        )
    after = snapshot_save_preferences(sw)
    target = target_save_preferences()
    if after != target:
        log.fail(
            "SolidWorks save preference readback mismatch",
            before=before,
            target=target,
            after=after,
            setter_returns=setter_returns,
        )
    log.event(
        "SAVE_PREFERENCES_APPLIED",
        before=before,
        target=target,
        after=after,
        setter_returns=setter_returns,
    )
    return after


def restore_save_preferences(sw, before):
    for key, value in before["integer"].items():
        sw.SetUserPreferenceIntegerValue(int(key), int(value))
    for key, value in before["toggle"].items():
        sw.SetUserPreferenceToggle(int(key), bool(value))
    return snapshot_save_preferences(sw)


def save_assembly_as_part(model, path, log):
    path.parent.mkdir(parents=True, exist_ok=True)
    ext = cast(get_com_member(model, "Extension"), "IModelDocExtension")
    errors_value = 0
    warnings_value = 0
    try:
        result = ext.SaveAs3(str(path), 0, 1, None, None, 0, 0)
        if isinstance(result, tuple):
            ok = bool(result[0])
            if len(result) > 1:
                errors_value = int(result[1])
            if len(result) > 2:
                warnings_value = int(result[2])
        else:
            ok = bool(result)
    except TypeError:
        errors = core.byref_i4()
        warnings = core.byref_i4()
        ok = bool(ext.SaveAs3(
            str(path), 0, 1, core.empty_dispatch(), core.empty_dispatch(),
            errors, warnings,
        ))
        errors_value = int(errors.value)
        warnings_value = int(warnings.value)
    if not ok or errors_value != 0 or not path.exists():
        log.fail(
            "assembly SaveAs3 multibody part failed",
            ok=ok, errors=errors_value, warnings=warnings_value, path=str(path),
        )
    log.event("ASSEMBLY_SAVED_AS_PART", path=str(path), errors=errors_value, warnings=warnings_value, bytes=path.stat().st_size)


def expected_bbox_after_pc(raw_bbox):
    xmin, ymin, zmin, xmax, ymax, zmax = raw_bbox
    return [
        round(198.0 + zmin, 6), ymin, round(-xmax, 6),
        round(198.0 + zmax, 6), ymax, round(-xmin, 6),
    ]


def bbox_close(actual, expected, tol_mm=0.1):
    return actual is not None and len(actual) == 6 and all(abs(a - e) <= tol_mm for a, e in zip(actual, expected))


def custom_properties():
    return {
        "OBJECT_ID": "B601_STOWED_HIFI",
        "SYSTEM_OWNER": "b601_visual_geometry",
        "PARENT_ID": "Spacecraft_Service_Vehicle_V2_2_STAGING",
        "REPRESENTATION_LAYER": "L2_HIFI_STATIC_GEOMETRY",
        "GEOMETRY_AUTHORITY": "reBot_B601_DM_v1.1_20260425.step",
        "SOURCE_STEP_SHA256": base.EXPECTED_STEP_SHA256,
        "SOURCE_SCRATCH_SHA256": base.sha256(base.SOURCE_ASM),
        "RECOVERY_PATH": "registered_STEP_same_hash_after_scratch_spiop_dependencies_missing",
        "FRAME_ID": "CS_S_V22",
        "INTERFACE_IDS": "IF-RM-002;M_PLANE_X_V22=198.0mm",
        "P_C_BAKED_TRANSFORM": "R_Y(+90deg)_about_origin_then_T_X(+198mm)",
        "MASS_AUTHORITY": "EXCLUDED",
        "MASS_OWNER": "accepted_URDF_only",
        "URDF_SHA256": "1bc2b7483cd8025d08ba6eadfd9e1f3b0477121714e7cf4ddc1794d9e471c164",
        "GEOMETRY_LICENSE": "CERN-OHL-W-2.0",
        "LICENSE_CLASS": "E3_INTERNAL_RESEARCH_ONLY",
        "DO_NOT_REDISTRIBUTE": "TRUE_UNTIL_URDF_LICENSE_CLARIFIED",
        "MANUFACTURING_AUTHORITY": "NONE",
        "EXECUTION_AUTHORITY": "DISPLAY_ONLY_STATIC_VENDOR_FOLDED_POSE",
        "CLAIM_LIMIT": "no_continuous_kinematics;no_collision_clearance;no_FEA;no_mass_inertia;no_manufacturing_release;CAPTURE_SAFE_UNKNOWN",
        "SOURCE_GROUP_MAPPING": ";".join(f"{k}={v['semantic_role']}" for k, v in SOURCE_GROUP_ROLES.items()),
    }


def main():
    log = BuildLog("b601_swap_01_build_part")
    base.EVIDENCE.mkdir(parents=True, exist_ok=True)
    HIFI_DIR.mkdir(parents=True, exist_ok=True)
    recovery_doc = json.loads((base.EVIDENCE / "registered_step_recovery_probe.json").read_text(encoding="utf-8"))
    if recovery_doc.get("recovery_gate") != "PASS":
        log.fail("registered STEP recovery gate is not PASS")
    for target in (RAW_PART, WORK_PART, FINAL_PART):
        if target.exists():
            log.fail("output already exists; refusing overwrite", path=str(target))
    scratch_hash_before = base.sha256(base.SOURCE_ASM)
    step_hash = base.sha256(base.SOURCE_STEP)
    if step_hash != base.EXPECTED_STEP_SHA256:
        log.fail("registered STEP hash mismatch", actual=step_hash)

    sw = connect(log, wait_seconds=45, visible=False)
    sw.CloseAllDocuments(True)
    try:
        model, load_errors, load_elapsed = recovery.load_step(sw, log)
    except Exception as exc:
        try:
            sw.CloseAllDocuments(True)
            sw.ExitApp()
        except Exception:
            pass
        log.fail("registered STEP LoadFile4 failed", error=repr(exc))
    asm = cast(model, "IAssemblyDoc")
    component_count = len(base.as_list(asm.GetComponents(False)))
    if component_count != 358:
        log.fail("loaded STEP component count changed", actual=component_count, expected=358)

    preferences_before = snapshot_save_preferences(sw)
    preferences_applied = None
    preferences_restored = None
    try:
        preferences_applied = apply_save_preferences(sw, preferences_before, log)
        save_assembly_as_part(model, RAW_PART, log)
    finally:
        preferences_restored = restore_save_preferences(sw, preferences_before)
        log.event(
            "SAVE_PREFERENCES_RESTORE_READBACK",
            before=preferences_before,
            after=preferences_restored,
        )
    if preferences_restored != preferences_before:
        log.fail("SolidWorks global save preferences were not restored", before=preferences_before, after=preferences_restored)
    sw.CloseAllDocuments(True)

    raw_model = core.open_document(sw, log, RAW_PART, read_only=True)
    raw_bodies, raw_records = body_records(raw_model)
    raw_bbox = union_bbox(raw_records)
    sw.CloseAllDocuments(True)
    if len(raw_bodies) < 100 or raw_bbox is None:
        log.fail("saved multibody part is incomplete", bodies=len(raw_bodies), bbox=raw_bbox)
    if not (2.5 <= raw_bbox[2] <= 4.1):
        log.fail("vendor mount-origin relationship is outside expected range", raw_zmin_mm=raw_bbox[2])

    shutil.copy2(RAW_PART, WORK_PART)
    work_model = core.open_document(sw, log, WORK_PART)
    work_bodies, _ = body_records(work_model)
    feat_mgr = cast(get_com_member(work_model, "FeatureManager"), "IFeatureManager")
    work_model.ClearSelection2(True)
    sel_mgr = cast(get_com_member(work_model, "SelectionManager"), "ISelectionMgr")
    sel_data = sel_mgr.CreateSelectData()
    sel_data.Mark = 1
    selected_rotation = sum(
        1 for body in work_bodies if cast(body, "IBody2").Select2(True, sel_data)
    )
    if selected_rotation != len(work_bodies):
        log.fail("not all bodies selected for P-C rotation", selected=selected_rotation, bodies=len(work_bodies))
    rotation_feature = feat_mgr.InsertMoveCopyBody2(
        0.0, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0,
        0.0, math.pi / 2.0, 0.0,
        False, 1,
    )
    if rotation_feature is None:
        log.fail("InsertMoveCopyBody2 rotation returned None")
    try:
        rotation_feature.Name = "B601_PC_BAKE_RY90"
    except Exception:
        pass
    work_model.ClearSelection2(True)
    core.rebuild_or_fail(work_model, log, "B601_P_C_ROTATION")
    rotated_bodies, rotated_records = body_records(work_model)
    rotated_bbox = union_bbox(rotated_records)
    expected_rotated_bbox = [
        raw_bbox[2], raw_bbox[1], -raw_bbox[3],
        raw_bbox[5], raw_bbox[4], -raw_bbox[0],
    ]
    if len(rotated_bodies) != len(work_bodies) or not bbox_close(rotated_bbox, expected_rotated_bbox):
        log.fail(
            "P-C rotation verification failed",
            bodies_before=len(work_bodies), bodies_after=len(rotated_bodies),
            actual_bbox=rotated_bbox, expected_bbox=expected_rotated_bbox,
        )
    sel_data_translation = sel_mgr.CreateSelectData()
    sel_data_translation.Mark = 1
    selected_translation = sum(
        1 for body in rotated_bodies if cast(body, "IBody2").Select2(True, sel_data_translation)
    )
    if selected_translation != len(rotated_bodies):
        log.fail("not all bodies selected for P-C translation", selected=selected_translation, bodies=len(rotated_bodies))
    translation_feature = feat_mgr.InsertMoveCopyBody2(
        0.198, 0.0, 0.0, 0.0,
        0.0, 0.0, 0.0,
        0.0, 0.0, 0.0,
        False, 1,
    )
    if translation_feature is None:
        log.fail("InsertMoveCopyBody2 translation returned None")
    try:
        translation_feature.Name = "B601_PC_BAKE_TX198"
    except Exception:
        pass
    work_model.ClearSelection2(True)
    core.set_custom_properties(work_model, log, custom_properties())
    core.rebuild_or_fail(work_model, log, "B601_P_C_TRANSLATION")
    core.save(work_model, log)
    _, final_records_in_session = body_records(work_model)
    final_bbox_in_session = union_bbox(final_records_in_session)
    expected_bbox = expected_bbox_after_pc(raw_bbox)
    if not bbox_close(final_bbox_in_session, expected_bbox):
        log.fail("P-C transformed bbox mismatch in session", actual=final_bbox_in_session, expected=expected_bbox)
    sw.CloseAllDocuments(True)

    os.replace(WORK_PART, FINAL_PART)
    final_model = core.open_document(sw, log, FINAL_PART, read_only=True)
    final_bodies, final_records = body_records(final_model)
    final_bbox_reopen = union_bbox(final_records)
    properties = core.read_custom_properties(final_model)
    sw.CloseAllDocuments(True)
    if len(final_bodies) != len(raw_bodies):
        log.fail("body count changed after close/reopen", before=len(raw_bodies), after=len(final_bodies))
    if not bbox_close(final_bbox_reopen, expected_bbox):
        log.fail("P-C transformed bbox did not persist after reopen", actual=final_bbox_reopen, expected=expected_bbox)
    required_props = {"MASS_AUTHORITY": "EXCLUDED", "FRAME_ID": "CS_S_V22", "LICENSE_CLASS": "E3_INTERNAL_RESEARCH_ONLY"}
    bad_props = {k: (properties.get(k), v) for k, v in required_props.items() if properties.get(k) != v}
    if bad_props:
        log.fail("governance properties failed reopen readback", bad=bad_props)

    dependencies = base.dependency_records(sw.GetDocumentDependencies2(str(FINAL_PART), True, True, True))
    missing_external = [d for d in dependencies if d["looks_like_path"] and not d["exists_if_path"]]
    if missing_external:
        log.fail("final multibody part has missing external dependencies", missing=missing_external)
    scratch_hash_after = base.sha256(base.SOURCE_ASM)
    if scratch_hash_after != scratch_hash_before:
        log.fail("ASSET-00 scratch assembly changed", before=scratch_hash_before, after=scratch_hash_after)

    mapping = {
        "mapping_id": "B601_SWAP01_BODY_MAPPING",
        "generated_utc": base.utc_now(),
        "status": "TRACEABLE_WITH_NON_1_TO_1_URDF_BOUNDARIES",
        "source_component_count": 358,
        "multibody_solid_count": len(final_bodies),
        "source_top_groups": SOURCE_GROUP_ROLES,
        "final_body_names": [r["name"] for r in final_records],
        "authority_note": "Vendor top groups are geometry groupings, not URDF link authority. Accepted URDF remains the sole kinematic and mass authority.",
    }
    BODY_MAPPING.write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = {
        "build_id": "B601_SWAP01_PART_BUILD",
        "generated_utc": base.utc_now(),
        "route": "P-C_RECOVERED_FROM_EXACT_REGISTERED_STEP",
        "load": {"errors": load_errors, "elapsed_sec": load_elapsed, "components": component_count},
        "preferences_before": preferences_before,
        "preferences_applied": preferences_applied,
        "preferences_restored": preferences_restored,
        "source": {"step_sha256": step_hash, "scratch_sha256_before": scratch_hash_before, "scratch_sha256_after": scratch_hash_after},
        "raw_part": {"path": str(RAW_PART), "sha256": base.sha256(RAW_PART), "bodies": len(raw_bodies), "bbox_mm": raw_bbox},
        "final_part": {"path": str(FINAL_PART), "sha256": base.sha256(FINAL_PART), "bodies": len(final_bodies), "bbox_in_session_mm": final_bbox_in_session, "bbox_reopen_mm": final_bbox_reopen, "expected_bbox_mm": expected_bbox, "dependencies": dependencies},
        "pc_transform": {"rotation_y_deg": 90.0, "translation_x_mm": 198.0, "features": ["B601_PC_BAKE_RY90", "B601_PC_BAKE_TX198"]},
        "verdict": "PART_BUILD_PASS",
    }
    RESULT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log.event("PART_BUILD_PASS", path=str(FINAL_PART), bodies=len(final_bodies), bbox_mm=final_bbox_reopen)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as exc:
        print(f"FAIL_CLOSED: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"UNEXPECTED_FAIL_CLOSED: {exc!r}")
        traceback.print_exc()
        sys.exit(2)
