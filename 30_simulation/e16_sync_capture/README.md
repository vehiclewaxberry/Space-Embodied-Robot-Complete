# P0-C 同步捕获 216 例刚体快算报告

日期：2026-07-14
冻结基线：`6c15395f444f693adad6ff0dfc9a3cfc0b4cf310`
实验：`P0-C-216-rigid-sync-20260714`

## 结论先行

- 终态记账：**216/216**，门禁通过。
- 实际完成刚体动力学：**18** 例；沿用冻结 Line A 后有 **198** 例在几何/IK 上游被拒绝，均记为 `N/A`，没有把未运行量伪装为 0。
- 刚体核心约束通过且柔性未知：**0** 例；正式 `SAFE`：**0** 例。所有新 α 状态的柔性证据均为 `UNKNOWN`，所以 `safe_claim_permitted=false`。
- 可重复性：两次独立 216 例运行的规范化行摘要一致，SHA-256 为 `bd972b6908a821f0c4ade06e80b1cb066cdc13f46e9b6c50c2f23a1504eac0f0`。
- α 的配对比较只覆盖 **6** 个完整动态块；这是确定性设计点，不作为随机总体显著性推断。
- Top-20 请求只有 **18** 个动态有效候选可供排序，因此交付真实的 18 行，不以几何无效案例补足名额。

## 模型和边界

期望末端扭量在惯性系 `I` 中定义为：

`xi_EE_des_I = alpha * xi_G_I + xi_closure_I`

其中顺序为 `[vx, vy, vz, wx, wy, wz]`，线速度单位 m/s、角速度单位 rad/s；`xi_closure_I=[-v_close*n_out_I, 0]`，正的闭合速度沿目标外法向的反方向靠近表面。随后用 `diag(R_BI,R_BI)` 转入基座坐标系求解零总动量自由漂浮末端跟踪。

捕获仍采用冻结 E1.5 的两阶段刚体定义：先用 6-D Delassus 冲量闭合接触相对扭量，再把全部关节塑性锁定。表中的“初始捕获冲量”与“锁定冲量”分开，最终角速度和动量需求来自锁定后的组合刚体。

## α 中位数响应

| 指标 | α=0 | α=0.8 | α=1 |
| --- | --- | --- | --- |
| Initial linear impulse [N s] | 0.0639303 | 0.0251757 | 0.0206526 |
| Initial angular impulse [N m s] | 0.00893021 | 0.00177771 | 0.000856916 |
| Terminal base rate [deg/s] | 0.118947 | 2.25805 | 2.80926 |
| Post-capture rigid rate [deg/s] | 3.05946 | 3.05946 | 3.05946 |
| Wheel momentum demand [N m s] | 3.67768 | 3.67768 | 3.67768 |

`α=1` 相对 `α=0` 的中位线冲量下降 **67.70%**、中位角冲量下降 **90.40%**，但终端基座角速度中位数上升 **2261.78%**。同一配对块的最终刚体角速度最大变化仅 **4.943e-12 deg/s**，统计表明确标为 `NUMERICAL_ONLY_RELATIVE_LT_1E-9`。

完整 Friedman、Kendall W、Shapiro-Wilk 和 Wilcoxon/Holm 结果见 `tables/alpha_*.csv`。若最终角速度/轮动量随 α 不变，并非同步无效：在零总动量机械臂假设下，α 主要改变首次接触相对速度与初始冲量，却不能消除目标原有的系统角动量；全锁定后的组合刚体状态仍受总角动量守恒控制。

## G0/G1/G2/G2-Sync

