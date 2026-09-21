# 空间具身机器人研究总路线

_状态水印：2026-07-23_

> 阶段标识：`RESEARCH_OS_03_SPACE_EMBODIED_ROBOTICS_INITIALIZED`  
> 执行权限：`NO_NEW_EXECUTION_AUTHORITY`  
> 性质：战略与证据导航层，不是新的科学 SSOT，不替代 Gate JSON、冻结配置、Q1–Q6 合同或人工授权。

## 1. 总裁决

项目可以把长期研究主题提升为“物理约束自由漂浮空间机器人操作能力演化”，但当前已验证成果仍只位于非合作目标捕获的冻结合同内。竞赛、Paper 1 与长期路线必须三层分名：

| 层级 | 推荐名称 | 使用边界 |
|---|---|---|
| 当前竞赛题目 | **物理约束空间具身任务智能：面向非合作目标捕获的可行域、策略选择与安全证据链** | 只陈述 `sim_10 → sim_12 → SAFE → DT2 离线回放` 所支持的内容 |
| Paper 1 冻结工作题目 | **动量与稳定性约束下的非合作航天器捕获策略选择：可行域地图与绑定门判据** | 英文冻结题目为 *Strategy Selection under Momentum and Stability Constraints for Non-Cooperative Spacecraft Capture: Feasibility Maps and a Binding-Gate Criterion* |
| 长期研究总主题（候选） | **物理约束自由漂浮空间机器人操作：从非合作目标捕获到模块化在轨装配的能力演化** | 仅用于路线图、学位研究规划和后续立项，不暗示未知目标闭环、装配或 VLA 已实现 |
| Long-term umbrella candidate | **Physics-Grounded Free-Floating Space Robotic Manipulation: A Capability Path from Non-Cooperative Capture to Modular On-Orbit Assembly** | 与中文候选名称同边界 |
| 长期学位主题（第二候选） | **面向自由漂浮空间机器人的物理约束具身智能操作方法研究 / Physics-Grounded Embodied Intelligence for Free-Floating Space Robots** | 只作为长期研究主题；不替换当前竞赛/Paper 1 标题，也不构成 VLA 已实现声明 |

附件提出的 “Embodied Intelligent Free-Floating Robotic Manipulation for Future Space Infrastructure Servicing and Assembly” 可保留为远期愿景句，但不作为当前比赛或 Paper 1 标题。

## 2. 为什么选择能力演化路线

| 路线 | 当前判断 | 原因 |
|---|---|---|
| A. 只保留碎片清除叙事 | 不作为长期唯一总线 | 会压缩已有自由漂浮动力学、柔性、装配与安全架构的后续空间；但不能据此声称该方向“创新不足”，因为 Paper 1 新颖性仍未完成系统查新 |
| B. 直接转入大型结构装配 | 拒绝当前执行 | 接口、参数、目标侧柔性、授权和 AG0 科学接口资格化均未闭合；大型结构还需要序列图、累积误差和全局柔性模型 |
| C. 从捕获物理内核向两条证据支线扩展 | **选定** | 允许复用方程、账本、资源与 fail-closed 接口，同时对每个新任务重新建立合同和机器证据 |

路线 C 的核心不是“已有证据可以自然外推”，而是：**已有方法可以作为新合同的起点，任何新任务必须重新资格化。**

## 3. 两轴路线，而非单一成熟度阶梯

### 3.1 任务能力轴

```mermaid
flowchart LR
    K["冻结捕获物理内核<br/>当前 Paper 1"]
    K --> B["桥接支线 BRIDGE-UT<br/>带界不确定目标操作"]
    K --> A["装配支线 Q6-L1<br/>预制接口模块装配"]
    A --> L["Q6-L2<br/>大型模块化结构"]
    B -."方法可共享，非强制前置".-> A
```

