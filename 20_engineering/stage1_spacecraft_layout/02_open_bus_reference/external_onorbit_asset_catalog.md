# 开源在轨航天器资源目录 v0（外部资产入口）

> 文档角色：外部开源资产目录（唯一入口） ｜ 类型：reference
> 语言：**中文合并入口**。2026-09-06 已逐项对比并删除英文镜像 `external_onorbit_asset_catalog.en.md`；两文 66 条资源、URL 顺序与优先级一致。英文“Multi-body / register-confirm”等翻译差异不覆盖中文“多星 / 待授权”。原英文及当时许可、状态记录可从统一整理账本恢复；下文仍是 2026-07-08 的历史资料记录。
> 版本：v0 ｜ 最后同步：2026-07-08
> 阶段原则：本轮仅新增；本目录只登记与判定，不下载/不复制资产。

本目录是项目对**外部开源在轨航天器/在轨服务资源**的正式入口，替代此前仅存在于会话记录的临时清单。共 **66 条**，由多智能体联网检索 + 逐条 URL/许可证核验产出，按 9 类角色分类。已有主参考（OreSat / BIRDS / PyCubed / SpaceRobotEnv / SPOT / LibreCube）见 `source_manifest.md`，本目录为其补充。

**配套文档**：许可分级见 [`license_gate_v0.md`](./license_gate_v0.md)；到 CAD 交付物的映射见 [`cad_asset_mapping_v0.md`](./cad_asset_mapping_v0.md)；缺口风险见 [`external_asset_gap_risks_v0.md`](./external_asset_gap_risks_v0.md)。

**闸门标记**（详见 license_gate）：A=可用池 / A-=可用池附注 / B=仅研究参考 / C=隔离(强copyleft) / D=待确认(无许可/受限)。**只有 A/A- 可进入交付。**

---

## 覆盖度速览

| 角色 | 覆盖 | 缺口 |
|---|---|---|
| 服务星总线/GNC | 充足（软件/仿真） | 无 300–500kg 整星制造 CAD (RA-001) |
| 机械臂动力学/仿真 | 极充足 | — |
| 目标失效卫星几何 | 充足 | 无实测惯量真值 (RA-003) |
| 碎片/翻滚上面级 | 改善 | 无实测惯量真值 (RA-003) |
| 合作对接接口 | 强（标记类） | 无制造级对接环 CAD (RA-002) |
| 交会位姿数据集 | 极充足 | 真实在轨图像稀缺 (RA-006) |
| 地面气浮验证 | 基本填补 | 部分许可不清 (RA-005) |
| 抓捕/末端执行器 | 增强 | 无空间级制造 CAD (RA-004) |
| 任务/资源聚合 | 覆盖 | 中文原生稀缺 (RA-007) |

## ★ 必用核心（P0）
Basilisk（服务星动力学/GNC）｜Astrobee（自由飞行基座）｜SPART（机械臂 GJM/RNS）｜SpaceDyn（GJM 理论交叉验证, 仅研究）｜SPEED+（位姿数据, 仅研究）｜IDSS（对接接口基准）。

---

## 复合许可核验注（2026-07-09 逐仓核验，含证据）

对下列 4 条**复合许可**资源逐仓核验其"实际可用资产（硬件/CAD，而非固件/软件）"的真实许可，避免 GPL/NC 成分被"只有 A/A- 进交付"的自动筛选误读。**唯一实质下调：ATMOS 气浮台 CAD 由 A- 更正为 C。**

