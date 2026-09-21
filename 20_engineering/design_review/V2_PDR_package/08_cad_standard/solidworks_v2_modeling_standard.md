# SolidWorks V2 System Mechanical Modeling Standard

> `STATUS: MODELING_STANDARD_READY_FOR_FUTURE_B3`  
> `CURRENT_CAD_EXECUTION: NOT_AUTHORIZED`

## 1. Modeling philosophy

V2 采用 top-down、证据状态可见、物理权限分离的建模方式：

```text
controlled input
  -> Master Skeleton
  -> structure/module skeleton
  -> replaceable part
  -> configuration-scoped review
  -> machine-readable evidence
```

模型的“工程真实感”来自明确结构职责、接口、装配和维护逻辑，不来自螺栓纹理、PCB、电机内部或未经来源支持的细节。

## 2. Future assembly tree

```text
Spacecraft_Service_Vehicle_V2_0.SLDASM
├── Master_Skeleton_V2_0.SLDPRT
├── SV2_ASM_01_PRIMARY_STRUCTURE.SLDASM
├── SV2_ASM_02_FRONT_MISSION.SLDASM
├── SV2_ASM_03_MID_AVIONICS.SLDASM
├── SV2_ASM_04_REAR_SERVICE.SLDASM
├── SV2_ASM_05_ROBOT_MOUNT.SLDASM
├── SV2_ASM_06_B601_REFERENCE.SLDASM
├── SV2_ASM_07_SOLAR_INTERFACES.SLDASM
├── SV2_ASM_08_PERCEPTION_REFERENCE.SLDASM
├── SV2_ASM_09_SERVICE_REFERENCES.SLDASM
└── SV2_ASM_10_REVIEW_OVERLAYS.SLDASM
```

## 3. Naming

### Document pattern

```text
SV2_<TYPE>_<NN>_<FUNCTION>[_<INDEX>].<EXT>
```

`TYPE` 只能为：

- `ASM`
- `STR`
- `PNL`
- `DECK`
- `MNT`
- `IF`
- `REF`
- `KPT`
- `OVR`

禁止使用空格、中文、`final`、`new`、`copy`、`test2` 等不可追溯名称。

B2.5 已预留的两个顶层文件是受控例外：

- `Assembly/Spacecraft_Service_Vehicle_V2_0.SLDASM`
- `00_Master_Skeleton/Master_Skeleton_V2_0.SLDPRT`

它们分别通过 `CAD_ID=SV2-ASM-000` 和 `CAD_ID=SV2-REF-000` 保持机器身份；不得再创建同义顶层文件。

### Feature naming

- `PLN_*`：reference plane；
- `CS_*`：coordinate system；
- `SK_*`：reference sketch；
- `DATUM_*`：interface datum；
- `VOL_*`：volume owner；
- `KPT_*`：keepout；
- `LP_*`：load-path reference；
- `CFG_*`：configuration/display state；
- `UNK_*`：suppressed unknown placeholder。

## 4. Structure class

每个实体只允许一个主要 class：

- `PRIMARY_PROPOSAL`
- `SECONDARY_PROPOSAL`
- `INTERFACE_REFERENCE`
- `VOLUME_PLACEHOLDER`
- `KEEPOUT_REFERENCE`
- `SEMANTIC_REFERENCE`
- `EXCLUDED`

一个对象不能同时通过显示颜色和装配位置隐式承担多个职责。

## 5. Evidence-state display

| state | display label | 含义 |
|---|---|---|
| `EVIDENCE_BOUND` | dark blue | 受控输入或 hash-bound reference |
| `DERIVED` | blue | 由受控关系直接推导 |
| `DESIGN_PROPOSAL` | light blue | 可替换候选设计 |
| `UNKNOWN_BLOCKED` | orange | 不得零值补齐 |
| `EXCLUDED` | grey | 不进入 active system |
| `NEGATIVE_RESULT` | red overlay | 已知问题，不得隐藏 |

颜色只用于 review display state；对象真值以属性为准。

## 6. Required custom properties

一级文档和关键对象至少具有：

```text
OBJECT_ID
CAD_ID
SYSTEM_OWNER
PARENT_ID
STRUCTURE_CLASS
REPRESENTATION_LAYER
EVIDENCE_STATE
SOURCE_REFERENCE
SOURCE_SHA256
FRAME_ID
INTERFACE_IDS
MASS_OWNER
MASS_AUTHORITY
DYNAMICS_AUTHORITY
MANUFACTURING_AUTHORITY
EXECUTION_AUTHORITY
CLAIM_LIMIT
BLOCKED_BY
BLOCKED_CONSUMERS
```

未知字段为空时必须同时提供 `EVIDENCE_STATE=UNKNOWN_BLOCKED`，不能写 `0`、`default` 或 `typical`。

## 7. External-reference rule

- Master Skeleton 不含活动外部引用；
- V2 子装配只引用 V2 Master Skeleton 或同一受控 module skeleton；
- V1.0 只作只读差异对照，不作活动 in-context parent；
- OreSat/vendor CAD 不得活动引用、复制或改名；
- accepted B601 visual reference 必须记录 URDF/source hash，且不改拓扑；
- 禁止 circular reference 和 root-assembly back-drive。

## 8. Mates and interfaces

- 只使用具名 datum/CS/plane 作为 mate；
- `M/A0` 使用 `T_SM/T_MA0`，禁止视觉对齐；
- unknown interface 不建立零偏置 mate；
- target/contact/physical TCP 不进入 active assembly；
- review overlay 不参与 physical mate；
- suppression 不得用于掩盖负结果。

## 9. Configurations and evidence

必须建立：

- `STRUCTURAL_REVIEW`
- `SERVICE_ACCESS_REVIEW`
- `DEPLOYED_REFERENCE_Q0`
- `STOWED_PROPOSAL`
- `EVIDENCE_STATE_REVIEW`

每份截图/干涉报告必须记录：

```text
configuration
joint state
solar state
suppressed components
source hashes
claim limit
```

## 10. Material and mass

- material/density 默认均为空；
- CAD mass property 无权覆盖 mass ownership ledger；
- placeholder 永远 `MASS_AUTHORITY=false`；
- 整星 CoM/inertia 不在 B3 输出范围内，除非另有具名物性 Gate；
- 不允许以 SolidWorks 默认值关闭 unknown。

## 11. Native verification

未来每个 B3 build loop 必须：

1. save；
2. close/reopen；
3. force rebuild；
4. inspect missing references and mates；
5. export document/feature/property/component inventory；
6. compare source hashes；
7. run configuration-scoped interference；
8. preserve negative findings；
9. regenerate evidence manifest。

## 12. Explicitly excluded detail

- decorative fasteners；
- PCB/internal electronics；
- motor internals；
- camera appearance；
- thruster/tank geometry；
- fabricated hinge/release mechanism；
- physical gripper/contact feature；
- manufacturing drawing/tolerance stack。
