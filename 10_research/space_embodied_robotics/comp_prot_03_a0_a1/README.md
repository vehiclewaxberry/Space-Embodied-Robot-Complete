# COMP-PROT-03-A0/A1 数字空间机器人本体知识入口

*Digital Space Robot Body Knowledge Base and Multi-Agent Model Review Framework, 2026-07-23*

---

> `PHASE: COMP-PROT-03-A0/A1`<br>
> `PHASE_VERDICT: COMP_PROT_03_A0_A1_COMPLETE`<br>
> `STATUS: DIGITAL_MODEL_ARCHITECTURE_ONLY`<br>
> `DOCUMENT_VERDICT: DOCUMENT_COMPLETE_WITH_RECORDED_DOWNSTREAM_BLOCKS`<br>
> `DOWNSTREAM_READINESS: BLOCKED_BY_EVIDENCE`<br>
> `SCIENTIFIC_GATE: false`<br>
> `EXECUTION_AUTHORITY: false`<br>
> `CAD_OR_URDF_GENERATION: false`<br>
> `SIMULATION_OR_EXTERNAL_INSTALL: false`<br>
> `NEXT_GATE: COMP-PROT-03-A2-CANDIDATE-MODEL-REVIEW / EXECUTED 2026-07-23`

## 📋 本阶段裁决

本目录把 COMP-PROT-02 的数字本体设计推进为三类**可审查的研究合同资产**：开源资源知识库、数字机体 manifest 和多智能体模型评审协议。它没有创建新的航天器或机械臂模型，也没有证明任何模型已通过工程一致性、动力学验证或任务验证。

本轮采用用户最新人工批准对 A0/A1 文档子阶段的授权。附件中曾把评审协议称作 A2；本项目为避免歧义，将“协议设计”并入本轮 A1，而把“对候选 CAD/URDF/数字机体执行正式评审”保留为未来 A2。该未来阶段仍需单独人工批准。

后续状态：A2 的候选构型与 Digital Skeleton 已在 [`../comp_prot_03_a2_candidate_model_review/README.md`](../comp_prot_03_a2_candidate_model_review/README.md) 落盘。A2 只完成设计合同；当前 `CAD-SKELETON-G0` 仍为 `CAD_ENTRY_BLOCKED_BY_EVIDENCE`，没有自动进入 CAD/URDF。

## 📦 交付物

| 文件 | 作用 | 权威边界 |
|---|---|---|
| [开源模型知识库](./open_source_model_knowledge_base.md) | 记录 NASA、GitHub、reBot 与本地固定来源的采用角色、许可和禁用边界 | 不下载资产，不替代 SSOT |
| [数字机器人本体清单](./digital_robot_body_manifest.yaml) | 定义 12U、B601、适配器、柔性板、目标、frame 与证据绑定 | 是设计 manifest，不是运行时配置 |
| [多智能体模型评审协议](./model_review_protocol.md) | 定义 Builder、五类审查角色、Chair、红队、冲突和裁决规则 | 是评审合同，不是科学 Gate |
| [结构化评审记录模板](./model_review_record_template.yaml) | 统一角色覆盖率、发现、异议和限制记录 | 空模板不代表已有模型获准 |
| [A0/A1 架构审查记录](./a0_a1_architecture_review_record.yaml) | 固化三路只读审查、15 项 blocker、双轴裁决与 15 个 Gate 哈希复核 | 不是 A2 候选模型接受记录 |
| [本地 Review Chair 入口](../../../.codex/agents/digital-body-model-review-chair.md) | 让 Codex/Claude 按同一协议编排只读模型评审 | 无执行、模型生成或自签权限 |

## 🔍 当前阻塞项

