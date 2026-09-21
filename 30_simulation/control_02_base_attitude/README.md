# CTRL-02 — 基座反冲抑制与捕获后动量级终端可行性（CTRL-02-R 整改轮）

本模块只在冻结 `sim_01–12` 证据链之上新增控制层比较，不修改既有物理工件。
本轮为 Wave1 预注册整改（R-4/R-5，注册见
`10_research/partner_requirement_closure/wave1_repeat/repeat_preregistration.md`），
**全部阈值冻结不变**（逐轴 |H_i|≤0.1 N·m·s、0.05 rad 裕度、端点恒等 1e-6、
守恒/归属 1e-12 等照旧）。

- Stage A（R-4 轨迹重设计，预注册修订）：
  - M1 保持不变，作为 sim_05 动力学锚（q2 越飞行限位，`flight_trajectory:
    false`，不入飞行裕度门，不支持飞行有效主张）。
  - M2 预注册内点起点 `[0, -15, -15, 0, 0, 0]°`（先验选点规则：每关节距活动
    限位 ≥0.25 rad，>5× 冻结 0.05 rad 门；min-jerk 逐关节单调 ⇒ 全程裕度 =
    端点最小值）。**已撤回的看结果后 −5° 探针未复用**。
  - A1 重设计为两段式任务有效轨迹：`[0, 4.8 s]` 反作用投影段 + 匹配关节速率的
    五次多项式收口段，t=8 s 精确落在注册关节终点（端点恒等按构造成立）。
    A1 不是无反作用轨迹（收口段偿还基座反作用）；投影段反作用残差 ~1e-16。
    诚实负结果：M2 上 A1 峰值 9.24° 略高于 A0 的 8.73°（收口偿还超过投影
    节省）；M1 上 A1 18.84° 略低于 A0 19.20°。A2 两机动峰值均降为数值零，
    轮箱占用 80.2% / 45.6%。
- Stage B L0 层不变：逐字读取 sim_12 四工况，独立刚化路径复算，B0–B3 动量级
  终端可行性；L0 行仍标 `stability_status=NOT_EVALUATED_NO_ACTUATOR_DYNAMICS`。
- Stage B 瞬态层（R-5 新增）：在 `20_engineering/config/attitude_stab/attitude_stab_v0.yaml`
  冻结 **PROVISIONAL** 执行器参数（轮最大力矩 0.01 N·m/轴、推力器最小脉宽
  20 ms、时间窗判据 300 s 窗/60 s 保持/0.05 °/s，均带出处级注释），按脉冲对齐
  定网格执行 L0 动量计划：16 行全部产出
  `STABILIZED/NOT_STABILIZED_WITHIN_WINDOW` 裁决（7 稳 / 9 不稳；B_anchor 两行
  为域外反事实）。脉冲量子 F·t·L = 3.4e-4 N·m·s 给出末端残差下界，终端与 L0
  计划一致性按量子界机器判定；代数预测与时间推进逐行一致。该层
  `model_fidelity=PROVISIONAL_L1_MOMENTUM_ACTUATOR`，不支持硬件有效或闭环
  控制性能主张；硬件参数冻结后必须重跑。
- 轮组物理容量只按每轴 ±0.1 N·m·s 箱式包络裁决；0.3 N·m·s 仅保留为历史标量
  对拍。机械臂与轮组均不能移除系统总角动量；只有推力器外部角冲量可移除。
- A3 仍为 `NOT_APPLICABLE_WITH_MISSING_FROZEN_ACTUATOR_DYNAMICS`：R-5 的
  PROVISIONAL 值只授权给 Stage-B 瞬态层，不解锁 A3。
- FLEX 始终为 `UNKNOWN_NOT_IN_CRITERIA`。

复现：

```powershell
python 30_simulation/control_02_base_attitude/tests/run_all.py
python 30_simulation/control_02_base_attitude/src/run_gates.py
python 30_simulation/control_02_base_attitude/src/freeze_evidence.py --source-commit <HEAD>
```

科学裁决只认 `results/control_02_gate_check.json`（schema `control02-gate-v3`，
GC0–GC7）。本轮机器裁决 `PASS`（八门全过，tests 24/24），但独立红队复审未完成，
`review_status` 保持 `PENDING_REVIEW`；不合并、不进集成，等 integrator-R 单跑
与 PI 终裁。
