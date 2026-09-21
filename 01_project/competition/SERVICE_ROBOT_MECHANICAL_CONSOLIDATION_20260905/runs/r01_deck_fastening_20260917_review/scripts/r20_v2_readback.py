# -*- coding: utf-8 -*-
"""WP03 R01 候选 V2 验收6 独立复验 - 任务1：V2 独立读回。

只读 run exports/（V2 已就地覆盖，V1 物证在 exports/v1_superseded/），不修改候选。
注意：STEP 文件头含写出时间戳，字节 sha256 不作同一性判据；结构一致性不靠指纹沿用，
而是在 V2 导出上直接重跑全部结构验证（闭孔/同轴/避口壁/包络完整性）。

  A) EXPORT_MANIFEST_V2 记录哈希完整性（清单自洽）；
  B) 结构重验证：16 闭孔（位置/完整度/72 环点/轴心判空/旧孔系残余）、32 组同轴、避口 12 壁；
  C) 全部 32 件紧固件包络 vs 被夹持结构件布尔交集体积（应全 0；重点 16 件腹板件 vs 剪力腹板）；
  D) 承压面到杆尖读回测量：腹板件=10.0mm、甲板件=12.0mm（V1 反例 9.5mm 应闭环）；
  E) 包络完整性（杆 R1.5/头 R2.75/OD6>=2 面、垫圈 OD<=6 限值）；
  F) V2 vs V1（v1_superseded 物证）腹板件包络体积差 = π*1.5^2*0.5 = 3.534292 mm3。
"""
import sys, json, math, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401  必须先于 build123d（系统坏字体守卫）
from cadgen.step_scene import import_step
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
from OCP.BRepTools import BRepTools
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_IN

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917'
REVIEW = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917_review'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
EXP = RUN / 'exports'
V1 = EXP / 'v1_superseded'

P = json.loads((ENG / 'design_parameters.json').read_text(encoding='utf-8'))
R01 = P['deck_fastening_r01']
DPAT = R01['deck_hole_pattern']; WPAT = R01['angle_to_shear_web_hole_pattern']
DECKS = {'lower': -99.65, 'upper': -10}
SEGMENTS = [(-167, 11.5), (28.5, 151.5)]
TOL_AXIS = 0.05
TOL_COAX = 1e-3

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    wlf(str(p) + '.sha256', h + '  ' + Path(p).name + '\n')
    return h

