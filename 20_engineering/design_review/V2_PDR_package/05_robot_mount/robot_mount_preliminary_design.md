# B601 Robot Mount Preliminary Mechanical Design

> `STATUS: TOPOLOGY_AND_INTERFACE_CONTRACT_DEFINED`  
> `LOADS_CONNECTIONS_MATERIALS: UNKNOWN_BLOCKED`  
> `STRENGTH_OR_STIFFNESS_CLAIM: false`

## 1. Design role

Robot Mount Module 是 V2 的核心机械接口，但本阶段的目标不是设计一块“看起来结实”的支架，而是闭合以下工程链：

```text
B601 identity
  -> A0
  -> IF-RM-002
  -> adapter
  -> M / IF-RM-001
  -> task-face load-spreading region
  -> front frame
  -> longitudinal primary structure
```

## 2. Evidence-bound geometry

| 参数 | 数值 | 状态 |
|---|---:|---|
| `MOUNT_ORIGIN_S` | `[185.25,0,0] mm` | `EVIDENCE_BOUND` |
| `MOUNT_RY` | `+90°` | `EVIDENCE_BOUND` |
| servicer flange envelope | `15 × 160 × 160 mm` | `EVIDENCE_BOUND` |
| adapter plate envelope | `12 × 160 × 160 mm` | `EVIDENCE_BOUND` |
| adapter boss envelope | `Ø100 × 15 mm` | `EVIDENCE_BOUND` |
| `T_MA0` | identity | `EVIDENCE_BOUND` |
| B601 topology | 10 links / 9 joints | `EVIDENCE_BOUND / READ_ONLY` |

这些是既有数字接口/包络，不是制造图，也不说明孔位、公差、材料或实际连接。

## 3. Preliminary module decomposition

```text
SV2_MNT_ROBOT
├── SV2_MNT_INTERFACE_PLANE_M
├── SV2_MNT_ADAPTER_REFERENCE
├── SV2_MNT_LOAD_SPREADING_REGION
├── SV2_MNT_PRIMARY_FRAME_TIE_REFERENCES
├── SV2_MNT_TOOL_ACCESS_KEEPOUT
├── SV2_MNT_HARNESS_PASSAGE_OWNER
└── SV2_MNT_WRENCH_OVERLAY
```

只有 adapter reference 可以消费已有 envelope；其余均为 reference/proposal，不含未经授权的实体细节。

## 4. Six-dimensional interface contract

所有机械臂工况统一在 `M` frame 表达：

```text
w_M(t) = [Fx, Fy, Fz, Mx, My, Mz]^T
```

PDR 仅定义字段，不填写数值。loads owner 未来必须同时提供：

- source and configuration；
- time history 或 conservative envelope；
- units and sign convention；
- joint state / arm configuration；
- target/contact state；
- combination and safety-factor authority；
- uncertainty/confidence；
- whether external support/launch boundary applies。

捕获仿真中的结果不能未经独立接口裁决直接变成 mount 结构载荷。

## 5. Load-spreading concept

候选拓扑：

1. adapter 反力首先进入 `MOUNT_LOAD_SPREADING_REGION`；
2. 该区域与 `FRM_FRONT_TASK` 建立直接责任链；
3. topology reference 向四个 longeron node 分配反力路径；
4. 可拆 front panel 不作为主反力闭合构件；
5. sensor reserve、工具区和 harness passage 不得切断 load-path reference；
6. 所有局部 rib/gusset 只作为可抑制 proposal，数量、形状和连接待后续载荷设计。

## 6. Alignment and assembly logic

- `M` 是 spacecraft-owned datum；
- `A0` 是 accepted B601 insertion datum；
- `T_MA0=identity` 不允许通过手工 mate 偏置；
- future locator/fastener 必须从 IF-RM owner 派生；
- assembly 中不得以 B601 外壳曲面作为定位基准；
- B601 reference 必须能在不改变 primary structure 的情况下替换/抑制；
- cable/thermal/electrical bonding 由独立 future owner 提供。

## 7. Service and keepout logic

未来 B3 应显示但不验证：

- adapter 周围工具访问 owner；
- front panel `+X_S` 候选拆卸方向；
- B601 q0 reference 和 task-face keepout；
- harness passage owner；
- sensor reservation/occlusion owner；
- solar/deployed state 之间的 configuration-scoped interference。

V1 的十处 q0 展开参考干涉必须继续作为负结果显示，不得通过 suppress B601 或太阳翼来制造通过。

## 8. Design alternatives retained

| 议题 | 当前 PDR 选择 | 保留候选/未知 |
|---|---|---|
| reaction termination | front primary frame | exact rib/longeron joint scheme |
| adapter role | single owned adapter reference | physical stack-up |
| local reinforcement | load-spreading region + tie references | rib count/shape/thickness |
| service access | front access owner | tool and fastener geometry |
| harness | passage owner | connector, bend radius, strain relief |

## 9. B3 entry checklist for mount

- B3 具名授权存在；
- `T_SM`、`T_MA0`、URDF hash 未变；
- IF-RM-001/002 的 null fields 仍为空；
- adapter source geometry/hash 可追溯；
- physical loads 未被默认值补齐；
- model property 明确 `NO_STRENGTH_CLAIM=true`；
- mount reference 不依赖 V1 活动零件；
- target/contact 未进入 active assembly。

## 10. Exit status

`ROBOT_MOUNT_PDR_TOPOLOGY_COMPLETE / PHYSICAL_DESIGN_BLOCKED_BY_LOADS_CONNECTIONS_AND_MATERIALS`
