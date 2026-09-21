# VIZ-Gate 0 冻结合同（2026-07-14）

## 冻结裁决

- 可视化门禁：`VIZ_GATE_0_ACCEPTED`
- 科学门禁：`PROJECT_FROZEN_AT_REPEAT_E1_5`
- 基线提交：`e473867273a880dba75c650d53eb7b2bad3676ac`
- 自动验收：6/6 PASS
- 回放数值一致性：44/44
- 核心输入资产：45/45 SHA-256 不变
- E1.5 冻结证据：22/22 SHA-256 一致

## 永久冻结对象

以下文件构成评审与验收基线；后续研究不得覆盖其内容：

- `40_evidence/artifacts/visualization/project_visualization_v0.html`
- `40_evidence/artifacts/visualization/grasp_geometry_explorer_v0.html`
- `40_evidence/artifacts/visualization/viz_gate0_acceptance_report.md`
- `70_tools/project_visualization/tests/viz_gate0_test_report.md`
- `40_evidence/artifacts/visualization/videos/anim_v01..v06*.mp4`
- `40_evidence/artifacts/visualization/figures/fig_v01..v10*.png`
- `40_evidence/artifacts/visualization/tables/replay_keyframe_check.csv`
- `40_evidence/artifacts/visualization/tables/asset_audit.csv`
- `40_evidence/artifacts/visualization/tables/gate_artifact_protection_manifest.csv`
- `40_evidence/artifacts/visualization/tables/frame_registry_v1.csv`
- `40_evidence/artifacts/visualization/viz_gate0_file_offline_chrome_20260714.png`
- `40_evidence/artifacts/visualization/viz_gate0_python_environment_20260714.txt`
- `40_evidence/artifacts/visualization/viz_gate0_freeze_manifest_20260714.csv`

冻结对象的逐文件哈希见 `viz_gate0_freeze_manifest_20260714.csv`。资产输入的
45 行哈希继续以 `asset_audit.csv` 为准；22 份 E1.5 证据以
`gate_artifact_protection_manifest.csv` 为准。

## 后续研究命名与写入边界

- 研究仪表板必须命名为
  `40_evidence/artifacts/visualization/project_visualization_v1_research.html`。
- P0-A 仅写入 `30_simulation/e15_core_coverage/` 专用树。
- P0-B 仅写入 `30_simulation/e15_ancf_certification/` 专用树。
- P0-C 仅写入 `30_simulation/e16_sync_capture/` 专用树。
- 三条功能线完成前，不得启动 E2、G3、视觉或 HIL。
- 唯一集成任务不得与三个功能任务并发修改共享合同或结果文件。
- 未收敛柔性结果必须保持 UNKNOWN；不得填零、不得进入排序或代理训练。

## 科学边界

本冻结合同只证明三维场景、回放、证据语义和离线展示链闭合，不证明存在
SAFE 候选。当前仍为 `admissible 0/72`、Line A PASS、Line B/C REPEAT。
`UNKNOWN ≠ 不安全`，`EVIDENCE_MISSING ≠ 物理不安全`。
