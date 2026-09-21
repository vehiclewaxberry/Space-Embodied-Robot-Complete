# R2 全柔性耦合集成规格 V1（R2_FLEX_COUPLING_INTEGRATION_SPEC_V1）

- schema: `R2_FLEX_COUPLING_INTEGRATION_SPEC_V1`
- 生成时间：2026-08-23T20:22+08:00（宿主机本地钟，Asia/Shanghai UTC+08）
- 生成者：KIMI M7 机械终局接管 swarm 第三轮（R2 全柔性闭合 Wave-3a）AGENT-F2 耦合集成规格子代理
- 工作方式：纯只读 + 文本产出。本轮未启动任何 CAD/FEA/仿真/积分器进程；未修改任何上游文件；git 只读；全部引用数字经路径 + 复算核验（sha256 全 64-hex 见附录 A，遵照 RT1-F01 教训不用截断拼写）。
- 状态：**CANDIDATE / PROVISIONAL —— 本规格不自我生效、不授权任何计算、不闭合任何 Gate**。
- release_credit: **false**；next_stage_authorized: **false**；review_status: PENDING_OWNER_REVIEW。
- 机器可读骨架：`R2_FLEX_COUPLING_INTEGRATION_SPEC_V1.yaml`（同目录；与本文冲突时以 YAML 结构化字段为准）。

## 0. 范围、纪律与边界

本规格回答一个问题：**R2 三叶铰链链 ROM（leaf-only Mqq 权威，MC-A 裁决已工程级落账）应以什么精确方式插入星-臂-帆板全耦合动力学模型（sim_11 路线 A 架构），使得后续 R2_FLEX 车道的实现、对拍与 e15 重认证挂接有据可依。**

逐字纪律（违反即失败，继承 ODR-43/ODR-44、e21 权威合同、MC-A 裁决 `forbidden` 段）：

- 只读已有文件；只在 `r2_full_flex_closure/round1/03_integration_spec/` 写新文件；一切新产物 CANDIDATE/PROVISIONAL。
- 禁止 file exists→PASS；null→0；PROVISIONAL/ASSUMPTION_BAND 冒充测量；两 frame 平均；静默复用旧 24 kg 或 R1 柔性卡（0.3483933 kg/翼、0.7–1.3 Hz 仅限 LEGACY 历史复现车道）；Route-B 负结果改名。
- `r2_full_flexible_coupling = NOT_EVALUATED`（e21 G02/G23 逐字）保持；e15 `REPEAT_ANCF_CERTIFICATION` 逐字保持；R2-HRN-04 `FAIL_REDESIGN_REQUIRED` 逐字保持；GAP-12（24 kg 预算重分配）保持 OPEN。
- 本规格不授权运行任何场景；E15R-T1..T8 挂接映射仅为挂接定义，运行前置硬条件逐字见 §10。

## 1. 证据基线（全部可复核；哈希全文见附录 A）

| 角色 | 路径 | 关键内容（已复核数字） |
|---|---|---|
| 宿主耦合模型 | `30_simulation/sim_11_coupled_dynamics/src/coupled_dynamics.py` 等 | 状态布局/质量阵分块/双积分模式，§2.1 |
| 接触窗 | `30_simulation/sim_11_coupled_dynamics/src/contact_window.py` | 半正弦等冲量 + lockup 收口 |
| sim_11 机器裁决 | `30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json` | `SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS`，G1–G5 全过 |
| 参数卡 | `20_engineering/config/coupled_scene/coupled_model_v0.yaml`、`scene_A1_arm_slew.yaml`、`scene_A2_capture.yaml` | Radau rtol=1e-10/atol=1e-12、cross BDF、T_c=20 ms PROVISIONAL |
| R2 ROM 权威 | `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/FLEXIBLE_APPENDAGE_R2.yaml`、`FLEXIBLE_APPENDAGE_R2_MODES.json` | Mqq、刚度带、五工况频率 |
| R2 ROM 复现 | `30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results/E21_FIXED_BASE_R2_ROM_REPRODUCTION_AND_MASS_CONFLICT_V1.json` | Mqq 复现 4.999999997368221e-10 kg·m²；五工况 ≤4.840419126761475e-05 Hz；damping/participation/forced_response 全 null |
| MC-A 裁决 | `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/decisions/ENG_DECISION_DYNAMIC_MASS_ALLOCATION_V1.yaml` | leaf-only Mqq 唯一权威；2×0.03 kg/翼铰质量刚性界面记账；`dynamic_mass_allocation_frozen=true`（工程级） |
| 双框架桥 | `.../round1_bridge/02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml` | B = Trans(z_A0,+0.02275 m)·Rot(z_A0,+25.000014°)，sha256 `0ACEB659284CAB86…`；MPI_BRIDGE_GATE_V1 = PASS（限域） |
| e21 刚性车道 | `.../results/E21_DIAGNOSTIC_GATE_V1.json` | 23/23 PASS、overall HOLD；V3_R2/C07 31.022864807342987 kg；dP≤2.8114773474276346e-16 |
| e15 现状 | `30_simulation/e15_ancf_certification/results/gate_summary.json`、`config/certification_v1.yaml` | REPEAT_ANCF_CERTIFICATION；交叉差 0.05637349419858036 > 0.05 |
| 退化对拍对象 | `30_simulation/sim_05_free_floating_arm/`、`30_simulation/sim_07_ancf_flexible/`、`30_simulation/common/capture_impulse.py` | 19.20°/7.3e-17；92×/37–75 s；rigidize 规范 |
| 任务可行域/分类器 | `30_simulation/sim_10_mission_feasibility/`、`30_simulation/sim_12_strategy_feasibility/`、`30_simulation/e15_core_coverage/config/threshold_registry_core_v1.yaml` | 四门 fail-closed；阈值 registry 哈希锁 |
| 既有规格草案 | `.../round1_bridge/r2_flex_prep/R2_ROM_PARTICIPATION_DAMPING_SPEC_DRAFT_V1.md`、`E15_RECERTIFICATION_TEST_SPEC_DRAFT_V1.md` | SLOT-01..10、参与因子数学定义、E15R-T1..T8 草案 |
| 输入盘点 | `.../round0_handover/03_r2_flex_inputs/R2_FLEX_INPUT_INVENTORY_V1.json` | GAP-01..12；e15 触发清单 |

## 2. (a) R2 ROM 插入耦合模型的精确位置与方式

### 2.1 宿主模型结构事实（sim_11，逐字复核自源码）

- 广义坐标/拟速度（S = 服务星本体系，基座量用 S 系分量的拟速度，`coupled_dynamics.py` 模块 docstring 逐字）：
  `q = [r_b(3, 惯性系), q_b(quat4, 本体->惯性, scalar-first), theta(6), eta_L(m), eta_R(m)]`，
  `u = [v_b(3), w_b(3), thetad(6), etad_L(m), etad_R(m)]`（`v_b = R^T rdot_b`）。
