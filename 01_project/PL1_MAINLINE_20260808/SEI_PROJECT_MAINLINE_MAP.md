# SEI_PROJECT_MAINLINE_MAP.md — M0–M14 工程主线

> Task: `SEI-PL1-PROJECT-MAINLINE-RECONSTRUCTION`  
> Snapshot: 2026-08-08, ROOT A HEAD `5c5addea00ddb70d86a5cc37a88bbcda50350e43`  
> Rule: 本图只指定“当前权威及其适用边界”。`PRESENT`、`CURRENT`、`PASS`、`AUTHORIZED` 彼此不等价；donor/reference 永不自动取得项目 authority。

## 总裁定

- 项目面对的两个入口是 ROOT A（当前工程主线）与 ROOT B（外部开源/仿真/参考资料）。稳定 Archive 逻辑从属于 ROOT A，但不是第三个日常工作入口，也不参与运行时。
- 当前机械层只有一个机器选定候选：F3R2 operational package；它复用 F3R1 V3 顶层装配字节，并增加姿态、定义、间隙和数字线程证据。它仍是 `PENDING_HUMAN_REVIEW`，不是人工接受的制造基线。
- B601 L0 动力学/运动学真值是 accepted URDF；SolidWorks/FreeCAD/mesh 分别是工程表达、参数子集或仿真表达，不得反向覆盖 URDF 的科学字段。
- 当前项目仿真权威是 ROOT A 内的确定性 Python/numpy 链。SpaceRobotEnv、Basilisk、Chrono 等均为参考实现或交叉验证候选，`runtime_dependency=false`。

## M0 — 项目使命与比赛需求

| 字段 | 裁定 |
|---|---|
| CURRENT AUTHORITY | `10_research/00_project_architecture/system_architecture.md`；比赛执行合同以 `10_research/competition_convergence/mission_demo_contract.yaml` 与 `launch_manifest.md` 为准。 |
| CURRENT FILES | `10_research/00_project_architecture/`；`10_research/competition_convergence/`。 |
| CURRENT STATUS | 使命、场景和比赛演示链已冻结；比赛交付已完成，研究工程主线继续。 |
| LATEST VALID RESULT | `COMPETITION_DEMO_READY`，17/17；测试 19/19、red-team 15/15。 |
| SUPERSEDED FILES | 早期聊天总结、未绑定 Gate 的演示叙事及旧项目总览只作历史背景，不覆盖当前合同/manifest。 |
| OPEN HOLDS | 比赛演示通过不等于机械制造、HIL 或飞行认证通过；任何变更均触发 fail-closed 复核。 |
| NEXT TASK | 保持冻结演示证据；仅在上游工程 authority 变更后重跑受影响链。 |

## M1 — 航天器总体构型

| 字段 | 裁定 |
|---|---|
| CURRENT AUTHORITY | `structure/` 的系统结构接口文件 + `20_engineering/stage1_spacecraft_layout/` 的总体布局、坐标系与系统预算。 |
| CURRENT FILES | `structure/INTERFACE_ARM_BUS.yaml`、`structure/BOM_12U.yaml`、`structure/LOAD_PATH.md`；`20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/`。 |
| CURRENT STATUS | `ACTIVE / LOW-CONFIDENCE SYSTEM BUDGET`；总体构型可用于接口与布局，不具备制造放行。 |
| LATEST VALID RESULT | stage-1 layout v0 已形成；坐标系与接口表可追溯。 |
| SUPERSEDED FILES | 无 Gate 的早期视觉构型和散落截图不拥有 authority；历史 CAD 代只在 M14/谱系中保留。 |
| OPEN HOLDS | 系统质量预算 `UNSOURCED_BLOCKED`；太阳翼质量仍有 5–10× 占位偏差；总体 FEA 未闭合。 |
| NEXT TASK | 取得可追溯部件质量/惯量与结构载荷输入，再更新系统预算和结构验证。 |

## M2 — B601 机械臂机械设计

