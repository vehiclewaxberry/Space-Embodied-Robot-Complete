# 公开发布的许可与隐私审计

日期：2026-09-21。本报告只做本机限定范围检查，不上传内容、不验证密钥可用性、不撤销凭据、不改写源文件或 Git 历史。结论：公开发布仍有未处理项；没有把“未检出”作为公开许可。

## 1. 必须先处置的凭据记录

已跟踪文件 `20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp7_fea_operational/jobs/fea1_capture_150kg_qs_coarse.env` 的第44、141行各含一个密钥格式值，分别赋给认证令牌与 API key 环境项。

两处值都存在于当前工作树、HEAD 和该路径的一份可达历史版本中；不是仅未跟踪缓存中的记录。提供者、归属和当前有效性没有测试，不能据格式断言是 OpenAI 的密钥。原始值没有写入本报告、扫描回执或聊天。

处置顺序：由持有者确认凭据身份；确为真实凭据时先撤销/轮换；从拟公开文件与拟推送历史中排除或安全替换；对选定发布树和历史重新扫描。不能仅添加 ignore 或在新提交中删去该文件便认为历史已净化。GitHub 对真实秘密的处置建议同样以先撤销/轮换为起点：[官方说明](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)。

没有证据证明这些内容已经泄漏到远端；当前仓库没有配置 remote，本轮也没有发送它们。机器证据是 [SECRET_FINDINGS_REDACTED.json](SECRET_FINDINGS_REDACTED.json)。

## 2. 扫描覆盖边界

[PRIVACY_PRESCAN.json](PRIVACY_PRESCAN.json) 对当前工作树25,580个文本文件、680,336,732字节作模式预检，命中上述两处。扫描跳过二进制、PDF/Office、压缩包、若干运行时/第三方库目录、179个超过2 MiB的文本，以及17处访问错误。Git历史只对上述已知命中路径做了复核，未对全部历史内容作秘密扫描。

因此仍需要在**选定的公开发布副本**运行专用秘密扫描、全历史检查、Office/PDF元数据及压缩附件检查；必要时人工复核。不要对外称本次预检已经完成安全认证。

已识别的其他公开审查对象：

- 已跟踪的 `.mcp.json.retired-20260911-superseded-by-user-scope`：本机配置，宜在公开副本以无凭据示例替代。
- `.claude/settings.local.json`：本机配置，不是研究复现依赖锁。
- `AGENTS.md`、`CLAUDE.md` 和协作问题文档：含个人协作背景与沟通渠道，先做公开适用性和协作者知情审查。
- `01_project/inbox/source_documents/`、全项目 SQLite 索引、环境转储和日志：默认留本机，选择经过审阅的研究派生内容公开。目录被列出不表示每个文件都有秘密。

公开裁剪不构成本机删除授权，尤其不能按 `_work`、`.tmp`、`archive` 名称删除有效负结果或恢复证据。

## 3. 已实际查到的许可差异

| 本地来源 | 查到的许可/声明 | 本次判断 |
|---|---|---|
| `80_third_party/vendor/reBot-DevArm/LICENSE` | CERN-OHL-W-2.0文本 | B601相关仓库不能直接被自有项目的MIT声明覆盖；逐件确认派生设计与随行来源义务 |
| `80_third_party/external/spacecraft_layout_refs/birds/BIRDSX-CAD/LICENSE` | MIT，BIRDS Project署名 | 选用文件须保留适用版权/许可，核对具体资产范围 |
| `80_third_party/external/spacecraft_layout_refs/librecube/LC2102/LICENSE.txt` | CERN-OHL-W-2.0文本 | 与软件MIT不同；按选定设计文件与实际派生关系核对 |
| WP09 `reuse_closure/sources/motorbridge/LICENSE` | MIT | 许可文本应随选定副本；不自动覆盖旁边所有硬件或厂家来源 |
| WP09 `reuse_closure/sources/oresat-kicad/LICENSE_FETCH.json` | 记录上游README声明CERN-OHL-S-v2-or-later及标准文本下载 | 仅是来源记录，仍要绑定实际使用版本、文件和变更 |
| 论文全文、OEM PDF/CAD、KiCad模型、SolidWorks材料库 | 尚无覆盖选定公开包的逐文件授权清单 | 默认提供引用、上游URL/commit、获取方法和校验；有明确再分发权再纳入附件 |

以上是本地许可识别，不是全部资产兼容性或权属结论。不得在未核对范围时给整个50 GB工作区统一加一份MIT许可证。根目录当前没有项目LICENSE；公开与开源授权也不是同一件事，见 [GitHub许可说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)。

`50_literature/references/manifest.yaml` 已规定 PDF、模型权重、数据集和第三方仓库不提交 Git。现有 `.gitignore` 的 `*.pdf` 仍未覆盖已经跟踪的一个PDF，不能用ignore规则替代文件级许可判断。下载允许清单不等于再分发许可清单。

建议建立 `THIRD_PARTY_NOTICES` 和逐文件来源表：来源URL、版本/commit、原始哈希、许可证、修改说明、再分发结论、公开处置。自有代码、硬件设计、文档与数据的许可证分别确认，未决定前保留“待决定”，不由本审计代签授权。

## 4. 公开资产建议

自有代码、参数合同、BOM/接口摘要、必要Gate及负结果可先形成受控清单；大CAD与数据在许可允许时放LFS/Release；论文优先给题录/DOI与合法获取入口；安装器、商业运行库、完整第三方镜像、本机密钥/配置和私人往来留本机。对外公开的清单、链接和附件还须单独验证，原始研究证据保持原字节。
