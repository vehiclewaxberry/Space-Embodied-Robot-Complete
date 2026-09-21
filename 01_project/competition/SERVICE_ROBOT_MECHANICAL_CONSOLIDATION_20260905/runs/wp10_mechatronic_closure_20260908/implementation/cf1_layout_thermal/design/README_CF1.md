# CF1：主输入板版图 + 导热路径热模型级修订（P0 限制性增量，r3）

**日期** 2026-09-14 建立，2026-09-17 r3 收口。r1→r2 按第一轮对抗复核修正（接耳落点、未分配热、焊盘颈、回执一致性）；r2→r3 按第二轮复核修正（**腹板按实际构造建模**、拱形梁路径、窄相位角色规则、规格符合性检查）。**父本** 电气 `ecad/revisions/v32`（哈希锁 `results/PARENT_SOURCE_LOCK.json`，84 项，`verify_thermal_cf1.py` 逐字节全查）、几何 V30、热筛 `thermal/*`、工况 `coupled_closure/COUPLED_RESULTS.json`。**命名空间** 全部产物在 `implementation/cf1_layout_thermal/`；父本文件零改动。

本文件只描述本增量做了什么、数字从哪来、哪些没做。它不是 Gate，不赋予任何制造、上电或飞行放行。

---

## 1. 结论

**方案 A（模块置于中高度腔、两条导热带接 ±Y 腹板）在按实际宿主构造建模后不闭合。** 原因是几何事实而非参数：两块 ±Y 壁（`mechanical/fixed_heat_common.py`）都是 2 mm 原始剪切腹板 + 2 mm 间隙层 + 8 mm 外辐射板，三者只在离散"桥块"处相连；接耳只能贴在 2 mm 内腹板上，而**两个接耳脚下的间隙层都是空的**（`WEB_FACE_PROBE_CF1.json`：`gap_material_under_lug_mm3 = 0`）。+Y 壁唯一的桥块是 110.6 mm 外的 CHB 冷指座；−Y 壁最近的桥块在 15 mm 外。热只能在 2 mm 腹板内横向走到桥块再进辐射板。

| 项 | r3 结果 | 限值 | 判定 |
|---|---|---|---|
| CHB 壳温（最坏 HOT_B） | 95.6 °C | ≤ 105 | 通过 |
| 载板（最坏 HOT_C） | **137.2 °C** | ≤ 95 | **不通过，超 42.2 K** |
| Q201 Tj（最坏 HOT_C） | **177.9 °C** | ≤ 150 | **不通过，超 27.9 K** |

规格 §5 的回退项（全部在四环境、10 mm 网格下评估）：全面积 +X 蒙皮 → 载板 123.7 °C（不通过）；Q201 换 11 mΩ（仅数值）→ 载板 101.4 / Tj 122.7（载板不通过）；**蒙皮 + 11 mΩ → CHB 79.9 / 载板 88.7 / Tj 110.0，通过**（仅名义热，未分配热为 0）。含 22 W 未分配热时任何组合都不通过。另加一组**假设性宿主改动**（在两接耳脚下各加一块间隙层桥块，同设备座做法；不在保存的宿主几何中，只供 owner 决策）：桥块单独 → 载板 100.6 °C（仍超 5.6 K）；桥块 + 约 30 % 面积的 +X 蒙皮 → 载板 95.0 °C（刚好）；桥块 + 11 mΩ → 78.1 °C；三者都加 → 64.5 °C。

其余结论：主输入板铜带 29.1 A/mm² / 损耗 −55.5 %（Q201 焊盘入口颈 62.9 A/mm² 超限，开放）；五个导热路径实体对宿主无物理/OEM 件干涉（父本工具因电池 D-max 包络判 REJECTED，见 §5）；模块位姿被精确窄相位拒绝，dy 0…−6 / dz 0…+6 平移无解。

一句话：**导热路径实体可以装，但按宿主实际构造它导不走热；要么宿主在接耳下加桥块，要么换热架构。这是本增量最重要的输出。**

## 2. 产物地图

