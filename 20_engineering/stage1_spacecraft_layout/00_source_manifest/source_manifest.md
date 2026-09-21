# Stage 1 Spacecraft Layout Source Manifest

更新时间：2026-06-16（2026-07-09 记账回填：3 份标准 PDF 状态由 `manual_download_needed` 更正为 `downloaded_ok`；新增对 `02_open_bus_reference/` 66 条外部资产目录的反向指针，见文末「补充」节。回填属 read-safe 记账，未改动上表 8 个 clone 仓库记录。）

说明：外部 GitHub 参考仓库统一放在 `80_third_party/external/spacecraft_layout_refs/`。本次为第一阶段资料库初始化，Git 仓库采用 `git clone --depth 1 --single-branch` 浅克隆；若后续需要完整历史，在对应仓库目录执行 `git fetch --unshallow`。

| 源名称 | URL | 本地路径 | 用途 | 当前状态 | 是否作为主设计依据 | 是否只是参考 | 与本项目的关系 |
|---|---|---|---|---|---|---|---|
| OreSat Structure | https://github.com/oresat/oresat-structure | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-structure` | 6U/12U CubeSat 开源机械结构、框架、板卡堆叠和结构布局参考 | cloned_ok；HEAD=`4c02299` | 是 | 否 | 第一阶段服务星机械布局的主开源结构参考，用于约束外形、结构分层、安装接口和布局图表达。 |
| OreSat Solar Hardware | https://github.com/oresat/oresat-solar-hardware | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-solar-hardware` | 太阳翼/太阳板硬件、展开面和外表面布置参考 | cloned_ok；HEAD=`af8f6f3` | 否 | 是 | 用于辅助服务星外表面、太阳电池板与机械臂避让关系设计。 |
| OreSat Backplane | https://github.com/oresat/oresat-backplane | `80_third_party/external/spacecraft_layout_refs/oresat/oresat-backplane` | 背板、电气接口、板卡堆叠接口思想参考 | cloned_ok；HEAD=`0e1550c` | 否 | 是 | 用于理解 CubeSat 内部板卡、线束和模块化接口，不直接作为动力学模型依据。 |
| BIRDSX-CAD | https://github.com/BIRDSOpenSource/BIRDSX-CAD | `80_third_party/external/spacecraft_layout_refs/birds/BIRDSX-CAD` | 开源 CubeSat CAD、结构件和教育卫星布局参考 | cloned_ok；HEAD=`36bceea` | 否 | 是 | 作为目标星/小卫星模型外观、结构层级和图纸组织方式参考。 |
| PyCubed Hardware | https://github.com/pycubed/hardware | `80_third_party/external/spacecraft_layout_refs/pycubed/hardware` | 开源 CubeSat OBC/EPS/通信一体化硬件板卡参考 | cloned_ok；HEAD=`d1adfd0` | 否 | 是 | 用于估计星务电子板卡尺寸、安装位置和质量预算条目，不作为服务星主结构依据。 |
| PyCubed Software | https://github.com/pycubed/software | `80_third_party/external/spacecraft_layout_refs/pycubed/software` | 开源 CubeSat 飞控软件结构参考 | cloned_ok；HEAD=`72ab3a1` | 否 | 是 | 第一阶段仅记录为星务软件与任务流程参考，不进入当前动力学或控制代码。 |
| SpaceRobotEnv | https://github.com/Tsinghua-Space-Robot-Learning-Group/SpaceRobotEnv | `80_third_party/external/spacecraft_layout_refs/spacerobotenv/SpaceRobotEnv` | 自由漂浮空间机械臂环境、轨道服务与强化学习任务参考 | cloned_ok；HEAD=`155989c` | 否 | 是 | 用于后续自由漂浮基座动力学、空间机械臂任务建模、GJM/RNS 反作用抑制对照阅读。 |
| SPOT | https://github.com/Carleton-SRCL/SPOT | `80_third_party/external/spacecraft_layout_refs/spot/SPOT` | 地面低摩擦/气浮平台与空间机器人验证参考 | cloned_ok；HEAD=`66a4929` | 否 | 是 | 用于 reBot 地面样机验证、低摩擦平台试验构型和验证指标设计参考。 |
| LibreCube Notes | https://librecube.org/ | `80_third_party/README.md#librecube-notes` | 模块化开源空间系统接口思想参考 | manual_download_needed；第一阶段暂不 clone | 否 | 是 | 当前仅保留接口思想备注；后续需要 OBC/EPS/模块接口定义时再展开。 |
| CubeSat Design Specification Rev. 14.1 | https://www.cubesat.org/s/CDS-REV14_1-2022-02-09.pdf | `20_engineering/stage1_spacecraft_layout/01_standards/CubeSat_Design_Specification_Rev14_1_2022-02-09.pdf` | 1U-12U CubeSat 外形、质量、结构和发射接口初步约束 | `downloaded_ok`（2026-06-16，SHA256 present_hash_match，见 `01_standards/standards_manifest.md`；⚠️ Appendix B 图纸尺寸文本解析失败，待人工目视复核） | 是 | 否 | 作为 6U/12U 服务星外形、结构包络、发射接口和机械布局边界的标准依据。 |
| NASA CubeSat 101 | https://www3.nasa.gov/sites/default/files/atoms/files/nasa_csli_cubesat_101_508.pdf | `20_engineering/stage1_spacecraft_layout/01_standards/NASA_CubeSat_101_Basic_Concepts_First_Time_Developers.pdf` | CubeSat 任务流程、评审、接口、合规和系统工程入门依据 | `downloaded_ok`（2026-06-16，SHA256 present_hash_match，正文已提取，见 `01_standards/standards_manifest.md`） | 是 | 否 | 用于组织第一阶段到后续方案阶段的系统工程流程、质量属性和交付物检查。 |
| NASA Small Spacecraft Technology State-of-the-Art 2026 | https://www.nasa.gov/smallsat-institute/sst-soa/ | `20_engineering/stage1_spacecraft_layout/01_standards/NASA_Small_Spacecraft_Technology_SOA_2026.pdf` | 小卫星平台、结构、电源、推进、GNC、通信、热控等技术状态参考 | `downloaded_ok`（2026-06-16，SHA256 present_hash_match，458 页正文已提取，含非致命解析警告，见 `01_standards/standards_manifest.md`） | 是 | 否 | 用于 300-500 kg 级空间服务微卫星平台选型、分系统边界和技术可行性论证。 |

