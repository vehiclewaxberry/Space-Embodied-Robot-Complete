# F3-P0: B601 制造级机械架构冻结

```
FREECAD-F3-P0-MECHANICAL-ARCHITECTURE-DESIGN-FREEZE
```

- 阶段：F3-P0（机械架构冻结，不建模）
- 日期：2026-08-04
- 距提交硬截止：28 天
- 性质：架构冻结文档。本文件不创建任何 CAD 几何，不授权建模。
- 前置：F0-F2 FreeCAD 制造级试点 PASS（用户裁决）；SolidWorks B5.1R1 S02 HOLD 归档
- 工具链：FreeCAD（制造级主线）；SolidWorks 证据链冻结为只读历史

---

## 0. 冻结声明

本文件冻结 B601 空间机械臂制造级数字样机的**结构架构**。冻结后，F3-P1 至 F3-P3 的建模工作必须在本架构约束内执行。任何架构级变更（新增/删除子系统、改变载荷路径、改变拓扑）必须回到 P0 重新冻结。

**冻结内容**：
1. B601 制造级结构树
2. 零件 BOM 规划
3. 参数表
4. 载荷路径图
5. F3 五线推进方案

**不冻结内容**（保持 TBD）：
- 具体尺寸公差、材料牌号、紧固件型号
- 供应商电机/减速器/轴承/编码器参数
- FEA 网格/载荷谱/验收准则
- 发射载荷谱、飞行合格性

---

## 1. 权威输入清单

以下输入在本阶段保持只读权威，F3 所有工作必须以其为真值基准：

### 1.1 运动学/质量真值

| 权威 | 路径 | SHA-256 | 用途 |
|---|---|---|---|
| accepted URDF | `20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf` | `408147DD…A3A4`（LF）/ `1BC2B748…C164`（CRLF） | 10 link / 9 joint 拓扑、质量、惯量唯一权威 |
| B601 运动学链报告 | `B5_0…/01_KINEMATICS/B601_ACCEPTED_KINEMATIC_CHAIN.md` | — | URDF 可读投影；R_SM 矩阵、双轨 185.25/198.0 |
| V2_2 PoseMap F1-F4 | `Space_Embodied_Robot_CAD_V2_2/120_B601_Geometry_and_PoseMap_02/` | — | 收拢可达族、走廊违规、限位饱和、q6 调平 |

### 1.2 航天器/接口基准

| 权威 | 路径 | SHA-256 | 用途 |
|---|---|---|---|
| Master Skeleton V2 | `B5_1R1…/02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2.SLDPRT` | `71D70F93…BEFA` | 21 datum 特征、3 配置、G07/G08 足印窗 |
| datum 注册表 | `B5_1R1…/02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2_DATUM_REGISTER.yaml` | `41A76916…BC6E` | CS_S / 双安装轨 / 25° 时钟角 / 纵梁 ±101.65 / 主承力面 ±110.15 / 面板 ±113.15 |
| 基座适配器设计 | `B5_0…/02_DESIGN/B601_BASE_ADAPTER_DESIGN.md` | — | 包络栈 156→198mm；载荷路径拓扑；物理接口 HOLD |
| Carrier 架构合同 | `B5_1R1…/03_CAD/10_KINEMATIC_CARRIERS/B51R1_CARRIER_ARCHITECTURE_CONTRACT.md` | `3998412F…9112` | 10 carrier 运动配合原则、禁止项 |
| URDF-CARRIER 映射 | `B5_1R1…/04_CONFIGURATION/B51R1_URDF_CARRIER_FRAME_MAPPING.yaml` | `4D5488A1…EB43` | 10 link / 9 joint 完整离线映射 |

### 1.3 质量真值（三账分离原则）

| 账目 | 来源 | 值 | 状态 |
|---|---|---|---|
| B601 动力学账 | accepted URDF | 4.6955559493429862 kg（10 links 逐项） | `AUTHORITY_LOCKED` |
| B601 CAD 候选账 | F3 制造级实体 | TBD | `F3_TARGET` |
| 整星质量账 | 各子系统汇总 | TBD | `F4_TARGET` |

**禁令**：CAD 自动质量不得覆盖 URDF 动力学真值。Carrier 质量贡献必须为 0。

---

## 2. B601 制造级结构树

### 2.1 顶层架构

