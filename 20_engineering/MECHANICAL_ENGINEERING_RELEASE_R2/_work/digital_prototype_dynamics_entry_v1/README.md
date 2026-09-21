# R2 数字样机与抓取动力学准入工作包 V1

## 2026-08-27 增量汇合 Gate V4

`aggregate_digital_prototype_dynamics_entry_v4.py` 以 append-only 方式绑定 V3 Gate/manifest、CAD 生成后验证链的 source-only 预检、ODR-60 Option A 的 M01 场景/碰撞预绑定 Gate/manifest，以及 R2 current-state reissue V2 Gate/package manifest。V4 的 PASS 只表示这些新增准备证据被完整、确定地汇合：候选 STEP 仍不存在，几何与 snapshot 均未执行；M01 仍为 0/3 场景实例、0/11166 系统 pair query、路径搜索 false；父 Dynamics/Control/Joint/Mechanical、Route-C、物理接触、非 ABORT 与发布均保持 HOLD/false。

```powershell
python aggregate_digital_prototype_dynamics_entry_v4.py --write
python aggregate_digital_prototype_dynamics_entry_v4.py --check
python -m pytest -q tests/test_entry_gate_v4.py
```

`CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_MANIFEST_V4.json` 排除自身，只绑定 V4 evaluator、测试、生成的 V4 Gate 与上述上游 pin，不授予执行或发布信用。

## 2026-08-27 增量汇合 Gate V3

`aggregate_digital_prototype_dynamics_entry_v3.py` 在 V2 之上精确绑定 DG3、DG4、DG5、父动力学 Gate、ODR-60 Option A 最新执行闭合、M01 intake、终端机械 Gate、控制预开发/父控制/联合 Gate，共 11 份机器裁决。V3 允许的最大解释是 DG1--DG5 受限设计候选与离线控制预开发研究范围；它不继承为父动力学、CAD、M01、Route-C、物理接触、非 ABORT、控制工程或发布 PASS。

V3 同时作两项字段级 supersession：最新 ODR-60 记录证明 Option A 已选择、安装拼写及 10/10 帧账本已闭合；它只覆盖旧控制/绑定 intake 中对应的旧字段，不覆盖 `0/9` M01 必填字段、`0/3` 场景实例或任何查询/搜索/发布 Gate。

```powershell
python aggregate_digital_prototype_dynamics_entry_v3.py --write
python aggregate_digital_prototype_dynamics_entry_v3.py --check
python -m pytest -q tests/test_entry_gate_v3.py
```

`CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_MANIFEST_V3.json` binds the
evaluator, V3 tests, this scope document, the generated V3 Gate, and all 11
external source pins. The manifest excludes itself and grants no parent-Gate,
next-stage, or release credit.

## 2026-08-27 增量汇合 Gate V2

`aggregate_digital_prototype_dynamics_entry_v2.py` 固定绑定四份机器裁决：原始准入审计、接触速度一致性裁决、Sim13 静态 System Binding 候选，以及 DG1/DG2 动力学候选。V2 只确认有界诊断进展；完整 CAD 生成、M01 几何/碰撞/路径权威、物理接触、非 ABORT 抓取、生产动力学、TMG-4/TMG-6 与发布信用继续为 false/HOLD。

```powershell
python aggregate_digital_prototype_dynamics_entry_v2.py --write
python aggregate_digital_prototype_dynamics_entry_v2.py --check
python -m pytest -q tests/test_entry_gate_v2.py
```

## 当前裁决

当前冻结件 `04_MASTER_GEOMETRY.step` 不是“完整机械臂安装在 12U 服务星上”的数字样机：其中 B601 仅为轴线/坐标见证体，夹爪仅为脱离机械臂的 palm overlay。该状态是既有 M7 生成器的明确设计选择，不是显示软件误差。

本工作包不改写任何冻结发布件，而是建立一条独立研究候选链：

- 从冻结 R2 master 中按源哈希和 solid traversal 合同保留服务星、Solar R2、M3R 与 load bridge；
- 删除 B601 轴线见证体与脱离的 palm overlay；
- 将固定 q0 的完整 B5.0 B601 B-rep 按 `T_S_B601_ARM_BASE = Ry(+90°) * Rz(+25.000014°)` 安装到 M3R；
- 保持 accepted B601 URDF 与 Unified R2 URDF 为关节、质量和动力学真值；固定 q0 STEP 不获得 DOF、质量、接触、路径搜索或发布权威。

## 权威分层

| 层级 | 当前资产 | 可声明 | 不可声明 |
|---|---|---|---|
| 冻结机械发布 | `04_MASTER_GEOMETRY.step` | R2 当前发布几何真值 | 完整安装 B601 |
| 整星外观/定位候选 | `R2_INTEGRATED_DIGITAL_PROTOTYPE_C01_V1.py` | 固定 q0 完整机械臂定位、外观审查候选 | 可运动关节、接触、制造、发布 |
| 运动学/质量 | Unified R2 URDF | 19 links、18 joints、8 actuated DOF、31.022864807342987 kg 模型质量 | Owner 已接受、接触/生产已授权 |
| 动力学诊断 | Sim14 / Sim15 | 可重复的理想刚性捕获与几何载荷诊断 | 真实接触、结构资格、非 ABORT 抓取 |
| 运行时抓取 | Sim13 v2 | 20/20 负控制与 fail-closed 后端 | 非 ABORT 运行；当前最大状态仍为 ABORT_ONLY |

