# -*- coding: utf-8 -*-
"""R07-E2 聚焦构建导出：接口构件（4 纵梁 + 8 端塞，未修改，作跨 run 哈希对照）+ 28 E2 保持件。
几何唯一来源：spacecraft_model build()/transverse_retention_parts（与整装同源）。"""
import sys, json, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401  必须先于 build123d（系统坏字体守卫）
from build123d import export_step, Compound

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e2_endplug_retention_20260918'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))

import spacecraft_model as sm

MEMBERS = (['RB_longeron_1_1', 'RB_longeron_-1_1', 'RB_longeron_1_-1', 'RB_longeron_-1_-1'] +
           [f'RB_end_plug_{sx}_{sy}_{sz}' for sx in [-1, 1] for sy in [-1, 1] for sz in [-1, 1]])

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sha256_of(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    t0 = time.time()
    log = []
    model, shapes, receipt = sm.build('service', include_arm=False)
    log.append({'event': 'build', 'instances': len(receipt['instances'])})
    exp = RUN / 'exports'
    manifest = []
    jobs = []
    for m in MEMBERS:
        jobs.append((m, shapes[m], 'INTERFACE_MEMBER_UNMODIFIED'))
    for p in sm.transverse_retention_parts(sm.P):
        jobs.append((p['name'], shapes[p['name']], p['kind']))
    for name, shp, kind in jobs:
        f = exp / f'{name}.step'
        solids = shp.solids()
        payload = solids[0] if len(solids) == 1 else Compound(children=list(solids))
        export_step(payload, str(f))
        bb = shp.bounding_box()
        manifest.append({
            'name': name, 'kind': kind, 'file': f.name, 'sha256': sha256_of(f), 'bytes': f.stat().st_size,
            'shape_valid': bool(shp.is_valid), 'solid_count': len(shp.solids()),
            'volume_mm3': round(shp.volume, 6),
            'bbox_min_mm': [round(v, 6) for v in bb.min],
            'bbox_max_mm': [round(v, 6) for v in bb.max],
        })
        log.append({'event': 'export', 'name': name, 'file': f.name})
    wlf(exp / 'EXPORT_MANIFEST.json', json.dumps({
        'run': 'r07_e2_endplug_retention_20260918',
        'source': 'spacecraft_model.build + spacecraft_model.transverse_retention_parts',
        'source_sha256': sha256_of(ENG / 'spacecraft_model.py'),
        'parameters_sha256': sha256_of(ENG / 'design_parameters.json'),
        'coordinate_frame': 'S (bus_geometric_center; X longitudinal, Y transverse, Z roof_normal), units mm',
        'interface_members_unmodified': MEMBERS,
        'interface_members_note': 'E2 不修改任何既有构件；纵梁导出哈希应与 E1 run 同名文件逐位一致（跨 run 对照项），端塞为现行 7.8 重建体',
        'parts': manifest,
    }, ensure_ascii=False, indent=2) + '\n')
    log.append({'event': 'done', 'elapsed_s': round(time.time() - t0, 3)})
    wlf(RUN / 'logs' / 's02_build_export_log.json', json.dumps(log, ensure_ascii=False, indent=2) + '\n')
    print('exported:', len(manifest), 'instances:', len(receipt['instances']), 'elapsed_s:', round(time.time() - t0, 2))
    for m in manifest:
        if not m['shape_valid']:
            print('INVALID', m['name'])

if __name__ == '__main__':
    main()
