# F3-P3 T_SM 双轨裁决报告

**文档编号：** `F3-P3-T-SM-DUAL-TRACK-20260805`
**生成 UTC：** 2026-08-05
**状态：** `DUAL_TRACK_RETAINED_MODE_A_B`
**前置：** F3-P3 GUI 见证 PASS

---

## 1. T_SM 双轨冲突现状

| 轨道 | 值 | 来源 | 状态 |
|---|---|---|---|
| **动力学轨** | t_SM = [185.25, 0, 0] mm + R_y(+90°) | `coordinate_frame_definition_v0.md` §3.1 | FROZEN |
| **显示轨** | MOUNT_FACE_X = 198 mm | V22_NATIVE01_PHASE1_REPORT.md §4.3 | CONFLICT |

**冲突：** 动力学轨 185.25 mm 会使 12 mm 适配板落在 X[173.25, 185.25]，与前端框（175..183）互穿。显示轨 198 mm 是为避免此互穿而调整的工程显示值。

---

## 2. 裁决：保留互斥 Mode A / Mode B 分支

在没有上级运载器或部署器 ICD 的情况下，**不能把两个互斥包络混进同一个顶装**。因此保留两条互斥分支：

### Mode A：Deployer-Constrained（部署器约束）

- **包络：** 226.3 × 226.3 × 366 mm（标准 12U 部署器包络）
- **T_SM：** 显示轨 198 mm（避免适配板与前端框互穿）
- **约束：** 严格符合部署器几何限制
- **C5 翼板超宽 12 mm：** **不可接受**（超出 226.3 mm 宽度限制）

### Mode B：External Service Module（外部服务模块）

- **包络：** 340.5 × 226.3 × 226.3 mm（项目冻结显示 profile，NON_FLIGHT_DISPLAY_ONLY）
- **T_SM：** 动力学轨 185.25 mm（保持动力学一致性）
- **约束：** 不受标准 12U 部署器限制，但需自定义部署方案
- **C5 翼板超宽 12 mm：** **可接受**（Mode B 包络更宽）

---

## 3. 共同元素与分支差异

### 共同元素（两条分支共享）

- 航天器本体（主结构、甲板、面板）
- B601 10-link HIFI 可运动装配
- 基座适配器与载荷桥（8 件）
- G07/G08 收拢支撑
- HDRM 功能包络
- 运动状态（Q0/STOW/DEPLOYED_NOMINAL/SERVICE）

### 分支差异

| 项 | Mode A | Mode B |
|---|---|---|
| T_SM | 198 mm | 185.25 mm |
| 包络宽度 | 226.3 mm | 340.5 mm |
| C5 翼板超宽 | 不可接受 | 可接受 |
| 部署器兼容性 | 标准 12U | 自定义 |
| 收拢态 Z 上限 | 366 mm | 226.3 mm（高度更严格） |

---

## 4. 顶层装配分支策略

**禁止：** 把 Mode B 的空间优势用于宣称 Mode A 通过。

**策略：**
1. 建立两个独立的顶层装配分支：
   - `SPACE_EMBODIED_ROBOT_TOP_INTEGRATION_F3P3_MODE_A.FCStd`
   - `SPACE_EMBODIED_ROBOT_TOP_INTEGRATION_F3P3_MODE_B.FCStd`
2. 每个分支使用自己的 T_SM 和包络
3. 共同元素共享，分支差异独立评价
4. C5 翼板超宽 12 mm 在 Mode A 中标记为 `NON_COMPLIANT`，在 Mode B 中标记为 `ACCEPTABLE`

---

## 5. 裁决结果

```text
DUAL_TRACK_RETAINED_MODE_A_B
```

**理由：**
- 没有上级运载器或部署器 ICD，无法单一路线裁决
- 两个互斥包络不能混进同一个顶装
- 保留两条分支，等待后续人工裁决或外部 ICD

**下一步：** C5 翼板超宽 12 mm 候选处置（三选一）。
