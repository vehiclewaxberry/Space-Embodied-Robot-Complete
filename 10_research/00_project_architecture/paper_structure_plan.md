# 论文结构计划冻结

_任务类型：DOCS_ONLY_ARCHITECTURE_FREEZE；对象：Paper 1 结构、证据绑定与引文成熟度；本文件不是完成稿或投稿就绪声明。_

---

## 📋 论文定位

### 推荐题目

> Strategy Selection under Momentum and Stability Constraints for Non-Cooperative Spacecraft Capture: Feasibility Maps and a Binding-Gate Criterion

中文工作题目：

> 动量与稳定性约束下的非合作航天器捕获策略选择：可行域地图与绑定门判据

### 研究问题

在冻结的航天器、目标、执行器预算和模型适用域内：

1. 哪些目标状态对给定策略是物理可行的？
2. 当前最先绑定的动量、姿态速率、资源或稳定性 Gate 是什么？
3. 为什么策略选择不能由单一几何操纵度或无条件算法排名决定？

### 当前论文状态

`STRUCTURE_FROZEN_EVIDENCE_BINDING_INCOMPLETE`

可以进入“结构定稿、逐主张绑定、核心文献精读”阶段，但不能宣称终稿完成。主要原因是 [旧 Paper 1 架构](../paper1_architecture.md) 内仍同时存在 sim_12 已 PASS 与“待 Gate/0%”的历史措辞，以及“59 条检索语料”与当前 45 条 manifest 的口径冲突。

## 🎯 贡献边界

### 可以规划的贡献

| 编号 | 贡献 | 当前证据 | 主状态 | 禁止外推 |
| --- | --- | --- | --- | --- |
| C1 | 冻结约束下的策略可行域与 binding gate 表达 | sim_10、sim_12 | `VERIFIED` | 通用全局最优策略 |
| C2 | 捕获前后动量、姿态与资源的可审计账本 | sim_06、sim_10、sim_12 | `VERIFIED/LIMITED` | 真实硬件资源资格 |
| C3 | 有限接触带宽对理想冲量模型的边界说明 | sim_11 | `LIMITED` | 高保真硬件接触模型 |
| C4 | fail-closed 证据纪律与负结果保留 | SAFE、CTRL-01、e15、Wave1 | `VERIFIED/NEGATIVE_RESULT` | 飞行级安全认证 |

### 不进入 Paper 1 贡献

- 在轨搭建：只允许在应用背景或 future work 中出现
- VLA/具身模型：只允许作为未来候选生成层出现
- 实时数字孪生：当前不存在 DT3/DT4 证据
- 硬件或微重力验证：H0–H3 未完成
- “国内首创”“世界首次”：未完成系统查新

## 🏗️ 论文逻辑

```mermaid
flowchart LR
    accTitle: Paper 1 论证链
    accDescr: 本图只表示论文论证组织而非科学依赖 DAG，sim_10 直接支撑 sim_12，sim_11 仅作为独立的 L3 模型边界证据。

    question["冻结捕获问题"] --> ledger["动量资源账本"]
    ledger --> map["sim_10 可行域"]
    ledger --> bandwidth["sim_11 模型边界"]
    map --> selection["sim_12 绑定门"]
    bandwidth --> limits
    selection --> safety["SAFE 与负结果"]
    safety --> conclusion["条件性结论"]
    conclusion --> limits["适用域与重跑触发器"]

    classDef action fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#1e3a5f
    classDef caution fill:#fef9c3,stroke:#ca8a04,stroke-width:2px,color:#713f12

    class question,ledger,map,bandwidth,selection,safety,conclusion action
    class limits caution
```

该图是章节论证组织，不是第二套项目 DAG；冻结科学主边仍为 `sim_10→sim_12→SAFE`，sim_11 只从 L3 侧限定模型适用域。

## 📑 正文章节结构

### 1. Introduction

目标：

- 说明非合作目标捕获同时受自由漂浮耦合、冲量、姿态和执行器资源约束
- 把研究问题限制为冻结预算下的策略可行性和 binding gate
- 明确论文不解决完整轨迹规划、硬件资格、VLA 或在轨验证

证据入口：

- [文献 manifest](../../50_literature/references/manifest.yaml)
- [双任务文献综合](../on_orbit_assembly/dual_mission_literature_synthesis.md)
- [现有 Paper 1 架构](../paper1_architecture.md)

### 2. Related Work

建议分为四个小节：

1. 自由漂浮动力学、GJM 与 RNS
2. 捕获冲量、阻抗与柔顺接触
3. 翻滚目标跟踪、捕获与消旋
4. 可行域、资源约束与本文边界

