# ASM-03 / ASM-05：装配序列规划（九技能 FSM）与 VLA 协议装配特化 — 设计稿 v0 — 2026-07-20

> 状态：**DESIGN_DRAFT（预注册式设计，未实现、未采数、未训练）**。
> 只读依赖（本稿不改动它们）：
> `10_research/on_orbit_assembly/state_truth_and_scope.md`（技能词表九项已冻结，Gate AG-A0 PASS）、
> `10_research/on_orbit_assembly/interface_ssot_draft.yaml`（接口 SSOT v0，全字段 PROVISIONAL/LITERATURE）、
> `10_research/on_orbit_assembly/gate_registry.yaml`（AG0–AG6 注册表）、
> `10_research/vla/vla_generalization_plan.md`（捕获阶段 VLA 协议：分层 L1–L5、五词表、溯源三元组）、
> `10_research/vla/tool_contract_draft.yaml`（Physics Tool 合约 v0-draft：fail-closed、provenance 块）、
> `10_research/integration/system_interface_plan.md`（五层集成链与 T-Gate）。
> Gate 归属：本稿是 **AG6（ASM-05）** 的判据文档，并向 **AG1/AG3（ASM-02）**、
> **AG5（SAFE-00 扩展）** 输出序列语义需求；不推翻任何已 PASS 裁决。
> 铁律继承（gate_registry `iron_rules_inherited` 全量适用）：VLA 禁力矩、禁改阈值、
> 禁跳 SAFE-00、UNKNOWN 永不转执行/成功、AprilTag 只称合作标记替身、
> 测试 PASS ≠ 科学 Gate PASS、负结果原样保留。

---

## 0. 定位与研究问题

**ASM-03（装配序列规划）**：把冻结的九技能词表组织成一台**确定性规则 FSM**，
每条转移的守卫由"本地判据 + Physics Tool 查询 + SAFE-00 扩展裁决"构成。
**第一版不含任何学习成分**——它既是系统的可用基线，也是 VLA 消融的对照物（§4 的 V1/V2.5）。

**ASM-05（VLA 协议装配特化）**：把捕获阶段 VLA 协议（`vla_generalization_plan.md`）
特化到装配任务。VLA 的活动空间仅限六项（§3.1），核心可证伪问题一句话：

> **在同一套 Physics Tools 与同一 Safety Gate 下，VLA 生成的装配步骤/技能选择
> 是否在"未见接口、异常事件顺序、任务中断恢复"三轴上优于确定性规则 FSM（V3 vs V2.5）；
> 若不优于，则如实记录"VLA 在本协议下无序列化增益"的负结果。**

不回答的问题（非目标）：VLA 能否控制机械臂（禁止）、端到端装配成功率
（低层控制闭环属 ASM-02/CTRL 线）、真实在轨性能（无飞行数据）、
大桁架装配（state_truth 已排除，后续扩展）。

---

## 1. ASM-03：九技能 FSM 状态机草图

### 1.1 状态集合

九个技能态（词表冻结，不增不减不改名）+ 三个元状态：

- 技能态：`OBSERVE / GRASP_MODULE / MOVE_TO_PREASSEMBLY / APPROACH_5D / ALIGN /
  COMPLIANT_INSERT / LOCK_6D / VERIFY_ASSEMBLY / RETREAT`
- 元状态：`SAFE_HOLD`（WAIT 落点，物理安全悬停位形）、
  `ASSEMBLY_SUCCESS`（八项判据全满足，接口 SSOT `assembly_success_criteria`）、
  `ABORTED`（模块保持受控持有或已安全归位，任务放弃）

### 1.2 名义主链与失败边（草图）

```
            ┌──────────────────────────── REOBSERVE（任何态感知过期/协方差超阈）──────────────┐
            ▼                                                                                │
  START → OBSERVE → GRASP_MODULE → MOVE_TO_PREASSEMBLY → APPROACH_5D → ALIGN ─→ COMPLIANT_INSERT
            ▲              │                ▲    │            ▲   │        ▲│           │
            │              │f1              │    │            │   │f3      ││f4         │f5
            │              ▼                │    ▼            │   ▼        │▼           ▼
            │           ABORTED             │ SAFE_HOLD ◄──(WAIT：D5 柔性未衰减 / D6 轮组近饱和)
            │                               │ (超时→ABORT)                              │
            │        CHANGE_CONFIG（换接近走廊，≤1 次）─────────┘                        │
            │                                                                           ▼
            └── VERIFY_ASSEMBLY ◄─────────────────────────────────────────────── LOCK_6D
                     │      │f7                                                    │f6
                     │      ▼                                                      ▼
                     │   SAFE_HOLD(+人工复核)                            (latch FAULT→RETREAT→ABORTED)
                     ▼
                  RETREAT → ASSEMBLY_SUCCESS
```