| 类别 | 文件 | 状态 |
|---|---|---|
| 设计 | `design/DESIGN_SPEC_CF1.md`、`design/IMPLEMENTATION_PLAN_CF1.md` | 已执行至 Task 10 |
| PCB | `ecad/wp10_main_input.kicad_pcb`（sha `c2b52d2c…`，KiCad 10.0.6） | DRC 0/0（62 条规则严重度全启用），ERC 13 页 0 违规（4 项 KiCad 默认忽略） |
| PCB 回执 | `results/pcb/NATIVE_BUILD.json`、`MAIN_INPUT_DRC.json`、`MAIN_INPUT_DRC_PARITY.json/.log`、`SYSTEM_ERC.json`、`CURRENT_DENSITY_CF1.json`、`COPPER_LOSS_CF1.json`、`COUNTEREXAMPLES.json`、`VALIDATION.json` | **19/23**（颈密度 + 三项规格符合性检查故意不通过） |
| 热 | `tools/thermal_cf1.py`、`results/thermal/THERMAL_MATRIX_CF1.json`（128 工况）、`THERMAL_ACCEPTANCE_CF1.json`、`ACCEPTANCE_FIELD_CF1.json`（温度场）、`COUNTEREXAMPLES.json`、`VALIDATION.json` | 验证通过（`passes = false` 属实） |
| 机械 | `mechanical/THERMAL_PATH_GEOMETRY_CF1.json`（几何真源，r3）、`thermal_path_cf1.step.py`、`thermal_path_cf1.step`、`INTERFACE_REQUIREMENTS_CF1.json` | cadgen `validate` 0 失败（`results/mechanical/CADGEN_VALIDATE_CF1.json`、`CADGEN_FACTS_CF1.json`） |
| 窄相位 | `results/mechanical/WEB_FACE_PROBE_CF1.json`（腹板 0.25 mm 剖面 + 桥块图）、`NARROWPHASE_CF1.json`（五实体 vs 宿主 + 模块自检）、`MODULE_POSE_NARROWPHASE_CF1.json`、`MODULE_POSE_LOCAL_SEARCH_CF1.json` | 见 §5 |
| 交付 | `DELIVERY_STATUS_CF1.json`、`SHA256_CF1.csv`、`results/REVIEW_CF1.json`（r1/r2 复核与处置）、`tools/register_cf1_navigation.py` | 本文件同时生成 |

## 3. PCB（六项改动，无换件）

父本 V32 主路径为 70 µm 铜、3 mm 走线串联；CF1 在同一 43 个封装（35 个位号 + MH1–4 + 4 个 PORT_*）、同一焊盘几何/网络指纹上（封装属性、courtyard 与 10 个库文件确有改动，回执列出）做了：3 oz 外层铜（stackup 持久化，密度脚本从 stackup 读取并断言）；正向五段 ≥ 8 mm 铜带；`WP10_PRECHARGED_PLUS` 底层并联铜条 + 20 过孔（判据 ≥ 12）；回流 TIM 接触区 704 mm²（填充 703.98）；16 条窄走线删除、4 条馈线重布；courtyard/属性补全，DRC 62 条规则严重度全部非 ignore。

| 指标 | 父本 V29/V32 | CF1 | 依据 |
|---|---|---|---|
| 主路径 R20（同路径定义：铜带 + 到焊盘中心的颈） | 8.578 mΩ | 3.818 mΩ | `CURRENT_DENSITY_CF1.json`；父本复算相对误差 5.8e-5 |
| 20 A / 100 °C 损耗 | 4.51 W | 2.01 W | 降低 55.5 %（判据 ≥ 40 %；仅铜带模型 57.4 %） |
| 24.44 A（电池电流上界）/ 100 °C 损耗 | — | 3.00 W | 热模型复现用主支路电流 23.15 A 计铜损 2.69 W |
| 铜带最坏电流密度 | — | 29.1 A/mm² | ≤ 35，通过 |
| Q201 焊盘入口颈密度 | 134 A/mm²（2.6 mm，70 µm） | 62.9 / 55.4 A/mm² | **超限，开放项**（TO-247 封装决定，不许换件） |
| 一维真空 ΔT 最坏铜带段 | — | 10.7 K | 无对流；颈不适用 |

**对规格的偏离（`VALIDATION.json` 中以规格值做检查，故意不通过，直至 owner 接受）**：§4.2 F201 落地 10 mm → 8 mm；§4.3 F201/R201/R202 两端并联铜 → 只做 PRECHARGED 一条（那些铜带下方是 §4.4 要求的回流铺铜）；§4.4 回流 + 正向铺铜 ≥ 2400 mm² → 只有回流 704 mm²；反例"过孔阵错连他网"→"过孔移入回流铺铜"。`ecad/` 中的 `negative_broken_VIN_sense.*`、`negative_missing_internal_R201.*` 是随 V32 复制来的父本反例夹具，本增量未重跑。