| 字段 | 裁定 |
|---|---|
| CURRENT AUTHORITY | L0：`20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf`；L1：F3R2 operational package 中的 B601 carrier 与当前 top assembly。 |
| CURRENT FILES | accepted URDF；`20_engineering/F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/03_native_cad/B601_ARM_B51_COPY/`；`20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/`。 |
| CURRENT STATUS | `CURRENT_MACHINE_SELECTED_MECHANICAL_CANDIDATE / PENDING_HUMAN_REVIEW`；F3R1/F3R2 已 hash-copy 至 ROOT A，但仍未 Git 跟踪/CM 接受。 |
| LATEST VALID RESULT | F3R2 final gate 11/14 + 4 HOLDs；top SHA-256 `19D85E9C703BEC107396AE84DAB7B12DE5722434FC7D5474B3A5A144A1B590D0`。 |
| SUPERSEDED FILES | V0.1–B5.1R1、F3/F3R1 gate 代均保留为谱系/供体；FreeCAD C1-A 是参数子集，不是当前 native top。 |
| OPEN HOLDS | 人工批准、CM/备份、10 条外部 native references、冷重开、native pair attribution；current carrier 与 protected D2 donor 已发生可解释的重存差异。 |
| NEXT TASK | 先完成人审、CM 接受/备份与 reference repair；任何 V4 CAD 写入须获得 scope-specific 授权。 |

## M3 — 机械接口与收拢机构

| 字段 | 裁定 |
|---|---|
| CURRENT AUTHORITY | D-1 mount 几何 `20_engineering/config/geometry/arm_mount_v1.yaml`；F3R2 G30/G31/G32 定义与 gate evidence。 |
| CURRENT FILES | F3R2 `03_native_cad/`、`04_configurations/`、`05_clearance/`、`10_digital_thread/`；F3R1 G3 interface closure recommendation。 |
| CURRENT STATUS | 接口栈已定义；stow/restraint 仍 `ENGINEERING_HOLD`，鞍座为占位壳体。 |
| LATEST VALID RESULT | T_SM 栈冻结；8 configs present/gate-checked；C12 在 t=0 以 0.0011 mm 占位接触失败，之后恢复间隙。 |
| SUPERSEDED FILES | 将 frame、adapter face、boss face 混为同一 T_SM 的旧冲突叙事；把 8 configs 写成全部 differentiated 的旧表述。 |
| OPEN HOLDS | 真实 G07/G08/Mid 支撑未建；SERVICE/PARTIAL 姿态 authority 不完整；连续路径只覆盖 1/6 已定义段。 |
| NEXT TASK | P0 先建 WING_ROOT_LUG；P1 再建真实支撑并重跑连续 clearance，随后才允许 ARM HDRM。 |

## M4 — 航天器结构、太阳翼与 HDRM

| 字段 | 裁定 |
|---|---|
| CURRENT AUTHORITY | 系统结构接口由 `structure/` 管理；F3R2 只提供当前 native representation 和 G3x 定义证据。 |
| CURRENT FILES | `structure/`；F3R2 G30–G33 定义；F3R1 `F3R1_G3_INTERFACE_CLOSURE_RECOMMENDATION.md`。 |
| CURRENT STATUS | 中央结构/载荷路径有工程定义；太阳翼 donor 可用但根部接口未闭合；ARM HDRM 仅定义/演示级。 |
| LATEST VALID RESULT | 四块 V2.2 panel donor 已集成；真实 hinge pin 与 panel donor 相差 30.0 mm，形成明确 P0 开口。 |
| SUPERSEDED FILES | 仅凭视觉外形宣称 wing-root/HDRM 完成的模型；V2.3 hash-drift 代已拒绝。 |
| OPEN HOLDS | WING_ROOT_LUG 未建；真实支撑、HDRM 选型、载荷/FEA、camera/harness 均未闭合。 |
| NEXT TASK | 严格按 `WING_ROOT_LUG → real saddles → ARM HDRM → camera/harness → gripper fingers` 执行。 |

## M5 — 动力学模型

