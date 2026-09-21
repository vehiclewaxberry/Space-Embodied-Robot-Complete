# 保护资产独立只读完整性复核

日期：2026-09-21T10:03:48.657178+00:00。裁决：`PASS_ALL_PROTECTED_AND_CURRENT_NATIVE_HASHES_UNCHANGED`。

仅按既定清单独立流式计算SHA256与已提供的字节数，未运行CAD/仿真，未改源文件、清单或文件权限。

| 核验组 | 清单行数 | 匹配 | 异常 | 路径基准 |
|---|---:|---:|---:|---|
| PROTECTED_BASELINE | 544 | 544 | 0 | `.` |
| COMPACT_PACKAGE_MANIFEST | 959 | 959 | 0 | `20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921` |
| R6H_NATIVE_SOURCE_LOCK | 790 | 790 | 0 | `.` |
| R6H_ORIGINAL_TOP | 1 | 1 | 0 | `.` |

合计2294次具名核验，2294匹配；去重后2292个实际文件。重复核验来自不同清单的交叉保护，不能把总核验次数称为不同文件数。

原R6H顶层仍为 `30ccbcbcff047ef54a112b841cf4814646714b24141b822bacbca13e1a5e45a7`；清单自身在复核前后字节一致=True。

异常（若有）：
- 无哈希/大小不匹配、缺文件、访问错误或重复清单路径。

本回执仅证明被列保护文件的字节完整性；不构成工程、科学、公开授权或全工作区逐文件内容验收。
