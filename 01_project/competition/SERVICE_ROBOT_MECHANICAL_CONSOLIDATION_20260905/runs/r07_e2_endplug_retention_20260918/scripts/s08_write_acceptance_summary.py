# -*- coding: utf-8 -*-
# s08: 汇总 R07-E2 机器验收摘要（ACCEPTANCE_SUMMARY.json，UTF-8/LF）
import io, json, os

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

summary = {
    "run": "r07_e2_endplug_retention_20260918",
    "ticket": "R07-E2",
    "scope": "R07 父票的 E2 一边：纵梁→端塞横向保持（数字几何候选）；E1/E3/E4 与 A/B 支承不动",
    "status": "DIGITAL_GEOMETRY_CANDIDATE_COMPLETE_WITH_NOT_RUNS",
    "parent_ticket_closure": "NOT_CLOSED; 父票 R07 不关闭，仅 E2 一边完成数字几何候选",
    "geometric_truth_registration": {
        "T1_plug_section": "WP02 源 9.8×9.8（字面将与 8×8 内孔单边干涉 0.9）vs WP03 重建 7.8×7.8（单边隙 0.1 SLIP_FIT_CANDIDATE）；原票文字 7.8对8 与 WP03 重建一致；WP02 只读不改",
        "T2_paired_holes_preexist": "X=±164 竖向 Ø4.5 对偶孔两侧均已存在（纵梁双壁贯穿 + 端塞竖向贯穿）；E2 不新增任何孔、不修改任何既有构件",
        "T3_crossing_conflict": "端塞竖向孔轴与既有 M4 端面螺钉包络(Ø4, x∈[161,183])塞心十字相交；全长竖销不可行（十字开孔销韧带 0.1 mm 无效，已否决）→ 分段短销，尖端让开 0.1 mm，装序无关"
    },
    "design": {
        "stations": 8,
        "station_ids": ["H01","H02","H03","H04","H05","H06","H07","H08"],
        "concept": "分段横向保持：每站两枚 Ø4.4 短销/栓经既有 Ø4.5 对偶孔分自两端穿入，各穿一壁+入塞 1.8 mm；sz=+1 站=外(+z)带头短栓+OD9 垫圈 / 舱内(−z)带头短栓+OD7 垫圈；sz=−1 站=舱内(+z)带头短栓+OD7 垫圈 / 翼侧(−z)无头压装销(PRESS_FIT_CANDIDATE+翼根垫板物理止动 REGISTERED_SECONDARY)",
        "shank_diameter_mm": 4.4,
        "plug_engagement_per_stub_mm": 1.8,
        "tip_to_m4_screw_clearance_mm": 0.1,
        "wing_pin_to_pad_clearance_mm": 0.2,
        "bay_washer_od_mm": 7,
        "bay_washer_od_note": "OD7 收窄避剪力板(y≤±103.15)，隙 0.5；外侧垫圈 OD9",
        "new_part_count": 28,
        "new_part_breakdown": {"stub": 12, "washer": 12, "wing_pin": 4},
        "param_block": "20_engineering/service_robot_wp03_spacecraft_body_r1/design_parameters.json::transverse_retention_r07_e2",
        "model_entry": "spacecraft_model.py::transverse_retention_spec(P)/transverse_retention_parts(P)；build() 直接消费；rootadd 无改动（无新孔）"
    },
    "registration_tables": {
        "dual_hole_pairs_rows": 8,
        "fastener_stacks_rows": 8,
        "mounting_surfaces_rows": 8,
        "tool_paths_rows": 8,
        "files": [
            "evidence/e2_dual_hole_pairs_8.json/.csv",
            "evidence/e2_fastener_stacks_8.json/.csv",
            "evidence/e2_mounting_surfaces.json",
            "evidence/e2_tool_paths.json"
        ]
    },
    "smoke": {
        "baseline_instances_e1_closed": 431,
        "expected_instances": 459,
        "actual_instances": 459,
        "e2_instances": 28,
        "composition": "459 = 431 + 28（12 短栓 + 12 垫圈 + 4 无头销）",
        "model_valid": True,
        "verdict": "PASS",
        "evidence": "logs/s07_build_smoke_log.json"
    },
    "readback": {
        "verdict": "PASS",
        "hole_counts": {"longeron_vertical_each": 2, "plug_vertical_each": 1},
        "coaxial_pairs": 8,
        "max_axis_offset_mm": 0.0,
        "max_parallel_deviation": 0.0,
        "iteration": "s05 V1 判据缺陷 FAIL（塞心平面环外点合法带误判）保留于 evidence/acc_readback_holes_coaxial_V1_CRITERION_FAIL.json；s05b 判据修正后 PASS；几何 V1 即定稿无参数迭代",
        "evidence": "evidence/acc_readback_holes_coaxial.json"
    },
    "boolean_interference": {
        "verdict": "PASS",
        "verdict_semantics": "PASS 口径=无 E2 新增干涉；既有项见 registered_*（结转登记、不覆盖、不静默剔除）",
        "pairs_checked": {"A_e2_vs_other": 68, "B_e2_vs_e2": 12, "C_named_clearance_checks": 64},
        "new_positive_pairs": 0,
        "max_common_volume_mm3": 0.0,
        "sampling_points_inside_neighbor": 0,
        "registered_preexisting_carried_forward": [
            {"pair": ["RB_upper_beam_160", "shear_web_screw_-1_150_94"], "common_volume_mm3": 0.4610888343501606, "bit_identical_to_e1_registration": True},
            {"pair": ["RB_upper_beam_160", "shear_web_screw_1_150_94"], "common_volume_mm3": 0.46108883435016085, "bit_identical_to_e1_registration": True}
        ],
        "registered_thread_engagement_convention": "8 对端塞 vs M4 端面螺钉包络重叠 49.7134–49.7157 mm³ = WP02 螺纹啮合表示惯例（Ø4 栓入 Ø3.3 导孔）；两者均未被 E2 修改",
        "evidence": "evidence/acc_interference_boolean.json"
    },
    "mass_delta": {
        "added_part_count": 28,
        "modified_member_count": 0,
        "added_volume_mm3": 3337.860504,
        "removed_volume_mm3": 0.0,
        "net_allocated_mass_delta_kg": 0.0,
        "net_al_candidate_mass_delta_kg": 0.009012223,
        "material_status": "UNKNOWN; 全部 28 件无螺纹包络 NOT_ALLOCATED（净分配质量增量 0 为如实登记，非零填）；铝 2.7e-6 当量仅供预算",
        "evidence": "evidence/e2_bom_mass_delta.json"
    },
    "cross_run_consistency": {
        "longeron_step_vs_e1": "4/4 归一化 OCC 时间戳后逐位一致（E2 未触碰纵梁直接证据）；原始 sha256 因 STEP 头时间戳不同"
    },
    "results_receipt_change": {
        "file": "20_engineering/service_robot_wp03_spacecraft_body_r1/results/service_structure_instances.json",
        "cause": "s06/s07 构建副作用：回执须匹配现行源码（同 R01/E1 模式）",
        "old_version_backup": "logs/service_structure_instances.json.pre_e2_smoke_bak",
        "restore": "NOT_RESTORED（回执语义=现行源码实例数）"
    },
    "not_run": [
        "独立第三方复验（独立复算/复跑）",
        "载荷/强度校核：短销剪切、承压（入塞 1.8 mm SHORT_ENGAGEMENT_REGISTERED）、滑移、压配保持力、振动脱出",
        "紧固件选型/配合等级/防松/材料（全部 UNSELECTED/UNKNOWN）",
        "制造性审查：0.05 mm/边配合隙、0.1 mm 尖端让隙、0.2 mm 翼侧间隙公差堆叠；无头销压装工艺",
        "工具路径实物回放（仅几何可达性登记；舱内件建议根框阶段施装）",
        "翼侧无头销装后更换须拆翼根叉（NEEDS_SEQUENCE_REVIEW）",
        "实物试配/装配"
    ],
    "constraints_honored": [
        "E1/E3/E4 与 A/B 支承未动",
        "未改写 gate/issues.json/CURRENT 指针",
        "WP02 文件只读",
        "未执行 git 提交",
        "UNKNOWN 零填禁止（质量 NOT_ALLOCATED 如实登记）",
        "FAIL 不覆盖（s05 V1 判据 FAIL 保留）"
    ]
}

out = os.path.join(RUN, "ACCEPTANCE_SUMMARY.json")
with open(out, "wb") as f:
    f.write((json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
print("WROTE", out)
