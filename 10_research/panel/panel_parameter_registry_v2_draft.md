# panel_parameter_registry_v2 候选草案（文献工作流 wf_08f5d04f, 2026-07-18）
# 状态：CANDIDATE_FOR_REVIEW——未经 Gate 重跑不得作为科学结论；正式替换以杨恒参数卡合并为准

以下为 panel_parameter_registry_v2 候选 YAML 草案与影响评估。

```yaml
# panel_parameter_registry_v2 — 候选草案（供 20_engineering/config/geometry/flexible_appendage_v1.yaml 升 v2 及
# 20_engineering/config/coupled_scene/coupled_model_v0.yaml 占位替换评审用；未经 Gate 重跑前不得作为科学结论引用）
# 口径约定：measured=实测 / datasheet_nominal=厂商标称 / derived=推算
version: v2_draft
status: CANDIDATE_FOR_REVIEW
date: 2026-07-18

per_side_wing_mass:                # 单侧翼系统质量（含铰链/HDRM/线缆，"翼系统"口径）
  value_kg: 0.65
  range_kg: [0.18, 1.07]           # COTS 6U/12U 翼全谱系：MMA HaWK 175 g/翼 → EnduroSat 双板翼 1065 g
  unit: kg
  sources:
    - {name: "Airbus Sparkwing datasheet 质量公式 3.8 kg/m² + 0.4 kg/panel 机构，按 6U 面翼估 ≈0.63 kg/侧",
       url: "https://satcatalog.s3.amazonaws.com/components/1209/SatCatalog_-_SparkWing_-_SmallSat_Solar_Array_-_Datasheet.pdf?lastmod=20210809221934",
       confidence: datasheet_nominal}
    - {name: "DHV 6U/12U 3板翼 <900 g", url: "https://dhvtechnology.com/wp-content/uploads/2017/07/Datasheet-6U-Julio-v1-front-back.pdf", confidence: datasheet_nominal}
    - {name: "EnduroSat 6U 单展开翼 655–770 g", url: "https://www.endurosat.com/products/6u-deployable-solar-array/", confidence: datasheet_nominal}
    - {name: "MMA HaWK 17AB36 175 g/翼（轻端，MarCO 飞行构型）", url: "https://mmadesignllc.com/wp-content/uploads/2018/09/MMA-HaWK-17AB36-spec-sheet-ICD.pdf", confidence: datasheet_nominal}
  confidence: datasheet_nominal
  note: >-
    现占位 0.348 kg/侧 = 24 kg 均匀密度分摊，非结构设计值。名义 0.65 kg 对应“12U 侧挂 6U 面级
    2–3 板翼 + 机构”。若维持冻结几何(0.200×0.227 m 单板小翼)，翼系统合理质量为 0.30–0.45 kg，
    与占位反而接近——质量偏差的主因是翼面积/板数假设，不是面密度假设。
    约束提醒：mass_split_check.py 强制 m_bus + 2*m_panel == 24.000 kg，改质量须同步改 bus 行并重跑闭合检查。

areal_density:                     # 展开阵面密度（panels+PVA，不含机构）
  value_kg_per_m2: 3.8
  range_kg_per_m2: [2.4, 10.8]     # 低端 MMA HaWK(推算2.4)；高端 EnduroSat 6U(推算9.2–10.8，含机构)
  unit: kg/m^2
  sources:
    - {name: "Sparkwing：CFRP 蜂窝 panels+PVA = 3.8 kg/m²（厂商公式）", confidence: datasheet_nominal}
    - {name: "DHV 单板推算 ≈4.6；ISISPACE 6U 推算 ≈3.6；STEP Cube Lab-II 裸板实测反推 ≈3.2", confidence: derived}
  confidence: datasheet_nominal
  note: >-
    现占位有效面密度 7.67 kg/m²（0.348/0.0454），落在 CubeSat PCB 翼 3.2–10.8 kg/m² 带内、
    高于大阵 2–5 kg/m² 经验带——占位并非“密度不真实”，而是“面积太小”。

first_mode_frequency:              # 展开悬臂一阶弯曲，翼系统口径（含根铰柔度）
  value_hz: 1.0                    # 名义保留，但依据从"任意指派"改为"2–3 板翼频带"
  envelope_hz: [0.6, 2.2]          # 建议由 0.7/1.3 扩为 Sparkwing 3板翼官方频带
  alternative_single_panel_hz: [5.0, 10.0]   # 若采纳冻结几何的单板短翼，一阶应上移至此档
  unit: Hz
  sources:
    - {name: "Sparkwing 展开频率带：1板 5.0–17.0 / 2板 1.5–5.0 / 3板 0.6–2.2 Hz", confidence: datasheet_nominal}
    - {name: "Zhao et al. 2021, DOI 10.1155/2021/7443312：两板阵 0.738/3.206/3.594 Hz，三板阵 0.956/2.697/5.575 Hz", confidence: derived}
    - {name: "HOKUSHIN-1 (arXiv:2601.12851)：单板展开铰支 FEA f1=6.11(FR4)/9.16(Al) Hz", confidence: derived}
  confidence: datasheet_nominal
  mode_spacing_note: >-
    现解析悬臂给 f2/f1=6.27、f3/f1=17.6；实测多板阵为 f2/f1≈2.8–4.3、f3/f1≈3.9–5.8（Zhao）。
    真实阵低阶模态更密集，FFR 截断 m=3 的能量收敛（G4）会更严苛而非更宽松。
  ei_note: >-
    频率由根铰/铰链链柔度主导：标定到 f1 的是“翼系统有效 EI”（量级 1e-2–1e2 N·m²），
    勿直接用板材级 D（高估 2–3 个数量级）。冻结几何+0.65 kg+1.0 Hz ⇒ 有效 EI ≈ 1.66e-2 N·m²
    （由 8.9042e-3 × 0.65/0.348 缩放，derived）。registry 建议同时存 (ρA, 有效EI, L) 三元组。

modal_damping_ratio:
  value: 0.005
  range: [0.003, 0.02]             # 最不利（振铃最长）取 0.003
  unit: dimensionless
  sources:
    - {name: "MOS-1 刚性板阵在轨外推：1阶1.1%/2阶0.4%/3阶0.45%，DOI 10.1016/S1474-6670(17)60880-2", confidence: derived}
    - {name: "HST SA-3 地面实测基线 0.5%（控制稳定需求 ≥1.5%），DOI 10.1109/AERO.2000.878438", confidence: measured}
    - {name: "SDO 飞行幅值外推下包络 0.3%（NTRS 20080012648）", confidence: derived}
    - {name: "裸 CFRP/PCB 结构实测 0.2–0.3%：Kong&Huang DOI 10.1177/1687814016687965；Bhattarai DOI 10.1155/2020/8820619", confidence: measured}
  confidence: measured_cluster_supported
  note: >-
    占位 0.005 恰在刚性板实测簇(0.3–1.1%)中心，名义值无需改动；>2% 仅见于柔性毯翼（ISS 2A/ROSA/SAFE），
    刚性板构型不应采用。flexible_appendage_v1.yaml 中 zeta:0.01 与 coupled_model_v0.yaml 中 0.005
    现不一致，v2 应统一为 0.005 并关闭 TBD_cite_literature。
```

