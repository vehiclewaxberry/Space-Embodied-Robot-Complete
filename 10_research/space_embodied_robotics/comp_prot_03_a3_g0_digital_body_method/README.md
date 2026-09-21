# 空间具身智能数字身体构建方法入口

_COMP-PROT-03 A3 前置研究合同，2026-07-23_

---

> `PHASE: COMP-PROT-03-A3-G0-DIGITAL-BODY-METHOD`<br>
> `STATUS: DIGITAL_BODY_METHOD_CONTRACT_ONLY`<br>
> `METHOD_VERDICT: METHOD_CONTRACT_READY_CANDIDATE_INSTANCE_PARTIAL`<br>
> `CAD_ENTRY_VERDICT: CAD_ENTRY_BLOCKED_BY_EVIDENCE`<br>
> `CAD_URDF_SIMULATION_AUTHORIZED: false`<br>
> `SCIENTIFIC_GATE: false`

## 📋 本阶段完成了什么

本目录把 A0/A1 的数字本体、A2 的候选构型与 Digital Skeleton，收敛为一套可重复使用的**空间具身智能数字身体构建方法**。数字身体不再等同于 CAD 文件，而被定义为：

```text
Digital Body
= Geometry
+ Physical Properties
+ Task Semantics
+ Evidence Chain
```

方法已经形成文档、机器可读合同、实例 Schema、12U+B601 示例实例、Claim–Evidence 账本和方法级验收 Gate。示例实例保留所有已知冲突与未知量，不关闭原 `CAD-SKELETON-G0`，也不授权 A3。

## 📦 交付物

| 文件 | 用途 | 权威边界 |
|---|---|---|
| [构建方法](./digital_body_construction_method.md) | 定义四层数字身体、八步构建流程与消费者投影视图 | 研究方法，不是科学 Gate |
| [方法合同](./digital_body_method_contract.yaml) | 固化术语、状态、层级、证据和 fail-closed 规则 | 方法 SSOT，不承载航天器参数真值 |
| [实例 Schema](./digital_body_record.schema.json) | 约束数字身体实例必须同时具有四层记录和跨层绑定 | 数据结构合同，不生成 CAD/URDF |
| [12U+B601 示例实例](./candidate_12u_b601_digital_body_v0_1.yaml) | 将 A2 现有信息投影到四层模型 | `PARTIAL_WITH_EXPLICIT_UNKNOWNS` |
| [Claim–Evidence 账本](./claim_evidence_traceability.yaml) | 绑定允许表述、证据、限制和禁止外推 | 不替代原始证据文件 |
| [方法验收 Gate](./digital_body_method_gate.yaml) | 区分“方法包完整”与“候选机体可进 CAD” | 非科学 Gate；不改变 G0 |
| [验证报告](./verification_report.md) | 记录结构校验、哈希、链接及冻结边界检查 | 当前工作树快照 |

## 📍 建议阅读顺序

1. 阅读 [构建方法](./digital_body_construction_method.md)，理解数字身体为什么不是单一几何模型
2. 阅读 [方法合同](./digital_body_method_contract.yaml)，理解受控词汇和停止规则
3. 对照 [12U+B601 示例实例](./candidate_12u_b601_digital_body_v0_1.yaml)，查看现有项目如何实例化
4. 用 [Claim–Evidence 账本](./claim_evidence_traceability.yaml)检查任何汇报表述
5. 最后读取 [方法验收 Gate](./digital_body_method_gate.yaml)，区分方法完成度和 CAD 准入状态

## 🔐 当前允许与禁止

当前允许表述：

> 已建立一套项目内可实例化、可审计的空间具身智能数字身体构建方法，并用 12U+B601 候选完成了保留未知量的文档级实例化。

当前禁止表述：

- “12U+B601 数字机械样机已经完成”
- “15 项 DB blocker 已全部证据关闭”
- “候选构型已经完成质量、质心、惯量或干涉验证”
- “CAD、URDF、Basilisk、ROS、Isaac、控制器、RL 或 VLA 已实现”
- “方法级 Schema 验证证明了科学模型正确或任务可行”

## 🚫 停止点

本阶段停在 `DIGITAL_BODY_METHOD_CONTRACT_ONLY`。下一合法动作是按既有 [CAD-SKELETON-G0](../comp_prot_03_a2_candidate_model_review/cad_entry_gate.md) 补齐质量 owner、Frame、profile、`T_SM/T_SB`、语义源和许可证证据，并单独申请人工 A3 授权；不得从本方法包自动进入 SolidWorks。

## 🔗 后续进展

`COMP-PROT-03-A3-G0-EVIDENCE-CLOSURE` 已形成 [Digital Mechanical Host v0.1](../comp_prot_03_a3_g0_evidence_closure/README.md)。该后续包只达到 `A3_GEOMETRY_ONLY_ENTRY_REVIEW_READY_TO_REQUEST`，仍未授权 SolidWorks、CAD、URDF 或仿真；完整 CAD/URDF 准入继续保持阻塞。
