"""B3-06b 太阳翼接口模块：根部零实体 owner ×2 + 展开参考翼板 ×2 → SLDASM。

翼板尺寸=几何 SSOT 冻结值（EVIDENCE_BOUND）；根部铰链 UNKNOWN_BLOCKED 零实体；
不声称收拢/锁定/释放/部署已验证。
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
from b3_lib.sw_part_factory import TOP, _m, build_x_extruded_part

SPEC = yaml.safe_load((V2_ROOT / "automation/b3_build_spec.yaml").read_text(encoding="utf-8"))
SOL = SPEC["solar_interface"]
MOD = V2_ROOT / "07_Solar_Array_Interface_Module"
PARTS_DIR = MOD / "parts"
ASM_PATH = MOD / "SV2_Solar_Array_Interface.SLDASM"


def props_base(oid, owner, evidence, claim, iface, frame):
    return {
        "OBJECT_ID": oid, "SYSTEM_OWNER": owner,
        "PARENT_ID": "SV2_Solar_Array_Interface",
        "STRUCTURE_CLASS": "DEPLOYABLE_REFERENCE",
        "REPRESENTATION_LAYER": "SYSTEM_MECHANICAL_DISPLAY",
        "EVIDENCE_STATE": evidence,
        "SOURCE_REFERENCE": "flexible_appendage_v1.yaml via b3_build_spec.yaml solar_interface",
        "FRAME_ID": frame, "INTERFACE_IDS": iface,
        "MASS_OWNER": "servicer_split_owner_NOT_from_CAD",
        "NO_DYNAMICS_USE": "true", "MANUFACTURING_AUTHORITY": "NONE",
        "EXECUTION_AUTHORITY": "DISPLAY_ONLY", "CLAIM_LIMIT": claim,
        "BLOCKED_CONSUMERS": "FEA;dynamics;mass_properties;deployment_claims",
    }


def build_root_ref(sw, log, name, origin_mm, iface, frame):
    out = PARTS_DIR / f"{name}.SLDPRT"
    if out.exists():
        log.event("PART_SKIP_EXISTS", part=out.name)
        return
    model = new_document(sw, log, "part")
    y = origin_mm[1]
    create_offset_plane(model, log, TOP, y, f"PLN_{name}", flip=y < 0)
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(f"PLN_{name}", "PLANE", 0, 0, 0,
                                       False, 0, None, 0):
        log.fail("选择根部面失败", part=name)
    sk = model.SketchManager
    sk.InsertSketch(True)
    sk.CreatePoint(0.0, 0.0, 0.0)
    sk.InsertSketch(True)
    rename_last_feature(model, log, f"SK_{name}_OWNER_POINT")
    props = props_base(name, "DEPLOYABLES_OWNER", "UNKNOWN_BLOCKED",
                       "hinge_release_latch_drive_UNKNOWN;zero_solid_owner;"
                       "geometry_NULL_unsourced", iface, frame)
    props["STRUCTURE_CLASS"] = "VOLUME_OWNER_REFERENCE"
    props["REPRESENTATION_LAYER"] = "OWNER_PLACEHOLDER_ZERO_SOLID"
    set_custom_properties(model, log, props)
    rebuild_or_fail(model, log, name)
    save_as(model, log, out)
    sw.CloseDoc(get_com_member(model, "GetTitle"))
    log.event("OWNER_REF_BUILT", vol=name)


def main():
    log = BuildLog("b3_06_solar")
    if ASM_PATH.exists():
        log.fail("SV2_Solar_Array_Interface.SLDASM 已存在，禁止无条件覆盖")
    PARTS_DIR.mkdir(parents=True, exist_ok=True)
    sw = connect(log)
    sw.CloseAllDocuments(True)

    for name, cfg in SOL["root_interfaces"].items():
        frame = "F_L" if name.endswith("L_IF") else "F_R"
        build_root_ref(sw, log, name, cfg["origin_mm"], cfg["interface"], frame)

    for name, w in SOL["wings"].items():
        y0, y1 = w["y_span_mm"]
        x0, x1 = w["x_span_mm"]
        z0, z1 = w["z_span_mm"]
        # 翼板沿 X 挤出：矩形 (yc,zc,hy,hz)
        build_x_extruded_part(
            sw, log, PARTS_DIR / f"{name}.SLDPRT", name,
            [((y0 + y1) / 2, (z0 + z1) / 2, (y1 - y0) / 2, (z1 - z0) / 2)],
            [x0, x1],
            props_base(name, "DEPLOYABLES_OWNER", "EVIDENCE_BOUND",
                       "deployed_reference_display_only;span_chord_thickness_frozen_SSOT;"
                       "no_deployment_or_latch_claim;flexible_params_placeholder",
                       "IF-SA-L" if "_L_" in name else "IF-SA-R", "CS_S"))

    asm_model = new_document(sw, log, "assembly")
    insert_components_identity(sw, log, asm_model,
                               sorted(PARTS_DIR.glob("*.SLDPRT")))
    set_custom_properties(asm_model, log, props_base(
        "V2-SOL-000", "DEPLOYABLES_OWNER", "DESIGN_PROPOSAL",
        "solar_interface_module_display;stowed_geometry_UNKNOWN",
        "IF-SA-L;IF-SA-R", "CS_S"))
    rebuild_or_fail(asm_model, log, "solar_asm")
    save_as(asm_model, log, ASM_PATH)
    sw.CloseAllDocuments(True)
    log.event("B3_06_SOLAR_DONE")
    print("SOLAR_MODULE_BUILD_OK")


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
