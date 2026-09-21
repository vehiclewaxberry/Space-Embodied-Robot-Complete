# B5.1R1 Phase 1 中间 Gate 进度报告

日期：2026-08-01（第四轮状态同步：单坐标系冷重开持久化通过）  
任务：`COMP-PROT-03-A4-B5.1R1-PHASE1`

## 当前结论

当前机器状态为：

`INTERMEDIATE_GATE_SINGLE_CS_PERSISTENCE_PASS_NATIVE_AUTHORING_SEPARATE_AUTHORIZATION_HOLD`

已通过的是耐久测量、Master Skeleton V2 中性 STEP 见证、10-carrier q0 中性拓扑见证，以及原生 Master Skeleton **Stage A 参考几何在同一可见会话内只读重开回读**。Stage B 原生坐标系建立在 API 调用处卡死，已经失效闭合；最终 `B51R1_MASTER_SKELETON_V2.SLDPRT` 仍不存在。

新的有界授权已经执行完毕：固定诊断件在全新 SolidWorks 2024 进程中冷打开，强类型回读确认仍恰好存在 1 个 `CS_DIAGNOSTIC_ONLY`，类型为 `CoordSys`，变换为单位旋转、零平移、比例 1，外部引用为 0。一次受控 `Save3` 的错误/警告为 `0/0`，按当前标题关闭后文档数为 0，`ExitApp` 后进程消失，当前 SolidWorks 进程数为 0。因此单坐标 Gate 已正式升级为 `SINGLE_COORDINATE_SYSTEM_PERSISTENCE_PASS`。

必须把 **单坐标持久化 PASS** 与 **下游原生机械设计仍未放行** 分开：

- 单坐标 Gate：首轮创建、同进程回读与本轮全新进程冷重开共同证明保存持久化；不可变冷重开收据状态为 `SINGLE_COORDINATE_SYSTEM_PERSISTENCE_PASS`；
- 历史证据：首轮 `FAIL_CLOSED_FIRST_LAUNCH` 和两次恢复失败收据继续原样保留，但不再控制当前单坐标 Gate；
- 下游 Gate：最终 Master Skeleton 不存在，原生 Carrier 仍为 0/10，H9 未裁决，H10 为 0/28，T005-A/B/C 均未运行，8 个机械—控制交接文件仍缺失；
- 授权边界：本轮冷重开可见启动授权已消耗完毕，不能外推为最终 Master Skeleton 或 Carrier authoring 授权。

因此单坐标诊断当前正式状态为：

`SINGLE_COORDINATE_SYSTEM_PERSISTENCE_PASS`

这仍不释放最终 Master Skeleton、10 个原生 carriers 或机械—控制交接工件。Phase 2 机械工程执行图已准备但未授权：`09_DELIVERY/B51R1_PHASE2_MECHANICAL_ENGINEERING_EXECUTION_MAP_20260801.md`，SHA-256 `722773988310A166EE8F006E16C2D1B934D82E68A35B35734AB83EDF8CA3AB90`。

Carrier 离线配置一致性 Gate 已通过：10 links、9 joints、6R + 1 fixed + 2 independent P 的合同、register、URDF frame mapping 和计划写入的原生自定义属性均已登记并交叉核验。但 `.SLDPRT` 仍为 0/10、`.SLDASM` 不存在，因此上述离线 PASS 不能获得原生运动、Mate、限位、H10 或 T005 信用。

当前可展示的参考整星、维护开舱、Carrier q0 与 G07/G08 footprint 图像已经汇总到：

[B51R1 Phase 1 当前机械设计效果与装配证据图册](B51R1_PHASE1_CURRENT_MECHANICAL_VISUAL_GALLERY_20260730.md)

图册只汇总并分层标注现有证据；它不代表新的 B5.1R1 原生装配或工程图已经生成。

## 已闭合的证据

### 1. 耐久测量因果

控制 Gate：

`01_MEASUREMENT/B51R1_DURABLE_DATUM_MEASUREMENT_FINAL.json`

SHA-256：

`94400C1E282A9B35084E68B7A1B53DCC41BF33113D908C7895D0B73C672904FB`

必须区分“测量因果闭合”和“几何修复完成”：

