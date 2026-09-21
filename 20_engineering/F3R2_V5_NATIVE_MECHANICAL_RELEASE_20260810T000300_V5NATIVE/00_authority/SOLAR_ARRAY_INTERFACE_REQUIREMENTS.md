# SOLAR_ARRAY_INTERFACE_REQUIREMENTS — V5 左右对称三板太阳翼接口要求

文档状态：`V5_NATIVE_FINALIZATION_INTERFACE_FROZEN_R2`  
签发范围：`COMPETITION_PROTOTYPE_BASELINE`  
签发日期：2026-08-13  
适用变更包：`V5_NATIVE_FINALIZATION`  
目标对象：`MULTI_PANEL_SOLAR_ARRAY_CANDIDATE`  

本文件是三板太阳翼原生重建、顶装、运动/净空和发布验证的唯一 V5 接口输入。它不是飞行太阳翼、部署器合格、发射合格或制造放行文件。

## 0. 工程边界

### SA-REQ-001 — 禁止重新设计机械总体

本变更只把既有单板太阳翼表示替换为可验证的左右对称三板机械候选；不得改变航天器总体构型、B601 安装侧、母舱主结构、机械臂拓扑、杆长或既有冻结接口。

### SA-REQ-002 — 不可变真值

以下对象保持只读，任何 CAD 质量、配合或配置均不得反向覆盖：

- accepted B601 URDF；
- B601 joint topology、joint axes、joint limits、link length；
- B601 mass / CoM / inertia truth；
- V2.2 frozen baseline 及 F3R1/F3R2 frozen evidence；
- 已签发的 Rev-B2 B601 adapter、wing-root three-web clevis、G07/G08/Mid V2 support、HDRM functional envelope、camera/harness envelope 与 gripper palm/left/right split 的接口语义。

accepted URDF 的原始文件 SHA256 为 `1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164`。历史姿态文件中的 `408147...` 是换行规范化后的内容哈希，不得把两者误判为真值漂移。

### SA-REQ-003 — 允许写入范围

所有新增或修正只允许进入唯一 V5 后继树：

`20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE/`

若现有错误候选需要替换，必须先进入该树的 quarantine/evidence 隔离区并形成移动前后哈希；禁止覆盖、删除或原地修改 V2.2/F3R1/F3R2 donor/frozen 文件。

## 1. 权威链与优先级

仓库中不存在独立命名为 “V5 authority matrix” 的文件。实际控制链是：V4 工作包权威矩阵 → V5 权威来源寄存器/控制基线 → F3R1/F3R2 状态与姿态冻结输入 → 本文件的 V5 三板接口细化。

| 优先级 | 权威对象 | 当前文件/哈希 | 用途 |
|---:|---|---|---|
| 0 | accepted B601 URDF | `20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf`，raw SHA256 `1BC2...C164` | L0 运动学、动力学与惯量真值 |
| 1 | V2.2/F3R1/F3R2 frozen baselines | `00_authority/V5_PROTECTED_BASELINE_PRE.json` | donor 与冻结证据只读边界 |
| 2 | V4 工作包权威矩阵 | `20_engineering/F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809/01_authority/MFINAL_AUTHORITY_MATRIX.csv`，SHA256 `74137F83A3D609EF9386195234E9EF6FD4B49ABCE56F9862EB70DDAA8B04BEE9` | V5 继承的工作包/claim scope |
| 3 | V5 权威来源寄存器 | `00_authority/V5_AUTHORITY_SOURCE_REGISTER.json` | V4 control/pose 与 F3R2 pose/freeze 的哈希链 |
| 4 | V5 控制基线 | `00_authority/V5_CONTROL_BASELINE.yaml`，SHA256 `6F10BF844B975F416FAB0B7BB02CB82D984A9CC8A5BF81D442870C7EBE554B75` | 不可变真值、q authority、禁止称谓 |
| 5 | 单板状态/角度权威 | `F3R1_G2_CONFIG_ANGLE_AUTHORITY.json`，SHA256 `1BDBCD3598B6C262E16CE3DF10CEA5BDE11FBF382F4192BAB92D6729CA9F5AF1` | 0°/90° 与左右失效的侧级语义 |
| 6 | F3R2 状态/姿态冻结 | `F3R2_CONFIGURATION_MATRIX.csv`，SHA256 `8CDE817944078ED318AF6FDB5D35CB1B5281FF150B33F4A099708F1BDB7E9947`；`F3R2_POSE_FREEZE.json` | 运行 q 与旧单板场景证据 |
| 7 | 根铰链接口实测 | `F3R2_WING_ROOT_INTERFACE.json` | 根轴、销/孔、翼根 clevis 与 stop 接口 |
| 8 | 本文件 | 本次 R2 签发 | 三板拓扑、逻辑角、镜像、状态和验收合同 |

