# 10 五日收口计划（FIVE_DAY_CLOSEOUT_PLAN）

- 生成日期：2026-08-27；硬截止：2026-09-01；生成者：综合代理 SYN-C。依据：`09_COMPETITION_DECISION_MEMO.md` §b/§c 缺口清单与解除条件。
- 资源配比（人时占比）：**40% 证据复算与图表 / 25% 控制演示 / 20% 报告材料 / 10% 提交安全 / 5% Route-C 只读跟踪**。
- 全程红线（每日适用，违反即审计事故）：
  - 禁止新 VLA 训练（`PREBIND_AUTHORITY.json` `$.owner_authorization.prohibited_scope` 含 RL/VLA，sha256 `e1157532605b`）；
  - 禁止整星重设计、禁止新末端执行器；
  - 禁止无合同 Monte Carlo；
  - 禁止第二条在轨装配主线（Wave A 维持 `PLANNED_NOT_AUTHORIZED`，`10_research/research_state_v4.md` 第 14-16 行，`1bd051d86368`）；
  - 禁止制造级 CAD 补细节；
  - 禁止 Route-C 伪闭合（P08/P10/P11 null 不得零填；provisional 不得入 SSOT）；
  - 禁止删除任何旧负结果/REPEAT/HOLD 记录；
  - 禁止最后一天（9-01）改核心模型或核心数字。

## 每日任务卡

### Day 1 — 2026-08-27（权威/规则/安全冻结日）

| 任务 | 内容 |
|---|---|
| T1.1 | Owner 动作启动：下载 2026 正式参赛指南+模板并登记（解 B-CD01）；发起 GitHub 可见性/forks 人工核对（B-CD04）；标题收窄决定签收（BLK-MEM-01，候选见 `13_TITLE_AND_CLAIM_CEILING.md`）。详见 `11_OWNER_ACTIONS_REQUIRED.md` |
| T1.2 | 冻结叙事基线：唯一科学主问题表述一次选定（BLK-MEM-03）；claim 禁用词表（红线六篇+四词）定稿进材料审校 |
| T1.3 | 安全冻结：secret scan 结论复核记录归档（compdeliv §C.2：tracked 文本 AKIA/PRIVATE KEY/password 赋值 0 命中）；确认仓库公开/外链分支冻结（fail-closed 条件 13 TRIGGERED） |
| 输入 | 7 fragments；`09` 备忘录 §c；官方指南（Owner 取回） |
| 输出 | 04 矩阵回填版（SYN-A/B 文件）；标题冻结签发记录；安全冻结记录 |
| 验收条件 | 04 矩阵每行有官方文件出处；标题签发含 PENDING 解除时间戳 |
| 阻塞条件 | 官方指南当日无法取得 → T1.1 转入 8-28 上午，COMPETITION_SUBMISSION 维持 CONDITIONAL_GO 但标注升级风险 |
| 可否并行 | T1.1/T1.2/T1.3 全部可并行 |
| 不完成的影响 | 后续所有材料无格式权威依据与标题基准，8-30 报告/PPT 无法定稿 |
| 禁止范围扩张 | 不启动报告正文撰写；不重排任何 Gate |

### Day 2 — 2026-08-28（数字复算+六图+claim-evidence 冻结日）

| 任务 | 内容 |
|---|---|
| T2.1 | 核心数字复算与六图定稿（40% 资源主线）：按 dyn fragment §6 row locator 表复算 sim_05/06/07/08/10/11/12 图表数字；六图候选=基座扰动 19.20°、捕获后 3.0633°/s、92× 激振比、|H_c|=3.65 N·m·s/12×、可行域 F1-F4、策略阶梯（binding gate） |
| T2.2 | **sim_10 哈希锁重钉**（解 DYN-B03）：按 REORG04 规则 5 将 `scan_v0.yaml` 冻结输入重钉到当前路径哈希（`006c6cc5…`/`75af082a…`）并重跑 R 门重发 gate；分钟级、内部可闭环；历史裁决 `SIM10_GATES_PASS`（`4dbd8c91ff34`）语义不变 |
| T2.3 | claim-evidence 矩阵 append-only 重冻结（解 BLK-MEM-02）：逐 claim 重绑当前 Gate 哈希，并入 08-23 查新红线禁用句与绿线检索截止声明（截止 2026-07-18 + 08-23 补检，`67ea28a65be4` §G） |
| 输入 | dyn fragment §6 表；`scan_v0.yaml`（`856f1e30de47`）；git diff 284c882 语义等价证据 |
| 输出 | 六图 PNG+源数据 locator 表；重钉后 sim_10 gate；重冻结 claim 矩阵 |
| 验收条件 | 每图数字=CSV 行定位复算值；R 门重跑 PASS；矩阵每行含 gate sha256+当前 HEAD 锚 |
| 阻塞条件 | R 门重跑 FAIL 且差异不能归因 REORG04 → 停止引用 sim_10 可行域图，降级为表格陈述并登记 |
| 可否并行 | T2.1 与 T2.3 可并行；T2.2 须先于 T2.3 中 sim_10 行重绑 |
| 不完成的影响 | 报告/答辩数字无当前树可复现锚；claim 审校无机器依据 |
| 禁止范围扩张 | 不重跑任何新仿真场景；不改 sim_10 物理口径；e15 legacy 不 resurrect |

