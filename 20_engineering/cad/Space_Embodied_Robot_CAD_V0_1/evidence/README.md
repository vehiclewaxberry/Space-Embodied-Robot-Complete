# Evidence Directory

该目录保存 A3 Geometry Only 的机器生成证据：

- `builder_stdout.log`：SolidWorks 原生构建结果、包络和干涉检查
- `builder_stderr.log`：构建异常；成功验收时应为空
- `finalizer.log`：当前 B601 与顶层装配的组件固定和保存复验记录；最终构建器也会直接固定组件
- `native_inspection.log`：重新打开文件后的特征、命名尺寸、自定义属性、组件与变换检查
- `12U_B601_geometry_only_isometric.bmp`：总装等轴测截图

证据只支持“几何数字样机已建立”，不支持动力学、强度、发射合规或任务可行性结论。
