# MECH-ARCHITECTURE-RESET-01 研究与执行计划

## 1. 任务目标

在不改动任何既有 CAD、STEP、URDF、仿真结果和第三方资产的前提下，重建空间具身智能服务航天器机械设计的权威链、版本边界、接口责任和后续 V3.0 工作包。

本轮完成条件是：

`MECHANICAL_ARCHITECTURE_RESET_COMPLETE`

该状态只表示机械架构重置文档与证据索引完成，不表示：

- V3.0 原生 CAD 已获准创建；
- 现有 V2.x 已通过机械发布；
- 结构强度、刚度、模态、热、发射或飞行适用性已成立；
- B601、太阳翼或具身硬件已完成物理资格验证。

## 2. 执行边界

### 允许

- 只读审计 `10_research/`、`20_engineering/`、`30_simulation/`、`40_evidence/`、`80_third_party/`；
- 读取当前 Gate、manifest、设计合同、原生 CAD 元数据、STEP/URDF 资产登记与 SHA-256；
- 新建本目录内的架构裁决、差距矩阵、执行计划和机器 Gate；
- 对后续原生 CAD 工作提出候选方案和人工裁决项。

### 禁止

- 打开并保存、另存、修复或改写任何既有 SolidWorks 文件；
- 创建或导入 STEP、URDF、STL 或新的原生 CAD；
- 删除、移动或隔离任何既有资产；
- 运行或重跑仿真、FEA、运动学、接触或热分析；
- 自动选择 V3.0 母体；
- 将 `PASS`、文件存在、静态干涉检查或显示代理升级为物理/制造/飞行结论。

## 3. 当前机器状态

- 审计时 Git HEAD：`b75352c1c226c0f3e9a4bc9c469b766e06f41616`
- 审计时 `SLDWORKS.exe`：`0`
- 工作树存在用户既有修改；本任务不覆盖、不暂存、不提交这些修改。
- 当前竞争链 Gate 为 `COMPETITION_DEMO_READY`，但 `next_stage_authorized=false`。
- `sim_10` 为 `SIM10_GATES_PASS`，柔性结论仍有 `UNKNOWN`。
- `sim_11` 为 `SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS`，面板模态与 20 ms 接触窗口仍为 provisional。

## 4. 证据优先级

从高到低：

1. 当前机器上的 Gate JSON/YAML、冻结 manifest、现场 SHA-256；
2. 已签发或明确标注 authority 的 URDF、接口合同和 human ruling；
3. 原生 CAD 的冷重开、引用归属、配置和干涉证据；
4. STEP、STL、显示包络、分析 staging；
5. 历史报告、截图和叙述性结论。

发生冲突时采取 fail-closed：

- 机器 verdict 与最终执行报告冲突时，采用时间更晚、限制更严格且能解释缺陷的裁决；
- 同一机械对象存在多个尺寸轨、frame 或状态时，不静默合并；
- 缺少签发来源的质量、载荷、材料、厚度、连接、紧固和硬件型号保持 `UNKNOWN/TBD`。

## 5. 并行审计分工

### CAD 母体线

- 复核 V2.0、V2.1、V2.2、V2.2_NATIVE、V2.3 顶层和冻结 manifest；
- 识别 V3 候选 seed、外部引用风险、Stage 2 污染和 writer authority 冲突。

### 结构与太阳翼线

- 复核 Master Skeleton、主结构、B601 安装载荷路径、收拢支承、左右翼根和工程图；
- 区分已存在原生实体、设计提案、reference TBD 和必须重建项；
- 保留 C5、302.3 mm 和 `STOW_Z_LIMIT=UNKNOWN` 等负结果。

### B601 与具身硬件线

- 绑定 URDF、厂商 STEP、质量/运动学/外形的独立 authority；
- 审查三表征、物理 TCP、F/T、柔顺、任务相机、计算硬件和许可边界；
- 识别不可进入 V3 的失败代理。

## 6. 交付物

1. `mechanical_truth_map.yaml`
2. `CAD_BASELINE_DECISION.md`
3. `MECHANICAL_GAP_MATRIX.md`
4. `SER_MECH_V3_0_PROGRAM_PLAN.md`
5. `MECH_ARCHITECTURE_RESET_01_REPORT.md`
6. `reset_gate.json`
7. `output_manifest.csv`

## 7. 退出与停止条件

以下任一情况出现，V3.0 原生 CAD authoring 必须保持 HOLD：

- 未签发 V3 seed 与唯一 writer authority；
- `T_SM=185.25 mm` 与 `MOUNT_FACE_X=198 mm` 未形成命名清晰的双轨或单一裁决；
- 25° clock 与 `T_MA0` 的关系未签发；
- V2.3 Stage 2 失败资产未给出处置记录；
- B601 三表征的质量隔离与配置互斥合同未批准；
- 结构载荷、材料、连接与紧固输入仍为空而任务要求承力/制造结论；
- 太阳翼轴、弹簧、HDRM、止挡、线束、翼板质量或收拢边界未签发；
- physical TCP、任务相机、F/T、柔顺/锁紧或 compute hardware 未选型而任务要求实体硬件。

## 8. 声明边界

本任务输出是 PDR/架构重置与 CAD authoring 前置合同。所有后续几何必须逐对象携带：

- `source`
- `authority`
- `file`
- `hash`
- `native_or_proxy`
- `editable`
- `keep_delete_freeze`
- `verification_status`

没有这些字段的对象不得进入 V3.0 active top assembly。
