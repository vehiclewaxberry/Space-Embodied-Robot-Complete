# 14 当前状态增量（CURRENT_STATE_DELTA_20260827）

- 生成日期：2026-08-27；生成者：综合代理 SYN-C。基准面：继承包 `PROJECT_ONBOARDING_PACKAGE/`（生成于 2026-07-29，`PROJECT_TRUTH_INDEX.json` `$_meta.generated_utc`，sha256 `e348749b9525`）与 AGENTS.md（08-25 口径，`3d2269562678`）。本文件只登记增量/差异，不改写任何历史裁决。

## A. 相对基准面的新增事实（仓内可核）

| # | 增量 | 证据指针 | 处置 |
|---|---|---|---|
| A1 | **HEAD 停在 2026-08-08 且 130 untracked**：`git rev-parse HEAD`=`5c5addea00ddb70d86a5cc37a88bbcda50350e43`；`git log -1 --format=%ci`=`2026-08-08 01:24:43 +0800`；`git status --short`=141 条（11 M + 130 ??，目录级），含 AGENTS.md 本身、`01_project/current/` 整层、机械 R2 终局目录、sim_13/14/15、e17–e23、r2_* 等 08-08 后全部终局证据 | compdeliv fragment §C.1；SYN-C 复算一致 | B-CD05（P0），Owner 决策锚定方式 |
| A2 | **ODR-60 Option A 已被 Owner 选择，但预搜索 fail-closed**：`OWNER_SELECTION_RECORD_V1.json` verdict `ODR60_OPTION_A_SELECTED__LOW_MEMORY_OVERRIDE_EXPLICITLY_NOT_AUTHORIZED__PRESEARCH_GATES_STILL_FAIL_CLOSED`（`a88e2301b36d`）；执行收口 Gate 8 项 blocker：0/9 场景绑定、**0/11166 clearance 策略行**、0/150 运动证书、0/11166 对 oracle、内存准入未过（`869a248050fd`） | mech fragment 新发现 2 | 维持 KNOWN HOLD；Route-C 只读跟踪（`10` 计划 5% 资源） |
| A3 | **Route-C V9F 被 M01 精确负见证终局否决**：raw -10.729480331980062 mm / gated -17.313396996697108 mm，43 节点/19 binary64 逐位一致；几何循环额度 0；不证明替代路径不存在（UNKNOWN_NOT_SEARCHED） | `ROUTE_C_V9F_MANDATORY_M01_FALSIFIER_GATE.json`（`09c3199bd982`）；`ROUTE_C_V9F_TERMINAL_RULING.json`（`09611ddb8adc`） | 终局负结果，叙事不得移除 |
| A4 | **B4G 合成接触 campaign 注册失败**：3 例 B4F-G06 能量-功恒等式失败；机理=冻结离散第一定律显式中点二阶截断缺陷（仅 slots 82/84/88，经验阶 2.011–2.080）；`original_b4g_final_credit=false`、`new_physics_campaign_executed=false` | `SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json`（`2743fbd314cc`）；R1 闭环门（`ae7e81f66cf6`） | fail-closed 条件 8 已正确触发冻结；材料禁引 v4 合成接触任何数字 |
| A5 | **`physics_agent/README.md` 缺失**：被 `AGENTS.md` 第 13 行（`3d2269562678`）与 `.codex/agents/space-embodied-intelligence-research-agent.md` Startup #3（`5d8780878956`）引用，但 2026-08-27 `find 10_research -iname '*physics_agent*'` 零匹配（SYN-C 复核零匹配一致） | embodied fragment §2.11 / BLK-E07 | P2；补建薄索引或修正两处引用 |
| A6 | **PUBLICATION_HOLD / PAPER_KNOWLEDGE_INTEGRITY 仓内零命中→前次审计状态无法仓内核实（UNKNOWN）**：`grep -rl PUBLICATION_HOLD`（排除 .git）零命中（SYN-C 复核一致）；`PAPER_KNOWLEDGE_INTEGRITY` 仅出现于 `.codex/skills/paper-knowledge-orchestrator/SKILL.md` 第 104-109 行 verdict token 定义（`ca0987b18595`），是技能定义非审计裁决；分支名 `publication/stage3-integrity-closure` 暗示该工作线存在但无机器裁决文件 | compdeliv fragment §B.2.6 / B-CD07 | P1；Owner 提供裁决原文或登记缺失 |
| A7 | **sim_10 冻结哈希锁因 REORG04 路径改写失效（FROZEN_HASH_LOCK_STALE）**：commit 284c882 将 `sim_08 assumptions.yaml`、`threshold_registry_core_v1.yaml` 路径字符串改写，SHA 由钉住值 `850f49da…`/`400bcedc…` 变为当前 `006c6cc5…`/`75af082a…`；git diff 逐行证实纯路径前缀、数值语义等价；今日重跑 `run_gates.py` 的 R 门必 FAIL；历史裁决 `SIM10_GATES_PASS` 不受影响 | dyn fragment §5.1；`scan_v0.yaml`（`856f1e30de47`） | DYN-B03（P1）；8-28 分钟级重钉并重跑 R 门 |
| A8 | **08-27 两份裁决 ODR-60 token 措辞冲突**：闭环裁决 §2.1 记 token `AUTHORIZE_OPTION_A_FIXED_ENDPOINT_M01_TRAJECTORY_SEARCH` 已 RECORDED（`3eed50dd728e`）；预开发裁决 §1/§5 写「本轮未取得…token」「若 Owner 决定继续」（`7884373ee9fc`）；以机器联合 Gate 为准：`owner_option_a_selection_recorded=true`、`path_search_executed=false`（`55490805d934`） | memory fragment §7 / BLK-MEM-04 | P1；统一口径「分支选择已记录，执行未授权」，不回改原文 |
| A9 | **COMPETITION_SUBMISSION_SCOPE 仓内不存在**：全仓 grep 零命中——无更晚比赛提交范围冻结包 | memory fragment §7 | 本审计 `09` 状态头第二行即填补该空缺，待 Owner 签发 |
| A10 | **继承包部分 SUPERSEDED**：TRUTH_INDEX 内 CLAUDE.md `cb851e2f…`≠当前 `d6cdd83a9775`、PROJECT_MAP.md `09dd9fa8…`≠当前 `4dcdad08bd74`；机械主线停在 B5.1R1 Phase 1（TIMELINE 第 41 行，`c875df1cb6a5`）；质量数字尾数差异以 L0 层级文件 `4.695555949342986 kg` 为准（`PROJECT_MODEL_TRUTH_HIERARCHY.yaml` 第 25 行，`c3a28ee3d796`） | memory fragment §6 / BLK-MEM-05 | P1；材料禁用继承包状态数字 |