- `4 mm` 的**测量根因已经闭合**：它来自旧截面与层基准传播，不是应整体平移的刚体误差；本轮**没有修复或替换几何**，禁止把旧桥接件或鞍座平移 4 mm。
- `3 mm` 是鞋底、可拆面板层与主结构面之间的**面板层关系**，不是可以脱离具体命名面泛化的“面板厚度”；本轮**没有修复或替换几何**，禁止添加 3 mm 垫片，也不能把可拆面板计作主承力路径。
- 鞋与纵梁仅有投影重叠证据，没有接触、紧固或载荷路径信用。
- 该 Gate 允许 Master Skeleton 基准与 carrier 运动载体 authoring，不允许直接绘制详细适配器、G07/G08。

### 2. Stage A 原生参考几何

原生零件：

`02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT`

SHA-256：

`5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B`

回读记录：

`02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2_STAGE_A_READBACK.json`

SHA-256：

`7537D17F87EA55911160B63615F590AB235ACB04F51AA797B72F8F2C891D4967`

回读状态：

`PASS_STAGE_A_NATIVE_REFERENCE_GEOMETRY_SAME_SESSION_REOPEN`

已核验：

- 16/16 必需命名特征存在；
- `COMMON_CANONICAL`、`MODE_A_EVALUATION`、`MODE_B_EVALUATION` 三个配置存在；
- 关键自定义属性通过；
- 实体数量为 0；
- 外部文件引用数量为 0；
- 回读关闭后文档数为 0。

该回读发生在同一可见 SolidWorks 会话内，不是真正的冷进程重开。Stage A 尚缺正式坐标系、G07/G08 接触窗草图、太阳翼扫掠禁入体和机械臂释放禁入体；因此它只能记为“原生参考几何”，不能称为最终 Master Skeleton。

### 3. 中性见证边界

Master Skeleton 中性 STEP：

`02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2_STEP_WITNESS_R2.step`

SHA-256：

`4AA03505AA5F3AB73ADFD091E7DFA77382234152D11CD32916783B11FA56F1BC`

10-carrier q0 中性拓扑 STEP：

`03_CAD/10_KINEMATIC_CARRIERS/B51R1_CARRIER_Q0_STEP_WITNESS_R2.step`

SHA-256：

`9A411E3DA94774C230BA9A7FBAC5F832E99333233E2193CE383998A0C3BE7602`

这些见证保留了基准轨、160 × 160 安装面、Ø100 中央禁入区、10 links、6R + 1 fixed + 2 independent P 的 q0 frame/topology/axis 信息，但不是原生 carrier 零件、Mate、限位、driver 或 T005 结果。

### 4. q0 R2 快照视觉可读性复核

独立复核记录：

`07_VERIFICATION/B51R1_CARRIER_Q0_R2_SNAPSHOT_VISUAL_REVIEW_20260730.json`

SHA-256：

`C2FCBB9962E13C545484BC1423F071292E63E3BD3E827BC55EB4AF4D13C06F51`

状态：

`PASS_RENDER_LEGIBILITY_WITH_ENGINEERING_CREDIT_HOLD`

四张现有 1800 × 1200 PNG 均已成功直接读取。复核确认：

- 模型均完整位于画面内，没有裁切；
- q0 frame chain 可追踪；
- ISO 与反向 ISO 中可见末端双分支；
- 视图标签可读。

这只关闭旧 viewer-error 引起的“渲染包可读性 HOLD”。快照没有 link/joint 文字标签，也没有精细工程几何；它不授予原生 carrier、Mate、limit、motion、干涉/间隙、尺寸精度、H10、T005 或物理信用。

### 5. Carrier 离线配置一致性

控制 Gate：

`04_CONFIGURATION/B51R1_CARRIER_CONFIGURATION_OFFLINE_CONSISTENCY_GATE.json`

SHA-256：

`2A82C41D2E49121D374B496FEEB34FA03E7C57BA85B8EF6782B95AC5D4B4F736`

Gate 状态：

`PASS_OFFLINE_CONFIGURATION_CONSISTENCY_NATIVE_CAD_NOT_CREATED`

输入合同：

`03_CAD/10_KINEMATIC_CARRIERS/B51R1_CARRIER_ARCHITECTURE_CONTRACT.md`

SHA-256：

`3998412F0FEF3DD6E0305877A4D72831A176DF6538764576608A8510B8D29112`

输出登记：

- `04_CONFIGURATION/B51R1_CARRIER_REGISTER.csv`  
  SHA-256：`D3FD0BA28BAD9F4E0819DCDABD157903921126485BE7BAEA4ACA2B781C41D8FC`
- `04_CONFIGURATION/B51R1_URDF_CARRIER_FRAME_MAPPING.yaml`  
  SHA-256：`4D5488A1A95F0CF052194908C6D8F3C79417F4FFA6EC3D06CB598D19AA19EB43`

离线交叉核验结果：

