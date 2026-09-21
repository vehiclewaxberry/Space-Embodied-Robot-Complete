# -*- coding: utf-8 -*-
"""R07-E4 独立复验 r35：REVIEW_VERDICT.json 生成 + 全部边车刷新 + 整组边车复核。
汇总 r30-r34 证据（不再复算几何）；边车口径：sha256 + '  ' + 相对 review run 根正斜杠路径。"""
import json, time
from pathlib import Path
from e4_common import REV, RUN, E4_COMMIT, SOURCE_SHA256_EXPECT, PARAMS_SHA256_EXPECT, \
    write_json, sidecar, sha256_file

EV = REV / 'evidence'


def load(name):
    return json.loads((EV / name).read_text(encoding='utf-8'))


def main():
    r30 = load('review_e4_readback.json')
    r31 = load('review_e4_negative_controls.json')
    r32 = load('review_e4_preexisting.json')
    r32b = load('review_e4_git_baseline.json')
    r33 = load('review_e4_scan.json')
    r34 = load('review_e4_spotcheck.json')
    subs = {'readback': r30['verdict'], 'negative_controls': r31['verdict'],
            'preexisting_check': r32['verdict'], 'git_baseline_lane2': r32b['verdict'],
            'new_interference_scan': r33['verdict'], 'spotcheck': r34['verdict']}
    all_pass = all(v == 'PASS' for v in subs.values())

    S = json.loads((RUN / 'ACCEPTANCE_SUMMARY.json').read_text(encoding='utf-8'))
    verdict = {
        'review': 'R07_E4_INDEPENDENT_REVERIFY',
        'review_run': REV.name,
        'reviewed_run': RUN.name,
        'reviewed_commit': E4_COMMIT,
        'reviewer_role': 'WP03 R07-E4 独立审阅者（只读；不改候选；不执行 git 提交）',
        'scope': ('仅 R07 父票 E4 一边（后端框→后发射保留隔框，4 阶梯夹套新增 + 4 件后场 M4 螺钉'
                  '同名替换延长 22→30）数字几何候选的独立复验；E1/E2/E3 与 A/B 支承、供应方侧'
                  '（保留体积/窗口外段/肋）、front_service_cover 不在本次范围'),
        'basis_pins': {
            'params_sha256': PARAMS_SHA256_EXPECT,
            'params_pin_ok': r30['basis_pins']['design_parameters.json']['match'],
            'source_sha256': SOURCE_SHA256_EXPECT,
            'source_pin_ok': r30['basis_pins']['spacecraft_model.py']['match'],
            'export_hash_pin': {
                'parts': len(r30['export_readback']),
                'all_sha256_ok': all(r.get('sha256_match') for r in r30['export_readback'].values()),
                'all_volume_bbox_ok': all(r.get('volume_match', True) and r.get('bbox_match', True)
                                          for r in r30['export_readback'].values())},
            'snapshot_vs_git_old_state': r32b['git_old_vs_snapshot']},
        'sub_verdicts': subs,
        'key_results': {
            'readback': {
                'exports_checked': r30['summary']['exports_checked'],
                'coaxial_pairs_4x6': r30['summary']['coaxial_pairs'],
                'coaxial_all_zero': r30['summary']['coaxial_all_zero'],
                'sleeve_geometry_ok': r30['summary']['sleeves_ok'],
                'screw_tip_engagement_ok': r30['summary']['screws_ok'],
                'fit_truth_bulkhead_common_frame': r30['fit_truth_recheck']['pass']},
            'negative_controls': {
                'controls': r31['summary']['controls'],
                'variant_fired': r31['summary']['variant_fired'],
                'real_zero': r31['summary']['real_zero'],
                'values': {k: {'variant_mm3': c['variant_common_mm3'],
                               'real_mm3': c['real_common_mm3']}
                           for k, c in r31['controls'].items()},
                'nc_a_direction_erratum': ('原拟 dx=-1 变异在 x 向与隔框无交属无效变异；'
                                           '内侵方向勘正为 dx=+1（法兰越外面向 +x 压入隔框），如实登记')},
            'preexisting_interference': {
                'conclusion': r32['conclusion'],
                'A_attribution_all_closed': r32['summary']['A_attribution_all_closed'],
                'B_lane1_bit_identical_8of8': r32['summary']['B_bit_identical_to_e3_review_all'],
                'B_lane2_git_baseline_bit_identical_8of8': r32b['summary']['B2_bit_identical_all'],
                'core_prediction': r32b['summary']['core_prediction'],
                'modified_screw_pairs': r32['summary']['B_modified_screw_pairs']},
            'new_interference_scan': {
                'A_effective_after_E_routing': r33['summary']['A_effective_after_E_routing'],
                'B_e4_vs_e4': r33['summary']['pairs_bbox_total']['B_e4_vs_e4'],
                'pair_counts_match_candidate': r33['summary']['pair_counts_match_candidate'],
                'new_positives': r33['summary']['new_positives'],
                'routed_to_E_thread_convention': r33['summary']['routed_to_E'],
                'named_clearance_checks': r33['summary']['clearance_checks'],
                'named_clearance_fail': r33['summary']['clearance_fail'],
                'e4_vs_e1_bbox_pairs': r33['summary']['e4_vs_e1_bbox_pairs'],
                'e4_vs_e2_bbox_pairs': r33['summary']['e4_vs_e2_bbox_pairs'],
                'e4_vs_e3_bbox_pairs': r33['summary']['e4_vs_e3_bbox_pairs'],
                'operand_order_probe': r33['operand_order_probe']},
            'spotcheck_pass_ratio': r34['summary']['consistency'],
            'mass_delta_recompute': r34['checks']['S5_mass_delta']['detail']},
        'observations': [
            {'id': 'O1',
             'topic': '法兰 2mm 薄壁 + 0.05/0.25mm 每边配合隙制造性 NOT_RUN',
             'detail': ('阶梯夹套法兰厚 2mm、筒/窗口隙 0.05 每边、ID/栓杆隙 0.25 每边，'
                        '制造性审查（配合隙公差堆叠、阶梯套内外圆同轴工艺、法兰薄壁）登记于 '
                        'ACCEPTANCE_SUMMARY not_run[4]，登记充分性确认；'
                        '几何 PASS 不构成制造性证明。')},
            {'id': 'O2',
             'topic': '夹紧力/预紧 UNKNOWN——面贴合零体积连接首次引入夹紧件',
             'detail': ('隔框∩端框 Common=0.0（x=-183 面贴合）经本审阅实测复算确认；E4 以夹套法兰+'
                        '延长螺钉首次把该贴合面转为夹紧堆栈，但夹紧力/预紧/压溃/承压/载荷路径全部 '
                        'UNKNOWN/NOT_RUN（not_run[1] 含"贴合面夹紧力与预紧"字样，登记充分）；'
                        '本复验仅覆盖数字几何候选，不构成夹紧有效性证明。')},
            {'id': 'O3',
             'topic': '供应方侧参数化占位边界清晰',
             'detail': ('S10 实证：root_structure.py 现行 sha == E4 inputs 快照（E4 未触）；'
                        '当前 build 实测 rear 肋 x[-195,-189]、保留体积 x[-215,-195] 未动；'
                        'Ø8 窗口外段保持参数化、不臆造部署器孔系、ICD UNKNOWN；'
                        'front_service_cover 登记 OUT_OF_SCOPE（原票仅指后端框），未擅自扩范围。')},
            {'id': 'O4',
             'topic': 'v1 判据缺陷迭代史（被审与审阅双侧同型教训）',
             'detail': ('被审 s05 v1 两处判据缺陷：尖端判据误用 bb.min.X（尖端在 max 侧 -161）、'
                        '端塞 Ø3.3 导孔按面计数=1 过严（导孔被 x=-164 E2 分段销孔 Ø4.5 横穿劈为 2 个'
                        '同轴圆柱面为几何事实）；v2 改 bb.max.X + 按唯一轴(y,z)计数 → PASS，'
                        'FAIL 归档链完整（S8 核验：归档未改、边车有效、iteration_history 注记）。'
                        '本审阅 r30 初版亦踩同型陷阱（对 import-STEP 件 vs 原生包络强求逐位一致，'
                        '跨求积路径 1e-13 漂移属预期），已在证据注记并改求积路径容差判据。')},
            {'id': 'O5',
             'topic': '质量与计数口径：净分配质量首次非零 + NOT_RUN 条数差异',
             'detail': ('夹套 4 件真实铝候选 CAD_ESTIMATE（density 2.7e-6，E1 防压套先例，'
                        'PHYSICAL_GEOMETRY/GOLD）→ 净分配质量 +0.00424505194042198 kg 为本项目 '
                        'BOM 净增量首次非零（独立复算 1572.241459415548×2.7e-6 互证）；'
                        '改件螺钉 NOT_ALLOCATED 前后同口径、体积差 π·2²·8/件 仅供预算。'
                        'NOT_RUN 任务书表述"九项" vs 实际 8 条：语义覆盖 8 主题全到位'
                        '（"部署器对接实物验证；实物试配/装配"合并一条），计数差异如实登记，'
                        '不构成缺口。')},
            {'id': 'O6',
             'topic': 'OCC 布尔操作数次序非逐位可交换（bit-identical 声明须带次序口径）',
             'detail': ('r33 探针：common(screw,plug)=49.7130518387019 vs '
                        'common(plug,screw)=49.713051764535635，差 ~7.4e-8 为求积路径漂移非几何差异。'
                        '被审登记、E3 审阅复核与本审阅 r32 双车道均 plug-first 同口径，'
                        '8/8 逐位互锁成立；建议后续所有 bit-identical 声明注明操作数次序，'
                        '扫描类循环与登记类核查次序不同时以容差口径对拍。')}],
        'limitations_carried_from_candidate': S['not_run'],
        'whole_design_complete': False,
        'manufacturing_release': False,
        'parent_ticket_r07_closure': 'NOT_CLOSED（本复验不构成父票关闭依据）',
        'verdict': 'R07_E4_INDEPENDENT_REVERIFY_PASS_WITH_OBSERVATIONS' if all_pass
                   else 'R07_E4_INDEPENDENT_REVERIFY_FAIL',
        'verdict_semantics': ('PASS_WITH_OBSERVATIONS=全部独立机器核查通过'
                              '（读回/三负控/既有核查双车道/新增扫描/抽验 10 项）；'
                              '观察项 O1-O6 为登记/口径类备注，不构成阻断；'
                              '候选维持 DIGITAL_GEOMETRY_CANDIDATE 等级，'
                              '不升级为制造放行或全设计完成'),
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S')}
    write_json(REV / 'REVIEW_VERDICT.json', verdict)

    # 全部脚本边车刷新
    for p in sorted((REV / 'scripts').glob('*.py')):
        sidecar(p)

    # 整组边车复核（scripts/*.py + evidence/*.json + REVIEW_VERDICT.json）
    bad = []
    checked = 0
    for d, pat in ((REV / 'scripts', '*.py'), (EV, '*.json'), (REV, 'REVIEW_VERDICT.json')):
        for p in sorted(d.glob(pat)):
            checked += 1
            sp = Path(str(p) + '.sha256')
            if not sp.exists():
                bad.append(f'missing sidecar: {p.name}')
                continue
            h, rel = sp.read_text(encoding='utf-8').strip().split('  ', 1)
            if h != sha256_file(p):
                bad.append(f'sidecar stale: {p.name}')
            if rel != p.resolve().relative_to(REV).as_posix():
                bad.append(f'sidecar rel path wrong: {p.name}: {rel}')
    print('verdict', verdict['verdict'])
    print('sidecar checked', checked, 'bad', bad)
    if bad:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
