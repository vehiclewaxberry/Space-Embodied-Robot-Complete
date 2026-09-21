# F3-P4C 接触垫详细设计

**文档编号：** `F3-P4C-CONTACT-PAD-DETAILED-DESIGN-20260805`
**生成 UTC：** 2026-08-05
**状态：** `CANDIDATE_MATRIX_AND_PARAMETER_SENSITIVITY`
**前置：** F3-P4B Mid 鞍座最终取舍（S3 备份模式）
**限制：** 材料和试验数据不足，不选定具体飞行材料，只完成候选矩阵和参数敏感性分析

---

## 1. 接触垫功能要求

| 功能 | 要求 | 来源 |
|---|---|---|
| **法向支撑** | 承担 Tz 主承托（G07）或 Ry 防摆（G08） | F3-P2A |
| **切向限位** | 提供 Tx/Ty 辅助限位 | F3-P2A |
| **扭转限位** | 提供 Rx/Rz 辅助限位 | F3-P2A |
| **顺应性** | 吸收制造误差和装配误差 | F3-P2A |
| **预紧保持** | 保持 HDRM 预紧力 | F3-P2C |
| **释放可靠** | 释放后无卡滞 | F3-P2C |
| **环境适应** | 真空、温度循环、放气 | 航天环境 |
| **重复释放** | 多次释放后性能不退化 | 任务需求 |

---

## 2. 候选材料矩阵

| 材料 | 类型 | 法向刚度 | 切向刚度 | 阻尼 | 温度范围 | 真空放气 | 压缩永久变形 | 磨损 | 重复释放 | 成本 | 综合评分 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **PTFE (聚四氟乙烯)** | 聚合物 | 低 | 低 | 低 | -200~260°C | 优 | 中 | 优 | 优 | 低 | 优 |
| **POM (聚甲醛)** | 聚合物 | 中 | 中 | 低 | -40~100°C | 良 | 中 | 良 | 良 | 低 | 良 |
| **PA66 (尼龙66)** | 聚合物 | 中 | 中 | 中 | -40~120°C | 中 | 中 | 中 | 中 | 低 | 中 |
| **聚氨酯** | 弹性体 | 低 | 低 | 高 | -40~80°C | 中 | 高 | 中 | 中 | 低 | 中 |
| **硅橡胶** | 弹性体 | 低 | 低 | 高 | -60~200°C | 良 | 高 | 中 | 中 | 低 | 良 |
| **氟橡胶** | 弹性体 | 低 | 低 | 高 | -20~200°C | 优 | 高 | 良 | 良 | 中 | 良 |
| **金属弹簧** | 金属 | 高 | 高 | 低 | -200~400°C | 优 | 无 | 优 | 优 | 高 | 良 |
| **碟形弹簧** | 金属 | 高 | 高 | 低 | -200~400°C | 优 | 无 | 优 | 优 | 中 | 优 |
| **橡胶金属复合** | 复合 | 中 | 中 | 高 | -40~120°C | 良 | 中 | 良 | 良 | 中 | 良 |

**评分说明：** 优 > 良 > 中 > 差

---

## 3. 参数敏感性分析

### 3.1 法向刚度敏感性

| 参数 | 变化范围 | 对反力的影响 | 对接触压力的影响 | 对模态的影响 | 敏感度 |
|---|---|---|---|---|---|
| 法向刚度 | ±20% | TBD | TBD | TBD | `PENDING_FEA` |
| 切向刚度 | ±20% | TBD | TBD | TBD | `PENDING_FEA` |
| 厚度 | ±10% | TBD | TBD | TBD | `PENDING_FEA` |
| 接触面积 | ±10% | TBD | TBD | TBD | `PENDING_FEA` |

### 3.2 预紧力敏感性

| 参数 | 变化范围 | 对反力的影响 | 对接触压力的影响 | 对释放的影响 | 敏感度 |
|---|---|---|---|---|---|
| 预紧力 | ±20% | TBD | TBD | TBD | `PENDING_FEA` |
| 预紧弹簧刚度 | ±20% | TBD | TBD | TBD | `PENDING_FEA` |
| 预紧量 | ±10% | TBD | TBD | TBD | `PENDING_FEA` |

---

## 4. 接触垫详细参数（候选）

### 4.1 G07 (Aft) 主承托接触垫

| 参数 | 候选值 | 状态 |
|---|---|---|
| 材料类别 | PTFE 或 碟形弹簧 | `DESIGN_PROPOSAL` |
| 厚度 | 3 mm | `DESIGN_PROPOSAL` |
| 接触面积 | 50×50 mm | `DESIGN_PROPOSAL` |
| 法向刚度 | 10 N/mm | `DESIGN_PROPOSAL` |
| 切向刚度 | 5 N/mm | `DESIGN_PROPOSAL` |
| 阻尼 | 低（PTFE）或 无（碟簧） | `DESIGN_PROPOSAL` |
| 允许压缩量 | 0.5 mm | `DESIGN_PROPOSAL` |
| 预紧量 | 0.2 mm | `DESIGN_PROPOSAL` |
| 温度范围 | -50~100°C | `DESIGN_PROPOSAL` |
| 真空放气 | 优（PTFE）或 优（金属） | `DESIGN_PROPOSAL` |
| 压缩永久变形 | < 10% | `DESIGN_PROPOSAL` |
| 磨损 | 优 | `DESIGN_PROPOSAL` |
| 重复释放 | > 100 次 | `DESIGN_PROPOSAL` |

