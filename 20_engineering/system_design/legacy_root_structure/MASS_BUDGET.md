# 12U 质量预算裁定

状态：`UNSOURCED_BLOCKED`  
构型裁定：`STRUCTURE_CONFIG_ISSUE_B601_STOW_Z_AND_SOLAR_PACKAGE_WIDTH`

## 结论先行

- 当前版本的 12U 质量上限：`PLACEHOLDER`。Cal Poly CDS 当前修订版和所选部署器/发射任务 ICD 尚未按本轨道准入，不能写入数值。
- 可相加的完整平台 BOM：尚不存在。结构、EPS、电池、OBC、ADCS、通信、线缆、紧固件和 HDRM 均缺选型或测量。
- 当前臂+平台总质量是否超限：`UNSOURCED_BLOCKED`，不能判定“超”或“不超”。
- 余量质量和余量百分比：`PLACEHOLDER`。

因此，任何沿用“12U 上限等于历史值”并据此计算余量的结论都被撤销。该撤销不会把缺失值置零，也不会把旧仿真参数改写为硬件事实。

## 分系统分配

| 分系统 | 分配质量 | 合格上限 | 当前状态 |
|---|---:|---:|---|
| 主结构（框架、板、部署器接口） | `PLACEHOLDER` | `PLACEHOLDER` | `UNSOURCED_BLOCKED` |
| EPS、太阳翼与电池 | `PLACEHOLDER` | `PLACEHOLDER` | `UNSOURCED_BLOCKED` |
| OBC | `PLACEHOLDER` | `PLACEHOLDER` | `UNSOURCED_BLOCKED` |
| ADCS | `PLACEHOLDER` | `PLACEHOLDER` | `UNSOURCED_BLOCKED` |
| 通信 | `PLACEHOLDER` | `PLACEHOLDER` | `UNSOURCED_BLOCKED` |
| B601 与安装座/HDRM | `PLACEHOLDER` | `PLACEHOLDER` | 数字臂质量存在，但实物称重、安装座和 HDRM 缺失 |
| 线缆 | `PLACEHOLDER` | `PLACEHOLDER` | `UNSOURCED_BLOCKED` |
| 紧固件 | `PLACEHOLDER` | `PLACEHOLDER` | `UNSOURCED_BLOCKED` |
| 系统余量 | `PLACEHOLDER` | `PLACEHOLDER` | `UNSOURCED_BLOCKED` |

余量公式仅保留接口，不代入虚构数字：

```text
margin_kg = qualified_limit_kg - qualified_launch_mass_kg
margin_percent = margin_kg / qualified_limit_kg × 100%
```

## 旧质量链审计

旧链只能用于解释错误来源，不得成为新 BOM：

| 旧值/关系 | 原始角色 | 本轮裁定 |
|---|---|---|
| `servicer_12U_v0 = 24.0 kg` | 用有效密度把九个简单几何体强制配平到旧 CDS 目标，并把若干内部子系统整体 lump 到本体 | `CORRECTED`：排除出逐项 BOM 和现行上限 |
| `servicer_12U_bus_v1 = 23.3032134 kg` | 从上述 24 kg 几何体中仅扣除两块旧太阳板占位 | `CORRECTED`：不是主结构实物质量，也不能再与独立 EPS/OBC/ADCS 行相加 |
| `robot_mount_adapter_v0 = 1.2 kg` | 板+凸台几何体有效密度估算 | `CORRECTED`：当前原生件只有参考包络，材料、孔、筋和紧固件未定义；新 BOM 写 `PLACEHOLDER` |
| `B601 = 4.6955559493429862 kg` | accepted URDF 每连杆数字质量求和 | `CORRECTED`：仅保留在 BOM 的 `model_only_reference`，物理 `mass_kg` 为 `PLACEHOLDER`，不可参与加总 |
| PDR provisional ledger `29.8955559493429862 kg` | 旧 bus/panel/adapter/arm 行的算术和 | `CORRECTED`：仅作审计快照；大部分真实硬件缺失，不能称整星质量 |

旧链的核心问题不是算术错误，而是“总量占位”和“分系统实物 BOM”混用了同一质量所有权。新 BOM 已把它们分开并禁止双计。

## 臂+平台超限问题的明确回答

```text
qualified_limit_kg = PLACEHOLDER
qualified_platform_mass_kg = PLACEHOLDER
qualified_B601_plus_mount_mass_kg = PLACEHOLDER
over_limit = UNSOURCED_BLOCKED
```

当前只能确认：accepted URDF 给出了一个审计用数字模型臂质量；该值已从可加总 `mass_kg` 字段移出。不能确认完整平台质量，也不能确认适用的 12U/CSD/任务质量上限，因此本轮不得写“已经超限”或“仍有余量”。

## 对下游的约束

- 角动量预算：反作用轮 `momentum_capacity_Nms` 与 `max_torque_Nm` 均为 `PLACEHOLDER`；旧扫描档位不是产品数据。
- GJM：不得用旧 24 kg lumped bus 与新增分系统再次相加；整星 CoM/惯量仍不可用。
- 结构/模态：质量分布、HDRM 和部署器边界未定，不能建立可信一阶模态模型。
- 仿真：历史冻结仿真可保留其原始占位口径，但不得声称已被本 BOM 转正。

## 解除阻塞所需证据

1. 准入当前 CDS、所选 12U 部署器/适配器和任务级质量/质心约束。
2. 冻结逐项硬件选型及 datasheet，特别是反作用轮、EPS、电池、OBC、星敏、通信和 HDRM。
3. 对 B601、安装座、线缆和最终收拢整星分级称重。
4. 以同一 `S` 坐标系做最终收拢构型的质量、CoM、惯量重组。
5. 再计算余量，并由独立质量审查签署。
