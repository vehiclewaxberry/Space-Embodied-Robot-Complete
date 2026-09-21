# mech 分片审计发现（机械与 Route-C 域）

审计日期：2026-08-27（本地）。分片名：mech。只读执行：未做任何 git 写操作、未覆盖/移动/删除任何文件、未运行 CAD/仿真、未重发任何 Gate。

## 写入授权覆盖声明

本审计唯一写入位置为 `90_competition_closeout/20260827_current_state_audit/fragments/mech/` 下 5 个 fragment 文件。该目录由用户在分片任务书中显式授权创建，优先于根 `AGENTS.md` REORG04「根目录业务资产只允许进入八个域」的限制（`AGENTS.md` L7，sha256 前 12 位 `3d2269562678`）。90_competition_closeout 系本次比赛收口专用域。

## 证据权威与交叉校验方法

以机器 Gate JSON/冻结配置/哈希清单 > 当前接口合同 > accepted URDF > 冻结 CAD > 独立复核 > 文档的顺序取证。所有引用文件经 Git Bash `sha256sum` 复算（见 hashes.csv），并与文件内部 pin 交叉比对：00_RELEASE_GATE、05/07/12/13/15/17/18/22、handoff V2、ODR-58、ODR-60 请求、V9F falsifier、Sim13 20/20 Gate、accepted URDF 等全部复算值与内部 pin 一致。

## (4) 当前机械 Release 是否成立：不成立

`20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/00_RELEASE_GATE.json`（sha256 前 12 位 `14d30fd40ac6`）字段原文：

- `verdict = "TERMINAL_CLOSURE_EXECUTED__GATE_A_NOT_PASSED__TMG4_TM6_INTERNAL_BLOCKERS_REGISTERED__NO_RELEASE_CREDIT"`
- `gate_a_pass: false`、`review_status: "PENDING_OWNER_REVIEW"`、`next_stage_authorized: false`、`release_credit: false`
- TMG 分项：TMG-1 PASS / TMG-2 PASS / TMG-3 PASS / **TMG-4 HOLD** / TMG-5 PASS_WITH_DECLARED_PROVISIONAL_PHYSICS / **TMG-6 FAIL_15_OF_20** / TMG-7 HIGH_0。

结论：机械 Release R2 不成立，且该否定为诚实登记（invariants: hash_mismatch=0、empty_comparison_set=0、unexplained_positive_interference=0）。后续 2026-08-26 的 V9F 终局裁决未改写该 Gate（`ROUTE_C_V9F_TERMINAL_RULING.json` `governing_records.historical_release_gate_preserved.modified_by_this_ruling=false`，sha256 前 12 位 `09611ddb8adc`）。

## (5) Checkpoint-A / B / C 状态

- **Checkpoint-A（Full-Flex/e23）**：历史态 HOLD 6/12（E22 16/18 G11/G17 fail；e15 REPEAT），冻结于 `TERMINAL_DECISION_PACK_GATE_V1.json` `checkpoint_state.A_R2_FULL_FLEX`（sha256 前 12 位 `0c9dc0353630`）。现行闭合经 2026-08-25 Round4 V3 17/17 + E23 18/18 交付，并在父 Gate TMG-5 入账为 PASS_WITH_DECLARED_PROVISIONAL_PHYSICS（`13_R2_FLEX_MODEL.yaml` `e23_recertification`，sha256 前 12 位 `8cadf790cf6a`）。即：历史 Gate 未改写，父 Gate 已重发含 TMG-5 PASS——不属于「子新父旧」情形。
- **Checkpoint-B（Route-C C2 准入）**：`ROUTE_C_CHECKPOINT_B_GATE_V1.json`（sha256 前 12 位 `c9e7526d790e`）保持 2026-08-24 的 HOLD：准入 2/8（仅 C2-ADM-01/07 PASS），注册表 13/13 null，RFI-E/F/G 响应 0，`ROUTE_C_CAD_AUTHORIZED=false`。该 Gate 从未重跑为 PASS；后续 RC-2/RC-3 由 Owner 指令放行（`ROUTE_C_PHYSICAL_INPUT_GATE_V1.json` `route_c_rc2_rc3_entry="ALLOWED_BY_OWNER_DIRECTIVE_A1"`，sha256 前 12 位 `f5016c3a6f82`）。终局结果为负（V9F 被拒）。
- **Checkpoint-C（终局 Release）**：从未到达。`checkpoint_state.C_TERMINAL_RELEASE: reached=false, candidate_generated=false`；R2 侧 `release_credit=false` 贯穿全部现行 Gate。

