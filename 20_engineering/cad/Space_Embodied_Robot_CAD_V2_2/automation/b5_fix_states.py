"""V2.2 状态修复（V2.0 HIGH-1 教训复用）：
1. 四个翼表示件提升为顶层组件（顶层 SetSuppression2 = 配置隔离且可持久）；
2. 太阳翼模块装配内的翼组件删除（模块=纯机构件）；
3. B601 偏移 +12.75 重设（解固→Transform2→读回验证→固定）；
4. 八态重设 + 逐配置读回验证 + 保存。
"""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import b3_lib.sw_core as core
from b3_lib.sw_core import (B3FailClosed, BuildLog, IDENT16, activate_configuration,
                            byref_i4, cast, connect, get_com_member,
                            open_document, rebuild_or_fail, save)

V22 = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad/Space_Embodied_Robot_CAD_V2_2")
core.V2_ROOT = V22
core.LOG_DIR = V22 / "evidence" / "build_logs"
S = yaml.safe_load((V22 / "automation/b5_build_spec.yaml").read_text(encoding="utf-8"))
TOP = V22 / "Assembly/Spacecraft_Service_Vehicle_V2_2.SLDASM"
WINGS = [V22 / "50_Solar_Array_Left/parts/WING_L_DEPLOYED.SLDPRT",
         V22 / "50_Solar_Array_Left/parts/WING_L_STOWED.SLDPRT",
         V22 / "50_Solar_Array_Right/parts/WING_R_DEPLOYED.SLDPRT",
         V22 / "50_Solar_Array_Right/parts/WING_R_STOWED.SLDPRT"]
MODULES = [V22 / "50_Solar_Array_Left/SV22_Solar_Array_L.SLDASM",
           V22 / "50_Solar_Array_Right/SV22_Solar_Array_R.SLDASM"]
PLAN = {"STOWED": ("stowed", "stowed"), "DEPLOYED_NOMINAL": ("deployed", "deployed"),
        "DEPLOY_FAILED_BOTH": ("stowed", "stowed"), "L_FAIL": ("stowed", "deployed"),
        "R_FAIL": ("deployed", "stowed"), "PARTIAL": ("none", "none"),
        "SERVICE": ("deployed", "deployed"), "CAPTURE_SAFE": ("deployed", "deployed")}


