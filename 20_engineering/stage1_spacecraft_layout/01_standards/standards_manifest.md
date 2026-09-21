# Stage 1-B+ 标准 PDF 实读清单

## 1. 本轮读取结论

三份 PDF 均已在本地目录中找到，SHA256 与任务给定值一致。文本层可由 `pypdf` 读取；其中 NASA Small Spacecraft Technology SOA 2026 在解析时出现若干 `Ignoring wrong pointing object` 警告，但页数和正文文本仍可读取，因此记为 `read_ok_with_nonfatal_warnings`。

CDS Rev.14.1 的 Appendix B 图纸页在 PDF 文本层仅能抽取页眉，图纸内部尺寸未能作为文本抽取。因此，Appendix B 中 1U/3U/6U/12U 具体图纸尺寸细项不在本轮强行提取，标记为 `drawing_text_parse_failed`，需后续人工目视/矢量图纸复核。

## 2. Manifest

| file_name | local_path | size_bytes | sha256 | status | extraction_status | notes |
|---|---:|---:|---|---|---|---|
| `CubeSat_Design_Specification_Rev14_1_2022-02-09.pdf` | `20_engineering/stage1_spacecraft_layout/01_standards/CubeSat_Design_Specification_Rev14_1_2022-02-09.pdf` | 8001529 | `221FBBBD4F632B16F3E219D1A5E2C2B04E1998C12025B793E6DFC6181AF66B5D` | present_hash_match | extracted_partial | 正文条款、Table 1/2、部署器章节可解析；Appendix B 图纸尺寸文本解析失败。 |
| `NASA_CubeSat_101_Basic_Concepts_First_Time_Developers.pdf` | `20_engineering/stage1_spacecraft_layout/01_standards/NASA_CubeSat_101_Basic_Concepts_First_Time_Developers.pdf` | 4445718 | `57D2783457CB94B69136476CA341DDF4C7DC23BF61682606E37A048E9E5AE592` | present_hash_match | extracted | 系统工程流程、飞行认证文档、质量属性、尺寸验证、测试和附录模板可解析。 |
| `NASA_Small_Spacecraft_Technology_SOA_2026.pdf` | `20_engineering/stage1_spacecraft_layout/01_standards/NASA_Small_Spacecraft_Technology_SOA_2026.pdf` | 16607339 | `3272266C06740C6FC9EE20AAC0EAB8A69FA1C8D6F3057B8D5CD7238D8B8D0AE0` | present_hash_match | extracted_with_nonfatal_warnings | 458 页，绝大多数页面有可读文本；解析警告未阻断正文提取。 |

## 3. 提取边界

- 本轮只基于 PDF 可解析文本写入，不从图像、常识或外部网页补尺寸。
- 对图纸页未能解析出的尺寸，不写成已确认约束。
- 对 NASA SOA 中供应商和任务案例，仅作为技术现状与报告论据，不写成本项目已采用或已实现。
- 对 CubeSat 标准中的发射适配、部署器和验收要求，只作为 Stage 1-C 布局/CAD 检查输入；最终约束仍需结合具体比赛设定和目标展示模型边界复核。

## 4. 解析工具记录

- 哈希：PowerShell `Get-FileHash -Algorithm SHA256`。
- 文本抽取：bundled Python + `pypdf`，必要处用 `pdfplumber` 复核 CDS Appendix B 图纸页文本层。
- CDS Appendix B 图纸页复核结果：`pdfplumber` 对第 28-34 页仅抽取到页眉，未抽取图纸内部尺寸文字。
