# 航天服务星 × B601：WP04 整机数字装配候选

已执行新一轮机械设计，生成三种整机数字配置、新增连接实体、接口合同和独立验证结果。当前交付等级是**工程样机的数字装配候选**。全部机械设计、真实机构选型、实物装配、连续动作与制造放行尚未完成。

[打开整机交互页面](http://127.0.0.1:8767/index.html) · [打开 R07 局部 CAD](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/candidate?file=r07_local.step.py) · [下载整机服务态 GLB](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/viewer/complete_service_robot.glb>) · [机器结果](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/results/WP04_RESULT.json>)

![整机服务构型](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/viewer/screenshots/service_final.png>)

页面可切换开放停放、释放、服务三态，按六类隐藏零件、查看内部、点击零件查询来源和接口。分解滑块仅用于观察装配关系；三态切换不表示连续动作已验证。“开放停放”不是合格的发射收拢构型。模型含功能包络与简化代理，585 个实例不等于 585 件完成选型的实物零件。

本轮实际改变了什么：

| 连接 | 已实现的 CAD 改变 | 保留的工程边界 |
|---|---|---|
| 桥板／跨梁到主纵梁 | 四块 3 mm 上跨接板、四个扩展下垫块，共用柱拉杆延长 3 mm | 拉杆预紧、跨板弯曲和公差待验 |
| 主纵梁到端塞 | 十二组竖向连接；中空段增加防压套管；前端轴向螺钉缩短避免相交 | 八处端塞用底孔与无螺纹杆代理，真实啮合为 UNKNOWN |
| 后端框到内侧后隔框 | 四处后端轴向连接穿过隔框并增加承压垫圈 | 加强肋固定与供应方分离接口待细化 |
| 保持横梁到主纵梁 | 四个耳座增加外翼，八组内／外固定连接与套管支撑 | 套管定位、防遗落及装配公差待定 |
| 保持脚到耳座／横梁 | 负 Y 足座增加两孔沉台，头部齐平避开旋转桅杆 | 2.5 mm 剩余底厚的承载尚未验证 |

另外修复了前盖四角与螺钉头干涉、翼根叉座的紧固件及工具通道、保持耳座与旧螺钉头干涉、下剪力板与扩展垫块干涉。四个旧侧向螺钉仅作名义几何截短，正装配间隙仍未建立。早期失败模型和 C4 审查负结果保存在 inputs/candidate_1、inputs/candidate_4_failed 与 review/R07_REVIEW_CANDIDATE4.json；最终 C5 结果没有覆盖它们。

**验证只在明示范围内计入：**

| 检查 | 最终结果 | 适用范围 |
|---|---|---|
| 非臂实体有效性 | 575/575 | 最终服务态 STEP 实体读回 |
| 局部与整机对应 | 245 实例一致；246 检查通过 | 库存一致性加逐实体材料差比较 |
| 对偶孔、承压面 | 60/60、40/40 | 名义轴线、孔道及平面材料支撑，未计算强度 |
| 插入／工具路径 | 128/128 | 合同指定阶段和直线包络；含八条裸纵梁套管插入路径 |
| R07 相关静态检查 | 服务态 72,443 对候选，418 对进入精查，无未解释的非螺纹交集 | 八处螺纹代理交集仍 UNKNOWN；总体不判全机无碰撞 |
| 三态回归 | 改动涉及的 158 个实例几何／位置一致；相关静态检查通过并保留八处 UNKNOWN | 停放、释放、服务三个离散配置，不覆盖完整机械臂和连续轨迹 |
| 审查负向用例 | 6/6 能拒绝缺陷 | 填孔、错轴、垫圈侵入、螺钉相交、套管过短、旧前盖干涉 |
| R01 回归 | 两甲板、八角材实际孔库存一致 | 只计检查的既有几何 |
| 参数传递 | 8/8 | 左轨连接 X=15→14 mm 的选定字段；未声称全系统任意参数可重建 |
| 数字身体合同 | 63/63 | 最终候选绑定及离线故障控制；没有硬件或控制仿真执行 |
| 实际质量账本复算 | 52/52 | 独立质量、质心、平行轴与来源检查 |

依据：[R07 最终审查](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/review/R07_REVIEW_FINAL.json>)、[三态回归](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/review/R07_THREE_STATE.json>)、[数字身体检查](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/review/DIGITAL_BODY_CONTROLS.json>)、[实际账本复算](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/review/ROBOT_ACTUAL_LEDGER_RECHECK.json>)。既有臂表面检查只覆盖已声明的非相邻臂体对；手指、包含关系、邻接关节与整机臂—舱连续避碰仍未获通过结论。

每种配置有 **585 个实例 = 575 个本轮非臂 STEP 实例 + 10 个保留来源与变换的 B601 实例**；相对上一轮新增 96 个实例。三份结构 STEP 不包含机械臂，完整装配由复合索引引用原臂 BRep；GLB 和交互页面同时显示两部分，GLB 是显示网格，不能替代精确 CAD。

质量账本含 198 项数字质量分配和 387 项 UNKNOWN。分配项合计 **20.733608541407722 kg**，其中 B601 数字质量 4.695555949342986 kg 只计一次。该合计不是整机实测总质量；未知项不能按零填充。复算最大质心差 1.39×10⁻¹⁷ m、惯量差 6.67×10⁻¹⁶ kg·m² 表示算术一致，不表示真实物理精度。该账本也不覆盖既有 R2 发布或研究 Gate。

| 交付文件 | 用途 |
|---|---|
| [服务态结构 STEP](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/candidate/servicer_structure_service.step>)／[停放态](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/candidate/servicer_structure_parking.step>)／[释放态](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/candidate/servicer_structure_released.step>) | 575 实例的精确非臂装配 |
| [服务态复合索引](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/candidate/results/service_COMPOSITE_ASSEMBLY_INDEX.json>) | 本轮结构与 10 个原臂来源、哈希及变换 |
| [R07 局部 STEP](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/candidate/r07_local.step>) | 245 实例局部连接检查 |
| [六视图 DXF](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/candidate/r07_interfaces.dxf>) | 来自实际最终 STEP 面的 1:1 毫米参考图，12 处尺寸；尚非全尺寸制造图 |
| [BOM](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/candidate/BOM.csv>)／[安装接口表](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/candidate/INTERFACES.csv>) | 各 585 行，保留质量和物理参数 UNKNOWN |
| [系统接口合同](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/contracts/SYSTEM_INTERFACES.json>) | 20 组具名连接、60 孔、40 面、128 路径及多端点关系 |
| [数字身体说明](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/contracts/数字身体与接口说明_ZH.md>)／[消费合同](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/contracts/DIGITAL_BODY_CONSUMER_CONTRACT.json>) | 坐标、量纲、质量来源、关节与状态接口；未验证的实际驱动参数为空 |
| [装配工艺设计](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/ASSEMBLY_PROCEDURE_ZH.md>) | 十二道工序及每步未完成验证 |
| [详细设计输入清单](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/MECHANICAL_INPUT_REGISTER_ZH.md>) | 选型、实测与力学计算所需数据 |
| [来源保护](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/results/SOURCE_PROTECTION.json>)／[证据新鲜度](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/results/FINAL_EVIDENCE_FRESHNESS.json>) | 46 项原始来源、50 项前轮文件、10 项原臂 BRep 均未改变；74 条审查输入引用当前匹配 |

接续设计按以下依赖推进：

1. 完成保持器导向端座、轴向防脱、机械止挡、退出锁止、驱动与传感器安装，以及后隔框加强肋和套管定位。这些仍可继续进行数字细化。
2. 完成整机工序依赖、甲板／设备／盖板后装路径、实际工具包络，以及机械臂、双指、翼和活动线束的连续轨迹检查。128 条局部路径不能替代这一验收。
3. 依据实装 B601、设备和连接器数据确定接口；取得材料、紧固件、扭矩—预紧、载荷和地面托持输入，开展尺寸链、承载及连接刚度核算。优先审查 **2.5 mm 沉孔残底、1.13276253 mm 叉座净距、0 mm 旧侧螺钉名义间隙**。
4. 完整标注 GD&T、完成零件选型与质量回填后，才形成可执行实物试装工单。实物试装、载荷试验和制造放行需实际记录；后续飞行适配另依供应方 ICD 与环境要求验收。

释放逻辑已提供离线合同：两站锁销、盖板、滑鞋和折退锁止状态必须有有效证据，未知、失联、矛盾或陈旧状态禁止输出运行许可。当前没有真实传感器校准、执行器力／速度许用或硬件试验，硬件命令授权保持 false；没有执行具身策略训练、机械臂控制或物理仿真。

重现入口为 candidate/design_parameters.json、candidate/r07_design.py 与本轮 candidate/build_nonarm_states.py；验证入口为 review/review_r07.py、review/r07_three_state.py、contracts/bind_contracts.py --final 及 review/robot_actual_ledger.py。本目录包含前轮保留脚本；不要运行旧 closeout.py 或 integrate_checks.py 来发布本轮结果。涉及 CAD 的重建必须经 run_guard.py 串行执行，随后重新绑定全部输出哈希；详见 candidate 中的脚本与 logs 中的执行记录。原研究 Gate、原输入和 R01 结果保持原样。
