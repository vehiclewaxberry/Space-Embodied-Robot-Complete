# A4-B1 CAD 退出验收结果

_基线：`../comp_prot_03_a4_design_review/a4_cad_acceptance_matrix.md`_

| ID | 状态 | 核验依据 |
|---|---|---|
| `A4-CAD-01` | `PASS` | 新建独立 `Space_Embodied_Robot_CAD_V1_0`；A3 原生 CAD `20/20`、自动化 `6/6` 哈希一致。 |
| `A4-CAD-02` | `PASS` | A3/SSOT/URDF/STL 来源写入原生属性与 inventory；accepted B601 输入 `11/11` 哈希一致；V1.0 内无 STEP，`vendor_STEP_used=false`。 |
| `A4-CAD-03` | `PASS` | 32 个文档均有 object ID、parent、status、representation layer；object ID 全局唯一，parent closure 通过。 |
| `A4-CAD-04` | `PASS` | `S/M/A0/G/E_virtual` 均有具名 feature/overlay；`T_SB` 与 physical TCP 保持 `UNKNOWN_DISABLED`。 |
| `A4-CAD-05` | `PASS` | 外框、纵向构件、4 道横向框环、三舱边界设备板、可拆外板和内部占位均为可识别原生组件/特征，不再是单一包络块。 |
| `A4-CAD-06` | `PASS` | 160 mm plate/boss 继承 A3 证据；加强筋/走线只标为 `DESIGN_PROPOSAL`；`MASS_CONTRIBUTION=FALSE_CAD_VISUAL_ONLY`。 |
| `A4-CAD-07` | `PASS` | 10 link / 9 joint、`6R + 1 fixed + 2 prismatic`、父子身份与 accepted URDF 一致；10 个 q=0 变换通过。 |
| `A4-CAD-08` | `PASS` | 每个 link 均登记 STL source reference、visual shell 与 physical-reserved/blocked 边界；明确 `NOT_VENDOR_EXACT`。 |
| `A4-CAD-09` | `PASS` | existing gripper 与 `E_virtual` 可见；`T_E_TCP`、physical TCP、contact geometry 均保持禁用。 |
| `A4-CAD-10` | `PASS` | `F_L/F_R` 展开参考与 `Review_Safe_Display_V1_0` 分离；安全显示明确是 proposal，不是部署真值。 |
| `A4-CAD-11` | `PASS` | 传感器为零实体语义参考；无有效硬件、选型、数值 FOV、BOM 或感知能力声明。模板默认材料/“质量 0.00”字段不具材料、质量或制造权威；禁用边界属性齐全。 |
| `A4-CAD-12` | `PASS` | active assembly 不含 target；独立场景包含 target proxy。`TARGET_INCLUDED=FALSE` 仅指未纳入 active engineering/operational assembly。场景没有组件间 mate/contact/rigid-lock；两个组件仅相对场景坐标系固定以供静态评审，这不是捕获关系。 |
| `A4-CAD-13` | `PASS_WITH_NEGATIVE_RESULT` | 仅报告 `DEPLOYED_REFERENCE_Q0`，记录 10 处静态干涉；结论固定为 `COLLISION_SAFETY_BLOCKED`，不外推。 |
| `A4-CAD-14` | `PASS` | proposal/reference/placeholder 均为视觉零质量权威；未写入冻结聚合质量、质心或惯量。 |
| `A4-CAD-15` | `PASS` | 10 类必需视图全部覆盖：12 张原生 BMP + 12 张带标题、图例、水印和 claim-limit 的 PNG；两份 manifest 均 `12/12`。 |
| `A4-CAD-16` | `PASS` | 原生属性含 evidence state、representation layer、source、mass contribution、no-dynamics、manufacturing/execution authority 等防误导字段。 |
| `A4-CAD-17` | `PASS` | 32 个原生文件重开/重建通过；247/247 检查、4 类 inventory、组件 manifest 与证据 seal 可复验。 |
| `A4-CAD-18` | `PASS` | 15/15 Gate JSON 哈希一致；`30_simulation/`、`40_evidence/`、冻结几何配置与 accepted URDF 的 tracked/staged diff 均为 0。 |

## 解释规则

`PASS_WITH_NEGATIVE_RESULT` 仍满足 A4-CAD-13 的“范围记录”要求，但它不能被改写为碰撞安全通过。A4-B1 的最终 `COMPLETE` 只适用于工程视觉与证据链，不赋予任何动力学、控制、制造、飞行或自治能力权威。
