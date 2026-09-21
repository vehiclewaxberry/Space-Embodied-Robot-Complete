# 数字机械主机 G0 执行计划

_COMP-PROT-03-A3-G0-EVIDENCE-CLOSURE，2026-07-23_

---

> `STATUS: APPROVED_SCOPE_EXECUTION`<br>
> `SCIENTIFIC_GATE: false`<br>
> `CAD_URDF_SIMULATION_AUTHORIZED: false`

## 🎯 研究问题

在不生成 CAD、URDF 或仿真资产的前提下，能否把现有 12U+B601 候选的几何、质量归属、坐标系、机械语义和来源证据收敛为一份可供后续 SolidWorks Master Skeleton 消费的单一输入合同？

本阶段不验证结构强度、干涉、可达性、任务可行性或飞行合规性。

## 📋 批准依据

- 用户提供的阶段说明明确批准 `COMP-PROT-03-A3-G0-EVIDENCE-CLOSURE`
- 用户当前命令为“执行数字主机构建”
- 本计划将“数字主机构建”解释为 **Digital Mechanical Host v0.1 的预 CAD 合同构建**
- 原始批准文本记录见 [批准范围记录](./approval_scope_record.md)

## 📦 计划交付

1. 建立数字机械主机主记录与 JSON Schema
2. 建立质量所有权注册表
3. 建立 Frame Tree v2 候选覆盖层
4. 选择唯一 competition geometry profile，并锁定对应 `T_SM`
5. 建立 SolidWorks Master Skeleton 输入表
6. 建立机械接口与任务语义注册表
7. 建立 B601 许可证与来源随行包
8. 对 15 个 DB blocker 给出本阶段处置矩阵
9. 建立独立的 `A3-GEOMETRY-ONLY` 请求闸门

## 🔐 边界

允许新增：

- `10_research/space_embodied_robotics/comp_prot_03_a3_g0_evidence_closure/`
- `80_third_party/notices/rebot_b601/`

禁止修改：

- `20_engineering/config/geometry/`
- `20_engineering/cad/`
- `30_simulation/`
- `40_evidence/`
- 所有现有机器 Gate JSON

禁止执行：

- SolidWorks 建模或 CAD 生成
- URDF 生成或改写
- 动力学、控制、Basilisk、ROS、Isaac、RL 或 VLA

## ✅ 验收条件

- 所有新增 YAML 和 JSON 可解析
- 主机实例通过 JSON Schema
- 现有 A2/A3-G0 方法包源哈希一致
- 第三方许可证全文可随项目包携带
- 质量 exactly-one 选择无双计
- `COMPETITION_DISPLAY_V0` 与 `CDS_12U_REFERENCE` 恰好选择一个
- `T_SM` 与所选 profile 一致
- `T_SB`、physical TCP 和 aggregate CoM/inertia 未被猜测
- 冻结目录 tracked diff 为零
- 新目录中 CAD/URDF/STEP/STL/SLDPRT/SLDASM 文件数为零

## 🔄 回滚

本阶段只新增文件。若验证失败，回滚范围仅为本计划列出的两个新增目录；不得触碰用户已有改动或冻结资产。

## 🏁 停止点

即使所有 G0 文档检查通过，最强裁决也只能是：

```text
A3_GEOMETRY_ONLY_ENTRY_REVIEW_READY_TO_REQUEST
A3_GEOMETRY_ONLY_AUTHORIZED=false
```

完整 CAD/URDF 准入继续受 `T_SB`、physical TCP、canonical target semantics、CAD 干涉与集成模型证据约束。
