# 空间具身智能机械臂：文献与开源资料索引（碎片清除 + 在轨搭建）

> 检索日期 2026-07-21 | 组织方式对齐 V0–V4 螺旋 | DOI 标记：`✔` 本轮已核实来源页 · `⚠` 需 Crossref 复核（下载 prompt 已含自动校验步骤）

---

## 0. 怎么用这份清单

分三种读法，不要混：

- **【定调】** — 写报告"研究现状 / 技术路线对比"直接引，读摘要 + 结论 + 图表即可，不必精读。
- **【推导】** — 你要自己重推公式的，必须逐式过一遍，对应 V1/V2/V3 的理论块。
- **【对标】** — 只看它做到了什么、指标是多少，用来定你的性能目标和"杀手图"基线。

开源资料同样分级：**A = 可直接复用进你的仓库**；**B = 参照实现，需要改写**；**C = 仅作对标/读代码理解方法**。

---

## 1. 第一层：定调综述（先读这一层，写报告用）

| # | 文献 | DOI | 定位 |
|---|---|---|---|
| S1 | Rybus T. (2024) *Robotic manipulators for in-orbit servicing and active debris removal: Review and comparison*, **Prog. Aerosp. Sci.** 151:101055 | `10.1016/j.paerosci.2024.101055` ✔ | **本清单第一优先**。把历史上所有 ADR/IOS 机械臂逐台列出并横向对比（自由度、臂长、质量、末端执行器）。你做臂本体参数选型和"为什么是 6/7 DOF、为什么这个臂长"的论证，直接从这里取表 |
| S2 | Papadopoulos E., Aghili F., Ma O., Lampariello R. (2021) *Robotic manipulation and capture in space: A survey*, **Front. Robot. AI** 8:686723 | `10.3389/frobt.2021.686723` ✔ | 动力学建模 → 规划 → 捕获 → 捕获后镇定的完整方法学地图。四位作者分别是 GJM 学派、接触动力学、地面验证的代表人物 |
| S3 | Alizadeh M., Zhu Z.H. (2024) *A comprehensive survey of space robotic manipulators for on-orbit servicing*, **Front. Robot. AI** 11:1470950 | `10.3389/frobt.2024.1470950` ✔ | 最新一版全景（含 OSAM-1/SPIDER、Canadarm3 状态），补 S1 之后的进展 |
| S4 | Farhad N., Zhu Z.H. *Review of Autonomous Space Robotic Manipulators for On-Orbit Servicing and Active Debris Removal*, **Space Sci. Technol.** | `10.34133/space.0291` ✔ | 聚焦**自主性**层级划分。你论证"为什么需要 VLA 而不是遥操作"时，用它的自主等级框架 |
| S5 | Zhang W. et al. (2022) *Review of On-Orbit Robotic Arm Active Debris Capture Removal Methods*, **Aerospace** 10(1):13 | `10.3390/aerospace10010013` ⚠ | 用文献计量法梳理 1983–2022 的 RA-ADCR 领域热点演化。适合做"研究趋势"图 |
| S6 | Ellery A. (2019) *Tutorial Review on Space Manipulators for Space Debris Mitigation*, **Robotics** 8(2):34 | `10.3390/robotics8020034` ✔ | 教程式，对基座反作用问题的物理直觉讲得最透。适合给队里非动力学背景的成员当入门材料 |
| S7 | Flores-Abad A., Ma O., Pham K., Ulrich S. (2014) *A review of space robotics technologies for on-orbit servicing*, **Prog. Aerosp. Sci.** 68:1–26 | `10.1016/j.paerosci.2014.03.002` ⚠ | 经典基准综述，被引最高。写引言时的"标准起手引用" |

---

## 2. V1 —— 自由漂浮基座：GJM 与 Reaction Null-Space

你已有 Umetani & Yoshida 1989（`10.1109/70.34766`）与 Nenchev et al. 1999（`10.1109/70.817666`），下面是需要补齐的**推导链条**。

| # | 文献 | DOI | 为什么必须读 |
|---|---|---|---|
| C1 | Wilde M., Kwok Choon S., Grompone A., Romano M. (2018) *Equations of Motion of Free-Floating Spacecraft-Manipulator Systems: An Engineer's Tutorial*, **Front. Robot. AI** 5:41 | `10.3389/frobt.2018.00041` ✔ | 【推导】**这是你 V1 理论章节的骨架**。把 VM（虚拟机械臂）/ DEM（动力学等效机械臂）/ GJM 三条路线并列推导并给出等价关系。你只用 GJM 的话，也必须知道另两条存在——评委会问"为什么不用 DEM" |
| C2 | Yoshida K., Hashizume K., Abiko S. (2001) *Zero Reaction Maneuver: Flight Validation with ETS-VII Space Robot and Extension to Kinematically Redundant Arm*, **ICRA 2001**, 441–446 | `10.1109/ROBOT.2001.932589` ⚠ | 【推导+对标】RNS 唯一的**在轨飞行验证**。你的"RNS vs 朴素规划基座姿态扰动对比"杀手图，基线必须对齐这篇的实测数据 |
| C3 | Yoshida K. (2003) *ETS-VII flight experiments for space robot dynamics and control*, **Int. J. Robot. Res.** 22(5):321–335 | `10.1177/0278364903022005003` ⚠ | 【对标】ETS-VII 全套实验的总结。GJM 在轨精度、时延遥操作、阻抗匹配都在里面 |
| C4 | Xu W. et al. (2017) *Analysis of reaction torque-based control of a redundant free-floating space robot*, **Chin. J. Aeronaut.** | `10.1016/j.cja.2017.03.010` ⚠ | 【推导】证明**反作用力矩零空间与 RNS 等价**，并把反作用力矩作为优化指标嵌入 GJM 笛卡尔轨迹跟踪。这是你把两张杀手图统一到一个框架下的关键桥梁 |
| C5 | Nenchev D.N., Yoshida K. (1999) *Impact analysis and post-impact motion control issues of a free-floating space robot subject to a force impulse*, **IEEE T-RA** 15(3):548–557 | `10.1109/70.768186` ⚠ | 【推导】V1→V2 的过渡。碰撞冲量如何在 GJM 框架下传播到基座 |
| C6 | Shao X., Yao W., Li X., Sun G., Wu L. (2022) *Direct trajectory optimization of free-floating space manipulator for reducing spacecraft variation*, **IEEE RA-L** 7(2):2795–2802 | `10.1109/LRA.2022.3145947` ⚠ | 【对标】RNS 的现代竞品（直接轨迹优化）。你要说明 RNS 的优势区间在哪，需要这个对照 |

