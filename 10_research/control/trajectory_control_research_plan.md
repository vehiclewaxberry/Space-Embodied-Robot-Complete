# control_01_end_effector_tracking 研究计划（规划文档，未实现）

> **2026-07-20 执行状态覆盖**：本文件保留为预注册历史；当前 machine verdict
> 为 `REPEAT`，CP6 已按真实负结果收口但未改写 verdict。以
> `30_simulation/control_01_end_effector_tracking/results/control_01_gate_check.json` 和
> `10_research/partner_requirement_closure/wave1_repeat/wave1_cp6_ruling.md` 为准。

> 版本 v0.1（2026-07-19）。本文档为**只读规划产物**：不改动、不新建任何 sim 代码。
> 实现阶段开工前须由 PI 批准本计划并冻结预注册项（阈值、控制周期、95 分位口径）。
> 证据基线：`10_research/partner_requirement_closure/state_truth_report.md`（Gate A0 PASS，
> HEAD 246673e）——"末端轨迹闭环控制 NOT_STARTED"即本模块要闭合的缺口。

---

## 0. 设计原则（先于一切方法选择）

1. **第一版必须保留可解释的 resolved-rate（分辨运动率）基线**。禁止直接选用
   "最先进控制器"（MPC、学习类、自适应滑模等一律不进 v1）。理由：
   （a）本项目科学主张的可信度建立在逐级机器裁决之上，控制律每一项都必须能
   写成闭式表达并被独立复算；（b）resolved-rate + 广义雅可比是自由漂浮空间
   机器人文献的公认参照系（Umetani & Yoshida 1989），C0→C3 的每一步增量都
   对应一个可单独证伪的物理假设；（c）先进控制器留给 control_02+，且必须以
   本模块的 C1 为对照基线。
2. **复用已冻结资产，不重造轮子**：
   - 动力学真值 = `30_simulation/sim_11_coupled_dynamics/src/coupled_dynamics.py`
     （`SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS`）；J* 已实现为
     `generalized_jacobian(th, eta)`，6×(6+2m) 帆板增广形式
     `J* = [J_m, 0] − J_b H_bb^{-1} H_bm`，输出 S 系末端空间速度；
     A1 收尾位形的 J* 数值已在
     `30_simulation/sim_11_coupled_dynamics/results/sim_11_scene_A1_summary.json`
     （`generalized_jacobian_Jstar_at_qf`，6×12，m=3 模态/帆板）。
   - 运动学/限位/奇异性诊断 = `30_simulation/sim_09_grasp_evaluator/src/ik.py`
     （多起点 DLS、URDF 限位单源自 sim_05 `b601_model`、奇异值/条件数/秩/零度
     诊断、approach_5d 五维任务行与 `B601Arm.J5` 同一构造）。
   - 轨迹形函数 = sim_05 `min_jerk`（10-15-6 五次多项式，端点速度加速度为零），
     与 A1 场景卡 `20_engineering/config/coupled_scene/scene_A1_arm_slew.yaml` 的
     `quintic_10_15_6` 同一多项式——退化锚点因此可逐位对拍。
3. **fail-closed 机器裁决**：科学结论只认 `results/control_01_gate_check.json`；
   tests PASS ≠ Gate PASS；任何占位参数（帆板 0.348 kg、T_c=20 ms）随裁决 JSON
   显式携带 `PROVISIONAL_PARAMS: true`。

---

## 1. 科学问题与研究对象

**科学问题**：在自由漂浮零动量、带柔性帆板的 12U 服务星上，B601 6R 机械臂末端
跟踪抓取相关轨迹时，"是否使用/如何使用广义雅可比 J*"对末端跟踪精度、基座姿态
扰动与帆板激振的影响能否被定量分离，并给出误差有界性的可论证条件？

**这不是控制器调参竞赛**：四方法是四个物理假设的阶梯，输出是"每一级假设值多少
误差/多少反作用"的机器证明，供 Paper 1（柔性耦合捕获任务可行域）的控制章节引用。

---

## 2. 四方法对比（C0–C3，全部 resolved-rate 级，速度指令接口）

统一控制律骨架（离散周期 T_s，ZOH）：

```
θ̇_cmd(k) = pinv_λ(J_ctrl(k)) · [ ẋ_ff(k) + K_e · e(k) ] + N(k) · ζ(k)
```

其中 `pinv_λ` = 阻尼伪逆（DLS，λ 自适应下限固定，复用 sim_09 的 Levenberg 风格），
`e(k)` = 任务空间误差（位置 + 姿态旋转矢量 / 或 approach 五维误差），
`N(k)` = 零空间投影（仅 C3 非零），各方法差异只在 `J_ctrl / ẋ_ff / N·ζ` 三项：

