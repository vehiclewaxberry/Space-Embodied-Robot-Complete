# 开源资产许可闸门 v0（License Gate）

> 文档角色：许可闸门（合规过滤） ｜ 类型：reference / policy
> 语言/主从：单语工作文档（中文，术语/许可名保留英文）
> 版本：v0 ｜ 最后同步：2026-07-08
> 阶段原则：本轮仅新增；闸门只做分类，不下载/不复制/不改现有文件。

本闸门对 `external_onorbit_asset_catalog.md` 中 66 条资源做**许可分级**，决定其能否进入项目"可用池"。**任何资产在进入交付资产包前，必须先过本闸门。**

## 分级规则

| 许可类别 | 闸门判定 | 项目处理 |
|---|---|---|
| Apache / MIT / BSD / ISC / Public Domain / CC BY / CC0 | **A｜可用池** | 可直接参考、可改造、可进入交付（署名义务照做） |
| LGPL / CERN-OHL / NASA-NOSA / ESA·NASA 媒体条款 | **A-｜可用池（附注）** | 可用，但需注意弱 copyleft / 逐模型条款 / 非标准 OSI |
| CC BY-NC / CC BY-NC-SA / 学术免费·禁商用 | **B｜仅研究参考** | 可阅读/研究/复现，**不进入竞赛交付资产包** |
| GPL / AGPL | **C｜隔离** | 先隔离，避免污染主交付；仅作独立工具/研究，不静态并入交付代码 |
| 无 LICENSE / 需注册 / 受限 / 逐模型不明 | **D｜待确认** | 只作线索，**不复制、不改用、不交付**，须逐个向作者/平台确认后才可升级 |

---

## A｜可用池（可进入交付）

| 资源 | 许可 | 角色 |
|---|---|---|
| Basilisk | ISC | servicer 动力学/GNC |
| NASA Astrobee | Apache-2.0 | servicer 基座 |
| 42 (NASA GSFC) | NOSA (A-) | servicer / 碎片接触 |
| MuSCAT | Apache-2.0 | servicer 系统预算 |
| KubOS / Cube-OS | Apache-2.0 | 飞控中间件 |
| SPART | LGPL-3.0 (A-, 弱 copyleft) | 机械臂动力学 |
| Space Robotics Bench | MIT/Apache/CC0 | 机械臂 RL |
| SpaceOctopus（清华） | Apache-2.0 | 多臂自由漂浮 RL |
| Space ROS + demos | Apache-2.0 | Canadarm2 ROS2 |
| OnOrbitROS | MIT | ETS-VII ROS 仿真 |
| SmallSatSim | Apache-2.0 | 接触仿真/地面台 |
| MATLAB 双臂碎片捕获 | MIT | 碎片捕获实现 |
| MMT/RoBo6/LCDC | MIT | 翻滚率标定 |
| NASA 3D Resources | Public Domain (A-, 逐模型核对) | 目标几何 |
| ESA SCIFLEET | CC-BY-SA IGO (A-, 逐模型) | 目标几何 |
| ESA/Hubble 3D | ESA 媒体 (A-, 逐模型) | 大型目标 |
| SPEED | CC BY 3.0 | 位姿数据集（可商用） |
| SPEED-UE-Cube | CC BY 4.0 | 位姿数据集（立方星） |
| SwissCube / wide-depth | BSD-3 | 位姿数据集 |
| URSO / UrsoNet | MIT + CC BY 4.0 | 位姿数据集（可商用） |
| IDSS | 公开 ICD | 对接接口基准 |
| AstraTag | Apache-2.0 / CC BY | 在轨合作靶标 |
| AprilTag + imgs | BSD-2 | 标记+位姿 |
| OpenCV ArUco/ChArUco | Apache-2.0 | 标记生成/检测 |
| speedplusbaseline | MIT | 关键点→PnP |
| AprilCube | MIT | 可打印立体靶 |
| bac-hardware | CERN-OHL-S / CC-BY-SA (A-) | 机-电互连接口 |
| ATMOS/DISCOWER 飞控 (PX4-Space-Systems) | BSD-3 | 气浮台飞控代码；⚠️ 气浮台 **CAD (w3_atmos)=GPL-3.0 → 见 C 档**（2026-07-09 逐仓核验） |
| bsk-ros2-bridge | BSD-3 | HIL 桥 |
| open-air-bearings | MIT | 气浮轴承设计 |
| M-STAR 控制分配 | MIT | 推力器分配 |
| reaction_wheel | MIT | 反作用轮件 |
| SoftCapture | MIT | 软捕获制导 |
| OpenManipulator-X | Apache-2.0 | 臂+夹爪 CAD |
| Robonaut2/Valkyrie URDF | NOSA (A-) | 灵巧末端 |
| astrobee_media | NASA 媒体 (A-) | 栖附臂/扶手网格 |
| OSSAT/KISPE | CC-BY-SA (A-) | 微卫星级总线 |
| UPSat（结构） | CERN-OHL v1.2 (A-) | 整星结构 CAD |
| Quetzal-1 | CC-BY-SA (A-) | EPS/ADCS 飞行验证 |
| Awesome Space Robotics | CC0 | 资源聚合 |
| OpenGrab EPM（硬件） | CC BY-SA 4.0 (A-) | 磁吸捕获硬件 |