## (6) Route-C P01–P13 与 E_HRN 0/75、11/11 核实

P01–P13 在 `ROUTE_C_PHYSICAL_CAPABILITY_REGISTRY_V2.yaml`（2026-08-25，sha256 前 12 位 `1e70d6f95141`）已逐项闭环，RC-1 Gate PASS（设计候选权威范围）：P01=12.0 mm / P02=50.0 mm / P03=543.946 mm（+40.78%）/ P04=110.0 mm / P05=HN-00..04 站表 / P06=50.0 mm（LOW）/ P07=1333.8 mm / **P08 value=null**（仅 [0,10] deg/m 分配，恢复力矩曲线 UNKNOWN 未零填）/ P09=65.0 [56.5,72.5] g/m（LOW）/ **P10 value=null**（[0.06,0.20] 数据表区间）/ **P11 value=null**（[50,63]，六个命名导向体积已实体化）/ P12=10.0x16.0 / P13=120 [55,150]。无一项为 MEASURED/AS_BUILT。MPI-01..04 电气输入未闭合。

E_HRN 原始字段核实属实：`B601_HARNESS_RATED_ENVELOPE_V1.yaml`（sha256 前 12 位 `a63a93de5b6b`）`E_HRN.sample_counts: SAFE 0 / UNSAFE 75 / UNKNOWN 0`（samples_total 75）、`mandatory_key_state_probe: states_safe 0, states_unsafe 11`；`B601_HARNESS_MISSION_COVERAGE_GATE.json`（sha256 前 12 位 `f3b444222e87`）10/10 强制任务态 UNSAFE。注意三个分母（75 map / 11 probe / 10 mandatory）是不同总体，引用时不得混写。

## (7) handoff 是否 12/12：否，11/12，G12 失败（核实属实）

`MECHANICAL_TO_EMBODIED_HANDOFF_GATE_V2.json`（sha256 前 12 位 `13722965d5c5`）：`checks_total=12, checks_passed=11, checks_failed=1, failing_checks=["G12"]`；G12 `HARNESS_RATED_OPERATIONAL_ENVELOPE` 失败因 `mission_coverage_pass=false`、`map_contains_safe_sample=false`（SAFE 0/75）。终端 Gate `17_MECH_TO_EMBODIED_HANDOFF_GATE.json`（sha256 前 12 位 `42792057bd9f`）确认：统一接口重跑仍失败，「until the harness mission envelope passes」。

## (8) accepted B601 URDF 未被 CAD 自动质量覆盖；31.022864807342987 kg 出处

`05_ACCEPTED_B601_URDF_REF.yaml`（sha256 前 12 位 `6912f7d547b8`）明文：`modification: FORBIDDEN`、`cad_mass_or_geometry_override_of_accepted_urdf: FORBIDDEN`，accepted URDF sha256 `1BC2B748...`（复算一致，11321 字节）。总质量 31.022864807342987 kg 的出处为 accepted URDF 惯性账本的精确合计：`20_RED_TEAM.json` RT-04 `evidence: "total=31.022864807342987"`、发射回执 `checks.total_mass_exact=true`、Sim13 补充 Gate `configuration_truth.runtime_c01_total_mass_kg: 31.022864807342987`。`07_SYSTEM_MASS_PROPERTIES.yaml` 中设计质量 V3 R2 标为 CANDIDATE_ONLY_NOT_AS_BUILT，as-built 为 HOLD_EXTERNAL_MEASUREMENT_PENDING——未见任何 CAD 自动质量覆盖 accepted URDF 的迹象。

