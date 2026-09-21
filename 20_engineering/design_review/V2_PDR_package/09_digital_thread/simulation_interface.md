# V2 Mechanical-to-Simulation Interface Plan

> `STATUS: CONTRACT_ONLY`  
> `SIMULATION_READY: false`  
> `DIGITAL_TWIN_IMPLEMENTED: false`

## 1. Purpose

规定未来 CAD 结果可以向 dynamics/Isaac/digital twin 提供哪些数据，以及哪些数据缺失时必须 fail closed。

## 2. Future handoff bundle

| bundle item | source | current status | consumer |
|---|---|---|---|
| object/CAD ID registry | PDR/CAD properties | schema ready | all consumers |
| frame mapping | frame SSOT + reviewed CAD datums | partial | dynamics/robotics |
| geometry export | future B3 STEP/STL | not created | visualization/collision review |
| B601 topology | accepted URDF | available read-only | robotics |
| mass-owner ledger | B2.5/PDR | available but provisional | mass review |
| aggregate mass/CoM/inertia | qualified configuration | missing | dynamics |
| robot mount wrench/load cases | loads owner | missing | FEA/structure |
| stiffness/flexible properties | qualification owner | missing | flexible dynamics |
| sensor/TCP/target transforms | subsystem owners | missing/excluded | perception/contact |

## 3. Fail-closed entry conditions

Simulation or digital-twin consumers must reject the bundle when:

- `T_SB` is required but null；
- aggregate mass/CoM/inertia is required but null；
- physical TCP/contact is required but `T_E_TCP` is null；
- target transform/contact is required but target remains excluded；
- structural flexibility is required but materials/sections/modal data are absent；
- geometry export lacks configuration, scale, frame and source hash；
- consumer attempts to inherit a scientific Gate from visual CAD。

## 4. Geometry export metadata

未来每个 export 至少带：

```text
EXPORT_ID
SOURCE_CAD_ID
SOURCE_DOCUMENT_SHA256
CONFIGURATION
FRAME_ID
UNIT
SCALE
REPRESENTATION_LAYER
EVIDENCE_STATE
CLAIM_LIMIT
CREATED_BY_GATE
```

没有这些字段的 STEP/STL 只能作临时可视化，不能进入可追溯数字线程。

## 5. Dynamics boundary

当前机械包不提供：

- dynamics-ready spacecraft base frame；
- complete mass matrix；
- flexible-body matrices；
- robot mount stiffness；
- contact model；
- actuator/sensor model。

因此不能宣称从 SolidWorks 到 Basilisk/Isaac 的闭环已经实现。

## 6. Future gated sequence

```text
B3 native CAD and evidence seal
  -> geometry export review
  -> mass/frame qualification
  -> URDF/robot mapping review
  -> dynamics input Gate
  -> separate simulation implementation
  -> independent evidence and scientific Gate
```

每一步都不得自动继承上一阶段的 PASS。
