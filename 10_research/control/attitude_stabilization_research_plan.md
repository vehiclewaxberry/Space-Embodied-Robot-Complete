# control_02 Research Plan — 基座姿态稳定：捕获前反冲抑制 + 捕获后组合体消旋
# 规划稿（只规划，不实施）— 2026-07-19；规划方：姿态控制科学家 Agent；PI 批准前禁止写任何控制代码
# 依据：10_research/partner_requirement_closure/state_truth_report.md 未闭合项 2
# （"姿态反冲稳定控制：有反冲预测 sim_05 19.20° 与执行器预算 sim_08，无闭环控制器 —— NOT_STARTED"）

> **2026-07-20 执行状态覆盖**：本文件保留为预注册历史；当前 machine verdict
> 为 `PASS_WITH_PROVISIONAL_SCOPE`，`review_status=PENDING_REVIEW`。7/16 仅在
> R5 PROVISIONAL 执行器及时窗模型下满足 `STABILIZED_WITHIN_WINDOW`，L0 硬件
> 有效稳定性 `NOT_EVALUATED_NO_ACTUATOR_DYNAMICS`。以
> `30_simulation/control_02_base_attitude/results/control_02_gate_check.json` 为准。

## 0. 定位与边界

- **本模块回答的是"控制层"问题**，位于已冻结的物理证据链之上：
  sim_05（反冲预测 19.20°）→ sim_06（捕获≠消旋，ω⁺=3.06°/s）→ sim_08（执行器/推进剂预算）
  → sim_10（可行域四门）→ sim_12（策略选择）。control_02 不重做上述任何一项
  （state_truth_report ALREADY_COMPLETE 清单约束），只补"闭环控制器 + 机器裁决"。
- **与 control_01（末端轨迹闭环）的边界**：control_01 管末端跟踪误差闭环；control_02 管
  基座姿态与组合体角速度。接口：Phase A 的反冲抑制会修改臂关节轨迹 →"末端轨迹劣化"
  指标即是交给 control_01 的接口量（同一 J*=generalized Jacobian 口径，sim_11 A1 已有数值）。
- **控制器不能改变可行域**：sim_10 区域图由动量与预算物理决定；control_02 只在可行区内
  改善"时间/品质/裕度"，在不可行区复现 ABORT。此为预注册断言（见 §8 P6），
  任何"控制器拯救了不可行任务"的结果一律先判账本错误。

## 1. Q1 科学问题

**在冻结执行器预算（3×100 mN·m·s 轮组 + 冷气推力器 54.73 g 共享账本）下，
基座姿态稳定的两个子问题各自需要什么控制架构、代价多少、边界在哪里？**

- A（捕获前）：臂作业反冲 19.20° 是否能用纯内部手段（零空间/轮组）压到任务门
  （registry 20°）以内？代价（末端轨迹劣化、轮组占用）随机动强度如何增长？何时必须动用推力器？
- B（捕获后）：组合体消旋的闭环实现相对 sim_08 开环预算的推进剂/时间开销是多少？
  轮组饱和调度与卸载如何与帆板激振约束共存？
- 输出不是"最优控制器"，是**控制架构 × 任务工况的代价-可达图**＋结果归属账本。

## 2. Q2 动量记账铁律与结果归属（先于一切代码）

铁律四条（10_research/sim_12/momentum_ledger.md 口径，逐字继承）：
1. **内部运动不改变总角动量 H**（臂、轮、帆板全部是内部件）；
2. **轮组只存储/重分配**，容量区间语义 |h_rw0+ΔH|≤h_max；
3. **只有推力器（外部力矩）才能移除动量**，ΔH_ext=∫r×F dt 逐项入账；
4. **容量与阈值取冻结链**：h_max=0.300 N·m·s（wheels_large，sim_08 assumptions.yaml，
   经 20_engineering/config/mission_feasibility/scan_v0.yaml SHA-256 锁定）；推进剂 54.73476731425644 g、
   J=32.205882352941174 N·s、消化上限 5.475 N·m·s@l_T=0.17 取
   30_simulation/e15_core_coverage/config/threshold_registry_core_v1.yaml 派生链。禁止另设数字。

**核心措辞纪律——两类结果严格分账，逐行机器标注 attribution 字段：**

