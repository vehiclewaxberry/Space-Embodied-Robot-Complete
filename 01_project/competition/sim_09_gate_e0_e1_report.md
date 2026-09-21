# sim_09 抓取候选评价器 — Gate E0 + E1 报告

日期：2026-07-13 ｜ 分支：`feat/sim09-grasp-evaluator`（基线 HEAD `2f954fd`）
执行：Gate E1「确定性 G0/G1/G2 薄切片」（72 工况，全确定性，无采样）

---

## 1. Gate E0 摘要（已提交 `2f954fd`）

评价器骨架 `30_simulation/sim_09_grasp_evaluator/src/`：

- **契约**（`contract.py`）：`GraspCandidate` → `evaluate()` → `GraspEvaluationResult`（21 个结果字段）；
  `scenario_hash` = 全部输入的规范化 JSON 的 sha256[:16]（1e-9 舍入，对任一输入 1e-6 扰动敏感，t7 验证）。
  **无 overall_score**（E0 裁定：硬约束筛选 → 单项指标 → Pareto，聚合分数仅保留注释占位）。
- **只读适配器**（`adapters.py`）：五个已验证求解器一律 import、绝不复制 —— capture
  （`30_simulation/common/capture_impulse.py` rigidize/点接触）、base reaction（sim_05 `FreeFloatingB601`）、
  flexible（sim_07 ANCF `sim_07a_task_response`）、actuator（sim_08 代数式）、propagation
  （`30_simulation/common/rigid_body.py`）。每段输出 provenance{module, commit, units, wall_time_ms}。
- **IK**（`ik.py`）：多起点 DLS（固定种子 20260712，逐位确定），pose_6d / approach_5d / position_3d；
  **碰撞**（`collision.py`）：胶囊-图元 SDF，几何假设 A1–A7 全部声明于
  `20_engineering/config/grasp_evaluator/collision_geometry_v1.yaml`。
- **锚定回归 7/7 PASS**（`30_simulation/sim_09_grasp_evaluator/results/anchor_report_e0.md`）：
  t1 冲量锚（sim_06/08 CSV，残差 3.0e-5）；t2 IK 往返（3.7e-8 rad）；t3 动量守恒（1.6e-17）；
  t4 ANCF 锚（sim_07a 标称，9.0e-6 相对）；t5 传播四性质（2.3e-11）；t6 推进剂逐位相等；
  t7 双重求值逐位一致 + 哈希敏感性。
- E0 发现并记录 **+X 腕部奇异**：抓取点若落位在 S 系 x 轴上（z=0），任务雅可比条件数 ~2–3e4；
  E0 默认落位 `capture_point_S=[0.95, 0, -0.10]` 避开（常规条件数 ~19–27）。E1 沿用该落位策略。

## 2. ANCF 运行成本审计摘要（口径澄清）

裁决文件：`30_simulation/sim_09_grasp_evaluator/results/ancf_cost_audit_verdict.md`（15 工况实测）。

- **口径澄清**：早先「每候选 ~20 s」混淆了 sim_07a 多进程**分摊**口径；实测**单例墙钟中位 101.7 s**
  （审计机，物理 15 s，Radau rtol 1e-6，常切线雅可比），最大 197.7 s。
- 由此裁定：**E1 薄切片（72 例）走路线 A 全量 ANCF**（4 进程批处理，预估 ~31 min）；代理模型推迟至
  E2/G2（1152×2 网格，串行 ~65 h 不经济），启用需过留出集误差 <10% / Top-3 一致率 >90% / Kendall τ>0.9。
- **sol.success 隐患已按裁决落实**：`sim_07a.simulate` 内部 `assert sol.success`；E1 生产流水线捕获该
  异常并以 **rtol 1e-5 重试**，重试仍失败 → 标 `FLEX_SOLVER_FAIL`，**不得静默进表**（见 §4.3）。
- E1 本机实测：快速段（IK+碰撞+基座反应+捕获+推进剂）平均 20.5 s/例，ANCF 平均 48.6 s/例；
  72 例 4 进程总墙钟 **≈22 min**（126 s 冒烟 + 1210 s 主扫），与审计外推一致（本机单线程更快）。

## 3. E1 薄切片定义（72 工况）

