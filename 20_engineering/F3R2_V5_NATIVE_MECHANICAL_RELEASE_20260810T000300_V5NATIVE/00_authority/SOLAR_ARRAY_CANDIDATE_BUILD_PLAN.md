# SOLAR_ARRAY_CANDIDATE_BUILD_PLAN — V5 左右对称三板太阳翼原生化计划

状态：`RELEASED_FOR_V5_NATIVE_FINALIZATION_R2`

权威输入：`SOLAR_ARRAY_INTERFACE_REQUIREMENTS.md`（状态 `V5_NATIVE_FINALIZATION_INTERFACE_FROZEN_R2`）  
适用范围：`MULTI_PANEL_SOLAR_ARRAY_CANDIDATE`，每侧 `ROOT_HINGE → P1 → P2 → P3`  
允许最终称谓：`COMPETITION_PROTOTYPE_BASELINE`  
禁止称谓：`FLIGHT_READY`、`LAUNCH_QUALIFIED`

## 1. 不可变边界

- accepted B601 URDF、joint topology、link length、inertial truth 和 V2.2 frozen baseline 均为只读；
- 不移动机械臂来规避太阳翼干涉；
- 不创建太阳电池片细节，不把太阳翼候选质量写回 L0 质量真值；
- 所有新件只写入 `V5_NATIVE_FINALIZATION`；后续机械变更进入 ECR。

## 2. 已知不合格候选的处理

现有 `SOLAR_PANEL_L1..R3`、`L/R_SOLAR_ARRAY.SLDASM` 与旧状态寄存器必须先做 SHA-256 留证并可恢复隔离，禁止原位覆盖。原因：

1. 右侧 `panel_pose()` 对已带符号的 Y 坐标再次乘以 `sign=-1`，实际几何不满足 XZ 镜像；
2. `config_pose_map(side)` 忽略 side，左右单侧失效语义错误；
3. 旧装配没有真实铰链 mate，也没有三板整机 clearance 证据。

历史 completion receipt 保留原位并标注为 `INVALIDATED_DIAGNOSTIC_DONOR_ONLY`。

## 3. Loop 1 — Geometry / native part creation

每侧建立三个简化原生 panel：

- `SOLAR_PANEL_L1/L2/L3.SLDPRT`
- `SOLAR_PANEL_R1/R2/R3.SLDPRT`

每块 panel 必须携带可读机械语义：简化结构、入/出铰链轴、收拢接口、展开止挡、折叠父子关系、线束出口与 `EXTERNAL_MECHANICAL_MASS_ONLY` 质量占位。太阳电池片细节保持 `PROHIBITED`。

根铰链仅继承实测接口：X 轴，`y=±143.15 mm`，`z=0`，pin `Ø8.0 mm`，ear bore `Ø8.4 mm`。L1–L2 和 L2–L3 的 pin/bearing/fastener/寿命均保持候选或 HOLD。

静态几何验收：

- 左/右六块 panel 一一镜像；
- deployed panel 质心目标为左侧 `+171.4833/+228.1500/+284.8167 mm`、右侧相反数；
- X 包络 `[-174.5,+52.5] mm`，每块 panel 厚度 `6 mm`；
- 所有原生件冷重开、单一实体/预期实体数、无 3D Interconnect、无 V5 树外引用。

## 4. Loop 2 — Assembly / mate / states

建立：

- `L_SOLAR_ARRAY.SLDASM`
- `R_SOLAR_ARRAY.SLDASM`

每侧必须有三条真实 X 轴转动链：ROOT、P1–P2、P2–P3。配置可以由确定性驱动器写入，但每条铰链都必须留下健康的原生 mate、轴读回和 1R 证据；不能仅靠自由组件 transform 冒充铰链。

七态唯一映射：

| 配置 | LEFT `[root,h12,h23]` | RIGHT `[root,h12,h23]` |
|---|---:|---:|
| `SOLAR_STOWED` | `0/0/0` | `0/0/0` |
| `SOLAR_DEPLOY_STAGE1` | `90/0/0` | `90/0/0` |
| `SOLAR_DEPLOY_STAGE2` | `90/90/0` | `90/90/0` |
| `SOLAR_DEPLOYED_NOMINAL` | `90/90/90` | `90/90/90` |
| `SOLAR_LEFT_FAIL` | `0/0/0` | `90/90/90` |
| `SOLAR_RIGHT_FAIL` | `90/90/90` | `0/0/0` |
| `SOLAR_BOTH_FAIL` | `0/0/0` | `0/0/0` |

阶段态是离散验证姿态，不授权部署时间、速度、动力、扭矩或可靠性结论。

## 5. Loop 3 — Top integration / motion / clearance

在新的 V5 top assembly 中以三板子装配替换旧 single-panel occurrence，禁止同时保留收拢与展开两套实体。对每个太阳翼状态和下列机械臂权威姿态运行原生 B-rep 检查：

- `Q_DEPLOYED_HOME`
- `Q_RELEASE_CLEAR`
- `Q_SERVICE_READY`

`SERVICE_GRASP` 无权威 q，只检查未来包络保留，不声称姿态已验证。

必查：`arm↔solar`、`arm↔bus`、`camera↔solar`、`harness↔solar`、`solar↔bus/wing-root/support/HDRM/gripper`。非白名单实体对最小净空必须 `≥5.0 mm`。优先通过太阳翼铰链角、折叠几何与部署顺序修正干涉。

## 6. Loop 4 — Release evidence

交付至少包括：

- 原生 `SLDPRT`、`SLDASM`、`SLDDRW`；
- 七态状态寄存器与逐板 angle/hinge/collision/camera/arm-clearance 记录；
- BOM、数字线程、质量占位账本；
- Pack-and-Go、独立会话 cold reopen、引用闭合和最终 SHA-256 manifest；
- SolidWorks 人工视觉复核记录。

最终 Gate 只有在所有强制证据通过后才允许：

`F3R2_V5_NATIVE_MECHANICAL_BASELINE_CLOSED`

持续 HOLD：launch load、thermal vacuum、random vibration、formal fastener MOS、部署动力学/寿命/可靠性和任何飞行资格。
