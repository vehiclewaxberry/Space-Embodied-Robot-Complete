# ASM-01 装配接触-柔性动力学研究计划（三保真度插接接触）— 2026-07-20

状态：PLAN_ONLY（未实现）。上游前置：Gate AG-A0 = PASS（`state_truth_and_scope.md`）、
接口 SSOT 草案 v0（`interface_ssot_draft.yaml`，全字段 PROVISIONAL/LITERATURE）。
科学结论只认未来的 `30_simulation/asm_01_contact_insert/results/asm_01_gate_check.json`；本文一切数值
示例均标注"示例估算（非裁决）"。

---

## 0. 范围与继承边界

- **场景**（PI 冻结）：12U 服务星 + B601 持 1U 模块，向目标星（22 kg + 双柔性帆板）+X 面
  预制接口插接：锥面粗对准 → 双销精对准 → 锁扣。技能词表中本计划覆盖
  **APPROACH_5D 末段 → ALIGN → COMPLIANT_INSERT → LOCK_6D → VERIFY_ASSEMBLY** 的
  *动力学侧*；控制律与相位切换属 ASM-02，不在本卡。
- **只读复用（不得重做/重命名冒用）**：sim_11 浮动基座 FFR 世界模型与
  `src/contact_window.py` 基建、sim_10 可行域口径、sim_12 策略账本方法学、
  CTRL-02 轮/推力器分账口径、SAFE-00 裁决核语义。
- **CTRL-01 负结果作为设计约束**：严格 6D 零空间为零（LOCK 段允许）、5D 接近段才有
  1 维零空间、冻结增益闭环锚超差 ⇒ 插接必须按**相位切换**建模而非单一 6D 任务；
  ASM-01 v0 在 COMPLIANT_INSERT 窗内**关节抱闸**（与 sim_11 A2 同款 θ̇=0 约束），
  臂伺服插接留给 ASM-02。
- **关键模型缺口（预登记）**：sim_11 的柔性帆板挂在**追踪星**基座；接口 SSOT 要求
  **目标星**带双柔性帆板，而 sim_11 目标是刚体。因此分两相：
  - **Phase A**：目标刚体 + 追踪星侧 FFR。八项成功判据中
    `flexible_response_within_validated_envelope`（目标侧）只能返回 UNKNOWN ⇒
    Phase A 裁决词汇上限为 `ASM01_SCREENING_ONLY`，**禁判装配成功**。
  - **Phase B**：把 `ffr_panel` 挂到目标 Newton-Euler 体（目标成为第二个浮动基座 FFR
    体），走完整八项判据。Phase B 前须过退化链：目标帆板刚化 → 逐位回归 Phase A。

---

## 1. 三保真度对比设计（①）

### 1.1 L0 —— 纯几何插接（运动学 + 冲量）

| 项 | 内容 |
|---|---|
| 物理 | 刚体运动学配合 + 事件式瞬时冲量（Delassus，复用 sim_11 `capture_solver.solve_capture` 与 sim_10 现状口径） |
| 插接建模 | 无接触力过程：位形空间可行性（锥/销/孔的公差漏斗几何布尔判定）+ 首触与锁扣两次瞬时冲量 |
| 输出 | 捕获域地图（初始横偏/倾角 → 可插/不可插）、传递总冲量 λ=[J;L]、基座速率跳变、λ 账本 |
| 盲区（注册制） | 无接触力峰值、无卡滞过程、无能量级量（理想冲量对模态能不适定——sim_11 `ideal_impulse_diagnostic` 已证，直接继承 `model_fidelity_selection_rules.yaml` R2a：L0 禁报 `modal_energy_peak_J`） |
| 成本 | ~1e-3 s/例，承担 Monte Carlo 公差漏斗筛（~1e3–1e4 例） |

### 1.2 L1 —— KV 持续接触 / 有限带宽（主力层）

**接触力模型**（接口 SSOT `contact_stiffness/damping/friction` 字段）：

```
F_n = max(0, k_n·δ + c_n·δ̇)          # KV 单边化：夹逼非负，δ=穿透深度
F_t = -μ·F_n·sat(v_t/v_eps)           # 库仑摩擦正则化（v_eps 待预注册冻结）
```