```
SPACECRAFT_TOP_ASSEMBLY (F4 冻结，F3 不建)
│
├── SPACECRAFT_PRIMARY_STRUCTURE
│   ├── 主框 ×N
│   ├── 纵梁 ×4 (Y/Z = ±101.65 mm)
│   ├── 承力面 (±110.15 mm)
│   └── 可拆面板 (±113.15 mm, 无主承力信用)
│
├── B601_ARM_SUBSYSTEM (F3-A 主线)
│   ├── BASE_MODULE
│   │   ├── base_link_carrier (KINEMATIC, mass=0)
│   │   ├── base_housing (Al 7075-T6 候选)
│   │   ├── base_flange (160×160 mm 候选)
│   │   └── base_connector_panel
│   │
│   ├── JOINT_MODULES ×6 (J1-J6, F3-A1)
│   │   ├── J01_SHOULDER_YAW (joint1, R, axis Z)
│   │   ├── J02_SHOULDER_PITCH (joint2, R, axis -Z)
│   │   ├── J03_ELBOW (joint3, R, axis Z)
│   │   ├── J04_ELBOW_AUX (joint4, R, axis Z)
│   │   ├── J05_WRIST_PITCH (joint5, R, axis Z)
│   │   └── J06_WRIST_YAW (joint6, R, axis Z)
│   │
│   ├── LINK_MODULES ×7 (link1-link6 + gripper_link, F3-A2)
│   │   ├── LINK01 (link1, 0.1613 kg URDF)
│   │   ├── LINK02 (link2, 1.3266 kg URDF) ← 大臂, 最重
│   │   ├── LINK03 (link3, 0.8353 kg URDF) ← 前臂
│   │   ├── LINK04 (link4, 0.5200 kg URDF)
│   │   ├── LINK05 (link5, 0.3830 kg URDF)
│   │   ├── LINK06 (link6, 0.3663 kg URDF)
│   │   └── GRIPPER_LINK (0.1818 kg URDF) ← 固定腕接口
│   │
│   └── END_EFFECTOR (F3-D)
│       ├── EE-V1: wrist_flange + camera_mount + F/T_sensor + capture_center
│       ├── EE-V2: + compliant_joint + passive_damping + guide_cone
│       └── EE-V3: + grasp_fingers + locking_mechanism (比赛后延)
│
├── SPACECRAFT_INTERFACE (F3-B)
│   ├── BASE_ADAPTER (A/B/C 待 downselect)
│   │   ├── upper_flange (183-198 mm, 160×160 mm)
│   │   ├── spreader_plate (171-183 mm, 160×160 mm)
│   │   └── primary_boss (156-171 mm, Ø100 mm)
│   └── CLOCK_ANGLE_BLOCK (25° 候选, 待人工批准)
│
├── STOWAGE_RELEASE (F3-C)
│   ├── G07_MAIN_SADDLE
│   │   ├── saddle_bracket (X=40..90 mm 窗)
│   │   ├── contact_pad
│   │   ├── lateral_limit
│   │   ├── axial_stop
│   │   └── preload_element
│   ├── G08_WRIST_SUPPORT
│   │   ├── wrist_bracket (X=-150..-110 mm 窗)
│   │   ├── primary_stop
│   │   ├── secondary_stop
│   │   ├── damping_element
│   │   └── preload_spring
│   └── HDRM (Engineering Candidate)
│       ├── latch
│       ├── release_actuator_envelope
│       ├── preload_spring
│       ├── status_sensor
│       └── mechanical_stop
│
└── HARNESS_ROUTING (F3-A 贯穿)
    ├── per-joint connector
    ├── cable_routing_channel
    ├── strain_relief
    └── rotation_envelope_check
```

### 2.2 关节模块内部结构（F3-A1 统一模板）

每个旋转关节（J1-J6）必须包含以下子结构，不得简化为单一圆柱体：

```
JOINT_MODULE_J##
│
├── ① 主承力壳体 (Joint Housing)
│   ├── 外壳体 (Al 7075-T6 / Al 6061-T6 候选)
│   ├── 加强筋
│   ├── 安装凸台
│   ├── 法兰面 (对接相邻 link)
│   ├── 检修盖板 (可拆卸)
│   └── 热控安装区域 (散热面/MLI 安装面占位)
│
├── ② 输出承载结构 (Load Path)
│   ├── 电机占位 (envelope only, 型号 TBD)
│   ├── 减速器占位 (envelope only, 型号 TBD)
│   ├── 输出轴
│   ├── 轴承座 (前/后轴承)
│   ├── 输出法兰 (对接 link)
│   ├── 螺栓圈 (PCD TBD, 螺栓规格 TBD)
│   └── 定位结构 (定位销 TBD)
│
├── ③ 关节接口 (Interface Control)
│   ├── PCD (TBD)
│   ├── 螺栓规格 (TBD)
│   ├── 定位销 (TBD)
│   ├── 基准面 (URDF joint frame 投影)
│   ├── 轴线 (URDF joint axis)
│   └── 承载方向 (由载荷路径图定义)
│
├── ④ 线束系统 (Harness)
│   ├── connector (占位)
│   ├── cable_routing (内部通道)
│   ├── strain_relief (应变释放)
│   └── rotation_envelope (qmin→qmax 全行程无拉伸/折叠/穿轴)
│
└── ⑤ 传感器占位
    ├── 编码器安装位置 (J1-J6)
    └── 零位索引标记
```

### 2.3 连杆模块内部结构（F3-A2 统一模板）

