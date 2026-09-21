# COMP-PROT-03-A4-B1 CAD Acceptance Matrix

_Engineering Visual CAD 的入口、退出、视图与否决矩阵，2026-07-23_

---

> `STATUS: DESIGN_REVIEW_BASELINE`  
> `NEXT_GATE: COMP-PROT-03-A4-B1-ENGINEERING-VISUAL-CAD`  
> `CAD_AUTHORING_AUTHORIZED: false`  
> `MAXIMUM_EXIT: A4_ENGINEERING_VISUAL_COMPLETE_WITH_PHYSICAL_LIMITATIONS`

## 🚪 入口条件

只有下列条件全部满足，才能由人工批准 A4-B1：

| ID | 条件 | 当前状态 |
|---|---|---|
| A4-ENTRY-01 | A3 几何基线及其哈希记录可读取 | 满足 |
| A4-ENTRY-02 | 唯一 profile 为 `COMPETITION_DISPLAY_V0` | 满足 |
| A4-ENTRY-03 | 唯一构型为 `A_CENTERLINE_TASK_FACE_SINGLE_ARM` | 满足 |
| A4-ENTRY-04 | B601 来源限定为 accepted STL + URDF | 满足 |
| A4-ENTRY-05 | vendor STEP 明确排除 | 满足 |
| A4-ENTRY-06 | 传感器仅为 nonphysical reference | 满足 |
| A4-ENTRY-07 | target 不进入 active assembly | 满足 |
| A4-ENTRY-08 | 独立人工批准已记录 | **未满足** |

因此，本文件不自动授权 CAD 建模。

## ✅ 退出验收矩阵

| ID | 验收项 | 通过标准 | 失败条件 |
|---|---|---|---|
| A4-CAD-01 | 版本隔离 | 新建独立 V1.0 目录；A3 文件哈希不变 | 覆盖、重命名或修改 A3 |
| A4-CAD-02 | 来源与许可 | 输入清单含 A3、SSOT、URDF/STL 哈希；`vendor_STEP_used=false` | 未登记来源或使用 vendor STEP |
| A4-CAD-03 | 组件身份 | 每个组件有唯一 ID、父级、状态和 representation layer | 仅依赖 SolidWorks 自动名称 |
| A4-CAD-04 | 主骨架 | `S/M/A0/G/E_virtual` 可见；未知帧仍为空且禁用 | 默认生成 `T_SB`、`TCP_contact` 等 |
| A4-CAD-05 | 12U 层级 | 外框、纵向构件、三舱 datum、设备板与可拆外板为独立组件 | 仍是单一包络块或无舱段语义 |
| A4-CAD-06 | Adapter | 160 mm plate/boss 保持证据几何；视觉特征标为提案；质量不重复 | 提案特征被标为制造真值或产生重复质量 |
| A4-CAD-07 | B601 拓扑 | 10 link / 9 joint、link ID 与父子关系匹配 accepted URDF | link 合并、关节重排或拓扑漂移 |
| A4-CAD-08 | B601 三层 | 每 link 有 source reference、visual shell、physical reserved 状态 | 视觉壳冒充 vendor exact 或物理内核 |
| A4-CAD-09 | 末端边界 | existing gripper 和 `E_virtual` 可见；physical TCP/contact disabled | 生成默认接触点或抓取几何 |
| A4-CAD-10 | 柔性附件 | 展开参考与收拢/安全显示构型分离，状态清楚 | 把显示构型写成部署真值 |
| A4-CAD-11 | 传感器边界 | 只有 datum、CS、预留草图和无数值标签；七项禁用属性齐全 | 出现实相机实体、选型、FOV 数值、BOM 或质量 |
| A4-CAD-12 | 目标隔离 | active assembly 中无 target；独立场景无 fixed/contact/rigid-lock mate | 目标并入主总装或激活接触 |
| A4-CAD-13 | 干涉范围 | 只报告具名构型与具名 q=0 pose；结论包含 scope | 推广为全工作空间或运动安全 |
| A4-CAD-14 | 质量零污染 | proposal/reference/placeholder 不写入已冻结聚合质量与惯量 | SolidWorks 默认材料或计算覆盖 SSOT |
| A4-CAD-15 | 评审视图 | 规定的 10 类视图完整、标题与水印清楚 | 只交一张等轴测截图 |
| A4-CAD-16 | 防误导属性 | 所有视觉提案含 `DESIGN_PROPOSAL`、`NO_DYNAMICS_USE` 等属性 | 缺少来源/状态/禁止消费者 |
| A4-CAD-17 | 原生可重开 | 零缺件重开、重建通过、组件/尺寸/属性清单可导出并哈希 | 仅有截图、STEP/STL 或断链装配 |
| A4-CAD-18 | 禁区证明 | Gate JSON、仿真结果、冻结配置、URDF、控制代码均无变更 | 任一禁区发生写入 |

