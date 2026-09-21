"""B3-02 修复：把三个建错侧的参考面翻转到负向（就地 ModifyDefinition）。

根因：初版 create_offset_plane 用了错误的 flip 位（64），正确为
swRefPlaneReferenceConstraint_OptionFlip=256。本脚本对
PLANE_REAR_BODY_FACE / PLANE_REAR_MID_BOUNDARY / PLANE_SOLAR_ROOT_R
设置 ReversedReferenceDirection 后重建保存；随后必须重跑 b3_02_verify.py。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from b3_lib.sw_core import (B3FailClosed, BuildLog, V2_ROOT, cast, connect,
                            get_com_member, open_document, rebuild_or_fail, save)

PART = V2_ROOT / "00_Master_Skeleton/Master_Skeleton_V2_0.SLDPRT"
TO_FLIP = ["PLANE_REAR_BODY_FACE", "PLANE_REAR_MID_BOUNDARY", "PLANE_SOLAR_ROOT_R"]


def set_reversed(data, value=True):
    for setter in ("SetReversedReferenceDirection",):
        fn = getattr(data, setter, None)
        if fn is not None:
            fn(0, value)
            return True
    try:
        data.ReversedReferenceDirection(0, value)
        return True
    except Exception:
        pass
    try:
        data.ReversedReferenceDirection = value
        return True
    except Exception:
        return False


def main():
    log = BuildLog("b3_02_fix_planes")
    sw = connect(log)
    sw.CloseAllDocuments(True)
    model = open_document(sw, log, PART)
    fixed = []
    f = cast(get_com_member(model, "FirstFeature"), "IFeature")
    while f is not None:
        if f.Name in TO_FLIP:
            data = get_com_member(f, "GetDefinition")
            data = cast(data, "IRefPlaneFeatureData")
            try:
                data.AccessSelections(model, None)
            except Exception:
                pass
            if not set_reversed(data, True):
                log.fail("无法设置 ReversedReferenceDirection", feature=f.Name)
            if not f.ModifyDefinition(data, model, None):
                log.fail("ModifyDefinition 失败", feature=f.Name)
            fixed.append(f.Name)
            log.event("PLANE_FLIPPED", name=f.Name)
        f = cast(get_com_member(f, "GetNextFeature"), "IFeature")
    if set(fixed) != set(TO_FLIP):
        log.fail("有平面未找到", fixed=fixed, wanted=TO_FLIP)
    rebuild_or_fail(model, log, "after_flip")
    save(model, log)
    sw.CloseAllDocuments(True)
    log.event("B3_02_FIX_DONE", fixed=fixed)
    print("PLANES_FLIPPED_OK")


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
