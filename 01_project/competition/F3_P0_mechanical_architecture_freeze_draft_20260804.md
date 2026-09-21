# F3-P0 B601 制造级机械架构冻结草案

> 文档编号：`F3-P0-DRAFT-20260804`
> 生成 UTC：2026-08-04
> 状态：`PDR_STAGE_PLANNING_DRAFT` — **不构成 CAD 授权，不启 CAD_AUTHORING**
> 路径裁决：用户在状态差异报告后选择**路径 A（状态校正 + 草案）**
> 真值基线：`AGENTS.md` / `spacecraft-mechanical-design-agent.md` / `asm_00_gate_check.json` / `phase0_completion_record.json`
> 上一阶段：`NATIVE01_PHASE1_BUILT_PASS`（V2_3 SolidWorks 原生，2026-07-27 冻结）

---

## 0. 状态校正（必读，否则后续章节前提错位）

### 0.1 用户 F3 启动前提与仓库机器状态的差异

| 检查项 | 用户前提 | 仓库实际 | 处置 |
|---|---|---|---|
| FreeCAD `.FCStd` 文件 | 已存在并验证 | **0 个**（仅 80_third_party/librepcb 等无关第三方） | 路径 A：不依赖 FreeCAD |
| F0/F1/F2 阶段报告 | 已 PASS | **0 份**，全文搜索零命中 | 路径 A：不引用 F0-F2 |
| CAD 工具链 | FreeCAD 制造级 | SolidWorks V2_3_NATIVE_INTEGRATION（47 零件 + 8 子装配） | 以 SolidWorks 真值继续 |
| `spacecraft-mechanical-design-agent.md` | F3 已授权 | `CAD_AUTHORING：当前禁用` | 路径 A：本草案仅在 `V2_ARCHITECTURE` / `CAD_ENTRY_REVIEW` 模式下产出 |
| `.codex/AGENTS.md` | F3 已授权 | `V2 CAD NOT_AUTHORIZED`；HAG-A 前 `PLANNED_NOT_AUTHORIZED` | 同上 |
| `asm_00_gate_check.json` | F3 已授权 | `HAG-A: ABSENT`；`scientific_execution_authorized: false` | F3-P0 不动 asm_00 裁决 |

### 0.2 本草案的允许边界

允许：
- 阅读、引用、对照现有 V2_3 SolidWorks 文件、URDF、配置、Gate JSON；
- 产出 PDR 阶段架构规划文档（本文）；
- 在文档中显式登记未来 F3-A..F3-E 的工作项、参数缺口、接口冻结需求；
- 标注"待 HAG-F3 授权"的具体动作清单。

禁止（本草案不做）：
- 创建、修改、保存任何 `.SLDPRT` / `.SLDASM` / `.FCStd` / `.step` / URDF / config / Gate JSON；
- 推断或捏造材料、板厚、紧固件、载荷、刚度、强度、模态数值；
- 自签 HAG-F3 或任何下一阶段 Gate；
- 改写 `20_engineering/config/geometry/`、`30_simulation/`、`40_evidence/` 冻结内容；
- 把"路径 A 草案"当作"F0-F2 PASS"的证据链入口。

### 0.3 升级路径

本草案在以下任一条件满足后才可升级为 F3-P1 实施合同：
1. 真实 F0-F2 FreeCAD 工作入库并通过哈希核验（路径 B）；
2. 用户签发具名 `HAG-F3-P1-CAD_AUTHORING.yaml` 显式授权 SolidWorks 或 FreeCAD 原生改写（路径 C 的 P1 版本）；
3. HAG-A 落地后 asm_00 解除 AG0 阻塞（影响 F3-C 接触资格子线）。

在此之前，F3-A..F3-E 所有"建模"动作为 `PLANNED_NOT_AUTHORIZED`。

---

## 1. 当前 V2_3 SolidWorks 原生装配真值

### 1.1 顶层装配树（已冻结，源=V2_2_NATIVE，108 文件 sha256 锁定）

```
Space_Embodied_Service_Spacecraft_V2_2.SLDASM
├── 00_Master_Skeleton_V2_2.SLDPRT            18 基准面 + 3D 包络草图 + 34 参数属性（零实体）
├── 01_Primary_Structure_V2_2.SLDASM          (7 子装配)
│   ├── Front_End_Frame / Rear_End_Frame      环框（4×17×17 横梁，纵梁间端接）
│   ├── Front_Transverse_Frame                X 119..125
│   ├── Mid_Transverse_Frame_1 / _2           X ±(58..64)
│   ├── Longerons_4X.SLDPRT                   4 根 17×17，角点 ±101.65，X -183..183
│   └── Equipment_Decks.SLDASM (3)            前/中/后舱甲板 z -40..-36
├── Removable_Panels.SLDASM (6)               ±Y 前后分缝 ×4 + ±Z ×2，3mm，外表面齐平 113.15
├── 02_B601_Mount_and_Load_Path.SLDASM (8)    扩散板→前端框→法兰→160×160×12 适配板→Ø110 导向凸台
│                                             + 双载荷桥 + 线束通道 + 内维修盖
├── 03_B601_Three_Representations.SLDASM      三表示总装（部分已建，见 §1.2）
├── 04_ARM_STOW_SUPPORT.SLDASM (5)            上臂/前臂/腕鞍座（接触高 234.77/248.49/253.80 实测）
│                                             + 发射锁参考 + 释放净空包络
├── 05_Solar_Array_Root_Left.SLDASM (9)       SC 侧支座 + 前后铰链耳（带 Ø8.4 销孔）+ 销包络
└── 06_Solar_Array_Root_Right.SLDASM (9)      + 翼板侧叶片 + 机械止挡 + HDRM 座 + 释放机构包络
                                              + 线束服务环
```

零件 47 个、装配 8 个、断链 0、重复装入 0。每个零件带 `ROLE / STATUS / OWNER / PARENT_ASSEMBLY / GEOMETRY_AUTHORITY / MASS_AUTHORITY / STRENGTH_AUTHORITY / BLOCKED_CONSUMERS` 自定义属性。

