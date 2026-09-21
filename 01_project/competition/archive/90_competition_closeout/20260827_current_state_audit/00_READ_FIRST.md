# 00 先读我（READ_FIRST）——2026-08-27 当前状态审计包导航

- 审计日期：2026-08-27；项目：中国研究生未来飞行器创新大赛（第十二届），提交硬截止 2026-09-01。
- 本包 = 7 个只读审计分片（fragments/）+ 3 个综合代理产出（本目录编号文件）。本文件由综合代理 SYN-C 生成。

## 1. 文件清单与一句话用途（16 项）

| # | 文件 | 用途（一句话） | 生成方 |
|---|---|---|---|
| 00 | `00_READ_FIRST.md` | 本导航：清单、机器状态速览、使用规则、审计边界 | SYN-C |
| 01 | `01_REPOSITORY_AND_SECURITY_SNAPSHOT.json` | 仓库与安全快照（git 锚定/远端/secret scan 的机器可读底账） | SYN-A / SYN-B |
| 02 | `02_CURRENT_AUTHORITY_SELECTION.json` | 当前权威选择记录（多源冲突时以哪份 Gate 为准） | SYN-A / SYN-B |
| 03 | `03_CURRENT_GATE_MATRIX.csv` | 当前 Gate 总表（全量机器裁决索引） | SYN-A / SYN-B |
| 04 | `04_COMPETITION_REQUIREMENTS_MATRIX.csv` | 比赛要求矩阵（官方要求到位前为仓内证据版，含 UNKNOWN 行） | SYN-A / SYN-B |
| 05 | `05_RESEARCH_GAP_MATRIX.csv` | 研究缺口矩阵 | SYN-A / SYN-B |
| 06 | `06_CLAIM_EVIDENCE_MATRIX.csv` | claim-evidence 综合矩阵 | SYN-A / SYN-B |
| 07 | `07_NEGATIVE_RESULT_REGISTER.csv` | 负结果登记册（IMMUTABLE，删除即审计事故） | SYN-A / SYN-B |
| 08 | `08_FORMAL_RELEASE_BLOCKERS.csv` | 正式 Release 阻断项汇总 | SYN-A / SYN-B |
| 09 | `09_COMPETITION_DECISION_MEMO.md` | 决策备忘录：13 行机器状态头 + 20 个决策问题逐条带证据回答 + P0/P1/P2/P3 缺口 + CONDITIONAL_GO 解除条件 + fail-closed 15 条核对 | SYN-C |
| 10 | `10_FIVE_DAY_CLOSEOUT_PLAN.md` | 8-27→9-01 逐日收口计划：任务输入/输出/验收/阻塞/并行性/禁止扩张，资源配比 40/25/20/10/5 | SYN-C |
| 11 | `11_OWNER_ACTIONS_REQUIRED.md` | 须 Owner/外部完成的 7 件事（官方指南、实物确认、GitHub 处置、Gate 复核、标题签收、Route-C 延期、杨恒待办排赛后） | SYN-C |
| 12 | `12_SUBMISSION_PACKAGE_CHECKLIST.md` | 提交包 18 项可勾选清单（READY/INCOMPLETE/MISSING+证据） | SYN-C |
| 13 | `13_TITLE_AND_CLAIM_CEILING.md` | 推荐标题（PENDING_OWNER_SIGNOFF）、四词证据评估、叙事五问、作品定义 | SYN-C |
| 14 | `14_CURRENT_STATE_DELTA_20260827.md` | 相对继承包/AGENTS.md(08-25) 的增量清单 + 核心数字复核表 + Sim13 双口径 | SYN-C |
| 15 | `15_SOURCE_AND_HASH_MANIFEST.csv` | 来源与哈希清单（全部引用文件的 sha256 底账） | SYN-A / SYN-B |
| 16 | `fragments/` | 7 分片×5 文件（gate_rows/negatives/blockers/hashes/findings）原始证据层，全部结论可追溯至此 | 7 只读分片代理 |

## 2. 机器状态速览（09 备忘录头部 13 行原样收录）

