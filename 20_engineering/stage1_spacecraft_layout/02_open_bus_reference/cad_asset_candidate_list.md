# CAD/几何候选资产清单

## 1. 扫描结果

扫描范围：`80_third_party/external/spacecraft_layout_refs/`

扫描格式：STEP, STP, STL, SLDPRT, SLDASM, FCStd, F3D, DXF, OBJ, URDF, mesh, DAE, STL 及 `mesh/stls` 目录。

底层扫描命中 CAD/几何文件 621 个；本表列出 Stage 1-C 最值得优先查看的 38 个候选资产。未列出的文件不代表无价值，只是不建议当前阶段深挖。

## 2. 候选清单

| file_name | local_path | format | source | candidate_usage | import_to_solidworks | direct_reference_or_visual_reference | notes |
|---|---|---|---|---|---|---|---|
| `12U_Frames.SLDASM` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/Frames/12U_Frames.SLDASM` | SLDASM | OreSat Structure | 12U 服务星主框架参考 | Yes | direct_reference | P0；只作结构参考，不作最终原创模型。 |
| `6U_Frame.SLDPRT` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/Frames/6U_Frame.SLDPRT` | SLDPRT | OreSat Structure | 6U 快速布局主体参考 | Yes | direct_reference | P0；用于 6U 外形和导轨层级。 |
| `6U_Frames.SLDASM` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/Frames/6U_Frames.SLDASM` | SLDASM | OreSat Structure | 6U 组合框架参考 | Yes | direct_reference | P0；检查装配结构。 |
| `3U_Frame.SLDPRT` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/Frames/3U_Frame.SLDPRT` | SLDPRT | OreSat Structure | 目标星/卡槽比例参考 | Yes | visual_reference | P2；辅助 Target-1。 |
| `1U_Frame.SLDPRT` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/Frames/1U_Frame.SLDPRT` | SLDPRT | OreSat Structure | 单元化结构参考 | Yes | visual_reference | P2；用于理解 U 单元。 |
| `CardWedge.STEP` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/Frames/CardWedge.STEP` | STEP | OreSat Structure | 板卡锁定/楔块参考 | Yes | direct_reference | P0；转成 internal_card_stack 参考。 |
| `CardWedgePosX.STEP` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/Frames/CardWedgePosX.STEP` | STEP | OreSat Structure | 板卡固定方向参考 | Yes | direct_reference | P1；平台舱内部细节。 |
| `OreSat_SolarPanel.SLDPRT` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/Solar/OreSat_SolarPanel.SLDPRT` | SLDPRT | OreSat Structure | 太阳板几何参考 | Yes | direct_reference | P0；需避开机械臂工作空间。 |
| `OreSat_SolarModule.SLDASM` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/Solar/OreSat_SolarModule.SLDASM` | SLDASM | OreSat Structure | 太阳板模块装配参考 | Yes | direct_reference | P1；仅抽象模块化思想。 |
| `SolarModulePCB.DXF` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/Solar/build/SolarModulePCB.DXF` | DXF | OreSat Structure | 太阳板 PCB/外形参考 | Yes | direct_reference | P1；可转占位外形。 |
| `3U_BackplaneAssembly.SLDASM` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/Backplane/3U_BackplaneAssembly.SLDASM` | SLDASM | OreSat Structure | 背板/板卡堆叠参考 | Yes | direct_reference | P1；12U 内部平台舱参考。 |
| `oresat-backplane-3u.dxf` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-backplane/3U/oresat-backplane-3u.dxf` | DXF | OreSat Backplane | 背板平面轮廓参考 | Yes | direct_reference | P1；用于 card-stack 占位图。 |
| `2u-backplane.dxf` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-backplane/2U/2u-backplane.dxf` | DXF | OreSat Backplane | 小卫星背板参考 | Yes | visual_reference | P2；可辅助 Target-1。 |
| `OreSat_BatteryAssembly.SLDASM` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/BatteryCard/OreSat_BatteryAssembly.SLDASM` | SLDASM | OreSat Structure | 电池包占位参考 | Yes | direct_reference | P1；质量需重新估算。 |
| `Battery_Samsung_ICR_18650_-22E.SLDPRT` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/COTS/other/Battery_Samsung_ICR_18650_-22E.SLDPRT` | SLDPRT | OreSat Structure | 电池单体尺寸参考 | Yes | visual_reference | P1；只作体积参考。 |
| `OreSat_ReactionWheels.SLDASM` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/ADACS/ReactionWheels/OreSat_ReactionWheels.SLDASM` | SLDASM | OreSat Structure | 反作用轮组占位参考 | Yes | direct_reference | P0；进入平台舱。 |
| `MountingBeam.STEP` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/ADACS/ReactionWheels/build/MountingBeam.STEP` | STEP | OreSat Structure | 安装梁/加强件参考 | Yes | direct_reference | P1；可启发 robot mount stiffener。 |
| `lensMount.STEP` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/Cameras/CFC/build/lensMount.STEP` | STEP | OreSat Structure | 相机镜头座参考 | Yes | direct_reference | P1；前端任务舱。 |
| `OreSat1_CameraBoard.SLDPRT` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/Cameras/OreSatLive/OreSat1_CameraBoard.SLDPRT` | SLDPRT | OreSat Structure | 相机板卡参考 | Yes | visual_reference | P1；用于 camera_payload 占位。 |
| `CassegrainBase.STEP` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/Cameras/OreSatLive/Build/CassegrainBase.STEP` | STEP | OreSat Structure | 相机/光学载荷支架参考 | Yes | visual_reference | P2；报告图参考。 |
| `OreSat1_HelicalAntenna.SLDPRT` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/Endcard/Helical/OreSat1_HelicalAntenna.SLDPRT` | SLDPRT | OreSat Structure | 天线/部署件参考 | Yes | visual_reference | P1；避开机械臂包络。 |
| `Echo34PatchAntenna.SLDPRT` | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure/COTS/other/Echo34PatchAntenna.SLDPRT` | SLDPRT | OreSat Structure | patch antenna 占位参考 | Yes | visual_reference | P2；后部通信舱。 |
| `0_2U_STD.step` | `80_third_party/external/spacecraft_layout_refs/birds/BIRDSX-CAD/BIRDSX-Structure/CAD/0_2U_STD.step` | STEP | BIRDSX-CAD | Target-1 小卫星部件参考 | Yes | visual_reference | P2；目标星外观/部件层级。 |
| `1_2U_STD.step` | `80_third_party/external/spacecraft_layout_refs/birds/BIRDSX-CAD/BIRDSX-Structure/CAD/1_2U_STD.step` | STEP | BIRDSX-CAD | Target-1 小卫星部件参考 | Yes | visual_reference | P2；与 0_2U_STD 组成目标结构参考。 |
| `5_2U_STD.step` | `80_third_party/external/spacecraft_layout_refs/birds/BIRDSX-CAD/BIRDSX-Structure/CAD/5_2U_STD.step` | STEP | BIRDSX-CAD | Target-1 细节部件参考 | Yes | visual_reference | P3；仅必要时查看。 |
| `9_2U_STD.step` | `80_third_party/external/spacecraft_layout_refs/birds/BIRDSX-CAD/BIRDSX-Structure/CAD/9_2U_STD.step` | STEP | BIRDSX-CAD | Target-1 细节部件参考 | Yes | visual_reference | P3；避免深挖全套 2U CAD。 |
| `mainboard.step` | `80_third_party/external/spacecraft_layout_refs/pycubed/hardware/mainboard-v05/mainboard.step` | STEP | PyCubed Hardware | OBC/C&DH 板卡占位 | Yes | direct_reference | P1；若该版本存在，可优先看 v05。 |
| `batteryboard.step` | `80_third_party/external/spacecraft_layout_refs/pycubed/hardware/batteryboard-v01/batteryboard.step` | STEP | PyCubed Hardware | battery/EPS 板卡占位 | Yes | direct_reference | P1；体积参考。 |
| `batteryboard.step` | `80_third_party/external/spacecraft_layout_refs/pycubed/hardware/batteryboard-v01b/batteryboard.step` | STEP | PyCubed Hardware | battery/EPS 板卡占位 | Yes | direct_reference | P1；与 v01 对比。 |
| `v_base.stl` | `80_third_party/external/spacecraft_layout_refs/spacerobotenv/SpaceRobotEnv/SpaceRobotEnv/assets/spacerobot/stls/v_base.stl` | STL | SpaceRobotEnv | 自由漂浮机械臂基座视觉参考 | Yes | visual_reference | P2；不替代 reBot。 |
| `v_shoulder.stl` | `80_third_party/external/spacecraft_layout_refs/spacerobotenv/SpaceRobotEnv/SpaceRobotEnv/assets/spacerobot/stls/v_shoulder.stl` | STL | SpaceRobotEnv | 机械臂肩部视觉参考 | Yes | visual_reference | P2；不做动力学。 |
| `v_upperarm.stl` | `80_third_party/external/spacecraft_layout_refs/spacerobotenv/SpaceRobotEnv/SpaceRobotEnv/assets/spacerobot/stls/v_upperarm.stl` | STL | SpaceRobotEnv | 机械臂上臂视觉参考 | Yes | visual_reference | P2；仅形态参考。 |
| `v_forearm.stl` | `80_third_party/external/spacecraft_layout_refs/spacerobotenv/SpaceRobotEnv/SpaceRobotEnv/assets/spacerobot/stls/v_forearm.stl` | STL | SpaceRobotEnv | 机械臂前臂视觉参考 | Yes | visual_reference | P2；仅形态参考。 |
| `v_wrist1.stl` | `80_third_party/external/spacecraft_layout_refs/spacerobotenv/SpaceRobotEnv/SpaceRobotEnv/assets/spacerobot/stls/v_wrist1.stl` | STL | SpaceRobotEnv | 腕部视觉参考 | Yes | visual_reference | P3；不进入 reBot 模型。 |
| `v_wrist2.stl` | `80_third_party/external/spacecraft_layout_refs/spacerobotenv/SpaceRobotEnv/SpaceRobotEnv/assets/spacerobot/stls/v_wrist2.stl` | STL | SpaceRobotEnv | 腕部视觉参考 | Yes | visual_reference | P3；不进入 reBot 模型。 |
| `v_wrist3.stl` | `80_third_party/external/spacecraft_layout_refs/spacerobotenv/SpaceRobotEnv/SpaceRobotEnv/assets/spacerobot/stls/v_wrist3.stl` | STL | SpaceRobotEnv | 腕部视觉参考 | Yes | visual_reference | P3；不进入 reBot 模型。 |
| `R10.stl` | `80_third_party/external/spacecraft_layout_refs/spacerobotenv/SpaceRobotEnv/SpaceRobotEnv/assets/spacerobot/stls/R10.stl` | STL | SpaceRobotEnv | 简化空间机器人几何参考 | Yes | visual_reference | P3；可用于报告图灵感。 |
| `cube.stl` | `80_third_party/external/spacecraft_layout_refs/spacerobotenv/SpaceRobotEnv/SpaceRobotEnv/assets/spacerobot/stls/cube.stl` | STL | SpaceRobotEnv | 简化基座/目标几何参考 | Yes | visual_reference | P3；不要导入为服务星。 |

## 3. 导入建议

- SolidWorks 优先查看 STEP/SLDASM/SLDPRT；DXF 用于平面板卡/背板外形。
- STL 只作为视觉参考，不用于质量惯量预算。
- BIRDS 2U STEP 只用于目标星参考，不建议转成服务星结构。
- SpaceRobotEnv STL 不进入本项目动力学链路；后续动力学仍使用 `reBot-DevArm_fixend.urdf`。