- KV 病理登记：接触末段 δ→0⁺、δ̇<0 时原式给出**拉力**，必须单边夹逼并把"被夹逼
  时间占比"入 summary（>5% 时升级 L1b Hunt–Crossley `F=k δ^n(1+κ δ̇)` 复核，避免
  分离瞬间力不连续污染恢复系数）。
- 接触几何状态机（**注册制**，未注册态一律 UNKNOWN，见 AG4）：
  `NO_CONTACT → CONE_SLIDE（锥面单点）→ PIN1_ONE_POINT → 跨销/单销 TWO_POINT →
  SEATED（到位面-面）→ LOCKED（锁扣）`。每步重算接触坐标系（法向/切向随几何走）。
- 与 sim_11 的耦合：每个接触点力旋量 w_S 经 `Q_ext = Φᵀ w_S` 注入追踪星 full 模式
  广义力（`contact_window.py` 第 93–95 行同款路径），目标侧受 −w 于同一空间点
  ⇒ 组合动量守恒仍是机器审计量。

**插接（持续接触）≠ 捕获（单脉冲）——必须显式区分的六点**（对 `contact_window.py` 的
复用/改造清单）：

| 维度 | sim_11 捕获单脉冲（现状） | ASM-01 插接持续接触（新建） |
|---|---|---|
| 力来源 | 预设半正弦 `s_pulse(t)`，等冲量前馈，λ 是**输入** | 状态反馈 F(δ,δ̇)，冲量是**输出** ∫F dt |
| 时长 | T_c 固定 5–100 ms | 涌现量：秒级滑insertion + 毫秒级微碰撞链（chatter） |
| 力方向 | 惯性系冻结（窗内转角≪1°） | 接触坐标系逐步重算（锥面滑移法向连续旋转） |
| 事件 | 无 | `solve_ivp` events：触/离/状态机迁移/停滞检测（混杂系统积分） |
| 耗散账本 | 仅模态阻尼 E_damp | 新增 ∫c_n δ̇² dt（接触阻尼）+ ∫μF_n·|v_t| dt（摩擦），三项分列入能量审计 |
| 收口 | 窗末一次 Delassus lockup | 仅当 SEATED ∧ 残余相对速度 < 阈值才允许 LOCK_6D lockup（复用 `solve_capture`） |

**可直接复用的 contact_window 基建**：联立 ODE 状态排布（追踪星 full 模式 + 目标
Newton-Euler）、Φᵀw_S 注入、动量/能量审计代码（`momentum_drift_max` /
`energy_audit_rel` 口径）、lockup Delassus 收口、`--tag` 扫掠 CLI 与
gate JSON + artifacts sha256 模式。

### 1.3 L2 —— 高保真多点接触 / ANCF 抽查

- 多点同时接触（跨销两点 + 锥面残余）不做状态机简化，直接以 LCP/罚函数细网格解；
  帆板用 sim_07 ANCF（8 单元平面梯度缺陷梁，Rayleigh 阻尼）替换 FFR 复核柔性响应。
- **口径继承 e15**：L1/L2 交叉对拍走 5% 门槛，且 e15 的
  `REPEAT_ANCF_CERTIFICATION`（交叉解 5.64% > 5%）未闭环 ⇒ **L2 抽查结论在 GR5
  重过前不得引用为"已认证"**，只能作 L1 的方向性复核（此限制句必须复述进报告）。
- 强制限定：sim_07 为平面梁组件级，非全 3D 板全耦合。
- 成本 ~300 s/例 ⇒ 只做 8 例抽查漏斗（对齐 `model_fidelity_selection_rules.yaml`
  R6 的 L2_cases: 8）。

---

## 2. 指标全集（②）

每项注明求值层与拟用阈值来源；未有出处的阈值标 **PROVISIONAL-待预注册冻结**（Wave1
纪律：阈值冻结后不得放宽，负结果保留）。