```
COMPETITION_SUBMISSION = CONDITIONAL_GO
COMPETITION_SCOPE = 物理约束抓捕策略选择与失效闭合安全验证（离线、确定性重放、受限任务包络）
MECHANICAL_MAIN_BODY = FROZEN
ACTIVE_MECHANICAL_WORK = ROUTE_C_ONLY（V9F 已被 M01 负见证终局否决、ODR-60 Option A 预搜索 fail-closed；维持 KNOWN HOLD，不入正式 SSOT）
DYNAMICS_CONTROL_PREBIND = GO
FORMAL_MECHANICAL_RELEASE = HOLD（00_RELEASE_GATE.json：TERMINAL_CLOSURE_EXECUTED__GATE_A_NOT_PASSED…NO_RELEASE_CREDIT）
FORMAL_CONTROL_RELEASE = HOLD（CTRL-01 REPEAT；CTRL-02 PASS_WITH_PROVISIONAL_SCOPE+PENDING_REVIEW；联合 Gate 4/13）
SIM13_CURRENT_SYSTEM = ABORT_ONLY（ABORT_ONLY_WITH_VALIDATED_FAIL_CLOSED_BACKENDS_20_OF_20_NC__PRODUCTION_NON_ABORT_STILL_MASKED_BY_12_GATE_AUTHORITY）
OFFLINE_DEMO = REPEAT（17/17 资产在且哈希自洽，但口径冻结于 07-20、REORG04 哈希漂移未闭环，须当前树重验证）
PHYSICAL_DEMONSTRATOR = UNKNOWN（2026 官方要求仓内缺席）
REPORT = HOLD（比赛技术报告母稿不存在，须从零建立）
VIDEO = REPEAT（07-20 媒体在，需按当前状态核对/重渲染）
SUBMISSION_PACKAGE = INCOMPLETE（无包/无恢复演练/无回执；HEAD 停在 2026-08-08、130 untracked 未锚定）
```

注：`DYNAMICS_CONTROL_PREBIND = GO` 仅限诊断性 prebind 工作线（`PB_G0_HOLD_PARTIAL_AUTHORITY__DIAGNOSTIC_PREBIND_ONLY__NO_RELEASE_CREDIT`，`30_simulation/dynamics_control_prebind_r1/10_verification/PB_G0_GATE.json`，sha256 前 12 位 `da2bbe1381a0`），不含正式控制发布信用。

## 3. 如何使用本包（评委材料引用规则）

1. **每个数字必须带证据指针**：路径 + JSON key/行定位 + sha256 前 12 位。示例：`sim_06` 捕获后残余角速度 3.0633°/s → `30_simulation/sim_06_capture_impulse/results/capture_impulse_matrix_v0.csv` 第 15 行 `post_rate_full_dps=3.06333`（`8cbad84b8ff6`）。
2. **双口径引用规则（Sim13）**：父 Gate 15/20 冻结未重发 + 子域 20/20 append-only，两者必须并置，且最高运行态恒为 ABORT_ONLY；只引其一即失真（依据 `14` §C）。
3. **限定语强制**：SAFE-00/CTRL-02/e23 引用必带 PENDING_REVIEW/PENDING_OWNER_REVIEW 与 `next_stage_authorized=false`；CTRL-01 必带「冻结增益与预注册轨迹下」；sim_11 必带 PROVISIONAL 占位声明；离线 demo 引用必并置 `command_emitted=false` 与 07-20 口径日期。
4. **红线**：UNKNOWN≠EXECUTE；source-only≠current-system；模块 PASS≠执行授权；子 PASS 不升级父 Gate；不得删除/淡化任何 REPEAT/HOLD/负结果；不得引用继承包状态数字（部分 SUPERSEDED，见 `14` A10）；不得引用 Wang 2026 的 96%/94% 等未核验数字。
5. **禁用词**：「具身智能/自主抓取/数字孪生/在轨装配」在 Owner 签收标题冻结前不得进任何对外材料（评估见 `13` §2）。

## 4. 本审计边界

- 只读：未执行任何 git 写操作、未覆盖/移动/删除任何项目文件、未运行 CAD/仿真、未重发任何 Gate。
- 全部 sha256 前 12 位由各分片用 Git Bash `sha256sum` 现算（见各 fragment `hashes.csv`）；SYN-C 对状态头关键 Gate（00_RELEASE_GATE、competition gate、SIM13 20/20、CTRL-01/02、SAFE-00）与 git 快照做了独立复核，结论一致。
- 本包不产生新的科学结论；所有裁决字符串均逐字引自既有机器 Gate JSON。
- SYN-A/SYN-B 文件与本文件并行生成，交叉引用以文件名约定为准，未做相互等待；若编号文件暂缺，以 fragments/ 为最终证据层。

## 5. 生成方式

7 个只读分片代理（mech/dyn/ctrl/sim13/embodied/compdeliv/memory）各自产出 5 个 fragment 文件（共 35 个，含各自 sha256 复算记录）→ 3 个综合代理（SYN-A/SYN-B/SYN-C）并行生成编号文件 → 本目录为唯一新增写入位置（`90_competition_closeout/20260827_current_state_audit/`，经任务书显式授权，优先于 REORG04 八域限制）。
