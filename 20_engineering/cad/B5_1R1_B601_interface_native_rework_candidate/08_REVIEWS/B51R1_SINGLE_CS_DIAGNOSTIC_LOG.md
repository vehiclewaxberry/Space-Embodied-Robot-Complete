# B5.1R1 单坐标系诊断与冷重开持久化审查记录

日期：2026-08-01  
任务：`COMP-PROT-03-A4-B5.1R1-PHASE1`

## 正式结论

单坐标系诊断 Gate 已升级为：

`SINGLE_COORDINATE_SYSTEM_PERSISTENCE_PASS`

新授权限定的一次可见 SolidWorks 2024 启动已经消耗完毕。固定目标在全新进程中冷打开，强类型回读确认仍恰好存在一个 `CS_DIAGNOSTIC_ONLY`，类型为 `CoordSys`，变换为单位旋转、零平移、比例 1，外部文件引用为 0。随后只执行一次受控 `Save3`，保存错误/警告为 `0/0`，按当前标题关闭后文档数为 0，`ExitApp` 后进程消失，当前 SolidWorks 进程数为 0。

这个 PASS 只关闭“单坐标系保存后能否跨全新 SolidWorks 进程持久存在”的诊断问题。它不自动放行最终 Master Skeleton、10 个原生 Carrier、`6R + 1 fixed + 2P` 装配、H10、T005 或机械—控制交接。后续原生 authoring 仍需单独的可见启动授权。

## 冷重开持久化证据

| 检查项 | 结果 | 裁决 |
|---|---:|---|
| 冷重开目标 | `B51R1_SINGLE_CS_DIAGNOSTIC_COPY.SLDPRT` | 固定目标 |
| `OpenDoc6` 调用数 | 1 | PASS |
| 打开错误 / 警告 | 0 / 0 | PASS |
| `CS_DIAGNOSTIC_ONLY` 精确名称数量 | 1 | PASS |
| 特征类型 | `CoordSys` | PASS |
| 坐标变换 | 单位旋转、零平移、比例 1 | PASS |
| 最大单位阵误差 | 0 | PASS |
| 外部文件引用 | 0 | PASS |
| `Save3` 调用数 | 1 | PASS |
| 保存错误 / 警告 | 0 / 0 | PASS |
| 关闭后文档数 | 0 | PASS |
| 进程退出 | `HasExited=true`，退出后进程数 0 | PASS |
| 外部进程 `ExitCode` | `UNAVAILABLE` | 非失败元数据；以进程消失为退出证据 |
| 强制终止 | 未使用 | PASS |
| Stage A SHA-256 前 / 后 | 均为 `5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B` | 未修改 |

不可变运行证据：

| 文件 | SHA-256 |
|---|---|
| `07_VERIFICATION/B51R1_SINGLE_CS_DIAGNOSTIC_COLD_REOPEN_RECEIPT.json` | `534316819A07D7204764511A4732C99C172311CE26935156AF6AE129DA06CA0D` |
| `07_VERIFICATION/B51R1_SINGLE_CS_DIAGNOSTIC_TRANSFORM_COLD_REOPEN.json` | `3BCA317E99629143326020FBCF7D5923680E9E1196A1A423FFEAFA062403C731` |
| `08_REVIEWS/B51R1_SINGLE_CS_DIAGNOSTIC_COLD_REOPEN_PROGRESS.log` | `24A7ABC64C53492B8B4A014627874F2045539BB3D723073F4D794D1BEE646B2D` |

正式汇总证据：

| 文件 | SHA-256 |
|---|---|
| `07_VERIFICATION/B51R1_SINGLE_CS_DIAGNOSTIC_TRANSFORM.json` | `C6BFBC3BA85711C4D1EBC6596D6CA92774CDBF7B7352FE561E0986314A2B7104` |
| `07_VERIFICATION/B51R1_SINGLE_CS_DIAGNOSTIC_GATE.json` | `6D0C27E154E3F1ACA150EA35B2A945EC257D1CB2898A06AB5AC9448A9AF3EC5E` |

## 受控保存后的文件哈希变化

目标文件在冷打开前为：

- `49233 bytes`
- SHA-256 `6B571B49D440BBDC723566FA97224C69AFABCBA6BAC34DCF4036A5F4037E120C`

一次受控 `Save3` 并关闭后为：

- `51508 bytes`
- SHA-256 `D55277E924B56F76EFA3682C7628B8FE841172792280E0FE57CDE4A90E3A4ABD`

正式解释为：

`HASH_CHANGED_AFTER_THE_SINGLE_CONTROLLED_SAVE3; SEMANTIC_INVARIANTS_UNCHANGED; BYTE_LEVEL_CAUSE_NOT_FURTHER_RESOLVED`

