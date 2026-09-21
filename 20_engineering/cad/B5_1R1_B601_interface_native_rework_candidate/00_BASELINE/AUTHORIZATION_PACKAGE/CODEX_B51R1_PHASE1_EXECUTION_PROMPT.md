# Codex 执行提示词：B5.1R1 Phase 1 整机原生装配与机械接口返工

## 0. 人工授权

本轮人工授权标识：

`COMP-PROT-03-A4-B5.1R1-PHASE1-MASTER-SKELETON-V2-AND-NATIVE-REWORK-AUTHORIZATION`

授权范围仅限：

1. 耐久基准测量与 4 mm / 3 mm 偏差因果闭合；
2. Master Skeleton V2；
3. 接口方案比较与候选几何；
4. 稳定、可复位的原生 `6R + 1 fixed + 2P` 运动装配；
5. G07/G08 收拢约束候选；
6. H10 与 T005-A/B/C 验证。

本授权不等于 H9 已裁决，不授权制造、发射、飞行、连续间隙或结构资格结论。

---

## 1. 不可修改真值

开始前重新读取并复算，不得只依赖本提示词：

- V2.2 冻结顶层装配及其 SHA-256；
- accepted B601 URDF 及其 SHA-256；
- 供应商 STEP 及其 SHA-256；
- B5.1 `B51_GATE.json`；
- B5.1R1 Phase 0 Gate、21/21 输入锁和测量 HOLD；
- H10 28 行原始记录；
- T005、T003 诊断文件；
- 当前机械设计进度展示页。

锁定真值：

- accepted 动力学质量：`4.6955559493429862 kg`；
- accepted 拓扑：`6R + 1 fixed + 2P`；
- H9：`HUMAN_DECISION_REQUIRED`；
- 25°：仅 `RATIFIED_FOR_B5_1_ENGINEERING_CANDIDATE_ONLY`；
- B5.1 父裁决：`B51_REVISE_INTERFACE_COLLISION`。

任何冻结文件哈希变化，立即 fail-closed。

---

## 2. 隔离工作区

建议新建：

`20_engineering/cad/B5_1R1_B601_interface_native_rework_candidate/`

目录：

```text
00_BASELINE/
01_MEASUREMENT/
02_MASTER_SKELETON/
03_CAD/
  10_KINEMATIC_CARRIERS/
  20_B601_NATIVE_ARTICULATED/
  30_INTERFACE_ADAPTER/
  40_STOWAGE_RESTRAINT/
  50_TOP_ASSEMBLY/
  60_DRAWINGS/
  70_EXPORTS/
04_CONFIGURATION/
05_H10/
06_T005/
07_VERIFICATION/
08_REVIEWS/
09_DELIVERY/
```

必须先复制到隔离目录，再核验所有引用归属。禁止在 V2.2、B5.0、B5.1 donor 目录直接编辑。

---

## 3. Phase 1A：耐久基准测量与因果审计

### 3.1 目标

不得直接把纵梁平移 4 mm 或把鞍座移动 3 mm。先确认偏差来自：

- 中面/实体面混用；
- 钣金厚度偏置；
- 接触垫或垫片未分模；
- STEP 局部坐标重复变换；
- 25° 旋转轴或旋转中心错误；
- 临时拖动位置被保存；
- Skeleton 与 V2.2 主结构版本不一致；
- 可拆面板被误认为主承力结构。

### 3.2 方法

通过 SolidWorks 命名面、命名轴、命名坐标系和组件实例变换读取：

- spacecraft body frame；
- canonical 纵梁面/中心面；
- 真实主框或承力横梁安装面；
- B601 base frame；
- G07/G08 canonical 接触面；
- 当前桥接适配器、G07、G08 实际安装面。

不得依靠屏幕像素、手工测图或包围盒代替耐久测量。

### 3.3 输出

