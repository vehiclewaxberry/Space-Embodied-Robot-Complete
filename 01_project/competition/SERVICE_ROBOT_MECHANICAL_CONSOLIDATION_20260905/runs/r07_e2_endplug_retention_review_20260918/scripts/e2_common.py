# -*- coding: utf-8 -*-
"""R07-E2 独立复验公共模块（审阅侧工具；只读候选，不改任何被审文件）。
几何常数独立推导自参数块与 WP02 源（inputs 快照），不调用候选方 spec/parts 函数。
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

REV = Path(__file__).resolve().parents[1]           # r07_e2_endplug_retention_review_20260918/
RUN = REV.parent / 'r07_e2_endplug_retention_20260918'
RUN_E1 = REV.parent / 'r07_root_longeron_anchoring_20260917'
ROOT = REV.parents[4]
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'

PARAMS_SHA256_EXPECT = '486e0c451a5c109c52e59fc7abd1820cc11a645eb51246b60c4ef42b74f3432f'
SOURCE_SHA256_EXPECT = 'f020f2179dfdffe319458b61968c6aee707572b82d438f87f12e120c285b31f0'

R_HOLE = 2.25      # Ø4.5 对偶孔
R_SHANK = 2.2      # Ø4.4 短销/栓杆
R_XBORE = 1.65     # 端塞 X 向 Ø3.3 导孔（M4 螺钉导孔）
R_SCREW = 2.0      # M4 端面螺钉包络 Ø4
PLUG_HALF = 3.9    # WP03 重建端塞 7.8/2
C = 107.15         # 角隅中心常数


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
    """OCC 原生布尔公共体积。
    工具勘误（2026-09-18 发现）：build123d Shape.intersect 在"第一参数为 import_step
    读回件"时对部分组合静默返回 None，本函数此前把 None 当 0.0，会把失败布尔伪装成
    零干涉。现改用 OCP.BRepAlgoAPI_Common 直接计算；布尔失败返回 error dict，绝不当 0。"""
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
    """从参数块独立展开 8 站（不经过候选方 transverse_retention_spec）。"""
    e2 = P['transverse_retention_r07_e2']
    out = []
    for s in e2['stations']:
        sx, sy, sz = int(s['sx']), int(s['sy']), int(s['sz'])
        out.append({'id': s['id'], 'sx': sx, 'sy': sy, 'sz': sz, 'variant': s['variant'],
                    'x': float(sx*e2['station_x_abs_mm']), 'y': float(sy*C), 'z': float(sz*C),
                    'longeron': f'RB_longeron_{sy}_{sz}',
                    'plug': f'RB_end_plug_{sx}_{sy}_{sz}',
                    'screw': f'RB_end_screw_{sx}_{sy}_{sz}'})
    assert len(out) == 8
    return out


def m4_screw_envelope(sx, sy, sz):
    """既有 M4 端面螺钉包络（WP02 screw(4,22,7,4) @ (sx*183,±C,±C) axis X）：Ø4, x∈[161,183]。"""
    return cylinder_at(4, 22, (sx*172.0, sy*C, sz*C), (1, 0, 0))


def full_length_pin(x, y, sz):
    """NC-a 变异：全长竖销 Ø4.4（舱内头下端 z=±100.15 至外侧头上端 z=±114.15 贯通）。"""
    z0, z1 = (100.15, 114.15) if sz > 0 else (-114.15, -100.15)
    return cylinder_at(4.4, z1 - z0, (x, y, (z0+z1)/2))


def plug_rebuild(sx, sy, sz, hole_dx=0.0):
    """WP03 重建端塞（spacecraft_model L253 模式）：box(20,7.8,7.8) + X 向 Ø3.3 导孔 +
    竖向 Ø4.5 孔 @ 局部 x=-sx*3（全局 sx*164）。hole_dx 为 NC-b 变异偏移。"""
    s = Box(20, 7.8, 7.8)
    s = s - cylinder_at(3.3, 24, (0, 0, 0), (1, 0, 0))
    s = s - cylinder_at(4.5, 12, (-sx*3 + hole_dx, 0, 0))
    return s.moved(Location((sx*167.0, sy*C, sz*C)))


def step_normalize_timestamp(b: bytes) -> bytes:
    """STEP 头 FILE_NAME 时间戳归一化（跨 run 同一性对照；OCC 导出时间戳不承载几何）。
    实际格式：FILE_NAME('Open CASCADE Shape Model','2026-09-18T20:56:49',...（单引号）。"""
    import re
    return re.sub(rb"'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'", b"'NORMALIZED'", b)