- `BRIDGE-UT_BOUNDED_UNCERTAINTY_MANIPULATION` 是路线条目，不新增 Q，也不覆盖既有 Q6。
- Q6 保持为[预制接口模块在轨装配可行性](../research_questions/Q6_on_orbit_assembly.md)。
- 未知/非规则目标操作与预制接口装配共享动力学内核，但不是后者必须先完成的科学前置。
- 大型桁架、反射面和空间望远镜属于 `DEFERRED_Q6_L2`。

### 3.2 自主性轴

```mermaid
flowchart LR
    A0["A0 离线评价与证据回放"] --> A1["A1 确定性 FSM/规划"]
    A1 --> A2["A2 物理门控候选生成"]
    A2 --> A3["A3 VLA 增量消融"]
```

自主性轴与任务轴相互独立。VLA 不是装配完成后的自然必经阶段，也不拥有执行授权；它只有在确定性基线、适用域拒绝和 SAFE 接口闭合后，才可作为候选生成器接受增量价值评估。

## 4. 分阶段研究路线

### Stage 0：可信动力学与证据底座

| 项目 | 内容 |
|---|---|
| 目标 | 维护自由漂浮耦合、GJM、动量/能量/资源账本、接触广义力和 fail-closed 证据接口 |
| 已有资产 | `sim_05/06` 数值锚点；`sim_10/12` 可行域与策略单元；`sim_11` 有限接触带宽侧证据；SAFE 运行时核 |
| 当前状态 | `VERIFIED/LIMITED/FROZEN`，逐模块保留原始限定 |
| 禁止外推 | 不把通用多体方程相容写成跨任务验证相容；不把 SAFE 的 `PASS` 写成下游授权 |

### Stage 1：非合作旋转目标捕获（当前主线）

| 项目 | 内容 |
|---|---|
| 科学对象 | 冻结终端捕获初始状态、航天器/目标参数、执行器预算和阈值下的任务可行域与绑定约束 |
| 机器主链 | `sim_10 SIM10_GATES_PASS → sim_12 SIM12_PHASE1_GATES_PASS → SAFE PASS` |
| 侧证据 | `sim_11 SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS`；`sim_09` 仅 `LIMITED` |
| 当前产出 | Paper 1 与竞赛主叙事 |
| 仍缺 | 逐主张 Gate/hash 绑定；Paper 1 专项 prior-art；工程参数转正；FLEX 不在 `sim_10/12` 判据中 |
| 明确不代表 | 已完成碎片清除、消旋、离轨或在轨验证；9002 点网格占比不是成功概率 |

### Stage 2：带界不确定目标操作桥接线

| 项目 | 内容 |
|---|---|
| 路线标识 | `BRIDGE-UT_BOUNDED_UNCERTAINTY_MANIPULATION`，不是 Q6，也不是现有成果 |
| 科学对象 | 在明确边界内，把位姿、转速、几何、质量和惯量从冻结真值升级为带来源、带置信度的估计量 |
| 先建合同 | 感知—动力学状态包、不确定域、校准/OOD、候选动作模式、适用域拒绝和 false-ALLOW 指标 |
| 可复用方法 | 自由漂浮耦合、资源账本、可行域组织方式和 fail-closed 架构 |
| 不可复用结论 | `sim_10/12` 冻结可行域不能直接充当未知目标鲁棒可行域；`sim_09` 固定候选枚举不是开放物体抓取器 |
| 当前状态 | `PLANNED_NOT_CONTRACTED`；仓库中没有独立机器 Gate |

这里的“未知”必须解释为**带界、可估计的不确定性**。完全无先验、无可校准状态包的开放世界对象不进入近期研究合同。

### Stage 3A：Q6-L1 预制接口模块装配