```
LINK_MODULE_## (link2-link6)
│
├── upper_flange (对接上游关节)
├── shell (CFRP/Al 壳体候选)
│   ├── 壳体壁 (TBD mm)
│   ├── 加强筋
│   └── 内部线束通道
├── lower_flange (对接下游关节)
├── 维护盖板 (可拆卸)
└── collision_envelope (URDF collision mesh 投影)
```

### 2.4 URDF-CAD 对应关系（冻结）

| URDF link | 质量(kg) | CAD 模块 | Carrier | 关节上下游 |
|---|---:|---|---|---|
| base_link | 0.8366 | BASE_MODULE | B51R1_CARRIER_base_link | — → J1 |
| link1 | 0.1613 | LINK01 + J01 housing | B51R1_CARRIER_link1 | J1 ← → J2 |
| link2 | 1.3266 | LINK02 + J02 housing | B51R1_CARRIER_link2 | J2 ← → J3 |
| link3 | 0.8353 | LINK03 + J03 housing | B51R1_CARRIER_link3 | J3 ← → J4 |
| link4 | 0.5200 | LINK04 + J04 housing | B51R1_CARRIER_link4 | J4 ← → J5 |
| link5 | 0.3830 | LINK05 + J05 housing | B51R1_CARRIER_link5 | J5 ← → J6 |
| link6 | 0.3663 | LINK06 + J06 housing | B51R1_CARRIER_link6 | J6 ← → fixed |
| gripper_link | 0.1818 | GRIPPER_LINK + wrist interface | B51R1_CARRIER_gripper_link | fixed ← → P1/P2 |
| gripper_left | 0.0423 | EE finger L | B51R1_CARRIER_gripper_left | P1 ← |
| gripper_right | 0.0423 | EE finger R | B51R1_CARRIER_gripper_right | P2 ← |

---

## 3. 零件 BOM 规划

### 3.1 BOM 层级定义

| 层级 | 定义 | 示例 |
|---|---|---|
| L0 | 顶层装配 | SPACECRAFT_TOP_ASSEMBLY |
| L1 | 子系统装配 | B601_ARM_SUBSYSTEM, STOWAGE_RELEASE |
| L2 | 模块装配 | JOINT_MODULE_J01, LINK_MODULE_02 |
| L3 | 零件 | housing, flange, shaft, bearing_seat |
| L4 | 外购件 | 电机, 减速器, 轴承, 螺栓, 传感器 |

### 3.2 BOM 规划表（F3 范围）

| BOM ID | 层级 | 名称 | 数量 | 材料(候选) | 质量(URDF/CAD) | 制造方法 | 来源 |
|---|---|---|---:|---|---|---|---|
| **F3-A: 机械臂本体** | | | | | | | |
| B601-BASE | L2 | 基座模块 | 1 | Al 7075-T6 | 0.8366(URDF) / TBD(CAD) | 机加工 | F3-P1 |
| B601-J01 | L2 | J01 肩偏航关节模块 | 1 | Al 7075-T6 | TBD | 机加工 | F3-P1 |
| B601-J02 | L2 | J02 肩俯仰关节模块 | 1 | Al 7075-T6 | TBD | 机加工 | F3-P1 |
| B601-J03 | L2 | J03 肘关节模块 | 1 | Al 7075-T6 | TBD | 机加工 | F3-P1 |
| B601-J04 | L2 | J04 肘辅关节模块 | 1 | Al 7075-T6 | TBD | 机加工 | F3-P1 |
| B601-J05 | L2 | J05 腕俯仰关节模块 | 1 | Al 7075-T6 | TBD | 机加工 | F3-P1 |
| B601-J06 | L2 | J06 腕偏航关节模块 | 1 | Al 7075-T6 | TBD | 机加工 | F3-P1 |
| B601-L01 | L2 | LINK01 连杆 | 1 | Al 6061-T6 | 0.1613(URDF) / TBD | 机加工 | F3-P1 |
| B601-L02 | L2 | LINK02 大臂 | 1 | CFRP+Al 端接 | 1.3266(URDF) / TBD | 复材+机加工 | F3-P1 |
| B601-L03 | L2 | LINK03 前臂 | 1 | CFRP+Al 端接 | 0.8353(URDF) / TBD | 复材+机加工 | F3-P1 |
| B601-L04 | L2 | LINK04 连杆 | 1 | Al 6061-T6 | 0.5200(URDF) / TBD | 机加工 | F3-P1 |
| B601-L05 | L2 | LINK05 连杆 | 1 | Al 6061-T6 | 0.3830(URDF) / TBD | 机加工 | F3-P1 |
| B601-L06 | L2 | LINK06 连杆 | 1 | Al 6061-T6 | 0.3663(URDF) / TBD | 机加工 | F3-P1 |
| B601-GRP | L2 | GRIPPER_LINK 腕接口 | 1 | Al 6061-T6 | 0.1818(URDF) / TBD | 机加工 | F3-P1 |
| **F3-B: 航天器接口** | | | | | | | |
| ADAPTER-UP | L3 | 适配器上法兰 | 1 | Al 7075-T6 | TBD | 机加工 | F3-P1 |
| ADAPTER-SP | L3 | 适配器扩展板 | 1 | Al 7075-T6 | TBD | 机加工 | F3-P1 |
| ADAPTER-BS | L3 | 适配器主凸台 | 1 | Al 7075-T6 | TBD | 机加工 | F3-P1 |
| **F3-C: 收拢释放** | | | | | | | |
| G07-BRKT | L3 | G07 主鞍座支架 | 1 | Al 7075-T6 | TBD | 机加工 | F3-P2 |
| G07-PAD | L3 | G07 接触垫 | 1 | TBD | TBD | TBD | F3-P2 |
| G08-BRKT | L3 | G08 腕部支撑支架 | 1 | Al 7075-T6 | TBD | 机加工 | F3-P2 |
| G08-PAD | L3 | G08 接触垫 | 1 | TBD | TBD | TBD | F3-P2 |
| G08-DAMP | L3 | G08 阻尼元件 | 1 | TBD | TBD | TBD | F3-P2 |
| HDRM-ASM | L2 | HDRM 功能包络 | 1-2 | TBD | TBD | 外购/定制 | F3-P2 |
| **F3-D: 末端执行器** | | | | | | | |
| EE-V1-FLANGE | L3 | EE 腕法兰 | 1 | Al 6061-T6 | TBD | 机加工 | F3-P3 |
| EE-V1-CAM | L3 | EE 相机支架 | 1 | Al 6061-T6 | TBD | 机加工 | F3-P3 |
| EE-V1-FT | L3 | EE F/T 传感器层 | 1 | TBD | TBD | 外购 | F3-P3 |
| EE-V2-COMP | L3 | EE 柔顺关节 | 1 | TBD | TBD | TBD | F3-P3 |
| EE-V2-CONE | L3 | EE 导向锥 | 1 | TBD | TBD | 3D打印/机加工 | F3-P3 |