- 维数与行块：`nu = 12 + 2*m`；`i_b = 0..5`（基座）、`i_a = 6..11`（臂关节）、`i_e = 12..12+2m`（模态）、`i_be = i_b ∪ i_e`（捕获冲量求解的抱闸行集 RL）。
- 动力学方程（Kane/投影 Newton-Euler，与拉格朗日严格一致）：`M(q) udot + c(q,u) = Q`，`Q = [0(基座, 自由漂浮); tau(关节); -K eta - D etad(模态)]`。
- 质量阵分块：`M_bb, M_ba, M_beta, M_aa, M_aeta, M_etaeta`；**本拟速度坐标下 `M_a,eta ≡ 0`**（臂与帆板速度都相对基座定义，耦合经基座块传递——`coupled_dynamics.py` docstring 及 `__main__` 自检断言）。
- 动量映射 `A(q)`（6×nu，S 系对 S 原点 [P; L]）与 M 同遍几何装配（`geometry()`）；独立路径 `momentum_inertial()` 不经 A 矩阵逐体合成，作机器精度交叉证据。
- 双积分模式：`reduced_momentum`（h_I 代数约束 `V_b = H_bb^{-1}(h_S - H_bm qdot_m)`，动量机器精度，对齐 sim_05 证据文化 7.3e-17）与 `full`（V_b 入状态量，动量漂移作装配一致性交叉证据）。
- 能量定理（精确成立，G2 依据）：`d(T+U)/dt = tau·thetad - etad^T D etad`。
- 模态广义力注入点（`accelerations()`）：`Q[i_e] = -(K_eta @ eta) - (D_eta @ etad)`；K_eta/D_eta 为 `[eta_L, eta_R]` 块对角（`__init__` 逐行装配）。
- 外部广义力通路：`Q_ext`（nu 向量），接触窗中 `Q_ext = Phi^T w_S`，`Phi` = 末端 E 部分速度矩阵（6×nu，`capture_solver.ee_partial_velocity`；**模态列结构为零**——接触力旋量作用于臂末端，不直接驱动帆板模态；帆板模态的激励经质量阵耦合块在 `M_RL^{-1} Phi_RL^T lam` 中自动裁定）。
- 捕获冲量：柔性 Delassus `G_c = Phi_RL M_RL^{-1} Phi_RL^T`（含帆板模态列），与目标刚体 Delassus 联立；`rigid_lock_6dof`（6 约束，J+L 全解）/`point_capture_3dof`（3 约束纯力冲量）。刚性极限与 `30_simulation/common/capture_impulse.py::rigidize` 机器精度一致（tests 断言）。
- 接触窗（v1.1，G4 物理修复）：`w_I(t) = lam_I * s(t)`，`s(t) = (pi/(2 T_c)) sin(pi t/T_c)`，`∫s dt = 1`；力旋量方向按捕获瞬间惯性系冻结；作用反作用同点（追踪星末端 E / 目标同一空间点 -w_I）=> 组合动量守恒为机器审计；窗末残余相对速度一次 Delassus 小冲量收口（lockup）。已验证账本级数字：窗内组合动量漂移 2.7346180875298387e-14、能量审计相对 8.459748222451578e-11、lockup 收口冲量比 0.0003533587053109225（0.035%）（`sim_11_scene_A2_summary_bw20.json` + gate JSON G1/G2，本代理复核）。
- 积分器约定（`coupled_model_v0.yaml` 逐字）：`method: Radau`、`cross_method: BDF`、`rtol: 1.0e-10`、`atol: 1.0e-12`、`mode: reduced_momentum`、全确定性无随机数。
- e21 刚性车道复用同一模式（`build_e21_diagnostics.py::RigidArmOnlyModel`）：reduced-momentum Radau、冻结容差（E21-G14）、动量双账本（E21-G15：dP≤2.8114773474276346e-16 / dL≤2.597469647189354e-16）、能量审计（E21-G16：3.8881625317763365e-11 / 4.0484963084180175e-11）、质量阵 SPD（E21-G18）、四元数归一（E21-G17）。**R2_FLEX 车道的 runner 应以 e21/sim_11 同一组装惯例如法炮制（unit-velocity 装配 + reduced/full 双模式 + 双账本审计），禁止另起语义。**

### 2.2 R2 ROM 权威输入（MC-A 后口径）

- 每翼 3 柔性叶 + 根铰柔顺 + 2 板间铰柔顺 + latch 刚度（书/手风琴链，全部铰轴平行 X_S）（`FLEXIBLE_APPENDAGE_R2.yaml` architecture 逐字）。
- 广义坐标（物理层）：每翼 3 个相对铰转角 `q_w = (q1,q2,q3)`（相对展开平直构形 q=0 处线性化）；叶绝对角 ψ_i = π/2 + Σ_{j≤i} q_j；运动在 (y,z) 平面（`compute_flexible_appendage_r2.py::kinetic_energy` 逐字行为）。
- 质量阵（唯一权威 = 已发布 leaf-only Mqq，`wing_L2_reduced_model.mass_matrix_kgm2`，e21 E21-G19 复现最大误差 4.999999997368221e-10 kg·m²）：

  ```
  Mqq = [[0.064800281, 0.033600188, 0.009600094],
         [0.033600188, 0.019200188, 0.006000094],
         [0.009600094, 0.006000094, 0.002400094]]  kg·m²
  ```

- 刚度阵：`K = diag(k_root, k_inter, k_inter)`，带角 root 50/200/800、inter 20/100/400 N·m/rad（全 PROVISIONAL_DERIVED）；五工况 = {nominal(200,100), all_low(50,20), all_high(800,400), root_low_inter_high(50,400), root_high_inter_low(800,20)}。
- 五工况频率（leaf-only 口径权威；e21 E21-G20 复现 ≤4.840419126761475e-05 Hz）：nominal [6.9726, 39.3586, 98.0042]；all_low [3.3278, 18.2952, 44.1763]；all_high [13.9452, 78.7172, 196.0085]；root_low_inter_high [4.3424, 65.0146, 190.5319]；root_high_inter_low [4.7369, 30.2986, 74.9597] Hz。
- 模态化：`Φ` 来自 `eigh(K, Mqq)`（MC-A E5：禁止用 Mqq* 预计算，禁止从 R1 卡继承数值），质量归一 `Φᵀ Mqq Φ = I`；模态刚度 `K_modal = diag(ω_i²)`；模态坐标 η_w 与物理铰角 `q_w = Φ η_w`。
- 模态数：已发布 = 3/翼；ODR-21 带允许 3–5。**m_w=4/5 需要新 ROM 版本重发五工况证据链（触发 e15 T2 族），本规格默认 m_w=3。**
- 保持显式 null（禁止零填）：damping_matrix、participation_factors、forced_response、standard_uncertainty（E21-G22 逐字）；GJ 带（SLOT-01）、latch 独立刚度（SLOT-03）、根部支架界面柔顺（SLOT-04）、铰链自由间隙（SLOT-05）均 null。

### 2.3 状态向量布局（R2_FLEX 车道）

与宿主完全同构，模态块语义替换：

```
q = [r_b(3), q_b(quat4, scalar-first), theta(6), eta_L(m_w), eta_R(m_w)]     # m_w = 3 默认（带 3–5）
u = [v_b(3), w_b(3), thetad(6), etad_L(m_w), etad_R(m_w)]
nu = 12 + 2*m_w          # m_w=3 -> nu=18
i_b = 0..5 ; i_a = 6..11 ; i_e = 12..12+2*m_w ; i_be = i_b ∪ i_e (=RL 抱闸行集)
eta_w = 模态坐标（q_w = Phi eta_w，Phi 质量归一自 eigh(K, Mqq)）
```

`M_a,eta ≡ 0` 性质保持：R2 翼固连于星体（基座），翼内速度同样相对基座定义，臂关节速度不进入叶速度——与 sim_11 docstring 同一论据成立。该性质是装配正确性的零成本不变式，实现后必须进 tests 断言（sim_11 `__main__` 有同款自检）。

### 2.4 质量阵分块组装（逐块指定）

沿用宿主 `geometry()` 单遍装配，每 RHS 调一次。R2_FLEX 车道的体系构成：

1. **基座固连刚体（S 系，惯量对各自质心）**：bus / adapter（经 T_SM）/ 臂 base_link / **翼非随动质量块**（见 §2.7 MC-A 边界：每翼根铰 0.05 kg、板间铰 2×0.03 kg 集中於展开态铰线、HDRM 0.08 kg、harness 0.05 kg）。臂安装语义只经冻结桥 B 消费（§3 车道纪律）。
2. **臂 link1..6**：复用 sim_05 `b601_model` 只读（hash-bound import 模式见 e21 `import_source` + `sys.dont_write_bytecode = True`）。
3. **翼模态子系统（每翼）**：三叶（3×0.18 kg）为随动质量，同时进入 (i) 基座块的刚体输运贡献（展开平直构形 q=0 处）与 (ii) 模态耦合列——与 sim_11 FFR 质点切片同一簿记结构：
   - 基座块：`M[0:3,0:3] += m_leaves·I₃`；`M[0:3,3:6] += -Sx`、`M[3:6,0:3] += Sx`、`M[3:6,3:6] += St`（Sx/St = 叶质心在 q=0 位形的 Σm[x]× 与 Σm[x]×ᵀ[x]× 核；叶自旋惯量块类比 `J_rot_S` 集中块处理）；
   - 耦合列（cols = 该翼模态行切片）：`M[0:3,cols] += B_t`、`M[cols,0:3] += B_tᵀ`、`M[3:6,cols] += B_r`、`M[cols,3:6] += B_rᵀ`、`M[cols,cols] += I`（质量归一模态阵）；
   - 动量映射同列：`A[0:3,cols] += B_t`、`A[3:6,cols] += B_r`；
   - 偏置 `c(q,u)`：线性化 ROM 下 q 只经 K_eta 进 Q；速度二次项（科氏/离心）按宿主同一公式（含 `w_b × v_b` 输运项，**不可省**——sim_11 实现教训，tests 有专门断言）。
