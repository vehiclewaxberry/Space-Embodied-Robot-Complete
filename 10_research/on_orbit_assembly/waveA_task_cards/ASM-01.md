# Task Card ASM-01 — 装配接触动力学（详细计划=contact_flexible_dynamics_plan.md）

- **task_id**: ASM-01 | **scientific_question**: 接触带宽与柔顺参数如何决定
  插接载荷、基座反应与帆板振动（RQ2），各相位需要何种保真度（RQ3）？
- **hypothesis**: L1 KV+状态机在 k_n∈[1e4,1e6] 内与 L2 抽查一致（5% 口径）；
  持续接触≠捕获单脉冲，需显式状态机。
- **baseline**: L0 几何+冲量（继承 sim_10/12 口径，禁报模态能）。
- **owned_paths**: 30_simulation/asm_01_contact_dynamics/
- **forbidden_paths**: 冻结区、他人 ASM 目录、sim_11 源（只读 import）
- **input_evidence**: contact_window 基建清单、Whitney 卡滞基元、SSOT v0/v1、
  **结构性缺口登记：sim_11 帆板在追踪星侧而 SSOT 要求目标星带帆板**。
- **minimal_implementation**: L1 单边 KV+六态接触状态机 → 卡滞判据
  （楔紧 l/d<μ、平行四边形、动力学停滞三条件）→ k_n×ζ_c×μ×v_ins×失准
  扫掠 → L2 抽查 8 例（e15 5% 口径；GR5 未闭环期间禁称已认证）。
- **experiment_matrix**: 5×4×μ×v×失准对数格；传染路径 P1–P6 标度校验。
- **metrics**: M1–M11（峰值力/冲量/深度/卡滞/基座/轮组/tip/模态能/残余/守恒/数值健康）。
- **machine_gates**: AG2（记账闭合/单边性/收敛链/跨解算器/L0 极限回归）+
  AG4（三级一致/未注册态→UNKNOWN_CONTACT_STATE/未收敛禁判成功/八项完备）。
  **Phase A verdict 上限 = `ASM01_SCREENING_ONLY`**（目标侧 FFR 未建）。
- **red_team_questions**: 状态机遗漏态；m_app Delassus 定义的正确性；
  k_n=1e6 触发 R2b 时的升级路径。
- **stop_condition**: AG2/AG4 裁决出具 → 停（预登记负结果照发）。
- **rollback_plan**: 新目录整体回滚。
- **claim_unlocked**: 冻结场景下接触参数-响应映射（SCREENING 限定）。
- **claim_forbidden**: 装配成功裁决（Phase B 前）；未收敛接触的任何结论。

## 红队修订（LOOP-1 开工前折入）
- 接触状态机补倒角穿越态（否则 AG4-3 零容忍下全 run UNKNOWN）+ 卡滞双子态：
  ENGAGED/卡滞→冻结保持，PREENGAGE→预授权守卫式回退原语（解 BACKOFF 盲退冲突）；
- 装配成功八判据由本模块**单源求值**（解 AG3-b FATAL）；补第九判据=接触历史合规、
  判据4 补 geometry_consistent（防假 LOCKED）、判据8 补 run 级相位裁决账本；
- S3 目标残速超 ASM-01 认证域必须触发 UNKNOWN。
