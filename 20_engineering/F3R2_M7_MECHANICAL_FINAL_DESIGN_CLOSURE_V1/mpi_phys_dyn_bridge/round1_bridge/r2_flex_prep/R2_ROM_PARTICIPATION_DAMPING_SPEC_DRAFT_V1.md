# R2 ROM 参与因子/阻尼/强迫响应输入规格草案 V1（AGENT-3 / round1_bridge / r2_flex_prep）

- schema: `R2_ROM_PARTICIPATION_DAMPING_SPEC_DRAFT_V1`
- 生成时间：2026-08-23T17:21+08:00（宿主机本地钟）
- 状态：**DRAFT_PENDING_AUTHORITY —— 本规格不自我生效、不授权任何计算**。参与因子/阻尼/强迫响应在 e21 ROM 中全为显式 null（E21-G22 PASS：`damping_matrix=null, participation_factors=null, forced_response=null`）；本文件只定义输入槽位与获取路径，所有 null 逐字保持，禁止零填。
- 范围：纯文本。本轮未启动任何 CAD/FEA/仿真进程；未修改 `FLEXIBLE_APPENDAGE_R2.yaml`、`compute_flexible_appendage_r2.py` 或任何上游账本。
- 上游输入：`round0_handover/03_r2_flex_inputs/R2_FLEX_INPUT_INVENTORY_V1.json`（sha256:12 `82ded3493069`）的 GAP-01..12。

## 0. 目标 ROM 与当前缺口

- 目标 ROM（逐字引盘点）：每翼 **3–5 主导模态**（ODR-21 带），**自由漂浮基座耦合**，含阻尼与强迫响应能力。
- 现状 ROM：定基座、每翼 3-DOF 铰转角链（相对角弹簧，平面 (y,z) 运动学，铰轴 ∥ X_S）、leaf-only 动能、无阻尼、无基座耦合、无强迫响应。证据：五工况频率（e21 复现 ≤4.84e-05 Hz，E21-G20）与 Mqq（5.0e-10 kg·m²，E21-G19）。
- 从"leaf-only 特征值复现"到目标 ROM 的全部输入缺口 = 下表 SLOT-01..10。**每一槽位在关闭前保持显式 null；任何槽位的关闭证据必须带出处（WP5 工单 / vendor / 实测 / 文献）。**

## 1. 输入槽位规格表（每槽位：现值 → 状态 → 阻塞对象 → 获取路径 → 消费规则）

