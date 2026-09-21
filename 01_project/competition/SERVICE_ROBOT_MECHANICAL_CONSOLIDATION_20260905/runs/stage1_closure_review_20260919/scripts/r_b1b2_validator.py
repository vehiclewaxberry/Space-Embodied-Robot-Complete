# -*- coding: utf-8 -*-
"""阶段一收口复验 B1/B2：严格验证器接入 + 36/35 派生链 + 正控真实入口重跑 + 负控重放。
B2a 派生链独立复算：xml.etree 解析 URDF（live 与 inputs 快照双钉固）→ 10 link、9 相邻、
   C(10,2)=45−9=36、指/指延期 1 → 必需 35；与 live POSE_SCREEN.json 合同逐键比对。
B2b 汇总器 live 重放：strict_surface_integration.py --input live POSE_SCREEN --snapshot-binding
   被审快照绑定 --output 本审阅 _work（不写被审结果目录）。
B2c pose_screen 真实入口沙箱重跑：复刻最小依赖树（含 27MB accepted STL），python pose_screen.py
   全链重跑（含 vtk worker 子进程），产物与 live POSE_SCREEN 逐姿态/逐配对语义比对；
   再以我重算的沙箱绑定跑汇总器。
B1 负控重放（≥4 类，实做 6 类）：过期来源/缺完成事件/NaN/爆炸视图/重复对/绑定错配，
   对 live POSE_SCREEN 深拷贝变异后调 live strict 模块 aggregate()，断言 overall≠PASS + 预期码。"""
import copy, importlib.util, itertools, json, shutil, subprocess, sys, time
import xml.etree.ElementTree as ET
from pathlib import Path
from sc_common import REV, RUN_B, ROOT, ENG, URDF, write_json, sha256_file, POSE_SCREEN_V2_SHA

PY = sys.executable
SAND = REV / '_work' / 'sandbox_b'
SAND_ENG_ROOT = SAND / '20_engineering'
POSE_LIVE = ENG / 'results' / 'POSE_SCREEN.json'


