# M-FINAL HDRM 与服务相机 Authority 裁决

**裁决编号：** `MFINAL-HDRM-CAMERA-AUTHORITY-RULING-V1`  
**适用基线：** `F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809`  
**发布日期：** 2026-08-09  
**状态：** `ACTIVE_FOR_V4_COMPETITION_CANDIDATE_WITH_HARD_HOLDS`  
**机器可读伴随文件：** `MFINAL_HDRM_CAMERA_AUTHORITY_RULING.json`

## 1. 裁决结论

本裁决仅在全新 V4 successor 内生效，不修改或回写 F3R2、P4D、P5B、P5D 或 vendor donor。

### 1.1 ARM HDRM

V4 竞赛样机候选的唯一 controlling chain 为：

`F3-P4D functional interface -> F3-P5B competition demonstrator -> F3-P5D competition-prototype release`

受控方向和行程如下：

| 项目 | V4 controlling value | 含义 |
|---|---:|---|
| 预载方向 | `+X` | 工作预载方向 |
| 工作释放方向 | `-X` | 与预载相反的机构释放方向 |
| 地面拆装/手动解锁方向 | `+Z` | 仅用于安装、拆卸和地面手动解锁；不是工作释放方向 |
| 释放行程 | `6 mm` | P5B 竞赛演示件实例值，满足 P4D 的不小于5 mm要求 |
| 工作预载 | `50 N` | P4D/P5B 门槛值 |
| P5B 选型矩阵能力 | `60 N` | 采购目标；最终能力必须由供应商曲线和台架试验确认 |
| 释放时间 | `<0.5 s` | 竞赛演示件要求 |
| 机构路线 | 电磁保持/解锁 + 压缩弹簧 + 机械止挡 | 竞赛演示件，不得外推为飞行 HDRM |

P4D 已明确把 `-X` 规定为释放方向，同时把 `+Z` 规定为主拆装和地面解锁方向。F3R2 后续自动生成的 `+Z, away from the bus deck` 与这一链冲突，而且其自身状态仍为 `G4_DEFINED_NOT_MODELLED`、行程仍为 `CANDIDATE`、最终门仍为 `PENDING_HUMAN_REVIEW`。因此：

- F3R2 的 `+Z` 不得用于 V4 工作释放配合、运动配置或控制状态机。
- F3R2 只保留为参考站位和测量包络证据。
- P4D/P5B/P5D 控制 V4 的功能方向、行程和竞赛演示路线。

### 1.2 服务相机

V4 配置状态锁定为：

`SERVICE_CAMERA = UNSELECTED / HARD_HOLD`

三个 vendor STEP 都只是 wrist mount，不含相机本体、镜头、连接器、线缆或 optical frame。它们不能单独构成相机选型或视觉标定 authority。

若比赛样机必须立即形成条件性实物路线，允许的首选路线为：

`实际采购 Intel RealSense D405 + D405_305_Mount.step`

该路线的状态仅为 `CONDITIONAL_PROTOTYPE_ROUTE_NOT_RELEASED`。其依据是本地 vendor 资料同时具有 B601 实装照片和 D405 eye-in-hand TF 线索；同一资料也明确指出当前只有 RViz/TF，没有 driver、depth、intrinsics，且支架标定未完成。条件性路线不是采购授权，也不是 V4 相机释放。

## 2. HDRM 几何和接口边界

P4D/P5B 竞赛接口基线：

- 安装法兰：`60×60×10 mm`
- 安装孔：`4×M5×16，PCD Ø50 mm`
- 定位要求：`2×Ø5 h7×16 mm`；销孔坐标和时钟角仍为 HOLD
- 候选弹簧：`Ø8×Ø1.2×20 mm，k=10 N/mm`
- 释放后臂侧残余突出：`<2 mm`
- 工具空间候选：`Ø50 mm` 圆柱

F3R2 可复用的参考站位：

- `Launch_Lock_Interface_Reference = [-10,-84,132]..[10,84,168] mm`
- 约束平面：`x=0`
- z 带：`132..168 mm`
- 临时几何中心：`C_REF=(0,0,150) mm`

V4 当前 neutral CAD 使用的保守 sweep keepout 为：

`[-21,-89,127]..[15,89,173] mm`

该包络由参考体沿 `-X` 平移6 mm并叠加5 mm包装裕量得到，只是碰撞与布置占位，不是释放后实体包络或可制造硬件。

V4 相关 neutral skeleton：

- `02_neutral_cad/hdrm/V4_ARM_HDRM_60MM_FLANGE_SKELETON.step`
- `02_neutral_cad/hdrm/V4_ARM_HDRM_RELEASE_SWEEP_KEEP_OUT.step`

两者均必须保持 `NON_PHYSICAL / HOLD_SKELETON_ONLY`，不得计入已采购件、已试验件、飞行件或最终质量台账。

## 3. 相机 donor 几何裁决

共同 donor 目录：

`F:\China Graduate Future Flight Vehicle Innovation Competition\80_third_party\vendor\reBot-DevArm\hardware\reBot_B601_DM\3D_Printed_Parts`

