# Codex Skills（每项为检查清单，按触发条件调用）

## 可执行总控技能

- `$paper-knowledge-orchestrator`：论文来源核验、全文精读、阅读卡、跨文献综合和 claim-evidence 绑定。唯一技能本体见 [`paper-knowledge-orchestrator/SKILL.md`](./paper-knowledge-orchestrator/SKILL.md)，派生状态见 `10_research/knowledge_base/papers/controller_state.yaml`。

## skill 0: research-state-audit（每次会话启动时，任何决策前）
- [ ] `git log/status` + 全部 `*_gate_check.json` verdict + CLAUDE.md 待办区扫描
- [ ] 与手头任务描述比对：目标是否已被裁决判定完成 → 是则上报，不重做
- [ ] 输出真实状态摘要（以 `10_research/research_state_v4.md` 为现行薄指针；v3 仅作
      Wave0 前历史快照）

## skill 5: experiment-readiness（任何硬件/演示排期前）
- [ ] H0 资格项逐项状态（driver/comm/camera/encoder/safety）
- [ ] 演示依赖的仿真工件是否全部 verdict=PASS 且非 PROVISIONAL 关键路径
- [ ] 命名红线自查（只称 ground component validation）

## skill 1: physics-gate-audit（每次代码修改后）
- [ ] 相关 `*_gate_check.json` 重新生成且 verdict 未被手改（diff 只应来自重跑）
- [ ] 阈值与冻结 registry 一致（sim_10 有 `t_s10_registry_hash` 自动化样板）
- [ ] 新结论逐条有 results 文件路径背书；FAIL 未被删除或口头淡化
- [ ] `thresholds_widened=False`

## skill 2: spacecraft-model-audit（引用任何质量/几何/惯量数字前）
- [ ] 数字来自 `20_engineering/config/geometry/` 或 `mass_inertia_budget_v1.csv`（SSOT），非手抄
- [ ] 坐标系/四元数约定与 30_simulation/common 一致（scalar-first, body→inertial）
- [ ] 占位参数（帆板 0.348 kg、T_c 20 ms、执行机构 CLASS 值）引用时带
      PROVISIONAL 标注
- [ ] 冻结锚点数字照抄勿改：19.20° / 3.06°/s / 3.65 N·m·s / 92× / 7.3e-17 / 5.64%

## skill 3: paper-claim-audit（每次写报告/论文文字后）
- [ ] 每个科学主张 ≤ 其证据强度（对照裁决 JSON verdict 与 PROVISIONAL 清单）
- [ ] "SAFE/可行"类声明检查 flex_status 与 next_stage_authorized
- [ ] 与文献审计 Top3 撞车论文的差异化表述到位且不贬损对方
- [ ] 地面实验表述遵守命名红线（见 ground-experiment-agent）

## skill 4: simulation-reproduction（接手任何模块前 / 交付前）
- [ ] 跑该模块 `tests/run_all.py` 全绿并留档
- [ ] 按报告 §复现 命令重生成关键工件，哈希与 `artifacts_sha256` 对拍
- [ ] 生成 reproduction report（谁、何时、哪个 commit、哪些工件、差异）

## skill 6: scope-ownership-guard（多Agent并行，每次写文件前）
- [ ] 输入 task_id/owned_paths/forbidden_paths/baseline_commit；比对本次改动清单
- [ ] 未越他人目录/冻结 30_simulation/阈值/共享接口；无孤立平行实现
- [ ] 越界→立即停止并上报（不自动回滚他人工作）

## skill 7: physics-conservation-audit（CTRL-01/02 每轮实验后）
- [ ] Δp、ΔH、|W−ΔT−ΔU−E_damp| 机器断言（约简精度口径）
- [ ] 每个控制作用强制归属标签：INTERNAL_REDISTRIBUTION / MOMENTUM_STORAGE /
      EXTERNAL_MOMENTUM_REMOVAL / MIXED（账本数值判定，禁手写）
- [ ] 臂内部运动不得表述为移除总角动量；轮组只存储交换；推力器才是外部角冲量

## skill 8: safety-fail-closed-audit（SAFE-00 专用，每次裁决核修改后）
- [ ] UNKNOWN→ALLOW 计数 = 0；数据过期→WAIT；L2 失败禁乐观回退 L0
- [ ] 降级后重查目标层适用域；registry hash 不匹配→ABORT
- [ ] 每决策含有效期 + 证据哈希（provenance 三元组完整率 100%）

## skill 9: control-baseline-reproducer（CTRL 开发前置，LOOP-2）
- [ ] 复现 sim_05 基座扰动锚（19.199885629572467° 口径）与 sim_11 J* 恒等式
- [ ] 复核 5D/6D 任务零空间维度、现有轨迹/质量参数、执行机构预算
- [ ] 任一基线不能复现→BLOCKED，禁止继续开发

## skill 10: claim-evidence-binder（每个新声明落纸前）
- [ ] claim_id/text/scope/gate_json/scenario_hash/result_csv/figure/commit/
      confidence/allowed_wording/forbidden_wording 十一字段齐
- [ ] 措辞限定在 scope 内（例："C2 在当前任务与参数范围内…"；禁"普遍优于"）

## skill 11: red-team-completeness-audit（每轮对抗审查收口时）
- [ ] planned vs completed reviewers/attacks 对账，coverage_ratio 落盘
- [ ] 关键 Reviewer 未完成时，禁止把"无确认问题"解释为"无问题"
      （sim_11 曾险因 confirmed=[] 空列表误读，此为制度化防复发）