失败边定义（v1 确定性规则；重试预算见 §2 D4）：

| 边 | 触发 | 去向 |
|---|---|---|
| f1 | GRASP_MODULE 硬约束不过（sim_09 口径）或抓取验证失败 ×2 | ABORT（模块留存储位，本质安全） |
| f2 | MOVE_TO_PREASSEMBLY 走廊侵犯/基座扰动预测超限 | 退回 OBSERVE 重规划；×2 后 CHANGE_CONFIG |
| f3 | APPROACH_5D 走廊偏差超粗容差（±5 mm/±5°，SSOT LITERATURE 值） | 退回 MOVE_TO_PREASSEMBLY；×2 后 CHANGE_CONFIG；再失败 ABORT |
| f4 | ALIGN 超时或精容差（0.1 mm/0.5°）不可达 | REOBSERVE→重试 ALIGN；偏差回到粗容差外→退回 APPROACH_5D |
| f5 | COMPLIANT_INSERT 接触载荷超限或插入深度停滞（卡阻） | 立即停进给→沿插入轴退至预插入路标→回 ALIGN；×2 后 CHANGE_CONFIG |
| f6 | LOCK_6D 后 `verify_latch_state` 返回 OPEN | 重锁 ×1；返回 FAULT → RETREAT（持模块）→ ABORTED |
| f7 | VERIFY_ASSEMBLY 八项任一不满足且 latch 已 LOCKED | **不自主解锁**：SAFE_HOLD + 人工复核（fail-closed，解锁不可逆性未建模） |

### 1.3 决策叠加层（五词表 → FSM 语义映射）

L4 决策词表沿用捕获协议五词（`WAIT / REOBSERVE / CHANGE_CONFIG / ABORT /
EXECUTE_UNDER_ASSUMPTIONS`），在 FSM 上的落点唯一化：

| 决策 | FSM 语义 |
|---|---|
| WAIT | 转 SAFE_HOLD（保持当前安全位形），带超时；超时未解除 → 升级 ABORT |
| REOBSERVE | 转 OBSERVE（感知支路重采），返回原技能态入口重新裁决 |
| CHANGE_CONFIG | 退回 MOVE_TO_PREASSEMBLY 并切换备选接近走廊（v1 仅 1 条备选） |
| ABORT | 经 RETREAT 安全退出 → ABORTED（模块受控持有或归位） |
| EXECUTE_UNDER_ASSUMPTIONS | 允许进入下一技能态，assumptions 必含 `flex_status=UNKNOWN_NOT_IN_CRITERIA` 等现行占位限定 |

**每一次技能态切换 = 一次相位切换 = SAFE-00 扩展重新裁决**（AG5 硬条款
"相位切换=重新裁决"）。装配新增 reason_code 走 SAFE-00 **新增面**，
不改已 PASS 的 47/47 裁决核（state_truth "扩装配 reason_code 属新增不改核"）。

### 1.4 CTRL-01 负结果作为相位语义的证据基础（引用限定语必带）

- **APPROACH_5D 段**：5D 任务（3 平移 + 2 姿态，绕插入轴 clocking 自由）——
  CTRL-01 证明**只有 5D 段存在 1 维零空间**可用于避奇异/避限位；
- **LOCK_6D 段**：严格 6D 任务零空间为 0——CTRL-01 允许 LOCK 段短程 6D，
  但**禁止把整个装配当单一 6D 任务**（冻结增益闭环锚超差的负结果即此证据，
  引用须带"冻结增益与预注册轨迹下"限定）；
- 因此 FSM 的 5D→6D 相位切换（§2 D3）不是工程便利，而是**由 CTRL-01
  预注册负结果强制的结构**。此语义的机器校验归 AG1（ASM-02 owner），本稿只消费。

---

## 2. 序列决策问题清单（六项，v1 = 确定性规则 + 工具查询）

每项给出：决策变量 / v1 规则 / 依赖的 Physics Tool（现有或 §6 PLANNED）/ 证据源 / 遗留问题。

### D1 接近方向选择
- 变量：接近走廊（离散候选集，由接口 SSOT `interface_mount_frame` +Z 外法向锥 ±
  偏置生成，v1 候选数 ≤3）。
