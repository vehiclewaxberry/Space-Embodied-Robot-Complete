# -*- coding: utf-8 -*-
"""R07-E3 独立复验公共模块（审阅侧工具；只读候选，不改任何被审文件）。
几何常数独立推导自参数块 retention_joints_r07_e3 与被审登记表，不调用候选方 spec/parts 函数。
布尔一律 OCP.BRepAlgoAPI_Common 原生路径（E2 审阅勘误 O2；禁用 build123d Shape.intersect 作判据，
仅作路径归因对照且仅限 build123d 原生件）。
约定：输出写二进制 LF；边车 = sha256 + '  ' + 相对 review run 根正斜杠路径。"""
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
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps

REV = Path(__file__).resolve().parents[1]           # r07_e3_retention_joints_review_20260918/
RUN = REV.parent / 'r07_e3_retention_joints_20260918'
RUN_E1 = REV.parent / 'r07_root_longeron_anchoring_20260917'
RUN_E2 = REV.parent / 'r07_e2_endplug_retention_20260918'
ROOT = REV.parents[4]
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'

PARAMS_SHA256_EXPECT = '0470d647d17b1779784123156963f5ce84aa1f259ba810f5b25454c54b2514c4'
SOURCE_SHA256_EXPECT = '4276a2da2c0a753f1b2734f140376b72b124f2cd25e0985b78dbb85107c70b3f'

Z_CLAMP = 103.65     # 边1 栓位 z
Y_FOOT = -90.65      # 边2 栓链 y（v2）
Y_FOOT_V1 = -94.15   # v1 栓链 y（NC-a 回放）
HUB_Z_MIN = 125.15   # 足叉槽内轮毂 r10 干涉域下限
C = 107.15


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
    """OCC 原生布尔公共体积（E2 勘误 O2 口径）；布尔失败返回 error dict，绝不当 0。"""
    try:
        op = BRepAlgoAPI_Common(a.wrapped, b.wrapped)
        op.Build()
        if not op.IsDone():
            return {'error': 'BRepAlgoAPI_Common build failed'}
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(op.Shape(), props)
        return float(props.Mass())
    except Exception as e:  # noqa: BLE001
        return {'error': str(e)[:200]}


def b123d_common(a, b):
    """被审方 E1 时代布尔路径 build123d Shape.intersect（仅用于路径归因对照；
    仅限 build123d 原生件；import 件有静默 None 陷阱）。"""
    c = a.intersect(b)
    if c is None:
        return {'error': 'build123d intersect returned None (import-step trap)'}
    return float(sum(s.volume for s in c.solids()))


def inside(solid, x, y, z):
    cls = BRepClass3d_SolidClassifier(solid.wrapped, gp_Pnt(x, y, z), 1e-9)
    return cls.State() == TopAbs_IN


def cyl_faces(shape):
    out = []
    for f in shape.faces():
        ad = BRepAdaptor_Surface(f.wrapped)
        if ad.GetType() == GeomAbs_Cylinder:
            c = ad.Cylinder(); a = c.Axis(); l = a.Location(); d = a.Direction()
            out.append((c.Radius(), (l.X(), l.Y(), l.Z()), (d.X(), d.Y(), d.Z()), f))
    return out


def axis_distance(l1, d1, l2, d2):
    cross = (d1[1]*d2[2]-d1[2]*d2[1], d1[2]*d2[0]-d1[0]*d2[2], d1[0]*d2[1]-d1[1]*d2[0])
    par = math.sqrt(sum(c*c for c in cross))
    v = (l2[0]-l1[0], l2[1]-l1[1], l2[2]-l1[2])
    cx = (v[1]*d1[2]-v[2]*d1[1], v[2]*d1[0]-v[0]*d1[2], v[0]*d1[1]-v[1]*d1[0])
    return par, math.sqrt(sum(c*c for c in cx))