冲突时按表中较高优先级裁决。低层原生 CAD 的“可重建”或“可冷开”不能升级其权威等级。

## 2. 坐标、角度与镜像合同

### SA-REQ-010 — 根铰链权威

| 项目 | LEFT | RIGHT | 状态 |
|---|---:|---:|---|
| 根铰链轴线 | X 平行线，过 `(-40, +143.15, 0) mm` | X 平行线，过 `(-40, -143.15, 0) mm` | `MEASURED_BREP_AUTHORITY` |
| 根销直径 | Ø8.000 mm | Ø8.000 mm | `MEASURED_BREP_AUTHORITY` |
| 根耳孔直径 | Ø8.400 mm | Ø8.400 mm | `MEASURED_BREP_AUTHORITY` |
| 原单板内缘 | `y=+113.15 mm` | `y=-113.15 mm` | `MEASURED_BREP_REFERENCE` |
| 原单板厚度 | 6.0 mm | 6.0 mm | `MEASURED_BREP_REFERENCE` |
| clevis 径向闭合距离 | 30.0 mm | 30.0 mm | 已由 V5 true-hinge/three-web clevis 候选承担 |

轴向量 `+X` 与 `-X` 代表同一无向轴线；验收比较轴线共线性，不以向量符号制造左右差异。根轴偏置应 ≤0.05 mm，轴线夹角应 ≤0.1°。

### SA-REQ-011 — 三板候选包络

三板不得改变原单板部署外廓：

- 展开 X 包络：`[-174.5, +52.5] mm`；
- 展开最外侧 Y：LEFT `+313.15 mm`，RIGHT `-313.15 mm`；
- 面板结构厚度占位：6.0 mm；
- 根轴至最外缘有效展长：170.0 mm；
- 每板出舱方向候选宽度：`170/3 = 56.6667 mm`；
- 每板 X 向候选长度：227.0 mm。

这些数值是保留既有外廓的 `CANDIDATE_PLACEHOLDER`，不是太阳电池片、铺层或强度设计。若为铰耳/止挡增加局部结构，整体 deployed envelope 仍不得越过上述边界，除非另行 ECR。

### SA-REQ-012 — 左右镜像不变量

RIGHT 必须是 LEFT 关于 XZ 平面的真正镜像：

`T_R = Mirror_XZ(T_L)`，即位置满足 `(x_R, y_R, z_R)=(x_L,-y_L,z_L)`，方向余弦满足同一反射合同。

展开态面板中心候选值为：

| Panel | LEFT y (mm) | RIGHT y (mm) |
|---|---:|---:|
| 1 | +171.4833 | -171.4833 |
| 2 | +228.1500 | -228.1500 |
| 3 | +284.8167 | -284.8167 |

左右对应实体的镜像位置误差应 ≤0.05 mm，镜像姿态误差应 ≤0.1°。任何 RIGHT 面板中心出现在 `+Y`、穿过 bus，或轴文本位于 `-Y` 而实体位于 `+Y`，均直接 FAIL。

### SA-REQ-013 — 逻辑角定义

状态表中的 `panel_angle_deg_[L/R][3]` 是三个串联铰链的**归一化逻辑展开角**：

`[α1(root→P1), α2(P1→P2), α3(P2→P3)]`