### 1.2 B601 三表示当前状态（关键）

| 表示 | 目录 | 状态 | 文件数 | 备注 |
|---|---|---|---|---|
| `B601_KINEMATIC_PROXY` | `03_B601_Three_Representations/B601_KINEMATIC_PROXY/` | **已建** | 21 | 10 × `B601_PROXY_*.SLDPRT` + 10 × `PROXY_*.SLDPRT`（双命名） + 1 SLDASM；运动学代理，来自 accepted URDF 几何 |
| `B601_MASS_SURROGATE` | `03_B601_Three_Representations/B601_MASS_SURROGATE/` | **已建** | 11 | 10 × `MASS_*.SLDPRT` + 1 SLDASM；质量代理，URDF inertial 包络化 |
| `B601_STOWED_HIFI` | `03_B601_Three_Representations/B601_STOWED_HIFI/` | **空目录** | 0 | `phase0_completion_record.json` 明示 `CONFIRMED_NOT_CREATED`；待导入 35 MB 厂商 STEP `reBot_B601_DM_v1.1_20260425.step`，该操作有失败史（headless LoadFile4 无返回，215 s 超时） |

**三表示策略**（来自任务书）：HIFI = 真实厂商几何用于收拢态可视化与干涉；KINEMATIC_PROXY = FK 碰撞体用于配置切换；MASS_SURROGATE = URDF 质量分布的体积占位，**不参与质量真值**（mass=EXCLUDED，URDF 4.6956 kg 唯一）。

### 1.3 已冻结的关键数值（引用时勿改）

| 项 | 值 | 来源 | 备注 |
|---|---|---|---|
| `T_SM` 名义冻结 v1 | t=[185.25,0,0] mm，R=R_y(+90°) | `coordinate_frame_definition_v0.md` §3.1 | 动力学轨；显示轨 `MOUNT_FACE_X=198`，双轨冲突 `T_SM_TRACK_CONFLICT` 未裁决 |
| 适配板尺寸 | 160×160×12 mm，Ø100 中央凸台高 15 mm | `arm_mount_v1.yaml` / V22 报告 §1 | |
| B601 总动力学质量 | 4.6956 kg（臂 4.4293 + 夹爪 0.2665） | `arm_b601_v1.yaml` | HYBRID 来源；URDF 唯一真值，CAD 不得覆盖 |
| 服务星 12U 质量 | 24.0 kg（v0）/ 23.30 kg（v1 bus only） | `mass_inertia_budget_v1.csv` | `confidence: low` |
| 目标星质量 | 22.0 kg | 同上 | `confidence: low` |
| 碎片质量 | 150.0 kg | 同上 | `confidence: low` |
| 收拢向量 v3 | clock=25°，q_deg=[145.572,-168.000,-57.000,-41.143,-20.954,-3.000] | `O13_STOW_VECTOR_V3_REPORT.md` | `STOW_VECTOR_STATUS=CANDIDATE_HOLD`，几何间隙 15.56 mm PASS，接触资格未定 |
| 三鞍座站位 | Aft X[-20,0] z=261.08 / Mid X[80,100] z=214.92 / Fwd X[160,180] z=209.42 | `design/o13_saddle_stations.json` | 塔高 147.93/101.77/96.27，全 ≤150 mm |
| C5 收拢超宽 | 238.3 mm > 226.3 mm，超 12.0 mm | `CODEX_CONTINUATION_RECONCILIATION.md` §3 | `NEGATIVE_PRESERVED_NOT_CLOSED`，禁止隐藏/减薄/移动制造假通过 |
| 翼根机构下限宽 | 302.3 mm（双侧达 \|Y\|=151.15） | 同上 | 不可消解，登记入 Master Skeleton |
| 收拢态 Z 上限 | UNKNOWN | V22 报告 §4.1 | 臂顶 z=359.02 高出整星盒顶 245.87 mm，无判据可判合规 |

### 1.4 已登记的未消解 HOLD

1. `T_SM_TRACK_CONFLICT` — 动力学 185.25 vs 显示 198，未裁决；
2. `STOW_VECTOR_STATUS = CANDIDATE_HOLD` — 几何 PASS 但接触资格未定（垫材料、预紧、发射载荷、B601 壳体承载能力）；
3. `STOW_Z_LIMIT_REFERENCE = UNKNOWN` — 收拢态高度无判据；
4. `B601_STOWED_HIFI` 未建 — 厂商 STEP 导入失败史；
5. C5 翼板超宽 12 mm — 翼板本体不在 V2_3 范围；
6. 翼根机构下限宽 302.3 mm — 不可消解；
7. 25° 时钟角 — 人工批准但比较配置并存；
8. `O11 ARM-STOW X 站位差异` — Codex [40,90]/[-150,-110] vs V2_3 [10,60]/[-100,-40]，随时钟角裁决；
9. 材料、强度、公差、紧固件、热、FEA、动力学 — 全部未定义/未运行；
10. `HAG-A ABSENT` — asm_00 AG0 BLOCKED，影响 F3-C 接触资格物理分支。

---

## 2. F3 愿景与 V2_3 现实的映射

用户 F3 愿景分 5 条并行线（F3-A..F3-E）。下表把每条线映射到 V2_3 现状，识别"已存在 / 部分存在 / 全新"。