def cylinder_at(d, h, c, axis=(0, 0, 1)):
    return Cylinder(d/2, h).moved(Plane(origin=tuple(c), z_dir=tuple(axis)).location)


def ring_at(od, idd, h, c, axis=(0, 0, 1)):
    return cylinder_at(od, h, c, axis) - cylinder_at(idd, h + 2, c, axis)


def load_params():
    p = ENG / 'design_parameters.json'
    return json.loads(p.read_text(encoding='utf-8')), sha256_file(p)


def stations(P):
    """从参数块独立展开 12 栓位（8 边1 clamp + 4 边2 foot），不经过候选方 spec 函数。"""
    e3 = P['retention_joints_r07_e3']
    out = []
    for g in e3['edge1_clamp']['groups']:
        sy = int(g['side_sy'])
        for j, b in enumerate(g['bolts']):
            x = float(b['x_S_mm'])
            out.append({'edge': 'edge1', 'pair_id': f"E3P-{g['id']}-{j}", 'group': g['id'],
                        'index': j, 'x': x, 'sy': sy, 'z': Z_CLAMP,
                        'bolt': f"e3_clamp_bolt_{g['id']}_{j}",
                        'washer': f"e3_clamp_washer_{g['id']}_{j}",
                        'mate': g['mate_instance'],
                        'beam': f"hold_crossbeam_{g['k']}"})
    for g in e3['edge2_foot']['groups']:
        for j, b in enumerate(g['bolts']):
            x = float(b['x_S_mm'])
            out.append({'edge': 'edge2', 'pair_id': f"E3P-{g['id']}-{j}", 'group': g['id'],
                        'index': j, 'x': x, 'y': Y_FOOT,
                        'bolt': f"e3_foot_bolt_{g['id']}_{j}",
                        'washer': f"e3_foot_washer_{g['id']}_{j}",
                        'beam': f"hold_crossbeam_{g['k']}",
                        'lug': f"hold_roof_lug_{g['k']}_-94.15",
                        'foot': f"hold_pivot_clevis_{g['k']}"})
    assert len(out) == 12
    return out


# ---- 新件包络（参数块独立重建；THREADLESS 名义包络） ----

def clamp_bolt_envelope(x, sy, shank_tip_y_abs=96.15):
    """边1 栓：杆 Ø3 y∈[sy*tip, sy*113.65] + 头 Ø5.5×3 y∈[sy*113.65, sy*116.65]。
    v2 杆端 |y|=96.15（贯入 5）；v1 回放杆端 |y|=93.15（贯入 8）。"""
    a, b = sorted((sy*shank_tip_y_abs, sy*113.65))
    shank = cylinder_at(3, b - a, (x, (a+b)/2, Z_CLAMP), (0, 1, 0))
    h0, h1 = sorted((sy*113.65, sy*116.65))
    head = cylinder_at(5.5, h1 - h0, (x, (h0+h1)/2, Z_CLAMP), (0, 1, 0))
    return shank + head


def clamp_washer_envelope(x, sy):
    y0, y1 = sorted((sy*113.15, sy*113.65))
    return ring_at(6, 3.4, y1 - y0, (x, (y0+y1)/2, Z_CLAMP), (0, 1, 0))


def foot_bolt_envelope(x, y=Y_FOOT, shank_top_z=123.15):
    """边2 栓链：头 Ø7×4 z∈[91.15,95.15] + 杆 Ø4 z∈[95.15, shank_top_z]（v2 尖 123.15）。"""
    head = cylinder_at(7, 4, (x, y, 93.15))
    shank = cylinder_at(4, shank_top_z - 95.15, (x, y, (95.15+shank_top_z)/2))
    return head + shank


def foot_washer_envelope(x, y=Y_FOOT):
    return ring_at(9, 4.5, 1, (x, y, 95.65))


def foot_bolt_v1(x):
    """v1 回放边2 栓链（y=-94.15）。"""
    return foot_bolt_envelope(x, y=Y_FOOT_V1)
