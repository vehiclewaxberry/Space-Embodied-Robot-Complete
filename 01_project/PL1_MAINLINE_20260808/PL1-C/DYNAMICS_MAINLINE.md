# DYNAMICS_MAINLINE.md — PL1-C 动力学/仿真主线重建

> 重建日期：2026-08-08 | 重建方式：只读核查（READ-ONLY），证据均附真实路径/hash/git 提交
> 仓库状态：git HEAD `5c5adde`（branch `publication/stage3-integrity-closure`，lineage b75352c → e14b224 → cd0ea80 → 5849b72 → 5c5adde，已实地 `git log` 核实）
> 全局运行纪律（`10_research/00_project_architecture/simulation_scenario_map.md`）：`NO_NEW_SIMULATION — STOP_AFTER_ARCHITECTURE_FREEZE`；所有 sim_01–12/e15/e16/SAFE/CTRL/Wave1 均 FROZEN，禁止重跑。

## 0. 关于 "M5/M6/M9" 命名的核查结论

仓库内**不存在**名为 M5/M6/M9 的里程碑主线。全仓 grep 到的 M5/M6/M9 仅是：
- `10_research/on_orbit_assembly/contact_flexible_dynamics_plan.md`（ASM-01 计划）中的**指标编号** M5=基座姿态/速率、M6=轮组动量/力矩需求、M9=接触后残余误差；
- VLA/装配文档中的评测指标编号。

因此本文件按 orchestrator 的任务定义，把 "M5/M6/M9 链" 映射为三条任务线重建：
- **M5 线 = 动力学模型主线**（dynamics model）
- **M6 线 = 非合作目标捕获主线**（non-cooperative target capture）
- **M9 线 = 外部仿真器（Isaac/MuJoCo/ROS2）主线**

这是 PL1-C 的语义裁决，非仓库原生术语；ASM-01 指标表中的 M5/M6/M9 与此无关，不要混用。

---

## M5 线 — 动力学模型主线（dynamics model）

### 当前权威（current authority）
**`30_simulation/sim_11_coupled_dynamics/`（路线 A 主线，v1.1）** — 中心刚体 + 双侧 FFR 柔性帆板 + B601 6R 机械臂的浮动基座树形多体模型（Kane 装配，reduced/full 双模式积分），纯 numpy/scipy，参数全部经 `20_engineering/config/coupled_scene/` YAML 参数卡 + 几何 SSOT 装载。

- 刚性自由漂浮锚点：**`30_simulation/sim_05_free_floating_arm/`**（VERIFIED+FROZEN）——真实 B601 URDF（sha256 `1bc2b748...`）、复合基座 25.2 kg、全系统 29.8956 kg、广义雅可比 J_g、 headline 基座扰动峰值 19.20°。
- 共享求解层：`30_simulation/common/rigid_body.py`（惯量装载/无力矩传播/H-E 诊断）、`30_simulation/common/capture_impulse.py`（捕获冲量精确解，Gate A 已过）。
- 质量/惯量总账：`20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/mass_inertia_budget_v1.csv`（confidence=low，build123d 块模型；缺质量/质心/惯量/坐标系/参考点任一即 blocking_TBD，禁入下游动力学）。
- 几何/模型 SSOT：`20_engineering/config/geometry/{arm_b601_v1,arm_mount_v1,frame_tree_v1,flexible_appendage_v1,service_spacecraft_v1,target_models_v1,capture_interface_v1}.yaml`、`20_engineering/config/coupled_scene/coupled_model_v0.yaml`。

### 当前文件（current files）
`sim_11_coupled_dynamics/src/{config_loader,ffr_panel,coupled_dynamics,capture_solver,contact_window,scene_a1_arm_slew,scene_a2_capture,run_gates,plot_g4_diagnostic}.py`；`tests/run_all.py`（27 项 assert）；`docs/sim_11_耦合动力学报告_20260717.md`、`docs/sim_11_对抗式审查闭环_20260717.md`。

