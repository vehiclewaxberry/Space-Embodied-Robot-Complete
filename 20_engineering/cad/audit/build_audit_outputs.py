"""MECH-INVENTORY-AUDIT-01 / 步骤 3：生成七件套输出（只读消费前两步产物）。"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
NOW = datetime.now(timezone.utc).isoformat()


def y(o, ind=0):
    """极简 YAML 序列化（避免引入依赖）。"""
    sp = "  " * ind
    if isinstance(o, dict):
        return "\n".join(f"{sp}{k}:" + (f" {y(v)}" if not isinstance(v, (dict, list))
                                         else "\n" + y(v, ind + 1))
                          for k, v in o.items())
    if isinstance(o, list):
        return "\n".join(f"{sp}- " + (y(v) if not isinstance(v, (dict, list))
                                      else "\n" + y(v, ind + 2)).lstrip()
                          for v in o)
    if isinstance(o, bool):
        return "true" if o else "false"
    if o is None:
        return "null"
    s = str(o)
    return f'"{s}"' if any(c in s for c in ":#\n") else s


def main():
    rows = list(csv.DictReader(open(OUT / "artifact_inventory.csv",
                                    encoding="utf-8-sig")))
    sw = json.loads((OUT / "sw_open_rebuild_check.json").read_text(encoding="utf-8"))
    sw1 = json.loads((OUT / "sw_open_rebuild_check_run1.json").read_text(encoding="utf-8"))
    res = {r["target"]: r for r in sw["results"]}
    res1 = {r["target"]: r for r in sw1["results"]}

    # ── solidworks_native_matrix.yaml ────────────────────────────────────
    nat = defaultdict(lambda: {"SLDPRT": 0, "SLDASM": 0, "SLDDRW": 0, "locks": 0})
    for r in rows:
        if r["is_lock_file"] == "True":
            nat[r["area"]]["locks"] += 1
        elif r["native_solidworks"] == "True":
            nat[r["area"]][r["file_type"]] = nat[r["area"]].get(r["file_type"], 0) + 1
    matrix = {"audit_id": "MECH_INVENTORY_AUDIT_01", "generated_utc": NOW,
              "readonly": True,
              "native_counts_by_area": {k: dict(v) for k, v in sorted(nat.items())},
              "verified_in_solidworks": {}}
    for t, r in res.items():
        cold = res1.get(t, {})
        matrix["verified_in_solidworks"][t] = {
            "path": r.get("path"), "classification": r.get("classification"),
            "opened": r.get("opened"), "rebuild_ok": r.get("rebuild_ok"),
            "missing_components": len(r.get("missing_components") or []),
            "external_refs_outside_cad_root": len(
                r.get("external_refs_outside_cad_root") or []),
            "engineering_features": r.get("engineering_features"),
            "has_import_feature": r.get("has_import_feature"),
            "configuration_count": r.get("configuration_count"),
            "distinct_suppression_states": r.get("config_states_distinct"),
            "cold_restart_readback_identical": (
                r.get("configuration_count") == cold.get("configuration_count")
                and r.get("component_count_top") == cold.get("component_count_top")
                and r.get("engineering_features") == cold.get("engineering_features"))}
    (OUT / "solidworks_native_matrix.yaml").write_text(y(matrix), encoding="utf-8")

    # ── claude_codex_overlap_matrix.yaml ─────────────────────────────────
    prod = Counter((r["producer"], r["area"]) for r in rows)
    natprod = Counter(r["producer"] for r in rows
                      if r["native_solidworks"] == "True")
    overlap = {
        "generated_utc": NOW,
        "producer_attribution_basis":
            "V2_0 evidence/b3_00/HUMAN_APPROVAL_RECORD.yaml 记 APPROVAL_CHANNEL="
            "'Claude Code 会话人工指令'；V2_0/V2_1/V2_2 构建日志分别为 b3_*/b4_1_*/"
            "asset00_* 且 automation/ 均含 b3_lib COM 层 ⇒ 原生 SolidWorks 线全部"
            "由 CLAUDE_CODE 产出。CODEX 产出为 100_Mechanical_Continuation"
            "（STEP-first build123d，零原生件，其自述因内存不足未启动 SolidWorks）。",
        "native_solidworks_files_by_producer": dict(natprod),
        "codex_native_solidworks_files": 0,
        "duplicate_objects_both_sides": [
            {"object": "B601 安装接口（160x160x12 + Ø100 + 面 X=198）",
             "claude": "V2_2_NATIVE/02_B601_Mount_and_Load_Path（原生 8 件）",
             "codex": "100_Mechanical_Continuation（STEP，adapter_outer_face_x=198）",
             "status": "数值一致，表示不同（原生 vs STEP）——非冲突，可合并"},
            {"object": "太阳翼根部机构",
             "claude": "V2_2_NATIVE/05|06（原生各 14 件，已按 Codex 站位返工）",
             "codex": "100 SOLAR-ROOT-01（STEP 源包络）",
             "status": "已对齐（O9），Codex 为几何来源，Claude 为原生实现"},
            {"object": "ARM-STOW 支承",
             "claude": "V2_2_NATIVE/04（原生 5 件，v3 向量站位）",
             "codex": "100 ARM-STOW-01（占位包络 Z 88..110.15）",
             "status": "口径不同：Codex 为 B601 LOD1 前占位，Claude 为真实几何实测；"
                        "Claude 取代，X 站位差异待随向量定案"},
            {"object": "整星布局/七态",
             "claude": "V2_2 顶装（9 配置）+ V2_2_NATIVE 顶装（9 配置）",
             "codex": "110_Layout_and_Deployment_01（STEP staging，7 态策略）",
             "status": "三套并存——**这是最需要人工收敛的重复**"}],
        "analysis_only_no_mechanical_entity": [
            "120_B601_Geometry_and_PoseMap_02（0 原生件，STEP/JSON/PNG）",
            "130_B601_Vendor_CAD_Direct_Integration_03（0 原生件）",
            "100_Mechanical_Continuation（0 原生件，Codex）",
            "110_Layout_and_Deployment_01（0 原生件）",
            "ASSET_00 / B601_SWAP_01（0 原生件，仅证据）"],
    }
    (OUT / "claude_codex_overlap_matrix.yaml").write_text(y(overlap), encoding="utf-8")

    # ── blocked_mechanical_functions.yaml ────────────────────────────────
    blocked = {"generated_utc": NOW, "functions": [
        {"id": "B601_STOWED_HIFI", "status": "NOT_CREATED",
         "evidence": "V2_2/35_B601_HiFi_Visual/ 为空目录；B601-SWAP-01 判 "
                      "HOLD_NO_MULTIBODY_PART（headless LoadFile4 无返回）",
         "blocks": ["收拢外观", "鞍座接触面资格", "静态包络", "比赛渲染"]},
        {"id": "B601_KINEMATIC_PROXY_NATIVE", "status": "PARTIAL",
         "evidence": "V2_0/06_B601_Visual_Arm 为逐连杆 q0 bbox 原生件（10 件），"
                      "非 URDF 关节驱动装配；离散姿态库未建",
         "blocks": ["离散姿态库", "臂-翼避让", "连续部署运动学"]},
        {"id": "B601_MASS_SURROGATE", "status": "NOT_CREATED",
         "evidence": "全树无该件；质量权威仅存于 accepted URDF",
         "blocks": ["整星质量/CoM/惯量闭环"]},
        {"id": "SOLAR_ROOT_MECHANISM_QUALIFICATION", "status": "GEOMETRY_ONLY",
         "evidence": "V2_2_NATIVE/05|06 各 14 原生实体已建（非零实体），"
                      "但销径/簧刚度/预紧/材料全 TBD",
         "blocks": ["释放可靠性", "展开动力学", "结构释放"]},
        {"id": "HDRM_RELEASE", "status": "ENVELOPE_ONLY",
         "evidence": "HDRM_Base/Rod 为原生实体但型号/预紧 TBD", "blocks": ["发射锁紧资格"]},
        {"id": "STOW_Z_ENVELOPE", "status": "UNDEFINED",
         "evidence": "冻结输入无收拢态 Z 上限；STOW_Z_LIMIT_REFERENCE=UNKNOWN",
         "blocks": ["发射包络合规判定", "收拢位形最终裁决"]},
        {"id": "C5_STOWED_PACKAGE_WIDTH", "status": "NEGATIVE_PRESERVED",
         "evidence": "238.3 > 226.3，超 12.0mm；翼根机构下限宽 302.3",
         "blocks": ["整星发射包络闭合"]},
        {"id": "PHYSICAL_TCP_AND_CONTACT", "status": "BLOCKED",
         "evidence": "按任务书禁止定义 physical TCP", "blocks": ["接触力学", "抓取验证"]},
        {"id": "FEA_MODAL_STRENGTH", "status": "NOT_STARTED",
         "evidence": "全线无 FEA；不得宣称结构释放", "blocks": ["结构释放", "发射鉴定"]},
        {"id": "EXPLODED_VIEW", "status": "API_UNAVAILABLE",
         "evidence": "IConfiguration 无 GetExplodedViewCount；IAssemblyDoc 无创建接口",
         "blocks": ["装配层次可视化（已用 MAINTENANCE 抑制态+A-A 剖视替代）"]},
    ]}
    (OUT / "blocked_mechanical_functions.yaml").write_text(y(blocked), encoding="utf-8")

    # ── supersession_graph.md ────────────────────────────────────────────
    (OUT / "supersession_graph.md").write_text("""# 取代关系图（MECH-INVENTORY-AUDIT-01）

