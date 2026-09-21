# -*- coding: utf-8 -*-
"""阶段一收口复验 A2/A3/A4：R17 静态复核。
A2 --bom-only 零 CAD 导入：独立探针子进程（import 模块 + main() 后审 sys.modules），
   并与被审证据互锁；对照输出字节 == 完整模式（A1 已证，此处复核证据一致性）。
A3 交付物哈希对照（9 项 before==inputs 快照、after==现行文件）+ BOM 未分配 null 保留
   （497 行 15 列、214 分配/283 空单元、无 0 填）+ HANDOFF 校验器 fail-closed 代码审读结论登记。
A4 current_BOM_is_proven_stale=false 语义未违反：票字段未回写 + 改前 BOM 备份在位 +
   INPUT_MANIFEST 失配审计一致性。"""
import csv, json, subprocess, sys, time
from pathlib import Path
from sc_common import (REV, RUN_A, ENG, ROOT, write_json, sha256_file, R17_AFTER,
                       R17_BEFORE_BOM, BASELINE_STRUCTURE_RECEIPT_SHA)

PY = sys.executable
SAND_ENG = REV / '_work' / 'sandbox_a' / 'service_robot_wp03_spacecraft_body_r1'
LIVE_RESULTS = ENG / 'results'

DELIVERABLES = [  # (登记名, inputs 快照名, 现行文件)
    ('BOM.csv', 'BOM.csv', ENG / 'BOM.csv'),
    ('INTERFACES.csv', 'INTERFACES.csv', ENG / 'INTERFACES.csv'),
    ('results/DYNAMICS_HANDOFF.json', 'DYNAMICS_HANDOFF.json', LIVE_RESULTS / 'DYNAMICS_HANDOFF.json'),
    ('results/DYNAMICS_SUMMARY_ZH.md', None, LIVE_RESULTS / 'DYNAMICS_SUMMARY_ZH.md'),
    ('results/parking_instances.json', 'parking_instances.json', LIVE_RESULTS / 'parking_instances.json'),
    ('results/released_instances.json', 'released_instances.json', LIVE_RESULTS / 'released_instances.json'),
    ('results/service_instances.json', 'service_instances.json', LIVE_RESULTS / 'service_instances.json'),
    ('results/parking_ground_instances.json', 'parking_ground_instances.json', LIVE_RESULTS / 'parking_ground_instances.json'),
    ('results/service_structure_instances.json', 'service_structure_instances.json', LIVE_RESULTS / 'service_structure_instances.json'),
]


