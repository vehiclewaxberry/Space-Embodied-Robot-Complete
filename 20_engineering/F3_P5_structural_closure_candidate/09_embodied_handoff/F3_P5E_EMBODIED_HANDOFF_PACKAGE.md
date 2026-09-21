# F3-P5E 具身交接包（结构 → 具身智能）

**文档编号：** `F3-P5E-EMBODIED-HANDOFF-20260805`
**生成 UTC：** 2026-08-05
**状态：** `EMBODIED_HANDOFF_PACKAGE_DELIVERED_WITH_NAMED_LIMITS`
**前置：** F3-P5E 控制交接
**交接对象：** 具身智能栈（观测/动作/仿真环境）

---

## 1. 交接内容清单

| 交接项 | 来源 | 数值/文件 | 状态 |
|---|---|---|---|
| 10-link HIFI 视觉 mesh | F3-P1 | `B601_HIFI_VISUAL_*.FCStd`（10 包，133 对象，2,727,847 mm³） | FROZEN |
| 坐标系帧表 | F3-P1/HAG-A4 | 8 个正式变换（正交、det=+1、右手系）+ 坐标帧寄存器 | FROZEN |
| 装配关系 | HAG-A | 139 matched / 0 unassigned / 256 accessory | CLOSED |
| 运动状态机 | F3-P5C | `07_configuration/F3_P5C_STATE_MACHINE_FROZEN.yaml` | FROZEN |
| 动作屏蔽表 | 本包 | 见 §4 | NEW |
| 负案例 | 本包 | 见 §5 | NEW |
| 静态 smoke test | 本包 | `F3_P5E_STATIC_SMOKE_TEST_SCRIPT.py` | NEW |

## 2. 观测 Schema

```yaml
observation_schema:
  camera_end: RGB+Depth, 60deg FOV, gripper_link mounted
  camera_wrist: RGB, 90deg FOV, link6 mounted (gripper close partial occlusion accepted)
  camera_base: RGB, 120deg FOV, base_link mounted
  joint_state: 6R joint angles + gripper open/close (URDF truth)
  hdrm_state: LOCKED / RELEASING / RELEASED (micro switch feedback)
  contact_state: G07/G08 contact boolean (reaction sign change = loss)
```

## 3. 动作 Schema

```yaml
action_schema:
  joint_position_cmd: 6-DOF arm + gripper (0/1)
  hdrm_release_cmd: single-shot with ARM_MOTION_ENABLE interlock
  high_level_skills: [dock, grasp, transport, assemble, retrieve]
  masking: see action mask table
```

## 4. 动作屏蔽表（Action Mask）

| 动作 | 允许状态 | 屏蔽状态 | 原因 |
|---|---|---|---|
| 臂运动（ARM_MOTION_ENABLE） | DEPLOYED_NOMINAL, SERVICE_*, RETRIEVED_NOMINAL | STOW, HDRM_RELEASE, SAFE_STOP | 收拢态碰撞/释放安全 |
| HDRM 释放 | STOW（锁定验证后） | 其他全部 | 预紧保持 |
| 夹爪闭合 | SERVICE_GRASP（目标确认后） | 其他全部 | 避免空抓/误抓 |
| 相机俯仰（若有） | 运行态 | STOW | 遮挡无意义 |

## 5. 负案例（训练/验证必测）

| ID | 场景 | 预期结果 |
|---|---|---|
| NEG-01 | 未确认 HDRM 已释放就下发臂运动 | 被互锁拒绝 |
| NEG-02 | STOW 状态下发展开动作 | 被互锁拒绝 |
| NEG-03 | G07 接触丢失 | SAFE_STOP |
| NEG-04 | G08 接触丢失 | SAFE_STOP |
| NEG-05 | 夹爪闭合时目标未确认 | 被互锁拒绝 |
| NEG-06 | Mode A 包络断言 | 被拒绝（NON_COMPLIANT_EXCLUDED） |
| NEG-07 | 引用飞行合格/AL 裕度 | 数据不可得，拒绝（TBD） |

## 6. 帧表摘要（8 正式变换）

| 帧 | 相对 | 类型 | 说明 |
|---|---|---|---|
| base_link → link1 … link6 | 顺序关节 | 6 个 | URDF 真值 |
| gripper_left | 01_Finger | P 分支 | HAG-A 映射 |
| gripper_right | 01_Finger001 | P 分支 | HAG-A 映射 |
| gripper_link | 末端 | 工具 | 含末端相机 |

**完整帧表：** `00_audit/F3_P5_COORDINATE_FRAME_REGISTER.yaml`

## 7. 静态 smoke test

`F3_P5E_STATIC_SMOKE_TEST_SCRIPT.py`（纯 Python，无依赖）校验：
1. 10 个 mesh 包路径存在
2. 帧表 YAML 可解析且含 8 帧
3. 状态机 YAML 含 12 状态 + 3 互锁
4. 6×6 矩阵 CSV 可读且对角项符号正确
5. 负案例表 ID 唯一
6. BOM 20 项
7. HOLD 寄存器状态机一致

## 8. 交接裁决

```text
F3_P5E_EMBODIED_HANDOFF_PARTIAL_PASS_DELIVERED_WITH_NAMED_LIMITS
```

遗留：实体 mesh 的 STL/GLB 导出（使用前由仿真环境转换）、真实相机标定参数（拍摄前由视觉组提供）。