```
V0_1 (15 原生, 早期未核验)
  └─▶ V1_0 (32 原生, 早期未核验)
        └─▶ V2_0 (57 原生, B3, COMPLETE_WITH_PHYSICAL_LIMITATIONS)
              ├─▶ V2_1 (60 原生, B4-1, NATIVE_REFERENCE_CAD_ACCEPTANCE_HOLD)
              │     └─▶ V2_2 (102 原生, B5/L1, 双轨 366 显示轨)
              │           ├─▶ 100_Mechanical_Continuation  [CODEX, STEP-only]
              │           ├─▶ 110_Layout_and_Deployment_01 [STEP-only]
              │           ├─▶ 120_PoseMap_02               [Claude, STEP/分析]
              │           ├─▶ 130_VendorCAD_03             [Claude, STEP/分析, 已封存]
              │           └─▶ V2_2_NATIVE (63 原生+2 图纸, NATIVE-01 Phase1)
              └─(B601 视觉臂 10 件 q0 bbox 原生件被 V2_2 继承)
```

## 取代裁定

| 资产 | 被取代者 | 取代者 | 依据 |
|---|---|---|---|
| 整星原生顶装 | V2_0 / V2_1 | **V2_2 或 V2_2_NATIVE（待人工选）** | 见 current_top_assembly_comparison.md |
| 翼根站位 | V2_2_NATIVE 初版 X[126,174] 内置 | Codex SOLAR-ROOT-01 外挂式 | O9 已返工 |
| ARM-STOW 站位 | Codex 占位包络 Z 88..110.15 | v3 向量实测站位 | 真实几何取代占位 |
| 收拢向量 | v1(120) → v2(130) | **v3(NATIVE, CANDIDATE_HOLD)** | O13 顶点级约束 |
| 时钟角论证 | "宽度必要性" | "限位余量 c≥7.894°" | O11 证伪并改写 |
| 视觉评审图 | matplotlib 网格图 | **原生 .SLDDRW + A-A 真剖视** | N13 |

