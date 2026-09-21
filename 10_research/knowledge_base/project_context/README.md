# 项目任务、研究问题与 7 月状态沿革

2026-09-06 合并：任务/状态/问题三份摘要、`research_state_v3.md`、零基础全景，以及原 `aerospace/` 三份领域说明和 `decisions/` 两份决策索引。十份原文已按原路径保存到[文件整理账本](../../../01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/loop0_20260905/screening/full_project_catalog.sqlite)。本页去除重复介绍和状态表，保留独有概念、日期差异、限定和负结果。

这里的阶段状态仅适用于 **2026-07-18 至 2026-07-23**，不是今天的任务许可或工程状态。现行入口是 [PROJECT_MAP](../../../PROJECT_MAP.md)；后续机械沿革见[7 月底至 8 月历史综述](../../../01_project/competition/archive/ROOT_HISTORY_20260729_20260810.md)。本次未重跑科学计算或硬件验证。

<a id="mission"></a>
## 任务与证据链

项目对象是 12U 级服务航天器和 B601 六自由度机械臂，研究对 150 kg 碎片或 22 kg 目标星等非合作翻滚目标的操作。目标可能缺标准接口，其位姿、转速、质量和惯量也可能不完全已知；动臂与捕获冲击会扰动自由漂浮的服务星。因此需要依次判断任务是否可行、哪个动量/姿态/资源约束先绑定、应采用哪种候选策略，以及证据是否支持继续、修改或放弃。捕获不能等同于消旋、碎片清除或离轨处置。

当时的科学主链是 `冻结输入 → sim_10 可行域 → sim_12 策略选择 → SAFE 证据核 → DT2 离线解释`。sim_11 为有限接触带宽和柔性参数边界的 L3 侧证据；e15、CTRL-01/02、Wave1 各自的负结果或限定不由主链覆盖。科学结论以原机器裁决及其配置为准，测试通过不是独立科学通过。

演示水印为 `OFFLINE EVIDENCE REPLAY / NO REAL-TIME SYNCHRONIZATION / NO COMMAND OUTPUT`。具身候选层提出任务解释、候选技能、工具调用计划和失败恢复建议；这不等于已经实现关节力矩、推进器控制或安全授权。

<a id="questions"></a>
## 研究问题与能力路线

Paper1 问题是：给定航天器、目标、执行器预算与适用域，哪些目标状态对指定策略可行，哪个约束最先绑定，为什么单一几何操纵度或无条件算法排名不足以选择策略。当时结构状态为 `STRUCTURE_FROZEN_EVIDENCE_BINDING_INCOMPLETE`；贡献需要绑定具体结果和文献，而非仅凭论文目录已经完成。

| 问题 | 已有或规划来源 | 7 月的范围 |
|---|---|---|
| 捕获冲量与组合体状态/资源需求 | sim_06、sim_10、sim_12 | 冻结模型中的 VERIFIED/LIMITED 证据 |
| 有限接触带宽与保真度 | sim_11 v1.1 | 参数 provisional；Paper1 方法与 Paper2 候选 |
| 几何抓点与稳定性差异 | sim_09 | 69 例同操纵度、结局约 2× 散布是动机证据，不是通用定理 |
| UNKNOWN、占位与负结果的任务解释 | SAFE、e15、CTRL-01、Wave1 | fail-closed 软件证据及真实负结果 |
| 带界不确定目标操作 BRIDGE-UT | Q3+Q4 | PLANNED，不新增 Q；需状态信封、UQ、OOD、基准与 SAFE 扩展合同 |
| 1U/2U 预制接口模块装配 Q6-L1 | Q6、ASM 规划 | `PLANNED_SCOPE_FROZEN_EXECUTION_BLOCKED`；研究 5D 接近到 6D 锁紧、接口、连续多点接触/卡滞与分阶段控制 |
| 大型模块化结构 Q6-L2 | 远期路线 | PLANNED + DEFERRED，不由 Q6-L1 或捕获 PASS 外推 |
| markerless 感知、VLA、DT3/DT4 | 数据/候选层/实时孪生规划 | 数据协议、统一状态流与时钟、双向接口、项目级 HIL 未建立 |

两条应用线可共享动力学、资源账本和 fail-closed 方法，不能互相继承验证。完整问题合同见[Q1–Q6](../../research_questions/README.md)、[Paper1 架构](../../paper1_architecture.md)、[双任务文献综合](../../on_orbit_assembly/dual_mission_literature_synthesis.md)和[空间具身机器人路线](../../space_embodied_robotics/research_roadmap.md)。

