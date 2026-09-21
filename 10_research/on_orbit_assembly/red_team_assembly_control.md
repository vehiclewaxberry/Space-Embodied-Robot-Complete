# 红队审查 — 装配力学与控制规划（ASM-00/01/02 三计划 + SSOT + Gate 注册表 + DAG）

审查人：空间装配力学与控制审稿人（红队，只读）｜日期 2026-07-20
对象：`interface_mechanics_plan.md`、`phased_control_plan.md`、`contact_flexible_dynamics_plan.md`、
`interface_ssot_draft.yaml`、`gate_registry.yaml`、`dependency_dag.md`
物理对照：`30_simulation/control_01_end_effector_tracking/results/control_01_gate_check.json`、
`30_simulation/control_02_base_attitude/results/{stage_a_summary.json, wave1_risk_update.csv}`、
`20_engineering/config/attitude_stab/attitude_stab_v0.yaml`、`30_simulation/sim_11_coupled_dynamics/src/{contact_window.py, coupled_dynamics.py}`、
`30_simulation/sim_09_grasp_evaluator/src/ik.py`、`10_research/rom/model_fidelity_selection_rules.yaml`。

事实核验（引用数字逐位对拍，全部命中）：GC1_A2 Δ=0.15504°>0.05°、C2_T1 诊断 0.00645°、
C3 vs C2_MATCH5 +1.8387e-5%、C2 前馈 −38.26%、GC1_F C1_T3 p95 0.19021 m>0.11 m 均与
gate JSON 逐位一致；W1-R12 0.033/0.021 N·m 与 wave1_risk_update.csv 第 13 行一致；
`attitude_stab_v0.yaml` 同时存在 `stage_a.A2.wheel_torque_limit_Nm: null`（144 行附近）与
`stage_b.actuator_dynamics.wheel_max_torque_Nm: 0.01`（158 行）两个键；
`generalized_jacobian` 公式、`Q_ext=Φᵀw_S` 注入路径（contact_window.py 93–95 行）、
sim_09 `residual_and_jacobian`/`_diagnose`（ik.py 87/151 行）均如计划所述存在。
RF-1/2/3 算术复核：8·tan15°=2.144 mm、tan16.7°≈0.300、0.05/12 rad=0.24°、0.1/12 rad=0.48°，
深锥案 19·tan15°=5.09 mm、宽锥案 8·tan32°=5.00 mm——全部正确。

---

## ① RF-1/2/3 处置彻底性与两计划一致性 — **NEEDS_FIX**

ASM-00 内部处置是彻底的：三面红旗全部机器化（AG0-C1/C2/C3），RF-1 缺字段被显式登记为
"必然 UNKNOWN → 阻塞转正"，fail-closed 链完整（DAG 硬边 1：AG0 未过 → ASM-02 禁用参数）。
但**跨计划一致性有三处漏洞**：

1. **AR4 缓解被当作已成立事实使用**。`phased_control_plan.md` §0 负结果 4 与 §4.1 P1→P2
   判据、`risk_register.csv` AR4 缓解列，都把"锥面捕获域（粗 5 mm/5°）吸收跟踪误差"写成
   现在时——而 RF-1 的结论恰是该捕获域**当前不可计算**（缺 r_t/r_m），且 v0 聚拢量仅
   2.14 mm。缓解并非"失效"，而是"未证实却被两处文本当作前提"。
   **修改**：P1→P2 进入条件改写为 "(δr, δθ) ∈ C_T1"，其中 C_T1 = AG0-C1 通过后由 T1
   输出的 δr_max(δθ) 认证曲线；SSOT coarse 5 mm/5° 只作 C_T1 的候选外包络，不得直接
   当切换门。AR4 缓解列补"以 AG0-C1 PASS 为生效前提"。
2. **S2 场景的箱角问题**。捕获域是耦合曲线 C(δr, δθ)，S2"横 5 mm ∧ 角 5° 同时取满"是
   公差箱的角点，即使 RF-1 修正后也很可能在曲线外。作为 AC0 的应力场景合理，但 AC2 的
   P1→P2 门若按箱判据放行，将在捕获域外进入接触。
   **修改**：S2 保留，但预注册声明"S2 角点若被 T1 判定在 C_T1 外，则该场景的合法出口是
   回退/ABORT 而非插入成功"，防止把域外接触算进失败率对比的分母语义混乱。
