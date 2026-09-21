# R4 收敛语义与 S03 复跑准入报告

## 裁决

R4 收敛语义实现已通过本地验证，但 Run4 时域复跑没有获得预执行准入。当前机器结论是 `R4_REPEAT_REQUIRED`，不是控制、机械或完整抓取发布。

## 中断恢复与 Run3 谱系

Run3 工件生成于 `2026-08-27T06:53:32.410398Z`；生产收敛源码在其后才修改。归档前保留了旧 `scen_dynamics.cpython-313.pyc`（SHA-256 `9CFCBEF2DEA9CECF060A5BCED9CA85CF649F8E72B4030BB8122DCC505D71BADE`），从而避免 pytest 重编译抹去执行证据。Run3 共归档 285 个文件，全部源/目标 SHA 一致，22 个 episode 完整保留。

## R4 唯一生产语义

`evaluate_s02_convergence` 现在直接承担生产与测试共同判定：

1. 输入顺序必须是 coarse→medium→fine，且相邻步长严格 2:1；函数不排序。
2. 至少需要三个逐次减半点；单点或双点一律 `FAIL_INSUFFICIENT_REFINEMENT_POINTS`。
3. 在满足三点最低数量后，全部误差低于 `1e-12` 才可 `PASS_AT_ROUNDOFF_FLOOR`。
4. 只有相邻两端都处于 floor 或以上的 pair 才进入阶数拟合，阶数必须位于 `[3.0, 5.5]`。
5. 没有信息 pair 时，只有从可测区一致下降并进入 floor 才可 `PASS_ENTERED_ROUNDOFF_FLOOR`。
6. 进入 floor 后反弹、非有限量、反序、重复或错误步长比均失败。
7. 收敛标签与 h/E/xcheck 硬 Gate 分开合成；任一硬 Gate 失败都保持 overall FAIL。

最终定向测试 11/11、完整测试 24/24。中断快照里重复实现判定规则的 test-only helper 已被生产 helper 直测替代；旧 13 项项目基线覆盖未回归，无 skip、xfail、xpass 或阈值放宽。

## Run2/Run3 事实与 S03 解释

S02 arm-only case1 的实际数值在 Run2/Run3 相同：相对 legacy 6D 动量漂移序列为 `[1.6716424722e-12, 1.0912256305e-13, 2.5788020546e-14]`，观测阶数 `[3.9372449787, 2.0811764925]`。Run3 的 R2 条款对底板内第二对拟合而失败；R4 helper 对同一不可变数据给出 `PASS_ENTERED_ROUNDOFF_FLOOR_REEVALUATION_ONLY`。Run3 case2/case3 各只有单一 `dt=1e-3` 点，最终 R4 helper 均判 `FAIL_INSUFFICIENT_REFINEMENT_POINTS`，所以不存在整个 S02/Run3 的反事实 PASS。

S03 在 `dt=1e-3` 时 joint6 达到 `7.0 N·m` cap、跟踪误差 `0.0526326 rad`；在 `dt=5e-4` 时无饱和、joint6 峰值 `7.67028e-05 N·m`、跟踪误差 `3.15112e-07 rad`。这强烈支持粗步长引发离散数值失稳，而不是轨迹持续要求 7 N·m。尚缺闭环特征值、RK4 稳定域定位和隐式/自适应求解器对拍，故不能声称机制已严格证明。

## 为什么 Run4 被阻断

旧 S02/S03 字段都把世界惯性原点的空间动量 `h_O=[angular; linear]` 六分量直接做欧氏范数。Run2 S03 的 `0.117438585` 实际由角动量漂移 `0.069950954 N·m·s` 与线动量漂移 `0.094332843 kg·m/s` 混合而成；该标量没有单一合法单位。Run3 细步长对应两项为 `6.21123e-14 N·m·s` 与 `1.04596e-13 kg·m/s`。S02 虽再除以初始六维混合范数而呈现“相对值”，结果仍依赖角/线分量采用何种单位缩放。因此这些旧值只能作为 legacy 数值回归，不能承担硬守恒或控制发布 Gate。

此外，现有 runner 固定写活跃目录且不支持 output-root；若直接执行，会先覆盖部分当前工件，再因不可变 episode 已存在而异常退出。它还只为 S02 case1 安排三点扫掠，case2/case3 各只有一个点。输出隔离、单位账本和全案例细化日程三项均为预执行硬阻断。

## 唯一下一动作

另开受控 R5：把角/线动量账本拆成各自带单位的 Gate，增加版本化 output-root、run-level source/config/controller 哈希与力矩时序，并为三个 S02 case 都提供至少三个逐次减半点；然后在不改变 plant、初态、增益、cap、场景时长和 SAFE 阈值的条件下复跑相同 S02/S03。R5 之前不得进入接触、完整抓取或控制 Release。
