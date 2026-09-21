---
title: C3 CA-A-R1 内部次结构构建记录
generated_at: 2026-08-27
status: DESIGN_RESEARCH_CANDIDATE
verdict: GATE_C3_CHECK_V2.json = PASS_WITH_DECLARED_OPEN_ITEM（open_items=0，deferred 登记 6 项）
---

# C3 构建记录（设计法庭 → CA-A-R1 → 实体模型）

## 流程留痕
1. 架构代理：三候选 + 设计依据（`55_c3_design_basis/`）。
2. 红队 RT1/RT2/RT3 对抗审查（`56_c3_redteam/`，工具事故后由主代理按完整报告落盘 + rt_verify.py 机器复核 8 项：5 CONFIRMED / 3 APPROXIMATE / 0 DISPUTED）。
3. 裁判终裁：CA-A 胜出，CA-B/CA-C 淘汰理由与收割项（`57_c3_decision/`）。
4. 构建：v1（163 违例）→ v2（keep-out 裁切 + 传感器开孔 + 支承板槽口 + 重分类）→ 角撑纳入开孔规则 → **0 违例**。

## 构建结果（CA_A_R1_INTERNAL_STRUCTURE_V2）
- 32 个构件：三舱底板+加强筋（R1-02/05）、PC/104 堆栈笼（端板内缩 ±52）、臂基座背板+4 角撑（R1-04，含 CAM-NAV/ILLUM/FT 开孔与臂包络 keep-out 裁切）、帆板根铰支架×2 t=10（R1-01）、电池板/轮支架（R1-03 派生尺寸）、转接块×8（R1-06，冻结壳体零开孔）。
- 结构质量 **1231.9 g**（CA-A 估算 1216.8 g 的 1.012 倍，预算 +60% 阈值内）；结构 CG [11.46, 8.23, -59.56] mm。
- 干涉：206 条全部归类（MOUNTING_CONTACT / VOLUME_OWNER_OVERLAP / ENVELOPE_OCCUPANCY / CONTACT_NOTE），**VIOLATION = 0**；冻结 STEP 哈希前后一致（零修改）。
- 工具链：FreeCAD 1.1.3 FreeCADCmd（`build_ca_a_r1_v2.py`，确定性参数化，可重跑）。

## 文件
- 模型：`CA_A_R1_INTERNAL_STRUCTURE_V2.FCStd` / `.step`（v1 同名文件为 lineage）
- 脚本：`build_ca_a_r1.py`（v1）、`build_ca_a_r1_v2.py`（现行）
- 报告：`BUILD_RECEIPT_V2.json`、`INTERFERENCE_REPORT_V2.json`、`MASS_CG_REPORT_V1.json`（v1 口径）、`GATE_C3_CHECK_V2.json`

## deferred 登记（出 C3 边界，禁删）
OI-3 收拢态 CG 核算；轮组缺口 30.4×（0.12 vs 0.3 N·m·s）；sim_10 锚点重锚；根铰支架穿壁路径 UNKNOWN；展开弹簧 ≥0.08 N·m 空间预留（机构迭代）；v1 163 违例历史（负结果保留）。

## 构建收尾补丁（2026-08-27 补记）
- **STEP 导出工具缺陷**：FreeCAD 1.1.3 headless 下 `Part.export(list, path)` 静默产出空文件（1640 B/0 实体），改用 `Import.export(doc.Objects, path)` 后正常（273 KB/6358 实体）；已加 `STEP_EXPORT_RECEIPT_V2.json` 回读校验：**32/32 solids, pass=true**。
- **D-01 角撑迁移**：`arm_base_gusset_-70_-70` 原位被臂包络 keep-out 整体吞没（净 0 mm³），迁至 y=-20（出 keep-out y≤-25.7 边界），双传力路径意图不变。
- 最终态：结构质量 **1244.9 g**（CA-A 估算 1.023 倍）、CG [12.85, 7.93, -59.67] mm、干涉 212 条 VIOLATION=0、冻结 STEP 哈希零改动。
