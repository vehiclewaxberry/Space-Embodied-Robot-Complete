# B5.1R1 Phase 2 机器人与航天器机械工程执行映射

状态：`PREPARED_NOT_AUTHORIZED`

日期：2026-08-01  
对象：B601 空间机械臂、航天器承力接口、收拢释放机构、整星机械集成、结构/质量闭环和控制交接  
性质：当前文件是来源驱动的执行映射，不是 CAD 生成、Gate 通过或总体构型裁决证据。

## 0. 执行边界与当前结论

单坐标诊断件已经在独立授权的可见 SolidWorks 2024 会话中完成冷重开、持久化回读和一次受控保存，
当前 Gate 为 `SINGLE_COORDINATE_SYSTEM_PERSISTENCE_PASS`；该次授权已消耗完毕。该动作不是由本文件执行，
本文件也不授予下一次可见启动。当前可继续的是 G1 离线输入协调；S01 最终 Master Skeleton 原生创建必须取得新的明确授权。

本文件只完成以下工作：

- 冻结 Phase 2 使用的 accepted URDF 真值链；
- 把附件要求的六个机械闭环映射到当前候选目录的真实输入、缺件和 Gate；
- 提出 G0 已通过后、完成 G1 前置协调才可签发的最小 Phase 2A 原生建模授权包；
- 标出两项必须先裁决的合同冲突；
- 保留所有 `TBD / HOLD / PROVISIONAL_TBD`。

本文件未执行以下动作：

- 未启动 SolidWorks；
- 未创建或修改任何 `.SLDPRT`、`.SLDASM` 或 `.SLDDRW`；
- 未修改当前总 Gate、总进度报告或工件索引；
- 未裁决 H9；
- 未选择适配器 A/B/C；
- 未给予 H10、T005、结构、控制或物理资格任何通过信用。

读取本文件时应重新读取当前机器 Gate。若本文件与更新后的 Gate 冲突，以更新后的机器 Gate 为准。

## 1. Phase 2 权威输入快照

| 权威内容 | 当前路径 | SHA-256 | 本阶段用途 |
|---|---|---|---|
| 新机械工程指令 | `00_BASELINE/AUTHORIZATION_PACKAGE/B51R1_COLD_REOPEN_AUTHORIZATION_20260801/B51R1_COLD_REOPEN_AND_MECHANICAL_ENGINEERING_DIRECTIVE.txt` | `C78926131EE309B67F652197FD839FEBDBB28E5D9D99EA45EBF21636CEEABAE2` | 六闭环范围和冷重开先决动作 |
| accepted URDF | `00_BASELINE/AUTHORITIES/accepted_urdf/arm_b601_v1.urdf` | `1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164` | link、joint、parent/child、type、origin、axis、limit、mass、inertia 唯一权威 |
| accepted URDF 锁定副本 | `00_BASELINE/PARENT_LOCKED_INPUTS/ACCEPTED_URDF/arm_b601_v1.urdf` | `1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164` | 与主权威逐字节一致的复核副本 |
| q0 轴导出 | `00_BASELINE/AUTHORITIES/accepted_urdf/q0_joint_axes.csv` | `73F1E674A57F3EB7863BEBF32D497DF8829E4348DBB84C6A1A796106036845C0` | A0/q0 轴向见证，不替代 URDF |
| 耐久测量 Gate | `01_MEASUREMENT/B51R1_DURABLE_DATUM_MEASUREMENT_FINAL.json` | `94400C1E282A9B35084E68B7A1B53DCC41BF33113D908C7895D0B73C672904FB` | 主结构、面板层和 G07/G08 足印来源 |
| Master Skeleton V2 datum 合同 | `02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2_DATUM_REGISTER.yaml` | `41A769163D7FE9066DDAC0A6E36E33A22AC9D33823F8CC47151515E8AC0FBC6E` | 当前原生 datum 命名与几何合同 |
| Stage A 原生参考件 | `02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT` | `5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B` | 只读保护输入；不是最终 Skeleton |
| Stage A 回读 | `02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2_STAGE_A_READBACK.json` | `7537D17F87EA55911160B63615F590AB235ACB04F51AA797B72F8F2C891D4967` | 16/16 参考特征、3 配置、0 实体、0 外部引用证据 |
| Carrier 架构合同 | `03_CAD/10_KINEMATIC_CARRIERS/B51R1_CARRIER_ARCHITECTURE_CONTRACT.md` | `3998412F0FEF3DD6E0305877A4D72831A176DF6538764576608A8510B8D29112` | 运动配合原则和禁止项 |
| Carrier 计划表 | `03_CAD/10_KINEMATIC_CARRIERS/B51R1_CARRIER_MAP.csv` | `D0C1E0A02A8BA7A367D45176E8BC1F69151414C4A8EF2A6568AF77291EBBAD63` | 10 个 carrier 的拓扑角色 |
| 原生关节合同 | `03_CAD/10_KINEMATIC_CARRIERS/B51R1_NATIVE_JOINT_REGISTER.csv` | `D9C053704011B8758C92A795F18CAD0ADC371829DF39DF57449CF6C1B320F116` | 9 个关节和拟用 Mate 名称 |
| 原生驱动映射 | `03_CAD/10_KINEMATIC_CARRIERS/B51R1_NATIVE_DRIVER_MAPPING.csv` | `0331807A238B6BD4765CD711382F5B24C36C00304BE77A865CCF2946D7799751` | URDF q 到原生 limit mate 的候选映射 |
| 精确 Carrier 注册表 | `04_CONFIGURATION/B51R1_CARRIER_REGISTER.csv` | `D3FD0BA28BAD9F4E0819DCDABD157903921126485BE7BAEA4ACA2B781C41D8FC` | 文件名、特征名、质量/BOM 属性和创建状态 |
| URDF—Carrier frame 映射 | `04_CONFIGURATION/B51R1_URDF_CARRIER_FRAME_MAPPING.yaml` | `4D5488A1A95F0CF052194908C6D8F3C79417F4FFA6EC3D06CB598D19AA19EB43` | 10 link / 9 joint 完整离线映射 |
| 适配器贸易框架 | `03_CAD/30_INTERFACE_ADAPTER/B51R1_INTERFACE_CONCEPT_TRADE_MATRIX.csv` | `FCBCFFB9B8DC2BEF6A776957A8C0356F83CAF9250DFDA16109568506A4D5A6E3` | A/B/C 概念比较框架，尚无评分权威 |
| 适配器当前判定 | `03_CAD/30_INTERFACE_ADAPTER/B51R1_INTERFACE_TRADE_DECISION.json` | `03D8C9826673CD4B05D1C603EA439E58826996FCDE0F057C0BBF8E062F9C2DDE` | `NO_DOWNSELECT` |
| H10 当前状态 | `05_H10/B51R1_H10_PHASE1_STATUS_CURRENT.json` | `DC25010418B6A49D619C149B60BA2DB9435E5B251EC10FF163240D636C6F6440` | 0/28 闭合的当前机器状态 |
| T005 当前状态 | `06_T005/B51R1_T005_EXECUTION_READINESS_CURRENT.json` | `8E43C9DFE82AF1EC5572E1916E7265717505688143D743C5A4466852E576B7F4` | `NOT_READY_NOT_RUN` |
| 单坐标系当前 Gate | `07_VERIFICATION/B51R1_SINGLE_CS_DIAGNOSTIC_GATE.json` | `6D0C27E154E3F1ACA150EA35B2A945EC257D1CB2898A06AB5AC9448A9AF3EC5E` | `SINGLE_COORDINATE_SYSTEM_PERSISTENCE_PASS`；仅关闭 G0，不授权原生建模 |

## 2. accepted URDF 拓扑和质量真值

机器人名：`arm_b601_v1`  
拓扑：`10 links / 9 joints / 6R + 1 fixed + 2 independent P`  
分支父节点：`gripper_link`  
accepted URDF 模型质量合计：`4.6955559493429862 kg`

