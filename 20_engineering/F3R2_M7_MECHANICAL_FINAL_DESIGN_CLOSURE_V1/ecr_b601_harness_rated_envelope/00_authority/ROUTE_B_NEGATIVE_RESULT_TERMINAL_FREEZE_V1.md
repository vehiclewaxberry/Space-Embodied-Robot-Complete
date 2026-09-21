# ROUTE_B_NEGATIVE_RESULT_TERMINAL_FREEZE_V1 — 人类可读伴随文件

- schema: `ROUTE_B_NEGATIVE_RESULT_TERMINAL_FREEZE_V1`
- generated_local: `2026-08-23T20:36:30+08:00`（HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08）
- generator: KIMI M7 机械终局接管 swarm Wave-4a (ODR-45..49 owner decisions + R2 full-flex closure) — A5 子代理（ODR-48 执行）
- authority: ODR-48
- next_stage_authorized: **false**；release_credit: **false**

> 冲突裁决：同名 YAML 机器文件的结构化字段为准；本 MD 仅为阅读伴随。

## 规范机器头条（canonical machine headline）

```
ROUTE_B_FULL_RANGE_FIXED_EXTERNAL_HARNESS = REJECTED_BY_EXACT_KINEMATIC_SWEEP
```

该措辞由 ODR-48 铸造，是 Route-B 终局负结果的前向规范引用。历史状态字符串在其冻结文件中逐字保留、不被本记录改写：

- `route_b: REJECTED` — `07_release/B601_HARNESS_TERMINAL_GATE_V1.json`
- `CLOSED_WITH_NEGATIVE_RESULT__ROUTE_B_REJECTED__ROUTE_C_TRIGGERED` — `00_authority/ECR_B601_HARNESS_RATED_ENVELOPE_01_WORK_ORDER_V1.yaml` status
- `FAIL_ROUTE_B_MANDATORY_STATES_OR_TRAJECTORIES` — 终局 Gate TMG-4（Harness），note: "never renamed FULL_RANGE_HARNESS_PASS"

## 引用锚点（citation_anchor，V2 机器头条）

| 量 | 值 | 状态/对象 |
|---|---|---|
| clearance_worst | **−11.9938 mm** | @`SWEEP_joint2_09` vs `link3` |
| min_bend_radius | **0.1 mm** | @`CORNER_110000:span_link5` |
| pinch_worst | **−11.9902 mm** | @`HARDSTOP_joint4_hi`（joint5） |

- source verdict: **FAIL**
- source: `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/HARNESS_B601_FULL_FK_SWEEP_V2.json`
- sha256: `DB86348B8276FB2DCEB48DA30D1969948B37AAC4DF6D67D7588D928CF8281FAE`（已复算 MATCH）

## 三套历史口径逐字保留（禁止合并/取平均/交叉引用）

1. **V1 机器头条**：clearance **−11.8667 mm**（@LHS_06 vs link5）、bend **1.081 mm**（@SWEEP_joint5_00:fillet_node_12）、pinch **−11.3573 mm**（@HARDSTOP_joint4_lo, joint5）— `HARNESS_B601_FULL_FK_SWEEP_V1.json`，sha256 `10EA7420BD30CEBA2F07404FB8B731264C2765B0FB11BBA091CCF9B688F6613A`。
2. **V2 机器头条**（规范锚点）：见上表。
3. **圆整叙述值**：collision **−11.86 mm**、bend **2.26 mm**、pinch **−11.83 mm** — `ECR_SOLAR_ARRAY_R2_WORK_ORDER_V1.yaml`（execution_status_2026_08_23_final，约 line 155），sha256 `1FC4CC686F8257BD5EA1BBDEB3CE24E3E299EF07E5815D6324299AA86E263034`。

**禁令**：三套口径永远分别逐字引用；禁止合并、取平均或交叉引用。

## 根因（逐字，源自 V2 failure_analysis）

1. j2/j3 折叠包络：link2/link3 杆件绕各自关节轴最大半径 292.5/277.0 mm，扫满整周方位角；joint1 钟簧盘绕（r=72.05 mm，平面 x=330 mm）及一切近基座走线元素被吞没（最坏 −11.994 mm vs link3 @SWEEP_joint2_09，即盘绕平面处中心线位于 link3 表面内 7 mm）。
2. 角点状态（六关节全在硬限位）使非相邻杆件接触按单关节扫掠设计的跨段（如 link2 −11.6 mm @CORNER_000000，link4 −11.99 mm @SWEEP_joint4_32）。
3. j5/j6 钟簧包绕之间的腕部跨段保留亚等级弯曲（0.10 mm @CORNER_110000）——极端位姿下包绕-跨段连接处残余 Catmull-Rom 尖点。
4. 硬限位处夹捏带达 ≈−12 mm：折叠闭合落在关节接口附近锚定的跨段上。

结论：固定外置线束走廊被消耗；碰撞/弯曲/夹捏约束无法同时满足。`what_would_be_needed`（逐字）：j2/j3 空心轴/滑环走线（vendor/arm 硬件变更），或缩小 harness-rated 运动包络（仅任务位姿+有界关节子集，全折叠状态声明为 transport/service-only 并拆/重穿线束），或关节式导向 dress-pack（新硬件，自带 Gate）。

## 措辞纪律（wording_discipline）

- 允许的声明：**当前受测试的固定外置线束架构无法覆盖完整 accepted B601 hardware envelope**。
- 禁止的越界声明：**任何外部走线从数学上都绝对不可能**（及任何等价的普遍不可能性措辞）。本记录冻结的是受测试候选族的负结果，不是数学不可能性证明。

## Route-C 需求输入

- 登记为 C2 需求：`ROUTE_C_MUST_OVERCOME_ROUTE_B_FAILURE_MODES`。
- 交叉锚定：`08_route_c/02_pre_cad_parametric_guided_route_search/00_authority/ROUTE_C_PRECAD_DIAGNOSTIC_CONTRACT_V1.yaml` 的 `route_b_v2_hard_negative_results_verbatim` 块（逐字），sha256 `46DE7E9D5C4E49060529364535C6B3D5967B7DCB740F8CE2FA8B69A46C7BB5A7`。本记录不编辑该合同。

## 闭合（closure）

- Route-B 迭代关闭：不重开、不重设判据、不再投入机械设计时间。
- 关闭 OI-R1-04（其等待的 Owner 裁决即本规范锚点裁定）；登记簿形式闭合由 CM agent 刷新执行，本记录不触碰任何 `OPEN_ITEMS*.csv`。

## 哈希纪律

- sha256 覆盖原始字节，全 64-hex pins；本记录引用的每个 pin 均在签发时复算并记入 YAML `verification_record`。
- ODR-45..49 决定记录（`00_authority/M7_OWNER_DECISION_ODR45_TO_ODR49_MPI_CONFIRMATION_AND_TERMINAL_PATH_V1.yaml`）签发时仍未落盘（重试约 5 分钟无果），其 sha256 保持显式 **null**，绝不补 0；下游消费者在其签发后自行锚定。
- self_hash_policy: SELF_REFERENCE_EXCLUDED——本文件不携带自身哈希；下游消费者签发后锚定其 sha256（与 e21/V5 manifests 及 02_bridge 同政策）。

## does_not_grant

- 不授权 Route-C CAD 生成或发布；不授权任何 flight/full-range qualification 声明；不授权进入 production dynamics / physical-contact RL / hardware motion；不重开 Route-B；不取得任何 OPEN_ITEMS 登记簿权限。
