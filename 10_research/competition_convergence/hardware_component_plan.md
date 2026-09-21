# H0/H1/H2 Ground-Component Qualification Plan

> 日期：2026-07-20
> 角色：Agent H（ground-component qualification planning）
> 基线提交：`c7f09ab80580f5810d75253fd836d412aa862460`
> 计划状态：`FROZEN_PLAN_ONLY / NOT_EXECUTED`
> 当前硬件状态：`H0=NOT_STARTED · H1=NOT_STARTED · H2=NOT_STARTED`
> 证据优先级：Machine Gate JSON > raw evidence > tests > Git > reports
> 本文件只冻结后续资格化合同；**本轮没有连接、枚举、上电、解锁、驱动或移动任何设备，也没有生成 H0/H1/H2 实验工件。**

## 0. 当前真值与本计划的权限边界

### 0.1 当前可证明的真值

| 项目 | 2026-07-20 当前事实 | 证据 |
|---|---|---|
| Git | Agent H worktree 在 `codex/ground-components-h`，写本文件前 clean，HEAD=`c7f09ab...` | `git status --short`、`git rev-parse HEAD` |
| 地面链 | H0/H1/H2/H3 均未启动 | `10_research/README.md` L5、`10_research/research_state_v4.md`、`10_research/partner_requirement_closure/state_truth_report.md` |
| 授权 | `10_research/on_orbit_assembly/approvals/HAG-E.yaml` 不存在 | `Test-Path` 只读检查 |
| 实验目录 | `hardware/qualification/H0/`、`H1/`、`H2/` 均不存在 | `Test-Path` 与 `git ls-files` 只读检查 |
| B601 静态模型 | 仓库有 B601 6R 混合 URDF/几何 SSOT；它是建模证据，不是实机驱动、通信或安全资格证据 | `20_engineering/config/geometry/arm_b601_v1.yaml`、`20_engineering/cad/spacecraft_layout/arm_b601_v1/README.md` |
| 夹爪时序 | sim_11 使用 `T_c=20 ms` 占位并扫掠 5–100 ms；未实测 | `20_engineering/config/coupled_scene/scene_A2_capture.yaml`、sim_11 Gate |
| 控制/安全上游 | SAFE-00=`PASS` 但 `next_stage_authorized=false`；CTRL-01=`REPEAT`；CTRL-02 原始 `PASS` 但 review/provisional 边界仍在；Wave1=`WAVE1_REPEAT` | 对应冻结 `*_gate_check.json` |

与本计划相邻的冻结 Gate 已从当前 worktree 原始字节复核：

| Gate path | Machine truth | Raw SHA-256 |
|---|---|---|
| `30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json` | `SIM10_GATES_PASS` | `2a9024bb0f57f837e58161a0fa96660e2e237ec96ef096eba458cb0dcc4a19d4` |
| `30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json` | `SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS` | `5bba3112a704583fecb315419c1d73848bf72fe82f89b7a8fb104abb1ea0aa47` |
| `30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json` | `SIM12_PHASE1_GATES_PASS` | `e92ae9c2287149ff00234760cf0d3a53524fd59b71b7e93b2785e578aae91f5f` |
| `30_simulation/safety_00_runtime_gate/results/safety_00_gate_check.json` | `PASS`; `next_stage_authorized=false`; `review_status=PENDING_REVIEW` | `ff56929dd8352e447afdb8b7d17c5ef0b248883c66bc4f00c16c50c6f4c46eee` |
| `30_simulation/control_01_end_effector_tracking/results/control_01_gate_check.json` | `REPEAT`; `next_stage_authorized=false` | `3d32f78a7cc4bf57718efb1e4ddf70cab843c4b67173833ab4aa4971735baa8a` |
| `30_simulation/control_02_base_attitude/results/control_02_gate_check.json` | raw `PASS`; `review_status=PENDING_REVIEW`；仅作 PROVISIONAL-scope 解释 | `8d072eaeacbbdbb1bb7637434a0b5db77b6d37c42f706dc075950aa9b123a341` |
| `10_research/partner_requirement_closure/wave1_results/wave1_gate_check.json` | `WAVE1_REPEAT`; `next_wave_authorized=false` | `c8d631d68537c9edd9c3e55ec9456c5ac61474ef850e4ca6f280595de4429dae` |

仓库文字中的 `physical_hardware_match: true`、`vendor reBotArmController_ROS2`
或外部源代码路径只能说明设计意图/静态来源；在 H0 证据出现前，它们**不能**
证明本机上的实际设备身份、驱动版本、SDK、通信方式、串口、波特率、关节映射、
相机标定、急停、限位、encoder 或可运动状态。

### 0.2 当前机器状态

当前没有 H0/H1/H2 Gate JSON，因此不得合成一个“空 PASS”。报告层只能显示：

```text
H0: NOT_STARTED_BLOCKED_BY_MISSING_HAG_E
H1: NOT_STARTED_BLOCKED_BY_H0
H2: NOT_STARTED_BLOCKED_BY_H1_AND_ESTIMATOR_GATE
B601_MOTION: PROHIBITED
H3/HIL/VLA: NOT_AUTHORIZED
```

`NOT_STARTED` 不是 `PASS`、`REPEAT` 或 `BLOCKED` 的替身；只有真实执行并生成
相应 Gate JSON 后，才允许使用本文件第 7 节的阶段裁决词。

### 0.3 绝对运动门禁

任何 B601 运动命令的必要条件冻结为：

```text
B601_MOTION_ALLOWED :=
  HAG_E_VALID
  AND H0_PREMOTION_PASS
  AND APPROVED_MOTION_PLAN_HASH_MATCH
  AND DEVICE_BINDING_MATCH
  AND HUMAN_ENABLE_PRESENT
  AND ESTOP_ARMED
  AND SOFTWARE_LIMITS_LOADED
```

任一项为 `FALSE / UNKNOWN / MISSING / EXPIRED`，结果均为 `false`。因此：

