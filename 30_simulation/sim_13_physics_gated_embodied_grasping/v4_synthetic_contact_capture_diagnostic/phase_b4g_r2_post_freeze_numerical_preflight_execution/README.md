# Phase B4G-R2：数值预检执行工具源码冻结

本目录实现 R2 数值预检所需的**源码级工具与执行阻断边界**，但不执行 78 个 case，不导入旧数值模块，不运行 physics、trajectory 或 campaign。这里能够得到的最高裁决仅为：

`PASS_PHASE_B4G_R2_EXECUTION_TOOLING_SOURCE_FREEZE_ONLY`

它不等于数值预检 PASS、科学 Gate PASS、current/NC19/Owner/production/release/next-stage PASS。

## 当前硬边界

- R2 机器矩阵仍为 78 个唯一 case：60 个 `FRESH`、18 个 `COMMON_PROP`；本包的 `trajectory_count` 固定为 0。
- 矩阵 canonical SHA256 固定为 `D7B23B92DA46A6F9E96CF856914C7D5AECAD26240141C7F2B637A2AF119B7BEB`，blocked case-ID 顺序 SHA256 固定为 `259EB3A99C0C0A45A6C80AEB979E2F15F3023804128517192C24D1B8A8F20EC7`。
- Common donor 只读绑定 slot 052：raw SHA256 `5DF0C19A71180E1BD91816235AAD50108613C2BC0F99F950018D786119CF9D4F`；payload SHA256 `DA3E10D7D30DFD9BABFB71BF055D62A1BD06CF8DE3023E463A649FF92A952D15`；派生 state-group SHA256 `396A903DA584765FDA03B867F2F3F27B910CED9383D34BC5064A01B33D4F6444`。
- 新包 JSON 禁止 duplicate key、`null`、NaN 和 Infinity。唯一例外是读取已经由 raw bytes/SHA256 锁定的历史 donor 外层 JSON；其历史 `null` 不进入抽取的 payload、新合同或新证据。
- 时间必须以 `s` 或 `ms` 明示；功率为 `W`、功为 `J`。G04 的 `Q·eta` 是功率，积分后才是 actuator work，禁止把功率、功和动能差混为同一量。
- 直接 Owner authority source 当前不存在，成功授权路径在本版本中没有实现。状态固定为 `NOT_VALIDATED_NO_DIRECT_OWNER_SOURCE`；任何 future execution 都要求新版本、新 Owner source 和新 source-freeze。

## 源码边界

`r2_preflight/` 提供严格 JSON、78-case 展开与顺序、typed donor rehydration/roundtrip、通道距离、G04/G06 与 G12 评估、授权前置阻断和 46 个 source-only mutation 控制。旧 `b4g_solver`、`b4_solver`、campaign、forced-retraction 或 full-floating 模块只作为外部 hash binding 存在，不得在 source-freeze、validator、audit 或 pytest 中导入。

递归护栏禁止在本目录留下 `.npz/.csv/.urdf/.step/.stp/.pyc/.tmp`，禁止 `__pycache__/.pytest_cache/raw/raw_cases`，并禁止新增文件名含 `solver`。运行 Python 时一律使用 `-B`，pytest 使用 `-p no:cacheprovider`。

## 46 个 source-only negative controls

Gate 只接受：

- exact 46 个注册 ID，顺序与 `PHASE_B4G_R2_SOURCE_ONLY_NEGATIVE_CONTROL_EVIDENCE_CONTRACT_V1.json` 一致；
- `implemented_count=46`、`source_only_executed_count=46`、`killed_count=46`；
- 每项 mutation 均由 `build_negative_control_evidence` 实际调用生产检查接口并被拒绝，且 `r2_runtime_trajectory_evaluated=false`；
- NC21/NC22 只可报告 `STRUCTURAL_SOURCE_SIGNATURE_KILLED`；其余项使用 source-only mutation 两种状态之一；
- 每项都绑定非空 witness、`fixture_class` 和九个生产实现文件的 canonical implementation SHA256；evidence 还绑定 source-manifest inventory SHA256；
- `r2_execution_negative_controls_executed=false`、`r2_numerical_preflight_executed=false`、`trajectory_count=0`。

