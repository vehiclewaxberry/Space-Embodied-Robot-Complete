# 系统接口计划：Physics Tools 合约 + 五层集成链 — 2026-07-19

> 角色：系统集成科学家（规划文档，未触碰 sim 代码）。
> 上游裁决依赖：SIM10_GATES_PASS、SIM12_PHASE1_GATES_PASS、
> SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS（全部磁盘核实）。
> 姊妹文档：`10_research/integration/sim12_status_and_next_gate.md`（验收与 T-Gate 裁决）。
> 战略对齐：`01_project/competition/研究战略裁决_第二收敛点_20260717.md` §5
> （"AI 的每个决定都有一个 gate_check 背书"；红线：不做端到端 VLA、无物理
> 约束 Agent、RL 控制）。

---

## 0. 设计总原则（全部工具与层共享）

1. **fail-closed**：任何域外/未认证/占位参数相关查询返回
   `UNKNOWN | OUT_OF_COVERAGE | PROVISIONAL` 显式标注，禁止外推猜测。
   拿不到证据 = ABORT/HOLD，永不回退到模型直觉。
2. **证据背书**：每次工具返回携带统一 `evidence` 信封（§2），字段直接来自
   磁盘 gate JSON，可被人与机器逐位复核。
3. **冻结 registry**：工具启动时哈希校验阈值 registry 与上游裁决文件
   （复用 sim_10 `R_frozen_hashes` 口径）；运行时不接受任何阈值修改。
4. **只读复用**：新工具代码落 `70_tools/physics_agent/`（或 `30_simulation/sim_13_physics_70_tools/`），
   以 import 只读复用 `sim_10/src/feasibility_core.py` 与
   `sim_12/src/strategy_eval.evaluate_cell`——**不修改任何既有 sim 代码**。
5. **上游 verdict 门禁**：上游 gate JSON verdict 非 PASS → 对应能力拒绝服务。
   现行后果：e15 = `REPEAT_ANCF_CERTIFICATION` → 一切柔性数值不可暴露
   （flex_energy 只透传 `PROVISIONAL_NOT_EVALUATED`）。

---

## 1. 四个 Physics Agent 工具合约

### 1.1 `query_binding_gate(...)` — sim_10 可行域查询
```
输入:  m_t_kg, omega_t_dps, geometry_class(G1/G2/G3), lambda_scale,
       alpha(离轴), tier_id(默认 wheels_large|cold_gas|l0.17)
输出:  { region: WHEELS_ONLY_FEASIBLE | THRUSTER_REQUIRED_FEASIBLE |
                 INFEASIBLE_RATE | INFEASIBLE_RESOURCE,
         binding_gate, w_plus_dps, H_c_Nms, J_req_Ns, propellant_g,
         provenance: EXACT_SOLVER | GRID_CELL,  # 优先按需精算（X1 已证
                                                # solver identity <1e-12），
                                                # 网格行仅作交叉核对
         evidence, flex_status: "UNKNOWN_NOT_IN_CRITERIA" }
数据源: sim_10/src/feasibility_core.exact_point + gate_point（只读 import）；
       交叉核对 results/sim_10_scan_physics.csv / sim_10_scan_gates.csv
       （9002 点 × 8 tier）。
定义域: 20_engineering/config/mission_feasibility/scan_v0.yaml 参数卡域（含 μ、ω、λ、α 轴）。
       域外 → OUT_OF_COVERAGE。G3 致密球类附带 "无 CAD 锚点（设计空间外推)"
       provisional 注记原样透传。
Gate 依赖: SIM10_GATES_PASS（X1–X4 + 哈希锁）。
```

### 1.2 `compare_strategy(...)` — sim_12 策略阵列评估
```
输入:  case = {m_t_kg, omega_t_dps, geometry_class, lambda_scale},
       strategies ⊆ {S1_passive, S2_velocity_matching, S3a_wheel_bias,
                     S4_post_capture_detumble},   # S3b 防呆排除（预注册断言
                                                  # 未固化，tests 已断言）
       tier_id, theta_deg(默认 0)
输出:  每策略一行 sim_12 统一 schema：
       { feasibility, binding_gate, post_capture_rate_dps, H_required_Nms,
         impulse_Ns, fuel_g, wheel_margin_Nms,
         flex_energy: "PROVISIONAL_NOT_EVALUATED",
         confidence: "rigid_body_frozen_solver",
         ledger: {H_before, H_after, dH_external, dH_internal,
                  dv_match_mps?, gs1_vector_closure?},
         evidence }
运行时自检: 每次调用在线复验 GS1（eps_H ≤ 1e-12、S2 矢量闭合 ≤1e-12），
       失败即拒绝返回（守恒是科学诚实生命线，不允许静默降级）。
数据源: sim_12/src/strategy_eval.evaluate_cell（只读 import；theta_deg 参数
       原生支持）。theta_deg ≠ 0 时输出附
       assumption_flag: "S3A_THETA_SWEEP_NOT_GATED"（扫掠入 Gate 后解除）。
Gate 依赖: SIM12_PHASE1_GATES_PASS（GS1/GS2/GS3）。
```