| # | 指标 | 定义 | 层 | 阈值/口径出处 |
|---|---|---|---|---|
| M1 | 峰值接触力 | max_t F_n（逐接触对 + 合旋量模） | L1/L2 | `contact_load_within_limit`（SSOT 第 35 行）；限值待接口实测，先 PROVISIONAL |
| M2 | 总传递冲量 | ∫[F;τ]dt = [J;L]，与 L0 λ 对拍 | L0/L1/L2 | GR1 式 `ee_impulse_rel` ≤1%（L0↔L1） |
| M3 | 插接深度 | δ_ins(t) 与终值 vs 12 mm（SSOT） | 全层 | `insertion_depth_reached` 布尔 |
| M4 | 卡滞判据组 | 见 §3：两点接触旗标、Whitney 平行四边形裕度、楔紧 l/d–μ 条件、停滞时长 τ_stall | L1/L2 | 本计划 §3 定义，预注册冻结 |
| M5 | 基座姿态/速率 | base_attitude_peak_deg、base_rate_peak_dps | 全层 | GR1 式 rel ≤1–2%（层间） |
| M6 | 轮组动量/力矩需求 | 离线 CTRL-02 分账口径的等效需求（非闭环）；接触瞬态力矩 vs **W1-R12 轮力矩 0.033>0.01 PROVISIONAL 冲突** | L1 | `base_wheel_within_resources`；W1-R12 为接口级阻塞候选，ASM-02 必须显式解决，本卡只记账不裁决 |
| M7 | 帆板 tip 挠度 | tip_L/R 峰值；r_defl = w_tip/L 对 R3 线性域 0.02/0.05 分档 | L1/L2 | GR1 `tip_defl_peak_rel` ≤5%；R3 阈值 |
| M8 | 模态能 | modal_energy_peak/final、前向加密链 τ_tail | L1/L2 | G4' 1% 判据；GR1 `modal_energy_peak_rel` ≤10% |
| M9 | 接触后残余误差 | LOCK 前位置/姿态误差 vs 0.1 mm / 0.5°（SSOT 八项）、lockup 冲量模与 `lockup_rel_to_lam` | L1/L2 | SSOT `assembly_success_criteria` |
| M10 | 守恒审计 | 组合动量漂移（≤1e-12 reduced 口径 / 窗内 ~1e-14 量级参照 sim_11 G1）、能量审计 rel ≤1e-8、接触耗散 ≥0、夹逼占比 | 全层 | sim_11 G1/G2 现行阈值直接继承 |
| M11 | 数值健康 | 最大穿透 δ_max vs 穿透帽（拟 0.2×clearance=0.02 mm，PROVISIONAL）、chatter 次数、事件收敛旗标、跨解算器差 | L1 | G5 式 Radau↔BDF ≤5% |

---

## 3. 卡滞判据的物理定义（③，双销 Whitney 准则引入）

采用 Whitney 经典准静态圆销-孔两点接触理论（Whitney 1982, *Quasi-Static Assembly of
Compliantly Supported Rigid Parts*, ASME J. DSMC）作为**必要条件层**，叠加动力学
充分条件层；全部写成机器可检断言。

### 3.1 单销经典准则（基元）

记销径 d=4 mm、间隙比 c=(D−d)/d=0.1/4=0.025、摩擦系数 μ（LITERATURE 0.3）、
啮合深度 l：

- **两点接触发生角**（小角近似）：θ_2pt(l) ≈ c·d/l。
- **楔紧（wedging，几何自锁，准静态不可恢复）**：两点接触 ∧ 两接触点摩擦锥在材料内
  相交，等价深径比条件 **l/d < μ**（μ=0.3 ⇒ l < 1.2 mm 为楔紧风险区）∧ 倾角达
  θ_2pt。示例估算（非裁决）：l=1.2 mm 处 θ_2pt≈0.025×4/1.2≈4.8°，远大于精对准
  0.5°（SSOT）⇒ 名义公差链下不应进入楔紧；此裕度必须在 E2 中机器复核而非引用本句。
- **卡滞（jamming，力旋量比例错误，可恢复）**：施加力旋量 (F_x/F_z, M/(d·F_z)) 落在
  Whitney 卡滞平行四边形**之外**——销停止前进但改变力旋量比例即可脱困。机器化：
  逐步求当前两点接触的平行四边形边界，输出带符号裕度 g_jam（<0 = 卡滞态）。

### 3.2 双销扩展（本接口 n_pins=2）

