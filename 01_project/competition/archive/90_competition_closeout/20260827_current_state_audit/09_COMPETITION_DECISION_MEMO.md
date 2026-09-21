# 09 比赛决策备忘录（COMPETITION_DECISION_MEMO）

- 生成日期：2026-08-27（本地）；生成者：综合代理 SYN-C（叙事与计划类交付）；输入：7 个只读审计分片（mech/dyn/ctrl/sim13/embodied/compdeliv/memory）的 fragments。
- 性质：本备忘录不签发任何 Gate、不修改任何源码/CAD/仿真；全部状态引用均来自既有机器裁决 JSON 或冻结文档，证据指针格式为「路径 + JSON key/行定位 + sha256 前 12 位」。
- 铁律适用：子 PASS 不升级父 Gate；UNKNOWN≠EXECUTE；source-only≠current-system；模块 PASS≠执行授权；本备忘录不删除、不淡化任何 REPEAT/HOLD/负结果。

## 机器可读状态头（逐条经 fragments 证据核实，见 §0 核实记录）

```
COMPETITION_SUBMISSION = CONDITIONAL_GO
COMPETITION_SCOPE = 物理约束抓捕策略选择与失效闭合安全验证（离线、确定性重放、受限任务包络）
MECHANICAL_MAIN_BODY = FROZEN
ACTIVE_MECHANICAL_WORK = ROUTE_C_ONLY（V9F 已被 M01 负见证终局否决、ODR-60 Option A 预搜索 fail-closed；维持 KNOWN HOLD，不入正式 SSOT）
DYNAMICS_CONTROL_PREBIND = GO
FORMAL_MECHANICAL_RELEASE = HOLD（00_RELEASE_GATE.json：TERMINAL_CLOSURE_EXECUTED__GATE_A_NOT_PASSED…NO_RELEASE_CREDIT）
FORMAL_CONTROL_RELEASE = HOLD（CTRL-01 REPEAT；CTRL-02 PASS_WITH_PROVISIONAL_SCOPE+PENDING_REVIEW；联合 Gate 4/13）
SIM13_CURRENT_SYSTEM = ABORT_ONLY（ABORT_ONLY_WITH_VALIDATED_FAIL_CLOSED_BACKENDS_20_OF_20_NC__PRODUCTION_NON_ABORT_STILL_MASKED_BY_12_GATE_AUTHORITY）
OFFLINE_DEMO = REPEAT（17/17 资产在且哈希自洽，但口径冻结于 07-20、REORG04 哈希漂移未闭环，须当前树重验证）
PHYSICAL_DEMONSTRATOR = UNKNOWN（2026 官方要求仓内缺席）
REPORT = HOLD（比赛技术报告母稿不存在，须从零建立）
VIDEO = REPEAT（07-20 媒体在，需按当前状态核对/重渲染）
SUBMISSION_PACKAGE = INCOMPLETE（无包/无恢复演练/无回执；HEAD 停在 2026-08-08、130 untracked 未锚定）
```

## §0 状态头逐条核实记录（含修正/加注理由）

