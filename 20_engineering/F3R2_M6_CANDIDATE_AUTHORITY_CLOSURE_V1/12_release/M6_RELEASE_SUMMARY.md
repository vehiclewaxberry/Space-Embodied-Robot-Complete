# M6 候选权威闭合发布摘要

生成:2026-08-21T21:18:54.341632+08:00(本地,+08:00)。

## 工程裁决

本轮在 M4(数字样机受限发布)、M5(几何与载荷闭合)、SIM15(诊断复核)之后,
把 M4 授权待办中**无需硬件/人审/外部 ICD** 的部分推进到候选/诊断级闭合。
这不是制造、结构、资格或飞行发布;正式 FEA 运行数为 0;所有物理权威 HOLD 原样保留。

## 七工作包结果

| WP | 令牌 | 状态 | 关键数值 |
|---|---|---|---|
| WP1 载荷桥 | M6_LOAD_BRIDGE_CANDIDATE_ISSUED | CANDIDATE | 160×160×10.75 mm 桥板跨 x 185.25–196.0;4×⌀6.6 @ (±70,±70);体积 260072.3919 mm³;候选质量 702.195458 g(MATERIAL_DERIVED,6061-T6 2700 kg/m³);21/21 检查 PASS |
| WP2 九构型质量 | M6_NINE_CONFIG_DIAGNOSTIC_MASS_ISSUED | DIAGNOSTIC | C01–C09 诊断聚合;Branch A 28.695555949 kg / Branch B 29.081436765 kg;与 M4 台账回归误差 ≤2.84e-14 kg;stage1 整星行复建误差 ≤4.2e-08;release 字段全 null |
| WP3 公差链 | M6_TOLERANCE_NUMERIC_CANDIDATES_ISSUED | CANDIDATE | B601-M3R 链 WC 最小径向间隙 0.1010 mm;Stage A↔B 止口 WC 0.206 mm;夹爪 4 档间隙 × 144 点 576/576 PASS_NEUTRAL(最小裕度 0.05 mm);铰链翼尖灵敏度 0.2 mm/mrad |
| WP4 材料库 | M6_MATERIAL_LIBRARY_V2_CANDIDATES_ISSUED | CANDIDATE | 7 条材料记录(V1 四条逐字保留 + A286/300 系 CRES/8552 预浸料);3 组采购规范候选、3 条表面/润滑工艺候选;22 条公开来源;规范选定 0、许用值 0 |
| WP5 结构入口 | M6_STRUCTURAL_ENTRY_EVIDENCE_PACK_ISSUED | DRAFT_PRE_AUTHORITY | FEA1/2/3 计划 + 4×HM4-75 螺栓组 6 单位载荷×4 钉解析(24 行,与 M5 系数一致);8 子门保持 HOLD;无 MoS 声称 |
| WP6 图纸/BOM | M6_BOM_V2_CANDIDATE_ISSUED | CANDIDATE | BOM V2 15 行(V1 13 行逐字保留 + DP-012 紧固件组 + DP-013 定位销);站位表 V2 补全 x 站位语义;D04 登记 CANDIDATE_PENDING(集成时已验证存在) |
| WP7 CDR 证据 | M6_CDR_READINESS_PACKS_ISSUED | PENDING_OWNER_REVIEW | Q0 条款映射骨架(14 标准全缺受控副本);Q1 19 项载荷缺口逐项闭合路径分类;Q2 ROOT_TO_M 五选项(未选定)+ 0/9 解除条件树 |

## 集成事实

- 输出清单:`M6_OUTPUT_MANIFEST_V1.json`(48 文件,610484 B)。
- 跨 WP 引用和解:`M6_CROSS_WP_REFERENCE_RECONCILIATION_V1.json`(8 验证 / 0 缺失);WP 文件与 receipt 未被改写。
- 基线完整性:M4/M5/CDR/SIM15 及 L0 URDF 全部只读;12 项门禁钉住哈希经独立复核 0 漂移。
- 独立验证:`M6_VALIDATION_RECEIPT_V1.json` 13/13 PASS(清单哈希、receipt 完整性、基线钉、跨 WP 引用、门禁语义、七个 WP 结构抽查、无 FEA 产物)。
- 内存门:6 GiB 仍未过;全程仅 WP1 使用单进程 FreeCAD(Owner Override,与 M4-OVR-001 同源)。

## 保留 HOLD(摘要)

载荷桥物理接口权威、旧法兰所有权、ROOT_TO_M、舱侧锚固图案、M3R 组件 COM/惯量、
九构型发布质量/质心/惯量(0/9)、可追溯不确定度、实测质量(需硬件)、材料规范/许用值/
工艺/环境选定、公差实测符合性、紧固件物理参数、结构入口全部子门、CDR Q0/Q1/Q2、
发射/分离 ICD、接触/柔体生产动力学与 RL、制造/发射/资格/飞行。完整清单见 gate JSON。

## 下一闭环(M7)

1. Owner 审查本轮候选包(WP1–WP7)并裁决 ROOT_TO_M 与失效保留/抛离语义;
2. 实测质量—质心—惯量活动(需硬件与不确定度模型);
3. 受控标准副本与发射/分离 ICD 获取(外部);
4. 有界诊断仿真研究可继续(SIM15 后继不得声称生产动力学)。