def load_live_aggregator():
    spec = importlib.util.spec_from_file_location(
        'strict_surface_integration_live', str(ENG / 'strict_surface_integration.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def urdf_derive(urdf_path):
    tree = ET.parse(urdf_path)
    root = tree.getroot()
    links = [l.get('name') for l in root.findall('link')]
    joints = [(j.find('parent').get('link'), j.find('child').get('link'))
              for j in root.findall('joint')]
    adjacent = {frozenset(x) for x in joints}
    all_pairs = {tuple(sorted(p)) for p in itertools.combinations(links, 2)}
    nonadj = sorted(all_pairs - {tuple(sorted(x)) for x in adjacent})
    return {'links': links, 'joints': joints, 'adjacent': sorted(map(sorted, adjacent)),
            'n_links': len(links), 'n_joints': len(joints),
            'n_all_pairs': len(all_pairs), 'nonadjacent': nonadj, 'n_nonadjacent': len(nonadj)}


def build_sandbox_b():
    if SAND.exists():
        shutil.rmtree(SAND)
    engroot = ENG.parent  # live 20_engineering
    cad = SAND_ENG_ROOT / 'cad/spacecraft_layout/arm_b601_v1'
    shutil.copytree(engroot / 'cad/spacecraft_layout/arm_b601_v1', cad)
    wp01 = SAND_ENG_ROOT / 'service_robot_wp01_20260905'
    (wp01 / 'results').mkdir(parents=True)
    for f in ('kinematics.py', 'design_parameters.json', 'LAYOUT_COMPARISON.json'):
        shutil.copy2(engroot / 'service_robot_wp01_20260905' / f, wp01 / f)
    for f in ('stowed_build_receipt.json', 'FINGER_INTERFACE_CHECK.json'):
        shutil.copy2(engroot / 'service_robot_wp01_20260905/results' / f, wp01 / 'results' / f)
    wp02 = SAND_ENG_ROOT / 'service_robot_wp02_20260905'
    wp02.mkdir(parents=True)
    shutil.copy2(engroot / 'service_robot_wp02_20260905/motion_analysis.py',
                 wp02 / 'motion_analysis.py')
    wp03 = SAND_ENG_ROOT / 'service_robot_wp03_spacecraft_body_r1'
    (wp03 / 'results').mkdir(parents=True)
    for f in ('pose_screen.py', 'wing_kinematics.py'):
        shutil.copy2(ENG / f, wp03 / f)
    return wp03


def main():
    t0 = time.time()
    result = {'review': 'STAGE1_CLOSURE_INDEPENDENT_REVERIFY/B_VALIDATOR_R14',
              'script': 'r_b1b2_validator.py', 'reviewed_run': 'validator_integration_r14_20260919',
              'failures': [], 'verdict': None}
    pose = json.loads(POSE_LIVE.read_text(encoding='utf-8'))

    # ---- B2a 36/35 派生链独立复算 ----
    d_live = urdf_derive(URDF)
    d_snap = urdf_derive(RUN_B / 'inputs' / 'arm_b601_v1.urdf')
    contract = pose['self_screen_contract']
    contract_pairs = sorted(tuple(sorted(p)) for p in contract['expected_nonadjacent_pairs'])
    deferred = [tuple(sorted(p)) for p in contract['explicit_unknown_pairs']]
    b2a = {
        'urdf_snapshot_sha': sha256_file(RUN_B / 'inputs' / 'arm_b601_v1.urdf'),
        'urdf_live_sha': sha256_file(URDF),
        'snapshot_eq_live': sha256_file(RUN_B / 'inputs' / 'arm_b601_v1.urdf') == sha256_file(URDF),
        'n_links': d_live['n_links'], 'n_joints_adjacent': d_live['n_joints'],
        'n_all_pairs_C_10_2': d_live['n_all_pairs'],
        'n_nonadjacent': d_live['n_nonadjacent'],
        'arithmetic': f"{d_live['n_all_pairs']} - {d_live['n_joints']} = {d_live['n_nonadjacent']}",
        'deferred_pairs': [list(p) for p in deferred],
        'deferred_in_expected': all(tuple(p) in set(map(tuple, contract_pairs)) for p in deferred),
        'required_evaluated': contract['required_evaluated_pair_count'],
        'contract_set_eq_review_derivation': contract_pairs == d_live['nonadjacent'],
        'link_names': d_live['links'], 'adjacent_pairs': d_live['adjacent'],
    }
    b2a['pass'] = (b2a['snapshot_eq_live'] and d_live['n_links'] == 10
                   and d_live['n_joints'] == 9 and d_live['n_all_pairs'] == 45
                   and d_live['n_nonadjacent'] == 36 and len(deferred) == 1
                   and b2a['deferred_in_expected']
                   and contract['required_evaluated_pair_count'] == 35
                   and b2a['contract_set_eq_review_derivation'])
    result['B2a_pair_derivation'] = b2a
    if not b2a['pass']:
        result['failures'].append('B2a pair derivation mismatch')

    # ---- B2b 汇总器 live 重放 ----
    out_live = REV / '_work' / 'strict_replay_live.json'
    cp = subprocess.run([PY, str(ENG / 'strict_surface_integration.py'),
                         '--input', str(POSE_LIVE),
                         '--snapshot-binding', str(RUN_B / 'inputs' / 'snapshot_binding.json'),
                         '--output', str(out_live)],
                        capture_output=True, timeout=120)
    replay = json.loads(out_live.read_text(encoding='utf-8')) if out_live.exists() else {}
    their_pos = json.loads((RUN_B / 'evidence' / 'r17b_strict_integration_positive.json').read_text(encoding='utf-8'))
    b2b = {'exit_code': cp.returncode,
           'stdout': cp.stdout.decode('utf-8', 'replace')[:300],
           'overall': replay.get('overall'),
           'protocol': replay.get('protocol', {}).get('verdict'),
           'mechanical': replay.get('mechanical_collision', {}).get('verdict'),
           'expected_pair_count': replay.get('protocol', {}).get('expected_pair_count'),
           'deferred_pair_count': replay.get('protocol', {}).get('deferred_pair_count'),
           'poses_checked': replay.get('protocol', {}).get('poses_checked'),
           'reasons': replay.get('protocol', {}).get('reasons'),
           'matches_candidate_evidence': (
               replay.get('overall') == their_pos.get('overall')
               and replay.get('protocol', {}).get('verdict') == their_pos.get('protocol', {}).get('verdict')
               and replay.get('mechanical_collision', {}).get('verdict') == their_pos.get('mechanical_collision', {}).get('verdict')
               and replay.get('protocol', {}).get('expected_pair_count') == their_pos.get('protocol', {}).get('expected_pair_count')),
           'pose_screen_live_sha': sha256_file(POSE_LIVE),
           'pose_screen_sha_matches_v2_registered': sha256_file(POSE_LIVE) == POSE_SCREEN_V2_SHA}
    b2b['pass'] = (cp.returncode == 0 and replay.get('overall') == 'PASS'
                   and replay.get('protocol', {}).get('verdict') == 'PASS'
                   and replay.get('mechanical_collision', {}).get('verdict') == 'DISJOINT_WITHIN_DECLARED_SCOPE'
                   and b2b['expected_pair_count'] == 36 and b2b['deferred_pair_count'] == 1
                   and b2b['poses_checked'] == 3 and b2b['matches_candidate_evidence']
                   and b2b['pose_screen_sha_matches_v2_registered'])
    result['B2b_aggregator_live_replay'] = b2b
    if not b2b['pass']:
        result['failures'].append(f"B2b: {b2b['exit_code']} {b2b['stdout']}")

    # ---- B2c pose_screen 真实入口沙箱重跑 ----
    wp03 = build_sandbox_b()
    cp2 = subprocess.run([PY, 'pose_screen.py'], cwd=str(wp03), capture_output=True, timeout=280)
    sand_pose_path = wp03 / 'results' / 'POSE_SCREEN.json'
    b2c = {'exit_code': cp2.returncode, 'stderr_tail': cp2.stderr.decode('utf-8', 'replace')[-300:]}
    if cp2.returncode == 0 and sand_pose_path.exists():
        sp = json.loads(sand_pose_path.read_text(encoding='utf-8'))
        sand_contract = sp['self_screen_contract']
        # 语义比对（run_id/snapshot_digest 含绝对路径，沙箱不同属预期；逐键比配对面与结果面）
        pair_cmp = []
        live_poses = {p['id']: p for p in pose['poses']}
        all_eq = True
        for p in sp['poses']:
            lp = live_poses[p['id']]
            ssc, lsc = p['self_surface_check'], lp['self_surface_check']
            row_eq = None
            if 'records' in ssc and 'records' in lsc:
                srows = sorted(((tuple(sorted(r['links'])), r['surface_intersection']) for r in ssc['records']))
                lrows = sorted(((tuple(sorted(r['links'])), r['surface_intersection']) for r in lsc['records']))
                row_eq = (srows == lrows)
                all_eq = all_eq and row_eq
            pair_cmp.append({'pose_id': p['id'], 'status': ssc.get('status'),
                             'live_status': lsc.get('status'),
                             'status_eq': ssc.get('status') == lsc.get('status'),
                             'records_pair_level_eq': row_eq,
                             'evaluated': ssc.get('evaluated_pairs'),
                             'required': ssc.get('required_evaluated_pairs')})
        # 沙箱绑定重算（source_hashes 键已是沙箱绝对路径，逐文件重算 sha）
        binding = {}
        for k in sp['source_hashes']:
            binding[k] = sha256_file(k)
        bpath = SAND / 'review_snapshot_binding.json'
        bpath.write_text(json.dumps(binding, indent=1), encoding='utf-8')
        out_sand = REV / '_work' / 'strict_replay_sandbox.json'
        cp3 = subprocess.run([PY, str(ENG / 'strict_surface_integration.py'),
                              '--input', str(sand_pose_path),
                              '--snapshot-binding', str(bpath),
                              '--output', str(out_sand)],
                             capture_output=True, timeout=120)
        sand_agg = json.loads(out_sand.read_text(encoding='utf-8')) if out_sand.exists() else {}
        b2c.update({
            'sandbox_elapsed_s': sp.get('elapsed_seconds'),
            'worker_returncode': sp.get('worker_returncode'),
            'contract_expected_count': len(sand_contract['expected_nonadjacent_pairs']),
            'contract_eq_live': sorted(map(tuple, map(sorted, sand_contract['expected_nonadjacent_pairs'])))
                                == sorted(map(tuple, map(sorted, contract['expected_nonadjacent_pairs']))),
            'required_evaluated': sand_contract['required_evaluated_pair_count'],
            'per_pose': pair_cmp,
            'all_pose_records_eq_live': all_eq,
            'aggregator_sandbox': {'exit': cp3.returncode,
                                   'overall': sand_agg.get('overall'),
                                   'mechanical': sand_agg.get('mechanical_collision', {}).get('verdict')},
        })
        b2c['pass'] = (b2c['contract_eq_live'] and b2c['required_evaluated'] == 35
                       and all_eq and all(p['status_eq'] for p in pair_cmp)
                       and all(p['status'] == 'NONADJACENT_BODY_PAIRS_SURFACE_DISJOINT_FINGER_UNKNOWN'
                               for p in pair_cmp if p['pose_id'].startswith('EXISTING_CANDIDATE'))
                       and all(p['status'].startswith('SOURCE_REFERENCE_')
                               for p in pair_cmp if not p['pose_id'].startswith('EXISTING_CANDIDATE'))
                       and sand_agg.get('overall') == 'PASS'
                       and sand_agg.get('mechanical_collision', {}).get('verdict') == 'DISJOINT_WITHIN_DECLARED_SCOPE')
    else:
        b2c['pass'] = False
    result['B2c_pose_screen_real_entry_sandbox_rerun'] = b2c
    if not b2c['pass']:
        result['failures'].append(f"B2c: {json.dumps(b2c, ensure_ascii=False)[:400]}")

    # ---- B1 负控重放（live 模块 aggregate 内存变异）----
    ssi = load_live_aggregator()
    BINDING = json.loads((RUN_B / 'inputs' / 'snapshot_binding.json').read_text(encoding='utf-8'))
    BASE = pose
    POSE0 = BASE['self_screen_contract']['configuration']['poses'][0]

    def cand(d):
        return next(p for p in d['poses'] if p['id'] == POSE0)

    def run_case(name, mutate, expect_codes):
        d = copy.deepcopy(BASE)
        mutate(d)
        res = ssi.aggregate(d, snapshot_binding=BINDING)
        reasons = res['protocol']['reasons']
        found = {c: any(c in r for r in reasons) for c in expect_codes}
        ok = res['overall'] != 'PASS' and all(found.values())
        return {'case': name, 'overall': res['overall'], 'expected_codes': expect_codes,
                'code_found': found, 'reasons_sample': reasons[:4], 'detected': ok}

    cases = []
    cases.append(run_case('NC4a_stale_input_hash',
                          lambda d: d['source_hashes'].__setitem__(sorted(d['source_hashes'])[0], '0' * 64),
                          ['INPUT_STALE']))
    cases.append(run_case('NC4b_stale_script_hash',
                          lambda d: d.__setitem__('script_sha256', '0' * 64),
                          ['SCRIPT_HASH_STALE']))

    def m_nocomp(d):
        del cand(d)['self_surface_check']['completion_event']
    cases.append(run_case('NC6a_no_completion_event', m_nocomp, ['NO_COMPLETION_EVENT']))

    def m_nan(d):
        cand(d)['self_surface_check']['records'][0]['surface_intersection'] = float('nan')
    cases.append(run_case('NC7_nan_result', m_nan, ['NAN_OR_FLOAT_RESULT']))

    def m_dup(d):
        rows = cand(d)['self_surface_check']['records']
        rows.append(copy.deepcopy(rows[0]))
    cases.append(run_case('NC1_duplicate_pair_record', m_dup, ['DUPLICATE_PAIR_ID']))

    def m_binding(d):  # 绑定错配（附加面）：绑定哈希置零 → SNAPSHOT_BINDING_MISMATCH
        d  # 数据不变，变异绑定（下方单独处理）
    d_bind = copy.deepcopy(BASE)
    bad_binding = {k: '0' * 64 for k, v in BINDING.items()}
    res = ssi.aggregate(d_bind, snapshot_binding=bad_binding)
    found = any('SNAPSHOT_BINDING_MISMATCH' in r for r in res['protocol']['reasons'])
    cases.append({'case': 'NC4c_snapshot_binding_mismatch', 'overall': res['overall'],
                  'expected_codes': ['SNAPSHOT_BINDING_MISMATCH'],
                  'code_found': {'SNAPSHOT_BINDING_MISMATCH': found},
                  'reasons_sample': res['protocol']['reasons'][:3],
                  'detected': res['overall'] != 'PASS' and found})

    nc5_thrown = None
    try:
        ssi.require_physical_view({'view': 'exploded', 'state': 'parking'})
    except ValueError as exc:
        nc5_thrown = str(exc)
    cases.append({'case': 'NC5_exploded_view_as_physical_input', 'overall': 'EXCEPTION_RAISED',
                  'expected_codes': ['DISPLAY_OR_UNSUPPORTED_CONFIGURATION_REJECTED'],
                  'code_found': {'DISPLAY_OR_UNSUPPORTED_CONFIGURATION_REJECTED': nc5_thrown == 'DISPLAY_OR_UNSUPPORTED_CONFIGURATION_REJECTED'},
                  'reasons_sample': [f'ValueError:{nc5_thrown}'],
                  'detected': nc5_thrown == 'DISPLAY_OR_UNSUPPORTED_CONFIGURATION_REJECTED'})

    pos = ssi.aggregate(copy.deepcopy(BASE), snapshot_binding=BINDING)
    b1 = {'positive_control_overall': pos['overall'], 'cases': cases,
          'all_detected': all(c['detected'] for c in cases),
          'guard_wiring_note': ('require_physical_view 为独立守卫函数：aggregate()/main() 主路径不调用它'
                                '（全仓 grep 仅被被审 NC 脚本与本审阅调用）；NC5 证守卫单元行为，'
                                '不构成汇总链集成面——登记为观察项')}
    b1['pass'] = pos['overall'] == 'PASS' and b1['all_detected']
    result['B1_negative_controls_replay'] = b1
    if not b1['pass']:
        result['failures'].append('B1: negative control gap')

    result['summary'] = {'B2a': b2a['pass'], 'B2b': b2b['pass'], 'B2c': b2c['pass'],
                         'B1': b1['pass'],
                         'nc_detected': f"{sum(c['detected'] for c in cases)}/{len(cases)}"}
    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['elapsed_s'] = round(time.time() - t0, 3)
    write_json(REV / 'evidence' / 'review_b1b2_validator.json', result)
    print('verdict', result['verdict'], json.dumps(result['summary'], ensure_ascii=False))
    print('failures', result['failures'])


if __name__ == '__main__':
    main()
