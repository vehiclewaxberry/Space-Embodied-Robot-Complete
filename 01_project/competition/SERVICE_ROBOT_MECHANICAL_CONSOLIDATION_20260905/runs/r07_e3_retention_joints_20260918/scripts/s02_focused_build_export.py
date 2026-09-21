# -*- coding: utf-8 -*-
"""R07-E3 聚焦构建导出：受影响构件 8 件（2 上纵梁[各+4 孔] + 2 保持横梁[端面盲孔+竖孔] +
2 屋顶耳座_-94.15[竖孔] + 2 足叉脚座[盲孔]，本 run 实改）+ 24 E3 保持件 = 32 STEP。
几何唯一来源：spacecraft_model build()/retention_clamp_parts/retention_foot_parts（与整装同源）。
注意：hold_* 为 WP03 原生实例名（无 _WP03 后缀）；上纵梁哈希与 E1/E2 run 不再一致属预期（新增孔 delta）。"""
import sys, json, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401  必须先于 build123d（系统坏字体守卫）
from build123d import export_step, Compound

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e3_retention_joints_20260918'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))

import spacecraft_model as sm

MEMBERS = ['RB_longeron_1_1', 'RB_longeron_-1_1',
           'hold_crossbeam_0', 'hold_crossbeam_1',
           'hold_roof_lug_0_-94.15', 'hold_roof_lug_1_-94.15',
           'hold_pivot_clevis_0', 'hold_pivot_clevis_1']

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
        jobs.append((m, shapes[m], 'INTERFACE_MEMBER_MODIFIED_THIS_RUN'))
    for p in sm.retention_clamp_parts(sm.P) + sm.retention_foot_parts(sm.P):
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
        'run': 'r07_e3_retention_joints_20260918',
        'source': 'spacecraft_model.build + spacecraft_model.retention_clamp_parts + spacecraft_model.retention_foot_parts',
        'source_sha256': sha256_of(ENG / 'spacecraft_model.py'),
        'parameters_sha256': sha256_of(ENG / 'design_parameters.json'),
        'coordinate_frame': 'S (bus_geometric_center; X longitudinal, Y transverse, Z roof_normal), units mm',
        'interface_members_modified': MEMBERS,
        'interface_members_note': '本 run 实改 8 构件（孔去除 delta）：上纵梁每根 +4 个 Y 向贯穿孔(Ø3.4@z=103.65)；保持横梁每根 +4 端面盲孔(Ø3.4深7)+2 竖孔(Ø4.5@y=-90.65)；耳座_-94.15 每座 +2 竖孔；足叉脚座每叉 +2 盲孔(Ø4.5深7打通至槽底)。上纵梁哈希与 E1/E2 不一致属预期；+y 侧耳座(94.15)未改不导出',
        'probe_closure': 'logs/s01b_probe_FAIL_v1.log（4 HIT 16.37mm3）-> v2 参数修复(s01d) -> logs/s01b_probe_v2.log（hits 0, instances 483）',
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