## 附加核实项

- **Unified R2 URDF 发射类别**：`UNIFIED_R2_URDF_EXECUTION_RECEIPT_V2.json`（sha256 前 12 位 `957ca67d7bcc`）`emission_class="SOURCE_ONLY_BUILDER_EMISSION__NOT_GEN_URDF_AUTHORITY_EXECUTION"`；`gen_urdf_attempts_under_valid_authorization=8`，全部 `DENIED_BY_FAIL_CLOSED_FINAL_CHECK`，缺陷 TMC-F01（marshal 运行码指纹在 CPython 3.13.9/3.14.4 下不稳）完整披露，URDF XML 输出确定不受影响，7 项检查全过。
- **T4 接触合同**：`DESIGN_CONTACT_MODEL_GATE_V1.json`（sha256 前 12 位 `20f3aa89a07d`）PASS_BOUNDED_PROVISIONAL_STRUCTURE，`as_built_all_null_measurement_pending=true`、`zero_fill_absent=true`；`10_GRIPPER_INTERFACE.yaml` `as_built_contact_model: null MEASUREMENT_PENDING`。
- **TMG-4/5/6**：见 (4)。TMG-4 HOLD（线束）、TMG-5 PROVISIONAL PASS、TMG-6 FAIL_15_OF_20（父 Gate 冻结值）。
- **夹爪干涉两本账未合并（核实）**：`INTERFERENCE_CLASSIFICATION.csv`（sha256 前 12 位 `1f343b02f4b3`）CLASS_1 donor 静态继承 81 行保持 ACCEPTED_EXCEPTION_OPTION_A_HISTORICAL_ONLY；CLASS_2 导轨-掌部 pose-induced 36 行（`GRIPPER_R1_GEOMETRY_VALIDATION.json` `original_v5_interference_evidence.pose_induced_rows=36`，OPEN 24 行/1266.93 mm³ + PREGRASP 12 行/779.63 mm³，sha256 前 12 位 `7bc0df784b36`）经中性 R1 修正后 post_count=0 PASS，原生 V5 36 行保留且重集成 HOLD。两账独立成类，未互相洗入。

## 新发现（超出任务书预期的三点）

1. **CHILD_RESULT_NEWER__PARENT_GATE_NOT_REISSUED（正式登记）**：Sim13 后端负控已达 20/20 PASS（`SIM13_20_OF_20_GATE_V1.json` `nc_score="20/20"`、61 pytest，sha256 前 12 位 `4a813f2ee3b0`），但父 Gate（00_RELEASE_GATE TMG-6=FAIL_15_OF_20、18_SIM13_PREEXECUTION_GATE）未重发；append-only 补充 Gate 明确 `full_tmg6_reissue_executed=false`、`historical_15_of_20_superseded=false`（`SIM13_POST_TERMINAL_HANDOFF_ADDENDUM_GATE_V1.json`，sha256 前 12 位 `144e09124ce2`）。综合裁决不得把 20/20 写成当前系统通过。
2. **ODR-60 Option A 已被 Owner 选择（2026-08-27 凌晨最新态）**：`OWNER_SELECTION_RECORD_V1.json` verdict `ODR60_OPTION_A_SELECTED__LOW_MEMORY_OVERRIDE_EXPLICITLY_NOT_AUTHORIZED__PRESEARCH_GATES_STILL_FAIL_CLOSED`（sha256 前 12 位 `a88e2301b36d`），授权证据为执行提示词块首行 token。静态绑定部分闭合（挂载 12 位小数拼写 + 10 行碰撞帧台账），但 pair/edge/path/内存准入全 false，8 项 blocker 在案（执行收口 Gate，sha256 前 12 位 `869a248050fd`）。
3. **完整性观察两项**（NEG-MECH-17/18）：`01_BASELINE_MANIFEST.json` 自引用条目陈旧（记 4497 字节/C7206FAD…，实测 4488 字节/7e87ee69…；22_RELEASE_SHA256.csv 本不含 01 条目，00 Gate 上游 pin 校验不受影响）；`20_RED_TEAM.json` 与 `21_FALSIFIER.json` 逐字节相同（同 sha256 `f3981655c383…`），引用时应注明同源。