- **HAG-E 生效前禁止 B601 上电运动、解锁、点动、回零、示教或轨迹回放。**
- H0 内部先做无运动的 H0-PRE 资格；只有
  `h0_premotion_gate_check.json.verdict=H0_PREMOTION_PASS` 后，才允许按已签名
  小范围、低速计划做 H0 本身的 encoder/e-stop/repeatability/`T_c` 资格动作。
- H0 最终 PASS 前禁止任何 H1/H2 任务动作；H1 PASS 前禁止 H2 动态台架试验。
- 任何脚本都不得自行置位 `HUMAN_ENABLE_PRESENT`，不得远程复位急停，不得在
  通信丢失后自动恢复运动。

## 1. 总体阶段与单向授权

```text
PLAN_ONLY
  → HAG-E + frozen contracts
  → H0-PRE read-only inventory and premotion safety gate
  → H0 limited qualification motion
  → H0 machine gate + STOP
  → separate human authorization
  → H1 fixed-base prerecorded low-speed execution
  → H1 machine gate + STOP
  → separate human authorization
  → H2 cooperative-marker sensing qualification
  → H2 machine gate + STOP
```

每阶段都执行：

`STATE TRUTH → CONTRACT FREEZE → BASELINE → MINIMAL IMPLEMENTATION →
DESIGNED EXPERIMENT → MACHINE GATE → RED TEAM → EVIDENCE FREEZE → STOP`

阶段 PASS 只证明该阶段的限定能力，不自动授权下一阶段。每个最终 Gate 固定
`next_stage_authorized=false`；下一阶段还必须有新的、阶段绑定的人类授权记录。

## 2. 共用数据、时钟和证据合同

### 2.1 未来 owned paths

真实执行获批后，Agent H 只可写：

```text
hardware/qualification/common/
hardware/qualification/H0/
hardware/qualification/H1/
hardware/qualification/H2/
```

本计划不创建这些目录。以下路径始终只读/禁止修改：

- `30_simulation/sim_01_*` 至 `30_simulation/sim_12_*`
- `30_simulation/safety_00_runtime_gate/`
- `30_simulation/control_01_end_effector_tracking/`
- `30_simulation/control_02_base_attitude/`
- `e15_*`、`30_simulation/e16_sync_capture/`
- `20_engineering/config/geometry/`
- `20_engineering/config/coupled_scene/`
- `10_research/partner_requirement_closure/wave1_results/`
- `10_research/partner_requirement_closure/wave1_repeat/`
- `10_research/on_orbit_assembly/` 的现有规划、Task Card、registry 与 draft
- 所有现有 `*_gate_check.json` 与 threshold registry

H0 的 `T_c`、H1 的执行器/接口实测只生成 **rerun trigger**；不得在本分支
回填 `scene_A2_capture.yaml`、重写 sim_11 Gate 或删去 `PROVISIONAL`。

### 2.2 每个执行合同的必填头

未来三个 `h*_execution_contract.yaml` 必须使用同一头部字段：

```yaml
schema_version: ground-component-execution-contract-v1
stage: H0 | H1 | H2
task_id: <stable id>
approved_base_commit: <sha40>
source_worktree_clean: true
plan_path: 10_research/competition_convergence/hardware_component_plan.md
plan_sha256: <raw bytes sha256>
authorization:
  path: 10_research/on_orbit_assembly/approvals/HAG-E.yaml
  raw_sha256: <sha256>
  authorization_id: <id>
  issued_at_utc: <RFC3339>
  expires_at_utc: <RFC3339>
  authorized_stage: H0 | H1 | H2
  authorized_device_ids: []
  authorized_motion_plan_sha256: <sha256 or NONE>
safety:
  sop_path: <repo-relative path>
  sop_sha256: <sha256>
  operator_ack_id: <non-personal record id>
  observer_ack_id: <non-personal record id>
  estop_channel_ids: []
device_binding:
  arm_asset_id: <observed asset id>
  controller_serial: <observed value>
  camera_serials: []
  target_stage_asset_id: <observed value or NOT_APPLICABLE>
timebases:
  host_monotonic_clock: <clock id>
  controller_clock: <clock id or NOT_AVAILABLE>
  camera_clock: <clock id or NOT_APPLICABLE>
  ground_truth_clock: <clock id or NOT_APPLICABLE>
threshold_registry:
  path: <stage-specific frozen yaml>
  raw_sha256: <sha256>
required_trials: []
forbidden_actions: []
```

任何必填值仍为 `TBD`、空、猜测或无法追溯时，entry validator 必须拒绝启动。
阈值要在第一条实验记录之前冻结；本计划**不替设备手册、风险评估和预试验发明
安全数值**。

### 2.3 所有 raw record 的共用字段

JSON/CSV/YAML 记录至少携带：

| 字段 | 规则 |
|---|---|
| `schema_version` | 文件级固定版本，不允许静默升级 |
| `session_id`, `trial_id`, `record_id` | 全局唯一、稳定 |
| `stage`, `substage` | H0/H1/H2 与明确子阶段 |
| `asset_id`, `device_serial` | 来自现场观察，不从文件名推断 |
| `host_timestamp_utc` | RFC3339，仅用于审计顺序 |
| `host_monotonic_ns` | 延迟/间隔计算的首选时钟 |
| `device_timestamp_raw`, `device_clock_id` | 原值保存；无时钟写 `NOT_AVAILABLE` |
| `frame_id`, `parent_frame_id` | 位姿/运动记录必填 |
| `value`, `unit` | SI 或明确原始单位；转换前后均留存 |
| `status` | `PASS / FAIL / UNKNOWN / NOT_APPLICABLE` |
| `reason_code` | 注册词表；禁止自由文本替换裁决 |
| `provisional_fields` | 列表；空列表也须显式 |
| `raw_ref` | 原始日志/图像/视频/控制器导出的相对路径 |
| `contract_sha256`, `authorization_sha256` | 每条试验绑定 |
| `software_build_sha256` | 采集/解析器二进制或源码包 hash |

### 2.4 Evidence manifest schema

每阶段的 `h*_evidence_manifest.json` 必须包含：

