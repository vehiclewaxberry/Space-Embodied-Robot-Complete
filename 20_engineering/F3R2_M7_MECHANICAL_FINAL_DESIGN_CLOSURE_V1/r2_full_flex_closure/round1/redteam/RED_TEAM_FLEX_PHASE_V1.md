# 红队柔性阶段攻击报告 V1（AGENT-4 / Wave-3a / R2 全柔性闭合）

- schema: `RED_TEAM_FLEX_PHASE_V1`（人读版；结构化字段以同目录 `.json` 为准）
- 生成时间：2026-08-23T20:20+08:00（宿主机本地钟）
- 状态：**CANDIDATE_ONLY__RED_TEAM_ATTACK_RECORD__PENDING_OWNER_REVIEW**；`release_credit=false`、`next_stage_authorized=false`
- 执行口径：纯 Python（numpy 2.3.5 / scipy 1.16.3 / pyyaml 6.0.3 / hashlib），全部上游文件只读，未启动任何 CAD/FEA/仿真进程，未 import 上游模块（无 `__pycache__` 污染），git 只读。复算脚本与原始输出同目录归档：`RED_TEAM_FLEX_PHASE_RECOMPUTE_V1.py` / `RED_TEAM_FLEX_PHASE_RECOMPUTE_V1_OUTPUT.json`。
- 攻击对象：
  1. MC-A 裁决 `decisions/ENG_DECISION_DYNAMIC_MASS_ALLOCATION_V1.yaml`（本代理复算 sha256 `9CCE829E1581B190…`）
  2. MPI-FB-08 Gate `08_gate/MPI_BRIDGE_GATE_V1.json`（`60911E3C88387E2E…`）+ `FB08_INDEPENDENT_RECOMPUTATION_V1.json`（钉 `A5678600…` 吻合）

## 0. 总结论

**两个攻击对象均 SURVIVED_FALSIFICATION。** findings：HIGH=0 / MEDIUM=0 / LOW=6 / INFO=2。全部机器可核查声称经本代理独立编码复算成立；唯一确认的文本级偏差为 RTF-F01（V09-01 计数口径）。MC-A 裁决与 MPI-FB-08 Gate 的状态、PASS 限域与全部 HOLD 逐字保持，本文件不升格、不逆转、不解除任何一项。

## 1. 对 MC-A 裁决的攻击（任务 1）

### 1.1 越权表述检查 —— 未越权

- `decision_class=ENGINEERING_AUTHORITY_DECISION__NOT_OWNER_LEVEL__ECR_REVERSIBLE`、`status=…PENDING_OWNER_CONFIRMATION…`、`authority_basis.explicit_nonclaim_owner`、人读版 §标题四处显式声明非 Owner 级；`review_status=PENDING_OWNER_REVIEW`、`next_stage_authorized=false`、`release_credit=false` 逐字在场。
- OI-R1-06 登记行 `owner_or_engineering=OWNER` 在冻结 CSV 中逐字保持（正确）；裁决仅 discharge 其工程内容、Owner 确认 pending（RTF-F05 读者级注意）。

### 1.2 KNOWN_BOOKKEEPING_DIFFERENCE 误读风险 —— 文本层不可误读，转录层注册哨兵

- 条目 `type=KNOWN_BOOKKEEPING_DIFFERENCE__NOT_STANDARD_UNCERTAINTY`、statement「不是测量不确定度」、forbidden「禁止记为标准不确定度」三重显式；`standard_uncertainty` 保持 null。
- 残余风险在 CM 转录（条目自述「本条目即不确定度寄存器登记内容…CM 转录时逐字携带」）：五工况数值数组可能被机械抓取为不确定度带。已在 Wave-3b 清单注册共现哨兵（RTF-F02）。

### 1.3 Mqq/ΔM/五工况频带独立复算（scipy.linalg.eigh）—— 全部成立

