# Current State

`DYNAMICS_CONTROL_PREBIND_R1` 已建立隔离预绑定胶囊。PB-00 Unified R2 零广义力诊断数值检查通过，
但由于 PB-G0-A 未通过，PB-G1 仍为 `HOLD`，不产生正式控制或机械发布信用。

关键诊断量：

- 初始动能：1.5728968053616468e-05 J
- 最大相对能量漂移：4.523550e-15
- 最大线动量残差：3.602424e-18 N*s
- 最大角动量残差：5.204453e-18 N*m*s
- 仓库 HEAD：`5c5addea00ddb70d86a5cc37a88bbcda50350e43`；dirty=`true`，无留存信用。

下一合法动作是关闭 PB-G0 权威缺口并由 owner 重判；不是 NMPC/RL/VLA。
