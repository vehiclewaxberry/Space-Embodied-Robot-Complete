# R01 补丁说明（r01_deck_fastening_20260917）

日期：2026-09-17。构建者：WP03 R01 唯一构建者（CAD 重任务，串行）。本补丁仅授权关闭 R01 的 digital_geometry / nominal_digital_assembly 子项候选实体构建；材料/载荷/有效啮合/预紧/防松保持 UNKNOWN；父票不关闭；issues.json、gate/verdict/CURRENT 指针、R07 均未改写。

## 修改文件（改前 → 改后 sha256）

| 文件 | 改前 | 改后 |
|---|---|---|
| `20_engineering/service_robot_wp03_spacecraft_body_r1/design_parameters.json` | `190c30ac8e3126ac…`（5851 B，快照 `inputs/design_parameters.json`） | `15c2a9673be08d97…`（8768 B） |
| `20_engineering/service_robot_wp03_spacecraft_body_r1/spacecraft_model.py` | `11bd80a667505fc5…`（28328 B，快照 `inputs/spacecraft_model.py`） | `eb40ff8019e57cf3…`（32281 B） |

## design_parameters.json 变更

新增顶层字段 `deck_fastening_r01`（CRLF 行尾与文件其余部分一致，插入后 JSON 校验通过）：

- `deck_hole_pattern`：X_S=[−150,−50,50,140]、Y_S=±92.65、Ø3.4、轴 S_Z、每甲板 8 孔；名义余量 3.8 / 9.8 mm。
- `angle_to_shear_web_hole_pattern`：X_S 分段 [[−130,−70],[60,130]]、Z_S lower=−94.15 / upper=−18.5、Ø3.4、轴 S_Y、16 对。
- `deck_angle_fastener_candidate`：M3×12 候选、grip 6、头 Ø5.5、垫圈外径 ≤6；材料/等级/啮合/预紧/防松 = UNKNOWN。
- `angle_web_fastener_candidate`：M3×10 候选、grip 5；同上 UNKNOWN。
- `legacy_deck_hole_pattern_superseded`：旧孔系 X=[−150,−50,50,150]、Y=±89 保留为 legacy 字段，标注 SUPERSEDED 及缺陷（X150 孔与 x160 柱避口连通 0.2 mm，两甲板四处破边）。
- `provenance`：票据 R01_DECK_ANGLE_FASTENER_MINIMUM_PROPOSAL_R1、issues.json 快照哈希、任务书 §3.2、本 run 路径、授权范围。

## spacecraft_model.py 变更（最小修改，LF 行尾保持）

1. 新增模块级函数 `deck_fastening_parts(P)`（唯一几何来源，build() 与聚焦导出/验证脚本同源）：
   - 两剪力腹板：原纵梁孔系不变，新增 8 个角材配合孔（参数驱动）；
   - 两甲板：柱避口保留不变，孔系改为参数驱动（新 X/Y/孔径）；
   - 八段角材：外形/分段不变，新增水平腿 2 孔（与甲板同轴）+ 竖直腿 2 孔（与剪力板同轴）；
   - 32 个紧固包络（SIMPLIFIED_PROXY、THREADLESS_ENVELOPE_UNSELECTED）：头 Ø5.5、垫 Ø6×0.5×2、杆 Ø3、螺母包络 Ø6×2.4；甲板组头在甲板 +Z、剪力板组头在板外侧。
2. build() 内剪力板段与甲板段改为消费 `deck_fastening_parts(P)`（逐件 world→local→world 放置，身份不变）；新增紧固包络 add 循环（parent=EQUIPMENT_BAY，basis 标注 UNKNOWN）。
3. 其余代码零改动（diff 范围仅限上述三段）。

## 验证链（全部机器数值见 evidence/）

- 验收1 `acc1_deck_closed_holes.json`：build123d.import_step 读回，16/16 闭孔（圆柱面完整度 + 72 点环采样 + 轴心判空三重判据），旧孔位 (150,±89) 残迹为零；x=140 孔到柱避口最小距离实测 9.8 mm。
- 验收2 `acc2_connection_consistency.json`：32/32 组同轴（偏差 0）/平行（0）/夹层（3+3=6、3+2=5 mm）一致。
- 验收3/4 `acc3_acc4_bearing_notch_stack.json`：32 包络头/垫/杆/螺母承压面完整；柱避口 12 壁面在位、开口侧无封闭面、深度 12.5 mm；角材侧名义余量实测 3.8 mm；结构许用边距 UNKNOWN。
- 验收5 `acc5_builder_self_check.json`：builder_self_check，0 穿透采样命中、紧固件两两最小间距 4.5458 mm、0 违规、46 条装序约束显式记录（具名检查集合 108 项）。
- BOM/质量 `r01_bom_mass_delta.json`：ΔV=−1164.73 mm³、Δm=−0.003145 kg（铝候选密度 2.7e-6，CANDIDATE 身份）；旧反例对照（0.2 mm 连通 → 9.8 mm 净距）。
- 烟测 `logs/s08_build_smoke_log.json`：build('service', include_arm=False) 成功，383 实例（=361−10 臂+32 紧固），R01 紧固件 32；results 回执逐字节恢复（restore_matches_before=true）。

## NOT_RUN / 保留项

