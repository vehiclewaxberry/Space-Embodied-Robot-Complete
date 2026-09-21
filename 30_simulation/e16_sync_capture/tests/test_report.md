# P0-C 验收测试报告

日期：2026-07-14

结果：**15/15 PASS**

| 测试 | 状态 | 详情 |
| --- | --- | --- |
| T01 exact 216-case Cartesian grid and unique identifiers | PASS | - |
| T02 terminal accounting is 216=18 dynamic+198 upstream | PASS | - |
| T03 upstream rejection uses explicit N/A for every downstream quantity | PASS | - |
| T04 twist-frame/sign/unit contract is exactly satisfied | PASS | - |
| T05 all rigid dynamics invariants and contact closures pass | PASS | - |
| T06 IK/collision/conditioning/joint geometry flags and actuator evidence are explicit | PASS | - |
| T07 frozen thresholds match the inherited source without widening | PASS | - |
| T08 every dynamic case has full classification and no SAFE claim | PASS | - |
| T09 deterministic double-run digest is self-consistent | PASS | - |
| T10 alpha statistics cover six complete paired blocks | PASS | - |
| T11 Pareto/ranking tie rule makes G2-Sync a real synchronized low-impact candidate | PASS | - |
| T12 Top-20 underfill is honest and contains only 18 dynamic candidates | PASS | - |
| T13 no ANCF/flexible solver is imported or executed | PASS | - |
| T14 primary-source literature record has adopted/not-adopted boundaries | PASS | - |
| T15 evidence artifacts exist and figure export is byte-deterministic | PASS | - |

## 数值闭合最大残差

| 字段 | 最大绝对值 |
| --- | ---: |
| `terminal_twist_residual_inf` | 1.526557e-16 |
| `terminal_momentum_residual_inf` | 2.038300e-17 |
| `contact_twist_residual_inf` | 1.398187e-15 |
| `contact_P_residual_inf` | 4.163687e-17 |
| `contact_H_residual_inf` | 7.091661e-12 |
| `two_stage_P_residual_inf` | 4.163687e-17 |
| `two_stage_H_residual_inf` | 7.090994e-12 |
| `wrench_closure_inf` | 4.532152e-12 |
| `energy_closure_J` | 1.906392e-13 |

## 可重复性

- 独立运行次数：2
- 行摘要：`bd972b6908a821f0c4ade06e80b1cb066cdc13f46e9b6c50c2f23a1504eac0f0`
- 门禁：`PASS_WITH_GEOMETRY_AND_FLEX_LIMITATIONS`
