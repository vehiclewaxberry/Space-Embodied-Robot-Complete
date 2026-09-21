# R2 动力学—控制系统联合闭环

本目录只做哈希绑定与 fail-closed 汇合，不重写上游科学 Gate。联合合同固定 19 个直接源，并逐行复核机械闭环包/源清单、动力学源绑定/包清单、控制源绑定/包清单；仅固定清单文件自身的哈希而不校验其内部行，不构成闭合。ODR-60 Option A 已由附件第十一节执行代码块首行明确选择，但这只记录研究分支，不等于静态预检、运行内存、碰撞查询、边验证或路径搜索授权。

当前联合裁决为 HOLD：机械静态预检与 G12 交接未过；动力学 DG1 缺 6R/2P 无量纲参考度量、DG2 缺独立全状态守恒；控制任务空间特征长度/权重矩阵未冻结；SAFE 尚待独立复审；Sim13 虽有 20/20 负控，但最大运行态仍为 ABORT_ONLY 且系统绑定未过。

独立红队凭据固定为 `results/R2_DYNAMICS_CONTROL_INDEPENDENT_REVIEW_V1.json`。它必须逐项绑定当前合同、builder 与测试文件，且高危未闭项为零；builder 会在任何新 Gate 写入前验证凭据，并把凭据自身的路径、字节数和 SHA-256 嵌入 Gate，同时把凭据纳入包级 SHA 清单。凭据不反向绑定 Gate 或清单，因此不存在自哈希循环。输出先完整暂存，联合 Gate 最后提交，缺件或校验失败不会先写出新的 `artifact_package_complete=true` Gate。

复现：

```powershell
python -B 30_simulation/r2_dynamics_control_system_closure/src/build_joint_system_gate.py
python -B -m pytest -p no:cacheprovider 30_simulation/r2_dynamics_control_system_closure/tests -q
```

任何 UNKNOWN 均不得自动 ALLOW；本包未调用几何、碰撞、接触、后端推进或 M01 路径搜索。
