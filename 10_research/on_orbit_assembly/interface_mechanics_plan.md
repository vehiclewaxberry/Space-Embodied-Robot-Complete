# 装配接口力学研究计划 — ASM-00 接口 SSOT 转正（v0 → v1）

日期 2026-07-20 ｜ 前置：`state_truth_and_scope.md`（Gate AG-A0 = PASS）｜
对象：`10_research/on_orbit_assembly/interface_ssot_draft.yaml`（v0，全字段 PROVISIONAL/LITERATURE）
纪律：本计划为**只读研究规划**，不改任何冻结 sim；sim_11 基建只读 import；
科学边界声明（state_truth §科学边界）全文继承。

---

## 0. 范围与转正定义

- **v0 → v1 转正判据**：`interface.*` 与 `module.*` 全部数值叶字段达到
  "LITERATURE 且携带可查引文键" 或 "MEASURED 且携带证据路径"；Gate AG0（§4）
  五组机器断言全过；UNKNOWN 永不转正（SAFE-00 fail-closed 纪律沿用）。
- **v1 → v2（MEASURED）**：挂硬件链 H0/H1（`10_research/integration/system_interface_plan.md`
  §4：H1 = 预存轨迹回放 + 运动学表征，T_c 实测为 H0/H1 科学交付物），非本卡范围，
  但实测方案（M1–M5）在本卡预注册。
- 接口级阻塞候选（继承）：W1-R12 轮力矩 0.033 > 0.01 PROVISIONAL 冲突必须在
  ASM-02 显式解决；本卡不解决、只传递。

---

## 1. 逐字段出处升级路径

### 1.1 升级规则（出处等级 MEASURED > LITERATURE > PROVISIONAL）

1. LITERATURE 升级 = 把 v0 的"类比"改为**可查引文键**（§1.3 L1–L10），数值若与
   引文不符则改数值并记录 delta；引文键写入 YAML note，AG0-P2 机器校验。
2. PROVISIONAL 升级 = 优先找文献（转 LITERATURE），找不到则预注册实测方案
   （§1.4 M1–M5，挂 B601/H1），实测前保持 PROVISIONAL 并保留扫掠区间。
3. 任何字段升级触发 `rerun_triggers` 对应重跑（YAML 已列四项，本卡新增
   "锥面几何字段补齐"触发 AG0-C 重跑）。

### 1.2 字段表

