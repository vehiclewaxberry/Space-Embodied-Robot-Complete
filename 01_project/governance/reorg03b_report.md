# REORG03-B 职责收敛与 Agent 知识入口验收报告

- 日期：2026-07-22
- 上游提交：`b84f5aa9269eae9dd56976bf295985ce4b091acf`
- 执行分支：`codex/reorg-03b-knowledge-entry`
- 本批裁决：`REORG03B_COMPLETE_WITH_FROZEN_PATHS_PRESERVED`

## 1. 本批目标

本批只处理低风险职责冲突和 Agent 导航，不迁移科学资产：

1. 为历史 ASM-00 前检建立未来规范命名空间的职责占位；
2. 明确根目录文档禁止新增和 `PATH_LOCKED` 历史输入规则；
3. 建立本地 Codex/Claude 研究知识入口；
4. 保持全部 Gate、结果、绑定路径和程序输出不变。

## 2. 职责收敛结果

### ASM-00

新增 [`sim/asm_00_interface_preflight/README.md`](../../30_simulation/asm_00_interface_preflight/MIGRATION_NOTICE.md)。该目录只有一个 README：

- Legacy path：`30_simulation/asm_00_interface_preflight/`
- Current role：`Interface preflight`
- 不含 `src/`、`tests/`、`config/`、`results/` 或新 Gate；
- 不复制、不移动、不改写历史胶囊；
- 明确比赛冻结解除后的未来迁移条件。

历史 ASM-00 目录仍存在 11 个文件，原 Gate SHA-256 仍为：

`c98639b03bd63b9bb279c6c3d846ac2b7fafa482661618e0f650cfb2e79224b9`

### 根目录资料

[`docs/95_inbox/README.md`](../inbox/README.md) 已增加根目录治理规则：一般性外来资料不得继续放在仓库根目录；已被合同、Gate 或冻结指纹绑定的历史输入保持原位，直到正式治理记录解除绑定。

根目录 `空间机械臂.docx` 未移动、未改写，其 SHA-256 与 `source_manifest.csv` 仍一致：

`c9b46196d9c3a161422c6ffeacaf2d80421086007914b24467d676810f7d1fb0`

## 3. Agent 知识入口

新增 [`knowledge_base/README.md`](../../10_research/knowledge_base/README.md) 和 12 个分层文件，共 13 个文件：

| 分区 | 文件数 | 职责 |
|---|---:|---|
| `project_context/` | 3 | 任务、带水印现状和研究问题 |
| `aerospace/` | 3 | 在轨捕获、柔性动力学和具身智能边界 |
| `simulation/` | 2 | 模块索引和 Gate 逻辑 |
| `papers/` | 2 | 45 条题录的派生索引和 canonical 阅读卡入口 |
| `decisions/` | 2 | 已有架构决策和明确拒绝路线 |
| 根 README | 1 | Agent 使用顺序和证据优先级 |

知识库采用 `NAVIGATION_ONLY` 规则：不建立第二套状态 SSOT、题录库、阅读卡、PDF 或 Gate。发生冲突时必须回到原始机器结果、现行状态真值或文献 manifest。

`paper_index.csv` 含 45 行，已与 `docs/00_references/manifest.yaml` 的 bibkey、年份、类别、mission line、优先级、DOI 状态、本地 PDF 和阅读卡路径逐字段对拍，差异为 0。

## 4. 变更范围

业务载荷变更共 17 个文件：

- 新增 14：13 个知识入口文件 + 1 个 ASM-00 职责占位；
- 修改 3：`CLAUDE.md`、`PROJECT_MAP.md`、`docs/95_inbox/README.md`；
- 迁移、删除或重命名：0；
- 科学证据内容变更：0。

逐文件 SHA-256 见 [`reorg03b_change_manifest.csv`](./reorg03b_change_manifest.csv)。本报告和清单自身属于治理记录，不列入其载荷哈希表。

## 5. 验收结果

| 检查项 | 结果 |
|---|---:|
| Gate JSON 基线对拍 | 15/15 一致 |
| 禁止路径的 tracked 内容变更 | 0 |
| 历史 ASM-00 路径 | 保留；11 文件 |
| 新 ASM-00 占位内容 | 仅 1 个 README |
| 根目录 DOCX manifest 哈希 | 一致 |
| 文献派生索引 | 45/45 一致 |
| 本阶段 Markdown 本地链接 | 71 条，0 断链 |
| 仪表板固定 HTML 输出 SHA-256 | 未变 |
| 科学仿真、VLA、装配实施 | 均未运行 |

仪表板固定输出仍为：

`artifacts/visualization/project_visualization_v1_research.html`

SHA-256 仍为：

`0bf424e17a55773fdb4e2ca3ce46ecc973000edf8eadc8a0f3c96d6906cc150b`

## 6. 明确未做

- 未移动 sim_09；
- 未移动 e15/e16；
- 未移动或提交历史 ASM-00 胶囊；
- 未修改任何 Gate JSON、配置、结果、阈值、CAD 或表格；
- 未实现 VLA；
- 未运行科学仿真或装配任务；
- 未把知识库提升为新科学真值。

后续如需处理冻结模块，必须另立任务、生成 path manifest，并重新执行 Gate 哈希、引用和机器测试验收。