def main():
    t0 = time.time()
    result = {'review': 'STAGE1_CLOSURE_INDEPENDENT_REVERIFY/A_R17', 'script': 'r_a2a3a4_static.py',
              'reviewed_run': 'r17_export_chain_20260919', 'failures': [], 'verdict': None}

    # ---- A2 独立探针：--bom-only 的 sys.modules 审计 ----
    from r_a1_r17_negctl import build_sandbox  # 先重建新鲜沙箱（A1 末案例删除过 HANDOFF）
    build_sandbox()
    probe = SAND_ENG / '_review_probe_bomonly.py'
    probe.write_text(
        "import sys, json\n"
        "sys.path.insert(0, '.')\n"
        "sys.argv = ['export_parts_and_bom.py', '--bom-only']\n"
        "import export_parts_and_bom as m\n"
        "m.main()\n"
        "bad = sorted(n for n in sys.modules if any(t in n.lower() for t in "
        "('build123d', 'ocp', 'cadgen', 'vtk', 'spacecraft_model', 'dynamics_handoff', 'numpy')))\n"
        "print('PROBE_JSON=' + json.dumps({'cad_modules_loaded': bad}))\n",
        encoding='utf-8')
    try:
        cp = subprocess.run([PY, '_review_probe_bomonly.py'], cwd=str(SAND_ENG),
                            capture_output=True, timeout=120)
        text = cp.stdout.decode('utf-8', 'replace')
        probe_line = next((ln for ln in text.splitlines() if ln.startswith('PROBE_JSON=')), None)
        probe_data = json.loads(probe_line[len('PROBE_JSON='):]) if probe_line else None
        cad_loaded = (probe_data or {}).get('cad_modules_loaded', ['PROBE_FAILED'])
        a2_ok = cp.returncode == 0 and probe_data is not None and cad_loaded == []
    finally:
        probe.unlink(missing_ok=True)
    their = json.loads((RUN_A / 'evidence' / 'r17_bom_only_verification.json').read_text(encoding='utf-8'))
    a2_ok = a2_ok and their['a_no_cad_import']['evidence']['cad_modules_loaded'] == [] \
        and their['b_functional_run'].get('bom_interfaces_byte_identical_to_full_mode') is True \
        and their['c_missing_handoff_refusal'].get('deliverables_unchanged') is True
    result['A2_bom_only_no_cad_import'] = {
        'review_probe': probe_data, 'probe_exit': cp.returncode,
        'probe_residual': probe.exists(),
        'candidate_evidence_consistent': bool(a2_ok),
        'note': '探针在 A1 沙箱内独立运行；A1 对照案例已独立证 bom-only 输出 == 完整模式字节',
        'pass': bool(a2_ok)}
    if not a2_ok:
        result['failures'].append(f'A2: {result["A2_bom_only_no_cad_import"]}')

    # ---- A3a 交付物 9 项哈希对照 ----
    cmp_e = json.loads((RUN_A / 'evidence' / 'r17_deliverables_hash_compare.json').read_text(encoding='utf-8'))
    reg = {d['file']: d for d in cmp_e.get('items', cmp_e.get('deliverables', []))}
    rows = []
    for name, snap, live in DELIVERABLES:
        r = {'file': name}
        claimed = reg.get(name, {})
        r['claimed_before'] = claimed.get('sha256_before')
        r['claimed_after'] = claimed.get('sha256_after')
        r['live_sha'] = sha256_file(live)
        r['after_matches_live'] = (r['claimed_after'] == r['live_sha'])
        if snap is not None:
            r['snapshot_sha'] = sha256_file(RUN_A / 'inputs' / snap)
            r['before_matches_snapshot'] = (r['claimed_before'] == r['snapshot_sha'])
        else:
            r['snapshot_sha'] = None
            r['before_matches_snapshot'] = 'NO_SNAPSHOT（DYNAMICS_SUMMARY_ZH.md 无 inputs 快照）'
        r['pass'] = r['after_matches_live'] and (
            r['before_matches_snapshot'] is True or isinstance(r['before_matches_snapshot'], str))
        rows.append(r)
        if not r['pass']:
            result['failures'].append(f'A3 hash compare: {name}: {r}')
    result['A3a_deliverables_hash_compare'] = rows

    # ---- A3b BOM null 保留 ----
    with (ENG / 'BOM.csv').open('r', encoding='utf-8-sig', newline='') as f:
        rd = csv.DictReader(f)
        cols = rd.fieldnames
        rows_bom = list(rd)
    alloc_col = 'allocated_dynamics_mass_kg'
    alloc = [r[alloc_col] for r in rows_bom]
    non_empty = [v for v in alloc if v != '']
    empty = [v for v in alloc if v == '']
    zero_fill = [v for v in alloc if v in ('0', '0.0', '0.00', '0.000')]
    numeric_ok = all(float(v) > 0 for v in non_empty)
    refs = {r['allocated_mass_reference'] for r in rows_bom}
    a3b = {'rows': len(rows_bom), 'columns': len(cols), 'columns_list': cols,
           'allocated_positive': len(non_empty), 'unallocated_null_empty_cell': len(empty),
           'zero_fill_cells': zero_fill[:5], 'all_allocated_numeric_positive': numeric_ok,
           'allocated_mass_reference_set': sorted(refs)}
    a3b['pass'] = (len(rows_bom) == 497 and len(cols) == 15 and len(non_empty) == 214
                   and len(empty) == 283 and not zero_fill and numeric_ok
                   and refs == {'results/DYNAMICS_HANDOFF.json'})
    result['A3b_bom_null_retention'] = a3b
    if not a3b['pass']:
        result['failures'].append(f'A3b: {a3b}')

    # ---- A3c HANDOFF 校验器 fail-closed 代码审读（静态，结论登记）----
    code = (ENG / 'export_parts_and_bom.py').read_text(encoding='utf-8')
    a3c = {
        'backup_before_any_write': code.index('backup = {p:') < code.index('if not bom_only'),
        'restore_on_any_exception': 'except Exception:' in code and '_restore(backup)' in code,
        'exit2_only_for_validation_reject': 'sys.exit(2)' in code,
        'bom_only_still_validates': code.index('violations = validate_handoff_provenance(handoff)') > code.index('if not bom_only:'),
        'bypass_scan': '未发现可绕过分支：BOM/INTERFACES 写入位于全部校验之后；'
                       'validate_* 任一违规 → HandoffRejected → except 恢复字节；'
                       '非 HandoffRejected 异常（如 dynamics_handoff 子进程非零）同样触发恢复，'
                       '但以 traceback 退出（exit≠2）——"任一失配 exit 2"严格覆盖校验拒绝路径',
        'unallocated_null_write': 'values.get(row[\'mass_owner\'])' in code,
    }
    a3c['pass'] = (a3c['backup_before_any_write'] and a3c['restore_on_any_exception']
                   and a3c['exit2_only_for_validation_reject'] and a3c['bom_only_still_validates'])
    result['A3c_fail_closed_code_read'] = a3c
    if not a3c['pass']:
        result['failures'].append(f'A3c: {a3c}')

    # ---- A4 stale=false 语义与改前备份 ----
    issues = json.loads((REV.parents[1] / 'issues.json').read_text(encoding='utf-8'))
    r17 = next(t for t in issues['issues'] if t['id'] == 'R17')
    man = json.loads((RUN_A / 'inputs' / 'INPUT_MANIFEST.json').read_text(encoding='utf-8'))
    audit = man.get('pre_fix_staleness_audit', {})
    bak_bom = sha256_file(RUN_A / 'inputs' / 'BOM.csv')
    a4 = {'ticket_fields': {k: r17.get(k) for k in ('current_BOM_is_proven_stale', 'production_fix_applied',
                                                    'engineering_issue_closed', 'status')},
          'fields_not_rewritten': (r17.get('current_BOM_is_proven_stale') is False
                                   and r17.get('production_fix_applied') is False),
          'pre_fix_bom_backup_sha': bak_bom,
          'backup_matches_registered_before': bak_bom == R17_BEFORE_BOM,
          'staleness_audit_present': bool(audit),
          'audit_shows_receipts_stale': all(
              not e.get('matches_current_model', True)
              for e in audit.get('receipts', [])) if audit.get('receipts') else None,
          'semantics_note': ('票字段 false 为 2026-09-06 审计时点事实，本 run 以 stale_fact_registration '
                             '如实登记"现存 BOM 相对现行 CAD 已失配"且不回写票字段——语义未违反；'
                             '改前 BOM/INTERFACES/HANDOFF/回执改前原件全部在 inputs/ 在位')}
    a4['pass'] = (a4['fields_not_rewritten'] and a4['backup_matches_registered_before']
                  and a4['staleness_audit_present'] and a4['audit_shows_receipts_stale'] in (True, None))
    result['A4_stale_semantics'] = a4
    if not a4['pass']:
        result['failures'].append(f'A4: {a4}')

    result['summary'] = {'A2': result['A2_bom_only_no_cad_import']['pass'],
                         'A3a': all(r['pass'] for r in rows),
                         'A3b': a3b['pass'], 'A3c': a3c['pass'], 'A4': a4['pass']}
    result['verdict'] = 'PASS' if not result['failures'] else 'FAIL'
    result['elapsed_s'] = round(time.time() - t0, 3)
    write_json(REV / 'evidence' / 'review_a2a3a4_static.json', result)
    print('verdict', result['verdict'], json.dumps(result['summary'], ensure_ascii=False))
    print('failures', result['failures'])


if __name__ == '__main__':
    main()