| 项 | 裁决/e21 声称 | 本代理复算 | 结论 |
|---|---|---|---|
| ΔM 逐字 | [[0.006,0.0024,0],[0.0024,0.0012,0],[0,0,0]] | max-abs 差 5.2e-18（浮点拼写） | PASS |
| 权威 Mqq == 发布卡 | — | max-abs 0.0 | PASS |
| E21-G19 质量阵复现 | 4.999999997368221e-10 kg·m² | 逐位一致 | PASS |
| E21-G20 五工况频率复现 | ≤4.840419126761475e-05 Hz | 逐位一致（全精度 Mqq 口径；发布卡口径 ≤5.47e-05，见 RTF-F08） | PASS |
| nominal 频移 | −3.5096/−6.9411/−13.4000% | −3.509589/−6.941130/−13.400025% | PASS |
| 五工况频移表 | 15 个数值 | 最大差 4.35e-05 个百分点（4 位舍入） | PASS |
| 反向表述 nominal | +3.64/+7.46/+15.47% | +3.6372/+7.4589/+15.4735% | PASS |
| 第一阶带记账差异 | −2.58%..−4.25% | [−4.2509, −2.5825]% | PASS |
| 第三阶带 | ≈−13%（−12.64..−13.43） | [−13.4345, −12.6446]% | PASS |
| 冲突车道 nominal Hz | 6.727892161986368/36.626689494084914/84.87164594535494 | 与 e21 max-abs 2.8e-14 | PASS |
| 质量闭合 | 0.78/1.56/+0.8632134/24.8632134 kg | 3×0.18+0.05+2×0.03+0.08+0.05=0.78；24.0+0.8632134=24.8632134，全精确 | PASS |

### 1.4 逆转条件可执行性 —— RC-3/RC-4 完整，RC-1/RC-2 缺定量阈值

- RC-1「显著偏离 0.03 kg/个」、RC-2「≈13% 不可接受」无数字判据 → judgment-class（RTF-F03，LOW）；逆转机制本身（ECR + ruling_id + sha 引用）完整。
- 附带：「偏刚=偏保守」为工程判读非机器结论，md 已用「方向性判读」缓和；引用须带频率口径限定（RTF-F04，LOW）。

## 2. 对 MPI-FB-08 Gate 的攻击（任务 2）

### 2.1 独立复算抽样（12 组，全部吻合）

1. 桥 sha256 重算 = `0ACEB659284CAB862BA65228C5C2DF4BEB06D9EE05B5E2F0B2B5CB38402BF72C`（钉吻合）。
2. 桥重建：`B = inv(T_S_A0_dyn) @ T_S_A0_phys`（合同哈希钉来源）vs 存储桥 max-abs = **0.0**。
3. 闭包 `T_dyn @ B == T_phys` max-abs = **0.0**。
4. `det(R_B)−1 = max|RᵀR−I| = roundtrip = 5.195843755245733e-13`（与 FB-08 逐位一致，手性 +1）。
5. 派生角 `25.000013999932346°`、轴 [0,0,1]（与 FB-08 逐位一致；桥文件自记 25.000013999964253° 的 3.2e-11° 差已登记，RTF-F07/INFO）。
6. 闭式（Trans z 0.02275 · Rot z 25.000014°）vs 存储桥 max-abs = 4.991562718714704e-13（= 合同 12 位截断登记值）。
7. Steiner witness：m_arm（FB-06 成员行 4.695555949342986 kg）× 0.02275² = 0.0024302436760318294，vs FB-04 发布 0.0024302436760318276，差 1.7e-18。
8. **C02/C06 补抽**（FB-08 原抽 C01/C05/C07）：从 composition_candidate 成员独立重聚合质量/质心/关于系统质心惯量（平行移轴），与 bridged_candidate 差 0.0 / 0.0 / ≤6.9e-18；candidate−stated 质量精确 0；ΔCG 解释残差 ≤1.7e-18；文件自记 ΔI 解释残差 C02=2.64e-16、C06=5.55e-16（九构型最差 5.55e-16 ≤ 1e-12 声称吻合）；FK 残差 C02=1.1314e-07 m、C06=2.72e-08 m（登记拼写带内）；候选惯量 SPD（min-eig 0.468/0.475）。
9. consumer_ambiguity 语义：FB-05/V6/R3 三处 `consumer_ambiguity_count: 0` 逐一在场；单峰 29.41085537835705° 与 acceptance-never-anchor 声明在场。
10. V5 gate 今日重读：HOLD / next_stage_authorized=false / single_consumption_rule_resolved=false；e15 重读：REPEAT_ANCF_CERTIFICATION，交叉求解 0.05637349419858036 > 0.05。
11. 黑名单扫描（decision+gate+fb08 三新文件）：29.226410622980581 / 0.3483933 / 1.7419665 / measured_mass 全部命中均在禁止/声明/探测器语境；decision 无裸「24.0」预算字面量。
12. 哈希哨兵：17 项钉全部吻合；OI-R1-01 drift 按登记复现（6160C1D0… vs 自记 AFE4CA26…）；rt2_static_output.json 重跑钉 A0D0C269… 在 RT2 JSON reproduction_package 内在场（manifest「41/42+1 documented」声称成立）；V6/R3 各恰 1 块 e21 mandatory_holds 与合同 deep-equal；FB-03 21/21、e21 23/23 复核一致；RT2-F01 复核成立（6 位舍入字面量 4.83193000000437e-07 逐位；角度合成 5.18009e-07 与寄存 5.18014e-07 同量级）。

