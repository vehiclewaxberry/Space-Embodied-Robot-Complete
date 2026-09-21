# Sim13 数字线程与当前系统绑定域——当前状态审计 fragment（分片 sim13）

审计日期 2026-08-27（本地）。只读执行：未做任何 git 写操作、未覆盖/移动/删除任何文件、未运行 CAD/仿真/Gate 重发。

**写入授权覆盖记录**：本分片唯一写入位置 `90_competition_closeout/20260827_current_state_audit/fragments/sim13/` 由用户在审计任务书中显式授权创建，优先于 AGENTS.md（`AGENTS.md` L6-9，sha256 前 12 位 `3d2269562678`）REORG04 的八域根目录限制；本 fragment 仅新增该目录下 5 个文件，不改动任何既有资产。

## 0. 域状态一句话

Sim13 当前系统绑定域处于「终端父 Gate 15/20 冻结 + 终端后 append-only 后端子域 20/20 已闭合但父未重发」的双口径状态，最高合法运行状态为 `ABORT_ONLY_WITH_VALIDATED_FAIL_CLOSED_BACKENDS_20_OF_20_NC__PRODUCTION_NON_ABORT_STILL_MASKED_BY_12_GATE_AUTHORITY`，non-ABORT 一律不允许，联合 Gate（R2 dynamics/control/system closure）保持 HOLD（4/13）。

## 1. 八个必答题逐条裁决

### Q1 真正当前系统的 MECH_RL_SYSTEM_INTERFACE_V2 实例是否存在？——存在（工件层），未授权（权威层）

- 实例文件 `30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/interfaces/MECH_RL_SYSTEM_INTERFACE_V2.yaml`（6716 B，sha256 前 12 位 `b105766ec1f1`，mtime 2026-08-25 19:59），`schema: MECH_RL_SYSTEM_INTERFACE_V2`，`instance_class: INSTANTIATED_20_OF_20_NC_BACKENDS_BOUND__PENDING_OWNER_REVIEW`（YAML L119/L131）。
- 发射回执 `runtime_fail_closed_backends_v2/evidence/SIM13_V2_INTERFACE_EMISSION_RECEIPT_V1.json`（sha `98370844b23f`，`$.interface.sha256=B105766E…` 与磁盘复算逐位一致）；addendum `$.source_pins.mech_rl_system_interface_v2`（bytes=6716, sha `B105766E…`）再次钉死，三方一致。
- 但接口自报权威字段：`authority.current_values.sim13_system_binding_gate_passed=false`、`owner_accepted=false`、`current_consumer_load_authorized=false`、`current_contact_grasp_authorized=false`、`next_stage_authorized=false`（YAML L97-122）。addendum `$.current_authority.mech_rl_interface_instance_exists=true` 同时确认存在性与未授权性。
- 预期「yaml 合同存在但实例待后端落地」**已被 2026-08-25 晚的后端包推进改写**：实例已落地，待的是 Owner 评审与绑定门，不再是后端实现。

### Q2 正式 current-system URDF 是否存在？——不存在正式版；存在 SOURCE_ONLY 发射候选

- `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/generated_v2/unified_r2_c01_no_route_c_sim_candidate_v2.urdf`（17191 B，sha 前 12 位 `d84aa23ce98a`），发射回执 `UNIFIED_R2_URDF_EXECUTION_RECEIPT_V2.json`（sha `957ca67d7bcc`）`$.emission_class=SOURCE_ONLY_BUILDER_EMISSION__NOT_GEN_URDF_AUTHORITY_EXECUTION`，7 项检查全 PASS（19 link/18 joint/16 physical、总质量精确 31.022864807342987 kg、E_HW 限位逐位不变）。
- 披露缺陷 TMC-F01（receipt `$.documented_defect`）：gen_urdf 运行时代码指纹在 CPython 3.13.9/3.14.4 冷热态间确定性漂移，8 次授权执行尝试全部被 fail-closed 终检拒绝；URDF XML 数据本身确定性不受影响；处置需 Red Team + Falsifier + Owner。
- prebind gate `$.system_urdf_available=false`（`SIM13_V2_PREBIND_SOURCE_GATE_V1.json`，sha `dbfff803a656`）是 2026-08-24 冻结时点的字面状态，已被 08-25 发射事实超越但父 Gate 未重发——属「字段陈旧」而非「矛盾」。
- 结论：区分两类——Unified R2 `SOURCE_ONLY_BUILDER_EMISSION` 发射**存在**；正式系统 URDF（经授权 gen_urdf 执行 + 系统绑定门通过）**不存在**。