- `01_MEASUREMENT/B51R1_DURABLE_DATUM_MEASUREMENT.json`
- `01_MEASUREMENT/B51R1_DATUM_CAUSALITY_AUDIT.md`
- `01_MEASUREMENT/B51R1_DATUM_TRANSFORM_MATRIX.csv`

每一对象至少记录：

`authority / source_path / source_sha256 / named_entity / instance_transform / origin / normal / delta_xyz / delta_rpy / root_cause / confidence`

若无法获得耐久命名面或稳定实体标识，停止 CAD 写入，保持 `MEASUREMENT_HOLD`。

---

## 4. Phase 1B：Master Skeleton V2

创建：

`B51R1_MASTER_SKELETON_V2.SLDPRT`

它是唯一接口定位母体，不承载动力学质量，不进入 BOM，排除质量统计。

至少包含：

1. `CS_SPACECRAFT_BODY`
2. `CS_B601_BASE_ACCEPTED`
3. `CS_B601_BASE_25DEG_CANDIDATE`
4. 160 × 160 mm 安装面
5. Ø100 mm 中央通道
6. V2.2 真实主框、纵梁、横梁承力面
7. G07/G08 接触窗及法向
8. 太阳翼连续扫掠禁入体
9. 机械臂释放初始扫掠禁入体
10. 线束、连接器、工具操作禁入体
11. 拆装方向和维护包络
12. Mode A 与 Mode B 分支配置

### H9 处理

若没有单独签署的 H9 决策：

- 不得默认 Mode A 或 Mode B；
- 创建 `MODE_A_EVALUATION`、`MODE_B_EVALUATION`；
- 只冻结两分支共用基准；
- 不得将任一分支称为最终构型。

所有后续适配器、鞍座、HDRM 和顶层定位必须引用该 Skeleton，禁止用顶层拖动决定设计尺寸。

---

## 5. Phase 1C：整臂装配架构

### 5.1 采用“双层装配”，禁止再次直接用供应商复杂面做运动配合

#### 第一层：运动载体

建立 10 个轻量、隐藏、排除 BOM/质量的 link carrier：

```text
B51R1_CARRIER_BASE
B51R1_CARRIER_LINK_01
...
B51R1_CARRIER_LINK_09
```

每个 carrier 只包含：

- accepted link frame；
- parent joint frame；
- child joint frame；
- 关节轴；
- 零位基准面；
- visual geometry 安装坐标系。

#### 第二层：工程几何

将供应商/现有精细几何按 link 归属刚性安装到对应 carrier。精细几何不得直接承担关节轴配合，以避免导入面拓扑变化和 Mate 翻转。

### 5.2 顶层运动装配

创建：

`B51R1_B601_NATIVE_ARTICULATED.SLDASM`

建议所有运动关节在一个运动链层级建立；各 link 几何子装配保持 rigid。避免依赖多层 flexible subassembly 作为唯一运动机制。

每个 6R 关节必须：

- 只保留一个旋转自由度；
- 轴线来自 carrier reference axis；
- 零位来自 reference plane；
- 正方向与 accepted URDF 一致；
- 建立原生 Limit Angle Mate；
- 建立唯一驱动参数；
- 不使用“固定”掩盖配合；
- 不把 Mate Controller 当作唯一真值。

fixed joint 必须完全约束并保留 accepted parent/child 关系。

每个 2P 关节必须：

- 使用 reference axis/plane 建立原生直线运动；
- 建立 Limit Distance Mate；
- 保持 accepted URDF 的独立、对称或 mimic 关系；
- 保存全开、半开、全闭状态；
- 不允许通过 Move Component 或配置位移冒充运动副。

### 5.3 驱动真值

生成：

- `04_CONFIGURATION/B51R1_JOINT_MATE_REGISTER.csv`
- `04_CONFIGURATION/B51R1_JOINT_ZERO_AND_SIGN_REGISTER.yaml`
- `04_CONFIGURATION/B51R1_URDF_CAD_FRAME_MAPPING.yaml`

每个 joint 记录：

