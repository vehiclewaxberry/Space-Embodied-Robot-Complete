# ctrl 分片审计发现（控制与 SAFE 安全核域）— 2026-08-27

## 授权覆盖声明

本审计唯一写入位置 `90_competition_closeout/20260827_current_state_audit/fragments/ctrl/` 由用户在任务指令中显式授权创建，优先于 `AGENTS.md`（sha256 前 12 位 `3d2269562678`）REORG04「根目录业务资产只允许八个域」的限制。本审计全程只读：未执行任何 git 写操作、未运行仿真/CAD、未重发任何 Gate；sha256 均用 Git Bash `sha256sum` 对引用文件现算。

## 审计方法

入口按任务给定路径直读：`30_simulation/` 下 7 个控制/安全胶囊的机器 Gate JSON 逐字段核验，交叉 `01_project/competition/R2动力学与控制工程闭环阶段裁决_20260827.md`（父裁决，sha256 `3eed50dd728e`）、`wave1_gate_check.json`（`ef49240d9047`）、`wave1_cp6_ruling.md`（`1eeea3ccffb1`）、`competition_gate_check.json`（`8b3cdbdaa09e`）。未按 mtime 选 authority；所有数字均回原始 JSON 字段核对。

## 一、父级裁决（2026-08-27，本域当前最高权威）

`01_project/competition/R2动力学与控制工程闭环阶段裁决_20260827.md` §1 fenced block（行 7-18）：R2 control engineering = HOLD、SAFE independent review = HOLD、joint system readiness = false、next_stage_authorized = false、release_credit = false。§5：联合 Gate 13 条件仅 4 真（source_binding、manifest integrity、owner option A、red team P0/P1=0），control_engineering_pass=false、safe_independent_review_pass=false。该裁决明文：「SAFE-00 的历史机器 Gate 为 PASS，但 review_status=PENDING_REVIEW 且 next_stage_authorized=false；Sim13 的 20/20 是负控后端信用，最大运行态仍为 ABORT_ONLY，不能升级为抓取执行权限」（§5 行 148）。管理默认状态（FORMAL_DYNAMICS_CONTROL_RELEASE=HOLD、OFFLINE_PHYSICS_GATED_DEMO=GO 等）与本地最新文件一致，未发现更晚 Owner 覆盖。

## 二、决策问题 11：CTRL-01/CTRL-02 真实状态与适用域

### CTRL-01 = REPEAT（冻结增益与预注册轨迹下）

- 机器 Gate：`30_simulation/control_01_end_effector_tracking/results/control_01_gate_check.json`（`ab1fd26978f4`），`$.verdict="REPEAT"`（行 6）、`$.next_stage_authorized=false`（行 7）、`$.evidence_complete=true`。
- 三缺陷修复已字段级确认：能量账本 `$.gates.GC1_B.energy_audit_relative_max=5.6325998524987115e-12`（阈值 1e-9 未动；v0 值 0.0789595238864667 逐字保留于 `$.gates.GC1_D.previous_loop_negative_results_preserved`）；T3 碰撞合同伪影修复后 static/target/combined 最小余量 +0.01462/+0.11476/+0.01462 m（`$.gates.GC1_E.collision_evaluation`，6×501 固定节点全覆盖）；C2_MATCH5 比较器方法学闭环（`$.gates.GC1_D.isolated_nullspace_comparator="C2_MATCH5"`）。
- 七项预注册真负结果保留：GC1_A2 闭环锚差 0.15504 deg>0.05、C2 位置增量 -38.26%、C3 孤立零空间真零 +1.8387e-05%、关节限位 -1.4728 rad、sigma_min 6.64e-5、速度/加速度超档、C1_T3 有界误差 0.1902 m>0.11 m（gate `$.gates.GC1_A2/D/E/F`；集成级归因见 wave1_gate_check.json `$.repeat_remainder_classification_per_preregistration_item_2`）。
- CP6 终裁（`1eeea3ccffb1` 行 20-22）：引用限定语为「冻结增益与预注册轨迹下」；C3 按真零 +1.84e-5% 表述；治理关闭不改写 `WAVE1_REPEAT`。
- 适用域边界（gate `$.claim_scope.forbidden`）：禁止一般控制器优越性、硬件/飞行性能、晋级表述。
- **当前树降级**：`CTRL_R2_PREDEVELOPMENT_GATE_V1.json`（`ed4d8b7774c6`）`$.criteria[C1].current_replay`：7 passed / 15 failed / 22 total，HOLD_CURRENT_REPLAY；`reproduction.status=NOT_CLAIMED_REORG04_NORMALIZED_HASH_DRIFT`（冻结 sim05 URDF 定位指向 pre-reorg 根 CAD 路径 + 配置/矩阵规范化哈希漂移）。历史 Gate 未变（`historical_gate_changed=false`），但当前树精确复现未声明。