### Q3 当前系统动力学状态演化证据是否存在？——后端级存在，生产级缺席

- NC18 后端：`SIM13_DYNAMICS_BACKEND_GATE_V2.json`（sha `bc02c02b75c0`）`gate_passed=true`、`dynamics_backend_validation_receipt_all_pass=true`；后端 README（sha `66a82bc13797`）L18-22 记载其实现：哈希锁定 unified URDF（17191 B / `D84AA23C…`）+ 执行回执，经树核 + 零动量约化动力学（Schur 补 + Richardson 导数 + RK4）演化 8-DOF 关节/自由漂浮基座/末端状态，名义推进动量残差 ~1e-19。
- 边界：prebind gate `production_dynamics_gate_passed=false`；v3 gate（sha `a657d015ba5e`）DYN-G02「production generalized-effort-driven dynamics」= `HOLD_NOT_IMPLEMENTED_OR_AUTHORIZED`；联合 gate `dynamics_engineering_pass=false`。力矩驱动生产正向动力学未实现未授权。

### Q4 权威窄相接触是否存在？v4_synthetic_contact_capture_diagnostic 证明边界？——合同包络级存在，物理级缺席；合成链证明边界清晰且有已注册失败

- NC19 后端：`SIM13_CONTACT_GRASP_GATE_V2.json`（sha `f13b755ea0b3`）verdict 含 `BOUNDED_PROVISIONAL`；后端 README L23-28：绑定 `DESIGN_CONTACT_MODEL_V1`（BOUNDED_PROVISIONAL）包络、released contact geometry 为派生非实测、包络外/缺参→UNKNOWN→ABORT。当前接触授权 `current_contact_grasp_authorized=false`。
- v4_synthetic_contact_capture_diagnostic 证明边界（逐 phase 的 audited gate authorizations）：
  - V4A（sha `82ecf267aa5f`）：合成 6R+2P 全浮动无接触内核 PASS_AUDITED；`current_system_bound=false`、`formal_nc19_closed=false`。
  - B1（`91f11fa541a3`）无摩擦单接触 PASS，`formal_contact_backend=false`；B2（`475fe497f8c3`）正则化摩擦 PASS，`physical_friction_identified=false`；B3（`8d7674711cd2`）分支双硬指瞬态候选 PASS，秩 5 无 6D 闭包、`grasp_success=false`。
  - B4 合同（`55441dff42c9`）仅预注册冻结，`b4_dynamics_solver_implemented=false`；B4E（`8f644e69f626`）求解器审计 PASS 但 `PRIMARY_BRANCH_HORIZON_EXHAUSTED_INCONCLUSIVE`；B4F（`27fa21f23bd4`）合同冻结，`SOLVER_NOT_IMPLEMENTED__CAMPAIGN_NOT_EXECUTED`。
  - B4G 执行链失败：`SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json`（sha `2743fbd314cc`）注册 3 例 B4F-G06 能量-功恒等式失败；`PRIOR_FINAL_CREDIT_SUPERSEDED_V1.json`（`e8ab12c4b117`）；R1 闭环门（`ae7e81f66cf6`）确认机理=冻结离散第一定律中显式中点二阶截断缺陷（仅 slots 82/84/88，经验阶 2.011–2.080），但 `original_b4g_final_credit=false`、`b4g_scientific_gate_pass=false`、`new_physics_campaign_executed=false`。
- 结论：synthetic contact ≠ 真实夹爪验证；该目录证明的是「合成接触算法路线诊断 + 一次已注册并闭环的 campaign 完整性失败」，不证明任何物理接触/捕获能力。

### Q5 当前是否允许 non-ABORT？——否

- 20/20 gate `$.maximum_operational_state=ABORT_ONLY_WITH_VALIDATED_FAIL_CLOSED_BACKENDS_20_OF_20_NC__PRODUCTION_NON_ABORT_STILL_MASKED_BY_12_GATE_AUTHORITY`、`next_stage_authorized=false`（sha `4a813f2ee3b0`）。
- 接口运行时合同 `fail_closed_rule: FAIL or UNKNOWN permits ABORT only`（接口 YAML L124-130）；failure_state_registry UNKNOWN=NEVER_PASS 运行时屏蔽为 ABORT_ONLY（`15_UNIFIED_R2_SYSTEM_INTERFACE.yaml` L144-148，sha `19822080e540`）。
- 联合 gate `sim13_non_abort_operation_authorized=false`（sha `55490805d934`）。

