<!-- generated-by: tools/build_delivery_report.py; WP07_DELIVERY_FACTS_V1 -->
# WP07 机械设计与装配交付记录

生成时间（UTC）：2026-09-06T22:40:44.363977+00:00。本文件按现存文件与机器记录汇总本轮事实，不是新的工程 Gate 或制造放行。

当前 3/3 个构型具备与现有原生文件、依赖哈希绑定的完整冷检查记录。597 实例整机分支只集成 WP06 侧向连接改动：保留 573、替换 8、删除 4 个旧裸杆件并新增 16 个紧固件，目标为 978 个实体。本轮保持机构的局部候选尚未并入这套整机。

模块执行入口：[当前机械模块执行状态表](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/MECHANICAL_MODULE_EXECUTION_STATUS.csv>) 列出 16 个模块的本轮实际执行、剩余边界和证据。原 [MECHANICAL_MODULE_MATRIX.csv](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/MECHANICAL_MODULE_MATRIX.csv>) 是准备阶段清单，保留其当时状态；当前执行表不代表各模块工程设计全部完成。

## 原生装配与查看

| 构型 | 当前文件与检查事实 | 证据 |
|---|---|---|
| [SERVICE](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/native/WP07_ROBOT_SERVICE.SLDASM>) | 原生已保存；597 实例 / 978 实体完整冷检记录绑定当前文件 | [PASS_NATIVE_SERVICE_COMPONENTWISE_COLD__FULL_STEP_NOT_VERIFIED](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/NATIVE_SERVICE_RECOVERY_FAST_V2.json>) |
| [PARKING](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/native/WP07_ROBOT_PARKING.SLDASM>) | 原生已保存；597 实例 / 978 实体完整冷检记录绑定当前文件 | [PASS_NATIVE_FIXED_POSE_COMPONENTWISE_COLD__FULL_STEP_NOT_VERIFIED](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/NATIVE_PARKING.json>) |
| [RELEASED](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/native/WP07_ROBOT_RELEASED.SLDASM>) | 原生已保存；597 实例 / 978 实体完整冷检记录绑定当前文件 | [PASS_NATIVE_FIXED_POSE_COMPONENTWISE_COLD__FULL_STEP_NOT_VERIFIED](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/NATIVE_RELEASED.json>) |

原生文件使用已固定哈希的 WP05/WP06 链接依赖；每态清单含 445 个不同原生零件文件，三态清单合计 460 个。当前不是独立 Pack and Go 包，移动装配文件时必须保留这些依赖路径。

**整机 STEP：** 本轮没有获得完整整机 STEP 交付证据；源组合 STEP 与原生回导 STEP 分别记录，不能互换。 已生成的局部装配、PCB 参考和分件 STEP 单独交付，不等于完整整机 STEP。

B601 的 10 个原生零件沿用既有几何 HOLD；实体计数、变换复核或 GLB 可视化不解除这些 HOLD，也不代表整机材料等价或全局无干涉。

SERVICE 最终只读重开已完成，[最终重开记录](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/FINAL_REOPEN_SERVICE_V4.json>) 绑定当前原生文件及 597 实例 / 445 个依赖的身份、哈希、矩阵与固定状态。978 个实体及实际 COM 四基点来自同一原生文件哈希下的先前完整冷检；此次未重新逐体或重新采集 COM 四基点，也未保存原生文件。这不单独证明整机图像已渲染或已目视审阅。

## 局部保持机构候选

这些成果是独立的局部候选，未集成到上述 597 实例整机。以下照录实际检查状态；名义几何或有条件装配路径结果不代表真实螺纹、预紧、强度或连续动作完成。