| 状态行 | 核实结论 | 证据指针 |
|---|---|---|
| COMPETITION_SUBMISSION = CONDITIONAL_GO | 成立（综合裁决）：无一分片报告 P0 之外的提交阻断被证伪；P0 七项全部可识别且四项解除条件可在 8-31 前闭合（见 §b/§c） | 各分片 findings.md「本域无 P0」段 + compdeliv `blockers.csv` B-CD01..05、memory `blockers.csv` BLK-MEM-01/02 |
| COMPETITION_SCOPE | 成立：与查新绿线五项及五锚点证据一致（见 Q1/Q2） | `01_project/competition/文献查新裁决_claim边界_20260823.md` §3（sha256 `3be39f02c15a`）；`30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json` `$.gates.GS2/GS3`（`a416c1348111`） |
| MECHANICAL_MAIN_BODY = FROZEN | 成立 | `01_project/competition/Route_C终局Owner系统边界决策包_20260826.md`（`9e9a4156c80f`）+ memory fragment §7 管理默认核实（未发现更晚 Owner 覆盖） |
| ACTIVE_MECHANICAL_WORK = ROUTE_C_ONLY | 成立 | V9F 终局否决：`20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_V9F_MANDATORY_M01_FALSIFIER_GATE.json`（`09c3199bd982`）+ `ROUTE_C_V9F_TERMINAL_RULING.json`（`09611ddb8adc`）；ODR-60 预搜索 fail-closed：`_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/results/ODR60_OPTION_A_EXECUTION_CLOSURE_GATE_V1.json` blockers 8 项（`869a248050fd`） |
| DYNAMICS_CONTROL_PREBIND = GO | **成立但须加注**：GO 仅限诊断性 prebind 工作线（无 release credit）——`PREBIND_AUTHORITY.json` `$.maximum_claim=DIAGNOSTIC_PREBIND_PARAMETER_MAPPING_AND_PB00_CHARACTERIZATION`（sha256 `e1157532605b`）、`PB_G0_GATE.json` verdict `PB_G0_HOLD_PARTIAL_AUTHORITY__DIAGNOSTIC_PREBIND_ONLY__NO_RELEASE_CREDIT`（`da2bbe1381a0`）。若被读作「动力学-控制正式绑定已放行」则为误读 | 同上两个文件 |
| FORMAL_MECHANICAL_RELEASE = HOLD | 成立（SYN-C 独立复算一致） | `20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/00_RELEASE_GATE.json` `$.verdict/gate_a_pass/review_status/next_stage_authorized/release_credit`（`14d30fd40ac6`） |
| FORMAL_CONTROL_RELEASE = HOLD | 成立 | CTRL-01 `$.verdict="REPEAT"`（`30_simulation/control_01_end_effector_tracking/results/control_01_gate_check.json`，`ab1fd26978f4`）；CTRL-02 `$.verdict="PASS"`+`$.review_status="PENDING_REVIEW"`（`30_simulation/control_02_base_attitude/results/control_02_gate_check.json`，`240fa708b536`）；联合 Gate 13 条件仅 4 真：`30_simulation/r2_dynamics_control_system_closure/results/R2_DYNAMICS_CONTROL_SYSTEM_GATE_V1.json`（`55490805d934`）+ 父裁决 §5（`01_project/competition/R2动力学与控制工程闭环阶段裁决_20260827.md`，`3eed50dd728e`） |
| SIM13_CURRENT_SYSTEM = ABORT_ONLY | 成立（SYN-C 独立复算逐字一致） | `30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_20_OF_20_GATE_V1.json` `$.maximum_operational_state`（`4a813f2ee3b0`） |
| OFFLINE_DEMO = REPEAT | 成立：17/17 与媒体字节一致性已核实；REPEAT 定性来自 07-20 口径冻结 + REORG04 重放文件哈希漂移未闭环 | `10_research/competition_convergence/competition_gate_check.json` `$.final_verdict/checks_passed`（`8b3cdbdaa09e`）；漂移证据见 ctrl fragment §五（replay_manifest 记录值 `438f2697…` vs 当前 `255eddaf…`）与 compdeliv B-CD08 |
| PHYSICAL_DEMONSTRATOR = UNKNOWN | 成立 | compdeliv fragment §A：2026 官方文件仓内零命中；唯一格式描述在归档文件 `01_project/competition/archive/项目现状总览_20260715.md` 第 11 行（`e65cf431ba00`，被 `AGENTS.md` 第 14 行禁作现行依据，`3d2269562678`） |
| REPORT = HOLD | 成立 | compdeliv fragment §B.2.1：仓内无比赛报告书 tex/docx/pdf；`10_research/paper1_architecture.md`（`6df2bec70a72`）为期刊论文架构非比赛报告书 |
| VIDEO = REPEAT | 成立 | mp4 存在且与 manifest 逐字节一致：`40_evidence/artifacts/competition_convergence/competition_mission_intelligence_demo.mp4`（`7043d026cef6`，1,572,615 B）对 `evidence_asset_manifest.json`（`33b7bfbf8682`）；口径冻结 07-20 |
| SUBMISSION_PACKAGE = INCOMPLETE | 成立（SYN-C 独立复算一致） | `git rev-parse HEAD`=`5c5addea00dd…`、`git log -1 --format=%ci`=`2026-08-08 01:24:43 +0800`、`git status --short`=141 条（11 M+130 ??）、`git remote -v` 空（compdeliv fragment §C.1/C.2） |

---

## §a 二十个决策问题逐条回答

**Q1 唯一科学主问题是什么？**
仓内三版本并存、未收敛：表述 A「面向抓取后可稳定性的预见式具身抓取」（`AGENTS.md` 第 4 行，`3d2269562678`）；表述 B「物理约束空间具身任务智能（捕获任务智能→装配闭环）」（`01_project/competition/项目现状总览_20260720.md` 第 3-4 行，`184cacb060fc`，其第 13 行确认比赛链不依赖装配 Wave A）；表述 C 项目总标题（`01_project/competition/研究战略裁决_第二收敛点_20260717.md` §2.3 第 75-77 行，`ced773571d74`，文首自声明状态过期）。**综合建议收敛表述**：在受限任务包络内，对翻滚非合作目标抓捕候选给出 EXECUTE/MODIFY/ABORT 裁决的物理约束策略选择问题（决策层+可行域），证据见 Q2 锚点 1/2。须 Owner 一次选定（BLK-MEM-03，P1）。

