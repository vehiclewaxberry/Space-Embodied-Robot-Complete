# CTRL-02 当前状态（CTRL-02-R 整改轮）

- 基线提交：`926522f199cae3b9d88ee6797089d57300fea994`
- 所有权：仅 `30_simulation/control_02_base_attitude/**` 与 `20_engineering/config/attitude_stab/**`
- 首轮 LOOP-0…7：完成，机器裁决 `REPEAT`（GC1 两项独立原因：预注册 M2 零起点
  限位裕度 0.0 < 0.05 rad；A1 未完成任务终点 584.7/322.0 mm 终点劣化）。
  历史见 git 631f2e3 之前的提交与 `evidence_manifest_pre_review.json` 中的
  `post_result_scene_edit_audit`。
- CTRL-02-R（本轮，预注册 R-4/R-5，CP3 已批准，阈值全部冻结）：
  - LOOP-R1（R-4 Stage-A 重设计）：完成。M2 预注册内点起点
    `[0,-15,-15,0,0,0]°`（先验规则：每关节距活动限位 ≥0.25 rad；min-jerk 单调
    ⇒ 全程裕度 = 端点最小值 0.2618 rad）；**已撤回的 −5° 看结果后探针未复用**。
    A1 重设计为两段式（4.8 s 反作用投影 + 匹配速率五次收口，8 s 精确落注册
    终点）；A0–A2 全部重跑。M1 锚不动，A0@M1 = 19.199852° 与 sim_05 直算锚
    逐位一致（diff = 0.0）。
  - LOOP-R2（R-5 执行器动态）：完成。`attitude_stab_v0.yaml` 冻结 PROVISIONAL
    轮最大力矩 0.01 N·m/轴、最小推力脉宽 20 ms、时间窗稳定判据
    （300 s 窗、60 s 保持、0.05 °/s，出处级注释齐备）；新增
    `src/transient_b.py` 按脉冲对齐定网格执行 L0 动量计划，16 行瞬态裁决：
    7 稳（A_low B1/B2/B3、C B2/B3、B_anchor B2/B3 反事实）/ 9 不稳
    （全部 B0、C/B_anchor/D 的 B1、D 的 B2/B3——D 因冻结外部容量枯竭且
    322 s 完成时间超窗）。终端与 L0 一致性 ≤ 脉冲量子 3.4e-4 N·m·s，代数预测
    与推进逐行一致，瞬态推进剂经独立下界审计零差。
  - LOOP-R3（守恒/归属/下界沿用重跑）：GC0 三标签归属机器判定纪律不变并扩展
    覆盖瞬态行；Stage-A 广义动量残差 5.6e-17，捕获 eps_H 3.85e-16，外账闭合 0。
  - 机器 Gate：`control02-gate-v3`，GC0–GC7 **全 PASS**，总裁决 **PASS**；
    tests 24/24。诚实负结果保留：M2 上 A1 峰值 9.24° > A0 8.73°（两段式收口
    偿还超过投影节省）；M1 上 A1 18.84° < A0 19.20°。
- `REPEAT`→`PASS` 的全部变化来自预注册修订授权范围（轨迹重设计 + PROVISIONAL
  执行器层新增），没有任何阈值放宽（`thresholds_widened=false`、
  `repeat_revision.thresholds_changed=false` 双机器断言）。
- A3 仍 `NOT_APPLICABLE_WITH_MISSING_FROZEN_ACTUATOR_DYNAMICS`；R-5 的
  PROVISIONAL 值只授权 Stage-B 瞬态层。
- 独立红队复审未完成：`review_status=PENDING_REVIEW`，本任务不自行关闭审查；
  停在本分支，不合并、不进集成，等 integrator-R 单跑与 PI 终裁。
- 待办（硬件冻结后必须重跑瞬态层）：轮最大力矩、推力器最小脉宽实测值替换
  PROVISIONAL 占位；0.05 °/s 稳定阈值与量子残差下界（最轻组合体 ~0.049 °/s
  量级）同步复核。