`joint_name / type / parent / child / CAD mate / axis / sign / zero / lower / upper / source URDF / source hash`

---

## 6. Phase 1D：接口适配器方案比较

在新建详细件前比较至少三个方案：

- A：双横梁桥式适配器；
- B：前后主框跨接适配器；
- C：局部加强框/承力筒。

评价：

- H10 关闭能力；
- 六分量根部载荷路径；
- 是否落到真实主承力框而非可拆面板；
- Mode A/Mode B 包络；
- Ø100 通道；
- 太阳翼扫掠；
- 紧固件孔边距；
- 装配工具空间；
- 质量趋势；
- 结构侵入程度；
- 维修拆装；
- 后续 FEA 可解释性。

输出：

- `03_CAD/30_INTERFACE_ADAPTER/B51R1_INTERFACE_TRADE_MATRIX.csv`
- `03_CAD/30_INTERFACE_ADAPTER/B51R1_INTERFACE_TRADE_DECISION.md`

未完成比较前不得默认沿用旧桥接件。

选定候选后生成：

- `B51R1_BASE_ADAPTER.SLDASM`
- 定位销/定位面；
- 紧固件功能包络；
- 中央通道；
- 承力横梁或加强框；
- 可拆装和工具空间；
- 明确载荷路径。

材料和紧固件等级保持 provisional，不宣称选型完成。

---

## 7. Phase 1E：G07/G08 收拢约束

创建：

- `B51R1_G07_MAIN_SADDLE.SLDASM`
- `B51R1_G08_EE_SADDLE.SLDASM`
- `B51R1_HDRM_FUNCTIONAL_ENVELOPE.SLDASM`

先输出：

`B51R1_STOW_RESTRAINT_DOF_ALLOCATION_MATRIX.csv`

分别定义：

- 约束自由度；
- 接触法向；
- 允许切向滑移；
- 预紧方向；
- 接触垫/浮动补偿；
- 安装误差吸收方式；
- 释放方向；
- 释放后残留突出包络；
- 到位/释放状态检测接口。

原则：

- 基座承担工作状态根部载荷；
- G07/G08 在发射/收拢状态参与约束；
- 禁止三个刚性接口形成无柔顺重复约束；
- 导向、承载、预紧和释放功能分开；
- 释放后不得侵入机械臂初始抬离轨迹。

---

## 8. Phase 1F：顶层整机装配

创建：

`B51R1_SPACE_EMBODIED_ROBOT_INTEGRATION.SLDASM`

建议树：

```text
B51R1_MASTER_SKELETON_V2
SC_BUS_V2_2_ISOLATED_REFERENCE
B51R1_BASE_ADAPTER
B51R1_B601_NATIVE_ARTICULATED
B51R1_G07_MAIN_SADDLE
B51R1_G08_EE_SADDLE
B51R1_HDRM_FUNCTIONAL_ENVELOPE
SOLAR_WING_ISOLATED_REFERENCE
B51R1_HARNESS_SWEEP_REFERENCE
```

必须建立并冷重开验证：

- `Q0`
- `STOWED`
- `SOLAR_DEPLOY_ARM_LOCKED`
- `ARM_RELEASE_START`
- `ARM_CLEAR_OF_RESTRAINT`
- `DEPLOYED_NOMINAL`
- `SERVICE`
- `2P_OPEN`
- `2P_HALF`
- `2P_CLOSED`

禁止通过移动实体保存姿态。状态必须来自原生配合驱动值和受控抑制矩阵。

---

## 9. H10 闭环

先按共因聚类，再逐行关闭 28 条。

每条记录必须具备：

- 返工前/后精确干涉体积；
- 返工前/后最小距离；
- 分类；
- 根因簇；
- 责任零件；
- 几何修改；
- 修改前后局部图；
- 替换证据路径、字节数、SHA-256；
- closure status。

允许分类：

