# SER-MECH-V3.0 机械差距矩阵

## 状态词典

- `BOUND`：来源、文件、哈希和 authority 已绑定。
- `DESIGN_PROPOSAL`：有原生几何，但没有物理/制造/强度 authority。
- `REFERENCE_ONLY`：仅能用于布局、对照或分析。
- `UNKNOWN_BLOCKED`：缺少输入，禁止猜测。
- `HOLD`：存在负结果、冲突或验证缺口。
- `REBUILD`：V3 必须新建，不能原样迁移。
- `EXCLUDE`：不得进入 V3 active top。

## A. 12U 主结构

| ID | 设计对象 | 当前证据 | 当前状态 | 关键缺口 | V3 动作 | 出口证据/Gate |
|---|---|---|---|---|---|---|
| STR-01 | 外包络与总长 | 226.3×226.3 横截面；340.5 与 366 mm 两轨并存 | `HOLD` | display/dynamics/flight envelope 未统一；标准 12U 声明被阻断 | 命名双轨或人工选定唯一轨；禁止静默替换 | `V3-A-01 ENVELOPE_RULING_SIGNED` |
| STR-02 | Master Skeleton | V2.2_NATIVE 原生 skeleton，SHA `337C…E6CA` | `DESIGN_PROPOSAL` | 轨、frame、keepout 和硬点未形成 V3 唯一 SSOT | 在新 V3 根重建 | `V3-A-02 SKELETON_HASH_AND_FRAME_LEDGER_PASS` |
| STR-03 | 环框 | 5 个原生环框 | `DESIGN_PROPOSAL` | 材料、截面、局部加强、制造、节点连接未知 | 保留站位意图；重建结构定义 | `V3-A-03 FRAME_SECTION_AND_MATERIAL_INPUT_SIGNED` |
| STR-04 | 纵梁 | 一个 `Longerons_4X` 多构件零件 | `DESIGN_PROPOSAL` | 单根追踪、连接、容差与可更换性不足 | 重构为 4 个可独立追踪实例 | `V3-A-04 LONGERON_INSTANCE_AND_JOINT_LEDGER_PASS` |
| STR-05 | 设备甲板 | 3 个原生甲板和部分穿舱孔 | `DESIGN_PROPOSAL` | 厚度、材料、载荷、安装孔、服务方向未知 | 重建真实硬点和开口控制 | `V3-A-05 DECK_ICD_PASS` |
| STR-06 | 可拆外板 | 6 个外板；V2.3 已证明引用修复 | `DESIGN_PROPOSAL` | 快卸、紧固、屏蔽、热接触与维护工具轴未知 | 重建面板接口；继承引用隔离方法 | `V3-A-06 PANEL_ACCESS_AND_FASTENER_GATE` |
| STR-07 | 主承载路径 | adapter→spreader→front frame→longerons 意图可解释 | `HOLD` | 六维发射、捕获、运行、地面载荷均未签发 | 建立 load case register 后再尺寸设计 | `V3-A-07 LOAD_CASE_INPUT_GATE` |
| STR-08 | 结构连接 | PDR 与 CAD 只有拓扑 | `UNKNOWN_BLOCKED` | 螺栓/定位销/焊接或粘接、预紧、公差未知 | 由 ICD 驱动重建 | `V3-A-08 JOINT_AND_FASTENER_ICD_SIGNED` |
| STR-09 | 材料与截面 | 当前实体声明 strength/manufacturing authority = none | `UNKNOWN_BLOCKED` | 材料、板厚、截面、表面处理、热膨胀未知 | 不猜测；等待输入 | `V3-A-09 MATERIAL_SECTION_RELEASED` |
| STR-10 | 质量/质心/惯量 | 整星仍无权威；旧预算低置信度 | `UNKNOWN_BLOCKED` | 设备选型与质量 owner 不完整 | 建立按 owner 的预算，不使用默认 CAD 密度 | `V3-A-10 MASS_OWNER_LEDGER_PASS` |
| STR-11 | 发射接口/导轨 | 未发现签发 rail/launcher ICD | `UNKNOWN_BLOCKED` | 约束面、分离界面、频响和载荷未知 | 仅保留 keepout，不建实体结论 | `V3-A-11 LAUNCH_INTERFACE_SIGNED` |
| STR-12 | 结构分析 | 没有签发载荷输入；本轮未跑 FEA | `NOT_AUTHORIZED` | 强度、刚度、模态、屈曲、热变形未评估 | 在 A 输入闭合后单独授权 CAE | `V3-A-12 FEA_ENTRY_GATE` |

