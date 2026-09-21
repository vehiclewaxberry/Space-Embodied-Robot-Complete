# Paper 1 架构设计 v1.0 — Strategy Selection under Momentum and Stability Constraints for Non-Cooperative Spacecraft Capture

> **2026-07-20 状态覆盖**：sim_12 Phase1 已裁决
> `SIM12_PHASE1_GATES_PASS`；正文中“预注册/待 Gate0/待实施”等措辞保留为历史
> 写作快照，不代表当前执行状态。现行机器结果以
> `30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json` 为准。

> 生成：2026-07-18｜角色：Acta Astronautica 论文架构｜目标刊：Acta Astronautica（备选 JGCD / Advances in Space Research）
> 证据纪律：**正文任何数字只允许来自 verdict=PASS 的机器裁决 JSON、冻结 CSV，或明确标注"预注册（待 sim_12 Gate 0 断言固化）"的账本数字**。本文档所有引用数字均于当日从下列文件核对：
> - `30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json`（`SIM10_GATES_PASS`）
> - `30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json`（`SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS`，v1.1 接触带宽）
> - `30_simulation/sim_09_grasp_evaluator/results/e1_gate_check.json` + `e1_results_72cases.csv`（本次直接复核：69 例 IK 可行案例操纵度同为 sqrt(det JJᵀ)=0.0065596（差异仅 1e-12 量级），post_capture_rate 散布 1.489→3.070 °/s ≈ 2.06×）
> - `10_research/sim_12/momentum_ledger.md`、`strategy_definition.yaml`、`reviewer_audit_gate0.md`、`reviewer2_attack_response.md`（预注册数字，冻结求解器只读复算，eps_H ≤ 4e-16）
> 写作红线（全程适用）：**禁用"首次 / first / 完全自主 / fully autonomous / 在轨验证 / on-orbit validated"**；禁用任何"S2 更优/更差"的无条件排序；禁用"轮组容量翻倍"孤立表述（必须同句给出预置成本与方向敏感性）；FLEX 未入判据前禁止柔性门结论；引用 e16 数字必须复述其 geometry/flex 限制条款。

---

## 1. Title（3 候选）

| # | 英文题 | 中文对照 | 评注 |
|---|---|---|---|
| T1 | **Strategy Selection under Momentum and Stability Constraints for Non-Cooperative Spacecraft Capture: Feasibility Maps and a Binding-Gate Criterion** | 动量与稳定性约束下的非合作航天器捕获策略选择：可行域图与瓶颈门判据 | 首选。主题词与审稿人裁定一致（用 strategy selection，避开与 2025 MPC 语义纠缠的 momentum shaping）；副题点出两个交付物 |
| T2 | **Which Capture Strategy, If Any? Momentum-Ledger Feasibility Boundaries for Tumbling Non-Cooperative Targets under a Frozen Actuator Budget** | 该选哪种捕获策略——或都不该？冻结执行器预算下翻滚非合作目标的动量账本可行域边界 | 问句式抓眼球，突出"abort 也是答案"的 fail-closed 立场；部分欧刊偏保守，作备选 |
| T3 | **A Strategy Feasibility Ladder for Non-Cooperative Target Capture: Momentum Accounting, Actuator Capacity Gates, and Constraint-Dependent Selection** | 非合作目标捕获的策略可行性阶梯：动量记账、执行器容量门与约束依赖的策略选择 | 以旗舰图（ladder）命名；若审稿担心"ladder"术语新造，可退回 T1 |

---

## 2. Abstract 草稿（英文，≤200 词；当前约 185 词）

> Capturing a tumbling, non-cooperative object transfers its angular momentum to a servicer whose actuators may be unable to absorb it. This paper asks which class of capture strategy — passive capture, velocity matching, wheel momentum biasing, or thruster-assisted post-capture detumbling — remains feasible as target mass and spin grow, and when no strategy exists. All strategies are compared under a single frozen actuator budget and a machine-audited angular-momentum ledger: the capture impulse is internal and cannot change the total momentum, so strategies differ only through propellant-accounted pre-capture states and post-capture resource consumption. Exact vector-impulse solutions over a dimensionless mass-ratio/spin-rate plane (9002 points, four fail-closed gates, conservation residuals below 1e-15) produce four-region feasibility maps anchored to independently cross-checked reference cases. The central quantitative result is a cost structure rather than a universal winner: velocity matching reduces capture impulse by 43% and contact dissipation by 63% while increasing the system momentum burden by 24%; the preferred strategy therefore depends on which gate binds at the mission point. A strategy feasibility ladder and a binding-gate selection criterion are proposed, supported by grasp-metric degeneracy evidence and a finite contact-bandwidth fidelity analysis.