| 归属标签 | 定义 | 允许宣称 | 禁止宣称 |
|---|---|---|---|
| INTERNAL_REDISTRIBUTION（反冲抑制） | ΔH_ext≡0，只改动量在体间的分布与姿态历史 | "基座姿态峰值下降""轮组暂存臂动量" | 任何含"消旋/移除/降低总 H"的表述 |
| EXTERNAL_REMOVAL（真正消旋） | ΔH_ext≠0 且与推力器冲量账逐项闭合 | "组合体 \|H\| 从 X 降到 Y，耗推进剂 Z g" | 未附冲量账本的任何 \|H\| 下降 |
| MIXED | A3/B2/B3 类协调控制 | 必须拆分内部/外部两行分别报告 | 合并成单一"性能提升" |

逐控制器归属预登记（实施时机器复核，不得手写）：

| 控制器 | ΔH_internal | ΔH_external | 归属 |
|---|---|---|---|
| A0 无补偿（sim_05 复放） | 0（零动量自由漂浮） | 0 | 基线 |
| A1 反作用零空间规划 | 0（纯运动学重分配） | 0 | INTERNAL |
| A2 臂+轮协调 | 0（轮⇄体交换，和为零） | 0 | INTERNAL |
| A3 臂+轮+受限推力器 | 轮⇄体部分 | ∫r×F dt ≠ 0（姿态硬保持代价） | MIXED |
| B0 捕获后无控 | 0（H_after=H_capture⁻ 恒等） | 0 | 基线 |
| B1 轮组-only | 轮⇄体交换直至饱和 | 0 | INTERNAL（**碎片工况预期 FAIL**） |
| B2 两段式（推力器粗消旋+轮精稳+卸载） | 精稳段交换 | 粗消旋+卸载段 ∫r×F dt | MIXED（消旋主张只归此行外部段） |
| B3 臂+轮+推力器全协调 | 臂惯量重构+轮交换 | 同 B2 | MIXED |

## 3. Q3 模型与保真度阶梯（复用冻结资产，只新增轮组状态）

- **L0 动量级**（Phase A 主力）：sim_05 `dynamics.py` 的 H_bb/H_bm 装配 + 零动量关系
  V_b=−H_bb⁻¹H_bm·q̇，**新增轮组动量状态 h_w**：p = H_bb·V_b + H_bm·q̇ + [0; h_w]。
  A0/A1 直接复用；A2 在此层闭环。
- **L1 力矩级刚体**（Phase A3 与 Phase B 主力）：组合体惯量来自 sim_06/sim_12 冻结
  rigidize（chaser_stack 26.5 kg + 目标，SSOT 装载）；轮矩饱和、推力器 PWM/最小脉宽在此层。
  **轮组最大力矩 τ_w,max 为新增 PROVISIONAL 参数**（sim_08 只有动量容量档，无力矩档）——
  入参数卡并列硬件待办，禁止散落硬编码。
- **L2 柔性抽检**（非判据）：sim_11 路线 A（FFR m=3 + 接触带宽 T_c=20 ms PROVISIONAL）
  对代表工况做帆板振动抽检；帆板参数占位（0.348 kg vs 真实差 5–10×，风险登记 №1），
  **FLEX 结论一律 UNKNOWN_NOT_IN_CRITERIA**（sim_10/sim_12 同纪律）；涉 ANCF 认证级
  主张须先重过 e15 `REPEAT_ANCF_CERTIFICATION` 口径。

## 4. Phase A — 捕获前臂作业反冲抑制

### 4.1 对比矩阵（证明集优先，扫描延后——sim_12 同纪律）

机动集（2 个）×控制器（A0–A3）= **8 例证明集**：
- **M1 锚点机动**：sim_05 headline（joint2 0→+60°、joint3 0→−40°、min-jerk 8 s、hold 至 12 s）。
  注意 sim_05 README 已声明 q2=+60° 超 URDF 限位，仅作动力学基准，非飞行轨迹——本计划继承该声明。
- **M2 限位合规机动**：同幅值量级、全程满足 URDF 关节限位与 e15 registry
  joint_limit_margin_min_rad=0.05 的任务型轨迹（指向抓点走廊，与 sim_04/sim_09 口径衔接）。

### 4.2 控制律候选（设计级，实施时允许等价替换但须留档）

- **A0**：开环复放（锚点门 GC1）。
- **A1 反作用零空间规划**：6 关节中以 (H_bm)_ang·q̇=0 为硬约束（3 约束），
  剩余自由度跟踪 3-DOF 末端位置（Jp 或 J_g 位置行）——方阵可解但会逼近奇异/限位，
  末端轨迹劣化与 condition_number_max=1e4（registry）在此成为 binding 候选。
- **A2 臂+轮协调**：前馈 h_w,cmd=−(H_bm·q̇)_ang + 基座姿态 PD 反馈（轮矩受限）；
  臂轨迹不改（末端零劣化为其卖点）。