## B. B601 安装、收拢与三表征

| ID | 设计对象 | 当前证据 | 当前状态 | 关键缺口 | V3 动作 | 出口证据/Gate |
|---|---|---|---|---|---|---|
| ARM-01 | 运动学与模型质量 | accepted URDF，10 links/9 joints，模型总质量 4.695555949342986 kg | `BOUND` | 物理称重仍未知；许可边界需从严 | 冻结为唯一运动学和质量/惯量输入 | `V3-B-01 URDF_HASH_PIN_PASS` |
| ARM-02 | 高保真外形 | vendor STEP 及 q0/stow 派生 | `REFERENCE_ONLY` | 不是运动学、质量或制造 authority；禁止再分发 | 只在 visual review 配置中引用或重建受控导入 | `V3-B-02 SOURCE_LICENSE_GATE` |
| ARM-03 | `T_SM` | 185.25 mm PDR/dynamics 与 198 mm native display | `HOLD` | 两个未命名 M frame 会破坏接口追踪 | 明确命名双轨或签发唯一值 | `V3-B-03 T_SM_RULING_SIGNED` |
| ARM-04 | clock 与 `T_MA0` | O13 候选为 25°；证据对批准状态表述冲突 | `HOLD` | adapter 内变换、`M_clocked` 或 A0 修改未裁决 | 签发唯一 frame tree | `V3-B-04 CLOCK_FRAME_RULING_SIGNED` |
| ARM-05 | 安装法兰 | 160×160×12 adapter、160×160×15 flange、Ø100 身份 | `DESIGN_PROPOSAL` | 孔系、定位、紧固、允许载荷、刚度、公差未知 | 以 interface part + ICD 重建 | `V3-B-05 MOUNT_ICD_PASS` |
| ARM-06 | 载荷扩散 | 原生 load bridge/spreading frame | `DESIGN_PROPOSAL` | 连接反力、材料和截面未知 | 由签发 load cases 重建 | `V3-B-06 LOAD_PATH_AND_JOINT_GATE` |
| ARM-07 | 收拢位姿 | q=`[145.572,-168,-57,-41.143,-20.954,-3]°`、clock=25° | `CANDIDATE_HOLD` | Z 上限、全路径、接触、clock authority 未闭合 | 保留为 comparator，不作为发布配置 | `V3-B-07 STOW_POSE_ACCEPTANCE` |
| ARM-08 | 三鞍座 | 三窗口与 15.56 mm 可动段几何间隙 | `CANDIDATE_HOLD` | 接触面、软垫、壳体允许载荷、预紧、HDRM 未知 | 选定接触 authority 后重建 | `V3-B-08 SUPPORT_CONTACT_GATE` |
| ARM-09 | HIFI 表征 | V2.3 目录为空 | `INVALID/HOLD` | 无装配、无插入、无冷重开 | V3 中按许可证新建受控 visual representation | `V3-B-09 HIFI_REFERENCE_GATE` |
| ARM-10 | Kinematic proxy | V2.3 双零件族、属性回读无效 | `EXCLUDE` | 无可信 URDF 链和配置持久性 | 从 accepted URDF 重新生成，逐 link 绑定 hash | `V3-B-10 KINEMATIC_CHAIN_AND_POSE_GATE` |
| ARM-11 | Mass surrogate | V2.3 以 500 kg/m³ 和立方体体积拟合 | `EXCLUDE` | CoM/MOI 未原生实现；可能重复计重 | 仅在证明 CAD 能表达 URDF 质量/惯量后新建；否则保持外部 URDF authority | `V3-B-11 MASS_EQUIVALENCE_GATE` |
| ARM-12 | 三表征互斥 | 当前三配置均为空 | `EXCLUDE` | 无 resolved/suppressed、BOM 和质量互斥证据 | 建立 visual/kinematic/mass 三个互斥配置 | `V3-B-12 SINGLE_INSTANCE_AND_NO_DOUBLE_MASS_GATE` |
| ARM-13 | 线束与维护 | 存在 passage 和 access cover 几何意图 | `DESIGN_PROPOSAL` | 连接器、弯曲半径、应变释放、工具轴未知 | 与硬件/电气 ICD 联合重建 | `V3-B-13 HARNESS_SERVICE_GATE` |
| ARM-14 | 任务/目标接口 | `T_SB`、目标接口、捕获接口未签发 | `UNKNOWN_BLOCKED` | 自由飞行器基座、容差、相对运动和接触未知 | 先发 task interface ICD | `V3-B-14 TARGET_INTERFACE_GATE` |