| 字段 | 裁定 |
|---|---|
| CURRENT AUTHORITY | `30_simulation/sim_11_coupled_dynamics/` v1.1；刚性锚为 `sim_05_free_floating_arm/`。 |
| CURRENT FILES | sim_11 source/config/results；`20_engineering/config/coupled_scene/`；sim_05 frozen evidence。 |
| CURRENT STATUS | `LIMITED + FROZEN`。模型结构闭合，但关键物理参数仍 provisional。 |
| LATEST VALID RESULT | `SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS`；sim_05 22/22 VERIFIED、基座反冲峰值 19.20°。 |
| SUPERSEDED FILES | sim_11 v1.0 的 G4 fail 由有限接触带宽 v1.1 取代，但旧 fail 作为负证据保留。 |
| OPEN HOLDS | panel modal 参数与 `T_c=20 ms` 未实测；`sim_05/.../b601_model.py:39` 当前 URDF 路径断裂，阻止全新复跑。 |
| NEXT TASK | 经治理批准修复一行路径；取得 panel modes 与 gripper contact time 后才允许参数转正/重跑。 |

## M6 — 非合作目标捕获

| 字段 | 裁定 |
|---|---|
| CURRENT AUTHORITY | `30_simulation/common/capture_impulse.py` → sim_06 → sim_10 → sim_12 → SAFE-00 的冻结链。 |
| CURRENT FILES | `30_simulation/sim_06_capture_impulse/`、`sim_09_grasp_evaluator/`、`sim_10_mission_feasibility/`、`sim_12_strategy_feasibility/`。 |
| CURRENT STATUS | 刚体/冲量/策略可行域已验证；正式安全候选为 0，柔性安全证据未闭合。 |
| LATEST VALID RESULT | sim_10 `SIM10_GATES_PASS`（9002 点）；sim_12 `SIM12_PHASE1_GATES_PASS`（16 proof units）；e15/e16 保留负结果。 |
| SUPERSEDED FILES | 把“admissible”写成“formally safe”的旧叙事；未绑定冻结阈值/哈希的捕获结果。 |
| OPEN HOLDS | e16 柔性证据 UNKNOWN；ASM-00 `BLOCKED_BY_MISSING_PARAMETERS`；HAG-A/interface SSOT 尚未授权。 |
| NEXT TASK | 先关闭接口参数 Gate；ASM-01 Phase A 上限仍为 screening-only，不得直接宣称连续接触安全。 |

## M7 — 控制与 SAFE-00

| 字段 | 裁定 |
|---|---|
| CURRENT AUTHORITY | `30_simulation/control_01_end_effector_tracking/`、`control_02_base_attitude/` 与 `safety_00_runtime_gate/`。 |
| CURRENT FILES | 上述 source/config/results；`20_engineering/config/{control_scene,attitude_stab,safety_gate}/`。 |
| CURRENT STATUS | CTRL-01 冻结负结果；CTRL-02 limited/provisional；SAFE-00 47/47 PASS 但 `PENDING_REVIEW`, `next=false`。 |
| LATEST VALID RESULT | CTRL-01 `REPEAT`；CTRL-02 `PASS_WITH_PROVISIONAL_SCOPE`；SAFE-00 deterministic gate 47/47。 |
| SUPERSEDED FILES | 把 provisional actuator 当硬件验证、或把 SAFE-00 PASS 外推为执行授权的叙事。 |
| OPEN HOLDS | SAFE-00 LOOP-6 独立复审为空；W1-R12 wheel torque 冲突；执行机构参数未硬件冻结。 |
| NEXT TASK | 完成独立 review，并在硬件参数转正后复测 CTRL-02/SAFE-00；保持 `next=false`。 |

## M8 — 具身智能、VLA 与 Physics Tool

| 字段 | 裁定 |
|---|---|
| CURRENT AUTHORITY | 仅合同/研究规划：`10_research/space_embodied_robotics/space_embodied_agent_v1_contract.md`、`physics_gated_agent_plan.md`、`10_research/vla/`。 |
| CURRENT FILES | 上述文件；`20_engineering/config/competition_prototype/` 与 `30_simulation/module_cards/` 已 hash-verified 回收至 ROOT A。 |
| CURRENT STATUS | `CONTRACT_OR_RESEARCH_SUPPORT_ONLY / NOT_IMPLEMENTED / NO_EXECUTION_AUTHORITY`；回收内容仍 untracked、待 CM。 |
| LATEST VALID RESULT | 物理链接链 15/15 已恢复并与治理区源哈希一致；没有模型训练、策略执行或 scientific gate。 |
| SUPERSEDED FILES | “相关目录 ABSENT”已被 2026-08-08 salvage 取代；规划文档不得被当作实现。 |
| OPEN HOLDS | 无 Isaac/MuJoCo/ROS2 项目集成；VLA=`PROTOCOL_DRAFT`，Physics Tool=`DRAFT_NOT_IMPLEMENTED`。 |
| NEXT TASK | 先完成 CM 接受与接口单源化，再单独批准最小 executable prototype；不得复用 reference checkout 伪装成项目实现。 |

