# WP03 第一轮机械细化交付记录

本轮已完成 **R01 甲板—角材—剪力板连接的有界数字闭环**，并完成 **R17 最终几何→动力学参数交接→BOM 的同源绑定**。可进入下一组 R07A 臂根桥架／横梁—主纵梁连接细化。材料、螺纹/预紧、结构强度及实物试装仍是 R01 父问题的后续验收项。

执行目录：`wp03_bounded_20260906_161431`。所有新设计和证据均在本目录；原 WP01/WP02/WP03、历史科学裁决及 loop0 账本作为来源保留。

## 实际改动

| 对象 | 本轮结果 |
|---|---|
| 两层甲板 | 保留 344×196.3×3 mm 外形和柱避口；每层8个 Ø3.4 完整紧固孔，X=−150/−50/50/140 mm、Y=±92.65 mm |
| 八段角材 | 补齐与甲板及剪力板的对偶孔，保留原外形与分段位置 |
| 两侧剪力板 | 补齐角材接口孔，X=−130/−70/60/130 mm，Z=−94.15/−18.5 mm |
| 紧固件 | 16组甲板—角材＋16组角材—剪力板，共32套；每套螺钉、两垫圈、螺母，合计128个名义实例 |
| 本轮揭示并修正的干涉 | 下甲板为 Ø10 导热代理增加 Ø12 贯通避让；下角材为10个既有螺钉末端增加 Ø3.4 避让 |

紧固件是未选型的名义无螺纹几何。甲板连接名义夹持厚度6 mm、螺钉头下长12 mm；剪力板连接为5 mm、10 mm。垫圈外径6 mm、内径3.4 mm、厚0.5 mm。工具轴/空心套筒是声明的检查包络，不能代替实际工具选型及传扭校核。

新热件孔提供名义径向1 mm避让；既有 Ø3 螺钉与 Ø3.4 避让孔的名义径向间隙为0.2 mm。它们均未包含制造、装配和热变形公差。

## 证据与边界

| 实际检查 | 结果 |
|---|---|
| STEP 读回实体有效性 | 479/479；包含明确标注的功能包络，几何有效不代表硬件落实 |
| 连接孔、承压区域 | 64个配对成员孔、64处垫圈承压面全部通过 |
| 孔清单、柱避口及新增避让 | 精确孔轴/孔径集合、8处柱避让、11处新增避让全部通过 |
| 服务态相关静态材料干涉 | 52,010个相关配对，273个进入窄相；最终0处正体积相交 |
| 紧固件及工具通道 | 服务态指定装配阶段192条路径通过；128个标准件装入＋64个工具包络 |
| 另外两态相关静态 | R01的140个实例三态逐值相同；parking新增8,540对、released新增3,780对均严格AABB分离，最小可证轴向间隙13.25 mm |
| 参数化传播 | 将一处X孔位140→138 mm，在内存重新生成甲板与角材，两侧同步变化；最终参数文件未改动 |
| 独立负控/软件 | 110项协议检查、19项组合来源检查通过；保留第一次几何失败及软件缺口回执 |

三态静态结果限于 R01 相关非臂几何。192条工具/装入路径的证据只属于服务态指定装配阶段。后装的设备、适配板、热垫和侧盖自身安装路径，仍需单独验证。

实际机械臂表面 worker 已运行三态；每态35组声明的非相邻臂体表面未检出相交。夹指对、相邻关节、体积包含、臂—星体全范围和连续路径仍不能据此判 PASS。

## 装配次序与下一阶段

1. 对甲板、分段角材、剪力板进行基准定位及临时支撑；临时支撑工装另行落实。
2. 在设备、适配板、热垫和侧盖安装之前，逐连接装入两侧垫圈、螺钉、螺母，并按对应工具包络检查可达性。
3. 选定真实紧固件和工艺后确定预紧、防松与检查方法；目前不填写未经来源确认的扭矩值。
4. 验证后装件自身路径，再进行局部实物试装及孔位/间隙测量。