### 2.1 十个 link

| 序号 | accepted link | URDF mass (kg) | 计划原生 Carrier |
|---:|---|---:|---|
| 0 | `base_link` | 0.83660000 | `B51R1_CARRIER_base_link.SLDPRT` |
| 1 | `link1` | 0.16130000 | `B51R1_CARRIER_link1.SLDPRT` |
| 2 | `link2` | 1.32660000 | `B51R1_CARRIER_link2.SLDPRT` |
| 3 | `link3` | 0.83530000 | `B51R1_CARRIER_link3.SLDPRT` |
| 4 | `link4` | 0.52000000 | `B51R1_CARRIER_link4.SLDPRT` |
| 5 | `link5` | 0.38300000 | `B51R1_CARRIER_link5.SLDPRT` |
| 6 | `link6` | 0.36630000 | `B51R1_CARRIER_link6.SLDPRT` |
| 7 | `gripper_link` | 0.181800159145243 | `B51R1_CARRIER_gripper_link.SLDPRT` |
| 8 | `gripper_left` | 0.0423278952416158 | `B51R1_CARRIER_gripper_left.SLDPRT` |
| 9 | `gripper_right` | 0.0423278949561274 | `B51R1_CARRIER_gripper_right.SLDPRT` |

Carrier 必须设置 `MODEL_ROLE=KINEMATIC_CARRIER`、`CAD_MASS_CONTRIBUTION=ZERO`、
`BOM_EXCLUDE=TRUE`、`DYNAMIC_AUTHORITY=ACCEPTED_URDF`。CAD 自动质量不得覆盖上表。

### 2.2 九个 joint

| joint | type | parent → child | origin xyz (m) | origin rpy (rad) | axis（joint frame） | URDF lower/upper | q0 语义 |
|---|---|---|---|---|---|---|---|
| `joint1` | revolute | `base_link → link1` | `-8.416E-05 0 0.08465` | `0 0 0` | `0 0 1` | `-2.8 / 2.8 rad` | interior |
| `joint2` | revolute | `link1 → link2` | `0.020084 0.031625 0.05555` | `-1.5708 0 0` | `0 0 -1` | `-3.14 / 0 rad` | upper numeric limit |
| `joint3` | revolute | `link2 → link3` | `-0.264 0 0` | `0 0 0` | `0 0 1` | `-3.14 / 0 rad` | upper numeric limit |
| `joint4` | revolute | `link3 → link4` | `0.2426 -0.054 -0.001625` | `0 0 0` | `0 0 1` | `-1.87 / 1.57 rad` | interior |
| `joint5` | revolute | `link4 → link5` | `0.078308 -0.0375 -0.03` | `-1.5708 0 0` | `0 0 1` | `-1.57 / 1.57 rad` | interior |
| `joint6` | revolute | `link5 → link6` | `0.023692 0 0.04` | `0 1.5708 0` | `0 0 1` | `-3.14 / 3.14 rad` | interior; mate flip probe required |
| `gripper_joint` | fixed | `link6 → gripper_link` | `0 0 0.15971` | `0 -1.5708 0` | N/A | N/A | exact fixed transform |
| `gripper_joint1` | prismatic | `gripper_link → gripper_left` | `-0.042091 2.7531E-05 -1.3031E-05` | `0 0 -1.5708` | `1 0 0` | `0 / 0.0715 m` | `MIN_NUMERIC` only |
| `gripper_joint2` | prismatic | `gripper_link → gripper_right` | `-0.042091 -2.7531E-05 1.3031E-05` | `0 0 1.5708` | `1 0 0` | `0 / 0.0715 m` | `MIN_NUMERIC` only |

两个 P 关节必须独立驱动。`0.0715 m`是各自 accepted joint coordinate 的上界；它不自动证明
“每爪 ±71.5 mm”“总开度 143 mm”或“q0 为机械闭合”。物理指爪位移、接触中心和总开度必须由
挂接后的接触面几何和独立 P 位移共同计算。

URDF 中的 `effort` 和 `velocity` 字段只能作为 accepted 文件字段保存；没有供应商和单位语义证据时，
不得把它们升级成额定转矩、峰值转矩、额定转速、推力或热限制。

## 3. Master Skeleton datum 合同

当前 V2 datum 合同要求同时保留：

- `CS_S`：航天器结构父坐标系；
- `CS_M_DYNAMICS_X185_25`：X=185.25 mm 动力学/PDR 安装轨；
- `CS_M_DISPLAY_X198`：X=198 mm V2.2 展示集成轨；
- `CS_A0_CLOCKED_25_DEG`：相对动力学安装轨绕 X 旋转 25°的工程候选；不是 J1 零位；
- `PLN_TASK_FACE_X183`：X=183 mm 任务面；
- 主承力表面：Y/Z=`±110.15 mm`；
- 可拆面板外表面：Y/Z=`±113.15 mm`，无主承力信用；
- 四条纵梁轴：Y/Z=`±101.65 mm`；
- 160 × 160 mm 安装设计目标；
- Ø100 mm 中央禁入通道设计目标；
- `COMMON_CANONICAL`、`MODE_A_EVALUATION`、`MODE_B_EVALUATION` 三配置；
- G07/G08 的四个 Z=113.15 mm 面板层足印窗口；
- `KO_SOLAR_SWEEP`、`KO_ARM_RELEASE`、`KO_HARNESS`、`KO_SERVICE_ACCESS`，当前几何均为 `TBD/HOLD`。

### 3.1 必须先解决的 datum 冲突

旧父级文件
`00_BASELINE/PARENT_LOCKED_INPUTS/PARENT_DATUM_REGISTER/B51_MASTER_SKELETON_DATUM_REGISTER.yaml`
写有 `longeron_center_abs_yz: 105.65`。当前耐久测量、Master Skeleton V2 构建合同和 V2 datum
注册表均把实际纵梁轴定义为 `±101.65 mm`，并把 `±110.15 mm`定义为主承力表面。

Phase 2A 在创建最终 Skeleton 前必须生成独立的 datum 协调收据，至少包含：

- 冲突文件的路径、字节数和 SHA-256；
- `101.65 / 105.65 / 110.15 / 113.15`各自的几何语义；
- 明确声明旧 `105.65`字段不得作为原生纵梁轴；
- 确认最终原生特征使用当前 V2 datum 合同；
- 不改写或删除历史父级输入。

在该收据通过前，不得凭经验任选一个数值。

### 3.2 必须先解决的 Carrier 命名冲突

`B51R1_CARRIER_ARCHITECTURE_CONTRACT.md`使用通用名：

`CS_LINK / CS_IN_<JOINT> / CS_OUT_<JOINT> / AXIS_<JOINT>_POS / PLN_<JOINT>_Q0 / CS_VISUAL`

而较具体的 `B51R1_URDF_CARRIER_FRAME_MAPPING.yaml`和
`B51R1_CARRIER_REGISTER.csv`使用：

`CS_LINK_<link> / CS_PARENT_JOINT_<joint> / CS_CHILD_JOINT_<joint> / AXIS_<joint> / PLANE_ZERO_<joint> / CS_VISUAL_MOUNT_<link>`

两套名称不能同时被当作唯一 CAD API 键。Phase 2A 必须先生成
`B51R1_PHASE2_FEATURE_NAMING_FREEZE.yaml`，选择一套唯一实体名，并给另一套建立只读别名映射。
建议采用 04_CONFIGURATION 中逐 link/joint 展开的名称作为原生名称，因为它已枚举全部 10 link 和 9 joint；
该建议本身不构成授权或命名冻结。

## 4. 六个机械设计闭环的可执行映射

### 闭环 1：原生运动机构

输入：accepted URDF、q0 轴导出、V2 datum 合同、命名冻结、冷重开持久化 PASS。  
输出：