证据固定为 `evidence/SIM13_V4B4G_R2_SOURCE_ONLY_NEGATIVE_CONTROLS_V1.json`。freeze 在 manifest 生成后亲自执行 builder 并覆盖生成该证据；validator 随后用同一冻结源码和 donor 再跑 46 项，要求完整 evidence canonical 对象逐字段相同。独立 audit 不导入生产包，但会独立复核 implementation 文件、manifest、witness 与 validator replay receipt 的 hash 链。缺失、ID 不精确、字段不完整、replay 不一致或任何 mutation 未杀死时，只能生成 `PARTIAL.../HOLD`，不得宣称 46/46 PASS。

## 自排除哈希链

生成顺序固定为：

1. `evidence/SIM13_V4B4G_R2_EXECUTION_SOURCE_MANIFEST_V1.json`
2. `evidence/SIM13_V4B4G_R2_SOURCE_ONLY_NEGATIVE_CONTROLS_V1.json`
3. `evidence/SIM13_V4B4G_R2_EXECUTION_SOURCE_VALIDATION_V1.json`
4. `evidence/SIM13_V4B4G_R2_EXECUTION_SOURCE_INDEPENDENT_AUDIT_V1.json`
5. `results/SIM13_V4B4G_R2_EXECUTION_TOOLING_SOURCE_FREEZE_GATE_V1.json`
6. `results/SIM13_V4B4G_R2_EXECUTION_SOURCE_FREEZE_TERMINAL_V1.json`

source manifest 只记录根级源码/README/pytest 配置、`r2_preflight/`、`contracts/` 和 `tests/`；整个 `evidence/`、`results/` 均自排除。terminal 最后生成，自身不进入 manifest，并且只 hash-bind Gate，因此哈希图无环。

在 audit 与 Gate 之间、Gate 与 terminal 之间、以及 terminal 写入后，freeze 会再次重算本地 source inventory、NC evidence、已绑定 evidence records、source validator 与 independent audit；任一 post-audit 漂移都会停止发布，不留下可用 terminal。

validator 可使用本包的 source-only API，但不导入 audit 或 tests。independent audit 只用 Python 标准库，独立重建 78-case 矩阵、blocked 顺序、donor group、raw inventory 和 canonical hashes；它不导入 validator、tests 或 `r2_preflight`。

在源码与 NC 证据均稳定后执行：

```powershell
python -B freeze_phase_b4g_r2_execution_sources.py
python -B validate_phase_b4g_r2_execution_source_freeze.py
python -B independent_audit_phase_b4g_r2_execution_source_freeze.py
python -B -m pytest -q -p no:cacheprovider
python -B verify_phase_b4g_r2_read_only_replay.py
```

只有第一条 freeze 命令会生成六件冻结链。standalone validator 与 audit 默认均为 `READ_ONLY_RECEIPT_VERIFY`：它们重新计算结果并与既有 receipt 逐字段比较，绝不覆盖文件；只有完整拼写且显式传入 `--write-receipt` 才允许单独生成 receipt（CLI 禁止参数缩写），而正常发布由 freeze 内部受控调用写入路径。pytest 同样使用 `-B` 和禁用 cache provider。最后一条回归命令会在 validator、audit、pytest 前后对本包全部规则文件、源码、合同、evidence 与 results 做 bytes/SHA256 快照，要求零新增、零删除、零变化；即使任一子命令失败也必须采集 after snapshot/delta，并在前后分别重验 Gate 的四个 evidence bytes/SHA256 与 terminal→Gate bytes/SHA256 链。

这些命令只进行源码/合同/静态 mutation 证据核验。freeze 在 NC 证据缺失但其余结构正确时以退出码 2 明示 partial；validator/audit 对缺失或漂移的 receipt 返回非零。任何命令的 PASS 都不授权数值执行。

## 必须保持为 false/zero

Gate 与 terminal 均机器记录：R2 numerical preflight、R2 execution-level negative controls、full campaign、scientific/current/formal NC19、formal Sim13 NC15/16/18/19/20、memory/Owner override、production、release、next stage 全部为 false；physics/solver/campaign invocation count 与 trajectory count 全部为 0。
