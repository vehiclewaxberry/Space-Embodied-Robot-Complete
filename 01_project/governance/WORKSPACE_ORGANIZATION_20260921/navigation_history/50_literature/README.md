# 文献主清单、阅读卡与全文

导航整理：2026-09-06。本域统一保存文献题录、核验记录、阅读卡和本地全文；不在导航中重复容易漂移的数量。

- [题录与核验主清单](references/manifest.yaml)：文献身份、本地文件和来源状态。
- [阅读卡索引](references/notes/INDEX.md)与[BibTeX](references/refs.bib)：阅读与引用入口；索引文字中的日期和计数仍需对照主清单。
- [本地 PDF](pdf/)：按文献分类保存全文。
- [文献工作流派生状态](../10_research/knowledge_base/papers/controller_state.yaml)：辅助安排阅读，不是第二份题录主清单。
- [历史补充论文来源](#legacy-supplemental)：保留迁移来源关系。

全文、阅读卡、题录及引用用途不同；同名或重复引用不等于内容可以互相替代。

<a id="legacy-supplemental"></a>
## 历史补充论文来源

REORG-01-R 已将原“补充论文”目录中的 21 份 PDF 归并到 [pdf/](pdf/)，统一采用 `NN_category/bibkey.pdf` 命名。题录、页数、SHA-256 与来源记录以[主清单](references/manifest.yaml)为准；原归并过程见[核验报告](references/reorg01r_report.md)。不再建立平行 PDF 副本。

2026-09-06 将原 `legacy_supplemental/README.md` 的迁移说明并入本节，并移除该空目录；原文完整字节保存在整理账本的 SQLite 快照中。
