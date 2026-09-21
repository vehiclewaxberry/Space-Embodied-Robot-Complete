# NW-01 — ASM-00 Interface Qualification

> 性质：现有 `10_research/on_orbit_assembly/waveA_task_cards/ASM-00.md` 的最小授权覆盖层。  
> 登记角色：`AUTHORIZATION_REGISTRY_ONLY`；范围摘要不替代原卡。  
> 基卡：`10_research/on_orbit_assembly/waveA_task_cards/ASM-00.md`。  
> 基卡 SHA-256：`8cc31a7769d387c3c709b399fed086e5be10b2e464eb9ffbdbcdd8c20dabd347`。  
> 授权记录：`10_research/on_orbit_assembly/approvals/HAG-A.yaml`（当前不存在；实施 Agent 禁止创建/修改）。  
> 当前：`PLANNED_NOT_AUTHORIZED`。  
> 优先级：P0；Wave A 第一个放行点。

## 科学问题

预制锥—销—锁接口的公差链是否形成自洽、可追溯、可计算的粗对准—精对准—
锁紧捕获域？

## 只允许实施的最小范围

1. 关闭 RF-1：补锥口/喉半径，用几何推导判断 5 mm 粗公差是否自洽。
2. 关闭 RF-2：固定表面/摩擦出处，验证 `tan(15°)` 与楔紧边界；不得单靠改深锥。
3. 关闭 RF-3：明确 clearance 为直径或半径口径。
4. 补销距 `s`、倒角 `w_ch`、来源等级与单位。
5. 对同一 SSOT 做解析公差链与独立 Monte Carlo 碰撞采样对拍。
6. 输出且只输出一个完整 AG0 machine verdict：
   `ASM00_AG0_PASS`、`ASM00_AG0_PASS_WITH_PROVISIONAL_PARAMS`、
   `ASM00_AG0_REPEAT` 或 `ASM00_AG0_BLOCKED_BY_INTERFACE`。

## 输入与冻结边

- 输入：`interface_ssot_draft.yaml`、`interface_mechanics_plan.md`、现有 ASM-00 卡。
- 冻结：sim、CTRL、SAFE、`20_engineering/config/geometry/` 现行文件均只读。
- 新结果只能写入获批的 ASM-00 所有权目录与 `20_engineering/config/assembly/` 新版本。

## Gate

- 单位一致、右手正交坐标系、字段齐全；
- 公差/材料/摩擦均有来源等级；
- 解析与独立几何采样一致；
- UNKNOWN 不转正；
- RF-1/2/3 任一未关闭时，不得输出无条件 PASS。

## Stop condition

AG0 原始裁决与接口 SSOT v1 或 BLOCKED 清单出具后停止；等待 HAG-B。

## 禁止声明

- 接口参数已实测或制造认证；
- 装配已可行；
- 通过放宽公差或改阈值“关闭”红旗。