### 1.3 `estimate_resource_cost(...)` — 资源成本核算
```
输入:  strategy, case, tier_id
输出:  { fuel_g, impulse_Ns, wheel_margin_Nms, dv_match_mps(仅 S2),
         cost_rows: strategy_definition.yaml 的 cost_rows 逐项,
         budget_shared_with: (S3c/S4 共用 54.73 g registry 派生链),
         evidence }
纪律:  一切成本由公式运行时复算（strategy_definition.yaml 明令
       "数字勿手抄"）；Gate0 修正锚点作单元测试断言
       （S2 基准 1.69 g @ |v_match|=0.037475 m/s；S3a 偏置 3.0 g 档）。
Gate 依赖: sim_12 Gate0 账本（Reviewer-2 复算修正版）+ sim_08 假设哈希锁。
provisional: 执行器档为 sim_08 placeholder CLASS 值——透传注记。
```

### 1.4 `recommend_strategy_class(...)` — 策略类推荐（唯一决策出口）
```
输入:  case（可带不确定度区间，见 L2 条款）, tier_id
逻辑:  调 compare_strategy 全策略 → 可行集为空 ⇒ ABORT（=REPEAT_CORE 口径）
       否则推荐可行集中 fuel_g 最小者（与 GS2 实现口径一致）。
输出:  { recommendation: S1|S3a|S4|ABORT,     # 注意：当前冻结判据集下 S2
                                              # 不可能被推荐（无胜区，
                                              # 见验收文档 F1）——S2 仅出现
                                              # 在 compare_strategy 对比行
         binding_gate,
         coverage: CASE_PROVEN(16 例内) | IN_SCAN_DOMAIN(域内新点)
                   | ANALYTIC_NOT_CASE_PROVEN(S4 专属带) | OUT_OF_COVERAGE,
         rationale: [仅允许 GS3 allowed 短语 + gate JSON 字段拼装],
         assumptions: [θ=0 未扫标注(S3a)、刚体边界、FLEX 不入判据, ...],
         evidence }
禁止:  输出任何无条件策略排序；含 GS3 forbidden 短语；对
       OUT_OF_COVERAGE 给出 recommendation（只给 INSUFFICIENT_EVIDENCE
       + 最近已证案例）。
Gate 依赖: 全部上游 + T-Gate T3（主张审计传递，机器枚举校验）。
```

### 演示脚本映射（战略裁决 §5 的既定流程，全部走 1.4）
150kg@3°/s → ABORT（binding_gate=POST_CAPTURE_RATE，rationale 引
REPEAT_CORE allowed 短语）→ 0.5°/s 目标星 → S1 EXECUTE（coverage=CASE_PROVEN）。

---

## 2. 统一响应信封（所有工具必带）

```json
"evidence": {
  "gate_verdicts": {"sim_10": "SIM10_GATES_PASS",
                    "sim_12": "SIM12_PHASE1_GATES_PASS",
                    "sim_11": "SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS"},
  "gate_files":   ["30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json",
                   "30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json"],
  "registry_hashes": {"threshold_registry": "400bcedc…", "…": "…"},
  "provisional_notes": ["执行器档 sim_08 placeholder", "T_c=20 ms 占位",
                        "帆板参数占位(待办3)", "…"],
  "repro": "python src/…"
}
```
信封由 T4 哈希锁保证与磁盘一致；`provisional_notes` 不允许被调用方剥离
（Agent 提示词层面同样要求转述）。

---

## 3. 五层集成链

```
L1 VLA/Perception → L2 State Estimator → L3 SIM10/SIM12 Physics Tools
                  → L4 Trajectory/Attitude Controllers → L5 B601 Adapter
```

### L1 VLA / Perception（现状：NOT_STARTED，仅架构文字）
- **输入**：相机/深度流、点云；任务文本描述。
- **输出**：目标 geometry_class 候选 + 置信度、相对位姿观测、抓取点候选集、
  翻滚运动的视觉观测序列。