## C. 太阳翼与根机构

| ID | 设计对象 | 当前证据 | 当前状态 | 关键缺口 | V3 动作 | 出口证据/Gate |
|---|---|---|---|---|---|---|
| SOL-01 | 左右翼根身份 | V2.2_NATIVE 左右独立原生子装配 | `DESIGN_PROPOSAL` | BOM 计数在 9/13/14 间冲突 | 冻结现状；V3 重新枚举每个 physical/reference 对象 | `V3-C-01 BOM_AND_OBJECT_ID_GATE` |
| SOL-02 | 根座与耳片 | root base、双耳和穿板槽已有几何 | `DESIGN_PROPOSAL` | 材料、轴承座、公差、紧固和反力链未知 | 保留界面意图，重建承载细节 | `V3-C-02 ROOT_ICD_GATE` |
| SOL-03 | 铰链轴/轴承 | 现有单根通销是几何参考 | `REFERENCE_TBD` | 轴径、配合、轴承/衬套、保持件、润滑未知 | 由 mechanism ICD 重建 | `V3-C-03 HINGE_DETAIL_GATE` |
| SOL-04 | 翼板本体 | V2.2 donor 中存在；V2.2_NATIVE 顶装未含 | `REFERENCE_ONLY` | 真实尺寸、层合、质量/惯量、刚度、热变形未知 | `MIGRATE_PANEL_ONLY` 后重建物理定义 | `V3-C-04 PANEL_AUTHORITY_GATE` |
| SOL-05 | 扭簧/驱动 | 现有扭簧仅 envelope/reference | `UNKNOWN_BLOCKED` | 刚度、预紧、扭矩曲线、温度、寿命、裕量未知 | 选型后重建 | `V3-C-05 DRIVE_TORQUE_GATE` |
| SOL-06 | HDRM | base/rod/display envelope 存在 | `REFERENCE_TBD` | 类型、保持载荷、释放能量、冗余、冲击、复位未知 | 选型与安全逻辑签发后重建 | `V3-C-06 HDRM_GATE` |
| SOL-07 | 止挡与锁定 | hard stop 几何存在 | `DESIGN_PROPOSAL` | 止挡角、冲击载荷、锁定/回弹和寿命未知 | 定义 stowed/deployed datum 与 load path | `V3-C-07 STOP_LATCH_GATE` |
| SOL-08 | 线束跨铰链 | service loop 为 reference | `REFERENCE_TBD` | 弯曲半径、扭转、连接器、热/电和寿命未知 | 与运动轨迹联合设计 | `V3-C-08 HARNESS_SWEEP_GATE` |
| SOL-09 | 状态配置 | L_FAIL/R_FAIL/PARTIAL 当前几何等同 | `HOLD` | 未形成独立运动与失效状态 | V3 中建立真实自由度和逐态 readback | `V3-C-09 CONFIGURATION_PERSISTENCE_GATE` |
| SOL-10 | C5 收拢宽度 | 238.3 mm > 226.3 mm，超 12.0 mm | `NEGATIVE_RESULT_OPEN` | 无关闭裁决 | 必须显式关闭或带入发布 HOLD | `V3-C-10 C5_RULING` |
| SOL-11 | 根机构宽度下限 | 302.3 mm > 226.3 mm | `NEGATIVE_RESULT_OPEN` | 机构布局与 envelope 冲突 | 不得隐藏、减薄或内移制造假通过 | `V3-C-11 ROOT_WIDTH_RULING` |
| SOL-12 | Z 包络 | `STOW_Z_LIMIT_REFERENCE=UNKNOWN` | `UNKNOWN_BLOCKED` | 无签发上限 | 保持 UNKNOWN，等待系统边界 | `V3-C-12 STOW_Z_LIMIT_SIGNED` |
| SOL-13 | 柔性/模态输入 | 200×227×6 mm、0.3483933 kg 为 provisional 仿真占位 | `REFERENCE_ONLY` | 非机械 panel authority | V3 物理面板输入完成后再回写仿真 | `V3-C-13 PANEL_TO_DYNAMICS_HANDOFF` |
| SOL-14 | 展开扫掠/遮挡 | 未完成真实关节 sweep、FOV/RF/喷流联合检查 | `NOT_STARTED` | 运动驱动和硬件 keepout 未签发 | C 机构闭合后执行 | `V3-C-14 MULTI_DOMAIN_SWEEP_GATE` |