> **给你的判断**：C1 + C4 是本节真正的"新料"，其余是把你已知的 Umetani/Nenchev 链条补完整。C1 建议排在最前，因为它会直接决定你 V1 代码里状态变量怎么选。

---

## 3. V2 —— 接触动力学、碰撞与阻抗控制

| # | 文献 | DOI | 用途 |
|---|---|---|---|
| K1 | Yoshida K., Nakanishi H., Ueno H., Inaba N., Nishimaki T., Oda M. (2004) *Dynamics, control and impedance matching for robotic capture of a non-cooperative satellite*, **Adv. Robot.** 18(2):175–198 | `10.1163/156855304322758015` ✔ | 【推导】**虚拟质量（virtual mass）+ 阻抗匹配**的原始定义。V2 的理论中心。捕获瞬间"末端有效惯量 vs 目标惯量"的匹配条件从这里来 |
| K2 | Uyama N., Nakanishi H., Nagaoka K., Yoshida K. (2012) *Impedance-based contact control of a free-flying space robot with a compliant wrist for non-cooperative satellite capture*, **IROS 2012**, 4477–4482 | `10.1109/IROS.2012.6386082` ✔ | 【推导】柔顺腕 + 阻抗的工程实现。你的 B601-DM 是 MIT 力矩模式，可以在关节层直接实现类似效果 |
| K3 | Uyama N., Narumi T. (2016) *Hybrid Impedance/Position Control of a Free-Flying Space Robot for Detumbling a Noncooperative Satellite*, **IFAC-PapersOnLine** 49(17):230–235 | `10.1016/j.ifacol.2016.09.040` ✔ | 【推导】捕获后消旋。是"抓住之后怎么办"的标准答案 |
| K4 | Fujii K., Rodríguez I., Schedl M., Grunwald G., Roa M.A. (2024) *Comparative analysis of robotic gripping solutions for cooperative and non-cooperative targets*, **IEEE Aerospace Conf. 2024** | `10.1109/AERO58975.2024.10520942` ✔ | 【定调】DLR 出品的末端执行器方案横评。你选夹持方案（夹爪/包络/柔性）的论证依据 |
| K5 | Gilardi G., Sharf I. (2002) *Literature survey of contact dynamics modelling*, **Mech. Mach. Theory** 37(10):1213–1239 | `10.1016/S0094-114X(02)00045-9` ⚠ | 【推导】接触力模型（Hertz / Hunt-Crossley / 恢复系数）的选型依据。Isaac Sim 里调接触参数前必读 |
| K6 | *Emerging strategies in close proximity operations for space debris removal: A review*, **Acta Astronaut.** (2024) | ScienceDirect S0094576524007665 ⚠ | 【定调】软体/柔顺捕获机构的最新综述。**与你的超材料柔性臂杆概念直接呼应**，是把 V3 卖点接到 V2 场景上的桥 |

---

## 4. V3 —— 柔性臂杆、ANCF 与超材料

这一层是你三个创新点里**文献支撑最薄**的，需要拼装：ANCF 理论（成熟）+ 空间柔性臂控制（成熟）+ 超材料点阵（成熟但几乎没人用在空间机械臂上）。**这个空白正是你的创新点，但报告里必须诚实地把它写成"交叉迁移"而不是"已有方向"。**

| # | 文献 | DOI | 用途 |
|---|---|---|---|
| F1 | Gerstmayr J., Sugiyama H., Mikkola A. (2013) *Review on the Absolute Nodal Coordinate Formulation for Large Deformation Analysis of Multibody Systems*, **ASME J. Comput. Nonlinear Dyn.** 8(3):031016 | `10.1115/1.4023487` ⚠ | 【定调】ANCF 权威综述。单元族谱、锁死问题、与浮动坐标法的取舍 |
| F2 | Gerstmayr J., Irschik H. (2008) *On the correct representation of bending and axial deformation in the ANCF with an elastic line approach*, **J. Sound Vib.** 318(3):461–487 | `10.1016/j.jsv.2008.04.019` ✔ | 【推导】ANCF 梁单元弯曲/轴向解耦的正确做法。你用 ETBM 就绕不开这篇 |
| F3 | Shabana A.A. (2015) *Definition of ANCF Finite Elements*, **ASME J. Comput. Nonlinear Dyn.** 10(5):054506 | `10.1115/1.4030369` ⚠ | 【推导】判定"什么才算 ANCF 单元"的规范。防止你实现出一个自称 ANCF 实则不满足条件的单元 |
| F4 | Gerstmayr J. (2023) *Exudyn – a C++-based Python package for flexible multibody systems*, **Multibody Syst. Dyn.** | `10.1007/s11044-023-09937-1` ✔ | 【推导+A 级代码】配套开源库的架构论文。见 §9 |
| F5 | Tayebi J., Chen T., Wu X., Mishra A.K. (2025) *Editorial: Advancements in vibration control for space manipulators: actuators, algorithms, and material innovations*, **Front. Robot. AI** | `10.3389/frobt.2025.1681168` ✔ | 【定调】**整个 Research Topic 就是你 V3 的主题**（空间机械臂 + 振动控制 + 智能材料 + 柔性夹持）。顺着这篇的引文表把整个专题拉下来 |
| F6 | Ma X. et al. (2025) *Multi-Physical Lattice Metamaterials Enabled by Additive Manufacturing: Design Principles, Interaction Mechanisms, and Multifunctional Applications*, **Adv. Sci.** 12:2405835 | `10.1002/advs.202405835` ✔ | 【定调】点阵超材料的设计原理综述（含带隙/减振/轻量化的耦合机制）。你论证"为什么点阵臂杆能同时减重和抑振"的材料侧依据 |
| F7 | 胡海岩, 田强, 文浩, 罗凯, 马小飞 (2025) *极大空间结构在轨组装的动力学与控制*, **力学进展** 55(1):1–29 | `10.6052/1000-0992-24-044` ✔ | 【定调+推导】多柔体系统建模、机器人规划控制、地面模拟实验五个环节。**同时覆盖你的 V3 和在轨搭建主线**，中文，写报告可直接引 |

