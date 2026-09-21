# CAD Baseline Decision — SER-MECH-V3.0

## 裁决摘要

| 项目 | 裁决 |
|---|---|
| 架构重置 | `MECHANICAL_ARCHITECTURE_RESET_COMPLETE` |
| V3.0 未来根目录 | `20_engineering/cad/Space_Embodied_Robot_CAD_V3_0/` |
| V3.0 未来顶装文件名 | `Assembly/Space_Embodied_Service_Spacecraft_V3_0.SLDASM` |
| V3.0 seed | `PENDING_HUMAN_RULING` |
| 原生 CAD authoring | `V3_CAD_AUTHORING_NOT_AUTHORIZED` |
| V2.3 Stage 2 | `NATIVE_MECH_REAL_01_STAGE2_HOLD` |
| 删除既有资产 | `NOT_AUTHORIZED` |

这份文件给出未来顶装的名称、边界和候选来源，但不自动选择母体，也不授予任何 CAD 写入权。

## 1. 现场基线事实

| 版本 | 顶层 SHA-256 | 现场证据 | 本次处置 |
|---|---|---|---|
| V2.0 | `DF19707C…616C7` | 57/57 manifest 匹配；B3 为机器完成但人工待审 | `FREEZE_HISTORICAL` |
| V2.1 | `32868FCE…03CFB` | 60/60 匹配；11 项有意回引 V2.0；`B4_1_ACCEPTANCE_HOLD` | `FREEZE_HISTORICAL` |
| V2.2 | `3B55EDB8…0CFB9` | L1 PASS，L2 PARTIAL，L3 未开始，L4 未授权；无全树终封 manifest | `REFERENCE_DONOR_ONLY` |
| V2.2_NATIVE | `30C09B50…DEF7A` | 108/108 冻结记录匹配；Phase 1 仍 `PENDING_HUMAN_REVIEW` | `READ_ONLY_NATIVE_SOURCE_BASELINE` |
| V2.3 | `76A3B289…1853` | 56/56 顶层引用已隔离；Stage 2 失败件未插入顶装 | `ISOLATED_SEED_CANDIDATE_ONLY` |

所有这些 SolidWorks 文件在 Windows 上当前均可写；“冻结”是治理约束，不是文件属性保证。

## 2. 未来顶装

未来唯一 active top 拟定为：

`20_engineering/cad/Space_Embodied_Robot_CAD_V3_0/Assembly/Space_Embodied_Service_Spacecraft_V3_0.SLDASM`

该顶装必须：

- 位于新的 V3.0 根目录；
- 所有生产依赖都解析到 V3.0 根内；
- 不直接引用 V2.0/V2.1/V2.2/V2.2_NATIVE/V2.3 原生文件；
- 不引用任何 Stage 2 quick/temp/test/双代理/空三配置装配；
- 对外部 vendor STEP、STL 和 URDF 采用登记的 reference/authority 关系，而不是隐式装入；
- 每个配置冷重开后保持组件数、抑制状态、引用归属和质量隔离；
- 生成全树 SHA-256 manifest、dependency ledger 和 deviation manifest。

## 3. Seed 候选，不自动选择

### 候选 A：复制当前 V2.3 隔离顶装的受控基础区

来源：

`Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION/Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM`

优点：

- 已证明顶层 56/56 组件引用全部归属 V2.3；
- 65 个基础原生文件中 64 个与 V2.2_NATIVE 逐字节相同；
- 唯一变化是有证据支持的 `Removable_Panels` 本地引用修复；
- Stage 2 失败件尚未插入该顶装。

风险：

- 同一根目录内存在失败的 Stage 2 双代理、体积质量体、空三配置装配、quick/temp/test 和 6 字节残留锁；
- 现有目录没有覆盖 Stage 2 新件的终封全树 manifest；
- Stage 2 machine verdict 与最终执行报告相互冲突；
- 后续审计必须证明只复制受控基础区，未夹带实验资产。

### 候选 B：从 V2.2_NATIVE 干净重复制，并重放唯一已证明的引用修复

来源：

`Space_Embodied_Robot_CAD_V2_2_NATIVE/Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM`

优点：

- 108/108 冻结记录现场匹配；
- 不带 V2.3 Stage 2 的失败执行历史；
- 最适合“新根、全量重封、逐对象迁移”的治理目标。

风险：

- 简单文件复制会使 `Removable_Panels` 解析回源目录；
- 必须重放并重新验证 V2.3 已证明的本地引用修复；
- Phase 0 曾删除源树中 56 个未列入冻结 manifest 的 `~$` 文件；虽然 108 个受控文件未变，该治理偏差仍需人工接受；
- 多一次受控迁移步骤，增加执行和复核工作量。

### 建议，但不是选择

面向“全面接管并建立干净 V3 数字线程”，治理上优先建议候选 B；面向“最小化已验证几何的再次变换”，技术上优先建议候选 A。

最终状态保持：

`V3_SEED = PENDING_HUMAN_RULING`

只有人工 Gate 明确给出 A 或 B，才允许创建 V3.0 根目录。

## 4. 各版本处置

### 保留并冻结

