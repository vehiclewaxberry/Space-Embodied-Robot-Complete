# MPI01_BRIDGE_DERIVATION_PLAN_V1（AGENT-1 / MPI-FB-01 / round0 handover / 01_frame_authority）

- 生成时间：2026-08-23（宿主机本地钟，Asia/Shanghai）
- 任务：按 ODR-43（B601_ARM_PLACEMENT_RULE: DUAL_FRAME_EXPLICIT_BRIDGE）给出唯一显式桥 `T_PHYSICAL_TO_DYNAMIC` 的推导与 MPI-FB-02..08 的执行计划。
- 术语：本文 MPI-FB-01..08 指**安装桥接工作包**（frame bridge），与 Route-C 的 minimum product inputs（MPI-01..08）同名不同义；Route-C 侧引用一律写 Route-C-MPI。
- 纪律：本文件一切数值均为 **NON-AUTHORITATIVE_PENDING_MPI-FB-02**（纯 python/numpy 核算，未冻结、未哈希钉入任何上游账本）；禁止二选一、按模块混用、取平均、把 0.36889° 当随机不确定度、静默替换坐标。桥在 MPI-FB-02 冻结并由 owner 确认前，任何下游消费均为 candidate。
- 输入（均已哈希复核，见 MPI01_FRAME_AUTHORITY_MATRIX.csv）：
  - 动力学轨 `T_S_A0_dyn`（= ODR-01 T_SM）：`E21_AUTHORITY_CONTRACT_V1.yaml:17-24`；`M7_OWNER_DECISION_REGISTER_V1.yaml:10-20`；`frame_tree_v1.yaml:10-19`；`DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml:61-70`。
  - 物理轨 `T_S_A0_phys`（= WP11_PHYSICAL_GEOMETRY_CONTEXT）：`E21_AUTHORITY_CONTRACT_V1.yaml:25-32`；`DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml:78-87`；`B601_CAD_URDF_GEOMETRY_CALIBRATION_V1.yaml:19-40`。

---

## (a) 桥的封闭形式推导与数值（MPI-FB-02 执行对象）

### a.1 记号
两个假设都是 `transform_S_A0`（A0=URDF base_link 坐标 → S 坐标）：`p_S = T_S_A0 · p_A0`。
- `T_S_A0_dyn = [R_d | t_d]`：`R_d = Ry(+90°) = [[0,0,1],[0,1,0],[-1,0,0]]`，`t_d = [0.18525, 0, 0] m`。
- `T_S_A0_phys = [R_p | t_p]`：`R_p = [[0,0,1],[s,c,0],[-c,s,0]]`（s=0.422618483193, c=0.906307683772），`t_p = [0.208, 0, 0] m`。

### a.2 结构分解（封闭形式）
直接验证（残差 5.0e-13）：`R_p = Rx_S(θ) · R_d`，`θ = 25.000014°`（即物理安装 = 动力学旋转后再绕星体 +X_S 钟摆 θ；与 M3R 实测 `clocking_about_spacecraft_x_deg: 25.000014` 一致）。

桥定义（按 ODR-43 与任务书）：

```
T_PHYSICAL_TO_DYNAMIC ≡ B = inv(T_S_A0_dyn) @ T_S_A0_phys
B = [ R_d^T R_p | R_d^T (t_p - t_d) ]
```

解析化简：
- `R_d^T R_p = R_d^T Rx_S(θ) R_d = Rot(R_d^T e_x, θ) = Rot(e_z_A0, θ)`（因为 `R_d^T e_x = Ry(−90°)·[1,0,0] = [0,0,1]`）——即桥旋转 = **绕动力学 A0 系 +z 轴 +θ**。
- `R_d^T (t_p − t_d) = Ry(−90°)·[0.02275,0,0] = [0,0,+0.02275]`——即桥平移 = **沿动力学 A0 系 +z（reach 方向）+22.75 mm**。

```
B = Trans(z_A0, +0.02275 m) · Rot(z_A0, +25.000014°)   （纯 z 螺旋，无 x/y 分量）
```

### a.3 数值（numpy 核算，NON-AUTHORITATIVE_PENDING_MPI-FB-02）
```
B = [[ 0.906307683772, -0.422618483193, 0.0, 0.0    ],
     [ 0.422618483193,  0.906307683772, 0.0, 0.0    ],
     [ 0.0,             0.0,            1.0, 0.02275],
     [ 0.0,             0.0,            0.0, 1.0    ]]
```
- det(R_B) = 1.0000000000005196（期望严格 +1：右手系保持，无镜像）
- 正交性 ‖R_BᵀR_B − I‖_max = 5.20e-13（双精度噪声级）
- 转角 25.000013999932°；转轴（A0-dyn 系）= [0,0,+1]（机器精度内）
- 四元数（wxyz）= [0.976295980677, 0, 0, 0.216439733215]
- 平移 t_B = [0, 0, 0.02275] m；逆桥 `inv(B) = Trans(z,−0.02275)·Rot(z,−25.000014°)`，往返残差 5.20e-13。

