# ASM-02 分阶段装配控制研究计划（规划稿，未实现）

> 版本 v0.1（2026-07-20）。**只读规划产物**：不改动、不新建任何 sim 代码；实现开工前须
> PI 批准并冻结全部预注册项（权重、切换判据、阈值、场景集）。
> 证据基线：`10_research/on_orbit_assembly/state_truth_and_scope.md`（Gate AG-A0 PASS，
> HEAD 738348e）；Gate 归属见 `10_research/on_orbit_assembly/gate_registry.yaml`
> （AG1/AG3 owner = ASM-02）；接口参数唯一来源
> `10_research/on_orbit_assembly/interface_ssot_draft.yaml`（全字段 PROVISIONAL/LITERATURE）。

---

## 0. 定位与边界

- **回答的问题**：12U 服务星 + B601 将 1U 模块安装到目标星预制接口（锥面粗对准→
  插销精对准→锁扣）的**控制相位结构**——"一个 6D 任务从头跟到尾"与"分阶段
  （5D 接近→阻抗接触→短程 6D 锁定）"哪个在冻结证据约束下失败率更低、代价几何。
- **证据基础 = CTRL-01 七项真实负结果**（`30_simulation/control_01_end_effector_tracking/results/control_01_gate_check.json`，
  verdict REPEAT，CP6 方案 B 文档化收口）。本计划把它们当**设计约束**而非待修缺陷：
  1. 冻结增益闭环锚超差：GC1_A2 Δ=0.15504° > 0.05°（C2_T1 诊断 0.00645° 把残差归
     因于冻结增益反馈滞后物理）→ **单一 6D 全程任务在冻结增益下不满足锚带**，
    分阶段语义正是对该负结果的结构性回应（state_truth_and_scope.md 第 17-18 行）。
  2. C3 孤立零空间真零：C3 vs C2_MATCH5 基座速率改善 **+1.84e-5%**（阈值 5%）→
     **禁止把"零空间省反作用"当作装配相位的预期收益**；5D 段的 1 维零空间只用于
     约束回避（限位/奇异裕度），不承诺反作用红利。
  3. C2 前馈位置负增量 −38.26%（阈值 +30%）→ 前馈不是免费午餐，装配相位内
     前馈项按消融对照进入，不进 headline。
  4. GC1_F 有界性违例（C1_T3 p95 0.1902 m > 0.11 m）→ 快速大范围机动段（RETREAT
     类）不承诺跟踪界，容差链由**锥面捕获域（粗 5 mm/5°）吸收**，不苛求跟踪精度
     （风险 AR4 的缓解即此）。
  引用上述任何数字**必须带限定句式："冻结增益与预注册轨迹下"**。
- **与兄弟模块边界**：ASM-01 管接触动力学基建（KV 接触、卡滞判据、动量/能量账本，
  AG2/AG4）；ASM-02 只消费其接触模型接口。SAFE-00 裁决核**只读复用**，装配新增
  reason_code 属扩展不改核（AG5）。动力学真值 = `30_simulation/sim_11_coupled_dynamics/src/coupled_dynamics.py`
  只读 import：`generalized_jacobian(th, eta)` 给 6×(6+2m) 的
  J* = [J_m, 0] − J_b H_bb⁻¹ H_bm（S 系末端速度）；H_bm 取 `momentum_matrix` 关节列块。
- **明确排除**：RL/VLA 力矩输出、学习控制器、大桁架装配、非预制接口、
  追逃/交会段；控制器不得改变可行域（sim_10 铁律继承）。

## 1. 科学问题

**在冻结增益纪律、冻结执行器档与 PROVISIONAL 接口参数下，装配任务的相位分解
（任务维度 3/5/混合/6 的切换结构）能否被机器证明降低失败率，且每一相位的任务
维度语义、切换判据与资源代价可逐项裁决？** 输出不是"最优装配控制器"，是
**相位结构 × 失败率 × 代价**的机器证明集。

## 2. 四基线 AC0–AC3 与相位语义（严格任务维度纪律）

### 2.1 相位词表映射（主场景冻结的技能词表 → 控制相位）

