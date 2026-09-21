# WP02 地面保持释放：离线状态机与操作顺序

对象：`WP02_KEY_ASSEMBLY_R1`，`OPEN_PARKING_GROUND_DEVELOPMENT`。实现：[release_state_machine.py](release_state_machine.py)；执行结果：[RELEASE_STATE_MACHINE.json](results/RELEASE_STATE_MACHINE.json)。

**已执行25个纯离线场景，25/25满足各自预期。** 输入全部为 `SYNTHETIC_VIRTUAL_INPUT`，输出的许可是状态机逻辑值；代码没有硬件IO，`hardware_actuation_allowed`始终为false。没有真实传感器、驱动或机械臂运行，也没有将该结果解释为机构强度、实物释放、连续净空或飞行通过。

## 本轮动作量与部件语义

数值来自 [design_parameters.json](design_parameters.json)，运行收据同时锁定参数与代码SHA-256。

| 对象 | 两站各自采用的候选动作 | 必须区分 |
|---|---|---|
| A/B独立锁销 | 每站向-X拔出48 mm并保持防脱捕获 | 当前Ø6×64 mm销轴、Ø12 mm俘获头；锁销承担独立保持力路，不依赖丝杆/电机保持转矩 |
| A/B上接触垫 | 每站沿+Z抬起12 mm | 当前CAD对应link3的名义采样相切区域，壳体允许压力尚未证实；不是直接夹住link2 |
| A/B下鞋/接触垫 | 每站沿-Z撤下30 mm | 下垫对应link2；释放行程30与装调±8 mm分开记，装调不能充当退触点确认 |
| A/B保持载台 | 每站沿+Y退出180 mm | 前提为双锁销和两站上下接触均已脱离；旧160 mm仅历史候选 |
| 人工移动机构 | Ø8 mm、螺距2 mm丝杆几何候选 | 本轮按手动丝杆设计，未选电机/传感器型号，开关只有支架/flag接口 |

上/下接触与框架配对使用 [CONTACT_REGISTRATION.json](results/CONTACT_REGISTRATION.json)、[当前运动分析](results/MOTION_ANALYSIS.json) 和实际CAD零件记录。下垫的accepted link2注册不能替代上垫link3注册。厂家根部新小件内核依据是 [VENDOR_GEOMETRY_PROBE.json](results/VENDOR_GEOMETRY_PROBE.json)，同样不代替实物接口计量。

18 mm为已被几何反例否决的初值：旧CAD中，载台在Y=0时虽无公共体积，刚移动至Y=0.25 mm即与锁销出现3.4291237253352587 mm³公共体积；见 [R1反例](results/KEY_GEOMETRY_CHECK_R1_FINDINGS.json)。新候选采用48 mm退出，载台局部-X边为-20 mm，销尖退出至-28 mm，名义轴向间隔8 mm；[当前几何记录](results/KEY_GEOMETRY_CHECK.json)逐对记录检查范围及状态。这8 mm是名义几何量，未包含实物公差、挠曲或停止超程，也不据此宣称全路径/实物释放通过。新增合成回归场景把两站销位置都设为旧18 mm而open为true，必须锁存故障、禁止Y动作和臂首动。

高支承仍全部归属`GROUND_SUPPORT_EQUIPMENT`。当前正Y侧为公共柱：S.x=40 mm，S.y=155/315 mm，柱顶z=690 mm，公共吊梁z=660 mm；负Y侧两站柱保持S.y=-155 mm。根桥/锚固仍为`ONBOARD_HARDWARE_CANDIDATE`。实际翼动作需要在独立托持和载荷接管条件下移开GSE并重新检查净空，不能把当前地面保持布局解释为翼展开兼容。

## 正常顺序

