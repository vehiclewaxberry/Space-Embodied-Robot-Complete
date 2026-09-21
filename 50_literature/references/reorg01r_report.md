# REORG-01-R 文献命名归一与链接原子改写报告

> 日期：2026-07-22
> 基线：`62f851e` / `feat/sim09-grasp-evaluator`
> 裁决：`REORG01R_COMPLETE`

## 1. 阶段 A：21 份补充论文命名现状

首页 DOI 仅按首页可提取文本层检索；“未检出”不等于 DOI 不存在，最终题录由全文身份、既有 manifest 与 Crossref 联合裁决。

| 类 | 现文件名 | 字节 | SHA-256 | 页数 | 首页提取 DOI | manifest 是否已有 DOI 对应 key | 归并后路径 |
|---|---|---:|---|---:|---|---|---|
| A | `fujii2024gripping.pdf` | 8,772,213 | `262e384edecf44c1491d750d4a6dab7ff1da54d1f39d3955839b000661ef19ed` | 14 | 未检出 | 是：fujii2024gripping | `50_literature/pdf/03_contact_capture/fujii2024gripping.pdf` |
| A | `gerstmayr2008elasticline.pdf` | 25,543,410 | `30897e9fcbb19720db68c4301a969b81243bb8651da246bf17b39dce50b2d716` | 27 | 未检出 | 是：gerstmayr2008elasticline | `50_literature/pdf/04_flexible_ancf/gerstmayr2008elasticline.pdf` |
| A | `gerstmayr2023exudyn.pdf` | 8,480,712 | `44ac028665e383f9dcd3366ad61271e548f3fe009f70f747e8bd81c4ba629d0c` | 29 | 未检出 | 是：gerstmayr2023exudyn | `50_literature/pdf/04_flexible_ancf/gerstmayr2023exudyn.pdf` |
| A | `rybus2024manipulators.pdf` | 38,799,430 | `628d70e347e74ebf56b1d0b5e263bfc1be1cc6a0be2eadcca9f319d295c7761b` | 26 | 未检出 | 是：rybus2024manipulators | `50_literature/pdf/01_survey/rybus2024manipulators.pdf` |
| A | `uyama2012compliantwrist.pdf` | 3,491,039 | `78f2719d35183ebd06afb846c3f6b52d32359d81a46a60dd124f060c83b83699` | 6 | 未检出 | 是：uyama2012compliantwrist | `50_literature/pdf/03_contact_capture/uyama2012compliantwrist.pdf` |
| A | `uyama2016hybrid.pdf` | 3,014,657 | `14cb4b4f3533ef406b1bdd474ab07f45e33ad601ad411ed66355a5369b922ec4` | 6 | 未检出 | 是：uyama2016hybrid | `50_literature/pdf/03_contact_capture/uyama2016hybrid.pdf` |
| A | `xu2017reactiontorque.pdf` | 12,586,446 | `e224c8088a11fae42611bf33ae821e0e37f40a13c1312129be701bff3ed49eeb` | 12 | 未检出 | 是：xu2017reactiontorque | `50_literature/pdf/02_gjm_rns/xu2017reactiontorque.pdf` |
| B | `aerospace-09-00406.pdf` | 2,067,512 | `03bb369b268463f0a8b23ef39f76c04e82b615f4e8de566d798b16b1a45f283a` | 17 | `10.3390/aerospace9080406` | 否 → 新增：palma2022compliantjoint | `50_literature/pdf/03_contact_capture/palma2022compliantjoint.pdf` |
| B | `applsci-12-00984.pdf` | 8,822,901 | `bf7b220aee57a410e0ad74ff25e4f575eca69959b3c3214764a4f67a88e3343e` | 18 | `10.3390/app12030984` | 否 → 新增：liu2022flexiblecapture | `50_literature/pdf/03_contact_capture/liu2022flexiblecapture.pdf` |
| B | `frobt-06-00014.pdf` | 8,676,342 | `c0aa98259a179ff889a43d9083e673f7888345ce77d1c9d24d3c8a76bcb5fa6b` | 24 | `10.3389/frobt.2019.00014` | 否 → 新增：virgilillop2019simultaneous | `50_literature/pdf/03_contact_capture/virgilillop2019simultaneous.pdf` |
| B | `frobt-08-652681.pdf` | 3,975,628 | `ee3ba06ab2a762670a5f3eceb35de7203f89503ab95419416a1aa68f70f5295d` | 19 | `10.3389/frobt.2021.652681` | 否 → 新增：mavrakis2021rocketstage | `50_literature/pdf/03_contact_capture/mavrakis2021rocketstage.pdf` |
| B | `kenneally-et-al-2020-basilisk-a-flexible-scalable-and-modular-astrodynamics-simulation-framework.pdf` | 2,241,511 | `a8fb11a942d7dc843e43b135c43c682065bea469c467b5de93ae76438f369a3d` | 12 | `10.2514/1.I010762` | 是：kenneally2020basilisk | `50_literature/pdf/07_platform/kenneally2020basilisk.pdf` |
| B | `virgili-llop-et-al-2018-a-convex-programming-based-guidance-algorithm-to-capture-a-tumbling-object-on-orbit-using-a.pdf` | 10,662,033 | `e87f37b31347a0d812faf28a4974d504d594747f84741a4af0945e12c9df8fb7` | 33 | `10.1177/0278364918804660` | 否 → 新增：virgilillop2019convexguidance | `50_literature/pdf/03_contact_capture/virgilillop2019convexguidance.pdf` |
| C | `A Detumbling Strategy for an Orbital Manipulator.pdf` | 4,196,172 | `52c2d0a0face6a9754171cf38817cefd1b1e428e7e20ef3e4b1fb8a78d98f499` | 7 | 未检出 | 否 → 新增：vijayan2022detumbling | `50_literature/pdf/03_contact_capture/vijayan2022detumbling.pdf` |
| C | `Architecture for in-space robotic assembly of a modular space telescope.pdf` | 21,439,059 | `a550600017fbbbd120c3887031f7f7e622c0b89a4a2ac14cf8fddc41229e9a77` | 16 | 未检出 | 否 → 新增：lee2016modulartelescope | `50_literature/pdf/06_on_orbit_assembly/lee2016modulartelescope.pdf` |
| C | `Dynamics  control and impedance matching for robotic capture of a non-cooperative satellite.pdf` | 1,006,233 | `204a685a44429e7218053c17b2f106f61d10a38b2e87f928b4a6f279433063c0` | 25 | `10.1163/156855304322758015` | 是：yoshida2004impedance | `50_literature/pdf/03_contact_capture/yoshida2004impedance.pdf` |
| C | `Reaction null-space control of flexible structure mounted manipulator systems.pdf` | 35,417,646 | `61e387a6ad51b521d50100431f98eed2a3d004018584068489bb011f1ee15cfb` | 13 | 未检出 | 否 → 新增：nenchev1999flexiblerns | `50_literature/pdf/02_gjm_rns/nenchev1999flexiblerns.pdf` |
| C | `Robust multi-task learning and online refinement for spacecraft pose estimation across domain gap.pdf` | 10,403,630 | `c2e9f3b00682a1ebe5b91055decb5f267cf92b7ca76bfe429b1cc713da9d274e` | 15 | 未检出 | 否 → 新增：park2024poseestimation | `50_literature/pdf/05_embodied_vla/park2024poseestimation.pdf` |
| C | `Tracking Control for the Grasping of a Tumbling Satellite With a Free-Floating Robot.pdf` | 4,314,201 | `1c9e91b39d94fdb3a74431dfdc4c270ef2c5bdd5e8bd8553750114fd5219928a` | 8 | 未检出 | 否 → 新增：lampariello2018tracking | `50_literature/pdf/03_contact_capture/lampariello2018tracking.pdf` |
| C | `Vibration suppression and zero reaction maneuvers of flexible space structure mounted manipulators.pdf` | 6,348,680 | `07098e04f42ac1849a205b69dcc5c08846c41fa1d2b926b43813cac5550f086f` | 11 | 未检出 | 否 → 新增：yoshida1999vibrationsuppression | `50_literature/pdf/02_gjm_rns/yoshida1999vibrationsuppression.pdf` |
| D | `nenchev1999impac.pdf` | 221,830 | `015b02c37fa174228372e34ea037779737130bf53c64202e06649355f63e8cfd` | 10 | 未检出 | 是：nenchev1999impact | `50_literature/pdf/02_gjm_rns/nenchev1999impact.pdf` |

