# R5 单位安全动量报告

Run6 对三个 S02 case 各执行 `4/2/1 ms` 三点细化，P/H 分账、能量、基座角/线速度投影的数值诊断全部通过；最细步长的 `epsilon_P` 范围为 `9.344e-16`–`2.153e-14`，`epsilon_H` 范围为 `4.426e-15`–`2.125e-14`。Run5/Run6 的 S02 摘要逐字节一致，Runner 生命周期与 verdict 修复未改变动力学结果。

主账本固定为 `P^I [kg·m/s]` 与 `H_O^I [N·m·s]`，O 为固定惯性原点；外部 wrench 为模型范围内显式零，事件监测 VERIFIED 且事件数 0。逐动态体的 P、H_spin、H_orbital 已写入 episode 时序并以 `math.fsum` 分量求和，再与 plant 空间动量对拍。旧 `rel_h_drift_max` 保留为 R4/Run3 历史，但状态为 `DEPRECATED_UNIT_INVALID_FOR_GATE`。

R5 的相对尺度是运行前由冻结 plant、初态和持续时间计算的工程诊断尺度，不是飞行要求。仓库查无适用于本 plant/场景/求解器的 `P_abs_max [kg·m/s]` 与 `H_abs_max [N·m·s]` 权威合同，因此正式 P/H Gate 均为 `HOLD_THRESHOLD_AUTHORITY_MISSING`。本报告只支持 `R5_LEDGER_NUMERICALLY_VERIFIED`，不产生控制或接触发布信用。
