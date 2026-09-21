# V2 Mechanical Digital Thread

> `STATUS: INTERFACE_SCHEMA_READY_IMPLEMENTATION_NOT_AUTHORIZED`  
> `CAD_EXPORTS_CREATED: false`  
> `DYNAMICS_OR_DIGITAL_TWIN_READY: false`

## Purpose

本目录定义未来机械数据如何从受控系统输入流向 CAD、URDF 映射和仿真，而不允许任一消费者反向改写上游真值：

```text
B2.5 input SSOT
  -> B2.8 PDR object/frame/owner contracts
  -> future B3 native CAD
  -> reviewed geometry export
  -> separately authorized URDF/dynamics mapping
  -> simulation or digital twin
```

每一跳都需要独立 Gate；CAD 完成不自动等于 dynamics、Isaac、VLA 或 digital twin 完成。

## Files

- [CAD object identity](./CAD_ID.yaml)
- [Frame mapping](./frame_mapping.yaml)
- [Mass ownership mapping](./mass_owner.yaml)
- [Inertia placeholders](./inertia_placeholder.yaml)
- [URDF mapping plan](./URDF_mapping_plan.yaml)
- [Simulation interface](./simulation_interface.md)

## Non-inheritance rule

- scientific Gate PASS 不能由 CAD 继承；
- CAD visual result 不能填充 mass/inertia/stiffness；
- URDF topology 不能证明制造结构；
- simulation result 不能自动成为结构载荷；
- digital-thread schema 不能被表述为已实现数字孪生。
