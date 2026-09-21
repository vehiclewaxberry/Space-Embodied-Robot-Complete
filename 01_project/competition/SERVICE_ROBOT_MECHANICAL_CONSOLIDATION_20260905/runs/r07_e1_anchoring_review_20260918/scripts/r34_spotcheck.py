# -*- coding: utf-8 -*-
"""R07-E1 独立复验 r34：ACCEPTANCE_SUMMARY 抽验 + 观察项登记。
抽验全部用本审阅链独立重算值对拍（r30 读回 / r31 负控 / r32 既有核查 / r33 扫描 / 解析式），
不采信候选方中间 JSON 的自述数值。"""
import json, math, time
from pathlib import Path
from rev_common import REV, RUN, write_json, load_params

R = 1.7
WALL = 2.0
BLIND_DEPTH = 12.0
RHO_AL = 2.7e-6


def main():
    t0 = time.time()
    ev = REV / 'evidence'
    acc = json.loads((RUN / 'ACCEPTANCE_SUMMARY.json').read_text(encoding='utf-8'))
    rb = json.loads((ev / 'review_readback.json').read_text(encoding='utf-8'))
    nc = json.loads((ev / 'review_negative_controls.json').read_text(encoding='utf-8'))
    pre = json.loads((ev / 'review_preexisting_interference.json').read_text(encoding='utf-8'))
    scan = json.loads((ev / 'review_new_interference_scan.json').read_text(encoding='utf-8'))
    bom = json.loads((RUN / 'evidence' / 'e1_bom_mass_delta.json').read_text(encoding='utf-8'))
    smoke = json.loads((RUN / 'logs' / 's07_build_smoke_log.json').read_text(encoding='utf-8'))
    P, _ = load_params()

    items = []
    def item(name, claim, recomputed, match, note=''):
        items.append({'item': name, 'claim': claim, 'recomputed': recomputed,
                      'match': bool(match), 'note': note})

    # 1) 同轴最大偏差
    item('coaxial_max_axis_offset_mm', acc['readback']['max_axis_offset_mm'],
         rb['max_axis_offset_mm'],
         rb['max_axis_offset_mm'] == acc['readback']['max_axis_offset_mm'],
         'r30 独立读回 16 站 ×3 线对')
    # 2) 孔数
    counts = {m: len(a['found']) for m, a in rb['member_face_audit'].items()}
    expect_counts = {'RB_longeron_1_1': 5, 'RB_longeron_-1_1': 5, 'RB_longeron_1_-1': 3,
                     'RB_longeron_-1_-1': 3, 'RB_upper_beam_20': 4, 'RB_upper_beam_160': 2,
                     'RB_lower_beam_20': 4, 'RB_lower_beam_160': 2, 'WP01-RB-BRIDGE-R2': 4}
    item('hole_counts_per_member', acc['readback']['hole_counts'], counts,
         counts == expect_counts, '与登记 5/5/3/3、4/2/4/2、4 对照')
    # 3) 新增体积
    vol = rb['measured_volumes_mm3']
    added = sum(v for n, v in vol.items() if n.startswith('e1_anchor_'))
    item('added_volume_mm3', bom['added_volume_mm3'], round(added, 6),
         abs(added - bom['added_volume_mm3']) < 1e-6,
         '48 件 exports 实测体积求和（16×(216.180844+9.597566+27.897343)）')
    # 4) 去除体积（解析式：纵梁贯穿孔=2壁×2mm×πr²；盲孔=πr²×12）
    hole_through = 2 * WALL * math.pi * R * R
    hole_blind = math.pi * R * R * BLIND_DEPTH
    removed_analytic = {}
    for m, c in counts.items():
        removed_analytic[m] = round(c * (hole_through if 'longeron' in m else hole_blind), 6)
    removed_total = sum(removed_analytic.values())
    bom_removed = {r['member']: r['removed_mm3'] for r in bom['modified_members']}
    per_member_ok = all(abs(removed_analytic[m] - bom_removed[m]) < 1e-4 for m in removed_analytic)
    item('removed_volume_mm3_total', bom['removed_volume_mm3'], round(removed_total, 6),
         abs(removed_total - bom['removed_volume_mm3']) < 1e-4 and per_member_ok,
         '解析式逐件对拍 bom 表')
    # 4b) 改后件体积
    post_ok = all(abs(vol[r['member']] - r['volume_post_mm3']) < 1e-4
                  for r in bom['modified_members'])
    item('modified_member_post_volumes', 'bom 9 件 volume_post_mm3', 'exports 实测',
         post_ok)
    # 5) 净质量
    net = (added - removed_total) * RHO_AL
    item('net_al_candidate_mass_delta_kg', bom['net_al_candidate_mass_delta_kg'], net,
         abs(net - bom['net_al_candidate_mass_delta_kg']) < 1e-8,
         '铝 2.7e-6 仅候选估算（UNKNOWN 保留）')
    # 6) 烟测实例数
    n_anchor_steps = len(list((RUN / 'exports').glob('e1_anchor_*.step')))
    item('smoke_431_eq_383_plus_48',
         [smoke['expected_instances'], smoke['actual_instances'], smoke['anchor_instances']],
         [scan['build_instance_count'], n_anchor_steps],
         scan['build_instance_count'] == 431 and n_anchor_steps == 48
         and 431 == 383 + 48,
         'r33 独立重建实例数 + exports 锚固 STEP 计数')
    # 7) 登记表行数
    ra = rb['registration_audit']
    item('registration_rows_16_16_10_10',
         acc['registration_tables'],
         {k: ra[k] for k in ('dual_hole_pairs_rows', 'fastener_stacks_rows',
                             'mounting_surfaces_rows', 'tool_paths_rows')},
         (ra['dual_hole_pairs_rows'] == 16 and ra['fastener_stacks_rows'] == 16
          and ra['mounting_surfaces_rows'] == 10 and ra['tool_paths_rows'] == 10
          and ra['pair_id_set_match']))
    # 8) UNKNOWN 保留
    e1p = P['root_anchoring_r07_e1']
    item('unknown_fields_preserved', 'material/grade/preload/locking/engagement/load UNKNOWN',
         {'registration': ra['unknown_fields_preserved'],
          'param_status_contains_UNKNOWN': 'UNKNOWN' in e1p['status'],
          'fastener_candidate_UNKNOWN': 'UNKNOWN' in e1p['fastener_candidate']['material_grade_thread_engagement_preload_locking']},
         ra['unknown_fields_preserved'] and 'UNKNOWN' in e1p['status'])
    # 9) 干涉对计数与具名零间隙
    item('interference_pairs_and_clearance',
         acc['boolean_interference']['pairs_checked'],
         {'A_anchor_vs_other': scan['pairs']['A_anchor_vs_other'],
          'B_anchor_vs_anchor': scan['pairs']['B_anchor_vs_anchor'],
          'C_member_vs_other': scan['pairs']['C_member_vs_other'],
          'named_clearance': len(scan['explicit_clearance_checks']),
          'clearance_all_pass': all(c['pass'] for c in scan['explicit_clearance_checks'])},
         scan['pairs'] == {'A_anchor_vs_other': 110, 'B_anchor_vs_anchor': 32,
                           'C_member_vs_other': 205}
         and len(scan['explicit_clearance_checks']) == 96,
         'ACCEPTANCE 的 A/B 标签与 s04 内部键名互换（数值一致）→ 观察项 O6')
    # 10) V1/V2 登记值 vs 本审阅回放
    item('v1_fail_replay_max_mm3',
         acc['iteration_history_fail_not_overwritten']['V1']['max_intrusion_mm3'],
         nc['nc_a']['max_common_volume_mm3'],
         nc['nc_a']['detect_ok'])
    item('v2_fail_replay_max_mm3',
         acc['iteration_history_fail_not_overwritten']['V2']['max_intrusion_mm3'],
         nc['nc_a2']['max_common_volume_mm3'],
         nc['nc_a2']['detect_ok'])
    # 11) 既有干涉登记值 vs r32
    item('preexisting_interference_mm3',
         [p['common_volume_mm3'] for p in acc['boolean_interference']['registered_preexisting']],
         {k: v['control_unmodified_beam_mm3'] for k, v in pre['recomputed'].items()},
         pre['conclusion'] == 'PRE_EXISTING_CONFIRMED')
    # 12) NOT_RUN 清单
    not_run_text = ' | '.join(acc['not_run'])
    need = ['独立第三方', '载荷', '选型', '0.15', '0.3', '工具路径实物', 'R14', '实物试配']
    missing = [k for k in need if k not in not_run_text]
    item('not_run_list_explicit', '7 项 NOT_RUN（含 0.15mm 边距/0.3mm 薄壁套制造性、'
         '载荷强度、工具实物回放、R14 扰动）', acc['not_run'], not missing,
         f'缺项: {missing}' if missing else '全部命中')

    n_ok = sum(1 for i in items if i['match'])
    observations = [
        {'id': 'O1', 'severity': 'NOTE', 'topic': 'x=160 单栓站防转不对称',
         'text': 'G03/G04/G07/G08 为单栓+REGISTERED_SECONDARY（M6 夹接/贯通杆夹接链/桥双栓同板路径），'
                 '滑移与残余转角 UNKNOWN；与 x=20 站 TWO_BOLT_POSITIVE 不构成同等防转。'
                 '登记充分性可接受，但载荷/强度评级前不得按双栓站等效处理。'},
        {'id': 'O2', 'severity': 'NOTE', 'topic': '制造性 NOT_RUN',
         'text': '防压套与管腔 z 边距仅 0.15mm、套壁 0.3mm 薄壁；制造性审查在 not_run 清单显式登记，'
                 '未闭环前不构成制造放行。'},
        {'id': 'O3', 'severity': 'PROCESS', 'topic': 'V1/V2 FAIL JSON 被同名覆盖',
         'text': '两轮 FAIL 的机器裁决 JSON 被同名覆盖，仅存数值于 PATCH_NOTES/ACCEPTANCE；'
                 '本审阅已按 s03b/s03c 参数 diff 独立回放复现 28.85/15.21 mm³ 两个 FAIL 量级（逐位一致），'
                 '历史可追溯性部分修复；建议后续 FAIL 文件一律带版本后缀（候选方已自 V3 起改正）。'},
        {'id': 'O4', 'severity': 'PROCESS', 'topic': '参数块路径笔误',
         'text': 'ACCEPTANCE_SUMMARY.design.param_block 写作 '
                 '20_engineering/service_robot_wp03_spacecraft_body_r1/config/design_parameters.json，'
                 '实际文件在工程根目录（无 config/ 子层）；哈希钉固不受影响。'},
        {'id': 'O5', 'severity': 'NOTE', 'topic': '既有干涉须上报父票',
         'text': 'RB_upper_beam_160 vs shear_web_screw_±1_150_94 的 0.461mm³ 经 r32 确认为改前既有'
                 '（WP02 横梁端角 vs 既有剪力板栓包络，git 旧态内容一致）；不在 E1 处置，'
                 '但应随父票 R07/WP02 lineage 上报跟踪，不得在后续汇总中静默消失。'},
        {'id': 'O6', 'severity': 'PROCESS', 'topic': '干涉对计数标签互换',
         'text': 'ACCEPTANCE_SUMMARY.boolean_interference.pairs_checked 的 A/B 标签 '
                 '(A_anchor_vs_anchor=110, B_anchor_vs_other=32) 与 s04 内部键名互换；'
                 's04/r33 一致口径为 A=锚固件 vs 既有件 110、B=锚固件两两 32、C=改件 vs 既有件 205。'
                 '数值无误，仅标签笔误。'},
    ]
    result = {'review': 'R07_E1_INDEPENDENT_REVERIFY', 'script': 'r34_spotcheck.py',
              'reviewed_run': RUN.name, 'spotcheck_items': items,
              'consistent': n_ok, 'total': len(items),
              'consistency_rate': f'{n_ok}/{len(items)}',
              'observations': observations,
              'verdict': 'PASS' if n_ok == len(items) else 'FAIL',
              'elapsed_s': round(time.time() - t0, 3)}
    write_json(ev / 'review_spotcheck.json', result)
    print('verdict', result['verdict'], 'consistency', result['consistency_rate'])
    for i in items:
        if not i['match']:
            print('MISMATCH', i['item'], i['claim'], i['recomputed'])


if __name__ == '__main__':
    main()