| 相位 | 技能词 | 任务维度 | 零空间 | 控制语义 |
|---|---|---|---|---|
| P0 远场转移 | MOVE_TO_PREASSEMBLY | **position_3d**（3 维）或 approach_5d | 3 或 1 维 | 位置走廊跟踪，姿态不约束或仅 approach 轴 |
| P1 接近 | APPROACH_5D / ALIGN | **approach_5d**（5 维，行构造与 sim_09 `residual_and_jacobian`/`B601Arm.J5` 逐位一致） | **1 维**（nullity=1 机器校验） | 位置 + approach 轴同步；零空间只做限位/奇异回避 |
| P2 接触插入 | COMPLIANT_INSERT | **混合 5 维**：切向位置 2 + 姿态 2（绕两切轴）+ **法向阻抗**（力目标，非位置） | 1 维 | 切向位置伺服 + 法向目标力 F_n_ref 阻抗（K_d, D_d 预注册），摩擦/卡滞由 ASM-01 判据监测 |
| P3 锁定 | LOCK_6D | **pose_6d 短程**（6 维） | **0（允许）** | 允许条件三件套：短程（‖Δx‖≤d_lock 预注册，量级 = 插入深度 12 mm 内）+ 低速（≤v_lock）+ **SAFE-00 预授权**（HMAC 授权 token 在场，相位切换=重新裁决） |
| P4 核验/撤离 | VERIFY_ASSEMBLY / RETREAT | position_3d（撤离沿 −approach 轴） | ≥1 维 | 撤离段不承诺跟踪界（负结果 4 继承） |

**铁律**：6D 段 nullity=0 是**合法状态而非缺陷**，但只在 P3 的三条件下合法；
任何在 P0–P2 用 pose_6d、或在 P3 注入零空间项的实现 = AG1 FAIL。

### 2.2 四基线定义

| 基线 | 相位结构 | 检验的假设 |
|---|---|---|
| **AC0 全程 6D** | P0→P4 全程 pose_6d 跟踪单一参考轨迹（无相位切换、无阻抗） | 对照下界："单一 6D 任务"在冻结增益下的失败率——CTRL-01 负结果 1 预测其在接触/精对准段超差（预注册预测 PA-1） |
| **AC1 5D→6D** | P0/P1 按 5D 语义，P2 跳过阻抗（位置直插，法向也是位置伺服），P3 按 6D | 相位任务降维本身（不含柔顺）值多少失败率 |
| **AC2 5D→阻抗→6D** | 完整 P0–P4 语义（P2 法向阻抗混合） | 接触柔顺的增量：接触力峰值/卡滞率/失败率相对 AC1 |
| **AC3 AC2+基座轮组柔性协调** | AC2 + 轮组前馈-反馈协调（CTRL-02 A2 架构的**限力矩版**，§6）+ 帆板激振代价项 w_f | 基座-臂-轮协调在**统一力矩档**下的真实增量（W1-R12 解决后才有意义） |

四基线共用同一 QP 骨架（§3），差异只在相位表、阻抗开关与轮组通道，保证增量归因。
AC3 的轮组交换严格记 INTERNAL（动量账本铁律继承，`10_research/sim_12/momentum_ledger.md`）。

## 3. 约束 QP 最小实现形式（每控制周期 T_s 解一次，速度级）

决策变量 z = [θ̇(6); u_w(3)（仅 AC3，轮力矩）]，目标函数（预注册权重）：

```
min_z  w_e‖J_task(θ,η)θ̇ − ẋ_d‖² + w_b‖(H_bm θ̇)_ang + h_w_dot‖²
     + w_f Ê_flex(θ̇) + w_u‖u_a‖²
```

- **J_task**：按相位取行——P0 取 J* 位置行（3×6）、P1 取 J5 五维行、P2 取切向
  4 行（法向由阻抗外环给 ẋ_d 法向分量 = 力误差映射）、P3 取 J*_θ 全 6 行。
  J* 一律来自 `generalized_jacobian` 关节列块（控制器模型），真值传播用全量
  质量矩阵（CTRL-01 的"控制器=J*、被控对象=全耦合"正规分层继承）。
- **w_b 项**：基座反作用代价 ‖(H_bm θ̇)_ang‖²（sim_05 预留信号口径）；AC3 时
  为 ‖(H_bm θ̇)_ang + ḣ_w‖²（轮组吸收后的净反作用）。**不承诺零空间红利**
  （负结果 2），该项是软代价不是硬指标。
