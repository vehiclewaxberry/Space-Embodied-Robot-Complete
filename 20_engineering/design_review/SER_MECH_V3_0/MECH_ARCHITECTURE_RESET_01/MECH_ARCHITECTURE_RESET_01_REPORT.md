# MECH-ARCHITECTURE-RESET-01 执行报告

## 最终状态

`MECHANICAL_ARCHITECTURE_RESET_COMPLETE`

同时：

- `V3_SEED=PENDING_HUMAN_RULING`
- `V3_CAD_AUTHORING_NOT_AUTHORIZED`
- `V2_3_STAGE2=NATIVE_MECH_REAL_01_STAGE2_HOLD`
- `DELETE_AUTHORIZED=false`

## 已完成

- 读取并核对 `10_research/`、`20_engineering/`、`30_simulation/`、`40_evidence/`、`80_third_party/` 的机械相关证据；
- 以当前 Gate 和现场 SHA-256 重建 V2.0—V2.3 基线事实；
- 建立 12U、B601、太阳翼、具身硬件和图纸的 logical-object truth map；
- 给出 V3.0 未来顶装名称和两条 seed 候选路线；
- 将 V2.3 Stage 2 失败资产从 V3 继承链中排除；
- 建立 A—E 五个工作包、入口/出口 Gate、质量隔离和停止条件；
- 保留全部 UNKNOWN、HOLD、负结果和 authority 冲突。

## 核心裁决

### 1. 不继续 V2.3 Stage 2 修补

控制报告是：

`NATIVE_MECH_REAL_01_STAGE2_EXECUTION_REPORT.md`

控制裁决是：

`NATIVE_MECH_REAL_01_STAGE2_HOLD`

双代理、体积质量体、空三配置装配和 quick/temp/test 文件只能作为失败证据，标记为：

`QUARANTINE_CANDIDATE_NOT_DELETE / NEVER_INHERIT_INTO_V3`

### 2. 不推翻既有验收基线

- V2.0、V2.1：历史冻结；
- V2.2：donor only；
- V2.2_NATIVE：只读原生 source baseline；
- V2.3：引用隔离与失败集成证据；
- 新设计只进入未来 `Space_Embodied_Robot_CAD_V3_0`。

### 3. B601 三种 truth 永不互相冒充

- accepted URDF：运动学和模型质量/惯量 authority；
- vendor STEP：高保真 visual reference；
- native CAD：接口、配置和工程装配载体。

任一表征都不能反向覆盖另外两种 authority。

### 4. 结构与机构尚未工程闭合

原生框架、安装链、鞍座和左右翼根真实存在，但当前最高只能称：

`NATIVE_GEOMETRY_EXISTS / ENGINEERING_CLOSURE_NOT_REACHED`

结构载荷、材料、截面、接头、紧固、预紧、强度、刚度、模态、热和制造仍未签发。

### 5. 具身硬件尚未选型

physical TCP、任务相机、F/T、柔顺/锁紧、任务工具、目标接口和具身计算硬件仍为：

`UNKNOWN_BLOCKED`

V2.2 的末端、GNC 和 V2.0 OBC 只能作 display/volume reference。

## 必须保留的负结果

- `238.3 mm > 226.3 mm`，C5 超宽 12.0 mm；
- 太阳翼根机构宽度下限 `302.3 mm > 226.3 mm`；
- `STOW_Z_LIMIT_REFERENCE=UNKNOWN`；
- `T_SM=185.25 mm` 与 `MOUNT_FACE_X=198 mm` 双轨；
- 340.5 mm 与 366 mm 总长双轨；
- 25° clock 与 `T_MA0` authority 冲突；
- 左右翼根现场 13 件/侧与证据 9/14 件冲突；
- L_FAIL/R_FAIL/PARTIAL 当前第一阶段几何等同；
- 两张 NATIVE01 图纸标题栏的 6.159 kg/5.191 kg 均无权威。

## 本轮没有执行

- 未打开或保存 SolidWorks；
- 未修改任何 CAD/STEP/URDF/STL；
- 未创建 V3.0 CAD 根；
- 未移动、删除或隔离 Stage 2 文件；
- 未运行仿真、FEA、接触或运动分析；
- 未提交 Git；
- 未给出飞行、制造、强度或安全结论。

## 交付包

- `research_execution_plan.md`
- `mechanical_truth_map.yaml`
- `CAD_BASELINE_DECISION.md`
- `MECHANICAL_GAP_MATRIX.md`
- `SER_MECH_V3_0_PROGRAM_PLAN.md`
- `reset_gate.json`
- `output_manifest.csv`

## 下一 Gate

下一步不是直接建模，而是签发：

`V3_G0_AUTHORING_AUTHORIZED`

该人工裁决必须选择 seed、唯一 writer、frame/尺寸轨、Stage 2 处置、B601 三表征合同和 V3 命名规则。只有 Gate 成立后，才进入 Work Package A。