```json
{
  "schema_version": "ground-component-evidence-manifest-v1",
  "stage": "H0|H1|H2",
  "source_commit": "<sha40>",
  "contract_path": "<path>",
  "contract_sha256": "<sha256>",
  "authorization_path": "<path>",
  "authorization_sha256": "<sha256>",
  "device_binding_sha256": "<sha256>",
  "artifacts": [
    {
      "path": "<repo-relative path>",
      "role": "RAW|CALIBRATION|COMMAND|TELEMETRY|DERIVED|GATE_INPUT",
      "schema_version": "<version>",
      "sha256": "<raw bytes sha256>",
      "size_bytes": 0,
      "record_count": 0,
      "status_counts": {"PASS": 0, "FAIL": 0, "UNKNOWN": 0, "NOT_APPLICABLE": 0},
      "provisional_fields": [],
      "generated_by": "<tool + version/hash>"
    }
  ],
  "negative_results_preserved": true,
  "missing_required_artifacts": [],
  "unexpected_artifacts": []
}
```

manifest 只登记 immutable raw evidence 和由其确定性生成的派生表。失败试验不得
删除、重编号或被“最佳若干次”替换。

## 3. H0 — Hardware Interface and Safety Qualification

### 3.1 Entry gate

H0 只有在以下全部满足时才能开始：

1. 有效的 `10_research/on_orbit_assembly/approvals/HAG-E.yaml` 绑定本计划、
   approved base、H0 合同、设备资产范围和安全规程 hash；
2. `h0_execution_contract.yaml` 与 `h0_threshold_registry.yaml` 已冻结，所有
   mandatory threshold 有来源，零 `TBD`；
3. 现场操作员和独立观察员确认工作区、机械止挡/隔离、供电切断路径、急停通道、
   允许运动包络和禁止进入区；
4. H0-PRE 只读 inventory 的命令 allowlist 已冻结；allowlist 中不存在
   enable、home、jog、trajectory、torque、gripper close 等运动写命令；
5. 输出目录为空或是全新 session；不得覆盖既有负结果；
6. 冻结 30_simulation/SAFE/CTRL/geometry 无 diff。

当前结果：上述第 1 条不满足，故 **H0 仍为 NOT_STARTED，B601 motion 禁止**。

### 3.2 H0-PRE：control 前的 read-only inventory

顺序固定：

1. 断电/物理观察优先：铭牌、asset id、控制器/相机/夹爪/encoder/急停硬件连接；
2. 若身份读取必须上电，只允许 motion inhibit 状态下的 read-only query；
3. 冻结 driver/SDK/firmware/transport/协议来源和二进制 hash；
4. 建立 joint order、unit、sign、encoder、软/硬限位映射；
5. 建立相机枚举与 timestamp capability；**枚举成功不等于内参/外参已标定**；
6. 建立急停/使能/故障复位的实际信号路径；
7. 运行 H0 premotion machine gate，输出
   `hardware/qualification/H0/h0_premotion_gate_check.json`；
8. 只有 verdict 精确为 `H0_PREMOTION_PASS` 才能进入受限资格动作。

串口存在、USB 名称、网络端口或 ROS topic 出现均不能单独证明是 B601。通信方式、
SDK、波特率、joint id 和指令编码必须来自设备返回值、厂商材料或现场绑定证据，
不得猜测。

### 3.3 H0 必测面

| 面 | 最小验证 | 失败/UNKNOWN 行为 |
|---|---|---|
| safety | SOP/工作区/人员/隔离/允许包络/故障复位链完整 | `H0_BLOCKED`，禁止运动 |
| driver | OS、驱动、SDK/控制器程序、firmware、二进制 hash 与设备绑定 | 身份或版本不明即 `H0_BLOCKED` |
| communication | 先只读握手，再按合同做有限 round-trip；序列号、超时、乱序、重连、CRC/状态码 | 丢包/协议歧义/自动重连导致使能即停 |
| camera | 型号/serial/driver/mode/timestamp capability 枚举 | 只影响 H2 时可登记 gap；若参与 H0 安全观察则阻塞 |
| encoder | joint order/sign/unit/zero/resolution/limit bits/readback 更新 | 任一关节映射 UNKNOWN 即禁止该关节运动 |
| e-stop/interlock | 双通道（如适用）触发、控制器 inhibit、实际停止、复位必须人工 | 任何一次未阻断或 stop latency 无法量化即 `H0_BLOCKED` |
| repeatability | 已批准小范围、低速、双向接近的重复落点；encoder 内部与独立测量分开报告 | 无独立量具时只能称 encoder repeatability |
| gripper `T_c` | 多次闭合，保存 command→first motion 与 command/first motion→closed 两种定义 | 时钟未标定或 closed condition 不可观测则保持 PROVISIONAL |

`T_c` 的实测量必须命名为 `gripper_closure_time`。它不自动等同于 sim_11 的
`contact_window_T_c`；只有独立接触起止传感与映射 Gate 通过后，才允许
`mapping_to_sim11_contact_window=MEASURED`。否则回灌记录必须写
`mapping_to_sim11_contact_window=PROVISIONAL_PROXY`。

### 3.4 H0 planned evidence files and exact fields

计划目录：`hardware/qualification/H0/`

