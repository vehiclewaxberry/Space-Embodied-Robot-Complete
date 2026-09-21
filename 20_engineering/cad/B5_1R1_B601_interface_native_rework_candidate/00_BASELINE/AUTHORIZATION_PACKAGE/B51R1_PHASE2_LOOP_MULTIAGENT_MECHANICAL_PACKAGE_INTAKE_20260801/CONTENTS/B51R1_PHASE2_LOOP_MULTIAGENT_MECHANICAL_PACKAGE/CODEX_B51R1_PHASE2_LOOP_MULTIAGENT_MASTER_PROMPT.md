# Codex 主执行提示词
# B5.1R1 Phase 2 航天器—B601 空间机械臂机械工程
# Loop Engineering + 多 Agent 对抗式设计与证据闭环

任务标识：

`COMP-PROT-03-A4-B5.1R1-PHASE2-LOOP-MULTIAGENT-MECHANICAL-ENGINEERING`

## 0. 总任务

在不修改冻结基线、不覆盖 accepted URDF、不虚报 Gate 的前提下，建立一套：

- 航天器—机械臂统一 Master Skeleton；
- 10-link、`6R + 1 fixed + 2 independent P` 原生运动载体；
- B601 精细工程几何装配；
- 航天器真实主承力接口；
- G07/G08 收拢约束与 HDRM 功能接口；
- 整星状态、连续间隙、结构/质量闭环；
- 可供控制、自由漂浮动力学、MuJoCo/Isaac Sim 和具身智能使用的机械数字线程；

的工程候选方案。

本提示词是总编排合同，不是无限写入授权。SolidWorks S01～S06 以及后续每个写入阶段仍须取得独立、明确的人类授权。

---

# 1. 当前机器事实

开始前必须现场重读 Gate、复算输入锁和 SHA-256，不得只依赖本提示词。

当前允许的事实：

- 单坐标系冷重开：`SINGLE_COORDINATE_SYSTEM_PERSISTENCE_PASS`；
- accepted URDF：
  - robot：`arm_b601_v1`
  - 10 links
  - 9 joints
  - `6R + 1 fixed + 2 independent P`
  - mass：`4.6955559493429862 kg`
- 最终 `B51R1_MASTER_SKELETON_V2.SLDPRT`：不存在；
- 原生 Carrier：`0/10`；
- 原生 Carrier chain：不存在；
- 原生 B601 articulated assembly：不存在；
- 顶层整星原生装配：不存在；
- H9：未裁决；
- H10：`0/28`；
- T005-A/B/C：`NOT_RUN`；
- 机械—控制正式交接文件：`0/8`。

禁止把中性 STEP、静态图片、Stage A 参考几何或离线配置一致性升级成原生运动信用。

---

# 2. G1 专家建议裁决

以下内容属于“专家建议值”。只有人类在对应 YAML 中签名、记录时间、来源路径与 SHA-256 后才成为项目权威。

## 2.1 Datum 裁决建议

采用当前 V2 datum 合同作为 Phase 2 原生建模控制合同：

- `±101.65 mm`：四条纵梁中心轴；
- `±110.15 mm`：主承力结构表面；
- `±113.15 mm`：可拆面板外表面及 G07/G08 footprint 所在层；
- 历史 `±105.65 mm`：
  - 保留在历史父输入中；
  - 标记 `HISTORICAL_SEMANTIC_UNRESOLVED_DO_NOT_DRIVE_NATIVE_GEOMETRY`；
  - 禁止作为纵梁轴、主承力面或面板面驱动任何原生特征；
  - 不修改、不删除历史文件。

控制合同：

`02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2_DATUM_REGISTER.yaml`

控制 SHA-256：

`41A769163D7FE9066DDAC0A6E36E33A22AC9D33823F8CC47151515E8AC0FBC6E`

## 2.2 特征命名冻结建议

唯一原生名称采用逐 link/joint 展开的方案：