- accepted link 顺序精确匹配 10/10；
- joint 名称、类型、父子关系精确匹配 9/9；
- URDF joint origin、axis 和有效运动关节 limit 与 register/mapping 一致；
- 拓扑为 10 links、9 joints、6 revolute、1 fixed、2 independent prismatic；
- `gripper_link` 是两个独立 P 分支的共同父节点，不是单一 width 或 mimic 参数；
- 10 行 planned native custom properties 已登记，包括 `MODEL_ROLE=KINEMATIC_CARRIER`、`DYNAMIC_AUTHORITY=ACCEPTED_URDF`、`CAD_MASS_CONTRIBUTION=ZERO` 和 `BOM_EXCLUDE=TRUE`；
- 这些属性尚未写入任何 `.SLDPRT`。

信用边界：

- 原生 carrier `.SLDPRT`：0/10；
- 原生 carrier 或 articulated `.SLDASM`：不存在；
- native motion、native Mate、native limit、同文档 q0 reset、冷重开持久化：均无信用；
- H10 和 T005 信用：均为 0。

### 6. 合同与 Trade 工件当前边界

已经更新并纳入索引的 Master Skeleton 合同与 datum register：

- `02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2_BUILD_CONTRACT.md`  
  SHA-256：`45185EE239A07016849798700A2B672BA1ADFF2842CAEC7DD919977C6C45F42F`
- `02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2_DATUM_REGISTER.yaml`  
  SHA-256：`41A769163D7FE9066DDAC0A6E36E33A22AC9D33823F8CC47151515E8AC0FBC6E`

Adapter trade 工件：

- `03_CAD/30_INTERFACE_ADAPTER/B51R1_INTERFACE_TRADE_DECISION.json`  
  SHA-256：`03D8C9826673CD4B05D1C603EA439E58826996FCDE0F057C0BBF8E062F9C2DDE`
- `03_CAD/30_INTERFACE_ADAPTER/B51R1_INTERFACE_CONCEPT_TRADE_MATRIX.csv`  
  SHA-256：`FCBCFFB9B8DC2BEF6A776957A8C0356F83CAF9250DFDA16109568506A4D5A6E3`

Adapter trade 当前仅为 `TRADE_FRAME_READY_WEIGHTED_SCORE_DISABLED_NO_DOWNSELECT`。A/B/C 三个概念没有权威评分、排序或 downselect，详细 adapter、G07/G08 authoring 仍未释放。

### 7. 空白零件单坐标诊断：冷重开持久化 PASS

本轮冷重开授权录入：

- `07_VERIFICATION/B51R1_COLD_REOPEN_AUTHORIZATION_ADMISSION_20260801.json`
- SHA-256：`3BC20BFBA9AAAB8A61A1E2A580C35B4977DA8169F15597453A82A4F2518E0BC4`
- 状态：`ADMITTED_SINGLE_VISIBLE_LAUNCH_COLD_REOPEN_ONLY`
- 启动额度：`authorized=1 / consumed=1 / remaining=0`

正式诊断 Gate：

- `07_VERIFICATION/B51R1_SINGLE_CS_DIAGNOSTIC_GATE.json`
- SHA-256：`6D0C27E154E3F1ACA150EA35B2A945EC257D1CB2898A06AB5AC9448A9AF3EC5E`
- 状态：`SINGLE_COORDINATE_SYSTEM_PERSISTENCE_PASS`
- 完整单坐标诊断 PASS：`true`
- 原生 authoring 自动放行：`false`
- 下一原生阶段资格：`ELIGIBLE_FOR_SEPARATE_VISIBLE_LAUNCH_AUTHORIZATION_ONLY`

冷重开不可变证据：

| 文件 | SHA-256 |
|---|---|
| `07_VERIFICATION/B51R1_SINGLE_CS_DIAGNOSTIC_COLD_REOPEN_RECEIPT.json` | `534316819A07D7204764511A4732C99C172311CE26935156AF6AE129DA06CA0D` |
| `07_VERIFICATION/B51R1_SINGLE_CS_DIAGNOSTIC_TRANSFORM_COLD_REOPEN.json` | `3BCA317E99629143326020FBCF7D5923680E9E1196A1A423FFEAFA062403C731` |
| `08_REVIEWS/B51R1_SINGLE_CS_DIAGNOSTIC_COLD_REOPEN_PROGRESS.log` | `24A7ABC64C53492B8B4A014627874F2045539BB3D723073F4D794D1BEE646B2D` |

本轮证实的持久化事实：

