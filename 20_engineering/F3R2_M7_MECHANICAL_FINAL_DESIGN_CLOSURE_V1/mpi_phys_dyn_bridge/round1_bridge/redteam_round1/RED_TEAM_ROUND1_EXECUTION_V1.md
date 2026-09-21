# RED_TEAM_ROUND1_EXECUTION_V1 — 红队第一轮攻击执行报告（AGENT-4 / round1_bridge / redteam_round1）

- 生成时间：2026-08-23T17:40+08:00（宿主机本地钟）
- 攻击计划依据：`round0_handover/04_red_team/RED_TEAM_ATTACK_PLAN_V1.md` §3（逐项清单）+ §2（Falsifier 协议）
- 纪律：全程只读上游；纯 Python 3.13.9 + numpy 2.3.5 + hashlib；未启动任何 CAD/FEA 进程；git 未使用；写入仅限本目录
- 复算包：本目录 `round1_verify.py` + 原始输出 `round1_verify_output.json`（一切数字可重跑复核）
- 判定词表：攻击面 `SAFE`/`FINDING`；证伪 `SURVIVED`/`FALSIFIED`/`NOT_INDEPENDENTLY_REPRODUCIBLE`（本轮无 CAD/FEA 内核路径被判 N-I-R 的 finding；唯一 N-I-R 登记项见 §6，不阻塞闭合）

## 0. 执行总览

| 产出物 | 计划项 | 执行 | 结论 |
|---|---|---|---|
| 00_receipt（回执） | 6 | 6/6 | **SAFE** |
| 01_frame_authority（权限矩阵 CSV + frame 定义 + 桥推导计划） | 9 | 9/9 | **FINDING**（2×LOW） |
| 02_route_c_inputs（Route-C 库存 .json/.md） | 7 | 7/7 | **SAFE** |
| 03_r2_flex_inputs（R2 柔性库存 .json/.md） | 7 | 7/7 | **FINDING**（1×MEDIUM） |
| 任务 (a)：round-1 报告 6 个 hash pin | — | 6/6 | **MATCH** |
| 任务 (b)：round1_bridge/02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml | — | 未落盘 | **PENDING_NEXT_SWEEP** |

**findings 总计：HIGH=0，MEDIUM=1，LOW=4；FALSIFIED=0。** 无 HIGH → 本轮不触发任何产出物的下游消费冻结；MEDIUM 项（RT1-F01）按纪律须在 Owner 签署前修复。

## 1. 任务 (a)：round-1 六个 hash pin 复算 —— 6/6 MATCH

| 文件 | pinned（前 16 hex） | 实测 bytes | 结果 |
|---|---|---|---|
| `arm_b601_v1.urdf` | 1BC2B7483CD8025D | 11321 | MATCH |
| `SOLAR_ARRAY_R2_CANDIDATE_V1.step` | 21FF77B882DBFAB8 | 131834 | MATCH |
| `E21_DIAGNOSTIC_GATE_V1.json` | B03B7C7AF571AA00 | 22675 | MATCH |
| `HARNESS_B601_FULL_FK_SWEEP_V2.json` | DB86348B8276FB2D | 20197 | MATCH |
| `ROUTE_C_PRECAD_PARAMETRIC_SEARCH_GATE_V1.json` | B43745081B4D0F22 | 17306 | MATCH |
| `ROUTE_C_PRECAD_PARAMETRIC_SEARCH_VALIDATION_V1.json` | 84D89F631F7904DA | 32996 | MATCH |

另做内存内 1 字节变异负控（e21 gate）：检测器 firing。全 64-hex 见复算包输出。

## 2. 任务 (b)：桥文件未落盘 → PENDING_NEXT_SWEEP

执行时刻（2026-08-23T17:26+08:00）`round1_bridge/` 下仅有 `00_authority/`、`r2_flex_prep/`、`route_c_prep/` 与本目录；`02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml` **不存在**。ATK-04/11/12 对桥文件实体的攻击与静默平均判别值扫描延至下一 sweep。已预登记判别 witness（落盘即打）：

- 静默平均判别值 **29.226410622980581°**（复算 (29.041965867604112+29.41085537835705)/2 = 29.22641062298058）；平均矩阵 det≈0.976 判别区间；
- Steiner witness **m·d² = 2.4302436760318294e-3 kg·m²**（比浮点噪声高 10 个数量级，漏项绝无容差可吸收）；
- 桥平移 [0,0,+0.02275] m、转角全精度 25.000014°（contract 截断拼写 25.000013999964253°）。