<a id="history"></a>
## 按日期理解状态，不拼接为当前裁决

**7 月 18 日 v3 审计**以当时 git `12df268` 与模块裁决为源：sim_01–08、sim_09、e15/e16、sim_10 已作冻结资产；sim_11 v1.1 为冻结并允许参数转正触发的扩展；sim_12 策略选择仍写 P0 未完成，Physics Agent MCP 为后续。其 sim_10 “72k 行 gates CSV”是结果行口径，不能改写为 72k 个独立扫描点。e16 记 `PASS_WITH_GEOMETRY_AND_FLEX_LIMITATIONS`、216 例刚体同步，引用前需保留几何/柔性限制。

**同日零基础全景**已经写 sim_12 Phase1 PASS，与 v3 的“未完成”处于不同记录进度；没有精确时间证据时不自行排序。全景中“五层证据全部通过”“binding-gate 无先例”等概括也不能升级为所有早期模块独立通过或当前新颖性结论。它的 Agent→地面 H0–H3→比赛材料日历只是当时排期，未证明这些任务如期发生。

**7 月 20–22 日 v4 / 总览**记录 sim_12 Phase1、SAFE 与比赛离线 Lane C 已形成结果，Wave1 保留 REPEAT；ASM-00 为 `ASM00_AG0_BLOCKED_BY_INTERFACE`，九判据合同完成但等待绑定。完整原记录保留在[research_state_v4.md](../../research_state_v4.md)和[20260720 总览](../../../01_project/competition/项目现状总览_20260720.md)。v4 被比赛合同按路径/哈希引用，所以本次没有合并删除它。

**7 月 23 日知识库快照**记 `ARCHITECTURE_FROZEN_WITH_INTERFACE_AND_VALIDATION_BLOCKERS`、`FRAMEWORK_CONVERGED_WITH_INTERFACE_BLOCKERS`；长期路线为 `RESEARCH_OS_03_SPACE_EMBODIED_ROBOTICS_INITIALIZED / NO_NEW_EXECUTION_AUTHORITY`。当时 Prototype A0/A1 只是 `DIGITAL_MODEL_ARCHITECTURE_ONLY`，候选一致性 `BLOCKED_BY_EVIDENCE`；A2、模型构建和新仿真未执行。`NO_NEW_SIMULATION — STOP_AFTER_ARCHITECTURE_FREEZE` 是该阶段规则，不覆盖本轮用户授权。

<a id="evidence"></a>
## 原状态表的证据边界

| 资产组 | 7 月 23 日解释 |
|---|---|
| sim_01–04 | LIMITED + FROZEN；没有补造独立 scientific PASS |
| sim_05–06 | VERIFIED + FROZEN；19.20° 基座扰动、约 3.06°/s 捕获后旋转是数字锚点 |
| sim_07–08 | LIMITED + FROZEN；约 92× 激振与 3.65 N·m·s/12× 轮组预算受组件模型和参数限制 |
| sim_09/E1、e16 | LIMITED + FROZEN；campaign/同步扫描不等于 formal safe；e16 formal safe=0、ANCF 未运行 |
| E1.5、e15 core/ANCF | NEGATIVE_RESULT + FROZEN；SAFE 候选与跨求解认证未闭合，e15 为 `REPEAT_ANCF_CERTIFICATION` |
| sim_10 / sim_12 Phase1 | VERIFIED + FROZEN；刚体资源假设下可行域与 16 个策略证明单元；FLEX 未入判据 |
| sim_11 v1.1 | LIMITED + FROZEN；理想瞬时冲量下模态能判据不适定的失败，经有限接触窗修复；不等于实物资格 |
| SAFE-00 | 47/47，PENDING_REVIEW，next=false；UNKNOWN 不变 ALLOW |
| CTRL-01 / CTRL-02 | 前者在冻结增益/预注册轨迹下 REPEAT；后者仅 PASS_WITH_PROVISIONAL_SCOPE，7/16 限 R5 执行器/时间窗，硬件有效稳定性未评估 |
| Wave1 / 研究仪表板 | WAVE1_REPEAT / REPEAT_CORE；离线综合不改原裁决 |
| ASM-00 / ASM-01/02 / H0–H3 | 前检仅接口证据，历史 LOCAL_ONLY_UNTRACKED；正式装配和硬件链 BLOCKED |
| Physics-Gated Agent / VLA | PLANNING_ONLY；状态信封、Physics Tool、SAFE 扩展与执行链没有实现 |