## B｜仅研究参考（不进交付）

| 资源 | 许可 | 说明 |
|---|---|---|
| SPEED+ | CC BY-NC-SA | 旗舰位姿集，仅研究/复现 |
| SHIRT | CC BY-NC-SA | 翻滚接近轨迹，仅研究 |
| SPE3R | CC BY-NC-SA | 64 航天器 3D，仅研究 |
| SpaceDyn | 学术免费/禁商用 | GJM 基线，**只做理论交叉验证** |
| Yale OpenHand | CC BY-NC | 抓取器 CAD，仅研究 |
| LEAP Hand（CAD） | CC BY-NC-SA（⚠️代码 README 称 MIT，但仓库唯一 LICENSE 实为 CC-BY-NC-4.0，GitHub 报 NOASSERTION，标*待核） | 灵巧手 CAD 仅研究（NC 禁商用；CAD 需 leaphand.com 申请） |
| DexHand | CC BY-NC-SA | 灵巧手 CAD 仅研究 |

## C｜隔离（强 copyleft，避免污染主交付）

| 资源 | 许可 | 说明 |
|---|---|---|
| SPIN | GPL-3.0 | 定制渲染，独立运行不并入交付代码 |
| aruco_3d | AGPL-3.0 | AprilCube 的备选，网络服务会传染，优先用 AprilCube(MIT) |
| TraceableRobotModels | GPL-3.0 | URDF 参考 |
| OSF 球面气浮台 | GPL-3.0 | 台架 CAD |
| SATLLA / FOSSASAT-1 | GPL-3.0 | 目标几何 |
| SUCHAI/SPEL、MOVE-II、Delfi-PQ | GPL/LGPL | 飞控软件参考 |
| ATMOS/DISCOWER 气浮台 CAD (w3_atmos) | GPL-3.0 | 气浮台机械 CAD（STL/DXF/GLB）；**2026-07-09 逐仓核验由 A- 下调**，隔离、不并入交付（其 PX4 飞控代码 BSD-3 见 A 档） |

## D｜待确认（不纳入，仅线索）

| 资源 | 许可状态 | 说明 |
|---|---|---|
| space_robot（清华） | 无 LICENSE | 翻滚目标 URDF，**仅线索**，须联系作者授权 |
| The Slider | 无 LICENSE（论文称开源） | 气浮台整机 CAD，须向作者确认 |
| Sapling | 无 LICENSE（顶层） | 逐子仓核对 |
| CubeSat 万向节台 | 无 LICENSE | 姿态台 CAD |
| Cold-Gas-Thruster | 无 LICENSE | 喷嘴设计代码 |
| SoftQLearning4SpaceRobots | 无 LICENSE | 捕获 RL |
| SatelliteDataset | 无 LICENSE（Google Drive） | 部件检测 |
| Spacecraft-DS | 无 LICENSE（Google Drive） | 部件检测 |
| SPARK | 需 cvi2.uni.lu 注册授权 | 碎片数据集 |
| GrabCAD 库 | 逐模型条款不明 | 适配器/对接环几何 |

---

## 交付红线（一句话）

**只有 A / A- 类可进入竞赛交付资产包；B 类仅供研究阅读与算法复现；C 类隔离使用；D 类在获得明确授权前不得复制或改用。** 每次把某资源写入 CAD/仿真/报告前，回到本表确认其闸门等级。
