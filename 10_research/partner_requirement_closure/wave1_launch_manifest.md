# Wave 1 Launch Manifest — 2026-07-19

## 1–2. 基线与规划提交核验
- 规划基线提交：**7dc6cd7**（纯规划，21 文件 + skills 0–11，零代码混入 ✅）
- 工作树评估：仅 wave1_launch_manifest.md（本文件）+ 01_project/inbox/source_documents/空间机械臂.docx（用户留置）
  未跟踪；无 tracked 脏文件。基线可作 worktree 分叉点。

## 3. Worktree 与分支
| Agent | 分支 | worktree 路径（仓库外兄弟目录） |
|---|---|---|
| SAFE-00 | wave1/safe-00 | ../wt-safe00 |
| CTRL-01 | wave1/ctrl-01 | ../wt-ctrl01 |
| CTRL-02 | wave1/ctrl-02 | ../wt-ctrl02 |
| 集成 | wave1/integrator | ../wt-integrator（前三者全部停止后单独创建） |

创建命令样板：`git worktree add ../wt-safe00 -b wave1/safe-00 7dc6cd7`

## 4. 所有权（file_ownership_matrix.csv 为准，此处摘要）
- SAFE-00 owned：30_simulation/safety_00_runtime_gate/、20_engineering/config/safety_gate/
- CTRL-01 owned：30_simulation/control_01_end_effector_tracking/、20_engineering/config/control_scene/
- CTRL-02 owned：30_simulation/control_02_base_attitude/、20_engineering/config/attitude_stab/
- 共同 forbidden：sim_01–12 冻结区、e15/e16、20_engineering/config/geometry、registry、
  10_research/（除各自 LOOP 报告子目录）、他人 owned 目录、.codex/

## 5. 共享接口冻结顺序（依赖铁则）
① SAFE-00 于 LOOP-1 冻结 SafetyRequest/SafetyResponse schema（PI 批准）→
② CTRL-01/02 可并行做内部基线（LOOP-2/3），但**在 ① 冻结前禁止输出任何
安全分类字段** → ③ 接口分歧＝立即停机上报 PI，禁止并行不兼容合同。

## 6. 各 Agent LOOP 0–7 检查单（通用）
LOOP-0 state-truth-audit（skill 0）→ task_current_state.md；
LOOP-1 合同冻结（单位/参考系/任务模式/错误码/所有权；CTRL 卡的 R1 fix-first
三项在此折入并复核）；LOOP-2 基线复现（skill 9）→ baseline_reproduction.json；
LOOP-3 最小实现（禁复杂优化器/学习件）；LOOP-4 预注册实验矩阵（禁看结果改
场景）；LOOP-5 机器 Gate（JSON 输出 PASS/REPEAT/BLOCKED，禁纯 Markdown）；
LOOP-6 对抗审查（physics/control/implementation 三 reviewer + skill 11 覆盖率
对账）；LOOP-7 证据固化（CSV/JSON/图/命令/哈希/提交号）→ 停。

## 7. 基线复现命令（LOOP-2 逐条）
```
python 30_simulation/sim_05_free_floating_arm/tests/…run（19.199885629572467° 锚）
python 30_simulation/sim_11_coupled_dynamics/tests/run_all.py（27/27；J* 恒等式在内）
python 30_simulation/sim_10_mission_feasibility/tests/run_all.py（6/6；registry 哈希锁）
python 30_simulation/sim_12_strategy_feasibility/tests/run_all.py（3/3；锚逐位）
```
任一不绿 → BLOCKED，禁止开发。

## 8. 实验矩阵（引用 Task Card，预注册）
SAFE-00：七绕过面对抗组 + 正常放行组 + 降级链组（SAFE-00.md）；
CTRL-01：{C0..C3}×{T1,T2(3.0°/s 修正锚),T3}，C3 仅 5D 行（CTRL-01.md）；
CTRL-02：A{0..2}×2 机动 + B{0..3}×sim_12 四例，箱式饱和判定（CTRL-02.md）；
SIM12-P1B：条件触发，预注册选例规则先行（SIM12-P1B.md）。

## 9. 机器 Gate 命令（各模块自带 run_gates 式脚本，输出 *_gate_check.json）
safety_00: GS-A/B/C；control_01: GC1 九项；control_02: GC0 批准制 + GC1–C6；
集成: wave1_gate_check.json（跨模块一致性 + 全局停机条件复核）。

## 10. 红队覆盖要求（skill 11 强制）
每任务 ≥3 reviewer（physics/control/implementation）；coverage_ratio=100% 才可
收口；confirmed=[] 且覆盖率<100% ＝ 审查未完成，不得解释为无问题。

## 11. 集成顺序
三功能 Agent 全部 LOOP-7 停止 → integrator 单跑：合同对账 → 跨模块测试 →
wave1_gate_check.json → claim-evidence 矩阵更新 → wave1_results/ 五件套。

## 12. 回滚与清理
每 Agent＝独立分支，回滚＝丢弃分支+删 worktree（`git worktree remove`）；
主干只接受 integrator 经 PI 批准后的合并；冻结区任何变更＝全局停机。

## 13. 预计运行量
SAFE-00 纯逻辑（分钟级）；CTRL-01 每格 resolved-rate 积分（秒-分级，
4×3×2 口径 ≈30–60 min 总）；CTRL-02 同量级；总算力远低于 sim_10 扫描；
Agent 用量风险见 RK3（分批启动、产出即写盘）。

## 14. 人工批准检查点
CP1 本清单批准（发射授权）；CP2 SAFE-00 合同冻结批准（LOOP-1 末）；
CP3 CTRL-02 的 GC0 动量归属账本批准；CP4 各 Gate 出 REPEAT 时的修复方案；
CP5 integrator 合并批准；CP6 Wave1 终裁（PASS/REPEAT/BLOCKED → 是否进 Wave2）。

---
## 发射裁决：**LAUNCH_READY**
（无硬阻塞：R1/R2 修订已作为 LOOP-1 入口判据编码于 Task Card；外部参数仅
阻塞 Wave2 支线；SIM12-P1B 保持条件触发。等待 CP1 人工批准后开工。）