**Q2 五项最强创新（全部机器可核）**
1. **Binding-gate 策略选择**：`sim_12_gate_check.json` `$.gates.GS2_differentiation.best_per_case`（A_low→S1_passive、B_anchor→ABORT、C_transition→S3a_wheel_bias、D_extreme→ABORT）与 `$.gates.GS3_claim_audit.allowed[0]`（`a416c1348111`）。
2. **多门失效闭合任务可行域**：`10_research/framework_convergence/claim_evidence_matrix.csv` C13 行（`7d296e7a2437`）：9002 物理点、`SIM10_GATES_PASS`、6323 wheels-only/1858 rate/730 thruster/91 resource；底层 `sim_10_gate_check.json` `$.verdict`（`4dbd8c91ff34`）。
3. **局部冲量改善可恶化全局角动量（反直觉反例）**：`sim_12_gate_check.json` `$.gates.GS3_claim_audit.allowed[1]/forbidden[0]`（`a416c1348111`）；`|ΔH_vec|`=1.43508 N·m·s（矢量）与 |H| 标量 +0.873 分账见 `10_research/sim_12/momentum_ledger.md` 第 30 行（`77e34aff3e28`）。
4. **候选—物理评价—SAFE—传统控制的分层架构（合同级）**：`10_research/on_orbit_assembly/dual_mission_literature_synthesis.md` §2/§5.4（`88118670c35d`）；SAFE-00 47/47 且 unknown_allow=0/bypass_success=0（`safety_00_gate_check.json` `$.metrics`，`ff56929dd835`）。
5. **负结果与 UNKNOWN 的机器可审计治理**：`10_research/contribution_map/paper1_contribution_map.md` C4 段第 48-59 行（`3453adfe30e7`）；`wave1_cp6_ruling.md` 第 16-17 行 `WAVE1_REPEAT` 原样入档（`1eeea3ccffb1`）。

**Q3 哪些内容只能作 baseline-only？**
查新红线六篇（禁作核心创新，只作 baseline/工具层）：Wang 2026 momentum feedforward（实验数字 96%/94% 未核验禁引用）、Lu 2026 一体化框架声称禁用、Ma 2026 视觉+RL 自主抓取（全文已读）、Cai 2026 data-driven post-capture MPC（方向整体放弃）、Mao 2026 Koopman/model-free、AA 246:734-744 RL detumbling——出处 `文献查新裁决_claim边界_20260823.md` §1/§2（`3be39f02c15a`）与 `AGENTS.md` 第 42 行（`3d2269562678`）。另有 momentum prebias=S3a 仅作候选策略类（C1 Dimitrov 2004 祖先线），禁包装成「新抓捕方法」（同裁决 §2 表 row1 + `AGENTS.md` 第 44 行）。

**Q4 机械 Release 是否成立？——不成立。**
`00_RELEASE_GATE.json`：`$.verdict="TERMINAL_CLOSURE_EXECUTED__GATE_A_NOT_PASSED__TMG4_TM6_INTERNAL_BLOCKERS_REGISTERED__NO_RELEASE_CREDIT"`、`$.gate_a_pass=false`、`$.review_status="PENDING_OWNER_REVIEW"`、`$.release_credit=false`（`14d30fd40ac6`）。TMG-4 HOLD、TMG-6 FAIL_15_OF_20；2026-08-26 V9F 终局裁决未改写该 Gate（`ROUTE_C_V9F_TERMINAL_RULING.json` `$.governing_records.historical_release_gate_preserved.modified_by_this_ruling=false`，`09611ddb8adc`）。

**Q5 Checkpoint-A/B/C 状态？**
- A（Full-Flex/e23）：历史态 HOLD 6/12 冻结于 `TERMINAL_DECISION_PACK_GATE_V1.json` `$.checkpoint_state.A_R2_FULL_FLEX`（`0c9dc0353630`）；现行闭合经 Round4 V3 17/17 + E23 18/18，父 Gate TMG-5 入账 `PASS_WITH_DECLARED_PROVISIONAL_PHYSICS`（`13_R2_FLEX_MODEL.yaml` `e23_recertification` 节，`8cadf790cf6a`；E23 gate `$.technical_verdict/summary`，`1ad4993fd9df`）。
- B（Route-C C2 准入）：保持 HOLD 2/8（仅 C2-ADM-01/07 PASS），注册表 13/13 null，`ROUTE_C_CAD_AUTHORIZED=false`（`ROUTE_C_CHECKPOINT_B_GATE_V1.json`，`c9e7526d790e`）；后续 RC-2/RC-3 由 Owner 指令放行（`ROUTE_C_PHYSICAL_INPUT_GATE_V1.json` `route_c_rc2_rc3_entry="ALLOWED_BY_OWNER_DIRECTIVE_A1"`，`f5016c3a6f82`），终局结果为负。
- C（终局 Release）：从未到达（`checkpoint_state.C_TERMINAL_RELEASE: reached=false`）。

**Q6 Route-C 哪些参数是 null/HOLD？**
P01–P13 已全部闭环但权威等级仅 DESIGN_CANDIDATE/PROVISIONAL_DERIVED/BOUNDED_DATASHEET_RANGE：**P08=null**（恢复力矩曲线 UNKNOWN 未零填）、**P10=null**（[0.06,0.20] 数据表区间）、**P11=null**（[50,63]）；P06=50.0 mm(LOW)、P09=65.0 [56.5,72.5] g/m(LOW)；MPI-01..04 电气输入未闭合。出处 `ROUTE_C_PHYSICAL_CAPABILITY_REGISTRY_V2.yaml`（`1e70d6f95141`）+ mech `blockers.csv` BLK-MECH-01/02/03。E_HRN 机器真值：`B601_HARNESS_RATED_ENVELOPE_V1.yaml` `E_HRN.sample_counts SAFE 0/UNSAFE 75`（`a63a93de5b6b`）、`mandatory_key_state_probe states_safe 0/states_unsafe 11`；任务覆盖 `B601_HARNESS_MISSION_COVERAGE_GATE.json` 10/10 强制任务态 UNSAFE（`f3b444222e87`）——三个分母（75/11/10）不得混写。