分类计数：A=7，B=6，C=7，D=1。按 DOI 匹配既有 key=10；新增 key=11。D 类已从 `nenchev1999impac.pdf` 更名为 `nenchev1999impact.pdf`，SHA-256 保持 `015b02c37fa174228372e34ea037779737130bf53c64202e06649355f63e8cfd`，manifest 保留 `renamed_from` 和 `rename_reason: typo_in_source_filename`。

## 2. 新题录与 Crossref 裁决

| DOI | bibkey | Crossref | 主分类 | mission_line |
|---|---|---|---|---|
| `10.1109/ICRA46639.2022.9812067` | `vijayan2022detumbling` | VERIFIED | `contact_capture` | `debris_removal` |
| `10.3390/aerospace9080406` | `palma2022compliantjoint` | VERIFIED | `contact_capture` | `both` |
| `10.3390/app12030984` | `liu2022flexiblecapture` | VERIFIED | `contact_capture` | `debris_removal` |
| `10.1117/1.JATIS.2.4.041207` | `lee2016modulartelescope` | VERIFIED | `on_orbit_assembly` | `on_orbit_assembly` |
| `10.3389/frobt.2019.00014` | `virgilillop2019simultaneous` | VERIFIED | `contact_capture` | `debris_removal` |
| `10.3389/frobt.2021.652681` | `mavrakis2021rocketstage` | VERIFIED | `contact_capture` | `debris_removal` |
| `10.1016/j.asr.2023.03.036` | `park2024poseestimation` | VERIFIED | `embodied_vla` | `platform_common` |
| `10.1109/LRA.2018.2855799` | `lampariello2018tracking` | VERIFIED | `contact_capture` | `debris_removal` |
| `10.1088/0964-1726/8/6/312` | `yoshida1999vibrationsuppression` | VERIFIED | `gjm_rns` | `platform_common` |
| `10.1177/0278364918804660` | `virgilillop2019convexguidance` | VERIFIED | `contact_capture` | `debris_removal` |