### CTRL-02 = PASS_WITH_PROVISIONAL_SCOPE（review_status=PENDING_REVIEW）

- 机器 Gate：`30_simulation/control_02_base_attitude/results/control_02_gate_check.json`（`240fa708b536`，与父裁决 §8 受保护哈希逐位一致），`$.verdict="PASS"`（行 1100）、`$.review_status="PENDING_REVIEW"`（行 1078）、`$.thresholds_widened=false`。
- 7/16：`$.experiment_summary.n_stabilized_within_window=7`（16 行 Stage-B transient）；判据模型 `$.gates.GC7.criterion.status="PROVISIONAL"`（wheel 0.01 N·m、最小脉冲 0.02 s、窗口 300 s、 settle 0.05 dps 全为 R5 PROVISIONAL 占位，行 545-556）。
- L0 硬件有效稳定性：`$.stage_B_scope.L0_stability_status="NOT_EVALUATED_NO_ACTUATOR_DYNAMICS"`（行 1093）；A3 `NOT_APPLICABLE_WITH_MISSING_FROZEN_ACTUATOR_DYNAMICS`；FLEX `UNKNOWN_NOT_IN_CRITERIA`。
- 量子残差=门槛 21.5%：wave1_gate_check.json `$.integration_checks.red_team_completeness.key_findings_this_round[6]`（行 286）——最坏残差 0.0108 dps 为 0.05 dps 门槛的 21.5%，硬件最小脉宽增大 ~4.6× 则 Stage-B 裁决翻转（W1-R13 硬件触发项，CP6 已登记）；gate 内 `$.gates.GC7.quantization_note` 同样声明残差地板贴近门槛。W1-R12（行 285）：Stage-A 隐含轮力矩 0.033 N·m 超 R5 档 3.3×。
- 适用域：`PASS_WITH_PROVISIONAL_SCOPE` 外部口径由 competition_gate `$.negative_results.ctrl02_external_scope` 与 prebind 快照（`bdbd17db679e`，CTRL_02 行 scope 字段）承载；claim_forbidden 禁止一切硬件有效/替换占位后仍成立的结论。
- **当前树降级**：PREDEVELOPMENT Gate `$.criteria[C4].current_replay`：12/12/24，HOLD_CURRENT_REPLAY，且记录到测试管线副作用重写冻结 Gate 后精确恢复（`TEST_PIPELINE_SIDE_EFFECT_REWROTE_FROZEN_GATE_THEN_EXACT_RESTORE_WAS_VERIFIED`）——治理风险点。

## 三、决策问题 12：SAFE-00 模块 PASS 是否授予执行权——**否**

- 机器 Gate：`30_simulation/safety_00_runtime_gate/results/safety_00_gate_check.json`（`ff56929dd835`），`$.verdict="PASS"`（行 3）、`$.review_status="PENDING_REVIEW"`（行 9）、`$.next_stage_authorized=false`（行 8）、review_note 明文「independent re-review remains required before any next-stage authorization」。
- 47/47：测试计数见 `results/evidence_manifest.json`（`056778011c4b`，`passed=47/total=47`）与 `safety_00_tests.log` 行 52 `TOTAL: 47/47 PASS`；gate 内预注册决策案例为 16 例（`$.cases`），GS-B 绕过案例 12 例 `bypass_success_count=0`。
- UNKNOWN 永不 ALLOW：`$.metrics.unknown_allow_count=0`，GS-A 五项检查全 true（unknown_never_allow、no_provenance_no_allow 等）；`false_abort_rate=0.0`。
- 合同原文：`docs/safety_gate_contract.md`（`bd3b362aa440`）§1 决策枚举 `ALLOW/MODIFY/WAIT/BACKOFF/ABORT`；§6 明文「机器 Gate PASS 不等于获准进入下一阶段」，`review_status=PENDING_REVIEW`、`next_stage_authorized=false`。
- **「downstream_authorization」字段在全项目 0 命中**（grep 全仓无匹配）——该字段名不存在于 SAFE-00 gate JSON；下游授权语义由 `next_stage_authorized=false` + contract §6 + 父裁决 §5 承载。记为证据缺口（预期字段缺席），语义结论不受影响。
- 当前树重放：PREDEVELOPMENT Gate `$.criteria[C7].current_replay` 23 passed / 24 failed / 47 total，HOLD_CURRENT_REPLAY（`CURRENT_SOURCE_BINDINGS_DO_NOT_REPRODUCE_FROZEN_SAFE_ALLOW_AND_MODIFY_FIXTURES`）。
- 结论：SAFE-00 模块 PASS 是冻结范围内的历史模块级证据，**不授予任何执行权或下一阶段授权**；「UNKNOWN 不得映射为 EXECUTE」在机器层由 unknown_allow_count=0 与 12 绕过案例 0 成功支撑。