### Q6 当前最高合法运行状态？——已更新为 20/20 后端口径（ABORT_ONLY 不变）

- 最新口径：`ABORT_ONLY_WITH_VALIDATED_FAIL_CLOSED_BACKENDS_20_OF_20_NC__PRODUCTION_NON_ABORT_STILL_MASKED_BY_12_GATE_AUTHORITY`，见 20/20 gate（`4a813f2ee3b0`）、addendum `$.backend_subscope.maximum_operational_state`（`144e09124ce2`）、联合 gate `$.diagnostic_facts_no_credit.sim13_maximum_operational_state`（`55490805d934`，该文件 2026-08-27 02:35 重算）。
- 旧口径 `ABORT_ONLY_WITH_SOURCE_ONLY_ANALYTIC_PREBIND_DIAGNOSTICS` 仍字面存在于终端父 Gate 18（`af24635327dc`）与 prebind gate（`dbfff803a656`）——未被覆盖（addendum `historical_15_of_20_superseded=false`），引用时须注明层级与时点。

### Q7 Sim13 gate 是否仍 15/20？五个后端工作单内容？intake 状态？

- 父层：18_SIM13_PREEXECUTION_GATE.json `nc_state="15/20 (NC15/NC16/NC18/NC19/NC20 dependency_hold)"` 字面未变（mtime 2026-08-25 17:51）。
- 子层：NC 注册表已真实重跑 20/20（`SIM13_V2_FULL_REGISTRY_20_OF_20_V2.json` `summary.executed=20/passed=20/failed=0/not_run_dependency_hold=0`，sha `a38f82538bf7`），三张新后端 V2 门全 PASS，包验证 10/10 + 61 pytest（`2c2ffc7a5524`）。**模式确认：CHILD_RESULT_NEWER__PARENT_GATE_NOT_REISSUED**；addendum 正式登记 `full_tmg6_reissue_executed=false`、`post_terminal_relation=APPEND_ONLY_BACKEND_SUBSCOPE_EVIDENCE`。
- 五个工作单（`SIM13_BACKEND_WORK_ORDERS_V1.json`，sha `4d169444c046`）：WO-NC15 新鲜 action/context 绑定快照回执+可信时钟+nonce+防重放 store；WO-NC16 后端 capability token+强制 shield-attestation 准入；WO-NC18 积分类非 ABORT 关节/基座/末端状态演化后端（依赖 unified URDF+接口实例）；WO-NC19 权威窄相接触后端+released contact geometry（依赖 DESIGN_CONTACT_MODEL_V1+窄相碰撞资产）；WO-NC20 action 绑定 150 kg 可行性/抓后评估回执（锚 sim10 3.0633 dps INFEASIBLE_RATE+sim12）。addendum 登记 `backend_work_orders_closed=5/5`。
- intake 两缺席路径：`CURRENT_SYSTEM_HANDOFF_INTAKE_V1.json`（sha `8e1419808aed`）`required_absent_paths` = unified URDF + 接口实例，冻结时点（08-25 11:49）`required_system_artifacts_absent=true`、`current_intake_status=HOLD_INCOMPLETE`。此后 URDF 16:16 发射、接口实例 19:59 发射——**两条缺席路径在工件层均已解决**；父 Gate 18（17:51）记录「1-of-2 resolved」时接口实例尚未发射。intake 门未重评，`HOLD_INCOMPLETE` 字面陈旧；promotion_sequence 四级（Owner 授权 URDF 执行→当前系统绑定→运行时集成→动力学…）全 `HOLD_NOT_EXECUTED`。

### Q8 v2_system_rebind verdict 与适用域

- verdict：`SIM13_V2_SOURCE_ONLY_PREBIND_IMPLEMENTATION_PASS__HISTORICAL_REGRESSION_PINNED__15_OF_20_NC_PASS__URDF_INTERFACE_OWNER_ACTION_BOUND_RUNTIME_TORQUE_DYNAMICS_CONTACT_AND_FIVE_NC_DEPENDENCY_HOLD`（`dbfff803a656`），score 25/25、owner_accepted=false、next_stage_authorized=false。
- 适用域：source-only prebind 实现正确性（合同解析、12 门只读快照、动量级自由漂浮后端、接触前检、历史锚定）。明确不适用：已绑定仿真环境、URDF/接口生成、生产动力学/接触/运行时门、训练或任何生产用途（v2 README L32-42，sha `f594afd3659e`）。
- CHILD_RESULT_NEWER__PARENT_GATE_NOT_REISSUED 模式成立，且已被 addendum 以 append-only 方式正式登记（非静默升级）。

