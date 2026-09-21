# Sim13 V2 Runtime Fail-Closed Backends（NC15/NC16/NC18/NC19/NC20）

本包按工作单 `20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_b/SIM13_BACKEND_WORK_ORDERS_V1.json`
实现 Sim13 缺失的五个后端，把 NC 注册表从 15/20 真实重跑到 **20/20**。
所有 Gate 均为 `review_status: PENDING_OWNER_REVIEW`、`next_stage_authorized: false`、
`release_credit: false`。UNKNOWN 永不为 PASS。

## 五个后端（sim13_v2_backends/）

- **NC15 `snapshot_receipt.py`**：action/context/12-gate 快照三元绑定回执（action hash、
  context hash、gate snapshot hash、nonce、trusted timestamp、expiry）。可信时钟为注入式
  接口（生产用宿主墙钟、测试用确定性钟，类别显式声明）；防重放为文件型单次消费 store，
  参照 unified_r2 run consumption 标记模式（`xb` 原子创建）。过期 →
  `SNAPSHOT_REJECTED_STALE`；重放 → `SNAPSHOT_REJECTED_NONCE_REPLAY`；均屏蔽为 canonical ABORT。
- **NC16 `capability.py`**：绑定 backend 源文件 SHA-256 的 capability token；
  `ShieldedBackendAdmission` 是运行时路径上的强制 shield-attestation 准入接口。
  无 attestation 的非 ABORT 后端直调 → `BACKEND_REJECTS_UNSHIELDED_NON_ABORT` → 屏蔽 ABORT。
- **NC18 `dynamics_backend.py`**：哈希锁定已发射 Unified R2 URDF（17191 B，
  `D84AA23C…CBDA`）与其执行回执，经 `sim13_v2.free_floating_dynamics` 树核 +
  零动量约化动力学（Schur 补 + Richardson 导数 + RK4）演化 8-DOF 关节、自由漂浮基座
  （位置/四元数/twist）与末端（gripper_link/left/right 质心）状态。仅改 task phase 而不
  改物理状态的假步 → `DYNAMICS_STATE_UPDATE_FAILURE_PHASE_ONLY`。名义推进动量残差 ~1e-19。
- **NC19 `contact_backend.py`**：绑定 `DESIGN_CONTACT_MODEL_V1`（BOUNDED_PROVISIONAL，
  哈希锁定）包络的权威窄相接触后端；窄相几何资产
  `assets/SIM13_V2_RELEASED_CONTACT_GEOMETRY_V1.json` 由
  `emit_released_contact_geometry_v1.py` 从 accepted URDF 夹爪关节 + 合同包络确定性派生
  （派生非实测）。法向力按合同 Hertz 族 `F=k·δ^1.5`；包络外/缺失参数 → UNKNOWN →
  屏蔽 ABORT。重叠几何但无接触状态更新的坏探测器 → `CONTACT_DETECTION_FAILURE`。
- **NC20 `feasibility_evaluator.py`**：哈希锁定 sim10（gate/summary/参数卡/anchor 源码
  四文件）与 sim12（gate/CSV 两文件）锚点：150 kg@3°/s → ω⁺=3.0633304945807067°/s
  `INFEASIBLE_RATE`；sim12 B_anchor 四策略全 INFEASIBLE、轮组角动量裕度为负（抓后不可
  稳定）。签发 action-bound 回执（requested action hash + feasibility verdict）；无
  FEASIBILITY_PASS 的非 ABORT 150kg 请求 → shield 执行 canonical ABORT，
  理由 `MISSION_VETO_INFEASIBLE_RATE`。

`runtime_gate_adapter.py` 把 NC15/NC16/NC20 串成唯一高层准入路径（receipt → capability →
feasibility 依次 fail-closed）。

## 产物

- `contracts/`：三份 receipt/token schema（英文、严格 JSON）。
- `evidence/`：5 项后端 NC 证据、三份后端验证回执、20/20 全注册表证据、接口发射回执。
- `results/`：三个后端 Gate（RUNTIME_FAIL_CLOSED / DYNAMICS_BACKEND / CONTACT_GRASP V2）、
  `SIM13_20_OF_20_GATE_V1.json` 检查点、本包总验证输出。
- `../interfaces/MECH_RL_SYSTEM_INTERFACE_V2.yaml`：按边界合同发射的接口实例
  （6 个核心 artifact + 9 个 GATE artifact 槽；authority 当前值如实：owner 未接受、
  Route-C 未处置，consumer load / contact grasp 均未授权）。
- `tests/`：61 项 pytest（每个后端：schema、名义正向、malformed、missing source、
  stale hash、UNKNOWN/fail-closed、确定性回放、只读/no-write）。

## 复现

```powershell
python -B emit_released_contact_geometry_v1.py
python -B run_negative_controls_backends_v2.py
python -B run_full_registry_intake_v2.py
python -B emit_mech_rl_system_interface_v2.py
python -B -m pytest -q -p no:cacheprovider
python -B validate_backends_v2.py
```

机器裁决只认 `results/SIM13_20_OF_20_GATE_V1.json`（20/20 检查点）与
`results/SIM13_V2_BACKENDS_PACKAGE_VALIDATION_V1.json`（V01–V10 全过）。

## 历史保留与事件披露

- 15/20 历史证据（`../evidence/SIM13_V2_NEGATIVE_CONTROLS_PREBIND_V1.json` 等五个文件）
  只读保留，本包总验证器 V02 钉死其字节与 SHA-256。
- **披露（FAIL_DOCUMENTED 级）**：本包探索阶段曾按上游 README 指示运行
  `python -B ../validate_prebind_v2.py`。该脚本为再生成式验证器，因 unified URDF 已于
  2026-08-25 发射（P25 由 true 变 false），重写了四个 prebind 文件（gate、validation、
  receipt、csv）。发现后已按记录哈希恢复：validation 与 csv 经记录的 SHA-256 逐字节
  验证恢复；gate 按会话开始时的完整内容恢复（2282 B 与 2026-08-24 冻结一致）；
  receipt 由同一确定性模板以全部原始值重构（1706 B）。15/20 负控证据本体
  （C9DAEC35…）自始至终未被触碰。此后未再运行该再生成式脚本。

## 明确边界

- HMAC 密钥为公开非秘密常量：本包的防篡改语义是协作式进程内 fail-closed 边界，
  不声明对同进程恶意攻击者的密码学安全。
- 可信时钟是宿主墙钟或注入钟，类别在每张回执上显式声明；不声明硬件信任根。
- MECHANICAL_TO_EMBODIED_HANDOFF_GATE_V2 的 G12 harness 项依赖机械 Route-C 线（A1 工作区），
  不在本包范围，已如实登记为 `NOT_IN_A3_SCOPE_DEPENDS_ON_MECHANICAL_ROUTE_C_LINE`，未伪造。
- 本包不授权训练、接触抓取、硬件运动、飞行或生产用途；12 门 authority 快照中
  harness/binding/owner 项仍为 FAIL/UNKNOWN，生产非 ABORT 仍被屏蔽。