> **缺口提示**：目前公开文献里"超材料点阵直接做空间机械臂臂杆"几乎为空白。检索时用组合词 `lattice / architected material` × `manipulator link / boom / deployable boom` × `vibration suppression`，并把 F5 专题的全部投稿过一遍——那里最可能出现最接近的工作。

---

## 5. V4 —— 具身智能：VLA 与空间感知

| # | 资源 | 标识 | 用途 |
|---|---|---|---|
| V1 | **SpaceMind: A Modular and Self-Evolving Embodied Vision-Language Agent Framework for Autonomous On-orbit Servicing** (2026) | arXiv `2604.14399` ✔ | 【对标 · 最高优先】**与你的选题撞得最近的一篇**。模块化 VLM 智能体 + MCP 工具层 + 技能自演化，在 UE5 仿真与物理实验室双环境跑了 192 次闭环，含退化工况。你必须读它、引它，并明确说清你的 VLA 路线（端到端动作生成）与它的智能体路线（技能调度）差在哪 |
| V2 | Kawaharazuka K., Oh J., Yamada J., Posner I., Zhu Y. (2025) *Vision-Language-Action Models for Robotics: A Review Towards Real-World Applications*, **IEEE Access** 13:162467–162504 | `10.1109/ACCESS.2025.3609980` ✔ | 【定调】最新的 VLA 落地导向综述。比纯学术 survey 更贴你的工程需求 |
| V3 | Ma Y., Song Z., Zhuang Y., Hao J., King I. (2024) *A Survey on Vision-Language-Action Models for Embodied AI* | arXiv `2405.14093` ✔ | 【定调】VLA 分类学的标准引用 |
| V4 | Kim M.J. et al. (2024) *OpenVLA: An Open-Source Vision-Language-Action Model* | arXiv `2406.09246` ✔ | 【推导+B 级代码】你用 Wall-X，但 OpenVLA 的 LoRA 微调配方、动作离散化、OFT 加速方案是公共参考系 |
| V5 | Rodriguez-Fernandez V. et al. (2024) *Language Models are Spacecraft Operators* | arXiv `2404.00413` ✔ | 【对标】LLM 直接当航天器操作员的早期工作，Kelvins 竞赛背景 |
| V6 | Carrasco A. et al. (2025) *Visual Language Models as Operator Agents in the Space Domain*, **AIAA SciTech 2025**, 1543 | ⚠ | 【对标】V5 的视觉版续作 |
| V7 | Park T.H., Märtens M., Lecuyer G., Izzo D., D'Amico S. (2021) *SPEED+: Next-Generation Dataset for Spacecraft Pose Estimation across Domain Gap* | arXiv `2110.03101` ✔ | 【A 级数据集】见 §9。你的位姿感知模块的**标准 benchmark**，不用它评审会问 |
| V8 | *Visual Servoing for Robotic On-Orbit Servicing: A Survey* (2024) | arXiv `2409.02324` ✔ | 【定调】视觉伺服在 OOS 的综述。把感知接到控制的那一段 |
| V9 | Orsula A. et al. (2025) *Space Robotics Bench: Robot Learning Beyond Earth* | arXiv `2509.23328` ✔ | 【A 级代码 + 对标】Isaac Sim 上的空间机器人学习基准，含 RL 基线与 sim-to-real 案例研究 |

---

## 6. 在轨搭建（组装）专线

| # | 文献 | DOI | 用途 |
|---|---|---|---|
| A1 | Li D. et al. (2022) *A Survey of Space Robotic Technologies for On-Orbit Assembly*, **Space Sci. Technol.** 2022:9849170 | `10.34133/2022/9849170` ✔ | 【定调】装配序列规划 + 运动规划 + 振动抑制 + 柔顺装配 + 地面验证的全景。**在轨搭建主线的第一引用**，CC-BY 开放获取 |
| A2 | 胡海岩 et al. (2025) 力学进展 55(1):1–29 | `10.6052/1000-0992-24-044` ✔ | 见 F7。百米级天线在轨组装的动力学与控制，含 NASA 水下装配、PULSAR、气浮台、ETS-VIII 悬吊卸载四类地面验证对比图 |
| A3 | Mulsow N., Dąbrowski K., Mallwitz M. et al. (2024) 可重构工具系统 for OSAM | ⚠ | 【对标】装配任务多样性 → 工具自重构。你如果要一臂多任务（清除 + 搭建），这是论证依据 |
| A4 | ESA CAT-IOD 任务（2024–2026）：CAT 捕获技术 + D4R 接口 + 合作/非合作双场景 | ESA Clean Space 博客 | 【对标】最新的在轨捕获技术验证任务时间线（2026 达 TRL 7）。你的任务设计成熟度对标它 |
| A5 | 关键词专线（自行续检索）：`robotic in-orbit assembly of large aperture space telescope (LAST)`、`PULSAR project`、`Archinaut / SPIDER / OSAM-1`、`modular self-assembling truss` | — | 在轨搭建的具体工程案例库 |

---

## 7. 平台级：星本体设计（比赛要求的整器设计）

