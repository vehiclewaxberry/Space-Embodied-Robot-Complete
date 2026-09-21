"""B3-05 三舱构建：volume owner 零实体参考件 + 前/后任务面访问板。

治理：无来源尺寸的 volume 一律零实体（具名站位面+草图点+完整属性）；
VOL-FM-SENSOR / VOL-REAR-PROP 为 UNKNOWN_BLOCKED，零实体为硬要求（V2-CAD-14）。
"""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from b3_lib.sw_core import (B3FailClosed, BuildLog, V2_ROOT, cast, connect,
                            create_offset_plane, get_com_member,
                            insert_components_identity, new_document,
                            rebuild_or_fail, rename_last_feature, save_as,
                            set_custom_properties)
from b3_lib.sw_part_factory import RIGHT, build_x_extruded_part

SPEC = yaml.safe_load((V2_ROOT / "automation/b3_build_spec.yaml").read_text(encoding="utf-8"))
BVO = SPEC["bay_volume_owners"]

BAYS = {
    "front_mission_bay": ("02_Front_Mission_Module", "SV2_Front_Mission_Module"),
    "avionics_bay": ("03_Avionics_EPS_ADCS_Bay", "SV2_Avionics_EPS_ADCS_Bay"),
    "rear_service_bay": ("04_Rear_Service_Module", "SV2_Rear_Service_Module"),
}


def vol_props(vol_id, bay_asm, cfg):
    zero = cfg.get("zero_solid_required", False)
    return {
        "OBJECT_ID": vol_id, "SYSTEM_OWNER": cfg["owner"],
        "PARENT_ID": bay_asm, "STRUCTURE_CLASS": "VOLUME_OWNER_REFERENCE",
        "REPRESENTATION_LAYER": "OWNER_PLACEHOLDER_ZERO_SOLID",
        "EVIDENCE_STATE": cfg["state"],
        "SOURCE_REFERENCE": "V2_subsystem_volume_owner_register.yaml via b3_build_spec.yaml",
        "FRAME_ID": "CS_S", "INTERFACE_IDS": "",
        "MASS_OWNER": cfg["mass_owner"],
        "NO_DYNAMICS_USE": "true", "MANUFACTURING_AUTHORITY": "NONE",
        "EXECUTION_AUTHORITY": "DISPLAY_ONLY",
        "CLAIM_LIMIT": ("geometry_NULL_unsourced;no_hardware_selected;"
                        "no_real_dims;no_mass;no_thermal"
                        + (";ZERO_SOLID_REQUIRED" if zero else "")),
        "SERVICE_DIRECTION": str(cfg["service"]),
        "MOUNT_PLANE": str(cfg.get("mount_plane", "null")),
        "BLOCKED_CONSUMERS": "FEA;dynamics;mass_properties;manufacturing;"
                             "hardware_selection;thermal",
    }


def build_owner_ref_part(sw, log, out_path, vol_id, station_x, props):
    if out_path.exists():
        log.event("PART_SKIP_EXISTS", part=out_path.name)
        return
    model = new_document(sw, log, "part")
    safe = vol_id.replace("-", "_")
    create_offset_plane(model, log, RIGHT, station_x, f"PLN_{safe}_STATION",
                        flip=station_x < 0)
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(f"PLN_{safe}_STATION", "PLANE", 0, 0, 0,
                                       False, 0, None, 0):
        log.fail("选择站位面失败", vol=vol_id)
    sk = model.SketchManager
    sk.InsertSketch(True)
    sk.CreatePoint(0.0, 0.0, 0.0)
    sk.InsertSketch(True)
    rename_last_feature(model, log, f"SK_{safe}_OWNER_POINT")
    body_count = get_com_member(cast(model, "IPartDoc"), "GetBodies2", 0, True)
    n_solid = len(body_count) if isinstance(body_count, tuple) else 0
    if n_solid:
        log.fail("owner 参考件出现实体，违反零实体要求", vol=vol_id)
    set_custom_properties(model, log, props)
    rebuild_or_fail(model, log, vol_id)
    save_as(model, log, out_path)
    sw.CloseDoc(get_com_member(model, "GetTitle"))
    log.event("OWNER_REF_BUILT", vol=vol_id, zero_solid=True)