| 资源 | 可用资产真实许可 | 闸门（修正后） | 关键证据 |
|---|---|---|---|
| UPSat 结构 | CERN-OHL-1.2（仅结构 CAD，**非 GPL**） | A-（不变；原"/GPL"误标已删） | GitLab `LICENSE`=“CERN Open Hardware Licence v1.2”；仓库已从 GitHub 迁至 GitLab |
| ATMOS/DISCOWER | 气浮台 CAD(`w3_atmos`)=**GPL-3.0** ｜ 飞控(`PX4-Space-Systems`)=BSD-3 | **C（CAD，原 A- 误判已下调）** / A（飞控代码） | `w3_atmos` GitHub license API=GPL-3.0；PX4 `LICENSE`=BSD-3-Clause |
| OpenGrab EPM | 硬件 CAD(`/hardware` STEP/IGS/SLDPRT)=**CC-BY-SA-4.0** ｜ 固件=GPL-3.0 | A-（硬件）/C（固件）（原判正确，仅澄清拆分） | README=“hardware sources … CC BY-SA 4.0”；根 `LICENSE`=GPL-3.0 |
| LEAP Hand | 手部 CAD=**CC-BY-NC-SA**（NC 禁商用，需 leaphand.com 申请）｜ 代码 README 称 MIT，但仓库唯一 `LICENSE`=CC-BY-NC-4.0，GitHub 报 NOASSERTION | B（CAD，仅研究，**主用途**）/ A*（代码，待核） | `LICENSE`=CC-BY-NC-4.0；`readme.md`=“Code: MIT / CAD: CC BY-NC-SA” |

> 结论：本项目实际会用的**硬件/CAD** 中，仅 ATMOS 气浮台 CAD 为强 copyleft（GPL），须隔离、不得并入竞赛交付；UPSat 结构 CAD 为 CERN-OHL 硬件许可（A-，可商用但 share-alike）；OpenGrab 硬件 CAD 为 CC-BY-SA（A-）；LEAP 手部 CAD 为 NC（B，仅研究）。`license_gate_v0.md` 与 `cad_asset_mapping_v0.md` 已同步。

---

## 1. servicer_bus_ref — 服务星平台/总线/GNC
| 资源 | URL | 许可 | P | 闸门 | 用途 |
|---|---|---|---|---|---|
| Basilisk (AVS Lab) | https://github.com/AVSLab/basilisk | ISC | P0 | A | 整星姿轨动力学+GNC 主仿真基座 |
| NASA Astrobee | https://github.com/nasa/astrobee | Apache-2.0 | P0 | A | ISS 自由飞行机器人 RPO 软件范式 |
| 42 (NASA GSFC) | https://github.com/ericstoneking/42 | NOSA | P1 | A- | 多星相对动力学+接触力（跨碎片角色） |
| OSSAT/KISPE | https://github.com/Open-Source-Satellite/OSSAT_OBC_Dev_Board | CC-BY-SA | P1 | A- | 质量量级最贴近的微卫星级开源总线 |
| MuSCAT (JPL) | https://github.com/nasa/muscat | Apache-2.0 | P2 | A | 整星子系统预算/trade study |
| KubOS/Cube-OS | https://github.com/Cube-OS/cubeOS | Apache-2.0 | P2 | A | 飞控中间件架构 |
| UPSat (Libre Space) | https://gitlab.com/librespacefoundation/upsat/upsat-structural | CERN-OHL-1.2 | P2 | A- | 全开源在轨 2U 整星结构 CAD（结构 CAD＝CERN-OHL 硬件许可，**非 GPL**；GitHub 仓已迁 GitLab，见文首「复合许可核验注」） |
| Quetzal-1 (UVG) | https://github.com/Quetzal-1-CubeSat-Team/quetzal1-hardware | CC-BY-SA-4.0 | P2 | A- | 飞行验证 EPS/ADCS+遥测 |
| Delfi-PQ (TU Delft) | https://github.com/DelfiSpace | GPL/LGPL | P2 | C | 模块化 PQ9 总线接口 |
| Sapling (Stanford SSI) | https://github.com/stanford-ssi/sapling | 无 LICENSE | P2 | D | PyCubed 生态整星集成经验（仅线索） |

