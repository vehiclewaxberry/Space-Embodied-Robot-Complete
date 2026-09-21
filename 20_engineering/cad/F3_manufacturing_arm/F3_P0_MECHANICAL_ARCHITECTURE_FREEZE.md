# F3-P0: B601 制造级机械架构冻结

状态：`F3_P0_ARCHITECTURE_FREEZE_PROPOSAL`
日期：2026-08-04
前置：F0–F2 FreeCAD 制造级试点 PASS（工具链稳定性已关闭）
权威输入：accepted URDF、frame_tree_v1.yaml、mass_inertia_budget_v1.csv、LOAD_PATH.md、B51R1 系统架构基线 V1

> 本文档冻结 B601 制造级结构架构。不建模。不生成几何。不修改 accepted URDF。
> 目的：为 F3-P1（关节+连杆）、F3-P2（收拢机构）、F3-P3（末端执行器）提供不可返工的结构合同。

---

## 0. 冻结原则

1. **载荷路径优先**：先定载荷链 → 再定接口 → 再定关节 → 再定连杆 → 再定末端 → 最后控制模型。
2. **URDF 质量权威不变**：CAD 质量 = 工程估计（`MASS_AUTHORITY=EXCLUDED`），URDF 质量 = 动力学真值。
3. **接口冻结先于几何**：每个关节的 ICD（PCD/螺栓/定位销/基准面/轴线/承载方向）在本阶段冻结，后续几何必须遵守。
4. **禁止跨阶段消费**：PLACEHOLDER 不当零；未裁决的载荷不进 FEA；CAD 体积不生成飞行质量。
5. **FreeCAD 原生**：所有 F3 几何以 `.FCStd` 原生格式交付，STEP 仅作交换见证。

---

## 1. B601 制造级结构树

### 1.1 顶层装配树

```
B601_MANUFACTURING_GRADE.FCStd (顶层装配)
│
├── 00_MASTER_SKELETON                    零实体骨架（基准面/参数/包络）
│
├── 10_BASE_MODULE                        基座模块
│   ├── 11_base_housing                   基座主承力壳体
│   ├── 12_base_flange                    基座输出法兰（对接 IF-RM-002）
│   ├── 13_base_bearing_seat              基座轴承座
│   ├── 14_base_cable_routing             基座线束通道
│   └── 15_base_service_cover             基座检修盖
│
├── 20_JOINT1_MODULE (J1: 基座俯仰)       关节1模块
│   ├── 21_J1_housing                     J1 主承力壳体
│   ├── 22_J1_output_flange               J1 输出法兰
│   ├── 23_J1_bearing_seat                J1 轴承座
│   ├── 24_J1_cable_routing               J1 线束通道
│   └── 25_J1_service_cover               J1 检修盖
│
├── 30_LINK1_MODULE                       连杆1模块
│   ├── 31_L1_upper_flange                L1 上端法兰
│   ├── 32_L1_shell                       L1 壳体（CFRP/Al）
│   ├── 33_L1_lower_flange                L1 下端法兰
│   ├── 34_L1_cable_channel               L1 内部线束通道
│   └── 35_L1_service_cover               L1 维护盖
│
├── 40_JOINT2_MODULE (J2: 肩部俯仰)       关节2模块
│   ├── 41_J2_housing ~ 45_J2_service_cover  (同 J1 结构)
│
├── 50_LINK2_MODULE                       连杆2模块
│   ├── 51_L2_upper_flange ~ 55_L2_service_cover
│
├── 60_JOINT3_MODULE (J3: 肘部)           关节3模块
│   ├── 61_J3_housing ~ 65_J3_service_cover
│
├── 70_LINK3_MODULE                       连杆3模块
│   ├── 71_L3_upper_flange ~ 75_L3_service_cover
│
├── 80_JOINT4_MODULE (J4: 腕俯仰)         关节4模块
│   ├── 81_J4_housing ~ 85_J4_service_cover
│
├── 90_LINK4_MODULE                       连杆4模块
│   ├── 91_L4_upper_flange ~ 95_L4_service_cover
│
├── A0_JOINT5_MODULE (J5: 腕偏航)         关节5模块
│   ├── A1_J5_housing ~ A5_J5_service_cover
│
├── B0_LINK5_MODULE                       连杆5模块
│   ├── B1_L5_upper_flange ~ B5_L5_service_cover
│
├── C0_JOINT6_MODULE (J6: 腕滚转)         关节6模块
│   ├── C1_J6_housing ~ C5_J6_service_cover
│
├── D0_LINK6_MODULE                       连杆6模块（腕部连接段）
│   ├── D1_L6_upper_flange ~ D5_L6_service_cover
│
├── E0_END_EFFECTOR_INTERFACE             末端执行器接口
│   ├── E1_wrist_flange                   腕法兰（对接 EE-V1/V2）
│   ├── E2_camera_mount                   相机安装座
│   ├── E3_ft_sensor_mount                力/力矩传感器安装座
│   └── E4_capture_center                 捕获中心基准
│
├── F0_GRIPPER_MODULE (来自 vendor, 锁定) 夹爪模块
│   ├── F1_gripper_link                   夹爪基座
│   ├── F2_gripper_left                   左指
│   └── F3_gripper_right                  右指
│
├── G0_STOWAGE_RESTRAINT                  收拢约束机构
│   ├── G07_main_saddle                   主鞍座（V 形定位站）
│   ├── G08_wrist_support                 腕部支撑（浮动鞍座）
│   ├── G09_contact_pad                   接触垫
│   └── G0A_axial_stop                    轴向挡块
│
├── H0_HDRM                               发射保持与释放机构
│   ├── H1_latch_envelope                 锁舌包络
│   ├── H2_release_actuator               释放作动器包络
│   ├── H3_preload_spring                 预紧弹簧
│   ├── H4_status_sensor                  状态传感器
│   └── H5_mechanical_stop                机械止挡
│
└── I0_HARNESS                            线束系统
    ├── I1_connector                      连接器
    ├── I2_cable_routing                  电缆走线
    ├── I3_strain_relief                 应力释放
    └── I4_rotation_envelope              旋转包络
```

