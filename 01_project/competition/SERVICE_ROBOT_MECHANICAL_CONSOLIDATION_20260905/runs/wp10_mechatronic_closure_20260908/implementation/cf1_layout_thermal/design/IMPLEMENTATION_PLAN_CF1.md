# WP10 V33 实施计划（P0 登记 V32 + 主输入板版图修订 + 热路闭合）

> **命名空间更正（2026-09-13）**：Codex 于 2026-09-13 恢复运行并已使用 `V32`（登记）、`V33`（底板加厚试验，HOLD）、`V34`（辅助保护板，进行中）标签。本文件原以 "V33" 命名的增量改为 **CF1**（Claude Fable 增量 1），全部产物写入 `implementation/cf1_layout_thermal/`，父本仍为 V32 电气（`ecad/revisions/v32`，哈希见 `cf1_layout_thermal/results/PARENT_SOURCE_LOCK.json`）与 V30/V28 几何。下文中的 "V33" 一律读作 "CF1"；路径 `ecad/revisions/v33/`→`cf1_layout_thermal/ecad/`，`results/v33_pcb/`→`cf1_layout_thermal/results/pcb/`，`results/v33_thermal/`→`cf1_layout_thermal/results/thermal/`，`thermal_path_v33/`→`cf1_layout_thermal/mechanical/`，`tools/*_v33.py`→`cf1_layout_thermal/tools/`。Task 0（登记 V32）已由 Codex 完成，本增量不再执行；导航文件在 Codex 空闲前不修改。


> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改 V30/V32 源的前提下，登记 V32，并产出 V33：3 oz 铜、8 mm 正向主路径、B.Cu 并行铜/过孔阵列、板底 TIM 铺铜、封装属性与 DRC 补全；在 `service` 态用现有求解器加入模块载板节点与双导热带，判定 360 W 稳态是否闭合。

**Architecture:** 所有产物写入 `implementation/` 下新目录；PCB 用 KiCad 10.0.6 的 `pcbnew` Python API 编辑并用 `kicad-cli` 做 ERC/DRC/parity；热模型复用 `tools/spatial_radiator_network.py` 的 `Sheet`，在本地脚本里扩展一个集总节点；机械件用 cadgen（build123d）生成 STEP，用 `coupled_closure/host_narrowphase.run` 做三态实体求交。

**Tech Stack:** `G:/Windows_program_file/Kicad/bin/python.exe`（pcbnew 10.0.6）；`70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe`；`G:/Windows_program_file/Anaconda/python.exe`（numpy/scipy/OCP/build123d）；`F:/codex_skill/AgentSkills/agents-skills/cad/scripts/gen`；`tools/native_delta_guard.py`（内存守卫，名称须以 `native_delta_` 开头，上限 1400 MiB）。

## Global Constraints

- 不修改 `ecad/revisions/v32/*`、`coupled_closure/*`、`thermal/*`、`power/*`、accepted URDF、任何 `*_gate_check.json`。
- 设计判据（来自 `v33_design/DESIGN_SPEC_V33.md`）：CHB 壳温 ≤105 °C；Q201 Tj ≤150 °C（Tj = 载板温 + Q201 热 × (0.31 + 1.5) K/W）；载板与板 TIM 区 ≤95 °C；能量平衡 ≤1e-6 W；10→5 mm 网格差 ≤1 °C。
- 电气工况：pack 20/22/25.2/29.4 V、η 0.85/0.9、Q201 热态 ×1/×2、铜 100 °C；热工况电流 24.44 A（`COUPLED_RESULTS.json` 第 2 个工况点）。
- 板坐标：KiCad y 向下；板 100×80 mm；正向主路径 y 带 8–16 mm，中心 y=12。
- 不运行任何旧 `run_all.py`；不启动 SolidWorks；不 git commit。

---

### Task 0: P0 登记 V32

