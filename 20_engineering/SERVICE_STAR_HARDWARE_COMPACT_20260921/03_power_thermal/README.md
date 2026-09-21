# 能源、电热与热控辐射设计输入

本目录保留模块电源选型、接口、热结构参数和B2候选热阻计算。当前装配实体见 [机械目录](../01_mechanical/)，电路与现行器件表见 [电气目录](../02_electrical/README.md)。本目录未闭合整星能量、充电、实际负载和当前装配热验证。

## 当前设计入口

| 内容 | 入口 | 范围 |
|---|---|---|
| 模块电源架构 | [POWER_CHAIN_SELECTION](power/POWER_CHAIN_SELECTION.json) | RRC3570-4电池、CHB500W-24S24N转换器及独立AUX等候选；RRC-PMM35的充电/并联负载接口未闭合 |
| 共用电池路径 | [SHARED_BATTERY_PATH_DEFINITION](power/SHARED_BATTERY_PATH_DEFINITION.json) | 分支电压面和设计负载分配；不是实测功耗与完整电源预算 |
| 电池机械/连接边界 | [BATTERY_INSTALLATION_INTERFACE](power/BATTERY_INSTALLATION_INTERFACE.json) | 公开包络/接口与未确定OEM针脚 |
| 当前分流器电热叠加 | [ELECTROTHERMAL_INPUT_UPDATE_R5E](electrothermal/ELECTROTHERMAL_INPUT_UPDATE_R5E.json) | R202=0.5 mΩ；未知负载、结温、有效电容保留UNKNOWN |
| 固定热路径与底板 | [FIXED_HEAT_PATH](thermal/FIXED_HEAT_PATH.json)、[BOTTOM_RADIATOR_MOUNT](thermal/BOTTOM_RADIATOR_MOUNT.json) | 机械热路径参数；上游阶段状态保留，需与现行机械布局联合解释 |
| 辐射与热网预算 | [FIXED_RADIATOR_BUDGET](thermal/FIXED_RADIATOR_BUDGET.json)、[SPATIAL_RADIATOR_NETWORK_SCREEN](thermal/SPATIAL_RADIATOR_NETWORK_SCREEN.json) | 既有简化模型的范围、热负载遗漏与边界条件；非当前完整装配的热验收 |
| B2设计目标 | [双纵梁需求反解](architecture_b/results/thermal_architecture_20260917/THERMAL_ARCHITECTURE_B_DESIGN_TARGETS_20260917.json) | 候选设计，未落实为已验收装配 |

旧 `POWER_LOOP_PARTS.json` / `SELECTED_BOM.csv` 中 R202仍为0.2 mΩ，旧 `POWER_BUDGET_SCREEN` 已自标过期，因此不作为本包现行来源。模块参数与早期热负载表被保留为设计输入，位号选型必须以R5E/当前PCB为准；完整回路、充电与全热负载预算需要统一更新，不能将不同阶段的通过项相加。

## TIM版本与适用对象

[当前冷界面合同](thermal/COLD_TIM_INTERFACE_CONTRACT.json) 和 [材料依据](sources/COLD_TIM_SELECTION.json) 为CHB底面一处及两侧冷指界面指定 BERGQUIST SIL PAD TSP1800ST，名义未压缩厚0.203 mm。它替代上游 `power/THERMAL_INTERFACE_CONTRACT.json` 的TSP1600S局部前序方案；旧文件不在本包作当前入口。实际压缩厚度、压力分布、预紧、介电与接触热阻仍未验证。

R6H为机械臂主机接口新建的0.5 mm绝缘垫与4 mm铝热桥属于另一接口。该0.5 mm垫的材料、耐压、压紧与发热输入仍UNKNOWN，不继承TSP1800ST的选型或试验信用。刹车电阻等其他TIM也不能自动沿用CHB合同。

## B2候选与验证缺口

B2每侧双纵梁的83.2–86.9°C仅是联合声明下限下的热阻估计，保守点仍超过85°C目标；梁/界面、边界温度、未分配热和质量代价需要FE或试验收敛。它不是当前装配已经拥有的完整热通路，也不是辐射热控完成证明。

[筛选源码](architecture_b/tools/thermal_architecture_b_screen_20260917.py) 和 [需求反解源码](architecture_b/tools/thermal_architecture_b_design_targets_20260917.py) 为Python标准库的稳态1-D工程计算，输出到同级 `architecture_b/results`；运行会重写副本输出。本次仅保留源码与结果，不重跑大模型，不包含FE求解器、完整射线网格或过程日志。源码内嵌的上游证据锚点有出处，相关历史求解档案未全部随包复制。

[逐文件来源](SYSTEM_COPY_MANIFEST.csv) 与 `sources` 只记录公开URL/摘要/哈希，未收录厂商PDF全文。参数文件内来源路径保留原样，仅用于追溯。