| 项目 | 内容 |
|---|---|
| 科学对象 | 12U 服务星 + B601 + 1U/2U 模块 + 目标星预制接口；5D 接近 → 柔顺插入 → 6D 锁紧 |
| 可复用方法 | 自由漂浮耦合、资源账本、有限接触带宽方法、组合体更新思想、SAFE 语义 |
| 新增核心 | 公差、摩擦/楔紧、持续多状态接触、卡滞、接触历史、九判据、锁紧后的质量/惯量/拓扑更新 |
| 当前机器真值 | AG0 前检已经运行：授权前检、原始哈希绑定和 RF 分类均 `BLOCKED`；`AG0_SCIENTIFIC_INTERFACE_QUALIFICATION=NOT_RUN_UNAUTHORIZED`；raw verdict=`ASM00_AG0_BLOCKED_BY_INTERFACE`；`scientific_execution_authorized=false`；`next_stage_authorized=false` |
| 下一合法入口 | 先提供有效 HAG-A、原始哈希及所需接口输入/出处；获单独授权后由 AG0 科学接口资格化本身裁决 RF-1/2/3，并输出资格与下游授权结果 |
| 当前状态 | `PLANNED_SCOPE_FROZEN_EXECUTION_BLOCKED` |

### Stage 3B：Q6-L2 大型结构扩展

| 项目 | 内容 |
|---|---|
| 对象 | 桁架、反射面、空间望远镜或超大型模块化结构 |
| 新增科学问题 | 装配顺序图、累积位姿误差、时变全局刚度/模态、结构精度、物流与可能的多机器人协同 |
| 证据边界 | 即使未来单个 1U/2U 接口通过，也不能线性外推到大型结构 |
| 当前状态 | `DEFERRED_Q6_L2` |

### Stage 4：物理门控具身技能/VLA 候选决策

```text
任务状态/感知估计
        ↓
VLA 或其他高层模型：仅生成候选技能/动作意图
        ↓
确定性动力学评价器 + 适用域检查
        ↓
SAFE fail-closed + 人工/任务授权
        ↓
允许、修改或拒绝候选
```

当前状态为 `PLANNED_NOT_IMPLEMENTED`。不得直接输出关节力矩、推进器命令或安全授权；不得把文献中的通用 VLA 能力当作本项目验证结果。

## 5. 相对 24 个月里程碑（规划，不是承诺）

| 相对窗口 | 合法工作 | 出口条件 | 不自动授权的后续 |
|---|---|---|---|
| T0–T3 月 | 收口 Paper 1 证据绑定、状态冲突和专项查新 | C1–C4 逐主张来源闭合；明确可投稿范围 | 新参数扫描或超出冻结域的结论 |
| T2–T6 月 | 起草 BRIDGE-UT 问题/数据/不确定性合同；建立确定性 nominal baseline 计划 | 输入状态包、来源、校准、OOD、false-ALLOW 和拒绝语义冻结 | 训练 VLA、闭环执行 |
| T3–T9 月 | 补齐 Q6-L1 的接口输入/出处、HAG-A 与原始哈希；补装配核心阅读卡 | AG0 科学接口资格化具备可审查输入，但仍需单独授权 | 不得自动启动 AG0 科学资格化复核或 ASM-01/02 |
| T6–T12 月 | 仅在分别获批后执行 BRIDGE-UT 新版本 Gate，或开展 Q6 AG0 科学接口资格化/闭合复核 | 每条支线独立的机器裁决与负结果保留 | 另一支线的证据继承 |
| T12–T18 月 | 若 Q6 AG0 输出资格且明确授权下游，逐 Gate 研究持续接触、分阶段控制与组合体更新 | AG1–AG5 与九判据聚合评估按授权推进 | 大型结构外推 |
| T15–T24 月 | 若确定性基线、安全接口和数据条件均闭合，评估 VLA 候选生成的增量价值；或独立评估 Q6-L2 立项 | 预注册消融与明确效用/风险指标，或 Q6-L2 独立合同 | 将任一路线包装成已验证成果 |

窗口允许并行，但任何任务必须满足自己的授权门。因此它们不是强制串行工期。

