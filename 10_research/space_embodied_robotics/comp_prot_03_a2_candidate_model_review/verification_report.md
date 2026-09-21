# COMP-PROT-03-A2 验证报告

*Final local verification snapshot, 2026-07-23*

---

> `A2_DOCUMENT_PACKET: COMPLETE_WITH_RECORDED_DOWNSTREAM_BLOCKS`<br>
> `PACKET_HASH_INTEGRITY: confirmed`<br>
> `CAD_ENTRY: CAD_ENTRY_BLOCKED_BY_EVIDENCE`<br>
> `A3_AUTHORIZED: false`<br>
> `GIT_RECOVERABLE_FREEZE: false — packet directory remains untracked`

## 📦 最终五文件冻结组

| 文件 | SHA-256 |
|---|---|
| `mechanical_configuration_design_standard.md` | `61fb5695f9f3e03788a5a3e226c344217b10c5cbe121e15c2161aeab52f3242e` |
| `candidate_configuration_v0.yaml` | `a055fb70c7e39047a84381c22bafed61a63932c334e81986a7b14599dce0a820` |
| `digital_skeleton_model_v0.yaml` | `5d0f87aaabc00e43466873d67213455f75c568521eb5acaa84dbeed6d3d7248d` |
| `db_blocker_resolution_ledger.yaml` | `c71308c2b5d3cab5ebb93d2340771eb7bcddb4b9e4654c316bff5bfd1a40e7b8` |
| `cad_entry_gate.md` | `f2846219a6bd0ca906f9b95636b707120d22ac158c960314705dc133e5b91353` |

补充评审记录 `configuration_review.yaml` 的本次快照哈希为 `e1e197f9d3cac33966b58957751d82eda708ce0144d573764bf7878e0719c379`。它不是五文件冻结组的自包含成员，避免自哈希循环。

## ✅ 本地结构校验

| 检查 | 结果 |
|---|---|
| YAML 解析 | `4/4` 成功 |
| Digital Skeleton | `30 nodes / 32 edges`，ID 唯一、无悬空引用、无孤立节点、无有向环 |
| Transform references | `21/21` 已注册；UNKNOWN/外部/运行时状态显式区分 |
| B601 topology | `10 links / 9 joints` 与 accepted URDF 的 parent、child、origin、axis 和 limits 一致 |
| B601 source-decimal mass | `4.6955559493429862 kg`，十个 link 的源数字符串逐项一致 |
| 候选质量账本 | `24 + 1.2 + 4.6955559493429862 = 29.8955559493429862 kg` |
| Exactly-one | `split_bus_panels_v1` 与 `full_urdf_10link` 两组均单选，active component 的 `representation_member` 一致 |
| Keepout registry | 碎片光滑壳体/后发动机区 + 目标星两块太阳翼/天线，共 `5` 项，无畸形记录 |
| DB blocker ledger | `15/15` 唯一；`4 design / 1 evidence / 4 isolated / 6 open`，计数与逐项一致 |
| Markdown local links | 全部可解析 |

`29.8955559493429862 kg` 只是一项 `PROVISIONAL_DESIGN_LEDGER_TOTAL`，不是实测或最终整机质量；总 CoM 与惯量仍是 `UNKNOWN`。

## 👥 多智能体回归

三名独立 Agent 对同一最终五文件哈希组完成只读回归：

- Geometry / Competition Configuration：哈希、profile、flange/adapter、keepout 和 exactly-one 通过；Geometry hard veto 保留。
- Dynamics / Robotics-URDF：质量源数字符串、URDF 拓扑、图结构和 transform registry 通过；Dynamics hard veto 保留。
- Mission / Red Team：15 项处置、目标独立性、历史 Gate、许可和禁止声明通过；未发现剩余过度主张。

由于五个核心角色由三名 Agent 承担，存在两项已记录的角色合并例外；因此 `advisory_final_packet_hash_review_coverage=1.0`，但“五名相互独立 reviewer”的正式程序条件仍未满足，不能升级为 `REVIEW_READY`。

## 🔐 冻结边界复核

- 当前 HEAD 仍为 `b75352c1c226c0f3e9a4bc9c469b766e06f41616`。
- 基线登记的 15 份 Gate JSON 与 12 份关键几何/质量/CAD source，共 `27` 个文件，raw SHA-256 mismatch 为 `0`。
- `30_simulation/`、`40_evidence/`、`20_engineering/config/geometry/`、`20_engineering/cad/` 的 tracked diff 均为 `0`。
- 未运行仿真，未生成或修改 CAD/URDF，未复制外部 STEP/许可证进入交付包。

工作区在本任务前已经存在未提交内容；本轮没有清理、覆盖或提交这些用户资产。A2 目录当前仍未跟踪，因此 raw-byte 哈希已冻结，但 Git 可恢复冻结尚未成立。

## 🚦 最终裁决

```text
COMP_PROT_03_A2_DOCUMENT_COMPLETE_WITH_RECORDED_DOWNSTREAM_BLOCKS
CAD_ENTRY_BLOCKED_BY_EVIDENCE
CAD_ACCEPTANCE_NOT_EVALUABLE_NO_ARTIFACT
A3_AUTHORIZED=false
```

正式进入 CAD/URDF 前，必须按 [CAD-SKELETON-G0](./cad_entry_gate.md) 关闭规定的证据项并获得独立人工授权。

