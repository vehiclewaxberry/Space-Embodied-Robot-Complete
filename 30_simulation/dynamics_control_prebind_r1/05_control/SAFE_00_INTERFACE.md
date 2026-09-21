# SAFE-00 Prebind Interface

沿用现行双层语义：物理分类只能为 `SAFE/UNSAFE/UNKNOWN`，决策只能为
`ALLOW/MODIFY/WAIT/BACKOFF/ABORT`。本阶段禁止将其改名后混成一个枚举。

- `UNKNOWN -> ALLOW` 永远非法；
- 请求和响应都必须带 schema/plant/frame hash；
- Route-C、接触、目标或执行器 authority 缺失时最宽只能 WAIT/BACKOFF/ABORT；
- SAFE-00 现有 PASS 仍是 `PENDING_REVIEW` 且 `next_stage_authorized=false`，
  本接口不继承执行授权。