## 比赛相关性判断（本分片无 P0/P1）

按任务书指示并经证据核实：Route-C P01–P13、RC5、handoff G12 均归 P2_FORMAL_RELEASE_BLOCKER。当前管理默认 OFFLINE_PHYSICS_GATED_MECHANICAL_DEMO=GO 且正式机械 Release=HOLD 为既定状态，初赛提交（2026-09-01）与决赛展示均不依赖正式机械 Release；机械域可引用的是诚实否定证据链与 E23/TMG-5 级物理证据（带 provisional 限定）。未发现任何 mech 域缺口会使 9-01 无法合规提交（P0）或阻断决赛展示（P1）。

## 给综合裁决的输入

1. 机械 Release R2 不成立：`00_RELEASE_GATE.json` `verdict=TERMINAL_CLOSURE_EXECUTED__GATE_A_NOT_PASSED__...__NO_RELEASE_CREDIT`、`gate_a_pass=false`（sha256 `14d30fd40ac6`）。
2. TMG-4 HOLD 的机器真值：E_HRN 0/75 SAFE（`B601_HARNESS_RATED_ENVELOPE_V1.yaml` sample_counts，`a63a93de5b6b`）+ 11/11 探针态 UNSAFE + 任务覆盖 FAIL_AT_MANDATORY_KEY_STATES（`f3b444222e87`）。
3. handoff 当前 11/12、唯一失败 G12：`MECHANICAL_TO_EMBODIED_HANDOFF_GATE_V2.json` checks_failed=["G12"]（`13722965d5c5`）；统一接口重跑仍失败（`17_…json`，`42792057bd9f`）。
4. Route-C 终局：V9F 在当前 M01 路径被精确负见证否决（raw -10.729480331980062 mm / gated -17.313396996697108 mm，43 节点/19 binary64 逐位一致），几何循环额度 0、TMG-4 HOLD、待 Owner 轨迹/架构决策（`ROUTE_C_V9F_MANDATORY_M01_FALSIFIER_GATE.json` `09c3199bd982`；`ROUTE_C_V9F_TERMINAL_RULING.json` `09611ddb8adc`）；不证明替代路径不存在（UNKNOWN_NOT_SEARCHED）。
5. Sim13 计分两版本并存必须按 CHILD_RESULT_NEWER__PARENT_GATE_NOT_REISSUED 处理：父 15/20 冻结（`af24635327dc`），子域 20/20 append-only 且 FULL_TMG6 NOT_REISSUED、ABORT_ONLY（`144e09124ce2` / `4a813f2ee3b0`）。
6. Checkpoint 现状：A=历史 6/12 HOLD 冻结、现行经 TMG-5 入账（PASS_WITH_DECLARED_PROVISIONAL_PHYSICS，E23 18/18，`8cadf790cf6a`）；B=HOLD 2/8 未重跑、后经 Owner 指令 A1 放行且终局为负；C=未到达。
7. 总质量 31.022864807342987 kg 出自 accepted URDF 惯性账本精确合计，CAD 覆盖被明文禁止（`05_…yaml` `6912f7d547b8`；RT-04 evidence，`f3981655c383`）；as-built 计量 EXTERNAL HOLD。
8. ODR 链最新态：ODR-42 APPROVE_BOUNDED_DETAILED_DESIGN（`d5e33b99532b`）→ ODR-58 额度用尽 → ODR-59 TMG-2 数值规则仍缺（owner_rule_present=false，`fe5274c5e588`）→ ODR-60 Option A 已选但预搜索全 fail-closed（`a88e2301b36d` / `869a248050fd`）。
9. mech 域 blockers 全部归 P2_FORMAL_RELEASE_BLOCKER（16 项，见 blockers.csv）；无 P0_SUBMISSION_BLOCKER、无 P1_FINAL_DEMO_BLOCKER。
