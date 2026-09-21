# Sim13 V3 Phase-A：纯内存广义力驱动通用诊断

## 裁决边界

本目录只实现 `SYNTHETIC_ONLY` 的通用数值诊断：手工构造的 6R+2P、8 个广义坐标自由漂浮树仅以 XML bytes 存在内存中，并复用 Sim13 V2 的 `URDFTreeDynamics` 组装 14×14 混合单位质量矩阵。目录内不会生成 `.urdf` 文件，也不会实例化生产机械—具身接口。

当前 Unified-R2 私有构造器与生成入口均未调用。其现行源文件只做 bytes/SHA-256 只读记录，不进入求解器。由于缺少绑定本候选的新鲜 Owner/run/hash/memory 授权，`DYN-G01` 必须保持 `HOLD`；本轮数值通过不得解释为当前系统动力学通过。

## 已实现的 Phase-A 算法

- 零外力、零总动量机械连接：`Vb = -Hbb^-1 Hbm qdot`。
- 约化质量矩阵：`Mred = Hmm - Hmb Hbb^-1 Hbm`。
- 8 个广义坐标/广义力通道的前向与逆向动力学；R 通道广义力为 N·m，P 通道为 N，不作硬件执行器独立性结论。
- 混合单位合同：R 为 rad、rad/s、N·m，P 为 m、m/s、N；质量阵按 R–R、R–P、P–P 等 block 分别声明单位，不存在统一 `kg·m²` 标签。
- R/P 分别采用 rad/m 步长的两级中心差分和 Richardson 外推；该 Christoffel 后端仅为数值诊断。
- 基座位置与四元数的 SE(3) 重构。
- 目标平移 + 非主轴转动完整 6DOF RK4 推进。
- 线动量 N·s 与关于根点角动量 N·m·s 分账；禁止拼成六维异量纲范数。
- 目标同时输出关于质心的自旋角动量，以及关于惯性原点的 `r×mv + spin` 总角动量；惯量非对称超差 fail-closed。
- R/P、平移、速度、角速度和四元数收敛逐项判定，不直接相加异量纲误差。
- 独立审计不导入主约化动力学模块，使用显式 Schur、逐坐标五点差分及三重 Christoffel 和在三个状态复算偏置、加速度与零动量。

## 复现

在本目录执行：

```text
python -B validate_phase_a.py
python -B independent_audit_phase_a.py
```

现行机器裁决为 `results/SIM13_V3_PHASE_A_DYNAMICS_GATE_V2.json`。证据采用无环链：显式白名单 source manifest → ledger/validation evidence manifest → Gate → independent receipt → self-excluded outer manifest。缓存、清单自身和下游产物不会回流进入上游哈希。
