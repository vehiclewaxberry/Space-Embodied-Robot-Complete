# B51R1 Autonomous Loop + Multi-Agent Engineering Package

本包把“逐次人工批准”改为“站立式委托 + 分级自治”。

关键变化：

1. G1A datum、命名、公差和 Stage A 锁文件可由机器委员会裁决。
2. S01–S18 使用一个有界会话池自动续跑，不再每一步向用户索要批准。
3. 当前命名方案改为 `JOINT_SIDE_EXPLICIT_V2`，避免
   `CS_PARENT_JOINT` / `CS_CHILD_JOINT` 的反直觉 ownership。
4. H9 不强行自主选择；在缺少 launcher/deployer ICD 时自动维持 Mode A/B 双分支。
5. 冻结基线、accepted URDF、真实硬件、采购和制造/飞行声明仍是不可委托边界。
6. 日常失败由 Agent 最多尝试两种不同恢复路线；只有不可委托问题才通知用户。

本包是执行政策和提示词，不代表本地 SolidWorks 已经运行。