注：43%/63%/24% 为预注册账本数字（`momentum_ledger.md`，冻结求解器复算）；若 sim_12 Gate 0 机器断言产生修正，以复算仲裁并同步改摘要。"below 1e-15" 对应 sim_10 worst_eps_P/H = 2.1e-16/6.0e-16。

---

## 3. Contribution（3 条，不夸大，逐条注明证据文件）

**C1 — 动量账本与瓶颈门依赖的策略选择判据（binding-gate dependent strategy selection）。**
在冻结执行器预算与统一系统质心记账口径下证明：捕获冲量为内力，任何策略都不在捕获瞬间改变总角动量（机器验证 |H_capture⁻ − H_after| 恒等）；策略差异全部来自捕获前初态选择（推进剂入账的外部输入）与捕获后资源消耗。定量核心：速度匹配（S2）以 **+24% 动量负担（3.65099→4.52436 N·m·s，碎片案例；卫星案例 ×4.7）** 换取 **−43% 冲量、−63% 接触耗散**，其矢量外部角冲量 |ΔH_vec|=1.435 N·m·s 闭合到 1.69 g 接近段推进剂（Δv=0.0375 m/s）；轮组预置（S3a）为**容量区间（球心）平移**（沿预测方向可吸收上限 = 2h_max·cosθ，θ=0 时 0.3→0.6 N·m·s，成本 3.00 g，θ=30° 严格 −13.4%，有效域 θ<60°）；臂摆整形（S3b）为预注册否定断言（终态 H 与被动策略一致，仅瞬态效应；须 sim_11 多体路径固化为机器事实）。由此得出：最优策略由任务点的 binding gate（结构门 vs 动量/资源门）决定，不存在无条件排序。
*证据文件*：`10_research/sim_12/momentum_ledger.md`（冻结求解器只读复算，守恒残差 ≤3.8e-16）；`10_research/sim_12/strategy_definition.yaml`（口径与断言清单）；`10_research/sim_12/reviewer_audit_gate0.md`（预注册预测）；锚点 `30_simulation/sim_06_capture_impulse/results/capture_impulse_matrix_v0.csv` 与 e16（`PASS_WITH_GEOMETRY_AND_FLEX_LIMITATIONS`，引用须复述限制条款）。**状态：预注册数字，待 sim_12 Gate 0 四项机器断言编码固化后方可入正文。**

**C2 — 带策略维的无量纲捕获-消旋可行域图（在检索语料内未见同框架，非穷尽声明）。**
以 9002 点精确矢量冲量解 + 四门 fail-closed 链（转速/轮组容量/推进剂冲量/消旋时间）构造 (μ, ω̂) 平面四区域图，两任务锚点机器恒等复现独立冻结证据（碎片 3.0633 °/s → INFEASIBLE_RATE；卫星 1.3872 °/s → WHEELS_ONLY；与 sim_08 对拍相对差 ≤7.2e-7），并如实报告"边界随 λ 单调"设计预期在过渡质量比窄带被精确求解器证伪（幅度 1.08%，亚分辨率）。本文将该机器扩展一个策略维 S∈{S1 被动, S2 速度匹配, S3a 轮组预置, S4 捕获后消旋}，交付**策略可行性阶梯图 + 边界平移定量表**（预注册预测：S3a 抬高 wheels-only 上边界约 2×；S2 使边界轻微下移——若证实，"速度匹配有利"直觉在可行域口径下被部分证伪）。存在性声明措辞固定为"在 59 条检索语料内未见"，不用"首次"。
*证据文件*：`30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json`（X1–X4+R 五 Gate 全 PASS）、`sim_10_F1..F4_*.png`、`sim_10_scan_gates.csv`；策略维为**缺口**（见 §5 实验计划）；文献定位 `01_project/competition/文献缺口审计_20260718.md`（覆盖度 5/6 如实声明）。

