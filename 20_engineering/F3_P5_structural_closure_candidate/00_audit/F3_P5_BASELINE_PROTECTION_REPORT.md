# F3-P5 Baseline Protection Report

**文档编号：** `F3-P5-BASELINE-PROTECTION-REPORT-20260805`
**生成 UTC：** 2026-08-05
**状态：** `PROTECTION_VERIFIED`

---

## 1. 冻结资产保护验证

| 资产 | 路径 | 哈希 | 状态 | 保护 |
|---|---|---|---|---|
| accepted B601 URDF | `20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf` | 408147DD... | FROZEN | 只读，F3-P5 不修改 |
| mass_inertia_budget | `20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/mass_inertia_budget_v1.csv` | 073C8025... | FROZEN | 只读，F3-P5 不修改 |
| coordinate_frame_definition | `20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/coordinate_frame_definition_v0.md` | — | FROZEN | 只读，F3-P5 不修改 |
| V2_3 baseline_freeze | `20_engineering/cad/Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION/baseline_freeze_manifest.yaml` | E27F44E5... | FROZEN | 只读，F3-P5 不修改 |
| F3-P4 GATE_STATUS | `F:/Space-Embodied-Robot-HAG_A_20260804/12_f3_p1_hifi_attachment/12_gate/F3_P4_GATE_STATUS.json` | 7CCA7DA6... | CURRENT | 只读，F3-P5 参考 |

---

## 2. 隔离工作目录保护

| 目录 | 路径 | 状态 |
|---|---|---|
| F3-P5 隔离工作目录 | `20_engineering/F3_P5_structural_closure_candidate/` | 新建，可写 |
| 源仓库 | `F:/China Graduate Future Flight Vehicle Innovation Competition` | 只读（除隔离目录） |

**规则：**
- F3-P5 所有新文件只写入 `20_engineering/F3_P5_structural_closure_candidate/`
- 不得修改源仓库中任何冻结资产
- 不得修改 `F:/Space-Embodied-Robot-HAG_A_20260804` 中任何 F3-P1~P4 资产

---

## 3. Donor 保护

| 资产 | 路径 | 哈希 | 状态 |
|---|---|---|---|
| Donor STEP | `F:/Space-Embodied-Robot-HAG_A_20260804/01_donor_intake/reBot_B601_DM_v1.1_20260425.step` | 87A0537D... | FROZEN |
| Donor FCStd | `F:/Space-Embodied-Robot-HAG_A_20260804/03_import_headless/B601_HIFI_HEADLESS_IMPORT.FCStd` | 09C24124... | FROZEN |

**规则：**
- Donor STEP 和 FCStd 只读
- F3-P5 不重新导入或修改 donor
- F3-P5 只使用 F3-P1 生成的 10 个视觉包作为 HIFI 几何来源

---

## 4. B601 真值边界保护

| 边界 | 规则 | 状态 |
|---|---|---|
| URDF 修改 | 禁止 | PROTECTED |
| Joint 结构修改 | 禁止 | PROTECTED |
| 质量覆盖 | 禁止 | PROTECTED |
| 惯量覆盖 | 禁止 | PROTECTED |
| HIFI 质量混入 B601 | 禁止 | PROTECTED |

---

## 5. 已知并行写入登记

| 项 | 值 |
|---|---|
| Git 状态数 | 284 |
| 性质 | KNOWN_PARALLEL_AGENT_WRITE |
| 处理 | 登记，不删除，不回滚 |
| 影响 | 不阻塞 F3-P5 隔离工作 |

---

## 6. 保护结论

```text
PROTECTION_VERIFIED
```

- 所有冻结资产哈希已记录并验证
- 隔离工作目录已建立
- Donor 保护已确认
- B601 真值边界已确认
- 已知并行写入已登记

**下一步：** 核实 S3 G07/G08/Mid 几何和 2mm 间隙。
