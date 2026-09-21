# R5 S03 离散稳定性诊断

科学分类：`NUMERICAL_INSTABILITY_STRONGLY_SUPPORTED`；机制诊断：`RK4_TIME_DISCRETIZATION_MECHANISM_CONFIRMED`，限定范围为 `LOCAL_TERMINAL_EQUILIBRIUM_ZERO_TOTAL_MOMENTUM_INTERNAL_SUBSPACE_UNCONSTRAINED_6R_PLUS_2P_MATHEMATICAL_PLANT`。

连续约化闭环特征值实部范围：-3134.62466 至 -5.10459292 s⁻¹；解析/有限差分相对 Frobenius 差 4.725e-10；最快模态以 joint6 为主。

| dt (s) | RK4 最大放大 | 实际约化一步映射 ρ | 分类 | 内部 stage 裁剪 |
|---:|---:|---:|---|---|
| 0.001 | 1.66773105 | 1.66773105 | UNSTABLE | True |
| 0.0005 | 0.997450958 | 0.997450959 | DECAY | False |
| 0.00025 | 0.998724666 | 0.998724667 | DECAY | False |

六个自由漂浮中性模只分类、不作为 `rho<1` 通过条件。所谓 full velocity-state polynomial 不包含基座位姿/四元数，不能称完整实际 pose map。1 ms 的 accepted-node joint6 未越 7 N·m，裁剪发生在 RK4 内部 stage；不得改写为执行器物理饱和 99%。两个 P 关节越下限，物理控制适用性继续 HOLD。

S03 的 complete_scenario_pass=false；本结论不证明全轨迹非线性稳定、飞行控制稳定、接触稳定或硬件执行器性能，也不产生控制发布信用。
