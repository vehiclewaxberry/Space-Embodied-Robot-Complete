# V5_SOLAR_ARRAY_RESIDUAL_GAPS — 太阳翼残余缺口登记（2026-08-10）

性质：只读分析报告。本报告不断言任何新证据、不修改任何受保护文件、不触碰 SolidWorks 会话（PID 87516 保留给编排器）。所有结论来自对现有文本/JSON/目录清单的静态比对。

## 0. 方法与输入

比对对象（as-required）：

- `00_authority/SOLAR_ARRAY_INTERFACE_REQUIREMENTS.md`（下称 REQU，CANDIDATE_INTERFACE_FROZEN_FOR_NATIVE_BUILD）
- `00_authority/SOLAR_ARRAY_CANDIDATE_BUILD_PLAN.md`（下称 PLAN）
- 上级指令要求的 per-state 记录、OD9 出口、收拢登记、deployed stop、质量占位、原生 B-rep 间隙复验六类闭合项

比对基准（as-built）：

- `13_validation/V5_SOLAR_ARRAY_NATIVE_RECEIPT_20260810T135905.775293Z.json`（下称 RCPT，verdict=`V5_SOLAR_ARRAY_CANDIDATE_NATIVE_PANELS_AND_SIDE_ASMS_PASS`，RCPT:318）
- `99_tools/F3R2_V5_NATIVE_SOLAR_ARRAY_BUILD.py`（下称 SCRIPT）
- `01_native_parts/solar_array/`（仅 6 个 SLDPRT）、`02_native_subassemblies/`（L/R_SOLAR_ARRAY.SLDASM）目录清单
- `04_configurations/`、`05_clearance/`、`06_mass_properties/`、`08_bom/`、`09_digital_thread/` 文本内容
- `13_validation/V5_SOLAR_ARRAY_FAIL_20260810T1345..1350*.json`（5 份 FAIL 回执）

## 1. 状态总览

| 状态 | 计数 | 条目 |
|---|---:|---|
| DONE | 5 | R1, R5, R13, R14, R15 |
| PARTIAL | 4 | R2, R3, R7, R16 |
| MISSING | 7 | R4, R6, R8, R9, R10, R11, R12 |
| DEFERRED（设计性推迟，已登记） | 1 | R4 的铰链配合部分见 §3 F-1 |

关键结论：RCPT 只证明“6 块简化板 + 2 个含 7 配置名集的侧装配存在且可冷重开”。配置内部位姿、铰链、止挡、收拢/线束接口、质量占位、数字线程注册、原生间隙证据全部未闭合。

## 2. 要求逐条对照表

