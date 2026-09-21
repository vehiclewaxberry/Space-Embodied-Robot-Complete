# -*- coding: utf-8 -*-
"""R07-E1 独立复验 r35：汇总 REVIEW_VERDICT.json + 全部二进制 LF .sha256 边车。"""
import json, time
from pathlib import Path
from rev_common import REV, RUN, write_json, sidecar

EV = REV / 'evidence'


def main():
    rb = json.loads((EV / 'review_readback.json').read_text(encoding='utf-8'))
    nc = json.loads((EV / 'review_negative_controls.json').read_text(encoding='utf-8'))
    pre = json.loads((EV / 'review_preexisting_interference.json').read_text(encoding='utf-8'))
    scan = json.loads((EV / 'review_new_interference_scan.json').read_text(encoding='utf-8'))
    spot = json.loads((EV / 'review_spotcheck.json').read_text(encoding='utf-8'))

    subs = {'readback': rb['verdict'], 'negative_controls': nc['verdict'],
            'preexisting_check': pre['verdict'], 'new_interference_scan': scan['verdict'],
            'spotcheck': spot['verdict']}
    all_pass = all(v == 'PASS' for v in subs.values())

    verdict = {
        'review': 'R07_E1_INDEPENDENT_REVERIFY',
        'review_run': 'r07_e1_anchoring_review_20260918',
        'reviewed_run': RUN.name,
        'reviewed_commit': '6579aee8',
        'reviewer_role': 'WP03 R07-E1 独立审阅者（只读；不改候选；不执行 git 提交）',
        'scope': '仅 R07 父票 E1 一边（桥/上下横梁→主纵梁锚固）数字几何候选的独立复验；'
                 'E2-E4 与 A/B 支承不在本次范围',
        'basis_pins': {
            'params_sha256': rb['params_sha256'],
            'source_sha256': scan['basis_pin']['spacecraft_model.py']['actual'],
            'export_hash_pin': rb['export_hash_pin'],
            'snapshot_vs_git_old_state': pre['git_old_state'],
        },
        'sub_verdicts': subs,
        'key_results': {
            'coaxial_max_axis_offset_mm': rb['max_axis_offset_mm'],
            'stations_checked': len(rb['stations']),
            'negative_controls': {
                'NC_a_V1_replay_max_mm3': nc['nc_a']['max_common_volume_mm3'],
                'NC_a_V1_registered_mm3': nc['nc_a']['replay_vs_registered_max']['registered_v1_max_mm3'],
                'NC_a_V1_positives': nc['nc_a']['positive_count'],
                'NC_a_V3_control_positives': len(nc['nc_a']['v3_control_positives']),
                'NC_a2_V2_replay_max_mm3': nc['nc_a2']['max_common_volume_mm3'],
                'NC_a2_V2_registered_mm3': nc['nc_a2']['replay_vs_registered_max']['registered_v2_max_mm3'],
                'NC_a2_V2_positives': nc['nc_a2']['positive_count'],
                'NC_b_mutation_detection': nc['nc_b']['detect_ok'],
                'NC_c_conflict_mutation_mm3': nc['nc_c']['mutated_bolt_vs_screw_common_mm3'],
                'NC_c_real_bolt_control_mm3': nc['nc_c']['real_G03_0_bolt_vs_same_screw_common_mm3'],
            },
            'preexisting_interference': {
                'conclusion': pre['conclusion'],
                'recomputed': {k: {'control_mm3': v['control_unmodified_beam_mm3'],
                                   'control_bit_identical': v['control_bit_identical']}
                               for k, v in pre['recomputed'].items()},
            },
            'new_interference_scan': {
                'pairs': scan['pairs'],
                'new_positives': len(scan['positives_new']),
                'registered_preexisting_positives': len(scan['positives_registered_preexisting']),
                'named_clearance_checks': len(scan['explicit_clearance_checks']),
                'named_clearance_all_pass': all(c['pass'] for c in scan['explicit_clearance_checks']),
            },
            'spotcheck_consistency': spot['consistency_rate'],
        },
        'observations': spot['observations'],
        'limitations_carried_from_candidate': [
            '载荷/强度校核 NOT_RUN（拉剪/承压/滑移/预紧/有效啮合）',
            '材料/等级/预紧/防松/有效啮合 UNKNOWN 保留，零填充禁止',
            '0.15mm 栓孔边距与 0.3mm 薄壁套制造性审查 NOT_RUN',
            '工具路径仅几何可达性登记，实物回放 NOT_RUN',
            'R14 参数扰动敏感性 NOT_RUN',
            '实物试配/装配 NOT_RUN',
        ],
        'whole_design_complete': False,
        'manufacturing_release': False,
        'parent_ticket_r07_closure': 'NOT_CLOSED（本复验不构成父票关闭依据）',
        'verdict': ('R07_E1_INDEPENDENT_REVERIFY_PASS_WITH_OBSERVATIONS' if all_pass
                    else 'R07_E1_INDEPENDENT_REVERIFY_FAIL'),
        'verdict_semantics': 'PASS_WITH_OBSERVATIONS=全部独立机器核查通过；观察项 O1-O6 为登记/'
                             '流程类备注，不构成阻断；候选维持 DIGITAL_GEOMETRY_CANDIDATE 等级，'
                             '不升级为制造放行或全设计完成',
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
    }
    if not all_pass:
        verdict['blocking_failures'] = {k: v for k, v in subs.items() if v != 'PASS'}

    write_json(REV / 'REVIEW_VERDICT.json', verdict)

    # 全部边车（scripts/evidence/_work 现存产物 + 本脚本）
    done = []
    for d in (REV / 'scripts', EV, REV / '_work'):
        for f in sorted(d.iterdir()):
            if f.is_file() and not f.name.endswith('.sha256'):
                sidecar(f)
                done.append(f.name)
    print('verdict', verdict['verdict'])
    print('sidecars refreshed:', done)


if __name__ == '__main__':
    main()
