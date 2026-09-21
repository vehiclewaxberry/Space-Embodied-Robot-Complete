# -*- coding: utf-8 -*-
"""R07-E3 干涉检查（口径：布尔交集为权威，采样为对照 —— R01 教训）。
布尔口径：OCP BRepAlgoAPI_Common 原生 + BRepGProp.VolumeProperties_s（E2 审阅勘误 O2；
禁用 build123d Shape.intersect）。
范围：
  A) 24 E3 保持件 vs 全部 PHYSICAL_GEOMETRY + SIMPLIFIED_PROXY 实例（bbox 预筛 + common 体积=0）
  B) 24 E3 保持件两两互查（含边1 J** vs 边2 C** —— v2 互避闭环项）
  C) 具名零间隙/让隙检查（栓杆 vs 各对偶孔、头/垫贴面、耳座/轮毂/枢轴销/剪力板/检修盖邻域、
     E3 vs E1 最近锚固件、FAIL v1 四对闭环复算）
  D) 采样口径对照（E3 件内部点落入邻近实体计数；应为 0；盲区声明）
  E) 既有项结转（非 E3 引入，复算不静默）：
     E1) E1 登记的 2 对既有干涉（RB_upper_beam_160 vs shear_web_screw_±1_150_94）当前构建复算
         + 未改件对照 + 与 E1 登记值逐位核对（方法差异如实登记）；
     E2) 8 对端塞 vs M4 端面螺钉包络 = WP02 螺纹啮合表示惯例（Ø4 栓入 Ø3.3 导孔）。
FUNCTIONAL_ENVELOPE 不作材料干涉判据，单列计数。
判定：A/B/C/D 无 >1e-6 mm3 且无错误 -> PASS；E 节只登记不从 PASS 剔除。"""
import sys, json, hashlib, time, itertools
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.GProp import GProp_GProps
from OCP.BRepGProp import BRepGProp
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_IN

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e3_retention_joints_20260918'
E1RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_root_longeron_anchoring_20260917'
E2RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e2_endplug_retention_20260918'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm

TOL = 1e-6
E3PREFIX = ('e3_clamp_', 'e3_foot_')

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    rel = Path(p).resolve().relative_to(RUN).as_posix()
    wlf(str(p) + '.sha256', h + '  ' + rel + '\n')
    return h

def volume_of(shape):
    g = GProp_GProps(); BRepGProp.VolumeProperties_s(shape, g)
    return g.Mass()

def bbox(s):
    b = s.bounding_box()
    return (b.min.X, b.min.Y, b.min.Z, b.max.X, b.max.Y, b.max.Z)

def overlap(a, b, margin=0.0):
    return not (a[3] < b[0] - margin or b[3] < a[0] - margin or
                a[4] < b[1] - margin or b[4] < a[1] - margin or
                a[5] < b[2] - margin or b[5] < a[2] - margin)

def bbox_gap(a, b):
    def g(alo, ahi, blo, bhi):
        return max(blo - ahi, alo - bhi, 0.0)
    return (g(a[0], a[3], b[0], b[3])**2 + g(a[1], a[4], b[1], b[4])**2 + g(a[2], a[5], b[2], b[5])**2) ** 0.5

def common_volume(a, b):
    try:
        op = BRepAlgoAPI_Common(a.wrapped, b.wrapped)
        op.Build()
        if not op.IsDone():
            return {'error': 'BRepAlgoAPI_Common not done'}
        return float(volume_of(op.Shape()))
    except Exception as e:
        return {'error': str(e)[:200]}

def inside(solid, x, y, z):
    cls = BRepClass3d_SolidClassifier(solid.wrapped, gp_Pnt(x, y, z), 1e-9)
    return cls.State() == TopAbs_IN

