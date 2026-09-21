---
name: paper-knowledge-orchestrator
description: 项目级论文知识总控。审计 manifest、PDF 与阅读卡状态，编排来源核验、逐篇精读、跨文献综合和 claim-evidence 绑定，并生成可追溯索引与阅读队列。用户要求读取论文、整理文献知识、核验 DOI 或全文、补阅读卡、选择下一篇论文、构建综述，或把论文证据连接到空间机械臂研究主张时使用。
---

# 论文知识总控

## 总控职责

把论文工作组织为一条可审计链：题录登记 → 来源核验 → 全文精读 → 阅读卡 → 跨文献综合 → 项目主张绑定。只协调和验收，不把检索命中、DOI 核验、PDF 在盘或测试通过互相替代。

开始任何任务前，完整读取 `references/project_contract.md`。创建或修改阅读卡时再读取 `references/paper_card_schema.md`；推进状态、综合或绑定主张时再读取 `references/handoff_and_state.md`。

## 选择工作模式

根据用户目标只启用必要模式：

- `STATE_AUDIT`：盘点题录、PDF、SHA-256、阅读卡和断点。
- `SOURCE_VERIFY`：裁决 DOI、版本、全文来源和本地文件是否对应。
- `DEEP_READ`：读取一篇本地全文并生成或补强 canonical 阅读卡。
- `SYNTHESIZE`：对多篇已核验材料做问题驱动的横向综合，不串联摘要。
- `CLAIM_BIND`：把论文证据与项目 Gate/结果分开绑定到允许措辞。
- `QUEUE_PLAN`：按研究问题、manifest 优先级和知识缺口安排下一批阅读。

若用户没有指定模式，先执行 `STATE_AUDIT`，再报告可继续的最小动作。不要因总控角色而擅自扩大为下载、仿真、VLA 或装配实现。

## 启动协议

1. 确认仓库根目录存在 `50_literature/references/manifest.yaml`。
2. 检查 Git 状态；保留用户和其他任务已有改动。
3. 按 `references/project_contract.md` 的真值层级读取 manifest、阅读卡索引和相关 Gate。
4. 运行轻量一致性检查：

   `python .codex/skills/paper-knowledge-orchestrator/scripts/paper_knowledge.py validate --repo-root .`

5. 在新建阅读卡、裁决来源完整性或正式交付前，再运行全文哈希检查：

   `python .codex/skills/paper-knowledge-orchestrator/scripts/paper_knowledge.py validate --repo-root . --verify-pdf-sha256 --write-report`

6. 任何错误先停止写作并报告；`BLOCKED_NO_LOCAL_PDF`、`DOI_MISMATCH` 和 `NOT_FOUND` 是显式状态，不得平滑成成功。

## 来源核验

逐篇建立 Material Passport：bibkey、题名、DOI/arXiv、版本、来源 URL、获取方式、本地路径、页数、SHA-256、核验状态和核验日期。

- 题录真值以 manifest/refs.bib 为准；发现冲突时提出裁决，不静默改写。
- `doi_status=VERIFIED` 只证明题录对应，不证明已经读过全文。
- PDF 路径存在只证明文件在盘；正式精读前对拍 manifest SHA-256。
- 扫描版、OCR 版或预印本必须显式标注版本和可读性限制。
- 缺全文时输出 `PAPER_READING_BLOCKED_NO_FULLTEXT`，保留题录缺口，不猜测正文。

## 逐篇精读

1. 从 manifest 读取该条目的 `why`、`figure_role`、`mission_line` 和 `reading_mode`，把它们视为阅读问题，不视为论文已经证明的结论。
2. 读取全文关键页，并记录页码、章节、公式、图表或表格定位符。
3. 区分作者原始结论、总控的受限解释、可迁移到项目的接口，以及不可迁移边界。
4. 按 `references/paper_card_schema.md` 写入 `50_literature/references/notes/{bibkey}.md`。
5. 不从摘要扩展方法细节，不从单一算例推导普适阈值，不把文献结果写成本项目 Gate 结果。
6. 完成后重新生成派生状态并校验。

## 跨文献综合

围绕研究问题建立“共识—差异—矛盾—缺口—本项目接口”矩阵。每个技术判断至少保留：来源 bibkey、页级定位、适用对象、假设、证据类型和限制。

综述必须显式区分：

- 文献共同支持的背景事实；
- 单篇论文的特定方法或案例结果；
- 总控基于多源材料做出的综合推断；
- 本项目机器 Gate 已验证的结果；
- 仍为 `PLANNED`、`LIMITED` 或 `BLOCKED` 的内容。

## 主张—证据绑定

仅在用户提出具体论文主张或写作任务时使用 `CLAIM_BIND`。按 `references/handoff_and_state.md` 的字段登记；文学证据和项目机器证据必须占不同字段。

- 文献可支撑方法依据、对标和边界，不能替代本项目 Gate。
- 项目数字必须回到 Gate JSON、结果文件、配置或绑定哈希核对。
- 允许措辞不得超过最弱证据；存在 `PROVISIONAL`、`LIMITED` 或负结果时写入限定语。
- 没有页级定位符的文献主张保持 `DRAFT_UNLOCATED`，不得晋升为可引用主张。

## 状态更新

文献或阅读卡发生变化后运行：

`python .codex/skills/paper-knowledge-orchestrator/scripts/paper_knowledge.py build --repo-root .`

该命令只刷新以下派生文件：

- `10_research/knowledge_base/papers/paper_index.csv`
- `10_research/knowledge_base/papers/controller_state.yaml`
- `10_research/knowledge_base/papers/reading_queue.md`

随后运行 `validate`。不得用派生文件反向覆盖 manifest、PDF、refs.bib、阅读卡或 Gate。

## 协作纪律

总控默认顺序完成各角色，避免同一 Agent 在一次步骤里同时“发现来源”和“宣布来源可信”。只有用户明确要求多 Agent 时，才拆分为 Bibliography、Source Verification、Reader、Synthesis 和 Claim Audit，并使用 `references/handoff_and_state.md` 的交接字段；总控仍是唯一状态合并者。

## 完成裁决

结束时只使用以下之一，并列出证据路径与剩余断点：

- `PAPER_KNOWLEDGE_READY`
- `PAPER_READING_CARD_COMPLETE`
- `PAPER_SYNTHESIS_COMPLETE_WITH_LIMITATIONS`
- `PAPER_READING_BLOCKED_NO_FULLTEXT`
- `PAPER_SOURCE_MISMATCH_REQUIRES_ADJUDICATION`
- `PAPER_KNOWLEDGE_INTEGRITY_FAILED`
- `HANDOFF_INCOMPLETE`
