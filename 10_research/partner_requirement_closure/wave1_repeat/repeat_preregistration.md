# Wave 1 Repeat 预注册 + CP2/CP3 治理记录 — 2026-07-19（PI: Fable 5）

## 治理记录（补齐集成报告指出的缺项）

**CP2（SAFE-00 合同冻结批准）= APPROVED**。审查依据：integrator 分支
`20_engineering/config/safety_gate/` 合同 schema（additionalProperties:false、规范化
CSV/YAML SHA256 绑定、HMAC 授权、时效字段）已覆盖 R2 七绕过面；integrator
独立复跑 SAFE-00 实现 Gate 全 PASS。批准人：PI Agent（用户 CP1 总授权下）。

**CP3（CTRL-02 GC0 动量归属账本批准）= APPROVED**。审查依据：
`30_simulation/control_02_base_attitude/results/gc0_momentum_ledger.json` +
`docs/GC0_momentum_attribution.md`，归属三标签数值判定、推进剂下界独立复算
16 行零差、+0.001 g 篡改测试正确拒绝。批准人：同上。

## Repeat 预注册（阈值冻结声明）

1. **全部阈值与本轮负结果不可改写**：能量审计 1e-9、闭环锚 0.05°、约束限值
   （0.7 rad/s / 2.0 rad/s² / 0.05 rad 裕度 / 1e-4 奇异值）、逐轴 |H_i|≤0.1
   N·m·s 照旧；C2 −51.91%、C3 整体 −7.99% 等负结果保留在证据链，若诊断
   确认为真实物理则如实入论文。
2. **修复原则**：先诊断"实现缺陷 vs 真实负结果"，只修前者；轨迹重设计属
   预注册修订（本文件即修订注册），禁止看结果后调场景。
3. 六项最小闭环（集成报告 §8）逐项指派：
   - R-1 本预注册提交 ✅（本文件）
   - R-2 冻结各方法 T2@15s 全状态 + 目标 3°/s 相位 → T3 目标/组合碰撞全节点 → CTRL-01-R
   - R-3 C2_MATCH5 比较器 + 能量审计/误差界/约束修复 → CTRL-01-R
   - R-4 任务有效 + 正关节裕度的 Stage-A 预注册轨迹（禁用已撤回 −5° 探针）→ CTRL-02-R
   - R-5 轮力矩/最小推力脉宽/稳定窗冻结（attitude_stab_v0.yaml，PROVISIONAL）→ Stage-B 执行器动态稳定性 → CTRL-02-R
   - R-6 CP2/CP3 记录 ✅（上节）+ 三 reviewer 覆盖审查复跑 → integrator-R
4. 能量审计诊断先验（PI 提示，非结论）：闭环控制经关节做功，审计式须含
   W_ctrl=∫τ·θ̇ dt 项——7.9e-2 量级残差的第一嫌疑是审计记账漏项而非动力学
   缺陷；若查实为记账缺陷，修记账不动门槛。
5. 完成序：CTRL-01-R ∥ CTRL-02-R → integrator-R 单跑 → 新 wave1_gate_check
   → PI 终裁（PASS/REPEAT/BLOCKED）→ 停，不进 Wave 2。