## 3. 四件产出物逐项攻击结果

### 3.1 receipt（00_receipt）— SAFE（6/6）

- **ATK-14（29 项 pin 全量复算）**：26 项 PASS 全部 hash+bytes+expected 三重 MATCH；2 项 NO_RECORDED_HASH 复算正常；1 项 DRIFT（solar_r2_build_report 自指哈希）**复现成立**——实测 6160C1D0… 与 receipt 声明的 actual 逐位一致、与 expected AFE4CA26… 确不匹配，receipt 的 DRIFT 裁决独立复算通过。receipt 不自列（防自指 ✓）。URDF 另验 LF 归一化哈希 408147DD… MATCH。
- **ATK-01/02/07**：文件非空可解析；null∧PASS 共存 0 命中（全文件仅 2 个 null，均为 NO_RECORDED_HASH 条目的 expected_sha256，fail-closed 语义正确）；自报计数 29/26/2/1 与独立计数全等；`next_stage_authorized=false`、`release_credit=false`；每个 PASS 挂 `recorded_in` 证据指针。
- **纪律/声明**：scope_compliance 声明纯 cpython 计算；文件 mtime 16:46:31.579 与 generated_local 一致；ODR-43/44 逐字块在 `authority_basis`，未新增任何 release 语义。

### 3.2 frame authority 三件（01_frame_authority）— FINDING（2×LOW）

- **ATK-11（桥 16 元独立重建）**：由 `E21_AUTHORITY_CONTRACT_V1.yaml` 两个 `transform_S_A0_rows` 独立提取重建 `B = inv(T_dyn)·T_phys`，与桥计划公布值逐元差 **6.94e-18**；det(R_B)=1.0000000000005196、正交 5.1958e-13、转角 25.000013999932346°、`T_dyn·B==T_phys` max-abs **0.0**、往返 5.55e-17、四元数差 ~1e-13——全部复现。手性判别：±θ 两候选相差 **49.986°**（≈50°，无容差可吸收）。方向约定与逆桥在计划 a.4 成文；截断 witness 双版对照在 a.5.1 成文（全精度拼写钉为桥常数，舍入拼写登记为 1.1e-4 mm 级已知差）。**SURVIVED**。
- **ATK-04（frame mixing 正向对照）**：两车道 CG 差范数复算 = **0.003524348142565558 m**（与公布逐位一致）；`C_S=T_dyn·inv(T_phys)` 映射 V2 账本 C01 臂 CG，对 e21 ODR01 车道计算值残差 **1.1314150167e-4 mm**，与 e21 公布的账本残差 1.1314150166e-4 mm 一致（残差全部为舍入钟摆拼写差，非桥结构误差）；系统级量级关系 (m_arm/M)·|Δr_arm| = 0.0232849 m 结构自洽。**SURVIVED**。
- **ATK-05（质量恒等）**：26.327308858000002 + 4.695555949342986 = 31.022864807342987 kg（|Δm|=0.0）；URDF 10 个 `<mass>` 标签独立求和 = 4.695555949342986 kg（误差 0.0）。**SURVIVED**。
- **ATK-12（Steiner）**：计划 (c).4 含正确构造（d 必须先在目标系形成）并显式禁止错误模式；通道惯量差复算 = **0.10311953522836159 kg·m²**（逐位一致）；witness m·d²=2.43024e-3 kg·m² 登记。**SURVIVED**。
- **ATK-06/03/HOLD/M3R**：静默平均黑名单（29.226410622980581、CG/惯量中点）8 文件 0 命中；M4 状态逐字（FROZEN_V1 等已对照 M4 yaml 行 61–97）；无 PROVISIONAL 提升；V5 `single_consumption_rule_resolved=false` 今日复核未变，无任何"二选一"语义；M3R 四站语义分离保持，210.405 as-built datum 被明确排除在桥外。
- **RT1-F02（LOW）**：CSV 45 行 pin 为 12-hex 短哈希。45/45 前缀 MATCH（36 个 unique path），列名已诚实标注 `sha256_short`，且同路径全 64-hex pin 在 receipt/Route-C 库存中存在——判 LOW 而非 MEDIUM。
- **RT1-F03（LOW）**：§4.4 消费警告的"错位 25.07 mm"独立复算不成立为 3D 范数：naive `T_dyn(mm)@T_M_flange` 落点 [185.16363393, 0.015994151, −25.155]，对 M4 M3R_LOCAL 的 3D 误差范数 = **33.9107 mm**（对 FASTENER_END_PLANE = 35.5748 mm）；25.07 mm 仅为 z 向分量 25.0686 mm。定性警告（合成约定必须钉死）成立，且其主张的正确读法复算精确吻合：t_dyn+t_json=[210.405, 0.015994151, −0.08636607] == M4 B601_FASTENER_END_PLANE。该数值为非权威警示注记，无下游消费。

