# 当前工程入口：WP09R 原生装配、电气与推进设计增量

2026-09-08：从 [本轮交付说明](runs/wp09_interfaces_20260907_1525/system_completion/README.md) 与 [可视化查看页](runs/wp09_interfaces_20260907_1525/system_completion/REVIEW.html) 进入。三态原生 SolidWorks 各 873 叶零件、10 固定容器，19 个唯一子装配；新增太阳面层、修订叠层机构与 R01 标准件。实际保存、冷重开及搬迁见 [原生交付回执](runs/wp09_interfaces_20260907_1525/system_completion/results/NATIVE_DELTA_DELIVERY.json)。原 705 组件便携包保留。

实际停止电路已并入系统两页原理图：94 元件/96 网/72 条外部主表连接、191 项连接核验；[主接线表](runs/wp09_interfaces_20260907_1525/system_completion/ecad/MASTER_FROM_TO.csv) 与 [分层 BOM](runs/wp09_interfaces_20260907_1525/system_completion/ecad/MASTER_BOM.csv) 为当前子版，父版同名文件保留历史身份。真实官方 MotorBridge DLL 完成18项边界ABI检查，DM公开电机型号与ID已绑定，原生串口/MIT编码未执行。推进源侧针位与安装螺纹已修正，模块受控ICD仍未绑定。

完整机电系统详细设计仍未完成：辅助供源与停止PCB、星上高功率支路、回生、推进受控接口、完整线束及热/强度/整机动作仍有开放设计责任。现行 [机器状态](runs/wp09_interfaces_20260907_1525/system_completion/results/DELIVERY_STATUS.json) 保留未满足条件与原24项未执行物理检查。原85文件电气/DM参考包、47网一致/29项Python历史验证均保留原身份，不与本轮18项原生ABI检查混记。

下方历次入口原样保留，其中“当前/本轮”均属于记录时刻。

---

# 当前工程入口：WP09R 成熟模块复用与结构候选收束

2026-09-07：从[本轮完整交付](runs/wp09_interfaces_20260907_1525/reuse_closure/README.md)与[可视化查看页](runs/wp09_interfaces_20260907_1525/reuse_closure/REVIEW.html)进入。三态SolidWorks各705组件/1086预期实体已完成本轮增量验收：全组件身份/哈希/变换冷读，新5实体实读，旧1081实体继承父本证据。另有独立RS422地面转接板原生SLDPRT。

实际KiCad系统含70连接记录/117端点/47网络，派生地面板ERC/DRC/板图一致性零违规；系统ERC保留1项停止链供电边界错误。完成29项真实DM协议离线测试、19项电源参数反例及36项推进源/需求核对。K1、P60板位和BPX针位冲突已定点修订；现有EPS不能承担360W机械臂在轨负载，真实推进ICD/功能仍开放。

本轮固定姿态结构候选可冻结；整机完整机械/电气功能、连续动作、制造与飞行放行仍未完成。详见[机器状态](runs/wp09_interfaces_20260907_1525/reuse_closure/results/DELIVERY_STATUS.json)。下方历史入口原样保留，“当前/本轮”均属于其记录时间。

---

# 当前工程入口：WP09F 电气、推进与地面端口候选

2026-09-07：从 [本轮候选交付包](runs/wp09_interfaces_20260907_1525/functional_closure/README.md) 查看完整选型与针位报告、23条导体记录、四张接线原理图、条件电气/推进计算和已通过冷回读的5件SolidWorks端口局部装配。采用用户指定的Seeed reBot-DevArm公开DM基线，未冒充实机出货核验。

局部新原生装配通过不等于整星增量通过。本轮705组件/1086预期实体三态增量未验收，SERVICE保存文件的冷读恢复受内存保护阻断，另两态尚未生成；**整星仍使用下方父版已验证的701组件三态**。已放行电路0，实物检查0/24，实际推进任务能力UNKNOWN。具体开放项和来源见[设计报告](runs/wp09_interfaces_20260907_1525/functional_closure/docs/FUNCTIONAL_DESIGN_REPORT_ZH.md)，机器状态见[DELIVERY_STATUS](runs/wp09_interfaces_20260907_1525/functional_closure/results/DELIVERY_STATUS.json)。

以下父版及历史记录原样保留，其中“本轮/当前”属于记录时的范围。

---

# 当前机械工程入口：WP09 共享舱、推进与DM接口整合

2026-09-07：从 [本轮交付说明](runs/wp09_interfaces_20260907_1525/README.md) 查看3套SolidWorks固定姿态总装，每套701组件/1082几何实体；619组件继承，82实例新增/替换，共享21个新原生零件。服务态全部实体实读，停放/释放态新82实体实读、旧1000实体依冻结WP08证据哈希绑定；全部姿态组件身份/文件哈希/变换已核验。