### 状态（status）
`LIMITED + FROZEN`。Gate JSON 机器裁决：**`SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS`**（`results/sim_11_gate_check.json`，schema sim11-gate-v3，`PROVISIONAL_PARAMS: true`，provisional 字段 = n_modes/mode_shape/stiffness_case/zeta_modal/contact_T_c）。
历史：v1.0 曾因理想冲量 Δt=0 下模态能变化 2.78%/1.27% >1% 判 `SIM11_GATES_FAIL: G4_convergence`（git 6c0035b）；v1.1 引入有限接触带宽（T_c=20 ms 名义，PROVISIONAL）后前向加密链收敛 0.48%/0.027%，同一 1% 判据通过。

### 最近有效结果（latest valid result）
- `30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json` — 2026-07-18，PASS_WITH_PROVISIONAL_PARAMS。
- `30_simulation/sim_11_coupled_dynamics/results/baseline_verification_20260717.log` — sim_05 22/22 + sim_07 benchmark 基线复跑留档，2026-07-17。
- `30_simulation/sim_05_free_floating_arm/results/sim_05_base_attitude.csv/.png` — 19.20° 峰值锚点。

### 已被取代（superseded）
- sim_03（平面 2-DOF 约化模型）→ 被 sim_05 全 3D 6R 链明确取代（README_sim_05 原文 "Replaces the sim_03 2-DOF reduced planar model"）。
- sim_01（早期自由飞行姿态漂移）→ 早期场景资产，LIMITED+FROZEN，不再是姿态动力学权威。

### 开放挂起（open holds）
1. **帆板模态参数为占位**（D-4 一阶频率指派 f1=0.7/1.0/1.3 Hz 包络 + zeta=0.01 文献待定）——实测到位前不得升级为硬件有效结论；重跑触发器状态 `BLOCKED`。
2. **接触时宽 T_c=20 ms 为 PROVISIONAL**——待 B601 夹爪实测；触发器 `BLOCKED`。
3. 轮力矩/轮动量/最小脉冲量为占位类值——sim_10/CTRL-02 资源复核触发器 `BLOCKED`。
4. W1-R12 轮力矩冲突（0.033 > 0.01 N·m PROVISIONAL）已记账，留 ASM-02 显式解决。
5. 目标（debris/satellite）惯量 confidence=low（RA-003），从未声称为实测。

### 下一任务（next task）
- **ASM-01 装配接触-柔性动力学仿真**（`10_research/on_orbit_assembly/contact_flexible_dynamics_plan.md`，状态 PLAN_ONLY 未实现；目标目录 `30_simulation/asm_01_contact_insert/`，L0 几何+冲量 / L1 KV 持续接触主力层 / L2 ANCF 抽查三保真度）。前置：ASM-00 AG0 解封（接口 SSOT v1 + HAG-A 批准，当前 `BLOCKED`）。
- 外部交叉验证最小波次（需单独批准）：Pinocchio 三刚体锚点（质量矩阵/雅可比/基座反冲 19.20° 复算），Basilisk 一个 ADCS 锚点。见 M9 线。

---

## M6 线 — 非合作目标捕获主线（capture）

### 当前权威与责任链
1. **捕获动量真值**：`30_simulation/common/capture_impulse.py`（共享塑性捕获求解器，Gate A 通过）+ **`30_simulation/sim_06_capture_impulse/`**（VERIFIED+FROZEN，40 工况精确矢量 rigidize）。
2. **任务可行域**：**`30_simulation/sim_10_mission_feasibility/`**（VERIFIED+FROZEN）——9002 点精确解 + 四门 fail-closed。
3. **策略选择**：**`30_simulation/sim_12_strategy_feasibility/`**（VERIFIED+FROZEN，Phase 1 限定）——16 策略证明单元（S1 被动/S2 速度匹配/S3a 轮组预置/S4 捕获后消旋）。
4. **运行时安全裁决**：**`30_simulation/safety_00_runtime_gate/`**（SAFE-00，VERIFIED+FROZEN，PASS 但 `next_stage_authorized=false`、`PENDING_REVIEW`）——逐调用绑定 sim_12 唯一键 `A_low|S1_passive`。
5. **抓取候选评估**：`30_simulation/sim_09_grasp_evaluator/`（LIMITED+FROZEN；E1.5 为冻结负结果）。
6. **同步捕获离线扫描**：`30_simulation/e16_sync_capture/`（LIMITED+FROZEN）。

