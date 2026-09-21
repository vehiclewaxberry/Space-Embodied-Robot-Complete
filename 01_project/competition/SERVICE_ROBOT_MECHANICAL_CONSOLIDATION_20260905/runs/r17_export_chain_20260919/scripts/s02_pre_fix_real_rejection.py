# -*- coding: utf-8 -*-
# s02: 真实文件集成负控——新导出器对改前（E1–E4 后失配）交付链必须 fail-closed 拒绝，
# 且 BOM.csv/INTERFACES.csv 字节保持改前不变（恢复机制证明）。
import hashlib, json, os, subprocess, sys, time

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG = r'F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1'

def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()

t0 = time.time()
before = {f: sha(os.path.join(ENG, f)) for f in ['BOM.csv', 'INTERFACES.csv']}
proc = subprocess.run([sys.executable, os.path.join(ENG, 'export_parts_and_bom.py'), '--bom-only'],
                      capture_output=True, text=True, cwd=ENG, encoding='utf-8')
after = {f: sha(os.path.join(ENG, f)) for f in ['BOM.csv', 'INTERFACES.csv']}
restored = before == after
try:
    out = json.loads(proc.stdout)
except Exception:
    out = {'parse_error': True, 'stdout': proc.stdout[-2000:], 'stderr': proc.stderr[-2000:]}
result = {
    'run': 'r17_export_chain_20260919',
    'check': 'pre_fix_real_chain_fail_closed_rejection',
    'scenario': 'E1–E4 改件后三态回执与 HANDOFF 未同步重建（真实旧交接配新 CAD）；'
                '--bom-only 必须拒绝写出且恢复交付物字节',
    'exit_code': proc.returncode,
    'rejected': proc.returncode == 2 and out.get('verdict') == 'REJECTED_FAIL_CLOSED',
    'violation_count': len(out.get('violations', [])),
    'violations': out.get('violations', []),
    'bom_interfaces_bytes_restored': restored,
    'bom_sha256_before': before['BOM.csv'], 'bom_sha256_after': after['BOM.csv'],
    'interfaces_sha256_before': before['INTERFACES.csv'], 'interfaces_sha256_after': after['INTERFACES.csv'],
    'verdict': 'PASS' if (proc.returncode == 2 and out.get('verdict') == 'REJECTED_FAIL_CLOSED' and restored) else 'FAIL',
    'elapsed_s': round(time.time() - t0, 3)}
p = os.path.join(RUN, 'evidence', 'r17_pre_fix_real_rejection.json')
open(p, 'wb').write((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
h = sha(p)
rel = os.path.relpath(p, RUN).replace('\\', '/')
open(p + '.sha256', 'wb').write((h + '  ' + rel + '\n').encode('utf-8'))
print('verdict', result['verdict'], 'exit', proc.returncode, 'violations', result['violation_count'], 'restored', restored)
for x in result['violations'][:10]:
    print('  -', x)
