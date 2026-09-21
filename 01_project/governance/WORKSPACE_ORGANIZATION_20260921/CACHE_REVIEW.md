# 八域可再生缓存审查

日期：2026-09-21。此分项只读识别候选，**未实际删除文件**，也未运行项目模型或更改科学、设计结论。执行清单为 [CACHE_CANDIDATES.json](CACHE_CANDIDATES.json)，生成器为 [tools/cache_scan.py](tools/cache_scan.py)。本轮结果不重复计算上一轮已经删除的 30 项。

## 可执行候选与保留项

最终候选是 **267 个未跟踪文件，共 5,636,960 B（约 5.38 MiB）**：265 个具源码且缓存头匹配的 Python 字节码，2 个已识别结构的 pytest 缓存载荷。每项记录路径、字节数、本机 SHA256、tracked、再生成说明、来源文件及来源 SHA256、缓存头/签名证明、引用保护检查和裁决。

| 所在域 | 删除候选文件数 |
|---|---:|
| `01_project/` | 102 |
| `20_engineering/` | 158 |
| `30_simulation/` | 6 |
| `70_tools/` | 1 |
| `10_research/`、`40_evidence/`、`50_literature/`、`80_third_party/` | 0 |

这不是按 `.pyc` 或 ignored 直接删除：

- 字节码必须找到对应 `.py`，并验证 PEP 552 缓存头。时间戳型核对源 mtime/大小；哈希型核对 keyed source hash；同时登记源文件 SHA256。
- pytest 文件必须有标准 `CACHEDIR.TAG` 签名，并属于已识别的 nodeids/lastfailed/stepwise JSON 或标准说明/标志文件。删除此类缓存会重置 pytest 的失败记忆/收集便利状态，不应删除测试结果或 Gate。
- 全域清单、合同、Gate、来源与具名证据，以及可执行脚本中的精确路径或 SHA256 引用会触发保留。**19 项被保守保留**，其中确有 WP09 `OUTPUT_SHA256.csv` 中绑定的字节码、机械封存清单中的 pytest 文件；部分共用缓存内容因与其他记录同 hash 被保守保护，并未据此宣称它们一定是动态依赖。
- **116 项证据不足，保持原位**：99 项字节码缓存头与当前源未证明匹配，4 项没有保留的 `.py`，10 项未证明标准 pytest 签名，3 项新机械整理工具的 COM 包装缓存尚未逐包绑定生成器/封存关系。

这轮可靠收益约 5.38 MiB。已不再有上一轮的 967 MB KiCad 安装器，不为了增加删除量而选大 CAD、ZIP 或唯一结果。

## 覆盖与明确排除

八个业务域枚举 **58,822** 个文件；读取 **10,235** 个参考文本文件用于保护核对。参考范围是全部 `.py/.ps1/.sh`，以及文件名含 manifest、sha256、资产索引/登记、Gate、contract、source、plan、handoff、input、provenance、receipt 的 JSON/CSV/YAML/TOML/Markdown。单文件上限 25 MiB；本轮没有因该上限跳过参考文件。只记录匹配的文件名，不输出文件内容或凭据。

`.git/.codex/.agents`、第三方嵌套 `.git`、活动虚拟环境、`site-packages`、`node_modules`、`portable`、`_runtime`、cadgen 安装库和 `70_tools/runtime_*` 安装目录排除。名称含 runtime 的研究后端仍已覆盖。`__cadgen__` 已有图册和包络诊断消费者，继续保留，不当作通用浏览缓存。扫描不跟随 symlink/reparse。

提权只读访问后，仍有 **10 个**具名 pytest/tmp 目录返回 PermissionError；完整路径见 JSON `scan_errors`。它们保持原位，没有修改 ACL 或按“不存在”处理。未覆盖内容不计入可删除收益。

## 根代理执行条件

1. 只使用 `recommendation=DELETE_CANDIDATE` 的精确文件；与根代理全局保护集合再次交叉。不能将本清单扩大为父目录递归删除。
2. 执行前逐项重新核对路径归属、SHA256、字节数和源码 SHA256；变化则跳过，不能沿用旧扫描值强删。
3. 对 pytest 候选，`source_is_deleted_cache_marker=true` 指示来源只是标准缓存签名；应先完成整批标记核对，保留测试源码与结果。本轮不要求删除完整 pytest 目录。
4. 不删 tracked 缓存、被引用缓存、来源不明缓存、`_work`/archive/history/.tmp 中的其他文件；不改 Git 历史。根目录和嵌套安装运行库均保持原位。
5. 本次保护检查不构成所有动态依赖的形式化证明。清理后保留原 Gate/manifest 字节，记录删除收据与未处理项；缓存随后被 Python/pytest 自动再生不等于重新出现无用设计资产。
