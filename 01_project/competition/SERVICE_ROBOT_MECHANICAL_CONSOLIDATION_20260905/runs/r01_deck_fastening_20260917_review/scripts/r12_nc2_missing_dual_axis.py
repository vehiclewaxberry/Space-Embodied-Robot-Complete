# -*- coding: utf-8 -*-
"""WP03 R01 验收6 独立复验 - 负控二：缺对偶 / 错轴线可检出。

变异件：重建 lower_deck_angle_-1_0（几何逐义复刻工程源 spacecraft_model.py deck_fastening_parts
角材段：水平腿 box((b-a,11,3)) + 竖直腿 box((b-a,3,14))，段 [-167,11.5]，side=-1，lower 甲板），
将甲板侧 x=-150 配合孔人为偏移 +1mm（钻到 x=-149）。
随后用与任务1完全同源的配对检查（期望轴位 vs 实测轴位，容差 0.05mm）对照真实读回的
lower_equipment_deck：预期该对偶在期望位置 (-150,-92.65) 找不到角材侧孔轴（缺对偶），
且最近角材孔轴径向偏差 1.0mm（错轴线），其余 7 组甲板-角材对偶不受影响（防误报对照）。
"""
import sys, json, math, hashlib, time
from pathlib import Path

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen  # noqa: F401
from build123d import Box, Cylinder, Location, Plane, export_step
from cadgen.step_scene import import_step
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder

ROOT = Path(__file__).resolve().parents[6]
RUN = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917'
REVIEW = ROOT / '01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/r01_deck_fastening_20260917_review'
ENG = ROOT / '20_engineering/service_robot_wp03_spacecraft_body_r1'
WORK = REVIEW / '_work' / 'nc2_mutant_angle'
TOL_AXIS = 0.05
TOL_COAX = 1e-3

P = json.loads((ENG / 'design_parameters.json').read_text(encoding='utf-8'))
R01 = P['deck_fastening_r01']
DPAT = R01['deck_hole_pattern']; WPAT = R01['angle_to_shear_web_hole_pattern']

def wlf(p, text):
    with open(p, 'wb') as fh:
        fh.write(text.encode('utf-8'))

def sidecar(p):
    h = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    wlf(str(p) + '.sha256', h + '  ' + Path(p).name + '\n')
    return h

def box(size, c=(0, 0, 0)):
    return Box(*size).moved(Location(tuple(c)))

def bore(s, d, h, c=(0, 0, 0), axis=(0, 0, 1)):
    return s - Cylinder(d / 2, h).moved(Plane(origin=tuple(c), z_dir=axis).location)

def z_axis_holes(shape, r=1.7, tol=0.02):
    out = []
    for f in shape.faces():
        ad = BRepAdaptor_Surface(f.wrapped)
        if ad.GetType() != GeomAbs_Cylinder:
            continue
        cyl = ad.Cylinder(); ax = cyl.Axis(); loc = ax.Location(); d = ax.Direction()
        if abs(cyl.Radius() - r) < tol and abs(abs(d.Z()) - 1) < 1e-6:
            out.append((loc.X(), loc.Y()))
    return out

def build_angle(side=-1, k=0, deck='lower', mutant_dx=None):
    """逐义复刻 deck_fastening_parts 角材段；mutant_dx: {孔x: 偏移mm} 仅作用甲板侧孔。"""
    z = {'lower': -99.65, 'upper': -10}[deck]
    a, b = [(-167, 11.5), (28.5, 151.5)][k]
    legz = 5.5 if deck == 'lower' else -5.5
    angle = box((b - a, 11, 3), (0, -side * 3.5, 0)) + box((b - a, 3, 14), (0, side * 3.5, legz))
    cx = (a + b) / 2; cy = side * 96.15; cz = z - 3
    for x in DPAT['X_S_mm']:
        if a - 1e-9 <= x <= b + 1e-9:
            xm = x + (mutant_dx or {}).get(x, 0)
            angle = bore(angle, 3.4, 7, (xm - cx, side * 92.65 - cy, 0))
    for x in WPAT['X_S_mm_by_segment'][k]:
        angle = bore(angle, 3.4, 12, (x - cx, side * 99.65 - cy,
                                      WPAT['Z_S_mm_by_deck'][deck] - cz), (0, 1, 0))
    return angle.moved(Location((cx, cy, cz)))

