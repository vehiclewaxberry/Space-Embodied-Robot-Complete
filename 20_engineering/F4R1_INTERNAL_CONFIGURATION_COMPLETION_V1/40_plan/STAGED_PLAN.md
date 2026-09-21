---
title: F4R1 分阶段计划（C0–C4）
generated_at: 2026-08-27
status: DRAFT_PENDING_OWNER_SIGNOFF
depends_on: 00_charter/CHARTER.md
---

# F4R1 分阶段计划

时间锚点：比赛提交 2026-09-01（B 轨五日计划见 `90_competition_closeout/20260827_current_state_audit/10_FIVE_DAY_CLOSEOUT_PLAN.md`）。C 轨与其串行错开：9-01 前仅 C0，9-02 起进入 C1。

## C0 研究基准（2026-08-27 → 09-01，仅文档）

- 内容：四路研究（已完成，见章程 §5）+ 章程 + 本计划 + Owner 对 ODR-F4R1-01 的签署决定。
- 退出条件：本包 00/10/20/30/40 五区文件齐备；ODR-F4R1-01 签署或驳回。
- 禁止：CAD 建模、冻结区任何修改、C 产物进入比赛提交包。

## C1 内部布局方案 v1（08-27 起，Owner 指令提前启动；原计划 09-02 → 09-08）

> 时间修正依据：`00_charter/ODR_F4R1_01_SIGNED.md` §6。C3（CAD）启动条件不受此修正影响，仍为提交后 + ODR §3 确认。

- 输入：B1 设备数据表与设计规则；`20_repo_assets/REPO_ASSET_INVENTORY.md`（V2 三舱 owner 登记、VOL_MID_* 包络、IF-AV-001/IF-SV-001 接口壳）；ODR-01 frame 冻结值；CDS Rev14.1 CG 约束（±4.5/±4.5/±7 cm）。
- 工作：
  1. 设备清单 v1：OBC/EPS/BAT/ADCS（轮组×3–4、IMU、星敏、太敏、磁力矩器）/数传/推进，逐项给型号候选、包络、质量、安装面归属（前任务舱/中电子设备舱/后服务舱）；
  2. 质量预算表：填入 V2 台账 9 行 placeholder 的实际值，输出与 V3 R2 账本的调和表（差异逐行说明）；
  3. CG/惯量核算：全船 CG vs CDS 包络；不满足时用 MDPI 五目标法在 owner 体积内做配重布局优化；
  4. C-ISS-01 质量口径落地：按 Owner 裁决（减重/声明/ESPA）调整质量线；
  5. T_SB frame 闭合（C-ISS-05）；
  6. 2D 布局图（剖视+三舱分配）。
- 输出：`40_plan/` 同级新增 `50_c1_layout/LAYOUT_SCHEME_V1.yaml`、`MASS_BUDGET_V1.csv`、`CG_INERTIA_CHECK_V1.json`、布局图 SVG/PNG。
- Gate C1 验收：总质量线在裁决口径内；CG 在 CDS 包络内或有签署豁免；每一设备行有来源（数据手册 URL 或仓内证据路径）；与冻结 V3 R2 差异调和表零未解释项。
- 阻塞：C-ISS-01 未裁决则 Gate C1 不开。

## C2 帆板参数成熟化（09-09 → 09-15）

- 输入：B3 三档参数集与检验公式；`config/coupled_scene/` 占位字段；R2 帆板候选 0.78 kg/翼；七模态 ROM 与 e23 链。
- 工作：
  1. 帆板质量线统一：sim_11（0.348 kg/板）与 R2（0.78 kg/翼）双线调和——统一值或「两模型两用途」声明（C-ISS-02）；
  2. 三档参数卡 V2（新卡，不动冻结卡）：面密度 2–5 kg/m²、f1 覆盖 1–20 Hz（重点 8–20 Hz 实测档）、ζ=0.002–0.03、展开力矩 ≥2×阻力矩；
  3. 检验公式复算（B3 §e 面积×面密度、悬臂板 f1 估算）并留痕；
  4. 灵敏度仿真方案：复用 sim_11/e23 已有链，帆板三档 × 策略子集 × T_c 已扫范围，明确不改冻结 config、全部输出进新目录。
- 输出：`60_c2_panel/PANEL_PARAM_ENVELOPE_V2.yaml`、检验复算记录、灵敏度 campaign 方案书。
- Gate C2 验收：三档每档有来源或公式依据；C-ISS-03 的"f1 低 8–20×"在论文中以灵敏度区间正面回答；A1「柔性可忽略」结论按三档重述（哪些档成立、哪些翻转）。

## C3 CAD 建模（09-16 → 09-25，须 ODR-F4R1-01 §3 生效）

- 前提：比赛已提交；ODR 签署；FreeCAD 工具链（现行证据链工具，不用 SolidWorks）。
- 工作：内部二级结构（托盘/安装板/紧固）+ 设备包络实体化；**新装配引用冻结接口、不打开不修改冻结装配**；干涉检查（新实体内部 + 新实体 vs 冻结壳体/臂/线束包络）；质量核对 vs C1 预算。
- 输出：`70_c3_cad/INTERNAL_STRUCTURE_V1.FCStd/.step`、干涉报告、质量核对表。
- Gate C3 验收：非登记干涉 = 0；质量偏差在 C1 预算阈值内；frame 与 ODR-01 一致；冻结区零改动（哈希复算证明）。
- 阻塞：P08/P10/P11、MPI-01..04 外部输入仍缺 → 线束穿越区只做包络占位并标注 MEASUREMENT_PENDING，禁止零填充。

## C4 验证与论文素材（09-26 → 10 月中）

- 工作：灵敏度 campaign 跑批（C2 方案）；论文图表（布局图、质量预算表、任务对标表、灵敏度曲面、帆板三档对可行域/binding gate 的影响）；claim-evidence matrix 更新；轮组 H_available 自有设计值+裕度论证（C-ISS-07）。
- Gate C4 验收：论文每个新数字机器可复算（路径+locator+sha256）；新结论不与冻结裁决冲突（冲突处以「更新候选+差异声明」入账）。

## 横向禁止项（全周期）

- 禁止修改/重发任何既有 Gate、冻结文件、accepted URDF、sim/e 系列结果；
- 禁止把 C 轨 provisional 值写入正式 SSOT；
- 禁止用工程猜测填补外部实测输入（P08/P10/P11、T_c 夹爪实测、as-built 计量）；
- 禁止在论文中把 DESIGN_RESEARCH_CANDIDATE 写成 as-built 或 flight-qualified；
- 禁止删除任何 REPEAT/HOLD/负结果——包括 C 轨自己产生的新负结果。
