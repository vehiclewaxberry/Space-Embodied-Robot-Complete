# Codex 执行提示词：B5.1R1 Phase 2A 原生 Skeleton / Carrier

> 当前状态：`PREPARED_NOT_AUTHORIZED / G1_HOLD`。在 `B51R1_PHASE2A_AUTHORIZATION.yaml` 被人类完整签发、对应会话明确列入授权范围且 G1 全部通过前，禁止执行本提示词中的任何 SolidWorks 动作。

## 1. 任务上限

本阶段的唯一工程范围是：

```text
最终原生 Master Skeleton
→ 10 个零质量运动学 Carrier
→ 6R + 1 fixed + 2 independent P 的 Carrier-only 原生链
→ J00..J09 增量检查点
→ Carrier-only T005-A0/B0/C0
```

本阶段不授权精细 B601 几何挂接、基座适配器、G07、G08、HDRM、H9 裁决、H10、正式 T005-A/B/C、连续间隙、FEA、最终工程图或控制模型发布。

## 2. 绝对权威和保护对象

- accepted URDF SHA-256：`1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164`。
- accepted URDF 总质量：`4.6955559493429862 kg`。
- Stage A SHA-256：`5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B`，全程只读且前后哈希必须一致。
- 单坐标系 Gate SHA-256：`6D0C27E154E3F1ACA150EA35B2A945EC257D1CB2898A06AB5AC9448A9AF3EC5E`，只证明单坐标系持久化，不自动授权原生建模。
- Carrier 拓扑：10 link、9 joint、`6R + 1 fixed + 2 independent P`；`gripper_link` 为两个 P 分支的共同父 link，不得错误串联。
- 所有 Carrier：`MODEL_ROLE=KINEMATIC_CARRIER`、`CAD_MASS_CONTRIBUTION=ZERO`、`BOM_EXCLUDE=TRUE`、`DYNAMIC_AUTHORITY=ACCEPTED_URDF`。

## 3. G1 离线前置条件

开始任何可见会话前必须逐项验证：

1. `B51R1_PHASE2A_INPUT_LOCK.json` 中全部输入路径、字节数和 SHA-256 一致；
2. datum 协调文件已由人类填写最终裁决并改为 `PASS_HUMAN_RATIFIED`；
3. 特征命名文件已由人类选择唯一原生命名方案并改为 `PASS_HUMAN_FROZEN`；
4. 验收容差文件已由具名权威填写数值、单位、适用对象、签发时间和证据引用并改为 `PASS_HUMAN_AUTHORIZED`；
5. 当前会话在授权 YAML 中被明确列入 `authorized_session_ids`，可见启动数大于零且未消耗；
6. SolidWorks 进程数为 0，目标输出在预期状态，不存在未登记的临时副本或恢复状态；
7. 受保护输入只读，写入根严格限制在 B5.1R1 隔离候选目录内。

任一项失败：记录 `FAIL_CLOSED_G1_HOLD`，不得启动 SolidWorks。

## 4. 会话执行顺序

每次会话只执行 `B51R1_PHASE2A_LAUNCH_AND_SESSION_SCOPE.yaml` 中的一个会话。不得把一个会话的授权外推到后续会话。

### S01：创建最终 Master Skeleton

- 在全新、可见、响应正常的 SolidWorks 2024 进程中创建并保存 `02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2.SLDPRT`。
- 只使用经人类闭合的 datum 和命名合同。
- 必须含 `COMMON_CANONICAL`、`MODE_A_EVALUATION`、`MODE_B_EVALUATION`；H9 不得被隐式选择。
- 保持 0 实体、0 外部引用、CAD 质量贡献 0。
- Stage A 只读；不得另存、覆盖、修复或更新它。
- 保存、回读、关闭文档并正常退出；生成 S01 收据。不得创建 Carrier。

### S02：冷重开并验收最终 Master Skeleton

- 在新的可见进程中只打开 S01 输出一次。
- 枚举配置、命名特征、坐标变换、实体数、外部引用和质量贡献。
- 按人类授权容差比对；执行一次受控保存（若授权明确要求），记录前后字节数和 SHA-256。
- 正常关闭并退出。未通过不得进入 S03。

### S03：按 accepted link 顺序创建 10 Carrier

严格按以下顺序，逐件创建、保存、关闭并生成独立收据：

```text
base_link, link1, link2, link3, link4,
link5, link6, gripper_link, gripper_left, gripper_right
```

每件仅含经冻结的 link frame、入/出关节 frame、轴、q0 面和 visual mount；每件 0 实体、0 外部引用、质量贡献 0、BOM 排除。首个失败即停止，保留已通过文件，不继续后续 Carrier。

### S04：新进程逐个冷重开 10 Carrier

- 逐件只开一次，枚举命名特征与变换并按人类容差比对。
- 记录每件 SHA-256、外部引用、实体数、质量贡献、属性和正常关闭结果。
- 10/10 全通过前不得进入 S05。

### S05：J00..J09 增量建链与 T005-A0/B0

- 创建 `03_CAD/10_KINEMATIC_CARRIERS/B51R1_CARRIER_CHAIN_NATIVE.SLDASM`。
- `J00_BASELINE` 后按 accepted joint 顺序一次只增加一个 joint；每步保存、回读并生成不可变检查点。
- 六个 R 关节各有且只有一个原生 Limit Angle 驱动；fixed 使用精确 URDF 变换且不得 `Fix Component`；两个 P 各有且只有一个原生 Limit Distance 驱动。
- 禁止 `Move Component` 保存姿态、`Transform2` 驱动、锁旋转同心配合、第二命令 Mate 或 Mate Controller 真值。
- 完成 Carrier-only T005-A0 独立位形和 T005-B0 同文档连续驱动并返回 q0；正常关闭并退出。

### S06：冷重开 Carrier 链与 T005-C0

- 新进程冷重开 S05 链，验证所有 native Mate、limit、配置、J00..J09、q0 和两条独立 P 分支持久化。
- 执行 T005-C0；不得用冷重开通过替代 T005-B0。
- 正常关闭并退出，生成 G5 候选收据。

## 5. 强制 fail-closed

出现以下任一情况立即停止当前会话，不得补猜、绕过或继续下一 Gate：

- 输入哈希、datum、命名、容差或授权不一致；
- 恢复对话框无法在当前授权范围内安全处理；
- API hang、保存错误/警告、文档标题不一致或进程未正常退出；
- 外部引用非零、实体非零、Carrier 质量贡献非零；
- 坐标、轴、q0 或符号超出人类授权容差；
- Mate 翻转、多驱动、冗余约束、P 分支串联或 q0 同文档复位失败；
- Stage A 哈希变化；
- 试图跨会话、跨 Gate 或扩大写入范围。

异常处理必须遵守 `B51R1_PHASE2A_RECOVERY_POLICY.md`。任何失败只允许形成诚实的 HOLD/incident 证据，不得升级结论。

## 6. 结论上限

只有 S01..S06 按顺序分别获授权并通过，才可提出：

`B51R1_PHASE2A_NATIVE_SKELETON_CARRIER_CANDIDATE_ACCEPTED_WITH_DOWNSTREAM_HOLDS`

即使通过，H9、适配器、G07/G08/HDRM、H10、正式 T005、连续间隙、结构资格和发布文件仍保持 HOLD。
