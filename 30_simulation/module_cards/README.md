# 仿真模块知识卡：统一入口

内容合并：2026-09-06。原分散卡归入本页对应章节，模板仍单独保留。各节的裁决、数值、限制和 `last_verified_head` 沿用原卡；这里没有重算 Gate，也不把旧卡中的“当前”扩大为新工程状态。原文件字节、哈希及删除映射保存在统一 SQLite 的 snapshots / domain_actions。

本目录是对既有仿真资产的**只读认知索引**。知识卡不替代模块 README、配置、结果或 Gate JSON，也不修改任何科学结果。

## 状态表

| 模块 | 资产分类 | 原始机器裁决 | 科学用途 |
|---|---|---|---|
| [sim09](#sim_09) | `LIMITED` | Gate 无总体 verdict 字段 | 抓取候选预筛、失败模式和 Pareto 候选 |
| [sim10](#sim_10) | `VERIFIED` | `SIM10_GATES_PASS` | Paper 1 冻结可行域主证据 |
| [sim11](#sim_11) | `LIMITED` | `SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS` | 有限接触带宽与柔性侧证据 |
| [sim12](#sim_12) | `VERIFIED` | `SIM12_PHASE1_GATES_PASS` | Paper 1 策略—绑定 Gate 主证据 |
| [e15 core](#e15_core) | `NEGATIVE_RESULT` | `REPEAT_CORE_NO_SAFE_CANDIDATE` | 安全候选为零的冻结负结果 |
| [e15 ANCF](#e15_ancf) | `NEGATIVE_RESULT / BLOCKED` | `REPEAT_ANCF_CERTIFICATION` | 柔性最终认证阻塞 |
| [e16](#e16) | `LIMITED`，含负结果 | `PASS_WITH_GEOMETRY_AND_FLEX_LIMITATIONS` | 同步捕获扩展覆盖；正式安全候选为零 |
| [e19](#e19) | `DIAGNOSTIC / HOLD` | `E19_ISOLATED_NUMERIC_REPRODUCIBILITY_CLOSED__END_TO_END_PHYSICAL_CONTACT_ATTACHED_RECOVERY_AND_MISSION_RELEASE_HOLD` | B601 四任务分支的隔离数值执行；不形成端到端任务或物理接触权威 |
| [e20](#e20) | `DIAGNOSTIC / HOLD` | `E20_INDEPENDENT_SURROGATE_MASS_BRANCH_SIM11_COUPLED_ARM_ONLY_DIAGNOSTICS_CLOSED__E15_ANCF_PROVISIONAL_PANEL_CONTACT_ATTACHED_RECOVERY_CAD_MISSION_PRODUCTION_AND_FLIGHT_HOLD` | 旧 M4 质量分支的独立 surrogate 耦合敏感性；不替代当前 M7/R2 |
| [e21](#e21) | `DIAGNOSTIC / HOLD` | `E21_M7_R2_MIXED_ARM_PLACEMENT_DETECTED__CURRENT_R2_RIGID_WING_FREE_FLOATING_ARM_ONLY_TWO_PLACEMENT_SENSITIVITY_AND_FIXED_BASE_ROM_REPRODUCTION_CLOSED__SINGLE_PLACEMENT_R2_FULL_FLEX_COUPLING_E15_HARNESS_CONTACT_MISSION_PRODUCTION_AND_FLIGHT_HOLD` | 当前 R2 刚性翼双安装响应与固定基座 ROM；全柔性、接触和任务仍 HOLD |

## 使用规则

1. 原始裁决必须逐字保留。
2. `Gate PASS`、科学结果状态和 `next_stage_authorized` 分开记录。
3. `UNKNOWN_NOT_IN_CRITERIA` 不得改写成“柔性通过”或“柔性失败”。
4. 机器结果数字来自当前 Gate；卡片与 Gate 冲突时，以 Gate 为准。
5. 新模块可复制 [_template.md](_template.md)，但必须先生成独立 Gate 合同。

`last_verified_head: b75352c1c226c0f3e9a4bc9c469b766e06f41616`

---

<a id="sim_09"></a>

## sim09 抓取评估器知识卡

### 身份

- 模块路径：`30_simulation/sim_09_grasp_evaluator/`
- 资产分类：`LIMITED`
- 原始 Gate：`NO_GLOBAL_VERDICT_FIELD`
- Gate 文件：`30_simulation/sim_09_grasp_evaluator/results/e1_gate_check.json`
- Gate SHA-256：`67c43bfd7788c4012b4f6ca28de6fede70d74e71cb849cfbbb56d21636face47`

### 科学问题

在冻结候选集和硬约束下，哪些抓取工况通过逆运动学与冲量可接受性预筛，失败由什么原因触发，哪些候选进入 Pareto 集？

### 模型与范围

- 输入：目标/抓取候选、B601 几何与质量、硬约束和柔性评估接口。
- 模型：候选枚举、IK、冲量/约束筛选和柔性求解状态记录。
- 输出：候选状态、失败码、代表工况和 Pareto 前沿。
- 排除：全任务策略优选、最终柔性认证、正式安全域和总体 PASS。

### 机器证据

| 指标 | Gate 值 |
|---|---:|
| 总工况 | 72 |
| IK 可行 | 69 |
| admissible | 24 |
| Pareto 候选 | 16 |
| `IK_FAIL` | 3 |
| `IMPULSE_EXCEED` | 45 |
| `FLEX_SOLVER_FAIL` | 2 |
| `condition3_any_bucket_pass` | `true` |

柔性状态计数为：`OK=62`、`RETRY_OK_rtol1e-5=5`、`SKIPPED_INADMISSIBLE=3`、`FLEX_SOLVER_FAIL=2`。

### 可用于论文的表述

- 可写：在 72 个冻结候选中，69 个 IK 可行、24 个满足 admissible 条件、16 个进入 Pareto 前沿。
- 可写：主要失败码为冲量超限，另有 IK 和柔性求解失败。
- 禁止写：`sim09` 总体 Gate 已通过。
- 禁止写：24 个 admissible 候选均为任务安全候选。
- 禁止写：柔性求解状态等价于 ANCF 最终认证。

### 参数与假设

- 硬阈值仍受暂定/未验证参数影响。
- Gate JSON 没有 `verdict`/`overall` 字段，所以资产分类保持 `LIMITED`。
- 该模块的候选预筛不能替代后续任务资源、策略和安全 Gate。

### 上下游接口

- 上游：几何/质量/抓取点 SSOT 与 `sim06` 捕获冲量接口。
- 下游：`sim10` 任务可行域，以及 e15/e16 候选覆盖。
- Paper 1 角色：方法/候选生成支撑，不作为总体科学 PASS。

### 解锁条件

只有新增明确的全局科学 verdict 合同、阈值来源升级并完成独立复核后，才可讨论升级 `VERIFIED`。

### 来源

- `30_simulation/sim_09_grasp_evaluator/results/e1_gate_check.json`
- `20_engineering/config/grasp_evaluator/hard_constraints_v1.yaml`
- `20_engineering/config/geometry/arm_b601_v1.yaml`

`last_verified_head: b75352c1c226c0f3e9a4bc9c469b766e06f41616`

---

<a id="sim_10"></a>

## sim10 任务可行域知识卡

### 身份

- 模块路径：`30_simulation/sim_10_mission_feasibility/`
- 资产分类：`VERIFIED`（仅限冻结合同）
- 原始 Gate：`SIM10_GATES_PASS`
- Gate 文件：`30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json`
- Gate SHA-256：`367078aa79853591b8da276f047c8c4fdbc4017e5136680fe90ad3432cc14265`
- 柔性状态：`UNKNOWN_NOT_IN_CRITERIA`

### 科学问题

在冻结目标、杠杆、转速、质量比和执行机构档位的扫描空间内，捕获后状态落入哪一种任务可行性区域，边界由速率还是资源约束控制？

### 模型与范围

- 输入：`20_engineering/config/mission_feasibility/scan_v0.yaml` 及其冻结依赖。
- 模型：捕获后组合体动量/惯量、姿态速率和执行机构资源账本。
- 输出：物理点分类、边界和与 sim06/sim08 的锚点交叉检查。
- 排除：柔性 Gate、硬件实测能力、概率成功率和完整轨道交会。

### 机器证据

| 指标 | Gate 值 |
|---|---:|
| 物理点 | 9,002 |
| `WHEELS_ONLY_FEASIBLE` | 6,323 |
| `THRUSTER_REQUIRED_FEASIBLE` | 730 |
| `INFEASIBLE_RATE` | 1,858 |
| `INFEASIBLE_RESOURCE` | 91 |
| 最大线动量残差 | `2.0937e-16` |
| 最大角动量残差 | `6.0298e-16` |

Gate X1–X4 与冻结哈希 Gate 均通过。X2 同时如实记录设计预期“边界随杠杆参数单调”在过渡质量比窄带内被精确求解器证伪；Gate 只判定该浅坑低于当前图网格的标签分辨率，并未删除负结果。

### 可用于论文的表述

- 可写：冻结扫描合同下形成四类任务可行区域。
- 可写：区域边界由捕获后速率和执行机构资源共同决定。
- 可写：过渡窄带存在已记录的浅非单调行为，且未改变当前离散区域标签。
- 禁止写：区域计数是真实任务发生概率。
- 禁止写：所有参数均来自 COTS 实物。
- 禁止写：已得到柔性航天器捕获可行域。

### 参数与假设

- 执行机构档为 sim08 placeholder CLASS 值。
- `t_detumble_max=3600 s` 为暂定任务假设。
- G3 致密球类没有 CAD 锚点。
- 杠杆参数定义与设计书符号存在已记录口径差异。

### 上下游接口

- 上游：sim06 捕获冲量锚点、sim08 执行机构预算、e15 阈值登记。
- 下游：sim12 策略比较、Paper 1 可行域图和 SAFE 合同。
- Paper 1 角色：主证据 C1/C2。

### 解锁条件

若目标模型、执行机构、柔性判据或阈值发生变化，必须新建扫描合同并重跑；不得覆盖本 Gate。

### 来源

- `30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json`
- `20_engineering/config/mission_feasibility/scan_v0.yaml`
- `30_simulation/sim_06_capture_impulse/results/capture_impulse_matrix_v0.csv`
- `30_simulation/sim_08_detumble_actuator_budget/results/actuator_budget_sweep.csv`

`last_verified_head: b75352c1c226c0f3e9a4bc9c469b766e06f41616`

---

<a id="sim_11"></a>

## sim11 刚柔耦合与有限接触带宽知识卡

### 身份

- 模块路径：`30_simulation/sim_11_coupled_dynamics/`
- 资产分类：`LIMITED`
- 原始 Gate：`SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS`
- Gate 文件：`30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json`
- Gate SHA-256：`287aa84824ced51fb4480dfc3d39e9dafc8ee41b37c9de0f73e2d927263fec10`
- `PROVISIONAL_PARAMS=true`

### 科学问题

自由漂浮树形多体、B601 6R 机械臂和有限模态帆板在机械臂扫掠及旋转目标捕获中，是否满足守恒/能量/退化/收敛/交叉求解合同；有限接触带宽是否能形成可审计的柔性侧证据？

### 模型与范围

- 模型：浮动基座树形多体 + FFR 帆板（默认每侧 3 模态）+ B601 6R + 有限接触窗。
- 场景 A1：机械臂扫掠；场景 A2：150 kg、3 deg/s 目标捕获。
- 主积分器：Radau；交叉求解：BDF。
- 排除：真实帆板/夹爪参数认证、最终安全候选 ANCF 认证和 Paper 1 柔性分类 Gate。

### 机器证据

| Gate | 结果 | 核心含义 |
|---|---|---|
| G1 动量 | PASS | 约简/全量/接触窗动量残差满足合同 |
| G2 能量审计 | PASS | 无阻尼与含耗散口径满足阈值 |
| G3a | PASS | FFR 与 sim07 ANCF 帆板组件级退化对比；非整星逐点等价 |
| G3b | PASS | 刚性帆板退化与 sim05 对照 |
| G3c | PASS | 全刚化组合体与 sim01 式刚体传播对照；非 24 kg 工件逐点同构 |
| G4 收敛 | PASS | 20 ms 名义接触窗下 m3→m4→m5 前向加密满足 1% 合同 |
| G5 交叉求解 | PASS | Radau/BDF 合同内一致 |

`next_stage_authorized=true` 是该 Gate 文件的原始字段；它不消除暂定参数，也不自动授权本任务实施新仿真。

### 可用于论文的表述

- 可写：在当前暂定模型合同内，有限接触带宽的耦合模型通过 G1–G5。
- 可写：理想冲量的柔性能量指标存在模型域边界，有限接触窗提供了当前主判据。
- 可写：退化对比的适用范围是帆板组件或同一全刚化组合体，不能扩大为所有整星状态逐点等价。
- 禁止写：真实航天器柔性参数已经认证。
- 禁止写：20 ms 是 B601 实测接触时长。
- 禁止写：sim11 已把柔性加入 sim10/sim12 正式安全域。

### 参数与假设

Gate 明确列出的暂定字段：`n_modes`、`mode_shape`、`stiffness_case`、`zeta_modal`、`contact_T_c`。名义接触时长为 20 ms，等待 B601 夹爪实测。

### 上下游接口

- 上游：几何/质量 SSOT、sim05、sim07、sim01 退化锚点。
- 下游：Q2 柔性边界、Paper 1 方法/限制；不得直接提升 e15 认证状态。
- Paper 1 角色：C3 有限接触带宽的 `LIMITED` 侧证据。

### 解锁条件

升级为高置信柔性证据需要实测/FEA 参数、接触时间证据和新的预注册 Gate；最终候选仍需 e15 ANCF 交叉认证。

### 来源

- `30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json`
- `20_engineering/config/coupled_scene/coupled_model_v0.yaml`
- `20_engineering/config/coupled_scene/scene_A2_capture.yaml`
- `20_engineering/config/geometry/flexible_appendage_v1.yaml`

`last_verified_head: b75352c1c226c0f3e9a4bc9c469b766e06f41616`

---

<a id="sim_12"></a>

## sim12 策略可行性知识卡

### 身份

- 模块路径：`30_simulation/sim_12_strategy_feasibility/`
- 资产分类：`VERIFIED`（Phase 1 合同内）
- 原始 Gate：`SIM12_PHASE1_GATES_PASS`
- Gate 文件：`30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json`
- Gate SHA-256：`a416c13481119bbdc61764d518a1abebc159a78bbd78fac132803069713dacd8`
- 柔性状态：`UNKNOWN_NOT_IN_CRITERIA`

### 科学问题

在 4 个冻结任务工况和 4 种策略中，策略输出是否满足守恒，是否表现出工况相关差异，以及允许的论文命题是否严格受绑定 Gate 约束？

### 模型与范围

- 输入：sim10/历史锚点、策略配置与冻结资源阈值。
- 规模：4 个任务工况×4 种策略，共 16 个单元。
- 输出：动量/资源账本、各工况可接受策略和 claim audit。
- 排除：无条件全局排名、柔性判据、硬件执行效果。

### 机器证据

| Gate | 结果 | 记录 |
|---|---|---|
| GS1 conservation | PASS | `max_eps_H=3.8498e-16`；S2 向量闭合最大值 `2.2204e-16` |
| GS2 differentiation | PASS | A_low→S1；B_anchor→ABORT；C_transition→S3a；D_extreme→ABORT |
| GS3 claim audit | PASS | 允许绑定 Gate 命题；明确禁止无条件策略排名和柔性结论 |

### 可用于论文的表述

- 可写：策略选择依赖当前活动的物理约束/绑定 Gate。
- 可写：在 B_anchor 工况，Gate 允许引用 S2 与 S1 的具体冲量—角动量账本差异。
- 可写：debris@3 deg/s 在四种当前策略中复现不可行结果。
- 禁止写：动量整形总能改善捕获。
- 禁止写：任意策略的无条件排名。
- 禁止写：柔性 Gate 结论。
- 禁止写：只用“轮容量翻倍”而脱离其余账本。

### 参数与假设

- Phase 1 只覆盖冻结 16 个单元。
- 柔性明确不在判据中。
- ABORT 是当前合同的正确输出之一，不应被改写成数据缺失。

### 上下游接口

- 上游：sim10 可行域、sim06/sim08 账本和策略配置。
- 下游：Paper 1 贡献 C1/C2、SAFE fail-closed 叙事。
- Paper 1 角色：策略—绑定 Gate 主证据。

### 解锁条件

扩充任务/策略空间、加入柔性或硬件约束时，必须单独冻结新配置和 Gate，不能覆盖 Phase 1 证据。

### 来源

- `30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json`
- `20_engineering/config/strategy_feasibility/strategies_v0.yaml`
- `10_research/sim_12/momentum_ledger.md`

`last_verified_head: b75352c1c226c0f3e9a4bc9c469b766e06f41616`

---

<a id="e15_core"></a>

## e15 core 覆盖与安全候选知识卡

### 身份

- 模块路径：`30_simulation/e15_core_coverage/`
- 资产分类：`NEGATIVE_RESULT`
- 覆盖 Gate：`P0_A_CORE_COVERAGE_PASS`
- 科学裁决：`REPEAT_CORE_NO_SAFE_CANDIDATE`
- Gate 文件：`30_simulation/e15_core_coverage/results/core_gate_check.json`
- Gate SHA-256：`761798e52ead35f8bf6200034af088e85f7bb9085c71d0883bf1e70c1cffe3a7`
- `next_stage_authorized=false`

### 科学问题

冻结 E1.5 的 72 个候选是否被完整、无静默缺失地分类；在当前阈值下是否存在可送入最终柔性认证的安全候选？

### 模型与范围

- 覆盖层：72 行候选必须全部获得明确状态和唯一主绑定约束。
- 核心数值层：仅对几何有效行进行核心安全判定。
- 排除：对几何无效行运行 ANCF、放宽阈值或用诊断锚点代替最终候选。

### 机器证据

| 指标 | Gate 值 |
|---|---:|
| 总行数/唯一 case | 72/72 |
| `GEOMETRY_INVALID` | 66 |
| `CORE_UNSAFE` | 6 |
| 安全候选 | 0 |
| 证据缺失 | 0 |
| ANCF 执行 | `false` |
| 阈值登记状态 | `PROVISIONAL` |

主绑定约束为 `IK_UNREACHABLE=66` 和 `POST_CAPTURE_RATE_EXCEEDS_LIMIT=6`。

### 可用于论文的表述

- 可写：覆盖 Gate 通过，72 行均被明确分类且无证据缺失。
- 可写：在当前冻结阈值下安全候选为 0，科学裁决为 `REPEAT_CORE_NO_SAFE_CANDIDATE`。
- 可写：负结果被保留并阻止了不合格候选进入 ANCF 最终认证。
- 禁止写：E1.5 总体通过。
- 禁止写：覆盖 PASS 等于科学 PASS。
- 禁止写：没有 ANCF 结果等于柔性响应为零。

### 参数与假设

- 阈值登记整体状态为 `PROVISIONAL`，且 `thresholds_widened=false`。
- 66 个几何无效行显式标记为不适用核心数值，而非静默丢弃。

### 上下游接口

- 上游：sim09 候选、硬约束和阈值登记。
- 下游：e15 ANCF；因安全候选为 0，最终候选认证不可用。
- Paper 1 角色：fail-closed 与负结果证据 C4。

### 解锁条件

不能通过放宽现有阈值解锁。需要新的、预注册且物理有据的候选生成/设计变更任务，并保留本负结果。

### 来源

- `30_simulation/e15_core_coverage/results/core_gate_check.json`
- `30_simulation/e15_core_coverage/config/threshold_registry_core_v1.yaml`

`last_verified_head: b75352c1c226c0f3e9a4bc9c469b766e06f41616`

---

<a id="e15_ancf"></a>

## e15 ANCF 认证知识卡

### 身份

- 模块路径：`30_simulation/e15_ancf_certification/`
- 资产分类：`NEGATIVE_RESULT / BLOCKED`
- 原始 Gate：`REPEAT_ANCF_CERTIFICATION`
- Gate 文件：`30_simulation/e15_ancf_certification/results/gate_summary.json`
- Gate SHA-256：`aab4d609e219279c2563c8a38743ac1784bbf16de399d5b8798439b0ac2dca80`

### 科学问题

ANCF 柔性求解是否在离散化、低振幅诊断和最终安全候选交叉求解层面满足认证合同？

### 模型与范围

- 检查：网格/时间步/脉冲趋势、历史状态分类、低振幅诊断和最终候选交叉求解。
- 关键规则：诊断锚点不能冒充最终安全候选。
- 排除：在没有核心安全候选时生成虚构最终候选，或把低振幅 PASS 当成整体认证。

### 机器证据

| 子项 | 结果 |
|---|---|
| 离散化趋势 Gate | PASS |
| 低振幅诊断 | 8/8 完成，Gate PASS |
| 历史分类 | 7/7 已分类，无 silent zero |
| 历史交叉求解诊断 | 6 个比较；最大相对差 `0.056373494...`，未全部低于 5% |
| 最终候选交叉求解 | `available=false`，Gate FAIL |
| 总体 | `REPEAT_ANCF_CERTIFICATION` |

5.637% 是**历史诊断**最大相对差，而非最终候选结果；最终候选不存在，因为冻结 E1.5 的安全候选为 0。

### 可用于论文的表述

- 可写：离散化和低振幅诊断完成，但整体认证仍为 REPEAT。
- 可写：fail-closed 规则阻止诊断锚点冒充最终候选。
- 禁止写：ANCF 已通过 5% 交叉求解认证。
- 禁止写：低振幅 Gate PASS 等于真实捕获候选 PASS。
- 禁止写：5.637% 是当前最终候选误差。

### 参数与假设

- 最终候选 Gate 限为 5%。
- 低振幅诊断 Gate 限为 10%，其用途不同，不能混用。
- 文献 `gerstmayr2013ancfreview` 本地 PDF 仍缺；文献缺口不改变机器 REPEAT。

### 上下游接口

- 上游：e15 core 安全候选。
- 下游：柔性安全域认证；当前阻塞。
- Paper 1 角色：限制与负结果，不是正式贡献结论。

### 解锁条件

需要合法的核心安全最终候选，并按冻结/新预注册的交叉求解合同完成候选级认证；不得用低振幅诊断替代。

### 来源

- `30_simulation/e15_ancf_certification/results/gate_summary.json`
- `30_simulation/e15_ancf_certification/config/certification_v1.yaml`
- `30_simulation/e15_core_coverage/results/core_gate_check.json`
- `50_literature/references/manifest.yaml`

`last_verified_head: b75352c1c226c0f3e9a4bc9c469b766e06f41616`

---

<a id="e16"></a>

## e16 同步捕获知识卡

### 身份

- 模块路径：`30_simulation/e16_sync_capture/`
- 资产分类：`LIMITED`（包含“无正式安全候选”的负结果）
- 原始 Gate：`PASS_WITH_GEOMETRY_AND_FLEX_LIMITATIONS`
- Gate 文件：`30_simulation/e16_sync_capture/results/gate_check.json`
- Gate SHA-256：`5538b054805781f7717d316bfc81c9f79cbc6b3b4d6cc9fdc72905d80984cc6f`

### 科学问题

在同步因子扩展的 216 个候选中，几何预筛、动力学评估、阈值政策、确定性和候选排序是否完整闭合；是否存在满足核心与柔性正式条件的安全候选？

### 模型与范围

- 输入：冻结几何/质量/冲量接口、同步因子和继承阈值。
- 规模：216 个终端候选。
- 输出：上游拒绝/动力学评估分类、绑定约束、排序和确定性检查。
- 排除：未经验证的新终端状态柔性结论；ANCF 未运行。

### 机器证据

| 指标 | Gate 值 |
|---|---:|
| 终端候选 | 216 |
| 上游拒绝 | 198 |
| 动力学评估 | 18 |
| `GEOMETRY_INVALID` | 198 |
| `CORE_UNSAFE` | 18 |
| `CORE_SAFE_RIGID_FLEX_UNKNOWN` | 0 |
| 正式安全候选 | 0 |
| Top-20 请求/交付 | 20/18 |

Top-20 少 2 个的原始原因是 `ONLY_18_LINE_A_GEOMETRY_VALID_DYNAMIC_CASES`，不是输出丢失。阈值政策为 `FROZEN_NO_WIDENING`，柔性政策为所有新同步终端状态 `UNKNOWN` 且 `safe_claim_when_unknown=false`。

### 可用于论文的表述

- 可写：216 行全部闭合，198 行被几何/IK 上游拒绝，18 行完成动力学评估。
- 可写：阈值未放宽，18 个动力学行均因捕获后速率超限而为 `CORE_UNSAFE`。
- 可写：总体 Gate 通过的是覆盖、政策和确定性合同；正式安全候选仍为 0。
- 禁止写：e16 已找到同步捕获安全策略。
- 禁止写：总体 PASS 表示柔性通过。
- 禁止写：Top-20 缺 2 行是数据缺失。

### 参数与假设

- 目标为 150 kg、3 deg/s 当前模型工况。
- 阈值继承且多项为 `PROVISIONAL_INHERITED_WITHOUT_RELAXATION`。
- `run_ancf=false`；所有新同步状态柔性为 `UNKNOWN`。

### 上下游接口

- 上游：sim09/e15 几何证据、B601 URDF、质量预算、共同冲量/刚体工具。
- 下游：同步捕获后续设计；当前不能进入正式安全执行。
- Paper 1 角色：扩展边界/负结果，可放讨论或补充材料。

### 解锁条件

需要新的几何有效候选、核心安全候选和对应候选级柔性验证；任何新设计必须保持本 216 行结果可追溯。

### 来源

- `30_simulation/e16_sync_capture/results/gate_check.json`
- `30_simulation/e16_sync_capture/config/experiment_v1.yaml`
- `30_simulation/e15_core_coverage/config/threshold_registry_core_v1.yaml`

`last_verified_head: b75352c1c226c0f3e9a4bc9c469b766e06f41616`

---

<a id="e19"></a>

## e19：B601 任务分支隔离诊断执行

### 资产分类

`DIAGNOSTIC / HOLD`

### 原始机器裁决

`E19_ISOLATED_NUMERIC_REPRODUCIBILITY_CLOSED__END_TO_END_PHYSICAL_CONTACT_ATTACHED_RECOVERY_AND_MISSION_RELEASE_HOLD`

机器入口：[`../e19_b601_mission_branch_diagnostic_evaluation/results/E19_DIAGNOSTIC_EVALUATION_GATE_V1.json`](../e19_b601_mission_branch_diagnostic_evaluation/results/E19_DIAGNOSTIC_EVALUATION_GATE_V1.json)

### 已闭合的范围

- M01 与 M07 arm-only 五次轨迹的逐点复算，以及显式 REORG 路径适配后的刚性自由漂浮基座反作用诊断。
- M05 Sim13 常角速运动学与 static-display 坐标代数两个不可合并分支。
- M06 的 20 例标量半正弦等冲量求解器刺激。
- Sim15 四个 22 kg 理想刚塑捕获案例的当前代码精确重算。
- 输入、算法、输出、Gate 和验证器的哈希闭环与 fail-closed 负控。

### 不得外推

- `gate=HOLD`、`released_segments=0`、`next_stage_authorized=false`。
- 不能把四支路串成任务时间线；不能把 M06 波形幅值解释为物理接触力。
- M07 arm-only 未附着 22 kg 目标；锁定变换、接触法向、发布质量属性与恢复终端合同均为空。
- sim_05 适配只修复 REORG 命名空间，不升级历史模型、质量属性或科学结论。
- 测试通过不授予 CAD、机械设计、任务、接触、硬件、生产动力学或飞行权威。

---

<a id="e20"></a>

## e20：旧 M4 质量分支独立耦合诊断

### 资产分类

`DIAGNOSTIC / HOLD`

### 原始机器裁决

`E20_INDEPENDENT_SURROGATE_MASS_BRANCH_SIM11_COUPLED_ARM_ONLY_DIAGNOSTICS_CLOSED__E15_ANCF_PROVISIONAL_PANEL_CONTACT_ATTACHED_RECOVERY_CAD_MISSION_PRODUCTION_AND_FLIGHT_HOLD`

机器入口：[`../e20_b601_independent_mass_branch_coupled_diagnostics/results/E20_INDEPENDENT_MASS_BRANCH_COUPLED_DIAGNOSTIC_GATE_V1.json`](../e20_b601_independent_mass_branch_coupled_diagnostics/results/E20_INDEPENDENT_MASS_BRANCH_COUPLED_DIAGNOSTIC_GATE_V1.json)

### 已闭合的范围

- `Legacy-A` 与 `M3R-B` 分别对 M01、M07 arm-only 形成四条相互独立的 reduced-momentum/Radau 诊断 lane。
- 总质量只用“bus-only 等密度标量缩放”完成 surrogate 闭合；两分支不选择、不平均，其差值不是统计不确定度。
- 四条主 lane 的动量、能量、四元数和质量矩阵正定性均通过本地数值判据；局部模态加密与 Radau/BDF 对拍闭合。
- 输入、输出、Gate、验证和逐字节复现形成哈希闭环。

### 不得外推

- `gate=HOLD`、`next_stage_authorized=false`、`release_credit=false`。
- 旧 M4 两分支只是过渡敏感性，未消费、选择或替代当前 M7/R2 设计质量权威。
- 模型仍是历史 sim11 的 R1 provisional 帆板；e15 仍为 `REPEAT_ANCF_CERTIFICATION`。
- 未读取或执行 A2、接触窗、目标附着、锁定或恢复；M07 仍为 arm-only。
- 测试通过不授予 CAD、机械设计、任务、硬件、生产动力学或飞行权威。

---

<a id="e21"></a>

## e21：当前 M7/R2 安装语义与刚性翼耦合诊断

### 资产分类

`DIAGNOSTIC / HOLD`

### 原始机器裁决

`E21_M7_R2_MIXED_ARM_PLACEMENT_DETECTED__CURRENT_R2_RIGID_WING_FREE_FLOATING_ARM_ONLY_TWO_PLACEMENT_SENSITIVITY_AND_FIXED_BASE_ROM_REPRODUCTION_CLOSED__SINGLE_PLACEMENT_R2_FULL_FLEX_COUPLING_E15_HARNESS_CONTACT_MISSION_PRODUCTION_AND_FLIGHT_HOLD`

机器入口：[`../e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results/E21_DIAGNOSTIC_GATE_V1.json`](../e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results/E21_DIAGNOSTIC_GATE_V1.json)

### 已闭合的范围

- 独立复算 V2 与 V3_R2 九配置臂质量属性：C01–C06 对应物理几何安装上下文，C07–C09 对应 ODR-01 `T_SM`；这证明消费语义混用，但不否定 ODR-01，也不判任何配置错误。
- 以 V3_R2/C07 为当前质量账本，保持同一固定残余体，分别执行 ODR-01 与物理几何上下文的 M07 arm-only 自由漂浮刚性翼诊断。
- ODR-01 初始总质量、质心和惯量闭合 V3_R2；两安装分支只作为互斥敏感性，不选择、不平均，也不解释为不确定度。
- 固定基座 3-DOF/翼 ROM 精确复现发布频率；随动中间铰链质量造成的频率差只记录为尚未冻结的动态质量分配冲突，未传播到耦合动力学。

### 不得外推

- `overall=HOLD`、`next_stage_authorized=false`、`release_credit=false`。
- 部署锁定的刚性 R2 太阳翼不等于 R2 全柔性耦合；基座—翼参与因子、动态质量分配和阻尼矩阵仍未冻结。
- e15 仍为 `REPEAT_ANCF_CERTIFICATION`，B601 `R2-HRN-04` 仍需重设计。
- 未评价碰撞、物理接触、目标附着、抓取任务、生产或飞行。
- 测试通过不授予单一安装选择、机械设计放行、硬件运动或任务权威。