3. **RF-1 修正选项与 RF-2 耦合未声明**。RF-1 三选一中的"加深锥 d_c≈19 mm@15°"保持
   α=15°，则 tanα=0.268<μ=0.3，AG0-C3（tanα ≥ k_margin·μ）在 k_margin≥1 时仍 FAIL——
   深锥选项**单独不能同时解 RF-2**；只有宽锥（α≈32°）或换材料对（降 μ）才能双解。
   **修改**：interface_mechanics_plan §2.2 补一句"T1 输出联合 (α, d_c, μ) 可行域图，
   RF-1 修正案必须在 RF-2 约束下选取"，避免 ASM-00 执行者按序单独闭环两旗。

另一处量化空洞：§2.5 总链不等式左端"臂端定位误差（接近窗内）"目前**没有任何证据源**。
CTRL-01 的负结果在预注册轨迹 T1/T2/T3 上（T3 违例 0.19 m 是快速大机动段，量级为粗公差
38 倍），慢速接近段的臂端误差从未被测过。**修改**：ASM-02 预注册一条 P1 代表性接近轨迹
的跟踪界测量行（冻结增益、不调参、只测量），作为 §2.5 链左端的证据输入；在此之前该
不等式只能标 UNKNOWN。

## ② W1-R12 统一 0.01 N·m/轴裁定 — **NEEDS_FIX**（方向正确，四处精化）

裁定方向正确：0.033 不是硬件档而是无约束模型的隐含需求，不得升格（与
wave1_risk_update.csv W1-R12 行的登记语义一致）；R12-3 把重评结果写入 ASM-02 自己的
results、不回改冻结 CTRL-02 工件，**与 CTRL-02 冻结纪律不冲突**。问题：

1. **键路径歧义**：`attitude_stab_v0.yaml` 同时有 `stage_a.A2.wheel_torque_limit_Nm: null`
   （A2 显式声明无力矩动力学）与 `stage_b.actuator_dynamics.wheel_max_torque_Nm: 0.01`
   （R-5 PROVISIONAL 档）。R12-2 只写字段名不写全路径。
   **修改**：R12-2 明确引用 `stage_b.actuator_dynamics.wheel_max_torque_Nm` 全键路径 +
   文件哈希，并注明 stage_a 的 null 键是"缺失登记"不是第二来源。
2. **字面量扫描断言不可实现**：仓库内 "0.01" 字面量出现于无数无关处（时间步长、裕度等）。
   **修改**：R12-2 的一致性测试限定为"`20_engineering/config/**/*.yaml` 中匹配 `wheel.*torque` 键名的
   数值字段"，白名单冻结历史工件，否则该测试永远 FAIL 或被迫放水。
3. **重评口径欠一笔**：Stage-A A2 是 momentum-level ideal（`fidelity_note:
   PROVISIONAL_IDEAL_MOMENTUM_TRACKING_NO_TORQUE_DYNAMICS`），"重放 + 限幅"必须新增
   ḣ_w 通道——这是模型扩展不是纯重放，且存在两种不同实验：(a) 理想分配结果事后饱和
   截断；(b) 在限幅约束下重新分配。两者的"峰值不再为零"幅度不同。
   **修改**：R12-3 预注册指明取 (a)（最小诚实版），网格取 stage_a_timeseries.csv 同款
   离散，指标 = 限幅下 peak_base_dev 与原零峰值的差；(b) 留作 AC3 本体。
4. **闭口条件须显式**：W1-R12 的登记关闭条件是"硬件力矩冻结后同一限值重评"。R12-3 在
   PROVISIONAL 0.01 下的重评**不关闭 W1-R12**。
   **修改**：§6 增一句"R12-3 完成后 W1-R12 保持 OPEN，直至 R12-5 硬件触发重跑"，防止
   重评行被引用为风险闭口。

## ③ 目标星帆板结构性缺口（D 发现）与 SCREENING_ONLY 上限 — **FATAL（计划态可修，Wave A 批准前必须修）**

`contact_flexible_dynamics_plan.md` §0 诚实登记了缺口（sim_11 帆板在追踪星侧、目标是
刚体）并给出 Phase A 上限 `ASM01_SCREENING_ONLY`、AG4-5 硬门。**但 phased_control_plan
全文不含 Phase A/B、不含"目标星帆板"缺口的任何字样**，且存在一条成功语义的旁路：

- SSOT 八判据 = 位置/姿态/深度/LOCKED/接触力/轮资源/**flexible_response_within_
  validated_envelope**/**provenance_complete**。AG3-b 自称"接口 SSOT 八判据的机器化"，
  实际枚举的合取 = 几何 4 项 ∧ 力学 4 项 ∧ 资源 3 项——**恰好漏掉第 7、8 两项**。
  `gate_registry.yaml` AG3 硬条款"成功=几何AND力学AND资源"把这个 6/8 版本**注册表化**，
  与同文件底部 `assembly_success_definition`（八项全满足、任一 UNKNOWN 不判 success）
  自相矛盾。
