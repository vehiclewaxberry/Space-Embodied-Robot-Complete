# dyn 分片审计发现（动力学与柔性域）

- 分片：dyn；审计日期：2026-08-27（本地）；模式：只读。
- 授权记录：本次审计唯一写入位置 `90_competition_closeout/20260827_current_state_audit/fragments/dyn/` 由用户在任务书中显式授权创建，优先于 AGENTS.md REORG04「根目录业务资产只允许八域」的限制；本分片未对任何既有文件做写/移/删操作，未运行任何仿真或 Gate。
- 方法：从 AGENTS.md / PROJECT_MAP.md / 01_project/current/README_CURRENT.md 入手，逐模块读机器 Gate JSON 与原始 results CSV，关键数字全部回到原始文件复算或核对到行定位，未照抄 AGENTS.md 摘要。

## 1. 核心数字复算结果（全部与摘要一致）

- **sim_05 基座姿态扰动峰值 19.20°**：复算 `30_simulation/sim_05_free_floating_arm/results/sim_05_base_attitude.csv`（sha256 前12 `d543fff76f13`）`base_dev_angle_deg` 列 601 行最大值 = **19.199852° @ t=8.00s**，与 `README_sim_05.md`（`181eba2721e7`）L113「19.20° at t=8.0s」一致；动量守恒 7.3e-17 见同 README L96 dyn2 测试行（worst residual 7.3e-17 < 1e-10）。
- **sim_06 碎片@3°/s 捕获后 3.0633°/s**：`results/capture_impulse_matrix_v0.csv`（`8cbad84b8ff6`）**第 15 行** `target_debris_v0,3,0.01,1.21521,3.06333,...`（post_rate_full_dps，eps_H=3.84985e-16，OVER_BUDGET）。3.0633304945807067 的精确值出自 sim_10 求解器：`sim_10_gate_check.json`（`4dbd8c91ff34`）`$.gates.X1_anchors_vs_sim06.checks[0].w_plus_dps`，与 CSV 差 4.95e-07，在半 ULP 容差 5e-06 内。卫星锚点 1.38721 在 CSV 第 34 行。
- **sim_07 ≈92× 与振铃 37–75s**：`results/task_response_summary.csv`（`df29073bdb6c`）6 行——刚性锁定 tip 峰值 5.235789/3.674004/2.827378 mm vs 点捕获 0.056821/0.039768/0.030597 mm，比值 92.1–92.4×；`t5pct_s` 列 37.03–75.17 s（`t5_method=fit_extrapolated`，窗外推，README_sim_07a.md L55-56 声明与单模态理论偏差 <4%）。
- **sim_08 |H_c|=3.65 N·m·s = 12× 轮组容量**：`results/actuator_budget_sweep.csv`（`1f0d45349565`）`target_debris_v0,3.0` 行 `H_Nms=3.65099`（900 s/lever 0.05 行：总冲量 73.0199 N·s、冷气推进剂 124.0992 g）；`README_sim_08.md`（`778e2ffaaa09`）L22-23 写明 3.65 N·m·s 对 3×100 mN·m·s 轮组为 12× 超容量。执行机构档全部为 placeholder CLASS 值（assumptions.yaml 头注）。
- **sim_10 9000 点四门 fail-closed + 双锚点**：`sim_10_gate_check.json`（`4dbd8c91ff34`）`$.verdict=SIM10_GATES_PASS`；`$.scan_summary.n_physics_points=9002`、`n_gate_rows=72016`（scan_summary.json `63d84ce5ca84`）；X1 双锚点逐位、X3 对拍 sim_08 相对差 7.2e-07、R 哈希锁裁决时刻全过；tests 为 `tests/run_all.py`（`2318d9b0d212`）L106 的 6 项 assert。G1 μ≈0.51 单调性证伪：`$.gates.X2` `design_expectation_status=REFUTED_IN_TRANSITIONAL_BAND`，`worst_dip_rel=0.010790032932416973`（1.08%）@ μ=0.5141，亚分辨率不改区域标签。
- **sim_11**：`sim_11_gate_check.json`（`9309f5325271`）`$.verdict=SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS`；G1 窗内组合动量守恒 `A2_bw20_window_drift=2.7346180875298387e-14`；G2 窗内能量审计 `8.459748222451578e-11`；A2 守恒量 `$.gates.G4.values.A2_ideal.m3` |H_O|=3.6782586304198084 / |L_C|=3.7213991753489832 N·m·s；帆板振铃 tip_L 峰值 2.0749 mm @ 1.00088 Hz（同 key）；G3b 刚化退化对 sim_05 峰值 19.199850770410567°（rel 7.8e-06）。**帆板模态参数为占位**：`$.provisional_fields=[n_modes,mode_shape,stiffness_case,zeta_modal,contact_T_c]`；T_c=20 ms 占位见 `scene_A2_capture.yaml`（`4b979a1dfd18`）L25；5–100 ms 扫掠见 `$.gates.G4.bandwidth_sweep_diagnostic` 五档。
- **sim_12 16 例**：`sim_12_gate_check.json`（`a416c1348111`）GS1 `max_eps_H=3.849848861643484e-16`；GS2 `best_per_case` A_low→S1、B_anchor→ABORT、C_transition→S3a_wheel_bias、D_extreme→ABORT；`strategy_results.csv`（`f538676005ce`）17 行=16 例+表头。S2 矢量/标量分账：`10_research/sim_12/momentum_ledger.md`（`77e34aff3e28`）L30 |ΔH_vec|=1.43508 N·m·s（矢量，dv=0.037475 m/s，推进剂 1.69 g）与 |H| 标量 +0.873「勿混用」；S3a 省 13×：`docs/strategy_comparison_report.md`（`5bb7c6a71677`）L13（3.0 g vs ~40 g）与 L20。
- **e15 交叉求解 5.637%**：`e15_ancf_certification/results/gate_summary.json`（`aab4d609e219`）`$.cross_solver_diagnostic.max_relative_difference=0.05637349419858036`、`all_lt_5pct=false`、`$.overall=REPEAT_ANCF_CERTIFICATION`；报告 `docs/ANCF_CERTIFICATION_REPORT_ZH.md`（`8cd3455aa52f`）L18「6 组；最大四指标差 5.63735%」。
- **e23 18/18**：`E23_R2_FULL_FLEX_COUPLED_GATE_V1.json`（`1ad4993fd9df`）`$.technical_verdict=PASS_WITH_DECLARED_PROVISIONAL_PHYSICS`、`summary 18/18`；`key_metrics.hf_to_rom_seven_mode_max_relative=0.0027143911284986865`（0.2714% ≤ 1%）、`cross_solver_max_relative=1.8136532292893113e-05`（≤ 5%）、`rigid_degeneration=0.0`；独立重算 33/33 见 `E23_INDEPENDENT_RECOMPUTE_V1.json`（`93951e31f20e`）`$.summary passed 33/33`。

