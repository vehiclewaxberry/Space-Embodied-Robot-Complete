---
title: T_SB frame 闭合提案 V1（C-ISS-05 / V2-UNK-004）
generated_at: 2026-08-27
status: DESIGN_RESEARCH_CANDIDATE
source_basis:
  - "V2-UNK-004: design_inputs/v2_system_mechanical/06_unknown_register/V2_unknown_register.yaml (sha256 51df9c560787)"
  - "ODR-01 frame 权威: F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_OWNER_DECISION_REGISTER_V1.yaml (sha256 f5b1572c0cfc)"
  - "frame SSOT: config/geometry/frame_tree_v1.yaml (sha256 958bff23bf83)"
  - "R2 frame 块: MECHANICAL_ENGINEERING_RELEASE_R2/02_PRODUCT_STRUCTURE.yaml (sha256 0f9897ef4e41)"
  - "GAP-FR-01: 30_gap_registry/GAP_REGISTRY.csv (sha256 49d28658904e)"
---

# T_SB frame 闭合提案 V1（C-ISS-05）

## 1. 现状证据

- `V2-UNK-004 T_SB_free_flyer_base_transform`：值 null，状态 `UNKNOWN_BLOCKED`，阻塞项 `free_floating_dynamics / aggregate_reference`。自 2026-07-24 V2 PRE-CAD 线建立以来从未闭合。
- `V2_mechanical_ICD.md` §1 约定："`T_SB` 只表示服务星几何 frame `S` 到自由漂浮动力学基座 `B`，当前未知"。
- 已冻结的 frame 链（均不覆盖 T_SB）：
  - ODR-01：`T_SM = [185.25, 0, 0] mm + R_y(+90°)`，且 **198.0 / 208.0 / 210.405 mm 几何特征栈不得成为第二动力学 frame**；
  - 臂基座 `T_S_B601_ARM_BASE` at x = 208.0 mm（frozen F3R2 mapping）；
  - `F_L/F_R` 帆板根 frame（frame_tree_v1.yaml）。
- 仿真侧事实：sim_05/sim_11/sim_12 自由漂浮动力学均以基体（S 系）为参考建模并通过对拍（动量守恒 7.3e-17 / 3.85e-16），但这些仿真从未把 `B` 作为一个独立命名 frame 登记——`B` 只是方程内部的参考，不是受控 frame。

## 2. 候选定义

| 候选 | 定义 | 优点 | 缺点 |
|---|---|---|---|
| CAND-1（推荐） | `T_SB = identity`：B ≡ S（原点=12U 几何中心，轴同 S）。动力学中关于系统质心的量按"在 S 系内计算平移"处理，不另立 frame | 零新变换；与 ODR-01 链零冲突；与既有全部仿真对拍语义一致；CG 随构型变化时 frame 不变（frame 是几何对象，CG 是质量对象，分离干净） | 动力学读者需习惯"质心参考在方程内、不在 frame 树内"的约定 |
| CAND-2 | B = 系统质心 frame（原点=C01 CG，轴平行 S） | 动力学教材式自然 | CG 随构型/推进剂消耗/臂位形变化 → frame 变成质量态函数，与冻结几何链耦合；每构型需一张 T_SB 表，治理成本高 |
| CAND-3（否决） | B 置于 M/臂基座站位（198/208/210.405 mm 之一） | — | **直接违反 ODR-01**（几何特征栈不得成为第二动力学 frame），否决 |

## 3. 对 ODR-01 链的一致性影响

- `T_SM`、`T_S_B601_ARM_BASE`、`F_L/F_R` 全部不变；CAND-1 不引入任何新数值，只给既有事实补一个名字（B ≡ S）。
- 与 340.5 vs 366.0 mm 外廓冲突（V2-UNK-001/GAP-IL-08）无耦合：T_SB=identity 不依赖舱长数值。
- 对下游消费者：URDF/仿真/论文中"free-flyer base frame"一律引用 S；关于质心的动力学量（H_C、I_C）按"S 系表达 + 平移到 CG"书写，与 sim_11 既有的 `|H_O|`（惯性原点）/`|L_C|`（系统质心）双登记实践一致。

## 4. 建议处置

1. **采纳 CAND-1 为 C 轨候选定义**：`T_SB = identity (B ≡ S)`，身份标注 `DESIGN_RESEARCH_CANDIDATE`，登记进 C1 布局基线。
2. **登记 HOLD 待 owner 签署**：V2-UNK-004 属 owner 裁决项（`agent_may_not_self_close_unknown` 规则），本提案不构成自闭合；建议以一条新 ODR（或 ODR-F4R1 增补）正式闭合，闭合后更新 V2_unknown_register 与 frame_tree 的下一代受控版本（C 轨不回写冻结文件）。
3. C2/C3 阶段所有动力学/布局文档引用 T_SB 时，一律附本提案编号与签署状态。

## 5. 未决

- owner 签署前，V2-UNK-004 状态保持 `UNKNOWN_BLOCKED`（本提案 = 闭合候选，非闭合事实）。
