# GC0 动量归属账本（批准口径机器化）

## 口径

所有角动量均按同一惯性系、系统质心口径记账。内部件运动可以改变各部件之间的动量
分配和基座姿态历史，但不能改变系统总角动量。轮组只是有限容量的内部存储器；只有
推力器产生的外部角冲量可以改变系统总角动量。

机器标签只有四种：

| 数值条件 | 机器标签 |
|---|---|
| 外部角冲量≈0、轮存储≈0 | `INTERNAL_REDISTRIBUTION` |
| 外部角冲量≈0、轮存储非零 | `MOMENTUM_STORAGE` |
| 外部角冲量非零、轮存储≈0 | `EXTERNAL_MOMENTUM_REMOVAL` |
| 外部角冲量非零、轮存储非零 | `MIXED` |

判别容差固定为 `1e-12 N·m·s`，与守恒 Gate 同源。B0 无动作基线是上述闭集中的
零作用子集，另以 `control_action=NONE` 区分。

守恒证据按量纲分门记录：捕获刚化的 `eps_H/eps_P` 为无量纲相对残差，外部角动量
账本闭合差为 N·m·s。GC0 分别保存各自阈值和单位，不再把二者混成一个最大值。

## 控制器预登记

| 控制器 | 外部角冲量 | 轮存储 | 预期机器标签 | 边界 |
|---|---:|---:|---|---|
| A0 无补偿 | 0 | 0 | `INTERNAL_REDISTRIBUTION` | 臂运动引起内部反冲 |
| A1 反作用轨迹 | 0 | 0 | `INTERNAL_REDISTRIBUTION` | 直接约束 `(Hbb^-1 Hbm)` 角行；不得称移除动量 |
| A2 臂+轮协调 | 0 | 非零 | `MOMENTUM_STORAGE` | 每轴 ±0.1 N·m·s 箱式容量 |
| A3 臂+轮+推 | 未冻结 | 未冻结 | 不评估 | 缺轮力矩与最小脉宽冻结输入 |
| B0 无控制 | 0 | 0 | `INTERNAL_REDISTRIBUTION` | `control_action=NONE` |
| B1 轮暂存 | 0 | 非零 | `MOMENTUM_STORAGE` | 不得称轮组消旋总系统 |
| B2 推力器 | 非零 | 0 | `EXTERNAL_MOMENTUM_REMOVAL` | 推进剂必须等于或高于动量下界 |
| B3 轮+推协调 | 非零 | 非零 | `MIXED` | 内外两行分账 |

Stage B 的所有 B0–B3 L0 行只评估
`MOMENTUM_LEVEL_TERMINAL_FEASIBILITY`，并明确写入
`stability_status=NOT_EVALUATED_NO_ACTUATOR_DYNAMICS`。这些行不能用于闭环稳定性或
瞬态收敛主张。

## 瞬态层（CTRL-02-R R-5 新增）

`B_TRANSIENT` 行是同一 L0 动量计划经 PROVISIONAL 执行器动态
（轮最大力矩 0.01 N·m/轴、最小推力脉宽 20 ms）的定网格执行，归属仍由
`classify_attribution` 按数值账本机器判定，四标签词汇与 1e-12 容差完全不变；
外部角冲量取实际发射的整脉冲量子和（方向为 L0 外移方向），轮存储取瞬态终值。
瞬态行标 `stability_status=EVALUATED_TIME_WINDOW_PROVISIONAL_ACTUATORS`、
`model_fidelity=PROVISIONAL_L1_MOMENTUM_ACTUATOR`、`hardware_valid=false`，
只支持时间窗判据下的 STABILIZED/NOT_STABILIZED 结论，不支持硬件有效或闭环
控制主张。终端状态与 L0 计划的差按脉冲量子界（3.4e-4 N·m·s）机器判定
（GC7），瞬态推进剂走与 GC4 相同的独立下界审计路径。

## A3 范围冲突裁决

旧 Task Card 标题写 A0–A3，但 Wave 1 专家批准的正式 Stage A 比较集为 A0/A1/A2。
冻结 sim_08 与 registry 没有轮组力矩和推力器最小脉宽，无法定义 A3 的动态分配器。
因此 A3 记录为
`NOT_APPLICABLE_WITH_MISSING_FROZEN_ACTUATOR_DYNAMICS`，不算已验证，也不因缺参伪造
PASS；A3 性能主张继续禁止。

机器账本见 `../results/gc0_momentum_ledger.json`。
