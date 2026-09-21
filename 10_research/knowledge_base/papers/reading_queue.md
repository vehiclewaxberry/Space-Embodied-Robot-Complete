# 论文阅读总控队列

> 状态：`DERIVED_NAVIGATION_ONLY`。本文件由 `paper_knowledge.py build` 从 manifest、在盘 PDF 和 canonical 阅读卡机械生成；不得反向覆盖真值源。

## 当前快照

- manifest 题录：**45**
- 完整阅读卡：**34**
- PDF 在盘且待精读：**10**
- 缺全文或本地文件异常：**1**
- manifest 快照日期：`2026-07-22`

## 选篇规则

1. 先由当前研究问题选择类别和 mission_line，再比较 manifest 的 priority；不要把列表首项当成永久唯一优先项。
2. 同一 priority 保持 manifest 原始顺序，不额外制造科学排序。
3. 精读前对拍本地 PDF SHA-256；完成后按 canonical 模板落阅读卡并重新生成本文件。
4. `why` 是 manifest 中的阅读动机，不是论文已经成立的结论。

## 可立即精读

### P0（5 篇）

| manifest序号 | bibkey | 层级/类别 | mission_line | manifest 阅读动机 | PDF |
|---:|---|---|---|---|---|
| 1 | `rybus2024manipulators` | V0/survey | `both` | 臂本体自由度、臂长、质量与末端执行器横向选型的首要表格来源。 | `50_literature/pdf/01_survey/rybus2024manipulators.pdf` |
| 9 | `xu2017reactiontorque` | V1/gjm_rns | `platform_common` | 连接反作用力矩零空间与 RNS，并把基座反作用纳入轨迹优化。 | `50_literature/pdf/02_gjm_rns/xu2017reactiontorque.pdf` |
| 16 | `gerstmayr2008elasticline` | V3/flexible_ancf | `platform_common` | 约束 ANCF 梁弯曲与轴向变形的正确解耦，避免伪柔性结果。 | `50_literature/pdf/04_flexible_ancf/gerstmayr2008elasticline.pdf` |
| 35 | `vijayan2022detumbling` | V2/contact_capture | `debris_removal` | 把抓持后的组合体状态重构、角速度衰减与模式切换落成可审计的消旋状态机。 | `50_literature/pdf/03_contact_capture/vijayan2022detumbling.pdf` |
| 36 | `palma2022compliantjoint` | V2/contact_capture | `both` | 提供选择性柔顺移动副与阻抗控制的自由漂浮验证，可共同服务捕获和柔顺装配。 | `50_literature/pdf/03_contact_capture/palma2022compliantjoint.pdf` |

### P1（5 篇）

| manifest序号 | bibkey | 层级/类别 | mission_line | manifest 阅读动机 | PDF |
|---:|---|---|---|---|---|
| 13 | `uyama2016hybrid` | V2/contact_capture | `debris_removal` | 回答捕获后的消旋与位置保持如何切换。 | `50_literature/pdf/03_contact_capture/uyama2016hybrid.pdf` |
| 14 | `fujii2024gripping` | V2/contact_capture | `both` | 为夹爪、包络与柔性抓取方案选型提供横向证据。 | `50_literature/pdf/03_contact_capture/fujii2024gripping.pdf` |
| 17 | `gerstmayr2023exudyn` | V3/flexible_ancf | `platform_common` | 对应 EXUDYN 实现，用于 ANCF 梁、模态与积分器选择。 | `50_literature/pdf/04_flexible_ancf/gerstmayr2023exudyn.pdf` |
| 40 | `mavrakis2021rocketstage` | V2/contact_capture | `debris_removal` | 提供废弃上面级抓持稳定性与实验结果，约束 ADR-GRASP 的抓点和末端方案。 | `50_literature/pdf/03_contact_capture/mavrakis2021rocketstage.pdf` |
| 41 | `park2024poseestimation` | embodied_vla/embodied_vla | `platform_common` | 覆盖合成到真实的位姿域差、在线修正与不确定度，是两类任务共用的感知校准证据。 | `50_literature/pdf/05_embodied_vla/park2024poseestimation.pdf` |

## 阻塞项

| bibkey | 状态 | DOI 状态 | 下一步 |
|---|---|---|---|
| `gerstmayr2013ancfreview` | `BLOCKED_NO_LOCAL_PDF` | `VERIFIED` | `ACQUIRE_FULLTEXT_UNDER_SOURCE_POLICY` |

## 总控调用

- 状态核验：`$paper-knowledge-orchestrator` + `STATE_AUDIT`
- 指定精读：`$paper-knowledge-orchestrator` + bibkey + 当前研究问题
- 横向综合：`$paper-knowledge-orchestrator` + bibkey 集合 + 明确的 synthesis question
