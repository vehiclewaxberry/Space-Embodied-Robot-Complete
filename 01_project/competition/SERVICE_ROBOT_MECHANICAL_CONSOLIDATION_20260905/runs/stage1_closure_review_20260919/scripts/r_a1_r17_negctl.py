# -*- coding: utf-8 -*-
"""阶段一收口复验 A1：R17 强制顺序链负控独立重放（NC1/NC3/NC6/NC8 + 缺交接拒绝 + 字节恢复）。
方法：沙箱复刻最小链（20_engineering 相对布局），HANDOFF input_sha256 键按沙箱绝对路径重定基
（文件字节不变=哈希值不变，仅键前缀换；语义等价于真实链），全程 --bom-only（无需 CAD build）。
每案例：新鲜沙箱 → 变异 → 子进程跑 export_parts_and_bom.py → 断言 exit 2 + 预期码 ∈ violations
+ BOM/INTERFACES 字节恢复（存在则哈希不变；不存在则仍不存在）。
对照案例（无变异）须 exit 0 PASS 且 BOM 字节 == 现行 ENG BOM.csv（a6ce5bff…）。"""
import json, shutil, subprocess, sys, time
from pathlib import Path
from sc_common import REV, ENG, ROOT, write_json, sha256_file, R17_AFTER

PY = sys.executable
SAND = REV / '_work' / 'sandbox_a'
ENG_S = SAND / 'service_robot_wp03_spacecraft_body_r1'
ENG_PARENT = ENG.parent  # live 20_engineering

COPY_FILES = ['export_parts_and_bom.py', 'dynamics_handoff.py', 'spacecraft_model.py',
              'design_parameters.json', 'kinematics.py', 'wing_kinematics.py',
              'root_structure.py', 'BOM.csv', 'INTERFACES.csv']
RECEIPTS = ['parking_instances.json', 'released_instances.json', 'service_instances.json',
            'service_structure_instances.json', 'parking_ground_instances.json',
            'DYNAMICS_HANDOFF.json']


def build_sandbox():
    if SAND.exists():
        shutil.rmtree(SAND)
    (ENG_S / 'results').mkdir(parents=True)
    for f in COPY_FILES:
        shutil.copy2(ENG / f, ENG_S / f)
    for f in RECEIPTS:
        shutil.copy2(ENG / 'results' / f, ENG_S / 'results' / f)
    urdf_s = SAND / 'cad/spacecraft_layout/arm_b601_v1'
    urdf_s.mkdir(parents=True)
    shutil.copy2(ENG_PARENT / 'cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf',
                 urdf_s / 'arm_b601_v1.urdf')
    wp01_s = SAND / 'service_robot_wp01_20260905'
    wp01_s.mkdir(parents=True)
    shutil.copy2(ENG_PARENT / 'service_robot_wp01_20260905/kinematics.py',
                 wp01_s / 'kinematics.py')
    # HANDOFF input_sha256 键重定基：live 20_engineering 前缀 → 沙箱前缀（值不变）
    hp = ENG_S / 'results' / 'DYNAMICS_HANDOFF.json'
    h = json.loads(hp.read_text(encoding='utf-8'))
    rebased = {}
    for k, v in h.get('input_sha256', {}).items():
        rel = Path(k).resolve().relative_to(ENG_PARENT)
        rebased[str((SAND / rel).resolve())] = v
    h['input_sha256'] = rebased
    hp.write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding='utf-8')
    return h


def run_chain():
    cp = subprocess.run([PY, 'export_parts_and_bom.py', '--bom-only'], cwd=str(ENG_S),
                        capture_output=True, timeout=120)
    out = None
    try:
        out = json.loads(cp.stdout.decode('utf-8', 'replace'))
    except json.JSONDecodeError:
        pass
    return cp.returncode, out, cp.stderr.decode('utf-8', 'replace')[-400:]


def deliverable_state():
    bom, itf = ENG_S / 'BOM.csv', ENG_S / 'INTERFACES.csv'
    return {'bom_exists': bom.is_file(), 'bom_sha': sha256_file(bom) if bom.is_file() else None,
            'itf_exists': itf.is_file(), 'itf_sha': sha256_file(itf) if itf.is_file() else None}


