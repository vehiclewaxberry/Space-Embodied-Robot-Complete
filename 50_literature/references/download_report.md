# LIT-01 下载、裁决与可读化执行报告

> **历史快照说明**：本文件保留 LIT-01 当日下载来源与仓库落盘证据；当前 44 份统一路径、手工补充与最终验收以 [REORG-01-R 报告](./reorg01r_report.md) 和 [landing_check.md](./landing_check.md) 为准。

生成日期：2026-07-21

上游基线：`aaa78b151fe8879fbc3ad0748830b3d3a0306edb`（LIT-00）

裁决：`LIT01_BLOCKED_BY_CATEGORY_COVERAGE`

## 1. 结果摘要

| 项目 | 数量 | 结论 |
|---|---:|---|
| LIT-00 既有 PDF 落地核验 | 15 | 15 个 `ON_DISK_HASH_MATCH`，0 个 mismatch，0 个 missing |
| 本次合法新增 PDF | 8 | 签名、页数、标识与 SHA-256 均通过；未覆盖既有文件 |
| 当前在盘可读 PDF | 23 | 每份均已生成阅读卡 |
| 当前付费墙/策略阻断 | 11 | 不绕过访问控制，进入 `paywalled_todo.md` |
| DOI 已核验 | 24 / 27 | 22 个 `VERIFIED`，2 个 `VERIFIED_AFTER_ADJUDICATION` |
| DOI mismatch | 0 | LIT-00 的 4 个 mismatch 已全部裁决 |
| Crossref 未收录、官网核验 | 3 | `hu2025ultralarge`、`ding2025spacerobotops`、`liu2021spacemanipulator` |
| 仓库落地核验 | 10 | 9 个 `80_third_party/vendor/` 仓库与 1 个 SpaceRobotEnv 均匹配 pinned SHA |

PDF、第三方仓库和数据集继续不进入 Git。上游 15 次成功下载、10 次仓库克隆和 20 条已验证 DOI 均未重跑。

## 2. 目标盘落地核实

- 当前工作目录与 Git 顶层目录均为 `F:\China Graduate Future Flight Vehicle Innovation Competition`。
- 当前 HEAD 为 LIT-00 基线提交 `aaa78b151fe8879fbc3ad0748830b3d3a0306edb`（执行增量前核验）。
- `50_literature/pdf/`、`80_third_party/vendor/`、`80_third_party/external/spacecraft_layout_refs/spacerobotenv/SpaceRobotEnv` 均在目标 Windows 工作盘。
- 15 个既有 PDF：文件存在 15/15、SHA-256 匹配 15/15、缺失 0、哈希不符 0。
- 9 个 `80_third_party/vendor/` 仓库及 SpaceRobotEnv：目录存在且 HEAD 均等于 manifest 的 `pinned_sha`。
- 三态逐文件与仓库逐项证据见 `landing_check.md`。

## 3. DOI 裁决

| key | 结果 | 证据与落库动作 |
|---|---|---|
| `yoshida2001zrm` | `10.1109/ROBOT.2001.932590` | Crossref 题名为目标 ZRM 论文；状态改为 `VERIFIED_AFTER_ADJUDICATION`；旧 DOI `...932589` 记为 `superseded_doi`。 |
| `xu2017reactiontorque` | `10.1016/j.cja.2017.02.021` | 按指定 Crossref 题名查询，第一名题名归一化相似度 `1.000000`（阈值 0.90）；旧 DOI `...03.010` 记为 `superseded_doi`，PII `S1000936117300869`。 |
| `ma2025latticemeta` | DOI 不变 | 种子题名截短是假阳性；改录 Crossref 完整题名，状态 `VERIFIED`，`title_note: seed_title_truncated`。 |
| `sscae2024strategy` | DOI 不变 | 中文题名与 Crossref 英文题名为同一 DOI 的双语记录；状态 `VERIFIED`，`title_note: bilingual_record`。 |

裁决后：`primary_doi_verified: 24`，`primary_doi_mismatch: 0`，`primary_doi_crossref_not_found: 3`。

## 4. PDF 清单

`PASS` 表示 `%PDF-` 签名存在、页数大于 0、首页题名/DOI/arXiv 标识可核、SHA-256 已记录。`liu2021spacemanipulator` 的内嵌字体导致文本层乱码，已改用期刊 RichHTML 与 PDF 页图交叉核验，未把乱码当作正文证据。

### 4.1 LIT-00 既有 15 份（只读复核）

