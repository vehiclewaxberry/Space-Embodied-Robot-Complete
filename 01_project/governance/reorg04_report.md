# REORG04 根目录收敛验收报告

## 裁决

`REORG04_COMPLETE_ROOT_COLLAPSED`

本轮完成了真实的物理迁移，不是仅增加导航 README。项目业务资产已收敛到八个根域；没有运行科学仿真，没有新增或升级科学结论。

## 迁移边界

- 基线提交：`6316f4e32afe00d5cfe7fb6340eb69862a17b1ea`
- 工作分支：`codex/reorg-04-root-collapse`
- 物理移动：49 项
- 回滚备份：`C:\Users\stude\AppData\Local\Temp\codex_reorg04_root_collapse_20260722_175149`
- 禁止项：未实现 VLA、未实现正式装配、未运行科学仿真、未重算结果数值。

## 根目录结果

整理前根目录共有 32 个项目；整理后共有 17 个实际项目，其中包括：

- 8 个业务根域：`01_project`、`10_research`、`20_engineering`、`30_simulation`、`40_evidence`、`50_literature`、`70_tools`、`80_third_party`；
- 2 个面向人的根入口：`CLAUDE.md`、`PROJECT_MAP.md`；
- 7 个 Git/Agent 元数据项目。

原根级 `sim/`、`config/`、`docs/`、`src/`、`results/`、`figures/`、`tables/`、`videos/`、`pdf/`、`补充论文/`、e15/e16 和 `assembly_research/` 均已撤除。完整映射见 [`reorg04_directory_mapping.csv`](./reorg04_directory_mapping.csv)，根目录清单见 [`reorg04_root_inventory.csv`](./reorg04_root_inventory.csv)。

## 关键合并结果

- sim09 的 `src/tests/results/figures/tables` 已合并到 [`../../30_simulation/sim_09_grasp_evaluator/`](../../30_simulation/sim_09_grasp_evaluator/)。
- e15/e16 已进入 [`../../30_simulation/`](../../30_simulation/) 的独立证据胶囊。
- ASM-00 历史草案与迁移说明已收敛到 [`../../30_simulation/asm_00_interface_preflight/`](../../30_simulation/asm_00_interface_preflight/)；其角色仍是授权前接口预检，不代表装配实现完成。
- 参数卡和 CAD 已进入 [`../../20_engineering/`](../../20_engineering/)。
- 图、表、视频和离线回放已进入 [`../../40_evidence/`](../../40_evidence/)。
- 题录、阅读卡和 44 份 PDF 已进入 [`../../50_literature/`](../../50_literature/)。
- 研究看板与可视化程序已进入 [`../../70_tools/`](../../70_tools/)。
- 外部工程和 9 个独立仓库已进入 [`../../80_third_party/`](../../80_third_party/)。

## 科学证据保护

### Gate JSON

15 份迁移前 Gate 已从独立备份逐字段转换到新路径后，与当前 JSON 做深度比较：

- Gate 数量：15；
- 非路径字段差异：0；
- 数字、布尔值、字段结构和裁决文本变化：0；
- 仅因路径字符串改变而需要新 SHA-256 的 Gate：按 [`reorg04_gate_refreeze.csv`](./reorg04_gate_refreeze.csv) 登记。

### 文献与第三方资产

- 44 份 PDF 的字节数和 SHA-256 均与迁移前一致，见 [`reorg04_pdf_integrity.csv`](./reorg04_pdf_integrity.csv)。
- 9 个 `vendor` 独立仓库的 HEAD 均保持不变，工作树均为 clean。
- 基线中 5 类未跟踪本地资产仍保持未跟踪属性，仅改变物理位置；没有被擅自纳入 Git。

### 路径绑定证据重冻结

- E15 保护快照：22/22 当前哈希一致；其中 18 份字节不变，4 份仅因路径文字改写产生新哈希。
- VIZ-Gate 0 冻结对象：29/29 当前哈希一致；其中 18 份字节不变，11 份仅因路径文字改写产生新哈希。
- 两份清单均新增 `pre_reorg04_*` 审计列，迁移前路径、大小与 SHA-256 未被覆盖；51 行双轨记录见 [`reorg04_evidence_refreeze.csv`](./reorg04_evidence_refreeze.csv)。
- 研究集成离线验收：18/18 PASS；没有运行长时 ANCF 或其他科学求解流程。

## 路径和程序验收

- 活动项目文件中的旧根路径引用：0；上述清单的 `pre_reorg04_*` 字段和 tagged-blob 校验属于显式历史证据，不计为活动路径。
- Markdown 本地链接：全部可解析；最终数量以 [`reorg04_validation.json`](./reorg04_validation.json) 为准。
- Python：全部通过 AST 语法检查。
- JSON：全部可解析。
- sim09、项目可视化和研究看板的仓库根路径均解析到当前项目根目录，关键输入目录存在。
- 未运行任何科学求解器或结果生成流程。

## 已知的基线例外

[`../../20_engineering/config/visualization/scene_manifest_v1.yaml`](../../20_engineering/config/visualization/scene_manifest_v1.yaml) 在迁移前基线中即因未加引号的冒号而无法由 PyYAML 解析。本轮当前文件与“迁移前内容 + 纯路径转换”逐字一致，因此保留为 `PREEXISTING_SYNTAX_EXCEPTION`，未借整理任务修改其科学配置文本。

该例外不影响本轮目录完整性裁决，但后续若要重新生成 VIZ 工件，应另立受控修复任务，并同步处理相关哈希合同。

## 可恢复性

迁移前 15 份 Gate 原始字节、44 份 PDF 哈希清单、根目录清单、Git 状态、5 类本地未跟踪资产和 Agent 元数据均已备份。首轮含中文路径的移动脚本曾因旧 PowerShell 编码失败，但已自动完整回滚并验证 Gate 哈希不变；随后以 Unicode 路径重试成功。

最终机器验收记录：[`reorg04_validation.json`](./reorg04_validation.json)。
