# e15 重认证测试规格草案 V1（AGENT-3 / round1_bridge / r2_flex_prep）

- schema: `E15_RECERTIFICATION_TEST_SPEC_DRAFT_V1`
- 生成时间：2026-08-23T17:21+08:00（宿主机本地钟）
- 状态：**DRAFT_PENDING_AUTHORITY —— 全文逐条标注草案；本文件不授权任何运行**。e15 现状 `REPEAT_ANCF_CERTIFICATION` 逐字保持；重认证运行须等：MPI/动力学权威的质量分配裁决（见 `R2_FLEX_MASS_ALLOCATION_RULING_OPTIONS_V1.md`）+ MPI-FB-01..08 桥接 Gate 闭合 + owner 放行。
- 范围：只起草，不运行。本轮未启动任何仿真/积分器进程；未修改 e15 模块、certification_v1.yaml、任何 Gate JSON。
- 依据文件：`30_simulation/e15_ancf_certification/results/gate_summary.json`（sha256:12 `aab4d609e219`）、`30_simulation/e15_ancf_certification/config/certification_v1.yaml`（`8c9f283b3444`）、`30_simulation/sim_07_ancf_flexible/`（benchmark 证据）、AGENTS.md §约定验证链。

## 0. 现状与缺口（逐字摘自 gate_summary.json，可复核）

- `overall = REPEAT_ANCF_CERTIFICATION`。
- 交叉求解诊断：`comparison_count=6`、`max_relative_difference=0.05637349419858036` > 门槛 `0.05` → `all_lt_5pct=false`。
- 冻结最终候选对拍：`final_candidate_cross_solver.available=false`，原因逐字：「冻结E1.5为SAFE=0且无名义Top-3；不得用低振幅诊断锚点冒充最终候选。」
- 已闭合子项（不因重认证推翻，作回归基线）：历史分类 `classification_fraction=1.0`（7/7 分类、unclassified=0、silent_zero=0）；低振幅 ANCF-模态最大轨迹相对差 8.19e-05 ≤ 0.10；离散化趋势（网格/脉冲/时间步）全部 observable，Newmark 误差序列 6.80e-2 / 2.36e-2 / 5.99e-3 单调下降。
- **结论：重认证的实质缺口 = 冻结最终候选的 Radau-vs-BDF 全比较 ≤5%；其余子项作为回归项保持。**

## 1. 触发条件 T1–T7（新全耦合模型何时必须重过本 Gate）

| 触发 | 内容 | 认证对象的变化 |
|---|---|---|
| T1 | 任何消费 R2 柔性翼的新全耦合模型（刚性翼车道不触发、但也不闭合任何柔性结论） | 认证对象从 R1 单叶悬臂梁变为 R2 三叶铰链链 + 星-臂耦合系统 |
| T2 | 动态质量分配冻结改变 Mqq→Mqq*（MC-B 情形），或 WP5 实测更新叶质量/EI | 质量阵/刚度带变更，五工况频率基线重发 |
| T3 | 阻尼模型引入（今 `damping_matrix=null`）或 ζ 变更 | 耗散项进入认证对象；能量审计口径须区分"守恒验证（ζ=0）"与"耗散预测（ζ≠0）"两条车道 |
| T4 | 铰/latch 刚度带被实测值替换（今 50/200/800、20/100/400 N·m/rad 全 PROVISIONAL_DERIVED） | 刚度带变更，频率带角重扫 |
| T5 | 接触窗模型变更（scene A2 `T_c_ms_nominal=20.0` 占位 → B601 夹爪闭合时间实测；扫掠域 5–100 ms） | 激励带宽定义变更，模态能指标重估（sim_11 教训：理想冲量对模态能不适定，须有限接触窗） |
| T6 | 积分器/容差/方法偏离既定约定（主 Radau `rtol=1e-10/atol=1e-12`，交叉 BDF；coupled_model_v0.yaml 逐字） | 对拍基准本身失效，全部比较重做 |
| T7 | 自由漂浮基座耦合 + 模态参与因子（GAP-03 闭合） | 认证对象从定基座梁变为耦合附件——当前 e15 的全部证据都是定基座/组件级口径，本触发是重认证范围最大的一次扩大 |

任一触发命中 ⇒ 全 Gate 重跑；多触发叠加 ⇒ 一次重跑覆盖，不得拆分分批放行。

## 2. 关闭条件（门槛逐字摘自 certification_v1.yaml，括号内为执行口径草案）

