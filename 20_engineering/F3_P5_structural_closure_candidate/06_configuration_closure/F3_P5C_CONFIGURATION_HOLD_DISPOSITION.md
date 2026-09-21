# F3-P5C 构型 HOLD 处置报告

**文档编号：** `F3-P5C-CONFIGURATION-HOLD-DISPOSITION-20260805`
**生成 UTC：** 2026-08-05
**状态：** `CONFIGURATION_CLOSED_MODE_B_SINGLE_ROUTE`
**前置：** F3-P5B 双 Gate（PAD/HDRM 竞赛侧闭合）
**HOLD 处置：** HOLD-01/02/03/05 → 全部闭合（详见下）

---

## 1. HOLD-02/03：T_SM 单路线裁决

### 1.1 依据链

- F3-P3 T_SM 双轨：动力学轨 185.25 mm（`coordinate_frame_definition_v0.md` §3.1）vs 显示轨 198 mm（V22_NATIVE01 报告 §4.3）。
- F3-P3 C5 处置 `CANDIDATE_C_MODE_B_ONLY`：翼根机构下限宽 302.3 mm 是不可消解物理事实 → **Mode A（标准 12U 部署器，包络宽 226.3 mm）NON_COMPLIANT**；Mode B（外部服务模块，包络 340.5×226.3×226.3）ACCEPTABLE。
- 项目冻结显示 profile 已是 `340.5 × 226.3 × 226.3 mm`（NON_FLIGHT_DISPLAY_ONLY）。

### 1.2 单路线裁决

```text
T_SM_SINGLE_ROUTE = MODE_B_DYNAMICS_TRACK
T_SM = 185.25 mm（动力学轨，保持动力学一致性）
```

- **唯一运行路线：Mode B**（外部服务模块），T_SM = 185.25 mm。
- **Mode A 排除：** `NON_COMPLIANT_EXCLUDED`（C5 超宽 12 mm 不可消解；仅当未来获得部署器 ICD 或翼板机构重新设计后才可回访）。
- 所有后续构型裁决（STOW 处置、包络、状态机）只基于 Mode B。

## 2. HOLD-03：Mode B STOW_Z 处置

| 项 | Mode B 值 | 处置 |
|---|---|---|
| STOW_Z 包络 | 226.3 mm（Mode B 高度限制） | — |
| 实际 STOW 高度 | 359.02 mm（STOW 状态 Z 尺寸，= Mode B 上限 −132.72 mm 超出量） | — |
| 裁决 | **STOW 状态排除于比赛运行基线** | `MODE_B_STOW_EXCLUDED_FROM_OPERATIONAL_BASELINE` |

**处置内容：**
1. 比赛运行基线只含 `DEPLOYED_NOMINAL`、`SERVICE_*`、`RETRIEVED_NOMINAL` 姿态。
2. STOW 状态仅作发射/存储/运输姿态（`NON_OPERATIONAL`），STOW 下的任务相关要求全部不适用。
3. 演示流程从展开姿态开始（`DEPLOYED_NOMINAL` 为演示初始状态）。
4. STOW 高度超限作为已记录负结果保留（`NEGATIVE_PRESERVED`），禁止隐藏或重定义包络制造假通过。

## 3. HOLD-05：相机遮挡时序闭合

### 3.1 各阶段相机可用性（Mode B 运行基线）

| 阶段 | 末端相机 | 腕部相机 | 基座相机 | 说明 |
|---|---|---|---|---|
| STOW（非运行） | 可用 | 部分遮挡（G07） | 部分遮挡（G07/G08） | 非运行阶段，不作监视要求 |
| 释放初段 | 可用（HDRM 释放可见） | 可用（G07 脱离可见） | 可用（整体释放） | 关键机构全部可见 |
| DEPLOYED_NOMINAL | 可用 | 可用 | 可用 | 全可见 |
| 捕获任务 | 可用（抓取中心无遮挡） | 夹爪闭合时部分遮挡手指 | 可用 | 末端相机承担捕获主感知 |
| 装配任务 | 可用 | 可用 | 可用 | 全可见 |

### 3.2 闭合理由

- 遮挡仅出现在**非运行 STOW 状态**与**夹爪闭合瞬间**（手指遮挡属于正常抓取构型，不影响目标中心观测）。
- 运行基线（释放→任务）所有关键机构全程可见。
- 若未来要求 STOW 状态监视，需增辅助相机（已记录，不阻塞）。

```text
CAMERA_OCCLUSION_CLOSED_PASS_WITH_ACCEPTED_TIMING
```

## 4. HOLD-01：GUI 见证闭合

- F3-P3 `GUI_WITNESS_PASS`：FreeCADCmd（与 GUI 同 OCCT 内核）对 10 个 HIFI 视觉包完成打开/遍历/属性/几何/冷重开五重验证（T005-C 10/10）。
- **闭合：** `CLOSED_WITH_CMDEQUIVALENT_WITNESS`。
- 人工 GUI 可视确认（截图/颜色/可见性）降级为提交前可选项，不阻塞。

## 5. HOLD-04/06（非 P5C 责任，状态确认）

| HOLD | 责任 | 状态 |
|---|---|---|
| HOLD-04 G8b robust clearance margins | F3-P5A | 保持 `TBD`（无 AL 源） |
| HOLD-06 Launch load spectrum | F3-P5A | 保持 `NOT_AUTHORIZED_NO_SOURCE` |
| HOLD-09 FEA execution | F3-P5A | **CLOSED**（P5A 已实际执行） |

## 6. 状态机冻结

23 状态收口为 Mode B 单路线运行状态机，输出：`07_configuration/F3_P5C_STATE_MACHINE_FROZEN.yaml`

## 7. 裁决

```text
F3_P5C_PARTIAL_PASS_CONFIGURATION_CLOSED_MODE_B_SINGLE_ROUTE
```

- T_SM = 185.25 mm 单路线（Mode B）
- Mode A / Mode B STOW 均排除于运行基线（负结果保留）
- 相机时序闭合、GUI 见证闭合
- 遗留：G8b/AL 裕度 TBD（外部依赖）、Mode A 回访条件（部署器 ICD）
