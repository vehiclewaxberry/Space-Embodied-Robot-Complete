# -*- coding: utf-8 -*-
# s04: 修复后完整导出链重跑（build→receipts→dynamics_handoff→校验→BOM），日志落盘
import hashlib, json, os, subprocess, sys, time

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG = r'F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/service_robot_wp03_spacecraft_body_r1'

def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()

def sidecar(p):
    h = sha(p)
    rel = os.path.relpath(p, RUN).replace('\\', '/')
    open(p + '.sha256', 'wb').write((h + '  ' + rel + '\n').encode('utf-8'))

t0 = time.time()
proc = subprocess.run([sys.executable, os.path.join(ENG, 'export_parts_and_bom.py')],
                      capture_output=True, text=True, cwd=ENG, encoding='utf-8')
tail = proc.stdout[-3000:]
parsed = None
for line in reversed(proc.stdout.split('\n')):
    pass
# 末端 JSON 为导出器摘要
idx = proc.stdout.rfind('{\n  "verdict"')
if idx >= 0:
    try:
        parsed = json.loads(proc.stdout[idx:])
    except Exception:
        parsed = None
log = {'run': 'r17_export_chain_20260919', 'check': 'full_export_chain_after_fix',
       'command': 'python export_parts_and_bom.py（完整模式：build service 结构+parts → dynamics_handoff 子进程 → HANDOFF 校验 → BOM）',
       'exit_code': proc.returncode, 'exporter_summary': parsed,
       'stdout_tail': tail, 'stderr_tail': proc.stderr[-2000:],
       'verdict': 'PASS' if proc.returncode == 0 and parsed and parsed.get('verdict') == 'PASS' else 'FAIL',
       'elapsed_s': round(time.time() - t0, 3)}
p = os.path.join(RUN, 'logs', 's04_full_export_log.json')
open(p, 'wb').write((json.dumps(log, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
sidecar(p)
print('verdict', log['verdict'], 'exit', proc.returncode)
if parsed:
    print(json.dumps(parsed, ensure_ascii=False, indent=1))
