# Q5：数字孪生证据升级

## 研究问题

如何把当前离线模型、冻结输入哈希、Gate、证据快照和回放能力，逐级升级为可校准、可同步、可审计的数字孪生，而不把“仿真文件齐全”误写成“实时孪生已实现”？

## 当前裁决

`LIMITED_DT2_AND_BLOCKED_UPGRADE`

当前最高可信表述是：已具备离线模型与证据回放所需的部分工程基础。实时同步、参数在线校准、HIL、硬件遥测闭环和在轨孪生均未完成。

## 成熟度边界

| 层级 | 定义 | 当前状态 |
|---|---|---|
| DT0 | 文件/几何/结果可浏览 | `VERIFIED` |
| DT1 | 配置、输入哈希、结果和 Gate 可追溯 | `VERIFIED/LIMITED`，视模块而定 |
| DT2 | 冻结场景可离线重放并对照证据 | 当前规划允许的最高表述；部分模块已有回放资产 |
| DT3 | 与硬件/传感器近实时同步 | `BLOCKED` |
| DT4 | 在线校准并支撑闭环决策 | `BLOCKED` |

本表是项目治理分级，不是新的科学实验结果。

## 当前可复用资产

- 模型/配置 SSOT 与冻结哈希。
- Gate JSON、证据 manifest、图表和回放结果。
- 参数来源—使用者登记，可用于后续校准影响分析。
- 科学问题树和模块卡，可用于定义孪生输出必须回答的问题。

## 主要阻塞

- B601 与柔性附件的关键参数仍缺实测/高置信度来源。
- 无统一时间基准、遥测协议、同步误差 Gate 或硬件在环证据。
- 柔性最终候选认证仍为 `REPEAT_ANCF_CERTIFICATION`。
- `safety_00` 虽为 PASS，但 `next_stage_authorized=false`。

## 解锁条件

1. 定义 DT2 离线回放的输入、时间戳、输出和一致性 Gate。
2. 建立参数校准合同，区分“可识别”“可测量”和“暂定”参数。
3. 另行批准 HIL/硬件数据接入，并建立不可覆盖的原始日志区。
4. 只有经过同步、延迟、回放一致性和安全审查后，才能升级实时孪生表述。

## 来源

- `10_research/00_project_architecture/digital_twin_plan.md`
- `10_research/00_project_architecture/system_architecture.md`
- `30_simulation/safety_00_runtime_gate/results/evidence_manifest.json`
- `20_engineering/parameter_registry/`

`last_verified_head: b75352c1c226c0f3e9a4bc9c469b766e06f41616`