**C3 — 支撑判据体系的两项机器审计证据：几何指标退化 + 捕获瞬态保真度纪律。**
(a) 抓取几何指标对捕获后稳定性致盲的机器证据：72 例网格中 69 例 IK 可行案例操纵度同为 sqrt(det JJᵀ)=0.0065596，捕获后角速率却散布 1.489→3.070 °/s（≈2.06×）——同一几何指标值下动力学结局翻倍，论证策略/选点评价必须使用组合体动量-容量量而非运动学代理。(b) 理想冲量（Δt=0）下帆板模态能指标不适定（悬臂模态动量系数慢衰减，m=2..7 逐阶 +2.86%/+1.29%/+0.72%/~+0.4% 的慢收敛尾），引入有物理依据的有限接触带宽（半正弦等冲量，T_c=20 ms 名义、5–100 ms 扫掠包络）后同一 1% 收敛判据恢复适定（m3→m4→m5 前向链 0.48%/0.027%），且可行域关心的动量级量（基座角速率）在两种口径下均已收敛（~1e-7 级）。该证据链界定了本文刚体边界结论的适用域，并把"机器 Gate 拒绝理想冲量能量指标、迫使模型引入接触带宽"写为验证体系有效性的直接证据。
*证据文件*：(a) `30_simulation/sim_09_grasp_evaluator/results/e1_results_72cases.csv` + `e1_gate_check.json`（72 例/69 IK 可行/24 admissible/Pareto 16）+ `30_simulation/sim_09_grasp_evaluator/results/anchor_report_e0.md`（8/8 锚定回归 PASS）；(b) `30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json`（G1–G5 PASS，`ideal_impulse_diagnostic` 与 `bandwidth_sweep_diagnostic` 字段；**PROVISIONAL_PARAMS=true，帆板模态与 T_c 为占位，引用必须随行声明**）。

---

## 4. Figure Plan（≤7 图；注明数据源与现成度）

| # | 图 | 科学作用 | 数据源 | 现成度 |
|---|---|---|---|---|
| Fig.1 | 系统与问题定义：12U 服务星 + B601 6R 臂 + 翻滚目标；策略时间线（捕获前初态选择 → 内力冲量 → 捕获后消耗）与四门链示意 | 建立"策略=预算交易"的记账框架 | `20_engineering/config/geometry/` SSOT、CAD 截图、四门链（sim_10 报告 §1） | **需绘制**（示意图；素材齐备，约 1 天） |
| Fig.2 | 动机：几何指标退化散点（横轴操纵度，69 例聚成一点；纵轴 ω⁺ 散布 1.489–3.070 °/s），叠加 G1/G2 逐指标对比 | "几何最优 ≠ 系统最优"，为组合体量纲的策略判据铺路 | `e1_results_72cases.csv`；现有 `30_simulation/sim_09_grasp_evaluator/figures/fig_e1_g1_vs_g2.png`、`fig_e1_phase_map.png` | **数据全部现成**；按"同指标—异结局"主视觉重绘（半天） |
| Fig.3 | 基线（S1）四区域可行域主图：(μ, ω̂) 平面 WHEELS_ONLY / THRUSTER_REQUIRED / INFEASIBLE_RATE / INFEASIBLE_RESOURCE + 两任务锚点星标 | 回答"什么目标值得抓"（策略前的存在性基线） | `sim_10_F1_feasibility_map.png` + `sim_10_scan_gates.csv` | **现成**（投稿需英文标注/重排版） |
| Fig.4 | 模型保真度双联图：(a) δ_analytic 偏差场（标量近似何处失效，中位 0.41）；(b) 理想冲量慢收敛尾 vs 有限带宽收敛（G4 诊断） | 论证"为什么必须精确矢量解 + 为什么刚体边界可信" | `sim_10_F4_delta_analytic.png` + `sim_11_g4_diagnostic.png` | **两张均现成**；合并排版（半天） |
| Fig.5 | 动量账本瀑布图：S1 vs S2（碎片案例）|H| 分解为目标自旋 3.678 / 追踪星轨道项 0.195→1.192 / 目标轨道项 0.035→0.211，及成本行（1.60 g / 3.00 g） | C1 的可视化：H 从哪来、代价记在哪 | `10_research/sim_12/momentum_ledger.md`（须由 sim_12 Gate 0 断言复算后出图，禁止手抄） | **数据已预注册，图未绘**；依赖 Gate 0 断言代码（约 1 天） |
| Fig.6 | **旗舰图：策略可行性阶梯 / 切换面**——(μ, ω̂) 平面着色"最后存活策略"（随 H_t 增长哪个策略最先失效），叠加 S3a 边界平移与 S2 边界移动的实测结果 | 把 sim_10 的"可不可行"升级为"该怎么做"；C2 的主交付 | sim_12 策略维扫描（9000 点 × 4 策略）；首轮投稿论证可由 16 例证明集支撑（审稿裁定 Q5），全分辨率图作 revision 弹药 | **缺口（0%）**——见 §5 |
| Fig.7 | 叙事锚：碎片 150 kg@3°/s 案例四策略逐门失效走查（每策略四门裕度条形 + abort 逻辑） | 单案例讲清判据如何运作；连接比赛 EXECUTE/ABORT 叙事 | sim_12 16 例证明集 | **缺口（0%）**——见 §5 |

