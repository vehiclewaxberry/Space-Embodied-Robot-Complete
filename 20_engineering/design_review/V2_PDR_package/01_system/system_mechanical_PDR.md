# V2 System Mechanical Preliminary Design Review

> `REVIEW_ID: COMP-PROT-03-A4-B2.8-PDR`  
> `STATUS: PDR_COMPLETE_WITH_OPEN_PHYSICAL_BLOCKERS`  
> `DESIGN_MATURITY: SYSTEM_TOPOLOGY_AND_INTERFACE_RESPONSIBILITY`  
> `CAD_AUTHORING: NOT_AUTHORIZED`

## 1. PDR objective

评审 12U+B601 空间服务航天器 V2 的系统机械初步设计是否已经达到“可向人工申请 B3 参数化 CAD”的成熟度，同时确保：

- 不把任务愿景写成已实现能力；
- 不把视觉几何写成物理真值；
- 不用典型值补齐材料、载荷、质量或连接；
- 不破坏 V1.0、B601、Gate、仿真和证据链。

## 2. Frozen system boundary

| 对象 | PDR 输入 | 状态 |
|---|---|---|
| profile | `340.5 × 226.3 × 226.3 mm` | `EVIDENCE_BOUND / NON_FLIGHT_DISPLAY_ONLY` |
| system frame | `S` 位于 body envelope center | `EVIDENCE_BOUND` |
| task direction | `+X_S` | `EVIDENCE_BOUND` |
| bays | rear/middle/front，边界 `-56.75/+56.75 mm` | `DERIVED` |
| robot mount | `T_SM=[185.25,0,0] mm, Ry=+90°` | `EVIDENCE_BOUND` |
| robot root | `T_MA0=identity contract` | `EVIDENCE_BOUND` |
| B601 | accepted 10-link/9-joint identity | `EVIDENCE_BOUND / READ_ONLY` |
| free-flyer base | `T_SB` | `UNKNOWN_BLOCKED / DISABLED` |
| physical TCP | `T_E_TCP` | `UNKNOWN_BLOCKED / DISABLED` |
| target | independent scenario only | `EXCLUDED` |
| V1 deployed q0 interference | 10 static interferences | `NEGATIVE_RESULT / COLLISION_SAFETY_BLOCKED` |

## 3. Preliminary system decomposition

```text
SV2_SPACE_SERVICE_VEHICLE
├── SV2_STR_PRIMARY_STRUCTURE
│   ├── front task-face frame
│   ├── rear boundary frame
│   ├── four longitudinal load-path members
│   ├── rear/mid and mid/front bay frames
│   └── two bay-boundary equipment decks
├── SV2_MOD_FRONT_MISSION
│   ├── robot mount load-spreading region
│   ├── perception/interface reservation
│   └── mission-side service access reservation
├── SV2_MOD_MID_AVIONICS
│   ├── C&DH owner
│   ├── EPS/PMAD owner
│   ├── battery owner
│   └── ADCS owner
├── SV2_MOD_REAR_SERVICE
│   ├── propulsion reservation
│   ├── communications reservation
│   ├── thermal reservation
│   └── integration/service reservation
├── SV2_MNT_ROBOT
│   ├── IF-RM-001 spacecraft-to-adapter
│   ├── adapter and local reinforcement proposal
│   └── IF-RM-002 adapter-to-B601
├── SV2_REF_B601
├── SV2_IF_SOLAR_LEFT_RIGHT
├── SV2_REF_SERVICE_AND_HARNESS
└── SV2_REVIEW_OVERLAYS
```

主结构、次结构、设备占位和 reference geometry 必须在装配树和属性层面分离。

## 4. Requirement disposition

| 需求组 | 数量 | PDR 处理 | 裁决 |
|---|---:|---|---|
| mission | 5 | 转换为 task face、语义接口和 excluded target；不产生能力证明 | `SATISFIED_AT_PDR_SCOPE` |
| system | 4 | profile、三舱、`T_SM` 和 target 隔离已冻结 | `SATISFIED_AT_PDR_SCOPE` |
| mechanical | 10 | 形成结构、接口、安装、维护和负结果方案 | `SATISFIED_WITH_PHYSICAL_BLOCKERS` |
| CAD/evidence | 8 | 建模方法、命名、属性、配置和 hash 规则已规定 | `READY_FOR_FUTURE_B3` |

27 项需求均有 PDR 处置，但没有一项因此升级为物理资格或科学 Gate。

## 5. Key preliminary design decisions

1. 使用独立 V2 根和 top-down Master Skeleton；禁止复用 V1 原生零件作为活动外部引用。
2. 以四个环形边界面和四条长向主构件表达概念主承力拓扑；截面和连接保持未知。
3. 任务面中央 `M/A0` 是唯一 B601 主安装链；反力不能终止在可拆面板。
4. 三舱首先按 owner 和安装平面组织，不按具体硬件外观组织。
5. 外板、设备托盘和线束走廊是 service/reference 层，不自动承担主结构职责。
6. 感知、physical TCP、contact、target、推进和太阳翼机构只保留 owner/reservation。
7. CAD ID、frame、mass owner、URDF mapping 和 simulation interface 同时发布，形成可追溯数字线程。
8. 太阳翼、设备甲板和长机械臂构件仅登记为未来柔性建模候选，不实施 ANCF/FEA。

## 6. System-level trade disposition

| 议题 | 候选 | PDR 选择 | 原因 | 未闭合 |
|---|---|---|---|---|
| CAD 方法 | bottom-up / top-down | top-down skeleton | 已由 B2.5 合同绑定 | SolidWorks 尚未授权 |
| 主结构表达 | 单盒体 / frame-and-deck | frame-and-deck proposal | 支持 load path、舱段和维护审查 | material/section/joints |
| robot mount | panel mount / primary-frame mount | primary-frame load-spreading path | 避免反力终止于次结构 | loads/stiffness/fasteners |
| 设备布置 | hardware-first / owner-first | owner-first | 硬件尚未选型 | envelope/mass/thermal/harness |
| target | active mate / independent scene | independent scene | 现有合同明确排除 | `T_ST/T_SD`、contact |
| deployables | one visual state / named states | named state separation | 保留负结果和审查语义 | stowed/hinge/release/loads |

## 7. Open physical blockers

- 标准 12U/deployer/rail/tab 仍未裁决；
- robot mount、发射和在轨操作载荷为空；
- 材料、截面、板厚、紧固件、连接刚度和制造工艺为空；
- 整星真实质量、CoM 和惯量未闭合；
- 真实设备 envelope、热、EMC、线束和维护工具净空为空；
- solar stowed/hinge/release/lock 和 physical sensor/TCP/target 均未闭合；
- B3 具名人工授权不存在。

## 8. PDR finding summary

| 类别 | 数量 | 处置 |
|---|---:|---|
| 文档/语义 critical | 0 | 无破坏冻结边界或伪造真值 |
| 文档/语义 major | 0 | 接口、owner、frame 和状态链已闭合 |
| 物理 blocker | 17 | 继承 unknown register，不在 PDR 内关闭 |
| negative result | 1 record / 10 interferences | 原样保留 |

## 9. PDR decision

```text
PDR documentation and topology: COMPLETE
physical design qualification: NOT_STARTED
B3 request package: READY
B3 CAD authoring: NOT_AUTHORIZED
```

PDR 完成仅说明设计方案具备受控建模入口，不说明机械系统已经工程完成。
