# 航天服务星推进完整模块公开选型复核

结论：在本次核查的旧 VACCO MiPS、旧 C-POD，以及限定的两种替代完整系统 GomSpace NanoProp 6DOF、T4i PERSEUS 中，没有一项能够依据已取得公开资料完成“喷口坐标与方向—允许并发—电源针位—命令及遥测协议”的完整绑定。因此本轮不能交付声称可直接接线、可直接控制的已定型推进模块。此结论表示本次公开证据不足；不表示这些产品不合格，也没有证明完整公开 ICD 在任何地方都不存在。

本轮推荐把下一次资料补齐集中到 **VACCO X13003000-01 C-POD** 一个对象，作为资料取得优先项，尚不构成采购或装机定型。原因是旧锁版供电范围及双阀功率更接近现有推进分支、完整目录冲量尚未被下述必要条件排除。其真实三轴能力、并发和任务适配仍须完整 ICD；旧共享舱空间和沿用历史推进剂预算不能直接接受。

本轮仅检索原厂网页、网页实际链接及原厂域名索引，实际保存了 8 份 PDF（含两份上轮冻结原件的精确副本）和 5 份网页；不提交表单、不联系供应商、不改变冻结 CAD 或科学 Gate。来源、HTTP 结果和哈希见 [SOURCE_MANIFEST.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/sources/propulsion_intake/SOURCE_MANIFEST.json>)。两种替代之外出现的新版 Standard MiPS 只用于辨别旧版本冲突，没有扩大替代比较。

| 对象与来源身份 | 本轮确认的公开内容 | 不能直接完成设计的字段 |
|---|---|---|
| VACCO MiPS X14029003-1，Rev 6/15，PDF 第 1–2 页 | 5×10 mN、44 Ns、542 g 湿质量；图有 A–E、4×19°局部角度及安装尺寸 | 缺喷口完整三维基准及指令映射、允许并发组合、接插件针表、命令/遥测字典；10 W 仅为最大稳态参数 |
| C-POD X13003000-01，锁定 SHA 对应的 Rev 7/14 | 8×10±2 mN、174 Ns、估计湿质量 1330 g；9–12.6 V；5 W 对应两个喷口；有 15°偏轴/典型喷流示意、流程编号 1–8 | 示意图没有完成编号—坐标—力方向—指令的关联；双喷口功率说明没有定义全部允许组合；缺完整针表/协议 |
| GomSpace NanoProp 6DOF，原厂旧 PDF 的索引文本 | 索引描述完整系统含两模块，每模块六喷口、200×100×55 mm、干质量 682 g、推进剂 122 g、65–100 Ns；5 V 与 32 V、CAN/I2C | 原厂 PDF URL 及 www 别名本次实际均返回 404；仅有搜索索引，不能冻结当前供货规格或完整图纸。索引给出控制类别，没有可执行命令字典 |
| T4i PERSEUS，DSH_000010_05，2025/09 路径，PDF 第 2–3 页 | 原厂列 6DoF、450 Ns、2.5 U、干质量 2.5 kg、稳压 12 V、开阀 <30 W（毫秒）、点火 <20 W、预备 60 s；接口标为 RS422、HDLC-like；原厂宣称 TRL 9 | 无受控安装/喷口坐标图、允许并发组合、完整接插件针表或帧/CRC/指令/遥测字典；“10/10/29 mN”不能解释为已知编号方向 |

