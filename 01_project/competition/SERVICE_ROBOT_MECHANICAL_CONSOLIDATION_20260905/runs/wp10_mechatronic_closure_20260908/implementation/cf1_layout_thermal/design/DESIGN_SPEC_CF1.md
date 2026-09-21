# WP10 V33 设计说明：主输入板版图修订与热路闭合（限制性 P0）

> **命名空间更正（2026-09-13）**：Codex 于 2026-09-13 恢复运行并已使用 `V32`（登记）、`V33`（底板加厚试验，HOLD）、`V34`（辅助保护板，进行中）标签。本文件原以 "V33" 命名的增量改为 **CF1**（Claude Fable 增量 1），全部产物写入 `implementation/cf1_layout_thermal/`，父本仍为 V32 电气（`ecad/revisions/v32`，哈希见 `cf1_layout_thermal/results/PARENT_SOURCE_LOCK.json`）与 V30/V28 几何。下文中的 "V33" 一律读作 "CF1"；路径 `ecad/revisions/v33/`→`cf1_layout_thermal/ecad/`，`results/v33_pcb/`→`cf1_layout_thermal/results/pcb/`，`results/v33_thermal/`→`cf1_layout_thermal/results/thermal/`，`thermal_path_v33/`→`cf1_layout_thermal/mechanical/`，`tools/*_v33.py`→`cf1_layout_thermal/tools/`。Task 0（登记 V32）已由 Codex 完成，本增量不再执行；导航文件在 Codex 空闲前不修改。


日期：2026-09-11。状态：`DESIGN_SPEC_APPROVED_BY_OWNER_2026-09-11`。本文件是 V33 的设计合同，不是交付回执；实施结果以 `DELIVERY_STATUS_V33.json` 与各回执 JSON 为准。

## 1. 目标与边界

目标：在当前 WP10 候选（V30 物理候选 + V31 输入基线 + V32 Kelvin 修正）之上，完成两件事：

1. **P0 登记 V32**：把已验证但未登记的 Kelvin 修正写入交付状态与导航。
2. **V33**：主输入板（`wp10_main_input.kicad_pcb`，100×80×1.6 mm，35 位号）的版图级修订，以及主输入模块的热路与整星热模型级修订，使 **CHB 输出 361 W 连续稳态**（臂端 360 W + 1 W 制动偏置）在声明的热工况下闭合或给出定量缺口。

不做：换器件型号（Q201 换型只做数值评估）、STOP 板 PCB、原生 SolidWorks 装配改写、实物试验、制造/上电/飞行放行结论、修改 V30/V32 源文件、修改 accepted URDF 与历史 Gate。

## 2. 输入与身份（实施前须逐项核哈希）

| 输入 | 路径（相对 `implementation/`） | 用途 |
|---|---|---|
| V32 板与原理图 | `ecad/revisions/v32/wp10_main_input.kicad_pcb`（sha `6cd2d3fa…`）、`ecad/revisions/v32/wp10_system.kicad_sch`、`ecad/revisions/v32/*.pretty` | V33 父本 |
| V32 回执 | `results/kelvin_v32/VALIDATION.json`（18 项）、`NATIVE_BUILD.json`、`MAIN_INPUT_DRC.json`、`SYSTEM_ERC.json`、`COUNTEREXAMPLES.json` | P0 登记来源 |
| 电气工况 | `coupled_closure/CANDIDATE_V30.json`（`electrical`、`analysis_scenario`）、`coupled_closure/COUPLED_RESULTS.json` | 电流/损耗热源 |
| 铜损 | `power/MAIN_INPUT_COPPER_LOSS_V29.json`（R20 8.578 mΩ，正向 3 mm/2.6 mm 段） | 版图缺陷基线 |
| 负载档 | `baseline_load_closure_v31/inputs/LOAD_TRADE_INPUTS_V1.json`（60/120/240/360 W）、`results/STEADY_POWER_TRADE.csv` | 热负载扫描 |
| 参考任务 | `baseline_load_closure_v31/inputs/REFERENCE_MISSION_V1.json` | 冷/热相位 |
| 热模型 | `tools/spatial_radiator_network.py`、`thermal/RADIATOR_MESH_VIEW_SCREEN.json`、`thermal/SPATIAL_RADIATOR_NETWORK_SCREEN.json`、`thermal/BOTTOM_RADIATOR_MOUNT.json`、`thermal/FIXED_HEAT_PATH.json`、`power/THERMAL_INTERFACE_CONTRACT.json` | 求解器、视因子、CHB 冷路径、TIM |
| 布局约束 | `thermal/RADIATOR_OBSTACLE_BOUNDS.json`（service/parking/released 各 894 盒）、`coupled_closure/host_narrowphase.py`、`coupled_closure/PLACEMENT_TRANSLATION_SCREEN.json` | 模块放置与导热带走廊 |
| 模块几何 | `coupled_closure/main_input_module.step(.py)`（132×92×43.6 mm）、`coupled_closure/mechanical_parts.py`、`coupled_closure/MECHANICAL_BRIEF.md` | 载板/悬臂/支柱父本 |