不入正文、留 supplementary：sim_10 F2（h*–j* 资源平面）、F3（λ 边界族）、sim_11 A1/A2 时程图、sim_09 Pareto 前沿。

---

## 5. Experiment Plan（缺口 = 16 例证明集与策略维扫描）

### 5.1 已冻结、不再重跑（引用即可）
sim_06（矢量冲量锚 3.0633 °/s）、sim_08（3.65 N·m·s = 12× 轮组容量、54.73 g 派生链）、sim_09 E1（72 例）、sim_10（9002 点四区域）、sim_11 v1.1（接触带宽）。e16 可引用但每次必须复述其 geometry/flex 限制条款。

### 5.2 E-A：sim_12 Gate 0 机器断言（账本 → 代码，先于一切扫描）
把 `strategy_definition.yaml` 的四条断言编码为 assert 并出机器裁决 JSON：
1. 每策略 |H_capture⁻ − H_after| ≤ 1e-12（内力冲量恒等）；
2. S3b 终态 H 与 S1 **逐位一致**（内部运动不改总量的构造性证明）；
3. S2 的 ΔH_ext 与账本 +0.873 N·m·s 闭合；
4. 成本行（1.69 g / 3.00 g）由公式复算，禁止手抄。
任一 FAIL 即冻结并如实报告（沿用 `SIM11_GATES_FAIL` 先例的诚实机制）。

### 5.3 E-B：16 例证明集（4 任务 × 4 策略；目的 = 物理正确性验证，非发表数据）
- 任务点：22 kg@0.5 °/s（WHEELS_ONLY 深处）、150 kg@3 °/s（INFEASIBLE_RATE 锚）、μ=2 中间过渡带、ω=5 °/s 极限；
- 策略：S1 被动 / S2 速度匹配 / S3a 轮组预置 / S4 捕获后消旋；
- 每例输出：四门裕度向量、区域标签、账本闭合残差、成本行；
- 验收 Gate（`10_research/sim_12/research_plan.md` 批准口径）：G-A 锚点（S1≡sim_10 逐位；S2 vs e16 带限制条款；S4 vs sim_08）；G-B 账本闭合；G-C 阶梯序一致性（机器断言 S3a 可行域 ⊇ S1 可行域）；G-D registry 哈希锁 + thresholds_widened=False；G-E 确定性。
- 产出物：Fig.7 数据 + Fig.6 初版叙事支撑。

### 5.4 E-C：策略维扫描（9000 点 × 4 策略 → Fig.6 全分辨率）
复用 sim_10 机器（几何类映射/四门/registry 哈希锁），每策略仅修改（追踪星预状态、轮组有效容量区间、推进剂账本）→ 逐点裁决 → 阶梯图 + 切换面 + 边界平移定量表。**预注册预测（待机器裁决证实或证伪，两种结果都入文）**：S3a 抬高 wheels-only 上边界约 2×；S2 使边界轻微下移。分期：16 例先行支撑首轮投稿论证，9000 点全扫描作 revision 弹药（审稿裁定 Q5 口径）。

### 5.5 E-D：敏感性与否定结果专节
- S3a 方向预测误差扫掠 [0, 15, 30, 45, 60]°（吸收上限 = 2h_max·cosθ，30° −13.4%，60° 归零）；
- S3b 专节：构造性否定结果（瞬态效应 ≠ 终态效应），作为可发表的 negative result；
- （投稿前若 registry v2 到位）帆板参数敏感性矩阵抽检（面密度 ×0.5–5、EI ±50%、ζ、f1），支撑 Limitations 的定量化。

### 5.6 时间与回滚
sim_12 实施窗 7/18–7/25（工单 `.codex/agents/sim12-strategy-agent.md`）；sim_12 独立目录只新增，失败不回改 sim_10/11，裁决 JSON 保留 FAIL 历史。论文成稿 9 月起（比赛材料优先）。