| 策略 | 案例 | α | 归一化初始冲量 | Jlin [N s] | ω+ [deg/s] | 分类 | 约束 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| G0 | P1_tc00_v10mm_pose_6d_a0p0 | 0.0 | 1 | 0.0639311 | 3.05945 | CORE_UNSAFE | POST_CAPTURE_RATE_EXCEED |
| G1 | P1_tc00_v05mm_pose_6d_a0p0 | 0.0 | 0.973933 | 0.0598088 | 3.05945 | CORE_UNSAFE | POST_CAPTURE_RATE_EXCEED |
| G2 | P1_tc00_v05mm_pose_6d_a0p0 | 0.0 | 0.973933 | 0.0598088 | 3.05945 | CORE_UNSAFE | POST_CAPTURE_RATE_EXCEED |
| G2-Sync | P1_tc00_v05mm_pose_6d_a1p0 | 1.0 | 0.119146 | 0.0103263 | 3.05945 | CORE_UNSAFE | POST_CAPTURE_RATE_EXCEED |

## 排名前五

| 排名 | 案例 | α | Pareto层 | 归一化初始冲量 | Jlin [N s] | Jang [N m s] | 核心裕度 | 分类 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | P1_tc00_v05mm_pose_6d_a1p0 | 1.0 | 1 | 0.119146 | 0.0103263 | 0.000428389 | -0.529727 | CORE_UNSAFE |
| 2 | P1_tc00_v05mm_pose_6d_a0p8 | 0.8 | 1 | 0.230192 | 0.0166097 | 0.00175138 | -0.529727 | CORE_UNSAFE |
| 3 | P1_tc00_v05mm_pose_6d_a0p0 | 0.0 | 1 | 0.973933 | 0.0598088 | 0.00902569 | -0.529727 | CORE_UNSAFE |
| 4 | P1_tc00_v10mm_pose_6d_a0p0 | 0.0 | 1 | 1 | 0.0639311 | 0.00892848 | -0.529727 | CORE_UNSAFE |
| 5 | P1_tc00_v20mm_pose_6d_a0p0 | 0.0 | 1 | 1.08999 | 0.0758101 | 0.00879364 | -0.529727 | CORE_UNSAFE |

全部有效候选见 `tables/top20_rigid_candidates.csv`。排序规则在运行前冻结为：Pareto 层 → 核心裕度（差异不超过 `1e-9` 视为守恒数值并列）→ 相对 G0 的线/角初始冲量等权归一化范数 → 终端关节速度 → 终端基座角速度 → 仅最后使用案例编号。Pareto 层本身是对六个“越低越好”的刚体量进行非支配分层；没有修改任何冻结阈值。

## 门禁与限制

- 门禁总体：`PASS_WITH_GEOMETRY_AND_FLEX_LIMITATIONS`；216/216 终态完整、动力学或上游拒绝的去向完整、状态与约束原因完整、两次运行一致。
- 上游限制：冻结 Line A 的 24 个 `(抓取点, 相位, 模式)` 组中，仅 P1/0 s 的两个模式具有选定关节解，因此实际动态覆盖为 18，而非 216。
- 柔性限制：本工作未运行 ANCF，也未把旧候选柔性结果外推到新 α 状态；柔性保持 `UNKNOWN`。
- 统计限制：完整配对块只有 6 个；p 值只作确定性网格的描述辅助，效果量和逐案例响应优先。
- 控制限制：本文只评价终端扭量、刚体冲量与等效执行机构需求，不声称已经实现 MPC、真实轮控/推力器闭环、HIL 或 E2/G3。

## 证据索引

- `results/sync_capture_216.csv` / `.json`：216 例全量记录。
- `results/gate_check.json`：计数、状态、约束、阈值冻结和确定性检查。
- `results/run_manifest.json`：运行摘要和源文件哈希。
- `tables/strategy_comparison.csv`、`tables/top20_rigid_candidates.csv`：策略与候选排序。
- `tables/alpha_median_summary.csv`、`alpha_omnibus_effects.csv`、`alpha_pairwise_effects.csv`：α 统计。
- `figures/alpha_effects.*`、`rigid_pareto.*`、`terminal_accounting.*`：机器生成图。
- `docs/literature_assumptions.md`：在线核验的一手文献与采用/不采用边界。
- `tests/test_report.md`：验收测试记录。