| 维度 | 取值 | 说明 |
|---|---|---|
| 目标 | `target_debris_v0` @3°/s | tumble_axis=[1,0.15,0.4]/‖·‖（惯性系），周期 T=120 s |
| 抓取点（D 系） | P1=[0.66,0,0.95]、P2=[0,0.66,0.95]、P3=[0.66,0,−0.95] | JSON 喷管缘特征；杠杆臂=点−cg（cg=[0.00027,0,−0.07054]，质量预算 SSOT）|
| 抓取系 C | z_C=外法向（P1/P3:+X_T，P2:+Y_T），x_C=±Z_T 背离本体 | P1 与 E0 标称帧完全一致 |
| 捕获相位 | t_c ∈ {0, 30, 60, 90} s | 即 0°/90°/180°/270° 相位 |
| 接近速度 | v_app ∈ {0.005, 0.01, 0.02} m/s | |
| 任务约束 | pose_6d、approach_5d | |
| 固定项 | q0=零位、rigid_6dof、b601 堆、capture_point_S=[0.95,0,−0.10] | q0 零位注：joint2/3 上限恰为 0，裕度在 q_c 处评估 |

G0 基线 = 网格单元 (P1, t_c=0, v_app=0.01, pose_6d)，即 E0 标称场景由**同一评价器**跑出。
柔性段只对通过 IK+碰撞的工况运行（69/72 符合，全部实际运行）。

复现命令（可重跑再生一切表/图）：

```
python 30_simulation/sim_09_grasp_evaluator/src/e1_thin_slice.py --workers 4   # 断点续跑：逐例即时 append
python 30_simulation/sim_09_grasp_evaluator/src/e1_analysis.py                 # 全部表 + 图 + gate 判定 JSON
python 30_simulation/sim_09_grasp_evaluator/tests/run_all.py                   # t1..t8 锚定回归
```

## 4. E1 结果

数据：`30_simulation/sim_09_grasp_evaluator/results/e1_results_72cases.csv`（72 行 × 68 列：候选全输入 +
scenario_hash + 契约 21 结果字段 + 展平便查列 + flex 状态 + M_PCS + provenance）。

### 4.1 工况统计（72 例）

| 类别 | 数量 | 明细 |
|---|---|---|
| IK 可行 | 69/72 | — |
| **IK_FAIL（如实记录 INADMISSIBLE）** | 3 | P3_tc00_v{5,10,20}mm_pose_6d：P3 底缘帧在 t_c=0 的 6D 期望姿态不可达（E0 已知落位/腕部姿态限制，未挪期望）|
| IMPULSE_EXCEED（ω⁺>2.0°/s） | 45 | P1 全部 24 例（ω⁺=3.054–3.070）+ P3 可行 21 例（ω⁺=2.512–2.525）|
| **FLEX_SOLVER_FAIL（重试后仍失败）** | 2 | P3_tc30_v10mm_approach_5d、P3_tc60_v5mm_approach_5d（两例本已 IMPULSE_EXCEED，未损失可行解；rtol 1e-5 重试仍不收敛，E2 待查）|
| ANCF rtol 1e-5 重试成功 | 5 | P1_tc60_v20mm_5d、P2_tc90_v{5,20}mm_6d、P3_tc30_v20mm_5d、P3_tc60_v20mm_5d —— 审计裁决的重试路径在生产中被真实触发 |
| **admissible（全部硬约束通过）** | **24** | **P2 全部 24 例**（ω⁺=1.489–1.718，H=3.79–4.23 N·m·s，E_flex=1.3e-6–1.8e-4 J）|

失败码统计表：`30_simulation/sim_09_grasp_evaluator/tables/infeasible_cases.csv`。

### 4.2 物理图景（图 `30_simulation/sim_09_grasp_evaluator/figures/fig_e1_phase_map.png`）

- **抓取点主导 ω⁺**：P2（+Y 缘）杠杆几何相对自旋轴（≈0.9X+0.14Y+0.36Z）使刚化后合成体
  ω⁺ 减半（1.49–1.72 vs P1 的 3.05–3.07°/s）—— 这是唯一使 2.0°/s 预算可满足的抓取点。
- **t_c 对刚体指标近乎不参与**（预判的坑，如实报告）：const_omega 下整个场景随 ω̂ 刚性旋转，
  E0 落位策略又把抓取点站位固定在 S 系 —— ω⁺/H 随相位仅变化 ≤1%（3.055→3.067），Δθ_base
  几乎恒定 1.627–1.630°。相位仅通过「追捕器姿态-场景滚转」二阶耦合进入刚体指标。