## 四、真实闭环轨迹与控制链段核查

- **不存在任何真实（硬件）closed-loop 轨迹证据**。所有闭环证据为仿真/合成：CTRL-01 闭环运行于 sim_11 冻结 plant（GC1_H 锚定 `sim_11_coupled_dynamics/src/coupled_dynamics.py`）；sim_13 v4 目录名即 `v4_synthetic_contact_capture_diagnostic`（见 prebind 工作树清单 locator）；R2 控制 Gate `$.execution_guards` 中 backend_advance/collision_query/contact_execution/pair_or_edge/m01_path_search 全为 false（`2740b33e7958` 行 65-71）；执行器 152/152 实测字段全 null 且零填充禁止（父裁决 §3 行 98）。
- **题述六段链 TASK_READY→PREGRASP→SPIN_SYNCHRONIZATION→SOFT_CONTACT→CAPTURE_VERIFICATION→RECOVERY 在全仓库 0 命中**（SPIN_SYNCHRONIZATION 与 CAPTURE_VERIFICATION 均无匹配），当前不存在该链任一可复现控制链段。现存仅有：supervisor 接口合同状态枚举（`CTRL_R2_SUPERVISOR_INTERFACE_V1.json`，`5bfd8ab0672d`：轮组 WHEEL_NOMINAL/…/ABORT 与接触 PRECONTACT/FINITE_WINDOW_CONTACT/CAPTURED_RECONFIGURE/POST_CAPTURE_STABILIZE/ABORT，均为枚举非运行时）；supervisor 评估 `operational_supervisor_complete=false`（`1779ece775a1`）；PB_G1 G1-04（RPO→TASK_READY）与 G1-05（PREGRASP→capture）均 NOT_EVALUATED，「State transitions remain schema-only」（`7ad34fcf9482`）；sim_14 事件链 RESET_READY→PREGRASP→CONTACT_CANDIDATE→CAPTURED 为域外参考。
- **MODIFY/WAIT/ABORT 状态机证据**存在于合同层与离线重放层：SAFE-00 决策枚举经 16 预注册案例机器验证；离线演示三场景动作确定性重放（见下节）。这些是合同/离线证据，非运行时执行证据。

## 五、离线三场景演示可重放性评估

- `10_research/competition_convergence/competition_gate_check.json`（`8b3cdbdaa09e`）：`$.final_verdict="COMPETITION_DEMO_READY"`、`checks_passed=17/17`；`OFFLINE_REPLAY_EXACT_ACTIONS` 核验 `A_low=EXECUTE、B_anchor=ABORT、C_transition=MODIFY`、`command_emitted=false`、`replay_mode=OFFLINE_DETERMINISTIC`、`deterministic=true`（行 84-106）；`DELIVERY_REPLAY_BYTE_IDENTITY` PASS；`VIDEO_PACKAGE`（mp4 1920x1080 h264 54.97 s）与 `PPTX_PACKAGE`（9 页）PASS；`GROUND_COMPONENT_STOP_STATE` 核验 B601_MOTION=PROHIBITED、H0/H1/H2 NOT_STARTED。
- 媒体与重放文件实物存在：`40_evidence/artifacts/competition_convergence/`（mp4 1,572,615 B、pptx 177,259 B、replay 四 JSON，mtime 2026-08-04），字节数与 Gate 记录一致。
- **可重放性结论**：在裁决语义层面，三场景演示用现有资产可确定性重放（离线、逐位、action 级）。**证明边界**：`offline_replay=true`、`real_time_synchronization=false`、`command_emitted=false`、`stop_rules` 全 false——离线 demo ≠ 硬件/实时/自动执行资格；`$.negative_results` 同时登记 safe00_next_stage_authorized=false 与 ctrl02 两项限定。
- **注意（REORG04 漂移）**：Gate 记录的重放文件 byte-identity 哈希为 2026-07-20 值（如 replay_manifest 438f2697…），当前文件现算 sha256 为 255eddaf…——与 REORG04「路径迁移允许路径字符串与文件 SHA-256 变化、语义保持一致」规则一致；字节同一性声明应视为历史结论，引用时以当前哈希+语义核验为准。

## 六、子模块/父 Gate 一致性检查