| F3 子线 | 用户目标 | V2_3 现状 | 缺口性质 | F3-P0 处置 |
|---|---|---|---|---|
| **F3-A** B601 本体深化 | 关节壳体 + 输出承载 + 关节接口 + 线束 | KINEMATIC_PROXY（URDF 几何）+ MASS_SURROGATE（URDF 质量包络）；HIFI 空目录 | **HIFI 未建**；无关节壳体/轴承座/螺栓圈/线束通道 | §3 结构树 + §4 BOM + §5 参数表，标注待授权 |
| **F3-B** 连杆制造设计 | 壳体 + 端接 + 加强筋 + 线束通道 + 维护盖 | KINEMATIC_PROXY link1..6 为 URDF mesh 包络，无制造特征 | **无制造级连杆** | §3 结构树，标注为 F3-A 完成后顺序项 |
| **F3-C** 收拢/释放机构 | G07 主鞍座 + G08 腕部支撑 + 6DOF 载荷路径 | `04_ARM_STOW_SUPPORT` 已有 Fwd/Mid/Aft 鞍座 + 发射锁参考 + 释放净空包络 | **接触垫/预紧/阻尼/二级止挡未定义**；CANDIDATE_HOLD | §6 载荷路径图，标注接触资格待 HAG-A + 实测 |
| **F3-D** HDRM | latch + 释放作动器 + 预紧弹簧 + 状态传感器 + 机械止挡 | 帆板侧 HDRM 已有（HDRM_Base/Rod ×2 每侧）；**机械臂侧 HDRM 无** | **机械臂收拢 HDRM 全新** | §3 结构树标注为 F3-C 完成后顺序项；功能包络而非飞行型号 |
| **F3-E** 末端执行器 | EE-V1 接口级 / V2 柔顺捕获 / V3 非合作目标 | URDF gripper_link + left/right fingers（运动学）；无 F/T 法兰/相机座/柔顺关节 | **EE-V1/V2/V3 全新** | §3 结构树标注为 F3-A/B 完成后顺序项；V1+V2 为比赛优先 |

**关键发现**：用户的 F3 愿景并非"从零开始"，而是把 V2_3 的"运动学/质量代理 + 结构骨架"升级为"制造级数字样机"。最大的单点缺口是 **B601_STOWED_HIFI 未建**——这是 F3-A/B/C/D/E 所有子线的高保真几何前提。

---

## 3. 交付物 1：B601 制造级结构树（规划态）

按用户指定的"载荷路径 → 接口 → 关节 → 连杆 → 末端 → 控制模型"顺序组织。**本结构树为规划态，不创建任何文件**。

### 3.1 B601 制造级结构树（拟建，标注现有/新建）

```
B601_MANUFACTURING_GRADE (拟建顶层，F3-P1 授权后创建)
│
├── [EXISTING] 00_Master_Skeleton_V2_2.SLDPRT
│   └── 继承 V2_3，零实体，34 参数属性；F3 增量：关节限位/线束包络/接触垫参数
│
├── [EXISTING - PARTIAL] 01_Primary_Structure (服务星主结构，非 B601)
│   └── 继承 V2_3；F3 不动主结构，仅核对 B601 接口面
│
├── [EXISTING] 02_B601_Mount_and_Load_Path (8 件)
│   ├── Adapter_Plate.SLDPRT                    160×160×12 适配板
│   ├── Central_Boss.SLDPRT                     Ø100×15 中央凸台
│   ├── Spacecraft_Flange.SLDPRT                航天器侧法兰
│   ├── Load_Spreading_Frame.SLDPRT             载荷扩散板
│   ├── Load_Bridge_Left/Right.SLDPRT           双载荷桥
│   ├── Harness_Passage.SLDPRT                  线束通道
│   └── Maintenance_Access_Cover.SLDPRT         维修盖
│   F3 增量：螺栓圈/定位销/PCD/基准面（参数表 §5）
│
├── [TO_BUILD] 03_B601_Manufacturing_Body (B601 本体深化，F3-A 主体)
│   │
│   ├── [TO_BUILD] B601_STOWED_HIFI (高保真，35 MB 厂商 STEP 导入)
│   │   └── 拟来自 reBot_B601_DM_v1.1_20260425.step
│   │
│   ├── [TO_BUILD] Joint_Housing_Assembly ×6 (J1..J6)
│   │   ├── Joint_Housing_Main.SLDPRT          主承力壳体（Al 7075-T6 候选）
│   │   ├── Joint_Reinforcement_Rib.SLDPRT      加强筋
│   │   ├── Joint_Mounting_Boss.SLDPRT          安装凸台
│   │   ├── Joint_Flange.SLDPRT                 法兰面
│   │   ├── Joint_Inspection_Cover.SLDPRT       检修盖
│   │   ├── Joint_Thermal_Mount_Area.SLDPRT     热控安装区域
│   │   ├── Bearing_Seat.SLDPRT                 轴承座
│   │   ├── Output_Flange.SLDPRT                输出法兰
│   │   ├── Bolt_Circle.SLDPRT (参考)           螺栓圈
│   │   └── Positioning_Feature.SLDPRT (参考)   定位结构
│   │
│   ├── [TO_BUILD] Output_Bearing_Structure ×6
│   │   载荷路径：电机 → 减速器 → 输出轴 → 轴承 → 法兰 → 连杆
│   │   └── Bearing_Housing / Output_Shaft / Bearing_Set / Flange_Bolt_Pattern
│   │
│   ├── [TO_BUILD] Joint_Interface ×6
│   │   └── 每关节输出 JOINT_INTERFACE_CONTROL_DOCUMENT（§5 参数表）
│   │
│   └── [TO_BUILD] Joint_Wiring ×6
│       ├── Connector.SLDPRT
│       ├── Cable_Routing_Channel.SLDPRT
│       ├── Strain_Relief.SLDPRT
│       └── Joint_Rotation_Envelope.SLDPRT（验证 qmin/qmax 下线束不被拉伸/折死/穿轴）
│
├── [TO_BUILD] 04_Link_Manufacturing (F3-B，10 连杆制造级)
│   │   注：B601 6R 有 6 link（base_link + link1..6 + gripper_link）；用户"10 links"对应 V2_3 已含的 10 carrier + J00-J09，需在 F3-P1 核对数量口径
│   │
│   ├── Link_Shell.SLDPRT ×N              壳体（CFRP/Al 候选）
│   ├── Link_Upper_Flange.SLDPRT ×N       上端金属端接
│   ├── Link_Lower_Flange.SLDPRT ×N       下端金属端接
│   ├── Link_Reinforcement_Rib.SLDPRT ×N  加强筋
│   ├── Link_Harness_Channel.SLDPRT ×N    内部线束通道
│   └── Link_Maintenance_Cover.SLDPRT ×N  维护盖
│   每连杆输出 LINKxx_MANUFACTURING_REPORT.md（材料/质量/URDF 对应/制造方法/接口/刚度/模态候选/维护）
│
├── [EXISTING - PARTIAL] 05_ARM_STOW_SUPPORT (F3-C，5 件已建，需补接触资格)
│   ├── Aft_Saddle.SLDPRT                    X[-20,0] z=261.08 塔高 147.93
│   ├── Mid_Saddle.SLDPRT                     X[80,100] z=214.92 塔高 101.77
│   ├── Fwd_Saddle.SLDPRT                     X[160,180] z=209.42 塔高 96.27
│   ├── Launch_Lock_Interface_Reference.SLDPRT   发射锁参考
│   └── Release_Clearance_Envelope.SLDPRT        释放净空包络
│   F3 增量（G07/G08）：
│   ├── [TO_BUILD] Guide_Cone.SLDPRT              导向锥面
│   ├── [TO_BUILD] Contact_Pad.SLDPRT             接触垫（材料待定）
│   ├── [TO_BUILD] Lateral_Limiter.SLDPRT         横向限位
│   ├── [TO_BUILD] Axial_Hard_Stop.SLDPRT         轴向挡块
│   ├── [TO_BUILD] Preload_Mechanism.SLDPRT       预紧结构
│   ├── [TO_BUILD] Primary_Stop.SLDPRT            G08 主止挡
│   ├── [TO_BUILD] Secondary_Stop.SLDPRT          G08 备用止挡
│   ├── [TO_BUILD] Preload_Spring.SLDPRT          G08 预紧弹簧
│   └── [TO_BUILD] Damping_Element.SLDPRT         G08 阻尼元件
│
├── [TO_BUILD] 06_ARM_HDRM (F3-D，机械臂收拢 HDRM，全新)
│   ├── Latch.SLDPRT
│   ├── Release_Actuator_Envelope.SLDPRT     功能包络，非飞行型号
│   ├── Preload_Spring.SLDPRT
│   ├── Status_Sensor_Envelope.SLDPRT        状态传感器包络
│   └── Mechanical_Stop.SLDPRT
│   输出 HDRM_FUNCTIONAL_DESIGN.md（明确 Engineering Candidate，非飞行）
│
├── [EXISTING - PARTIAL] 07_Gripper (URDF 运动学已有，制造级待 F3-E)
│   └── gripper_link + left + right（URDF mesh）
│
├── [TO_BUILD] 08_End_Effector (F3-E，三阶段)
│   ├── EE-V1 (接口级，比赛优先)
│   │   ├── Wrist_Flange.SLDPRT             腕法兰
│   │   ├── Camera_Mount.SLDPRT             相机座
│   │   ├── F_T_Sensor_Envelope.SLDPRT      力/力矩传感器包络
│   │   └── Capture_Center.SLDPRT           捕获中心
│   ├── EE-V2 (柔顺捕获，比赛优先)
│   │   ├── Compliant_Joint.SLDPRT          柔顺关节
│   │   ├── Passive_Damping.SLDPRT          被动阻尼
│   │   └── Guide_Cone_EE.SLDPRT            导向锥
│   └── EE-V3 (非合作目标，赛后)
│       ├── Grasp_Finger.SLDPRT ×N
│       └── Locking_Mechanism.SLDPRT
│
└── [EXISTING] 09_Solar_Array_Root ×2 (非 B601，但 F3-C 收拢干涉相关)
    └── 继承 V2_3；C5 超宽负结果保留
```