### 当前文件
- sim_06：`sim_06_capture_impulse.py` + `tests/`（7 测试文件 + verification_report_v0.md）
- sim_10：`src/{feasibility_core,scan_grid,run_gates,figures}.py`，参数卡 `20_engineering/config/mission_feasibility/scan_v0.yaml`
- sim_12：`src/strategy_eval.py`，配置 `20_engineering/config/strategy_feasibility/strategies_v0.yaml`，账本仲裁 `10_research/sim_12/momentum_ledger.md`
- SAFE-00：`src/{safety_core,case_factory,run_gates,run_diagnostics}.py`，策略/契约 `20_engineering/config/safety_gate/`
- sim_09：`src/{evaluator,ik,collision,target_propagation,e1_analysis,...}.py`（路径锁定例外：分布于同名 src/tests/results/figures/tables）
- e16：`src/{run_campaign,sync_model}.py`，`config/experiment_v1.yaml`

### 状态与最近有效结果
| 模块 | verdict | 日期 | 关键数字 |
|---|---|---|---|
| sim_06 | VERIFIED+FROZEN | ≤2026-07-11（Gate A） | 碎片 150 kg@3°/s → 捕获后 3.06°/s；2°/s 预算边界：碎片 1.96°/s / 卫星 4.37°/s；标量捷径误差 −2.9%…−12.3% |
| sim_10 | `SIM10_GATES_PASS` | 2026-07-18 | 9002 点：6323 WHEELS_ONLY / 1858 INFEASIBLE_RATE / 730 THRUSTER_REQUIRED / 91 INFEASIBLE_RESOURCE；FLEX=UNKNOWN_NOT_IN_CRITERIA |
| sim_12 | `SIM12_PHASE1_GATES_PASS` | 2026-07-18（账本 @ git 2d26ddc） | GS1 守恒 max eps_H 3.85e-16；无策略全案例最优（GS2 机器证明） |
| SAFE-00 | `PASS`（next=false，PENDING_REVIEW） | 冻结基线 | UNKNOWN→ALLOW=0；绕过成功=0；误停率=0 |
| sim_09/E1 | LIMITED+FROZEN | 2026-07-13（E0 锚 ALL PASS） | 72 例：69 IK / 24 admissible / 16 Pareto |
| sim_09/E1.5 | `REPEAT_E1_5`（NEGATIVE_RESULT+FROZEN） | 2026-07-14 快照 | SAFE=0 / UNKNOWN=3 / UNSAFE=69 |
| e16 | `PASS_WITH_GEOMETRY_AND_FLEX_LIMITATIONS` | 2026-07-14 | 216 例：18 动力学有效 / 198 上游拒绝 N/A / formal safe=0；重跑 sha256 `bd972b69...` |
| e15 core | `REPEAT_CORE_NO_SAFE_CANDIDATE`（NEGATIVE） | 冻结基线 | 72/72 覆盖 PASS 但 0 安全候选（66 几何无效 + 6 CORE_UNSAFE） |
| e15 ANCF | `REPEAT_ANCF_CERTIFICATION`（NEGATIVE） | 冻结基线 | 交叉求解器最大差 5.637% > 5% 门槛，认证未闭环 |

### 已被取代
- **sim_04 v0 启发式走廊**（`post_rate ~ tumble·I_t/(I_s+I_t)`）→ 被 sim_06 精确矢量模型取代；sim_04 目录内 `sim_04_v2_exact_impulse.py` 为保留的精确口径。v0 启发式造成 24 个 false-safe 网格点（碎片侧 −2.6% 乐观、卫星侧 +20% 保守，单一标量修正无法同时修复）。
- 历史 "SAFE 312" 走廊计数 → 不是当前统一安全 Gate（scenario map 明示）。