| key | 本地路径 | 字节 | 页数 | SHA-256 | 状态 |
|---|---|---:|---:|---|---|
| `papadopoulos2021survey` | `50_literature/pdf/01_survey/papadopoulos2021survey.pdf` | 3,545,537 | 36 | `85e2a7bb0d217132a6daac7c0a5da7c8d4027b73a1de9a56340685fdc94f8d91` | PASS |
| `alizadeh2024comprehensive` | `50_literature/pdf/01_survey/alizadeh2024comprehensive.pdf` | 84,515,215 | 34 | `176c85af31115383f3e9b8a3a37699c45eb59ed74a40ae2d61f0b5b62a0eac7f` | PASS |
| `zhang2022adcr` | `50_literature/pdf/01_survey/zhang2022adcr.pdf` | 4,656,919 | 27 | `bf55fadf562ae224721cb0fcb548187450cd8bea99f7a0eee981427d27b44d88` | PASS |
| `ellery2019tutorial` | `50_literature/pdf/01_survey/ellery2019tutorial.pdf` | 1,465,511 | 56 | `e08a68903de91f740a67547ec6278c0a8ab75191b73720cc6e2b894c7037f16d` | PASS |
| `wilde2018tutorial` | `50_literature/pdf/02_gjm_rns/wilde2018tutorial.pdf` | 4,279,702 | 24 | `8d7d36f825f40e9be87d668dcd1cd363a92de4400766f9bfbc95119af3d205a6` | PASS |
| `tayebi2025vibrationeditorial` | `50_literature/pdf/04_flexible_ancf/tayebi2025vibrationeditorial.pdf` | 6,372,256 | 3 | `b899622796088bab9547e0cedd1c55103c8881e14d40a07e279ff03648d35cd8` | PASS |
| `spacemind2026` | `50_literature/pdf/05_embodied_vla/spacemind2026.pdf` | 2,437,679 | 23 | `2e1a65354f41952509eca939edfa5c1c5b04728c5dae375d16d65f989433559f` | PASS |
| `ma2024vlasurvey` | `50_literature/pdf/05_embodied_vla/ma2024vlasurvey.pdf` | 4,047,091 | 54 | `8f8419e0ec4e0dae9a8ec649db463159cb628359194c6a09223f31e873d35a00` | PASS |
| `kim2024openvla` | `50_literature/pdf/05_embodied_vla/kim2024openvla.pdf` | 13,240,309 | 37 | `353c37df34458f12f969b14dfd8b77175b727b9cddea7bb891759beddeefe1be` | PASS |
| `rodriguez2024lmspacecraft` | `50_literature/pdf/05_embodied_vla/rodriguez2024lmspacecraft.pdf` | 9,143,024 | 13 | `5c4f1fbf7b72a129d51cddc2c22331a04992906b714b1ae4f2bd15beb092fc1e` | PASS |
| `park2021speedplus` | `50_literature/pdf/05_embodied_vla/park2021speedplus.pdf` | 23,508,622 | 15 | `aaa88692a0be8d4b2d1be21c296b63342ae4235e603863e2776dfdafe75fbd6f` | PASS |
| `orsula2025srb` | `50_literature/pdf/05_embodied_vla/orsula2025srb.pdf` | 13,786,340 | 13 | `08ce86c86ff41b2986198e41fb7d14da08e38a7cb0122155e8756b1506fe97a6` | PASS |
| `visualservoing2024survey` | `50_literature/pdf/05_embodied_vla/visualservoing2024survey.pdf` | 2,136,604 | 8 | `a334394e847326bcbbe60e91b82b99e19b1fb63cf44d002ecac3584ee53c0461` | PASS |
| `alali2024hiltestbed` | `50_literature/pdf/07_platform/alali2024hiltestbed.pdf` | 25,675,219 | 20 | `4604f10019640e5ead797b55d64235d83589e0540d5cea671881098cf1af1435` | PASS |
| `sscae2024strategy` | `50_literature/pdf/08_chinese/sscae2024strategy.pdf` | 5,316,116 | 11 | `83981279757fbbd1d71abe5a88f50ddc44e5cd0170bf7b8a3d432424b62f2f28` | PASS |

### 4.2 LIT-01 合法新增 8 份

