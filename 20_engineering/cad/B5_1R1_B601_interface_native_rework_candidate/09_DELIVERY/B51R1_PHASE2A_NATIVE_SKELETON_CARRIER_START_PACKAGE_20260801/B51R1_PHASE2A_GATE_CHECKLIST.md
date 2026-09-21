# B5.1R1 Phase 2A Gate 清单

当前状态：`G1_HOLD / PREPARED_NOT_AUTHORIZED`

## G1：输入协调与人类权威

- [ ] 输入锁中每个路径存在，字节数和 SHA-256 完全匹配。
- [ ] accepted URDF 哈希为 `1BC2...C164`，质量权威为 `4.6955559493429862 kg`。
- [ ] Stage A 哈希为 `5DEB...C76B`，已设置并保持只读。
- [ ] 单坐标系 Gate 哈希为 `6D0C...EC5E`，状态为 `SINGLE_COORDINATE_SYSTEM_PERSISTENCE_PASS`，但未被误当作建模授权。
- [ ] 人工裁决 `101.65 / 105.65 / 110.15 / 113.15 mm` 的不同几何层语义；旧父级输入不改写。
- [ ] 人工冻结六类 Carrier 原生特征的唯一名称，并定义只读别名映射。
- [ ] 人工签发 FK、旋转、joint readback、q0 和位移容差；所有数值、单位、指标和来源完整。
- [ ] 对应会话有独立人类授权；`visible_launches_authorized` 与授权文字一致。
- [ ] G1 收据状态为 `PASS_HASH_LOCKED_AND_HUMAN_RATIFIED`。

退出条件：以上全部通过。任一未通过均不得启动 S01。

## G2：最终 Master Skeleton

### S01 创建

- [ ] 目标仅为 `B51R1_MASTER_SKELETON_V2.SLDPRT`，Stage A 未打开或保存。
- [ ] `COMMON_CANONICAL`、`MODE_A_EVALUATION`、`MODE_B_EVALUATION` 三配置共存，H9 未选定。
- [ ] 航天器结构 frame、B601 accepted base frame、A0 25°候选、160 × 160 边界、Ø100 通道和 X=183/185.25/198 轨完整。
- [ ] 经人工裁决的纵梁轴、主承力面、面板外层与 G07/G08 面板层足印窗口分层明确。
- [ ] `KO_SOLAR_SWEEP`、`KO_ARM_RELEASE`、`KO_HARNESS`、`KO_SERVICE_ACCESS` 保持 `TBD/HOLD`，未虚构几何。
- [ ] 0 实体、0 外部引用、质量贡献 0；保存错误/警告为 0。
- [ ] 文档正常关闭、进程正常退出、Stage A 哈希未变。

### S02 冷重开

- [ ] 新进程仅打开目标一次；特征名、配置、16 元变换和属性持久化。
- [ ] 所有数值比对使用已签发容差，不使用显示舍入或历史诊断阈值。
- [ ] 受控保存前后字节数和 SHA-256 有记录；语义不变量重新验证。
- [ ] 正常关闭并退出；G2 Gate 收据完整。

退出条件：`FINAL_MASTER_SKELETON_CANDIDATE_G2_PASS`。这不授予 Carrier 会话。

## G3：10/10 原生 Carrier

- [ ] S03 按 `base_link → link1 → ... → gripper_right` 顺序逐件创建、保存、关闭。
- [ ] 每件只含经冻结的 link/joint frame、轴、q0 面和 visual mount。
- [ ] `gripper_link` 同时含两个独立 P 分支的出关节 frame；不得串联两指。
- [ ] 每件 `MODEL_ROLE=KINEMATIC_CARRIER`、质量贡献 0、BOM 排除、动力学权威 accepted URDF。
- [ ] 每件 0 实体、0 外部引用；路径、字节数、SHA-256 和独立创建收据完整。
- [ ] S04 在新进程逐件冷重开并回读全部名称、变换和属性。
- [ ] 10/10 均通过；首个失败后无越过式继续创建或验收。

退出条件：`NATIVE_CARRIER_10_OF_10_G3_PASS`。这不授予建链会话。

## G4：9/9 原生 Joint 增量建链

- [ ] `J00_BASELINE` 存在；J01..J09 每增加一个 joint 即保存、回读并固化独立检查点。
- [ ] 六个 R 各自只有一个旋转自由度和一个原生 Limit Angle 命令驱动。
- [ ] 每个 R 依据 accepted 轴、原点、q0、正方向和 URDF 软限位；`+1°/-1°` 符号试验在人工容差下通过。
- [ ] fixed joint 使用精确 URDF 变换和完整约束，不使用 `Fix Component`。
- [ ] 两个 P 为独立分支，各有独立轴、q0、正方向和原生 Limit Distance；不得用一个夹爪宽度参数冒充两个 P。
- [ ] P 的 q0 仅称 `MIN_NUMERIC`，不得未经物理校准称“机械闭合”。
- [ ] 不使用 `Move Component`、`Transform2`、锁旋转同心配合、第二命令 Mate 或 Mate Controller 真值。
- [ ] 每个 moving joint 驱动数恰为 1；无 Mate 翻转、冗余或状态污染。
- [ ] 非零状态后，同一文档显式回到 q0；link FK、joint readback 和符号比对均使用人类授权容差。

退出条件：`NATIVE_6R_1_FIXED_2P_CARRIER_CHAIN_G4_PASS`。这不等于正式整臂 T005。

## G5：Carrier-only T005-A0/B0/C0

- [ ] A0：每个规定的独立位形都被保存为不可变证据，且由原生 Mate 值产生。
- [ ] B0：同一打开文档连续顺序驱动，最后返回 q0；无重开替代。
- [ ] C0：保存、正常关闭、进程退出、新进程冷重开，所有 Mate、limit、分支和 q0 持久化。
- [ ] T005-C0 未被用来替代 T005-B0。
- [ ] A0、B0、C0 各有独立收据、输入/输出哈希和异常记录。
- [ ] Stage A 哈希仍为 `5DEB...C76B`，SolidWorks 最终进程数为 0。

退出条件：`CARRIER_ONLY_T005_A0_B0_C0_G5_PASS`。

## G5 后仍保持的 HOLD

- H9 Mode A/Mode B 裁决与 launcher/deployer ICD；
- 精细 B601 工程几何挂接和正式 T005-A/B/C；
- 基座适配器、G07、G08、HDRM 和 H10 28/28；
- 连续间隙、结构/模态、三质量账、工程图和控制发布；
- `COMPLETE`、`MANUFACTURING_READY`、`FLIGHT_READY`、`LAUNCH_QUALIFIED`。