**Q7 handoff 是否 12/12？——否，11/12，G12 失败。**
`MECHANICAL_TO_EMBODIED_HANDOFF_GATE_V2.json` `$.checks_total=12/checks_passed=11/failing_checks=["G12"]`（`13722965d5c5`）；G12 失败因 `mission_coverage_pass=false`、`map_contains_safe_sample=false`（SAFE 0/75）。终端侧 `17_MECH_TO_EMBODIED_HANDOFF_GATE.json` 确认统一接口重跑仍失败（`42792057bd9f`）。

**Q8 accepted URDF 是否被 CAD 质量覆盖？——否。**
`05_ACCEPTED_B601_URDF_REF.yaml`：`modification: FORBIDDEN`、`cad_mass_or_geometry_override_of_accepted_urdf: FORBIDDEN`（`6912f7d547b8`）；总质量 31.022864807342987 kg 出自 accepted URDF 惯性账本精确合计（`20_RED_TEAM.json` RT-04 evidence，`f3981655c383`）；`07_SYSTEM_MASS_PROPERTIES.yaml` 中 V3 R2 设计质量标 CANDIDATE_ONLY_NOT_AS_BUILT，as-built 为 HOLD_EXTERNAL_MEASUREMENT_PENDING。

**Q9 Unified R2 是否已生成正式当前系统 URDF？——否。**
现存为 SOURCE_ONLY 发射候选：`unified_r2_c01_no_route_c_sim_candidate_v2.urdf`（sha256 前 12 `d84aa23ce98a`），发射类别 `SOURCE_ONLY_BUILDER_EMISSION__NOT_GEN_URDF_AUTHORITY_EXECUTION`（`UNIFIED_R2_URDF_EXECUTION_RECEIPT_V2.json` `$.emission_class`，`957ca67d7bcc`）；gen_urdf 8 次授权执行均被 fail-closed 终检拒绝（缺陷 TMC-F01：CPython 3.13.9/3.14.4 下 marshal 运行码指纹不稳）。prebind gate `$.system_urdf_available=false`（`dbfff803a656`）为 08-24 冻结时点字面状态，属字段陈旧而非矛盾。

**Q10 Sim13 是否允许 non-ABORT？——否。**
`SIM13_20_OF_20_GATE_V1.json` `$.maximum_operational_state=ABORT_ONLY_WITH_VALIDATED_FAIL_CLOSED_BACKENDS_20_OF_20_NC__PRODUCTION_NON_ABORT_STILL_MASKED_BY_12_GATE_AUTHORITY`、`$.next_stage_authorized=false`（`4a813f2ee3b0`）；接口运行时合同 `fail_closed_rule: FAIL or UNKNOWN permits ABORT only`（`MECH_RL_SYSTEM_INTERFACE_V2.yaml` 第 124-130 行，`b105766ec1f1`）；联合 Gate `$.sim13_non_abort_operation_authorized=false`（`55490805d934`）。父 Gate 18 仍字面 15/20（`18_SIM13_PREEXECUTION_GATE.json` `$.nc_state`，`af24635327dc`），子域注册表 20/20（`SIM13_V2_FULL_REGISTRY_20_OF_20_V2.json` `$.summary`，`a38f82538bf7`）——`CHILD_RESULT_NEWER__PARENT_GATE_NOT_REISSUED`，addendum 登记 `full_tmg6_reissue_executed=false`（`144e09124ce2`）。引用必须双口径并置。

**Q11 CTRL-01/CTRL-02 真实状态与适用域？**
- CTRL-01=**REPEAT**：`control_01_gate_check.json` `$.verdict` 第 6 行（`ab1fd26978f4`）；引用限定语「冻结增益与预注册轨迹下」（`wave1_cp6_ruling.md` 第 20-22 行，`1eeea3ccffb1`）；三缺陷修复字段级确认（能量账本 `$.gates.GC1_B.energy_audit_relative_max=5.6325998524987115e-12`）与七项预注册真负结果保留；当前树精确复现降级 7/22 HOLD_CURRENT_REPLAY（`CTRL_R2_PREDEVELOPMENT_GATE_V1.json` `$.criteria[C1]`，`ed4d8b7774c6`）。
- CTRL-02=**PASS_WITH_PROVISIONAL_SCOPE + PENDING_REVIEW**：`control_02_gate_check.json` `$.verdict` 第 1100 行/`$.review_status` 第 1078 行（`240fa708b536`）；7/16 STABILIZED 仅在 R5 PROVISIONAL 执行器/时窗模型下；L0 硬件有效稳定性 `NOT_EVALUATED_NO_ACTUATOR_DYNAMICS`（第 1093 行）；量子残差=门槛 21.5%（最坏 0.0108 dps 对 0.05 dps 门槛）为 W1-R13 硬件触发项（`wave1_gate_check.json` 第 286 行，`ef49240d9047`）。

