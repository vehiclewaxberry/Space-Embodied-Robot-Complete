# ANCF 数值认证报告（P0-B）

- 日期：2026-07-14
- 冻结基线：`6c15395`
- 专用树：`30_simulation/e15_ancf_certification/`
- 最终裁决：**REPEAT_ANCF_CERTIFICATION**

## 1. 结论

本轮没有把求解器返回成功、放宽容差或资源耗尽解释成科学收敛。7 个历史工况均得到类型化结果，未收敛项保持 `UNKNOWN`，所有失败数值字段为空，不进入排序、训练或安全评价。

| Gate | 实测 | 裁决 |
|---|---:|---:|
| 历史失败分类 | 7/7；重现旧大类 6/7；未分类 0 | PASS |
| 静默填零 | 0 | PASS |
| 低振幅 ANCF—模态必选锚点 | 6/6；最大轨迹相对差 0.00819144%（限值 10%） | PASS |
| 附加诊断矩阵 | 8/8；UNKNOWN 0 | 仅诊断，不替代必选门 |
| Radau/BDF 诊断锚点 | 6 组；最大四指标差 5.63735% | REPEAT |
| 网格/步长/冲量趋势 | mesh=True，Newmark dt=True，pulse=True | PASS |
| 最终候选跨求解器 | 不可用；SAFE=0、Top-3为空 | **REPEAT** |

因此，数值基础锚点通过，但候选级最终认证仍未闭合；科学主链不得进入 E2/G3/HIL。

## 2. 独立性与输入保护

- 旧 `30_simulation/`、`src/`、E1/E1.5、VIZ v0 和共享合同均只读；新写入全部位于本专用树。
- 位移坐标非线性 ANCF 使用冻结 Beam 的同一 `M`、弹性力、Rayleigh 阻尼与捕获激励，但不复用旧绝对坐标积分状态。
- 6 个旧输入的 Git blob 与冻结基线一致：6/6；新认证配置不属于旧基线。
- VIZ 保护表自身的 Git blob 未被本轮修改，表内记录的是生成时“源/快照 22/22”声明；但在当前隔离基线中，原源文件存在 0/22，冻结快照 Git blob 可重现预期 SHA-256 的是 14/22。因此本报告不把表内声明冒充当前独立复核通过；该预存差异不属于本轮写入范围。
- 正式数值运行总耗时：192.62 s（低振幅锚点 39.85 s；历史重跑 152.77 s）；原型和本次离线封装时间不计入。

## 3. 历史失败分类方法

每个冻结 case/hash 在当前进程重新构造抓取姿态、基座速度跳变和 ANCF 初值，并分别运行 Radau 与 BDF。每次尝试同时受 30 s 墙钟、100000 接受步和 2000000 RHS 调用限制。`NUMERICAL_STEP_UNDERFLOW`、`RESOURCE_LIMIT_WALL`、`RESOURCE_LIMIT_ACCEPTED_STEPS` 和 `RESOURCE_LIMIT_NFEV` 都归入可审计的 `SOLVER_NONCONVERGENCE`；它们不是零响应。

逐工况证据：`results/historical_attempts.csv` 与 `results/historical_classification.csv`。

### 资源纪律更正

早期探索阶段发现：外层命令超时并不保证其数值子进程一并退出。相关残留子进程已在正式运行前逐个显式终止并确认退出；这些探索耗时和结果均不计入认证。此后正式锚点改为“每工况一个独立可杀子进程”，内部墙钟 12 s，另给 8 s 启动宽限，超限由父进程 terminate/kill；历史重跑则对每个 solver attempt 同时执行 30 s、100000 接受步和 2000000 RHS 调用三重上限。本报告只引用采用这些控制后的两次正式运行。

## 4. 低振幅与离散极限

- 低振幅比例：`0.0001`；Radau/BDF 与线性模态闭式参考同场比较。
- 网格：2/4/8 ANCF 单元；只在小变形极限评估趋势，不外推到候选强激励。
- 容差：`rtol=1e-05/1e-06`；最大步长：0.10/0.05/0.025 s。
- 冲量：瞬时速度跳变与 20/10 ms 矩形脉冲；脉冲时宽减小时检查向速度跳变极限靠近。
- 独立固定步长：线性有限元 Newmark 平均加速度法，dt=20/10/5 ms，与模态闭式解对照。

## 5. 未通过项与止损边界

1. 冻结E1.5为SAFE=0且无名义Top-3；不得用低振幅诊断锚点冒充最终候选。
2. 低振幅锚点通过只能证明实现和线性极限自洽，不能授权历史强激励工况。
3. 墙钟或步数上限是明确的资源终止，不是收敛；放宽容差后的历史成功仍不获得资格。
4. 如要取得最终 `<5%` Gate，必须先产生经核心链认可的候选，再对同一物理输入完成 Radau/BDF、网格、步长、容差和冲量正则化的候选级一致性证明。

## 6. 一手技术来源及对选择的影响

- [https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html)：Radau/BDF用于刚性ODE；按success/status/message分类，不把放宽容差后的返回成功当作收敛证明。
- [https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.Radau.html](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.Radau.html)：采用五阶Radau IIA作为隐式交叉求解器之一，并记录rtol/atol/max_step/Jacobian。
- [https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.BDF.html](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.BDF.html)：采用1至5阶BDF作为独立隐式交叉求解器，并逐项比较物理输出。
- [https://doi.org/10.1006/jsvi.1999.2935](https://doi.org/10.1006/jsvi.1999.2935)：保留项目既有Berzeri-Shabana简化弹性力ANCF形式；本认证不改变旧模型，只做独立极限和离散检查。
- [https://doi.org/10.1007/s11071-006-1856-1](https://doi.org/10.1007/s11071-006-1856-1)：用小变形线性模态极限和网格收敛检查约束ANCF结果解释。

## 7. 机器可读成果

- `results/gate_summary.json`
- `results/run_manifest.json`
- `results/source_inventory.json`
- `results/timing_summary.json`
- `results/low_amplitude_runs.csv`
- `results/historical_attempts.csv`
- `results/historical_classification.csv`
- `tables/cross_solver_differences.csv`
- `tables/discretization_trends.csv`
- `tables/newmark_timestep_trend.csv`
- `tests/test_report.md`
