# RED_TEAM_ROUND2_EXECUTION_V1 — 红队第二轮攻击执行报告（Wave-2b REDTEAM-2 / round1_bridge / redteam_round2）

- 生成时间：2026-08-23T19:05+08:00（宿主机本地钟，Asia/Shanghai）
- 攻击依据：`round0_handover/04_red_team/RED_TEAM_ATTACK_PLAN_V1.md` §2（Falsifier 协议）+ `redteam_round1/RED_TEAM_ROUND1_EXECUTION_V1.md` §7（下一轮优先攻击顺序）
- 纪律：全程只读上游与主链；纯 Python 3.13.9 + numpy 2.3.5 + scipy 1.16.3 + hashlib；未启动任何 CAD/FEA 进程；git 未使用；写入仅限本目录。**未执行 Wave-2a 任何生成器脚本**（执行会重写冻结产物）；e21/b601 模块以 importlib + `dont_write_bytecode` 只读加载
- 复算包（一切数字可重跑复核）：
  - `rt2_static_attacks.py`（45995 B，sha256 `47E8E2EB33D4E2DD…`）→ `rt2_static_output.json`（110644 B，`A0D0C2693184B07D…`）：S0 hash 哨兵 / S1 ATK-11 / S2 ATK-06 / S3 ATK-04 / S4 ATK-12 / S5 FB-06 重组 / S6 V6-R3 审计 / S7 卫生扫描
  - `rt2_e21_rerun.py`（15827 B，`9D2C84B3F77B1748…`）→ `rt2_e21_rerun_output.json`（8619 B，`5E0583CFF25AF445…`）：e21 桥接车道独立复跑 23/23 + FB-06 FK 交叉复核 + 77 文件污染哨兵
  - 本报告两件（.json/.md）按项目惯例 SELF_REFERENCE_EXCLUDED，自身不入自列哈希，由下游落盘后 pin
- 判定词表：攻击面 `fired`/`not_fired`；证伪 `SURVIVED`/`FALSIFIED`/`NOT_INDEPENDENTLY_REPRODUCIBLE`；findings 只保留 SURVIVED_FALSIFICATION

## 0. 执行总览

| 任务 | 攻击 | 结果 | 判定 |
|---|---|---|---|
| (a) 桥本体 | ATK-11 | not_fired | **SURVIVED** |
| (b) 静默平均 | ATK-06 | not_fired | **SURVIVED** |
| (c) frame mixing | ATK-04 | not_fired | **SURVIVED** |
| (d) Steiner/不确定度阵 | ATK-12 | not_fired | **SURVIVED** |
| (e) e21 桥接重跑独立复算 | FB-05 复核 | not_fired（23/23 复现） | **SURVIVED** |
| (f) FB-06 九构型 | FB-06 复核 | not_fired | **SURVIVED** |
| (g) V6/R3 候选 | FB-07 复核 | not_fired | **SURVIVED** |
| (h) 全程 hash 哨兵 | ATK-14 类 | fired ×1（已登记上游自指 DRIFT 复现，非新漂移） | **SURVIVED** |

**findings 总计：HIGH=0，MEDIUM=0，LOW=4（RT2-F01..F04，全部卫生/注记级）；FALSIFIED=0；无新增 NOT_INDEPENDENTLY_REPRODUCIBLE 项。**

**对 MPI-FB-08 Gate 的放行意见：PASS_RECOMMENDED**（仅限红队攻击面 = FB-02..07 主链完整性；Gate 还须评估的桥外 CM 状态见 §7；本意见不授予任何 release/production/flight 权限）。

## 1. (a) ATK-11 桥本体 — SURVIVED

由 hash 钉死的 e21 authority contract（`7D2E0792…` 复核 MATCH）两条 `transform_S_A0_rows` 独立重建，与冻结桥文件（`0ACEB659284CAB86…` 复核 MATCH）逐元对拍：

