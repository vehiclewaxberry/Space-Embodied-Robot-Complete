# Stage 1-B++ 开源资产审计

## 1. 审计边界

本审计只读取本地 `80_third_party/external/spacecraft_layout_refs/` 下已有内容，不下载新资料，不运行 SpaceRobotEnv 或 SPOT，不修改外部仓库，不生成 CAD 文件。外部资产均作为参考输入，不作为本项目原创模型。

底层扫描结果：

- 外部源文件总数：`oresat` 1003、`birds` 27、`pycubed` 348、`spacerobotenv` 128、`spot` 374、`librecube_notes` 1。
- CAD/几何文件扫描命中：621 个。
- CAD/几何格式分布：DXF 37、SLDASM 94、SLDPRT 371、STEP 51、STL 44、STP 12。

## 2. 外部源总表

| source | local_path | asset_type | discovered_files | useful_for | priority | can_directly_use | needs_adaptation | originality_risk | notes |
|---|---|---|---:|---|---|---|---|---|---|
| OreSat Structure | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure` | SolidWorks assemblies/parts, STEP, STL, DXF, CubeSat frame/card/solar/camera/ADCS hardware | 结构组内多数资产；全 `oresat` 587 个 CAD/几何文件 | `servicer_12U_structure`, `servicer_6U_structure`, solar panel, backplane, card stack, reaction wheel, camera/lens, antenna, mounting details | P0 | No, reference only | 必须重新建立 `servicer_12U_v0`，只抽取布局思想、尺寸层级和接口逻辑 | High if copied as final model | README 明确结构仓库已 deprecated 且迁到 Onshape；本地 CAD 适合做机械参考和候选导入，不适合作最终原创。 |
| OreSat Solar Hardware | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-solar-hardware` | Solar module hardware reference | included in `oresat` count | solar panel reference, MPPT/module concept | P1 | No, reference only | 太阳板要按本项目机械臂工作空间重布置 | Medium | README 说明每 1U 面板有独立模块思想，可借鉴为 12U 两侧太阳板占位。 |
| OreSat Backplane | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-backplane` | Backplane DXF/PCB/reference docs | included in `oresat` count | backplane/card stack, CAN/power/RF connector layout idea | P1 | No, reference only | 只做 `internal_card_stack` 和 harness 占位参考 | Medium | README 提到 card cage/backplane、CAN、2-cell Li-ion power bus 和连接器。 |
| BIRDSX-CAD | `80_third_party/external/spacecraft_layout_refs/birds/BIRDSX-CAD` | 2U CubeSat STEP parts, drawings, stress/procurement spreadsheets | 27 files, 10 CAD/geometry files | `target_satellite`, educational 2U structural part reference | P2 | No, visual/reference only | 作为 Target-1 失效小卫星外观/结构层级参考，不能直接变成本项目目标星 | Medium | README 标注 BIRDS-X 是 2U CubeSat、1.758 kg、amateur radio mission；适合目标星参考，不适合 12U 服务星主结构。 |
| PyCubed Hardware | `80_third_party/external/spacecraft_layout_refs/pycubed/hardware` | KiCad boards, schematics, STEP board models | `pycubed` 348 files, 3 CAD/geometry files | `avionics_placeholder`, OBC/EPS/battery board volume reference | P1 | No, placeholder only | 仅抽象成 OBC/EPS/电池板卡占位，不复制电路设计 | Medium | README 说明 4-layer PCB、mainboard/batteryboard、CC BY-SA hardware；报告需要 attribution。 |
| PyCubed Software | `80_third_party/external/spacecraft_layout_refs/pycubed/software` | Flight software reference | included in `pycubed` count | `not_used_in_stage1` except avionics context | P3 | No | Stage 1 不展开软件 | Low | 当前阶段是布局和机械任务书，不进入软件审计。 |
| SpaceRobotEnv | `80_third_party/external/spacecraft_layout_refs/spacerobotenv/SpaceRobotEnv` | Mujoco XML, free-floating robot STL meshes, RL environment code | 128 files, 9 CAD/geometry files | `free_floating_dynamics_reference`, robot mesh/visual reference | P2 | No | 不运行环境；只记录 free-floating dynamics and robot mesh concepts | Medium | README 明确是 free-floating space robot trajectory planning environment；本项目 Stage 2 使用 `reBot-DevArm_fixend.urdf`，不是 SpaceRobotEnv 模型。 |
| SPOT | `80_third_party/external/spacecraft_layout_refs/spot/SPOT` | Simulink/MATLAB ground testbed software, air-bearing platform docs | 374 files, 0 CAD/geometry files in scanned formats | `ground_testbed_reference`, low-friction demo/testbed concept | P1 | No | 不运行；只抽取地面验证叙事和测量/实验组织思路 | Low | README 描述三台气浮平台、花岗岩台面、3DOF、motion capture；适合实物演示验证参考。 |
| LibreCube Notes | `80_third_party/README.md#librecube-notes` | Local note only | 1 file | modular interface idea | P3 | No | 后续需要 OBC/EPS 模块接口时再展开 | Low | 当前 README 为备注，不包含可直接导入资产。 |

## 3. Stage 1-C 直接行动建议

- P0：以 OreSat 12U/6U frame、card stack、solar/backplane/reaction wheel/camera/antenna 资产为参考，建立本项目原创 `servicer_12U_v0` 布局输入。
- P1：用 PyCubed 和 OreSat backplane 形成 OBC/EPS/battery/card-stack 占位策略；用 SPOT 形成地面演示验证叙事。
- P2：用 BIRDS 2U 结构作为 Target-1 目标星视觉参考；用 SpaceRobotEnv 只作为自由漂浮任务背景和机械臂网格参考。
- P3：LibreCube 和 PyCubed software 暂不展开。

## 4. 原创性风险控制

- 不直接复用 OreSat/BIRDS/PyCubed 模型作为最终参赛 CAD。
- 不把外部模型改名后写成本项目原创。
- 所有引用进入竞赛报告时保留 source、license/README 说明和用途边界。
- 本项目原创性应落在系统布局、机械臂安装、质量惯量接口、GJM/RNS 反作用抑制、VLA 高层任务闭环和 reBot 地面样机验证。
