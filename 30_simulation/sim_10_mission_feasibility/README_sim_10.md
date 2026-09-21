# sim_10 — 任务可行域（Mission Feasibility Boundary）

把捕获-消旋可行性当作 (μ, ω̂, 几何类, λ, α) 设计空间上的**存在性问题**：
四门 fail-closed 判定（转速预算/轮组/推力器冲量/消旋时间），9000 点精确
rigidize 矢量解 + 共轴解析对照。只读 import `30_simulation/common/capture_impulse.py`
与 sim_08 冻结工件，阈值经冻结 registry SHA-256 绑定（禁止放宽）。

| 位置 | 内容 |
|---|---|
| `src/feasibility_core.py` | ι(μ) 几何类映射、精确/解析单点解、四门裁决、registry 装载 |
| `src/scan_grid.py` | 主扫描 → `results/sim_10_scan_{physics,gates}.csv` + summary |
| `src/run_gates.py` | X1 锚点 / X2 λ 单调 / X3 sim_08 对拍 / X4 解析对照 / R 哈希锁 |
| `src/figures.py` | F1 可行域主图 / F2 h*-j* 资源平面 / F3 λ 边界族 / F4 δ 场 |
| `tests/run_all.py` | 6 项 assert 回归（锚点恒等/确定性/单调/哈希/守恒/门语义） |
| `docs/sim_10_任务可行域报告_20260718.md` | 中文报告（含两项科学发现与偏差声明） |
| 参数卡 | `20_engineering/config/mission_feasibility/scan_v0.yaml`（零硬编码） |

**科学结论以 `results/sim_10_gate_check.json` 为准**：当前 `SIM10_GATES_PASS`。
锚点：碎片 (μ=6.25) ω⁺=3.0633°/s → INFEASIBLE_RATE；卫星 (μ=0.917) 1.3872°/s
→ WHEELS_ONLY_FEASIBLE。刚体边界，`flex_status=UNKNOWN_NOT_IN_CRITERIA`
（柔性使不可行区只扩不缩的保守性方向声明见报告 §6）。