4. **可选捕获后目标**：`attach_target`（与 link6 固连）语义不变。

其中 `B_t = Φᵀ B_t,q`、`B_r = Φᵀ B_r,q`；`B_t,q = ∂²T/∂q̇_w∂v_b|₀`（3×3，每铰 DOF 一行）、`B_r,q = ∂²T/∂q̇_w∂ω_b|₀`（3×3），由已发布动能结构（`compute_flexible_appendage_r2.py::kinetic_energy`，链式求和）在 q=0 处对基座运动交叉求导获得（规格草案 §2 定义；MC-A E5 已解除前置）。

**负控制（稀疏性不变式，逐字继承规格草案 §2）**：由运动学结构（铰轴 ∥ X_S、链运动在 (y,z) 平面、展开平直构形叶沿 y 展开），`B_t` 仅 **v_z 行**非零（v_x、v_y 行恒零），`B_r` 仅 **ω_x 行**非零（ω_y、ω_z 行恒零）；对 X_S 以外轴的耦合为二阶量，线性化模型中应为零。**计算/装配后若零行出现非零项即实现错误，必须 fail-closed 抛出。**

**刚化极限闭合不变式（R2 版 mass_split_check）**：η ≡ 0 锁定后，每翼装配质量属性必须等于 `SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json` 展开锁定刚性翼行（C01：每翼 0.78 kg，cg_S = [0, ±0.346553846, -0.099134615] m，`inertia_about_S_origin_kgm2` 见原件；C07 两翼 1.56 kg 行 e21 E21-G09 已核）；容差取机器精度量级（参照 e21 E21-G10 全系统闭合 4.440892098500626e-16 的判据文化）。这是柔性车道与质量账本的唯一接口点：**刚化极限闭合一票否决，任何偏差禁止入 Gate。**

### 2.5 模态阻尼注入

- 注入点：宿主 `accelerations()` 的 `Q[i_e] = -(K_eta @ eta) - (D_eta @ etad)`；R2 车道 `K_eta = blkdiag(diag(ω_L²), diag(ω_R²))`（ω 取当前刚度工况的已发布频率），`D_eta = blkdiag(diag(2 ζ_i ω_i))`。
- **双车道制（规格草案 SLOT-02 逐字）**：守恒审计车道 ζ=0（能量/动量机器精度账本，G2 类审计强制 ζ=0，对齐 sim_11 纪律）与耗散预测车道 ζ≠0 必须分离声明；现状 ζ 全 null——卡片 0.01（TBD_cite_literature）与旧卡 0.005 均为无出处占位，**禁止消费**。阻尼到位前一切衰减/振铃时长类结论禁止输出（sim_07 的 37–75 s 为 R1 历史口径，仅供参考不继承）。
- 耗散车道开通 = e15 T3 触发（耗散项进入认证对象，能量审计口径分叉声明）。

### 2.6 参与因子耦合项进入广义力的通路（逐通路指定)

1. **捕获冲量通路（瞬时柔性 Delassus）**：`lam = -(G_c + G_t)^{-1} rel_pre`，`G_c = Phi_RL M_RL^{-1} Phi_RL^T`；模态列经 `M` 的 B_t/B_r 耦合块进入 `M_RL`——冲量向翼模态的分配由耦合质量阵自动裁定（`capture_solver.py` docstring 同一机制）。模态速度跳变 `detad = du[i_e]`；能量校验区分 `modal_velocity_kick_energy_J`（½detad²，kick 尺度）与 `modal_energy_change_J`（含 etad_pre·detad 交叉项），**二者不得混称**（源码注释逐字纪律）。
2. **接触窗通路（有限带宽）**：`Q_ext = Phi^T w_S`，模态列结构为零（接触在臂末端）；翼模态在窗内经 M 耦合与基座运动双向交换；组合动量（追踪星+目标同点作用反作用）为机器审计；窗末 lockup 一次 Delassus 收口，`lockup_rel_to_lam` 如实输出。
3. **持续激励通路（捕获后自由漂浮段）**：模态广义力只有 `-K η - D η̇`（弹性 + 阻尼）；基座-模态动量交换经 A 阵代数约束（reduced 模式）或全量积分（full 模式交叉证据）。
4. **禁止通路**：理想冲量 Δt=0 直接评模态能（sim_11 v1.0 教训：频谱平坦 + 悬臂 B_t 慢衰减 => 能量指标不适定，m=2..7 慢收敛尾 +2.86/+1.29/+0.72/~+0.4% 保留为非 Gate 诊断）；任何把 B_t/B_r 当外力直接加进 Q[i_e] 的实现（物理上那是根运动激励的耦合系数，不是力）。

### 2.7 与 MC-A 记账口径的一致性（铰质量：系统质量账本 vs ROM 动能边界）

- **ROM 动能侧**：唯一权威质量阵 = leaf-only Mqq（§2.2）；ΔM = Mqq* − Mqq = [[0.006, 0.0024, 0], [0.0024, 0.0012, 0], [0, 0, 0]] kg·m²（e21 逐字）**被排除在 ROM 动能之外**；禁止消费 Mqq*、禁止两阵平均、禁止按模块混用（MC-A freeze_surface 逐字）。
- **系统质量账本侧**：每翼 2×0.03 kg 移动板间铰点质量作为**刚性、非随动**界面质量集中记账在铰线处（MC-A rule_verbatim_engineering 逐字）；0.78 kg/翼闭合（3×0.18 叶 + 0.05 根铰 + 2×0.03 板间铰 + 0.08 HDRM + 0.05 harness，本代理按 `SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json mass_model` 复核求和一致）；两翼 1.56 kg；整星 24.8632134 kg（24 kg 预算重分配 GAP-12 OPEN，本规格不触碰）。
- **耦合模型落法**：该 2×0.03 kg/翼在 §2.4 第 1 类"基座固连刚体"中以展开态铰线位置点质量入账（进 M_bb/A 的刚体输运项），**不进**模态耦合列、不进 Mqq——两侧各记一次、互不重复，刚化极限闭合不变式（§2.4）对此天然闭环。
- **频移簿记差异**：Mqq* 车道相对 leaf-only 的频率下移（nominal -3.5096% / -6.9411% / -13.4%；五工况表见 MC-A `five_case_relative_shift_pct_recomputed`）为 **KNOWN_BOOKKEEPING_DIFFERENCE__NOT_STANDARD_UNCERTAINTY**（BK-DYN-MASS-HINGE-ALLOC-MC-A 逐字）；standard_uncertainty 保持 null；禁止平均、禁止修正、禁止零填。leaf-only 口径偏刚 = 柔性响应估计偏保守一侧（MC-A reverse_framing_note）。
- 逆转条件 RC-1..RC-4（MC-A 逐字）任一命中即解冻重裁决；届时若切换 Mqq* 车道，已发布 MODES.json 须新版本重发且 e15 T2 触发。

## 3. (b) 三车道定义

| 车道 | 定义 | 消费口径 | 状态纪律 |
|---|---|---|---|
| **RIGID** | 展开锁定刚性翼自由漂浮：e21 模式（V3_R2/C07 固定残余 26.327308858000002 kg + 完整 B601 臂，全系统 31.022864807342987 kg，E21-G10 闭合 0/0/4.44e-16），reduced-momentum Radau runner；含 sim_10/sim_12 刚性堆栈可行域扫描 | 质量/惯量经 V3_R2 账本 + 冻结桥 B；臂安装语义唯一消费者 = ODR01_DYNAMICS 经桥（consumer_ambiguity=0，MPI-FB Gate PASS 限域） | 不受 MC-A 影响（E9 逐字），继续按既有合同走；本车道不断言任何柔性结论 |
| **LEGACY_R1_FLEX** | sim_11 v1.1 FFR 悬臂 EB 模态车道（`coupled_model_v0.yaml`：0.3483933 kg/翼、0.7/1.0/1.3 Hz 包络、ζ=0.005 占位、T_c=20 ms 占位） | 仅历史复现：G1–G5 裁决（`SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS`）与全部 artifacts 作为冻结历史记录 | **禁止新结论引用**（MC-A E7、e21 forbidden 逐字）；禁止把 R1 卡任何数值带入 R2_FLEX；其退化链证据（19.20° 等）属于 R1 质量口径，对 R2 系统不适用 |
| **R2_FLEX** | 本规格定义的新车道：R2 三叶铰链链 ROM（leaf-only Mqq 权威）插入宿主耦合装配，五刚度工况，模态阻尼 null，参与因子待计算（前置已由 MC-A E5 解除） | 只消费：FLEXIBLE_APPENDAGE_R2（hash-bound）+ MC-A 裁决 + 冻结桥 + e21 刚性残余；禁止消费 R1 柔性卡、旧 24 kg 质量行、Mqq* | `r2_full_flexible_coupling = NOT_EVALUATED` 逐字保持；本规格不授权运行；全部未来输出 CANDIDATE 直至 e15R 闭合 + owner 放行 |