| 记录 | 模式 / 站点 / 姿态 | 实际状态 | 已记录检查数量 |
|---|---|---|---|
| [results/RETENTION_BOTH_STATIONS_CROSS.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/RETENTION_BOTH_STATIONS_CROSS.json>) | — / — / — | PASS_BOUNDED_AABB_SEPARATION | — |
| [results/retention_detail/station_0/CHECK_local.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/retention_detail/station_0/CHECK_local.json>) | local / 0 / None | INCOMPLETE | {'PASS': 456, 'INCOMPLETE': 19} |
| [results/retention_detail/station_0/EMISSION_RECEIPT.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/retention_detail/station_0/EMISSION_RECEIPT.json>) | — / 0 / — | CAD_CANDIDATE_NOT_VALIDATED | — |
| [results/retention_detail/station_1/EMISSION_RECEIPT.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/retention_detail/station_1/EMISSION_RECEIPT.json>) | — / 1 / — | CAD_CANDIDATE_NOT_VALIDATED | — |
| [results/retention_detail_c03/station_0/CHECK_local.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/retention_detail_c03/station_0/CHECK_local.json>) | local / 0 / None | PASS | {'PASS': 475} |
| [results/retention_detail_c03/station_0/CHECK_neighbours_parking.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/retention_detail_c03/station_0/CHECK_neighbours_parking.json>) | neighbours / 0 / parking | PASS | {'PASS': 9895} |
| [results/retention_detail_c03/station_0/CHECK_neighbours_released.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/retention_detail_c03/station_0/CHECK_neighbours_released.json>) | neighbours / 0 / released | PASS | {'PASS': 9895} |
| [results/retention_detail_c03/station_0/CHECK_neighbours_service.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/retention_detail_c03/station_0/CHECK_neighbours_service.json>) | neighbours / 0 / service | PASS | {'PASS': 9895} |
| [results/retention_detail_c03/station_1/CHECK_local.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/retention_detail_c03/station_1/CHECK_local.json>) | local / 1 / None | PASS | {'PASS': 475} |
| [results/retention_detail_c03/station_1/CHECK_neighbours_parking.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/retention_detail_c03/station_1/CHECK_neighbours_parking.json>) | neighbours / 1 / parking | PASS | {'PASS': 9895} |
| [results/retention_detail_c03/station_1/CHECK_neighbours_released.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/retention_detail_c03/station_1/CHECK_neighbours_released.json>) | neighbours / 1 / released | PASS | {'PASS': 9895} |
| [results/retention_detail_c03/station_1/CHECK_neighbours_service.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/retention_detail_c03/station_1/CHECK_neighbours_service.json>) | neighbours / 1 / service | PASS | {'PASS': 9895} |
| [results/RETENTION_NATIVE_S0_c03_v1.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/RETENTION_NATIVE_S0_c03_v1.json>) | — / 0 / — | PASS_NATIVE_FIXED_LOCAL_ASSEMBLY_COLD_REOPEN_ONLY | — |
| [results/RETENTION_NATIVE_S1_c03_v1.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/RETENTION_NATIVE_S1_c03_v1.json>) | — / 1 / — | PASS_NATIVE_FIXED_LOCAL_ASSEMBLY_COLD_REOPEN_ONLY | — |
| [results/RETENTION_WP06_CROSS_STATION0.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/RETENTION_WP06_CROSS_STATION0.json>) | — / — / — | PASS_SELECTED_STATION_AABB_SEPARATION | — |

C03 对照器 [results/retention_detail_c03/station_0/CHECK_local.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/retention_detail_c03/station_0/CHECK_local.json>) 实际记录 475/475 项 PASS；其几何输入仍来自已生成的 C02 局部零件。这不增加整机集成或强度、真实螺纹与制造放行的结论。

C03 对照器 [results/retention_detail_c03/station_1/CHECK_local.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/retention_detail_c03/station_1/CHECK_local.json>) 实际记录 475/475 项 PASS；其几何输入仍来自已生成的 C02 局部零件。这不增加整机集成或强度、真实螺纹与制造放行的结论。

各邻域对照记录分别对应表中指定站点、冻结姿态和邻件合同；其检查数量不相加作为全机或连续动作验证。

两站交叉结果 [results/RETENTION_BOTH_STATIONS_CROSS.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/RETENTION_BOTH_STATIONS_CROSS.json>) 的实际状态为 PASS_BOUNDED_AABB_SEPARATION；记录 2091 对比较。下面两个子集分别列示：

| 指定子集（三个冻结姿态） | 分离 / 比较对数 | 最小距离下界 mm | NEEDS_BREP |
|---|---|---|---|
| 站 0 的 17 件 × 站 1 的 17 件 | 867/867 | 38.0 | 0 |
| 站 1 的 17 件 × WP06 的 24 个改件 | 1224/1224 | 24.0 | 0 |

该记录的分组数量一致性：True；当前输入哈希绑定：True。原站 0 对 WP06 的交叉记录独立保留，不把这些数量合并为全机碰撞、连续路径或制造验证。

保持机构与 WP06 改件的交叉检查 [results/RETENTION_WP06_CROSS_STATION0.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/RETENTION_WP06_CROSS_STATION0.json>) 记录 1224/1224 对包围盒分离，0 对需要进一步 BRep 处理。这仅覆盖所选保持机构与 24 个 WP06 改件，不是整机全部邻件或连续运动检查。

