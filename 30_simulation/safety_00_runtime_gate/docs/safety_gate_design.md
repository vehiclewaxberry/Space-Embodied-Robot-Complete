# SAFE-00 设计与预注册说明

## 裁决链

`decide(request, evidence)` 按固定次序执行：

1. closed schema 校验；
2. 对 request 与 evidence 的全部决策字段重算 scenario hash；
3. 校验捕获、请求、裁决、截止和证据有效期的时间顺序；
4. 重读 raw-byte 冻结 registry；
5. 重读并规范化哈希 Gate JSON；
6. 重读 sim_12 CSV、案例 YAML 和质量比参考 YAML，验证候选行及派生状态；
7. 验证 artifact scope、模型级别、认证状态、临时参数与柔性状态；
8. 执行分层域、资源、独立物理证据和降级链裁决；
9. 仅在 SAFE、完整 provenance 且显式注入 HMAC 密钥时生成执行授权。

任何一步失败都不能产生 `ALLOW/MODIFY`。

## 候选与全局证据分离

`A_low-S1_passive` 是当前唯一场景候选，绑定 sim_12 的唯一数据行。`CAPTURE` 使用
案例配置中的捕获前 `omega=0.5 deg/s`，不再误用捕获后 `1.387206 deg/s`。

sim_11 Gate 是 `GLOBAL_GATE_NON_SCENARIO`：它证明全局 G1/G4/G5 与临时参数状态，
但不证明 `A_low|S1_passive` 这一场景行。结构化 scope 和白名单阻止二者混用。

## HMAC 与调用模式

核心没有默认授权密钥。生产环境必须由调用方注入至少 32 bytes 的 key 和 key ID；
未注入、为空或过短时，
名义 SAFE 请求也 ABORT。测试与 Gate 通过 `decide_test_vector(...)` 显式使用公开测试
向量，输出 key ID 也明确标记 `TEST_VECTOR`，不得作为生产 secret。

## 预注册矩阵

矩阵 v2 包含：

- 正常 2 例；
- 绕过与错误输入 12 例；
- L2 降级链 2 例。

新增负例覆盖错误 sim_12 行、未注册 candidate、未来 captured_at、deadline 重绑定和
生产密钥缺失。单元测试进一步覆盖 CSV 行篡改、案例 YAML 篡改、公开 checksum 重算、
`UNKNOWN+ALLOW`、空 provenance、期限超界以及 Gate 重跑逐位一致。

## 决定性与诊断

冻结 Gate JSON 不读取 `perf_counter`，不包含延迟。`evaluate()` 对同一冻结输入生成逐位
相同 payload。延迟只由 `run_diagnostics.py` 写入
`safety_00_latency_diagnostic.json`；该文件在 evidence manifest 中按明确规则排除，
不能影响 PASS/REPEAT/BLOCKED。

## Gate 与复审状态

- GS-A：fail-closed 硬规则；
- GS-B：全部预注册绕过面成功次数为 0；
- GS-C：registry、Gate JSON、候选行、HMAC 模式与不放宽阈值均锁定；
- LOOP-6：修复项已实现，但独立复审仍为 `PENDING_REVIEW`；
- `next_stage_authorized=false`。