def main():
    t0 = time.time()
    model, shapes, receipt = sm.build('service', include_arm=False)
    reps = {r['id']: r['representation_role'] for r in receipt['instances']}
    e3parts = sorted(n for n in shapes if n.startswith(E3PREFIX))
    checked_roles = ('PHYSICAL_GEOMETRY', 'SIMPLIFIED_PROXY')
    others = {n: s for n, s in shapes.items() if reps.get(n) in checked_roles and not n.startswith(E3PREFIX)}
    envelopes = [n for n in shapes if reps.get(n) == 'FUNCTIONAL_ENVELOPE']
    bb = {n: bbox(s) for n, s in shapes.items()}
    result = {'run': 'r07_e3_retention_joints_20260918',
              'check': 'boolean_common_interference_with_sampling_comparison',
              'authoritative_method': 'OCP BRepAlgoAPI_Common native + BRepGProp.VolumeProperties_s (E2 审阅勘误 O2 口径; 禁用 build123d Shape.intersect)',
              'tolerance_mm3': TOL,
              'checked_roles': list(checked_roles),
              'functional_envelopes_excluded_count': len(envelopes),
              'e3_part_count': len(e3parts), 'other_count': len(others),
              'pairs': {'A_e3_vs_other': 0, 'B_e3_vs_e3': 0},
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

    # A) E3 parts vs others
    for na in e3parts:
        sa = shapes[na]
        for no, so in others.items():
            if overlap(bb[na], bb[no]):
                run_pair(na, sa, no, so, 'A_e3_vs_other')
    # B) E3 pairwise
    for n1, n2 in itertools.combinations(e3parts, 2):
        if overlap(bb[n1], bb[n2]):
            run_pair(n1, shapes[n1], n2, shapes[n2], 'B_e3_vs_e3')

    # C) 具名零间隙/让隙检查
    spec1 = sm.retention_clamp_spec(sm.P)
    spec2 = sm.retention_foot_spec(sm.P)
    def named(a, b, pair_id, intent):
        if not overlap(bb[a], bb[b]):
            result['explicit_clearance_checks'].append({'pair_id': pair_id, 'a': a, 'b': b,
                'intent': intent, 'common_volume_mm3': 0.0, 'bbox': 'DISJOINT', 'pass': True})
            return
        v = common_volume(shapes[a], shapes[b])
        result['explicit_clearance_checks'].append({'pair_id': pair_id, 'a': a, 'b': b,
            'intent': intent, 'common_volume_mm3': None if isinstance(v, dict) else v,
            'pass': (not isinstance(v, dict)) and v <= TOL})
        if isinstance(v, dict):
            result['errors'].append({'pair': [a, b], **v})
        elif v > TOL:
            result['positives'].append({'pair': [a, b], 'common_volume_mm3': v, 'intent': intent})
    for r in spec1:
        pid = f"E3P-{r['group']}-{r['index']}"
        bolt = f"e3_clamp_bolt_{r['group']}_{r['index']}"
        washer = f"e3_clamp_washer_{r['group']}_{r['index']}"
        lug_near = f"hold_roof_lug_{r['k']}_{r['sy']*94.15}"
        named(bolt, r['mate'], pid, '边1 栓杆 vs 纵梁双壁 Ø3.4 贯穿孔：零干涉')
        named(bolt, r['beam'], pid, '边1 栓杆 vs 横梁端面盲孔(Ø3.4深7,贯入5)：零干涉')
        named(washer, r['mate'], pid, '边1 垫圈 vs 纵梁外腹面：贴面零体积')
        named(bolt, lug_near, pid, '边1 栓/头 vs 耳座(z>=106.15 占位)：零干涉')
        named(washer, lug_near, pid, '边1 垫圈 vs 耳座：零干涉')
    for r in spec2:
        pid = f"E3P-{r['group']}-{r['index']}"
        bolt = f"e3_foot_bolt_{r['group']}_{r['index']}"
        washer = f"e3_foot_washer_{r['group']}_{r['index']}"
        named(bolt, r['beam'], pid, '边2 栓杆 vs 横梁 Ø4.5 竖孔：零干涉')
        named(bolt, r['lug'], pid, '边2 栓杆 vs 耳座 Ø4.5 竖孔：零干涉')
        named(bolt, r['foot'], pid, '边2 栓杆 vs 脚座盲孔(打通至槽底,啮合5)：零干涉')
        named(washer, r['beam'], pid, '边2 垫圈 vs 横梁底面：贴面零体积')
        named(bolt, f"hold_fold_mast_{r['k']}", pid, '边2 栓 vs 轮毂 r10 干涉域(z>=125.15)：零凸出零干涉')
        named(bolt, f"hold_pivot_pin_{r['k']}", pid, '边2 栓 vs 枢轴销(z[131.15,139.15])：零干涉')
        named(bolt, f"shear_web_{-1}", pid, '边2 栓 vs 剪力板：零干涉')
        named(washer, f"access_cover_{-1}", pid, '边2 垫圈/头 vs 检修盖：零干涉')
    # C-v2) FAIL v1 四对闭环复算（互避后应为 0）
    for cb, fb in [('e3_clamp_bolt_J02_0', 'e3_foot_bolt_C01_0'), ('e3_clamp_bolt_J02_1', 'e3_foot_bolt_C01_1'),
                   ('e3_clamp_bolt_J04_0', 'e3_foot_bolt_C02_0'), ('e3_clamp_bolt_J04_1', 'e3_foot_bolt_C02_1')]:
        named(cb, fb, 'V2_CLOSURE', 'FAIL v1 相贯对(16.37mm3) 互避闭环：栓杆-栓杆 y 净距 3.5 零干涉')
    # C-E1) E3 vs 最近 E1 锚固件（按 bbox 间隙取最近 4 对）
    e1names = [n for n in shapes if n.startswith('e1_anchor_')]
    cand = []
    for ne in e3parts:
        for n1 in e1names:
            cand.append((bbox_gap(bb[ne], bb[n1]), ne, n1))
    cand.sort(key=lambda t: t[0])
    for gap, ne, n1 in cand[:4]:
        named(ne, n1, 'E3_VS_E1_NEAREST', f'E3 vs E1 最近锚固件（bbox 间隙 {gap:.3f}mm；x/z 无交叠登记）：零干涉')

    # D) 采样口径对照
    sampled_points = 0; inside_hits = []
    for na in e3parts:
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
                                inside_hits.append({'e3_part': na, 'neighbor': no, 'point_mm': [round(x, 3), round(y, 3), round(z, 3)]})
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

    # E1) 既有干涉结转（E1 run 登记的 2 对，当前构建复算 + 未改件对照 + 逐位核对）
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
            'method_note': 'E3 复算口径=OCP BRepAlgoAPI_Common 原生（E2 勘误 O2）；若与 E1 登记值末位差异属求积路径差异，如实登记不覆盖',
            'status': 'PRE_EXISTING_NOT_INTRODUCED_BY_E1/E2/E3; 随父票 R07/WP02 lineage 上报跟踪（E1 审阅观察项 O5），不静默消失'})

    # E2) 端塞 vs M4 端面螺钉包络：WP02 螺纹啮合表示惯例（两者均未被 E3 修改）
    for r in sm.transverse_retention_spec(sm.P):
        plug, screw = r['plug'], r['screw']
        v = common_volume(shapes[plug], shapes[screw])
        result['registered_thread_engagement_convention'].append({
            'pair': [plug, screw], 'common_volume_mm3': None if isinstance(v, dict) else v,
            'status': 'PRE_EXISTING_THREAD_ENGAGEMENT_CONVENTION (WP02: Ø4 螺钉包络入 Ø3.3 导孔=螺纹啮合表示)；端塞/螺钉均未被 E3 修改，非 E3 引入'})

    result['verdict'] = 'PASS' if not result['positives'] and not result['errors'] and not inside_hits else 'FAIL'
    if result['registered_preexisting_carried_forward'] or result['registered_thread_engagement_convention']:
        result['verdict_note'] = 'PASS 口径=无 E3 新增干涉；既有项见 registered_*（结转登记、不覆盖、不静默剔除）'
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
