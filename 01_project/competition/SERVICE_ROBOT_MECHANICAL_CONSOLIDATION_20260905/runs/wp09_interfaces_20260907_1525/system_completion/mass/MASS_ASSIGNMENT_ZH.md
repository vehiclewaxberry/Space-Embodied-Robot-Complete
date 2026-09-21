# 当前三态 705 实例质量归属账

当前 service、parking、released 三态的同一组 **705 个实例已完成 100% 责任归属**，分为 41 个唯一责任组。这里的“owner”是质量归属对象，不是个人或审批角色。705 个实例不能乘以三个姿态计成 2115 件硬件。

**有来源的材料模型质量小计为 7.820206 kg；加一次 B601 DM 整臂厂家名义 4.5 kg 后为 12.320206 kg。两者都不是整星完整质量。** 旧设备/太阳翼等 7.69 kg 预算已从材料和厂家名义分账中分开；未将预算当作真实设备质量，未给未知件填零。

| 覆盖维度 | 当前结果 | 含义 |
|---|---:|---|
| 实例质量责任归属 | 705/705，100% | 每个实例只属于一个责任组 |
| 具有体积与已定义候选密度的实例 | 178 | 160 个铝候选件、18 个钢候选件 |
| 厂家整模块名义质量覆盖 | B601 10 个实例 | 只在完整机械臂 owner 计一次 4.5 kg |
| 材料模型或整模块名义数值覆盖 | 188/704，26.7045% | 分母排除一个纯空间预留对象；不包括预算 |
| 仅有旧规划预算的实例 | 16 | 不能据此证明质量已测定 |
| 有真实/代表硬件而数值尚未绑定 | 516 个实例，30 个 owner | 包括预算对象及连接器/机构/线束包络所代表的硬件 |
| owner 数值分配完整 | 10 个硬件 owner | 另有 1 个纯空间 owner 无质量适用性 |
| 有交付硬件实测或保证下限 | 0 | 不能把上述估算升级为实物保证 |

详细文件：[逐实例 JSON](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/mass/MASS_ASSIGNMENT_705.json>)、[逐实例 CSV](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/mass/MASS_ASSIGNMENT_705.csv>)、[41 组汇总](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/mass/OWNER_SUMMARY.csv>)、[30 组最小缺数据](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/mass/OPEN_MASS_INPUTS.csv>)、[机器检查结果](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/results/MASS_ASSIGNMENT.json>)。

本轮实际修正了前服务盖板。原 701 清单的 `front_service_cover` 已从当前三态移除，其 0.246856283539 kg 也随之移除；705 清单中的 `WP09F_front_service_cover_GSE` 使用已有冷回读体积 90603.773586449 mm³，沿用该盖板已定义的 AL_CANDIDATE 密度 2.7×10⁻⁶ kg/mm³，得到 **0.244630188683 kg**，差值 **−2.226095 g**。四个新增 GSE 压盖/锁母另归两个成套 owner，质量保持未知；型号相符的厂家成套质量到位后可各计一次，不要求拆到内部零件。名称中的 GSE 表明当前 705 配置含地面接口候选，该账不能自动当作最终飞行配置。

原 20.012432095120083 kg 混合小计在只修正盖板后会变为约 20.010206 kg，但仍含 7.69 kg 预算和 4.5 kg 未绑定交付修订的厂家名义值，**不得把它写成 705 实例整星质量或下界**。本轮已把这三种数值分列，而没有静默删除或重写旧冻结账。

已定义材料的追溯采用 WP04 的逐实例密度字段、WP05 与当前 source SHA 匹配的实际导出体积，以及 WP09 已定义的新铝件质量分配。154 条旧 CAD 质量全部找到了对应密度和体积，最大反算差约 1.61×10⁻¹¹ kg；移除旧前盖、保留其余 153 条，再加入 24 条已有明确材料分配和一条新前盖，形成当前 178 条。两个保持站部分零件在不同姿态有不同 STEP/native 文件，已逐态核对体积，未因文件名或哈希不同重复加质量。没有用旧 WP03 的不同版本体积覆盖当前真值。

| 有材料数值的责任范围 | 当前已计材料小计 kg | 尚需另补的范围 |
|---|---:|---|
| 根部框架金属 37 件 | 2.455722243 | 72 件根部紧固件属于单独 kit |
| 主结构金属 31 件 | 1.443930343 | 梁板和 WP06 的 60 件紧固件另计 |
| 盖板及当前 GSE 前盖 16 件 | 0.949942233 | 两个 GSE 压盖成套质量另计 |
| 设备板及转接支架 15 件 | 1.600488066 | 设备实际质量、R01 紧固件另计 |
| 既有保持机构金属 22 件 | 0.811860373 | 改版立杆、导杆、分体箍、紧固件、垫片、执行器/传感器另计 |
| 太阳翼既有边框及铰链 28 件 | 0.132337289 | 当前叶片层合体、展开器、线束另计 |
| R07 金属盖、热扩散板、外部支架 | 0.091920724 | 对应设备和软界面另计 |
| 推进支座/P60 安装件/线束金属支撑中的已知部分 | 0.334004729 | 同 owner 内仍有螺杆、紧固件、聚合物夹块或护圈缺质量 |

