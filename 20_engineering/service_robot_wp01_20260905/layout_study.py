"""Reproducible fixed-base B601 layout comparison; units: mm, deg.

Read-only source meshes. Writes only LAYOUT_COMPARISON.json/.md beside this file.
Final work-pose VTK worker is bounded to 90 s; gripper sibling pair remains
explicitly unverified. Vertex-to-box SDF is NOT a mesh collision proof.
"""
from __future__ import annotations
import hashlib
import itertools
import json
import math
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
from kinematics import ROOT, URDF, TREE, tf, fk, raw_vertices, place

HERE = Path(__file__).resolve().parent
BUS_DIMS = np.array([366.0, 226.3, 226.3])
HALF = BUS_DIMS / 2
POSES = {
    'stow': [0, -15, -15, 60, -30, 0],
    'initial': [0, -30, -60, 40, 0, 0],
    'work': [0, -80, -70, 30, 0, 0],
}
BASES = {
    'roof': tf([90, 0, 125.15]),
    'side': tf([90, 125.15, 0], [-math.pi/2, 0, 0]),
    'front': tf([195, 0, 0], [0, math.pi/2, 0]),
}
FINGER_MM = 0
SKIP_FINGER_PAIR = False
CANDIDATES = [
    [0, -30, -60, 40, 0, 0],
    [0, -30, -80, 60, 0, 0],
    [0, -45, -75, 30, 0, 0],
    [0, -60, -90, 50, 0, 0],
]

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def sdf_box(points):
    d = np.abs(points) - HALF
    return np.linalg.norm(np.maximum(d, 0), axis=1) + np.minimum(d.max(axis=1), 0)

def bbox(points):
    lo, hi = points.min(axis=0), points.max(axis=0)
    return {'min_mm': lo.tolist(), 'max_mm': hi.tolist(), 'size_mm': (hi-lo).tolist()}

