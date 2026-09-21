# V5_LOOP_SOLAR_B_STATIC_READINESS — 太阳翼收口环（LOOP-SOLAR-B）静态就绪说明（2026-08-10）

性质：静态交付说明。本文件不断言任何新运行时证据；未附加到 SolidWorks 会话；未修改/删除任何既有文件（所有交付物均为新文件）。

## 1. 交付物

| 文件 | 类型 | 说明 |
|---|---|---|
| `99_tools/F3R2_V5_NATIVE_SOLAR_ARRAY_COMPLETION_ATTACH_ONLY.py` | 新脚本 | LOOP-SOLAR-B 收口脚本，attach-only，CLI 为 `audit`（默认，纯文件系统，绝不 attach）/ `execute`（显式执行旗标），风格与 Loop1D 一致 |
| `06_mass_properties/V5_EXTERNAL_MECHANICAL_MASS_SOLAR_ANNEX.csv` | 新数据 | 6 行太阳翼质量占位 annex（SOLAR_PANEL_L1..R3） |
| `09_digital_thread/V5_SOLAR_ARRAY_THREAD_ANNEX.yaml` | 新数据 | 6 板 + 2 侧装配 + 8 占位件的数字线程候选注册 annex |
| `99_tools/V5_LOOP_SOLAR_B_STATIC_READINESS_20260810.md` | 本文件 | 静态就绪说明 |

脚本复用模板 `F3R2_V5_NATIVE_SOLAR_ARRAY_BUILD.py` 的助手：会话绑定 `sbin.resolve_pid(42276)`（当前经 `V5_SESSION_REQUALIFICATION.json` 解析为 PID 87516）、内存门 `base.memory_gate()` + `mo.override_allowed()`、共享基座 `F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY`、Loop1D 的 `build_part`/`verify_part_cold`/`create_native_primitive` 原语、一次性写入回执与冷重开验证模式。execute 对任何不一致 fail-closed（回执 `V5_SOLAR_ARRAY_COMPLETION_FAIL_*.json`）。

## 2. 缺口闭合映射（对 `V5_SOLAR_ARRAY_RESIDUAL_GAPS_20260810.md`）

