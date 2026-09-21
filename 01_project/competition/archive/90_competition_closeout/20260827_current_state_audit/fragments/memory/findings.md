# memory 分片审计发现（继承包、叙事与 claim 边界域）

- 审计日期：2026-08-27（本地）；审计模式：只读；分片：memory。
- **写入授权记录**：本 fragment 目录 `90_competition_closeout/20260827_current_state_audit/fragments/memory/` 由用户（Owner 侧审计任务书）显式授权创建，优先于 `AGENTS.md` L6-9（REORG04 根目录八域限制，sha256 `3d2269562678`）。本域其余操作均为只读：未执行 git 写操作、未改动任何现有文件、未运行 CAD/仿真、未重发 Gate。
- 范围声明：本域只审计叙事/claim/继承关系；sim_10/sim_11 gate JSON 的数值复核由动力学分片承担，本域引用其裁决字符串时以 `AGENTS.md` L20-31 与 `10_research/framework_convergence/claim_evidence_matrix.csv`（sha256 `7d296e7a2437`）C13/C15 行的转录为准。

---

## 1. 唯一科学主问题的现行表述：三版本并存，未收敛

- 表述 A「面向抓取后可稳定性的预见式具身抓取」：`AGENTS.md` L4（sha256 `3d2269562678`）；同源见于 `PROJECT_ONBOARDING_PACKAGE/01_PROJECT_OVERVIEW.md` L17（sha256 `a373f13a9d47`）与 `PROJECT_ONBOARDING_PACKAGE/PROJECT_TRUTH_INDEX.json` 对 `research_state_v4.md` 的描述行（sha256 `e348749b9525`）。
- 表述 B「物理约束空间具身任务智能（捕获任务智能 → 装配闭环）」：`01_project/competition/项目现状总览_20260720.md` L3-4（sha256 `184cacb060fc`），且 L13 确认比赛链「不依赖装配 Wave A」——即表述 B 的「装配闭环」半句从未获得执行授权。
- 表述 C（项目总标题）「面向非合作航天器在轨服务的动力学约束具身任务决策与刚柔耦合捕获方法」：`01_project/competition/研究战略裁决_第二收敛点_20260717.md` §2.3 L75-77（sha256 `ced773571d74`）；该文文首 ⚠ 注自声明「状态与日历已过期」，且「具身任务决策」措辞与 08-23 查新红线存在张力。
- 结论：三者语义兼容（都指向决策层+可行域），但**没有一份现行文档把唯一主问题收敛为单一表述**；09-01 材料前须由 Owner 一次选定（BLK-MEM-03，P1）。

## 2. 五类可冻结主张的证据锚点（全部机器可核）

1. **Binding-gate 策略选择**：`30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json`（sha256 `a416c1348111`）`gates.GS2_differentiation.best_per_case`：A_low→S1_passive、B_anchor→ABORT、C_transition→S3a_wheel_bias、D_extreme→ABORT；`GS3_claim_audit.allowed[0]` 允许措辞原文「Strategy selection depends on the active physical constraint (binding gate)」。
2. **多门失效闭合可行域**：framework 矩阵 C13 行（sha256 `7d296e7a2437`）：9002 物理点、`SIM10_GATES_PASS`、6323 wheels-only/1858 rate/730 thruster/91 resource；查新裁决 §3 绿线第 1/2 条（sha256 `3be39f02c15a`）锚定 sim_10/sim_08。限定：执行机构档与 3600s 为 PROVISIONAL。
3. **局部冲量改善可恶化全局角动量/资源（sim_12 反例）**：同 gate `GS3_claim_audit.allowed[1]`「B_anchor S2 impulse 0.194 N·s vs S1 0.338 N·s while H increases」；`forbidden[0]` 禁写「momentum shaping always improves capture」；`30_simulation/sim_12_strategy_feasibility/docs/strategy_comparison_report.md` L20-21（sha256 `5bb7c6a71677`）：B/D 瓶颈是速率门（2°/s registry）→ ABORT。`|ΔH_vec|` 与 `|H|` 标量变化不得混用（AGENTS.md L27）。
4. **候选—物理评价—SAFE—传统控制分层**：`10_research/on_orbit_assembly/dual_mission_literature_synthesis.md` §2 合法执行链与 §5.4（sha256 `88118670c35d`）：EXECUTE/MODIFY/ABORT 均为离线解释标签，`execution_authority=false`、`command_emitted=false`；SAFE-00 侧 framework C17 行：47/47、`unknown_allow=0`、`bypass_success=0`，但 `next_stage_authorized=false`。L4 具身层为 PLANNING ONLY（`PROJECT_CURRENT_STATUS.md` EMBODIED_AI 行，sha256 `cce6517b4cd5`）。
5. **负结果与 UNKNOWN 的机器可审计治理**：`10_research/contribution_map/paper1_contribution_map.md` C4 段 L48-59（sha256 `3453adfe30e7`）：覆盖/科学/认证/授权四分离、e15 REPEAT、SAFE 不授权；framework 矩阵 C10/C11/C18/C20 行为同构机器登记；CP6 终裁（`wave1_cp6_ruling.md` L16-17，sha256 `1eeea3ccffb1`）：`WAVE1_REPEAT` 原样入档。限定：治理本身学术新颖性未检索（C4 remaining_gap 自声明）。