| 文件 | 必填字段 |
|---|---|
| `h0_execution_contract.yaml` | 第 2.2 节全部字段；H0-PRE allowlist；motion plan hash；每项 threshold/source |
| `device_inventory.json` | `session_id, observed_at_utc, arm_asset_id, manufacturer, model, serial, controller_model, controller_serial, firmware_version, power_supply_id, gripper_model, encoder_channels[], joint_count_observed, nameplate_photo_refs[], observation_method, identity_status, unknown_fields[]` |
| `software_inventory.json` | `host_os, driver_name, driver_version, driver_source, sdk_name, sdk_version, controller_app_version, executable_paths[], sha256[], transport_declared, protocol_declared, provenance_refs[], status` |
| `communication_roundtrip.csv` | `session_id, trial_id, seq, operation=READ_ONLY|QUALIFICATION_WRITE, request_type, request_sha256, send_monotonic_ns, device_timestamp_raw, receive_monotonic_ns, roundtrip_ms, response_code, response_sha256, crc_status, ordered, timeout, retry_count, motion_enabled, status, reason_code, raw_ref` |
| `camera_inventory.json` | `camera_asset_id, manufacturer, model, serial, driver, firmware, transport, supported_modes[], selected_mode, hardware_timestamp_available, clock_id, exposure_control, raw_capture_ref, inventory_status, calibration_status` |
| `encoder_joint_map.csv` | `joint_index, logical_joint_id, device_channel_id, encoder_type, raw_unit, output_unit, sign, zero_definition, resolution, hard_min_raw, hard_max_raw, soft_min_rad, soft_max_rad, limit_bit_ids, provenance_ref, status` |
| `estop_interlock_log.csv` | `trial_id, estop_channel_id, test_mode, motion_plan_sha256, motion_state_before, trigger_monotonic_ns, controller_inhibit_monotonic_ns, stop_detected_monotonic_ns, stop_latency_ms, residual_motion_value, residual_motion_unit, power_removed, reset_was_manual, threshold_ref, status, reason_code, raw_ref` |
| `joint_limit_and_repeatability.csv` | `trial_id, repeat_index, joint_id, approach_direction, target_rad, commanded_speed_rad_s, encoder_start_rad, encoder_end_rad, error_rad, external_measurement_value, external_measurement_unit, external_instrument_id, hard_limit_state, soft_limit_state, estop_state, threshold_ref, status, raw_ref` |
| `gripper_tc_trials.csv` | `trial_id, load_condition, opening_start_mm, opening_end_mm, command_clock_id, command_timestamp_ns, first_motion_timestamp_ns, closed_condition_timestamp_ns, closed_condition_source, tc_command_to_closed_ms, tc_first_motion_to_closed_ms, sample_rate_hz, timing_uncertainty_ms, contact_sensor_used, mapping_to_sim11_contact_window, threshold_ref, status, raw_ref` |
| `h0_premotion_gate_check.json` | 第 7.1 节 Gate schema；`verdict=H0_PREMOTION_PASS|H0_PREMOTION_BLOCKED` |
| `h0_evidence_manifest.json` | 第 2.4 节 schema |
| `h0_gate_check.json` | 第 7.1 节 Gate schema；H0 最终三选一裁决 |

### 3.5 H0 exit gate

`H0_COMPONENT_QUALIFIED` 仅在以下全部成立时允许：

- H0-PRE PASS，授权与 device binding 从开始到结束未漂移；
- driver/communication/encoder/joint map 全部 mandatory check PASS；
- 急停每个批准通道的每次 mandatory trial 都正确阻断，复位均为人工；
- 软件/硬件限位与批准的小范围运动包络一致；
- repeatability 与 `T_c` 的 required trial 数、方向/载荷组和阈值均按合同完成；
- raw evidence、manifest、hash、时钟不确定度齐全；
- mandatory `UNKNOWN=0`，无未解释的 command、丢帧、丢包或自动恢复运动；
- 红队 H0 攻击全部完成并正确 fail-closed。

未达到数值阈值但输入/设备/证据完整时为 `H0_REPEAT`；缺授权、身份、协议、安全、
时钟或关键证据时为 `H0_BLOCKED`。Gate 落盘后 **STOP**，不自动启动 H1。

## 4. H1 — Fixed-Base Prerecorded Low-Speed Execution

### 4.1 Entry gate

H1 必须同时满足：

1. `h0_gate_check.json.verdict=H0_COMPONENT_QUALIFIED`，且 manifest/device binding
   hash 精确匹配当前设备；
2. HAG-E 对 H1 的阶段授权有效，绑定唯一预存轨迹、速度/加速度/力矩限制、
   工作区、人员和时间窗；
3. 独立生成的 `h1_controller_preflight_gate_check.json` PASS；它只做离线轨迹、
   joint order/unit/sign/frame、限位、采样率、watchdog 与停止路径检查；
4. `trajectory_plan.yaml` 已冻结，所有 command sample 预生成并 hash 锁；
5. L5 Adapter 只做单位/坐标/关节顺序/限位转换和急停，不含策略选择、
   在线轨迹生成、视觉伺服或自适应控制；
6. CTRL-01 当前 `REPEAT` 与 `next_stage_authorized=false` 被原样登记；
   **不得把它当作已解决的硬件控制 Gate**；
7. 现场执行仍须人工 enable，任何运行时编辑使 trajectory hash 失效并阻止启动。

当前 H0 未开始，因此 H1 entry 不满足。

### 4.2 Minimal experiment

- 固定基座 B601；
- 仅执行合同内的预存、低速、无在线修改轨迹；
- 先 dry-run/command preview，再无负载或批准载荷的最小动作；
- 同步保存实际发出的 command bytes、控制器确认和全部可用 telemetry；
- 评价 command/telemetry 对齐、跟踪误差、limit margin、延迟、丢包、watchdog、
  急停/正常停止；
- 不接收 H2 感知、VLA/Agent 或 offline twin 的运行时动作；
- M2–M5 接口样件试验只有在 ASM-00/样件/测力/安全合同被单独纳入 H1
  authorization 时才可运行；否则字段为 `NOT_APPLICABLE`，不阻塞纯执行资格，
  也不得创建伪造的零数据。

### 4.3 H1 planned evidence files and exact fields

计划目录：`hardware/qualification/H1/`

