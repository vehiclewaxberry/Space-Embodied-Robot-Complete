# ma2025latticemeta — Multi‐Physical Lattice Metamaterials Enabled by Additive Manufacturing: Design Principles, Interaction Mechanisms, and Multifunctional Applications
- DOI/arXiv：10.1002/advs.202405835 ｜ 类别：flexible_ancf ｜ 等级：B ｜ 读法：定调
- 本地：50_literature/pdf/04_flexible_ancf/ma2025latticemeta.pdf（65 页）

## 一句话结论
点阵超材料可共设计带隙、减振和能量采集，但仍属跨域候选。

## 与本项目的挂钩
| 本项目对象 | 关系 |
|---|---|
| SIM07 | 提供等效刚度、局域共振与带隙的材料侧建模假设。 |
| e15 | 只能生成待验证材料/结构参数，不提供 ANCF 梁单元正确性或收敛判据。 |
| ASM00 | 为轻量化大结构和振动抑制提供概念候选，不构成航天适用性证明。 |

## 可复用内容（改写，附页码指针，禁止抄录）
- 方程/推导：第 17 页讨论通过预应力等参数调节有效弹性与声子带隙；我方若采用，只能先形成等效参数假设，再在 SIM07/e15 校准。
- 参数/阈值：第 39 页涉及阻尼与缺陷表征，但没有针对空间机械臂的统一数值；第 47 页的局域共振带隙与 PVDF 能量采集属于器件案例。
- 图表：第 4–5 页图 2 的 SC/BCC/FCC 点阵分类适合做材料候选图；第 47、50 页图 24 可做“隔振+能量采集”机制图。

## 边界与不适用条件
论文覆盖多物理点阵与增材制造，不是空间机械臂、极端温度/辐照或 ANCF 验证研究；PMC 副本与正式排版页码需在正式引用时核对。

## 不能据此声称什么
不能声称点阵结构已经提高本项目减振性能，也不能用材料带隙案例替代柔性臂系统级模态、强度和控制验证。