- Sim13：父联合 Gate（`55490805d934` `$.diagnostic_facts_no_credit.sim13_*`）已直接绑定 20/20 负控 Gate 文件并仍判 HOLD；08-25 机械终裁文档中的「15/20」字段已被 08-27 父裁决取代——**非挂起的 CHILD_RESULT_NEWER__PARENT_GATE_NOT_REISSUED 案例**（父 Gate 已重发且包含子模块新结果，未升级是语义决定而非遗漏）。
- prebind 快照（`bdbd17db679e`）对 CTRL-01/CTRL-02/SAFE-00 三模块的源哈希复核值（AB1FD269…/240FA708…/FF56929D…）与本审计现算值逐位一致。

## 七、对比赛提交（2026-09-01）的相关性结论

本域无 P0_SUBMISSION_BLOCKER：离线演示 Gate 17/17 已 PASS 且媒体齐备，控制/安全叙事均有带限定语的机器证据可引用。两项 P1（E-COMP-04 受限控制闭环、E-COMP-03 SAFE 故障注入/复审）影响决赛答辩展示口径：答辩只能承诺「离线确定性重放 + 冻结合同层安全核 + 历史模块 PASS（PENDING_REVIEW）」，不得暗示在线控制链或已授权执行。CTRL 正式 Release、执行器实测、replay 漂移、接触 as-built 均为 P2，禁止升级为 P0。

## 给综合裁决的输入

1. CTRL-01 当前真实状态=REPEAT（gate `$.verdict`，`ab1fd26978f4` 行 6），适用域仅限「冻结增益与预注册轨迹下」限定句式（CP6 `1eeea3ccffb1` 行 20-22），且当前树精确复现 7/22 HOLD（`ed4d8b7774c6` `$.criteria[C1]`）。
2. CTRL-02 当前真实状态=PASS_WITH_PROVISIONAL_SCOPE + review_status=PENDING_REVIEW（`240fa708b536` 行 1078/1100）；7/16 STABILIZED 仅在 R5 PROVISIONAL 执行器/时窗模型下；L0=NOT_EVALUATED_NO_ACTUATOR_DYNAMICS；量子残差=门槛 21.5% 为 W1-R13 硬件触发项（`ef49240d9047` 行 286）。
3. SAFE-00 模块 PASS（47/47）**不授予执行权**：next_stage_authorized=false、review_status=PENDING_REVIEW（`ff56929dd835` 行 8-9），合同 §6 明文「PASS≠进入下一阶段」（`bd3b362aa440`）；UNKNOWN→ALLOW 计数为 0、12 绕过案例 0 成功。
4. SAFE-00 gate JSON 中不存在 downstream_authorization 字段（全仓 0 命中），下游授权语义由 next_stage_authorized=false 承载——记为预期字段缺席的证据缺口。
5. 三模块当前树 replay 均 HOLD：CTRL-01 7/22、CTRL-02 12/24（含重写冻结 Gate 的副作用记录）、SAFE-00 23/47（`ed4d8b7774c6` `$.criteria[C1/C4/C7]`）；历史冻结 Gate 未变，漂移源于 REORG04 哈希规范化与 sim05 URDF 定位。
6. 不存在任何真实 closed-loop 轨迹证据：全部闭环为 sim_11 仿真 plant 或 synthetic contact 诊断；R2 控制 Gate `$.execution_guards` 六项执行计数全 false（`2740b33e7958`）；执行器 152/152 实测字段 null、零填充禁止。
7. 题述六段任务链（TASK_READY→…→RECOVERY）全仓 0 命中、不可复现；最近似的合同状态机为 supervisor 枚举（`5bfd8ab0672d`）与 PB_G1 G1-04/05=NOT_EVALUATED（`7ad34fcf9482`），operational_supervisor_complete=false（`1779ece775a1`）。
8. 离线三场景演示可确定性重放：COMPETITION_DEMO_READY 17/17、动作 A_low=EXECUTE/B_anchor=ABORT/C_transition=MODIFY、command_emitted=false（`8b3cdbdaa09e` 行 84-106/212-218）；媒体实物字节数与 Gate 一致；但 replay 文件当前哈希与 Gate 记录存在 REORG04 漂移，byte-identity 为历史结论。
9. 联合 Gate 13 条件仅 4 真、control_engineering_pass=false、safe_independent_review_pass=false、release_credit=false（`55490805d934`）；Sim13 20/20 已被父 Gate 绑定且仍 ABORT_ONLY——无挂起的子模块升级案例。
10. 本域 blockers 分类：E-COMP-04/E-COMP-03=P1（决赛展示），CTRL 正式 Release/执行器实测/replay 漂移/接触 as-built/prebind 权威=P2（禁止升 P0），Sim13 非 ABORT=P3；无 P0。
