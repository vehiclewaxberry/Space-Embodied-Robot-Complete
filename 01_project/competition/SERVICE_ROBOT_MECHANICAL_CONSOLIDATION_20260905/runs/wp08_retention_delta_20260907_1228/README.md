# WP08 机械收束实际交付 · 2026-09-07

本轮完成两站保持机构在三个实际 SolidWorks 整机装配中的增量回装，并完成一处 +Y 后竖肋两点紧固的局部实体设计。目标仍为可装配工程样机候选；整星全部结构、运动机构和电气设计尚未完成。

直接查看：[整星三维预览](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp08_retention_delta_20260907_1228/viewer?file=WP08_SERVICE_RETENTION_DELTA_V3.glb) · [后肋局部三维预览](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp08_retention_delta_20260907_1228?file=candidate%2Frear_rib_connection.step.py)。两个页面均已实际加载并审阅。整星预览是625实例显示模型，后肋候选尚未并入其中。

| 可打开的实际装配 | 本轮证据 |
|---|---|
| [服务态 SLDASM](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp08_retention_delta_20260907_1228/native/WP08_ROBOT_SERVICE.SLDASM>) | 625实例 / 1006实体；完整冷重开、实例/依赖/位置独立核对通过 |
| [停放态 SLDASM](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp08_retention_delta_20260907_1228/native/WP08_ROBOT_PARKING.SLDASM>) | 625实例 / 1006实体；完整冷重开、实例/依赖/位置独立核对通过 |
| [释放态 SLDASM](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp08_retention_delta_20260907_1228/native/WP08_ROBOT_RELEASED.SLDASM>) | 625实例 / 1006实体；完整冷重开、实例/依赖/位置独立核对通过 |
| [后肋局部 SLDASM](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp08_retention_delta_20260907_1228/native/REAR_RIB_LOCAL/WP08_RIGHT_REAR_RIB.SLDASM>) | 11实例 / 11实体；逐件原生冷重开和导出STEP逐体材料比较通过 |

整机每态保留591实例、替换6实例、新增28实例。每态473个不同原生依赖，三态合计488个不同依赖文件；依赖分布在已有WP05–WP07目录，请保留当前目录结构。37个原有功能包络的隐藏状态予以保留。

停放态保存时曾触发内存保护；SolidWorks随后留下的实际文件通过重新完整只读冷检。原保存调用的API返回仍未知，采用恢复V2及独立检查作为当前证据，不将旧中断日志改写为成功。

**本轮新增的后肋实体**：两个原件各增加两处Ø3.4名义通孔，轴线位于S系Y=90、Z=±50 mm；采用两套目录M3×16螺钉、双垫圈和螺母，共8件硬件。局部包还包含1个原有端框用于检查，端框不属于新增随星零件。所有局部STEP为S世界系毫米，原生装配采用恒等放置。

[后肋主 STEP](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp08_retention_delta_20260907_1228/candidate/rear_rib_connection.step>) · [原生回导 STEP](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp08_retention_delta_20260907_1228/native/REAR_RIB_LOCAL/native_roundtrip.step>) · [参数与源件合同](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp08_retention_delta_20260907_1228/inputs/REAR_RIB_DESIGN_CONTRACT.json>) · [后肋零件清单](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp08_retention_delta_20260907_1228/results/REAR_RIB_LOCAL_BOM.csv>)
 
独立局部几何检查179项通过：核对源件保形、通孔、承压接触、55对局部材料交叠、三态14952组新增硬件—保留邻件筛查及7596组声明工具包络筛查。后两类采用AABB排除后对候选执行BRep精查，不能理解为全部进行了BRep布尔。

11个原生回导实体逐一与源实体比较，对称材料差均为0 mm³（检查容差1e-5 mm³）。前侧工具包络到端框为7.15 mm，但与内垫圈末端面存在零距离、零体积接触；这不是全通道最小正间隙。螺纹、防松、预紧、实际工具适配、装配工序和连接强度尚未确认。

**对已有结构的更正**：两站现有叉座已具有90°附近的名义单向越程止挡，每站实际接触约109.361 mm²。该检查仅取89.9°、90°、90.1°；折叠后保持锁扣、传感靶标及其真实状态仍缺，`mast_park_locked=null`。

**结构查看图**（本轮后肋局部，已审阅）：

![后肋连接两面装配](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp08_retention_delta_20260907_1228/viewer/rear_rib_opposite_20260907T042333Z.png>)

四视图：[等轴](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp08_retention_delta_20260907_1228/viewer/rear_rib_iso_20260907T042333Z.png>) · [反向](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp08_retention_delta_20260907_1228/viewer/rear_rib_opposite_20260907T042333Z.png>) · [轴向](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp08_retention_delta_20260907_1228/viewer/rear_rib_axial_20260907T042333Z.png>) · [俯视](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp08_retention_delta_20260907_1228/viewer/rear_rib_top_20260907T042333Z.png>).

整机PNG导出因渲染浏览器关闭失败，已保留日志；补充两改件单独出图也触发内存保护，未取得单件PNG。上面的四张局部装配图及交互显示不改写这些结果。局部11实例的CAD refs与validate已执行，validate为0失败。

**继续执行入口**：[16模块实际执行表](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp08_retention_delta_20260907_1228/results/MECHANICAL_MODULE_EXECUTION_STATUS.csv>) · [下一批实体执行单](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp08_retention_delta_20260907_1228/docs/NEXT_MECHANICAL_EXECUTION.md>) · [完整结构缺项核对](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp08_retention_delta_20260907_1228/docs/STRUCTURAL_COMPLETENESS.md>).

下一批优先处理主枢轴/盖轴轴向防脱、锁销机械捕获，以及已验证后肋的三态差量集成；随后补其余肋、盖板、太阳翼另一端保持、设备载体、线束端接与工装。后肋集成后的633实例/1014实体仅是下一批验收目标，不是当前交付数量。

实际B601/驱动、PCB、EPS、电池和连接器尚未完整选型并绑定孔系/电流/针脚；四块参考PCB不计为已装星电路。B601原有4项FAIL和6项INCOMPLETE保留。质量预算、连续运动、强度与实物装配未重新完成，当前不能用于宣称制造或通电放行。

**文件与证据**：[625实例BOM](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp08_retention_delta_20260907_1228/results/ASSEMBLY_BOM_SERVICE.csv>) · [488项原生依赖](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp08_retention_delta_20260907_1228/results/NATIVE_DEPENDENCIES.csv>) · [实际交付机器记录](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp08_retention_delta_20260907_1228/results/DELIVERY_STATUS.json>) · [局部179项检查](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp08_retention_delta_20260907_1228/results/rear_rib/CHECK.json>) · [局部原生回导检查](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp08_retention_delta_20260907_1228/results/REAR_RIB_NATIVE_ROUNDTRIP_CHECK_V3.json>).

交付时重新核对1263个已绑定输入，当前哈希一致。SolidWorks原生文件已保存；为释放缓存，已核对并关闭12个本轮无修改文档，再正常退出空会话，可用内存由约0.9 GiB恢复到约3.1 GiB。交互查看服务保持开启。

本轮原生零件主要为导入实体，参数修改入口在源模型与设计合同；固定姿态装配不等于完整SolidWorks运动配合模型。历史科学Gate、accepted URDF及L2辅助研究模型保持其既有结论。