### a.4 语义方向（必须钉死，MPI-FB-02 裁决项）
- `B` 把**物理安装系表达的 A0 坐标**映射为**动力学约定下的 A0 坐标**：`p_A0dyn = B · p_A0phys`。
- 对**已在 S 系表达**的量（如 WP2 账本中按物理安装算出的臂 CG/惯量），重表达用 S 系共轭：
  `C_S = T_S_A0_dyn · inv(T_S_A0_phys) = Trans_S([−0.02275,0,0]) · Rot_S(x, −25.000014°)`，`p_S|dyn消费 = C_S · p_S|phys消费`。
- 端到端见证（本代理核算）：`C_S · (V2 账本 C01 臂 CG [0.376934164889081,−0.17567666955456437,−0.08674287405126006])` = e21 ODR01 车道计算值 `[0.3541841648890811,−0.1958762386983999,−0.004371637241445176]`，残差范数 **1.1314e-4 mm**——恰等于 e21 审计报告的 WP11 车道账本残差（0.00011314150166020904 mm），即残差全部来自 F3R2 位姿文件的**舍入钟摆拼写**（24.999981252° vs 25.000014°，WP11-F-03），不是桥结构误差。
- 惯量见证：`R(C_S) · I_ledger(C01臂) · R(C_S)ᵀ` 对 e21 ODR01 计算值最大绝对差 6.42e-8 kg·m²（e21 报告 7.03e-8，同源拼写差）。

### a.5 MPI-FB-02 必须裁决/钉死的事项
1. 桥常数取**全精度拼写** θ=25.000014°（M3R 实测、WP11/e21/M4 一致）；把账本 C01..C06 消费链中的舍入拼写登记为已知 1.1e-4 mm 级差异（WP11-F-03），**禁止**静默用桥输出覆盖账本。
2. 桥的存储格式与常量精度（建议：存 4x4 行主序 + 封闭形式参数 θ、t，双精度，sha256 钉入桥文件）。
3. M3R as-built datum（210.405 mm + yz 偏置 [0.015994151,−0.086366070] mm）**不在本桥内**；它是否/如何进入动力学系需另立裁决（当前仅 GEOMETRY 语义）。
4. `M3R_TSM_FRAME_TO_FLANGE_TRANSFORM.json` 的合成约定（平移按栈轴向书写）须在桥文档中显式禁止误读（见 FRAME_DEFINITIONS_DISCOVERED_V1.md §4.4）。
5. 桥文件 schema 建议：`MPIFB02_T_PHYSICAL_TO_DYNAMIC_V1.yaml`，含 B 与 inv(B)、封闭形式参数、两个源的 sha256、语义方向声明、nonclaims。

---

## (b) 往返验证计划（MPI-FB-03）

目的：证明 B 是良构刚体变换且方向语义正确。
1. **封闭性**：`inv(B) @ B = I` 到 ≤1e-12；`T_S_A0_dyn @ B == T_S_A0_phys` 到 ≤1e-12（逐元素 max-abs）。
2. **旋转合法**：det(R_B)=+1（容差 1e-12）；‖RᵀR−I‖_max ≤1e-12；手性保持（无反射）。
3. **位置残差**：取 A0 系一组测试点（原点、单位轴端点、URDF base_link CG [−7.849e-06,−1.1531e-06,0.029841] m），验证 `T_dyn·(B·p) == T_phys·p` 机器精度闭合。
4. **姿态残差**：`R_d·R_B == R_p`；转轴/转角与封闭形式一致。
5. **独立复算**：用与推导无关的第二实现（如直接 4x4 求逆 vs 封闭形式参数合成）互拍到 ≤1e-12。
6. **跨文件一致性**：B 作用于 `F3R2_ARM_INITIAL_POSE.yaml` mount 应落在全精度物理轨的 1.2e-4 mm 以内（拼写差已登记）；若超出则表明拼写裁决错误，MPI-FB-03 FAIL。
7. 负控制：把 B 的 θ 取反或平移取反，检测器必须能发现（变异测试）。

## (c) 质量/CG/惯量变换计划（MPI-FB-04）

记号：成员质量特性在源系给为 (m, r=CG, I=关于自身 CG 的惯量)。桥的 4x4 记 (R, p)。

