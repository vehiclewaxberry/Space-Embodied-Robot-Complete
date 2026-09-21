# -*- coding: utf-8 -*-
# s08: 汇总 R07-E1 机器验收摘要（ACCEPTANCE_SUMMARY.json，UTF-8/LF）
import io, json, os

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

summary = {
    "run": "r07_root_longeron_anchoring_20260917",
    "ticket": "R07-E1",
    "scope": "R07 父票的 E1 一边：根部桥/上下横梁 -> 主纵梁锚固（数字几何候选）；E2-E4 与 A/B 支承不动",
    "status": "DIGITAL_GEOMETRY_CANDIDATE_COMPLETE_WITH_NOT_RUNS",
    "parent_ticket_closure": "NOT_CLOSED; 父票 R07 不关闭，仅 E1 一边完成数字几何候选",
    "design": {
        "anchor_groups": 10,
        "group_ids": ["G01","G02","G03","G04","G05","G06","G07","G08","G09","G10"],
        "bolt_positions_total": 16,
        "longeron_bolt_z_mm": [105.3, -105.3],
        "bridge_bolt_z_mm": 109.0,
        "x20_station_bolt_x_mm": [15.5, 24.5],
        "x160_station_bolt_x_mm": 154.85,
        "bridge_bolt_x_mm": [40.0, 146.0],
        "x160_secondary_anti_rotation": "REGISTERED（单栓 + 二级防转登记）",
        "anti_crush_sleeve_mm": {"outer_d": 4.0, "inner_d": 3.4, "length": 8.0},
        "param_block": "20_engineering/service_robot_wp03_spacecraft_body_r1/config/design_parameters.json::root_anchoring_r07_e1",
        "model_entry": "spacecraft_model.py::root_anchoring_spec(P)/root_anchoring_parts(P)；rootadd 打 E1 孔 delta；受影响件 pn 加 _WP03"
    },
    "registration_tables": {
        "dual_hole_pairs_rows": 16,
        "fastener_stacks_rows": 16,
        "mounting_surfaces_rows": 10,
        "tool_paths_rows": 10,
        "files": [
            "evidence/e1_dual_hole_pairs_16.json/.csv",
            "evidence/e1_fastener_stacks_16.json/.csv",
            "evidence/e1_mounting_surfaces.json",
            "evidence/e1_tool_paths.json"
        ]
    },
    "smoke": {
        "baseline_instances_r01_closed": 383,
        "expected_instances": 431,
        "actual_instances": 431,
        "anchor_instances": 48,
        "composition": "431 = 383 + 48（16 栓包络 + 16 垫圈包络 + 16 防压套）",
        "model_valid": True,
        "verdict": "PASS",
        "evidence": "logs/s07_build_smoke_log.json"
    },
    "readback": {
        "verdict": "PASS",
        "hole_counts": {"RB_longeron_each_top_bottom": "5/3（含两侧端）", "upper_beam_x20_x160": "4/2", "lower_beam_x20_x160": "4/2", "bridge": 4},
        "coaxial_pairs": 16,
        "max_axis_offset_mm": 1.4210854715202004e-14,
        "max_parallel_deviation": 0.0,
        "evidence": "evidence/acc_readback_holes_coaxial.json"
    },
    "boolean_interference": {
        "verdict": "PASS",
        "verdict_semantics": "PASS 口径=无 E1 新增干涉；既有相邻对登记不覆盖、不静默剔除",
        "pairs_checked": {"A_anchor_vs_anchor": 110, "B_anchor_vs_other": 32, "C_other_vs_other": 205},
        "new_positive_pairs": 0,
        "named_zero_clearance_checks": 96,
        "sampling_points": 68368,
        "sampling_hits": 0,
        "max_common_volume_mm3": 0.46108883435016085,
        "max_common_volume_attribution": "PRE_EXISTING_NOT_INTRODUCED_BY_E1",
        "registered_preexisting": [
            {
                "pair": ["RB_upper_beam_160", "shear_web_screw_-1_150_94"],
                "common_volume_mm3": 0.4610888343501606,
                "control": "UNMODIFIED_WP02_BEAM_COMMON_VOLUME",
                "control_bit_identical_to_e1_build": True,
                "mirrored_pair": ["RB_upper_beam_160", "shear_web_screw_1_150_94"]
            }
        ],
        "evidence": "evidence/acc_interference_boolean.json"
    },
    "mass_delta": {
        "added_part_count": 48,
        "modified_member_count": 9,
        "added_volume_mm3": 4058.812048,
        "removed_volume_mm3": 2324.275907,
        "net_volume_mm3": 1734.536141,
        "net_al_candidate_mass_delta_kg": 0.004683239,
        "material_status": "UNKNOWN; 铝 2.7e-6 kg/mm3 仅 CANDIDATE 估算；栓/垫圈为无螺纹包络，质量未分配（AL_EQUIVALENT 仅供预算）",
        "evidence": "evidence/e1_bom_mass_delta.json"
    },
    "iteration_history_fail_not_overwritten": {
        "V1": {"defect": "防压套侵入管壁", "max_intrusion_mm3": 28.854630126389758, "pairs": 34},
        "V2": {"defect": "同站位双栓互侵", "max_intrusion_mm3": 15.208025245922368, "pairs": 12},
        "V3": {"verdict": "PASS"},
        "process_deviation": "V1/V2 FAIL JSON 被同名覆盖（数值已入档 PATCH_NOTES）；自 V3 起 FAIL 文件带版本后缀"
    },
    "results_receipt_change": {
        "file": "20_engineering/service_robot_wp03_spacecraft_body_r1/results/service_structure_instances.json",
        "cause": "s07 烟测副作用：回执须匹配现行源码（同 R01 模式）",
        "old_version_backup": "logs/service_structure_instances.json.pre_e1_smoke_bak",
        "restore": "NOT_RESTORED（回执语义=现行源码实例数）"
    },
    "not_run": [
        "独立第三方复验（独立复算/复跑）",
        "载荷/强度校核（拉剪、承压、滑移、预紧、有效啮合长度）",
        "紧固件选型/防松/材料确认",
        "0.15 mm 栓孔边距与 0.3 mm 薄壁套的制造性审查",
        "工具路径实物回放（仅几何可达性登记）",
        "R14 参数扰动敏感性",
        "实物试配/装配"
    ],
    "constraints_honored": [
        "E2-E4 与 A/B 支承未动",
        "未改写 gate/issues.json/CURRENT 指针",
        "WP02 文件只读",
        "未执行 git 提交"
    ]
}

out = os.path.join(RUN, "ACCEPTANCE_SUMMARY.json")
with open(out, "wb") as f:
    f.write((json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
print("WROTE", out)
