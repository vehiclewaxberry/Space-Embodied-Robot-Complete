# 原生电气与 DM 离线源可迁移参考包

这是已封存 WP09R 原生电气工程的原样快照，MASTER_FROM_TO.csv 的内容及身份保持不变。
打开 ecad/wp09_system.kicad_pro 查看总原理图，打开 ecad/rs422_gse_splice.kicad_pcb 查看独立地面转接板。
软件参考位于 software/，原样上游源码及 MIT 许可证位于 sources/motorbridge/。
本包在新的本机目录实际重新导出系统网表并核对全部网络、重新执行地面板 DRC 与 29 项 Python 离线测试。
系统仍有原有一项停止链电源边界 ERC 问题；没有新增真实停止驱动或推进控制电路，没有进行硬件 I/O。
离线测试为 Python 移植及 AST/假 ABI；Rust 本体、FFI 和设备后端没有运行。
原 README/来源回执中的绝对工作区路径属于来源记录，不代表另一台机器存在这些路径。
本包验证的是原生文件及上述离线路径可用，不代表完整系统功能或所有工程生成器可异机复现。
