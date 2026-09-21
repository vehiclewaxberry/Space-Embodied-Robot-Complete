# -*- coding: utf-8 -*-
"""R07-E1 独立复验公共模块（审阅侧工具；只读候选，不改任何被审文件）。
约定：所有输出写二进制 LF；边车 = sha256 + '  ' + 相对 review run 根的正斜杠路径。"""
import sys, json, math, hashlib
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401  系统坏字体守卫
from build123d import Box, Cylinder, Plane, Location, import_step, export_step  # noqa: F401
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_IN

REV = Path(__file__).resolve().parents[1]           # r07_e1_anchoring_review_20260918/
RUN = REV.parent / 'r07_root_longeron_anchoring_20260917'
ROOT = REV.parents[4]                                # 工作区根
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'

PARAMS_SHA256_EXPECT = 'c875b6b22b719c8e74eed87016a5c4f4a8e65f24baa0f85300081bb05d79e2d6'
SOURCE_SHA256_EXPECT = '15573df4fe7dafcdc986e3b7b623f18065acd875d1eb82b95c731f0226b3ca82'


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))


def sidecar(p):
    h = sha256_file(p)
    rel = Path(p).resolve().relative_to(REV).as_posix()
    wlf(str(p) + '.sha256', h + '  ' + rel + '\n')
    return h