B601已确认DM，工程样机采用外置RSP-500-24；BPX 8S/P60用于低功率支路。共享舱布局、非承压推进托架与两条静态线束路线已纳入总装。整机机械、电气、制造和飞行放行仍开放；真实端接、设备固定、DM出货机械修订与拆盖/工具验证见[关闭项与开放项](runs/wp09_interfaces_20260907_1525/docs/CLOSURE_DELTA_AND_OPEN_ITEMS_ZH.md)。完整电气回路仍为0。

机器状态见[DELIVERY_STATUS](runs/wp09_interfaces_20260907_1525/results/DELIVERY_STATUS.json)，文件完整性见[FINAL_INTEGRITY](runs/wp09_interfaces_20260907_1525/results/FINAL_INTEGRITY.json)。以下为历史入口，表述属于当时记录。

---

# 当前机械工程入口：WP09 电气与推进局部设计

2026-09-07：从 [WP09 交付说明](runs/wp09_electro_propulsion_20260907_1350/README.md) 查看三套局部 STEP，共44实体；其中 A3200 与 MiPS 的28件原生零件、2套 SolidWorks 固定装配通过冷重开与材料回读。电池源STEP检查通过，沉头螺钉原生转换仍为HOLD。当前状态见 [DELIVERY_STATUS](runs/wp09_electro_propulsion_20260907_1350/results/DELIVERY_STATUS.json)。

[电气与推进机械工作包](runs/wp09_electro_propulsion_20260907_1350/docs/ELECTRO_PROPULSION_MECHANICAL_WORK_PACKAGE_ZH.md) 给出设备实选、EPS/电池/推进共享舱调整、机械臂供电与保持/热/线束接口的后续工作。局部模型未合入WP08，整星机械、电气和制造放行仍未完成。

现有整星三态仍从 [WP08](runs/wp08_retention_delta_20260907_1228/README.md) 查看，保留每态625实例及后肋局部未回装状态。

以下为历史入口，表述属于当时记录。

---

# 当前机械工程入口：WP08

2026-09-07：从 [WP08 实际交付说明](runs/wp08_retention_delta_20260907_1228/README.md) 查看三态 SolidWorks 装配、后肋局部实体及检查记录。两站保持器已回装，每态625实例/1006实体；后肋11实例局部连接已验证但尚未回装整机。

整星机械与电气尚未完成。后续具体实体任务见 [下一批机械执行单](runs/wp08_retention_delta_20260907_1228/docs/NEXT_MECHANICAL_EXECUTION.md)。WP07与更早结果、失败记录及原问题账本继续保留。

以下为此前入口与文件整理历史，其中“当前/本轮”表述仅属于当时记录。

---

# 项目文件整理与机械设计工作入口

更新：2026-09-07。当前机械与机电接口审阅从 [WP07 交付说明](runs/wp07_system_20260907_0610/README.md) 进入；其中列出实际生成文件、原生回读、局部几何检查、参考 PCB 及尚未关闭的接口。

本轮为工程样机候选执行，不表示整机机械、电气、实物装配或制造放行完成。原 17 项问题记录保持原样，新增执行链接见 [issues.json](issues.json) 的 `wp07_execution`。

以下保留 2026-09-06 文件整理记录；其“本轮”及未运行 CAD 等表述只属于当时整理范围。

更新：2026-09-06。日常入口为 [PROJECT_MAP](../../../PROJECT_MAP.md)，机械总装从 [WP03](../../../20_engineering/service_robot_wp03_spacecraft_body_r1/README.md) 进入。本页记录已执行整理和实际覆盖范围，原机械问题继续保存在 [issues.json](issues.json)。

## 本轮内部整理的实际结果

- **删除 33 份 Markdown**：31 份经内容比较后归并到 11 个保留入口，另 2 份与保留件完全同字节。仅新建 2 份合并文，其余使用已有文件。
- **删除 159 个可再生 Python 字节码**，源码全部保留并重新核对 SHA。限定审阅的 356 个缓存中，其余 197 个因证据绑定、版本/头差异或消费者范围未查清而保留。
- 共删除 **192 个文件、4 个空目录**。12 个另外已空的缓存目录因自动审批拒绝删除而保留，未修改访问权限。
- 修改了导航及已定位的消费者引用；原件均备份在已有 SQLite，不再生成同样内容的归档 Markdown 或压缩包。
- 整理后八域可枚举范围为 **53,176 个文件、6,731 个子目录**，根目录仍为 **19 项**。相比本轮开始净少 190 个文件（删 192、新增 2）。这些数量包含运行环境、第三方库和派生物，并非设计零件数；SQLite WAL/SHM 会随连接启停变化。