| 方法 | J_ctrl | 前馈 ẋ_ff | 零空间 N·ζ | 检验的物理假设 |
|---|---|---|---|---|
| **C0** 固定基座几何雅可比 | `B601Arm.jacobian(θ)`（J_m，视基座为惯性固定） | 0（纯反馈）| 0 | "地面装调习惯直接上天"的代价基线；预期系统性漂移 |
| **C1** 自由漂浮 J* 分辨运动率 | `generalized_jacobian(θ,η)` 取关节列块 J*_θ (6×6) | 0（纯反馈）| 0 | 零动量流形上 J* 是否足以消除 C0 的模型性漂移（**本模块可解释主基线**）|
| **C2** J* + 基座运动前馈 | 同 C1 | ẋ_ref^I 旋回 S 系 + 基座运动预测校正（V_b_pred = −H_bb⁻¹H_bm[θ̇;η̇]）；消融 C2b：再加帆板速度补偿 −J*_η η̇ | 0 | 前馈能否把"跟踪滞后 ∝ 目标速度/K_e"降为二阶小量 |
| **C3** J* + 反作用零空间 | 同 C1，任务降维为 approach_5d（m=5，零度≥1，行构造与 sim_09 `residual_and_jacobian` 逐位一致）| 同 C2 | ζ = −k_r ∇_θ̇ ‖H_bb⁻¹H_bm,θ θ̇‖²（瞬时基座反作用代价梯度），N = I − J⁺J | 冗余度换基座安静度：跟踪不劣化前提下反作用可降多少 |

**C3 的诚实声明（预注册）**：B601 为 6R，pose_6d 任务下 nullity=0，反作用零空间
不存在；因此 C3 只在 approach_5d 任务口径下定义（与 sim_09 已验证的 J5 任务同构，
抓取物理上放开滚转自由度是合理的）。若 T2 需要完整姿态同步，C3 在该轨迹上标记
`NOT_APPLICABLE` 而非硬造冗余。sim_05 已输出 `|H_bm·q̇|` 时程并在其 docstring 中
预留为"reaction-minimizing trajectory work 的基线信号"——C3 直接对接该信号口径。

**明确排除（v1 不做）**：力矩级控制、动量轮/推力器协同、非零动量（抓取后）工况、
接触阶段控制、任何学习/预测控制器。

---

## 3. 三条参考轨迹（T1–T3）

所有轨迹在任务空间定义（末端位姿），关节侧不预置答案；形函数统一 10-15-6。

| 轨迹 | 定义 | 时长 | 锚点关系 |
|---|---|---|---|
| **T1 预抓取** | 末端从收拢位形 FK(θ=0) 到预抓取位形 FK(θ=[0,60°,−40°,0,0,0]) 的任务空间五次多项式；位姿六维 | 8 s 机动 + 4 s 保持（与 sim_05/A1 同）| 参考路径由 A1 已裁决的 θ(t) 经 FK 生成 ⇒ pose_6d 无冗余下闭环解唯一，构成退化锚点（§6 Gate C-A）|
| **T2 移动目标同步** | 跟踪翻滚目标星抓取点：`target_propagation` const_omega 传播（sim_09 现成模块），ω=1.3872°/s（sim_10 卫星锚点 μ=0.917 口径），抓取点保持在 `capture_point_S=[0.95,0,−0.10]` 附近工作区（sim_09 D 卷宗约定，避开腕部奇异）；位置 + approach 轴同步 | 30 s | 与 sim_10 WHEELS_ONLY 可行域锚点同一目标参数；不允许改用碎片 3°/s（那是 INFEASIBLE_RATE 区，留给 abort 研究）|
| **T3 紧急后退** | 从 T2 中途触发：沿 −approach 轴退 0.5 m，3 s 内完成，端点速度为零；触发时刻预注册（t=15 s）| 3 s + 2 s 保持 | 对应 sim_12 B/D 区 ABORT 策略的执行层；后退过程基座扰动是 abort 成本的一部分 |

---

## 4. 控制问题的完整定义（预注册项）

- **状态变量**：真值仿真态 `y = [r_b(3), quat(4), θ(6), η(6), η̇(6)]`，零动量流形
  上由 sim_11 `integrate_reduced` 同款约简积分推进（基座速度由动量矩阵解出，
  不独立积分）。控制器可见态 v1 = **理想全状态反馈**（θ, quat, η, η̇ 无噪声、
  无延迟）——这是预注册的理想化假设，写入 claim 边界；测量模型留 control_02。
