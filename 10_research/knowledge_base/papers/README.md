# 论文知识总控入口

> 状态：`DERIVED_NAVIGATION_ONLY`。本目录让 Codex、Claude 和项目成员读取同一份论文工作状态；不替代 manifest、refs.bib、本地 PDF、canonical 阅读卡或科学 Gate。

## 入口

- 总控技能：[`paper-knowledge-orchestrator`](../../../.codex/skills/paper-knowledge-orchestrator/SKILL.md)
- 机器状态：[`controller_state.yaml`](./controller_state.yaml)
- 最近一次正式校验：[`controller_validation.json`](./controller_validation.json)
- 航天器/机械臂/具身智能专业综合：[`AEROSPACE_ROBOTICS_EXPERT_RESEARCH_SYNTHESIS_20260808.md`](./AEROSPACE_ROBOTICS_EXPERT_RESEARCH_SYNTHESIS_20260808.md)
- 待读队列：[`reading_queue.md`](./reading_queue.md)
- 轻量索引：[`paper_index.csv`](./paper_index.csv)
- 主张账本：[`claim_evidence_ledger.csv`](./claim_evidence_ledger.csv)
- canonical 阅读卡：[`50_literature/references/notes/INDEX.md`](../../../50_literature/references/notes/INDEX.md)

## 真值边界

| 对象 | 真值源 | 本目录角色 |
|---|---|---|
| 题录、DOI、分类、优先级 | `50_literature/references/manifest.yaml`、`refs.bib` | 只派生索引 |
| PDF 路径、页数、SHA-256 | manifest + 本地文件对拍 | 只显示存在性和阅读状态 |
| 论文正文证据 | canonical 阅读卡 + 页级定位 | 只组织队列与引用入口 |
| 项目数值与裁决 | 机器 Gate JSON、原始结果、绑定哈希 | 仅在 claim 账本中引用 |
| 论文写作主张 | `claim_evidence_ledger.csv` 的已审核行 | 不自动晋升未定位草稿 |

## 使用方式

在 Codex 中调用：`$paper-knowledge-orchestrator`。在 Claude 中调用 `paper-knowledge-orchestrator` Agent。两个入口都读取同一个 skill、同一个状态文件，不维护平行知识库。

只刷新派生状态：

```powershell
python .codex/skills/paper-knowledge-orchestrator/scripts/paper_knowledge.py build --repo-root .
python .codex/skills/paper-knowledge-orchestrator/scripts/paper_knowledge.py validate --repo-root .
```

正式新建阅读卡或交付前增加 `--verify-pdf-sha256 --write-report`。当前计数只读取 `controller_state.yaml`，不要在本页手工复制，避免再次漂移。
