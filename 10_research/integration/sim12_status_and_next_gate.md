# sim_12 Phase1 验收评估与下一 Gate 裁决 — 2026-07-19

> 角色：系统集成科学家（只读评估，未触碰任何 sim 代码）。
> 证据基（全部磁盘复核，非记忆）：
> `30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json`（verdict=**SIM12_PHASE1_GATES_PASS**）、
> `30_simulation/sim_12_strategy_feasibility/results/strategy_results.csv`（16 行）、
> `30_simulation/sim_12_strategy_feasibility/docs/strategy_comparison_report.md`、
> `30_simulation/sim_12_strategy_feasibility/src/strategy_eval.py`、`tests/run_all.py`、
> `10_research/sim_12/phase1_workorder.md`、`10_research/sim_12/strategy_definition.yaml`、
> `30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json`（SIM10_GATES_PASS）、
> `10_research/partner_requirement_closure/state_truth_report.md`（Gate A0 PASS）、
> `01_project/competition/研究战略裁决_第二收敛点_20260717.md`。
> **前提锁定：Phase1 已完成，本文不提议任何形式的重做。**

---

## 1. 总验收结论

**sim_12 Phase1 满足"策略选择证据"要求，验收 PASS。**
GS1/GS2/GS3 三门全部闭合且有机器裁决背书；B-S1 与 sim_10 碎片锚点逐位一致
（tests 断言 <1e-12，实际差 0.00e+00）；核心科学主张
"**最优捕获策略 = binding gate 的函数，不存在无条件排序**"已由 16 例
机器证明成立。S4 专属带未覆盖与 S3a 方向敏感性未扫**均不阻塞下一步**
（判定依据见 §4），但必须以合约条款形式进入工具层的 fail-closed 边界。
**下一 Gate = 直接进工具化（Physics Tool Contract Gate，建议编号 T-Gate/sim_13），
策略维大扫描降级为并行 revision 弹药，不上关键路径**（裁决理由见 §5）。

---

## 2. GS1–GS3 逐门验收

### GS1 守恒 — 闭合 ✅
- 工单要求：ΔH_internal=0 全例机器断言，账本闭合 ≤1e-12。
- 实测：`max_eps_H = 3.85e-16`（好于门槛约 3.5 个量级）；
  S2 矢量闭合 `s2_vector_closure_max = 2.22e-16`（ΔH_vec = m_c(r_c−r_com)×v_match
  与 H(α=1)−H(α=0) 的矢量闭合，Gate0 Reviewer-2 修正后口径，|ΔH_vec|=1.435 N·m·s
  与 B 案 CSV 行 `ledger_dH_external_Nms=1.435081` 一致）。
- 每例账本行（H_before/H_after/ΔH_ext/ΔH_int）齐备于 `strategy_results.csv`
  （`ledger_*` 列），S1/S3a/S4 的 ΔH_ext=0、S2 的 ΔH_ext>0 与
  `strategy_definition.yaml` 的策略定义逐项对应。**这是"动量记账是本模块科学
  诚实生命线"（战略裁决 §4.2）要求的完整落实。**

### GS2 策略分化 — 闭合 ✅（附一处口径差异发现 F1，见下）
- 机器输出 `best_per_case`：A_low→S1、B_anchor→ABORT、C_transition→S3a、
  D_extreme→ABORT。判据（`strategy_eval.py` L145–152）：选择结果 ≥2 类，
  且无任何非 ABORT 策略赢得全部案例 → 无条件排序被机器排除。
- C 过渡带是分化的决定性证据：S1/S2 均 INFEAS(WHEEL)，唯一能平移轮组容量
  球心的 S3a FEAS(3.0 g)，S4 FEAS(~40 g)——S3a 对 S4 省 ~13× 推进剂。
  这直接回应 Reviewer-2 攻击 2（"S2 只是特殊工况?"→过渡带覆盖）。
- REPEAT_CORE 在策略空间复现：B/D 案四策略全灭于 RATE 门（2°/s registry），
  e16 的控制口径结论推广到策略类口径。

**验收发现 F1（如实记录，不改变验收结论）**：工单 GS2 原文为"每策略至少
一例最优/一例劣"（强式），实现判据为"无策略在全部案例最优"（弱式）。
16 例中 **S2 与 S4 从未胜出任何案例**。深看这不是缺陷而是物理事实：
- S2 在冻结的刚体 gate 集（RATE/WHEEL/资源）下**由构造不可能最优**——它降低
  接触冲量但恒增 |ΔH_ext|>0 且恒有正燃料成本；其价值恰是 Impulse–Momentum
  Decoupling 的反例证据（B 案：冲量 0.338→0.194 N·s（−43%）而 H 3.651→4.524
  N·m·s（+24%））。S2 的"最优带"只会出现在接触载荷/柔性激振类判据进入 gate
  集之后（依赖 sim_11 带宽口径 + e15 认证闭环，FLEX 现为 UNKNOWN 不入判据）。