## 2. 动力学证据链 verdict 与适用域（逐环节）

1. **自由漂浮反作用（sim_05）**：VERIFIED（源级冻结，无 gate JSON）。适用域：刚体、动量级运动学反作用，无关节力矩/柔性；URDF 惯量为厂商值。比赛图表可用。
2. **捕获冲量（sim_06）**：VERIFIED（源级）。适用域：刚体矢量冲量；CSV 6 位有效数字，精确值以 sim_10 求解器为准。结论「捕获≠消旋」可进图表。
3. **柔性激振（sim_07）**：VERIFIED 但**阶段 A 单向耦合**（假设 A1，基座不接收柔性反馈）；3DOF 面外数值仅下界（A3）。92×/37–75 s 可进图表，须注明组件级单向口径。
4. **资源账本（sim_08）**：VERIFIED 作为 CLASS 级预算；执行机构未选型，12×/124 g 引用须带 CLASS 声明。
5. **可行域（sim_10）**：VERIFIED（SIM10_GATES_PASS），**刚体边界、FLEX=UNKNOWN 不入判据**；占位项：执行机构 CLASS、t_detumble_max=3600 s、G3 无 CAD 锚点。
6. **有限接触窗（sim_11）**：PROVISIONAL（PASS_WITH_PROVISIONAL_PARAMS）；T_c=20 ms 与帆板模态全占位。引用须带声明。
7. **binding-gate 策略选择（sim_12）**：VERIFIED（SIM12_PHASE1_GATES_PASS）；flex 不入判据；GS3 禁四条过度宣称。
8. **耦合重认证（e23）**：PENDING_REVIEW（18/18 + 33/33），诊断检查点级，`next_stage_authorized=false`、`release_credit=false`。

## 3. Unified R2 守恒与状态连续性（PB-00..PB-03）——无当前系统信用证据

