# 具身智能/感知/HIL 域只读当前状态审计（分片 embodied）

- 审计日期：2026-08-27（本地）；比赛硬截止 2026-09-01。
- 范围：感知、具身智能、HIL/数字孪生侧证据。Sim13 内部 gate 数值的正式裁决归 sim13 分片，本分片只引用其路径与字段，不重复裁决。
- **授权覆盖记录**：本目录 `90_competition_closeout/20260827_current_state_audit/fragments/embodied/` 下的 5 个 fragment 文件由用户在本任务中显式授权创建，优先于 `AGENTS.md`（sha256 前 12 位 `3d2269562678`，L6-L9 REORG04）的根目录八域限制；本分片未对其他任何文件做写操作。

## 0. 域状态一句话

具身智能域当前**只有合同/规划层资产与离线回放演示是实的**（机器 Gate 或冻结合同可查），**感知前端、状态估计器、VLA、Physics Tool 服务、HIL、DT3/DT4 全部无实现证据**；「具身智能」作为**架构贡献**（候选—物理—SAFE—控制分层、VLA 无直接力矩权限）证据成立，作为**已验证系统能力**不成立。

## 1. 已实现/已冻结证据（机器可核查）

1. **比赛离线物理门控演示已就绪**：`10_research/competition_convergence/competition_gate_check.json`（`8b3cdbdaa09e`）`checks_passed=17/checks_total=17`、`final_verdict=COMPETITION_DEMO_READY`；同 JSON `command_emitted=false`、`real_time_synchronization=false`、`offline_replay=true`、`scenario_actions={A_low:EXECUTE, B_anchor:ABORT, C_transition:MODIFY}`、`stop_rules.start_hil=false`、`stop_rules.start_vla=false`。证明 OFFLINE_PHYSICS_GATED_DEMO=GO；同时证明其边界是离线解释性回放。
2. **Sim13 V2 源级预绑定通过但硬锁 ABORT**：`30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/results/SIM13_V2_PREBIND_SOURCE_GATE_V1.json`（`dbfff803a656`）`prebind_source_implementation_passed=true`、`score=25/25`、`maximum_current_operational_state=ABORT_ONLY_WITH_SOURCE_ONLY_ANALYTIC_PREBIND_DIAGNOSTICS`、`formal_negative_controls=15/20（NC15/16/18/19/20 dependency_hold）`、`next_stage_authorized=false`、`owner_accepted=false`。source-only PASS ≠ current-system PASS。
3. **V4 运行时防护诊断（token/capability/握手侧唯一实跑证据，仅合成）**：`.../v4_runtime_guard_diagnostic/results/SIM13_V4_RUNTIME_GUARD_DIAGNOSTIC_GATE_V1.json`（`104d6d25d1c4`）`diagnostic_gate_passed=true`、`scope=SYNTHETIC_PREBIND_DIAGNOSTIC_ONLY`、`score=25/25`；NC15（nonce 单次消费/绑定漂移→ABORT）、NC16（coordinator 一次性 opaque invocation，直调后端精确拒绝）、NC18（合成 6R+2P 经唯一 coordinator 的真实数值变化）、NC20（sim10 四工件 SHA 绑定+150kg@3°/s 预 veto）=`PASS_DIAGNOSTIC_LOGIC_ONLY`；`formal_v2_negative_controls` 仍 `passed=15/declared=20`、`unchanged_by_v4=true`，NC19 `NOT_EXECUTED`。synthetic contact ≠ 真实夹爪验证。
4. **当前系统交接 intake 源冻结通过、intake 本身 HOLD**：`.../current_system_handoff_intake_v1/results/CURRENT_SYSTEM_HANDOFF_INTAKE_SOURCE_FREEZE_GATE_V1.json`（`23903c1af1a6`）`overall_status=PASS_SOURCE_FREEZE_ONLY`、`current_intake_status=HOLD_INCOMPLETE`、`flags.interface_instantiated=false`、`flags.current_system_bound=false`；`preserved_hard_negatives` 保留 e15=`REPEAT_ANCF_CERTIFICATION`（0.05637349419858036>5%）、harness G12 FAIL（11/12）、route_c_physical_registry 0/13 可用。`v2_system_rebind/interfaces/MECH_RL_SYSTEM_INTERFACE_V2.yaml`（`b105766ec1f1`）存在但仅为源冻结候选。
5. **子模块 20/20 与父 Gate 15/20 并存（CHILD_RESULT_NEWER__PARENT_GATE_NOT_REISSUED）**：`.../runtime_fail_closed_backends_v2/results/SIM13_20_OF_20_GATE_V1.json`（`4a813f2ee3b0`，mtime 2026-08-25T10:56:52Z）`gate_passed=true`、`nc_score=20/20`、NC01–NC20 全 `PASS_NEGATIVE_CONTROL_DETECTED`，但 `review_status=PENDING_OWNER_REVIEW`、`next_stage_authorized=false`、`maximum_operational_state=ABORT_ONLY...`、`release_credit=false`；父 prebind gate（`dbfff803a656`，同日 11:09:48Z）与 `AGENTS.md` L39（`3d2269562678`）仍记 15/20。按铁律只登记差异，不升级为父 Gate PASS；正式裁决归 sim13 分片。