| 合并内容 | 现在阅读的位置 | 本轮删除源数 |
|---|---|---:|
| 任务背景、状态、研究问题、领域概念、架构决定与早期规划 | [背景与状态沿革](../../../10_research/knowledge_base/project_context/README.md)、[早期研究规划](../archive/EARLY_RESEARCH_PLAN_20260711_20260717.md) | 13 |
| 分散模块卡、旧仿真基线说明及同字节报告副本 | [模块索引](../../../30_simulation/module_cards/README.md)、[仿真入口](../../../30_simulation/README.md) | 12 |
| Stage 1 双语需求、建库说明、英文资源镜像及 Route-C 简报副本 | [Stage 1](../../../20_engineering/stage1_spacecraft_layout/README.md)、[工程入口](../../../20_engineering/README.md) | 6 |
| 旧补充文献迁移备注与 LibreCube 来源说明 | [文献入口](../../../50_literature/README.md)、[第三方来源入口](../../../80_third_party/README.md) | 2 |

旧 PL1 模块卡复制树检查被新合并结构取代后，消费者明确报告原复制范围为历史 HOLD；其余复制检查仍保留。没有把改目录后的检查伪装成原 15/15 结果。

## 哪些内容保留，以及为什么

- WP01/WP02 仍是 WP03 的输入，R2、历史模型、失败几何和科学负结果分别保留。原生 CAD、坐标、质量惯量 CSV 与科学 Gate 未在本轮修改，也未运行 CAD/动力学/控制程序。
- WP01/WP02/WP03 的 13,954 个 `__cadgen__` 文件包括图册消费者和包络诊断的来源；已有图片或 STEP 未证明它们可完整替代。
- 工程域剩余 11 个 ZIP 有不同哈希与授权/基线/失效原件职责；来源清单固定的 donor 副本也保留。两份 BIRDS 工作树包含独立 Git 状态，已标明主参考与历史镜像。
- A4 清单固定的适配器英文要求、研究状态 v4、R2 V1–V7 链及具名历史回执保留原始身份。历史记录中出现旧路径可用下述映射定位；原记录日期、数字和裁决不被无痕更新。

## 审阅覆盖与尚未完成的范围

本轮对全部可访问路径登记了角色和保留/删除理由，并给各已登记子目录记录审阅范围。**这不等于逐个文件都已完成专业全文或原生内容审查。** 删除 Markdown 的依据是具名的全文比较；字节码依据是源码、文件头及消费者检查；大量其余项仅有既有提取记录或元数据/用途分类。

仍有 **10 个 pytest 临时子树拒绝访问**；原生 CAD 内部装配引用、PDF 图形、动态消费者以及未精读正文继续标为待审阅。统一账本中的 `previous_read_status` 不因本轮分类被升级。最终追加的独立复核因额度中断未完成；根代理完成最终恢复、路径和执行账核验，前面已完成的独立比较与检查分别保留。

自动审批两次拒绝删除已核实为空的缓存目录，返回仅为 `blocked by policy`。12 个目录保留；此记录不表示文件删除失败，也不作为清空其他目录的授权。

## 逐文件查询与恢复

使用唯一 [full_project_catalog.sqlite](runs/loop0_20260905/screening/full_project_catalog.sqlite)：

- `domain_inventory` / `domain_subtree_review`：原编目、逐项处置、目录审阅范围；新合并文件已补登记。
- `domain_actions` / `domain_current_locations`：本轮原路径、动作、保留内容位置、执行状态及恢复阶段；历史引用通过这里追溯。
- `snapshots`：删除/修改前原始字节，以 zlib 存储。按动作中的 `snapshot_stage` 解压后核对 SHA256 和长度，再按需恢复。
- `reviews` / `meta`：内容比较、消费者检查、独立验证与当前范围；`ENGINEERING_PYC_READONLY_REVIEW_20260906` 是字节码逐件检查记录。

[run_manifest](run_manifest.json) 与 [dependency_manifest](dependency_manifest.json) 的旧 WP03 字段保留历史身份；新增 `domain_internal_consolidation_20260906` 记录本轮结果。文件快照属于恢复凭据，不是新的设计版本。

## 前一轮根目录整理（独立范围）

此前根目录 45→19 项，19 份 Markdown 合为 2 份，77 个独有文件归入业务域；删除 24 文件和 18 空目录。原启动/入驻内容进入[根部历史综述](../archive/ROOT_HISTORY_20260729_20260810.md)，原 knowledge 方法进入[结构方法](../../../10_research/knowledge_base/spacecraft_mechanical_design/legacy_structure_methods_20260728.md)。明细在 `root_layout_actions`，恢复阶段为 `BEFORE_ROOT_PHYSICAL_CONSOLIDATION_20260906`；更早的 12 文件缓存清理也单独记账，不重复计入本轮 192 文件。