| 检查项 | 结果 |
|---|---:|
| 新进程冷重开 `OpenDoc6` 调用数 | 1 |
| 打开错误 / 警告 | 0 / 0 |
| `CS_DIAGNOSTIC_ONLY` 精确名称数量 | 1 |
| 特征类型 | `CoordSys` |
| 变换 | 单位旋转、零平移、比例 1 |
| 最大单位阵误差 | 0 |
| 外部引用 | 0 |
| 受控 `Save3` 调用数 | 1 |
| 保存错误 / 警告 | 0 / 0 |
| 目标保存前 | 49233 bytes，SHA-256 `6B571B49D440BBDC723566FA97224C69AFABCBA6BAC34DCF4036A5F4037E120C` |
| 目标保存后 | 51508 bytes，SHA-256 `D55277E924B56F76EFA3682C7628B8FE841172792280E0FE57CDE4A90E3A4ABD` |
| Stage A SHA-256 前 / 后 | 均为 `5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B` |
| 关闭后文档数 | 0 |
| `HasExited` / 后续进程数 | `true` / 0 |
| 外部进程 `ExitCode` | `UNAVAILABLE`，不作为失败 |
| 强制终止 | 未使用 |

目标哈希在唯一一次受控保存后变化。正式解释为：`HASH_CHANGED_AFTER_THE_SINGLE_CONTROLLED_SAVE3; SEMANTIC_INVARIANTS_UNCHANGED; BYTE_LEVEL_CAUSE_NOT_FURTHER_RESOLVED`。坐标系数量、名称、类型、变换及外部引用等语义不变量未变；当前没有进一步解析 `.SLDPRT` 字节变化的内部来源，因此不得把它解释成几何、动力学或其他未授权内容变化。

原始 `FAIL_CLOSED_FIRST_LAUNCH`、动态 COM 失败和外部 `ExitCode` 读取失败收据全部保留为不可变历史，不被覆盖。新的全新进程冷重开 PASS 关闭了它们当时没有完成的持久化缺口，但不改写历史运行事实，也不向最终 Master Skeleton、Carrier、H10 或 T005 转移信用。

## Stage B 失效闭合

事故记录：

`07_VERIFICATION/B51R1_MASTER_SKELETON_V2_STAGE_B_COORDINATE_API_HANG_INCIDENT_20260729.json`

SHA-256：

`4655C1F553BAD4CF4CA8D568330EC97F462274D3572938063B1CE865C07ACB71`

事实：

- 使用的是实体驱动 `IFeatureManager.CreateCoordinateSystem`，没有使用数值坐标系 API；
- 进度日志停在 `BEGIN | ADD_CS_SPACECRAFT_BODY`，没有匹配的结束记录；
- SolidWorks PID 59616 变为无响应，15 秒 CPU 增量 0.203125 秒；
- 在确认只打开 Stage A 脏副本后，按精确 PID 终止该进程；
- Stage A 保存文件终止前后 SHA-256 均为 `5DEBE5...C76B`，保持不变；
- 没有生成 Stage B receipt、CS01/CS02/CS03/CS04 检查点或最终 Master Skeleton；
- 当前 `SLDWORKS.exe` 进程数为 0。

所以 Stage B 和最终 Master Skeleton 均为 `HOLD`，没有最终 Master Skeleton 的原生坐标系信用。空白诊断零件中的单坐标 CAD 功能证据不能迁移为 Stage B 或最终 Master Skeleton 信用。

## 历史离线准备（已被空白零件诊断替代）

离线验证：

`02_MASTER_SKELETON/B51R1_INSERT_COORDINATE_SYSTEM_DIAGNOSTIC_OFFLINE_VERIFICATION.json`

SHA-256：

`3DD17CBC176D70C7BE8B5F73F7B5DE8866C57CB8343EB49821D4F045A5E71671`

状态：

- 离线编译、API 反射、选择标记与附着约束检查：`PASS`；
- Stage A 副本 SolidWorks 运行时操作：`NOT_RUN`；
- 诊断范围：只在 Stage A 一次性副本上建立一个坐标系；
- 选择策略：原点标记 1、X 轴标记 2、Y 轴标记 4，调用 `InsertCoordinateSystem`；
- 工具不启动 SolidWorks，只允许附着到恰好一个、可响应且空文档的可见会话；
- 工具自超时不得终止 SolidWorks；受保护 Stage A 必须在关闭副本后重新取哈希。

该工具是历史离线准备，不是本轮空白零件运行所用的控制路径。它现为 `HISTORICAL_SUPERSEDED_BY_BLANK_PART_DIAGNOSTIC`，不能解释为 Stage A 副本诊断已运行，也不能给当前 Gate 增加信用。

