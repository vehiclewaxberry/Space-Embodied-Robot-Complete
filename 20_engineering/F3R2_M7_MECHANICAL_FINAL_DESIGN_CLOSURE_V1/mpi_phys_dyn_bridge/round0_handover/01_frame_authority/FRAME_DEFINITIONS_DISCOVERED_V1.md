# FRAME_DEFINITIONS_DISCOVERED_V1（AGENT-1 / MPI-FB-01 / round0 handover / 01_frame_authority）

- 生成时间：2026-08-23（宿主机本地钟，Asia/Shanghai）
- 范围：B601 安装语义双轨（WP11 physical placement ↔ ODR-01 T_SM dynamics frame）桥接工作包 MPI-FB-01 的 frame 定义全枚举。**只读盘点**：本轮未修改/重生成任何 accepted 资产；未启动任何 CAD/FEA 进程；所有数值均可从所引文件复核。
- 授权上下文：ODR-43（DUAL_FRAME_EXPLICIT_BRIDGE）与 ODR-44（APPROVE_BOUNDED_DETAILED_DESIGN）。
- 约定：除非另注，平移单位以源文件为准（标注 mm 或 m），矩阵为行主序 4x4 齐次变换 `T_parent_child`（子系坐标 → 父系坐标，旋转列 = 子系轴在父系中的表达，与 M4/M6 约定一致）。
- 命名提示：本工作包内 MPI-FB-01..08 指**安装桥接**工作包，与 Route-C 的 minimum product inputs 同名不同义。

---

## 1. 根/参考系

### 1.1 `I`（惯性/世界系）
- 定义：恒等参考；t=0 静态快照。
- 来源：`40_evidence/artifacts/visualization/tables/frame_registry_v1.csv` 行 2（sha 637DBDE5FF4E）；`20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/coordinate_frame_definition_v0.md`（sha 6AFCB4FB6F1C）框架表。
- 状态：reference definition。

### 1.2 `S`（服务星体/几何系，12U 几何中心）
- 4x4：恒等。
- 来源：`DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml:51-59`（status FROZEN_V1）；`frame_tree_v1.yaml:9`；`spacecraft_assembly_frame` 与 `S` 为冻结恒等别名（`DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml:8-17`，FROZEN_EXACT_ALIAS_NO_TRANSFORM_UNCERTAINTY）。
- 状态：FROZEN_V1。

### 1.3 `B`（free-flyer 母体基座系）
- 4x4：默认恒等（T_SB），CoM 偏置未实测。
- 来源：`coordinate_frame_definition_v0.md` 框架表行 `B`；`frame_registry_v1.csv` 行 4（default/unverified）。
- 状态：默认/未验证。

---

## 2. 动力学轨（DYNAMICS rail）—— ODR-01 T_SM

### 2.1 `M` / `M_DYNAMICS`（臂安装面/动力学原点）
四处等价定义 + 一处 owner 裁决 + 一处求解器硬编码：

1. **原始数值冻结**：`coordinate_frame_definition_v0.md:70-99`（§3.1，nominal_frozen_v1，decision D-2）
   - `t_SM = [185.25, 0, 0] mm`；`R_SM = R_y(+90°) = [[0,0,1],[0,1,0],[-1,0,0]]`
   - 轴：`+Z_M=+X_S`（reach），`+Y_M=+Y_S`，`+X_M=-Z_S`；URDF 写法 `xyz="0.18525 0 0" rpy="0 1.5707963 0"`；quat wxyz `[0.70710678,0,0.70710678,0]`
   - 明示：design nominal，NOT measured。
2. **几何 SSOT**：`20_engineering/config/geometry/frame_tree_v1.yaml:10-19`（sha 958BFF23BF83）——同一组数值；M4 权威优先级 rank 1（`DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml:19-23`）。
3. **M4 数字样机 frame tree**：`DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml:61-70`（sha 67293323A452）
   - `M_DYNAMICS` rows：`[0,0,1,185.25]; [0,1,0,0]; [-1,0,0,0]; [0,0,0,1]`（mm），status FROZEN_V1，role "accepted_dynamics_origin_no_physical_entity"。
