# F3-P5E 控制交接包（结构 → 控制）

**文档编号：** `F3-P5E-CONTROL-HANDOFF-20260805`
**生成 UTC：** 2026-08-05
**状态：** `CONTROL_HANDOFF_PACKAGE_DELIVERED_WITH_NAMED_MODEL_LIMITS`
**前置：** F3-P5D 制造发布
**交接对象：** 控制系统（臂运动学/动力学/状态机）

---

## 1. 交接内容清单

| 交接项 | 来源 | 数值/文件 | 模型等级 |
|---|---|---|---|
| 6×6 刚度矩阵 | F3-P5A | `04_fea/08_matrices/F3_P5A_STIFFNESS_6X6_SI.csv` | 工程简化（解析近似，对角主导） |
| 6×6 柔度矩阵 | F3-P5A | `04_fea/08_matrices/F3_P5A_COMPLIANCE_6X6_SI.csv` | 工程简化（解析近似） |
| ROM 模态 | F3-P5A | 61.13 / 200.90 / 429.00 Hz（前 3 阶弹性） | 裸结构模态 |
| 接触模型 | F3-P5B | G07=10 N/mm、G08=5 N/mm（标定前名义值） | 弹簧等效 |
| HDRM 释放状态机 | F3-P5C | `07_configuration/F3_P5C_STATE_MACHINE_FROZEN.yaml` | 冻结 |
| ARM_MOTION_ENABLE 互锁 | F3-P5C | 仅运行态 true | 冻结 |
| B601 收拢等效惯量 | F3-P5A | 4.695556 kg，COM=[-1.708877, 0.255519, 0.246888] m | URDF 真值聚合 |
| 载荷桥/鞍座刚度 | F3-P5A | 平动 1.497/1.497/3.333 N/mm；转动 375216 N·mm/rad | 工程简化 |

## 2. 交接模型等级声明（必读）

1. **6×6 矩阵为解析近似**（对角主导、条件数 2.506e+05），不是从实体 FEM 位移场读取的完整耦合矩阵；控制模型中耦合项缺失，**禁止**用于依赖交叉耦合的控制律验证。
2. **模态为裸结构模态**（B601 质量未耦合连接）；收拢态真实模态待含 B601 惯量模型验证。ROM 前 3 阶仅用于控制带宽参考。
3. **接触刚度名义值**：G07/G08 台架标定后若偏差 >20%，必须更新本包并重跑 UL。
4. **本包不替代** sim_05/sim_12 等动力学真值；控制交接以 URDF（SHA-256 `408147DD...`）为质量/惯量真值。

## 3. 控制接口约定

### 3.1 状态机互锁（来自 F3_P5C_SM_FROZEN_V1）

```yaml
interlocks:
  ARM_MOTION_ENABLE: true only in OPERATIONAL states
  HDRM_RELEASE: requires ARM_MOTION_ENABLE=false AND STOW verified
  GRIPPER_CLOSE: requires ARM_MOTION_ENABLE=true AND grasp target confirmed
```

### 3.2 释放时序（HDRM 竞赛演示件）

| 参数 | 值 | 状态 |
|---|---|---|
| 释放行程 | 6 mm | COMPETITION_DEMONSTRATOR |
| 释放时间 | <0.5 s | COMPETITION_DEMONSTRATOR |
| 失效安全 | 弹簧保持 + 机械止挡 | FROZEN |
| 状态反馈 | 微动开关（到位/释放） | COMPETITION_DEMONSTRATOR |

### 3.3 接触丢失判据

- G07/G08 反力变号 = 接触丢失 → 触发 SAFE_STOP（F3-P5A 判据，P5C 状态机已含）。

## 4. 交接裁决

```text
F3_P5E_CONTROL_HANDOFF_PARTIAL_PASS_DELIVERED_WITH_NAMED_MODEL_LIMITS
```

遗留：完整耦合 6×6（实体 FEM 读取）、含 B601 惯量的收拢态模态、接触刚度实测标定。