| ID | 事实 | 当前处理 |
|---|---|---|
| `DB-BLK-001` | 24 kg 整星参考、23.3032134 kg 总线、两块 0.3483933 kg 柔性板、1.2 kg 适配器和 4.6956 kg B601 的系统质量所有权未闭合 | `BLOCKED_BY_COMPONENT_OWNERSHIP`；禁止计算“最终整机质量” |
| `DB-BLK-002` | `frame_tree_v1.yaml` 的工具 frame `E` 指向 `arm_link7`，而 accepted B601 URDF 不含该 link | `BLOCKED_BY_FRAME_BINDING`；不得猜测绑定到 `link6` 或 `gripper_link` |
| `DB-BLK-003` | `arm_b601_v1.yaml` 中厂商 STEP 的声明路径不存在；观察到的本地候选路径位于另一目录 | `BLOCKED_BY_STALE_SOURCE_PATH`；本轮不改 SSOT |
| `DB-BLK-004` | 捕获接口几何仍为 `geometry TBD`，夹爪包络和硬捕获接口未资格化 | `BLOCKED_BY_CAPTURE_GEOMETRY`；只保留 3DOF/6DOF 约束语义 |
| `DB-BLK-005` | CubeSat CDS Appendix B 图纸尺寸尚未完成人工目视复核 | `LIMITED_STANDARD_CONFORMANCE`；不能声称发射接口合规 |
| `DB-BLK-006` | E16 历史 Gate 的 8 项 protected source 对当前 checkout 做 raw SHA-256 复核时只有 2 项一致 | `BLOCKED_BY_CURRENT_SOURCE_BUNDLE_MISMATCH`；不改写历史 E16 verdict |
| `DB-BLK-007` | sim_05 的 `b601_model.py` 仍把 URDF 解析到已不存在的根目录 `cad/…` | `BLOCKED_BY_STALE_CONSUMER_PATH`；当前加载器不能作为可用数字机体入口 |
| `DB-BLK-008` | B601 YAML 分项质量与 accepted URDF 精确求和存在小额但真实的不闭合 | `BLOCKED_BY_MASS_SUBTOTAL_CONFLICT`；保留 4.6956 kg 为既有暂定锚点，不重算覆盖 |
| `DB-BLK-009` | `B` 自由漂浮母体 frame 与 `T_SB` 未写入现行 `frame_tree_v1.yaml` 的数值树 | `BLOCKED_BY_FREE_FLYER_FRAME_BINDING`；不得默认 `B=S` |
| `DB-BLK-010` | 现有 12U CAD/spec 仍含 140 × 140 × 15 mm 旧法兰，现行 geometry SSOT 已冻结 160 × 160 × 15 mm，展示 manifest 还记录了适配器穿插 | `BLOCKED_BY_FLANGE_GEOMETRY_CONFLICT`；不修改 CAD |
| `DB-BLK-011` | `T/D/A0` 未在 frame tree 完整定义，`C_sat/C_deb` 只有 origin+normal 而无完整旋转 | `BLOCKED_BY_FRAME_TREE_COMPLETENESS`；不足以支持 6DOF rigid-lock frame 绑定 |
| `DB-BLK-012` | `[660,0,950]` 在 geometry/capture YAML 中被称为 `nozzle_rim`，但目标 JSON 将其定义为前端环，并把真正的后部喷管区列为禁触区 | `BLOCKED_BY_GRASP_SEMANTIC_CONFLICT`；禁止按“喷管抓取”实现 |
| `DB-BLK-013` | `frame_tree_v1.yaml` 已冻结 `T_SM`，但适配器 JSON 仍将同一变换标为 `TBD / NOT fixed` | `BLOCKED_BY_TRANSFORM_AUTHORITY_CONFLICT`；不得挑选对实现更方便的一份 |
| `DB-BLK-014` | B601 硬件许可证正文只存在于工程外部 vendor checkout，当前项目内 accepted URDF 只有 attribution | `BLOCKED_BY_LICENSE_PORTABILITY`；当前组件包不能独立携带完整许可链 |
| `DB-BLK-015` | 当前没有把 `S→M→A0→E`、B601 与目标对象装入同一份 CAD 或 URDF 的组合数字机体 | `BLOCKED_BY_INTEGRATED_MODEL_ABSENCE`；现状只能称为组件资产包 |

这些阻塞不影响本轮文档合同完成，但阻止任何候选数字机体进入正式模型接受、仿真、CAD/URDF 派生或对外工程能力声明。

只读实盘共登记 `40` 个 CAD 根目录文件，其中 `35` 个非占位文件；现有 `7` 份 URDF、`5` 份 STEP、`15` 份 STL、`6` 份 JSON 和 `1` 份原生 SLDPRT 均保持原位且未修改。数字清单把它们标记为组件资产，而非已闭合总装。

## 🔐 允许与禁止措辞

允许：

> 已完成 COMP-PROT-03-A0/A1 的数字机体知识库、设计 manifest 与多智能体评审合同；状态为 `DIGITAL_MODEL_ARCHITECTURE_ONLY`。

禁止：

- “数字空间机器人本体已经建成/验证”；
- “CAD、URDF、Basilisk、ROS 或 Isaac Sim 已集成”；
- “多智能体投票证明模型正确”；
- “已实现空间具身智能、自主捕获、VLA 或安全控制”；
- “架构合同通过等于科学 Gate PASS”。

## 🚫 本轮未发生的动作

- 未生成或修改 CAD、STEP、STL、URDF、USD；
- 未下载、克隆或复制外部模型进入工程；
- 未安装或运行 Basilisk、ROS、Isaac Sim；
- 未运行仿真、控制、训练、Physics Tool 或 SAFE；
- 未修改 `30_simulation/`、`40_evidence/`、Gate JSON 或冻结几何配置。
