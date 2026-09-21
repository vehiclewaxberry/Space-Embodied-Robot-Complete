# 状态机、交接与主张绑定

## 状态转换

```text
CATALOG_ONLY
  ├─ 全文缺失 ─> BLOCKED_NO_LOCAL_PDF
  └─ 全文在盘 ─> PDF_READY_FOR_READING
                     └─ 开始精读 ─> READING_CARD_DRAFT
                                          └─ 结构与定位验收 ─> READING_CARD_COMPLETE
                                                                       └─ 具体主张审核 ─> CLAIM_BOUND
```

DOI/元数据状态与阅读状态是正交字段。`VERIFIED`、`NOT_FOUND` 或 `MISMATCH` 不直接改变阅读完成度。

## 角色交接字段

多 Agent 仅在用户明确要求时启用。每次交接必须包含：

- `task_id`
- `research_question`
- `input_bibkeys`
- `source_paths`
- `source_verification_status`
- `requested_output`
- `completed_checks`
- `unresolved_issues`
- `prohibited_inferences`
- `next_owner`

缺一项则返回 `HANDOFF_INCOMPLETE`。总控是 `controller_state.yaml` 的唯一合并者；子角色不得各自维护平行状态文件。

## 推荐角色边界

- Bibliography：发现候选和登记检索式，不宣布正文可信。
- Source Verification：核对 DOI、版本、PDF、页数和 SHA，不撰写综合结论。
- Reader：逐页提取并写阅读卡，不改 manifest 元数据。
- Synthesis：只使用已核验来源做横向综合，不制造引用。
- Claim Audit：检查措辞、定位符、项目 Gate 与限制，不修改科学结果。

## Claim-evidence 账本字段

`10_research/knowledge_base/papers/claim_evidence_ledger.csv` 使用以下字段：

- `claim_id`
- `claim_text`
- `claim_scope`
- `literature_keys`
- `literature_locators`
- `project_gate_json`
- `project_result_file`
- `figure`
- `commit`
- `confidence`
- `allowed_wording`
- `forbidden_wording`
- `status`
- `reviewed_on`

文学证据字段与项目证据字段不得合并。没有项目 Gate 时留空，不得用论文替代；没有文学来源时也留空，不得虚构“已有共识”。

## 主张状态

- `DRAFT_UNLOCATED`：缺页级定位，不可用于正式文本。
- `LITERATURE_LOCATED`：有文献定位，但未绑定项目证据。
- `PROJECT_EVIDENCE_BOUND`：已绑定项目 Gate/结果，仍需措辞审核。
- `APPROVED_WITH_LIMITATIONS`：证据、范围和限制一致。
- `REJECTED_OVERCLAIM`：措辞超过证据强度。
- `BLOCKED_CONTRADICTION`：来源或项目证据冲突，等待裁决。

## 综合验收

综合交付必须同时给出：研究问题、纳入/排除来源、来源状态、共识、分歧、矛盾、缺口、项目接口、不能声称内容和下一步。按文章顺序逐篇摘要不构成综合完成。