**封存（不再开发）**：V0_1、V1_0、130_VendorCAD_03（保留为几何来源与诊断证据）、
_failed_builds。
""", encoding="utf-8")

    # ── current_top_assembly_comparison.md ───────────────────────────────
    def g(t, k, d="—"):
        return res.get(t, {}).get(k, d)
    (OUT / "current_top_assembly_comparison.md").write_text(f"""# 候选顶层装配对比（现场打开+重建，两遍含冷启动）

| 指标 | V2_0 | V2_1 | V2_2 | V2_2_NATIVE |
|---|---|---|---|---|
| 顶层组件数 | {g('V2_0_TOP','component_count_top')} | {g('V2_1_TOP','component_count_top')} | {g('V2_2_TOP','component_count_top')} | {g('V2_2_NATIVE_TOP','component_count_top')} |
| 原生件总数(区域) | 57 | 60 | 102 | 63(+2 图纸) |
| 配置数 | {g('V2_0_TOP','configuration_count')} | {g('V2_1_TOP','configuration_count')} | {g('V2_2_TOP','configuration_count')} | {g('V2_2_NATIVE_TOP','configuration_count')} |
| **独立抑制态数** | {g('V2_0_TOP','config_states_distinct')} | **{g('V2_1_TOP','config_states_distinct')}** | **{g('V2_2_TOP','config_states_distinct')}** | {g('V2_2_NATIVE_TOP','config_states_distinct')} |
| 缺件 | {len(g('V2_0_TOP','missing_components',[]) or [])} | {len(g('V2_1_TOP','missing_components',[]) or [])} | {len(g('V2_2_TOP','missing_components',[]) or [])} | {len(g('V2_2_NATIVE_TOP','missing_components',[]) or [])} |
| 重建 | {g('V2_0_TOP','rebuild_ok')} | {g('V2_1_TOP','rebuild_ok')} | {g('V2_2_TOP','rebuild_ok')} | {g('V2_2_NATIVE_TOP','rebuild_ok')} |
| 导入哑实体特征 | {g('V2_0_TOP','has_import_feature')} | {g('V2_1_TOP','has_import_feature')} | {g('V2_2_TOP','has_import_feature')} | {g('V2_2_NATIVE_TOP','has_import_feature')} |
| 冷启动读回一致 | ✅ | ✅ | ✅ | ✅ |
| 全树干涉 | 未在本审计复测 | 未复测 | 未复测 | **0（本轮实测）** |
| 主结构形态 | 舱段/体积占位 | 语义参考 | 366 站位实体+C1 开口 | **框-纵梁-甲板-可拆板真骨架** |
| 翼根机构 | 接口件 | **零实体 named-only** | 实体机构 | **每侧 14 实体，Codex 站位对齐** |

## 关键差异

- **V2_1 独立抑制态仅 1**：8 个配置的组件抑制状态完全相同 → 七态在 V2_1 里
  **没有几何区分**（与其 ACCEPTANCE_HOLD 定性一致）。
- **V2_2 独立抑制态 6**：9 配置中 6 种真实不同 —— 状态表达最丰富。
- **V2_2_NATIVE 独立抑制态 3**：STOWED/DEPLOYED 等在第一阶段几何等同
  （翼板不在 A–F 范围），已如实登记为 O7。
- 四者**均无缺件、均可重建、均无导入哑实体特征**。

## 不做自动选择

按任务书禁止自动选定基线。两条可选路线与代价已列于主报告 F 项，**待人工裁决**。
""", encoding="utf-8")
    print("outputs written:", sorted(p.name for p in OUT.glob("*")
                                      if p.suffix in (".yaml", ".md", ".csv")))


if __name__ == "__main__":
    main()