- S4 的胜出带 H∈(0.6, 5.47] ∧ ω⁺≤2°/s 解析存在（S3a 球心平移上限 0.6 N·m·s、
  推进剂预算上限 ~5.47 N·m·s）但四例设计未落点其中（报告 §结论 4 已自我申明）。

F1 的处置：gate JSON 已透明记录 `best_per_case`，主张边界由 GS3 守住
（"any unconditional strategy ranking" ∈ forbidden 双向适用——既禁止排序
也未宣称"每策略各有胜区"）。**论文与工具中引用 GS2 时必须使用弱式表述**：
"无策略在全部工况最优 / 选择由 binding gate 决定"，不得写成"四策略各有
最优区间"（S2 在当前判据集内无胜区，S4 胜区未被案例见证）。

### GS3 主张审计 — 闭合 ✅（性质=清单生成+人工复核，非数值断言）
- allowed 3 条 / forbidden 4 条已产（gate JSON 内），数字由运行时结果字符串
  插值生成（无手抄）。注意 `strategy_eval.py` L169 `gs3 = True` 为固定值：
  该门的机器部分是"清单必须生成"，判 allowed/forbidden 的正确性靠人工复核
  ——本次验收人工复核通过：3 条 allowed 均有 CSV 行/账本行背书，4 条
  forbidden 均对应真实的过度主张风险（含 F1 情形）。
- 纪律遵守核验：S3b 不在集合（tests `t_s12_s3b_placeholder_absent` 防呆断言
  参数卡不含 S3b）；flex_energy 全列 `PROVISIONAL_NOT_EVALUATED`；
  `flex_status = UNKNOWN_NOT_IN_CRITERIA`；语言纪律（"Impulse–Momentum
  Decoupling"而非"velocity matching paradox"）在报告与 JSON 中一致。

### 锚点与测试
- tests 3/3 PASS：Gate 复跑 + B-S1 锚点逐位（ω⁺=3.0633304945807067°/s、
  H=3.650992635553959 N·m·s，与 sim_10 `X1_anchors_vs_sim06` 的
  solver_identity_diff=0.0 同源）+ S3b 防呆。
- 与 sim_10 的一致性是**同求解器逐位**（sim_12 只读复用 sim_10
  feasibility_core），信任等级最高的一档。

---

## 3. 交付物齐套性核对（对工单清单）

| 工单要求 | 磁盘现状 | 判定 |
|---|---|---|
| strategy_results.csv | 16 行 + 统一 schema + 账本列 | ✅ |
| strategy_comparison_report.md | `30_simulation/sim_12_strategy_feasibility/docs/` 下，含结果矩阵 + binding-gate 分析 | ✅ |
| strategy_ladder_initial.png | results/ 下（Selection Map 口径） | ✅ |
| binding_gate_analysis.md | **未单独成文**——内容并入 comparison_report §Binding-Gate 分析 | ✅（实质满足，形式合并；不构成缺口） |
| sim_12_gate_check.json（GS1-3） | 齐 | ✅ |
| 复用 sim_10 只读 + Gate0 账本仲裁 | `ledger_arbitration` 指向 momentum_ledger.md | ✅ |

---

## 4. 两个未覆盖项是否阻塞下一步 — 判定：**均不阻塞**

### 4.1 S4 专属带未被 4 例覆盖 — 不阻塞
理由：
1. **范围纪律**：Phase1 工单冻结为"16 例证明集，完成后停止"，PI 已批准该
   范围；专属带扫描在报告中已预注册为"策略维扫描（revision 弹药）"。
2. **主张边界已自洽**：GS3 未 allowed 任何涉及 S4 胜区的主张；当前全部
   allowed claims 不依赖该带。不存在"已发表主张缺证据"的悬空。
3. **下游可用性**：Physics Agent 演示脚本（150kg@3°/s→ABORT→0.5°/s→EXECUTE，
   战略裁决 §5）只需 A/B 两类已证案例；S4 专属带不在演示路径上。
4. **工具层可解析处置**：该带边界（0.6 = 轮容量平移上限、5.47 ≈ 推进剂预算
   ×Isp×g0×l_T）是 gate 结构的闭式推论，工具可按查询点在线复算判定，无需
   预扫描网格——落带查询返回 S4 时标注 `coverage=ANALYTIC_NOT_CASE_PROVEN`。

### 4.2 S3a 方向敏感性未扫（θ=0 名义）— 不阻塞，但构成硬性主张限制
理由与限制：
1. `evaluate_cell` 已带 `theta_deg` 参数且 `strategy_definition.yaml` 预注册
   扫掠 [0,15,30,45,60]（60°=归零悬崖点）——代码路径存在，只是未跑、未入 Gate。
2. C 案 S3a 的胜出（Phase1 核心分化证据）是 θ=0 理想预测下的结论。**在扫掠
   入 Gate 前，任何"S3a 鲁棒/工程可用"的表述都是 forbidden 级过度主张**；
   工具层 `recommend_strategy_class` 推荐 S3a 时必须携带
   `assumption: theta_pred_error=0 (UNSWEPT)` 标注并降 confidence。
