"""B3-08a 顶层装配 + 六具名配置。

Spacecraft_Service_Vehicle_V2_0.SLDASM（任务书冻结名）：
  Master_Skeleton + 01..07 模块 + 09 服务参考，恒等插入。
配置语义（b3_build_spec.yaml solar_interface.configuration_semantics + R4）：
  STRUCTURAL_REVIEW        外板抑制、翼展开显示
  SERVICE_ACCESS_REVIEW    全显示
  DEPLOYED_REFERENCE_Q0    全显示（几何参考态，非部署验证）
  STOWED_PROPOSAL          太阳翼模块抑制（收拢几何 UNKNOWN，不作飞行收拢声明）
  SAFE_DISPLAY_PROPOSAL    太阳翼模块抑制（安全展示提案）
  EVIDENCE_STATE_REVIEW    全显示
target 永不进入本装配（T_ST/T_SD EXCLUDED）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from b3_lib.sw_core import (B3FailClosed, BuildLog, V2_ROOT, activate_configuration,
                            cast, connect, get_com_member,
                            insert_components_identity, new_document,
                            rebuild_or_fail, save, save_as,
                            set_custom_properties, open_document)

ASM_DIR = V2_ROOT / "Assembly"
TOP = ASM_DIR / "Spacecraft_Service_Vehicle_V2_0.SLDASM"

COMPONENTS = [
    V2_ROOT / "00_Master_Skeleton/Master_Skeleton_V2_0.SLDPRT",
    V2_ROOT / "01_Primary_Structure/SV2_Primary_Structure.SLDASM",
    V2_ROOT / "02_Front_Mission_Module/SV2_Front_Mission_Module.SLDASM",
    V2_ROOT / "03_Avionics_EPS_ADCS_Bay/SV2_Avionics_EPS_ADCS_Bay.SLDASM",
    V2_ROOT / "04_Rear_Service_Module/SV2_Rear_Service_Module.SLDASM",
    V2_ROOT / "05_Robot_Mount_Module/SV2_Robot_Mount_Module.SLDASM",
    V2_ROOT / "06_B601_Visual_Arm/SV2_B601_Visual_Arm.SLDASM",
    V2_ROOT / "07_Solar_Array_Interface_Module/SV2_Solar_Array_Interface.SLDASM",
    V2_ROOT / "09_Service_Access_and_Harness_References/SV2_SERVICE_ACCESS_REFERENCES.SLDPRT",
]

CONFIGS = {
    "STRUCTURAL_REVIEW": {"suppress": ["PNL_", "SV2_Solar_Array_Interface"],
                          "comment": "主结构评审：外板与太阳翼抑制"},
    "SERVICE_ACCESS_REVIEW": {"suppress": [],
                              "comment": "维护可达评审：全部显示"},
    "DEPLOYED_REFERENCE_Q0": {"suppress": [],
                              "comment": "展开几何参考态 q0（非部署验证）"},
    "STOWED_PROPOSAL": {"suppress": ["SV2_Solar_Array_Interface"],
                        "comment": "收拢提案：翼几何 UNKNOWN 以抑制表达，无飞行收拢声明"},
    "SAFE_DISPLAY_PROPOSAL": {"suppress": ["SV2_Solar_Array_Interface"],
                              "comment": "安全展示提案：太阳翼抑制"},
    "EVIDENCE_STATE_REVIEW": {"suppress": [],
                              "comment": "证据状态评审：全部显示"},
}


def suppress_matching(asm_model, log, patterns):
    """按名称前缀抑制当前激活配置中的组件（含子装配内 PNL_ 零件逐级匹配顶层名）。"""
    asm = cast(asm_model, "IAssemblyDoc")
    n = 0
    for c in asm.GetComponents(False) or []:   # 顶层组件
        c2 = cast(c, "IComponent2")
        name = c2.Name2
        if any(p in name for p in patterns):
            c2.SetSuppression2(0)   # 0 = swComponentSuppressed
            n += 1
            log.event("COMPONENT_SUPPRESSED", component=name)
            continue
        # 子装配内命中（如 01 内 PNL_*、02/04 内 PNL_*）
        children = c2.GetChildren
        if callable(children):
            children = children()
        for ch in children or []:
            ch2 = cast(ch, "IComponent2")
            if any(p in ch2.Name2 for p in patterns):
                ch2.SetSuppression2(0)
                n += 1
                log.event("COMPONENT_SUPPRESSED", component=ch2.Name2)
    return n


def main():
    log = BuildLog("b3_08_top_assembly")
    ASM_DIR.mkdir(parents=True, exist_ok=True)
    missing = [str(p) for p in COMPONENTS if not p.exists()]
    if missing:
        log.fail("模块缺失，禁止建顶装", missing=missing)
    sw = connect(log)
    sw.CloseAllDocuments(True)
    if TOP.exists():
        # 顶装已存在（前次保存于配置阶段前）——续跑：打开补配置，不重建
        model = open_document(sw, log, TOP)
        log.event("TOP_RESUME_EXISTING")
    else:
        model = new_document(sw, log, "assembly")
        insert_components_identity(sw, log, model, COMPONENTS)
    set_custom_properties(model, log, {
        "OBJECT_ID": "V2-TOP-000",
        "SYSTEM_OWNER": "system_architecture",
        "PARENT_ID": "", "STRUCTURE_CLASS": "TOP_ASSEMBLY",
        "REPRESENTATION_LAYER": "SYSTEM_MECHANICAL_DISPLAY",
        "EVIDENCE_STATE": "DESIGN_PROPOSAL",
        "SOURCE_REFERENCE": "b3_build_spec.yaml (all module specs)",
        "FRAME_ID": "CS_S",
        "INTERFACE_IDS": "IF-RM-001;IF-RM-002;IF-SA-L;IF-SA-R;IF-PL-001;IF-EE-001",
        "MASS_OWNER": "NONE_CAD_ZERO_MASS_AUTHORITY",
        "NO_DYNAMICS_USE": "true", "MANUFACTURING_AUTHORITY": "NONE",
        "EXECUTION_AUTHORITY": "DISPLAY_ONLY",
        "CLAIM_LIMIT": ("system_mechanical_prototype_display;"
                        "profile_COMPETITION_DISPLAY_V0_NON_FLIGHT;"
                        "target_excluded_from_active_assembly;"
                        "T_SB_UNKNOWN_BLOCKED;physical_TCP_disabled"),
        "TARGET_IN_ACTIVE_ASSEMBLY": "false",
        "BLOCKED_CONSUMERS": "FEA;dynamics;URDF_roundtrip;manufacturing;"
                             "mass_properties;autonomous_capture_claims",
    })
    rebuild_or_fail(model, log, "top_assembly")
    if not TOP.exists():
        save_as(model, log, TOP)

    cfg_mgr = get_com_member(model, "ConfigurationManager")
    existing = model.GetConfigurationNames
    if callable(existing):
        existing = existing()
    existing = set(existing or ())
    for cname, cdef in CONFIGS.items():
        if cname not in existing:
            newc = cfg_mgr.AddConfiguration2(cname, cdef["comment"], "", 0, "",
                                             cdef["comment"], True)
            if newc is None:
                log.fail("AddConfiguration2 失败", config=cname)
        activate_configuration(model, log, cname)
        n = suppress_matching(model, log, cdef["suppress"]) if cdef["suppress"] else 0
        rebuild_or_fail(model, log, f"config_{cname}")
        log.event("CONFIG_CREATED", config=cname, suppressed=n)
    activate_configuration(model, log, "DEPLOYED_REFERENCE_Q0")
    save(model, log)
    sw.CloseAllDocuments(True)
    log.event("B3_08A_DONE", configs=len(CONFIGS))
    print("TOP_ASSEMBLY_BUILD_OK")


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
