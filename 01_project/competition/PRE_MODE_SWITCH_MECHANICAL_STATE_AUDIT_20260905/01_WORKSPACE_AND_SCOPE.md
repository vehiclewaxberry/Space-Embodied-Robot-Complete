# 工作区、方法与证据覆盖

审计日：2026-09-05。用户附件将任务限定为换线前的机械资产与证据只读审计。新写入范围仅为本目录 `01_project/competition/PRE_MODE_SWITCH_MECHANICAL_STATE_AUDIT_20260905/`。

| 工作区 | 角色 | 本次覆盖 |
|---|---|---|
| `F:\China Graduate Future Flight Vehicle Innovation Competition` | Root A，项目工程/机器 Gate/研究来源 | no-ignore 文件元数据盘点；指定机械权威与候选、原生引用、A3、质量及交接源的针对性审计 |
| `F:\SPACE_ROBOTICS_REFERENCE_LIBRARY` | Root B，只读参考库 | 入口与文件元数据盘点，确认参考属性；未把参考 CAD/软件作为项目真值或运行依赖 |
| `F:\Mechanical structure modeling and simulation` | 外部 CAE 参考（不是 Root B） | 顶层定位；不执行内容 |
| `F:\Robotic arm` | 外部教学/供应商参考 | 顶层定位；不执行内容 |

Root B 的角色由其 `REFERENCE_LIBRARY_START_HERE.md` 明确；其库内无 Git 不表示项目源库失效。本轮没有重新组织目录或迁移任何资产。

## 方法

1. 读取用户附件、PROJECT_MAP、当前机械导航/机器 Gate 和后续 append-only 增量；以来源范围和替代关系确定状态，不按文件名 CURRENT 或修改时间直接升级权威。
2. 三条并行只读分工分别核 A3、资产/总装、授权/具身交接；主审核质量、环境、文件身份和综合报告。各分工输出限定在本审计目录。
3. 原生 CAD 用现存收据与磁盘引用检查、FCStd ZIP 内 `Document.xml` 静态解析。没有通过 CAD API 加载或重建模型，没有启动 SolidWorks/FreeCAD GUI。
4. A3 只对已存姿态读 URDF 和原 STL，独立复算刚体变换、顶点极值和表格算术。没有重跑优化、原生产脚本、FEA、动力学、碰撞或控制。
5. 工具能力只读包元数据并 import VTK 碰撞类；没有安装包、改环境、执行项目 pair/edge/path 查询。官方 VTK/NASA 页面用于核对方法语义，未下载论文或引入外部工程资产。
6. 输出来源路径/哈希，核对选定受保护源的前后哈希，检查报告链接与机器可读附件。所有输出是派生审计，不能覆盖任何源 Gate。

## 覆盖统计与限制

`root_file_inventory.csv` 使用 `rg --files --hidden --no-ignore`，排除 `.git`、`__pycache__` 和本审计输出；它是元数据目录，不是对每个文件全文或几何有效性的证明。

- Root A：37,313 个可列出文件，16,148,329,428 字节。
- Root B：17,520 个可列出文件，3,751,542,248 字节。
- Root A：10 处 `.pytest_cache`/`.pytest-tmp*` 目录访问被拒，rg exit=2；详细路径见 `root_inventory_coverage.json`。未尝试修改权限，未把其内容判不存在。
- Root B：rg exit=0，元数据获取无 stat 错误。
- 初始 Git HEAD：`75143b1d3ba05d9916f016637f37b5abf6004087`；分支与已有脏状态原文在 `root_workspace_before.json`。已有大量工程候选为 `LOCAL_ONLY_UNTRACKED`，未跟踪不等于不存在或无证据，亦不能称为已纳入受控版本发布。

受保护前后快照选取 R2 根文件、Mode A/A3 包、F4R1 包、geometry SSOT 和 accepted URDF，共 134 个文件。前快照在初次只读定位后、主审复算前采集；这不是所有仓库文件的全量前后哈希证明。更广的实际读取源以 `09_SOURCE_SHA256.csv` 封印，并标记 Git 跟踪状态。

## 输出阅读顺序

- `00_航天服务星机械设计现状总览.md`：设计、集成、验证的总体结论。
- `02_ASSET_INTEGRATION_VERIFICATION.csv`：逐对象矩阵，含 A3 八项缺失的重新分类。
- `03_NATIVE_ASSEMBLY_AUDIT.md`：主模型、原生候选、配置、引用、身份与查看路径。
- `04_A3_METHOD_AUDIT.md`：数值复算、方法局限、交接错误与不能继承项。
- `05_AUTHORITY_AND_EMBODIED_HANDOFF.md`：Owner 溯源、父子 Gate 与当前具身交接。
- `06_MASS_AND_COLLISION_CAPABILITY.md`：质量分账、材料/机构缺口、可用工具和资格化边界。
- `07_REUSE_AND_REVALIDATION.md`：复用与新配置验证清单。
- `08_AUDIT_RECEIPT.json`、`09_SOURCE_SHA256.csv`：审计执行与来源证据。

禁止主张：全量磁盘法证完成、所有 CAD 当前冷开通过、全局无解已证明、完整系统无碰撞、机械发布完成、Mode B 已批准、新配置继承旧 PASS。允许主张：在明示检索和解析范围内，现有资产及其有限验证已逐项对应，冲突和缺口已登记。
