# 终版原生哈希清单说明（增补，2026-07-25）

`native_file_hash_manifest.csv`（55 项）生成于 B3 评审整改之前。整改期两项已记录变更
未反映其中：

1. 顶装 `Assembly/Spacecraft_Service_Vehicle_V2_0.SLDASM` 因配置状态修复重新保存
   （b3_10_fix_configs，见 `build_logs/b3_10_fix_configs.jsonl`）；
2. 独立 target 场景两文件（`10_Review_Overlays/target_scene_independent/`）由视图阶段
   （b3_10_views）创建，晚于清单导出。

本终版清单 `native_file_hash_manifest_v2_final.csv`（57 项）为 V2.0 交付态封存权威；
原清单保留作历史，不删除不改写。V2.1（B4-1）入口封存复核以本终版清单为准
（`Space_Embodied_Robot_CAD_V2_1/evidence/b4_1_00/v2_0_seal_recheck.json`）。