| # | 要求（来源） | as-built 证据 | 状态 | 闭合责任 |
|---|---|---|---|---|
| R1 | 6 panel 简化板、禁止太阳电池片（REQU §2.1 行67；PLAN §1 行28） | 6 个 SLDPRT 冷开 0 错 0 警、单实体、box 6.0×56.67×227.0（RCPT:21-42 等；SCRIPT:42-44）；`SOLAR_CELL_DETAIL=PROHIBITED`（SCRIPT:113）；non_claims 含 `NO_SOLAR_CELL_DETAIL`（RCPT:289-294） | DONE | — |
| R2 | 每 hinge 明确轴向量+轴点；禁止双实体伪造运动（REQU §2.2 行68） | 铰链轴仅以文本自定义属性存在：`HINGE_AXIS=X@ROOT_Y=±143.15mm`（SCRIPT:115）；无任何铰链配合/轴特征——SCRIPT 设计注记明确推迟（SCRIPT:8-9 "kinematic hinge mates are a separate later step"）；面板间铰链（L1-L2/L2-L3）轴完全未定义 | PARTIAL | 太阳翼收口脚本（建议新 `F3R2_V5_NATIVE_SOLAR_ARRAY_COMPLETION_ATTACH_ONLY.py`，下称 LOOP-SOLAR-B），依赖 Loop1B 角度配合方案先行 |
| R3 | 同一物理 panel 绕真实 hinge 运动、配置间单实体（REQU §2.5 行71；PLAN §3 行52） | 单实体满足：每配置对同一组件 `SetTransformAndSolve3`（SCRIPT:245-265），无 STOWED/DEPLOYED 双实体；但运动由每配置静态变换给定，非绕铰链约束解算 | PARTIAL | LOOP-SOLAR-B（铰链配合化后重出回执） |
| R4 | 7 个太阳态 per-state 记录：panel angle / hinge state / collision state / camera visibility / arm clearance（上级指令） | 7 配置名集双侧冷验通过（RCPT:261-269, 277-285；SCRIPT:50-58, 284-286）；但 RCPT 无任何 per-config 位姿/角度行——两侧装配均 `resumed_from_existing`（RCPT:239, 249），跳过了 SCRIPT:265 的 `configurations` 记录行；hinge state 不存在（无铰链）；collision/camera/clearance 记录不存在：`05_clearance/` 为空目录，`04_configurations/` 仅有机械臂姿态登记（`V5_POSE_AUTHORITY_REGISTER.csv` 行1-10，无太阳态） | MISSING（名集 DONE / 记录 MISSING） | per-state 记录由 LOOP-SOLAR-B 生成（建议落 `04_configurations/V5_SOLAR_STATE_REGISTER.csv` + 新回执）；collision/camera/clearance 字段由 Loop2 填充 |
| R5 | 中间展开角不升格、保持 CANDIDATE（REQU §1 行40-41, 48；PLAN §5 行65） | 无任何升格记录；RCPT non_claims 完整（RCPT:289-294）；人审签发未见，符合保持要求 | DONE（合规保持） | human 签发前持续保持 |
| R6 | OD9 线束出口每侧 ≥1 个 + service loop 接口，最小弯曲半径 ≥25 mm（REQU §2.6 行72；PLAN §1 行23） | `01_native_parts/solar_array/` 仅 6 个 panel SLDPRT，无 `SOLAR_HARNESS_EXIT.SLDPRT`；Loop1D 已有 `B601_OD9_HARNESS_CLAMP` / `B601_HARNESS_SERVICE_LOOP_ENVELOPE` 但属机械臂侧（`00_authority/V5_LOOP1D_SCRIPT_CONTINUATION.json` 行40-50），非太阳翼出口 | MISSING | LOOP-SOLAR-B 建件+接口登记；弯曲半径原生 B-rep 验证入 Loop2 |
| R7 | FAIL/中间构型与权威映射一致（REQU §1 行39-46；PLAN §3 行44-50） | STOWED=0/0/0、DEPLOYED_NOMINAL=90/90/90、BOTH_FAIL=0/0/0 与权威端点一致（SCRIPT:197-206）；但 `SOLAR_LEFT_FAIL={1:deployed,2,3:stowed}`、`SOLAR_RIGHT_FAIL={1,2,3:deployed}` 与权威 `L_FAIL(0/90)`/`R_FAIL(90/0)` 不一致，且 `config_pose_map(side)` 忽略 side 参数、左右两装配位姿表完全相同（SCRIPT:197-206）——侧装配内 FAIL 构型编码的是未签发中间角候选而非权威 0° 失效语义 | PARTIAL（语义偏差，未升格故无权威违例） | LOOP-SOLAR-B 修正位姿表或显式登记为 CANDIDATE 中间角，待 human 签发 |
| R8 | 收拢接口 vs G07/G08/Mid 分开登记（REQU §2.3 行69；PLAN §1 行22 `SOLAR_STOW_PAD`） | 无 stow pad 零件；无任何收拢接触/预载登记记录；`04_configurations/` 无对应条目 | MISSING | LOOP-SOLAR-B 建 stow pad 占位 + Loop1E 顶装上下文内登记（接触语义按 REQU 保持分离） |
| R9 | 每 hinge 一个 deployed stop，角度与接触面需原生 B-rep 证据（REQU §2.4 行70；PLAN §1 行19-21） | 无 `SOLAR_DEPLOY_STOP.SLDPRT`、无 `ROOT_HINGE_ASSEMBLY`/`INTER_PANEL_HINGE` 装配件（目录清单实证）；无角度配合/限位配合；Loop1B 翼根真铰链本身未完成（`V5_LOOP1_NATIVE_BLOCKER_REPORT.md` 行12-17，`HINGE_GROUP_KINEMATIC_DRIFT`，12 份 FAIL 回执） | MISSING | Loop1B（翼根铰链/止挡 B-rep 前提）→ LOOP-SOLAR-B（止挡件+角度配合）→ Loop2 出 B-rep 接触证据 |
| R10 | 每 panel external mass placeholder，来源 ESTIMATED，不并入 L0 URDF/航天器质量真值（REQU §2.7 行73 + 上级指令） | panel 仅有文本属性 `MASS_SOURCE=EXTERNAL_MECHANICAL_ONLY`（SCRIPT:114）；`06_mass_properties/V5_EXTERNAL_MECHANICAL_MASS_SEED.csv` 16 行无任何 solar 行（行2-17）；`V5_MASS_BOUNDARY.yaml` `required_items` 16 项无 solar（行11）；`08_bom/` 两个 BOM 种子均无 SOLAR 行（全文检索无命中） | MISSING | 静态数据步：质量种子追加 6 行 ESTIMATED 占位（可即刻做，不需 SolidWorks）；Loop3 原生测量后 ESTIMATED→MEASURED_CAD 替换，全程不并入 L0 |
| R11 | arm↔solar / camera↔solar / harness↔solar 原生 B-rep 间隙复验；禁 bbox 终证；empty/Infinity/skipped fail-closed（REQU §4 行92-102 + 上级指令） | `05_clearance/` 空目录；`09_digital_thread/V5_COLLISION_ASSET_MANIFEST.csv` 仅含历史 L2_MESH `WING_L/R_DEPLOYED` STL（行57-58，源自 F3R2 冻结树），无 V5 原生太阳翼资产；AM 规则要求 `native_revalidation: REQUIRED_AFTER_V5_TOP_ASSEMBLY`（`V5_ACTION_MASK_RULES.yaml` 行71） | MISSING | Loop2（依赖 Loop1E 顶装 + Loop1D 相机/线束包络完成）；fail-closed 规则沿用 REQU §4 行102 |
| R12 | 数字线程注册（frame mapping / link-component mapping / collision manifest / BOM） | `V5_FRAME_MAPPING.yaml` `native_component_frames`（行85-93）无 SOLAR_PANEL/L_R_SOLAR_ARRAY；`V5_LINK_COMPONENT_MAPPING.csv` 仅 Loop1B 翼板件（行39, 47）；collision manifest 见 R11；BOM 见 R10 | MISSING | `F3R2_V5_DIGITAL_THREAD_SEED_GENERATOR.py` 修订增补 + Loop2 以原生资产重注册 |
| R13 | UNKNOWN/HOLD 机构参数不得填值（REQU §3 行79-88） | SCRIPT 仅写身份类属性（SCRIPT:109-116），未填 hinge_pin_diameter/spring/stop/cable_bend_radius 等任何冻结项 | DONE（合规保持） | 持续保持；LOOP-SOLAR-B 不得越界填值 |
| R14 | 非声明边界：非部署器合格/非飞行资质/不改 L0 真值（REQU §8 行141-142；PLAN §6） | RCPT non_claims：`NOT_FINAL_NATIVE_BASELINE/NOT_FLIGHT_READY/NO_SOLAR_CELL_DETAIL/NO_L0_MASS_OVERRIDE`（RCPT:289-294）；受保护资产零触碰 | DONE（合规保持） | — |
| R15 | 5 项禁止称谓不断言 | 全部证据与报告中未出现禁止称谓的达成断言 | DONE | — |
| R16 | 7 配置族存在性（REQU §1 行37-46；PLAN §3） | 双侧装配冷验配置名集 = 7（RCPT:261-269, 277-285）；但见 F-3 证据链缺口：配置内位姿变换无 PASS 回执 | PARTIAL | LOOP-SOLAR-B 全量重建验证（非 resume）出新回执 |

