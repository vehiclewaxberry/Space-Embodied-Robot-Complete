# 空间机器人模型参数规格

*COMP-PROT-02 output A1/A3 — parameter ownership, confidence and range policy*

---

> `STATUS: ARCHITECTURE_ONLY`<br>
> `PARAMETER_WRITES: none`<br>
> `SOURCE_OF_TRUTH: existing YAML / CSV / URDF / Gate`<br>
> `UNDECLARED_RANGE_POLICY: UNKNOWN_NOT_GUESSED`

## 📋 规格目的

本规格不新增数值，而是规定现有 12U、B601、目标模型和柔性附件的参数如何进入未来数字本体。每个参数必须同时回答：**它是什么、在哪个坐标系、单位是什么、谁拥有真值、置信度多高、用于哪一层模型、何时过期、能否外推**。

“参数范围”不再等同于随意给出上下界，而分成三类：

1. `REFERENCE_ANCHOR`：当前 SSOT 中的单点锚值；
2. `DECLARED_ENVELOPE`：项目已经明确登记的离散工况或区间；
3. `FUTURE_SWEEP`：尚未预注册的研究扫描，当前值必须为 `UNKNOWN`，不得补猜。

该规则避免为了让数字样机“看起来完整”而把暂定值升级成科学真值。

## 🔐 参数状态词表

| 状态 | 定义 | 允许用途 | 禁止用途 |
|---|---|---|---|
| `FROZEN_MODEL_ANCHOR` | 已被当前模型/路径采用，但未必实测 | 重现现有模型、建立对象身份 | 宣称物理实测或普适最优 |
| `PROVISIONAL` | 有来源和显式限制，仍待称量/标定/文献补强 | 有水印的原型、敏感性或规划 | 隐去限制后进入论文主结论 |
| `UNKNOWN` | 关键值未定、来源不足或适用域外 | 触发补测、保守保持或拒绝 | 自动取默认值、插值或语言模型生成 |
| `DEPRECATED` | 被现行 SSOT 明确替代 | 历史追溯 | 新模型输入 |
| `REJECTED_VARIANT` | 与当前批准基线冲突 | 未来独立课题对照 | 回流竞赛主线 |

注意：`FROZEN_MODEL_ANCHOR` 只表示“为了可复算而锁定”，不表示“高置信度”。

## 📊 12U 服务星参数

### 几何与质量锚点

| 参数 | 当前值 | 状态/置信度 | Canonical 来源 | 使用边界 |
|---|---:|---|---|---|
| 名义刚体外包络 | 340.5 × 226.3 × 226.3 mm | `FROZEN_MODEL_ANCHOR` / exact-standard-review pending | [model specs](../../../20_engineering/cad/spacecraft_layout/model_specs_v0.json) | 当前原创块体模型；不能写成已完成发射适配验证 |
| 展开外包络 | 440.5 × 626.3 × 276.3 mm | `FROZEN_MODEL_ANCHOR` | [service spacecraft SSOT](../../../20_engineering/config/geometry/service_spacecraft_v1.yaml) | 与展开板状态绑定；不等于收拢包络 |
| 三舱段 | 3 × [113.5, 226.3, 226.3] mm | `FROZEN_MODEL_ANCHOR` | 同上 | 布局抽象，不代表制造结构 |
| 整星参考质量 | 24.0 kg | `PROVISIONAL` / low | [mass-inertia budget](../../../20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/mass_inertia_budget_v1.csv) | 现有刚体参考；不是实测整机质量 |
| 无帆板刚体总线 | 23.3032134 kg | `FROZEN_MODEL_ANCHOR` / low | [service spacecraft SSOT](../../../20_engineering/config/geometry/service_spacecraft_v1.yaml) | 仅与下列两块等效板的代数拆分闭合 |
| 单块等效太阳翼 | 0.3483933 kg | `PROVISIONAL` / low | [flexible appendage SSOT](../../../20_engineering/config/geometry/flexible_appendage_v1.yaml) | 设计等效值，不是实物称量 |
| 安装面变换 `T_SM` | `[185.25, 0, 0]` mm，`R_y(+90°)` | `FROZEN_MODEL_ANCHOR` | [frame tree](../../../20_engineering/config/geometry/frame_tree_v1.yaml) | 所有 CAD/URDF/动力学消费者共用 |

