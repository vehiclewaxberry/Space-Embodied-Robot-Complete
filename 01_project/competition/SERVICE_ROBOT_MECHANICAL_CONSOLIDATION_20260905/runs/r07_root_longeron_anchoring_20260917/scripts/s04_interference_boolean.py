# -*- coding: utf-8 -*-
"""R07-E1 干涉检查（口径：布尔交集为权威，采样为对照 —— R01 教训：纯采样对环形承压区有盲区）。
范围：
  A) 48 锚固件 vs 全部 PHYSICAL_GEOMETRY + SIMPLIFIED_PROXY 实例（bbox 预筛 + 布尔 common 体积=0）
  B) 48 锚固件两两互查
  C) 9 受影响构件（含新对偶孔）vs 全部物理/代理实例
  D) 采样口径对照：锚固件内部采样点落入邻近实体计数（应为 0；盲区声明）
FUNCTIONAL_ENVELOPE 不作材料干涉判据，单列计数。
判定：所有布尔 common 体积 <= 1e-6 mm^3 -> PASS，否则 FAIL 列出。"""
import sys, json, hashlib, time, itertools
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_IN

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_root_longeron_anchoring_20260917'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm

MEMBERS = ['RB_longeron_1_1', 'RB_longeron_-1_1', 'RB_longeron_1_-1', 'RB_longeron_-1_-1',
           'RB_upper_beam_20', 'RB_upper_beam_160', 'RB_lower_beam_20', 'RB_lower_beam_160',
           'WP01-RB-BRIDGE-R2']
TOL = 1e-6

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    wlf(str(p) + '.sha256', h + '  ' + Path(p).name + '\n')
    return h

def bbox(s):
    b = s.bounding_box()
    return (b.min.X, b.min.Y, b.min.Z, b.max.X, b.max.Y, b.max.Z)

def overlap(a, b, margin=0.0):
    return not (a[3] < b[0] - margin or b[3] < a[0] - margin or
                a[4] < b[1] - margin or b[4] < a[1] - margin or
                a[5] < b[2] - margin or b[5] < a[2] - margin)

def common_volume(a, b):
    try:
        c = a.intersect(b)
        if c is None:
            return 0.0
        v = sum(s.volume for s in c.solids()) if hasattr(c, 'solids') else 0.0
        return float(v)
    except Exception as e:
        return {'error': str(e)[:200]}

def inside(solid, x, y, z):
    cls = BRepClass3d_SolidClassifier(solid.wrapped, gp_Pnt(x, y, z), 1e-9)
    return cls.State() == TopAbs_IN

