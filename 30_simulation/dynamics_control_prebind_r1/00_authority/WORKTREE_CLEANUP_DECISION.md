# Worktree Cleanup Decision

本轮只删除了可以证明可再生成或有逐字节规范副本的内容，共 164 个文件、
约 1,590,285 字节。Mechanical R2、Accepted B601、E23、Sim13、Route-C
物理设计与历史负结果均未删除。

当前机械中间产物候选为 769 项，已知大小
2694154152 字节。其中约 2.65 GB 位于旧 V5
`13_validation/quarantine/`；这些目录包含失败样本和负结果原件，不能仅因名称为
quarantine 就删除。应先建立可恢复归档、验证 manifest 覆盖和独立恢复测试，再由
owner 单独批准第三批清理。

仍留在根目录但与 V5NATIVE `99_tools` 不同哈希的历史脚本也保持 HOLD；不同哈希
意味着它们不是可证明的重复副本。Route-C 正在运行的脚本、日志、备份和输出保持
机械线独占，只读不清理。