## 2. 架构/合同层资产（非实现）

6. **Physics-Gated Agent 仅规划冻结**：`10_research/space_embodied_robotics/physics_gated_agent_plan.md`（`ecba24564e55`）L5-L8 水印 `PLANNING_COMPLETE_NO_IMPLEMENTATION`/`NO_NEW_EXECUTION_AUTHORITY`；§2 E/C/P/S 图；§5 表：`Physics Foundation Model` 被拒（`REJECTED_AS_PREMATURE_LABEL`）、Isaac/MuJoCo/ROS2 搭建 `DEFERRED_TOOL_EVALUATION`、SAFE 扩展 `DEFERRED_TO_SEPARATE_CONTRACT`。
7. **Embodied Agent V1 合同 + 五 schema 落盘、验收未跑**：`10_research/space_embodied_robotics/space_embodied_agent_v1_contract.md`（`3d949b26caf8`）状态头 `PROTOTYPE_CONTRACT_ONLY`、`SCIENTIFIC_GATE=false`、`EXECUTION_AUTHORITY=false`；§1.1 三项创新点自声明为「设计创新点，不是已验证系统能力」。`20_engineering/config/competition_prototype/prototype_acceptance.yaml`（`8214139674a9`）`acceptance_kind=DOCUMENT_AND_SCHEMA_ONLY`、`evaluation_record.status=PLANNED`。五 schema（envelope `d0b436bdfe60`、candidate `2184bc6a3e61`、skill `a7f145b05f5e`、physics_response `12c43c7e2a32`、memory `ff255105c988`）均 `contract_status=PROTOTYPE_CONTRACT`。
8. **Physics Tool 只有草案**：`10_research/vla/tool_contract_draft.yaml`（`b8f130d578b2`）L8 `status: DRAFT_NOT_IMPLEMENTED`；五工具定义齐全但无服务端实现。旧草案冲突未收敛（physics_gated_agent_plan §3.2：`DRAFT_CONFLICTS_OPEN_NOT_IMPLEMENTED`）。
9. **VLA 只有预注册式协议**：`10_research/vla/vla_generalization_plan.md`（`169cb1f05b33`）L3 `PROTOCOL_DRAFT（未实现、未采数、未训练）`；§2 V0–V3 四基线、§4 七组轴（含 G-E 遮挡、G-F 延迟）、§5 M1–M8、§8 阻塞表（渲染管线 NOT_STARTED）。确定性候选器 vs VLA 成组对照无任何实跑。
10. **数字身体方法为方法合同**：`10_research/space_embodied_robotics/comp_prot_03_a3_g0_digital_body_method/README.md`（`98fed05581e9`）`DIGITAL_BODY_METHOD_CONTRACT_ONLY`、`CAD_URDF_SIMULATION_AUTHORIZED=false`。
11. **两个 agent 文件是治理/导航，不是实现**：`.codex/agents/space-embodied-intelligence-research-agent.toml`（`58432426011a`）与同名 `.md`（`5d8780878956`）自述 `PLANNING_AND_EVIDENCE_ROUTING_ONLY`，硬边界含「不实现 VLA、Physics Tool、装配、数字孪生、HIL、RL 或控制器」。**注意**：其 Startup #3 与 `AGENTS.md` L13 引用的 `10_research/knowledge_base/physics_agent/README.md` **不存在**（2026-08-27 `find 10_research -iname '*physics_agent*'` 零匹配）——记 UNKNOWN 缺口（BLK-E07）。

