"""B3-02 Master Skeleton 构建器。

消费 b3_build_spec.yaml（几何唯一驱动源），产出 00_Master_Skeleton/Master_Skeleton_V2_0.SLDPRT：
  - 全局方程（参数合同逐字入方程管理器）
  - 7 个具名参考面（舱段边界/任务面/安装面/太阳翼根）
  - 包络 3D 线框 + 端面/舱边界/安装接口具名参考草图
  - CS_S / CS_M / CS_A0 坐标系特征（CS_B/CS_TCP_CONTACT/CS_SENSOR 保持不存在=禁用）
  - 15 项治理自定义属性
  - 重开+重建自检，导出 published_geometry_register.yaml 与特征清单

禁止事项（UNKNOWN_BLOCKED 保持空）：材料、厚度、螺栓、质量、CS_B、physical TCP。
"""
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from b3_lib.sw_core import (B3FailClosed, BuildLog, V2_ROOT, add_global_equations,
                            close_document, connect, get_com_member, new_document,
                            open_document, rebuild_or_fail, rename_last_feature,
                            save_as, set_custom_properties, create_offset_plane,
                            read_custom_properties, _equation_mgr, eq_text, cast)

SPEC = yaml.safe_load((V2_ROOT / "automation/b3_build_spec.yaml").read_text(encoding="utf-8"))
OUT_PART = V2_ROOT / "00_Master_Skeleton/Master_Skeleton_V2_0.SLDPRT"
EVID = V2_ROOT / "evidence/b3_02"

RIGHT = ["右视基准面", "Right Plane"]   # 法向 +X
TOP = ["上视基准面", "Top Plane"]       # 法向 +Y
FRONT = ["前视基准面", "Front Plane"]   # 法向 +Z


def p(name):
    return float(SPEC["parameters"][name]["value"])


def mm(v):
    return v / 1000.0