## 3. 已核实的设计事实

- 正向主电流路径为 F.Cu 3 mm 与 2.6 mm 段（`WP10_BAT_PROTECTED_PLUS`、`WP10_MAIN_FUSED`、`WP10_SENSE_MID`、`WP10_MAIN_SENSE`、`WP10_PRECHARGED_PLUS`），回流为 B.Cu 8 mm；铜厚 70 µm。热工况电池电流 24.44 A（pack 20 V、η 0.85、Q201 热态 ×2）。
- F201（Eaton 1025HC 20–30 A）原厂热条件为 3 oz 铜/10 mm 走线；V26 为 70 µm/8 mm 情景，未满足。
- `THERMAL_RESULTS.json` 的 107.060 °C 是在 `released`（翼折叠）态计算的；该态 ±Y 面被折叠翼遮挡约 90%。360 W 只发生在 `service` 态，该态 ±Y 面遮挡 26–31%、−Z 底板 0.2%、拟议 +X 蒙皮 9%。
- 整星 974 实例包围盒（service 态）扫描：模块 132×92×44 mm 在 ±Y 壁面无可贴壁位置；唯一无冲突空腔为 x[−44,88]、y[−56,36]、z[50,94]（S 坐标，mm）。模块槽 [−40,−56,50]…[92,36,94] 无任何包围盒命中；到 −Y 壁走廊 x[−15,10] 只碰 `shear_web_-1` 包围盒（该包围盒向内延伸到 y=−83.5，需实体求交裁定）；到 +Y 壁走廊只碰 `shear_web_1` 包围盒与 `PROP_PWR_ROUTE` 线束包络。
- service 态展开翼位于 z −114…−107 平面、y ±121…±721 mm，与底板共面，不遮挡底板视场。

## 4. PCB V33 设计

父本 `ecad/revisions/v32/` 复制为 `ecad/revisions/v33/`；只改板、封装库与叠层，不改原理图网络。

1. **叠层**：2 层，外层铜 3 oz（105 µm），板厚 1.6 mm；在 `.kicad_pcb` stackup 中声明；铜损与电流密度重算以 105 µm 为基准。
2. **正向主路径加宽**：所有 3 mm/2.6 mm 主电流段加宽至 ≥8 mm；受分流器 WSLP2726 焊盘（2.69 mm 宽）限制处允许 2 mm 长扩口；F201 落焊连接 10 mm 宽。加宽不得改变任何网络连接、不得跨接 F201/R201/R202。
3. **B.Cu 并行铜与过孔阵列**：在 F201 两端、R201/R202 两端的同网区域增加 B.Cu 并行铜，用 ≥12 孔（0.6 mm 钻、1.0 mm 焊盘）过孔阵列连接；每个阵列只连接同一网络。
4. **板底 TIM 接触区**：在 B.Cu 定义回流网铺铜与正向网铺铜（两者绝缘间距 ≥1.0 mm），合计覆盖不小于 60×40 mm；对应载板凸台，隔 TSP1800ST 0.203 mm 绝缘垫；正向网 F.Cu 热过孔到 B.Cu 正向铺铜。
5. **Q201 夹持接口指标**：TO-247 tab 至载板热阻 ≤1.5 K/W（TSP1800ST 25 psi 典型 0.28 K·in²/W，tab 约 0.5 in² → 0.54 K/W；余量留给夹紧不足）。指标写入 `thermal_path_v33/INTERFACE_REQUIREMENTS_V33.json`，不在本轮实测。
6. **DRC 完整性**：为 `WP10_INPUT/PASSIVES/TERMINALS/TIMING.pretty` 自定义封装补 courtyard；解除 `missing_courtyard`、`footprint_filters_mismatch`、`footprint_type_mismatch`、`track_not_centered_on_via`、`tuning_profile_track_geometries` 五条忽略；运行 `kicad-cli pcb drc --schematic-parity`；保留 V32 的 R201/R202 内连属性。

负控（必须全部检出）：把任一加宽段回退为 3 mm 时 `CURRENT_DENSITY_V33` 判 FAIL；删除一个过孔阵列时并行铜检查 FAIL；断开一段取样线时 DRC 报未连接（继承 V32 反例）；把过孔阵列错连到另一网时 DRC 报短路。

## 5. 热设计 V33

**架构 A**：主输入模块水平置于中高位空腔，载板经两根 6061 铝导热带分别接 −Y 与 +Y 剪力腹板内侧接耳；CHB 保持底板冷路径不变；+X 蒙皮只在模型中作为备选面计算，不安装。

