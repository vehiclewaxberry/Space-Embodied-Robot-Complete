# B5.1R1 单坐标系诊断证据汇总

## 结论

当前正式判定为：

`PARTIAL_PASS_EVIDENCE_HOLD_COLD_REOPEN_PENDING`

首轮可见进程中的几何构造、单次坐标系插入、保存、同进程强类型回读、按当前文档标题关闭以及正常退出请求均有证据支持。由于原始首轮不可变收据仍是 `FAIL_CLOSED_FIRST_LAUNCH`，第二次恢复工具又在进程退出后读取外部 `Process.ExitCode` 时抛出 `InvalidOperationException`，未形成正常的 recovery PASS 收据；冷进程重开也未获本包授权。因此：

- 单坐标系完整诊断 PASS：`false`
- 原生机械设计继续放行：`false`
- 冷重开：`NOT_RUN_REQUIRES_SEPARATE_VISIBLE_LAUNCH_AUTHORIZATION`
- Phase 总 Gate、总报告、索引：本次未修改

## 已确认事实

| 检查项 | 结果 | 证据判定 |
|---|---:|---|
| `InsertCoordinateSystem` 调用数 | 1 | PASS |
| 精确名称 `CS_DIAGNOSTIC_ONLY` 数量 | 1 | PASS |
| 特征类型 | `CoordSys` | PASS |
| 坐标变换 | 单位旋转、零平移、比例 1 | PASS |
| 最大单位阵误差 | 0 | PASS |
| 外部文件引用 | 0 | PASS |
| 保存错误 / 警告 | 0 / 0 | PASS |
| 目标文件 | 49233 bytes，SHA-256 `6B571B49D440BBDC723566FA97224C69AFABCBA6BAC34DCF4036A5F4037E120C` | PASS |
| Stage A 前后哈希 | 均为 `5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B` | 未修改 |
| 按当前标题关闭 | `CloseDoc(model.GetTitle())`，关闭后文档数 0 | PASS |
| `ExitApp` | 已调用 | 有运行日志 |
| 进程退出等待 | `WaitForExit` 已返回 | 有运行日志 |
| 当前 SolidWorks 进程数 | 0（检查时间 `2026-07-29T18:34:36.6511826Z`） | PASS |
| 外部进程 `ExitCode` | `UNAVAILABLE` | 证据工具缺陷，不等于 CAD 退出失败 |
| 项目内截图文件 | 0 | 不计 Gate 信用 |
| 冷进程重开 | 未运行、未授权 | HOLD |

## 运行时间线

### 首轮创建

首轮工具在唯一、可见、响应正常且空文档的 SolidWorks 2024 SP5 进程中创建空白零件。它确认三个默认正交基准面与原点，建立单一支撑 3D 草图，并恰好调用一次 `InsertCoordinateSystem`。坐标系被命名为 `CS_DIAGNOSTIC_ONLY`，类型读回为 `CoordSys`，数量为 1；外部引用为 0，保存错误和警告均为 0。

原始工具随后以旧的会话空状态判据失败，生成不可变收据：

- `07_VERIFICATION/B51R1_SINGLE_CS_DIAGNOSTIC_FIRST_LAUNCH_RECEIPT.json`
- 状态：`FAIL_CLOSED_FIRST_LAUNCH`
- 失败点：`VERIFY_SESSION_EMPTY_AFTER_CLOSE`

该收据未被覆盖，仍是首轮执行的原始控制证据。

### 恢复尝试 1

第一次恢复尝试在仅附着现有进程时遇到：

`TYPE_E_ELEMENTNOTFOUND (0x8002802B)`

因此生成 `FAIL_CLOSED_POSTSAVE_RECOVERY`，没有取得恢复 PASS 信用。

### 恢复尝试 2

第二次恢复使用强类型 SolidWorks 互操作完成了以下动作：

