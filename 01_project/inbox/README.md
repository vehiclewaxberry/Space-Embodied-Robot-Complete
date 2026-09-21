# 受控资料收件箱

本目录保存用户、协作者或外部渠道提供、但尚未转化为项目正式 SSOT 的原始资料。

规则：

1. 原始字节不得改写；通过 `source_manifest.csv` 记录来源、SHA-256 和处理状态。
2. 从收件箱提取出的正式结论必须进入对应 `10_research/`、`01_project/competition/` 或 `20_engineering/config/` 路径。
3. 原始文件进入正式归档后，收件箱仅保留一个 canonical 原件，不建立平行副本。
4. 被历史 Gate/合同直接绑定的资料可以暂留根目录，并在 manifest 中标记 `PATH_LOCKED`。

## 根目录治理

- 仓库根目录禁止新增一般性 DOCX、PDF、图片、压缩包或临时说明文档。
- 新收到的外部资料先进入本目录，并在 `source_manifest.csv` 登记来源、SHA-256 与处理状态。
- 已经被合同、Gate 或冻结指纹绑定的历史输入保留原位，直到对应绑定通过正式治理记录解除；不得仅为目录美观而移动。
- 当前根目录 `01_project/inbox/source_documents/空间机械臂.docx` 属于上述 `PATH_LOCKED` 例外，本规则不授权移动、改写或复制它。

当前清单见 [`source_manifest.csv`](./source_manifest.csv)。
