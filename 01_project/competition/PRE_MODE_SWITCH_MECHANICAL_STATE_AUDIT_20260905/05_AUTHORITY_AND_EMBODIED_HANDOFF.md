# 授权链与机械—动力学—控制—具身交接只读审计

审计日：2026-09-05。工作模式：`READ_ONLY_SOURCE_AUDIT`。本报告为派生审计，不是新 Owner 决策或机器 Gate；没有运行 CAD、几何查询、仿真、控制、训练或历史验证器。只在本审计目录生成文字、来源哈希和原文摘录。

**结论：已有可复用的机械候选、动力学子项、控制诊断和 fail-closed 软件后端；完整机械交接与当前系统运行资格仍未闭合。不能把旧入口中的“未实现”照搬成全部现状，也不能将后续局部 PASS 汇总成父 Gate PASS。当前 Mode A 退出后的 Mode B 转线仍是待决选项，本轮只读审计不启动转线。**

## 1. 权威的时间与范围必须同时核对

2026-08-25 机械父 Gate 的精确 verdict 为：

`TERMINAL_CLOSURE_EXECUTED__GATE_A_NOT_PASSED__TMG4_TM6_INTERNAL_BLOCKERS_REGISTERED__NO_RELEASE_CREDIT`

其中 TMG-4=`HOLD`、TMG-6=`FAIL_15_OF_20`、`gate_a_pass=false`、`next_stage_authorized=false`、`release_credit=false`。这是仍未被重发的父裁决，不能因为后续文件时间更晚而静默改成通过。[父 Gate，2026-08-25T08:51:20.842809Z](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/00_RELEASE_GATE.json:3>)

同时，08-25 知识入口所述 Route-C 全无候选、Sim13 五后端待实现、接口实例缺席，已经不足以完整描述后来工作。08-28 CURRENT_R2 索引和 V2–V8 增量、08-29 Sim13 父子权限核对必须一并读取。`PROJECT_CURRENT_AUTHORITY_V1.yaml` 自己声明 `NAVIGATION_ONLY / authority: NONE`，不得替代原 Gate。[导航身份](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/current/PROJECT_CURRENT_AUTHORITY_V1.yaml:1>)；[08-28 索引](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/CURRENT_R2_AUTHORITY_INDEX.json:1>)。

## 2. F4R1 的“SIGNED”有具体正文，但尚不足以独立定位原始会话

两份文件正文明确保存了 Owner 中文指令、日期及许可范围：

- ODR-F4R1-01（2026-08-27）授权 C1/C2 立即开始；C3 原定后续另行确认；DESIGN_POINT 采用 `12U-derived form factor`，不承诺标准 12U deployer 约束，并保留 ≤24 kg 变体预算线。
- ODR-F4R1-02（同日）进一步将 C3 提前至 08-27；允许 FreeCAD/OCP 候选工作，限定冻结接口只读、候选不进入正式 SSOT，不授予制造/飞行资格；末句明确“签署范围仅限 F4R1 工作包内部”。

因此不能只读章程中旧 CAD 禁令，也不能只凭 `SIGNED` 文件名认定无限授权。两份记录虽含 `signoff_evidence` 原话引用，但没有原始 attachment 路径、消息 ID、原始会话摘要哈希等定位信息；本次在指定工程/项目文档范围内未独立核验那两条对话。此结论是**溯源尚不完整**，不是断言用户从未授权。[ODR-01 正文](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1/00_charter/ODR_F4R1_01_SIGNED.md:5>)；[ODR-02 正文](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1/00_charter/ODR_F4R1_02_SIGNED.md:5>)。

比赛排期类限制只作为当时记录保留；本次用户给定的 2026-08-31 owner 覆盖已取消其作为当前机械工程进度或授权 Gate 的作用。

## 3. Mode A 的许可声明与 Mode B 的选项必须分开

`A3_00_INPUT_AUTHORITY.json` 声明 `NATIVE_CANDIDATE_DESIGN_AUTHORIZED`，写入边界为 `.../_work/mode_a_native_design_r1/`，claim 上限为 `RESEARCH_AND_ENGINEERING_CANDIDATE_ONLY`；它把工具链授权来源写为 `ODR_F4R1_02_SIGNED.md clause 3`，同时保留 `SSOT_AND_ODR_PROMOTION_HOLD`、Owner review pending 和 release=false。[Mode A 权威记录](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1/00_authority/A3_00_INPUT_AUTHORITY.json:1>)

这份文件与 F4R1-02 的目录范围存在需要区分的关系：后者正文仅限定 F4R1 内部，前者引用了其中工具链条款。指定范围内未定位到独立的 Mode A 扩展授权原文，故本审计将其列为“既有候选包自述许可，直接会话溯源未完整定位”，不自签扩权。

