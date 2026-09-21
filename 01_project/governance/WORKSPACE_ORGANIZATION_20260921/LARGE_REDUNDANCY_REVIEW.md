# 全工作区大文件与重复导出复核

只读复核完成；本审阅未删除或移动文件。复用上轮和本轮八域清单；不修改Git、CAD/Gate、R6H或compact。

可交根代理执行前核对的精确白名单：**3份展示STEP副本，830,303,108 B（791.84 MiB）**。三份均与WP03规范源字节哈希一致；当前封存/构建路径检查未见showcase消费者。历史目录盘点只是存在记录，不构成运行依赖。

| 展示副本 source(copy) | 必须保留 canonical | 字节 | SHA256 |
|---|---|---:|---|
| `40_evidence/artifacts/visualization/cad_showcase_20260916/servicer_service.step` | `20_engineering/service_robot_wp03_spacecraft_body_r1/servicer_service.step` | 276768393 | `05ad2ce4d218b2822b66d6607942108c4f65e0a533471076455af161703e23b2` |
| `40_evidence/artifacts/visualization/cad_showcase_20260916/servicer_released.step` | `20_engineering/service_robot_wp03_spacecraft_body_r1/servicer_released.step` | 276767510 | `7a32616442247ca651a4a0c1a0e9f3f227eea75c4a93732c369aea5b79b53f59` |
| `40_evidence/artifacts/visualization/cad_showcase_20260916/servicer_parking.step` | `20_engineering/service_robot_wp03_spacecraft_body_r1/servicer_parking.step` | 276767205 | `d7420629dc3b547f206d0b04b7f1ccddc769f25bba2164b35e60185760ff70bc` |

执行前重新核对两端文件大小、哈希和解析后路径；仅对三项明确副本操作。WP03的README和VIEWER_LINKS以规范目录为查看器源，各自 `.step.py` 均存在。旧showcase日志记录3245端口；`netstat -ano -p TCP`成功返回，3245/3246当前无匹配。PowerShell网络查询曾拒绝访问，未把它的空返回误算为无监听。

R6H封存清单、来源依赖、装配plan/layout及compact清单/两份来源选择表共7文件均没有showcase路径。旧清单引用不用改写。根代理可在原展示目录新增普通README指向WP03规范源，保留 `viewer_launch.log`；不启动查看器、不重生成CAD/截图。

恢复方法：将对应canonical逐字节复制回原source(copy)，校验本表字节数和SHA256。

另记录 1196 个候选（其中压缩包 72、零字节 1103），12 组非零字节重复。逐项size/hash/重复关系与推荐见 [JSON](LARGE_REDUNDANCY_REVIEW.json)。这些重复量不能直接当作可回收空间。

必须保留：775,008,256 B统一数据库含原始文档快照、审阅与合并账本，入口和manifest明确引用；manifest绑定ZIP、donor、pack-and-go、负结果归档保留；WP01/02/03的__cadgen__有实际消费者；portable运行时保留。原967,765,696 B KiCad安装器已不在，不能重复计算收益。

零字节文件不凭名称删除，本轮没有新增零字节删除清单。压缩包只读中心目录，不以“看似已展开”推定可删。大范围通用basename扫描因零字节同名日志过多而停止，没有依据该未完成扫描授予删除。精确3项决定依据哈希、规范源所有权、现行七文件路径检查及查看器监听检查。

其他候选保持原位，后续归档应沿用父级治理方案，不扩大三项白名单。
