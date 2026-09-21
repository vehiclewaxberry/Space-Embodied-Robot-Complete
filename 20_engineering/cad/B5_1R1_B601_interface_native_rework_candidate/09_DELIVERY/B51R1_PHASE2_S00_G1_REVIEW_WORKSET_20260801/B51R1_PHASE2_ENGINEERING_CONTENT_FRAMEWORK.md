# B5.1R1 Phase 2 航天工程与机器人学完整工程内容框架

状态：`FRAMEWORK_PREPARED_FOR_HUMAN_REVIEW / G1A_HOLD / S01_NOT_AUTHORIZED`

本文件是工程内容、责任、证据和退出准则的总框架，不是 SolidWorks 写入授权，不替代 accepted URDF、已签署的接口控制文件、载荷谱、制造图或鉴定证据。

## 1. 当前事实基线

- accepted URDF：`arm_b601_v1`，10 links、9 joints、`6R + 1 fixed + 2 independent P`，质量权威精确文本为 `4.6955559493429862 kg`。
- Single-CS 持久化 Gate：`SINGLE_COORDINATE_SYSTEM_PERSISTENCE_PASS`，但 `native_authoring_release=false`。
- 最终 Master Skeleton：不存在。
- 原生 Carrier：`0/10`；Carrier chain、原生 B601 整臂和顶层整星装配均不存在。
- H9 未裁决；H10 为 `0/28`；T005-A/B/C 均为 `NOT_RUN`。
- 机械—控制正式交接：`0/8`。
- 可见 SolidWorks 启动授权：0；S01～S06 均未授权。
- Stage A 受合同策略和哈希保护，但 Windows `ReadOnly` 属性为 false；目录内仍有一个 6-byte 残留锁文件，须由人类裁决。

## 2. 权威层级与不可混用规则

权威优先级从高到低为：

1. 人类 Owner 的逐会话精确授权及其不可变收据；
2. 人类签署的 datum、命名、数值容差权威与重冻结 input lock；
3. accepted URDF：运动拓扑、joint origin/axis/limit、质量和惯量权威；
4. 经 Gate 接纳的测量、datum register、frame mapping 和 joint register；
5. 原生 Carrier：运动载体和 CAD 约束实现，不提供动力学质量权威；
6. B601 精细几何：工程外形、装配、间隙、工程图和候选 CAD 质量账；
7. 中性 STEP、截图和渲染：只作为形态或可读性证据。

禁止以下替代：

- STEP 或截图替代原生运动；
- CAD 自动质量替代 accepted URDF；
- 冷重开 T005-C 替代同文档连续驱动 T005-B；
- `Move Component`、`Transform2`、`Fix Component` 或 Mate Controller 替代原生唯一驱动；
- 可拆面板或 G07/G08 footprint 替代真实主框/纵梁载荷路径；
- 具身模型/VLA 输出绕过物理、碰撞、状态机和 SAFE Gate。

## 3. Gate 架构

原 G1 被拆成两个不循环的 Gate：