## 3. 红线 prior-art 与绿线（查新裁决原文核验）

裁决全文 `01_project/competition/文献查新裁决_claim边界_20260823.md`（sha256 `3be39f02c15a`）：

- **红线核验状态**（§1 表 + §2 表）：① Wang 2026（AA 245:1035–1054）DOI 题录通过，**实验数字 50次/96%/94% 未核验，引用前必须读原文**；② Lu 2026（AST 177:112197）DOI 通过，摘要级方法描述未核验——「首次结构–接触–任务一体化框架」类声称**禁用**；③ Ma 2026（Sci Rep，OA）**全文页已读**：perception-informed RL-ISC、纯仿真——视觉+RL 自主抓取禁用为具身智能论文一号贡献；④ Cai 2026（Astrodynamics）摘要已读无全文，且 §4.3 记 Cai 组自 2023 起系统性占位——data-driven post-capture 方向**整体放弃作创新**；⑤ Mao 2026（FITEE 27(7)）DOI 题录通过——Koopman/model-free 只作工具层；⑥ AA 246:734–744 RL detumbling，Crossref 题录 2026-08-23 核验通过（§5.2 行动项 2 已勾销）。
- **检索截止纪律**：E 节存在性结论「binding-gate dependent strategy selection 未见」维持，检索截止 **2026-07-18**，08-23 补检索后结论不变；引用一律附截止与范围声明（`sim12_literature_closure.md` §G，sha256 `67ea28a65be4`；其文首覆盖度声明为「本次检索范围内未见」级、十轮检索 14 篇）。缺口审计 §6 第 3 项（两个存在性结论各找 2 名独立核查）**仍未闭环**（同文 §F）。
- **绿线五项**（§3 表，均带机器锚点）：F_i/∂F_i 策略级可行域（sim_10）；pre-capture→post-capture infeasibility 判据 ω_post≤ω_allow、H_required≤H_available（sim_08→sim_10）；SAFE/UNKNOWN/UNSAFE fail-closed（SAFE-00 47/47）；binding-gate strategy selector（sim_12 Phase1）；embodied candidate + independent physics veto（PLANNED_NOT_AUTHORIZED 规划线，不受本轮影响）。
- **prebias=S3a 护栏原文**（§2 表 row1 + AGENTS.md L44）：momentum prebias = sim_12 S3a 候选策略（C1 Dimitrov & Yoshida 2004 直系祖先；Wang 2026 只是推进到 2026 双臂地面实验）；S3a 定位不变：候选策略类，研究问题是「轮组容量 8%（0.3 vs 3.65 N·m·s）下预置量换多少可行域边界改善」，**不得包装成「新抓捕方法」**。

## 4. 标题证据评估与收缩建议

| 标题词 | 证据结论 | 收缩建议 |
|---|---|---|
| 具身智能 | `PROJECT_CURRENT_STATUS.md` EMBODIED_AI=PLANNING LAYER ONLY（VLA=PROTOCOL_DRAFT、Physics Tool=DRAFT_NOT_IMPLEMENTED）；framework C23/C24 均 NOT_EVALUATED；Ma 2026 红线 | 不作主标题贡献词；限展示叙事/future work |
| 自主抓取 | framework C25：H0_H3_NOT_STARTED；继承包 §2 L-3 感知 PLANNED；查新 §2 红线 | 改为决策层措辞「物理约束抓捕策略选择」 |
| 数字孪生 | framework C21：DT2_SCOPE_LIMITED_OFFLINE_REPLAY，回放早于 sim10-12/SAFE/CTRL/ASM 当前状态；contribution_map F2=BLOCKED | 只称「确定性离线 DT2 证据回放」并注明 command_emitted=false |
| 在轨装配 | `research_state_v4.md` L14-16 PLANNED_NOT_AUTHORIZED；framework C26-C29 全 NOT_EVALUATED；master_plan 最终裁决 READY_WITH_INTERFACE_BLOCKERS | 不进主叙事/标题；仅路线图 |

