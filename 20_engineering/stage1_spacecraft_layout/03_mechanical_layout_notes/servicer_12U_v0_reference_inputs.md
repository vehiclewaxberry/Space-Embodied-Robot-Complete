# `servicer_12U_v0` 建模参考输入

> 坐标记号迁移（SSOT，2026-07-09）：机械臂基座 = 安装面坐标系 `M`（= reBot URDF 基座）；服务星→安装面统一写 `T_SM`。旧 `B`、`^S T_B` 仅作兼容别名。见 [`../04_mass_inertia_budget/coordinate_frame_definition_v0.md`](../04_mass_inertia_budget/coordinate_frame_definition_v0.md) §0。

## 1. 建模定位

`servicer_12U_v0` 是本项目第一阶段的 12U 展示型服务星基线模型。它可以参考 OreSat、PyCubed、BIRDS 和 NASA 标准提取结果，但必须重新建立为本项目自己的服务星布局，不得把 OreSat/BIRDS/PyCubed 模型直接改名使用。

## 2. 输入对象表

| input_item | reference_source | modeling_role | Stage 1-C notes |
|---|---|---|---|
| main_frame | OreSat `12U_Frames.SLDASM`; CDS Rev.14.1 | 12U 主承力框架、导轨/边界参考 | 建立原创 12U 外形和三舱分区；人工复核 CDS Appendix B 尺寸。 |
| rail_or_tab_reference | CDS Rev.14.1; OreSat frame | rail/tab 约束系统选择 | 当前建议 rail-reference；若改 tab-reference 需重写接口说明。 |
| front_task_bay | 本项目任务需求；OreSat camera/mount reference | 机械臂、相机、视觉标记、照明、抓取接近方向 | 机械臂安装点尽量靠近质心投影；相机与工作空间近同轴。 |
| middle_bus_bay | OreSat backplane/card stack; PyCubed mainboard/batteryboard | OBC/EPS/PMAD/battery/reaction wheel/IMU | 作为质量配平核心；板卡和电池靠近质心。 |
| rear_service_bay | SOA propulsion/communications; OreSat antenna reference | 推进、通信、调试接口、线束出口 | 与前端机械臂任务面隔离；避免喷流/天线与工作空间冲突。 |
| solar_panels | OreSat solar module/panel assets; CDS deployable constraints | 左右侧太阳板和展开/收拢包络 | 必须避开机械臂最大工作空间和相机视场；记录 deployable 状态。 |
| camera_mount | OreSat `lensMount.STEP`, `OreSat1_CameraBoard.SLDPRT` | 前端相机/视觉载荷安装 | 建立相机视场锥；与机械臂工作空间近同轴。 |
| robot_mount_adapter | OreSat mounting beam/stiffeners; reBot base requirements | reBot 安装法兰、转接座、加强结构 | 输出 `T_SM`（旧 `^S T_B`）、安装面坐标系 `M`（=reBot 基座）和 keepout。 |
| internal_card_stack | OreSat backplane/card wedges; PyCubed board models | 中部平台舱板卡堆叠 | 记录板间距、线束通道、质量估算和热路径。 |
| reaction_wheel_cluster | OreSat `OreSat_ReactionWheels.SLDASM` | GNC/姿控占位 | 放在质心附近；不写成已选型飞行硬件。 |
| battery_pack | OreSat battery assembly; PyCubed batteryboard | 电池质量配平和供电占位 | 需要热控说明、BMS/保护接口和质量置信度。 |
| EPS/PMAD | PyCubed power board; SOA EPS/PMAD | 电源调理和分配占位 | 记录机械臂、相机、OBC、通信负载接口。 |
| thermal_area | SOA thermal control; OreSat thermal straps/copper mass | 散热面、导热路径、热隔离区 | 指定外表面散热区，避免被太阳板和机械臂完全遮挡。 |
| antenna_placeholder | OreSat helical/patch antenna | 通信天线外形与部署件占位 | 后部或侧面布置，避开机械臂和太阳板。 |
| propulsion_placeholder | SOA propulsion chapter | 后部推进/阀组/储箱占位 | 当前只做占位，不选型、不仿真。 |
| robot_arm_keepout_volume | reBot workspace; CDS protrusion limits; workspace checklist | 机械臂折叠、展开和最大运动包络 | 必须与太阳板、相机、天线、本体和目标模型叠加检查。 |

## 3. 建模输出要求

- 输出服务星坐标系 `S`，并说明原点是几何中心还是质心。
- 输出前端任务舱、中部平台舱、后部推进/通信舱三舱分界。
- 输出机械臂安装点、相机视场、太阳板收拢/展开包络、天线占位和机器人 keepout volume。
- 输出质量、质心、惯量预算表所需组件清单。
- 输出所有外部参考来源和 attribution。

## 4. 不进入当前建模的内容

- 不生成实际 CAD 文件。
- 不导入并改写 OreSat/BIRDS/PyCubed 外部模型。
- 不运行 SpaceRobotEnv 或 SPOT。
- 不声明任何 GJM/RNS 仿真结果。