## B. AGENTS.md 核心数字复核表（全部经原始文件复核一致）

| 数字 | AGENTS.md 表述 | 复核值与出处 | 结论 |
|---|---|---|---|
| 19.20° | sim_05 臂致基座姿态扰动峰值 19.20° | `30_simulation/sim_05_free_floating_arm/results/sim_05_base_attitude.csv` `base_dev_angle_deg` 601 行 max=**19.199852°** @ t=8.00 s（`d543fff76f13`）；README L113（`181eba2721e7`） | 一致 |
| 7.3e-17 | 动量守恒 | sim_05 README 第 96 行 dyn2 测试行 worst residual 7.3e-17<1e-10 | 一致 |
| 3.06°/s | sim_06 碎片@3°/s 捕获后 3.06°/s | `results/capture_impulse_matrix_v0.csv` **第 15 行** `post_rate_full_dps=3.06333`（`8cbad84b8ff6`）；精确值 3.0633304945807067 见 sim_10 gate `$.gates.X1_anchors_vs_sim06.checks[0].w_plus_dps`（`4dbd8c91ff34`） | 一致 |
| ≈92× | sim_07 点捕获激振 vs 刚性锁定 ≈92×，振铃 37–75 s | `results/task_response_summary.csv` 6 行比值 92.1–92.4×、`t5pct_s` 列 37.03–75.17 s（`df29073bdb6c`） | 一致 |
| 3.65 N·m·s / 12× | sim_08 150 kg 碎片消旋 | `results/actuator_budget_sweep.csv` `target_debris_v0,3.0` 行 `H_Nms=3.65099`（`1f0d45349565`）；README 第 22-23 行 12×（`778e2ffaaa09`） | 一致 |
| 5.64% | e15 交叉求解最大差 5.64%>5%→REPEAT | `e15_ancf_certification/results/gate_summary.json` `$.cross_solver_diagnostic.max_relative_difference=0.05637349419858036`、`$.overall=REPEAT_ANCF_CERTIFICATION`（`aab4d609e219`） | 一致（维持 REPEAT，不删除） |
| SIM10_GATES_PASS / 双锚点 | sim_10 9000 点四门 fail-closed，μ=6.25→3.0633°/s INFEASIBLE_RATE、μ=0.917→1.3872°/s WHEELS_ONLY | `sim_10_gate_check.json` `$.verdict`、`$.scan_summary.n_physics_points=9002/n_gate_rows=72016`、X1 双锚点逐位（`4dbd8c91ff34`）；G1 单调性证伪 `worst_dip_rel=0.010790032932416973`@μ=0.5141 | 一致（但 R 哈希锁对当前树失效，见 A7） |
| SIM12_PHASE1_GATES_PASS / 16 例 / S3a 省 13× | sim_12 策略证明集 | `sim_12_gate_check.json` GS1 `max_eps_H=3.849848861643484e-16`、GS2 `best_per_case`（`a416c1348111`）；S3a 3.0 g vs ~40 g 见 `docs/strategy_comparison_report.md` 第 13/20 行（`5bb7c6a71677`）；S2 分账 |ΔH_vec|=1.43508 见 `momentum_ledger.md` 第 30 行（`77e34aff3e28`） | 一致 |
| SIM11 …PROVISIONAL_PARAMS / T_c=20 ms 占位 | sim_11 v1.1 | `sim_11_gate_check.json` `$.verdict`、`$.provisional_fields` 五项（`9309f5325271`）；`scene_A2_capture.yaml` 第 25 行（`4b979a1dfd18`）；G1 窗内守恒 2.7346180875298387e-14、G2 能量审计 8.459748222451578e-11 | 一致（占位声明必须随引用） |
| 0.2714% / 1.81e-05 / 33/33 | E23 耦合重认证 18/18 | `E23_R2_FULL_FLEX_COUPLED_GATE_V1.json` `$.key_metrics.hf_to_rom_seven_mode_max_relative=0.0027143911284986865`、`cross_solver_max_relative=1.8136532292893113e-05`、`rigid_degeneration=0.0`（`1ad4993fd9df`）；独立重算 `E23_INDEPENDENT_RECOMPUTE_V1.json` `$.summary passed 33/33`（`93951e31f20e`） | 一致（PENDING_OWNER_REVIEW、无 release credit） |
| 31.022864807342987 kg | Unified R2 总质量精确值 | accepted URDF 惯性账本合计：`20_RED_TEAM.json` RT-04 evidence（`f3981655c383`）；发射回执 `checks.total_mass_exact=true`（`957ca67d7bcc`）；Sim13 配置真值同值 | 一致（as-built 计量 EXTERNAL HOLD） |
| 5.63e-12 | CTRL-01 能量账本修复后 | `control_01_gate_check.json` `$.gates.GC1_B.energy_audit_relative_max=5.6325998524987115e-12`（`ab1fd26978f4`） | 一致（CTRL-01 仍 REPEAT） |
| 47/47 / unknown_allow=0 | SAFE-00 | `safety_00_gate_check.json` `$.metrics.unknown_allow_count=0`（`ff56929dd835`）；`results/evidence_manifest.json` passed=47/47（`056778011c4b`） | 一致（next_stage_authorized=false） |
| 7/16 / 21.5% | CTRL-02 窗口稳定数与量子残差 | `control_02_gate_check.json` `$.experiment_summary.n_stabilized_within_window=7`（`240fa708b536`）；`wave1_gate_check.json` 第 286 行残差=门槛 21.5%（`ef49240d9047`） | 一致（仅 R5 PROVISIONAL 模型下） |
| 17/17 | COMPETITION_DEMO_READY | `competition_gate_check.json` `$.checks_passed=17/checks_total=17`（`8b3cdbdaa09e`） | 一致（口径冻结 07-20） |

