# 服务星固定基座三布局比较

本表使用同一套 10 个 B601 STL、同一组关节姿态；每种布局的基座在三个状态中固定，母线盒始终以原点为中心。长度为 mm。

状态：`OPEN_PARKING_AND_WORK_BODY_SURFACE_CHECKS_RECORDED__FINGER_PAIR_UNVERIFIED__NO_OVERALL_PASS`。数字 URDF 质量 4.695555949 kg，未实测。

母线盒尺寸 366 × 226.3 × 226.3；结果暂不含太阳翼、新支承、线束及内部设备。夹爪两个移动关节各为 15 mm。

| 布局 | 姿态 | 整臂+母线包络 X×Y×Z | 顶点最低 signed 距离 | 穿入母线顶点数 | 六轴限位 |
|---|---|---|---:|---:|---|
| roof | stow | 504.808 × 226.300 × 758.480 | 12.000000 | 0 | 满足 |
| roof | initial | 504.808 × 226.300 × 758.480 | 12.000000 | 0 | 满足 |
| roof | work | 694.475 × 226.300 × 715.166 | 12.000000 | 0 | 满足 |
| side | stow | 504.808 × 758.480 × 226.300 | 12.000000 | 0 | 满足 |
| side | initial | 504.808 × 758.480 × 226.300 | 12.000000 | 0 | 满足 |
| side | work | 694.475 × 715.166 × 226.300 | 12.000000 | 0 | 满足 |
| front | stow | 898.180 × 226.300 × 499.579 | 12.000000 | 0 | 满足 |
| front | initial | 898.180 × 226.300 × 499.579 | 12.000000 | 0 | 满足 |
| front | work | 854.866 × 226.300 × 534.625 | 12.000000 | 0 | 满足 |

## 安装与姿态

- roof：xyz=(90, 0, 125.15)，rpy=(0, 0, 0)。
- side：xyz=(90, 125.15, 0)，rpy=(-π/2, 0, 0)。
- front：xyz=(195, 0, 0)，rpy=(0, π/2, 0)。
- 基座基准修正：BRep承载底面位于base_link局部z=2.405 mm；上述坐标是URDF根坐标，不是承载面坐标。
- 当前姿态：stow=[0, -30, -60, 40, 0, 0]°；initial=[0, -30, -60, 40, 0, 0]°；work=[0, -80, -70, 30, 0, 0]°。

## 非相邻 link 三角面相交

整体刚性变换不改变机械臂自交，因此每个姿态检测一次并同时适用于 roof/side/front。排除 URDF 中直接父子 link；夹爪兄弟 link 仍检查。严格分离包围盒用于排除不可能相交的配对，所有包围盒重叠配对由 VTK 原始三角网格检测。

- stow：覆盖 35/36 对，其中 VTK 精检 1 对；表面相交：无。
  未验证：gripper_left/gripper_right；不作整体无相交结论。
- initial：覆盖 35/36 对，其中 VTK 精检 1 对；表面相交：无。
  未验证：gripper_left/gripper_right；不作整体无相交结论。
- work：覆盖 35/36 对，其中 VTK 精检 3 对；表面相交：无。
  未验证：gripper_left/gripper_right；不作整体无相交结论。

## 停放姿态修复与历史负结果

原 stow=(0,-15,-15,60,-30,0)°、手指0 mm的五对三角面相交保存在JSON historical_trials中，未删除。该原姿态不作为当前可用收拢姿态。

当前 stow 状态含义为 OPEN_PARKING 静态开放停放候选，不宣称紧凑收拢、发射约束保持或实物可用。initial 与 stow 使用相同关节值、双指15 mm，共享同一次臂体自交证据；保持件退出160 mm属于CAD装配动作，不在本脚本几何范围。work仅使用其明示覆盖结果。

加速仅移除三角形AABB与两link公共AABB严格分离的原始三角面，未简化或改动保留三角面。重叠配对仍由VTK FirstContact判定。

## 每 link 对母线盒的顶点 signed 距离

距离为盒外正、盒内负；最低值针对 STL 的唯一顶点。负值对应至少一个顶点位于实体母线代理盒内部。正值不证明三角面没有穿过盒体，也不等同于完整网格最小间隙。

