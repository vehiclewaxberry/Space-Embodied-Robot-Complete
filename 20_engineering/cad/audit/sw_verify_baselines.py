"""MECH-INVENTORY-AUDIT-01 / 步骤 2：SolidWorks 现场打开+重建核验（只读）。

只读纪律：以只读方式打开，不保存、不修改、不修复。配置切换只在内存中进行，
读回后即关闭且**不保存**——因此不改变任何被审计文件的字节。

核验项（按任务书）：
1 直接打开  2 重建无错  3 无缺件  4 特征树可编辑（非纯导入哑实体）
5 配置切换后抑制状态  6 冷启动重开再次读回  7 导入实体无工程特征
8 外部引用断链
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

V22_AUTO = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad/Space_Embodied_Robot_CAD_V2_2/automation")
sys.path.insert(0, str(V22_AUTO))
from b3_lib.sw_core import (BuildLog, cast, connect, get_com_member,
                            open_document)

CAD = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad")
OUT = CAD / "audit"
NOW = datetime.now(timezone.utc).isoformat()

TARGETS = [
    ("V2_0_TOP", "Space_Embodied_Robot_CAD_V2_0/Assembly/Spacecraft_Service_Vehicle_V2_0.SLDASM"),
    ("V2_1_TOP", "Space_Embodied_Robot_CAD_V2_1/Assembly/Spacecraft_Service_Vehicle_V2_1.SLDASM"),
    ("V2_2_TOP", "Space_Embodied_Robot_CAD_V2_2/Assembly/Spacecraft_Service_Vehicle_V2_2.SLDASM"),
    ("V2_2_NATIVE_TOP", "Space_Embodied_Robot_CAD_V2_2_NATIVE/Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM"),
    ("NATIVE_ARM_STOW", "Space_Embodied_Robot_CAD_V2_2_NATIVE/04_ARM_STOW_SUPPORT/04_ARM_STOW_SUPPORT.SLDASM"),
    ("NATIVE_SOLAR_L", "Space_Embodied_Robot_CAD_V2_2_NATIVE/05_Solar_Array_Root_Left/05_Solar_Array_Root_Left.SLDASM"),
    ("NATIVE_SOLAR_R", "Space_Embodied_Robot_CAD_V2_2_NATIVE/06_Solar_Array_Root_Right/06_Solar_Array_Root_Right.SLDASM"),
    ("NATIVE_PRIMARY", "Space_Embodied_Robot_CAD_V2_2_NATIVE/01_Primary_Structure/01_Primary_Structure_V2_2.SLDASM"),
    ("NATIVE_MOUNT", "Space_Embodied_Robot_CAD_V2_2_NATIVE/02_B601_Mount_and_Load_Path/02_B601_Mount_and_Load_Path.SLDASM"),
]

FEATURE_NOISE = ("注解", "实体", "材质", "光源", "方程式", "曲面实体", "Tables",
                 "收藏", "历史记录", "选择集", "传感器", "设计活页夹", "标注",
                 "备注", "前视基准面", "上视基准面", "右视基准面", "原点",
                 "Annotations", "Solid Bodies", "Material", "Lights", "Equations",
                 "Design Binder", "Comments", "Front Plane", "Top Plane",
                 "Right Plane", "Origin", "Surface Bodies", "配合", "Mates")
IMPORT_MARKERS = ("输入", "Imported", "曲面-输入", "实体-输入", "Surface-Imported",
                  "Imported1", "输入1")


def feature_names(model):
    try:
        feats = cast(model, "IModelDoc2").FeatureManager.GetFeatures(True)
    except Exception:
        return []
    out = []
    for f in (feats or []):
        try:
            out.append(cast(f, "IFeature").Name)
        except Exception:
            pass
    return out


def audit_doc(sw, log, tag, rel):
    p = CAD / rel
    r = {"target": tag, "path": rel, "exists": p.exists()}
    if not p.exists():
        r["verdict"] = "MISSING"
        return r
    r["bytes"] = p.stat().st_size
    dtype = 2 if p.suffix.upper() == ".SLDASM" else 1
    # OpenDoc6 早绑定返回元组（byref 出参）——用库里已验证的封装
    try:
        m = open_document(sw, log, p, read_only=True)
    except Exception as e:
        r["verdict"] = "OPEN_FAILED"
        r["error"] = str(e)
        return r
    if m is None:
        r["verdict"] = "OPEN_FAILED"
        return r
    r["opened"] = True
    title = get_com_member(m, "GetTitle")
    try:
        rb = m.ForceRebuild3(False)
        r["rebuild_ok"] = bool(rb)
    except Exception as e:
        r["rebuild_ok"] = False
        r["rebuild_error"] = str(e)

    feats = feature_names(m)
    real = [f for f in feats if not any(f.startswith(n) or f == n
                                        for n in FEATURE_NOISE)]
    r["feature_total"] = len(feats)
    r["engineering_features"] = len(real)
    r["engineering_feature_sample"] = real[:8]
    r["has_import_feature"] = any(any(k in f for k in IMPORT_MARKERS)
                                   for f in feats)

    cm = cast(m, "IModelDoc2").ConfigurationManager
    try:
        names = list(m.GetConfigurationNames() or [])
    except Exception:
        names = []
    r["configuration_count"] = len(names)
    r["configurations"] = names[:12]
    r["active_configuration"] = cm.ActiveConfiguration.Name if names else None

    if dtype == 2:
        asm = cast(m, "IAssemblyDoc")
        comps = asm.GetComponents(True) or []
        missing, ext = [], []
        sup = {}
        for c in comps:
            c2 = cast(c, "IComponent2")
            cp = get_com_member(c2, "GetPathName")
            if cp and not Path(cp).exists():
                missing.append(Path(cp).name)
            if cp and CAD.as_posix().lower() not in Path(cp).as_posix().lower():
                ext.append(Path(cp).name)
            sup[Path(cp).stem if cp else "?"] = int(c2.GetSuppression2())
        r["component_count_top"] = len(comps)
        r["missing_components"] = missing
        r["external_refs_outside_cad_root"] = ext
        r["suppression_active_config"] = sup
        # 配置切换读回（内存中，不保存）
        matrix = {}
        for cn in names[:9]:
            try:
                m.ShowConfiguration2(cn)
                act = cast(m, "IModelDoc2").ConfigurationManager.ActiveConfiguration.Name
                row = {}
                for c in (asm.GetComponents(True) or []):
                    c2 = cast(c, "IComponent2")
                    cp = get_com_member(c2, "GetPathName")
                    row[Path(cp).stem if cp else "?"] = int(c2.GetSuppression2())
                matrix[cn] = {"activated": act, "suppression": row}
            except Exception as e:
                matrix[cn] = {"error": str(e)}
        r["config_suppression_matrix"] = matrix
        r["config_states_distinct"] = len({
            json.dumps(v.get("suppression", {}), sort_keys=True)
            for v in matrix.values() if "suppression" in v})
    # 关闭且不保存 —— 保持只读
    sw.CloseDoc(title)
    r["closed_without_save"] = True

    if r.get("engineering_features", 0) == 0 and r.get("has_import_feature"):
        r["classification"] = "IMPORTED_DUMB_SOLID"
    elif dtype == 2:
        r["classification"] = ("NATIVE_EDITABLE_SOLIDWORKS"
                                if not r.get("missing_components")
                                else "BROKEN_OR_INCOMPLETE")
    else:
        r["classification"] = ("NATIVE_EDITABLE_SOLIDWORKS"
                                if r.get("engineering_features", 0) > 0
                                else "ZERO_ENTITY_REFERENCE")
    r["verdict"] = "CHECKED"
    return r


def main():
    log = BuildLog("audit_sw_verify")
    sw = connect(log)
    res = []
    for tag, rel in TARGETS:
        try:
            r = audit_doc(sw, log, tag, rel)
        except Exception as e:
            r = {"target": tag, "path": rel, "verdict": "CHECK_ERROR",
                 "error": str(e)}
        res.append(r)
        print(f"{tag:20s} {r.get('verdict'):12s} "
              f"cfg={r.get('configuration_count')} "
              f"comp={r.get('component_count_top')} "
              f"missing={len(r.get('missing_components') or [])} "
              f"feat={r.get('engineering_features')} "
              f"cls={r.get('classification')}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sw_open_rebuild_check.json").write_text(
        json.dumps({"audit_id": "MECH_INVENTORY_AUDIT_01_SW_CHECK",
                     "generated_utc": NOW, "readonly": True,
                     "open_mode": "ReadOnly+Silent, CloseDoc without save",
                     "results": res}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    sw.CloseAllDocuments(True)


if __name__ == "__main__":
    main()
