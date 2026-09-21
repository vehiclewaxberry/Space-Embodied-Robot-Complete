# 机械终局决策包 V1 收据

生成时间：2026-08-24T02:43:50+08:00

## 裁决

- 决策包完整性：13/13 PASS。
- Checkpoint A：HOLD（6/12；E22 16/18，G11/G17 失败；e15=REPEAT_ANCF_CERTIFICATION）。
- Checkpoint B：HOLD（完整性 8/8；C2 准入 2/8；P01–P13 为 0/13 非空；Route-C CAD 禁止）。
- Checkpoint C：未到达，未生成机械终局 Release 候选。

## 两项待 Owner 独立落字的内部决策

1. ODR-GPT-07：推荐 A_11D_FIVE_REGISTERED_WINDOWS_CANDIDATE。该 11D 基底只证明名义诊断输入在 5/10/20/50/100 ms 五个离散注册窗满足当前 1% 六指标分数，最坏 0.742604%@5 ms；不证明连续 5–100 ms 区间，也不预授 E22/e15 PASS。
2. ODR-GPT-08：推荐 A_FOUR_LANE_PROTOCOL_MATCHED_COMPARATOR。R1 与 R2 各自只在族内做刚/柔因果配对；跨族只能报告设计族差异。

## 外部物理输入

当前冻结 Route-B 的 ODR-GPT-04 额定任务包络分支已被机器证伪：当前注册证据为 10 个强制状态 0/10 SAFE、8 条轨迹 0/8 released、Mission Coverage FAIL，同时 Route-B 终局冻结明确 `reopening=NONE_PERMITTED`。该结论不泛化为所有外置线束拓扑物理不可能，也不声称所有 q 均 UNSAFE；圆角裁剪的全域不变量尚未建立。它终止的是当前冻结 Route-B 的合法发布分支。当前闭环必须补齐 Route-C P01–P13 的可追溯物理数据、单位、不确定度及 authority class，达到 Checkpoint-B 8/8 后另取 CAD 授权，再完成新物理路线与全程任务覆盖。任何 null、扫描轴或 LLM 估计均不得转为 CAD 权威。

## 不变声明

M4 的受限数字样机发布继续有效且不重做；当前工作只处理 R2 终局增量。Owner acceptance、next_stage_authorized、release_credit 均为 false。
