# V2 Primary Structure Preliminary Design Report

> `STATUS: CONCEPTUAL_LOAD_PATH_AND_TOPOLOGY_DEFINED`  
> `MATERIAL_SECTION_JOINTS: UNKNOWN_BLOCKED`  
> `STRENGTH_STIFFNESS_MODAL: NOT_EVALUATED`

## 1. Design intent

主结构必须同时服务四类评审：

1. 把 B601 反力从任务面传入 bus 主结构；
2. 固定三个功能舱的基准和安装平面；
3. 为太阳翼根、外板、设备托盘和线束提供责任边界；
4. 在不引入虚假物理参数的情况下，为未来载荷和 FEA 建立明确输入接口。

## 2. Reference topology

### 2.1 Transverse frames

| CAD reference | `X_S` | 结构角色 | 状态 |
|---|---:|---|---|
| `FRM_REAR_BOUNDARY` | `-170.25 mm` | rear system boundary；未来 deployer/rail load boundary owner | `DERIVED + UNKNOWN_BOUNDARY` |
| `FRM_REAR_MID` | `-56.75 mm` | rear/middle 分舱框；solar root longitudinal station | `DERIVED / DESIGN_PROPOSAL` |
| `FRM_MID_FRONT` | `+56.75 mm` | middle/front 分舱框和 equipment-deck boundary | `DERIVED / DESIGN_PROPOSAL` |
| `FRM_FRONT_TASK` | `+170.25 mm` | task-face load-spreading frame | `DERIVED / DESIGN_PROPOSAL` |

四个 frame 只定义位置和拓扑角色，不定义环框截面、材料、局部开口、接头或加工方式。

### 2.2 Longitudinal members

四条位于 body-envelope corner reference 附近的长向构件形成候选主反力通道：

```text
LNG_PY_PZ
LNG_PY_NZ
LNG_NY_PZ
LNG_NY_NZ
```

它们由 Master Skeleton 的 `±BODY_HALF_Y`、`±BODY_HALF_Z` 参考驱动。实际构件中心线偏置、截面和与 frame 的连接保持 null。

### 2.3 Decks and panels

- `DECK_REAR_MID` 与 `DECK_MID_FRONT`：舱段边界/设备安装候选面；是否承担主载荷需后续 loads/structure owner 决定。
- 外板：默认归类为 `SECONDARY_OR_UNCLASSIFIED_PENDING`，不得在 PDR 中被当作闭合主载荷路径。
- 设备托盘：可拆卸 secondary/reference object；不得反向驱动总体 envelope。

## 3. Conceptual primary load path

### Robot-operation path

```text
B601 A0
  -> IF-RM-002
  -> robot mount adapter
  -> IF-RM-001 / M
  -> front task-face frame
  -> four longitudinal members
  -> bay frames and rear boundary frame
  -> future external/support boundary owner
```

### Solar-root path

```text
solar reference geometry
  -> IF-SA-L / IF-SA-R at F_L/F_R
  -> rear-mid frame station
  -> longitudinal members
  -> remaining bus primary structure
```

该路径只表示 owner 和拓扑连续性。因为 hinge、部署载荷、连接和边界未知，不构成可计算载荷路径。

### Equipment path

```text
future subsystem
  -> future mount plane
  -> deck or frame interface
  -> primary longitudinal/frame topology
```

所有 future mount plane 当前为 reservation；不可把 placeholder 直接 mate 到外板并据此声称结构闭合。

## 4. Primary/secondary/reference classification

| 对象 | PDR class | 说明 |
|---|---|---|
| front/rear/inter-bay frames | `PRIMARY_PROPOSAL` | 概念主承力 |
| four longitudinal members | `PRIMARY_PROPOSAL` | 概念长向反力链 |
| bay boundary decks | `PRIMARY_OR_SECONDARY_TBD` | 需载荷与连接裁决 |
| removable external panels | `SECONDARY_PROPOSAL` | 维护与包络，不默认承力 |
| subsystem trays | `SECONDARY_PROPOSAL` | 可拆安装载体 |
| harness corridor/keepouts | `REFERENCE_ONLY` | 无实体质量和承力权威 |
| B601 visual and target scene | `REFERENCE_ONLY` | 不作为 bus 结构 |

## 5. Local reinforcement concept

任务面允许创建以下可抑制提案：

- `MOUNT_LOAD_SPREADING_RING`：围绕 `M` 的局部反力扩散 reference；
- `MOUNT_TO_FRAME_RIB_SET`：从 adapter region 指向 `FRM_FRONT_TASK`/longeron nodes 的拓扑线；
- `ADAPTER_SUPPORT_REGION`：容纳现有 adapter envelope 的区域；
- `HARNESS_PASSAGE_RESERVATION`：不切断主 load-path reference 的空值通道。

这些名称不代表已经选择加强筋数量、形状、板厚或连接。

## 6. Boundary and load-case handoff

未来 loads owner 必须至少分别提供：

- launch/recovery boundary（若项目进入相关范围）；
- B601 nominal operation wrench；
- capture transient equivalent/interface history；
- solar stowed/deployment root loads；
- ground handling/integration loads。

每个 load case 需给出 frame、单位、时域/包络、组合规则、来源、置信度和适用 configuration。在此之前六维载荷均为 null。

## 7. PDR verification views

- primary structure only；
- front task-face section；
- four-longeron continuity；
- three-bay cutaway；
- robot reaction load path；
- solar root owner path；
- primary/secondary/reference color state；
- unresolved boundary and null-load overlay。

## 8. Limits

本报告不选择结构形式的具体截面，不判断 frame-and-deck 优于其他制造方案，也不提供质量、强度、刚度、模态、屈曲、热变形或寿命结论。