车道隔离不变式：三车道独立模型对象、独立零初态、禁止状态互传（e21 E21-G12 模式）；跨车道对比只允许"同族指标 + 容差纪律"层级（E15R-T2 口径），禁止跨车道数值并册。

## 4. (c) 锚例配置（两例，参数全部有出处）

两锚例 = sim_12 证明集的 A_low / B_anchor（`20_engineering/config/strategy_feasibility/strategies_v0.yaml` 逐字：`A_low: {cls: G2_cubesat, m_t_kg: 22.0, omega_dps: 0.5}`、`B_anchor: {cls: G1_slender, m_t_kg: 150.0, omega_dps: 3.0}`），与 sim_13 名义锚（22 kg/0.5 dps、150 kg/3.0 dps）、sim_06 矩阵行、safety_00 CAPTURE 名义输入一致。目标 SSOT：`20_engineering/config/geometry/target_models_v1.yaml`。

### 锚例 A：ANCHOR_SAT22_0P5DPS（22 kg 目标星 @ 0.5°/s）

- target_object_id: `target_satellite_v0`；mass 22.0 kg；惯量对角 [0.231629, 0.422149, 0.489336] kg·m²；抓点 launch_adapter_ring [290, 0, 0] mm_T（lever_to_com 0.2517 m）；置信度 low（RA-003 逐字）。
- 翻滚：0.5°/s 绕 TUMBLE_AXIS = [1.0, 0.15, 0.4]/‖·‖（`capture_impulse.py` 冻结常量）；v_app = 0.01 m/s（sim_06/08/10 名义）。
- 刚性锚值（s1 被动口径，sim_12 `strategy_results.csv` A_low/S1_passive 行 + sim_06 CSV 行，本代理复核一致）：ω⁺ = 0.23120208979778084°/s；|H_c| = 0.0024962462560704844 N·m·s；|J| = 0.12021626868793249 N·s；sim_06 附加列：grasp_couple 0.00151767 N·m·s、dT 0.000607468 J、budget_2dps = WITHIN_BUDGET；分类：gate1 过（0.2312 ≤ 2.0）、gate2 过（0.00250 ≪ 0.045/0.300 轮组档）→ **WHEELS_ONLY_FEASIBLE / binding NONE**；S1 燃料 0 g；wheel_margin 0.297504 N·m·s（wheels_large 档）。
- sim_10 对照锚（同一目标 ω=3°/s 口径）：μ=0.917 → ω⁺=1.3872°/s → WHEELS_ONLY_FEASIBLE（README_sim_10 逐字）。

### 锚例 B：ANCHOR_DEB150_3DPS（150 kg 碎片 @ 3°/s）

- target_object_id: `target_debris_v0`；mass 150.0 kg；惯量对角 [74.805599, 74.829903, 26.592617] kg·m²；抓点 nozzle_rim [660, 0, 950] mm_D（lateral_lever 1.02 m；sim_06 行 grasp_leverarm 1.21521 m）；置信度 low（RA-003）；known_issue：solid placeholder density 60.9 kg/m³ non-physical（D-8 逐字保持）。
- 翻滚：3.0°/s 绕 TUMBLE_AXIS；v_app = 0.01 m/s。
- 刚性锚值（sim_12 B_anchor/S1_passive 行 + sim_06 CSV 行复核一致）：ω⁺ = 3.0633304945807067°/s；|H_c| = 3.650992635553959 N·m·s；|J| = 0.3384597133729326 N·s；sim_06 附加列：grasp_couple 0.121693 N·m·s、dT 0.00527415 J、eps_H_origin 3.84985e-16、budget_2dps = OVER_BUDGET；分类：gate1 失败（3.0633 > 2.0）→ **INFEASIBLE_RATE / binding POST_CAPTURE_RATE_EXCEEDS_LIMIT**；S4 消旋燃料 36.4998 g（sim_12 行）。
- sim_10 对照锚：μ=6.25 → ω⁺=3.0633°/s → INFEASIBLE_RATE（README_sim_10 逐字）；sim_08 口径 |H_c|=3.65 N·m·s = 12× 轮组容量（AGENTS.md 已验证证据区）。
- sim_11 LEGACY 车道对照（R1 柔性占位参数，**仅历史参照**）：A2 场景 |J| = 0.8590247898519836 N·s、|L| = 0.517635563322184 N·m·s、dT = 0.020087831721442267 J、|H_O| = 3.6782586304198084 N·m·s（惯性原点）/ |L_C| = 3.7213991753489832 N·m·s（系统质心）（`sim_11_scene_A2_summary.json`，捕获在 A1 末态预抓取构形上叠加，与 sim_06 零姿态堆栈不同口径，禁止直接并数值）。

### 锚例场景配置骨架（R2_FLEX 车道，YAML 机器可读骨架见同目录 .yaml）

激励口径逐字沿用 `scene_A2_capture.yaml`：半正弦等冲量 `F(t)=λ·(π/2T_c)·sin(πt/T_c)`、∫F dt = 瞬时 Delassus 解；力旋量方向按捕获瞬间惯性系冻结；`T_c_ms_nominal = 20.0`（**PROVISIONAL 待 B601 夹爪闭合实测**，扫掠域 [5, 10, 20, 50, 100] ms）；窗末 lockup 收口；约束模式 rigid_lock_6dof 主案 / point_capture_3dof 对比案（capture_interface SSOT）；捕获瞬间关节抱闸；捕获后目标并入组合体。刚度工况：五工况全扫（§2.2）。模态数 m_w=3。阻尼：守恒审计车道 ζ=0（强制）；耗散车道关闭（阻尼 null）。积分器：Radau rtol=1e-10/atol=1e-12 主 + BDF 交叉（e15 T6 纪律，偏离即触发重认证）。捕获后窗口：t_post 40 s 特征窗（末值为 40 s 快照非渐近，scene_A2 post 段口径逐字）+ 短窗变体供收敛链。

## 5. (d) 输出指标精确定义（逐字引用出处）

R2_FLEX 车道输出指标 = 宿主 sim_11/sime10 既有定义的平移，字段名与语义逐字对齐，禁止改名或改口径：

