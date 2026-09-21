"""Actual STEP faces, hole axes, thread reach and isolated cold-path contacts."""
from pathlib import Path
import json,hashlib,runpy,math
from OCP.gp import gp_Trsf
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
A=Path(__file__).resolve().parents[1];core=runpy.run_path(str(A/'tools/check_fixed_heat_geometry.py'))
read=core['read'];prop=core['prop'];common=core['common'];parts=core['parts'];fy=core['faces_y'];fz=core['faces_z']
p=json.loads((A/'thermal/BOTTOM_RADIATOR_MOUNT.json').read_text());c=p['chb_path'];plan=json.loads((A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json').read_text());rows={r['id']:r for r in plan['states']['service']['rows']}
def shape(key):
    r=rows[key];path=Path(r['step_path']);assert hashlib.sha256(path.read_bytes()).hexdigest()==r['source_sha256']
    M=r['T_S_step'];t=gp_Trsf();t.SetValues(*[float(M[i][j]) for i in range(3) for j in range(4)])
    return BRepBuilderAPI_Transform(read(path),t,True).Shape()
def contact(a,b,value,axis):
    fn=fy if axis=='y' else fz
    return sum(common(x,y,False) for x in fn(a,value) for y in fn(b,value))
checks=[]
def ck(n,v,**kw):checks.append(dict(name=n,passed=bool(v),**kw))
plate=shape('radiator_spreader');device=shape('U202_CHB');tim=shape('U202_CHB_TIM');joints=[]
ck('monolithic_bottom_and_two_fingers_one_solid',len(parts(plate))==1)
ck('CHB_ECAD_ref_bound_to_U203_not_legacy_CAD_alias',rows['U202_CHB']['ecad_ref']=='U203')
for side in [-1,1]:
    wall=shape(f'shear_web_{side}');pad=shape(f'WP10_COLD_{side}_TIM');inner=side*(c['wall_seat_abs_y_mm']-c['wall_TIM_thickness_mm']);outer=side*c['wall_seat_abs_y_mm']
    ap=contact(plate,pad,inner,'y');aw=contact(wall,pad,outer,'y');expected=58*24-2*math.pi*(4.5/2)**2
    ck(f'wall_{side}_TIM_both_actual_faces',abs(ap-expected)<1e-4 and abs(aw-expected)<1e-4,plate_pad_mm2=ap,wall_pad_mm2=aw,expected_mm2=expected)
    ck(f'wall_{side}_solid_bodies_not_interpenetrating',common(plate,wall)<1e-5)
    for i,(x,z) in enumerate(c['wall_screw_centers_xz_mm']):
        screw=shape(f'WP10_COLD_{side}_{i}_SCREW');bb=prop(screw)['bbox'];tip=bb[1] if side==1 else -bb[4]
        reach=c['wall_seat_abs_y_mm']-c['wall_TIM_thickness_mm']-tip
        expected_reach=c['wall_seat_abs_y_mm']-c['wall_TIM_thickness_mm']-(113.15-c['wall_screw_inclusive_length_mm'])
        ck(f'wall_{side}_{i}_screw_nominal_insertion',abs(reach-expected_reach)<1e-5 and reach<c['finger_thread_nominal_depth_mm'],value_mm=reach)
        ck(f'wall_{side}_{i}_screw_nonpenetration',common(screw,plate)<1e-5 and common(screw,wall)<1e-5 and common(screw,pad)<1e-5)
    joints.append(dict(side=side,contact_area_mm2=ap,through_wall_m=(113.15-c['wall_seat_abs_y_mm'])/1000,TIM_typical_25psi_R_K_W=c.get('TIM_impedance_C_in2_W_at25psi',.75)*25.4**2/ap))
for i in range(4):
    screw=shape(f'WP10_CHB_{i}_SCREW');bb=prop(screw)['bbox'];reach=bb[5]-c['oem_base_z_mm']
    ck(f'CHB_{i}_screw_nominal_insertion',abs(reach-2)<1e-5,value_mm=reach)
    ck(f'CHB_{i}_screw_nonpenetration',common(screw,device)<1e-5 and common(screw,tim)<1e-5 and common(screw,plate)<1e-5)
ac=contact(plate,tim,c['seat_z_mm'],'z');ad=contact(device,tim,c['oem_base_z_mm'],'z')
ck('CHB_pad_both_actual_faces',abs(ac-3234.4827487648063)<1e-4 and abs(ad-ac)<1e-4,area_mm2=ac)
ck('CHB_bbox_manufacturer_full_height18',abs(prop(device)['bbox'][5]-prop(device)['bbox'][2]-18)<1e-5)
selected=['radiator_spreader','lower_equipment_deck_B','shear_web_-1','shear_web_1','U202_CHB','U202_CHB_TIM']+[k for k in rows if k.startswith('WP10_CHB_') or k.startswith('WP10_COLD_')]
out=dict(schema='WP10_COLD_PATH_ACTUAL_GEOMETRY_V1',source_plan_sha256=hashlib.sha256((A/'mechanical/FIXED_HEAT_INSTANCE_PLAN.json').read_bytes()).hexdigest(),config_sha256=hashlib.sha256((A/'thermal/BOTTOM_RADIATOR_MOUNT.json').read_bytes()).hexdigest(),source_steps={k:dict(path=rows[k]['step_path'],sha256=rows[k]['source_sha256'],T_S_step=rows[k]['T_S_step']) for k in selected},checks=checks,checks_passed=all(r['passed'] for r in checks),check_count=len(checks),wall_joints=joints,CHB_TIM_contact_mm2=ac,CHB_nominal_metal_path_mm=c['seat_z_mm']-p['outer_z_mm'],same_candidate_real_GEOMETRIC_thermal_connection=True,thermal_resistance_verified=False,thread_effective_engagement_verified=False,preload_structural_and_orbit_verified=False)
(A/'results/COLD_PATH_GEOMETRY.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(dict(checks=checks,passed=out['checks_passed']),indent=2));assert out['checks_passed']
