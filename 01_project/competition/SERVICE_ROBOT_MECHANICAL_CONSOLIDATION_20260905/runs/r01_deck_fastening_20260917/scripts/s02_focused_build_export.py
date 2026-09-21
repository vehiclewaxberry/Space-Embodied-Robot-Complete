# -*- coding: utf-8 -*-
"""R01 聚焦构建：仅建两甲板/八角材/两剪力腹板/32 紧固包络，导出 STEP 与构建日志。
几何唯一来源：spacecraft_model.deck_fastening_parts（与整星 build() 同源）。"""
import sys, json, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401  必须先于 build123d（系统坏字体守卫）
from build123d import export_step

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))

import spacecraft_model as sm

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sha256_of(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    t0 = time.time()
    log = []
    parts = sm.deck_fastening_parts(sm.P)
    counts = {}
    for p in parts:
        counts[p['kind']] = counts.get(p['kind'], 0) + 1
    log.append({'event': 'build', 'part_count': len(parts), 'counts_by_kind': counts})
    exp = RUN / 'exports'
    manifest = []
    for p in parts:
        f = exp / f"{p['name']}.step"
        export_step(p['shape'], str(f))
        bb = p['shape'].bounding_box()
        manifest.append({
            'name': p['name'], 'kind': p['kind'], 'mount': p['mount'],
            'file': f.name, 'sha256': sha256_of(f), 'bytes': f.stat().st_size,
            'shape_valid': bool(p['shape'].is_valid),
            'solid_count': len(p['shape'].solids()),
            'bbox_min_mm': [round(v, 6) for v in bb.min],
            'bbox_max_mm': [round(v, 6) for v in bb.max],
        })
        log.append({'event': 'export', 'name': p['name'], 'file': f.name})
    wlf(exp / 'EXPORT_MANIFEST.json', json.dumps({
        'run': 'r01_deck_fastening_20260917',
        'source': 'spacecraft_model.deck_fastening_parts (parameter-driven, design_parameters.json deck_fastening_r01)',
        'source_sha256': sha256_of(ENG / 'spacecraft_model.py'),
        'parameters_sha256': sha256_of(ENG / 'design_parameters.json'),
        'coordinate_frame': 'S (bus_geometric_center; X longitudinal, Y transverse, Z roof_normal), units mm',
        'parts': manifest,
    }, ensure_ascii=False, indent=2) + '\n')
    log.append({'event': 'done', 'elapsed_s': round(time.time() - t0, 3)})
    wlf(RUN / 'logs' / 's02_build_export_log.json', json.dumps(log, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(counts, ensure_ascii=False))
    print('parts:', len(parts), 'elapsed_s:', round(time.time() - t0, 2))
    for m in manifest:
        if not m['shape_valid']:
            print('INVALID', m['name'])

if __name__ == '__main__':
    main()