- 后果：ASM-02 的全部 run 都在 Phase A 世界（目标刚体）里执行，flexible_response 结构性
  UNKNOWN；但 AG3-b 的合取里没有这一项，于是每 run 可以机器判 `success=true`，
  AG3-a 的 fail_rate 统计与"失败率更低"headline 随之成立——**装配成功在 ASM-01 侧被
  SCREENING_ONLY 禁判，却在 ASM-02 侧被重新定义后判出**。rom_safety_plan AG5-B 的
  "SCREENING_ONLY 入 ALLOW provenance"负例只封运行时授权面，封不住 ASM-02 结果文件
  与集成裁决里的统计口径。
- 附带逻辑洞：若按八判据，Phase A 内 success≡UNKNOWN，则 fail_rate 分子分母皆无定义，
  AG3-a 断言不可求值 → 按 fail-closed 应 UNKNOWN，整个四基线对比失去裁决量。

**修改（三条，缺一不可）**：
1. 成功判据单一实现：由 ASM-01 提供唯一的 `evaluate_assembly_success()`（机器读 SSOT
   八项，Phase A 下 flexible_response 恒返 UNKNOWN），ASM-02 只准调用不准重写；
   `gate_registry.yaml` AG3 硬条款改为"成功=SSOT 八判据单源求值"。
2. ASM-02 的 AG3-a 统计量改名并重定义：不叫 assembly success/fail_rate，改为
   `control_failure_rate`，failure 事件显式枚举 =（精公差违例 ∨ JAMMED ∨ QP 不可行
   ∨ SAFE-00 ABORT/BACKOFF 终态 ∨ 超时 ∨ 相位序列非法），与 assembly_success 解耦；
   phased_control_plan §5/§7/§8 与 Task Card 同步改词。
3. phased_control_plan §0 增"继承 ASM-01 Phase A/B 划分与 ASM01_SCREENING_ONLY 上限"
   段落，claim_forbidden 增"Phase A 世界内任何 assembly success 率表述"。

## ④ 卡滞判据/公差链/接触状态机接口一致性 — **NEEDS_FIX**

1. **两点接触角公式差一倍（RF-3 的跨文件复现）**：interface_mechanics_plan §2.3 用
   θ_max ≈ c_r/l（半径间隙口径，0.24°@直径解读）；contact_flexible_dynamics_plan §3.1 用
   θ_2pt ≈ c·d/l = c_diam/l（0.48°）。同一几何事件两个公式、两计划各取一支。
   **修改**：统一从 L11 推导一次并全仓单源（建议 θ_bind ≈ (D−d)/l 为几何绑定角、
   c_r/l 为保守设计角，二者显式命名区分），RF-3 定案后两文件同步替换。
2. **Whitney 卡滞图归一化不一致**：interface plan §2.2 写 (F_x/F_z, **M/(r·F_z)**)，
   contact plan §3.1 写 (F_x/F_z, **M/(d·F_z)**)——力矩轴差 2×，平行四边形边界与
   g_jam 符号裕度将系统性错一倍。**修改**：对照 L11 原文定一种，另一处改正并加引文页码。
3. **contact plan 单方面预定了 RF-3 语义**：§3.1 c=(D−d)/d=0.1/4=0.025 与 M11 穿透帽
   0.2×clearance=0.02 mm 都默认 clearance=直径差，而 ASM-00 仍把 RF-3 当未决项且
   实验矩阵专设两口径敏感性行。**修改**：contact plan 卡滞判据与穿透帽全部参数化为
   c_r（半径间隙），标注"取值待 RF-3 定案"，并引用 ASM-00 的两口径敏感性行。
4. **D_eff≈s 代换缺配套间隙缩放**：把双销等效为"大销"直径 D_eff≈s 后，若仍用单销
   间隙比 c=0.025，楔紧条件 l/D_eff<μ 变成 l<0.3s——插入全程（12 mm）都会被误判
   楔紧风险区（s 量级几十 mm）。等效大销的间隙比应为 c_eff≈c_abs/s（绝对间隙不变、
   直径放大）。red_team_questions 已自问"小 s 失效"，但方向反了：**大 s 下不缩放间隙
   同样失效**。**修改**：§3.2 显式给出 (D_eff≈s, c_eff≈c_abs/s) 成对代换公式。