def main():
    t0 = time.time()
    result = {'review': 'STAGE1_CLOSURE_INDEPENDENT_REVERIFY/A_R17', 'script': 'r_a1_r17_negctl.py',
              'reviewed_run': 'r17_export_chain_20260919', 'cases': [], 'failures': [],
              'verdict': None}

    # 对照（无变异）：exit 0 + PASS + BOM 字节 == 现行 ENG（a6ce5bff…）
    build_sandbox()
    pre = deliverable_state()
    rc, out, err = run_chain()
    post = deliverable_state()
    ok = (rc == 0 and out and out.get('verdict') == 'PASS'
          and post['bom_sha'] == R17_AFTER['BOM.csv']
          and post['itf_sha'] == R17_AFTER['INTERFACES.csv'])
    result['control_bom_only'] = {'exit_code': rc, 'out': out,
                                  'bom_sha_matches_live_full_mode': post['bom_sha'] == R17_AFTER['BOM.csv'],
                                  'interfaces_sha_matches_live': post['itf_sha'] == R17_AFTER['INTERFACES.csv'],
                                  'pass': ok}
    if not ok:
        result['failures'].append(f'control bom-only fail: rc={rc} err={err}')

    def nc(name, mutate, expect_codes, bom_absent_before=False):
        build_sandbox()
        if bom_absent_before:
            (ENG_S / 'BOM.csv').unlink()
        mutate()
        pre = deliverable_state()
        rc, out, err = run_chain()
        post = deliverable_state()
        viol = (out or {}).get('violations', [])
        found = {c: any(c in v for v in viol) for c in expect_codes}
        restored = (pre == post)
        ok = (rc == 2 and out and out.get('verdict') == 'REJECTED_FAIL_CLOSED'
              and all(found.values()) and restored
              and (out.get('bom_interfaces_restored') is True))
        case = {'nc': name, 'exit_code': rc, 'expected_codes': expect_codes,
                'code_found': found, 'all_violations': viol[:8],
                'deliverables_pre': pre, 'deliverables_post': post,
                'bytes_restored': restored, 'pass': ok}
        if not ok:
            case['stderr_tail'] = err
            result['failures'].append(f'{name}: rc={rc} found={found} restored={restored}')
        result['cases'].append(case)

    def m_nc1():  # 旧交接配新 CAD：交接生成后输入已变化
        p = ENG_S / 'wing_kinematics.py'
        p.write_bytes(p.read_bytes() + b'\n# review NC1 tamper\n')
    nc('NC1_stale_handoff_input_hash', m_nc1, ['HANDOFF_INPUT_HASH_MISMATCH'])

    def m_nc1b():  # 同上 + BOM 初始不存在 → 拒绝后仍不存在（_restore None 分支）
        p = ENG_S / 'wing_kinematics.py'
        p.write_bytes(p.read_bytes() + b'\n# review NC1b tamper\n')
    nc('NC1b_stale_hash_bom_absent_before', m_nc1b, ['HANDOFF_INPUT_HASH_MISMATCH'],
       bom_absent_before=True)

    def m_nc3():  # 配置混用：HANDOFF 姿态与回执不一致
        hp = ENG_S / 'results' / 'DYNAMICS_HANDOFF.json'
        h = json.loads(hp.read_text(encoding='utf-8'))
        s = next(x for x in h['states'] if x['state'] == 'service')
        s['q_deg'] = list(s['q_deg'])
        s['q_deg'][0] = s['q_deg'][0] + 1
        hp.write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding='utf-8')
    nc('NC3_state_config_mismatch', m_nc3, ['STATE_CONFIG_MISMATCH'])

    def m_nc6():  # UNKNOWN 零填：交接分配值写 0
        hp = ENG_S / 'results' / 'DYNAMICS_HANDOFF.json'
        h = json.loads(hp.read_text(encoding='utf-8'))
        s = next(x for x in h['states'] if x['state'] == 'service')
        k = sorted(s['mass_owner_values'])[0]
        s['mass_owner_values'][k] = 0.0
        hp.write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding='utf-8')
    nc('NC6_unknown_zero_fill', m_nc6, ['HANDOFF_UNKNOWN_ZERO_FILL'])

    def m_nc8():  # 标准件与父总成双计：注入预算总成下的正质量紧固件行（与被审 NC8 同法）
        rp = ENG_S / 'results' / 'service_instances.json'
        r = json.loads(rp.read_text(encoding='utf-8'))
        prefixes = ('equipment_', 'navigation_camera', 'wing_release_budget_', 'wing_harness_budget_')
        budget = next(row for row in r['instances']
                      if row.get('mass_kg') and str(row.get('id', '')).startswith(prefixes))
        parent = budget.get('parent_assembly')
        r['instances'].append({
            'id': 'review_nc8_mount_screw_1', 'pn': 'WP01-MT-M4X8-REVIEW-NC8',
            'product_role': 'ONBOARD_CANDIDATE', 'representation_role': 'SIMPLIFIED_PROXY',
            'parent_assembly': parent, 'mass_kg': 0.001,
            'mass_owner': 'review_nc8_double_count_owner', 'mass_source': 'CAD_ESTIMATE'})
        rp.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding='utf-8')
        # 同步 HANDOFF 对该回执文件的登记哈希（隔离 NC8 单码面之外的哈希噪声；
        # 实例集合/owner 覆盖面错配属本变异不可避免的连带码，如实记录全部 violations）
        hp = ENG_S / 'results' / 'DYNAMICS_HANDOFF.json'
        h = json.loads(hp.read_text(encoding='utf-8'))
        h['input_sha256'][str(rp.resolve())] = sha256_file(rp)
        hp.write_text(json.dumps(h, ensure_ascii=False, indent=2), encoding='utf-8')
    nc('NC8_standard_part_parent_double_count', m_nc8, ['STANDARD_PART_PARENT_DOUBLE_COUNT'])

    def m_missing():  # 缺交接拒绝
        (ENG_S / 'results' / 'DYNAMICS_HANDOFF.json').unlink()
    nc('NC0_missing_handoff_refused', m_missing, ['HANDOFF_MISSING'])

    n_pass = sum(1 for c in result['cases'] if c['pass'])
    result['summary'] = {'control_pass': result['control_bom_only']['pass'],
                         'nc_cases': len(result['cases']), 'nc_pass': n_pass,
                         'all_exit2_with_restore': all(
                             c['exit_code'] == 2 and c['bytes_restored'] for c in result['cases'])}
    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['elapsed_s'] = round(time.time() - t0, 3)
    write_json(REV / 'evidence' / 'review_a1_r17_negctl.json', result)
    print('verdict', result['verdict'], json.dumps(result['summary'], ensure_ascii=False))
    for c in result['cases']:
        print(c['nc'], 'rc=', c['exit_code'], 'found=', c['code_found'], 'restored=', c['bytes_restored'])
    print('failures', result['failures'])


if __name__ == '__main__':
    main()
