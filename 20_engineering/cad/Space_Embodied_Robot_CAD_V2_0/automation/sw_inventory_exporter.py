"""B3-09 数字线程与机器证据导出。

遍历 V2 全部原生文件（COM 只读）+ 规格/校验 JSON，产出 16 项证据到
evidence/digital_thread/：装配树、对象/属性/特征/外部引用清单、frame 导出、
接口清单、结构分类、设备 volume 登记、维护矩阵、配置登记、干涉报告索引、
V1→V2 偏差、原生哈希、来源许可、claim 审计。
"""
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from b3_lib.sw_core import (B3FailClosed, BuildLog, V2_ROOT, cast, connect,
                            get_com_member, open_document,
                            read_custom_properties)

OUT = V2_ROOT / "evidence/digital_thread"
SPEC = yaml.safe_load((V2_ROOT / "automation/b3_build_spec.yaml").read_text(encoding="utf-8"))
TOP = V2_ROOT / "Assembly/Spacecraft_Service_Vehicle_V2_0.SLDASM"

PROHIBITED = ["STRENGTH_PASS", "STIFFNESS_PASS", "MODAL_PASS", "FLIGHT_QUALIFIED",
              "standard_12U_compliant", "global_collision_safe",
              "autonomous_capture_demonstrated", "deployment_verified"]


def sha256_of(p: Path):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def walk_features(model):
    feats = []
    f = cast(get_com_member(model, "FirstFeature"), "IFeature")
    while f is not None:
        feats.append({"name": f.Name, "type": get_com_member(f, "GetTypeName2")})
        f = cast(get_com_member(f, "GetNextFeature"), "IFeature")
    return feats


def component_tree(model):
    asm = cast(model, "IAssemblyDoc")
    def walk(comp):
        c2 = cast(comp, "IComponent2")
        kids = c2.GetChildren
        if callable(kids):
            kids = kids()
        return {"name": c2.Name2,
                "path": get_com_member(c2, "GetPathName"),
                "suppressed": bool(get_com_member(c2, "IsSuppressed")),
                "children": [walk(k) for k in kids or []]}
    root = get_com_member(get_com_member(model, "ConfigurationManager"),
                          "ActiveConfiguration")
    root_comp = get_com_member(root, "GetRootComponent3", True)
    return walk(root_comp)


