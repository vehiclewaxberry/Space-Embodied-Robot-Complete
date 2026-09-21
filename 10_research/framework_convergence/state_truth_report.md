# State Truth Report — Research Framework Convergence

> 审计日期：2026-07-20  
> 分支：`feat/sim09-grasp-evaluator`  
> HEAD：`c7f09ab80580f5810d75253fd836d412aa862460`  
> 审计输入快照：在本目录生成前，仅 `01_project/inbox/source_documents/空间机械臂.docx` 未跟踪；该文件未读取为真值、未修改。  
> 纪律：机器 Gate JSON > 原始 CSV/JSON > 测试输出 > Git > 当前报告 > 旧报告。  
> **测试 PASS 不等于科学 Gate PASS。**

## 1. 总裁决摘要

项目已经完成并冻结“动力学基础—任务可行域—参数受限刚柔耦合—策略选择—
运行时安全—控制证据”数值链，并另有旧 campaign 的局部 DT2 离线回放；二者
尚未形成覆盖当前 sim_10/11/12、SAFE/CTRL/ASM 的统一回放链。sim_10、sim_11、sim_12 不得重建；
CTRL-01 与 Wave1 的 `REPEAT` 已按真实负结果收口，不得改写成 PASS，也不得继续
在同一冻结场景上调参“修到 PASS”。

当前唯一候选科学实施主线是：

`ASM-00 接口资格化 → ASM-01 连续接触与单源成功判据 → ASM-02 分阶段装配控制
→ Wave A 唯一集成 → ASM-TWIN-00 离线装配回放`

但 Wave A 尚未获 HAG-A 人工批准；ASM-00 存在 RF-1/RF-2/RF-3 与接口实测阻塞，
SSOT/gate registry 的八项 success 与 ASM-01“八项+第九项”尚未收敛为单源 schema，
目标侧 FFR/AG4 尚未闭合，W1-R12/W1-R13 的执行器资格也仍开放。
因此本轮推荐裁决为：

**`FRAMEWORK_CONVERGED_WITH_INTERFACE_BLOCKERS`**

## 2. A–G 分类

分类定义：A 已完成且冻结；B 已完成但带 PROVISIONAL 参数；C 已完成并保留真实
负结果；D 已规划但未实施；E 被外部参数阻塞；F 未启动；G 已被取代或仅供历史
考古。`A*` 表示有冻结数值资产，但无本模块独立 machine Gate JSON。

