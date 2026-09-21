"""Nominal surface/placement checks and counterexamples without CAD imports."""
from pathlib import Path
import sys,json,hashlib,math,copy,ast
A=Path(__file__).resolve().parents[1];sys.path.insert(0,str(A/'mechanical'))
from c203_pcb_surface_profile import definition,surface_at,copper_at,on_layer,distance_segment
from c203_surface_source_contract_v19 import validate_profile
from prepare_cap_harness_plan_v19 import validate_plan
def read(p):return json.loads((A/p).read_text())
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def close(a,b):return abs(a-b)<1e-9
def copper_gap(c,side,center,radius):
 gaps=[math.dist(center,p['local_xy_mm'])-p['diameter_mm']/2-radius for p in c['pads'] if p['pin'] and on_layer(p,side+'.Cu')]
 if side=='B':gaps += [distance_segment(center,t['start_local_mm'],t['end_local_mm'])-t['width_mm']/2-radius for t in c['back_tracks']]
 return min(gaps) if gaps else float('inf')
def evaluate(c,d,m,p,w):
 validate_profile(c)
 validate_plan(p,require_generated=not p.get('surface_profile_pending',False))
 checks=[];f=c['faces_S_mm'];l=c['layers_mm']
 def ck(name,value,**kw):checks.append(dict(name=name,passed=bool(value),**kw))
 ck('stackup_total_1p6',close(sum(l.values()),1.6))
 expected={'component_seating_x':-7,'core_front_x':-7+l['F.Mask'],'core_back_x':-7+l['F.Mask']+l['dielectric 1']}
 expected.update(front_exposed_copper_x=expected['core_front_x']-l['F.Cu'],front_nominal_mask_on_copper_x=expected['core_front_x']-l['F.Cu']-l['F.Mask'],rear_exposed_copper_x=expected['core_back_x']+l['B.Cu'],rear_mask_on_copper_x=expected['core_back_x']+l['B.Cu']+l['B.Mask'],rear_no_copper_bearing_x=expected['core_back_x']+l['B.Mask'])
 ck('all_faces_derived_from_actual_layer_definition',set(f)==set(expected) and all(close(f[k],v) for k,v in expected.items()))
 ck('CAP_seating_datum_preserved',close(m['body_face_S_mm'][0],f['component_seating_x']) and close(m['board_component_bearing_x_mm'],f['component_seating_x']))
 front=[q for q in c['pads'] if q['pin'] and on_layer(q,'F.Cu')]
 ck('all_front_copper_clear_of_max_CAP_projection',len(front)==2 and all(math.hypot(*q['local_xy_mm'])-q['diameter_mm']/2>=15.5+2 for q in front))
 ck('all_front_copper_inside_frame_window',all(max(map(abs,q['local_xy_mm']))+q['diameter_mm']/2<16.5 for q in front))
 ck('masked_CAP_seating_sample',close(surface_at(c,'F',[0,0]),-7))
 for x in [-5,5]:
  ck('CAP_'+str(x)+'_actual_CAM_open_front_annulus',close(surface_at(c,'F',[x+1.3,0]),f['core_front_x']) and not copper_at(c,'F.Cu',[x+1.3,0]) and close(surface_at(c,'B',[x+1.3,0]),f['rear_exposed_copper_x']))
 for i,(y,z) in enumerate(c['mount_holes_yz_mm']):
  center=[y,-50-z];gaps={s:copper_gap(c,s,center,2.75) for s in ['F','B']}
  disk_in_board=c['board_y_mm'][0]<=y-2.75 and y+2.75<=c['board_y_mm'][1] and c['board_z_mm'][0]<=z-2.75 and z+2.75<=c['board_z_mm'][1]
  holes_clear=all(math.dist(center,h['local_xy_mm'])>=2.75+h['finished_drill_mm']/2 for h in c['holes'] if math.dist(center,h['local_xy_mm'])>1e-9)
  ck(f'mount{i}_whole_bearing_disk_inside_board_no_other_holes',disk_in_board and holes_clear)
  # Full head disk has no copper, not merely a few samples. Own drilled hole is excluded from bearing annulus.
  ck(f'mount{i}_whole_head_disk_has_no_copper',all(v>0 for v in gaps.values()),gap_mm=gaps)
  q=[center[0]+2.1,center[1]]
  ck(f'mount{i}_nominal_front_rear_bearing_faces',close(surface_at(c,'F',q),-7) and close(surface_at(c,'B',q),c['screw_underhead_x_mm']))
  for state,st in p['states'].items():
   screw=next(r for r in st['rows'] if r['id']==f'C203_BOARD_SCREW_{i}')
   ck(f'{state}_mount{i}_head_position',close(screw['T_S_step'][0][3],f['rear_no_copper_bearing_x']) and screw['T_S_step'][1][3]==y and screw['T_S_step'][2][3]==z and [screw['T_S_step'][j][2] for j in range(3)]==[-1,0,0])
 ck('blind_bore_bottom_gap_0p36_not_thread_qualification',close(c['screw_tip_x_mm'],c['screw_underhead_x_mm']-8) and close(c['screw_tip_x_mm']-c['carrier_nominal_blind_bore_bottom_x_mm'],.36))
 ck('bearing_clamp_thickness_1p46',close(c['screw_underhead_x_mm']-f['component_seating_x'],1.46))
 for term in d['terminal_features']:
  if term['id'].startswith('WIRE_'):
   q=[term['local_xy_mm'][0]+1.3,term['local_xy_mm'][1]]
   ck(term['id']+'_copper_faces_at_actual_annulus',close(surface_at(c,'F',q),term['S_face_mm'][0]) and close(surface_at(c,'B',q),term['solder_exit_S_x_mm']))
   wire=next(x for x in w['wires'] if x['from_feature']=='C203_PCB.'+term['id'])
   setback=term['S_face_mm'][0]-wire['insulation_start_S_mm'][0]
   ck(term['id']+'_strip_and_projection_from_exposed_copper',setback>=1 and close(wire['sharp_vertices_S_mm'][0][0]-term['solder_exit_S_x_mm'],wire['C203_solder_projection_mm']) and close(wire['strip_start_mm'],4.2),setback_mm=setback,projection_mm=wire['C203_solder_projection_mm'])
 ck('STEP_status_consistent_with_source_bound_generation',validate_plan(p,require_generated=not p['surface_profile_pending']))
 ck('outside_board_has_no_material_surface',surface_at(c,'F',[1000,1000]) is None and surface_at(c,'B',[1000,1000]) is None)
 return dict(passed=all(x['passed'] for x in checks),checks=checks)