- 双销为平面过约束配合：接触点枚举扩展到 4 个候选缘点，须检测**跨销两点接触**
  （销1 前缘 + 销2 后缘），其等效力偶臂为销间距 s ⇒ 等效"大销"直径 D_eff≈s 代入
  3.1 的平行四边形与楔紧条件（s 由 CAD/SSOT 升级 v1 时补齐，现 PROVISIONAL）。
- 双销楔紧的附加模式：两销同时单点接触但法向相反（对顶）——注册为独立接触态
  `TWO_PIN_OPPOSED`，判据同两点摩擦锥相交。

### 3.3 动力学充分条件（自由漂浮补充）

Whitney 准则是准静态的；双星自由漂浮下补充**停滞判据**：

```
JAMMED_DYN :=  δ̇_ins < v_stall（拟 0.1 mm/s, PROVISIONAL）持续 τ_stall > 0.5 s
            ∧ F_n 单调不减
            ∧ 施加力旋量位于摩擦锥对偶锥内（即"推得再狠也只增加法向压紧"）
```

三条同时成立才判 JAMMED；仅 Whitney 必要条件成立记 `JAM_RISK` 旗标不判死。
卡滞/楔紧判定结果进入 M4，并作为 ASM-02 相位切换（回退 ALIGN / RETREAT）的触发
接口——本卡只输出判据与旗标，不设计脱困控制。

---

## 4. Gate 机器断言（④）

Gate 梯队：AG0（SSOT 出处齐全，已在 `interface_ssot_draft.yaml` 定义）→ AG1（L0 几何
漏斗完成度）→ **AG2（物理有效性）** → AG3（收敛/跨解算器，可并入 AG2 报告）→
**AG4（多保真一致 + fail-closed）** → AG5（八项装配成功判据，仅 Phase B 可裁）。
本卡核心为 AG2/AG4，全部 fail-closed（任何断言不可求值 ⇒ 按 FAIL/UNKNOWN 处置，
沿用 `model_fidelity_selection_rules.yaml` 的 `on_unevaluable` 语义）。

### AG2 —— 动量/能量记账闭合与数值有效性（对 L1 每例强制）

| 断言 | 内容 | 阈值 |
|---|---|---|
| AG2-1 | 组合动量守恒：max_t \|Δ(h_chaser+h_target)\|（接触内力作用反作用同点） | 继承 sim_11 G1 口径（reduced 1e-12；窗内漂移参照 2.7e-14 量级实绩） |
| AG2-2 | 能量定理闭合：\|W_contact − (ΔE_c + ΔT_t + E_damp + E_KV + E_fric)\|_rel | ≤1e-8（G2 口径），接触耗散两项分列且各 ≥ −1e-12 |
| AG2-3 | 单边性：min_t F_n ≥ 0（夹逼后）且夹逼时间占比入账，>5% 触发 L1b 复核 | 硬断言 |
| AG2-4 | 模态前向加密链 m3→m4→m5 在持续接触激励下 τ_tail < 1%（G4' 判据）；若接触等效带 f_c 使 `modal_basis_covers_band=false` 则按 R2b 增模至 m≤7，否则升级 L2 | G4'/R2b |
| AG2-5 | 跨解算器：Radau vs BDF 关键量（M1/M2/M5/M7/M8）相对差 ≤5%（G5 口径） | 5% |
| AG2-6 | 极限回归：k_n→∞（步进 3 档外推禁用，只做已算档单调性）与"首触瞬时化"情形回归 L0 冲量解，M2 相对差 ≤1%；lockup 冲量随 SEATED 残速 →0 | 1% |

### AG4 —— 多保真一致性与 fail-closed 裁决