1. `02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2.SLDPRT`；
2. 上表十个 Carrier `.SLDPRT`；
3. `03_CAD/10_KINEMATIC_CARRIERS/B51R1_CARRIER_CHAIN_NATIVE.SLDASM`；
4. J00 到 J09 独立保存点；
5. 6 个原生 Limit Angle、1 个精确 fixed、2 个独立 Limit Distance；
6. Carrier-only `T005-A0/B0/C0`证据。

退出条件：10/10 Carrier 冷重开、外部引用 0、CAD 质量贡献 0；9/9 joint 具有唯一原生驱动；
q0 同文档复位；正负方向与 accepted FK 一致；人类批准的 FK/角度/位移容差已绑定。

禁止：`Move Component`保存姿态、`Transform2`作为驱动、`Fix Component`冒充 fixed joint、
一个夹爪宽度参数冒充两个 P、Mate Controller 作为真值、导入面/边作为运动 Mate。

### 闭环 2：航天器承力接口

当前输入状态：A/B/C 贸易框架已存在，但评分和排序禁用，`downselect=null`。H9 仍为
`HUMAN_DECISION_REQUIRED`，未绑定 launcher/deployer ICD。

输出顺序：

1. H9 人工选择，或书面批准的 Mode A/Mode B 双分支继续；
2. 适配器 A（双横梁）、B（前后主框跨接）、C（局部加强框/承力筒）的同口径贸易；
3. 明确的 `B601法兰 → 定位/紧固 → 适配器 → 主框/纵梁 → 主结构`载荷路径；
4. 安装孔、孔边距、定位销、工具空间、Ø100 通道、连接器、接地、拆装和热隔离包络；
5. 选定方案的原生适配器和 H10 替代几何。

退出条件：适配器方案有来源驱动的评分、人工 downselect、真实主承力路径、紧固件/工具/通道检查，
且不把可拆面板当作根部弯矩主载荷路径。

### 闭环 3：收拢、约束与释放

输出顺序：

1. `B51R1_G07_G08_DOF_ALLOCATION_MATRIX.csv`；
2. G07 法向支撑、横向限位、允许微滑移、接触垫、到位检测合同；
3. G08 末端导向、重复定位、辅助约束、2P 开合禁入区合同；
4. HDRM 预紧/保持/释放方向、行程、残留突出体、检测、失败和维护功能包络；
5. 原生 G07、G08、HDRM 功能包络件和独立 Gate。

退出条件：基座、G07、G08 不形成不可装配的刚性过约束；HDRM 释放后完全退出初始抬离路径；
G08 不侵入两个独立 P 的全行程和接触面区域。

### 闭环 4：整星集成与连续间隙

目标装配：`03_CAD/90_TOP_INTEGRATION/B51R1_SPACE_EMBODIED_ROBOT_INTEGRATION.SLDASM`。

必须包含：最终 Skeleton、隔离只读 V2.2 整星参考、适配器、原生 B601、G07、G08、HDRM、
太阳翼隔离参考、传感器包和线束扫掠参考。

必须由原生 Mate 和受控抑制矩阵产生至少以下状态：

`Q0`、`STOWED_LOCKED`、`SOLAR_DEPLOY_ARM_LOCKED`、`SOLAR_DEPLOY_CONFIRMED`、
`HDRM_RELEASE_START`、`ARM_CLEAR_OF_G07`、`ARM_CLEAR_OF_G08`、`DEPLOYED_NOMINAL`、
`SERVICE`、`2P_OPEN`、`2P_HALF`、`2P_CLOSED`、`RELEASE_FAILED`、`SOLAR_DEPLOY_FAILED`。

连续间隙必须输出关节值—时间、最小距离—时间、最危险零件对、最危险时刻、局部加密和失效裁决；
截图不能单独构成通过证据。Phase 1、G07/G08/HDRM 和必要 keepout 未通过前不得启动正式连续间隙。

### 闭环 5：结构、质量和质心

只有载荷源、材料、连接、边界条件和接口几何被接受后，才允许进入结构分析。
没有正式发射载荷谱时，只能做 `PRELIMINARY_UNIT_LOAD_AND_MODAL_CANDIDATE`，不得声称发射合格。

输出至少包括：

- 适配器六向单位载荷、根部弯矩、紧固件分配、接口翘曲、首阶模态和局部屈曲趋势；
- G07/G08 压缩、剪切、长细比、接触垫、预紧和残余变形风险；
- 主结构真实载荷路径、Ø100 截面削弱和太阳翼/机械臂载荷路径竞争；
- 基座 6×6 刚度、阻尼候选、模态、参与系数和适用频带；
- accepted URDF 动力学账、CAD 候选质量账、整星质量账三账分离；
- STOW、DEPLOY、SERVICE 质心和整星惯量对比。

accepted URDF 的 `4.6955559493429862 kg`在本阶段仍是 B601 动力学权威，CAD 候选质量不得自动覆盖。

### 闭环 6：控制/仿真交接和发布工程文件

机械侧需定义传感器、工具、抓取、G07/G08、航天器本体坐标，逐 link collision/visual/keepout 映射，
以及 `FIXED_BASE_DEBUG`与`FREE_FLOATING_VALIDATION`两个不同模型模式。

当前以下八个正式交接文件均不存在：

- `B51R1_MECH_CONTROL_HANDOFF_CONTRACT.yaml`；
- `B51R1_JOINT_ACTUATION_PARAMETER_REGISTER.csv`；
- `B51R1_JOINT_ZERO_SIGN_LIMIT_REGISTER.yaml`；
- `B51R1_SENSOR_FRAME_REGISTER.yaml`；
- `B51R1_BASE_INTERFACE_COMPLIANCE.yaml`；
- `B51R1_STOW_RELEASE_STATE_MACHINE.yaml`；
- `B51R1_COLLISION_MODEL_MAPPING.yaml`；
- `B51R1_CONTROL_MODEL_VALIDATION_MATRIX.csv`。

在 9 个原生 joint、q0/符号/limit、正式 T005-A/B/C、frame 100%映射、2P 关系、传感器 frame、
双基座模式和 provisional 标记通过前，只能生成 `DRAFT_NOT_RELEASED`，不得发布控制模型。

工程图、BOM、ICD、STEP 和 PDF 必须在几何、质量账和配置通过后生成；图框质量不得引用未受控的
SolidWorks 默认质量值。

## 5. 当前缺口的机器事实

### 5.1 原生 CAD 缺件

- `B51R1_MASTER_SKELETON_V2.SLDPRT`：不存在；
- 十个原生 Carrier：`0/10`；
- `B51R1_CARRIER_CHAIN_NATIVE.SLDASM`：不存在；
- `B51R1_B601_NATIVE_ARTICULATED.SLDASM`：不存在；
- `B51R1_SPACE_EMBODIED_ROBOT_INTEGRATION.SLDASM`：不存在；
- 原生 Base Adapter、G07、G08、HDRM 功能包络：均不存在。

### 5.2 Gate 缺口

- 单坐标系：冷重开已通过，状态为 `SINGLE_COORDINATE_SYSTEM_PERSISTENCE_PASS`；本项只关闭 G0，原生建模仍需独立授权；
- H9：Mode A/Mode B 未裁决，launcher/deployer ICD 未绑定；
- 适配器：A/B/C 贸易框架存在，评分禁用，无 downselect；
- H10：`0/28`，其中 8 行 `UNACCEPTABLE_COLLISION`、20 行 `INTENDED_BOLTED_LAP`、28 行未解决；
- T005-A/B/C：全部 `NOT_RUN`；
- 旧 6R 预试最大 FK 误差约 `0.012812317 m`，只可作为失败复现证据；
- G07/G08：无原生自由度分配或接触实体；
- 连续间隙、正式结构/模态、质量闭环、发布工程图、控制交接：均未闭合。