- `CS_LINK_<LINK>`
- `CS_PARENT_JOINT_<JOINT>`
- `CS_CHILD_JOINT_<JOINT>`
- `AXIS_<JOINT>`
- `PLANE_ZERO_<JOINT>`
- `CS_VISUAL_MOUNT_<LINK>`

规则：

1. 每个原生特征只有一个唯一名称；
2. 通用名称和旧合同名称仅进入只读 alias register；
3. API 调用前必须先解析为唯一原生名称；
4. API 不允许使用 alias 查找；
5. 不创建重复特征来兼容旧名称；
6. 大小写严格敏感；
7. `<LINK>`、`<JOINT>`逐字采用 accepted URDF 名称。

## 2.3 Phase 2A CAD 数值一致性容差建议

这些是 CAD—URDF 数值一致性容差，不是制造公差、结构公差或飞行鉴定公差。

- 坐标系平移回读：`1.0e-8 m`
- 坐标系旋转回读：`1.0e-8 rad`
- 各 link FK 原点平移：`5.0e-6 m`
- 各 link FK 旋转：`5.0e-6 rad`
  - 指标：`acos(clamp((trace(R_err)-1)/2,-1,1))`
- R关节 Mate 回读：`1.0e-6 rad`
- P关节 Mate 回读：`1.0e-6 m`
- R关节 q0 复位：`1.0e-6 rad`
- P关节 q0 复位：`1.0e-6 m`
- 同一文档返回 q0 后：
  - max link translation error：`5.0e-6 m`
  - max link rotation error：`5.0e-6 rad`
- 冷重开关节持久化：
  - R：`1.0e-6 rad`
  - P：`1.0e-6 m`
- 原生限位回读：
  - R：`1.0e-6 rad`
  - P：`1.0e-6 m`

不得自动放宽。若 SolidWorks API 的可重复量化误差超出上述门槛：

1. 保留失败结果；
2. 至少执行 10 次同条件 smoke readback；
3. 给出误差分布、最大值、均值和标准差；
4. 提交人类重新裁决；
5. 未获新授权前保持 HOLD。

---

# 3. 多 Agent 组织结构

只能在当前授权和机器 Gate 内工作。

## Agent A0：Authority & Configuration Manager

职责：

- 读取 Gate、输入锁、hash、授权次数；
- 冻结 accepted URDF 和 protected inputs；
- 检查命名、datum、容差权威；
- 拒绝任何越权动作。

拥有：停止权。  
没有：CAD 设计裁决权。

## Agent A1：Spacecraft Mechanical Architect

职责：

- 航天器主框、纵梁、面板层和任务面；
- B601 基座载荷路径；
- 适配器 A/B/C 贸易；
- H9 双分支影响；
- Ø100 通道、工具与维护空间。

必须主动攻击“可拆面板承担根部弯矩”的错误方案。

## Agent A2：Robot Kinematics & Native CAD

职责：

- Master Skeleton；
- 10 Carrier；
- 9 joint；
- q0、轴向、正负号、限位；
- T005-A0/B0/C0 与正式 T005；
- 精细几何按 link 挂接。

必须主动攻击：

- imported face/edge Mate；
- Move Component；
- Transform2 驱动；
- Fix Component 冒充 fixed；
- 单夹爪宽度冒充两个 P；
- Mate Controller 冒充真值。

## Agent A3：Controls & Free-Floating Dynamics

职责：

- 检查机械输出是否可供控制使用；
- 固定基座与自由漂浮模式分离；
- frame、joint、limit、2P、状态机；
- 基座6×6柔度/刚度；
- 结构模态与控制适用频带。

不得改变 accepted URDF 质量和惯量。

## Agent A4：Mechanism, Harness & Maintainability

职责：

- G07/G08/HDRM；
- 过约束检查；
- 逐关节线束；
- 连接器、编码器、盖板、相机、F/T、工具法兰；
- 拆装与复装基准；
- 发射收拢与释放路径。

必须主动攻击：

