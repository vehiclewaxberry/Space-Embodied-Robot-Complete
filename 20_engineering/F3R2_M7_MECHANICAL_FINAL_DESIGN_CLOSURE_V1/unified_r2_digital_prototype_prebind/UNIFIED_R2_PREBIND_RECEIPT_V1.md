# Unified R2 数字样机预绑定回执 V1

- 裁决：`HOLD_PREBIND_DOCUMENT_SET_COMPLETE__ENGINEERING_SPECIFICATION_INCOMPLETE__GEOMETRY_BLOCKED_BY_REBASE_AUTHORITY_BUS_SOLAR_ROUTE_C_AND_MEMORY__RELEASE_BLOCKED_BY_FULL_FLEX_HARNESS_GRIPPER_AND_RUNTIME_JOINS`
- 文档集完成：是；工程规格完成：否；执行授权：否。
- 来源锁：25/25 文件的字节数与 SHA-256 在构建前匹配。
- 预绑定判据：5/20 PASS，15 HOLD。
- B601 URDF 独立解析：10 links / 9 joints / 10 inertials；声明质量合计 4.695555949342986 kg；本地 mesh 引用全部存在。
- 构型合同：C01–C09 共 9/9；M7 DESIGN_MODEL_R2 数值已进入预绑定账本，但未改名为 M4 released value，也未绑定到 Sim13 production loader。
- 新增显式 HOLD：需独立 Unified R2 rebase 执行授权；12U 当前仅 envelope proxy；Solar R2 根铰链不得继承 legacy R1 `F_L/F_R`；夹爪 15 m/s URDF 字面量不得推导物理/任务时序。
- 本轮生成：CAD brief、URDF ledger、重发合同、readiness、Gate、回执、哈希清单。
- 本轮未生成：FCStd、STEP、STL、GLB、URDF/Xacro、FEA、仿真或训练结果。
- 内存记录：2026-08-24 的无时刻、非权威只读采样约 1.798 GiB 可用，低于 6.0 GiB；只用于解释本轮未启动重任务，实际执行必须重测；`memory_gate_passed=false`，`owner_override_used=false`。
- 快照审查：未执行，因为本轮仅检查/预绑定且没有可见几何变更；未来几何重发必须补齐四向快照和局部干涉图。
- `owner_accepted=false`；`next_stage_authorized=false`；`release_credit=false`。
