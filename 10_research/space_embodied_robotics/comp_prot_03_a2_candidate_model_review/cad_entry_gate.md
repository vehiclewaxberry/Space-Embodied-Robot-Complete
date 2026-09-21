# CAD-SKELETON-G0：A3 建模入口闸门

*Evidence gate between Digital Skeleton Model and integrated CAD/URDF authoring*

---

> `CURRENT_VERDICT: CAD_ENTRY_BLOCKED_BY_EVIDENCE`<br>
> `A3_AUTHORIZED: false`<br>
> `AUTOMATIC_TRANSITION: forbidden`<br>
> `SCIENTIFIC_GATE: false`

## 📋 为什么不能把 15/15 机械地设为 CAD 前置

`DB-BLK-015` 的定义是“尚无集成 CAD/URDF”，它只能由 A3 产物关闭；`DB-BLK-010` 中实际干涉和间隙也必须在 CAD 中检查。若要求这两项在 CAD 之前证据关闭，就会形成循环。

因此本闸门把阻塞分成三类：

1. **A3 输入必须证据闭合**：没有它们就不能开始正式总装；
2. **带限制或条件进入**：可隔离，但不得继承能力声明；
3. **A3 退出项**：正是 CAD/URDF 要产生的证据。

满足本闸门后，最强状态也只能是 `CAD_ENTRY_REVIEW_READY_TO_REQUEST_A3` 或 `CAD_ENTRY_REVIEW_READY_WITH_LIMITATIONS_TO_REQUEST_A3`，仍需新的人工批准，不能自动建模。

## 🔒 A3 前必须闭合

| Gate item | 对应 blocker | 关闭证据 |
|---|---|---|
| Mass owner signoff | `DB-BLK-001` | 对 split 24 kg、适配器、full-URDF B601 的互斥和包含范围签核；保留 `29.8955559493429862 kg` 的 source-decimal provisional 水印 |
| Tool frame signoff | `DB-BLK-002` | Geometry + Robotics/URDF 双签 `E` 的 parent、完整变换、用途和与 `G` 的区别；FK 往返检查方案 |
| B601 mass source decision | `DB-BLK-008` | 明确 accepted URDF 精确逐 link 值为候选 owner，并记录 YAML 冲突的处置；不得用容差静默吞掉 |
| Free-flyer frame binding | `DB-BLK-009` | `B` 原点、轴和唯一 `T_SB` 的来源/置信度/owner；禁止默认 identity |
| Flange/profile input | `DB-BLK-010` input part | 选择 160 mm 现行接口、排除 140 mm consumer，并选定唯一 geometry profile |
| Debris semantic source | `DB-BLK-012` | canonical source 将正 Z 特征统一为前端环，并将 aft engine 区统一为禁触区 |
| Unique `T_SM` | `DB-BLK-013` | 在 `COMPETITION_DISPLAY_V0` 与 `CDS_12U_REFERENCE` 中只选一个，并给出完整、单值、签核后的 `T_SM` |
| Portable provenance/license | `DB-BLK-014` | B601 资产包携带 CERN-OHL-W-2.0 全文、NOTICE、上游提交、源哈希与修改说明 |

## 🧷 条件项与可隔离项

| Blocker | 允许处理 | 触发为硬阻塞的条件 |
|---|---|---|
| `DB-BLK-003` | 不消费 vendor STEP 时，提交 dependency-exclusion 证据 | A3 导入或派生 vendor STEP |
| `DB-BLK-004` | Interface 2 可延期且禁止硬捕获/装配声明 | 目标或接触几何进入 A3 时，Interface 0/1 必须闭合 |
| `DB-BLK-005` | 12U 图纸输入已人工复核，但只作 reference | 声称发射/部署器合规 |
| `DB-BLK-006` | E16 保持历史参考 | 候选试图继承 E16 Gate、protected bundle 或 SAFE 结论 |
| `DB-BLK-007` | sim05 loader 完全隔离 | 声称当前 runtime model/仿真入口可用 |
| `DB-BLK-011` | 目标分支保持 inactive、只保留 point+normal | 目标进入总装、场景或 6DOF rigid lock |

## 🏁 A3 退出项

| Exit item | 对应 blocker | A3 必须输出的证据 |
|---|---|---|
| 集成模型 | `DB-BLK-015` | 一份 profile-bound 12U+adapter+B601 总装；若含目标，目标仍为独立 runtime body，接触边是条件边 |
| 法兰与适配器间隙 | `DB-BLK-010` physical part | 干涉报告、rail/contact overlay、6.5 mm protrusion 检查、8.5 mm first-protrusion 检查 |
| CAD/URDF frame round-trip | `DB-BLK-002/009/011/013` | `S→M→A0→arm→E` 与可选 `T/D/C` 完整变换的往返报告 |
| 资产包证据 | `DB-BLK-003/014/015` | 每个外部/派生资产的 path、SHA-256、commit、license、NOTICE、单位、frame 和 generator |

## ✅ 请求 A3 的检查表

- [ ] 候选构型、Digital Skeleton、blocker ledger 和本 Gate 均冻结 raw SHA-256。
- [ ] 正式评审的五个核心角色读取了**同一最终 packet hash**；独立性例外已获人工接受。
- [ ] A 构型被描述为主候选，不是“最优构型”。
- [ ] `COMPETITION_DISPLAY_V0` 与 `CDS_12U_REFERENCE` exactly-one 已选择。
- [ ] `T_SM` 与所选 profile 一致；`T_SB` 单值且不得默认 `B=S`。
- [ ] 质量 exactly-one 与 B601 full-URDF 主表示获得 owner 签核。
- [ ] `E`、`G`、接触 datum 不再混用。
- [ ] 160/140 法兰冲突已在输入层裁决。
- [ ] 碎片前端环/后喷管 keepout 语义已回写 canonical source。
- [ ] B601 license/NOTICE/commit/hash 可随项目包携带。
- [ ] 若目标进入 A3，`T_ST/T_SD`、完整 `C` 旋转与 Interface 0/1 已闭合。
- [ ] E16、sim05 的历史证据隔离仍为零继承。
- [ ] 已取得独立人工 A3 授权。

## 🚫 当前 HOLD 项

当前至少以下输入仍未满足：`DB-BLK-001`、`002`、`008`、`009`、`010`（profile/input）、`012`（canonical harmonization）、`013`、`014`。最终 packet 也尚未由五个角色按同一 SHA-256 复审。

本 Gate 面向当前规划的 **CAD/URDF 一致性 A3 包**，因此把 `T_SB` 列为前置项。若未来人工授权把范围缩小为纯几何草图，必须建立独立 `A3-GEOMETRY-ONLY` Gate，并强制标记 `NO_DYNAMICS_USE`；不能用该窄范围绕过当前 A3 Gate。

因此当前裁决保持：

```text
CAD_ENTRY_BLOCKED_BY_EVIDENCE
```

这不是科学 FAIL，也不是构型 A 被否定；它表示设计合同已形成，但证据不足以授权正式 CAD/URDF 总装。
