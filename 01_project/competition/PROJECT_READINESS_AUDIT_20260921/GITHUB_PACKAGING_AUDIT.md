# GitHub 公开打包审计

审计日期：2026-09-21。结论：**不宜把当前工作区或当前 Git 历史直接整体公开推送。** 已定位一项确定的 GitHub 文件大小阻断，以及入口、许可声明、可移植复现和未跟踪交付物的发布缺口。现有工程成果可以整理为公开研究候选，不能把“公开”写成“整星工程完成”。

本审计只读检查仓库和文件元数据，并读取具名入口；未上传、提交、删除、改写历史、调整 LFS 或变更现有配置。文件体积单位 GB=10^9 B，MiB=2^20 B。完整机器记录见 [GITHUB_INVENTORY.json](GITHUB_INVENTORY.json)。隐私和第三方授权须同时查阅本审计包其他分项；这里不宣称已经完成秘密扫描或逐项版权许可审计。

## 1. 当前 Git 状态与正确解释

| 项目 | 实测结果 | 发布含义 |
|---|---|---|
| HEAD | `669ce052411971415cddccccfacf70dd486c09ba`，2026-09-19 | 已提交主线截至 R17 文档核验；后续 R1–R6H 等本地内容不能只靠 push 自动带走 |
| 分支 | `docs/fix-third-party-notices-link` | 当前分支名不是完整研究版本的发布说明 |
| remote | 无 | 本地未配置发布远端；本轮未新建远端 |
| index 路径 | 42,466 | 当前 Git 索引统计 |
| 非 ignored 未跟踪路径 | 2,073（初次快照） | 其中 2,054 在 `20_engineering/`；需逐包选择并验证后入发布清单 |
| ignored Git 枚举路径 | 26,310（初次快照） | 包含缓存、PDF、其他排除；不是可随意删除清单 |
| 已跟踪文件状态 | 提权只读复核干净 | 沙箱初报 125 个 `D` 全部是访问限制假象，不是真实删除 |

初始扫描有 37 处目录 PermissionError，Git 同时报告 125 个 `D`。随后提权仅作 stat/list：**37/37 目录可列出，原 125/125 文件均存在，Git 已跟踪状态无差异、无警告**。证据为 [READ_ACCESS_RECHECK.json](READ_ACCESS_RECHECK.json) 和 [SANDBOX_REPORTED_D_PATHS.json](SANDBOX_REPORTED_D_PATHS.json)。不能据初次沙箱输出进行 `git add -u`、清理或宣称证据丢失。文件体积扫描未重做这些目录，因此下面体积保持可读下限。

新增本审计文件和并行审计产物会增加未跟踪计数；2,073 是起始快照，不承诺最终瞬时值。初始完整计数保留在 JSON，提权结果作为明确覆盖解释保留。

## 2. 体积与确定的推送阻断

可读文件共 **117,680** 个、**50.55 GB**，其中根 `.git` **13.87 GB**；排除根 `.git` 的工作目录仍约 **36.68 GB**。这包含 ignored、运行时、缓存、备份和第三方嵌套 `.git`，不是建议的公开仓库体积。扫描不跟随 symlink/reparse，未发现需跳过的 reparse 点。

| 顶域 | 可读文件数 | GB |
|---|---:|---:|
| `01_project/` | 25,535 | 7.709 |
| `10_research/` | 255 | 0.002 |
| `20_engineering/` | 31,677 | 20.378 |
| `30_simulation/` | 5,035 | 0.482 |
| `40_evidence/` | 226 | 0.880 |
| `50_literature/` | 89 | 0.500 |
| `70_tools/` | 7,662 | 1.540 |
| `80_third_party/` | 20,310 | 5.184 |
| 根 `.git/` | 26,849 | 13.870 |