- **Ê_flex**：帆板激振率代理 = ‖S_c(θ)θ̇‖²（H_bm 帆板耦合列的二次型）。
  FLEX=UNKNOWN_NOT_IN_CRITERIA 纪律不变：w_f 是设计项，帆板指标只报告不裁决。
- **w_u‖u_a‖²**：执行器用量正则（θ̇ 与 u_w 统一加权）。
- **硬约束**（全部 fail-closed，QP 不可行 → 本步降级为 SAFE-00 BACKOFF 请求，
  禁止松约束续跑）：
  1. 限位：θ_lo + m_q ≤ θ + T_s θ̇ ≤ θ_hi − m_q（m_q=0.05 rad 冻结门）；
  2. 速度：|θ̇| ≤ θ̇_max（URDF/占位，出处标注）；
  3. 加速度：|θ̇ − θ̇_prev|/T_s ≤ θ̈_max；
  4. 碰撞：线性化距离约束 ḋ ≥ −k_c(d − d_min)（sim_09 走廊口径，d_min 预注册）；
  5. 接触力（P2）：F_n ∈ [F_min, F_max]（阻抗外环目标 + QP 法向速率限幅双保险；
     F_max 联动接口 SSOT contact_load_within_limit）；
  6. 轮组容量（AC3）：|h_w,i + T_s u_w,i| ≤ 0.1 N·m·s/轴（箱式包络，冻结档）
     且 **|u_w,i| ≤ τ_w,max（§6 统一档 0.01 N·m）**；
  7. 基座角速率：‖ω_b(θ̇)‖ ≤ ω_b,max（动量关系解析映射，预注册值）；
  8. 模型域：σ_min(J_task) ≥ 1e-4（registry）、cond ≤ 1e4、接触模型域内
     （μ、插入深度、KV 参数扫掠包络内；域外 → UNKNOWN 不判 success）；
  9. 安全授权：本步执行前 SAFE-00 决策 ∈ {ALLOW, MODIFY}；WAIT/BACKOFF/ABORT
     一律覆写 QP 输出（UNKNOWN 永不 ALLOW 继承）。

**权重预注册纪律**（CTRL-01 GC1_G `gains_tuned_on_plant=false` 制度继承）：
(w_e, w_b, w_f, w_u)、阻抗 (K_d, D_d, F_n_ref)、DLS/正则化 λ 下限全部在
`20_engineering/config/assembly_control/asm02_qp_v0.yaml` 冻结并 SHA-256 哈希锁定后方可开跑；
**禁止按场景/按基线调参**（四基线共用同一组权重，差异只准来自相位表本身）；
改任何权重 = 预注册修订（带修订 ID，前值保留）；权重敏感性以附录扫掠呈现，
不得用于事后挑选 headline。

## 4. 相位切换判据与瞬态处理（全部预注册数值，实现前 PI 冻结）

### 4.1 切换判据（迟滞 + 去抖，禁止单采样触发）

| 切换 | 进入条件（全部满足，连续 N_db 个控制周期） | 迟滞退出 |
|---|---|---|
| P0→P1 | 进入预装配走廊：‖e_p‖ ≤ r_corridor 且视线/approach 轴误差 ≤ α_far | e_p 超 1.5× 回退 P0 |
| P1→P2 | **锥面捕获域**：横向误差 ≤ 5.0 mm、角误差 ≤ 5.0°（接口 SSOT coarse 档）且接近速度 ≤ v_touch（PROVISIONAL，量级 mm/s）且（预测接触视界内 或 实测 F_n ≥ F_touch） | 接触丢失（F_n < F_release 持续 N_db）→ 回退 P1 重对准 |
| P2→P3 | 插入深度 ≥ 12 mm（SSOT）且横向精对准 ≤ 0.1 mm / 0.5°（fine 档）且残余速率 ≤ v_lock 且接触力在窗内且**无卡滞**（ASM-01 Whitney 判据未触发） | LOCK 超时 t_lock,max → BACKOFF |
| P3→P4 | latch_state=LOCKED 且电源/数据状态位 CONNECTED（状态机模拟） | — |
| 任意→BACKOFF/ABORT | SAFE-00 非 ALLOW/MODIFY、QP 不可行、卡滞判据触发、任何 UNKNOWN | 只准后退（P_k→P_{k−1} 或 RETREAT），**禁止跳级前进** |

