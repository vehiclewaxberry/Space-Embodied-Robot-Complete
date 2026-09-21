"""B3-08 修复 D-V2-04：中部两框环径向内缩至侧板内面（113.15→110.15）。

根因：侧板为外蒙皮（径向 [110.15,113.15]），中框band原建到包络 113.15，
在框站位与四块侧板体积重叠（8 对干涉）。端框不在侧板覆盖区，保持原状。
就地重建特征（文件身份保留，装配引用不断）后重跑 scoped 干涉。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from b3_lib.sw_core import (B3FailClosed, BuildLog, V2_ROOT, cast, connect,
                            get_com_member, open_document, rebuild_or_fail, save)
from b3_lib.sw_part_factory import extrude_checked, yz_rect_to_sketch

PARTS = {
    "FRM_REAR_MID": [-62.75, -50.75],
    "FRM_MID_FRONT": [50.75, 62.75],
}
HIN = 98.15
OUT_R = 110.15            # 新径向外缘 = 侧板内面
BAR_C = (HIN + OUT_R) / 2  # 104.15
BAR_H = (OUT_R - HIN) / 2  # 6.0
NEW_RECTS = [(0.0, BAR_C, HIN, BAR_H), (0.0, -BAR_C, HIN, BAR_H),
             (BAR_C, 0.0, BAR_H, HIN), (-BAR_C, 0.0, BAR_H, HIN)]


def main():
    log = BuildLog("b3_08_fix_mid_frames")
    sw = connect(log)
    sw.CloseAllDocuments(True)
    for name, x_span in PARTS.items():
        path = V2_ROOT / f"01_Primary_Structure/parts/{name}.SLDPRT"
        model = open_document(sw, log, path)
        # 删除 4 个挤出（对象级选择——类型串 ICE/Extrusion 混杂，按名匹配最稳）
        targets = {f"EX_{name}_{i}" for i in range(1, 5)}
        model.ClearSelection2(True)
        f = cast(get_com_member(model, "FirstFeature"), "IFeature")
        n_sel = 0
        while f is not None:
            if f.Name in targets:
                if not f.Select2(True, 0):
                    log.fail("特征对象选择失败", part=name, feature=f.Name)
                n_sel += 1
            f = cast(get_com_member(f, "GetNextFeature"), "IFeature")
        if n_sel != 4:
            log.fail("旧挤出数目异常", part=name, selected=n_sel)
        if not model.Extension.DeleteSelection2(1):   # 1=swDelete_Absorbed
            log.fail("删除旧特征失败", part=name)
        log.event("OLD_FEATURES_DELETED", part=name, count=n_sel)
        # 重建 4 段内缩梁条
        x_min, x_max = x_span
        for i, r in enumerate(NEW_RECTS):
            model.ClearSelection2(True)
            if not model.Extension.SelectByID2(f"PLN_{name}_BASE", "PLANE",
                                               0, 0, 0, False, 0, None, 0):
                log.fail("选择基面失败", part=name)
            sk = model.SketchManager
            sk.InsertSketch(True)
            sk.CreateCenterRectangle(*yz_rect_to_sketch(*r))
            sk.InsertSketch(True)
            extrude_checked(model, log, x_max - x_min, "x", x_min, x_max,
                            f"EX_{name}_{i+1}", plane_off_mm=x_min)
            feats = cast(model, "IModelDoc2").FeatureManager.GetFeatures(True)
            cast(feats[-2], "IFeature").Name = f"SK_{name}_{i+1}"
        # 属性追加内缩说明
        mgr = model.Extension.CustomPropertyManager("")
        mgr.Add3("CLAIM_LIMIT", 30,
                 "display_topology_only;section_material_joints_UNKNOWN_BLOCKED;"
                 "NO_STRENGTH_CLAIM;radial_outer_inset_to_panel_inner_110.15_D-V2-04",
                 2)
        rebuild_or_fail(model, log, name)
        save(model, log)
        sw.CloseAllDocuments(True)
        log.event("MID_FRAME_FIXED", part=name)
    log.event("B3_08_FIX_DONE")
    print("MID_FRAMES_FIXED_OK")


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
