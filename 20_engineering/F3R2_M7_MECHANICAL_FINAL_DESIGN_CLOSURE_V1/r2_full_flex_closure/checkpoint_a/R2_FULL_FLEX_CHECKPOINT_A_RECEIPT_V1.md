# R2 Full-Flex CHECKPOINT-A 收据

## 总裁决

`CHECKPOINT-A` 已到达，但结果是 **HOLD，不是 PASS**。

- 机器裁决：`CHECKPOINT_A_REACHED__R2_FULL_FLEX_HOLD_ROM5_TRUNCATION_AND_LEGACY_R1_SCOPE__E15_NOT_INHERITED__NO_RELEASE_CREDIT`
- R2 组件 HF/ROM：17/17，`PASS_WITH_DECLARED_PROVISIONAL_PHYSICS`
- R2 耦合诊断：16/18，仅 G11、G17 失败
- Owner 状态：`PENDING_OWNER_REVIEW`；`owner_accepted=false`
- `next_stage_authorized=false`；`release_credit=false`
- Checkpoint Gate SHA-256：`FC8C9D7BEABF58D19B25CF4A238F12AC255F664F756E7950A942E7E6D3FC1C13`

## 当前磁盘前沿

当前前沿由 `CHECKPOINT_A_FRONTIER_SUPPLEMENT_V1.csv` 记录；原 `GPT_TERMINAL_HANDOVER_RECEIPT_V1.json` 和 `GPT_CURRENT_FRONTIER_MATRIX_V1.csv` 保留为检查点前快照，不覆盖。

已确认：MPI 唯一桥、Round3 组件 HF/ROM、E22 两场景三角点 coupled campaign、独立复算、五次确定性重放、ROM5 falsifier、终版红队、现行 e15/线束/Route-C/Handoff 负状态均已落盘并哈希化。

未闭合：P2 五模 1% 全场合同、Legacy R1 同口径两场景、R2 e15 再认证、任务线束覆盖、Route-C 物理能力、Handoff 12/12 和终局 Release 包。

## MPI final status

- `CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE`
- 9/9 PASS；frame/mass/inertia/consumer/hash 五个底线量均为 0
- 物理安装权威：WP11；动力学帧权威：ODR-01 `T_SM`
- 唯一桥：`T_PHYSICAL_TO_DYNAMICS = Trans(z,+0.02275 m) · Rot(z,+25.000014°)`
- 该确认只覆盖安装语义桥，不产生机械 Release credit

## Full-Flex 状态与剩余工作

- 183-DOF HF→当前 ROM5 全场最大相对误差：3.505870603% > 1%
- 792 个五维 HF 组合全部失败；最佳五维：1.082963756%
- 最小通过为 6D：0.657580852%；保留三弯曲族需 7D：0.271439113%
- P2 当前上限为每翼 5 模态，不能静默扩成 6D/7D；需要 Owner/P2 合同变更与上游 ROM 重生
- Legacy R1：22 kg 同口径证据不存在；150 kg 仅历史复现且因果口径不兼容，G17 保持 FAIL
- e15 保持 `REPEAT_ANCF_CERTIFICATION` / `NOT_INHERITED`

名义诊断：22 kg@0.5°/s 得 `omega_plus_equiv=0.160367°/s`、`Hc=0.0117823 N·m·s`；150 kg@3°/s 得 `3.042713°/s`、`3.646612 N·m·s`。两者均为 E22 provisional diagnostic，不继承 sim10 Gate。

## Harness mission coverage

- `FAIL_AT_MANDATORY_KEY_STATES`
- 10 个必需关键状态：0 SAFE / 10 UNSAFE
- 8 条任务轨迹：0 released / 8 UNKNOWN
- ODR-GPT-04 的 Route-C 延期条件不成立；Route-B 精确负结果继续冻结
- Handoff V2：11/12，G12 `HARNESS_RATED_OPERATIONAL_ENVELOPE` 失败

## Route-C physical null fields

13/13 均为 null/HOLD：`D_max_geometry_mm`, `R_path_min_mm`, `deltaL_mm`, `carrier_travel_mm`, `manufacturing_coordinates_mm`, `minimum_dynamic_bend_radius_mm`, `max_axial_extension_mm`, `torsional_compliance`, `linear_density_g_per_m`, `guide_friction_candidate`, `guide_curvature`, `carrier_size_mm`, `clamp_spacing_mm`。

现有准入评估为 2/8 PASS、6/8 FAIL；`ROUTE_C_CAD_AUTHORIZED=false`。只允许继续 RFI-E/F/G 和可追溯物理注册，不允许猜值、null→0、继承 Route-B seed 或生成 Route-C CAD。

## Agent assignments

- A0：权威、依赖图、聚合 Gate 与 Checkpoint-A 签发——完成
- A2：Full-Flex coupled campaign、独立复算与确定性 CM——完成，G11/G17 HOLD
- A5-Falsifier：792 个五维组合与最小通过维数——完成负结果
- A5-Red Team：质量/帧/张量/守恒/哈希/确定性终审——完成，无新增阻断

## Heavy-task schedule

Round3 HF/ROM、E22 campaign、确定性终版重建和五次独立重放均已按单一大型任务串行完成。当前无正在运行的 heavy solver，也未授权新的 heavy task；Route-C CAD 未启动。

## 下一自动动作

1. 冻结本 Checkpoint-A 证据，不把 HOLD 改写为 PASS。
2. 准备 P2 模态数量/验收合同决策包；未经 Owner 授权不生成 6D/7D ROM。
3. Route-C 仅继续 RFI-E/F/G 与 P01-P13 物理注册闭合；不生成 CAD。
4. 在 ROM 合同与线束物理权威闭合前，不重跑 e15、不签发 Handoff 12/12、不创建终局 Release 包。