### 开放挂起
1. **formal safe = 0**：e16 全部柔性证据 UNKNOWN ⇒ `safe_claim_permitted=false`；e15 core 无安全候选。**捕获链当前没有任何"正式安全"候选**——这是 M6 线最大的诚实边界。
2. **ASM-00 前置 Gate 阻塞**：`ASM00_AG0_BLOCKED_BY_INTERFACE` / `ASM00_BLOCKED_BY_MISSING_PARAMETERS`（RF-1/2/3 红旗、接口 SSOT v1 与 HAG-A 批准缺失）。
3. **持续接触模型不存在**：现有接触仅是 sim_11 `contact_window.py` 的有限带宽捕获脉冲（T_c=20 ms PROVISIONAL）；插接持续接触（KV/Hunt–Crossley、卡滞判据）属 ASM-01 计划，未实现。
4. 消旋执行机构常数为 NASA SmallSat SOA 2026 类值（sim_08 assumptions.yaml 占位），不等于硬件选型。
5. SAFE-00 独立复审 PENDING_REVIEW；PASS ≠ 执行授权。

### 下一任务
- 新核心安全刚体候选认证（e15 core/ANCF 支路，触发器状态 `PLANNED`）。
- ASM-00 解封 → ASM-01（L0/L1/L2 三保真度插接接触；目标侧双柔性帆板 Phase B 退化链）。
- 禁止事项（scenario map 统一措辞）：不得说"e16 同步捕获已实时实现"、"SAFE PASS 已授权执行"、"捕获等于消旋"。

---

## M9 线 — 外部仿真器主线（Isaac / MuJoCo / ROS2 / 交叉验证）

### 当前权威
**治理文件：`10_research/framework_convergence/tool_stack_decision.md`** —— 裁决"当前外部工具 NOW 项为零"。仓库**没有任何** SPART/Pinocchio/Basilisk/MuJoCo/Adams/Isaac Sim 的项目级 machine Gate、冻结适配器或结果哈希；但 ROOT A 的 external/reference 子树确有上游源码 checkout（包括 SpaceRobotEnv/MuJoCo）。numpy/scipy 原生动力学 + CSV/JSON + 机器 Gate 仍是唯一项目真值链。

逐项定位（原文裁决）：

| 工具 | 裁决 | 允许定位 | ROOT B 检出位置 |
|---|---|---|---|
| Pinocchio | **NEXT** | 三刚体锚点首选轻量 cross-validator（M(q)、J、基座反冲 19.20° 复算） | 无检出 |
| Basilisk | **NEXT** | 一个服务星 ADCS 锚点（对拍 CTRL-02/sim_10 冻结案例） | `REFLIB2_03_space_dynamics/.../repos/basilisk` |
| SPART/Simulink | **LATER** | 第二刚体 cross-validator（仅当 Pinocchio 锚点出现不可解释差异） | `REFLIB1_SPART`（LGPL-3，AS_INDEPENDENT_TOOL_ONLY） |
| MuJoCo | **LATER** | Wave B/C 后技能/接触状态覆盖/FSM-VLA 环境回放 | ROOT A `80_third_party/external/.../SpaceRobotEnv`（Apache-2.0，legacy `mujoco-py` free-floating reference）；外部 `F:\Robotic arm\zero-robotic-arm\5. Deep_LR`（GPL-2.0，新版 MuJoCo + Gymnasium + TD3，固定基座 6R 教学例）——均非项目实现 |
| Isaac Sim | **LATER** | Wave C 后视觉数据/展示/具身交互 | `REFLIB2_04 .../repos/int-ball2_isaac_sim`（范例） |
| SpaceDyn | **AUDIT_ONLY** | Yoshida GJM/RNS 公式审计 | `REFLIB1_SpaceDyn`（无许可证，只读方法） |
| Adams | **NOT_NEEDED** | — | 无 |
| 气浮台 | **LATER** | 赛后 H0–H3 地面组件验证 | — |