def make_3d_wireframe_envelope(model, log):
    hx, hy, hz = mm(p("BODY_HALF_X_MM")), mm(p("BODY_HALF_Y_MM")), mm(p("BODY_HALF_Z_MM"))
    sk = model.SketchManager
    sk.Insert3DSketch(True)
    c = [(sx * hx, sy * hy, sz * hz) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    edges = [(0, 1), (2, 3), (4, 5), (6, 7),      # Z 向棱
             (0, 2), (1, 3), (4, 6), (5, 7),      # Y 向棱
             (0, 4), (1, 5), (2, 6), (3, 7)]      # X 向棱
    for a, b in edges:
        sk.CreateLine(*c[a], *c[b])
    sk.Insert3DSketch(True)
    rename_last_feature(model, log, "SK3D_BODY_ENVELOPE")


def make_face_rect_sketch(model, log, plane_feature_name, half_u_mm, half_v_mm, name):
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(plane_feature_name, "PLANE", 0, 0, 0, False, 0, None, 0):
        log.fail("选择参考面失败", plane=plane_feature_name)
    sk = model.SketchManager
    sk.InsertSketch(True)
    sk.CreateCenterRectangle(0, 0, 0, mm(half_u_mm), mm(half_v_mm), 0)
    sk.InsertSketch(True)
    rename_last_feature(model, log, name)


def make_mount_interface_sketch(model, log):
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2("PLANE_MOUNT_M", "PLANE", 0, 0, 0, False, 0, None, 0):
        log.fail("选择 PLANE_MOUNT_M 失败")
    sk = model.SketchManager
    sk.InsertSketch(True)
    sk.CreateCenterRectangle(0, 0, 0, mm(p("SERVICER_FLANGE_Y_MM") / 2),
                             mm(p("SERVICER_FLANGE_Z_MM") / 2), 0)
    sk.CreateCircleByRadius(0, 0, 0, mm(p("ADAPTER_BOSS_D_MM") / 2))
    sk.InsertSketch(True)
    rename_last_feature(model, log, "SK_MOUNT_INTERFACE_IF-RM-001")


def make_point_ref_sketch(model, log, plane_feature_name, name):
    model.ClearSelection2(True)
    if not model.Extension.SelectByID2(plane_feature_name, "PLANE", 0, 0, 0, False, 0, None, 0):
        log.fail("选择参考面失败", plane=plane_feature_name)
    sk = model.SketchManager
    sk.InsertSketch(True)
    pt = sk.CreatePoint(0, 0, 0)
    if pt is None:
        log.fail("CreatePoint 失败", sketch=name)
    sk.InsertSketch(True)
    rename_last_feature(model, log, name)


def make_coordinate_system(model, log, name, origin_m, x_dir, y_dir):
    """3D 草图 点+两轴线 → InsertCoordinateSystem（对象选择，免本地化名称）。"""
    sk = model.SketchManager
    sel = model.SelectionManager
    sk.Insert3DSketch(True)
    ox, oy, oz = origin_m
    L = 0.03
    pt = cast(sk.CreatePoint(ox, oy, oz), "ISketchPoint")
    lx = cast(sk.CreateLine(ox, oy, oz, ox + x_dir[0] * L, oy + x_dir[1] * L,
                            oz + x_dir[2] * L), "ISketchSegment")
    ly = cast(sk.CreateLine(ox, oy, oz, ox + y_dir[0] * L, oy + y_dir[1] * L,
                            oz + y_dir[2] * L), "ISketchSegment")
    sk.Insert3DSketch(True)
    sketch_feat = rename_last_feature(model, log, f"SK3D_{name}_REF")
    if pt is None or lx is None or ly is None:
        log.fail("坐标系参考几何创建失败", cs=name)
    model.ClearSelection2(True)
    sd = sel.CreateSelectData
    sd.Mark = 1
    if not pt.Select4(True, sd):
        log.fail("坐标系原点选择失败", cs=name)
    sd2 = sel.CreateSelectData
    sd2.Mark = 2
    if not lx.Select4(True, sd2):
        log.fail("坐标系 X 轴选择失败", cs=name)
    sd4 = sel.CreateSelectData
    sd4.Mark = 4
    if not ly.Select4(True, sd4):
        log.fail("坐标系 Y 轴选择失败", cs=name)
    feat = model.FeatureManager.InsertCoordinateSystem(False, False, False)
    if feat is None:
        rename_last_feature(model, log, name)
    else:
        feat.Name = name
        log.event("FEATURE_RENAME", name=name)
    model.ClearSelection2(True)
    return sketch_feat


def export_registers(model, log):
    EVID.mkdir(parents=True, exist_ok=True)
    feats = []
    f = cast(get_com_member(model, "FirstFeature"), "IFeature")
    while f is not None:
        feats.append({"name": f.Name, "type": get_com_member(f, "GetTypeName2")})
        f = cast(get_com_member(f, "GetNextFeature"), "IFeature")
    eq = _equation_mgr(model, log)
    equations = [eq_text(eq, i) for i in range(get_com_member(eq, "GetCount"))]
    props = read_custom_properties(model)
    inv = {"file": str(OUT_PART.relative_to(V2_ROOT)), "features": feats,
           "equations": equations, "custom_properties": props,
           "generated_utc": datetime.now(timezone.utc).isoformat()}
    (EVID / "master_skeleton_inventory.json").write_text(
        json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")

    reg = {
        "register_id": "V2_MASTER_SKELETON_PUBLISHED_GEOMETRY",
        "source_spec": "automation/b3_build_spec.yaml",
        "file": "00_Master_Skeleton/Master_Skeleton_V2_0.SLDPRT",
        "published_planes": {k: SPEC["reference_planes"][k]
                             for k in SPEC["reference_planes"]},
        "published_coordinate_systems": ["CS_S", "CS_M", "CS_A0"],
        "disabled_coordinate_systems": ["CS_B", "CS_TCP_CONTACT", "CS_SENSOR"],
        "published_sketches": [x["name"] for x in feats
                               if x["name"].startswith(("SK_", "SK3D_"))],
        "equations_global_variables": equations,
        "claim_limit": "reference_geometry_only_no_mass_no_material_no_dynamics",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    (V2_ROOT / "00_Master_Skeleton/published_geometry_register.yaml").write_text(
        yaml.safe_dump(reg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    log.event("REGISTER_EXPORTED", features=len(feats), equations=len(equations))


def main():
    log = BuildLog("b3_02_master_skeleton")
    if OUT_PART.exists():
        log.fail("Master_Skeleton_V2_0.SLDPRT 已存在——可重入规则禁止无条件覆盖，"
                 "如需重建请人工移除或授权覆盖")
    sw = connect(log)
    sw.CloseAllDocuments(True)   # 丢弃此前失败运行遗留的未保存文档
    model = new_document(sw, log, "part")

    add_global_equations(model, log, {k: v["value"] for k, v in
                                      SPEC["parameters"].items()
                                      if not isinstance(v["value"], list)})

    create_offset_plane(model, log, RIGHT, -170.25, "PLANE_REAR_BODY_FACE", flip=True)
    create_offset_plane(model, log, RIGHT, -56.75, "PLANE_REAR_MID_BOUNDARY", flip=True)
    create_offset_plane(model, log, RIGHT, 56.75, "PLANE_MID_FRONT_BOUNDARY")
    create_offset_plane(model, log, RIGHT, 170.25, "PLANE_TASK_FACE")
    create_offset_plane(model, log, RIGHT, 185.25, "PLANE_MOUNT_M")
    create_offset_plane(model, log, TOP, 113.15, "PLANE_SOLAR_ROOT_L")
    create_offset_plane(model, log, TOP, -113.15, "PLANE_SOLAR_ROOT_R", flip=True)

    make_3d_wireframe_envelope(model, log)
    hy, hz = p("BODY_HALF_Y_MM"), p("BODY_HALF_Z_MM")
    make_face_rect_sketch(model, log, "PLANE_REAR_BODY_FACE", hy, hz, "SK_REAR_BODY_FACE")
    make_face_rect_sketch(model, log, "PLANE_TASK_FACE", hy, hz, "SK_TASK_FACE")
    make_face_rect_sketch(model, log, "PLANE_REAR_MID_BOUNDARY", hy, hz,
                          "SK_BAY_BOUNDARY_REAR_MID")
    make_face_rect_sketch(model, log, "PLANE_MID_FRONT_BOUNDARY", hy, hz,
                          "SK_BAY_BOUNDARY_MID_FRONT")
    make_mount_interface_sketch(model, log)
    make_point_ref_sketch(model, log, "PLANE_SOLAR_ROOT_L", "SK_SOLAR_ROOT_L_IF-SA-L")
    make_point_ref_sketch(model, log, "PLANE_SOLAR_ROOT_R", "SK_SOLAR_ROOT_R_IF-SA-R")

    make_coordinate_system(model, log, "CS_S", (0, 0, 0), (1, 0, 0), (0, 1, 0))
    t = [v / 1000.0 for v in SPEC["transforms"]["T_SM"]["translation_mm"]]
    make_coordinate_system(model, log, "CS_M", tuple(t), (0, 0, -1), (0, 1, 0))
    make_coordinate_system(model, log, "CS_A0", tuple(t), (0, 0, -1), (0, 1, 0))

    set_custom_properties(model, log, {
        "OBJECT_ID": "V2-SKEL-000",
        "SYSTEM_OWNER": "system_architecture",
        "PARENT_ID": "Spacecraft_Service_Vehicle_V2_0",
        "STRUCTURE_CLASS": "REFERENCE",
        "REPRESENTATION_LAYER": "MASTER_SKELETON",
        "EVIDENCE_STATE": "EVIDENCE_BOUND",
        "SOURCE_REFERENCE": "automation/b3_build_spec.yaml <- V2_master_skeleton_parameter_contract.yaml + frame_export_v0_1.yaml",
        "FRAME_ID": "CS_S",
        "INTERFACE_IDS": "IF-RM-001;IF-RM-002;IF-SA-L;IF-SA-R",
        "MASS_OWNER": "NONE_REFERENCE_ONLY",
        "NO_DYNAMICS_USE": "true",
        "MANUFACTURING_AUTHORITY": "NONE",
        "EXECUTION_AUTHORITY": "DISPLAY_ONLY",
        "CLAIM_LIMIT": "geometry_reference_only_profile_COMPETITION_DISPLAY_V0",
        "BLOCKED_CONSUMERS": "FEA;dynamics;URDF_roundtrip;manufacturing;mass_properties",
    })

    rebuild_or_fail(model, log, "master_skeleton")
    save_as(model, log, OUT_PART)
    close_document(sw, model, log)

    model2 = open_document(sw, log, OUT_PART)
    rebuild_or_fail(model2, log, "master_skeleton_reopen")
    export_registers(model2, log)
    close_document(sw, model2, log)
    log.event("B3_02_DONE", part=str(OUT_PART))
    print("MASTER_SKELETON_BUILD_OK")


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
