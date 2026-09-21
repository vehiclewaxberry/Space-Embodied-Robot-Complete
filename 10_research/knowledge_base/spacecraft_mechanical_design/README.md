# MECH-TI-01 机械真值入口完整性闭环

> **身份声明：`RECONSTRUCTED_NAVIGATION_ENTRY_NOT_HISTORICAL`**
>
> 本目录是 2026-08-25 新建的机械真值**导航与完整性入口**。它不是 A4-B2 清单中已丢失知识库原文的恢复件、复制件或等价替代件，也不继承那些原件的历史 SHA-256、字节数或内容权威。

## 当前机器裁决

`PASS_MECH_TI_01_RECONSTRUCTED_NAVIGATION_INTEGRITY_ONLY`

这个 PASS 仅表示：现行机械真值入口已能用哈希锁定的来源，按 fail-closed 方式复述当前权威关系和阻断状态，并能被独立验证与负控击穿。它不表示机械设计、CAD、结构、动力学、接触、RL、制造或飞行资格通过。

当前状态原样继承：

- M7 机械 Loop V5：`HOLD`，`released_segments=0`，`next_stage_authorized=false`；
- M7 工程发布 Gate：`5 PASS + 12 PASS_WITH_DECLARED_OPEN_ITEM + 1 HOLD`，`review_status=PENDING_OWNER_REVIEW`，`next_stage_authorized=false`；
- Unified R2 有效 prebind：`6/20 PASS`、`14/20 HOLD`；
- Route-C MPI：`0/8 CONTROLLED`；
- Route-C 物理注册表 P01–P13：`0/13 non-null`、`13/13 HOLD`；
- Checkpoint-B：完整性 `8/8`，准入 `2/8`，结果 `HOLD`，Route-C CAD 禁止；
- 当前 Sim13 生产机械绑定：被较新的 M7 证据判为无效；
- 当前 Mechanical→Embodied Handoff V2：`FAIL`；
- Owner 接受、下一阶段、发布、生产动力学、物理接触/RL 权限：全部保持 `false`。

## 真值顺序

1. 具名 Owner 授权或机器 Gate；
2. 哈希锁定的现行 Gate、合同、注册表与 frame/geometry SSOT；
3. 历史清单及其预期身份；
4. 本目录的派生导航、权威图和阻断矩阵；
5. 对话、视觉、案例与 Agent 意见。

本目录永远不能反向覆盖第 1–3 层，也不能把历史“曾存在”推断为当前“已恢复”。

## 文件

- `knowledge_contract.yaml`：MECH-TI-01 的允许/禁止用途与 fail-closed 不变量；
- `source_registry.yaml`：现行外部来源的 bytes+SHA-256 锁；
- `MECH_TI_01_HISTORICAL_MISSING_ORIGINAL_AUDIT_V1.json`：A4-B2 清单内 10 个历史知识库原件的缺失审计；
- `MECH_TI_01_AUTHORITY_GRAPH_V1.json`：历史身份、现行 Gate、Route-C、Unified R2、Sim13 与 Handoff 的权威关系；
- `MECH_TI_01_BLOCKER_MATRIX_V1.json`：PRB-01..20、MPI-01..08、P01..13 的只读阻断矩阵；
- `MECH_TI_01_SHA256_MANIFEST_V1.csv`：本包非结果文件的哈希封印；
- `validate_mech_ti_01.py`：只读独立验证器；
- `run_negative_controls.py`：在系统临时目录中运行的语义负控；
- `results/`：验证、负控和机器 Gate。

## 允许的主张

- 当前存在一个可复核、可击穿、哈希锁定的重建导航入口；
- 历史 A4-B2 清单列出的 10 个知识库原件没有在 2026-08-25 全工作区精确哈希扫描中找到；
- 本入口准确复述其锁定来源中的当前阻断状态。

## 禁止的主张

- 历史知识库原文已恢复；
- 本目录重建了历史规则、知识卡或 blocked unknowns 的原始内容；
- M7、Unified R2、Route-C、Sim13、Handoff、CAD、URDF、FEA、仿真或发布状态因本包而升级；
- 测试 PASS 等于科学、产品、制造或飞行 Gate PASS。

## 下一合法动作

仅接收具名 Owner 或可追溯实物/供应商证据，按原 Gate 的单位、容差/不确定度、来源和 authority class 要求更新其**原拥有者目录**；然后重跑相应历史 Gate。本目录只能随新的已锁定机器裁决追加导航版本，不能替代原 Gate。