| 量 | 本轮复算 | 主链公布 | 一致 |
|---|---|---|---|
| stored B vs 重建（dense 路径） | 0.0 | FB03-14 = 0.0 | ✓ 逐位 |
| dense vs 刚体解析逆 双路径 | 0.0 | — | ✓ |
| stored inv(B) vs 重建 | 4.709566070459914e-13 | dense-vs-rigid 4.709566070459914e-13 | ✓ 逐位（stored invB = inv(T_phys)@T_dyn 路径） |
| stored C_S / C_S_inv vs 重建 | 4.709566070459914e-13 / 5.55e-17 | — | ✓ |
| det(R_B) | 1.0000000000005196 | 1.0000000000005196 | ✓ |
| max\|RᵀR−I\| | 5.195843755245733e-13 | 5.195843755245733e-13 | ✓ |
| **T_dyn@B == T_phys（方向语义）** | **0.0（float64 精确）** | 0.0 | ✓ |
| 测试点方向闭合 worst | 0.0（含 URDF base_link CG 等 6 点） | — | ✓ |
| 手性判别 | +θ 候选 0.0°；−θ 候选 50.000028°（=2θ 精确） | — | ✓ det>0，无容差可吸收 |
| 四元数 | stored vs 重建（q/−q 等价）0.0；轴翻转候选拒于 0.4329 | — | ✓ |
| 平移 | [0,0,+0.02275]（z 分量差 −6.9e-18） | +0.02275 | ✓ 非 12.75/2.405 mm 栈内站距 |

截断双版对照（全复现）：

| witness | 本轮复算 | 桥文件登记 | 一致 |
|---|---|---|---|
| contract 12 位截断导出角 | 25.000013999964253° | 25.000013999964253° | ✓ |
| 与 25.000014° 的差 | 3.574740503609064e-11° | 3.574740503609064e-11° | ✓ 逐位 |
| 全精度 θ 合成 vs 桥（矩阵元） | 4.991562718714704e-13 | 4.991562718714704e-13 | ✓ 逐位 |
| 精确 25° 参考 vs 桥 | 2.2145230055281573e-07 | 2.2145230055281573e-07 | ✓ 逐位 |
| 舍入拼写 vs 桥 | **4.83193e-07（6 位三角拼写）** | 5.180141831595542e-07（角度合成拼写） | ⚠ 见 RT2-F01（LOW） |
| C01 臂 CG 见证 | 1.1314150163732986e-07 m | 1.1314152027209831e-07 m | ✓ 同一 ~1.1e-4 mm 登记级（互差 1.9e-14 m） |

已知偏差登记（24.999981252° 拼写、C01 见证）如实携带；负控自检：1 字节内存变异即被检出。

## 2. (b) ATK-06 静默平均 — SURVIVED

- 数值黑名单（容差 rel 1e-9）扫全部 31 个 round1 文件全部数值叶：**主链产物（02..07）0 命中**。8 个 HARD 命中全部位于 redteam_round1 自身输出文件——那是一轮红队**预登记的判别 witness**（`silent_average_discriminant_deg` 29.22641062298058、`cg_midpoint_blacklist`、`inertia_midpoint_max_element`），属判别器注册而非平均。
- `23.3032134` 命中 9 处（FB-06 各构型 bus 行）：谱系算术核验成立——M4 bus core 22.927194215348 + legacy flange 0.376019184652 = 23.3032134 精确；系统总量为 31.022864807342987 kg（非 24.0 kg），属 accepted 账本合法携带，非旧 24 kg 模型静默复用。`24.0` 命中 2 处均为 JSON 行号字段误命中。R1 板数值（0.3483933/1.7419665/EI 三值）**0 命中**。
- 旋转块 det 异常扫描（|det−1|>1e-6）：**0 命中**（FB03-20 的 0.9531538418861297 = (1+cos25°)/2 为已登记变异负控判别值，合法）。
- `averag|midpoint|blend|select…` 关键词 98 命中逐条分类：47 条禁令语境（"no selection/averaging_forbidden/forbidden"等）+ 51 条逐条复核（负控代码、HOLD 名称、Route-C 注册表文本、MC-A 裁决记录等），**无任何执行平均/二选一语义的命中**。

## 3. (c) ATK-04 frame mixing — SURVIVED

- FB-06 九构型 **9/9**：臂行 `bridge_provenance` 携带唯一桥标识 + sha256，与本轮重算桥哈希 **9/9 MATCH**；`bridge_uncertainty: null` 9/9；非臂成员携带桥 provenance = **0**（正确：翼/总线/目标不过臂桥）。
- V6/R3 重绑定块：`bridge_id: T_PHYSICAL_TO_DYNAMIC` + sha 与重算 MATCH；三条 validation 证据 sha 全部重算 MATCH；质量覆盖层 sha MATCH；`consumer_ambiguity_count: 0`。
- 残留二选一/混用语义：无。全部 select/choose 类命中均为禁令文本、HOLD 名称或 MC-A 唯一显式书面裁决记录。

