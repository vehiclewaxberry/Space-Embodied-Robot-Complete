# 12U 服务星平台舱占位对象候选清单

## 1. 用途

本清单为 Stage 1-C 的 `servicer_12U_v0` 建模提供占位对象。所有占位对象均需在后续质量、质心、惯量预算中单列；外部资产仅提供几何尺度、板卡堆叠和接口组织参考。

## 2. 占位对象表

| subsystem | reference_source | suggested_geometry | estimated_mass_strategy | estimated_volume_strategy | thermal_notes | power_notes | data_interface_notes |
|---|---|---|---|---|---|---|---|
| OBC | PyCubed `mainboard.step`; OreSat backplane/card stack | 单块或双层矩形 PCB，位于 middle_bus_bay | 先按板卡占位估算，后续用实际 OBC 模块或称重更新 | 采用 PyCubed mainboard 外形或 100 mm 级 PCB 占位 | 与散热面保持导热路径；避免贴近机械臂驱动热源 | 作为低/中功耗持续负载 | CAN/UART/Ethernet/USB 等只设接口占位 |
| EPS | PyCubed power schematics; OreSat solar/backplane | PCB + 电源接口板 | 以 EPS 板卡 + 连接器占位估算 | 与 OBC 叠放或背板连接 | 需靠近电池和太阳板接口，注意热隔离 | 负责电源调理和保护 | 记录遥测和开关控制接口 |
| battery | OreSat `OreSat_BatteryAssembly.SLDASM`; PyCubed `batteryboard.step` | 电池包盒体或 18650 阵列占位 | 以单体/电池包估算，置信度 low/medium | 放在中部靠近质心位置 | 电池需热控，避免太阳直晒和机械臂电机热源 | 记录容量和最大放电电流 TBD | BMS 状态遥测接口占位 |
| PMAD | NASA SOA EPS/PMAD 概念；PyCubed/OreSat 电源板 | 电源分配板 + 线束端子 | 按板卡和连接器估算 | 与 EPS 相邻，靠近线束通道 | PMAD 发热需导热路径 | 分配机械臂、相机、OBC、通信、GNC 负载 | 遥测/开关命令接口 |
| reaction_wheel_set | OreSat `OreSat_ReactionWheels.SLDASM` | 三轴或四轮簇盒体 | 以 OreSat wheel cluster 为初始尺度参考，质量另估 | 放在质心附近，减少耦合 | 电机/驱动热源需散热 | 峰值功耗单独记录 | GNC 控制接口占位 |
| IMU | SOA GNC sensor categories | 小型传感器盒体 | 低质量占位，后续按器件手册更新 | 靠近质心/刚性结构 | 温漂敏感，远离强热源 | 低功耗持续负载 | SPI/I2C/UART/CAN 占位 |
| camera_payload | OreSat camera/lens assets | 相机板 + 镜头座 + 视场锥 | 相机板、镜头和支架分别估算 | 放在 front_task_bay，尽量与机械臂工作空间近同轴 | 光学器件需控温和遮光 | 中等功耗，含图像处理峰值 | 高速数据到 OBC/VLA 处理单元 |
| communication_unit | OreSat helical/patch antenna assets | 通信板 + 天线占位 | 通信板、天线、线缆单列 | 后部或侧面，避开机械臂 | 射频功放可能发热 | 峰值发射功耗单列 | RF、遥测、指令链路 |
| propulsion_placeholder | SOA propulsion chapter | 推进器/储箱/阀组简化盒体或圆柱 | 当前只做占位，质量 TBD | rear_service_bay，远离任务面 | 推进热/安全隔离 TBD | 推进阀/加热器功耗 TBD | 命令和状态遥测接口 |
| solar_panel_left | OreSat solar module | 左侧平板/折叠板 | 面板、铰链、线束分别估算 | 左侧外表面，避开机械臂最大工作空间 | 同时作为热表面/受热面 | 发电输入到 EPS | MPPT/遥测接口占位 |
| solar_panel_right | OreSat solar module | 右侧平板/折叠板 | 面板、铰链、线束分别估算 | 右侧外表面，避开机械臂最大工作空间 | 与左侧热环境对称性需说明 | 发电输入到 EPS | MPPT/遥测接口占位 |
| harness_placeholder | OreSat backplane/connector notes | 线束通道、扎带、穿舱孔 | 按线束长度和连接器估算 | 从 rear_service_bay 到 front_task_bay 的保守通道 | 线束避免跨越高温件和运动件 | 记录电源线束载流能力 | 记录相机、机械臂、OBC、EPS 数据线 |
| robot_arm_mount | OreSat mounting beam/stiffeners; reBot base requirement | 前端安装板 + 加强筋 + 法兰 | 安装板、法兰、紧固件、传感器占位单列 | front_task_bay，靠近质心投影并保留 keepout | 机械臂电机热和结构导热需说明 | 机械臂供电峰值单列 | 关节控制、传感器、FT 接口和急停线 |

## 3. Stage 1-C 输出要求

- 每个占位对象必须进入质量/质心/惯量预算表。
- 每个占位对象必须标注坐标系、位置、来源和置信度。
- 只要占位对象影响机械臂工作空间或相机视场，就必须进入工作空间避让图。