- v1 规则：在满足 (a) 帆板扫掠体积零交叠 (b) 走廊全程与碰撞几何间隙 ≥ 下限的候选中，
  选**预测基座姿态扰动峰值最小**者；并列取间隙最大者。
- 工具：`plan_assembly_approach`（PLANNED，§6.1）；扰动预测数据面 = ASM-02 未来
  扫掠工件（sim_05 19.20° 量级方法学同源）。
- 遗留：扰动预测在双漂浮情形的口径（服务星+目标星各自基座）由 ASM-02 定义。

### D2 先对准哪个轴
- 变量：ALIGN 段内的对准次序。
- v1 规则：**公差从粗到细**——平移粗对准（锥捕获域 ±5 mm）→ 锥面接触被动收敛承担
  剩余平移 → 角粗对准（±5°）→ 销孔 clocking（绕插入轴转角）**最后**。
- 物理依据：锥面半角 15°/深 8 mm（SSOT LITERATURE）在粗容差内提供被动机械收敛；
  clocking 自由度保留到最后 = APPROACH_5D 段维持 1 维零空间（CTRL-01，§1.4）。
- 工具：`predict_contact_load`（PLANNED）校验锥面首触载荷在限内。
- 遗留：双销的 clocking 二义性（180° 对称）需接口 SSOT 增加防呆特征字段（提请 ASM-00）。

### D3 5D→6D 切换时机
- 变量：ALIGN → COMPLIANT_INSERT/LOCK_6D 的准入时刻。
- v1 规则（五条件与门，任一不满足 → WAIT/REOBSERVE）：
  1. 位置误差 ≤ 精平移容差 0.1 mm × k_s（安全系数 k_s 待 PI 批准，入 registry）；
  2. 角误差 ≤ 精角容差 0.5° × k_s；
  3. 位姿协方差迹 ≤ registry 阈值（超阈 → REOBSERVE 而非 WAIT，沿用捕获协议）；
  4. D5 柔性等待判据满足；
  5. D6 轮组余量判据满足。
- 切换本身触发 SAFE-00 重新裁决（AG5）；切换后进入的 6D 段长度最短化
  （只覆盖 COMPLIANT_INSERT 末段 + LOCK_6D）。
- 遗留：k_s 与协方差阈值数值**不得在本稿冻结**（阈值出处纪律，AG 注册表首行）。

### D4 失败后重试 / 退出 / 换构型
- 变量：每技能态失败后的升级路径。
- v1 规则（升级阶梯，预算写死防振荡）：
  `本地重试(≤2) → REOBSERVE → 退回上一稳定态 → CHANGE_CONFIG(≤1 条备选走廊) → ABORT`。
- 附加硬规则：接触载荷超限后的任何重试**必须**先 `verify_latch_state` + OBSERVE
  确认接口未受损/未半锁；latch=FAULT 一律不重试直接 ABORT；
  VERIFY 失败且已 LOCKED 不自主解锁（f7）。
- 遗留：重试预算 2/1 为 PROVISIONAL 工程常数，消融实验（§4）中对五组统一冻结。

### D5 柔性未衰减时的等待判据
- 变量：接触/锁定激振后允许进入下一精对准/插入动作的等待时长。
- v1 规则：查询 `predict_ringing_window`（PLANNED，§6.4）——预测帆板端部振幅衰减至
  ≤ 精容差量级的分数 η（η 待定入 registry）才放行；**查询域外或帆板参数为占位时
  返回 UNKNOWN → 强制 WAIT**，WAIT 超时 → ABORT（UNKNOWN 永不 ALLOW，SAFE-00 硬条款）。
- 证据尺度（只作量级锚，不作阈值）：sim_07 点捕获激振振铃 37–75 s；
  sim_11 A2 帆板振铃 ~2.1 mm @ 1.0005 Hz——两者均带**帆板模态参数占位**限定
  （待办 3：真实面密度差 5–10 倍，结论可能翻转）。
- 遗留：装配激振工况（锥面接触、锁扣冲击）的振铃数据面 = ASM-01 未来工件；
  AG4（e15 5% 口径）过门前，本判据整体标 PROVISIONAL。

### D6 轮组近饱和暂停判据
- 变量：下一技能动作执行前的轮组动量预算准入。
- v1 规则：查询 `check_assembly_resources`（PLANNED，§6.5）——按 CTRL-02 分账账本
  预测"当前 |H_wheel| + 下一技能动作预计增量"≥ β × 轮组容量（β=0.8 PROVISIONAL）
  → WAIT（暂停于 SAFE_HOLD）；动量卸载是否/何时执行属 CTRL-02 分账语义，
  **本 FSM 只暂停不指挥卸载**。
