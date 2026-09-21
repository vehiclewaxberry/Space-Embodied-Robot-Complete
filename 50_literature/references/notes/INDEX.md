# LIT-01 阅读卡索引

当前在盘 PDF：**44**；完整逐篇阅读卡：**29**；仅题录级归档：**15**。状态以 `../manifest.yaml` 为单一真值源，21 份对照见 [REORG-01-R 报告](../reorg01r_report.md)。

标记说明：**有**＝在盘文献可直接支撑该格；**弱**＝只有综述/跨域/接口级线索；**空**＝当前在盘文献没有直接支撑。`CTRL01`、`CTRL02`、`ASM00` 是文献工作流标签，不声称仓库内存在同名代码模块。

## 本周优先阅读

1. [wilde2018tutorial](./wilde2018tutorial.md)：SIM05/CTRL01 的 GJM 方程骨架。
2. [spacemind2026](./spacemind2026.md)：CTRL02/ASM00 的模块化智能体对标。
3. [papadopoulos2021survey](./papadopoulos2021survey.md)：捕获任务全阶段证据链。
4. [ellery2019tutorial](./ellery2019tutorial.md)：动量—反作用—阻抗的物理入口。
5. [alizadeh2024comprehensive](./alizadeh2024comprehensive.md)：任务代际与地面验证框架。
6. [yoshida2004impedance](./yoshida2004impedance.md)：VIM 阻抗匹配，Paper 1 接触带宽方法节直接支撑。

## V0–V4 × 项目对象交叉表

| 文献层 | SIM05 | SIM07 | SIM11 | CTRL01 | CTRL02 | e15 | e16 | ASM00 |
|---|---|---|---|---|---|---|---|---|
| V0 总体综述 | **有**：动量/GJM 总览 | **弱**：只提柔性问题 | **有**：捕获阶段与方法谱系 | **有**：RNS 入口 | **有**：阻抗/自治路线 | **空**：无 ANCF 收敛判据 | **有**：阶段与 HIL 边界 | **有**：任务与系统代际 |
| V1 GJM/RNS | **有**：Wilde+Yoshida | **有**：柔性 RNS+ZRM 抑振 | **弱**：接触点雅克比接口 | **有**：GJM/RNS 主方程 | **空**：无智能/阻抗上层 | **弱**：有柔性 RNS 原文，不替代 e15 数值门 | **弱**：捕获前扰动约束 | **空**：无装配序列证据 |
| V2 接触捕获 | **有**：冲量/阻抗原文 | **有**：柔性捕获原文 | **有**：阻抗、跟踪、同步捕获 | **有**：冲量传播与制导 | **有**：抓后消旋状态机 | **弱**：接触×柔性有文献，不替代认证 | **有**：虚拟质量/柔顺腕；阈值仍须本项目冻结 | **弱**：柔顺控制可迁移，接口序列另证 |
| V3 柔性/ANCF | **有**：柔性结构安装机械臂原文 | **有**：ANCF 梁+Exudyn+柔性 RNS | **有**：柔性目标捕获原文 | **有**：柔性 RNS 原文 | **有**：ZRM 振动抑制 | **弱**：核心原文已在盘，2013 权威综述仍缺 | **弱**：有柔性捕获响应，无本项目阈值 | **有**：柔性装配综述/架构接口 |
| V4 具身/VLA | **空**：不提供自由漂浮方程 | **空**：不提供柔性模型 | **空**：不提供接触安全律 | **空**：不提供 RNS 控制 | **有**：VLA/视觉/工具调用 | **空**：不提供求解器认证 | **弱**：位姿与视觉伺服 | **有**：长时任务/基准框架 |

### 仍为空的关键格

- **V2×SIM11、V2×CTRL02、V2×e16**：六张原文卡已补（阻抗/柔顺腕/凸引导/联合轨迹/跟踪/柔性捕获，见 V2 节）；仍不能把论文阈值直接替代本项目的接触带宽与安全 Gate。
- **V3×e15**：`gerstmayr2008elasticline`、Exudyn 与柔性 RNS/ZRM 原文已在盘；`gerstmayr2013ancfreview` 仍缺，因此 ANCF 单元族与建模取舍的权威综述来源未闭环，且文献不能替代 e15 5% 交叉求解 Gate。
- **V1×SIM07/e15**：柔性结构安装机械臂的 RNS 与 ZRM 抑振原文已在盘；后续需制作阅读卡并映射到 e15 的模型假设。
- **V4×SIM05/SIM11**：VLA/语言模型论文不提供自由漂浮动力学或接触安全证明，必须由现有 SIM 层承担。