| 局部原生装配 | 实际交付事实 |
|---|---|
| [Station 0 局部装配](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/native/RET_S0_c03_v1/WP07_RETENTION_S0_LOCAL_CANDIDATE.SLDASM>) | 已保存并冷检 18 实例 / 18 实体（17 个候选零件 + 1 个已有上下文零件）；独立局部坐标，未整星回装 |
| [Station 0 局部原生回导 STEP](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/native/RET_S0_c03_v1/local_assembly_roundtrip.step>) | 实际导出文件；有限有效性检查见下表，未声明布尔材料等价 |
| [Station 1 局部装配](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/native/RET_S1_c03_v1/WP07_RETENTION_S1_LOCAL_CANDIDATE.SLDASM>) | 已保存并冷检 18 实例 / 18 实体（17 个候选零件 + 1 个已有上下文零件）；独立局部坐标，未整星回装 |
| [Station 1 局部原生回导 STEP](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/native/RET_S1_c03_v1/local_assembly_roundtrip.step>) | 实际导出文件；有限有效性检查见下表，未声明布尔材料等价 |

### 已执行的局部与参考几何有效性检查

以下读取真实 CAD `validate` 的结构化 stdout，并核对已结束的 guard、目标路径和实际 STEP 哈希。目标为 `.step` 的两项是局部原生回导 STEP；目标为 `.step.py` 的项是生成源几何检查，并以单独 `refs` 结果绑定已导出的 STEP。这些有限检查不等于源/回导体的双向布尔材料等价或整机有效性。

| 目标与范围 | 实际 occurrences / failures | 结果 |
|---|---|---|
| [局部原生回导 STEP / validate_native_retention0](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/native/RET_S0_c03_v1/local_assembly_roundtrip.step>) | 18 / 0 | [PASS_SCOPED_CAD_VALIDITY_LOG](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/logs/validate_native_retention0.stdout.log>) |
| [局部原生回导 STEP / validate_native_retention1](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/native/RET_S1_c03_v1/local_assembly_roundtrip.step>) | 18 / 0 | [PASS_SCOPED_CAD_VALIDITY_LOG](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/logs/validate_native_retention1.stdout.log>) |
| [局部视图源几何 / validate_retention_view0](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/candidate/retention_station0.step>) | 18 / 0 | [PASS_SCOPED_CAD_VALIDITY_LOG](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/logs/validate_retention_view0.stdout.log>) |
| [局部视图源几何 / validate_retention_view1](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/candidate/retention_station1.step>) | 18 / 0 | [PASS_SCOPED_CAD_VALIDITY_LOG](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/logs/validate_retention_view1.stdout.log>) |
| [PCB 参考源几何 / validate_pcb_reference](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/candidate/pcb_reference_panels.step>) | 4 / 0 | [PASS_SCOPED_CAD_VALIDITY_LOG](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/logs/validate_pcb_reference.stdout.log>) |

## 可视化与电气

显示文件按已执行记录和当前哈希选择：优先采用 V4 精确紧缩 GLB，保留 V3 的源 STEP / BRep 缓存来源。GLB 是显示用三角网格；精确紧缩只保持已引用的显示字节、层级和变换，不代表渲染完成、BRep 有效性、间隙或机械验收。

[优先载入：V4 精确紧缩 GLB](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/viewer/WP07_SERVICE_BREP_REVIEW_V4_COMPACT.glb>)：实际状态 PASS_EXACT_DISPLAY_COMPACTION；文件 82,706,304 字节，597 个实例。实际显示与目视审阅另见下方记录。

V4 来源为 [V3 显示记录](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/viewer/REVIEW_GLB_V3_RESULT.json>)；保留完整顶点属性（含 CAD 边缘）、索引、三角形顺序和实例变换。597 项世界包围盒检查由字节与变换不变关系继承，未增加新的几何验证。

- [viewer/REVIEW_GLB_RESULT.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/viewer/REVIEW_GLB_RESULT.json>)：FAIL_DISPLAY_BOUNDS；旧 V1 失败历史，不作为当前通过预览。
- [viewer/REVIEW_GLB_V3_RESULT.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/viewer/REVIEW_GLB_V3_RESULT.json>)：PASS_DISPLAY_REVIEW_ONLY；[显示候选文件](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/viewer/WP07_SERVICE_BREP_REVIEW_V3.glb>)。
- [viewer/REVIEW_GLB_V4_COMPACT_RESULT.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/viewer/REVIEW_GLB_V4_COMPACT_RESULT.json>)：PASS_EXACT_DISPLAY_COMPACTION；[显示候选文件](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/viewer/WP07_SERVICE_BREP_REVIEW_V4_COMPACT.glb>)。

