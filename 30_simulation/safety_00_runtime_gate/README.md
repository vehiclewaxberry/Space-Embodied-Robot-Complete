# SAFE-00 Runtime Safety Gate

SAFE-00 是只读消费既有仿真证据的 fail-closed 运行时裁决模块。它不控制机械臂、
不生成轨迹，也不修改 sim_01～sim_12 或冻结阈值 registry。

## 复现

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python 30_simulation/safety_00_runtime_gate/tests/run_all.py
python 30_simulation/safety_00_runtime_gate/src/run_gates.py
python 30_simulation/safety_00_runtime_gate/src/run_diagnostics.py
```

- `run_gates.py` 只输出决定性 Gate 字段；重复运行结果逐位一致。
- `run_diagnostics.py` 单独记录非 Gate 延迟，结果明确排除在冻结证据哈希之外。
- 测试和 Gate 使用公开的 `TEST_VECTOR_SAFE00_V1` HMAC 测试向量。它不是生产密钥。
- 生产调用必须向 `decide(...)` 显式注入至少 32 bytes 的 HMAC-SHA256 密钥与
  key ID；缺失、为空或过短时，
  原本可能执行的 `ALLOW/MODIFY` 会降为 `UNKNOWN/ABORT`。

## 名义候选绑定

`A_low-S1_passive` 的 `CAPTURE` 请求被逐调用绑定到：

- `strategy_results.csv` 的唯一键 `A_low|S1_passive`；
- `strategies_v0.yaml` 的 `cases.A_low`；
- `scan_v0.yaml` 的 24 kg 质量比参考。

因此名义输入使用捕获前角速度 `0.5 deg/s`、`G2_cubesat` 和
`mu=22/24`。CSV 行、案例配置、行引用、candidate ID 或派生状态任一失配都 ABORT。
sim_11 仅作为白名单中的 `GLOBAL_GATE_NON_SCENARIO` 全局证据，不冒充候选场景行。

机器裁决见
`30_simulation/safety_00_runtime_gate/results/safety_00_gate_check.json`。LOOP-6 修复后的独立复审
尚未完成，因此始终保持 `review_status=PENDING_REVIEW` 与
`next_stage_authorized=false`。