- 唯一 PB 级证据是 `dynamics_control_prebind_r1/10_verification/PB_G1_GATE.json`（`7ad34fcf9482`，2026-08-26）：G1-01/02/03 = **PASS_DIAGNOSTIC_NO_CREDIT**（能量漂移 4.52e-15、P/L 残差 3.6e-18/5.2e-18、确定性回放哈希匹配），G1-04/05（RPO→TASK_READY、PREGRASP→捕获连续性）= **NOT_EVALUATED**，verdict `PB_G1_HOLD_NOT_AUTHORIZED_BY_PB_G0`。`13_reports/CURRENT_STATE.md`（`0c5319bc2c68`）明示「不产生正式控制或机械发布信用……下一合法动作是关闭 PB-G0-A，不是 NMPC/RL/VLA」。
- 当前系统侧：`r2_dynamics_engineering_closure/results/R2_8DOF_CONSTRAINED_DYNAMICS_GATE_V1.json`（`6fc6f5ec0df1`，2026-08-27 02:17）16/18，failed=[DG1 单位度量, **DG2 独立全状态动量守恒**]——Unified R2 守恒无当前系统信用；`R2_DYNAMICS_ENGINEERING_GATE_V1.json`（`c847dd680814`）DG1–DG5 全 HOLD；联合门 `R2_DYNAMICS_CONTROL_SYSTEM_GATE_V1.json`（`55490805d934`）HOLD、无路径搜索。
- 结论：PB-00..PB-03 记 **PLANNED/HOLD**；诊断表征存在但 no-credit，禁止升级为当前系统证据。

## 4. e21 与 e23 的关系

- e21（`E21_DIAGNOSTIC_GATE_V1.json`，`b03b7c7af571`，2026-08-23）：23/23 诊断子项全过但 overall=**HOLD**——闭合的是「当前 R2 **刚性翼** + 臂-only 两安装敏感性 + 固定基座 ROM 复现」；当时 `r2_full_flexible_coupling=NOT_EVALUATED`；质量 31.022864807342987 kg 精确闭合；harness R2_HRN_04 FAIL_REDESIGN_REQUIRED 作为强制 HOLD 保留。
- e22（`472ada4a7abf`，2026-08-24）：首次全柔耦合诊断，16/18 HOLD（G11 五模态 HF→ROM 3.51%>1% FAIL、G17 FAIL）——**不可变历史**。
- e23（2026-08-25，Owner TMC-01 授权七模态 ROM）：**e23 是 e22 的重认证**，闭合 e22 失败的 G11/G17；e21 与 e23 是互补域——e21=刚性翼安装敏感性（HOLD 因语义/harness），e23=全柔耦合 Checkpoint-A（PASS_WITH_DECLARED_PROVISIONAL_PHYSICS，PENDING_OWNER_REVIEW）。两者都不授予任务/发布放行。

## 5. 最高风险发现

1. **sim_10 冻结哈希锁对当前树失效（FROZEN_HASH_LOCK_STALE）**：REORG04（commit 284c882）将 `sim_08 assumptions.yaml`、`threshold_registry_core_v1.yaml` 路径字符串改写，SHA 由钉住值 850f49da…/400bcedc… 变为当前 006c6cc5…/75af082a…；`scan_v0.yaml`（`856f1e30de47`）与 gate 未重钉——**今日重跑 `run_gates.py` 的 R 门必 FAIL**。已用 `git show 284c882` 逐行确认改写为纯路径前缀、数值语义等价（符合 PROJECT_MAP.md 规则5），历史裁决 SIM10_GATES_PASS 不受影响；但决赛前任何重跑/现场复核会被阻塞。最小动作：重钉哈希并重发 gate（分钟级，内部可闭环）。
2. **帆板占位参数是科学硬伤候选**：`coupled_model_v0.yaml`（`67a532fb29c7`）L5 `status: PROVISIONAL_PARAMS`；AGENTS.md 待办3 自评「真实参数下 A1 柔性反馈可忽略结论可能翻转，属论文最大硬伤」。决赛展示柔性结论必须带 PROVISIONAL 声明。
3. **E-COMP-02（Unified R2 守恒/状态连续性）**：PB-G1 HOLD + DG2 未绑定（见 §3），归 P1；e15 legacy 重认证归 P2（已由 E23 口径替代）。

## 6. 可进比赛图表的数字（数据文件 + 脚本 + row locator）

