"""B3-04 机械臂安装模块：法兰/板/boss/肋条 + 参考件 → SV2_Robot_Mount_Module.SLDASM。

adapter 与 bus structure owner 分离；反力链回链 LPE_*；六维载荷仅符号表达。
禁止出现 STRENGTH_PASS/STIFFNESS_PASS/MODAL_PASS/FLIGHT_QUALIFIED。
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
RMP = SPEC["robot_mount_display_proposal"]
PARTS_DIR = V2_ROOT / "05_Robot_Mount_Module/parts"
ASM_PATH = V2_ROOT / "05_Robot_Mount_Module/SV2_Robot_Mount_Module.SLDASM"
MX = 0.18525   # M 面（米）


def props_for(oid, name, owner, evidence, claim, lp="", ifaces="IF-RM-001"):
    return {
        "OBJECT_ID": oid, "SYSTEM_OWNER": owner,
        "PARENT_ID": "SV2_Robot_Mount_Module",
        "STRUCTURE_CLASS": "PRIMARY_PROPOSAL" if owner == "bus_structure"
        else "SECONDARY_PROPOSAL",
        "REPRESENTATION_LAYER": "SYSTEM_MECHANICAL_DISPLAY",
        "EVIDENCE_STATE": evidence,
        "SOURCE_REFERENCE": "b3_build_spec.yaml robot_mount_display_proposal"
                            + (f"; load_path:{lp}" if lp else ""),
        "FRAME_ID": "CS_M", "INTERFACE_IDS": ifaces,
        "MASS_OWNER": "NONE_DISPLAY_ONLY", "NO_DYNAMICS_USE": "true",
        "MANUFACTURING_AUTHORITY": "NONE", "EXECUTION_AUTHORITY": "DISPLAY_ONLY",
        "CLAIM_LIMIT": claim, "NO_STRENGTH_CLAIM": "true",
        "BLOCKED_CONSUMERS": "FEA;dynamics;mass_properties;manufacturing;strength_claims",
    }


CLAIM = ("envelope_display_only;bolts_locators_loads_stiffness_UNKNOWN_BLOCKED;"
         "NO_STRENGTH_CLAIM")


def build_reference_part(sw, log):
    """参考件：虚拟 F/T 面、线缆过孔、工具 keepout、六维符号载荷 overlay。"""
    out = PARTS_DIR / "SV2_MNT_REFERENCES.SLDPRT"
    if out.exists():
        log.event("PART_SKIP_EXISTS", part=out.name)
        return
    model = new_document(sw, log, "part")
    create_offset_plane(model, log, RIGHT, 185.25, "VIRTUAL_FT_INTERFACE")
    # 线缆过孔 reference：法兰外面 Ø30 @ (y=+55, z=0)
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2("VIRTUAL_FT_INTERFACE", "PLANE", 0, 0, 0,
                                       False, 0, None, 0):
        log.fail("选择 VIRTUAL_FT_INTERFACE 失败")
    sk = model.SketchManager
    sk.InsertSketch(True)
    sk.CreateCircleByRadius(0.0, 0.055, 0.0, 0.015)
    sk.InsertSketch(True)
    rename_last_feature(model, log, "SK_CABLE_PASSAGE_REF")
    # 工具访问 keepout：M 外侧 200x200x100 线框（3D 草图）
    sk.Insert3DSketch(True)
    hy = hz = 0.100
    x0, x1 = MX, MX + 0.100
    c = [(x, sy * hy, sz * hz) for x in (x0, x1) for sy in (-1, 1) for sz in (-1, 1)]
    for a, b in [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7),
                 (0, 4), (1, 5), (2, 6), (3, 7)]:
        sk.CreateLine(*c[a], *c[b])
    sk.Insert3DSketch(True)
    rename_last_feature(model, log, "SK3D_TOOL_ACCESS_KEEPOUT")
    # 六维符号载荷 overlay：M 点沿 ±X/±Y/±Z 六条短线（符号接口，非载荷证据）
    sk.Insert3DSketch(True)
    L = 0.04
    for d in [(L, 0, 0), (-L, 0, 0), (0, L, 0), (0, -L, 0), (0, 0, L), (0, 0, -L)]:
        sk.CreateLine(MX, 0, 0, MX + d[0], d[1], d[2])
    sk.Insert3DSketch(True)
    rename_last_feature(model, log, "SK3D_WRENCH_OVERLAY_SYMBOLIC")
    set_custom_properties(model, log, props_for(
        "V2-MNT-005", "SV2_MNT_REFERENCES", "robot_mount_references",
        "DESIGN_PROPOSAL",
        CLAIM + ";wrench_overlay_symbolic_no_values;visual_arrow_is_not_load_evidence",
        ifaces="IF-RM-001;IF-RM-002"))
    rebuild_or_fail(model, log, "SV2_MNT_REFERENCES")
    save_as(model, log, out)
    sw.CloseDoc(get_com_member(model, "GetTitle"))
    log.event("PART_BUILT", part="SV2_MNT_REFERENCES")


def main():
    log = BuildLog("b3_04_robot_mount")
    if ASM_PATH.exists():
        log.fail("SV2_Robot_Mount_Module.SLDASM 已存在，禁止无条件覆盖")
    PARTS_DIR.mkdir(parents=True, exist_ok=True)
    sw = connect(log)
    sw.CloseAllDocuments(True)

    p = RMP["parts"]
    fl = p["SV2_MNT_SERVICER_FLANGE"]
    build_x_extruded_part(
        sw, log, PARTS_DIR / "SV2_MNT_SERVICER_FLANGE.SLDPRT",
        "SV2_MNT_SERVICER_FLANGE",
        [(0.0, 0.0, fl["section_mm"][0] / 2, fl["section_mm"][1] / 2)],
        fl["x_span_mm"],
        props_for("V2-MNT-001", "SV2_MNT_SERVICER_FLANGE", "bus_structure",
                  "EVIDENCE_BOUND", CLAIM + ";envelope_15x160x160_EVIDENCE_BOUND",
                  fl["lp_id"]))
    pl = p["SV2_MNT_ADAPTER_PLATE"]
    build_x_extruded_part(
        sw, log, PARTS_DIR / "SV2_MNT_ADAPTER_PLATE.SLDPRT",
        "SV2_MNT_ADAPTER_PLATE",
        [(0.0, 0.0, pl["section_mm"][0] / 2, pl["section_mm"][1] / 2)],
        pl["x_span_mm"],
        props_for("V2-MNT-002", "SV2_MNT_ADAPTER_PLATE", "robot_adapter",
                  "EVIDENCE_BOUND", CLAIM + ";envelope_12x160x160_EVIDENCE_BOUND",
                  pl["lp_id"], "IF-RM-001;IF-RM-002"))
    bs = p["SV2_MNT_ADAPTER_BOSS"]
    build_x_extruded_part(
        sw, log, PARTS_DIR / "SV2_MNT_ADAPTER_BOSS.SLDPRT",
        "SV2_MNT_ADAPTER_BOSS",
        [(0.0, 0.0, bs["diameter_mm"] / 2)], bs["x_span_mm"],
        props_for("V2-MNT-003", "SV2_MNT_ADAPTER_BOSS", "robot_adapter",
                  "EVIDENCE_BOUND", CLAIM + ";envelope_D100x15_EVIDENCE_BOUND",
                  bs["lp_id"], "IF-RM-002"))
    rb = p["SV2_MNT_RIB_SET"]
    lo, hi = rb["bar_span_mm"]
    mid, half = (lo + hi) / 2, (hi - lo) / 2
    w = rb["bar_width_mm"] / 2
    build_x_extruded_part(
        sw, log, PARTS_DIR / "SV2_MNT_RIB_SET.SLDPRT", "SV2_MNT_RIB_SET",
        [(mid, 0.0, half, w), (-mid, 0.0, half, w),
         (0.0, mid, w, half), (0.0, -mid, w, half)], rb["x_span_mm"],
        props_for("V2-MNT-004", "SV2_MNT_RIB_SET", "bus_structure",
                  "DESIGN_PROPOSAL",
                  CLAIM + ";" + rb["claim"] + ";suppressible_proposal",
                  "LPE_003"))
    build_reference_part(sw, log)

    asm_model = new_document(sw, log, "assembly")
    insert_components_identity(sw, log, asm_model,
                               sorted(PARTS_DIR.glob("*.SLDPRT")))
    set_custom_properties(asm_model, log, props_for(
        "V2-MNT-000", "SV2_Robot_Mount_Module", "robot_mount_module",
        "DESIGN_PROPOSAL", CLAIM, "LPE_001..003",
        "IF-RM-001;IF-RM-002"))
    rebuild_or_fail(asm_model, log, "robot_mount_asm")
    save_as(asm_model, log, ASM_PATH)
    sw.CloseAllDocuments(True)
    log.event("B3_04_DONE", parts=len(list(PARTS_DIR.glob("*.SLDPRT"))))
    print("ROBOT_MOUNT_BUILD_OK")


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
