# Task Card ASM-02 — 分阶段装配控制（详细计划=phased_control_plan.md）

- **task_id**: ASM-02 | **scientific_question**: 5D 接近→柔顺接触→短程 6D 锁紧
  是否优于全程 6D 跟踪（RQ1）？
- **hypothesis**: AC1/AC2 失败率 ≤ AC0 且接触载荷/基座扰动改善；反向结果
  如实发布（预注册承诺）。
- **baseline**: AC0 全程 6D 几何跟踪（共用 QP 骨架，差异仅相位表/阻抗/轮组通道）。
- **owned_paths**: 30_simulation/asm_02_phased_control/、20_engineering/config/assembly_control/
- **forbidden_paths**: 冻结区、Wave1 模块（CTRL-01/02 只读）、他人 ASM 目录
- **input_evidence**: CTRL-01 七负结果（引用带"冻结增益与预注册轨迹下"）、
  J*、CTRL-02 分账、**W1-R12 裁定：轮力矩统一 0.01 N·m/轴**（0.033 不得升格；
  统一限下 Stage-A A2 重评，不回改 CTRL-02 冻结工件）——**开工前置（AR2）**。
- **minimal_implementation**: 约束 QP（w_e‖J*q̇−ẋ_d‖²+w_b‖H_bm q̇‖²+w_f Ê_flex
  +w_u‖u_a‖²；九类硬约束）；相位语义 P0 position_3d→P1 approach_5d(nullity=1)
  →P2 切向位置+法向阻抗→P3 短程 pose_6d（合法条件=短程+低速+SAFE-00 预授权）；
  切换判据预注册（coarse 5mm/5°→接触，12mm+0.1mm/0.5°→LOCK）；
  瞬态六条（C¹ 收口、阻抗斜坡 T_blend≥2T_c、切换=重裁决、账本跨切换连续、抖振检测）。
- **experiment_matrix**: {AC0..AC3}×装配场景格（初始失准×接触参数抽样）；
  权重四基线共用、哈希锁、禁按场景调参。
- **metrics**: 装配成功八判据 + 接触载荷 + 基座/轮组 + 帆板相对指标 + 算时。
- **machine_gates**: AG1（相位维度机器校验/切换可达性/裕度）+ AG3
  （失败率比较/6D 段零空间双层禁令/成功=几何∧力学∧资源/UNKNOWN 不判 success）。
- **red_team_questions**: RF-1 解前"捕获域吸收跟踪误差"（AR4）是否成立；
  QP 不可行时的降级语义；与 ASM-01 接触模型的冻结时序。
- **stop_condition**: AG1/AG3 裁决出具 → 停。
- **rollback_plan**: 新目录整体回滚。
- **claim_unlocked**: 分阶段方法在冻结场景集的相对表现（PROVISIONAL 限定全程携带）。
- **claim_forbidden**: 阶段切换普遍优越；自主在轨组装完成；CTRL-01 结论外推。

## 红队修订（LOOP-1 开工前折入）
- **AG3-b FATAL 修复**：success 只从 ASM-01 单源函数取值（本模块禁自行合取）；
  AG3-a 改名 control_failure_rate 与 success 语义解耦；Phase A 只报
  SCREENING 口径 headline，禁 success 字样；
- AR4 前提修正：5mm/5° 捕获域在 RF-1 解除前不得作为吸收跟踪误差的论据
  （CTRL-01 违例 0.19 m = 38×5 mm——接近段臂端误差证据链须先补）；
- QP 公平性：weights_tuned_on_scenarios 旗标 + AC0 公平参考构造规则 +
  字面量扫描可执行化；AC3 补失败率门；n=4 等号空过封堵；
- W1-R12 重评=理想分配事后饱和口径，重评**不关闭** W1-R12。