4. **Owner 裁决 ODR-01**：`M7_OWNER_DECISION_REGISTER_V1.yaml:10-20`（sha F5B1572C0CFC）——T_SM=[185.25,0,0]mm+Ry(90°) 是**唯一**动力学安装参考；198.0/208.0/210.405 mm 为几何特征栈，不得成为第二动力学系。WP10 V5_R2 逐字携带（`MECH_DYNAMICS_INTERFACE_V5_R2.yaml:55-72`，sha 9B6D8025D331）。
5. **求解器硬编码**：`30_simulation/sim_05_free_floating_arm/b601_model.py:42-46,89-90,191-198`（sha 3E2B451476F4）——`T_SM_t=[0.18525,0,0]` m，`fk()` 默认 `T_base=T_SM_4x4()`。

### 2.2 `A0`（URDF base frame = base_link）
- 定义：`arm_b601_v1.urdf` 头注释（行 3-11，sha 1BC2B7483CD8）："Base frame A0 = base_link; mount: T_MA0 = identity nominal, +Z_A0 = +Z_M = reach direction"。
- 即：URDF 自身不含安装变换；A0 与 M 恒等绑定是**名义约定**（scene manifest 行 111-112 同此约定，confidence 注明 "physical mounting not yet measured"）。

---

## 3. 物理轨（PHYSICAL rail）—— WP11 / F3R2 物理安装

### 3.1 `B601_ARM_BASE_PHYSICAL`（物理臂基座 = WP11_PHYSICAL_GEOMETRY_CONTEXT）
同一物理安装有**四种数值拼写**，必须区分（WP11-F-03 carried open item）：

1. **M4 frame tree（全精度）**：`DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml:78-87`，status FROZEN_F3R2_MAPPING
   - rows（mm）：`[0,0,1,208.0]; [0.422618483193,0.906307683772,0,0]; [-0.906307683772,0.422618483193,0,0]; [0,0,0,1]`
   - `clocking_about_positive_X_S_deg: 25.000014`
2. **WP11 标定 frame_context（全精度）**：`B601_CAD_URDF_GEOMETRY_CALIBRATION_V1.yaml:19-40`（sha 7463C1309C35）——同一矩阵；并注明 "dynamics_M_frame_is_separate: ODR-01 T_SM=[185.25,0,0]+Ry(90°) remains the single dynamics mounting reference"。
3. **e21 权威合同假设（全精度）**：`E21_AUTHORITY_CONTRACT_V1.yaml:25-32`（sha 7D2E0792B3FF）——`WP11_PHYSICAL_GEOMETRY_CONTEXT.transform_S_A0_rows`（m）：`[0,0,1,0.208]; [0.422618483193,0.906307683772,0,0]; [-0.906307683772,0.422618483193,0,0]; [0,0,0,1]`，selected=false。
4. **F3R2 位姿 SSOT / V5R 中性包（6 位舍入）**：`F3R2_ARM_INITIAL_POSE.yaml:12-39`（sha D6E33CB5993B）与 `SYSTEM_FRAME_TREE.yaml:44-64`（sha 71A9FFFAA30A）——平移同为 208.0 mm，但 clocking 拼写为 `0.422618/0.906308`（= 24.999981252°，与全精度差 3.28e-5° ≈ 0.12 角秒）。M5 链路定位矩阵（`B601_CAD_MESH_FRAME_DECISION_V1.json`，sha 2A99484C6CE5）经本代理数值核算同为 24.999981252°——即 M4 命名位姿复算链与 M5 网格定位链消费的是**舍入拼写**。

旋转结构（本代理 numpy 核算，NON-AUTHORITATIVE_PENDING_MPI-FB-02）：`R_phys = Rx_S(+25.000014°) · R_y(+90°)`（残差 5.0e-13），即物理安装 = 动力学旋转后再绕星体 +X_S 钟摆 25.000014°；平移差 = 208.0 − 185.25 = 22.75 mm 沿 +X_S。

### 3.2 语义裁决记录
- M4 语义裁决（`DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml:36-48`）：M_DYNAMICS(185.25) 与 B601_ARM_BASE_PHYSICAL(208.0) **保留为不同 frame**；上游文件的 base-link 措辞重叠；M4 不做别名；消费侧别名保持 HOLD。消费规则（行 166-172）："Never substitute M_DYNAMICS for B601_ARM_BASE_PHYSICAL."
- WP11 receipt（`receipt.json`，sha 83E36583E370）：verdict COORDINATE_REGISTRATION_DIFFERENCE_NOT_VERSION_MISMATCH；disposition O2-A（URDF=运动学/质量权威，CAD=物理几何权威，D_i=桥）。