**Files:**
- Create: `implementation/DELIVERY_STATUS_V32.json`、`implementation/results/kelvin_v32/SHA256_V32.csv`
- Modify: `implementation/CURRENT_WORKING_CANDIDATE.json`、`../../CURRENT_candidate.md`（顶部追加）

- [ ] 用 Python 计算 `results/kelvin_v32/` 与 `ecad/revisions/v32/` 全部文件 sha256 → `SHA256_V32.csv`
- [ ] 写 `DELIVERY_STATUS_V32.json`：`revision=V32`、`kelvin_items_closed=4`、`system_ERC_violations=0`、`main_input_DRC_unconnected=0`、`negative_controls_passed=2`、`independent_checks=18`、`registered_by=Claude Fable 5.1 (P0)`、引用回执路径+sha
- [ ] `CURRENT_WORKING_CANDIDATE.json` 增加 `electrical_revision` 块指向 V32
- [ ] `CURRENT_candidate.md` 顶部追加 V32 条目（旧条目不动）
- [ ] 验证：重新读取两个 JSON 可解析；CSV 行数 = 文件数

### Task 1: V33 目录与 3 oz 叠层

**Files:**
- Create: `ecad/revisions/v33/`（复制 v32 全部文件）、`tools/build_pcb_v33.py`
- Test: `tools/verify_pcb_v33.py::check_stackup`

- [ ] 复制 `ecad/revisions/v32/*` → `ecad/revisions/v33/`，记录父本 sha 到 `results/v33_pcb/PARENT_SOURCE_LOCK.json`
- [ ] 在 `wp10_main_input.kicad_pcb` 的 `(setup` 块内插入 `(stackup (layer "F.SilkS" (type "Top Silk Screen")) (layer "F.Paste" (type "Top Solder Paste")) (layer "F.Mask" (type "Top Solder Mask") (thickness 0.01)) (layer "F.Cu" (type "copper") (thickness 0.105)) (layer "dielectric 1" (type "core") (thickness 1.37) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02)) (layer "B.Cu" (type "copper") (thickness 0.105)) (layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01)) (layer "B.Paste" (type "Bottom Solder Paste")) (layer "B.SilkS" (type "Bottom Silk Screen")) (copper_finish "None") (dielectric_constraints no))`
- [ ] 验证：`pcbnew.LoadBoard` 成功；`kicad-cli pcb drc` 返回码 0；文本中出现 `(thickness 0.105)` 两次

### Task 2: 正向主路径加宽（pcbnew API）

**Files:**
- Modify: `ecad/revisions/v33/wp10_main_input.kicad_pcb`（经 `tools/build_pcb_v33.py`）

规则：删除下列现有 F.Cu 正向段并按同网重建 8 mm 宽、中心 y=12 的直线段；J204/J206 九针网格段（3.2 mm）保留。

| 网 | 删除段（起→止，宽） | 新段（起→止，宽） |
|---|---|---|
| WP10_BAT_PROTECTED_PLUS | (7,15)→(15.325,15) 3.0 | (7,12)→(16.9,12) 8.0；补 (15.325,12)→(15.325,15) 3.25 |
| WP10_MAIN_FUSED | (24.675,15)→(31.535,14.11) 3.0 | (23.1,12)→(32.8,12) 8.0；补 (24.675,12)→(24.675,15) 3.25；(31.535,12)→(31.535,14.11) 2.69 |
| WP10_SENSE_MID | (36.465,14.11)→(42.535,14.11) 3.0 | (35.2,12)→(43.8,12) 8.0；补 (36.465,12)→(36.465,14.11) 2.69；(42.535,12)→(42.535,14.11) 2.69 |
| WP10_MAIN_SENSE | (47.465,14.11)→(50,14.11) 3.0；(50,14.11)→(50,10) 3.0；(50,10)→(59.45,10) 5.0；(59.45,10)→(59.45,17) 2.6 | (46.2,11)→(59.45,11) 8.0（y 7–15，避开栅极焊盘 (54,17) 上缘 15.5）；补 (47.465,11)→(47.465,14.11) 2.69；(59.45,11)→(59.45,17) 3.7 |
| WP10_PRECHARGED_PLUS | (64.9,17)→(69,17) 2.6；(69,17)→(90,17) 6.0；(90,17)→(93,15) 6.0 | (64.9,12)→(93,12) 8.0；补 (64.9,12)→(64.9,17) 4.2 |

