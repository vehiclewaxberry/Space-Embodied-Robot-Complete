# M4 机械数字样机受限发布摘要

## 工程裁决

本轮完成了可复现、可追溯、可继续迭代的航天器—B601 机械臂机械数字样机工作发布，并建立了通向抓取动力学研究的 fail-closed 接口。

这不是制造、结构分析、资格鉴定或飞行发布。所有缺少物理权威的数据继续使用 `null/HOLD`，不得由诊断值、候选材料或名义几何替代。

| 域 | 令牌 | 结果 | 获准范围 |
|---|---|---|---|
| 机械数字样机 | `M4_DIGITAL_PROTOTYPE_RELEASED` | `PASS_SCOPED_WORKING_RELEASE` | 哈希冻结的 FreeCAD/STEP、默认静态几何、显式坐标/槽位架构、九构型数据契约、原型图样与非采购 BOM |
| 受限诊断动力学 | `SIM14_BOUNDED_DYNAMICS_READY` | `PASS_DIAGNOSTIC_ONLY` | 哈希/模式校验、fail-closed 动作掩码、理想两刚体刚性锁定动量闭合、抓取事件状态机 |
| 结构分析入口 | `STRUCTURAL_ANALYSIS_READY` | `HOLD` | `formal_fea_authorized=false`；正式 FEA 运行数为 0 |
| 生产接触与 RL | `PHYSICS_GATED_CONTACT_RL_READY` | `HOLD` | 接触、柔性体、训练策略、HIL、资格鉴定与飞行均未获授权 |

最终门禁见 `MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_GATE_V1.json`。

## 可复算证据

- 冻结输入：137 个文件、158026662 byte、0 缺失、0 重复、0 哈希漂移。
- FreeCAD 主模型：68 个对象、5 个 `App::Part`、6 个内部 `App::Link`；所有源形状有效且链接无外部悬挂。
- 中性 STEP：40 个有效实体。
- 默认构型窄相碰撞检查：15 对，0 个未分类正体积重叠；Bus—M3R 公共体积为 0，最小间距为 10.75 mm。该间距明确暴露了尚未定义的航天器载荷桥，不是装配通过结论。
- 主文件 SHA-256：
  - `SEI_DIGITAL_PROTOTYPE_V1.FCStd`：`DEA1BC93AB182C0003B37B8B8D7D7BA2559AFB649769BDE59E52FAC0DB20D481`
  - `SEI_DIGITAL_PROTOTYPE_V1.step`：`0FA64971512FAAA0B1D8EB026D4449DD513340BE8F047554D370ED359CD28020`
- 九个构型均具备统一字段契约；发布质量、质心、惯量、包围盒均为 `null/HOLD`，整机碰撞完成数为 0。
- 仅供 wiring/range check 的 Branch B 诊断质量为 29.081436764691 kg；叠加 22 kg 与 150 kg 场景目标后分别为 51.081436764691 kg 和 179.081436764691 kg。不确定度仍为 `null`，这些不是实测或发布质量。
- `spacecraft_assembly_frame` 已定义为根坐标系 `S` 的冻结恒等别名；九构型惯量均声明参考点 `configuration_system_CG`；14 条 CG/惯量不确定度记录均保留空分布、空自由度和可解析来源。
- 独立审查将 Stage B 名义净孔边韧带从错误的 11.7 mm 修正为 6.7 mm，即 `160/2 - 70 - 6.6/2`；185.25/198/208/210.405 mm 四个 x 站位已绑定物理堆栈来源。完整配合公差链仍为 `HOLD`。
- 根级验证：34/34 `PASS`，且所有预期物理 `HOLD` 被保留。

## Sim14 诊断桥

- `MECH_RL_INTERFACE_V2.yaml` SHA-256：`2A72F8B77220529B191BA6FE780924D2067195EC9CAF7A7EE5626A589B2E826F`。
- 外层必需资产 14/14 解析；第 14 项为质量—材料—公差—机构跨域审计，加载器又现场重算其内嵌 13/13 文件哈希与字节数。
- `pytest` 25/25，Ruff 通过，单位/不确定度静态审计 0 findings。
- 22 kg 场景线/角动量残差分别为 `5.421010870158359e-20 kg*m/s` 与 `5.551115123772022e-17 kg*m^2/s`。
- 150 kg 场景线/角动量残差分别为 `4.440918038809e-16 kg*m/s` 与 `2.220446049250313e-16 kg*m^2/s`。
- `1e-12` 只是不随物理公差发布的软件数值闭合阈值；当前模型没有接触力、摩擦、柔性体、IK/轨迹执行或训练策略能力。

## 内存执行事实

构建时可用物理内存为 2.061157 GiB，低于 6 GiB 门槛，因此 `memory_gate_passed=false`。本轮仅使用已登记的单进程 Owner Override；这不构成 `MEMORY_GATE_PASS`，也没有授权正式 FEA 或重型并行求解。

## 下一闭环

M5 应按 `M4_NEXT_LOOP_ACTION_REGISTER_V1.yaml` 顺序关闭：

1. 航天器—M3R 载荷桥实体、孔面基准与所有权；
2. B601 各连杆真实几何、夹爪手指和连续扫掠碰撞资源；
3. 九构型的面板/机械臂/捕获变换及故障语义；
4. 目标身份、捕获基准、接触表面与允许损伤；
5. 实测质量—质心—惯量与不确定度；
6. 材料产品形态、工艺、环境、设计许用值、公差链与机构试验；
7. 全部结构入口子门关闭后才执行正式 FEA；生产接触动力学验证后才允许 RL 训练。

最终输出文件哈希由 `M4_OUTPUT_MANIFEST_V1.json` 冻结。