---

## 4. 实测轨（GEOMETRY / as-built rail）—— M3R 刚性栈

### 4.1 站点栈 `M3R_TSM_PHYSICAL_STACK`
- 来源：`M3R_TSM_PHYSICAL_STACK.yaml:1-32`（sha 172F3603E458）。
- 站点（mm，沿 +X_S）：185.25 = accepted URDF base frame = **M_FRAME_DYNAMICS_ORIGIN（immutable）**；198.0 = adapter plate external face；208.0 = central boss physical installation face（PHYSICAL_INSTALLATION_FACE）；210.405 = B601 as-built fastener end plane（4×HM4-75 螺钉端面，非连续法兰）。
- 偏置（mm）：M→adapter 12.75；adapter→installation 10.0；M→installation 22.75；installation→fastener 2.405；M→fastener 25.155。
- pattern center yz (mm)：[0.015994151, −0.086366070]；clocking about x：25.000014°。
- ruling：四个站点是**同一刚性栈上的不同语义**，不是同一界面的竞争值。

### 4.2 `M3R_LOCAL`（M3R 工作 BRep 局部系）
- 来源：`DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml:89-97`。
- rows（mm）：`[0,0,1,208.0]; [0.422618483193,0.906307683772,0,0.015994151]; [-0.906307683772,0.422618483193,0,-0.086366070]; [0,0,0,1]`。
- 局部 +z 朝 B601；status PHYSICAL_STACK_AND_AS_BUILT_PATTERN_APPLIED。
- 与 B601_ARM_BASE_PHYSICAL 的差别：y/z 多了实测 pattern-center 偏置（0.015994151, −0.086366070 mm）。

### 4.3 `B601_FASTENER_END_PLANE`
- 来源：`DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml:99-104`。
- origin_S_mm [210.405, 0.015994151, −0.086366070]；orientation = same_as_M3R_LOCAL；status MEASURED_COMPETITION_DATUM_NOT_OEM。

### 4.4 `M3R_TSM_FRAME_TO_FLANGE_TRANSFORM`（M_FRAME → as-built datum）
- 来源：`M3R_TSM_FRAME_TO_FLANGE_TRANSFORM.json:1-20`（sha 29303BA65DFD）。
- translation_xyz_mm [25.155, 0.015994151, −0.08636607]；rotation_about_x_deg 25.000014；旋转阵 = Rx(25.000014°)。
- **消费警告（本代理数值核算）**：该 JSON 的平移按"栈轴向（M 原点处的 S 轴表达）"书写；若按标准 `T_M_child` 齐次合成（T_dyn(mm) @ T_M_flange），datum 落点与 M4 的 M3R_LOCAL 差 25.07 mm。即该文件的合成约定本身需要在 MPI-FB-02 中钉死，禁止默读。
- `accepted_urdf_modified: false`。

### 4.5 `ADAPTER_PLATE_EXTERNAL_FACE`
- 来源：`DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml:72-76`：origin_S_mm [198.0,0,0]，orientation inherited_axial_station_only，status AXIAL_STATION_FROZEN_GEOMETRIC_ENTITY_NOT_PRESENT_IN_M4。
- 历史注记：`40_evidence/c1_evidence/F3_P3_T_SM_DUAL_TRACK.md`（sha E1FB9374DB0B）曾把 198 mm 当"显示轨 T_SM"（Mode A）与 185.25 mm 动力学轨（Mode B）双轨保留；该语义已被 ODR-01 + M3R 栈取代（198.0 = 适配板外面站点，不是安装面）。

### 4.6 V5R 中性包 datum 链
- 来源：`SYSTEM_FRAME_TREE.yaml:13-43`。
- `M_FRAME`：transform TBD — HOLD_ROOT_TO_M_FRAME_NOT_REASSERTED_BY_NEUTRAL_PACKAGE。
- `B601_AS_BUILT_PATTERN_DATUM`：parent=M_FRAME，translation [25.155,0.015994151,−0.08636607]mm + Rx 25.000014°（来源即 4.4）。
- 注意：datum 挂在**未断言的** M_FRAME 之下——父链未闭合，消费时必须显式补全。

