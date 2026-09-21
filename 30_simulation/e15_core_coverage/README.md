# E1.5 P0-A 核心证据覆盖

本目录只读消费冻结提交中的 E1.5 证据快照，独立重算五态分类、唯一主阻塞和执行机构派生预算。它不修改旧 E1/E1.5、VIZ v0、共享合同、`20_engineering/cad/`、`30_simulation/` 或 `src/`。

执行：

```powershell
python 30_simulation/e15_core_coverage/src/build_core_coverage.py
python 30_simulation/e15_core_coverage/tests/run_all.py
```

关键边界：

- 不运行 ANCF；
- 不放宽阈值；
- IK 不可达后，下游物理量标为不适用，不填零、不猜测；
- P0-A 覆盖通过不等于存在安全候选，也不授权进入 E2/G3/HIL。