- [ ] 实现 `build_pcb_v33.py`：按 (网, 起点, 终点) 精确匹配删除；新建 `pcbnew.PCB_TRACK`；保存前后各做 `geometry()` 指纹（复用 `build_kelvin_v32.py` 的函数）并把差异写入 `results/v33_pcb/NATIVE_BUILD.json`
- [ ] 运行 `kicad-cli pcb drc --severity-all --format json`；若出现 clearance 违规，把对应新段宽度减到 6 mm 并记录，不得删除违规规则
- [ ] 验证：正向路径连通（DRC `unconnected_items=[]`）；违规 0

### Task 3: B.Cu 并行铜与过孔阵列

**Files:**
- Modify: `ecad/revisions/v33/wp10_main_input.kicad_pcb`

- [ ] 新增 B.Cu 段：WP10_MAIN_FUSED (23.6,18.5)→(32.2,18.5) 宽 7.0；WP10_SENSE_MID (35.6,18.5)→(41.2,18.5) 宽 7.0
- [ ] 过孔阵列（`PCB_VIA`，钻 0.6、盘 1.0，同网）：MAIN_FUSED 两端 x=24.2/25.4 与 x=30.6/31.8，y=16.2/17.4/18.6/19.8/21.0 各 2×5；SENSE_MID 两端 x=36.2/37.4 与 x=39.4/40.6，同 y 列
- [ ] DRC 0 违规；`verify_pcb_v33.py::check_parallel_copper` 断言两段存在且网名正确、过孔数 ≥40

### Task 4: B.Cu 回流铺铜（TIM 接触区）

- [ ] 新增 `pcbnew.ZONE`：层 B.Cu，网 WP10_INPUT_RETURN，多边形 (18,3)-(82,3)-(82,14)-(18,14)，`SetMinThickness(0.25mm)`、`SetLocalClearance(0.3mm)`；`ZONE_FILLER(board).Fill(board.Zones())`
- [ ] 验证：填充面积 ≥ 600 mm²（`zone.GetFilledArea()`）；DRC 0 违规；铺铜与 J204/J206 B.Cu 网格无交叠

### Task 5: 封装属性与 DRC 规则补全

**Files:**
- Modify: `ecad/revisions/v33/WP10_INPUT.pretty/*.kicad_mod`、`ecad/revisions/v33/WP10_TIMING.pretty/C201_MKP2_1uF_P5_Slot2.kicad_mod`、`ecad/revisions/v33/wp10_main_input.kicad_pro`

- [ ] 用 `pcbnew.FootprintLoad/Save` 设置 `SetAttributes`：IXTH_TO247、MKP2_*、MKS2_*、C201_MKP2 → THT；LM5069、LT3013、SMBJ30A、STPS3H100U、WSLP2726 → SMD；板内实例同步（`f.SetAttributes`）
- [ ] `.kicad_pro` 中 `missing_courtyard`、`footprint_filters_mismatch`、`footprint_type_mismatch`、`track_not_centered_on_via`、`tuning_profile_track_geometries` 改为 `error`
- [ ] 运行 `kicad-cli pcb drc --schematic-parity --severity-all --format json -o results/v33_pcb/MAIN_INPUT_DRC.json`；`kicad-cli sch erc` → `SYSTEM_ERC.json`
- [ ] 验证：`violations=[]`、`unconnected_items=[]`、`schematic_parity=[]`、`ignored_checks` 中不再含上述五条

### Task 6: 铜损与电流密度重算

