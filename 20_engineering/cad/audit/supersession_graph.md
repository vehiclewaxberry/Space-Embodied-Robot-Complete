# 取代关系图（MECH-INVENTORY-AUDIT-01）

```
V0_1 (15 原生, 早期未核验)
  └─▶ V1_0 (32 原生, 早期未核验)
        └─▶ V2_0 (57 原生, B3, COMPLETE_WITH_PHYSICAL_LIMITATIONS)
              ├─▶ V2_1 (60 原生, B4-1, NATIVE_REFERENCE_CAD_ACCEPTANCE_HOLD)
              │     └─▶ V2_2 (102 原生, B5/L1, 双轨 366 显示轨)
              │           ├─▶ 100_Mechanical_Continuation  [CODEX, STEP-only]
              │           ├─▶ 110_Layout_and_Deployment_01 [STEP-only]
              │           ├─▶ 120_PoseMap_02               [Claude, STEP/分析]
              │           ├─▶ 130_VendorCAD_03             [Claude, STEP/分析, 已封存]
              │           └─▶ V2_2_NATIVE (63 原生+2 图纸, NATIVE-01 Phase1)
              └─(B601 视觉臂 10 件 q0 bbox 原生件被 V2_2 继承)
```

## 取代裁定

| 资产 | 被取代者 | 取代者 | 依据 |
|---|---|---|---|
| 整星原生顶装 | V2_0 / V2_1 | **V2_2 或 V2_2_NATIVE（待人工选）** | 见 current_top_assembly_comparison.md |
| 翼根站位 | V2_2_NATIVE 初版 X[126,174] 内置 | Codex SOLAR-ROOT-01 外挂式 | O9 已返工 |
| ARM-STOW 站位 | Codex 占位包络 Z 88..110.15 | v3 向量实测站位 | 真实几何取代占位 |
| 收拢向量 | v1(120) → v2(130) | **v3(NATIVE, CANDIDATE_HOLD)** | O13 顶点级约束 |
| 时钟角论证 | "宽度必要性" | "限位余量 c≥7.894°" | O11 证伪并改写 |
| 视觉评审图 | matplotlib 网格图 | **原生 .SLDDRW + A-A 真剖视** | N13 |

**封存（不再开发）**：V0_1、V1_0、130_VendorCAD_03（保留为几何来源与诊断证据）、
_failed_builds。