| 文件 | 必填字段 |
|---|---|
| `h1_execution_contract.yaml` | 共用头；H0 Gate/hash；trajectory/adapter/controller-preflight hashes；冻结阈值；`online_update_allowed=false` |
| `trajectory_plan.yaml` | `trajectory_id, source, generation_tool_sha256, joint_order[], frame_convention, sample_period_s, duration_s, position/velocity/acceleration/torque_limits, start_state, end_state, hold_points[], stop_profile, samples_sha256` |
| `adapter_binding.json` | `adapter_version, build_sha256, input_joint_order, output_channel_order, unit_conversions[], sign_conventions[], frame_transforms[], software_limits[], controller_mode, watchdog_period_ms, estop_bindings[], decision_logic_present=false, status` |
| `h1_controller_preflight_gate_check.json` | Gate schema；trajectory feasibility、limit margin、hash、watchdog、stop-path checks；`verdict=H1_PREFLIGHT_PASS|H1_PREFLIGHT_BLOCKED` |
| `trajectory_command.csv` | `session_id, trial_id, trajectory_id, sample_index, scheduled_monotonic_ns, emitted_monotonic_ns, joint_id, position_cmd_rad, velocity_cmd_rad_s, acceleration_cmd_rad_s2, torque_limit_Nm, command_mode, command_payload_sha256, controller_ack_code, motion_enable_state, estop_state, status, raw_ref` |
| `joint_telemetry.csv` | `session_id, trial_id, sample_index, host_receive_monotonic_ns, device_timestamp_raw, device_clock_id, joint_id, position_rad, velocity_rad_s, effort_value, effort_unit, current_A, temperature_C, hard_limit_state, soft_limit_state, controller_state, estop_state, packet_seq, raw_ref` |
| `latency_drop_log.csv` | `trial_id, stream_id, expected_seq, received_seq, send_monotonic_ns, receive_monotonic_ns, latency_ms, gap_count, reordered, stale, watchdog_triggered, action_taken, threshold_ref, status, reason_code, raw_ref` |
| `tracking_summary.csv` | `trial_id, joint_id|EEF_metric, frame_id, metric_name, value, unit, window_start_s, window_end_s, threshold_ref, status, provisional_fields, command_ref, telemetry_ref` |
| `contact_coupon_results.csv` | 若批准 M2–M5：`trial_id, coupon_id, material_pair, surface_treatment, measurement=M2|M3|M4|M5, input_value, response_value, unit, instrument_id, calibration_ref, uncertainty, fit_method, status, raw_ref`；否则文件不创建并由 manifest 标 `NOT_APPLICABLE_BY_CONTRACT` |
| `h1_evidence_manifest.json` | 第 2.4 节 schema |
| `h1_gate_check.json` | 第 7.1 节 Gate schema；H1 最终三选一裁决 |

### 4.4 H1 exit gate

`H1_FIXED_BASE_EXECUTION_QUALIFIED` 只证明：在冻结设备、固定基座、批准载荷与
预存低速轨迹范围内，Adapter 命令/遥测链和已冻结指标合格。必要条件：

- command payload 与 `trajectory_plan.yaml` 逐 sample/hash 对拍，零额外命令；
- telemetry 时间单调、缺包/乱序/陈旧、tracking/limit/watchdog 指标均按
  preregistered threshold 裁决；
- 所有停止事件都按合同执行；任何 e-stop/safety 触发后没有自动恢复；
- raw command 与 telemetry 均可回放、manifest 完整、mandatory UNKNOWN=0；
- 红队 H1 攻击全部完成。

数值指标未达但证据完备为 `H1_REPEAT`；任何非预存命令、hash 漂移、危险状态、
设备/时间/telemetry 证据缺失为 `H1_BLOCKED`。Gate 落盘后 **STOP**，不得自动
启动 H2。

## 5. H2 — Cooperative-Marker Sensing Qualification

### 5.1 Entry gate

H2 必须同时满足：

1. `h1_gate_check.json.verdict=H1_FIXED_BASE_EXECUTION_QUALIFIED`；
2. HAG-E 对 H2 的阶段授权有效并绑定 camera、marker board、目标运动台、
   工作区、速度上限、数据合同和 calibration hashes；
3. 相机内参、相机到实验室/目标运动台的外参和 ground-truth sensor 标定
   都有未过期 Gate；
4. timebase offset/drift/uncertainty 已测；不能假设 camera、host、controller、
   target stage 共用时钟；
5. estimator preregistration 冻结输入、marker family/size/id、frame tree、
   covariance、validity/freshness、latency/dropout/occlusion 分组和阈值；
6. 若使用已知运动目标，其驱动/编码器必须有独立安全资格；否则只允许静态
   calibration，H2 动态 Gate 保持 BLOCKED；
7. H2 不向 B601 发送动作：`arm_motion_enabled=false`,
   `closed_loop_control=false`, `command_emitted=false`。

当前 H1 未开始且 estimator/calibration Gate 不存在，因此 H2 entry 不满足。

### 5.2 Minimal designed experiment

1. 静态 marker board 做内参/畸变复核；
2. camera→lab、lab→target-stage、marker→target 的外参链闭合；
3. 独立 ground truth 下的已知低速转动/平移，覆盖预注册距离、视角、角速度组；
4. latency 试验分解 exposure/capture、transport、estimation、publication；
5. dropout 试验包含 sequence gap、延迟帧、乱序帧、遮挡和 marker detection loss；
6. stale/invalid frame 必须输出 `INVALID/HOLD`，不得沿用旧 pose 伪装连续估计；
7. pose/rate 结果携带 covariance/uncertainty；区间跨下游 gate boundary 时只允许
   `HOLD/INSUFFICIENT_EVIDENCE`，本阶段不调用真实执行链。

### 5.3 H2 planned evidence files and exact fields

计划目录：`hardware/qualification/H2/`

