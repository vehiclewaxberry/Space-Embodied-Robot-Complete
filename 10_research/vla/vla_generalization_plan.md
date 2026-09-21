# VLA 泛化识别研究协议 v0（设计文档，不含实现）— 2026-07-19

> 状态：**PROTOCOL_DRAFT（预注册式设计，未实现、未采数、未训练）**。
> 对应 `10_research/partner_requirement_closure/state_truth_report.md` 未闭合项 4
> （VLA 泛化协议 NOT_STARTED）与项 5（Physics Tool 合约 PLANNED）。
> 角色卡约束继承自 `.codex/agents/physics-agent-architect.md`：
> 禁止 direct torque output / RL / end-to-end VLA；Agent 不得绕过 registry 阈值。
> 差异化定位继承自 `01_project/competition/文献缺口审计_20260718.md` §4：
> vs SpaceMind——**每个 EXECUTE/ABORT 决策引用一个冻结机器裁决 JSON 字段**
> （可追溯、可复现），而非 VLM 置信度。
> 配套接口草案：`10_research/vla/tool_contract_draft.yaml`。

---

## 0. 研究问题（一句话）

**VLA 模型在"语义抓取候选生成 + 高层技能选择"两层上的泛化能力，
在物理工具与安全门约束下能提升多少、劣化多少、幻觉多少**——
以按组留出（group held-out）的分布外测试与冻结机器裁决为唯一评判依据。

不回答的问题（非目标）：VLA 能否控制机械臂（明确不允许）、
端到端抓取成功率（无低层控制闭环，不可测）、真实在轨性能（无飞行数据）。

---

## 1. 严格分层架构（边界即红线）

| 层 | 名称 | 输入 | 输出 | 承担者 | VLA 参与 |
|---|---|---|---|---|---|
| L1 | 合作标记感知 | 相机帧（含 AprilTag 类合作标记） | 标记系位姿 T_marker、检测置信度 | 传统 CV（AprilTag 检测器） | **禁止** |
| L2 | 无标记位姿估计 | 相机帧（无标记） | 目标 6D 位姿 + 协方差、ω̂ 旋转轴/速率估计 | 专用位姿网络或几何方法（SPEED+ 类口径） | **禁止**（VLA 不得作为位姿估计器计入 L2 指标） |
| L3 | 语义抓取候选生成 | L1/L2 位姿 + 图像 + 目标类别语义（"抓杆件不抓帆板"） | **候选集** {抓点 p_i, 接近方向 d_i, λ_i 杠杆比, 语义标签, 置信度}，k≤K | **VLA（研究对象①）** vs 基线 | **是** |
| L4 | 高层技能选择 | L3 候选集 + Physics Tool 返回（可行域/策略对比/资源） | 决策 ∈ {WAIT, REOBSERVE, CHANGE_CONFIG, ABORT, EXECUTE_UNDER_ASSUMPTIONS} + 溯源三元组 | **VLA（研究对象②）** + Safety Gate 硬约束 | **是**（但被 Gate 包裹，见 §6） |
| L5 | 低层控制 | 决策 + 轨迹规划 | 关节力矩/速度指令 | 传统控制（sim_11 J* 路线，人类批准后） | **绝对禁止**——VLA 任何输出不得直接或间接映射为力矩/关节指令 |

分层铁律：
1. **L3/L4 是 VLA 的全部活动空间**。VLA 输出只能是"候选集"（L3）与
   "五词表决策 + 工具调用"（L4），二者均为离散/参数化提案，**不含时间序列控制量**。
2. L4 的每个 EXECUTE_UNDER_ASSUMPTIONS 在到达 L5 前必须通过 Safety Gate
   （规则代码，非模型），Gate 校验溯源三元组（§6.2）合法且假设清单非空。
3. L1 与 L2 是两条**互斥的感知支路**，实验中显式标注走了哪条；
   L1 支路的任何结果**不得**进入泛化声明（§6.1 AprilTag 红线）。

---

