# compdeliv 分片审计发现（比赛要求、交付物与仓库安全域）

审计时间：2026-09-01 硬截止前 5 天（2026-08-27 本地）。只读审计；唯一写入位置为本 fragment 目录
（`90_competition_closeout/20260827_current_state_audit/fragments/compdeliv/`）。
**授权覆盖记录**：该写入目录由用户在分片任务书中显式授权创建，优先于 `AGENTS.md`（`3d2269562678`，第 6-9 行）
REORG04「根目录业务资产只允许进入八个域」的限制；本 fragment 不新增任何业务资产，仅审计输出。

## 0. 审计方法与入口

入口：`AGENTS.md` → `PROJECT_MAP.md`（`4dcdad08bd74`）→ `01_project/current/README_CURRENT.md`（`38925c4c7df1`）
→ `01_project/current/` 全 10 文件 → 关键词检索（Grep）+ 文件名检索（Glob/find）+ 只读 git 命令 +
`sha256sum` 复算。未运行任何仿真/CAD/git 写操作。

---

## A. 比赛正式要求定位（对应 04_COMPETITION_REQUIREMENTS_MATRIX）

### A.1 检索结论：仓内无 2026 正式参赛要求文件

- 关键词检索（参赛指南/竞赛通知/比赛通知/提交要求/作品提交/视频要求/参赛手册/大赛章程/未来飞行器/研赛/
  报告书/展架/作品照片/报名/初赛/决赛/poster/submission/deliverable）覆盖 `01_project/`（含 inbox、
  competition、archive）、`50_literature/`、`80_third_party/` 与全仓文件名搜索。
- **零官方文件命中**。`01_project/inbox/` 仅 2 份协作者输入（`01_project/inbox/source_manifest.csv`，
  `7d1d733eb792`，2 行：建议.docx、空间机械臂.docx），无官方指南。
- 唯一描述比赛格式的文件是**归档文件** `01_project/competition/archive/项目现状总览_20260715.md`
  （`e65cf431ba00`）第 11 行：「作品提交硬截止 2026-09-01，初赛纯网评（报告书+附件），决赛现场答辩+可选实物」。
  该路径被 `AGENTS.md`（`3d2269562678`）第 14 行明令「历史文档在 `01_project/competition/archive/`，
  禁作现行依据」——**禁止把它当作 2026 正式要求**。
- 现行版 `01_project/competition/项目现状总览_20260720.md`（`184cacb060fc`）对 初赛/决赛/报告书/展架/
  视频/答辩/实物 七关键词**零命中**——现行总览不含格式描述。
- `COMPETITION_REQUIREMENT_STATUS=UNKNOWN_BLOCKING_FORMAT_CONFIRMATION`（P0，B-CD01）。

### A.2 04_COMPETITION_REQUIREMENTS_MATRIX 内容（仓内证据版）

| 要求项 | 仓内权威证据 | 状态 | 证据指针 |
|---|---|---|---|
| 提交硬截止 2026-09-01 | 仅项目内部文件反复声明（非官方原文） | PROVISIONAL | `AGENTS.md` 第 4 行（`3d2269562678`）；归档总览 0715 第 11 行（`e65cf431ba00`）；用户外部线索一致但非仓内权威 |
| 初赛交付物清单 | 无官方文件 | UNKNOWN | 归档总览 0715 第 11 行称「报告书+附件」（禁作现行依据） |
| 技术报告模板/字段 | 无 | UNKNOWN | 无 |
| 演示视频格式要求 | 无官方要求；仓内已有 h264/1920x1080/55s 视频 | UNKNOWN（要求）+ VERIFIED（资产） | 要求：无；资产：`competition_gate_check.json` VIDEO_PACKAGE（`8b3cdbdaa09e`） |
| 展架图 | 无要求、无资产 | UNKNOWN | 文件名搜索零命中 |
| 作品照片 | 无要求、无资产 | UNKNOWN | 文件名搜索零命中 |
| 实物展示（决策问题 18） | 无官方要求；当前硬件 `B601_MOTION=PROHIBITED` | UNKNOWN（要求）+ HOLD（能力） | 要求：无；能力：`competition_gate_check.json` hardware_component_status（`8b3cdbdaa09e`） |
| 决赛答辩形式 | 无官方文件 | UNKNOWN | 归档总览 0715 第 11 行称「现场答辩+可选实物」（禁作现行依据） |

**决策问题 17 答案：UNKNOWN**（仓内无权威证据；唯一描述在归档文件，禁作现行依据）。
**决策问题 18 答案：UNKNOWN**（仓内无权威证据；且当前硬件运动被机器禁止，若实物必需则为直接冲突）。

---

## B. 交付物现状（对应 12_SUBMISSION_PACKAGE_CHECKLIST 草案）