## 逐层阅读卡

### V0 — 总体定调

- [papadopoulos2021survey](./papadopoulos2021survey.md)：建模、接近、捕获与镇定全链路。
- [alizadeh2024comprehensive](./alizadeh2024comprehensive.md)：任务代际、自治与地面验证。
- [sst2024autonomous](./sst2024autonomous.md)：自由漂浮/自由飞行与捕获前后分层。
- [zhang2022adcr](./zhang2022adcr.md)：主动碎片清除与柔性预处理方法。
- [ellery2019tutorial](./ellery2019tutorial.md)：动量、扩展雅克比和接触阻抗教程。

### V1 — 自由漂浮、GJM 与 RNS

- [wilde2018tutorial](./wilde2018tutorial.md)：完整 GJM 推导与控制算例。
- [yoshida2001zrm](./yoshida2001zrm.md)：ETS-VII RNS 飞行对标与 6R/7R 冗余边界。

### V2 — 接触捕获、阻抗与消旋

- [yoshida2004impedance](./yoshida2004impedance.md)：VIM 阻抗匹配与接触维持条件；sim_11 接触带宽动机源头。
- [uyama2012compliantwrist](./uyama2012compliantwrist.md)：柔顺腕拉长接触时间+恢复系数调参（扫描版，页码经渲染图像核对）。
- [virgilillop2019simultaneous](./virgilillop2019simultaneous.md)：捕获-消旋联合轨迹设计；design vs existence/selection 划界证据。
- [virgilillop2019convexguidance](./virgilillop2019convexguidance.md)：凸规划引导标杆（44,100 次 MC）；可行性只到算法层充分判据。
- [lampariello2018tracking](./lampariello2018tracking.md)：翻滚目标跟踪同步抓取（扫描版 OCR 核对）；e16 直接对标。
- [liu2022flexiblecapture](./liu2022flexiblecapture.md)：柔性臂+Hertz 接触捕获仿真；偏心多次碰撞与主动柔顺减冲。

### V3 — 柔性臂、ANCF 与材料候选

- [tayebi2025vibrationeditorial](./tayebi2025vibrationeditorial.md)：振动控制专题地图与验证缺口。
- [ma2025latticemeta](./ma2025latticemeta.md)：点阵带隙/减振的跨域候选，非 ANCF 认证。

### V4 — 空间具身智能、VLA 与视觉

- [spacemind2026](./spacemind2026.md)：技能、工具、推理与失败恢复。
- [kawaharazuka2025vlareview](./kawaharazuka2025vlareview.md)：VLA 全栈与真实部署约束。
- [ma2024vlasurvey](./ma2024vlasurvey.md)：组件—策略—规划 taxonomy。
- [kim2024openvla](./kim2024openvla.md)：开放 VLA 与 LoRA 适配基线。
- [rodriguez2024lmspacecraft](./rodriguez2024lmspacecraft.md)：航天器函数调用及接口失败反例。
- [park2021speedplus](./park2021speedplus.md)：航天器位姿估计 synthetic→HIL 域差。
- [orsula2025srb](./orsula2025srb.md)：空间机器人学习任务与 RL 基线。
- [visualservoing2024survey](./visualservoing2024survey.md)：PBVS/IBVS 与接近—接触视觉闭环。

## 专线补充

### ASM00 — 在轨组装

- [li2022assemblysurvey](./li2022assemblysurvey.md)：规划、柔顺、振动与地试全链路。
- [hu2025ultralarge](./hu2025ultralarge.md)：极大结构的时变构型、密模态与刚柔耦合。

### 平台/HIL

- [alali2024hiltestbed](./alali2024hiltestbed.md)：主动重力补偿双臂 6DOF HIL。

### 中文总引用

- [ding2025spacerobotops](./ding2025spacerobotops.md)：感知、建模、规划控制与协作四主线。
- [liu2021spacemanipulator](./liu2021spacemanipulator.md)：空间机械臂七项关键技术与工程脉络。
- [sscae2024strategy](./sscae2024strategy.md)：自主维护发展战略与能力边界。
