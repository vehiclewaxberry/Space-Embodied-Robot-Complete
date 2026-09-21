# 停止监督逻辑的实际离线实现

`stop_supervisor.py` 是本轮实际运行的状态逻辑源，`test_stop_supervisor.py` 检查启动、显式复位、新运行上升沿、遥测重复、七类故障与 UNKNOWN、正常降能顺序。无 CAN、串口或机械臂 I/O。

正常停止保持供电，直到残余能量有界且机械支撑已接管，才请求撤掉 K1。异常故障产生故障锁存和撤线圈请求；这只是命令反应，不证明失去力矩后载荷安全。`CONTACT_OPEN_REQUESTED` 不等于主触点已经开断；实际辅助触点与负载侧电压必须分别观测。辅助 NO 不是认证镜像触点。

调用顺序：物理接口适配器验证时间戳和实际接线 → 将经过量程/断线诊断的状态放入 Observation → 调用 step → 把命令送入独立硬件允许链。`binding_verified` 是适配器的输入合同，不能靠应用随意置 true 获得硬件放行。没有物理适配器时，所有观测默认 None、绑定默认 false，执行保持禁止。

该文件没有实现 MCU 引脚、硬件看门狗、线圈驱动、主触点分断时间、母线放电超时或回生功率级，也没有执行 MotorBridge 的 Rust 本体。实际控制电路仍未闭环，不能将这组测试用于清零这些责任。

TPS3431 可采用 SET1 高、CWD 经 10 kΩ 接 VDD 的 170–230 ms 超时，但 WDO 在 EN 拉低时会回到高阻，因此只使用 WDO 将漏掉禁止状态。ENOUT 必须参与禁止链，故障解除后另需锁存和显式复位；该时限不能冒充现有 0.1 s 故障分断要求。来源见 `../sources/power_intake/TPS3431_datasheet.pdf` 第 3、6 页。

复算：使用 Python 运行 `../tools/verify_stop_policy.py`；机器结果在 `../results/STOP_POLICY_TESTS.json`。物理动作、刷写与接电均未执行。
