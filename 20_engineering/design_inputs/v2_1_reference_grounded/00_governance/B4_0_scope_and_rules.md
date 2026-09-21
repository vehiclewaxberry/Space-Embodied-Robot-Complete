# B4-0 范围与规则（公开来源准入与方案冻结）

> `GATE: COMP-PROT-03-A4-B4-REFERENCE-GROUNDED-STRUCTURE-AND-SOLAR-REFINEMENT`
> `PHASE: B4-0`
> `SOLIDWORKS_CONTACT: FORBIDDEN`（本阶段不创建/不修改任何 CAD）
> `V2_0_BASELINE: FROZEN`（`Space_Embodied_Robot_CAD_V2_0/` 及其证据链全不变）
> 授权来源：用户 2026-07-25 会话指令（V2.1 Reference-Grounded Mechanical Refinement 方案）

## 允许

- 只读核验白名单公开资源；保存 commit / license / hash / 状态自述；
- 建立 feature-adoption matrix（逐特征登记 FEATURE_ID/SOURCE/COMMIT/LICENSE/
  BORROWED_PRINCIPLE/PROJECT_DIMENSION_OWNER/ADAPTATION_RULE/NO_DIRECT_SCALE=TRUE/
  EVIDENCE_STATE/CLAIM_LIMIT）；
- 冻结主结构与太阳翼根部候选方案（trade study 级）；
- 多代理对抗设计轮（冲突保留，不多数票覆盖硬阻塞）。

## 禁止

- 等比例放大任何外部 CubeSat（Reference Morphing, not Uniform Scaling）；
- 把外部 CAD 当 canonical 模型或继承其质量/惯量/板厚/弹簧参数等数值；
- 混入 366mm CDS_12U_REFERENCE 包络（保持 COMPETITION_DISPLAY_V0
  340.5×226.3×226.3；未来部署器版本另建 V3_CDS_REFERENCE）；
- 重构 B601 V2.0 子装配；
- 填写无证据数值（铰链轴径/轴承/弹簧刚度与预紧角/释放丝/锁定机构/展开冲击/
  线缆弯曲半径/铰链寿命/面板材料铺层/电池厚度 一律 UNKNOWN/TBD）；
- FEA/动力学/控制/接触/飞行与制造合规声明；Git 提交。

## 白名单来源

1. CubeSat Design Specification Rev.14.1（Cal Poly）——只约束外边界
2. OreSat structure（deprecated SolidWorks，现行 Onshape）——模块化组织参考
3. OreSat solar hardware——标准化太阳能模块思想
4. BIRDS-X CAD——工程图包组织方式
5. AlbertaSat Hyperion——太阳翼机构（弹簧铰链+burnwire 收拢保持）
6. LibreCube——标准化接口与板卡栈

## 输出（本目录）

`01_source_admission/source_admission_manifest.yaml`、
`02_feature_adoption/open_source_feature_adoption_matrix.yaml`、
`03_trade_studies/primary_structure_trade_study.md` 与
`solar_array_mechanism_trade_study.md`、
`04_cad_preparation/v2_1_master_skeleton_delta.yaml` 与 `v2_1_drawing_register.yaml`、
`05_adversarial_review/adversarial_design_record.yaml`、`B4_0_exit_gate.yaml`。

B4-0 完成后 B4-1（`Space_Embodied_Robot_CAD_V2_1/` 深化）需**另行人工批准**。
