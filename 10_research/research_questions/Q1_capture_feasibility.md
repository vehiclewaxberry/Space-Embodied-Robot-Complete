# Q1：捕获可行域与绑定约束

## 研究问题

在**终端捕获初始状态已给定**、目标参数与任务阈值被冻结的条件下，目标质量/惯量、初始转速、抓取杠杆和捕获—镇定策略如何决定：

1. 捕获后状态是否落入当前 Gate 定义的可行区域；
2. 哪一个物理或资源约束首先成为绑定约束；
3. 不同策略的优劣为何不能脱离具体任务工况进行无条件排序。

## 当前裁决

`ACTIVE_VERIFIED_CORE_LIMITED_SCOPE`

这是 Paper 1 的核心问题。当前证据支持“冻结假设和既有 Gate 合同内”的回答，不支持普适任务最优性或飞行级安全声明。

## 范围

### 纳入

- 终端捕获阶段的质量、惯量、目标转速与抓取杠杆。
- 捕获冲量/动量交换后的角速度、轮控/推力器资源与任务阈值。
- `sim10` 的物理空间扫描与 `sim12` 的四工况×四策略比较。
- SAFE fail-closed 语义和负结果保留。

### 排除

- 从远距离轨道交会到终端接近的完整 Hill/CW 或高保真轨道传播。
- 柔性附件进入 `sim10/sim12` 的正式可行性判据；两者均标记 `UNKNOWN_NOT_IN_CRITERIA`。
- 感知误差闭环、VLA、自主装配、HIL、硬件或在轨验证。

## 当前证据

| 证据对象 | 原始裁决 | 可用范围 |
|---|---|---|
| `30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json` | `SIM10_GATES_PASS` | 9,002 个物理点评估；默认执行机构档的四类区域计数；冻结输入哈希一致 |
| `30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json` | `SIM12_PHASE1_GATES_PASS` | 16 个“工况×策略”单元；支持绑定 Gate 依赖工况，不支持无条件策略排名 |
| `30_simulation/safety_00_runtime_gate/results/safety_00_gate_check.json` | `PASS`, `next_stage_authorized=false` | fail-closed 安全合同通过；不能写成下一阶段已经获批 |
| `30_simulation/e15_core_coverage/results/core_gate_check.json` | `REPEAT_CORE_NO_SAFE_CANDIDATE` | 证明冻结 E1.5 核心覆盖没有安全候选，作为负结果边界 |

`sim10` 的 Gate 记录默认档区域计数为：`WHEELS_ONLY_FEASIBLE=6323`、`THRUSTER_REQUIRED_FEASIBLE=730`、`INFEASIBLE_RATE=1858`、`INFEASIBLE_RESOURCE=91`。这些是当前冻结扫描的机器结果，不应外推为真实任务总体概率。

## 工作命题与证伪条件

| 工作命题 | 当前状态 | 证伪/限制条件 |
|---|---|---|
| WP1-A：策略选择依赖当前绑定物理约束 | 已由 `sim12` Gate 允许表述 | 只能用于当前 4 个工况和 4 个策略；不能改写为任意工况普适规律 |
| WP1-B：冻结参数下可以构造可行域图 | 已由 `sim10` Gate 支撑 | 参数更改、柔性判据加入或执行机构实物定型后必须重算 |
| WP1-C：动量降低不必然等于任务更优 | `sim12` 允许用具体账本行说明 | 禁止写成“某策略总是更好/更差” |

## FINER 预审

| 维度 | 预审结论 |
|---|---|
| Feasible | 是；已有 Gate、结果和可复核配置 |
| Interesting | 与比赛主线和 Paper 1 直接相关 |
| Novel | `UNASSESSED`；未在本阶段执行系统先验检索，不能声称新颖性已成立 |
| Ethical | 不涉及新增人体/动物/敏感数据实验 |
| Relevant | 直接连接捕获可行性、资源约束和安全论证 |

## 文献知识锚点

- `wilde2018tutorial`、`yoshida2001zrm`：自由漂浮/GJM 与反作用接口。
- `yoshida2004impedance`、`uyama2012compliantwrist`：接触阻抗/接触时长的物理动机。
- `virgilillop2019simultaneous`、`virgilillop2019convexguidance`：捕获—消旋设计与可行性边界。
- `papadopoulos2021survey`、`ellery2019tutorial`：任务阶段与动量—接触背景。

上述内容只能按 `50_literature/references/notes/` 中已完成阅读卡引用；文献不能替代项目 Gate。

## Paper 1 可用表述

- 可写：在冻结参数和 Gate 合同内，策略可行性由当前工况的绑定约束决定。
- 可写：`sim10` 提供扫描层可行域，`sim12` 提供策略层绑定约束比较。
- 不可写：已证明某一策略普遍最优。
- 不可写：已证明柔性整星捕获安全。
- 不可写：已完成真实航天器或硬件验证。

## 解锁下一步所需证据

1. 明确新的研究变量与预注册扫描合同，而非修改旧 Gate。
2. 将 COTS 执行机构、柔性参数和接触时长从暂定值升级为可追溯实测/权威来源。
3. 若要讨论鲁棒可行域，需单独批准不确定性传播或敏感度研究。

## 来源

- `10_research/00_project_architecture/paper_structure_plan.md`
- `10_research/00_project_architecture/simulation_scenario_map.md`
- `30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json`
- `30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json`
- `30_simulation/safety_00_runtime_gate/results/safety_00_gate_check.json`
- `50_literature/references/manifest.yaml`
- `50_literature/references/notes/INDEX.md`

`last_verified_head: b75352c1c226c0f3e9a4bc9c469b766e06f41616`