- **A3 臂+轮+受限推力器**：A2 + 轮组占用超 0.8·h_max 或姿态超门时的推力器卸载/保持；
  "受限"= 最小脉宽、固定 l_T=0.17、推进剂计入 54.73 g 共享账本。

### 4.3 预注册数值锚（复算仲裁基准，引用勿改）

- M1 臂致角动量峰值 |（H_bm·q̇)_ang| = **0.0891 kg·m²/s**（sim_05 headline）
  → A2 轮组峰值占用预计 0.0891/0.300 ≈ **29.7%**，名义机动**预测无饱和**；
- A0 峰值 **19.20°**、几何相位 **2.6168°/循环**（闭合关节循环后基座净转动——A1/A2 必须
  同时消掉瞬态峰值与该累积项，报告分列）；
- A3 在名义 M1/M2 下**预测推进剂 = 0 g**（A2 已够）；若非零即控制分配设计缺陷，fail-closed。

## 5. Phase B — 捕获后组合体消旋稳定

### 5.1 工况集：逐字复用 sim_12 四例（20_engineering/config/strategy_feasibility/strategies_v0.yaml）

| 例 | 工况 | sim_10 区域 | 控制层预期 |
|---|---|---|---|
| A_low | 22 kg @0.5°/s | WHEELS_ONLY_FEASIBLE | B1 轮组-only 收敛（H≈0.0025 N·m·s 量级，sim_08 卫星线 0.015@3°/s 同口径） |
| B_anchor | 150 kg @3°/s（ω⁺=3.06333°/s） | INFEASIBLE_RATE | **反事实压力测试**：标注 OUT_OF_FEASIBLE_REGION，只用于对标 sim_08 消旋预算口径（36.5 g 冷气），不得进入可行性主张 |
| C_transition | 48 kg @2°/s | 过渡带 | B1 vs B2 切换点；与 sim_12 C→S3a（轮组预置省 13×）衔接：S3a 预置属策略层，B 段验证其执行层可实现性 |
| D_extreme | 150 kg @5°/s（H≈6.08 > 5.475 消化上限） | INFEASIBLE_RESOURCE | B2 必须复现预算超限 → ABORT；控制器不得"拯救" |

### 5.2 控制器

- **B0**：无控基线（H_capture⁻≡H_after 恒等复核）。
- **B1 轮组-only**：速率阻尼 τ_w=−k·ω 直至饱和；交付饱和时间 t_sat 与占用曲线
  （碎片类工况的 FAIL 本身就是交付物——把 sim_08 "12× 超容量"从静态预算升级为动态饱和过程）。
- **B2 两段式**（sim_08 架构的闭环化）：推力器偶粗消旋（bang-off-bang/PWM，τ=|H_c|/t_d 为
  开环参照）→ 轮组四元数反馈精稳 → 推力器卸载调度。
- **B3 全协调**：B2 + 臂构型重构（收拢降惯量/调抓点力矩臂）——臂贡献严格记 INTERNAL，
  只允许宣称"改变消旋时间/激振谱"，禁止宣称省动量。

### 5.3 帆板激振约束（B 段特有设计约束，非判据）

sim_11 A2 帆板振铃 ~2.1 mm@**1.0005 Hz**（占位参数）。粗消旋 PWM 开关谱若落在
0.8–1.2 Hz 带内有激振风险——预注册设计规则：脉宽调制基频避开该带或加陷波，
L2 抽检验证；帆板参数转正后此带宽随之重算（外部依赖 №1）。

## 6. 指标定义表（全部机器可算，阈值只认冻结源）

