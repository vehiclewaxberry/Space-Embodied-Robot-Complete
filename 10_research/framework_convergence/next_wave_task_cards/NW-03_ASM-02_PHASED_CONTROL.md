# NW-03 — ASM-02 Phased Assembly Control

> 性质：现有 `10_research/on_orbit_assembly/waveA_task_cards/ASM-02.md` 的最小授权覆盖层。  
> 登记角色：`AUTHORIZATION_REGISTRY_ONLY`；范围摘要不替代原卡。  
> 基卡：`10_research/on_orbit_assembly/waveA_task_cards/ASM-02.md`。  
> 基卡 SHA-256：`595a1803c81d465896dc659d892aac5b6427224e5287b7b671f8a1ce5faf97ec`。  
> 授权记录：HAG-A/HAG-B canonical path 见 `authorization_record_schema.yaml`
> （当前不存在；实施 Agent 禁止创建/修改）。  
> 当前：`BLOCKED_BY_W1_R12_AND_AG0`。  
> 优先级：P2。

## 科学问题

5D 接近—柔顺插接—短程 6D 锁紧是否在同一冻结场景/约束下优于全程 6D 基线？

## 开工前置

1. 固定 `0.01 N·m/轴` 统一口径，重评 Stage-A；重评不关闭 W1-R12。
2. HAG-B 批准 AG0 SSOT v1。
3. ASM-01 状态/接触接口冻结；AC2 正式裁决还需 ASM-01 接触模型冻结。
4. 正式运行必须同时满足 AG0 PASS、HAG-B 与冻结接触模型；任一缺失时只允许
   schema/控制骨架，不产生 AG3 正式裁决。

## 最小范围

- 公平共享的 QP 骨架与 AC0–AC3；权重和场景哈希锁定。
- P0 position_3d → P1 approach_5d → P2 法向阻抗/切向位置 → P3 短程 pose_6d。
- 6D 段机器禁止不存在的零空间控制。
- Wave A 只验证相位切换的 prospective SAFE request 与 fail-closed 语义，账本连续；
  SAFE-00 装配扩展 AG5 完成前不得产生装配 `EXECUTE`。
- success 只读取已版本化、哈希绑定且解决 8/9 冲突的 ASM-01 单源 evaluator；
  本模块只报 control failure rate 与资源/载荷指标。
- 若 ASM-01 success 仍为 `SCREENING_ONLY`，本模块结果不得上推唯一集成
  scientific PASS。

## Gate

- AG1：任务维度、nullity、可达性、限位和奇异裕度。
- AG3：AC1/AC2/AC3 相对 AC0 的预注册比较；负结果原样。
- UNKNOWN、资源超限、未通过 SAFE 或无完整 provenance 均不得 success。

## Stop condition

AG1/AG3 原始裁决出具后停止；不自动进入唯一集成。

## 禁止声明

- CTRL-01 已普遍解决轨迹控制；
- 分阶段方法普遍更优；
- 轮组已满足硬件力矩；
- 自主在轨装配完成。