## M9 — Isaac、MuJoCo、ROS2 与外部仿真器

| 字段 | 裁定 |
|---|---|
| CURRENT AUTHORITY | 项目层没有权威 external-engine adapter；M9 当前 authority 是 PL1-C 的“零项目集成”边界裁定。 |
| CURRENT FILES | ROOT A `80_third_party/external/spacecraft_layout_refs/spacerobotenv/SpaceRobotEnv`（reference only）；ROOT B 的 open-source/dynamics registers。 |
| CURRENT STATUS | 项目集成、Gate、冻结结果、运行时依赖均为 0；SpaceRobotEnv 是 legacy Gym + `mujoco_py` 参考 checkout。 |
| LATEST VALID RESULT | SpaceRobotEnv clean tree @ `155989c2ae94a3afeedf9b8601b6125d83b9c097`，与 `F:/Robotic arm` duplicate tree 相同；未做 B601 适配。 |
| SUPERSEDED FILES | “项目内完全没有 MuJoCo 源码”已被 reference checkout 事实取代；但“没有项目级 MuJoCo 集成”仍成立。 |
| OPEN HOLDS | reference source 错置于 ROOT A；迁往 ROOT B 前必须同步 literature manifest 路径；ROS2/Isaac 仍无项目实现。 |
| NEXT TASK | 仅在独立批准的交叉验证波次中选最小 adapter；否则维持 `REFERENCE_ONLY`。 |

## M10 — HIL 与实物

| 字段 | 裁定 |
|---|---|
| CURRENT AUTHORITY | `NONE`。不存在已授权 HIL authority。 |
| CURRENT FILES | 无项目 HIL 执行目录；`10_research/00_project_architecture/experiment_roadmap.md` 仅为计划。 |
| CURRENT STATUS | `NOT_STARTED`。 |
| LATEST VALID RESULT | 无 H0–H3 Gate，无硬件闭环结果。 |
| SUPERSEDED FILES | `F:/Robotic arm` 的历史本机路径/README 不能作为 HIL 结果或当前 runtime dependency。 |
| OPEN HOLDS | 无批准试验台、测量链、硬件参数冻结、SOP 与安全审查。 |
| NEXT TASK | 先签发 HIL charter、硬件清单、校准/安全协议及 H0 Gate；此前不得创建“已验证”叙事。 |

## M11 — Dataset

| 字段 | 裁定 |
|---|---|
| CURRENT AUTHORITY | `NONE`；ROOT B 的 SPEED+ 等代码只属参考。 |
| CURRENT FILES | 无项目数据集生成/版本化目录；VLA 文档中的 schema 仅是计划合同。 |
| CURRENT STATUS | `NOT_STARTED`。 |
| LATEST VALID RESULT | 无 dataset Gate、manifest、seeded generation 或发布包。 |
| SUPERSEDED FILES | 外部 repo 的示例数据、截图、仿真 CSV 不得汇总成“项目 dataset”。 |
| OPEN HOLDS | 缺来源、许可、schema、split、seed、质量 Gate 与 storage policy。 |
| NEXT TASK | 先定义 dataset charter/manifest/schema/provenance，再批准确定性最小生成波次。 |

## M12 — Competition Demo