根 `.git/lfs` 占约 **10.88 GB**，普通对象目录约 **2.98 GB**。运行时名称候选约 2.01 GB；压缩档候选约 2.21 GB；缓存/临时目录名称候选约 46 MB。这些名称类别存在交叠，不能相加或据名字认定无价值。

工作树有 **73** 个文件超过 50 MiB、**51** 个超过 100 MiB，见 [LARGE_FILES.csv](LARGE_FILES.csv)。其中很多 CAD 在 Git 中已是 LFS 指针，不能把这 51 个全部当作普通 Git 推送失败。

真正的当前 index 普通大 blob，以及 `--all` 可达历史大 blob，各有以下两项：

| 路径 | 普通 Git blob 大小 | 处理优先级 |
|---|---:|---|
| `70_tools/runtime_wp09_kicad/kicad-10.0.6-x86_64.exe` | **922.933 MiB**（967,765,696 B） | **P0：GitHub 常规推送硬阻断**；它是安装器，不应成为研究源码交付的必需部分 |
| `01_project/governance/sei_pl1_cleanup_20260828/_ref_matches.tsv` | 89.862 MiB | P1：超出建议警告线，先查是否为保留证据/索引，再决定 Release 附件或只保留生成器与摘要 |

GitHub 当前对大于 50 MiB 的普通文件警告，大于 100 MiB 阻断；官方建议仓库理想小于 1 GB、强烈建议小于 5 GB。来源：[GitHub 大文件说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)。

922.933 MiB 安装器已经在历史中，**追加 `.gitignore` 或在下一提交删去安装器，不能消除旧可达 blob**。建议新建经过筛选的公开发布快照仓库，保持现有研究仓库和完整历史本地留档；公开包保留原 HEAD、来源文件哈希和负结果索引。若一定要保留完整提交谱系，应先单独备份并在隔离副本制定历史迁移方案，不能直接重写本研究仓库。本轮没有执行任何历史迁移。

历史扫描范围是本地所有可达 refs，共 35,469 对象、30,642 唯一 blob、逻辑总量约 5.18 GB；不包括 reflog/不可达对象，也不是网络压缩传输体积。详情见 [TRACKED_LARGE_BLOBS.csv](TRACKED_LARGE_BLOBS.csv)、[HISTORY_LARGE_BLOBS.csv](HISTORY_LARGE_BLOBS.csv)。

## 3. LFS 已有基础，但尚未形成公开发布闭环

| 检查 | 结果 |
|---|---:|
| 当前属性 `filter=lfs` 的 tracked 路径 | 8,152 |
| index 中确实为 LFS 指针的路径 | 8,111 |
| 去重后的指针 blob | 4,842 |
| 指针对应本地 LFS 对象缺失路径 | 0 |
| LFS 指针但属性不匹配 | 0 |
| 匹配 LFS 属性却仍为普通 Git blob | 41 |

41 项见 [LFS_ATTRIBUTE_MISMATCH.csv](LFS_ATTRIBUTE_MISMATCH.csv)，主要是早期 FreeCAD/CAD 原始 blob；其中两项为历史失败记录中的零字节 SLDASM。它们不是本轮发现的超 100 MiB 阻断，不应自动“修复”为成功 CAD 或删除失败证据。按发布范围区分后再规范 LFS 入库。

LFS 指针所代表的路径合计逻辑体积约 **16.62 GB**，其中有相同对象的重复路径；这不等于新增上传量或实际计费量。本地对象存在也不代表已上传到新公开远端。公开后必须用全新 clone + LFS 拉取核验，防止只有文本指针却无模型。

LFS 单文件上限与套餐有关，GitHub Free/Pro 当前为 2 GB，Team 4 GB，Enterprise Cloud 5 GB；规则和归档行为见 [GitHub LFS 文档](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage)。本审计未假定用户套餐、预算或 LFS 远端可用性。

`.gitignore` 中 `*.pdf` 不会自动取消历史跟踪：本仓仍有 **1 个 tracked PDF 命中 ignore 规则**。因此不能把“有 ignore 规则”当作许可/隐私放行证据。

