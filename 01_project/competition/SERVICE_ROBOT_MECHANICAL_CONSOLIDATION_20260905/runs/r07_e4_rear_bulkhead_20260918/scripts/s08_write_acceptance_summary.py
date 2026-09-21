# -*- coding: utf-8 -*-
# s08: 汇总 R07-E4 机器验收摘要（ACCEPTANCE_SUMMARY.json，UTF-8/LF）
import io, json, os

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

summary = {
    "run": "r07_e4_rear_bulkhead_20260918",
    "ticket": "R07-E4",
    "scope": "R07 父票的 E4 边：connection_edges 第 3 边（ADAPTER_CONNECTION_REDESIGN）端框→后发射保留隔框星内侧连接闭合（数字几何候选）；E1/E2/E3 与 A/B 支承（rear 肋）不动；供应方侧（保留体积/窗口外段/肋）参数化不动；front_service_cover OUT_OF_SCOPE（原票仅指后端框）",
    "status": "DIGITAL_GEOMETRY_CANDIDATE_COMPLETE_WITH_NOT_RUNS",
    "parent_ticket_closure": "NOT_CLOSED; 父票 R07 不关闭，仅 E4 边完成数字几何候选",
    "geometric_truth_registration": {
        "gap_face_contact_no_clamp": "隔框 x[-189,-183] 与端框 x[-183,-177] 于 x=-183 面贴合，Common 体积 0.0：当前构建仅面贴合、无夹紧件=原票缺口（s00b 实读）",
        "no_new_holes": "本边零新增孔：Ø8 窗口（隔框）/Ø4.5 孔（端框）/Ø3.3 导孔（端塞）均既有未改",
        "original_screw_recessed": "原 M4×22 头 x[-187,-183] recessed 于窗口内（径向隙 0.5），隔框外侧面无承压件",
        "corner_avoidance": "rear 肋 x[-195,-189] y/z∈[77,95] 带与角区 ±103.65 之外不交；保留体积 x[-215,-195] r60 角区径向 151.5 不入侵；E2 分段销站位 x=-164 Z 向与新头位 x[-195,-191] 间隙 ≈16.8",
        "front_cover_out_of_scope": "前端框→front_service_cover 连接登记 OUT_OF_SCOPE（原票仅指后端框）"
    },
    "design": {
        "clamp_sleeve": {
            "groups": 4,
            "group_ids": ["1_1", "1_-1", "-1_1", "-1_-1"],
            "part_count": 4,
            "concept": "阶梯夹套：筒 OD7.9×6 滑入既有 Ø8 窗口（x[-189,-183]，隙 0.05/边）+ 法兰 OD12×2 压隔框外面（x[-191,-189]，承压环 Ø8→Ø12）+ ID Ø4.5 过 M4 杆（隙 0.25/边）；FOUR_SLEEVE_POSITIVE",
            "mass_status": "真实铝候选 CAD_ESTIMATE（density 2.7e-6，E1 防压套先例；GOLD/PHYSICAL_GEOMETRY）；材料牌号/压溃/承压 UNKNOWN 非零填"
        },
        "modified_screw": {
            "part_count": 4,
            "same_name_replaced": ["RB_end_screw_-1_1_1", "RB_end_screw_-1_1_-1", "RB_end_screw_-1_-1_1", "RB_end_screw_-1_-1_-1"],
            "concept": "M4×22→M4×30 包络延长：锚点 x=-183→-191（压套法兰），头 x[-195,-191]，杆 x[-191,-161]；延长仅在头侧，尖端 x=-161 与端塞啮合段 x[-177,-161] 逐位不变",
            "mass_status": "无螺纹名义包络 SIMPLIFIED_PROXY / NOT_ALLOCATED；pn 候选 WP01-MT-M4X30-E4-ENVELOPE_WP03"
        },
        "new_part_count": 4,
        "modified_part_count": 4,
        "param_block": "20_engineering/service_robot_wp03_spacecraft_body_r1/design_parameters.json::rear_bulkhead_clamp_r07_e4",
        "model_entry": "spacecraft_model.py::rear_bulkhead_clamp_spec/parts + build() 消费（ROOT_STRUCTURE, GOLD, 默认 density）；root_structure rootadd 拦截 RB_end_screw_-1_（M4×30 复合圆柱，xyz 改 -191，pn 换）"
    },
    "iteration_history": {
        "s05_readback_FAIL_v1": "两处判据缺陷：① 尖端判据误用 bb.min.X（尖端在 max 侧 -161）；② 端塞导孔按面计数=1 过严（Ø3.3 导孔被 x=-164 Z 向 E2 分段销孔 Ø4.5 横穿劈为 2 个同轴圆柱面，几何事实探针核实）；归档 evidence/acc_readback_holes_coaxial_v1_fail.json（FAIL 不覆盖，内容未改仅改名）",
        "s05_readback_v2_fix": "尖端判据改 bb.max.X；导孔改按唯一轴(y,z)计数=1/塞 → PASS",
        "probe_v1_first_pass": "s01c 探针 v1 即过：hits 0、实例 487、螺纹惯例 4 对跳过（logs/s01c_probe_v1.log），无几何迭代"
    },
    "registration_tables": {
        "dual_hole_pairs_rows": 4,
        "fastener_stacks_rows": 4,
        "mounting_surfaces_rows": 4,
        "tool_paths_rows": 4,
        "files": [
            "evidence/e4_dual_hole_pairs_4.json/.csv",
            "evidence/e4_fastener_stacks_4.json/.csv",
            "evidence/e4_mounting_surfaces.json",
            "evidence/e4_tool_paths.json"
        ]
    },
    "smoke": {
        "baseline_instances_e3_closed": 483,
        "expected_instances": 487,
        "actual_instances": 487,
        "e4_instances": 4,
        "composition": "487 = 483 + 4（clamp_sleeve 4）；改件螺钉 4 件同名替换不增数",
        "model_valid": True,
        "verdict": "PASS",
        "evidence": "logs/s07_build_smoke_log.json"
    },
    "readback": {
        "verdict": "PASS",
        "version": "v2（v1 FAIL 判据缺陷已归档 evidence/acc_readback_holes_coaxial_v1_fail.json）",
        "hole_counts": {
            "rear_launch_bulkhead_d8_windows": "4（既有未改）",
            "RB_end_frame_-1_d4p5_holes": "4（既有未改）",
            "RB_end_plug_-1_*_d3p3_pilot": "1 轴/塞（既有未改；同孔被分段销孔横穿劈 2 面，按唯一轴计数）"
        },
        "coaxial_pairs": "4 角 × 6 对（窗口轴 vs 套 ID 轴 vs 端框孔轴 vs 栓杆轴）",
        "max_axis_offset_mm": 0.0,
        "max_parallel_deviation": 0.0,
        "screw_tip_truth": "改件螺钉 bbox x∈[-195,-161]，尖端 -161 与 M4×22 基线逐位一致",
        "evidence": "evidence/acc_readback_holes_coaxial.json"
    },
    "boolean_interference": {
        "verdict": "PASS",
        "verdict_semantics": "PASS 口径=无 E4 新增干涉；既有项见 registered_*（结转登记、不覆盖、不静默剔除）",
        "authoritative_method": "OCP BRepAlgoAPI_Common 原生 + BRepGProp.VolumeProperties_s（E2 审阅勘误 O2；禁用 build123d Shape.intersect）",
        "pairs_checked": {
            "A_e4_vs_other": 30,
            "B_e4_vs_e4": 4,
            "C_named_clearance_checks": 38
        },
        "named_clearance_pass": "38/38",
        "new_positive_pairs": 0,
        "max_common_volume_mm3": 0.0,
        "sampling_points_inside_neighbor": 0,
        "sampling_note": "0.4mm 网格 58340 点对照 0 命中；薄壁/环形承压区盲区已声明，布尔为权威口径",
        "registered_preexisting_carried_forward": [
            {
                "pair": ["RB_upper_beam_160", "shear_web_screw_-1_150_94"],
                "common_volume_mm3": 0.4610888343501606,
                "bit_identical_to_e1_registration": True
            },
            {
                "pair": ["RB_upper_beam_160", "shear_web_screw_1_150_94"],
                "common_volume_mm3_now": 0.4610888343501606,
                "e1_registered_mm3": 0.46108883435016085,
                "bit_identical_to_e1_registration": False,
                "note": "末位差 2.5e-16：求积路径差异；如实登记不覆盖（同 E2/E3）"
            }
        ],
        "registered_thread_engagement_convention": "8 对端塞 vs M4 螺钉包络重叠（49.71mm³ 级）与 E3 登记逐位一致 8/8；后场 4 对 screw_modified_by_e4=true 仍 bit_identical——延长仅在头侧、重叠区 x[-177,-161] 不变（方案核心预言验证）",
        "evidence": "evidence/acc_interference_boolean.json"
    },
    "mass_delta": {
        "added_part_count": 4,
        "modified_part_count": 4,
        "added_volume_mm3": 1572.241459415548,
        "added_sleeve_al_candidate_mass_kg": 0.004245051940421980,
        "sleeve_per_piece": {"volume_mm3": 393.060364853887, "mass_kg": 0.0010612629851054949},
        "modified_screw_delta_volume_mm3_per_piece": 100.5309649148732,
        "modified_screw_delta_volume_mm3_total": 402.1238596594928,
        "modified_screw_baseline": "同源复建 root_structure.screw(4,22,7,4)=430.3981935418017 mm³（体积平移不变量）；现值 530.9291584566749=screw(4,30,7,4)；解析 π·2²·8=100.5309649148734 吻合",
        "removed_volume_mm3": 0.0,
        "removed_volume_note": "零新增孔，无构件去除",
        "net_allocated_mass_delta_kg": 0.004245051940421980,
        "material_status": "UNKNOWN; 夹套为真实铝候选 CAD_ESTIMATE（E1 先例，非零填）；改件螺钉包络 NOT_ALLOCATED（前后同口径，体积差仅供预算）",
        "evidence": "evidence/e4_bom_mass_delta.json"
    },
    "results_receipt_change": {
        "file": "20_engineering/service_robot_wp03_spacecraft_body_r1/results/service_structure_instances.json",
        "cause": "s06/s07 构建副作用：回执须匹配现行源码（同 R01/E1/E2/E3 模式）",
        "old_version_backup": "logs/service_structure_instances.json.pre_e4_smoke_bak",
        "restore": "NOT_RESTORED（回执语义=现行源码实例数）"
    },
    "not_run": [
        "独立第三方复验（独立复算/复跑）",
        "载荷/强度校核：夹套法兰承压环（Ø8→Ø12）压溃/承压、隔框窗口壁承压、M4 栓拉伸/剪切、贴合面夹紧力与预紧（面贴合零体积连接首次引入夹紧件）",
        "紧固件选型/配合等级/防松/材料（全部 UNSELECTED/UNKNOWN；夹套材料牌号 UNKNOWN）",
        "供应方侧 ICD：部署器孔系/分离接口 UNKNOWN（保留体积/窗口外段/肋参数化未动，不臆造）",
        "制造性审查：0.05/0.25mm 每边配合隙、阶梯套筒内外圆同轴工艺、法兰 2mm 薄壁",
        "工具路径实物回放（仅几何可达性登记）",
        "前端框→front_service_cover 连接（OUT_OF_SCOPE 登记）",
        "部署器对接实物验证；实物试配/装配"
    ],
    "constraints_honored": [
        "E1/E2/E3 与 A/B 支承（rear 肋）未动",
        "供应方侧（保留体积/窗口外段/肋）参数化未动",
        "未改写 gate/issues.json/CURRENT 指针",
        "WP02 文件只读",
        "未执行 git 提交",
        "UNKNOWN 零填禁止（材料/选型 UNKNOWN 如实登记；夹套质量为 CAD_ESTIMATE 非零填）",
        "FAIL 不覆盖（s05 v1 FAIL 归档 evidence/acc_readback_holes_coaxial_v1_fail.json）"
    ]
}

p = os.path.join(RUN, "ACCEPTANCE_SUMMARY.json")
with open(p, "wb") as f:
    f.write((json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
print("written", p)