- 已知接口级阻塞候选：**W1-R12 轮力矩 0.033 > 0.01 PROVISIONAL 冲突**必须先在
  ASM-02 显式解决（state_truth 原文），轮组选型冻结前本判据阈值不得转正；
  W1-R12/R13 为硬件触发重跑项。
- 遗留：装配全程的分账预算切分（接近段 vs 锁定段）由 ASM-02/CTRL-02 扩展定义。

---

## 3. ASM-05：VLA 协议装配特化

### 3.1 VLA 活动空间（六项白名单，其余一律禁止)

继承捕获协议 L1–L5 分层（`vla_generalization_plan.md` §1）：L1/L2 感知支路与
L5 控制不变，VLA 仅在 L3/L4 活动。装配特化后 VLA **只承担**：

1. **接口/模块识别**：图像 → {geometry/interface 类别候选 + 置信度}（输出是观测标注，
   不是指令；不得计入 L2 位姿估计指标）；
2. **语义抓点**：模块抓取面候选集（schema 与捕获协议 §3 L3 一致，sim_09 口径评判）；
3. **装配步骤理解**：任务文本/图示 → 九技能词表内的**步骤序列提案**（词表外技能名
   一律判非法）；
4. **技能选择**：当前状态 + 工具返回 → 下一技能态 + 五词表决策提案；
5. **工具调用**：按 `tool_contract_draft.yaml` + §6 扩展面发起查询（参数越界/伪造
   字段计入非法调用率）；
6. **异常语义**：把感知/遥测异常翻译为词表内的失败边触发提案（如"销未入孔"→ f4）。

**四禁（红线，违反即该 run 判非法）**：禁输出力矩/关节量/轨迹（禁力矩）、
禁请求或暗示放宽任何阈值（禁改阈值）、禁绕过 SAFE-00 直接触发技能切换（禁跳 SAFE-00）、
禁在任何 UNKNOWN 字段上给出执行/成功语义（禁 UNKNOWN→执行）。
全部继承捕获协议 §6 溯源三元组条款：每个 EXECUTE_UNDER_ASSUMPTIONS 必须携带
`{gate_json_path, registry_sha256, scenario_hash}`，缺失 → Safety Gate 强制 ABORT。

### 3.2 五组对照（装配基线族，前缀 ASM- 以区隔捕获阶段 V0–V3）

五组共用：同一 L1/L2 前端、同一 SAFE-00 扩展 Safety Gate（全组在场兜底）、
同一场景与随机种子、同一重试预算（§2 D4）。**唯一变量 = 序列来源 × 工具接入**。

| 组 | 序列/技能选择来源 | Physics Tools | 回答的问题 |
|---|---|---|---|
| **ASM-V0 固定脚本** | 名义场景硬编码九技能顺序 + 定点参数（无在线决策） | 无（参数离线人工代入） | 名义下限锚；任何偏差场景**应当**失败——校验实验难度非平凡 |
| **ASM-V1 规则 FSM** | §1–2 的 FSM，守卫仅用本地阈值/感知量（无工具在线查询） | 无 | 不接物理证据的规则系统能到哪；暴露"规则但无接地"的失败模式 |
| **ASM-V2 VLA 步骤生成** | VLA 直接生成步骤序列与技能选择（无工具可调） | 无 | 裸 VLA 序列化的增益与危险暴露（幻觉步骤、非法转移）——Gate 前指标主来源 |
| **ASM-V2.5 FSM+工具** | 同 V1 的 FSM，守卫接入全套工具查询（= ASM-03 完整体） | 全套（合约五工具 + §6 扩展） | **强对照**：确定性规则在同等物理接地下的天花板 |
| **ASM-V3 VLA+工具** | VLA 步骤/技能选择 + 同一套工具 + 同一 Gate | 全套（与 V2.5 逐一相同） | 本研究主张的完整体；**AG6 主对比 = V3 vs V2.5** |

消融逻辑：V2−V1 = 裸 VLA 序列化差量（预期含危险暴露）；V2.5−V1 = 工具接地
对规则系统的增益；**V3−V2.5 = 在同等工具与 Gate 下 VLA 的净序列化增益——
这是唯一被允许写进论文主张的 VLA 价值项**（AG6 硬条款"V2.5 对照在场、V3 差异归因"）。

### 3.3 核心可证伪问题的三条主张轴