引文纪律：

- M3 文献可进入方法谱系和细粒度比较
- M2 文献在补完整阅读卡前，只用于题名、主题和候选引文定位
- M1 的 `gerstmayr2013ancfreview` 只能登记缺口，不能转述全文结论
- 未进入当前 `manifest.yaml` 的“2020 执行器协同分配、2025 MPC、Aghili 2024”等条目不得进入正式稿

### 3. Problem Formulation

应包含：

- 参考系、系统质心和自由漂浮假设
- 内部捕获冲量与外部角冲量的记账口径
- 冻结的轮组、推力器、姿态速率和稳定性资源类别
- S1/S2/S3a/S4 的策略定义
- 四类 Gate 的 fail-closed 语义

不得把 Markdown 摘要中的数字手抄为真值。每个数值都必须映射到当前机器结果字段。

### 4. Numerical Method and Evidence Discipline

应包含：

- 无量纲或统一单位口径
- 矢量冲量与守恒残差
- sim_06/sim_10 锚点交叉核对
- sim_11 理想冲量与有限接触带宽的退化关系
- registry、哈希、provisional 字段与 UNKNOWN 处理
- 测试 PASS 与科学 Gate PASS 的区别

### 5. Results

建议顺序：

1. S1 四区域基线
2. 几何指标与系统级可行性指标的差异
3. 有限接触带宽与 provisional 模型边界
4. 策略可行性阶梯与 binding gate
5. 代表性锚点的逐门解释

只允许从当前冻结结果重排已有图表；本任务不生成新图、不重算数据。

### 6. Discussion

应回答：

- 为什么不存在无条件“最好”的捕获策略
- 结构门、动量门、速率门和资源门如何改变选择
- 为什么 `EXECUTE` 解释与真实授权不同
- CTRL-01、e15、Wave1 的负结果如何限定适用域
- 文献方法与本项目机器证据之间的区别

### 7. Limitations

必须原样保留：

- sim_10 和 sim_12 未把 FLEX 纳入判据
- sim_11 使用 provisional 帆板参数与接触时间
- CTRL-02 使用 provisional 执行器范围
- e15 ANCF 认证未闭合
- 无 markerless 项目级 HIL Gate
- 无自由漂浮、微重力或在轨硬件验证
- 无 VLA 实体、实时 DT3/DT4 或装配科学 Gate

### 8. Conclusion

结论只能总结：

> 在冻结模型与资源范围内，项目形成了可机器审计的捕获可行域、有限带宽边界和 binding-gate 策略选择证据。

不得把该结论升级为通用自主捕获、空间碎片清除完成或飞行资格。

## 📊 主张—证据绑定

| 论文主张 | 权威证据 | 主状态 | 允许措辞 | 禁止措辞 |
| --- | --- | --- | --- | --- |
| sim_10 可行域完成 | [sim_10 Gate](../../30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json) | `VERIFIED + FROZEN` | 9002 点冻结可行域通过其 Gate | 全任务或硬件可行 |
| 有限带宽模型通过 | [sim_11 Gate](../../30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json) | `LIMITED + FROZEN` | 带 provisional 参数通过 | 已完成高保真接触认证 |
| 策略 Phase 1 通过 | [sim_12 Gate](../../30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json) | `VERIFIED + FROZEN` | 16 个 Phase 1 单元通过 | 完整四策略全域完成 |
| SAFE fail-closed 有效 | [SAFE Gate](../../30_simulation/safety_00_runtime_gate/results/safety_00_gate_check.json) | `VERIFIED + FROZEN` | 决策核合同通过 | 获得真实执行授权 |
| 6D RNS 收益不足 | [CTRL-01 Gate](../../30_simulation/control_01_end_effector_tracking/results/control_01_gate_check.json) | `NEGATIVE_RESULT + FROZEN` | 冻结场景下 REPEAT | RNS 普遍无效或已解决 |
| 柔性认证未闭合 | [e15 Gate](../../30_simulation/e15_ancf_certification/results/gate_summary.json) | `NEGATIVE_RESULT + FROZEN` | 跨解算器 Gate REPEAT | ANCF 已认证 |
| 本地演示可回放 | [competition Gate](../competition_convergence/competition_gate_check.json) | `LIMITED + LOCAL_ONLY_UNTRACKED` | 本地离线包 17/17 | committed、实时或命令闭环 |

## 🖼️ 图表计划