三份 STEP 均可解析为 AP214、1 root、1 closed solid，并共享：

- B601 wrist 侧 `R28.5 mm` 圆柱接触面
- 2×`Ø2.7 mm` 完整内孔，中心距 `22.000 mm`
- 相机安装面约绕 X 倾斜 `15°`

`Ø2.7 mm` 没有螺纹和公差 authority，只能称为 M3 级打印安装孔，不能直接发布为 M3 通孔。

| Donor | AABB 尺寸 mm | 体积 mm³ | 相机侧几何线索 | 状态 |
|---|---:|---:|---|---|
| `D435_Gemini2_Mount.step` | `95.761459×53.514945×28.464120` | `36062.814775` | 2×Ø3.2、2×Ø5.6沉孔，轴距约44.915 mm | donor only |
| `D405_305_Mount.step` | `94.447575×70.905870×33.961850` | `29047.043205` | 2×Ø3.2、2×Ø5.6沉孔，轴距20.000 mm | conditional D405 route donor |
| `UVC32_mount.step` | `70.001604×69.443959×32.310659` | `19344.699315` | 4×Ø1.5，28×28 mm阵列 | donor only；成熟度最低 |

三者都明显超出 F3R2 提出的 `40×34×26 mm` 支架候选包络，必须按真实相机和 link6 最终姿态重新做 swept clearance。STEP 内嵌的“钢/7850 kg·m⁻³”属于默认或残留材料属性，与 vendor 的 ABS 打印说明冲突，禁止进入质量台账。

## 4. 硬 HOLD 与非声明

### 4.1 HDRM HARD HOLD

- 实际电磁件型号、供应商数据表、外形和保持力—电流曲线
- 断电/通电失效安全逻辑、热设计、占空比和寿命
- bus deck 与 arm restraint boss/cup 的真实 B-rep 接触面
- 法兰全局姿态、安装中心、孔阵列时钟角和定位销坐标
- 连接器、pinout、线束出口及 keepout
- 材料、公差、表面处理、紧固件等级和预紧
- native LOCKED/RELEASED/FAILED 配置、连续干涉和冷开重建
- 物理保持力、行程、释放时间、重复释放和失效恢复试验

### 4.2 CAMERA HARD HOLD

- 实际相机采购料号和 OEM CAD/接口图
- 相机本体质量、质心、连接器和线束
- 驱动、深度流、内参、FOV 和工作距离
- 支架物理试装、紧固件和打印材料/工艺
- optical frame、手眼标定、视场遮挡和最终 swept clearance

### 4.3 本裁决明确不构成

- 飞行发布、飞行鉴定或航天级采购结论
- 采购授权或供应商选型闭环
- 物理试验、环境试验或寿命试验闭环
- SolidWorks 原生机构、配合、配置或工程图发布
- 制造发布或最终质量/惯量 authority
- 相机正式选型、视觉标定或任务视场闭环

## 5. 精确源路径与 SHA-256

### 5.1 HDRM controlling chain

| 角色 | 精确路径 | SHA-256 |
|---|---|---|
| P4D 接口证据副本 | `F:\China Graduate Future Flight Vehicle Innovation Competition\40_evidence\c1_evidence\F3_P4D_HDRM_STRUCTURAL_DEEPENING.md` | `697E806E210C0842433DB8F41DE3371B5A6F8AC1CAFAA1984378ED02158DFC3B` |
| P4 gate | `F:\China Graduate Future Flight Vehicle Innovation Competition\40_evidence\c1_evidence\F3_P4_GATE_STATUS.json` | `00A4DEF86FB38772651B5A14C8961C54EEE18B515255C8474F5AD26BB0862C23` |
| P5 输入清单 | `F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3_P5_structural_closure_candidate\00_audit\F3_P5_INPUT_MANIFEST.csv` | `00E30603F92FBC39883D1106C73F6A25967839712269B724455ACB9EDABFFD8C` |
| P5B 演示件定义 | `F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3_P5_structural_closure_candidate\06_hdrm\F3_P5B_HDRM_COMPETITION_DEMONSTRATOR.md` | `785DEE8E485603D46DEFEF51C7C4F39C123ACACF9F9C4F678B48CEEA1295F17C` |
| P5B gate | `F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3_P5_structural_closure_candidate\06_hdrm\F3_P5B_HDRM_GATE_STATUS.json` | `828D40823ECD7A101E13CE1A53E65729D6D59757856AF0AF4FAD996C2A39B7EF` |
| P5B 选型矩阵 | `F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3_P5_structural_closure_candidate\06_hdrm\F3_P5B_HDRM_SPECIFIC_MODEL_MATRIX.csv` | `793D1FF5301F7AD595AA0E2F618D52820CF0A47407243B1DE799EB5C58F7D133` |
| P5D 竞赛制造 gate | `F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3_P5_structural_closure_candidate\07_manufacturing_release\F3_P5D_GATE_STATUS.json` | `DE74784E9F16EB01536585ECC9928452FFF6E8763A3B989E598BA12F74F872D3` |
| P5 terminal closure | `F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3_P5_structural_closure_candidate\10_submission\F3_P5_TERMINAL_CLOSURE.json` | `44D21CA3CFB48E330AA88FDE1B2E38D591BE66FD7ABD666BBFE13338D7F36F18` |
| P5 terminal manifest | `F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3_P5_structural_closure_candidate\10_submission\F3_P5_TERMINAL_MANIFEST_SHA256.txt` | `7CB8A716D79713DD068C3FC966916720614C8C1C1075704C977F4261977AEE7B` |