当前 A3.2D 精确 Gate 为 `A3_2D_HOLD_FULL_SYSTEM_EXCEEDS_NOMINAL_12U`；`options_not_evaluated_here` 中列出 `Mode B (12U-class free flyer without deployer constraint)`，并写 `owner_decision_required=true`。它只证明 Mode B 是本轮退出后的未评估选项，不能当作已执行或已获转线许可。历史 P5C 等文档中的同名 Mode B 属于其历史配置语义，不自动解决此次 Mode A 分支的退出决策。A3 文件未提供可用于独立排序的生成时间字段，本审计不以磁盘修改时间补造时间线。[A3.2D Gate](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1/04_a3_2d/A3_2D_FINAL_GATE.json:2>)；[转线仍为未评估选项](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1/04_a3_2d/A3_2D_FINAL_GATE.json:133>)。

## 4. ODR-60 的 Option A 有原始附件定位，仍须遵守分阶段准入

这里的 Option A 是固定端点 M01 路径研究，**不是 Mode A/B 的整星包装路线**。`OWNER_SELECTION_RECORD_V1.json` 指向原始附件，字节数 18519、SHA-256=`EB9138AF1C04E07F7470587871F26A364DCB754994A6C1131F077D0467E91AC3`；本次只读复算吻合。附件第 706 行的执行块首行为 `AUTHORIZE_OPTION_A_FIXED_ENDPOINT_M01_TRAJECTORY_SEARCH`，随后按顺序要求 mount、frame、三阶段 scene、pair、motion、clearance、oracle、edge 最后 bounded search 闭合。

精确记录 verdict：`ODR60_OPTION_A_SELECTED__LOW_MEMORY_OVERRIDE_EXPLICITLY_NOT_AUTHORIZED__PRESEARCH_GATES_STILL_FAIL_CLOSED`。选择本身不使 geometry/pair/edge/path 四项授权为 true；当时低内存豁免也不具备复用授权。本次不执行该流程。[选择记录](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/OWNER_SELECTION_RECORD_V1.json:1>)；[原始附件执行块](<C:/Users/stude/.codex/attachments/0cd497c9-fcae-4714-997d-859171b88dc2/pasted-text.txt:706>)。

## 5. Route-C 已产生局部候选，系统查询仍为零

最新已核对的 CURRENT_R2 V8（2026-08-28）精确 verdict：

`AUTHORITY_DELTA_V8_APPEND_ONLY_COMPLETE__LOCAL_LINK2_B12_CANDIDATE_AUTHORITY_ONLY__NO_SYSTEM_OR_RELEASE_UPGRADE`

V7 的 47 个本地候选加 Link2-B12 的 12 个，合计 **59 个本地待绑定候选**；Route-C R 类剩余 **83**。但当前系统注册仍为 **150 个对象、1 个 operational geometry authority 行**，clearance policy **0/11,166**，三阶段 instance **0/3**，生产 pair query=0、SAFE pair=0、continuous edge=0，`path_search_authorized=false`、`path_search_executed=false`。`path_exists=false` 在未搜索的上下文中不能解释成“已证明无可行路径”。[V8 候选计数与系统边界](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/CURRENT_R2_AUTHORITY_DELTA_V8.json:130>)

C9 已有 9 个对象、61 个解析 primitive、2355 个 capsule 的局部候选；需保留设计半径+Hausdorff 上界恰好一次的有效半径规则，J3 production union 接受及 P11 谱系仍未闭合。Link2-B12 局部 Gate 为 24/24，核验 q1×q2 九点 FK，不等于生产碰撞安全。[C9 后续边界](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/CURRENT_R2_GAP_AND_CRITICAL_PATH_V7.md:15>)；[Link2-B12 局部 Gate](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_ROUTE_C_R95_LINK2_B12_OPERATIONAL_COLLISION_CANDIDATE_V1/05_results/LOCAL_CANDIDATE_GATE_V1.json:1>)。

## 6. 生产碰撞后端不是“完全没实现”，而是尚未绑定当前系统

OCP/BRep 单 pair 后端有 **25/25** 的合成软件 Gate、18/18 适用负控、5/5 独立验证；其精确 verdict 为：

`PAIR_ORACLE_BACKEND_SYNTHETIC_GATE_PASS__18_OF_18_NEGATIVE_CONTROLS__INDEPENDENT_5_OF_5__ZERO_CURRENT_SYSTEM_PAIR_QUERIES__TMG4_G12_M01_EDGE_PATH_PARENT_RELEASE_HOLD`