| Gate/阶段 | 目标 | 进入条件 | 最低退出证据 | 当前状态 |
|---|---|---|---|---|
| S00 / G1A | 权威与哈希锁 | 本地只读审计 | 三项人类权威签署、Critical/High 关闭、Stage A 锁文件处置、V2 input lock 重冻结 | HOLD |
| G1B | S01 准入 | G1A PASS | Owner 精确授权、授权收据、仅 S01、一次可见启动 | NOT_AUTHORIZED |
| S01 | 创建最终 Master Skeleton | G1B PASS | 0实体、0外部引用、0质量、3配置、正常保存关闭 | NOT_RUN |
| S02 / G2 | 冷重开 Skeleton | S01 PASS + 独立授权 | 名称/类型/16元素变换/配置/datum/质量持久化 | NOT_RUN |
| S03 | 创建 10 Carrier | G2 PASS + 独立授权 | 按 accepted link 顺序逐件创建、独立收据、首错即停 | NOT_RUN |
| S04 / G3 | 冷重开 10 Carrier | S03 10/10 + 独立授权 | 10/10 名称、变换、属性和零质量持久化 | NOT_RUN |
| S05 / G4 | J00→J09 建链 | G3 PASS + 独立授权 | 6R+1fixed+2P、唯一驱动、q0/符号/限位、A0/B0 | NOT_RUN |
| S06 / G5 | T005-C0 | G4+A0/B0 PASS + 独立授权 | 保存关闭新进程冷重开，C0 不替代 B0 | NOT_RUN |
| Phase 2B / G6 | 精细 B601 原生装配 | Phase2A PASS + 独立授权 | 几何逐 link 刚挂、正式 T005-A/B/C、质量权威不覆盖 | HOLD |
| Phase 2C / G7-G9 | 基座、G07/G08/HDRM、H9/H10 | 正式 T005、H9 或双分支批准、trade 可评分 | 真实载荷路径、DOF 分配、28/28、0 unresolved | HOLD |
| Phase 2D / G9 | 顶层整星与连续间隙 | H10 PASS + 独立授权 | 全状态原生配置、CL-01～CL-08、三类太阳翼失败分支 | HOLD |
| Phase 2E / G10 | 结构、质量、控制/AI 交接 | 上游 Gate 与正式输入齐备 | 结构候选、三账、8文件、claim audit | HOLD |

每次授权只能进入表中一个阶段，不能自动继承到下一阶段。

## 4. 多智能体责任与否决权

| Agent | 专业责任 | 必须攻击的问题 | 否决权 |
|---|---|---|---|
| A0 Authority | 配置、哈希、授权、基线 | 越权、旧哈希、空签名、授权次数错误 | 任一权威不一致即停止 |
| A1 Spacecraft Mechanical | 主框、纵梁、面板层、适配器 | 面板承根部弯矩、通道/工具空间丢失 | 载荷路径不成立即 HOLD |
| A2 Robot CAD/Kinematics | Skeleton、Carrier、joint、T005 | 假驱动、Mate flip、2P耦合、q0错 | 拓扑/运动证据不完整即 FAIL |
| A3 Controls/Dynamics | frame、符号、自由漂浮、柔性接口 | frame 不闭合、固定/自由漂浮混用 | 禁止控制发布 |
| A4 Mechanism/Harness | G07/G08/HDRM、线束、维护 | 过约束、线束穿轴、不可拆、2P侵入 | 释放/维护路径不闭合即 HOLD |
| A5 Structural/Mass | 载荷、连接、模态、三质量账 | 无载荷谱做鉴定、质量重复 | 禁止制造/飞行结论 |
| A6 Verification | schema、hash、H10、T005、图纸 | 用截图或默认值判 PASS | 证据不足即拒绝 PASS |
| A7 Red Team | 独立攻击设计和声明 | datum、分支、持久化、载荷、配置 | Critical/High 未关即阻断 Gate |
| A8 Embodied Integration | sensor/tool/grasp/collision/SAFE | VLA 绕过物理/安全、UNKNOWN 被当真值 | 禁止 AI/控制发布 |

设计者不得关闭自己的 Critical/High finding；关闭必须由 A6 复核、A0 确认权威、相应专业 Agent 确认技术证据。Finding 只阻断其 `gate_impact` 指定的 Gate：G1A 相关 Critical/High 必须在 S01 前关闭；纯下游问题可由 A0/A6 接纳为带明确未来阻断 Gate 的 `DEFERRED_HOLD`，不得伪装成技术关闭。

## 5. Loop Engineering 标准循环

每一阶段固定执行：

1. `Loop 0 Authority Lock`：进程、Git快照、授权、hash、Gate、datum/naming/tolerance；
2. `Loop 1 Design Synthesis`：目标、输入、变量、TBD、输出、失败退出；
3. `Loop 2 Robotics & Control Cross-Check`：拓扑、frame、q0、符号、limit、2P、fixed/free-floating；
4. `Loop 3 Mechanical & Structural Cross-Check`：载荷路径、接触、过约束、线束、维护、材料/连接来源；
5. `Loop 4 Evidence Verification`：文件、bytes、hash、API回读、配置、外部引用、质量、容差；
6. `Loop 5 Adversarial Review`：机械、控制、AI、声明四线攻击；
7. `Loop 6 Final Claim Audit`：只从机器结果生成状态和下一条唯一授权语句。

