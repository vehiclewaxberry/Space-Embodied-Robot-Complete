# ROM×安全门集成规划（装配阶段安全线）— RQ3/RQ4 + SAFE-00 扩展 + Gate AG5

> 状态：**PLAN_ONLY（只读规划，未实现）**。2026-07-20，ROM-安全集成规划 Agent。
> 本文件是 `10_research/on_orbit_assembly/` 装配阶段安全线的唯一规划产物；不修改任何
> 冻结证据，不触碰已 PASS 的 SAFE-00 裁决核。
>
> 证据基线（全部磁盘核实）：
> - SAFE-00：`30_simulation/safety_00_runtime_gate/results/safety_00_gate_check.json` verdict=**PASS**
>   （GS-A/GS-B/GS-C 全过；bypass 12 例 0 成功；determinism 16 例逐位；tests 47/47；
>   `next_stage_authorized=false`、`review_status=PENDING_REVIEW` 原样继承）。
> - 合同：`safety-gate-v1` + `safety-gate-policy-v1.2`，状态 `FROZEN_FOR_SAFE_00_WAVE1`
>   （`20_engineering/config/safety_gate/safety_policy_v1.yaml` + 三份 closed schema）。
> - ROM：`10_research/rom/multifidelity_rom_plan.md` v0.1 + `model_fidelity_selection_rules.yaml`
>   （DRAFT_PLAN_ONLY，未实现未认证）。
> - 红队：`10_research/partner_requirement_closure/red_team_vla.md`（攻击面⑤ A1–A7、
>   攻击面⑥ ROM 五组合）。
> - 装配主场景与技能词表：`10_research/on_orbit_assembly/state_truth_and_scope.md`（AG-A0 PASS）；
>   接口参数：`10_research/on_orbit_assembly/interface_ssot_draft.yaml`（**全字段
>   PROVISIONAL/LITERATURE，无 MEASURED**）。

---

## 0. 红线（从冻结资产直接继承，本计划不得违反）

1. **不改已 PASS 裁决核**：`30_simulation/safety_00_runtime_gate/src/*`、
   `20_engineering/config/safety_gate/{safety_request,evidence_bundle,safety_response}.schema.json`、
   `safety_policy_v1.yaml`、`results/safety_00_gate_check.json` 全部只读。装配扩展 =
   新增合同文件 + 新增模块，改动面与回归界见 §2.4。
2. **UNKNOWN 永不 ALLOW**（SAFE-00 GS-A `unknown_never_allow=true`）；本计划将其延伸为
   **UNKNOWN 永不 success**（装配八判据，§2.3）。
3. **fail-closed 升级语义**：升级目标不可用 ≠ 低层定案（response schema
   `fallback_trace[].accepted_for_finalization` 为 `const:false`；B6/D1/D2 判例）。
4. **PROVISIONAL 传染**：接口 SSOT 无任何 MEASURED 字段；一切装配安全结论继承
   `PROVISIONAL_INTERFACE_PARAMS`，实测到货后全 Gate 重跑（rerun_triggers 见接口 SSOT）。
5. 科学结论只认机器裁决 JSON；测试 PASS ≠ 科学 Gate PASS。

---

## 1. RQ3：装配相位 × 保真度映射表

原则（每格给判据出处，不拍脑袋）：**远场=L0、接近/接触=L1、锁紧验证=L2 抽查**；
过渡带禁止 L0 单独定案（sim_10 X2：G1 μ≈0.51 亚分辨率非单调 dip 1.08%，
`model_fidelity_selection_rules.yaml` R5 `minimum_level: L1`）；L2 现为
`certification: UNAVAILABLE`（`safety_policy_v1.yaml` L2_reason=E15_REPEAT_ANCF_CERTIFICATION），
故 **L2 抽查=审计性证据（audit-only），在 e15 闭环前不得作为 ALLOW/success 的裁决依据**，
抽查缺失或失败 → UNKNOWN→WAIT，绝不"跳过检查视同通过"。