CubeSat 官方资源页把 CDS Rev.14.1 列为 1U–12U 设计规范入口。项目本地已经保存该规范，但其 Appendix B 精确 12U 图纸仍标记人工目视复核，因此本表保留当前模型锚点，不把它升级为已验证的发射接口尺寸。[^cubesat]

### 12U 范围裁决

| 维度 | 当前允许范围表达 | 裁决 |
|---|---|---|
| 外形 | 单一现行模型锚点 + 展开/收拢状态标签 | 不建立第二套 200 × 200 × 300 mm 几何 |
| 质量 | 24.0 kg 单点参考；未来不确定区间 `UNKNOWN` | 不采用附件建议的 12–15 kg 平行基线 |
| 惯量 | 使用 CSV 中当前张量及 reference point；未来测量区间 `UNKNOWN` | 不按箱体公式重新覆盖现值 |
| 质心 | 使用现有低置信度偏置；测量误差界 `UNKNOWN` | COMP-PROT-03 前不得声称闭合 |
| 柔性 | 现有 0.7/1.0/1.3 Hz 三个设计工况 | 是唯一已登记 `DECLARED_ENVELOPE` |
| 阻尼 | `ζ = 0.01` 且 `TBD_cite_literature` | 只能带暂定标记，不能作为实测阻尼 |

## ⚙️ 机械臂与安装接口参数

| 参数 | 当前值 | 状态/置信度 | Canonical 来源 | 说明 |
|---|---:|---|---|---|
| B601 臂自由度 | 6 个 revolute | `FROZEN_MODEL_ANCHOR` / hardware matched | [arm SSOT](../../../20_engineering/config/geometry/arm_b601_v1.yaml) | 主线唯一臂构型 |
| 夹爪自由度 | 2 个 prismatic | `FROZEN_MODEL_ANCHOR` | 同上 | 不计入机械臂冗余自由度 |
| 臂质量（不含夹爪） | 4.4293 kg | `PROVISIONAL` / medium | 同上 | 取 DevArm 惯性集，待实物称量 |
| 夹爪质量 | 0.2665 kg | `PROVISIONAL` / medium | 同上 | 取混合证据链 |
| 动力学总质量 | 4.6956 kg | `PROVISIONAL` / medium | 同上与 [B601 URDF](../../../20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf) | 未来导入必须质量闭合 |
| 安装适配器质量 | 1.2 kg | `PROVISIONAL` / low | [mount SSOT](../../../20_engineering/config/geometry/arm_mount_v1.yaml) | 与 24 kg 服务星边界存在重复计数风险，待裁决 |
| 安装板/凸台 | 160 × 160 × 12 mm；Ø100 × 15 mm | `FROZEN_MODEL_ANCHOR` | 同上 | 具体孔系仍为占位，不是制造 ICD |

关节轴、上下限、原点、惯性张量与网格 URI 应从 B601 URDF 原样读取，不在第二份文档中复制一套平行数值。导入器若改变关节名、轴方向或 root 固定方式，必须形成差异报告。

7 自由度通用骨架状态为 `REJECTED_VARIANT`：它可以在未来独立研究中用于理论比较，但不能冒充 B601 硬件，也不能替换比赛/论文共享基线。

## 📚 目标模型参数

| 对象 | 质量/惯量锚点 | 抓取语义 | 状态 | 禁止外推 |
|---|---|---|---|---|
| `target_satellite_v0` | 22 kg；`diag(I)=[0.231629,0.422149,0.489336] kg·m²` | `C_sat=[290,0,0] mm`，分离环 | `PROVISIONAL` / low | 不称为真实失效卫星实测惯量 |
| `target_debris_v0` | 150 kg；`diag(I)=[74.805599,74.829903,26.592617] kg·m²` | `C_deb=[660,0,950] mm`，喷口/端环 | `PROVISIONAL` / low | 不称为特定上面级，不忽略实心等效密度问题 |

