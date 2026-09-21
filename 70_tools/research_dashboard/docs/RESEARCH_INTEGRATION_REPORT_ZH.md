# P0 研究集成裁决（2026-07-15）

## 唯一裁决

`REPEAT_CORE`

P0-A、P0-B、P0-C 已完成机器证据交叉核对，但尚无可进入后续阶段的安全候选。E2、G3、HIL 均未获授权。

## 独立 campaign，不混池

- P0-A 核心覆盖：72 行，粒度为 3 抓取点 × 4 相位 × 3 速度 × 2 任务模式；66 行为 `GEOMETRY_INVALID`，6 行为 `CORE_UNSAFE`，`EVIDENCE_MISSING=0`，SAFE=0。
- P0-C 同步捕获：216 行，粒度在 P0-A 维度上额外加入 3 个 alpha；18 行完成刚体动力学，198 行上游几何拒绝，SAFE=0。两类 campaign 仅通过 discriminator 统一浏览，不合并为同一统计总体。

## 关键科学结论

- 严格以初始线冲量和角冲量作双目标 Pareto 时，唯一非支配点为 `P1_tc00_v05mm_pose_6d_a1p0`（alpha=1.0）：0.010326315 N·s、0.000428389 N·m·s。
- 相比 alpha=0，中位初始线冲量下降 67.695%，角冲量下降 90.404%；但捕获后刚体角速度仍为 3.059454842 deg/s，高于冻结门槛 2.0 deg/s。同步策略改善“初始冲量”，没有消除最终刚体角动量约束。
- Case R（刚体主线）18/18 均被 `POST_CAPTURE_RATE_EXCEED` 约束；Case F（柔性扩展）保持 `UNKNOWN_NOT_RUN`，不得填零、不得进入安全排序。
- P0-B 的低振幅锚点完成 6/6，ANCF-modal 最大轨迹差 0.008191%；然而 10 ms 脉冲的 Radau/BDF 诊断最大差为 5.637%，且 7 个历史候选全部 UNKNOWN，最终候选交叉求解器证据不可用。因此总判定保持 `REPEAT_ANCF_CERTIFICATION`。

## 下一门禁

先重复核心研究，得到至少一个满足所有冻结刚体阈值的候选；之后才可对该候选运行 Radau/BDF 柔性认证并要求最大差异 <5%。这不是 E2、G3 或 HIL 的启动许可。

## VIZ-Gate 0 状态

v0 已按 REORG04 新根路径完成路径重冻结，当前 SHA-256 为 `83C67E63A90E23172C085577E2FB5EF01B2E31D0E812C9729D0A4BA281DE57C7`，迁移前 SHA-256 `1F66454100AFB0A66E31E042C52C6B2A570801B72217F8709A2B50CA225B3166` 保留在审计字段中。ANCF 报告中的早期 clean-checkout 可移植性注记已被提交 `e765194`、`86d50d1` 及清洁检出验证 `1cc3c2f` 覆盖；当前状态为 22/22 snapshot、29/29 freeze、45/45 assets。

## 语义合同

- `N/A`：上游门禁失败使下游不适用/未运行；不是数值 0。
- `UNKNOWN`：证据未认证；不等于 SAFE，且不得进入排序或训练。
- `EVIDENCE_MISSING`：适用证据缺失；本轮为 0，但不代表物理安全。
