# 研究、学习与文献队列

_状态水印：2026-07-23；裁决：`QUEUE_DEFINED_NO_DOWNLOAD_NO_INSTALL_NO_EXECUTION`。_

> 本页把附件中的“马上执行十件事”改写为受 Gate 约束的工作队列。它不启动仿真、训练、文献下载、软件安装、数字孪生、VLA、装配或硬件任务。

## 1. 未来 12 个月的依赖顺序

| 优先级 | 工作包 | 当前允许动作 | 完成门 | 不自动解锁 |
|---|---|---|---|---|
| P0 | Paper 1 收口 | claim–evidence/hash/row locator、状态冲突清理、专项 prior-art | 每个图、数字和主张可复核；新颖性仍需独立审计 | 新参数扫描、VLA、装配 |
| P1-A | BRIDGE-UT 合同 | Q3 UQ、状态信封、OOD、候选分层和 benchmark 预注册草案 | B0/B1 合同审查通过并获独立实施授权 | 训练、闭环、执行 |
| P1-B | Q6 接口资料 | 真实几何/材料/摩擦/公差出处、HAG-A 与 raw hash | 具备 AG0 科学接口资格化的可审查输入与单独授权 | ASM-01/02 |
| P2 | 确定性 Physics Tool/SAFE 扩展 | 先收敛单一合约与负例，不改冻结 SAFE | B3/B4 独立 Gate 和红队通过 | VLA 增量主张 |
| P3 | VLA 增量评价 | 仅在确定性 V2.5 基线闭合后预注册消融 | 有用候选、错误提案、弃权、效用和运行时指标完整 | 直接控制、普适泛化 |

P1-A 与 P1-B 可以并行建合同；它们不是证据继承链。

## 2. 文献队列

当前唯一题录入口仍为 `50_literature/references/manifest.yaml`，执行入口仍为 Paper Knowledge Agent。轻量校验时的当前状态为：45 条题录、44 份本地 PDF、29 张完整阅读卡、15 条 PDF-ready、1 条缺全文。

### 2.1 已有全文的优先精读

| 顺序 | bibkey | 用途 | 当前状态 | 出口 |
|---:|---|---|---|---|
| 1 | `park2024poseestimation` | Paper 2 的域差、在线修正和状态信封边界 | `PDF_READY_NO_COMPLETE_CARD` | 完整卡、定位器、允许/禁止措辞 |
| 2 | `lee2016modulartelescope` | Q6-L1 模块化望远镜/装配架构先验 | `PDF_READY_NO_COMPLETE_CARD` | 完整卡、任务映射与局限 |
| 3 | 其余 PDF-ready 条目 | 按 Paper 1→Paper 2→Paper 3 的 claim 缺口排序 | `QUEUE_ONLY` | 每次只为明确 claim 建卡 |

`gerstmayr2013ancfreview` 继续保持 `BLOCKED_NO_LOCAL_PDF`。没有全文时不得伪造模型细节或页码定位器。

### 2.2 未来来源发现查询

以下只登记为 `UNVERIFIED_CANDIDATE_QUERY`，本轮没有搜索、下载或写入 manifest：

- 空间具身智能：`embodied intelligence space robotics`、`physics-grounded space robot manipulation`、`VLA robotic manipulation space`；
- 物理/安全约束智能：`physics-guided robot planning`、`runtime assurance robot manipulation`、`safe learning constraint shielding robotics`；
- ISAM/装配：`in-space robotic assembly`、`prepared interface modular spacecraft assembly`、`robotic servicing assembly verification`。

任何候选来源必须经过来源核验、去重、题录裁决、全文获取和阅读卡流程；检索结果不能直接成为项目主张。

## 3. 学习主线

附件给出的 40/30/20/10 只作为时间管理建议，不是项目真值或固定比例。近期学习顺序应服从科学缺口：