| 编号 | 计划内容 | 现有来源 | 当前状态 | 使用条件 |
| --- | --- | --- | --- | --- |
| Fig. 1 | 系统、策略时间线与四门概念图 | 现有架构和配置 | `PLANNED` | 仅作问题定义示意 |
| Fig. 2 | 同操纵度、不同捕获后角速率 | [E1 图](../../30_simulation/sim_09_grasp_evaluator/figures/fig_e1_g1_vs_g2.png) | `LIMITED + FROZEN` | 不泛化到所有构型 |
| Fig. 3 | S1 四区域可行域 | sim_10 现有结果 | `VERIFIED + FROZEN` | 只重排已有数据 |
| Fig. 4 | 理想冲量与有限带宽边界 | sim_11 现有结果 | `LIMITED + FROZEN` | 注明 provisional |
| Fig. 5 | S1/S2 动量账本 | sim_12 机器字段 | `PLANNED` | 必须逐字段绑定 |
| Fig. 6 | 策略可行性阶梯 | sim_12 机器字段 | `BLOCKED` | 先解决旧架构状态冲突 |
| Fig. 7 | 代表案例逐门失效 | sim_12 机器字段 | `BLOCKED` | 同上，不得手抄数字 |
| Table 1 | 符号、参考系和参数来源 | 配置/SSOT | `PLANNED` | 区分 frozen 与 provisional |
| Table 2 | 策略及动量成本账本 | sim_10/12 | `PLANNED` | 不新增结果 |
| Table 3 | Gate 定义与 fail-closed 规则 | Gate JSON | `VERIFIED` | 保留 exact verdict |
| Table 4 | 策略/锚点 binding gate | sim_12 | `BLOCKED` | 逐字段核验后填 |
| Table 5 | 文献方法对比 | 阅读卡 | `LIMITED` | M2 精读后填细节 |
| Table 6 | 局限与重跑触发器 | 本冻结包 | `VERIFIED` | 不写乐观 PASS |

## 📚 文献成熟度

当前唯一题录真值来自 [manifest](../../50_literature/references/manifest.yaml)：

| 成熟度 | 数量 | 资产状态 | 论文用途 |
| --- | ---: | --- | --- |
| M3：题录 + PDF + 完整阅读卡 | 23 | `VERIFIED + FROZEN` | 可做方法与边界论证 |
| M2：题录 + PDF，无完整阅读卡 | 21 | `LIMITED + FROZEN` | 候选引文；先补精读 |
| M1：题录元数据，无全文 | 1 | `BLOCKED` | 只登记来源缺口 |

补充统计：

- 45 条唯一题录与 BibTeX key
- 44 份有效本地 PDF
- 38 条 DOI 主记录：Crossref `VERIFIED=35`、`NOT_FOUND=3`、`MISMATCH=0`
- 7 条 arXiv 主记录元数据已核验
- mission line：debris removal 13、on-orbit assembly 3、both 9、platform common 20

这些数字证明文献工程的完整性，不证明 44 篇都已精读，也不证明任一论文方法已在本项目复现。

## 🔍 起草前必过门

1. 清理 [paper1_architecture.md](../paper1_architecture.md) 内 sim_12 “已 PASS”与“待 Gate/0%”冲突
2. 把摘要、贡献、Fig. 5–7 的每个数字映射到当前 Gate/原始字段
3. 把 related work 收敛到当前 45 条 manifest，移除未入库比较文献
4. 为 Paper 1 核心 M2 原始论文补完整阅读卡
5. 对任何“首次”主张执行正式查新；未完成前一律删除

以上均为未来文档工作门，不授权新仿真。

## 🚫 Paper 2 与远期主题

在轨搭建、双任务共平台、VLA 工具调用与实时数字孪生可以形成未来 Paper 2 候选；其主证据状态统一为 `PLANNED`，起草与实施授权为 `BLOCKED`：

- 没有 ASM-00/01/02 正式科学结果
- 没有 H0–H3 硬件结果
- 没有 VLA 对照实验
- 没有 DT3/DT4 状态流与双向闭环

因此 Paper 2 不进入当前交付，也不能用于抬高 Paper 1 的成熟度。

## ✅ 结构冻结验收

- [x] Paper 1 只围绕已有捕获可行域与策略证据
- [x] 每个主要主张都有 Gate 路径和禁止外推
- [x] 文献归档成熟度与精读成熟度已分离
- [x] 旧“59 条语料”口径被标为待清理，不再作为真值
- [x] 装配、VLA、硬件与实时孪生均未写成当前贡献
- [x] 没有生成新图、新数据或新科学结论

结构冻结后状态为 `STOP_AFTER_ARCHITECTURE_FREEZE`；正式起草需由新的明确任务授权。