### B.1 已验证存在的交付物

1. **离线演示链机器 Gate**：`10_research/competition_convergence/competition_gate_check.json`
   （`8b3cdbdaa09e`），`final_verdict=COMPETITION_DEMO_READY`，`checks_passed=17/17`，
   `next_stage_authorized=false`。本次复算其 sha256 与 `01_project/current/CURRENT_GATE_MATRIX_V1.csv`
   （`824cdcfd1f53`）row 2 记录 `8B3CDBDA...` 一致——导航层哈希仍有效。
2. **演示视频**：`40_evidence/artifacts/competition_convergence/competition_mission_intelligence_demo.mp4`
   （`7043d026cef6`，1,572,615 B，h264 1920x1080 54.97s），与
   `evidence_asset_manifest.json`（`33b7bfbf8682`）记录逐字节一致（本次 sha256sum 复算确认）。
3. **演示 PPT**：同目录 `competition_mission_intelligence_demo.pptx`（`9deff92b539c`，177,259 B，9 页），
   哈希复算一致；另有 9 张 1280x720 slide PNG。
4. **比赛 claim-evidence 矩阵**：`10_research/competition_convergence/competition_claim_evidence_matrix.csv`
   （`10c8d503c55e`，9 条数据行），每行绑定 gate JSON + result CSV 行定位 + commit。
5. **claim 边界文档**：`competition_execution_report.md`（`dc8f05268955`）§8 明确不声称清单
   （无实时孪生、无硬件验证、无真实执行权等）。

### B.2 缺口（全部核实为「不存在」而非「未找到路径」）

1. **比赛技术报告书母稿不存在**：`Glob **/*.tex` 零命中；`01_project` 下 docx 仅协作者输入与调研报告；
   无报告书 PDF。`10_research/paper1_architecture.md`（`6df2bec70a72`）是 Acta Astronautica 期刊论文
   架构草稿，**不是比赛报告书**（B-CD02，P0）。
2. **展架图、作品照片不存在**：文件名搜索零命中（B-CD06，P1，因官方要求本身 UNKNOWN）。
3. **submission package / ZIP manifest / restore rehearsal / 提交回执不存在**：仓内 zip 均为机械
   B51R1/F3R2 内部包，无比赛提交包（B-CD03，P0）。
4. **论文级 claim 账本为空**：`10_research/knowledge_base/papers/claim_evidence_ledger.csv`
   （`1cff4ab952b7`，185 B 仅表头）；`controller_state.yaml`（`7eac082162b5`）
   `counts.claim_evidence_rows: 0` 证实（B-CD09，P1）。
5. **根级 `08_REVIEWS/` 为空目录**：独立对抗审查档案缺失；红队 15/15 机器记录存在于
   `competition_gate_check.json` COMPETITION_TESTS_AND_RED_TEAM（`8b3cdbdaa09e`）（B-CD10，P2）。
6. **文档发布门裁决原文不在仓**：bash `grep -rl PUBLICATION_HOLD` 全仓（除 .git）**零命中**；
   `PAPER_KNOWLEDGE_INTEGRITY` 仅出现在 `.codex/skills/paper-knowledge-orchestrator/SKILL.md`
   （`ca0987b18595`）第 104-109 行的 verdict token 定义列表（含 `PAPER_KNOWLEDGE_INTEGRITY_FAILED`），
   **是技能定义而非审计裁决**（B-CD07，P1）。当前分支名 `publication/stage3-integrity-closure` 暗示
   存在发布完整性工作线，但仓内无对应机器裁决文件。
7. **多个互相冲突的 FINAL 版本：未发现**（针对比赛交付物）。仓内 FINAL 命名均为机械 CAD 内部证据文件；
   比赛交付物单一（07-20 冻结一套）。存在的真实风险是**时代差**：演示包口径冻结于 2026-07-20，
   而 08-25 机械终局后系统级 HOLD 增多（见 C.3），答辩引用必须带日期与 scope 限定（B-CD08，P1）。

### B.3 12_SUBMISSION_PACKAGE_CHECKLIST 草案（仓内现状核对版）

