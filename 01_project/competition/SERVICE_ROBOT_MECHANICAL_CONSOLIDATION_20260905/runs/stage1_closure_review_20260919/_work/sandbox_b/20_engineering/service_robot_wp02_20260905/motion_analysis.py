"""WP02 accepted-STL sampled path and fixture-proxy analysis (mm, deg).

No BRep import, CAD rebuild, or actuator simulation. Only four owned outputs.
"""
from __future__ import annotations
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import numpy as np

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
WP01 = HERE.parent/'service_robot_wp01_20260905'
spec = importlib.util.spec_from_file_location('wp01_kinematics', WP01/'kinematics.py')
kin = importlib.util.module_from_spec(spec); spec.loader.exec_module(kin)
BASE = kin.tf([90, 0, 125.15])
Q0 = np.array([0,-30,-60,40,0,0], dtype=float)
Q1 = np.array([0,-80,-70,30,0,0], dtype=float)
FINGER_MM = 15.0
TOL = 1e-8
BUDGETS = {'position_error_candidate_mm':2.0, 'overrun_candidate_mm':3.0, 'design_margin_candidate_mm':5.0}
SAMPLES = sorted(set(np.linspace(0,1,21).tolist()+[0.002,0.005,0.01,0.02,0.025]))

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read_triangles():
    meshes={}; sources=[]
    dtype=np.dtype([('normal','<f4',3),('vertices','<f4',(3,3)),('attr','<u2')])
    for link in kin.TREE.findall('link'):
        path=kin.URDF.parent/link.find('visual/geometry/mesh').get('filename')
        with path.open('rb') as stream:
            stream.read(80);count=int.from_bytes(stream.read(4),'little')
            data=np.fromfile(stream,dtype=dtype,count=count)
        name=link.get('name');meshes[name]=data['vertices'].astype(float)*1000
        sources.append({'link':name,'path':str(path),'sha256':sha(path),'triangles':len(meshes[name])})
    return meshes,sources

def box_relation(a,b):
    a=np.asarray(a,float);b=np.asarray(b,float)
    overlap=np.minimum(a[1],b[1])-np.maximum(a[0],b[0])
    if np.any(overlap < -TOL): relation='STRICTLY_SEPARATED'
    elif np.any(np.abs(overlap)<=TOL): relation='TOUCHING_BOUNDS'
    elif np.all(a[0]>=b[0]) and np.all(a[1]<=b[1]): relation='A_CONTAINED_IN_B'
    elif np.all(b[0]>=a[0]) and np.all(b[1]<=a[1]): relation='B_CONTAINED_IN_A'
    else: relation='OVERLAPPING_BOUNDS'
    return {'relation':relation,'axis_overlap_mm':overlap.tolist()}

def clip_polygon(poly,axis,bound,keep_greater):
    if not len(poly): return poly
    output=[];prev=poly[-1];dp=(prev[axis]-bound)*(1 if keep_greater else -1)
    for cur in poly:
        dc=(cur[axis]-bound)*(1 if keep_greater else -1)
        pin=dp >= -TOL;cin=dc >= -TOL
        if pin != cin:
            denom=cur[axis]-prev[axis]
            if abs(denom)>1e-15:
                output.append(prev+(bound-prev[axis])/denom*(cur-prev))
        if cin:output.append(cur)
        prev=cur;dp=dc
    return np.asarray(output,dtype=float).reshape(-1,3)

def clipped_bounds(triangles,limits):
    """Clip original triangles against axis half-spaces; do not use vertices alone."""
    if not len(triangles):return None
    lo=triangles.min(axis=1);hi=triangles.max(axis=1);mask=np.ones(len(triangles),dtype=bool)
    for axis,(lower,upper) in limits.items():
        mask &= (hi[:,axis]>=lower-TOL)&(lo[:,axis]<=upper+TOL)
    candidates=triangles[mask]
    if not len(candidates):return None
    out_lo=np.full(3,np.inf);out_hi=np.full(3,-np.inf);count=0
    for triangle in candidates:
        poly=triangle
        for axis,(lower,upper) in limits.items():
            poly=clip_polygon(poly,axis,lower,True)
            poly=clip_polygon(poly,axis,upper,False)
            if not len(poly):break
        if len(poly):
            out_lo=np.minimum(out_lo,poly.min(axis=0));out_hi=np.maximum(out_hi,poly.max(axis=0));count+=1
    return None if not count else {'min_mm':out_lo.tolist(),'max_mm':out_hi.tolist(),'intersecting_triangle_count':count,
                                   'triangle_aabb_candidates':len(candidates)}

def clip_world(world,limits):
    details={}
    for name,tris in world.items():
        result=clipped_bounds(tris,limits)
        if result:details[name]=result
    if not details:return None
    return {'min_mm':np.min([d['min_mm'] for d in details.values()],axis=0).tolist(),
            'max_mm':np.max([d['max_mm'] for d in details.values()],axis=0).tolist(),'links':details}

def transform_meshes(raw,q):
    frames=kin.fk(q,BASE,finger_mm=FINGER_MM)
    return {name:kin.place(tris.reshape(-1,3),frames[name]).reshape(-1,3,3) for name,tris in raw.items()}

def extrema(world):
    return {'min_mm':np.min([t.min(axis=(0,1)) for t in world.values()],axis=0).tolist(),
            'max_mm':np.max([t.max(axis=(0,1)) for t in world.values()],axis=0).tolist()}

