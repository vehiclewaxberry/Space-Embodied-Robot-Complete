# -*- coding: utf-8 -*-
"""R07-E4 候选几何 fail-fast 探针（非裁决）：整装构建后，E4 夹套 4 件 + 改件后场螺钉 4 件 vs
全部物理/代理实例布尔公共体积预筛（OCP BRepAlgoAPI_Common 原生路径，E2 审阅勘误 O2 口径）。
已知豁免：改件螺钉 vs 自有端塞 = E2 登记的螺纹啮合惯例对（s04 E 节结转，探针跳过不计命中）。"""
import sys, json, time, itertools
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp

ROOT = Path(__file__).resolve().parents[6]
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm

TOL = 1e-6
E4PREFIX = ('e4_clamp_', 'RB_end_screw_-1_')

def volume_of(shape):
    g = GProp_GProps(); BRepGProp.VolumeProperties_s(shape, g)
    return g.Mass()

def cv(a, b):
    op = BRepAlgoAPI_Common(a.wrapped, b.wrapped)
    op.Build()
    if not op.IsDone():
        return 'ERR:not_done'
    return float(volume_of(op.Shape()))

def bbox(s):
    b = s.bounding_box()
    return (b.min.X, b.min.Y, b.min.Z, b.max.X, b.max.Y, b.max.Z)

def overlap(a, b):
    return not (a[3] < b[0] or b[3] < a[0] or a[4] < b[1] or b[4] < a[1] or a[5] < b[2] or b[5] < a[2])

def main():
    t0 = time.time()
    model, shapes, receipt = sm.build('service', include_arm=False)
    reps = {r['id']: r['representation_role'] for r in receipt['instances']}
    e4 = sorted(n for n in shapes if n.startswith(E4PREFIX))
    others = {n: s for n, s in shapes.items() if reps.get(n) in ('PHYSICAL_GEOMETRY', 'SIMPLIFIED_PROXY') and n not in e4}
    bb = {n: bbox(s) for n, s in shapes.items()}
    hits = []
    skipped_thread_conv = []
    pairs = [(a, b) for a in e4 for b in others if overlap(bb[a], bb[b])]
    pairs += [(a, b) for a, b in itertools.combinations(e4, 2) if overlap(bb[a], bb[b])]
    for a, b in pairs:
        # E2 登记螺纹啮合惯例：改件螺钉 vs 自有端塞（延长仅在头侧，重叠区不变）
        if a.startswith('RB_end_screw_-1_') and b == a.replace('RB_end_screw_', 'RB_end_plug_'):
            skipped_thread_conv.append((a, b)); continue
        v = cv(shapes[a], shapes[b])
        if isinstance(v, str) or v > TOL:
            hits.append((a, b, v))
    print('e4_parts', len(e4), 'instances', len(receipt['instances']), 'pairs_checked', len(pairs),
          'skipped_thread_convention', len(skipped_thread_conv))
    print('hits', len(hits), 'elapsed_s', round(time.time() - t0, 2))
    for a, b, v in hits:
        print('HIT', a, 'vs', b, v)

if __name__ == '__main__':
    main()