Canonical 来源为 [target model SSOT](../../../20_engineering/config/geometry/target_models_v1.yaml)。目标角速度不设项目统一范围：小卫星模型中的 2–5 deg/s 只是一项场景占位，碎片模型中的“数 deg/s 至更高量级”只作背景；具体工况必须绑定到已有仿真配置或未来预注册 scenario，不能从本架构文档抽取为新结论。

目标库的未来类别只扩展**语义组合**：立方/箱形主体、带柔性附件主体、圆柱翻滚主体。除非获得新的几何/质量/许可证据，不新增“看起来更真实”的下载模型。

## 🔗 参数所有权

| 参数族 | 唯一所有者 | 消费者 | 冲突裁决 |
|---|---|---|---|
| 几何尺寸、frame、抓取点 | `20_engineering/config/geometry/*.yaml` | CAD、URDF、动力学、可视化 | YAML/现行 SSOT 优先；消费者不得反写 |
| 块体模型外形与注释 | `model_specs_v0.json` + 对应对象 JSON | STEP/STL/URDF/展示 | 仅模型级；不能覆盖 SSOT 后续裁决 |
| 机械臂拓扑/惯性 | `arm_b601_v1.yaml` + accepted URDF | 动力学、ROS、Isaac | 名称/轴/质量差异必须 fail closed |
| 质量惯量预算 | `mass_inertia_budget_v1.csv` | 分析与场景配置 | 必须同时携带 frame、reference point、confidence |
| 柔性设计工况 | `flexible_appendage_v1.yaml` | ANCF/ROM/敏感性 | 暂定值不能升级为测量值 |
| 科学阈值与判据 | 原始 Gate/config | Physics Tool/论文 | 本文不得复制后成为新 SSOT |
| 可视材质、灯光、纹理 | 展示层资产 | Isaac/视频 | 无科学参数所有权 |

## 🔍 运行时参数记录要求

未来每个 scenario 参数集至少包含以下元数据：

| 字段 | 要求 |
|---|---|
| `parameter_id` / `version` | 稳定、不可复用的身份 |
| `value` / `unit` | SI 值；CAD 边界可保留 mm 但进入动力学前必须显式转换 |
| `frame` / `reference_point` | 对向量、张量、位姿、角动量强制填写 |
| `source_path` / `source_field` | 能定位到 YAML/CSV/URDF/JSON 的字段或行 |
| `source_hash` | 绑定实际消费文件，而不是只记文件名 |
| `confidence` | high/medium/low/unknown，不从文件冻结状态推断 |
| `status` | 本文五值词表之一 |
| `valid_for` | 模型层、对象、场景和时间范围 |
| `uncertainty` | 类型、上下界/协方差、来源；未知时明确 `UNKNOWN` |
| `used_by` | 未来运行、图表、证据包的反向索引 |

任何缺少单位、坐标系、reference point 或 provenance 的质量/惯量/角动量字段都应被视为无效输入。

## ⚠️ 系统质量边界待裁决

当前存在一个必须在 COMP-PROT-03 前关闭的工程问题：24 kg “whole-sat reference”、23.3032134 kg “bus without panels”、1.2 kg 适配器和 4.6956 kg B601 的所有权边界尚未形成系统级唯一账本。不得直接相加后把结果称为整机质量，也不得把适配器既计入服务星法兰又单列一次。

未来必须输出一张 `component_id → mass_owner → included_in → source_hash` 的闭合表，并通过以下守恒检查：

```text
sum(unique component masses) == declared system mass
recomposed CoM and inertia == runtime mass properties
no component_id counted more than once
```

这是一项实施前验收要求，不是本阶段计算任务。

## 🚫 本阶段不做的事

- 不修改任何 YAML、CSV、URDF、JSON、CAD 或 Gate；
- 不拟合、重算或优化质量/惯量/柔性参数；
- 不创建“合理默认值”填补 `UNKNOWN`；
- 不用 NASA/开源网格的外观反推质量、惯量或材料；
- 不建立新的仿真扫描范围或论文结果。

## 🔗 References

[^cubesat]: CubeSat Program, “CubeSat Information,” including the CubeSat Design Specification Revision 14.1 entry for 1U–12U systems, https://www.cubesat.org/cubesatinfo