也就是说，哈希变化与本轮唯一一次受控原生保存相关；冷重开前后的坐标系数量、名称、类型、变换和外部引用等语义不变量保持不变。当前证据没有进一步解析 `.SLDPRT` 字节差异的精确内部来源，因此不得把哈希变化解释成几何变化、动力学变化或未授权内容修改。

## 历史 fail-closed 证据的处理

以下历史文件继续保留，不被覆盖：

- 首轮不可变收据 `FAIL_CLOSED_FIRST_LAUNCH`，失败点为旧的 `VERIFY_SESSION_EMPTY_AFTER_CLOSE` 判据；
- 恢复尝试 1 的动态 COM `TYPE_E_ELEMENTNOTFOUND (0x8002802B)`；
- 恢复尝试 2 对外部附着进程读取 `ExitCode` 时的 `InvalidOperationException`；
- Stage B 坐标 API hang 事故记录。

这些记录描述先前工具链与会话判据的真实失败历史。新冷重开收据没有改写它们，而是用全新进程、强类型回读、当前标题关闭、进程消失判据和不可变证据完成了原先缺失的持久化闭环。因此它们不再控制单坐标 Gate，但继续控制各自历史运行的事实边界。

## 授权与证据边界

本轮授权录入：

- `07_VERIFICATION/B51R1_COLD_REOPEN_AUTHORIZATION_ADMISSION_20260801.json`
- SHA-256 `3BC20BFBA9AAAB8A61A1E2A580C35B4977DA8169F15597453A82A4F2518E0BC4`
- 状态 `ADMITTED_SINGLE_VISIBLE_LAUNCH_COLD_REOPEN_ONLY`
- 可见启动：授权 1、已消耗 1、剩余 0

本轮没有修改 Stage A，没有创建最终 Master Skeleton 或 Carrier，没有运行 H10/T005，也没有创建机械—控制正式交接文件。Codex 任务 UI 中曾可见冷重开后的坐标系特征，但项目目录中没有持久化截图；本 Gate 不要求截图，故不影响持久化 PASS，也不向其他机械 Gate 转移截图信用。

## 仍然有效的机械工程 HOLD

- 最终 `B51R1_MASTER_SKELETON_V2.SLDPRT`：不存在，`HOLD`；
- 原生 Carrier：`0/10`；
- H9：`UNRESOLVED_HUMAN_DECISION_REQUIRED`；
- H10：`0/28`，`UNRESOLVED=28`；
- T005-A/B/C：全部 `NOT_RUN`；
- mechanics-control handoff：`NOT_RELEASED`，以下 8 个正式交接文件仍缺失：
  - `B51R1_MECH_CONTROL_HANDOFF_CONTRACT.yaml`
  - `B51R1_JOINT_ACTUATION_PARAMETER_REGISTER.csv`
  - `B51R1_JOINT_ZERO_SIGN_LIMIT_REGISTER.yaml`
  - `B51R1_SENSOR_FRAME_REGISTER.yaml`
  - `B51R1_BASE_INTERFACE_COMPLIANCE.yaml`
  - `B51R1_STOW_RELEASE_STATE_MACHINE.yaml`
  - `B51R1_COLLISION_MODEL_MAPPING.yaml`
  - `B51R1_CONTROL_MODEL_VALIDATION_MATRIX.csv`

Phase 2 机械工程执行图已准备但未授权：

- `09_DELIVERY/B51R1_PHASE2_MECHANICAL_ENGINEERING_EXECUTION_MAP_20260801.md`
- SHA-256 `722773988310A166EE8F006E16C2D1B934D82E68A35B35734AB83EDF8CA3AB90`
- 状态 `B51R1_PHASE2_MECHANICAL_ENGINEERING_EXECUTION_MAP_PREPARED_NOT_AUTHORIZED`

## 下一 Gate

单坐标 Gate 已无未决项。下一步只能在新的、明确的可见启动授权下进入有界的 Phase 2A：先完成 datum 协调、特征命名冻结、输入锁和验收容差权威，再分会话创建与冷重开最终 Master Skeleton、10 个 Carrier 和 Carrier-only 原生关节链。当前授权不能外推到该工作。

当前 Phase 结论上限为：

`INTERMEDIATE_GATE_SINGLE_CS_PERSISTENCE_PASS_NATIVE_AUTHORING_SEPARATE_AUTHORIZATION_HOLD`

禁止使用 `COMPLETE`、`MANUFACTURING_READY`、`FLIGHT_READY` 或 `LAUNCH_QUALIFIED`。
