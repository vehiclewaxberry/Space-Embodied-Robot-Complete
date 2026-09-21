# -*- coding: utf-8 -*-
"""R07-E2 干涉检查（口径：布尔交集为权威，采样为对照 —— R01 教训：纯采样对环形承压区有盲区）。
范围：
  A) 28 E2 保持件 vs 全部 PHYSICAL_GEOMETRY + SIMPLIFIED_PROXY 实例（bbox 预筛 + 布尔 common 体积=0）
  B) 28 E2 保持件两两互查
  C) 具名零间隙/让隙检查（设计意图逐对声明；含 vs M4 端面螺钉、剪力板、翼根叉垫板、E1 锚固件、检修盖）
  D) 采样口径对照（E2 件内部点落入邻近实体计数；应为 0；盲区声明）
  E) 既有项登记（非 E2 引入，结转不静默）：
     E1) E1 登记的 2 对既有干涉（RB_upper_beam_160 vs shear_web_screw_±1_150_94）在当前构建复算 + 未改件对照；
     E2) 8 对端塞 vs M4 端面螺钉包络重叠 = WP02 螺纹啮合表示惯例（Ø4 栓入 Ø3.3 导孔；端塞/螺钉均未被 E2 修改）。
FUNCTIONAL_ENVELOPE 不作材料干涉判据，单列计数。
判定：A/B/C/D 无 >1e-6 mm3 且无错误 -> PASS；E 节只登记不从 PASS 剔除（本就不在 A/B 对集内）。"""
import sys, json, hashlib, time, itertools
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_IN

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e2_endplug_retention_20260918'
E1RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_root_longeron_anchoring_20260917'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm

TOL = 1e-6
E2PREFIX = ('e2_stub_', 'e2_washer_', 'e2_pin_')

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    rel = Path(p).resolve().relative_to(RUN).as_posix()
    wlf(str(p) + '.sha256', h + '  ' + rel + '\n')
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
        return float(sum(s.volume for s in c.solids())) if hasattr(c, 'solids') else 0.0
    except Exception as e:
        return {'error': str(e)[:200]}

def inside(solid, x, y, z):
    cls = BRepClass3d_SolidClassifier(solid.wrapped, gp_Pnt(x, y, z), 1e-9)
    return cls.State() == TopAbs_IN