任一循环失败返回 Loop 1；Authority、授权或基线失败直接停止，不进行设计修补。

## 6. 工程工作包

| WBS | 工程包 | 核心输入 | 主要输出 | 验收边界 |
|---|---|---|---|---|
| W00 | 配置与数字线程 | Gate、hash、授权、accepted URDF | authority lock、input lock、claim matrix、artifact index | 路径/bytes/hash 全匹配 |
| W01 | Master Skeleton | 签署 datum、H9双分支、160×160、Ø100 | `B51R1_MASTER_SKELETON_V2.SLDPRT` | 0实体/外引/质量；3配置；冷重开 |
| W02 | 10 Carrier | accepted link/joint mapping、冻结命名 | 10 个零质量参考零件 | 10/10独立创建与冷重开 |
| W03 | 原生运动链 | 10 Carrier、joint origin/axis/limit | Carrier-only `6R+1fixed+2P` chain | 唯一驱动；J00-J09；A0/B0/C0 |
| W04 | B601精细装配 | vendor/工程几何、visual mount | `B51R1_B601_NATIVE_ARTICULATED.SLDASM` | 每实体唯一link；正式T005；CAD质量单独记账 |
| W05 | 基座接口贸易 | 主框/纵梁、通道、工具空间、载荷 | A/B/C适配器评分与人类downselect | 真实主承力路径，不以面板承载 |
| W06 | 收拢释放机构 | STOW、接触窗、误差、HDRM方向 | G07/G08 DOF矩阵、接触/预紧/释放包络 | 不过约束；释放后无残留侵入 |
| W07 | 顶层状态装配 | 整星、太阳翼、机械臂、FSM | 顶层 SLDASM 和受控状态矩阵 | 状态由原生配合/抑制生成 |
| W08 | 连续间隙 | 状态序列、速度、keepout、pair list | G8a刚体CL与G8b结构/热/容差鲁棒CL | 左/右/双翼失败独立计算且G9后强制复查 |
| W09 | 结构与接口柔性 | 载荷谱或单位载荷合同、材料、连接 | stress/buckling/modal、6×6 K/C | 无正式谱仅 preliminary candidate |
| W10 | 三质量账 | URDF、B601 CAD、整星BOM | 动力学账、CAD候选账、整星账 | 不重复；Carrier永远为0 |
| W11 | 控制与具身接口 | frame、joint、sensor、FSM、碰撞 | 8个机械—控制文件及仿真映射 | 初始仅 `DRAFT_NOT_RELEASED` |
| W12 | 图纸与发布 | 已验收配置、BOM、GD&T来源 | 装配/零件/接口/线束/检验图 | 配置正确、空白视图检查、claim一致 |

## 7. Master Skeleton 与 Carrier 机械架构

采用双层架构：

```text
accepted URDF
    ↓ kinematics / mass / inertia authority
zero-mass native Carrier layer
    ↓ native mates / limits / q0 / persistence
fine B601 engineering geometry
    ↓ rigid attachment through CS_VISUAL_MOUNT_<LINK>
adapter + G07/G08 + HDRM
    ↓ true frame/longeron load path
isolated V2.2 spacecraft reference
```

Datum 候选分层：

- `±101.65 mm`：纵梁中心轴候选；
- `±110.15 mm`：主承力结构表面候选；
- `±113.15 mm`：可拆面板外表面及 G07/G08 footprint 层候选；
- 历史 `±105.65 mm`：保留但不得驱动原生几何，直至人类裁决。

命名候选采用逐 link/joint 展开的唯一原生名称。当前 mapping 中 `CS_CHILD_JOINT_<JOINT>` 位于父/出端 Carrier，而 `CS_PARENT_JOINT_<JOINT>` 位于子/入端 Carrier；该方向命名反直觉，必须由人类明确确认，不能由 API 猜测。