**Files:**
- Create: `tools/current_density_v33.py`，输出 `results/v33_pcb/COPPER_LOSS_V33.json`、`CURRENT_DENSITY_V33.json`

- [ ] 从 v33 板读取正向/回流各段（长度、宽度、层），铜厚 0.105 mm，ρ20=1.72e-8 Ω·m，α=0.00393/K；计算 R20、R100、I²R@24.44 A/100 °C；逐段电流密度 A/mm²
- [ ] 一维真空温升估计：每段 q=I²R100/L (W/m)，通过 FR4 到 B.Cu 铺铜 R_FR4 = 1.6e-3/(0.3·w·L)，ΔT_seg = q·L·R_FR4；报告最大 ΔT
- [ ] 判据：正向路径最大电流密度 ≤35 A/mm²；总铜损（20 A、100 °C）相对 V29 4.51 W 下降 ≥40%
- [ ] 负控：把任一 8 mm 段临时改回 3 mm 时判 FAIL（在内存中模拟，不写盘）

### Task 7: PCB 反例与验证回执

- [ ] `tools/falsify_pcb_v33.py`：(a) 删除 MAIN_FUSED 过孔阵列 → `check_parallel_copper` FAIL；(b) 断开 (31.535,12)→(31.535,14.11) 段 → DRC unconnected ≥1；(c) 把一个过孔网改为 WP10_INPUT_RETURN → DRC 短路/clearance 违规；写 `results/v33_pcb/COUNTEREXAMPLES.json`
- [ ] `tools/verify_pcb_v33.py` 汇总 → `results/v33_pcb/VALIDATION.json`（父本字节不变、V30 源锁不变、网表针脚记录不变、Kelvin 属性保留、叠层、加宽段、并行铜、铺铜面积、DRC/ERC/parity、铜损判据、反例）

### Task 8: 热模型 V33（service 态 + 模块节点）

**Files:**
- Create: `tools/thermal_v33.py`、`tools/verify_thermal_v33.py`；输出 `results/v33_thermal/THERMAL_MATRIX_V33.json`、`THERMAL_ACCEPTANCE_V33.json`、`COUNTEREXAMPLES.json`

- [ ] 导入 `tools/spatial_radiator_network.py` 的 `Sheet`、`SIGMA`；面与网格：`thermal/RADIATOR_MESH_VIEW_SCREEN.json` 中 `state=='service'` 的 `FIXED_MINUS_Z_BOTTOM_PLATE`（含 `BOTTOM_RADIATOR_MOUNT.json` 几何）、`FIXED_PLUS_Y`、`FIXED_MINUS_Y`
- [ ] CHB 载荷：sheet0、中心 `chb_path.center_xy_mm`、尺寸 [55.9,59]、功率 361·(1/η−1)；CHB 冷指链路沿用 `SPATIAL_RADIATOR_NETWORK_SCREEN.json` 的 `links_endpoints` 与 25 psi `per_link_R_K_W`
- [ ] 扩展求解：在 `solve` 的线性系统外增加 1 个集总节点（模块载板，不辐射），两条链路：−Y 补丁 center=[−3,25] size=[25,40]（S x −15..10，z 5..45 → 面坐标）R1；+Y 补丁同尺寸 R2；R = L/(k·A)+2·R_TIM，k=167，A=25×15 mm，L1=45 mm，L2=65 mm，R_TIM=0.28/(1.55 in²)
- [ ] 模块热 Q_module 由工况给出：Q201+shunts+fuse+copper+controller+startup（从 `COUPLED_RESULTS.json` 同工况点取，铜损用 Task 6 的 V33 值替换）
- [ ] 工况矩阵：负载 {60,120,240,360} × η {0.85,0.9} × Q201 {×1,×2} × 环境 {HOT-A: solar 1361 on +Y; HOT-B: solar on −Z; HOT-C: solar on −Y; DARK}；网格 10/5 mm
- [ ] 判定：按 Global Constraints；输出每工况 CHB 壳温、Q201 Tj、载板温、各面净辐射、链路热流
- [ ] 若 360 W/η 0.85/×2/最坏受晒 不闭合：加入 `PROPOSED_PLUS_X_FIXED_SKIN` 面（网格已有，`surface_built=False` 视为设计面），与 ±Y 面各以 R=0.5 K/W 链路耦合，二分搜索使 CHB ≤105 °C 的最小面积比例；另算 Q201 换 11 mΩ 的温度
- [ ] 冷工况：`released` 态网格，环境 250 K，待机热（取 60 W 档）+加热器 20 W/0.8
- [ ] 反例：链路 R→1e6（导热带缺失）时载板温超限；环境改回 `released` 态时 ±Y 净辐射显著下降；能量残差 >1e-6 时拒绝
- [ ] `verify_thermal_v33.py`：复算一行能量平衡、复算链路 R、检查 service 网格 sha 与 `RADIATOR_MESH_VIEW_SCREEN.json` 一致