下一组为 **R07A 臂根桥架／横梁—主纵梁连接**：建立完整接口和双侧对偶孔、确定定位/紧固方向、验证装入与工具空间；取得臂根六分量载荷、材料及紧固件数据后，完成螺栓群、孔壁承压、净截面/撕裂和局部刚度校核。任务输入及验收项已写入 [下一轮工作单](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp03_bounded_20260906_161431/results/NEXT_R07A_WORK_ORDER.json>)。

## 数字装配和质量交接

每态489实例由 **479个本轮重建的非臂实例＋10个哈希锁定的未改动臂实例** 组成。三份新 STEP 只含非臂几何；完整组合包通过装配索引引用原臂 BRep 与其位姿，`monolithic_complete_step_generated=false`。旧臂几何、姿态和原始属性逐项保留，未继承旧碰撞结论。

已分配质量小计 **20.712042414482 kg**，194个质量原子；295实例质量仍未知，其中含本轮新增128个紧固件实例。这个小计包含 CAD 估算、设备预算和 URDF 数字质量，不能作为整星实测质量。三态质量一致，COM 和惯量按各自位姿重新计算。独立复算质量差为0，COM最大差约1.39e−17 m，惯量最大差约6.66e−16 kg·m²；这些是数值一致性结果。

[BOM](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp03_bounded_20260906_161431/candidate/BOM.csv>) · [接口清单](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp03_bounded_20260906_161431/candidate/INTERFACES.csv>) · [动力学参数交接](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp03_bounded_20260906_161431/candidate/results/DYNAMICS_HANDOFF.json>) · [独立账本复算](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp03_bounded_20260906_161431/review/ACTUAL_LEDGER_RECHECK.json>)

## 交付入口

- [R01局部连接STEP](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp03_bounded_20260906_161431/candidate/r01_local.step>)（12个改件＋128个名义紧固件）
- [接口参考图DXF](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp03_bounded_20260906_161431/candidate/r01_interfaces.dxf>)（11视图、22个尺寸实体；制造公差/材料/工艺未放行）
- [停放态星体STEP](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp03_bounded_20260906_161431/candidate/servicer_structure_parking.step>) · [释放态星体STEP](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp03_bounded_20260906_161431/candidate/servicer_structure_released.step>) · [服务态星体STEP](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp03_bounded_20260906_161431/candidate/servicer_structure_service.step>)
- [服务态完整组合索引](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp03_bounded_20260906_161431/candidate/results/service_COMPOSITE_ASSEMBLY_INDEX.json>) · [参数文件](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp03_bounded_20260906_161431/candidate/design_parameters.json>)
- [独立机械复核](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp03_bounded_20260906_161431/review/R01_REVIEW_CANDIDATE2.json>) · [三态静态补充复核](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp03_bounded_20260906_161431/review/R01_THREE_STATE_CONTEXT_RECHECK.json>) · [本轮机器记录](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp03_bounded_20260906_161431/results/ROUND_RESULT.json>)

[交互查看R01](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp03_bounded_20260906_161431/candidate?file=r01_local.step.py) · [交互查看服务态星体](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp03_bounded_20260906_161431/candidate?file=servicer_structure_service.step.py)

![R01背侧与甲板避让孔](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp03_bounded_20260906_161431/candidate/results/r01_local_opposite_20260906T083349Z.png>)

## 执行记录说明

本轮使用1名生产构建者与2名独立审阅者。首版几何暴露11处真实静态干涉、16条被后装件阻挡的路径及64项垫圈装入覆盖缺失；第二版逐项修复并复核。首次完整STEP复核还暴露了检查器复制父装配树的内存问题，随后采用脱离装配树的单实体定位，并增加操作系统级1,400 MiB子进程内存硬上限。原失败和恢复说明保留在 logs/ 与 review/。

CAD的9张快照已检查。安装的DXF构建器与快照器预览格式不一致，DXF交换文件验证通过；4张静态图直接由该DXF渲染并核对，未改变图纸几何。原WP来源哈希复核见 [来源保护记录](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp03_bounded_20260906_161431/results/SOURCE_PROTECTION_FINAL.json>)。
