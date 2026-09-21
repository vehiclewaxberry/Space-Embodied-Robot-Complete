# Unified R2 数字样机 CAD Brief V1

## 1. 工程目的

在独立授权条件全部满足后，一次性重发 `DESIGN_FREEZE_ASSEMBLY_R2_V1`，供后续动力学、连续碰撞、抓取接触和具身策略门控使用。当前文件仅是**文档化预绑定 brief**，不授权也不生成 CAD、网格、URDF、FEA 或仿真结果。

## 2. 当前继承基线

- M4 受限数字样机继续有效，不重做；其发布上限为竞赛工程数字样机。
- 当前 M7 R1 装配报告裁决：`PASS_DESIGN_FREEZE_ASSEMBLY_BUILD_WITH_EXPLICIT_HOLDS`；默认构型：`DEPLOYED_NOMINAL__ARM_TASK_READY`。
- 当前 R1 中性 STEP 为有效组合体，报告记载 41 solids；但 B601 仍为 frame/axis witness，夹爪仅 palm，太阳翼仍为 R1 代理。
- 当前 12U `BUS_PRIMARY_STRUCTURE` 只是 6 个解析实体组成的 **DISPLAY/ENVELOPE proxy**：无内部结构、舱、线束孔和检修开口，且 340.5/366.0 mm 长度尚未调和；不得作为可直接继承的物理主结构权威。
- Solar R2 为独立 `ENGINEERING_CANDIDATE - not flight-qualified`，保持候选件身份；本 brief 不把它静默并入 R1 装配。
- 根坐标系为 `S`；长度内部 CAD 单位沿用 mm，动力学边界只转换一次到 m。

## 3. 统一 R2 产品树（未来重发）

1. 12U 服务星：先冻结物理主结构来源并解决 340.5/366.0 mm 长度冲突；当前 6-primitive envelope proxy 只可用于显示/粗包络，不能冒充内部结构。
2. spacecraft load bridge 与 M3R Stage-A/Stage-B，保留已冻结接口基准、孔系和 +X_S 轴向站位语义。
3. B601 六转动关节完整物理实体；不得把 q0 frame/axis witness 当作碰撞实体。
4. Gripper R1 palm、两指、驱动/限位/保持语义及左右接触帧。
5. 左右翼 Solar R2，每翼 3 叶片；部署、单翼失效、双翼失效和收拢状态须由同一参数源生成。
6. ARM HDRM、线束/导向/夹持/连接器有限体积；Route-C 仅在 Checkpoint-B 8/8 且另有 CAD 授权后进入实体化。
7. 22 kg 目标星和 150 kg 碎片只作为场景外部资产；`T_S_target` 未冻结时不得写入主 STEP。

## 4. 帧与运动语义

- `spacecraft_assembly_frame` 与 `S` 仅按冻结 identity alias 等价。
- `M_DYNAMICS` 与 `B601_ARM_BASE_PHYSICAL` 必须保持不同，禁止静默别名。
- 任一必要变换为 null 时，该构型/动作必须被 mask 为 UNKNOWN/HOLD。
- 每个活动关节必须给出父子链、零位、正向运动的物理描述、轴、上下限、速度/力矩或推力限制以及故障锁定语义。
- M4 `F_L/F_R` 是 legacy R1 原点 `[-56.75, 113.15, 0.0]` / `[-56.75, -113.15, 0.0]` mm；Solar R2 候选根铰线为 `|y|=115.4 mm, z=-108.15 mm`、轴向 X_S。二者**不得数值继承或静默别名**；必须新建并冻结 R2 左/右根铰链 frame 及其变换。
- B601 六轴、夹爪两指、Solar R2 和 HDRM 必须使用一致的显式输入驱动 CAD、URDF 与构型表；夹爪 URDF `velocity=15` 的 SI 模型语义是 15 m/s，但不是物理执行器能力，禁止据此推导开合或任务时序。

## 5. STEP-first 交付合同

未来授权重发以 STEP 为主要几何验证产物，执行链固定为 `source generator → native model → STEP → independent inspect → snapshots`。必须同时生成：