### 当前文件
ROOT A 内：没有 Isaac/MuJoCo/ROS2 的**项目适配器、冻结配置、Gate 或结果**；但存在 reference-only 源码 checkout：SpaceRobotEnv（MuJoCo/Gym，clean @ `155989c2…`）、Chrono（clean @ `24c78cf8…`）以及若干 vendor/reference clones。外部 donor 根另有 `F:\Robotic arm\zero-robotic-arm\5. Deep_LR`（14 个已跟踪文件、38,422,631 B；固定基座桌面 6R TD3 教学例；README 明示手写 TD3 未验证）。这些源码均未被当前工程代码 import，不能称为项目仿真实现。
ROOT B 内物理检出（全部 REFERENCE_IMPLEMENTATION/THIRD_PARTY，项目运行时不读取，已验证零引用）：EXUDYN、SPART、SpaceDyn、SpaceDyn_python、MATLAB_space_debri_capturing_sim、spacedyn_freefloating_demo（TEACHING_CASE）、spaceros_demos、space_robotics_bench、basilisk、ANCF_beam、isaac、int-ball2_isaac_sim、space-ros、astrobee。Chrono 与 SpaceRobotEnv 仅由 ROOT B register 指向 ROOT A 的临时 reference checkout，尚未物理进入 ROOT B。

### 状态
`NOT_STARTED / PLANNED_NOT_AUTHORIZED`。唯一候选科学实施主线是 ON-ORBIT ASSEMBLY WAVE A（`READY_WITH_INTERFACE_BLOCKERS`）；外部最小对拍是有资源上限的辅助验证，不得阻塞 Wave A、比赛材料或 2026-09-01 提交。

### 最近有效结果
无（外部工具零执行）。最近的"对外对拍合同"文档：`tool_stack_decision.md` §4（Pinocchio 三锚点 + Basilisk 单锚点 + 统一 verdict 词汇 CROSS_CHECK_PASS / CROSS_CHECK_REPEAT / NOT_EVALUATED_INPUT_MISMATCH / BLOCKED_BY_TOOL_OR_LICENSE）。

### 开放挂起
1. 任何外部对拍需单独批准 "EXTERNAL CROSS-VALIDATION MINIMAL WAVE"；容差预注册，禁止事后放宽。
2. 外部结果不能直接改写现有 Gate；输入不等价时必须记 `NOT_EVALUATED_INPUT_MISMATCH`。
3. 禁止强结论清单（原文）：SPART/Pinocchio 验证 sim_11 柔性真值；MuJoCo/Adams 认证装配接触；Basilisk 验证刚柔耦合捕获；Isaac Sim 证明 VLA 泛化；外部求解器优先于项目 machine Gate —— 全部禁止。
4. 角动量对拍必须同时报告惯性原点与系统质心两种口径，不得交叉比较。

### 下一任务
1. Wave A 首个 machine verdict 之后（或独立空档）：**Pinocchio RIGID-1/2/3 三锚点**（冻结 B601 URDF + T_SM + 一个构型；M(q) 对称正定；J 对拍；sim_05 轨迹 19.20° 基座反冲复算）。
2. 其后：**Basilisk 一个 ADCS 锚点**（同一质量/惯量/初始角动量/轮组盒/推力器/脉冲量子；对拍区域分类与动量收支）。
3. MuJoCo / Isaac Sim：Wave B/C 之后再评估；当前 `LATER`，不启动。

---

## 主线裁决摘要（一句话/线）

- **M5（动力学模型）**：当前权威 = sim_11 v1.1（LIMITED，占位参数待实测），刚性锚 = sim_05（VERIFIED）；下一步 = ASM-01 实现 + Pinocchio 锚点。
- **M6（非合作捕获）**：真值链 = capture_impulse.py → sim_06 → sim_10 → sim_12 → SAFE-00（均 VERIFIED/PASS 且 FROZEN）；但 formal safe=0，ASM-00 阻塞未解；负结果（E1.5/e15/CTRL-01/Wave1）全部冻结保留。
- **M9（Isaac/MuJoCo/ROS2）**：项目集成层零实现、零运行时依赖；ROOT A、ROOT B 与 `F:\Robotic arm` 外部 donor 根均有 reference checkout、教学例或索引，但都不拥有项目 authority；外部仿真器裁决仍为 NEXT/LATER/AUDIT_ONLY/NOT_NEEDED。