- V2.0：历史闭环和早期外形/配置证据；
- V2.1：参考落地与 `B4_1_ACCEPTANCE_HOLD` 证据；
- V2.2：功能几何和 donor 支线；
- V2.2_NATIVE：只读原生几何 source baseline；
- V2.3：引用隔离证据与失败集成证据；
- 现有两张 NATIVE01 图：仅 `NOT FOR MANUFACTURE` 评审证据；
- B601 accepted URDF、STL、vendor STEP 派生、第三方通知；
- 所有负结果、UNKNOWN/HOLD 和冲突记录。

### V3 中重建

- 唯一 Master Skeleton 与顶层装配；
- 四根可独立追踪的纵梁实例、主结构连接与设备硬点；
- B601 mount 孔系、定位、紧固、载荷连接和收拢支承；
- B601 三表征及质量互斥；
- 左右翼板与完整根部机构；
- 任务相机、F/T、柔顺/锁紧、工具/TCP、计算托盘和服务线束；
- 全套工程图、BOM、配置表、fastener register 和 ICD。

### 仅作参考

- V2.2 donor 中的末端执行器、GNC、推进、通信和热控显示包络；
- `100_Mechanical_Continuation` STEP；
- `110_Layout_and_Deployment_01` staging；
- `120_B601_Geometry_and_PoseMap_02` LOD2/pose-map STEP；
- `130_B601_Vendor_CAD_Direct_Integration_03` vendor geometry；
- `80_third_party` 中的公开 CAD 原则与接口参考。

所有第三方对象保持：

`NO_DIRECT_SCALE / NO_AUTOMATIC_IMPORT`

## 5. V2.3 Stage 2 的控制裁决

控制入口：

`design/NATIVE_MECH_REAL_01_STAGE2_EXECUTION_REPORT.md`

SHA-256：

`FDBD4B5771C5609C129ED8D996E31DA8530DDE5C35B2BBFC3ADE05A17EC1E80A`

控制状态：

`NATIVE_MECH_REAL_01_STAGE2_HOLD`

不能作为控制入口：

`evidence/stage2_b601_three_rep/stage2_machine_verdict.json`

原因：

- 当前文件仍把 kinematic proxy 和 mass surrogate 写为 PASS；
- summary 的 `gates_pass=4` 与实际 PASS 列表数量不一致；
- mass surrogate 采用 500 kg/m³ 默认密度和体积反算；
- CoM/MOI 只写入字符串，未形成原生惯量实现；
- 三表征三个配置均为 0 resolved / 0 suppressed；
- HIFI 空、顶层未插入、未完成冷重开。

处置：

- `B601_KINEMATIC_PROXY`
- `B601_MASS_SURROGATE`
- `B601_THREE_REPRESENTATIONS.SLDASM`
- `QUICK_TEST.SLDASM`
- `TEMP_THREE_REP.SLDASM`
- `TEST_LATE.SLDASM`
- `~$QUICK_TEST.SLDASM`

全部标为：

`QUARANTINE_CANDIDATE_NOT_DELETE / NEVER_INHERIT_INTO_V3`

本轮不移动、不删除它们。

## 6. Codex 与 Claude 资产边界

- V2.2_NATIVE 是 Claude Code 创建的原生几何源，不因此获得物理/质量/制造 authority；
- Codex 的 `v22_mechanical_continuation.step` 是 `STEP_REFERENCE`，不是母 CAD；
- V2.3 Stage 2 出现的 Codex quick/test 原生文件属于执行偏差和失败证据，不是可接受 Codex 原生资产；
- 当前没有任何已验收的“Codex 原生 SolidWorks V3 资产”；
- `phase0_record.json` 中的 `SOLIDWORKS_SOLE_WRITER=CLAUDE_CODE` 仍是现有 writer 记录。

用户要求 Codex 全面接管，足以授权本次架构重置，但不足以在不改写 writer 记录的情况下自动授权原生 CAD 写入。必须新增人工裁决：

`MECH_V3_WRITER_AUTHORITY = CODEX | CLAUDE_CODE | HUMAN_INTERACTIVE | OTHER`

并同时给出唯一 owner、工具版本、日志目录、恢复规则和失败停止条件。

## 7. V3-G0 必须人工签发的内容

1. Seed 选择：候选 A 或候选 B。
2. 唯一原生 CAD writer 与 supersession 记录。
3. V3 根目录、顶装名称、零件编号规则和配置清单。
4. V2.3 Stage 2 失败资产的隔离/归档/删除策略；删除仍需单独授权。
5. `T_SM=185.25 mm` 动力学/PDR 轨与 `MOUNT_FACE_X=198 mm` native display 轨的命名与使用规则。
6. 25° clock、`T_MA0` 和 `M_clocked` 的唯一 frame 关系。
7. B601 visual、kinematic、mass 三种 representation 的用途、互斥和 BOM/mass 抑制规则。
8. B601/mesh/vendor STEP 的内部使用与对外展示/分发边界。
9. `STOW_Z_LIMIT=UNKNOWN`、`238.3>226.3`、`302.3>226.3` 是否作为进入 V3 的开放 blocker。
10. 是否接受 Phase 0 对 56 个源树锁文件的治理偏差。

未取得这些签发前，允许继续完善文档与人工裁决模板，不允许创建或修改原生 CAD。