| 断言 | 内容 | 阈值/语义 |
|---|---|---|
| AG4-1 | L0↔L1 关键量一致：总冲量、基座速率峰、姿态峰 rel 差 | GR1 式 ≤1%/1%/1%（p95 统计入 CSV） |
| AG4-2 | L1↔L2 抽查一致：tip ≤5%、主频 ≤2%、模态能 ≤10%、接触力峰 ≤10%（后者 PROVISIONAL-预注册冻结）；**e15 GR5 未闭环期间 L2 侧结论只作方向性复核**，AG4-2 通过也不得升格为"L2 已认证" | e15/GR1 口径 |
| AG4-3 | **未建模接触态 ⇒ UNKNOWN**：接触状态机遇到未注册态（三点及以上、缘-缘、锥外碰撞、跨销未枚举组合）、k_n/c_n/μ 超出扫掠矩阵凸包、r_defl ≥0.05 线性域外 —— 一律返回 `UNKNOWN_CONTACT_STATE`，**任何数值预测输出即 FAIL**（GR4 语义逐字继承） | 硬门，零容忍 |
| AG4-4 | **未收敛接触禁判装配成功**：solver 失败、δ_max 超穿透帽、chatter 事件链未在窗内终止、AG2-4/2-5 任一不过 ⇒ 该例 `assembly_success = UNKNOWN`（非 fail 亦非 success），且 UNKNOWN 永不计入成功率分子分母以外的任何"可行"统计（SAFE-00 UNKNOWN-永不-ALLOW 的装配版） | 硬门 |
| AG4-5 | 成功判据完备性：判 success 必须八项全布尔真（SSOT `assembly_success_criteria`），Phase A 因目标柔性=UNKNOWN 结构性不可满足 ⇒ Phase A 裁决上限 `ASM01_SCREENING_ONLY` | 硬门 |

裁决词汇：`[ASM01_GATES_PASS, ASM01_GATES_PASS_WITH_PROVISIONAL_PARAMS,
ASM01_GATES_FAIL, ASM01_SCREENING_ONLY]`；例级状态另有 `UNKNOWN_CONTACT_STATE`。
输出 `results/asm_01_gate_check.json`（含 artifacts_sha256，格式对齐 sim_11 gate v3）。

---

## 5. k_n/c_n 扫掠矩阵与传染路径（⑤）

### 5.1 扫掠矩阵（预注册后冻结）

| 因子 | 取值 | 说明 |
|---|---|---|
| k_n [N/m] | {1e4, 3.16e4, **1e5**, 3.16e5, 1e6}（对数 5 档） | SSOT 名义 1e5；范围即 SSOT 注记 1e4–1e6 |
| ζ_c（接触阻尼比） | {0.05, 0.2, **0.5**, 1.0} | c_n = 2ζ_c√(k_n·m_app)；SSOT 名义 c_n=200 N·s/m 反解出的 ζ_c 落点须在报告中标注 |
| μ | {0.1, **0.3**, 0.5} | LITERATURE 0.3 为名义 |
| v_ins [mm/s] | {1, **5**, 10} | 插接进给速度（ASM-02 接口量，此处开环给定） |
| 失准 | 横偏 {0.05, 0.1, 0.5, 1.0} mm × 倾角 {0.1, 0.5, 1, 2}° | 覆盖精对准公差 0.1 mm/0.5° 的 0.5–20 倍 |

漏斗（R6 同款，禁放宽阈值抵预算）：L0 全因子×失准 Monte Carlo ~2e3 例 →
L1 核心 5×4×3 = 60 例（名义失准）+ E2 失准应力 16 例 → L2 抽查 8 例
（k_n 两端 × 最差失准 × 名义，含 ANCF 帆板替换）。

其中 **m_app 定义**：不是天真两体折合质量，而是沿插接轴的 Delassus 表观质量
（由 sim_11 模型 `ee_partial_velocity`/质量阵在接触点投影求得，Phase A 对追踪星侧、
目标侧分别求再串联）。示例估算（非裁决）：若 m_app ∈ [1,10] kg，则接触频率
f_c=(1/2π)√(k_n/m_app)：k_n=1e4 ⇒ 5–16 Hz；1e5 ⇒ 16–50 Hz；1e6 ⇒ 50–160 Hz。

### 5.2 传染路径（k_n/c_n → 基座/柔性响应的因果链，逐条给预期标度与观测量）

