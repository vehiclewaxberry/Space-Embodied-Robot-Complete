# R5 动力学方程与实现追溯

Run4 执行证据：`12_results/runs/R5_RUN4_ATOMIC_PACKAGE_AND_AUTHORITY_HOLD_20260827`，完成标志 SHA-256 `a55cbd43837155c553b45987c9f864d28c77ebc542b1af7a8e29c30a03f27dfa`。这是阈值授权缺失条件下的诊断证据，不是正式 Gate PASS。

| 物理量/方程 | 生产实现 | 合同 | Run4 证据 |
|---|---|---|---|
| `P^I = Σ m_i v_Gi^I` | `momentum_ledger_r5.body_momentum_contributions` + `math.fsum` 分量求和 | `R5_MOMENTUM_FRAME_CONTRACT.yaml` | 每个 episode `TIMESERIES.parquet` 的 `P_body_*` 与 `P_I_*` |
| `H_O^I = Σ(H_spin + r_OG×P_i)` | 同上；自旋/轨道分列 | 固定惯性原点 O | `H_spin_body_*`、`H_orbital_body_*`、`H_O_I_*` |
| `R_P=P-P0-∫F_ext dt-ΣJ` | `build_unit_safe_ledger` | `R5_WRENCH_AND_IMPULSE_CONTRACT.yaml` | S02/S03 metrics 与 event monitor |
| `R_H=H-H0-∫τ_ext,O dt-ΣK` | `build_unit_safe_ledger` | 同上 | S02/S03 metrics |
| 自由基座内部模态 `M_eff=Hqq-HqB HBB^-1 HBq` | `stability_analysis_r5` | 6R+2P 单位缩放 | S03 local stability artifact |
| RK4 `R(z)=1+z+z²/2+z³/6+z⁴/24` | 解析放大 + 实际 reduced step Jacobian | 三步长冻结 | 1 ms 不稳定；0.5/0.25 ms 衰减 |

文献只支撑方程族与边界；阈值、代码和 Run4 数值均为可审计工程定义。仓库内没有适用于当前 plant/场景/求解器的绝对 P/H 残差阈值 authority，因此相对指标不得作硬 Gate。
