# V2 Master Skeleton CAD Construction Specification

> `STATUS: CAD_CONSTRUCTION_SPECIFICATION_COMPLETE`  
> `NATIVE_CAD_CREATED: false`  
> `SOURCE: B2.5_MASTER_SKELETON_PARAMETER_CONTRACT`

## 1. Intended future document

```text
20_engineering/cad/Space_Embodied_Robot_CAD_V2_0/
└── 00_Master_Skeleton/
    └── Master_Skeleton_V2_0.SLDPRT
```

该路径只作 B3 预留；本阶段不创建目录或文件。

文件名继承 B2.5 已预留路径，是一般 `SV2_<TYPE>_*` 命名规则的受控例外；其对象身份仍使用 `CAD_ID=SV2-REF-000`。

## 2. Document settings

- unit system：MMGS；
- origin：spacecraft geometry frame `S`；
- axes：`+X_S` mission direction、`+Y_S` lateral、`+Z_S` normal；
- material：none；
- density：none；
- mass authority：false；
- external active references：none；
- solid body：prefer zero-solid/reference-only；若 B3 需要 envelope body，必须单独标记 `REFERENCE_ONLY / NO_MASS_AUTHORITY`。

## 3. Global parameters

| equation name | value | state | owner |
|---|---:|---|---|
| `SV2_BODY_X` | `340.5 mm` | `EVIDENCE_BOUND` | profile SSOT |
| `SV2_BODY_Y` | `226.3 mm` | `EVIDENCE_BOUND` | profile SSOT |
| `SV2_BODY_Z` | `226.3 mm` | `EVIDENCE_BOUND` | profile SSOT |
| `SV2_HALF_X` | `SV2_BODY_X/2` | `DERIVED` | skeleton |
| `SV2_HALF_Y` | `SV2_BODY_Y/2` | `DERIVED` | skeleton |
| `SV2_HALF_Z` | `SV2_BODY_Z/2` | `DERIVED` | skeleton |
| `SV2_BAY_COUNT` | `3` | `EVIDENCE_BOUND` | architecture |
| `SV2_BAY_NOMINAL_X` | `SV2_BODY_X/3` | `DERIVED` | skeleton |
| `SV2_MOUNT_X` | `185.25 mm` | `EVIDENCE_BOUND` | `T_SM` |
| `SV2_MOUNT_RY` | `90 deg` | `EVIDENCE_BOUND` | `T_SM` |

禁止在 skeleton 中添加材料、壁厚、截面、质量、载荷、连接或安全系数方程。

## 4. Reference planes

按 feature tree 顺序建立：

| plane | offset in `S` | role |
|---|---:|---|
| `PLN_REAR_BODY_FACE` | `X=-170.25 mm` | rear boundary |
| `PLN_REAR_MID_FRAME` | `X=-56.75 mm` | rear/middle frame and solar station |
| `PLN_MID_FRONT_FRAME` | `X=+56.75 mm` | middle/front frame |
| `PLN_FRONT_TASK_FACE` | `X=+170.25 mm` | task-face primary frame |
| `PLN_ROBOT_MOUNT_M` | from `T_SM` | IF-RM-001 |
| `PLN_SOLAR_ROOT_L` | from `F_L` | IF-SA-L |
| `PLN_SOLAR_ROOT_R` | from `F_R` | IF-SA-R |

不得用子装配曲面反向定义这些 plane。

## 5. Coordinate systems

| CAD CS | definition | state | enabled |
|---|---|---|---|
| `CS_S` | document origin | `EVIDENCE_BOUND` | yes |
| `CS_M` | `T_SM` | `EVIDENCE_BOUND` | yes |
| `CS_A0` | `T_MA0=identity` relative to `M` | `EVIDENCE_BOUND` | yes |
| `CS_B` | `T_SB` | `UNKNOWN_BLOCKED` | no |
| `CS_E_VIRTUAL` | B601 link6 semantic frame | `EVIDENCE_BOUND_REFERENCE` | future reference |
| `CS_TCP_CONTACT` | `T_E_TCP` | `UNKNOWN_BLOCKED` | no |
| `CS_SENSOR` | `T_SC` | `UNKNOWN_BLOCKED` | no |

Disabled coordinate systems 只能以属性或 suppressed placeholder 表示，不能用零值代替未知 transform。

## 6. Topology reference sketches

### `SK_BODY_ENVELOPE`

发布 body-envelope corners、centerlines 和 task direction。其 profile 标注必须显示：

`COMPETITION_DISPLAY_V0 / NON_FLIGHT_DISPLAY_ONLY`

### `SK_PRIMARY_FRAME_STATIONS`

发布四个 transverse frame station，不含 frame section。

### `SK_LONGERON_REFERENCE`

发布四条长向 topology line，位置由 `±SV2_HALF_Y`、`±SV2_HALF_Z` corner reference 控制；actual member offset/section 为 null。

### `SK_ROBOT_LOAD_PATH`

发布 `A0 -> M -> front frame -> longeron nodes` 的 reference chain，不含力值或截面。

### `SK_BAY_OWNER_BOUNDARIES`

发布 rear/middle/front zone，并给 volume owner overlay 提供稳定引用。

### `SK_SERVICE_AND_HARNESS_OWNER`

只发布 service direction arrows、harness corridor owner 和 keepout owner，不产生质量或实体。

## 7. Interface datums

| datum | interface | geometry |
|---|---|---|
| `DATUM_IF_RM_001` | spacecraft → adapter | `CS_M` + existing envelope references |
| `DATUM_IF_RM_002` | adapter → B601 | `CS_A0` |
| `DATUM_IF_SA_L/R` | solar roots | `F_L/F_R` |
| `DATUM_IF_PL_001` | perception reserve | zero-solid, transform null |
| `DATUM_IF_EE_001` | physical TCP reserve | disabled |
| `DATUM_IF_AV/SV` | internal owner interface | bay plane + owner tag |
| `DATUM_IF_MA_001` | maintenance | direction/keepout owner |
| `DATUM_IF_TG_001` | target | excluded, no mate |

## 8. Published geometry

Master Skeleton 只允许向子装配发布：

- envelope surfaces；
- planes and axes；
- coordinate systems；
- points and topology lines；
- interface datum sketches；
- bay/owner boundaries；
- evidence-state metadata。

禁止发布：

- material/section/thickness；
- hardware dimensions without source；
- physical contact geometry；
- target mate；
- calculated mass/CoM/inertia；
- FEA mesh/load/boundary；
- vendor/OreSat active geometry。

## 9. Dependency direction

```text
Master Skeleton
  -> primary structure
  -> module skeletons
  -> interface/reference subassemblies
  -> panels/trays/placeholders
  -> review overlays
```

子装配之间不得互相发布总体基准；不得形成 circular external reference；root assembly 不得反向驱动 skeleton。

## 10. Configuration publication

Master Skeleton 为以下配置提供可见性控制：

- `STRUCTURAL_REVIEW`
- `SERVICE_ACCESS_REVIEW`
- `DEPLOYED_REFERENCE_Q0`
- `STOWED_PROPOSAL`
- `EVIDENCE_STATE_REVIEW`

配置只改变显示/抑制状态，不得改写同一受控 parameter 的数值。

## 11. B3 construction tests

未来原生文件必须通过：

1. reopen/rebuild 无错误；
2. equation/property inventory 与本规范匹配；
3. external reference list 为空或仅含具名受控内部 V2 依赖；
4. unknown coordinate systems disabled；
5. no material/no mass authority；
6. all published geometry has owner and evidence state；
7. no target/contact/vendor/OreSat active reference；
8. source hash 和 claim limit 可导出。