### 3.3 Route-C 库存（02_route_c_inputs）— SAFE（7/7）

- **状态 verbatim**：MPI gate 复核（hash MATCH）MPI-01..06/08=HOLD_NOT_CONTROLLED、MPI-07=HOLD_PARTIAL_LOCAL_KINEMATICS_ONLY、0/8；库存全文无任何 MPI "controlled/closed" 宣称。
- **ATK-10（Route-B 八字）**：V1（−11.8667 @LHS_06 vs link5 / 1.081 @SWEEP_joint5_00:fillet_node_12 / −11.3573 @HARDSTOP_joint4_lo joint5）与 V2（−11.9938 @SWEEP_joint2_09 vs link3 / 0.1 @CORNER_110000:span_link5 / −11.9902 @HARDSTOP_joint4_hi joint5）逐字一致；NRB-03 工单行 155、NRB-04 角色标签、NRB-05 终端 gate（REJECTED/TRIGGERED/TMG-4 FAIL/NOT_RELEASED）逐字一致；V1/V2 哈希双 MATCH；`route_b_values_not_inherited` 四值（10.0/25.0/30.0/4001.158）`inherited=false` 在 MPI audit 中逐字复核。库存还正确登记了三套数字口径（机器头条 V1/V2 vs 圆整叙述）不得合并的警示。
- **ATK-02**：13 项物理量全 null+HOLD；前沿五 null + UNKNOWN 理由串、manufacturing_coordinates_status、扫描轴边界标记全部与源文件逐字一致。
- **ATK-03 变体**：47/47 仅以 `PASS_SYNTHETIC_SEMANTICS_ONLY` 引用且 `grants_design_authority=false`；P11 引用的合成弧 49.99999999999991 mm 已在 `ROUTE_C_PREDICATE_QUALIFICATION_V1.json:651` 核实。
- **ODR-44 边界**：禁止 Route-C CAD 候选语句逐字在册；今日 CAD entry gate 仍 HOLD（NOT_AUTHORIZED）。
- **八条 forbidden_shortcuts**：逐条对照，库存无违反。
- **ATK-07**：13/5/3/21 计数与 summary 全等；21 个源 pin 全 64-hex 复算 21/21 MATCH；owner 模板映射与 MPI gate 逐字一致。

### 3.4 R2 柔性库存（03_r2_flex_inputs）— FINDING（1×MEDIUM）

- **RT1-F01（MEDIUM）**：`source_files_sha256` 全部 16 条仅存 16-hex + "..." 截断值，违反 ATK-14"新产出物禁止只 pin 16-hex 截断值"。Falsifier：独立全量 sha256 复算 **16/16 前缀 MATCH**（内容完整、无替换证据；e21 gate/contract/几何候选等前缀均与全宽 pin 链一致）。格式违规直接可观察 → SURVIVED_FALSIFICATION。修复：Owner 签署前以全 64-hex 重发该库存的 pin 块。
- **ATK-09**：五工况频率表与 e21 ROM JSON **逐 float 相等**（5 工况 × {leaf_only, conflict, conflict_minus} 三组数组）；conflict 负差全部保留符号（nominal −0.2447/−2.7319/−13.1326 Hz）；4 位公布值与 MODES.json 一致；相对频移复算 [−3.5096, −6.9411, −13.4000]% vs 库存 [−3.51, −6.94, −13.40]%；e21 公布最大误差 4.8404e-05 Hz = 库存声明 4.84e-05；R1 黑名单数值 0 静默命中（0.3483933 仅出现在显式 legacy 注记）。
- **ATK-03**：14 行参数表 status/uncertainty/source 全非空；class 逐字（PROVISIONAL/PROVISIONAL_DERIVED；ζ=0.01 带 TBD_cite_literature；GJ 降为 NULL_EFFECTIVE 且逐字引用卡片自身"band not yet assigned"——保守方向，非提升）。
- **ATK-05**：翼闭合 0.78 = 3×0.18+0.05+2×0.03+0.08+0.05；两翼 1.56 kg；R2−R1 = 0.8632134 kg；24.8632134 kg——与质量账本逐项一致，无重复计入。
- **G21 语义**：e21 三标志（selected/propagated/frozen 全 false）逐字保持；Mqq*−Mqq 矩阵一致；`this_inventory_selects=null`，MC-A/B/C 只列不选。
- **ATK-02**：damping/participation/forced_response/standard_uncertainty 四 null 与 e21 ROM 一致保持，无零化。
- **e15**：`REPEAT_ANCF_CERTIFICATION` 逐字携带；交叉求解差 0.05637349419858036 > 0.05 与 `final_candidate_cross_solver.available=false` 均在 e15 gate_summary 核实。