[打开 service 交互查看器](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/viewer?file=WP07_SERVICE_BREP_REVIEW_V4_COMPACT.glb)。

[打开 retention_station0.step.py 交互查看器](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/candidate?file=retention_station0.step.py)。

[打开 retention_station1.step.py 交互查看器](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/candidate?file=retention_station1.step.py)。

[打开 pcb_reference_panels.step.py 交互查看器](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/candidate?file=pcb_reference_panels.step.py)。

[交互查看器实际交接记录](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/VIEWER_HANDOFF.json>)：THREE_INTERACTIVE_VIEWS_ACTUALLY_OPENED_AND_REVIEWED。

[实际图像审阅记录](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/VISUAL_REVIEW.json>)：LOCAL_PNG_AND_WHOLE_INTERACTIVE_DISPLAY_REVIEWED__NO_WHOLE_SNAPSHOT_PNG；当前哈希仍匹配且已审阅的图像 12 张。

| 图像组 | 当前文件绑定与审阅事实 | 图像 |
|---|---|---|
| retention0 | 实际本地图像已审阅，仅显示范围 | [retention0_front_20260906T222900Z.png](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/snapshots/retention0_front_20260906T222900Z.png>)、[retention0_iso_20260906T222900Z.png](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/snapshots/retention0_iso_20260906T222900Z.png>)、[retention0_opposite_20260906T222900Z.png](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/snapshots/retention0_opposite_20260906T222900Z.png>)、[retention0_top_20260906T222900Z.png](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/snapshots/retention0_top_20260906T222900Z.png>) |
| retention1 | 实际本地图像已审阅，仅显示范围 | [retention1_front_20260906T222905Z.png](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/snapshots/retention1_front_20260906T222905Z.png>)、[retention1_iso_20260906T222905Z.png](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/snapshots/retention1_iso_20260906T222905Z.png>)、[retention1_opposite_20260906T222905Z.png](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/snapshots/retention1_opposite_20260906T222905Z.png>)、[retention1_top_20260906T222905Z.png](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/snapshots/retention1_top_20260906T222905Z.png>) |
| pcb_reference | 实际本地图像已审阅，仅显示范围 | [pcb_reference_front_20260906T222910Z.png](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/snapshots/pcb_reference_front_20260906T222910Z.png>)、[pcb_reference_iso_20260906T222910Z.png](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/snapshots/pcb_reference_iso_20260906T222910Z.png>)、[pcb_reference_opposite_20260906T222910Z.png](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/snapshots/pcb_reference_opposite_20260906T222910Z.png>)、[pcb_reference_top_20260906T222910Z.png](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/snapshots/pcb_reference_top_20260906T222910Z.png>) |
| service | 实际交互画面已审阅，绑定 GLB 哈希；无整机 PNG | [交互查看器](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/viewer?file=WP07_SERVICE_BREP_REVIEW_V4_COMPACT.glb) |

整机 SERVICE 交互画面已在本轮实际加载并审阅，当前 GLB 源文件哈希仍匹配。尚无已保存的完整整机 PNG；交互画面审阅不改写 scripts/snapshot 的失败记录。

整机快照尝试分别记录如下；内存保护、浏览器页面关闭或不支持的显示模式属于显示流程结果，不判为几何失败。

| 快照尝试 | 实际运行状态 |
|---|---|
| [snapshot_service.run.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/logs/snapshot_service.run.json>) | JOB_WORKING_SET_GUARD |
| [snapshot_service_v4.run.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/logs/snapshot_service_v4.run.json>) | COMMAND_FAILED |
| [snapshot_service_v4_rendered.run.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/logs/snapshot_service_v4_rendered.run.json>) | COMMAND_FAILED |
| [snapshot_service_v4_single.run.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/logs/snapshot_service_v4_single.run.json>) | COMMAND_FAILED |

电气工作仍按参考提取、接口草案与静态一致性记录；未形成可上电接线或完成电气设计的结论。

