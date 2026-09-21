# 下一授权动作

当前自动授权只到 R5 派生证据与 Owner 审阅，`next_stage_authorized=false`。R5-G5 已闭合，无需再次追赶 Runner 生命周期。

1. 由 Owner/需求权威签发绝对残差合同，分别给出 `P_abs_max [kg·m/s]`、`H_abs_max [N·m·s]`，并绑定惯性系、固定参考点 O、系统边界、场景、时域、求解器、步长、比较关系、来源、批准人和生效时间。不得从本轮数值结果反推阈值。
2. 由机械/需求权威裁决两个 P 关节到底是锁定结构还是动态夹爪自由度，并给出物理位置、速度、effort 限位 authority；该决定必须进入新版本 plant，不得追溯改写 R5 冻结 plant。
3. 上述 authority 闭合后，R6 才可从 SPART 的 accepted-URDF FK、Jacobian、浮动基座质量矩阵与 P/H 独立对拍开始；当前 R6 仍为规划态，不安装或执行外部后端。

若继续在低内存主机运行，必须重新采样内存并继续保留 `memory_gate_passed=false` 与 Owner Override 证据；不能把释放进程、分页文件或成功完成一次运行解释为 6 GiB 门 PASS。

