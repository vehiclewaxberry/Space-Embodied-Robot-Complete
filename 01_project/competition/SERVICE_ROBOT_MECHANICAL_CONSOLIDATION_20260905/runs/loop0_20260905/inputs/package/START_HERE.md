# WP03对抗式审阅与闭环工程执行包

## 结论范围

本包基于本轮上传的7份WP03文档/脚本。已完成文档逐项审阅、两份Python代码静态检查，以及`pose_screen.py`状态表达式的6组隔离合成记录试验。没有导入或运行该工程脚本、没有执行CAD/VTK/OCC、没有读取用户F盘、没有启动真实多Agent、没有修改用户项目。

建议：允许进入有界的问题修复、接口详细化及带显式未知参数的研究模型建设；不据此批准完整机构可用、实物承载、制造发布、发射收拢、部署器兼容或空间环境资格。

## 最短使用路径

将`01_MASTER_EXECUTION_PROMPT_ZH.md`交给本地协调Agent，默认执行REVIEW_AND_PLAN。让Agent先获取原始本地收据、统一问题账本和依赖导航。独立确认最小修改范围后，由Owner一次性授权对应候选整改范围，避免逐孔问批和无限审计。

## 本包文件

| 文件 | 用途 |
|---|---|
| 01_MASTER_EXECUTION_PROMPT_ZH.md | 主提示词、七角色分工、对抗问题、迭代与安全整理规则 |
| issue_register_seed.json | 16项种子问题；逐项区分文档声明、静态代码、合成试验与工程推断 |
| loop_contract.yaml | 提议的运行模式、并发/预算、状态机与接受契约；不是已执行配置 |
| status_branch_probe.py | 从上传脚本AST提取单个状态表达式，仅用合成记录运行 |
| status_branch_probe_results.json | 本次6组合成试验结果；不是CAD碰撞结果 |
| source_manifest.json | 7份上传文件的实际字节hash与缺少的原始输入清单 |

### 复现隔离试验

在Python环境中运行（不需要numpy、VTK或CAD库）：

```text
python status_branch_probe.py --source <pose_screen.py实际路径> --output <一个尚不存在的新JSON路径>
```

脚本不会导入源脚本，只解析AST并执行白名单中的单个条件表达式。源状态分支发生变化时可能拒绝继续，需要人工审阅。输出已存在时拒绝覆盖。

### 对试验的正确解读

当前表达式只根据是否有相交记录与`checked == 35`选择表面筛查标签。34种配对+1条重复、35条非预期ID，也能得到相同标签；worker_completed不参与该表达式。这证明验收汇总缺少身份/完整性防护，不证明任何既有几何检查已经漏检或结果为假。

完整修复还需要本地拓扑、输入hash与结果契约，不能仅用本包合成配对替代实际期望集合。

## 整理原则

第一轮不移动WP01/WP02/WP03，不删旧结果；`pose_screen.py`仍依赖旧目录。先建立单一导航和依赖图，再讨论经验证的派生副本与冷重建。相同hash、旧日期、新版本存在均不是自动删除授权。本包没有自动清理脚本。

## 方法参照

以下为方法参考，不是该项目已经通过的标准条款：

- NASA — Configuration Management: https://www.nasa.gov/reference/6-5-configuration-management/
- NASA — Product Verification: https://www.nasa.gov/reference/5-3-product-verification/
- NASA — Product Validation: https://www.nasa.gov/reference/5-4-product-validation/
- ECSS — Mechanisms Rev.2: https://ecss.nl/standard/ecss-e-st-33-01c-rev-2-1-march-2019-space-engineering-mechanisms/
- Anthropic — Building Effective Agents: https://www.anthropic.com/engineering/building-effective-agents
- LangChain — The Art of Loop Engineering (2026-06-16): https://www.langchain.com/blog/the-art-of-loop-engineering

这里采用清晰判据、独立验证和有界反馈循环，不要求安装LangChain或任何新服务。Agent数量/预算是本次工程调度建议，不是航天标准要求。
