# Q201 降损候选，尚未替换

只读审查建议优先评估 IXTX200N10L2，IXTH110N10L2 为较小封装改动备选。当前 ECAD 保持 IXTH75N10L2。

| 型号 | 25°C 最大 Rds(on)，Vgs=10V | Rjc 最大 | 典型 Qg | 封装 |
|---|---:|---:|---:|---|
| IXTH110N10L2 | 18 mΩ | 0.21 K/W | 260 nC | TO247，有安装孔 |
| IXTX200N10L2 | 11 mΩ | 0.12 K/W | 540 nC | PLUS247，无安装孔，需压夹 |

原厂PDF：[110，DS100235(01/10)](https://www.littelfuse.com/assetdocs/Littelfuse-Discrete-MOSFETs-N-Channel-Linear-IXT-110N10-Datasheet.PDF?assetguid=943FCDE2-5B6B-487D-B3B5-86C224D05696)、[200，DS100239(2/10)](https://www.littelfuse.com/assetdocs/littelfuse-discrete-mosfets-ixt-200n10-datasheet?assetguid=6bb6dc09-793f-4e09-b710-59fcc558e7da)。两份仍标 Advance，直连本地下载曾403，没有本地PDF哈希信用。

200 的 tab 仍带 Drain 电位，不能当绝缘封装；压夹20–120 N范围不等于实际已实现。110 的 SOA 表出现80V×3.6A与360W不一致，不能取较有利数值。图14为壳温75°C、单脉冲条件，未对实际热短路轨迹数字化验收。

[LM5069 Rev G](https://www.ti.com/lit/ds/symlink/lm5069.pdf)门极充电电流10/16/22 µA；Qg典型值仅供尺度判断，不构成启动/过冲时间上界。任何替换需重新绑定门极电荷、外部栅阻/寄生、TIMER、热态故障Vds–Id–时间轨迹及绝缘夹具热路径。