- **但 t_c 强烈参与柔性指标**：dv/dw 在 S 系的方向随相位滚转，帆板法向激励分量变化,
  P2 的 E_flex 从 1.6e-4 J（t_c=0）降到 1.3e-6 J（t_c=90）—— **136 倍**；这使相位选择在
  G2 里真实可优化（Pareto 前沿覆盖全部 4 个相位）。
- v_app 增大 → J_t 平移分量与 E_flex 增大、ω⁺ 微增；v=0.02 全部被支配（前沿仅含 v∈{0.005,0.01}）。

### 4.3 G0 / G1 / G2 对比（表 `30_simulation/sim_09_grasp_evaluator/tables/g0_g1_g2_comparison.csv`）

选择规则：G1 = 桶内（相位×速度×模式）可达 + 最大 manipulability（√det(JJᵀ)，1e-12 舍入并列时
按点号字典序）；G2 = 桶内 admissible → 六指标 Pareto 第 1 层 → 代表取最大 M_PCS。

**关键结构性发现**：E0 落位策略把每个抓取点映射到 S 系**同一期望 EE 位姿**（q_c 逐位相同），
故 manipulability 在桶内三点间**完全并列**（0.006559590149…，13 位有效数字相同）——
几何判据在本切片**不可判别**，G1 退化为字典序（21/24 桶选 P1；3 个 t_c=90/pose_6d 桶因
1e-12 量级差异恰选 P2）。动力学差异（ω⁺ 减半）对几何判据完全不可见 —— 这正是 G2 存在的理由。

G0 桶（t_c=0, v=0.01, pose_6d）逐指标（完整 21 项见 CSV）：

| 指标（方向） | G0 = G1（P1） | G2（P2） | G2 vs G1 |
|---|---|---|---|
| ω⁺ [°/s]（min，约束 2.0） | 3.0551（**超budget 53%**） | 1.5671 | **−48.7%** |
| Δθ_base [deg]（min） | 1.6294 | 1.6294 | 0.0% |
| |J_t| [N·s]（min） | 0.3545 | 0.9869 | +178.4% |
| E_flex [J]（min，约束 1e-3） | 2.49e-5 | 1.56e-4 | +524.9% |
| H_RW [N·m·s]（min，约束 5.475） | 3.6471 | 3.9513 | +8.3% |
| m_prop [g]（min） | 36.46 | 39.50 | +8.3% |
| manipulability（max） | 0.0065596 | 0.0065596 | 0.000% |
| admissible | 否（IMPULSE_EXCEED） | **是** | — |
| **M_PCS**（max） | **−0.5275** | **+0.2165** | **+141.0%** |

M_PCS = min(1−H/H_max, 1−J_thr/J_max, 1−E_flex/E_max, 1−ω⁺/ω_max, 1−Δθ_b/θ_max)，阈值出处：

| 项 | 阈值 | 出处 |
|---|---|---|
| H_max | 5.475 N·m·s | `hard_constraints_v1.yaml` wheel_momentum_max_Nms（PLACEHOLDER，1.5×sim_08）|
| ω_max | 2.0 °/s | 同上 post_capture_rate_max_dps（sim_04 POST_CAP_BUDGET）|
| E_max | 1e-3 J | 同上 flexible_energy_max_J（PLACEHOLDER，~40×sim_07a 标称）|
| J_max | 32.21 N·s | **导出值** = H_max / lever(0.17 m)（sim_08 双推力器力偶臂；yaml 无独立条目）|
| θ_max | 20° | **yaml 无条目** —— 占位：sim_05 主线全程基座漂移 19.20° 取整（列入 UNVERIFIED）|

全局 Pareto 第 1 层（`30_simulation/sim_09_grasp_evaluator/tables/pareto_front.csv`）：16 例，**全部 P2**，
覆盖 4 个相位 × v∈{0.005,0.01} × 两种任务模式；全局最优 M_PCS = **P2_tc90_v5mm_approach_5d**
（M_PCS=+0.2555，ω⁺=1.489°/s，E_flex=1.3e-6 J，H=3.801 N·m·s）。
图：`fig_e1_pareto.png`（前沿三投影 + G1 选点高亮 + G0 基线）、`fig_e1_g1_vs_g2.png`（逐指标条形+相对%）。

## 5. 通过条件逐条判定

