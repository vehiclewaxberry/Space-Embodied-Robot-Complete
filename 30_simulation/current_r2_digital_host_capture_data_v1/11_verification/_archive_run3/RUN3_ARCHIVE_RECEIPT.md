# Run3 无损归档回执

- 状态：`ARCHIVED_AS_DIAGNOSTIC_OR_SUPERSEDED_RUN`
- 源工件时间：`2026-08-27T06:53:32.410398+00:00`
- 归档时间：`2026-08-27T16:34:31.0441529+09:00`
- 归档范围：6 份验证裁决、22 个完整 episode 包、S02/S03/S07 结果、生成 plant、数据集清单、运行脚本及 Run3 执行字节码证据。
- 完整性：285 个源/目标文件逐文件 SHA-256 相同，共 783797 bytes。
- 哈希清单 SHA-256：`D439C990455D118CA213AECB0A70F3D2CB5D3B6EA384615DB2F66D78C73D93C1`；CSV 分列保存 source/destination SHA-256 与 match 状态。
- Run3 执行 `scen_dynamics` 字节码 SHA-256：`9CFCBEF2DEA9CECF060A5BCED9CA85CF649F8E72B4030BB8122DCC505D71BADE`。

Run3 的 `DH-G0=FAIL` 与 S02 case 1 `FAIL_ORDER_OUT_OF_RANGE` 均原样保留。归档不把负结果改写成 PASS，也不授予父 Gate、控制或机械发布信用。

注意：目标目录在 Git 中整体未跟踪，且旧 runner 未生成 run-level 源码清单。归档因此额外保存了运行时 CPython 3.13 字节码；当前 R4 源码只作为“Run3 后待执行修改”保存，不宣称它是 Run3 源码。
