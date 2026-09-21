"""B3-03 主结构构建器：4 框 + 4 纵梁 + 2 甲板 + 4 侧板 → SV2_Primary_Structure.SLDASM。

顺序按构建计划：前任务面承力框 → 后端框 → 纵梁 → 中部框 → 甲板 → 外板。
所有零件在 S 全局坐标建模，装配恒等插入并固定。合同回链：FRM_* ↔ LP_*。
截面尺寸=DESIGN_PROPOSAL_DISPLAY_ONLY（b3_build_spec.yaml structure_display_proposal），
不构成真实截面/材料/连接权威。
"""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from b3_lib.sw_core import (B3FailClosed, BuildLog, V2_ROOT, cast, connect,
                            get_com_member, new_document, rebuild_or_fail,
                            save_as, set_custom_properties)
from b3_lib.sw_part_factory import build_face_panel_part, build_x_extruded_part

SPEC = yaml.safe_load((V2_ROOT / "automation/b3_build_spec.yaml").read_text(encoding="utf-8"))
SDP = SPEC["structure_display_proposal"]
PARTS_DIR = V2_ROOT / "01_Primary_Structure/parts"
ASM_PATH = V2_ROOT / "01_Primary_Structure/SV2_Primary_Structure.SLDASM"

HB = 113.15      # BODY_HALF_Y/Z
NW = 15.0        # FRAME_BAND_WIDTH / LONGERON 截面
HIN = HB - NW    # 98.15 内开口半宽
BAR_C = HB - NW / 2.0   # 105.65 梁条/纵梁中心线

FRAME_RECTS = [   # (yc, zc, hy, hz) 四段梁条
    (0.0, BAR_C, HIN, NW / 2), (0.0, -BAR_C, HIN, NW / 2),
    (BAR_C, 0.0, NW / 2, HIN), (-BAR_C, 0.0, NW / 2, HIN)]


def props_for(object_id, name, structure_class, evidence_state, claim, lp_id="",
              interface_ids=""):
    return {
        "OBJECT_ID": object_id, "SYSTEM_OWNER": "primary_structure"
        if structure_class.startswith("PRIMARY") else "secondary_structure",
        "PARENT_ID": "SV2_Primary_Structure",
        "STRUCTURE_CLASS": structure_class,
        "REPRESENTATION_LAYER": "SYSTEM_MECHANICAL_DISPLAY",
        "EVIDENCE_STATE": evidence_state,
        "SOURCE_REFERENCE": "b3_build_spec.yaml structure_display_proposal"
                            + (f"; load_path:{lp_id}" if lp_id else ""),
        "FRAME_ID": "CS_S", "INTERFACE_IDS": interface_ids,
        "MASS_OWNER": "NONE_DISPLAY_ONLY", "NO_DYNAMICS_USE": "true",
        "MANUFACTURING_AUTHORITY": "NONE", "EXECUTION_AUTHORITY": "DISPLAY_ONLY",
        "CLAIM_LIMIT": claim,
        "BLOCKED_CONSUMERS": "FEA;dynamics;mass_properties;manufacturing;strength_claims",
    }


CLAIM_STRUCT = ("display_topology_only;section_material_joints_UNKNOWN_BLOCKED;"
                "NO_STRENGTH_CLAIM")