## C. 双口径登记（Sim13）

- **父口径（冻结）**：`18_SIM13_PREEXECUTION_GATE.json` `$.nc_state="15/20 (NC15/NC16/NC18/NC19/NC20 dependency_hold)"`（`af24635327dc`）；prebind gate `maximum_current_operational_state=ABORT_ONLY_WITH_SOURCE_ONLY_ANALYTIC_PREBIND_DIAGNOSTICS`（`dbfff803a656`）。
- **子口径（append-only，更新）**：`SIM13_20_OF_20_GATE_V1.json` `$.nc_score="20/20"`、61 pytest（`4a813f2ee3b0`）；注册表 `SIM13_V2_FULL_REGISTRY_20_OF_20_V2.json` `$.summary executed=20/passed=20`（`a38f82538bf7`）；addendum `full_tmg6_reissue_executed=false`、`historical_15_of_20_superseded=false`（`144e09124ce2`）。
- **索引层承认并存**：`01_project/current/CURRENT_GATE_MATRIX_V1.csv`（2026-08-27 02:35 重建，`824cdcfd1f53`）同时登记四行并标注 `FULL_TMG6_NOT_REISSUED`；联合 Gate（`55490805d934`）已吸收 20/20 仍 HOLD 4/13。
- **引用规则**：任何对外表述必须双口径并置且最高运行态恒为 `ABORT_ONLY_WITH_VALIDATED_FAIL_CLOSED_BACKENDS_20_OF_20_NC__PRODUCTION_NON_ABORT_STILL_MASKED_BY_12_GATE_AUTHORITY`；只引其一即失真。

## D. 未变化确认（防止把增量读成全面变更）

- 管理默认状态未被更晚 Owner 决定覆盖：MECHANICAL_MAIN_BODY=FROZEN / ACTIVE=ROUTE_C_ONLY / FORMAL 双 Release=HOLD / OFFLINE_PHYSICS_GATED_DEMO=GO / FINAL_RL_VLA_TRAINING=DEFER / HIL=DEFER / ON_ORBIT_ASSEMBLY=FUTURE_EXTENSION_ONLY（memory fragment §7 核实）。
- 全部历史 REPEAT/HOLD/负结果原样保留（e15 REPEAT、CTRL-01 REPEAT、WAVE1_REPEAT、E22 16/18 HOLD、V9F 终局穿透、B4G 失效注册等），本审计零删除。