### 1.2 结构层级规则

| 层级 | 内容 | 质量权威 | 几何权威 |
|------|------|----------|----------|
| 00 | Master Skeleton | 零实体 | 基准/参数/包络 |
| 10–C0 | 关节模块 | CAD 估计（URDF per-link 为真值） | FreeCAD 原生 |
| 30–D0 | 连杆模块 | CAD 估计（URDF per-link 为真值） | FreeCAD 原生 |
| E0 | 末端接口 | CAD 估计 | FreeCAD 原生 |
| F0 | 夹爪 | URDF（vendor, 锁定） | vendor STL |
| G0 | 收拢约束 | PLACEHOLDER | FreeCAD 原生 |
| H0 | HDRM | PLACEHOLDER | FreeCAD 原生 |
| I0 | 线束 | PLACEHOLDER | FreeCAD 原生 |

---

## 2. 零件 BOM 规划

### 2.1 关节模块 BOM（每关节通用模板）

| 编号 | 零件 | 材料（候选） | 制造方法 | 质量（估计） | 接口 |
|------|------|-------------|----------|-------------|------|
| Jx-01 | 主承力壳体 | Al 7075-T6 | CNC 整体铣削 | PLACEHOLDER | 法兰面×2 |
| Jx-02 | 输出法兰 | Al 7075-T6 | CNC 车铣 | PLACEHOLDER | PCD 螺栓圈 |
| Jx-03 | 轴承座 | Al 7075-T6 / 钢嵌件 | CNC + 压配 | PLACEHOLDER | 轴承外径配合 |
| Jx-04 | 线束通道 | Al 6061-T6 / PTFE 衬 | 铣削 + 注塑 | PLACEHOLDER | 连接器接口 |
| Jx-05 | 检修盖 | Al 6061-T6 | 冲压/铣削 | PLACEHOLDER | 螺钉固定 |

### 2.2 连杆模块 BOM（每连杆通用模板）

