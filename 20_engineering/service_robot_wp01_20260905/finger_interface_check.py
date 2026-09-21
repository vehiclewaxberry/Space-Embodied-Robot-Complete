"""Static nominal BRep finger-pair check at q_left=q_right=15 mm."""
from pathlib import Path
import hashlib
import json
import math
import sys
import time
import xml.etree.ElementTree as ET

sys.path.insert(0, 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/packages/cadgen/src')
import cadgen
from cadgen.step_scene import import_step
import numpy as np
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepGProp import BRepGProp
from OCP.Bnd import Bnd_Box
from OCP.GProp import GProp_GProps
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.gp import gp_Trsf

HERE = Path(__file__).resolve().parent
URDF = HERE.parent / 'cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf'
OUT = HERE / 'results/FINGER_INTERFACE_CHECK.json'
TIME_LIMIT_S = 175
VOLUME_TOL_MM3 = 1e-7


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bbox(shape):
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, box, False, False)
    v = box.Get()
    return [list(v[:3]), list(v[3:])]


def solids(shape):
    result = []
    cursor = TopExp_Explorer(shape, TopAbs_SOLID)
    while cursor.More():
        result.append(cursor.Current())
        cursor.Next()
    return result


def matrix_from_joint(joint, q_mm):
    origin = joint.find('origin')
    xyz = np.array([float(x) for x in origin.get('xyz').split()]) * 1000
    roll, pitch, yaw = [float(x) for x in origin.get('rpy').split()]
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    rotation = rz @ ry @ rx
    axis = np.array([float(x) for x in joint.find('axis').get('xyz').split()])
    matrix = np.eye(4)
    matrix[:3, :3] = rotation
    matrix[:3, 3] = xyz + rotation @ (axis * q_mm)
    transform = gp_Trsf()
    transform.SetValues(*[float(x) for x in matrix[:3, :].ravel()])
    return matrix, transform


def main():
    started = time.perf_counter()
    tree = ET.parse(URDF).getroot()
    fingerprints = {str(URDF): sha(URDF)}
    groups, group_rows = [], []
    for name in ['gripper_left', 'gripper_right']:
        source = HERE / 'inputs' / f'{name}.step'
        fingerprints[str(source)] = sha(source)
        joint = next(j for j in tree.findall('joint') if j.find('child').get('link') == name)
        assert joint.get('type') == 'prismatic'
        assert joint.find('parent').get('link') == 'gripper_link'
        assert float(joint.find('limit').get('lower')) <= .015 <= float(joint.find('limit').get('upper'))
        matrix, transform = matrix_from_joint(joint, 15.0)
        transformed = BRepBuilderAPI_Transform(import_step(source).wrapped, transform, True).Shape()
        items = solids(transformed)
        groups.append((transformed, items))
        group_rows.append(dict(link=name, joint=joint.get('name'), input=str(source),
                               q_mm=15.0, T_gripper_link_child_mm=matrix.tolist(),
                               solid_count=len(items), compound_bbox_mm=bbox(transformed),
                               solids=[dict(index=i, bbox_mm=bbox(s)) for i, s in enumerate(items)]))
    checked, overlaps, errors = [], [], []
    timeout = False
    for i, a in enumerate(groups[0][1]):
        for j, b in enumerate(groups[1][1]):
            aa = group_rows[0]['solids'][i]['bbox_mm']
            bb = group_rows[1]['solids'][j]['bbox_mm']
            widths = [min(aa[1][k], bb[1][k]) - max(aa[0][k], bb[0][k]) for k in range(3)]
            if min(widths) <= 1e-6:
                continue
            if time.perf_counter() - started > TIME_LIMIT_S:
                timeout = True
                break
            row = dict(left_solid_index=i, right_solid_index=j,
                       aabb_overlap_width_mm=widths, source_bboxes_mm=[aa, bb])
            try:
                common = BRepAlgoAPI_Common(a, b)
                if not common.IsDone():
                    raise RuntimeError('OCC common failed')
                props = GProp_GProps()
                BRepGProp.VolumeProperties_s(common.Shape(), props)
                row['common_volume_mm3'] = abs(props.Mass())
                checked.append(row)
                if row['common_volume_mm3'] > VOLUME_TOL_MM3:
                    overlaps.append(row)
            except Exception as exc:
                row['error'] = str(exc)
                errors.append(row)
        if timeout:
            break
    minimum_distance = None
    if not timeout:
        distance = BRepExtrema_DistShapeShape(groups[0][0], groups[1][0])
        if distance.IsDone():
            minimum_distance = distance.Value()
        else:
            errors.append(dict(error='OCC compound minimum distance failed'))
    after = {path: sha(Path(path)) for path in fingerprints}
    out = dict(method='ACCEPTED_URDF_RZ_RY_RX_MATRIX_DIRECT_TO_GP_TRSF_THEN_BREP_COMMON',
               units='mm_and_mm3', state=dict(gripper_joint1_mm=15.0, gripper_joint2_mm=15.0),
               groups=group_rows, exact_pairs=checked, positive_volume_overlaps=overlaps,
               minimum_compound_distance_mm=minimum_distance, errors=errors,
               elapsed_s=time.perf_counter()-started, time_limit_reached=timeout,
               source_hashes_before=fingerprints, source_hashes_after=after,
               sources_unchanged=fingerprints == after,
               volume_threshold_mm3=VOLUME_TOL_MM3,
               status='INCOMPLETE' if timeout or errors else
                      'NOMINAL_BREP_POSITIVE_VOLUME_OVERLAPS_FOUND' if overlaps else
                      'NOMINAL_BREP_NO_POSITIVE_VOLUME_OVERLAPS_AT_15MM',
               scope='STATIC_NOMINAL_BREP_TWO_FINGERS_ONLY; DOES_NOT_CLOSE_ACCEPTED_STL_VTK_CHECK; NO_SYSTEM_PASS_OR_HARDWARE_FIT_CLAIM')
    OUT.write_text(json.dumps(out, indent=2), encoding='utf-8')
    print(json.dumps({k: out[k] for k in ['status','minimum_compound_distance_mm','elapsed_s','sources_unchanged']}, indent=2))
    print('exact_candidates', len(checked), 'overlaps', len(overlaps))
    print(json.dumps(overlaps, indent=2))


if __name__ == '__main__':
    main()
