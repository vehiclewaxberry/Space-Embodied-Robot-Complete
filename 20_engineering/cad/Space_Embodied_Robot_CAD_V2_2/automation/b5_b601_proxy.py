"""V2.2 B601 代理重建（偏移内建于几何，规避跨目录子装配位姿锁）。

来源：V2.0 evidence/b3_06/b601_q0_boxes.json（accepted URDF q0 正运动学 + STL 顶点界派生，
哈希 11/11 已核）。V2.2 轨 X 全体 +12.75（M 面 185.25→198.0）。
不修改 accepted URDF/STL，不修改 V2.0，不改 link/joint/质量拓扑（10L/9J 身份不变）。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import b3_lib.sw_core as core
from b3_lib.sw_core import (B3FailClosed, BuildLog, cast, connect, get_com_member,
                            insert_components_identity, new_document,
                            open_document, rebuild_or_fail, save, save_as,
                            set_custom_properties)
from b3_lib.sw_part_factory import build_x_extruded_part

V22 = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad/Space_Embodied_Robot_CAD_V2_2")
core.V2_ROOT = V22
core.LOG_DIR = V22 / "evidence" / "build_logs"
V20 = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad/Space_Embodied_Robot_CAD_V2_0")
BOXES = json.loads((V20 / "evidence/b3_06/b601_q0_boxes.json").read_text(encoding="utf-8"))
OFF = 12.75
D = V22 / "30_B601_Controlled_Subassembly/parts"
ASM = V22 / "30_B601_Controlled_Subassembly/SV22_B601_Proxy.SLDASM"
TOP = V22 / "Assembly/Spacecraft_Service_Vehicle_V2_2.SLDASM"
LINKS = ["base_link", "link1", "link2", "link3", "link4", "link5", "link6",
         "gripper_link", "gripper_left", "gripper_right"]


def props(i, link):
    return {"OBJECT_ID": f"V22-B601-{i:02d}", "SYSTEM_OWNER": "b601_controlled",
            "PARENT_ID": "SV22_B601_Proxy", "STRUCT_CLASS": "VISUAL_PROXY",
            "STRUCTURE_CLASS": "VISUAL_PROXY",
            "REPRESENTATION_LAYER": "AXIS_ALIGNED_BBOX_PROXY_Q0",
            "EVIDENCE_STATE": "EVIDENCE_BOUND",
            "SOURCE_REFERENCE": "V2_0/evidence/b3_06/b601_q0_boxes.json "
                                "(accepted URDF/STL hash 11/11) + display_track_offset_X_12.75",
            "FRAME_ID": "CS_A0_V22", "INTERFACE_IDS": "IF-RM-002",
            "MASS_OWNER": "b601_urdf_owner_NOT_from_visual", "NO_DYNAMICS_USE": "true",
            "MANUFACTURING_AUTHORITY": "NONE", "EXECUTION_AUTHORITY": "DISPLAY_ONLY",
            "CLAIM_LIMIT": "conservative_envelope_not_exact_vendor_geometry;q_zero;"
                           "topology_10L9J_unchanged;urdf_unmodified;"
                           "display_track_366;dynamics_SSOT_340.5_unchanged",
            "URDF_LINK": link,
            "BLOCKED_CONSUMERS": "FEA;dynamics;mass_properties;URDF_roundtrip"}


def main():
    log = BuildLog("b5_b601_proxy")
    D.mkdir(parents=True, exist_ok=True)
    sw = connect(log)
    sw.CloseAllDocuments(True)
    for i, link in enumerate(LINKS):
        b = BOXES["links"][link]["s_box_mm"]
        (x0, y0, z0), (x1, y1, z1) = b
        build_x_extruded_part(
            sw, log, D / f"B601V22_{link}.SLDPRT", f"B601V22_{link}",
            [((y0 + y1) / 2, (z0 + z1) / 2, (y1 - y0) / 2, (z1 - z0) / 2)],
            [x0 + OFF, x1 + OFF], props(i, link))
    if not ASM.exists():
        m = new_document(sw, log, "assembly")
        insert_components_identity(sw, log, m,
                                   [D / f"B601V22_{k}.SLDPRT" for k in LINKS])
        p = props(0, "assembly")
        p["OBJECT_ID"] = "V22-B601-000"
        set_custom_properties(m, log, p)
        rebuild_or_fail(m, log, "b601_proxy_asm")
        save_as(m, log, ASM)
        sw.CloseAllDocuments(True)
    # 顶装换装：删除 V2.0 引用组件，插入 V2.2 代理
    m = open_document(sw, log, TOP)
    asm = cast(m, "IAssemblyDoc")
    m.ClearSelection2(True)
    n = 0
    for c in asm.GetComponents(True) or []:
        c2 = cast(c, "IComponent2")
        if "SV2_B601_Visual_Arm" in c2.Name2:
            c2.Select4(True, None, False)
            n += 1
    if n:
        if not m.Extension.DeleteSelection2(0):
            log.fail("旧 B601 组件删除失败")
        log.event("OLD_B601_REMOVED", count=n)
    m.ClearSelection2(True)
    existing = {cast(c, "IComponent2").Name2.rsplit("-", 1)[0]
                for c in asm.GetComponents(True) or []}
    if "SV22_B601_Proxy" not in existing:
        insert_components_identity(sw, log, m, [ASM])
    rebuild_or_fail(m, log, "top_with_b601_v22")
    # 顶层含代理装配的断言
    top_names = {cast(c, "IComponent2").Name2.rsplit("-", 1)[0]
                 for c in asm.GetComponents(True) or []}
    if "SV22_B601_Proxy" not in top_names:
        log.fail("顶装未含 V2.2 B601 代理", top=sorted(top_names))
    if any("SV2_B601_Visual_Arm" in n for n in top_names):
        log.fail("旧 V2.0 B601 引用仍在顶装")
    save(m, log)
    sw.CloseAllDocuments(True)
    # 几何读回：代理 base_link 零件前缘 = 185.25+12.75 = 198.0（偏移内建于几何）
    pm = open_document(sw, log, D / "B601V22_base_link.SLDPRT", read_only=True)
    got = round(cast(pm, "IPartDoc").GetPartBox(True)[0] * 1000, 3)
    sw.CloseAllDocuments(True)
    if abs(got - 198.0) > 0.05:
        log.fail("B601 代理位置校验失败", got_mm=got, expected=198.0)
    log.event("B601_PROXY_POSITION_VERIFIED", base_link_x_mm=got)
    log.event("B5_B601_PROXY_DONE")
    print(f"B601_PROXY_OK base_link_x={got}")


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