- `0° = STOWED/FOLDED`；
- `90° = DEPLOYED/COPLANAR`；
- LEFT/RIGHT 的 SolidWorks 原始 mate 符号允许相反，但归一化读回应相同；
- 不得以静态自由变换代替真实铰链约束后再宣称运动闭环；
- 中间连续路径尚无部署动力学权威，阶段配置只是比赛机械静态锚点。

## 3. 三板机械拓扑

### SA-REQ-020 — 每侧拓扑

```text
Bus / existing true root hinge
  → Panel-1
      → Inter-panel hinge H12
          → Panel-2
              → Inter-panel hinge H23
                  → Panel-3
```

LEFT 使用 L1/L2/L3，RIGHT 使用 R1/R2/R3。两侧使用独立 OBJECT_ID、独立配置/配合抑制状态和独立证据行，禁止 side 参数被忽略。

### SA-REQ-021 — 每个 panel 的最低机械语义

每个 L1/L2/L3/R1/R2/R3 必须具有：

1. 简化原生结构实体；禁止真实太阳电池片、铺层和电性能建模；
2. inboard hinge axis datum；P1 连接 root，P2/P3 连接前一板；
3. 与相邻板/收拢垫的 stow interface datum；
4. deployed stop contact datum；
5. 单一实体跨配置的折叠关系；禁止 STOWED/DEPLOYED 双实体伪造；
6. `HARNESS_EXIT_IF` 几何接口/出口基准；禁止凭空选连接器或线规；
7. `EXTERNAL_MECHANICAL_MASS_ONLY` 质量占位属性与独立 BOM 行。

### SA-REQ-022 — 铰链/止挡层级

- root hinge 复用已通过的 LEFT/RIGHT true-hinge 轴线、销/孔和 three-web clevis；不得再创建第二套并行根轴；
- H12 与 H23 必须各有一个真实 1R 同轴配合组和一个 deployed limit/stop 接触；
- 每侧三铰链应读取为 3R 串联链；除明确配置驱动外不得 Fix 全部面板；
- inter-panel pin diameter、bearing type、spring stiffness/preload、latch/lock、stop compliance/load share 均为 `UNKNOWN/HOLD`；原生候选只能用几何占位，不得声称机构选型完成。

### SA-REQ-023 — 收拢与线束

- 每侧至少一个独立 `STOW_PAD_IF` 与 G07/G08/Mid/HDRM 接触白名单登记；收拢接触不得被误报为一般干涉；
- 每个 panel 必须有 harness exit datum；每侧根部必须有 `IF-SA-HARNESS-L/R` 接到当前 OD9 静态包络；
- 旧 OD9 静态扫掠的 114.665 mm 最小曲率半径不能继承为三板活动线束证据；
- 三板活动线束的实际 cable bend radius、service-loop length、扭转与寿命保持 `UNKNOWN/HOLD`，直到有原生 sweep、实物和 owner 签发。

## 4. 太阳翼状态合同

状态名统一使用用户签发的 `SOLAR_DEPLOY_STAGE1/2`；旧文档中的 `SOLAR_DEPLOYING_STAGE1/2` 仅作历史别名，不得继续写入 CAD/configuration registry。

### SA-REQ-030 — 七个配置及逐板逻辑角

