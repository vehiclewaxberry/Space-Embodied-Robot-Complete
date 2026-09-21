# NW-04 — ASM-TWIN-00 Offline Assembly Replay

> 性质：Wave A 唯一集成之后的证据包装卡，不是独立科学求解器。  
> 登记角色：`AUTHORIZATION_REGISTRY_ONLY`；本卡是后续包装约束，不是当前实施授权。  
> 基线计划：`10_research/on_orbit_assembly/master_plan.md`。  
> 基线计划 SHA-256：`dea2436daa5e1acdcb043ac56ed4df31d5dcbe107e715e62bdba9903128d2f04`。  
> 授权记录：`10_research/on_orbit_assembly/approvals/HAG-I.yaml`（当前不存在；实施 Agent 禁止创建/修改）。  
> 当前：`NOT_STARTED / BLOCKED_BY_ASM_RESULTS`。  
> 优先级：P3。

## 目标

把真实 ASM-00/01/02 与唯一集成工件编成标准时程、Gate 溯源和离线证据回放，
形成当前化的装配 DT2。

## 前置

- ASM-00/01/02 已产生原始 CSV/JSON/Gate；
- 唯一集成 verdict 已出具；
- 输入 manifest、哈希、scenario/config binding 完整；
- UNKNOWN/REPEAT/BLOCKED 原样携带。

## 最小范围

1. 标准时程：接近、预接触、倒角穿越、柔顺插接、锁紧、验证、退离。
2. 每帧绑定 scenario hash、配置 hash、结果行与 Gate reason code。
3. 同屏呈现接口状态、接触状态、资源、基座、柔性和冻结 single-source success
   evaluator 的全部判据；不得自行固定为八项或九项。
4. 离线、确定性、可移植；不需要网络或实时设备。
5. 构建前后验证冻结科学输入哈希未改变。

## Gate

- 数值关键帧与源 CSV/JSON 一致；
- Gate verdict/reason 不被视觉层重写；
- screening/PROVISIONAL/UNKNOWN 水印不可删除；
- 缺真实时序时不得插值或合成“成功动画”。

## Stop condition

ASM-TWIN-00 离线回放与输入保护报告出具后停止。

## 禁止声明

- DT3 实时同步或 DT4 硬件闭环；
- 动画证明装配成功；
- 固定基座等价于微重力/在轨验证；
- 展示层 PASS 替代科学 Gate。