| 缺口 | 闭合方式 | 状态 |
|---|---|---|
| F-3（证据链缺口）/ R16 | execute 走 **非 resume** 全量路径：打开每侧装配 → 逐 7 配置 ShowConfiguration2 + EditRebuild3 → 对每板重放期望位姿表（`SetTransformAndSolve3`）→ ForceRebuild3 后逐板读回 `Transform2.ArrayData`，16 元素绝对容差 2e-7 m 比对 → 保存后**只读冷重开**再验 7×3 位姿。as-found 与期望的偏差逐行记录（`as_found_within_tolerance` / `pose_corrected_by_this_run`），绝不静默。出新回执证明配置内位姿被真实执行 | 脚本就绪，待 execute |
| R4（per-state 记录） | execute 末段一次性写 `04_configurations/V5_SOLAR_STATE_REGISTER.csv`，schema 为 `state,panel_angle_deg_L[3],panel_angle_deg_R[3],hinge_state,collision_state,camera_visibility,arm_clearance_mm,evidence_ref,owner`；角度由验证后位姿表填充（0/90 语义）；`hinge_state=NO_KINEMATIC_MATE_YET`；`collision_state/camera_visibility/arm_clearance_mm=PENDING_LOOP2`（不编造值） | 脚本就绪，待 execute |
| R7（FAIL 构型语义） | as-built FAIL 位姿**保持不变**；回执 `fail_config_registration` 显式登记为 CANDIDATE 中间角语义，并给出到权威单板 L_FAIL(0/90)/R_FAIL(90/0) 的映射注记（提案 P-3）。线程 annex 同步登记 | 脚本就绪，待 execute |
| R6/R8/R9（占位件） | 新建 8 个占位级原生件（`01_native_parts/solar_array/`）：`SOLAR_HARNESS_EXIT_{L,R}.SLDPRT`（OD9 出口占位，圆柱 r4.5×20 mm）、`SOLAR_STOW_PAD_{L,R}.SLDPRT`（收拢接触占位，30×30×4 mm box）、`SOLAR_DEPLOY_STOP_{L,R}_H{1,2}.SLDPRT`（每铰链一个展开止挡占位，12×10×6 mm box）。仅身份类自定义属性，不填 REQU §3 任何 UNKNOWN/HOLD 参数；单实体、无太阳电池片；以固定（非配置相关）参考位姿插入侧装配，逐配置验证 fixed+resolved | 脚本就绪，待 execute |
| R2（铰链轴语义） | 沿用构建脚本 `HINGE_AXIS` 文本约定并扩展到板间铰链：每板新增 `HINGE_AXIS_INBOARD`（root X@y=±143.15 z=0；板2/3 为 y=±199.82 / ±256.49）与 `HINGE_AXIS_OUTBOARD`（板3 为 NONE_TERMINAL_PANEL），另加 `HINGE_SEMANTICS=PARTIAL_TEXT_ONLY_PENDING_LOOP1B_HINGE_MATE_PATTERN` 与 `HINGE_MATE_STATE=NO_KINEMATIC_MATE_YET`；轴向表录入回执 | 脚本就绪，待 execute |
| R10（质量占位） | 质量 annex 6 行，`source_class=ESTIMATED`、`mass_g` 留空、`basis=PENDING_NATIVE_ESTIMATE`、`status=PENDING`（镜像既有种子 `springs` 行的未知约定），note 声明 external-mechanical-only、不并入 L0 URDF | 已静态完成 |
| R12（数字线程注册） | 线程 annex 注册 16 个候选条目（frame-mapping / link-component / collision-manifest / BOM 四链），全部标 CANDIDATE + PENDING_LOOP2_NATIVE_REVALIDATION，hash 待回执绑定 | 已静态完成 |
| R3 / R9 证据段 / R11 | 仍依赖 Loop1B 铰链配合模式、Loop1E 顶装与 Loop2 原生 B-rep 间隙复验；不在本环范围 | 保持开放 |

重要单位注记：SolidWorks API 变换以**米**计；脚本将构建脚本的毫米位姿几何除以 1000 后应用，as-found 若为毫米直填会被容差比对捕获、记录并显式修正（`pose_corrected_by_this_run`）。

## 3. 清单影响核查（manifest-impact finding）

- `06_mass_properties/V5_EXTERNAL_MECHANICAL_MASS_SEED.csv`：**未**在任何 `14_release/*MANIFEST_SHA256.txt` 或 `00_authority/*.json|yaml` 中 hash 注册（grep 实证）。
- `09_digital_thread/*`（V5_FRAME_MAPPING.yaml、V5_LINK_COMPONENT_MAPPING.csv、V5_COLLISION_ASSET_MANIFEST.csv 等）：同样**未**注册。
- 但按写一次纪律，二者均**未做原地修改**——只新增 annex 文件。`06_mass_properties/V5_MASS_BOUNDARY.yaml` 已在 `V5_AUTHORITY_SEED_MANIFEST_SHA256.txt` 注册，保持不动（P-5 提案仅登记于差距报告）。
- 太阳翼既有资产（6 板 + 2 侧装配）未在任何 release manifest 注册；LOOP-SOLAR-B execute 会附加修改这些文件（面板加身份属性、装配插入占位件+位姿校正），前后 sha256 均录入新回执，旧回执不触碰。

## 4. 执行命令（编排器）

```bash
cd "F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
python 99_tools/F3R2_V5_NATIVE_SOLAR_ARRAY_COMPLETION_ATTACH_ONLY.py execute
```

前置状态：**Loop1B + Loop1D 回执落定之后、Loop1E 顶装之前**（脚本静态审计强制 `03_top_assembly/` 为空、`04_configurations/V5_SOLAR_STATE_REGISTER.csv` 不存在、无既有 completion 回执，否则 HOLD）。会话须为 `sbin.resolve_pid(42276)` 解析到的空文档会话（当前 PID 87516，须先等其它环释放）。