| 布局 | 姿态 | link | 最低 signed 距离/mm | 穿入顶点数 |
|---|---|---|---:|---:|
| roof | stow | base_link | 12.000000 | 0 |
| roof | stow | link1 | 89.550001 | 0 |
| roof | stow | link2 | 123.700112 | 0 |
| roof | stow | link3 | 261.823208 | 0 |
| roof | stow | link4 | 424.226477 | 0 |
| roof | stow | link5 | 403.051069 | 0 |
| roof | stow | link6 | 402.612088 | 0 |
| roof | stow | gripper_link | 388.636296 | 0 |
| roof | stow | gripper_left | 402.721139 | 0 |
| roof | stow | gripper_right | 402.695510 | 0 |
| roof | initial | base_link | 12.000000 | 0 |
| roof | initial | link1 | 89.550001 | 0 |
| roof | initial | link2 | 123.700112 | 0 |
| roof | initial | link3 | 261.823208 | 0 |
| roof | initial | link4 | 424.226477 | 0 |
| roof | initial | link5 | 403.051069 | 0 |
| roof | initial | link6 | 402.612088 | 0 |
| roof | initial | gripper_link | 388.636296 | 0 |
| roof | initial | gripper_left | 402.721139 | 0 |
| roof | initial | gripper_right | 402.695510 | 0 |
| roof | work | base_link | 12.000000 | 0 |
| roof | work | link1 | 89.550001 | 0 |
| roof | work | link2 | 123.700385 | 0 |
| roof | work | link3 | 389.702908 | 0 |
| roof | work | link4 | 414.503753 | 0 |
| roof | work | link5 | 383.340980 | 0 |
| roof | work | link6 | 381.631332 | 0 |
| roof | work | gripper_link | 368.892986 | 0 |
| roof | work | gripper_left | 385.845130 | 0 |
| roof | work | gripper_right | 385.723396 | 0 |
| side | stow | base_link | 12.000000 | 0 |
| side | stow | link1 | 89.550001 | 0 |
| side | stow | link2 | 123.700112 | 0 |
| side | stow | link3 | 261.823208 | 0 |
| side | stow | link4 | 424.226477 | 0 |
| side | stow | link5 | 403.051069 | 0 |
| side | stow | link6 | 402.612088 | 0 |
| side | stow | gripper_link | 388.636296 | 0 |
| side | stow | gripper_left | 402.721139 | 0 |
| side | stow | gripper_right | 402.695510 | 0 |
| side | initial | base_link | 12.000000 | 0 |
| side | initial | link1 | 89.550001 | 0 |
| side | initial | link2 | 123.700112 | 0 |
| side | initial | link3 | 261.823208 | 0 |
| side | initial | link4 | 424.226477 | 0 |
| side | initial | link5 | 403.051069 | 0 |
| side | initial | link6 | 402.612088 | 0 |
| side | initial | gripper_link | 388.636296 | 0 |
| side | initial | gripper_left | 402.721139 | 0 |
| side | initial | gripper_right | 402.695510 | 0 |
| side | work | base_link | 12.000000 | 0 |
| side | work | link1 | 89.550001 | 0 |
| side | work | link2 | 123.700385 | 0 |
| side | work | link3 | 389.702908 | 0 |
| side | work | link4 | 414.503753 | 0 |
| side | work | link5 | 383.340980 | 0 |
| side | work | link6 | 381.631332 | 0 |
| side | work | gripper_link | 368.892986 | 0 |
| side | work | gripper_left | 385.845130 | 0 |
| side | work | gripper_right | 385.723396 | 0 |
| front | stow | base_link | 12.000000 | 0 |
| front | stow | link1 | 89.550001 | 0 |
| front | stow | link2 | 123.700112 | 0 |
| front | stow | link3 | 277.311489 | 0 |
| front | stow | link4 | 424.226477 | 0 |
| front | stow | link5 | 403.051069 | 0 |
| front | stow | link6 | 402.612088 | 0 |
| front | stow | gripper_link | 386.508052 | 0 |
| front | stow | gripper_left | 399.408027 | 0 |
| front | stow | gripper_right | 399.382466 | 0 |
| front | initial | base_link | 12.000000 | 0 |
| front | initial | link1 | 89.550001 | 0 |
| front | initial | link2 | 123.700112 | 0 |
| front | initial | link3 | 277.311489 | 0 |
| front | initial | link4 | 424.226477 | 0 |
| front | initial | link5 | 403.051069 | 0 |
| front | initial | link6 | 402.612088 | 0 |
| front | initial | gripper_link | 386.508052 | 0 |
| front | initial | gripper_left | 399.408027 | 0 |
| front | initial | gripper_right | 399.382466 | 0 |
| front | work | base_link | 12.000000 | 0 |
| front | work | link1 | 89.550001 | 0 |
| front | work | link2 | 123.700385 | 0 |
| front | work | link3 | 389.702908 | 0 |
| front | work | link4 | 409.012708 | 0 |
| front | work | link5 | 373.932224 | 0 |
| front | work | link6 | 371.772368 | 0 |
| front | work | gripper_link | 358.076981 | 0 |
| front | work | gripper_left | 372.482623 | 0 |
| front | work | gripper_right | 372.456952 | 0 |

## 证据边界与复现

静态三角面相交只说明源网格在给定姿态存在表面接触/交叉；尚未区分穿透体积、制造配合和数字导出伪影。无相交不能排除一个闭合网格完全包含另一个，也不能证明运动途中安全。直接相邻 link、实物线束、支承与完整装配几何不在本次自交覆盖内。

JSON 保存完整坐标包络、每轴限位、各 link 最低值对应顶点、网格哈希、VTK 配对与覆盖记录。所有源资产只读。

复现最终布局：在项目根目录运行 `python 20_engineering/service_robot_wp01_20260905/layout_study.py`。最终work检测最多90秒，指/指明确跳过为UNVERIFIED；`--candidate-repair`运行300秒候选搜索，`--legacy`运行原始240秒检测。最终布局复现读取JSON中已保存的停放35对原始回执。
