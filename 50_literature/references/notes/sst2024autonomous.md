# sst2024autonomous — Review of Autonomous Space Robotic Manipulators for On-Orbit Servicing and Active Debris Removal
- DOI/arXiv：10.34133/space.0291 ｜ 类别：survey ｜ 等级：B ｜ 读法：定调
- 本地：50_literature/pdf/01_survey/sst2024autonomous.pdf（23 页）

## 一句话结论
自主捕获应按自由飞行模式和捕获前后阶段分别设计与验证。

## 与本项目的挂钩
| 本项目对象 | 关系 |
|---|---|
| SIM11 / e16 | 提供捕获前规划、速度估计、接触和捕获后镇定的阶段化证据。 |
| CTRL02 | 汇总自由漂浮/自由飞行条件下的镇定和阻抗控制路线。 |
| ASM00 | 提供地面微重力模拟与 HIL 验证方式的选择框架。 |

## 可复用内容（改写，附页码指针，禁止抄录）
- 方程/推导：第 1 页把方法按 free-floating/free-flying 与 pre-/post-capture 两轴组织；我方应将 e16 状态机与 SIM11 接触模式按同样边界拆分。
- 参数/阈值：第 17 页指出 HIL 需要足够带宽和阻抗并处理硬件接触—仿真反力时延，但没有统一数值；这些量必须在 e16 本机测得。
- 图表：第 7 页表 1 对比 Canadarm1/2 捕获机构；第 13 页起的捕获后章节可作为“接触→镇定”技术路线图来源。

## 边界与不适用条件
综述中的控制器来自不同目标、抓取器和验证设施，不能直接横向比较性能；地面设施也不能完整复现轨道微重力与结构柔性。

## 不能据此声称什么
不能据此声称某自主等级已经在本项目实现，也不能把 HIL 可行性讨论等同于 e16 安全门通过。
