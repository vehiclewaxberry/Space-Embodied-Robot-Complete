# 12 提交包检查清单（SUBMISSION_PACKAGE_CHECKLIST）

- 生成日期：2026-08-27；生成者：综合代理 SYN-C。基础：compdeliv fragment §B.3 草案（12 行现状核对版），补全为可勾选清单。
- 状态词表：**READY**（资产在且证据自洽）/ **INCOMPLETE**（资产在但口径或锚定未闭合）/ **MISSING**（资产不存在）。每项给证据指针；勾选动作发生在 8-31 终核（`10_FIVE_DAY_CLOSEOUT_PLAN.md` Day 5/6）。
- 前置 UNKNOWN：官方提交要求未确认（B-CD01，P0）——本清单「官方格式合规性」列在官方文件到位前一律不可判 READY。

| ☐ | # | 检查项 | 状态 | 证据指针 | 闭合动作（责任/期限） |
|---|---|---|---|---|---|
| ☐ | 1 | 官方要求确认（清单/格式/截止/是否实物） | **MISSING** | compdeliv fragment §A：官方文件零命中；归档描述 `01_project/competition/archive/项目现状总览_20260715.md:11`（`e65cf431ba00`）禁作现行依据（`AGENTS.md` L14，`3d2269562678`） | Owner 取回官方文件并回填 04 矩阵（8-28） |
| ☐ | 2 | 比赛技术报告书母稿 | **MISSING** | 仓内 `*.tex` 仅 `80_third_party/vendor/astrobee/…` 命中；`01_project` 无报告书 docx/pdf；`10_research/paper1_architecture.md`（`6df2bec70a72`）为期刊论文架构非比赛报告书（B-CD02） | 8-30 从零撰写，逐 claim 绑 gate JSON+locator |
| ☐ | 3 | 报告 claim→Gate 追溯矩阵 | **INCOMPLETE** | 比赛链 9 行可用：`10_research/competition_convergence/competition_claim_evidence_matrix.csv`（`10c8d503c55e`）；论文级账本 0 行：`10_research/knowledge_base/papers/claim_evidence_ledger.csv`（185 B 表头，`1cff4ab952b7`）；三份矩阵均停 08-04/旧 HEAD b75352c（BLK-MEM-02） | 8-28 append-only 重冻结（吸收 08-23 红绿线） |
| ☐ | 4 | 演示视频 | **INCOMPLETE**（资产 READY、口径 REPEAT） | `40_evidence/artifacts/competition_convergence/competition_mission_intelligence_demo.mp4`（`7043d026cef6`，1,572,615 B，h264/1920x1080/54.97s）与 `evidence_asset_manifest.json`（`33b7bfbf8682`）逐字节一致；Gate 记录 `competition_gate_check.json` VIDEO_PACKAGE（`8b3cdbdaa09e`）；口径冻结 07-20（B-CD08） | 8-30 按当前状态核对/补日期+scope 限定，必要重渲染（仅文字层） |
| ☐ | 5 | 答辩 PPT | **INCOMPLETE**（资产 READY、口径 REPEAT） | 同目录 pptx（`9deff92b539c`，177,259 B，9 页）哈希复算一致；另有 9 张 1280x720 PNG | 同 #4 |
| ☐ | 6 | 展架图 | **MISSING** | 文件名搜索零命中（B-CD06）；官方要求本身 UNKNOWN | 待 #1 确认后 8-30 制作（无实物走 baseline 结构图+动画方案，`11` 第 2 项） |
| ☐ | 7 | 作品照片 | **MISSING** | 同上；硬件 `B601_MOTION=PROHIBITED`（`8b3cdbdaa09e` `$.hardware_component_status`） | 同 #6 |
| ☐ | 8 | 局限性/对抗审查声明 | **INCOMPLETE** | 报告 §8 不声称清单存在：`competition_execution_report.md`（`dc8f05268955`）；独立红队档案根级 `08_REVIEWS/` 为空目录（B-CD10）；Gate 内红队 15/15 机器记录在 `8b3cdbdaa09e` COMPETITION_TESTS_AND_RED_TEAM | 8-30 并入报告母稿局限性章；08_REVIEWS 处置 Owner 决定（P2） |
| ☐ | 9 | 提交 ZIP+manifest | **MISSING** | 仓内 zip 均为机械内部包，无比赛提交包（B-CD03） | 8-31 打包+sha256 manifest |
| ☐ | 10 | 离线恢复演练记录 | **MISSING** | 同上 | 8-31 干净目录恢复演练并记录 |
| ☐ | 11 | 提交回执 | **MISSING** | 同上 | 9-01 提交后登记 |
| ☐ | 12 | 提交包哈希清单（sha256 manifest） | **MISSING** | 同上 | 8-31 随 ZIP 生成 |
| ☐ | 13 | 秘密扫描记录 | **READY**（本次审计快照） | compdeliv fragment §C.2：tracked 文本（1062 tracked/845 文本类）AKIA 0 命中、PRIVATE KEY 0、password 赋值 0；`api_key=` 仅 2 个 visualization HTML 的 Stamen 瓦片 URL 空占位，非凭证 | 8-31 提交包范围复扫一次并入档 |
| ☐ | 14 | 版本锚定（git commit 或独立哈希清单） | **MISSING** | HEAD=`5c5addea00dd…`@2026-08-08；`git status --short`=141 条（11 M+130 ??）；08-08 后终局证据（机械 R2 目录、`01_project/current/`、AGENTS.md 本身等）未提交（B-CD05） | Owner 决策后 8-31 执行（审计只读） |
| ☐ | 15 | 仓库可见性安全裁决记录 | **MISSING** | `git remote -v` 空；GitHub 元数据离线不可验证（B-CD04） | Owner 人工核对+书面裁决（8-29） |
| ☐ | 16 | 演示口径时代限定声明 | **MISSING** | demo 冻结 07-20 vs 08-25 后 HOLD 增多（`HOLD_AND_NEGATIVE_RESULTS_V1.csv` H-01..H-15，`667dd3bd8a83`）（B-CD08） | 8-30 报告/答辩稿每处 demo 引用附日期+scope 限定 |
| ☐ | 17 | 标题冻结签发记录 | **MISSING** | 候选标题仓内业务文档零命中，PENDING_OWNER_SIGNOFF（BLK-MEM-01；见 `13_TITLE_AND_CLAIM_CEILING.md`） | Owner 签收（8-27/28） |
| ☐ | 18 | Gate 复核决定记录（PENDING_OWNER_REVIEW 项） | **MISSING** | 00_RELEASE_GATE/SIM13 20-20/e23/SAFE-00/CTRL-02 待 Owner 复核（`11` 第 4 项） | Owner 复核或明示延期（8-30） |

## 汇总

- READY：1 项（#13）；INCOMPLETE：4 项（#3/4/5/8）；MISSING：13 项。
- 9-01 提交的最低可接受形态：#1/2/3/9/10/12/14/16/17 必须闭合（对应 P0 与口径红线）；#6/7 依 #1 结论；#11 提交后当日内补登。
- 本清单不授权任何范围扩张：新增交付物类型须先回到 04 矩阵确认官方要求。
