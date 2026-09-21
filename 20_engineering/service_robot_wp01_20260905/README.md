# 航天服务星与 B601：WP01 总体联合设计包

日期：2026-09-05。首候选：`WP01_ROOF_EXTERNAL_R1`。

本包已进入新机械候选的参数化设计与装配执行。工作围绕完整服务星、B601 臂和实际装配接口推进；此前只读审计用于识别可复用来源与需补设计，本包按用户本轮“现在开始”的请求实施新方案。当前阶段是 WP01 总体设计与 WP02–WP04 初案，目标是形成能继续零件化、试装和具身联调的一套共同配置。

**本候选为屋顶外置臂、连续内部设备舱的任务优先方案。母线核心尺寸初值为 366×226.3×226.3 mm；机械臂和附件使完整装配显著高于母线，不是紧凑 12U 整机，也没有标准部署器适配结论。最终数值以 `results` 和 `LAYOUT_COMPARISON` 为准。**

## 直接查看

首轮实际完成项、几何检查结果与下一轮动作汇总在 [EXECUTION_REPORT.md](EXECUTION_REPORT.md)。[交付收据](results/DELIVERY_RECEIPT.json)列出最终模型哈希及实际检查状态。

| 要了解的内容 | 入口 | 当前用途 |
|---|---|---|
| 本轮范围和交付口径 | [CAD_BRIEF.md](CAD_BRIEF.md) | 参数化总体与完整臂/附件共同设计 |
| 设计输入与明确假设 | [DESIGN_INPUTS.md](DESIGN_INPUTS.md) | 任务、硬件来源、布局和待测物理输入 |
| 唯一候选参数 | [design_parameters.json](design_parameters.json) | 母线、根部、状态、支承、翼与设备位置 |
| 三种固定根部布局比较 | [LAYOUT_COMPARISON.md](LAYOUT_COMPARISON.md) · [JSON](LAYOUT_COMPARISON.json) | 顶置、侧置、前置使用同一完整臂和同一对象口径；含适用范围/负结果 |
| 输入几何的来源 | [SOURCE_INPUTS.json](SOURCE_INPUTS.json) · [inputs/](inputs/) | 10 个臂/夹爪 link 的 BRep 输入及 M3R A/B |
| 主建模实现 | [service_robot_common.py](service_robot_common.py) · [kinematics.py](kinematics.py) | 通用装配与显式运动学变换 |
| 新建框架与根部模块 | [frame_root_module.step](frame_root_module.step) | 19个有效实体的新设计结构，可独立复查 |
| 收拢/初展/工作模型入口 | [stowed](service_robot_stowed.step.py) · [initial_deploy](service_robot_initial_deploy.step.py) · [work](service_robot_work.step.py) | 可修改的 STEP 生成设计源；导出状态以实际生成收据为准 |
| 构建、接口、BOM 与质量分账 | [results/](results/) | 已生成项目逐项读回；`*_build_receipt.json` 与 `*_BOM.csv` 按状态对应 |
| 25 项对偶接口要求 | [interface_requirements.csv](interface_requirements.csv) | 主结构、根部、支承、释放、线束、翼、航电与末端接口 |
| 装配及验证步骤 | [ASSEMBLY_AND_TEST_PLAN.md](ASSEMBLY_AND_TEST_PLAN.md) | 关键组合件、10 步装配、13 类检查/试验 |
| 立即开展的零件化 | [NEXT_PARTS.md](NEXT_PARTS.md) | 首批零件、真实输入与完成条件 |

## 配置和模型的读法

S 原点在母线几何中心，X 为长向，Y 为横向，Z 朝屋顶。几何采用 mm，accepted URDF 平移由 m 转换一次。候选根部 frame 为 [90,0,125.15] mm、旋转 I；各状态沿用这一固定根部。M3R Stage A 环嵌入 Stage B 槽，与名义 BRep base_link 共用 z=125.15 mm 的局部原点，B 底面落在屋顶 z=113.15 mm。名义 BRep 基座承载底面在局部 z=2.405 mm，因而它与 A 顶面的接触面是全局 z=127.555 mm；frame 原点并不是这个接触面。

