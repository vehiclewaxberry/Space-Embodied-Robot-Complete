"""Check same-candidate CAP delta without changing any electrical rule."""
from pathlib import Path
import json,copy,xml.etree.ElementTree as ET
from erc_source_contract import parse,children,val,properties
from c203_cam_contract_v20 import A,read,sha,current
P='ecad/wp10_c203_terminal.kicad_pcb';N='C203_SingleFace_Terminal_D30_P10_W18'
H='history/20260909_V19_before_CAP_PTH/'
def xy(p):return tuple(float(x) for x in children(p,'at')[0][1:3])
def validate_drc(run,report):
 root=next(p for p in A.parents if (p/'PROJECT_MAP.md').is_file());cli=root/'70_tools/runtime_wp09_kicad/portable/bin/kicad-cli.exe'
 required={P,'ecad/wp10_c203_terminal.kicad_pro','results/CAP_TERMINAL_DRC_NATIVE_V20.json','results/CAP_TERMINAL_DRC_V20.rpt','tools/cap_pth_native_v20.py'}
 assert required<=set(run['inputs']) and all(sha(p)==h for p,h in run['inputs'].items())
 assert run['native_DRC_executed'] is True and len(run['commands'])==2
 for rec,fmt,target in zip(run['commands'],['json','report'],['results/CAP_TERMINAL_DRC_NATIVE_V20.json','results/CAP_TERMINAL_DRC_V20.rpt']):
  assert rec['command']==[str(cli),'pcb','drc','--format',fmt,'--severity-all','--exit-code-violations','-o',str(A/target),str(A/P)] and rec['returncode']==0
 assert report['source']=='wp10_c203_terminal.kicad_pcb' and report['kicad_version']=='10.0.6'
 assert set(report['included_severities'])=={'error','warning','exclusion'}
 assert report['violations']==report['unconnected_items']==report['schematic_parity']==[] and run['violations']==0
 assert report['ignored_checks']==read(H+'results/CAP_TERMINAL_DRC_NATIVE_V19.json')['ignored_checks']
 return True
def validate_binding(binding,g):
 xml=ET.parse(A/'ecad/wp10_system.xml').getroot()
 pins={n.get('pin'):net.get('name') for net in xml.findall('./nets/net') for n in net.findall('node') if n.get('ref')=='C203'}
 assert pins==binding['native_C203_pins']=={'1':'WP10_PRECHARGED_PLUS','2':'WP10_INPUT_RETURN'}
 assert binding['board_sha256']==g['board_sha256']==sha(P) and binding['source_xml_sha256']==sha('ecad/wp10_system.xml')
 assert g['native_C203_binding_sha256']==sha('results/CAP_TERMINAL_NATIVE_BINDING.json')
 assert binding['physical_electrical_pads']==len([p for p in g['pads'] if p['number']])==4 and binding['logical_pins']==len(pins)==2
 assert binding['physical_holes_plated']==binding['physical_holes_nonplated']==4
 assert all(p['net']==pins[p['number']] for p in g['pads'] if p['number'])
 return True
def validate_features(d,cap):
 expected={'CAP_PLUS':([-5,0],'1',2,0),'CAP_MINUS':([5,0],'2',2,0),'WIRE_PLUS':([-14,14],'1',1.8,3.5),'WIRE_MINUS':([14,14],'2',1.8,3.5)}
 assert d['board']==P and d['pcb_origin_xy_mm']==[100,100]
 assert len(d['terminal_features'])==4 and {t['id'] for t in d['terminal_features']}==set(expected)
 for t in d['terminal_features']:
  pos,pin,hole,front=expected[t['id']];p=next(p for p in children(cap,'pad') if xy(p)==tuple(pos))
  assert t['local_xy_mm']==pos and t['drill_type']=='PTH' and val(p[1])==t['logical_pin']==pin and val(children(p,'net')[0][-1])==t['native_net']
  assert t['drill_mm']==float(children(p,'drill')[0][1])==hole and t['pad_outer_D_mm']==float(children(p,'size')[0][1])==3.5
  assert t['front_pad_outer_D_mm']==front and t.get('back_pad_outer_D_mm',t['pad_outer_D_mm'])==3.5
  assert t.get('front_mask_opening_D_mm',t['pad_outer_D_mm'])==t.get('back_mask_opening_D_mm',t['pad_outer_D_mm'])==3.5
 return True