## 3. 决策问题 13：当前最高数字孪生成熟度

**结论：`DT2_SCOPE_LIMITED_OFFLINE_REPLAY`，与预期一致。** 出处：`10_research/00_project_architecture/digital_twin_plan.md`（`64e88a4db0c6`）L7-L13「当前最高允许称为 DT2_SCOPE_LIMITED_OFFLINE_REPLAY」+ DT0–DT4 表（DT3=`BLOCKED` 未实现未启动、DT4=`BLOCKED`）；`10_research/research_questions/Q5_digital_twin.md`（`358fa65552e6`）L9 裁决 `LIMITED_DT2_AND_BLOCKED_UPGRADE`；`mission_demo_contract.yaml`（`28cdc815093e`）`scope: DT2_CURRENT_SCOPE_OFFLINE_EVIDENCE_REPLAY` 与 `replay_mode: OFFLINE_DETERMINISTIC`。本地另有 `LOCAL_ONLY_UNTRACKED` 三场景回放 Gate（digital_twin_plan L18-L19、DT2 资产表）。

## 4. 决策问题 14：是否已有 感知→候选→物理→SAFE→控制 完整闭环

**结论：否。逐项缺失清单（均有直接证据）：**

- **状态估计器/位姿估计器：不存在**。`sim_13` 现行环境 `config/sim13_bootstrap.json`（`4624c5ba2a01`）`observation_mode=state_based`；`src/observation.py`（`fafb189460bf`）L24-L60 观测由后端状态真值直读（target 相对位姿/角速度直接来自 `BackendState`），无相机、无协方差、无噪声、无遮挡；`flexible_modes=INTERFACE_ONLY_UNKNOWN`、`joint_limit_margin=UNKNOWN_NO_LIMIT_BINDING_IN_BOOTSTRAP`；`results/README.md`（`4cc9fac52198`）确认无 RL 训练结果。
- **camera frame 合同：占位且 HOLD**。`20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/02_interfaces/SYSTEM_FRAME_TREE.yaml`（`71a9fffaa30a`）L87-L90 `camera_optical_frame: transform=TBD — MANUFACTURING OR FLIGHT AUTHORITY REQUIRED, status=HOLD_CAMERA_SELECTION_AND_CALIBRATION`；committed `20_engineering/config/geometry/frame_tree_v1.yaml`（`958bff23bf83`）grep camera/optical 零命中。
- **候选生成器基准（确定性 vs VLA 成组对照）：只有协议**。vla_generalization_plan §2/§4（`169cb1f05b33`）；无渲染管线、无数据集（`PROJECT_CURRENT_STATUS.md`（`cce6517b4cd5`）DATASET 行 `NOT_STARTED`）。
- **typed tool contract 实跑：无**。工具合约 `DRAFT_NOT_IMPLEMENTED`（`b8f130d578b2` L8）；tool call/token 握手侧唯一实跑是 V4 合成诊断（`104d6d25d1c4`），scope 限 SYNTHETIC_PREBIND_DIAGNOSTIC_ONLY，且 NC15 nonce 不跨进程/重载持久（formal HOLD）。
- **实时 SAFE 集成：无**。冻结 SAFE-00 不覆盖新信封/新候选，扩展 `SEPARATE_EXTENSION_REQUIRED_NOT_AUTHORIZED`（physics_gated_agent_plan §3.3，`ecba24564e55`）；比赛回放中 SAFE 仅以冻结工件离线绑定（mission_demo_contract artifact_registry.safe_gate，`28cdc815093e`）。
- **HIL：无**（见下节）。
- ** Isaac/MuJoCo scene、fixed-base/free-floating 试验、B601 driver、F/T sensor、低摩擦平台、hardware communication、real-time loop：仓库内均无实现证据**；相关词命中仅在文献阅读卡（如 `50_literature/references/notes/alali2024hiltestbed.md`）与冻结计划文档。