1. **base attitude peak/final**（基座姿态偏差）：`peak_base_attitude_deviation_deg` / `final_base_attitude_deviation_deg`——四元数标部换算 `dev = degrees(2*arccos(|q_w|))`（`coupled_dynamics._collect`；e21 同名字段同一公式）。A1 类机动场景参照值（LEGACY）：19.199885629572467°（`sim_11_scene_A1_summary.json`）；R2 刚性车道参照值（M07 轨迹）：29.041965867604112°（ODR01 车道，E21-G15）。
2. **基座角速率**：`base_rate_peak_dps = max ||w_b||·180/π`、`base_rate_final_dps`（`scene_a2_capture.summarize` post 段逐字：`float(np.max(np.linalg.norm(wb, axis=1)) * 180 / np.pi)`）。
3. **ω⁺（捕获后角速度）**：刚体口径 `w_plus = I_c^{-1} H`（`capture_impulse.rigidize` 逐字），`w_plus_dps`（`feasibility_core.exact_point`）。R2_FLEX 车道派生等效量定义（本规格新增，CANDIDATE）：`omega_plus_equiv_dps = degrees(|| I_comb(θ_f, η=0)^{-1} · L_C ||)`，其中 L_C = 捕获完成瞬间组合系统对系统质心角动量（`momentum_inertial_groups` + `chaser_composite` 既有机制），I_comb 取锁定构形复合惯量；**与 base_rate_final_dps 同时输出，二者偏差即柔性动能占比的观测量**。刚化退化链（E15R-T3）下 omega_plus_equiv 必须回刚性锚值（锚 A 0.23120208979778084 / 锚 B 3.0633304945807067 °/s）。
4. **modal energy（模态能量）**：`panel_modal_energy_peak_J` / `panel_modal_energy_final_J` = `0.5·etadᵀetad + 0.5·etaᵀ K_eta eta`（质量归一 ⇒ 模态质量为 1；`scene_a2_capture.summarize` 逐字）；接触窗口径 `window_modal_energy_peak_J` 与合并峰值 `combined.modal_energy_peak_J`（窗内与捕获后窗合并最大值，run_gates G4 window_note 逐字）；LEGACY 参照：bw20 combined 1.2789845032388716e-05 J。
5. **wheel momentum（轮组动量需求）**：|H_c|（捕获后需轮组吸收的角动量模）与 `h_star = H_c / wheel_Nms`（`feasibility_core.gate_point` 逐字）；轮组档 wheels_small 0.045 / wheels_large 0.300 N·m·s（sim_08 出处，`scan_v0.yaml actuator_tiers`）；registry 上限 `wheel_momentum_max_Nms = 5.475`（PROVISIONAL UNVERIFIED 逐字）。
6. **stabilization proxy（可稳定性代理）**：sim_10 门1 `post_capture_rate_max_dps = 2.0`°/s（registry 逐字：`source_type: MISSION_ASSUMPTION`，source `sim_04_capture_corridor.py:POST_CAP_BUDGET`，`verification_status: PARTIAL`）；判定式 `gate1 = w_plus_dps <= post_capture_rate_max_dps`（`gate_point` 逐字）。R2_FLEX 车道对应可观测量 = §5.3 的 omega_plus_equiv_dps 与 base_rate_final_dps。**注**：control_02 的 `STABILIZED_WITHIN_WINDOW` 属 Wave1 PROVISIONAL 执行器/时窗模型（L0 硬件有效稳定性 NOT_EVALUATED_NO_ACTUATOR_DYNAMICS），不并入本车道指标。
7. **守恒/审计账本**（每场景强制）：`momentum_max_abs_dP/dL`（reduced 全程，Gate 模板 1e-12；e21 模板 dP≤2.8114773474276346e-16 / dL≤2.597469647189354e-16；sim_05 文化 7.3e-17）；`energy_audit_rel`（无阻尼强制 <1e-8，sim_11 G2 口径）；接触窗 `window_momentum_drift_max` / `window_energy_audit_rel`（模板 2.7346180875298387e-14 / 8.459748222451578e-11）；`lockup_rel_to_lam`（模板 0.0003533587053109225）；`attach_momentum_residual`（并入路径 vs 分体路径机器精度）。
8. **帆板响应**：`tip_L/R_peak_mm` 的 R2 对应物 = **铰线/叶尖响应**（叶尖相对展开位形偏移，由 q_w = Φη 链式重构；R2 为铰链链非连续体，输出定义须在 ROM 产物中给出重构公式，见 §9 IR-03）；主频 `tip_L_dominant_freq_hz`（Hann 窗 + 抛物线插值 FFT，`scene_a2_capture.dominant_frequency` 逐字算法）。
9. **动量重分配诊断**：`L_about_com_initial/final_Nms` 按体组 {base, arm, panels, target}（`momentum_inertial_groups` + `group_momentum_series` 逐字机制）；sim_12 纪律：外部矢量角冲量 |ΔH_vec| 与 |H| 标量变化不得混用（Gate0 账本仲裁文件 `10_research/sim_12/momentum_ledger.md`）。

## 6. (e) 安全分类翻转检测法（flip = 真实科学结果，必须记录，不得平滑）

1. **分类器复用口径**：sim_10 四门 fail-closed（`feasibility_core.gate_point` 逐字顺序：门1 捕获后转速 ≤2.0 °/s；门2 轮组容量 |H_c| ≤ n_w·h_w；门3 推力器冲量 J_req = |H_c|/l_T ≤ J_avail = m_prop·Isp·g0；门4 消旋时间 t_d = |H_c|/(F·l_T) ≤ t_max），区域 `WHEELS_ONLY_FEASIBLE / THRUSTER_REQUIRED_FEASIBLE / INFEASIBLE_RATE / INFEASIBLE_RESOURCE`，binding = 声明顺序中首个失败门（registry `binding_priority`/`primary_binding_rule: first_failed_independent_gate_in_declared_order`）；阈值经冻结 registry SHA-256 绑定（`scan_v0.yaml frozen_inputs`），`thresholds_widened` 断言必须为 False（禁止放宽）；`derived_metrics_do_not_duplicate_binding: true`。
2. **翻转检测程序（CANDIDATE 定义）**：
   - S1 刚性锚分类：region_rigid/binding_rigid 取 §4 锚值（A：WHEELS_ONLY_FEASIBLE/NONE；B：INFEASIBLE_RATE/POST_CAPTURE_RATE_EXCEEDS_LIMIT），与 sim_10/sim_12 机器恒等锚定（X1 锚点纪律：求解器恒等 <1e-12）。
   - S2 R2_FLEX 车道同激励运行后，提取 omega_plus_equiv_dps 与 |H_c|（§5.3/§5.5 定义），经**同一** `gate_point` 与**同一** registry 阈值重分类得 region_flex/binding_flex；五刚度工况逐角点各出一套分类（带角不得并册）。
   - S3 翻转判定：`region_flex ≠ region_rigid` 或 `binding_flex ≠ binding_rigid`（任一工况）即记 `CLASSIFICATION_FLIP` 事件，字段：锚例、工况、双向 region/binding、omega_plus_equiv、H_c、模态能量峰值、证据链哈希。
   - S4 **翻转是一等科学结果**：必须逐字记录进裁决 JSON，禁止平滑/平均/多数投票/静默；特别是**使不可行区收缩的翻转**（如 B 锚 INFEASIBLE_RATE 变为可行）将证伪 sim_10 报告 §6"柔性使不可行区只扩不缩"的保守性方向声明（`flex_status=UNKNOWN_NOT_IN_CRITERIA` 时代的声明），必须显式上报 owner，禁止降级为脚注。
3. **权威性分层**：e15R 闭合前，R2_FLEX 分类结果为 **诊断**（diagnostic），安全分类的权威口径保持刚性锚 + `FLEX=UNKNOWN_NOT_IN_CRITERIA`（sim_10 现行纪律逐字）；e15R 闭合 + owner 放行后方可升格。h_star/j_star 等派生指标不重复绑定（registry `derived_metrics_do_not_duplicate_binding`）。

## 7. (f) e15R 测试挂接映射（E15R-T1..T8 → 脚本/对拍对象/容差）

映射基线：`E15_RECERTIFICATION_TEST_SPEC_DRAFT_V1.md` §3（DRAFT_PENDING_AUTHORITY 逐字保持）+ e15 关闭条件（`certification_v1.yaml`）+ sim_11 G1–G5 已实现先例（可直接复用的挂接模式）。e15 现状缺口逐字：`overall = REPEAT_ANCF_CERTIFICATION`；交叉求解 `comparison_count=6`、`max_relative_difference=0.05637349419858036 > 0.05`；`final_candidate_cross_solver.available=false`（原因逐字：「冻结E1.5为SAFE=0且无名义Top-3；不得用低振幅诊断锚点冒充最终候选。」）。

