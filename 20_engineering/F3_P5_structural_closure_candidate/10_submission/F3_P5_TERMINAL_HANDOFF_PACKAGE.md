# F3 机械架构终止交接包

**文档编号：** `F3-P5-TERMINAL-HANDOFF-20260805`
**生成 UTC：** 2026-08-05
**状态：** `CLOSED_CONTROL_AND_EMBODIED_HANDOFF_READY_AL_HOLD`

---

## 1. 执行摘要

F3 机械架构工作全部闭环：
- UL 验证（F3-P5A）
- 竞赛级架构确定（PAD G07/G08，HDRM 演示件）（F3-P5B）
- 构型冻结（Mode B 单轨、状态机 FROZEN）（F3-P5C）
- 比赛样机制造发布（8 件 + BOM + MPI）（F3-P5D）
- 控制交接（6×6 + ROM + 接触 + 状态机）（F3-P5E）
- 具身交接（mesh/帧/观测/动作/负案例/smoke test）（F3-P5E）
- 变更控制 + HOLD 处置（HOLD-01/02/03/05/07/08/09/10 关闭；04/06 保持 TBD）

## 2. 交付物清单

| 类别 | 交付物 | 位置 |
|---|---|---|
| FEA 证据 | `F3_P5A_GATE_STATUS.json`、`F3_P5A_MODAL_REPORT.md`、6×6 矩阵 | `04_fea/01_geometry/`…`16_gate/`、`08_matrices/`、`09_modal/` |
| 构型 | `F3_P5C_CONFIGURATION_HOLD_DISPOSITION.md` | `06_configuration_closure/` |
| 状态机 | `F3_P5C_STATE_MACHINE_FROZEN.yaml` | `07_configuration/` |
| 制造 | `F3_P5D_MANUFACTURING_RELEASE.md` + MPI + BOM | `07_manufacturing_release/`、`11_bom/` |
| 控制交接 | `F3_P5E_CONTROL_HANDOFF_PACKAGE.md` + Schema | `08_control_handoff/` |
| 具身交接 | `F3_P5E_EMBODIED_HANDOFF_PACKAGE.md` + Schema + smoke test | `09_embodied_handoff/` |
| 变更控制 | `F3_P5_CHANGE_CONTROL.md` | `11_change_control/` |
| 审计 | 坐标帧寄存器、HOLD 寄存器 | `00_audit/` |

## 3. 交接证明（证据链）

- **制造发布**：F3-P4E 8 件制造深化（材料/基准/GD&T + TechDraw 出图给制造商）
- **控制交接**：6×6 + 接触 + 状态机 + ROM 模态（61.13/200.90/429.00 Hz）
- **具身交接**：mesh/帧/观测/动作/屏蔽/负案例/静态 smoke test 8/8 PASS
- **构型**：应力时序相机遮挡 + GUI 见证 CMD 等效（OCCT 同内核，T005-C 10/10）
- **装配**：139 matched / 0 unassigned（HAG-A）
- **认证族**：基线 SHA `408147DD...`；哈希链 + IBR（collision summary）

## 4. HOLD 状态（终态）

| HOLD | 状态 | 备注 |
|---|---|---|
| HOLD-01 | CLOSED | GUI 见证交由 CMD 等效 |
| HOLD-02 | CLOSED | T_SM 单路线 Mode B |
| HOLD-03 | CLOSED | Mode B STOW 排除（非运行） |
| HOLD-04 | OPEN（TBD） | G8B 二裕度无 AL 源 |
| HOLD-05 | CLOSED | 相机遮挡时序闭合 |
| HOLD-06 | OPEN（TBD） | AL 载荷谱不存在 |
| HOLD-07 | CLOSED（竞赛级） | G07/G08 竞赛完成；飞行侧 PROCUREMENT_TBD |
| HOLD-08 | CLOSED（竞赛级） | HDRM 演示件选型；飞行侧 PROCUREMENT_TBD |
| HOLD-09 | CLOSED | 实际 FEA 已执行 |
| HOLD-10 | CLOSED | 制造发布（比赛样机） |

## 4. 遗留开口（明确声明）

- 飞行侧材料/验收：AL 缺失 → 强度/屈曲/G8B 二裕度保持 **`OPEN_TBD`**
- 6×6 矩阵为解析、自由模态为裸结构（B601 惯性未合）→ 控制用预留
- G07/G08 标定结果 >20% → 需重跑 UL（并升级交接包）
- SL/实体 STL/GLB 导出、相机标定参数：仿真/视觉组提供

## 5. 终局裁决（目标）

```text
F3_MECHANICAL_ARCHITECTURE_AND_COMPETITION_PROTOTYPE_CLOSED
CONTROL_AND_EMBODIED_HANDOFF_READY_AL_HOLD
```

机械架构、比赛样机架构、控制交接、具身交接全部 `CLOSED_READY`；
发射合格与 AL 裕度一律保持 `AL_HOLD`（无 AL 源，不降级为通过）。

**明确不声明：** FLIGHT_RELEASED / QUALIFIED / DEMO_ALLOWED_TO_FLIGHT。