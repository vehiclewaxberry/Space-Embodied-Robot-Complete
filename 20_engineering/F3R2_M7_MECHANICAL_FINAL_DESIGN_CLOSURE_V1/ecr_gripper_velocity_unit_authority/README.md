
# B601 夹爪速度单位权威纠偏 ECR

## 机器结论

`GRIPPER_URDF_UNIT_SEMANTICS_RECONCILED__PHYSICAL_ACTUATOR_SPEED_AND_CONTACT_TIMING_HOLD`

## 已关闭的问题

- accepted URDF 中 `gripper_joint1/2` 均为移动副，`velocity=15` 的模型语义为 **15 m/s**。
- 既有 M7 文件把该值解释成 15 mm/s，并据此计算 4.767 s / 3.667 s；这两项不得再作为下游物理时序。
- accepted URDF 未被修改；本 ECR 只纠正解释与消费规则。
- 新的活跃候选为 `wp5_mechanisms/GRIPPER_ENGINEERING_PACK_V2.yaml`；V1 仅保留为历史证据。

## 仍未关闭的问题

- 15 m/s 只是 URDF 模型上限，不是实测或可指令硬件速度。
- 5 mm/s 仍只是首次接触速度设计目标候选，不是实测能力。
- 真实力—速曲线、时延、占空比、故障响应、开合时间及其不确定度全部保持 `null/HOLD`。
- M06_22 的夹爪行程、接触时间、接触力、法向和锁定确认继续保持 `null/HOLD`。

## 下游规则

动力学、接触、具身强化学习及硬件控制不得从 URDF 速度推导物理时序，也不得用零填充未知量。只有 GVA-PI-01..07 全部受控并通过独立执行器表征 Gate 后，才可生成新的物理夹爪时序。
