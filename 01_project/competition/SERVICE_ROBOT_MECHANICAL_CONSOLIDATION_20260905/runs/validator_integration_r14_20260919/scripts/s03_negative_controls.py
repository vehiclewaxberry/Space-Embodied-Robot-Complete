"""s03 六类负控：对真实 POSE_SCREEN.json 逐类变异，证明严格汇总器 fail-closed 检出。

正控 = aggregate(原始数据, 真实快照绑定) 必须 PASS（与 s02 一致）。
负控类别：
  NC1 重复 pair 记录        -> DUPLICATE_PAIR_ID
  NC2 缺失 pair 记录        -> MISSING_OR_UNEXPECTED_PAIR_ID
  NC3 错误 ID（不存在 link）-> MISSING_OR_UNEXPECTED_PAIR_ID
  NC4 过期来源              -> a) INPUT_STALE（输入哈希不符） b) SCRIPT_HASH_STALE（脚本哈希不符）
  NC5 爆炸视图充当物理输入  -> require_physical_view 抛 DISPLAY_OR_UNSUPPORTED_CONFIGURATION_REJECTED
  NC6 不完整事件            -> a) NO_COMPLETION_EVENT b) WORKER_COMPLETION_FLAG_FALSE c) TIMEOUT_OR_TIMEOUT_STATE_UNKNOWN
  NC7（附加 fail-closed 面）NaN 结果 -> NAN_OR_FLOAT_RESULT
每个负控必须 overall != PASS（NC5 为异常抛出），且检出理由含预期码；否则本脚本 FAIL。
"""
from pathlib import Path
import copy
import hashlib
import json
import sys

RUN = Path(__file__).resolve().parents[1]
ENG = Path(r'F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1')
sys.path.insert(0, str(ENG))
import strict_surface_integration as ssi  # noqa: E402

POSE_JSON = ENG / 'results/POSE_SCREEN.json'
BINDING = json.loads((RUN / 'inputs/snapshot_binding.json').read_text(encoding='utf-8'))
BASE = json.loads(POSE_JSON.read_text(encoding='utf-8'))
POSE0 = BASE['self_screen_contract']['configuration']['poses'][0]


def cand(d, pose_id=POSE0):
    """按合同姿态 ID 定位候选姿态记录（参考姿态不入场）。"""
    return next(p for p in d['poses'] if p['id'] == pose_id)


def run_case(name, mutate, expect_codes, expect_overall='FAIL'):
    data = copy.deepcopy(BASE)
    mutate(data)
    res = ssi.aggregate(data, snapshot_binding=BINDING)
    reasons = res['protocol']['reasons']
    found = {c: any(c in r for r in reasons) for c in expect_codes}
    ok = res['overall'] == expect_overall and all(found.values())
    return {'case': name, 'overall': res['overall'], 'mechanical': res['mechanical_collision']['verdict'],
            'expected_codes': expect_codes, 'code_found': found,
            'reasons': reasons, 'detected': ok}


