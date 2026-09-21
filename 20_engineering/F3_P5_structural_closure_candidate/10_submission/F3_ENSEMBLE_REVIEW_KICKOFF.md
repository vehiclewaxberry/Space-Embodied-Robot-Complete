# F3 机械架构 · Ensemble 只读对抗复审启动指令
# 重启 OpenCode 后在新会话直接粘贴以下内容给主 Agent

你现在使用 Ensemble 对 F3 机械架构终态做**只读**对抗复审。禁止写入任何 `20_engineering/F3_P5_structural_closure_candidate/**` 文件，禁止调用 team_create / team_run（Agent Teams 主线已完成，不得重复执行 112 节点 DAG）。

## 前置事实（勿推翻）
- F3-P5A→P5E+终局已全部完成并冻结；终局裁决 `F3_MECHANICAL_ARCHITECTURE_AND_COMPETITION_PROTOTYPE_CLOSED_CONTROL_AND_EMBODIED_HANDOFF_READY_AL_HOLD`
- C 复核 9/9 PASS：`10_submission/F3_C_POST_CLOSURE_REVIEW.json`；基线哈希 46/46 无漂移；UL_FZ smoke 完整（12 工况 .frd 在 `04_fea/06_calculix_results`）
- HOLD 终态：01/02/03/05/07/08/09/10 CLOSED（07/08 为 CLOSED_COMPETITION）；04/06 OPEN_TBD_NO_AL_SOURCE

## 复审范围（只读）
读取工作区：`F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3_P5_structural_closure_candidate\`

启动 5 个只读评审 Agent，分别输出到 `40_evidence/` 下新目录（不得写工作区）：

1. **FEA 评审**：复核 12 工况 UL 判据、反力平衡、6×6 矩阵 cond=2.506e5 的条件数风险、模态为裸结构（B601 惯量未耦合）的声明是否一致。重点：`04_fea/`、`13_reports/F3_P5A_ACTUAL_FEA_EXECUTION_REPORT.md`、`04_fea/16_gate/F3_P5A_GATE_STATUS.json`
2. **机械接口评审**：G07/G08 接触垫、HDRM 演示件、T_SM=185.25mm Mode B 单轨、状态机 12 状态 3 互锁是否与 P5B/P5C 裁决一致。重点：`05_contact_pad/`、`06_hdrm/`、`06_configuration_closure/`、`07_configuration/`
3. **控制交接评审**：6×6 对角近似 + ROM 61.13/200.90/429.00 Hz + 接触模型 + 互锁是否带齐"模型等级声明"，是否可能被误用为耦合控制律。重点：`08_control_handoff/`
4. **具身交接评审**：观测 schema、动作屏蔽表、7 个负案例、smoke test 8/8 是否与状态机互锁一致、是否可防 NEG-01~07。重点：`09_embodied_handoff/`
5. **声明-证据一致性评审**：终局 JSON/P5A–P5E Gate JSON/交接包/HOLD 寄存器四者之间数字、状态、裁决文本是否逐字一致；特别核对任何可能被引申为"飞行合格/AL 通过"的表述必须保持 TBD/NOT_PERFORMED。重点：`10_submission/`、`11_change_control/`、`00_audit/F3_P5_HOLD_REGISTER.csv`

## 每个评审 Agent 的产出格式
- `PASS / NEEDS_CHANGES / HALLUCINATING` 三选一裁决
- 若 NEEDS_CHANGES：列出具体文件+行号+不一致内容+建议修复
- 若发现任何文件把竞赛级(G07/G08/HDRM 演示件)结论引申为飞行证据，或把 AL 裕度从 TBD 降级：直接判 NEEDS_CHANGES 并标 CRITICAL

## 汇总
5 份评审完成后，由主 Agent 汇总成 `40_evidence/F3_ENSEMBLE_ADVERSARIAL_REVIEW_SUMMARY.md`：
- 各维度裁决表
- CRITICAL 项清单（若有）
- 总体结论：`F3_ENSEMBLE_REVIEW_PASS` / `F3_ENSEMBLE_REVIEW_NEEDS_FIX`
- 若 NEEDS_FIX：修复项回到本会话走 ECR 流程（`11_change_control/F3_P5_CHANGE_CONTROL.md`），不得直接改冻结文件

## 禁止
- 禁止重启/重跑 P5A–P5E 任何计算
- 禁止修改工作区任何文件（评审输出只能写 `40_evidence/`）
- 禁止使用 Agent Teams / Swarm 的写工具
- 禁止把 HOLD-04/06 的 OPEN_TBD 改为 CLOSED（无 AL 源）
