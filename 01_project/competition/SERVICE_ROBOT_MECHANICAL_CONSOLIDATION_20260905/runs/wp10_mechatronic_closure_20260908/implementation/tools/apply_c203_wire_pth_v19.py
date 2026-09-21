"""Change only the two outboard wire terminations to real PTH in active sources.

Pure KiCad S-expression edits: does not start KiCad, OCP, COM or fabrication.
The native readback/DRC must be rerun before accepting this working revision.
"""
from pathlib import Path
import json,hashlib,copy,shutil,math,datetime
from erc_source_contract import parse,enc,children,val,properties
A=Path(__file__).resolve().parents[1]
H=A/'history/20260909_V19_before_wire_pth'
N='C203_SingleFace_Terminal_D30_P10_W18'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False),encoding='utf-8')
def xy(p):return tuple(float(x) for x in children(p,'at')[0][1:3])
TARGET={(-14.,14.):'1',(14.,14.):'2'}
def change_footprint(fp):
 before=copy.deepcopy(fp);changed=[]
 for coords,pin in TARGET.items():
  group=[p for p in children(fp,'pad') if xy(p)==coords]
  assert len(group)==2
  hole=next(p for p in group if p[2]=='np_thru_hole');pad=next(p for p in group if p[2]=='smd')
  assert val(pad[1])==pin and [float(x) for x in children(pad,'size')[0][1:]]==[3.5,3.5]
  assert children(hole,'drill')[0]==['drill','1.8']
  fp.remove(hole);pad[2]='thru_hole'
  pad.insert(5,['drill','1.8'])
  layers=children(pad,'layers')[0];layers[:]=['layers','"*.Cu"','"*.Mask"']
  changed.append(dict(local_xy_mm=list(coords),pin=pin,finished_hole_mm=1.8,front_and_back_land_mm=3.5,
   front_copper_to_max_body_mm=math.hypot(*coords)-15.5-1.75,front_copper_to_frame_window_mm=16.5-max(map(abs,coords))-1.75))
 # No change to either under-body capacitor termination.
 assert [p for p in children(before,'pad') if xy(p) not in TARGET]==[p for p in children(fp,'pad') if xy(p) not in TARGET]
 description=children(fp,'descr')[0]
 description[1]=json.dumps('Legacy footprint identifier retained. Two outboard WIRE pads are real PTH with F.Cu/B.Cu annuli; CAP pads remain B.Cu lands plus NPTH. No F.Cu copper beneath capacitor body. Native DRC and solder/CAM qualification pending.')
 return changed
