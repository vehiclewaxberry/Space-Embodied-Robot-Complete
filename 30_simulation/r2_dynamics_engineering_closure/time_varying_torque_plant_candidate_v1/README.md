# Current-R2 时变广义力矩/力刚体 plant 候选 V1

## 裁决边界

本包只交付一个 hash-bound、零总动量、刚体、8-DOF 的设计诊断候选。它不是接触/抓取/抓后组合体模型，不包含 Solar R2 柔性、目标刚体、执行器硬件动态或控制器，也不改变 parent Dynamics Engineering Gate、Sim13、机械发布或下一阶段授权。

最大允许主张固定为：

```text
R2_TIME_VARYING_TORQUE_DRIVEN_ZERO_MOMENTUM_RIGID_PLANT_CANDIDATE_PASS__ARBITRARY_DESIGN_EFFORT_ONLY__NO_FLEX_CONTACT_TARGET_ATTACHMENT_HARDWARE_CONTROL_PARENT_OR_RELEASE_CREDIT
```

所有 `flex/contact/target_attachment/hardware/control/parent/release/next` 权限字段必须保持 `false`。输入广义力是任意数值激励，不是 B601 实测力矩/力包络。

## 模型与状态

底层只复用当前 Unified R2 URDF、`UnifiedR2DynamicsBackend` 和 parent `ReducedR2Model`，并逐文件校验 19 个源 pin。除原 12 项外，实际导入轨迹识别出的 7 个项目内 transitive 模块（`sim13_v2` package init、authority resolver、contracts、env、system model，以及 backend package init、canonical）也全部按 bytes/SHA256 冻结；不允许未 pin 的项目内运行时模块。Unified R2 为 19 link、18 joint、16 个有惯性 link、3 个 frame-only link、8 个可动坐标，总质量严格为 `31.022864807342987 kg`。

积分物理状态严格为 23 个标量：

```text
x = [r_I(3), Q_BI,wxyz(4), q_R(6), q_P(2), dq_R(6), dq_P(2)]
```

六维基座 twist 不是独立动量状态，而由零总动量机械连接逐时重构：

```text
V_B = -H_bb(q)^(-1) H_bm(q) dq
```

代码只使用线性求解，不显式构造逆矩阵。四元数采用 body-to-inertial、wxyz 约定。内部另积分一个无物理状态信用的功账本 `Wdot = tau^T dq`。

降阶动力学为：

```text
Mbar(q) ddq + h(q,dq) = tau(t)
Mbar = H_mm - H_mb H_bb^(-1) H_bm
tau_i(t) = amplitude_i sin²(pi t / T)
```

主证据网格使用固定步长 RK4（0.25 ms），并以 SciPy DOP853 独立对拍。两个 lane 分别是 `ACTUATED_8DOF` 与 `LOCKED_2P_6R_PULSE`。后者把两夹指固定在 `0.03575 m`，以 KKT、坐标消元、约束反力与零反力功交叉验证；反力不是接触力。

## 关键防伪

backend 自带 `initial_state()` 不能直接执行：当前它至少违反 `joint3` 上限，并把 `gripper_joint2` 置为 `-0.004 m`，低于 URDF 下限 `0 m`。本包显式拒绝该默认状态并使用合同内合法状态。

转动坐标与平移坐标的单位始终分开：前六维为 rad/rad·s⁻¹/N·m，后两维为 m/m·s⁻¹/N。不得对原始混合单位矩阵的特征值或条件数授予 Gate 信用。参考尺度变换只用于验证方程、加速度、能量和功率在坐标缩放下不变。

动量由两条独立路径逐采样计算：

- 逐有惯性刚体在惯性系求和得到 `P_I` 与关于惯性原点的 `H_O,I`；
- 完整广义质量矩阵先得到 root-frame 动量，再旋转/移轴至惯性系。

两条路径同时与机械连接闭合对拍。功—能误差使用全轨迹峰值功/能变化作为相对尺度；接近零交叉点的逐点相对比只保留为无 Gate 信用诊断。