## 2. 另查

### DT2/DT3/DT4 数字孪生成熟度出处

- `10_research/framework_convergence/numerical_twin_status.md`（sha 前 12 位 `bf783ca9dd8b`）L5：「当前最高可证成熟度：`DT2_SCOPE_LIMITED_OFFLINE_REPLAY`」；L24-26 表：DT2 局部具备（VIZ-Gate0 单文件仪表板/6 支 MP4/44 关键帧/冻结哈希，不覆盖 sim10-12/SAFE/CTRL/Wave1/ASM），DT3 未达到（无真实遥测/统一时钟/在线估计），DT4 未启动（H0-H3 未启动）。与管理默认 `HIL_AND_REALTIME_DIGITAL_TWIN=DEFER` 一致；未发现任何更晚 Owner 决定覆盖该上限。

### Sim13 与 dynamics_control_prebind_r1 的关系

- prebind_r1 是隔离诊断胶囊（README，sha `4329f39b0809`）：只做 PB-G0 权威预绑定审计 + PB-00 零控制自由漂浮诊断，不修改 Sim13。
- `PREBIND_AUTHORITY.json`（sha `e1157532605b`）：Owner 授权源 `CURRENT_CODEX_TASK_OWNER_INSTRUCTION_2026_08_26`；以哈希钉消费 unified URDF（`D84AA23C…`，与 Q2 候选一致）作 `diagnostic_system_urdf`；`maximum_claim=DIAGNOSTIC_PREBIND_PARAMETER_MAPPING_AND_PB00_CHARACTERIZATION`；禁止 RL/VLA/HIL/接触捕获 credit/Route-C 质量传播。
- 门状态：PB_G0=`PB_G0_HOLD_PARTIAL_AUTHORITY__DIAGNOSTIC_PREBIND_ONLY__NO_RELEASE_CREDIT`（sha `da2bbe1381a0`）；PB_G1=`HOLD_NOT_AUTHORIZED_BY_PB_G0__PB00_DIAGNOSTIC_CHARACTERIZATION_AVAILABLE`（sha `7ad34fcf9482`）。它不向 Sim13 让渡任何 PASS，也不被 Sim13 20/20 覆盖；两者在联合 gate 中分别作为 sim13_binding 与 dynamics/control 条件项，均未过。

## 3. 横向一致性核验（本审计复算）

- CURRENT_GATE_MATRIX_V1.csv（sha `824cdcfd1f53`，2026-08-27 02:35 重建）同时登记 sim13_preexecution（15/20，sha `AF246353…`）、sim13_20_of_20（sha `4A813F2E…`）、sim13_post_terminal_addendum（sha `144E0912…`）、r2_dynamics_control_system（sha `55490805…`）四行——索引层承认双口径并存，未做静默升级。
- addendum 24 项 source_pins 中本审计抽查复算的 8 项（父 Gate 18、handoff 17、统一接口 15、工作单、prebind gate、接口实例、发射回执、20/20 gate 及三张后端门）哈希全部逐位一致。
- 联合 gate（2026-08-27 02:35 重算）已吸收 20/20 新状态但仍 HOLD 4/13——证明「子 PASS 不升级父 Gate」规则在最新重算中被遵守。

## 4. 风险登记（详见 blockers.csv / negatives.csv）

1. 父/子口径并存：任何只引 15/20 或只引 20/20 的对外表述都失真；正确表述=「终端父 Gate 15/20 冻结未重发 + 终端后 append-only 后端子域 20/20，最高状态 ABORT_ONLY」。
2. B4G 合成接触 campaign 已注册失败（中点二阶截断缺陷）且新 campaign 未授权未执行——合成接触路线当前无 campaign 级结论可用。
3. TMC-F01（gen_urdf 运行时代码指纹不稳）未处置——正式系统 URDF 的授权执行路径仍被 fail-closed 设计正确拒绝。
4. 答辩演示若声称非 ABORT 抓取执行或真实接触捕获即越权（BLK-SIM13-08，P1）。
5. 本域无 P0_SUBMISSION_BLOCKER：比赛提交口径（OFFLINE_PHYSICS_GATED_DEMO=GO、ABORT_ONLY 陈述）不依赖本域任何未决项。

