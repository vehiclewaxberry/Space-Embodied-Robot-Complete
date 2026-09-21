# -*- coding: utf-8 -*-
"""R07-E4 干涉检查（口径：布尔交集为权威，采样为对照 —— R01 教训）。
布尔口径：OCP BRepAlgoAPI_Common 原生 + BRepGProp.VolumeProperties_s（E2 审阅勘误 O2；
禁用 build123d Shape.intersect）。
范围：
  A) E4 检查集（4 夹套 + 4 改件后场螺钉）vs 全部 PHYSICAL_GEOMETRY + SIMPLIFIED_PROXY 实例
     （bbox 预筛 + common 体积=0；改件螺钉 vs 自有端塞=螺纹惯例对，转 E 节不计命中）
  B) E4 检查集两两互查
  C) 具名零间隙/让隙检查（套筒 vs 窗口、法兰贴面、栓杆 vs 套 ID/端框孔/窗口、头 vs 法兰、
     vs 肋/保留体积/E2 角区销/E1/E3 远场）
  D) 采样口径对照（E4 件内部点落入邻近实体计数；应为 0；盲区声明）
  E) 既有项结转（非 E4 引入，复算不静默）：
     E1) E1 登记的 2 对既有干涉当前构建复算 + 未改件对照 + 逐位核对；
     E2) 8 对端塞 vs M4 端面螺钉包络 = WP02 螺纹啮合表示惯例；后场 4 对螺钉已延长（头侧），
         端塞∩螺钉重叠区不变，复算应与 E3 登记逐位一致，差异如实登记。
FUNCTIONAL_ENVELOPE 不作材料干涉判据，单列计数（保留体积与角区径向间隙另登记）。
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
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e4_rear_bulkhead_20260918'
E1RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_root_longeron_anchoring_20260917'
E3RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r07_e3_retention_joints_20260918'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
sys.path.insert(0, str(ENG))
import spacecraft_model as sm

TOL = 1e-6
E4SET_PREFIX = ('e4_clamp_', 'RB_end_screw_-1_')

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
    e4parts = sorted(n for n in shapes if n.startswith(E4SET_PREFIX))
    checked_roles = ('PHYSICAL_GEOMETRY', 'SIMPLIFIED_PROXY')
    others = {n: s for n, s in shapes.items() if reps.get(n) in checked_roles and not n.startswith(E4SET_PREFIX)}
    envelopes = [n for n in shapes if reps.get(n) == 'FUNCTIONAL_ENVELOPE']
    bb = {n: bbox(s) for n, s in shapes.items()}
    result = {'run': 'r07_e4_rear_bulkhead_20260918',
              'check': 'boolean_common_interference_with_sampling_comparison',
              'authoritative_method': 'OCP BRepAlgoAPI_Common native + BRepGProp.VolumeProperties_s (E2 审阅勘误 O2 口径; 禁用 build123d Shape.intersect)',
              'tolerance_mm3': TOL,
              'checked_roles': list(checked_roles),
              'functional_envelopes_excluded_count': len(envelopes),
              'e4_part_count': len(e4parts), 'other_count': len(others),
              'thread_convention_pairs_routed_to_E': 4,
              'pairs': {'A_e4_vs_other': 0, 'B_e4_vs_e4': 0},
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

    # A) E4 set vs others（改件螺钉 vs 自有端塞转 E 节）
    for na in e4parts:
        sa = shapes[na]
        for no, so in others.items():
            if na.startswith('RB_end_screw_-1_') and no == na.replace('RB_end_screw_', 'RB_end_plug_'):
                continue
            if overlap(bb[na], bb[no]):
                run_pair(na, sa, no, so, 'A_e4_vs_other')
    # B) E4 pairwise
    for n1, n2 in itertools.combinations(e4parts, 2):
        if overlap(bb[n1], bb[n2]):
            run_pair(n1, shapes[n1], n2, shapes[n2], 'B_e4_vs_e4')

    # C) 具名零间隙/让隙检查
    spec = sm.rear_bulkhead_clamp_spec(sm.P)
    def named(a, b, pair_id, intent):
        if not overlap(bb[a], bb[b]):
            result['explicit_clearance_checks'].append({'pair_id': pair_id, 'a': a, 'b': b,
                'intent': intent, 'common_volume_mm3': 0.0, 'bbox': 'DISJOINT',
                'bbox_gap_mm': round(bbox_gap(bb[a], bb[b]), 3), 'pass': True})
            return
        v = common_volume(shapes[a], shapes[b])
        result['explicit_clearance_checks'].append({'pair_id': pair_id, 'a': a, 'b': b,
            'intent': intent, 'common_volume_mm3': None if isinstance(v, dict) else v,
            'pass': (not isinstance(v, dict)) and v <= TOL})
        if isinstance(v, dict):
            result['errors'].append({'pair': [a, b], **v})
        elif v > TOL:
            result['positives'].append({'pair': [a, b], 'common_volume_mm3': v, 'intent': intent})
    e2spec = sm.transverse_retention_spec(sm.P)
    def e2bay(sy, sz):
        for r2 in e2spec:
            if r2['x'] == -164 and r2['sy'] == sy and r2['sz'] == sz:
                return f"e2_stub_bay_{r2['id']}"
        return None
    for r in spec:
        pid = f"E4P-{r['group']}"
        sleeve = f"e4_clamp_sleeve_{r['group']}"
        screw = r['screw']
        named(sleeve, 'rear_launch_bulkhead', pid, '夹套筒 vs 隔框 Ø8 窗口（隙 0.05/边）+ 法兰 vs 外面（贴面）：零干涉')
        named(sleeve, screw, pid, '夹套 ID Ø4.5 vs M4×30 栓杆 Ø4（隙 0.25/边）+ 栓头 vs 法兰（贴面）：零干涉')
        named(sleeve, 'RB_end_frame_-1', pid, '夹套 vs 后端框：零干涉')
        named(screw, 'rear_launch_bulkhead', pid, 'M4×30 栓杆/头 vs Ø8 窗口：零干涉')
        named(screw, 'RB_end_frame_-1', pid, 'M4×30 栓杆 vs 端框 Ø4.5 孔：零干涉')
        named(screw, f"rear_vertical_rib_{'-' if r['sy']<0 else ''}86", pid, '改件螺钉 vs 纵肋（A/B 支承不动）：零干涉')
        named(screw, 'launch_interface_reserved_volume', pid, '改件螺钉头/法兰 vs 供应方保留体积（r60 不覆角区，FUNCTIONAL_ENVELOPE 仅登记间隙）：零入侵')
        named(sleeve, 'launch_interface_reserved_volume', pid, '夹套 vs 供应方保留体积：零入侵')
        e2n = e2bay(r['sy'], r['sz'])
        if e2n:
            named(screw, e2n, pid, '改件螺钉 vs E2 角区舱内短销（x=-164 站位，间隙 ~16.8）：零干涉')
    # C-远场) E4 vs E1/E3 最近件（按 bbox 间隙取最近 2 对）
    far = [n for n in shapes if n.startswith(('e1_anchor_', 'e3_clamp_', 'e3_foot_'))]
    cand = []
    for ne in e4parts:
        for n1 in far:
            cand.append((bbox_gap(bb[ne], bb[n1]), ne, n1))
    cand.sort(key=lambda t: t[0])
    for gap, ne, n1 in cand[:2]:
        named(ne, n1, 'E4_VS_E1E3_NEAREST', f'E4 vs E1/E3 最近件（bbox 间隙 {gap:.3f}mm）：零干涉')

    # D) 采样口径对照
    sampled_points = 0; inside_hits = []
    for na in e4parts:
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
                            if na.startswith('RB_end_screw_-1_') and no == na.replace('RB_end_screw_', 'RB_end_plug_'):
                                continue
                            if not overlap((x, y, z, x, y, z), bb[no]):
                                continue
                            if any(inside(s2, x, y, z) for s2 in others[no].solids()):
                                inside_hits.append({'e4_part': na, 'neighbor': no, 'point_mm': [round(x, 3), round(y, 3), round(z, 3)]})
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
            'method_note': 'E4 复算口径=OCP BRepAlgoAPI_Common 原生（E2 勘误 O2）；若与 E1 登记值末位差异属求积路径差异，如实登记不覆盖',
            'status': 'PRE_EXISTING_NOT_INTRODUCED_BY_E1/E2/E3/E4; 随父票 R07/WP02 lineage 上报跟踪（E1 审阅观察项 O5），不静默消失'})

    # E2) 端塞 vs M4 端面螺钉包络：WP02 螺纹啮合表示惯例（后场 4 件螺钉已被 E4 延长——头侧，重叠区不变；
    #     与 E3 run 登记值逐位核对，差异如实登记）
    e3_reg = {tuple(c['pair']): c['common_volume_mm3'] for c in
              json.loads((E3RUN / 'evidence' / 'acc_interference_boolean.json').read_text(encoding='utf-8'))['registered_thread_engagement_convention']}
    for r in sm.transverse_retention_spec(sm.P):
        plug, screw = r['plug'], r['screw']
        v = common_volume(shapes[plug], shapes[screw])
        key = (plug, screw)
        e3v = e3_reg.get(key)
        modified = screw.startswith('RB_end_screw_-1_')
        result['registered_thread_engagement_convention'].append({
            'pair': [plug, screw], 'common_volume_mm3': None if isinstance(v, dict) else v,
            'e3_registered_mm3': e3v,
            'bit_identical_to_e3_registration': (v == e3v) if e3v is not None else None,
            'screw_modified_by_e4': modified,
            'status': ('PRE_EXISTING_THREAD_ENGAGEMENT_CONVENTION; 螺钉经 E4 延长（头侧 x<-183），'
                       '端塞∩螺钉重叠区 x[-177,-161] 不变，复算应逐位一致' if modified else
                       'PRE_EXISTING_THREAD_ENGAGEMENT_CONVENTION (WP02: Ø4 螺钉包络入 Ø3.3 导孔=螺纹啮合表示)；端塞/螺钉均未被 E4 修改')})

    result['verdict'] = 'PASS' if not result['positives'] and not result['errors'] and not inside_hits else 'FAIL'
    if result['registered_preexisting_carried_forward'] or result['registered_thread_engagement_convention']:
        result['verdict_note'] = 'PASS 口径=无 E4 新增干涉；既有项见 registered_*（结转登记、不覆盖、不静默剔除）'
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