| # | 检查项 | 现状 | 证据 |
|---|---|---|---|
| 1 | 官方要求确认（清单/格式/截止） | UNKNOWN（P0 阻断） | §A |
| 2 | 技术报告书母稿 | 缺失（P0） | B.2.1 |
| 3 | 报告 claim→gate 追溯 | 比赛链 9 行可用；论文账本 0 行 | `competition_claim_evidence_matrix.csv`（`10c8d503c55e`）；`claim_evidence_ledger.csv`（`1cff4ab952b7`） |
| 4 | 演示视频 | 存在且哈希一致；格式合规性未知 | `8b3cdbdaa09e` VIDEO_PACKAGE |
| 5 | 答辩 PPT | 存在（9 页）且哈希一致 | `9deff92b539c` |
| 6 | 展架图 | 缺失 | B.2.2 |
| 7 | 作品照片 | 缺失；硬件 PROHIBITED | B.2.2 + N-CD10 |
| 8 | 局限性/对抗审查声明 | 报告 §8 claim boundaries 存在；独立 08_REVIEWS 空 | `dc8f05268955` §8 |
| 9 | 提交 ZIP+manifest+恢复演练+回执 | 缺失（P0） | B.2.3 |
| 10 | 版本锚定（git commit） | 缺失：08-08 后证据全未提交（P0） | §C.1 |
| 11 | 仓库安全（secret/可见性） | secret 扫描净；GitHub 可见性 UNKNOWN | §C.2 |
| 12 | 演示口径时代限定 | 须附加 | B.2.7 |

---

## C. 仓库与安全快照（只读 git）

### C.1 版本状态

- `git rev-parse HEAD` = `5c5addea00ddb70d86a5cc37a88bbcda50350e43`，branch =
  `publication/stage3-integrity-closure`，最后提交时间 `2026-08-08 01:24:43 +0800`（git log -1 --format=%ci）。
- `git log --oneline -10`：全部为 CM3/reorg/文献/收口 chore-docs 提交，无 08-08 之后的提交。
- `git status --short`：**141 条**（复核时两次计数 139→141；+1 可确认为本审计自建的
  `90_competition_closeout/` fragment 目录首次以 untracked 出现，另 +1 未逐项定位，疑为 untracked
  缓存刷新；不影响结论）。分解：**11 条 ` M`（未暂存修改）+ 130 条 `??`（untracked，目录级条目）**。
- 11 条 M 关键条目：`.claude/settings.json`、`.gitignore`、`PROJECT_MAP.md`、`PROJECT_START_HERE.md`、
  `01_project/competition/sim12_literature_closure.md`、`10_research/knowledge_base/papers/README.md`、
  `controller_validation.json`、`simulation/sim_modules_index.md`、`20_engineering/README.md`、
  `20_engineering/system_design/README.md`、`30_simulation/README.md`。
- 130 条 ?? 中关键条目：**`AGENTS.md` 本身**、`01_project/current/`（整个当前权威导航层）、
  `20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/`（08-25 机械终局发布目录）、`30_simulation/sim_13/14/15`、
  `e17`–`e23`、`r2_*` 三个闭环目录、`control_r2_integrated_candidate`、`dynamics_control_prebind_r1`、
  `20_engineering/cad/*` 全部候选、`40_evidence/artifacts/authorization_readiness`、
  `70_tools/current_authority_index`、`70_tools/preauthorization_readiness`、根级 `F3R2_*` 脚本。
- **结论：2026-08-08 之后的全部终局证据与当前导航层均未提交 git**（B-CD05，P0——提交包无法锚定
  commit，机器可复现性当前依赖工作树状态；审计只读，不操作 git，处置权在 Owner）。

### C.2 远端与安全

- `git remote -v` **输出为空**；`.git/config` 无 `[remote]` 节——本地仓无任何远端配置。
- 继承包曾声明的「GitHub README 要求 Private 但元数据 public 且有 forks」风险：在仓内文本搜索
  （GitHub/私有/可见性/fork(s)/镜像）**未定位到原声明出处**；离线无法验证 GitHub 元数据。
  → 记 UNKNOWN，需 Owner 人工登录核对（B-CD04，P0）。
- **Secret scan**（`git grep` 仅扫 tracked 文件，1062 tracked / 845 文本类，只报路径+模式）：
  `AKIA[0-9A-Z]{16}` = 0 命中；`BEGIN .* PRIVATE KEY` = 0；`password` 赋值 = 0；
  `api_key=` 仅 2 个文件（`40_evidence/artifacts/visualization/grasp_geometry_explorer_v0.html`、
  `project_visualization_v0.html`），核实为 Stamen 地图瓦片 URL 占位模板（`...?api_key=` 空值），非凭证；
  `token/secret` 赋值仅安全门代码标识符（路径 token、`ASSEMBLY_SUCCESS`、`allow_unknown: false`）。
  **未发现凭证泄露证据**；未把任何密钥原文写入输出。

### C.3 根目录杂项归属粗判

- `$out/`：空目录；`01_project/current/RETIREMENT_CANDIDATES_V1.csv`（`40398d77af5a`）R-07 记
  `UNKNOWN_NEEDS_OWNER`。
