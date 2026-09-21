# V31 执行器语义与有界能力参考

本包区分轮组内部储存与推力器外部角冲量，提供纯 Python 标准库计算及反例。它不修改历史 registry，不操作设备，不给 C-POD 或当前整机赋予真实推进能力。

## 三个历史数值分别是什么

| 数值 | 正确语义 | 本包处理 |
|---|---|---|
| 0.300 N·m·s | 旧 sim10 轮组档/三轴标量容量之和 | 保留历史含义；不能当任意方向的轮箱容量 |
| [0.1, 0.1, 0.1] N·m·s | CTRL-02 各轴轮动量绝对值上限 | 给定初始储存和需求矢量，逐轴检查最终储存 |
| 5.475 N·m·s | 原注释中 3.65×1.5 的推进力偶外部移除预算示例 | 不称轮组容量，不用作当前 C-POD 能力或本轮任务需求 |

旧字段名 `wheel_momentum_max_Nms` 容易误导。原 `hard_constraints_v1.yaml` 注释说明其来自推力器力偶方案；CTRL-02 装载器把该字段映射为 `external_removal_capacity_Nms`，分配器与轮箱分别计算。`ACTUATOR_CONTRACT.json` 中的映射与 `SOURCE_BINDINGS.json` 保存原字段、来源、字节数及 raw SHA-256。

逐轴箱式储存满足 `abs(H_initial_i + delta_H_i) <= Hmax_i`。从零起点，沿单轴可存 0.1 N·m·s；沿等分三轴方向可存约 0.173205 N·m·s。0.25 N·m·s 的单轴需求虽然小于 0.300，仍会饱和。轮组储存不改变整机总角动量；本包不验证轮力矩、转速、响应时间或真实轮轴安装。

## 合成阵列的严格边界

`SYNTHETIC_ARRAY_REFERENCE.json` 是 `DESIGN_SYNTHETIC_NOT_C_POD_NOT_INSTALLED`。选取 12 个理想开关喷口，在合成参考质心的 ±0.15 m 位置提供三组力/力矩通道；每个喷口全开推力 0.012 N，研究假设最短脉宽 0.020 s、同时最多 2 喷口。上述值是独立选择的研究参数，不能宣称来自 C-POD 指令接口。

`wrench_matrix` 的每列为 `[d; (r-COM)×d]`。前三行是力方向，后三行是米；可分别乘 N 或 N·s 得到力/力矩或线/角冲量。求秩前逐行归一化，不把异量纲行组成物理范数。

满秩 6 只证明线性张成。反例包括：去除反向喷口后线性秩仍为 6，却不能生成负向净力；某个双轴角冲量同时需 4 喷口而违反并发限制；小角冲量对应脉宽低于最小值；指定时窗不足以提供目标冲量。

分配器只评估一种明确计划：每个选中喷口单次矩形脉冲，全部在 t=0 开始，全开推力固定。它不搜索多段/顺序/抵消脉冲计划。返回“该计划被拒绝”不代表任意调度都不可达；通过也不含喷流、电热、阀寿命、推进剂或姿态随时间转动约束。

当前 C-POD 的喷口坐标/方向、并发、最小指令宽及当前整星 COM 没有受控绑定，因此 `actual_C_POD` 保持 UNKNOWN，实际 wrench matrix/rank 均为 null。合成阵列质心设定不得偷偷替代当前未知 COM。

## 消费接口

- `wheel_storage_check(delta_H_Nms, initial_H_Nms, capacity_per_axis_Nms)` → `storage_feasible` 与逐轴余量。
- `wheel_direction_capacity(direction, initial_H_Nms, capacity_per_axis_Nms)` → 单位方向及 `additional_storage_capacity_Nms`。
- `wrench_matrix(nozzles, com_m)` → 6×N 矩阵。
- `matrix_rank(matrix)` → 经逐行归一化的线性秩。
- `allocate_reference_impulse([Jx,Jy,Jz,Lx,Ly,Lz], window_s, reference)` → 脉冲计划、分别计量的残差、约束违反项与 `plan_feasible_within_declared_constraints`。前三项单位 N·s、后三项 N·m·s。
- `current_cpod_capability()` → 当前硬件 UNKNOWN 状态。

## 复现

在本目录使用现有 Python：

```powershell
python -B build_actuator_contract.py
python -B run_checks.py
```

只读历史源文件，所有输出仅写本目录。若已有来源锁与当前源不一致，构建器拒绝静默刷新；应先核对漂移，再另立版本。测试覆盖方向容量、预置储存、六维正反向基向量、单向控制锥、并发、最短脉冲、时窗、未知硬件与非有限输入。