def main():
 receipt=A/'results/C203_WIRE_PTH_SOURCE_CHANGE_V19.json'
 assert not receipt.exists() and not H.exists(),'Already edited; inspect existing working sources instead of replaying'
 paths=['ecad/wp10_c203_terminal.kicad_pcb',f'ecad/WP10_PASSIVES.pretty/{N}.kicad_mod',f'power/cap_terminal_sources/{N}.kicad_mod','power/CAP_TERMINAL_DEFINITION.json','mechanical/INPUT_CAP_MOUNT_DESIGN.json','mechanical/input_cap_pcb.step.py','tools/cap_terminal_native.py','tools/check_cap_terminal_copper.py','power/CAP_HARNESS_DEFINITION_V19.json','results/CAP_HARNESS_PATH_V19.json','power/CAP_HARNESS_ELECTROTHERMAL_V19.json','thermal/CAP_HARNESS_REFINED_HEAT_LOADS_V19.csv','thermal/ACTIVE_HEAT_LOADS_V19.json','results/CAP_HARNESS_READONLY_REVIEW_V19.json','results/CAP_HARNESS_HEAT_READONLY_REVIEW_V19.json','results/CAP_HARNESS_WORKING_STATUS_V19.json','docs/hardware/CAP_HARNESS_BRIEF_V19.md','tools/publish_cap_harness_v19.py','tools/record_cap_harness_review_v19.py','tools/record_cap_harness_heat_review_v19.py']
 for p in paths:
  dest=H/p;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(A/p,dest)
 dump(H/'ARCHIVE_SHA256.json',{p:sha(H/p) for p in paths})
 source_board=parse((A/paths[0]).read_text(encoding='utf-8'));original=copy.deepcopy(source_board)
 cap=next(f for f in children(source_board,'footprint') if properties(f).get('Reference')=='C203')
 changes=change_footprint(cap)
 for p in paths[1:3]:
  fp=parse((A/p).read_text(encoding='utf-8'));assert change_footprint(fp)==changes
  (A/p).write_text(enc(fp)+'\n',encoding='utf-8')
 stack=children(children(source_board,'setup')[0],'stackup')[0]
 for layer in children(stack,'layer'):
  if val(layer[1])=='F.Cu':children(layer,'thickness')[0][1]='0.07'
  elif val(layer[1])=='dielectric 1':children(layer,'thickness')[0][1]='1.43'
 actual={val(n[1]):float(children(n,'thickness')[0][1]) for n in children(stack,'layer') if children(n,'thickness')}
 assert actual=={'F.Mask':.01,'F.Cu':.07,'dielectric 1':1.43,'B.Cu':.07,'B.Mask':.02} and abs(sum(actual.values())-1.6)<1e-12
 for tag in ['segment','arc','zone','net','general','gr_line']:
  assert children(source_board,tag)==children(original,tag),'Unrelated '+tag
 (A/paths[0]).write_text(enc(source_board)+'\n',encoding='utf-8')
 d=json.loads((A/paths[3]).read_text());d['schema']='WP10_C203_TERMINAL_DEFINITION_V19_WIRE_PTH'
 for t in d['terminal_features']:
  if t['id'].startswith('WIRE_'):t.update(drill_type='PTH',front_pad_outer_D_mm=3.5,finished_hole_tolerance_mm=None,barrel_plating_min_mm=None)
 d.update(copper_layers=['F.Cu','B.Cu'],native_stackup_mm=actual,finished_copper_thickness_native_bound=False,
  thickness_scope='Source stackup 1.6mm: F.Mask .01/F.Cu .07/core1.43/B.Cu .07/B.Mask .02; native readback pending. STEP remains finished-board envelope, not material-resolved copper.',
  front_copper_scope='Only the two outboard WIRE PTH annuli; no front copper under the maximum capacitor body projection.',
  manufacturing_definition='Two outboard WIRE holes are PTH, finished diameter1.8mm,3.5mm front/back lands. CAP± remain2mm NPTH with rear lands; four mounting holes remain NPTH. Do not CAM-convert the two CAP holes without a separately reviewed design. Laminate, plating and solder process qualification remain open.',
  DRC_local_process_issues_open=True,DRC_current_revision_executed=False,whole_design_complete=False)
 dump(A/paths[3],d)
 m=json.loads((A/paths[4]).read_text());m['source_files'].update({p:sha(A/p) for p in [paths[3],paths[1]]})
 m['materials']['pcb']='1.6mm finished-board envelope; two outboard real PTH terminations on two copper faces; CAP necessary holes remain NPTH. Material/plating/tolerance not qualified.'
 dump(A/paths[4],m)
 step_source=(A/paths[5]).read_text();assert 'WP10_C203_PCB_V17_FINISHED_ENVELOPE_TWO_WIRE_NPTH_ADDED' in step_source
 (A/paths[5]).write_text(step_source.replace('WP10_C203_PCB_V17_FINISHED_ENVELOPE_TWO_WIRE_NPTH_ADDED','WP10_C203_PCB_FINISHED_ENVELOPE_WIRE_HOLES_PLATING_NOT_RESOLVED'),encoding='utf-8')
 dump(receipt,dict(status='ACTUAL_SOURCE_EDITED__NATIVE_READBACK_DRC_PENDING',timestamp=datetime.datetime.now().astimezone().isoformat(),
  changed_wire_terminations=changes,stackup_source_mm=actual,unchanged_finished_board_mm=[50,48,1.6],unchanged_component_holes='Two CAP holes remain NPTH; no new copper under body',
  preserved='Native nets, six B.Cu segments, outline and board finished-hole positions/sizes preserved by AST assertions; original assembly parent retained.',
  source_files={p:sha(A/p) for p in paths[:6]},historical_source_archive=str(H),
  expected_DRC_reduction=dict(hole_clearance=4,solder_mask_bridge=2,basis='From two repaired hole/land groups in old report; not an executed DRC result'),
  actual_new_DRC_errors=None,native_readback_executed=False,manufacturing_qualified=False,whole_design_complete=False))
 print(json.dumps(dict(status='SOURCE_EDITED_NATIVE_PENDING',PTH_wire_holes=2,front_gap_mm=changes[0]['front_copper_to_max_body_mm'])))
if __name__=='__main__':main()
