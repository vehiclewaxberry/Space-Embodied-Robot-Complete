# V2 Serviceability Preliminary Design Review

> `STATUS: ACCESS_RESPONSIBILITY_AND_REVIEW_STATES_DEFINED`  
> `TOOL_CLEARANCE_OR_ASSEMBLY_VALIDATION: NOT_PERFORMED`

## 1. Review objective

确保未来 V2 CAD 不只是外观封闭，而能明确回答：

- 从哪个方向访问；
- 先拆什么、后拆什么；
- 哪个 owner 管理工具、连接器和线束；
- 哪些 access/keepout 尚未闭合；
- 哪个 configuration 下评审。

## 2. Candidate access directions

| 对象 | 候选方向 | PDR 角色 | 未闭合 |
|---|---|---|---|
| front mission panel | `+X_S` | robot mount/sensor access owner | B601、工具、连接器净空 |
| rear service panel | `-X_S` | comm/prop/thermal/service access owner | 硬件 envelope、plume/RF/thermal |
| left side panel | `+Y_S` | side access | solar root/rail/deployer conflict |
| right side panel | `-Y_S` | side access | solar root/rail/deployer conflict |
| top panel | `+Z_S` | optional equipment access | frame/harness/tool conflict |
| bottom panel | `-Z_S` | optional equipment access | frame/harness/tool conflict |
| middle equipment tray | null | future replaceable tray owner | extraction direction/connectors |

所有方向都是 `DESIGN_PROPOSAL`，不是已验证装配工艺。

## 3. Preliminary access sequences

### Robot mount access

```text
select SERVICE_ACCESS_REVIEW
  -> suppress independent target scene
  -> display B601 q0 reference and mount keepout
  -> remove front access panel proposal
  -> expose IF-RM-001 tool-access owner
  -> retain primary frame/load-path references
```

此顺序不授权实际拆装，也不定义 fastener。

### Middle-bay service

```text
select middle-bay owner
  -> display relevant side/top/bottom access candidates
  -> display harness and connector owners
  -> choose future tray extraction after hardware selection
  -> record any blocked access as finding
```

### Rear service access

```text
rear panel candidate
  -> service/debug owner
  -> communications/thermal/propulsion reservations
  -> longitudinal harness breakout
```

## 4. Configuration control

| configuration | serviceability purpose | claim limit |
|---|---|---|
| `STRUCTURAL_REVIEW` | 保留主结构，防止面板承担虚假载荷 | topology only |
| `SERVICE_ACCESS_REVIEW` | 显示 panels/trays/tool/harness owners | no validated clearance |
| `DEPLOYED_REFERENCE_Q0` | 显示既有展开参考和负干涉 | no collision safety |
| `STOWED_PROPOSAL` | 未来收拢方案占位 | no flight/deployment claim |
| `EVIDENCE_STATE_REVIEW` | 按状态着色 | no physics upgrade |

## 5. Harness service logic

只建立 longitudinal corridor owner 及各 subsystem branch owner。以下字段保持 null：

- cross-section；
- connector type；
- minimum bend radius；
- power/data/RF separation；
- grounding/strain relief；
- moving joint routing；
- thermal/EMC constraints。

CAD 中的 reference curve 不构成线束设计完成。

## 6. Negative-result policy

- V1 `DEPLOYED_REFERENCE_Q0` 十处静态干涉必须在 service/deployed review 中继承；
- 不能通过隐藏、抑制或移动受控对象把负结果改成 PASS；
- 新发现的阻塞访问或干涉必须记录 configuration、joint state、solar state、suppressed objects 和 claim limit；
- 只有具名 owner 的后续 redesign 和独立复核才能关闭 finding。

## 7. PDR findings

| finding | 状态 | owner |
|---|---|---|
| middle-bay tray extraction direction unknown | `OPEN_PHYSICAL_BLOCKER` | Integration and Maintenance |
| panel fasteners/latches/tools unknown | `OPEN_PHYSICAL_BLOCKER` | Mechanical Interface |
| harness/connector/EMC constraints unknown | `OPEN_PHYSICAL_BLOCKER` | Electrical/Thermal Integration |
| solar root vs side-panel access unresolved | `OPEN_PHYSICAL_BLOCKER` | Deployables/Integration |
| q0 deployed static interferences | `NEGATIVE_RESULT_PRESERVED` | Configuration/Geometry |

## 8. Exit status

`SERVICEABILITY_REVIEW_LOGIC_COMPLETE / PHYSICAL_ACCESS_VALIDATION_NOT_STARTED`