| # | 资源 | 标识 | 用途 |
|---|---|---|---|
| P1 | Cubot（沈阳自动化所） | `10.34133/2022/9894604` | 你已有。CubeSat 尺度臂-基座惯量比方案的直接对标 |
| P2 | Kenneally P.W., Piggott S., Schaub H. (2020) *Basilisk: A Flexible, Scalable and Modular Astrodynamics Simulation Framework*, **J. Aerosp. Inf. Syst.** 17 | `10.2514/1.I010762` ✔ | 【推导+A 级代码】星平台动力学/GNC 框架论文。做整器姿控、反作用轮/磁力矩器建模、轨道摄动 |
| P3 | Forshaw J.L. et al. (2016) *RemoveDEBRIS: An in-orbit active debris removal demonstration mission*, **Acta Astronaut.** 127:448–463 | `10.1016/j.actaastro.2016.06.018` ⚠ | 【对标】已飞的 ADR 任务全器设计（网捕 + 鱼叉 + 视觉导航 + 阻力帆） |
| P4 | Biesbroek R. et al. (2021) *The ClearSpace-1 mission: ESA and ClearSpace team up to remove debris*, 8th Eur. Conf. Space Debris | — | 【对标】四臂抓捕构型 + 95 kg PROBA-1 目标，2029 演示。构型选择的反例/正例 |
| P5 | Al Ali A., Beigomi B., Zhu Z.H. (2024) *Development of 6DOF Hardware-in-the-Loop Ground Testbed for Autonomous Robotic Space Debris Removal*, **Aerospace** 11(11):877 | `10.3390/aerospace11110877` ✔ | 【对标】地面验证平台设计（主动重力补偿 + 双工业臂 + 力/触觉传感）。**你的 B601-DM 地面验证台的论证参照** |

---

## 8. 中文文献（写中文报告直引）

| # | 文献 | DOI |
|---|---|---|
| Z1 | 丁希仑, 陈一同, 王成才, 徐坤 (2025) *空间机器人操作技术研究现状与展望*, **航空学报** 46(6):531556 | `10.7527/S1000-6893.2024.31556` ✔ |
| Z2 | 刘宏, 刘冬雨, 蒋再男 (2021) *空间机械臂技术综述及展望*, **航空学报** 42(1):524164 | `10.7527/S1000-6893.2020.24164` ✔ |
| Z3 | *面向航天器自主维护的空间机器人发展战略研究*, **中国工程科学** (2024) | `10.15302/J-SSCAE-2024.01.014` ✔ |
| Z4 | 胡海岩 et al. (2025) *极大空间结构在轨组装的动力学与控制*, **力学进展** 55(1):1–29 | `10.6052/1000-0992-24-044` ✔ |
| Z5 | *空间机械臂操作子系统设计与实现*, **空间科学学报** 44(5):939–947 (2024) | `10.11728/cjss2024.05.2023-0081` ✔ |

> Z1 覆盖"视觉感知 / 刚柔耦合建模 / 规划控制 / 人机协同"四层，与你四个技术模块一一对应；Z2 是天宫/空间站机械臂的官方口径，写国内现状必引。

---

## 9. 开源代码与数据集

### 9.1 自由漂浮基座动力学（V1 直接命中）

| 等级 | 仓库 | 说明 |
|---|---|---|
| **A** | `NPS-SRL/SPART` | MATLAB/Simulink 浮动基多体建模控制工具箱，**支持 URDF 导入**，直接算 GIM/CIM、几何雅可比及其导数、浮动基正逆动力学，支持符号计算与代码生成。你的 `reBot-DevArm_fixend.urdf` 可以直接喂进去，与 Pinocchio 结果交叉验证 |
| **A** | `Space-Robotics-Laboratory/SpaceDyn` | Yoshida 实验室原版（东北大）MATLAB/C++ 库。**GJM 与 RNS 的"权威参考实现"**。SPART 与 Pinocchio 对不上时，以它为裁决基准 |
| **B** | GitHub topic `space-robotics` 下的 Python 版 SpaceDyn（东北大移植，WIP） | Python 生态更贴你的工具链，但 WIP 状态，读代码为主 |
| **A** | `stack-of-tasks/pinocchio` | 你已在用。V1 关键：`JointModelFreeFlyer` 建自由漂浮基座，配合动量守恒约束求 GJM |

### 9.2 空间机器人学习/仿真环境（V4 与杀手图）

| 等级 | 仓库 | 说明 |
|---|---|---|
| **A** | `Tsinghua-Space-Robot-Learning-Group/SpaceRobotEnv` | MuJoCo 自由漂浮空间机器人 Gym 环境，**含双臂捕获任务、图像观测、基座-臂耦合扰动**。你做 RL/VLA 基线对比最省事的起点 |
| **A** | `AndrejOrsula/space_robotics_bench` | Isaac Sim / Isaac Lab 上的空间机器人基准，含 RL 基线、泛化与 sim-to-real 案例。与你的 Isaac Sim 路线同栈 |
| **A** | `isaac-30_simulation/IsaacLab` + `isaac-30_simulation/IsaacSim` | 你的主仿真栈。Isaac Sim 已开源；Isaac Lab 支持 RSL-RL / skrl / rl_games / SB3 |
| **B** | `nasa/astrobee` + `nasa/astrobee_media` | ISS 自由飞行器**全栈飞行软件**（视觉定位、自主导航、对接栖靠）+ Gazebo 仿真。不是机械臂，但"自由飞行基座 + 感知 + 自主"的完整工程范例，含栖靠臂模型 |

### 9.3 柔性多体 / ANCF（V3）

