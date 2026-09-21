# Unified R2 V2 URDF 源级数字样机回执

- 静态检查：`24/24`；裁决仅为 `PASS_SOURCE_STATIC_ONLY`。
- 选定模式：`EXPLICIT_STRUCTURE_PLUS_RESIDUAL`，19 links / 18 joints / 8 DOF；对照 aggregate 模式为 18 / 17 / 8。
- 显式主结构与代数余量精确重组既有 bus lump；两模式整星质量均为 `31.022864807342987 kg`。
- `D_BUS_MATE_PHYSICAL`、`M_DYNAMICS_NONPHYSICAL` 与 `D_BUS_M6_PATTERN` 是三个独立 frame-only links；物理路径经 D→Pattern，不经 M。
- B601 接受版 10-link/9-joint 惯量与关节字段保持；`15 m/s` 仍只是 URDF 模型字面量。
- 公共 `gen_urdf()` 未授权调用按预期 fail-closed；本目录没有 `.urdf`，没有修改 Sim13 V1。
- 当前仍需 Owner 接受、Route-C 排除接受、版本化 Sim13 loader/runtime harness、接触后端及后续动力学 Gate。