## 4. (d) ATK-12 Steiner / 不确定度阵 — SURVIVED

- Steiner witness：m·d² = 4.695555949342986 × 0.02275² = **0.0024302436760318276 kg·m²** 精确复现（量级 2.43e-3，漏项绝无容差可吸收）。
- R 共轭正确形式：about-origin 变换 vs 第一性原理 = **5.39124300757976e-13**（≤1e-12）；字面读法（未共轭减源项）偏差 **0.007710680881610109 kg·m²** 复现，且被主链**显式登记为 FORBIDDEN_READING**。
- 车道差解析（残余固定 + 臂经 C_S_inv 映射）：ΔCG 范数复算 0.003524348142565572（公布 0.003524348142565558）、ΔI 复算 0.10311953522847439（公布 0.10311953522836159）；桥接系统 vs WP11 公布车道：CG 1.39e-17 / 惯量 1.13e-13——车道差被桥**解释而非抹零**。
- 不确定度阵审计（WP2-AUD-02 禁径）：FB-06 九构型臂行的不确定度子树（含 6×6 协方差、σ 向量、质量/CG 不确定度）与 V3_R2 **逐字段深比较全等**；而 C01..C06 的 CG/惯量确实被桥改写——"量动、不确定度逐字"证明**不存在 RURᵀ 逐元素旋转**。FB-04 方法声明"never rotated"逐字在册。

## 5. (e) e21 桥接重跑独立复算 — SURVIVED（23/23）

自有 runner（不消费 Wave-2a 脚本；mount 由 contract 自建而非读桥文件）：

- 独立 B vs 桥文件 = **0.0**；mount = T_dyn@B 与 T_phys 差 **0.0**（精确）；`consumer_ambiguity_count = 0`（runner 内 mount 构造点 = 1）。
- 单一权威峰 **29.41085537835705°** 复现，与 WP11 公布车道**逐位相等**；与 ODR01 参考车道差 **0.3688895107529362°** 复现；nfev 5013 一致。
- 闭合：dP **2.582350176184633e-16**、dL **2.3686440571016716e-16**、energy **4.0484963084180175e-11**、四元数 pre **2.1760371282653068e-13**（Radau 带内）/post **2.220446049250313e-16**、质量阵最小特征值 **0.00039091914924673215**——与 FB-05 公布值全部一致。
- 初值 vs V3_R2 C07：质量误差 0.0；CG 差 0.003524348142565558 m；惯量差 0.10311953522836159 kg·m²（桥效应，非噪声）。
- 全状态轨迹 bridged vs WP11 参考：四元数/位置/偏差 **0.0**（451 采样点逐位一致）。
- 验收独立性：FB-05 全部 13 项 check 的 limit 无一引用 29.04197/29.41086/29.22641；`acceptance_rule_declaration` 逐字在册。
- 污染哨兵：77 个监视文件（e21 全模块 + sim_05 + URDF + wp2 + M6 transforms）前后快照 **0 新增 / 0 漂移 / 0 删除**；e21 目录无 `__pycache__`；sim_05 存在 8 个**历史性** `.pyc`（先于本轮，前后逐位一致）——登记为 RT2-F04 卫生注记。

## 6. (f) FB-06 九构型 — SURVIVED

V3_R2 成员独立重组（自有聚合器 + 自有 C_S）：

| 构型 | 成员→stated | 质量不变式 | 我的候选 vs FB-06 CG | vs FB-06 惯量 | ΔCG 解释残差 | ΔI 解释残差 | 非臂逐字 |
|---|---|---|---|---|---|---|---|
| C01 | 0.0 | 0.0 | 1.54e-14 | 3.44e-13 | ≤6.9e-18 | ≤8.9e-16 | ✓ |
| C05 | 0.0 | 0.0 | 1.23e-14 | 2.40e-13 | 同上带 | 同上带 | ✓ |
| C07 | 0.0 | 0.0 | **0.0** | **0.0** | — | — | ✓ |
| C07..C09 | 0.0 | 0.0 | 0.0 ×3 | 0.0 ×3 | — | — | ✓ ×3 |