### Day 3 — 2026-08-29（受限控制链+三场景离线重放验证+SAFE 故障注入最小集）

| 任务 | 内容 |
|---|---|
| T3.1 | 受限控制链演示口径固化（25% 资源主线，对应 E-COMP-04）：以 supervisor 合同枚举（`CTRL_R2_SUPERVISOR_INTERFACE_V1.json`，`5bfd8ab0672d`）+ PB_G1 NOT_EVALUATED 边界为限，准备「离线重放+合同枚举」答辩口径；不声称任何运行时闭环 |
| T3.2 | EXECUTE/MODIFY/ABORT 三场景离线重放验证：按当前树重放 `competition_gate_check.json` 登记的三场景（A_low=EXECUTE/B_anchor=ABORT/C_transition=MODIFY），以当前 sha256 重新核验动作序列与媒体一致性，产出「REORG04 后重验证记录」解除 OFFLINE_DEMO=REPEAT 的当前树疑虑（历史 byte-identity 保持历史结论表述） |
| T3.3 | SAFE 故障注入最小集（对应 E-COMP-03）：仅复用冻结 12 绕过案例+2 降级案例做当前树离线复跑并记录漂移差异（23/47 HOLD 现状如实登记）；不做新故障注入设计、不触碰 HMAC 密钥资格（W1-R01 开放项保持开放） |
| 输入 | `competition_gate_check.json`（`8b3cdbdaa09e`）；SAFE-00 gate（`ff56929dd835`）；`CTRL_R2_PREDEVELOPMENT_GATE_V1.json`（`ed4d8b7774c6`） |
| 输出 | 答辩口径卡（含 ABORT_ONLY 限定）；三场景当前树重放记录；SAFE 最小集复跑记录 |
| 验收条件 | 重放动作序列与 Gate 登记一致；所有演示话术经 claim 审查（BLK-SIM13-08）；SAFE 复跑差异逐条归因 REORG04/定位漂移 |
| 阻塞条件 | 当前树重放与冻结动作不一致 → 演示降级为 07-20 录像+显式日期限定，差异登记为负结果不得掩盖 |
| 可否并行 | T3.2 与 T3.3 可并行；T3.1 依赖两者结论定稿 |
| 不完成的影响 | OFFLINE_DEMO 维持 REPEAT 状态提交（可提交但须带限定语）；决赛答辩演示可信度降档 |
| 禁止范围扩张 | 不申请任何 bounded 在线演示授权；不启动 PB_G0-A 关闭以外的 prebind 新范围；不重发 SAFE/CTRL 任何 Gate（PENDING_REVIEW 归 Owner，见 `11` 第 4 项） |

### Day 4 — 2026-08-30（报告/PPT/视频/展架图产出日，20% 资源）