---

## 6. Reviewer Risk Top 5（按杀伤力排序，攻/防/证据）

| # | 攻击 | 防御 | 依托证据 |
|---|---|---|---|
| R1 | **帆板占位参数（0.348 kg，真实面密度差 5–10×）**："柔性不移动边界"的任何暗示在真实参数下可能翻转 | 主张严格限定为**刚体边界 + FLEX=UNKNOWN 不入判据**；给保守方向声明（柔性只会扩大 INFEASIBLE 区，FEASIBLE 标签在柔性证据闭合前不用于"安全"声明）；Limitations 列参数转正触发的全 Gate 重跑承诺 | `sim_10_gate_check.json` 的 `flex_status=UNKNOWN_NOT_IN_CRITERIA`；`sim_11_gate_check.json` 的 `PROVISIONAL_PARAMS` 字段；`10_research/panel/panel_parameter_registry_v2_draft.md` |
| R2 | **动量守恒攻击**："S2 的 H 无中生有？S3a 创造容量？" | 正面转化为结论本身：账本逐项闭合（eps_H ≤ 4e-16），S2 的 +0.873 N·m·s 来自捕获前接近段推进剂（1.60 g 入账）；S3a 全文固定口径"可用动量交换区间平移"，同句给预置成本 3.00 g 与方向敏感性；Gate 0 四断言为机器背书 | `momentum_ledger.md`、`reviewer2_attack_response.md` 攻1/攻2、sim_12 Gate 0 裁决 JSON（待产） |
| R3 | **"阶梯图只是工程分类 / 可行域只是参数扫掠"** | 科学主张定位在**判据**而非分类：binding-gate dependent selection（同一工况 S1/S2 在结构门与资源门排序相反的数字支撑）；扫描背后有共轴解析骨架 + 精确二分边界；λ 非单调发现（1.08% 浅坑，设计预期被精确求解器证伪）证明求解器分辨率有科学产出 | `reviewer_audit_gate0.md` Q1/Q4、`sim_10_gate_check.json` X2/X4 |
| R4 | **撞车与划界**：Virgili-Llop & Romano 2019（联合轨迹设计）、2020 执行器协同分配、2025 MPC momentum counter-balance、Aghili 2024（existence proof） | 划界句式固定：他们回答"给定任务如何设计轨迹/控制器"，本文回答"哪些任务不存在可行策略、存在时选哪类"（existence/selection vs design，互补引用）；标题词用 strategy selection 避开 momentum shaping；文献覆盖度如实声明 5/6 并在投稿前补 contact-impulse 专线检索 | `文献缺口审计_20260718.md` §2/§5、`reviewer2_attack_response.md` 攻4/攻5 |
| R5 | **PROVISIONAL 阈值与锚链限制**：54.73 g 推进剂派生链、t_max=3600 s、执行机构 CLASS 占位、T_c=20 ms 未实测、e16 限制条款 | 全部集中入 PROVISIONAL 表并声明"结论条件于冻结阈值集"；T_c 已有 5–100 ms 扫掠包络（结论对 T_c 不敏感的范围如实给出）；B601 夹爪闭合时间实测列入 H1 计划；e16 引用处逐条复述其 gate 限制条款 | `sim_10_gate_check.json` `provisional_notes`、`sim_11_gate_check.json` `provisional_fields` + `bandwidth_sweep_diagnostic`、e16 gate 裁决 |

次级风险（正文预埋防线，不占 Top5）：sim_09 的 69 例同操纵度系网格设计使然的质疑——明写"同几何异动力学正是实验设计意图"并在 Discussion 提跨位形扩展；无微重力/在轨实验——定位为"仿真 + 机器裁决链验证"，与写作红线一致，不做任何硬件验证声称。

---

## 7. 与 Paper 2 / 比赛材料的边界（防自我重叠）

- 接触带宽在本文只作**方法节 + 适用域证据**（C3b，一图一段）；"理想冲量不适定性 + FFR/ANCF 保真域边界 + 切换面守恒一致性"的完整方法学归 Paper 2（Multibody Syst. Dyn. / JSV 口径）。
- sim_09 评价器全量（三级筛选、Pareto、fail-closed 选点）归 Paper 3 候选；本文只取其"几何指标退化"动机证据。
- Physics Agent / EXECUTE-ABORT 仅出现在 Discussion 展望与比赛 demo，不作为本文贡献（无学习组件、无硬件闭环，不可承受审稿）。