| 编号 | 零件 | 材料（候选） | 制造方法 | 质量（估计） | 接口 |
|------|------|-------------|----------|-------------|------|
| Lx-01 | 上端法兰 | Al 7075-T6 | CNC 车铣 | PLACEHOLDER | 关节对接 PCD |
| Lx-02 | 壳体 | CFRP / Al 6061-T6 | 复材铺层 / 挤压 | PLACEHOLDER | 法兰胶接/螺栓 |
| Lx-03 | 下端法兰 | Al 7075-T6 | CNC 车铣 | PLACEHOLDER | 关节对接 PCD |
| Lx-04 | 内部线束通道 | PTFE / 尼龙 | 注塑 / 3D 打印 | PLACEHOLDER | 连接器对接 |
| Lx-05 | 维护盖 | Al 6061-T6 | 冲压 | PLACEHOLDER | 螺钉固定 |

### 2.3 URDF per-link 质量对照（动力学真值，不可覆盖）

| URDF link | 对应结构模块 | URDF 质量 (kg) | CAD 估计质量 | 差异规则 |
|-----------|-------------|:--------------:|:----------:|----------|
| base_link | 10_BASE_MODULE | 0.8366 | PLACEHOLDER | CAD ≤ URDF 10% |
| link1 | 30_LINK1_MODULE | 0.1613 | PLACEHOLDER | CAD ≤ URDF 10% |
| link2 | 50_LINK2_MODULE | 1.3266 | PLACEHOLDER | CAD ≤ URDF 10% |
| link3 | 70_LINK3_MODULE | 0.8353 | PLACEHOLDER | CAD ≤ URDF 10% |
| link4 | 90_LINK4_MODULE | 0.5200 | PLACEHOLDER | CAD ≤ URDF 10% |
| link5 | B0_LINK5_MODULE | 0.3830 | PLACEHOLDER | CAD ≤ URDF 10% |
| link6 | D0_LINK6_MODULE | 0.3663 | PLACEHOLDER | CAD ≤ URDF 10% |
| gripper_link | F1_gripper_link | 0.1818 | vendor | N/A |
| gripper_left | F2_gripper_left | 0.0423 | vendor | N/A |
| gripper_right | F3_gripper_right | 0.0423 | vendor | N/A |
| **总计** | | **4.6956** | | |

> **质量账本规则**：URDF 质量 = 动力学真值（accepted）。CAD 质量 = 工程估计。
> `FREECAD_MASS_REGISTER.yaml` 记录每个零件的 CAD 估计质量、CG、惯量、来源、置信度。
> CAD 质量与 URDF 质量的偏差以 `confidence=low/medium/high` 标注，不回写 URDF。

### 2.4 收拢/HDRM/EE BOM

| 编号 | 零件 | 材料（候选） | 制造方法 | 质量 | 状态 |
|------|------|-------------|----------|------|------|
| G07 | 主鞍座 | Al 7075-T6 + 接触垫 | CNC + 粘接 | PLACEHOLDER | DESIGN_CANDIDATE |
| G08 | 腕部支撑 | Al 7075-T6 + 阻尼件 | CNC + 粘接 | PLACEHOLDER | DESIGN_CANDIDATE |
| G09 | 接触垫 | PTFE / 硅胶 | 注塑 | PLACEHOLDER | DESIGN_CANDIDATE |
| G0A | 轴向挡块 | Al 7075-T6 | CNC | PLACEHOLDER | DESIGN_CANDIDATE |
| H1 | HDRM 锁舌包络 | — | — | PLACEHOLDER | ENVELOPE_ONLY |
| H2 | 释放作动器包络 | — | — | PLACEHOLDER | ENVELOPE_ONLY |
| H3 | 预紧弹簧 | 弹簧钢 | 标准件 | PLACEHOLDER | ENVELOPE_ONLY |
| H4 | 状态传感器 | — | — | PLACEHOLDER | ENVELOPE_ONLY |
| H5 | 机械止挡 | Al 7075-T6 | CNC | PLACEHOLDER | ENVELOPE_ONLY |
| E1 | 腕法兰 | Al 7075-T6 | CNC | PLACEHOLDER | DESIGN_CANDIDATE |
| E2 | 相机安装座 | Al 6061-T6 | CNC | PLACEHOLDER | DESIGN_CANDIDATE |
| E3 | F/T 传感器座 | Al 7075-T6 | CNC | PLACEHOLDER | DESIGN_CANDIDATE |
| E4 | 捕获中心基准 | — | — | — | DATUM_ONLY |

