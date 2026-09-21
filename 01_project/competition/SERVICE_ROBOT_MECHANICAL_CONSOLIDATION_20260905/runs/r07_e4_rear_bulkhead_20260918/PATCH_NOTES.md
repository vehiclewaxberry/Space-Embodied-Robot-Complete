# R07-E4 端框→后发射保留隔框（星内侧连接闭合）— PATCH_NOTES

run：`01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e4_rear_bulkhead_20260918/`
状态：`DIGITAL_GEOMETRY_CANDIDATE_COMPLETE_WITH_NOT_RUNS`；父票 R07 **不关闭**；E1/E2/E3 与 A/B 支承（rear 肋）未动；front_service_cover 已登记 OUT_OF_SCOPE（原票仅指后端框）。

## 原票缺口（实读几何，s00b 探针 `logs/s00b_corner_truth_probe.log`）

- 后发射保留隔框 x[−189,−183] 与后端框 RB_end_frame_-1 x[−183,−177] 在 x=−183 面贴合，**Common 体积 0.0**：当前构建两者仅面贴合、无任何夹紧件——即 R07 connection_edges 第 3 边（ADAPTER_CONNECTION_REDESIGN）星内侧连接缺口。
- 既有接口链（全部既有、本边零新增孔）：隔框 4 角 Ø8 窗口（x[−189,−183]，轴 y/z=±107.15）；端框 4 角 Ø4.5 孔；原 M4×22 端面螺钉包络（锚点 x=−183，头 x[−187,−183] recessed 于窗口内，径向隙 0.5）；端塞 x[−177,−157] Ø3.3 导孔（WP02 螺纹啮合表示惯例）。
- 邻域互避（实读）：rear 肋 x[−195,−189]（y/z∈[77,95] 带，与角区 ±103.65 之外不交）；保留体积 x[−215,−195] r60（角区径向 151.5 不入侵）；E2 分段销站位 x=−164 Z 向（与新头位 x[−195,−191] 间隙 ≈16.8）。

## 方案（阶梯夹套 + 螺钉包络延长，零新增孔）

**阶梯夹套 ×4**（`e4_clamp_sleeve_{sy}_{sz}`，sy/sz=±1，角区 y/z=±107.15）：筒 OD7.9×6 滑入既有 Ø8 窗口（x[−189,−183]，隙 0.05/边）+ 法兰 OD12×2 压隔框外面（x[−191,−189]，承压环 Ø8→Ø12）+ ID Ø4.5 过 M4 杆（隙 0.25/边）；FOUR_SLEEVE_POSITIVE。真实铝候选（density 2.7e-6，E1 防压套先例，GOLD/PHYSICAL_GEOMETRY/CAD_ESTIMATE；材料牌号/压溃/承压 UNKNOWN，非零填）。

**改件螺钉 ×4**（同名替换 `RB_end_screw_-1_*`）：M4×22→M4×30 包络延长，锚点（头下面）x=−183→−191（压套法兰），头 x[−195,−191]，杆 x[−191,−161]；**延长仅在头侧，尖端 x=−161 与端塞啮合段 x[−177,−161] 逐位不变**（E2 螺纹惯例对复算逐位一致，方案核心预言，已验证）。仍为无螺纹名义包络 SIMPLIFIED_PROXY / NOT_ALLOCATED，pn 候选 `WP01-MT-M4X30-E4-ENVELOPE_WP03`。

新增 4 件（夹套）；改件 4 件同名替换不增数；整装 **487 = 483 + 4**。

## 迭代史（FAIL 不覆盖）

- **s05 读回 v1 FAIL**（`evidence/acc_readback_holes_coaxial_v1_fail.json`，内容未改仅改名归档）：两处判据缺陷——① 尖端判据误用 bb.min.X（尖端在 max 侧 −161）；② 端塞导孔按面计数=1 过严（Ø3.3 导孔被 x=−164 Z 向 E2 分段销孔 Ø4.5 横穿，STEP 读回同一孔劈为 2 个同轴圆柱面，几何事实探针核实）。
- **v2 修复**（`scripts/s05_readback_v2.py`）：尖端判据改 bb.max.X；导孔改按唯一轴（y,z）计数。v2 **PASS**。
- 探针（s01c）v1 即过：hits 0、实例 487、38 对、螺纹惯例 4 对跳过（`logs/s01c_probe_v1.log`），无几何迭代。

## 机器裁决（evidence/ 与 logs/，全部带 sha256 边车）