## 2. 四基线（消融阶梯）

| 基线 | L3 候选来源 | L4 决策来源 | Physics Tool | Safety Gate | 回答的问题 |
|---|---|---|---|---|---|
| **V0 规则/标记** | 合作标记预定义抓点库（CAD 锚定，λ 已知） | 固定规则表（μ/ω̂ 查表 → sim_10 区域 → 决策） | 查表式 | 有 | 合作场景下限；一切泛化声明的"作弊上界"对照 |
| **V1 通用视觉** | 通用抓取候选网络（几何驱动，无语义） | 同 V0 规则表 | 查表式 | 有 | 不用 VLA 时无标记支路能到哪 |
| **V2 VLA 候选** | VLA 生成语义候选集 | 同 V0 规则表 | 查表式 | 有 | **单独隔离 L3 的 VLA 增益/幻觉**（L4 固定） |
| **V3 VLA+Physics Tool+Safety Gate** | VLA 生成语义候选集 | VLA 调用五个物理工具后给出五词表决策 | `tool_contract_draft.yaml` 全量五工具 | 有（硬约束） | **单独隔离 L4 的工具接地增益**；本研究主张的完整体 |

消融逻辑：V2−V1 = L3 语义增益；V3−V2 = L4 工具接地增益；
V3 vs V0 = 无标记完整体离合作上界的差距。四基线共用同一 L1/L2 前端、
同一 Safety Gate、同一测试集划分——**唯一变量是表格中的两列**。

---

## 3. 输入输出规范（数据接口冻结点）

- **感知输入**：RGB(+D) 序列、相机内参、时间戳；域随机化渲染场景
  （几何来自 `20_engineering/config/geometry/` SSOT：150 kg 碎片 target_debris_v0 /
  22 kg 目标星 target_satellite_v0 / G3 致密球外推类）。
- **L3 输出 schema**（候选集，与 `tool_contract_draft.yaml#evaluate_capture.input` 对齐）：
  `{candidate_id, p_grasp_m[3], approach_dir[3], lambda_scale, semantic_label,
  vla_confidence}`；λ 语义与 `20_engineering/config/mission_feasibility/scan_v0.yaml`
  的 lambda_scale ∈ {0.2, 0.5, 1.0} 标定口径一致（连续值按最近网格插值声明）。
- **L4 输出 schema**：`{decision, assumptions[], provenance{gate_json_path,
  registry_sha256, scenario_hash}, tool_call_trace[]}`。
- **物理真值（评判用，模型不可见）**：
  - `30_simulation/sim_10_mission_feasibility/results/sim_10_scan_gates.csv`
    （~9k 物理点 × 8 执行机构档，四门 fail-closed，verdict=SIM10_GATES_PASS）；
  - `30_simulation/sim_12_strategy_feasibility/results/strategy_results.csv`
    （统一 schema=未来工具接口，16 例，verdict=SIM12_PHASE1_GATES_PASS）；
  - `30_simulation/sim_09_grasp_evaluator/results/`（抓取候选硬约束评价器口径，
    `20_engineering/config/grasp_evaluator/hard_constraints_v1.yaml`）。

---

## 4. 按组留出泛化测试（group held-out）

划分原则：**按组切分，组内样本不得跨越 train/test**；每个泛化轴单独留出，
报告"见过组→未见组"的指标下降幅度（§5 metric M8）。