**Q12 SAFE-00 模块 PASS 是否授予执行权？——否。**
`safety_00_gate_check.json`：`$.verdict="PASS"`（第 3 行）但 `$.review_status="PENDING_REVIEW"`（第 9 行）、`$.next_stage_authorized=false`（第 8 行）（`ff56929dd835`）；47/47 见 `results/evidence_manifest.json`（`056778011c4b`）；UNKNOWN 永不 ALLOW：`$.metrics.unknown_allow_count=0`、GS-B 12 绕过案例 0 成功；合同 §6 明文「机器 Gate PASS 不等于获准进入下一阶段」（`docs/safety_gate_contract.md`，`bd3b362aa440`）。附记：「downstream_authorization」字段全仓 0 命中，下游授权语义由 `next_stage_authorized=false` 承载（ctrl fragment §三）。

**Q13 当前最高数字孪生成熟度？——DT2_SCOPE_LIMITED_OFFLINE_REPLAY。**
`10_research/framework_convergence/numerical_twin_status.md` 第 5 行与第 24-26 行表（`bf783ca9dd8b`）；`10_research/00_project_architecture/digital_twin_plan.md` 第 7-13 行（DT3/DT4=BLOCKED，`64e88a4db0c6`）；`10_research/research_questions/Q5_digital_twin.md` 第 9 行 `LIMITED_DT2_AND_BLOCKED_UPGRADE`（`358fa65552e6`）。DT2 局部资产不覆盖 sim_10-12/SAFE/CTRL/Wave1/ASM。

**Q14 是否有 感知→候选→物理→SAFE→控制 完整闭环？——否。**
状态估计器不存在（`30_simulation/sim_13_physics_gated_embodied_grasping/config/sim13_bootstrap.json` `observation_mode=state_based`，`4624c5ba2a01`；`src/observation.py` 第 24-60 行观测为后端真值直读，`fafb189460bf`）；相机系 HOLD（`SYSTEM_FRAME_TREE.yaml` 第 87-90 行 `camera_optical_frame: TBD / HOLD_CAMERA_SELECTION_AND_CALIBRATION`，`71a9fffaa30a`）；Physics Tool 仅草案（`10_research/vla/tool_contract_draft.yaml` 第 8 行 `DRAFT_NOT_IMPLEMENTED`，`b8f130d578b2`）；SAFE 扩展未授权（`physics_gated_agent_plan.md` §3.3，`ecba24564e55`）；控制链段题述六状态机全仓 0 命中（ctrl fragment §四）。

**Q15 是否有 HIL？——否，机器登记的停止态。**
`competition_gate_check.json` `$.hardware_component_status={B601_MOTION:PROHIBITED, H0:NOT_STARTED_BLOCKED_BY_MISSING_HAG_E, H1:NOT_STARTED_BLOCKED_BY_H0, H2:NOT_STARTED_BLOCKED_BY_H1_AND_ESTIMATOR_GATE}`、`$.stop_rules.start_hil=false`（`8b3cdbdaa09e`）；`10_research/on_orbit_assembly/approvals/` 目录不存在（embodied fragment 2026-08-27 核实）。

**Q16 离线 demo 能/不能证明什么？**
能证明：17/17 资产齐全且哈希自洽；三场景动作确定性离线重放（`A_low=EXECUTE、B_anchor=ABORT、C_transition=MODIFY`）；媒体字节级一致（mp4 `7043d026cef6`、pptx `9deff92b539c` 对 manifest `33b7bfbf8682`）。不能证明：`$.command_emitted=false`、`$.real_time_synchronization=false`、`$.offline_replay=true`、`$.stop_rules` 全 false（`competition_gate_check.json`，`8b3cdbdaa09e`）——即不构成硬件/实时/自动执行资格；且 replay 文件当前哈希与 Gate 记录存在 REORG04 漂移，byte-identity 为历史结论（ctrl fragment §五）。

**Q17 2026 比赛要求哪些文件？——UNKNOWN（仓内无权威证据）。**
官方指南/模板/提交字段/视频格式仓内零命中（compdeliv fragment §A 检索记录）；唯一格式描述在归档文件 `项目现状总览_20260715.md` 第 11 行（「报告书+附件」「现场答辩+可选实物」），被 `AGENTS.md` 第 14 行禁作现行依据。`COMPETITION_REQUIREMENT_STATUS=UNKNOWN_BLOCKING_FORMAT_CONFIRMATION`（B-CD01，P0）。

**Q18 是否需要实物？——UNKNOWN，且与当前硬件状态存在潜在冲突。**
要求侧 UNKNOWN（同 Q17）；能力侧 `B601_MOTION=PROHIBITED`、H0/H1/H2 NOT_STARTED（`competition_gate_check.json`，`8b3cdbdaa09e`）。若官方强制实物，当前硬件运动禁令构成直接冲突，须 Owner 8-28 前确认并定展示方案（见 `11_OWNER_ACTIONS_REQUIRED.md` 第 2 项）。

