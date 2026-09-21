# Competition Convergence and Assembly Minimal-Proof Execution Report

日期：2026-07-20  
基线提交：`c7f09ab80580f5810d75253fd836d412aa862460`  
演示范围：`DT2_CURRENT_SCOPE_OFFLINE_EVIDENCE_REPLAY`

## 1. Executive verdict

本轮竞争演示链的最终规划与机器判据目标为：

`COMPETITION_DEMO_READY`

该状态只表示：三个冻结场景能够由已验证结果工件进行确定性的离线证据回放，并生成可审阅的解释。它不表示 SAFE-00 已授权下一阶段，不表示系统输出真实执行命令，也不依赖 Assembly Wave A 通过。

ASM-00 必须单独报告为：

`ASM00_BLOCKED_BY_MISSING_PARAMETERS`

ASM-00 的阻塞不会向上改写 Competition Demo 的证据链，但它明确禁止 ASM-01/ASM-02 启动。当前 H0/H1/H2 均未启动，B601 运动仍被禁止。

## 2. Verified competition chain

演示链冻结为：

`mission input → SIM10 feasibility → SIM12 strategy selection → SAFE-00 authorization evidence → CTRL-02 attitude/resource evaluation → OFFLINE deterministic replay → EXECUTE / MODIFY / ABORT explanation`

机器验证结果：

- frozen artifact registry：9 个工件全部通过原始哈希、规范化哈希、来源提交和关键状态检查；
- evidence contract：`PASS`，Git scope violations 为 0；
- automated tests：`19/19 PASS`；
- red team：`15/15 PASS`，所有攻击均被 fail-closed 拒绝；
- replay：两次构建位级一致，`command_emitted=false`；
- 水印：`OFFLINE EVIDENCE REPLAY`、`NO REAL-TIME SYNCHRONIZATION`、`NO COMMAND OUTPUT`。

主证据哈希：

| Artifact | SHA-256 |
|---|---|
| `mission_demo_contract.yaml` | `0a6aab02cc44bf009e7c1c2f85211d7f8532f50795bebd21cd34c29f60c89126` |
| `three_scenario_manifest.yaml` | `5d0f6104ade666d65b2ba8f6ff466bc0972cad9f11257e32bab135f12226e1ec` |
| `competition_claim_evidence_matrix.csv` | `650e37df5028f7e6336b37c8181f6c41c5a8183be2b7bf596e9ce8680fd47c4c` |
| `evidence_verification.json` | `9cc7407734e597101d318f8cef460624e004112af576c93cb37dc06c05bad31c` |
| `test_report.json` | `426e94efd11f16d26d1728a68eee6ed148df07481281e75cbf48d96b32d1c143` |
| replay package content | `2e2b715f84417a6082da12e38b3b6f6d4cf9801a4d5c2113a01032774833ae83` |

## 3. Frozen demonstration scenarios

### A_low — EXECUTE explanation only

- mission input：22 kg，0.5 deg/s，`PROVISIONAL_LOW_CONFIDENCE_MASS`；
- SIM10：只提供全局 Gate，`join_status=GLOBAL_ONLY`，不存在该精确场景行；
- SIM12：精确命中 `A_low | S1_passive`，结果为 `FEASIBLE`；
- SAFE-00：候选绑定精确，但 Gate 仍为 `PENDING_REVIEW` 且 `next_stage_authorized=false`；
- CTRL-02：精确引用 A_low/B1 资源评估；外部表述必须为 `PASS_WITH_PROVISIONAL_SCOPE`，L0 硬件有效稳定性仍是 `NOT_EVALUATED_NO_ACTUATOR_DYNAMICS`；
- 显示动作：`EXECUTE`，仅为解释性推荐；`execution_authority=false`、`command_emitted=false`。

### B_anchor — ABORT upstream

- mission input：150 kg debris，3 deg/s，低可信度质量输入保持可见；
- SIM10：精确锚点为 `INFEASIBLE_RATE`；
- SIM12：四个冻结策略均为 `INFEASIBLE`，选择 `ABORT`；
- SAFE-00：`NOT_APPLICABLE_UPSTREAM_ABORT`，不创建请求或响应；
- CTRL-02：已有 debris 行只属于 counterfactual，排除出演示执行链；
- 显示动作：`ABORT`。

### C_transition — MODIFY candidate

- mission input：48 kg，2 deg/s，`PROVISIONAL_PROOF_CASE`；
- SIM10：只提供全局 Gate，`join_status=GLOBAL_ONLY`；
- SIM12：`S1_passive` 因 wheel momentum 约束不可行，`S3a_wheel_bias` 可行；
- SAFE-00：没有注册的 C_transition/S3a 候选，`authorized_candidate_binding=MISSING`；
- CTRL-02：只允许 `REFERENCE_ONLY`；CTRL-02 controller 不能被宣称等价于 SIM12 的 S3a；
- 显示动作：`MODIFY`，含义是改变候选并在未来重新进入安全授权链，不是立即执行。

## 4. ASM-00 minimal proof result

ASM-00 结果 Gate SHA-256 为：

`c98639b03bd63b9bb279c6c3d846ac2b7fafa482661618e0f650cfb2e79224b9`

