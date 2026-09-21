# S02_SR01 根因范围更正

本文件以追加方式更正初始失败事件中的属性影响范围，原事件保持不变。

冷重开验证器在检查 `G1B_RECEIPT_SHA256` 前，已经让 `FRAME_ID`、`BUILD_STRATEGY`、`G07_G08_CONTACT_WINDOW_STATUS` 通过 `Get6(false)=2` 和精确值检查。上游 NativeBuilder 也确实使用 `Add3` 创建了这三个属性。

因此需要新增的最小属性集合为：

```text
G1B_RECEIPT_SHA256
FINAL_INPUT_LOCK_SHA256
PANEL_PRIMARY_LOAD_CREDIT
PANEL_ATTACHMENT_CREDIT
PANEL_PHYSICAL_CONTACT_CREDIT
```

这五个属性在 Finalizer 中首次出现时均只调用了未检查返回值的 `Set2`；没有上游 `Add3` 创建。`G1B_RECEIPT_SHA256` 已由运行时 `Get6 result=1 / NotPresent` 直接确认缺失，其余四个由同一连续实现路径确认需要修复。

修复应仅在新修订件 `B51R1_MASTER_SKELETON_V2_R1.SLDPRT` 中使用 `Add3` 创建这五个属性，并对全部文档属性执行 `Get6(false)` 精确读回。不得覆盖当前 V2 文件。
