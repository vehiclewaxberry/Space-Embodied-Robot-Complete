# R17 BOM 交接来源时序生产修复 — PATCH_NOTES

run：`01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r17_export_chain_20260919/`
状态：`PRODUCTION_FIX_COMPLETE_WITH_NOT_RUNS`；R17 票**不关闭**（`production_fix_applied` 待 owner/审阅回写，本包不改写 issues.json）；严格验证器接入与 R14 属工作包 B，不在本包。

## 原票与现状实读

- R17："BOM交接来源未校验且重建顺序可能保留旧质量分配"，acceptance："Reject stale/missing required input hashes and instance/owner mismatch before writing output; export BOM after dynamics; keep initial unallocated values null."
- 原 `export_parts_and_bom.py`：build → 读 `results/service_instances.json` → 若 `DYNAMICS_HANDOFF.json` 存在则**直接消费（不校验其来源哈希/实例完整性）**→ 写 BOM/INTERFACES；`--bom-only` 顶层仍 `from spacecraft_model import build`；README 复现顺序为先 BOM 后 HANDOFF。
- `dynamics_handoff.py`（HANDOFF 生成器）：读三态回执+URDF+WP01 FK，自带回执-源码绑定与计算期不变性检查，本包未改。
- `finalize_delivery.py`：交付回执绑定器（终检 STEP/收据哈希），非导出链，本包未改。
- `integrate_checks.py`：只读集成检查，本包未改。

## 既成事实登记（不改写原票字段）

- 原票 `current_BOM_is_proven_stale=false` 记录于 2026-09-06 审计（当时 11 项交接输入哈希匹配）。
- 本 run 改前审计（`inputs/INPUT_MANIFEST.json::pre_fix_staleness_audit`）：E1–E4 改件后三态回执与地面视图回执均未同步重建，`source_sha256` 与 `design_parameters.json` 依赖哈希全部失配——**现存 HANDOFF/BOM 相对现行 CAD 已失配**。这正是 R17 所要防止的混配在真实链路上的实例化，也构成修复的必要性实证。此事实不回写 issues.json。

## 修复内容（最小修改，仅 `export_parts_and_bom.py` + README 顺序说明）

**强制顺序链**：有效输入哈希校验 → 构建/回执 → `dynamics_handoff.py` 子进程生成 HANDOFF → HANDOFF 逐项校验 → 最后写 BOM →（独立逐项核对由校验器内嵌完成）。BOM 消费 HANDOFF 不回写几何，HANDOFF 经子进程隔离生成，避免循环哈希。

1. **HANDOFF 来源校验**（`validate_handoff_provenance`）：schema、必需输入哈希集（三态回执+地面视图+URDF+WP01 kinematics+spacecraft_model/design_parameters/kinematics/wing_kinematics/dynamics_handoff 共 9–10 项）逐项重算比对；回执-源码绑定复核；计算期不变性标志。
2. **BOM 回执逐项校验**（`validate_receipt_for_bom`）：状态/视图（仅 complete）、回执-源码与依赖哈希、角色白名单、GSE/TEST_DUMMY 混入、实例 id 唯一、正质量 owner 非空且全表唯一、UNKNOWN 零填（mass=0 且 source UNKNOWN/None 拒绝）、标准件与父总成双计（紧固件在含总成预算行的装配内计正质量即拒绝；翼叶逐件预算与释放/线束总成预算合法共存不误判——修复史见下）。
3. **HANDOFF↔回执交叉核对**（`cross_validate`）：状态集合恰为 parking/released/service；姿态/根变换逐态对拍（配置混用检出）；实例集合恒等；逐 id 的 mass_owner/product_role/representation_role 一致；逐 owner 质量值一致（容差 1e-12，同总质量错源检出）；来源分解对账（1e-9）；角色计数；跨状态 owner 集合/质量独立复算。
4. **fail-closed 写出**：任一违规→拒绝写出，并将 BOM.csv/INTERFACES.csv 恢复为改前字节（不留下半更新交付物）；exit code 2 + 违规清单 JSON。
5. **未分配保持 null**：`allocated_dynamics_mass_kg` 用 `.get()`，未分配=None→CSV 空单元格，绝不写 0；臂 link 的 URDF 数字分配（SOURCE_DIGITAL）不算未分配泄漏（修复史 F1）。
6. **--bom-only 拆依赖**：顶层仅 stdlib（csv/json/sys/hashlib/subprocess/pathlib），CAD 导入懒加载于完整模式分支内；`--bom-only` 永不触达。

## 修复迭代史（FAIL 不覆盖）

