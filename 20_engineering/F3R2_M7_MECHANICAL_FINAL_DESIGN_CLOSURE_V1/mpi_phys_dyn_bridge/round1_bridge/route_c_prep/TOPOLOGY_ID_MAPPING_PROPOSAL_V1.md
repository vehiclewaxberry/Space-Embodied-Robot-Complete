# TOPOLOGY_ID_MAPPING_PROPOSAL_V1 — 拓扑命名对照与 RC-C 冲突处置提案（待 Owner 裁决）

- 生成时间：2026-08-23T17:22:11+08:00（宿主机本地时钟，Asia/Shanghai）
- 作者：AGENT-2（Wave-2a Route-C 文本准备）
- 性质：**对照提案**。不裁决、不改写任何既有工件、不授权任何拓扑选择。两套命名空间现状均保持冻结。
- 输入锚点：
  - 交接书语义：`round0_handover/02_route_c_inputs/ROUTE_C_PHYSICAL_INPUT_INVENTORY_V1.json`（sha256 `b91611f9…353b7`）`topology_input_readiness_matrix`；
  - 仓库语义：`08_route_c/02_pre_cad_parametric_guided_route_search/02_search/ROUTE_C_PARAMETER_SPACE_V1.yaml`（sha256 `230D8C3C…01D489`）与 `08_route_c/ROUTE_C_CONCEPT_TRADE_V1.csv`（sha256 `5553B3CA…0411A`）。

## 1. 两套命名空间的逐字定义

### 1.1 交接书语义（主控/round0 盘点标签）

| 标签 | 逐字语义 | 来源 |
|------|----------|------|
| C-A | joint-local Ω loops | round0 盘点 readiness matrix |
| C-B | semi-captive dress-pack | 同上 |
| C-C | mini cable-carrier hybrid | 同上 |

### 1.2 仓库语义（冻结工件标签）

| 标签 | architecture（逐字） | status（逐字） | 来源 |
|------|----------------------|----------------|------|
| RC-A | captive-guided-hybrid | PROPOSED_FOR_ODR42_NOT_SELECTED | 参数空间 YAML / 概念权衡 CSV |
| RC-B | all-joint-semi-captive-carrier | ALTERNATE_NOT_SELECTED | 同上 |
| RC-C | dual-dress-pack-hybrid | TRADE_ONLY | 同上 |
| RC-D | improved-free-loop | REJECTED_AS_PRIMARY_CONCEPT | 同上 |

仓库侧附加逐字事实：参数空间 `mutual_exclusion_rule` 规定 RC-A/RC-B/RC-C/RC-D 恰好其一在诊断分支激活，**结果跨分支禁止平均**；RC-D 的 rejection_basis 为 "Does not eliminate the uncontrolled fold and snag mechanisms observed in Route-B."

## 2. 对照提案（解释性映射，非权威）

| 交接书 | 最近邻仓库分支 | 语义差（必须随映射保留的警示） |
|--------|----------------|--------------------------------|
| C-A joint-local Ω loops | RC-A captive-guided-hybrid | 非等同：RC-A 除 J1 捕获式定曲率盒、J5/J6 定曲率腕部包络外，还含 J2/J3 父子半捕获移动导向或滚动环、J4 side-bypass 与 guided-loop 互斥权衡——不只是"关节局部 Ω 环"。 |
| C-B semi-captive dress-pack | RC-B all-joint-semi-captive-carrier | 非等同：RC-B 逐字为全部六关节半捕获载体；交接书 C-B 的 "dress-pack" 表述未声明全部六关节均为载体。 |
| C-C mini cable-carrier hybrid | **无精确仓库分支** | 最近邻为 RC-B（载体硬件）与仓库 RC-C（dual-dress-pack-hybrid，不同概念）。交接书 C-C 需要 P04/P12（载体行程/尺寸），仓库 RC-C 无载体硬件、为电源/数据双 dress-pack 分离方案。 |
| （无交接对应） | RC-D improved-free-loop | 交接书三候选无此概念；仓库已 REJECTED_AS_PRIMARY_CONCEPT。 |

## 3. RC-C 冲突详述

- 冲突：字面短串 "C-C" 在交接书 = mini cable-carrier hybrid；字面短串 "RC-C" 在仓库 = dual-dress-pack-hybrid。两个概念在机械上不同（前者含微型拖链载体硬件；后者为电源/数据分离双 dress-pack，J2/J3 分离滚动环、J4 分离局部分流、J5/J6 双腕部包络）。
- 风险：若不作处置，后续任何工件裸写 "C-C"/"RC-C" 都可能把需求与就绪度挂错概念——例如 P04/P12 对交接书 C-C 是 REQUIRED__HOLD，但对仓库 RC-C 在拓扑级并不需要；就绪度矩阵的 0/13 行会错绑到无载体的概念上。
- 现状纪律：round0 盘点已把该映射标为解释性并逐行标注冲突；本提案将其升级为正式处置请求。

## 4. 处置方案（二选一，待 Owner 裁决）

### 方案 M1：交接侧改名（退役裸 "C-C"）

- 做法：交接书语义侧把 "C-C mini cable-carrier hybrid" 改名为不与仓库冲突的新 ID（建议候选：`C-MC`，取 mini-carrier 义；或 `C-D`，但须注意与仓库 RC-D improved-free-loop 的字面邻近）。仓库 RC-A..RC-D 保持冻结、一字不改。
- 历史处理：round0 盘点 JSON/MD 与主控任务书中既有 "C-C" 引用**不改写**，以 alias 注记形式在新工件中声明 "handover C-C ≡ C-MC"。
- 优点：单一无冲突命名空间；后续工件无需限定符；gate 脚本无需新增命名检查。
- 缺点：交接历史文本与新 ID 之间需要永久 alias 注记；改名决议本身须入 ODR 记录。

### 方案 M2：双命名空间强制限定符

- 做法：两套标签都保留，但此后一切新工件中必须写限定形式——`HANDOVER::C-A/C-B/C-C` 与 `REPO::RC-A/RC-B/RC-C/RC-D`（或等价后缀 `@handover`/`@repo`）；并发布一份机器可读对照表，内含显式断言 `HANDOVER::C-C NOT_EQUAL REPO::RC-C`。
- 历史处理：两侧历史文本均不动。
- 优点：零改写，对既有证据链侵入最小。
- 缺点：依赖纪律执行，裸写风险长期存在；下游 gate/校验需新增命名限定检查；跨 swarm 交接时每轮都须重述该纪律。

### 两方案共同禁令

- 无论 M1/M2，均禁止把交接书 C-C 与仓库 RC-C 互相绑定证据、需求或就绪度；禁止借改名/限定符把任何 HOLD 量提升为 AVAILABLE。

## 5. 待 Owner 裁决清单

1. M1 vs M2 二选一（本提案不推荐立场，供裁决）；
2. C-A↔RC-A、C-B↔RC-B 的"最近邻解释性映射"是否接受为**工作映射**（接受后仍非权威，仅用于跨工件检索）；
3. RC-D（无交接对应、仓库已 REJECTED_AS_PRIMARY_CONCEPT）在后续工件中的记录方式：保持仓库原样引用，还是在交接侧补一条显式 "no-handover-counterpart" 注记。

`gate_state` 维持 `HOLD__AWAITING_MPI_GATE`；本提案不产生任何 release credit；`next_stage_authorized = false`。