- **默认候选标题核验**：「面向翻滚非合作目标的自由漂浮空间服务航天器：基于 Binding-Gate 的物理约束抓捕策略选择与失效闭合安全验证」全仓 grep **零命中**——它不在任何现行文档中。一致性评估：与 Paper 1 冻结 EN 题（`paper1_contribution_map.md` L5「Strategy Selection under Momentum and Stability Constraints … Binding-Gate Criterion」，sha256 `3453adfe30e7`）、查新绿线五项、fail-closed 治理叙事**方向一致**，且避开了全部红线词与四个证据不足词；但**尚未获 Owner 冻结**（BLK-MEM-01，P0）。

## 5. On-Orbit Assembly Wave A 状态与阻塞项原文

- 状态原文（`10_research/research_state_v4.md` L14-16，sha256 `1bd051d86368`）：「当前唯一候选科学实施主线为 On-Orbit Assembly Wave A；在 HAG-A 前为 `PLANNED_NOT_AUTHORIZED`，并受 RF-1/2/3、目标侧 FFR/AG4、W1-R12/R13 阻塞。」AGENTS.md L29 同口径。
- 阻塞项原文（`10_research/on_orbit_assembly/master_plan.md` 最终裁决段 L9-17，sha256 `dea2436daa5e`）：最终裁决 `READY_WITH_INTERFACE_BLOCKERS`；「RF-1 锥面聚拢 2.14mm<5mm 几何不自洽、RF-2 楔紧边界、RF-3 clearance 语义、SSOT 缺销距/倒角字段、全卡无 MEASURED 出处——这些是 ASM-00 的 LOOP-1 入口判据而非停工理由」；Wave 结构段：「Wave A（待批）」；verdict 词表强制 `_WITH_PROVISIONAL_PARAMS`，ASM-01 上限 SCREENING_ONLY。
- 比赛解耦原文（同文 AR7 段 + 0720 总览 §四）：「比赛材料主线独立于装配线……8 月中材料冻结时不依赖 Wave A 结果」。归类 P3（BLK-MEM-07）。

## 6. 继承包与 AGENTS.md 真值入口的新旧关系

- `PROJECT_ONBOARDING_PACKAGE/` 生成于 2026-07-29（`PROJECT_TRUTH_INDEX.json` `_meta.generated_utc`，sha256 `e348749b9525`），其权威声明（README_NEW_MEMBER §4，sha256 `aa9ff833c3e9`）自认 Level 0 Gate JSON 为最终依据，与 AGENTS.md 真值入口**纪律同构、不构成平行 SSOT**。
- **已 SUPERSEDED 的部分**（实证）：① 真值索引内 `CLAUDE.md` sha256 `cb851e2f…` ≠ 当前 `d6cdd83a9775`（current CLAUDE.md sha256 `d6cdd83a9775`）、`PROJECT_MAP.md` `09dd9fa8…` ≠ 当前 `4dcdad08bd74`（项目现状总览 `184cacb0…` 仍匹配）——索引哈希部分失配；② 继承包机械主线停在 B5.1R1 Phase 1（TIMELINE L41，sha256 `c875df1cb6a5`），已被 PL1（08-08）→ F3R2 → Terminal Mechanical Closure（08-25，`AGENTS.md` L33-39）→ R2 双裁决（08-27）supersede；③ 继承包机械臂质量写 `4.6955559493429862 kg`（01_PROJECT_OVERVIEW L57），层级文件为 `4.695555949342986 kg`（`PROJECT_MODEL_TRUTH_HIERARCHY.yaml` L25，sha256 `c3a28ee3d796`），末位多一个「2」，属转录差异，以 L0 层级文件为准。
- 结论：继承包=**历史导航层**（SUPERSEDED partial），其证据纪律条款仍有效；答辩/提交材料禁止引用继承包状态数字（BLK-MEM-05，P1）。

## 7. 其他域交叉的关键发现（供综合裁决注意）