- `historical_classification_fraction_min: 1.0`、`unclassified_max: 0`、`silent_zero_max: 0` —— 历史用例全部分类可复现，禁静默零。
- `low_amplitude_ancf_modal_relative_max: 0.10` —— 低振幅（1e-4 激励）ANCF 对线性模态极限的轨迹相对差。
- `final_candidate_cross_solver_relative_max: 0.05` —— **5% 门槛**：冻结最终候选（SAFE>0 且名义 Top-3 存在；低振幅诊断锚点禁止冒充）的全部比较项 Radau-vs-BDF 相对差 ≤ 0.05。
- `require_mesh_trend: true`、`require_time_step_trend: true` —— 网格加密与时间步加密趋势可观测（单调或收敛序列）。

## 3. 测试矩阵草案（DRAFT_PENDING_AUTHORITY）

### E15R-T1 冻结最终候选交叉求解对拍（5% 门槛主项）【DRAFT_PENDING_AUTHORITY】

- 目的：闭合当前唯一实质缺口（0.0564 > 0.05）。
- 口径：主积分器 Radau（`rtol=1e-10, atol=1e-12`）vs 交叉 BDF（同容差族）；比较对象 = 冻结最终候选的全部物理输出（与 e15 既有 comparison_count=6 的同族输出项对齐并扩展到 R2 耦合输出的对应量）。
- 通过判据：全部比较项相对差 ≤ 0.05；分类规则沿用 success/status/message（scipy 语义），放宽容差后的返回成功**不得**作为收敛证明（certification_v1.yaml primary_sources 纪律逐字继承）。
- 前置：最终候选已冻结（SAFE>0、名义 Top-3）；MC 裁决已落账（质量阵唯一）；T5 接触窗口径已按实测或显式占位声明。
- 证据落盘：新 e15 轮次的 gate_summary.json（新文件，不覆盖旧件）。

### E15R-T2 组件级同激励对比 sim_07（退化链第一环）【DRAFT_PENDING_AUTHORITY】

- 目的：验证新耦合模型的帆板组件在**锁关节、同激励**口径下复现 sim_07 已认证行为。
- 口径：取 sim_07 组件级工况（点捕获激振 vs 刚性锁定 ≈92× 放大、振铃 37–75 s、benchmark b1 静变形 rel 1.03e-04、b2 频率 err ≤8.0e-05、b3 零刚体应变能 ~1e-14 J、b4 能量漂移 ≤1.6e-09、b5 网格收敛序列）；新模型的 R2 帆板组件在相同激励族下给出同族指标。
- 通过判据：同族指标落入 sim_07 已认证容差带（b1 <1%、b2 <5%、b3 机器精度、b4 <1e-6@tight、b5 单调收敛）；组件级口径声明**激励、约束、输出定义逐字一致**（不得改激励后比数值）。
- 备注：sim_07 组件参数为 R1 悬臂卡（EI 8.9042e-3 N·m²、mu 1.74197 kg/m）；R2 组件为三叶铰链链，**对比的是行为族与容差纪律，不是逐数值相等**；R2 数值基线 = 已发布五工况（本代理复核 4.84e-05 Hz 内复现）。

### E15R-T3 帆板刚化退化 sim_05（退化链第二环）【DRAFT_PENDING_AUTHORITY】

- 目的：帆板刚度趋向刚化极限时，新耦合模型退化复现 sim_05 刚体自由漂浮结论。
- 口径：R2 刚度带角 all_high → 继续放大至刚化极限（程序内刚度乘子扫描），锚点 = sim_05 的 B601 6R 自由漂浮臂致基座姿态扰动峰值 **19.20°** 与动量守恒 7.3e-17。
- 通过判据：刚化极限下基座扰动峰值收敛到 sim_05 锚点的声明容差内（建议 ≤1%，草案值待定）；动量残差保持机器精度量级。

### E15R-T4 全刚化 sim_01 式无力矩传播（退化链第三环）【DRAFT_PENDING_AUTHORITY】

- 目的：全结构刚化后，同一组合体的自由传播必须与 sim_01 式刚体无力矩传播逐状态一致。
- 口径：零外力/外力矩、初态赋值后自由传播；比较姿态/角动量/能量全状态轨迹。
- 通过判据：与刚体解析/已认证刚体积分器的偏差机器精度量级；动量、能量双账本同时闭合。