- **fail-fast 探针**（s01c）：76→38 对布尔 0 命中，实例 487，e4_parts 4。
- **布尔干涉 PASS**（s04，`acc_interference_boolean.json`，OCP `BRepAlgoAPI_Common` 原生 + `BRepGProp.VolumeProperties_s`，E2 审阅勘误 O2 口径；PASS 口径=无 E4 新增）：A(E4 vs 既有) 30 对 + B(E4 两两) 4 对，**max common 0.0**，positives 0、errors 0；具名让隙检查 **38/38 全过**；采样对照（0.4 mm 网格，58340 点）0 命中（薄壁盲区已声明，布尔为权威口径）。
- **既有项结转**（同 JSON，不静默）：E1 登记的 2 对既有干涉（RB_upper_beam_160 vs shear_web_screw_±1_150_94）复算：−1 侧 0.4610888343501606 与 E1 登记**逐位一致**；+1 侧 0.4610888343501606 vs 0.46108883435016085，**末位差 2.5e-16**（求积路径差异，`bit_identical=false` 如实登记）；**8 对端塞 vs M4 螺钉包络重叠（49.71 mm³ 级）与 E3 登记逐位一致 8/8**——其中后场 4 对 `screw_modified_by_e4=true` 仍 bit_identical：延长仅在头侧、重叠区 x[−177,−161] 不变，方案核心预言成立。
- **STEP 读回 PASS v2**（s05，`acc_readback_holes_coaxial.json`）：隔框 Ø8 窗口 4 角中面（x=−186）环闭合；夹套 ID Ø4.5 筒中面/法兰中面双环闭合 + 筒 OD7.9/法兰 OD12 柱面在位；改件螺钉 bbox x∈[−195,−161]、尖端 −161 与 M4×22 基线逐位一致；**同轴 max 轴线距 0.0 mm、max 平行偏差 0.0**（每角 窗口轴 vs 套 ID 轴 vs 端框孔轴 vs 栓杆轴，4 角×6 对）；孔数核对：窗口 4、端框 Ø4.5 孔 4（既有未改）、端塞导孔 1 轴/塞。
- **BOM/质量**（s06）：新增 4 夹套 1572.241459 mm³，真实铝候选 CAD_ESTIMATE **净分配质量增量 +0.004245051940 kg**（4×0.001061262985）；改件螺钉体积差实算 +100.530964915 mm³/件（基线=同源复建 screw(4,22,7,4)=430.3981935418017；现值 530.9291584566749，与 screw(4,30,7,4) 一致；解析 π·2²·8=100.5309649148734 吻合），包络 NOT_ALLOCATED 仅供预算；**removed_volume = 0**（零新增孔，无构件去除）。
- **烟测 PASS**（s07）：487 = 483 + 4（clamp_sleeve 4），改件螺钉 4 件同名替换，model.is_valid=True。

## results 回执改动登记

- `results/service_structure_instances.json` 被 s06/s07 构建刷新（回执须匹配现行源码，同 R01/E1/E2/E3 模式）；E3 后 483 版备份 `logs/service_structure_instances.json.pre_e4_smoke_bak`，不恢复。

## NOT_RUN（显式登记，留审阅者/后续工作包）

1. 独立第三方复验（独立复算/复跑）。
2. 载荷/强度校核：夹套法兰承压环（Ø8→Ø12）压溃/承压、隔框窗口壁承压、M4 栓拉伸/剪切、贴合面夹紧力与预紧（面贴合零体积连接首次引入夹紧件）。
3. 紧固件选型/配合等级/防松/材料（全部 UNSELECTED/UNKNOWN；夹套材料牌号 UNKNOWN）。
4. 供应方侧 ICD：部署器孔系/分离接口 UNKNOWN（保留体积/窗口外段/肋参数化未动，不臆造）。
5. 制造性审查：0.05/0.25 mm 每边配合隙、阶梯套筒内外圆同轴工艺、法兰 2 mm 薄壁。
6. 工具路径实物回放（仅几何可达性登记）。
7. 前端框→front_service_cover 连接（OUT_OF_SCOPE 登记，原票仅指后端框）。
8. 部署器对接实物验证；实物试配/装配。

## 边界遵守

E1/E2/E3 与 A/B 支承（rear 肋）未动；供应方侧（保留体积/窗口外段/肋）参数化未动；未改写 gate/issues.json/CURRENT 指针；WP02 文件只读；未执行 git 提交；UNKNOWN 零填禁止遵守（材料/选型 UNKNOWN 如实登记，夹套质量为 CAD_ESTIMATE 非零填）；FAIL 不覆盖（s05 v1 FAIL 归档保留）。