| 对象 | 分类 | 当前真实状态 | 机器裁决/边界 | 主要证据 |
|---|---|---|---|---|
| 六层研究框架、20260720 总览、七份历史文档归档 | A | HEAD 已完成，禁止再建平行总览或重复归档 | Git `c7f09ab`，非科学 Gate | `10_research/README.md`；`10_research/research_state_v4.md`；`01_project/competition/项目现状总览_20260720.md`；`01_project/competition/archive/README.md` |
| 坐标系与 frame tree | A | `T_SM` 等名义关系已冻结 | `nominal_frozen_v1` | `20_engineering/config/geometry/frame_tree_v1.yaml` |
| 12U+B601、目标、质量惯量与帆板 SSOT | B | SSOT 路径成立；质量、惯量、目标、帆板仍含低置信或占位参数 | 非 MEASURED | `20_engineering/config/geometry/`；`mass_inertia_budget_v1.csv` |
| 捕获/装配接口 | D+E | 捕获约束模式有定义；装配接口几何、公差、销距、倒角、刚度、锁紧参数未转正 | `geometry TBD` / `PROVISIONAL_DRAFT_FOR_PLANNING` | `capture_interface_v1.yaml`；`interface_ssot_draft.yaml` |
| sim_01–04 | A* | 早期刚体/翻滚/反冲/走廊数值资产已冻结 | 无独立 Gate JSON | 各 `results/*.csv` |
| sim_05 | A* | B601 6R 自由漂浮反冲基线完成；19.20° 被 sim_11 退化链复核 | sim_11 `G3b.pass=true` | `sim_05_base_attitude.csv`；`sim_11_gate_check.json` |
| sim_06 | A* | 捕获冲量锚点完成并被 sim_10 复核 | sim_10 `X1.pass=true` | `capture_impulse_matrix_v0.csv`；`sim_10_gate_check.json` |
| sim_07 组件模型 | B | ANCF 组件响应存在，参数占位 | 组件结果不等于候选级认证 | `30_simulation/sim_07_ancf_flexible/` |
| e15 ANCF 认证 | C | 已执行并保留负裁决 | `REPEAT_ANCF_CERTIFICATION`，最大跨解算器差 5.637% > 5% | `30_simulation/e15_ancf_certification/results/gate_summary.json` |
| sim_08 | B | 执行机构预算完成并被 sim_10 X3 对拍；硬件档仍为 placeholder | sim_10 `X3.pass=true` | `actuator_budget_sweep.csv`；`sim_10_gate_check.json` |
| sim_09/E1 | A* | 72 例抓点评价与 Pareto 资产已完成 | 无总科学 PASS verdict | `30_simulation/sim_09_grasp_evaluator/results/` |
| e15 刚体核心覆盖 | C | 覆盖核算通过，但无安全候选是真实负结果 | `P0_A_CORE_COVERAGE_PASS`；scientific verdict=`REPEAT_CORE_NO_SAFE_CANDIDATE` | `30_simulation/e15_core_coverage/results/core_gate_check.json` |
| e16 同步捕获 | B+C | 216 例 campaign 完整；18 个动态例均非 formal safe，柔性未评估 | `PASS_WITH_GEOMETRY_AND_FLEX_LIMITATIONS`；formal safe=0 | `30_simulation/e16_sync_capture/results/gate_check.json` |
| sim_10 任务可行域 | B | 9002 物理点、五门裁决完成，禁止重建 | `SIM10_GATES_PASS`；`FLEX=UNKNOWN_NOT_IN_CRITERIA`；四项 provisional note | `sim_10_gate_check.json` |
| sim_11 刚柔耦合/有限接触带宽 | B | v1.1 G1–G5 通过，G4 已闭环，禁止重做 | `SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS` | `sim_11_gate_check.json` |
| sim_12 策略选择 | A | Gate0 与 16 例 Phase1 已完成并冻结 | `SIM12_PHASE1_GATES_PASS` | `sim_12_gate_check.json` |
| SAFE-00 | A | 冻结合同和预注册案例下 fail-closed 安全门通过 | 模块 `PASS`；`next_stage_authorized=false`；Wave1 独立复核 PASS | `safety_00_gate_check.json`；`wave1_gate_check.json` |
| CTRL-01 | C | 3 缺陷已修、7 项真实负结果保留，治理收口 | `REPEAT`；`next_stage_authorized=false`；`tests_are_not_gate=true` | `control_01_gate_check.json`；`wave1_cp6_ruling.md` |
| CTRL-02 | B | GC0–GC7 通过；`review_status=PENDING_REVIEW`；执行器、量子与硬件有效性仍 provisional | `PASS`；7/16 在 R5 PROVISIONAL 执行器及时窗模型下为 `STABILIZED_WITHIN_WINDOW`，9/16 未满足；L0 硬件有效稳定性 `NOT_EVALUATED_NO_ACTUATOR_DYNAMICS`；W1-R12/R13 保留 | `control_02_gate_check.json` |
| Wave1 集成 | C | 实现缺陷清零，余项按真实负结果收口；治理关闭不改 verdict | `WAVE1_REPEAT`；`next_wave_authorized=false` | `wave1_gate_check.json`；`wave1_cp6_ruling.md` |
| CAD/可视化冻结包 | A（局部 DT2） | v0 三维场景、六支 MP4、单文件仪表板与离线证据回放已冻结 | `VIZ_GATE_0_ACCEPTED`，不改变科学 verdict | `VIZ_GATE0_FREEZE_20260714.md`；`viz_gate0_acceptance_report.md` |
| 当前全链 DT2 | D | 现有回放未覆盖 sim_10/11/12、SAFE/CTRL、Wave1 与 ASM 的当前证据 | 未实施统一回放 | `project_visualization_v1_research.html` 的旧 `REPEAT_CORE` 口径 |
| DT3/DT4 | F | 无实时状态同步或硬件双向闭环 | NOT_STARTED | 无相应 Gate |
| ROM 选择器 | D | L0/L1/L2 组件与规则草案存在；selector 和 Gate 未实现 | `DRAFT_PLAN_ONLY` | `10_research/rom/` |
| Physics Tools | D | 合同与 T-Gate 已设计；工具和裁决未实现 | `DRAFT_NOT_IMPLEMENTED` | `tool_contract_draft.yaml`；`system_interface_plan.md` |
| V2.5/VLA | D+F | 装配 V3-vs-V2.5 配对协议存在；捕获协议缺同工具确定性 V2.5；模型、数据、渲染、消融与 Gate 均未执行 | `PROTOCOL_DRAFT` | `vla_generalization_plan.md`；`on_orbit_assembly/vla_sequence_plan.md` |
| B601 H0–H3 | D+F | 路线有规划，硬件资格与控制均未开始 | NOT_STARTED | `system_interface_plan.md` |
| 在轨组装规划包 | A（规划资产） | 15 个规划/审计文件 + 3 张卡（共 18 个文件）存在，无需重规划 | planning verdict=`READY_WITH_INTERFACE_BLOCKERS` | `10_research/on_orbit_assembly/` |
| ASM-00 | D+E | 任务卡完备，实施与 AG0 均不存在 | RF-1/2/3、接口实测阻塞 | `waveA_task_cards/ASM-00.md` |
| ASM-01 | D+E | 连续接触、卡滞状态机已规划，无结果；success 存在 8/9 项 schema 冲突 | 预注册上限 `ASM01_SCREENING_ONLY`；HAG-A 前先单源化 | `interface_ssot_draft.yaml`；`gate_registry.yaml`；`waveA_task_cards/ASM-01.md` |
| ASM-02 | D+E | AC0–AC3 已规划，无实现；受 AG0、ASM-01 冻结及 W1-R12 阻塞 | NOT_EVALUATED | `waveA_task_cards/ASM-02.md` |
| ASM-TWIN-00 | F | 无装配标准时程、Gate 证据或回放 | NOT_STARTED | 无结果目录 |
| SPART/Pinocchio/Basilisk/SpaceDyn/MuJoCo/Simulink 等对拍 | D+F | 只有候选定位或零散审计建议，无外部运行结果和 Gate | NOT_EVALUATED | 现有计划/外部资产目录 |
| 20260715 总览、research_state_v3、旧控制“未启动”文字、旧可视化横幅 | G | 状态已被当前 Gate/Wave1/20260720 总览取代 | 历史参考 | 对应历史文件 |

