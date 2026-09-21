# F3-P5B 比赛演示 HDRM 定型

**文档编号：** `F3-P5B-HDRM-COMPETITION-DEMONSTRATOR-20260805`
**生成 UTC：** 2026-08-05
**状态：** `COMPETITION_DEMONSTRATOR_CONFIGURED_FLIGHT_REPRESENTATIVE_PROCUREMENT_TBD`
**前置：** F3-P4D HDRM 结构深化（功能接口全闭合）
**HOLD 处置：** HOLD-08（hdrm_specific_model_matrix）→ 竞赛演示侧 `CLOSED_COMPETITION_DEMONSTRATOR`，飞行侧保持 `PROCUREMENT_TBD`

---

## 1. 定型原则

- **竞赛演示 HDRM：** 在 P4D 功能包络（行程 ≥5 mm、力 ≥50 N、响应 <1 s、失效安全）内选择**机电一体演示配置**，作为比赛样机装配基线。
- **飞行代表 HDRM：** `FLIGHT_REPRESENTATIVE_HDRM = PROCUREMENT_TBD` 永久保留（无商业航天级型号数据）。
- **接口不变：** P4D 已冻结的 13 项安装接口（法兰/PCD/螺栓/预紧/释放/止挡/传感器/电连接/keepout/拆装/故障/手动解锁）**全部保持**，型号选择只替换功能包络实例。

## 2. 竞赛演示 HDRM 配置（选型矩阵）

| 选项 | 类型 | 行程 | 力 | 响应 | 失效安全 | 成本 | 评分 |
|---|---|---|---|---|---|---|---|
| **A. 电磁锁 + 压缩弹簧** | 机电 | 6 mm | 60 N | <0.5 s | 弹簧保持（断电释放或锁定） | 低 | **优** |
| B. 形状记忆合金（SMA）释放 | 机电 | 5 mm | 55 N | <2 s | 需加热，恢复慢 | 中 | 中 |
| C. 火工分离 | 火工 | >10 mm | 高 | <0.1 s | 一次性 | 高 | 良（演示危险性高） |
| D. 电机丝杠 | 机电 | 5 mm | 80 N | <1 s | 需自锁机构 | 中 | 良 |

**竞赛演示选择：选项 A —— 电磁锁 + 压缩弹簧**

理由：
1. 可重复释放（>100 次），符合演示任务需求
2. 失效安全：断电时由弹簧保持锁定状态（机械止挡兜底），符合 P4D 冻结的失效模式
3. 成本低、可采购、可在地面反复演示
4. 响应 <0.5 s 满足 <1 s 要求

## 3. 竞赛演示 HDRM 规格（选项 A 实例化）

| 参数 | 竞赛演示规格 | 状态 |
|---|---|---|
| 类型 | 电磁锁（保持型电磁铁 + 压缩弹簧） | `COMPETITION_DEMONSTRATOR` |
| 保持力 | ≥ 50 N（电磁保持，断电保持） | `COMPETITION_DEMONSTRATOR` |
| 释放方式 | 通电消磁 + 弹簧推出，行程 6 mm | `COMPETITION_DEMONSTRATOR` |
| 释放时间 | < 0.5 s | `COMPETITION_DEMONSTRATOR` |
| 弹簧 | 压缩弹簧 Ø8×Ø1.2×20 mm，刚度 10 N/mm（与 P4D 一致） | `COMPETITION_DEMONSTRATOR` |
| 电源 | 28 V DC / ≤1 A（P4D 电连接接口一致） | `COMPETITION_DEMONSTRATOR` |
| 状态指示 | 微动开关（到位/释放），±0.1 mm 重复精度 | `COMPETITION_DEMONSTRATOR` |
| 控制接口 | 单路继电器 + 状态反馈（TTL 电平） | `COMPETITION_DEMONSTRATOR` |
| 寿命 | > 1000 次（演示要求） | `COMPETITION_DEMONSTRATOR` |
| 供应商数据 | 采购时出具电磁铁规格书（保持力-电流曲线） | `COMPETITION_GRADE` |
| 飞行代表 | `PROCUREMENT_TBD`（不允许引用演示型号为飞行结论） | FROZEN |

## 4. 与 P4D 接口一致性核对

| P4D 冻结接口 | 竞赛演示规格 | 一致 |
|---|---|---|
| 安装法兰 60×60×10 mm / Ø50 PCD / 4×M5 | 保持 | ✅ |
| 预紧 +X 50 N / 0.2 mm | 保持 | ✅ |
| 释放行程 5 mm（≥） | 6 mm | ✅ |
| 释放方向 -X | 保持 | ✅ |
| 机械止挡 / 碟簧缓冲 | 保持 | ✅ |
| 传感器接口（机械/接近开关） | 微动开关 | ✅ |
| 电连接 MIL-DTL-38999 4 芯 | 保持 | ✅ |
| 残留 keepout <2 mm | 电磁锁本体收回 ≤1 mm | ✅ |
| 拆装 +Z | 保持 | ✅ |
| 故障释放方案 | 机械止挡 + 地面手动解锁 | ✅ |

## 5. 边界声明

1. 竞赛演示配置**不构成**飞行 HDRM 选型结论。
2. 电磁锁采购时需验证保持力-电流曲线与真空适应性（若演示环境为常压则无需真空验证）。
3. 飞行代表型号 `PROCUREMENT_TBD` 保持到获得商业航天级供应商数据。