### 3.2 数量口径校正

用户提到"10 links 制造模型"与"10 carrier + J00-J09 + FK 验证已通过"。V2_3 B601 KINEMATIC_PROXY 实际为 base_link + link1..6 + gripper_link + gripper_left + gripper_right = **10 个运动学件**，与"10 links"口径一致。F3-P1 需在制造级阶段核对：
- base_link 是否单独制造（与适配器共享安装面）；
- gripper_left/right 是否归入 EE-V1 而非 Link；
- 6 个 J 关节壳体是否独立制造或与 link 一体化。

---

## 4. 交付物 2：零件 BOM 规划（规划态）

按"现有继承 / 待建 / 接口冻结"三类分。**质量为 URDF 真值，CAD 不覆盖**。

### 4.1 现有继承（V2_3 已冻结，F3 不重建）

| 类别 | 件数 | 来源 | F3 动作 |
|---|---|---|---|
| 主结构（环框/纵梁/甲板/外板） | 17 | `01_Primary_Structure` | 只读核对接口面 |
| B601 安装与载荷路径 | 8 | `02_B601_Mount_and_Load_Path` | 补螺栓圈/定位销参数 |
| B601 运动学代理 | 21 | `B601_KINEMATIC_PROXY` | 保持，作 FK 碰撞体 |
| B601 质量代理 | 11 | `B601_MASS_SURROGATE` | 保持，mass=EXCLUDED |
| 收拢支撑 | 5 | `04_ARM_STOW_SUPPORT` | 补 G07/G08 接触元件 |
| 帆板根部 | 18 | `05/06_Solar_Array_Root_*` | 保持，C5 负结果保留 |
| Master Skeleton | 1 | `00_Master_Skeleton_V2_2` | 增量参数写入属性 |

### 4.2 待建（F3-P1 授权后按子线推进）

