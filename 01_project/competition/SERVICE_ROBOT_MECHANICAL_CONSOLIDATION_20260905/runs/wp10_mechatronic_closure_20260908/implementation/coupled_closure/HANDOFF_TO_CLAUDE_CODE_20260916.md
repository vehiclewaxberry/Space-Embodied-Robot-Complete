# WP10 同候选工程交接 · 2026-09-16

本文件用于用户因额度限制转交 Claude Code。交接准备已完成；不表示 Claude Code 已启动，也不表示整机设计完成。继续原 WP10，主执行者唯一写入，最多一位只读审阅者分波工作，原生 CAD/KiCad 串行。

## 首先确认的当前状态

工作根目录 `F:/China Graduate Future Flight Vehicle Innovation Competition`。

下文 A 指 `01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation`，所有相对路径均相对 A。

| 对象 | 当前证据与裁决 |
|---|---|
| 正式活动版本 | `CURRENT_WORKING_CANDIDATE.json` 仍指 V35；不要直接提升为 V36 发布 |
| 正在编辑的源 | `ecad/revisions/v36/wp10_system.kicad_sch` 及同目录子页/库 |
| 最新原生检查点 | `results/stop_v36/pcb/native_checkpoint_20260916/CHECKPOINT_VERIFICATION.json` |
| 最新原生网表 | 上述目录的 `wp10_system.xml`：240 电气位号、777 针脚记录 |
| 最新 ERC | 上述目录的 `SYSTEM_ERC.json`：15 页、零错误、零警告；继承的4类忽略规则未改变 |
| STOP 物理映射 | 94 个选定落板位号均在新网表有匹配封装；温敏电阻 RT311–313 属于板外 |
| STOP PCB | `wp10_stop_control.kicad_pcb` 尚不存在。94 是选定器件数，不是已布线器件数 |
| 实物、制造与飞行 | 未执行试验，未放行；整机详细设计尚未闭合 |

最新检查点对导出前后所有原理图、库、项目文件和封装作哈希比对，并记录实际 CLI 命令及返回码。它只验证源连接及封装映射，不证明停止时序、功率、散热、布线或机械装配。

## 本轮已经落实的修改

1. 修复 J106 的实例归属：改回 `wp10_system` 的实际根/子页 UUID，补 MPN、厂商、板归属。六针为 TEMP1/RETURN1/TEMP2/RETURN2/TEMP3/RETURN3。
2. 补齐 U311–313、R341–349、C311–313 共15件原理图实例中真正缺失的 Footprint。此前 MCP 报批改成功，但仅选型清单有封装；现已通过新原生 XML 逐件核验。
3. 新增两个原生 KiCad 封装：`ecad/revisions/v36/WP10_STOP.pretty/TPS3431_DRB0008A.kicad_mod` 和 `Vishay_PR02_P15_24.kicad_mod`，并注册新封装库。
4. TPS3431 采用原厂4218875/A图：焊盘列 x=±1.4mm、节距0.65mm、信号焊盘0.6×0.31mm、主露铜焊盘1.5×1.75mm，pin9接ARM_RETURN。已加入铜指和独立钢网开口；可选散热过孔尚未在板上实现。0.3mm向内偏移的错误解释已排除。
5. PR02采用工程成形脚距15.24mm、成品孔1.1mm、焊盘2.2mm，原厂本体上限D3.9/L1=10/L2=12mm。成形脚距与孔径是工程选择；本体至少离板1mm，不能宣称OEM固定成形封装或热试验通过。
6. 为旧 `tools/audit_stop_v36.py` 增加陈旧输入拒绝保护，防止“当前源哈希+旧XML/ERC”被重新包装成通过。回归已证明：拒绝发生于修改旧结果之前。

新增脚本：`tools/build_stop_footprints_v36.py`、`reconcile_stop_pcb_metadata_v36.py`、`export_stop_checkpoint_v36.py`。第一次封装生成遇到API兼容错误，已修正；成功记录是 `logs/native_delta_stop_v36_footprints_20260916_r5.run.json`，新导出记录是 `logs/native_delta_stop_v36_current_export_20260916.run.json`。历史失败日志保留。

## 不可混用的旧结果

- `ecad/revisions/v36/wp10_system.xml` 仍是239/771的前一检查点；当前新网表位于上表新目录。后续建板必须明确读取新网表，不能因文件名相同而误读旧文件。
- `results/stop_v36/SOURCE_VERIFICATION.json`、同层 `SYSTEM_ERC.json`、旧 BOM/针脚CSV仍为历史结果，不能证明当前源。V36目录复制来的V35报表/PCB也不能自动视为V36全量交付。
- `coupled_closure/PROGRESS_PLAN_V35_V36.html` 是09-14规划页面；以本交接及09-16原生检查点为最新事实入口。
- `tools/prepare_stop_pcb_v36.py` 已执行检查点创建，不能重跑。恢复点为 `history/V36_STOP_SOURCE_BEFORE_PCB_20260915/`，不要覆盖。
- 旧 `finish_stop_source_v36.py` 只认识四个早期修改实例；不要用它替代新的元数据修复。