**未覆盖**：原理图 parity（`kicad-cli` 在交付板上拒绝：未全注释原理图，拒绝文本在 `MAIN_INPUT_DRC_PARITY.log`，故 `footprint_filters_mismatch` 未被评估）、制板、通流试验、SOA、装配。

## 4. 热模型（`tools/thermal_cf1.py`，r3）

复用 `tools/spatial_radiator_network.py` 的 `Sheet`（−Z 底板、+Y、−Y 三块 8 mm 辐射板，ε 0.89 / α 0.17，service 态视因子网格），加：
- **两块 2 mm 内腹板**作为不辐射的面内 Sheet（同面框、同孔，厚度按探测值缩放），各自只在探测到的桥块处与辐射板耦合（R = 2 mm /(130 × 桥块面积)）：+Y 一块（CHB 座，1374 mm²）；−Y 四块（设备座 1980 mm² ×3 + CHB 座）；
- 一个不辐射的集总节点（载板，定义在拱形梁横梁/+Y 立柱交点），两条链路接到两块**内腹板**上的接耳补丁；
- 电气工况点透明代数复现 25.2 V 与 20 V 两点（输入功率 6.3e-4、Q201 1.6e-3、CHB 0）。

链路阻值（`mechanical/THERMAL_PATH_GEOMETRY_CF1.json`，与 STEP 同源）：

| 链路 | 拱形梁立柱 | 载板展宽 | TIM 源 | 导热带（57.15 mm） | TIM 汇 | 接耳贯穿 | 合计 |
|---|---|---|---|---|---|---|---|
| −Y | 1.111（立柱下行 37.1 mm） | 0.703（1-D 全宽 62 mm） | 0.181 | 0.913 | 0.181 | 0.048 | **3.136 K/W** |
| +Y | 0.392（立柱到桨形心 13.1 mm） | — | 0.223 | 0.845 | 0.167 | 0.044 | **1.672 K/W** |

Q201 壳→节点的 1.5 K/W 预算（IF_CF1_01）= TIM 0.54 + 立柱 B 上行 0.47 + 横梁 0.32 = 1.33 K/W。凸台热（铜/分流/熔断器 ~5 W）实际进入底板，此处并入节点（已披露）。

**验收**（360 W，η 0.85，Q201 ×2，pack 20 V，5 mm 网格，四环境；判据逐项取最坏）：

| 环境 | CHB 壳温 | 载板 | Q201 Tj | +Y 腹板峰值 | −Y 腹板峰值 | 通过 |
|---|---|---|---|---|---|---|
| HOT_A（+Y 受晒） | 90.2 | 134.9 | 175.6 | 119.8 | 85.9 | 否 |
| HOT_B（−Z 受晒） | **95.6** | 134.4 | 175.2 | 118.3 | 87.9 | 否 |
| HOT_C（−Y 受晒） | 90.3 | **137.2** | **177.9** | 119.5 | 93.9 | 否 |
| DARK（330 K 遮挡） | 81.9 | 125.3 | 166.0 | 109.0 | 79.1 | 否 |
| 限值 | 105 | 95 | 150 | | | |
| 最小余量 | 9.4 K | **−42.2 K** | **−27.9 K** | | | |

导热带热流仅 11–16 W 每条；+Y 腹板峰值 ~120 °C 说明热在腹板里"堵住"（唯一出口是 110 mm 外的 CHB 座，而该座同时承担 ~14 W 的 CHB 冷指热）。10→5 mm 网格差 0.18 K；128 工况矩阵中 12 例不通过（均为 360 W）。

**未分配热敏感性**（三面按面积摊分，10 mm，四环境取最坏）：0 W → 载板 136.8；+5 → 140.1；+10 → 143.3；+22 → CHB 109.0 / 载板 150.7；+33.3 → 115.3 / 157.2；+22 W 且全面积 +X 蒙皮 → 99.8 / 137.1。全部不通过。

**规格 §5 回退（名义热，四环境，10 mm）**：