def main():
 b=parse((A/P).read_text());old=parse((A/(H+P)).read_text());d=read('power/CAP_TERMINAL_DEFINITION.json')
 lib=f'ecad/WP10_PASSIVES.pretty/{N}.kicad_mod';canonical=f'power/cap_terminal_sources/{N}.kicad_mod'
 f=parse((A/lib).read_text());assert f==parse((A/canonical).read_text())
 cap=lambda t:next(x for x in children(t,'footprint') if properties(x).get('Reference')=='C203')
 for tag in ['segment','arc','zone','net','gr_line','general','setup']:
  assert children(b,tag)==children(old,tag),'Unapproved board delta: '+tag
 assert sha('ecad/wp10_c203_terminal.kicad_pro')==sha(H+'ecad/wp10_c203_terminal.kicad_pro')
 for fp in [cap(b),f]:
  pads=children(fp,'pad');assert len(pads)==4
  for pos,pin,diameter in [((-5,0),'1',2),((5,0),'2',2),((-14,14),'1',1.8),((14,14),'2',1.8)]:
   matches=[p for p in pads if xy(p)==pos];assert len(matches)==1;p=matches[0]
   assert val(p[1])==pin and p[2:4]==['thru_hole','circle'] and float(children(p,'drill')[0][1])==diameter
   assert [float(x) for x in children(p,'size')[0][1:]]==[3.5,3.5] and children(p,'layers')==[['layers','"*.Cu"','"*.Mask"']]
   if diameter==2:
    assert children(p,'remove_unused_layers')==[['remove_unused_layers','yes']] and children(p,'keep_end_layers')==[['keep_end_layers','no']]
   else:assert children(p,'remove_unused_layers') in [[],[['remove_unused_layers','no']]]
 assert [p for p in children(cap(old),'pad') if xy(p) in [(-14,14),(14,14)]]==[p for p in children(cap(b),'pad') if xy(p) in [(-14,14),(14,14)]]
 assert [f for f in children(b,'footprint') if properties(f).get('Reference')!='C203']==[f for f in children(old,'footprint') if properties(f).get('Reference')!='C203']
 validate_features(d,cap(b))
 data,g,cam=current();run=read('results/CAP_PTH_DRC_EXECUTION_V20.json');report=read('results/CAP_TERMINAL_DRC_NATIVE_V20.json')
 validate_drc(run,report)
 assert not (A/'ecad/wp10_c203_terminal.kicad_dru').exists(),'New external DRC rules need explicit review'
 assert not read('ecad/wp10_c203_terminal.kicad_pro')['board']['design_settings'].get('drc_exclusions',[])
 binding=read('results/CAP_TERMINAL_NATIVE_BINDING.json')
 validate_binding(binding,g)
 faults=[]
 def reject(name,fn):
  try:fn()
  except (AssertionError,StopIteration):faults.append(dict(name=name,rejected=True));return
  raise AssertionError(name)
 def bad_run(**kw):return dict(copy.deepcopy(run),**kw)
 reject('empty_DRC_inputs',lambda:validate_drc(bad_run(inputs={}),report))
 reject('empty_DRC_commands',lambda:validate_drc(bad_run(commands=[]),report))
 reject('DRC_not_executed',lambda:validate_drc(bad_run(native_DRC_executed=False),report))
 for field,value in [('source','other.kicad_pcb'),('kicad_version','0'),('included_severities',[])]:
  reject('wrong_DRC_'+field,lambda field=field,value=value:validate_drc(run,dict(report,**{field:value})))
 reject('swapped_binding_polarity',lambda:validate_binding(dict(binding,native_C203_pins={'1':'WP10_INPUT_RETURN','2':'WP10_PRECHARGED_PLUS'}),g))
 reject('zero_binding_pad_count',lambda:validate_binding(dict(binding,physical_electrical_pads=0),g))
 reject('zero_binding_pin_count',lambda:validate_binding(dict(binding,logical_pins=0),g))
 reject('empty_terminal_feature_set',lambda:validate_features(dict(d,terminal_features=[]),cap(b)))
 for field,value in [('drill_mm',1),('front_pad_outer_D_mm',3.5),('back_mask_opening_D_mm',2)]:
  q=copy.deepcopy(d);q['terminal_features'][0][field]=value
  reject('wrong_CAP_'+field,lambda q=q:validate_features(q,cap(b)))
 paths=[P,lib,canonical,'power/CAP_TERMINAL_DEFINITION.json','ecad/wp10_c203_terminal.kicad_pro','ecad/wp10_system.xml','results/CAP_TERMINAL_NATIVE_BINDING.json','results/CAP_TERMINAL_NATIVE_GEOMETRY.json','results/CAP_PTH_DRC_EXECUTION_V20.json','results/CAP_TERMINAL_DRC_NATIVE_V20.json','tools/check_cap_pth_source_v20.py','tools/c203_cam_contract_v20.py',H+P,H+'ecad/wp10_c203_terminal.kicad_pro',H+'results/CAP_TERMINAL_DRC_NATIVE_V19.json']
 out=dict(passed=True,status='CAP_PTH_SOURCE_NATIVE_CAM_AND_DRC_CURRENT',DRC_violations=0,unconnected_items=0,electrical_PTH=4,mount_NPTH=4,six_BCu_tracks_unchanged=True,C203_board_networks_preserved=True,setup_rules_and_ignored_checks_unchanged=True,no_external_kicad_dru=True,faults=faults,native_board_sha256=sha(P),inputs={p:sha(p) for p in paths},manufacturing_release=False,whole_design_complete=False)
 (A/'results/CAP_PTH_SOURCE_CHECK_V20.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(out['status'])
if __name__=='__main__':main()
