# Robot Mount Adapter v0 参考输入

> 坐标记号迁移（SSOT，2026-07-09）：机械臂基座 = 安装面坐标系 `M`（= reBot URDF 基座，SSOT 已将旧 `B` 并入 `M`）；服务星→安装面统一写 `T_SM`。旧 `B`、`^S T_B`、`^M T_B` 仅作兼容别名。见 [`../04_mass_inertia_budget/coordinate_frame_definition_v0.md`](../04_mass_inertia_budget/coordinate_frame_definition_v0.md) §0。

## 1. 建模定位

`robot_mount_adapter_v0` 用于连接 `servicer_12U_v0` 前端任务面与 reBot 等效空间机械臂。外部资产仅提供安装梁、板卡固定、结构加强和线缆组织参考；最终转接座必须由本项目按 reBot 基座和服务星坐标系重新定义。

## 2. 输入对象表

| input_item | reference_source | modeling_role | Stage 1-C notes |
|---|---|---|---|
| servicer_mounting_plate | OreSat frame/mounting beam; CDS mechanical constraints | 服务星前端安装板 | 定义安装面坐标系 `M`；记录板厚、外形、紧固件占位和材料假设。 |
| reBot_base_flange | reBot physical/URDF base requirement; SpaceRobotEnv `v_base.stl` only as visual reference | 机械臂基座法兰 | 必须与 `reBot-DevArm_fixend.urdf` 基座坐标系一致；SpaceRobotEnv 不替代 reBot。 |
| bolt_pattern_placeholder | OreSat fastener/mounting examples | 螺栓孔阵列占位 | 先定义孔位字段，不写最终加工尺寸；避免侵占导轨/外包络。 |
| cable_routing_channel | OreSat backplane/cable guide; PyCubed connector layout | 电源、数据、传感器线缆通道 | 线缆不得穿越机械臂运动包络；保留急停和传感器线。 |
| coordinate_frame_marker | 本项目坐标系规范（SSOT） | `S`, `M` 坐标系可视化标记（M=机械臂安装面=reBot 基座；旧 `B` 兼容） | 输出 `T_SM`（旧 `^S T_B`）；CAD 图中必须显示服务星坐标系 `S` 与安装面坐标系 `M`。 |
| force_torque_sensor_placeholder | Stage 2 contact/impedance requirements | 力/力矩传感器或虚拟接口占位 | 可为空间预留或仿真接口；不声明已采购传感器。 |
| stiffness_reinforcement | OreSat `MountingBeam.STEP`, frame stiffeners | 加强筋、背板、三角撑 | 目标是降低 reBot 基座柔性和装配晃动；需记录质量和惯量影响。 |
| keepout_zone | workspace checklist; CDS protrusion limits; solar/camera/antenna layout | 机械臂折叠/展开/维护禁入空间 | 与太阳板、相机视场、天线、本体和目标星包络叠加检查。 |

## 3. 必须输出的参数

| parameter | meaning |
|---|---|
| `T_SM` | 服务星坐标系 `S` 到安装面坐标系 `M` 的固定变换（机械臂基座桥；旧 `^S T_M`/`^S T_B`）。 |
| `M` = reBot URDF 基座 | 安装面坐标系 `M` 即 reBot URDF 基座（SSOT 已并入旧 `B`；旧 `^M T_B` = 单位阵/兼容）。 |
| `adapter_mass_kg` | 转接座质量估计。 |
| `adapter_com_S_m` | 转接座质心在服务星坐标系下的位置。 |
| `adapter_inertia_kgm2` | 转接座惯量估计。 |
| `adapter_collision_geometry` | 转接座简化碰撞几何。 |
| `robot_arm_keepout_volume` | reBot 折叠、展开和最大运动包络。 |

## 4. 检查项

- [ ] reBot 基座固定方式已定义。
- [ ] 前端任务面未侵占导轨或外部包络禁区。
- [ ] 螺栓孔阵列、定位销和线缆孔有占位。
- [ ] 力/力矩传感器或虚拟接口预留。
- [ ] 转接座质量、质心、惯量进入预算表。
- [ ] 机械臂 keepout zone 与太阳板、相机、天线和目标模型叠加检查。
- [ ] 所有外部参考均有 attribution。

## 5. 不允许事项

- 不把 OreSat 安装梁直接改成 reBot 转接座最终 CAD。
- 不把 SpaceRobotEnv `v_base.stl` 当作 reBot 基座。
- 不修改 `reBot-DevArm_fixend.urdf`。
- 不生成实际 CAD 文件。
