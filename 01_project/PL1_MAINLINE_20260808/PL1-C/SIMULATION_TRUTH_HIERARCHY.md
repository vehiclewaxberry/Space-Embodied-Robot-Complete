# SIMULATION_TRUTH_HIERARCHY.md — PL1-C 仿真真值层级与运行时依赖核查

> 日期：2026-08-08 | 范围：ROOT A（F:\China Graduate Future Flight Vehicle Innovation Competition）、ROOT B（F:\SPACE_ROBOTICS_REFERENCE_LIBRARY）、CAE 库（F:\Mechanical structure modeling and simulation，仅索引级）
> 方法：只读核查；gate verdict 以各 `*_gate_check.json` 机器裁决原文为准；冻结语义以 `10_research/00_project_architecture/simulation_scenario_map.md` 为准。

## 1. 真值层级（高 → 低）

### Tier 0 — 治理/冻结层（决定什么能被称为真值）
- `10_research/00_project_architecture/simulation_scenario_map.md` — 场景/Gate 地图冻结；`NO_NEW_SIMULATION — STOP_AFTER_ARCHITECTURE_FREEZE`；15 个 Gate JSON 登记（14 权威 + 1 partial）。
- `10_research/framework_convergence/tool_stack_decision.md` — 外部工具裁决（NOW=0；Pinocchio/Basilisk=NEXT；SPART/MuJoCo/Isaac=LATER；SpaceDyn=AUDIT_ONLY；Adams=NOT_NEEDED）。
- `F:\SEI_PROJECT_ARCHIVE\CONFIGURATION_MANAGEMENT\20260807_CONSOLIDATION\` — CM SSOT（PROJECT_LIBRARY_INDEX.yaml / ASSET_AUTHORITY_MATRIX.csv / CANONICAL_ROOT_REGISTER.yaml）。

### Tier 1 — PROJECT_AUTHORITY（当前科学真值脊柱，全部 FROZEN）
| 资产 | 领域 | verdict |
|---|---|---|
| `30_simulation/common/rigid_body.py` + `common/capture_impulse.py` | 共享求解层（自由漂浮传播 / 精确捕获冲量） | Gate A passed；被下游全部只读 import |
| `30_simulation/sim_05_free_floating_arm/` | 刚性自由漂浮动力学锚（真实 B601 URDF） | VERIFIED（22/22 复跑 2026-07-17） |
| `30_simulation/sim_06_capture_impulse/` | 捕获动量锚（40 工况） | VERIFIED |
| `30_simulation/sim_11_coupled_dynamics/` | 星-臂-帆板全耦合主线（路线 A） | `SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS`（LIMITED） |
| `30_simulation/sim_10_mission_feasibility/` | 任务可行域 | `SIM10_GATES_PASS`（VERIFIED） |
| `30_simulation/sim_12_strategy_feasibility/` | 策略选择 Phase 1 | `SIM12_PHASE1_GATES_PASS`（VERIFIED） |
| `30_simulation/safety_00_runtime_gate/` | 运行时安全裁决核 | `PASS`（next=false，PENDING_REVIEW） |
| 数据真值：`mass_inertia_budget_v1.csv`、`20_engineering/config/geometry/*.yaml`、`config/coupled_scene/coupled_model_v0.yaml`、`cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf`（sha256 `1bc2b748...`） | 模型/参数 SSOT | frozen/registry-locked |

### Tier 2 — PROJECT_ACTIVE（当前引用但受限）
- `sim_08_detumble_actuator_budget/`（LIMITED；执行机构常数为类值占位）
- `sim_09_grasp_evaluator/`（E1 LIMITED；admissible ≠ formal safe）
- `e16_sync_capture/`（LIMITED；离线扫描，formal safe=0，柔性 UNKNOWN）
- `control_02_base_attitude/`（模块 PASS 但 PROVISIONAL 执行器口径；7/16 时窗内稳定）

### Tier 3 — VALIDATION_CASE（认证/对照试验，含冻结负结果）
- `sim_07_ancf_flexible/`（组件级 ANCF 响应与 benchmark；LIMITED）
- `e15_ancf_certification/`（`REPEAT_ANCF_CERTIFICATION`，交叉求解器差 5.637%；NEGATIVE）
- `e15_core_coverage/`（覆盖 PASS / 科学 `REPEAT_CORE_NO_SAFE_CANDIDATE`；NEGATIVE）
- `control_01_end_effector_tracking/`（`REPEAT`；NEGATIVE——严格 6D 零空间为零、冻结增益超差）
- `asm_00_interface_preflight/`（`BLOCKED`；接口参数缺失）

### Tier 4 — SUPERSEDED（被主线取代的冻结早期资产）
- `sim_01_free_flight/`、`sim_02_target_tumble/`（2026-07-09 v0 基线，LIMITED+FROZEN）
- `sim_03_arm_reaction/`（平面约化模型 → 被 sim_05 明确取代）
- `sim_04_capture_corridor/`（v0 启发式 → 被 sim_06 精确模型取代；目录内 v2 精确口径保留；24 个 false-safe 网格点已证伪）
- 历史快照：`40_evidence/artifacts/visualization/e15_gate_evidence_snapshot_20260714/`（E1.5 冻结证据）

### Tier 5 — REFERENCE_IMPLEMENTATION / THIRD_PARTY（ROOT B；可参考、可审计，**不是项目真值**）
- 自由漂浮/多体：REFLIB1_SpaceDyn（AUDIT_ONLY，无许可证）、REFLIB1_SPART（LGPL-3，独立工具）、REFLIB1_EXUDYN（BSD-like）、REFLIB2_06 ANCF_beam（无许可证，只读方法）、REFLIB2_04 chrono（sandbox only）
- 捕获：REFLIB1_MATLAB_space_debri_capturing_sim（MIT）
- 姿态/ADCS：REFLIB2_03 basilisk（NEXT 锚点候选）
- ROS2/Isaac/具身：REFLIB1_spaceros_demos、REFLIB1_space_robotics_bench、REFLIB2_04 {isaac, int-ball2_isaac_sim, space-ros, astrobee}（均 post_competition / LATER）
- 出处与许可台账：ROOT B `REFLIB1__root_/REFERENCE_INDEX.json`（含各仓 head SHA/日期/许可/allowed_use）、`REFLIB2_00_manifest/00_manifest/PUBLIC_REFERENCE_*`

### Tier 6 — TEACHING_CASE / CAE_EXAMPLE（教学；禁作工程真值）
- `REFLIB1_spacedyn_freefloating_demo/`（项目自建教学 wrapper，DEMO_ONLY 合成参数；RUNTIME_STATUS_20260729/30 留档）
- CAE 库 SEI 相关条目（仅索引级）：`6自由度机械臂多体动力学.mp4`、`机械手关节瞬态动力学评估.x_t`、`机械臂夹爪model.zip`、`连杆型灵巧手动力学仿真.mp4`、`Ansys_CAE/vibration_platform_six_DOF/`、`Ansys_CAE/Robot_Humanoid/`（ParaCS 训练营）、`train/Robot_day{1,2}/`、`25·五爪夹持机构SolidWorks三维建模实战.zip`、`智元机器人瞬态分析.mp4`/`智元机器人整机.zip`
- CAE 库中未发现任何 B601/航天器/空间结构专属动力学资产（文件名级扫描：b601|space|satellite|空间|帆板 零命中，"商业航天*"为发动机教学视频，与 SEI 动力学主线无关）。

## 2. 责任矩阵（谁拥有什么）

| 领域 | 当前权威 | 状态 | 备注 |
|---|---|---|---|
| 捕获动力学（动量/冲量） | `common/capture_impulse.py` + sim_06；柔性扩展 = sim_11 `capture_solver.py`（刚性极限==sim_06 机器断言） | VERIFIED / LIMITED | 捕获 ≠ 消旋（sim_06 头条结论） |
| 姿态动力学 | 科学层：sim_05（刚性锚）→ sim_11（耦合）；控制层：CTRL-02（PROVISIONAL） | VERIFIED / LIMITED | sim_01 已降为早期证据 |
| 接触模型 | sim_11 `contact_window.py` v1.1（有限接触带宽，T_c=20 ms PROVISIONAL） | LIMITED | 持续接触/卡滞：ASM-01 PLAN_ONLY，未实现；无项目集成/权威 MuJoCo/LCP 引擎（ROOT A 仅有 SpaceRobotEnv 参考 checkout） |
| 柔性附件模型 | 系统级：sim_11 FFR 帆板（占位模态）；组件级：sim_07 ANCF 梁 | LIMITED | e15 ANCF 认证未闭环（5.637%）；SSOT=`config/geometry/flexible_appendage_v1.yaml` |
| 任务可行域 | sim_10 | VERIFIED | FLEX=UNKNOWN_NOT_IN_CRITERIA |
| 策略选择 | sim_12 Phase 1 | VERIFIED | 账本仲裁 `10_research/sim_12/momentum_ledger.md` |
| 运行时安全 | SAFE-00 | VERIFIED（PASS，next=false） | 证据与执行授权分离 |
| 外部交叉验证 | 无（Pinocchio/Basilisk=NEXT，未启动） | NOT_STARTED | 合同见 tool_stack_decision §4 |

## 3. 运行时依赖核查：'project runtime must not read from ROOT B checkouts'

**核查方法**：对 ROOT A 全仓（排除 .git）按 `F:/` / `F:\` 绝对路径 grep（py/yaml/json/md/ps1/sh/toml/cfg/ini/txt），并专项搜索 `SPACE_ROBOTICS_REFERENCE_LIBRARY`、`space_robotics_references`、`SPACE_ROBOTICS_PUBLIC_REFERENCE`、`Robotic arm`。

**结论：通过。** 30_simulation、20_engineering/config、10_research 可执行代码与配置中**没有任何**指向 ROOT B（或已退役前身 `F:\space_robotics_references`）的引用。仿真链只读 repo-relative 路径 + `20_engineering/` SSOT。逐项发现：

1. **ROOT B 零运行时引用** —— `SPACE_ROBOTICS_REFERENCE_LIBRARY` 仅出现在 `PROJECT_START_HERE.md` 的状态表（文档指针）；`F:/space_robotics_references/...` 仅残留在 `knowledge/B_cubesat_structure_practice.md:5`、`knowledge/B_assets_and_conventions.md:6-7`（**文档漂移**，指向已退役路径，非代码）。
2. **`F:\Robotic arm` 零存活引用** —— 唯一曾存在的配置引用已按 CM3 修复为 repo-relative（`20_engineering/config/geometry/arm_b601_v1.yaml:10` 注释 "was broken F:/Robotic arm abs path"，对应 git 5849b72 "fix broken external runtime ref"）。其余出现均为归档文档叙述。
3. **一个已批准的外部运行时回退**：`10_research/competition_convergence/src/run_competition_gate.py:146` 硬编码回退 `F:\ffmpeg-master-latest-win64-gpl-shared\bin\ffprobe.exe`（优先级：显式参数 → 环境变量 FFPROBE_PATH → PATH → 该绝对路径）。该依赖在 PROJECT_LIBRARY_INDEX `external_tools` 中显式登记（"主仓运行时依赖, DO_NOT_MOVE"），属**已批准例外**，且与动力学/仿真无关（视频证据查验）。
4. **冻结历史证据中的失效绝对路径**（不可重跑，非运行时）：`40_evidence/c1_evidence/*.py`/`*.json` 引用已删除工作区 `F:\Space-Embodied-Robot-HAG_A_20260804`、`F:\Space-Embodied-Robot-Complete_FREECAD_MIGRATION_20260803`。这些是历史证据工件，不属于任何 Gate 的运行路径；若未来重放需先修复路径。
5. `.claude/settings.json` allow-list 引用 `20_engineering/F3_MECHANICAL_TERMINAL_AUDIT_20260806/`、`20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/` —— 两目录在当前 worktree **均不存在**（陈旧权限条目，非运行时依赖）。
6. `30_simulation/asm_00_interface_preflight/README.md` 复现命令含 `--planning-root "F:\China Graduate Future Flight Vehicle Innovation Competition"`（指向 ROOT A 自身，合规）。

## 4. NEW_CONTRADICTION / HOLD 登记

- **NEW_CONTRADICTION-01（路径漂移，内容一致，非双真值）**：CM SSOT（PROJECT_LIBRARY_INDEX.yaml `b601.accepted_urdf` 与 ASSET_AUTHORITY_MATRIX.csv `ACCEPTED_URDF` 行）指向 `20_engineering/cad/B5_1R1_B601_interface_native_rework_candidate/00_BASELINE/AUTHORITIES/accepted_urdf/arm_b601_v1.urdf`——该目录在当前 worktree **不存在**（全仓 Glob 仅 1 个 arm_b601_v1.urdf）。同 hash 文件（raw sha256 `1bc2b7483cd8025d...`，与 SSOT 登记一致）实际位于 `20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf`，且它就是 sim_05/sim_11/CTRL 实际装载的文件。**裁决建议（留给 PL1-G/CM）**：更新 SSOT 路径字段至现存路径；不存在双 URDF 冲突，无需 HOLD。
- **NEW_CONTRADICTION-02（SSOT 声称目录缺失）**：PROJECT_LIBRARY_INDEX.yaml 声称 `20_engineering/F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/`（363 files, KEEP_UNTIL_F3R2）；当前 worktree 中 `20_engineering/` 下**无此目录**（仅 README.md/cad/config/stage1_spacecraft_layout/system_design），全仓 `*F3R1*` 零命中。机械域归 PL1-B 深查；本件仅作证据登记。相关地，`.claude/settings.json` 中 F3R2 路径同样失效（见 §3.5）。
- **观察项（非矛盾）-03**：PROJECT_LIBRARY_INDEX.yaml 的 `git_head`/`current_head` 记录为 5849b72；实测 HEAD 为 5c5adde（= 5849b72 之后一个 docs(CM3) 提交，lineage 一致）。属 SSOT 轻微滞后。
- **观察项（非矛盾）-04**：`30_simulation/README.md:19` 称 "e15/e16 仍保留在仓库根目录"；实测 e15_ancf_certification/e15_core_coverage/e16_sync_capture 均位于 `30_simulation/` 内，仓库根目录无 e15/e16。文档漂移。
- **HOLD**：本任务域（动力学/仿真）未发现需要 HOLD 的双真值冲突（无双 CURRENT CAD、无双 accepted URDF、无冲突质量真值、无 F3R1/F3R2 状态冲突落入本域）。NEW_CONTRADICTION-02 的处置权交 PL1-B/PL1-G。

## 5. 一句话层级裁决

当前动力学/仿真真值 = **numpy/scipy 原生链（sim_05 刚性锚 + sim_11 耦合主线 + capture_impulse 求解器 + sim_10/12 可行域与策略 + SAFE-00 裁决核），全部 FROZEN、机器 Gate 裁决**；ROOT B 全部 16 个相关检出为参考/教学/第三方资产，项目运行时对其**零依赖（已验证）**；CAE 库仅含通用教学示例，无 SEI 工程真值。