def main():
    t0 = time.time()
    model, shapes, receipt = sm.build('service', include_arm=False)
    reps = {r['id']: r['representation_role'] for r in receipt['instances']}
    e2parts = sorted(n for n in shapes if n.startswith(E2PREFIX))
    checked_roles = ('PHYSICAL_GEOMETRY', 'SIMPLIFIED_PROXY')
    others = {n: s for n, s in shapes.items() if reps.get(n) in checked_roles and not n.startswith(E2PREFIX)}
    envelopes = [n for n in shapes if reps.get(n) == 'FUNCTIONAL_ENVELOPE']
    bb = {n: bbox(s) for n, s in shapes.items()}
    result = {'run': 'r07_e2_endplug_retention_20260918',
              'check': 'boolean_common_interference_with_sampling_comparison',
              'authoritative_method': 'BOOLEAN_COMMON_VOLUME (bbox prefilter)',
              'tolerance_mm3': TOL,
              'checked_roles': list(checked_roles),
              'functional_envelopes_excluded_count': len(envelopes),
              'e2_part_count': len(e2parts), 'other_count': len(others),
              'pairs': {'A_e2_vs_other': 0, 'B_e2_vs_e2': 0},
              'positives': [], 'errors': [], 'max_common_volume_mm3': 0.0,
              'explicit_clearance_checks': [], 'sampling_comparison': {},
              'registered_preexisting_carried_forward': [], 'registered_thread_engagement_convention': []}

    def run_pair(n1, s1, n2, s2, cat):
        v = common_volume(s1, s2)
        if isinstance(v, dict):
            result['errors'].append({'pair': [n1, n2], **v}); return
        result['pairs'][cat] += 1
        if v > result['max_common_volume_mm3']:
            result['max_common_volume_mm3'] = v
        if v > TOL:
            result['positives'].append({'pair': [n1, n2], 'common_volume_mm3': v})

    # A) E2 parts vs others
    for na in e2parts:
        sa = shapes[na]
        for no, so in others.items():
            if overlap(bb[na], bb[no]):
                run_pair(na, sa, no, so, 'A_e2_vs_other')
    # B) E2 pairwise
    for n1, n2 in itertools.combinations(e2parts, 2):
        if overlap(bb[n1], bb[n2]):
            run_pair(n1, shapes[n1], n2, shapes[n2], 'B_e2_vs_e2')

    # C) 具名零间隙/让隙检查
    spec = sm.transverse_retention_spec(sm.P)
    def named(a, b, pair_id, intent):
        v = common_volume(shapes[a], shapes[b])
        result['explicit_clearance_checks'].append({'pair_id': pair_id, 'a': a, 'b': b,
            'intent': intent, 'common_volume_mm3': None if isinstance(v, dict) else v,
            'pass': (not isinstance(v, dict)) and v <= TOL})
        if isinstance(v, dict):
            result['errors'].append({'pair': [a, b], **v})
        elif v > TOL:
            result['positives'].append({'pair': [a, b], 'common_volume_mm3': v, 'intent': intent})
    for r in spec:
        sid, sz = r['id'], r['sz']
        rail, plug, screw = r['longeron'], r['plug'], r['screw']
        wf = f"wing_root_fork_{r['sy']}_{r['sx']}"
        web = f"shear_web_{r['sy']}"
        bay_stub, bay_washer = f'e2_stub_bay_{sid}', f'e2_washer_bay_{sid}'
        named(bay_stub, rail, sid, '舱内短栓杆 vs 纵梁 Ø4.5 孔：零干涉')
        named(bay_stub, plug, sid, '舱内短栓杆 vs 端塞 Ø4.5 孔：零干涉')
        named(bay_stub, screw, sid, '舱内短栓尖 vs M4 端面螺钉包络：让隙 0.1 零干涉')
        named(bay_washer, web, sid, '舱侧垫圈 OD7 vs 剪力板：让隙 0.5 零干涉')
        if sz > 0:
            out_stub, out_washer = f'e2_stub_out_{sid}', f'e2_washer_out_{sid}'
            named(out_stub, rail, sid, '外短栓杆 vs 纵梁 Ø4.5 孔：零干涉')
            named(out_stub, plug, sid, '外短栓杆 vs 端塞 Ø4.5 孔：零干涉')
            named(out_stub, screw, sid, '外短栓尖 vs M4 端面螺钉包络：让隙 0.1 零干涉')
            named(out_washer, rail, sid, '外垫圈 vs 纵梁外顶面：贴面零体积')
        else:
            pin = f'e2_pin_wing_{sid}'
            named(pin, rail, sid, '翼侧无头销 vs 纵梁 Ø4.5 孔：零干涉')
            named(pin, plug, sid, '翼侧无头销 vs 端塞 Ø4.5 孔：零干涉')
            named(pin, screw, sid, '翼侧无头销顶 vs M4 端面螺钉包络：让隙 0.1 零干涉')
            named(pin, wf, sid, '翼侧无头销底 vs 翼根叉垫板：让隙 0.2 零干涉')
        # E2 vs 最近 E1 锚固件（x=154.85 站 G03/G04/G07/G08 及桥 G09/G10 栓）
        for e2n in [n for n in e2parts if n.endswith('_' + sid)]:
            for g in ['G03', 'G04', 'G07', 'G08', 'G09', 'G10']:
                for e1n in [n for n in shapes if n.startswith(f'e1_anchor_') and f'_{g}_' in n]:
                    if overlap(bb[e2n], bb[e1n]):
                        named(e2n, e1n, sid, 'E2 保持件 vs E1 锚固件（最近站）：零干涉')

    # D) 采样口径对照
    sampled_points = 0; inside_hits = []
    for na in e2parts:
        sa = shapes[na]; solids = sa.solids(); b = bb[na]
        neigh = [no for no in others if overlap(bb[na], bb[no])]
        n = 0; step = 0.4
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
                                inside_hits.append({'e2_part': na, 'neighbor': no, 'point_mm': [round(x, 3), round(y, 3), round(z, 3)]})
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

    # E1) 既有干涉结转（E1 run 登记的 2 对，当前构建复算 + 未改件对照）
    import root_structure as rs
    from build123d import Location as _Loc
    ctrl_beam = rs.plate(rs.R['upper_crossbeam_mm'], [(0, y, 6.6) for y in [-70, 70]] + [(0, y, 4.5) for y in [-94.15, 94.15]])
    ctrl_beam = ctrl_beam.moved(_Loc((160, 0, 101.15)))
    e1_reg = json.loads((E1RUN / 'evidence' / 'acc_interference_boolean.json').read_text(encoding='utf-8'))['registered_preexisting']
    for pre in e1_reg:
        a, b = pre['pair']
        v_now = common_volume(shapes[a], shapes[b])
        v_ctrl = common_volume(ctrl_beam, shapes[b])
        result['registered_preexisting_carried_forward'].append({
            'pair': [a, b], 'common_volume_mm3_now': v_now, 'control_common_volume_mm3': v_ctrl,
            'e1_registered_mm3': pre['common_volume_mm3'],
            'bit_identical_to_e1_registration': v_now == pre['common_volume_mm3'] and v_ctrl == pre['common_volume_mm3'],
            'status': 'PRE_EXISTING_NOT_INTRODUCED_BY_E1_OR_E2; 随父票 R07/WP02 lineage 上报跟踪（E1 审阅观察项 O5），不静默消失'})

    # E2) 端塞 vs M4 端面螺钉包络：WP02 螺纹啮合表示惯例（两者均未被 E2 修改）
    for r in spec:
        plug, screw = r['plug'], r['screw']
        v = common_volume(shapes[plug], shapes[screw])
        result['registered_thread_engagement_convention'].append({
            'pair': [plug, screw], 'common_volume_mm3': None if isinstance(v, dict) else v,
            'status': 'PRE_EXISTING_THREAD_ENGAGEMENT_CONVENTION (WP02: Ø4 螺钉包络入 Ø3.3 导孔=螺纹啮合表示)；端塞/螺钉均未被 E2 修改，非 E2 引入'})

    result['verdict'] = 'PASS' if not result['positives'] and not result['errors'] and not inside_hits else 'FAIL'
    if result['registered_preexisting_carried_forward'] or result['registered_thread_engagement_convention']:
        result['verdict_note'] = 'PASS 口径=无 E2 新增干涉；既有项见 registered_*（结转登记、不覆盖、不静默剔除）'
    result['elapsed_s'] = round(time.time() - t0, 3)
    f1 = RUN / 'evidence' / 'acc_interference_boolean.json'
    wlf(f1, json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    sidecar(f1)
    print('verdict', result['verdict'], 'pairs', result['pairs'], 'max_common', result['max_common_volume_mm3'],
          'positives', len(result['positives']), 'errors', len(result['errors']),
          'sampling hits', len(inside_hits), 'named', len(result['explicit_clearance_checks']),
          'carried', len(result['registered_preexisting_carried_forward']),
          'threadconv', len(result['registered_thread_engagement_convention']), 'elapsed_s', result['elapsed_s'])
    for p in result['positives'][:10]:
        print('POSITIVE', p)

if __name__ == '__main__':
    main()
