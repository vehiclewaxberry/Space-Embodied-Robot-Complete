# B5.1R1 单坐标系冷重开持久化 CAD Brief

## 目的

在一个全新的可见 SolidWorks 2024 SP5 进程中冷打开既有诊断件，确认唯一原生坐标系在跨进程保存后仍可枚举、命名和回读。

## 唯一允许目标

`00_BASELINE/DIAGNOSTIC_ONLY/B51R1_SINGLE_CS_DIAGNOSTIC_COPY.SLDPRT`

受保护 Stage A 仅允许运行前后只读 SHA-256：

`02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT`

## 允许动作

1. 可见启动一个空的 SolidWorks 2024 SP5 会话；
2. 冷打开固定诊断件；
3. 枚举并确认精确一个 `CS_DIAGNOSTIC_ONLY`，类型为 `CoordSys`；
4. 回读 16 元变换，确认单位旋转、零平移、缩放 1；
5. 确认外部引用为 0；
6. 记录受控 `Save3` 前哈希，执行一次受控保存并记录错误、警告与保存后哈希；
7. 使用当前标题关闭文档，确认会话为空；
8. 调用 `ExitApp`，以进程消失或 `HasExited` 作为退出证据；外部附着进程不提供退出码时记录 `UNAVAILABLE`，不得据此判 CAD 失败；
9. 复核 Stage A 哈希不变。

二进制哈希若变化，只能确认该变化发生在本次唯一受控 `Save3` 之后；当名称、类型、变换、外部引用与 Stage A 保护等语义不变量均保持时，记录为“哈希已变化、字节级原因未进一步解析”。若未变化，则记录为无字节差异的受控保存。两种情况都不得外推为几何或动力学变化。

## 禁止动作

- 不创建最终 Master Skeleton；
- 不创建 Carrier；
- 不创建 Mate、装配或第二个坐标系；
- 不导入 STEP；
- 不打开、复制或写入 Stage A；
- 不强制终止 SolidWorks；
- 不生成 H10、T005、控制发布、制造或飞行信用。

## 通过状态

仅当冷打开、名称/类型/变换/外部引用、受控保存、关闭、进程退出及 Stage A 哈希全部闭合时，允许：

`SINGLE_COORDINATE_SYSTEM_PERSISTENCE_PASS`

该状态只释放后续原生建模的规划 Gate，不自动授权新的可见 SolidWorks 启动。
