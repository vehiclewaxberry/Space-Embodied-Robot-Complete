# -*- coding: utf-8 -*-
"""R07-E2 候选几何 fail-fast 探针（非裁决）：整装构建后，E2 28 件 vs 全部物理/代理实例布尔公共体积预筛。
任何 >1e-6 mm3 的命中先打印出来，供设计修正（正式裁决以 s04 为准）。"""
import sys, json, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401

ROOT = Path(__file__).resolve().parents[6]
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm

TOL = 1e-6

def bbox(s):
    b = s.bounding_box()
    return (b.min.X, b.min.Y, b.min.Z, b.max.X, b.max.Y, b.max.Z)

def overlap(a, b):
    return not (a[3] < b[0] or b[3] < a[0] or a[4] < b[1] or b[4] < a[1] or a[5] < b[2] or b[5] < a[2])

def cv(a, b):
    try:
        c = a.intersect(b)
        return float(sum(s.volume for s in c.solids())) if c is not None else 0.0
    except Exception as e:
        return 'ERR:' + str(e)[:120]

def main():
    t0 = time.time()
    model, shapes, receipt = sm.build('service', include_arm=False)
    reps = {r['id']: r['representation_role'] for r in receipt['instances']}
    e2 = sorted(n for n in shapes if n.startswith(('e2_stub_', 'e2_washer_', 'e2_pin_')))
    others = {n: s for n, s in shapes.items() if reps.get(n) in ('PHYSICAL_GEOMETRY', 'SIMPLIFIED_PROXY') and n not in e2}
    bb = {n: bbox(s) for n, s in shapes.items()}
    hits = []
    import itertools
    pairs = [(a, b) for a in e2 for b in others if overlap(bb[a], bb[b])]
    pairs += [(a, b) for a, b in itertools.combinations(e2, 2) if overlap(bb[a], bb[b])]
    for a, b in pairs:
        v = cv(shapes[a], shapes[b])
        if isinstance(v, str) or v > TOL:
            hits.append((a, b, v))
    print('e2_parts', len(e2), 'instances', len(receipt['instances']), 'pairs_checked', len(pairs))
    print('hits', len(hits), 'elapsed_s', round(time.time() - t0, 2))
    for a, b, v in hits:
        print('HIT', a, 'vs', b, v)

if __name__ == '__main__':
    main()