## D. 具身硬件与服务系统

| ID | 设计对象 | 当前证据 | 当前状态 | 关键缺口 | V3 动作 | 出口证据/Gate |
|---|---|---|---|---|---|---|
| EMB-01 | 末端夹爪 | URDF 含 gripper link 与左右 prismatic finger | `BOUND_KINEMATIC_ONLY` | 接触面、材料、夹持力、容差和寿命未知 | 保留运动学；真实工具另立 ICD | `V3-D-01 TOOL_KINEMATIC_GATE` |
| EMB-02 | Physical TCP | 只有 `E_virtual`/`G` 语义 | `UNKNOWN_BLOCKED` | `T_E_TCP`、工具中心、安装基准和标定未知 | 选定工具后建立 physical TCP | `V3-D-02 TCP_CALIBRATION_GATE` |
| EMB-03 | F/T 传感器 | V2.2 只有包络级显示件 | `REFERENCE_ONLY` | 型号、量程、精度、刚度、安装栈、标定未知 | datasheet/ICD 到位后重建 | `V3-D-03 FT_SELECTION_GATE` |
| EMB-04 | 柔顺/锁紧/快换 | V2.2 为 candidate display proxy | `EXCLUDE` | 刚度/阻尼/行程、锁紧、冗余和工具接口未知 | 任务接口先行，再选型 | `V3-D-04 COMPLIANCE_TOOL_GATE` |
| EMB-05 | Task camera | 现有 NAV_CAM/FOV 只是无型号显示体 | `REFERENCE_ONLY` | 型号、FOV、工作距、质量、功耗、热、标定未知 | 建立 `T_SC` 和真实支架 | `V3-D-05 TASK_CAMERA_GATE` |
| EMB-06 | Range/导航传感器 | 无型号包络 | `REFERENCE_ONLY` | 量程、盲区、光轴、遮挡、接口未知 | 选型后重建 | `V3-D-06 SENSOR_SUITE_GATE` |
| EMB-07 | 具身计算舱 | 只有 V2.0 `VOL_MID_OBC` 占位 | `UNKNOWN_BLOCKED` | compute、存储、功耗、散热、质量、辐射和接口未知 | 选型后建立 tray 与 thermal path | `V3-D-07 COMPUTE_HARDWARE_GATE` |
| EMB-08 | 线束与数据 | 只有 passage/route 语义 | `UNKNOWN_BLOCKED` | 连接器、带宽、供电、弯曲、EMC、应变释放未知 | 建立 harness ICD 和 service loop | `V3-D-08 HARNESS_GATE` |
| EMB-09 | 维护可达性 | 有 MAINTENANCE 评审态 | `HOLD` | 工具轴、拆卸顺序、快卸和人机接口未证明 | 做 extraction/service matrix | `V3-D-09 SERVICE_ACCESS_GATE` |
| EMB-10 | 联合 keepout | FOV、臂、翼、喷流、RF、热分散存在 | `NOT_STARTED` | 缺真实硬件和运动 authority | D 硬件选型后联合检查 | `V3-D-10 CROSS_DOMAIN_KEEPOUT_GATE` |
| EMB-11 | 任务目标 | 未签发服务目标机械接口 | `UNKNOWN_BLOCKED` | 抓取点、相对位姿、容差、接触/冲击未知 | 目标 ICD 先于 physical end-effector | `V3-D-11 TARGET_ICD_GATE` |
| EMB-12 | 航天器自由飞行基座 | `T_SB` 未知 | `UNKNOWN_BLOCKED` | 目标/服务星 frame 关系和耦合载荷未知 | 与 GNC/dynamics 联合签发 | `V3-D-12 T_SB_GATE` |