H10 责任分配保持：适配器 V14-01..16（16 行）、G07 V14-17..21（5 行）、
G08 V14-22..28（7 行）。退出条件必须是 `28/28 disposition complete`、
`UNACCEPTABLE_COLLISION=0`、`UNRESOLVED=0`。

## 6. 推荐 Gate 顺序

| Gate | 允许动作 | 必须证据 | 失败动作 |
|---|---|---|---|
| G0 | 已完成：冷重开单坐标诊断件 | 唯一 `CS_DIAGNOSTIC_ONLY`、identity transform、外部引用 0、正常关闭/进程消失、Stage A hash 不变；`SINGLE_COORDINATE_SYSTEM_PERSISTENCE_PASS` | 保持 native authoring HOLD，进入 G1 准备 |
| G1 | Phase 2A 输入协调 | URDF hash lock、datum 冲突收据、feature naming freeze、FK/角度/位移容差人类权威 | 不创建最终 Skeleton |
| G2 | 创建并冷重开最终 Master Skeleton | 所有受权 datum/配置可枚举；0 实体；0 外部引用；质量贡献 0；hash/回读 | 不创建 Carrier |
| G3 | 逐个创建并冷重开 10 Carrier | 10/10 文件、命名实体、变换、属性、hash、外部引用 0 | 停在失败 Carrier，不继续 |
| G4 | J00→J09 增量建立 9 joint | 每步保存/回读；6R+1 fixed+2P；唯一 driver；limit；符号；q0 | 停在首个失败 joint |
| G5 | Carrier-only T005-A0/B0/C0 | 独立位形、同文档连续驱动回 q0、冷重开持久化 | 不挂接精细几何 |
| G6 | 按 link 挂接精细几何并执行正式 T005-A/B/C | visual mount 刚性挂接；2P 接触几何；20 固定种子；连续回 q0；冷重开 | 不进入接口闭合 |
| G7 | H9/适配器/G07/G08/HDRM/H10 | 人工架构裁决或批准双分支；载荷路径；DOF 分配；28/28 H10 | 不建立发布级顶层装配 |
| G8 | 顶层配置和连续间隙 | 原生状态、名义时序、最小距离时程和失败状态 | 不进入结构/质量发布 |
| G9 | 初步结构、模态、质量/惯量三账 | 来源化载荷/材料/边界；6×6 接口；三账不混用 | 保持 qualification HOLD |
| G10 | 控制交接与工程图候选 | 八个交接文件、ICD/BOM/图纸/STEP/PDF 一致性 Gate | 不发布控制或制造状态 |

T005-C 或任一冷重开通过都不能替代同一文档连续驱动的 T005-B。

## 7. 冷重开通过后建议签发的最小 Phase 2A 授权包

Phase 2A 应只授权“最终坐标母体 → 10 Carrier → 9 joint → Carrier-only T005-A0/B0/C0”。
它不应同时授权详细适配器、G07/G08/HDRM、连续间隙、FEA、最终图纸或控制发布。

最小包建议包含：

1. `CODEX_B51R1_PHASE2A_NATIVE_SKELETON_CARRIER_EXECUTION_PROMPT.md`：精确顺序、停机规则、禁止项；
2. `B51R1_PHASE2A_AUTHORIZATION.yaml`：唯一写入根、保护输入、允许输出、可见启动总数和逐次用途；
3. `B51R1_PHASE2A_INPUT_LOCK.json`：本文件第 1 节全部控制输入的路径、字节数和 SHA-256；
4. `B51R1_PHASE2_DATUM_RECONCILIATION.yaml`：101.65/105.65/110.15/113.15 语义裁决；
5. `B51R1_PHASE2_FEATURE_NAMING_FREEZE.yaml`：两套 Carrier 命名的唯一原生名和别名映射；
6. `B51R1_PHASE2_ACCEPTANCE_TOLERANCE_AUTHORITY.yaml`：FK 平移、旋转、joint readback 和 q0 容差；
7. `B51R1_PHASE2A_EXPECTED_ARTIFACT_MANIFEST.csv`：1 Skeleton、10 Carrier、1 chain、J00..J09 和 Gate 文件；
8. `B51R1_PHASE2A_LAUNCH_AND_SESSION_SCOPE.yaml`：每次可见会话的唯一目的、输入、输出和停止条件；
9. `B51R1_PHASE2A_GATE_CHECKLIST.md`：G1 到 G5 的逐项验收；
10. `B51R1_PHASE2A_RECOVERY_POLICY.md`：API hang、Mate flip、保存失败、恢复对话框和精确 PID containment 规则。

建议把 Phase 2A 会话明确拆成六个有界作用域：

- S01：只创建和保存最终 Master Skeleton；
- S02：只冷重开并验收最终 Master Skeleton；
- S03：按 accepted link 顺序创建并独立保存十个 Carrier；
- S04：在新进程中逐个冷重开十个 Carrier 并回读；
- S05：建立 J00..J09、执行 T005-A0/B0 并正常退出；
- S06：冷重开 carrier chain 并执行 T005-C0。

授权必须写明每次会话是否允许在当前 Gate 通过后进入下一子步骤；不能使用“完整执行机械设计”作为
无限启动、无限写入或跨 Gate 继续的替代授权。

## 8. 不允许猜测的参数登记

以下内容必须保持 `TBD / HOLD / PROVISIONAL_TBD`，直至有本地权威或人工批准：

- H9 Mode A/Mode B 最终选择、launcher/deployer ICD 和飞行器外包络；
- FK、姿态、joint、间隙、应力、模态和质量验收容差；
- 真实机械硬限位及其相对 URDF 软限位的 margin；
- 电机、减速器、轴承和编码器型号；额定/峰值转矩、速度、传动比、效率和热降额；
- motor/reflected inertia、Coulomb/viscous friction、backlash、刚度、阻尼和线束恢复力矩；
- 两个 P 的物理闭合零位、总开度、接触中心、指爪刚度/推力和同步策略；
- 适配器材料、板厚、孔径、孔边距、螺栓/定位销型号、数量、预紧、扭矩、摩擦和公差；
- G07/G08 接触材料、垫片刚度、预紧、允许滑移、误差补偿和实际保持载荷；
- HDRM 产品型号、保持力、释放力/行程/时间、冲击和释放后残留包络；
- 太阳翼连续扫掠、机械臂初始释放、线束和维护工具 keepout 的正式几何；
- 相机型号、intrinsics/FOV/距离、安装误差、时延；F/T 传感器量程和过载；
- 线束最小弯曲半径、连接器拉脱方向、磨损/夹点和关节角相关恢复力矩；
- 正式发射载荷谱、材料卡、接触/紧固边界、结构阻尼、模态验收频率和安全系数；
- B601 CAD 候选物理质量、适配器/G07/G08/HDRM/传感器/线束/紧固件质量及整星余量；
- 基座 6×6 刚度/阻尼、柔性模态和刚柔模型适用频带。

旧桥接件、旧鞍座、STEP 静态见证、视觉截图、Mate smoke test 或 SolidWorks 默认质量均不能填补这些未知量。

## 8.1 B601 精细机械输出与验收清单

本节仅定义 G6 以后应交付和检查的机械对象，不授权当前创建几何。每一项的尺寸、材料、紧固件、供应商型号、
公差和质量在权威输入缺失时均保持 `TBD / HOLD`；供应商外形只能作为按 link 刚性挂接的精细几何，不能成为运动配合基准。

