# Task Card ASM-00 — 装配接口 SSOT 转正（详细计划=interface_mechanics_plan.md）

- **task_id**: ASM-00 | **scientific_question**: 预制接口的公差链能否形成自洽的
  粗→精→锁三级捕获域并全程有出处？
- **hypothesis**: 锥-销-锁参数经 T1–T3 公差链推导后自洽；现 v0 草案存在
  RF-1（锥面聚拢 2.14mm < 粗公差 5mm）等三面红旗须先解。
- **baseline**: interface_ssot_draft.yaml v0（全 PROVISIONAL/LITERATURE）
- **owned_paths**: 30_simulation/asm_00_interface_preflight/、20_engineering/config/assembly/
- **forbidden_paths**: 全部冻结区、Wave1 模块、他人 ASM 目录
- **input_evidence**: L1–L13 引文候选、M1–M5 实测方案、RF-1/2/3 红旗登记
- **minimal_implementation**: T1 锥面捕获域解析（补锥口/喉半径字段解 RF-1）→
  T2 销孔精对准域（定 clearance 语义解 RF-3）→ T3 锁紧载荷路径；
  sympy 推导 vs 独立 Monte Carlo 碰撞采样对拍；1U/2U 经 attach_target 原语
  接入 sim_11（LOCK 质量转移事件 + 动量账本审计 + 四级退化链）。
- **experiment_matrix**: 公差链参数格 × 两模块档；RF-2 楔紧边界 μ 扫掠。
- **metrics**: 捕获域体积、公差链闭合裕度、对拍偏差、退化链锚点差。
- **machine_gates**: AG0 五组断言（单位/右手系/出处/碰撞几何/哈希）；
  UNKNOWN 不转正；RF 红旗全解否则 verdict 带 `_WITH_INTERFACE_BLOCKERS`。
- **red_team_questions**: RF-1 解法是否改几何而非改公差（禁为自洽而放宽公差）；
  引文键落实率；CDS Rev13 vs Rev14.1 取版决策记录。
- **stop_condition**: AG0 裁决出具（ssot v1 或 BLOCKED 清单）→ 停。
- **rollback_plan**: 新目录整体回滚；v0 草案不动。
- **claim_unlocked**: 接口公差链自洽性（限所引出处等级）。
- **claim_forbidden**: "接口参数已验证"（无 MEASURED 字段前）；任何实物互操作声明。

## 红队修订（LOOP-1 开工前折入，出处=red_team_assembly_control.md / red_team_assembly_safety.md）
- SSOT 补字段：锥口/喉半径（RF-1）、销距 s、倒角 w_ch、clearance 语义定案（直径口径，含 c_eff≈c_abs/s 缩放）；
- 两点接触角公式与 Whitney 归一化在 ASM-00/01 间统一（现差因子 2）；
- 深锥选项单独不解 RF-2，须与 μ 下调/表面处理组合论证；
- CDS 取版（Rev13 vs 14.1）决策记录入卡。