## 3. 额外发现（非逐条要求，但影响收口）

- F-1 设计性推迟已登记：铰链配合被 SCRIPT 明确推迟以规避 Loop1D 抑制/重建挂死（SCRIPT:8-9）。此为已声明的 DEFERRED，不是遗漏；闭合入口是 LOOP-SOLAR-B，且应复用 Loop1B 待授权的角度配合/嵌套子装配方案（`V5_LOOP1_NATIVE_BLOCKER_REPORT.md` 行17）。
- F-2 几何偏差未登记：PLAN §2 候选为每板 ~66.7×200×6 mm（行34）、面板内缘 y=±113.15 mm（行9，F3R2 实测）；as-built 为 56.67×227×6 mm（SCRIPT:42-44；RCPT:33-37）、deployed 起始 y=±143.15、stowed 折叠点 y=±116.15（SCRIPT:45-48, 131-140）。外展终点 143.15+3×56.67=313.16 mm 与 donor 实测 313.15 mm 吻合（PLAN 行10），但内段 113.15→143.15 的 30 mm 未被 panel 覆盖、单板划分与计划值不一致。双方均为 CANDIDATE_PLACEHOLDER（PLAN §2 行32），无违例，但偏差未在任何文件中登记。
- F-3 证据链缺口：5 份 FAIL 回执（13:45:45Z→13:50:18Z）均失败于 `config transform failed SOLAR_DEPLOY_STAGE1 panel 1`；两侧 SLDASM 落盘时间 13:57Z，无对应回执；PASS 回执（13:59:05Z）全部 `resumed_from_existing`，冷验仅核对配置名集（SCRIPT:284-286），不重验配置内位姿。结论：现有证据不能证明 7 配置内面板位姿变换曾被成功执行并验证——必须由 LOOP-SOLAR-B 以非 resume 全量路径出新回执闭合。
- F-4 命名不一致：REQU §1 用 `SOLAR_DEPLOYING_STAGE1/2`（行40-41），PLAN/as-built 用 `SOLAR_DEPLOY_STAGE1/2`（PLAN 行45-46；SCRIPT:51-52）。建议统一，避免登记键分裂。
- F-5 PLAN §1 零件族缺口：11 类目标件中仅 6 panel 已建；`ROOT_HINGE_ASSEMBLY.SLDASM`、`INTER_PANEL_HINGE.SLDASM×2/侧`、`SOLAR_DEPLOY_STOP.SLDPRT×2/侧`、`SOLAR_STOW_PAD.SLDPRT`、`SOLAR_HARNESS_EXIT.SLDPRT`（PLAN 行19-23）全部未建。

