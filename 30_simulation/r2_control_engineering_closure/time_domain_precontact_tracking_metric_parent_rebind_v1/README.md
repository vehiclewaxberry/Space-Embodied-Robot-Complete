# Time-Domain Diagnostic Metric Parent-HOLD Rebind V1

本包只处理一个证据链问题：任务空间度量候选原合同固定的 `CTRL_R2_PRECONTACT_TRACKING_GATE_V1.json` 与当前文件相差 2 bytes/SHA。当前文件仍是明确的 HOLD，并且不参与任务度量的数值计算。

处置方式是 append-only：不修改历史合同、父 Gate 或 19/20 时域候选；在内存副本中只替换该同名 pin 的 bytes/SHA，然后用固定的 task-metric source 完整重算 17 项。重算任务数据与归档数据只允许 1e-15 绝对数值舍入差，结构与非数值字段必须精确相同。

本包 Gate PASS 时最高只表示：

```text
TIME_DOMAIN_DIAGNOSTIC_TRANSITIVE_PARENT_HOLD_REBIND_PASS
```

原时域 Gate 仍保留 19/20、`gate_passed=false`；本包不重发任何父 Gate，不验证控制、硬件、碰撞、接触、SAFE、非 ABORT、下一阶段或发布。

复现：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B build_metric_parent_rebind.py
python -B -m pytest -q -p no:cacheprovider tests
```