| 槽位 | 现值 | 状态 | 阻塞 | 获取路径 | 消费规则（草案） |
|---|---|---|---|---|---|
| SLOT-01 叶 GJ 带 | 卡片 `GJ_Nm2` 无数值（"torsion estimate pending sandwich shear model; band not yet assigned"） | **NULL_EFFECTIVE** | HF 模型扭转模态；ROM 模态集完整性（现模型为纯弯曲平面链，无扭转 DOF） | WP5 R2 硬件选型工单 → 夹层剪切模型估算 + vendor 铺层数据 → 实测扭转刚度 | 进入 HF 模型前必须有带角的 PROVISIONAL_DERIVED 或实测值；不得从 EI 带角缩放捏造 |
| SLOT-02 阻尼模型 | ROM `damping_matrix=null`；卡片 ζ=0.01 `TBD_cite_literature`；旧 sim_11 卡 `zeta_modal=0.005` 同为占位（能量审计 Gate 强制 0） | **NULL_IN_ROM**（卡片占位不得消费） | 一切衰减/振铃预测（sim_07 曾见 37–75 s 振铃，R2 未量化） | 文献引用（夹层结构/铰链链模态阻尼比，须可核查出处）或实测（锤击/自由衰减对数减量法） | 双车道制：守恒审计车道 ζ=0（机器精度账本）与耗散预测车道 ζ≠0 必须分离声明；禁止把占位 0.01/0.005 当权威 |
| SLOT-03 latch 独立刚度 | null（折叠进板间 kθ 带；`latch_compliance.folded_into`） | **NULL** | 展开锁定态刚度权威；latch 反驱校核 | latch 硬件选型（`HOLD_LATCH_GEOMETRY_NOT_MODELLED`）→ vendor 刚度数据或实测 | 到位前保持折叠于板间带（20/100/400 N·m/rad）；到位后须验证反驱条件：480 N 控制端停瞬态 + 带角一阶模态振动下不反驱（机构账本 C_latch 逐字） |
| SLOT-04 根部支架/星体界面柔顺 | null（除根铰弹簧外无界面柔顺模型） | **NULL** | HF 模型根边界真实性 | WP5 R2 update（支架结构设计）→ 后续轮次授权后的 FEA 或实测 | 到位前根铰 kθ 带（50/200/800 N·m/rad）为唯一根柔顺模型；机构账本仅有 48.0 N·m 根部支架反力瞬态候选可作校核载荷参考，不是刚度 |
| SLOT-05 铰链自由间隙 | null（`HOLD_FREEPLAY_LIMITS_NO_NUMERIC_AUTHORITY`） | **NULL** | 非线性微动力学（backlash） | 硬件实测（铰链间隙测量） | 到位前 HF/ROM 均不得含 backlash 项；到位后作分段线性/死区模型，数值须带测量记录 |
| SLOT-06 叶实测构造数据 | 候选：2×0.2 mm CFRP（E=70 GPa 准各向同性）+ 2.1 mm 芯、总厚 2.5 mm、面密度候选 3.0 kg/m² → 叶 0.18 kg、EI 名义 11.109 带 [3.333, 33.327] N·m² | **PROVISIONAL_DERIVED**（`HOLD_PANEL_LAYUP_AND_CELL_GEOMETRY_NOT_MODELLED`） | PROVISIONAL 质量/EI 的替换；AGENTS.md 待办 3（真实 2–5 kg/m² 口径下"A1 柔性反馈可忽略"结论可能翻转，论文最大硬伤，优先级最高） | WP5 R2 硬件选型工单 → vendor 铺层/胞元数据 → 实测面密度与悬臂频率 | 到位前现行点值/带角保持 PROVISIONAL_DERIVED；替换即触发 e15 T2/T4 重认证 |
| SLOT-07 模态参与因子/动量耦合系数 | null（定基座 ROM 无自由漂浮耦合） | **NULL** | ROM-动力学耦合；捕获激励响应；e15 T7 | **计算获取**（非硬件）：扩展动能至基座运动，取交叉块——但见 §2 前置条件 | 计算前置：MC 质量分配裁决落账（`dynamic_mass_allocation_frozen=true`）；禁止在裁决前用 Mqq* 预计算 |
| SLOT-08 强迫响应定义（捕获激励经 R2 柔性） | null（`r2_full_flexible_coupling=NOT_EVALUATED`；e21 明禁 scene A2 类运行） | **NULL** | scene-A2 类场景评估 | 定义见 §4；运行须等 MPI-FB-01..08 全闭合 + owner 放行 | 激励模型沿用接触窗约定（半正弦等冲量，`T_c_ms_nominal=20.0` 占位 PROVISIONAL，扫掠 5–100 ms）；占位值替换 = e15 T5 触发 |
| SLOT-09 标准不确定度约定 | 全柔性参数 `standard_uncertainty=null`；带角 = 工程角点非标准不确定度 | **NULL** | 任何 UQ 陈述 | 文档化约定（本轮文本可写）+ 未来实测统计 | 纪律：null 不零填；0.36889° 双框架差值不得记为不确定度（E21 权威合同 `branch_delta_is_uncertainty=false` 逐字） |
| SLOT-10 移动铰点质量分配 | Mqq vs Mqq* 冲突（ΔM 见下） | **CONFLICT_NONSELECTING_NONPROPAGATED** | 一切下游柔性动力学数字（SLOT-07 的直接前置） | MPI/动力学权威裁决（见 `R2_FLEX_MASS_ALLOCATION_RULING_OPTIONS_V1.md`） | 裁决落账前 e21 三 false 逐字保持 |