3. 它不阻塞工具化的原因：工具合约本身就是把这类限制机器化（fail-closed
   返回而非人背口径）。反而是先建合约、把 θ 扫掠做成合约 Gate 的一个
   升级项（T-Gate 通过后跑 5 点扫掠即可将标注解除），顺序更经济。

---

## 5. 下一 Gate 裁决：**直接进工具化，策略维扫描降级为并行弹药**

### 5.1 裁决
下一 Gate = **Physics Tool Contract Gate**（建议落位 `30_simulation/sim_13_physics_70_tools/`
或 `70_tools/physics_agent/`，工具合约见姊妹文档
`10_research/integration/system_interface_plan.md`），验收对象是四个工具
（compare_strategy / query_binding_gate / estimate_resource_cost /
recommend_strategy_class）的机器合约，不是新的物理结论。

### 5.2 理由（按权重排序）
1. **关键路径**：距 2026-09-01 约 6.3 周。战略裁决 §7 排期 Physics Agent MCP
   在 8/08–8/18，而 sim_10/11/12 已全部提前闭合（state_truth_report：
   "Physics Tool 合约"是未闭合项 5、状态 PLANNED，且是 H3 Agent 闭环的
   前置）。当前稀缺资源是集成与材料时间，不是物理证据量。
2. **边际科学收益不对称**：策略维扫描只提高 Selection Map 分辨率、见证 S4
   胜区——全部属于 revision 弹药（报告原话），不新增任何 allowed claim，
   也不解除任何现有 forbidden。工具化则解锁 H3、比赛演示与 Paper 1 的
   "AI 决定有 gate_check 背书"叙事，是新能力。
3. **证据充分性**：策略选择证据的三要素（守恒机器断言、分化机器证明、
   主张审计清单）已闭合；工具只暴露已证结论 + fail-closed 边界，不需要
   更密的网格来"更正确"。
4. **纪律一致性**：sim_12 工单红线"禁止大扫描/Physics Agent/控制器，完成后
   停止"——Phase1 停止后进入下一模块（工具合约）正是该纪律的延续；而
   "先扫 9000×4 再工具化"等于回头做被明令延后的大扫描。

### 5.3 策略维扫描（Phase 2）的触发条件（满足其一才启动，不上关键路径）
- Paper 1 revision 收到"Selection Map 分辨率不足 / S4 区间未见证"类审稿意见；
- 比赛演示需要 C 带之外的策略切换可视化；
- T-Gate 通过后有富余机时（strategy_eval 单例毫秒级，9000 点 × 4 策略
  技术上一夜可完成——正因便宜，更不该现在挤占集成窗口）。
- θ 扫掠（4.2）例外：**建议作为 T-Gate 的升级断言在工具化完成后立即补跑**
  （5 点 × C 案 ≈ 分钟级），因为它解除的是工具输出上的 confidence 降级，
  收益直接作用于演示质量。

### 5.4 建议的 T-Gate 四门（预注册，细节见接口计划文档 §6）
- **T1 锚点一致**：工具对 A/B/C/D×4 策略共 16 查询的返回与
  `strategy_results.csv` 逐位一致；对 sim_10 两锚点与 `sim_10_gate_check.json`
  X1 数字逐位一致。
- **T2 fail-closed 覆盖**：域外查询（m_t/ω/几何类超 scan_v0 参数卡域）、
  FLEX 类查询、θ≠0 的 S3a 置信查询，必须返回
  UNKNOWN / OUT_OF_COVERAGE / PROVISIONAL 标注，禁止外推猜测——负例测试
  入 Gate。
- **T3 主张审计传递**：`recommend_strategy_class` 的 rationale 字符串只能由
  GS3 allowed 清单 + gate JSON 字段拼装（机器可枚举校验）；forbidden 短语
  出现即 FAIL。
- **T4 registry 哈希锁**：工具启动时校验冻结 registry 与上游 gate JSON 哈希
  （复用 sim_10 `R_frozen_hashes` 口径）；上游 verdict 非 PASS 时对应工具
  拒绝服务（e15 `REPEAT_ANCF_CERTIFICATION` 未闭环 → 一切 flex 数值不可暴露）。

---

## 6. 验收附带条件（进入工具层的强制条款）

1. e16 引用必须复述其 geometry/flex 限制条款（S2 相关输出继承）。
2. flex_energy 字段永远原样透传 `PROVISIONAL_NOT_EVALUATED`，直到 e15 口径
   再认证闭环 + 杨恒参数卡转正（帆板 0.348 kg 占位为 Paper 1 最大硬伤，
   CLAUDE.md 待办 3）。
3. 执行器档为 sim_08 placeholder CLASS 值、T_c=20 ms 占位（待办 2）——工具
   evidence 块必须携带 `provisional_notes` 透传。
4. GS2 表述一律弱式（见 F1）；S3a 推荐必携 θ=0 未扫标注直至扫掠入 Gate。

**验收签发：sim_12 Phase1 = PASS（策略选择证据成立）；下一 Gate = Physics
Tool Contract Gate（工具化）；无重做项；无阻塞项；4 条附带条款随合约生效。**