---

## 3. 接口控制文档 (ICD) 参数表

### 3.1 航天器—臂根接口 IF-RM-002

| 参数 | 值 | 来源 | 状态 |
|------|-----|------|------|
| 安装面尺寸 | 160 × 160 mm | arm_mount_v1.yaml | FROZEN |
| 中央凸台直径 | Ø100 mm | arm_mount_v1.yaml | FROZEN |
| 凸台高度 | 15 mm | arm_mount_v1.yaml | FROZEN |
| 适配板厚度 | 12 mm | arm_mount_v1.yaml | FROZEN |
| T_SM 动力学轨 | 185.25 mm | frame_tree_v1.yaml | FROZEN (dynamics) |
| T_SM 显示轨 | 198.0 mm | V2.2 native | FROZEN (display) |
| 双轨差值 | 12.75 mm | accepted_chain | DUAL_TRACK_EXPLICIT |
| R_SM | Ry(+90°) | frame_tree_v1.yaml | FROZEN |
| 安装面基准 | 前端框面 X=183 mm | V2.2 native | FROZEN |
| 纵梁轴 | ±101.65 mm | V2.2 native | FROZEN |
| 主结构参考面 | ±110.15 mm | V2.2 native | FROZEN |
| 可拆面板面 | ±113.15 mm | V2.2 native | FROZEN |
| PCD（螺栓圈） | PLACEHOLDER | — | F3-P1 冻结 |
| 螺栓规格 | PLACEHOLDER | — | F3-P1 冻结 |
| 定位销 | PLACEHOLDER | — | F3-P1 冻结 |

### 3.2 关节接口通用合同（每关节 J1–J6）

每个 revolute 关节必须定义以下 ICD 字段：

```yaml
JOINT_INTERFACE_CONTROL_DOCUMENT:
  joint_name: Jx
  joint_type: revolute
  axis: [ax, ay, az]           # accepted URDF axis
  origin_xyz_m: [ox, oy, oz]  # accepted URDF origin
  origin_rpy_rad: [rx, ry, rz] # accepted URDF rpy
  lower_limit_rad: qmin        # accepted URDF lower
  upper_limit_rad: qmax        # accepted URDF upper
  parent_link: <link_name>
  child_link: <link_name>
  interface:
    pcd_mm: PLACEHOLDER         # 螺栓分布圆直径
    bolt_count: PLACEHOLDER     # 螺栓数量
    bolt_spec: PLACEHOLDER      # 螺栓规格 (e.g. M3×0.5)
    dowel_pin_count: 2          # 定位销数量
    dowel_pin_diameter_mm: PLACEHOLDER
    datum_plane: parent_joint_origin_plane
    bearing_axis: joint_axis
    bearing_type: PLACEHOLDER   # 轴承型号
    bearing_id_mm: PLACEHOLDER
    bearing_od_mm: PLACEHOLDER
    load_direction: PLACEHOLDER # 承载方向
  cable:
    connector_type: PLACEHOLDER
    routing_envelope_mm: PLACEHOLDER
    strain_relief: PLACEHOLDER
    max_rotation_deg: [qmin_deg, qmax_deg]
    clearance_to_axis_mm: PLACEHOLDER
```

### 3.3 accepted URDF 关节参数（冻结输入，不可修改）