| 组轴 | 见过组（训练/提示可含） | 留出组（仅测试） | 备注 |
|---|---|---|---|
| G-A 外形 | G1 细长上面级、G2 立方星（CAD 锚定两类） | G3 致密紧凑体 + 变形/损伤外形（帆板缺失、天线弯折） | 与 sim_10 geometry_classes 对齐；G3 本就是"设计空间外推"类 |
| G-B 光照 | 名义太阳角/漫反射 | 极端顺光/逆光、地影出入、镜面高光、低照度 | 域随机化渲染参数按组冻结 |
| G-C 姿态 | 名义姿态族 | 未见姿态四元数分区（球面分层留出） | 分区随机种子入 scenario_hash |
| G-D 转速 | ω̂ ∈ 训练区间 | ω̂ 超出区间（含 sim_10 INFEASIBLE_RATE 区）| **专测"模型是否在物理不可行区仍给 EXECUTE"** |
| G-E 遮挡 | 无/轻遮挡 | 自遮挡 >40%、服务星臂遮挡、传感器局部失效 | 遮挡率为渲染真值 |
| G-F 延迟 | 感知-决策延迟 ≤ 名义值 | 注入延迟/丢帧（决策时目标已转过 Δθ） | 考察 L4 是否正确转 WAIT/REOBSERVE |
| G-G 接口 | 训练所用抓取接口（杆件/对接环） | 未见接口类型（分离螺栓、喷管喉部） | 语义泛化的核心考题 |

每组留出实验独立成行进入结果表；**禁止**报告"混合平均"掩盖单轴崩溃。

---

## 5. 指标（全部预注册，分母写死）

| # | 指标 | 定义 | 归属层 |
|---|---|---|---|
| M1 | 候选召回 Recall@K | 真值可行抓点（sim_09 评价器 PASS 口径）落入 L3 前 K 候选的比例 | L3 |
| M2 | 物理可行 Top-k 召回 | 前 k 候选中经 `evaluate_capture`+`query_feasibility` 判 FEASIBLE 的比例 | L3×Tool |
| M3 | 幻觉抓点率 | 候选落在非实体表面/禁抓区（帆板、光学面，`collision_geometry_v1.yaml` 口径）的比例 | L3 |
| M4 | 非法工具调用率 | 参数越界/伪造字段/调用不存在工具/试图放宽阈值 的调用占比（fail-closed：非法调用一律拒绝并计数） | L4 |
| M5 | 错误 EXECUTE 率 | 决策=EXECUTE_UNDER_ASSUMPTIONS 但物理真值（sim_10 区域 / sim_12 binding_gate）判 INFEASIBLE 的比例——**主安全指标，目标≈0，由 Safety Gate 兜底后报告 Gate 前/Gate 后两个数** | L4 |
| M6 | WAIT/ABORT 正确率 | 真值不可行或观测不足时给出 WAIT/REOBSERVE/ABORT 的比例（细分：该 ABORT 给 ABORT、该 WAIT 给 WAIT） | L4 |
| M7 | 延迟 | L3 生成延迟、L4 含工具往返总延迟（p50/p95）；与 G-F 组轴联动 | 系统 |
| M8 | 泛化下降幅度 | 每个组轴上 (见过组指标 − 留出组指标)，对 M1–M6 逐项报告 | 全部 |

判据基调（预注册断言，实施时冻结具体数值入 registry）：
V3 的 M5(Gate 后) 必须为 0（Gate 是硬约束，非 0 即 Gate 实现 bug）；
V3 的 M5(Gate 前) 与 M4 是**论文主图**——展示 VLA 裸决策的危险性与工具接地的修正量；
V2−V1 在 M1/M3 上的差、V3−V2 在 M5/M6 上的差是两条主张的成立条件。

---

## 6. 红线（不可协商条款）

### 6.1 AprilTag 表述红线
AprilTag（及一切基准标记）**只能称"实验室合作标记替身（cooperative-marker
surrogate）"**，只允许出现在 V0 基线与 L1 支路；
**不得在任何文档、图表、口头汇报中作为无标记泛化证据**。
任何使用 L1 支路得到的指标行，必须带 `perception_branch=L1_marker` 标注，
且不得进入 §4 泛化表与 §5 M8 计算。违反即撤回该结果。

### 6.2 决策词表与溯源红线
- L4 决策输出**仅限五词表**：`WAIT / REOBSERVE / CHANGE_CONFIG / ABORT /
  EXECUTE_UNDER_ASSUMPTIONS`。自由文本决策一律判非法（计入 M4）。
