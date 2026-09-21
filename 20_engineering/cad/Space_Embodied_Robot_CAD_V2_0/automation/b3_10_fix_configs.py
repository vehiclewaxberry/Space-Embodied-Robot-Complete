"""B3-10 整改 v2（评审 HIGH-1/2/3）：两层修复 + 可实现的配置语义。

层1：子装配文档自修复——早前 SetSuppression2 把子件抑制烧进各模块文件自身配置，
     逐个打开模块 SLDASM 全解析并保存。
层2：顶层六配置重建——太阳翼模块=顶层抑制（SetComponentSuppression，已验证配置隔离）；
     外板=按配置 Visible=False（display 语义；子件配置级抑制不可靠→D-V2-05 偏差）。
     每配置读回验证 fail-closed。
语义更新：STRUCTURAL_REVIEW 的"外板抑制"改述为"外板隐藏（仍参与干涉求解）"，
太阳翼在 STRUCTURAL/STOWED/SAFE 三配置抑制。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from b3_lib.sw_core import (B3FailClosed, BuildLog, V2_ROOT, activate_configuration,
                            cast, connect, get_com_member, open_document,
                            rebuild_or_fail, save)

TOP = V2_ROOT / "Assembly/Spacecraft_Service_Vehicle_V2_0.SLDASM"
MODULES = [
    V2_ROOT / "01_Primary_Structure/SV2_Primary_Structure.SLDASM",
    V2_ROOT / "02_Front_Mission_Module/SV2_Front_Mission_Module.SLDASM",
    V2_ROOT / "03_Avionics_EPS_ADCS_Bay/SV2_Avionics_EPS_ADCS_Bay.SLDASM",
    V2_ROOT / "04_Rear_Service_Module/SV2_Rear_Service_Module.SLDASM",
    V2_ROOT / "05_Robot_Mount_Module/SV2_Robot_Mount_Module.SLDASM",
    V2_ROOT / "06_B601_Visual_Arm/SV2_B601_Visual_Arm.SLDASM",
    V2_ROOT / "07_Solar_Array_Interface_Module/SV2_Solar_Array_Interface.SLDASM",
]
SOLAR = "SV2_Solar_Array_Interface"
SUPPRESS_SOLAR_IN = {"STRUCTURAL_REVIEW", "STOWED_PROPOSAL", "SAFE_DISPLAY_PROPOSAL"}
HIDE_PANELS_IN = {"STRUCTURAL_REVIEW"}
CONFIGS = ["STRUCTURAL_REVIEW", "SERVICE_ACCESS_REVIEW", "DEPLOYED_REFERENCE_Q0",
           "STOWED_PROPOSAL", "SAFE_DISPLAY_PROPOSAL", "EVIDENCE_STATE_REVIEW"]


def repair_module(sw, log, path):
    model = open_document(sw, log, path)
    asm = cast(model, "IAssemblyDoc")
    model.ClearSelection2(True)
    n = 0
    for c in asm.GetComponents(False) or []:
        c2 = cast(c, "IComponent2")
        if bool(get_com_member(c2, "IsSuppressed")):
            c2.Select4(True, None, False)
            n += 1
    if n:
        asm.SetComponentSuppression(2)   # swComponentFullyResolved
        model.ClearSelection2(True)
        rebuild_or_fail(model, log, f"repair_{path.stem}")
        save(model, log)
        log.event("MODULE_REPAIRED", module=path.name, resolved=n)
    else:
        log.event("MODULE_CLEAN", module=path.name)
    sw.CloseAllDocuments(True)


def walk(asm):
    out = []

    def rec(comp):
        c2 = cast(comp, "IComponent2")
        out.append(c2)
        kids = c2.GetChildren
        if callable(kids):
            kids = kids()
        for k in kids or []:
            rec(k)

    for c in asm.GetComponents(False) or []:
        rec(c)
    return out


def set_states(model, log, cname):
    asm = cast(model, "IAssemblyDoc")
    activate_configuration(model, log, cname)
    # 顶层全解析（IComponent2.SetSuppression2 经探针证实配置隔离；2=FullyResolved）
    for c in asm.GetComponents(True) or []:
        c2 = cast(c, "IComponent2")
        if bool(get_com_member(c2, "IsSuppressed")):
            c2.SetSuppression2(2)
    # 太阳翼按计划抑制（0=Suppressed）
    if cname in SUPPRESS_SOLAR_IN:
        for c in asm.GetComponents(True) or []:
            c2 = cast(c, "IComponent2")
            if SOLAR in c2.Name2:
                c2.SetSuppression2(0)
    # 外板可见性（display 语义）
    hide = cname in HIDE_PANELS_IN
    n_pnl = 0
    for c2 in walk(asm):
        if "PNL_" in c2.Name2 and not bool(get_com_member(c2, "IsSuppressed")):
            try:
                c2.Visible = not hide
                n_pnl += 1
            except Exception:
                log.event("PANEL_VISIBILITY_SET_FAILED", component=c2.Name2)
    rebuild_or_fail(model, log, f"states_{cname}")
    # 读回验证
    bad = []
    for c2 in walk(asm):
        nm = c2.Name2
        sup = bool(get_com_member(c2, "IsSuppressed"))
        if SOLAR in nm.split("/")[0]:
            want = cname in SUPPRESS_SOLAR_IN
            if sup != want:
                bad.append({"component": nm, "want_suppressed": want, "is": sup})
        elif sup and SOLAR not in nm:
            bad.append({"component": nm, "want_suppressed": False, "is": True})
    if bad:
        log.fail("配置状态验证失败", config=cname, mismatches=bad[:8])
    log.event("CONFIG_STATES_VERIFIED", config=cname, panels_touched=n_pnl,
              solar_suppressed=cname in SUPPRESS_SOLAR_IN)


def main():
    log = BuildLog("b3_10_fix_configs")
    sw = connect(log)
    sw.CloseAllDocuments(True)
    for p in MODULES:
        repair_module(sw, log, p)
    model = open_document(sw, log, TOP)
    for cname in CONFIGS:
        set_states(model, log, cname)
    activate_configuration(model, log, "DEPLOYED_REFERENCE_Q0")
    save(model, log)
    sw.CloseAllDocuments(True)
    log.event("B3_10_FIX_CONFIGS_DONE")
    print("CONFIG_STATES_FIXED_OK")


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
