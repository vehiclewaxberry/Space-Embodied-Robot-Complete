# Task Card CTRL-01 — 末端轨迹闭环控制最小基线（C0–C3）

- **task_id**: CTRL-01
- **scientific_question**: 帆板增广广义雅可比 J* 能否在保证末端轨迹精度的同时降低基座反冲（SQ2）？
- **hypothesis**: C1(J*) 相对 C0（固定基座雅可比）显著降低自由漂浮下的末端误差；C2 前馈进一步降基座扰动 ≥30%；C3 仅在任务零度>0 时有效。
- **baseline**: C0 = 固定基座 resolved-rate（可解释基线，禁"最先进控制器"）。
- **owned_paths**: 30_simulation/control_01_end_effector_tracking/（新建）、20_engineering/config/control_scene/（新建）
- **forbidden_paths**: sim_01–12 冻结区、sim_11 源码（只读 import）、10_research/（除自身报告）
- **input_evidence**: sim_11 generalized_jacobian 与 A1 summary J* 数值、sim_05 19.20° 锚、trajectory_control_research_plan.md（**先折入 R1 修订**）
- **minimal_implementation**: resolved-rate 骨架统一四法（仅 J_ctrl/前馈/零空间三项差异）；**R1 三处高严重度先修**：①T2 锚点改捕获前 3.0°/s；②A1 反作用约束改 (H_bb⁻¹H_bm) 角行（H_bm 参考点=基座原点）；③轮组占用按逐轴箱式包络重算（89.1% 口径）；C3 仅 approach_5d（nullity=1）任务启用，pose_6d 下机器拒绝；K_e/调参规则预注册后冻结。
- **experiment_matrix**: {C0,C1,C2,C3}×{T1 预抓取, T2 目标同步(修正锚), T3 紧急后退}，C3 只跑 5D 口径行；每格含帆板柔性相对指标（PROVISIONAL 标注）。
- **metrics**: 末端位置/姿态误差与 95 分位、基座姿态峰值与角速度积分、关节速度/加速度/力矩、奇异裕度、帆板 tip 与模态能（相对比较）、算时。
- **machine_gates**: GC1 九项（B 计划 + R1 修订版）：三退化锚逐位（19.199885629572467° 等）、守恒 ≤1e-12、C0/C1 分化机器证明（负结果照发）、C2 增量阈值、约束合规、误差有界闭环、哈希锁。
- **red_team_questions**: R1 报告全部 NEEDS_FIX 逐条 + "增益是否为四法分别调优造成不公平比较"。
- **stop_condition**: GC1 全过或负结果如实裁决 → control_01_gate_check.json 停；不进 control_02。
- **rollback_plan**: 新建目录整体回滚；sim_11 无任何改动。
- **claim_unlocked**: 四法在冻结场景集下的相对排序（限占位参数域，携带 PROVISIONAL）。
- **claim_forbidden**: 任何绝对精度指标外推；"适用于所有任务模式的零空间控制"；柔性绝对幅值结论。
