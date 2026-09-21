# 航天服务星与 B601：SolidWorks 原生零件及装配

本次接续中断工作，已把 WP04 的三态数字装配候选转换为 **443 个可复用 .SLDPRT 零件、3 个整机 .SLDASM、1 个连接局部 .SLDASM 和 1 个 B601 机械臂 .SLDASM**。零件含实际边界表示实体，整机引用这些零件，可在 SolidWorks 2024 中展开组件树、逐件选择、隐藏和继续设计。

[服务态整机](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/WP05_SW_20260907/assemblies/WP05_ROBOT_SERVICE.SLDASM>) · [零件目录](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/WP05_SW_20260907/parts>) · [原生交付核验](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/WP05_SW_20260907/results/INDEPENDENT_NATIVE_DELIVERY_CHECK.json>) · [实例与零件清单](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/WP05_SW_20260907/bom>)

![SolidWorks 服务态整机](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/WP05_SW_20260907/screenshots/WP05_ROBOT_SERVICE.png>)

| 配置 | 原生装配文件 | 组件实例 | 解析实体数 |
|---|---|---:|---:|
| 服务态 | [WP05_ROBOT_SERVICE.SLDASM](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/WP05_SW_20260907/assemblies/WP05_ROBOT_SERVICE.SLDASM>) | 585 | 966 |
| 开放停放态 | [WP05_ROBOT_PARKING.SLDASM](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/WP05_SW_20260907/assemblies/WP05_ROBOT_PARKING.SLDASM>) | 585 | 966 |
| 释放态 | [WP05_ROBOT_RELEASED.SLDASM](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/WP05_SW_20260907/assemblies/WP05_ROBOT_RELEASED.SLDASM>) | 585 | 966 |

[R07 连接局部装配](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/WP05_SW_20260907/assemblies/WP05_R07_CONNECTIONS.SLDASM>)含 245 个实例，用于检查主结构、端塞、跨板、套管与相关连接关系；[B601 机械臂服务态装配](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/WP05_SW_20260907/assemblies/WP05_B601_SERVICE.SLDASM>)含 10 个链接组件，保留整机 S 系下的服务姿态坐标。“开放停放态”不表示已满足发射收拢包络。

零件全部执行保存、关闭、重新打开，记录实体数、曲面体数、体积、包围盒和外部引用。整机保存后重新打开，逐项核对组件编号、实际依赖路径、安装变换、表示角色、固定状态和可解析实体。三态装配的组件、坐标、依赖和实体数量核对已通过。包含几何传递判据在内的独立回执核验状态为 **FAIL**，必需检查计数为 `{'PASS': 18329, 'FAIL': 48}`。此独立检查读取真实 COM 执行回执和文件 SHA；没有把回执检查称为另一 CAD 内核的独立装配试验。


**几何保留项：10 个零件未通过完整材料传递核验。** 当前文件可用于查看与继续修复，不得声明全套几何等价已通过。无效实体指标属于 OCC 对源或回导 BRep 的检查结果，不能直接认定为实物缺陷。逐零件/实体索引与数值见 [几何问题清单](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/WP05_SW_20260907/results/GEOMETRY_HOLD_REGISTER.json>)。

| 零件 | 核验结果 | 源无效实体索引 | 回导无效实体索引 | 同核体积差 mm³ |
|---|---|---|---|---:|
| B601_base_link_LINKLOCAL | FAIL | [58, 59] | [59] | 未取得结果 |
| B601_link1_LINKLOCAL | FAIL | 未取得结果 | 未取得结果 | 0.002325166016817093 |
| B601_link2_LINKLOCAL | FAIL | [3, 4, 61, 62] | [1, 3] | 未取得结果 |
| B601_link3_LINKLOCAL | INCOMPLETE | 未取得结果 | 未取得结果 | 未取得结果 |
| B601_link4_LINKLOCAL | INCOMPLETE | 未取得结果 | 未取得结果 | 未取得结果 |
| B601_link5_LINKLOCAL | INCOMPLETE | 未取得结果 | 未取得结果 | 未取得结果 |
| B601_link6_LINKLOCAL | INCOMPLETE | 未取得结果 | 未取得结果 | 未取得结果 |
| B601_gripper_link_LINKLOCAL | FAIL | 未取得结果 | 未取得结果 | 0.006225599761819467 |
| B601_gripper_left_LINKLOCAL | INCOMPLETE | 未取得结果 | 未取得结果 | 未取得结果 |
| B601_gripper_right_LINKLOCAL | INCOMPLETE | 未取得结果 | 未取得结果 | 未取得结果 |

