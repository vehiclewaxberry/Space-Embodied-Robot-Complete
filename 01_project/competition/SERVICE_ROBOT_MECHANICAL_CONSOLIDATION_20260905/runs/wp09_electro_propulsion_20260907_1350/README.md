# WP09 电气与推进部件机械设计候选

本轮完成三套可查看的局部 STEP 模型，共44个局部实体；其中A3200与MiPS交付28个验证过的原生零件文件和2套SolidWorks固定定位装配。三套源几何检查共726项通过，专项检查了电池连接的实际接触面积；另两套完成原生冷重开与STEP回导材料等价。电池沉头螺钉跨内核导入仍不合格，因此电池原生装配保持HOLD。可继续硬件型号绑定和受控整星布置调整，整星电气、推进、实物装配与制造放行尚未完成。

## 直接查看

| 组件 | 可查看文件 | 局部检查 | 回导材料检查 |
|---|---|---|---|
|电池载板—甲板固定（16实体）|[打开源 STEP（原生HOLD）](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/candidate/battery_mount_v2.step>)|[322项通过](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/results/battery_mount_v2/CHECK.json>)|[未通过转换](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/results/BATTERY_NATIVE_BLOCKER.json>)|
|A3200 参考载板（22实体）|[打开 SLDASM](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/native/a3200/WP09_A3200.SLDASM>)|[341项通过](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/results/a3200/CHECK.json>)|[73项通过](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/results/a3200_NATIVE_MATERIAL_CHECK.json>)|
|MiPS 推进外托架（6实体）|[打开 SLDASM](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/native/mips/WP09_MIPS.SLDASM>)|[63项通过](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/results/mips/CHECK.json>)|[24项通过](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/results/mips_NATIVE_MATERIAL_CHECK.json>)|

已交付的两套SolidWorks零件为源STEP导入实体，装配采用固定定位，没有可动配合。native目录还保留失败诊断文件；有效交付仅限上表与BOM所指28件。尺寸合同和构建源位于 inputs/ 与 candidate/，可按合同改版重建；当前原生实体没有完整的特征历史。保留 native/<模块>/parts 全部依赖；尚未进行异机路径迁移测试。

## 本轮实际变化

