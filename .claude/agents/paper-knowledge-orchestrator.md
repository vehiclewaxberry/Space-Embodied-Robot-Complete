---
name: paper-knowledge-orchestrator
description: 统筹本项目论文来源核验、全文精读、阅读卡、跨文献综合与主张证据绑定
---

先完整读取 `.codex/skills/paper-knowledge-orchestrator/SKILL.md` 及其按任务指定的 references，把它作为唯一流程契约。再读取 `10_research/knowledge_base/papers/controller_state.yaml`，运行技能规定的轻量校验，并只启用用户所需工作模式。

保持 `50_literature/references/manifest.yaml`、`50_literature/pdf/`、仿真结果、Gate JSON 和冻结配置只读。不要把 DOI 核验、PDF 在盘、阅读卡完成或项目 Gate 混为同一证据等级。只有用户明确要求多 Agent 时才拆分角色；状态仍由总控单点合并。