```
ΔM = Mqq* − Mqq = [[0.006, 0.0024, 0], [0.0024, 0.0012, 0], [0, 0, 0]] kg·m²  （e21 逐字）
```

## 2. 参与因子数学定义草案（SLOT-07；仅定义，不计算）

- 现有动能构造（`compute_flexible_appendage_r2.py` 逐字行为描述）：三叶链相对铰转角 q=(q1,q2,q3)，叶绝对角 ψ_i = π/2 + Σ_{j≤i} q_j，叶质心速度链式求和，T 在展开平直言形（q=0）处对 q̇ 二次型展开得 `Mqq`（已发布、e21 复现）。
- 扩展定义（草案）：将基座运动（v_b ∈ R³，ω_b ∈ R³，S 系表达）叠加进叶质心速度，于 q=0 处取交叉块：
  - `B_t = ∂²T / ∂q̇ ∂v_b |₀`（3×3，平动模态动量系数，每铰 DOF 一行）；
  - `B_r = ∂²T / ∂q̇ ∂ω_b |₀`（3×3，转动模态动量系数）；
  - 模态坐标化：`Φ` 来自 `eigh(K, Mqq)`（MC-A 情形），模态参与系数 = `Φᵀ B_t`、`Φᵀ B_r`。
- **结构预测（待计算时复核，不作为结论）**：由运动学结构（铰轴 ∥ X_S、链运动在 (y,z) 平面、展开平直言形叶沿 y 展开）可知一阶耦合稀疏——`B_t` 仅 **v_z** 行非零（v_x、v_y 行恒零：平面运动无 x 向速度分量；q=0 处铰转动产生的叶速度纯沿 z 向），`B_r` 仅 **ω_x** 行非零（ω_y、ω_z 行恒零）；对 X_S 以外轴的耦合为二阶量，线性化模型中应为零。本代理已用一次性纯 Python 链式法则草稿（直接对已发布动能结构求导，不写任何文件）复核该稀疏性：vx/vy 行与 wy/wz 行逐项为零，vz 行与 wx 行非零。计算时若零行出现非零项即实现错误，负控制判据。
- 守恒校核（草案）：自由漂浮耦合装配后，零激励自由传播必须满足动量双账本机器精度（模板：e21 dP ≤ 2.81e-16 / dL ≤ 2.60e-16；sim_05 7.3e-17）。
- 命名纪律：sim_11 旧卡为 R1 悬臂 FFR 计算过 B_t/B_r 类系数；R2 值**必须重新计算**，禁止从 R1 卡继承任何数值（e21 `forbidden` 逐字）。

## 3. 阻尼模型规格草案（SLOT-02）

- 候选形式（择一须带出处）：(i) 模态阻尼比 `C_modal = diag(2 ζ_i ω_i)`（模态坐标）；(ii) Rayleigh `C = αM + βK`（物理坐标，α/β 由两阶模态目标 ζ 反解）。
- 输入需求：每阶模态 ζ_i（或带角）+ 出处；现状全 null，卡片 0.01 与旧卡 0.005 均为无出处占位，**禁止消费**。
- 口径纪律：能量/动量守恒审计一律在 ζ=0 车道进行（沿用 sim_11 能量审计 Gate 强制取 0 的纪律）；耗散车道单独声明，任何"振铃 37–75 s"类结论只允许出自带出处的耗散模型。
- 获取路径排序（建议）：① WP5 工单查 vendor/文献（夹层板+铰链链模态阻尼）；② 地面自由衰减实测（对数减量）；③ 若均不可得，保持 NULL 并禁止一切衰减类结论。

## 4. 强迫响应定义草案（SLOT-08）

