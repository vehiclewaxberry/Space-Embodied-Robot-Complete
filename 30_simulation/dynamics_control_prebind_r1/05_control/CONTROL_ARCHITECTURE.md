# Control Architecture (Prebind Only)

数据流冻结为：RPO/导航状态 -> state handoff schema -> plant/frame/hash validator ->
SAFE-00 fail-closed decision -> future control allocator -> independent physics veto ->
backend adapter。当前只实现 validator 合同与零广义力 PB-00；future control allocator
保持 `HOLD`。

控制相位与机械拓扑分离：`PREGRASP` 不是 `COMPLIANT_CAPTURE`，后者也不是
`LOCKED_COMPOSITE`。任何 hash drift、单位/坐标歧义、UNKNOWN 或 authority 缺失均
直接进入 WAIT/BACKOFF/ABORT，不执行控制性能评分。
