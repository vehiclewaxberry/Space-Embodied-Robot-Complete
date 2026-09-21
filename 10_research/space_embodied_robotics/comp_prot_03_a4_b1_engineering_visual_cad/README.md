# COMP-PROT-03-A4-B1 Engineering Visual CAD

> `STATUS: COMPLETE_WITH_PHYSICAL_LIMITATIONS`  
> `VERDICT: A4_ENGINEERING_VISUAL_COMPLETE_WITH_PHYSICAL_LIMITATIONS`  
> `SCIENTIFIC_GATE: false`  
> `A5_AUTHORIZED: false`

## 本阶段完成了什么

在独立目录 `20_engineering/cad/Space_Embodied_Robot_CAD_V1_0/` 中建立了可由 SOLIDWORKS 2024 SP5 打开和编辑的 12U+B601 工程视觉数字样机：

- 结构化 12U 主体、纵向构件、4 道横向框环、三舱语义、设备板和可拆外板；
- A3 证据几何派生的 160 mm B601 安装接口，以及明确标为设计提案的加强筋/走线参考；
- 基于 accepted URDF + 10 份 STL 的 B601 10-link/9-joint、q=0 视觉重构；
- 左右柔性附件展开参考与安全显示提案；
- 仅承担任务语义的传感器参考与 `E_virtual`；
- 与主总装隔离的 target scene；
- 12 张原生视图和 12 张带标题、图例与 claim-limit 的评审图。

主总装：

`../../../20_engineering/cad/Space_Embodied_Robot_CAD_V1_0/Assembly/Space_Embodied_Robot_V1_0.SLDASM`

## 验收结论

- 原生 CAD：`32/32` SHA-256 一致，含 24 个零件和 8 个装配体；
- 原生重开、重建、属性、来源、拓扑与边界检查：`247/247 PASS`；
- 结构化清单：32 个文档、1,750 条属性、796 条特征、52 条装配组件记录，清单校验 `PASS`；
- A3 原生 CAD：`20/20` 哈希一致；A3 自动化基线：`6/6` 哈希一致；
- B601 accepted URDF + STL：`11/11` 当前源哈希一致；
- 冻结 Gate JSON：`15/15` 当前哈希与 A0/A1 基线一致；
- 规定视图：原生 `12/12`、带注释评审图 `12/12` 哈希一致。

逐项依据见：

- `a4_b1_acceptance_results.md`
- `a4_b1_verification_report.md`
- `a4_b1_frozen_boundary_integrity.yaml`
- `a4_b1_exit_review.yaml`
- `recovery_chain.md`

## 必须保留的负结果与限制

- `DEPLOYED_REFERENCE_Q0` 静态检查记录到 10 处干涉。它是 `NEGATIVE_RESULT`，因此全局碰撞安全保持 `BLOCKED`；不能把本阶段写成“无碰撞”或“抓取可行”。
- B601 是 accepted STL/URDF 派生的项目自有视觉重构，不是 vendor-exact CAD。
- 传感器只含零实体语义参考，不含有效硬件、选型、标定 FOV、BOM 或感知能力。SOLIDWORKS 模板仍可能导出默认材料/“质量 0.00”字段；这些字段没有材料、质量或制造权威。
- `E_virtual` 不是 physical TCP；`T_E_TCP`、接触几何与抓取接口保持 `UNKNOWN_DISABLED`。
- `T_SB`、聚合质量/质心/惯量、动力学、控制、SAFE、RL、VLA、制造和飞行资格均未授权。
- 独立 target scene 确实包含 target proxy；`TARGET_INCLUDED=FALSE` 仅表示它未进入 active engineering/operational assembly。场景中的两个组件仅相对场景坐标系静态落位；未建立组件间 mate、contact 或 rigid-lock，也不代表捕获。

## 恢复与版本说明

最终 V1.0 由一次受控续建完成。外层工具超时和早期失败均保留为历史证据，没有被隐藏；最终成功证据由 `native_build.log`、原生 manifest、`native_inspection.*`、inventory 和证据封存清单共同给出。

本阶段未创建 Git 提交或锚点。工作树原先已经非干净，A4-B1 资产保持未暂存，等待人工决定是否形成独立提交。
