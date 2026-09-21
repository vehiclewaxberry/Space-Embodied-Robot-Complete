# B5.1R1 S02_SR01 冷重开失败根因与修复 HOLD

生成时间：2026-08-02T21:27:23.9192957+08:00

## 结论

`S02_SR01` 已完成对用户预先打开的唯一 SolidWorks 进程的附着，并成功以静默、只读方式打开固定 Master Skeleton。失败不再是进程启动或 ROT 超时，而是目标文件缺少必需的文档级自定义属性 `G1B_RECEIPT_SHA256`。

运行时证据为：

```text
failed_stage = TEN_REBUILD_READBACK_CYCLES
Get6("G1B_RECEIPT_SHA256", useCached=false) = 1
1 = swCustomInfoGetResult_NotPresent
save_api_call_count = 0
normal_document_close = true
normal_application_exit = true
```

Master Skeleton、Stage A、S01 current gate 及上一轮 S02 失败证据的 SHA、字节数和修改时间均未改变。

## 已确认的实现根因

`08_REVIEWS/B51R1_S01_MasterSkeletonFinalizer.cs` 第 188–196 行对八个文档属性调用了 `Set2`，没有先调用 `Add3`，也没有检查 `Set2` 返回值。

SOLIDWORKS API 的 `Set2` 参数是“现有自定义属性”的名称；本机 2024 interop 中 `swCustomInfoSetResult_NotPresent=1`。因此当模板中不存在这些属性时，`Set2` 不会创建属性。S02 的冷重开 `Get6` 返回 `swCustomInfoGetResult_NotPresent=1`，与该实现缺陷一致。

至少 `G1B_RECEIPT_SHA256` 已由运行时确认缺失。其余七个通过相同未检查 `Set2` 路径写入的属性也必须在修复后逐项验证，不能假定存在。

## 唯一可接受的修复路径

1. 不覆盖 `B51R1_MASTER_SKELETON_V2.SLDPRT`；从其创建新修订件 `B51R1_MASTER_SKELETON_V2_R1.SLDPRT`。
2. 对八个属性使用 `Add3(name, swCustomInfoText=30, value, swCustomPropertyReplaceValue=2)`。
3. 每次要求返回 `swCustomInfoAddResult_AddedOrChanged=0`。
4. 保存前逐项执行 `Get6(useCached=false)`，要求：result=2、WasResolved=true、LinkToProperty=false、raw/resolved 均与合同值完全一致。
5. 重新验证 21 项必需原生特征、44 项精确特征库存、3 个构型、0 实体、0 外部引用，以及所有坐标系/基准面/轴线。
6. 生成新的 S01 修订件 PASS receipt、supersession chain 与 current gate；旧文件和旧 PASS/HOLD 证据保持不变。
7. 再用独立新进程对新修订件执行 S02 的 10×3 冷重开验证。

重复运行当前 S02 不会修复缺失属性，因此禁止直接重试。

## 当前边界

```text
ledger = BLOCKED_S02_SR01_FAIL_CLOSED
consumed = 6
remaining = 14
next_session_authorized = false
SolidWorks process count = 0
H10 = 0/28
T005-A/B/C = NOT_RUN
```

下一步需要所有者一次性授权：一个 `S01_CR01` 属性修复槽，以及一个随后针对新修订件的 S02 冷重开槽。

当前不得进入 S03，也不得使用 `COMPLETE`、`MANUFACTURING_READY`、`FLIGHT_READY` 或 `LAUNCH_QUALIFIED`。