| F3 子线 | 待建类别 | 件数估算 | 优先级 | 前置 |
|---|---|---|---|---|
| F3-A | B601_STOWED_HIFI（厂商 STEP 导入） | 1 装配 | P0 | 解决 35 MB STEP 导入失败史 |
| F3-A | Joint_Housing_Assembly ×6 | 6×(6..10) ≈ 36..60 | P1 | HIFI 几何 + 关节接口冻结 |
| F3-A | Output_Bearing_Structure ×6 | 6×(3..5) ≈ 18..30 | P1 | 轴承选型（待授权） |
| F3-A | Joint_Wiring ×6 | 6×(3..4) ≈ 18..24 | P2 | 关节壳体冻结 |
| F3-B | Link_Manufacturing ×N | N×(5..6)，N=6..10 | P2 | F3-A 关节冻结 |
| F3-C | G07/G08 接触元件 | 8..10 | P1 | 接触垫材料 + 预紧 + 发射载荷（HAG-A 影响物理分支） |
| F3-D | ARM_HDRM | 5 | P2 | F3-C 接触资格冻结 |
| F3-E | EE-V1 | 4 | P1 | F3-A 腕接口冻结 |
| F3-E | EE-V2 | 3 | P2 | EE-V1 完成 |
| F3-E | EE-V3 | 2..N | P3（赛后） | 不阻塞比赛 |

### 4.3 接口冻结件（每件输出 ICD）

| 接口 | 数量 | ICD 字段 | 当前状态 |
|---|---|---|---|
| 关节-连杆接口 | 6 | PCD / 螺栓规格 / 定位销 / 基准面 / 轴线 / 承载方向 | 未冻结 |
| 关节-基座接口 | 1 | 同上 + T_SM 数值轨裁决 | T_SM 双轨冲突 |
| 适配器-航天器接口 | 1 | 法兰面 / 螺栓圈 / 定位 | V2_3 已有几何，参数未冻结 |
| 鞍座-臂接触接口 | 3 | 接触垫材料 / 预紧 / 接触面积 / 摩擦系数 | CANDIDATE_HOLD |
| HDRM-鞍座接口 | 3 | 锁紧力 / 释放行程 / 状态传感 | 未冻结 |
| EE-腕接口 | 1 | 腕法兰 PCD / 螺栓 / 定位 | 未冻结 |
| EE-夹爪接口 | 1 | 夹爪开合行程 / 锁定 | URDF 运动学已有，制造级未冻结 |

---

## 5. 交付物 3：参数表（接口/材料/质量，规划态）

### 5.1 接口参数（拟冻结，待 HAG-F3-P1 授权）

```yaml
# 拟冻结参数表 — F3-P0 草案，未授权
joint_interface:
  PCD_mm: TBD                          # 螺栓分度圆
  bolt_spec: TBD                       # 例 M4×10
  positioning_pin: TBD                 # 例 Ø4 h7/h6
  datum_plane: TBD                     # 关节基准面
  axis: TBD                            # 旋转轴方向
  load_direction: TBD                  # 承载方向
  note: "每关节输出 JOINT_INTERFACE_CONTROL_DOCUMENT"

adapter_interface:
  footprint_mm: [160, 160, 12]         # 已冻结 arm_mount_v1.yaml
  boss_diameter_mm: 100                # 已冻结
  boss_height_mm: 15                   # 已冻结
  bolt_circle_PCD_mm: TBD              # 待冻结
  spacecraft_flange_datum: TBD         # 待冻结

stow_interface:
  saddle_contact_height_mm: [261.08, 214.92, 209.42]  # O13 v3 实测
  saddle_tower_height_mm: [147.93, 101.77, 96.27]      # O13 v3 实测
  contact_pad_material: TBD                            # 待 HAG-A + 实测
  preload_N: TBD                                      # 待发射载荷分析
  damping_coefficient: TBD                            # 待选型
```

### 5.2 材料候选（规划态，禁止作为工程真值）

| 部件 | 候选材料 | 候选来源 | 状态 |
|---|---|---|---|
| 关节主承力壳体 | Al 7075-T6 / Al 6061-T6 | 用户建议 + 航天成熟 | `DESIGN_PROPOSAL` |
| 连杆壳体 | CFRP / Al 蒙皮 | 用户建议 | `DESIGN_PROPOSAL` |
| 连杆端接 | Al 7075-T6 | 用户建议 | `DESIGN_PROPOSAL` |
| 接触垫 | TBD | 需 HAG-A 物理分支 | `UNKNOWN_BLOCKED` |
| 鞍座主体 | TBD | V2_3 已有几何，材料未定 | `UNKNOWN_BLOCKED` |
| HDRM 弹簧 | TBD | 需选型 | `UNKNOWN_BLOCKED` |
| 紧固件 | TBD | 需选型 | `UNKNOWN_BLOCKED` |

**禁止**：从视觉模型、案例或对话推断材料、板厚、紧固、载荷、刚度、强度、模态数值。

### 5.3 质量账本（双轨制）

```yaml
# 双轨原则：URDF = accepted dynamics truth；CAD = engineering estimate
URDF_mass_truth:                      # 来自 arm_b601_v1.yaml，禁止 CAD 覆盖
  total_arm_mass_kg: 4.4293
  gripper_mass_kg: 0.2665
  total_dynamics_mass_kg: 4.6956
  source: HYBRID_DevArm_inertial_set
  confidence: medium
  pending: physical_weighing_of_real_arm

CAD_mass_register:                    # 拟建，F3-P1 授权后
  schema: FREECAD_MASS_REGISTER.yaml  # 文件名沿用用户提议，但实际工具为 SolidWorks
  fields:
    component: <part_name>
    mass: <kg>                        # CAD 估算
    cg: [x, y, z]                     # m
    inertia: [Ixx, Iyy, Izz, Ixy, Ixz, Iyz]  # kg m^2
    source: <CAD_material_assignment>
    confidence: <low/medium/high>
  rule: "CAD_mass != URDF_mass; URDF wins for dynamics"
```

### 5.4 柔性接口模型（论文核心，F3 同步）

