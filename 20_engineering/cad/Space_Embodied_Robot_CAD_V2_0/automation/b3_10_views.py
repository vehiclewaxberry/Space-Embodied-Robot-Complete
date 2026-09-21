"""B3-10a 评审视图：15 张 raw + annotated（V2_review_view_plan 对应）。

每张绑定配置；annotated 版加标题/配置/claim/日期水印（PIL）。剖切用
"外板抑制配置"方法表达并在注记声明。V2-VIEW-15 为独立 target 场景
（target 不入主装配），加 NO_CONTACT / NO_AUTONOMOUS_CAPTURE CLAIM 水印。
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
from b3_lib.sw_core import (B3FailClosed, BuildLog, V2_ROOT, activate_configuration,
                            cast, connect, get_com_member,
                            insert_components_identity, new_document,
                            open_document, rebuild_or_fail, save_as,
                            set_custom_properties)
from b3_lib.sw_part_factory import build_x_extruded_part

TOP = V2_ROOT / "Assembly/Spacecraft_Service_Vehicle_V2_0.SLDASM"
RAW = V2_ROOT / "10_Review_Overlays/review_views/raw"
ANN = V2_ROOT / "10_Review_Overlays/review_views/annotated"
SCENE_DIR = V2_ROOT / "10_Review_Overlays/target_scene_independent"

# (编号, 名称, 配置, 朝向, 缩放盒或 None, 附加说明)
ISO, FRONT_V, TOP_V, RIGHT_V = 7, 1, 5, 4
MOUNT_BOX = (0.10, -0.15, -0.15, 0.30, 0.15, 0.15)
MID_BOX = (-0.06, -0.13, -0.13, 0.06, 0.13, 0.13)
REAR_BOX = (-0.18, -0.13, -0.13, -0.05, 0.13, 0.13)
VIEWS = [
    ("V2-VIEW-01", "whole_vehicle_module_overview", "EVIDENCE_STATE_REVIEW", ISO, None, ""),
    ("V2-VIEW-02", "primary_structure_only", "STRUCTURAL_REVIEW", ISO, None,
     "外板/太阳翼抑制"),
    ("V2-VIEW-03", "primary_secondary_reference_classification",
     "EVIDENCE_STATE_REVIEW", ISO, None, "分类见 structure_class_inventory.csv"),
    ("V2-VIEW-04", "three_bay_cutaway", "STRUCTURAL_REVIEW", TOP_V, None,
     "剖切以外板抑制配置表达"),
    ("V2-VIEW-05", "robot_mount_section", "STRUCTURAL_REVIEW", RIGHT_V, MOUNT_BOX,
     "局部视图（外板抑制）"),
    ("V2-VIEW-06", "robot_reaction_load_path", "STRUCTURAL_REVIEW", ISO, MOUNT_BOX,
     "B601→adapter→前框→纵梁；NO_STRENGTH_CLAIM"),
    ("V2-VIEW-07", "avionics_EPS_ADCS_volume_owners", "SERVICE_ACCESS_REVIEW",
     ISO, MID_BOX, "零实体 owner（几何 NULL 未授权填充）"),
    ("V2-VIEW-08", "rear_service_zone_owners", "SERVICE_ACCESS_REVIEW", ISO,
     REAR_BOX, "PROP=UNKNOWN_BLOCKED 零实体"),
    ("V2-VIEW-09", "removable_panels_and_tray_directions", "SERVICE_ACCESS_REVIEW",
     ISO, None, "托盘抽取方向 TBD（无来源不画）"),
    ("V2-VIEW-10", "harness_and_service_corridor", "SERVICE_ACCESS_REVIEW",
     FRONT_V, None, "走廊 candidate；截面 null"),
    ("V2-VIEW-11", "solar_interfaces_and_keepouts", "DEPLOYED_REFERENCE_Q0",
     ISO, None, "根部铰链 UNKNOWN；q0 参考态"),
    ("V2-VIEW-12", "stowed_configuration_proposal", "STOWED_PROPOSAL", ISO, None,
     "收拢几何 UNKNOWN，以抑制表达；无飞行收拢声明"),
    ("V2-VIEW-13", "evidence_state_overview", "EVIDENCE_STATE_REVIEW", ISO, None,
     "EVIDENCE_BOUND/DESIGN_PROPOSAL/UNKNOWN_BLOCKED/EXCLUDED 见清单"),
    ("V2-VIEW-14", "V1_to_V2_system_mechanical_delta", "EVIDENCE_STATE_REVIEW",
     ISO, None, "偏差见 v1_to_v2_deviation_manifest.csv"),
]


def annotate(src: Path, dst: Path, title, config, note):
    im = Image.open(src).convert("RGB")
    d = ImageDraw.Draw(im)
    bar_h = 90
    d.rectangle([0, im.height - bar_h, im.width, im.height], fill=(20, 20, 20))
    lines = [f"{title}  |  CONFIG={config}  |  B601=q_zero",
             f"claim: {note or 'display_only'}  |  NO_DYNAMICS  NO_STRENGTH_CLAIM"
             f"  NON_FLIGHT_DISPLAY_ONLY",
             f"generated {datetime.now(timezone.utc).isoformat()}  |  "
             f"Space_Embodied_Robot_CAD_V2_0"]
    y = im.height - bar_h + 8
    for ln in lines:
        d.text((12, y), ln, fill=(240, 240, 240))
        y += 26
    im.save(dst)


def shoot(model, path, orient, zoombox):
    model.ShowNamedView2("", orient)
    if zoombox:
        model.ViewZoomTo2(*zoombox)
    else:
        model.ViewZoomtofit2()
    return model.SaveBMP(str(path), 1600, 1200)


def build_target_scene(sw, log):
    """独立 target 场景：碎片包络盒（SSOT target_models_v1.yaml 的显示包络），
    不进入主装配，无配合无接触。"""
    import yaml
    scene_asm = SCENE_DIR / "Target_Scene_Independent.SLDASM"
    if scene_asm.exists():
        return scene_asm
    SCENE_DIR.mkdir(parents=True, exist_ok=True)
    tm = yaml.safe_load(Path(
        r"F:/China Graduate Future Flight Vehicle Innovation Competition/"
        r"20_engineering/config/geometry/target_models_v1.yaml").read_text(encoding="utf-8"))
    dims = None
    for key in ("target_debris", "debris", "target_debris_v0"):
        node = tm.get(key) or (tm.get("targets", {}) or {}).get(key)
        if isinstance(node, dict):
            g = node.get("geometry", node)
            for dk in ("envelope_m", "size_m", "dimensions_m"):
                if dk in g:
                    dims = [float(v) * 1000 for v in g[dk]]
                    break
        if dims:
            break
    if not dims:
        dims = [1000.0, 1000.0, 1000.0]
        src_note = "envelope_not_in_SSOT_using_1m_display_cube_UNSOURCED"
    else:
        src_note = "target_models_v1.yaml"
    part = SCENE_DIR / "TARGET_DEBRIS_ENVELOPE_REF.SLDPRT"
    if not part.exists():
        build_x_extruded_part(
            sw, log, part, "TARGET_DEBRIS_ENVELOPE_REF",
            [(0.0, 0.0, dims[1] / 2, dims[2] / 2)],
            [-dims[0] / 2, dims[0] / 2],
            {"OBJECT_ID": "V2-TGT-REF", "SYSTEM_OWNER": "MISSION_TARGET_OWNER",
             "PARENT_ID": "Target_Scene_Independent",
             "STRUCTURE_CLASS": "EXCLUDED_INDEPENDENT_SCENE",
             "REPRESENTATION_LAYER": "ENVELOPE_REFERENCE",
             "EVIDENCE_STATE": "EXCLUDED",
             "SOURCE_REFERENCE": src_note, "FRAME_ID": "T_ST_EXCLUDED",
             "INTERFACE_IDS": "", "MASS_OWNER": "target_scenario_EXCLUDED",
             "NO_DYNAMICS_USE": "true", "MANUFACTURING_AUTHORITY": "NONE",
             "EXECUTION_AUTHORITY": "DISPLAY_ONLY",
             "CLAIM_LIMIT": "independent_scene_only;no_contact;no_mate;"
                            "no_capture_claim;excluded_from_active_assembly",
             "BLOCKED_CONSUMERS": "active_assembly;contact;capture_claims"})
    asm_model = new_document(sw, log, "assembly")
    insert_components_identity(sw, log, asm_model, [part])
    set_custom_properties(asm_model, log, {
        "OBJECT_ID": "V2-TGT-SCENE", "SYSTEM_OWNER": "MISSION_TARGET_OWNER",
        "PARENT_ID": "", "STRUCTURE_CLASS": "EXCLUDED_INDEPENDENT_SCENE",
        "REPRESENTATION_LAYER": "INDEPENDENT_SCENE",
        "EVIDENCE_STATE": "EXCLUDED", "SOURCE_REFERENCE": "b3_10_views.py",
        "FRAME_ID": "T_ST_EXCLUDED", "INTERFACE_IDS": "",
        "MASS_OWNER": "target_scenario_EXCLUDED", "NO_DYNAMICS_USE": "true",
        "MANUFACTURING_AUTHORITY": "NONE", "EXECUTION_AUTHORITY": "DISPLAY_ONLY",
        "CLAIM_LIMIT": "NO_CONTACT;NO_AUTONOMOUS_CAPTURE_CLAIM",
        "BLOCKED_CONSUMERS": "active_assembly"})
    rebuild_or_fail(asm_model, log, "target_scene")
    save_as(asm_model, log, scene_asm)
    return scene_asm


def main():
    log = BuildLog("b3_10_views")
    RAW.mkdir(parents=True, exist_ok=True)
    ANN.mkdir(parents=True, exist_ok=True)
    sw = connect(log, visible=True)   # 截图需要渲染
    sw.CloseAllDocuments(True)
    model = open_document(sw, log, TOP)
    manifest = []
    for vid, name, config, orient, zoom, note in VIEWS:
        activate_configuration(model, log, config)
        rebuild_or_fail(model, log, vid)
        raw = RAW / f"{vid}_{name}.bmp"
        if not shoot(model, raw, orient, zoom):
            log.fail("截图失败", view=vid)
        ann = ANN / f"{vid}_{name}_annotated.png"
        annotate(raw, ann, f"{vid} {name}", config, note)
        manifest.append({"view": vid, "name": name, "config": config,
                         "raw": str(raw.relative_to(V2_ROOT)),
                         "annotated": str(ann.relative_to(V2_ROOT)),
                         "claim_note": note})
        log.event("VIEW_EXPORTED", view=vid, config=config)
    activate_configuration(model, log, "DEPLOYED_REFERENCE_Q0")
    sw.CloseAllDocuments(True)

    scene = build_target_scene(sw, log)
    m2 = open_document(sw, log, scene)
    raw15 = RAW / "V2-VIEW-15_independent_target_scene.bmp"
    if not shoot(m2, raw15, ISO, None):
        log.fail("target 场景截图失败")
    ann15 = ANN / "V2-VIEW-15_independent_target_scene_annotated.png"
    im = Image.open(raw15).convert("RGB")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, im.width, 60], fill=(120, 0, 0))
    d.text((12, 8), "INDEPENDENT TARGET SCENE — NO_CONTACT / "
                    "NO_AUTONOMOUS_CAPTURE_CLAIM", fill=(255, 255, 255))
    d.text((12, 32), "target EXCLUDED from active assembly; no mates; "
                     "scenario reference only", fill=(255, 255, 255))
    im.save(ann15)
    manifest.append({"view": "V2-VIEW-15", "name": "independent_target_scene",
                     "config": "INDEPENDENT_SCENE",
                     "raw": str(raw15.relative_to(V2_ROOT)),
                     "annotated": str(ann15.relative_to(V2_ROOT)),
                     "claim_note": "NO_CONTACT;NO_AUTONOMOUS_CAPTURE_CLAIM"})
    sw.CloseAllDocuments(True)
    (V2_ROOT / "10_Review_Overlays/review_view_manifest.json").write_text(
        json.dumps({"generated_utc": datetime.now(timezone.utc).isoformat(),
                    "views": manifest}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    log.event("B3_10A_DONE", views=len(manifest))
    print("REVIEW_VIEWS_OK", len(manifest))


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