def main():
 c=definition();d=read('power/CAP_TERMINAL_DEFINITION.json');m=read('mechanical/INPUT_CAP_MOUNT_DESIGN.json');p=read('mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json');w=read('power/CAP_HARNESS_DEFINITION_V19.json')
 result=evaluate(c,d,m,p,w);assert result['passed'],[q for q in result['checks'] if not q['passed']]
 faults=[]
 def reject(name,mutate):
  vals=copy.deepcopy([c,d,m,p,w]);mutate(*vals)
  try:bad=evaluate(*vals);rejected=not bad['passed'];reasons=[q['name'] for q in bad['checks'] if not q['passed']]
  except (AssertionError,KeyError,StopIteration,TypeError,FileNotFoundError) as e:rejected=True;reasons=[str(e)]
  assert rejected,name;faults.append(dict(name=name,rejected=True,reasons=reasons))
 reject('front_seating_shifted_70um',lambda c,d,m,p,w:c['faces_S_mm'].update(component_seating_x=-6.93))
 reject('old_screw_head_position_retained',lambda c,d,m,p,w:next(r for r in p['states']['service']['rows'] if r['id']=='C203_BOARD_SCREW_0')['T_S_step'][0].__setitem__(3,-5.4))
 reject('back_solder_face_from_uniform_thickness',lambda c,d,m,p,w:d['terminal_features'][2].update(solder_exit_S_x_mm=d['terminal_features'][2]['S_face_mm'][0]+1.6))
 reject('old_insulation_setback_0p94',lambda c,d,m,p,w:w['wires'][0].update(insulation_start_S_mm=[-8,-14,-64],strip_start_mm=4.1))
 reject('front_copper_added_under_CAP',lambda c,d,m,p,w:c['pads'].append(dict(pin='1',local_xy_mm=[0,0],diameter_mm=3.5,layers=['F.Cu'])))
 reject('screw_longer_than_blind_bore',lambda c,d,m,p,w:c.update(screw_tip_x_mm=-14.1))
 reject('contradictory_plan_generation_state',lambda c,d,m,p,w:p.update(surface_profile_pending=not p['surface_profile_pending'],source_geometry_fresh=not p['source_geometry_fresh']))
 reject('back_track_width_4_to_0p1',lambda c,d,m,p,w:c['back_tracks'][0].update(width_mm=.1))
 reject('CAP_hole_2_to_0p2',lambda c,d,m,p,w:next(h for h in c['holes'] if h['finished_drill_mm']==2).update(finished_drill_mm=.2))
 reject('board_width_reduced_to_4',lambda c,d,m,p,w:c.update(board_y_mm=[-2,2]))
 reject('PCB_translated_1mm',lambda c,d,m,p,w:next(r for r in p['states']['service']['rows'] if r['id']=='C203_PCB')['T_S_step'][0].__setitem__(3,1))
 reject('BODY_translated_1mm',lambda c,d,m,p,w:next(r for r in p['states']['service']['rows'] if r['id']=='C203_BODY')['T_S_step'][0].__setitem__(3,1))
 def wrong_screw(c,d,m,p,w):
  q='mechanical/input_cap_screw_12.step'
  next(r for r in p['states']['service']['rows'] if r['id']=='C203_BOARD_SCREW_0').update(step_path=str(A/q),source_sha256=sha(q))
 reject('12mm_screw_with_real_file_hash',wrong_screw)
 def wrong_row_state(c,d,m,p,w):
  row=next(r for r in p['states']['service']['rows'] if r['id']=='C203_PCB');row['native_geometry_current']=not row['native_geometry_current']
 reject('contradictory_PCB_row_generation_state',wrong_row_state)
 for code in ['mechanical/c203_pcb_surface_profile.py','mechanical/input_cap_pcb.step.py','mechanical/input_cap_mount_common.py']:ast.parse((A/code).read_text())
 inputs=['mechanical/C203_SURFACE_PROFILE_V19.json','mechanical/c203_pcb_surface_profile.py','mechanical/input_cap_pcb.step.py','mechanical/input_cap_mount_common.py','mechanical/INPUT_CAP_MOUNT_DESIGN.json','mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json','power/CAP_TERMINAL_DEFINITION.json','power/CAP_HARNESS_DEFINITION_V19.json','tools/check_c203_surface_profile_v19.py','tools/c203_surface_source_contract_v19.py','tools/prepare_cap_harness_plan_v19.py','tools/c203_surface_generation_contract_v19.py','mechanical/CHB_INPUT_INSTANCE_PLAN.json']
 result.update(schema='WP10_C203_SURFACE_NOMINAL_CHECK_V19',faults=faults,inputs={q:sha(q) for q in inputs},nominal_geometry_only=True,actual_surface_profile_measured=False,native_CAD_generated=p['source_geometry_fresh'],native_CAD_checked_by_this_script=False,thread_engagement_qualified=False,whole_design_complete=False)
 (A/'results/C203_SURFACE_PROFILE_CHECK_V19.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
 print(json.dumps(dict(passed=True,checks=len(result['checks']),faults=len(faults),native_CAD_generated=p['source_geometry_fresh'],native_CAD_checked_by_this_script=False)))
if __name__=='__main__':main()