有 419 个零件通过实体数、曲面体数、体积及包围盒核对；这些指标不等同于逐面材料等价证明。另保留了 24 项跨内核标量体积差诊断，未放宽原数值阈值。对这 24 项执行了 SolidWorks 实际 STEP 回导，并逐件进行有时间上限的同一 OCC 内核材料差检查，结果为 `{'PASS': 14, 'FAIL': 4, 'INCOMPLETE': 6}`；FAIL 与 INCOMPLETE 均保留为未关闭项。详见 [回导几何验证](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/WP05_SW_20260907/results/NATIVE_ROUNDTRIP_VALIDATION.json>)。STEP 导出前需激活目标文档并清空选择，依据 [SOLIDWORKS API 文档](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~SaveAs.html)。早期导出崩溃及失败诊断保留在 queue 与 results 中。

每态仍是 **193 项物理几何、355 项简化代理、37 项功能包络**；功能包络在原生主视图中隐藏，可通过组件树查看。585 个实例不等于 585 件完成选型的实物零件。10 个机械臂链接按原 STEP 内部实体与链接局部坐标保留；不同构型引用各自的安装变换。

现有 .SLDPRT 使用导入 BRep 特征，尚未重建全套草图、尺寸和加工特征树；.SLDASM 使用固定姿态组件，尚未建立可驱动的完整配合机构。不能从本次原生转换推导全机无干涉、连续动作通过、强度通过或制造放行。SW 默认材质或密度不用于整机质量结论。质量未知字段保留为空；历史零件号按来源保留，仍需结合实际候选几何校核，特别是旧 M4×22 标识与已缩短的前端螺钉。

为控制内存，建议一次打开一个整机装配；整机按轻化形式保存，编辑时再解析所需组件。打开时保留本目录的 `assemblies/` 与 `parts/` 相对目录关系；当前实际重开检查的依赖均在本交付目录内。此轮未进行搬移目录后的独立重开试验。`bom/WP05_INSTANCES_*.csv` 每态逐实例列出原编号、角色、原零件号、规范零件路径及来源；`WP05_CANONICAL_PARTS.csv` 分态列数量并取三态最大值，不把互斥配置用量相加作采购数量。

质量表分别保存 CAD 来源字段与已绑定的数字身体分配字段。原来源字段有 188 项非空；数字身体账本有 198 项分配与 387 项 UNKNOWN，其中 10 个机械臂链接质量从已接受 URDF 逐链接核对、仅计一次。数字分配合计 20.733608541407722 kg，不是完整整机实测质量，也不能与原来源列再次相加。

现在可以进入 SolidWorks 接口细化与装配设计审查：先逐项处理几何保留项、重建关键连接件参数特征，再建立保持器导向、防脱、止挡及退出锁止的完整结构和运动配合，再检查盖板、设备、工具与线束装入路径。随后用实际 B601/器件 ICD、材料、紧固件和载荷输入完成尺寸链、连接承载、预紧及完整制造图。既有重点未关闭项包括 2.5 mm 沉孔残底、1.13276253 mm 叉座净距、0 mm 旧侧螺钉名义间隙、八处螺纹代理未知、整机连续避碰以及质量未知项，仍以 [WP04 详细设计输入清单](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/MECHANICAL_INPUT_REGISTER_ZH.md>) 和 [装配工序](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp04_robot_assembly_20260906_175153/ASSEMBLY_PROCEDURE_ZH.md>) 为入口。

已另附 [SolidWorks 后续细化与检查工序](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/WP05_SolidWorks后续细化与检查工序_20260907.md>)，明确几何修复、参数特征、可动配合、保持机构、装入路径与图纸的后续执行顺序。这些步骤仍待实施。

本轮 33 项输入文件和前轮封存的 596 个文件 SHA 均保持一致，见 [来源保护](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/WP05_SW_20260907/results/SOURCE_PRESERVATION_FINAL.json>)。原研究 Gate、制造状态和硬件许可没有升级。