| 配置 | CHB | 载板 | Tj | 通过 |
|---|---|---|---|---|
| 全面积 +X 蒙皮（214×214，2 mm，两侧 0.5 K/W 链路） | 86.3 | 123.7 | 164.5 | 否 |
| Q201 → 11 mΩ（仅数值） | 88.8 | 101.4 | 122.7 | 否 |
| 蒙皮 + 11 mΩ | 79.9 | 88.7 | 110.0 | **是** |
| 最小蒙皮面积比例（仅蒙皮） | — | — | — | 不存在（全面积不通过） |
| *假设宿主改动*：接耳脚下各加一块间隙层桥块（同设备座做法，**不在保存的宿主几何中**） | 93.9 | 100.6 | 141.3 | 否（载板超 5.6 K） |
| 桥块 + 全面积蒙皮 | 84.6 | 86.4 | 127.2 | **是** |
| 桥块 + 11 mΩ | 87.8 | 78.1 | 99.5 | **是** |
| 桥块 + 蒙皮 + 11 mΩ | 78.7 | 64.5 | 85.8 | **是** |
| 桥块 + 最小蒙皮面积比例 | 90.4 | 95.0 | 135.7 | 是（比例 0.30 ≈ 13 640 mm²） |

`released` 态同点 CHB 117.2 °C（回归检查）；冷工况 250 K、60 W 待机、20 W×0.8 加热器：CHB 24.9 / 载板 13.1 °C，无加热器 −0.8 / −5.3 °C（无冷判据，`passes = null`）。负反例：接耳补丁接错腹板 → ±Y 净辐射各移 +5.5 / −6.1 W；补丁越出面 → 断言拒绝；链路 R = 0 → 求解前拒绝。`verify_thermal_cf1.py`（35 项）从存储温度场独立复算能量平衡（+1 K 扰动可检出）、从场向量复算链路热流、按探测回执核对腹板厚度/桥块/接耳脚下无桥块/腹板不辐射、逐环境复算判据、全查 84 项父本锁。

**未覆盖**：轨道热平衡、瞬态、载板二维展宽（1-D 全宽估计）、腹板内侧向舱内的辐射（视为绝热）、TIM 压力实现、+X 蒙皮与桥块的机械设计。

## 5. 机械与窄相位（Task 9）

五个 6061-T6 实体（模块坐标，`box_at` 语义同 `coupled_closure/mechanical_parts.py`）：`CF1_CARRIER_BOSS`（64×11×5.797）、`CF1_STRAP_MINUS_Y`（25×71.15×15 杆 + 25×6×40 桨）、`CF1_LUG_MINUS_Y`（25×8×40）、`CF1_STRAP_PLUS_Y`（27×6×30 桨 + 27×45.15×15 杆 + 27×6×40 桨）、`CF1_LUG_PLUS_Y`（27×8×40）。总铝量 83 028 mm³ ≈ **224 g**。cadgen `validate` 0 失败。

**腹板真实构造**（`WEB_FACE_PROBE_CF1.json`）：两壁在接耳范围内均为 2.0 mm 内腹板（S y ±101.15…±103.15）+ 2.0 mm 空间隙 + 8.0 mm 辐射板（到 ±113.15）；接耳脚下间隙层材料 0 mm³；桥块：+Y 仅 CHB 座（x −57…8 扫描格，距接耳 110.6 mm）；−Y 设备座 ×3（最近 15 mm）+ CHB 座。V27 包围盒的内侧界（+96.5 / −83.5）是 CHB 座，不是腹板面。接耳外面与腹板面重合，接触 1080 / 1000 mm²（100 %）。+Y 壁在两份边界文件中绑定到不同 STEP（`wall_navigation_bosses.step` vs `fixed_heat_wall_pos.step`），接耳范围内剖面相同，已登记为上游不一致。

**导热带对宿主**（`NARROWPHASE_CF1.json`，`host_narrowphase.run` 原样复用，974 行/态，三态；角色规则：只有登记的包络角色不判拒，其余含 *_PROXY 全部判拒，同父本）：父本裁决 **REJECTED**——凸台 4081 mm³ 全部、−Y 杆 14 700 mm³ 落在 `WP10_RRC3570_4_D_MAX_ENVELOPE`（电池厂商最大包络）内；物理/OEM/代理件 **0 干涉**（`physical_only_view = CLEAR`）；`WP10_INTERNAL_BATTERY_BYPASS` 精确距离 37.93 mm；`PROP_PWR_ROUTE` / `PROP_DATA_ROUTE` 净距 1.000 / 1.472 mm。**模块自检**：五实体与 V30 模块 STEP 共体积 0；接触条：凸台 704 mm²、−Y 杆 1000 mm²、+Y 桨 810 mm²，TIM 间隙内无模块材料。