| 相位（技能词表） | 名义裁决层 | 升级/抽查路径 | 判据出处（磁盘证据） |
|---|---|---|---|
| OBSERVE | 无动力学裁决；仅感知时效+协方差门 | — | `safety_policy_v1.yaml` time_policy：`max_capture_age_s=2`；request schema `state_covariance.assessment`（FAIL/UNKNOWN → `STATE_COVARIANCE_NOT_PASS`）；来源仅限 `trusted_state_channels`（A1 封堵面） |
| GRASP_MODULE（抓 1U 模块） | **L1**（接触带宽口径强制） | R5 裕度不足 → L2 审计抽查 | 接触事件必须有限带宽建模：`30_simulation/sim_11_coupled_dynamics/src/contact_window.py`（T_c=20 ms **PROVISIONAL**，扫掠带 [5,100] ms）；R2b 模态覆盖 κ_band=1.4，锚点 T_c=20ms→f_band=25Hz、f3=17.55Hz 在带内 ⇒ m≥3（sim_11 m2 诊断模态能差 2.18%）；理想冲量口径能量指标不适定（sim_11 `ideal_impulse_diagnostic`）禁用于本相位 |
| MOVE_TO_PREASSEMBLY（远场转移，无接触） | **L0 可行性筛选** + L1 刚化模式传播臂-基座耦合 | R3 挠度黄区 → L1 全柔复核 | L0 域定义不含 T_c/f1（`safety_policy_v1.yaml` domains.L0 注释："L0 不使用 T_c/f1"——红队⑥组合1 的封堵）；臂动基座扰动量级 sim_05 19.20°；L1 刚化↔sim_05 逐点 7.8e-6（rom plan §1 层间锚定/G3b）；**注意**：A1"柔性反馈可忽略"结论基于 0.348 kg 占位帆板（CLAUDE.md 待办3，真实 2–5 kg/m² 差 5–10 倍可能翻转），故本相位 L0/刚化结论必须挂 `PROVISIONAL_PANEL_MASS` |
| APPROACH_5D（5 自由度接近） | **L1** | 过渡带（G1 μ∈[0.4,0.7]）候选禁 L0 定案；裕度 d≤ε_tot → L2 审计 | R5 `in_transitional_band → minimum_level: L1`（sim_10 X2 实录）；相位语义的控制物理依据 = CTRL-01 预注册负结果：**5D 接近段才有 1 维零空间，严格 6D 零空间真零（+1.84e-5%）**（Wave1，`10_research/partner_requirement_closure/wave1_repeat/`，引用须带"冻结增益与预注册轨迹下"限定） |
| ALIGN（锥面/销孔精对准） | **L1** | r_defl 黄区 [0.02,0.05) → 挂 `LINEARITY_MARGINAL` 且边界候选升 L2 | 公差判据来自接口 SSOT：粗 5.0 mm/5.0°、精 0.1 mm/0.5°（LITERATURE）；R3 阈值 0.02/0.05（EB 小挠度工程界，rom plan §2 R3，"阈值本身列为认证集敏感性扫描对象"） |
| COMPLIANT_INSERT（柔顺插入，接触富集） | **L1 强制**（禁 L0） | R2b 覆盖失败→加模态至 m≤7 否则 L2；R4 慢尾（连续两档不降）→判不适定或 L2；d≤ε_tot → L2 | KV 接触参数 k_n=1e5 N/m、c_n=2e2 N·s/m 均 **PROVISIONAL**（接口 SSOT，ASM-01 扫掠 1e4–1e6）；R4 判据 τ_m<0.01（G4' 现行 1% 判据，实测 m3→m4=0.48%、m4→m5=0.027%）；慢尾 FAIL 特征 = 理想冲量 +2.86/+1.29/+0.72%（sim_11 v1.0→v1.1 教训） |
| LOCK_6D（机械锁扣，锁紧冲击） | **L1 名义裁决** + **L2 审计抽查** | L2 未认证 → 抽查为 audit-only，不入 ALLOW 依据；若规则要求 L2 定案而 L2 不可用 → `ASM_ROM_ESCALATION_UNAVAILABLE`（§4） | latch_force 20 N **PROVISIONAL**（接口 SSOT）；L2 认证债：e15 交叉求解 5.64%>5% → `REPEAT_ANCF_CERTIFICATION`（rules YAML `certification_debt`）；L2 限定条款强制复述："平面梁组件级，非全 3D 板全耦合"（`limitation_clause_mandatory`）；SAFE-00 B6/D2 判例：L2 失败无乐观回退 → WAIT |
| VERIFY_ASSEMBLY（八判据裁决） | 证据汇总层（消费 L1 结果 + L2 审计行） | 任一判据 UNKNOWN → 非 success（§2.3） | 八判据注册于 `interface_ssot_draft.yaml` `assembly_success_criteria`（"UNKNOWN 永不判 success"已写入 SSOT 注释）；判据7（柔性响应在已验证包络内）的包络 = **L1 认证域**（r_defl 绿区 + L1 域），不得引用未认证 L2 |
| RETREAT（撤离） | L1 释放瞬态 → L0 远场 | 层降级必须重查目标层域 | 降级链判例 D1：`FALLBACK_DOMAIN_UNCHECKED → BACKOFF`（safety_00_gate_check.json）；L1→L0 降级时域重查是 GS-A `fallback_target_domain_rechecked=true` 的既有纪律 |