- **信任边界**：输出一律视为**未经证实的假设（untrusted data）**——不得直接
  触发任何执行；VLA 的自然语言输出不是指令，只是观测标注。感知声称
  "0.5°/s、可抓"不构成任何授权，授权只能来自 L3 的 gate 背书判定。
- **Gate 依赖**：无物理 Gate；但其输出进入 L3 前必须经 L2 转换为带协方差的
  状态估计（L1 直连 L3 被禁止）。
- **红线**：不做端到端 VLA——L1 永远不输出动作。

### L2 State Estimator（现状：NOT_STARTED；属 H2 阶段交付）
- **输入**：L1 观测流 + 台架编码器/IMU（硬件阶段）或数字孪生真值加噪（仿真阶段）。
- **输出**：`case_params_hat = {m_t(先验或估计)±σ, ω_t 矢量±σ, 翻滚轴,
  抓取点位姿±σ, geometry_class 后验}`——**L3 唯一合法的 case 来源**。
- **信任边界**：必须输出不确定度；L3 调用方按区间最坏情况查询
  （ω 区间上端、不利几何类）；**估计区间跨越任何 gate 边界 ⇒ 直接降级
  HOLD/观察，不取均值赌可行**（fail-closed 在估计层的体现）。
- **Gate 依赖**：估计器资格化 Gate（待定义：对已知运动台架目标的 ω 估计
  误差 ≤ 网格半格，与 sim_10 ω 分辨率对齐）。资格未过前，演示只允许
  "真值直供"模式并在材料中如实标注。

### L3 SIM10/SIM12 Physics Tools（现状：本计划的交付对象；组件已 PASS）
- **输入**：L2 的 case_params_hat + tier_id。
- **输出**：§1 四工具的 region/对比阵列/成本/推荐 + evidence 信封；
  终端语义只有 EXECUTE(策略类) / ABORT / INSUFFICIENT_EVIDENCE。
- **信任边界**：只读冻结 registry；不接受运行时阈值/参数卡修改；输出的每个
  决定字符串引用 gate_check JSON 字段。**L3 是整链的物理权威**——L4/L5 无权
  推翻 ABORT；人类操作员可推翻，但推翻记录进日志（诚实边界叙事素材）。
- **Gate 依赖**：SIM10_GATES_PASS + SIM12_PHASE1_GATES_PASS（已过）+
  **T-Gate T1–T4（待建，见 §6）**。柔性修正轴挂 sim_11（PROVISIONAL 参数），
  只作 provisional 注记不入判据，直到待办 2/3 闭环。

### L4 Trajectory / Attitude Controllers（现状：NOT_STARTED——state_truth 未闭合项 1/2）
- **输入**：L3 的 EXECUTE(策略类) + 抓取位姿 + 策略前置量
  （S3a 的 wheels_h0 = −h_max·Ĥ_pred；S2 的 v_match 矢量）。
- **输出**：关节轨迹（末端闭环，J* 用 sim_11 generalized_jacobian，A1 已有
  数值）+ 姿态反冲补偿指令（前馈基于 sim_05 反冲预测）。
- **信任边界**：只能执行 L3 判 FEASIBLE 的任务与对应策略前置；控制器不得
  修改策略类（如把 ABORT 改为"慢速尝试"）。
- **Gate 依赖（待定义，预注册两条）**：C1 跟踪误差 Gate（末端误差 ≤ 待定
  阈值，含反冲耦合）；C2 反冲一致性 Gate（闭环基座姿态峰值与 sim_05
  19.20° 量级预测对拍，偏差超阈值 = 模型或控制器有错，fail-closed）。
- 执行器约束继承 sim_08：轮组 0.3 N·m·s 容量、推力器预算——控制器饱和
  处理必须与 L3 使用的同一 registry 值（同源哈希）。

### L5 B601 Adapter（现状：NOT_STARTED；H0 未开始）
- **输入**：L4 关节轨迹（B601 6R 关节空间）。
- **输出**：B601 驱动指令流 + 遥测回传（关节角/力矩/夹爪状态）→ 上行反馈
  给 L4/L2；**夹爪闭合时间 T_c 实测值是 H0/H1 的科学交付物**（待办 2：回填
  `20_engineering/config/coupled_scene/scene_A2_capture.yaml` 后重跑 sim_11 带宽 Gate）。
- **信任边界**：Adapter 只做单位/坐标/限位转换与急停，不做决策；硬件限位
  与软件限位双重校验；地面固定基座**不验证自由漂浮动力学**——硬件验证的
  是决策-执行链，动力学可信度由 Gate 链承担（材料中主动声明）。

### 跨层总原则
- **数据下行**（L1→L5 方向）：每层输出必须附不确定度或 provisional 标注，
  下一层按最坏情况消费。