1. 重新读取 `CS_DIAGNOSTIC_ONLY`，确认精确数量为 1、类型为 `CoordSys`。
2. 读取 16 元素变换数组，确认单位旋转、零平移、比例 1，最大误差为 0。
3. 确认外部文件引用为 0。
4. 使用 `CloseDoc(model.GetTitle())` 关闭当前目标文档，关闭后文档数为 0。
5. 读取目标零件哈希并确认 Stage A 哈希未改变。
6. 调用 `ExitApp`，随后 `WaitForExit` 返回。

工具之后读取并非由该 `Process` 对象启动的外部进程之 `ExitCode`，抛出：

`System.InvalidOperationException: 进程不是由此对象启动的，因此无法确定所请求的信息。`

因此正式记录：

- `exit_code = UNAVAILABLE`
- 正常 recovery PASS 收据不存在
- 不能把该工具异常提升为完整诊断 PASS
- 当前只可确认 `ExitApp` 已调用、等待已结束且后续只读检查发现 SolidWorks 进程数为 0

## 证据文件

| 文件 | SHA-256 |
|---|---|
| `07_VERIFICATION/B51R1_SINGLE_CS_DIAGNOSTIC_FIRST_LAUNCH_RECEIPT.json` | `20666BD9B09B5DD6480E4D9ABE25934813524BCA90FA76656C724E9CEFCDAFC4` |
| `07_VERIFICATION/B51R1_SINGLE_CS_DIAGNOSTIC_TRANSFORM_FIRST_LAUNCH.json` | `CE593DD8F9937EEBA9295D602855B99C4075AA8F8859691B38C25935CA8449CC` |
| `07_VERIFICATION/B51R1_SINGLE_CS_DIAGNOSTIC_POSTSAVE_RECOVERY_FAIL_CLOSED.json` | `C90DE72AD2809E21A098A631BEAE40167DA0E18581EC025DBE8BD2892CF0B989` |
| `07_VERIFICATION/B51R1_SINGLE_CS_DIAGNOSTIC_POSTSAVE_RECOVERY_ATTEMPT_002_FAIL_CLOSED.json` | `366349154B2E7FFACD7F825F897CC7E108020AA686FE5743039BA9FC2DDD659B` |
| `08_REVIEWS/B51R1_SINGLE_CS_DIAGNOSTIC_FIRST_LAUNCH_PROGRESS.log` | `DB5BF41F4E53C0B2D6F45D3D4E2AD3DAD9C78B74F66DD064E58CBDD9479B805B` |
| `08_REVIEWS/B51R1_SINGLE_CS_DIAGNOSTIC_POSTSAVE_RECOVERY_PROGRESS.log` | `3CC1B5B4595C93717FDB61F112A05719376697F5622F6CE7141C5BEB7C629DFD` |
| `08_REVIEWS/B51R1_SINGLE_CS_DIAGNOSTIC_POSTSAVE_RECOVERY_ATTEMPT_002_PROGRESS.log` | `AA32DDAF06202708621C93CEF728E2C11E46C0D10656FD2F4B529345E678F7B3` |
| `07_VERIFICATION/B51R1_MECHANICS_CONTROL_CONTINUATION_PACKAGE_ADMISSION.json` | `E2DFBBC019F72163A971529A18BB1972805A1043D6BAD6B34CFFE8F6736B46B4` |

## 截图边界

执行期间截图只在 Codex 可见任务界面中显示，没有保存为候选工程目录内的持久文件。因此这些画面不能获得项目 Gate 信用，也不能替代冷重开证据。

## 下一 Gate

需要新的、明确的第二次可见启动授权后，才能在全新 SolidWorks 进程中冷重开已保存目标，并验证：

1. 精确存在 1 个 `CS_DIAGNOSTIC_ONLY`；
2. 类型仍为 `CoordSys`；
3. 变换仍为单位旋转、零平移、比例 1；
4. 外部引用仍为 0；
5. 文档可正常关闭，进程可正常退出；
6. 形成新的不可变 cold-reopen PASS 或 fail-closed 收据。

在此之前，禁止声明 `FULL_SINGLE_CS_DIAGNOSTIC_PASS`、原生载体放行、H10 闭合、T005 通过、控制参数发布、`COMPLETE`、`MANUFACTURING_READY`、`FLIGHT_READY` 或 `LAUNCH_QUALIFIED`。
