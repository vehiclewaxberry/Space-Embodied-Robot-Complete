# B5.1R1 SolidWorks 2024 可见启动与恢复对话框记录

日期：2026-07-29  
授权包 SHA-256：`AB2D6EAC2C508F2D192E05263E6256AC7FB343A3E3F43BD224BEF28FF42497A4`

## 启动前

- `SLDWORKS.exe`：0 个；
- `swShellFileLauncher.exe`：0 个；
- `sldworks_fs.exe`：1 个，PID 49264，无窗口、可响应；
- B5.1R1 候选目录 `~$` 锁文件：0 个；
- 未删除任何锁文件；
- 冻结启动包、accepted URDF、q0 轴台账和 V2.2 顶层装配哈希复核一致。

## 可见启动

- 本轮授权的一次可见启动已消耗；
- `SLDWORKS.exe`：PID 59616；
- 主窗口：`SOLIDWORKS Premium 2024 SP5.0`；
- SolidWorks revision：`32.5.0`；
- 主进程数量：1；
- COM 绑定：成功；
- 启动后文档数：0；
- 启动后活动文档：`NULL`。

## 恢复对话框裁决

可见启动期间未出现恢复对话框、恢复候选列表、许可提示、版本转换、
未来版本、缺失引用、宏安全或外部引用警告。

因此：

- 冻结资产恢复动作：0；
- 候选恢复文件打开动作：0；
- 恢复列表文件数：0；
- 恢复对话框截图：`NOT_APPLICABLE_DIALOG_NOT_PRESENT`。

受控桌面检查已观察启动界面和空白工作区，但没有不存在的恢复对话框可供归档截图。

## 空白零件烟测

文件：

`00_BASELINE/SW_SESSION_SMOKE_TEST_20260729.SLDPRT`

第一次烟测在保存成功后、文件仍被 SolidWorks 占用时提前计算哈希，触发
`0x80070020` 并失效闭合。该失败记录已保留为：

`07_VERIFICATION/B51R1_SOLIDWORKS_VISIBLE_SESSION_RECOVERY_ATTEMPT_001_FAIL_CLOSED.json`

修正为关闭文件后再计算哈希，随后在同一可见实例完成：

1. 保存；
2. 关闭；
3. 重新打开；
4. 路径读回；
5. 外部引用计数读回；
6. 再次关闭。

最终结果：

- 保存文件 SHA-256：`FD24B397EE519795BFBE89AE79864A87AD01AC6152E0151FE29B1CED957432D8`；
- 保存字节数：40360；
- 重开 errors：0；
- 重开 warnings：0；
- 外部引用计数：0；
- 最终文档数：0；
- 最终活动文档：`NULL`；
- Gate：`PASS_VISIBLE_SINGLE_INSTANCE_SAVE_CLOSE_REOPEN_COM_BIND`。

控制 receipt：

`07_VERIFICATION/B51R1_SOLIDWORKS_VISIBLE_SESSION_RECOVERY.json`

本记录只提供会话恢复信用，不提供 Master Skeleton、原生运动链、H10 或 T005 信用。