- **ODR-60 Option A token 同日措辞冲突**：`R2动力学与控制工程闭环阶段裁决_20260827.md` §2.1（sha256 `3eed50dd728e`）记 `AUTHORIZE_OPTION_A_FIXED_ENDPOINT_M01_TRAJECTORY_SEARCH` 已 RECORDED（证据类 EXPLICIT_EXECUTION_PROMPT_BLOCK_FIRST_LINE）；`R2航空宇航机械与控制预开发阶段裁决_20260827.md` §1/§5（sha256 `7884373ee9fc`）写「本轮未取得…token」「若 Owner 决定继续」。按权威顺序以机器联合 Gate 为准：`R2_DYNAMICS_CONTROL_SYSTEM_GATE_V1.json`（sha256 `55490805d934`）`owner_option_a_selection_recorded=true`、`path_search_executed=false`、`joint_system_ready=false`、`next_stage_authorized=false`、`release_credit=false`。统一口径：**分支选择已记录，执行未授权**（BLK-MEM-04，P1；不回改裁决原文）。
- **Sim13 子新父旧**：`Route_C终局Owner系统边界决策包_20260826.md` §2（sha256 `9e9a4156c80f`）：旧 15/20 快照被 20/20 后端包 supersede，但 `next_stage_authorized=false` 与 no-release 结论仍然正确，最大运行态 `ABORT_ONLY…MASKED_BY_12_GATE_AUTHORITY`；记 `CHILD_RESULT_NEWER__PARENT_GATE_NOT_REISSUED`，叙事中 20/20 必须带 ABORT_ONLY 限定。
- **管理默认状态核实**：08-27 两份裁决与联合 Gate 均未改变 MECHANICAL_MAIN_BODY=FROZEN / ACTIVE=ROUTE_C_ONLY / FORMAL 双 release=HOLD / OFFLINE_PHYSICS_GATED_DEMO=GO（competition_gate_check.json `COMPETITION_DEMO_READY` 17/17，sha256 `8b3cdbdaa09e`）/ FINAL_RL_VLA_TRAINING=DEFER / HIL=DEFER / ON_ORBIT_ASSEMBLY=FUTURE_EXTENSION_ONLY；**未发现更晚 Owner 决定覆盖**。
- **COMPETITION_SUBMISSION_SCOPE 缺席**：全仓 grep 零命中——无更晚比赛提交范围冻结包；09-01 前建议 Owner 签发（BLK 表配套）。

## 给综合裁决的输入

1. 比赛叙事 claim 上限 = 五锚点：sim_12 GS2/GS3（`a416c1348111`）、framework C13（`7d296e7a2437`）、sim_12 GS3.allowed[1]/forbidden[0]（`a416c1348111`）、synthesis §2+§5.4 分层链（`88118670c35d`）、C4 治理链（`3453adfe30e7`）；全部限定在冻结工况+PROVISIONAL 参数+FLEX=UNKNOWN 内。
2. P0-1：默认候选标题仓内零命中且与冻结 spine 一致，须 Owner 冻结签发；「具身智能/自主抓取/数字孪生/在轨装配」四词证据不足（`cce6517b4cd5` EMBODIED_AI 行、`7d296e7a2437` C21/C23-C29）。
3. P0-2：三份 claim-evidence 矩阵均停在 2026-08-04/旧 HEAD b75352c（`c6944e472039` L10），未吸收 08-23 查新红绿线；须 append-only 重冻结后方可作材料审校依据。
4. 红线六篇核验状态分层：Ma 全文已读、Wang/Lu/Mao/AA246 题录级、Cai 摘要级；Wang 96%/94% 数字未核验禁引用（`3be39f02c15a` §1/§2/§5）。
5. 「检索范围内未见」声明有效期 = 检索截止 2026-07-18 + 08-23 补检（`67ea28a65be4` §G）；2 名独立核查未闭环（同文 §F），赛后 P3。
6. ODR-60 口径以联合 Gate 为准：Option A 分支已记录、执行未授权（`55490805d934`），两份 08-27 裁决文本措辞不一致不回改、只在叙事层统一。
7. 继承包为部分 SUPERSEDED 的历史导航层：TRUTH_INDEX 内 CLAUDE.md/PROJECT_MAP.md 哈希已与当前失配（`e348749b9525` vs `d6cdd83a9775`/`4dcdad08bd74`），质量数字尾数差异以 L0 层级文件 `4.695555949342986 kg` 为准。
8. 负结果登记完整（e15 REPEAT、CTRL-01 REPEAT、WAVE1_REPEAT、sim_12 B/D ABORT、S3b 未入集、v1.0 G4 FAIL、E22 16/18 HOLD、e15core/e16 零安全候选、V9F 终局穿透），全部 IMMUTABLE，删除即审计事故。
9. 管理默认状态与 08-27 最新裁决一致，无更晚 Owner 覆盖；比赛演示链 COMPETITION_DEMO_READY 17/17 仅离线 DT2（`8b3cdbdaa09e`），引用须并置 command_emitted=false。
