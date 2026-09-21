# R5 工程与科学裁决（Run6）

工程裁决：批准 Run6 的单位安全 P/H 数值诊断、72 项全测试、静态单位审计、21 文件成功包和“积分前预开—失败留存—成功原子发布”生命周期证据入档。R5-G5 已由 HOLD 闭合为 PASS，但不批准把整个 R5 写成正式 Gate PASS。最终裁决为 `R5_REPEAT_REQUIRED__UNIT_SAFE_P_H_LEDGER_DIAGNOSTIC_EVIDENCE_PRESERVED__THRESHOLD_AUTHORITY_HOLD__VERSIONED_RUNNER_FAILURE_LIFECYCLE_PASS__NO_CONTROL_OR_CONTACT_RELEASE__PARENT_GATE_NOT_REISSUED__NEXT_STAGE_NOT_AUTHORIZED`。

Run5 保持不可变，并作为 verdict 语义负控留存：其 12/12 生命周期布尔值已经通过，但固定文本仍残留 `FAILURE_LIFECYCLE_HOLD`。Run6 将 verdict 改为由实际布尔条件组合；Run5 与 Run6 的 S02、S03 摘要文件分别逐字节一致，证明修复未改变动力学结果。

科学裁决：三个 S02 case 的 P/H、能量和投影数值诊断全部通过，但 `P_abs_max [kg·m/s]` 与 `H_abs_max [N·m·s]` 的 authority 仍缺失，正式 Gate 保持 HOLD。S03 连续约化闭环稳定；1 ms 的 RK4 放大与实际约化一步映射谱半径均约 1.6677，0.5/0.25 ms 分别约 0.99745/0.99872，最快模态为 joint6。合法结论仍为 `NUMERICAL_INSTABILITY_STRONGLY_SUPPORTED`，范围限定为 `LOCAL_TERMINAL_EQUILIBRIUM_ZERO_TOTAL_MOMENTUM_INTERNAL_SUBSPACE_UNCONSTRAINED_6R_PLUS_2P_MATHEMATICAL_PLANT`，不得外推为全局控制稳定或飞行硬件有效。

机械/物理 HOLD：当前 plant 实际为 6R+2P，两个 P 关节的无约束轨迹越下限；accepted URDF 未改。`T_E_T`、接触、目标、飞轮、推力器和柔性帆板均未进入本轮。Run6 启动时可用内存 2.690448760986328 GiB，低于 6 GiB 门；仅凭既有 Owner Override 执行，`memory_gate_passed=false`、`owner_override_used=true`，不产生任何科学 Gate 信用。

