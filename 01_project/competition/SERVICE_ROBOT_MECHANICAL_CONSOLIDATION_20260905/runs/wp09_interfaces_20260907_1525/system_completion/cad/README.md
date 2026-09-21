# WP09D 原生 SolidWorks 三态装配候选

打开 WP09D_SERVICE.SLDASM、WP09D_PARKING.SLDASM 或 WP09D_RELEASED.SLDASM。将 ZIP 全部文件解压到同一个短目录；零件不可分开移动。建议完整路径少于 250 个字符。

每态顶层 10 个固定子装配容器、递归 873 个叶部件；容器不重复计入叶部件。1254 个实体为当前装配成员结合零件证据的 SHA 绑定计数。138 个本轮原生零件逐一冷读实体/包围盒/体积；其中 8 个边框另通过同内核往返几何等价校核，保留 SolidWorks 标量体积差异。其他零件继承母版 SHA 证据，未重测全部 1254 个实体。

三态已冷启动读取组件 ID、变换和本地依赖；三态另在原目录缺席时移至另一短目录逐态冷读，并将文件原样返回。冷读在隐藏文档会话内完成；如提供 PNG，则来自独立 SolidWorks Large Design Review 会话的实际视口 BMP 无损转换，图像不承担几何验证。可选图像失败不取消实际保存/冷读证据。

保存使用每组最多 96 叶的两级固定子装配和 AvoidRebuildOnSave；子装配父变换全部为 identity，叶部件保留原 native T，并冷读核验完整父链。未执行强制全量特征重建。保存前后及冷读的实际 NeedsRebuild2/SaveFlag 记录于项目结果目录 results/NATIVE_DELTA_DELIVERY.json 的 rebuild_state_each。

本包为固定姿态的结构候选，不具有连续运动、制造或飞行放行结论。太阳电池层仅表示玻璃占位投影；完整 CIC 引出片/互连包络未知。机电功能、全机构连续间隙及实物装配验证仍须按项目总体状态验收。
