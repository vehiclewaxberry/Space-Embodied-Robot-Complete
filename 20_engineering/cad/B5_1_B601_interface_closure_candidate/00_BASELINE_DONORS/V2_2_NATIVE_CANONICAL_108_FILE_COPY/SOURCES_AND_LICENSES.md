# NATIVE-01 来源与许可清单

## 本轮原生几何的来源性质

**本目录下全部 .SLDPRT / .SLDASM 均为本项目原创参数化建模**，不含任何第三方
几何拷贝、不含厂商 STEP 导入实体。每个零件的 `GEOMETRY_AUTHORITY` 自定义属性
均为 `NATIVE_SW_THIS_FILE`。

## 输入依赖（只读引用，未复制几何）

| 输入 | 用途 | 权威性 | 许可 |
|---|---|---|---|
| `20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf` | 运动学/质量权威（未修改；本阶段未装入 B601） | KINEMATIC + MASS | 溯源=reBotArmController_ROS2@319100d3，**无 LICENSE 文件 → E3_INTERNAL_RESEARCH_ONLY** |
| V2.2 冻结尺寸（±183 / ±113.15 / ±105.65→本轮改 ±101.65 / MID ±61 / 翼根 Y=±110, Z=-105.65） | 骨架参数 | 显示轨 SSOT | 项目内部 |
| `130_.../design/saddle_windows_for_native.json` | 三处鞍座接触高度（234.77 / 248.49 / 253.80） | 由厂商网格顶点实测导出的**数值**，非几何 | 数值派生，不含厂商几何 |
| reBot-DevArm 厂商 STEP | **本阶段未使用**（仅 VENDOR-CAD-03 使用） | — | CERN-OHL-W-2.0（正文本地核验） |

## 许可结论

- 本阶段原生模型**不含受限第三方几何**，可自由用于本项目交付与展示。
- 鞍座接触高度是从 E3 类几何**测得的数值参数**（三个 Z 值），不构成几何再分发。
- 若后续按任务书第 9 项装入 `B601_STOWED_HIFI.SLDPRT`（厂商 STEP 派生），
  该零件将带 `LICENSE_CLASS=E3_INTERNAL_RESEARCH_ONLY` 与 `DO_NOT_REDISTRIBUTE=TRUE`，
  并且**不得随交付包对外分发**。

## 未改动声明

- accepted URDF：字节未改（`arm_b601_v1.urdf`，sha256 1bc2b748…）
- V2.0 / V2.1 / V2.2 既有树：本轮零写入（唯一写区 = `Space_Embodied_Robot_CAD_V2_2_NATIVE/`）
- 120 / 130 目录：只读引用，未覆盖