- 验收6（独立复验：旧破边检出、缺对偶/错轴线负控、垫圈或工具冲突负控）：NOT_RUN，留待审阅者。
- 验收3 图纸部分（局部尺寸图）：NOT_RUN。
- 整星 361 实例全装重建与 BOM.csv/STEP 正式重导出：NOT_RUN（烟测已证代码路径可执行，未覆写任何正式导出物）。
- 材料/等级/有效啮合/预紧/防松/结构许用边距：UNKNOWN，禁止零填。

---

# V2 段（2026-09-17，审阅 FAIL 关闭修复）

## 审阅 FAIL 引用（历史原样保留，不覆盖）

独立复验 run `runs/r01_deck_fastening_20260917_review/`（提交 9c5e6276）对候选 V1 判 **FAIL**：全部 16 件腹板紧固件头侧垫圈（Ø6×0.5）承压面位于剪力腹板外表面内侧 0.5 mm，环形承压区（r1.7–3.0）整体嵌入腹板材料，布尔交集体积每件 9.597566 mm³（本构建者复算值 9.597565556717031，一致）；同根因致验收4 腹板件"承压面到杆尖"实测 9.5 mm ≠ 名义 10 mm。16 件甲板紧固件干净。V1 证据文件（`acc5_builder_self_check.json`、`acc3_acc4_bearing_notch_stack.json`、`r01_bom_mass_delta.json` 等）与 V1 缺陷 STEP（`exports/v1_superseded/`，16 件带边车）原样保留。

## 最小修改说明（spacecraft_model.py，单行两常数）

V1 → V2 源码：`eb40ff8019e57cf3…`（32281 B）→ `c48c43aebe4f3fc5…`（32702 B）；`design_parameters.json` **未变**（`15c2a9673be08d97…`，EXPORT_MANIFEST_V2 已证 parameters_changed_vs_v1=false）。

`deck_fastening_parts` 腹板紧固件行仅两常数外移 0.5 mm（联动件清单）：

| 元素 | V1 中心 | V2 中心 | 说明 |
|---|---|---|---|
| 头侧垫圈 Ø6×0.5 | side×102.9 | side×**103.4** | 贴腹板外表面 side×103.15（=腹板中心 102.15 + 半厚 1 + 垫圈半厚 0.25） |
| 头 Ø5.5×3 | side×104.65 | side×**105.15** | 随垫圈联动，叠层关系不变 |
| 杆 Ø3×10 | side×98.15（不变） | 不变 | 承压面(103.15)→杆尖(93.15)=10.0 mm = 名义 |
| 螺母侧垫圈/螺母 | side×97.9 / 96.45（不变） | 不变 | 仍贴角材竖直腿内面 98.15 |

甲板紧固件、孔系、角材、腹板、甲板几何一律未动。

## 受影响/未变文件对照（几何指纹法）

STEP 文件头含写出时间戳，字节 sha256 不作同一性判据；采用几何指纹（体积/面积/面/边/实体数/bbox）对照，V1 候选函数由当前源码仅回退两常数重建，重建保真度经 `exports/v1_superseded/` 备份 STEP 指纹 16/16 校验。结果（`exports/EXPORT_MANIFEST_V2.json`）：**16 件腹板紧固件指纹变化（全部为 angle_web_fastener），其余 28 件（2 甲板、8 角材、2 腹板、16 甲板紧固件）指纹完全一致**。

## V2 验证结果

- 垫圈—腹板布尔交集：16 件全部 **0.0 mm³**（`evidence/acc3_acc4_bearing_notch_stack_v2.json`）。
- 验收4 承压面到杆尖：腹板件 10.0 mm = 名义 10；甲板件 12.0 mm = 名义 12；32/32 match（同文件）。
- acc5 V2（`evidence/acc5_builder_self_check_v2.json`）：**布尔交集口径已固化进 `scripts/s06_acc5_paths.py` 第 1b 节**（32 包络 vs 全部 CO_PRESENT 邻居 common 体积必须 =0），结果 32 件 max=0.0、0 违规、46 条装序约束、具名集合 108 项；采样口径盲区（假阴性根因）由此封闭。
- BOM/质量（`evidence/r01_bom_mass_delta_v2_compare.json`）：结构件 ΔV=−1164.729674 mm³、Δm=−0.003145 kg（AL 候选）与 V1 数值完全一致；甲板紧固件包络体积与 V1 一致；腹板紧固件包络体积每件名义 +3.534292 mm³（=π·1.5²·0.5，V1 垫圈—杆重叠去重消除的合法几何差），紧固件质量保持 UNKNOWN。
- 边车：全 run 142 个 `.sha256` 边车已刷新并逐文件核验一致（中断现场的 STEP 边车过期残留已清除）。
- 验收1/2 证据（`acc1_deck_closed_holes.json`、`acc2_connection_consistency.json`）：甲板/角材/腹板几何指纹与 V1 完全一致（EXPORT_MANIFEST_V2 证明），V1 PASS 结论原样适用，未重跑未覆盖。
- s08 整装烟测 V2：`logs/s08_build_smoke_log_v2.json`。

## V2 纪律确认

父票不关闭；材料/等级/有效啮合/预紧/防松/结构许用边距保持 UNKNOWN；issues.json/gate/CURRENT 指针/审阅目录零改写；V1 文件与 FAIL 历史未覆盖；未执行 git 提交；whole_design_complete=false；manufacturing_release=false。
