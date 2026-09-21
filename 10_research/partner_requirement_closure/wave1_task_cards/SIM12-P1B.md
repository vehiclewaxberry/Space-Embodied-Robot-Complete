# Task Card SIM12-P1B — 策略支配性靶向审计（8–12 例，条件触发）

- **task_id**: SIM12-P1B
- **scientific_question**: S2（速度匹配）与 S4（外部消旋）在冻结预算下是否存在真实最优区，还是被支配策略？
- **hypothesis**: S4 在 H∈(0.6, 5.47] ∧ ω⁺≤2°/s 解析带内有胜区（现为 ANALYTIC_NOT_CASE_PROVEN）；S2 在冻结刚体判据下疑似被支配（若证实，如实判定并写入论文弱式表述的证据注）。
- **baseline**: sim_12 Phase1 16 例（冻结，不重做）；本任务只增例不改口径。
- **owned_paths**: 30_simulation/sim_12_strategy_feasibility/results/（新增 p1b_* 工件）、src/（新增 p1b 驱动，不改 strategy_eval.py 既有函数签名）
- **forbidden_paths**: Phase1 既有工件与 gate JSON（只读）；sim_10 冻结区
- **input_evidence**: strategy_results.csv、sim12_status_and_next_gate.md（F 验收：弱式 GS2 发现）、S4 解析带推导、S3a θ 扫掠路径
- **minimal_implementation**: 在三条边界（冲量受限/动量容量/推力资源）附近自适应选 8–12 例（二分逼近边界格），四策略评估 + S3a θ∈[0..60°] 敏感性列；复用 Phase1 全部机器断言。
- **experiment_matrix**: S4 解析带内 3–4 例 + S2 潜在优势构造例（结构门主导工况）2–3 例 + 过渡带补充 3–4 例 + θ 扫掠。
- **metrics**: 每例 best_strategy、支配关系矩阵、S4 带内胜率、S2 胜例存在性、θ 退化曲线 vs 2h_max·cosθ 解析。
- **machine_gates**: GP1 守恒与锚点断言继承 Phase1；GP2 支配性裁决（每策略 DOMINANT_REGION_PROVEN / DOMINATED_UNDER_FROZEN_BUDGET / UNRESOLVED 三选一，机器判定）；GP3 主张审计更新（强式表述解锁条件=GP2 出 PROVEN）。
- **red_team_questions**: "构造例是否为 S2 量身定制而失公平"（须预注册选例规则）；"θ 扫掠是否与解析式循环验证"（用独立 rigidize 路径）。
- **stop_condition**: GP1–3 裁决出具 → p1b_gate_check.json 停；无论结果如何不再加例。
- **rollback_plan**: p1b_* 工件独立命名，删除即回滚；Phase1 裁决不受影响。
- **claim_unlocked**: 若 GP2=PROVEN：四策略最优区图（Fig.6 升级）；若 DOMINATED：如实的被支配判定（同样是论文结果）。
- **claim_forbidden**: 在 GP2 出具前使用"四策略分别占据明确最优区"强式表述。