| ID | 必须形成的工程对象 | 最低表达内容 | 验收证据 | 当前状态 |
|---|---|---|---|---|
| B601-M01 | 关节法兰与连接关系 | J1～J6、固定腕部接口及两条 P 支链的定位面、紧固方向、拆装方向和载荷传递关系 | 原生特征树、接口表、局部剖视图、受控尺寸来源 | `TBD / HOLD` |
| B601-M02 | 关节外壳分段 | 每段外壳的 link 归属、分缝、内部功能包络、相邻运动件间隙和装配顺序 | link—零件归属表、爆炸图、最小间隙记录 | `TBD / HOLD` |
| B601-M03 | 检修盖板 | 盖板边界、开启/拆除方向、紧固件可达性、密封或热控接口占位 | 维护姿态局部图、工具包络、拆装步骤 | `TBD / HOLD` |
| B601-M04 | 连接器与线束出口 | 连接器占位、键位方向、插拔方向、应变释放区和出入口防磨边界 | 连接器方向图、插拔包络、线束路径 ID | `TBD / HOLD` |
| B601-M05 | 中空轴或外走线方案 | 对 J1～J6 和两条 P 支链逐项选择中空穿轴、外走线或混合路径；禁止用一条总包络代替逐关节路径 | 逐关节路线裁决、弯曲/扭转余量、夹点检查 | `TBD / HOLD` |
| B601-M06 | 编码器安装位置 | J1～J6 编码器功能包络、测量轴、安装基准、零位索引和可维护性 | frame 映射、零位/符号检查、拆装可达性 | `TBD / HOLD` |
| B601-M07 | 机械硬限位 | 每个 R 关节的正/负硬限位功能包络、接触件、载荷路径及相对 URDF 软限位的裕量 | 硬限位登记、局部接触图、来源和审签 | `TBD / HOLD` |
| B601-M08 | 腕部工具法兰 | 工具安装基准、定位/紧固、中央通道、工具更换方向和末端载荷路径 | `CS_TOOL_FLANGE` 回读、ICD、剖视与工具包络 | `TBD / HOLD` |
| B601-M09 | 六维力/力矩传感器安装层 | 法兰叠层、传力面、紧固、过载保护占位、线束出口和拆装方向 | `CS_FT_SENSOR` 回读、接口层剖视、维护步骤 | `TBD / HOLD` |
| B601-M10 | 相机及支架 | 基座、腕部和末端近场相机的安装基准、支架、遮挡/防护和更换包络 | 三个相机 frame、FOV 遮挡记录、支架工程图 | `TBD / HOLD` |
| B601-M11 | 防碰撞保护包络 | 各 link、腕部、夹爪、相机、F/T、连接器和线束的受控 collision/keepout 表达 | visual/collision/keepout 映射、H10 与连续间隙引用 | `TBD / HOLD` |

退出条件为：11/11 对象均有唯一零件或功能包络 ID、唯一 link 归属、来源、配置适用性、质量账归属、维护路径和证据哈希；
任何“外形看起来存在”但没有上述追溯链的对象均不得计为完成。

## 8.2 十个统一 frame、逐关节线束与维护矩阵

### 8.2.1 必须逐字使用的十个统一 frame

以下名称来自机械工程指令，数量必须恰为 10；此处冻结的是接口名称和用途，不冻结尚无权威来源的变换数值。

| 序号 | frame 精确名称 | 用途 | 父 frame、六自由度变换与公差 | 验收方式 | 当前状态 |
|---:|---|---|---|---|---|
| 1 | `CS_SPACECRAFT_BODY` | 航天器结构根 frame | 由最终 Skeleton 和受控 datum 给出 | 原生回读 16 元素变换、方向图、hash | `TBD / HOLD` |
| 2 | `CS_B601_BASE` | B601 基座接口 frame | 由 H9 分支及最终接口裁决给出 | 与 accepted base frame、安装面和配置交叉核对 | `TBD / HOLD` |
| 3 | `CS_CAMERA_BASE` | 基座相机 frame | 安装件、方向和外参均待权威输入 | CAD 回读、相机外参表和 FOV 见证 | `TBD / HOLD` |
| 4 | `CS_CAMERA_WRIST` | 腕部 RGB/RGB-D 相机 frame | 安装件、方向和外参均待权威输入 | CAD 回读、相机外参表和 FOV 见证 | `TBD / HOLD` |
| 5 | `CS_CAMERA_EE` | 末端近场相机 frame | 安装件、方向和外参均待权威输入 | CAD 回读、相机外参表和 FOV 见证 | `TBD / HOLD` |
| 6 | `CS_FT_SENSOR` | 六维力/力矩传感器测量 frame | 传感器型号、叠层和测量方向待权威输入 | CAD 回读、供应商 ICD、轴向示意 | `TBD / HOLD` |
| 7 | `CS_TOOL_FLANGE` | 腕部工具接口 frame | 法兰标准、定位方式和变换待权威输入 | CAD 回读、工具 ICD、方向图 | `TBD / HOLD` |
| 8 | `CS_GRASP_CENTER` | 两个独立 P 支链共同定义的抓取中心 | 必须由两指接触几何和两条 P 位移共同计算 | 2P open/half/closed 回读和接触几何计算 | `TBD / HOLD` |
| 9 | `CS_STOW_G07` | G07 收拢接触/约束 frame | 由 G07 自由度分配和实体接触面给出 | DOF 矩阵、接触面和原生 frame 回读 | `TBD / HOLD` |
| 10 | `CS_STOW_G08` | G08 收拢接触/约束 frame | 由 G08 自由度分配和实体接触面给出 | DOF 矩阵、接触面和原生 frame 回读 | `TBD / HOLD` |

frame 发布时每一行必须增加：`parent_frame`、`xyz_m`、`rpy_rad`、旋转矩阵、单位、配置、来源路径、字节数、SHA-256、
作者和复核人。任一变换仍为 `TBD` 时，`B51R1_SENSOR_FRAME_REGISTER.yaml` 只能是 `DRAFT_NOT_RELEASED`。

### 8.2.2 逐关节线束与维护矩阵

| 关节 | 入线/出线和跨关节策略 | 必做运动余量检查 | 必做维护检查 | 当前状态 |
|---|---|---|---|---|
| `joint1` | 中空轴/外走线/混合：`TBD`；入口、出口、夹点和固定夹：`TBD` | q0、两软限位、STOW、释放起点；弯曲半径和恢复力矩均待来源 | 基座连接器插拔、根部螺栓工具空间、无需破坏主承力接口的更换路径 | `TBD / HOLD` |
| `joint2` | 路径方案、应变释放和防磨套：`TBD` | q0 位于数值上限，必须检查向负方向全行程；不得假设 q0 两侧对称余量 | 盖板拆除、编码器可达、线束可更换且不要求拆除无关 link | `TBD / HOLD` |
| `joint3` | 路径方案、入口/出口和固定夹：`TBD` | q0 位于数值上限，必须检查向负方向全行程、折叠态夹点和 G07 邻近段 | 编码器、连接器和外壳分段的独立拆装路径 | `TBD / HOLD` |
| `joint4` | 路径方案和跨肘部余量：`TBD` | lower/q0/upper、STOW、抬离 G07 的连续扭转与刮碰 | 肘部盖板、固定夹、防磨套和连接器可达性 | `TBD / HOLD` |
| `joint5` | 路径方案和腕部过渡：`TBD` | lower/q0/upper、抬离 G08、腕部相机/F-T 共路线束夹点 | 腕部线束、相机和 F/T 在受控顺序下可更换 | `TBD / HOLD` |
| `joint6` | 旋转穿轴/外绕策略：`TBD` | 全软限位、mate flip、线束累积扭转和恢复力矩 | 不拆除工具法兰即可检查连接器；若不能，记录强制拆装步骤 | `TBD / HOLD` |
| `gripper_joint` | 固定腕部接口的连续穿线和应变释放：`TBD` | 固定变换必须恒定；不得出现由线束引起的伪自由度 | F/T、工具法兰和夹爪子装配的分层拆装顺序 | `TBD / HOLD` |
| `gripper_joint1` | 左 P 支链柔性段、滑环/拖链/外绕方案：`TBD` | 独立 0～0.0715 m 全行程、open/half/closed、与 G08 和右支链互不干涉 | 左指及其线束可独立拆换，不能要求同步拆除右指 | `TBD / HOLD` |
| `gripper_joint2` | 右 P 支链柔性段、滑环/拖链/外绕方案：`TBD` | 独立 0～0.0715 m 全行程、open/half/closed、与 G08 和左支链互不干涉 | 右指及其线束可独立拆换，不能要求同步拆除左指 | `TBD / HOLD` |

