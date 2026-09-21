# ANCF 认证离线验收测试

结果：**9/9 PASS**

| 检查 | 结果 | 说明 |
|---|---:|---|
| `config_contract` | PASS |  |
| `low_amplitude_anchors` | PASS |  |
| `cross_solver_diagnostic` | PASS |  |
| `discretization_trends` | PASS |  |
| `historical_fail_closed` | PASS |  |
| `final_gate_fail_closed` | PASS |  |
| `frozen_input_integrity` | PASS |  |
| `manifest_hashes_and_timing` | PASS |  |
| `report_semantics` | PASS |  |

该测试只读取冻结输入和已有数值结果；不启动 ANCF 长时积分。
