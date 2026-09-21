# Stage 1 布局参考与参数模板（历史资料库）

本目录保存 2026-07 月初的布局参考、需求和预算模板。当前整星候选从 [WP03](../service_robot_wp03_spacecraft_body_r1/README.md) 进入；原 R2 基线与裁决从 [R2 发布目录](../MECHANICAL_ENGINEERING_RELEASE_R2/00_RELEASE_GATE.json) 进入。两者的模型身份和证据分别保留，Stage 1 模板不覆盖当前模型参数。

## 本目录阅读顺序

1. [来源清单](00_source_manifest/source_manifest.md)：文件来源、取得时间及当时状态。
2. [开源在轨资产目录](02_open_bus_reference/external_onorbit_asset_catalog.md)与[资产映射](02_open_bus_reference/asset_to_project_mapping.md)：外部模型的参考用途。
3. [布局需求](03_mechanical_layout_notes/)：6U/12U、适配器与目标模型；中英文重复内容已逐项归并到中文主文。
4. [质量惯量预算](04_mass_inertia_budget/mass_inertia_budget_notes.md)及[坐标定义](04_mass_inertia_budget/coordinate_frame_definition_v0.md)：保留原 CSV、坐标和缺失字段规则。
5. [工作空间与避让检查](05_workspace_and_clearance/workspace_clearance_checklist.md)：姿态、包络、证据字段；未填写项仍待验证。
6. [旧汇报图](06_competition_figures/)与[早期状态记录](07_next_actions/)：用于追溯当时方案，不作为现行进度指令。

适配器英文 `robot_mount_adapter_requirements_v0.md` 仍被 A4 来源清单按 SHA 固定，保留原件供复核；其存在不是遗漏去重。旧重组审阅报告也保持历史原文，原路径可由统一整理账本查询替代位置。

## 早期路线及规划范围

原 Stage 1 的资料目标为比赛设想中的 **300–500 kg** 级服务微卫星，涉及自由漂浮基座动力学、GJM/RNS、VLA 高层任务和 reBot 地面样机。这是早期范围记录，不能用作当前 12U 服务星质量定义。

当时以 OreSat 作为机械布局主参考，以 CubeSat Design Specification、NASA CubeSat 101、NASA Small Spacecraft Technology State-of-the-Art 作为标准与系统工程资料；SpaceRobotEnv 用于自由漂浮动力学参考，SPOT 用于低摩擦/气浮试验参考；BIRDSX-CAD、PyCubed、LibreCube 为辅助接口参考。标准文件与下载状态按 [01_standards](01_standards/) 和来源清单核查，本页不把旧人工下载清单当作实时缺件清单。

原规划的模型槽位保留在 `20_engineering/cad/spacecraft_layout/` 下的 `servicer_6U_v0`、`servicer_12U_v0`、`target_satellite_v0`、`target_debris_v0` 和 `robot_mount_adapter_v0`。目录存在不代表所列设计或验证已完成。

## 历史建库约定

原 README 与原 `07_next_actions/free_floating_servicer_stage1.md` 均说明：该轮只建立资料入口，不改已有仿真、`30_simulation/verify_model.py` 或 URDF；当时要求动力学使用 `urdf/reBot-DevArm_fixend.urdf`，不采用 `urdf/reBot_B601_DM_with_gripper.urdf`。这段作为旧阶段来源约定保留，后续模型采用其自身清单和证据，不能跨版本继承。

2026-09-06：合并上述重复建库说明及三组需求镜像，原始字节保存于项目现有整理账本；未改 CAD、CSV、Gate 或物理参数。
