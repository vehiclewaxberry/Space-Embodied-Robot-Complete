# E1.5 P0-A 核心证据覆盖审计报告

日期：2026-07-14

冻结基线：`6c15395f444f693adad6ff0dfc9a3cfc0b4cf310`

分支：`codex/core-evidence-coverage`

机器裁决：**P0_A_CORE_COVERAGE_PASS**

科学裁决：**REPEAT_CORE_NO_SAFE_CANDIDATE**

## 1. 结论

冻结 E1.5 的 72 个顶层候选已经全部得到确定、可审计的核心证据处置：

| 五态 | 数量 |
|---|---:|
| `CORE_SAFE_FLEX_VALIDATED` | 0 |
| `CORE_SAFE_FLEX_UNKNOWN` | 0 |
| `CORE_UNSAFE` | 6 |
| `GEOMETRY_INVALID` | 66 |
| `EVIDENCE_MISSING` | 0 |

P0-A 的“覆盖通过”只说明 72 行均有确定证据处置、唯一主阻塞和可重复哈希，**不表示每个几何无效候选都存在伪造的下游动力学数值，也不表示已经产生 SAFE 候选**。本结果不授权进入 E2、G3 或 HIL。

## 2. 输入与隔离边界

- 唯一候选输入是冻结提交中已提交的 E1.5 快照：`40_evidence/artifacts/visualization/e15_gate_evidence_snapshot_20260714/results__sim_09_grasp_evaluator__e15_results_72cases.csv`。
- 输入 SHA-256：`876f72274c0e0f9db8418f3df9a72298a72278459a751885793a2bce23ecee54`。
- 没有读取或修改旧集成工作树中的未提交结果。
- 所有新文件均位于 `30_simulation/e15_core_coverage/`；旧 E1/E1.5、VIZ v0、共享合同、`20_engineering/cad/`、`30_simulation/` 和原 `src/` 未改动。
- ANCF 执行数为 0；本任务不进行全量或单例柔性重算。

## 3. 为什么只有 6 行有完整数值链

固定公共服务星基座条件下，只有 P1、`t_c=0 s`、三种闭合速度与两种任务模式组成的 6 行通过 IK。其余分布为：

- P1、`t_c=30/60/90 s`：18 行 `IK_UNREACHABLE`；
- P2、全部四相位：24 行 `IK_UNREACHABLE`；
- P3、全部四相位：24 行 `IK_UNREACHABLE`。

这 66 行的结构化阶段状态为：

```text
geometry_stage_status       = FAILED_IK_UNREACHABLE
collision_stage_status      = NOT_RUN_DUE_TO_UPSTREAM_IK
base_reaction_stage_status  = NOT_RUN_DUE_TO_UPSTREAM_IK
capture_impulse_stage_status= NOT_RUN_DUE_TO_UPSTREAM_IK
post_capture_stage_status   = NOT_RUN_DUE_TO_UPSTREAM_IK
actuator_budget_stage_status= NOT_RUN_DUE_TO_UPSTREAM_IK
downstream_numeric_semantics= NOT_APPLICABLE_NOT_MISSING
```

因此下游数值列保持不可计算的空值，不填 0、不外推、不猜测。`EVIDENCE_MISSING=0` 的含义是“证据链已有确定处置”，不是“所有后续数值都存在”。

## 4. 六行数值链复核

对 6 个几何有效候选，独立复核并保留了 IK、碰撞、自由漂浮基座反作用、首次接触六维冲量、锁止冲量、目标净冲量、捕获后角速度、轮组动量、推进器冲量和冷气工质预算。

| 指标 | 6 行范围 | 门槛/语义 |
|---|---:|---|
| 碰撞裕度 | 0.05465 m | ≥ 0.02 m，均通过 |
| Jacobian 条件数 | 19.2449–27.2472 | ≤ 10000，均通过 |
| 基座姿态变化 | 1.62913–1.62936 deg | ≤ 20 deg，均通过 |
| 基座角速度指标 | 0.76670–0.76759 deg/s | 完整数值保留，当前无独立硬门槛 |
| 首次接触线冲量范数 | 0.0103263–0.0413053 N·s | 三维分量重算范数闭合 |
| 首次接触角冲量范数 | 0.000428389–0.00171411 N·m·s | 三维分量重算范数闭合 |
| 捕获后角速度 | 3.0594548–3.0594587 deg/s | ≤ 2.0 deg/s，全部失败 |
| 轮组动量需求 | 3.6776839 N·m·s | ≤ 5.475，均通过 |
| 推进器冲量需求 | 21.6334348 N·s | 由 `H/0.17` 复算，均通过派生预算 |
| 工质需求 | 36.7666070 g | 由 `1000 J/(Isp·g0)` 复算，均通过派生预算 |

6 行的唯一主阻塞均为 `POST_CAPTURE_RATE_EXCEEDS_LIMIT`。其中柔性状态 3 行已有 E1.5 合格数值、3 行为求解未知，但核心角速度门槛已经先失败，因此五态均为 `CORE_UNSAFE`，没有把柔性未知误报为核心安全。

## 5. 阈值纪律

阈值登记在 `config/threshold_registry_core_v1.yaml`，全部保持 E1/E1.5 既有值：碰撞 0.02 m、关节裕度 0.05 rad、条件数 10000、基座姿态 20 deg、捕获后角速度 2 deg/s、轮组动量 5.475 N·m·s、柔性能量 0.001 J。推进器冲量与工质上限仅由轮组动量根门槛和冻结执行机构常数推导，不作为重复主阻塞。

这些门槛仍带 `PROVISIONAL` 或任务假设限定；本任务没有通过调宽阈值制造 SAFE。

## 6. 可重复性与测试

执行命令：

```powershell
python 30_simulation/e15_core_coverage/tests/run_all.py
```

结果：`7 passed`。测试覆盖：

1. 72 行、唯一 case、五态合同和 `EVIDENCE_MISSING=0`；
2. 66 行上游失败的结构化 N/A 语义；
3. 6 行核心数值有限性、六维冲量范数闭合和执行机构推导闭合；
4. 阈值未放宽与冻结输入哈希绑定；
5. 两个临时输出目录的逐文件确定性哈希一致；
6. 构建路径无柔性求解器调用；
7. 每行确定性哈希格式与输出结构。

结果 CSV SHA-256：`e92b0f72d8db608bfed1d52fd43e1f4027ce719c233c17c4bc626dbbc2ebfb4e`。72 行哈希链：`81a78e825e5e81abb17d97d7da248e38574ddbea0b71c4918c03683960ac1c38`。

## 7. 后续门禁

P0-A 覆盖门禁已经闭合，但没有核心安全候选。下一步只能回到可行域创造问题，例如改变同步策略或经正式审批改变公共基座/任务设计；不能把这份覆盖表解释为 `CORE_READY_FOR_E2`。在产生至少一个核心安全候选并完成柔性可信性边界前，保持 `REPEAT_CORE_NO_SAFE_CANDIDATE`。