B601 的 `base_link`、`link1`–`link6`、`gripper_link`、左右指爪共 10 个实例，在现行回读清单中包含 **391 个实体**。这不是 391 个可另加质量的采购件；原厂整臂名义值只覆盖完整原装机械臂（原有内部电机、驱动器、内部紧固与夹爪），交付修订、随货附件边界及质量公差仍待确认。星体 M5/M6 根部安装件、R01/R07/WP06/WP07 安装紧固件、保持机构、外部服务线环和 USB-CAN/分线板均没有被吞入该整臂质量。

原 496 个未分配实例中，没有新增发现可按 B601 内部件直接消除的重复质量项；其中 1 个是 `launch_interface_reserved_volume` 纯预留空间，余 495 个仍有待确定的真实硬件质量责任。主量来自星体安装紧固件和保持/热/线束接口。四类大型现有紧固件 kit 分别有 72、60、128、92 个实例，可按明确内容表取得整套质量，不必逐个螺钉实测。WP07 已有 ISO 几何的零件也未被统一赋成钢：其受控合同仍缺采购材料，目录几何不能替代材质选择。

`FUNCTIONAL_ENVELOPE` 只描述几何表达方式，不能一律豁免质量。40 个此类实例中只有上述 launch 预留空间明确无独立硬件质量；连接器、P60/MiPS、释放器、弹簧、传感器和线束路径仍归属真实硬件 owner，包络体积本身不乘密度。相互覆盖的线束路径必须先对应唯一的线缆 BOM，不能把每条示意路径当作独立线束重复加长。相机镜头归相机组件，但原 0.15 kg 预算是否包含镜头仍是待填字段。

重复计量处理还包括：MiPS 0.542 kg、BPX 0.5 kg、A3200 0.024 kg 不叠加在旧设备汇总预算上；P60 0.191 kg 参考配置尚无当前实例/配置绑定，保持独立待决；`equipment_arm_drive` 的 0.8 kg 只是旧规划额，责任范围明确为外部分线/接口电子件，不能把六个 DM 关节内置驱动器再算一次。未依据代理盒的几何体积计算电子件质量。

在**178 个源绑定物理件均按现有几何保留，并采用记录中的固定候选密度**这一数学模型条件下，未知余项质量非负，因此可给出保守模型下界 **7.820205 kg**。它包含每件 10⁻⁵ mm³ 的账本数值余量和 1 mg 向下取整，不包含设备预算或厂家名义质量。这不是材料、制造公差或实物称量保证：现有证据尚不能给出非零的、经过公差或称量保证的整机实物下界。机器文件将该字段保持 `null`；通用 `m≥0` 的物理事实没有被用来给任何未知零件填质量 0。

太阳翼新增 AZUR 81442 CIC 按原已锁规划的 6×7S2P，共 84 个、CIC-only 名义参考质量 **0.3024 kg**，保存于 [未集成 PV84 增量](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/mass/PV84_UNINTEGRATED_DELTA.json>)。它不进入当前 705 实例，也不叠加在当前六片各 0.18 kg 的叶片预算上。后续完成新叶片及布线/胶层设计后应形成明确替换差量，边框和铰链是否沿用也需逐项确认。

最小补数按 30 个 owner 列在 CSV 中：紧固件最终规格/材质或含内容表的整套质量；改版保持件的当前体积与明确材料；软垫和热界面的材料/胶层；实际释放/弹簧/传感器组件；唯一线束 BOM 与长度/线密度/端子；电子设备及 P60 的确切装配配置；推进选定模块；当前太阳翼叶片层合体与展开器。已完成材料估算的 owner 进入实物阶段时仍需相应制造或测量证据。

完整质量、质心和惯量继续保持未知。姿态变换充分并不能补出未知质量或内部质量分布，本轮没有以包络盒中心或均匀盒体惯量替代真实物性。[复算脚本](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/tools/mass_assignment.py>) 使用纯 Python 读取既有回执，检查 **687/687** 通过，峰值工作集 **63.2 MiB**；结果只证明责任分组、来源绑定、替换差量和分账自洽。未运行 CAD/COM、未修改冻结 N 或科学模型。