### 3.3 外购件占位（L4, 型号全部 TBD）

| 类别 | 数量(估) | 关键参数 TBD | 约束 |
|---|---:|---|---|
| 电机 | 6+2 | 型号/额定转矩/峰值转矩/转速 | URDF effort/velocity 字段不可升级为额定值 |
| 减速器 | 6 | 型号/传动比/背隙/刚度 | — |
| 轴承 | ≥12 | 型号/内外径/动载/静载 | — |
| 编码器 | 6 | 型号/分辨率/零位索引 | — |
| 螺栓 | TBD | 规格/等级/预紧/防松 | PCD/孔边距待定 |
| 定位销 | TBD | 规格/配合 | — |
| F/T 传感器 | 1 | 量程/过载/精度 | — |
| 相机 | 3 | 型号/FOV/分辨率/帧率 | 基座/腕部/末端各一 |
| HDRM | 1-2 | 保持力/释放力/行程/时间 | Engineering Candidate |
| 连接器 | TBD | 键位/插拔方向/拉脱力 | — |

---

## 4. 参数表

### 4.1 运动学参数（accepted URDF 冻结值）

| 关节 | 类型 | 原点 xyz (m) | 原点 rpy (rad) | 轴 | 下限 | 上限 | q0 语义 |
|---|---|---|---|---|---:|---:|---|
| joint1 | revolute | -0.000084, 0, 0.08465 | 0, 0, 0 | 0,0,1 | -2.8 rad | 2.8 rad | interior |
| joint2 | revolute | 0.020084, 0.031625, 0.05555 | -1.5708, 0, 0 | 0,0,-1 | -3.14 rad | 0 rad | upper limit |
| joint3 | revolute | -0.264, 0, 0 | 0, 0, 0 | 0,0,1 | -3.14 rad | 0 rad | upper limit |
| joint4 | revolute | 0.2426, -0.054, -0.001625 | 0, 0, 0 | 0,0,1 | -1.87 rad | 1.57 rad | interior |
| joint5 | revolute | 0.078308, -0.0375, -0.03 | -1.5708, 0, 0 | 0,0,1 | -1.57 rad | 1.57 rad | interior |
| joint6 | revolute | 0.023692, 0, 0.04 | 0, 1.5708, 0 | 0,0,1 | -3.14 rad | 3.14 rad | interior; mate flip check |
| gripper_joint | fixed | 0, 0, 0.15971 | 0, -1.5708, 0 | — | — | — | exact transform |
| gripper_joint1 | prismatic | -0.042091, 2.75e-05, -1.3e-05 | 0, 0, -1.5708 | 1,0,0 | 0 m | 0.0715 m | MIN_NUMERIC |
| gripper_joint2 | prismatic | -0.042091, -2.75e-05, 1.3e-05 | 0, 0, 1.5708 | 1,0,0 | 0 m | 0.0715 m | MIN_NUMERIC |