它明确 `current_system_asset_support_claimed=false`、`current_system_backend_bound=false`，不能通过“后端类存在/可导入”推导当前系统可查询。连续 edge 方法也已有静态合成验证，但未获得当前 pair、motion、scene、ACM 全绑定信用。应复用其 schema、单位防护、UNKNOWN/UNSAFE/SAFE 判定和负控，再依据原合同完成生产绑定；不能把 11,166 对未评估对象批量标 SAFE。[后端 Gate](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_SYSTEM_PAIR_ORACLE_BACKEND_V1/results/M01_SYSTEM_PAIR_ORACLE_BACKEND_GATE_V1.json:1>)；[edge 方法 Gate](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_QUERY_INFRASTRUCTURE_V1/QUERY_INFRASTRUCTURE_GATE_V1.json:1>)。

## 7. Sim13 20/20 是真实后续子项成果，父 TMG-6 没有重发

2026-08-25 后端子 Gate 的精确 verdict 是 `SIM13_NC_REGISTRY_20_OF_20_PASS__PENDING_OWNER_REVIEW__NO_RELEASE_CREDIT`；5/5 后端工单已关闭，`MECH_RL_SYSTEM_INTERFACE_V2.yaml` 实例已经存在。不得继续写成“五个后端均未实现、接口不存在”。

但 append-only addendum 显式保留 `historical_15_of_20_superseded=false`、`full_tmg6_reissue_executed=false`，精确 verdict：

`SIM13_POST_TERMINAL_BACKEND_SUBSCOPE_20_OF_20_PASS__FULL_TMG6_NOT_REISSUED__ABORT_ONLY__NO_RELEASE_CREDIT`

2026-08-29 reconciliation 再确认 `NO_CONFLICT__DIFFERENT_SCOPES__ADDENDUM_ALREADY_ADJUDICATES`，研究侧父状态仍为 `PARENT_15_OF_20__ABORT_ONLY__NOT_REISSUED`。后端成果可用于结构/模型/schema 诊断复用；不能继承为 G12 PASS、当前系统绑定、非 ABORT 抓取、真实接触、RL/VLA 训练或发布许可。[20/20 原 Gate](<F:/China Graduate Future Flight Vehicle Innovation Competition/30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_20_OF_20_GATE_V1.json:1>)；[addendum 父子语义](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_b/sim13_post_terminal_handoff_addendum_v1/SIM13_POST_TERMINAL_HANDOFF_ADDENDUM_GATE_V1.json:140>)；[08-29 裁决](<F:/China Graduate Future Flight Vehicle Innovation Competition/30_simulation/sim_13_viability_extension_r1/00_authority/SIM13_CURRENT_PARENT_CHILD_AUTHORITY_RECONCILIATION_V1.json:76>)。

## 8. 动力学、控制“父 HOLD”和后续诊断子 PASS 同时成立

父动力学精确 verdict 为 `R2_DYNAMICS_ENGINEERING_HOLD__DG1_UNIT_METRIC_DG2_INDEPENDENT_CONSERVATION_DG3_DG4_DG5_OPEN__NO_RELEASE_CREDIT`，候选满足 1/6。后续有 DG1/DG2 15/15、DG3 30/30、DG4 15/15、DG5 16/16 **候选子 Gate**；应承认这些已完成的有限工作，而非照抄父 Gate 的旧实现缺口为“现在仍完全没有”。这些子 Gate 逐一保留 parent HOLD、物理参数/当前绑定限制、next-stage=false 与 release=false。抓后 spatial inertia kernel 的合成 Gate及外审仍明确 `CURRENT_C08_C09_NOT_EVALUATED`。

控制侧已有 task-space metric 候选、时域 twist tracking 诊断及独立审计；时域原 Gate 仍 **19/20 REPEAT_REQUIRED**，单 G04 为父 HOLD 指纹不匹配。随后重绑定 **16/16**、metric 独立复算 **17/17**，不覆盖原 Gate。汇合 V3 **21/21** 的精确 verdict 为 `CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_V3_APPEND_ONLY_EVIDENCE_PASS__ORIGINAL_TIME_DOMAIN_GATE_REMAINS_REPEAT_REQUIRED__NO_AUTHORITY_UPGRADE`。[动力学父 Gate](<F:/China Graduate Future Flight Vehicle Innovation Competition/30_simulation/r2_dynamics_engineering_closure/results/R2_DYNAMICS_ENGINEERING_GATE_V1.json:1>)；[DG1/DG2 子 Gate](<F:/China Graduate Future Flight Vehicle Innovation Competition/30_simulation/r2_dynamics_engineering_closure/dg1_dg2_candidate_v2/results/R2_DG1_DG2_CANDIDATE_GATE_V2.json:1>)；[后续汇合的原文约束](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/current_r2_mechanical_dynamics_control_increment_v3/CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_GATE_V3.json:44>)。

