# -*- coding: utf-8 -*-
"""R07-E1 run: 输入快照与 sha256 清单（LF 二进制写）。
快照改件前输入；另备份将被烟测覆盖的 results/service_structure_instances.json。"""
import hashlib, shutil, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_root_longeron_anchoring_20260917'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
W2 = ROOT / '20_engineering/service_robot_wp02_20260905'

FILES = [
    ENG / 'spacecraft_model.py',
    ENG / 'design_parameters.json',
    ENG / 'root_structure.py',
    ENG / 'kinematics.py',
    ENG / 'wing_kinematics.py',
    W2 / 'parts_model.py',
    W2 / 'design_parameters.json',
    ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/issues.json',
    ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/WP03_NEXT_STAGE_MECHANICAL_PLAN_20260906.md',
]

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sha256_of(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    man = []
    for f in FILES:
        data = f.read_bytes()
        suffix = 'wp02_' if f.parent == W2 else ''
        dst = RUN / 'inputs' / (suffix + f.name)
        shutil.copy2(f, dst)
        man.append({
            'path': str(f).replace(chr(92), '/'),
            'sha256': hashlib.sha256(data).hexdigest(),
            'bytes': len(data),
            'snapshot': str(dst).replace(chr(92), '/'),
            'snapshot_sha256': sha256_of(dst),
        })
    # 备份烟测将覆盖的现存实例清单（经核实为 R01 前旧版，source 11bd80a6...）
    stale = ENG / 'results/service_structure_instances.json'
    if stale.exists():
        shutil.copy2(stale, RUN / 'logs' / 'service_structure_instances.json.pre_e1_smoke_bak')
    manifest = {
        'run': 'r07_root_longeron_anchoring_20260917',
        'created_by': 'WP03_R07_E1_builder (single CAD builder)',
        'role': 'pre_change_input_snapshot',
        'note': '改件前输入快照；sha256 对原文件字节计算。WP02 文件只读不改，快照仅为来源绑定。',
        'files': man,
    }
    wlf(RUN / 'inputs' / 'INPUT_MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    for m in man:
        print(m['sha256'][:16], m['bytes'], m['path'])

if __name__ == '__main__':
    main()