- 电池：在既有载板/下设备甲板源实体上完成4处沉头座和甲板通孔，加入12个目录紧固件；固定的是载板，电池本体压紧、防窜和绝缘仍未定。三态新增硬件/邻件筛查与工具空间分阶段核验。顶部工具在电池/热垫装入后受阻，要求先固定载板再装电池；底部工具只证明接近螺母外端的空间。
- A3200：85×60×2载板、4根3mm支柱、65×40×1.8 PCB参考板及M3紧固堆栈。厂家图中部分孔位通过对称性推导；没有真实器件、铜层、完整FSI连接器和绝缘/热设计。参考依据：[GomSpace A3200 DS1006901 Rev2.0](https://gomspace.com/wp-content/uploads/2025/09/gs-ds-nanomind-a3200_1006901-2.0.pdf)。
- MiPS：依据厂家外形与两侧4-40 UNC-2B孔基准建立非承压外托架和4片接口垫。透明体为最大外形包络；螺孔有效深度、螺钉长度、端口和三维喷口/羽流资料未知。局部托架当前高97mm，不能按当前姿态进入75mm共享舱。参考依据：[VACCO Standard MiPS](https://www.vacco.com/images/uploads/pdfs/MiPS_standard_0714.pdf)。

## 研究已识别的布局与电气约束

P60 各份资料的尺寸口径均不能装入现有65×70×30 EPS预算；BPX单块外形有可行排列，双块的全部轴对齐并列方式失败。MiPS单盒的可行排列要求30mm深度沿现有预算Z轴，但尚未证明与ADCS共存。A3200单载板可继续细化，其箱体还承担通信设备，不能独占预算。完整计算见 [包络筛查](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/results/COMPONENT_ENVELOPE_SCREEN.json>)。

P60的24V降压选项要求电池最低输入大于25.5V，不能覆盖本轮BPX候选的全部低电压工作段；机械臂应单列稳压、保护、回生处理和导热安装设计。实际B601版本/电流谱未确认，未按地面电源铭牌冒充航天功耗。来源和相互冲突的口径见 [电气资料核验](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/research/ELECTRICAL_HARDWARE_RESEARCH.md>)。

## 工程交接

BOM的 `size_x_mm/size_y_mm/size_z_mm` 为源实体轴对齐包围盒尺寸（mm），不是安装位置。安装坐标与变换以各组件合同和尺寸卡为准。BOM含代理设备/功能包络，不能直接作为采购或质量预算清单。

- [尺寸与装配顺序卡](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/docs/DIMENSIONS_AND_ASSEMBLY_SEQUENCE_ZH.md>)
- [44项局部实例 BOM](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/docs/LOCAL_INSTANCE_BOM.csv>)
- [12项后续机械工程工作包](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/docs/ELECTRO_PROPULSION_MECHANICAL_WORK_PACKAGE_ZH.md>)
- [推进硬件来源核验](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/research/PROPULSION_HARDWARE_RESEARCH.md>)
- [受控布置调整依据](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/research/MECHANICAL_ALLOCATION_DECISIONS.md>)
- [机器交付状态](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/results/DELIVERY_STATUS.json>)

三组局部模型均未合入 WP08 的625实例整机，也不包含此前未合入整机的后肋板局部候选。现有整机、质量预算、科学 Gate 与历史负结果保持原样。

## 运行记录

A3200 首轮原生导入触发512MiB空闲内存保护；已核对唯一中断时保存的干净文件，退出空CAD会话，分批恢复并完成22件冷重开和材料等价。原始保存API确认在该一件上仍为UNKNOWN；后续检查证明文件可读与几何一致，不回填旧确认。首轮原生回执与守卫日志原样保留。

电池初版主锥角识别采用了合同外角度阈值，首轮失败保留；修复识别后实际接触面积仍为零，第二次失败亦保留。修正版仅把沉头座解析参数匹配到目录螺钉实际主锥，独立重查去材、接触、邻件及工具空间；名义90°尺寸和原接受阈值保持，未给加工公差或强度信用。

直接STEP导入电池沉头螺钉的四次尝试因COM极值检测与源相差约5.639µm而失败。补充高精度体积、极值点与源距离、原生STEP回导诊断未建立等价证明，故原失败保留。随后源STEP→IGES BRep回读29项通过，但两种SolidWorks IGES实体导入模式均只得到7个曲面体、0个实体，未建立电池原生装配。失败曲面文件已保存用于诊断；当前可查看的电池交付为已验证源STEP。转换HOLD详情见 [电池原生阻塞记录](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/results/BATTERY_NATIVE_BLOCKER.json>)。验收阈值未放宽。IGES检查初版的内核零值断言和第二版临时文件替换失败均保留；修正版仅解释内核固有1e−7mm底线并为临时文件替换的访问拒绝增加短暂重试，不改变几何。

交付复查意见见 [独立于CAD执行的文档和证据复查](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/docs/INDEPENDENT_DELIVERY_REVIEW_ZH.md>)。该复查是时间快照；后续原生转换结果由上表当前机器回执给出。MiPS检漏/功能检查已明确划为未来供应商许可规程阶段。

## 预览

### A3200 参考载板

![A3200 参考载板](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/viewer/a3200_iso_20260907T050951Z.png>)

### MiPS 推进外托架

![MiPS 推进外托架](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/viewer/mips_opposite_20260907T051032Z.png>)

### 电池载板—甲板固定

![电池载板—甲板固定](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_electro_propulsion_20260907_1350/viewer/battery_mount_v2_opposite_20260907T053548Z.png>)