| 数字 | 数据文件 | 生成脚本 | row locator |
|---|---|---|---|
| 19.20° 基座扰动 | `30_simulation/sim_05_free_floating_arm/results/sim_05_base_attitude.csv` + .png | `sim_05_headline.py` | CSV `base_dev_angle_deg` max=19.199852 @ t=8.00 s |
| 3.0633°/s 捕获后残余 | `30_simulation/sim_06_capture_impulse/results/capture_impulse_matrix_v0.csv` | `sim_06_capture_impulse.py` | CSV 第15行 `post_rate_full_dps=3.06333` |
| 92× 激振比 / 37–75 s 振铃 | `30_simulation/sim_07_ancf_flexible/results/task_response_summary.csv` + tip_response_matrix.png | `sim_07a_task_response.py` | CSV 6 行 tip_peak_mm 比值；`t5pct_s` 列 |
| 3.65 N·m·s / 12× / 124 g | `30_simulation/sim_08_detumble_actuator_budget/results/actuator_budget_sweep.csv` + budget_*.png | `actuator_budget.py` | CSV `target_debris_v0,3.0,…,900.0,0.05` 行 |
| 可行域 F1–F4 | `30_simulation/sim_10_mission_feasibility/results/sim_10_scan_{physics,gates}.csv`、sim_10_F1..F4 png | `src/scan_grid.py`、`src/figures.py` | gate `$.scan_summary`；锚点 `$.gates.X1.checks[*]` |
| 柔性耦合捕获（PROVISIONAL） | `30_simulation/sim_11_coupled_dynamics/results/sim_11_scene_A2*.csv/png` | `src/scene_a2_capture.py` | gate `$.gates.G4.values.A2_bandwidth` |
| 策略阶梯（binding gate） | `30_simulation/sim_12_strategy_feasibility/results/strategy_results.csv` + strategy_ladder_initial.png | `src/strategy_eval.py` | CSV 16 行；gate `$.gates.GS2.best_per_case` |
| 耦合重认证支撑（带 PENDING_OWNER_REVIEW 标签） | `30_simulation/e23_r2_full_flex_coupled_recert/results/E23_CASE_MATRIX_V1.csv` | `src/build_e23.py` | gate `$.key_metrics` |

禁入图表：e15 legacy 5.637% 线（仅作负结果登记）、e22（SUPERSEDED）、sim_13 V4 合成接触任何数字、PB-00 诊断表征（no credit）。

## 给综合裁决的输入

1. sim_05/06/07/08 四模块无独立 gate JSON，核心数字已回原始 CSV/README 复算一致：19.199852°（sim_05 CSV max）、3.06333°/s（sim_06 CSV 第15行）、92.1–92.4× 与 37.03–75.17 s（sim_07 CSV 6行）、3.65099 N·m·s（sim_08 CSV debris@3.0 行）。
2. sim_10 gate `$.verdict=SIM10_GATES_PASS`（sha `4dbd8c91ff34`）有效，但其 R 哈希锁钉住值与当前树不符（850f49da→006c6cc5、400bcedc→75af082a，REORG04 路径改写，git diff 证实语义等价）——记 FROZEN_HASH_LOCK_STALE，内部分钟级可闭环。
3. sim_11 `SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS`（sha `9309f5325271`），占位字段五项含 T_c=20 ms 与帆板模态；外部输入（夹爪实测+帆板数值案例）未到位，归 P1。
4. sim_12 `SIM12_PHASE1_GATES_PASS`（sha `a416c1348111`）16 例；S2 |ΔH_vec|=1.43508 矢量与 |H| 标量 +0.873 已分账（ledger L30），S3a 省 13×（报告 L13/L20）。
5. e15 legacy 维持 REPEAT（gate_summary `aab4d609e219`，5.637%）；e15_core `REPEAT_CORE_NO_SAFE_CANDIDATE`（72 例 0 SAFE）；二者为保留硬负结果。
6. e22 16/18 HOLD 为不可变历史（sha `472ada4a7abf`）；e23 18/18 PASS_WITH_DECLARED_PROVISIONAL_PHYSICS（sha `1ad4993fd9df`，HF→ROM 0.2714%、Radau/BDF 1.81e-05、独立重算 33/33）是当前耦合认证口径，但 PENDING_OWNER_REVIEW 且无 release credit。
7. Unified R2 守恒/状态连续性（PB-00..PB-03）无当前系统信用证据：PB_G1 HOLD（sha `7ad34fcf9482`，G1-04/05 NOT_EVALUATED）+ R2 8DOF DG2 未绑定（sha `6fc6f5ec0df1`）→ E-COMP-02 归 P1。
8. e21（23/23 诊断 PASS，overall HOLD，sha `b03b7c7af571`）与 e23 互补：刚性翼安装敏感性 vs 全柔耦合重认证；二者均不放行任务。
9. sim_13 正式态 15/20 NC + 5 dependency_hold，V4 证据全部 synthetic 且自带防提升 truth_guard——无 CHILD_RESULT_NEWER 违规；sim_14/15 诊断 PASS 但生产/接触/柔体门 HOLD。
10. sim_01–04 与 sim_09 为 LIMITED/NEGATIVE_RESULT + FROZEN（scenario map L92–101、L126–127），仅作 lineage，不得引用为当前结论。