- 九构型质量不变式全部精确 0 差；C01..C06 全部 ΔCG/ΔI 由臂行桥作用逐项解释（worst 6.9e-18 / 8.9e-16）。
- **C05 HELD_CANDIDATE 状态逐字携带**：`HELD_CANDIDATE_FK_REGRESSION_FAIL_MAX_RESIDUAL_567P734_MM_RETAINED_FACT_NOT_ABSORBED_BY_UNCERTAINTY` 与 V3_R2 逐字一致，未被吸收/未修复；FB-06 顶部 carried note 在册。
- FK 交叉复核（e21 纯 ODR01 直算）：C01 = 1.1314151618148656e-07 m / C05 = 1.0857568217800054e-07 m / C07 = 0.0，与 FB-06 公布**逐位一致**（舍入拼写偏差级，登记不归零）。
- 臂行除 com/inertia/bridge_provenance 外全部字段与 V3_R2 深比较全等（含 pose_status、不确定度树）。

## 7. (g) V6/R3 候选 — SURVIVED

- **base 字节不动**：wp10 V5_R2（18869 B / `9B6D8025…`）与 wp13 R2（95903 B / `5DDA6277…`）当前哈希+字节数与 **round0 receipt（Wave-2a 之前 16:46 独立锚点）逐位一致**。
- CANDIDATE 命名、`candidate: true`、`status: CANDIDATE_ONLY__NOT_RELEASE_NOT_PRODUCTION_NOT_FLIGHT__PENDING_OWNER_REVIEW`、`review_status: PENDING_OWNER_REVIEW`、`next_stage_authorized: false`、`release_credit: false`、required_acknowledgement 均在册。
- **逐字携带全量比对（非抽检）**：V5 11 条 fail_closed_invariants 在 V6 与 R3 各 11/11 逐字等于 V5 gate 活源；R2 11 条 retained_holds 11/11 + 8 条 prohibitions 8/8 逐字；e21 11 条 mandatory_holds 在两候选各 11/11 逐字。
- V5 gate 今日复核：gate=HOLD、next_stage_authorized=false、`single_consumption_rule_resolved=false` 未变。
- RT2-F03（LOW 建议）：候选同文携带 `UNRESOLVED` hold 与候选级单一消费语义并存，判定为**有意共存**（候选级工程解 vs 权威级 HOLD），建议 FB-08 文本显式说明以免下游误读。

## 8. (h) 全程 hash 哨兵 — SURVIVED（1 项已登记复现）

- round1 产物落盘登记 **31 件**全量 sha256+bytes（清单见 `rt2_static_output.json` S0，与本报告落盘前目录树程序化集合比对一致）。
- 上游 pin 跨源一致性：46 个唯一路径，**45 MATCH + 1 冲突**。唯一冲突 = `SOLAR_ARRAY_R2_BUILD_REPORT_V1.json` 自指哈希：实测 `6160C1D0…` 与 receipt 声明 actual 逐位一致、与 expected `AFE4CA26…` 永不匹配（自指不可能匹配）——即已登记 open item **OI-R1-01**（AWAITING_UPSTREAM_ERRATUM），两个真实工件 STEP/FCStd 复算 PASS 不变。**非新漂移**。
- 关键上游全部 MATCH：e21 contract/campaign/src/gate/双车道/residual/九构型 audit、URDF、Solar R2 STEP、wp2 V3_R2、wp10 V5_R2、wp13 R2、V5 gate、M3R stack/flange json、F3R2 初始姿态、frame tree、WP11 标定、M6 transforms、M7 ODR 登记、b601_model.py。
- 变异负控：桥文件 1 字节内存变异即 firing。
- RT1-F01 修复件（FULLHASH addendum）：本轮独立复算 **16/16 全 64-hex MATCH**。

## 9. Findings 清单（仅 SURVIVED_FALSIFICATION）