1. **质量**：`m' = m`（标量不变；验证 |m'−m|=0）。
2. **CG**：`r' = R·r + p`。
3. **惯量（关于自身 CG）**：`I' = R·I·Rᵀ`（旋转部分作用；参考点随 CG 映射，无额外平移项）。
4. **参考点平移（关于新点 P' 的惯量）**：令 d =（新参考点 − 旧 CG）在目标系表达，则 `I_{P'} = R·I·Rᵀ + m·[(d·d)E − d⊗d]`。系统级再聚合时 d_member = (r'_member − r'_system)，逐成员平移后求和——这才是任务书所示扩展形的正确含义：**平行轴项必须先在目标系形成 d 再构造**，禁止把 `[(r·r)E − r⊗r]` 在源系构造后不与 R 共轭就直接相加。
5. **显式禁止**：禁止对惯量阵逐元素左乘/右乘旋转以外的任何"逐元素旋转"；禁止对**不确定度阵**做 R U Rᵀ（WP2-AUD-02 先例：V1 曾把标准不确定度矩阵分量式旋转产出负元，已被裁为无效对象）。不确定度传播用 WP2 V2 规则 P9 的精确诱导线性映射 `C_global = T(R) C_local T(R)ᵀ`（作用于 6 向量 [Ixx,Iyy,Izz,Ixy,Ixz,Iyz] 的协方差）。
6. **验证清单**（每成员、每构型）：
   - 对称性 ‖I'−I'ᵀ‖_max = 0（机器精度）；
   - SPD：最小特征值 > 0（记录数值）；
   - 主惯量不变：eig(I') 与 eig(I) 最大相对差 ≤1e-12（纯旋转下特征值不变）；
   - 迹不变：tr(I')=tr(I)（纯旋转；含平行轴项时检查 tr 增量 = 2m|d|²）；
   - 三角不等式（I'x+I'y≥I'z 等三式）；
   - 质量不变、CG 映射与独立 FK 复算一致（对 C01..C09 逐构型对拍 e21 审计已发布的两车道计算值，容差须大于已登记拼写差 1.2e-4 mm / 7.1e-8 kg·m²，或先完成 MPI-FB-02 拼写裁决后收紧到 1e-9 级）。
7. 对象范围：WP2 V3_R2 九构型的臂成员（`b601_complete_arm_including_gripper_urdf_links`）、M3R 成员（站点栈语义复核）、load bridge candidate；Solar R2 两翼为星体系安装、**不经此桥**（仅复核其 S 系表达在系统再聚合中不被桥污染）。

## (d) e21 单消费者重跑计划（MPI-FB-05）

前提：MPI-FB-02 桥已冻结并哈希钉入；ODR-43 指定 ODR-01 T_SM = DYNAMICS_FRAME_AUTHORITY。
1. 重跑 e21 的 M07/C07 刚性车道**一次**，消费语义 = ODR-01 T_SM；物理侧量（若有进入）只能经 B 桥进入。
2. 验收核心是**消费无歧义**，不是复现旧数：
   - `consumer_ambiguity_count = 0`（模型内每一处臂安装量都可追溯到唯一语义声明）；
   - **不得**以逼近 29.041965867604112° 或 29.41085537835705° 中任何一个为判据；这两个数是双轨各自消费的输出，不是真值锚点；
   - 允许的对拍：若重跑消费语义与 e21 ODR01 车道完全同构（账本 C07 臂行本就是 ODR01 消费），则初始质量特性应闭合到 e21 G10 已证的 0 / 4.44e-16 水平；任何桥接成员的引入用 MPI-FB-04 的变换结果替换，差异须由桥解析解释。
3. 保持不变式：动量守恒（dP/dL ≤1e-15 级）、能量审计 ≤1e-10 级、质量阵 SPD、四元数归一、Radau rtol=1e-10/atol=1e-12、独立零初值、无目标/接触/碰撞/全柔性消费。
4. 车道输出文件须以新 schema 名落盘（candidate），禁止覆盖 e21 既有结果。

## (e) 九构型质量传播（MPI-FB-06）与 V6/R3 候选重绑定（MPI-FB-07）

MPI-FB-06（质量传播，candidate 账本）：
1. 对 C01..C09 逐构型把臂成员统一到单一消费语义：C07..C09 臂行已是 ODR01 消费（e21 证残差 0）；C01..C06 臂行（物理轨消费）经 `C_S` 共轭重表达（CG 用 C_S 映射、关于自身 CG 的惯量用 R(C_S) 共轭、再按系统 CG 做平行轴再聚合）。
2. 同时重算系统 CG/惯量/主轴，输出 `SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2_BRIDGED_CANDIDATE`（candidate，禁止覆盖 V3_R2；ODR-44 冻结原文件）。
3. 每构型验证：质量不变（31.022864807342987 kg，C08 53.022864807342984，C09 181.02286480734298 不动——桥只动臂成员的**表达**，不动成员质量）；对称/SPD/主轴/三角不等式逐构型过；与 e21 已发布的两车道独立计算逐构型对拍并解释差异到拼写量级。
4. 太阳能翼、M3R、bridge、bus 成员不动（仅复核其 S 系语义未受桥污染）。
5. 不确定度：V3_R2 的 declared uncertainty 随候选账本逐项携带；桥本身不确定度 = null（桥是确定几何对象；as-built 实测相关的不确定度不在本轮发明）。

MPI-FB-07（V6/R3 候选重绑定）：
1. 生成 `MECH_DYNAMICS_INTERFACE` 的 candidate 下一版（V6 候选）与 wp13 合同候选（R3 候选），其中 frame_authority 段引用已冻结桥文件，`single_consumption_semantics` 字段置为桥接后语义。
2. **只生成 candidate**：文件名/路径必须含 CANDIDATE 字样，禁止写回/覆盖 R2 绑定（MECH_DYNAMICS_INTERFACE_V5_R2.yaml、EMBODIED_MECHANICAL_CONTRACT_R2.yaml 保持字节不动）。
3. 候选文件须携带：桥 sha256、源账本 sha256、九构型 candidate 账本 sha256、`not_release_not_production` 声明、全部既有 HOLD 的逐字携带。

## (f) MPI-FB-08 Gate 判据落法

建议判据（全部为 fail-closed；任一不过则维持 HOLD）：
1. 桥文件存在、sha256 自洽、两个源 transform 与 e21 权威合同逐位一致（非"file exists→PASS"：逐字段对拍数值）。
2. MPI-FB-03 往返/正交/行列式/手性全部 ≤1e-12；负控制变异全部被捕。
3. MPI-FB-04 全部验证清单通过；无逐元素旋转、无不确定度阵误用（扫描确认 T(R) 诱导映射实现）。
4. MPI-FB-05 重跑 `consumer_ambiguity_count == 0` 且全部数值不变式达标；输出未覆盖任何上游文件（目录级哈希扫描）。
5. MPI-FB-06 九构型 candidate 账本质量不变式逐构型为 0 差；与 e21 已发布值的全部差异均有拼写级解析解释。
6. MPI-FB-07 候选接口/合同文件存在且 R2 文件哈希未变。
7. 纪律扫描：无平均、无二选一、无模块混用、无 null→0、无把分支差当不确定度、无旧 24 kg / 旧 Solar R1 柔性模型的静默消费（对全部新文件做 grep/哈希审计）。
8. 全部强制 HOLD 逐字携带：e15 REPEAT_ANCF_CERTIFICATION、R2_HRN_04 FAIL_REDESIGN_REQUIRED、r2_full_flexible_coupling NOT_EVALUATED、collision/contact/target/mission/production/flight HOLD、owner_review PENDING。
9. Gate 输出：`MECHANICAL_LOOP` V5 重估所需的输入包（桥 + candidate 账本 + 候选接口 + 验证报告），`next_stage_authorized` 仍由 owner 裁决，本工作包不自授权；Route-C independent versioned CAD candidate 在 MPI-FB-01..08 全闭合前保持禁止（ODR-44）。

---

## 附：本轮已完成的 sanity 核算登记（NON-AUTHORITATIVE_PENDING_MPI-FB-02）

| 核算项 | 结果 | 说明 |
|---|---|---|
| R_p = Rx_S(25.000014°)·Ry(90°) | 残差 4.99e-13 | 物理轨旋转结构分解 |
| B = inv(T_dyn)·T_phys | Rot(z,+25.000014°) + Trans(z,+0.02275m) | det=1+5.2e-13，正交 5.2e-13 |
| inv(B)·B 往返 | 5.2e-13 | 机器精度 |
| C_S·(账本C01臂CG) vs e21 ODR01 计算 | 残差 1.1314e-4 mm | = e21 已发布账本残差，全部为拼写差 |
| R(C_S)·I·R(C_S)ᵀ vs e21 ODR01 惯量 | 最大差 6.42e-8 kg·m² | 同上，拼写级 |
| 迹不变 tr(I) | 0.363413527747167 → 0.363413527747293 | 差 1.3e-13 |
| 钟摆拼写比对 | 25.000014° / 24.999981252° / 24.999981252°(M5) / 25°整 | WP11-F-03 三种拼写数值化 |
| M3R flange JSON 合成约定 | 标准 T_M_child 合成错位 25.07 mm | 消费警告，见 FRAME_DEFINITIONS §4.4 |

核算环境：cpython（仓库脚本 3.11/3.13 线）+ numpy；未启动任何 CAD/FEA 进程；未写任何输出目录之外的文件。
