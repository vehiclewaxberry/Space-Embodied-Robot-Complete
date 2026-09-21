# 第三方代码、供应商与参考资源

<!-- WORKSPACE_NAV_START -->
**2026-09-21 目录整理入口：** [本域用途与归档总览](../01_project/governance/WORKSPACE_ORGANIZATION_20260921/WORKSPACE_INDEX.html?domain=80_third_party) · [全项目导航](../PROJECT_MAP.md)。历史来源和证据原位保留；本轮整理不改变设计或科学结论。
<!-- WORKSPACE_NAV_END -->

导航整理：2026-09-06。本域保存外部代码、参考平台和供应商资源；外部来源与项目自有设计、计算结果分开。

- [外部参考工程和资料](external/)：按来源、版本和实际消费者定位。
- [供应商及第三方仓库](vendor/)：保留各仓库的许可证、独立版本历史和本地修改信息。
- [文献题录](../50_literature/README.md)：论文进入文献库；[工程定义](../20_engineering/README.md)负责本项目使用这些资料形成的设计。

许可证与 NOTICE 以对应来源中的实际文件为准；旧导航所述待建目录不视为已存在。第三方参考或演示结果不自动成为本项目结论。

旧导航中的 `notices/` 是待建的项目随行许可证、NOTICE 与来源哈希记录目录；该规划不代表目录或第三方源资产副本已经存在。

## BIRDSX-CAD 来源入口

优先使用 [birds/BIRDSX-CAD](external/spacecraft_layout_refs/birds/BIRDSX-CAD/) 的完整来源与 [README](external/spacecraft_layout_refs/birds/BIRDSX-CAD/README.md)。[birdsx/BIRDSX-CAD](external/spacecraft_layout_refs/birdsx/BIRDSX-CAD/) 保留为已有消费者使用的历史镜像，两处属于同一上游来源，不应计作两份独立工程参考。

2026-09-06 本地核验：两库 HEAD 均为 `36bceeacc9f899477f2f10e36f8a65f7b58cb4ed`，共有的 26 个工作树文件逐项 SHA-256 相同；`birds` 工作树完整且干净，`birdsx` 存在原有 `README.md` 删除状态。两库的独立 `.git` 索引与日志有差异，因此各自版本历史和原有工作树状态完整保留。许可证见 [BIRDSX-CAD/LICENSE](external/spacecraft_layout_refs/birds/BIRDSX-CAD/LICENSE)，历史镜像内也保留原许可证。

<a id="librecube-notes"></a>
## LibreCube 接口参考范围

LibreCube 用作模块化开源空间系统的接口思想参考。原第一阶段说明约定暂不深入代码，仅在需要 OBC、EPS 或模块接口定义时再展开；这是原阶段的范围记录，不构成新的实施授权。现有 [LC2102 源库](external/spacecraft_layout_refs/librecube/LC2102/) 与其许可证、版本历史继续保留。

2026-09-06 将原 `external/spacecraft_layout_refs/librecube_notes/README.md` 的三条说明并入本节，并移除该空目录；原文完整字节保存在整理账本的 SQLite 快照中。此次元数据与目录核验不等同于第三方代码、CAD 原生内部引用或论文全文的专业审查。
