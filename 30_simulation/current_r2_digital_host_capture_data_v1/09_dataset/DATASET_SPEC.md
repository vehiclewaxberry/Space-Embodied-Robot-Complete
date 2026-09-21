# 数据集规范（四级，不直接生成"大数据集"）

## 分级

| 级 | 名称 | 状态 | 准入条件 | 用途 |
|---|---|---|---|---|
| D0 | REGRESSION（确定性回归） | **ACTIVE（本增量建立）** | 无 | 数字主机每次更新必重跑的 CI 数据；**不用于宣称学习性能** |
| D1 | PAIRED_STRATEGY（同状态配对策略） | PLANNED | current geometry + 接触/附着权威 | 比赛与论文主数据；复用 sim_12 同状态证明思路 |
| D2 | UNCERTAINTY（不确定性） | **BLOCKED** | 质量/惯量/接触/摩擦/柔性/视觉误差区间具备来源 | LHS/边界延拓/MC/对抗边界搜索；**未知参数禁设正态** |
| D3 | PERCEPTION（视觉合成） | **BLOCKED** | camera frame + intrinsics + current visual geometry | 仅支持感知研究，不替代动力学/接触证据 |

## D0 内容（本增量已实现）

Gate 正例（S00/S01/S02 通过项）、负控（单位/框架/树结构/四元数/变换误用）、SHA 篡改（真实字节翻转）、
缺字段（writer 拒绝）、solver 不收敛（NaN 注入 + 力矩爆散）、`UNKNOWN`/`NOT_EVALUATED`/`ABORT`/`WAIT` 终态。

## D1 合同（预注册，未生成）

同一 `base_state_id` 下并列保存六策略：`DIRECT_CAPTURE / SPIN_MATCH / MOMENTUM_PRESHAPE / COMPLIANT_CAPTURE / PROPULSION_ASSISTED / ABORT`。
所有策略必须共享：初始相对状态、目标质量惯量、抓取点、执行器能力、接触参数、柔性参数、模型与配置 SHA——
**不得改变初始条件后声称策略优劣**（研究问题：局部冲量改善是否造成全局资源恶化；|J| vs |H| 口径分账，sim_12 教训）。

## 存储格式

metadata→JSON；resolved config→YAML；time series→**Parquet**（pandas+pyarrow 已验证可用）；
event log→JSONL；summary metrics→JSON；views/images→PNG；demo→MP4；hash manifest→CSV。

## 每 episode 最低字段

见 `EPISODE_SCHEMA.json`（含 8 类 SHA 绑定、五权威状态、动力学最低通道与 fail-closed 终态字段）。
失败结果不得删除；episode 目录不可变（重跑=新 episode_id）。

## 标签纪律

`EXECUTE / MODIFY / ABORT / UNKNOWN / NOT_EVALUATED` 严格分离；
`NOT_EVALUATED` 不得偷偷转负样本；运行时 `UNKNOWN` 必 fail-closed（见 LABEL_TAXONOMY.yaml）。