## E. 工程图与数字线程

| ID | 设计对象 | 当前证据 | 当前状态 | 关键缺口 | V3 动作 | 出口证据/Gate |
|---|---|---|---|---|---|---|
| DRW-01 | STOWED 评审图 | 原生 SLDDRW；4 视图 + A-A | `REFERENCE_ONLY` | 标题栏 6.159 kg 无权威；无尺寸/BOM/材料 | 冻结证据，V3 重画 | `V3-E-01 STOWED_DRAWING_RELEASE_GATE` |
| DRW-02 | MAINTENANCE 评审图 | 原生 SLDDRW；4 视图 + A-A | `REFERENCE_ONLY` | 标题栏 5.191 kg 无权威；维护可达未证明 | 冻结证据，V3 重画 | `V3-E-02 MAINTENANCE_DRAWING_RELEASE_GATE` |
| DRW-03 | 总装 GA/BOM | 不存在 V3 包 | `REBUILD` | 零件号、authority、配置和质量 owner 缺失 | 新建 V3 GA/BOM | `V3-E-03 GA_BOM_GATE` |
| DRW-04 | 主结构图 | 不存在工程发布级图纸 | `REBUILD` | 尺寸、公差、材料、紧固和节点未知 | A 输入闭合后新建 | `V3-E-04 STRUCTURE_DRAWING_GATE` |
| DRW-05 | B601 ICD/支承图 | 不存在工程发布级图纸 | `REBUILD` | 安装、定位、载荷、接触和释放未知 | B 输入闭合后新建 | `V3-E-05 B601_DRAWING_GATE` |
| DRW-06 | 太阳翼机构图 | 不存在工程发布级图纸 | `REBUILD` | 轴、弹簧、HDRM、止挡、线束未签发 | C 输入闭合后新建 | `V3-E-06 SOLAR_DRAWING_GATE` |
| DRW-07 | 具身硬件安装图 | 不存在 | `REBUILD` | 所有选型和标定接口未签发 | D 输入闭合后新建 | `V3-E-07 EMBODIED_DRAWING_GATE` |
| DRW-08 | 数字线程 | 各版本证据水平不一 | `HOLD` | V2.2/V2.3 无统一全树终封；Stage 2 verdict 冲突 | V3 每个 Gate 重建 manifest/dependency/deviation | `V3-E-08 DIGITAL_THREAD_GATE` |

## 最高优先级阻断项

1. V3 seed 与唯一 writer 尚未人工签发。
2. 366/340.5 mm 与 198/185.25 mm 双轨未裁决。
3. 25° clock 与 `T_MA0` 的 frame authority 不一致。
4. 所有结构载荷、材料、截面、连接和紧固输入仍为空。
5. B601 收拢接触、发射锁定、Z 包络和释放路径未资格化。
6. 太阳翼现场 13 件/侧与证据 9/14 件冲突。
7. C5 和 302.3 mm 宽度负结果未关闭。
8. physical TCP、任务相机、F/T、柔顺/工具和 compute hardware 未选型。
9. 当前两张图纸含无权威标题栏质量，不能外发为工程发布图。
