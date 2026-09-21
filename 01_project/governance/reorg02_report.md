# REORG-02 项目目录归一与安全迁移报告

- 日期：2026-07-22
- 基线分支：`feat/sim09-grasp-evaluator`
- 基线提交：`b4dd48aa728876ee15636bd03d4f6734dad7b54b`
- 执行分支：`codex/reorg-02-project-layout`

## 1. 裁决

`REORG02_COMPLETE_WITH_PATH_LOCKED_EXCEPTIONS`

项目已经建立唯一根导航、目录所有权、命名规则、受控资料收件箱和迁移记录。无 Gate 绑定的散落资产已迁入对应领域；会迫使改写机器 Gate、冻结 manifest 或科学结果的旧路径保持原位，并作为竞争期路径锁定例外登记。

## 2. 执行边界

- 未运行新仿真、VLA、装配实验或科学 Gate。
- 未修改任何科学数值、verdict、阈值或结果表。
- 文件内容只允许目录导航、路径引用和迁移审计所必需的变化。
- 迁移前已在工作区外备份全部 71 个未跟踪文件，并生成 795 文件 SHA-256 清单。
- 恢复备份：`C:\Users\stude\AppData\Local\Temp\codex_reorg02_b4dd48a_20260722_162640`。

## 3. 实际迁移

共迁移 11 个文件：

- 7 份架构文件：`research/project_architecture_final/` → `research/00_project_architecture/`。
- 文献种子笔记：根目录 → `docs/00_references/source_notes/`。
- `建议.docx`：根目录 → `docs/95_inbox/source_documents/`。
- 自由漂浮服务星 Stage 1 占位说明：`sim/` → Stage 1 `07_next_actions/`。
- 几何审计裁决：独立 `docs/geometry/` → Stage 1 `06_reviews/`。

完整逐文件映射见 [`reorg02_migration_manifest.csv`](./reorg02_migration_manifest.csv)。

## 4. 路径锁定例外

以下资产不做物理搬迁：

- `e15_core_coverage/`、`e15_ancf_certification/`、`e16_sync_capture/`。
- 根目录 sim_09 的 `src/tests/results/figures/tables` 分片。
- `research_integration/`。
- `research/competition_convergence/` 与 `artifacts/competition_convergence/`。
- `30_simulation/asm_00_interface_preflight/`。
- 根目录 `空间机械臂.docx`。

原因不是权限不足，而是这些路径已经写入科学 Gate、测试常量、哈希清单或比赛证据合同。物理改名会改变证据本体，超出“只整理、不改结果”的边界。

## 5. 完整性核验

| 项目 | 结果 |
|---|---:|
| 迁移前未跟踪文件备份 | 71/71 |
| 迁移前项目文件哈希清单 | 795 |
| 未预期丢失文件 | 0 |
| 未预期 SHA-256 变化 | 0 |
| 检查的 Gate 类 JSON | 15 |
| Gate 类 JSON 缺失 | 0 |
| Gate 类 JSON 哈希变化 | 0 |
| 迁移文件 | 11 |
| 原始字节保持一致 | 10 |
| 仅路径清单发生变化 | 1（`agent_management_plan.md`） |

全库解析 265 条 Markdown 本地链接，目标缺失为 0。旧路径仅允许出现在迁移 manifest 的 `old_path` 字段或明确的历史快照中。

## 6. 后续放置规则

- 新科学模块：`sim/<module>/{src,tests,results,docs}`。
- 新研究规划：`research/` 对应专题，不得混入生成媒体。
- 新离线工具：`tools/`。
- 新工程设计文档：现有 Stage 1 体系或 `docs/20_system_design/` 导航域。
- 新外来资料：`docs/95_inbox/`，先登记哈希再引用。
- 新竞赛报告：`docs/90_competition/`；被取代版本进入 `archive/`。