- **控制输入**：关节速度指令 θ̇_cmd（6 维，ZOH），即速度伺服假设。关节力矩不是
  输入，但每步用 `accelerations()`（θ̈ 由 θ̇_cmd 差分限带获得）反解 τ 作为指标
  与限幅审计（超限 → Gate C-4 FAIL，不做饱和续跑掩盖）。
- **J* 使用位置**：仅在控制律的 `pinv_λ(J*_θ)` 与 C2 的 V_b 预测、C3 的反作用
  梯度三处；真值传播**不用** J*（真值走全量质量矩阵/动量矩阵），保证"控制器
  模型=J*、被控对象=全耦合模型"的正规分层，避免自证清白。
- **前馈项**（C2/C3）：`ẋ_ff = R_S^T·ẋ_ref^I − J*_η η̇ (C2b) `，其中参考在惯性系
  定义、旋回 S 系（J* 输出为 S 系末端速度，帧变换是 C0 常犯错误源，单列测试）。
- **零空间目标**（C3）：min 瞬时基座角动量转移率 ‖(H_bb⁻¹H_bm)_ang,θ · θ̇‖，
  梯度闭式可写（二次型），k_r 扫掠 3 档预注册。
- **控制周期**：名义 T_s = 10 ms（100 Hz），扫掠 {5, 10, 20, 50} ms。依据：帆板
  一阶模态 1.0005 Hz（A1 已测）远低于 Nyquist；T_c=20 ms 接触窗（PROVISIONAL）
  要求控制周期至少同量级；结果须报告 T_s 敏感性而非单点。
- **参考轨迹**：§3；全部以解析形函数给出（无插值表），保证逐位复现。
- **误差有界性论证途径**（三级，逐级机器验证）：
  1. 连续时间理想 C1：ė = −K_e e + d(t)，d 含目标加速度、J* 模型残差
     （真值为全耦合、控制器为 J* 的差）、DLS 阻尼偏置（‖bias‖ ≤ λ‖ẋ‖/(σ_min²+λ)）；
     ISS ⇒ ‖e‖_∞ ≤ ‖d‖_∞/λ_min(K_e) + 指数衰减项。给出各 d 分量的解析上界。
  2. 采样保持修正：+O(T_s)·(‖ẍ_ref‖+‖K_e ė‖) 项，随 T_s 扫掠数值验证斜率。
  3. 机器验证：每条轨迹每方法的实测 ‖e‖_∞ 必须落在解析界之内（界不紧允许，
     越界 = 论证链或实现有错，Gate C-5 FAIL）。

---

## 5. 全指标清单（每方法 × 每轨迹，全部入 CSV + summary JSON）

| 组 | 指标 | 符号/口径 |
|---|---|---|
| 末端跟踪 | 位置误差 | ‖e_p(t)‖：RMS、max、**95 分位**（p95 口径预注册：对时间序列取分位，不重采样）|
| | 姿态误差 | 旋转矢量范数 ‖e_R(t)‖（T1/T2 pose 口径）或 approach 轴夹角（5d 口径）：RMS、max、p95 |
| 基座 | 姿态峰值 | dev_angle 峰值 [deg]（与 sim_05/A1 同一四元数总转角口径）|
| | 角速度积分 | ∫‖ω_b‖dt [deg]（基座"累计晃动量"，C3 的主收益指标）|
| 关节 | 速度/加速度 | max‖θ̇‖∞、max‖θ̈‖∞ vs 限值（URDF SSOT；速度/加速度限值现无 SSOT → 占位并标注）|
| | 力矩 | max‖τ‖∞（`accelerations()` 反解，审计口径）|
| 奇异性 | 奇异裕度 | min σ_min(J_ctrl)、max cond(J_ctrl)、限位裕度 min(θ−lo, hi−θ)（sim_09 `_diagnose` 同口径）|
| 帆板 | tip 位移 | tip_L/tip_R 峰值 [mm]（A1 口径，锚点 0.106 mm 量级）|
| | 模态能 | E_modal 峰值与末值 [J]（PROVISIONAL_PARAMS 标注强制携带）|
| 守恒审计 | 动量/能量 | max|ΔP|、max|ΔL|（独立路径 `momentum_inertial`）、能量审计相对残差 |
| 算力 | 算时 | 每控制步壁钟 [ms]（均值/max）、实时率 = T_s/步算时；排除出 canonical 对拍（同 sim_09 wall_time 处理）|

