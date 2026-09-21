# -*- coding: utf-8 -*-
"""R07-E4 聚焦构建导出：E4 新增夹套 4 件 + 改件后场螺钉 4 件（M4×22→M4×30 包络）
+ 接口构件 6 件未改作对照（隔框/后端框/后场端塞×4）= 14 STEP。
几何唯一来源：spacecraft_model build()/rear_bulkhead_clamp_parts（与整装同源）。"""
import sys, json, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401  必须先于 build123d（系统坏字体守卫）
from build123d import export_step, Compound

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e4_rear_bulkhead_20260918'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))

import spacecraft_model as sm

MEMBERS_UNMODIFIED = ['rear_launch_bulkhead', 'RB_end_frame_-1',
                      'RB_end_plug_-1_1_1', 'RB_end_plug_-1_1_-1', 'RB_end_plug_-1_-1_1', 'RB_end_plug_-1_-1_-1']
SCREWS_MODIFIED = ['RB_end_screw_-1_1_1', 'RB_end_screw_-1_1_-1', 'RB_end_screw_-1_-1_1', 'RB_end_screw_-1_-1_-1']

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
    for p in sm.rear_bulkhead_clamp_parts(sm.P):
        jobs.append((p['name'], shapes[p['name']], 'E4_CLAMP_SLEEVE_NEW'))
    for m in SCREWS_MODIFIED:
        jobs.append((m, shapes[m], 'INTERFACE_FASTENER_MODIFIED_THIS_RUN'))
    for m in MEMBERS_UNMODIFIED:
        jobs.append((m, shapes[m], 'INTERFACE_MEMBER_UNMODIFIED'))
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
        'run': 'r07_e4_rear_bulkhead_20260918',
        'source': 'spacecraft_model.build + spacecraft_model.rear_bulkhead_clamp_parts',
        'source_sha256': sha256_of(ENG / 'spacecraft_model.py'),
        'parameters_sha256': sha256_of(ENG / 'design_parameters.json'),
        'coordinate_frame': 'S (bus_geometric_center; X longitudinal, Y transverse, Z roof_normal), units mm',
        'new_parts': [p['name'] for p in sm.rear_bulkhead_clamp_parts(sm.P)],
        'modified_fasteners': SCREWS_MODIFIED,
        'modified_fasteners_note': '后场 4 件 M4 螺钉包络 22→30（锚点 x=-183→-191，尖端 x=-161 不变）；pn WP01-MT-M4X30-E4-ENVELOPE_WP03；前场 4 件不动',
        'interface_members_unmodified': MEMBERS_UNMODIFIED,
        'interface_members_note': '隔框/后端框/端塞均未被 E4 修改（Ø8 窗口与 M4 接口均既有，本边不新增任何孔）；导出作读回对照',
        'probe_closure': 'logs/s01c_probe_v1.log（hits 0, instances 487, 螺纹惯例对 4 跳过计入 s04 E 节）',
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