预注册主张：V3 仅在以下三轴上**可能**优于 V2.5，且每轴独立成行报告：

1. **未见接口几何**（§5 轴 A）：FSM 守卫参数是按 SSOT 接口写死的，VLA 可能从语义
   泛化到变体接口；
2. **异常事件顺序**：注入 FSM 失败边**未编码**的事件序（如 ALIGN 完成后 latch 传感器
   先报 ENGAGED 再回 OPEN、插入中途感知丢帧+接触载荷阶跃同时发生）——FSM 按
   fail-closed 退化为 ABORT（正确但保守），VLA 能否给出**同样安全但更少放弃**的恢复路径；
3. **任务中断恢复**：从任意中间技能态冷启动（模块半插入、latch=ENGAGED 未 LOCKED），
   FSM 需人工指定入口态，VLA 能否从观测正确识别续接点。

预注册对称条款：若三轴上 V3 均不优于 V2.5（配对差不显著或为负），结论如实写为
"**在本协议约束下 VLA 无序列化增益，规则 FSM + 物理工具已充分**"——负结果原样入档，
不得以调阈值/换指标挽救（铁律"禁改阈值制造 PASS、禁删 FAIL"）。

---

## 4. 装配泛化留出轴（按组留出，组内不跨 train/test）

沿用捕获协议 §4 的 group held-out 纪律；装配特有四轴（与捕获 G-A…G-G 独立命名）：

| 轴 | 见过组（提示/开发可含） | 留出组（仅测试） | 专测问题 |
|---|---|---|---|
| AH-A 接口几何 | SSOT 锥+双销接口（名义参数） | 锥半角/销径/间隙变体、三销构型、方形导向套 | VLA 语义识别 vs FSM 写死参数；D2 对准次序是否迁移 |
| AH-B 模块外形 | 1U 名义模块 | 2U 变体、带突出物（连接器/把手）、表面贴装变化 | 语义抓点与走廊规划的外形泛化 |
| AH-C 锁扣异常态 | latch 名义序列 OPEN→ENGAGED→LOCKED | 卡半程（ENGAGED 停滞）、假 LOCKED（几何未达位）、FAULT 抖动 | 异常语义翻译正确率；**假 LOCKED 是 VERIFY 八项判据的专门考题** |
| AH-D 遮挡 | 无/轻遮挡 | 臂自遮挡 >40%、接口近距离视野丢失（插入末段必然发生） | 近距失明段是否正确转 REOBSERVE/依赖递推而非幻觉位姿 |

纪律：每轴独立成行，禁止混合平均掩盖单轴崩溃；AH-C/AH-D 的留出组场景参数
入 scenario_hash；**AprilTag/合作标记若用于实验室模块定位，只能标注
`perception_branch=L1_marker`，其结果不得进入本表任何行**（AG6 硬条款）。

---

## 5. 指标（预注册，分母写死；命名 AM-x 以区隔捕获协议 M1–M8）

| # | 指标 | 定义 | 主归属 |
|---|---|---|---|
| AM1 | 序列合法率 | 提案的技能转移落在 FSM 合法边集内、技能名在九词表内的比例（V2/V3 专项；V0/V1/V2.5 恒 1 作校验） | 步骤理解 |
| AM2 | 非法工具调用率 | 参数越界/伪造 provenance/阈值覆盖字段/调不存在工具 的占比（fail-closed 拒绝并计数） | 工具调用 |
| AM3 | 错误推进率 | 决策=EXECUTE 但物理真值（ASM-01/02 未来工件判据）为不可行/超载 的比例——**Gate 前/Gate 后两个数，Gate 后必须为 0**（非 0 = Gate 实现 bug） | 安全 |
| AM4 | 装配成功率 | 八项判据（接口 SSOT）全满足的 run 占比；任一 UNKNOWN 不判 success | 任务 |
| AM5 | 异常恢复率 | 注入异常集（§3.3 轴 2/3）下"安全且完成"与"安全但放弃(ABORT)"分列报告 | 恢复 |
| AM6 | 泛化下降幅度 | 每留出轴 (见过组 − 留出组)，对 AM1–AM5 逐项 | 泛化 |
| AM7 | 保守性开销 | 步数、WAIT 总时长、REOBSERVE 次数（安全指标的代价面，防"全 ABORT 刷 AM3=0"） | 系统 |

真值源诚实声明：AM3/AM4 的物理真值依赖 **ASM-01（接触/柔性数据面）与
ASM-02（运动学/控制数据面）未来工件**——本稿只冻结指标定义与分母口径，
**不虚构真值数据存在**；两者未交付前，五组对照只能在"几何/流程真值"子集上先行
（AM1/AM2/AM7 + AM4 的几何子项）。

