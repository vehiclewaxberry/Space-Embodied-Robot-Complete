# 空间具身智能研究总控 — 领域路由入口

> 状态：`NAVIGATION_ONLY`
> 权威等级：`authority_credit: NONE`
>
> 本文件**只做路由**。它不是第二份状态、不是 Physics Tool、不是模型或结果，
> 也不拥有任何 Gate 裁决权。任何数值、PASS/REPEAT/HOLD、授权或哈希结论，
> 必须回到下面指向的原始 Gate JSON、配置或 manifest 核对。
>
> 建立说明：本文件此前被 `A26_PHYSICS_GATED_AGENT`、
> [`knowledge_base/README.md`](../README.md)、
> [`research_roadmap.md`](../../space_embodied_robotics/research_roadmap.md)、
> `.codex/agents/space-embodied-intelligence-research-agent.md` 与 `CLAUDE.md`
> 共五处引用，但文件本身缺失（断链）。本次按上述文件**既有的**规格补齐路由内容，
> **未新增任何科学结论、状态或授权**。

---

## 1. 启动顺序

按序读取，不要跳步：

1. [`CLAUDE.md`](../../../CLAUDE.md) 与 [`PROJECT_MAP.md`](../../../PROJECT_MAP.md)
2. [`project_context/README.md#history`](../project_context/README.md#history) — 带时间水印的状态索引
3. **本文件**（领域路由）
4. [`physics_gated_agent_plan.md`](../../space_embodied_robotics/physics_gated_agent_plan.md) — 规划冻结件
5. 与任务相关的 Q1–Q6、原始 Gate / config / manifest

任务边界先看 [`project_context/README.md#mission`](../project_context/README.md#mission)。
涉及文献时再读 `.codex/skills/paper-knowledge-orchestrator/SKILL.md` 并运行其轻量
`validate`；**不得**维护第二份题录或论文状态。

---

## 2. 领域路由

| 需要做什么 | 去哪里 | 那里**不**承担什么 |
|---|---|---|
| 理解任务与禁止外推边界 | [`project_context/README.md#mission`](../project_context/README.md#mission) | 新科学结论 |
| 查当前状态 | [`project_context/README.md#history`](../project_context/README.md#history) | 新项目总状态 SSOT |
| 长期能力路线（捕获—不确定目标操作—模块装配） | [`research_roadmap.md`](../../space_embodied_robotics/research_roadmap.md) | 执行授权 |
| Physics-Gated Agent 规划 | [`physics_gated_agent_plan.md`](../../space_embodied_robotics/physics_gated_agent_plan.md) | 实现、Physics Tool、SAFE 扩展 |
| 比赛 Prototype 合同 | [`space_embodied_agent_v1_contract.md`](../../space_embodied_robotics/space_embodied_agent_v1_contract.md) | CAD 或飞行权威 |
| 运行时安全 Gate | [`safety_00_gate_check.json`](../../../30_simulation/safety_00_runtime_gate/results/safety_00_gate_check.json) | 执行授权 |
| 具身抓取后端 | [`SIM13_20_OF_20_GATE_V1.json`](../../../30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_20_OF_20_GATE_V1.json) | 硬件动作授权 |
| 在轨装配预检 | [`asm_00_gate_check.json`](../../../30_simulation/asm_00_interface_preflight/results/asm_00_gate_check.json) | 装配放行 |
| 12U 服务航天器机械 / CAD | [`spacecraft_mechanical_design/README.md`](../spacecraft_mechanical_design/README.md) | CAD 执行、物性、FEA、制造、飞行 |
| 已定架构决策与被拒路线 | [`project_context/README.md#decisions`](../project_context/README.md#decisions) | 新授权或阈值变更 |
| 证据矩阵与状态真值报告 | [`state_truth_report.md`](../../framework_convergence/state_truth_report.md) | 覆盖原始 Gate |

对应 Agent 定义：`.codex/agents/space-embodied-intelligence-research-agent.md`
（研究总控，`PLANNING_AND_EVIDENCE_ROUTING_ONLY`）与
`.codex/agents/physics-agent-architect.md`。

---

## 3. 真值优先级

冲突时按此顺序，序号小的赢：

1. 最终机器 Gate JSON、原始结果与绑定哈希
2. 冻结配置、接口 SSOT 与授权记录
3. [`state_truth_report.md`](../../framework_convergence/state_truth_report.md) 与证据矩阵
4. [`50_literature/references/manifest.yaml`](../../../50_literature/references/manifest.yaml)、阅读卡与本地 PDF 完整性
5. 派生规划文档
6. 对话记忆

**测试 PASS ≠ 科学 Gate PASS。**

---

## 4. 拒绝规则（硬边界）

研究总控**不得**：

- 运行或修改 `30_simulation/`、Gate、SAFE、CTRL、e15/e16、配置或结果
- 实现 VLA、Physics Tool、装配、数字孪生、HIL、RL 或控制器
- 直接输出关节/末端命令、力矩、轨迹、推进器命令或执行授权
- 把现有 Physics Tool 草案描述为已实现服务或 "Physics Foundation Model"
- 把 SAFE PASS、formal-safe 候选或文献结论写成执行授权
- 未经明确请求联网下载论文、安装平台、创建新数据或派生训练集
- 重编号 Q1–Q6，或让 `BRIDGE-UT` 与 Q6 相互继承 PASS

分线纪律：任务能力轴与自主性轴独立；**任何支线不得继承另一支线的机器裁决**。
项目**不采用** "Stage 0→5 必须串行继承 PASS" 的解释。

---

## 5. 引用本目录时的措辞约束

- 本文件是路由，引用它不构成任何证据。
- `PHYSICS_GATED_AGENT_PLANNING_COMPLETE_NO_IMPLEMENTATION` 是规划冻结裁决，
  执行权限为 `NO_NEW_EXECUTION_AUTHORITY` —— 不要写成"已实现"。
- 引用 `PROVISIONAL` / `PENDING_OWNER_REVIEW` / `EXTERNAL_INPUT_HOLD` 分类的
  权威时必须带限定词，只有 `CURRENT` 能当现行依据。
