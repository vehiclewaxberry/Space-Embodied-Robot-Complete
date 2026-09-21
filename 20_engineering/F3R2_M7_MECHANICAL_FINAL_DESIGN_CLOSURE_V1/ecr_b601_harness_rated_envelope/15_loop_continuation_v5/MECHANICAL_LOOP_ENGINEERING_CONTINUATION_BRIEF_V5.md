# 机械 Loop Engineering 续接裁决 V5

## 本轮闭合的非释放证据

- V5 Gate 的顶层 schema、12 条事实、权限与人类裁决字段、HOLD 账本、阻断前沿及最短工程顺序均已纳入 exact canonical fail-closed 校验；新增平行 authority/release/CAD/capacity 字段会被拒绝。
- V5 manifest 的 Gate/Brief 输出及 builder/validator source 记录均按运行时 path/SHA-256/bytes 精确闭合；validation 按明确 self-hash policy 排除，避免递归自引用。
- e21 已机器检测 M7 V2 与 V3_R2 账本中的 B601 臂放置上下文混用，并完成 current-R2、双翼 deployed-locked rigid、M07 arm-only 的两放置分支敏感性诊断。该差值不是统计不确定度，两个分支没有选择、平均或合并。
- fixed-base leaf-only R2 ROM 已复现；moving inter-hinge mass 冲突被记录但未选择、未传播到自由漂浮动力学。阻尼矩阵、参与因子与受迫响应仍为 `null`。
- Route-C C1.5 仅完成合成谓词资格检查和参数空间合同冻结。全部物理容量前沿字段仍为 `null`，released segments 仍为 `0`，不能解释为找到或选择了物理 Route-C 候选。

机器裁决：`MECHANICAL_LOOP_ENGINEERING_CONTINUES_WITH_CURRENT_R2_RIGID_ARM_PLACEMENT_SENSITIVITY_FIXED_BASE_ROM_AND_ROUTE_C_PRECAD_METHOD_CONTRACT_CLOSED__SINGLE_PLACEMENT_R2_FULL_FLEX_E15_HARNESS_PHYSICAL_CAPACITY_CONTACT_ATTACHED_CAD_MISSION_PRODUCTION_AND_FLIGHT_HOLD`

## 关键工程裁决

- 臂放置消费状态：`M7_R2_ARM_PLACEMENT_CONSUMPTION_SEMANTICS_EVALUATED__MIXED_CONTEXT_DETECTED__SINGLE_CONSUMPTION_RULE_UNRESOLVED`。这表示“已经评估并检测到混用”，不表示 single placement 已协调或授权。
- e21 自由漂浮结果只覆盖 current R2 deployed-locked rigid-wing + M07 arm-only；不覆盖 R2 full-flex、接触、目标附着、锁定、恢复或任务序列。
- e15 仍为 `REPEAT_ANCF_CERTIFICATION`；`R2-HRN-04=FAIL_REDESIGN_REQUIRED`。
- Route-C physical capacity、ODR-42、MPI 0/8、产品/vendor、CAD、任务、生产、硬件与飞行均保持 UNKNOWN/HOLD。

## 下一最短闭环

先由 Owner 冻结唯一的 B601 arm-placement consumption rule；随后冻结 moving-hinge mass allocation 与受控 R2 柔性参数并重过 e15。线束侧先完成 R2-HRN-04 重设计，再关闭 ODR-42 和 MPI-01..MPI-08，之后才能进入独立版本 Route-C CAD 与物理容量验证。

测试 PASS 不授予 authority。总体 `gate=HOLD`、`next_stage_authorized=false`、`release_credit=false`、`released_segments=0`。