| 指标 | 定义/单位 | 阈值 | 来源与状态 |
|---|---|---|---|
| 基座姿态峰值 | max‖euler(t)‖，deg（A 段：机动全程；B 段：精稳段） | ≤ 20.0 | registry base_attitude_change_max_deg（PROVISIONAL） |
| 稳定时间 | A：机动结束→\|θ_err\|<0.5° 且 \|ω\|<0.01°/s；B：粗消旋 t_d + 精稳收敛，s | t_d ≤ 3600 | scan_v0.yaml t_detumble_max_s；0.5°/0.01°/s 为本计划新设 PROVISIONAL，入参数卡待 PI 冻结 |
| 捕获后角速度 | ω⁺ 及 ω(t) 收敛史，°/s | ≤ 2.0 | registry post_capture_rate_max_dps（MISSION_ASSUMPTION） |
| 轮组动量占用/饱和时间 | max\|h_w\|/h_max（%）；\|h_w\|→h_max 的 t_sat（s） | \|h_w\| ≤ 0.300 N·m·s | sim_08 assumptions.yaml wheels_large（哈希锁） |
| 推力冲量/推进剂 | ∫\|F\|dt（N·s）；m_p（g），A/B 段合并共享账本 | ≤ 32.206 N·s / ≤ 54.735 g | registry 派生链（duplicate_root=wheel_momentum） |
| 末端轨迹劣化 | max/RMS 末端位置偏差（mm）+ 任务时间延长（%），vs 名义轨迹（J_g 口径） | 报告值；门槛待 control_01 联合冻结 | 本计划新设 PROVISIONAL |
| 帆板振动 | flex_energy（J）+ 板尖位移（mm），L2 抽检 | 参考 1e-3 J | registry flexible_energy_max_J；**非判据**（FLEX=UNKNOWN 纪律） |
| 稳定裕度 | ①线化闭环 GM/PM（B2 精稳段）；②鲁棒系数 = 目标惯量缩放 ∈[0.5,2]（RA-003 低置信）下全门仍 PASS 的最大区间 | GM≥6 dB、PM≥30°（工程惯例） | 本计划新设 PROVISIONAL |

## 7. 机器 Gate 设计（fail-closed，任一 FAIL 如实冻结）

- **GC0 守恒与归属账本**（对应 sim_12 GS1 口径）：
  a) 所有 INTERNAL 例：\|H_total(t)−H_total(0)\| ≤ 1e-12（reduced 口径，阈值同 sim_11 G1）；
  b) 轮⇄体交换逐时刻闭合：Δh_w + ΔH_body ≡ 0（≤1e-12）；
  c) 所有 MIXED/EXTERNAL 例：\|ΔH_total − ∫r×F dt\| ≤ 1e-12，推进剂 m_p 由公式复算非手抄；
  d) attribution 标签由账本数值机器判定（\|ΔH_ext\|<阈值→INTERNAL），禁止手写。
- **GC1 sim_05 锚点**：A0 复放峰值 19.20°——同求解器恒等 ≤1e-12；对 sim_05 CSV 交叉
  对拍取半末位容差（sim_10 X1 的存储分辨率教训，恒等由求解器承担）。
- **GC2 sim_06/sim_10 锚点与区域一致性**：B0 的 ω⁺=3.0633304945807067°/s 恒等 ≤1e-12；
  四例控制结局与 sim_10 区域标签一致性断言（§5.1 表末列），B_anchor 结果强制携带
  OUT_OF_FEASIBLE_REGION 标注，缺标注即 Gate FAIL。
- **GC3 sim_08 锚点**：m_p = \|H_c\|/(l_T·Isp·g0) 复算 3.65/(0.17·60·9.80665)=36.5 g（冷气）
  与 12× 轮组超容比逐位复现；B1 碎片类饱和结局复现"wheels-only infeasible"。
- **GC4 sim_12 账本锚**：触及 S3a/S4 语义处（C_transition 预置、共享 54.73 g）与
  momentum_ledger.md 数字逐位一致；**闭环推进剂 ≥ 动量下界 m_p,min=\|ΔH_ext\|/(l_T·Isp·g0)
  机器断言**——低于下界=记账错误，直接 FAIL。
- **GC5 预算门与哈希锁**：全部阈值经冻结 registry/参数卡装载，frozen_inputs SHA-256 校验，
  `thresholds_widened=False` 断言（scan_v0.yaml 铁律继承）。
- **GC6 确定性与口径纪律**：定种复跑逐位；FLEX 列只报告不裁决；裁决只认
  `results/control_02_gate_check.json`（verdict：CONTROL02_PHASE{A,B}_GATES_PASS）。

## 8. 预注册断言与主张纪律

预测（待机器裁决，写入裁决 JSON 对照）：
- P1：A1 可将 M1 峰值 19.20°→<2°（量级），代价为末端劣化非零且随机动幅值增长；
- P2：A2 峰值占用 ≈29.7% 无饱和；几何相位累积项被反馈闭合；
- P3：A3 名义工况推进剂=0 g（非零即 FAIL）；
- P4：B1 t_sat 解析预估 h_max/τ_w,max 与仿真一致（τ_w,max PROVISIONAL）；A_low 轮组-only 收敛；
- P5：B2 闭环推进剂 ≥36.5 g（B_anchor 对标口径）且 ≤54.73 g 门内；
- P6：任何例的可行性标签相对 sim_10 不翻转（控制器不创造可行域）。