| V5 configuration | LEFT α1/α2/α3 | RIGHT α1/α2/α3 | hinge-state 摘要 | 状态等级 |
|---|---:|---:|---|---|
| `SOLAR_STOWED` | 0/0/0 | 0/0/0 | 两侧 `[STOW,STOW,STOW]` | 静态工程收拢锚点 |
| `SOLAR_DEPLOY_STAGE1` | 90/0/0 | 90/0/0 | 两侧 `[DEPLOY_STOP,STOW,STOW]` | `CANDIDATE_STATIC_STAGE` |
| `SOLAR_DEPLOY_STAGE2` | 90/90/0 | 90/90/0 | 两侧 `[DEPLOY_STOP,DEPLOY_STOP,STOW]` | `CANDIDATE_STATIC_STAGE` |
| `SOLAR_DEPLOYED_NOMINAL` | 90/90/90 | 90/90/90 | 两侧 `[DEPLOY_STOP,DEPLOY_STOP,DEPLOY_STOP]` | 继承侧级 90/90 端态；三铰链细化为 V5 interface mapping |
| `SOLAR_LEFT_FAIL` | 0/0/0 | 90/90/90 | LEFT `[ROOT_RELEASE_FAIL,BLOCKED_UPSTREAM,BLOCKED_UPSTREAM]`；RIGHT 全 deployed stop | 旧 `L_FAIL(0/90)` 的三板根释放失败锚态 |
| `SOLAR_RIGHT_FAIL` | 90/90/90 | 0/0/0 | LEFT 全 deployed stop；RIGHT `[ROOT_RELEASE_FAIL,BLOCKED_UPSTREAM,BLOCKED_UPSTREAM]` | 旧 `R_FAIL(90/0)` 的三板根释放失败锚态 |
| `SOLAR_BOTH_FAIL` | 0/0/0 | 0/0/0 | 两侧 `[ROOT_RELEASE_FAIL,BLOCKED_UPSTREAM,BLOCKED_UPSTREAM]` | 旧 `DEPLOY_FAILED_BOTH(0/0)` 的三板根释放失败锚态 |

FAIL 三态是用于碰撞环境与具身 AI 数据多样性的**静态根释放失败场景**，不提供故障概率、故障检测、恢复动作或所有 H12/H23 局部卡滞组合的权威。新增局部铰链故障场景必须通过 ECR 增加新状态名，不能改写上述七态。

### SA-REQ-031 — 状态寄存器 schema

每个状态必须在 `04_configurations/V5_SOLAR_STATE_REGISTER.csv` 形成一行，至少包含：

```text
state
panel_angle_deg_L[3]
panel_angle_deg_R[3]
hinge_state_L[3]
hinge_state_R[3]
collision_state
camera_visibility
arm_clearance_mm
bus_clearance_mm
harness_clearance_mm
native_configuration_ref
evidence_ref
owner
authority_class
```

字段不得以 `Infinity`、空比较集、`SKIPPED`、未解析 Measure 或 bbox 结果作为 PASS。任何未执行项必须显式写 `PENDING/HOLD`，不得留空。

## 5. 机械臂与相机权威

### SA-REQ-040 — 冻结 q 输入

| Pose | q (deg) | 当前权限 |
|---|---|---|
| `Q_DEPLOYED_HOME` | `[-90,-120,-60,0,-30,0]` | `AUTHORIZED_RUNTIME_INPUT` |
| `Q_RELEASE_CLEAR` | `[-90,-120,-120,-60,-30,0]` | `AUTHORIZED_GEOMETRIC_END_STATE`；不授权释放过程 |
| `Q_SERVICE_READY` | `[-90,-60,-120,-30,0,0]` | `AUTHORIZED_RUNTIME_INPUT_WITH_SERVICE_RATIFICATION_HOLD` |
| `Q_STOW_ENGINEERING_CANDIDATE` | `[145.572,-168,-57,-41.143,-20.954,-3]` | 仅工程 fit-up seed |
| `Q_SERVICE_GRASP` | 未定义 | `NOT_AUTHORIZED`；只能保留未来 envelope/IK candidate 空间，不得声称已验证 |

太阳翼碰撞不能通过移动上述机械臂姿态来解决。优先级固定为：solar hinge logical angle → panel fold handedness/geometry → deployment sequence。任何 q 改动都超出本变更包权限。

### SA-REQ-041 — Camera visibility 的允许含义

`SERVICE_CAMERA=UNSELECTED` 与 `CAMERA_MODEL_SELECTION_HOLD` 保持不变。当前每态只允许记录：

- `INTERFACE_ENVELOPE_LOS_CLEAR`；
- `INTERFACE_ENVELOPE_OCCLUDED`；
- `NOT_EVALUATED_CAMERA_MODEL_SELECTION_HOLD`。

即使接口包络 LOS CLEAR，也不得声称真实 FOV、工作距离、最小测距、深度质量或手眼标定 PASS。