### 4.2 质量惯量参数（accepted URDF 冻结值）

| 连杆 | m (kg) | CoM x,y,z (m) | Ixx (kg·m²) | Iyy | Izz |
|---|---:|---|---:|---:|---:|
| base_link | 0.8366 | ~0, ~0, 0.0298 | 0.00133 | 0.00213 | 0.00276 |
| link1 | 0.1613 | 0.00011, -0.00062, 0.0236 | 0.000252 | 0.000155 | 0.000234 |
| link2 | 1.3266 | -0.13226, -0.00306, -0.0308 | 0.000734 | 0.01256 | 0.01281 |
| link3 | 0.8353 | 0.12104, -0.05362, -0.0310 | 0.000468 | 0.006327 | 0.006482 |
| link4 | 0.5200 | 0.06082, -0.05117, -0.0303 | 0.000460 | 0.000753 | 0.000667 |
| link5 | 0.3830 | -0.00503, ~0, 0.0386 | 0.000198 | 0.000217 | 0.000172 |
| link6 | 0.3663 | ~0, -0.00010, 0.0253 | 0.000156 | 0.000156 | 0.000140 |
| gripper_link | 0.1818 | -0.11400, ~0, ~0 | 0.000232 | 0.0000585 | 0.000205 |
| gripper_left | 0.0423 | 0.00937, -0.01835, -0.00213 | 9.69e-6 | 9.72e-6 | 1.14e-5 |
| gripper_right | 0.0423 | 0.00937, +0.01835, +0.00213 | 9.69e-6 | 9.72e-6 | 1.14e-5 |
| **合计** | **4.6956** | — | — | — | — |

### 4.3 航天器安装参数

| 参数 | 值 | 来源 | 状态 |
|---|---|---|---|
| 安装面（显示轨） | X = 198.0 mm | V2.2 人工批准(2026-07-27) | frozen |
| 安装面（动力学轨） | X = 185.25 mm | PDR/dynamics | frozen |
| 轨道差 | 12.75 mm | DUAL_TRACK_EXPLICIT | frozen, 不得隐藏在 joint origin |
| R_SM | [[0,0,1],[0,1,0],[-1,0,0]] | accepted URDF | frozen |
| 时钟角 | 25° (推荐) / ≥7.894° (下限) | O11 裁决 | **待人工批准** |
| 纵梁轴 | Y/Z = ±101.65 mm | V2 datum 测量 | frozen (旧 105.65 已弃用) |
| 主承力面 | Y/Z = ±110.15 mm | V2 datum 测量 | frozen |
| 可拆面板外表面 | Y/Z = ±113.15 mm | V2 datum 测量 | frozen (无主承力信用) |
| 安装设计目标 | 160 × 160 mm | PDR | target |
| 中央禁入通道 | Ø100 mm | PDR | target |
| G07 足印窗 (Z=113.15) | X = [-20,0] / [80,100] / [160,180] mm | 耐久测量 | candidate |
| G08 足印窗 (Z=113.15) | X = [-150,-110] mm | 耐久测量 | candidate |

### 4.4 收拢位形参数（V2_2 PoseMap 发现）

| 参数 | 值 | 来源 | 状态 |
|---|---|---|---|
| 收拢向量 q_deg | [160.0, -179.909, -53.909, -25.143, -29.954, 157.591] | V2_2 PoseMap F1-F4 | CANDIDATE_HOLD |
| EE 位置 (收拢) | [-121.9, -38.8, 161.1] mm | FK 计算 | CANDIDATE_HOLD |
| q6 调平角 | 157.591° | 雅可比证明(纯自旋) | CANDIDATE_HOLD |
| 关节心 max\|Y\| | 70.9 mm (运动学) / 118.6 mm (实体) | V2_2 MC1 | FAIL_RECORDED |
| 走廊目标 \|Y\| | ≤40 mm | PDR | violated (运动学事实) |
| 三点发射支承 | 安装法兰 + 主鞍座(G07) + 腕鞍座(G08) | V2_2 S4 | candidate |

### 4.5 材料候选（F3 冻结候选集，非最终选型）

| 部件 | 候选材料 | 理由 | 状态 |
|---|---|---|---|
| 关节壳体 | Al 7075-T6 | 航天成熟、高比强度、加工性好 | candidate |
| 关节壳体(备选) | Al 6061-T6 | 成本低、焊接性好、航天成熟 | candidate |
| 大臂/前臂壳体 | CFRP + Al 端接 | 轻量化、刚度可控 | candidate |
| 短连杆壳体 | Al 6061-T6 | 简单可靠 | candidate |
| 适配器 | Al 7075-T6 | 高承载 | candidate |
| G07/G08 支架 | Al 7075-T6 | 高承载 | candidate |
| 接触垫 | TBD | 需阻尼/耐磨/热隔离要求 | TBD |
| HDRM | TBD | 需供应商数据 | TBD |

