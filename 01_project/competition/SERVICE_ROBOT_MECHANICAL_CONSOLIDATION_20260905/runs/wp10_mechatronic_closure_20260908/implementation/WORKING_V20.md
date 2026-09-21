# WP10 V20 当前工作件

本轮完成 C203 电容端接板的原生改件、CAM 对照和局部数字装配。整机机电详细设计仍有开放项；最后封装发布保持 V18。

| 对象 | 当前实际结果 |
|---|---|
| 整机原理图 ERC | 12 页重新执行：0 错误、0 警告，原忽略规则保持 |
| C203 原生 PCB DRC | 从 V19 的 6 项降为 0 项；0 未连接，规则未放宽 |
| 四处电气端接 | CAP 两孔 Ø2 PTH、WIRE 两孔 Ø1.8 PTH；另有四个 Ø3.4 安装 NPTH |
| CAP 板面 | 保留背面 Ø3.5 铜环；前面无铜环、Ø3.5 阻焊开窗；孔周裸基材面 X=-6.99 mm，其余座面 X=-7 mm |
| 三态装配清单 | 各 972 行：965 父行保持、PCB 与四颗螺钉按现行表面定位、两根导线 |
| 精确局部检查 | 每态 31 组邻件、9 处名义接触通过；非整星全局／连续动作检查 |
| 电热分账 | 384 状态、4800 行；线长及电阻保持，实际纹波与温升仍待确定 |

[查看页面](WORKING_V20.html) · [局部装配 STEP](mechanical/cap_harness_assembly.step) · [PCB STEP](mechanical/input_cap_pcb.step) · [装配清单](mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json)

[当前机器证据](results/CAP_PTH_WORKING_STATUS_V20.json) · [ERC](results/SYSTEM_ERC_NATIVE_V20.json) · [DRC](results/CAP_TERMINAL_DRC_NATIVE_V20.json) · [CAM 核验](results/C203_CAM_CHECK_V20.json)

![当前原生装配快照](review/CAP_HARNESS_ASSEMBLY_V19.png)

部分活动文件沿用 V19 文件名；当前版本以 V20 状态文件内 SHA256 为准。历史 V19 文件已归档。STEP 可作为 SolidWorks 的导入几何，本轮未生成新的 SLDASM／SLDPRT。

独立审阅发现并修复了 CAM 校验器的终止标记、清单、文件角色和检查回执绑定问题；16 个 CAM、13 个源／绑定反例拒绝通过。首次 PCB 生成因模块导入失败，已修复并实际重生成，未计成功信用。全部最终原生作业串行完成。

尚需完成：焊接和孔桶工艺、线束应变释放与工具空间、CHB 局部板面、主回路故障保护与停止／回生动态、整星热路径、电池／PMM、推进同修订接口及任务能力、整机公差和连续动作验证。0 ERC／DRC 只说明已启用规则下本轮检查通过；不能据此宣布整机完成或制造放行。