[电气包说明](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/ecad/README.md>)。
- [ELECTRICAL_BUILD_RECEIPT.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/ELECTRICAL_BUILD_RECEIPT.json>)：STATIC_REFERENCE_EXTRACTION_COMPLETED；模块 16，参考板卡 4。
- [ELECTRICAL_CONTRACT_CHECK.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/ELECTRICAL_CONTRACT_CHECK.json>)：CONSISTENT_DRAFT_ELECTRICAL_COMPLETION_BLOCKED；模块 16，未闭合模块 14，被拒绝的负对照 9。
- [ELECTRICAL_MECHANICAL_FIT_SCREEN.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/ELECTRICAL_MECHANICAL_FIT_SCREEN.json>)：BOUNDED_ARITHMETIC_SCREEN_COMPLETED；参考板卡 4。
- [ELECTRICAL_READY_CHECK.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/ELECTRICAL_READY_CHECK.json>)：CONSISTENT_DRAFT_ELECTRICAL_COMPLETION_BLOCKED；模块 16，未闭合模块 14，被拒绝的负对照 0。
- [ELECTRICAL_TOOL_DISCOVERY.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/ELECTRICAL_TOOL_DISCOVERY.json>)：STATUS_NOT_DECLARED。

### 未选型 PCB 机械参考

参考合同包含 4 块裸板、156 条源板框/内部槽边、26 个机械相关钻孔记录及各自源文件厚度。源数据的 3649 个总钻孔/过孔记录已经包含这 26 个；另有 3623 个未建模。

[已生成 PCB 机械参考 STEP](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/candidate/pcb_reference_panels.step>)；当前状态：REFERENCE_STEP_CURRENT_READBACK_PASS。
[独立 STEP 读回结果](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/PCB_REFERENCE_STEP_READBACK.json>)：PASS；与当前 STEP 哈希绑定的完成证据：有。
已生成快照文件：[pcb_reference_front_20260906T222910Z.png](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/snapshots/pcb_reference_front_20260906T222910Z.png>)、[pcb_reference_iso_20260906T222910Z.png](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/snapshots/pcb_reference_iso_20260906T222910Z.png>)、[pcb_reference_opposite_20260906T222910Z.png](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/snapshots/pcb_reference_opposite_20260906T222910Z.png>)、[pcb_reference_top_20260906T222910Z.png](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/snapshots/pcb_reference_top_20260906T222910Z.png>)。快照存在不单独记为审阅通过。

这 4 块板是未选型的机械参考，并非服务星已经选定的 PCB；未包含真实已装器件高度、铜层与完整布线，也不代表服务星原理图完成、已经分配机内安装位置或完成电气设计。它们没有加入 597 实例整机。
读回检查重新加载实际 STEP，期望参数仍复用生成源的纯参数提取；不声明全板框逐点或材料等价。

## 中断、未完成与范围

以下保留本轮全部未成功结束的受控任务；内存保护、主动停止、检查失败与超时分别照录，不改写为成功。

| 任务 | 实际状态 | 运行秒数 | 最低可用内存 MiB |
|---|---|---|
| [native_service](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/logs/native_service.run.json>) | AVAILABLE_MEMORY_GUARD | 751.73 | 404.94 |
| [recover_service_componentwise](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/logs/recover_service_componentwise.run.json>) | COMMAND_FAILED | 282.44 | 877.96 |
| [recover_service_fast_full](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/logs/recover_service_fast_full.run.json>) | AVAILABLE_MEMORY_GUARD | 49.38 | 496.78 |
| [retention_local0_c02](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/logs/retention_local0_c02.run.json>) | COMMAND_FAILED | 83.71 | 573.16 |
| [review_glb_service](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/logs/review_glb_service.run.json>) | COMMAND_FAILED | 3.52 | 1955.58 |
| [snapshot_service](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/logs/snapshot_service.run.json>) | JOB_WORKING_SET_GUARD | 10.70 | 1281.56 |
| [snapshot_service_v4](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/logs/snapshot_service_v4.run.json>) | COMMAND_FAILED | 32.73 | 1552.08 |
| [snapshot_service_v4_rendered](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/logs/snapshot_service_v4_rendered.run.json>) | COMMAND_FAILED | 0.55 | 2557.95 |
| [snapshot_service_v4_single](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/logs/snapshot_service_v4_single.run.json>) | COMMAND_FAILED | 32.87 | 1635.78 |
| [source_service](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/logs/source_service.run.json>) | AVAILABLE_MEMORY_GUARD | 94.93 | 483.44 |

后续仍需完成保持机构的整机邻件核验与受控回装、冻结实际硬件及接线、质量预算、强度与公差、连续动作与实物装配验证。本轮不声明整星机械设计完成、全局无干涉、硬件上电许可、制造放行或飞行适用。

完整事实与文件哈希见 [DELIVERY_STATUS.json](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp07_system_20260907_0610/results/DELIVERY_STATUS.json>)。