原快照的文献账为 45 题录、44 PDF、29 完整阅读卡、15 份有 PDF 无完整卡、1 缺全文 `gerstmayr2013ancfreview`。文件完整性不等于精读；后续新增阅读卡不会回写这些历史计数。现行题录以[manifest](../../../50_literature/references/manifest.yaml)为准。

<a id="inputs"></a>
## 当时待补输入与复核触发器

帆板 0.348 kg/侧是 SSOT 占位，文献登记工作流 `wf_08f5d04f` 产生的候选不能替代杨恒参数卡；真实质量、模态、刚度/阻尼可能改变原“柔性反馈可忽略”判断。T_c=20 ms 也是未测名义值，已有 5–100 ms 扫掠，不代表夹爪实测。替换参数需要明确来源与受影响的 sim_11/下游新版本复核。

轮力矩、轮动量、最小脉冲量转正触发资源/控制支路复核；正式装配需明确接口 SSOT 与成功判据绑定；新核心安全刚体候选才构成新 e15 认证输入。7 月文献审计 5/6 覆盖、contact-impulse 专线与存在性独立核查待补，是当时缺口，不是本次查新结果。旧多代理工作还提出 journal/断点恢复以避免用量中断丢失记录；本页不保留已失效的周历作为当前任务表。

<a id="domain-methods"></a>
## 领域概念与文献使用边界

本节吸收的五份领域/决策笔记没有各自标注独立日期；其中“当前”“禁止实现”等属于原知识库规划语境，不新增今天的权限限制。

自由漂浮捕获后需要重新计算组合体质量、惯量、角速度和执行器余量，再判断轮组、推力器与中止策略。末端可达、单个可行锚点或 e15 coverage PASS，均不能推出所有目标安全或安全候选存在。刚体模型能给动量和大尺度姿态，不能自动给出柔性振铃、应变能、峰值接触力和多模态响应。

原笔记区分：FFR 用浮动参考系在刚体平台上表述柔性部件；ANCF 用绝对节点坐标表述柔性体，应用仍需收敛和跨求解器认证；有限接触带宽用有持续时间的接触窗处理瞬时冲量对模态能指标的不适定解释。这三者不是替代同一个物理问题的三个产品选项。sim_07、e15、sim_11 和 FLEX 未入 sim_10/12 判据的状态已在上表列出，不在这里重复计数。

文献键 `yoshida1999vibrationsuppression`、`nenchev1999flexiblerns` 分别提供 RNS/柔性抑振桥接与柔性安装机械臂背景；`gerstmayr2008elasticline`、`gerstmayr2023exudyn` 提供 ANCF 表示和交叉验证工具背景；缺全文的 `gerstmayr2013ancfreview` 只登记缺口，不推断其全文结论。GJM/RNS 是理论谱系，阻抗/柔顺腕/移动副是接触设计候选依据，均不证明“越软越安全”或本项目已经复现某控制器。

SpaceMind、OpenVLA、OpenPI 与综述可用于任务分解、动作表示和工具编排；克隆仓库或固定提交不等于集成、训练和复现。旧笔记中的 SPEED/SPEED+ 为未来位姿域差资源，不代表项目数据已下载、协议已执行；markerless HIL 与在轨装配同样不能从外部文献推得完成。

L4 的任务语义、技能序列、工具需求、证据缺口和恢复建议需要经 L0/L3 求值与 SAFE，再进入明确授权的确定性控制。直接关节力矩/速度/位置命令、推进器点火、绕过 SAFE 的授权、把缺失或 provisional 伪装为已知安全值，不属于这些旧候选合同的输出。来源可沿[系统架构](../../00_project_architecture/system_architecture.md)、[仿真场景](../../00_project_architecture/simulation_scenario_map.md)、[Agent 管理](../../00_project_architecture/agent_management_plan.md)及[数字孪生计划](../../00_project_architecture/digital_twin_plan.md)追溯。

<a id="decisions"></a>
## 原架构索引与拒绝路线

下表保留原 ADR 编号和当时标签；这些是对已有来源的索引，不是原始决策凭证或新批准。