## 3. ALREADY_COMPLETE：不得重做

1. sim_01–08 冻结基础资产；引用强度按是否有下游 Gate 交叉复核限定。
2. sim_10 任务可行域、四门 fail-closed 扫描及哈希锁。
3. sim_11 v1.1 接触带宽修复、G4 前向收敛链与 G1–G5 裁决。
4. sim_12 Gate0 账本、16 例 Phase1 和 binding-gate 结论。
5. SAFE-00 运行时安全门。
6. CTRL-01 实施、缺陷修复与真实负结果收口。
7. CTRL-02 冻结 provisional 范围内的姿态分账裁决。
8. Wave1 唯一集成、独立审查与 CP6 方案 B 终裁。
9. VIZ-Gate0 离线三维场景、视频与证据回放包；等级仅 DT2。
10. 坐标系、12U+B601 主构型与现行 SSOT 路径。
11. ROM、Physics Tools、VLA/V2.5、H0–H3 的现有规划；实施时复用。
12. 在轨组装规划、双红队与 ASM-00/01/02 三张现有任务卡。
13. `10_research/README.md`、`research_state_v4.md`、20260720 总览和七份历史归档。

## 4. 真正未闭合

### 外部参数/接口阻塞

- RF-1 锥面聚拢、RF-2 楔紧边界、RF-3 clearance 语义。
- 销距、倒角、接口刚度/摩擦/锁紧力、公差与出处转正。
- 杨恒帆板参数卡；到位后触发 sim_11 与受影响下游 Gate 重跑。
- B601 夹爪 `T_c` 实测。
- W1-R12 轮力矩与 W1-R13 最小脉冲量硬件资格。
- ASM success 8/9 项冲突：HAG-A 前必须选定唯一版本化 schema 并绑定哈希。

