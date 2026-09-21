# -*- coding: utf-8 -*-
# s06: --bom-only 依赖拆分验证（机器证据）：
# (a) 模块导入不引入任何 CAD 模块（sys.modules 快照）；
# (b) --bom-only 功能运行 PASS 且 BOM/INTERFACES 与完整模式输出字节一致；
# (c) 缺失 HANDOFF 时 --bom-only 拒绝写出且交付物字节不变（集成负控，try/finally 恢复）。
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
# (a) 无 CAD 导入机器证据
code = ("import sys, importlib.util; "
        "spec = importlib.util.spec_from_file_location('export_parts_and_bom', r'%s/export_parts_and_bom.py'); "
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); "
        "cad = sorted(x for x in sys.modules if x.split('.')[0] in "
        "('spacecraft_model','root_structure','cadgen','build123d','OCP','kinematics','wing_kinematics')); "
        "import json; print(json.dumps({'cad_modules_loaded': cad}))" % ENG)
proc_a = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, cwd=ENG, encoding='utf-8')
no_cad = json.loads(proc_a.stdout.strip())

# (b) 功能运行 + 字节一致
bom_before = sha(os.path.join(ENG, 'BOM.csv'))
itf_before = sha(os.path.join(ENG, 'INTERFACES.csv'))
proc_b = subprocess.run([sys.executable, os.path.join(ENG, 'export_parts_and_bom.py'), '--bom-only'],
                        capture_output=True, text=True, cwd=ENG, encoding='utf-8')
idx = proc_b.stdout.rfind('{\n  "verdict"')
parsed_b = json.loads(proc_b.stdout[idx:]) if idx >= 0 else None
byte_identical = bom_before == sha(os.path.join(ENG, 'BOM.csv')) and itf_before == sha(os.path.join(ENG, 'INTERFACES.csv'))

# (c) 缺失 HANDOFF 集成负控
handoff = os.path.join(ENG, 'results', 'DYNAMICS_HANDOFF.json')
handoff_bak = handoff + '.r17_tmp_bak'
os.replace(handoff, handoff_bak)
try:
    proc_c = subprocess.run([sys.executable, os.path.join(ENG, 'export_parts_and_bom.py'), '--bom-only'],
                            capture_output=True, text=True, cwd=ENG, encoding='utf-8')
    idx = proc_c.stdout.rfind('{\n  "verdict"')
    parsed_c = json.loads(proc_c.stdout[idx:]) if idx >= 0 else {'raw': proc_c.stdout[-500:], 'stderr': proc_c.stderr[-500:]}
    unchanged_during_refusal = bom_before == sha(os.path.join(ENG, 'BOM.csv')) and itf_before == sha(os.path.join(ENG, 'INTERFACES.csv'))
finally:
    os.replace(handoff_bak, handoff)

result = {'run': 'r17_export_chain_20260919', 'check': 'bom_only_dependency_split_verification',
          'a_no_cad_import': {'evidence': no_cad, 'pass': no_cad['cad_modules_loaded'] == []},
          'b_functional_run': {'exit_code': proc_b.returncode, 'summary': parsed_b,
                               'bom_interfaces_byte_identical_to_full_mode': byte_identical,
                               'pass': proc_b.returncode == 0 and parsed_b and parsed_b.get('verdict') == 'PASS' and byte_identical},
          'c_missing_handoff_refusal': {'exit_code': proc_c.returncode, 'response': parsed_c,
                                        'deliverables_unchanged': unchanged_during_refusal,
                                        'pass': proc_c.returncode == 2 and parsed_c.get('verdict') == 'REJECTED_FAIL_CLOSED' and unchanged_during_refusal},
          'verdict': None, 'elapsed_s': round(time.time() - t0, 3)}
result['verdict'] = 'PASS' if all(result[k]['pass'] for k in ('a_no_cad_import', 'b_functional_run', 'c_missing_handoff_refusal')) else 'FAIL'
p = os.path.join(RUN, 'evidence', 'r17_bom_only_verification.json')
open(p, 'wb').write((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
sidecar(p)
print('verdict', result['verdict'])
print(' (a) cad modules loaded:', no_cad['cad_modules_loaded'])
print(' (b) exit', proc_b.returncode, 'byte_identical', byte_identical)
print(' (c) exit', proc_c.returncode, 'refused+unchanged', unchanged_during_refusal)