**Q19 9-01 前最小工作是什么？**
即 §c 四项 P0 解除条件 + §b 中 P1 的最小答辩口径准备：官方要求确认并回填 04 矩阵（B-CD01）；报告母稿从零建立并逐 claim 绑 Gate（B-CD02）；标题/claim 收缩冻结（BLK-MEM-01/02）；git 锚定与仓库安全处置（B-CD04/05）；提交包+manifest+恢复演练+回执（B-CD03）；答辩口径带 07-20 日期+scope 限定（B-CD08）。逐日安排见 `10_FIVE_DAY_CLOSEOUT_PLAN.md`。

**Q20 哪些必须明确 HOLD（不得因比赛需要而松口）？**
正式机械 Release（Q4）；正式控制 Release（联合 Gate 4/13，`55490805d934`）；Sim13 non-ABORT 运行（Q10）；Route-C 正式化与 P01-P13 升 SSOT（Q6）；真实接触/捕获能力声称（v4 全 synthetic、T4 as-built=null）；VLA 训练、HIL、DT3/DT4（`PREBIND_AUTHORITY.json` `$.owner_authorization.prohibited_scope`，`e1157532605b`）；在轨装配 Wave A 主线（`research_state_v4.md` 第 14-16 行 `PLANNED_NOT_AUTHORIZED`，`1bd051d86368`）；e15 legacy 线维持 REPEAT（`e15 gate_summary.json` `$.overall`，`aab4d609e219`）。

---

## §b P0/P1/P2/P3 缺口清单（与 fragments blockers.csv 一致）

### P0_SUBMISSION_BLOCKER（7 项；9-01 合规提交的硬前提）
| 编号 | 缺口 | 证据指针 |
|---|---|---|
| B-CD01 | 2026 官方参赛要求仓内缺失，Q17/Q18=UNKNOWN | compdeliv findings §A；`blockers.csv` B-CD01 |
| B-CD02 | 比赛技术报告书母稿不存在 | 仓内 `*.tex` 仅 `80_third_party/vendor/` 命中；`01_project` 无报告书 docx/pdf（compdeliv §B.2.1） |
| B-CD03 | 无 submission package/ZIP manifest/恢复演练/提交回执 | compdeliv §B.2.3 |
| B-CD04 | GitHub 仓库可见性/forks 离线不可验证，敏感资产公开性未决 | `git remote -v` 空、`.git/config` 无 `[remote]`（compdeliv §C.2） |
| B-CD05 | 08-08 后全部终局证据未提交 git（141 条 status，含 130 untracked） | compdeliv §C.1；SYN-C 复算 HEAD=`5c5adde`@2026-08-08 |
| BLK-MEM-01 | 标题/claim 未收缩，四词无 current-system 证据；候选标题仓内零命中未冻结 | `10_research/research_questions/PROJECT_CURRENT_STATUS.md` EMBODIED_AI 行（`cce6517b4cd5`）；framework 矩阵 C21/C23-C29（`7d296e7a2437`）；grep 候选标题业务文档零命中（memory §4） |
| BLK-MEM-02 | claim-evidence 矩阵未按当前状态重冻结（停 08-04/旧 HEAD b75352c，未吸收 08-23 红绿线） | `10_research/contribution_map/README.md` 第 10 行（`c6944e472039`）；`40_evidence/tables/paper_claim_evidence_matrix.csv` mtime 2026-08-04 |

### P1_FINAL_DEMO_BLOCKER（16 项；影响决赛答辩口径与展示强度）
DYN-B01（T_c=20 ms 占位，`scene_A2_capture.yaml` 第 25 行，`4b979a1dfd18`）；DYN-B02（帆板模态占位，`coupled_model_v0.yaml` 第 5 行 `PROVISIONAL_PARAMS`，`67a532fb29c7`）；DYN-B03（sim_10 冻结哈希锁 REORG04 失效，`scan_v0.yaml` `856f1e30de47`，钉住值 `850f49da…/400bcedc…` vs 当前 `006c6cc5…/75af082a…`）；E-COMP-02（Unified R2 守恒/状态连续性无当前系统信用，`PB_G1_GATE.json` `7ad34fcf9482` + `R2_8DOF_CONSTRAINED_DYNAMICS_GATE_V1.json` `6fc6f5ec0df1`）；E-COMP-03（SAFE 故障注入/独审未闭合，`ff56929dd835` 第 8-9 行 + 当前树重放 23/47）；E-COMP-04（无可复现任务级控制链段，六段链全仓 0 命中，`R2_CONTROL_ENGINEERING_GATE_V1.json` `$.execution_guards` 全 false，`2740b33e7958`）；BLK-SIM13-08（演示叙事越权风险：任何非 ABORT 执行说法即事故，`4a813f2ee3b0` `$.maximum_operational_state`）；BLK-E01（E-COMP-05 最小感知接口运行时资产缺失，`sim13_bootstrap.json` `4624c5ba2a01`）；B-CD06（展架图/作品照片缺失且硬件 PROHIBITED）；B-CD07（PUBLICATION_HOLD 裁决原文仓内零命中）；B-CD08（演示包 07-20 口径与 08-25 后 HOLD 增多的时代差，`HOLD_AND_NEGATIVE_RESULTS_V1.csv` H-01..H-15，`667dd3bd8a83`）；B-CD09（论文级 claim 账本 0 行，`claim_evidence_ledger.csv` `1cff4ab952b7`）；BLK-MEM-03（主问题三版本未收敛）；BLK-MEM-04（08-27 两裁决 ODR-60 token 措辞冲突，`3eed50dd728e` §2.1 vs `7884373ee9fc` §1/§5，以联合 Gate `55490805d934` 为准）；BLK-MEM-05（继承包部分 SUPERSEDED，`PROJECT_TRUTH_INDEX.json` `e348749b9525` 哈希失配）；BLK-MEM-06（查新精读未闭环，Wang/Lu/Cai 三级核验状态，`3be39f02c15a` §1/§5）。

