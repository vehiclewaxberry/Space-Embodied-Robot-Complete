# WP10 分层电气 BOM
本表从实际新网表和停止电路BOM生成。99个实际原理图ref唯一映射，其中23个顶层设备/边界，76个停止电路子项；另保留父版未进网表的8个参考责任项。共107行。
STOPBOARD是装配父项，不重复采购或累加子件质量。5个J符号是逻辑边界，未选定实体连接器，不能据引脚编号直接制线。J101.1/.2现为内部电源TEST端，禁止外供；输入仍为J101.3上游保护24V与J101.4回流。
B601套装与分线板/USB-CAN、ODrive及随附电阻的采购去重规则沿父表保留。候选料号不表示收到、下单授权或制造放行；所有未知质量保持空。
新的辅助供源、预负载和TC4420驱动器属于有界GSE静态设计。典型纹波、启动/瞬态、PCB散热和实际母线诊断未闭合，不据BOM完整性签发整机电气完成。
来源母表：F:\China Graduate Future Flight Vehicle Innovation Competition\01_project\competition\SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905\runs\wp09_interfaces_20260907_1525\system_completion\ecad\MASTER_BOM.csv
当前子页：F:\China Graduate Future Flight Vehicle Innovation Competition\01_project\competition\SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905\runs\wp10_mechatronic_closure_20260908\electrical\STOP_BOM.csv