## 5. 静态验证结果（本机已执行）

- `python -m py_compile 99_tools/F3R2_V5_NATIVE_SOLAR_ARRAY_COMPLETION_ATTACH_ONLY.py` → 通过。
- `python 99_tools/F3R2_V5_NATIVE_SOLAR_ARRAY_COMPLETION_ATTACH_ONLY.py audit`（及无参默认模式）→ `verdict=V5_SOLAR_B_STATIC_AUDIT_PASS`，`execution_authorized=true`，`attach_attempted=false`，`win32com_imported_by_this_script=false`（由 `sys.modules` 实测，非硬编码）。
- `09_digital_thread/V5_SOLAR_ARRAY_THREAD_ANNEX.yaml` 经 `yaml.safe_load` 解析通过（16 link 候选行 + 6 collision 候选行）；质量 annex 表头与既有种子逐列一致。

## 6. 偏差说明（对任务书）

1. **占位件命名加侧/铰链后缀**：任务书字面给出 `SOLAR_HARNESS_EXIT.SLDPRT`（每侧）等单名；同一目录下同侧两件同名不可能共存，故采用 `SOLAR_HARNESS_EXIT_{L,R}`、`SOLAR_STOW_PAD_{L,R}`、`SOLAR_DEPLOY_STOP_{L,R}_H{1,2}`（每侧每铰链一件，共 4 止挡，对应 PLAN §1 的 ×2/侧；root 铰链止挡属 Loop1B 翼根域，不在此建）。
2. **R4 登记表由 execute 生成而非静态预写**：schema 要求"从已验证位姿表"填充角度，验证只能发生在 execute；静态步写表会编造证据。登记表现在不存在，audit 将其列为写一次目标。
3. **位姿表米制化**：构建脚本 `panel_pose` 的平移量为毫米直填；本脚本按 SW API 米制约定 ÷1000 应用，并记录/修正 as-found 偏差（非静默）。这是对 F-3 的实质修复，不是语义变更（deployed/stowed 分配逐配置保持 as-built）。
4. **R7 只登记不改位姿**：FAIL 构型未改为权威 0/90 单板语义——权威映射属 human 签发事项（P-3），脚本仅登记 CANDIDATE 中间角语义。

## 7. 残余风险

- **as-built 位姿可能为单位错误**（毫米直填进米制变换）：execute 首轮会大量报 `pose_corrected_by_this_run=true` 并修正；这是预期路径，但意味着既有装配文件 hash 会变，旧 PASS 回执与文件不再对应（旧回执保持写一次，不失效于历史语义）。
- **铰链语义仍为 PARTIAL**：文本属性不是运动学约束；Loop1B 铰链配合模式落定后需重出回执（R2/R3 才能升 DONE）。
- **止挡/收拢/线束出口仅为占位几何**：无接触面 B-rep 证据（Loop2）、无角度值（REQU §3 保持 UNKNOWN/HOLD）。
- **R4 的 collision/camera/clearance 字段** 在 Loop2 前保持 PENDING_LOOP2；任何提前填值都违反 fail-closed。
- **execute 中途失败**会留下部分占位件：重跑时存在件走冷验 resume 路径，装配仍走非 resume 全量验证，登记表与回执保持写一次，语义安全。

## 8. 非声明

本环不断言 FINAL_NATIVE_CAD_BASELINE / MANUFACTURING_RELEASED_BASELINE / FLIGHT_READY / LAUNCH_QUALIFIED / FULLY_AUTHORIZED_SERVICE_AND_GRASP_TRAJECTORY 中任何一项；非声明集：`NOT_FINAL_NATIVE_BASELINE`、`NOT_FLIGHT_READY`、`NO_SOLAR_CELL_DETAIL`、`NO_L0_MASS_OVERRIDE`、`CANDIDATE_ANGLES_NOT_AUTHORITATIVE`。
