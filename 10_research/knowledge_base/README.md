# 本地研究 Agent 知识入口

> 状态：`NAVIGATION_ONLY`。本目录帮助 Codex、Claude 和项目成员快速定位现有证据，不是新的科学 SSOT，也不拥有 Gate 裁决权。

## 使用顺序

1. 先读 [`project_context/README.md#mission`](./project_context/README.md#mission) 理解任务和禁止外推边界。
2. 再读 [`project_context/README.md#history`](./project_context/README.md#history) 查看带时间水印的状态索引。
3. 需要理解“捕获—不确定目标操作—模块装配”的长期能力路线时，进入 [`../space_embodied_robotics/research_roadmap.md`](../space_embodied_robotics/research_roadmap.md)。
4. 需要启动空间具身智能研究总控时，先读 [`physics_agent/README.md`](./physics_agent/README.md)；它只做路由，不是第二份状态或工具实现。
5. 需要查看比赛 Prototype 时，先读 [`space_embodied_agent_v1_contract.md`](../space_embodied_robotics/space_embodied_agent_v1_contract.md)，再按 [`space_embodied_robotics/README.md`](../space_embodied_robotics/README.md) 的阶段表进入 A0/A1 至 A4-B2。A4-B1 已完成受限工程视觉 CAD；A4-B2 已建立 V2.0 系统机械架构合同，但 V2.0 CAD、URDF、仿真与实施仍未授权。
6. 需要规划 12U 服务航天器结构、舱段、机械臂 mount 或 SolidWorks 顶层模型时，进入 [`spacecraft_mechanical_design/README.md`](./spacecraft_mechanical_design/README.md)；它只做来源受控的设计迁移，不拥有 CAD、物理或飞行权威。
7. 领域概念与历史决策已并入 [project_context](./project_context/README.md#domain-methods)；仿真索引与文献分别进入 `simulation/`、`papers/`。
8. 任何数值、PASS、REPEAT、授权或哈希结论必须回到原始 Gate JSON、配置或 manifest 核对。

## 目录职责

| 路径 | 职责 | 不承担 |
|---|---|---|
| `project_context/` | 任务、状态沿革、研究问题、领域概念与历史 ADR | 新项目总状态 SSOT |
| `simulation/` | 仿真模块和 Gate 逻辑索引 | 仿真执行、结果重算或裁决覆盖 |
| `papers/` | manifest 的轻量派生索引与阅读卡入口 | 第二份题录库或 PDF 副本 |
| `physics_agent/` | 空间具身智能总控的领域路由、启动顺序和拒绝规则 | Physics Tool、模型、结果或平行 SSOT |
| `spacecraft_mechanical_design/` | 12U 服务航天器结构、案例迁移、robot mount、CAD 方法与未知量入口 | CAD 执行、物性、FEA、制造、飞行或科学 Gate |

## 真值优先级

发生冲突时按以下顺序处理：

1. 最终机器 Gate JSON、原始结果和绑定哈希；
2. 冻结配置、接口 SSOT 与授权记录；
3. [`10_research/framework_convergence/state_truth_report.md`](../framework_convergence/state_truth_report.md) 与证据矩阵；
4. [`50_literature/references/manifest.yaml`](../../50_literature/references/manifest.yaml)、阅读卡和本地 PDF 完整性；
5. 本地未跟踪资产，必须显式标记 `LOCAL_ONLY_UNTRACKED`；
6. 本知识入口、叙述性报告、PPT、视频和历史记忆。

项目总导航以 [`PROJECT_MAP.md`](../../PROJECT_MAP.md) 为准。[research_state_v4.md](../research_state_v4.md) 是机器合同引用的 7 月历史输入；合并任务知识见 [project_context/README.md](./project_context/README.md)。本页旧阶段计划不覆盖后来工程进展或当前用户授权。