| 字段 | 裁定 |
|---|---|
| CURRENT AUTHORITY | `10_research/competition_convergence/` 的 contract、manifest、source、tests 与 gate。 |
| CURRENT FILES | `mission_demo_contract.yaml`、`three_scenario_manifest.yaml`、`competition_gate_check.json`、`competition_execution_report.md`；媒体在 `40_evidence/artifacts/competition_convergence/`。 |
| CURRENT STATUS | `DONE / FROZEN / OFFLINE`。 |
| LATEST VALID RESULT | `COMPETITION_DEMO_READY` 17/17；19/19 tests；15/15 red-team。 |
| SUPERSEDED FILES | 修复前失败运行与旧 launch artifacts 仅作负证据，不覆盖最终 gate。 |
| OPEN HOLDS | 该 demo 不包含 HIL、连续接触物理解算、机械制造或飞行认证。 |
| NEXT TASK | 无 lane 内任务；仅当冻结 upstream hash 改变时触发受控重放。 |

## M13 — Paper 与 Research

| 字段 | 裁定 |
|---|---|
| CURRENT AUTHORITY | `10_research/00_project_architecture/paper_structure_plan.md`、`10_research/paper1_architecture.md` 与 `50_literature/references/manifest.yaml`。 |
| CURRENT FILES | `50_literature/`；`10_research/{research_questions,theory_graph,contribution_map,research_os_01,research_os_02}/`。 |
| CURRENT STATUS | `ACTIVE`；研究支持目录已回收但仍 untracked/待 CM，科学结论仍受冻结证据边界约束。 |
| LATEST VALID RESULT | paper knowledge audit：45 manifest、44 PDFs、34 cards、1 个全文缺口，0 errors/warnings。 |
| SUPERSEDED FILES | 29-card 旧计数；仅题录或缺全文的来源不得写成已精读证据。 |
| OPEN HOLDS | claim–evidence 矩阵未填完；Fig.1/Fig.5 待 Gate-0 重算；禁止为论文启动未经授权的新实验。 |
| NEXT TASK | 补核心 M2 阅读卡与 claim–evidence 矩阵；只引用与其 evidence tier 相称的结论。 |

## M14 — Verification、Gate 与 Evidence

| 字段 | 裁定 |
|---|---|
| CURRENT AUTHORITY | 各域冻结 Gate JSON/报告；当前跨域入口为 `01_project/PL1_MAINLINE_20260808/`；稳定 CM SSOT 位于 `F:/SEI_PROJECT_ARCHIVE/CONFIGURATION_MANAGEMENT/20260807_CONSOLIDATION/`。 |
| CURRENT FILES | `40_evidence/`；F3R1/F3R2 gates/reviews；PL1-A–G；`PL1-V/validate_pl1.py` 与独立评审。 |
| CURRENT STATUS | 主线重建与两 Root 逻辑边界已闭合；工程仍带显式 HOLD。健康检查结构项全 PASS，整体仅因工作树 dirty 为 `FAIL 1`。 |
| LATEST VALID RESULT | F3R1 363/363、F3R2 482/482、supplemental chain 15/15、CM3A 6/6 均 source/dest SHA 相同；root-level `UNKNOWN=0`。 |
| SUPERSEDED FILES | pre-salvage 的 `WT-only/ABSENT` 报告、旧 HEAD/count/health pins 以及把 Archive/Root B 当 runtime 的说明。 |
| OPEN HOLDS | Git/CM 接受、冷备份、3,432-file 历史 CAD 谱系、880-file stage3 closure、Robotic arm witness、donor license、sim_05 path。 |
| NEXT TASK | 人工审阅 PL1 与 F3R2；选择 Git/CM/DR 策略；按独立 dependency-island Gate 处理剩余资产，禁止批量删除。 |

## 五分钟导航

1. 当前盘面：`PROJECT_CURRENT_STATUS.md`。
2. 机械入口：`MECHANICAL_START_HERE.md`。
3. 当前机械裁定：`PL1-B/CURRENT_MECHANICAL_BASELINE_RULING.md`。
4. 动力学/捕获：`PL1-C/DYNAMICS_MAINLINE.md`。
5. 外部参考：ROOT B `REFERENCE_LIBRARY_START_HERE.md`。
6. 迁移与 HOLD：`PL1-G/TWO_ROOT_EXECUTION_PLAN.md`、`PL1-G/NEW_CONTRADICTION_REGISTER.md`。
7. 独立复核：`PL1-V/PL1_INDEPENDENT_REVIEW.md`。
