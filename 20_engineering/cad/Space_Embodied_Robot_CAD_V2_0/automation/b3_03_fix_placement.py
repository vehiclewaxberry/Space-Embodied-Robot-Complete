"""B3-03 修正：把装配内全部组件位姿显式设为恒等（AddComponent5 会把包围盒中心
放到插入点，导致全局坐标零件偏移）。解除固定 → Transform2=I → 固定 → 重建保存。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from b3_lib.sw_core import (B3FailClosed, BuildLog, V2_ROOT, cast, connect,
                            get_com_member, open_document, rebuild_or_fail, save)

ASM_PATH = V2_ROOT / "01_Primary_Structure/SV2_Primary_Structure.SLDASM"
IDENT16 = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0,
           0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]


def set_identity_placement(sw, log, asm_model, asm_path):
    asm = cast(asm_model, "IAssemblyDoc")
    mu = cast(get_com_member(sw, "GetMathUtility"), "IMathUtility")
    xf = mu.CreateTransform(IDENT16)
    if xf is None:
        log.fail("CreateTransform 失败")
    comps = asm.GetComponents(True)
    asm_model.ClearSelection2(True)
    for c in comps or []:
        cast(c, "IComponent2").Select4(True, None, False)
    asm.UnfixComponent()
    asm_model.ClearSelection2(True)
    moved = []
    for c in comps or []:
        c2 = cast(c, "IComponent2")
        try:
            c2.Transform2 = xf
        except Exception:
            c2.SetTransformAndSolve2(xf)
        moved.append(c2.Name2)
        log.event("PLACEMENT_IDENTITY", component=c2.Name2)
    asm_model.ClearSelection2(True)
    for c in comps or []:
        cast(c, "IComponent2").Select4(True, None, False)
    asm.FixComponent()
    asm_model.ClearSelection2(True)
    rebuild_or_fail(asm_model, log, "identity_placement")
    return moved


def main():
    log = BuildLog("b3_03_fix_placement")
    sw = connect(log)
    sw.CloseAllDocuments(True)
    m = open_document(sw, log, ASM_PATH)
    moved = set_identity_placement(sw, log, m, ASM_PATH)
    save(m, log)
    sw.CloseAllDocuments(True)
    log.event("B3_03_FIX_DONE", components=len(moved))
    print("PLACEMENT_FIXED_OK")


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