```yaml
# 拟建 B601_FLEX_MODEL.yaml — F3 同步动力学任务
flex_model:
  link_stiffness:
    link1..6: TBD                     # 需 FEA 或实验
  joint_stiffness:
    J1..J6: TBD                       # 需关节刚度测试或厂商数据
  base_compliance:
    T_SM_compliance: TBD              # 适配器+法兰刚度
  support_stiffness:
    saddle_contact_stiffness: TBD     # 需接触垫材料 + 预紧
  note: "与 sim_11 柔性耦合捕获任务可行域对接；当前 sim_11 帆板参数为占位"
```

---

## 6. 交付物 4：载荷路径图（发射/在轨/捕获，规划态）

### 6.1 发射段载荷路径（最严酷，F3-C 核心判据）

```
机械臂惯性载荷（收拢态，q_v3 + 25° clock）
        │
        ▼
   臂-鞍座接触面（3 站：Aft/Mid/Fwd）
        │   contact_pad_material = TBD（HAG-A 阻塞）
        │   preload = TBD
        │   damping = TBD
        ▼
   G07 鞍座塔（V2_3 已有 5 件）
        │   tower_height = 147.93 / 101.77 / 96.27 mm（O13 v3）
        ▼
   G08 腕支撑（待建）
        │   primary_stop = TBD
        │   secondary_stop = TBD
        │   preload_spring = TBD
        │   damping_element = TBD
        ▼
   航天器主结构（4 纵梁 + 5 环框 + 3 甲板）
        │   longerons 17×17 角点 ±101.65
        │   ring frames X -183..183
        ▼
   航天器-部署器接口（12U deployer，未定义）
        │
        ▼
   部署器-运载接口（未定义）
```

**关键 HOLD**：
- 接触垫材料/预紧/阻尼全部 TBD → CANDIDATE_HOLD；
- 发射载荷谱未定义 → 无法做强度/刚度校核；
- C5 翼板超宽 12 mm → 翼板本体不在 V2_3，但影响整星收拢包络；
- 收拢态 Z 上限 UNKNOWN → 高度合规无判据。

### 6.2 在轨展开段载荷路径

```
展开指令
        │
        ▼
   HDRM 释放（机械臂侧待建 F3-D；帆板侧已有）
        │   release_actuator = TBD
        │   preload_release = TBD
        ▼
   鞍座-臂分离（释放净空包络 V2_3 已有）
        │
        ▼
   关节驱动（B601 6R，q_v3 → DEPLOYED_NOMINAL）
        │   joint_torque = TBD（需厂商 QDD 数据）
        │   joint_stiffness = TBD（F3 同步）
        ▼
   基座反作用（sim_05 已建模 19.20° 扰动，但用的旧 2DOF 模型）
        │   ⚠ arm_b601_v1.yaml note: "sim_05 must re-derive with this model"
        ▼
   姿态控制系统（CTRL-01/02 已裁决，WAVE1_REPEAT）
```

### 6.3 捕获段载荷路径（论文 Paper 1 核心）

```
末端执行器接触目标（T 或 D）
        │
        ▼
   接触冲量（sim_06/sim_10/sim_11/sim_12 已建模）
        │   sim_11 v1.1: T_c=20 ms 名义 PROVISIONAL 待 B601 夹爪实测
        │   sim_12 Phase1: 策略集已裁决
        ▼
   末端-腕-臂载荷传递
        │   EE-V1 接口（待建 F3-E）
        │   joint_stiffness（待 F3 同步）
        ▼
   臂-基座耦合（sim_11 A1/A2 场景）
        │   base_compliance（待 F3 同步）
        ▼
   基座-帆板柔性耦合（sim_11 A2，|H_O|=3.678 N·m·s）
        │   ⚠ 帆板质量 0.348 kg 为 SSOT 占位（真实 2-5 kg/m²，差 5-10×）
        │   ⚠ 杨恒待办 3：真实参数下结论可能翻转
        ▼
   消旋推力器（sim_08：150 kg 碎片需推力器，|H_c|=3.65 N·m·s = 12× 轮组容量）
```

---

## 7. 交付物 5：F3 设计冻结方案

### 7.1 F3 阶段化授权建议

按用户建议的 F3-P0 → F3-P1 → F3-P2 → F3-P3 推进，**每阶段需独立人工 Gate**。

| 阶段 | 内容 | 建议授权名 | 前置 |
|---|---|---|---|
| F3-P0 | 机械架构冻结（本草案） | `HAG-F3-P0-PLANNING` | 本草案人工评审 |
| F3-P1 | 关节 + 连杆制造级 | `HAG-F3-P1-CAD_AUTHORING` | F3-P0 评审通过 + B601_STOWED_HIFI 导入方案验证 + T_SM 双轨裁决 |
| F3-P2 | 收拢机构 + HDRM | `HAG-F3-P2-CAD_AUTHORING` | F3-P1 关节接口冻结 + 接触垫材料选定（HAG-A 影响物理分支） |
| F3-P3 | 末端执行器 | `HAG-F3-P3-CAD_AUTHORING` | F3-P1 腕接口冻结 |

### 7.2 F3-P0 评审清单（本草案需人工确认）

- [ ] 状态校正（§0）是否接受？
- [ ] V2_3 SolidWorks 作为继续基线是否接受？（而非 FreeCAD）
- [ ] F3 5 子线优先级（F3-A → F3-B → F3-C → F3-D → F3-E）是否接受？
- [ ] B601_STOWED_HIFI 作为 F3-A 单点最大风险是否接受？
- [ ] T_SM 双轨冲突是否在 F3-P1 前裁决？
- [ ] C5 翼板超宽 12 mm 负结果是否继续保留？
- [ ] 接触垫材料是否需在 HAG-A 物理分支前预选？
- [ ] 质量/惯量双轨制（URDF 真值 / CAD 估算）是否接受？
- [ ] 柔性接口模型 B601_FLEX_MODEL.yaml 与 sim_11 对接是否在 F3 同步任务范围？

### 7.3 F3-P1 启动条件（硬性）

