# R07-E2 纵梁→端塞横向保持 — PATCH_NOTES

run：`01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e2_endplug_retention_20260918/`
状态：`DIGITAL_GEOMETRY_CANDIDATE_COMPLETE_WITH_NOT_RUNS`；父票 R07 **不关闭**（E2 一边）；E1/E3/E4 与 A/B 支承未动。

## 设计驱动（三条实读几何真相，已入参数块 geometric_truth_registration）

- **T1 端塞截面**：WP02 源定义 `box(20,9.8,9.8)`（字面构建将与纵梁 8×8 内孔单边干涉 0.9 mm）；WP03 `rootadd` 重建为 `box(20,7.8,7.8)`（单边间隙 0.1，SLIP_FIT_CANDIDATE）。原票文字"端塞7.8对内孔8"与 WP03 重建一致。WP02 只读不改，分歧登记不静默。
- **T2 对偶孔已存在**：X=±164 竖向 Ø4.5 孔两侧均有——纵梁双壁贯穿（WP02 `root_structure` L18）+ 端塞竖向贯穿（L27 `bore(plug,4.5,12,(-sx*3,0,0))` 默认轴 z，全局 x=∓164，WP03 重建逐位一致保留）。**E2 不新增任何孔、不修改任何既有构件。**
- **T3 十字相交冲突（本工作包核心设计约束）**：端塞竖向孔轴 (x=±164, y=±107.15) 与既有 M4 端面螺钉包络（Ø4，x∈[161,183]，轴线 y/z=±107.15）在塞心十字相交。全长竖销与 M4 螺钉几何不可共存：十字开孔销剩余韧带仅 0.1 mm（结构无效，已否决）；缩短 M4 螺钉超出本边授权。**处置 = 分段短销/栓**：每站两枚 Ø4.4 短销/栓分自两端穿入既有 Ø4.5 对偶孔，各穿一壁 + 入塞 1.8 mm，尖端让开螺钉包络 0.1 mm；两销均不阻塞 Ø3.3 导孔，**与 M4 螺钉/端框装序无关**。

## 方案（8 站 = 2 端 × 4 纵梁）

| 站 | 位置 | 构成 |
|---|---|---|
| H01–H04 | sz=+1（上纵梁） | 外侧(+z 星外)带头短栓+OD9 垫圈；舱内侧(−z)带头短栓+OD7 垫圈 |
| H05–H08 | sz=−1（下纵梁） | 舱内侧(+z)带头短栓+OD7 垫圈；翼侧(−z)无头压装销（底 z=−112.95，距翼根叉垫板顶面 −113.15 仅 0.2 → 任何外凸保持件不可行；保持=压配候选 + 垫板物理止动 REGISTERED_SECONDARY） |

- 杆 Ø4.4 入 Ø4.5 孔（隙 0.05/边，LOCATING_FIT_CANDIDATE）；头 Ø7×4；舱侧垫圈收窄 OD7（剪力板内缘 y=±103.15，OD9 将相交；OD7 留隙 0.5）。
- 新增 28 件 = 12 短栓 + 12 垫圈 + 4 无头销；整装 **459 = 431 + 28**。

## 机器裁决（evidence/ 与 logs/，全部带 sha256 边车）