5. **SSOT 缺字段与 RF-1 同类但未登记**：销距 s（§2.3 yaw 容限 c_r/(s/2) 与 §3.2 D_eff
   都依赖）、销倒角宽 w_ch（T1→T2 交接不等式 δr_exit ≤ w_ch + c_r 依赖）在
   `interface_ssot_draft.yaml` 中**均无字段**，AG0 也无对应断言——r_t/r_m 有 RF-1 机器化
   待遇，s/w_ch 没有。**修改**：SSOT 补 `pin_spacing_mm`、`pin_chamfer_mm` 字段
   （PROVISIONAL），AG0-C 增完备性断言 C6"公差链推导所需几何字段无缺失"。
6. **状态机缺销倒角穿越态**：注册态只有 CONE_SLIDE→PIN1_ONE_POINT→TWO_POINT→SEATED，
   而交接不等式明确存在销倒角穿越段。AG4-3 零容忍下：要么每 run 在倒角段落入未注册态
   → 全体 UNKNOWN（fail-closed 卡死），要么实现者把倒角接触悄悄归入 PIN1_ONE_POINT
   （未审查的语义走私）。**修改**：注册 `PIN_CHAMFER_CROSS` 态，或 SSOT 显式声明销无
   倒角并把交接不等式收紧为 δr_exit ≤ c_r。

## ⑤ QP 权重预注册 + 四基线共用防作弊 — **NEEDS_FIX**

骨架健全（共用权重、哈希锁、禁按场景调参、敏感性只进附录），但留有三个未封面：

1. **预冻结泄漏**：CTRL-01 有 `gains_tuned_on_plant=false` 机器旗标；ASM-02 只有散文。
   在权重冻结**之前**对冻结场景集做探索性试跑并据此选权重，现行文本不禁止。
   **修改**：`asm02_qp_v0.yaml` 增 `weights_tuned_on_scenarios: false` 声明字段 + 权重
   来源规则（如量纲归一化推导式）入卡；冻结前禁跑 S1–S4 正式场景（试跑用独立冒烟场景）。
2. **参考轨迹是最大的未冻结自由度**：权重锁了，但 AC0 的"单一参考轨迹"与分阶段基线的
   P0–P4 参考（路点、时序、速度剖面）的生成规则不在冻结清单里。构造一条不利的 AC0
   参考即可制造 PA-1。**修改**：预注册"公平构造规则"——AC0 参考与分阶段基线共享同一
   路点集、同一总时长、同一末端速度上限，生成参数入哈希锁；PA-1 的裁决以此为前提。
3. **阻抗参数的敏感性缺位**：PA-2（AC2 优于 AC1）整个由 (K_d, D_d, F_n_ref) 决定，
   §3 冻结了它们，但敏感性扫掠句只写"权重敏感性"。**修改**：附录扫掠范围显式含
   K_d/D_d/F_n_ref；另把切换阈值 (v_touch, d_lock, v_lock, N_db, T_blend) 声明为
   AC1–AC3 共用同一冻结卡（现文本可推断但未明说）。

## ⑥ AG1–AG4 可绕过组合 — **NEEDS_FIX**

- **B-1（最重，即 ③ 的 Gate 面）**：AG3-b(6/8 合取) × AG4-5（在 ASM-01 另一份裁决文件
  里）× 集成只查各模块 verdict——成功语义洗白路径。修法见 ③。
- **B-2 稀疏记录绕过 AG1-a**："每个记录节点"未定义节点间距；把日志抽稀即可让 5D
  rank/nullity 违例落在节点间。**修改**：节点间距 = T_s 且写入哈希锁矩阵（CTRL-01 的
  0.01 s 全节点纪律同款）；AG1-a 增"记录覆盖率 = 100% 控制周期"子断言。
- **B-3 AG3-a 等号 + n=4 的空洞通过**：四场景分辨率 25%，AC1==AC0（如同全成/全败）
  即通过。**修改**：裁决 JSON 强制携带逐场景成败表与 n=4 限定句；claim 措辞禁用
  "更低失败率"裸表述，必须带样本量。
- **B-4 S3 目标残速在接触模型认证域外**：ASM-02 S3 给目标 1.3872°/s 残速，但 ASM-01
  E0–E5 因子矩阵不含目标角速率，AG4-3 的域检查只覆盖 k_n/c_n/μ 凸包与 r_defl——S3 的
  接触预测将在未认证激励域内运行**而不触发 UNKNOWN**。**修改**：ASM-01 实验矩阵增目标
  残速因子（0 与 sim_10 门内量级两档），或 AG4-3 域字段增 `target_rate_dps` 并把域外
  判 UNKNOWN。