| 字段 | v0 值/状态 | 目标 | 升级路径（引文候选 / 实测方案） | 重跑触发 |
|---|---|---|---|---|
| module.mass_kg | 1.33, LITERATURE | LITERATURE(引文键) | **L1** CDS：Rev13 1U 上限 1.33 kg；Rev14.1 已放宽至 2.0 kg——须决策取哪版并记录 | 模块选型冻结 |
| module.inertia | derive_from_uniform_box, PROVISIONAL | DERIVED(公式+来源质量) | 公式化：1U 立方 a=0.1 m，I=(m/6)a²；2U 长方体 I=(m/12)diag(b²+c², a²+c², a²+b²)；派生字段标 DERIVED_FROM(mass_kg) | mass_kg 变更 |
| module.grasp_frame / mating_frame | PROVISIONAL | GEOMETRY_FROZEN | 与 `20_engineering/config/geometry/frame_tree_v1.yaml` 同款语义字符串（右手系断言 AG0-F）；待模块 CAD 后由 CAD JSON 单源化（决策 D-6 同款） | 模块 CAD 到货 |
| interface.guide_cone (α=15°, d=8mm) | LITERATURE(类比) | LITERATURE(引文键)+补字段 | **L3** SIROM、**L4** HOTDOCK、**L2** iBOSS iSSI 导向几何；**缺口：无锥口/锥喉半径字段，捕获域不可计算（RF-1，§2.2）**——补 `throat_r_mm`/`mouth_r_mm` | 字段补齐→AG0-C |
| interface.pin_hole (d4, c0.1, n2) | LITERATURE | LITERATURE(引文键)+语义澄清 | **L3/L4** 标准接口销孔；**须澄清 clearance 是直径差还是半径差**（影响 §2.3 θ_max 一倍） | 语义定案 |
| insertion_depth_mm=12 | PROVISIONAL | LITERATURE 或 DESIGN | 与销导入长度 l 绑定（§2.3 θ_max≈c/l 直接用 l）；候选 L3/L4 插入行程数据 | 公差链推导 T2 |
| translational/angular_tolerance (粗5mm/5°, 精0.1mm/0.5°) | LITERATURE | LITERATURE(引文键)+自洽 | 粗档上界对标 **L5** IDSS IDD soft-capture 初始接触条件、**L6** SSRMS LEE/抓捕夹具捕获包络（大尺度，只作上界类比须降尺声明）；精档由 §2.3 解析式反推，不允许独立于几何自由标定 | §2 推导定案 |
| contact_stiffness 1e5 N/m | PROVISIONAL(扫掠1e4–1e6) | LITERATURE→MEASURED | 方法学引文 **L8** Gilardi & Sharf 2002、**L9** Hunt–Crossley 1975 / Flores 2011（KV 参数辨识方法）；实测 **M2** | M2 到货 |
| damping 2e2 N·s/m | PROVISIONAL | 同上 | 与 k_n 绑定为临界阻尼比口径（ζ 扫掠），引文同 L8/L9；实测 **M2** | M2 到货 |
| friction_coulomb 0.3 | LITERATURE | LITERATURE(引文键) | **L10** ESTL 空间摩擦学手册（材料对未定：铝-铝阳极化/不锈钢销，须先定材料对再引数）；实测 **M3** | 材料对定案 |
| latch_force_N 20 | PROVISIONAL | LITERATURE→MEASURED | **L2** iSSI / **L4** HOTDOCK 锁紧预载数据表；实测 **M5**（B601 夹爪闭合力作类比下界） | M5 |
| latch/power/data_state 枚举 | 状态机语义 | FROZEN | 无数值，仅 AG0 检查枚举完备 + "UNKNOWN 不判 success" | — |
| target.interface_mount_frame | PROVISIONAL | GEOMETRY_FROZEN | 并入 frame_tree（B_int 占位帧正好空缺，`frame_tree_v1.yaml:25`）；与 C_sat 抓点不冲突断言 | frame_tree 修订 |
| assembly_success_criteria 八项 | 判据 | FROZEN | 数值项（0.1mm/0.5°）与精公差字段同源引用，禁止两套数字（D-2 同款） | 公差定案 |

### 1.3 LITERATURE 引文候选清单（可查线索，ASM-00 执行时逐条核实后才写入 YAML）

- **L1** CubeSat Design Specification (CDS), Cal Poly SLO；Rev13（1U ≤1.33 kg）与
  Rev14.1（≤2.0 kg）差异须显式决策。
- **L2** iBOSS / iSSI（intelligent Space System Interface）：Kortmann et al.,
  "Building Block-Based 'iBOSS' Approach…", IAC-15 (2015)；iBOSS GmbH iSSI 数据手册
  （机/电/数/热四合一，锁紧力与导向几何）。
- **L3** SIROM（EU H2020 SRC OG5）：Vinals et al., IAC/ASTRA 论文（2018–2020），
  标准机器人接口锥销导向与对接公差实测。
- **L4** HOTDOCK（Space Applications Services / MOSAR）：Letier et al.,
  "HOTDOCK: Design and Validation of a New Generation Standard Robotic Interface…",
  IAC-20 (2020)。
- **L5** IDSS IDD（International Docking System Standard, Interface Definition
  Document, Rev E, NASA 公开）：soft capture 初始接触横向/角容差——仅作大尺度上界。
- **L6** SSRMS LEE 与抓捕夹具（FRGF/PVGF）：Rembala & Ower, Acta Astronautica (2009)；
  NASA SSP 42004 抓捕夹具 ICD——snare 捕获包络类比，须降尺声明。
- **L7** CBM（Common Berthing Mechanism）对准导板与捕获闩：AIAA/SAE 会议文献
  （ISS berthing mechanisms 综述）——粗对准导板几何类比。
- **L8** Gilardi & Sharf, "Literature survey of contact dynamics modelling",
  Mech. Mach. Theory (2002)——KV/k_n,c_n 取值方法学。
- **L9** Hunt & Crossley, ASME J. Appl. Mech. (1975)；Flores et al. 连续接触力模型
  综述 (2011)——非线性阻尼与恢复系数标定。
- **L10** ESTL Space Tribology Handbook（ESA）——真空/大气干摩擦系数按材料对查表。
- **L11**（公差链方法）Whitney, "Quasi-Static Assembly of Compliantly Supported
  Rigid Parts", ASME J. Dyn. Syst. Meas. Control 104(1) (1982)——peg-in-hole
  卡阻/楔紧图、倒角穿越条件；RCC 背景 Whitney & Nevins (1979)。