- **fail-fast 探针**（s01b）：80 对布尔 0 命中，实例 459。
- **布尔干涉 PASS**（s04，`acc_interference_boolean.json`，口径=无 E2 新增）：A(E2 vs 既有) 68 对 + B(E2 两两) 12 对，**max common 0.0**，positives 0、errors 0；具名让隙检查 **64/64 全过**（含短栓尖 vs M4 螺钉 0.1、舱侧垫圈 vs 剪力板 0.5、翼侧销底 vs 翼根垫板 0.2、E2 vs E1 最近锚固件）；采样对照（0.4 mm 网格）0 命中。
- **既有项结转**（同 JSON，不静默）：E1 登记的 2 对既有干涉（RB_upper_beam_160 vs shear_web_screw_±1_150_94）当前构建复算 0.4610888343501606/85 mm³ 与 E1 登记**逐位一致**（O5 遵守）；8 对端塞 vs M4 螺钉包络重叠 49.71–49.72 mm³ 登记为 **WP02 螺纹啮合表示惯例**（Ø4 栓入 Ø3.3 导孔；端塞/螺钉均未被 E2 修改）。
- **STEP 读回 PASS**（s05b，`acc_readback_holes_coaxial.json`）：纵梁 X±164 竖孔 2/根（双壁闭合）、端塞竖孔 1/塞（十字带外闭合 + 塞心平面环外点全部落在 Ø3.3 导孔合法遮盖带 |sin a|≤1.65/2.3 内）；**同轴轴线距 max 0.0 mm、平行偏差 0.0**（全部解析轴严格同轴）。
- **BOM/质量**（s06）：新增 3337.860504 mm³，去除 0（无构件修改，恒等）；28 件全部无螺纹包络 NOT_ALLOCATED，**净分配质量增量 0 kg**（非零填，质量状态如实登记）；铝当量参考 +0.009012223 kg（仅供预算）。
- **烟测 PASS**（s07）：459 = 431 + 28（12 stub + 12 washer + 4 wing_pin），model.is_valid=True。

## 迭代史（FAIL 不覆盖）

- **V1（s05 读回判据缺陷）**：首版读回脚本对端塞塞心平面环采样误判——环外点合法带应为 X 向 Ø3.3 导孔遮盖带 |sin a|≤1.65/2.3，脚本误按仅 ±x 方向 0.6 rad 角窗判定，8 塞全数 FAIL。几何本身无缺陷（同轴 0.0/0.0）。V1 FAIL 文件保留：`evidence/acc_readback_holes_coaxial_V1_CRITERION_FAIL.json`（含 iteration 注记与边车）；s05b 修正判据后 PASS。设计参数与几何 **V1 即定稿**，无参数迭代。

## 跨 run 对照

- 4 根纵梁导出 STEP 与 E1 run 同名文件：原始 sha256 不同（OCC STEP 头含导出时间戳），归一化 `FILE_NAME` 时间戳后 **4/4 逐位一致**——E2 未触碰纵梁的直接证据。

## results 回执改动登记

- `results/service_structure_instances.json` 被 s06/s07 构建刷新（回执须匹配现行源码，同 R01/E1 模式）；E1 后 431 版备份 `logs/service_structure_instances.json.pre_e2_smoke_bak`，不恢复。

## E1 审阅观察项遵守

- O4：参数块路径写为工程根目录 `design_parameters.json`（无 config/ 子层）。
- O5：既有 2 对干涉随本 run 结转登记（见上）。
- O6：干涉对计数标签按 s04 内部键如实给出（A=E2 vs 既有 68、B=E2 两两 12、C=具名检查 64）。

## NOT_RUN（显式登记，留审阅者/后续工作包）

1. 独立第三方复验（独立复算/复跑）。
2. 载荷/强度校核：短销剪切、承压（入塞仅 1.8 mm，SHORT_ENGAGEMENT_REGISTERED）、滑移、压配保持力、振动脱出。
3. 紧固件选型/配合等级/防松/材料（全部 UNSELECTED/UNKNOWN）。
4. 制造性审查：0.05 mm/边配合隙、0.1 mm 尖端让隙、0.2 mm 翼侧间隙的公差堆叠；无头销压装工艺。
5. 工具路径实物回放（仅几何可达性登记；舱内件建议根框阶段施装）。
6. 翼侧无头销装后更换须拆翼根叉（NEEDS_SEQUENCE_REVIEW）。
7. 实物试配/装配。

## 边界遵守

E1/E3/E4 与 A/B 支承未动；未改写 gate/issues.json/CURRENT 指针；WP02 文件只读；未执行 git 提交；UNKNOWN 零填禁止遵守（质量 NOT_ALLOCATED 如实登记）。
