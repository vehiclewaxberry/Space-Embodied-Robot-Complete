# SAFE-00 运行时安全合同

状态：`FROZEN_FOR_SAFE_00_WAVE1`

合同版本：`safety-gate-v1`

策略版本：`safety-gate-policy-v1.2`

## 1. 输入与输出

三份 closed schema 位于 `20_engineering/config/safety_gate/`：

- `safety_request.schema.json`
- `evidence_bundle.schema.json`
- `safety_response.schema.json`

未知字段、自由散文条件、旧动作词汇和不完整 provenance 均在入口拒绝。物理状态只允许
`SAFE / UNSAFE / UNKNOWN`，决策只允许
`ALLOW / MODIFY / WAIT / BACKOFF / ABORT`。

## 2. 候选场景行绑定

当前唯一注册候选是 `A_low-S1_passive`。每次裁决都重新读取并验证：

1. sim_12 `strategy_results.csv` 的规范化表哈希；
2. 唯一键 `{case: A_low, strategy: S1_passive}` 及规范化行哈希；
3. `strategies_v0.yaml` 的规范化文档哈希与 `cases.A_low` 哈希；
4. `scan_v0.yaml` 的规范化文档哈希与 24 kg 质量比参考；
5. candidate ID、row ref、动作、几何类、捕获前角速度、质量比、策略 alpha 和 lambda。

名义 `CAPTURE` 状态必须是 `G2_cubesat`、`omega_dps=0.5`、
`mu=22/24`、`alpha=0`、`lambda=1`。错误行、任意 candidate、源文件篡改或派生状态
不一致均返回 `UNKNOWN/ABORT`。

sim_10、sim_11 和 e15 Gate 只能按策略白名单声明
`GLOBAL_GATE_NON_SCENARIO`；其 row ref 不得被解释为候选场景行。sim_11 的
`sim11:G1/G4/G5` 仅是全局门证据。

## 3. 时间合同

时间字段全部进入 `scenario_hash`，包括 request timestamp、captured_at、decision time、
deadline、各 valid_until 与证据行有效期。冻结顺序是：

`captured_at <= request.timestamp <= decision_time <= deadline/valid_until`

策略同时冻结：

- `max_clock_skew_s=0`
- `max_capture_age_s=2`
- `max_request_to_decision_s=2`
- `max_deadline_horizon_s=240`
- `max_validity_horizon_s=300`

未来数据或非法期限返回 ABORT；已过期但结构合法的证据返回 WAIT。修改期限但不重建
scenario hash 会先触发 `SCENARIO_HASH_MISMATCH`。

## 4. 哈希与 provenance

Gate JSON 使用 `CANONICAL_JSON_SHA256_V1`：严格解析 UTF-8 JSON，拒绝重复键及
NaN/Infinity，再以排序键、紧凑分隔符和 UTF-8 计算 SHA-256。CRLF/LF、缩进和对象键
顺序不影响哈希，字段语义变化会阻断。

sim_12 CSV 与 YAML 案例来源分别使用
`CANONICAL_CSV_TABLE_SHA256_V1`、`CANONICAL_CSV_ROW_SHA256_V1` 和
`CANONICAL_YAML_SHA256_V1`。冻结 threshold registry 继续使用 raw-byte SHA-256，
不做规范化、不修改文件。

输出 provenance 保留：

- Gate 路径、哈希模式、哈希和 verdict；
- artifact scope、row ref 与结构化 row binding；
- `model_level`、`certification`、`provisional_flags`、`flex_status`；
- registry hash 与 scenario hash。

## 5. HMAC 授权

`ALLOW/MODIFY` 只能由显式注入的至少 32 bytes 密钥生成 `HMAC-SHA256` 授权。授权绑定完整响应、
key ID、`not_before`、`expires_at` 与执行要求。验证器必须同时确认：

- `physical_state=SAFE`；
- provenance 完整且记录非空；
- reason、decision 与 modified action 合法匹配；
- `not_before <= now <= expires_at`；
- HMAC 使用调用方提供的预期密钥和 key ID 验证通过。

生产未提供密钥、密钥为空或少于 32 bytes 时，均 fail-closed 为
`AUTHORIZATION_KEY_UNAVAILABLE`。仓库内公开
`TEST_VECTOR_SAFE00_V1` 只用于测试和 Gate，明确不是生产 secret。

## 6. 边界

机器 Gate PASS 不等于获准进入下一阶段。sim_11 参数仍有 PROVISIONAL 项，e15/L2
仍为 `REPEAT_ANCF_CERTIFICATION`。LOOP-6 修复后的独立复审尚未完成，故
`review_status=PENDING_REVIEW`、`next_stage_authorized=false`。
