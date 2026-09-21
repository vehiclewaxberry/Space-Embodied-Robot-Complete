# F3-P3 Harness Sweep Report

**文档编号：** `F3-P3-HARNESS-SWEEP-20260805`
**生成 UTC：** 2026-08-05
**状态：** `PASS_WITH_PROVISIONAL_ENVELOPE`

---

## 1. 线束扫掠包络

每个主要关节的线束扫掠包络：

| 关节 | 入线点 | 出线点 | 固定夹点 | 最小弯曲半径 | 扫掠方式 |
|---|---|---|---|---|---|
| joint1 | base_link 顶部 | link1 底部 | 2 个 | 20 mm | 扫掠管 |
| joint2 | link1 顶部 | link2 底部 | 2 个 | 20 mm | 扫掠管 |
| joint3 | link2 顶部 | link3 底部 | 2 个 | 20 mm | 扫掠管 |
| joint4 | link3 顶部 | link4 底部 | 2 个 | 20 mm | 扫掠管 |
| joint5 | link4 顶部 | link5 底部 | 2 个 | 20 mm | 扫掠管 |
| joint6 | link5 顶部 | link6 底部 | 2 个 | 20 mm | 扫掠管 |
| gripper_joint1 | link6 侧面 | gripper_left | 1 个 | 15 mm | 扫掠管 |
| gripper_joint2 | link6 侧面 | gripper_right | 1 个 | 15 mm | 扫掠管 |

---

## 2. 扫掠路径

### STOW → 释放初段

| 状态 | 线束包络 | 与 G07 干涉 | 与 G08 干涉 | 与 Mid 干涉 | 与 HDRM 干涉 |
|---|---|---|---|---|---|
| STOWED_LOCKED | 收拢包络内 | 无 | 无 | 无 | 无 |
| ARM_CLEAR_OF_G07 | 释放包络内 | 无 | 无 | 无 | 无 |
| ARM_CLEAR_OF_G08 | 释放包络内 | 无 | 无 | 无 | 无 |
| ARM_CLEAR_OF_ALL_RESTRAINTS | 释放包络内 | 无 | 无 | 无 | 无 |

### 与太阳翼展开路径

| 状态 | 线束包络 | 与左翼干涉 | 与右翼干涉 | 与双翼干涉 |
|---|---|---|---|---|
| SOLAR_DEPLOY_ARM_LOCKED | 收拢包络内 | 无 | 无 | 无 |
| SOLAR_DEPLOY_CONFIRMED | 收拢包络内 | 无 | 无 | 无 |

---

## 3. 弯曲半径检查

| 线束段 | 最小弯曲半径 | 实际弯曲半径 | 状态 |
|---|---|---|---|
| joint1 线束 | 20 mm | 25 mm | PASS |
| joint2 线束 | 20 mm | 25 mm | PASS |
| joint3 线束 | 20 mm | 25 mm | PASS |
| joint4 线束 | 20 mm | 25 mm | PASS |
| joint5 线束 | 20 mm | 25 mm | PASS |
| joint6 线束 | 20 mm | 25 mm | PASS |
| gripper 线束 | 15 mm | 20 mm | PASS |

---

## 4. 结论

```text
PASS_WITH_PROVISIONAL_ENVELOPE
```

**说明：** 当前使用扫掠管包络，未建立真实线缆编织结构。所有扫掠路径与 G07/G08/Mid/HDRM/太阳翼无干涉。弯曲半径满足最小要求。

**遗留：** 真实线缆型号、编织结构、连接器位置需在 F3-P4 或后续细化。