```
k_n, c_n, μ
  ├─(P1) 单次碰撞标度：F_peak ≈ v_rel·√(k_n·m_app)（∝√k_n），t_bounce ≈ π√(m_app/k_n)，
  │      恢复系数 e ≈ exp(−πζ_c/√(1−ζ_c²)) → M1、chatter 链长度（M11）
  ├─(P2) 频带传染：f_c 随 √k_n 上移 → 与帆板 f1 包络 0.6–2.2 Hz 及保留模态
  │      f3=17.55 Hz 的相对位置决定注入路径——
  │      k_n=1e6 档 f_c 预计越过 f3 ⇒ R2b 触发增模（m≤7）或 L2 升级；
  │      这是扫掠矩阵与模态收敛 Gate（AG2-4）的耦合主轴 → M7/M8
  ├─(P3) 基座传染：接触力旋量经 Φᵀw_S 注入 → 基座速率/姿态峰（动量级，预期对 k_n
  │      弱敏感、对总冲量强敏感）；但**轮组力矩需求跟随 F_peak 瞬态**（∝√k_n）
  │      → M5/M6，直接对撞 W1-R12 的 0.01 N·m PROVISIONAL 轮力矩上限
  │      ⇒ 高 k_n 档很可能给出"轮组不可行、需推力器分账"的负结果，保留不掩埋
  ├─(P4) 柔性传染：持续滑移接触≈准静态载荷 + 微碰撞链≈宽带激励的叠加；
  │      低 k_n（长接触）偏准静态耦合、高 k_n（短脉冲链）偏 sim_11 捕获式振铃
  │      → tip/模态能/振铃时长（M7/M8），r_defl 分档触发 R3 升级
  ├─(P5) 摩擦-卡滞传染：μ↑ 使 Whitney 平行四边形收窄、楔紧区 l<μd 变深 →
  │      E2 失准应力下 JAM_RISK/JAMMED 发生率地图（M4）
  └─(P6) 残差传染：ζ_c 低 ⇒ chatter 反复冲量注入 ⇒ LOCK 前残余速度与 lockup 冲量↑
         ⇒ 残余位姿误差 vs 0.1 mm/0.5°（M9）
```

每条路径 P1–P6 在报告中各配一张"因子→观测量"曲线族图 + 单调性/标度检验
（对 P1 的 √k_n 标度做拟合指数区间，偏离 ±20% 即记异常入红队清单）。

---

## 6. 实验矩阵

| 编号 | 层 | 内容 | 例数 | 产出 |
|---|---|---|---|---|
| E0 | L0 | 公差漏斗 Monte Carlo（粗对准 5 mm/5° 域内采样）→ 几何可插域地图 + 冲量账本 | ~2e3 | AG1 + AG4-1 的 L0 侧 |
| E1 | L1 | 名义失准下 k_n×ζ_c×v_ins 核心矩阵 | 60 | §5 传染路径全套曲线 |
| E2 | L1 | 失准应力（横偏×倾角 16 组合 × 名义 k_n/μ 与最不利 μ=0.5） | 32 | 卡滞/楔紧发生率地图（M4） |
| E3 | L1 | chatter/恢复系数专项：低 ζ_c × v_ins 扫掠 | 12 | P1/P6 验证 |
| E4 | L2 | 抽查：k_n∈{1e4,1e6} × {名义, 最差失准} × {FFR→ANCF 帆板}，+ 双销对顶楔紧 1 例、多点 LCP 1 例 | 8 | AG4-2 |
| E5 | 回归 | k_n 单调链极限回归 L0（AG2-6）；关节抱闸 + 首触瞬时化退化对拍 sim_11 A2 捕获口径；目标帆板刚化退化（Phase B 入口） | 6 | AG2-6 + Phase B 授权 |

---

## 7. Task Card（ASM-01）

# Task Card ASM-01 — 装配接触-柔性动力学（三保真度插接）

- **task_id**: ASM-01
- **scientific_question**: 在全 PROVISIONAL 接口参数下，1U 模块对预制锥-双销接口的
  持续接触插接动力学，能否在 L0/L1/L2 三保真度下给出层间一致、fail-closed 的
  卡滞判据与装配成功裁决，并量化 k_n/c_n 沿 P1–P6 路径对基座与柔性响应的传染？
- **hypothesis**: (a) KV 单边化 + 接触状态机 + 关节抱闸的 L1 模型可在 G1/G2 现行
  机器精度下闭合动量/能量账本；(b) Whitney 双销扩展判据 + 动力学停滞条件可把
  卡滞/楔紧写成零散文机器断言；(c) k_n=1e6 档将触发 R2b 增模或 L2 升级，且轮组
  力矩需求与 W1-R12 上限冲突将以真实负结果形式显影。