整机维护还必须逐项验证：基座螺栓工具可达、可拆面板移除后的设备可达、三处相机可更换、F/T 可拆装、
HDRM 可复位、所有连接器可插拔，以及是否必须整体拆除机械臂才能维护内部设备。每项必须记录姿态、拆装先后、工具包络、
被抑制/移除零件、复装基准和复装后 Gate；只有截图而没有可复现步骤不得通过。

## 8.3 H10 逐行证据 schema 与 28/28 关闭规则

H10 每一行必须使用同一字段集合，禁止只写“已修改”或只附局部截图：

```text
row_id
owner_group
configuration
pair_a
pair_b
before_interference_volume_mm3
after_interference_volume_mm3
before_min_distance_mm
after_min_distance_mm
root_cause
responsible_part
modification_action
before_local_image_path
after_local_image_path
measurement_evidence_path
evidence_bytes
evidence_sha256
final_classification
reviewer
review_timestamp_utc
```

字段规则如下：

- `row_id` 必须唯一覆盖 V14-01～V14-28；责任分配保持适配器 V14-01..16、G07 V14-17..21、G08 V14-22..28；
- 返工前/后干涉体积和最小距离必须来自同一单位制、同一测量算法和明确配置；无有效测量时填 `TBD`，不得填 0；
- `root_cause`、`responsible_part` 和 `modification_action` 必须形成一一可追溯因果链；
- 修改前/后局部图必须可定位零件对、方向和配置，且各自具有路径、字节数和 SHA-256；
- `measurement_evidence_path` 必须指向机器可读结果；`evidence_bytes` 和 `evidence_sha256` 必须与该文件现场复算一致；
- `final_classification` 必须取受控分类表中的值；分类表尚未冻结时保持 `TBD / HOLD`，不得自行新增“可忽略”；
- 接触意图、紧固搭接、允许接触或净间隙必须分别有接口/装配依据，不能以负间隙截图替代设计意图。

逐行验收要求是字段 100% 完整、数值单位明确、证据文件存在且 hash 复算一致、责任人和复核人闭合。
总 Gate 仍仅在 `28/28 disposition complete`、`UNACCEPTABLE_COLLISION=0`、`UNRESOLVED=0` 同时成立时才能声明 `H10_CLOSED`；
当前保持 `0/28`，本节不改变任何 H10 状态。

## 8.4 正式 T005-A/B/C 验收定义

Carrier-only 的 `T005-A0/B0/C0` 不能替代精细 B601 几何挂接后的正式 T005。

### T005-A：22 个独立不可变位形

- 位形集合必须明确包含 `q0`、`STOW` 和 20 个固定随机种子位形，共 22 个；
- 随机种子值、生成算法版本、关节采样域、位形向量、顺序和 manifest SHA-256 必须在运行前冻结；当前种子和容差均为 `TBD / HOLD`；
- 每个位形必须是独立配置或独立受控文档，不能从上一个位形的残余 Mate 状态推导通过；
- 每个位形记录 6R、fixed、2P 的命令值与原生 Mate 回读、FK 回读、重建错误、干涉结果、文件路径、字节数和 SHA-256；
- 20 个样本必须同时驱动两个独立 P 坐标；不得把一个夹爪总宽度参数冒充两个 P；
- manifest 冻结后不得因为碰撞或失败而换种子。失败位形必须保留并进入根因/返工闭环。

### T005-B：同一文档连续驱动并返回 q0

- 在同一个已打开的原生装配文档内，按冻结顺序连续遍历正式测试向量；中途不得关闭、冷重开或换副本；
- 每个 R 和每个 P 必须由其唯一原生 limit mate 独立驱动，fixed 关节全程保持精确固定变换；
- 每一步强制 rebuild，并记录命令值、Mate 回读、FK、最小距离、错误/警告和时间序号；
- 最后必须显式设置全部关节回到 accepted q0，再次 rebuild 并按经人工批准的平移、旋转、角度和位移容差验收；
- 禁止 `Move Component` 保存姿态、`Transform2` 驱动、抑制失败 Mate 后继续或用冷重开恢复正常来替代连续驱动通过。

### T005-C：保存、关闭、退出和冷重开持久化

- 仅在同一次 T005-B 已正常完成后，对同一受控文档执行一次受控保存；
- 记录保存前后 hash 及可解释的原生重序列化结论，关闭文档、正常退出 SolidWorks，并确认原 PID 消失；
- 在新进程中冷重开同一路径，回读 9 个 joint 的 Mate 名称、类型、限位、当前值、fixed 变换、配置矩阵、外部引用和 q0；
- 复核 q0、STOW 和 20 个不可变位形均可从冻结 manifest 恢复，且精细几何、2P 接触几何和引用路径未丢失；
- T005-C 通过不补偿 T005-B 失败；任何恢复对话框、缺失引用、Mate flip 或配置漂移均触发 fail-closed。

正式退出状态只有 `T005-A=PASS`、`T005-B=PASS`、`T005-C=PASS` 三者独立成立后才允许汇总为 `T005_A_B_C_PASS`。

## 8.5 连续间隙 pair matrix、名义时序与太阳翼失效分支

### 8.5.1 必查 pair matrix

| pair ID | 对象 A | 对象 B | 必查状态/区间 | 必须输出 | 数值门限 |
|---|---|---|---|---|---|
| CL-01 | B601 全部精细几何/保护包络 | 航天器舱体、面板、主框和纵梁 | STOW、释放全程、DEPLOY、SERVICE | 最小距离—时间、危险零件对、危险时刻、局部加密 | `TBD / HOLD` |
| CL-02L | B601/线束 | 左太阳翼及其连续扫掠体 | 名义展开及左翼失效分支 | 同上并记录翼角/臂关节值 | `TBD / HOLD` |
| CL-02R | B601/线束 | 右太阳翼及其连续扫掠体 | 名义展开及右翼失效分支 | 同上并记录翼角/臂关节值 | `TBD / HOLD` |
| CL-03 | B601 中段/保护包络 | G07 接触件和释放后残留体 | STOW 接触、卸载、抬离、回退 | 接触到净间隙的连续转变 | `TBD / HOLD` |
| CL-04 | 腕部/夹爪/保护包络 | G08 接触件和释放后残留体 | STOW、2P 禁用段、抬离、2P 全行程 | 最小距离及两 P 独立位移 | `TBD / HOLD` |
| CL-05 | B601/线束 | HDRM 释放件及残留突出体 | 预紧、释放起点、释放后全程 | HDRM 行程、残留体和最小距离 | `TBD / HOLD` |
| CL-06 | 左指 | 右指及各自线束 | 2P open/half/closed 和独立极限组合 | 指间/线束最小距离、接触中心 | `TBD / HOLD` |
| CL-07 | 全部线束扫掠 | 关节外壳、盖板、固定夹、舱体 | q0、软限位、STOW、释放和 SERVICE | 弯曲半径、夹点、磨损点、恢复力矩 | `TBD / HOLD` |
| CL-08 | 三个相机 FOV/近场工作区 | 航天器、机械臂、线束、G07/G08/HDRM | 所有任务与失败配置 | 遮挡率/盲区定义及最危险状态 | `TBD / HOLD` |

