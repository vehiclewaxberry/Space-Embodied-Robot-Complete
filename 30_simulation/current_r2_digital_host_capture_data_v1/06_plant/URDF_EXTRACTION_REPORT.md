# URDF 提取报告（accepted B601 → prebind plant）

来源：`20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf`
（SHA-256 `1bc2b748…e471c164`，11321 B；指定文档 `05_ACCEPTED_B601_URDF_REF.yaml`；MODIFICATION_FORBIDDEN）。
提取器：`src/dh_v1/urdf_extract.py`（XML 直读，零手工重录）；机器报告：`11_verification/URDF_TOPOLOGY_REPORT.json`。

## 拓扑（与合同"10 links / 9 joints = 6R + 1 fixed + 2 independent P"逐项吻合）

| 项 | 提取值 | 校验 |
|---|---|---|
| links | 10（base_link, link1–6, gripper_link, gripper_left, gripper_right） | S01 ✓ |
| joints | 9 = revolute×6（joint1–6）+ fixed×1（gripper_joint）+ prismatic×2（gripper_joint1/2，独立） | S01 ✓ |
| root | base_link；树连通无环、无双亲 | S01 ✓ + 负控 |
| inertial | 10/10 link 含质量+全张量；总质量 4.695600 kg ≈ 账本 4.695555949 kg（BUDGETED） | S01 ✓（±5e-4） |
| limits | 8 个可动关节均含 lower/upper/effort/velocity | S01 ✓ |

## 语义处理

- `<inertia>` 关于 CoM、表达于 inertial-origin 系 → 提取时经 `R·I·R^T` 旋入 link 系（本文件 rpy 全零，旋转为恒等）。
- 轴向量归一化；`continuous` 视作 revolute（本文件无）。
- 独立 P 指验证：gripper_joint1 仅动 gripper_left（0.05 m），gripper_right 位移 < 1e-12 m。
- joint6 轴不变性：gripper_link 原点在 joint6 轴上（转动 1.1 rad 位移 < 1e-12 m）。

## 已知边界（不升级）

- 惯量集为 HYBRID（D-5-final）：fixend 惯量 + with_gripper 夹爪质量；**物理称重 pending**（confidence medium）。
- gripper prismatic `velocity=15.0` 为 UNVALIDATED_AUTO_EXPORTED_MODEL_LIMIT（m/s 口径裁决），执行器速度权威 = HOLD。
- 本报告只描述提取正确性，不构成运动/接触/任务授权。
