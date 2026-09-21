# SAFE-00 当前状态

- task_id: `SAFE-00`
- branch: `codex/wave1-safe00-recovery`
- baseline_commit: `926522f199cae3b9d88ee6797089d57300fea994`
- owned paths:
  - `30_simulation/safety_00_runtime_gate/**`
  - `20_engineering/config/safety_gate/**`
- 禁止修改：sim_01～sim_12、`10_research/**`、`.codex/**`、冻结 threshold registry

## LOOP 状态

| LOOP | 状态 | 证据 |
|---|---|---|
| LOOP-0 状态审计 | PASS | sim_10/11/12 与 e15 裁决只读确认 |
| LOOP-1 合同冻结 | PASS | closed schema + policy v1.2 |
| LOOP-2 基线复现 | PASS | 既有测试 58/58，冻结日志哈希不变 |
| LOOP-3 最小实现 | PASS | 每调用重读证据 + fail-closed 裁决 |
| LOOP-4 预注册矩阵 | PASS | 正常 2、绕过 12、降级链 2 |
| LOOP-5 机器 Gate | PASS | SAFE-00 47/47；GS-A / GS-B / GS-C |
| LOOP-6 独立红队 | PENDING_REVIEW | 缺陷已修复，等待独立复审 |
| LOOP-7 证据冻结 | PASS | 全量 tracked inventory、日志、命令和哈希已刷新 |

## LOOP-6 修复

- `A_low-S1_passive` 绑定 sim_12 的 `A_low|S1_passive` 行；
- CAPTURE 使用捕获前 `omega_dps=0.5`，质量比固定为 `22/24`；
- CSV 行、案例 YAML、质量参考 YAML 每次读取并做规范化哈希；
- sim_11 明确标记为全局非场景 Gate；
- scenario hash 覆盖 timestamp、decision time、deadline 与全部有效期；
- 冻结零 clock skew、最大捕获年龄、裁决年龄和期限 horizon；
- 授权改为显式注入至少 32 bytes 密钥的 HMAC-SHA256；生产密钥缺失、为空或过短必 ABORT；
- provenance 输出保留模型级别、认证、临时字段和柔性状态；
- 非确定延迟移出 Gate JSON，单列 diagnostic；
- Gate payload 对相同冻结输入逐位确定。

## 当前机器指标

- `UNKNOWN -> ALLOW/MODIFY`: 0
- 绕过成功次数: 0
- 正常组误 ABORT 率: 0
- ALLOW/MODIFY provenance 完整率: 100%
- `thresholds_widened=false`
- `review_status=PENDING_REVIEW`
- `next_stage_authorized=false`
- 16 个预注册案例 Gate payload 连续两次原始 SHA-256 相同：
  `7a352fe3d511804da3c182ee6380e3c86003173796ab912f5390ec43bb66836c`

残余边界：sim_11 仍含 PROVISIONAL 参数；e15/L2 仍需重复 ANCF 认证；本实现者不能
自行把修复后的 LOOP-6 标为独立复审通过。