全部 pair 必须采用连续采样和危险区局部加密；采样步长、时间参数化、距离算法和通过阈值在权威输入前均为 `TBD / HOLD`。
单帧截图、只检查端点或只检查名义分支均不得通过。

### 8.5.2 名义时序

```text
STOWED_LOCKED
→ SOLAR_DEPLOY_ARM_LOCKED
→ SOLAR_DEPLOY_CONFIRMED
→ HDRM_RELEASE_START
→ ARM_CLEAR_OF_G07
→ ARM_CLEAR_OF_G08
→ ARM_CLEAR_OF_RESTRAINT_AND_KEEPOUT
→ DEPLOYED_NOMINAL
→ SERVICE（如任务需要）
```

每一跳必须有进入条件、离开条件、主动关节、被锁定关节、G07/G08/HDRM 状态、太阳翼状态、2P 许可状态和超时/失败转移；
真实时间、速度和停留时长当前均为 `TBD / HOLD`。

### 8.5.3 左翼、右翼与双翼失效分支

| 分支 | 初始检测 | 强制安全约束 | 必做裁决 | 当前状态 |
|---|---|---|---|---|
| 左翼展开失败 | 左翼未达确认，右翼状态独立记录 | 机械臂和 HDRM 不得因超时自动释放；保持受控锁定，除非后续故障处置权威明确允许 | 对 CL-01～CL-08 全矩阵计算，并裁决保持锁定、重试、单翼后继续或终止 | `FAILURE_DECISION_HOLD` |
| 右翼展开失败 | 右翼未达确认，左翼状态独立记录 | 同上 | 对称但不得复制左翼数值；必须使用右翼真实几何和状态 | `FAILURE_DECISION_HOLD` |
| 双翼展开失败 | 两翼均未达确认 | 默认保持 `STOWED_LOCKED`；任何机械臂释放或 HDRM 动作需要独立人工/任务权威 | 评估锁定生存、复位/重试、维护与终止路径 | `FAILURE_DECISION_HOLD` |

失败分支的“默认保持锁定”是 fail-closed 约束，不是最终任务策略。没有太阳翼驱动/锁定/故障 ICD 前不得宣称任一分支可恢复。

## 8.6 完整工程图与发布文件清单

| 发布 ID | 必须交付 | 最低内容 | 发布前置 Gate | 当前状态 |
|---|---|---|---|---|
| REL-01 | 整星总装图 | 顶层 BOM、基准、接口、主要包络、受控配置和质量账引用 | G8～G10 | `HOLD` |
| REL-02 | 收拢态图 | `STOWED_LOCKED`、G07/G08/HDRM 接触/约束、太阳翼状态和最小包络 | G7/G8 | `HOLD` |
| REL-03 | 展开态图 | `DEPLOYED_NOMINAL`、机械臂/太阳翼展开包络和关键 frame | G8 | `HOLD` |
| REL-04 | 维护态图 | `SERVICE`、拆装方向、工具和人员/设备可达包络 | G8 | `HOLD` |
| REL-05 | 基座适配器零件及装配图 | 主载荷路径、定位/紧固、Ø100 通道、连接器、接地和热隔离接口 | H9/downselect、G7/G9 | `HOLD` |
| REL-06 | G07 零件及装配图 | 接触垫、允许滑移、预紧、检测和安装误差补偿 | G7/G9 | `HOLD` |
| REL-07 | G08 零件及装配图 | 末端导向、重复定位、2P 禁入和检测接口 | G7/G9 | `HOLD` |
| REL-08 | HDRM 功能接口图 | 保持/释放方向、行程、检测、残留突出体和复位/维护接口 | G7/G8 | `HOLD` |
| REL-09 | B601 q0 与关节限位图 | 6R+fixed+2P 零位、正方向、软限位、硬限位占位和独立 P 定义 | G6、T005 | `HOLD` |
| REL-10 | B601 精细本体图包 | 法兰、外壳、盖板、连接器、线束出口、工具/F-T/相机支架和保护包络 | G6 | `HOLD` |
| REL-11 | 线束路径图 | 逐关节入/出线、固定夹、防磨、弯曲余量、连接器方向和维护断点 | G6/G8 | `HOLD` |
| REL-12 | 相机视场图 | 三个相机 frame、FOV、遮挡和工作距离来源 | G8/G10 | `HOLD` |
| REL-13 | 爆炸图与拆装顺序 | 紧固件、定位件、维护层级、特殊工具和复装基准 | G8/G10 | `HOLD` |
| REL-14 | 关键剖视图 | 基座载荷路径、关节穿线、腕部 F/T/工具叠层、G07/G08 接触 | G7～G10 | `HOLD` |
| REL-15 | 受控 BOM | 零件号、版本、数量、材料/来源、质量账归属和替代件规则 | G9/G10 | `HOLD` |
| REL-16 | 机械 ICD | 坐标、安装面、孔系、定位、紧固、keepout、载荷和维护边界 | G7～G10 | `HOLD` |
| REL-17 | 交换与发布包 | 原生 CAD、STEP、PDF、机器可读 BOM/ICD、manifest、bytes、SHA-256 | G10 | `HOLD` |

每张图必须有非空主视图、正确引用配置、单位/比例、修订、图号、材料/表面处理来源、关键尺寸与公差来源、审批状态和引用 hash。
图框质量、质心和惯量只能引用受控账本及其版本；不得读取 SolidWorks 默认质量后写成 accepted URDF 真值。

## 8.7 整星质量、质心和惯量总账

总账必须逐项覆盖且防止重复计数：

| 账目 | 质量/质心/惯量来源 | 账本处理 | 当前状态 |
|---|---|---|---|
| 舱体与主结构 | 受控整星结构模型或质量清单 | 包括主框、纵梁、承力筒/面板；可拆面板单列 | `TBD / HOLD` |
| 左/右太阳翼及部署机构 | 受控太阳翼质量属性 | 左右分列并随 STOW/DEPLOY 状态变换 | `TBD / HOLD` |
| B601 动力学账 | accepted URDF | 固定保持 `4.6955559493429862 kg`，按 10 links 保留质量/惯量；不得被 CAD 覆盖 | `AUTHORITY_LOCKED` |
| B601 CAD 候选账 | 最终精细实体、实际材料和排除规则 | 与 URDF 并列比较，不并入动力学权威；Carrier 质量贡献必须为 0 | `TBD / HOLD` |
| 基座适配器及局部加强 | downselect 后原生实体和材料卡 | 适配器、垫片、定位件、隔热/绝缘件分列 | `TBD / HOLD` |
| G07 | 原生零件和接触垫 | 支架、垫片、传感器、紧固件分列 | `TBD / HOLD` |
| G08 | 原生零件和接触垫 | 支架、导向、传感器、紧固件分列 | `TBD / HOLD` |
| HDRM | 供应商/受控功能件数据 | 本体、安装件、线束和释放后残留体分别标识 | `TBD / HOLD` |
| 相机系统 | 基座、腕部、末端相机及各自支架 | 三套分列，含保护罩/支架，不得只计传感器裸机 | `TBD / HOLD` |
| F/T 传感器层 | 传感器、转接法兰、紧固件 | 与工具法兰和夹爪避免重复计数 | `TBD / HOLD` |
| 线束与连接器 | 逐段长度、线密度或称量数据 | 固定段/运动段/余量段、夹具和防磨件分列 | `TBD / HOLD` |
| 紧固件与小件 | BOM 或称量数据 | 已包含于上级零件时必须标记，防止二次汇总 | `TBD / HOLD` |
| 系统质量余量 | 经批准的余量规则 | 规则、基数、阶段、百分比/绝对值和责任人均待权威；不得自行取经验百分比 | `TBD / HOLD` |