- 激励：捕获冲量经有限接触窗（`scene_A2_capture.yaml` 逐字口径：半正弦等冲量 `F(t)=λ·(π/2T_c)·sin(πt/T_c)`，∫F dt = 瞬时 Delassus 解；力旋量方向按捕获瞬间惯性系冻结；`T_c_ms_nominal=20.0` 占位 PROVISIONAL 待 B601 夹爪闭合实测，扫掠域 5/10/20/50/100 ms；窗末残余相对速度一次 Delassus 小冲量收口）。
- 输出需求（草案）：模态坐标 η(t)、叶尖/铰线响应、铰力矩 vs 刚度带角、窗内组合动量账本（模板：sim_11 窗内 2.7e-14、能量审计 8.5e-11、锁定收口冲量 0.035%）、帆板振铃幅度/时长的 R2 口径量化（现状 null；sim_07 历史口径 37–75 s 仅供参考不继承）。
- 禁止项：e21 范围明禁本轮运行 scene A2 类评估；理想冲量（Δt=0）直接评模态能（sim_11 v1.0 教训：不适定，m=2..7 慢收敛尾 +2.86/+1.29/+0.72/~+0.4% 保留为非 Gate 诊断）。

## 5. WP5 R2 硬件选型工单需求清单（文本草案，供 owner 签发）

1. 叶：铺层/胞元构造、真实面密度（对照候选 3.0 kg/m² 与文献 2–5 kg/m² 区间）、EI 与 GJ 的 vendor 数据或试样实测（覆盖 SLOT-01/06）。
2. 铰链：根铰与板间铰展开锁定态旋转刚度实测计划（对照现行带 50/200/800、20/100/400 N·m/rad）、自由间隙测量（覆盖 SLOT-03 铰侧/SLOT-05）。
3. latch：硬件选型 + 刚度/反驱特性 vendor 数据（覆盖 SLOT-03；反驱校核载荷 = 480 N 控制端停瞬态 + 带角一阶模态振动）。
4. 支架：根部支架结构与星体界面柔顺估算/实测计划（覆盖 SLOT-04；参考载荷 48.0 N·m 瞬态候选）。
5. 阻尼：模态阻尼比出处（文献可核查引用）或地面衰减实测方案（覆盖 SLOT-02）。
6. 夹爪：B601 夹爪闭合时间实测（接触窗 T_c 占位 20 ms 替换 → 触发 e15 T5）。

## 6. 纪律声明（逐字有效）

- 本规格为 DRAFT_PENDING_AUTHORITY；不冻结任何参数、不授权任何计算、不修改任何上游文件。
- null 不零填；PROVISIONAL 不当 authority；工程带角不当标准不确定度；两质量矩阵不平均；旧 R1 柔性卡/质量/FFR 不进 R2 车道。
- 全部上游数字引用路径见 §1 表与 §7 哈希绑定；本代理复核记录：五工况频率/Mqq/ΔM/质量闭合复算见 `R2_FLEX_MASS_ALLOCATION_RULING_OPTIONS_V1.md` §1/§6。

## 7. 源文件哈希绑定（sha256:12，本代理 2026-08-23 实测）

| 文件 | sha256:12 |
|---|---|
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/FLEXIBLE_APPENDAGE_R2.yaml` | `a04acfe440c6` |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/FLEXIBLE_APPENDAGE_R2_MODES.json` | `e068de078a0d` |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/compute_flexible_appendage_r2.py` | （与 round0 盘点绑定一致，见该 JSON `2b64a18605abbd1f…`） |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_R2_MECHANISM_ANALYTICAL_LEDGER_V1.yaml` | `11d585258597` |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_HDRM_LATCH_DESIGN_V1.yaml` | `bf8f76e654c5` |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json` | `d5b7dd16532f` |
| `30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results/E21_FIXED_BASE_R2_ROM_REPRODUCTION_AND_MASS_CONFLICT_V1.json` | `57958a9f3ac1` |
| `20_engineering/config/coupled_scene/scene_A2_capture.yaml` | `4b979a1dfd18` |
| `20_engineering/config/coupled_scene/coupled_model_v0.yaml` | `67a532fb29c7` |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round0_handover/03_r2_flex_inputs/R2_FLEX_INPUT_INVENTORY_V1.json` | `82ded3493069` |
