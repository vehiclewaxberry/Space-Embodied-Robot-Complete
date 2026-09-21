# Phase B4G-R1：注册失败闭环合同

本包只把已失效的 B4G 执行收口成可审计合同。它读取并复算既有 144-slot raw 证据，不调用 B4G 求解器，不生成新物理轨迹，也不恢复原 B4G 的 final credit。

## 冻结裁决

- 原 B4G 仍为 `final_credit=false`。ACTIVE execution source-freeze terminal 为 `B22C4D…F3464`，失效收据为 `2743FB…B1D9`。
- raw 目录严格包含 144 个 JSON、120 个 NPZ 和 24 个无 NPZ 的 A2 `NOT_EVALUATED_NO_A1_SUCCESS` 元数据；本包新增的 264-file canonical inventory 根为 `916F39…43DD5`。
- 仅 slot 82、84、88 超过冻结 G06 `1e-7 J` 门限，均为 `MIDPOINT_COARSE / A1 / alpha=16`。独立 `T-W` 复算与 raw 保存数组一致到 `1e-18 J` 内。
- midpoint 两次二分步长的经验阶精确范围为 `2.01099–2.08035`，按两位小数报告为 `2.01–2.08`。本包裁决为冻结离散一阶定律中的显式 midpoint 二阶截断缺陷；不支持物理漏项或偶发代码故障解释。
- G04 存在 runner/RUN_SPEC 与 validator 的累计作功检查分叉。下一版本必须显式统一，禁止静默删除 validator 检查。
- G12 的 9 个 paired-finite level 全部 `scientific_predicate=false`；eligible pool 为空、`selected_parent=null`，故 24 个 A2 均未评估。修正 G06 不会自动修正 G12。

## 后续边界

`0.25/0.125/0.0625 ms` 仅是 prospective midpoint 候选。旧 raw 中 `0.25 ms` 的最差 G06 余量约 `1.65×`，但 validator 的累计 G04 最薄余量仅约 `1.096×`，因此必须先完成独立的 acquisition-convergence 与 common-initial-state propagation-convergence preflight，再决定是否申请新 campaign。时间单位为 `s/ms`，能量残差及余量单位为 `J`；不把能量门限伪写成 `J/s` 功率门限。

严禁原位调松 G06、删除 alpha=16、以 RK4 冒充 midpoint、令 `W=delta_T`、强塞共享 acquisition 事件或覆盖原始失效证据。

## 复现

在本目录执行：

```powershell
python -B run_phase_b4g_r1_contract_closure.py
```

该命令仅运行本包 pytest、只读 validator 与不导入 validator 的独立 audit。最终 Gate 只能是失败闭环合同 PASS，不是 B4G 科学 PASS。所有物理、current-system、formal NC19、Owner、production 与 next-stage 字段保持 `false`。