## 4. 重现入口和可移植性缺口

1. **根 README、LICENSE、CITATION、统一环境锁和根 CI 均不存在。** 现有 `PROJECT_MAP.md` 有用，但日期为 2026-09-06，入口仍以 WP03 为主，未完整表达 R6H/R7 与研究复现关系。公开首页需要当前对象/版本、范围、已验证结论与未完成项、三条最短命令、硬件/仿真依赖以及引用方式。
2. **安装环境不是一份研究复现锁。** `70_tools/research_env/README.md` 主要描述本机 MCP/技能与安装路径。排除 vendor/runtime 后，本次只定位一份标准命名依赖清单：`30_simulation/r2_mujoco_free_floating_precontact_v1/00_authority/requirements-mujoco-v1.txt`；它只锁该 MuJoCo 支路的四项依赖，不能覆盖 OCP、SolidWorks COM、KiCad 和所有历史仿真。
3. **绝对路径广泛存在。** 有 5,090 个受检文本文件匹配 F:/G: 路径，见 [ABSOLUTE_FG_PATH_REFERENCES.csv](ABSOLUTE_FG_PATH_REFERENCES.csv)。这是导航、历史回执、JSON 输入和可执行脚本的混合统计；不意味着 5,090 个都执行失败。应优先改活跃入口的路径解析和派生发布副本，保留冻结回执原始字节，并以映射文件关联。
4. **R6H 原生 CAD 明确不是可迁移交付包。** `results/FINAL_DELIVERY_STATUS.json` 声明 `portable_package=false`，790 原生文件锁依赖跨 R1/R4 等包；当前 README 明确未作 Pack and Go。单独上传 `SERVICE_STAR_SERVICE_R6H.SLDASM` 不会自动带齐零件。应生成单独发布副本，依照 `SOURCE_DEPENDENCIES_SHA256.csv` 收集引用、Pack and Go/相对路径重链接，并在另一根目录冷打开验证 15 组、1153 叶、1602 实体。保留原冻结包，不改其证据哈希。
5. **CAD 与科学模型不能默认共享质量真值。** 发布入口应把 R6H 静态装配候选、旧 R2/七模态模型、当前质量/BOM与动力学接口分别定位，不能因为 CAD 打开成功就称模型已迁移认证。
6. **本机浏览器 URL 不能充当公开演示链接。** `http://127.0.0.1:8768/...` 仅本机可用；可交付自包含 HTML/PNG 和运行说明。含本机绝对引用或外链依赖的页面须另验；本轮没有发布 GitHub Pages。
7. **未进行全新机器复现。** 当前审计没有全模块测试、没有新目录 clone/LFS 实验，也没有原生 CAD 异机重链接试验，不能据本机历史 PASS 宣称开箱即复现。

建议三层验证：A) 无商业 CAD 的配置/哈希/小型数值 smoke tests；B) 具名冻结科学场景及其原 Gate/负控回放；C) 有授权 SolidWorks/OCP/KiCad 环境中的模型重建/冷打开。CI 先覆盖 A，B 按耗时人工/计划运行，C 声明 Windows、软件版本、许可证和人工复核要求。不要将全部历史脚本无差别串联执行，以免覆写冻结结果。

## 5. 建议公开资产分层