## 2. arm_dynamics_sim — 自由漂浮机械臂动力学/仿真
| 资源 | URL | 许可 | P | 闸门 | 用途 |
|---|---|---|---|---|---|
| SPART (NPS-SRL) | https://github.com/NPS-SRL/SPART | LGPL-3.0 | P0 | A- | URDF→GJM/RNS 工具箱（reBot 主工具） |
| SpaceDyn (Tohoku) | https://github.com/Space-Robotics-Laboratory/SpaceDyn | 学术/禁商用 | P0 | B | GJM/RNS 理论交叉验证（不进交付） |
| Space Robotics Bench | https://github.com/AndrejOrsula/space_robotics_bench | MIT/Apache/CC0 | P1 | A | Isaac Sim RL，含 debris_capture |
| SpaceOctopus（清华） | https://github.com/Tsinghua-Space-Robot-Learning-Group/SpaceOctopus | Apache-2.0 | P1 | A | 多臂自由漂浮+基座零反作用 RL（国内锚点） |
| Space ROS + demos | https://github.com/space-ros/demos | Apache-2.0 | P1 | A | Canadarm2 ROS2 抓捕仿真 |
| OnOrbitROS | https://github.com/OnOrbitROS/Simulation | MIT | P2 | A | ETS-VII 在轨机械臂 ROS 仿真 |
| TraceableRobotModels | https://github.com/vyas-shubham/TraceableRobotModels | GPL-3.0 | P2 | C | SSRMS/Canadarm/ETS-VII URDF |
| SoftQLearning4SpaceRobots | https://github.com/ycz0512/SoftQLearning4SpaceRobots | 无 LICENSE | P2 | D | 捕获 RL 思路（仅线索） |

## 3. target_satellite — 目标失效卫星几何
| 资源 | URL | 许可 | P | 闸门 | 用途 |
|---|---|---|---|---|---|
| NASA 3D Resources | https://github.com/nasa/NASA-3D-Resources | Public Domain | P1 | A- | Agena 圆柱目标+卫星几何（逐模型核对） |
| ESA SCIFLEET | https://scifleet.esa.int/ | CC-BY-SA IGO | P1 | A- | 大型卫星高保真几何 |
| SPE3R (Stanford) | https://purl.stanford.edu/pk719hm4806 | CC BY-NC-SA | P1 | B | 64 个航天器 3D 模型（仅研究） |
| ESA/Hubble 3D | https://esahubble.org/products/models3d/ | ESA 媒体 | P2 | A- | 大型可维修目标参照 |
| SATLLA-0/2B | https://github.com/kcglab/satllazero | GPL-3.0 | P2 | C | 可下载结构 STL |
| FOSSASAT-1 | https://github.com/FOSSASystems/FOSSASAT-1 | GPL-3.0 | P2 | C | 极小目标体外形 |
| SatelliteDataset | https://github.com/Yurushia1998/SatelliteDataset | 无 LICENSE | P2 | D | 部件检测/分割（仅线索） |
| Spacecraft-DS (SEU) | https://github.com/spacecraftds/Spacecraft-DS | 无 LICENSE | P2 | D | 真实 HIL 部件识别（仅线索） |

## 4. target_debris — 碎片/翻滚上面级（另见 42、SmallSatSim）
| 资源 | URL | 许可 | P | 闸门 | 用途 |
|---|---|---|---|---|---|
| space_robot（清华） | https://github.com/Mingrui-Yu/space_robot | 无 LICENSE | P1 | D | 可加载翻滚目标 URDF+夹爪（仅线索，须授权） |
| MATLAB 双臂碎片捕获 | https://github.com/Space-Robotics-Laboratory/MATLAB_space_debri_capturing_sim | MIT | P1 | A | 消旋+包络捕获实战实现（配 SpaceDyn） |
| SPARK 数据集 | https://zenodo.org/records/6599762 | 需注册 | P1 | D | 唯一含"碎片"类识别数据（登记待授权） |
| MMT/RoBo6/LCDC | https://huggingface.co/datasets/kyselica/RoBo6 | MIT | P2 | A | 上面级真实翻滚率标定 |