- **F0 双计判据过宽（首版）**：`BUDGET_DOUBLE_COUNT_SAME_ASSEMBLY` 把翼叶逐件预算误判为与翼释放/线束总成预算双计（6 叶假阳性）。按票面收窄为仅标准件/紧固件双计；复跑真实链拒绝 43 项违规全部为过期间题、零误判（`evidence/r17_pre_fix_real_rejection.json` 为首版 61 项→收窄后 43 项的复跑输出）。
- **F1 臂 link 误判（首次完整链重跑被拒）**：臂 link 回执 `mass_kg=None`，其 HANDOFF 分配来自 accepted URDF（SOURCE_DIGITAL），被"未分配 owner 进入交接值"误判。修正为排除 `arm_link` 行；八类负控复跑仍 8/8 检出（`evidence/r17_negative_controls.json` 为修正后版本）。被拒运行的 BOM/INTERFACES 已按 fail-closed 恢复改前字节，未留下半更新交付物。

## 机器裁决（evidence/ 与 logs/，全部带 sha256 边车）

- **改前真实链拒绝**（s02）：`--bom-only` 对失配链 exit 2，43 项违规（HANDOFF 输入哈希失配 3、回执-源码失配 3、回执依赖失配等），BOM/INTERFACES 字节恢复一致。
- **八类负控 8/8 检出**（s03，合成夹具+正控零违规）：NC1 旧交接配新 CAD→HANDOFF_INPUT_HASH_MISMATCH；NC2 同总质量错源→OWNER_VALUE_MISMATCH+MASS_BY_SOURCE_MISMATCH；NC3 配置混用→STATE_CONFIG_MISMATCH；NC4 exploded→RECEIPT_VIEW_NOT_COMPLETE+HANDOFF_STATE_SET_MISMATCH；NC5 缺/重复 owner→MISSING/DUPLICATE_MASS_OWNER；NC6 UNKNOWN 零填→UNKNOWN_ZERO_FILL×2 路径；NC7 GSE 混入→GSE_IN_ONBOARD_RECEIPT；NC8 标准件双计→STANDARD_PART_PARENT_DOUBLE_COUNT。
- **完整链重跑 PASS**（s04，`logs/s04_full_export_log.json`）：497 实例（487 结构+10 臂），214 分配正质量 / 283 未分配 null；HANDOFF 自测（平行轴/平移不变/WP01 FK 对拍 2.27e-13）全过。
- **--bom-only 验证**（s06）：(a) 模块导入后 sys.modules 零 CAD 模块（spacecraft_model/root_structure/cadgen/build123d/OCP/kinematics/wing_kinematics 均无）；(b) 功能 PASS 且 BOM/INTERFACES 与完整模式字节一致；(c) 缺失 HANDOFF 拒绝 exit 2 且交付物字节不变。
- **烟测 487 PASS**（s07）：结构态 487=483+4（E4 夹套 4 在位），回执哈希 `d220c70274…` 与 E4 烟测逐位一致；全态 497。
- **交付物哈希对照**（s05，`evidence/r17_deliverables_hash_compare.json`）：9 项交付物改前/改后逐行登记（改前备份在 `inputs/` 同名快照）。

## 交付物改动登记

| 交付物 | 改动 |
|---|---|
| `export_parts_and_bom.py` | 重写为强制顺序+校验器（改前快照 `inputs/export_parts_and_bom.py`） |
| `README.md` | 复现顺序说明：BOM 移至 HANDOFF 之后（脚本内部强制），去掉单独先跑 dynamics_handoff 的旧行 |
| `BOM.csv` / `INTERFACES.csv` | 重生成（497 实例、15 列含分配列） |
| `results/DYNAMICS_HANDOFF.json` / `DYNAMICS_SUMMARY_ZH.md` | 重生成（新回执输入，来源哈希全绑现行） |
| `results/{parking,released,service,parking_ground}_instances.json` | 重建（497/497/497/502） |
| `results/service_structure_instances.json` | 完整模式 build 副作用刷新，字节与 E4 后版本逐位一致 |
| `parts/*.step` | 完整模式 write_parts 副作用重导出（原有生产行为，非本包新增语义） |

## NOT_RUN（显式登记）

1. 独立第三方复验（留审阅者；构建者不自验）。
2. 严格验证器真实接入与 R14 参数扰动——工作包 B，不在本包。
3. `finalize_delivery.py` 交付回执未重跑（其绑定的 inspect/refs/快照链不在本包授权范围；重跑属交付绑定工作包）。
4. `geometry_checks.py`/`integrate_checks.py` 未重跑（本包为导出链溯源修复；两脚本只读消费回执，语义未变）。
5. parking_cutaway/parking_exploded 展示视图回执仍为旧源码生成（HANDOFF/BOM 不消费展示视图；刷新属 gen/inspect 链）。
6. R17 票状态字段（`production_fix_applied` 等）不回写——本包不改 issues.json/CURRENT/gate。
7. 实物/硬件验证不适用（软件溯源修复）。

## 边界遵守

不改写 gate/issues.json/CURRENT 指针；WP02 文件只读；未执行 git 提交；UNKNOWN 零填禁止（未分配质量保持 null，CSV 空单元格）；FAIL 不覆盖（两次修复迭代均留痕于本文件与证据）；布尔未涉及（无 CAD 几何改动）。