| key | 合法来源 | 本地路径 | 字节 | 页数 | SHA-256 | 状态 |
|---|---|---|---:|---:|---|---|
| `hu2025ultralarge` | 《力学进展》官网 | `50_literature/pdf/06_on_orbit_assembly/hu2025ultralarge.pdf` | 14,351,248 | 30 | `11f7199fc1fc8b380592fd019d80bb2f52e147de87b9718737e2b9fe1fd9a217` | PASS |
| `li2022assemblysurvey` | SciOpen 授权平台 | `50_literature/pdf/06_on_orbit_assembly/li2022assemblysurvey.pdf` | 2,099,990 | 13 | `8cf93e6c1bea5fd654de34e28aa18bf15bf9d9dcabcbc29f57595759e974087c` | PASS |
| `sst2024autonomous` | SciOpen 授权平台 | `50_literature/pdf/01_survey/sst2024autonomous.pdf` | 7,286,590 | 23 | `df14530433630446d54a365841c9bba739deb05bd63a8d8dffeac4dd530e00be` | PASS |
| `kawaharazuka2025vlareview` | arXiv `2510.07077` | `50_literature/pdf/05_embodied_vla/kawaharazuka2025vlareview.pdf` | 7,705,369 | 38 | `35b9fad5b156b6ac70d6abc3b8083ca35cd66bdaa96728cc5d6769d86ceb9784` | PASS |
| `ma2025latticemeta` | PMC OA，`PMC11848643` | `50_literature/pdf/04_flexible_ancf/ma2025latticemeta.pdf` | 30,738,983 | 65 | `bd315c414f9219521344757400596f6beda8cfd28108310197565d7b9d9e4932` | PASS |
| `ding2025spacerobotops` | 《航空学报》官网 | `50_literature/pdf/08_chinese/ding2025spacerobotops.pdf` | 2,342,158 | 29 | `d9049425a2c0aeff397ccbae093999a470ca5b529efdc55ecf11b0ed4957d223` | PASS |
| `liu2021spacemanipulator` | 《航空学报》官网 | `50_literature/pdf/08_chinese/liu2021spacemanipulator.pdf` | 9,557,808 | 14 | `adac6672f5a3e0065bb520033c59189620f2987f9a9fbb2a440cd96e0ff9e567` | PASS* |
| `yoshida2001zrm` | 作者本人主页 | `50_literature/pdf/02_gjm_rns/yoshida2001zrm.pdf` | 1,210,366 | 6 | `8bf22a1088ddeafc35941cbd3765fe9bd4f97ceaeb916b6d5482dd051854c3e8` | PASS |

新增来源分布：期刊官网 3、SciOpen 2、作者主页 1、PMC 1、arXiv 1。

## 5. 开放版本复核

### 5.1 arXiv

- 对 LIT-00 的全部 14 条 `PAYWALLED_TODO` 逐条发起指定的 arXiv 官方 API 题名查询。
- `export.arxiv.org` 本次连续超时；未把超时伪装成“无结果”。随后以 `arxiv.org` 官方域名精确题名检索降级复核。
- 确认命中 1 条：`kawaharazuka2025vlareview` → arXiv `2510.07077`，已下载并标 `version_used: arxiv_preprint`。
- 其余 13 条未找到可确认的 arXiv 版本。

### 5.2 Europe PMC / PMC

- 对 14 条逐条按 DOI 或完整题名查询 Europe PMC。
- `ma2025latticemeta` 命中 PMID `39834122` / PMCID `PMC11848643`，全文为 CC BY 4.0，已从 PMC Open Access AWS 分发下载。
- `gerstmayr2023exudyn` 仅命中一个非开放、未进入 PMC 的 Research Square 记录，未下载。
- 其他条目没有可用 PMCID 全文。

## 6. 当前 11 条未下载状态

活动清单、阻塞度顺序、机构字段与人工回填规则见 `paywalled_todo.md`。当前状态仅有两类：

- `OPEN_ACCESS_DOWNLOADED`: 23
- `PAYWALLED_TODO`: 11

`FAILED_AFTER_RETRY` 与 `POLICY_SKIPPED_NOT_ON_DOWNLOAD_ALLOWLIST` 均已归零。

## 7. 仓库落地复核

本任务没有重新克隆、拉取、安装或运行第三方仓库。