---

## 补充：外部开源在轨资产目录（2026-07-09 记账回填指针）

> 本 manifest 原仅覆盖上表「8 个 clone 仓库 + 3 份标准 PDF + LibreCube 备注」。此后经多智能体联网检索 + 逐条 URL/许可核验，新增的**开源在轨航天器资源目录（66 条，9 类角色）** 已落库到 `02_open_bus_reference/`。上表 8 个 GitHub 仓库仍为**主参考基线**（已 clone、记录 HEAD）；下列 66 条目录为其**补充**，二者不重复登记。此处建立 manifest → 目录的反向指针（此前仅有目录 → manifest 单向链）：

| 配套文档 | 路径 | 角色 |
|---|---|---|
| 外部资产唯一入口 | [`../02_open_bus_reference/external_onorbit_asset_catalog.md`](../02_open_bus_reference/external_onorbit_asset_catalog.md)（中文合并入口；英文镜像于 2026-09-06 归并，原文可从整理账本恢复） | 66 条资源目录 |
| 许可闸门 | [`../02_open_bus_reference/license_gate_v0.md`](../02_open_bus_reference/license_gate_v0.md) | 合规过滤（A/A-/B/C/D） |
| CAD 交付物映射 | [`../02_open_bus_reference/cad_asset_mapping_v0.md`](../02_open_bus_reference/cad_asset_mapping_v0.md) | 资源→8 类交付物 |
| 缺口风险 | [`../02_open_bus_reference/external_asset_gap_risks_v0.md`](../02_open_bus_reference/external_asset_gap_risks_v0.md) | RA-001~007 |
| 落地验收 | [`../07_next_actions/landing_audit_report_v1.md`](../07_next_actions/landing_audit_report_v1.md) | 本轮验收审计 |