# 13 标题与声称上限（TITLE_AND_CLAIM_CEILING）

- 生成日期：2026-08-27；生成者：综合代理 SYN-C。依据：memory fragment §1/§3/§4、embodied fragment §0/§6、查新裁决（`01_project/competition/文献查新裁决_claim边界_20260823.md`，sha256 `3be39f02c15a`）。

## 1. 推荐标题

**「面向翻滚非合作目标的自由漂浮空间服务航天器：基于 Binding-Gate 的物理约束抓捕策略选择与失效闭合安全验证」**

- 状态：**PENDING_OWNER_SIGNOFF**。仓内业务文档 grep 零命中（2026-08-27 复核：唯一命中为本审计 fragments，即该标题未在任何现行文档中出现），且未获 Owner 冻结（BLK-MEM-01，P0）。Owner 签收前一切材料不得使用该标题定稿。
- 一致性依据：与 Paper 1 冻结 EN 题方向一致（`10_research/contribution_map/paper1_contribution_map.md` 第 5 行「Strategy Selection under Momentum and Stability Constraints … Binding-Gate Criterion」，`3453adfe30e7`）；覆盖查新绿线五项（`3be39f02c15a` §3）；避开全部红线词与四个证据不足词（见 §2）。

## 2. 四个候选词的证据充分性逐词评估（结论：均不足，给收缩建议）

| 词 | 证据结论 | 证据指针 | 收缩建议 |
|---|---|---|---|
| 具身智能 | **不足**：EMBODIED_AI=PLANNING LAYER ONLY（`10_research/research_questions/PROJECT_CURRENT_STATUS.md`，`cce6517b4cd5`）；VLA=PROTOCOL_DRAFT（`10_research/vla/vla_generalization_plan.md` 第 3 行，`169cb1f05b33`）；Physics Tool=DRAFT_NOT_IMPLEMENTED（`10_research/vla/tool_contract_draft.yaml` 第 8 行，`b8f130d578b2`）；framework C23/C24 均 NOT_EVALUATED（`7d296e7a2437`）；Ma 2026 红线（视觉+RL 自主抓取全文已读，`3be39f02c15a` §1）。**架构贡献在合同级成立**（`space_embodied_agent_v1_contract.md` §1.1/§2/§3，`3d949b26caf8`；五 schema PROTOTYPE_CONTRACT；四条禁止主张已机器登记于 `prototype_acceptance.yaml`，`8214139674a9`） | 见左 | 不作主标题贡献词；仅在「系统设计/路线图」节以合同级架构表述出现，并带「设计创新点，不是已验证系统能力」限定 |
| 自主抓取 | **不足**：framework C25 H0_H3_NOT_STARTED；感知前端/估计器不存在（`sim13_bootstrap.json` `observation_mode=state_based`，`4624c5ba2a01`；`observation.py` 第 24-60 行真值直读，`fafb189460bf`）；查新红线禁视觉+RL 自主抓取口径 | 见左 | 改为决策层措辞「物理约束抓捕策略选择」；任何「自主」字样只用于未来工作节 |
| 数字孪生 | **不足**：上限 DT2_SCOPE_LIMITED_OFFLINE_REPLAY（`10_research/framework_convergence/numerical_twin_status.md` 第 5/24-26 行，`bf783ca9dd8b`；`digital_twin_plan.md` 第 7-13 行，`64e88a4db0c6`）；DT3/DT4=BLOCKED；回放早于 sim_10-12/SAFE/CTRL 当前状态 | 见左 | 只称「确定性离线 DT2 证据回放」，并置 `command_emitted=false`（`competition_gate_check.json`，`8b3cdbdaa09e`） |
| 在轨装配 | **不足**：Wave A `PLANNED_NOT_AUTHORIZED`（`10_research/research_state_v4.md` 第 14-16 行，`1bd051d86368`）；framework C26-C29 全 NOT_EVALUATED；master_plan 最终裁决 READY_WITH_INTERFACE_BLOCKERS（`dea2436daa5e`）；比赛链已声明不依赖 Wave A（`项目现状总览_20260720.md` 第 13 行，`184cacb060fc`） | 见左 | 不进主叙事/标题；仅路线图节一行提及并带 PLANNED_NOT_AUTHORIZED |

## 3. 叙事五问（Why / What / How / Evidence / Boundary）

- **Why（为什么做）**：翻滚非合作目标抓捕的失败代价集中在「抓捕后才暴露的不可稳定/不可消旋」；需要在抓捕决策点之前用物理可行域筛掉不可行候选。锚：150 kg 碎片捕获后 3.0633°/s 超速率门（sim_06 CSV 第 15 行，`8cbad84b8ff6`）；消旋需 |H_c|=3.65099 N·m·s = 12× 轮组容量（sim_08 CSV `target_debris_v0,3.0` 行，`1f0d45349565`）。
- **What（做了什么）**：一个基于真实机械与动力学边界、能够对非合作目标抓捕候选给出 EXECUTE、MODIFY 或 ABORT 裁决的物理约束数字验证系统（见 §4 作品定义）。
- **How（怎么做）**：9002 点四门 fail-closed 可行域扫描（sim_10 `$.verdict=SIM10_GATES_PASS`，`4dbd8c91ff34`）+ binding-gate 策略选择 16 例证明集（sim_12 `$.gates.GS2`，`a416c1348111`）+ fail-closed 运行时安全核（SAFE-00 47/47，unknown_allow=0，`ff56929dd835`）+ 分层架构合同（候选→物理评价→SAFE→控制，`88118670c35d` §2/§5.4）。
- **Evidence（证据是什么）**：五锚点全部机器可核（见 `09_COMPETITION_DECISION_MEMO.md` Q2）；离线三场景确定性重放 17/17（A_low=EXECUTE/B_anchor=ABORT/C_transition=MODIFY，`8b3cdbdaa09e`）；耦合重认证 E23 18/18（HF→ROM 0.2714%、交叉求解 1.81e-05，`1ad4993fd9df`，带 PENDING_OWNER_REVIEW）。
- **Boundary（边界是什么）**：离线、确定性重放、受限任务包络；`command_emitted=false`、`real_time_synchronization=false`；Sim13 最高 ABORT_ONLY；CTRL-02 仅 R5 PROVISIONAL 执行器模型下 7/16；帆板模态与 T_c=20 ms 为占位（PROVISIONAL）；无硬件/实时/HIL 证据；正式双 Release=HOLD。

## 4. 作品定义（对外表述的唯一合法形态）

> 本作品是**基于真实机械与动力学边界、能够对非合作目标抓捕候选给出 EXECUTE、MODIFY 或 ABORT 裁决的物理约束数字验证系统**。

禁止表述形态（违反即越界 claim）：
- 不得表述为「已实现的 VLA 自主抓取系统」（VLA=PROTOCOL_DRAFT，无训练/采数/评测）；
- 不得表述为「在轨碎片清除系统/装备」（无实物、无飞行验证、装配主线未授权）；
- 不得表述为「实时数字孪生/HIL 验证平台」（DT2 上限、HIL NOT_STARTED）；
- 不得暗示任何 formal release 或 next_stage_authorized=true（全仓现行 Gate 均为 false）。