| 仓库 | 本地路径 | pinned SHA | 落地状态 |
|---|---|---|---|
| SPART | `80_third_party/vendor/SPART` | `1365c7e6f345255a700936511b8abfd58d179016` | MATCH |
| SpaceDyn | `80_third_party/vendor/SpaceDyn` | `57e5d608cb959338b1bcec6bc34249d959815036` | MATCH |
| SpaceRobotEnv | `80_third_party/external/spacecraft_layout_refs/spacerobotenv/SpaceRobotEnv` | `155989c2ae94a3afeedf9b8601b6125d83b9c097` | MATCH |
| space_robotics_bench | `80_third_party/vendor/space_robotics_bench` | `7528ff81f1ac0b34ba259b1ae150fdb4f6a90b5e` | MATCH |
| EXUDYN | `80_third_party/vendor/EXUDYN` | `b428cda78ef745e2092e7d202e72d84881bf4667` | MATCH |
| basilisk | `80_third_party/vendor/basilisk` | `6b9c222fc9ea8d4b478c26435b16ff71910e80e8` | MATCH |
| astrobee | `80_third_party/vendor/astrobee` | `bf43a42d5f89bf0679e51ab25e7a9b7800313e9c` | MATCH |
| chrono | `80_third_party/vendor/chrono` | `24c78cf889de1105be3742cec9586f662cc52b05` | MATCH |
| openvla | `80_third_party/vendor/openvla` | `c8f03f48af692657d3060c19588038c7220e9af9` | MATCH |
| openpi | `80_third_party/vendor/openpi` | `15a9616a00943ada6c20a0f158e3adb39df2ccac` | MATCH |

## 8. 可读化产物

- 为 23 份在盘 PDF 生成 `notes/{key}.md`，均含结论、项目挂钩、页码指针、边界和禁用声明。
- 生成 `notes/INDEX.md`，按 V0–V4 和 SIM/CTRL/ASM 逻辑对象交叉索引。
- `CTRL01`、`CTRL02`、`ASM00` 是本次文献交叉索引使用的逻辑工作流标签，不声明仓库内已有同名代码模块。
- 所有笔记均为改写，没有整段复制原文。

## 9. 机器检查

| 检查 | 结果 |
|---|---|
| manifest YAML 可解析，34 篇论文/10 仓库/2 数据集 | PASS |
| 23 个 `local_pdf` 文件存在、SHA-256 与 manifest 一致 | PASS |
| 23 个 PDF 签名与页数有效 | PASS |
| 23 张阅读卡与 manifest 的在盘 key 一一对应 | PASS |
| 10 个仓库 HEAD 等于 pinned SHA | PASS |
| 受保护目录与用户未跟踪产物未修改 | PASS |
| PDF、第三方仓库、数据集未加入 Git | PASS |

## 10. 声明边界

- 未使用 Sci-Hub、LibGen、Z-Library 或其他未授权镜像。
- 未绕过登录、机构订阅、验证码、付费墙或反爬访问控制。
- SciOpen、PMC、作者主页与期刊官网均属于任务明确授权的合法来源。
- arXiv 阅读卡明确标注预印本差异；正式引用页码仍应以版本记录为准。
- 文献“在盘”不等于本项目已完成相应算法、硬件或飞行验证。

## 11. 类别覆盖（G-LIT-COV）

口径：仅统计每个 category 的 P0 条目；`on-disk` 要求 manifest 有 `local_pdf` 且文件通过可读性核验。关键三类低于 60% 为 `BLOCKED_BY_CATEGORY_COVERAGE`；其他类别低于 40% 为 `WARN`。

| category | P0 总数 | P0 在盘 | 可读率 | 门禁 |
|---|---:|---:|---:|---|
| `survey` | 2 | 1 | 50.0% | PASS |
| `gjm_rns` | 3 | 2 | 66.7% | PASS |
| `contact_capture` | 1 | 0 | 0.0% | **BLOCKED_BY_CATEGORY_COVERAGE** |
| `flexible_ancf` | 3 | 1 | 33.3% | **BLOCKED_BY_CATEGORY_COVERAGE** |
| `embodied_vla` | 4 | 4 | 100.0% | PASS |
| `on_orbit_assembly` | 2 | 2 | 100.0% | PASS |
| `platform` | 0 | 0 | N/A | NOT_APPLICABLE |
| `chinese` | 2 | 2 | 100.0% | PASS |

关键三类：`gjm_rns = 2/3 = 66.7%`，`contact_capture = 0/1 = 0.0%`，`flexible_ancf = 1/3 = 33.3%`。因此总裁决为 `LIT01_BLOCKED_BY_CATEGORY_COVERAGE`；具体阻塞来自 contact_capture 与 flexible_ancf，而不是总下载数量。
