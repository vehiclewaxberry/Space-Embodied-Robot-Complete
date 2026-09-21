# 协议修订记录（append-only）

## R1 — 标签分类学：终态 WAIT 的 episode 标签（Run1 崩溃触发）

- 现象：S07 INJ02a（软过期 WAIT）episode 以 `WAIT` 作数据集标签被 writer 硬拒（设计内 fail-closed）。
- 裁决：WAIT 是**运行时决策**（`terminal_decision` 合法取值），不是数据集标签；终态 WAIT 的 episode
  标 `NOT_EVALUATED` + `not_evaluated_reason`（保持窗内判据未渲染）。
- 性质：分类学澄清，不改变任何判据数值。Run1 产物隔离于 `12_results/episodes_QUARANTINED_run1_crash_wait_label/`。

## R2 — S02 收敛判据：舍入底板条款（Run2 FAIL 触发）

- 现象：Run2 三案例 rel_h_drift 均 ~1e-14（比 1e-9 门槛好 5 个量级），但预注册收敛阶拟合在舍入底板上
  病态（drift 序列非单调/比值无意义），`G_convergence_order` 判 FAIL → DH-G0 FAIL。
- 诊断：与 sim_11 v1.0 G4 同族——对不适定量做阶拟合。守恒残差在**每个** dt 都处于 1e-12 以下本身就是
  最强通过证据；此时阶拟合无信息量。
- 裁决（v2 判据，Run3 前冻结）：`rel_drift < 1e-12（全部扫掠 dt）→ PASS_AT_ROUNDOFF_FLOOR`；
  高于底板时仍要求 order ∈ [3.0, 5.5]。**1e-9 守恒门槛与 xcheck 门槛不变。**
- 性质：判据补充（底板条款），非放宽——底板 1e-12 比原门槛 1e-9 严 3 个量级。
  Run2 原样存档：`11_verification/_archive_run2/`、`12_results/_archive_run2/`。

## R4 — S02 收敛判据：成对底板语义（Run3 FAIL 触发，R2 的修正案）

- 现象：Run3 case1（arm_only, dt 扫掠 4e-3/2e-3/1e-3）rel_drift = [1.67e-12, 1.09e-13, 2.58e-14]——
  首值略高于 1e-12 底板，后两值深入底板。R2 条款要求"全部低于底板"才触发底板通过，于是对
  (1.09e-13→2.58e-14) 这对**舍入主导的数据**做了阶拟合（2.08 ∉ [3.0,5.5]）→ 判 FAIL。
- 诊断：R2 底板条款写得不完整。Roache 收敛分析常识：阶拟合只在**两个漂移都在底板之上**时有信息量；
  序列"进入底板"（末值 < 底板）本身就是收敛证据。
- 裁决（R4，成对语义）：
  1) 全部 < 底板 → PASS_AT_ROUNDOFF_FLOOR；
  2) 存在双双高于底板的相邻对 → 仅对这些"信息对"要求 order ∈ [3.0,5.5]；
  3) 无信息对且末值 < 底板 → PASS_ENTERED_ROUNDOFF_FLOOR；
  4) 其余 → FAIL。
  （case1 实际首对 (1.67e-12, 1.09e-13) 亦跨底板，非信息对 → 按 3) 通过；其 order=3.94 恰在 RK4 带内，
  记录为佐证不入判据。）**守恒门槛 1e-9 与 xcheck 1e-8 始终不变。**
- 性质：判据语义修正（阶拟合适用域收窄到有信息数据），不放宽任何数值门槛。
  Run3 v1 判据产物存档 `11_verification/_archive_run3/` 与 `12_results/archive_run3_r2clause/`。

## R3 — S03 名义步长：dt=1e-3 → 5e-4（Run2 饱和诊断触发）

- 现象：dt=1e-3 时 S03 出现 joint6 力矩打满（7.0 N·m cap）+ 动量漂移 0.117；dt=5e-4 时同场景
  taumax=0.020 N·m、漂移 1.2e-13、跟踪误差 3.2e-7 rad——纯数值失稳（最快 PD 关节模态超出 RK4 稳定边界），
  非物理结论。
- 裁决：S03 名义 dt=5e-4；dt=1e-3 运行**保留为预注册负见证**入 s03_summary
  （`negative_witness_dt_1e_3`），不删除不粉饰。
- 性质：数值配置修正 + 真实负结果保留。S03 无 pass gate，claim 仍为 DIAGNOSTIC_ONLY。

## R4 执行闭环 — 本地语义验证完成，时域复跑在预执行门 HOLD

- 中断恢复：确认生产 `scen_dynamics.py` 也已在 Run3 之后被编辑；Run3 旧 CPython 3.13 执行字节码先于任何 import/pytest 无损冻结。
- Run3 归档：`11_verification/_archive_run3/` 与 `12_results/archive_run3_r2clause/`，285 个文件、783797 bytes，源/目标 SHA-256 逐一一致；原 `DH-G0=FAIL` 与 S02 case1 负结果不改写。
- R2 路径勘误：本项目实际 Run2 结果路径是 `12_results/archive_run2_preprotocol/`，不是上文历史记录中的 `12_results/_archive_run2/`。
- R4 生产语义：唯一 helper 要求至少三个 coarse→fine 严格逐次减半点；单点/双点直接 `FAIL_INSUFFICIENT_REFINEMENT_POINTS`；只拟合双端均处于 floor 或以上的相邻对；进入 floor 必须在可测区一致下降；进入 floor 后反弹、倒序、重复或非 2:1 步长均 fail-closed。
- 测试：最终计数与源码 SHA 见 `R4_TARGETED_TEST.log`、`R4_FULL_TEST.log` 和 `R4_ARTIFACT_SHA256.csv`。中断快照中的测试内复制判定已由直接调用生产 helper 的负控替代；旧 13/13 项目基线覆盖未回归，但不声称中断期间的测试文件字节未被替换。
- 预执行裁决：`HOLD_FAIL_CLOSED`，Run4 未执行。阻断一为旧 runner 不支持版本化 output-root，保留的 Run3 活跃 episode 会导致部分覆盖后失败；阻断二为 S02/S03 都从未缩放的 `h_O=[angular;linear]` 六维范数派生指标：S03 标量没有单一合法 SI 单位，S02 的“相对”比值也依赖角/线分量的任意单位缩放，违反 UNIT_CONTRACT 的分列口径；阻断三为 case2/case3 只有单一 dt 点，不满足最终 R4 三点最低要求。
- 结果边界：Run3 S02 case1 数据用 R4 helper 只可得到 `PASS_ENTERED_ROUNDOFF_FLOOR_REEVALUATION_ONLY`；case2/case3 各只有一个 dt 点，按最终 fail-closed helper 为 `FAIL_INSUFFICIENT_REFINEMENT_POINTS`。因此没有“整个 Run3 反事实 PASS”，更不是 Run4 时域结果。最高状态为 `R4_REPEAT_REQUIRED`；父 Gate 未重发，`next_stage_authorized=false`，`release_credit=false`。
- R3 机制措辞收窄：两步长证据强烈支持时间离散失稳，但“最快 PD 模态已被证明跨越 RK4 稳定边界”仍缺闭环特征值/稳定域计算及独立求解器对拍，保留为待验证机制假设。