- 原生参数模型：`DESIGN_FREEZE_ASSEMBLY_R2_V1.FCStd`
- 中性主模型：`DESIGN_FREEZE_ASSEMBLY_R2_V1.step`
- 可视网格：按 link/component 命名的 STL
- 简化碰撞网格：独立于 visual mesh，保留几何误差/膨胀量记录
- 原生 GLB：不得通过 STL 反向转换冒充原生 GLB
- 生成器源、构建报告、源哈希清单、系统 URDF/Xacro 生成物及消费端接口文件

## 6. 九构型一次性重发

必须覆盖 C01–C09：DEPLOYED_NOMINAL、LEFT_PANEL_FAIL、RIGHT_PANEL_FAIL、BOTH_PANEL_FAIL、ARM_STOWED_ONORBIT、ARM_TASK_READY、PREGRASP、TARGET_CAPTURE_22KG、TARGET_CAPTURE_150KG。每个构型均须重算系统质量、系统质心、关于系统质心且在 S 表达的完整惯量、整机包围盒、静态/连续碰撞状态和不确定度；禁止把现有 M7 DESIGN_MODEL_R2 数值直接改名为 M4 released value。

## 7. 验证与审图最低集

- BRep/STEP 冷启动：对象数、solid 数、closed/valid、零体积/重复实体、命名和层级一致性。
- 接口：M3R、load bridge、B601 基座、夹爪、Solar R2 根铰链与 HDRM 对齐及间隙。
- 运动：9 构型静态碰撞 + B601/太阳翼/夹爪连续扫掠；碰撞几何不得使用 witness。
- 质量：CAD/URDF/质量账本逐 link/component 对账，参考点和坐标系显式。
- 快照：等轴、反等轴、顶、前；至少给出干涉区域和每个失败/锁定构型的局部图。
- 消费：URDF 树/mesh 路径/惯量正定、Sim13 loader smoke test、FAIL/UNKNOWN 负控和版本哈希拒绝测试。

## 8. 分阶段准入（禁止循环依赖）

### 8.1 CAD/URDF 几何重发前置条件

1. 另行签发哈希绑定的 `UNIFIED_R2_REBASE_EXECUTION_AUTHORIZED=true` 执行记录；它是整机 R2 重发授权，不得与 Route-C 局部 CAD 授权混同或相互替代。
2. 12U physical-structure authority 与 340.5/366.0 mm 长度冲突完成独立裁决。
3. R2 左/右根铰链 frame 和 `T_S_R2_ROOT_L/R` 冻结，legacy R1 `F_L/F_R` 不得复用。
4. Route-C P01–P13 具有 value、unit、tolerance/uncertainty、traceable source 和 authority class。
5. Checkpoint-B 由 2/8 提升至 8/8，随后另发 `ROUTE_C_CAD_AUTHORIZED=true` 的有效授权记录。
6. 重发执行时重新测量内存；需 `available >= 6 GiB` 或得到**针对该次重发**的显式 Owner Override 与风险记录。历史 M4 override 不自动继承。

### 8.2 可并行但不构成 CAD 前置的科学决策

1. ODR-GPT-07 冻结 R2 ROM 维数/接触窗候选验证范围。
2. ODR-GPT-08 冻结 protocol-matched R1/R2 comparator 语义。

### 8.3 几何完成后的终局 Release joins

1. 对新实体 CAD 执行连续扫掠和 rated-envelope mission coverage；不得以旧几何提前宣称 PASS。
2. 用受控实测/供应商数据闭合夹爪真实速度、载荷速度、接触时序和不确定度；不得消费 URDF 15 m/s 字面量作为硬件能力。
3. 重算九构型质量属性、R2 Full-Flex 和耦合诊断，完成独立重放/红队/证伪。
4. 生成新版本机械接口并重绑 Sim13，最后通过独立 production/contact/handoff Gates。

## 9. 当前裁决

`HOLD_PREBIND_DOCUMENT_SET_COMPLETE__ENGINEERING_SPECIFICATION_INCOMPLETE__NO_GEOMETRY_EXECUTION_AUTHORITY`