- **模型**：沿用 `spatial_radiator_network.py`（k=130 W/m·K，ε=0.89，α=0.17，遮挡体 330 K，深空 3 K）。面：`FIXED_MINUS_Z_BOTTOM_PLATE`、`FIXED_MINUS_Y`、`FIXED_PLUS_Y`；视因子取 `service` 态网格。模块载板作为集总节点，经两条链路接入 ±Y 面补丁（补丁位置：−Y 侧 x[−15,10]、z[40,90]；+Y 侧同 x、z）。链路热阻由几何计算：R = L/(k·A) + 2×R_TIM，导热带截面 25×8 mm，长度 −Y 约 45 mm、+Y 约 65 mm，TIM 接触 25×25 mm，TSP1800ST 25 psi。
- **热源**：CHB 损耗（361 W × (1/η − 1)）、模块热 = Q201 + 分流 + 保险 + 铜 + 控制器 + 启动电阻（取 `COUPLED_RESULTS.json` 同工况值；热态约 30 W，名义约 18.5 W）、THN 4.2 W 与 STOP 16.8 W 作为"未分配已知热"单列，不塞入模块节点。
- **工况矩阵**：负载 60/120/240/360 W × η 0.85/0.9 × Q201 ×1/×2 × 环境 {HOT-A 晒 +Y、HOT-B 晒 −Z、HOT-C 晒 −Y、DARK 无日照} 于 `service` 态；COLD：`released` 态、环境 250 K、待机热、加热器 20 W×η 0.8。
- **验收**（360 W、η 0.85、Q201 ×2、三种受晒面中的最坏）：CHB 壳温 ≤105 °C；Q201 Tj ≤150 °C（Tj = 载板温 + Q201 热 × (0.31 + 1.5) K/W）；模块载板与板 TIM 区 ≤95 °C；能量平衡误差 ≤1e-6 W；10→5 mm 网格差 ≤1 °C。
- **不满足时的处理**：在模型中加入 `PROPOSED_PLUS_X_FIXED_SKIN`（214×214 mm，视因子已有）并与 ±Y 面用声明链路耦合，给出使 CHB ≤105 °C 所需的最小面积；同时给出 Q201 换 IXTX200N10L2（11 mΩ）后的损耗与温度，仅作数值，不换件。
- **机械**：`thermal_path_v33/` 用 cadgen 生成导热带 ×2、载板凸台、腹板接耳 ×2 的 STEP；用 `coupled_closure/host_narrowphase.py` 同源方法对 service/parking/released 三态做实体求交；`PROP_PWR_ROUTE` 包络冲突登记为改线需求，不算通过。

## 6. 交付物与文件布局

```
implementation/
  DELIVERY_STATUS_V32.json            # P0
  results/kelvin_v32/SHA256_V32.csv   # P0
  ecad/revisions/v33/                 # 板、封装库、工程文件
  tools/build_pcb_v33.py, verify_pcb_v33.py, falsify_pcb_v33.py, current_density_v33.py
  results/v33_pcb/{NATIVE_BUILD,MAIN_INPUT_DRC,SYSTEM_ERC,PARITY,COPPER_LOSS_V33,CURRENT_DENSITY_V33,COUNTEREXAMPLES,VALIDATION}.json
  thermal_path_v33/{*.step.py,*.step,INTERFACE_REQUIREMENTS_V33.json,NARROWPHASE_V33.json}
  tools/thermal_v33.py, verify_thermal_v33.py
  results/v33_thermal/{THERMAL_MATRIX_V33.json,THERMAL_ACCEPTANCE_V33.json,COUNTEREXAMPLES.json}
  v33_design/DESIGN_SPEC_V33.md（本文件）、README_V33.md
  DELIVERY_STATUS_V33.json、SHA256_V33.csv
```

导航更新：`CURRENT_WORKING_CANDIDATE.json` 增加 `electrical_revision=V32`、`active_layout_and_thermal=V33`；`CURRENT_candidate.md` 顶部追加 V32/V33 条目，旧条目原样保留。

## 7. 实施顺序

1. P0：写 `DELIVERY_STATUS_V32.json` 与 SHA 清单，更新两处导航。
2. PCB：复制 v32→v33；叠层；封装 courtyard；加宽与并行铜（pcbnew API）；TIM 铺铜；DRC/ERC/parity；铜损与电流密度重算；负控。
3. 热：链路几何与热阻；工况矩阵；验收判定；备选面与 Q201 换型数值。
4. 机械：导热带/凸台/接耳 STEP；三态窄相位。
5. 复核：一名只读对抗复核代理逐项核对回执与判据；修正后出 `DELIVERY_STATUS_V33.json`。

## 8. 风险与未闭合项（实施不得掩盖）

- 包围盒级无冲突不等于实体无冲突；`shear_web_-1` 包围盒向内延伸，导热带落点须以实体求交为准。
- 3 oz 铜的可制造性（最小线宽/间距）与器件焊盘不重新验证；本轮只保证 DRC 规则下无违规。
- 模型环境为示意热边界，不是轨道热真空结果；α/ε 为涂层假设。
- Q201 热态 ×2、η 0.85、共享接触 0.01 Ω 均为敏感性假设，来源见 `CANDIDATE_V30.json`。
- 实机负载谱未测，360 W 仍是筛查上界。