用户列出的 10 条 DOI：VERIFIED=10，MISMATCH=0，NOT_FOUND=0。清单外但由第 21 份 PDF 必须补入的 `10.1109/70.817666`（`nenchev1999flexiblerns`）同样为 VERIFIED，因此实际新增 11 条。

`10.1088/0964-1726/8/6/312` 主分类为 `02_gjm_rns`，`cross_category: [04_flexible_ancf]`；它是 RNS 与柔性抑振之间唯一的直接桥接文献。

## 3. mission_line 汇总

| mission_line | 条目数 | 含义 |
|---|---:|---|
| `debris_removal` | 13 | 空间碎片清除独有 |
| `on_orbit_assembly` | 3 | 在轨搭建独有 |
| `both` | 9 | 直接覆盖两条任务线 |
| `platform_common` | 20 | 共用动力学、感知、柔性、具身与平台基础 |

总计 45 条；其中 44 条有本地 PDF，`gerstmayr2013ancfreview` 为唯一无本地 PDF 条目。

## 4. 链接与路径原子性

- 先建立 44 条旧路径→新路径映射，再保存 Markdown 改写，最后移动文件。
- synthesis 附录 A 的 21/21 条链接在移动后重新解析并确认目标存在。
- synthesis 之外引用 `补充论文/*.pdf` 的文件数：0。
- manifest 中保留的 `补充论文/nenchev1999impac.pdf` 仅是 `renamed_from` 审计值，不是可点击路径。
- 冻结边界内只处理任务点名的 `10_research/on_orbit_assembly/dual_mission_literature_synthesis.md`；其余冻结文件未修改。

## 5. 落盘验收

| 检查 | 结果 |
|---|---|
| `50_literature/pdf/` 实际 PDF | 44 |
| manifest `local_pdf` 条目 | 44 |
| SHA-256 逐条一致 | 44/44 |
| 页数逐条一致 | 44/44 |
| 全库字节级唯一 SHA | 44/44 |
| 命名规则 | 44/44 符合 `50_literature/pdf/NN_category/bibkey.pdf` |
| synthesis 链接 | 21/21 可解析 |
| 未匹配手工 PDF | 0 |

分类文件数：`01_survey=6`、`02_gjm_rns=6`、`03_contact_capture=11`、`04_flexible_ancf=4`、`05_embodied_vla=9`、`06_on_orbit_assembly=3`、`07_platform=2`、`08_chinese=3`。

## 6. Gerstmayr 2013 与 e15

`gerstmayr2013ancfreview` 缺失阻塞的是 e15 认证包中的“ANCF 理论依据与模型选型来源闭环”——单元族、锁死、应变度量以及 ANCF/浮动坐标法取舍的权威出处。它不直接阻止数值求解器运行，也不是当前 `REPEAT_ANCF_CERTIFICATION` 的数值原因。当前真正未闭合的数值步骤是最终候选真实幅值下的交叉求解认证：`final_candidate_cross_solver.available=false`，且历史诊断最大相对差 5.637% 高于 5% 门槛。

## 7. 最终裁决

`REORG01R_COMPLETE`