allowed：反冲抑制降低基座姿态峰值（INTERNAL）；两段式消旋以 X g 推进剂移除 Y N·m·s（EXTERNAL，附账本）；
binding-gate dependent 控制架构选择（sim_12 判据框架的控制层延伸）。
forbidden："轮组消旋了目标"；"零空间规划移除了动量"；"反冲抑制降低捕获后 \|H\|"；
"控制器扩大可行域"；柔性门任何结论；无条件控制器排序；未附账本的性能主张。

## 9. 文件与验收

```
30_simulation/control_02_base_attitude_stabilization/{src,results,tests,docs}
20_engineering/config/attitude_stab/attitude_stab_v0.yaml  # 零硬编码；frozen_inputs 哈希锁；新 PROVISIONAL 参数集中于此
10_research/control/momentum_attribution.md    # Gate C0 评审产物（§2 表的数值化），PI 批准前不得写控制代码
```
交付：control_results.csv（含 attribution 列）/ 代价-可达图（A：峰值 vs 末端劣化 Pareto；
B：推进剂-时间-饱和三视图）/ control_02_gate_check.json（GC0–GC6）/ 复现命令。
建议窗口：8/05–8/20（与 B601 H0/H1 并行，τ_w,max 与 T_c 实测同窗）；先 8+12 例证明集，
扫描延后。停止规则：Phase A Gate 未 PASS 不开 Phase B 代码。

## 10. 风险与外部依赖

1. 帆板参数占位（差 5–10×）→ B 段激振带与 L2 抽检结论全部 PROVISIONAL（待办 3 优先级最高）；
2. τ_w,max 无冻结源 → 新增硬件待办：轮组力矩档 COTS 数据表（与夹爪 T_c 实测同清单）；
3. T_c=20 ms 占位 → B0/B2 捕获瞬态用 sim_11 带宽口径时须标注；
4. RA-003 目标惯量低置信 → 稳定裕度②的鲁棒扫描即为缓解手段；
5. e15 REPEAT_ANCF_CERTIFICATION 未闭环 → 本模块不做 ANCF 级主张，绕开该 Gate。

## 11. Rollback

control_02 独立目录只新增；失败不回改 sim_05/06/08/10/11/12 任何冻结工件；
裁决 JSON 保留 FAIL 历史；attribution 账本随 FAIL 一并入库。

---

## Task Card（工单，同 sim12-strategy-agent 款式）

# Agent: control02-attitude-agent（P1）

## Role
航天器姿态控制专家。实现 control_02：捕获前臂作业反冲抑制（A0–A3）与捕获后
组合体消旋稳定（B0–B3）的闭环控制对比研究——研究**控制架构的代价与归属**，
不重做可行域、不做学习类控制器。

## 先读真值
`CLAUDE.md`、本计划全文、`10_research/sim_12/momentum_ledger.md`（铁律四条）、
`30_simulation/sim_05_free_floating_arm/`（H_bb/H_bm 与 19.20° 锚）、
`30_simulation/sim_08_detumble_actuator_budget/`（预算锚与 assumptions.yaml）、
`20_engineering/config/mission_feasibility/scan_v0.yaml`（frozen_inputs 哈希与执行器档）、
`30_simulation/e15_core_coverage/config/threshold_registry_core_v1.yaml`（阈值唯一来源）、
`30_simulation/sim_11_coupled_dynamics/`（L2 抽检与接触带宽口径）。

## 动量归属评审先行（Gate C0，未过不得写控制代码）
产出 `10_research/control/momentum_attribution.md`：逐控制器
H_before / H_after / ΔH_internal / ΔH_ext(=∫r×F dt) / attribution，
含 §4.3/§8 全部预注册数值。**反冲抑制=内部重分配，真正消旋=外部移除，
逐行机器标注，禁止混写。** PI 批准账本后方可进入实施。

## 输出
8 例（Phase A）+ 12 例（Phase B）证明集 → control_results.csv（attribution 列强制）
→ 代价-可达图 → `results/control_02_gate_check.json`（GC0 守恒/GC1 sim_05/
GC2 sim_06+sim_10 区域一致/GC3 sim_08/GC4 sim_12 账本+推进剂下界/GC5 哈希锁/GC6 确定性）。

## 红线
禁止 RL/VLA；禁止修改任何冻结 sim 工件；阈值取同一冻结 registry，
thresholds_widened=False；FLEX 非判据；新参数只进 attitude_stab_v0.yaml 并标
PROVISIONAL；B_anchor 必须带 OUT_OF_FEASIBLE_REGION 标注；任一 Gate FAIL 如实冻结。