def main():
    log = BuildLog("b5_fix_states")
    sw = connect(log)
    sw.CloseAllDocuments(True)

    # 1) 模块内翼组件删除
    for mod in MODULES:
        m = open_document(sw, log, mod)
        asm = cast(m, "IAssemblyDoc")
        m.ClearSelection2(True)
        n = 0
        for c in asm.GetComponents(True) or []:
            c2 = cast(c, "IComponent2")
            if "WING_" in c2.Name2:
                c2.Select4(True, None, False)
                n += 1
        if n:
            if not m.Extension.DeleteSelection2(0):
                log.fail("模块翼组件删除失败", module=mod.name)
            rebuild_or_fail(m, log, f"wингs_removed_{mod.stem}")
            save(m, log)
            log.event("MODULE_WINGS_REMOVED", module=mod.name, count=n)
        sw.CloseAllDocuments(True)

    # 2) 顶装：翼提升为顶层 + B601 偏移
    m = open_document(sw, log, TOP)
    asm = cast(m, "IAssemblyDoc")
    activate_configuration(m, log, "DEPLOYED_NOMINAL")
    mu = cast(get_com_member(sw, "GetMathUtility"), "IMathUtility")
    xf_i = mu.CreateTransform(IDENT16)
    existing_top = {cast(c, "IComponent2").Name2.rsplit("-", 1)[0]
                    for c in asm.GetComponents(True) or []}
    title = get_com_member(m, "GetTitle")
    for prt in WINGS:
        if prt.stem in existing_top:
            log.event("WING_ALREADY_TOP", part=prt.name)
            continue
        open_document(sw, log, prt, read_only=True)
        try:
            sw.ActivateDoc3(title, False, 0, 0)
        except TypeError:
            sw.ActivateDoc3(title, False, 0, byref_i4())
        c = asm.AddComponent5(str(prt), 0, "", False, "", 0.0, 0.0, 0.0)
        if c is None:
            log.fail("翼顶层插入失败", part=prt.name)
        c2 = cast(c, "IComponent2")
        try:
            c2.Transform2 = xf_i
        except Exception:
            c2.SetTransformAndSolve2(xf_i)
        m.ClearSelection2(True)
        c2.Select4(True, None, False)
        asm.FixComponent()
        m.ClearSelection2(True)
        log.event("WING_PROMOTED_TOP", part=prt.name)
        sw.CloseDoc(prt.name)

    # B601 偏移重设（解固→多法尝试→读回；不 fail-closed，结果如实记录后由专项脚本处理）
    data = list(IDENT16)
    data[9] = S["params"]["B601_OFFSET_X"] / 1000.0
    xf_b = mu.CreateTransform(data)
    for c in asm.GetComponents(True) or []:
        c2 = cast(c, "IComponent2")
        if "B601" not in c2.Name2:
            continue
        m.ClearSelection2(True)
        c2.Select4(True, None, False)
        asm.UnfixComponent()
        m.ClearSelection2(True)
        got = None
        for tag, fn in (("SetTransformAndSolve2",
                         lambda: c2.SetTransformAndSolve2(xf_b)),
                        ("Transform2", lambda: setattr(c2, "Transform2", xf_b))):
            try:
                fn()
            except Exception as e:
                log.event("B601_OFFSET_METHOD_EXC", method=tag, err=repr(e)[:80])
                continue
            m.EditRebuild3()
            got = list(get_com_member(get_com_member(c2, "Transform2"),
                                      "ArrayData"))[9] * 1000
            log.event("B601_OFFSET_ATTEMPT", method=tag, got_mm=round(got, 4))
            if abs(got - 12.75) < 1e-6:
                break
        m.ClearSelection2(True)
        c2.Select4(True, None, False)
        asm.FixComponent()
        m.ClearSelection2(True)
        log.event("B601_OFFSET_RESULT", x_mm=round(got or 0.0, 4),
                  ok=bool(got is not None and abs(got - 12.75) < 1e-6))
    rebuild_or_fail(m, log, "top_after_promotion")

    # 3) 八态重设（顶层翼件）+ 读回验证
    for cname, (lm, rm) in PLAN.items():
        activate_configuration(m, log, cname)
        for c in asm.GetComponents(True) or []:
            c2 = cast(c, "IComponent2")
            nm = c2.Name2
            for side, mode in (("L", lm), ("R", rm)):
                if f"WING_{side}_DEPLOYED" in nm:
                    c2.SetSuppression2(0 if mode in ("stowed", "none") else 2)
                elif f"WING_{side}_STOWED" in nm:
                    c2.SetSuppression2(0 if mode in ("deployed", "none") else 2)
        rebuild_or_fail(m, log, f"state_{cname}")
        got, want = {}, {}
        for c in asm.GetComponents(True) or []:
            c2 = cast(c, "IComponent2")
            nm = c2.Name2
            if "WING_" in nm:
                got[nm.rsplit("-", 1)[0]] = bool(get_com_member(c2, "IsSuppressed"))
        for side, mode in (("L", lm), ("R", rm)):
            want[f"WING_{side}_DEPLOYED"] = mode in ("stowed", "none")
            want[f"WING_{side}_STOWED"] = mode in ("deployed", "none")
        bad = {k: (got.get(k), v) for k, v in want.items() if got.get(k) != v}
        if bad:
            log.fail("状态读回失败", config=cname, bad=bad)
        log.event("STATE_VERIFIED", config=cname)
    activate_configuration(m, log, "DEPLOYED_NOMINAL")
    save(m, log)
    sw.CloseAllDocuments(True)
    log.event("B5_FIX_STATES_DONE")
    print("V22_STATES_FIXED_OK")


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