def build_parts(sw, log):
    frames = SDP["layout_rules"]["frames"]
    order = ["FRM_FRONT_TASK", "FRM_REAR_BOUNDARY", None, "FRM_REAR_MID",
             "FRM_MID_FRONT"]
    idx = 1
    for nm in ["FRM_FRONT_TASK", "FRM_REAR_BOUNDARY"]:
        fr = frames[nm]
        build_x_extruded_part(
            sw, log, PARTS_DIR / f"{nm}.SLDPRT", nm, FRAME_RECTS,
            fr["x_span_mm"],
            props_for(f"V2-STR-{idx:03d}", nm, "PRIMARY_PROPOSAL",
                      "DESIGN_PROPOSAL", CLAIM_STRUCT, fr["lp_id"],
                      "IF-RM-001" if nm == "FRM_FRONT_TASK" else ""))
        idx += 1
    for nm, pos in SDP["layout_rules"]["longerons"].items():
        yc, zc = pos["yc_mm"], pos["zc_mm"]
        build_x_extruded_part(
            sw, log, PARTS_DIR / f"{nm}.SLDPRT", nm,
            [(yc, zc, NW / 2, NW / 2)], [-170.25, 170.25],
            props_for(f"V2-STR-{idx:03d}", nm, "PRIMARY_PROPOSAL",
                      "DESIGN_PROPOSAL", CLAIM_STRUCT, "LP_LONGERON_SET"))
        idx += 1
    for nm in ["FRM_REAR_MID", "FRM_MID_FRONT"]:
        fr = frames[nm]
        build_x_extruded_part(
            sw, log, PARTS_DIR / f"{nm}.SLDPRT", nm, FRAME_RECTS,
            fr["x_span_mm"],
            props_for(f"V2-STR-{idx:03d}", nm, "PRIMARY_PROPOSAL",
                      "DESIGN_PROPOSAL", CLAIM_STRUCT, fr["lp_id"],
                      "IF-SA-L;IF-SA-R" if nm == "FRM_REAR_MID" else ""))
        idx += 1
    t = SDP["DECK_THICKNESS_MM"]
    for nm, d in SDP["layout_rules"]["decks"].items():
        xc = d["x_center_mm"]
        build_x_extruded_part(
            sw, log, PARTS_DIR / f"{nm}.SLDPRT", nm,
            [(0.0, 0.0, HIN, HIN)], [xc - t / 2, xc + t / 2],
            props_for(f"V2-STR-{idx:03d}", nm, d["class"], "DESIGN_PROPOSAL",
                      CLAIM_STRUCT + ";deck_class_TBD"))
        idx += 1
    for nm, p in SDP["layout_rules"]["side_panels"].items():
        build_face_panel_part(
            sw, log, PARTS_DIR / f"{nm}.SLDPRT", nm, p["face"],
            props_for(f"V2-STR-{idx:03d}", nm, "SECONDARY_PROPOSAL",
                      "DESIGN_PROPOSAL",
                      CLAIM_STRUCT + ";removable_panel;may_close_primary_path=false"))
        idx += 1


def activate_doc(sw, log, title):
    try:
        ret = sw.ActivateDoc3(title, False, 0, 0)
    except TypeError:
        from b3_lib.sw_core import byref_i4
        ret = sw.ActivateDoc3(title, False, 0, byref_i4())
    if ret is None or (isinstance(ret, tuple) and ret[0] is None):
        log.fail("ActivateDoc3 失败", title=title)


def build_assembly(sw, log):
    model = new_document(sw, log, "assembly")
    asm = cast(model, "IAssemblyDoc")
    asm_title = get_com_member(model, "GetTitle")
    comps = []
    for prt in sorted(PARTS_DIR.glob("*.SLDPRT")):
        from b3_lib.sw_core import open_document
        open_document(sw, log, prt, read_only=True)   # AddComponent5 要求已加载
        activate_doc(sw, log, asm_title)
        c = asm.AddComponent5(str(prt), 0, "", False, "", 0.0, 0.0, 0.0)
        if c is None:
            log.fail("AddComponent5 失败", part=prt.name)
        comps.append(cast(c, "IComponent2"))
        log.event("COMPONENT_ADDED", part=prt.name)
    model.ClearSelection2(True)
    for c in comps:
        c.Select4(True, None, False)
    asm.FixComponent()
    model.ClearSelection2(True)
    set_custom_properties(model, log, props_for(
        "V2-STR-000", "SV2_Primary_Structure", "PRIMARY_PROPOSAL",
        "DESIGN_PROPOSAL", CLAIM_STRUCT))
    rebuild_or_fail(model, log, "primary_structure_asm")
    save_as(model, log, ASM_PATH)
    sw.CloseDoc(get_com_member(model, "GetTitle"))


def main():
    log = BuildLog("b3_03_primary_structure")
    if ASM_PATH.exists():
        log.fail("SV2_Primary_Structure.SLDASM 已存在，禁止无条件覆盖")
    PARTS_DIR.mkdir(parents=True, exist_ok=True)
    sw = connect(log)
    sw.CloseAllDocuments(True)
    build_parts(sw, log)
    build_assembly(sw, log)
    log.event("B3_03_DONE", parts=len(list(PARTS_DIR.glob("*.SLDPRT"))))
    print("PRIMARY_STRUCTURE_BUILD_OK")


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
