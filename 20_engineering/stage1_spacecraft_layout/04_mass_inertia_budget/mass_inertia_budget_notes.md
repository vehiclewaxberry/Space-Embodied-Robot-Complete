# 质量、质心与惯量预算说明

> 文档角色：质量/质心/惯量预算说明（中文主） | 类型：reference
> 版本：v0 | 最后同步：2026-07-09（新增 frame/reference_point/status 字段规则与 blocking-TBD 规则；坐标系引用 SSOT）
> 坐标系定义见单一真值源 [`coordinate_frame_definition_v0.md`](./coordinate_frame_definition_v0.md)，本文件不另定义坐标系。

## 1. 用途

质量、质心和惯量预算用于把第一阶段布局设计转换为第二阶段自由漂浮空间机械臂动力学模型输入。该预算不是仿真结果，而是对服务星、机械臂安装转接座、太阳板、相机、目标模型和其他关键部件的质量属性记录。

## 2. 数据来源

质量、质心和惯量可以来自以下来源，必须在 `source` 和 `confidence` 字段中标注：

| 来源 | 适用情况 | 可信度建议 |
|---|---|---|
| CAD 质量属性 | 已建立 CAD、材料密度和装配约束时 | `medium` 或 `high`，取决于 CAD 完整度。 |
| 实物称重 | 已有地面样机、模块或转接件时 | `high`，但仍需说明坐标系和参考点。 |
| 几何估算 | 早期只有外形包络和材料假设时 | `low` 或 `medium`。 |
| URDF/厂家资料 | reBot 连杆或电机已有模型参数时 | 按来源可靠性标注。 |
| 人工占位 | 只为建立预算结构时 | `low`，并在 notes 中写明待替换。 |

## 3. 从 CAD 得到参数

从 CAD 导出质量属性时，应记录：

- CAD 文件名、版本、导出日期。
- 材料密度和是否包含螺钉、线缆、传感器、安装座。
- 质心参考坐标系。
- 惯量矩阵参考点和坐标轴方向。
- 单位，统一使用 kg、m、kg m^2。

如果 CAD 只包含外形而没有真实材料或内部部件，不应把 CAD 输出写成高可信度结果。

## 4. 从估算得到参数

早期估算可以使用简单几何体：

- 长方体：用于服务星主体、电子舱、相机盒体。
- 薄板：用于太阳板、结构板、安装板。
- 圆柱：用于推进罐、火箭适配器、壳段。
- 点质量或小盒体：用于电子模块、电池、反作用轮占位。

估算时需要记录：

- 采用的等效几何体。
- 尺寸参数。
- 质量来源。
- 质心位置。
- 惯量是否已用平行轴定理转换到服务星坐标系。

## 5. 为什么质心/惯量重要

自由漂浮空间机械臂没有固定地面基座。机械臂关节运动会通过动量守恒反作用到服务星本体，导致基座平动和姿态扰动。服务星质量越小、机械臂安装点越偏离质心、惯量分布越不合理，机械臂运动引起的姿态扰动越明显。

因此，质量、质心和惯量直接影响：

- 基座姿态扰动曲线。
- 末端轨迹跟踪误差。
- GJM 建模中的系统耦合项。
- RNS 规划中用于抑制基座反作用的零空间优化方向。
- 朴素规划与 RNS 规划对比图是否有可信输入。

## 6. 对 GJM/RNS 仿真的需求

第二阶段 GJM/RNS 仿真至少需要：

- 服务星本体质量。
- 服务星本体质心位置。
- 服务星本体惯量矩阵。
- reBot 机械臂各连杆质量属性。
- 服务星坐标系到机械臂基座坐标系的固定变换。
- 目标模型质量、质心、惯量和抓取点位姿。
- 碰撞几何和视觉/抓取坐标系，用于解释规划约束。

## 7. CSV 字段说明（与 `mass_inertia_budget_v0_template.csv` 对齐）

坐标系取值必须来自坐标系单一真值源 [`coordinate_frame_definition_v0.md`](./coordinate_frame_definition_v0.md)（`S/B/M/T/D/C`），本表不另定义坐标系。

