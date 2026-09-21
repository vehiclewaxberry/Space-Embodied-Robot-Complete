# -*- coding: utf-8 -*-
"""R07-E4 独立复验公共模块（审阅侧工具；只读候选，不改任何被审文件）。
几何常数独立推导自参数块 rear_bulkhead_clamp_r07_e4 与被审登记表，不调用候选方 spec/parts 函数。
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

REV = Path(__file__).resolve().parents[1]           # r07_e4_rear_bulkhead_review_20260918/
RUN = REV.parent / 'r07_e4_rear_bulkhead_20260918'
RUN_E1 = REV.parent / 'r07_root_longeron_anchoring_20260917'
RUN_E2 = REV.parent / 'r07_e2_endplug_retention_20260918'
RUN_E3 = REV.parent / 'r07_e3_retention_joints_20260918'
REV_E3 = REV.parent / 'r07_e3_retention_joints_review_20260918'
ROOT = REV.parents[4]
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'

# 现行钉固（已实测与 E4 EXPORT_MANIFEST 逐位一致）
SOURCE_SHA256_EXPECT = 'a888cda0a2c0ead7d3d985b5d3218ee1f8f6721059420dec593e1bdefcf1d81e'
PARAMS_SHA256_EXPECT = '324b49c712f3b499dda0feb963527e4e7f4b25bfc151c4f83ab57bf382108ea8'
E4_COMMIT = 'd1a3b70a'

C = 107.15  # 角区 y/z 站位 |值|

# E3 审阅 r32 build 口径 OCC 复核值（bit-identical 预言的对照基准）
E3_REVIEW_BUILD_OCC = {
    'RB_end_plug_-1_-1_-1': 49.71305176453028,
    'RB_end_plug_-1_-1_1': 49.713051764535635,
    'RB_end_plug_-1_1_-1': 49.71305176453034,
    'RB_end_plug_-1_1_1': 49.713051764535685,
    'RB_end_plug_1_-1_-1': 49.71154569515958,
    'RB_end_plug_1_-1_1': 49.711545695160815,
    'RB_end_plug_1_1_-1': 49.71154569515932,
    'RB_end_plug_1_1_1': 49.71154569516056,
}


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
    """从参数块独立展开 4 角站位，不经过候选方 spec 函数。"""
    e4 = P['rear_bulkhead_clamp_r07_e4']
    out = []
    for g in e4['groups']:
        sy, sz = int(g['sy']), int(g['sz'])
        out.append({'group': g['id'], 'sy': sy, 'sz': sz,
                    'y': sy * C, 'z': sz * C,
                    'sleeve': f"e4_clamp_sleeve_{g['id']}",
                    'screw': f"RB_end_screw_-1_{sy}_{sz}",
                    'plug': f"RB_end_plug_-1_{sy}_{sz}",
                    'frame': 'RB_end_frame_-1',
                    'bulkhead': 'rear_launch_bulkhead'})
    assert len(out) == 4
    return out


# ---- E4 新件/改件包络（参数块独立重建；THREADLESS 名义包络；支持变异偏移作负控） ----

def clamp_sleeve_envelope(sy, sz, dx=0.0, dy=0.0):
    """阶梯夹套：筒 OD7.9×6 x∈[-189,-183] + 法兰 OD12×2 x∈[-191,-189] − ID Ø4.5 通孔。
    dx/dy 为负控变异偏移。"""
    y, z = sy * C + dy, sz * C
    barrel = cylinder_at(7.9, 6, (-186 + dx, y, z), (1, 0, 0))
    flange = cylinder_at(12, 2, (-190 + dx, y, z), (1, 0, 0))
    return (barrel + flange) - cylinder_at(4.5, 12, (-186 + dx, y, z), (1, 0, 0))


def screw_e4_envelope(sy, sz, dy=0.0):
    """改件 M4×30：头 Ø7×4 x∈[-195,-191] + 杆 Ø4 x∈[-191,-161]（尖端 -161）。"""
    y, z = sy * C + dy, sz * C
    head = cylinder_at(7, 4, (-193, y, z), (1, 0, 0))
    shank = cylinder_at(4, 30, (-176, y, z), (1, 0, 0))
    return head + shank


def screw_baseline_envelope(sy, sz):
    """E4 前基线 M4×22：头 Ø7×4 x∈[-187,-183] + 杆 Ø4 x∈[-183,-161]（尖端 -161 不变）。"""
    y, z = sy * C, sz * C
    head = cylinder_at(7, 4, (-185, y, z), (1, 0, 0))
    shank = cylinder_at(4, 22, (-172, y, z), (1, 0, 0))
    return head + shank


def sleeve_volume_analytic():
    return (math.pi / 4 * (7.9**2 - 4.5**2) * 6 + math.pi / 4 * (12**2 - 4.5**2) * 2)
