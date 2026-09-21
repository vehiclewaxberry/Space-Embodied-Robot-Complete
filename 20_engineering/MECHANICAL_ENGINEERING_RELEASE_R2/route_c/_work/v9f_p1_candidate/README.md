# V9F FULL sweep P1 加速候选（隔离、非授权）

## 结论

本目录提供一个 **mission 姿态＋RC hardware cross-clearance 外层姿态并行**候选，不修改活跃
`ROUTE_C_EXACT_SWEEP_V9F.py`，也不改变输入几何、阈值、采样或已有输出。创建本候选时
没有启动 FULL sweep。

候选在动态逐字段对拍完成前一律是：

`NON_AUTHORITATIVE__NO_GATE_OR_RELEASE_CREDIT`

## 热点审计

基于当前任务合同和冻结采样规则：

| 阶段 | 冻结工作量 | 本轮处置 |
|---|---:|---|
| mission nominal，0.25° | 2,512 姿态 | **按段有序并行；主线程顺序回填 cache** |
| mission refinement，0.125° | 5,014 姿态 | **按段有序并行；收敛与 argmin 顺序不变** |
| mandatory key states | 10 状态 | 不并行；大多由 mission cache 复用 |
| full-range spot check，2°＋64 corners | 780 姿态 | 不并行；保留诊断顺序和 first-hit tie |
| RC hardware cross，1° | 635 原始／537 个 round-6 去重姿态 | **P1 仅并行此阶段** |

RC cross 每个姿态仍按 121 个 Route-C 部件、vendor 字段顺序、solar、bus 的原始顺序
运行。P1 只把 537 个互相独立的姿态分给线程；每个姿态内部的候选掩码、
`signed_clearance_batch`、`np.argmin`、comparison count 和严格 `<` 更新不变。

Mission 每段先由主线程按冻结 q 顺序读取已有 `eval_cache` 并构造 base；worker 通过
thread-local 获得精确 q/base，只读执行 `eval_clearance`，且在 worker 内禁止共享 cache
读写。`Executor.map` 返回后，原 `run_mission` 仍按 q 顺序执行 qmin/qmax、comparison
count、pinch、J4 指标、per-segment/worst-record 严格 `<` 归并；最后主线程按同一顺序
回填 cache。名义与加密两阶段仍串行，加密收敛定义不变。

运行时还会哈希绑定任务合同，并逐段重算 round12 key 安全性；当前 2,512/5,014 个
名义/加密姿态均为段内 **0 exact duplicate、0 distinct-key collision**。若合同变化或任一
段出现碰撞，P1 在启动 FULL 前 fail-closed。

## 为什么用有序线程，而不是 multiprocessing

- Windows `spawn` 无法安全 pickle 当前 `main()` 内的闭包和 `TriField` 图；完整重构会扩大
  科学代码变更面。
- 线程共享只读 mesh/field，避免 4 份约数百 MiB 的网格驻留和序列化。
- `Executor.map` 按输入顺序产出；父级仍以严格 `<` 归并，平局保留原顺序中的第一次命中。
- worker 异常在归并前传播，输出链 fail-closed。
- base kinematics 仍在主线程按冻结 q 顺序预计算；worker 不写 evaluator cache。

## 机械等价边界

overlay 只接受活跃源码 SHA256：

`9F26AC9A8DE5E2EEB57103F07B769EB43AC30A8FBAFD90FE8DF5D501FA8C8A7F`

并再次绑定 RC cross 原循环块 SHA256：

`5C871E440D66F8548DF9EDADF0F3C09CA5398943442D3F114488376D1FC0018D`

此外，`P1_CANDIDATE_MANIFEST.json` 从 wrapper 外部绑定 overlay 本身的 SHA；默认自测与
`--run-nonauthoritative` 实际入口都会重算并核验该 SHA。执行入口还会重新运行 synthetic
ordered-map／平局／计数／异常传播测试、resolved output isolation 和 authority 断言，历史
自测结果不能代替当次 preflight。

RC 原循环体通过机械提升生成 worker；仅将三个局部累加器重命名。Mission 只替换每段
`eval_clearance(q)` 的取值来源并隔离 worker cache 写；科学常量、0.25°/0.125°/1°
采样、round-6 去重、部件/障碍顺序、AABB、距离核和 argmin 不改。候选在执行前即把
`authoritative` 降为 `false`，输出只允许写入本目录。

## 已做的测试（不运行 sweep）

```powershell
python -B P1_RC_CROSS_THREADED_OVERLAY.py --self-test
python -B -m unittest -v test_p1_overlay.py
```

测试覆盖：外部 wrapper 哈希、源码双哈希、变换后编译、14 个科学常量 AST 等价（含 tracking tube 合成量）、关键 kernel 片段计数、
有序返回、逆序完成、mission cache hit/duplicate-q/顺序回填、严格平局 first-hit、comparison count 精确求和、worker 异常传播、
输出路径隔离和 authority 预先降级。

这些测试只能证明静态／合成等价，**不能替代 sequential P0 FULL 与 P1 FULL 的动态对拍**。

## 后续允许执行时的命令（本轮未执行）

```powershell
$env:RC_P1_ACCEPT_NONAUTHORITATIVE='YES'
$env:RC_P1_WORKERS='4'
python -B P1_RC_CROSS_THREADED_OVERLAY.py --run-nonauthoritative
```

固定候选文件存在时脚本拒绝覆盖。运行后也仍无 Gate credit。

## 动态等价验收（必须全部满足）

1. sequential P0 FULL 与 P1 FULL 输入哈希相同，且 P1 绑定上述源码／循环块哈希。
2. 去除明确的 P1 execution/authority metadata 后，所有科学 JSON 字段严格相等；不得使用
   数值容差掩盖差异。
3. ledger 科学行逐字节相等。
4. `rc_hardware_cross_clearance` 的 worst、record、evaluations 完全相等。
5. mission nominal/refined、key states、full-range、predicate、verdict 完全相等。
6. P1 以相同 worker count 连续两次回放，科学输出完全确定；任一差异即拒绝 P1。

## 预期加速与风险

- 预期（未实测）：4 线程时 mission/RC cross 并行段约 **2.0–3.2×**；FULL 总耗时保守约
  **1.8–2.8×**。
- 最大风险：NumPy/Python 混合 kernel 的 GIL 比例可能使线程加速低于预期；多线程临时数组
  会提高峰值内存；平台 BLAS 线程若未约束可能过度订阅。
- 本候选仍不并行 key states/full-range；它们保留 cache 复用、诊断顺序和 first-hit tie。
  若动态对拍发现任何 mission/cache 字段差异，应拒绝 mission 并行，不能用容差放行。