总账每一项必须具有 `item_id`、配置、数量、质量、质心、关于统一 frame 的惯量、来源、成熟度、是否含余量、重复计数标志、
字节数和 SHA-256。必须分别发布 STOW、DEPLOY 和 SERVICE 的整星总质量、质心与惯量，并量化机械臂和太阳翼状态变化；
在材料、细节件或余量规则未闭合时只能报告不完整下限/区间并显式 `HOLD`，不能补猜单点值。

## 8.8 六个 R 关节的 +1°/-1° 符号测试与硬限位 HOLD

符号测试必须相对每个关节自身 joint frame 的 accepted axis 执行。测试中心 `q_probe` 必须位于 URDF 软限位内部并至少留出 1°
数值余量；`q_probe` 的选值和测试容差须由 G1 人工权威冻结。`joint2`、`joint3` 的 q0 位于数值上限，禁止在 q0 直接执行 +1°；
这两轴必须先进入经批准的内部 `q_probe` 再做对称微动。

| R joint | accepted axis | URDF 软限位 | 测试序列 | 预期判据 | 机械硬限位 |
|---|---|---|---|---|---|
| `joint1` | `0 0 1` | `-2.8 / 2.8 rad` | `q_probe → +1° → q_probe → -1° → q_probe → q0` | child 相对 parent 的正/负旋转符合右手轴和 accepted FK | `TBD / HOLD` |
| `joint2` | `0 0 -1` | `-3.14 / 0 rad` | 同上；`q_probe ≠ q0` | 同上，特别检查负 Z 轴语义且不越过数值上限 | `TBD / HOLD` |
| `joint3` | `0 0 1` | `-3.14 / 0 rad` | 同上；`q_probe ≠ q0` | 同上且不越过数值上限 | `TBD / HOLD` |
| `joint4` | `0 0 1` | `-1.87 / 1.57 rad` | 同上 | 同上 | `TBD / HOLD` |
| `joint5` | `0 0 1` | `-1.57 / 1.57 rad` | 同上 | 同上 | `TBD / HOLD` |
| `joint6` | `0 0 1` | `-3.14 / 3.14 rad` | 同上 | 同上并强制 mate-flip 检查 | `TBD / HOLD` |

每一步都要记录命令角、原生 Mate 回读、parent/child 变换、FK 差、截图/机器可读证据、文件 bytes 和 SHA-256；完成后显式返回 q0。
测试通过只证明 CAD 软限位内的符号和原生驱动，不证明物理硬限位。每个 R 的硬限位下界、上界、接触件、容差、吸能/承载能力以及
相对 URDF 软限位的正负裕量，在供应商或工程权威批准前一律保持 `TBD / HOLD`。

## 8.9 结构机械逐项验收矩阵

在正式载荷谱、材料卡、连接/接触、边界条件和验收准则缺失时，本矩阵只能处于
`PRELIMINARY_UNIT_LOAD_AND_MODAL_CANDIDATE / HOLD`，不得据此声明发射合格。

| 结构对象/检查项 | 必做分析和输出 | 通过所需证据 | 数值准则与当前状态 |
|---|---|---|---|
| 适配器六方向单位载荷与根部弯矩 | ±X/±Y/±Z 单位载荷、单位力矩或经批准组合；接口力流和紧固件载荷分配 | 载荷/边界来源、网格收敛、反力平衡、热点局部模型 | `TBD / HOLD` |
| 适配器局部变形 | 安装面相对位移、翘曲、B601 base frame 偏转 | 变形场、基准点读数、接口 6×6 柔度/刚度候选 | `TBD / HOLD` |
| 适配器局部屈曲 | 薄壁、腹板、开孔和加强区的屈曲模态/非线性趋势 | 特征屈曲及必要的缺陷敏感性记录 | `TBD / HOLD` |
| 主结构面板开孔 | Ø100 通道和安装/维修开孔对面板、主框连接及局部载荷旁路的影响 | 开孔前后刚度/应力/屈曲对比、边缘加强依据 | `TBD / HOLD` |
| 纵梁局部加强 | 机械臂载荷进入真实主框/纵梁，局部加强件及连接载荷 | 连续载荷路径图、连接反力、加强前后对比；不得以可拆面板为主路径 | `TBD / HOLD` |
| 太阳翼/机械臂载荷路径竞争 | 共用主框/纵梁节点的叠加载荷和局部变形 | 组合工况、接口载荷分解和敏感性 | `TBD / HOLD` |
| G07 接触垫压缩 | 法向压缩、接触压力、预紧、允许滑移和释放后回弹 | 接触材料来源、压力/压缩量分布、残余变形 | `TBD / HOLD` |
| G08 接触垫压缩 | 同上，并覆盖末端导向和两 P 禁入状态 | 同上及 2P 全行程邻近检查 | `TBD / HOLD` |
| G07/G08 侧向剪切与立柱稳定 | 侧向剪切、长细比、连接弯矩和局部屈曲 | 反力、屈曲/强度结果、连接与基座局部模型 | `TBD / HOLD` |
| 紧固件/定位件 | 预紧、剪切、拉脱、承压、滑移和载荷分配 | 型号/材料/摩擦/扭矩来源、组载结果、失效模式 | `TBD / HOLD` |
| 接口面与释放后残余变形 | 面翘曲、接触卸载、HDRM/G07/G08 释放后的残余偏移 | 加载—卸载路径、残余量和对首次运动间隙的回灌 | `TBD / HOLD` |
| 模态与控制交接 | 基座 6×6 刚度/阻尼候选、模态、振型、参与系数、适用频带 | 质量账版本、边界条件、模态有效质量和控制接口文件 | `TBD / HOLD` |

所有结构行必须记录模型版本、配置、材料、连接、接触、网格、载荷、边界、求解器、结果路径、bytes、SHA-256、复核人和适用限制。
局部变形、面板开孔、纵梁加强、接触垫压缩或局部屈曲任一项未裁决，都不得进入结构 Gate 的通过汇总。

## 9. 允许的当前结论

允许：

`B51R1_PHASE2_MECHANICAL_ENGINEERING_EXECUTION_MAP_PREPARED_NOT_AUTHORIZED`

同时允许：

- `SINGLE_COORDINATE_SYSTEM_PERSISTENCE_PASS`，仅限单坐标诊断件持久化；

仍禁止：

- `FINAL_MASTER_SKELETON_PASS`；
- `NATIVE_CARRIER_10_OF_10_PASS`；
- `NATIVE_6R_1_FIXED_2P_PASS`；
- `H10_CLOSED`；
- `T005_A_B_C_PASS`；
- `CONTROL_MODEL_RELEASE_CANDIDATE`；
- `COMPLETE`、`MANUFACTURING_READY`、`FLIGHT_READY`、`LAUNCH_QUALIFIED`。

下一可执行决策点是：完成 G1 的 datum 协调、Carrier 特征命名冻结、Phase 2A 输入锁和验收容差权威；这些离线前置项通过后，人工签发第 10 节仅限 S01 的一次性可见启动授权。

## 10. 冷重开通过后的精确下一次授权短语

只有当前机器 Gate 已记录 `SINGLE_COORDINATE_SYSTEM_PERSISTENCE_PASS`，且 G1 datum 协调、
Carrier 特征命名冻结和 Phase 2A 输入锁均已通过时，建议人工逐字授权：

> 允许可见启动 SolidWorks 2024 一次，仅用于在 B5.1R1 隔离候选目录内，依据已通过的 Phase 2A 输入锁创建、保存并正常关闭 `B51R1_MASTER_SKELETON_V2.SLDPRT`；Stage A、accepted URDF、V2.2 基线和单坐标诊断件保持只读；本次不得创建 Carrier 或关节装配，不得设计适配器、G07、G08 或 HDRM，不得运行 H10、T005、连续间隙、FEA、最终工程图或控制发布；任一前置 Gate、API、保存或回读失败立即 fail-closed 停止。

该短语只授权 S01。S02 冷重开验收及后续 S03～S06 必须由后续明确授权覆盖，不能从 S01 自动外推。