这一修正来自本轮 CAD 对偶复核，见 [INTERFACE_GEOMETRY.json](results/INTERFACE_GEOMETRY.json) 的同原点情况；把 base_link 再抬高 2.405 mm 会产生几何间隙。A/B 也不能简化成两整片顺序叠加。accepted STL 基座 bbox 从局部 z=0 起，与名义 BRep 的承载底面不同，仍需 BRep/STL 与实物的基准注册。

本包准备了 base_link、link1–link6、gripper_link、gripper_left、gripper_right 共 **10 个 link 的名义 BRep 候选**。这些实体便于总装表达；其来源不等同于 accepted STL 的精确复制。运动学和布局检查使用 accepted URDF/STL 时，必须同时保留与 BRep 的模型差异，不能用一条链的检查替代另一条链的检查。

状态角度和夹爪/翼位置以当前参数文件为准。初始收拢种子在检查中暴露了非相邻臂体相交，需要保存该负结果并检验替代姿态；读者不得从早期初值或静态截图推断最终收拢状态可用。完整包络、碰撞/接触与路径覆盖结果，以 [布局比较](LAYOUT_COMPARISON.md) 和 [结果目录](results/) 的最终记录为准。

支承参数中的 **2 mm 是建模时相对源网格的设置间隙**。它既不是接触预紧量，也不证明支承已经承载。下一轮必须加入真实对偶曲面、接触垫和调节结构，闭合间隙/预紧及载荷分流，再验证保持和释放。

完整B601导入模型中仍有6个源实体拓扑问题，默认ShapeFix保形修复未解决，见 [源拓扑探测](results/SOURCE_TOPOLOGY_REPAIR_PROBE.json)。新建19实体结构模块与这些导入源缺陷分别记录；完整总装当前用于布局和接口评审，尚非制造交付。

质量按来源逐件区分：臂沿用 accepted URDF 数字质量；新金属件按候选密度与 CAD 体积估算；设备为明示预算；未分配的线束、机构、传感器等保持缺项。已分配质量小计不是整星实测质量，也不能继承旧整体母线预算块叠加计数。

## 本轮做到什么、接着做什么

本轮工作形成新的共同参数源、完整臂 BRep 输入与显式安装关系，建立三布局比较、状态装配生成入口、接口表、装配验证计划和首批零件任务。具体已生成的模型、BOM、检查数量及数值，以实际文件和收据为准；未完成的检查不写成通过。

下一轮先做**根部承载板/纵梁连接—两鞍座—保持释放—真实线束**这一组合件。将目前的支承间隙闭合为可调整的真实接触，将功能包络深化为可安装的机构与连接器，再通过试装/释放反馈修改零件。末端 F/T 接入、两翼铰链和设备板可以按接口并行深化；F/T 的轴向厚度和质量必须进入新的腕链，不能只在原夹爪旁添加传感器外形。

后续工作的顺序由这些接口、载荷、运动和制造依赖决定。实体试制完成后，再更新同一实装配置的质量、关节零位、TCP、相机/F/T 外参和碰撞几何，开展静止目标抓持闭环及异常停止试验。

## 方法参照

NASA 的服务机械臂资料将活动线束、末端六轴 F/T 与机械臂系统一并描述，并说明工程设计样机可用于在飞行硬件之前发现和修正设计问题。本包据此把真实线束、传感器和关键组合件试装作为联合设计内容；并不借用其硬件能力或资格结论。[NASA Robotic Servicing Arm](https://www.nasa.gov/isam/robotic-servicing-arm/)

ECSS-E-ST-33-01C Rev.2 的官方范围覆盖机构概念、设计、分析、制造、试验验证和在轨运行；官方页面列出机构需求、设计描述、分析验证与使用说明四类文档。本包仅将这些内容作为后续机构工作组织的参考，没有开展逐条符合性审查，也没有标准认证声明。[ECSS-E-ST-33-01C Rev.2 — Mechanisms](https://ecss.nl/standard/ecss-e-st-33-01c-rev-2-1-march-2019-space-engineering-mechanisms/)