### 2.2 确认偏差（RTF-F01，LOW，文本级）

- V09-01 机器实查口径 = 字符串 `T_PHYSICAL_TO_DYNAMIC` **名称提及**（跳过 08_gate）：definers=1、citers=23（本代理逐位复现）；但 23 个中 **18 个不携带已验证 sha256**（含 round0 先于桥存在的文件与 8 个 .py 生成器）。gate bottom_line「23 other package files cite it, **all with the verified sha256**」表述强于实查。
- 安全属性不受影响：唯一定义文件成立（本代理独立扫描确认）；携带 sha 的主链 6 产品 + 裁决 + gate 文件全部钉 `0ACEB659284CAB86`。
- 处置建议：CM 下一轮文本标注（同 RT2-F01/F02 类），不阻塞 PASS 限域。

### 2.3 nonclaims 完整性（RTF-F06，LOW）

- V5 gate 19 个 false 字段逐一映射：gripper speed / hardware motion / attached recovery / released mass properties / end-to-end dynamics / sim13 binding 等未逐名枚举，但经「V5 HOLD 逐字复核 + mandatory_holds 11 键 verbatim + next_stage_authorized=false / released_segments=0」传递覆盖；collision/contact/target/mission/production/flight/Route-C/owner 均显式在场。**无可利用遗漏**；硬化建议：引用本 gate 的文本加一行「V5 current_release 全部 false 字段按引用逐字保持 false」。

## 3. 柔性阶段新攻击面（Wave-3b/3c 执行计划，任务 3）

十条攻击面已写入 JSON `wave_3b_3c_attack_plan`（W3-ATK-01..10）：ASSUMPTION_BAND 冒充测量、阻尼带编造、频率复现过拟合（调参凑 6.9726）、参与因子符号错（B_t 仅 v_z 行/B_r 仅 ω_x 行稀疏负控制）、振型归一化漂移、分类翻转被平滑、交叉求解对拍 cherry-pick 容差、R1 旧卡静默复用（0.3483933/1.7419665/0.6967866 黑名单）、空比较集=PASS/null→0、不确定度阵逐元素旋转（WP2-AUD-02 先例）。每条含 motive / machine-checkable detection / fail-closed sentinel。

**必打清单**（JSON `wave_3b_3c_mandatory_checklist`）：
- W3b-1 SLOT-07 参与因子产物：Mqq 逐位（max-abs 0）+ 稀疏负控制（应零行 >1e-15 即 FAIL）+ 归一化声明 + 动量账本（>1e-14 即 FAIL）。
- W3b-2 新寄存器：RTF-F02 共现哨兵 + W3-ATK-01/02/06/10。
- W3b-3 RTF-F01 文本标注与 RTF-F03 RC 阈值补注进 CM 转录模板。
- W3c-1 e15 重认证输入包：认证对象=已发布 leaf-only Mqq（T2 未触发口径）；比较集预注册。
- W3c-2 全柔性首运行包：R1 黑名单 + 分类逐字 + ζ=0 守恒车道三前置。
- W3c-3 整星质量引用纪律：24.8632134 kg（非 accepted budget），禁回写 24.0。

## 4. 复核边界（verification_limitations）

- rt2 的 77 文件 watch 与 FB05-13 目录哨兵属运行时观测，本代理未重放；静态部分已由 manifest V2 50 文件 + 17 钉 + rt2 重跑钉覆盖。
- V03-05 的 WP11 物理车道 C_S_inv 重聚合路径本代理未重复；本代理 C02/C06 走成员独立重聚合路径。
- RT2-F01 寄存值与本代理角度合成重建存在 4.97e-12 绝对差（同量级，判定计算路径噪声；标注请求已在 RT2-F01 登记）。

## 5. 纪律声明

本文件不修改/不升格/不逆转 MC-A 裁决与 MPI-FB-08 Gate；不授权任何仿真/CAD/FEA 进程与 e15 重认证运行；不解除任何 HOLD（e15 REPEAT_ANCF_CERTIFICATION、R2-HRN-04 FAIL_REDESIGN_REQUIRED、r2_full_flexible_coupling NOT_EVALUATED、V5 HOLD、Route-C 全 HOLD、owner PENDING 全部逐字有效）；不授予生产/制造/鉴定/发射/飞行权威；GAP-12（24 kg 预算）保持 OPEN；帆板质量/刚度占位（AGENTS.md 待办 3）保持最高优先级开放。