---

## 6. 机器 Gate 设计（fail-closed，单一裁决 JSON）

裁决文件：`30_simulation/control_01_end_effector_tracking/results/control_01_gate_check.json`
（实现阶段产物；目录当前不存在，本计划不创建）。总 verdict 命名
`CONTROL01_GATES_PASS`；任一子 Gate FAIL ⇒ 总 FAIL，禁止摘取子结论。

- **Gate C-A 退化锚点（先于一切对比）**：
  - C-A1 开环复放：θ̇_ref 直接由 A1 的 θ(t) 微分给出（旁路控制器），全柔性
    模型下基座姿态峰值 vs `sim_11_scene_A1_summary.json` 的
    **19.199885629572467°**，容差 ≤1e-6°（同一积分器应逐位级）。
  - C-A2 闭环复现：C1 + pose_6d 跟踪 T1（参考=A1 末端路径），零初始误差；
    6R 无冗余 ⇒ 关节轨迹应回到 A1 解：基座姿态峰值落入 19.20° 锚带
    （预注册 |Δ|≤0.05°，闭环瞬态预算），末端 p95 误差 ≤ 预注册阈值。
  - C-A3 帆板刚化开关：同 C-A2 刚化后峰值 vs sim_11 G3b 的
    **19.199850770410567°**（即 sim_05 19.20° 口径），|Δ|≤0.05°。
- **Gate C-B 守恒**：全部闭环运行 max|ΔP|、max|ΔL| ≤ 1e-12（sim_11 实测
  7.6e-17 量级，阈值留 4 个量级裕度）；能量审计残差 ≤ 1e-9。
- **Gate C-C 分化机器证明**（sim_12 GS2 同风格）：C0 vs C1 在 T2 上的末端 p95
  误差必须统计可分（C0 漂移项存在且方向与 J_b H_bb⁻¹H_bm 预测一致）；若 C0
  与 C1 不可分 ⇒ 要么扰动太小（场景失效）要么实现有错，均 FAIL。**预注册
  承诺：若 C1 不优于 C0，如实裁决并发布**，反向结果同样是科学结论。
- **Gate C-D 增量有效性**：C2 相对 C1 的 T2 p95 误差改善 ≥ 预注册比例（首轮
  预注册 30%，理由：滞后项 ∝‖ẋ_ref‖/K_e 应被前馈近乎消除）；C3 相对 C1（同
  5d 任务口径）基座 ∫‖ω_b‖dt 下降且末端 p95 不劣化超过 10%。
- **Gate C-E 约束合规**：全程限位裕度 >0、σ_min ≥ 预注册下限、τ ≤ 占位限幅
  （占位来源写明）；T3 全程无碰撞（复用 sim_09 collision 走廊口径）。
- **Gate C-F 有界性闭环**：§4 第 3 级——实测误差 ≤ 解析界，逐轨迹逐方法。
- **哈希锁**：所有输入参数卡与输出 CSV 入 SHA-256 清单（sim_10/11 同制度）。

---

## 7. B601 未来验证边界（claim 纪律）

- 本模块一切结论**只可称"地面组件级验证"候选**：B601 硬件资格 H0–H3 未开始
  （state_truth_report 第 8 项），速度伺服带宽、关节速度/力矩限值、夹爪 T_c
  均为占位。禁止任何"在轨可用/飞行验证"表述。
- 帆板参数为 SSOT 占位（0.348 kg，真实差 5–10 倍，待办 3）：帆板相关指标只做
  **方法间相对比较**，绝对 mm/J 数值不进论文正文主张；杨恒参数卡到位后全部
  Gate 重跑（与 sim_11 待办 1 同一触发器）。
- 未来地面验证路径（仅列口径，不承诺）：B601 固定基座跑 C0 轨迹层（运动学层
  可地面验证）；自由漂浮部分只能以仿真+守恒审计背书，气浮台不在本项目范围。

---

## 8. Task Card