| Joint | Origin xyz (m) | Origin rpy (rad) | Axis | Lower (rad) | Upper (rad) |
|-------|-----------------|-------------------|------|:-----------:|:-----------:|
| joint1 | [-0.0000842, 0, 0.08465] | [0, 0, 0] | [0,0,1] | -2.8 | 2.8 |
| joint2 | [0.020084, 0.031625, 0.05555] | [-1.5708, 0, 0] | [0,0,-1] | -3.14 | 0 |
| joint3 | [-0.264, 0, 0] | [0, 0, 0] | [0,0,1] | -3.14 | 0 |
| joint4 | [0.2426, -0.054, -0.001625] | [0, 0, 0] | [0,0,1] | -1.87 | 1.57 |
| joint5 | [0.078308, -0.0375, -0.03] | [-1.5708, 0, 0] | [0,0,1] | -1.57 | 1.57 |
| joint6 | [0.023692, 0, 0.04] | [0, 1.5708, 0] | [0,0,1] | -3.14 | 3.14 |

### 3.4 连杆长度参数（从 URDF origin 推导）

| 连杆 | 有效长度 (mm) | 说明 |
|------|:------------:|------|
| base→J1 | 84.65 (Z) | base_link 到 joint1 原点 |
| J1→J2 | 55.55 (Z) + 31.625 (Y) + 20.084 (X) | joint1 到 joint2 |
| L1 (J2→J3) | 264 (X) | joint2 到 joint3 |
| L2 (J3→J4) | 242.6 (X) + 54 (Y) + 1.625 (Z) | joint3 到 joint4 |
| L3 (J4→J5) | 78.308 (X) + 37.5 (Y) + 30 (Z) | joint4 到 joint5 |
| L4 (J5→J6) | 23.692 (X) + 40 (Z) | joint5 到 joint6 |
| L5 (J6→gripper) | 159.71 (Z) | joint6 到 gripper_link |

---

## 4. 载荷路径图

### 4.1 在轨作业载荷路径

```
末端/各连杆惯性与接触载荷
    │
    ├─ 末端执行器 (E0)
    │   └─ F/T 传感器 → 腕法兰 (E1) → link6 (D0)
    │       └─ joint6 (C0) → link5 (B0)
    │           └─ joint5 (A0) → link4 (90)
    │               └─ joint4 (80) → link3 (70)
    │                   └─ joint3 (60) → link2 (50)
    │                       └─ joint2 (40) → link1 (30)
    │                           └─ joint1 (20) → base_link (10)
    │                               └─ IF-RM-002 (12_base_flange)
    │                                   └─ 适配板 160×160×12
    │                                       └─ 载荷扩散板/凸台
    │                                           └─ 前端框 (X=183)
    │                                               └─ 四纵梁 (±101.65)
    │                                                   └─ 舱段横框
    │                                                       └─ 整星刚体
    │                                                           └─ 姿控系统
    └─ 在轨载荷六分量: Fx/Fy/Fz/Mx/My/Mz = PLACEHOLDER (UNSOURCED_BLOCKED)
```

### 4.2 发射收拢载荷路径

```
发射振动/冲击惯性载荷
    │
    ├─ B601 收拢臂惯性
    │   └─ 各收拢支承接触区 (G07/G08/G09)
    │       ├─ G07 主鞍座 → 命名主框/纵梁硬点
    │       ├─ G08 腕部支撑 → 命名主框/纵梁硬点
    │       └─ G0A 轴向挡块 → 命名主框硬点
    │           └─ HDRM (H0) 预紧闭合
    │               ├─ H1 锁舌 → H3 预紧弹簧 → H5 机械止挡
    │               └─ H2 释放作动器 (发射前不承载)
    │                   └─ 横梁/前任务面主结构
    │                       └─ 纵梁/横框
    │                           └─ 部署器凸耳/导轨接口
    │
    └─ 注意：根部安装法兰仅承担在轨支路
        发射载荷必须绕过谐波/QDD 减速器
        不能默认整臂惯性沿关节串联传回根部
```

### 4.3 在轨装配接触载荷路径

```
导向锥/销/孔接触
    │
    └─ 末端工具与柔顺单元 (E0 + EE-V2 compliant joint)
        └─ B601 (D0→10)
            └─ 臂根接口 IF-RM-002
                └─ 载荷扩散区
                    └─ 前框与四纵梁
                        └─ 整星姿控
```

### 4.4 载荷状态汇总