def main():
    log = BuildLog("b3_09_digital_thread")
    OUT.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    natives = sorted(V2_ROOT.rglob("*.SLDPRT")) + sorted(V2_ROOT.rglob("*.SLDASM"))

    # 1) native_file_hash_manifest.csv（无 COM）
    with open(OUT / "native_file_hash_manifest.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["relative_path", "bytes", "sha256"])
        for p in natives:
            w.writerow([str(p.relative_to(V2_ROOT)).replace("\\", "/"),
                        p.stat().st_size, sha256_of(p)])
    log.event("HASH_MANIFEST", files=len(natives))

    sw = connect(log)
    sw.CloseAllDocuments(True)

    # 2) 逐文件属性/特征清单
    props_rows, feat_rows, obj_rows, struct_rows, claims = [], [], [], [], []
    for p in natives:
        m = open_document(sw, log, p, read_only=True)
        rel = str(p.relative_to(V2_ROOT)).replace("\\", "/")
        pr = read_custom_properties(m)
        for k, v in pr.items():
            props_rows.append([rel, k, v])
        for ft in walk_features(m):
            feat_rows.append([rel, ft["name"], ft["type"]])
        obj_rows.append([rel, pr.get("OBJECT_ID", ""), pr.get("SYSTEM_OWNER", ""),
                         pr.get("EVIDENCE_STATE", ""), pr.get("CLAIM_LIMIT", "")])
        struct_rows.append([rel, pr.get("OBJECT_ID", ""),
                            pr.get("STRUCTURE_CLASS", ""),
                            pr.get("MASS_OWNER", "")])
        blob = " ".join(str(v) for v in pr.values())
        hits = [t for t in PROHIBITED if t in blob]
        claims.append([rel, pr.get("CLAIM_LIMIT", ""), ";".join(hits),
                       "FAIL" if hits else "PASS"])
        sw.CloseAllDocuments(True)
    for name, rows, hdr in [
        ("custom_property_inventory.csv", props_rows, ["file", "property", "value"]),
        ("feature_inventory.csv", feat_rows, ["file", "feature", "type"]),
        ("object_inventory.csv", obj_rows,
         ["file", "object_id", "system_owner", "evidence_state", "claim_limit"]),
        ("structure_class_inventory.csv", struct_rows,
         ["file", "object_id", "structure_class", "mass_owner"]),
        ("claim_limit_audit.csv", claims,
         ["file", "claim_limit", "prohibited_hits", "verdict"]),
    ]:
        with open(OUT / name, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(hdr)
            w.writerows(rows)
    log.event("INVENTORIES_DONE", files=len(natives))
    bad = [c for c in claims if c[3] == "FAIL"]
    if bad:
        log.fail("claim 审计发现禁止声明", rows=bad)

    # 3) 装配树 + 外部引用（打开顶装）
    m = open_document(sw, log, TOP, read_only=True)
    tree = component_tree(m)
    (OUT / "assembly_tree.yaml").write_text(
        yaml.safe_dump({"generated_utc": now, "top": tree},
                       allow_unicode=True, sort_keys=False), encoding="utf-8")
    ext_rows = []
    for p in natives:
        deps = sw.GetDocumentDependencies2(str(p), True, True, False)
        if isinstance(deps, tuple):
            names = deps[1::2]
            for d in names:
                inside = str(d).startswith(str(V2_ROOT))
                ext_rows.append([str(p.relative_to(V2_ROOT)).replace("\\", "/"),
                                 d, "INTERNAL" if inside else "EXTERNAL_VIOLATION"])
    with open(OUT / "external_reference_inventory.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "dependency", "classification"])
        w.writerows(ext_rows)
    violations = [r for r in ext_rows if r[2] == "EXTERNAL_VIOLATION"]
    if violations:
        log.fail("发现 V2 外部引用越界", rows=violations[:5])
    sw.CloseAllDocuments(True)

    # 4) 规格派生登记（frame/接口/volume/维护/配置/干涉索引/偏差/来源）
    mc = json.loads((V2_ROOT / "evidence/b3_02/master_skeleton_machine_check.json")
                    .read_text(encoding="utf-8"))
    (OUT / "frame_export.yaml").write_text(yaml.safe_dump({
        "generated_utc": now,
        "coordinate_systems": mc["coordinate_systems"],
        "planes": mc["planes"],
        "transforms": SPEC["transforms"],
        "disabled": ["CS_B(T_SB)", "CS_TCP_CONTACT(T_E_TCP)", "CS_SENSOR(T_SC)"],
    }, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (OUT / "interface_inventory.yaml").write_text(yaml.safe_dump({
        "generated_utc": now, "interfaces": SPEC["interfaces"],
        "robot_mount_wrench_IF_RM_001": "fields_only_all_null_UNKNOWN_BLOCKED",
    }, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (OUT / "equipment_volume_register.yaml").write_text(yaml.safe_dump({
        "generated_utc": now, "bays": SPEC["bay_volume_owners"],
        "rule": "volumes_may_overlap=false; null_geometry_not_filled",
    }, allow_unicode=True, sort_keys=False), encoding="utf-8")
    with open(OUT / "serviceability_matrix.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["item", "direction_or_token", "state"])
        w.writerows([
            ["PNL_FRONT_MISSION_ACCESS", "+X_S", "DESIGN_PROPOSAL"],
            ["PNL_REAR_SERVICE_ACCESS", "-X_S", "DESIGN_PROPOSAL"],
            ["PNL_LEFT", "+Y_S", "DESIGN_PROPOSAL"],
            ["PNL_RIGHT", "-Y_S", "DESIGN_PROPOSAL"],
            ["PNL_TOP", "+Z_S", "DESIGN_PROPOSAL"],
            ["PNL_BOTTOM", "-Z_S", "DESIGN_PROPOSAL"],
            ["B601_install_removal", "+X_S", "DESIGN_PROPOSAL"],
            ["mid_bay_tray_extraction", "TBD_NO_SOURCE", "UNKNOWN_BLOCKED"],
            ["harness_corridor", "longitudinal_candidate", "DESIGN_PROPOSAL"],
            ["keepout_rail_tab/optical/plume/antenna/thermal", "owner_only",
             "UNKNOWN_BLOCKED"],
        ])
    (OUT / "configuration_register.yaml").write_text(yaml.safe_dump({
        "generated_utc": now,
        "configurations": {
            "STRUCTURAL_REVIEW": "外板+太阳翼抑制；主结构评审",
            "SERVICE_ACCESS_REVIEW": "全显示；维护可达评审",
            "DEPLOYED_REFERENCE_Q0": "几何参考态 q0；非部署验证",
            "STOWED_PROPOSAL": "太阳翼抑制表达；收拢几何 UNKNOWN；无飞行收拢声明",
            "SAFE_DISPLAY_PROPOSAL": "太阳翼抑制；安全展示提案",
            "EVIDENCE_STATE_REVIEW": "全显示；证据状态评审",
        },
        "independent_scene_note": "INDEPENDENT_SCENE 仅用于独立 target 场景文件"
                                  "（target 不入主装配）",
    }, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (OUT / "source_and_license_manifest.yaml").write_text(yaml.safe_dump({
        "generated_utc": now,
        "sources": {
            "parameter_contract": "20_engineering/design_inputs/v2_system_mechanical/"
                                  "07_cad_preparation/V2_master_skeleton_parameter_contract.yaml",
            "frame_export": "10_research/space_embodied_robotics/"
                            "comp_prot_03_a3_geometry_only/frame_export_v0_1.yaml",
            "solar_geometry": "20_engineering/config/geometry/flexible_appendage_v1.yaml",
            "b601_urdf_stl": "20_engineering/cad/spacecraft_layout/arm_b601_v1/ "
                             "(accepted, READ_ONLY, hash 11/11)",
            "b601_upstream": "80_third_party/notices/rebot_b601 "
                             "(upstream 71a1a6e662c3935c83d46e11c8d610d1e92b0486)",
            "vendor_step": "NOT_COPIED_NOT_IMPORTED (A3 禁令保持)",
            "oresat": "NOT_REFERENCED_IN_V2_NATIVE_FILES",
            "v1_cad": "READ_ONLY_PROBED_ONLY (bbox 探针), 未复制未引用",
        },
    }, allow_unicode=True, sort_keys=False), encoding="utf-8")
    with open(OUT / "v1_to_v2_deviation_manifest.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["deviation_id", "description", "rationale"])
        w.writerows([
            ["D-EQ-01", "方程管理器不可用（VBA 运行时缺失），参数权威由规格 YAML+PARAM_* 属性承担",
             "环境限制，非语义变更；见 build_logs/b3_02_master_skeleton.jsonl"],
            ["D-V2-01", "B601 由 V1 视觉壳改为 STL 轴对齐 bbox 代理（q0）",
             "A3 授权表达；V2 不引用 V1 活动零件；保守包络"],
            ["D-V2-02", "框环表达为 4 段梁条+纵梁角柱合围（角部切角避让）",
             "消除纵梁-框环体积重叠，多体单件表达"],
            ["D-V2-03", "9 项无来源 volume owner 为零实体锚点（非盒子）",
             "null_geometry_may_be_filled_without_source=false"],
        ])
    (OUT / "interference_report_index.yaml").write_text(yaml.safe_dump({
        "generated_utc": now,
        "reports": "见 evidence/b3_08/interference_*.json（按具名配置 scoped）",
        "inherited_negative_results": {
            "id": "DEPLOYED_REFERENCE_Q0_STATIC_INTERFERENCE",
            "count": 10, "classification": "NEGATIVE_RESULT",
            "global_collision_safety": "BLOCKED",
            "note": "V1 记录级继承；V2 bbox 代理表达差异不构成对该负结果的消解",
        },
    }, allow_unicode=True, sort_keys=False), encoding="utf-8")
    log.event("B3_09_DONE", outputs=16)
    print("DIGITAL_THREAD_EXPORT_OK")


if __name__ == "__main__":
    try:
        main()
    except B3FailClosed as e:
        print(f"FAIL_CLOSED: {e}")
        sys.exit(1)
