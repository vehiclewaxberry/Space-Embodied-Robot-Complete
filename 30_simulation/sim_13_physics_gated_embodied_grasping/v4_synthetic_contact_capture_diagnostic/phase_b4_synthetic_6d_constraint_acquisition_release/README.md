# Sim13 V4 Phase B4：合成 6-DOF 约束获取—释放预注册

## 工程裁决

本目录把 V4B3 已审计的双点 `hard-finger`、rank-5 瞬态候选推进到下一项可证伪问题：若未来夹爪另有一个能够补足接触弦轴扭转自由度的保持机构，理想化 6-DOF 约束在获取瞬间需要多大冲量、损失多少动能，约束激活期间能否保持动量与能量账本，解除约束时能否做到无伪冲量。

当前只冻结合同、单位与测试判据，**没有实现 B4 求解器，也没有签发接触/锁定/抓取 Gate**。该约束是一个具名 `SYNTHETIC_6DOF_RETENTION_CONSTRAINT`；它不是从 V4B3 两个点接触自然推出的，也不是实体夹爪锁定接口。

现行工程真值不变：左右物理接触坐标系、目标表面、材料对、摩擦、刚度、阻尼、允许压力、夹爪力速/时序、保持力和物理锁定变换仍为 `null/HOLD`。正式 Sim13 V2 仍为 15/20，NC15/NC16/NC18/NC19/NC20 均为 HOLD。

## 预注册核心

- 唯一合法触发是 B3 参考轨迹中“首个全部谓词与在线账本同时通过”的样本；当前冻结索引为 205、时间为 `0.051250000000000004 s`。
- 在触发时刻冻结一个仅用于诊断的快照变换 `T_PALM_TARGET_SNAPSHOT_SYNTHETIC`：它等于当时 target body frame 在 palm frame 中的相对位姿。它不得改名、复制或提升为 `T_gripper_target_locked`。
- 获取事件采用完全非弹性的质量度量投影。服务星与目标先保持为独立 20 维速度状态，再投影到 target 与 palm 快照框架零相对 twist 的 14 维附着子空间。
- 投影必须由 reduced-coordinate 与 KKT 两条独立路径对拍；线冲量 `N·s`、角冲量 `N·m·s` 分开报告，禁止把六维异量纲量直接取范数或条件数。
- V4B3 双点抓取映射保持 rank 5。新增第六个约束的弦轴纯力矩冲量必须单独报告为“合成机构需求”，不能归因给两个 hard-finger 接触点。
- 获取时关闭 B3 接触力，剩余的两侧接触弹性能不得消失，而应转入明确的 `contact_potential_absorbed_at_switch_j` 耗散账本。
- 约束激活段以后续 reduced-coordinate 附着模型传播；target 是 palm 的固定刚体子体，两个 P 指仍是独立自由度，且不再宣称由其接触保持 target。
- 解除约束只能在原始 gap 几何证明双侧分离、连续 clearance dwell 达标且全部账本闭合时发生。解除映射是速度连续的：`z_plus=z_minus`，释放冲量和理想约束储能都必须为零。
- 解除时刻固定为最小 active dwell 后“首个完整 clearance dwell 的结束时刻”；若该集合为空，只能 `DIAGNOSTIC_FAIL_CLOSED_NO_REMOVAL_EVENT`，不得改挑更有利时刻。由于触发时两个 P 指仍在闭合，本合同并不保证移除路径可达。
- 主审计支路在解除后继续关闭接触核，只记录原始 gap；任何 gap 再次变为负值都进入 fail-closed。重新启用有状态接触力模型属于未来独立 re-contact 子合同，本轮不偷渡。

## 状态机

```text
B3_SOFT_CAPTURE_TRANSIENT_CANDIDATE
  -> SYNTHETIC_CONSTRAINT_ACQUISITION_REQUEST
  -> SYNTHETIC_CONSTRAINT_ACTIVE_DIAGNOSTIC
  -> SYNTHETIC_CONSTRAINT_REMOVAL_ELIGIBLE
  -> SYNTHETIC_CONSTRAINT_REMOVED_FREE_FLIGHT_DIAGNOSTIC
```

任一触发、秩、SPD、冲量、能量、位姿、clearance、再接触或非有限量检查失败，都只能进入 `DIAGNOSTIC_FAIL_CLOSED_*`。禁止出现 `LOCKED`、`HELD_CAPTURE`、`GRASP_SUCCESS`、`TARGET_ATTACHED`、`RELEASED_ATTACHED_TARGET` 等状态或声明。

## 数值冻结锚点

数值验收值已在 `contracts/PHASE_B4_NUMERICAL_ACCEPTANCE_CONTRACT_V1.json` 中按原生单位预注册。B3 首个候选样本独立重算得到：`L_ref=0.03999999992105392 m`，左/右接触弹性能分别为 `3.3837573393085704e-7 J` 与 `4.6759575924213813e-7 J`，切换时必须一次且仅一次吸收合计 `8.059714931729952e-7 J`。

关键数值门包括：SVD 相对秩阈值 `1e-10`、仅允许报告尺度化 `W_bar` 的条件数且上限 `1e10`、正 clearance 下限 `1e-6 m`、再入闭合速度容差 `1e-6 m/s`、跨积分器获取/移除事件时差 `2.5e-4 s`。这些都是 synthetic solver 的数值验收门，不是机械公差、实体间隙、锁定时序或硬件资格指标。

合同冻结阶段固定 62 项 pytest、12 项真实 in-memory 合同 mutation；未来求解器另预注册 22 项负控，当前未执行、不得报 PASS。

## 当前状态

`CONTRACT_FROZEN_FOR_VALIDATION__FINAL_CREDIT_REQUIRES_INDEPENDENT_AUDIT__NO_IMPLEMENTATION`

合同冻结验证与独立审计完成前，本目录不能升级为 `CONTRACT_FROZEN`。即使未来合同 Gate 通过，它也只代表预注册完整，不代表求解器、物理机构或当前系统通过。
