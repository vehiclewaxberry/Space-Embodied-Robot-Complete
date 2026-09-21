"""Accept the checked electrical delta in the same working candidate, with history."""
import json,csv,shutil,copy,datetime,xml.etree.ElementTree as ET
from terminals_v29 import A,H,ROWS,sha,dump
C=A/'coupled_closure';assert not (C/'CANDIDATE_V29.json').exists()
ea=json.loads((A/'results/TERMINAL_ELECTRICAL_AUDIT_V29.json').read_text());ga=json.loads((C/'TERMINAL_GEOMETRY_CHECK_V29.json').read_text());assert ea['passed'] and ga['passed']
old=json.loads((C/'CANDIDATE.json').read_text());planned={str(A/'ecad/wp10_power_1.kicad_sch')}
assert all(p in planned or sha(p)==h for p,h in old['source_lock'].items())
rows=[]
for dst,src in [('ecad/wp10_system.xml','ecad/wp10_system_v29.xml'),('ecad/wp10_main_input.kicad_pcb','ecad/wp10_main_input_v29_candidate.kicad_pcb')]:
 rows.append(dict(path=dst,before_sha256=sha(A/dst),after_sha256=sha(A/src)));shutil.copy2(A/src,A/dst)
sel=A/'power/SELECTED_BOM.csv';shutil.copy2(sel,H/'power/SELECTED_BOM.csv')
with sel.open(encoding='utf-8-sig',newline='') as f:r=csv.DictReader(f);fields=r.fieldnames;parts=list(r)
assert not any(p['MPN']=='74651195R' for p in parts)
parts.append(dict(role='main input terminals J204 J205 J206 J207',manufacturer='Wuerth Elektronik',MPN='74651195R',quantity=4,status='PROTOTYPE_CANDIDATE_LUG_SOLDER_TORQUE_UNQUALIFIED',source='terminal_v29/74651195R.pdf'))
with sel.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(parts)
rt=ET.parse(A/'ecad/wp10_system.xml').getroot();comps=rt.findall('./components/comp');nets=rt.findall('./nets/net')
with (C/'ACTIVE_ELECTRICAL_BOM_V29.csv').open('w',encoding='utf-8',newline='') as f:
 w=csv.writer(f);w.writerow(['ref','value_or_MPN','footprint','sheet','source','source_sha256','selection_status'])
 for c in comps:w.writerow([c.get('ref'),c.findtext('value'),c.findtext('footprint'),c.find('sheetpath').get('names'),'ecad/wp10_system.xml',sha(A/'ecad/wp10_system.xml'),'ACTUAL_NETLIST_VALUE_NOT_PROCUREMENT_RELEASE'])
with (C/'PIN_NETWORKS_V29.csv').open('w',encoding='utf-8',newline='') as f:
 w=csv.writer(f);w.writerow(['ref','pin','net','pin_type'])
 for n in nets:
  for p in n.findall('node'):w.writerow([p.get('ref'),p.get('pin'),n.get('name'),p.get('pintype')])
c=copy.deepcopy(old);c['schema']='WP10_COUPLED_CANDIDATE_V29';c['parent']='Same WP10 candidate: V26 ECAD -> V29 terminal delta, V28 spreader source plan; original 873/99 parent and 37-row closure preserved.'
allow=planned|{str(A/'ecad/wp10_system.xml'),str(A/'ecad/wp10_main_input.kicad_pcb')}
for p,h in list(c['source_lock'].items()):
 if sha(p)!=h:assert p in allow,p;c['source_lock'][p]=sha(p)
newfiles=['power/MAIN_INPUT_BOARD_DEFINITION_V29.json','power/MAIN_INPUT_COPPER_LOSS_V29.json','power/SELECTED_BOM.csv','ecad/WP10_TERMINALS.pretty/MP_Wurth_WP-THRSH_74651195R.kicad_mod','coupled_closure/TERMINAL_GEOMETRY_INPUTS_V29.json','coupled_closure/main_input_terminals_v29.step.py','coupled_closure/main_input_terminals_v29.step','coupled_closure/SPREADER_INSTANCE_PLAN_V28.json','coupled_closure/spreader_v28.step','SYSTEM_CLOSURE_MATRIX.csv']
for p in newfiles:c['source_lock'][str(A/p)]=sha(A/p)
c['source_lock'].update({str(A/p):h for p,h in json.loads((C/'TERMINAL_GEOMETRY_INPUTS_V29.json').read_text())['source_lock'].items()})
c['electrical']['main_R_components_ohm']['copper_20C']=json.loads((A/'power/MAIN_INPUT_COPPER_LOSS_V29.json').read_text())['R20_ohm']
c['terminal_delta']=dict(references=[r[0] for r in ROWS],OEM='74651195R',lug_bound=False,solder_process_qualified=False,torque_reaction_qualified=False,nine_legs_are_one_electrode=True)
c['mechanical_delta']=dict(module_source='main_input_terminals_v29.step.py',module_SOLIDWORKS_importable_STEP='main_input_terminals_v29.step',native_SLDASM=False,native_SLDPRT=False,host_installed=False,solid_count=ga['solid_count'],whole_plan='SPREADER_INSTANCE_PLAN_V28.json',same_974_instance_plan_not_inflated_by_uninstalled_module=True)
dump(C/'CANDIDATE_V29.json',c)
dump(C/'SOURCE_ACTIVATION_V29.json',dict(time_local=datetime.datetime.now().astimezone().isoformat(),active_changed_files=rows,previous_candidate_sha256=sha(C/'CANDIDATE.json'),candidate_sha256=sha(C/'CANDIDATE_V29.json'),source_locks=len(c['source_lock']),old_37_row_matrix_sha256=sha(A/'SYSTEM_CLOSURE_MATRIX.csv'),parent_history_snapshot='history/20260910_V29_before_terminals/SOURCE_SNAPSHOT.json',whole_design_complete=False))
print(json.dumps(dict(accepted=True,components=len(comps),pin_records=sum(len(n.findall('node')) for n in nets),source_locks=len(c['source_lock']))))