## 接手后的第一组实际工程工作

1. 先验证 `HANDOFF_SNAPSHOT_20260916.json` 中源哈希及最新导出收据，读取项目 AGENTS.md 和原WP10_GOAL附件，不全盘重审、不重新生成整机外形。
2. 完成已经分析但**未落地**的温监滤波：R350–352各1k，仅串接原始NTC节点到各TLV6700的pin3；8.2k上拉和649k分压支路仍留在原始节点。C314–319各1nF C0G，分别从三路pin3滤波节点、pin4开路监测节点到ARM_RETURN。精确电容MPN、容差、延迟须绑定资料和计算后写入。
3. 三组NTC必须独立成对回线，不能在外部共地旁路断线检测。输入RC不等于线束ESD或误接24V保护；跨路短接和启动过程仍需核验。若9件全部实际加入，源计数预计249、板选定计数103，最终以原生导出为准。
4. 更新新导出脚本的明确差量合同：当前合同只允许J106增量与94封装，不能硬改计数凑通过。用新的唯一tag导出新XML/ERC，校验新增9件的逐针连接、滤波延迟及负控制。
5. 使用新网表创建 `ecad/revisions/v36/wp10_stop_control.kicad_pcb`。90×70×1.6mm两层是当前分配，尚未安装进873组件宿主。布置接口、TSR稳压器、PR02、Q101、U112、看门狗及温监；完成网表对应、实际布线、DRC、丝印/插拔与元件净空。
6. PR02两件现有持续损耗筛查约1.23008W，未含TSR损耗：置板边并与120pF定时电容、精密分压和塑料接口分开。Q101 TO220金属片属漏极，不能默认接机壳地。
7. 分波只读复核STOP失电、欠压、断线、过温、卡键、人工复位、接触器释放及重新启动；UCC27517输入电流最大值未获公开保证，当前静态条件计算不能填成全工况已验证。

当前新检查点可用以下方式重新生成到一个**未使用过**的tag（只有源未改变时可直接使用现有合同）：

```powershell
$wp10Impl = 'F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation'
Set-Location -LiteralPath $wp10Impl
& 'G:/Windows_program_file/Anaconda/python.exe' -B -X utf8 tools/native_delta_guard.py native_delta_stop_v36_review_20260916_b -- 'G:/Windows_program_file/Anaconda/python.exe' -B -X utf8 tools/export_stop_checkpoint_v36.py --tag 20260916_b
```

## 整机目标继续保持

保持873组件/99位号父本及原37行闭环表、360W机械臂筛查需求。STOP板完成后，继续闭合负载侧回生与独立供电、20A路径和单针10A约束、充放电与太阳阵补能；实际修改CHB—TIM压紧—承载件—固定辐射面、电池/PMM安装和舱内布局，再回装同一宿主。

正式V35记录仍有：联合启动和人工复位未验证、全周期能量未闭合、V33热结构候选被拒、完整约束装配/收拢构型/物性未完成、真实推进任务能力未知。不得把旧质量或默认水密度当作当前整机惯量。

推进继续采用完整成熟模块集成。C-POD同修订喷口位置/方向、并发、最小脉冲、峰值电源和羽流ICD未绑定；禁止混用174与186N·s版本，禁止将合成阵列或目录总冲量作为本机任务能力。能完成的任务反推、接口合同和内部设计继续执行；外部缺项精确登记。

目标结束条件仍是同版本CAD/ECAD/线束/BOM/热/推进与逐项验收证据齐备。不得自动采购、联系厂商、制造、接电、动作、充装或承压。

## 资源与工具

- 启动内存≥2048MiB；运行可用内存底线512MiB；任务树RSS/Windows Job提交上限1400MiB；CAD/KiCad/COM/OCC串行。
- `tools/reclaim_cap_terminal_memory.py 唯一tag` 回收空闲工具工作集；`reclaim_background_checkpoint.py 唯一tag` 处理可确认的后台预加载器。脚本不会自动形成无限重试循环，清理后必须复测。保留当前用户会话与未保存窗口。
- KiCad MCP当前SWIG文件后端；写文件后重新加载，避免GUI旧缓存覆盖。原生CLI固定在工作区 `70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe`；KiCad Python为 `G:/Windows_program_file/Kicad/bin/python.exe`。
- 原理图新增/连线继续用MCP；缺少Footprint字段时以 `properties.Footprint` 创建，再用新XML验证。不能仅信工具“Updated”计数。
- 新空 `.pretty` 库需用原生 `PCB_IO_KICAD_SEXPR()` 显式读写，已写入封装生成脚本。
- 接手前仍应检查活进程。此次交接不启动任何后台设计任务，也不自动给Claude Code发消息。