---

## 5. URDF 运动链帧（L0 运动学权威）

来源：`arm_b601_v1.urdf`（sha 1BC2B7483CD8）与 `SYSTEM_FRAME_TREE.yaml:111-263`（ACCEPTED_URDF_FRAME_AUTHORITY）。

- `base_link`（= A0，见 2.2）→ `link1_frame`：joint1，xyz_m [−8.416e-05,0,0.08465]，rpy 0，轴 +z，revolute ±2.8 rad。
- `link2_frame`：joint2，[0.020084,0.031625,0.05555]，rpy [−1.5708,0,0]，轴 −z。
- `link3_frame`：joint3，[−0.264,0,0]，轴 +z。
- `link4_frame`：joint4，[0.2426,−0.054,−0.001625]，轴 +z。
- `link5_frame`：joint5，[0.078308,−0.0375,−0.03]，rpy [−1.5708,0,0]，轴 +z。
- `link6_frame`：joint6，[0.023692,0,0.04]，rpy [0,1.5708,0]，轴 +z。
- `gripper_link_frame`：gripper_joint（fixed），[0,0,0.15971]，rpy [0,−1.5708,0]。
- `gripper_left/right_frame`：prismatic，[−0.042091,±2.7531e-05,∓1.3031e-05]，轴 x，行程 0..0.0715 m。

派生帧：
- `LINK6_Q0`（`DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml:120-128`）：q0 下 accepted URDF 链结果（mm 级 4x4，DERIVED_FROM_HASH_BOUND_URDF_AT_Q0）——注意其数值是在**物理安装**（208.0+25.000014°）下计算的。
- `GRIPPER_R1_PALM`（同文件 130-138）：parent LINK6_Q0，恒等，palm_only，INSTALLED_DIGITAL_PROTOTYPE。
- `E`（末端/捕获工具系）：`frame_registry_v1.csv` 行 6（M 的子系，[0.1,0,0.76475]m 显示位姿）；`frame_tree_v1.yaml:22`（parent arm_link7，Z_E 接近方向）；URDF gripper_joint 原点。

---

## 6. 帆板/机翼帧

- `F_L`：`frame_tree_v1.yaml:20` 与 `DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml:106-111`：origin [−56.75,+113.15,0]mm，Y_F=+Y_S，Z_F=+Z_S；full_orientation_matrix=null（HOLD）。
- `F_R`：origin [−56.75,−113.15,0]mm，Y_F=−Y_S，Z_F=+Z_S；full orientation HOLD（同上 112-117）。
- `left_wing_hinge_axis` / `right_wing_hinge_axis`（V5R BRep 探测）：`SYSTEM_FRAME_TREE.yaml:65-86`：点 [−61.0,±143.15,0]mm，轴 +X。
- R2 铰链语义： hinge axes parallel to X_S（`MECH_DYNAMICS_INTERFACE_V5_R2.yaml:166` 与 SOLAR_ARRAY_R2 包）。

## 7. 目标/抓取帧（场景级，不进安装桥）

- `T`（22 kg 目标星）：`frame_registry_v1.csv` 行 7：[1.24,0,−0.1]m；M6 候选变换 `CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml:215-227`（DISPLAY_ONLY）。
- `D`（150 kg 碎片）：行 8：[1.61,0,−1.05]m；M6 候选 228-239 行。
- 抓取点 `C_sat` [290,0,0]mm in T / `C_deb` [660,0,950]mm in D（`frame_tree_v1.yaml:23-24`）；`G1/G2/G3`（`frame_registry_v1.csv` 行 9-11）。
- M4 中 `TARGET_SATELLITE_T` / `TARGET_DEBRIS_D` 均 parent=null、T_S=null（INDEPENDENT_SCENARIO_FRAME_RELATIVE_POSE_HOLD，行 156-164）。

## 8. 显式 HOLD / null 帧（禁止填 0）