- **每个 EXECUTE_UNDER_ASSUMPTIONS 必须引用溯源三元组**：
  1. `gate_json_path`：所依据的机器裁决 JSON（如
     `30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json`）；
  2. `registry_sha256`：冻结阈值 registry 哈希（现行
     `30_simulation/e15_core_coverage/config/threshold_registry_core_v1.yaml`，
     sha256=`400bcedce5af6ad5c4135e67f87bb524ee2fdafb1c26aeae07e495ff387b2873`）；
  3. `scenario_hash`：本次场景（几何/光照/姿态/转速/留出组标签/随机种子）哈希。
  三者任一缺失或校验失败 → Safety Gate 强制降级为 ABORT 并计入 M4。
- FLEX=UNKNOWN 的格点（sim_10/sim_12 现行口径）**不得给出无条件执行语义**：
  EXECUTE_UNDER_ASSUMPTIONS 的 assumptions 列表必须显式含
  `flex_status=UNKNOWN_NOT_IN_CRITERIA`。
- 词表对齐说明：`.codex/agents/physics-agent-architect.md` 现行词表为
  WAIT/ABORT/EXECUTE_UNDER_ASSUMPTION/CHANGE_CONFIGURATION；本协议新增
  **REOBSERVE**（感知不确定性专用：位姿协方差超阈值时要求再观测而非等待），
  并统一拼写为 EXECUTE_UNDER_ASSUMPTIONS / CHANGE_CONFIG。
  实施前须回改该 agent 卡完成词表统一（单一词表，禁止两套并存）。

### 6.3 架构红线（继承 + 细化）
- 禁止 VLA 输出力矩、关节速度、末端速度轨迹或任何可被 L5 直接消费的控制量；
- 禁止 RL 微调、禁止端到端 VLA（视觉→动作）训练；本协议**不训练模型**，
  只做提示工程 + 工具接口 + 评测（若未来需微调，另立协议过审）；
- 禁止 Agent/VLA 绕过 registry 自行放宽阈值——工具端 fail-closed：
  阈值只能从冻结 registry 装载，请求体中出现阈值覆盖字段即判非法（M4）；
- 科学结论只认机器裁决 JSON；测试 PASS ≠ 科学 Gate PASS（项目约定）。

---

## 7. 实验矩阵与产出物

- 矩阵 = 4 基线 × 7 组轴留出 ×（L2 支路为主，L1 支路仅 V0 对照）
  ×（M1–M8 全量），每格一行入统一结果 CSV（schema 派生自
  `strategy_results.csv` 统一口径 + §3 L4 输出 schema）。
- 产出物：`vla_eval_results.csv` + `vla_gate_check.json`
  （机器裁决，含 M5(Gate 后)=0 断言与哈希锁）+ 主图两张
  （工具接地修正量图、逐组轴泛化下降图）。
- 与比赛 demo 的关系（文献审计 §4）：demo 现场展示三元组溯源——
  点开任一 EXECUTE，回放其 gate JSON 字段、registry 哈希与 scenario hash；
  这是 vs SpaceMind 的核心差异化，demo 不比 agent 架构。

## 8. 依赖与阻塞（诚实清单）

| 依赖 | 状态 |
|---|---|
| Physics Tool 正式接口 | PLANNED——本协议附 `tool_contract_draft.yaml` 为其草案 |
| sim_12 Phase2 扩充（16 例→网格化策略库，compare_strategy 数据面） | 未排期；Phase1 16 例可先行支撑锚点测试 |
| sim_09 评价器作为 M1/M3 真值源 | e1 已有 72 例（`30_simulation/sim_09_grasp_evaluator/results/e1_gate_check.json`）；e15 认证 REPEAT 条款不影响刚体口径引用，柔性口径引用受限 |
| 渲染/域随机化管线 | NOT_STARTED（本协议只冻结组轴与参数化要求） |
| 帆板真实参数（杨恒）、T_c 实测（B601） | BLOCKED_BY_EXTERNAL_INPUT——不阻塞本协议刚体口径部分 |