## 5. 决策问题 15：是否已有 HIL

**结论：否，且为机器登记的停止态。** `competition_gate_check.json`（`8b3cdbdaa09e`）`hardware_component_status={H0:NOT_STARTED_BLOCKED_BY_MISSING_HAG_E, H1:NOT_STARTED_BLOCKED_BY_H0, H2:NOT_STARTED_BLOCKED_BY_H1_AND_ESTIMATOR_GATE, B601_MOTION:PROHIBITED}`、`stop_rules.start_hil=false`；`hardware_component_plan.md`（`8d4efc4963a4`）L6-L9 `FROZEN_PLAN_ONLY / NOT_EXECUTED`、L44-L51 `H3/HIL/VLA: NOT_AUTHORIZED`、L19 记 `HAG-E.yaml` 不存在（本分片 2026-08-27 核实 `10_research/on_orbit_assembly/approvals/` 目录缺失）。无 H0/H1/H2 Gate JSON，按文件自身规则禁止合成空 PASS。

## 6. 「具身智能」架构贡献的证据成立性

**成立（架构/合同口径）**：分层（感知信封→候选包→Physics Tool 四值→SAFE 五值→外部授权）在 space_embodied_agent_v1_contract.md §2/§3（`3d949b26caf8`）与 physics_gated_agent_plan §2/§4（`ecba24564e55`）双重冻结；「VLA 无直接力矩权限」在 candidate_bundle.schema.json（`2184bc6a3e61`，结构上排除轨迹/力矩/SAFE 决策/执行授权）、vla_generalization_plan §1 L5 红线（`169cb1f05b33`）与 `.codex/AGENTS.md` 红线（`af8f80d70b3e`，禁止端到端 VLA 控制）三层一致；文献查新绿线含「embodied candidate + independent physics veto」（`AGENTS.md` L43，`3d2269562678`）。**不成立的口径**：任何「已实现/已验证具身智能闭环」——四条禁止主张已机器登记（prototype_acceptance.yaml `forbidden_claims`，`8214139674a9`）。

## 7. E-COMP-05 最小感知接口盘点（E-COMP-05 为审计自定义编号，仓内 grep 零命中）

**现存资产**：envelope schema 含 pose+6x6 协方差+`covariance_status`+`valid_until`（预测有效期）+`perception_branch` U0–U4（含 U3 部分观测）+`ood`+fail-closed 品质降级（`d0b436bdfe60`）；失效语义表（过期→WAIT/ABORT）见 servicing_to_assembly_transition.md §4.2（`1edd2559e6c9`）；`FAIL_CLOSED_HOLD` 状态入 skill_contract schema（`a7f145b05f5e`）；失效 ABORT 的可用裁决核为冻结 SAFE-00（经 mission_demo_contract 哈希绑定，`28cdc815093e`）；结构化技能词表 Level0×6/Level1×5 已唯一化。
**缺失**：记录/合成目标位姿序列生成器、协方差实际数据源、短时遮挡注入、失效→ABORT 的实跑演示、对应机器 Gate、相机系（HOLD）、估计器（不存在）。**处置二选一**（BLK-E01）：标题保留「具身智能」→P1，内部可用 HARNESS_TRUTH 合成序列+遮挡注入离线驱动 SAFE-00 fail-closed 演示并立 Gate；标题收窄→降 P3。

