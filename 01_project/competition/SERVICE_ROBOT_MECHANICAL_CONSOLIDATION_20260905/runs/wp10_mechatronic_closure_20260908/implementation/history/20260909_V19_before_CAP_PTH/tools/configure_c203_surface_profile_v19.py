"""Bind actual PCB copper/mask patterns to a mechanical seating datum."""
from pathlib import Path
import json,hashlib,shutil,math,sys
from erc_source_contract import parse,children,val,properties
from c203_surface_source_contract_v19 import validate_profile
A=Path(__file__).resolve().parents[1]
H=A/'history/20260909_V19_before_surface_profile'
def sha(p):return hashlib.sha256((A/p).read_bytes()).hexdigest()
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def dump(p,v):(A/p).write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding='utf-8')
def xy(n):return [float(v) for v in children(n,'at')[0][1:3]]
def main():
 refresh=sys.argv[1:]==['--refresh-after-normalize']
 assert refresh or not H.exists(),'Use --refresh-after-normalize for a source-equivalent refresh'
 names=['mechanical/input_cap_mount_common.py','mechanical/input_cap_pcb.step.py','mechanical/input_cap_pcb.step','mechanical/INPUT_CAP_MOUNT_DESIGN.json','power/CAP_TERMINAL_DEFINITION.json','power/CAP_HARNESS_DEFINITION_V19.json','mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json','tools/define_cap_harness_v19.py','tools/check_cap_harness_path_v19.py','tools/prepare_cap_harness_plan_v19.py','mechanical/cap_harness_plus.step','mechanical/cap_harness_minus.step','results/CAP_HARNESS_PATH_V19.json','power/CAP_HARNESS_ELECTROTHERMAL_V19.json','thermal/ACTIVE_HEAT_LOADS_V19.json','results/CAP_HARNESS_WORKING_STATUS_V19.json']
 if not refresh:
  for p in names:
   target=H/p;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(A/p,target)
  dump(H.relative_to(A).as_posix()+'/ARCHIVE_SHA256.json',{p:sha(p) for p in names})
 d=read('power/CAP_TERMINAL_DEFINITION.json');m=read('mechanical/INPUT_CAP_MOUNT_DESIGN.json')
 tree=parse((A/d['board']).read_text());stack=children(children(tree,'setup')[0],'stackup')[0]
 layers={val(q[1]):float(children(q,'thickness')[0][1]) for q in children(stack,'layer') if children(q,'thickness')}
 assert layers==d['native_stackup_mm']=={'F.Mask':.01,'F.Cu':.07,'dielectric 1':1.43,'B.Cu':.07,'B.Mask':.02}
 datum=m['body_face_S_mm'][0];assert datum==-7
 cf=datum+layers['F.Mask'];cb=cf+layers['dielectric 1']
 faces=dict(component_seating_x=datum,front_exposed_copper_x=cf-layers['F.Cu'],front_nominal_mask_on_copper_x=cf-layers['F.Cu']-layers['F.Mask'],core_front_x=cf,core_back_x=cb,rear_exposed_copper_x=cb+layers['B.Cu'],rear_mask_on_copper_x=cb+layers['B.Cu']+layers['B.Mask'],rear_no_copper_bearing_x=cb+layers['B.Mask'])
 pads=[];holes=[];origin=d['pcb_origin_xy_mm']
 for fp in children(tree,'footprint'):
  pos=xy(fp);rotation=children(fp,'at')[0][3:];assert not rotation or float(rotation[0])==0
  for p in children(fp,'pad'):
   local=[xy(p)[i]+pos[i]-origin[i] for i in [0,1]]
   size=[float(v) for v in children(p,'size')[0][1:3]];assert p[3]=='circle' and size[0]==size[1]
   layernames=[val(x) for x in children(p,'layers')[0][1:]]
   record=dict(ref=properties(fp)['Reference'],pin=val(p[1]),type=p[2],local_xy_mm=local,diameter_mm=size[0],layers=layernames)
   drill=children(p,'drill')
   if drill:
    assert len(drill[0])==2;record['finished_drill_mm']=float(drill[0][1]);holes.append(dict(local_xy_mm=local,finished_drill_mm=record['finished_drill_mm'],type=p[2]))
   pads.append(record)
 assert len(holes)==8 and sum(h['type']=='thru_hole' for h in holes)==2
 tracks=[]
 for t in children(tree,'segment'):
  assert val(children(t,'layer')[0][1])=='B.Cu'
  tracks.append(dict(start_local_mm=[float(q)-origin[i] for i,q in enumerate(children(t,'start')[0][1:3])],end_local_mm=[float(q)-origin[i] for i,q in enumerate(children(t,'end')[0][1:3])],width_mm=float(children(t,'width')[0][1])))
 assert len(tracks)==6 and not children(tree,'zone')
 # Aperture dilation is not qualified; nominal openings follow native pad sizes.
 profile=dict(schema='WP10_C203_LOCAL_SURFACE_PROFILE_V19',status='NOMINAL_SOURCE_PROFILE__CAD_REGEN_AND_TOLERANCE_PENDING',frame='S_mm',pcb_to_S='Y_S=Xpcb-local; Z_S=-50-Ypcb-local; thickness along +X_S',
  datum_basis='Project-selected no-copper masked FR4 bearing plane at unchanged CAP and carrier face X=-7',layers_mm=layers,faces_S_mm=faces,
  board_y_mm=m['board_y_mm'],board_z_mm=m['board_z_mm'],nominal_full_stack_x_mm=[faces['front_nominal_mask_on_copper_x'],faces['rear_mask_on_copper_x']],
  pads=pads,holes=holes,back_tracks=tracks,mount_holes_yz_mm=m['board_holes_yz_mm'],screw_underhead_x_mm=faces['rear_no_copper_bearing_x'],screw_tip_x_mm=faces['rear_no_copper_bearing_x']-8,
  carrier_nominal_blind_bore_bottom_x_mm=-13.9,nominal_bore_bottom_gap_mm=faces['rear_no_copper_bearing_x']-8-(-13.9),
  mask_model='Piecewise conformal nominal film on copper or core; no planarization assumed. Nominal pad apertures; mask registration, flow and vertical step coating unqualified.',
  PTH_barrel_geometry='Not resolved: mechanical voids use finished-hole diameter; this surface model is not a laminate/preplate drill or copper-mass model.',
  contact_qualification='Nominal surface positions only; flatness, tolerance, solder shape, real sealing rubber and preload are not qualified.',whole_contact_verified=False,whole_design_complete=False,
  inputs={p:sha(p) for p in [d['board'],'tools/configure_c203_surface_profile_v19.py','tools/c203_surface_source_contract_v19.py']})
 validate_profile(profile)
 if refresh:
  previous=read('mechanical/C203_SURFACE_PROFILE_V19.json')
  assert {k:v for k,v in previous.items() if k!='inputs'}=={k:v for k,v in profile.items() if k!='inputs'},'Physical profile changed: explicit redesign needed'
 dump('mechanical/C203_SURFACE_PROFILE_V19.json',profile)
 d.update(surface_profile='mechanical/C203_SURFACE_PROFILE_V19.json',mechanical_frame='S_mm; Xpcb->+Ys, Ypcb->-Zs; no-copper masked-core seating datum Xs=-7; exposed terminal faces separately derived',surface_profile_native_verified=False)
 for t in d['terminal_features']:
  t['solder_exit_S_x_mm']=faces['rear_exposed_copper_x']
  t['entry_face_kind']='EXPOSED_FRONT_COPPER' if t['id'].startswith('WIRE_') else 'NO_COPPER_COMPONENT_SEATING'
  t['S_face_mm'][0]=faces['front_exposed_copper_x'] if t['id'].startswith('WIRE_') else datum
 dump('power/CAP_TERMINAL_DEFINITION.json',d)
 m.update(board_x_mm=profile['nominal_full_stack_x_mm'],board_component_bearing_x_mm=datum,board_screw_bearing_x_mm=faces['rear_no_copper_bearing_x'],board_surface_profile='mechanical/C203_SURFACE_PROFILE_V19.json',board_contact_profile_verified=False)
 m['source_files']['power/CAP_TERMINAL_DEFINITION.json']=sha('power/CAP_TERMINAL_DEFINITION.json')
 dump('mechanical/INPUT_CAP_MOUNT_DESIGN.json',m)
 dump('results/C203_SURFACE_REBUILD_REQUIRED_V19.json',dict(status='ACTIVE_MECHANICAL_SOURCES_CHANGED__OLD_STEP_AND_PLAN_NOT_CURRENT',source_profile='mechanical/C203_SURFACE_PROFILE_V19.json',source_profile_sha256=sha('mechanical/C203_SURFACE_PROFILE_V19.json'),required_geometry_regeneration=['mechanical/input_cap_pcb.step','mechanical/cap_harness_plus.step','mechanical/cap_harness_minus.step','mechanical/cap_harness_assembly.step'],required_instance_changes=['C203_PCB','four_C203_PCB_screw_translations'],old_generated_plan='mechanical/CAP_HARNESS_INSTANCE_PLAN_V19.json',old_generated_plan_current=False,native_geometry_generated=False,whole_design_complete=False))
 print(json.dumps(dict(profile=faces,screw_bottom_gap=profile['nominal_bore_bottom_gap_mm'],CAD_generated=False)))
if __name__=='__main__':main()
