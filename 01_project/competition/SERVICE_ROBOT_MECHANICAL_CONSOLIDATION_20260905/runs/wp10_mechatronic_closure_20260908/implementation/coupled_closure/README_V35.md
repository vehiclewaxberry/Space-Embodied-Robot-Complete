# WP10 V35 · 当前整机进度与电源时序 PCB

结论：系统详细设计与局部验证阶段；全部电气选型、完整机械装配和真实推进任务能力均未完成。本版可交付源文件供设计审阅，不能作为制造、接电或飞行放行。活动电气V35，几何V30/V28，输入基线V31。

本版新增THN启动电压监督与独立偏置，辅助板60×70×1.6 mm、26个电气封装、6安装孔；新器件最高标称18 mm，尚未置入整舱。主输入板43个电气封装沿用V34字节相同源。整机237位号/767针脚记录/15页原理图；ERC0，辅助DRC0，主板继承V34 DRC0。ERC4类和DRC5类忽略项保留并列于VERIFICATION.json，零违规不表示所有可能规则与性能均已通过。

两块板作用：主板提供输入预充、限流和功率开关接口；辅助板从同一电池的独立支路供给THN/STOP，并增加电压资格与启动延迟。辅助板不会为机械臂直接供给360W，也不承担电机制动能量吸收。低压启动恒功率反例促成本轮时序设计；它独立于主开关，共用电池。

U208 TPS3760A015DYYR经200k/10k分压监测AUX，U209 LT3013提供约6V偏置。D209/D210只保持监控器供电，许可仍来自AUX电压；不自动授予RUN。R231改1.8k，计入THN源向0.5mA和D210反漏1mA场景，净最小负载1.66258mA。释放电压17.323–17.960V；下降阈值16.502–17.102V；冷态RC部分97.28–167.46ms，温态残压可缩短。延迟参数的特定过驱动测试条件不可扩大成任意故障响应上界。

96个假设导通工作点保留360W臂筛查需求与16.8W辅助输出，加30mA控制支路分配，完成独立KCL/KVL和分项热账核对。84点满足新的释放电压条件、12点不能获得新释放；不是84次硬件启动通过。180个充电包络和20个CTR残压场景用于寻找反例，未完成联合时域。30mA不是原厂保证，THN内部输入电容、启动电流、eFuse热跳闸时间与STOP短掉电仍未知。REMOTE线开路时THN默认开启，故本时序不能计作独立停止屏障。

原873组件宿主仍为三个固定姿态；974实例/2922姿态是源计划，未回装为新总装。V30局部主输入56子件/60实体尚未安装，不应与974计划机械相加后宣称完成。parking不是发射收拢；配合、连续运动、真实整机质量/COM/惯量尚未形成一致验收。V31物性记录有270项CAD估算、94项数字来源、610项未知；不能把旧“全是水密度”概括作为现状。DM公开模型约2.74448kg与4.5kg参考差异仍需解释。

V33加厚热板试验继续拒绝：计入板端热分配后CHB约105.837–107.214°C，超过105°C；三个安装短名单分别8/7/7处交叠。只代表这些方案被拒绝，不是所有12U布局都不可行。下一步应实际重排模块与补真实TIM—承载件—外部固定辐射面，不继续仅加厚。

推进已有目录资源筛查、候选安装及合成阵列反例；实际C-POD同修订喷口位置/方向、并发、最小脉宽、羽流/指令和当前COM尚未绑定，真实六自由度任务能力UNKNOWN。继续复用完整商业推进模块，不自制压力内部件。

成熟案例能够复用：B601 DM继续用原厂开源机械/驱动/软件；OreSat参考背板、配电和监测架构；P60在额定范围内承担低功耗配电。公开完整同构12U+B601系统尚未取得。现有模块的母线电压、电流和失电行为需匹配本机，不能凭飞行案例名直接替代接口验证。GomSpace PDU-200公开单通道2A，不等同本机24V/15A筛查路径；这是接口不匹配判断，不是该模块质量问题。

下一步执行顺序见NEXT_ENGINEERING_ACTIONS_V35.csv：STOP/回生故障行为和剩余PCB→储供电与全周期能量→热结构与舱内安装→构型/配合/物性与原生回装→推进真实接口和当前COM任务能力→同版本整机验收。推进ICD收集可与内部改件并行。实测、外部文档、内部设计分别管理，未测量项目不回填PASS。

查看：整机PDF第13页为新时序图；原生入口ecad/revisions/v35/wp10_system.kicad_sch。主板/辅助板分别为wp10_main_input.kicad_pcb和wp10_aux_protection.kicad_pcb。已保存文件供KiCad重新加载查看，不宣称MCP与GUI实时同步。SYSTEM_BOM是混合系统位号清单，部分型号在Value文本；55项具有结构化MPN字段，不是只有55项曾选型，也不是237件均可直接采购。

复算：在原工作区implementation下运行tools/calculate_sequence_v35.py，再运行tools/verify_sequence_v35.py。原生作业串行使用native_delta_guard.py，启动可用内存≥2GiB；仅清理已识别的相关进程工作集。包内保留依赖路径和哈希，完整审计依赖原工作区；标准3D库依赖KiCad10，本版未生成全装配3D模型。

原厂资料：
- [B601 DM说明](https://wiki.seeedstudio.com/rebot_b601_dm_getting_started/)
- [THN30WIR](https://www.tracopower.com/products/thn30wir.pdf)
- [TPS3760](https://www.ti.com/lit/ds/symlink/tps3760.pdf)
- [LT3013](https://www.analog.com/media/en/technical-documentation/data-sheets/3013fe.pdf)
- [STPS3H100 Rev3](https://www.st.com/resource/en/datasheet/stps3h100.pdf)（公开PDF已核读；本机原PDF下载超时，包内明确为资料摘记）
- [OreSat子系统](https://www.oresat.org/technologies/cubesat-subsystems)
- [P60 PDU-200](https://gomspace.com/UserFiles/Subsystems/datasheet/gs-ds-nanopower-p60-pdu200-26.pdf)
