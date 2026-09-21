# F3-P5B 比赛样机接触垫定型（G07/G08）

**文档编号：** `F3-P5B-PAD-COMPETITION-SPECIFICATION-20260805`
**生成 UTC：** 2026-08-05
**状态：** `COMPETITION_GRADE_SELECTED_FLIGHT_PROCUREMENT_TBD`
**前置：** F3-P4C 候选矩阵 + F3-P5A（F3_P5A_PARTIAL_PASS_RESULTS_VALID_MARGIN_HOLD）
**HOLD 处置：** HOLD-07（contact_pad_specific_grade_matrix）→ 竞赛样机侧 `CLOSED_COMPETITION_GRADE`，飞行侧保持 `PROCUREMENT_TBD`

---

## 1. 定型原则

- **竞赛样机（演示/比赛原型）：** 选择**可采购、规格明确、与 F3-P5A FEA 弹簧参数一致**的具体规格族，作为本次比赛样机制造基线。
- **飞行侧：** 无供应商实测数据，`FLIGHT_REPRESENTATIVE_PAD = PROCUREMENT_TBD` 永久保留。
- **FEA 参数映射：** P5A 已用 G07=10 N/mm、G08=5 N/mm 弹簧完成 UL 表征；竞赛样机所选规格必须落在该刚度 ±20% 内，否则需重跑 UL。

## 2. 竞赛样机接触垫具体规格

### 2.1 G07（Aft）主承托接触垫 —— 碟形弹簧组 + PTFE 摩擦片

| 参数 | 竞赛样机规格 | 状态 |
|---|---|---|
| 结构 | 碟形弹簧（GB/T 1972 / DIN 2093 系列）2 片对合叠 + 3 mm PTFE 板 | `COMPETITION_GRADE` |
| 碟簧规格 | Ø50×Ø25.4×t1.5（单片面载荷 ~10 N/mm 等效，叠合后 ~20 N/mm，实际预紧后名义 10 N/mm） | `COMPETITION_GRADE_PENDING_CALIBRATION` |
| PTFE 板 | 3 mm 改性 PTFE（含 25% 玻纤，耐磨级），50×50 mm，Ra 0.8 | `COMPETITION_GRADE` |
| 接触面积 | 50×50 mm（与 P4C 一致） | `COMPETITION_GRADE` |
| 名义法向刚度 | 10 N/mm（FEA 映射值，待台架标定确认） | `COMPETITION_GRADE` |
| 切向刚度 | 5 N/mm（PTFE 摩擦面） | `COMPETITION_GRADE` |
| 预紧力 | 50 N / 预紧量 0.2 mm | `COMPETITION_GRADE` |
| 采购渠道 | 标准件市场（碟簧）+ 板材加工（PTFE） | `COMPETITION_GRADE` |
| 供应商数据 | 需采购时出具材料证书（批号、硬度、厚度公差） | `COMPETITION_GRADE` |
| 标定动作 | 装配后台架压缩标定，实测刚度写入 `F3_P5B_PAD_CALIBRATION_LOG` | `PENDING_CALIBRATION` |

### 2.2 G08（Fwd）腕部支撑接触垫 —— 硅橡胶垫

| 参数 | 竞赛样机规格 | 状态 |
|---|---|---|
| 材料 | 甲基乙烯基硅橡胶（VMQ），邵氏硬度 60A，2 mm 板 | `COMPETITION_GRADE` |
| 尺寸 | 30×30 mm，Ra 0.8 贴合面 | `COMPETITION_GRADE` |
| 名义法向刚度 | 5 N/mm（FEA 映射值，压缩模量 ~0.5 MPa 量级） | `COMPETITION_GRADE` |
| 切向刚度 | 2 N/mm | `COMPETITION_GRADE` |
| 预紧力 | 25 N / 预紧量 0.1 mm | `COMPETITION_GRADE` |
| 安装 | 机械卡扣 + 背胶（双保险） | `COMPETITION_GRADE` |
| 标定动作 | 装配后台架压缩标定，实测刚度写入 `F3_P5B_PAD_CALIBRATION_LOG` | `PENDING_CALIBRATION` |

## 3. FEA 参数映射表（P5A ↔ 竞赛样机）

| FEA 参数（P5A 已用） | G07 竞赛规格 | G08 竞赛规格 | 一致性 |
|---|---|---|---|
| 弹簧刚度 N/mm | 10（碟簧组，标定后修正） | 5（硅橡胶，标定后修正） | 名义一致，标定后重查 |
| 弹簧方向 | +Z（法向承托） | +Z（法向承托） | 一致 |
| 接触丢失判据 | 反力变号即接触丢失 | 反力变号即接触丢失 | 一致 |
| 阻尼 | 无（碟簧） | 高（硅橡胶） | 一致 |

**标定规则：** 若台架实测刚度偏离名义值 > ±20%，必须重跑对应 UL 工况并更新 6×6 矩阵（F3-P5A 裁决随之升级）。

## 4. 候选矩阵收口

从 P4C 九项候选收口为：

| 位 | 候选 | 竞赛样机选择 | 飞行候选（保持 TBD） |
|---|---|---|---|
| G07 | PTFE / 碟形弹簧 | **碟形弹簧 + PTFE 摩擦片** | PTFE 或碟簧（数据待定） |
| G08 | PTFE / 硅橡胶 | **硅橡胶（60A）** | PTFE 或硅橡胶（数据待定） |

## 5. 边界声明

1. 竞赛样机规格**不构成**飞行选材结论。
2. 未经台架标定，刚度值仅为设计名义值。
3. 供应商具体品牌/批号由采购环节确定并留痕，本 Gate 只冻结规格族与参数。
