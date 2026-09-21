# 硬件设计目录精简：独立删除候选复核

日期：2026-09-21。此分项仅识别候选，**实际删除数为 0**；由根代理结合其他依赖审计决定并执行。没有修改 Git、删除历史、处理 `10_research/` 或 `30_simulation/`。未根据沙箱曾误报的 125 个 `D` 作删除判断。

## 可交给根代理执行前核对的清单

已生成逐文件 [CLEANUP_CANDIDATES.json](CLEANUP_CANDIDATES.json)，**30 个文件，合计 1,005,499,308 B，约 1.005 GB / 958.92 MiB**。每项均有本机 SHA256、字节数、tracked 标记、再生成原因或逐字节重复来源，以及当前清单引用检查。

| 候选 | 文件数 | 字节数 | 依据 |
|---|---:|---:|---|
| `70_tools/runtime_wp09_kicad/kicad-10.0.6-x86_64.exe` | 1 | 967,765,696 | 已解包安装器载荷；保留 `portable/`、获取脚本和原下载回执即可保留当前执行环境 |
| 当前 SERVICE_STAR 包 `tools/_generated_com/` 的明确文件 | 18 | 37,630,644 | makepy 自动生成的 SolidWorks 2024 类型库包装器、索引；保留源工具 `configure_com()` 会通过 `gencache.EnsureModule` 重建 |
| 当前 SERVICE_STAR 包中有对应 `.py` 源文件的 `.pyc` | 11 | 102,968 | 源码存在且 SHA256 已登记；CPython 可再生成；不含 CAD 或 Gate 原始结果 |

只有安装器是 tracked 文件，其余 29 项不在 Git 索引。缓存中 10 项还有另一份逐字节同哈希副本，但全部缓存的主要删除依据是可再生成，而非假定所有包装器字节相同。包装器含生成时间，重新生成可能得到不同字节，不承诺旧缓存 hash 重现。

安装器实测 SHA256 为 `9e24dc47119f7c472128c2f293c5e3f35569274a44c905e60a7514d47c16ce48`，与 `reuse_closure/results/KICAD_DOWNLOAD.json` 完全一致。`portable/bin/kicad-cli.exe` 实际存在。相关获取脚本与回执属于来源记录，应保留；未来下载源可用性未测试。**删除本地安装器不会清除 Git 可达历史中的 922.933 MiB blob，因此不能单独解决 GitHub 普通文件上限。**

COM 缓存分布在 R1、R2、R3、R4、已撤回的 R6，以及 R6H 六个包；这里只删明确列出的三类自动生成文件，不删这些设计包或其历史状态。R6H 的 `finalize_delivery.py` 和 `PACKAGE_VALIDATION.json` 显式将 `_generated_com/`、`__pycache__/`、`*.pyc` 排除在封存清单外。

## 依赖复核范围

对下列三份当前清单，30 项均未命中完整路径或文件 hash：

- `20_engineering/SERVICE_STAR_CORE_INSTALLATION_R6H_20260920/SOURCE_DEPENDENCIES_SHA256.csv`
- `20_engineering/SERVICE_STAR_CORE_INSTALLATION_R6H_20260920/PACKAGE_SHA256.csv`
- `20_engineering/SERVICE_STAR_ELECTRICAL_UPDATE_R5E_20260920/PACKAGE_SHA256.csv`

另外只读扫描 `20_engineering/` 和具名机械整理包内 **299** 份机械资产/来源/哈希清单，匹配文件名中的 manifest、sha256、asset index/register、handoff_latest、dependency，限定 CSV/JSON/YAML 且小于 25 MiB；30 项均未命中完整路径或文件 hash。扫描排除生成缓存、软件运行时目录。这不是所有可能动态消费者的形式化证明；根代理如有更完整保护清单，应再与候选交叉。

执行前应重新核对 JSON 中的精确绝对解析范围、文件大小和 SHA256，再只删除这些具体文件；不要把父目录通配符扩成递归删除规则。若任一文件变化、被新的清单引用、或出现无法解释的权限错误，停止该项并保留。已经运行中的 Python/SolidWorks 会话应结束其生成缓存使用后再清理；清理后当前原生 CAD 和封存 manifest 应保持原 hash。

## 明确保留，不能为了体积勉强删除

1. **WP01/WP02/WP03 的 `__cadgen__` 树。** `CURRENT_candidate.md:151` 明确记录 13,954 个文件中含图册消费者和包络诊断来源，已有 STEP/PNG 不能证明完整替代。大 `topology.glb` 看似缓存，但本分项不批准删除。
2. **R1 的 `SERVICE_STAR_R1_REVIEW_PACKAGE.zip`（333,834,996 B）。** 已有封存回执和 `package_delivery.py` 的白名单/冷复验依赖，不是已经证明无用的重复 ZIP。本分项保留。
3. **解包后的 `70_tools/runtime_wp09_kicad/portable/`。** 既有电气脚本使用它，删除安装器的理由不适用于删除可执行运行时。
4. **旧原生 CAD、STEP、donor、副本、失败几何、`_work`、archive、history 和 ZIP 不按目录名自动删除。** 历史整理入口已记载来源锁定、授权基线和失效原件职责；本轮未证明其可替代性。
5. **日志和负结果不整树清理。** 仅大小或名称不能区分无用 HTTP 日志与当前验证证据，故本分项不主动扩大到未审阅日志。

所得约 1 GB 是有证据支持的保守收益。进一步压缩硬件目录应依赖根代理建立的当前依赖闭包和公开发布包，而不是扩大本清单为“旧文件一律删除”。
