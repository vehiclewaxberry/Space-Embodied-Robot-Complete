# M4-L02 R2 九构型状态与质量属性合同 V1

## 裁决

本包闭合的是 **C01–C09 配置身份、状态字段、设计级质量/质心/惯量视图及动力学允许用途**，不是 CAD、碰撞、接触、装配或父级发布 Gate。机器裁决固定为：

`PASS_CONFIGURATION_CONTRACT_AND_DESIGN_MASS_TRACEABILITY_ONLY__ZERO_COMPLETE_CURRENT_GEOMETRY_ZERO_RELEASED_COLLISION_NO_PARENT_GATE_CREDIT`

因此，本包可让动力学消费者以 fail-closed 方式读取九构型的 `DESIGN_MODEL_R2` 质量属性，并能区分“可加载的设计质量属性”和“不可用于碰撞/接触的缺失当前几何”。它不重发 `00_RELEASE_GATE.json`，也不授权下一阶段。

## 当前机器真值

| 项目 | 计数 | 最大可主张范围 |
|---|---:|---|
| C01–C09 身份映射 | 9/9 | 精确跨 M4、M5、M7 名称与历史别名 |
| 设计质量/质心/惯量 | 9/9 | `DESIGN_MODEL_CANDIDATE_ONLY_NOT_AS_BUILT` |
| 唯一核心质量/质心/惯量 binary64 叶 | 180/180 | 每构型 20 个唯一叶；类型与 IEEE-754 位模式逐叶对拍 |
| 质量 receipt 独立复核 | 36/36 | 每构型质量 1 项、质心 3 项；这是复核次数，不冒充新的唯一叶 |
| `min_eigenvalue_kg_m2` 审计 | 9/9 + receipt 9/9 | `design_checks_from_ssot` 全字段精确对拍，最小特征值另做 binary64 位级复核 |
| 当前完整集成几何 | 0/9 | 不可做系统碰撞或接触 |
| 当前 source-only 拓扑候选 | 1/9 | 仅 C01；不是发布几何 |
| M5 诊断几何见证 | 9/9 | 哈希绑定；不具质量或碰撞权威 |
| 发布级碰撞清晰 | 0/9 | 全部 false |
| 生产完整状态向量 | 0/9 | 夹爪/HDRM/锁止/目标附着未知量保持 null |
| as-built 质量属性 | 0/9 | 禁止由设计值冒充 |

特别地，C01 的构型语义使用 `Q_HOME`，而当前静态 CAD 候选表示 `q=[0,0,0,0,0,0]`；该冲突未解决，所以 C01 也不能记为“当前完整构型几何”。C05 的候选姿态保留 567.734 mm FK 不一致与 abort-only HOLD；C06 保留构型批准 HOLD；C07–C09 只保留诊断候选姿态。

## 产物

- `frozen_contract_v1.py`：无 I/O、无评估函数的冻结合同层；builder 与 validator 只共享字面合同，不共享判定实现。
- `SOURCE_AUTHORITY_LOCK_V1.json`：20 个源的字节数和 SHA-256 精确锁；raw rows、ID map、声明计数必须同时为 20，ID/path 唯一且 `all_sources_match=true`。
- `R2_CONFIGURATION_CROSSWALK_V1.yaml`：九构型跨版本身份与别名。
- `R2_CONFIGURATION_STATE_VECTOR_CONTRACT_V1.yaml`：6R、2P、离散状态、太阳翼、HDRM、锁止和目标附着字段合同。
- `R2_NINE_CONFIGURATION_MASS_PROPERTY_VIEW_V1.yaml`：从 V3_R2 SSOT 无改值派生的九构型设计质量属性。
- `R2_CONFIGURATION_GEOMETRY_AVAILABILITY_V1.csv`：当前、source-only、部分 master、诊断几何和碰撞权威分账；bbox 必须严格解析为有限 binary64 三元组并逐位对拍 M5 源。
- `R2_CONFIGURATION_DYNAMICS_USE_MATRIX_V1.yaml`：每个构型允许的最大动力学用途。
- `M4_L02_NEGATIVE_CONTROL_RESULTS_V1.json`：35 个反例必须被捕获，覆盖重复键、NaN/Infinity、质量类型/1 ULP、source-lock 重复 ID/path/计数、空结构化 null、bbox、SSOT checks/min-eigenvalue、权限晋升、名称/部分几何漂移及 Gate/source/spec/manifest hash/role 完整性。
- `M4_L02_CONFIGURATION_STATE_CONTRACT_GATE_V1.json`：本地合同 Gate；所有父级授权字段为 false。
- `M4_L02_CONFIGURATION_STATE_CONTRACT_SHA256_V1.csv`：自排除清单；不把自身纳入递归哈希。

`.yaml` 文件采用 JSON 子集的规范化编码，以便严格拒绝重复键、`NaN`、`Infinity`。太阳翼 HDRM、锁止与机械臂 HDRM 未知量必须符合冻结的非空键结构且所有指定叶为 `null`；空 `{}` 不得利用真空全称检查冒充结构化未知。URDF 中 `[0, 0.0715] m` 只是夹爪关节允许域，M5 中 `0.055 m` 只是显示见证，两者都不是 C01–C09 的权威状态值。

## 可复现命令

在本目录运行：

```powershell
python build_configuration_contract.py --write
python build_configuration_contract.py --check
python validate_configuration_contract.py
python run_negative_controls.py --check
python -m pytest -q -p no:cacheprovider --basetemp=.pytest_tmp tests
```

构建器先校验 20 个源哈希；任何源字节变化都会 fail-closed，要求重新审计而不是静默更新。生成链与验证链被强制分离：builder 不导入 validator，validator 不导入 builder，冻结 spec 不导入两者。builder 用自己的 25 项生成检查和 35 项反例生成 Gate；独立 validator 重新读取源和产物，以另一套实现复算 25 个核心检查、35 个反例、26 项 Gate、14 条 exact-set/unique/no-extra/role-exact 自排除 manifest 及导入图，完整验证为 29/29。NC21/22/23/25/35 使用与正式 `FULL27`/`FULL28` 相同的完整 Gate/manifest 验证路径对临时对象执行篡改，不以“对象发生变化”作为捕获证据。

## 不可升级边界与下一证据

本包没有新 CAD 运行，不能把 M5 诊断 GLB、41-solid partial master STEP 或 source-only URDF 升级为完整集成几何；不能把低置信度目标惯量升级为实测；不能填实太阳翼 HDRM、锁止点、机械臂 HDRM、夹爪位置、目标附着变换或接触法向。

若要提升到几何/碰撞/接触或父级准入，至少需要：C01 在构型 `Q_HOME` 下的当前集成几何、所需 C02–C09 几何分支、发布级系统碰撞与接触证据、经测量或批准的夹爪/HDRM/锁止/目标附着状态，以及硬件存在后的 as-built 质量属性。任何这些证据到达后都应触发源锁更新和本包重审计，而不是继承本次 PASS。
