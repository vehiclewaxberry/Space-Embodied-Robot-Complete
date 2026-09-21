# ODR-GPT-04 冻结 Route-B 分支证伪收据 V1

生成时间：2026-08-24T02:43:43.387533+08:00

## 裁决

- 证伪器完整性：18/18 PASS；负控：18/18 PASS。
- 当前冻结 Route-B 的 ODR-GPT-04 额定任务包络分支：**已证伪**。
- 直接原因：当前注册证据为 10 个强制状态 0/10 SAFE、8 条轨迹 0/8 released、Mission Coverage FAIL，同时 Route-B 终局冻结明确 `reopening=NONE_PERMITTED`。因此当前冻结分支没有合法的继续搜索或发布路径。
- `span_link5` 在这些注册状态下的确定性模型输出约 0.100123 mm，对 30 mm 要求的最小缺口约 29.899877 mm；它是根因诊断，不是“任意 q 均失败”的全域证明，因为最终连接器还存在构型相关圆角裁剪与重采样。
- 10 个强制状态 0/10 SAFE；8 条轨迹 0/8 released；Mission Coverage 保持 FAIL。
- 当前不再对冻结 Route-B 投入轨迹搜索、姿态重绑或限速优化算力。

## 边界

这不是“所有外置线束拓扑都不可能”的结论，也不是“所有 q 均 UNSAFE”的结论或物理资格鉴定结论。75 点地图不是六维空集证明；圆角裁剪的全域不变量尚未建立。所有数值均带 mm/rad 量纲，但没有可用的计量不确定度，故只作为冻结模型/软件合同证据。

红队还发现：10/10 强制状态的 `per_joint_pinch_mm.joint6` 均为 null；每个状态也有一个或多个 `per_field_clearance_mm` 为 null，而 V1 聚合仍记 `empty_comparison_sets=0`。它们不改变当前负结果，但任何未来正向 Route-C 谓词必须把任一必需 joint/field 的 null 判为 UNKNOWN/ABORT。

## 唯一受控前进方向

继续 Route-C 的 P01-P13 物理输入闭环，达到 Checkpoint-B 8/8 后再取得独立 CAD 授权并建立新物理路线；或者由 Owner 另行授权一个版本隔离的新中心线/新谓词 ECR。两者都不得重开、改名或美化当前冻结 Route-B。

Owner acceptance、Route-C CAD authority、next-stage authority、release credit 均保持 false。