## 8. 机器人学与控制闭环

### 8.1 拓扑和 joint 真值

- R：`joint1`～`joint6`；每个只有一个原生 Limit Angle 驱动。
- fixed：`gripper_joint`；使用完整 accepted URDF 变换，不使用 `Fix Component`。
- P：`gripper_joint1`、`gripper_joint2`；两条独立分支，各自 `0～0.0715 m`，无 mimic，不推断总开度。
- q0 为数值零位，不自动等于机械闭合或发射锁定。
- joint2、joint3 的 q0 位于上限，符号 probe 必须选择软限位内部点；禁止在 q0 直接做越界 `+1°`。

### 8.2 frame 合同

每个 link 至少具有 link frame 和 visual mount；每个 joint 具有父/子 frame；每个 moving joint 具有轴与 q0 零位面。所有 frame 均须提供：

- accepted source XPath/hash；
- parent/child；
- 16元素刚体变换；
- 右手性和轴归一化；
- 正方向 `+probe/-probe` 结果；
- CAD 名称、控制名称、仿真名称和只读 alias。

### 8.3 固定基座与自由漂浮分离

- `FIXED_BASE_DEBUG` 仅用于机构和控制调试；
- `FREE_FLOATING_VALIDATION` 必须包含航天器 6-DOF、总质量/质心/惯量及接口 6×6 柔度；
- 两种模式的状态、输入、输出和适用结论分开记录；
- 固定基座结果不得直接升级为自由漂浮捕获或消旋结论。
- 自由漂浮模型必须显式定义 bus pose/twist、机构状态、太阳翼构型、外部扰动、轮/推力器资源、接口柔性和动量守恒/反作用/饱和 oracle。
- accepted URDF 保持不变；相机、F/T、支架、线束、工具和适配器通过版本化 additive-body/inertia overlay 加入，记录不确定度和唯一计数，不能静默覆盖 4.6955559493429862 kg 权威。

### 8.4 控制与具身安全链

```text
perception
  → candidate pose / grasp
  → frame and timestamp validation
  → collision + keepout + state-machine validation
  → free-floating / structural physics validation
  → SAFE-00 decision
  → bounded control command
  → telemetry and evidence
```

任一输入为 `UNKNOWN`、过期、frame 不闭合或安全 Gate 不通过时，输出必须 fail-closed；VLA 不直接发关节命令。

SAFE-00 必须形成机器可读 typed contract，至少覆盖 frame/时间新鲜度、状态许可、joint/force/collision/keepout/姿态/资源边界、超时、锁存、人工 override 和故障注入。Camera optical frame、时间延迟/jitter、外参协方差、F/T wrench frame/偏置/饱和以及 allowed-contact matrix 也必须进入同一发布 Gate。

## 9. B601 精细机械闭环

正式精细装配必须关闭以下 11 项：关节法兰、分段外壳、检修盖板、连接器/线束出口、逐关节走线、编码器、硬限位包络、工具法兰、F/T安装层、三处相机及支架、collision/keepout 包络。

逐关节维护矩阵至少记录：弯曲半径、扭转循环、服务环、应变释放、连接器方向、拆装顺序、工具进入、盖板移除、复装定位和检查方法。任何线束不得穿越旋转轴、进入硬限位或 G08/2P 全行程。

## 10. 航天器接口、G07/G08 与 HDRM

适配器 A/B/C 使用同一评分口径：主承力载荷路径、质量、刚度、首频候选、Ø100通道、紧固件/定位销、工具可达、太阳翼间隙、机械臂释放、制造装配性和后续 FEA 可建模性。downselect 必须由人类完成。

G07/G08/HDRM 在画详细实体前先冻结 DOF allocation：约束方向、允许浮动方向、预紧方向、误差补偿、接触垫、释放方向、释放残留包络和装配顺序。基座、G07、G08 不能形成三个完全刚性的闭环接口。

## 11. 状态、干涉与连续间隙