| 等级 | 仓库 | 说明 |
|---|---|---|
| **A** | `jgerstmayr/EXUDYN` | C++ 核 + Python 接口，**原生 ANCF 梁/板单元**、隐式/显式积分、特征值分析、FFRF 模态缩减。`pip install exudyn`。V3 刚柔耦合的首选 |
| **B** | `projectchrono/chrono` | C++ 多物理场，ANCF + 接触 + 颗粒。要做"柔性臂 + 接触捕获"耦合（V2×V3）时它比 Exudyn 强，但接入成本高 |
| **C** | MBDyn | 气动弹性传统强，ANCF 支持一般，仅作交叉验证 |

### 9.4 感知与数据集（V4）

| 等级 | 资源 | 说明 |
|---|---|---|
| **A** | **SPEED+**（Stanford SLAB，Stanford Digital Repository `purl.stanford.edu/wv398fc4383`） | 6 万张合成 + 9531 张 TRON 硬件在环图像，Tango 星模型，专攻**域间隙**。lightbox / sunlamp 两域无标注，专用于测鲁棒性 |
| **A** | **SPEED**（`purl.stanford.edu/dz692fn7184`） | SPEED+ 的前代，SPEC2019 用 |
| **B** | **SHIRT** | SPEED+ 的序列版（交会轨迹 ROE1/ROE2），做位姿跟踪而非单帧估计 |
| **B** | ESA Kelvins 竞赛页 `kelvins.esa.int/satellite-pose-estimation-challenge` | 评测协议与排行榜基线，写指标对比时引 |
| **C** | URSO（Soyuz/Dragon 合成数据集）、大规模非合作空间目标感知基准（**Sci. Data** 2025，含检测/识别/部件分割标注） | 补充域，做部件级分割（抓捕点选择）时有用 |

### 9.5 VLA（V4）

| 等级 | 仓库 | 说明 |
|---|---|---|
| **A** | `huggingface/lerobot` | 你已在用其数据格式。π0 / π0-FAST / SmolVLA 已并入 |
| **B** | `openvla/openvla` | LoRA 微调配方 + OFT 加速（推理快 25–50×，支持多图输入与高频双臂控制）。Wall-X 微调策略可直接借鉴 |
| **B** | `Physical-Intelligence/openpi` | π0 / π0-FAST / π0.5 的开源训练管线与 LIBERO 微调配置 |
| **C** | `NVIDIA GR00T N1` (arXiv `2503.14734`) | 双系统架构（慢 VLA 主干 2–5 Hz + 快扩散动作头）。你若要论证"决策慢/控制快"的分层，是标准引用 |

### 9.6 星平台与轨道（比赛整器设计）

| 等级 | 仓库 | 说明 |
|---|---|---|
| **A** | `AVSLab/basilisk` (`avslab.github.io/basilisk`) | Python 包 C/C++ 核，耦合轨道+姿态、结构挠性、不平衡动量交换装置、燃料晃动。ISC 许可 |
| **B** | Orekit / Tudat / GMAT | 轨道动力学与任务分析。做离轨、共面/异面转移预算时用 |
| **C** | NASA `42`（GSFC，多刚/柔体多航天器姿轨仿真） | Basilisk 的替代品，风格更老派 |

---

## 10. 继续检索的策略

1. **引文滚雪球优先于关键词**：S1（Rybus 2024）和 A1（Li 2022）的参考文献表本身就是两份精选书目，比再检索十次有效。
2. **锁定期刊**：`Progress in Aerospace Sciences` / `Acta Astronautica` / `Advances in Space Research` / `IEEE T-RO` / `Multibody System Dynamics` / `航空学报` / `力学进展`。
3. **锁定作者**：Yoshida K.（GJM/RNS/阻抗匹配）、Nenchev D.（RNS）、Papadopoulos E.（自由漂浮规划）、Zhu Z.H.（ADR + 地面验证台）、黄攀峰（绳系/双臂捕获）、Gerstmayr J.（ANCF/Exudyn）、胡海岩/田强（刚柔耦合 + 在轨组装）。
4. **组合关键词（V3 空白区专用）**：`architected/lattice material` × `manipulator link | deployable boom` × `vibration suppression | bandgap`；`metamaterial` × `space robot`。
5. **设订阅**：arXiv `cs.RO` + `eess.SY`，关键词告警 `free-floating space robot`、`on-orbit servicing`、`in-space assembly`、`spacecraft pose estimation`。距 9 月 1 日截止还有约 6 周，每周一次告警足够。
6. **付费墙处理**：用东京大学图书馆的机构订阅（Elsevier / IEEE / Springer / Wiley 都在）。中文文献走知网/万方，或作者主页/ResearchGate 的作者自存档版。**不要用非法镜像站——比赛报告的参考文献可溯源性会被查。**

---

## 11. 本地归档 Prompt（喂给 Codex / Claude Code）

> 直接复制以下整段。它按你现有仓库纪律写（先只读盘点、不重做既有产物、二进制不入库、输出裁决态）。

````text
# 任务：空间具身智能机械臂项目——文献与开源资料本地归档（LIT-00）

## 最高真值协议（先读盘，不重做）
1. 先用只读工具盘点仓库：`git status`、`ls docs/`、`ls 10_research/`、`ls 80_third_party/vendor/`。
   若已存在 `50_literature/references/` 或 `10_research/literature/` 及其 manifest，**读取其状态标记后只补差集，绝不重做已完成条目**。
2. 本任务默认 `EXECUTE`（允许写文件），但**禁止**：删除任何已有科学工件、修改冻结区、提交二进制。
3. 完成后输出裁决态之一：`LIT_ARCHIVE_COMPLETE` / `LIT_ARCHIVE_PARTIAL_WITH_PAYWALL_BLOCKERS` / `LIT_ARCHIVE_BLOCKED`。

## 目录约定
50_literature/references/
├── manifest.yaml          # 单一真值源（SSOT），下面给了种子内容
├── refs.bib               # 由 manifest 生成，可直接 \bibliography
├── README.md              # 人读索引：按 V0–V4 分组，每条含"读什么/为什么/对应哪张图"
├── paywalled_todo.md      # 需机构权限手动下载的清单（含 DOI 直链）
└── download_report.md     # 本次执行报告：成功/失败/跳过，逐条原因
50_literature/pdf/                       # 全部 PDF 落这里，**加入 .gitignore，不入库**
80_third_party/vendor/                    # 开源仓库克隆点，已 gitignore（沿用现状）

