# Digital Mechanical Host v0.1 验证报告

_COMP-PROT-03-A3-G0-EVIDENCE-CLOSURE 工作树快照，2026-07-23_

---

> `VERDICT: PASS_WITH_SCOPE_ISOLATION`<br>
> `HOST_STATUS: PRE_CAD_DIGITAL_MECHANICAL_HOST_CONTRACT_READY`<br>
> `GEOMETRY_ONLY_REQUEST: A3_GEOMETRY_ONLY_ENTRY_REVIEW_READY_TO_REQUEST`<br>
> `GEOMETRY_ONLY_AUTHORIZED: false`<br>
> `FULL_CAD_URDF_ENTRY: CAD_ENTRY_BLOCKED_BY_EVIDENCE`

## 📋 验证结论

数字机械主机主记录、Schema、profile 裁决、质量 owner、Frame Tree v2 候选、机械语义、SolidWorks 输入、15 项 blocker 处置矩阵和第三方许可证包已形成一致的预 CAD 合同。

这个结果只证明数据合同完整且 fail-closed。它不证明结构正确、任务可行、无干涉、可发射，也不表示 CAD、URDF 或仿真已经实现。

## ✅ 机器检查

| 检查 | 结果 | 说明 |
|---|---|---|
| YAML 解析 | `8/8 PASS` | G0 核心 YAML 全部可解析 |
| JSON 解析 | `1/1 PASS` | 主机 Schema 可解析 |
| Schema 实例 | `PASS / 0 errors` | 主机实例满足授权、四层和 UNKNOWN 约束 |
| Schema 负例 | `4/4 REJECTED` | 拒绝 CAD 授权、错 profile、伪造 CoM、静默加入目标 |
| 主机 source packet | `9/9 PASS` | 路径存在且 raw SHA-256 一致 |
| Gate packet | `11/11 PASS` | 路径存在且 raw SHA-256 一致 |
| profile exactly-one | `PASS` | 2 个候选中选择 1 个 |
| 质量复算 | `PASS` | source decimal 精确闭合 |
| fail-closed Frame | `PASS` | `T_SB` 与 `T_E_TCP` 均为 `UNKNOWN_DISABLED` |
| 许可证文本 | `PASS` | 上游 CRLF 与项目 LF 规范化后逐字相同 |
| 禁止资产 | `0` | 新目录无 CAD/URDF/STEP/STL/USD 文件 |

## 📊 质量复算

```text
23.3032134
+ 0.3483933
+ 0.3483933
= 24.0000000 kg

B601 accepted URDF 10-link exact sum
= 4.6955559493429862 kg

24.0000000
+ 1.2
+ 4.6955559493429862
= 29.8955559493429862 kg
```

最终值仍标记为 `PROVISIONAL_DESIGN_LEDGER_TOTAL`。未进行称重、aggregate CoM 重组或 aggregate inertia 重组。

## 🔍 15 项 blocker 处置

| 状态 | 数量 | 含义 |
|---|---:|---|
| **CLOSED_FOR_GEOMETRY_ONLY_INPUT** | 5 | 本阶段所需输入已单值化 |
| **ISOLATED_FROM_GEOMETRY_ONLY** | 7 | 受影响字段对纯几何消费者不可见 |
| **CARRIED_LIMITATION** | 1 | 仅保留有限声明 |
| **A3_EXIT_EVIDENCE** | 2 | 必须由未来 CAD 阶段产生，不能作为循环前置 |

全部 15 项都有 scope disposition，但没有宣称 15 项都对完整 CAD/URDF/动力学范围证据关闭。

## 🔐 核心文件哈希

| 文件 | SHA-256 |
|---|---|
| `research_execution_plan.md` | `455a950ac14acab7b2fcb2e01582e5cb6a3fe7e05fe1e0e01acb55b6375a1ebe` |
| `approval_scope_record.md` | `a4241b29836843d3550eae5608ab9bcc7859b4c6c3d9ae80f20267c819cca67f` |
| `cad_profile_decision_v0_1.yaml` | `f6cf7075fb00ba45548fba23c9a4d36a7e36a76f931cde933f68a01c7b3b898a` |
| `mass_owner_registry_v0_1.yaml` | `ae5b028bdeeebd04ddf53ecdcdb7f867d34b2b01b2c788cc0b85de456ec73410` |
| `frame_tree_v2_candidate.yaml` | `ba2034841602eb46f11f20052b55665e85ed2e064427aa80819d4f1c665e15b6` |
| `mechanical_interface_semantics_v0_1.yaml` | `f3d424e77be9bf394eb30d2796288d0fddc1dcffd8010ef8d8b045835d643020` |
| `solidworks_skeleton_input_v0_1.yaml` | `1601e4820a01f2fed626e78061037bea555b79654995ffca01442d4ac2335017` |
| `digital_mechanical_host.schema.json` | `c6ecc930573088064b6609c07715a630a7aa6ee5d13c647c2e06d404f4045dc9` |
| `digital_mechanical_host_v0_1.yaml` | `846f35d54db3ccc507acb6b4045c557e7799f012d9d36d19e67a9b59ff07296a` |
| `evidence_closure_matrix.yaml` | `2c6351469610641bea911bf8ffed3a7744697d69ade0ad9b81cafb3e929c3174` |
| `a3_geometry_only_entry_gate.yaml` | `c1537c87a65b17e3eeb90a2f09905aaa814b3ccf6814fa2a1abb69ed9cac193f` |
| `CERN-OHL-W-2.0.txt` | `e258a9c6833bfd17fb90252df8c33e29d13fabc2768508248927824c17878db7` |
| `NOTICE.md` | `80a6a2528f2dda8eb159405c98af9b42df0da8cab848e416f551f66e5f844ef4` |
| `PROVENANCE.yaml` | `02c38ec0273ed7850dbdcdb8ae00e728b31936b6541328b1b371c2646239d287` |

README 与本验证报告不进入核心 packet，避免导航或自引用哈希导致循环变化。

## 🚫 未触碰证明

- `20_engineering/config/geometry/` tracked diff：`0`
- `20_engineering/cad/` tracked diff：`0`
- `30_simulation/` tracked diff：`0`
- `40_evidence/` tracked diff：`0`
- sim_10 Gate SHA-256：`367078aa79853591b8da276f047c8c4fdbc4017e5136680fe90ad3432cc14265`
- sim_11 Gate SHA-256：`287aa84824ced51fb4480dfc3d39e9dafc8ee41b37c9de0f73e2d927263fec10`
- competition Gate SHA-256：`8b3cdbdaa09e9048262888f596bacc5a7ec543af55542256e8bce66de15a6200`
- 未运行科学仿真、控制、Basilisk、ROS、Isaac、RL 或 VLA

工作树在本任务开始前已有大量未提交修改。本任务未暂存、未提交，也未清理用户现有改动。

## ⚠️ 下一门槛

可以请求人工批准 `A3-GEOMETRY-ONLY`，但尚未获得执行授权。若批准，下一阶段仍必须携带：

- `NO_DYNAMICS_USE`
- `TARGET_EXCLUDED`
- `NON_FLIGHT_DISPLAY_PROFILE`
- `T_SB=UNKNOWN_DISABLED`
- `T_E_TCP=UNKNOWN_DISABLED`

完整 CAD/URDF 或动力学入口继续阻塞。
