"""Bounded current-board placement check; run only through the native serial guard.

The PCB uses current V26 dimensions/drills. Only overlapping parent STEP parts
are loaded, and service/parking/released results retain their individual IDs.
This is an installation rejection check, not a populated-board fit release.
"""
from pathlib import Path
import datetime, hashlib, itertools, json
from build123d import Box, Cylinder, Pos, Align
from OCP.STEPControl import STEPControl_Reader
from OCP.gp import gp_Trsf
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepCheck import BRepCheck_Analyzer

A = Path(__file__).resolve().parents[1]
def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def transformed(shape, matrix):
    t = gp_Trsf()
    t.SetValues(*[v for row in matrix[:3] for v in row])
    return BRepBuilderAPI_Transform(shape, t, True).Shape()

def bounds(bb, matrix):
    pts = [[sum(matrix[i][j] * v[j] for j in range(3)) + matrix[i][3]
            for i in range(3)] for v in itertools.product(*[(bb[i], bb[i+3]) for i in range(3)])]
    return [min(p[i] for p in pts) for i in range(3)] + [max(p[i] for p in pts) for i in range(3)]

def overlap(a, b):
    return all(min(a[i+3], b[i+3]) - max(a[i], b[i]) > 1e-6 for i in range(3))

def main():
    target = A/'results/MAIN_BOARD_SIDE_POSE_CHECK_V27.json'
    assert not target.exists(), 'Retain previous check evidence; do not overwrite'
    source = A/'mechanical/MAIN_INPUT_PLACEMENT_BOUNDS_V27.json'
    data = json.loads(source.read_text())
    definition = A/'power/MAIN_INPUT_BOARD_DEFINITION_V26.json'
    d = json.loads(definition.read_text())
    assert sha(A/data['source_plan']) == data['source_plan_sha256']
    assert sha(A/'ecad/wp10_main_input.kicad_pcb') == d['PCB_sha256']
    assert all(len(rows) == 974 for rows in data['states'].values())
    board = Pos(50, -40, -.8) * Box(100, 80, 1.6)
    refs = {r['ref']: r for r in d['refs']}
    for x,y in d['mounting_holes_mm']:
        board -= Pos(x, -y, -2) * Cylinder(1.6, 3, align=(Align.CENTER, Align.CENTER, Align.MIN))
    for pad in d['pads']:
        dx,dy = pad['drill_mm']
        if dx == 0 or dy == 0 or pad['ref'].startswith('MH'):
            continue
        x,y = pad['xy_mm']
        if abs(dx-dy) < 1e-8:
            cut = Pos(x,-y,-2) * Cylinder(dx/2,3,align=(Align.CENTER,Align.CENTER,Align.MIN))
        else:
            assert dx >= dy and refs[pad['ref']]['rotation_deg'] == 0
            cut = Pos(x,-y,-.5) * Box(dx-dy,dy,3)
            for off in (-(dx-dy)/2,(dx-dy)/2):
                cut += Pos(x+off,-y,-2) * Cylinder(dy/2,3,align=(Align.CENTER,Align.CENTER,Align.MIN))
        board -= cut
    assert BRepCheck_Analyzer(board.wrapped).IsValid()
    poses = {
        'negative_Y_initial': [[1,0,0,-55],[0,0,1,-92],[0,-1,0,-5],[0,0,0,1]],
        'positive_Y_first_candidate': [[1,0,0,-38],[0,0,-1,92],[0,1,0,75],[0,0,0,1]],
    }
    cache, results = {}, {}
    for name, matrix in poses.items():
        bb = bounds([0,-80,-1.6,100,0,0], matrix)
        placed = transformed(board.wrapped, matrix)
        rows_out = {}
        for state, rows in data['states'].items():
            hits = []
            for row in rows:
                if not overlap(bb, row['bbox_S_mm']):
                    continue
                key = (name, row['source_sha256'], json.dumps(row['T_S_step']))
                if key not in cache:
                    assert sha(row['step_path']) == row['source_sha256']
                    reader = STEPControl_Reader()
                    assert int(reader.ReadFile(row['step_path'])) == 1
                    reader.TransferRoots()
                    existing = transformed(reader.OneShape(), row['T_S_step'])
                    assert BRepCheck_Analyzer(existing).IsValid()
                    common = BRepAlgoAPI_Common(placed, existing)
                    common.Build()
                    assert common.IsDone()
                    props = GProp_GProps()
                    BRepGProp.VolumeProperties_s(common.Shape(), props)
                    cache[key] = props.Mass()
                hits.append(dict(id=row['id'], common_volume_mm3=cache[key],
                                 source_sha256=row['source_sha256'], step_path=row['step_path']))
            rows_out[state] = hits
        results[name] = dict(T_S_step=matrix, board_bbox_S_mm=bb, states=rows_out,
                            rejected_by_board_collision=any(h['common_volume_mm3'] > 1e-3
                                for hits in rows_out.values() for h in hits))
    out = dict(schema='WP10_V27_CURRENT_PCB_SIDE_POSE_NATIVE_INTERSECTION',
               time_local=datetime.datetime.now().astimezone().isoformat(),
               source_script_sha256=sha(__file__), bounds_source_sha256=sha(source),
               board_definition_sha256=sha(definition), PCB_sha256=d['PCB_sha256'],
               parent_plan_sha256=data['source_plan_sha256'], native_unique_pairs=len(cache),
               board_substrate_valid=True, poses=results, installed_in_whole=False,
               populated_board_fit_verified=False, manufacturing_release=False,
               scope='Current drilled bare PCB versus overlapping existing STEP instances only; '
                     'no new component population, bracket, tool access, tolerance or thermal credit.')
    with target.open('x',encoding='utf-8') as f:
        json.dump(out,f,ensure_ascii=False,indent=2)
    print(json.dumps({name:{'rejected':v['rejected_by_board_collision'],
                           'service_intersections':v['states']['service']} for name,v in results.items()}))

if __name__ == '__main__':
    main()