### 4.2 切换瞬态处理（每条都是机器可查项）

1. **参考连续性 C¹**：切换时刻新相位参考以匹配速率的五次多项式收口段衔接
   （CTRL-02 A1 两段式 `quintic_matched_rate_zero_accel` 同款构造），禁止参考跳变。
2. **控制器状态交接**：积分/滤波状态交接策略预注册（默认：误差积分清零 +
   前馈热启动）；切换后 T_blend 内权重线性斜坡（阻抗 K_d 从 0 斜坡进入，
   避免接触瞬间等效冲量伪影——T_blend ≥ 2×T_c=40 ms，T_c=20 ms PROVISIONAL 联动）。
3. **控制周期**：T_s 名义 10 ms ≤ T_c/2，扫掠 {5,10,20} ms 报敏感性。
4. **SAFE-00 相位切换=重新裁决**（AG5 硬规则）：每次切换发起新 safety_request
   （新增装配 reason_code：PHASE_TRANSITION_5D_TO_CONTACT、CONTACT_TO_LOCK6D、
   LOCK6D_PREAUTH 等，扩展词表不改裁决核）；P3 进入必须持有对 LOCK6D 的
   预授权 token（HMAC、not_before/expires_at 界定短程窗）。
5. **账本跨切换连续**：动量/能量账本在切换时刻两侧逐位衔接（≤1e-12/1e-9），
   切换不是账本重置点；接触冲量单列（ASM-01 接口）。
6. **抖振检测**：每次运行相位序列必须匹配预注册合法序列集（前进链 + 显式
   BACKOFF 环），相位切换次数超预算 = AG1 FAIL。

## 5. 机器 Gate 设计（AG1/AG3，fail-closed，单一裁决 JSON）

裁决文件（实现阶段产物）：`30_simulation/asm_02_phased_assembly_control/results/asm_02_gate_check.json`，
verdict 命名 `ASM02_GATES_PASS`；tests PASS ≠ Gate PASS；`PROVISIONAL_PARAMS: true`
强制携带（接口全字段 + T_c + 帆板 + τ_w,max）。

### AG1 运动学相位语义（硬断言）
- **AG1-a 任务维度机器校验**：每个记录节点上，5D 段 rank(J_task)=5 且
  nullity=1；P3 段 nullity=0 且**零空间项恒等于零**（QP 中 w_nullspace 通道
  不存在/系数为 0 的结构性断言 + 运行时 ‖N·ζ‖≡0 数值断言）——"6D 段禁调
  不存在零空间"的两层实现。
- **AG1-b LOCK 合法性证书**：P3 每次进入须落盘三条件证据（‖Δx‖≤d_lock、
  速率≤v_lock、SAFE-00 预授权 token 验证通过），缺一即该 run FAIL。
- **AG1-c 切换点可达性**：每个切换位形 IK 可达且限位裕度 ≥0.05 rad、
  σ_min ≥1e-4（sim_09 `_diagnose` 同口径）。
- **AG1-d 相位序列合法**：见 §4.2 第 6 条。

### AG3 装配控制性能（硬断言）
- **AG3-a 失败率不劣断言**：冻结场景集上
  `fail_rate(AC1) ≤ fail_rate(AC0)` 且 `fail_rate(AC2) ≤ fail_rate(AC0)`
  （逐场景成败机器计数；等于允许）。**预注册承诺：若不成立，如实裁决并发布
  ——"分阶段不优于全程 6D"同样是科学结论**，禁止改阈值/改场景救结果。
- **AG3-b 成功 = 几何 ∧ 力学 ∧ 资源**（接口 SSOT 八判据的机器化）：
  几何（0.1 mm ∧ 0.5° ∧ 深度 12 mm ∧ LOCKED）∧ 力学（接触力窗内 ∧ 无卡滞 ∧
  动量账本 ≤1e-12 ∧ 能量审计 ≤1e-9）∧ 资源（轮箱 ≤0.1 N·m·s/轴 ∧
  |u_w|≤τ_w,max ∧ 无推力器用量——名义装配零推进剂，非零即分配缺陷 FAIL）；
  **任一 UNKNOWN → 不判 success**。