| 测试 | 挂接脚本/模式 | 对拍对象 | 容差/判据 | 备注 |
|---|---|---|---|---|
| **E15R-T1** 冻结最终候选交叉求解对拍（5% 主项） | 新 R2 耦合 runner 的 Radau vs BDF 双积分（同一 rtol=1e-10/atol=1e-12 族；模式先例 = sim_11 `run_gates.py` G5：`--method BDF` tag 工件 + `rel_diff` 聚合，TH_G5_CROSS=0.05） | e15 既有 6 项比较的同族输出（`tables/cross_solver_differences.csv` 列：relative_tip_peak / relative_root_moment_peak / relative_strain_energy_peak / relative_total_energy_peak；行族 = mesh 2/4/8 velocity_jump + 8 单元脉冲 0.02/0.01 s）扩展到 R2 耦合对应量（铰线/叶尖响应、铰力矩、模态应变能、总能量、base_rate_peak、omega_plus_equiv、modal_energy_peak） | 全部比较项相对差 ≤ 0.05（`final_candidate_cross_solver_relative_max`）；success/status/message scipy 语义分类，放宽容差后的返回成功不得作收敛证明（primary_sources 纪律） | 前置硬条件：最终候选已冻结（SAFE>0 + 名义 Top-3，现状不存在）；MC-A 已落账（工程级满足）；T5 接触窗口径声明；本规格不授权运行 |
| **E15R-T2** 组件级同激励对拍 sim_07 | R2 翼组件（锁关节、同激励族）在新装配中的组件级模式；先例 = sim_11 G3a（`gate3a_locked_joints_vs_sim07`：同激励一次性速度跳变驱动 + 与 `sim_07/results/task_response_summary.csv` 对拍） | sim_07 已认证行为族：点捕获 vs 刚性锁定 ≈92× 放大、振铃 37–75 s（R1 口径）、benchmark b1 静变形 rel 1.03e-04、b2 频率 err ≤8.0e-05、b3 零刚体应变能 ~1e-14 J、b4 能量漂移 ≤1.6e-09、b5 网格收敛单调（草案 §3 逐字） | 同族容差带：b1 <1%、b2 <5%、b3 机器精度、b4 <1e-6@tight、b5 单调收敛（草案值）；sim_11 G3a 已用带：tip <5%（TH_G3A_TIP=0.05）、主频 <2%（TH_G3A_FREQ=0.02） | R2 组件为三叶铰链链，**对比行为族与容差纪律，不是逐数值相等**（草案逐字）；R2 数值基线 = 已发布五工况（e21 复现 ≤4.84e-05 Hz）；激励/约束/输出定义逐字一致声明强制 |
| **E15R-T3** 帆板刚化退化（退化链第二环） | 程序内刚度乘子扫描：五工况 all_high 起继续放大至刚化极限；先例 = sim_11 G3b（`gate3b_rigid_panels_vs_sim05`：峰值对比 + 逐点时程对比） | **R2 车道锚 = e21 刚性车道**（V3_R2/C07 + M07 轨迹）：ODR01 车道峰值 29.041965867604112°、dP ≤ 2.8114773474276346e-16、能量审计 3.8881625317763365e-11（E21-G15/G16）；非 sim_05 19.20°（该值属 R1 质量口径，见 §8 风险 R7） | 刚化极限峰值收敛到 e21 刚性车道声明容差内（草案建议 ≤1%，待定）；动量残差机器精度量级；sim_11 G3b 既有带：峰值 <0.1% + 逐点 <1e-3°（供校准参考） | LEGACY 车道的 19.20°/7.3e-17 回归由 sim_11 自身 G3b 继续承担，不移入 R2 车道 |
| **E15R-T4** 全刚化 sim_01 式无力矩传播（退化链第三环） | 臂锁 + 翼刚化 = 单刚体，初态翻滚自由传播；先例 = sim_11 G3c（`gate3c_all_rigid_vs_sim01`） | `30_simulation/common/rigid_body.py::propagate_torque_free`（合成惯量 `chaser_composite`） | 姿态角逐点 <1e-5°（TH_G3C_ANGLE_DEG）+ 动量机器精度（TH_G1_MOM=1e-12）；w0=[1,5,2]°/s 族 | 证据范围声明逐字沿用："同一全刚化组合体退化……不是与 24 kg sim_01 冻结工件逐点同构" |
| **E15R-T5** 动量守恒机器精度 | 全部场景双账本（reduced 主 + full 交叉）；接触窗组合动量单列 | 模板：sim_05 7.3e-17；e21 双车道 dP≤2.8114773474276346e-16 / dL≤2.597469647189354e-16（E21-G15）；sim_11 reduced Gate 1e-12 / 窗内组合 2.7346180875298387e-14 + 能量审计 8.459748222451578e-11 | 无接触/无耗散工况 |dP|,|dL| ≤ 1e-13 量级（草案值，对齐 e21 模板）；含接触窗工况按 sim_11 口径单独声明阈值（2.7e-14 量级） | 阻尼引入后（T3）能量账本不再守恒，动量账本仍必须机器精度（草案备注逐字） |
| **E15R-T6** 离散化趋势回归 | e15 协议族（mesh 2/4/8、脉冲 0.02/0.01 s、Newmark 0.02/0.01/0.005 s）用于 HF 组件；模态 ROM 对应物 = 模态截断扫描 + rtol 扫描（先例 = sim_11 G4：A1 m=2/3/4 + rtol 1e-8 vs 1e-10；A2 接触带宽下前向加密链 m3→m4→m5，TH_G4_CONV=0.01） | 趋势可观测性（`require_mesh_trend`/`require_time_step_trend` 双 true）；e15 既有序列参照：Newmark 误差 6.80e-2/2.36e-2/5.99e-3 单调降、mesh changes 2.13e-2/2.68e-3 | R2 车道模态截断收敛 <1%（同 G4 判据）且**必须重做**——接触带边 1/(2·0.02 s)=25 Hz 与 R2 模态带（3.33–196.01 Hz）的相对位置异于 R1（0.7–1.3 Hz），sim_11 G4 结论不可继承（§8 风险 R4） | m_w=2 粗化对比的分辨率诊断口径（带内模态缺失）沿用 G4 window_note 纪律 |
| **E15R-T7** 历史分类回归 | e15 既有历史重跑协议（`certification_v1.yaml historical_rerun`：Radau+BDF、8 单元、t=15 s 等逐字参数） | 7 历史用例（P1_tc60_v20mm…P3_tc60_v5mm 逐字） | classification_fraction=1.0、unclassified=0、silent_zero=0；任何重分类须单独裁决记录，禁止静默 | 新求解链接管历史用例前的回归基线 |
| **E15R-T8** 低振幅 ANCF-模态对拍回归 | 低振幅（1e-4 激励）协议（`certification_v1.yaml low_amplitude` 段逐字：baseline/tight 容差族、硬墙 12 s） | ANCF 对线性模态极限轨迹相对差（现状 8.191436722962712e-05） | ≤ 0.10（`low_amplitude_ancf_modal_relative_max`）；网格趋势同时观测 | R2 组件上线性模态极限 = 已发布五工况频率族的直接对拍 |

触发—测试追溯（T1–T7 → 必跑测试矩阵）逐字沿用草案 §4；多触发叠加一次重跑覆盖，不得拆分分批放行。

## 8. 集成风险清单（AGENT-F2 findings）