## 硬约束
- **PDF、模型权重、数据集一律不进 git**。执行前确认 `.gitignore` 含 `50_literature/pdf/`、`80_third_party/vendor/`、`*.pdf`、`data/datasets/`；缺则补上。
- **只提交** `manifest.yaml`、`refs.bib`、`README.md`、`paywalled_todo.md`、`download_report.md`、`.gitignore` 变更。
- **不得绕过付费墙**：仅允许从 arXiv、作者主页、机构仓储（如 Stanford Digital Repository）、开放获取期刊（MDPI / Frontiers / Space: Science & Technology / 中国工程科学）、NASA NTRS 直接下载。命中 Elsevier / IEEE / Springer / Wiley / 知网 的条目，**只记录 DOI 与 landing page URL 到 `paywalled_todo.md`，不尝试下载**。
- **DOI 逐条校验**：对每个 DOI 调 `https://api.crossref.org/works/{doi}`，比对返回标题与 manifest 中标题。不匹配则在 manifest 打 `doi_status: MISMATCH` 并把 Crossref 返回的标题记进备注，**不要擅自替换 DOI**，留给我裁决。
- **克隆仓库用 `--depth 1`**，除非条目显式标 `full_history: true`。克隆后记录 commit SHA 到 manifest 的 `pinned_sha` 字段（可复现性要求）。
- 每条产物必须能回答"为什么在这里"：README 里每条至少一句用途说明，禁止只列标题。

## 执行步骤
1. 盘点（只读），报告已存在什么。
2. 写 `manifest.yaml`（种子内容见下，缺字段补全）。
3. Crossref 校验全部 DOI，回写 `doi_status`。
4. 下载开放获取 PDF 到 `50_literature/pdf/{category}/{key}.pdf`；失败重试一次后记 `FAILED` 并写明原因（403/404/超时）。
5. 克隆开源仓库到 `80_third_party/vendor/{name}`，记录 `pinned_sha`。**只克隆，不安装、不编译、不运行**。
6. 由 manifest 生成 `refs.bib`（BibTeX，key 用 `姓氏年份关键词` 格式）。
7. 生成 `README.md`：按 §V1/V2/V3/V4/在轨组装/平台/中文 分组，标注 A/B/C 等级与"定调/推导/对标"读法。
8. 生成 `paywalled_todo.md`：表格含 标题 / DOI / 期刊 / 直链 / 优先级。
9. 生成 `download_report.md`：成功 N 条、付费墙 N 条、失败 N 条、跳过（已存在）N 条。
10. `git add` 仅上述文本产物 → 单次提交，message 用 `docs(refs): 建立文献与开源资料索引 LIT-00`。
11. 输出裁决态与"需要我决定的事"清单。

