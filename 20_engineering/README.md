# 工程设计、参数与装配入口

<!-- WORKSPACE_NAV_START -->
**2026-09-21 目录整理入口：** [本域用途与归档总览](../01_project/governance/WORKSPACE_ORGANIZATION_20260921/WORKSPACE_INDEX.html?domain=20_engineering) · [全项目导航](../PROJECT_MAP.md)。历史来源和证据原位保留；本轮整理不改变设计或科学结论。
<!-- WORKSPACE_NAV_END -->

整理日期：2026-09-21。本域保存当前机械候选、被引用的上游模型、参数和历史验证来源。先按以下入口阅读；目录名中的 RELEASE、FINAL 或版本号不能独自证明工程完成或可制造。

**硬件设计的精简工作入口为 [SERVICE_STAR_HARDWARE_COMPACT_20260921](SERVICE_STAR_HARDWARE_COMPACT_20260921/README.md)。其中当前服务态总装以R6H为准，保留后续水平安装集成，并包含机械、电气线束、能源热控和推进主文件。原R6H总装未删除；WP03属于上游机械基线，不能替代R6H。整理状态与公开边界见包内说明。**

## 当前设计与装配

| 内容 | 入口与职责 |
|---|---|
| 当前硬件精简副本 | [硬件设计总入口](SERVICE_STAR_HARDWARE_COMPACT_20260921/README.md)：R6H机械总装及电气、热控、推进主设计 |
| 当前机械源总装 | [R6H原生服务态总装](SERVICE_STAR_CORE_INSTALLATION_R6H_20260920/native/SERVICE_STAR_SERVICE_R6H.SLDASM)、[现行指针](SERVICE_STAR_CORE_INSTALLATION_LATEST.json) |
| 上游完整机械基线 | [WP03](service_robot_wp03_spacecraft_body_r1/README.md)：星体、完整 B601、双翼、保持器、设备接口和总装图册；保留其来源职责 |
| 装配和实际交付范围 | [装配程序](service_robot_wp03_spacecraft_body_r1/ASSEMBLY_SEQUENCE.md)、[交付回执](service_robot_wp03_spacecraft_body_r1/results/DELIVERY_RECEIPT.json) |
| 仍被 WP03 读取的上游 | [WP01](service_robot_wp01_20260905/)与[WP02](service_robot_wp02_20260905/)：机械臂、根框、接触、线束及检查输入；不是三套可互换的当前整星 |
| 参数和接口 | [config](config/)、[design_inputs](design_inputs/)、[parameter_registry](parameter_registry/)：按各模型所属版本使用 |
| 原生 CAD 和厂家/accepted 来源 | [cad](cad/)；保留 donor、冻结基线和原生装配引用关系 |
| 审阅与系统材料 | [design_review](design_review/)、[system_design](system_design/)、[automation](automation/) |

## R2 与早期版本的职责

- [R2 原终裁](MECHANICAL_ENGINEERING_RELEASE_R2/00_RELEASE_GATE.json)与[基线清单](MECHANICAL_ENGINEERING_RELEASE_R2/01_BASELINE_MANIFEST.json)独立描述 R2；不被 WP03 候选覆盖。
- R2 后续具名记录由[发布来源指针](../01_project/current/CURRENT_RELEASE_POINTERS_V1.yaml)定位，包括 [ODR-60 Option A](MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/results/ODR60_OPTION_A_EXECUTION_CLOSURE_GATE_V1.json)。
- `F3*`、`F4*`、`F5*` 的版本树包含 donor、失败几何、冻结输入和验证链。旧导航所称 M7“当前”仅指当时记录；其 [V5 continuation Gate](F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/15_loop_continuation_v5/MECHANICAL_LOOP_ENGINEERING_CONTINUATION_GATE_V5.json)原结论为 HOLD，不覆盖本页 WP03 入口。
- 27 个 `_MFINAL_G0_SMOKE_*` 目录共 83 个 JSON，是旧会话/连接核查回执；已有历史脚本按路径读取，集中在索引中作为回执组查看。目录多不表示存在 27 套机械设计，本轮保持路径和证据身份。
- [Stage 1 早期库](stage1_spacecraft_layout/README.md)包含早期参考、布局需求、坐标和预算模板。已合并三组中英文需求、一份建库说明和一份英文资产镜像；适配器英文原件因 A4 清单固定 SHA 保留。
- [原根结构材料](system_design/legacy_root_structure/)保留合同原值和独立职责。

## 缓存、压缩包与重复件为什么有些保留

WP01/02/03 的 `__cadgen__` 编目分别为 4,132 / 1,368 / 8,454 文件，合计 **13,954**。这些是 CAD 可视化/拓扑派生物及诊断来源，数量不等于设计零件数。已查 WP03 的 Python 生成视图包与 STEP 导入视图包具有不同 stepHash 和网格参数；[包络方法比较](service_robot_wp03_spacecraft_body_r1/results/BOUNDING_METHOD_COMPARISON.json)固定了 assembly、542 个组件 GLB 和 topology GLB 的输入身份。交付汇总与图册脚本也读取这些包，已有 PNG 或 STEP 不足以证明它们全部可删除。

工程域剩余 11 个 ZIP 为 9 个 B51 授权/阶段包、1 个原终端基线包、1 个 V5 失效模型隔离包。它们不是 11 份同字节文件；其中已检查的基线包和隔离包被回执固定 SHA/范围，保留原始包。来源许可、O11/O13、PHASE0 等相同正文的 donor 副本也有 source/copy 分别绑定的情形，不能只保留一份后仍声称原验证链完整。

Route-C V8 第 1 回路简报的冗余副本已删除，保留 [规范简报](MECHANICAL_ENGINEERING_RELEASE_R2/route_c/B601_ROUTE_C_V8_CAD_BRIEF.md)；该回路的被拒绝模型、构建器、JSON 和网格证据仍在原处。

已从 WP01/WP02/WP03 删除 159 个对应源码存在、文件头匹配且未发现固定输入绑定的 Python 字节码，源码均保留。审阅的其余 197 个缓存保持原位；12 个删除文件后已空的缓存目录因自动审批拒绝删除而保留。未执行冷启动或重新编译来宣称重建通过。

## 全域记录

[统一整理入口](../01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/CURRENT_candidate.md)连接逐文件目录、处置理由、删除映射及原始字节备份。对目录和文件用途的登记不等于逐件打开 CAD、验证全部动态引用或全文专业精读；这些范围在账本中分别标记。