| 字段 | 说明 |
|---|---|
| `component` | 部件名称，如 servicer_structure、battery_pack、robot_mount_adapter、camera_payload、target_satellite。 |
| `subsystem` | 分系统，如 structure、power、avionics、robotics、payload、target_model。 |
| `configuration` | 状态构型，如 baseline、stowed_deployed、scenario。 |
| `frame` | **参考坐标系**（取自 SSOT）：服务星部件用 `S`；转接座/机械臂可用 `S` 或 `M`；目标 `T`；碎片 `D`。不得留空。 |
| `reference_point` | **质心/惯量参考点**，如 `S_origin`、`CoM`、`mount_plane`、`T_origin`；不同参考点的惯量不可直接混用。 |
| `mass_kg` | 部件质量，单位 kg。 |
| `x_m, y_m, z_m` | 质心在 `frame` 下的位置，单位 m。 |
| `Ixx_kgm2` 等 | 惯量矩阵分量（关于 `reference_point`），单位 kg m^2。 |
| `material`, `density_kg_m3` | 材料与密度；估算时写假设值并在 notes 注明。 |
| `source` | CAD、measurement、estimate、URDF、datasheet、allocation、placeholder 等。 |
| `confidence` | `low`、`medium`、`high`。 |
| `status` | `blocking_TBD`（缺关键字段，禁入动力学）/ `estimate`（占位可用）/ `cad_derived` / `measured`。 |
| `notes` | 参考坐标系补充、估算假设、待更新事项。 |

> **阻塞规则（blocking-TBD）**：任一对象只要缺 `mass_kg`、质心 `x/y/z`、惯量、`frame` 或 `reference_point` 其中之一，`status` 必须为 `blocking_TBD`，且**不得进入第二阶段动力学仿真**（Basilisk / SPART / 42 / SmallSatSim）。缺失字段作为阻塞项前推，不得静默填充或编造。

## 8. 填写原则

- 不知道的值留空或写 `TBD`，不要编造。
- 每个对象必须有 `frame`（取自 SSOT）与 `reference_point`；缺则 `status=blocking_TBD`，见 §7 阻塞规则。
- 估算值必须写明估算方法。
- CAD 值必须写明 CAD 版本。
- 惯量矩阵必须说明参考点；不同参考点的惯量不能直接混用。
- 服务星本体、机械臂转接座、reBot、目标模型应分开记录，便于后续动力学组合。

## 9. 原英文 v0 的补充与冲突澄清（2026-09-06 合并）

原 `mass_inertia_budget_v0_notes.md` 的共同说明归入上文，独有输入细节如下。原文在统一整理账本保留可恢复快照。

- 厂家参数附资料名称、版本和可信度；预算分配占位附分配原因与责任人。CAD 导出除文件、材料、密度和日期外，还要记录装配构型。
- 完整保留 `Ixy, Ixz, Iyz` 惯性积字段；未知不等于零。跨参考点转换记录平行轴定理，跨坐标轴表达还需记录方向变换。
- 原英文曾将 CAD 导出、称重和核验资料并列于可称为 measured 的来源；这与中文主表的成熟度区分不一致。整理后沿用主表：CAD 结果为 `cad_derived`，实物测量为 `measured`，厂家资料以 `source=datasheet` 明示。此次只澄清文义，未修改 CSV 或升级任何既有参数状态。
- 空白、`TBD`、旧 `stage1_estimate` 可以出现在早期模板，不能替代 §7 的完整性要求；缺必需字段仍为 `blocking_TBD`。
- 变换按坐标 SSOT：`T_SM` 为服务星至臂安装系；旧文把此桥接称为 `T_SB`，现 `T_SB` 表示自由漂浮基座变换，两者不得混用。相机使用 `T_SC`，目标星/碎片初态分别使用 `T_ST` / `T_SD`。
- 原 Stage 2 曾引用 `reBot-DevArm_fixend.urdf` 或有记录的等价模型作为臂质量来源；这是该历史阶段的来源说明，当前 WP03/R2 输入必须按各自清单定位。
