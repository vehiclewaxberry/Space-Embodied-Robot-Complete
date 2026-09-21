# R5E 电气选型独立阶段评审

项目：12U 服务星与 B601；日期：2026-09-20；范围：本轮候选 BOM、45 项缺口处置、额定值与电热输入。评审者独立冷读实际 PCB、XML、原厂资料，并使用独立 Decimal 算术复算；未修改原理图或 PCB。

结论：可作为候选选型和资料更新交付，工程状态为 **CONCERN**。本文件不授予采购、制造、上电或在轨实装信用。候选原理图新增属性与原生导出 XML 已追加独立复验，2047/2047 通过，结果只限候选资料一致性。

## 第一轮：Completeness

- Status: **PASS**，限定本轮选型增量。
- 已通过 Gate 的项：未发现可据此继承的完整硬件 Gate 1–5 通过记录；不冒用仿真或历史 DRC 作为该 Gate。

## 第二轮：Risk Identification

- Status: **CONCERN**。
- 已通过 Gate 的项：本轮三板网络/value 与 249 主源独立审计通过，详见 `LOCKED_249_XML_BOARD_AUDIT.json`；这不是上电安全 Gate。
- Findings：初版 U207 TPS26600PWPR 的额定记录误写 4.5–60 V、可调限流 0.02–2 A。独立审核按 [TI TPS2660 Rev.G](https://www.ti.com/lit/ds/symlink/tps2660.pdf) p1、p7–8 指出，构建者已改成 4.2–60 V、典型可调限流 0.1–2.23 A；5.36 kΩ 时典型 2.23 A、最大 2.35 A。复验通过，F01 已关闭。剩余高风险是有效电容、R305 全角阈值、主输入板 Q201 颈缩及安装导热边界；供应与替代料为中等风险。
- Recommendation：有效容量和温度仍以待测边界处理；Q201 原有 62.9086 A/mm² 对 35 A/mm² 条件的负结果继续携带，不能被选型更新覆盖。原厂额定范围与项目设计限制分别记录。

## 第三轮：Implementability

- Status: **CONCERN**。
- 已通过 Gate 的项：15 个现有 `.kicad_sch` 与 249-ref 原生导出时的 `source_before` 哈希 15/15 一致；旧 239-ref XML 是过期导出，详见 `SCHEMATIC_SOURCE_HASH_AUDIT.json`。
- Findings：45 个处置项中 39 个尚不在三块受检实际 PCB 内。C204 的精确封装/极性/焊盘待核对；R305 候选为 665 kΩ 0805 加 11 kΩ 0603 串联，需要中间网和两个实体封装；C301 改成 1.5 µF 薄膜候选，不能以原 1 µF Value 混作已装配。
- Recommendation：候选 ECAD 的自定义属性必须与当前 Value/Footprint/连线及原有效容量要求分开。C301 保留“有效容量至少 1 µF”要求；R305 仅在实际完成 ECO 后才能新增实体采购/布局信用。候选 XML 应与主源保持 249 refs / 795 pin-net，对每一 ref 的 Value、Footprint、Pin/Net 逐项比对。

## 第四轮：Cost Reasonableness

- Status: **CONCERN**。
- 已通过 Gate 的项：无成本 Gate 可继承。
- Findings：价格、库存、交期、生命周期和已验证第二来源未闭合。当前统一 TNPW 系列有助于少量样机管理，但不能据此称成本最优。已正确保留 null 并关闭采购发布。
- Recommendation：采购前逐一核验精确订货号、数量、授权渠道、交期和可替代范围。栅极电阻若后续优化成本，需先满足脉冲能量和布线要求；无需为了本次候选更新立即换料。

## 第五轮：Validation Coverage

- Status: **CONCERN**。
- 已通过 Gate 的项：数字一致性/算术复验 65/65，结果见 `INDEPENDENT_SELECTION_CHECKS.json`，不可替代硬件验证。
- Findings：本轮没有硬件试验。独立复算已覆盖 R305 八个初始公差角、电容容差/TCC 分析及 R202 损耗；有效容量、比较器参考/偏置/回差/TCR、脉冲、安装终温及 EMC/ESD 仍未验证。候选原理图新增属性和电气语义另经 2047 项独立检查，见附录。
- Recommendation：EVT 至少核验 C301 ≥1 µF、C302 ≥10 µF、C305 ≥1 µF 的完整工况/寿命下限，核验 TPS26600 限流与锁止、R305 全角阈值和主输入链电流承载。DVT 覆盖安装热边界、瞬态与 EMC/ESD；PVT 作为将来批次、极性、追溯和可制造性检查，当前阶段不宣称已启动。未知数保持 UNKNOWN，任何放行项均需明确通过标准和实测证据。

| Area | Status | Key Finding |
|------|--------|-------------|
| Completeness | PASS | 249 行受检主源、45 项处置与候选/实现状态分账完整 |
| Risk Identification | CONCERN | U207 错误已修复；有效容量、热边界、供货风险保持 HOLD |
| Implementability | CONCERN | 39 项未进入三块已审 PCB，C204 和 R305 仍需 ECO/布局 |
| Cost Reasonableness | CONCERN | 无报价/交期/已验证第二来源，采购发布保持关闭 |
| Validation Coverage | CONCERN | 算术/范围 65/65、候选 XML 2047/2047；EVT/DVT/PVT 尚未执行 |

## 证据与边界

- `inputs/SELECTION_UPDATES.json`、`bom/ELECTRICAL_SELECTION_BOM_R5E.json` / CSV、`bom/ECAD_ECO_R5E.csv`：候选选型与实施状态。
- `results/SELECTION_CALCULATIONS.json`、`results/ELECTROTHERMAL_INPUT_UPDATE.json`：构建者结果。
- `INDEPENDENT_SELECTION_CHECKS.json`：独立复算、65 项断言、受检输入哈希。
- `SCHEMATIC_SOURCE_HASH_AUDIT.json`：15 个原理图源的导出前锁定哈希一致性。
- `CURRENT_V36_SOURCE_AUDIT.json`、`LOCKED_249_XML_BOARD_AUDIT.json`、`AUX_EMBEDDED_LIBRARY_PADS.json`：三板冷读及有限例外。
- 原厂资料核对包括 TI TPS3431/TLV6700/TPS2660、ADI MAX5048C/MAX16053、Vishay TNPW/WSLP2726、WIMA MKS2 和四张 KEMET 精确 MPN 数据表。未将典型曲线解释为全温全寿命保证。

本轮 R202 采用 0.5 mΩ 成品阻值和 ±75 ppm/K 成品 TCR；6 K/W 是元件至端子而非至环境。20 A 时 R201+R202 名义损耗 1.000 W，较旧模型增加 0.120 W。100°C 情景上界 1.01568125 W 只是在假定均匀电阻温度下的算术结果，尚未求解安装温度。

## 附录：候选原生 XML 的最终独立复验

`tools/reviewer/review_candidate_native_xml.py` 未调用构建者比较器，直接解析原 249-ref XML 和新 `results/ECAD_CANDIDATE.xml`。

- 249 个 component 的 Value、Footprint、Datasheet、描述、原非 R5E 属性、库符号、层级路径和引脚定义保持一致；795 个 pin/net（含引脚功能与类型）、197 个网络保持一致。
- 11 张图、46 个位号、278 个 R5E 属性在 `<field>` 和 `<property>` 两种 XML 投影中均与计划逐项一致，候选 MPN、封装、数据来源、开放项及状态与 BOM 对应。
- C301 原 Value 仍保留有效容量要求，同时明确候选 `1.5uF 100V +/-5%`，有效容量至少 1 µF 仍标为待验证；R305 两件串联 ECO 明确未实施。
- 原 15 张原理图及 3 块 PCB 的哈希均未变化。候选复制包含 15 张原理图；本次不导入或改写实板。
- 电气语义的规范化摘要新旧均为 `e1c7389d0e024541d4b2ca2112d9f4d740ca98f789ddcb0bfd308271ab60423d`。候选 XML SHA256 为 `6032e01959924f7b8464cfaa5bdbac47d886acead944dd755ec3ca89af3b2d4a`。
- 检查结果 **2047/2047**，零语义或候选属性错配；`ECAD_CANDIDATE_INDEPENDENT_REVIEW.json` 保留全部检查与受检文件哈希。

构建者另有 58/58 自检及负控记录，本评审仅引用其结果，不将其计作独立检查。独立算术/范围检查在最终构建者记录更新后重新运行，仍为 65/65。最终独立交付信封见 `FINAL_REVIEW.json`：候选资料包可交付，功能电路变更未应用，制造/上电/飞行仍为 HOLD。