来源 `DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml` 与 `SYSTEM_FRAME_TREE.yaml`：
- `SPACECRAFT_LOAD_BRIDGE`：T=null，UNRESOLVED_STRUCTURAL_LOAD_PATH_DISCONTINUITY_HOLD（M4 行 146-149；星体 proxy 止于 185.25 而 M3R B-rep 起于 ~196，10.75 mm 净空无授权桥接几何——行 45-47）。
- `ARM_HDRM`：T=null，UNRESOLVED_GLOBAL_TRANSFORM_AND_CLOCKING_HOLD（行 151-154）。
- `SENSOR_PACKAGE`：候选 [190.25,0,80]mm，UNRESOLVED_CANDIDATE_REJECTED_M3R_POSITIVE_PENETRATION（行 140-144）。
- `camera_optical_frame`：TBD HOLD_CAMERA_SELECTION_AND_CALIBRATION（V5R 行 87-90）。
- `gripper_contact_left/right`：SEMANTIC_CONTACT_FRAME，PROVISIONAL_FOR_SIM13_STATE_INTERFACE（V5R 行 91-98）。
- keep-out 帧（CAMERA/CABLE/ARM_HDRM_RELEASE_SWEEP）：语义包络，非数值变换（V5R 行 99-110）。

---

## 9. 两条 e21 消费路径（双轨事实的机器证据）

来源：`E21_NINE_CONFIGURATION_ARM_PLACEMENT_AUDIT_V1.json`（sha FCCE9EFBD401）、`E21_TWO_PLACEMENT_RIGID_DYNAMICS_SENSITIVITY_V1.json`（sha 7AB105046E58）、两个 lane summary（sha C575F1D4F4CD / 55DC3E9E36FC）。

- **ODR01_DYNAMICS_T_SM 车道**：transform_S_A0 = [0,0,1,0.18525; 0,1,0,0; −1,0,0,0; 0,0,0,1]（m）。C07/M07 峰值基座姿态偏差 **29.041965867604112°**；初始质量特性与 V3_R2 C07 逐位闭合（误差 0/4.44e-16）。
- **WP11_PHYSICAL_GEOMETRY_CONTEXT 车道**：transform_S_A0 = [0,0,1,0.208; 0.422618483193,0.906307683772,0,0; −0.906307683772,0.422618483193,0,0; 0,0,0,1]（m）。峰值 **29.41085537835705°**；对 V3_R2 C07 的 CG 偏差 3.524348142565558 mm。
- 差值 **0.3688895107529362°**（`branch_delta_is_uncertainty=false`，`standard_uncertainty=null`）。
- 九构型审计（2 账本 × 9 构型 × 2 假设 = 36 评估）：**C01..C06 臂成员匹配 WP11 物理轨（残差 ~1.1e-4 mm，恰为舍入钟摆拼写差），C07..C09 匹配 ODR01 动力学轨（残差 0）**；verdict `MIXED_LEDGER_ARM_PLACEMENT_CONTEXT_DETECTED__CONSUMPTION_SEMANTICS_UNRESOLVED_HOLD`。
- 账本侧根因链：C01..C06 ← `B601_NAMED_POSE_REVALIDATION_V1.json`（base_transform_source = F3R2_ARM_INITIAL_POSE mount，物理轨、舍入拼写）；C07..C09 ← 同一文件 `pregrasp_scene_candidate`（源自 `scene_manifest_v1.yaml` 的 A0==M@T_SM，动力学轨）。

## 10. 枚举结论（供 MPI-FB-02 直接消费）

1. 两轨的**显式 4x4 均已冻结在多处**且互相一致到拼写精度：动力学轨 [185.25mm + Ry90]；物理轨 [208.0mm + Rx_S(25.000014°)·Ry90]。桥接可解析封闭（见 MPI01_BRIDGE_DERIVATION_PLAN_V1.md）。
2. 第三语义层（M3R as-built datum：210.405 + yz 偏置 + 25.000014°）是**实测竞争基准**，与物理安装面（208.0，无 yz 偏置）不同；桥接不包括它，任何使用需另立裁决。
3. 数值拼写分裂（25.000014° vs 24.999981252°）已在 WP11-F-03 登记；影响量级 ~1.1e-4 mm（C01 臂 CG），MPI-FB-02 必须钉死唯一拼写，禁止静默混用。
4. 混合消费在**同一账本内部**（V2/V3_R2 的 C01..C06 vs C07..C09），不是账本间差异；ODR-44 冻结 V3_R2 为 accepted，桥接后的重绑定只能产 candidate（MPI-FB-06/07）。