## 给综合裁决的输入

1. Sim13 最高合法运行状态=`ABORT_ONLY_WITH_VALIDATED_FAIL_CLOSED_BACKENDS_20_OF_20_NC__PRODUCTION_NON_ABORT_STILL_MASKED_BY_12_GATE_AUTHORITY`；证据：`SIM13_20_OF_20_GATE_V1.json` `$.maximum_operational_state`（sha256 `4a813f2ee3b0…`）+ addendum `$.backend_subscope.maximum_operational_state`（`144e09124ce2…`）。
2. 父 Gate 18 仍 15/20 而 NC 注册表已 20/20，父未重发：记 `CHILD_RESULT_NEWER__PARENT_GATE_NOT_REISSUED`；证据：`18_SIM13_PREEXECUTION_GATE.json` `$.nc_state`（`af24635327dc…`）vs `SIM13_V2_FULL_REGISTRY_20_OF_20_V2.json` `$.summary`（`a38f82538bf7…`）+ addendum `$.lineage.full_tmg6_reissue_executed=false`。
3. MECH_RL_SYSTEM_INTERFACE_V2 实例已存在且三方哈希钉一致（`b105766ec1f1…`，6716 B），但 `sim13_system_binding_gate_passed=false`、`owner_accepted=false`——存在性≠授权；证据：接口 YAML `$.authority.current_values` + 发射回执 `98370844b23f…`。
4. 正式 current-system URDF 不存在；现存为 `SOURCE_ONLY_BUILDER_EMISSION` 候选（sha `d84aa23ce98a…`），带已披露缺陷 TMC-F01（8 次授权 gen_urdf 尝试全被拒）；证据：`UNIFIED_R2_URDF_EXECUTION_RECEIPT_V2.json` `$.emission_class`/`$.documented_defect`（`957ca67d7bcc…`）。
5. non-ABORT 当前一律不允许：所有现行 Gate `next_stage_authorized=false`，联合 gate `sim13_non_abort_operation_authorized=false`（`55490805d934…`）；UNKNOWN→ABORT（`15_UNIFIED_R2_SYSTEM_INTERFACE.yaml` L144-148）。
6. 当前系统动力学状态演化证据=后端级（NC18，零动量约化 8-DOF，动量残差~1e-19），生产力矩驱动动力学=HOLD_NOT_IMPLEMENTED_OR_AUTHORIZED；证据：`SIM13_DYNAMICS_BACKEND_GATE_V2.json`（`bc02c02b75c0…`）+ v3 gate `$.gates[DYN-G02]`（`a657d015ba5e…`）。
7. 权威窄相接触=合同包络级 BOUNDED_PROVISIONAL（派生非实测几何），真实夹爪验证缺席；v4 合成接触链含已注册失败（B4G invalidated，机理=中点二阶截断缺陷），无 campaign 级结论；证据：`SIM13_CONTACT_GRASP_GATE_V2.json`（`f13b755ea0b3…`）+ `SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json`（`2743fbd314cc…`）+ R1 闭环门（`ae7e81f66cf6…`）。
8. 五个后端工作单 WO-NC15/16/18/19/20 子域 5/5 闭合，但 after_20_of_20 尾序（handoff V2 重跑+接口正式化）未闭环；证据：`SIM13_BACKEND_WORK_ORDERS_V1.json` `$.work_orders`/`$.after_20_of_20`（`4d169444c046…`）+ addendum `$.backend_subscope.backend_work_orders_closed=5/5`。
9. 数字孪生成熟度上限=DT2_SCOPE_LIMITED_OFFLINE_REPLAY（局部历史），DT3/DT4 未达到/未启动；证据：`numerical_twin_status.md` L5/L24-26（`bf783ca9dd8b…`），与管理默认 HIL_AND_REALTIME_DIGITAL_TWIN=DEFER 一致。
10. 本域 P0=0、P1=1（演示叙事越权风险）、P2=7（绑定门/接口正式化/NC18 生产化/NC19 物理化/工作单尾序/Owner 接受/G12 线束包络）、P3=2（DT3/DT4、RL/VLA）；证据：本 fragment `blockers.csv` 全表。
