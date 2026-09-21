# RESEARCH-OS-01 初始化报告

## 裁决

`RESEARCH_OS_01_INITIALIZED`

科研认知层已经建立，并与当前 Gate、仿真路径、参数所有者和 Paper Knowledge Controller 完成绑定。本裁决只表示“认知与导航基础设施就绪”，不升级任何科学 verdict、不授权新仿真，也不表示 VLA、装配、数字孪生或硬件实验已经实现。

## 已建立的闭环

```text
科学问题 Q1–Q5
  -> Paper 1 理论接口与假设
  -> sim09/10/11/12、e15、e16 模块卡
  -> 参数来源—消费者登记
  -> Paper 1 候选贡献 / Claim–Evidence 矩阵
  -> 允许/禁止表述与解锁条件
```

## 主要产物

| 产物 | 路径 | 内容 |
|---|---|---|
| 科学问题树 | `10_research/research_questions/` | Q1–Q5、范围、FINER 预审、证据与解锁条件 |
| 理论图谱 | `10_research/theory_graph/` | 零基础理论链、机器关系图、假设登记 |
| 模块知识卡 | `30_simulation/module_cards/` | 7 个关键模块/支路的精确裁决、边界和论文用途 |
| 参数登记 | `20_engineering/parameter_registry/` | 29 个高影响参数、10 个来源—使用者映射、模板与暂定项审计 |
| 贡献地图 | `10_research/contribution_map/` | C1–C4 候选贡献和 6 行 Claim–Evidence 矩阵 |
| 来源快照 | `10_research/research_os_01/source_inventory.csv` | 14 个 Gate/文献/控制器真值入口及哈希 |

## 科学主线压缩结果

- Q1 捕获可行域与绑定约束：`ACTIVE_VERIFIED_CORE_LIMITED_SCOPE`，是当前 Paper 1 核心。
- Q2 柔性—接触带宽：`LIMITED_AND_NEGATIVE_CERTIFICATION`，只能进入方法边界/限制。
- Q3 参数不确定性：完成来源追溯，但 `NOT_QUANTIFIED`，不能声称统计鲁棒性。
- Q4 具身智能：`PLANNED_NOT_IMPLEMENTED`，只定义未来安全接口。
- Q5 数字孪生：当前上限为受限 DT2 离线回放，实时/HIL 升级仍阻塞。

## 关键纠偏

1. 当前证据主链从终端捕获状态开始；没有把 `sim01` 误写为 Hill/CW 轨道交会验证。
2. `sim09` 没有总体 verdict，保持 `LIMITED`。
3. e15 core 的覆盖 Gate PASS 与科学 `REPEAT_CORE_NO_SAFE_CANDIDATE` 分开。
4. e16 的总体带限制 PASS 与“正式安全候选为 0”同时保留。
5. `sim10/sim12` 的柔性状态为 `UNKNOWN_NOT_IN_CRITERIA`，未生成柔性安全域主张。
6. Paper 1 的 C1–C4 均标记为候选贡献；新颖性为 `UNASSESSED`，需另做系统检索。

## Paper Knowledge 绑定

控制器当前机器状态：

- manifest 条目：45；
- 本地 PDF：44；
- 完整阅读卡：29；
- PDF 已在盘但尚无完整卡：15；
- 缺全文：1（`gerstmayr2013ancfreview`）；
- 控制器裁决：`PAPER_KNOWLEDGE_READY`。

文献只用于理论、方法、先验工作和边界说明；机器 Gate 继续是本项目科学状态真值。

## 未改变的边界

- 未运行任何科学仿真。
- 未修改任何 Gate JSON、结果、配置、仿真代码或冻结架构文件。
- 未实现 VLA、装配、HIL、硬件控制或实时数字孪生。
- 未放宽阈值、翻转负结果或生成新的安全候选。
- 未提交、暂存或清理用户既有工作区变更。

## 下一合法阶段

建议先执行 `RESEARCH-OS-02_CLAIM_BINDING`：只针对 C1/C2，把现有图、表、Gate 行与论文段落逐项绑定；同时补 `gerstmayr2008elasticline`、`gerstmayr2023exudyn`、`yoshida1999vibrationsuppression` 等关键阅读卡。任何新扫描或模型改动应另立研究合同。

`last_verified_head: b75352c1c226c0f3e9a4bc9c469b766e06f41616`