- **R1（高）翼根/铰线几何未钉入动力学可消费 SSOT**：根铰点 P0 = (y=0.1149, z=-0.10815) m 仅存在于 `compute_flexible_appendage_r2.py` 第 56 行常量；`FLEXIBLE_APPENDAGE_R2.yaml`/`FLEXIBLE_APPENDAGE_R2_MODES.json` 均未携带铰线位置/铰轴方向/展开方向的显式帧定义。耦合装配的 B_r 与刚化闭合都依赖该几何——**必须先经 T_PHYSICAL_TO_DYNAMIC 桥登记为动力学可消费接口（GAP-10），否则 B 阵无从权威计算**。
- **R2（高）参与因子全 null**：B_t/B_r 数学定义已就绪（规格草案 §2）但数值未计算；其错误将经 §2.6 通路 1/2 直接污染模态激励（模态列不经 Q_ext 直接外力，全部激励经质量耦合）——负控制稀疏性断言（B_t 仅 v_z 行、B_r 仅 ω_x 行非零）必须 fail-closed 进 tests。
- **R3（高）阻尼 null**：一切振铃衰减预测（含捕获后 40 s 窗口的振铃时长结论）在 SLOT-02 闭合前禁止输出；守恒审计强制 ζ=0 车道；占位 0.01/0.005 禁止消费（双车道纪律）。
- **R4（中高）接触带宽 × R2 模态带交互未评估**：R2 一阶模态 3.33–13.95 Hz 落在 25 Hz 接触带边内，二阶 18.30–78.72 Hz 跨带边，三阶 44.18–196.01 Hz 大部在带外——与 R1（0.7–1.3 Hz 全在带内深处）定性不同；sim_11 G4 的 m3→m4→m5 收敛证据与"带宽下 1% 判据适定"结论**不可继承**，模态截断扫描必须在 R2 带上重做（E15R-T6）。高阶模态 196 Hz 对 Radau rtol=1e-10 的步长压力须在首跑时以 nfev/步长统计复核（积分器约定变更 = e15 T6 触发）。
- **R5（中高）线性化 ROM 小角域 validity 未闭合**：ROM 为 q=0 处二次型展开；捕获激励下铰转角幅度（forced_response=null）未量化；大变形几何刚化/软化不在模型内。耦合输出的铰角峰值必须回代校验小角假设（建议 |q_w| 峰值与铰刚度带乘积 = 铰力矩，对照机构账本 48.0 N·m 根部支架瞬态候选与 480 N 控制端停 latch 反驱校核载荷；超域即声明出域，禁止外推结论）。
- **R6（中）质量账本双口径**：整星 24.8632134 kg（R1 24 kg 预算线 +0.8632134 kg，GAP-12 OPEN）与 e21 系统口径 V3_R2/C07 31.022864807342987 kg（含臂 4.695556 kg）分属不同账本；R2_FLEX 车道只能消费 V3_R2 账本经桥（禁止静默复用旧 24 kg 行或 `mass_inertia_budget_v1.csv` 的 servicer_12U_v0 行——该 CSV 是 LEGACY 车道 SSOT）。
- **R7（中）刚化退化锚的口径错配风险**：sim_05 19.20° 是 R1 质量口径（25.2 kg 复合基座 + 4.6956 kg 臂）的锚；R2 系统刚化退化的正确锚 = e21 刚性车道（29.041965867604112°@M07，或未来 R2 版 A1 类场景）。E15R-T3 若误用 19.20° 即车道污染（LEGACY 数值入 R2），必须在 Gate 脚本中把锚值来源做成显式断言。
- **R8（中）e15 最终候选不存在**：E15R-T1 前置（SAFE>0 + 名义 Top-3）现状不满足；本规格的 T1 挂接仅为定义。任何用低振幅诊断锚点冒充最终候选的行为 = 重犯 e15 已登记错误（原因字段逐字在案）。
- **R9（中）消费语义唯一性**：臂安装语义只经冻结桥 B（sha256 `0ACEB659284CAB862BA65228C5C2DF4BEB06D9EE05B5E2F0B2B5CB38402BF72C`）消费；WP11_PHYSICAL_GEOMETRY_CONTEXT 车道（29.41085537835705°）为敏感性记录不可混用；0.3688895107529362° 分支差不是不确定度（`branch_delta_is_uncertainty=false` 逐字）。新 runner 挂载点构造点必须为 1（MPI-FB-05 审计口径 `mount_construction_sites_in_runner=1`）。
- **R10（中）R2-HRN-04 FAIL_REDESIGN_REQUIRED**：harness 0.05 kg/翼在翼质量闭合内；重设计可能扰动 Mqq → e15 T2 触发 + MC-A RC 族再评估；本规格的质量阵接口须把 harness 质量块做成独立可替换行。
- **R11（低）模态数扩展成本**：m_w=4/5 需新 ROM 版本重发五工况证据链（MC-B 裁决理由同款断档成本）；本规格 m_w=3 默认与 ODR-21 带（3–5）兼容，扩展决策权属 owner。
- **R12（低）状态布局版本化**：nu=18（m_w=3）写入 CSV/JSON 的列结构（`eta_L1..3/eta_R1..3` 等）须带 schema 版本；LEGACY 工件（m=3 FFR）与 R2 工件同名列禁止混读（输出文件名建议带 `r2flex` tag，类比 sim_11 `--tag` 机制）。

## 9. 对 HF/ROM 产物的接口要求清单（CANDIDATE，供下游工作包消费）

- **IR-01 ROM 包（必需，新版本不重写既有件）**：机器可读 + 哈希钉入：leaf-only Mqq（逐字）、K 五工况（diag(k_root,k_inter,k_inter)）、Φ（eigh(K,Mqq) 质量归一）、ω 五工况；schema 扩展 `FLEXIBLE_APPENDAGE_R2.yaml`/`MODES.json` 的新版本文件；禁改已发布件。
- **IR-02 参与因子包（必需）**：每翼 B_t,q/B_r,q（3×3，物理铰坐标，q=0 处）+ 模态化 ΦᵀB_t/ΦᵀB_r；附推导记录（对已发布动能结构链式求导，q=0 交叉块）；负控制：B_t 的 v_x/v_y 行、B_r 的 ω_y/ω_z 行精确为零（非零即实现错误 fail-closed）；计算口径 = MC-A E5（禁 Mqq* 预计算、禁 R1 继承）。
- **IR-03 几何接口（必需，桥登记）**：每翼根铰线点 + 铰轴方向（∥X_S）+ 展开方向在 S 系的显式定义；铰线集中质量位（根铰 0.05 kg、板间铰 2×0.03 kg、HDRM 0.08 kg、harness 0.05 kg 的安装点）；叶尖/铰线响应重构公式（q_w→物理位移）；现状唯一来源 `compute_flexible_appendage_r2.py` P0 常量，须升格为 SSOT。
- **IR-04 刚化闭合数据集（必需）**：展开锁定每翼/两翼刚性质量属性（`SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json` C01/C07 行）作为 §2.4 刚化极限闭合不变式的对照真值，机器精度量级容差。
- **IR-05 阻尼（阻塞中）**：显式 null 保持至 SLOT-02 闭合；闭合时给每阶模态 ζ_i（或带角）+ 可核查出处（vendor/文献/实测对数减量）；双车道声明强制。
- **IR-06 HF 模型（未来，GAP-01/03/05/06/07 闭合后）**：每翼 3 柔性叶 + 2 板间铰 + 根铰/latch 柔顺（GJ 带 SLOT-01 前置）；职责 = 大变形校核、铰力矩 vs 刚度带角、自由间隙（SLOT-05）非线性；实测替换触发 e15 T2/T4。
- **IR-07 接触接口（阻塞中）**：B601 夹爪闭合时间实测替换 T_c=20 ms 占位 → e15 T5 触发；扫掠域 [5,10,20,50,100] ms 保持。
- **IR-08 版本与触发纪律（强制）**：任何 ROM/HF 参数变更 = 新版本号文件 + e15 触发登记（T1–T7 逐字）；禁静默；MC-A RC-1..RC-4 命中即解冻重裁决。

## 10. 不授权事项与 HOLD 逐字保持

- 本规格不授权运行任何场景、不授权修改 e15/e21/sim_05/sim_07/sim_11/V5 等一切上游既有文件与 gate、不授权任何 CAD/FEA/仿真进程。
- `r2_full_flexible_coupling = NOT_EVALUATED`；scene-A2 类捕获经 R2 柔性评估 HOLD（须 GAP-03/04 闭合 + MPI-FB-01..08 + owner 放行，MC-A E8 逐字）；e15 重认证运行不授权（MC-A E3 逐字）；24 kg 预算重分配不触碰（GAP-12 OPEN）。
- E15R 运行前置硬条件（草案 §5 逐字）：MC 裁决落账（工程级已满足，owner 确认 pending）；MPI-FB-01..08 全闭合（Gate 已 PASS 限域）；T_PHYSICAL_TO_DYNAMIC 桥已冻结哈希钉入（已冻结 `0ACEB659284CAB86…`）；owner 放行。
- release_credit=false；next_stage_authorized=false；review_status=PENDING_OWNER_REVIEW；本文件不带自哈希（SELF_REFERENCE_EXCLUDED，下游消费方钉 sha256，同 e21/V5 惯例）。

## 附录 A：源文件哈希绑定（sha256 全 64-hex，本代理 2026-08-23 实测复核）