- **B-5 AC3 无失败率断言**：AG3-a 只约束 AC1/AC2 vs AC0；AC3 更差也不 FAIL 任何门，
  headline 却可宣传"协调增量"。PA-3 是预测不是门。**修改**：AG3-a 增
  `control_failure_rate(AC3) ≤ control_failure_rate(AC2)` 或 claim_forbidden 增
  "AC3 增量表述须附与 AC2 的逐场景对比行"。
- **B-6（低危，登记即可）**：R12-4 对 AC0–AC2 空真（无轮通道）；AG2-6 的 L0↔L1 总冲量
  1% 一致仅在 k_n→∞+首触瞬时化回归情形适定，AG4-1 把 1% 推广到含摩擦长时程插接的
  一般情形很可能诚实 FAIL（L0 无切向摩擦冲量通道）——按负结果保留纪律处理即可，但
  预注册时应把 AG4-1 的 1% 限定在"动量级量 + 短接触极限"，避免阈值现实性争议。

---

## Reviewer concerns

1. ③ 的成功语义分叉是本轮唯一 FATAL 级问题：两份计划 + 注册表三处文本对 "success"
   的定义不闭合，且现行文字恰好允许在 SCREENING_ONLY 世界里产出成功率 headline。
2. §2.5 公差链左端（接近段臂端误差）无任何证据源；CTRL-01 的 0.19 m 违例与 5 mm 捕获
   域相差 38×，"锥面吸收"目前是设计意图不是证据。
3. 两计划的 Whitney 公式族存在两处因子 2 不一致（两点接触角、卡滞图力矩归一化），
   叠加 RF-3 未决语义，实现期极易把保守/激进方向搞反。
4. ASM-01 v0 关节抱闸 + 开环进给认证的接触模型，将被 ASM-02 闭环伺服插接消费——激励
   类型不在 AG4-3 域检查内，建议增加"ASM-02 轨迹回放入 ASM-01 模型"交叉验证例。
5. 会话/审批流风险：gate_registry.yaml AG3 行若不与 ③ 修正同步，注册表本身会成为
   错误口径的"真值"。

## Required evidence（批准 Wave A 前须补齐）

- 修订后的 AG3-b/gate_registry AG3 行（八判据单源求值）+ `control_failure_rate` 定义。
- SSOT 补 `throat_r_mm/mouth_r_mm`（已列）、`pin_spacing_mm`、`pin_chamfer_mm` 字段
  及 AG0-C6 完备性断言。
- 统一后的两点接触角/卡滞图归一化公式（含 L11 页码引用）单源文档。
- P1 代表性接近轨迹的冻结增益跟踪界测量预注册（§2.5 链左端证据源）。
- R12-2 键路径全名 + 扫描规则可执行化；R12-3 重评口径（(a) 事后饱和、同网格）预注册。
- AC0 公平参考构造规则 + `weights_tuned_on_scenarios` 旗标入 `asm02_qp_v0.yaml` 草案。

## Allowed claims（现阶段）

- "三面红旗已登记并机器化为 AG0-C1/C2/C3，SSOT v0→v1 转正被 fail-closed 阻塞中"。
- "W1-R12 采用唯一保守档 0.01 N·m/轴（PROVISIONAL，源
  `attitude_stab_v0.yaml stage_b.actuator_dynamics.wheel_max_torque_Nm`），重评不改冻结
  CTRL-02 工件，风险保持 OPEN 至硬件冻结"。
- "CTRL-01 七项负结果（冻结增益与预注册轨迹下）是装配相位分解的设计约束依据"。
- "Phase A 裁决上限 ASM01_SCREENING_ONLY；目标星侧柔性响应在 Phase B 前恒 UNKNOWN"。

## Forbidden claims

- 任何在 Phase A 世界（目标刚体）内的"装配成功/成功率/失败率更低"表述（③ 修正落地前，
  连 control_failure_rate 口径也不得发布）。
- "锥面捕获域可吸收跟踪误差"作为已成立事实（AG0-C1 PASS + P1 跟踪界证据前）。
- "5 mm/5° 粗公差 = 捕获域"（公差箱 ≠ C_T1 曲线；S2 角点未证在域内）。
- 0.033 N·m 作为任何层级的参数或需求档；A2"峰值为零"外推到有力矩限硬件。
- 卡滞/楔紧数值裕度引用（两处因子 2 不一致 + RF-3 未决期间）。
- "接口参数已验证/已实测"；L2/ANCF"已认证"（e15 REPEAT 未闭环）；固定基座≡微重力。