def write_json(p, obj):
    wlf(p, json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    return sidecar(p)


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
    except Exception as e:  # noqa: BLE001
        return {'error': str(e)[:200]}


def inside(solid, x, y, z):
    cls = BRepClass3d_SolidClassifier(solid.wrapped, gp_Pnt(x, y, z), 1e-9)
    return cls.State() == TopAbs_IN


def cyl_faces(shape, r_tol=1e-4):
    """全部圆柱面 [(radius, loc(x,y,z), dir(x,y,z), face)]。"""
    out = []
    for f in shape.faces():
        ad = BRepAdaptor_Surface(f.wrapped)
        if ad.GetType() == GeomAbs_Cylinder:
            c = ad.Cylinder(); a = c.Axis(); l = a.Location(); d = a.Direction()
            out.append((c.Radius(), (l.X(), l.Y(), l.Z()), (d.X(), d.Y(), d.Z()), f))
    return out


def axis_distance(l1, d1, l2, d2):
    """两空间直线：平行偏差 |d1×d2| 与轴线距。"""
    cross = (d1[1]*d2[2]-d1[2]*d2[1], d1[2]*d2[0]-d1[0]*d2[2], d1[0]*d2[1]-d1[1]*d2[0])
    par = math.sqrt(sum(c*c for c in cross))
    v = (l2[0]-l1[0], l2[1]-l1[1], l2[2]-l1[2])
    cx = (v[1]*d1[2]-v[2]*d1[1], v[2]*d1[0]-v[0]*d1[2], v[0]*d1[1]-v[1]*d1[0])
    return par, math.sqrt(sum(c*c for c in cx))


def ring_closure(solid, cx, cz, y, r, n=72, dr=0.05):
    """Y 轴孔闭孔环采样：r+dr 处 n 点全部在实体内 → 该壁闭环；轴心须在实体外。"""
    out_angles = []
    for i in range(n):
        a = 2*math.pi*i/n
        if not inside(solid, cx + (r+dr)*math.cos(a), y, cz + (r+dr)*math.sin(a)):
            out_angles.append(round(a, 4))
    return out_angles, inside(solid, cx, y, cz)


def cylinder_at(d, h, c, axis=(0, 1, 0)):
    return Cylinder(d/2, h).moved(Plane(origin=tuple(c), z_dir=tuple(axis)).location)


def ring_at(od, idd, h, c, axis=(0, 1, 0)):
    return cylinder_at(od, h, c, axis) - cylinder_at(idd, h + 2, c, axis)


def load_params():
    p = ENG / 'design_parameters.json'
    h = sha256_file(p)
    P = json.loads(p.read_text(encoding='utf-8'))
    return P, h


def beam_part_name(member, beam_x):
    if member == 'bridge':
        return 'WP01-RB-BRIDGE-R2'
    return f'RB_{member}_{beam_x}'


def expected_stations(P):
    """从参数块独立展开 16 栓位（不经过候选方 spec 函数）。"""
    e1 = P['root_anchoring_r07_e1']
    out = []
    for g in e1['groups']:
        sy, sz = g['side_sy'], g['longeron_sz']
        rail = f'RB_longeron_{sy}_{sz}'
        assert rail == g['mate_instance'], f"{g['id']} mate 不一致: {rail} vs {g['mate_instance']}"
        beam = beam_part_name(g['member'], g['beam_x_mm'])
        for j, b in enumerate(g['bolts']):
            out.append({
                'pair_id': f"E1P-{g['id']}-{j}", 'group': g['id'], 'index': j,
                'x': b['x_S_mm'], 'z': b['z_S_mm'], 'sy': sy, 'sz': sz,
                'rail': rail, 'beam': beam, 'member': g['member'],
                'beam_x': g['beam_x_mm'], 'anti_rotation': g['anti_rotation'],
            })
    return out


def bolt_envelope(x, sy, z):
    """V3 栓包络：杆 Ø3 y∈[sy*93.15, sy*113.65] + 头 Ø5.5×3 y∈[sy*113.65, sy*116.65]。"""
    shank = cylinder_at(3, 20.5, (x, sy*103.4, z))
    head = cylinder_at(5.5, 3, (x, sy*115.15, z))
    return shank + head


def washer_envelope(x, sy, z):
    return ring_at(6, 3.4, 0.5, (x, sy*113.4, z))


def sleeve_envelope(x, sy, z, od=4.0):
    return ring_at(od, 3.4, 8, (x, sy*107.15, z))


def shear_web_screw_envelope(side):
    """既有剪力板栓包络（spacecraft_model L231 定义）：rod((154,±100.15,94),(154,±110.15,94),3)，
    rod 第三参为直径 → Ø3。"""
    a = (154.0, side*100.15, 94.0); b = (154.0, side*110.15, 94.0)
    c = tuple((a[i]+b[i])/2 for i in range(3))
    d = tuple(b[i]-a[i] for i in range(3))
    return cylinder_at(3, 10.0, c, d)


def unmodified_upper_beam(beam_x):
    """改件前 WP02 上横梁（依 inputs/root_structure.py 快照 L36-37 重建，逐行引用）：
    plate(R['upper_crossbeam_mm']=[14,202.3,12],
          M6_local (±70,±70) Ø6.6 + pillar local (beam_x-90,±94.15) Ø4.5) 移至 (beam_x,0,101.15)。"""
    holes = [(lx, ly, 6.6) for lx in (-70, 70) for ly in (-70, 70)]
    holes += [(beam_x - 90, ly, 4.5) for ly in (-94.15, 94.15)]
    s = Box(14, 202.3, 12)
    for hx, hy, hd in holes:
        s = s - cylinder_at(hd, 14, (hx, hy, 0), (0, 0, 1))
    return s.moved(Location((beam_x, 0, 101.15)))


def unmodified_lower_beam(beam_x):
    """改件前 WP02 下横梁（快照 L38-39）：plate([14,202.3,6], pillar (beam_x-90,±94.15) Ø4.5)
    移至 (beam_x,0,-104.15)。"""
    s = Box(14, 202.3, 6)
    for ly in (-94.15, 94.15):
        s = s - cylinder_at(4.5, 8, (beam_x - 90, ly, 0), (0, 0, 1))
    return s.moved(Location((beam_x, 0, -104.15)))


def unmodified_longeron(sy, sz):
    """改件前主纵梁（快照 L20-24）：tube((354,12,12),2,'x') + X±164 Ø4.5 孔，
    位于 (0,sy*107.15,sz*107.15)。"""
    s = Box(354, 12, 12) - Box(356, 8, 8)
    for x in (-164, 164):
        s = s - cylinder_at(4.5, 16, (x, 0, 0), (0, 0, 1))
    return s.moved(Location((0, sy*107.15, sz*107.15)))