## 当前未完成

- 最终 `B51R1_MASTER_SKELETON_V2.SLDPRT`：不存在；
- 原生 carrier `.SLDPRT`：0/10；
- carrier 原生装配：不存在；
- `B51R1_B601_NATIVE_ARTICULATED.SLDASM`：不存在；
- `B51R1_SPACE_EMBODIED_ROBOT_INTEGRATION.SLDASM`：不存在；
- H10：`0/28`，`UNRESOLVED=28`；
- T005-A/B/C：全部 `NOT_RUN`；
- Adapter A/B/C：没有 downselect；
- G07/G08：没有原生自由度分配和接触实体；
- H9：`UNRESOLVED_HUMAN_DECISION_REQUIRED`，Mode A/B 都保留；
- 太阳翼扫掠与机械臂释放禁入几何：TBD；
- 单坐标冷进程重开：`SINGLE_COORDINATE_SYSTEM_PERSISTENCE_PASS`（此项已闭合，但不向下游转移信用）；
- mechanics-control handoff：`NOT_RELEASED`，以下 8 个正式文件仍缺失：
  - `B51R1_MECH_CONTROL_HANDOFF_CONTRACT.yaml`
  - `B51R1_JOINT_ACTUATION_PARAMETER_REGISTER.csv`
  - `B51R1_JOINT_ZERO_SIGN_LIMIT_REGISTER.yaml`
  - `B51R1_SENSOR_FRAME_REGISTER.yaml`
  - `B51R1_BASE_INTERFACE_COMPLIANCE.yaml`
  - `B51R1_STOW_RELEASE_STATE_MACHINE.yaml`
  - `B51R1_COLLISION_MODEL_MAPPING.yaml`
  - `B51R1_CONTROL_MODEL_VALIDATION_MATRIX.csv`
- 物理质量、惯量、刚度、载荷路径、连接、公差、制造和鉴定：无信用。

## 授权状态与下一 Gate

本轮冷重开授权录入：

`07_VERIFICATION/B51R1_COLD_REOPEN_AUTHORIZATION_ADMISSION_20260801.json`

SHA-256：`3BC20BFBA9AAAB8A61A1E2A580C35B4977DA8169F15597453A82A4F2518E0BC4`

其中一次可见启动额度为 1，已经消耗 1，剩余 0。最后一次可见会话 PID 为 `63432`；正常退出后进程数为 0，未使用强制终止。由于该 `Process` 对象是外部附着而不是启动者，`exit_code=UNAVAILABLE`，但 `HasExited=true` 与进程消失已经构成退出证据。

本轮授权已经耗尽，不能复用或扩展到 Phase 2 原生建模。当前已准备但未授权的执行图为：

- `09_DELIVERY/B51R1_PHASE2_MECHANICAL_ENGINEERING_EXECUTION_MAP_20260801.md`
- SHA-256：`722773988310A166EE8F006E16C2D1B934D82E68A35B35734AB83EDF8CA3AB90`
- 状态：`B51R1_PHASE2_MECHANICAL_ENGINEERING_EXECUTION_MAP_PREPARED_NOT_AUTHORIZED`

下一 Gate 仅限：

1. 先形成并验收 Phase 2A 输入锁、datum 协调、特征命名冻结和 FK/角度/位移容差权威；
2. 另行给出限定次数和每次唯一用途的可见 SolidWorks 2024 授权；
3. S01/S02 只创建并冷重开最终 Master Skeleton，任一前置 Gate 失败立即停止；
4. S03/S04 才按 accepted link 顺序创建并逐一冷重开 10 个 Carrier；
5. S05/S06 才建立 J00..J09 和执行 Carrier-only T005-A0/B0/C0；
6. 在上述 Gate 完成前，不创建详细 adapter、G07/G08/HDRM、顶层装配、FEA、最终图纸或控制发布文件；
7. H9、Adapter trade、G07/G08 与 keep-out 未闭合前，不进入详细接口结构。

## 当前允许的结论上限

`INTERMEDIATE_GATE_SINGLE_CS_PERSISTENCE_PASS_NATIVE_AUTHORING_SEPARATE_AUTHORIZATION_HOLD`

禁止使用：

- `B51R1_PHASE1_NATIVE_INTERFACE_AND_ARTICULATION_CANDIDATE_ACCEPTED`
- `COMPLETE`
- `MANUFACTURING_READY`
- `FLIGHT_READY`
- `LAUNCH_QUALIFIED`