def main():
    t0 = time.time()
    WORK.mkdir(parents=True, exist_ok=True)
    mutant = build_angle(side=-1, k=0, deck='lower', mutant_dx={-150: 1.0})
    f = WORK / 'mutant_lower_deck_angle_-1_0_hole150_shifted_1mm.step'
    export_step(mutant, str(f))
    s_mut = import_step(str(f))
    s_deck = import_step(str(RUN / 'exports' / 'lower_equipment_deck.step'))

    deck_axes = z_axis_holes(s_deck)
    ang_axes = z_axis_holes(s_mut)
    checks = []
    detected_missing = False
    detected_deviation = None
    false_positives = []
    for x in DPAT['X_S_mm']:
        if not (-167 - 1e-9 <= x <= 11.5 + 1e-9):
            continue
        ey = -92.65
        da = min(deck_axes, key=lambda ax: math.hypot(ax[0] - x, ax[1] - ey))
        near = [ax for ax in ang_axes if math.hypot(ax[0] - x, ax[1] - ey) < TOL_AXIS]
        dual_missing = not near
        aa = min(ang_axes, key=lambda ax: math.hypot(ax[0] - da[0], ax[1] - da[1]))
        dev = math.hypot(aa[0] - da[0], aa[1] - da[1])
        flagged = dual_missing or dev > TOL_COAX
        checks.append({'expected_xy': [x, ey], 'deck_axis': [round(v, 6) for v in da],
                       'nearest_angle_axis': [round(v, 6) for v in aa],
                       'dual_missing_at_expected_position': dual_missing,
                       'coaxial_deviation_mm': round(dev, 6), 'flagged': flagged})
        if x == -150:
            detected_missing = dual_missing
            detected_deviation = dev
        elif flagged:
            false_positives.append(x)
    rep = {
        'review': 'r01_deck_fastening_20260917_review',
        'check': 'ACC6_NC2_missing_dual_or_axis_offset_detectable',
        'negative_control': '变异角材 x=-150 甲板侧孔偏移 +1mm -> 配对检查必须报缺对偶且错轴线 1.0mm',
        'mutant': {'part': 'lower_deck_angle_-1_0（隔离重建）', 'mutation': 'deck-side hole x=-150 -> -149 (+1mm)',
                   'step_file': f.name, 'step_sha256': hashlib.sha256(f.read_bytes()).hexdigest(),
                   'geometry_source': '工程源 spacecraft_model.py deck_fastening_parts 角材段逐义复刻；未改原文件'},
        'reference_deck': 'exports/lower_equipment_deck.step（真实读回）',
        'tolerances': {'axis_match_mm': TOL_AXIS, 'coaxial_mm': TOL_COAX},
        'pair_checks': checks,
        'detection': {'missing_dual_detected_at_x-150': detected_missing,
                      'measured_axis_deviation_mm': round(detected_deviation, 6),
                      'expected_deviation_mm': 1.0,
                      'false_positives_on_unmutated_pairs': false_positives},
        'failures': []}
    ok = (detected_missing and abs(detected_deviation - 1.0) < 1e-6 and not false_positives)
    if not ok:
        rep['failures'].append(f'检出异常: missing={detected_missing} dev={detected_deviation} false_pos={false_positives}')
    rep['detected'] = ok
    rep['verdict'] = 'NC2_PASS_missing_dual_and_axis_offset_detected' if ok else 'NC2_FAIL_detector_blind_to_dual_defect'
    rep['elapsed_s'] = round(time.time() - t0, 3)
    out = REVIEW / 'evidence' / 'review_nc2_missing_dual_axis.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    wlf(out, json.dumps(rep, ensure_ascii=False, indent=2) + '\n'); sidecar(out)
    print('NC2', rep['verdict'], 'missing_dual:', detected_missing,
          'dev:', round(detected_deviation, 6), 'false_pos:', false_positives)

if __name__ == '__main__':
    main()