def sha256_of(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def common_volume(a, b):
    c = a & b
    return 0.0 if c is None else c.volume

def cyl_faces(shape):
    out = []
    for f in shape.faces():
        ad = BRepAdaptor_Surface(f.wrapped)
        if ad.GetType() != GeomAbs_Cylinder:
            continue
        cyl = ad.Cylinder(); ax = cyl.Axis()
        umin, umax, vmin, vmax = BRepTools.UVBounds_s(f.wrapped)
        loc = ax.Location(); d = ax.Direction()
        out.append({'r': cyl.Radius(), 'p': (loc.X(), loc.Y(), loc.Z()),
                    'd': (d.X(), d.Y(), d.Z()), 'fullness': (umax - umin) / (2 * math.pi)})
    return out

def plane_faces(shape):
    out = []
    for f in shape.faces():
        ad = BRepAdaptor_Surface(f.wrapped)
        if ad.GetType() == GeomAbs_Plane:
            pl = ad.Plane(); n = pl.Axis().Direction(); l = pl.Location()
            out.append({'n': (n.X(), n.Y(), n.Z()), 'p': (l.X(), l.Y(), l.Z())})
    return out

def inside(shape, x, y, z):
    return BRepClass3d_SolidClassifier(shape.wrapped, gp_Pnt(x, y, z), 1e-9).State() == TopAbs_IN

def closed_hole(solid, x, y, zmid, hole_r=1.7, n=72):
    axis_void = not inside(solid, x, y, zmid)
    out_pts = 0
    for i in range(n):
        a = 2 * math.pi * i / n
        if not inside(solid, x + (hole_r + 0.05) * math.cos(a), y + (hole_r + 0.05) * math.sin(a), zmid):
            out_pts += 1
    return axis_void and out_pts == 0

def head_bearing_to_tip(shape, axis_idx, side_sign=1):
    head = None
    for f in shape.faces():
        ad = BRepAdaptor_Surface(f.wrapped)
        if ad.GetType() == GeomAbs_Cylinder and abs(ad.Cylinder().Radius() - 2.75) < 0.02:
            head = f
            break
    if head is None:
        return None
    hb = head.bounding_box(); sb = shape.bounding_box()
    if axis_idx == 2:
        head_far, tip = hb.max.Z, sb.min.Z
    else:
        head_far = hb.max.Y if side_sign > 0 else -hb.min.Y
        tip = sb.min.Y if side_sign > 0 else -sb.max.Y
    return (head_far - 3.0 - 0.5) - tip

def main():
    t0 = time.time()
    rep = {'review': 'r01_deck_fastening_20260917_review', 'candidate_version': 'V2',
           'check': 'ACC6_V2_T1_independent_readback',
           'reviewer': 'WP03 R01 独立审阅者（只读，未修改候选，未执行 git 提交）',
           'reviewed_builder_commit': '4c184e0e',
           'readback_tool': 'cadgen.step_scene.import_step (OCP), 自写脚本 scripts/r20_v2_readback.py',
           'note': 'STEP 文件头含写出时间戳，字节 sha256 不作同一性判据；结构要求直接在 V2 导出上重验',
           'units': 'mm', 'frame': 'S', 'failures': []}

    # A) 清单哈希完整性
    m2 = json.loads((EXP / 'EXPORT_MANIFEST_V2.json').read_text(encoding='utf-8'))
    bad = [p['file'] for p in m2['parts'] if sha256_of(EXP / p['file']) != p['sha256']]
    rep['manifest_v2'] = {'files': len(m2['parts']), 'sha256_all_match': not bad, 'mismatch': bad,
                          'manifest_sha256': sha256_of(EXP / 'EXPORT_MANIFEST_V2.json')}
    if bad:
        rep['failures'].append(f'EXPORT_MANIFEST_V2 哈希不一致: {bad}')
    shapes = {p['name']: import_step(str(EXP / p['file'])) for p in m2['parts']}
    struct_names = [n for n in shapes if n.endswith('equipment_deck') or '_deck_angle_' in n or n.startswith('shear_web')]
    struct = {n: shapes[n] for n in struct_names}

    # B) 结构重验证：闭孔 + 旧孔系残余 + 避口壁 + 同轴
    hole_r = DPAT['diameter_mm'] / 2
    total_closed = 0
    deck_info = {}
    for deck, z in DECKS.items():
        s = shapes[f'{deck}_equipment_deck']
        cf = [c for c in cyl_faces(s) if abs(c['r'] - hole_r) < 0.02 and abs(abs(c['d'][2]) - 1) < 1e-6]
        n_closed = 0
        for x in DPAT['X_S_mm']:
            for y in DPAT['Y_S_mm']:
                cand = [c for c in cf if abs(c['p'][0] - x) < TOL_AXIS and abs(c['p'][1] - y) < TOL_AXIS]
                full = max((c['fullness'] for c in cand), default=0)
                ok = bool(cand) and full > 0.999 and closed_hole(s, x, y, z)
                n_closed += ok
                if not ok:
                    rep['failures'].append(f'V2 {deck} 孔({x},{y}) 闭孔验证失败')
        resid = sum(1 for oy in (-89, 89)
                    for c in cf if abs(c['p'][0] - 150) < TOL_AXIS and abs(c['p'][1] - oy) < TOL_AXIS)
        walls = [p for p in plane_faces(s)
                 if (abs(abs(p['n'][0]) - 1) < 1e-6 and any(abs(p['p'][0] - v) < 0.01 for v in (11.5, 28.5, 151.5, 168.5))) or
                    (abs(abs(p['n'][1]) - 1) < 1e-6 and abs(abs(p['p'][1]) - 85.65) < 0.01)]
        deck_info[deck] = {'closed_holes': n_closed, 'cyl_hole_faces': len(cf),
                           'old_pattern_residual_faces': resid, 'column_notch_wall_faces': len(walls)}
        if n_closed != 8 or resid != 0 or len(walls) != 12:
            rep['failures'].append(f'V2 {deck}: closed={n_closed} resid={resid} walls={len(walls)}')
        total_closed += n_closed
    rep['structural_reverify'] = {'decks': deck_info, 'total_closed_holes': total_closed}

    coax_da = 0; coax_aw = 0; dev_max = 0.0
    for deck, z in DECKS.items():
        ds = shapes[f'{deck}_equipment_deck']
        deck_axes = [(c['p'][0], c['p'][1]) for c in cyl_faces(ds)
                     if abs(c['r'] - hole_r) < 0.02 and abs(abs(c['d'][2]) - 1) < 1e-6]
        for side in (-1, 1):
            web_axes = [(c['p'][0], c['p'][2]) for c in cyl_faces(shapes[f'shear_web_{side}'])
                        if abs(c['r'] - hole_r) < 0.02 and abs(abs(c['d'][1]) - 1) < 1e-6]
            for k, (a, b) in enumerate(SEGMENTS):
                acf = cyl_faces(shapes[f'{deck}_deck_angle_{side}_{k}'])
                a_hz = [(c['p'][0], c['p'][1]) for c in acf
                        if abs(c['r'] - hole_r) < 0.02 and abs(abs(c['d'][2]) - 1) < 1e-6]
                a_vy = [(c['p'][0], c['p'][2]) for c in acf
                        if abs(c['r'] - hole_r) < 0.02 and abs(abs(c['d'][1]) - 1) < 1e-6]
                for x in [x for x in DPAT['X_S_mm'] if a - 1e-9 <= x <= b + 1e-9]:
                    ey = side * 92.65
                    da = min(deck_axes, key=lambda ax: math.hypot(ax[0] - x, ax[1] - ey))
                    aa = min(a_hz, key=lambda ax: math.hypot(ax[0] - da[0], ax[1] - da[1])) if a_hz else None
                    dev = math.hypot(aa[0] - da[0], aa[1] - da[1]) if aa else 1e9
                    dev_max = max(dev_max, dev)
                    coax_da += dev < TOL_COAX
                    if dev >= TOL_COAX:
                        rep['failures'].append(f'V2 同轴 deck-angle {deck} {side} {k} x={x}: dev={dev}')
                wz = WPAT['Z_S_mm_by_deck'][deck]
                for x in WPAT['X_S_mm_by_segment'][k]:
                    wa = min(web_axes, key=lambda ax: math.hypot(ax[0] - x, ax[1] - wz))
                    aa = min(a_vy, key=lambda ax: math.hypot(ax[0] - wa[0], ax[1] - wa[1])) if a_vy else None
                    dev = math.hypot(aa[0] - wa[0], aa[1] - wa[1]) if aa else 1e9
                    dev_max = max(dev_max, dev)
                    coax_aw += dev < TOL_COAX
                    if dev >= TOL_COAX:
                        rep['failures'].append(f'V2 同轴 angle-web {deck} {side} {k} x={x}: dev={dev}')
    rep['structural_reverify']['coaxial'] = {'deck_angle_ok': coax_da, 'angle_web_ok': coax_aw,
                                             'deviation_max_mm': dev_max}

    # C) 布尔交集体积（全部 32 件 vs 被夹持结构件）
    commons = []
    max_web_common = 0.0
    for fn in sorted(n for n in shapes if 'fastener' in n):
        deck = 'lower' if fn.startswith('lower') else 'upper'
        total = 0.0; detail = {}
        for sn, ss in struct.items():
            if not (sn.startswith(deck) or sn.startswith('shear_web')):
                continue
            v = common_volume(shapes[fn], ss)
            if v > 1e-9:
                detail[sn] = round(v, 6)
            total += v
        commons.append({'fastener': fn, 'boolean_common_volume_mm3': round(total, 9), 'detail': detail})
        if 'angle_web' in fn:
            for sn, v in detail.items():
                if sn.startswith('shear_web'):
                    max_web_common = max(max_web_common, v)
        if total > 1e-6:
            rep['failures'].append(f'{fn}: V2 布尔交集 {total} mm3 != 0, detail={detail}')
    rep['boolean_common'] = commons
    rep['web_fastener_common_max_mm3'] = max_web_common

    # D) 承压面到杆尖
    tips = []
    for fn in sorted(n for n in shapes if 'fastener' in n):
        if '_deck_fastener_' in fn:
            L = head_bearing_to_tip(shapes[fn], 2); nominal = 12.0
        else:
            side = int(fn.split('_')[4])
            L = head_bearing_to_tip(shapes[fn], 1, side); nominal = 10.0
        ok = L is not None and abs(L - nominal) < 0.01
        tips.append({'fastener': fn, 'bearing_face_to_shank_tip_mm': None if L is None else round(L, 6),
                     'nominal_mm': nominal, 'match': bool(ok)})
        if not ok:
            rep['failures'].append(f'{fn}: 承压面到杆尖 {L} != {nominal}')
    rep['bearing_face_to_shank_tip'] = tips
    rep['tip_match'] = f"{sum(t['match'] for t in tips)}/{len(tips)}"

    # E) 包络完整性 + 垫圈 OD 限值
    env_bad = []
    for fn in sorted(n for n in shapes if 'fastener' in n):
        radii = [c['r'] for c in cyl_faces(shapes[fn])]
        ok = (any(abs(r - 1.5) < 0.02 for r in radii) and any(abs(r - 2.75) < 0.02 for r in radii)
              and sum(1 for r in radii if abs(r - 3.0) < 0.02) >= 2 and 2 * max(radii) <= 6 + 1e-6)
        if not ok:
            env_bad.append(fn)
    rep['envelope_completeness'] = {'checked': 32, 'bad': env_bad}
    if env_bad:
        rep['failures'].append(f'包络完整性/垫圈限值异常: {env_bad}')

    # F) V2 vs V1 物证包络体积差
    deltas = []
    for v1f in sorted(V1.glob('*.step')):
        fn = v1f.stem
        if fn not in shapes:
            rep['failures'].append(f'v1_superseded 含未知件: {fn}')
            continue
        dv = shapes[fn].volume - import_step(str(v1f)).volume
        deltas.append({'fastener': fn, 'volume_delta_mm3': round(dv, 6)})
    exp_dv = math.pi * 1.5 ** 2 * 0.5
    dv_ok = len(deltas) == 16 and all(abs(d['volume_delta_mm3'] - exp_dv) < 1e-4 for d in deltas)
    rep['v1_v2_envelope_volume_delta'] = {'expected_mm3': round(exp_dv, 6),
                                          'expected_identity': 'π*1.5^2*0.5（V1 垫圈与杆 0.5mm 重叠在 V2 解除）',
                                          'v1_superseded_files': len(deltas),
                                          'per_fastener': deltas, 'all_match': dv_ok}
    if not dv_ok:
        rep['failures'].append(f'包络体积差与机理预期不符: n={len(deltas)} sample={deltas[:3]}')

    rep['verdict'] = 'PASS' if not rep['failures'] else 'FAIL'
    rep['elapsed_s'] = round(time.time() - t0, 3)
    f = REVIEW / 'evidence' / 'review_v2_readback.json'
    f.parent.mkdir(parents=True, exist_ok=True)
    wlf(f, json.dumps(rep, ensure_ascii=False, indent=2) + '\n'); sidecar(f)
    print('V2-T1', rep['verdict'], '| closed:', total_closed, '/16 | coax:', coax_da, '+', coax_aw,
          '| web common max:', max_web_common, '| tip:', rep['tip_match'],
          '| dv match:', dv_ok, '| failures:', len(rep['failures']))
    for x in rep['failures'][:10]:
        print(' FAIL', x)

if __name__ == '__main__':
    main()
