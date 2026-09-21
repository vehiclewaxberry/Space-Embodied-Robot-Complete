# -*- coding: utf-8 -*-
"""R07-E2 独立复验 r35：汇总 REVIEW_VERDICT.json + 全部二进制 LF .sha256 边车。"""
import json, time
from pathlib import Path
from e2_common import REV, RUN, write_json, sidecar

EV = REV / 'evidence'


def main():
    r30 = json.loads((EV / 'review_e2_readback.json').read_text(encoding='utf-8'))
    nc = json.loads((EV / 'review_e2_negative_controls.json').read_text(encoding='utf-8'))
    pre = json.loads((EV / 'review_e2_preexisting.json').read_text(encoding='utf-8'))
    scan = json.loads((EV / 'review_e2_scan.json').read_text(encoding='utf-8'))
    spot = json.loads((EV / 'review_e2_spotcheck.json').read_text(encoding='utf-8'))

    subs = {'readback': r30['verdict'], 'negative_controls': nc['verdict'],
            'preexisting_check': pre['verdict'], 'new_interference_scan': scan['verdict'],
            'spotcheck': spot['verdict']}
    all_pass = all(v == 'PASS' for v in subs.values())

    observations = [
        {'id': 'O1', 'topic': '十字开孔全长销韧带数值定义差异',
         'detail': 'NC-a 解析韧带 (Ø4.4-Ø4.0)/2=0.2 mm/边；候选方登记 0.1 mm。'
                   '两者同量级且均结构无效，全长销几何不可共存结论双方一致（分段短销方案的否决依据不受影响）。'},
        {'id': 'O2', 'topic': '工具勘误：build123d Shape.intersect 静默 None 陷阱',
         'detail': 'import_step 读回件作第一参数时，Shape.intersect 对部分组合选择性静默返回 None'
                   '（实测：导入栓.intersect(导入塞)=None，而同对几何 OCC 原生 BRepAlgoAPI_Common 正常出值）。'
                   '把 None 当 0.0 会把失败布尔伪装成零干涉。本审阅全部布尔已切换 OCP.BRepAlgoAPI_Common '
                   '原生路径（Build 失败返回 error dict，绝不当 0），r30/r31 已在修复后整轮重跑，结论不变。'
                   '对 E1 已交付审阅的影响：仅 NC-c 真实栓对照 0.0（导入栓.intersect(剪力板螺钉包络)）'
                   '走过受影响路径；该对解析可证真零——G03_0 栓 z∈[102.55,108.05]（头 Ø5.5 @ z=105.3±2.75），'
                   '剪力板螺钉包络 z∈[92.5,95.5]（Ø3 绕 z=94），z 向区间不相交（最小间距 7.05 mm），'
                   'E1 结论不受影响。建议后续所有审阅/被审脚本统一 OCC 原生布尔路径。'},
        {'id': 'O3', 'topic': '登记布尔值的实现路径依赖（≈5e-5 相对）',
         'detail': '49.71 mm³ 螺纹咬合惯例八对：被审方 build123d 路径登记值 vs 本审阅 OCC 路径复算值 '
                   '系统差 1.9e-3~2.6e-3 mm³（OCC 圆柱-圆柱相交曲线剖分的路径依赖；探针 _work/probe_boolean_'
                   'path_attribution.py 已归因，build123d 路径可复现登记值：sx=+1 四站逐位、sx=-1 四站 6.7e-5 内）。'
                   '该对为登记性数值（WP02 螺纹啮合表示惯例），非 Gate 判据；全部 Gate 相关对的零/非零语义 '
                   '在两条路径下一致，不影响任何 Gate 结论。E1 结转 0.461 mm³ 对存在同型 1ulp(2.2e-16) 漂移。'},
        {'id': 'O4', 'topic': '入塞 1.8 mm 保持有效性（SHORT_ENGAGEMENT_1.8MM_REGISTERED）',
         'detail': '短销/栓每枚仅入塞 1.8 mm 承压；剪/承压许用、滑移、振动脱出全部 UNKNOWN/NOT_RUN，'
                   '已如实登记于 e2_mounting_surfaces.json 与 ACCEPTANCE_SUMMARY not_run。'
                   '本复验仅覆盖数字几何候选，不构成保持有效性证明。'},
        {'id': 'O5', 'topic': '翼侧无头销装后更换须拆翼根叉（NEEDS_SEQUENCE_REVIEW）',
         'detail': '已在 e2_tool_paths.json 登记（翼侧销须在 wing_root_fork 装入前压装；'
                   '装后更换须先拆翼根叉）；装序审查 NOT_RUN。压配保持力 PRESS_FIT_UNKNOWN 保留。'},
        {'id': 'O6', 'topic': '0.05/0.1/0.2 mm 公差堆叠制造性审查 NOT_RUN',
         'detail': '栓孔配合隙 0.05 mm/边、尖端让 M4 螺钉包络 0.1 mm、翼销让垫板 0.2 mm 的公差堆叠'
                   '制造性审查 NOT_RUN；材料/配合等级/防松/紧固件选型 UNSELECTED/UNKNOWN 保留，'
                   '零填充禁止已遵守（净分配质量增量 0.0 为 NOT_ALLOCATED 如实登记，铝当量仅供预算）。'},
    ]

    verdict = {
        'review': 'R07_E2_INDEPENDENT_REVERIFY',
        'review_run': 'r07_e2_endplug_retention_review_20260918',
        'reviewed_run': RUN.name,
        'reviewed_commit': '90cd8d1f',
        'reviewer_role': 'WP03 R07-E2 独立审阅者（只读；不改候选；不执行 git 提交）',
        'scope': '仅 R07 父票 E2 一边（纵梁→端塞横向保持，8 站 28 件分段短销/栓+垫圈+翼侧压装销）'
                 '数字几何候选的独立复验；E1/E3/E4 与 A/B 支承不在本次范围',
        'basis_pins': {
            'params_sha256': r30['params_sha256'],
            'params_sha256_pin_ok': r30['params_sha256_pin_ok'],
            'source_sha256': scan['basis_pin']['spacecraft_model.py']['actual'],
            'source_pin_ok': scan['basis_pin']['spacecraft_model.py']['ok'],
            'export_hash_pin': r30['export_hash_pin'],
            'snapshot_vs_git_old_state': pre['G_not_introduced_by_e2'],
        },
        'sub_verdicts': subs,
        'key_results': {
            'readback': {
                'coaxial_max_axis_offset_mm': r30['max_axis_offset_mm'],
                'stations_checked': len(r30['stations']),
                'export_hash_pin_40_of_40': r30['export_hash_pin'],
                'registration_audit': r30['registration_audit'],
                't1_plug_section_truth': r30['t1_truth'],
                'cross_run_longeron_4of4_identical': all(
                    v['normalized_identical_to_e1_export']
                    for v in r30['cross_run_longeron'].values()),
            },
            'negative_controls': {
                'NC_a_full_pin_vs_screw_positives': nc['nc_a']['positives'],
                'NC_a_full_pin_sample_mm3': nc['nc_a']['full_pin_vs_screw'][0]['common_volume_mm3'],
                'NC_a_real_stubs_16of16_zero': nc['nc_a']['detect_ok'],
                'NC_a_ligament_analytic_mm_per_side': nc['nc_a']['ligament_analytic_mm_per_side'],
                'NC_b_missing_hole_mutation_detected': nc['nc_b']['detect_ok'],
                'NC_c1_wing_pad_conflict_mutation_mm3': nc['nc_c']['c1_wing_pad']['mutated_vs_forks_common_mm3'],
                'NC_c1_real_pin_zero': nc['nc_c']['c1_wing_pad']['real_vs_forks_common_mm3'],
                'NC_c2_shifted_stub_conflict_mutation_mm3': nc['nc_c']['c2_shifted_stub']['mutated_vs_plug_common_mm3'],
                'NC_c2_real_stub_zero': nc['nc_c']['c2_shifted_stub']['real_vs_plug_common_mm3'],
            },
            'preexisting_interference': {
                'conclusion': pre['conclusion'],
                'A_e1_carried_forward_pairs': pre['summary']['A_pairs'],
                'A_build123d_path_bit_identical': all(
                    v['control_build123d_bit_identical']
                    for v in pre['A_e1_carried_forward'].values()),
                'B_thread_convention_pairs': pre['summary']['B_pairs'],
                'B_all_pass': pre['summary']['B_all_pass'],
                'boolean_path_attribution': pre['boolean_path_attribution']['finding'],
            },
            'new_interference_scan': {
                'pairs': scan['pairs'],
                'new_positives': scan['summary']['new_positives'],
                'thread_convention_positives_registered': scan['summary']['thread_convention_positives'],
                'named_clearance_checks': scan['summary']['clearance_checks'],
                'named_clearance_fail': scan['summary']['clearance_fail'],
                'e2_vs_e1_anchor_bbox_pairs': scan['summary']['e2_vs_e1_anchor_bbox_pairs'],
                'errors': len(scan['errors']),
            },
            'spotcheck_pass_ratio': spot['spotcheck_pass_ratio'],
        },
        'observations': observations,
        'limitations_carried_from_candidate': [
            '载荷/强度校核 NOT_RUN（短销剪切、承压（入塞 1.8 mm SHORT_ENGAGEMENT_REGISTERED）、滑移、压配保持力、振动脱出）',
            '紧固件选型/配合等级/防松/材料全部 UNSELECTED/UNKNOWN 保留，零填充禁止',
            '制造性审查 NOT_RUN（0.05 mm/边配合隙、0.1 mm 尖端让隙、0.2 mm 翼侧间隙公差堆叠；无头销压装工艺）',
            '工具路径仅几何可达性登记，实物回放 NOT_RUN（舱内件建议根框阶段施装）',
            '翼侧无头销装后更换须拆翼根叉（NEEDS_SEQUENCE_REVIEW），装序审查 NOT_RUN',
            '实物试配/装配 NOT_RUN',
        ],
        'whole_design_complete': False,
        'manufacturing_release': False,
        'parent_ticket_r07_closure': 'NOT_CLOSED（本复验不构成父票关闭依据）',
        'verdict': ('R07_E2_INDEPENDENT_REVERIFY_PASS_WITH_OBSERVATIONS' if all_pass
                    else 'R07_E2_INDEPENDENT_REVERIFY_FAIL__' +
                         '_'.join(k.upper() for k, v in subs.items() if v != 'PASS')),
        'verdict_semantics': 'PASS_WITH_OBSERVATIONS=全部独立机器核查通过（读回/三负控/既有核查/'
                             '新增扫描/抽验 10 项）；观察项 O1-O6 为登记/定义/工具类备注，不构成阻断；'
                             '候选维持 DIGITAL_GEOMETRY_CANDIDATE 等级，不升级为制造放行或全设计完成',
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
    }
    if not all_pass:
        verdict['blocking_failures'] = {k: v for k, v in subs.items() if v != 'PASS'}

    write_json(REV / 'REVIEW_VERDICT.json', verdict)

    # 全部边车（scripts/evidence/_work 现存产物 + 本脚本）
    done = []
    for d in (REV / 'scripts', EV, REV / '_work'):
        for f in sorted(d.iterdir()):
            if f.is_file() and not f.name.endswith('.sha256') and '__pycache__' not in f.parts:
                sidecar(f)
                done.append(f.name)
    print('verdict', verdict['verdict'])
    print('sidecars refreshed:', done)


if __name__ == '__main__':
    main()