全部当前源 Gate 的 exact scalar verdict、行定位、SHA-256 见 [authority_source_extract.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/PRE_MODE_SWITCH_MECHANICAL_STATE_AUDIT_20260905/authority_source_extract.json>)。未提供日期的 deterministic Gate 不补造生成日期。

## 9. 当前机械到具身智能的实质缺口

R2 联合 Gate 仍 **4/13**，`joint_system_ready=false`、`ready_for_physics_gated_embodied_intelligence=false`，精确 verdict：

`R2_DYNAMICS_CONTROL_SYSTEM_HOLD__MECHANICAL_DYNAMICS_CONTROL_SAFE_SIM13_GATES_OPEN__NO_PATH_SEARCH__NO_RELEASE_CREDIT`

下一步工程接合至少要把已有候选变为同一配置、同一版本的受控消费关系：机械 G12 与 M01/线束/碰撞路径；当前质量/惯量与 frame 的绑定；双翼柔性激励和任务时序；6R+2P 执行器 effort/rate/delay/bandwidth、轮组资源阈值；接触 patch/frame/标定与抓前→抓后 plant 切换；SAFE 当前树重放和独立复核；Sim13 当前系统绑定与 Owner scope disposition。当前 frame tree 尚不覆盖 tool flange、F/T sensor、wrist camera、active grasp、target contact frames。**这些是当前全系统交接缺口，不能用不同配置上的算法 PASS 消掉。**[联合 Gate](<F:/China Graduate Future Flight Vehicle Innovation Competition/30_simulation/r2_dynamics_control_system_closure/results/R2_DYNAMICS_CONTROL_SYSTEM_GATE_V1.json:4>)；[控制父 Gate](<F:/China Graduate Future Flight Vehicle Innovation Competition/30_simulation/r2_control_engineering_closure/results/R2_CONTROL_ENGINEERING_GATE_V1.json:72>)；[frame 缺项](<F:/China Graduate Future Flight Vehicle Innovation Competition/30_simulation/sim_13_viability_extension_r1/00_authority/SIM13_CURRENT_PARENT_CHILD_AUTHORITY_RECONCILIATION_V1.json:169>)。

既有 accepted B601 10 link/9 joint（6R+1 fixed+2P）、Unified R2 19 link/18 joint 的源码发射资产、C01 设计质量 31.022864807342987 kg、C01–C09 设计质量/CG/惯量账本可按各自 authority 复用；不是 AS_BUILT，也不是 Mode A 新几何自动继承的动力学绑定。

## 10. 两类易造成假完成的后续记录已隔离

F5R2 frontier 文件实际上写于 **2026-08-26**，是只读侦察摘要；其中 `FACTUALLY SUPERSEDED` 语句不能胜过随后明确 `historical_15_of_20_superseded=false` 的 addendum 与 08-29 reconciliation。其可用价值是导航到 Route-C、Sim13 和 ODR50–57 后续材料，不是父 Gate 重发证据。[F5R2 日期及 caveat](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/F5R2_TERMINAL_CLOSURE_V1/00_frontier/CURRENT_FRONTIER_FABLE5_V1.json:3>)。

更后的 Sim13 v4 合成夹爪 B4G 包也不能继承到当前 R2：所见 `SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json` 为 active=true，登记三例 `MIDPOINT_COARSE` 的 `B4F-G06-ENERGY-MINUS-WORK-IDENTITY` 失败；`PRIOR_FINAL_CREDIT_SUPERSEDED` 中 replacement summary=null。这里仅记录不同配置的合成实验状态，不展开该任务、不把原始案例存在说成最终 Gate PASS。[B4G 无效记录](<F:/China Graduate Future Flight Vehicle Innovation Competition/30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b4g_post_freeze_synthetic_jaw_retraction_execution/results/SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json:1>)。

## 本审计可复核的边界

- `SOURCES_READ`：82 个指定入口、原 Gate、候选 Gate、增量及原始 ODR60 附件；路径列表见 [authority_sources.txt](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/PRE_MODE_SWITCH_MECHANICAL_STATE_AUDIT_20260905/authority_sources.txt>)。本数字是来源数，不是验收判据数。
- `FILES_CHANGED`：仅本目录 `05_AUTHORITY_AND_EMBODIED_HANDOFF.md`、`authority_collect.py`、`authority_sources.txt`、`authority_source_extract.json`。
- `FROZEN_BOUNDARY_CHECK`：采集程序只读来源并计算哈希；未导入工程代码、未调用生产 evaluator。来源中的历史 PASS 只复述，未重新验证其执行正确性。
- `NEXT_HUMAN_GATE`：本轮完成只读审计后再决策当前 Mode A 后续路线。既有有限授权和局部 Gate 可沿来源复用；本报告不签发 Mode B、M01 运行、系统联动或发布许可。
