# B601 DM 实际原生接口与关节映射增量

本次已实际加载官方 PyPI **MotorBridge 0.5.3 / CPython 3.13 / Windows x64** 分发包中的 `motor_abi.dll`，完成 18 项元数据、空句柄、未绑定控制器生命周期和 Python→真实 DLL 错误传播检查。没有使用假 ABI，没有打开串口或 CAN、添加电机、发送真实使能或动作。原生 MIT 编码和串口数据路径仍未执行；不能将这次 ABI 验证扩大成实机通信通过。

安装方式为工作目录内解包，不修改系统 Python。原始 wheel 的 SHA256 已与 PyPI 发布元数据核对；Python 绑定与既有锁定提交一致。DLL 的身份由官方 wheel 摘要、ABI 版本和能力表绑定，没有本机重新构建或二进制提交证明。错误选取但未执行的 cp310 wheel 仅保留在 sources 中，现行索引明确选择 cp313。

- [实际原生验收回执](../results/DM_NATIVE_VERIFICATION.json)
- [公开关节映射增量](../results/DM_PUBLIC_REFERENCE_DELTA.json)
- [现行禁止物理执行的配置](DM_REFERENCE_CONFIG.json)
- [串行链路预算](SERIAL_BUDGET.csv)
- [原厂配置及提交清单](sources/seeed_dm_config/manifest.json)

Seeed `reBotArm_control_py` 的提交 `1bcd81b22c182ec257bf04f5746e1e3d556a5f1c` 明确将 J1–J3 绑定 4340P，J4–J6 和夹爪绑定 4310；电机 ID 1–7、反馈 ID 0x11–0x17。这补齐了公开参考设计的逐关节型号。实机修订、方向、零位、传动比、机械限位和插头视向仍未知。没有把上游示例增益/速度值当成经过本服务星工况验证的允许值。

同提交的通用 `rebotarm.yaml` 默认转向 **RS** 配置，因此本设计明确引用 DM 专用配置，禁止自动选择通用配置。

锁定 `dm_serial.rs` 明确使用 8N1、30 字节 TX 和 16 字节 RX。921600 baud 下理想 TX 上限为 3072 指令/秒。七轴各 500 Hz 需要 3500 指令/秒，占 113.93%，不成立；六臂轴 500 Hz、夹爪不发送时也已占 97.66%，尚未计参数请求和桥接排队。六臂轴 250 Hz 加夹爪 50 Hz 是占 50.46% 的预算例，不是已经选定或验证的闭环控制频率。全双工收发分别计账，不将 RX 字节简单加到 TX。实际 USB 延迟、CAN 速率和驱动调度仍需绑定后评价。

离线复算：运行 `verify_native_abi.py` 和 `build_dm_reference_delta.py`。取得新公开资料不覆盖父包的旧快照和检查身份，也不修改 accepted URDF 或历史科学 Gate。
