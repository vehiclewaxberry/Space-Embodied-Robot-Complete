# Canonical 阅读卡规范

阅读卡路径必须为 `50_literature/references/notes/{bibkey}.md`，其中 bibkey 与 manifest 逐字一致。阅读卡是全文精读记录，不是第二份题录库。

## 必需结构

```markdown
# {bibkey} — {title}
- DOI/arXiv：... ｜ 类别：... ｜ 等级：... ｜ 读法：...
- 本地：50_literature/pdf/.../{bibkey}.pdf（N 页）

## 一句话结论
限定对象、方法和证据范围的一句话。

## 与本项目的挂钩
| 本项目对象 | 关系 |
|---|---|
| ... | 文献能提供什么，以及不能替代什么。 |

## 可复用内容（改写，附页码指针，禁止抄录）
- 方程/推导：页码、章节、公式号及受限解释。
- 参数/阈值：原文对象、工况、数值和不可直接迁移边界。
- 图表：图号/表号、可复用信息及版权友好的重绘方式。

## 边界与不适用条件
模型假设、数据范围、验证层级、域差与未覆盖问题。

## 不能据此声称什么
列出最容易被过度外推的表述。
```

## 内容规则

- 每条技术性事实给出页码、章节、公式号、图号或表号中的至少一种。
- 明确区分 `AUTHOR_CLAIM`、`MEASURED_RESULT`、`SIMULATION_RESULT`、`REVIEW_SUMMARY` 和 `ORCHESTRATOR_INFERENCE`。
- 摘要只能支持摘要明确写出的范围；正文方法、参数和限制必须回到对应页面。
- 扫描/OCR 内容标记 `OCR_CHECKED`，并人工核对关键公式、符号和小数点。
- 二手综述用于导航；需要精确阈值或推导时追到原始来源。
- 不复制长段原文。使用受限改写并保留定位符。

## 完成级别

- `CATALOG_ONLY`：只有题录，不能引用正文细节。
- `PDF_READY_FOR_READING`：PDF 在盘且存在，但尚无完整卡。
- `READING_CARD_DRAFT`：已读部分正文，定位或边界未闭环。
- `READING_CARD_COMPLETE`：五个必需章节齐全，并有页级定位。
- `CLAIM_BOUND`：具体主张已在 claim-evidence 账本登记并通过强度审核。

只有 `READING_CARD_COMPLETE` 及以上状态可直接进入正式综合；仍须按具体主张复核定位符。