- **L12**（双销过定位）Sathirakul & Sturges, "Jamming conditions for multiple
  peg-in-hole assemblies", Robotica (1998)。
- **L13** RAFTI（Orbit Fab, Rapidly Attachable Fluid Transfer Interface）公开
  ICD/白皮书——锥面软捕获公差（流体接口，仅几何类比）。

### 1.4 实测方案预注册（挂 B601 / 硬件链 H0/H1，全部为 v2 内容、v1 不阻塞）

- **M1 夹爪闭合时间 T_c**：即待办 2（H0/H1 交付物），回填
  `scene_A2_capture.yaml` 与本 SSOT `latch` 时序；触发带宽 Gate 重跑。
- **M2 接触刚度/阻尼 k_n, c_n**：接口样件（3D 打印锥座 + 金属销）固定台架，
  B601 末端 + 测力传感准静态压入（k_n 割线）+ 敲击/跌落瞬态（对数衰减辨识 c_n）；
  区间必须落在已扫掠 1e4–1e6 内，否则 ASM-01 扫掠区间扩展重跑。
- **M3 摩擦系数**：销/孔样件斜面滑移或拉拔试验，材料对与表面处理同飞行意图。
- **M4 公差链几何**：样件三坐标/塞规实测 α、d、c；随后固定基座 B601 重复插入
  试验（H1 预存轨迹回放）绘制实测捕获域，与 §2 解析域对拍。
- **M5 锁紧力**：锁扣样件 + 拉力计/测力计，闭合力-行程曲线。

---

## 2. 锥面—销—锁扣三级公差链分析方法（解析几何推导任务）

### 2.1 建模约定

帧与符号：模块 mating_frame 为 {M̂}，目标安装口 interface_mount_frame 为 {P}；
横向偏差 δr = ‖p_M̂ − p_P‖⊥（垂直插入轴），角偏差 δθ = 轴夹角；锥半角 α、锥深 d_c、
锥喉半径 r_t、锥口半径 r_m = r_t + d_c·tanα；销径 d_p、（待澄清口径的）间隙 c、
销导入长度 l；摩擦角 φ = arctan μ。工具链：sympy 符号推导 + numpy 采样碰撞几何
交叉验证（两条独立路径，不共享公式实现——对拍纪律同 sim_10 X1）。

### 2.2 T1 锥面粗对准捕获域推导任务

**任务**：推导捕获域 C(α, d_c, r_t, r_m; δr, δθ) 的闭式边界，输出
δr_max(δθ) 曲线族。要点：

1. 纯横向：δr_max ≈ r_m − r_probe(δθ)，其中探入体有效半径含角偏差投影损失
   ~L_probe·sin δθ（L_probe = 模块凸出结构长度）。
2. 聚拢能力：锥面从口到喉的径向收拢量 Δr_funnel = d_c·tanα。
   **RF-1（先验红旗，机器断言 AG0-C1 的动机）**：v0 参数 d_c=8 mm、α=15° 给出
   Δr_funnel ≈ 2.14 mm，而声明的粗横向公差为 5.0 mm，且精档需 0.1 mm——
   若锥口半径不显著大于销倒角捕获半径，则 5 mm→0.1 mm 的收敛在几何上不闭合。
   预期结论三选一：加深锥（d_c≈19 mm@15°）、加大半角（α≈32°@8 mm）、或显式
   声明 r_m 承担剩余 2.9 mm。**v0 缺 r_t/r_m 字段，本项推导被阻塞——字段补齐为
   T1 前置。**
3. 卡阻/楔紧（Whitney L11）：单点接触滑移条件 tan α > μ（α=15°, μ=0.3=tan16.7°
   ——**边界情形，第二个先验红旗 RF-2**：名义参数下锥面滑移不保证，须在
   (α, μ) 平面画出楔紧图并给出裕度要求）；两点接触卡阻图按 L11 的
   (F_x/F_z, M/(r·F_z)) 平行四边形判据复现。

### 2.3 T2 双销精对准推导任务