## 5. cooperative_interface — 合作对接接口/标记靶标
| 资源 | URL | 许可 | P | 闸门 | 用途 |
|---|---|---|---|---|---|
| IDSS 国际对接标准 | https://www.internationaldockingstandard.com/ | 公开 ICD | P0 | A | 对接环权威几何/载荷基准 |
| AstraTag | https://github.com/astradyn/astratag | Apache-2.0/CC BY | P1 | A | 唯一在轨专用合作靶标（多距离/曲面） |
| AprilTag + imgs | https://github.com/AprilRobotics/apriltag | BSD-2 | P1 | A | 事实标准标记+6DOF 位姿 |
| OpenCV ArUco/ChArUco | https://github.com/opencv/opencv | Apache-2.0 | P1 | A | 标记生成/检测/位姿 |
| speedplusbaseline | https://github.com/tpark94/speedplusbaseline | MIT | P1 | A | 关键点→PnP 位姿管线 |
| AprilCube | https://github.com/younghyopark/aprilcube | MIT | P2 | A | 可3D打印立体靶 CAD（备选 aruco_3d=AGPL/C） |
| bac-hardware | https://codeberg.org/buildacubesat-project/bac-hardware | CERN-OHL-S/CC-BY-SA | P2 | A- | 机-电互连接口标准 CAD |
| GrabCAD 库 | https://grabcad.com/library/tag/cubesat | 混合 | P2 | D | 适配器/对接环几何占位（逐模型确认） |

## 6. rendezvous_pose_dataset — 交会位姿数据集
| 资源 | URL | 许可 | P | 闸门 | 用途 |
|---|---|---|---|---|---|
| SPEED+ (Stanford+ESA) | https://purl.stanford.edu/wv398fc4383 | CC BY-NC-SA | P0 | B | 旗舰位姿+域适应（仅研究） |
| SPEED | https://zenodo.org/records/6327547 | CC BY 3.0 | P1 | A | 许可最宽松（可商用），入门标准 |
| SPEED-UE-Cube | https://purl.stanford.edu/hw812wb1641 | CC BY 4.0 | P1 | A | 3U 立方星尺度+时序 |
| SwissCube (EPFL) | https://github.com/cvlab-epfl/wide-depth-range-pose | BSD-3 | P1 | A | 立方星逐部件 CAD+宽深度 |
| URSO / UrsoNet | https://github.com/pedropro/UrsoNet | MIT/CC BY 4.0 | P1 | A | Soyuz/Dragon/Envisat，可商用 |
| SHIRT (Stanford) | https://purl.stanford.edu/zq716br5462 | CC BY-NC-SA | P1 | B | 翻滚目标接近段时序轨迹（仅研究） |
| SPIN (UAM) | https://github.com/vpulab/SPIN | GPL-3.0 | P1 | C | 按 reBot 构型定制生成数据（隔离） |

## 7. ground_testbed — 地面气浮/验证平台（reBot + SPOT 补充）
| 资源 | URL | 许可 | P | 闸门 | 用途 |
|---|---|---|---|---|---|
| ATMOS/DISCOWER (KTH) | https://github.com/DISCOWER | GPL-3.0(CAD)/BSD-3(飞控) | P1 | C(CAD)/A(飞控) | 气浮台 CAD(w3_atmos)＝GPL-3.0 **须隔离、不进交付**；PX4 飞控代码＝BSD-3 可用（原 A- 经核验下调，见核验注） |
| bsk-ros2-bridge | https://github.com/DISCOWER/bsk-ros2-bridge | BSD-3 | P1 | A | Basilisk↔气浮台 HIL 桥 |
| SmallSatSim (JPL/UMich) | https://github.com/usclaser/smallsat-sim | Apache-2.0 | P1 | A | MuJoCo 接触仿真（跨碎片角色） |
| The Slider (LTU) | https://github.com/LTU-RAI/The_Slider-Low_Friction_Platform | 无 LICENSE | P1 | D | 完整 2D 气浮台机械 CAD（仅线索） |
| OSF 球面气浮台 | https://osf.io/k5zb8/ | GPL-3.0 | P2 | C | 三轴姿态气浮台 CAD |
| open-air-bearings | https://github.com/0x23/open-air-bearings | MIT | P2 | A | 气浮轴承自制工艺 |
| M-STAR 控制分配 | https://github.com/ynakka/spacecraft_control_allocation | MIT | P2 | A | 推力器分配算法 |
| CubeSat 万向节台 | https://github.com/dylanballback/CubeSat_Attitude_Control | 无 LICENSE | P2 | D | 非气浮姿态台（仅线索） |
| reaction_wheel | https://github.com/CGrassin/reaction_wheel | MIT | P2 | A | 可打印反作用轮件 |
| Cold-Gas-Thruster | https://github.com/jprks/Cold-Gas-Thruster | 无 LICENSE | P2 | D | 冷气喷嘴设计（仅线索） |