### P2_FORMAL_RELEASE_BLOCKER（正式工程 Release 链；禁止升级为 P0）
mech BLK-MECH-01..16（Route-C 物理输入权威、G12、TMG-6 未重签、窄相碰撞资产 ABSENT、as-built 计量 HOLD 等，见 mech `blockers.csv`）；dyn DYN-B04..B08（e15 legacy REPEAT、e21 语义 UNRESOLVED、sim_13 正式化、执行机构 CLASS 占位、e23 PENDING_OWNER_REVIEW）；ctrl E-CTRL-RELEASE、E-CTRL-HW-01（执行器 152/152 null）、E-CTRL-REPLAY-01、E-CTRL-CONTACT-01、E-CTRL-PREBIND-01；sim13 BLK-SIM13-01..07（绑定门/接口正式化/NC18 生产化/NC19 物理化/工作单尾序/Owner 接受/G12）；embodied BLK-E05（相机系 HOLD）、BLK-E06（SAFE 扩展未授权）、BLK-E07（`physics_agent/README.md` 缺失）、BLK-E08（Sim13 父子口径）；compdeliv B-CD10（08_REVIEWS 空）；memory BLK-MEM-09（Release 叙事边界）。

### P3_POST_COMPETITION_RESEARCH（赛后研究线）
DYN-B09（NMPC/RL/VLA 禁止序）；E-CTRL-SIM13-01（Sim13 非 ABORT 生产化）；BLK-SIM13-09/10（DT3/DT4、RL/VLA）；BLK-E02（HIL H0-H3）、BLK-E03（VLA 对照实验）、BLK-E04（DT 升级门）；B-CD11（根目录杂项治理）；BLK-MEM-07（装配 Wave A）、BLK-MEM-08（检索刷新+独立核查）。

---

## §c CONDITIONAL_GO 解除条件（P0 四项，均须 2026-08-31 前闭合）

1. **官方要求确认**（解 B-CD01，并带动 B-CD06/Q18）：Owner 下载 2026 正式参赛指南+模板，登记入 `01_project/inbox/source_manifest.csv` 并回填 04 矩阵；确认技术类是否强制实物。**未闭合后果**：COMPETITION_SUBMISSION 降级 NO_GO（格式无权威依据）。
2. **报告母稿**（解 B-CD02）：按 §13 标题与 claim ceiling 从零建立比赛技术报告母稿，逐 claim 绑定 gate JSON+row locator+sha256。**未闭合后果**：初赛网评无交付物，NO_GO。
3. **claim 收缩冻结**（解 BLK-MEM-01/02）：Owner 签收收缩标题（`13_TITLE_AND_CLAIM_CEILING.md`），PI 以 append-only 重冻结 claim-evidence 矩阵（吸收 08-23 红绿线与 08-25/27 收口）。**未闭合后果**：全部材料禁用四词（具身智能/自主抓取/数字孪生/在轨装配），叙事降级为可行域+fail-closed 单线。
4. **git 锚定+仓库安全处置**（解 B-CD04/05，并带动 B-CD03）：Owner 决定提交策略（审计只读不操作 git），至少为提交包建立独立 sha256 manifest+恢复演练+回执；人工登录 GitHub 核对可见性/forks 并书面裁决。**未闭合后果**：提交包无法锚定 commit、机器可复现性依赖工作树状态，且敏感资产公开性风险悬置，NO_GO。

---

## §d fail-closed 条件清单核对（TRIGGERED/NOT_TRIGGERED + 证据）

