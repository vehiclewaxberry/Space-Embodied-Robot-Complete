# B5.1R1 原生机械设计状态记录：S01 PASS / S02 HOLD

生成时间：2026-08-02 21:05:46 +08:00

## 当前有效结论

- S01 已通过：最终原生 B51R1_MASTER_SKELETON_V2.SLDPRT 已创建。
- S01 当前 Gate：S01_PASS_NATIVE_MASTER_SKELETON_CREATED。
- S02 尚未通过：本次失败发生在 ATTACH_EXPECTED_FRESH_PROCESS，未进入 OpenDoc6。
- 因未打开目标文件，本次没有执行重建、读回或 CAD 保存。
- S03 原生 10-Carrier 构建未获准启动。

## S01 原生骨架事实

- 最终文件：02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2.SLDPRT
- 大小：232506 bytes
- SHA-256：71D70F93C356CB4AFDA9C2F594811F683502781C4C6243EF25C2BB888DDEBEFA
- 原生合同：21 项必需特征、3 个配置、0 实体、0 外部引用。
- 受保护 Stage A SHA-256：
  5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B
- S01 Current Gate SHA-256：
  314A413809DE05EBDF584121D68DA39701683EA9928F0170F90CB0920FF08D95
- S01 旧 HOLD、自动停止事故和三次失败记录均未覆盖。

## S02 失败事实

- 启动进程：PID 43500，单一可见 SolidWorks 2024 进程。
- 失败原因：新进程在内部 30 秒 ROT/StartupProcessCompleted 窗口内未达到可附着状态。
- 运行时观察：21:03:45 进程暂时无响应；21:04:18 恢复响应，晚于内部附着截止时间。
- Gate receipt：07_VERIFICATION/AUTONOMOUS/S02/B51R1_S02_GATE_RECEIPT.json
  SHA-256 5B03B48F4E583CAEFB0EF36E7F1A56AFC85A8E769CCC57CDCB0EFDE65AADD80E
- Session receipt：07_VERIFICATION/AUTONOMOUS/S02/B51R1_S02_SESSION_EXECUTION_RECEIPT.json
  SHA-256 D30BD774F40C5F766C09193015BA46B75A3E8A7B1236359936B8EFB6F6ECEF73
- Incident：07_VERIFICATION/AUTONOMOUS/S02/B51R1_S02_FAIL_CLOSED_INCIDENT.json
  SHA-256 F203FBA2000A7F0D5CD57B2B5D57F3C9B274BD3735168C741F586DB7AB5494DE
- 清理结果：SolidWorks 进程数 0；未使用强制终止。

## 已完成的 S02 工具工程化

R2 工具已经独立离线复核通过，但尚未取得 live S02 PASS：

- 两条坐标系 API 的原始矩阵、两条 IInverse() 和固定刚体代数逆三路闭合；
- 11 个受控基准面的真实位置与法向；
- 4 根纵梁轴的端点；
- 25 个受控特征/辅助特征与 44 项精确总特征库存；
- 3 个配置 × 10 个循环，共 30 次重建和完整读回；
- GetBodies2(swSolidBody,false)=0；
- GetBodies2(swAllBodies,false)=0；
- GetMassProperties2 返回 swMassPropertiesStatus_NoBody；
- 全部受控自定义属性使用 Get6(..., UseCached=false) 新鲜解析；
- 只读打开、零 Save/SaveAs 调用，目标/Stage A/Current Gate 的 SHA、字节数和修改时间前后守卫；
- 不允许 Kill、Stop-Process 或其他强制终止。

R2 supplemental lock：
09_DELIVERY/B51R1_AUTONOMOUS_G1A_CLOSURE_20260801/B51R1_PHASE2A_INPUT_LOCK_V3_S01_SUPPLEMENT_R2.json

SHA-256：
F6C7D18FA5B063B6F0D1200F13B4EB406AF1486477BC408C06A7EDFE153B3447

## 授权与预算状态

- 已消耗会话：5 / 20。
- 剩余可见启动预算：15。
- 当前 ledger 状态：BLOCKED_S02_COLD_REOPEN_FAIL_CLOSED。
- 当前 next_session_authorized=false。
- 之前用户新增的一个恢复槽明确绑定 S01，并已由 SR03 消耗。
- 现有授权不包含 S02 恢复槽，因此不得自动再次启动 SolidWorks。

## 推荐恢复入口

最稳妥路线：

1. 用户手动打开 SolidWorks，等待欢迎页完全响应；
2. 明确授权新增一个 S02 恢复槽；
3. 新恢复会话只附着现有进程，不再直接启动第二个进程；
4. 使用新的 append-only S02 recovery receipt 路径，永久保留本次失败；
5. S02 通过后才允许启动 S03 原生 10-Carrier 构建。

备选路线是在用户明确授权后，将新进程 StartupProcessCompleted/ROT 等待窗口扩展到 120 秒。

## 保留项

- H10：0/28
- T005-A/B/C：NOT_RUN
- H9：仍需人工裁决
- 禁止结论：COMPLETE、MANUFACTURING_READY、FLIGHT_READY、LAUNCH_QUALIFIED

当前结论上限：

S01_NATIVE_MASTER_SKELETON_CREATED; S02_HOLD_PRE_CAD_ROT_STARTUP_TIMEOUT