## 4. Findings 清单（仅保留 SURVIVED_FALSIFICATION）

| ID | 严重度 | 产出物 | 要点 | 处置 |
|---|---|---|---|---|
| RT1-F01 | MEDIUM | R2 flex 库存 .json | 16 条 pin 仅 16-hex 截断；内容复算 16/16 完整 | Owner 签署前以全 64-hex 重发 pin 块 |
| RT1-F02 | LOW | 权限矩阵 CSV | 45 行 12-hex 短 pin（已诚实标注 sha256_short，全宽 pin 交叉存在） | 下轮改全宽 |
| RT1-F03 | LOW | frame 定义 §4.4 + CSV 行 12 | "25.07 mm"仅为单轴分量；3D 范数实为 33.91/35.57 mm；定性警告成立 | 下轮修正数值口径 |
| RT1-F04 | LOW | 上游 Route-C 机器件（非本轮产出物缺陷） | 内部 generated_local 为名义标签（17:35/23:15）与 mtime（13:09/15:44）不可同时成立；pin 全 MATCH、无完整性影响 | 上游时钟纪律注记 |
| RT1-F05 | LOW | 红队自身 round0 计划书 | ATK-12 witness 笔误 2.4304e-3 → 精确 2.43024e-3；量级结论不变 | 计划书下次修订更正 |

## 5. 与基线不符之处

无科学性不符。V5 gate 今日复核仍 HOLD、`single_consumption_rule_resolved=false`；e21 双车道全部关键数字（29.041965867604112°/29.41085537835705°/Δ0.3688895107529362°、CG 差 0.003524348142565558 m、惯量差 0.10311953522836159 kg·m²）从 hash 钉死的车道文件逐位复现。仅记录四类卫生级偏差（见 §4 LOW 项）。

## 6. NOT_INDEPENDENTLY_REPRODUCIBLE 登记（不阻塞）

- 桥计划 a.4 的惯量见证 6.42e-8 kg·m²（及 e21 对照 7.03e-8）：需从 WP2 V2 账本提取 C01 臂惯量张量，超出本轮边界；桥方向/语义已由 CG 级见证（1.1314150167e-4 mm == e21 公布残差）充分验证，故不阻塞。

## 7. 下一轮优先攻击顺序（对主链下一轮产物）

1. **桥文件落盘即打**（`02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml`）：ATK-11（16 元/det/正交/手性/方向/逆矩阵/截断双版 witness）→ ATK-06（29.226410622980581° 与 det≈0.976 判别）→ ATK-04（跨系量必须引用唯一桥标识+hash）→ ATK-12（Steiner witness 2.4302436760318294e-3 必须可复现，不得抹成 0）。
2. **MPI-FB-03 往返报告**：封闭性 ≤1e-12；θ 反号/平移反号两个变异负控必须被其自检出。
3. **MPI-FB-04 质量/CG/惯量变换包**：Steiner 项构造顺序（d 在目标系形成）、禁逐元旋转、禁对不确定度阵 RURᵀ、逐成员特征值/迹不变式。
4. **MPI-FB-05 e21 重跑**：`consumer_ambiguity_count==0`；禁止以 29.04197°/29.41086° 任一为判据；目录级哈希扫描证明未覆盖 e21 既有文件。
5. **MPI-FB-06/07**：九构型质量不变式 0 差；CANDIDATE 命名；R2 文件字节不动；全部强制 HOLD 逐字携带。
6. **R2 flex 下一轮**：动态质量分配裁决（MC-A/B/C）单一显式记录；e15 重认证规格保持文本态直至 MPI gate。

—— 执行完 ——