## 6. 原生验证合同

### SA-REQ-050 — 必查实体对

在 V5 顶装中，对七个太阳态与三个授权 q（适用时）至少运行：

- arm ↔ L1/L2/L3/R1/R2/R3；
- arm ↔ bus；
- arm ↔ root hinge / inter-panel hinge / deployed stop；
- gripper ↔ bus / solar；
- camera interface/envelope ↔ solar；
- B601 harness ↔ solar；
- solar harness ↔ bus / solar moving bodies；
- solar ↔ bus / G07 / G08 / Mid / HDRM residual envelope；
- LEFT solar ↔ RIGHT solar。

### SA-REQ-051 — 净空判据

- 继承 F3R2 的竞争原型最小净空判据：非白名单实体对 `minimum distance ≥ 5.0 mm`；
- interference volume 必须为 0；
- `STOW_PAD`、stop contact、pin/bore 等预期接触只能通过显式 pair whitelist 与接触语义验收；
- 历史单板 mesh 的 123.5222/166.2478 mm arm↔wing 数值不能转移到新三板；必须用解析后的 V5 native B-rep 重测；
- 最终证据只接受 SolidWorks 原生解析 B-rep 的干涉/最小距离结果；STEP/FCStd/STL/bbox 只能作诊断。

### SA-REQ-052 — 运动与读回

每个配置必须证明：

1. 配置名存在且唯一；
2. 六块 panel 均为同一物理组件实例的配置运动，不使用成对假实体；
3. 三个逻辑角的 command/readback 在 ±0.1° 内一致；
4. 左右镜像误差满足 SA-REQ-012；
5. H12/H23 的同轴偏差 ≤0.05 mm；
6. rebuild error=0、mate error=0、dangling reference=0；
7. 从全新进程冷开后重新测量，而不是只核对配置名列表；
8. deployment stage 连续段按自适应采样检查碰撞，不能只验证端点。

## 7. 质量、BOM 与数字线程

### SA-REQ-060 — 质量边界

- 太阳翼质量仅为 `external mechanical mass only`；
- 六块 panel、铰链/止挡/收拢/线束接口件均应有独立质量行；
- 初始来源等级为 `ESTIMATED_PLACEHOLDER`，原生质量属性读回后可升为 `MEASURED_CAD_EXTERNAL_ONLY`；
- 不得写入 accepted URDF，不得覆盖航天器 mass/inertia truth，不得把 CAD roll-up 宣称为航天器真实质量；
- panel material/layup/cell thickness、真实太阳翼惯量保持 `UNKNOWN/HOLD`。

### SA-REQ-061 — 数字线程

每个 L1/L2/L3/R1/R2/R3、H12/H23、root IF、stop、stow pad、harness exit 必须进入：

- frame mapping；
- link/component mapping（太阳翼为 external subsystem，不伪造 B601 link）；
- configuration/state mapping；
- collision asset manifest；
- BOM 与 mass annex；
- native file/hash manifest。

## 8. 已知不合格现状（不得继承为 PASS）

### SA-REQ-070 — 现有三板候选失效

截至本文件签发前，以下资产只可作 `QUARANTINED_DIAGNOSTIC_DONOR`：

- `01_native_parts/solar_array/SOLAR_PANEL_L1..R3.SLDPRT`；
- `02_native_subassemblies/L_SOLAR_ARRAY.SLDASM`；
- `02_native_subassemblies/R_SOLAR_ARRAY.SLDASM`；
- `13_validation/V5_SOLAR_ARRAY_COMPLETION_RECEIPT_20260811T113120.766168Z.json`；
- `04_configurations/V5_SOLAR_STATE_REGISTER.csv`（旧版 SHA256 `EA09A55A8845DF92EFDC7C55A20BB884306BC4401AC201A269302C9900457F05`）。

失效原因：

