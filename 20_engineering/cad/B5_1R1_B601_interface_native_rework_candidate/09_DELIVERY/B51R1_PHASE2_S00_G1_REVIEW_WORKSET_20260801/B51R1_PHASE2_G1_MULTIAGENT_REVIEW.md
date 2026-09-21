# B5.1R1 Phase 2 G1 多智能体对抗审查

裁决：`B51R1_PHASE2_S00_AUTHORITY_INPUTS_HASH_VERIFIED_G1_HOLD`

本轮为 S00 离线审查。未启动或附着 SolidWorks，未创建或修改原生 CAD，未填写任何人类签名字段，未授权 S01。

## 1. 审查组织

- A0/A6：权威、输入锁、哈希、授权、进程和证据链只读审计；
- A1/A4/A5/A7：航天器结构、接口、收拢释放、维护、质量与机械红队；
- A2/A3/A8：机器人原生运动、控制、自由漂浮动力学、传感/碰撞与具身安全红队；
- Root Integrator：只负责合并相互独立的 finding、创建待审工作集和执行格式/哈希终审，不替人类签署。

设计审查与红队审查分开；Finding 只有在对应专业 reviewer、A6 和 A0 均认可证据后才能关闭。

## 2. 已复核权威输入

- 新 intake ZIP：11,814 bytes，SHA-256 `277AFF81693DF362BBE45B01528452156E9481FD003E07C903E8E0358BABFDD2`；5/5 安全条目，归档副本逐字节相同。
- 原 Phase 2A 启动包：11/11 文件；ZIP 24,023 bytes，SHA-256 `EE44124CC0DB1E0F6757F3662D66729B2D4CB3CF2F3391D2370CC0F8CC8D226C`。
- V1 input lock：15/15 路径、bytes 和 SHA-256 当前匹配。
- Single-CS Gate：`SINGLE_COORDINATE_SYSTEM_PERSISTENCE_PASS`，但 `native_authoring_release=false`。
- Phase Gate：`INTERMEDIATE_GATE_SINGLE_CS_PERSISTENCE_PASS_NATIVE_AUTHORING_SEPARATE_AUTHORIZATION_HOLD`。
- accepted URDF：10 links、9 joints、`6R + 1 fixed + 2P`、mimic=0，质量权威精确文本 `4.6955559493429862 kg`。
- Stage A：511,198 bytes，SHA-256 `5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B`。
- 审查时 `SLDWORKS.exe=0`；最终 Skeleton 不存在、Carrier `0/10`、原生 chain 不存在。

## 3. Finding 统计与 Gate 范围

完整机器可读记录见 `B51R1_PHASE2_G1_ADVERSARIAL_FINDINGS.csv`：

- 总 finding：35；
- Critical：11；High：22；Medium：2；
- G1A 范围：12；G1B 范围：2；
- 下游具名 `DEFERRED_HOLD`：19；
- 其余为 W00 控制项或全 Gate 审查覆盖项。

Gate 范围规则：

- G1A/G1B 相关 Critical/High 未关闭，禁止 S01；
- 纯下游问题不得被伪关闭，只能由 A0/A6 接纳为带 `defer_to_gate` 的 `DEFERRED_HOLD_REGISTERED`；
- 被延期的问题在指定未来 Gate 自动重新成为硬阻断。

对应处置表见 `B51R1_PHASE2_FINDING_DISPOSITION_REGISTER.csv`。

## 4. G1A/G1B 硬阻断

### 4.1 权威与证据链

1. 原 V1 input lock 未锁入新 intake、当前 Phase Gate、签署后三份权威、review/receipt 和 Stage A 锁文件处置。
2. 原 29 行 manifest 缺 S00 证据、S01/S02 收据和 10×S03/10×S04 收据。
3. 原 authorization/prompt 不检查 G1A receipt、V2 lock、Red-Team 处置或 Stage A 锁文件。
4. G1 与 S01 授权存在循环；必须采用 `G1A_AUTHORITY_AND_HASH_LOCK` → `G1B_S01_ADMISSION`。
5. Git 工作区不干净，Git 只能记录快照，不能替代文件哈希锁。

### 4.2 Datum

建议仍为：101.65 mm 纵梁轴、110.15 mm 主承力面、113.15 mm 面板/footprint 层。历史 105.65 mm 可以由人类签署为“语义仍未解决、保留、禁止驱动”，不能为了过 Gate 强行猜测其物理含义。

### 4.3 特征命名与 ownership

建议采用逐 link/joint 展开名称，但下列反直觉语义必须人工确认：当前 mapping 把 `CS_CHILD_JOINT_<JOINT>` 放在父/出端，把 `CS_PARENT_JOINT_<JOINT>` 放在子/入端；input-locked Carrier register 把 moving axis/q0 plane 放在子/入端 Carrier。第三套旧缩写只能作为只读 alias，不能参与 API 查找。

### 4.4 数值验收容差

