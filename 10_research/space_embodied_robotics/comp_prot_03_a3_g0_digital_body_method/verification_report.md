# 空间具身智能数字身体方法验证报告

_COMP-PROT-03-A3-G0-DIGITAL-BODY-METHOD 工作树快照，2026-07-23_

---

> `VERDICT: METHOD_CONTRACT_READY_CANDIDATE_INSTANCE_PARTIAL`<br>
> `SCHEMA_INSTANCE_VALID: true`<br>
> `CAD_ENTRY_VERDICT: CAD_ENTRY_BLOCKED_BY_EVIDENCE`<br>
> `A3_AUTHORIZED: false`

## 📋 验证结论

方法文档、机器可读合同、实例 Schema、12U+B601 示例实例、Claim–Evidence 账本和方法 Gate 已形成一致包。Schema 与自定义跨层检查均通过；候选实例仍保留 10 项显式未知量，未把结构完整性解释为物理正确、科学 PASS 或 CAD 准入。

## 🔐 核心文件哈希

以下 SHA-256 均按 raw bytes 计算；验证报告和导航文件不纳入核心包，避免自引用哈希。

| 文件 | SHA-256 |
|---|---|
| `digital_body_construction_method.md` | `aabd23f5aa2a074560682ebbceca5faa6e162f34a849e13cf6280b325c776a61` |
| `digital_body_method_contract.yaml` | `5b903426d704dbd6c9497b46db2058acdcf82b0230b9e2a03fa09eccb19a2aa4` |
| `digital_body_record.schema.json` | `eb221afbe65b59642f01ffa01e2566c4470c31a85ee64636c0c3199630cfbbae` |
| `candidate_12u_b601_digital_body_v0_1.yaml` | `7eb0f299a273255f3ddcfe19389d4fccdeefe2537be508d96ee63e60c305375d` |
| `claim_evidence_traceability.yaml` | `11581f152c3b8a895ed001729df60488ea4e064a183fb168af27dc9231893cb0` |
| `digital_body_method_gate.yaml` | `90f619a893e97d951d5de1bc40ebfe448cc256f56a6c114fd21407d9a6917b2a` |

## ✅ 结构与一致性检查

| 检查 | 结果 | 说明 |
|---|---|---|
| YAML 解析 | `4/4 PASS` | method contract、candidate instance、traceability、method Gate |
| JSON 解析 | `1/1 PASS` | `digital_body_record.schema.json` |
| Schema 实例验证 | `PASS / 0 errors` | 示例实例满足四层和 fail-closed 结构 |
| Schema 负例 | `4/4 REJECTED` | 拒绝 CAD 授权绕过、UNKNOWN 偷填值、删除语义层和 provisional 去来源 |
| 几何引用 | `PASS` | 7 entities、11 frames，无重复 ID 或悬空 entity 引用 |
| 物理引用 | `PASS` | 9 properties、5 mass owner components |
| 任务语义引用 | `PASS` | 8 semantic features 均具有 geometry owner |
| 跨层绑定 | `PASS` | 3 bindings，均绑定 geometry、semantic 与 evidence |
| 显式未知量 | `PASS` | 10 项，均记录 owner 与 blocked consumers |
| 证据源 | `7/7 PASS` | 实例引用文件均存在且 raw SHA-256 一致 |
| A2 核心包 | `5/5 PASS` | A2 标准、构型、骨架、blocker ledger、CAD Gate 哈希未变 |
| Claim–Evidence | `10/10 BOUND` | 0 条新增科学结论 |
| Markdown 链接 | `PASS` | 新目录及两处研究导航链接均可解析 |
| Mermaid 可访问性 | `4/4 PASS` | 每个图均含 `accTitle` 和 `accDescr` |

## 📊 数值与所有权复核

质量复核使用原 source decimal，不把显示精度替代为真值：

```text
23.3032134
+ 0.3483933
+ 0.3483933
= 24.0000000 kg

24.0000000
+ 1.2
+ 4.6955559493429862
= 29.8955559493429862 kg
```

结果仍只允许标记为 `PROVISIONAL_DESIGN_LEDGER_TOTAL`。aggregate CoM 与 aggregate inertia 均为 `UNKNOWN`；未运行重组计算、物理称重或动力学验证。

## 🚫 CAD 与冻结边界

- 当前 Git HEAD：`b75352c1c226c0f3e9a4bc9c469b766e06f41616`
- `20_engineering/config/geometry/`、`20_engineering/cad/`、`30_simulation/`、`40_evidence/` 的 tracked diff：`0`
- 新目录中的 CAD/URDF/USD/STEP/STL/SLDPRT/SLDASM 文件：`0`
- 未运行仿真、控制、训练、Basilisk、ROS 或 Isaac
- `30_simulation/module_cards/` 在本任务开始前已经是 untracked，文件时间为 2026-07-22；本任务未创建或修改它
- 工作树在本任务开始前已存在多项未提交修改；本任务未暂存、未提交，也未清理用户现有改动

## ⚠️ 仍未关闭的准入问题

本方法没有改变 A2 blocker 状态：

- 15/15 已进入处置账本
- `CLOSED_BY_DESIGN: 4`
- `CLOSED_BY_EVIDENCE: 1`
- `ISOLATED_FROM_SCOPE: 4`
- `OPEN_BLOCKING: 6`
- 项目证据层仍有 14 项 open 或 limited

`CAD-SKELETON-G0` 要求在 A3 前继续关闭 `DB-BLK-001/002/008/009/010/012/013/014` 的对应证据。本方法只提供关闭这些问题时应写入何种对象、属性、语义和证据字段，不代替 owner 签核、许可证归档、Frame 裁决或物理干涉检查。

## 📍 最终裁决

```text
METHOD_CONTRACT_READY_CANDIDATE_INSTANCE_PARTIAL
CAD_ENTRY_BLOCKED_BY_EVIDENCE
A3_AUTHORIZED=false
```

下一合法 Gate 为 `COMP-PROT-03-A3-G0-EVIDENCE-CLOSURE`。即使该 Gate 未来满足，也仍需新的人工 A3 授权。