## 文件

- `INTEGRATED_CANDIDATE_INPUTS_V1.json`：源哈希、过滤索引、安装变换、边界与 claim 限制。
- `CAD_BRIEF_R2_INTEGRATED_C01_V1.md`：装配坐标、源过滤、输出、基准、验证目标与非声明边界。
- `R2_INTEGRATED_DIGITAL_PROTOTYPE_C01_V1.py`：无顶层 CAD 导入的 STEP-first 生成器。
- `execute_integrated_candidate_v1.py`：调用标准 CAD STEP 工具并保持单 writer 锁直至 STEP/GLB 收据提交。
- `execute_integrated_candidate_v2.py`：在不放宽 V1 门的前提下追加失败收据，并在成功后把 authority、V1 execution、STEP 与 topology GLB 绑定成一份执行链收据；实际运行应优先调用此入口。
- `postvalidate_integrated_candidate_v1.py`：生成后两次调用标准 `cad/scripts/inspect refs`；先枚举完整 topology，再逐项复核 399 个 shape 均为正体积 solid、每叶恰一实体、单根下 11/388 两直接分组、整星 bounds、210.405 mm 安装基准、STEP/GLB、输入合同、pre-import authority、V1/V2 执行链及 active-lock absence；候选不存在时必须在 CAD 导入前 fail-closed。
- `CAD_SNAPSHOT_JOB_V1.json`：冻结 41-solid master 的历史四视图任务，不改写。
- `CAD_CANDIDATE_SNAPSHOT_JOB_V2.json`：只指向待生成的 399-solid 候选，保存正/反等轴测、顶视与前视四张审查图。
- `validate_digital_prototype_entry_v1.py`：轻量 URDF、哈希、Gate、快照与准入审计。
- `CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V1.json`：本工作包的机器裁决；不得被测试 PASS 覆盖。

生成后链当前已完成 source-only 预检 11/11，配套测试 24/24；这只证明后处理链就绪，不证明候选 STEP 存在或几何通过。

## 当前可执行验证

```powershell
python validate_digital_prototype_entry_v1.py --rerun-diagnostics
```

该命令不加载 CAD 内核；它可重放 Sim14/Sim15 诊断验证并生成本工作包收据。

## 完整候选生成的受控入口

仅在 Owner 为当前命名 run 明确授权后执行。若当时可用物理内存仍低于 6 GiB，还必须为该 run 提供新的、最长两小时、一次性 Owner Override；旧 override 禁止复用。

```powershell
$env:R2_DP_EXECUTION_AUTHORIZED = 'YES'
$env:R2_DP_RUN_ID = '<fresh-run-id-at-least-12-chars>'
$env:R2_DP_OWNER_OVERRIDE_ID = '<fresh-override-id-at-least-12-chars>'
$env:R2_DP_OWNER_OVERRIDE_ISSUED_UTC = '<ISO-8601-UTC>'
$env:R2_DP_OWNER_OVERRIDE_EXPIRES_UTC = '<ISO-8601-UTC-within-2-hours>'
$env:R2_DP_OWNER_OVERRIDE_RISK_ACK = 'ACCEPT_SINGLE_RUN_LOW_MEMORY_RISK'
python execute_integrated_candidate_v2.py
```

若可用内存达到 6 GiB，只需新 run 授权，不需要低内存 override。生成成功后按顺序执行：

```powershell
python postvalidate_integrated_candidate_v1.py --postgenerate
python -m scripts.snapshot --job "F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/digital_prototype_dynamics_entry_v1/CAD_CANDIDATE_SNAPSHOT_JOB_V2.json"
```

第二条命令从 active CAD skill 根目录执行。随后必须人工/视觉审阅四张快照，并把疑点转成 `measure`、`frame` 或 `align` 检查；在 post-generation Gate 与视觉审查完成前，STEP 仍只是“未审查研究候选”。当前 CAD Viewer runtime 缺少技能要求的 `agent:start`，所以生成后的合规可视交接先以强制 snapshot 为回退，不能伪造 Viewer 链接。

## 未闭合项

- M01：required fields 0/9、instantiated scenes 0/3、clearance 0/11166、motion certificate 0/150、oracle 0/11166，且无连续 edge certificate。
- Route-C/线束：当前固定外线束强制关键状态为 UNSAFE，G12 未闭合。
- Sim13：Owner、Route-C disposition、system binding 与 consumer/contact authority 均未接受；最大运行状态 ABORT_ONLY。
- 接触速度已完成消费者级语义处置：0.005 m/s 为当前硬上限，历史 0.05 m/s 对当前消费者拒绝；as-built/physical contact authority 仍为 HOLD。
- 冻结 `01_BASELINE_MANIFEST.json` 的 self entry 与当前文件自身 bytes/hash 不一致；本研究分支仅登记，不静默改写。
