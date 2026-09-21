# Task Card CTRL-02 — 基座反冲抑制与捕获后姿态稳定（A0–A3 / B0–B3）

- **task_id**: CTRL-02
- **scientific_question**: 反作用规划、轮组协调与受限推力器协调后，能否显著降低作业段姿态扰动，并在冻结预算内完成捕获后消旋（SQ3）？
- **hypothesis**: A2（臂+轮协调）较 A0 降基座峰值 ≥50%；消旋结论与 sim_10/12 区域裁决一致（B_anchor 必 OUT_OF_FEASIBLE_REGION）。
- **baseline**: A0 无补偿（=sim_05 口径 19.20° 复现）。
- **owned_paths**: 30_simulation/control_02_base_attitude/（新建；**改名避 R1 指出的命名冲突**）、20_engineering/config/attitude_stab/（attitude_stab_v0.yaml，新参数全 PROVISIONAL）
- **forbidden_paths**: sim_01–12 冻结区、control_01 目录（只读其反冲历史输出）
- **input_evidence**: sim_05/08/12 锚（19.20°、36.5 g、12×、ω⁺=3.0633304945807067）、momentum_ledger.md 铁律、attitude_stabilization_research_plan.md（**先折入 R1 修订：轮组逐轴箱式容量、"29.7%→89.1%"翻正、增益预注册**）
- **minimal_implementation**: Phase A 反冲抑制 8 例（A0–A3）；Phase B 消旋 B0–B3 逐字复用 sim_12 四例；归属三标签（INTERNAL_REDISTRIBUTION/EXTERNAL_REMOVAL/MIXED）由账本数值机器判定。
- **experiment_matrix**: A{0..3}×2 臂机动 + B{0..3}×sim_12 四例；轮饱和按逐轴箱式包络判定。
- **metrics**: 基座姿态峰值、稳定时间、捕获后角速度、轮组逐轴占用与饱和时间、推力冲量/推进剂、末端轨迹劣化、帆板振动（相对）、稳定裕度。
- **machine_gates**: GC0 动量归属账本（PI 批准前禁写控制代码）+ GC1–C6（守恒 ≤1e-12、四锚逐位、推进剂≥动量下界、registry 哈希锁+thresholds_widened=False、FLEX 非判据、抑制/消旋分账出具）。
- **red_team_questions**: R1 全部 NEEDS_FIX + "箱式包络下 A2 是否仍达 ≥50% 假设"、"B 相与 sim_12 结论是否循环验证（须用独立积分路径复算）"。
- **stop_condition**: GC0–C6 裁决出具（含负结果）→ control_02_gate_check.json 停。
- **rollback_plan**: 新建目录整体回滚。
- **claim_unlocked**: 反冲抑制（内部）与消旋（外部）分账口径下的方案对比；轮组逐轴饱和边界。
- **claim_forbidden**: "轮组消旋了目标"；混称抑制为消旋；手改容量；绝对性能外推。