| 文件 | 必填字段 |
|---|---|
| `h2_execution_contract.yaml` | 共用头；H1 Gate/hash；camera/marker/stage binding；测试组；estimator build/hash；thresholds；`command_emitted=false` |
| `marker_target_manifest.json` | `marker_family, marker_ids[], nominal_size_m, measured_size_m, size_uncertainty_m, print/source_sha256, marker_to_target_transform, frame_ids, mounting_method, occlusion_notes, photo_refs[], status` |
| `camera_intrinsics.yaml` | `schema_version, camera_asset_id, serial, image_width, image_height, pixel_format, camera_matrix, distortion_model, distortion_coefficients, calibration_method, calibration_timestamp_utc, image_count, reprojection_error_px, validity_conditions, calibration_raw_refs[], calibration_gate_status` |
| `camera_extrinsics.yaml` | `schema_version, parent_frame, child_frame, translation_m, quaternion_wxyz, covariance_6x6, calibration_method, calibration_timestamp_utc, calibration_raw_refs[], inverse_closure_error, chain_closure_error, validity_conditions, calibration_gate_status` |
| `timebase_calibration.json` | `session_id, clock_pairs[], method, sample_count, offset_ns, drift_ppm, jitter_ns_p50, jitter_ns_p95, uncertainty_ns, calibration_start_utc, calibration_end_utc, validity_window_s, raw_refs[], status` |
| `target_motion_manifest.json` | `target_stage_asset_id, controller_serial, encoder_id, motion_profile_id, profile_sha256, frame_id, axis, commanded_rate, rate_unit, measured_rate_source, safety_gate_ref, start/stop_method, status` |
| `ground_truth_timeseries.csv` | `session_id, trial_id, sample_index, ground_truth_clock_id, ground_truth_timestamp_ns, host_receive_monotonic_ns, target_frame_id, position_x_m, position_y_m, position_z_m, quat_w, quat_x, quat_y, quat_z, omega_x_rad_s, omega_y_rad_s, omega_z_rad_s, covariance_ref, encoder_seq, validity, raw_ref` |
| `estimate_timeseries.csv` | `session_id, trial_id, frame_seq, camera_clock_id, exposure_timestamp_ns, host_capture_monotonic_ns, estimate_ready_monotonic_ns, camera_frame_id, marker_id, target_frame_id, position_x_m, position_y_m, position_z_m, quat_w, quat_x, quat_y, quat_z, omega_x_rad_s, omega_y_rad_s, omega_z_rad_s, covariance_6x6_ref, detection_confidence, age_ms, validity, reason_code, raw_image_ref` |
| `latency_dropout.csv` | `trial_id, frame_seq_expected, frame_seq_received, exposure_to_capture_ms, capture_to_estimate_ms, exposure_to_estimate_ms, timebase_uncertainty_ms, dropped, reordered, duplicate, occluded, detection_lost, stale, estimator_output_action, threshold_ref, status, raw_ref` |
| `calibration_and_error_summary.csv` | `trial_group, distance_m, view_angle_deg, target_rate_dps, occlusion_class, metric_name, value, unit, uncertainty, sample_count, threshold_ref, status, ground_truth_ref, estimate_ref` |
| `h2_evidence_manifest.json` | 第 2.4 节 schema |
| `h2_gate_check.json` | 第 7.1 节 Gate schema；H2 最终三选一裁决 |

### 5.4 H2 exit gate

`H2_COOPERATIVE_MARKER_SENSING_QUALIFIED` 仅在以下全部成立时允许：

- intrinsics/extrinsics/timebase/ground-truth calibration Gate 全部 PASS 且未过期；
- 所有预注册距离/角度/速度/遮挡组完成，无组被事后删除；
- pose/rate error、covariance consistency、latency、dropout 与 freshness 均按
  冻结 threshold 裁决；
- dropout/occlusion/stale 负例全部 fail-closed，零陈旧 pose 被标为可执行；
- 数据 join 依赖明确的 clock mapping 与 frame transform，不能仅按行号拼接；
- mandatory UNKNOWN=0，raw images/ground truth/estimates/manifest 齐全；
- 红队 H2 攻击全部完成。

指标未达但数据完整为 `H2_REPEAT`；标定、时钟、ground truth、frame、marker size
或 provenance 缺失为 `H2_BLOCKED`。Gate 落盘后 **STOP**；不启动 H3、HIL、
VLA 或任何闭环动作。

## 6. Planned threshold registries

每阶段在实验前各建一个 immutable registry：

```text
hardware/qualification/H0/h0_threshold_registry.yaml
hardware/qualification/H1/h1_threshold_registry.yaml
hardware/qualification/H2/h2_threshold_registry.yaml
```

registry 的每项必须有：

```yaml
threshold_id: <stable id>
metric: <exact field/derived metric>
operator: LT | LE | GT | GE | EQ | IN_SET
value: <numeric or enum>
unit: <SI or explicit>
applicability: <trial group>
source_type: MANUFACTURER | SAFETY_REVIEW | CALIBRATION | PREREGISTRATION
source_ref: <path + key/page>
frozen_at_commit: <sha40>
status: FROZEN
```

H0 至少覆盖通信 round-trip/timeout、stop latency/residual motion、允许关节包络、
repeatability、`T_c` required trials 与 timing uncertainty。H1 至少覆盖 tracking、
limit margin、latency/dropout/watchdog、停止响应。H2 至少覆盖 calibration、
pose/rate error、covariance、latency、dropout、freshness 与 timebase uncertainty。

缺任何 mandatory threshold 时，entry Gate 直接 BLOCKED；不得在看到结果后补阈值，
也不得从本计划的叙述性文字推导数值。

## 7. Machine Gate contracts and commands

### 7.1 共用 Gate JSON schema

`h0_gate_check.json`、`h1_gate_check.json`、`h2_gate_check.json` 共用：

```json
{
  "schema_version": "ground-component-gate-v1",
  "stage": "H0|H1|H2",
  "source_commit": "<sha40>",
  "source_worktree_clean_before_run": true,
  "contract": {"path": "<path>", "sha256": "<sha256>"},
  "authorization": {
    "path": "10_research/on_orbit_assembly/approvals/HAG-E.yaml",
    "sha256": "<sha256>",
    "valid": true,
    "stage_bound": true,
    "device_bound": true,
    "not_expired": true
  },
  "upstream_gates": [
    {"path": "<path>", "sha256": "<sha256>", "required_verdict": "<value>", "actual_verdict": "<value>"}
  ],
  "device_binding_sha256": "<sha256>",
  "threshold_registry": {"path": "<path>", "sha256": "<sha256>", "all_frozen": true},
  "evidence_manifest": {"path": "<path>", "sha256": "<sha256>", "complete": true},
  "checks": [
    {
      "check_id": "<stable id>",
      "mandatory": true,
      "status": "PASS|FAIL|UNKNOWN|NOT_APPLICABLE",
      "reason_code": "<registered code>",
      "threshold_ref": "<id or NOT_APPLICABLE>",
      "evidence_refs": ["<path#record>"]
    }
  ],
  "counts": {"mandatory_pass": 0, "mandatory_fail": 0, "mandatory_unknown": 0, "negative_results": 0},
  "red_team": {"planned": 0, "completed": 0, "correctly_blocked": 0},
  "provisional_fields": [],
  "negative_results_preserved": true,
  "scope": "<stage-specific limited claim>",
  "verdict": "<stage vocabulary>",
  "next_stage_authorized": false
}
```