def geometry():
    meshes = raw_vertices()
    sources = []
    for link in TREE.findall('link'):
        visual = link.find('visual')
        origin = visual.find('origin')
        assert all(float(x) == 0 for x in origin.get('xyz').split())
        assert all(float(x) == 0 for x in origin.get('rpy').split())
        mesh = visual.find('geometry/mesh')
        assert all(float(x) == 1 for x in mesh.get('scale', '1 1 1').split())
        path = URDF.parent / mesh.get('filename')
        sources.append({'link': link.get('name'), 'path': str(path.relative_to(ROOT)),
                        'sha256': digest(path), 'unique_vertices': len(meshes[link.get('name')]),
                        'triangles': (path.stat().st_size-84)//50})
    joints = [j for j in TREE.findall('joint') if j.get('type') == 'revolute']
    limits = [{'joint': j.get('name'), 'lower_deg': math.degrees(float(j.find('limit').get('lower'))),
               'upper_deg': math.degrees(float(j.find('limit').get('upper')))} for j in joints]
    states = {}
    for label, base in BASES.items():
        states[label] = {}
        for state, q in POSES.items():
            frames = fk(q, base, finger_mm=FINGER_MM)
            transformed = {name: place(v, frames[name]) for name, v in meshes.items()}
            all_vertices = np.vstack(list(transformed.values()))
            bus_corners = np.array(list(itertools.product(*[[-h, h] for h in HALF])))
            records = {}
            for name, points in transformed.items():
                signed = sdf_box(points)
                index = int(np.argmin(signed))
                records[name] = {
                    'bbox': bbox(points),
                    'unique_vertex_count': len(points),
                    'min_vertex_signed_distance_to_bus_mm': float(signed[index]),
                    'inside_bus_vertex_count': int(np.count_nonzero(signed < -1e-8)),
                    'surface_vertex_count_tolerance_1e_minus_8_mm': int(np.count_nonzero(np.abs(signed) <= 1e-8)),
                    'minimum_sdf_vertex_world_mm': points[index].tolist(),
                }
            checks = [dict(lim, q_deg=qv, within_limit=bool(lim['lower_deg'] <= qv <= lim['upper_deg']))
                      for lim, qv in zip(limits, q)]
            states[label][state] = {
                'q_deg': q, 'base_transform_mm': base.tolist(),
                'all_six_joint_limits_satisfied': all(c['within_limit'] for c in checks),
                'joint_limit_checks': checks,
                'arm_only_bbox': bbox(all_vertices),
                'arm_and_bus_bbox': bbox(np.vstack([all_vertices, bus_corners])),
                'links': records,
                'total_inside_bus_unique_link_vertices': sum(v['inside_bus_vertex_count'] for v in records.values()),
                'self_intersection_reference': state,
            }
    return {
        'schema': 'FIXED_BASE_LAYOUT_COMPARISON_V1',
        'status': 'GEOMETRY_COMPUTED_VTK_PENDING',
        'units': {'length': 'mm', 'joint_angle': 'deg'},
        'bus_center_mm': [0, 0, 0], 'bus_dimensions_mm': BUS_DIMS.tolist(),
        'finger_joint_displacement_mm': FINGER_MM,
        'finger_joint_limit_checks': [
            {'joint':j.get('name'),'q_mm':FINGER_MM,
             'lower_mm':float(j.find('limit').get('lower'))*1000,
             'upper_mm':float(j.find('limit').get('upper'))*1000,
             'within_limit':float(j.find('limit').get('lower'))*1000 <= FINGER_MM <= float(j.find('limit').get('upper'))*1000}
            for j in TREE.findall('joint') if j.get('type')=='prismatic'
        ],
        'source_urdf': str(URDF.relative_to(ROOT)), 'source_urdf_sha256': digest(URDF),
        'kinematics_sha256': digest(HERE/'kinematics.py'),
        'layout_script_sha256': digest(__file__),
        'mesh_sources': sources,
        'digital_urdf_mass_kg_not_measured': sum(float(link.find('inertial/mass').get('value')) for link in TREE.findall('link')),
        'scope': 'Ten complete accepted B601 STL meshes plus centered rectangular bus proxy. No wings, new support, harness, equipment or motion sweep.',
        'limitations': [
            'Positive minimum vertex SDF does not prove triangle-to-bus clearance; triangles may cross the box without an interior vertex.',
            'Negative vertex SDF proves at least that mesh vertex is inside the bus proxy; the bus is a filled box proxy, not detailed spacecraft structure.',
            'Self-intersection tests check non-adjacent-link triangle surfaces at three static postures, not swept motion or hardware safety.',
            'Direct parent-child pairs are excluded; all other pairs, including gripper siblings, are included.',
            'Surface intersection includes touching; no intersection does not exclude full volumetric containment or certify minimum clearance.',
            'URDF mass/inertia and meshes are digital source data, not as-built metrology or physical certification.',
        ],
        'layouts': states, 'self_intersection_by_pose': {},
    }

def vtk_worker():
    import vtk
    started = time.monotonic()
    meshes = {}
    for link in TREE.findall('link'):
        path = URDF.parent / link.find('visual/geometry/mesh').get('filename')
        reader = vtk.vtkSTLReader(); reader.SetFileName(str(path)); reader.Update()
        scale = vtk.vtkTransform(); scale.Scale(1000, 1000, 1000)
        apply = vtk.vtkTransformPolyDataFilter(); apply.SetInputData(reader.GetOutput()); apply.SetTransform(scale); apply.Update()
        poly = vtk.vtkPolyData(); poly.DeepCopy(apply.GetOutput()); meshes[link.get('name')] = poly
    adjacent = {frozenset([j.find('parent').get('link'), j.find('child').get('link')]) for j in TREE.findall('joint')}
    pairs = [(a,b) for a,b in itertools.combinations(meshes,2) if frozenset([a,b]) not in adjacent]
    identity = vtk.vtkTransform(); identity.Identity()
    for state, q in POSES.items():
        frames = fk(q)
        world = {}
        for name, poly in meshes.items():
            matrix = vtk.vtkMatrix4x4()
            for row in range(4):
                for col in range(4): matrix.SetElement(row, col, float(frames[name][row,col]))
            transform = vtk.vtkTransform(); transform.SetMatrix(matrix)
            apply = vtk.vtkTransformPolyDataFilter(); apply.SetInputData(poly); apply.SetTransform(transform); apply.Update()
            output = vtk.vtkPolyData(); output.DeepCopy(apply.GetOutput()); world[name] = output
        result = {
            'pose': state, 'method': 'vtkCollisionDetectionFilter; first-contact; full source triangle meshes; mm',
            'vtk_version': vtk.vtkVersion.GetVTKVersion(), 'coverage_expected_nonadjacent_pairs': len(pairs),
            'excluded_direct_adjacency_count': len(adjacent), 'pairs': [],
            'rigid_base_transform_invariant_applies_to_layouts': list(BASES),
            'vtk_box_tolerance_mm': 0.0, 'vtk_cell_tolerance': 0.0,
        }
        for a,b in pairs:
            ba, bb = world[a].GetBounds(), world[b].GetBounds()
            disjoint = any(ba[2*i+1] < bb[2*i] or bb[2*i+1] < ba[2*i] for i in range(3))
            if disjoint:
                record = {'links': [a,b], 'broad_phase': 'DISJOINT_AABB', 'vtk_tested': False,
                          'surface_intersection': False, 'basis': 'Strictly separated bounds exclude intersection; no AABB overlap is treated as collision.'}
            else:
                collision = vtk.vtkCollisionDetectionFilter()
                collision.SetInputData(0,world[a]); collision.SetInputData(1,world[b])
                collision.SetTransform(0,identity); collision.SetTransform(1,identity)
                collision.SetBoxTolerance(0.0); collision.SetCellTolerance(0.0)
                collision.SetNumberOfCellsPerNode(2); collision.SetCollisionModeToFirstContact()
                collision.GenerateScalarsOff(); collision.Update()
                count = int(collision.GetNumberOfContacts())
                record = {'links': [a,b], 'broad_phase': 'OVERLAPPING_AABB', 'vtk_tested': True,
                          'surface_intersection': bool(count), 'contact_count_first_contact_mode': count}
                if count:
                    print(json.dumps({'event': 'intersection', 'pose': state, 'record': record}), flush=True)
            result['pairs'].append(record)
        result['coverage_evaluated_pairs'] = len(result['pairs'])
        result['vtk_narrow_phase_pairs'] = sum(p['vtk_tested'] for p in result['pairs'])
        result['surface_intersection_pairs'] = [p['links'] for p in result['pairs'] if p['surface_intersection']]
        result['elapsed_seconds_from_worker_start'] = time.monotonic()-started
        print(json.dumps({'event': 'pose_complete', 'data': result}), flush=True)

def write_outputs(data):
    (HERE/'LAYOUT_COMPARISON.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = [
        '# 服务星固定基座三布局比较', '',
        '本表使用同一套 10 个 B601 STL、同一组关节姿态；每种布局的基座在三个状态中固定，母线盒始终以原点为中心。长度为 mm。', '',
        f"状态：`{data['status']}`。数字 URDF 质量 {data['digital_urdf_mass_kg_not_measured']:.9f} kg，未实测。",
        '', f'母线盒尺寸 366 × 226.3 × 226.3；结果暂不含太阳翼、新支承、线束及内部设备。夹爪两个移动关节各为 {data["finger_joint_displacement_mm"]} mm。', '',
        '| 布局 | 姿态 | 整臂+母线包络 X×Y×Z | 顶点最低 signed 距离 | 穿入母线顶点数 | 六轴限位 |',
        '|---|---|---|---:|---:|---|',
    ]
    for layout, states in data['layouts'].items():
        for pose, rec in states.items():
            dims = ' × '.join(f'{x:.3f}' for x in rec['arm_and_bus_bbox']['size_mm'])
            dist = min(x['min_vertex_signed_distance_to_bus_mm'] for x in rec['links'].values())
            lines.append(f"| {layout} | {pose} | {dims} | {dist:.6f} | {rec['total_inside_bus_unique_link_vertices']} | {'满足' if rec['all_six_joint_limits_satisfied'] else '超限'} |")
    lines += ['', '## 安装与姿态', '',
              '- roof：xyz=(90, 0, 125.15)，rpy=(0, 0, 0)。',
              '- side：xyz=(90, 125.15, 0)，rpy=(-π/2, 0, 0)。',
              '- front：xyz=(195, 0, 0)，rpy=(0, π/2, 0)。',
              '- 基座基准修正：BRep承载底面位于base_link局部z=2.405 mm；上述坐标是URDF根坐标，不是承载面坐标。',
              '- 当前姿态：' + '；'.join(f'{name}={q}°' for name,q in POSES.items()) + '。',
              '', '## 非相邻 link 三角面相交', '',
              '整体刚性变换不改变机械臂自交，因此每个姿态检测一次并同时适用于 roof/side/front。排除 URDF 中直接父子 link；夹爪兄弟 link 仍检查。严格分离包围盒用于排除不可能相交的配对，所有包围盒重叠配对由 VTK 原始三角网格检测。', '']
    if not data['self_intersection_by_pose']:
        lines.append('VTK 未完成，不能给出自交裁定。')
    for pose, result in data['self_intersection_by_pose'].items():
        pairs = ', '.join('/'.join(p) for p in result['surface_intersection_pairs']) or '无'
        lines.append(f"- {pose}：覆盖 {result['coverage_evaluated_pairs']}/{result['coverage_expected_nonadjacent_pairs']} 对，其中 VTK 精检 {result['vtk_narrow_phase_pairs']} 对；表面相交：{pairs}。")
        if result.get('unverified_pairs'):
            lines.append('  未验证：' + ', '.join('/'.join(p) for p in result['unverified_pairs']) + '；不作整体无相交结论。')
    if data.get('vtk_worker_error'):
        lines += ['', f"VTK 限制/错误：`{data['vtk_worker_error']}`"]
    if data.get('candidate_repair'):
        lines += ['', '## 停放姿态修复与历史负结果', '',
                  '原 stow=(0,-15,-15,60,-30,0)°、手指0 mm的五对三角面相交保存在JSON historical_trials中，未删除。该原姿态不作为当前可用收拢姿态。', '',
                  '当前 stow 状态含义为 OPEN_PARKING 静态开放停放候选，不宣称紧凑收拢、发射约束保持或实物可用。initial 与 stow 使用相同关节值、双指15 mm，共享同一次臂体自交证据；保持件退出160 mm属于CAD装配动作，不在本脚本几何范围。work仅使用其明示覆盖结果。', '',
                  '加速仅移除三角形AABB与两link公共AABB严格分离的原始三角面，未简化或改动保留三角面。重叠配对仍由VTK FirstContact判定。']
    lines += ['', '## 每 link 对母线盒的顶点 signed 距离', '',
              '距离为盒外正、盒内负；最低值针对 STL 的唯一顶点。负值对应至少一个顶点位于实体母线代理盒内部。正值不证明三角面没有穿过盒体，也不等同于完整网格最小间隙。', '',
              '| 布局 | 姿态 | link | 最低 signed 距离/mm | 穿入顶点数 |',
              '|---|---|---|---:|---:|']
    for layout, states in data['layouts'].items():
        for pose, rec in states.items():
            for name, link in rec['links'].items():
                lines.append(f"| {layout} | {pose} | {name} | {link['min_vertex_signed_distance_to_bus_mm']:.6f} | {link['inside_bus_vertex_count']} |")
    lines += ['', '## 证据边界与复现', '',
              '静态三角面相交只说明源网格在给定姿态存在表面接触/交叉；尚未区分穿透体积、制造配合和数字导出伪影。无相交不能排除一个闭合网格完全包含另一个，也不能证明运动途中安全。直接相邻 link、实物线束、支承与完整装配几何不在本次自交覆盖内。', '',
              'JSON 保存完整坐标包络、每轴限位、各 link 最低值对应顶点、网格哈希、VTK 配对与覆盖记录。所有源资产只读。', '',
              '复现最终布局：在项目根目录运行 `python 20_engineering/service_robot_wp01_20260905/layout_study.py`。最终work检测最多90秒，指/指明确跳过为UNVERIFIED；`--candidate-repair`运行300秒候选搜索，`--legacy`运行原始240秒检测。最终布局复现读取JSON中已保存的停放35对原始回执。', '']
    (HERE/'LAYOUT_COMPARISON.md').write_text('\n'.join(lines), encoding='utf-8')

def main():
    data = geometry(); write_outputs(data)
    try:
        process = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--collision-worker'],
                                 capture_output=True, text=True, timeout=240)
        output = process.stdout
        if process.returncode:
            data['vtk_worker_error'] = process.stderr[-3000:]
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ''
        if isinstance(output, bytes): output = output.decode('utf-8', errors='replace')
        data['vtk_worker_error'] = 'TIMEOUT_240_SECONDS; completed pose results retained; remaining coverage incomplete'
    for line in output.splitlines():
        try: event = json.loads(line)
        except json.JSONDecodeError: continue
        if event.get('event') == 'pose_complete':
            rec = event['data']; data['self_intersection_by_pose'][rec['pose']] = rec
        if event.get('event') == 'intersection': print(line, flush=True)
    data['status'] = 'GEOMETRY_AND_STATIC_NONADJACENT_SURFACE_CHECK_COMPLETE' if len(data['self_intersection_by_pose']) == len(POSES) else 'GEOMETRY_COMPLETE_SELF_INTERSECTION_PARTIAL_OR_UNAVAILABLE'
    write_outputs(data)
    print(json.dumps({'status': data['status'], 'self_intersections': {k:v['surface_intersection_pairs'] for k,v in data['self_intersection_by_pose'].items()}}, ensure_ascii=False))

def raw_triangles():
    result = {}
    dtype = np.dtype([('normal','<f4',3),('vertices','<f4',(3,3)),('attr','<u2')])
    for link in TREE.findall('link'):
        path = URDF.parent/link.find('visual/geometry/mesh').get('filename')
        with path.open('rb') as stream:
            stream.read(80); count = int.from_bytes(stream.read(4),'little')
            records = np.fromfile(stream,dtype=dtype,count=count)
        result[link.get('name')] = records['vertices'].astype(float)*1000
    return result

def candidate_worker():
    import vtk
    from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
    started = time.monotonic(); raw = raw_triangles()
    adjacent = {frozenset([j.find('parent').get('link'),j.find('child').get('link')]) for j in TREE.findall('joint')}
    pairs = [(a,b) for a,b in itertools.combinations(raw,2) if frozenset([a,b]) not in adjacent]
    identity = vtk.vtkTransform(); identity.Identity()
    def polydata(tris):
        points = vtk.vtkPoints(); points.SetData(numpy_to_vtk(np.ascontiguousarray(tris.reshape(-1,3)),deep=True))
        cells = np.column_stack([np.full(len(tris),3,dtype=np.int64),np.arange(len(tris)*3,dtype=np.int64).reshape(-1,3)])
        triangles = vtk.vtkCellArray(); triangles.SetCells(len(tris),numpy_to_vtkIdTypeArray(cells.ravel(),deep=True))
        poly = vtk.vtkPolyData(); poly.SetPoints(points); poly.SetPolys(triangles)
        return poly
    for candidate_id,q in enumerate(CANDIDATES):
        frames = fk(q,finger_mm=15)
        world = {name:place(tris.reshape(-1,3),frames[name]).reshape(-1,3,3) for name,tris in raw.items()}
        extrema = {name:(tris.min(axis=1),tris.max(axis=1)) for name,tris in world.items()}
        bounds = {name:(lo.min(axis=0),hi.max(axis=0)) for name,(lo,hi) in extrema.items()}
        result = {'pose':f'candidate_{candidate_id+1}','q_deg':q,'finger_joint_displacement_mm':15,
                  'method':'vtkCollisionDetectionFilter FirstContact on unchanged source triangles after conservative triangle-AABB culling',
                  'vtk_version':vtk.vtkVersion.GetVTKVersion(),'vtk_cells_per_node':16,
                  'coverage_expected_nonadjacent_pairs':len(pairs),'excluded_direct_adjacency_count':len(adjacent),
                  'rigid_base_transform_invariant_applies_to_layouts':list(BASES),'pairs':[]}
        for a,b in pairs:
            if SKIP_FINGER_PAIR and {a,b}=={'gripper_left','gripper_right'}:
                record={'links':[a,b],'vtk_tested':False,'surface_intersection':None,'broad_phase':'NOT_EVALUATED_FINGER_PAIR_PREVIOUS_300_SECOND_TIMEOUT'}
                result['pairs'].append(record)
                print(json.dumps({'event':'pair_complete','candidate_id':candidate_id,'record':record}),flush=True)
                continue
            low = np.maximum(bounds[a][0],bounds[b][0]); high = np.minimum(bounds[a][1],bounds[b][1])
            record = {'links':[a,b],'vtk_tested':False,'surface_intersection':False}
            if np.any(low>high):
                record['broad_phase']='DISJOINT_LINK_AABB'
            else:
                crop={}
                for name in (a,b):
                    lo,hi=extrema[name]
                    mask=np.all(hi>=low,axis=1)&np.all(lo<=high,axis=1)
                    crop[name]=world[name][mask]
                record['triangle_counts_after_conservative_cull']={name:len(crop[name]) for name in (a,b)}
                if not len(crop[a]) or not len(crop[b]):
                    record['broad_phase']='NO_TRIANGLE_AABB_IN_COMMON_LINK_BOUNDS'
                else:
                    record['broad_phase']='OVERLAP_REQUIRES_VTK'
                    c=vtk.vtkCollisionDetectionFilter(); c.SetInputData(0,polydata(crop[a]));c.SetInputData(1,polydata(crop[b]))
                    c.SetTransform(0,identity);c.SetTransform(1,identity);c.SetBoxTolerance(0);c.SetCellTolerance(0)
                    c.SetNumberOfCellsPerNode(16);c.SetCollisionModeToFirstContact();c.GenerateScalarsOff();c.Update()
                    count=int(c.GetNumberOfContacts());record.update(vtk_tested=True,surface_intersection=bool(count),contact_count_first_contact_mode=count)
            result['pairs'].append(record)
            print(json.dumps({'event':'pair_complete','candidate_id':candidate_id,'record':record}),flush=True)
            if record['surface_intersection'] and set(record['links'])!={'gripper_left','gripper_right'}:
                break
        result['coverage_evaluated_pairs']=sum(p['surface_intersection'] is not None for p in result['pairs'])
        result['vtk_narrow_phase_pairs']=sum(p['vtk_tested'] for p in result['pairs'])
        result['surface_intersection_pairs']=[p['links'] for p in result['pairs'] if p['surface_intersection']]
        result['unverified_pairs']=[p['links'] for p in result['pairs'] if p['surface_intersection'] is None]
        result['all_nonadjacent_pairs_surface_disjoint']=(not result['surface_intersection_pairs']) if result['coverage_evaluated_pairs']==len(pairs) else None
        result['elapsed_seconds_from_worker_start']=time.monotonic()-started
        print(json.dumps({'event':'candidate_complete','data':result}),flush=True)
        if result['all_nonadjacent_pairs_surface_disjoint']: return

def repair_main():
    global FINGER_MM, POSES
    previous=json.loads((HERE/'LAYOUT_COMPARISON.json').read_text(encoding='utf-8'))
    try:
        process=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--candidate-worker'],capture_output=True,text=True,timeout=300)
        output=process.stdout; error=process.stderr[-3000:] if process.returncode else None
    except subprocess.TimeoutExpired as exc:
        output=exc.stdout or '';output=output.decode('utf-8',errors='replace') if isinstance(output,bytes) else output
        error='TIMEOUT_300_SECONDS; partial pair records retained; uncompleted candidates unverified'
    trials=[];partial=[]
    for line in output.splitlines():
        try:event=json.loads(line)
        except json.JSONDecodeError:continue
        if event.get('event')=='candidate_complete':trials.append(event['data']);print(line,flush=True)
        if event.get('event')=='pair_complete':partial.append(event)
    selected=next((trial for trial in trials if trial['all_nonadjacent_pairs_surface_disjoint']),None)
    if selected:
        POSES={'parking':selected['q_deg'],'initial':selected['q_deg'],'work':[0,-80,-70,30,0,0]}
    FINGER_MM=15
    data=geometry();data['historical_trials']=previous.get('historical_trials',[previous])
    data['candidate_repair']={'candidate_sequence_q_deg':CANDIDATES,'completed_candidates':trials,'pair_receipts':partial,
                              'selected_parking_q_deg':selected['q_deg'] if selected else None,
                              'work_self_intersection_status':'NOT_EVALUATED_WITH_15_MM_FINGERS'}
    if selected:
        data['self_intersection_by_pose']={'parking':dict(selected,pose='parking'),'initial':dict(selected,pose='initial')}
        data['status']='STATIC_PARKING_CANDIDATE_SURFACE_CHECK_COMPLETE__WORK_UNVERIFIED'
    else:data['status']='PARKING_REPAIR_NOT_YET_CLOSED'
    if error:data['vtk_worker_error']=error
    write_outputs(data)
    print(json.dumps({'status':data['status'],'selected_q_deg':selected['q_deg'] if selected else None,
                      'roof_parking':data['layouts']['roof'].get('parking'),'trials':len(trials)},ensure_ascii=False))

def final_main():
    global FINGER_MM, POSES
    previous=json.loads((HERE/'LAYOUT_COMPARISON.json').read_text(encoding='utf-8'))
    receipts=previous['candidate_repair']['pair_receipts']
    parked_pairs=[event['record'] for event in receipts if event['candidate_id']==0]
    assert len(parked_pairs)==35 and all(r['surface_intersection'] is False for r in parked_pairs)
    missing={'links':['gripper_left','gripper_right'],'vtk_tested':False,'surface_intersection':None,
             'broad_phase':'UNVERIFIED_PREVIOUS_300_SECOND_TIMEOUT'}
    parked={'pose':'stow','q_deg':CANDIDATES[0],'finger_joint_displacement_mm':15,
            'method':'Strict bounding separation or vtkCollisionDetectionFilter on unchanged triangles after conservative culling',
            'pairs':parked_pairs+[missing],'coverage_expected_nonadjacent_pairs':36,'coverage_evaluated_pairs':35,
            'vtk_narrow_phase_pairs':sum(r['vtk_tested'] for r in parked_pairs),'surface_intersection_pairs':[],
            'unverified_pairs':[['gripper_left','gripper_right']],'all_nonadjacent_pairs_surface_disjoint':None,
            'body_involving_pairs_surface_disjoint':True,'containment_status':'NOT_EVALUATED',
            'rigid_base_transform_invariant_applies_to_layouts':list(BASES)}
    try:
        process=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--work-worker'],capture_output=True,text=True,timeout=90)
        output=process.stdout;error=process.stderr[-3000:] if process.returncode else None
    except subprocess.TimeoutExpired as exc:
        output=exc.stdout or '';output=output.decode('utf-8',errors='replace') if isinstance(output,bytes) else output
        error='WORK_TIMEOUT_90_SECONDS; uncompleted pairs unverified'
    work=None;work_pairs=[]
    for line in output.splitlines():
        try:event=json.loads(line)
        except json.JSONDecodeError:continue
        if event.get('event')=='candidate_complete':work=event['data']
        if event.get('event')=='pair_complete':work_pairs.append(event['record'])
    if work is None:
        work={'pose':'work','q_deg':[0,-80,-70,30,0,0],'finger_joint_displacement_mm':15,'pairs':work_pairs,
              'coverage_expected_nonadjacent_pairs':36,'coverage_evaluated_pairs':sum(r['surface_intersection'] is not None for r in work_pairs),
              'vtk_narrow_phase_pairs':sum(r['vtk_tested'] for r in work_pairs),
              'surface_intersection_pairs':[r['links'] for r in work_pairs if r['surface_intersection']],
              'unverified_pairs':[['REMAINDER','NOT_EVALUATED']],'all_nonadjacent_pairs_surface_disjoint':False}
    work['pose']='work';work['containment_status']='NOT_EVALUATED'
    work['body_involving_pairs_surface_disjoint']=work['coverage_evaluated_pairs']==35 and not work['surface_intersection_pairs']
    POSES={'stow':CANDIDATES[0],'initial':CANDIDATES[0],'work':[0,-80,-70,30,0,0]};FINGER_MM=15
    data=geometry();data['historical_trials']=previous.get('historical_trials',[previous])
    data['candidate_repair']=previous['candidate_repair']
    data['candidate_repair'].update(selected_parking_q_deg=CANDIDATES[0],selection_status='OPEN_PARKING_CANDIDATE_WITH_FINGER_PAIR_UNVERIFIED',
                                    work_self_intersection_status='SEE_EXPLICIT_35_PAIR_COVERAGE')
    data['self_intersection_by_pose']={'stow':parked,'initial':dict(parked,pose='initial'),'work':work}
    data['status']='OPEN_PARKING_AND_WORK_BODY_SURFACE_CHECKS_RECORDED__FINGER_PAIR_UNVERIFIED__NO_OVERALL_PASS'
    data['base_datum_correction']={'bearing_surface_local_z_mm':2.405,'root_xyz_mm':{name:t[:3,3].tolist() for name,t in BASES.items()},
                                   'historical_old_root_results_preserved':True}
    data['containment_status']='NOT_EVALUATED'
    if error:data['vtk_worker_error']=error
    write_outputs(data)
    print(json.dumps({'status':data['status'],'q_stow':CANDIDATES[0],'q_work':POSES['work'],
                      'work_coverage':work['coverage_evaluated_pairs'],'work_intersections':work['surface_intersection_pairs'],
                      'roof_bboxes':{k:v['arm_and_bus_bbox'] for k,v in data['layouts']['roof'].items()}},ensure_ascii=False))

if __name__ == '__main__':
    if '--collision-worker' in sys.argv:vtk_worker()
    elif '--candidate-worker' in sys.argv:candidate_worker()
    elif '--work-worker' in sys.argv:
        CANDIDATES=[[0,-80,-70,30,0,0]];SKIP_FINGER_PAIR=True;candidate_worker()
    elif '--finalize' in sys.argv:final_main()
    elif '--legacy' in sys.argv:main()
    elif '--candidate-repair' in sys.argv:repair_main()
    else:final_main()
