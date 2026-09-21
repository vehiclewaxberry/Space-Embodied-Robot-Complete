# REORG03-A 低风险命名空间归一验收报告

- 日期：2026-07-22
- 上游裁决：`REORG02_COMPLETE_WITH_PATH_LOCKED_EXCEPTIONS`
- 基线提交：`3325920a858f96e2ecc394d309af95acbce73744`
- 执行分支：`codex/reorg-03a-research-dashboard`
- 本批裁决：`REORG03A_COMPLETE`

## 1. 执行内容

将离线研究仪表板从：

`research_integration/`

迁移到：

`tools/research_dashboard/`

`research/integration/` 保持原位，继续承担系统集成研究规划职责。迁移后“研究治理”和“离线程序”不再使用近似的根目录名称。

## 2. 禁止边界执行情况

- 未移动 sim_09。
- 未移动 e15/e16。
- 未修改任何 Gate JSON。
- 未运行科学仿真、ANCF、VLA 或装配实验。
- 只运行仪表板自己的确定性离线构建和验收测试。

## 3. 文件与哈希

| 项目 | 结果 |
|---|---:|
| 迁移文件 | 15 |
| 原始字节完全一致 | 11 |
| 仅因新命名空间修改路径 | 4 |
| 科学汇总 JSON 字节变化 | 0 |
| 结果 CSV 字节变化 | 0 |
| 报告与模板字节变化 | 0 |
| Gate 类 JSON 哈希变化 | 0/15 |

发生内容变化的四个文件仅为：

- `README.md`：复现命令和目录说明。
- `build_research_dashboard.py`：仓库根定位和工具目录常量。
- `tests/run_all.py`：仓库根定位和工具内路径。
- `results/run_manifest.json`：六个工具内 artifact key 的路径前缀。

逐文件前后 SHA-256 见 [`reorg03a_migration_manifest.csv`](./reorg03a_migration_manifest.csv)。

## 4. 输出路径与确定性

程序展示输出继续写入：

`artifacts/visualization/project_visualization_v1_research.html`

迁移前后 SHA-256 均为：

`0bf424e17a55773fdb4e2ca3ce46ecc973000edf8eadc8a0f3c96d6906cc150b`

工具原有 18 项离线验收全部 PASS，包括两次构建字节确定性、冻结可视化哈希、P0-A/B/C 账本、唯一 `REPEAT_CORE` 裁决和离线 HTML 合同。

## 5. 路径扫描

活动 Markdown、Python、JSON 和 YAML 已切换到 `tools/research_dashboard/`。Python、JSON、YAML 中旧目录引用均为 0；Markdown/CSV 中的旧路径文字只保留在迁移记录和不可变历史快照中：

- `docs/00_project_governance/reorg02_report.md`
- `docs/00_project_governance/reorg02_migration_manifest.csv`
- `docs/00_project_governance/reorg03a_report.md`
- `docs/00_project_governance/reorg03a_migration_manifest.csv`
- `docs/90_competition/archive/项目现状总览_20260715.md`

这些记录描述当时真实路径，不作为当前运行入口。

全库解析 270 条 Markdown 本地链接，目标缺失为 0。

## 6. 恢复信息

迁移前 15 文件及 Gate JSON 哈希备份：

`C:\Users\stude\AppData\Local\Temp\codex_reorg03a_research_dashboard_20260722_170354`