---

## 5. 载荷路径图

### 5.1 主载荷路径（发射/收拢态）

```
                    发射载荷谱 (TBD)
                          │
                 ┌────────▼────────┐
                 │  整星惯性载荷    │
                 └────────┬────────┘
                          │
              ┌───────────┼───────────┐
              │           │           │
     ┌────────▼───┐  ┌───▼────┐  ┌──▼─────────┐
     │ B601 惯性   │  │ 太阳翼  │  │ 航天器本体  │
     │ (4.7 kg)   │  │ 惯性    │  │ 惯性       │
     └────────┬───┘  └───┬────┘  └────────────┘
              │           │
     ┌────────▼───────────▼────────┐
     │    三点发射支承系统          │
     │  ① 安装法兰 (base_adapter)  │
     │  ② G07 主鞍座               │
     │  ③ G08 腕部支撑             │
     └────────┬────────┬───────────┘
              │        │
     ┌────────▼──┐  ┌──▼──────────────┐
     │ base_     │  │ G07/G08 支架     │
     │ adapter   │  │                  │
     │           │  │ primary_stop     │
     │ upper     │  │ secondary_stop   │
     │ flange    │  │ preload          │
     │ →spreader │  │ damping          │
     │ →boss     │  └──┬───────────────┘
     └─────┬─────┘     │
           │           │
     ┌─────▼───────────▼───────────┐
     │    主承力结构                 │
     │  前框 → 纵梁(±101.65)        │
     │  → 承力面(±110.15)           │
     │  → 主结构                    │
     └──────────────────────────────┘
```

### 5.2 在轨操作载荷路径（展开态）

```
     目标接触力 (TBD)
          │
     ┌────▼────┐
     │ 末端执行器│
     │ EE-V1/V2│
     └────┬────┘
          │
     ┌────▼────────────────────────┐
     │ J06 → J05 → J04 → J03 → J02 │
     │ (腕→肘→肩, 逐级放大)         │
     └────┬────────────────────────┘
          │
     ┌────▼────┐
     │  J01    │
     │ 基座关节 │
     └────┬────┘
          │
     ┌────▼──────────┐
     │ base_adapter  │
     │ (六向载荷)     │
     └────┬──────────┘
          │
     ┌────▼──────────────────────────────┐
     │ 航天器主结构 → 自由漂浮基座         │
     │ (sim_05: 19.20° 姿态扰动)          │
     │ (sim_08: 推力器消旋需求)           │
     └────────────────────────────────────┘
```

### 5.3 载荷路径关键节点（必须验证）

| 节点 | 载荷类型 | 验证内容 | 当前状态 |
|---|---|---|---|
| B601 法兰 → 适配器 | 6-DOF (弯/剪/扭/轴) | 螺栓圈、定位销、预紧 | TBD |
| 适配器 → 主框/纵梁 | 6-DOF | 载荷分配、局部加强 | TBD |
| G07 接触垫 | 法向压缩 + 横向剪切 | 接触压力、允许滑移、长细比 | TBD |
| G08 支撑 | 6-DOF | primary/secondary stop、阻尼 | TBD |
| HDRM 预紧/释放 | 轴向保持力 | 行程、残留体、冲击 | TBD |
| Ø100 通道 | 截面削弱 | 开孔前后刚度/应力/屈曲对比 | TBD |
| 太阳翼/机械臂共用节点 | 叠加载荷 | 组合工况、载荷竞争 | TBD |

---

## 6. F3 五线推进方案

### 6.1 线路划分与优先级

```
F3-P0 架构冻结 (本文件)
        │
   ┌────┼────┬────┬────┐
   │    │    │    │    │
   P1   P1   P2   P3   (同步)
   │    │    │    │    │
  F3-A F3-B F3-C F3-D  F3-E
  本体  接口  收拢  末端  动力学
  (最高)(高)  (高)  (中)  (贯穿)
```

### 6.2 F3-P1: 关节+连杆（F3-A + F3-B 基座适配器）

**目标**：完成 6 关节模块 + 7 连杆模块 + 基座适配器的制造级 FreeCAD 模型

**推进顺序**（按载荷路径，非零件顺序）：

```
载荷路径 → 接口 → 关节 → 连杆 → 末端 → 控制模型
```

**P1 具体步骤**：

1. **A1: 关节模块设计**（6 个统一模板 + 个体参数）
   - 每关节：主承力壳体 → 输出承载结构 → 关节接口 → 线束 → 传感器占位
   - 输出：JOINT_INTERFACE_CONTROL_DOCUMENT（PCD/螺栓/定位销/基准面/轴线/承载方向）
   - 线束验证：qmin→qmax 全行程，不拉伸/不折叠/不穿轴

