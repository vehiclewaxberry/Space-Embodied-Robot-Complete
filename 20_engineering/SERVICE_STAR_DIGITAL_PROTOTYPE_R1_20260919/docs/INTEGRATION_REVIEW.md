# 独立集成审查

当前可以接受为**三态固定姿态数字集成候选的构建计划**；不能宣称电气、热控、推进已经完整闭合。本审查未运行 CAD 或 SolidWorks，仅核对文件、来源哈希、ID、变换、材料分类和信用边界。独立审查的三份文件不是本审阅者编写；既有材料参考和增量几何清单是本审阅者前序产物，仅用作明确标识的支持输入。

核对每态：873 − 18（WP10移除）＋119（WP10新增）＋136（R17新增）＝1110 个唯一实例。分解为804保留、119 WP10新增、20 WP10直接替换、136 R17新增、22 R17直接替换、9合并替换；预计1513个实体。service/parking/released均无ID遗漏、误加、重复或来源/变换不一致，18个移除项均未残留。

9项合并按回执的 `host_id` 落到实际宿主；其中 `lower_equipment_deck` / `upper_equipment_deck` 分别映射到 `_B` 宿主件，不能按原始id误判为11项。9项输出哈希、9项回执的残余体积判据及不继承工程接受的标识一致；本轮没有独立重跑布尔或干涉。

747条装配实际引用的STEP路径现哈希匹配。材料清单→ALL_IMPORT_PLAN→INCREMENT_IMPORT_PLAN/INTERFACE_MERGE来源链匹配。材料清单覆盖231个增量与合并资源，其中138个赋予候选材料、93个保持null；不是全机1110实例的材料完备率。未发现PCBA、线束等混合物/纯包络误赋bulk材料，未发现未知质量零填或保留件原质量被改写。87项304赋值属于明确的新地面候选，不能当作实物材证或A2-70强度认证。

## 第一轮：Completeness

- Status: **FAIL**（针对“全系统完整设计”主张）
- 已通过 Gate 的项：未见覆盖全系统完备性的Gate 1–5，不重复声称旧局部Gate。
- Findings: 当前完整V36三板尚未装入，CF1冲突热模块仍排除，OEM推进选型未冻结。
- Recommendation: 以“固定姿态集成候选”发布；分别完成板卡回装、热路重布置和受控推进ICD/选型。

## 第二轮：Risk Identification

- Status: **CONCERN**
- 已通过 Gate 的项：已有来源/形体证据按其原范围保留。
- Findings: 保守孔合并可能保留旧孔/开口，R01封闭承压边/旧孔移除结论不继承；新304材料不提供紧固等级、预紧或防咬合证据；LPS300源解析诊断仍须保留。
- Recommendation: 对新合并件重查承压边、边距、配对紧固件和工具空间，原生读回保留源诊断。

## 第三轮：Implementability

- Status: **CONCERN**
- 已通过 Gate 的项：本轮三态ID、来源和变换账核对通过。
- Findings: 三态属于固定姿态，motion_mates=false；计划文件不能独立证明SW冷打开、引用无缺失、重建成功及完整装配无干涉。
- Recommendation: 由CAD执行链提供逐态冷读回、实体数/包围盒/体积、原生材料及引用检查；连续运动另验。

## 第四轮：Cost Reasonableness

- Status: **CONCERN**
- 已通过 Gate 的项：没有本范围内的询价/采购成本Gate。
- Findings: 候选材料与实例账未形成完整图号/订货码、数量聚合、库存和报价。
- Recommendation: 接口收敛后形成加工/采购BOM，用实际可购材料和器件校核成本。

## 第五轮：Validation Coverage

- Status: **CONCERN**
- 已通过 Gate 的项：9件有效性/布尔残余记录只按原范围引用，没有重复运行或继承整机接受。
- Findings: 整体装配适配、上电、飞行和全材料字段均未通过；停止/回生、整机散热和主动推进不在本次证明范围。
- Recommendation: 分立原生交付、材料溯源、整机适配、电气、热控和推进验证记录；构型改变后，相关研究结论须经重新验证。

| Area | Status | Key Finding |
|---|---|---|
| Completeness | FAIL | V36完整板卡、CF1热模块和推进冻结尚缺 |
| Risk Identification | CONCERN | 保守孔合并不继承R01承压边接受 |
| Implementability | CONCERN | 固定姿态计划需独立原生CAD读回 |
| Cost Reasonableness | CONCERN | 未形成可直接采购的统一BOM及报价 |
| Validation Coverage | CONCERN | 上电、全热路、真实推进与飞行尚未验收 |

审查结果与源文件哈希见 [INDEPENDENT_INTEGRATION_REVIEW.json](../results/INDEPENDENT_INTEGRATION_REVIEW.json)。本结论允许有界布局、接口和质量敏感性研究；不构成全系统详细设计、上电或飞行放行。