def main():
    results = {'schema': 'R14_VALIDATOR_NEGATIVE_CONTROLS_V1',
               'positive_control': None, 'negative_controls': [], 'verdict': None}

    # 正控：原始真实数据必须 PASS
    pos = ssi.aggregate(copy.deepcopy(BASE), snapshot_binding=BINDING)
    results['positive_control'] = {'overall': pos['overall'], 'protocol': pos['protocol']['verdict'],
                                   'mechanical': pos['mechanical_collision']['verdict'],
                                   'reasons': pos['protocol']['reasons']}
    pos_ok = pos['overall'] == 'PASS'

    cases = []

    def m_dup(d):  # NC1 重复
        rows = cand(d)['self_surface_check']['records']
        rows.append(copy.deepcopy(rows[0]))
    cases.append(run_case('NC1_duplicate_pair_record', m_dup,
                          ['DUPLICATE_PAIR_ID']))

    def m_del(d):  # NC2 缺失
        cand(d)['self_surface_check']['records'].pop()
    cases.append(run_case('NC2_missing_pair_record', m_del, ['MISSING_OR_UNEXPECTED_PAIR_ID']))

    def m_badid(d):  # NC3 错误 ID
        cand(d)['self_surface_check']['records'][0]['links'] = ['base_link', 'nonexistent_link']
    cases.append(run_case('NC3_wrong_pair_id', m_badid, ['MISSING_OR_UNEXPECTED_PAIR_ID']))

    def m_stale(d):  # NC4a 过期来源：输入文件哈希
        k = sorted(d['source_hashes'])[0]
        d['source_hashes'][k] = '0' * 64
    cases.append(run_case('NC4a_stale_input_hash', m_stale, ['INPUT_STALE']))

    def m_script(d):  # NC4b 过期来源：脚本哈希
        d['script_sha256'] = '0' * 64
    cases.append(run_case('NC4b_stale_script_hash', m_script, ['SCRIPT_HASH_STALE']))

    # NC5 爆炸视图充当物理检查输入（视图守卫，异常面）
    nc5_thrown = None
    try:
        ssi.require_physical_view({'view': 'exploded', 'state': 'parking'})
    except ValueError as exc:
        nc5_thrown = str(exc)
    nc5_ok = nc5_thrown == 'DISPLAY_OR_UNSUPPORTED_CONFIGURATION_REJECTED'
    cases.append({'case': 'NC5_exploded_view_as_physical_input', 'overall': 'EXCEPTION_RAISED',
                  'mechanical': None, 'expected_codes': ['DISPLAY_OR_UNSUPPORTED_CONFIGURATION_REJECTED'],
                  'code_found': {'DISPLAY_OR_UNSUPPORTED_CONFIGURATION_REJECTED': nc5_ok},
                  'reasons': [f'ValueError:{nc5_thrown}'], 'detected': nc5_ok})
    nc5b_thrown = None
    try:
        ssi.require_physical_view({'view': 'complete', 'state': 'exploded'})
    except ValueError as exc:
        nc5b_thrown = str(exc)
    cases.append({'case': 'NC5b_unsupported_state', 'overall': 'EXCEPTION_RAISED', 'mechanical': None,
                  'expected_codes': ['DISPLAY_OR_UNSUPPORTED_CONFIGURATION_REJECTED'],
                  'code_found': {'DISPLAY_OR_UNSUPPORTED_CONFIGURATION_REJECTED': nc5b_thrown == 'DISPLAY_OR_UNSUPPORTED_CONFIGURATION_REJECTED'},
                  'reasons': [f'ValueError:{nc5b_thrown}'],
                  'detected': nc5b_thrown == 'DISPLAY_OR_UNSUPPORTED_CONFIGURATION_REJECTED'})

    def m_nocomp(d):  # NC6a 缺完成事件
        del cand(d)['self_surface_check']['completion_event']
    cases.append(run_case('NC6a_no_completion_event', m_nocomp, ['NO_COMPLETION_EVENT']))

    def m_flag(d):  # NC6b worker 未完成
        cand(d)['self_surface_check']['worker_completed'] = False
    cases.append(run_case('NC6b_worker_completion_flag_false', m_flag, ['WORKER_COMPLETION_FLAG_FALSE']))

    def m_timeout(d):  # NC6c 超时
        d['worker_timed_out'] = True
    cases.append(run_case('NC6c_worker_timed_out', m_timeout, ['TIMEOUT_OR_TIMEOUT_STATE_UNKNOWN']))

    def m_nan(d):  # NC7 NaN 结果
        cand(d)['self_surface_check']['records'][0]['surface_intersection'] = float('nan')
    cases.append(run_case('NC7_nan_result', m_nan, ['NAN_OR_FLOAT_RESULT']))

    results['negative_controls'] = cases
    all_detected = all(c['detected'] for c in cases)
    results['verdict'] = 'NEGATIVE_CONTROLS_ALL_DETECTED' if (pos_ok and all_detected) else 'NEGATIVE_CONTROL_GAP'
    results['positive_control_ok'] = pos_ok

    out = RUN / 'evidence/r14_validator_negative_controls.json'
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    (RUN / 'evidence/r14_validator_negative_controls.json.sha256').write_bytes(
        (digest + '  evidence/r14_validator_negative_controls.json\n').encode('utf-8'))

    log = {'script': 's03_negative_controls.py', 'positive_control_ok': pos_ok,
           'cases': [{'case': c['case'], 'detected': c['detected'], 'overall': c['overall']} for c in cases],
           'verdict': results['verdict'], 'evidence_sha256': digest}
    (RUN / 'logs/s03_negative_controls_log.json').write_text(
        json.dumps(log, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'verdict': results['verdict'], 'positive_ok': pos_ok,
                      'detected': sum(c['detected'] for c in cases), 'total': len(cases)}, ensure_ascii=False))
    if results['verdict'] != 'NEGATIVE_CONTROLS_ALL_DETECTED':
        sys.exit(1)


if __name__ == '__main__':
    main()