| 文件 | sha256 |
|---|---|
| `30_simulation/sim_11_coupled_dynamics/src/coupled_dynamics.py` | `B8727041872802CC6BB62A4977BF3393B328754BAE0959622ADA6F32B534FDD7` |
| `30_simulation/sim_11_coupled_dynamics/src/contact_window.py` | `D6AD26E3F8DAFADA3812689C050EF77AC8A8185F6600118B1F938B4386E98626` |
| `30_simulation/sim_11_coupled_dynamics/src/capture_solver.py` | `C5217AFB39339344DCFF1C17FA03A5A57D452E5939F213FC3D025BA7CD16EC1A` |
| `30_simulation/sim_11_coupled_dynamics/src/ffr_panel.py` | `CCD56EEC234625B180BE5CAEF0F935F5326C663E6754FA09E3CBD020512AFFCF` |
| `30_simulation/sim_11_coupled_dynamics/src/config_loader.py` | `716B92618DADF72D6BC7B7A47DBFAF9B48EA740162A33A5713EF2DA4145F3391` |
| `30_simulation/sim_11_coupled_dynamics/src/run_gates.py` | `F6337FB337B19EA3F1C9F1BC9C1CEE0D507814E5CEA8DA9AE9733030B5AA5EF7` |
| `30_simulation/sim_11_coupled_dynamics/src/scene_a1_arm_slew.py` | `2910142E70A47BAC99C32FBB06DE2F38A3C81A0BB6EAD1D0D4E19D8B8500D9F0` |
| `30_simulation/sim_11_coupled_dynamics/src/scene_a2_capture.py` | `AD1F757EC216BF962616940ECDB8247E763BA98F49E15BEF1E99C563C926209A` |
| `30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json` | `9309F5325271BF5EFDAA7ECAC2BCF20B4FECA3FCA771D22391A7D7D576F9366F` |
| `30_simulation/sim_11_coupled_dynamics/results/sim_11_scene_A1_summary.json` | `3B466DD3B0CA8408666D29445375FE7EB942E939791EED925B34043226A6DA03` |
| `20_engineering/config/coupled_scene/coupled_model_v0.yaml` | `67A532FB29C7EF66229CB41D6D3882946A8454FF37EDD9CF5933E4C91C2663EB` |
| `20_engineering/config/coupled_scene/scene_A1_arm_slew.yaml` | `6E3B53F126F03644EC19F26A4B74911C737E6666DBC89B41A2D0C9D1694C7D3B` |
| `20_engineering/config/coupled_scene/scene_A2_capture.yaml` | `4B979A1DFD183AD938D79D6EB05A8FB0D4164C0E075A5391B467CC50E173A707` |
| `20_engineering/config/mission_feasibility/scan_v0.yaml` | `856F1E30DE47CA5B3F505F9FE5BD5CD22A75E448EC916B42D9C330F7A62E28EA` |
| `20_engineering/config/strategy_feasibility/strategies_v0.yaml` | `D29FB152CFDDBF22BF991BB2595E837F2BEB4C4982E023D04E94DE9A27E01AA8` |
| `30_simulation/sim_10_mission_feasibility/src/feasibility_core.py` | `A4F0FD47B91CFB60CA58FC1F8A8279F5139D7C8A9D77869E6A18100FA00D944A` |
| `30_simulation/sim_10_mission_feasibility/README_sim_10.md` | `FA8B10C49CD3FB4D08F25AFECE44BB8FB1410B6B6E5F92AE1BA007133684BFC8` |
| `30_simulation/sim_12_strategy_feasibility/src/strategy_eval.py` | `188C9D26CBC54F83070E99124D8C502B0B50131D3FD2F53CDAB52CAA32967837` |
| `30_simulation/sim_12_strategy_feasibility/results/strategy_results.csv` | `F538676005CE8CE899BEB8956B33EE75458B18A207AD06FCACAA8B59AEC42DE6` |
| `30_simulation/common/capture_impulse.py` | `DB0AEFBD35032268BC38BC8A18C0A8AFE7BDF9208BE6ACFBC8E2F4B58F9AE089` |
| `30_simulation/e15_core_coverage/config/threshold_registry_core_v1.yaml` | `75AF082AB45A4029C753978686A41CF1DC49B72EE9418CF2E0F1127126D71C82` |
| `30_simulation/sim_06_capture_impulse/results/capture_impulse_matrix_v0.csv` | `8CBAD84B8FF69FFCA6992CE29E95520BAE3C309260EC8C55083CBE62DFED5151` |
| `30_simulation/e15_ancf_certification/results/gate_summary.json` | `AAB4D609E219279C2563C8A38743AC1784BBF16DE399D5B8798439B0AC2DCA80` |
| `30_simulation/e15_ancf_certification/config/certification_v1.yaml` | `8C9F283B3444B948C42B9A649FE86E2E777F525CDCC0E0EB2C09F2D7AD60E788` |
| `30_simulation/sim_05_free_floating_arm/README_sim_05.md` | `181EBA2721E765E6B9588EDC17464219690885C4910FB9248F055ED93523CAF3` |
| `30_simulation/sim_05_free_floating_arm/dynamics.py` | `86C512DFFC9AEC2C7840F4AF3E1A7380F613D302A56C9021F10BDB40F0D705E9` |
| `30_simulation/sim_05_free_floating_arm/b601_model.py` | `3E2B451476F437E482661E275073249AD101705251B78C042851C32AE741052F` |
| `30_simulation/sim_07_ancf_flexible/sim_07a_task_response.py` | `AA559E84C092C4445690B62F360860C82F7B393C2E5B53344E2BBBAE44CE8AA3` |
| `30_simulation/sim_07_ancf_flexible/README_sim_07a.md` | `02C321A85D768B843C403F4CBD61163B4199AAEA4A589CD40E922D62763F9205` |
| `30_simulation/sim_07_ancf_flexible/results/task_response_summary.csv` | `DF29073BDB6CAD1FCE21BF7D22CE5FAC487230631DBE844411565A49D029A33B` |
| `30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/src/build_e21_diagnostics.py` | `7EC0B2ADA7EDCD5E7F34F7E7857A9F0147A1FF633D3EC2227E939C2C62903792` |
| `30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results/E21_DIAGNOSTIC_GATE_V1.json` | `B03B7C7AF571AA00FE3612756FFBBD99CB834B84377BA8DC2C213355C252616B` |
| `30_simulation/e21_m7_r2_arm_placement_rigid_coupled_diagnostics/results/E21_FIXED_BASE_R2_ROM_REPRODUCTION_AND_MASS_CONFLICT_V1.json` | `57958A9F3AC194893D689E9ECA4F12666474D97E0CFBB848ACBA794838B8396B` |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/FLEXIBLE_APPENDAGE_R2.yaml` | `A04ACFE440C636BB095585C74F71E3563FD35F6678FCFAA39355383A9BF6B3FD` |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/FLEXIBLE_APPENDAGE_R2_MODES.json` | `E068DE078A0DC680A44807516733FDF018DD720B5F65636BB2B8D21E557593B6` |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json` | `D5B7DD16532FE7117D27ECC09EFB29ECC570F51928BDBDF3B27BB96C3CF12C5E` |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/compute_flexible_appendage_r2.py` | `2B64A18605ABBD1F79648398A161DDD4D7BCB07665C5D8623B1A34440C1E9BF4` |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/decisions/ENG_DECISION_DYNAMIC_MASS_ALLOCATION_V1.yaml` | `9CCE829E1581B190C6FC50BAE56C47659C61319052268E7C9DFD25FAC8B8C9E4` |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml` | `0ACEB659284CAB862BA65228C5C2DF4BEB06D9EE05B5E2F0B2B5CB38402BF72C` |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/r2_flex_prep/R2_ROM_PARTICIPATION_DAMPING_SPEC_DRAFT_V1.md` | `E3453EFBFF644FA499AD2453E63621F710AC2B0BDB6F56798AA2B0D14B929E18` |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/r2_flex_prep/E15_RECERTIFICATION_TEST_SPEC_DRAFT_V1.md` | `FBC90E00C5C2775635B0ECAFA53C3A9F54F82E61B756F9A00EAA8B64633DA369` |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round0_handover/03_r2_flex_inputs/R2_FLEX_INPUT_INVENTORY_V1.json` | `82DED34930694831AE9A03C1F6E1888C7B4577BA27F17098BBAFA8C16E4A00AD` |
| `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/08_gate/MPI_BRIDGE_GATE_V1.json` | `60911E3C88387E2ED53601F2B541649BF90D689C57C4E74225226AE6FD10C721` |
| `20_engineering/config/geometry/target_models_v1.yaml` | `45666D9D37460FD825F0ED7301BF69113016689FDF00A13DFF8046358A76AE45` |
| `20_engineering/config/geometry/frame_tree_v1.yaml` | `958BFF23BF83434C773854FD0E78DA3B09BE4A3A213EB81A0741514750B3E55B` |
| `20_engineering/config/geometry/flexible_appendage_v1.yaml` | `52FA88084C628CE8845E05DE0C0A892BCA5347B7146C8D1C6B99093927153786` |
