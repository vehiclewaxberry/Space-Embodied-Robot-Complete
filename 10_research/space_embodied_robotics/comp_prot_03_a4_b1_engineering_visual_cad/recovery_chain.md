# A4-B1 构建恢复链

## 结论

最终 V1.0 是一次**受控恢复后的有效构建**，不是“一次性无故障构建”。历史失败与最终成功证据同时保留。

## 恢复顺序

1. 早期尝试 01–04 在建模 API、文档生命周期和几何生成环节暴露问题；对应目录保存在 `20_engineering/cad/_failed_builds/A4_B1_attempt_*`。
2. 完整构建在 26 个前置资产已经保存后触发外层工具超时。该事件由 `evidence/resume_after_tool_timeout.marker` 记录。
3. 受控续建仅补齐顶层总装、评审装配、独立 target scene 与视图，不重做已核验资产。
4. 续建结束时，SOLIDWORKS 仍持有文件句柄，导致最终哈希步骤失败；`evidence/builder_failure.log` 保留这一历史事实。
5. 释放 SOLIDWORKS 文档后执行终结器，生成 32 条原生文件 manifest 和 `evidence/native_build.log`。
6. 独立 inspector 重新打开/重建全部原生文件并完成 247 项检查。
7. 独立 inventory exporter 导出文档、属性、特征和组件清单；validation 为 `PASS`。
8. 重新导出无重叠注释的原生视图，再生成确定性的带注释评审图。
9. 最后生成证据 seal；seal 之前的全部证据文件均逐字节 SHA-256 封存。

## 证据优先级

发生冲突时按下列顺序解释：

1. `evidence/evidence_seal_manifest.csv`
2. `evidence/native_inspection.json`
3. `evidence/inventory_validation.json`
4. `evidence/native_component_manifest.csv`
5. 两份 review-view hash manifest
6. `evidence/native_build.log`
7. `evidence/builder_failure_superseded.md`
8. `evidence/builder_failure.log` 与历史 attempt 目录

`builder_failure.log` 不能单独用于判断最终 V1.0 失败；它只说明恢复前的终结步骤失败。反过来，最终 `PASS` 也不能用于抹去恢复史或宣称 clean first pass。