| 工况 | 载荷六分量 | 边界刚度 | 一阶模态 | 状态 |
|------|-----------|----------|---------|------|
| 发射收拢 | PLACEHOLDER | PLACEHOLDER | PLACEHOLDER Hz | UNSOURCED_BLOCKED |
| 在轨作业 | PLACEHOLDER | PLACEHOLDER | PLACEHOLDER Hz | UNSOURCED_BLOCKED |
| 装配接触 | PLACEHOLDER | PLACEHOLDER | — | ASM00_AG0_BLOCKED |
| 地面搬运 | PLACEHOLDER | — | — | UNSOURCED_BLOCKED |

---

## 5. F3 阶段设计冻结方案

### 5.1 F3 子阶段与 Gate

```
F3-P0 (本文件) — 机械架构冻结
    │
    ├─ Gate F3-G0: 架构冻结审查
    │   ✓ 结构树完整
    │   ✓ ICD 字段定义
    │   ✓ 载荷路径图
    │   ✓ URDF 映射
    │   ✓ 质量账本模板
    │
F3-P1 — 关节 + 连杆制造级建模
    │
    ├─ Gate F3-G1: 关节 ICD 冻结
    │   ✓ 6 个 revolute 关节 PCD/螺栓/定位销/轴承
    │   ✓ 线束通道包络
    │   ✓ 限位验证 (qmin/qmax 不干涉)
    │
    ├─ Gate F3-G2: 连杆制造报告
    │   ✓ 每连杆 LINK_MANUFACTURING_REPORT.md
    │   ✓ CAD 质量登记
    │   ✓ 刚度方向标注
    │   ✓ 模态候选
    │
F3-P2 — 收拢与释放机构
    │
    ├─ Gate F3-G3: 收拢约束闭合
    │   ✓ G07 V 形定位站几何
    │   ✓ G08 浮动鞍座几何
    │   ✓ 接触垫/预紧/阻尼
    │   ✓ 6DOF 载荷路径到主结构
    │   ✓ STOW_Z_LIMIT 释放
    │
    ├─ Gate F3-G4: HDRM 功能设计
    │   ✓ HDRM_FUNCTIONAL_DESIGN.md
    │   ✓ latch/release/preload/sensor/stop
    │   ✓ Engineering Candidate (非飞行型号)
    │
F3-P3 — 末端执行器
    │
    ├─ Gate F3-G5: EE-V1 接口级
    │   ✓ wrist flange / camera mount / F/T sensor / capture center
    │
    ├─ Gate F3-G6: EE-V2 柔顺捕获
    │   ✓ compliant joint / passive damping / guide cone
    │
F3-P4 — 动力学/结构同步
    │
    ├─ Gate F3-G7: 质量账本闭合
    │   ✓ FREECAD_MASS_REGISTER.yaml 填充
    │   ✓ CAD vs URDF 偏差 < 10%
    │
    ├─ Gate F3-G8: 柔性接口模型
    │   ✓ B601_FLEX_MODEL.yaml
    │   ✓ link stiffness / joint stiffness / base compliance / support stiffness
    │
    ├─ Gate F3-G9: 模态分析
    │   ✓ Case 1: 臂展开 base fixed, 前 10 阶
    │   ✓ Case 2: 自由漂浮 spacecraft+arm, 前 10 阶
```

### 5.2 F3 各线并行推进顺序

```
F3-A 机械臂本体深化 ──── F3-P1 (J1-J6 + L1-L6)
        │
        │ (ICD 冻结后)
        ↓
F3-B 航天器接口深化 ──── F3-P1 (IF-RM-002 PCD/螺栓冻结)
        │
        ├──→ F3-C 收拢/释放 ── F3-P2 (G07/G08/HDRM)
        │
        └──→ F3-D 末端执行器 ── F3-P3 (EE-V1/V2)
        
F3-E 动力学/结构同步 ── F3-P4 (每完成一个结构即更新)
```

### 5.3 F3 前置条件检查