| 任务 | 内容 |
|---|---|
| T4.1 | 比赛技术报告母稿撰写（解 B-CD02）：按 04 矩阵模板字段从零建立；结构=标题页（已冻结标题）+唯一科学主问题+五创新锚点+可行域/策略/安全验证证据+边界与负结果声明+局限性；逐 claim 绑定 gate JSON+locator+sha256（引用纪律见 `00_READ_FIRST.md`） |
| T4.2 | PPT/视频按当前状态核对与必要重渲染（解 VIDEO=REPEAT、B-CD08）：07-20 媒体（mp4 `7043d026cef6`、pptx `9deff92b539c`）逐页核对，凡涉系统能力表述处补 07-20 日期+scope 限定；如需重渲染仅改文字层，不改任何数值 |
| T4.3 | 展架图/作品照片决策执行（B-CD06，依 Day1 官方要求结论）：若要求存在且无实物→冻结 operational baseline 结构图+动画帧替代方案 |
| 输入 | 04 矩阵回填版；重冻结 claim 矩阵；六图；三场景重放记录 |
| 输出 | 报告母稿 v1；PPT/视频更新版；展架图（如要求确认） |
| 验收条件 | 报告每数字有 locator；无禁用词表词汇；所有演示引用带日期+scope；ABORT_ONLY/HOLD 限定并置 |
| 阻塞条件 | 04 矩阵未回填（官方要求未确认）→ 报告按「通用技术报告结构」撰写并留格式回填占位，COMPETITION_SUBMISSION 不升级 |
| 可否并行 | T4.1 与 T4.2/T4.3 可并行（不同执笔） |
| 不完成的影响 | P0 未闭合，9-01 无法合规提交 |
| 禁止范围扩张 | 不新增任何超出五锚点的创新声称；不引用 Wang 96%/94% 等未核验数字；不使用继承包状态数字（BLK-MEM-05） |

### Day 5 — 2026-08-31（红队/secret scan/离线恢复/ZIP/提交演练日，10% 资源）

| 任务 | 内容 |
|---|---|
| T5.1 | 提交包红队自审：对照 `09` §d fail-closed 清单 15 条逐项过检；对照禁用词表与 ABORT_ONLY/HOLD 限定做全文扫 |
| T5.2 | 打包与恢复演练（解 B-CD03）：生成提交 ZIP+sha256 manifest（含报告/PPT/视频/展架/证据指针附录），在干净目录做离线恢复演练并记录，产出提交回执登记表 |
| T5.3 | git 锚定执行（解 B-CD05，Owner 决策后）：按 Owner 授权提交或建立独立 sha256 清单；GitHub 处置结论归档（B-CD04 书面裁决） |
| 输入 | 报告母稿 v1 + 全部媒体定稿；`12_SUBMISSION_PACKAGE_CHECKLIST.md` |
| 输出 | 提交 ZIP+manifest+恢复演练记录+回执登记；红队自审记录；git 锚定凭证 |
| 验收条件 | 恢复演练一次通过（解包后哈希全对）；回执字段完整；红队 15 条全 NOT_TRIGGERED 或已冻结分支明示 |
| 阻塞条件 | 恢复演练失败 → 重打包再演练，当日必须闭合；官方格式仍 UNKNOWN → 按「冻结对应分支」仅提交已确认渠道部分并登记 |
| 可否并行 | T5.1 与 T5.2 可并行；T5.3 依赖 Owner 前置决策 |
| 不完成的影响 | CONDITIONAL_GO 条件 4 未闭合 → NO_GO 风险 |
| 禁止范围扩张 | 不改任何 Gate/数字/模型；不新增交付物类型 |

### Day 6 — 2026-09-01（终核提交日）

| 任务 | 内容 |
|---|---|
| T6.1 | 终核：对照 `12_SUBMISSION_PACKAGE_CHECKLIST.md` 全表勾选；确认四项解除条件闭合凭证齐 |
| T6.2 | 提交并留存回执；提交后仓库状态快照归档 |
| 输入 | Day 5 全部产出 |
| 输出 | 提交回执；最终状态快照 |
| 验收条件 | 回执取得；checklist 无 MISSING 项（或 MISSING 项均有官方要求豁免证据） |
| 阻塞条件 | 任何核心数字与 8-31 冻结值不符 → 当日禁止修正，登记差异延期处理 |
| 可否并行 | 否，串行终核 |
| 不完成的影响 | 错过硬截止 |
| 禁止范围扩张 | **禁改核心数字、核心模型、Gate、叙事口径** |

## Route-C 只读跟踪（5% 资源，全程）

- 每日一次只读核对：ODR-60 预搜索 8 项 blocker（`869a248050fd`）与 V9F 终局（`09611ddb8adc`）状态是否被更晚 Owner 指令改变；如有改变只登记到次日计划，不主动推进。
- 禁止：Route-C 伪闭合、P08/P10/P11 零填、provisional 升 SSOT、把 V9F 负见证从叙事中移除。
- 杨恒三项待办（帆板面密度占位、T_c 实测、数值案例）与 Route-C 外部参数统一排赛后，见 `11_OWNER_ACTIONS_REQUIRED.md` 第 6/7 项。