- `INTENDED_BOLTED_LAP`
- `INTENDED_MACHINED_SEAT`
- `INTENDED_CLEARANCE_CUTOUT`
- `UNACCEPTABLE_COLLISION`
- `REFERENCE_GEOMETRY_FALSE_POSITIVE`

退出条件：

```text
28/28 disposition complete
UNACCEPTABLE_COLLISION = 0
UNRESOLVED = 0
```

不得因整体移动消除 8 项严重碰撞就自动关闭其他记录。

---

## 10. T005-A/B/C 验证

### T005-A：独立位形重建

- q0；
- STOW；
- 20 个固定随机种子合法位形；
- 每个位形独立从标准状态建立；
- 比较各 link frame 和末端 frame。

### T005-B：连续顺序驱动

不关闭文档，执行：

`q0 → q1 → ... → q20 → STOW → q0`

检查状态污染、Mate 翻转、符号错误和显式复位。

### T005-C：保存、关闭、冷重开

至少验证：

- q0；
- STOW；
- 一个随机位形；
- 2P 全开/半开/全闭；
- 配合抑制状态；
- 限位状态。

“关闭重开后恢复”不能替代 T005-B 显式复位通过。

输出：

- `06_T005/B51R1_T005_A_IMMUTABLE_POSES.json`
- `06_T005/B51R1_T005_B_SEQUENTIAL_RESET.json`
- `06_T005/B51R1_T005_C_COLD_REOPEN.json`

容差沿用父合同；不得临时放宽门槛。

---

## 11. 工程图与交换文件

只有 H10 与 T005 通过后才生成发布候选：

- 顶层装配 SLDDRW；
- 收拢态、释放初始态、展开态、维护态；
- 适配器 ICD；
- G07/G08 接触与释放图；
- B601 关节/零位/限位图；
- STEP；
- 用于 L2 的简化网格。

修复现有空白 PDF 问题：

- 冷重开模型和工程图；
- 强制重建所有视图；
- 检查引用配置；
- 删除或覆盖无权威默认质量字段；
- PDF 逐页渲染复核；
- 图框只引用受控质量账本，不读取 SolidWorks 默认质量作为权威。

---

## 12. Phase 1 退出 Gate

至少检查：

```text
G0 frozen hashes unchanged
G1 H9 explicit decision OR dual-branch evaluation retained
G2 28/28 H10 closed; unacceptable=0
G3 native 6R+1fixed+2P; native limits; T005-A/B/C pass
G4 G07/G08 restraint DOF and release path defined
References 100% internal and resolved
No baseline contamination
```

Phase 1 未通过时：

- 保留所有负结果；
- 不启动连续间隙和结构分析；
- 不生成“可发布整机”结论；
- 输出精确阻塞文件、实例、Mate 和所需人工动作。

允许的阶段结论最多是：

`B51R1_PHASE1_NATIVE_INTERFACE_AND_ARTICULATION_CANDIDATE_ACCEPTED_WITH_H9_AND_PHYSICAL_QUALIFICATION_HOLDS`

禁止：

- COMPLETE
- MANUFACTURING_READY
- FLIGHT_READY
- LAUNCH_QUALIFIED
- CONTINUOUS_CLEARANCE_PASS（除非后续 Gate 独立通过）

---

## 13. 首次立即执行动作

现在按顺序执行：

1. 输出仓库根目录、Git 状态和当前 SolidWorks 进程/锁文件；
2. 复算冻结输入 SHA-256；
3. 创建 B5.1R1 隔离副本；
4. 核验所有引用归属；
5. 执行耐久基准测量；
6. 输出 4 mm / 3 mm 偏差因果审计；
7. 创建 Master Skeleton V2 草案和 Mode A/B 双分支；
8. 创建 carrier 装配架构，不先导入精细几何运动配合；
9. 输出接口 A/B/C 贸易矩阵；
10. 给出 Phase 1A/1B 中间 Gate。

在耐久测量未闭合前，不创建详细适配器和鞍座；在 carrier 运动链未通过 q0 与符号测试前，不挂接全部供应商精细几何。