### 4.2 G08 (Fwd) 腕部支撑接触垫

| 参数 | 候选值 | 状态 |
|---|---|---|
| 材料类别 | PTFE 或 硅橡胶 | `DESIGN_PROPOSAL` |
| 厚度 | 2 mm | `DESIGN_PROPOSAL` |
| 接触面积 | 30×30 mm | `DESIGN_PROPOSAL` |
| 法向刚度 | 5 N/mm | `DESIGN_PROPOSAL` |
| 切向刚度 | 2 N/mm | `DESIGN_PROPOSAL` |
| 阻尼 | 低（PTFE）或 高（硅橡胶） | `DESIGN_PROPOSAL` |
| 允许压缩量 | 0.3 mm | `DESIGN_PROPOSAL` |
| 预紧量 | 0.1 mm | `DESIGN_PROPOSAL` |
| 温度范围 | -50~100°C | `DESIGN_PROPOSAL` |
| 真空放气 | 优（PTFE）或 良（硅橡胶） | `DESIGN_PROPOSAL` |
| 压缩永久变形 | < 10% | `DESIGN_PROPOSAL` |
| 磨损 | 优 | `DESIGN_PROPOSAL` |
| 重复释放 | > 100 次 | `DESIGN_PROPOSAL` |

---

## 5. 安装与防脱方式

| 方式 | 描述 | 适用 | 状态 |
|---|---|---|---|
| **机械卡扣** | 接触垫边缘卡入鞍座槽 | G07/G08 | `DESIGN_PROPOSAL` |
| **粘接** | 接触垫背面粘接鞍座 | G07/G08 | `DESIGN_PROPOSAL` |
| **机械压板** | 接触垫上方压板固定 | G07/G08 | `DESIGN_PROPOSAL` |
| **嵌入式** | 接触垫嵌入鞍座凹槽 | G07/G08 | `DESIGN_PROPOSAL` |

**推荐：** 机械卡扣（便于更换）+ 嵌入式（防脱）

---

## 6. 候选矩阵输出

```csv
material,type,normal_stiffness,tangential_stiffness,damping,temp_range,vacuum_outgassing,compression_set,wear,repeat_release,cost,score
PTFE,polymer,low,low,low,-200~260C,excellent,medium,excellent,excellent,low,excellent
POM,polymer,medium,medium,low,-40~100C,good,medium,good,good,low,good
PA66,polymer,medium,medium,medium,-40~120C,fair,medium,fair,fair,low,fair
Polyurethane,elastomer,low,low,high,-40~80C,fair,high,fair,fair,low,fair
Silicone_Rubber,elastomer,low,low,high,-60~200C,good,high,fair,fair,low,good
Fluoro_Rubber,elastomer,low,low,high,-20~200C,excellent,high,good,good,medium,good
Metal_Spring,metal,high,high,low,-200~400C,excellent,none,excellent,excellent,high,good
Disc_Spring,metal,high,high,low,-200~400C,excellent,none,excellent,excellent,medium,excellent
Rubber_Metal_Composite,composite,medium,medium,high,-40~120C,good,medium,good,good,medium,good
```

---

## 7. 参数寄存器

```yaml
contact_pad_register:
  G07_aft:
    material_category: PTFE_or_Disc_Spring
    thickness_mm: 3.0
    contact_area_mm: [50, 50]
    normal_stiffness_N_per_mm: 10
    tangential_stiffness_N_per_mm: 5
    damping: low_or_none
    allowable_compression_mm: 0.5
    preload_mm: 0.2
    temperature_range_C: [-50, 100]
    vacuum_outgassing: excellent
    compression_set_pct: <10
    wear: excellent
    repeat_release_cycles: >100
    status: DESIGN_PROPOSAL
  G08_fwd:
    material_category: PTFE_or_Silicone_Rubber
    thickness_mm: 2.0
    contact_area_mm: [30, 30]
    normal_stiffness_N_per_mm: 5
    tangential_stiffness_N_per_mm: 2
    damping: low_or_high
    allowable_compression_mm: 0.3
    preload_mm: 0.1
    temperature_range_C: [-50, 100]
    vacuum_outgassing: excellent_or_good
    compression_set_pct: <10
    wear: excellent
    repeat_release_cycles: >100
    status: DESIGN_PROPOSAL
```

---

## 8. 预紧压缩报告

### 8.1 G07 预紧压缩

| 参数 | 值 | 状态 |
|---|---|---|
| 预紧力 | 50 N | `DESIGN_PROPOSAL` |
| 预紧量 | 0.2 mm | `DESIGN_PROPOSAL` |
| 压缩后厚度 | 2.8 mm | `DESIGN_PROPOSAL` |
| 压缩率 | 6.7% | `DESIGN_PROPOSAL` |
| 压缩永久变形风险 | 低 | `DESIGN_PROPOSAL` |

### 8.2 G08 预紧压缩

| 参数 | 值 | 状态 |
|---|---|---|
| 预紧力 | 25 N | `DESIGN_PROPOSAL` |
| 预紧量 | 0.1 mm | `DESIGN_PROPOSAL` |
| 压缩后厚度 | 1.9 mm | `DESIGN_PROPOSAL` |
| 压缩率 | 5.0% | `DESIGN_PROPOSAL` |
| 压缩永久变形风险 | 低 | `DESIGN_PROPOSAL` |

---

## 9. 下一步

进入 F3-P4D：HDRM 结构深化（安装接口闭合，型号保持采购 TBD）。