Stage vocabulary：

| Stage | PASS | 可修复数值/重复性失败 | 授权/安全/身份/证据阻塞 |
|---|---|---|---|
| H0 | `H0_COMPONENT_QUALIFIED` | `H0_REPEAT` | `H0_BLOCKED` |
| H1 | `H1_FIXED_BASE_EXECUTION_QUALIFIED` | `H1_REPEAT` | `H1_BLOCKED` |
| H2 | `H2_COOPERATIVE_MARKER_SENSING_QUALIFIED` | `H2_REPEAT` | `H2_BLOCKED` |

PASS 规则固定为：全部 mandatory check PASS、mandatory UNKNOWN=0、required red-team
coverage 完整、manifest 完整、hash 不漂移。测试程序返回码 0 不等于科学 Gate PASS。

### 7.2 当前允许的只读 preflight

```powershell
git status --short
git rev-parse HEAD
git diff --name-only HEAD -- sim config 10_research/on_orbit_assembly
Test-Path 10_research/on_orbit_assembly/approvals/HAG-E.yaml
Test-Path hardware/qualification/H0/h0_gate_check.json
Test-Path hardware/qualification/H1/h1_gate_check.json
Test-Path hardware/qualification/H2/h2_gate_check.json
Get-FileHash 20_engineering/config/geometry/arm_b601_v1.yaml -Algorithm SHA256
Get-FileHash 20_engineering/config/coupled_scene/scene_A2_capture.yaml -Algorithm SHA256
```

这些命令不连接设备。当前不得运行端口枚举、camera probe、ROS discovery、SDK
handshake、上电、回零或运动命令。

### 7.3 未来获批后的 planned runners

以下路径目前不存在；它们是执行合同，不是“已可用命令”：

```powershell
python hardware/qualification/common/verify_stage_entry.py `
  --stage H0 `
  --authorization 10_research/on_orbit_assembly/approvals/HAG-E.yaml `
  --contract hardware/qualification/H0/h0_execution_contract.yaml

python hardware/qualification/H0/run_premotion_gate.py `
  --contract hardware/qualification/H0/h0_execution_contract.yaml `
  --output hardware/qualification/H0/h0_premotion_gate_check.json

python hardware/qualification/H0/run_gate.py `
  --contract hardware/qualification/H0/h0_execution_contract.yaml `
  --manifest hardware/qualification/H0/h0_evidence_manifest.json `
  --output hardware/qualification/H0/h0_gate_check.json

python hardware/qualification/common/verify_stage_entry.py `
  --stage H1 `
  --authorization 10_research/on_orbit_assembly/approvals/HAG-E.yaml `
  --contract hardware/qualification/H1/h1_execution_contract.yaml `
  --upstream hardware/qualification/H0/h0_gate_check.json

python hardware/qualification/H1/run_controller_preflight_gate.py `
  --contract hardware/qualification/H1/h1_execution_contract.yaml `
  --output hardware/qualification/H1/h1_controller_preflight_gate_check.json

python hardware/qualification/H1/run_gate.py `
  --contract hardware/qualification/H1/h1_execution_contract.yaml `
  --manifest hardware/qualification/H1/h1_evidence_manifest.json `
  --output hardware/qualification/H1/h1_gate_check.json

python hardware/qualification/common/verify_stage_entry.py `
  --stage H2 `
  --authorization 10_research/on_orbit_assembly/approvals/HAG-E.yaml `
  --contract hardware/qualification/H2/h2_execution_contract.yaml `
  --upstream hardware/qualification/H1/h1_gate_check.json

python hardware/qualification/H2/run_gate.py `
  --contract hardware/qualification/H2/h2_execution_contract.yaml `
  --manifest hardware/qualification/H2/h2_evidence_manifest.json `
  --output hardware/qualification/H2/h2_gate_check.json
```

每个 entry runner 必须验证：authorization/contract/plan/upstream/registry/device/trajectory
hash、Git scope、上一阶段精确 verdict 与 expiry。由于阶段 Gate 固定
`next_stage_authorized=false`，runner 还必须另读 HAG-E 中对当前阶段的独立授权；
不得编辑、覆盖或把上游的 `next_stage_authorized=false` 解释成 true。校验失败时
不得调用任何采集或设备进程。

## 8. Red-team coverage

红队结果计划写入各阶段 `red_team_results.json`，字段为
`attack_id, stage, setup_ref, expected_block, actual_block, evidence_ref, status`。
每个已启动阶段要求 `completed/planned=100%`。

### 8.1 H0 attacks

1. HAG-E 缺失、过期、错误 stage/device/hash；
2. 仅因发现 COM/USB/ROS 名称就绑定 B601；
3. firmware/driver/SDK 来源或 binary hash 不明；
4. read-only allowlist 中混入 enable/home/jog/write；
5. joint order、unit、sign 或 zero 交换；
6. encoder 不更新、跳变或 limit bit 语义 UNKNOWN；
7. software limit 与硬件 limit/批准包络冲突；
8. e-stop 只改变 UI 状态但实际输出仍使能；
9. e-stop latency 时钟未标定或复位被自动化；
10. repeatability 只保留最佳 run；
11. `T_c` 用两个未对齐时钟相减；
12. gripper closure time 被直接改名为 contact-window `T_c`。

所有攻击必须在任何越界动作前阻断；第 8 项若在批准的 H0 试验中暴露真实安全
失败，立即人工断能、冻结证据并判 `H0_BLOCKED`。

### 8.2 H1 attacks

1. H0 非精确 PASS、设备 serial/hash 漂移；
2. 轨迹在运行时被编辑或样本 hash 不匹配；
3. Adapter joint order/unit/sign/frame 错置；
4. 在线生成/感知/VLA 命令混入预存 command；
5. 额外 command sample、重复 sample 或 controller ack 不对应；
6. telemetry 丢包/乱序/陈旧仍被插值成“跟踪成功”；
7. limit/watchdog/e-stop 触发后自动恢复；
8. CTRL-01 REPEAT 被文案改成“控制问题已解决”；
9. 仅凭固定基座轨迹回放外推自由漂浮/在轨控制；
10. 失败 trial 被删或只展示成功视频。

