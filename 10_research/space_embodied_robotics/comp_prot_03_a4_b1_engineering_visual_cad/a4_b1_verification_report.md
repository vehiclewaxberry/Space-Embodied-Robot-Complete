# A4-B1 Engineering Visual CAD 验收报告

_核验日期：2026-07-23；本报告是工程视觉 CAD 验收，不是科学 Gate。_

## 裁决

`A4_ENGINEERING_VISUAL_COMPLETE_WITH_PHYSICAL_LIMITATIONS`

本裁决仅说明：独立的 V1.0 工程视觉数字样机、组件语义、来源链、原生可重开性和评审证据已经闭合。它不证明结构强度、动力学正确性、可达性、全局无碰撞、抓取可行性、自治控制、VLA、制造或飞行资格。

## 交付规模

| 对象 | 数量 | 核验状态 |
|---|---:|---|
| SOLIDWORKS 原生文件 | 32 | `32/32 HASH_MATCH` |
| 零件 | 24 | 原生重开与重建通过 |
| 装配体 | 8 | 引用均可解析 |
| 原生检查 | 247 | `247/247 PASS` |
| 原生评审视图 | 12 | `12/12 HASH_MATCH` |
| 带注释评审图 | 12 | `12/12 HASH_MATCH`，且哈希互异 |
| 文档清单 | 32 | object ID 全局唯一 |
| 属性记录 | 1,750 | 可导出、可追溯 |
| 特征记录 | 796 | 包含纵梁、框环、舱段板和 frame 证据 |
| 装配组件记录 | 52 | source path 与 parent closure 通过 |
| 最终证据封存记录 | 43 | `43/43 HASH_MATCH` |

## 原生工程视觉检查

| 检查域 | 结果 | 证据 |
|---|---:|---|
| 文件重开、重建、引用解析 | `PASS` | `evidence/native_inspection.json` |
| 32 个文件 SHA-256 | `32/32` | `evidence/native_component_manifest.csv` |
| 唯一 object ID 与 parent closure | `PASS` | `evidence/inventory_validation.json` |
| 4 个纵向构件的具名特征 | `PASS` | `evidence/native_feature_inventory.csv` |
| 4 道横向框环 | `PASS` | `transverse_frame_ring_count=4` |
| 三舱边界设备板 | `PASS` | 两个具名 boundary-deck 特征 |
| `S/M/A0` 主 frame | `PASS` | feature inventory |
| B601 10-link/9-joint 拓扑 | `PASS` | accepted URDF 与 native inspection |
| 10 个 link 的 q=0 变换 | `10/10 PASS` | 最大绝对误差不超过 `2.2204460492503131E-16` |
| 10 份 STL 与 1 份 URDF 源哈希 | `11/11 PASS` | native inspection + document inventory |
| adapter 与 B601 的 `T_SM` | `2/2 PASS` | 最大绝对误差 `0` |
| vendor STEP 排除 | `PASS` | V1.0 树内无 STEP；属性均为 `FALSE` |
| target 从 active assembly 排除 | `PASS` | top property 与组件清单 |
| physical TCP / `T_SB` | `UNKNOWN_DISABLED` | top/B601 属性检查 |
| CAD 质量权威 | `FALSE` | `MASS_CONTRIBUTION=FALSE_CAD_VISUAL_ONLY` |

语义说明：

- Sensor 与 `E_virtual` 的原生文件均为零实体参考。SOLIDWORKS 模板可能仍导出默认材料名和“质量 0.00”字段；它们不构成有效硬件、BOM、材料、质量或制造权威。
- 独立 target scene 中存在 target proxy。`TARGET_INCLUDED=FALSE` 的含义是“未纳入 active engineering/operational assembly”，不是“独立场景没有目标”。
- target scene 的两个组件分别相对场景坐标系静态固定；没有相互 mate、contact 或 rigid-lock。

最终证据 seal manifest 的 SHA-256 为：

`dce2b66ac9f60a32329388c4579fec8d7174b7be3c1dfc60dccc716c7a8969f0`

## 冻结边界复核

| 边界 | 结果 |
|---|---:|
| A3 原生 CAD manifest | `20/20 HASH_MATCH` |
| A3 自动化 manifest | `6/6 HASH_MATCH` |
| A0/A1 登记 Gate JSON | `15/15 HASH_MATCH` |
| `30_simulation/` tracked diff | `0` |
| `40_evidence/` tracked diff | `0` |
| `20_engineering/config/geometry/` tracked diff | `0` |
| accepted B601 URDF tracked diff | `0` |

工作树在本阶段前已经非干净；以上“0”只说明具名冻结边界没有 tracked/staged diff，不等价于整个仓库 clean。A4-B1 文件当前未暂存、未提交。

## 静态干涉：负结果

原生检查仅在具名状态 `DEPLOYED_REFERENCE_Q0` 下记录静态干涉，数量为 10。其正确解释是：

> `NEGATIVE_RESULT / COLLISION_SAFETY_BLOCKED`

该结果不能外推为全工作空间、运动过程、抓取过程或安全控制结论。A4-CAD-13 的通过仅表示“检查范围和负结果被准确记录”，不表示“干涉检查通过”。

## 恢复链

构建曾经历早期失败和一次外层工具超时。最终资产通过受控续建、SOLIDWORKS 文档释放后哈希终结、独立原生检查、inventory 导出及证据封存完成。历史 `builder_failure.log` 和 `_failed_builds/A4_B1_attempt_*` 被保留，不应删除或改写为一次性成功。

## 退出边界

- `DYNAMICS_AUTHORITY_NOT_GRANTED`
- `COLLISION_SAFETY_BLOCKED`
- `A5_NOT_AUTHORIZED`
- `GIT_ANCHOR_NOT_CREATED`

下一阶段只有在新的人工 Gate 下，才能讨论真实传感器、physical TCP、接触、质量/惯量、URDF round-trip、工作空间、动力学、控制或仿真。
