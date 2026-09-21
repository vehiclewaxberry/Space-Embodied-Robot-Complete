# -*- coding: utf-8 -*-
# s00: 输入快照清单 + 改前哈希登记
import hashlib, json, os

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()

ROLE = {
    'pose_screen.py': '被修改对象：硬编码 35/36 判据消除、合同/事件身份字段接入',
    'strict_surface_aggregator_prototype.py': '隔离原型（本包不动，接入版新建于工程目录）',
    'wing_kinematics.py': '场景输入：WP03 翼运动学',
    'wp03_design_parameters.json': 'R14 扰动对象（deck_fastening_r01 段）',
    'wp01_kinematics.py': '关节/碰撞表示来源（URDF FK）',
    'wp01_design_parameters.json': '场景姿态来源（states.stowed/work）',
    'wp01_LAYOUT_COMPARISON.json': '既有候选姿态序列来源',
    'wp01_stowed_build_receipt.json': 'M3R 包络夹具来源',
    'wp01_FINGER_INTERFACE_CHECK.json': '名义双指间隙证据',
    'wp02_motion_analysis.py': '三角面读取/裁剪来源',
    'arm_b601_v1.urdf': 'accepted 臂关节树/碰撞表示',
    'POSE_SCREEN_before.json': '改前 pose_screen 输出（旧判据）',
    'issues.json': 'R14 原票快照',
}
inputs = []
for fn in sorted(os.listdir(os.path.join(RUN, 'inputs'))):
    p = os.path.join(RUN, 'inputs', fn)
    if os.path.isfile(p):
        inputs.append({'file': 'inputs/' + fn, 'bytes': os.path.getsize(p), 'sha256': sha(p),
                       'role': ROLE.get(fn, '')})
out = {'run': 'validator_integration_r14_20260919', 'check': 's00_input_snapshot',
       'inputs': inputs,
       'snapshot_binding': '接入版汇总器运行时核对：现行文件哈希须与本快照逐位一致（过期来源拒绝）'}
p1 = os.path.join(RUN, 'inputs', 'INPUT_MANIFEST.json')
open(p1, 'wb').write((json.dumps(out, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))

def sidecar(p):
    h = sha(p)
    rel = os.path.relpath(p, RUN).replace('\\', '/')
    open(p + '.sha256', 'wb').write((h + '  ' + rel + '\n').encode('utf-8'))

for it in inputs:
    sidecar(os.path.join(RUN, it['file']))
sidecar(p1)
print('inputs', len(inputs))
for it in inputs:
    print(' ', it['file'], it['sha256'][:16])