def main():
    t0 = time.time()
    model, shapes, receipt = sm.build('service', include_arm=False)
    reps = {r['id']: r['representation_role'] for r in receipt['instances']}
    anchors = sorted(n for n in shapes if n.startswith('e1_anchor_'))
    checked_roles = ('PHYSICAL_GEOMETRY', 'SIMPLIFIED_PROXY')
    others = {n: s for n, s in shapes.items() if reps.get(n) in checked_roles and not n.startswith('e1_anchor_')}
    envelopes = [n for n in shapes if reps.get(n) == 'FUNCTIONAL_ENVELOPE']
    bb = {n: bbox(s) for n, s in shapes.items()}
    result = {'run': 'r07_root_longeron_anchoring_20260917',
              'check': 'boolean_common_interference_with_sampling_comparison',
              'authoritative_method': 'BOOLEAN_COMMON_VOLUME (bbox prefilter)',
              'tolerance_mm3': TOL,
              'checked_roles': list(checked_roles),
              'functional_envelopes_excluded_count': len(envelopes),
              'anchor_count': len(anchors), 'other_count': len(others),
              'pairs': {'A_anchor_vs_other': 0, 'B_anchor_vs_anchor': 0, 'C_member_vs_other': 0},
              'positives': [], 'errors': [], 'max_common_volume_mm3': 0.0,
              'explicit_clearance_checks': [], 'sampling_comparison': {}}

    def run_pair(n1, s1, n2, s2, cat):
        v = common_volume(s1, s2)
        if isinstance(v, dict):
            result['errors'].append({'pair': [n1, n2], **v}); return
        result['pairs'][cat] += 1
        if v > result['max_common_volume_mm3']:
            result['max_common_volume_mm3'] = v
        if v > TOL:
            result['positives'].append({'pair': [n1, n2], 'common_volume_mm3': v})

    # A) anchors vs others
    for na in anchors:
        sa = shapes[na]
        for no, so in others.items():
            if overlap(bb[na], bb[no]):
                run_pair(na, sa, no, so, 'A_anchor_vs_other')
    # B) anchor vs anchor
    for n1, n2 in itertools.combinations(anchors, 2):
        if overlap(bb[n1], bb[n2]):
            run_pair(n1, shapes[n1], n2, shapes[n2], 'B_anchor_vs_anchor')
    # C) members vs others (excluding anchors already covered in A)
    for nm in MEMBERS:
        sm_ = shapes[nm]
        for no, so in others.items():
            if no == nm:
                continue
            if overlap(bb[nm], bb[no]):
                run_pair(nm, sm_, no, so, 'C_member_vs_other')

    # 具名零间隙检查（设计意图：栓-套-孔零干涉）
    spec = sm.root_anchoring_spec(sm.P)
    for r in spec:
        gid, j = r['group'], r['index']
        bn, wn, sn = f'e1_anchor_bolt_{gid}_{j}', f'e1_anchor_washer_{gid}_{j}', f'e1_anchor_sleeve_{gid}_{j}'
        beam = 'WP01-RB-BRIDGE-R2' if r['member'] == 'bridge' else f"RB_{r['member']}_{r['beam_x']}"
        rail = f"RB_longeron_{r['sy']}_{r['sz']}"
        plug = f"RB_end_plug_1_{r['sy']}_{r['sz']}"
        for a, b, intent in [(bn, rail, '栓杆 vs 纵梁 Ø3.4 孔：零干涉'),
                             (bn, beam, '栓杆 vs 端面盲孔：零干涉(threadless 包络)'),
                             (bn, sn, '栓杆 Ø3 vs 套 ID3.4：零干涉'),
                             (sn, rail, '防压套 vs 纵梁管内腔：零干涉'),
                             (sn, plug, '防压套 vs 端塞(x>=157)：零干涉(154.85 站关键)'),
                             (wn, rail, '垫圈 vs 纵梁外腹面：贴面零体积')]:
            v = common_volume(shapes[a], shapes[b])
            result['explicit_clearance_checks'].append({'pair_id': f'E1P-{gid}-{j}', 'a': a, 'b': b,
                'intent': intent, 'common_volume_mm3': None if isinstance(v, dict) else v,
                'pass': (not isinstance(v, dict)) and v <= TOL})
            if isinstance(v, dict):
                result['errors'].append({'pair': [a, b], **v})
            elif v > TOL:
                result['positives'].append({'pair': [a, b], 'common_volume_mm3': v, 'intent': intent})

    # D) 采样口径对照：锚固件内点 vs 邻近实体
    sampled_points = 0; inside_hits = []
    for na in anchors:
        sa = shapes[na]
        solids = sa.solids()
        b = bb[na]
        neigh = [no for no in others if overlap(bb[na], bb[no], margin=0.0)]
        n = 0
        step = 0.4
        x = b[0] + step / 2
        while x < b[3]:
            y = b[1] + step / 2
            while y < b[4]:
                z = b[2] + step / 2
                while z < b[5]:
                    if any(inside(s, x, y, z) for s in solids):
                        n += 1
                        for no in neigh:
                            if not overlap((x, y, z, x, y, z), bb[no]):
                                continue
                            if any(inside(s2, x, y, z) for s2 in others[no].solids()):
                                inside_hits.append({'anchor': na, 'neighbor': no, 'point_mm': [round(x, 3), round(y, 3), round(z, 3)]})
                                break
                    z += step
                y += step
            x += step
        sampled_points += n
    result['sampling_comparison'] = {
        'method': 'grid 0.4 mm interior point sampling, BRepClass3d classification',
        'sampled_interior_points': sampled_points,
        'points_inside_neighbor': len(inside_hits),
        'hits': inside_hits[:50],
        'blind_spot_declaration': '采样口径对薄壁/环形承压区存在盲区（R01 教训）；本 run 以布尔交集为权威口径，采样仅作对照',
    }
    result['verdict'] = 'PASS' if not result['positives'] and not result['errors'] and not inside_hits else 'FAIL'
    # 既有（非 E1 引入）相邻对登记：以未改件（WP02 原始定义、无 E1 孔）对照复算，
    # 公共体积逐位一致方可列入；列入者从 E1 新增干涉裁决中剔除，但作为负结果登记上报。
    result['registered_preexisting'] = []
    import root_structure as rs
    ctrl_beam = rs.plate(rs.R['upper_crossbeam_mm'], [(0, y, 6.6) for y in [-70, 70]] + [(0, y, 4.5) for y in [-94.15, 94.15]])
    from build123d import Location as _Loc
    ctrl_beam = ctrl_beam.moved(_Loc((160, 0, 101.15)))
    PRE = [('RB_upper_beam_160', 'shear_web_screw_1_150_94', ctrl_beam),
           ('RB_upper_beam_160', 'shear_web_screw_-1_150_94', ctrl_beam)]
    remaining = []
    for p in result['positives']:
        pair = tuple(p['pair'])
        hit = next((c for c in PRE if tuple(c[:2]) == pair), None)
        if hit is not None:
            cv = common_volume(hit[2], shapes[pair[1]])
            p2 = dict(p); p2['control'] = 'UNMODIFIED_WP02_BEAM_COMMON_VOLUME'
            p2['control_common_volume_mm3'] = cv
            p2['bit_identical_to_e1_build'] = (cv == p['common_volume_mm3'])
            p2['status'] = 'PRE_EXISTING_NOT_INTRODUCED_BY_E1; 先行存在（WP02 横梁端角 vs 既有剪力板栓包络 z 95.15..95.5 掠入 0.461 mm3）；E1 孔不涉及该角；登记上报父票，不在 E1 处置'
            result['registered_preexisting'].append(p2)
            if cv != p['common_volume_mm3']:
                remaining.append(p)  # 对照不一致则不得剔除
        else:
            remaining.append(p)
    result['positives'] = remaining
    result['verdict'] = 'PASS' if not result['positives'] and not result['errors'] and not inside_hits else 'FAIL'
    if result['registered_preexisting']:
        result['verdict_note'] = 'PASS 口径=无 E1 新增干涉；既有相邻对见 registered_preexisting（不覆盖、不静默剔除）'
    result['elapsed_s'] = round(time.time() - t0, 3)
    f1 = RUN / 'evidence' / 'acc_interference_boolean.json'
    wlf(f1, json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    sidecar(f1)
    print('verdict', result['verdict'], 'pairs', result['pairs'], 'max_common', result['max_common_volume_mm3'],
          'positives', len(result['positives']), 'errors', len(result['errors']),
          'sampling hits', len(inside_hits), 'elapsed_s', result['elapsed_s'])
    for p in result['positives'][:10]:
        print('POSITIVE', p)

if __name__ == '__main__':
    main()
