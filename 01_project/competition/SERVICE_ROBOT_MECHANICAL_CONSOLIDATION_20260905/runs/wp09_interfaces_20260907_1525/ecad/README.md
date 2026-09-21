# ECAD 静态推进支路候选

本目录只有V6两条ICD交接截面之间的预布线与算术结果。没有已选的完整设备支路。CSV使用UTF-8 BOM；空值表示UNKNOWN，不表示NC或0。数据差分对行是接口需求，配对数量及方向须等供应商ICD，不能按行数采购或裁线。

运行纯算术复算：

```powershell
python .\calculate_power_conditions.py
```

脚本路径可从任意目录执行；输入、输出默认位于脚本旁。仅需Python标准库。它读取已绑定哈希的V6合同，重算两个90°圆角路径，比较`results/EMISSION_V6.json`实际曲线长度，并检查未知电阻传播及严格电压门槛。输入合同改变时会报错，需明确更新快照；不自动接受新几何。

`POWER_CONDITIONS_RESULTS.json`的自检PASS仅针对算术。实际硬件、回路电阻、裁线长度、制造验收仍未闭合。两份`*_PREFAB_CHECKLIST.csv`共24项，全部NOT_EXECUTED；没有现场高压测试参数或上电授权。

本轮来源增量在上一级`research/DEVICE_INTERFACE_DELTA.json`，标准PDF及其哈希在`standards_sources/`和输入JSON中。实际几何检查见主任务结果文件，不由本目录升级结论。

V5绑定哈希保存在`BINDING_REVISION_HISTORY.json`。V6两条路径与V5一致；历史不具有已完成电气或制造放行信用。