九项 single-source success evaluator contract 已冻结并通过结构验证，但这不是 HAG-A 审批，`authorization_effect=NONE`。RF-1、RF-2、RF-3 的负结果保持如下：

| RF | Machine classification | Evidence |
|---|---|---|
| RF-1 | `BLOCKED` | 缺 mouth/throat guide radii；名义 funnel reduction `2.143593539449 mm` 小于所需 `4.9 mm` |
| RF-2 | `BLOCKED` | `tan(15 deg)=0.267949192431 < μ=0.3`；缺材料对、表面、引用验证和 margin factor |
| RF-3 | `BLOCKED` | clearance 语义未冻结；radial/diametral 两种分支均未形成合格裕度 |
| Shared | `BLOCKED` | 缺 pin spacing 与 chamfer width |

此外，HAG-A/HAG-B/HAG-I 均不存在；Agent A0 工作树中的三项输入还记录了 CRLF 与冻结 LF 原始哈希不一致。规范化内容相同不能替代原始字节等价，因此该差异保留为 blocker。

结论：`ASM00_BLOCKED_BY_MISSING_PARAMETERS`。未执行 physics solver、Monte Carlo、ASM-01 或 ASM-02。

## 5. H0/H1/H2 evidence status

地面组件路径只完成了资格化计划与证据合同冻结：

- `H0 = NOT_STARTED_BLOCKED_BY_MISSING_HAG_E`
- `H1 = NOT_STARTED_BLOCKED_BY_H0`
- `H2 = NOT_STARTED_BLOCKED_BY_H1_AND_ESTIMATOR_GATE`
- `B601_MOTION = PROHIBITED`

本轮没有连接、枚举、上电、解锁、驱动或移动 B601，也没有生成伪造的 H0/H1/H2 PASS Gate。后续必须从有效 HAG-E 与 H0-PRE 只读清单开始，并在每个 Gate 后 STOP。

## 6. Integration red-team finding

首次根目录集成验证正确产生 `FAIL`，原因不是科学结果漂移，而是：

1. Agent C 新工作树将 `strategies_v0.yaml` 检出为 CRLF，原始哈希为 `3660765e…`；主集成目录和 Git blob 均为 LF，原始哈希为 `fb228cf1…`；
2. 原验证器把启动前已有的用户脏文件和 ASM-00 owned path 误判为 scope violation，并对中文路径使用了非 NUL Git 状态解析。

修复仅发生在新建的 competition convergence 合同与验证器中：

- 主集成目录的 LF 原始字节成为唯一运行绑定；
- CRLF 观测值作为负证据保留，不被当作 raw-equivalent；
- 启动前 28 个脏文件逐文件锁定 SHA-256；
- Git 状态改用 NUL 分隔与 UTF-8 路径解析；
- 只允许 Competition、ASM-00 和 competition artifacts 三个精确 owned prefix。

冻结的 SIM10、SIM11、SIM12、SAFE-00、CTRL-02、threshold registry 与策略配置均未被修改。修复后连续两次得到 `19/19 PASS` 与 `15/15` red-team PASS。

## 7. Evidence assets

交付包由以下部分组成：

- machine-readable contract、scenario manifest、claim-evidence matrix；
- `results/replay/` 与 `40_evidence/artifacts/competition_convergence/replay/` 的逐字节一致离线回放；
- 9 页可编辑 PPT；
- 1920×1080 H.264 evidence video；
- 9 张 1280×720 slide render；
- `competition_gate_check.json` 与 `evidence_asset_manifest.json`。

PPT 和视频中的 A/B/C 动作均来自回放记录，不运行任何 solver，不连接外部实时系统，也不产生设备命令。

## 8. Claim boundaries

允许的表述：

- “已完成 verified-artifact-driven deterministic OFFLINE evidence replay demonstrator。”
- “A_low 显示 EXECUTE explanation only；B_anchor 显示 upstream ABORT；C_transition 显示 MODIFY and re-enter authorization。”
- “CTRL-02 的外部表述为 `PASS_WITH_PROVISIONAL_SCOPE`。”
- “九项 ASM-00 success evaluator contract 已冻结，但 ASM-00 当前被参数与授权缺口阻塞。”
- 需要参数前提时只使用 `_WITH_PROVISIONAL_PARAMS` 后缀。

本报告明确不声称：

- completed autonomous on-orbit assembly；
- real-time digital twin；
- free-floating hardware validation；
- markerless VLA generalization；
- flight-qualified safety；
- final flexible assembly certification；
- SAFE-00 已授予真实执行权；
- H0/H1/H2 已完成。

任何 `UNKNOWN`、`REPEAT`、`PENDING_REVIEW`、`NOT_EVALUATED` 或 `PROVISIONAL` 状态均未被提升为 SUCCESS 或真实 EXECUTE。

## 9. Stop and rollback status

本轮在证据冻结后停止。以下动作均保持 `false`：

- start ASM-01/ASM-02；
- start VLA；
- start Wave B；
- start HIL；
- move B601；
- emit command；
- widen thresholds。

若最终机器 Gate 发现任一 frozen hash、scenario action、scope fingerprint、PPT/video结构或 evidence-copy hash 漂移，则竞争裁决自动降为 `COMPETITION_DEMO_REPEAT` 或 `COMPETITION_DEMO_BLOCKED`；不得用报告文字覆盖机器结论。
