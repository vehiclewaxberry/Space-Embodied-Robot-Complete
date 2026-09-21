# Q4：具身智能决策接口

## 研究问题

未来的感知/规划/具身智能上层，如何在不绕过确定性动力学与 fail-closed 安全 Gate 的前提下，提出、筛选和执行非合作目标捕获动作？

## 当前裁决

`PLANNED_NOT_IMPLEMENTED`

本问题只定义未来接口和证据要求。本阶段不实现 VLA、不训练模型、不生成自主闭环性能结论，也不把已有 VLA 文献当作本项目的实验结果。

## 建议接口（规划态）

```text
感知估计（未来）
  -> 候选目标状态与不确定度
  -> 技能/策略候选生成（未来）
  -> 现有动力学可行性筛选
  -> SAFE fail-closed Gate
  -> 人工/任务授权
  -> 执行与证据记录（未来）
```

“建议接口”不是实现声明。任何学习系统都不得直接把语言/视觉输出写入执行器，也不得绕过现有 Gate 或人为授权。

## 当前已有资产

- 文献阅读卡：`spacemind2026`、`kawaharazuka2025vlareview`、`ma2024vlasurvey`、`kim2024openvla`、`rodriguez2024lmspacecraft`、`park2021speedplus`、`orsula2025srb`、`visualservoing2024survey`。
- 物理安全接口：`sim10`、`sim12` 和 `safety_00_runtime_gate` 的冻结结果。
- 当前缺失：感知数据集合同、技能库、训练/验证集、实时接口、HIL 和硬件执行证据。

## Paper 1 边界

- 可作为未来工作和系统架构接口出现。
- 不列为 Paper 1 已验证贡献。
- 不写“已实现具身智能捕获”或“VLA 提升了成功率”。

## 解锁条件

1. 另立任务并明确是否仅做离线策略建议、仿真闭环或硬件闭环。
2. 固定感知输入/输出模式、失败模式、数据来源和安全回退。
3. 将学习模块输出限制在“候选建议”，由确定性 Gate 负责最终准入。
4. 预注册对照组、成功/失败指标、域差和停止条件。

## 来源

- `10_research/00_project_architecture/system_architecture.md`
- `10_research/00_project_architecture/paper_structure_plan.md`
- `50_literature/references/notes/INDEX.md`
- `30_simulation/safety_00_runtime_gate/results/safety_00_gate_check.json`

`last_verified_head: b75352c1c226c0f3e9a4bc9c469b766e06f41616`