| # | 条件 | 判定 | 证据与处置 |
|---|---|---|---|
| 1 | 找不到 accepted URDF | NOT_TRIGGERED | `05_ACCEPTED_B601_URDF_REF.yaml` 存在且 accepted URDF sha256 `1BC2B748…` 复算一致（mech fragment §8，`6912f7d547b8`） |
| 2 | 哈希冲突 | NOT_TRIGGERED | 各分片引用文件复算与内部 pin 全部一致（mech/dyn/sim13 hashes.csv）；sim_10 R 锁漂移已由 git diff 证实为 REORG04 纯路径改写、语义等价（dyn fragment §5.1，commit 284c882），记 DYN-B03 风险而非冲突；replay byte-identity 降为历史结论（ctrl §五）。无任何综合结论因哈希冲突被拒 |
| 3 | CAD 质量污染 accepted URDF | NOT_TRIGGERED | `05_…yaml` 双 FORBIDDEN 明文；未见覆盖迹象（mech §8） |
| 4 | 父 Gate 不定 | NOT_TRIGGERED | 父 Gate 均为确定态：00_RELEASE_GATE TERMINAL…NO_RELEASE_CREDIT（`14d30fd40ac6`）、联合 Gate HOLD 4/13（`55490805d934`）；CHILD_RESULT_NEWER 已正式登记（`144e09124ce2`） |
| 5 | 36 行并入 81 行 | NOT_TRIGGERED | CLASS_1 donor 81 行 ACCEPTED_EXCEPTION_OPTION_A_HISTORICAL_ONLY 与 CLASS_2 pose-induced 36 行两账独立成类未合并（`INTERFERENCE_CLASSIFICATION.csv`，`1f343b02f4b3`；`GRIPPER_R1_GEOMETRY_VALIDATION.json`，`7bc0df784b36`） |
| 6 | Route-C provisional 入 SSOT | NOT_TRIGGERED | P01-P13 停留 route_c 注册表 DESIGN_CANDIDATE/PROVISIONAL 权威（`1e70d6f95141`），无升 SSOT 记录；维持 KNOWN HOLD |
| 7 | frame 单位冲突 | NOT_TRIGGERED | camera_optical_frame TBD/HOLD（`71a9fffaa30a` 第 87-90 行），committed `frame_tree_v1.yaml` 无相机系（`958bff23bf83`）；未发现已提交坐标系单位冲突 |
| 8 | solver 不收敛 | TRIGGERED（已正确 fail-closed，不扩散） | B4G 合成接触 campaign 3 例能量-功恒等式失败已注册失效（`SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json`，`2743fbd314cc`），机理=冻结离散第一定律中点二阶截断缺陷（R1 闭环门 `ae7e81f66cf6`）；`original_b4g_final_credit=false`、`new_physics_campaign_executed=false`——对应分支已冻结，本备忘录不引用 v4 合成接触任何数字 |
| 9 | UNKNOWN 放行 | NOT_TRIGGERED | SAFE-00 `unknown_allow_count=0`、12 绕过案例 0 成功（`ff56929dd835`）；运行时 UNKNOWN=NEVER_PASS→ABORT_ONLY（`15_UNIFIED_R2_SYSTEM_INTERFACE.yaml` 第 144-148 行，`19822080e540`） |
| 10 | source-only 写成 current-system | NOT_TRIGGERED | 本备忘录 Q9/Q10 显式区分 SOURCE_ONLY_BUILDER_EMISSION 候选与正式系统 URDF 不存在（`957ca67d7bcc`）；prebind PASS 未升级为系统 PASS |
| 11 | synthetic 写成真实夹爪 | NOT_TRIGGERED | v4 目录名即 `v4_synthetic_contact_capture_diagnostic`；NC19 仅合同包络 BOUNDED_PROVISIONAL、派生非实测几何（`SIM13_CONTACT_GRASP_GATE_V2.json`，`f13b755ea0b3`）；T4 as-built=null MEASUREMENT_PENDING（`10_GRIPPER_INTERFACE.yaml`） |
| 12 | 官方提交格式无法确认 | **TRIGGERED** | compdeliv §A 零官方文件命中（B-CD01）。处置：冻结「按既定格式打包提交」分支——提交格式相关内容以 Owner 取回官方文件为前置，其余证据复算/报告撰写/演示重验证分支照常推进 |
| 13 | 仓库敏感资产公开性未决 | **TRIGGERED** | `git remote -v` 空、继承包风险声明仓内不可定位（B-CD04）。处置：冻结「仓库公开/外链分享/镜像同步」分支——任何对外仓库动作待 Owner 人工核对 GitHub 可见性与 forks 后书面裁决 |
| 14 | 核心数字无 row locator | NOT_TRIGGERED | 全部图表数字带数据文件+脚本+row locator（dyn fragment §6 表，如 sim_06 CSV 第 15 行 `post_rate_full_dps=3.06333`，`8cbad84b8ff6`）；本备忘录数字均带 JSON key/行号 |
| 15 | 放宽 Gate 删 REPEAT | NOT_TRIGGERED | 本次审计只读，未重发任何 Gate；e15/CTRL-01/WAVE1/E22/V9F 等全部 REPEAT/HOLD/负结果原样保留（memory fragment「给综合裁决的输入」第 8 条） |

---

## 附：本备忘录的引用纪律

评委材料引用本备忘录任何数字时，须同时引用其证据指针（路径+JSON key/行定位+sha256 前 12 位）；Sim13 一律双口径（父 15/20 冻结 + 子 20/20 append-only，最高 ABORT_ONLY）；SAFE-00/CTRL-02/e23 引用必带 PENDING_REVIEW/PENDING_OWNER_REVIEW 与 next_stage_authorized=false；CTRL-01 引用必带「冻结增益与预注册轨迹下」。