1. F3-P0 草案人工评审通过并签发 `HAG-F3-P0-PLANNING.yaml`；
2. B601_STOWED_HIFI 厂商 STEP 导入方案验证（35 MB，headless LoadFile4 失败史需绕过）；
3. `T_SM_TRACK_CONFLICT` 人工裁决（185.25 动力学 vs 198 显示）；
4. 关节选型数据：B601 QDD 电机/减速器/轴承规格（需联系厂商或实测）；
5. 接触垫材料候选（HAG-A 物理分支允许后）；
6. 与杨恒协作：帆板真实质量参数（待办 3，影响 F3 同步动力学）。

### 7.4 F3 同步动力学任务（每结构完成即更新）

| 同步项 | 触发 | 输出 | 状态 |
|---|---|---|---|
| 质量账本更新 | 每个零件/子装配冻结 | `FREECAD_MASS_REGISTER.yaml`（SolidWorks 实际） | 待 F3-P1 |
| 柔性接口模型 | 关节/连杆/基座/支撑任一冻结 | `B601_FLEX_MODEL.yaml` | 待 F3-P1 |
| 模态分析 Case 1 | 臂展开态结构冻结 | base fixed, first 10 modes | 待 F3-P1 |
| 模态分析 Case 2 | 全星装配冻结 | free-flyer + arm, first 10 modes | 待 F3-P2 |
| 与 sim_11 对拍 | 柔性模型建立 | sim_11 重跑（按 e15 REPEAT_ANCF_CERTIFICATION 要求） | 待 F3 同步 |

---

## 8. 阻塞清单与负结果保留

### 8.1 F3-P0 → F3-P1 的硬阻塞

| 阻塞 ID | 描述 | 影响子线 | 解除条件 |
|---|---|---|---|
| B-F3-01 | `V2_CAD_NOT_AUTHORIZED` | 全部 | F3-P0 评审 + `HAG-F3-P1-CAD_AUTHORING` |
| B-F3-02 | `B601_STOWED_HIFI` 未建 | F3-A/B/C/D/E | 35 MB STEP 导入方案验证 |
| B-F3-03 | `T_SM_TRACK_CONFLICT` 未裁决 | F3-A | 人工裁决 185.25 vs 198 |
| B-F3-04 | 关节选型数据缺失 | F3-A | 厂商 QDD/减速器/轴承数据 |
| B-F3-05 | `HAG-A ABSENT` | F3-C 接触资格物理分支 | HAG-A 签发或物理分支预选 |
| B-F3-06 | `STOW_Z_LIMIT_REFERENCE = UNKNOWN` | F3-C 高度合规 | 收拢态 Z 上限裁决 |
| B-F3-07 | 帆板质量占位 0.348 kg | F3 同步动力学 | 杨恒提供真实参数（待办 3） |
| B-F3-08 | B601 夹爪 T_c 实测 | F3-C 接触窗 | 硬件组实测（待办 2） |

### 8.2 必须保留的负结果（禁止隐藏/消解）

| 负结果 ID | 内容 | 来源 |
|---|---|---|
| NR-F3-01 | C5 收拢翼包超宽 238.3 > 226.3，超 12.0 mm | `CODEX_CONTINUATION_RECONCILIATION` §3 |
| NR-F3-02 | 翼根机构下限宽 302.3 mm（双侧 \|Y\|=151.15） | 同上 |
| NR-F3-03 | `STOW_VECTOR_STATUS = CANDIDATE_HOLD`，几何 PASS 但接触资格未定 | `O13_STOW_VECTOR_V3_REPORT` |
| NR-F3-04 | DEPLOYED_REFERENCE_Q0 的 10 处静态干涉 = `COLLISION_SAFETY_BLOCKED` | spacecraft-mechanical-design-agent §Mandatory truth corrections #6 |
| NR-F3-05 | e15 交叉求解最大差 5.64% > 5% 门槛 → `REPEAT_ANCF_CERTIFICATION` | CLAUDE.md 核心证据区 |
| NR-F3-06 | WAVE1_CTRL-01 L0 硬件有效稳定性 `NOT_EVALUATED_NO_ACTUATOR_DYNAMICS` | CLAUDE.md Wave1 段 |
| NR-F3-07 | WAVE1_CTRL-02 仅 7/16 在 R5 PROVISIONAL 下 `STABILIZED_WITHIN_WINDOW` | 同上 |

---

## 9. 允许与禁止声明（Required handoff）