def fixtures():
    base=[[0,0,0],[1,1,1]]
    cases=[('box_separation',[[2,0,0],[3,1,1]],'STRICTLY_SEPARATED'),
           ('box_overlap',[[.5,.5,.5],[1.5,1.5,1.5]],'OVERLAPPING_BOUNDS'),
           ('box_tangent',[[1,0,0],[2,1,1]],'TOUCHING_BOUNDS'),
           ('box_containment',[[.2,.2,.2],[.8,.8,.8]],'B_CONTAINED_IN_A'),
           ('thin_box_overlap',[[.499999,0,0],[.500001,1,1]],'B_CONTAINED_IN_A')]
    records=[]
    for name,other,expected in cases:
        actual=box_relation(base,other)['relation'];records.append({'case':name,'expected':expected,'actual':actual,'passed':actual==expected})
    tests=[('triangle_disjoint',[[2,0,.5],[3,0,.5],[2,1,.5]],{0:(0,1),1:(0,1),2:(0,1)},False),
           ('triangle_crosses_thin_box_without_inside_vertex',[[-2,-1,.5],[2,-1,.5],[0,2,.5]],{0:(-.001,.001),1:(-.001,.001),2:(0,1)},True),
           ('triangle_tangent',[[0,0,1],[1,0,1],[0,1,1]],{0:(0,1),1:(0,1),2:(0,1)},True),
           ('triangle_inside_box',[[.2,.2,.5],[.8,.2,.5],[.2,.8,.5]],{0:(0,1),1:(0,1),2:(0,1)},True)]
    for name,tri,limits,expected in tests:
        actual=clipped_bounds(np.array([tri],float),limits) is not None
        records.append({'case':name,'expected_intersection':expected,'actual_intersection':actual,'passed':actual==expected})
    assert all(r['passed'] for r in records)
    return records