| 检查项 | 状态 | 备注 |
|--------|------|------|
| FreeCAD 工具链稳定 | PASS (F0-F2) | 用户确认 |
| accepted URDF 冻结 | PASS | SHA-256 已登记 |
| frame_tree_v1 冻结 | PASS | nominal_frozen_v1 |
| mass_inertia_budget_v1 | PASS (low confidence) | 可用于 F3 估计 |
| 载荷路径拓扑确认 | PASS (CONFIRMED_TOPOLOGY_ONLY) | 物理值 PLACEHOLDER |
| 载荷六分量 | UNSOURCED_BLOCKED | FEA 前必须解决 |
| T_SM 双轨 | DUAL_TRACK_EXPLICIT | 12.75mm 差值不可隐藏 |
| STOW_Z_LIMIT | UNKNOWN | F3-P2 必须释放 |
| 实物称重 | HOLD | confidence=medium |
| 部署器/发射 ICD | MISSING | 一阶模态目标无法定 |

### 5.4 F3 设计纪律

1. **接口先行**：每个零件建模前，其上下游 ICD 必须已冻结。
2. **载荷路径不跨阶段**：F3-P1 的关节几何不消费 F3-P2 的收拢载荷。
3. **PLACEHOLDER 不当零**：任何 UNSOURCED_BLOCKED 值不得被当作数值输入。
4. **CAD 质量不回写 URDF**：CAD 估计质量仅进 `FREECAD_MASS_REGISTER.yaml`。
5. **材料/公差/紧固件随几何冻结**：每个零件冻结时必须同时冻结材料、公差、紧固件（至少候选）。
6. **不创建顶层装配**：在 F3-P1/P2/P3 全部 PASS 前，不创建 `SPACECRAFT_TOP_ASSEMBLY.FCStd`。

### 5.5 F3 输出物清单

| 输出物 | 格式 | 所在目录 | 对应 Gate |
|--------|------|----------|----------|
| 本文件（架构冻结） | .md | F3_manufacturing_arm/ | F3-G0 |
| 关节 ICD（×6） | .yaml | F3_manufacturing_arm/icd/ | F3-G1 |
| 连杆制造报告（×6） | .md | F3_manufacturing_arm/reports/ | F3-G2 |
| 收拢约束设计 | .md + .FCStd | F3_manufacturing_arm/stowage/ | F3-G3 |
| HDRM 功能设计 | .md | F3_manufacturing_arm/hdrm/ | F3-G4 |
| EE 设计 | .md + .FCStd | F3_manufacturing_arm/end_effector/ | F3-G5/G6 |
| CAD 质量登记 | .yaml | F3_manufacturing_arm/ | F3-G7 |
| 柔性接口模型 | .yaml | F3_manufacturing_arm/ | F3-G8 |
| 模态分析报告 | .md | F3_manufacturing_arm/analysis/ | F3-G9 |

---

## 6. 柔性接口模型模板 (F3-P4 预登记)

```yaml
# B601_FLEX_MODEL.yaml — F3-P4 冻结时填充
# 从 F3 开始建立，每完成一个结构即更新

link_stiffness:
  link1: { kx: PLACEHOLDER, ky: PLACEHOLDER, kz: PLACEHOLDER,
           ktx: PLACEHOLDER, kty: PLACEHOLDER, ktz: PLACEHOLDER }
  link2: { kx: PLACEHOLDER, ky: PLACEHOLDER, kz: PLACEHOLDER,
           ktx: PLACEHOLDER, kty: PLACEHOLDER, ktz: PLACEHOLDER }
  link3: { ... }
  link4: { ... }
  link5: { ... }
  link6: { ... }

joint_stiffness:
  joint1: { kt: PLACEHOLDER_Nm_per_rad }  # 关节扭转刚度
  joint2: { kt: PLACEHOLDER }
  joint3: { kt: PLACEHOLDER }
  joint4: { kt: PLACEHOLDER }
  joint5: { kt: PLACEHOLDER }
  joint6: { kt: PLACEHOLDER }

base_compliance:
  kx: PLACEHOLDER  # N/m
  ky: PLACEHOLDER
  kz: PLACEHOLDER
  ktx: PLACEHOLDER  # Nm/rad
  kty: PLACEHOLDER
  ktz: PLACEHOLDER

support_stiffness:  # 收拢支撑刚度
  G07: { kn: PLACEHOLDER, kt: PLACEHOLDER }  # 法向/切向
  G08: { kn: PLACEHOLDER, kt: PLACEHOLDER }
  HDRM: { kp: PLACEHOLDER }  # 预紧刚度

# 来源标注
source_rule: >-
  所有 PLACEHOLDER 值在 F3-P4 填充时必须标注来源
  (FEA/实验/文献/估计) 和不确定度。
  sim_11 的接触窗 T_c=20ms 为 PROVISIONAL，
  不直接进入此模型。
```