映射表的机器落点：相位×层白名单入装配策略卡（§2.4 `asm_policy_v0.yaml`
`phase_level_map`），选择器实现（ROM R1 阶段）按卡求值，卡外组合 → fail-closed
`ASM_SKILL_NOT_REGISTERED` / `OUT_OF_DOMAIN`。

---

## 2. SAFE-00 装配扩展设计（新增合同字段，不改已 PASS 裁决核）

### 2.1 装配专用 reason_code（新增注册，`ASM_` 前缀与 v1 命名空间零冲突）

v1 现有 reason_code 全集已从 `safety_core.py` 逐项提取核对（AUTHORIZED_SAFE …
SOURCE_CHANNEL_UNTRUSTED 等 40+ 项），扩展码均满足 response schema 现行 pattern
`^[A-Z0-9_]{1,96}$`，因此**响应 schema 无需修改**即可容纳：

| reason_code | 触发语义 | 决策映射 |
|---|---|---|
| `ASM_PHASE_SCOPE_MISMATCH` | 持 APPROACH_5D 授权执行 LOCK_6D（或任意相位越权） | UNKNOWN/ABORT |
| `ASM_PHASE_TRANSITION_UNADJUDICATED` | 相位切换未经过重新裁决（沿用上一相位授权） | UNKNOWN/ABORT |
| `ASM_LATCH_STATE_INVALID` | latch_state ∉ {OPEN,ENGAGED,LOCKED} 或 =FAULT | UNSAFE/ABORT（FAULT）；UNKNOWN/WAIT（缺失） |
| `ASM_SUCCESS_CRITERION_UNKNOWN` | 八判据任一为 UNKNOWN | UNKNOWN/WAIT（永不 success） |
| `ASM_SUCCESS_EVIDENCE_INCOMPLETE` | 八判据证据行缺失/provenance 不完整 | UNKNOWN/ABORT |
| `ASM_CONTACT_PARAM_OUT_OF_SWEEP` | k_n∉[1e4,1e6] 或 T_c∉[5,100]ms 或 c_n 域外 | UNKNOWN/BACKOFF |
| `ASM_STALE_IN_CONTACT` | 接触相位（COMPLIANT_INSERT/LOCK_6D）内证据过期 | UNKNOWN/**BACKOFF**（接触中不许 WAIT 原地持锁，见 §3 注） |
| `ASM_ROM_ESCALATION_UNAVAILABLE` | 规则要求升级而目标层 certification∉{CERTIFIED,白名单 PROVISIONAL} | UNKNOWN/WAIT（红队⑥组合2 落位） |
| `ASM_INTERFACE_PROVENANCE_PROVISIONAL_UNACKED` | 接口 SSOT 的 PROVISIONAL/LITERATURE 标注未随请求透传确认 | UNKNOWN/ABORT（A6 纪律延伸） |
| `ASM_SKILL_NOT_REGISTERED` | proposed phase ∉ 九词技能词表 | UNKNOWN/ABORT |
| `ASM_WHEEL_LEDGER_UNRESOLVED` | 基座轮组判据引用 CTRL-02 分账但 W1-R12 冲突未解且请求未带该 flag | UNKNOWN/WAIT（接口级阻塞候选，ASM-02 显式解决前不得静默通过） |

### 2.2 相位授权语义（APPROACH_5D 授权 ≠ LOCK_6D 授权）

物理依据（CTRL-01 预注册负结果，冻结增益与预注册轨迹限定下）：严格 6D 任务零空间
真零、5D 接近段才有 1 维零空间、冻结增益闭环锚超差 ⇒ 装配必须相位切换而非单一 6D
任务。安全门授权语义直接编码这一事实：

1. **授权按相位签发**：装配请求新增 `phase`（enum=九词技能词表）与
   `phase_instance_id`；二者**进入 scenario_hash 定义域**（红队③教训：hash 定义域
   不含关键字段则红线无机器落点）。HMAC 授权绑定完整响应（沿用 v1 机制），响应含
   `phase_scope` ⇒ 授权天然绑定相位，跨相位重放在 MAC 验证即失败。
2. **相位切换 = 重新裁决点**：进入新相位必须发新 request（新 request_id、新
   scenario_hash、新鲜 evidence）；上一相位授权在切换瞬间作废
   （`expires_at ≤ 相位预算终点`）。沿用旧授权 → `ASM_PHASE_TRANSITION_UNADJUDICATED`。
3. **授权范围单调不外溢**：APPROACH_5D 授权只覆盖 5D 运动类（含其 1 维零空间自由度）；
   LOCK_6D 是独立裁决，其前置证据必须包含 ALIGN 相位的精公差达标记录
   （0.1 mm/0.5°，LITERATURE 级出处随行透传）。
4. 时间合同数值沿用 v1 冻结值（skew=0、capture_age≤2s、request_to_decision≤2s、
   deadline≤240s、validity≤300s）；相位预算是**额外**上界，不放宽 v1 任何一项
   （`thresholds_widened` 永久 false）。

### 2.3 UNKNOWN 纪律延伸到 assembly_success 八判据

八判据（接口 SSOT `assembly_success_criteria`）逐项三态化 PASS/FAIL/UNKNOWN：

- success ⇔ **八项全 PASS 且 provenance complete**；任一 UNKNOWN → 整体 UNKNOWN →
  决策 WAIT/BACKOFF，**永不 success**（GS-A `unknown_never_allow` 的判据级延伸）。
- 判据7 `flexible_response_within_validated_envelope`：包络=L1 认证域（r_defl<0.02
  绿区 ∪ 带 `LINEARITY_MARGINAL` 的黄区仅在非边界候选时计 PASS）；L2 未认证前不得
  以 L2 结果判此项。注意与 sim_10 口径的关系：sim_10 中 FLEX=UNKNOWN **不入判据**
  （可行域不因未知加分或减分），而装配 success 判据7 是**显式必查项**——UNKNOWN
  在此处是阻断性的。这是有意的收紧，不是口径冲突，须在论文措辞中说明。
- 判据6 `base_wheel_within_resources`：消费 CTRL-02 分账账本；W1-R12（轮力矩
  0.033>0.01 PROVISIONAL）未解决前，本判据最多 PASS-with-flag（透传
  `W1_R12_UNRESOLVED`），账本缺失 → UNKNOWN（`ASM_WHEEL_LEDGER_UNRESOLVED`）。
- 判据8 `provenance_complete` 复用 v1 provenance 结构（gate 路径/哈希模式/verdict/
  registry hash/scenario hash 五件套 + row binding）。

### 2.4 改动面与回归界

**新增（允许）**：
- `20_engineering/config/safety_gate/assembly/asm_request.schema.json`、`asm_evidence.schema.json`、
  `asm_response.schema.json`——全部 closed schema（`additionalProperties:false`，
  A4 白名单纪律）；contract_version 取新常量 `safety-gate-asm-v1`，与 v1 双栈并存。
- `20_engineering/config/safety_gate/assembly/asm_policy_v0.yaml`——相位×层白名单（§1 表）、相位
  预算、ASM reason_code 注册、八判据注册、W1-R12 flag、接口 SSOT 哈希锚定。
- `30_simulation/asm_safety_extension/`（ASM-04 实现目录）：**import 复用** `safety_core` 的
  规范化哈希（CANONICAL_JSON/CSV/YAML_SHA256_V1）、时间合同、HMAC 原语——只读复用，
  不 fork 不改。

**冻结面（禁改）**：`20_engineering/config/safety_gate/` v1 三 schema + `safety_policy_v1.yaml`；
`30_simulation/safety_00_runtime_gate/` 全目录；threshold registry
（sha256=400bcedc…7873，raw-byte 冻结）。

**回归界（扩展合入的机器判定）**：
1. SAFE-00 tests 47/47 重跑全绿；
2. `safety_00_gate_check.json` canonical hash 逐位不变；
3. v1 determinism 16 例裁决 payload 逐位相等（含 12 绕过例 0 成功复跑）；
4. 七绕过面封堵状态逐项复核不回退（映射见 §4.2）；
5. ASM 新测试独立目录独立计数，不并入 v1 的 47。
任一项不满足 → 扩展分支不得合并（fail-closed 合入语义）。

---

## 3. RQ4 实验设计：三注入 × 安全门行为矩阵

注入均为**预注册负例**（对齐 SAFE-00 预注册矩阵 v2 方法学）；期望行为全部 fail-closed，
**任何注入下 ALLOW 计数必须为 0**。列取四个代表相位；state/decision/reason_code 为期望值。

### I-A 模型失效注入（ROM 层失效/认证翻转）

| 子注入 | APPROACH_5D | COMPLIANT_INSERT | LOCK_6D | VERIFY_ASSEMBLY |
|---|---|---|---|---|
| A1 上游 gate verdict 翻转（sim_11 重跑 FAIL） | UNKNOWN/ABORT `GATE_VERDICT_MISMATCH` | 同左 | 同左 | UNKNOWN/ABORT（判据7 证据失效） |
| A2 gate JSON 篡改（哈希不匹配） | UNKNOWN/ABORT `GATE_ARTIFACT_HASH_MISMATCH`（B1 判例复用） | 同左 | 同左 | 同左 |
| A3 L1 认证降级 SCREENING_ONLY（认证前总锁情形） | UNKNOWN/WAIT `MODEL_CERTIFICATION_MISMATCH` | 同左 | 同左 | UNKNOWN/WAIT（success 禁止） |
| A4 需 L2 定案而 L2=UNAVAILABLE | UNKNOWN/WAIT `ASM_ROM_ESCALATION_UNAVAILABLE` | 同左（禁 L1 回落定案） | 同左 | 同左 |

### I-B 感知过期注入

| 子注入 | APPROACH_5D | COMPLIANT_INSERT | LOCK_6D | VERIFY_ASSEMBLY |
|---|---|---|---|---|
| B1 captured_at 超龄（>2 s，B2 判例） | UNKNOWN/WAIT `EVIDENCE_STALE` | UNKNOWN/**BACKOFF** `ASM_STALE_IN_CONTACT` | UNKNOWN/**BACKOFF** `ASM_STALE_IN_CONTACT` | UNKNOWN/WAIT |
| B2 未来时间戳（B10 判例） | UNKNOWN/ABORT `TEMPORAL_ORDER_INVALID` | 同左 | 同左 | 同左 |
| B3 状态源不在可信信道（A1 面） | UNKNOWN/ABORT `SOURCE_CHANNEL_UNTRUSTED` | 同左 | 同左 | 同左 |
| B4 协方差 assessment=FAIL/UNKNOWN | UNKNOWN/WAIT `STATE_COVARIANCE_NOT_PASS` | UNKNOWN/BACKOFF | UNKNOWN/BACKOFF | UNKNOWN/WAIT |

> 注：**接触相位内过期映射 BACKOFF 而非 WAIT** 是装配扩展的新语义——接触中"原地
> 等待"意味着持续不确定接触载荷，正确的 fail-closed 动作是退到已裁决的安全保持位
> （沿 RETREAT 已授权运动类）。此语义差异本身是 AG5 断言对象（§4.1 AG5-B）。

### I-C 接触不确定注入

| 子注入 | APPROACH_5D | COMPLIANT_INSERT | LOCK_6D | VERIFY_ASSEMBLY |
|---|---|---|---|---|
| C1 k_n 域外（>1e6 或 <1e4） | （无接触，不适用→域检仍拒）UNKNOWN/BACKOFF `ASM_CONTACT_PARAM_OUT_OF_SWEEP` | UNKNOWN/BACKOFF 同码 | UNKNOWN/BACKOFF 同码 | UNKNOWN/WAIT |
| C2 T_c 声明域外（<5 或 >100 ms）或理想冲量口径混入 | UNKNOWN/BACKOFF `OUT_OF_DOMAIN`（B3 判例） | 同左；能量级指标一律禁用（R2a） | 同左 | 同左 |
| C3 接触载荷证据缺失（判据5 无行） | — | UNKNOWN/ABORT `ASM_SUCCESS_EVIDENCE_INCOMPLETE` | 同左 | UNKNOWN/ABORT |
| C4 d_margin≤ε_tot 且 L2 不可用 | UNKNOWN/WAIT `ASM_ROM_ESCALATION_UNAVAILABLE` | 同左 | 同左 | 同左 |
| C5 latch_state=FAULT 注入 | — | — | **UNSAFE**/ABORT `ASM_LATCH_STATE_INVALID` | FAIL→非 success |

