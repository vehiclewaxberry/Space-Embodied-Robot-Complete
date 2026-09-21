# Q2：柔性附件—接触带宽耦合

## 研究问题

在自由漂浮服务航天器捕获旋转目标时，有限接触时间、柔性附件模态与捕获后响应之间的耦合，目前能够被哪些模型和 Gate 可信地描述？哪些部分仍因参数暂定或 ANCF 认证失败而不能进入正式安全域结论？

## 当前裁决

`LIMITED_AND_NEGATIVE_CERTIFICATION`

现有证据可说明“为什么必须显式考虑有限接触带宽和柔性边界”，但不能定量宣称柔性使 Paper 1 安全域扩大或缩小了多少。

## 证据分层

| 层 | 证据 | 原始裁决 | 解释边界 |
|---|---|---|---|
| 柔性侧证据 | `sim11` | `SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS` | 守恒、能量审计、退化对比、收敛和交叉求解 Gate 通过；模态、阻尼和接触时长仍暂定 |
| 核心候选 | `e15_core` | `REPEAT_CORE_NO_SAFE_CANDIDATE` | 72 行完整覆盖，但 0 个安全候选；不能把覆盖 Gate 当成科学 PASS |
| ANCF 认证 | `e15_ancf` | `REPEAT_ANCF_CERTIFICATION` | 最终候选交叉求解不可用；历史诊断最大相对差约 5.637%，超过 5% 线 |
| 同步捕获 | `e16` | `PASS_WITH_GEOMETRY_AND_FLEX_LIMITATIONS` | 216 行闭合，但正式安全候选 0；新状态柔性为 `UNKNOWN` |
| Paper 1 主链 | `sim10/sim12` | Gate 均 PASS | `flex_status=UNKNOWN_NOT_IN_CRITERIA`，所以不能生成柔性 Gate 结论 |

## 当前可回答

1. `sim11` 已建立有限接触窗、柔性模态和整星耦合的数值侧证据，并且所有 Gate 在其合同内通过。
2. `sim11` 明确记录 `n_modes`、模态形状、刚度档、模态阻尼和 `contact_T_c` 为暂定字段。
3. ANCF 认证仍为 `REPEAT`，且没有可用于最终候选交叉求解的安全候选。
4. 因此，柔性只能进入 Paper 1 的方法边界、限制和后续验证路线，不能进入正式可行域分类结论。

## 当前不可回答

- 柔性附件使捕获安全边界移动了多少。
- 哪个 ANCF 网格/积分器组合已经对最终候选完成认证。
- 名义 20 ms 接触时长是否对应 B601 真实夹爪。
- 暂定帆板参数是否代表比赛实物或真实在轨航天器。

## FINER 预审

| 维度 | 预审结论 |
|---|---|
| Feasible | 部分；模型和负结果存在，但关键实参和最终候选缺失 |
| Interesting | 直接连接柔性航天器与捕获冲击 |
| Novel | `UNASSESSED`；本阶段不做新颖性声明 |
| Ethical | 无新增敏感实验 |
| Relevant | 是；决定 Paper 1 的外推边界和后续验证优先级 |

## 文献知识锚点

- 已有阅读卡：`liu2022flexiblecapture`、`yoshida2004impedance`、`uyama2012compliantwrist`。
- 已在盘但尚未形成完整卡：`gerstmayr2008elasticline`、`gerstmayr2023exudyn`。
- 明确缺失：`gerstmayr2013ancfreview` 本地 PDF；因此 ANCF 单元族与建模取舍的权威综述闭环仍未完成。

## 解锁条件

1. B601 夹爪接触时长实测或可审计来源。
2. 帆板模态/阻尼/刚度参数获得实测、CAD/FEA 或权威数据支撑。
3. 出现符合核心安全条件的最终候选，并按 5% 交叉求解合同重做 ANCF 认证。
4. 单独批准将柔性判据加入可行域分类的新研究任务。

## 来源

- `30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json`
- `30_simulation/e15_core_coverage/results/core_gate_check.json`
- `30_simulation/e15_ancf_certification/results/gate_summary.json`
- `30_simulation/e16_sync_capture/results/gate_check.json`
- `20_engineering/config/coupled_scene/coupled_model_v0.yaml`
- `20_engineering/config/coupled_scene/scene_A2_capture.yaml`
- `50_literature/references/notes/INDEX.md`

`last_verified_head: b75352c1c226c0f3e9a4bc9c469b766e06f41616`