| 原 ID / 标签 | 保留的决策含义 |
|---|---|
| ADR-001 / FROZEN | 机器裁决、原始结果、绑定哈希优先于摘要与测试 |
| ADR-002 / FROZEN | L0 任务、L1 SAFE、L2 控制、L3 世界模型、L4 候选、L5 验证分层；L4 无执行授权 |
| ADR-003 / FROZEN | 旧比赛主链为可行域→策略→SAFE→离线解释；装配/VLA/实时孪生/硬件未计完成 |
| ADR-004 / FROZEN | e15、CTRL-01、Wave1 等负结果保留 |
| ADR-005 / VERIFIED | integration 归研究治理，离线 dashboard 归工具域；来源为 REORG03-A |
| ADR-006 / CURRENT | 旧 ASM-00 名称不代表正式 SSOT；当时只登记职责、不移动冻结胶囊 |
| ADR-007 / CURRENT | 新一般资料按域落位；外来输入进 inbox，绑定历史路径需查消费者 |
| ADR-008 / CURRENT | 知识库只作薄索引，不复制状态、题录、阅读卡或 Gate 真值 |
| ADR-009 / CURRENT | 任务能力轴与自主性轴独立；BRIDGE-UT/Q6-L1 可并行建证、不能继承 PASS |
| ADR-010 / CURRENT | Physics Agent 入口位于 knowledge_base/physics_agent，不在根另建副本 |
| ADR-011 / CURRENT | Physics Tool 是当时未实现的确定性证据绑定评价接口，不是 foundation model |

拒绝路线的原因归并为三类。**证据失真**：用测试/外部论文/回放替代科学通过、放宽阈值或隐藏失败、把 44 PDF 当作 44 篇精读、依赖未形成的装配结果支撑比赛主线，均缺对应证据；新证据只能支撑新范围，不能重写旧记录。**角色越界**：模型直出命令或授权、平行 project_status_latest 真值、根目录复制 physics_agent/模型/题录/Gate、用“博士 Q1–Q3”覆盖既有 Q1–Q6，均破坏既有职责；长期主题可用 RT-A/RT-B/RT-C 表述而不重编号。**成熟度夸大**：DT2 不能称实时 DT3/DT4，历史 preflight 不能称正式 SSOT，Physics Tool 草案不能称 Physics Foundation Model。

原拒绝表也包含可重新评估的事项：实时孪生需状态流/双向接口/HIL 证据；正式 ASM-00 需具名接口和成功判据；旧胶囊迁移需完整路径/哈希影响检查；阅读成熟度随实际阅读卡更新；多栈仿真工具评估应先明确单一可证伪问题、工具缺口和锚点。这些理由不构成本轮文件整理或已授权工程工作的旧许可门。原治理来源见[REORG03-A](../../../01_project/governance/reorg03a_report.md)与[项目总导航](../../../PROJECT_MAP.md)。

<a id="sources"></a>
## 十份原文的吸收位置

| 原路径 | 本页段落 |
|---|---|
| `10_research/knowledge_base/project_context/mission.md` | 任务链、两应用线、候选边界、离线水印 |
| `10_research/knowledge_base/project_context/current_state.md` | 7/23 架构、逐组状态、文献计数与触发器 |
| `10_research/knowledge_base/project_context/research_questions.md` | Paper1、BRIDGE-UT、Q6、感知/VLA/实时孪生问题与来源 |
| `10_research/research_state_v3.md` | 7/18 快照、72k 行口径、216 刚体同步、计划/风险/工作流 |
| `01_project/competition/项目全景_零基础版_20260718.md` | 零基础任务解释、同日 sim_12 进度差异、旧日历与概括的边界 |
| `10_research/knowledge_base/aerospace/orbital_capture.md` | 任务/证据表及领域概念：组合体重构、coverage 与 formal safe 的区别 |
| `10_research/knowledge_base/aerospace/flexible_dynamics.md` | 领域概念：FFR/ANCF/有限带宽、五个文献键；证据表和输入触发器共用 |
| `10_research/knowledge_base/aerospace/embodied_robotics.md` | 候选数据流、L4 输出边界、外部代码/数据来源角色 |
| `10_research/knowledge_base/decisions/architecture_decisions.md` | ADR-001–011 原编号、标签与职责来源 |
| `10_research/knowledge_base/decisions/rejected_options.md` | 三类拒绝原因与可重新评估的证据条件；保留为历史边界 |

旧路径作为历史清单/机器记录中的字符串仍可保留；活动阅读入口已改到本页。源字节、源哈希、删除动作和消费者更新分别登记于共享 SQLite，不能用本摘要反向重建原文件哈希。