## 🖼️ 必需评审视图

下一版不得只用一张“看起来更真实”的截图验收，必须提供：

1. 整机等轴测视图。
2. 前、顶、侧三个正投影视图。
3. 装配层级爆炸视图。
4. 前舱/中舱/后舱剖切视图。
5. 机械臂安装适配器局部视图。
6. B601 link ID、joint axis 与 frame overlay 视图。
7. 柔性附件展开参考视图。
8. 柔性附件收拢/安全显示提案视图。
9. `EVIDENCE_BOUND / DESIGN_PROPOSAL / UNKNOWN_BLOCKED / EXCLUDED` 状态着色视图。
10. 独立 target scene 参考图，并明确水印 `NO_CONTACT / NO_AUTONOMOUS_CAPTURE CLAIM`。

## 🎨 视觉与属性规则

| 状态 | 建议视觉编码 | 允许用途 |
|---|---|---|
| `EVIDENCE_BOUND` | 深蓝/实线 | 表示已钉住的几何身份或参数 |
| `DESIGN_PROPOSAL` | 浅蓝/青色 | 比赛与论文的工程视觉提案 |
| `UNKNOWN_BLOCKED` | 橙色/虚线/透明 | 显示仍需证据或资格审查的接口 |
| `EXCLUDED` | 灰色/单独场景 | 显示不属于当前主总装的对象 |

视觉编码不能替代自定义属性。每个非证据实体至少需要：

```text
EVIDENCE_STATE
REPRESENTATION_LAYER
SOURCE_REFERENCE
MASS_CONTRIBUTION
NO_DYNAMICS_USE
MANUFACTURING_AUTHORITY
EXECUTION_AUTHORITY
```

## 🧪 核验顺序

1. 冻结 A3 文件清单和哈希。
2. 建立 A4 独立源目录和输入 manifest。
3. 先建 master skeleton、组件 ID 与 evidence-state 属性。
4. 再建 12U、adapter、B601 和附件视觉几何。
5. 导出装配树、命名尺寸、属性、配合和来源清单。
6. 重开、重建并检查缺件。
7. 在唯一具名构型和 q=0 pose 下执行静态干涉检查。
8. 生成 10 类评审视图。
9. 核验零质量污染、零禁区变更和 A3 哈希一致。
10. 人工复核后才能给出退出裁决。

## ⛔ 立即否决

以下任一情况不允许使用 `COMPLETE`：

- A3 被改写，或新模型无法追溯到 A3/SSOT/URDF/STL。
- 导入未批准的 vendor STEP。
- 传感器、FOV、physical TCP、接触面或材料参数由 Agent 猜测。
- target 进入 active assembly 或与 gripper 建立接触/固定关系。
- 视觉壳被写入动力学、制造、强度或飞行证据链。
- 静态 q=0 检查被表述为抓取、全空间碰撞或自治能力验证。
- Gate JSON、科学结果、冻结配置或现有 URDF 被修改。

## 🏁 允许的退出裁决

| 裁决 | 条件 |
|---|---|
| `A4_ENGINEERING_VISUAL_COMPLETE_WITH_PHYSICAL_LIMITATIONS` | A4-CAD-01 至 18 全部通过 |
| `A4_ENGINEERING_VISUAL_PARTIAL` | 可重开且证据链完整，但一项或多项非安全展示要求未闭合 |
| `A4_BLOCKED_BY_SOURCE_OR_INTERFACE` | 来源、许可、frame、target 或未知接口越界 |
| `A4_REJECTED_BY_EVIDENCE_POLLUTION` | A3、质量、Gate、仿真或冻结证据发生污染 |

无论何种退出裁决，都不能自动授权 URDF、Isaac、动力学、控制、SAFE、RL、VLA 或物理制造阶段。