2. **A2: 连杆制造设计**（7 个，从最重/最长优先）
   - 优先级：LINK02(大臂,1.33kg) → LINK03(前臂,0.84kg) → LINK04 → LINK05 → LINK06 → LINK01 → GRIPPER_LINK
   - 每连杆：壳体+两端金属端接+加强筋+内部线束通道+维护盖
   - 输出：LINK##_MANUFACTURING_REPORT.md

3. **B: 基座适配器深化**
   - 从 B5.0 envelope（156-198mm 包络栈）升级为制造级
   - A/B/C 贸易 downselect（需人工裁决 H9）
   - 载荷路径：B601 A0 → upper flange → spreader → boss → 前框 → 纵梁 → 主结构

**P1 退出条件**：
- 6/6 关节模块 + 7/7 连杆模块 FreeCAD 文件存在
- 适配器 downselect 完成
- 每模块有 LINK/JOINT##_MANUFACTURING_REPORT.md
- FREECAD_MASS_REGISTER.yaml 逐项填写
- URDF 质量保持权威不被覆盖

### 6.3 F3-P2: 收拢与释放机构（F3-C）

**目标**：完成 G07/G08/HDRM 制造级设计

**P2 具体步骤**：

1. **G07 主鞍座**
   - 导向锥面 + 接触垫 + 横向限位 + 轴向挡块 + 预紧结构
   - X 窗 [40,90]mm，接触高 z≈156.45mm（V2_2 实测）
   - +Y 钳口被 ±113.15 包络裁剪问题 → 顶部绑带 HOLD（V2_2 发现）

2. **G08 腕部支撑**
   - 6-DOF load path: primary stop + secondary stop + preload + damping
   - X 窗 [-150,-110]mm，接触高 z≈140.02mm
   - 不得侵入两个独立 P 全行程和接触面区域

3. **HDRM**
   - Engineering Candidate（非飞行型号）
   - latch + release_actuator_envelope + preload_spring + status_sensor + mechanical_stop
   - 输出：HDRM_FUNCTIONAL_DESIGN.md

**P2 退出条件**：
- G07/G08/HDRM FreeCAD 文件存在
- G07/G08 DOF 分配矩阵不形成刚性过约束
- HDRM 释放后完全退出初始抬离路径
- H10 28/28 disposition（与 G07/G08 相关的 12 行关闭）

### 6.4 F3-P3: 末端执行器（F3-D）

**目标**：EE-V1 + EE-V2（比赛优先）

**P3 具体步骤**：

1. **EE-V1: 接口级**
   - wrist flange → camera mount → F/T sensor → capture center
   - 对应 URDF: gripper_link + gripper_joint(fixed)

2. **EE-V2: 柔顺捕获**
   - + compliant joint + passive damping + guide cone
   - 与 sim_11 接触带宽（T_c=20ms PROVISIONAL）呼应

3. **EE-V3: 非合作目标**（比赛后延）
   - + grasp fingers + locking mechanism

**P3 退出条件**：
- EE-V1 FreeCAD 文件存在，含三个相机 frame 占位
- EE-V2 compliant joint + guide cone 文件存在
- CS_GRASP_CENTER 由两指接触几何和两条 P 位移共同计算

### 6.5 F3-E: 动力学/结构分析同步（贯穿全程）

**每完成一个结构必须更新**：

1. **质量账本** `FREECAD_MASS_REGISTER.yaml`

```yaml
# 字段模板
component: B601-J01-housing
mass: TBD  # FreeCAD 计算值
cg: [TBD, TBD, TBD]
inertia: [TBD, TBD, TBD, TBD, TBD, TBD]  # Ixx,Iyy,Izz,Ixy,Ixz,Iyz
source: FreeCAD-0.21-material-Al7075-T6
confidence: ENGINEERING_ESTIMATE  # 非 URDF 权威
urdf_counterpart: link1  # URDF mass=0.1613 kg
```

2. **柔性接口模型** `B601_FLEX_MODEL.yaml`

```yaml
# 字段模板
link_stiffness:
  link2:
    k_axial: TBD    # N/m
    k_bending: TBD  # N·m/rad
    k_torsion: TBD  # N·m/rad
joint_stiffness:
  joint1:
    k_rotational: TBD  # N·m/rad
    damping: TBD       # N·m·s/rad
base_compliance:
  k_6x6: TBD  # 6×6 矩阵
support_stiffness:
  G07: TBD
  G08: TBD
```

3. **模态分析**（两批）

| Case | 边界条件 | 输出 | 前置 |
|---|---|---|---|
| Case 1 | 机械臂展开, base fixed | 前 10 阶模态、频率、主导分量 | P1 完成 |
| Case 2 | 自由漂浮: spacecraft + arm | 前 10 阶模态、频率、主导分量 | P1+P2 完成 |

