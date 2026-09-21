# PATCH_NOTES — validator_integration_r14_20260919（工作包 B）

## 修改范围（仅两处工程文件，均在本包授权内）

### 1. 修改：`20_engineering/service_robot_wp03_spacecraft_body_r1/pose_screen.py`

目的：消除期望配对/关节/场景硬编码，期望集改由输入快照同源推导；worker 事件携带身份；判据全部派生化。

- 新增模块级函数（worker 与 main 同源推导，杜绝两份常量漂移）：
  - `INPUT_FILES` / `contract_input_hashes()`：合同输入文件清单与哈希（URDF、wp01 kinematics/design_parameters/LAYOUT_COMPARISON/stowed_build_receipt/FINGER_INTERFACE_CHECK、wp02 motion_analysis、wp03 wing_kinematics）。
  - `expected_nonadjacent_pairs()`：从接受 URDF 关节树推导——10 link，C(10,2)=45 − 9 相邻 = 36 非相邻。
  - `DEFERRED_PAIRS`：显式延期对（gripper_left/gripper_right 指/指对，UNKNOWN 不零填）。
  - `screen_run_id()` / `snapshot_digest()`：运行身份与输入快照摘要。
- worker 事件升级：`pair`/`pose_complete` 事件携带 `run_id`、`snapshot_digest`、`pose_id`、`completed`、`expected_pair_count`。
- main 输出 schema 升级 `WP03_BOUNDED_EXISTING_POSE_SCREEN_V1 → V2`：
  - 录 `self_screen_contract`（run_id / snapshot_digest / expected_nonadjacent_pairs 36 列表 / explicit_unknown_pairs / required_evaluated_pairs=35 / input_sha256 / configuration）。
  - 录 `worker_returncode` / `worker_timed_out` / `self_worker_error`。
  - 判据派生化：有命中→`EXPLICIT_SELF_SURFACE_INTERSECTION_REJECTED`；完成事件身份不符 / checked≠required / 超时 / rc≠0 → INCOMPLETE_UNKNOWN 类；否则 `NONADJACENT_BODY_PAIRS_SURFACE_DISJOINT_FINGER_UNKNOWN`。
  - `completion_event`（去 rows）入档。
- 未动：两参考姿态的历史标签字符串（指历史 WP01 记录）；指/指对延期语义；VTK FirstContact 方法。

哈希对照：改前 `POSE_SCREEN_before.json`（输出快照）= e3104aeca58697fb8dd1ebf4b9d0eadbb80b3e99617b695b630eece53ab98129；改后脚本 = 15cc772ff0c4b2fe19b6d691cdd8a30cd173ea50af5854c21bfec0a51da6e70a；改后真实重跑输出 `POSE_SCREEN.json` = 07670f67879b88950c6a320b7e8e2695e15049254d2a14d9f8e557bef386c57f（16.3 s，无超时）。

### 2. 新增：`20_engineering/service_robot_wp03_spacecraft_body_r1/strict_surface_integration.py`

- 原型 `runs/loop0_20260905/a4/strict_surface_aggregator.py` 未动；本文件为部署接入版（新文件，不覆盖任何既有交付物）。
- `aggregate(data, script_path, snapshot_binding)` fail-closed 检查面：
  脚本哈希 / schema / source_hashes 逐项重算 / 快照绑定失配 / 合同完备性 / worker rc≠0、超时、error / 完成事件身份（run_id+pose_id+snapshot_digest+expected_pair_count）/ worker_completed 标志 / 记录 pair 集合恒等（重复、缺失、错误 ID）/ float-NaN 与非法布尔 / 延期范围漂移 / 姿态状态一致性 / evaluated==required。
- 协议验收与机械碰撞验收**分列**：机械碰撞仅声明范围内结论（hits→SURFACE_INTERSECTION_RECORDED；否则 DISJOINT_WITHIN_DECLARED_SCOPE；UNKNOWN 范围列明：指/指对、相邻对、闭体包含、连续路径）。
- `require_physical_view`：view≠complete 或 state∉{parking,released,service} → 抛 `DISPLAY_OR_UNSUPPORTED_CONFIGURATION_REJECTED`。
- 文件 sha256 = 783e3b7e13fd9a8a88a65489c5e029e01e5554c1acfca44e16da602cd52c2c96。

## 未触碰（边界确认）

- gate / issues.json / CURRENT 文件未改；无 git 提交。
- 正式交付物未改动：R14 扰动全程 `write_parts=False`，BOM.csv / INTERFACES.csv / HANDOFF 未重生成；`design_parameters.json` 与 `results/service_structure_instances.json` 扰动后均字节级恢复并复核 sha256（324b49c7… / d220c702…）。
- 原型 strict_surface_aggregator.py 未动。