- **AG3-c CTRL-01 负结果口径继承**：裁决 JSON 内置 `claim_qualifier` 字段 =
  "冻结增益与预注册轨迹下"；claim_forbidden 固定含：零空间反作用收益（除非
  新预注册假设独立过门）、前馈普遍有效、跟踪精度普适界、任何不带限定句式的
  CTRL-01 数字引用。
- **AG3-d 归属与守恒**：轮/臂全部 INTERNAL_REDISTRIBUTION 机器标注
  （|ΔH_ext|<1e-12 → INTERNAL，禁止手写）。
- **AG3-e 制度锁**：参数卡/结果 SHA-256 清单、定种复跑逐位、
  `thresholds_widened=false`、负结果原样保留。

## 6. W1-R12 轮力矩冲突的显式解决方案（AR2 阻塞项，Wave A 开工前必须落地）

**冲突事实**（wave1_risk_update.csv W1-R12 行）：CTRL-02 Stage-A A2"峰值降为零"
隐含轮力矩峰值 **0.033 N·m（M1）/ 0.021 N·m（M2）**，是 R-5 冻结的 Stage-B
PROVISIONAL 档 **0.01 N·m/轴**（`20_engineering/config/attitude_stab/attitude_stab_v0.yaml`，
出处注释锚定 2–20 mNm 小轮目录级）的 3.3×/2.1×；A2 结论仅在无力矩限的动量级
模型成立（integrator-R 已从 stage_a_timeseries.csv 复核确认）。

**裁定（本计划预注册，PI 批准后生效）**：
- **R12-1 统一档**：ASM-02 全部层级（QP 约束、AC3 协调、任何前馈）采用
  **唯一 τ_w,max = 0.01 N·m/轴**——取更保守且有目录出处的 R-5 档。理由：
  0.033 不是任何硬件档，是无约束模型的隐含需求，不得升格为参数。
- **R12-2 单一来源机器锁**：`asm02_qp_v0.yaml` 的 wheel_max_torque_Nm 字段
  携带 attitude_stab_v0.yaml 的键路径 + 哈希引用；仓库内该数值的第二个字面量
  出现（除冻结历史工件）= 一致性测试 FAIL。
- **R12-3 统一力矩限下的 Stage-A 重评**（W1-R12 登记的 next_gate 原文）：
  ASM-02 首轮内做 pre-gate 断言——在 τ_w,max=0.01 限幅下重放 CTRL-02 Stage-A
  A2 的 M1/M2 协调，如实记录"峰值不再为零"的诚实结果（M1 预期饱和比 3.3×）；
  结果入 ASM-02 results 作交叉核验行，**不改动任何冻结 CTRL-02 工件**；claim
  矩阵按 W1-R12 缓解措辞限定"A2 主张为 momentum-level ideal"。
- **R12-4 运行时断言**：每个 ASM-02 run 机器检查
  max_t |ḣ_w,i(t)| ≤ τ_w,max（+数值容差），超限 = FAIL——确保 0.033 类
  隐含超限**永远不能再无声发生**。
- **R12-5 硬件触发**：轮组选型冻结（接口 SSOT rerun_triggers 已登记）→
  单点替换该键 → 重跑 AC3 全部场景 + R12-3 重评行；W1-R13（推力器脉冲量子
  敏感性）与本项分列——名义装配不用推力器，R13 不被本计划触发。

## 7. 场景集与指标（证明集优先，扫描延后——sim_12 纪律）

**冻结证明集（4 基线 × 4 场景 = 16 run）**：S1 名义插入；S2 粗对准边界起点
（横 5 mm/角 5° 同时取满）；S3 目标带速率摄动（量级取 sim_10 卫星锚
1.3872°/s 口径内的残余速率，装配前提=已消旋至门内）；S4 接触刚度边界
（k_n=1e4/1e6 扫掠端点，ASM-01 联合口径）。L2 柔性抽检仅 S1/S2（非判据）。

**指标**：逐相位跟踪 p95（位置/姿态或 approach 角）、基座 dev_angle 峰值与
∫‖ω_b‖dt、轮占用峰值与 max|ḣ_w|、接触力峰值/冲量/卡滞标志、插入耗时、
相位切换次数、QP 求解状态计数、success 及 reason_code、守恒/能量审计、
帆板 tip/模态能（PROVISIONAL 标注强制）。

## 8. claim 纪律