矩阵产出物：`results/asm_rq4_matrix.csv`（逐例 expected/actual/response_sha256/
deterministic，格式对齐 safety_00_gate_check.json cases 数组）；三注入全体进入
AG5-B 绕过计数（成功数必须恒 0）。

---

## 4. Gate AG5：机器断言 + fail-closed 语义复核（红队遗留项落位）

### 4.1 AG5 机器断言清单（产出 `results/asm_gate_check.json`，五诀全过才 PASS）

| 断言 | 内容 | 判据 |
|---|---|---|
| AG5-A | UNKNOWN 永不 ALLOW/success：装配全案例 `unknown_allow_count==0` 且 `unknown_success_count==0` | 恒等 0，一票 FAIL |
| AG5-B | 装配绕过集成功数==0：预注册 ≥12 例——相位越权、跨相位授权重放、latch 伪造、接触内过期不 BACKOFF、PROVISIONAL 剥离、k_n/T_c 域外走私、λ 取整走私（复用 B4）、八判据缺行、scenario_hash 不含 phase 的旧口径请求、SCREENING_ONLY 层出现在 ALLOW provenance、L2 未认证升级回落、词表外技能词 | `asm_bypass_success_count==0` |
| AG5-C | v1 回归界四项（§2.4）：47/47 全绿 + gate JSON 哈希不变 + 16 例逐位 + 七面不回退 | 全真 |
| AG5-D | ROM 域外 UNKNOWN：D 类域外探针（参数超凸包、T_c 超扫掠带、r_defl 超线性域、f1 超包络、真实多板 f2/f1=2.8 构型）全部返回 `UNKNOWN_OUT_OF_DOMAIN`；**任何数值预测即 FAIL** | 对齐 ROM GR4，一票 FAIL |
| AG5-E | 升级 fail-closed：规则升级目标 certification ∉ {CERTIFIED, 相位白名单内 PROVISIONAL} 时必须返回 `ASM_ROM_ESCALATION_UNAVAILABLE`（或 `BOUNDARY_UNRESOLVED`），**禁止低层回落定案**；必含负例判例："L2 未认证时 R3 红区（r_defl≥0.05）工况不得被 L1 定案"（红队 Required evidence 第 6 条原文落位） | 负例全拒 |
| AG5-F | 相位重裁决：每次相位切换新 request_id + 新 scenario_hash；跨相位重放旧授权 HMAC 验证必败 | 重放全败 |
| AG5-G | 决定性：同一冻结输入响应逐位相等（沿用 SAFE-00 determinism 口径） | bitwise equal |

