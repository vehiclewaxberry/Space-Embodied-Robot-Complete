# 参数登记入口

> `DERIVED_AUDIT_ONLY — NOT A CONFIGURATION SSOT`

本目录把散落在既有配置中的高影响参数整理为“值—来源—可信状态—使用模块—解锁条件”索引。它只用于科研认知、论文限制和影响分析，不允许从这里反向覆盖任何配置或 Gate。

## 文件

- [parameter_schema.yaml](parameter_schema.yaml)：新参数记录模板与状态词典。
- [parameter_inventory.csv](parameter_inventory.csv)：当前高影响参数清单。
- [source_consumer_map.csv](source_consumer_map.csv)：来源文件到消费模块/重新验证动作的映射。
- [provisional_parameters.md](provisional_parameters.md)：暂定参数、同名异义参数和升级顺序。

## 状态解释

| 状态 | 含义 |
|---|---|
| `FROZEN_MODEL_ANCHOR` | 当前模型合同中的冻结输入；不等价于飞行实测 |
| `FROZEN_PLACEHOLDER_MODEL_ANCHOR` | 当前结果已绑定，但物理来源仍为占位/设计假设 |
| `PROVISIONAL` | 暂定值；只允许在当前合同内解释 |
| `LOW_CONFIDENCE` | 配置已明确记录低置信度 |
| `DERIVED` | 由其他根参数代数推导；不能当作独立要求重复计数 |
| `MISSION_ASSUMPTION` | 任务层假设，必须与硬件能力区分 |

所有条目的 `modifiable_now=false`，因为 RESEARCH-OS-01 是只读认知层任务。

`last_verified_head: b75352c1c226c0f3e9a4bc9c469b766e06f41616`