### 5.2 F3R2 冲突与限制证据

| 角色 | 精确路径 | SHA-256 |
|---|---|---|
| F3R2 G4 定义 | `F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807\07_hdrm\F3R2_ARM_HDRM_DEFINITION.json` | `90E227F582A4155DD8BAC11B8EC0838EC2195F8D5A36C67475243060911435FD` |
| F3R2 生成脚本 | `F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807\99_tools\r2j_g4_hdrm_camera.py` | `CAF607EEC10D8773D59F8B94EB24888BE017D14FA8492B1100BE107AFE84AF19` |
| F3R2 final gate | `F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807\13_gate\F3R2_FINAL_GATE.json` | `6AE690EB37CA0700B1E595643D13035BC4458FC367BB09AFA0435803F03CD994` |
| F3R2 camera/harness/gripper 定义 | `F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807\08_camera_harness\F3R2_CAMERA_HARNESS_GRIPPER.json` | `07618B5CFE2C2F1D2391B5D845CB82AD7ECFBBCC6371EEADF931289C8F2902D6` |
| M3R evidence inventory | `F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807\03_native_cad\M3_interface_authority\M3R_INTERFACE_EVIDENCE_INVENTORY.csv` | `EB9EBF10131D2EDD9B775C64C2CE6F2B275CEF79F8F6F58E62862848C831476F` |

### 5.3 Camera donor

| Donor | 精确路径 | SHA-256 |
|---|---|---|
| D435/Gemini2 mount | `F:\China Graduate Future Flight Vehicle Innovation Competition\80_third_party\vendor\reBot-DevArm\hardware\reBot_B601_DM\3D_Printed_Parts\D435_Gemini2_Mount.step` | `F6B7FF37B690C0B24BDDBAFB2825A7C365F9F49B064CC83634C1317961E08274` |
| D405/305 mount | `F:\China Graduate Future Flight Vehicle Innovation Competition\80_third_party\vendor\reBot-DevArm\hardware\reBot_B601_DM\3D_Printed_Parts\D405_305_Mount.step` | `9FD1239427F073B401A9CF0978983936BA85B8814326E954AE08C5A52F7687D8` |
| UVC32 mount | `F:\China Graduate Future Flight Vehicle Innovation Competition\80_third_party\vendor\reBot-DevArm\hardware\reBot_B601_DM\3D_Printed_Parts\UVC32_mount.step` | `D731A9F269CF9411097C603972904D6B5568DABB549152CBFDDC47E78D3DF978` |
| vendor README | `F:\China Graduate Future Flight Vehicle Innovation Competition\80_third_party\vendor\reBot-DevArm\README.md` | `0E626CE952634A1F143B58252117DA5F8DD44A3F16EEAD0CDACCA36DB1AF5D47` |
| vendor 中文 README | `F:\China Graduate Future Flight Vehicle Innovation Competition\80_third_party\vendor\reBot-DevArm\README_zh.md` | `4EBB457E3A3FC1E53089C041A1A0D3A448E1640E440925652D14120F4AA9AA63` |

## 6. 配置管理说明

`F3_P5_INPUT_MANIFEST.csv` 记录的原始 P4D 文件位于当前不存在的隔离路径，并期望 SHA-256 `657181E6F12ECDC9AB8019E63E00105F61806C617BD65382C5AD9EAC59BD65DF`；当前 `40_evidence` 副本 SHA-256 为 `697E806E...58DFC3B`，不是字节级同一文件。该差异可能来自复制时的编码或换行变化，不得静默解释为同一受控字节流。

本裁决不依赖当前 P4D 副本单独成立：P5B 定义、P5B gate、P5B matrix、P5D gate 和 P5 terminal closure 已重新陈述并由 terminal manifest 锁定关键竞赛接口。若后续恢复原始隔离源，应另做 byte-level provenance reconciliation，但不得因此把工作释放方向改回 `+Z`。

## 7. 变更规则

以下任一变化必须新建 V4 ECR/authority ruling，不得直接编辑本裁决中的受控值：

- 将 HDRM 工作释放方向改为非 `-X`
- 将 `+Z` 用于非地面拆装/手动解锁动作
- 将行程改为非6 mm
- 选择实际 HDRM 产品或宣称采购/试验闭环
- 将 `SERVICE_CAMERA` 从 `UNSELECTED` 改为具体型号
- 将条件性 D405 路线升级为发布状态
- 将任一 neutral skeleton/keepout 升格为物理或飞行硬件

