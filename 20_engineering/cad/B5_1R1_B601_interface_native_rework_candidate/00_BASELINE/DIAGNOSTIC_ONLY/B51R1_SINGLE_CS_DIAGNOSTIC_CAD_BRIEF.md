# B5.1R1 单坐标系原生诊断 CAD Brief

## 1. 目的

本诊断只回答一个问题：在全新空白 SolidWorks 2024 零件中，能否通过一次且仅一次原生 `InsertCoordinateSystem` 调用建立并保存名为 `CS_DIAGNOSTIC_ONLY` 的坐标系。

它不是 Master Skeleton V2、Carrier、整机装配、H10 或 T005 的替代证据，也不得用于宣称原生机构已通过。

## 2. 授权边界

- 本轮授权最多可见启动 SolidWorks 2024 **一次**。
- 唯一允许写入的 CAD 目标：
  `00_BASELINE\DIAGNOSTIC_ONLY\B51R1_SINGLE_CS_DIAGNOSTIC_COPY.SLDPRT`
- 已验证 Stage A 受保护文件：
  `02_MASTER_SKELETON\B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT`
- Stage A 不得被打开写入、复制为诊断输入、另存为诊断件或发生任何时间戳/哈希变化。
- 诊断件必须由标准空白零件模板新建，不得由既有零件派生。

## 3. 诊断构造

空白零件应保留并记录其原生默认参考：

1. 三个相互正交的默认基准面；
2. 原点；
3. 一次 `FeatureManager.InsertCoordinateSystem(...)` 调用；
4. 唯一生成的原生坐标系特征，重命名为 `CS_DIAGNOSTIC_ONLY`。

不得在本次运行中创建第二个坐标系。不得导入 STEP，不得建立 Mate，不得构建 Carrier，不得进行恢复模式操作。

## 4. 第一次可见启动的允许顺序

1. 可见启动一个 SolidWorks 2024 进程，并确认无恢复对话框阻塞。
2. 新建空白零件。
3. 确认默认三基准面与原点存在。
4. 只调用一次 `InsertCoordinateSystem`。
5. 将生成特征命名为 `CS_DIAGNOSTIC_ONLY`。
6. 保存到唯一允许目标。
7. 关闭诊断文档。
8. 正常退出 SolidWorks。
9. 离线核对文件存在、运行日志、进程退出和 Stage A 前后哈希。

## 5. 首次启动的状态上限

即使第 4 节全部成功，第一次启动结束后的最高允许状态也只能是：

`SINGLE_CS_CREATION_SAVE_EXIT_PASS_COLD_REOPEN_PENDING`

原因是冷重开持久化检查必然需要第二次可见启动，而当前明确授权只有一次。未经新的人工授权，不得执行第二次启动，不得将该诊断标记为完整 `PASS`。

## 6. 失败关闭规则

出现下列任一情况时停止原生 CAD 推进，并记录：

`SINGLE_COORDINATE_SYSTEM_DIAGNOSTIC_HOLD`

- `InsertCoordinateSystem` 调用卡住、抛错或返回空；
- 生成零个或多个坐标系特征；
- 坐标系无法命名或保存；
- 诊断工具触碰 Stage A；
- SolidWorks 无法正常关闭；
- 无法证明调用次数严格为一次；
- 目标文件、日志或哈希证据不一致。

冷重开未执行不是本次创建失败，但必须保持：

`COLD_REOPEN_PENDING_SEPARATE_VISIBLE_LAUNCH_AUTHORIZATION`

## 7. 本 Brief 不释放的工作

- Master Skeleton V2 最终文件；
- 10 个原生 Carrier；
- `6R + 1 fixed + 2P` 原生整机；
- H10 28/28；
- T005-A/B/C；
- 控制参数验证、执行器选型或控制模型发布。

上述内容仍由后续独立 Gate 管理。