---

## 6. Physics Tools 装配扩展面（全部 PLANNED，I/O 草案）

纪律：全部继承 `tool_contract_draft.yaml` 的 `common.provenance_block`（响应必带
gate_json_path/registry_sha256/scenario_hash/data_row_refs）与 `error_semantics`
（域外 REFUSE_OUT_OF_DOMAIN、阈值覆盖 REFUSE_ILLEGAL_CALL、哈希漂移
REFUSE_STALE_ARTIFACT）；工具只吃**现成机器裁决工件**，不在线新算物理；
数据源指向 ASM-01/02 未来工件处一律标 `data_source_status: PLANNED_NOT_EXIST`——
**工件不存在时工具必须拒绝服务，不得返回猜测值**。

### 6.1 `plan_assembly_approach`（D1/D4 消费）
```yaml
status: PLANNED
intent: 在冻结的接近走廊扫掠库上查询候选走廊的可行性与基座扰动预测，返回排序而非轨迹
data_source: ASM-02 走廊扫掠 CSV + 基座扰动预测表   # PLANNED_NOT_EXIST
input:
  required: [interface_pose_hat, pose_covariance_trace, module_in_gripper,
             corridor_candidates, scenario_hash]
  # interface_pose_hat: L2 输出的接口装配框位姿±σ；corridor_candidates: 离散走廊 id 列表
output:
  required: [ranked_corridors, provenance]
  ranked_corridors[]:
    {corridor_id, clearance_min_m, panel_sweep_overlap: boolean,
     predicted_base_disturbance_deg,      # sim_05 方法学同源，双漂浮口径由 ASM-02 定义
     feasibility: FEASIBLE|INFEASIBLE|UNKNOWN}
hard_rules: [域外/工件缺失 → 拒绝, 不输出关节/笛卡尔轨迹（排序≠轨迹）]
```

### 6.2 `predict_contact_load`（D2/f5 消费）
```yaml
status: PLANNED
intent: 在 ASM-01 接触参数扫掠网格上查询给定相对位姿误差/插入深度下的峰值接触载荷
data_source: ASM-01 KV 接触扫掠（k_n∈[1e4,1e6] N/m 等，接口 SSOT 扫掠计划）  # PLANNED_NOT_EXIST
input:
  required: [pose_error, insertion_depth_mm, contact_param_set_id, scenario_hash]
  # contact_param_set_id 只允许引用冻结扫掠网格点；连续值由客户端声明最近网格
output:
  required: [peak_force_N, peak_moment_Nm, within_limit: boolean,
             excitation_energy_ref,        # 供 6.4 振铃预测引用的激振量标识
             provenance]
hard_rules: [网格外禁止外推 → UNKNOWN, 未收敛接触工况在源头即不得入库（AG2 条款）,
             within_limit 阈值只从 registry 装载]
```

### 6.3 `verify_latch_state`（f6/f7/VERIFY 消费）
```yaml
status: PLANNED
intent: 汇聚锁扣状态机仿真态（后期为硬件遥测）与插入遥测，输出锁扣状态判定
data_source: ASM-01 锁扣状态机仿真 + 插入深度/载荷遥测   # PLANNED_NOT_EXIST；硬件版挂 H 链
input:
  required: [latch_sensor_state, insertion_depth_mm, load_signature, scenario_hash]
output:
  required: [latch_state: OPEN|ENGAGED|LOCKED|FAULT|UNKNOWN,
             geometry_consistent: boolean,   # 假 LOCKED 检出：传感器态 vs 几何达位交叉验证
             provenance]
hard_rules: [传感器态与几何证据冲突 → UNKNOWN（不猜）, UNKNOWN 不得被上游转译为 LOCKED,
             power/data 状态位只在 latch_state=LOCKED 且 geometry_consistent 时置位（SSOT 语义）]
```

### 6.4 `predict_ringing_window`（D5 消费）
```yaml
status: PLANNED
intent: 在认证包络内查询一次激振事件后帆板振幅衰减到目标分数所需等待时长
data_source: sim_07/sim_11 既有振铃数据（占位参数限定原样透传）+ ASM-01 装配激振工况库
             # ASM-01 部分 PLANNED_NOT_EXIST；sim_07/sim_11 部分只作量级锚
input:
  required: [excitation_energy_ref, target_amplitude_fraction, scenario_hash]
output:
  required: [t_wait_s | UNKNOWN, envelope_status: IN_ENVELOPE|OUT_OF_ENVELOPE,
             provisional_flags,             # 必含 帆板参数占位（待办3）直至参数卡转正+AG4 过门
             provenance]
hard_rules: [OUT_OF_ENVELOPE 或参数占位未认证 → t_wait=UNKNOWN → 客户端只能 WAIT/ABORT,
             e15 REPEAT 条款生效期间柔性数值引用受限（沿用合约 flex 条款）]
```