## 影响评估（中文）

**质量放大倍数**：现占位 0.348 kg/侧 → 推荐名义 0.65 kg/侧，即 **约 1.9 倍**（COTS 全谱 0.18–1.07 kg 对应 0.5–3.1 倍）；帆板占整星质量比从 2.9% 升至 5.4%。注意两点：(1) 由于 `mass_split_check.py` 强制 m_bus+2·m_panel=24.000 kg 闭合，bus 行须同步降为 22.70 kg，sim_05 的 19.20° 刚性基线和整条退化验证链都要重跑——这是基线漂移，不是柔性结论翻转；(2) 若维持冻结几何（0.2×0.227 m 小翼），按真实面密度反而算出 0.17–0.35 kg，"占位偏轻"的实质是翼面积假设偏小，质量与几何必须绑定同改。

**"A1 柔性可忽略"翻转风险：低**。依据 `sim_11_scene_A1_summary.json`：现工况帆板尖端峰值仅 0.106 mm、终态模态能量 9.0e-10 J、基座姿态峰值 19.19989° 与刚性帆板情形差 <1e-4°——余量有 3–4 个数量级。在 f1 固定 1.0 Hz 下把 ρA 放大 1.9 倍，均匀悬臂模态形状与频率不变，尖端对基座加速度的响应基本不变，帆板对基座的反作用约按质量线性放大 ~1.9 倍，姿态差从 ~1e-4° 量级升到 ~2e-4° 量级，相对 19.2° 仍完全可忽略。A1 是慢时标臂展开（峰值在 8.3 s），激励谱远低于 0.6 Hz 下限，不存在共振通道。

**真正的风险不在 A1 而在三处**：(1) **G4（A2 收敛 Gate，当前唯一阻断项）**——实测多板阵模态间距 f2/f1≈2.8–4.3 远密于现解析悬臂的 6.27，换真实模态表后截断 m=3 的模态能量收敛只会更难，G4 修复方案须按"低阶更密集"预设；(2) 若为写实改用更长翼展/多板构型（f1 → 0.6 Hz 低端、转动惯量占比上升），A2 捕获冲量的激振响应和振铃时长会显著变化，sim_07 的 92× 对比口径也需按新参数复算；(3) 频率与构型解耦取值是伪装的自由参数——1.0 Hz 只有在"2–3 板翼"构型下物理自洽，单板小翼应为 5–10 Hz，registry v2 必须把 (翼构型, 质量, f1, 有效EI) 作为一组绑定字段而非四个独立占位。

相关文件：`F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\config\geometry\flexible_appendage_v1.yaml`、`F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\config\coupled_scene\coupled_model_v0.yaml`、`F:\China Graduate Future Flight Vehicle Innovation Competition\30_simulation\sim_11_coupled_dynamics\results\sim_11_scene_A1_summary.json`