## 6. 能力状态总览

| 能力 | 分类 | 证据解释 |
|---|---|---|
| 冻结合同内捕获可行域与策略选择 | `VERIFIED + FROZEN` | 由 `sim_10/sim_12` 支持，限冻结范围 |
| 有限接触带宽与柔性侧证据 | `LIMITED + FROZEN` | 参数 provisional，不能证明完整柔性安全域 |
| 柔性安全候选认证 | `NEGATIVE_RESULT + FROZEN` | e15 safe=0，ANCF 仍 `REPEAT_ANCF_CERTIFICATION` |
| 带界不确定目标操作 | `PLANNED` | 只有路线定义，没有独立合同或 Gate |
| Q6-L1 模块装配 | `BLOCKED` | 范围冻结，接口、授权与参数未闭合 |
| Q6-L2 大型结构 | `PLANNED/DEFERRED` | 仅先验与未来问题登记 |
| VLA 候选层 | `PLANNED_NOT_IMPLEMENTED` | 只有候选层架构，无实体、训练或执行权 |
| 实时数字孪生/HIL | `BLOCKED` | 当前最高只到受限 DT2 离线回放 |

## 7. 研究治理门

每次从“路线”进入“科学执行”，至少需要：

1. 独立、版本化、可证伪的问题合同；
2. 输入参数、数据和不确定性来源；
3. 冻结指标、负结果和 false-ALLOW 定义；
4. 原始文件及配置哈希绑定；
5. 人工授权与 `next_stage_authorized` 的显式裁决；
6. 不改写既有 Gate，不把旧 PASS 继承到新任务；
7. 新颖性结论在系统 prior-art 完成前保持 `UNASSESSED_PENDING_SYSTEMATIC_PRIOR_ART`。

## 8. 当前禁止声明

- 已完成空间碎片清除、消旋或离轨；
- 已实现未知目标闭环、在线质量/惯量辨识或 VLA；
- 已完成接口资格化、模块装配或大型结构搭建；
- 已完成实时 DT3/DT4、HIL、微重力或在轨验证；
- `sim_10/sim_12` 已包含 FLEX；
- SAFE 的 `PASS` 等于执行授权；
- 9002 点网格占比等于任务成功概率；
- 国内首创、世界首次或已证明新颖性。

## 9. 权威入口

- 当前状态：[知识库状态速查](../knowledge_base/project_context/README.md#history)
- 科学问题：[Q1–Q6 登记](../research_questions/README.md)
- Paper 1 理论链：[paper1_theory_chain.md](../theory_graph/paper1_theory_chain.md)
- 候选贡献：[claim_evidence_matrix.csv](../contribution_map/claim_evidence_matrix.csv)
- 仿真模块卡：[`30_simulation/module_cards/`](../../30_simulation/module_cards/)
- Q6 现行合同：[Q6_on_orbit_assembly.md](../research_questions/Q6_on_orbit_assembly.md)
- 文献控制器：[controller_state.yaml](../knowledge_base/papers/controller_state.yaml)
- 领域来源登记：[online_source_register.csv](../research_os_02/online_source_register.csv)
- Physics-Gated Agent 规划冻结：[physics_gated_agent_plan.md](./physics_gated_agent_plan.md)
- 研究、学习与文献队列：[research_learning_and_literature_queue.md](./research_learning_and_literature_queue.md)
- Agent 薄知识入口：[knowledge_base/physics_agent/README.md](../knowledge_base/physics_agent/README.md)

## 10. AI 辅助研究披露

本路线由 Codex 在读取本地 Gate 状态、研究问题合同、模块卡、文献 manifest/阅读卡和既有架构材料后综合生成，并经过动力学、具身/VLA、竞赛/论文三个只读 Agent 交叉审查。AI 仅用于整理、冲突检测和路线综合；科学状态仍以原始 Gate、冻结配置、来源文件和人工授权为准。
