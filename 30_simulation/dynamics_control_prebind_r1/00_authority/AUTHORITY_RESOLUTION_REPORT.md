# Authority Resolution Report

## 裁决

PB-G0 定位/哈希层为 `VERIFIED`，权威充分性层为 `HOLD`。因此聚合裁决是
`PB_G0_HOLD_PARTIAL_AUTHORITY`，允许的最大工作范围仅为隔离的参数映射和
PB-00 非信用诊断。

## 已绑定

- Accepted B601 URDF 原始字节哈希已锁定，4.695555949342986 kg，禁止修改。
- Unified R2 source-only URDF 已锁定，19 link / 18 joint / 8 movable DOF，
  总质量 31.022864807342987 kg；Route-C 明确未包含。
- 物理安装与动力学参考之间只能使用唯一 bridge：绕 A0-z
  +25.000014 deg、沿 A0-z +0.02275 m。

## 未闭合

- 系统与目标正式质量惯量 authority；
- frame owner confirmation；
- 0.005 m/s 与 0.05 m/s 的接触速度冲突；
- 关节、基座、夹爪硬件执行器动力学；
- 当前脏仓关键资产的版本控制留存信用。

任何 UNKNOWN 不得自动转为 ALLOW，任何 null 不得补零。