1. 单销倾角容限：θ_max ≈ c_r/l（c_r=半径间隙）。若 c=0.1 mm 为**直径**间隙、
   l=12 mm，则 θ_max ≈ 0.05/12 = 0.24°<声明精角公差 0.5°；若为半径间隙则
   0.48°≈0.5° 仍是边界。**RF-3：间隙语义未定导致精角公差可能不自洽**——
   T2 输出 θ_max 闭式并由 AG0-C2 断言 fine_ang ≤ θ_max。
2. 双销过定位（L12）：销距 s 与两孔位置度 e_pos 折减有效间隙
   c_eff = c − f(e_pos, s)；推导双销同时导入的 (δr, δθ, δφ_yaw) 联合容许域，
   yaw 容限 ≈ c_r/(s/2)。
3. 倒角穿越：销倒角宽 w_ch 与锥喉交接：T1 出口残差 δr_exit ≤ w_ch + c_r
   为 T1→T2 交接不等式。
4. 插入力/卡阻：Whitney 准静态插入力模型给 F_insert(δθ, μ, 接触深度)，
   上限与 KV 参数、CTRL-01 负结果（LOCK 段才允许 6D）共同决定
   COMPLIANT_INSERT 的顺应策略需求——输出给 ASM-01/02，不在本卡闭环。

### 2.4 T3 锁扣接合窗

锁扣接合的残余失准窗（位置/角度）≥ T2 完成态残差；锁紧力 20 N（PROVISIONAL）
对界面预载的力封闭校核：预载矩 ≥ 帆板振铃反力矩包络（sim_11 A2 量级，
帆板参数占位限定必须携带）。输出 latch_state 状态机的物理触发条件表。

### 2.5 公差链合成与交叉验证

总链不等式（fail-closed 方向）：

```
臂端定位误差 ⊕ 基座漂移(接近窗内) ⊕ 估计误差 ≤ C_T1(粗捕获域)
C_T1 出口残差 ≤ C_T2 入口容许域；C_T2 出口残差 ≤ C_T3 锁扣窗
```

⊕ 用保守区间和（不假设统计独立；RSS 仅作参考列）。验证：解析边界 vs
独立采样碰撞几何 Monte Carlo（≥1e4 位姿采样，穿透判定为纯几何布尔），
边界分类一致率为机器断言（AG0-C4，阈值预注册后冻结）。

---

## 3. 模块质量/惯量接入 sim_11 组合体动力学

### 3.1 装载纪律

复用 `30_simulation/sim_11_coupled_dynamics/src/config_loader.py` 模式：新增
`load_interface_config()` 只读装载本 SSOT，零硬编码，代码中不出现任何手抄
接口数字；`interface_ssot_draft.yaml` 进入 ssot_refs 级联，哈希锁入 Gate。

### 3.2 附着拓扑与质量归属事件（attach_target 语义复用）

`CoupledDynamics.attach_target(m_t, I_t_S, c_t_S, th)`（`coupled_dynamics.py:132`，
把刚体按当前 FK 与 link6 固连）与 `detach_target()` 原语**直接复用，不改核**：

| 技能阶段 | 模块质量归属 | 实现 |
|---|---|---|
| OBSERVE→GRASP_MODULE 前 | 不在链上 | 无 |
| GRASP_MODULE 后（含 MOVE/APPROACH/ALIGN） | 服务星组合体 | `attach_target(m_mod, I_mod_S, c_mod_S, th)`——模块即"目标刚体"，c_mod_S 由 grasp_frame 偏置经 FK 得到 |
| COMPLIANT_INSERT 接触窗 | 仍在臂端，受界面接触力旋量 | 外力注入复用 contact_window 的 `Q_ext = Φᵀ w_S` 通道；力旋量由 KV(k_n,c_n)+库仑摩擦按 §2 接触几何计算（连续接触，非半正弦等冲量——但守恒/能量审计结构照搬 contact_window：组合动量机器精度、能量定理含 E_damp） |
| LOCK_6D 判 LOCKED | **质量转移事件**：`detach_target()` + 模块并入目标星刚体侧 | 目标星侧（contact_window 中的惯性系 Newton-Euler 刚体，或 ASM-01 的双柔性体扩展）质量/惯量/质心按平行轴合成；事件前后组合动量守恒为机器断言（动量账本方法学沿用） |
| VERIFY/RETREAT | 目标星组合体 | 服务星回到无载构型，退化校验 §3.4 |

### 3.3 1U/2U 两档参数卡

