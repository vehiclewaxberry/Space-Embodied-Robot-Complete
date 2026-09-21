# B601 Geometry Reference

> `REPRESENTATION: URDF_MESH_BOUNDING_BOX_REFERENCE`  
> `REFERENCE_POSE: Q_ZERO_GEOMETRY_ONLY`  
> `VENDOR_STEP_IMPORTED: false`

`B601_Reference_Assembly.SLDASM` 保留 10 个 link、9 个 joint 的 accepted URDF q=0 拓扑。每个 link 使用对应 STL 的轴对齐包围盒生成一个原生可编辑 SolidWorks 零件。

来源：

- accepted URDF：`20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf`
- accepted URDF SHA-256：`1bc2b7483cd8025d08ba6eadfd9e1f3b0477121714e7cf4ddc1794d9e471c164`
- 可移植许可证与来源记录：`80_third_party/notices/rebot_b601/`

限制：

- 包围盒不是供应商精确 CAD
- 不表达关节间隙、紧固件、线束、接触表面和物理 TCP
- 不允许用于动力学、质量属性、制造或碰撞安全结论
- 外部供应商 STEP 未复制到本包，也未被导入