1. RIGHT 构建同时对已带负号的坐标和 side sign 再取负，造成双重符号；R1/R2/R3 落入 `+Y`/bus 方向，不是 LEFT 的 XZ 镜像；
2. `config_pose_map(side)` 忽略 side，`SOLAR_LEFT_FAIL` 与 `SOLAR_RIGHT_FAIL` 在左右装配中应用同一三元组；
3. 旧 `LEFT_FAIL=90/0/0`（双侧）、`RIGHT_FAIL=90/90/90`（双侧）分别退化为 STAGE1 和 NOMINAL，不能表达单侧失效；
4. `hinge_state=NO_KINEMATIC_MATE_YET`，只有静态 transform；
5. collision/camera/arm clearance 均为 `PENDING_LOOP2`；
6. 完成回执的 42/42 只证明错误的 expected table 被持久化并冷开，不证明镜像、真实铰链、失效语义或整机集成；
7. 当前 V5 顶装路径仍使用每侧一个 `*_WING_PANEL_PHYSICAL.SLDPRT`，尚未把 L/R 三板子装配作为 live solar subsystem 接入。

因此修复必须产生新的原生文件哈希、非 resume 全量位姿/配合读回、顶装回执和状态寄存器；禁止在旧回执上补文字后沿用其 PASS。

## 9. 原生交付与 Gate

### SA-REQ-080 — Loop 顺序

```text
Interface freeze（本文件）
  → quarantine 旧错误候选并锁定哈希
  → Loop 1: 六 panel + root/H12/H23/stop/stow/harness 原生件
  → Loop 2: L/R 三板子装配、真实 mates、七配置、镜像/冷开
  → Loop 3: V5 top integration + q/solar/camera/harness clearance
  → Loop 4: SLDDRW + BOM + Pack-and-Go + clean-process cold reopen + hash + human review
```

### SA-REQ-081 — 必须存在的原生交付

- 六块 panel 的 `SLDPRT`；
- 两套独立三板 `SLDASM`；
- root/H12/H23/stop/stow/harness interface 原生零件/子装配；
- 接入三板太阳翼的 V5 top `SLDASM`；
- 太阳翼总装/接口工程图 `SLDDRW`（至少展开、收拢、铰链/接口与状态表）；
- 原生 BOM、mass annex、state register、clearance evidence；
- Pack-and-Go 自包含包；
- 退出 SolidWorks 后由全新进程 cold reopen 的 readback；
- SHA256 manifest 与受保护输入 PRE=POST。

只存在 STEP、FCStd、STL 或截图不能通过该 Gate。

### SA-REQ-082 — 最终称谓与持续 HOLD

完成全部证据后允许最高称谓：

`F3R2_V5_NATIVE_MECHANICAL_BASELINE_CLOSED / COMPETITION_PROTOTYPE_BASELINE`

以下持续 HOLD：

- `AUTHORIZED_LAUNCH_LOAD=HOLD`；
- `THERMAL_VACUUM=HOLD`；
- `RANDOM_VIBRATION=HOLD`；
- `FORMAL_FASTENER_MOS=HOLD`；
- `CAMERA_MODEL_SELECTION_HOLD`；
- inter-panel mechanism product/life/reliability/deployment shock；
- `FLIGHT_READY`、`LAUNCH_QUALIFIED`、`MANUFACTURING_RELEASED_BASELINE`。

机械闭环后所有机械修改进入 `ECR ONLY`；之后才能把冻结的 native geometry/hash 交给 free-floating dynamics、control、SAFE-00、embodied capture 与 VLA。

## 10. 变更控制

以下任一变化必须新建 ECR/authority ruling：

- 改变 root hinge axis、V2.2 bus/wing-root interface 或 deployed outer envelope；
- 改变 accepted B601 URDF、q、拓扑、轴、长度、质量或惯量；
- 改写七态名称或 SA-REQ-030 的 FAIL 侧级语义；
- 选定相机、铰链/轴承/弹簧/锁定器件或真实线束；
- 把本候选提升为飞行、发射、制造或环境试验合格状态。

本文件签发后，下一允许动作是：隔离旧错误三板候选，并按本文件重建 `MULTI_PANEL_SOLAR_ARRAY_CANDIDATE`；不得继续使用旧 RIGHT/FAIL 位姿表。