最低状态集：`Q0`、`STOWED_LOCKED`、`SOLAR_DEPLOY_ARM_LOCKED`、`SOLAR_DEPLOY_CONFIRMED`、`HDRM_RELEASE_START`、`HDRM_RELEASE_CONFIRMED`、`ARM_CLEAR_OF_G07`、`ARM_CLEAR_OF_G08`、`ARM_CLEAR_OF_RESTRAINT_AND_KEEPOUT`、`DEPLOYED_NOMINAL`、`SERVICE`、`2P_OPEN/HALF/CLOSED`、`RELEASE_FAILED`、`SOLAR_DEPLOY_FAILED`。命令态与确认态分离；未确认 HDRM 释放时禁止机械臂运动。

H10 必须逐行关闭 28 项，最终要求：`disposition_complete=28/28`、`UNACCEPTABLE_COLLISION=0`、`UNRESOLVED=0`。连续间隙必须输出采样时刻、驱动状态、pair、最近点实体、距离、符号、配置、失败分支和证据 hash；单张终态截图不能代替时程。G8a 的刚体名义 PASS 不能直接发布，G9 输出变形、接触垫压缩、回差、热和线束不确定度后必须执行 G8b。

## 12. 结构、质量与工程图

没有正式载荷谱、材料批次、连接预紧和边界条件时，结构结论上限为：

`PRELIMINARY_UNIT_LOAD_AND_MODAL_CANDIDATE`

结构检查必须覆盖根部弯矩、紧固件分配、局部变形、面板开孔、纵梁加强、G07/G08 接触垫压缩、局部屈曲、6×6 柔度/刚度、模态与参与系数。

质量始终分三账：accepted URDF 动力学账、B601 CAD 候选账、整星质量/质心/惯量账。每条记录同时区分 `authority`、`validation_maturity`、`uncertainty`、`configuration_scope` 和 `qualification_level`；“权威已锁”不等于已称重、已鉴定。工程图必须绑定已验收配置，禁止默认配置/默认质量，并执行空白视图、断链引用、BOM配置和修订状态检查。

## 13. 机器证据最小 schema

每个 Gate 收据至少包含：

- schema、task/session/gate、generated_at；
- 授权原文路径/hash、授权次数；
- 输入路径/bytes/hash；
- 进程 PID、打开/保存/关闭/退出次数和错误警告；
- feature/mate 名称、类型、driver 数、数值和容差；
- 配置、外部引用、实体数、质量贡献；
- 前后文件 bytes/hash 和语义不变量；
- Red Team findings 与 closure evidence；
- current status、claim limit、下一条唯一授权语句。

证据文件创建后不可原地重写为 PASS；修订须生成新版本并保留失败历史。

## 14. 人类审核入口

进入任何 CAD 操作前，Owner 需要依次审核并签署：

1. datum 三层语义和历史 105.65 处置；
2. 唯一原生命名、父/子 token 方向、分支 ownership 和 alias；
3. 14 项 CAD—URDF 数值一致性容差、单位和 metric；
4. Stage A 残留锁文件处置，且处置后 Stage A hash 不变；
5. 所有 G1A 相关 Critical/High finding 的关闭证据，以及下游 Critical/High finding 的命名 `DEFERRED_HOLD` 处置；
6. `B51R1_PHASE2A_INPUT_LOCK_V2_REFROZEN.json`；
7. G1A PASS 收据；
8. 仅 S01 的新一次精确授权，并通过 `B51R1_PHASE2_G1B_S01_ADMISSION_PENDING.yaml` 的 V2 admission verifier；旧 V1 authorization 不能单独作为执行入口。

在此之前，允许结论只有：

`B51R1_PHASE2_S00_AUTHORITY_INPUTS_HASH_VERIFIED_G1_HOLD`

禁止结论：`G1_PASS`、`S01_AUTHORIZED`、`NATIVE_SKELETON_ACCEPTED`、`10_CARRIERS_ACCEPTED`、`NATIVE_6R_1_FIXED_2P_ACCEPTED`、`COMPLETE`、`MANUFACTURING_READY`、`FLIGHT_READY`、`LAUNCH_QUALIFIED`。