| # | 条件 | 判定 | 证据 |
|---|---|---|---|
| ① | 锚定 7/7 通过 | **PASS** | E1 开跑前复跑 t1–t7 全 PASS；E1 完成后 t1–t8 全 PASS（`anchor_report_e0.md` 重新生成，t8 三条 G0 锚残差 0.0e0）|
| ② | 可追溯（CSV 含 hash+provenance） | **PASS** | 72 行含全部输入字段 + 72 个唯一 scenario_hash（与确定性网格逐一匹配，t8 校验）+ solver_provenance（module+commit，wall_time 剔除）|
| ③ | 存在 G2 候选：≥2 主指标改善且其余恶化 ≤5%，**或** M_PCS 提升 ≥20% | **PASS（经 M_PCS 分支）** | 21/24 桶 M_PCS 提升 ≥20%（G0 桶 −0.528→+0.216，+141%；不足 20% 的 3 桶是 G1 恰好也选中 P2）。**A 分支 0/24 桶满足**，如实说明：ω⁺ 减半的代价是 |J_t|+178%、E_flex 数倍（仍深居预算内）——杠杆几何权衡使六指标无一候选同时改善 ≥2 项且其余 ≤5%；这是物理权衡而非评价器缺陷（诊断清单核查：候选差异足够大 ✓、场景有挑战 ✓ [P1/P3 全部超 ω⁺ 预算]、t_c 经柔性通道真实参与 ✓ [E_flex 136×]、IK 多解保留 ✓ [每例 5–9 解]、归一化基于 yaml 阈值 ✓）|
| ④ | 图表自动生成 | **PASS** | 3 图 3 表全部由 `e1_analysis.py` 从结果 CSV 再生（重跑命令见 §3）；无手绘/硬编码数字 |
| ⑤ | 无未验证接触量 | **PASS** | 全程无接触力/抓取概率/阻抗最优值；`impact_severity_proxy` 在契约与表格中均显式标注 PROXY（|J_t|+|L_g|/lever 组合，非接触力）|

## 6. UNVERIFIED 清单

1. **θ_max=20°** 非 yaml 条目（基座姿态漂移无 GNC 指标来源），取 sim_05 主线 19.20° 取整的占位值；
   M_PCS 的 θ 项在本切片从不 binding（Δθ≈1.63°），不影响排序结论。
2. yaml 中 4 项阈值本身即 PLACEHOLDER（碰撞 0.02 m、条件数 1e4、H_max 5.475、E_max 1e-3）。
3. E0 落位策略（抓取点站位于固定 capture_point_S、追捕器姿态保持）**构造性地**压制了刚体指标的
   相位依赖与几何判据的可判别性 —— G1/G2 的对比结论依赖该策略；E2 若引入落位滚转自由度/
   相对姿态场景族，几何指标可能重新参与。
4. ANCF 单帆板(+Y)、单向耦合（基座速度跳变→帆板，无反馈）、nominal EI 单刚度；
   2 例 FLEX_SOLVER_FAIL（P3/approach_5d/v10&v5）在 rtol 1e-5 下仍不收敛，根因未查明（E2 项）。
5. 碰撞几何 v1 粗糙（胶囊+图元、A6 不查服务星-目标本体接近）；接近轨迹为关节空间 min-jerk
   （非笛卡尔跟踪），碰撞裕度沿该轨迹评估。
6. const_omega 传播（惯性固定自旋轴假设）；torque_free 通道已具备但本切片未启用。
7. m_prop 与 J_thr 与 H_RW 线性相关（sim_08 代数式），六指标实际独立维度为 4。

## 7. 是否建议进入 E2

**建议进入**：评价器在 72 例上零手工干预地复现了「几何判据不可判别、动力学判据把不可行基线
（ω⁺ 超预算 53%）翻转为 +25.6% 裕度候选」的完整证据链，且锚定/确定性/追溯三件套全绿 ——
E2 的前提（可信的单例评价器 + 实测成本模型）已就绪；E2 应优先解决落位滚转自由度、
代理模型门控（1152×2 网格）与 FLEX_SOLVER_FAIL 根因三件事。

---

### 附：M_PCS 最优候选描述

> P2 喷管缘抓取点（P2_tc90_v5mm_approach_5d）虽然几何可操作度并不更优（与 G1 选点相差
> 0.000%，落位策略下几何指标不可判别），但确定性工况下抓取后仍保留 **25.6%** 系统级稳定裕度
> （M_PCS=+0.256，binding 项为 ω⁺ 裕度：1.489/2.0 °/s），而几何选点 P1 的系统裕度为
> **−53.3%**（ω⁺=3.067 °/s，超出捕获后角速率预算）。