1. 自由漂浮机器人动力学、GJM、动量/资源账本、接触与柔性适用域；
2. 估计不确定性、区间/鲁棒传播、可达/可行域、MPC/NMPC 与 fail-closed 决策；
3. 空间机器人任务、接口、操作与装配验证；
4. 具身 AI、safe/shielded learning 和 VLA，只用于候选生成与消融设计。

算法学习次序建议为：`MPC/NMPC → robust/tube MPC → deterministic physics planner → optional safe/shielded RL → optional VLA`。PPO、SAC、TD3 或 Offline RL 不构成当前实施清单，也不能替代动力学、SAFE 或独立授权。

## 4. 仿真平台选择门

MuJoCo、PyBullet、ROS 2 和 Isaac Sim 当前统一登记为 `DEFERRED_TOOL_EVALUATION`，不安装、不集成，也不建立“四栈并行平台”。未来评估必须先回答：

1. 哪个可证伪问题是现有 Python/MATLAB 与冻结求解器无法回答的？
2. 需要接触、视觉、控制、实时通信还是硬件接口中的哪一种能力？
3. 模型参数、坐标、时间同步和参考真值如何与现有 Gate 对齐？
4. 选择一个最小工具后，如何建立与现有锚点的交叉验证和停止门？

没有上述合同，不以“平台更先进”为理由引入新依赖。

## 5. 数字孪生与数据准备边界

当前最高成熟度仍是受限 DT2 离线证据回放。`CAD → URDF → dynamics → vision → controller` 只能作为未来依赖链，不代表这些接口已存在。升级 DT3/DT4 至少需要统一状态 schema、时钟、延迟/丢帧 Gate、双向接口、不可覆盖原始日志和 HIL 资格链。

未来候选数据记录可以规划以下字段：

`observation_ref + instruction + candidate_bundle + physics_response + safe_decision + provenance + failure_label`

该字段集合目前为 `DATA_SCHEMA_IDEA_ONLY`。不得从冻结结果批量生成“训练集”，也不得把 SAFE 构造出的标签包装成 VLA 安全能力。

## 6. 长期研究主题，不重编号 Q1–Q6

附件中的三个“博士级 Q1–Q3”改为以下主题，避免覆盖现有问题登记：

| 主题 ID | 长期问题 | 绑定现有问题 |
|---|---|---|
| RT-A | 强耦合自由漂浮动力学下，如何建立可审计的安全操作可行域与控制接口？ | Q1、Q2、Q5 |
| RT-B | 带界不确定环境下，如何用物理工具与 fail-closed 门约束候选决策？ | Q3、Q4、BRIDGE-UT |
| RT-C | 如何从单次捕获/操作过渡到预制接口模块装配与独立的大型结构合同？ | Q6-L1、Q6-L2 |

这些是长期主题，不是新科学问题编号，不具有执行授权。

## 7. 近期清单

- [ ] Paper 1 的 C1–C4 主张、图、数字与 Gate/hash/locator 全绑定；
- [ ] 完成 `park2024poseestimation` 阅读卡；
- [ ] 完成 `lee2016modulartelescope` 阅读卡；
- [ ] 起草但不执行 Q3 `uncertainty_contract_v0`；
- [ ] 起草但不执行 BRIDGE-UT 状态信封/benchmark 合同；
- [ ] 收集 Q6 接口来源、HAG-A 和 raw hash；
- [ ] 在 B3 前裁决 Physics Tool 草案冲突；
- [ ] 保持 MuJoCo/PyBullet/ROS 2/Isaac Sim、VLA、RL、DT3/DT4 为未授权队列。

## 8. 入口

- [Physics-Gated Agent 规划冻结](./physics_gated_agent_plan.md)
- [技术缺口分析](./technology_gap_analysis.md)
- [未来论文路线](./future_paper_plan.md)
- [论文控制器](../knowledge_base/papers/controller_state.yaml)
- [论文阅读队列](../knowledge_base/papers/reading_queue.md)
- [Q1–Q6](../research_questions/README.md)

本队列只安排认知、合同、来源与学习工作；未执行任何科学计算或外部获取。