## 8. docking_grapple_mechanism — 抓捕/末端执行器
| 资源 | URL | 许可 | P | 闸门 | 用途 |
|---|---|---|---|---|---|
| SoftCapture (CMU) | https://github.com/RoboticExplorationLab/SoftCapture | MIT | P1 | A | 翻滚目标软捕获制导 |
| Yale OpenHand | https://www.eng.yale.edu/grablab/openhand/ | CC BY-NC | P1 | B | 自适应抓取器 CAD（仅研究） |
| OpenGrab EPM | https://github.com/Zubax/opengrab_epm_v3 | CC-BY-SA-4.0(硬件)/GPL-3.0(固件) | P2 | A-(硬件CAD)/C(固件) | 电永磁磁吸捕获；硬件 CAD(STEP/IGS/SLDPRT)＝CC-BY-SA 可用，固件 GPL 隔离（见核验注） |
| Robonaut2/Valkyrie URDF | https://github.com/gkjohnson/nasa-urdf-robots | NOSA | P2 | A- | 飞行履历灵巧手 |
| OpenManipulator-X | https://github.com/ROBOTIS-GIT/open_manipulator | Apache-2.0 | P2 | A | 臂+夹爪完整 CAD/URDF |
| LEAP Hand (CMU) | https://github.com/leap-hand/LEAP_Hand_API | CC-BY-NC-SA(CAD)/MIT?(代码) | P2 | B(CAD)/A*(代码) | 16-DOF 灵巧手；手部 CAD＝NC 禁商用**仅研究**(B，主用途)；代码 README 称 MIT 但仓库 LICENSE 实为 CC-BY-NC-4.0，标*待核（见核验注） |
| DexHand | https://github.com/iotdesignshop/dexhand-mechanical-build | CC BY-NC-SA | P2 | B | 完整机械 CAD/BOM（仅研究） |
| astrobee_media | https://github.com/nasa/astrobee_media | NASA 媒体 | P2 | A- | 栖附臂/ISS 扶手网格 |

## 9. mission_reference — 任务/资源聚合
| 资源 | URL | 许可 | P | 闸门 | 用途 |
|---|---|---|---|---|---|
| Awesome Space Robotics | https://github.com/AndrejOrsula/awesome-space-robotics | CC0 | P2 | A | 在轨服务/机械臂资源聚合入口 |
| SUCHAI/SPEL (智利) | https://github.com/spel-uchile | GPL-3.0 | P2 | C | 在轨姿态真值数据集 |
| MOVE-II (TUM) | https://github.com/MOVE-II | GPL-3.0 | P2 | C | CDH 软件栈 |

---

## 缺口（不再靠盲搜解决，已转风险，见 `external_asset_gap_risks_v0.md`）
1. 无 300–500kg 级服务星整星制造 CAD（RA-001）
2. 无制造级软捕获/对接环 CAD（RA-002）
3. 目标星/碎片无实测质量-惯量真值（RA-003）
4. 抓捕末端无空间级制造 CAD（RA-004）
5. 许可风险（RA-005）／真实在轨图像稀缺（RA-006）／中文原生稀缺（RA-007）
