# 340.5 mm 12U 主结构候选包 V1

本目录是 PRB-17 的低内存、source-only 闭环包。它继承既有 B601、M3R、M6 载荷桥和 Solar R2 边界，不重画已冻结产品；新增的是可复核的 12U 主结构构件树与 `170.25→185.25 mm` 前端承力过渡。

## 当前机器结论

- 源模型 Gate：当且仅当本包无 CAD/授权/生成尝试证据时，可为 `16/16 PASS_SOURCE_ONLY_TECHNICAL_CANDIDATE_WITH_EXPLICIT_HOLDS`。
- 独立静态验证：对当前哈希一致包的目标为 `18/18 PASS_INDEPENDENT_SOURCE_ONLY_VALIDATION_WITH_PRB17_HOLD`。
- PRB-17：`HOLD`；有效 prebind：`6/20 → 6/20`。
- 本轮没有生成 STEP/FCStd，因而没有伪造 CAD 快照、FEA、制造或飞行结论。

## 权威入口

- `BUS_PRIMARY_STRUCTURE_DESIGN_INPUTS_V1.json`：尺寸、材料候选、成员树、接口、质量边界、不确定度与上游哈希。
- `build_bus_primary_structure_analytic_v1.py`：纯标准库解析质量/惯量、GUM、Monte Carlo、刚度 stiff-bound 与 Gate 构建器。
- `bus_primary_structure_source_v1.py`：零参数 `gen_step()` 的受控 Build123d 源；导入无 CAD 副作用。
- `BUS_PRIMARY_STRUCTURE_ANALYTIC_REPORT_V1.json/.md`：名义几何、质量/惯量及载荷路径。
- `BUS_PRIMARY_STRUCTURE_MASS_UNCERTAINTY_V1.json`：项目 `ANALYTIC_IDEALIZATION=15% (k=1)` 下游标准不确定度，以及仅用于诊断的局部 GUM Type-B/20,000 次 Monte Carlo 对拍。
- `BUS_MASS_DECOMPOSITION_BRIDGE_V1.json`：不增加总质量的“显式结构 + 代数余量”候选，精确重组现有 bus lump；不代表设备物理布局。
- `BUS_M3R_LOAD_PATH_CONTRACT_V1.md`：连续载荷路径和下游消费合同。
- `BUS_PRIMARY_STRUCTURE_SOURCE_GATE_V1.json`：16 项源层 Gate。
- `BUS_PRIMARY_STRUCTURE_STATIC_VALIDATION_V1.json`：不导入构建器或 CAD 源的独立复算。
- `UNIFIED_R2_PREBIND_STRUCTURE_DELTA_V1.json`：PRB-17 与有效 prebind 的显式零提升记录。
- `BUS_PRIMARY_STRUCTURE_REPRODUCIBILITY_RECEIPT_V1.json`：未授权动态负对照与两次连续轻量重建的零哈希漂移回执。
- `BUS_PRIMARY_STRUCTURE_SHA256_V1.csv`：本包哈希清单。

## 可复现命令

在项目根目录运行：

```powershell
python -B 20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/bus_primary_structure_candidate_v1/build_bus_primary_structure_analytic_v1.py
python -B 20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/bus_primary_structure_candidate_v1/validate_bus_primary_structure_source_v1.py
```

这两条命令不加载 CAD 内核。构建器的 20,000 次 Monte Carlo 是单进程、确定性的。

## STEP 生成保护

当前无本轮专属 CAD 执行授权，禁止调用 `gen_step()`。后续每次运行必须同时提供：

```text
BUS_PRIMARY_STRUCTURE_EXECUTION_AUTHORIZED=YES
BUS_PRIMARY_STRUCTURE_RUN_ID=<fresh single-use id, 12..128 safe characters>
```

运行 ID 会在 CAD 内核导入前原子消费，不论内存高低都不可复用。若可用内存低于 6 GiB 或无法测量，还必须提供：

```text
BUS_PRIMARY_STRUCTURE_OWNER_OVERRIDE_ID=<fresh single-use id>
BUS_PRIMARY_STRUCTURE_OWNER_OVERRIDE_ISSUED_UTC=<ISO-8601 UTC>
BUS_PRIMARY_STRUCTURE_OWNER_OVERRIDE_EXPIRES_UTC=<ISO-8601 UTC, validity <= 2 h>
BUS_PRIMARY_STRUCTURE_OWNER_OVERRIDE_RISK_ACK=ACCEPT_SINGLE_RUN_LOW_MEMORY_RISK
```

低内存记录必须是 `memory_gate_status=OWNER_OVERRIDE_LOW_MEMORY`、`memory_gate_passed=false`、`execution_authorized=true`，绝不得写成 `MEMORY_GATE_PASS`。历史 override 或任意非空字符串都无法通过时间窗、风险回执和单次消费校验。

所有授权运行还受包级“单 CAD 写者”原子锁约束：锁在任何运行消费记录、Gate 失效记录或 CAD 内核导入之前建立；只有生成记录完整提交后才自动释放。若进程异常、被终止或锁归属不一致，锁会保留并要求 Owner 核验进程已退出后人工清退，禁止用第二个 RUN_ID 并发覆盖固定的记录与 STEP 路径。

任何授权尝试都会在 CAD 导入前写入 Gate 失效记录；因此旧 source Gate/静态验证不会在 STEP 生成或失败后继续伪装为当前证据。新 STEP 生成后必须再做几何统计、输入/源前后哈希一致性、可见快照/CAD Viewer 检查和独立 Gate；生成成功本身不升级 PRB-17。
