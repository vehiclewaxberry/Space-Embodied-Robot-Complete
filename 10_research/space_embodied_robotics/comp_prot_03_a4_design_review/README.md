# COMP-PROT-03-A4 Engineering Geometry Design Review

_12U+B601 空间具身机器人机械结构深化设计评审，2026-07-23_

---

> `STATUS: A4_DESIGN_REVIEW_COMPLETE`  
> `CURRENT_CAD: A3_GEOMETRY_ONLY_BASELINE`  
> `NEXT_CAD_SCOPE: ENGINEERING_VISUAL_ONLY`  
> `SCIENTIFIC_GATE: false`  
> `CAD_AUTHORING_AUTHORIZED: false`

## 📋 裁决

当前 A3 结果是合格的几何合同样机，但不是比赛展示所需的机械结构样机。A4 已完成从“包络块”到“工程视觉结构”的设计定义：

- 12U 主体由单一实体升级为外框、三舱、设备板和外板层级；
- 太阳翼、后服务模块、任务面和适配器形成独立模块；
- B601 从轴对齐包围盒升级为基于 accepted STL/URDF 的 link 级视觉重构；
- 现有夹爪可进入视觉装配，physical TCP 和接触结构继续禁用；
- 传感器只能进入非实体 reference/semantic overlay，硬件实体延期到 A5；
- 目标和捕获接口继续作为独立场景分支，不进入当前主总装。

本目录不包含新的 SolidWorks 文件，也不授权自动进入 CAD 建模。

## 📚 交付文件

| 文件 | 用途 |
|---|---|
| [`embodied_mechanical_design_specification.md`](./embodied_mechanical_design_specification.md) | A4 机械结构、视觉语言和四层数字身体主规范 |
| [`a4_component_register.yaml`](./a4_component_register.yaml) | 模块、状态、来源和禁用消费者的机器可读登记 |
| [`mechanical_design_council_review.md`](./mechanical_design_council_review.md) | 航天结构、机械臂/动力学边界、具身语义与红队综合评审 |
| [`a4_cad_acceptance_matrix.md`](./a4_cad_acceptance_matrix.md) | 下一版 CAD 的入口、退出、视图和否决标准 |
| [`a4_source_traceability.yaml`](./a4_source_traceability.yaml) | A3、SSOT、URDF/STL 和许可输入的哈希链 |
| [`a4_design_review_exit.yaml`](./a4_design_review_exit.yaml) | 本轮非科学 Gate 裁决与下一授权边界 |
| [`a4_packet_hash_manifest.csv`](./a4_packet_hash_manifest.csv) | 本轮交付包的字节数与 SHA-256 清单 |

## 🎯 下一阶段

下一阶段建议命名为：

`COMP-PROT-03-A4-B1-ENGINEERING-VISUAL-CAD`

其最高允许结果是：

`A4_ENGINEERING_VISUAL_COMPLETE_WITH_PHYSICAL_LIMITATIONS`

开始前仍需新的人工批准。该批准只能允许结构化 12U、太阳翼显示构型、adapter 工程视觉件、B601 STL/URDF 视觉重构和语义 reference overlay；不得允许 vendor STEP、传感器硬件、目标接触、URDF、动力学、控制、SAFE、RL 或 VLA。

## 🚫 仍然禁止

- 不把工程视觉外壳称为供应商精确 CAD、制造模型或飞行件
- 不从 SolidWorks 默认材料读取或覆盖质量、质心和惯量
- 不定义 `T_SB`、physical TCP、接触面或刚性捕获接口
- 不把 FOV 标签称为已选相机、已标定视场或已验证观测覆盖
- 不把动画、截图、Agent 共识或静态干涉当作科学证据
- 不修改 A3 原生 CAD；A4 必须创建独立新版本