### 8.3 H2 attacks

1. marker family/id/实际尺寸与 estimator 配置不符；
2. camera serial 或分辨率改变但复用旧内参；
3. 外参方向颠倒、quaternion 次序错、frame chain 不闭合；
4. camera/host/ground-truth 时钟被假设同步；
5. latency 只报推理时间，省略 exposure/transport；
6. sequence gap、乱序、duplicate 或 stale frame 被静默插值；
7. 遮挡后复用旧 pose 仍标 valid；
8. 无 covariance/uncertainty 仍向下游提供点估计；
9. ground truth 与 estimate 按行号而非时间/帧连接；
10. AprilTag/cooperative marker 结果被写成 markerless/non-cooperative 泛化；
11. H2 输出被直接用作 B601 闭环命令；
12. 只报均值，隐藏角度/速度/遮挡负组。

## 9. Evidence-to-claim boundaries

### 9.1 当前允许的唯一表述

- “已冻结 H0/H1/H2 地面组件资格化计划；真实资格试验尚未启动。”
- “B601 数字模型/几何 SSOT 已存在，但实机 driver/communication/safety/encoder/
  camera 链尚无本阶段 Machine Gate 证据。”
- “sim_11 当前 `T_c=20 ms` 是 PROVISIONAL 占位，未来 H0 实测只会形成受控
  rerun trigger。”

### 9.2 未来各 Gate PASS 后才允许

| Gate | 最强允许 claim |
|---|---|
| H0 PASS | “记录配置、限定包络和冻结阈值下的 B601 ground-component interface/safety qualification” |
| H1 PASS | “固定基座、预存低速轨迹、记录载荷与设备配置下的 execution/telemetry characterization” |
| H2 PASS | “记录距离/角度/速度/遮挡范围内的 cooperative-marker sensing qualification” |

每条 claim 必须同时给 Gate 路径/hash、设备 binding、合同范围、PROVISIONAL 字段和
不适用范围。H0/H1/H2 PASS 均不是飞行资格、整机资格或在轨有效性。

### 9.3 永久禁止或本阶段禁止

- HAG-E 与 H0 premotion Gate 前的任何 B601 movement；
- H0 最终 PASS 前的 H1/H2 任务动作；
- H3、HIL、VLA、Wave B 或 Agent 闭环；
- completed autonomous on-orbit assembly；
- real-time digital twin 或硬件双向在线 twin；
- free-floating hardware validation；
- 固定基座等价于 microgravity/space/on-orbit validation；
- markerless VLA generalization、AprilTag 等价非合作目标感知；
- flight-qualified safety；
- final flexible assembly certification；
- CTRL-01 通用控制问题已解决、CTRL-02 已 hardware-valid；
- `UNKNOWN / NOT_EVALUATED / PROVISIONAL / REPEAT` 被写为 SUCCESS/EXECUTE。

## 10. Downstream handoff without silent promotion

### 10.1 `T_c` handoff

H0 Gate PASS 后另建 rerun request，至少绑定：

```text
h0_gate_check.json sha256
gripper_tc_trials.csv sha256
measured quantity definition
clock/calibration uncertainty
load/opening conditions
mapping_to_sim11_contact_window status
target config path/key
required sim_11 rerun scope
```

只有新的独立 sim_11 执行与 Machine Gate 能解除对应 PROVISIONAL 字段；H0 报告
不得声明 sim_11 已转正。

### 10.2 H1/H2 handoff

- H1 telemetry 可形成 controller/actuator model 的 rerun trigger，但不修改冻结
  CTRL-01/02 工件。
- H2 error/covariance/latency 区间可供未来 estimator/physics-tool 查询合同使用，
  但 H2 不生成 EXECUTE，不授权 C 场景或任何新 SAFE 候选。
- competition demo 在 H0/H1/H2 未过时继续使用纯 offline evidence replay；
  不得让硬件 lane 阻塞比赛主线，也不得用计划动画代替硬件证据。

## 11. Rollback, incident and STOP rules

1. 每阶段使用新 session 目录；raw evidence 只追加，禁止覆盖。
2. FAIL/UNKNOWN 先 hash + manifest + incident record，再停；不得删除失败结果
   “清理画面”。
3. 安全事件由获批现场人员按 SOP 物理断能；软件不得自动复位或重新使能。
4. authorization/contract/registry/device/trajectory/calibration/upstream Gate 任一 hash
   漂移，立即停止，当前 session 标 `INVALIDATED_BY_HASH_DRIFT`。
5. 任一非 owned path diff、冻结区 diff 或用户文件被触碰，立即停止并上报。
6. 任一未计划 command、运动包络越界、limit/encoder 语义冲突、e-stop 未阻断、
   通信丢失自动恢复，判相应阶段 `BLOCKED` 并停止。
7. H2 标定/时钟/ground truth 不可信时不得“先看趋势”；动态 qualification 停止。
8. Repeat 只允许在新的 authorization/session 下执行；旧 session 原样保留。
9. 每个阶段 Gate 落盘后 STOP；不得把 PASS 自动解释为下一阶段授权。
10. 本计划不自动开始 H3、HIL、VLA、Wave B，也不接触真实 competition command path。

## 12. Planning closeout

本文件完成时的真实状态仍是：

```text
H0 = NOT_STARTED_BLOCKED_BY_MISSING_HAG_E
H1 = NOT_STARTED_BLOCKED_BY_H0
H2 = NOT_STARTED_BLOCKED_BY_H1_AND_ESTIMATOR_GATE
B601_MOTION = PROHIBITED
H3/HIL/VLA = NOT_AUTHORIZED
```

因此本计划可以进入 PI/安全负责人审查，但不能作为设备动作授权。下一次合法动作是
冻结 HAG-E、阶段合同、threshold registry、人员/工作区安全记录和 H0-PRE
read-only allowlist；在这些全部机器校验通过前继续保持 planning only。