| ID | 严重度 | 对象 | 要点 | 处置 |
|---|---|---|---|---|
| RT2-F01 | LOW | 桥文件 known_deviation_register[WP11-F-03] | 条目文本引 6 位三角拼写（对应矩阵差 4.83193e-07），登记的 matrix_max_abs 5.180141831595542e-07 对应角度合成拼写；两重建互差 3.49e-8（6 位拼写对范数亏损 1.65e-7）；C01 物理见证两拼写下均复现（互差 1.9e-14 m），偏差级不变 | Owner 签署前注明该数值对应哪条重建路径（或两者并登） |
| RT2-F02 | LOW | FB03-14/15/16 | 1e-16 限量是同路径复算（同 numpy/LAPACK 序列）恒真，不构成独立证据；真正独立的跨路径量（4.709566070459914e-13、5.195843755245733e-13）桥文件已诚实公布且本轮复现 | 卫生项：FB-08 可将该三条改标为同路径复现，跨路径见证作独立证据引用 |
| RT2-F03 | LOW | V6/R3 候选 | `UNRESOLVED` hold 与候选级 single-consumption 声明同文并存——判定有意共存（候选≠权威升格），非矛盾 | 建议 FB-08 gate 文本显式确认共存语义 |
| RT2-F04 | LOW | sim_05 `__pycache__` | 8 个历史性 .pyc 先于本轮存在，本轮前后逐位一致；e21 目录无 pycache；我的 importlib 未产字节码 | 纯卫生注记，不阻塞 |

## 10. 与基线不符之处

无科学性不符。三条注记：

1. 一轮红队报告的手性分离角引为 49.986°；本轮直接复算为 **50.000027999951776°**（=2×25.000014 精确）。差异为测试矢量相关（非垂直于转轴的测试矢量会缩小表观角）；不变量结论（"~50° 分离，无容差可吸收"）不受影响。
2. round0 计划书引 ODR01 车道 CG 的 y 分量为 4.376e-05（截断引用）；pin 文件全精度值为 4.37633035602944e-05；本轮全部计算用 pin 全精度值。
3. round0 计划书 Steiner witness 期望 2.4302436760318294e-3 vs 本轮复算 0.0024302436760318276（末位 ulp 路径噪声，RT1-F05 已登记同类）。

## 11. Wave-2b 并行落盘观察（本轮执行期间）

- `decisions/ENG_DECISION_DYNAMIC_MASS_ALLOCATION_V1.yaml/.md`：MC-A 裁决（OI-R1-06 工程级 discharge、Owner 确认 pending、ECR 可逆）；不属本轮攻击面；OPEN_ITEMS_UPDATE 登记其 severity 是否降级属 CM/Owner 口径。
- `00_authority/R2_FLEX_INPUT_INVENTORY_V1_FULLHASH_ADDENDUM_V1.json`：RT1-F01 修复件，本轮独立复算 16/16 MATCH。
- `00_authority/OPEN_ITEMS_UPDATE_V1.csv`：OI-R1-05（P10-P12 RFI 缺口）仍 **STILL_HIGH**；OI-R1-01 仍待上游 erratum。
- `00_authority/MPI_BRIDGE_PACKAGE_MANIFEST_V1.json`：18:38:10 快照 42 件；其 pin 的 `rt2_static_output.json` 为本件首版（`d62c1b93…`），本件因补登 18:38 三件而重跑（现 `A0D0C269…`，同字节数 110644）——清单自带"此后新增文件须经复走目录树补登"声明，**建议 CM-FIX 在本目录最终化后复走刷新**。

## 12. 对 MPI-FB-08 Gate 的放行意见

**PASS_RECOMMENDED** —— 限定于红队攻击面：FB-02..07 主链产物的完整性（桥正确性、无静默平均、无 frame mixing、Steiner 完备、单消费者重跑、九构型传播、候选重绑定、哈希链）。八项指派攻击全部 not_fired 于主链；HIGH=0、MEDIUM=0；唯一 fired 项为已登记上游自指 DRIFT 的复现（非新）。

Gate 自身仍须评估的桥外状态（不属于红队放行语义）：

1. OI-R1-05 P10-P12 RFI 缺口仍 HIGH OPEN（Route-C 侧，不触及桥完整性）；
2. OI-R1-06 MC-A 裁决 Owner 确认 pending（severity 降级权属 CM/Owner）；
3. OI-R1-01 上游 erratum 未签发（两个真实工件 PASS）；
4. V5 gate 今日仍 HOLD / next_stage_authorized=false / single_consumption_rule_resolved=false；全部 round1 产物自报 next_stage_authorized=false / release_credit=false，前后一致；
5. 本报告 4 条 LOW（RT2-F01..F04）——卫生/建议级，均不阻塞。

本意见不授予任何 release、production、manufacturing、qualification、launcher 或 flight 权限；仅声明主链产物在第二轮红队攻击下存活。

—— 执行完 ——