上表对应实际一手来源：[旧 MiPS 参数表](https://www.vacco.com/images/uploads/pdfs/MiPS_standard_0714.pdf)、[锁定 C-POD 参数表](https://cubesat-propulsion.com/wp-content/uploads/2022/04/X13003000-01_RCM_2016update.pdf)、[GomSpace 原厂索引对象（本次直接获取 404）](https://gomspace.com/UserFiles/Subsystems/flyer/Flyer_NanoProp_6DOF.pdf)、[T4i 产品总览](https://www.t4innovation.com/wp-content/uploads/2025/09/DSH_000010_05_T4i_Product_Overview.pdf)。GomSpace 搜索证据保存于 [参数索引原始响应](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/sources/propulsion_intake/PUBLIC_SEARCH_CAPTURE.json>) 和 [双模块配置索引原始响应](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/sources/propulsion_intake/GOMSPACE_CONFIG_SEARCH_CAPTURE.json>)；不是本地已取得完整 PDF。NanoProp 6U 的在轨经历也不能自动证明这个 6DOF 修订的成熟度。T4i 对 IPERDRONE.0 的原厂任务说明支持产品家族经历，仍需硬件/固件适用性绑定。

**C-POD 的版本冲突必须先解决。** [VACCO 官方下载索引](https://cubesat-propulsion.com/document-downloads/) 指向的另一份 [X13003000-01 参数表](https://cubesat-propulsion.com/wp-content/uploads/2015/10/Reaction-control-propulsion-module.pdf) 同样写 Rev 7/14，却列 R134a、25±5 mN、186 Ns、1244 g、响应 <2 ms；其 SHA 为 `2bf995824f1c4f2374fe3f7707e6b86f6b138d80bcd75cfdee938938019813a3`。此前冻结的产品页下载文件为 R236fa、10±2 mN、174 Ns、1330 g、响应 <10 ms，SHA 为 `86d9f4b73df5948fa89a11d83e7f25979530173ee4d79c65cdb30b642216c088`。当前产品网页还混有不同参数组合。因此型号加页脚年月不足以唯一识别配置，禁止择优拼接参数。

新版 [Standard MiPS 参数表](https://cubesat-propulsion.com/wp-content/uploads/2020/04/Standard-MiPS-datasheet-042120.pdf) 实际是 X19039000、Rev 4/20、4×25 mN、82–515 Ns，并非旧 X14029003-1 的新缺页。该版本有更多喷口安装角度信息，仍只有 RS422 名称，不能拿来补旧设备的针位或协议。原件均保存在本轮 intake 中。

**能力筛查只有必要条件，没有虚构喷口阵列。** 历史输入为角动量模长 3.65099 N·m·s、`propellant_budget_max_g=54.73476731425644` 和 `t_detumble_max_s=3600`（PROVISIONAL）；当前完整任务向量、允许平移、时间窗及整星质量/质心尚未绑定，不能继承旧科学 PASS。计算采用目录比冲 40 s 和标准重力 9.80665 m/s²。

若喷口力作用点全部包含在上一轮采用的紧凑模块包络中，且瞬时合力为零形成平衡力偶（或者固定姿态静态分配的积分合力为零），则以包络半对角线 R 为保守最大半径，有 `|ΔH| ≤ R·ΣJ_i`。ΣJ_i 是全模块各喷口累计标量冲量之和，不能给每个喷口分别分配一次目录总冲量。零合力使平移参考点项抵消，因此将整个紧凑模块外移，不能增加其内部平衡力偶的力臂。

| 条件量 | 旧 MiPS（89.0016×89.0016×30 mm） | 锁定 C-POD（98.5012×94.488×101.473 mm） |
|---|---:|---:|
| 包络半对角线 R | 0.064697 m | 0.085040 m |
| 全目录冲量形成的乐观角冲量上界 | 2.84665 N·m·s | 14.79697 N·m·s |
| 为 3.65099 N·m·s 所需标量冲量下界 | 56.43254 Ns > 44 Ns | 42.93260 Ns < 174 Ns |
| Isp=40 s 时所需推进剂乐观下界 | 143.8629 g | 109.4477 g |
| 若沿用历史 54.734767 g 预算，角冲量乐观上界 | 1.38907 N·m·s | 1.82586 N·m·s |

在上述条件下，旧 0.3U MiPS 即便使用全部目录冲量也不能覆盖历史模长；C-POD 的完整目录资源没有被这个必要条件排除，但历史推进剂预算不足。历史预算只等价于 21.47059 Ns，要求有效力臂至少 0.170046 m；C-POD 紧凑包络半径约为其一半。109.4477 g 也只是最有利上界推导出的最低需求，未包含实际喷口方向损失、留量、热工、泄漏或比冲变化。该判断不排除带非零合力、平移和姿态变化的复杂机动，也不证明 C-POD 实际三轴分配可行。

3600 s 对应所需平均力矩 1.01416 mN·m。若允许使用半径 R=0.085040 m 的理想反向双喷口，则每个喷口至少 5.96286 mN；实际 C-POD 能否形成这样的方向、力臂和持续组合仍待 ICD。若 PERSEUS 的 60 s 预备也计入该历史窗，剩余 3540 s 所需平均力矩为 1.03135 mN·m。这些是需求阈值，不是新闭环消旋仿真。

结构与电源的具体冲突如下。

- 旧共享舱分配为 110×160×75 mm，C-POD 最小边 94.488 mm 大于 75 mm，六种正交轴向置换均放不下，须重新分配局部安装空间。当前 WP03 外壳 366×226.3×226.3 mm 仅为外部尺寸，不能当作空置净空间或据此断言整星装不下。
- GomSpace 索引中的单模块长 200 mm 已大于旧分配最长边 160 mm；完整双模块体积合计约 2.2 L，且需要独立核对 5 V/32 V 供电配置。因原 PDF 未取得，这些仅用于排除“原位直接替换”的无依据假设，不冻结实体或电源规格。
- PERSEUS 的 2.5 U 与 2.5 kg 干质量需要重新分配；湿质量和完整安装图仍缺。若推进分支仅有稳压 12 V、2 A，则 24 W 不能保证覆盖厂家公布的 <30 W 开阀设计包络。<30 W 不代表实测恰为 30 W；需要厂家给出的实际电流/时长及保护协调证据，或经验证的支路瞬态供能设计。<20 W 点火对应上界约 1.667 A，也不证明预热和全并发峰值已覆盖。

**下一次最小资料输入已经具体到一个模块。** 优先提供 VACCO **X13003000-01 RCM/C-POD** 的原厂受控交付资料，明确它与上述锁定 SHA 的 R236fa/174 Ns/10±2 mN 参数表对应，或明确是哪个有完整替代关系的新配置。所需文件可合并为一份完整 ICD，也可分为下列四件；原厂文件编号和 ICD 修订目前未知，不能把参数表“Rev 7/14”伪写为 ICD 修订号。

1. 配置/交付适用性表：完整订货号、总装图号及修订、硬件修订、固件版本、保证性能与推进剂配置，明确处理两份同型号同页脚 PDF 的冲突。
2. 机械 ICD 或受控总装图：坐标系基准、每个喷口编号/出口 XYZ/单位力方向及指令编号关联、安装孔及公差、接插件配对和拔插空间、喷流限制、满载/空载质心与惯量。
3. 电气 ICD：接插件完整型号、针号视图、电源/回流/机壳与 RS422 TX/RX 极性针表、允许电压/纹波、阀和加热器启动及保持电流时序、并发负载、掉电/故障状态。
4. 与交付固件一致的软件 ICD/协议手册：链路设置、帧结构、字节序、CRC、地址/命令码、使能/禁止及超时/看门狗、最小脉冲/占空比/允许并发组合、应答与遥测缩放/状态位、可离线核对的协议向量。

这些是 Owner 可直接提供的受控资料对象，不要求本轮私联供应商。拿到其中一个针表或只给“RS422/HDLC-like”名称均不足以闭环。若当前坚持只采用本轮已经公开获取的资料，则应保留推进实际选型未定状态；不能由工程人员猜写针位或驱动协议填满交付表。

工程决策还须明确是否继续沿用历史 54.734767 g 预算及 3600 s 窗，并绑定实际角动量方向和允许平移。若坚持紧凑单 C-POD 平衡力偶路线，就不能同时原样保留该历史推进剂预算；至少需要按实际 ICD 重算后重新分配资源和舱位。该工作属于当前工程任务定义，不修改历史裁决。

[结构化证据与缺项矩阵](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/sources/propulsion_intake/REVIEW_EVIDENCE.json>)、[可复算脚本](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/sources/propulsion_intake/recompute_review.py>) 和 [检查结果](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/sources/propulsion_intake/REVIEW_CHECK_RESULTS.json>) 已保存。检查 **25/25** 通过，仅表示文件绑定、版本冲突记录和必要条件计算自洽，不是推进硬件 PASS。上轮 20.012432 kg 是 701 实例范围内有来源的分配小计，不能当作现行 705 实例整星质量；本轮没有更新质量、质心、惯量、CAD 或任何接受后的科学模型。
