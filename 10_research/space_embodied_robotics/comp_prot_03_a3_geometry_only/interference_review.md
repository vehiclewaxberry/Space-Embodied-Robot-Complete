# A3 Geometry Only 干涉审查

## 结果

`CURRENT_Q0_CONSERVATIVE_ENVELOPE_INTERFERENCE_COUNT: 0`

SolidWorks 在当前总装、当前 q=0 参考姿态和当前保守包络代理下返回 0 个干涉。嵌入式安装堆叠同时满足：

- bus 最大 X：`185.25000000000003 mm`
- adapter 最小 X：`158.24999999999997 mm`
- adapter 最大 X：`185.25 mm`
- B601 base 最小 X：`185.24999998211861 mm`

## 适用边界

该结果仅用于发现当前几何样机的明显装配重叠，不证明：

- B601 全工作空间无碰撞；
- 真实供应商曲面、紧固件、线束或公差无干涉；
- 抓取、接触或在轨任务安全；
- 发射收拢构型成立。

因此本项状态为 `PASS_FOR_CURRENT_GEOMETRY_PROXY_ONLY`。