- **baseline**: sim_11 v1.1（`SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS`）的 A2 捕获
  口径与 contact_window 基建；sim_10 fail-closed 四门语义；e15 5% 交叉口径。
- **owned_paths**: `30_simulation/asm_01_contact_insert/`（新建）、`20_engineering/config/assembly_interface/`
  （新建，由 `10_research/on_orbit_assembly/interface_ssot_draft.yaml` 升 v1 落卡）、
  `10_research/on_orbit_assembly/`（本计划与报告）。
- **forbidden_paths**: sim_01–12 全冻结区（只读 import）、`20_engineering/config/coupled_scene/`
  （只读）、SAFE-00/CTRL-01/CTRL-02 产物、`.codex/`。
- **input_evidence**: `sim_11_gate_check.json`（G1–G5 实绩与阈值）、
  `src/contact_window.py`（联立 ODE/审计/lockup 基建）、`scene_A2_capture.yaml`
  contact 段、`interface_ssot_draft.yaml`、`model_fidelity_selection_rules.yaml`
  （R1–R6、GR1–GR5）、CTRL-02 分账口径、W1-R12 登记项、sim_07 ANCF 组件级基准。
- **minimal_implementation**: ①`contact_geometry.py` 锥/双销接触状态机（注册制，
  未注册态抛 UNKNOWN）；②`contact_kv.py` 单边 KV+正则库仑，耗散分列；
  ③`insert_scene.py` 复用 contact_window 的联立 ODE 骨架改为状态反馈力 + events；
  ④`jamming.py` Whitney 平行四边形/楔紧/停滞三层判据；⑤`run_asm_gates.py` 产
  `asm_01_gate_check.json`。全 numpy/scipy，参数零硬编码。
- **experiment_matrix**: §6 E0–E5（L0 ~2e3 / L1 104 / L2 8 / 回归 6）。
- **metrics**: §2 M1–M11 全集（含阈值出处列）。
- **machine_gates**: §4 AG2-1..6、AG4-1..5；裁决词汇四值 + 例级
  `UNKNOWN_CONTACT_STATE`；Phase A 上限 `ASM01_SCREENING_ONLY`。
- **red_team_questions**: KV 夹逼是否把能量审计残差藏进"耗散"？chatter 事件链
  截断是否被当作收敛？双销 D_eff≈s 近似在小 s 下是否失效？m_app 用错（天真折合
  质量 vs Delassus 表观质量）会否让 f_c 判档系统性偏移？UNKNOWN 例是否被下游
  成功率统计悄悄丢弃？L2 未认证（e15 REPEAT）期间 AG4-2 措辞是否越界？
- **stop_condition**: AG2/AG4 全部可求值且 E0–E5 跑毕 → 输出
  `asm_01_gate_check.json`（无论 PASS/FAIL/SCREENING_ONLY）即停；
  负结果（轮组冲突、k_n 高档不收敛、卡滞高发）原样入档不返工掩盖。
- **rollback_plan**: 新建目录整体删除即回滚；不触碰任何既有 Gate 与冻结区。
- **claim_unlocked**: "插接接触的卡滞/成功判据是机器断言而非散文；k_n/c_n 传染
  路径有逐条标度证据"（Paper 1 §方法 候选 + ASM-02 相位切换的物理依据）。
- **claim_forbidden**: "装配已验证成功"（Phase A 结构性禁止）；"L2/ANCF 已认证"
  （e15 GR5 未闭环）；任何超出扫掠凸包的 k_n/c_n 外推；"接口参数已实测"
  （全 PROVISIONAL/LITERATURE）；固定基座地面演示 ≡ 微重力。

---

## 8. 重跑触发器（继承 + 新增）

接口实测公差/刚度/锁紧力到货、B601 夹爪 T_c 实测、杨恒帆板参数卡转正
（0.348 kg 占位 vs 真实 2–5 kg/m² 差 5–10 倍——柔性传染 P4 结论可能翻转，
优先级最高）、轮组选型冻结（W1-R12）→ 均触发 E1–E5 与 AG 全量重跑并递增版本号。