```text
WORK_MODE: V2_ARCHITECTURE + CAD_ENTRY_REVIEW（planning only, no CAD authoring）

SOURCES_READ:
- CLAUDE.md
- .codex/AGENTS.md
- .codex/agents/spacecraft-mechanical-design-agent.md
- 10_research/knowledge_base/spacecraft_mechanical_design/README.md
- 20_engineering/config/geometry/arm_b601_v1.yaml
- 20_engineering/config/geometry/arm_mount_v1.yaml
- 20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/coordinate_frame_definition_v0.md
- 20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/mass_inertia_budget_v1.csv
- 20_engineering/cad/Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION/baseline_freeze_manifest.yaml
- 20_engineering/cad/Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION/V22_NATIVE01_PHASE1_REPORT.md
- 20_engineering/cad/Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION/O13_STOW_VECTOR_V3_REPORT.md
- 20_engineering/cad/Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION/CODEX_CONTINUATION_RECONCILIATION.md
- 20_engineering/cad/Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION/phase0_completion_record.json
- 30_simulation/asm_00_interface_preflight/results/asm_00_gate_check.json
- V2_3 子目录结构：00_Master_Skeleton / 01_Primary_Structure / 02_B601_Mount_and_Load_Path / 03_B601_Three_Representations / 04_ARM_STOW_SUPPORT / 05_Solar_Array_Root_Left / 06_Solar_Array_Root_Right

EXACT_STATUS:
- V2_3_NATIVE_INTEGRATION: PHASE0_COMPLETE_BASELINE_FROZEN_AND_ISOLATED
- B601_KINEMATIC_PROXY: BUILT (21 files)
- B601_MASS_SURROGATE: BUILT (11 files)
- B601_STOWED_HIFI: CONFIRMED_NOT_CREATED (empty directory)
- asm_00: ASM00_AG0_BLOCKED_BY_INTERFACE, HAG-A ABSENT
- V2 CAD: NOT_AUTHORIZED (per AGENTS.md and spacecraft-mechanical-design-agent.md)
- FreeCAD F0-F2: NO EVIDENCE IN REPOSITORY (status correction accepted by user, Path A)

EVIDENCE_BOUND_FACTS:
- V2_3 contains 47 parts + 8 assemblies, all SolidWorks native, sha256-locked
- B601 total dynamics mass = 4.6956 kg (URDF HYBRID, confidence medium)
- T_SM nominal_frozen_v1 = [185.25,0,0] mm + R_y(90°), but display track = 198 mm (conflict)
- Stow vector v3 = clock 25°, q=[145.572,-168,-57,-41.143,-20.954,-3], clearance 15.56 mm
- 3 saddle stations: Aft/Mid/Fwd at z=261.08/214.92/209.42, tower 147.93/101.77/96.27
- C5 stowed package 238.3 mm > 226.3 mm available (12 mm overage, NEGATIVE_PRESERVED)
- Solar root mechanism lower bound width 302.3 mm (unresolvable)

DESIGN_PROPOSALS:
- F3 sub-line decomposition (F3-A..F3-E) mapped to V2_3 reality
- Manufacturing-grade structure tree (§3) with EXISTING/TO_BUILD tags
- BOM plan (§4) with 3 categories (inherit/build/freeze)
- Parameter table (§5) with frozen/TBD/proposed fields
- Load path diagrams (§6) for launch/on-orbit/capture
- F3-P0..F3-P3 authorization ladder (§7)

UNKNOWN_BLOCKERS:
- B601_STOWED_HIFI vendor STEP import (35 MB, headless failure history)
- T_SM track conflict (dynamics 185.25 vs display 198)
- Joint selection data (QDD motor / reducer / bearing specs)
- Contact pad material (HAG-A physics branch)
- Stowed Z upper limit (no compliance criterion)
- Solar panel real mass (Yang Heng TODO 3)
- B601 gripper T_c measurement (hardware team TODO 2)

NEGATIVE_RESULTS_PRESERVED:
- NR-F3-01: C5 stowed package overage 12 mm
- NR-F3-02: Solar root mechanism lower bound 302.3 mm
- NR-F3-03: STOW_VECTOR_STATUS CANDIDATE_HOLD
- NR-F3-04: DEPLOYED_REFERENCE_Q0 10 static interferences
- NR-F3-05: e15 REPEAT_ANCF_CERTIFICATION (5.64% > 5%)
- NR-F3-06: WAVE1 CTRL-01 L0 NOT_EVALUATED_NO_ACTUATOR_DYNAMICS
- NR-F3-07: WAVE1 CTRL-02 only 7/16 under R5 PROVISIONAL

FILES_CHANGED:
- 01_project/competition/F3_P0_mechanical_architecture_freeze_draft_20260804.md (NEW, this file)

FROZEN_BOUNDARY_CHECK: PASS
- No frozen files modified (V2_3, config/geometry, 30_simulation, 40_evidence, Gate JSON)
- No CAD files created or modified
- No URDF modified
- No Gate JSON modified

ALLOWED_CLAIMS:
- "F3-P0 architecture planning draft produced under Path A (status correction)"
- "V2_3 SolidWorks is the current CAD baseline; B601_STOWED_HIFI is the single largest gap"
- "F3 sub-lines mapped to V2_3 with EXISTING/PARTIAL/TO_BUILD classification"
- "All manufacturing-grade modeling actions remain PLANNED_NOT_AUTHORIZED"

PROHIBITED_CLAIMS:
- "F0-F2 FreeCAD PASS" (no evidence in repository)
- "FreeCAD manufacturing-grade pilot validated" (no FreeCAD files exist)
- "F3 CAD authorized" (only F3-P0 planning draft authorized under Path A)
- "B601_STOWED_HIFI built" (empty directory)
- "T_SM conflict resolved" (still open)
- "Contact pad material selected" (TBD, HAG-A blocked)
- "Stow vector qualified" (CANDIDATE_HOLD)
- "Mass/inertia from CAD = URDF truth" (URDF wins, CAD is estimate only)

NEXT_HUMAN_GATE:
- HAG-F3-P0-PLANNING: review and accept/reject this draft
- HAG-F3-P1-CAD_AUTHORING: authorize SolidWorks native CAD authoring for F3-A/B
- HAG-A: unblock asm_00 AG0 for F3-C contact qualification physics branch
- T_SM_TRACK_CONFLICT ruling: 185.25 (dynamics) vs 198 (display)
```

---

## 10. 下一步建议（不构成授权）

1. **请你评审本草案 §7.2 清单**，逐项 ✅/❌/改；
2. 若接受 F3-P0 草案，签发 `HAG-F3-P0-PLANNING.yaml`（建议放在 `01_project/competition/approvals/` 或 `10_research/on_orbit_assembly/approvals/` 并行目录）；
3. 同步裁决 `T_SM_TRACK_CONFLICT`（这是 F3-A 关节壳体建模的前置）；
4. 与杨恒推进帆板真实质量参数（待办 3，影响 F3 同步动力学与 sim_11 重跑）；
5. 与硬件组推进 B601 夹爪 T_c 实测（待办 2，影响 F3-C 接触窗）；
6. 若你确实有外部 F0-F2 FreeCAD 工作，请按路径 B 入库到 `20_engineering/cad/Space_Embodied_Robot_CAD_V3_0_FREECAD_F0_F2/`（建议命名），我核验后并入 F3-P0 草案升级版。

**本草案不启动任何建模动作。** F3-A..F3-E 全部子线在 `HAG-F3-P1-CAD_AUTHORING` 签发前保持 `PLANNED_NOT_AUTHORIZED`。