## manifest.yaml 种子（补全其余字段）
```yaml
version: 1
generated: 2026-07-21
categories: [survey, gjm_rns, contact_capture, flexible_ancf, embodied_vla, on_orbit_assembly, platform, chinese, oss, dataset]

papers:
  # ---- 定调综述 ----
  - key: rybus2024manipulators
    title: "Robotic manipulators for in-orbit servicing and active debris removal: Review and comparison"
    venue: "Progress in Aerospace Sciences 151:101055"
    year: 2024
    doi: 10.1016/j.paerosci.2024.101055
    category: survey
    access: paywalled
    priority: P0
    note: "臂本体参数选型的横评表来源"
  - key: papadopoulos2021survey
    title: "Robotic manipulation and capture in space: A survey"
    venue: "Frontiers in Robotics and AI 8:686723"
    year: 2021
    doi: 10.3389/frobt.2021.686723
    category: survey
    access: open
    priority: P0
  - key: alizadeh2024comprehensive
    title: "A comprehensive survey of space robotic manipulators for on-orbit servicing"
    venue: "Frontiers in Robotics and AI 11:1470950"
    year: 2024
    doi: 10.3389/frobt.2024.1470950
    category: survey
    access: open
    priority: P1
  - key: sst2024autonomous
    title: "Review of Autonomous Space Robotic Manipulators for On-Orbit Servicing and Active Debris Removal"
    venue: "Space: Science & Technology"
    doi: 10.34133/space.0291
    category: survey
    access: open
    priority: P1
  - key: zhang2022adcr
    title: "Review of On-Orbit Robotic Arm Active Debris Capture Removal Methods"
    venue: "Aerospace 10(1):13"
    year: 2022
    doi: 10.3390/aerospace10010013
    category: survey
    access: open
    priority: P2
  - key: ellery2019tutorial
    title: "Tutorial Review on Space Manipulators for Space Debris Mitigation"
    venue: "Robotics 8(2):34"
    year: 2019
    doi: 10.3390/robotics8020034
    category: survey
    access: open
    priority: P2

  # ---- V1 GJM / RNS ----
  - key: wilde2018tutorial
    title: "Equations of Motion of Free-Floating Spacecraft-Manipulator Systems: An Engineer's Tutorial"
    venue: "Frontiers in Robotics and AI 5:41"
    year: 2018
    doi: 10.3389/frobt.2018.00041
    category: gjm_rns
    access: open
    priority: P0
    note: "V1 理论章节骨架；VM/DEM/GJM 三路线并列"
  - key: yoshida2001zrm
    title: "Zero Reaction Maneuver: Flight Validation with ETS-VII Space Robot and Extension to Kinematically Redundant Arm"
    venue: "ICRA 2001, 441-446"
    year: 2001
    doi: 10.1109/ROBOT.2001.932589
    doi_status: UNVERIFIED
    category: gjm_rns
    access: paywalled
    priority: P0
    note: "RNS 在轨飞行验证；杀手图基线。作者主页可能有 PDF: astro.mech.tohoku.ac.jp/~yoshida/"
  - key: xu2017reactiontorque
    title: "Analysis of reaction torque-based control of a redundant free-floating space robot"
    venue: "Chinese Journal of Aeronautics"
    year: 2017
    doi_status: UNVERIFIED
    category: gjm_rns
    access: open
    priority: P0
    note: "证明反作用力矩零空间 == RNS；统一两张杀手图的桥梁"
  - key: nenchev1999impact
    title: "Impact analysis and post-impact motion control issues of a free-floating space robot subject to a force impulse"
    venue: "IEEE T-RA 15(3):548-557"
    year: 1999
    doi: 10.1109/70.768186
    doi_status: UNVERIFIED
    category: gjm_rns
    access: paywalled
    priority: P1

  # ---- V2 接触与捕获 ----
  - key: yoshida2004impedance
    title: "Dynamics, control and impedance matching for robotic capture of a non-cooperative satellite"
    venue: "Advanced Robotics 18(2):175-198"
    year: 2004
    doi: 10.1163/156855304322758015
    category: contact_capture
    access: paywalled
    priority: P0
  - key: uyama2012compliantwrist
    title: "Impedance-based contact control of a free-flying space robot with a compliant wrist for non-cooperative satellite capture"
    venue: "IROS 2012, 4477-4482"
    year: 2012
    doi: 10.1109/IROS.2012.6386082
    category: contact_capture
    access: paywalled
    priority: P1
  - key: uyama2016hybrid
    title: "Hybrid Impedance/Position Control of a Free-Flying Space Robot for Detumbling a Noncooperative Satellite"
    venue: "IFAC-PapersOnLine 49(17):230-235"
    year: 2016
    doi: 10.1016/j.ifacol.2016.09.040
    category: contact_capture
    access: open
    priority: P1
  - key: fujii2024gripping
    title: "Comparative analysis of robotic gripping solutions for cooperative and non-cooperative targets"
    venue: "IEEE Aerospace Conference 2024"
    year: 2024
    doi: 10.1109/AERO58975.2024.10520942
    category: contact_capture
    access: paywalled
    priority: P1

  # ---- V3 柔性 / ANCF / 超材料 ----
  - key: gerstmayr2013ancfreview
    title: "Review on the Absolute Nodal Coordinate Formulation for Large Deformation Analysis of Multibody Systems"
    venue: "ASME J. Comput. Nonlinear Dyn. 8(3):031016"
    year: 2013
    doi: 10.1115/1.4023487
    doi_status: UNVERIFIED
    category: flexible_ancf
    access: paywalled
    priority: P0
  - key: gerstmayr2008elasticline
    title: "On the correct representation of bending and axial deformation in the absolute nodal coordinate formulation with an elastic line approach"
    venue: "J. Sound Vib. 318(3):461-487"
    year: 2008
    doi: 10.1016/j.jsv.2008.04.019
    category: flexible_ancf
    access: paywalled
    priority: P0
  - key: gerstmayr2023exudyn
    title: "Exudyn - a C++-based Python package for flexible multibody systems"
    venue: "Multibody System Dynamics"
    year: 2023
    doi: 10.1007/s11044-023-09937-1
    category: flexible_ancf
    access: paywalled
    priority: P1
  - key: tayebi2025vibrationeditorial
    title: "Editorial: Advancements in vibration control for space manipulators: actuators, algorithms, and material innovations"
    venue: "Frontiers in Robotics and AI"
    year: 2025
    doi: 10.3389/frobt.2025.1681168
    category: flexible_ancf
    access: open
    priority: P0
    note: "顺其引文表把整个 Research Topic 全部拉下来 —— 这是 V3 最近的邻域"
  - key: ma2025latticemeta
    title: "Multi-Physical Lattice Metamaterials Enabled by Additive Manufacturing"
    venue: "Advanced Science 12:2405835"
    year: 2025
    doi: 10.1002/advs.202405835
    category: flexible_ancf
    access: open
    priority: P1

  # ---- V4 具身智能 ----
  - key: spacemind2026
    title: "SpaceMind: A Modular and Self-Evolving Embodied Vision-Language Agent Framework for Autonomous On-orbit Servicing"
    venue: "arXiv"
    year: 2026
    arxiv: "2604.14399"
    category: embodied_vla
    access: open
    priority: P0
    note: "与本课题选题最接近的公开工作；必须读透并在报告中区分路线差异"
  - key: kawaharazuka2025vlareview
    title: "Vision-Language-Action Models for Robotics: A Review Towards Real-World Applications"
    venue: "IEEE Access 13:162467-162504"
    year: 2025
    doi: 10.1109/ACCESS.2025.3609980
    category: embodied_vla
    access: open
    priority: P0
  - key: ma2024vlasurvey
    title: "A Survey on Vision-Language-Action Models for Embodied AI"
    arxiv: "2405.14093"
    year: 2024
    category: embodied_vla
    access: open
    priority: P1
  - key: kim2024openvla
    title: "OpenVLA: An Open-Source Vision-Language-Action Model"
    arxiv: "2406.09246"
    year: 2024
    category: embodied_vla
    access: open
    priority: P1
  - key: rodriguez2024lmspacecraft
    title: "Language Models are Spacecraft Operators"
    arxiv: "2404.00413"
    year: 2024
    category: embodied_vla
    access: open
    priority: P2
  - key: park2021speedplus
    title: "SPEED+: Next-Generation Dataset for Spacecraft Pose Estimation across Domain Gap"
    arxiv: "2110.03101"
    year: 2021
    category: embodied_vla
    access: open
    priority: P0
  - key: orsula2025srb
    title: "Space Robotics Bench: Robot Learning Beyond Earth"
    arxiv: "2509.23328"
    year: 2025
    category: embodied_vla
    access: open
    priority: P0
  - key: visualservoing2024survey
    title: "Visual Servoing for Robotic On-Orbit Servicing: A Survey"
    arxiv: "2409.02324"
    year: 2024
    category: embodied_vla
    access: open
    priority: P1

  # ---- 在轨组装 ----
  - key: li2022assemblysurvey
    title: "A Survey of Space Robotic Technologies for On-Orbit Assembly"
    venue: "Space: Science & Technology 2022:9849170"
    year: 2022
    doi: 10.34133/2022/9849170
    category: on_orbit_assembly
    access: open
    priority: P0
  - key: hu2025ultralarge
    title: "极大空间结构在轨组装的动力学与控制"
    venue: "力学进展 55(1):1-29"
    year: 2025
    doi: 10.6052/1000-0992-24-044
    category: on_orbit_assembly
    access: open
    priority: P0

  # ---- 平台 ----
  - key: kenneally2020basilisk
    title: "Basilisk: A Flexible, Scalable and Modular Astrodynamics Simulation Framework"
    venue: "J. Aerospace Information Systems 17"
    year: 2020
    doi: 10.2514/1.I010762
    category: platform
    access: paywalled
    priority: P1
  - key: alali2024hiltestbed
    title: "Development of 6DOF Hardware-in-the-Loop Ground Testbed for Autonomous Robotic Space Debris Removal"
    venue: "Aerospace 11(11):877"
    year: 2024
    doi: 10.3390/aerospace11110877
    category: platform
    access: open
    priority: P1

  # ---- 中文 ----
  - key: ding2025spacerobotops
    title: "空间机器人操作技术研究现状与展望"
    venue: "航空学报 46(6):531556"
    year: 2025
    doi: 10.7527/S1000-6893.2024.31556
    category: chinese
    access: open
    priority: P0
  - key: liu2021spacemanipulator
    title: "空间机械臂技术综述及展望"
    venue: "航空学报 42(1):524164"
    year: 2021
    doi: 10.7527/S1000-6893.2020.24164
    category: chinese
    access: open
    priority: P0
  - key: sscae2024strategy
    title: "面向航天器自主维护的空间机器人发展战略研究"
    venue: "中国工程科学"
    year: 2024
    doi: 10.15302/J-SSCAE-2024.01.014
    category: chinese
    access: open
    priority: P1

repos:
  - name: SPART
    url: https://github.com/NPS-SRL/SPART
    grade: A
    use: "浮动基 GJM/GIM/CIM，支持 URDF 导入；与 Pinocchio 交叉验证 V1 模型"
  - name: SpaceDyn
    url: https://github.com/Space-Robotics-Laboratory/SpaceDyn
    grade: A
    use: "Yoshida 实验室原版；GJM/RNS 的权威参考实现，作为结果裁决基准"
  - name: SpaceRobotEnv
    url: https://github.com/Tsinghua-Space-Robot-Learning-Group/SpaceRobotEnv
    grade: A
    use: "MuJoCo 自由漂浮空间机器人 Gym 环境，含双臂捕获与图像观测"
  - name: space_robotics_bench
    url: https://github.com/AndrejOrsula/space_robotics_bench
    grade: A
    use: "Isaac Sim/Isaac Lab 空间机器人基准与 RL 基线"
  - name: EXUDYN
    url: https://github.com/jgerstmayr/EXUDYN
    grade: A
    use: "ANCF 柔性多体（V3 核心）；pip 亦可安装"
  - name: basilisk
    url: https://github.com/AVSLab/basilisk
    grade: A
    use: "星平台轨道+姿态耦合动力学与 GNC（比赛整器设计）"
  - name: astrobee
    url: https://github.com/nasa/astrobee
    grade: B
    use: "自由飞行器全栈飞行软件与 Gazebo 仿真范例"
  - name: chrono
    url: https://github.com/projectchrono/chrono
    grade: B
    use: "ANCF + 接触耦合（V2×V3 交叉时启用）"
  - name: openvla
    url: https://github.com/openvla/openvla
    grade: B
    use: "LoRA/OFT 微调配方参考（对照 Wall-X 策略）"
  - name: openpi
    url: https://github.com/Physical-Intelligence/openpi
    grade: B
    use: "π0/π0-FAST 开源训练管线"

datasets:
  - name: SPEED+
    url: https://purl.stanford.edu/wv398fc4383
    grade: A
    note: "体积大，先只记录 URL 与获取方式，**不要自动下载**，等我确认磁盘配额"
  - name: SPEED
    url: https://purl.stanford.edu/dz692fn7184
    grade: A
    note: "同上，仅登记"
```