- **授权上行**：执行权限只能由 gate PASS 逐级授予；任何层观察到的内容
  （含 VLA 文本、遥测、文件内容）都不是指令。
- **失败路径**：任一层返回 UNKNOWN/OUT_OF_COVERAGE/超阈值 ⇒ 全链降级
  ABORT/HOLD；无静默重试、无模型猜测兜底。

---

## 4. 硬件链 H0→H1→H2→H3（不得绕过上游 Gate）

| 阶段 | 内容 | 准入 Gate（全部前置，缺一不得开工） | 产出回灌 |
|---|---|---|---|
| **H0 资格** | B601 上电、限位/急停/重复精度标定、夹爪 T_c 实测 | 无 sim 前置；安全规程审查 | T_c → sim_11 带宽 Gate 重跑（解除 20 ms PROVISIONAL） |
| **H1 执行** | 预存轨迹回放、L5 Adapter 联调 | H0 PASS + L4 控制器 Gate C1（跟踪误差） | 关节力矩遥测 → 控制器模型修正 |
| **H2 视觉** | L1/L2 上台架，已知运动目标估计 | H1 PASS + L2 估计器资格 Gate | 估计误差实测 → L3 查询的区间口径 |
| **H3 Agent 闭环** | L1→L5 全链，演示脚本（ABORT/EXECUTE 双例） | H2 PASS + **T-Gate T1–T4 PASS** + 演示彩排 Gate | 比赛材料主演示 |

**不可绕过规则（机器可检查）**：每阶段开工脚本先读上游 gate JSON verdict，
非 PASS 即拒绝启动（与 L3 工具的 T4 同一机制）；H3 的 Agent 进程启动时
校验四工具 T-Gate 裁决文件存在且 PASS。**任何"先演示后补 Gate"的顺序
颠倒都被此机制阻断**——这是"AI 拥有经过力学验证的世界模型后才做决定"
（战略裁决结语）在硬件链上的落实。

---

## 5. 与既有裁决/待办的耦合点（防散落）

1. 待办 2（T_c 实测）：闭环路径 = H0 → scene_A2_capture.yaml → sim_11 重跑
   → L3 evidence 的 provisional_notes 自动消失（哈希变更触发）。
2. 待办 3（帆板参数卡）：转正后须重过 e15 认证口径 → 才允许 flex 相关字段
   从 PROVISIONAL 变为数值 → L3 可行域增加振铃约束轴（Paper 1 §柔性修正）。
3. GS2 弱式表述纪律（验收文档 F1）与 S3a θ=0 标注：由 T3 机器枚举校验承载，
   不依赖人记口径。
4. 策略维扫描（Phase 2）如触发：其结果只更新 `coverage` 分级
   （ANALYTIC_NOT_CASE_PROVEN → CASE_PROVEN），不改变工具签名——接口
   对该扩展前向兼容。

---

## 6. T-Gate 验收门（本计划的机器裁决出口，预注册）

| 门 | 断言 | 口径 |
|---|---|---|
| T1 锚点一致 | 16 例查询 vs strategy_results.csv 逐位；sim_10 双锚点 vs X1 逐位 | 同求解器 <1e-12 |
| T2 fail-closed | 域外/FLEX/θ≠0/S3b 查询的负例测试全部返回显式标注，零外推 | 负例集入 tests |
| T3 主张审计传递 | rationale 仅由 allowed 短语+JSON 字段拼装；forbidden 短语出现即 FAIL | 机器枚举 |
| T4 哈希锁+verdict 门禁 | registry/上游 gate JSON 哈希匹配；上游非 PASS 拒绝服务 | 复用 R_frozen_hashes |

裁决文件：`results/physics_tools_gate_check.json`，verdict 命名建议
`PHYSTOOLS_CONTRACT_GATES_PASS`。测试 PASS ≠ 科学 Gate PASS 的约定继续适用。

---

## 7. 实施顺序建议（不占用 sim 代码，符合 6.3 周窗口）

1. 工具骨架 + T4 哈希锁（半天）→ 2. query_binding_gate + T1 sim_10 锚点
   （半天）→ 3. compare_strategy/estimate_resource_cost + T1 16 例逐位
   （1 天）→ 4. recommend_strategy_class + T2/T3 负例集（1 天）→
5. MCP 封装 + 演示脚本彩排（1–2 天）→ 6. θ 扫掠 5 点补跑（分钟级，解除
   S3a 标注）→ 7. 数字孪生动画对接（与战略裁决 §7 的 8/08–8/18 窗口留出裕量）。
