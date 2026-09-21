# F3-P5 Truth Hierarchy

**文档编号：** `F3-P5-TRUTH-HIERARCHY-20260805`
**生成 UTC：** 2026-08-05
**状态：** `FROZEN`

---

## 真值层级（从高到低）

| 层级 | 对象 | 角色 | 可修改性 |
|---|---|---|---|
| **L0** | accepted B601 URDF | 运动学/质量/惯量真值 | **只读冻结** |
| **L0** | mass_inertia_budget_v1.csv | 质量账本真值 | **只读冻结** |
| **L0** | coordinate_frame_definition_v0.md | 坐标系 SSOT | **只读冻结** |
| **L1** | V2_3 baseline_freeze_manifest.yaml | CAD 基线 | **只读冻结** |
| **L1** | F3-P4 GATE_STATUS.json | F3-P4 裁决 | **只读参考** |
| **L2** | F3-P4 8 个交付文件 | 工程定义 | **只读参考** |
| **L3** | F3-P5 新生成文件 | 候选/待批准 | **可修改** |

---

## 关键规则

1. **L0 不可覆盖** — accepted B601 URDF、mass_inertia_budget、coordinate_frame_definition 是最高真值，任何后续文件不得覆盖
2. **L1 只读** — V2_3 CAD 基线和 F3-P4 裁决只读，不得修改
3. **L2 参考** — F3-P4 8 个交付文件是工程定义，不是工程真值，不得作为通过证据
4. **L3 候选** — F3-P5 新生成文件是候选，需人工批准后才能升级为 L2 或 L1

---

## HIFI CAD 边界

| 允许 | 禁止 |
|---|---|
| 工程视觉表达 | 覆盖 accepted URDF 质量/惯量 |
| 外部包络 | 修改 B601 内部关节结构 |
| 安装接口 | 修改 joint 数量/顺序/轴向/零位 |
| 干涉检查 | 用 HIFI 质量覆盖动力学真值 |
| 外部载荷传递 | 重画 B601 内部传动系统 |
| 仿真 visual/collision mesh 来源 | 将 HIFI 作为动力学真值 |

---

## 质量账本边界

| 允许 | 禁止 |
|---|---|
| 新增外部结构质量单独入账 | 混入 accepted B601 内部质量 |
| CAD 质量与 URDF 质量双轨记录 | 自动覆盖 URDF 质量 |
|  provisional 质量标记 | 将 provisional 作为真值 |

---

## 载荷分类边界

| 类别 | 标识 | 可执行性 | 输出限制 |
|---|---|---|---|
| **UL** | UNIT_LOAD_CHARACTERIZATION | **立即可执行** | 不得声称发射验证 |
| **PL** | PROVISIONAL_COMPETITION_DESIGN_LOAD | **需项目负责人批准** | 仅用于相对比较/样机风险控制/控制初步参数 |
| **AL** | AUTHORIZED_LAUNCH_LOAD_CASE | **未授权** | 无正式输出 |

**当前状态：** 无 AL 源，LAUNCH_STRENGTH_MARGIN = TBD，LAUNCH_BUCKLING_MARGIN = TBD，G8B_MARGIN = TBD。