### 4.2 红队七绕过面（攻击⑤ A1–A7）在装配扩展下的保持义务

SAFE-00 已封堵（磁盘证据），扩展必须逐项继承、AG5-C 复核不回退：

| 面 | SAFE-00 封堵证据 | 扩展保持义务 |
|---|---|---|
| A1 状态自证清白 | `trusted_state_channels=[HARNESS_TRUTH, INDEPENDENT_PHYSICS_GATE]` + `SOURCE_CHANNEL_UNTRUSTED` | 装配感知（锥面/销孔对准量）同信道纪律；地面演示=固定基座 B601+数字模型，digital truth 走 HARNESS_TRUTH |
| A2 scenario_hash 自报 | 裁决核重算 hash（design doc 步骤2）+ B11 `SCENARIO_HASH_MISMATCH` | phase/phase_instance_id 入 hash 定义域后同样重算 |
| A3 响应嫁接重放 | HMAC 绑定完整响应 + B1/B12 | phase_scope 在响应内 ⇒ 同一 MAC 覆盖 |
| A4 黑名单式校验 | 全 schema `additionalProperties:false` + B5/B7 `REQUEST_SCHEMA_INVALID` | 三份 asm schema 同为 closed schema |
| A5 缓存过期裁决 | 每次裁决重读 registry/gate JSON/CSV/YAML（design doc 步骤4–6） | 装配扩展逐调用重读接口 SSOT 哈希锚定 |
| A6 PROVISIONAL 剥离 | `provisional_flags/flex_status` 均 required + B5 判例 | `ASM_INTERFACE_PROVENANCE_PROVISIONAL_UNACKED` 延伸到接口参数出处等级 |
| A7 词表分裂/散文条件 | `STRUCTURED_V1` + B7 + `legacy_integration_conflicts.forbidden_in_contract_enum=[HOLD, INSUFFICIENT_EVIDENCE]` | 装配词表=九词技能表单一枚举；不得新增第二套决策词表 |

