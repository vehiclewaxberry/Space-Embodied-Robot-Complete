# 外部资产到本项目对象映射

## 1. 映射原则

`project_object` 只使用本阶段允许的对象名称。所有外部资产默认作为参考，不作为最终原创模型。

## 2. 映射表

| external_source | discovered_asset | local_path | project_object | project_usage | adaptation_needed | attribution_required | priority |
|---|---|---|---|---|---|---|---|
| OreSat Structure | `12U_Frames.SLDASM` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/Frames/12U_Frames.SLDASM` | servicer_12U_structure | 12U 外形、frame 分层、导轨/结构布局参考 | 重新建立本项目 `servicer_12U_v0`，不能直接作为最终模型 | Yes | P0 |
| OreSat Structure | `6U_Frame.SLDPRT`, `6U_Frames.SLDASM` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/Frames/` | servicer_6U_structure | 6U 快速验证构型参考 | 仅提取包络和结构层级 | Yes | P0 |
| OreSat Structure | `CardWedge*.STEP`, `OreSat_CardWedge*.SLDPRT` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/Frames/` | backplane_or_card_stack | 板卡卡槽、楔块、内部堆叠参考 | 转成中部平台舱 card-stack 占位 | Yes | P0 |
| OreSat Solar | `OreSat_SolarModule.SLDASM`, `OreSat_SolarPanel.SLDPRT` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/Solar/` | solar_panel_reference | 两侧太阳板尺寸/厚度/安装层级参考 | 根据机械臂工作空间重布置 | Yes | P0 |
| OreSat Backplane | `1.5U_BackplanePCB.DXF`, `2u-backplane.dxf`, `oresat-backplane-3u.dxf` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-backplane/` | backplane_or_card_stack | 背板和板卡连接器占位参考 | 仅抽象为板卡堆叠和线束空间 | Yes | P1 |
| OreSat Structure | `OreSat_BatteryAssembly.SLDASM`, battery holders | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/BatteryCard/` | avionics_placeholder | 电池包/电池支架占位参考 | 按质量预算重新估算 | Yes | P1 |
| OreSat Structure | `OreSat_ReactionWheels.SLDASM` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/ADACS/ReactionWheels/` | avionics_placeholder | 反作用轮组占位参考 | 简化成 reaction wheel cluster 几何和质量条目 | Yes | P0 |
| OreSat Structure | `OreSat1_CameraBoard.SLDPRT`, `lensMount.STEP`, `CassegrainBase.STEP` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/Cameras/` | avionics_placeholder | 相机/镜头/载荷安装占位参考 | 适配前端任务舱、相机视场和机械臂同轴需求 | Yes | P1 |
| OreSat Structure | `OreSat1_HelicalAntenna.SLDPRT`, `Echo34PatchAntenna.SLDPRT` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/Endcard/Helical/` | avionics_placeholder | 天线外形和部署件参考 | 避开机械臂最大工作空间 | Yes | P1 |
| OreSat Structure | `MountingBeam.STEP`, `OreSat_MountingBeam.SLDPRT` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/ADACS/ReactionWheels/` | robot_mount_adapter | 安装梁/加强件形式参考 | 仅用于加强筋/安装板构型灵感 | Yes | P1 |
| OreSat Structure | `tunacan.SLDPRT`, `CDS_v13_Maximum_spec*.SLDPRT` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/` | not_used_in_stage1 | 包络和额外体积概念参考 | 不直接用于 Stage 1 CAD；需 CDS Rev.14.1 人工复核 | Yes | P3 |
| BIRDSX-CAD | `0_2U_STD.step` to `9_2U_STD.step` | `80_third_party/external/spacecraft_layout_refs/birds/BIRDSX-CAD/BIRDSX-Structure/CAD/` | target_satellite | Target-1 失效小卫星结构/目标外观参考 | 转成非合作目标星简化盒体、太阳板/天线/标记接口 | Yes | P2 |
| BIRDSX-CAD | `Satellite part Stresses 2.xlsx`, drawings | `80_third_party/external/spacecraft_layout_refs/birds/BIRDSX-CAD/` | target_satellite | 目标星部件组织和应力/图纸参考 | 只做资料组织参考，不进入 CAD | Yes | P3 |
| PyCubed Hardware | `mainboard.step` | `80_third_party/external/spacecraft_layout_refs/pycubed/hardware/mainboard-v*/` | avionics_placeholder | OBC/C&DH 主板占位参考 | 用长方体/板卡简化，不复制电路 | Yes | P1 |
| PyCubed Hardware | `batteryboard.step` | `80_third_party/external/spacecraft_layout_refs/pycubed/hardware/batteryboard-v01*/` | avionics_placeholder | battery/EPS 板占位参考 | 用作电池板体积和接口占位 | Yes | P1 |
| PyCubed Hardware | KiCad schematics | `80_third_party/external/spacecraft_layout_refs/pycubed/hardware/mainboard-v*/` | not_used_in_stage1 | 电气架构背景 | Stage 1 不展开电路设计 | Yes | P3 |
| SpaceRobotEnv | `spacerobot_state.xml`, `spacerobot_cost.xml`, `spacerobot_dualarm.xml` | `80_third_party/external/spacecraft_layout_refs/spacerobotenv/SpaceRobotEnv/SpaceRobotEnv/assets/spacerobot/` | free_floating_dynamics_reference | 自由漂浮任务、基座扰动、末端目标等概念参考 | 不运行，不替代 reBot URDF | Yes | P2 |
| SpaceRobotEnv | `v_base.stl`, `v_shoulder.stl`, `v_upperarm.stl`, `v_forearm.stl`, `v_wrist*.stl` | `80_third_party/external/spacecraft_layout_refs/spacerobotenv/SpaceRobotEnv/SpaceRobotEnv/assets/spacerobot/stls/` | free_floating_dynamics_reference | 空间机械臂视觉网格参考 | 只做视觉/概念参考；后续动力学仍用 `reBot-DevArm_fixend.urdf` | Yes | P2 |
| SPOT | README and Simulink testbed software | `80_third_party/external/spacecraft_layout_refs/spot/SPOT/` | ground_testbed_reference | 气浮低摩擦地面试验台、motion capture、3DOF 控制叙事参考 | 不运行；只写地面样机验证路线 | Yes | P1 |
| LibreCube Notes | `README.md` | `80_third_party/README.md#librecube-notes` | not_used_in_stage1 | 模块化接口思想备注 | 暂不展开 | Yes | P3 |
| none | cylindrical adapter/debris not found as local CAD | none | target_debris | Target-2 需由本项目建立简化圆柱目标 | 不从现有外部源直接导入 | No external asset | P0 |
| none | cooperative service interface not found as local CAD | none | target_debris | Target-3 需由本项目建立把手/环/对接接口模型 | 不从现有外部源直接导入 | No external asset | P0 |

## 3. 使用结论

- 12U 服务星主参考：OreSat 12U frame + card stack + solar/backplane + ADCS/camera/antenna assets。
- 目标星参考：BIRDSX 2U STEP 组件和 OreSat frame 外观层级。
- 板卡占位参考：PyCubed mainboard/batteryboard 与 OreSat backplane。
- 动力学背景参考：SpaceRobotEnv 只用于自由漂浮问题叙事，不作为本项目动力学模型。
- 地面验证参考：SPOT 只用于低摩擦演示和实验组织，不运行软件。