### 6.5 `check_assembly_resources`（D6 消费）
```yaml
status: PLANNED
intent: check_resources 的装配扩展——按 CTRL-02 分账账本查询下一技能动作的轮组/推进剂余量
data_source: CTRL-02 分账账本口径 + 轮组档 registry + ASM-02 技能动作动量增量表  # 增量表 PLANNED_NOT_EXIST
input:
  required: [tier, current_H_wheel_Nms, next_skill, scenario_hash]
output:
  required: [predicted_H_after_Nms, margin_fraction, pause_advised: boolean,
             blocking_flags,                # W1-R12 冲突未解决期间必含 WHEEL_TORQUE_PROVISIONAL_CONFLICT
             provenance]
hard_rules: [轮组选型未冻结（W1-R12）期间 pause 阈值 β 标 PROVISIONAL 且不得转正,
             本工具不指挥动量卸载（CTRL-02 职权），只给暂停建议]
```

**SAFE-00 对接**：五个扩展工具的拒绝/UNKNOWN 语义各自映射为新增装配 reason_code
（如 `ASM_CONTACT_OOD`、`ASM_LATCH_UNKNOWN`、`ASM_FLEX_WAIT`、`ASM_WHEEL_MARGIN`），
全部走 SAFE-00 扩展面新增，**不触碰已 PASS 的裁决核**（AG5 硬条款）。

---

## 7. Gate AG6 消融判据（V3 vs V2.5 差异归因，预注册）

AG6 注册表硬条款展开为机器可检断言：

1. **V2.5 对照在场**：任何 V3 结果行必须存在同 scenario_hash、同种子、同工具版本、
   同 Gate 版本的 V2.5 配对行；孤行 V3 结果一律无效（机器校验配对完整性）。
2. **配对归因协议**：V3 与 V2.5 的每个差异 run 必须归因到三类之一，机器可分：
   - `SEQ_DIFF`：技能序列不同（步骤级 diff 非空）→ 唯一允许计入"VLA 序列化增益"；
   - `TOOL_TRACE_DIFF`：序列相同但工具调用参数/次序不同 → 计入"查询策略差异"，
     单列报告，不得并入序列化增益；
   - `NONDETERMINISM`：序列与工具迹均相同而结果不同 → 判实验实现 bug，该对作废重跑。
3. **主对比统计**：三条主张轴（§3.3）各自做配对二项检验（同场景 V3 胜/负/平），
   显著性水平预注册（数值待 PI 批准入 registry，不在本稿冻结）；**禁止事后新增主张轴**。
4. **安全底线断言**：五组的 AM3(Gate 后) 全部 = 0；V3 的任何"胜"若伴随 AM2 或
   AM1 违规，该 run 判负不判胜（安全违规不可被任务成功抵扣）。
5. **保守性对照**：报告 AM7——若 V3 的胜来自更高 WAIT/REOBSERVE 开销，须如实
   写入"增益的代价面"；若 V2.5 以全 ABORT 达成 AM3=0，AM5 的"安全但放弃"列
  会将其暴露，防止保守性伪装成安全性。
6. **表述红线**：AprilTag 只称合作标记替身；固定基座演示不称微重力验证；
   泛化声明只允许引用 §4 留出轴行；负结果（V3 不优）原样入档。
- 裁决出口：`10_research/on_orbit_assembly/results/ag6_gate_check.json`（未来），
  verdict 命名建议 `AG6_ABLATION_PASS / AG6_NO_VLA_GAIN(负结果同样是合法收口) /
  AG6_INVALID_PAIRING`。测试 PASS ≠ 科学 Gate PASS 继续适用。

---

## 8. Task Cards

### Task Card ASM-03：装配序列规划（九技能 FSM v1）
- **目标**：实现 §1–2 的确定性 FSM（= ASM-V1/V2.5 两种配置），含五词表决策叠加层
  与 SAFE-00 扩展对接；不含学习。