## 24 行 Gate

`G01–G24` 依次覆盖：源 pin、拓扑/质量、合法初态与非法默认态拒绝、混合单位、时变激励、有限性/限位、质量矩阵、bias Christoffel 对拍、8DOF 演化、locked KKT、零夹指力反例、RK4/DOP853、四元数、逐刚体线动量、逐刚体角动量、matrix/body 对拍、功—能、机械连接、尺度不变性、零输入退化、常值 effort backend 回归、确定性回放、20 项 mutation/physics 负控、全权限关闭。Gate 的 `review_status` 精确冻结为 `PENDING_OWNER_REVIEW`；任何修改即使同步重签 Gate/manifest 哈希也被 standalone 拒绝。

测试 PASS 只说明本包合同被满足；科学裁决只认 `results/R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_GATE_V1.json`。

## 复现

在项目根目录执行：

```powershell
python 30_simulation/r2_dynamics_engineering_closure/time_varying_torque_plant_candidate_v1/evaluate_time_varying_torque_plant.py --write
python 30_simulation/r2_dynamics_engineering_closure/time_varying_torque_plant_candidate_v1/evaluate_time_varying_torque_plant.py --check
python 30_simulation/r2_dynamics_engineering_closure/time_varying_torque_plant_candidate_v1/run_validation.py
```

manifest 不再从当前目录 `rglob` 反推合法内容，而是使用冻结的 11 路径 allowlist，并固定 19 个外部源 pin；`__pycache__`、pytest cache、`.pyc/.pyo` 与任何未列出的业务文件都会使生成或验证 fail-closed。manifest 显式自排除，独立 receipt 是唯一允许的动态排除项；不含运行时间戳。

## 独立验证架构

`evaluate_time_varying_torque_plant.py --check` 只表示同一 builder/evaluator 的确定性重放，**不得称为独立验证**。真正的交叉验证入口是：

```powershell
python 30_simulation/r2_dynamics_engineering_closure/time_varying_torque_plant_candidate_v1/independent_validate_time_varying_torque_plant.py --write
python 30_simulation/r2_dynamics_engineering_closure/time_varying_torque_plant_candidate_v1/independent_validate_time_varying_torque_plant.py --check
```

该 standalone 文件不导入 `src/time_varying_torque_plant.py`、builder 或 evaluator，也不复用它们的常量/函数。它独立持有 19 个源 pin、合同/证据/Gate 固定哈希及关键阈值，并直接：

- 严格解析 JSON，拒绝重复键、NaN 与正负 Infinity；
- 重新解析 URDF 的 topology、质量、关节类型和限位，并通过公开 Unified R2 backend 复核非法默认状态；
- 从 evidence 的 23 维原始轨迹与功账本，重新计算逐刚体惯性系 `P/H`、完整矩阵对拍、机械连接、功—能、KKT/消元/反力功、坐标尺度不变性与 RK4/DOP853 差异；
- 用独立实现重新积分两条时变 RK4 lane、两条 DOP853 lane、零输入 lane 与常值 effort backend 回归；独立 DOP853 结果按 `qR/qP/dqR/dqP/position/attitude/work` 分字段与存档轨迹比较；
- 逐行重现 G01–G24，并运行 28 项独立 artifact/physics mutation 负控；非零总动量负控调用真实 fail-closed 行为，而不是只检查说明字符串；
- 按冻结 11 路径 allowlist 检查 manifest 和目录 payload，要求条目唯一、有序、无额外文件/缓存/字节码，且 manifest 自身明确排除。

独立验证 receipt 因为由验证器生成，作为明确、唯一的动态排除项不进入 package manifest；standalone validator 会验证这个排除合同，且拒绝任何其他额外业务文件。receipt 本身仍使用严格 JSON、确定性内容和独立 raw SHA 报告。它不授予新的物理、硬件或发布权限。