`20_engineering/config/assembly_scene/module_1U.yaml` / `module_2U.yaml`（ASM-01 新建，本卡仅定
schema）：mass_kg（1U=1.33 LITERATURE-L1；2U=2.66 同源推定，标 DERIVED）、
inertia 由 §1.2 公式派生（DERIVED_FROM 标注）、grasp/mating 帧、外包络
（1U 100 mm 立方 / 2U 100×100×227 mm，以 CDS 为源）。两档共用同一接口段
（锥销锁扣不随档变），差异仅质量/惯量/包络——保证 ASM-01 扫掠时接口参数不动。

### 3.4 退化链与守恒审计（CLAUDE.md 约定的装配版）

1. m_mod → 0：装配全程退化为 sim_11 A1 式空载臂运动（逐位对拍）；
2. 锁定后组合体全刚化：退化 sim_05 式动量守恒传播；
3. 接触窗 T→0 且等冲量归一：回归 contact_window 瞬时 Delassus 解
   （既有 tests 断言口径复用）；
4. 全程组合动量守恒 ≤ 机器精度（对标 sim_11 的 2.7e-14 量级）、
   能量审计含 E_damp（对标 8.5e-11 量级）——阈值按新场景预注册后冻结。

---

## 4. Gate AG0 机器断言清单（可执行，fail-closed）

实现为 `run_gate_ag0.py`（ASM-00 owned 路径内），输出
`asm_00_gate_check.json`；任一子项 FAIL/UNKNOWN → SSOT 不转正。

**AG0-U 单位组**
- U1 YAML 树遍历：所有数值叶键名带单位后缀（_mm/_deg/_kg/_N/_N_per_m/_N_s_per_m/
  _dps），值可解析为有限 float；无裸数值字段。
- U2 量纲区间：mass>0；k_n ∈ [1e4,1e6] 扫掠区间内；ζ(c_n,k_n,m_mod) ∈ (0,1]
  记录口径；insertion_depth ≥ guide_cone.depth；clearance < pin_d；
  fine ≤ coarse（平移与角度各自成立）。

**AG0-F 右手系组**
- F1 grasp_frame/mating_frame 语义 → R：‖RᵀR−I‖∞ < 1e-12 且 det(R)−1 < 1e-12
  （解析器复用 config_loader.parse_axis_token 模式）。
- F2 反向共轴：ẑ_mating = −ẑ_grasp，逐位 < 1e-12。
- F3 interface_mount_frame 可在 frame_tree 语义下解析（建议并入 B_int 占位帧），
  且与 target_models_v1 的 C_sat 抓点帧不重叠冲突。

**AG0-P 出处组**
- P1 每个数值叶字段携带 source ∈ {MEASURED, LITERATURE, PROVISIONAL, DERIVED}；
  缺失 → FAIL。
- P2 LITERATURE 必须携带引文键（L1–L13 对照表内且已核实）；MEASURED 必须携带
  证据路径+日期+设备；DERIVED 必须携带 DERIVED_FROM 指针；违者 fail-closed。
- P3 转正覆盖率：v1 要求 interface.* 公差/几何/摩擦字段 LITERATURE 以上 100%，
  刚度/阻尼/锁紧力允许 PROVISIONAL 但必须挂 M2/M5 预注册编号。

**AG0-C 碰撞几何一致性组**
- C1 锥面聚拢闭合：d_c·tanα + (r_m 相关项) ≥ coarse_trans − T2 入口容许——
  **v0 缺 r_t/r_m 字段，本项当前必然 UNKNOWN → 阻塞转正（RF-1 的机器化）**。
- C2 销孔自洽：θ_max(c_r, l) ≥ fine_ang（间隙语义定案后；RF-3 的机器化）。
- C3 楔紧裕度：tanα ≥ k_margin·μ（k_margin 预注册，RF-2 的机器化）。
- C4 解析捕获域 vs 独立 Monte Carlo 碰撞采样边界分类一致率 ≥ 预注册阈值。
- C5 CAD/URDF 到货后：SSOT 数值与碰撞网格逐项一致（α、d_c、d_p、模块包络）；
  到货前该项记 UNKNOWN 并在裁决 JSON 中显式列为未闭合项（不冒充 PASS）。

**AG0-H 哈希与装载纪律组**
- H1 SSOT 文件 SHA-256 写入裁决 JSON；消费端 grep 扫描证明零硬编码
  （复用 sim_11 test_config_ssot 模式）。
