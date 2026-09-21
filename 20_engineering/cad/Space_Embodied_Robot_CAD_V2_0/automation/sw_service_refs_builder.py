"""B3-07 维护/装配/线束 reference：全部为具名 3D 草图/点参考，不入质量/BOM。

治理要点（R3）：托盘抽取方向 TBD ⇒ 只登记 token 不画方向箭头；面板拆卸方向为
DESIGN_PROPOSAL 可画；rail/tab、光学、plume、天线、热面 keepout 均 UNKNOWN_BLOCKED
⇒ 零几何 owner 锚点；线束走廊为 candidate（截面 null）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from b3_lib.sw_core import (B3FailClosed, BuildLog, V2_ROOT, connect,
                            get_com_member, new_document, rebuild_or_fail,
                            rename_last_feature, save_as, set_custom_properties)

MOD = V2_ROOT / "09_Service_Access_and_Harness_References"
OUT = MOD / "SV2_SERVICE_ACCESS_REFERENCES.SLDPRT"

M = 0.001
ARROW = 0.06     # 拆卸方向线长 60mm


def sk3d_lines(model, log, name, segments):
    sk = model.SketchManager
    sk.Insert3DSketch(True)
    for (a, b) in segments:
        sk.CreateLine(a[0] * M, a[1] * M, a[2] * M, b[0] * M, b[1] * M, b[2] * M)
    sk.Insert3DSketch(True)
    rename_last_feature(model, log, name)


def sk3d_point(model, log, name, p):
    sk = model.SketchManager
    sk.Insert3DSketch(True)
    sk.CreatePoint(p[0] * M, p[1] * M, p[2] * M)
    sk.Insert3DSketch(True)
    rename_last_feature(model, log, name)


def main():
    log = BuildLog("b3_07_service_refs")
    if OUT.exists():
        log.fail("SV2_SERVICE_ACCESS_REFERENCES.SLDPRT 已存在，禁止无条件覆盖")
    MOD.mkdir(parents=True, exist_ok=True)
    sw = connect(log)
    sw.CloseAllDocuments(True)
    model = new_document(sw, log, "part")

    # 1) 面板拆卸方向（DESIGN_PROPOSAL，R3 候选方向）
    face_arrows = [
        ("FRONT", (170.25, 0, 0), (170.25 + 60, 0, 0)),
        ("REAR", (-170.25, 0, 0), (-170.25 - 60, 0, 0)),
        ("LEFT", (0, 113.15, 0), (0, 113.15 + 60, 0)),
        ("RIGHT", (0, -113.15, 0), (0, -113.15 - 60, 0)),
        ("TOP", (0, 0, 113.15), (0, 0, 113.15 + 60)),
        ("BOTTOM", (0, 0, -113.15), (0, 0, -113.15 - 60)),
    ]
    sk3d_lines(model, log, "SK3D_PANEL_REMOVAL_DIRECTIONS",
               [(a, b) for _, a, b in face_arrows])

    # 2) B601 装拆路径（+X_S 轴向提案）
    sk3d_lines(model, log, "SK3D_B601_INSTALL_REMOVAL_PATH",
               [((185.25, 0, 0), (335.25, 0, 0))])

    # 3) 主线束走廊 candidate：后舱 breakout → 纵向走廊 → 各舱支线（截面 null）
    corridor = [((-160.0, 0, -80.0), (150.0, 0, -80.0)),          # 纵向主走廊
                ((-113.5, 0, -80.0), (-113.5, 0, -20.0)),         # 后舱支线
                ((0.0, 0, -80.0), (0.0, 0, -20.0)),               # 中舱支线
                ((113.5, 0, -80.0), (113.5, 0, -20.0)),           # 前舱/robot mount 支线
                ((-56.75, 0, -80.0), (-56.75, 80.0, -80.0)),      # 太阳翼根 L 支线
                ((-56.75, 0, -80.0), (-56.75, -80.0, -80.0))]     # 太阳翼根 R 支线
    sk3d_lines(model, log, "SK3D_HARNESS_CORRIDOR_CANDIDATE", corridor)

    # 4) 跨舱过孔 reference（两甲板中央 Ø 参考点位）
    sk3d_point(model, log, "SK3D_DECK_PASSAGE_REAR_MID", (-56.75, 0, -60.0))
    sk3d_point(model, log, "SK3D_DECK_PASSAGE_MID_FRONT", (56.75, 0, -60.0))

    # 5) 托盘抽取 TBD（只登记锚点，不画方向——方向无来源）
    sk3d_point(model, log, "SK3D_TRAY_EXTRACTION_TBD_ANCHOR", (0.0, 0, 0.0))

    # 6) UNKNOWN_BLOCKED keepout owner 锚点（零几何语义，仅 owner 登记）
    for name, p in [("SK3D_KEEPOUT_RAIL_TAB_OWNER", (-170.25, 0, 0)),
                    ("SK3D_KEEPOUT_SENSOR_OPTICAL_OWNER", (113.5, 0, 60.0)),
                    ("SK3D_KEEPOUT_PLUME_OWNER", (-170.25, 0, -60.0)),
                    ("SK3D_KEEPOUT_ANTENNA_OWNER", (-113.5, 0, 60.0)),
                    ("SK3D_KEEPOUT_THERMAL_OWNER", (-113.5, 60.0, 0))]:
        sk3d_point(model, log, name, p)

    set_custom_properties(model, log, {
        "OBJECT_ID": "V2-SVC-000",
        "SYSTEM_OWNER": "integration_and_maintenance",
        "PARENT_ID": "Spacecraft_Service_Vehicle_V2_0",
        "STRUCTURE_CLASS": "REFERENCE_ONLY",
        "REPRESENTATION_LAYER": "SERVICEABILITY_REFERENCE",
        "EVIDENCE_STATE": "DESIGN_PROPOSAL",
        "SOURCE_REFERENCE": "V2_serviceability_and_keepout_plan.md via b3_build_spec.yaml",
        "FRAME_ID": "CS_S", "INTERFACE_IDS": "",
        "MASS_OWNER": "NONE_REFERENCE_ONLY", "NO_DYNAMICS_USE": "true",
        "MANUFACTURING_AUTHORITY": "NONE", "EXECUTION_AUTHORITY": "DISPLAY_ONLY",
        "CLAIM_LIMIT": ("review_responsibility_only_not_real_accessibility;"
                        "no_tool_size_no_fastening_no_reachability;"
                        "tray_extraction_direction_TBD;harness_cross_section_null;"
                        "keepout_rail_tab_optical_plume_antenna_thermal_UNKNOWN_BLOCKED"),
        "TRAY_EXTRACTION": "TBD_NO_SOURCE",
        "BLOCKED_CONSUMERS": "FEA;dynamics;mass_properties;BOM;manufacturing",
    })
    rebuild_or_fail(model, log, "service_refs")
    save_as(model, log, OUT)
    sw.CloseAllDocuments(True)
    log.event("B3_07_DONE")
    print("SERVICE_REFS_BUILD_OK")


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