def main():
    started=time.monotonic(); raw, sources=read_triangles()
    parameters=json.loads((WP01/'design_parameters.json').read_text(encoding='utf-8'))
    receipt=json.loads((WP01/'results/stowed_build_receipt.json').read_text(encoding='utf-8'))
    assert np.allclose(np.asarray(receipt['T_S_arm_base']),BASE)
    assert np.array_equal(parameters['states']['stowed']['q_deg'],Q0)
    assert np.array_equal(parameters['states']['work']['q_deg'],Q1)
    station_inputs=receipt['supports'];samples=[]
    parked=transform_meshes(raw,Q0)
    parked_checks={}
    for station in station_inputs:
        x=station['x_mm']; top=station['retainer_bottom_z_mm']
        section=clip_world(parked,{0:(x-9,x+9)})
        parked_checks[str(x)]={'retainer_z_mm':[top,top+6],
                              'arm_exact_clipped_station_top_mm':section['max_mm'][2] if section else None,
                              'full_18_mm_station_top_clearance_mm':top-section['max_mm'][2] if section else None,
                              'positive_y_exit_samples':[]}
        for slide in np.linspace(0,160,9):
            limits={0:(x-9,x+9),1:(-59+slide,59+slide),2:(top,top+6)}
            hit=clip_world(parked,limits)
            parked_checks[str(x)]['positive_y_exit_samples'].append({'slide_mm':float(slide),'accepted_stl_surface_intersects_retainer_proxy':hit is not None,'intersection':hit})
    print(json.dumps({'event':'parked_retainer_geometry','data':parked_checks}),flush=True)
    for fraction in SAMPLES:
        q=Q0+fraction*(Q1-Q0);world=parked if fraction==0 else transform_meshes(raw,q)
        record={'path_fraction':fraction,'q_deg':q.tolist(),'arm_bbox':extrema(world),'stations':{}}
        for station in station_inputs:
            x=station['x_mm'];upper=station['retainer_bottom_z_mm'];lower=station['pad_top_z_mm']
            section=clip_world(world,{0:(x-9,x+9)})
            retainer_band=clip_world(world,{0:(x-9,x+9),2:(upper,upper+6)})
            saddle_section=clip_world(world,{0:(x-7,x+7),1:(-47,47)})
            saddle_hit=clip_world(world,{0:(x-7,x+7),1:(-47,47),2:(lower-6,lower)})
            exit_hit=clip_world(world,{0:(x-9,x+9),1:(101,219),2:(upper,upper+6)})
            record['stations'][str(x)]={
                'section_18_mm':section,'retainer_height_band':retainer_band,'saddle_xy_section':saddle_section,
                'stationary_saddle_proxy_surface_intersection':saddle_hit is not None,
                'stationary_saddle_proxy_intersection_details':saddle_hit,
                'retainer_160_mm_proxy_surface_intersection':exit_hit is not None,
                'saddle_vertical_clearance_mm':saddle_section['min_mm'][2]-lower if saddle_section else None,
            }
        samples.append(record)
        print(json.dumps({'event':'sample_complete','fraction':fraction,'saddle_clearance_mm':{name:s['saddle_vertical_clearance_mm'] for name,s in record['stations'].items()}}),flush=True)
    extra=sum(BUDGETS.values());summary={}
    for station in station_inputs:
        key=str(station['x_mm']);recs=[s['stations'][key] for s in samples]
        section_recs=[r['section_18_mm'] for r in recs if r['section_18_mm']]
        bands=[r['retainer_height_band'] for r in recs if r['retainer_height_band']]
        ymax=max(r['max_mm'][1] for r in section_recs)
        band_ymax=max((r['max_mm'][1] for r in bands),default=None)
        saddle_samples=[(s['path_fraction'],s['stations'][key]['saddle_vertical_clearance_mm']) for s in samples if s['stations'][key]['saddle_vertical_clearance_mm'] is not None]
        worst=min(saddle_samples,key=lambda item:item[1]);geom_drop=max(0,-worst[1])
        first_negative=next((r for r in saddle_samples if r[1]<-TOL),None)
        geom_slide=max(0,ymax+59);total_slide=geom_slide+extra
        saddle_y_geom=max(0,ymax+47)
        summary[key]={
            'station_source':station,'sampled_arm_section_y_max_mm':ymax,
            'sampled_retainer_height_band_y_max_mm':band_ymax,
            'retainer_geometry_only_sufficient_positive_y_slide_mm':geom_slide,
            'retainer_candidate_position_error_mm':BUDGETS['position_error_candidate_mm'],
            'retainer_candidate_overrun_mm':BUDGETS['overrun_candidate_mm'],
            'retainer_candidate_margin_mm':BUDGETS['design_margin_candidate_mm'],
            'retainer_total_candidate_positive_y_slide_mm':total_slide,
            'retainer_160_mm_surplus_over_candidate_requirement_mm':160-total_slide,
            'retainer_160_positive_y_separation_min_mm':101-ymax,
            'saddle_min_vertical_clearance_mm':worst[1], 'saddle_worst_sample_fraction':worst[0],
            'saddle_first_sample_negative_clearance':first_negative,
            'saddle_geometry_only_downward_withdrawal_mm':geom_drop,
            'saddle_downward_candidate_with_2_3_5_mm_budgets':geom_drop+extra,
            'saddle_geometry_only_sufficient_positive_y_slide_mm':saddle_y_geom,
            'saddle_total_candidate_positive_y_slide_mm':saddle_y_geom+extra,
            'stationary_saddle_intersection_fractions':[s['path_fraction'] for s in samples if s['stations'][key]['stationary_saddle_proxy_surface_intersection']],
            'retainer_160_intersection_fractions':[s['path_fraction'] for s in samples if s['stations'][key]['retainer_160_mm_proxy_surface_intersection']],
            'parking_18_mm_retainer_top_check':parked_checks[key],
        }
    global_ymax=max(s['arm_bbox']['max_mm'][1] for s in samples)
    cable={'candidate_exclusion_corridor_y_mm':[-160,-110],
           'x_extent_mm':None,'z_extent_mm':None,'bend_radius_mm':None,'as_built_position_error_mm':None,
           'status':'CANDIDATE_CORRIDOR_NOT_A_ROUTED_HARNESS',
           'minimum_arm_y_over_samples_mm':min(s['arm_bbox']['min_mm'][1] for s in samples),
           'retainer_translation_y_union_mm':[-59,219],
           'retainer_vs_corridor_y_axis_separation_mm':51.0,
           'caution':'Only specified retainer Y envelope can be separated from the corridor; carriage/drive/connectors lack full geometry.'}
    result={'schema':'WP02_SAMPLED_ACCEPTED_STL_MOTION_ANALYSIS_V1','status':'SAMPLED_PATH_CHECK_NOT_CONTINUOUS_OR_FULL_ASSEMBLY_CERTIFICATION',
            'units':{'length':'mm','joint_angle':'deg'},'root_transform':BASE.tolist(),'q_park_deg':Q0.tolist(),'q_work_deg':Q1.tolist(),
            'finger_mm':FINGER_MM,'sample_count':len(SAMPLES),'sample_fractions':SAMPLES,
            'path_sequence':['unlock while arm remains parked; unlock mechanism unmodelled','withdraw upper retainer and carriage toward +Y; lower saddle withdrawal must be resolved','move arm along sampled linear joint path with wings folded','deploy wings after arm path; wing sweep NOT_EVALUATED'],
            'candidate_error_budget_mm':BUDGETS,'physical_error_inputs':{'position_error_mm':None,'overrun_mm':None,'structural_deflection_mm':None,'joint_tracking_error_deg':None,'harness_bend_radius_mm':None},
            'budget_status':'2/3/5 mm ARE DESIGN CANDIDATES, NOT MEASURED PHYSICAL VALUES',
            'station_summary':summary,'sampled_global_arm_y_max_mm':global_ymax,
            'global_y_plane_geometry_only_sufficient_retainer_slide_mm':global_ymax+59,
            'global_y_plane_candidate_slide_with_budgets_mm':global_ymax+59+extra,
            'cable_corridor':cable,'samples':samples,'fixtures':fixtures(),
            'source_meshes':sources,'source_hashes':{str(path):sha(path) for path in [WP01/'design_parameters.json',WP01/'kinematics.py',WP01/'layout_study.py',WP01/'results/stowed_build_receipt.json',WP01/'results/DELIVERY_RECEIPT.json',Path(__file__)]},
            'limitations':['Discrete joint samples do not enclose the continuous rotation between samples.','Triangle clipping checks accepted STL surfaces against explicit fixture boxes; fixture-box overlap is not a full CAD collision verdict.','No full volumetric containment, BRep collision, dynamic joint tracking, flexible harness, lower support mechanism or wing swept-volume test.','Carriage and release drive dimensions remain unspecified; same-direction motion alone does not certify their separation.','Unknown physical errors are null; candidate allowances must be replaced by identified bounds before certification.'],
            'elapsed_seconds':time.monotonic()-started,
            'elapsed_seconds_scope':'Original parked-fixture and26-pose scan plus method fixtures; supplementary crossbeam/GSE measurements excluded',
            'supplementary_elapsed_seconds':None}
    add_revised_candidate(result,raw,parked)
    (HERE/'results').mkdir(parents=True,exist_ok=True)
    (HERE/'results/MOTION_ANALYSIS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    write_report(result)
    print(json.dumps({'event':'SUMMARY','stations':{k:{kk:vv for kk,vv in v.items() if kk not in ['parking_18_mm_retainer_top_check','station_source']} for k,v in summary.items()},'global_y_plane_candidate_slide_mm':global_ymax+59+extra,'elapsed_seconds':result['elapsed_seconds']},ensure_ascii=False),flush=True)

def write_report(d):
    coverage=[
        ['arm_bus','arm ↔ spacecraft bus','UNKNOWN','No full swept triangle-box bus test in this task; WP01 static vertex checks are not inherited as path clearance.'],
        ['arm_self','nonadjacent arm links and finger pair','UNKNOWN','No self-collision test along the WP02 path; WP01 endpoint receipts do not establish intermediate clearance.'],
        ['arm_upper_retainer','arm ↔ upper retainer/pad','SAMPLED_PATH_CHECK','Old fixture intersections retained. Raised keeper end state uses conditional Y-plane separation; initial upper pads touch link3 and shell load allowance is unknown.'],
        ['arm_lower_saddle','arm ↔ lower shoes/crossbeams','SAMPLED_PATH_CHECK','Actual triangle clipping in 24x90 footprints; active down30, up8 adjustment and candidate error budgets are separately reported.'],
        ['arm_carriage_drive','arm ↔ carriage, guide, release actuator','PARTIAL_SAMPLED_END_STATE_SEPARATION','Given whole moving-group minY=-59, +Y180 separates group from sampled arm; detailed withdrawal/interlock geometry remains unknown.'],
        ['retainer_fixed_structure','retainer/carriage ↔ posts, rails, spacecraft','SAMPLED_OCC_FIXED_MOVING_CHECK','Latest KEY_GEOMETRY_CHECK covers Y0/90/180 plus selected first-motion/functional interfaces; latest fixedGSE-arm box result covers26 arm poses. Continuous motion and complete fixed/fixed joining not certified.'],
        ['wings_environment','arm/retainer/GSE ↔ folded and deploying wings','COUNTEREXAMPLE_AT_WING_90_DEG','Four current final-receipt posts with shared positiveX40 and top690 intersect90deg wing envelopes; former six-column layout retained only as history.'],
        ['mechanism_harness','moving mechanisms/GSE ↔ negative-Y cable corridor','PARTIAL_AXIS_CHECK_WITH_RESERVATION_CONFLICT','Moving-group Y union[-59,310] is 51 mm from corridor; negative-Y155 post overlaps the corridor Y reservation by15 mm; actual route X/Z unknown.'],
    ]
    with (HERE/'collision_coverage.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.writer(stream);writer.writerow(['pair_class','pair_description','status','basis_and_limits']);writer.writerows(coverage)
    lines=['# WP02 停放释放与机械臂运动几何分析','',
           '**结论等级：SAMPLED_PATH_CHECK。** 本计算使用10个accepted STL和固定URDF根坐标[90,0,125.15] mm，不导入508个BRep。', '',
           f"停车q={d['q_park_deg']}°，work q={d['q_work_deg']}°，双指各15 mm；沿关节线性插值计算{d['sample_count']}个姿态，在首动段额外加密。路径参数不是时间。", '',
           '当前候选时序：停车解锁→下鞋-30 mm、上接触垫+12 mm分别确认→整体保持框/滑架+Y180 mm确认→臂首动及到work→移除工装或转独立托持→再展开翼。当前公共正柱X40、柱顶690、高梁Z660；Y0/90/180已有新件OCC实体配对结果，但不能据此声明连续释放路径全部通过。', '',
           '## 新180 mm/下退30 mm候选', '',
           '本节是当前候选，后文原160 mm/旧平板结果作为反例保留。']
    if d.get('revised_candidate'):
        n=d['revised_candidate'];g=n['global_y_plane_separation']
        lines += [f"移动组初态minY=-59 mm，+Y180后minY=121 mm；采样臂最大Y={g['sampled_arm_y_max_mm']:.9f}，几何分离={g['geometry_gap_mm']:.9f} mm，扣候选2+3+5 mm后余{g['candidate_budget_residual_mm']:.9f} mm。该结论不覆盖未采样旋转间隙。", '',
                  '| 站位 | 24×90区域最小臂Z | 下退30后名义净空 | 装调+8后净空 | 再扣10预算 | 新上框梁底Z | 上垫初始底Z/责任link |',
                  '|---|---:|---:|---:|---:|---:|---|']
        for key,s in n['lower_crossbeams'].items():
            upper=n['upper_keeper'][key]
            lines.append(f"| {key} | {s['minimum']['minimum_z_mm']:.6f} | {s['minimum_gap_after_down30_mm']:.6f} | {s['minimum_gap_with_adjustment_plus8_mm']:.6f} | {s['residual_after_candidate_budget_mm']:.6f} | {upper['keeper_bottom_max_plus20_mm']:.6f} | {upper['pad_bottom_mm']:.6f} / {upper['responsible_link']} |")
        lines += ['', '**已修订反例仍保留：**旧同站+Y155柱冲突、其后的X+55六柱跨站冲突均为历史。最新release receipt只有4根柱：(-115,-155)、(-40,-155)、(40,155)、(40,315)，顶690 mm；公共高梁Z660，导轨为局部arm_maxZ+65，实际新件由KEY_GEOMETRY_CHECK记录。', '',
                  '当前4根柱仍与90°翼板外包络相交：两根负Y155及一根正Y155柱各2000 mm³，一根+Y315柱1515 mm³。数值为外包络交叠，不能当作方管实际材料体积。此结论来自90°时精确轴对齐声明box，翼展开前仍需移除GSE。', '',
                  '上保持框的责任link为link3，下鞍座接触对象为link2；目前没有壳体承载许可、接触力或局部强度证据，不能把整体折叠臂保持框称为直接夹紧link2。']
    lines += ['',
           '## 原160 mm/旧平板的历史反例', '',
           '| 站位x/mm | 保持件几何+Y行程/mm | 候选2+3+5后/mm | 160 mm余量/mm | 下鞍座最小Z净空/mm | 几何下降/mm | 下降加预算/mm |',
           '|---:|---:|---:|---:|---:|---:|---:|']
    for key,s in d['station_summary'].items():
        lines.append(f"| {key} | {s['retainer_geometry_only_sufficient_positive_y_slide_mm']:.6f} | {s['retainer_total_candidate_positive_y_slide_mm']:.6f} | {s['retainer_160_mm_surplus_over_candidate_requirement_mm']:.6f} | {s['saddle_min_vertical_clearance_mm']:.6f} | {s['saddle_geometry_only_downward_withdrawal_mm']:.6f} | {s['saddle_downward_candidate_with_2_3_5_mm_budgets']:.6f} |")
    lines += ['', '保持件代理：每站x±9 mm、初始y[-59,59] mm、厚6 mm，底面取WP01该站retainer_bottom_z_mm。行程要求使用该站完整x切片的采样臂Y上界，给出Y平面分离的充分几何条件；这不证明两姿态之间的连续旋转路径。', '',
              '误差预算逐项分开：位置误差2 mm、退出过冲3 mm、设计余量5 mm，均为明确候选值。实测位置误差、执行器过冲、结构变形和关节跟踪误差均为null，不能把候选预算当成硬件参数。该历史计算时滑架/驱动器没有完整尺寸，160 mm对当时保持件的结果不能推广给后续完整机构。', '',
              '下鞍座按WP01 x±7、y±47、厚6 mm代理计算。负净空意味着局部臂表面已降到鞍座顶面以下；应结合三角面与鞍座box相交记录处理，不能仅看全臂外包络。下降需求按整个采样路径最小Z给出，也提供向+Y完全退出的候选行程；能否下降、轨道是否穿过母线结构仍为未知。', '']
    for key,s in d['station_summary'].items():
        park=s['parking_18_mm_retainer_top_check']
        lines += [f"- x={key}：首个负鞍座净空采样={s['saddle_first_sample_negative_clearance']}；最差在路径比例{s['saddle_worst_sample_fraction']:.6f}。固定鞍座三角面相交比例={s['stationary_saddle_intersection_fractions']}。",
                  f"  保持件18 mm厚度范围的停车上表面净空={park['full_18_mm_station_top_clearance_mm']:.6f} mm；原14 mm顶点切片的2 mm设置不能自动保证扩宽后的18 mm保持件净空。",
                  f"  下鞍座向+Y完全退出的候选总行程={s['saddle_total_candidate_positive_y_slide_mm']:.6f} mm。"]
    lines += ['', '## 线束与覆盖边界', '',
              '根部线束候选走负Y侧，预留y[-160,-110] mm排他走廊。当前整体移动组平移范围y[-59,310]与该走廊具有51 mm轴向分离；但负Y155工装柱y[-165,-145]与走廊Y预留重叠15 mm，需要在路线X/Z与柱位上处理。真实线束、弯曲半径、连接器仍未知。', '',
              'collision_coverage.csv列出8类配对。新件滑架/固定工装已做三个Y位置的OCC Boolean，固定GSE与accepted arm已做26姿态box裁剪；连续机械臂自碰、完整翼扫掠、真实线束、体积包含和未采样路径仍UNKNOWN。', '',
              '## 方法与复现', '',
              '使用严格AABB分离进行宽相筛选；近区对原始STL三角形执行半空间多边形裁剪，获得x切片/xy区域实际表面极值，并测试显式fixture box。薄片穿越即使没有原始顶点位于box内部也会被裁剪测试发现。表面相交不等于完整实体配合结论，源STL与BRep差异仍保留。', '',
              f"解析fixture自检{len(d['fixtures'])}/{len(d['fixtures'])}通过，覆盖分离、交叠、相切、包含和无内部顶点的薄片穿越。这只是方法自检，不是设计通过。", '',
              '复现：`python 20_engineering/service_robot_wp02_20260905/motion_analysis.py`。原始结果、每姿态局部几何、全部相交记录和来源SHA256保存在results/MOTION_ANALYSIS.json。', '']
    final=d.get('revised_candidate',{}).get('final_receipt_geometry')
    if final:
        fixed_check=final.get('fixed_gse_arm_check')
        if fixed_check:
            lines += ['## 最终固定工装与机械臂覆盖','',
                      f"当前released构建收据选出{fixed_check['fixed_fixture_count']}个固定部件，与10个accepted STL link、26姿态共{fixed_check['total_sample_link_fixture_pairs']}配对；{fixed_check['strict_aabb_separation_count']}对严格AABB分离，{fixed_check['triangle_clip_pair_count']}对进入原三角面box裁剪，表面相交{fixed_check['surface_hit_count']}。", '',
                      f"收据来源：{fixed_check.get('released_receipt_source','结果文件内记录')}；使用KEY内嵌构建快照={fixed_check.get('released_receipt_is_embedded_snapshot',False)}。新增锁销吊架、上接桥、捕获壳底座、丝杆端连接件均在本轮范围。", '',
                      '完整实心Box与带孔梁/方管外包络已按receipt体积分开；contains和采样间连续旋转均未验证。详见results/FIXED_GSE_ARM_PATH.json。', '']
        key_check=final.get('key_geometry_check')
        if key_check:
            lines += ['最新轻量OCC实体检查：'+json.dumps(key_check,ensure_ascii=False)+'。这不等于实物装配、接触力或预紧验证。','']
    (HERE/'MOTION_AND_CLEARANCE.md').write_text('\n'.join(lines),encoding='utf-8')

def add_revised_candidate(data,raw,parked,lower_rows=None):
    """Owner-provided revision; retain all original 160 mm/flat-pad findings."""
    tops={-115.0:365.829873,-40.0:331.631998}
    upper={}
    for x in tops:
        section=clip_world(parked,{0:(x-9,x+9),1:(-59,59)})
        responsible=max(section['links'],key=lambda name:section['links'][name]['max_mm'][2])
        z=section['max_mm'][2]
        upper[str(x)]={'all_arm_park_section':section,'responsible_link':responsible,
                       'pad_bottom_mm':z,'pad_thickness_mm':4,'pad_initial_retreat_positive_z_mm':12,
                       'keeper_bottom_max_plus20_mm':z+20,'shell_load_allowance':None,
                       'scope':'Overall folded-arm keeper contacting link3; NOT direct link2 hold claim.'}
    if lower_rows is None:
        lower_rows={str(x):{'nominal_top_mm':top,'lowered_top_mm':top-20,'samples':[]} for x,top in tops.items()}
        for t in SAMPLES:
            world=transform_meshes(raw,Q0+t*(Q1-Q0))
            for x,top in tops.items():
                clipped=clip_world(world,{0:(x-12,x+12),1:(-45,45)})
                z=clipped['min_mm'][2] if clipped else None
                lower_rows[str(x)]['samples'].append({'fraction':t,'minimum_z_mm':z,'gap_after_down20_mm':None if z is None else z-(top-20)})
        for s in lower_rows.values():s['minimum']=min((row for row in s['samples'] if row['minimum_z_mm'] is not None),key=lambda row:row['minimum_z_mm'])
    for s in lower_rows.values():
        s['active_withdrawal_mm']=30;s['adjustment_range_mm']=[-8,8];s['active_lowered_top_mm']=s['nominal_top_mm']-30
        for row in s['samples']:
            z=row['minimum_z_mm']
            row['gap_after_down30_mm']=None if z is None else z-s['active_lowered_top_mm']
            row['gap_after_down30_and_adjustment_plus8_mm']=None if z is None else z-s['active_lowered_top_mm']-8
        s['minimum_gap_after_down30_mm']=s['minimum']['gap_after_down20_mm']+10
        s['minimum_gap_with_adjustment_plus8_mm']=s['minimum_gap_after_down30_mm']-8
        s['residual_after_candidate_budget_mm']=s['minimum_gap_with_adjustment_plus8_mm']-sum(BUDGETS.values())
    fixed={str(x):{'dimensions_mm':[24,330,12],'top_mm':top-40,'samples':[]} for x,top in tops.items()}
    for t in SAMPLES:
        world=transform_meshes(raw,Q0+t*(Q1-Q0))
        for x in tops:
            section=clip_world(world,{0:(x-12,x+12),1:(-165,165)})
            z=section['min_mm'][2] if section else None
            fixed[str(x)]['samples'].append({'fraction':t,'minimum_arm_z_mm':z,'top_plane_gap_mm':None if z is None else z-fixed[str(x)]['top_mm']})
    for s in fixed.values():s['minimum_top_plane_gap_mm']=min(row['top_plane_gap_mm'] for row in s['samples'] if row['top_plane_gap_mm'] is not None)
    columns=[];wing_counterexamples=[];keeper_counterexamples=[]
    for x in tops:
        for y in [-155.,155.,345.]:
            column=np.array([[x-10,y-10,-132.15],[x+10,y+10,580]])
            columns.append({'center_xy_mm':[x,y],'outer_box_mm':column.tolist(),'tube_wall_mm':None})
            for side in [-1,1]:
                y_bounds=(-320.15,-125.15) if side<0 else (125.15,320.15)
                wing=np.array([[-160,y_bounds[0],-108.15],[160,y_bounds[1],-103.15]])
                relation=box_relation(column,wing)
                if relation['relation']!='STRICTLY_SEPARATED':
                    overlap=np.maximum(0,np.minimum(column[1],wing[1])-np.maximum(column[0],wing[0]))
                    wing_counterexamples.append({'column_center_xy_mm':[x,y],'wing_side':side,'relation':relation,
                                                 'overlap_dimensions_mm':overlap.tolist(),'outer_envelope_overlap_mm3':float(np.prod(overlap)),
                                                 'actual_tube_material_overlap_mm3':None,
                                                 'material_overlap_for_uniform_wall_t_mm':'5*(400-(20-2*t)^2), 0<t<10; t unknown',
                                                 'basis':'At90deg source wing substrate is axis-aligned; this is an exact declared-box intersection, not rotated-AABB inference.'})
            bar_bottom=upper[str(x)]['keeper_bottom_max_plus20_mm']
            bar=np.array([[x-9,121,bar_bottom],[x+9,239,bar_bottom+6]])
            relation=box_relation(column,bar)
            if relation['relation']!='STRICTLY_SEPARATED':
                keeper_counterexamples.append({'column_center_xy_mm':[x,y],'keeper_at_y180_box_mm':bar.tolist(),
                                               'height_assumption_mm':6,'relation':relation,
                                               'positive_thickness_intersection_condition':'Any positive bar thickness with bottom below580; 6 mm used only to display proxy box.',
                                               'actual_tube_material_overlap_mm3':None})
    ymax=data['sampled_global_arm_y_max_mm'];gap=121-ymax;extra=sum(BUDGETS.values())
    data['revised_candidate']={'status':'SAMPLED_ARM_CLEARANCE_WITH_RETAINED_GSE_COUNTEREXAMPLES',
        'active_sequence':['arm parked and wings folded','unlock; lower shoe -30 mm and upper pad +12 mm confirmed','keeper/carriage +Y180 mm confirmed, after fixed-post conflict repair','arm sampled q path','remove GSE or transfer to independent support','only then deploy wings'],
        'moving_group_initial_min_y_mm':-59,'carrier_cantilever_initial_y_mm':[-12,130],
        'moving_group_translation_union_y_mm':[-59,310],
        'global_y_plane_separation':{'sampled_arm_y_max_mm':ymax,'moving_group_final_min_y_mm':121,'geometry_gap_mm':gap,
                                     'candidate_budget_residual_mm':gap-extra,'old160_geometry_gap_mm':101-ymax,
                                     'old160_residual_after_budget_mm':101-ymax-extra,
                                     'scope':'Sufficient end-state plane separation for specified whole-group minY at26 arm samples; not proof of continuous motion or fixture/fixture separation.'},
        'upper_keeper':upper,'lower_crossbeams':lower_rows,'fixed_lower_beams':fixed,
        'gse_columns':columns,'keeper_positive155_post_counterexamples':keeper_counterexamples,
        'wing90_column_counterexamples':wing_counterexamples,
        'negative155_post_vs_cable_y_reservation':{'post_y_mm':[-165,-145],'corridor_y_mm':[-160,-110],'overlap_y_mm':15,'actual_3d_route_conflict':'UNKNOWN_XZ_CORRIDOR_NOT_DEFINED'},
        'physical_uncertainty_inputs':{'position_error_mm':None,'stop_overrun_mm':None,'joint_tracking_error_deg':None,'shell_contact_allowance':None,'gse_tube_wall_mm':None}}
    data['prior_candidate_sequence']=data['path_sequence'];data['path_sequence']=data['revised_candidate']['active_sequence']
    apply_gse_column_revision(data)
    data['source_hashes'][str(Path(__file__))]=sha(__file__)

def apply_gse_column_revision(data):
    data['elapsed_seconds_scope']='Original parked-fixture and26-pose scan plus method fixtures; supplementary crossbeam/GSE measurements excluded'
    data['supplementary_elapsed_seconds']=None
    n=data['revised_candidate'];columns=[];wing_hits=[];keeper_checks=[]
    for x in [-115.,-40.]:
        for cx,cy in [(x,-155.),(x+55,155.),(x+55,315.)]:
            box=np.array([[cx-10,cy-10,-132.15],[cx+10,cy+10,620]])
            columns.append({'station_x_mm':x,'center_xy_mm':[cx,cy],'outer_box_mm':box.tolist(),'tube_wall_mm':None})
            for side in [-1,1]:
                ylo,yhi=(-320.15,-125.15) if side<0 else (125.15,320.15)
                wing=np.array([[-160,ylo,-108.15],[160,yhi,-103.15]])
                relation=box_relation(box,wing)
                if relation['relation']!='STRICTLY_SEPARATED':
                    overlap=np.maximum(0,np.minimum(box[1],wing[1])-np.maximum(box[0],wing[0]))
                    wing_hits.append({'post_center_xy_mm':[cx,cy],'wing_side':side,'overlap_dimensions_mm':overlap.tolist(),
                                      'outer_envelope_overlap_mm3':float(np.prod(overlap)),'actual_material_overlap_mm3':None,
                                      'basis':'Exact axis-aligned declared outer-envelope box intersection at wing90deg.'})
            bottom=n['upper_keeper'][str(x)]['keeper_bottom_max_plus20_mm']
            bar=np.array([[x-9,121,bottom],[x+9,239,bottom+6]])
            keeper_checks.append({'post_center_xy_mm':[cx,cy],'relation_to_same_station_nominal_keeper_at_y180':box_relation(box,bar),
                                  'scope':'Nominal18x118x6 keeper only; complete moved CAD group/bridges/endstops not tested.'})
    n['old_gse_geometry_status']='SUPERSEDED_BY_OFFSET_POSITIVE_COLUMNS; original counterexamples retained'
    n['gse_column_revision_v2']={'status':'CURRENT_DECLARED_POST_LAYOUT_PARTIAL_CHECK',
        'columns':columns,'nominal_keeper_end_state_post_checks':keeper_checks,'wing90_counterexamples':wing_hits,
        'suspension_attachment_y_mm':[78,322],'moving_group_y_end_envelopes_mm':{'closed':[92,128],'open':[272,308]},
        'offset_x_bridge':'rail_center_z+40; full dimensions and CAD pair checks pending',
        'low_dogleg_bridge':'X55; below shoe55; full dimensions and CAD pair checks pending',
        'upper_cantilever_to_front_stop_status':'Boundary contact reported by owner; needs final CAD measurement',
        'scope':'Post-only proxy separation does not certify the complete fixture or withdrawal path.'}
    n['status']='SAMPLED_ARM_CLEARANCE__GSE_POSTS_REVISED__COMPLETE_FIXED_HARDWARE_CHECK_PENDING'
    apply_final_receipt_geometry(data)
    data['source_hashes'][str(Path(__file__))]=sha(__file__)

def apply_final_receipt_geometry(data):
    receipt_path=HERE/'results/released_build_receipt.json'
    if not receipt_path.exists():return
    receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
    cols=[r for r in receipt['parts'] if '_tower_' in r['instance'].lower() and '_foot_' not in r['instance'].lower()]
    wing_hits=[]
    for col in cols:
        box=np.array([col['min_mm'],col['max_mm']])
        for side in [-1,1]:
            ylo,yhi=(-320.15,-125.15) if side<0 else (125.15,320.15)
            wing=np.array([[-160,ylo,-108.15],[160,yhi,-103.15]])
            relation=box_relation(box,wing)
            if relation['relation']!='STRICTLY_SEPARATED':
                dimensions=np.maximum(0,np.minimum(box[1],wing[1])-np.maximum(box[0],wing[0]))
                wing_hits.append({'column':col['instance'],'column_box_from_final_receipt_mm':box.tolist(),'wing_side':side,
                                  'outer_envelope_overlap_dimensions_mm':dimensions.tolist(),'outer_envelope_overlap_mm3':float(np.prod(dimensions)),
                                  'actual_material_common_volume_mm3':None})
    latest={'receipt_path':str(receipt_path),'receipt_sha256':sha(receipt_path),'columns':cols,'column_count':len(cols),
            'wing90_column_envelope_counterexamples':wing_hits,
            'scope':'Current coordinates come from final part receipt; former six-column and old same-X layouts remain historical only.'}
    fixed_path=HERE/'results/FIXED_GSE_ARM_PATH.json'
    if fixed_path.exists():
        fixed=json.loads(fixed_path.read_text(encoding='utf-8'))
        latest['fixed_gse_arm_check']={key:fixed[key] for key in ['status','fixed_fixture_count','total_sample_link_fixture_pairs','strict_aabb_separation_count','triangle_clip_pair_count','surface_hit_count','contains_status','continuous_rotating_path_status']}
        latest['fixed_gse_arm_check']['receipt_sha256']=sha(fixed_path)
        latest['fixed_gse_arm_check']['released_receipt_source']=fixed.get('released_receipt_source')
        latest['fixed_gse_arm_check']['released_receipt_is_embedded_snapshot']=fixed.get('released_receipt_is_embedded_snapshot',False)
    key_path=HERE/'results/KEY_GEOMETRY_CHECK.json'
    if key_path.exists():
        key=json.loads(key_path.read_text(encoding='utf-8'))
        latest['key_geometry_check']={'source_changed_during_run':key.get('source_changed_during_run'),
            'sample_Y_mm':[s['Y_mm'] for s in key.get('sampled_cross_fixed_moving',[])],
            'positive_volume_pairs_by_Y':[len(s['positive_volume_intersections']) for s in key.get('sampled_cross_fixed_moving',[])],
            'released_noncontext_solid_count':key.get('released_solid_validation',{}).get('solid_count'),
            'held_noncontext_solid_count':key.get('held_solid_validation',{}).get('solid_count'),
            'receipt_sha256':sha(key_path)}
    data['revised_candidate']['final_receipt_geometry']=latest
    data['revised_candidate']['gse_column_revision_v2']['status']='SUPERSEDED_SIX_COLUMN_HISTORY'
    data['revised_candidate']['status']='SAMPLED_CHECKS_RECORDED_CURRENT_SHARED_GSE__CONTINUOUS_AND_CONTAINMENT_UNKNOWN'

if __name__=='__main__':
    if '--refresh-gse' in sys.argv:
        data=json.loads((HERE/'results/MOTION_ANALYSIS.json').read_text(encoding='utf-8'))
        apply_gse_column_revision(data)
        (HERE/'results/MOTION_ANALYSIS.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        write_report(data)
        print(json.dumps({'current_gse_wing90_counterexamples':len(data['revised_candidate']['final_receipt_geometry']['wing90_column_envelope_counterexamples'])}))
    elif '--revise-candidate' in sys.argv:
        data=json.loads((HERE/'results/MOTION_ANALYSIS.json').read_text(encoding='utf-8'))
        supplied=json.load(sys.stdin); raw,_=read_triangles();parked=transform_meshes(raw,Q0)
        add_revised_candidate(data,raw,parked,supplied)
        (HERE/'results/MOTION_ANALYSIS.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        write_report(data)
        print(json.dumps({'revision':data['revised_candidate']['status'],'keeper_column_counterexamples':len(data['revised_candidate']['keeper_positive155_post_counterexamples']),
                          'wing_column_counterexamples':len(data['revised_candidate']['wing90_column_counterexamples'])}))
    else:main()