```yaml
task_id: control_01_end_effector_tracking
scientific_question: >-
  自由漂浮柔性航天器上，广义雅可比 J* 的使用层级（不用/反馈/加前馈/加反作用
  零空间）对末端跟踪误差、基座扰动与帆板激振的定量影响及误差有界条件。
hypothesis:
  H1: C0 在 T2 上存在与 J_b·H_bb^{-1}·H_bm 预测方向一致的系统性漂移，C1 消除之。
  H2: C2 前馈将 T2 跟踪 p95 误差相对 C1 降低 ≥30%（滞后项被前馈抵消）。
  H3: C3（5d 任务）在末端误差不劣化 >10% 前提下降低基座 ∫|ω_b|dt。
  H4: 各方法实测误差均落在 §4 的 ISS 解析界内。
baseline: >-
  C1（自由漂浮 J* resolved-rate，可解释闭式基线）；C0 为对照下界；
  退化锚点 = sim_05 19.20° 与 sim_11 A1 19.199885629572467°。
owned_paths:
  - 10_research/control/trajectory_control_research_plan.md   # 本文档
  - 30_simulation/control_01_end_effector_tracking/**                # 实现阶段新建
  - 20_engineering/config/control_scene/**                                # 实现阶段新建参数卡
forbidden_paths:
  - 30_simulation/sim_01..sim_12/**（含 results；只读引用与 import）
  - 30_simulation/sim_09_grasp_evaluator/src/**（只读 import ik/collision/target_propagation）
  - 20_engineering/config/geometry/**, 20_engineering/config/coupled_scene/**, 20_engineering/config/mission_feasibility/**
  - 一切已冻结裁决 JSON 与哈希清单
metrics: 见 §5 全表（末端 p95 为主指标；基座 ∫|ω_b|dt 为 C3 主指标）
machine_gates: [C-A1, C-A2, C-A3, C-B, C-C, C-D, C-E, C-F, hash_lock]  # §6
red_team_questions:
  - C0 是否稻草人？（答辩口径：C0=地面装调默认做法，其漂移幅值本身是结论）
  - pose_6d 下零空间不存在，C3 换 5d 任务是否偷换比较口径？（C1/C3 对比强制同口径重跑）
  - 理想全状态反馈是否夸大所有方法性能？（写入 claim 边界，测量模型延后）
  - 真值与控制器共享同一几何/惯量 SSOT，模型误差敏感性谁来证？（留 control_02 摄动实验，v1 声明）
  - DLS 阻尼下限与奇异裕度 Gate 是否互相掩盖？（λ 固定预注册，禁止按轨迹调）
  - p95 阈值是否赛后拟合？（本文档冻结数值后方可开跑，改阈值=重新预注册）
  - 帆板占位参数下"帆板指标"是否可发表？（只允许相对比较，见 §7）
  - T2 站保假设（抓取点保持在工作区）是否把最难部分假设掉了？（是——追逃/交会
    不在本模块 scope，claim 中限定"抓取窗内同步段"）
  - θ̈ 由 θ̇_cmd 差分反解 τ 是否低估峰值力矩？（差分限带口径预注册并做 T_s 敏感性）
stop_condition: >-
  （a）Gate C-A 任一锚点两轮修复后仍 FAIL → 停，升级为"J*/积分器不一致"模型
  问题，禁止调增益绕过；（b）实现+验证超 2 周未达 C-A → 收缩为仅 C0/C1 两方法
  重新报批；（c）杨恒真实帆板参数到位 → 暂停发布，全 Gate 重跑。
rollback: >-
  删除 owned_paths 新建目录即可完全回滚；不触碰任何 SSOT/已冻结裁决；本计划
  文档保留并记录 FAIL 裁决（负结果入库，不删历史）。
claim_allowed:
  - "占位帆板参数与理想状态反馈假设下，四方法在三类抓取轨迹上的相对排序与机器证明"
  - "C0 固定基座假设的漂移幅值 = 自由漂浮建模必要性的定量证据"
  - "resolved-rate + J* 闭环的误差有界性论证链（解析界+数值验证）"
  - "B601 运动学层结论 = 未来地面组件级验证候选"
claim_forbidden:
  - 在轨性能/飞行验证/工程可用性表述
  - 帆板绝对振动幅值与模态能的硬件意义（PROVISIONAL）
  - "最先进/最优控制器"表述；任何未与 C1 基线对比的先进方法结论
  - 抓取后（非零动量）与接触段控制结论（J* 零动量前提之外）
```

---

## 9. 实现阶段排期建议（供 PI 裁量，非承诺）

1. 步骤 1：轨迹生成器 + C-A1 开环复放锚点（不含控制器）——先锁积分与帧约定。
2. 步骤 2：C1 + Gate C-A2/C-A3/C-B —— 基线成立才有后续。
3. 步骤 3：C0 + Gate C-C（分化证明）；4：C2 + C-D 前半；5：C3（5d 口径）+ C-D 后半；
   6：T_s/k_r 扫掠 + C-F 有界性 + 哈希锁 + tests + 裁决 JSON。