allowed：占位接口参数与冻结增益纪律下四基线相位结构的失败率与代价机器证明；
"分阶段语义是 CTRL-01 负结果的结构性回应"（带限定句式）；统一 τ_w,max 档下
AC3 协调的真实（非理想）性能；负结果本身。
forbidden：已完成自主在轨组装/实物验证；固定基座≡微重力；零空间反作用收益；
控制器扩大可行域；FLEX 任何判据性结论；A2"峰值为零"外推到有力矩限硬件；
不带"冻结增益与预注册轨迹下"限定的 CTRL-01 数字引用。

---

## 9. Task Card（ASM-02）

```yaml
task_id: asm_02_phased_assembly_control
role: 分阶段装配控制科学家 Agent（P0，AR2 解锁责任人）
scientific_question: >-
  冻结增益纪律与统一执行器档下，装配任务的相位分解（3D/5D/接触混合/短程6D）
  能否机器证明降低失败率；每相位任务维度语义、切换判据与资源代价逐项裁决。
baselines: [AC0 全程6D, AC1 5D->6D, AC2 5D->阻抗->6D, AC3 AC2+轮组柔性协调]
preregistered_predictions:
  PA-1: AC0 在 S2 粗对准边界场景失败（冻结增益 6D 全程超 fine 容差）——
        CTRL-01 GC1_A2 负结果的装配推论；若 AC0 全过，分阶段必要性主张降级。
  PA-2: AC2 接触力峰值 < AC1（阻抗增量）；卡滞率不升。
  PA-3: AC3 在 tau_w_max=0.01 统一档下基座峰值改善为部分而非归零（R12-3 联动）。
  PA-4: 名义装配推进剂恒等于 0 g（非零 = 分配缺陷 FAIL）。
first_read:
  - CLAUDE.md
  - 10_research/on_orbit_assembly/state_truth_and_scope.md
  - 10_research/on_orbit_assembly/phased_control_plan.md          # 本文档
  - 10_research/on_orbit_assembly/interface_ssot_draft.yaml
  - 10_research/on_orbit_assembly/gate_registry.yaml
  - 30_simulation/control_01_end_effector_tracking/results/control_01_gate_check.json
  - 30_simulation/control_02_base_attitude/results/control_02_gate_check.json
  - 10_research/partner_requirement_closure/wave1_results/wave1_risk_update.csv  # W1-R12 原文
  - 30_simulation/sim_11_coupled_dynamics/src/coupled_dynamics.py        # generalized_jacobian 只读
  - 30_simulation/safety_00_runtime_gate/docs/safety_gate_contract.md
owned_paths:
  - 10_research/on_orbit_assembly/phased_control_plan.md
  - 30_simulation/asm_02_phased_assembly_control/**        # 实现阶段新建
  - 20_engineering/config/assembly_control/**    # 实现阶段新建（asm02_qp_v0.yaml）
forbidden_paths:
  - 30_simulation/sim_01..sim_12/**, 30_simulation/control_01/**, 30_simulation/control_02/**, 30_simulation/safety_00/**
    （只读引用与 import；R12-3 重评结果写入自己 results，不回改冻结工件）
  - 20_engineering/config/geometry/**, 20_engineering/config/coupled_scene/**, 20_engineering/config/attitude_stab/**（只读引用）
  - 一切已冻结裁决 JSON 与哈希清单
blocking_precondition: >-
  W1-R12 统一裁定（§6 R12-1/R12-2）经 PI 批准并落 asm02_qp_v0.yaml 后方可写
  控制代码（AR2：协调基线不得建在矛盾参数上）。
machine_gates: [AG1-a..d, AG3-a..e, R12-3重评, R12-4运行时力矩断言, hash_lock, 定种复跑]
stop_condition: >-
  （a）AG1-a 任务维度断言两轮修复仍 FAIL -> 停，升级为相位语义/雅可比构造
  模型问题，禁止调权重绕过；（b）AG3-a 反向（分阶段更差）-> 如实冻结负结果并
  报 PI，不改场景救结果；（c）接口实测/轮组选型/帆板参数任一到位 -> 暂停发布，
  按 rerun_triggers 重跑。
rollback: 删除 owned_paths 新建目录即完全回滚；FAIL/UNKNOWN 裁决与账本原样入库。
claim_qualifier: 全部结论带"冻结增益与预注册轨迹下、PROVISIONAL 接口与执行器参数"限定。
```