## 8. 本分片 P0 评估

本域**无 P0_SUBMISSION_BLOCKER**：提交合规链（competition gate 17/17、离线演示、PPT/视频包）已在 `8b3cdbdaa09e` 中 PASS 且不依赖具身层任何未实现项；具身层风险全部落在决赛叙事强度（P1）与正式 Release/赛后研究（P2/P3）。

## 给综合裁决的输入

1. 数字孪生成熟度封顶 `DT2_SCOPE_LIMITED_OFFLINE_REPLAY`：`digital_twin_plan.md` L7-L13（`64e88a4db0c6`）+ Q5_digital_twin.md L9（`358fa65552e6`）；DT3/DT4=BLOCKED。
2. 比赛演示=离线确定性回放且机器锁定：`competition_gate_check.json` `final_verdict=COMPETITION_DEMO_READY`、`command_emitted=false`、`stop_rules.start_hil/start_vla=false`（`8b3cdbdaa09e`）。
3. 感知→候选→物理→SAFE→控制闭环不存在：估计器缺失（`sim13_bootstrap.json` `observation_mode=state_based`，`4624c5ba2a01`；observation.py L24-L60，`fafb189460bf`）、相机系 HOLD（SYSTEM_FRAME_TREE.yaml L87-L90，`71a9fffaa30a`）、工具草案未实现（tool_contract_draft.yaml L8，`b8f130d578b2`）、SAFE 扩展未授权（physics_gated_agent_plan §3.3，`ecba24564e55`）。
4. HIL=NOT_STARTED：`competition_gate_check.json` `hardware_component_status` 四字段 + `stop_rules.start_hil=false`（`8b3cdbdaa09e`）；HAG-E 授权缺失（approvals 目录不存在，2026-08-27 核实）。
5. 具身智能架构贡献证据成立（合同级）：space_embodied_agent_v1_contract.md §1.1/§2/§3（`3d949b26caf8`）+ 五 schema PROTOTYPE_CONTRACT + 禁止主张四条已登记（prototype_acceptance.yaml `8214139674a9`）；系统能力口径不成立。
6. Sim13 侧口径冲突待 sim13 分片裁决：子 20/20（SIM13_20_OF_20_GATE_V1.json，`4a813f2ee3b0`，PENDING_OWNER_REVIEW、next=false）vs 父 15/20（SIM13_V2_PREBIND_SOURCE_GATE_V1.json，`dbfff803a656`；AGENTS.md L39）→ `CHILD_RESULT_NEWER__PARENT_GATE_NOT_REISSUED`，引用须带限定。
7. typed tool/token 握手唯一实跑为 V4 合成诊断（SIM13_V4_RUNTIME_GUARD_DIAGNOSTIC_GATE_V1.json，`104d6d25d1c4`，scope=SYNTHETIC_PREBIND_DIAGNOSTIC_ONLY，formal NC 15/20 不变）——不得当作当前系统运行时证据。
8. E-COMP-05（审计编号）处置分支：标题保留具身智能→P1（缺序列生成/遮挡注入/失效 ABORT 实跑/Gate；合同载体已齐）；标题收窄→P3（BLK-E01）。
9. 治理缺口：`10_research/knowledge_base/physics_agent/README.md` 被 AGENTS.md L13 与 agent Startup#3 引用但文件不存在（find 零匹配）→ UNKNOWN，建议补建或修正引用（BLK-E07，P2）。
10. Sim13 V1 已降级历史 bootstrap（README L3-L21，`e7fa21a26808`），任何材料不得引用 V1 为现行具身能力。
