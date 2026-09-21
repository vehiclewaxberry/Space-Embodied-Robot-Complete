# DM 成熟协议复用交付

本包完成 WP-SW 的源码、适配接口和离线验收。锁定 MotorBridge 提交 `c48ebc4b2f250aa1f411a580d9d7b626e187040f`（Cargo 版本 0.5.3）；实际取得 18 个最小源文件，保留 MIT 许可证和署名。29 项离线测试通过，真实设备 I/O 为 0。这里没有把原自有 WPF1 改名为 DM 协议。

公开选型为 **100011896 → dm-serial，串口 921600 baud**。证据链是 [Seeed DM 快速入门](https://wiki.seeedstudio.com/rebot_b601_dm_getting_started/)明确给出的传输示例与其链接的 [SKU 100011896 产品页](https://www.seeedstudio.com/DM-CAN-USB-Driver-Borad-p-6706.html)。921600 不是 CAN 总线速率。这确定了公开参考适配路径，尚不等于实机出货板卡/固件已符合。

| 实际文件 | 内容与执行身份 |
|---|---|
| `../sources/motorbridge/` | 18 件原样上游源码与许可证；协议、串口封装、型号、寄存器、Python 接口均可审阅 |
| `dm_codec.py` | 锁定 Rust 纯函数的 Python 移植：MIT 打包、反馈解析、30 字节发送包、16 字节接收包；无设备 I/O |
| `dm_offline_adapter.py` | 项目薄适配：显式关节映射/单位/限幅、通信与功率许可分离、错误和超时锁存；仅接受精确 `FakeTransport` 类型 |
| `test_dm_offline.py` | 真正执行 29 项测试；另将上游 Python `send_mit` 等原始方法体以 AST 隔离，在假 ABI 上验证调用顺序和返回错误 |
| `DM_REFERENCE_CONFIG.json` | 7 个电机/反馈 ID 的公开参考配置；固件、实际关节限位和未核对型号保持 null，不能拿空值作为真实电机运行配置 |
| `../results/DM_OFFLINE_TEST_RESULTS.json` | 每项测试、执行实现身份、输入/代码 SHA256、物理 I/O 0 回执 |
| `../results/DM_INTEGRATION_CONTRACT.json` | 与既有 23 导体中 C01–C04 的精确绑定、源码映射、已完成项和剩余输入 |
| `../results/DM_SOURCE_MANIFEST.json` | 每件实际原文件 URL、提交、字节数与 SHA256；下载缺项及依赖声明 |

执行的是 **Python 编解码移植＋真实上游 Python 转发方法体的假 ABI 测试**。Rust 库、原生 FFI、串口后端没有执行；没有安装 Rust 或完整 MotorBridge 环境。后续原生 ABI 加载器、运行时部署器和示例下载遇到 TLS EOF，未获得的文件没有计入 18 件源包。当前可执行适配仅依赖 Python 标准库，缺少这些可选运行时不阻断本离线交付。

测试覆盖零值/端点金样、源型号参数一致性、反馈量化误差、分段接收、多帧/噪声、错误长度/标准 ID/RTR、缓冲上限、7 种故障和未知状态、通信缺失、功率许可缺失、超时后新帧禁止自动恢复、显式禁用复位、双 ID 匹配、限幅、单位变换、局部 API 重复序号、时间倒退与禁用命令。全部金样和反馈是**按协议构造的合成用例**，没有声称采集过电机数据。

上游型号表给出的 4310（12.5 rad、30 rad/s、10 N·m）与 4340P（12.5 rad、10 rad/s、28 N·m）用于协议缩放，不是机械关节允许范围、连续额定力矩或已校准工作限值。薄适配对项目限值先拒绝越界，再编码；关节变换为 `motor_q = r × joint_q + zero`，速度按 r 变换、力矩按 1/r、增益按 1/r²。r、零位、效率及真实机构限值仍需绑定。本包的小角度/低速测试值仅属于合成夹具。

通信反馈正常不会自动给出功率许可；超时或错误撤销模拟许可并锁存，后续正常帧不能自行恢复。显式复位要求新鲜 DISABLED 反馈，且复位后许可仍为 false。这是可审阅的软件行为，尚不证明 K1、失扭矩支撑、回生去路、实际停止时间或 USB/CAN 隔离。

**边界仍具体开放**：实机板卡/电机固件与 ID；J2–J7 型号分布、关节方向/零位/传动与机构限值；CAN 速率/端接、V4 插头针位与 USB 返回电路；合法实测帧和匹配原生 ABI；硬件停止及回生链。公开 BOM 的 3×4340P、4×4310 不能单凭数量分配到未核对的每个关节。

串口参考实现的 TX CRC 字段为 0，当前 RX 格式也不提供本包能验证的完整性码；DM 反馈没有本包可用的认证序号。因此不把格式检测宣称为任意位错误检测，也不把本地 API 序号校验宣称为总线防重放。实际功率与机构安全仍由独立硬件/工程验收负责。

离线复现命令（不访问设备）：

```powershell
& 'G:/Windows_program_file/Anaconda/python.exe' -X utf8 'F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/reuse_closure/software/test_dm_offline.py'
```