## 完成后必须回答
- 每个 `doi_status: MISMATCH` 的条目，Crossref 返回的标题是什么？
- `paywalled_todo.md` 里 P0 优先级有几条？（我用东大图书馆权限手动取）
- 有没有条目在仓库里已经存在（避免重复）？
````

---

## 附：给你的三点判断

1. **SpaceMind（arXiv 2604.14399）是本次检索最重要的发现**，它和你的选题几乎正面撞上。好消息是它走的是"VLM 智能体 + 技能调度 + MCP 工具层"，而你走的是"VLA 端到端动作生成 + GJM/RNS 底层控制"——分工不同，可以引它作为最新工作并说明差异。**但报告里必须主动提它**，否则评委查到会认为你不了解前沿。

2. **V3 是三个创新点里学术支撑最薄的一环**。ANCF 成熟、空间柔性臂控制成熟、点阵超材料成熟，但"超材料点阵臂杆用于空间机械臂"基本是空白。这既是机会也是风险：报告里建议明确写成"跨领域迁移"，并用 F5 那个 Frontiers 专题 + F6 的点阵综述搭起论证链，而不是假装这是已有研究方向。

3. **在轨搭建这条新主线，A1 + A2（含中文）已经足够支撑报告一章**，不需要再大规模检索。真正缺的是**装配序列规划**的具体算法文献——那个方向可以等你 ASM-00 接口资格化做完、明确了模块化接口形式之后再定向检索，现在检索会发散。