- 线束穿越关节轴；
- G08侵入2P全行程；
- 释放后残留体侵入初始抬离；
- 只能装不能拆的结构。

## Agent A5：Structural, Mass & Interface Analyst

职责：

- 结构前置条件；
- 单位载荷与根部弯矩；
- 紧固件分配、开孔、局部加强；
- G07/G08接触与屈曲；
- 三套质量账；
- 6×6接口柔度。

没有正式载荷谱时只允许：
`PRELIMINARY_UNIT_LOAD_AND_MODAL_CANDIDATE`。

## Agent A6：Verification & Evidence

职责：

- 每个 Gate 的机器可读 schema；
- bytes、SHA-256、路径与复算；
- H10 28行；
- T005 manifest；
- 连续间隙时程；
- 工程图空白视图检查；
- claim matrix。

拥有：证据不足时拒绝 PASS 的权力。

## Agent A7：Adversarial Red Team

职责：

独立于设计者，至少从以下角度尝试推翻结果：

1. Datum错层；
2. frame方向/右手性错误；
3. joint2/joint3 q0位于上限导致符号测试越界；
4. joint6 Mate flip；
5. 两P被错误耦合；
6. 同一文档 q0复位失败；
7. 冷重开掩盖连续驱动失败；
8. 供应商几何跨link挂接；
9. 可拆面板误获载荷信用；
10. G07/G08/HDRM刚性过约束；
11. 太阳翼失效时机械臂错误释放；
12. CAD质量覆盖URDF；
13. 工程图引用错误配置或默认质量；
14. 控制模型在frame不完整时提前发布。

Red Team只出具“攻击—证据—严重度—阻断Gate”，不得直接修改设计。

## Agent A8：AI / Embodied-System Integration Reviewer

职责：

- 检查输出是否支持 perception → candidate → physics → SAFE → control；
- 检查 camera、F/T、grasp center、tool frame；
- 检查 collision/visual/keepout；
- 检查状态机和 UNKNOWN/fail-closed；
- 确保 VLA 不直接绕过物理与安全 Gate。

不得宣称 VLA 已完成自主抓取。

---

# 4. Loop Engineering 工作法

每个阶段必须依次执行以下六轮，不能只做一次“自检”。

## Loop 0：Authority Lock

A0完成：

- 当前 Gate；
- Git状态；
- SolidWorks进程数；
- protected input hash；
- 授权会话和剩余次数；
- datum/naming/tolerance状态。

输出：
`LOOP00_AUTHORITY_LOCK.json`

任何不一致：停止。

## Loop 1：Design Synthesis

A1/A2/A4生成候选设计或CAD步骤。

输出必须包含：

- 设计目标；
- 输入；
- 设计变量；
- 保留TBD；
- 预期证据；
- 失败退出。

## Loop 2：Robotics & Control Cross-Check

A3检查：

- 拓扑；
- frame；
- 符号；
- q0；
- limits；
- fixed/free-floating；
- 2P；
- 状态机；
- 结构柔性接口。

不通过则返回 Loop 1。

## Loop 3：Mechanical & Structural Cross-Check

A1/A4/A5检查：

- 载荷路径；
- 接触；
- 过约束；
- 线束；
- 维护；
- 材料与连接来源；
- 结构分析前置条件。

不通过则返回 Loop 1。

## Loop 4：Evidence Verification

A6验证：

- 文件存在；
- bytes；
- hash；
- API回读；
- 配置；
- 外部引用；
- 质量贡献；
- 容差；
- 证据schema。

不通过不得提交 Red Team。

## Loop 5：Adversarial Review

A7/A8从机械、控制、AI和声明四方面攻击。

每轮必须输出：

- finding_id
- attacked_claim
- attack_method
- evidence
- severity
- gate_impact
- required_correction
- closure_evidence

Critical/High未关闭：Gate保持FAIL/HOLD。

## Loop 6：Final Claim Audit

A0+A6仅允许从机器结果生成结论。