### E15R-T5 动量守恒机器精度【DRAFT_PENDING_AUTHORITY】

- 目的：新模型在全工况下保持动量双账本机器精度。
- 口径：参照已冻结模板——sim_05 `7.3e-17`；e21 双车道 `dP ≤ 2.81e-16 / dL ≤ 2.60e-16`（E21-G15）；sim_11 窗内组合动量 2.7e-14、能量审计 8.5e-11（含接触窗耗散机制时的口径须分离）。
- 通过判据：无接触/无耗散工况 |dP|、|dL| ≤ 1e-13 量级（草案值，对齐 e21 模板）；含接触窗工况按 sim_11 口径单独声明阈值（2.7e-14 量级）。
- 备注：阻尼引入后（T3）能量账本不再是守恒量，动量账本仍必须机器精度。

### E15R-T6 离散化趋势回归【DRAFT_PENDING_AUTHORITY】

- 目的：网格趋势与时间步趋势在新模型上保持可观测。
- 口径：沿用 e15 既有协议族（mesh 2/4/8 单元、脉冲时长 0.02/0.01 s、Newmark 步长 0.02/0.01/0.005 s 三档）；新模型的模态/响应指标须呈收敛序列。
- 通过判据：`require_mesh_trend` 与 `require_time_step_trend` 双 true。

### E15R-T7 历史分类回归【DRAFT_PENDING_AUTHORITY】

- 目的：既有 7 历史用例（P1_tc60_v20mm…至 P3_tc60_v5mm，certification_v1.yaml `historical_rerun.cases` 逐字）在新求解链下分类不变。
- 通过判据：classification_fraction=1.0、unclassified=0、silent_zero=0；任何重分类须单独裁决记录，禁止静默。

### E15R-T8 低振幅 ANCF-模态对拍回归【DRAFT_PENDING_AUTHORITY】

- 目的：小变形极限下 ANCF 与线性模态解的一致性在新模型组件上保持。
- 通过判据：轨迹相对差 ≤ 0.10（现状 8.19e-05，回归保持同量级）；网格趋势同时观测。

## 4. 触发—测试追溯矩阵

| 触发 | 必跑测试 | 说明 |
|---|---|---|
| T1 | T1/T2/T3/T4/T5/T6/T7/T8 全项 | 新认证对象全 Gate |
| T2 | T1/T2/T5/T6 + 频率基线重发对拍 | 质量阵变更传导全模态 |
| T3 | T1/T5 + 耗散车道新增 | 能量审计口径分叉声明 |
| T4 | T1/T2/T6 + 频率带角重扫 | 刚度带变更 |
| T5 | T1 + 接触窗带宽对拍 | 模态能指标重估（sim_11 理想冲量教训） |
| T6 | 全项 | 对拍基准失效，全部重做 |
| T7 | T1/T3/T4/T5 全项 + 参与因子耦合正确性新增项 | 认证对象从定基座变为自由漂浮耦合附件 |

## 5. 明确不授权事项（逐字纪律）

- 本草案不授权运行任何上述测试；不授权修改 e15 模块、certification_v1.yaml、任何 Gate JSON。
- 本草案不设最终候选、不声明 SAFE、不消费任何低振幅诊断锚点冒充候选。
- 5% 门槛、0.10 低振幅门槛、趋势要求为既有合同逐字引用；任何放宽须 owner 书面裁决。
- 运行前置硬条件：MC 裁决落账（`dynamic_mass_allocation_frozen=true`）；MPI-FB-01..08 全闭合（ODR-44）；T_PHYSICAL_TO_DYNAMIC 桥已冻结哈希钉入；owner 放行。

## 6. 源文件哈希绑定（sha256:12，本代理 2026-08-23 实测）

| 文件 | sha256:12 |
|---|---|
| `30_simulation/e15_ancf_certification/results/gate_summary.json` | `aab4d609e219` |
| `30_simulation/e15_ancf_certification/config/certification_v1.yaml` | `8c9f283b3444` |
| `30_simulation/sim_07_ancf_flexible/results/benchmark_results_v1.md` | `cb970783497c` |
| `20_engineering/config/coupled_scene/coupled_model_v0.yaml` | `67a532fb29c7` |
| `20_engineering/config/coupled_scene/scene_A2_capture.yaml` | `4b979a1dfd18` |
| `30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results/E21_DIAGNOSTIC_GATE_V1.json` | `b03b7c7af571` |
