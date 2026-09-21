# MuJoCo V1 控制重放语义

本目录说明 `R2_MUJOCO_FREE_FLOATING_PRECONTACT_CROSS_SOLVER_DIAGNOSTIC_V1` 的控制输入合同。它是 CURRENT R2 捕获前短时域反馈的独立 MuJoCo 重放，不是新控制器设计、硬件控制验证、目标相对轨迹闭环或飞行稳定性证明。运行结果只认 `../results/R2_MUJOCO_FREE_FLOATING_PRECONTACT_GATE_V1.json`。

## 四个物理运行

```text
C0_UNCONTROLLED_5D_REFERENCE
C1_CONTROLLED_5D
C0_UNCONTROLLED_6D_REFERENCE
C2_CONTROLLED_6D
```

每组时窗均为 12 ms。5D 受控线只与 5D 无控线比较，6D 受控线只与 6D 无控线比较；不得跨任务维数或跨单位比较。应继承现行合同中的相同初始状态、`spacecraft_bus` 根坐标系、`gripper_link` 工具点、参考 twist、characteristic length/权重、`Kv` 和反馈广义力构造。

任务量是瞬时 `spacecraft_bus` 根坐标系中的工具 twist/velocity error，不是惯性系位置、姿态或轨迹误差。5D 与 6D 的加权度量沿用现行单位安全合同；任何移除任务权重的变体只能作为负控。

## 执行器与反馈

- 6R 使用 gear=1 的 MuJoCo direct-drive torque `motor`，不使用 position servo 代替力矩输入。
- `tauP=0`；2P 是否锁定由 lane 拓扑或 equality 决定，不能由零控制力假定。
- `LOCKED_2P_REDUCED_6R` 是控制重放主 lane：2P 坐标被移除并固定于 `qP*=[0.03575,0.03575] m`。
- `LOCKED_2P_EQUALITY_6R2P` 只用于 `MUJOCO_SOFT_EQUALITY_LOCK_DIAGNOSTIC`；其约束反力、漂移和约束功不能冒充精确 KKT。
- `FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL` 必须保留 2P 自由响应，用于证明 `tauP=0` 不等于锁止。

MuJoCo RK4 每个积分子步都应根据实时状态重新计算控制量；仅在每个宏步计算一次并保持不变不满足本合同。V1 不允许为抑制漂移添加根节点阻尼、虚拟弹簧、人工姿态控制或外力。

## 必须记录的诊断

每个场景至少记录：

- 6R/2P 状态、自由基座位置、四元数与 twist；
- 加权任务误差的初值、终值、RMS 与同维受控/无控比；
- 回调次数与 RK4 子步重算证据；
- timestep、接触数量及确定性回放哈希；
- 与当前 DOP853 参考的 6R 终态和任务误差交叉；
- 独立逐 link 计算的 `P`、固定惯性原点 `H_O`、`T` 与 `∫tau_R^T qdot_R dt`。

`P`、`H_O` 与能量必须分别以 SI 单位审计；禁止使用混合量纲范数。MuJoCo 内置子树质心角动量只能作为辅助，不得替代固定惯性原点角动量账本。

## 权限边界

即使四组运行均满足本包阈值，也只可能支持“MuJoCo 捕获前跨求解器控制诊断”这一局部主张。它不验证电机、驱动器、轮组、饱和、速率、带宽、延迟、热、故障、柔性、碰撞、接触、目标附着、SAFE、Sim13、非 ABORT、下一阶段或发布。所有相关权限字段必须保持 `false`。