禁止用：

- “看起来正确”
- “通常应该”
- “理论上可以”
- “截图显示”
- “SolidWorks默认值”

替代机器证据。

---

# 5. Phase 2A：原生坐标母体与Carrier运动链

## S00：离线G1闭合

在启动SolidWorks前：

1. 填写 datum reconciliation；
2. 填写 feature naming freeze；
3. 填写 acceptance tolerance authority；
4. 复算 Phase 2A input lock；
5. 生成：
   - `B51R1_PHASE2_G1_HUMAN_ADJUDICATION_RECEIPT.json`
   - `B51R1_PHASE2_G1_MULTIAGENT_REVIEW.md`
6. A7必须攻击三项裁决；
7. 人类签署后才可设置：
   - `PASS_HUMAN_RATIFIED`
   - `PASS_HUMAN_FROZEN`
   - `PASS_HUMAN_AUTHORIZED`
   - `PASS_HASH_LOCKED`

若任何一项仍为null，不得进入S01。

## S01：只创建最终Master Skeleton

严格使用单次明确授权。

输出：

`02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2.SLDPRT`

必须包含：

- 0实体；
- 0外部引用；
- 0质量贡献；
- 3配置；
- 受权 datum；
- 统一frame；
- G07/G08 footprint；
- keepout占位只标TBD/HOLD；
- 不打开或保存Stage A。

S01不创建Carrier、不创建装配。

## S02：只冷重开Master Skeleton

验证：

- 特征名；
- 类型；
- 16元素变换；
- 配置；
- datum数值；
- 0实体；
- 0外部引用；
- 0质量；
- hash；
- 正常退出。

通过状态：
`B51R1_PHASE2A_G2_MASTER_SKELETON_PASS`

## S03/S04：创建并冷重开10 Carrier

顺序必须为：

1. base_link
2. link1
3. link2
4. link3
5. link4
6. link5
7. link6
8. gripper_link
9. gripper_left
10. gripper_right

每个Carrier：

- 只含参考特征；
- 0实体；
- 0外部引用；
- 0质量；
- 唯一原生特征名称；
- accepted URDF source hash属性；
- 单独creation receipt；
- 单独cold reopen receipt。

首个失败即停止，不创建后续Carrier。

## S05：J00→J09与T005-A0/B0

逐关节：

- J00 baseline；
- J01 joint1；
- J02 joint2；
- J03 joint3；
- J04 joint4；
- J05 joint5；
- J06 joint6；
- J07 fixed gripper_joint；
- J08 gripper_joint1；
- J09 gripper_joint2。

R关节：

- 唯一driver；
- 原生Limit Angle；
- q_probe必须在软限位内部至少留1°；
- +1°/-1°符号测试；
- joint2/joint3禁止在q0执行+1°；
- q0显式复位。

P关节：

- 两个独立Limit Distance；
- 0～0.0715m各自坐标；
- 不推断总开度；
- 不建立mimic；
- q0/half/upper；
- q0显式复位。

执行：

- T005-A0：carrier-only独立位形；
- T005-B0：同一文档连续驱动并回q0。

T005-B0失败时，禁止用冷重开恢复来判PASS。

## S06：T005-C0

只在A0/B0通过后：

- 受控保存；
- 正常关闭；
- 正常退出；
- 新进程冷重开；
- 回读9个joint；
- 回读limits、q0、配置和分支；
- 检查外部引用和质量。

Phase 2A结论上限：

`B51R1_PHASE2A_NATIVE_SKELETON_CARRIER_CANDIDATE_ACCEPTED_WITH_DOWNSTREAM_HOLDS`

---

# 6. Phase 2B：B601精细工程装配

进入条件：

- Phase2A全部通过；
- 独立人工授权；
- 不改变accepted URDF。

创建：

`B51R1_B601_NATIVE_ARTICULATED.SLDASM`

规则：

