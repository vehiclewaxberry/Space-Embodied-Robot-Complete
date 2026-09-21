# R5 版本化运行器与来源追溯报告（Run6）

Run6 位于 `12_results/runs/R5_RUN6_LIFECYCLE_CLOSED_THRESHOLD_AUTHORITY_HOLD_20260827`，`RUN_COMPLETE.json` SHA-256 为 `f301f4e6a313a3c638f4874b9a649362c0ea49c94d00f836d6eb5e7bbb62f72d`。运行包含 12 个 batch episode 和 12 个 canonical 包；每包具有任务书规定的 18 项必需文件、`HASH_MANIFEST.csv`、兼容控制遥测和事件监视状态，共 21 文件。297 个 Run6 输出、全部包内哈希与 lifecycle contract 后验重算均为 0 个失败。

每个 episode 在数值积分前于最终 canonical 父目录预开同卷临时目录，并记录 `CREATED`、`PREEXEC_PASS`、`RUNNING`。成功路径完成精确 schema 检查后删除 `INCOMPLETE_RUN_MARKER.json`，再以 `os.replace` 原子发布；成功 manifest 绑定 `preopened_before_integration=true` 与发布方法。合成积分异常负控则原子保留失败目录，包含不完整标记、失败 manifest、异常类型、traceback 与 `success_credit=false`。因此 R5-G5 的成功发布与失败生命周期均为 PASS。

每个 episode 绑定 plant physics、生成 plant artifact、controller、Gate、scenario、source tree、source snapshot、authority、environment、seed、initial state、solver execution、preintegration scale 和 resolved episode config 哈希。Run6 执行前 72/72 测试通过，单位审计对两个生产动力学文件均为 0 findings。运行时 `OMP/OPENBLAS/MKL/NUMEXPR` 线程数均限制为 1，并写入环境证据。

Run5 因固定 verdict 字符串残留旧 lifecycle HOLD 而作为不可变负控保留；其实际 lifecycle 布尔值为 true。Run6 使用条件驱动的 verdict 组合，且 Run5/Run6 的 S02 与 S03 摘要逐字节一致。Run6 不追溯升级任何 Run1–Run5 历史证据，也不改父 Gate。

