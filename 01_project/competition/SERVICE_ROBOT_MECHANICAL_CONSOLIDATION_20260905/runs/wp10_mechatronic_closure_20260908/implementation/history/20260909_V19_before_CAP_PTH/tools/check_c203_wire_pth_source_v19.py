"""Check actual working PCB syntax and physical pad-stack intent, without KiCad."""
from pathlib import Path
import json,math,hashlib,copy
from erc_source_contract import parse,children,val,properties
A=Path(__file__).resolve().parents[1];H=A/'history/20260909_V19_before_wire_pth'
N='C203_SingleFace_Terminal_D30_P10_W18'
P='ecad/wp10_c203_terminal.kicad_pcb'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def xy(p):return tuple(float(x) for x in children(p,'at')[0][1:3])
def pads(fp):return children(fp,'pad')
def evaluate(board,footprint,definition):
 cap=next(f for f in children(board,'footprint') if properties(f).get('Reference')=='C203')
 for fp in [cap,footprint]:
  assert len(pads(fp))==6
  for coords,pin in [((-14,14),'1'),((14,14),'2')]:
   matched=[p for p in pads(fp) if xy(p)==coords];assert len(matched)==1
   p=matched[0];assert val(p[1])==pin and p[2:4]==['thru_hole','circle']
   assert children(p,'drill')==[['drill','1.8']] and children(p,'size')==[['size','3.5','3.5']]
   assert children(p,'layers')==[['layers','"*.Cu"','"*.Mask"']]
   assert math.hypot(*coords)-15.5-1.75>=2
  for coords,pin in [((-5,0),'1'),((5,0),'2')]:
   group=[p for p in pads(fp) if xy(p)==coords];assert len(group)==2
   copper=next(p for p in group if p[2]=='smd');hole=next(p for p in group if p[2]=='np_thru_hole')
   assert val(copper[1])==pin and children(copper,'layers')==[['layers','"B.Cu"','"B.Mask"']]
   assert children(hole,'drill')==[['drill','2']]
 allpads=[p for f in children(board,'footprint') for p in pads(f)]
 assert sum(p[2]=='thru_hole' for p in allpads)==2 and sum(p[2]=='np_thru_hole' for p in allpads)==6
 native_net={val(children(p,'net')[0][-1]) for p in pads(cap) if val(p[1])}
 assert native_net=={'WP10_PRECHARGED_PLUS','WP10_INPUT_RETURN'}
 for p in pads(cap):
  if val(p[1]):assert val(children(p,'net')[0][-1])==('WP10_PRECHARGED_PLUS' if val(p[1])=='1' else 'WP10_INPUT_RETURN')
 stack=children(children(board,'setup')[0],'stackup')[0]
 actual={val(l[1]):float(children(l,'thickness')[0][1]) for l in children(stack,'layer') if children(l,'thickness')}
 assert actual==definition['native_stackup_mm']=={'F.Mask':.01,'F.Cu':.07,'dielectric 1':1.43,'B.Cu':.07,'B.Mask':.02}
 for t in definition['terminal_features']:
  assert t['drill_type']==('PTH' if t['id'].startswith('WIRE_') else 'NPTH')
  assert t['local_xy_mm']==[t['S_face_mm'][1],-50-t['S_face_mm'][2]]
 return True
def main():
 b=parse((A/P).read_text());f=parse((A/f'ecad/WP10_PASSIVES.pretty/{N}.kicad_mod').read_text());d=json.loads((A/'power/CAP_TERMINAL_DEFINITION.json').read_text())
 assert f==parse((A/f'power/cap_terminal_sources/{N}.kicad_mod').read_text())
 assert evaluate(b,f,d)
 old=parse((H/P).read_text());oldcap=next(x for x in children(old,'footprint') if properties(x).get('Reference')=='C203');newcap=next(x for x in children(b,'footprint') if properties(x).get('Reference')=='C203')
 assert [p for p in pads(oldcap) if xy(p) in [(-5,0),(5,0)]]==[p for p in pads(newcap) if xy(p) in [(-5,0),(5,0)]]
 for tag in ['segment','arc','zone','net','gr_line','general']:
  assert children(b,tag)==children(old,tag),tag
 # All setup rules except physical stackup are exactly preserved.
 assert [x for x in children(b,'setup')[0][1:] if x[0]!='stackup']==[x for x in children(old,'setup')[0][1:] if x[0]!='stackup']
 faults=[]
 def reject(name,mutate):
  bb,ff,dd=copy.deepcopy(b),copy.deepcopy(f),copy.deepcopy(d);mutate(bb,ff,dd)
  try:evaluate(bb,ff,dd);ok=False
  except (AssertionError,StopIteration):ok=True
  assert ok,name;faults.append(dict(name=name,rejected=True))
 def wire(fp):return next(p for p in pads(fp) if xy(p)==(-14,14))
 reject('wire_falsely_left_as_SMD',lambda b,f,d:wire(f).__setitem__(2,'smd'))
 reject('front_copper_thickness_zero',lambda b,f,d:d['native_stackup_mm'].update({'F.Cu':0}))
 reject('finished_wire_hole_shrunk',lambda b,f,d:children(wire(f),'drill')[0].__setitem__(1,'1.0'))
 reject('wire_positive_logical_pin_swapped',lambda b,f,d:wire(f).__setitem__(1,'"2"'))
 reject('front_copper_added_under_capacitor',lambda b,f,d:children(next(p for p in pads(f) if xy(p)==(-5,0) and p[2]=='smd'),'layers')[0].append('"F.Cu"'))
 paths=[P,f'ecad/WP10_PASSIVES.pretty/{N}.kicad_mod',f'power/cap_terminal_sources/{N}.kicad_mod','power/CAP_TERMINAL_DEFINITION.json','tools/check_c203_wire_pth_source_v19.py','tools/cap_terminal_native.py','tools/check_cap_terminal_copper.py']
 result=dict(status='PASS_SOURCE_PADSTACK_DELTA_ONLY',passed=True,wire_PTH_count=2,remaining_NPTH_count=6,front_copper_to_max_cap_body_mm=math.sqrt(392)-1.75-15.5,original_six_BCu_tracks_unchanged=True,under_body_CAP_pad_groups_unchanged=True,setup_rules_unchanged=True,faults=faults,inputs={p:sha(A/p) for p in paths},native_KiCad_readback=False,native_DRC_executed=False,actual_DRC_count=None,manufacturing_qualified=False,whole_design_complete=False)
 (A/'results/C203_WIRE_PTH_SOURCE_CHECK_V19.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
 print(json.dumps(dict(passed=True,faults=len(faults),native_DRC_executed=False)))
if __name__=='__main__':main()