| 当前状态 | 转换所需事实/事件 | 下一状态 | 允许的下一项人工操作 |
|---|---|---|---|
| `PARKED_HELD` | 独立托持ready、卸载ready、供电/信号有效；操作者手动复位确认；保持几何已恢复；再发新的release请求 | `RELEASE_REQUESTED` | 分别拔出A/B被捕获锁销 |
| `RELEASE_REQUESTED` | 两站锁销open确认与向-X退出量≥48 mm成立，closed信号不得矛盾 | `LATCH_OPEN_CONFIRMED` | 撤离上下接触垫，保持独立托持 |
| `LATCH_OPEN_CONFIRMED` | 两站上垫+12 mm、下鞋-Z30 mm均达到，四个脱离确认成立；所有接触/退回信号无矛盾 | `CONTACTS_RETRACTED_CONFIRMED` | 仅向+Y进行人工退出；不得直接复位接近臂 |
| `CONTACTS_RETRACTED_CONFIRMED` | 两站载台退出位置≥180 mm且各自clear确认成立；锁销和触点确认持续有效 | `CARRIER_CLEAR_CONFIRMED` | 等待明确的首动请求，不能自动命令臂 |
| `CARRIER_CLEAR_CONFIRMED` | 新的first-motion请求；两套A/B信号有效无矛盾、双退出、双锁销、全部触点脱离、独立托持/卸载和人工复位有效持续成立 | `ARM_FIRST_MOTION_ALLOWED` | 仅产生离线虚拟许可；硬件动作始终禁用 |

每次处理最多跨一个阶段，不允许用一次“全部已打开”的输入跳过完整顺序。源文件`initial_deploy`不构成这一状态机的完整动作证明。

## 信号、未知值与故障

每站有独立的锁销open/closed、上垫retracted/contact、下垫retracted/contact、载台clear/held信号及对应位置。两个相反状态同时true属于矛盾；任一关键字段unknown/null或非布尔量、位置非有限数、站位集合不完整，均锁存`FAULT_LATCHED`。两端状态都false可表示已知的中间运动状态，但不能用它取得完成确认。A/B两套signal-set有效值是合成测试条件，不表示实际已安装冗余传感器系统。

单侧锁销、单侧上垫、单侧下垫或单侧载台完成时，状态机等待完整条件，不给臂许可；超时、失电、外部故障、支撑/卸载丢失、已经确认后信号退回或矛盾则锁存故障并撤销虚拟许可。`timed_out`在本离线脚本中是显式合成输入，没有真实定时器或硬件采样调度。

`FAULT_LATCHED`不能通过普通observe或新的动作请求自动消失。复位需要独立托持及卸载有效、供电/信号恢复、操作者手动确认，且锁销/上下垫/载台已人工恢复保持位置。复位只回到`PARKED_HELD`、清除旧许可并要求新的release请求；它不会自动执行复位机械运动或命令臂。

数值比较EPS=1e-9 mm只用于避免合成浮点算术边界误判，**不是传感器精度或制造公差**。真实位置误差、停止超程、接触变形、线束和信号资格仍须对应实物输入。当前根框M6连接/丝杆强度未定不阻止离线逻辑检查，也没有因此获得承载通过。

## 已执行场景

| 类别 | 场景 |
|---|---|
| 正常与顺序 | 完整受托持顺序；载台clear后仍等待首动请求；首动请求不能跳阶段 |
| 输入/支撑 | unknown锁销反馈；无人工复位；无独立托持；无卸载；B信号集失效 |
| 单侧完成 | 单锁销；单上触点；单下触点；单退出载台 |
| 矛盾与异常 | 开闭矛盾；超时；首动前失电；已许可后卸载状态丢失 |
| 动作绕过 | 未确认触点先Y动；未确认锁销先退触点；把装调位移当下鞋释放；下鞋行程不足却发完成flag；旧18 mm锁销退出伪报open |
| 故障复位 | 非人工复位拒绝；无托持复位拒绝；有效人工故障复位不命令臂；普通observe不清故障 |

每个场景在结果JSON内保存了逐步合成输入、状态、拒绝原因、Y虚拟许可和臂虚拟许可；所有场景同时检查硬件始终禁用。25/25指这些逻辑预期被验证，不等于25次实物释放。

本次参数版本追踪：前次24场景收据的参数SHA-256为`f78557bee7003abeba51febb1d8881586ffd572170ec762afb2b64bfbafeb579`；48 mm锁销/公共正柱更新后的参数SHA-256为`67ecd595396360b9f20574df7d0851f4756799e4d7c3a1ba5befd9f5725b4671`。本次执行结果中的`parameters_sha256`和`source_code_sha256`分别绑定本次实际读取参数与代码；历史哈希不表示前后参数仅改了一个字段。

在项目目录可重跑：

```powershell
python '20_engineering/service_robot_wp02_20260905/release_state_machine.py'
```

该命令仅读取候选参数、执行合成场景并更新本包的状态机结果JSON。实际首装与卸载程序见 [ASSEMBLY_AND_ACCEPTANCE.md](ASSEMBLY_AND_ACCEPTANCE.md)。