### 已规划未实施

- ASM-00/01/02 的实现、原始结果与机器 Gate。
- ASM-TWIN-00 离线装配回放。
- ROM selector/认证；Physics Tools 正式合同/实现；V2.5/VLA 实验。
- B601 H0–H3。
- 外部独立框架最小对拍。
- DT3 实时同步与 DT4 双向硬件闭环。

### 已执行但受限

- e15 ANCF `REPEAT_ANCF_CERTIFICATION` 是负裁决，不是漏做。
- e15 core/e16 的零 formal-safe 候选只对冻结场景成立，不能外推“永远不可行”。
- CTRL-01 `REPEAT` 是冻结增益与预注册轨迹下的真实负结果；新增益/轨迹必须另立
  新实验，不得回改冻结结果。

## 5. 状态冲突与过期指针

1. 审计输入中的 `.codex/AGENTS.md` 曾称 sim_12 为唯一在研仿真主线；本轮已原位
   修正为 Phase1 ALREADY_COMPLETE 与 Wave A `PLANNED_NOT_AUTHORIZED`。
2. `10_research/partner_requirement_closure/state_truth_report.md` 仍保留当时的
   `NOT_STARTED` 快照；两份 control 预注册计划已加当前 Gate 覆盖横幅，历史正文保留。
3. `项目现状总览_20260715.md`、`research_state_v3.md` 和 v1 研究仪表板的
   `REPEAT_CORE` 横幅是旧阶段状态。
4. 20260720 总览初稿把 sim_01–08 放入“全部机器裁决背书”表；本轮已改为“机器
   Gate + 下游交叉复核”，明确八个早期模块并非各有独立 scientific PASS。
5. SAFE-00 模块 `next_stage_authorized=false/review_status=PENDING_REVIEW` 与 Wave1
   独立复核 PASS 分属实现者与集成者层级；都必须保留。
6. CP6 关闭治理循环不把 `WAVE1_REPEAT` 或 CTRL-01 `REPEAT` 改成 PASS。
7. 组装 `AG-A0=PASS`、`READY_WITH_INTERFACE_BLOCKERS` 是规划审计，不是装配
   科学 Gate。
8. 组装 success 基数存在 8/9 冲突；本轮未擅自选边，已设为 HAG-A 前硬阻塞。
9. HEAD 已完成七份归档与六层总览；不得再次移动或创建平行体系。

## 6. 核心证据哈希

| 工件 | SHA-256 |
|---|---|
| `sim_10_gate_check.json` | `2a9024bb0f57f837e58161a0fa96660e2e237ec96ef096eba458cb0dcc4a19d4` |
| `sim_11_gate_check.json` | `5bba3112a704583fecb315419c1d73848bf72fe82f89b7a8fb104abb1ea0aa47` |
| `sim_12_gate_check.json` | `e92ae9c2287149ff00234760cf0d3a53524fd59b71b7e93b2785e578aae91f5f` |
| `safety_00_gate_check.json` | `ff56929dd8352e447afdb8b7d17c5ef0b248883c66bc4f00c16c50c6f4c46eee` |
| `control_01_gate_check.json` | `3d32f78a7cc4bf57718efb1e4ddf70cab843c4b67173833ab4aa4971735baa8a` |
| `control_02_gate_check.json` | `8d072eaeacbbdbb1bb7637434a0b5db77b6d37c42f706dc075950aa9b123a341` |
| `wave1_gate_check.json` | `c8d631d68537c9edd9c3e55ec9456c5ac61474ef850e4ca6f280595de4429dae` |

## 7. 当前实施授权

本报告不自动批准 Wave A。批准前状态为 `PLANNED_NOT_AUTHORIZED`。人工批准后，
只授权一个主波次：先以 ASM-00 解除接口阻塞，再按 Gate 边推进 ASM-01/02；
外部工具、ROM、VLA、DT3/DT4 与硬件不得抢占主线。