- `__pycache__/`：根级 pyc 缓存，全部来自根级 `F3R2_V5_*` 脚本运行（R-04 `CACHE_CANDIDATE_NOT_APPROVED`）。
- 根级 `F3R2_V5_*.py/.ps1/.md` 共 10 文件：2026-08-09/10 机械 V5 native loop 的 SolidWorks
  ATTACH_ONLY 会话工具（G0 smoke、Loop1B/1C/1C1/1D/1E、Loop2、Loop3）+ 内存释放 ps1 + TOOLING_HOLD
  记录；属机械域历史工具，按 REORG04 不应在根目录，但未授权移动（B-CD11，P3）。

### C.4 `01_project/current/` 与最新 Gate 的新旧关系评估

- 全 10 文件 mtime = 2026-08-27 02:35:46，晚于 `Route_C终局Owner系统边界决策包_20260826.md`
  （`9e9a4156c80f`，mtime 08-27 00:27）与两份 08-27 裁决 md（`3eed50dd728e` 02:35:11、
  `7884373ee9fc` 01:25:54）。
- `CURRENT_GATE_MATRIX_V1.csv`（`824cdcfd1f53`）row 3 已含 2026-08-25 机械终局裁决
  `TERMINAL_CLOSURE_EXECUTED__GATE_A_NOT_PASSED__TMG4_TM6_INTERNAL_BLOCKERS_REGISTERED__NO_RELEASE_CREDIT`；
  row 26-27 含 sim13 20/20 与 post-terminal addendum（并正确标注 `FULL_TMG6_NOT_REISSUED`，
  符合「子模块 PASS 不升级父 Gate」铁律）；row 30 含联合系统 HOLD。
- 矩阵自身声明 `NAVIGATION_ONLY`、无 gate authority（`README_CURRENT.md`，`38925c4c7df1`）。
- **结论：`01_project/current/` 已吸收 8-25 机械终局与 8-27 裁决，是当前最新导航层**；
  但整个目录 git untracked（见 C.1）。

---

## 给综合裁决的输入

1. **比赛官方要求仓内 UNKNOWN**：2026 参赛指南/报告模板/提交字段/视频格式零官方文件命中，唯一格式描述在归档文件 `01_project/competition/archive/项目现状总览_20260715.md:11`（`e65cf431ba00`，禁作现行依据）→ P0，决策问题 17/18 均 UNKNOWN，须 Owner 提供官方文件。
2. **比赛技术报告书母稿不存在**：`Glob **/*.tex` 零命中、`01_project` 无报告书 docx/pdf；`10_research/paper1_architecture.md`（`6df2bec70a72`）是期刊论文架构非比赛报告书 → P0。
3. **无 submission package/ZIP manifest/restore rehearsal/提交回执** → P0，9-01 前须建立打包与回执流程。
4. **版本锚定断裂**：HEAD=`5c5adde`@2026-08-08，`git status --short` 141 条（11 M+130 ??），08-25 机械终局目录、`01_project/current/`、AGENTS.md 本身均未提交 → P0（只读审计不操作 git）。
5. **GitHub 镜像风险不可离线验证**：`git remote -v` 空、`.git/config` 无 remote；继承包「要求 Private 但 public 有 forks」声明未在仓内定位原文 → UNKNOWN + P0，Owner 人工核对。
6. **演示链资产可用且哈希自洽**：`competition_gate_check.json`（`8b3cdbdaa09e`）17/17 `COMPETITION_DEMO_READY`；mp4（`7043d026cef6`）/pptx（`9deff92b539c`）本次复算与 manifest（`33b7bfbf8682`）逐字节一致；但 `next_stage_authorized=false`、`command_emitted=false`、B601_MOTION=PROHIBITED——claim 上限为 offline replay demonstrator。
7. **演示口径时代差**：demo 冻结于 2026-07-20，08-25 后系统 HOLD 增多（`HOLD_AND_NEGATIVE_RESULTS_V1.csv` H-01..H-15，`667dd3bd8a83`）未反映进演示叙事 → 答辩引用必须带日期+scope 限定，P1。
8. **文档发布门裁决原文不在仓**：`grep -rl PUBLICATION_HOLD` 全仓零命中；`PAPER_KNOWLEDGE_INTEGRITY` 仅 `.codex/skills/paper-knowledge-orchestrator/SKILL.md:104-109`（`ca0987b18595`）token 定义 → UNKNOWN，P1。
9. **secret scan 净**：tracked 文本 AKIA/PRIVATE KEY/password 赋值 0 命中；`api_key=` 仅 2 个 visualization HTML 的 Stamen 瓦片 URL 空占位 → 无凭证泄露证据（仅所扫模式）。
10. **`01_project/current/` 为最新导航层且新旧关系正确**：mtime 08-27 02:35:46 晚于全部 08-26/27 裁决；矩阵 row 3 已含 08-25 机械终局、row 26-27 正确标注 `FULL_TMG6_NOT_REISSUED`；但整目录 untracked。
