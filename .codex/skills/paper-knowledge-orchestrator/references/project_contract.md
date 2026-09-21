# 项目契约与真值层级

## 适用仓库

本技能绑定 `F:/China Graduate Future Flight Vehicle Innovation Competition` 的现行 REORG04 结构。不得建立根级 `pdf/`、`docs/`、`sim/`、`config/` 或“补充论文”等平行目录。

## 文献真值层级

发生冲突时按以下顺序裁决：

1. 本地文件完整性与 manifest 中的 SHA-256；
2. `50_literature/references/manifest.yaml` 与 `refs.bib` 的登记字段；
3. 出版社、DOI 注册机构、arXiv 或机构仓储的官方元数据；
4. `50_literature/references/notes/{bibkey}.md` 的页级阅读记录；
5. `10_research/knowledge_base/papers/` 下的派生索引和队列；
6. 叙述性报告、演示材料、历史提示词和模型记忆。

manifest 与 refs.bib 冲突时不得任选其一。记录差异并输出 `PAPER_SOURCE_MISMATCH_REQUIRES_ADJUDICATION`。

## 项目科学真值层级

文献只能解释理论来源、方法选择、可比对象和限制。项目自身的数值、PASS、REPEAT、授权与结论强度按以下顺序核对：

1. 机器 Gate JSON、原始结果和绑定哈希；
2. 冻结配置、接口 SSOT 与正式授权记录；
3. 现行状态报告与证据矩阵；
4. 阅读卡与文献综合；
5. 派生导航、PPT 和历史总结。

测试 PASS 不等于科学 Gate PASS。文献中的阈值、质量、接触时间或控制效果不得直接替换项目参数。

## 允许写入

- `.codex/skills/paper-knowledge-orchestrator/`：总控技能本体。
- `.codex/agents/` 与 `.claude/agents/`：指向同一技能契约的薄入口。
- `10_research/knowledge_base/papers/`：派生状态、队列、索引和 claim-evidence 账本。
- `50_literature/references/notes/{bibkey}.md`：仅在实际完成全文精读后新增或修订阅读卡。
- `50_literature/references/notes/INDEX.md`：仅在阅读卡变更后同步链接与计数。

## 默认只读

- `50_literature/pdf/`、`manifest.yaml`、`refs.bib` 和来源记录；元数据裁决任务获得明确授权后才可修改登记文件。
- 所有 `30_simulation/`、`40_evidence/`、`20_engineering/config/` 和 `*_gate_check.json`。
- e15/e16、SAFE、CTRL、比赛收敛证据及其哈希绑定路径。

禁止运行科学仿真、修改阈值、实现 VLA、实现装配或创造新的科学主张。

## Material Passport 最小字段

每次来源核验至少保留：

- `bibkey`
- `origin`
- `identifier`（DOI/arXiv/报告号）
- `version_used`
- `acquisition_mode`
- `local_path`
- `page_count`
- `sha256`
- `metadata_verification_status`
- `fulltext_verification_status`
- `verified_on`
- `dependencies`

不要用单一 `VERIFIED` 同时覆盖元数据、文件完整性、正文可读性和科学可迁移性。