- H2 success_criteria 数值与公差字段同源引用断言（禁止两套数字，D-2 纪律）。

---

## 5. Task Card

# Task Card ASM-00 — 装配接口 SSOT 转正（力学出处 + 公差链 + Gate AG0）

- **task_id**: ASM-00
- **scientific_question**: 锥面-双销-锁扣三级接口在何种 (α, d_c, r_m, c, l) 参数下，
  粗对准公差 (5 mm, 5°) → 精对准 (0.1 mm, 0.5°) 的收敛链在几何与摩擦学上闭合？
- **hypothesis**: v0 名义参数不闭合（RF-1 聚拢缺口 ~2.9 mm、RF-2 楔紧边界、
  RF-3 销孔角容限边界），存在文献支持的参数修正使 AG0-C 全过。
- **baseline**: v0 草案参数 + Whitney 准静态装配理论（L11）为可解释基线；
  禁止引入"学习式对准"作基线。
- **owned_paths**: 10_research/on_orbit_assembly/（本计划、SSOT 草案、
  run_gate_ag0.py、asm_00_gate_check.json、推导笔记）
- **forbidden_paths**: sim_01–12 冻结区（只读 import）、20_engineering/config/geometry/ 既有
  v1 文件（frame_tree 增补 B_int 须走单独修订流程）、SAFE-00/CTRL-01/02 全部。
- **input_evidence**: interface_ssot_draft.yaml v0、frame_tree_v1/
  target_models_v1/capture_interface_v1、contact_window.py 审计结构、
  CTRL-01 负结果（分阶段语义依据）、W1-R12 冲突登记。
- **minimal_implementation**: ①L1–L13 逐条核实并回填引文键（§1.2 表）；
  ②T1–T3 sympy 推导 + numpy 采样对拍（§2）；③补 r_t/r_m 字段与间隙语义定案；
  ④load_interface_config + run_gate_ag0.py（§4 全部断言）；⑤M1–M5 实测方案
  预注册文档化。不写任何动力学仿真（那是 ASM-01）。
- **experiment_matrix**: {T1 捕获域, T2 双销, T3 锁扣} × {名义 v0, 文献修正案} ×
  {解析, Monte Carlo}；间隙语义 {直径, 半径} 两口径敏感性行。
- **metrics**: δr_max(δθ) 曲线族、Δr_funnel 缺口、θ_max、楔紧裕度、
  解析/采样边界一致率、引文覆盖率、AG0 子项通过数。
- **machine_gates**: AG0 五组（U/F/P/C/H，§4 逐项）；C5 在 CAD 到货前
  记 UNKNOWN 且裁决 JSON 显式列示——UNKNOWN 不转正。
- **red_team_questions**: 大尺度对接文献（L5/L6）降尺类比是否被冒用为同尺度证据？
  RSS 与保守区间和的选择是否影响结论方向？Monte Carlo 与解析式是否共享了
  同一几何实现（对拍失效）？clearance 语义定案是否倒果为因迁就 0.5° 声明？
- **stop_condition**: AG0 全过（C5 除外按 UNKNOWN 列示）→ SSOT 升 v1 →
  asm_00_gate_check.json 落盘即停；负结果（参数不闭合）照发，不擅自改公差声明。
- **rollback_plan**: 全部产物在 owned_paths 内，整体删除即回滚；
  interface_ssot_draft.yaml 保留 git 历史，v0→v1 为新增修订非覆盖。
- **claim_unlocked**: "v1 接口参数下三级公差链在准静态几何+库仑摩擦模型内闭合/不闭合"
  （限刚体几何与文献参数域，携带 PROVISIONAL 限定）。
- **claim_forbidden**: 任何"接口已验证/已实测"表述；动态插入成功率；
  柔性影响结论（帆板占位参数限定继承）；在轨/微重力实证表述。

---

## 6. 与后续任务的边界

- **ASM-01**（动力学）：消费本卡 v1 SSOT + §3 接入方案，实现 COMPLIANT_INSERT
  KV 接触与质量转移事件仿真，退化链 §3.4 为其 Gate 前置。
- **ASM-02**（控制）：消费 §2.4 插入力包络与 CTRL-01 分阶段负结果；
  必须显式解决 W1-R12 轮力矩冲突（接口级阻塞候选）。
- 本卡不产生对杨恒待办 1–3 的新依赖；帆板占位限定原样传递。