---

## 7. 质量账本模板 (F3-P4 预登记)

```yaml
# FREECAD_MASS_REGISTER.yaml — F3-P4 冻结时填充
# CAD 质量 = 工程估计; URDF 质量 = 动力学真值

component: B601_BASE_HOUSING
mass_kg: PLACEHOLDER
cg_m: [PLACEHOLDER, PLACEHOLDER, PLACEHOLDER]
inertia_kgm2:
  Ixx: PLACEHOLDER
  Iyy: PLACEHOLDER
  Izz: PLACEHOLDER
source: FreeCAD_material_estimate
confidence: low  # low / medium / high
urdf_link: base_link
urdf_mass_kg: 0.8366
deviation_pct: PLACEHOLDER  # (CAD - URDF) / URDF * 100
note: >-
  CAD 质量不含电机/减速器/轴承内圈。
  URDF 质量含 DevArm 全部惯量集。
  偏差来源 = CAD 未建模内部器件。

# ... 每个零件重复此模板 ...
```

---

## 8. 与已有仿真链的关系

| 仿真 | 当前输入 | F3 后输入变化 | 影响 |
|------|---------|-------------|------|
| sim_05 | accepted URDF (只读) | 无变化 | URDF 不动 |
| sim_10 | accepted URDF + scan_v0 | 无变化 | URDF 不动 |
| sim_11 | accepted URDF + coupled_scene | 无变化 | URDF 不动 |
| sim_12 | accepted URDF + strategies | 无变化 | URDF 不动 |
| F3 模态 (新) | CAD 几何 + 材料 | F3-P4 新建 | 新仿真，不消费 URDF |
| F3 FEA (新) | CAD 几何 + 载荷 | F3-P4 新建 | 需载荷六分量先解封 |

> **关键边界**：F3 的 CAD 质量、模态、FEA 结果不得回写 accepted URDF。
> 如果 CAD 质量偏差超过 10%，触发 `F3_MASS_DEVIATION_REVIEW`，但不自动修改 URDF。

---

## 9. 未解决问题（F3-P0 不消解）

1. **载荷六分量 UNSOURCED_BLOCKED**：在 FEA 可运行前必须解决。需要至少给出名义运动、急停、极限关节加速度、捕获瞬态和失效安全回撤工况。
2. **T_SM 双轨 12.75mm**：F3 几何采用显示轨 198.0mm；动力学采用 185.25mm。两者差值不可隐藏。
3. **STOW_Z_LIMIT UNKNOWN**：F3-P2 必须用真实 B601 几何释放。
4. **实物称重 HOLD**：confidence=medium，F3 全程保持。
5. **部署器/发射 ICD MISSING**：一阶模态目标无法定，F3 模态分析只能给相对值。
6. **帆板质量占位**：0.348 kg/panel 差 5-10×，影响整星模态，但不影响臂本体 F3。

---

## 10. 授权

```
F3_P0_ARCHITECTURE_FREEZE_PROPOSAL
  → 待人工审查
  → 审查通过后状态改为 F3_P0_ARCHITECTURE_FROZEN
  → 授权 F3-P1 启动
```

本文件不授权：
- 任何 .FCStd 几何创建
- 任何 accepted URDF 修改
- 任何载荷值从 PLACEHOLDER 升级为数值
- 任何飞行/制造/采购声明
- 顶层航天器装配创建