| 层 | 建议内容 | 验收条件 |
|---|---|---|
| 公开源码 Git 仓库 | 自有代码、配置合同、BOM/接口表、必要证据 JSON/小 CSV、具名负结果、阅读卡与题录、许可/引用/导航 | 来源与许可已核验；无密钥和私人往来；可读 README；当前输入输出关系清楚 |
| LFS | 确有协作修订需要的当前原生 CAD/STEP/必要网格和不可小型化数据 | 指针/属性一致；独立 clone 可获取；上游再分发许可明确；配额确认 |
| 版本 Release | 自包含 CAD Pack and Go、当前中性 STEP、查看器、固定版证据附件和 SHA256 清单 | 版本、范围、构建环境和 `whole_design_complete=false` 等限制随包；不要重复附整套 `.git` |
| 外部来源登记 | 论文 DOI/来源 URL、第三方仓库 commit、厂家数据页与下载校验 | 默认提供来源而非把全部 PDF/厂商模型打入仓库；可再分发的例外逐项登记 |
| 本机完整留档 | 原研究 Git、SQLite 目录/恢复快照、安装器、缓存、私人输入、原始全部文献与未核权来源 | 保留可恢复性；公开排除不等于本机删除；原失败证据不能消失 |

明确的**公开包候选排除**，均不构成本机删除授权：

- 根 `.git/`、第三方树内的 `.git/`、`.claude/`/`.codex/` 中用户环境配置，以及 `.mcp.json.retired-20260911-superseded-by-user-scope` 的本机配置正文；公开仅留经过审查的示例配置。
- `70_tools/runtime_wp09_kicad/kicad-10.0.6-x86_64.exe`、`70_tools/runtime_wp09_kicad/portable/`，以及实现目录 `tools/cadgen_v30/cadgen/_runtime/`；以官方安装说明、版本和校验替代。若改作再分发，先单独核验许可及必要性。
- `01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/loop0_20260905/screening/full_project_catalog.sqlite`（739.105 MiB）等恢复/全路径索引，先留本机；公开用经审核的来源/变更摘要。
- `.pytest_cache/`、`__pycache__/`、`_generated_com/`、`viewer_http*.log` 和真正可再生临时构建产物；**命中 `.tmp*` 或 `_work` 只触发人工分类，不能一概排除，因为其中有有效合同、失败证据和已冻结 Gate**。
- `50_literature/pdf/`、`80_third_party/vendor/`、`80_third_party/external/spacecraft_layout_refs/` 整树默认不进源码仓库；按精确许可逐件选择，保留题录/源码 commit/获取方法。
- `01_project/inbox/source_documents/` 与协作者输入、联系人或聊天导出默认待公开审查；范围确认后再公开去敏派生件。
- 重复的大 STEP 展示副本、旧完整 ZIP 不直接悉数入库；保留源哈希和明确谱系，按复现必要性选择当前 Release 与必要历史反例。

## 6. 发布前最短闭环

| 次序 | 必做工作 | 完成证据 |
|---|---|---|
| P0-1 | 选定公开快照范围并保留私有完整源历史；阻止普通 922.933 MiB 安装器进入推送历史 | 公共发布清单 + 大 blob 复检无阻断 |
| P0-2 | 逐项许可、隐私/秘密、提交历史检查；建立自有/第三方边界 | 文件级处置表 + LICENSE/NOTICE 等批准的公开声明 |
| P0-3 | 把已授权的 R1–R6H/R7 等未跟踪包纳入选定清单，核验依赖，不把撤回 R6 当现行 | 当前指针 + 源哈希 + 未跟踪处置表 |
| P0-4 | CAD 可迁移包和环境入口 | 独立目录冷打开报告；最小命令和依赖锁 |
| P1-1 | 当前 README、CITATION、研究/工程范围表和已知限制 | 首页每个主要结论都有原 Gate/适用构型链接 |
| P1-2 | 新目录 clone/LFS 拉取 + smoke tests + 具名数值复现 | 可复现报告与资源开销，确认原 Gate 不被改写 |
| P1-3 | Release 附件/查看器/校验清单 | 外部下载后的 SHA256 验证与链接检查 |
| 发布动作 | 在上述公开清单可审阅后创建仓库/推送并核验 | 本轮未执行；不要把审计结论等同发布完成 |

本分项结论是公开交付准备度判断，不替代机械、电气、热、推进或科学 Gate。