def panel_props(oid, name, parent):
    return {
        "OBJECT_ID": oid, "SYSTEM_OWNER": "secondary_structure",
        "PARENT_ID": parent, "STRUCTURE_CLASS": "SECONDARY_PROPOSAL",
        "REPRESENTATION_LAYER": "SYSTEM_MECHANICAL_DISPLAY",
        "EVIDENCE_STATE": "DESIGN_PROPOSAL",
        "SOURCE_REFERENCE": "b3_build_spec.yaml bay_volume_owners.access_panels",
        "FRAME_ID": "CS_S", "INTERFACE_IDS": "",
        "MASS_OWNER": "NONE_DISPLAY_ONLY", "NO_DYNAMICS_USE": "true",
        "MANUFACTURING_AUTHORITY": "NONE", "EXECUTION_AUTHORITY": "DISPLAY_ONLY",
        "CLAIM_LIMIT": "removable_panel_display;may_close_primary_path=false;"
                       "no_fastening_method;NO_STRENGTH_CLAIM",
        "BLOCKED_CONSUMERS": "FEA;dynamics;mass_properties;manufacturing",
    }


def main():
    log = BuildLog("b3_05_bays")
    sw = connect(log)
    sw.CloseAllDocuments(True)

    for bay_key, (mod_dir, asm_name) in BAYS.items():
        asm_path = V2_ROOT / mod_dir / f"{asm_name}.SLDASM"
        if asm_path.exists():
            log.event("ASM_SKIP_EXISTS", asm=asm_name)
            continue
        parts_dir = V2_ROOT / mod_dir / "parts"
        parts_dir.mkdir(parents=True, exist_ok=True)
        for vol_id, cfg in BVO[bay_key].items():
            build_owner_ref_part(sw, log,
                                 parts_dir / f"{vol_id.replace('-', '_')}.SLDPRT",
                                 vol_id, cfg["station_x_mm"],
                                 vol_props(vol_id, asm_name, cfg))
        if bay_key == "front_mission_bay":
            ap = BVO["access_panels"]["PNL_FRONT_MISSION_ACCESS"]
            build_x_extruded_part(
                sw, log, parts_dir / "PNL_FRONT_MISSION_ACCESS.SLDPRT",
                "PNL_FRONT_MISSION_ACCESS",
                [(0.0, 90.075, 98.15, 8.075), (0.0, -90.075, 98.15, 8.075),
                 (90.075, 0.0, 8.075, 82.0), (-90.075, 0.0, 8.075, 82.0)],
                ap["x_span_mm"],
                panel_props("V2-FM-PNL", "PNL_FRONT_MISSION_ACCESS", asm_name))
        if bay_key == "rear_service_bay":
            ap = BVO["access_panels"]["PNL_REAR_SERVICE_ACCESS"]
            h = ap["half_wh_mm"]
            build_x_extruded_part(
                sw, log, parts_dir / "PNL_REAR_SERVICE_ACCESS.SLDPRT",
                "PNL_REAR_SERVICE_ACCESS", [(0.0, 0.0, h, h)], ap["x_span_mm"],
                panel_props("V2-RS-PNL", "PNL_REAR_SERVICE_ACCESS", asm_name))
        asm_model = new_document(sw, log, "assembly")
        insert_components_identity(sw, log, asm_model,
                                   sorted(parts_dir.glob("*.SLDPRT")))
        set_custom_properties(asm_model, log, {
            "OBJECT_ID": asm_name, "SYSTEM_OWNER": bay_key,
            "PARENT_ID": "Spacecraft_Service_Vehicle_V2_0",
            "STRUCTURE_CLASS": "BAY_MODULE", "REPRESENTATION_LAYER":
            "SYSTEM_MECHANICAL_DISPLAY", "EVIDENCE_STATE": "DESIGN_PROPOSAL",
            "SOURCE_REFERENCE": "b3_build_spec.yaml bay_volume_owners",
            "FRAME_ID": "CS_S", "INTERFACE_IDS": "", "MASS_OWNER":
            "NONE_DISPLAY_ONLY", "NO_DYNAMICS_USE": "true",
            "MANUFACTURING_AUTHORITY": "NONE", "EXECUTION_AUTHORITY":
            "DISPLAY_ONLY", "CLAIM_LIMIT": "bay_owner_container_display_only",
            "BLOCKED_CONSUMERS": "FEA;dynamics;mass_properties;manufacturing"})
        rebuild_or_fail(asm_model, log, asm_name)
        save_as(asm_model, log, asm_path)
        sw.CloseAllDocuments(True)
        log.event("BAY_DONE", bay=bay_key)
    log.event("B3_05_DONE")
    print("BAYS_BUILD_OK")


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