### Task 9: 导热带/凸台/接耳 STEP 与三态窄相位

**Files:**
- Create: `thermal_path_v33/thermal_path_v33.step.py`、`thermal_path_v33/INTERFACE_REQUIREMENTS_V33.json`、`thermal_path_v33/narrowphase_v33.py`、输出 `NARROWPHASE_V33.json`

- [ ] 模块位姿 `T_S_module=[[1,0,0,-24],[0,1,0,30],[0,0,1,61.6],[0,0,0,1]]`（模块框 x[−16,116] y[−86,6] z[−11.6,32] → S x[−40,92] y[−56,36] z[50,93.6]）
- [ ] 零件（模块坐标，mm）：载板凸台 `box_at(18,-14,-11.6-5.6,64,11,5.6)`（板底 TIM 区正下方，S z 44.4–50）；−Y 导热带 L 形：`box_at(9,-131.15,-9.6,25,45,15)`（S x −15..10，y −101.15..−56，z 52..67）；+Y 导热带 `box_at(9,6,-9.6,25,60.5,15)`（S y 36..96.5）；接耳 ×2：`box_at(9,-139.15,-14.6,25,8,40)` 与 `box_at(9,66.5,-14.6,25,8,40)`（贴腹板内面，8 mm 厚）
- [ ] `INTERFACE_REQUIREMENTS_V33.json`：Q201 壳-载板 ≤1.5 K/W；导热带-接耳 TIM 25×40 mm @25 psi；接耳-腹板 M3×4 预紧待验；材料 6061-T6
- [ ] cadgen：`gen thermal_path_v33/thermal_path_v33.step.py --write --json`（经 `native_delta_guard.py`）；`inspect refs --facts`
- [ ] 窄相位：复用 `coupled_closure/host_narrowphase.run(parts,pose,parent)`，parent=`mechanical/MAIN_INPUT_PLACEMENT_BOUNDS_V27.json`（974 行/态）；输出到 `thermal_path_v33/NARROWPHASE_V33.json`
- [ ] 判定：三态 `collisions` 为空 → `SAVED_GEOMETRY_CLEAR_ONLY`；否则列出配对与体积，PROP_PWR_ROUTE 类 FUNCTIONAL_ENVELOPE 交叠登记为改线需求

### Task 10: 独立复核、交付状态与导航

- [ ] 启动一名只读复核代理（Workflow 单代理）：核对 `results/v33_pcb/VALIDATION.json`、`results/v33_thermal/THERMAL_ACCEPTANCE_V33.json`、`NARROWPHASE_V33.json` 与设计判据的一致性，尝试反驳
- [ ] 按复核修正；写 `DELIVERY_STATUS_V33.json`、`SHA256_V33.csv`、`v33_design/README_V33.md`
- [ ] `CURRENT_WORKING_CANDIDATE.json` 增加 `active_layout_and_thermal` 指向 V33；`CURRENT_candidate.md` 顶部追加 V33 条目