### 4.3 红队 ROM 五绕过组合（攻击⑥）封堵状态与遗留项落位

| 组合 | 现状 | 遗留落位 |
|---|---|---|
| 1 全局域使 L0 死锁 | **已封**于 SAFE-00 策略层：domains 按层拆分，L0 无 contact_T_c/panel_f1（`safety_policy_v1.yaml` domains 注释即为此修复） | rules YAML 本体（`in_domain` 统一域、R2a 不可达分支）仍未修订——**R1 实现前必须改**，AG5 附负例 |
| 2 升级目标不可用未定义 | SAFE-00 层已封：B6/D2 `L2_FAILED_NO_OPTIMISTIC_FALLBACK`、D1 `FALLBACK_DOMAIN_UNCHECKED`、response schema `accepted_for_finalization:false` | 选择器终态 `UNKNOWN_ESCALATION_UNAVAILABLE` 尚未写入 rules YAML——由本计划 `ASM_ROM_ESCALATION_UNAVAILABLE` + AG5-E 承接落位 |
| 3 伪机器可执行条件（散文 if / goto / 未注册层名） | 入口已封：`machine_condition_language=STRUCTURED_V1` + B7 判例拦散文条件进入裁决 | YAML 内 R4 "连续两档不降" 须形式化为 refine_history 状态机字段、goto 改显式 return、`L1_bandwidth_mode` 注册为 L1 mode——R1 修订项，AG5 负例覆盖 |
| 4 eps_tot 自举循环 | 部分封：certification 枚举含 SCREENING_ONLY + `MODEL_CERTIFICATION_MISMATCH` 拒不一致声明 | "R2 认证 PASS 前选择器整体 SCREENING_ONLY 总锁、禁止 finalize" 须明文入 rules YAML；AG5-B 含"SCREENING_ONLY 入 ALLOW provenance"负例 |
| 5 R3 引用 R5 量的次序依赖 | **未封**（纯 YAML 内部缺陷，SAFE-00 不消费该路径） | R1 修订：R3 黄区只设 tag、边界性统一 R5 判；R5 在 L2 层 on_unevaluable 显式改 `BOUNDARY_UNRESOLVED`；AG5 附求值次序负例 |

