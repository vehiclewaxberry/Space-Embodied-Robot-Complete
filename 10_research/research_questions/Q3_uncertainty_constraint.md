# Q3：参数不确定性与约束可信度

## 研究问题

在不放宽冻结阈值、也不把暂定参数包装成真实参数的前提下，如何把质量/惯量、接触时长、柔性参数、执行机构能力和安全阈值的来源可信度传播到可行域与策略结论的可信度说明中？

## 当前裁决

`ACTIVE_METHOD_QUESTION_NOT_QUANTIFIED`

本阶段已能完成“参数—来源—使用模块—状态”的追溯，但没有运行概率不确定性传播、区间分析或新敏感度仿真，因此不能声称结果具有统计鲁棒性。

## 当前发现的关键参数层级

| 层级 | 示例 | 当前状态 |
|---|---|---|
| 冻结模型锚点 | 24 kg 整星参考质量、23.3032134 kg 无帆板刚性舱体 | 可复算闭合，但仍是模型输入而非飞行实测 |
| 低置信度目标参数 | 22 kg 卫星目标、150 kg 碎片目标 | 配置明确标记 `confidence: low` |
| 待实测硬件参数 | B601 动力学质量 4.6956 kg | `confidence: medium`，等待实物称重 |
| 柔性暂定参数 | 帆板频率包络、阻尼、模态数 | 设计假设/暂定；不可当成认证值 |
| 任务/执行机构暂定参数 | 2 deg/s、轮容量档、推力器/比冲、3600 s | 来源和派生链可追溯，但多项未验证 |
| 派生约束 | 推力器总冲量、推进剂预算 | 由根参数代数派生，不能当作独立证据重复计数 |

## 当前可回答

- 哪些参数是冻结模型锚点、暂定值、低置信度目标数据或代数派生量。
- 每个参数由哪些模块消费，修改后哪些 Gate 必须失效并重做。
- 同名或相似参数为何不能简单合并。例如策略扫描的 `0.300 N·m·s` 轮容量档与 E1.5 的 `5.475 N·m·s` Gate 属于不同合同角色。

## 当前不可回答

- 当前可行区域对各参数误差的概率置信水平。
- 结论对联合参数分布的鲁棒性。
- 任何参数的飞行认证精度或供应商保证值。

## 方法边界

本阶段生成的 `20_engineering/parameter_registry/parameter_inventory.csv` 是**只读派生索引**，不是新的配置 SSOT。修改参数仍必须在原配置所有者和新的研究合同下进行。

## FINER 预审

| 维度 | 预审结论 |
|---|---|
| Feasible | 来源审计可行；定量传播需要新任务授权 |
| Interesting | 决定可行域是否可以从“算例”升级到“工程论证” |
| Novel | `UNASSESSED` |
| Ethical | 无新增敏感实验 |
| Relevant | 是；直接影响论文限制、比赛答辩和数字孪生路线 |

## 解锁条件

1. 选定需要传播的不确定参数及其合法取值域。
2. 预注册敏感度/UQ 方法、样本数量、Gate 和停止条件。
3. 参数域来源由实测、CAD/FEA、供应商数据或文献完成证据分级。
4. 新结果与现有冻结结果分目录保存，不覆盖原 Gate。

## 来源

- `20_engineering/parameter_registry/parameter_inventory.csv`
- `20_engineering/config/geometry/`
- `20_engineering/config/mission_feasibility/scan_v0.yaml`
- `20_engineering/config/coupled_scene/coupled_model_v0.yaml`
- `30_simulation/e15_core_coverage/config/threshold_registry_core_v1.yaml`

`last_verified_head: b75352c1c226c0f3e9a4bc9c469b766e06f41616`

