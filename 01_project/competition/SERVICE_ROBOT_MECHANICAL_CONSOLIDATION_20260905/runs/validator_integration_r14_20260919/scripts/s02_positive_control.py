# -*- coding: utf-8 -*-
# s02: 正控——接入版汇总器消费真实 POSE_SCREEN.json（输入快照绑定），协议/机械碰撞分列
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
# 输入快照绑定：快照哈希 ↔ 现行绝对路径（键必须与 pose_screen 记录的 source_hashes 键逐位一致）
pose = json.loads(open(os.path.join(ENG, 'results', 'POSE_SCREEN.json'), encoding='utf-8').read())
manifest = json.loads(open(os.path.join(RUN, 'inputs', 'INPUT_MANIFEST.json'), encoding='utf-8').read())
snap = {os.path.join(RUN, it['file']): it['sha256'] for it in manifest['inputs']}
MAP = {'wp01_kinematics.py': 'kinematics.py', 'wp01_design_parameters.json': 'design_parameters.json',
       'wp01_LAYOUT_COMPARISON.json': 'LAYOUT_COMPARISON.json',
       'wp01_stowed_build_receipt.json': 'stowed_build_receipt.json',
       'wp01_FINGER_INTERFACE_CHECK.json': 'FINGER_INTERFACE_CHECK.json',
       'wp02_motion_analysis.py': 'motion_analysis.py', 'arm_b601_v1.urdf': 'arm_b601_v1.urdf',
       'wing_kinematics.py': 'wing_kinematics.py'}
snap_by_snapname = {os.path.basename(k): v for k, v in snap.items()}
binding = {}
unbound = []
for path in pose['source_hashes']:
    base = os.path.basename(path)
    cand = None
    for snapname, srcname in MAP.items():
        if base == srcname:
            if srcname in ('kinematics.py', 'design_parameters.json'):
                # 同名歧义：WP01 的 kinematics/design_parameters 仅匹配 wp01 前缀快照
                if 'service_robot_wp01_20260905' in path:
                    cand = snap_by_snapname.get(snapname)
            elif srcname == 'wing_kinematics.py':
                if 'service_robot_wp03' in path:
                    cand = snap_by_snapname.get(snapname)
            elif srcname == 'motion_analysis.py':
                if 'service_robot_wp02_20260905' in path:
                    cand = snap_by_snapname.get(snapname)
            else:
                cand = snap_by_snapname.get(snapname)
    if cand:
        binding[path] = cand
    else:
        unbound.append(path)
bp = os.path.join(RUN, 'inputs', 'snapshot_binding.json')
open(bp, 'wb').write((json.dumps(binding, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
sidecar(bp)

out_run = os.path.join(RUN, 'evidence', 'r17b_strict_integration_positive.json')
proc = subprocess.run([sys.executable, os.path.join(ENG, 'strict_surface_integration.py'),
                       '--snapshot-binding', bp, '--output', out_run],
                      capture_output=True, text=True, cwd=ENG, encoding='utf-8')
result = json.loads(open(out_run, encoding='utf-8').read()) if os.path.exists(out_run) else None
# 同步写入工程 results（新文件，不覆盖既有交付物）
prod = os.path.join(ENG, 'results', 'STRICT_SURFACE_INTEGRATION.json')
open(prod, 'wb').write(open(out_run, 'rb').read())
log = {'run': 'validator_integration_r14_20260919', 'check': 'strict_integration_positive_control',
       'snapshot_binding_entries': len(binding), 'unbound_source_paths': unbound,
       'aggregator_stdout': proc.stdout.strip(), 'aggregator_stderr_tail': proc.stderr[-1000:],
       'protocol': result['protocol'] if result else None,
       'mechanical_collision': {k: v for k, v in result['mechanical_collision'].items() if k != 'per_pose'} if result else None,
       'mechanical_per_pose': result['mechanical_collision']['per_pose'] if result else None,
       'overall': result['overall'] if result else None,
       'production_copy': '20_engineering/service_robot_wp03_spacecraft_body_r1/results/STRICT_SURFACE_INTEGRATION.json（新文件）',
       'verdict': 'PASS' if result and result['overall'] == 'PASS' and not unbound else 'FAIL',
       'elapsed_s': round(time.time() - t0, 3)}
lp = os.path.join(RUN, 'logs', 's02_positive_control_log.json')
open(lp, 'wb').write((json.dumps(log, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
sidecar(lp)
sidecar(out_run)
print('verdict', log['verdict'], '| overall', log['overall'], '| protocol', log['protocol']['verdict'] if result else None,
      '| mechanical', log['mechanical_collision']['verdict'] if result else None, '| unbound', unbound)