- **输入（冻结依赖）**：技能词表九项（state_truth，不得增删改名）；接口 SSOT v0
  （PROVISIONAL 字段限定随答案透传）；CTRL-01 负结果（5D/6D 相位语义证据，引用带
  "冻结增益与预注册轨迹下"限定）；CTRL-02 分账口径；`tool_contract_draft.yaml`
  common 块；本稿 §6 扩展工具草案。
- **产出物**：FSM 实现 + 转移守卫表（机器可读 YAML）+ 负例测试集（非法转移/
  UNKNOWN 推进/阈值覆盖注入全部被拒）+ 对 AG1/AG5 的语义需求清单。
- **Gate**：喂 AG1（相位语义机器校验，owner ASM-02）与 AG5（相位切换=重新裁决）；
  自身验收 = 负例测试全过 + 五词表落点唯一性机器校验。
- **预注册断言**：FSM 在名义场景走通主链；每条失败边有至少一个注入用例触发；
  UNKNOWN 输入下不存在任何通向"推进/成功"的路径（穷举检查）。
- **阻塞/外部依赖**：D5 真值面（ASM-01）、D6 阈值转正（W1-R12 轮组选型冻结）、
  k_s/η/β 数值需 PI 批准入 registry——**未批前全部 PROVISIONAL，不得冻结在代码里**。
- **明确不做**：低层控制（ASM-02/CTRL 线）、接触物理新算（ASM-01）、任何学习组件。

### Task Card ASM-05：VLA 协议装配特化与消融
- **目标**：实现 §3 的 VLA 六项白名单接入（提示工程 + 工具接口 + 评测，不训练模型），
  跑通五组对照（§3.2）× 四留出轴（§4）× AM1–AM7（§5），出 AG6 裁决。
- **输入（冻结依赖）**：捕获阶段 VLA 协议全部红线（§6.1–6.3 原文适用：五词表、
  溯源三元组、AprilTag 表述红线、禁 RL/端到端/力矩）；ASM-03 交付的 FSM
  （V1/V2.5 对照物）；§6 扩展工具（V2.5/V3 共用同版本）；SAFE-00 扩展 Gate。
- **产出物**：`asm_vla_eval_results.csv`（配对 schema，V3 行强制携带 V2.5 配对键）+
  `ag6_gate_check.json` + 主图两张（V3−V2.5 三主张轴配对图、逐留出轴泛化下降图）。
- **Gate**：AG6（本稿 §7 为其判据文档）；依赖 AG0–AG5 的相应 owner 交付。
- **预注册断言**：AM3(Gate 后)=0 五组全部成立；V3 主张仅允许来自 `SEQ_DIFF` 归因；
  三主张轴均不显著时收口为 `AG6_NO_VLA_GAIN` 负结果。
- **阻塞/外部依赖**：ASM-01/02 数据面（AM3/AM4 物理真值）；渲染/域随机化管线
  （捕获协议同项，NOT_STARTED）；词表统一回改（捕获协议 §6.2 对
  `.codex/agents/physics-agent-architect.md` 的单一词表要求，实施前完成）。
- **明确不做**：VLA 微调/RL（另立协议过审）；用 L1 标记支路结果支撑泛化声明；
  在 ASM-01/02 工件缺位时虚构 AM3/AM4 真值。

---

## 9. 依赖与阻塞（诚实清单）

| 依赖 | 状态 | 影响 |
|---|---|---|
| ASM-01 接触/柔性/锁扣数据面 | NOT_STARTED | §6.2/6.3/6.4 工具与 AM3/AM4 真值；缺位时工具拒绝服务 |
| ASM-02 走廊扫掠/相位校验/动量增量表 | NOT_STARTED | §6.1/6.5 工具、AG1 校验、W1-R12 冲突解决（接口级阻塞候选） |
| 接口实测公差/刚度/锁紧力 | 无实测（SSOT 全 PROVISIONAL/LITERATURE） | 转正触发 rerun（SSOT rerun_triggers 已登记） |
| 帆板参数卡（杨恒，待办 3） | BLOCKED_BY_EXTERNAL_INPUT | D5 判据转正与 AG4；现行结论可能翻转的最大硬伤 |
| B601 夹爪 T_c / 执行器实测（待办 2，W1-R12/R13） | BLOCKED_BY_EXTERNAL_INPUT | D6 阈值转正、硬件触发重跑 |
| 阈值数值（k_s/η/β/显著性水平） | 待 PI 批准入 registry | 本稿一律不冻结数值（AG 注册表首行纪律） |
| 词表统一回改（agent 卡） | 未完成（捕获协议 §6.2 条款） | ASM-05 实施前置 |