V1 把米和弧度字段合并，无法无损承载专家建议。本工作集已拆成 14 项。R 关节 readback、q0、limit 和 cold-reopen 必须使用“无包络的有界 joint coordinate 差 + branch index”，不能用 shortest-angle 隐藏 J6 的 ±2π 翻转；SO(3) geodesic 只用于 frame/FK 旋转。

### 4.5 Stage A 锁文件

Stage A 目录存在 6-byte `~$B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT`，SHA-256 `0D477825E5F9D305044B3EADCCAFFB403858E766BDC2E4BBD94A728DA79A4F47`。本轮未删除。Owner 必须批准处置方式，并在处置后证明 Stage A hash 未变。

## 5. 下游机械结构 DEFERRED HOLD

- G07/G08 footprint 当前位于 113.15 mm 可拆面板层，必须保持 `LOAD_CREDIT_NONE`；真实承力须绕过面板进入命名主框/纵梁。
- 适配器 A/B/C 的载荷路径、fastener、工具、质量、刚度、H10、评分和 Mode A/B 分支仍为 TBD，无 downselect。
- G07/G08/HDRM 的定性 DOF 表不能证明不过约束；需统一 contact frame、Jacobian、单边接触、摩擦、预紧、柔度和容差角点。
- 状态矩阵缺 `SOLAR_DEPLOY_CONFIRMED`、`HDRM_RELEASE_CONFIRMED`、独立 G07/G08 clear 和完整故障分支。
- 连续间隙必须拆为 G8a 刚体名义检查和 G8b 结构/热/容差/线束/回差后的鲁棒复查。
- 6×6 接口矩阵须冻结作用点、wrench/twist 顺序、单位、符号、变换、边界、平衡和收敛规则。
- HDRM holding、预紧损失、shock、释放、残留体和失败状态尚无器件/载荷权威。
- URDF 是当前项目动力学权威，但其 header 明示 physical weighing pending、confidence medium；不能据此声称物理或飞行级质量成熟度。
- 三质量账还需明确旋转、平行轴、张量符号、状态构型和 additive-body/inertia overlay。

## 6. 下游机器人/控制/具身 DEFERRED HOLD

- URDF 引用 10 个 `meshes_b601_gripper/*.STL`，工作区实际为 `0/10`；visual/collision、MuJoCo 和 Isaac Sim 依赖未闭合。
- URDF header 说两 P 在 dynamics v1 锁定，但 XML 定义两个独立可动 P；锁定值、模式维数和切换权限未裁决。
- fixed `gripper_joint` 使用零轴向量；须做 target parser compatibility gate。
- J6 的近 2π Limit Angle 需要全行程单调、branch、保存和冷重开 oracle。
- `FREE_FLOATING_VALIDATION` 当前只是标签；缺 bus 6-DOF、机构状态、动量守恒、反作用、轮/推力器饱和和跨求解器 oracle。
- `CS_GRASP_CENTER` 是 q/contact/object-dependent 运行时量，不能被一个静态 frame 记录替代；`2P_CLOSED` 也不能在物理零位未标定时成立。
- SAFE-00 仍是文字流程；缺 typed contract、freshness、UNKNOWN、interlock、override、fault injection 和 actuator permission。
- Camera/F-T/碰撞/contact 仍缺坐标约定、时间、协方差、偏置/饱和、allowed-contact、margin 与不确定度膨胀规则。

## 7. 本工作集已经实施的框架修正

以下均为离线候选，不等于人类批准：

- 建立 `LOOP00_AUTHORITY_LOCK.json`；
- 拆分 G1A/G1B，建立 G1B S01 admission V2 pending schema；
- 建立三份独立待签权威文件，不修改原 11 文件包；
- 将容差 schema 正规化为 14 项并加入 branch index；
- 建立 10-row expanded native feature register，并按 input-locked Carrier register 调整 axis/q0 ownership；
- 建立 URDF dependency/parser Gate；
- 建立 35-row adversarial findings、Gate-scoped disposition register 和 claim matrix；
- 建立完整 Phase 2 工程内容框架和 V2 refreeze plan。

## 8. 人类审核与退出条件

Owner 需要：

1. 签署 datum、命名和容差三份文件；
2. 裁决 Stage A 锁文件；
3. 由 A0/A6 审批 Gate-scoped finding disposition；
4. 关闭全部 G1A blocking finding；
5. 生成并复核 V2 expected manifest 与 V2 input lock；
6. 将 G1 receipt 设置为 `PASS_HUMAN_RATIFIED_AND_HASH_LOCKED`；
7. 随后单独签发 G1B，仅授权 S01 一次可见启动。

当前不得使用：`G1_PASS`、`S01_AUTHORIZED`、`NATIVE_SKELETON_ACCEPTED`、`10_CARRIERS_ACCEPTED`、`NATIVE_6R_1_FIXED_2P_ACCEPTED`、`MANUFACTURING_READY` 或 `FLIGHT_READY`。
