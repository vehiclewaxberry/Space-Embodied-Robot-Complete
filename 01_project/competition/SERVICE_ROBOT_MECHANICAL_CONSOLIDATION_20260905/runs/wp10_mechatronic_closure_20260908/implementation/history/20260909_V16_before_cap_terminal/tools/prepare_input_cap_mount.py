"""Create parameterized C203 installation candidate and extend the same source plan."""
from pathlib import Path
import json,hashlib,copy,argparse
import numpy as np
A=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads((A/p).read_text(encoding='utf-8-sig'))
def dump(p,v):(A/p).write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding='utf-8')
p=argparse.ArgumentParser();p.add_argument('--phase',choices=['design','plan'],required=True);args=p.parse_args()
names=['BODY','PCB','CARRIER','LOWER_A','LOWER_B','LINER_A_TOP','LINER_A_BOTTOM','LINER_B_TOP','LINER_B_BOTTOM','DECK','SCREW_12','SCREW_10','SCREW_8','WASHER','NUT']
if args.phase=='design':
 parent='mechanical/ROOT_BUSHING_INSTANCE_PLAN.json';plan=read(parent)
 deck=next(r for r in plan['states']['service']['rows'] if r['id']=='upper_equipment_deck_B')
 c=dict(schema='WP10_C203_HORIZONTAL_MOUNT_V1',parent_plan=parent,parent_plan_sha256=sha(A/parent),deck_source=deck,
  frame='S_mm',electrical_ref='C203',MPN='ELXG101VSN222MR50S',body_face_S_mm=[-7,0,-50],axis_S=[-1,0,0],nominal_D_L_mm=[30,50],maximum_D_L_mm=[31,52],
  cap_local_to_S=[ [0,0,-1,-7],[1,0,0,0],[0,-1,0,-50],[0,0,0,1] ],
  board_x_mm=[-7,-5.4],board_y_mm=[-25,25],board_z_mm=[-74,-26],board_holes_yz_mm=[[y,z] for y in [-20,20] for z in [-69,-31]],board_hole_D_mm=3.4,
  pads=[dict(number='1',polarity='PLUS',local_xy_mm=[-5,0],S_face_mm=[-7,-5,-50]),dict(number='2',polarity='MINUS',local_xy_mm=[5,0],S_face_mm=[-7,5,-50])],pad_drill_D_mm=2,
  OEM_lead_projection_mm=[3.5,4.5],vent_clearance_mm=3,band_centers_x_mm=[-48,-20],band_width_mm=6,clamp_ID_OD_mm=[31,37],nominal_liner_thickness_mm=.5,
  deck_holes_xy_mm=[[x,y] for x in [-48,-20] for y in [-32.5,32.5]],clamp_holes_xy_mm=[[x,y] for x in [-48,-20] for y in [-22.5,22.5]],deck_hole_D_mm=3.4,deck_z_mm=[-11.5,-8.5],flange_z_mm=[-15.5,-11.5],flange_y_mm=[-37.5,37.5],
  fastener_geometry=dict(screw_D_mm=3,head_D_mm=5.5,head_H_mm=3,washer_ID_OD_T_mm=[3.2,7,.5],nut_across_flats_H_mm=[5.5,2.4],thread='major-diameter envelope only; catalogue grade, thread form, torque and locking open'),
  materials=dict(carrier_and_liners='Unfilled PEEK candidate; finished stock, creep, outgassing, clamp pressure and allowable force unqualified',pcb='1.6mm insulating laminate geometry; stackup, copper and process not released'),
  source_files={q:sha(A/q) for q in ['sources/lxg_2026.pdf','sources/chemi_al_precautions_2026.pdf','ecad/WP10_PASSIVES.pretty/CP_ChemiCon_VS_D30_P10_2mm_Candidate.kicad_mod']},
  native_footprint='WP10_PASSIVES:CP_ChemiCon_VS_D30_P10_2mm_Candidate',assembly_sequence=['Machine four deck holes in candidate source only','Mount upper carrier to deck with four through bolts/washer/nuts','Fit capacitor flush to terminal board and lower into lined cradle before closing two lower bands','Install board and clamp screws; actual tightening and soldering require qualified process'],
  thermal_neighbor_exception_open=True,axial_retention_qualified=False,terminal_connection_to_CHB_complete=False,whole_design_complete=False)
 dump('mechanical/INPUT_CAP_MOUNT_DESIGN.json',c)
 for n in names:(A/f'mechanical/input_cap_{n.lower()}.step.py').write_text('from input_cap_mount_common import make\n\ndef gen_step():return make('+repr(n)+')\n',encoding='utf-8')
 print(json.dumps(dict(design=True,source_targets=len(names))))
else:
 c=read('mechanical/INPUT_CAP_MOUNT_DESIGN.json');assert sha(A/c['parent_plan'])==c['parent_plan_sha256'];parent=read(c['parent_plan']);states={}
 def tr(x=0,y=0,z=0):T=np.eye(4);T[:3,3]=[x,y,z];return T.tolist()
 for state,p in parent['states'].items():
  rows={r['id']:copy.deepcopy(r) for r in p['rows']};added=[];changed=[]
  def put(k,n,T=None):
   new=k not in rows;r=rows.get(k,dict(id=k,is_ground_only=False,predecessor_ids=[]));path=A/f'mechanical/input_cap_{n.lower()}.step'
   r.update(step_path=str(path),source_sha256=sha(path),T_S_step=T or tr(),representation_role='C203_NOMINAL_INSTALLATION_CANDIDATE__THERMAL_RETENTION_AND_WIRING_OPEN',mass_inertia_requalification='NOT_REQUALIFIED',native_geometry_current=False)
   rows[k]=r;(added if new else changed).append(k)
  put('upper_equipment_deck_B','DECK')
  for n in names[:9]:put('C203_'+n,n)
  for i,(x,y) in enumerate(c['deck_holes_xy_mm']):
   put(f'C203_DECK_SCREW_{i}','SCREW_12',tr(x,y,-15.5));put(f'C203_DECK_WASHER_{i}','WASHER',tr(x,y,-8.5));put(f'C203_DECK_NUT_{i}','NUT',tr(x,y,-8))
  for i,(x,y) in enumerate(c['clamp_holes_xy_mm']):put(f'C203_CLAMP_SCREW_{i}','SCREW_10',tr(x,y,-54))
  for i,(y,z) in enumerate(c['board_holes_yz_mm']):
   T=[[0,0,-1,-5.4],[1,0,0,y],[0,-1,0,z],[0,0,0,1]];put(f'C203_BOARD_SCREW_{i}','SCREW_8',T)
  assert len(added)==29 and len(rows)==965 and changed==['upper_equipment_deck_B']
  assert all(rows[r['id']]==r for r in p['rows'] if r['id']!='upper_equipment_deck_B')
  states[state]=dict(rows=list(rows.values()),changed_ids=changed,added_ids=added)
 out=dict(schema='WP10_C203_MOUNT_SOURCE_VARIANT_V1',inputs={q:sha(A/q) for q in [c['parent_plan'],'mechanical/INPUT_CAP_MOUNT_DESIGN.json','mechanical/input_cap_mount_common.py','tools/prepare_input_cap_mount.py']},states=states,component_count=965,component_count_identity='936 retained IDs including one revised deck, plus29 C203 installation candidate IDs; capacitor is body envelope only',whole_fit_verified=False,thermal_mass_native_requalified=False,whole_design_complete=False)
 dump('mechanical/INPUT_CAP_MOUNT_INSTANCE_PLAN.json',out);print(json.dumps(dict(source_instances=965,added=29,modified=1)))