## 4. 拟议要求文件修订（仅提案，不改动受保护文件）

- P-1（PLAN §2）：将候选几何更新为 as-built 56.67×227×6 mm、deployed 内缘 y=±143.15、stowed 折叠点 y=±116.15，或恢复计划值并由 LOOP-SOLAR-B 重建；二选一，但须登记偏差来源。
- P-2（PLAN §1）：把零件族拆为 Phase-A（6 panel + 2 侧装配，变换式，已执行）与 Phase-B（铰链/止挡/stow pad/线束出口，LOOP-SOLAR-B），使计划与执行历史一致。
- P-3（REQU §1）：为三板翼定义 `SOLAR_LEFT_FAIL`/`SOLAR_RIGHT_FAIL` 的逐板角度语义（现权威 L_FAIL/R_FAIL 是单板 0/90 语义），并明确 `SOLAR_DEPLOY(ING)_STAGE*` 命名。
- P-4（REQU §2 新增）：定义 per-state 记录 schema（state, panel_angle_deg[3], hinge_state[3], collision_state, camera_visibility, arm_clearance_mm, evidence_ref, owner）与存放位置（建议 `04_configurations/V5_SOLAR_STATE_REGISTER.csv` + per-state 回执）。
- P-5（`V5_MASS_BOUNDARY.yaml`）：`required_items` 增补 `solar_panel_L1..R3`（或单列太阳翼 annex），来源等级 ESTIMATED 起步，Loop3 原生测量后升级 MEASURED_CAD。

## 5. 建议闭合顺序（与 Loop1B/Loop1C1/Loop1D → Loop1E → Loop2 → Loop3 依赖序一致）

1. 静态步（无需 SolidWorks，可即刻）：撰写 LOOP-SOLAR-B 脚本 + 质量种子/数字线程种子增补（R10 的 ESTIMATED 占位、R12 注册、P-4 记录 schema），静态审计 + `python -m py_compile`。
2. Loop1B 完成翼根真铰链装配（当前 `HINGE_GROUP_KINEMATIC_DRIFT` 阻塞，需先授权角度配合/嵌套子装配重写）——产出太阳翼 root hinge 轴/销/止挡的原生 B-rep 前提。
3. Loop1C1 完成夹爪棱柱配合（最新阻塞 `LIMIT_MATE_ADD_FAIL`，`V5_LOOP1C1_FAIL_20260810T151856.525979Z.json`）；Loop1D 完成 HDRM/相机/线束装配——产出 camera↔solar、harness↔solar 间隙对的另一端几何。
4. 执行 LOOP-SOLAR-B：铰链/止挡/stow pad/线束出口建件，铰链配合 + 每 hinge 一个 deployed stop 角度配合，FAIL 构型位姿表修正或 CANDIDATE 登记，per-state 记录生成，非 resume 全量验证出新回执（闭合 R2/R3/R4/R6/R7/R8/R9 几何段、F-3）。
5. Loop1E 顶装：L/R_SOLAR_ARRAY 经 root hinge 接入翼根/舱体；收拢接口 vs G07/G08/Mid 在顶装上下文登记（R8 登记段）。
6. Loop2：原生 B-rep 间隙复验 arm↔solar、camera↔solar、harness↔solar（含 REQU §4 的 HDRM residual↔solar），per-state 记录的 collision/camera/clearance 字段填充；empty/Infinity/skipped 一律 fail-closed（R4 字段段、R6 验证段、R9 证据段、R11）。
7. Loop3：质量 ESTIMATED→MEASURED_CAD 替换、BOM/工程图太阳翼行、Pack-and-Go 纳管、release evidence（R10 升级段、R12 终验）。

## 6. 非声明

本报告不是部署器合规、发射包络、展开动力学、可靠性或飞行资质结论；不改变 L0 动力学真值；不构成任何最终基线或 release 证据；未修改/删除任何既有回执或受保护基线；未附加到 SolidWorks 会话。