- 精细几何只刚性挂接`CS_VISUAL_MOUNT_<LINK>`；
- 导入面/边不承担运动Mate；
- 每个几何体唯一link归属；
- 不能跨越相邻关节；
- visual质量不得覆盖URDF。

必须形成B601-M01～M11：

1. 关节法兰；
2. 外壳分段；
3. 检修盖板；
4. 连接器与线束出口；
5. 逐关节走线；
6. 编码器位置；
7. 硬限位功能包络；
8. 工具法兰；
9. F/T安装层；
10. 三处相机及支架；
11. collision/keepout保护包络。

然后执行正式T005-A/B/C。

---

# 7. Phase 2C：航天器接口与收拢释放

进入条件：

- H9人工裁决，或明确批准Mode A/B双分支；
- 正式T005通过；
- 适配器trade可评分。

完成：

- A/B/C适配器同口径贸易；
- 人工downselect；
- 基座法兰→适配器→真实主框/纵梁载荷路径；
- Ø100通道；
- 定位销、紧固件、工具空间；
- G07/G08 DOF allocation；
- HDRM功能包络；
- 过约束审计；
- H10 28/28。

H10退出：

- disposition complete=28/28
- UNACCEPTABLE_COLLISION=0
- UNRESOLVED=0

---

# 8. Phase 2D：整星装配与连续间隙

创建：

`B51R1_SPACE_EMBODIED_ROBOT_INTEGRATION.SLDASM`

状态：

- Q0
- STOWED_LOCKED
- SOLAR_DEPLOY_ARM_LOCKED
- SOLAR_DEPLOY_CONFIRMED
- HDRM_RELEASE_START
- ARM_CLEAR_OF_G07
- ARM_CLEAR_OF_G08
- ARM_CLEAR_OF_RESTRAINT_AND_KEEPOUT
- DEPLOYED_NOMINAL
- SERVICE
- 2P_OPEN
- 2P_HALF
- 2P_CLOSED
- RELEASE_FAILED
- SOLAR_DEPLOY_FAILED

检查CL-01～CL-08连续pair matrix。

左翼、右翼、双翼失效均单独计算，禁止复制数值。

---

# 9. Phase 2E：结构、质量和控制交接

## 9.1 结构

没有正式载荷谱时，仅：

`PRELIMINARY_UNIT_LOAD_AND_MODAL_CANDIDATE`

输出：

- 适配器单位载荷；
- 根部弯矩；
- 紧固件分配；
- 面翘曲；
- 开孔影响；
- 纵梁加强；
- G07/G08接触与屈曲；
- 6×6柔度/刚度；
- 模态、参与系数、适用频带。

## 9.2 三账

分开：

1. accepted URDF动力学账；
2. B601 CAD候选账；
3. 整星质量/质心/惯量账。

Carrier质量永远为0。

## 9.3 控制与AI交接

生成8个文件，最初状态只能：

`DRAFT_NOT_RELEASED`

必须支持：

- FIXED_BASE_DEBUG
- FREE_FLOATING_VALIDATION
- sensor frames
- tool/grasp frames
- collision/visual/keepout
- stow/release FSM
- unknown/provisional参数
- SAFE-00调用边界

---

# 10. 强制输出格式

每个阶段结束时只输出：

1. 已读取权威输入；
2. 已创建资产；
3. 机器验证；
4. Multi-Agent findings；
5. 关闭的问题；
6. 剩余HOLD/FAIL；
7. 当前Gate；
8. 下一次唯一授权语句。

禁止输出大量无意义日志。

---

# 11. 当前首次动作

现在先执行S00离线G1，不启动SolidWorks：

1. 打开Phase2A启动包；
2. 复算11/11文件；
3. 应用专家建议datum；
4. 应用展开式唯一原生命名；
5. 应用CAD一致性容差；
6. 生成Multi-Agent对抗审查；
7. 输出三份待人类签名文件和G1收据；
8. 保持S01未授权；
9. 给出仅S01的精确授权文本。

不得自行签名，不得自行启动SolidWorks。