**F3-E 禁令**：
- 无正式发射载荷谱时只能做 PRELIMINARY_UNIT_LOAD_AND_MODAL_CANDIDATE
- 不得声称发射合格
- 适配器/G07/G08 局部变形/屈曲/接触任一项未裁决，不得进入结构 Gate 通过汇总

---

## 7. F3→F4 过渡条件

以下全部满足才允许进入 F4（SPACECRAFT_TOP_ASSEMBLY）：

```
□ 10 links 制造级 FreeCAD 模型存在
□ 6 joints 制造级 FreeCAD 模型存在
□ G07/G08 制造级 FreeCAD 模型存在
□ HDRM 功能包络 FreeCAD 模型存在
□ EE-V1 + EE-V2 FreeCAD 模型存在
□ Base adapter downselect 完成
□ FREECAD_MASS_REGISTER.yaml 逐项填写
□ B601_FLEX_MODEL.yaml 初始版本
□ URDF 映射验证通过（URDF 质量不被 CAD 覆盖）
□ H10 28/28 disposition complete
□ 模态分析 Case 1 + Case 2 完成
```

**不满足时的禁止项**：
- 禁止建立 SPACECRAFT_TOP_ASSEMBLY_FREECAD.FCStd
- 禁止宣称 COMPLETE / MANUFACTURING_READY / FLIGHT_READY / LAUNCH_QUALIFIED

---

## 8. 冻结裁决

```
F3_P0_MECHANICAL_ARCHITECTURE_FROZEN
TOOLCHAIN: FreeCAD (manufacturing-grade mainline)
URDF_AUTHORITY: LOCKED (4.6955559493429862 kg, 10L/9J)
MASTER_SKELETON: V2 datum inherited (SLDPRT → FreeCAD datum mapping)
LOAD_PATH: FROZEN (three-point stowage + adapter → primary structure)
BOM: FROZEN (F3-A/B/C/D scope, L4 external all TBD)
MATERIAL_CANDIDATES: Al 7075-T6 / Al 6061-T6 / CFRP (non-final)
H10: 0/28 (carried forward)
T005: NOT_RUN
FEA: NOT_STARTED
LAUNCH_QUALIFICATION: NOT_STARTED

NEXT_AUTHORIZED_STEP: F3-P1 (joint + link + adapter modeling)
NEXT_AUTHORIZATION_REQUIRED: F3-P1 execution prompt

FORBIDDEN_IN_F3:
  - SolidWorks reactivation (evidence chain frozen read-only)
  - Text2CAD for B601/HDRM/saddle/contact surfaces
  - STEP→SW large-scale conversion
  - COMPLETE / MANUFACTURING_READY / FLIGHT_READY claims
  - CAD mass overriding URDF mass
  - Building top assembly before P1-P3 exit conditions met
```

---

## 9. 未决人工裁决项（F3 前置）

| ID | 裁决内容 | 影响 | 优先级 |
|---|---|---|---|
| H9 | 适配器 A/B/C downselect 或批准双分支 | F3-B, F3-P1 | 最高 |
| O3 | T_SM 双轨冲突 (185.25 dynamics vs 198 display) | 安装精度 | 高 |
| O11 | 25° 时钟角人工批准 | 横向包络 | 高 |
| STOW_Z | STOW_Z_LIMIT 定义 | 收拢包络闭合 | 高 |
| C5 | 翼根机构宽 302.3mm vs 226.3mm 包络 | 收拢态闭合 | 高 |
| HIFI | 252MB vendor STEP 交互式导入 | 精细几何来源 | 中 |
| T_c | B601 夹爪闭合时间实测 → 替换 20ms 占位 | sim_11 接触带宽 | 中 |
| 帆板质量 | 真实帆板质量替换 0.348kg 占位 | 动力学结论稳定性 | 最高(论文) |

---

## 10. 文件组织约定

```
20_engineering/cad/F3_MANUFACTURING_GRADE_DESIGN/
├── F3_P0_MECHANICAL_ARCHITECTURE_FREEZE.md   ← 本文件
├── F3_P1_JOINTS_AND_LINKS/                    ← P1 工作区
│   ├── joints/
│   ├── links/
│   ├── adapter/
│   └── reports/
├── F3_P2_STOWAGE_RELEASE/                     ← P2 工作区
│   ├── G07/
│   ├── G08/
│   ├── HDRM/
│   └── reports/
├── F3_P3_END_EFFECTOR/                        ← P3 工作区
│   ├── EE_V1/
│   ├── EE_V2/
│   └── reports/
├── F3_E_DYNAMICS_SYNC/                        ← 同步分析
│   ├── FREECAD_MASS_REGISTER.yaml
│   ├── B601_FLEX_MODEL.yaml
│   └── modal_analysis/
└── F3_GATE_CHECK.json                         ← F3 总 Gate
```

---

*本文件冻结 B601 制造级机械架构。后续所有 F3 建模工作必须在此架构约束内执行。架构级变更须回到 P0 重新冻结。*