**整模块对宿主**（`MODULE_POSE_NARROWPHASE_CF1.json`）：位姿 `[[1,0,0,−24],[0,1,0,30],[0,0,1,61.6]]` **被拒绝**：`CLAMP_DUAL_BASE` 384.10、`CLAMP_DUAL_LID` 18.82、`POST_DUAL_0/1` 各 9.00 mm³；包络 `P60_REFERENCE_B` 66.76、`PROP_DATA_ROUTE` 263.10、电池 D-max 90 413 mm³。**局部搜索**（dy 0…−6、dz 0…+6、dx 0，16 位姿）：无物理无干涉位姿，最小 139.84 mm³（dy −6）。V30 已接受位姿同样 `REJECTED`（18 处/态），V33 三个短名单均 `false`——树内没有任何精确无干涉的模块位姿。模块实际包络 S x −71…123（含接线端子），非规格所述 −40…92（载板 + 拱形梁）。

**接口要求**（`INTERFACE_REQUIREMENTS_CF1.json`，8 项，全部 `NOT_VERIFIED`）：接耳固定进 2 mm 腹板需贯穿螺栓或嵌件；腹板侧孔位归宿主；回流区凸台的电气隔离开放。

## 6. 复核与状态

- 复核记录 `results/REVIEW_CF1.json`：r1 由 4 视角中完成的 2 个（PCB、热）提出 24 项，作者分诊，18 项修正、4 项披露、1 项部分、1 项无需；r2 由新鲜的机械与断言视角提出 18 项 + 对 24 项 r1 处置的审计，其中 2 项阻断（腹板层表误读）、4 项主要，全部在 r3 处置；两轮的反驳与综合代理都因会话额度失败，**r3 未经第三方机器复核**，只经 `verify_*` 脚本自检。
- `results/pcb/VALIDATION.json` 19/23（颈密度 + 三项规格符合性属实不通过）、`results/thermal/VALIDATION.json` 全通过（其中 `acceptance passes = false` 被复算确认）。
- **CF1 是父本 V32 之上的版图与热模型级修订，不是登记的活动候选。** 采用与否、宿主是否加桥块、是否允许 Q201 换件与 +X 蒙皮、未分配热的归宿、焊盘颈处置、模块位姿，都是 owner 决定。
- 与 Codex 并发：Codex 期间推进到 V35/V36；`coupled_closure/CANDIDATE.json` 源锁已因共享 `ecad/` 编辑而漂移，父本 `coupled_adapter` 已无法直接导入，本增量以 shim 绕过并在回执中登记。

## 7. 复现

```powershell
# 腹板探测与几何（在 implementation/ 下；cadgen 与窄相位经内存守卫）
& "G:/Windows_program_file/Anaconda/python.exe" -B -X utf8 cf1_layout_thermal/tools/probe_web_faces_cf1.py
& "G:/Windows_program_file/Anaconda/python.exe" -B -X utf8 tools/native_delta_guard.py --timeout 300 native_delta_cf1_thermal_path -- "G:/Windows_program_file/Anaconda/python.exe" -B -X utf8 "F:/codex_skill/AgentSkills/codex-skills/cad/scripts/gen" cf1_layout_thermal/mechanical/thermal_path_cf1.step.py --write --json --force
& "G:/Windows_program_file/Anaconda/python.exe" -B -X utf8 tools/native_delta_guard.py --timeout 900 native_delta_cf1_narrowphase -- "G:/Windows_program_file/Anaconda/python.exe" -B -X utf8 cf1_layout_thermal/tools/narrowphase_cf1.py
# 热（在 cf1_layout_thermal/ 下，Anaconda）
& "G:/Windows_program_file/Anaconda/python.exe" -B -X utf8 tools/thermal_cf1.py
& "G:/Windows_program_file/Anaconda/python.exe" -B -X utf8 tools/verify_thermal_cf1.py
# PCB（KiCad 10 python）
& "G:/Windows_program_file/Kicad/bin/python.exe" -X utf8 tools/current_density_cf1.py
& "G:/Windows_program_file/Kicad/bin/python.exe" -X utf8 tools/verify_pcb_cf1.py
# 交付状态与清单
& "G:/Windows_program_file/Anaconda/python.exe" -B -X utf8 tools/delivery_status_cf1.py
```
