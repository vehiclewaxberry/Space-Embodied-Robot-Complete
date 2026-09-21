# ACCEPTANCE_SUMMARY — WP03 阶段一收口 工作包 B（严格验证器真实接入 + R14 参数扰动）

run：`01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/validator_integration_r14_20260919/`

## 1. 真实接入的输入来源链

- 期望配对不再硬编码：由接受 URDF（`arm_b601_v1.urdf`，快照 1bc2b748…）关节树推导——10 link → C(10,2)=45 − 9 相邻 = **36 非相邻对**；延期 1（gripper_left/gripper_right 指/指对，UNKNOWN）；**必需评估 35**。
- 输入哈希合同：pose_screen V2 录 `self_screen_contract.input_sha256`（8 个输入文件）+ `script_sha256`；worker `pose_complete` 事件携带 run_id / snapshot_digest / pose_id / expected_pair_count 身份。
- 快照绑定：`inputs/snapshot_binding.json` 将 POSE_SCREEN.json 记录的 8 个 source_hashes 键逐位绑定到本 run 输入快照哈希（同名歧义已按 wp01/wp02/wp03 前缀消歧），汇总器逐项重算现行文件哈希比对。

## 2. 正控（真实 worker 链，协议/机械碰撞分列）

证据：`evidence/r17b_strict_integration_positive.json`；工程同步件 `results/STRICT_SURFACE_INTEGRATION.json`（新文件）。

| 验收面 | 结果 |
|---|---|
| 协议验收 | **PASS**（expected_pair_count=36，deferred=1，poses_checked=3，reasons 空） |
| 机械碰撞验收 | **DISJOINT_WITHIN_DECLARED_SCOPE**（3 候选姿态 36 对全 disjoint，hits 空） |
| overall | **PASS**；unbound 源路径 = [] |

机械碰撞 UNKNOWN 范围（声明，不零填）：指/指对、相邻 link 对、闭体包含、连续路径；协议 PASS 不构成整星安全或发射收拢证明。

## 3. 负控（六类 + 附加 NaN 面，11/11 全检出）

证据：`evidence/r14_validator_negative_controls.json`，verdict `NEGATIVE_CONTROLS_ALL_DETECTED`，正控 PASS。

| 案例 | 变异 | 检出码 |
|---|---|---|
| NC1 | 重复 pair 记录 | DUPLICATE_PAIR_ID |
| NC2 | 缺失 pair 记录 | MISSING_OR_UNEXPECTED_PAIR_ID |
| NC3 | 错误 ID（不存在 link） | MISSING_OR_UNEXPECTED_PAIR_ID |
| NC4a | 输入文件哈希置零 | INPUT_STALE |
| NC4b | 脚本哈希置零 | SCRIPT_HASH_STALE |
| NC5 / NC5b | 爆炸视图 / 非法 state 充当物理输入 | ValueError: DISPLAY_OR_UNSUPPORTED_CONFIGURATION_REJECTED |
| NC6a | 删完成事件 | NO_COMPLETION_EVENT |
| NC6b | worker_completed=False | WORKER_COMPLETION_FLAG_FALSE |
| NC6c | worker_timed_out=True | TIMEOUT_OR_TIMEOUT_STATE_UNKNOWN |
| NC7 | surface_intersection=NaN | NAN_OR_FLOAT_RESULT |

全部 overall≠PASS（NC5 系列为异常抛出面）。

## 4. R14 参数扰动（机检对照，非"JSON 已改即通过"）

扰动：`deck_fastening_r01.deck_hole_pattern.X_S_mm[1]` **-50 → -45**（甲板孔距有效参数）。
证据：`evidence/r14_perturbation_compare.json`，verdict `R14_PERTURBATION_EXPECTED_EFFECT_CONFIRMED`；扰动回执 `r14_perturbed_receipt.json`。

| 断言组 | 结果 |
|---|---|
| A 复现性 | 恢复态重建回执 sha256 == 基线 d220c70274ab…（**bit-identical**） |
| B 遗留字段无效 | 扰动 `legacy_deck_hole_pattern_superseded.X_S_mm[3]` 150→155 后，回执除 dependency_sha256.design_parameters.json 外**逐键相等**（几何零效应；回执哈希变仅因依赖 provenance 如实记录参数文件哈希变化） |
| C1 BOM/id 集合 | 实例总数 487 不变；差集恰 4 移除（`*_deck_fastener_*_-50`）+ 4 新增（`_-45`），改名双射成立 |
| C2 责任件 | 上下甲板 + 两侧 segment0 角材：mass_kg 不变、惯量张量变化、COM x **负移**且与解析值 \|dx\|=n_hole·m_hole·5/mass 在 1% 内一致（孔=去除材料，孔正移则质心负移；甲板 -0.001363 mm、角材 -0.010256 mm）；segment1 角材与剪力网逐位不变（局部性） |
| C3 对偶件 | 4 个改名 fastener：parent/mount 不变、pn 映射 `WP03_…_-50→_-45`、质量不变、COM x **+5.000 mm** |
| C4 叠层 | 每甲板 fastener 数 8 不变；甲板 z/y bounds 不变（grip 叠层几何未变，仅孔位平移） |
| C6 provenance | dependency_sha256.design_parameters.json 改变、source_sha256 与其余依赖不变 |

扰动后 `design_parameters.json` 与 `service_structure_instances.json` 均已字节级恢复并复核 sha256（324b49c7… / d220c702…）。

## 5. pose_screen 覆盖范围声明

- 入场姿态 5 个：2 参考（OPEN_PARKING_REFERENCE / SERVICE_WORK_REFERENCE，保留历史标签）+ 3 候选（EXISTING_CANDIDATE_2/3/4，真实 VTK FirstContact 检查）。
- UNKNOWN 不零填：指/指对、相邻 link 对、闭体包含、连续路径、臂/星体其余对。

## 6. NOT_RUN / 边界

- 独立复验留审阅者（本包为构建者自证）。
- pose_screen 真实运行 16.3 s，无超时登记。
- finalize_delivery / geometry_checks / integrate_checks 未重跑。
- 票字段不回写；issues.json / gate / CURRENT 未改；无 git 提交。
- 实物验证不适用（纯数字几何层）。

## 7. 关键哈希

| 项 | sha256 |
|---|---|
| pose_screen.py（改后） | 15cc772ff0c4b2fe19b6d691cdd8a30cd173ea50af5854c21bfec0a51da6e70a |
| strict_surface_integration.py | 783e3b7e13fd9a8a88a65489c5e029e01e5554c1acfca44e16da602cd52c2c96 |
| POSE_SCREEN.json 改前快照 | e3104aeca58697fb8dd1ebf4b9d0eadbb80b3e99617b695b630eece53ab98129 |
| POSE_SCREEN.json 改后（V2） | 07670f67879b88950c6a320b7e8e2695e15049254d2a14d9f8e557bef386c57f |
| 基线结构回执 | d220c70274ab3bc27b306b253a4f6ac96057494de05a50c05955f04a450ef9a3 |
| 扰动回执 | c9934346ead7d21bac25f429d63c28dbf4dbb280ca55d9cae247cda584b68e16 |
| 遗留扰动回执 | 645714e4d749c2c282106f70fff916b440d0d2c3323982f7c633e86d6c7e11e1 |
| 复现回执 | d220c70274ab3bc27b306b253a4f6ac96057494de05a50c05955f04a450ef9a3 |