结论：**七面全封（保持义务转入回归界）；五组合中 1/2/3 已在 SAFE-00 策略层封堵、
2 的选择器终态与 4/5 属 ROM R1 实现前置修订项，全部已在 AG5 断言中给出机器落点**，
不存在"规划完成=默认安全"的敞口。

---

## 5. Task Card — ASM-04（安全线部分）

```yaml
task_id: ASM-04-SAFETY
title: 装配阶段 SAFE-00 扩展 + ROM 相位调度安全层 + Gate AG5
status: PLANNED            # 本文件为其规划 SSOT
depends_on:
  - SAFE-00 PASS 裁决核（只读 import，冻结面禁改）
  - 10_research/rom/model_fidelity_selection_rules.yaml 的 R1 修订
    （红队⑥组合 1/3/4/5 修订项为实现前置，见 §4.3）
  - 10_research/on_orbit_assembly/interface_ssot_draft.yaml v0→v1
    （B-Agent 出处细化；参数仍可 PROVISIONAL，但出处等级必须标注齐全）
  - ASM-02 显式解决 W1-R12 轮力矩 0.033>0.01 冲突（接口级阻塞候选；
    未解决前判据6 只能 PASS-with-flag 或 UNKNOWN）
deliverables:
  - 20_engineering/config/safety_gate/assembly/{asm_request,asm_evidence,asm_response}.schema.json
  - 20_engineering/config/safety_gate/assembly/asm_policy_v0.yaml   # 相位×层白名单+ASM reason_code 注册
  - 30_simulation/asm_safety_extension/{src,tests,results,docs}  # import safety_core 原语
  - results/asm_rq4_matrix.csv                        # RQ4 三注入行为矩阵逐例
  - results/asm_gate_check.json                       # AG5-A..G 机器裁决
gates:
  AG5: {assertions: [A_unknown_never_allow_or_success, B_bypass_zero,
        C_v1_regression_boundary, D_ood_unknown, E_escalation_fail_closed,
        F_phase_readjudication, G_determinism], verdict_vocabulary:
        [ASM_SAFETY_GATES_PASS_WITH_PROVISIONAL_PARAMS, ASM_SAFETY_GATES_FAIL]}
        # 接口 SSOT 无 MEASURED 字段 ⇒ 本阶段不存在无 PROVISIONAL 后缀的 PASS
non_goals:
  - 不重做 SAFE-00 已 PASS 的 47/47 与 12 绕过面（只回归复核）
  - 不实现 ROM 选择器本体（属 ROM R1 工单）；本卡只消费其修订后规则
  - 不声明"自主在轨组装已验证"（科学边界声明纪律，state_truth §科学边界）
rerun_triggers:
  - 接口实测公差/刚度/锁紧力到货（SSOT 转 MEASURED）
  - B601 夹爪 T_c 实测（W1-R13）
  - 杨恒帆板参数卡转正（判据7 包络重算）
  - 轮组选型冻结（W1-R12）
  - rules YAML 版本递增 / SAFE-00 任何上游 gate 重跑翻转
```

---
*本文件所有数字与判例均给出磁盘出处；未修改任何冻结证据。已知最大诚实风险：
接口 SSOT 全 PROVISIONAL/LITERATURE + 帆板质量占位（待办3）——装配安全结论在
参数转正前一律带 `_WITH_PROVISIONAL_PARAMS` 后缀，无例外。*
